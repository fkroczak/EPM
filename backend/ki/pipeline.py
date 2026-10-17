"""Verarbeitung eines Dokuments (ein ``KiVorgang``) – läuft im KI-Dienst, nie im Backend.

1. **Stufe 1 – klassische Texterkennung** (vorhandene Strecke aus „Scans“: Aufbereitung, Tesseract, PP-OCR; PDF mit
   Textebene direkt). Je Seite Text, Sicherheit und die Reihen für die regelbasierte Auswertung. Das Seitenbild für
   Stufe 2 liegt verschlüsselt in der Arbeitsablage – endet das Nachtfenster mitten im Dokument, geht es in der
   nächsten Nacht dort weiter.
2. **Stufe 2 – Vision-Modell** (Qwen3.5 lokal): Seiten unter der OCR-Schwelle liest das Modell selbst ab
   (Handschrift, schlechte Kopien, Tabellen); danach Extraktion je Seite als JSON nach festem Schema (Dokumenttyp,
   Metadaten, Laborwerte, Infusionen, Medikamente, Diagnosen, Zusammenfassung). Seiten mit sicherer Textebene gehen
   ohne Bild an das Modell (schneller).
3. **Gegenprüfung** mit Regeln (``ki.pruefung``) und der regelbasierten Laborauswertung aus „Scans“.
4. **Felder** zur Prüfung anlegen → Status „Zur Prüfung vorgelegt“.

Ohne Modell-Dienst (oder wenn er ausfällt) liefert die regelbasierte Auswertung allein Vorschläge (Laborwerte,
Datum, Dokumenttyp); der Vorgang trägt dann den Hinweis, dass die KI-Stufe fehlte, und lässt sich später erneut
verarbeiten.

Nichts hiervon schreibt in die Akte.
"""
import logging
import time
from collections import Counter
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from audit.models import SystemEreignis, protokolliere

from . import krypto, prompts, pruefung
from .modell import Client, ModellFehler
from .models import KiEinstellung, KiFeld, KiModellversion, KiRohergebnis, KiSeite, KiVorgang

log = logging.getLogger("epm.ki")
S = KiVorgang.Status


class Abgebrochen(Exception):
    """Nachtfenster zu Ende, Pause wegen Last oder Dienst wird beendet – Vorgang später fortsetzen."""


@dataclass
class Rahmen:
    """Was der Worker der Verarbeitung mitgibt."""
    client: Client | None = None
    sparsam: bool = False
    abbrechen: object = None   # Funktion () -> str|None: Grund zum Abbrechen
    melden: object = None      # Funktion (text, prozent)

    def pruefe_abbruch(self):
        grund = self.abbrechen() if callable(self.abbrechen) else None
        if grund:
            raise Abgebrochen(grund)

    def schritt(self, text: str, prozent: int | None = None):
        if callable(self.melden):
            self.melden(text, prozent)


def _jpeg(bild, max_px: int) -> bytes:
    import cv2

    h, b = bild.shape[:2]
    faktor = min(1.0, max_px / max(h, b))
    if faktor < 1.0:
        bild = cv2.resize(bild, (int(b * faktor), int(h * faktor)), interpolation=cv2.INTER_AREA)
    ok, puffer = cv2.imencode(".jpg", bild, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise ValueError("Seitenbild nicht kodierbar")
    return puffer.tobytes()


def _bildpfad(vorgang: KiVorgang, nr: int):
    pfad = krypto.vorgang_ordner(vorgang.pk) / f"seite-{nr:03d}.bin"
    pfad.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return pfad


def _bezug(vorgang: KiVorgang, nr: int) -> str:
    return f"vorgang:{vorgang.pk}:{vorgang.sha256}:seite:{nr}"


def stufe1(vorgang: KiVorgang, einst: KiEinstellung, rahmen: Rahmen, paddle=None):
    """Klassische Texterkennung aller (noch nicht erkannten) Seiten."""
    from scans.ocr import fusion
    from scans.ocr.erkennung import seite_erkennen
    from scans.ocr.laden import seiten_laden

    daten = vorgang.dokument.pfad.read_bytes()
    import hashlib

    if hashlib.sha256(daten).hexdigest() != vorgang.sha256:
        raise ValueError("Das Dokument wurde seit dem Vormerken geändert – bitte erneut verarbeiten lassen.")
    _mime, seiten = seiten_laden(daten, max_seiten=einst.max_seiten)
    vorgang.seiten = len(seiten)
    vorgang.save(update_fields=["seiten"])
    fertig = set(vorgang.seiten_liste.values_list("nr", flat=True))
    max_px = int(einst.bild_max_px * (0.75 if rahmen.sparsam else 1))
    for i, roh in enumerate(seiten, 1):
        if i in fertig:
            continue
        rahmen.pruefe_abbruch()
        rahmen.schritt(f"Seite {i} von {len(seiten)}: Texterkennung", int(40 * (i - 1) / len(seiten)))
        t0 = time.monotonic()
        auf, ergebnis = seite_erkennen(roh, None, paddle=paddle, stufe=1 if rahmen.sparsam else 0)
        k = fusion.kennzahlen(ergebnis)
        krypto.schreiben(_bildpfad(vorgang, i), _jpeg(auf.bild if auf.bild.ndim == 3 else auf.grau, max_px),
                         _bezug(vorgang, i))
        KiSeite.objects.create(vorgang=vorgang, nr=i, text=fusion.text_aus_json(ergebnis), konfidenz=k["sicherheit"],
                               verfahren=ergebnis.get("verfahren") or [], ergebnis=ergebnis,
                               breite=int(ergebnis.get("breite") or 0), hoehe=int(ergebnis.get("hoehe") or 0),
                               dauer_s=round(time.monotonic() - t0, 2))


def _modellversion() -> tuple[KiModellversion | None, str]:
    mv = KiModellversion.aktiv("vision")
    return mv, (mv.name if mv else "")


def _roh(vorgang, art, seite, antwort, mv, name, parameter):
    KiRohergebnis.objects.create(vorgang=vorgang, art=art, seite=seite, modellversion=mv,
                                 modell=antwort.modell or name, prompt_version=prompts.PROMPT_VERSION,
                                 parameter=parameter, antwort=antwort.text[:200000], dauer_s=antwort.dauer_s)


def stufe2(vorgang: KiVorgang, einst: KiEinstellung, rahmen: Rahmen) -> list[tuple[int, dict]]:
    """Vision-Modell: Transkription unsicherer Seiten und Extraktion je Seite → [(Seite, JSON)]."""
    client = rahmen.client
    mv, name = _modellversion()
    ergebnisse = []
    seiten = list(vorgang.seiten_liste.all())
    for s in seiten:
        rahmen.pruefe_abbruch()
        bild = None
        pfad = _bildpfad(vorgang, s.nr)
        if pfad.exists():
            bild = krypto.lesen(pfad, _bezug(vorgang, s.nr))
        digital = "textebene" in (s.verfahren or []) or (s.ergebnis or {}).get("textebene")
        unsicher = s.konfidenz is None or s.konfidenz < einst.ocr_schwelle
        if not s.vision_fertig and unsicher and bild is not None and not rahmen.sparsam:
            rahmen.schritt(f"Seite {s.nr} von {len(seiten)}: KI liest die Seite", 40 + int(30 * s.nr / len(seiten)))
            a = client.chat(prompts.TRANSKRIPTION, "Bitte die Seite abschreiben.", bilder=[bild], max_tokens=3000)
            _roh(vorgang, "transkription", s.nr, a, mv, name, {"max_tokens": 3000})
            s.vision_text = a.text
        s.vision_fertig = True
        s.save(update_fields=["vision_text", "vision_fertig"])
        rahmen.pruefe_abbruch()
        rahmen.schritt(f"Seite {s.nr} von {len(seiten)}: KI strukturiert", 70 + int(20 * s.nr / len(seiten)))
        text = s.vision_text or s.text
        mit_bild = bild is not None and not (digital and not unsicher)
        a = client.chat(prompts.EXTRAKTION, prompts.extraktion_text(text, s.nr, len(seiten)),
                        bilder=[bild] if mit_bild else None, schema=prompts.EXTRAKTION_SCHEMA, max_tokens=2500)
        _roh(vorgang, "extraktion", s.nr, a, mv, name, {"max_tokens": 2500, "bild": mit_bild})
        try:
            ergebnisse.append((s.nr, a.json()))
        except ModellFehler as e:
            log.warning("%s Seite %s: %s", vorgang, s.nr, e)
    if len(ergebnisse) > 1:
        teile = [f"Seite {nr}: {e.get('zusammenfassung', '')}" for nr, e in ergebnisse if e.get("zusammenfassung")]
        if teile:
            rahmen.pruefe_abbruch()
            a = client.chat(prompts.ZUSAMMENFASSUNG, "\n".join(teile), max_tokens=600)
            _roh(vorgang, "zusammenfassung", None, a, mv, name, {"max_tokens": 600})
            vorgang.zusammenfassung = a.text[:5000]
    elif ergebnisse:
        vorgang.zusammenfassung = str(ergebnisse[0][1].get("zusammenfassung") or "")[:5000]
    vorgang.modellversion = mv
    return ergebnisse


def _regeln(vorgang: KiVorgang) -> dict:
    """Regelbasierte Auswertung wie in „Scans“ (Laborwerte, Datum, Arten, Absender)."""
    from scans import lernen
    from scans.dienst import diagnoseliste, katalog
    from scans.ocr import auswertung

    seiten = [s.ergebnis for s in vorgang.seiten_liste.all() if s.ergebnis]
    if not seiten:
        return {}
    return auswertung.auswerten(seiten, katalog(), timezone.localdate(), lernen.gelerntes(),
                                diagnoseliste=diagnoseliste())


TYP_AUS_REGELN = {"labor": "labor", "arztbrief": "arztbericht"}


def felder_bilden(vorgang: KiVorgang, modell: list[tuple[int, dict]], regeln: dict) -> list[KiFeld]:
    """Modell- und Regelergebnis → Felder zur Prüfung (mit Konfidenz und Hinweisen)."""
    from scans import lernen

    katalog = pruefung.Katalog(gelernt=lernen.gelerntes())
    seiten = {s.nr: s for s in vorgang.seiten_liste.all()}
    absender = (regeln.get("labor") or {}).get("name") or ""
    quelle_norm = pruefung.auswertung.norm(absender)[:150]
    regel_werte = (regeln.get("labor") or {}).get("werte") or []
    felder: list[KiFeld] = []

    def feld(gruppe, schluessel, ergebnis, nr=0):
        felder.append(KiFeld(vorgang=vorgang, gruppe=gruppe, schluessel=schluessel, nr=nr, wert=ergebnis["wert"],
                             konfidenz=ergebnis.get("konfidenz"), quelle=ergebnis.get("quelle", ""),
                             belege=ergebnis.get("belege") or {}))

    # Dokumenttyp: Mehrheit der Seiten (Modell), sonst Regeln
    typen = Counter(e.get("dokumenttyp") for _nr, e in modell if e.get("dokumenttyp"))
    arten = regeln.get("arten") or []
    if typen:
        typ, n = typen.most_common(1)[0]
        konf = 0.6 + 0.3 * n / max(1, len(modell))
        if typ == "labor" and "labor" in arten:
            konf += 0.1
        feld("meta", "dokumenttyp", {"wert": {"wert": typ}, "konfidenz": min(konf, 1.0), "quelle": "vision",
                                     "belege": {"hinweise": [f"{n} von {len(modell)} Seiten"]}})
    elif arten:
        feld("meta", "dokumenttyp", {"wert": {"wert": TYP_AUS_REGELN.get(arten[0], "sonstiges")}, "konfidenz": 0.6,
                                     "quelle": "regeln", "belege": {"hinweise": [f"Regeln: {', '.join(arten)}"]}})

    # Metadaten: erste Seite, auf der die Angabe steht
    def erste(schluessel):
        for nr, e in modell:
            if e.get(schluessel) not in (None, "", []):
                return nr, e[schluessel]
        return None, None

    nr, roh = erste("dokumentdatum")
    d = pruefung.datum(roh)
    if d:
        feld("meta", "dokumentdatum", {"wert": {"wert": d.isoformat()}, "konfidenz": 0.75, "quelle": "vision",
                                       "belege": {"seite": nr, "hinweise": []}})
    elif regeln.get("datum"):
        feld("meta", "dokumentdatum", {"wert": {"wert": regeln["datum"]}, "konfidenz": 0.65, "quelle": "regeln",
                                       "belege": {"hinweise": [f"Regeln ({regeln.get('datum_quelle') or ''})"]}})
    for schluessel in ("erstellungsdatum", "absender", "fall", "sprache", "vertraulich"):
        nr, roh = erste(schluessel)
        if roh is None:
            continue
        if schluessel == "erstellungsdatum":
            roh = pruefung.datum(roh)
            if roh is None:
                continue
            roh = roh.isoformat()
        feld("meta", schluessel, {"wert": {"wert": roh if isinstance(roh, bool) else str(roh)[:200]},
                                  "konfidenz": 0.7, "quelle": "vision", "belege": {"seite": nr}})
    if not any(f.schluessel == "absender" for f in felder) and absender:
        feld("meta", "absender", {"wert": {"wert": absender[:200]}, "konfidenz": 0.6, "quelle": "regeln",
                                  "belege": {}})
    nr, roh = erste("patient")
    abgleich = pruefung.patient_abgleich(roh, vorgang.patient)
    if abgleich:
        abgleich["belege"]["seite"] = nr
        feld("meta", "patient", abgleich)
    ocr_konf = [s.konfidenz for s in seiten.values() if s.konfidenz is not None]
    feld("meta", "ocr_konfidenz", {"wert": {"wert": round(min(ocr_konf), 3) if ocr_konf else None,
                                            "seiten": len(seiten)},
                                   "konfidenz": min(ocr_konf) if ocr_konf else None, "quelle": "ocr", "belege": {}})

    # Laborwerte: Modell je Seite, gegengeprüft; Werte, die nur die Regeln fanden, kommen dazu
    def schl(w):
        return w.get("parameter") or pruefung.auswertung.norm(w.get("erkannt_als") or "")

    gesehen = set()
    lfd = 0
    for nr, e in modell:
        s = seiten.get(nr)
        text = s.text if s else ""  # Beleg nur aus der klassischen Erkennung, nicht aus dem Modell selbst
        regeln_seite = [r for r in regel_werte if (r.get("seite") or 0) + 1 == nr]
        for roh in e.get("laborwerte") or []:
            erg = pruefung.laborwert(roh, katalog, ocr_text=text, seite=nr,
                                     seite_konfidenz=s.konfidenz if s else None, regeln=regeln_seite,
                                     quelle=quelle_norm)
            k = (schl(erg["wert"]), erg["wert"].get("datum"))
            if k in gesehen:
                continue
            gesehen.add(k)
            lfd += 1
            feld("labor", "laborwert", erg, lfd)
    vom_modell = {k for k, _d in gesehen}
    for r in regel_werte:
        if schl(r) in vom_modell:
            continue
        vom_modell.add(schl(r))
        s = seiten.get((r.get("seite") or 0) + 1)
        lfd += 1
        feld("labor", "laborwert", pruefung.regelwert(r, s.konfidenz if s else None), lfd)

    lfd = 0
    for nr, e in modell:
        s = seiten.get(nr)
        text = s.text if s else ""
        for roh in e.get("infusionen") or []:
            lfd += 1
            feld("infusion", "position", pruefung.infusion(roh, ocr_text=text, seite=nr), lfd)
    lfd = 0
    for nr, e in modell:
        for roh in e.get("medikamente") or []:
            lfd += 1
            feld("medikation", "medikament", pruefung.medikament(roh, seite=nr), lfd)
    lfd, codes = 0, set()
    for nr, e in modell:
        s = seiten.get(nr)
        for roh in e.get("diagnosen") or []:
            erg = pruefung.diagnose(roh, ocr_text=s.text if s else "", seite=nr)
            key = erg["wert"]["icd_code"] or erg["wert"]["bezeichnung"].lower()
            if key in codes:
                continue
            codes.add(key)
            lfd += 1
            feld("diagnose", "diagnose", erg, lfd)
    if vorgang.zusammenfassung:
        feld("text", "zusammenfassung", {"wert": {"text": vorgang.zusammenfassung, "aktenabschnitt": ""},
                                         "konfidenz": 0.6, "quelle": "vision", "belege": {}})
    verlauf = "\n".join(str(e.get("verlauf")) for _nr, e in modell if e.get("verlauf"))
    if verlauf:
        feld("text", "verlauf", {"wert": {"text": verlauf[:5000], "aktenabschnitt": "therapie"}, "konfidenz": 0.6,
                                 "quelle": "vision", "belege": {}})
    offen = [p for _nr, e in modell for p in (e.get("offene_punkte") or []) if p]
    if offen:
        feld("text", "offene_punkte", {"wert": {"text": "\n".join(f"• {p}" for p in offen)[:5000],
                                                "aktenabschnitt": "empfehlung"},
                                       "konfidenz": 0.55, "quelle": "vision", "belege": {}})
    return felder


def alte_felder_entfernen(v: KiVorgang):
    """Offene Vorschläge einer früheren Verarbeitung entfernen; korrigierte bleiben (als verworfen) für das
    Qualitäts-Dashboard, übernommene unverändert."""
    offen = v.felder.filter(status__in=[KiFeld.Status.OFFEN, KiFeld.Status.FREIGEGEBEN])
    offen.filter(korrekturen__isnull=False).update(status=KiFeld.Status.VERWORFEN)
    # ohne Kaskade auf ki_kikorrektur: Dort darf der KI-Dienst nur anfügen (ki/dbrolle.py), und diese Felder haben
    # ohnehin keine Korrektur (kommt gleichzeitig eine hinzu, scheitert der Fremdschlüssel statt sie zu löschen)
    weg = KiFeld.objects.filter(pk__in=list(offen.filter(korrekturen__isnull=True).values_list("pk", flat=True)))
    weg._raw_delete(weg.db)


def verarbeiten(vorgang: KiVorgang, rahmen: Rahmen, paddle=None) -> KiVorgang:
    """Ganzer Ablauf eines Vorgangs. Wirft ``Abgebrochen`` (Vorgang bleibt fortsetzbar)."""
    einst = KiEinstellung.laden()
    t0 = time.monotonic()
    verfahren = []
    stufe1(vorgang, einst, rahmen, paddle=paddle)
    vorgang.status = S.OCR_FERTIG
    seiten = list(vorgang.seiten_liste.all())
    vorgang.ocr_text = "\n\n".join(s.text for s in seiten)[:500000]
    konf = [s.konfidenz for s in seiten if s.konfidenz is not None]
    vorgang.ocr_konfidenz = round(sum(konf) / len(konf), 3) if konf else None
    vorgang.save(update_fields=["status", "ocr_text", "ocr_konfidenz"])
    verfahren += sorted({v for s in seiten for v in (s.verfahren or [])})

    modell_ergebnis: list[tuple[int, dict]] = []
    hinweis = ""
    if rahmen.client is not None:
        try:
            modell_ergebnis = stufe2(vorgang, einst, rahmen)
            verfahren.append("vision")
        except ModellFehler as e:
            hinweis = f"KI-Stufe nicht verfügbar ({e}) – nur regelbasierte Vorschläge."
            log.warning("%s: %s", vorgang, hinweis)
    else:
        hinweis = "Kein KI-Modell eingerichtet – nur regelbasierte Vorschläge."
    rahmen.pruefe_abbruch()
    rahmen.schritt("Gegenprüfung und Vorschläge", 92)
    regeln = _regeln(vorgang)
    verfahren.append("regeln")
    felder = felder_bilden(vorgang, modell_ergebnis, regeln)
    typ = next((f.wert.get("wert") for f in felder if f.schluessel == "dokumenttyp"), "")
    with transaction.atomic():
        alte_felder_entfernen(vorgang)
        KiFeld.objects.bulk_create(felder)
        nutzbar = any(f.schluessel != "ocr_konfidenz" for f in felder)
        # ohne Modell und ohne verwertbare Vorschläge: liegen lassen, bis das Modell läuft
        vorgang.status = S.NACHVERARBEITUNG if (hinweis and not nutzbar) else S.ZUR_PRUEFUNG
        vorgang.dokumenttyp = typ or ""
        vorgang.typ_konfidenz = next((f.konfidenz for f in felder if f.schluessel == "dokumenttyp"), None)
        vorgang.metadaten = {f.schluessel: f.wert.get("wert") for f in felder if f.gruppe == "meta"}
        if hinweis:
            vorgang.metadaten["hinweis"] = hinweis
        vorgang.verfahren = verfahren
        vorgang.prompt_version = prompts.PROMPT_VERSION if modell_ergebnis else ""
        vorgang.fertig_am = timezone.now()
        vorgang.dauer_s = round((vorgang.dauer_s or 0) + time.monotonic() - t0, 1)
        vorgang.fortschritt, vorgang.schritt, vorgang.fehler = 100, "", ""
        vorgang.save()
        mv = vorgang.modellversion
        protokolliere(SystemEreignis.Art.KI, benutzername="ki-dienst", objekt=str(vorgang), aktion="verarbeitet",
                      vorgang=vorgang.pk, dokument=vorgang.dokument_id, patient_id=vorgang.patient_id,
                      modell=mv.name if mv else "", modell_sha256=mv.sha256 if mv else "",
                      prompt_version=vorgang.prompt_version, verfahren=verfahren, felder=len(felder),
                      dauer_s=vorgang.dauer_s)
    # Verknüpfung Labor ↔ Infusionsplan für diesen Patienten neu berechnen (Hinweise)
    from .verknuepfung import fuer_patient

    fuer_patient(vorgang.patient)
    if vorgang.status == S.ZUR_PRUEFUNG:
        krypto.vorgang_aufraeumen(vorgang.pk)
    return vorgang

