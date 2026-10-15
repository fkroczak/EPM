"""Benchmark der Modellvarianten auf der Ziel-VM (Plan Phase 0, Auftrag 2: Qualität, Geschwindigkeit, Speicher).

Läuft im Container ``ki-worker`` (Netz „intern“) gegen einen vorübergehend gestarteten llama-server je Variante
(``werkzeuge/ki-benchmark.sh`` startet ihn, misst Speicher und CPU von außen und ruft diesen Teil auf).

Testseiten:
- **synthetisch** (immer): Laborbefund als sauberer Scan und als „Foto“ (schräg, Schatten, Rauschen), Arztbrief –
  mit bekanntem Text und bekannten Laborwerten; dazu ein großes PDF (``--grosses-pdf``, Standard 20 Seiten) für den
  Durchsatz.
- **eigene** (optional): Bilder/PDFs in einem Ordner auf dem Server, z. B. ``hand_*.jpg`` (Handschrift),
  ``tabelle_*.png``, ``alt_*.pdf``. Liegt daneben ``NAME.txt`` (Text) bzw. ``NAME.json`` (``{"laborwerte":
  [["Kalium", "3.2"], …]}``), wird die Qualität gemessen. Die Dateien verlassen den Server nicht.

Ergebnis je Seite: Zeit für Abschreiben und Strukturieren, Tokens je Sekunde, Zeichenfehlerrate (CER) gegen den
erwarteten Text, Treffer der Laborwerte (Precision/Recall/F1) – zusammengefasst je Kategorie.
"""
import json
import time
from pathlib import Path

from scans.ocr import auswertung

from . import prompts
from .modell import Client, ModellFehler
from .pruefung import Katalog, dezimal


def cer(erwartet: str, gelesen: str) -> float | None:
    """Zeichenfehlerrate (Levenshtein / Länge), Leerraum vereinheitlicht."""
    a, b = " ".join(erwartet.split()), " ".join(gelesen.split())
    if not a:
        return None
    vorher = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        jetzt = [i]
        for j, cb in enumerate(b, 1):
            jetzt.append(min(vorher[j] + 1, jetzt[j - 1] + 1, vorher[j - 1] + (ca != cb)))
        vorher = jetzt
    return round(vorher[-1] / len(a), 4)


def _jpeg(bild_bytes: bytes, max_px: int) -> list[bytes]:
    """Datei (PNG/JPG/PDF) → JPEG je Seite, auf ``max_px`` verkleinert."""
    import cv2

    from scans.ocr.laden import seiten_laden

    _mime, seiten = seiten_laden(bild_bytes, max_seiten=200)
    aus = []
    for s in seiten:
        h, b = s.bild.shape[:2]
        f = min(1.0, max_px / max(h, b))
        bild = cv2.resize(s.bild, (int(b * f), int(h * f)), interpolation=cv2.INTER_AREA) if f < 1 else s.bild
        aus.append(cv2.imencode(".jpg", bild, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes())
    return aus


def synthetische_seiten(grosses_pdf: int = 20) -> list[dict]:
    from scans import testbilder

    namen = {"nachname": "Muster", "vorname": "Erika", "geburt": "14.03.1961"}
    labor = testbilder.seite(testbilder.LABOR, **namen)
    brief = testbilder.seite(testbilder.BRIEF, **namen)

    def text(zeilen):
        aus = []
        for z in zeilen:
            if z is None:
                continue
            if isinstance(z, tuple):
                z = "\t".join(z[1]) if z[0] == "tab" else z[1]
            aus.append(z.format(**namen))
        return "\n".join(aus)

    werte = [[r[1][0], str(dezimal(r[1][1]))] for r in testbilder.LABOR
             if isinstance(r, tuple) and r[0] == "tab" and dezimal(r[1][1]) is not None]
    seiten = [
        {"name": "synthetisch_labor_scan", "kategorie": "tabelle", "daten": testbilder.png(labor),
         "text": text(testbilder.LABOR), "laborwerte": werte},
        {"name": "synthetisch_labor_foto", "kategorie": "foto", "daten": testbilder.foto(labor, seed=3),
         "text": text(testbilder.LABOR), "laborwerte": werte},
        {"name": "synthetisch_arztbrief", "kategorie": "brief", "daten": testbilder.png(brief),
         "text": text(testbilder.BRIEF), "laborwerte": []},
    ]
    if grosses_pdf:
        seiten.append({"name": f"synthetisch_pdf_{grosses_pdf}_seiten", "kategorie": "grosses_pdf",
                       "daten": testbilder.pdf(*([labor, brief] * ((grosses_pdf + 1) // 2))[:grosses_pdf]),
                       "text": "", "laborwerte": [], "nur_zeit": True})
    return seiten


def eigene_seiten(ordner: Path) -> list[dict]:
    aus = []
    for p in sorted(ordner.iterdir()) if ordner and ordner.is_dir() else []:
        if p.suffix.lower() not in (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"):
            continue
        txt, js = p.with_suffix(".txt"), p.with_suffix(".json")
        erwartet = json.loads(js.read_text()) if js.exists() else {}
        aus.append({"name": p.name, "kategorie": p.stem.split("_")[0] if "_" in p.stem else "eigene",
                    "daten": p.read_bytes(), "text": txt.read_text() if txt.exists() else "",
                    "laborwerte": erwartet.get("laborwerte") or []})
    return aus


def _f1(erwartet: set, gefunden: set) -> dict:
    treffer = len(erwartet & gefunden)
    p = treffer / len(gefunden) if gefunden else (1.0 if not erwartet else 0.0)
    r = treffer / len(erwartet) if erwartet else 1.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def seite_messen(client: Client, seite: dict, katalog: Katalog, max_px: int) -> dict:
    bilder = _jpeg(seite["daten"], max_px)
    erg = {"name": seite["name"], "kategorie": seite["kategorie"], "seiten": len(bilder), "fehler": ""}
    t0 = time.monotonic()
    texte, extraktionen, tokens = [], [], 0
    try:
        for b in bilder:
            if not seite.get("nur_zeit"):
                a = client.chat(prompts.TRANSKRIPTION, "Bitte die Seite abschreiben.", bilder=[b], max_tokens=3000)
                texte.append(a.text)
                tokens += int(a.tokens.get("completion_tokens") or 0)
            a = client.chat(prompts.EXTRAKTION, prompts.extraktion_text(texte[-1] if texte else "", 1, 1),
                            bilder=[b], schema=prompts.EXTRAKTION_SCHEMA, max_tokens=2500)
            tokens += int(a.tokens.get("completion_tokens") or 0)
            extraktionen.append(a.json())
    except ModellFehler as e:
        erg["fehler"] = str(e)[:300]
    dauer = time.monotonic() - t0
    erg["sekunden"] = round(dauer, 1)
    erg["sekunden_je_seite"] = round(dauer / max(1, len(bilder)), 1)
    erg["tokens_je_sekunde"] = round(tokens / dauer, 2) if dauer else None
    if seite.get("text") and texte:
        erg["cer"] = cer(seite["text"], "\n".join(texte))
    if seite.get("laborwerte") and extraktionen:
        def schl(name, wert):
            p, _a = katalog.finden(name or "")
            z = dezimal(wert)
            return auswertung.norm(p.name if p else name or ""), str(z.normalize()) if z is not None else ""

        erwartet = {schl(n, w) for n, w in seite["laborwerte"]}
        gefunden = {schl(x.get("parameter"), x.get("wert")) for e in extraktionen for x in e.get("laborwerte") or []}
        erg["laborwerte"] = _f1(erwartet, gefunden)
        erg["dokumenttyp"] = extraktionen[0].get("dokumenttyp")
    return erg


def ausfuehren(url: str, *, eigene: Path | None = None, grosses_pdf: int = 20, max_px: int = 1600) -> dict:
    client = Client(url, zeitlimit_s=1800)
    stand = client.bereit()
    if not stand["bereit"]:
        raise ModellFehler(f"Modell-Dienst nicht bereit: {stand['text']}")
    katalog = Katalog()
    seiten = synthetische_seiten(grosses_pdf) + (eigene_seiten(eigene) if eigene else [])
    ergebnisse = [seite_messen(client, s, katalog, max_px) for s in seiten]
    je_kategorie = {}
    for e in ergebnisse:
        k = je_kategorie.setdefault(e["kategorie"], {"seiten": 0, "sekunden": 0.0, "cer": [], "f1": []})
        k["seiten"] += e["seiten"]
        k["sekunden"] += e["sekunden"]
        if e.get("cer") is not None:
            k["cer"].append(e["cer"])
        if e.get("laborwerte"):
            k["f1"].append(e["laborwerte"]["f1"])
    zusammen = {k: {"seiten": v["seiten"], "sekunden_je_seite": round(v["sekunden"] / max(1, v["seiten"]), 1),
                    "cer": round(sum(v["cer"]) / len(v["cer"]), 4) if v["cer"] else None,
                    "laborwerte_f1": round(sum(v["f1"]) / len(v["f1"]), 3) if v["f1"] else None}
                for k, v in je_kategorie.items()}
    return {"modell": stand["modell"], "max_px": max_px, "seiten": ergebnisse, "je_kategorie": zusammen,
            "prompt_version": prompts.PROMPT_VERSION}

