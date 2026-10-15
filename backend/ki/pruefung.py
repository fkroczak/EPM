"""Gegenprüfung der Modell-Ergebnisse mit festen Regeln – bevor ein Mitarbeiter sie sieht.

Das Modell liefert Texte („3,1“, „3,5–5,1“, „12.03.2026“). Hier werden daraus Zahlen, Bereiche und Daten; jeder
Vorschlag bekommt eine Konfidenz und Hinweise, warum er sicher oder unsicher ist:

- Parameter im Laborkatalog gefunden (Synonyme, Suchbegriffe – wie in „Scans“)?
- Einheit bekannt und Wert im plausiblen Messbereich (``scans.ocr.einheiten``)?
- Steht die Zahl auch im Text der klassischen Texterkennung (Beleg)? Fehlt sie dort, obwohl die Seite gut lesbar
  war, ist das ein Warnzeichen (Modell hat sich verlesen oder etwas erfunden).
- Stimmt der Wert mit der regelbasierten Auswertung derselben Seite überein?
- Datum gültig, nicht in der Zukunft?

Keine medizinische Bewertung: „Markierung“ ist nur die Lage zum Referenzbereich, wie sie auch auf dem Befund steht.
"""
import datetime as dt
import re
from decimal import Decimal

from django.utils import timezone

from scans.ocr import auswertung, einheiten

# Substanz im Infusionsplan → Feld des Plans (infusionen.Infusionsplan) und Stoff für die Verknüpfung mit dem Labor
PLANFELDER = {
    "kalium_mmol": ("kalium", ["kalium", "kcl", "kaliumchlorid", "kalinor", "kaliumzusatz", "kaliumsubstitution"]),
    "natrium_mmol": ("natrium", ["natrium", "nacl", "natriumchlorid", "kochsalz"]),
    "phosphat_mmol": ("phosphat", ["phosphat", "glycophos", "glycerophosphat", "natriumglycerophosphat"]),
    "calcium_mmol": ("calcium", ["calcium", "calciumgluconat", "kalzium"]),
    "magnesium_mmol": ("magnesium", ["magnesium", "magnesiumsulfat", "mgso4"]),
    "glucose_g": ("glucose", ["glucose", "glukose", "dextrose"]),
    "aminosaeuren_g": (None, ["aminosaeuren", "aminoven", "aminomix", "aminoplasmal"]),
    "lipide_g": (None, ["lipide", "smoflipid", "omegaven", "intralipid", "lipofundin", "clinoleic"]),
    "albumin_ml": ("albumin", ["albumin", "humanalbumin"]),
}
EINHEIT_PLANFELD = {"kalium_mmol": "mmol", "natrium_mmol": "mmol", "phosphat_mmol": "mmol", "calcium_mmol": "mmol",
                    "magnesium_mmol": "mmol", "glucose_g": "g", "aminosaeuren_g": "g", "lipide_g": "g",
                    "albumin_ml": "ml"}


def planfeld(substanz: str) -> str | None:
    n = auswertung.norm(substanz).replace(" ", "")
    for feld, (_stoff, begriffe) in PLANFELDER.items():
        if any(b in n for b in begriffe):
            return feld
    return None


def dezimal(text) -> Decimal | None:
    if text is None:
        return None
    t = str(text).strip()
    t = re.sub(r"^[<>≤≥~]=?\s*", "", t)
    m = re.match(r"[-+]?\d[\d.,]*", t.replace(" ", ""))
    return einheiten.zahl(m.group(0)) if m else None


def referenz(text) -> tuple[Decimal | None, Decimal | None]:
    """„3,5 - 5,1“ → (3.5, 5.1); „< 5“ → (None, 5); „> 60“ → (60, None)."""
    if not text:
        return None, None
    t = str(text).replace("–", "-").replace("—", "-").replace(" bis ", "-").strip()
    m = re.match(r"^\s*([<≤]|kleiner)\s*=?\s*([\d.,]+)", t)
    if m:
        return None, einheiten.zahl(m.group(2))
    m = re.match(r"^\s*([>≥]|größer|groesser)\s*=?\s*([\d.,]+)", t)
    if m:
        return einheiten.zahl(m.group(2)), None
    m = re.match(r"^\s*([\d.,]+)\s*-\s*([\d.,]+)", t)
    if m:
        return einheiten.zahl(m.group(1)), einheiten.zahl(m.group(2))
    return None, None


def datum(text) -> dt.date | None:
    if not text:
        return None
    t = str(text).strip()
    try:
        d = dt.date.fromisoformat(t[:10])
    except ValueError:
        d = auswertung.datum_aus(t)
    if d is None or d.year < 1900 or d > timezone.localdate():
        return None
    return d


def uhrzeit(text) -> dt.time | None:
    if not text:
        return None
    m = re.search(r"(\d{1,2})[:.h](\d{2})", str(text))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return dt.time(h, mi) if h < 24 and mi < 60 else None


def _ziffern(text: str) -> str:
    return re.sub(r"[^0-9,.\n ]", " ", text or "")


def im_text(wert: str | None, text: str) -> bool:
    """Steht die Zahl (so gelesen) im Text der klassischen Erkennung? Komma und Punkt gelten gleich."""
    if not wert:
        return False
    z = re.sub(r"[^0-9,.]", "", str(wert)).replace(".", ",")
    if not z or z in {",", ""}:
        return False
    vorrat = _ziffern(text).replace(".", ",")
    return re.search(rf"(?<![0-9,]){re.escape(z)}(?![0-9])", vorrat) is not None


def _dez(d: Decimal | None) -> str | None:
    return None if d is None else format(d.normalize(), "f")


def _klemmen(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 3)


class Katalog:
    """Laborkatalog für die Zuordnung (wie in „Scans“, mit gelernten Zuordnungen)."""

    def __init__(self, parameter: list[dict] | None = None, gelernt=None):
        if parameter is None:
            from scans.dienst import katalog

            parameter = katalog()
        self.parameter = {p["id"]: p for p in parameter}
        self.index, self.eintraege = auswertung.katalog_index(parameter)
        self.gelernt = gelernt

    def finden(self, name: str, quelle: str = ""):
        p, art, _t = auswertung._suche_parameter(name, self.index, self.eintraege, self.gelernt, quelle)
        return p, art


def laborwert(roh: dict, katalog: Katalog, *, ocr_text: str, seite: int, seite_konfidenz: float | None,
              regeln: list[dict] | None = None, quelle: str = "") -> dict:
    """Ein Laborwert des Modells → ``{"wert": …, "konfidenz": …, "quelle": …, "belege": …}`` für ``KiFeld``."""
    hinweise = []
    name = str(roh.get("parameter") or "").strip()[:150]
    gelesen = str(roh.get("wert") or "").strip()[:50]
    zahl = dezimal(gelesen)
    wert_text = "" if zahl is not None and re.fullmatch(r"[\d.,\s]+", gelesen) else gelesen
    if wert_text:
        zahl = None
    param, art = katalog.finden(name, quelle) if name else (None, "")
    einheit = einheiten.einheit(roh.get("einheit")) or (str(roh.get("einheit") or "").strip()[:30])
    ref_von, ref_bis = referenz(roh.get("referenz"))
    konf = 0.7
    if param is None:
        hinweise.append("Parameter nicht im Laborkatalog – als Freitext vorgeschlagen")
        konf -= 0.1
    elif art == "aehnlich":
        hinweise.append(f"Parameter nur nach ähnlicher Schreibweise zugeordnet („{name}“ → „{param.name}“)")
        konf -= 0.1
    if zahl is None and not wert_text:
        hinweise.append("kein Wert lesbar")
        konf -= 0.4
    if param is not None and zahl is not None and einheit:
        ok = einheiten.plausibel(param.stoff, zahl, einheit)
        if ok is False:
            hinweise.append(f"Wert {gelesen} {einheit} liegt außerhalb des üblichen Messbereichs – Lesefehler?")
            konf -= 0.35
    belegt = im_text(gelesen, ocr_text)
    if belegt:
        konf += 0.1
    elif seite_konfidenz is not None and seite_konfidenz >= 0.85:
        hinweise.append("Zahl steht nicht im Text der klassischen Erkennung, obwohl die Seite gut lesbar ist")
        konf -= 0.25
    regel = _passende_regel(param.id if param else None, name, regeln or [])
    if regel is not None:
        if regel.get("wert") is not None and zahl is not None and Decimal(regel["wert"]) == zahl:
            konf += 0.15
            quelle_feld = "vision+regeln"
        else:
            hinweise.append(f"die regelbasierte Auswertung las {regel.get('wert') or regel.get('wert_text')!r}")
            konf -= 0.15
            quelle_feld = "vision"
    else:
        quelle_feld = "vision"
    d = datum(roh.get("datum"))
    if roh.get("datum") and d is None:
        hinweise.append(f"Datum „{roh.get('datum')}“ ungültig oder in der Zukunft")
    u = uhrzeit(roh.get("uhrzeit"))
    markierung = _markierung(roh.get("markierung"), zahl, ref_von, ref_bis)
    wert = {
        "parameter": param.id if param else None,
        "parameter_name": param.name if param else None,
        "erkannt_als": name,
        "freitext_name": "" if param else name,
        "wert": _dez(zahl), "wert_text": wert_text,
        "einheit": einheit or (param.einheit if param else ""),
        "referenz_von": _dez(ref_von), "referenz_bis": _dez(ref_bis),
        "datum": d.isoformat() if d else None,
        "uhrzeit": u.strftime("%H:%M") if u else None,
        "markierung": markierung,
    }
    return {"wert": wert, "konfidenz": _klemmen(konf), "quelle": quelle_feld,
            "belege": {"seite": seite, "gelesen": gelesen, "im_ocr_text": belegt, "hinweise": hinweise}}


def _markierung(gedruckt, zahl, ref_von, ref_bis) -> str:
    g = str(gedruckt or "").strip().upper()
    if g in ("H", "+", "↑", "HOCH", "++"):
        return "↑"
    if g in ("L", "-", "↓", "NIEDRIG", "--", "TIEF"):
        return "↓"
    if zahl is not None:
        if ref_bis is not None and zahl > ref_bis:
            return "↑"
        if ref_von is not None and zahl < ref_von:
            return "↓"
    return ""


def _passende_regel(param_id, name, regeln):
    n = auswertung.norm(name)
    for r in regeln:
        if param_id is not None and r.get("parameter") == param_id:
            return r
        if param_id is None and n and auswertung.norm(r.get("erkannt_als") or "") == n:
            return r
    return None


def regelwert(r: dict, seite_konfidenz: float | None) -> dict:
    """Ein Wert der regelbasierten Auswertung (``scans.ocr.auswertung``) als Vorschlag – wenn kein Modell läuft oder
    das Modell den Wert nicht gefunden hat."""
    wert = {k: r.get(k) for k in ("parameter", "parameter_name", "erkannt_als", "freitext_name", "wert", "wert_text",
                                  "einheit", "referenz_von", "referenz_bis")}
    wert.update({"datum": None, "uhrzeit": None, "markierung": r.get("markierung") or ""})
    return {"wert": wert, "konfidenz": _klemmen(float(r.get("sicherheit") or 0.6)), "quelle": "regeln",
            "belege": {"seite": (r.get("seite") or 0) + 1, "zeile": r.get("zeile"), "box": r.get("box"),
                       "im_ocr_text": True, "hinweise": list(r.get("hinweise") or [])}}


def infusion(roh: dict, *, ocr_text: str, seite: int) -> dict:
    hinweise = []
    substanz = str(roh.get("substanz") or "").strip()[:150]
    feld = planfeld(substanz)
    menge = dezimal(roh.get("menge"))
    einheit = str(roh.get("einheit") or "").strip()[:20]
    if not einheit and roh.get("menge"):
        m = re.search(r"[a-zA-Zµ/%]+.*$", str(roh.get("menge")))
        einheit = m.group(0).strip()[:20] if m else ""
    konf = 0.7
    if feld is None:
        hinweise.append("Substanz keinem Feld des Infusionsplans zugeordnet – als Position vorgeschlagen")
        konf -= 0.1
    elif einheit and EINHEIT_PLANFELD[feld] not in einheit.lower():
        hinweise.append(f"Einheit „{einheit}“ passt nicht zum Planfeld ({EINHEIT_PLANFELD[feld]}) – bitte umrechnen")
        konf -= 0.2
    if roh.get("menge") and not im_text(str(roh.get("menge")), ocr_text):
        hinweise.append("Menge steht nicht im Text der klassischen Erkennung")
        konf -= 0.1
    von, bis = datum(roh.get("von")), datum(roh.get("bis"))
    if roh.get("von") and von is None:
        hinweise.append(f"Beginn „{roh.get('von')}“ ungültig")
    if von is None:
        hinweise.append("ohne Beginn – für die Verknüpfung mit Laborwerten nur eingeschränkt nutzbar")
        konf -= 0.1
    u = uhrzeit(roh.get("uhrzeit"))
    wert = {"substanz": substanz, "planfeld": feld, "menge": _dez(menge), "einheit": einheit,
            "von": von.isoformat() if von else None, "bis": bis.isoformat() if bis else None,
            "uhrzeit": u.strftime("%H:%M") if u else None,
            "applikation": str(roh.get("applikation") or "")[:60], "haeufigkeit": str(roh.get("haeufigkeit") or "")[:60],
            "kontext": str(roh.get("kontext") or "")[:300]}
    return {"wert": wert, "konfidenz": _klemmen(konf), "quelle": "vision",
            "belege": {"seite": seite, "hinweise": hinweise}}


def medikament(roh: dict, *, seite: int) -> dict:
    wert = {"wirkstoff": str(roh.get("wirkstoff") or "").strip()[:150],
            "handelsname": str(roh.get("handelsname") or "")[:150], "staerke": str(roh.get("staerke") or "")[:60],
            "dosierung": str(roh.get("dosierung") or "")[:150], "grund": str(roh.get("grund") or "")[:200]}
    s = datum(roh.get("seit"))
    wert["seit"] = s.isoformat() if s else None
    konf = 0.65 if wert["wirkstoff"] else 0.3
    return {"wert": wert, "konfidenz": konf, "quelle": "vision", "belege": {"seite": seite, "hinweise": []}}


ICD = re.compile(r"^[A-Z]\d{2}(\.\d{1,2})?[GVAZRLB]?$")


def diagnose(roh: dict, *, ocr_text: str, seite: int) -> dict:
    hinweise = []
    code = str(roh.get("icd_code") or "").strip().upper().replace(" ", "")[:10]
    konf = 0.65
    if code and not ICD.match(code):
        hinweise.append(f"„{code}“ ist kein gültiger ICD-10-Code")
        code, konf = "", konf - 0.15
    if code and code not in (ocr_text or "").upper().replace(" ", ""):
        hinweise.append("ICD-Code steht nicht im Text der klassischen Erkennung")
        konf -= 0.15
    wert = {"bezeichnung": str(roh.get("bezeichnung") or "").strip()[:300], "icd_code": code}
    return {"wert": wert, "konfidenz": _klemmen(konf), "quelle": "vision", "belege": {"seite": seite,
                                                                                      "hinweise": hinweise}}


def patient_abgleich(gelesen: dict | None, patient) -> dict | None:
    """Passt der im Dokument genannte Patient zur Akte? Nur ein Hinweis – falsch abgelegte Dokumente fallen so auf."""
    if not gelesen or not (gelesen.get("name") or gelesen.get("geburtsdatum")):
        return None
    hinweise, passt = [], True
    name = auswertung.norm(gelesen.get("name") or "")
    if name:
        teile = set(name.split())
        if auswertung.norm(patient.nachname) not in name and not teile & set(auswertung.norm(patient.nachname).split()):
            passt = False
            hinweise.append("Nachname im Dokument passt nicht zur Akte")
    geb = datum(gelesen.get("geburtsdatum"))
    if geb and getattr(patient, "geburtsdatum", None) and geb != patient.geburtsdatum:
        passt = False
        hinweise.append("Geburtsdatum im Dokument passt nicht zur Akte")
    return {"wert": {"name": gelesen.get("name"), "geburtsdatum": geb.isoformat() if geb else None, "passt": passt},
            "konfidenz": 0.9 if passt else 0.3, "quelle": "vision",
            "belege": {"hinweise": hinweise or ["Angaben passen zur Akte"]}}
