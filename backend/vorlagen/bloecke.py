"""Aufbau einer Dokumentvorlage aus Blöcken: Prüfung und Startvorlagen (Entwurf 18 · Dokumentvorlagen).

Ein Block ist ein JSON-Objekt ``{"id", "typ", "bezeichnung", "optionen", …}``. Platzhalter stehen als
``{{Feldname}}`` im Text und müssen aus der festen Liste der Art stammen (``felder.FELDER``).
In der Fußzeile stehen zusätzlich ``{Seite}`` und ``{Seiten}``.
"""
import re

from .felder import FELDER, TABELLEN

PLATZHALTER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
ID_MUSTER = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

TYPEN = {
    "briefkopf": "Briefkopf",
    "titel": "Titel",
    "text": "Text",
    "datenfelder": "Datenfelder",
    "tabelle": "Tabelle",
    "trennlinie": "Trennlinie",
    "leerraum": "Leerraum",
    "unterschrift": "Unterschrift",
    "seitenumbruch": "Seitenumbruch",
    "fusszeile": "Fußzeile",
}
OPTIONEN = {
    "schrift": {"klein", "normal", "gross"},
    "ausrichtung": {"links", "mitte", "rechts"},
    "fett": bool, "kursiv": bool, "ausblenden_wenn_leer": bool, "nicht_teilen": bool,
    "ueberschrift": bool,  # Bezeichnung als Überschrift über dem Block drucken
}
MAX_BLOECKE = 60
MAX_FELDER = 30
MAX_TEXT = 4000


def platzhalter(text: str) -> list[str]:
    return PLATZHALTER.findall(text or "")


def _text(wert, name, fehler, pflicht=False, laenge=MAX_TEXT):
    if wert is None or wert == "":
        if pflicht:
            fehler.append(f"{name}: bitte ausfüllen.")
        return
    if not isinstance(wert, str):
        fehler.append(f"{name}: Text erwartet.")
    elif len(wert) > laenge:
        fehler.append(f"{name}: höchstens {laenge} Zeichen.")


def _felder_pruefen(art, text, name, fehler):
    erlaubt = FELDER[art]
    for f in platzhalter(text if isinstance(text, str) else ""):
        if f not in erlaubt:
            fehler.append(f"{name}: unbekanntes Datenfeld „{f}“.")


def _eintraege(art, liste, name, fehler):
    if not isinstance(liste, list) or not liste:
        fehler.append(f"{name}: mindestens ein Feld angeben.")
        return
    if len(liste) > MAX_FELDER:
        fehler.append(f"{name}: höchstens {MAX_FELDER} Felder.")
    for i, e in enumerate(liste, 1):
        if not isinstance(e, dict) or set(e) - {"label", "wert"}:
            fehler.append(f"{name}, Feld {i}: nur „label“ und „wert“.")
            continue
        _text(e.get("label"), f"{name}, Feld {i} (Bezeichnung)", fehler, laenge=100)
        _text(e.get("wert"), f"{name}, Feld {i} (Wert)", fehler, pflicht=True, laenge=500)
        _felder_pruefen(art, e.get("wert"), f"{name}, Feld {i}", fehler)


def pruefe_bloecke(art: str, bloecke) -> list[str]:
    """Liefert eine Liste verständlicher Fehlermeldungen (leer = in Ordnung)."""
    if art not in FELDER:
        return ["Unbekannte Vorlagenart."]
    if not isinstance(bloecke, list) or not bloecke:
        return ["Die Vorlage braucht mindestens einen Block."]
    if len(bloecke) > MAX_BLOECKE:
        return [f"Höchstens {MAX_BLOECKE} Blöcke."]
    fehler: list[str] = []
    ids = set()
    zaehler = {"briefkopf": 0, "fusszeile": 0}
    for nr, b in enumerate(bloecke, 1):
        if not isinstance(b, dict):
            fehler.append(f"Block {nr}: ungültig.")
            continue
        typ = b.get("typ")
        name = f"Block {nr} ({b.get('bezeichnung') or TYPEN.get(typ, typ)})"
        if typ not in TYPEN:
            fehler.append(f"{name}: unbekannter Bausteintyp.")
            continue
        if not isinstance(b.get("id"), str) or not ID_MUSTER.match(b["id"]) or b["id"] in ids:
            fehler.append(f"{name}: fehlende oder doppelte Kennung.")
        ids.add(b.get("id"))
        _text(b.get("bezeichnung"), f"{name} (Bezeichnung)", fehler, laenge=80)
        optionen = b.get("optionen", {})
        if not isinstance(optionen, dict):
            fehler.append(f"{name}: Optionen ungültig.")
            optionen = {}
        for k, v in optionen.items():
            regel = OPTIONEN.get(k)
            if regel is None or (regel is bool and not isinstance(v, bool)) or (isinstance(regel, set) and v not in regel):
                fehler.append(f"{name}: Option „{k}“ ungültig.")
        erlaubt = {"id", "typ", "bezeichnung", "optionen"}
        if typ in zaehler:
            zaehler[typ] += 1
        if typ == "titel":
            erlaubt |= {"text", "zusatz_label", "zusatz"}
            _text(b.get("text"), f"{name} (Text)", fehler, pflicht=True, laenge=200)
            _text(b.get("zusatz_label"), f"{name} (Zusatz)", fehler, laenge=80)
            _text(b.get("zusatz"), f"{name} (Zusatz)", fehler, laenge=200)
            for feld in ("text", "zusatz"):
                _felder_pruefen(art, b.get(feld), name, fehler)
        elif typ in ("text", "fusszeile"):
            erlaubt |= {"text"}
            _text(b.get("text"), f"{name} (Text)", fehler, pflicht=True)
            _felder_pruefen(art, b.get("text"), name, fehler)
        elif typ == "datenfelder":
            erlaubt |= {"spalten", "felder"}
            if b.get("spalten", 2) not in (1, 2, 3, 4, 5, 6):
                fehler.append(f"{name}: 1 bis 6 Spalten.")
            _eintraege(art, b.get("felder"), name, fehler)
        elif typ == "unterschrift":
            erlaubt |= {"felder", "linie"}
            if b.get("felder"):
                _eintraege(art, b.get("felder"), name, fehler)
            _text(b.get("linie"), f"{name} (Linie)", fehler, laenge=80)
        elif typ == "tabelle":
            erlaubt |= {"quelle"}
            if b.get("quelle") not in TABELLEN[art]:
                fehler.append(f"{name}: unbekannte Tabelle. Möglich: {', '.join(TABELLEN[art])}.")
        elif typ == "leerraum":
            erlaubt |= {"hoehe_mm"}
            h = b.get("hoehe_mm", 6)
            if not isinstance(h, int) or isinstance(h, bool) or not 1 <= h <= 100:
                fehler.append(f"{name}: Höhe 1 bis 100 mm.")
        unbekannt = set(b) - erlaubt
        if unbekannt:
            fehler.append(f"{name}: unbekannte Angaben {', '.join(sorted(unbekannt))}.")
    for typ, anzahl in zaehler.items():
        if anzahl > 1:
            fehler.append(f"{TYPEN[typ]} darf höchstens einmal vorkommen.")
    return fehler


FUSSZEILE = "{{Absender.Name}} · {{Absender.Fußzeile}} · Seite {Seite}/{Seiten}"

# Startvorlagen: Aufbau wie im Entwurf „EPM Oberfläche“ (Dokumentvorlagen). Ergänzt um Werte, die nach dem Entwurf
# festgelegt wurden (Protonenpumpenhemmer, Tage pro Woche, Bemerkung, weitere Bestandteile).
STARTVORLAGEN = {
    "infusionsplan": [
        {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf"},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Infusionsplan",
         "zusatz_label": "gültig ab", "zusatz": "{{Plan.gültig_ab}}"},
        {"id": "patient", "typ": "datenfelder", "bezeichnung": "Patientendaten", "spalten": 1, "felder": [
            {"label": "Patient", "wert": "{{Patient.Name}}"}, {"label": "Geboren", "wert": "{{Patient.Geburtsdatum}}"},
            {"label": "Gewicht", "wert": "{{Patient.Gewicht}}"}, {"label": "Versorger", "wert": "{{Versorger.Firma}}"}]},
        {"id": "zusammensetzung", "typ": "tabelle", "bezeichnung": "Zusammensetzung", "quelle": "zusammensetzung"},
        {"id": "elektrolyte", "typ": "datenfelder", "bezeichnung": "Elektrolyte", "spalten": 5, "felder": [
            {"label": "Na", "wert": "{{Na}}"}, {"label": "K", "wert": "{{K}}"}, {"label": "Phosphat", "wert": "{{PO4}}"},
            {"label": "Ca", "wert": "{{Ca}}"}, {"label": "Mg", "wert": "{{Mg}}"}]},
        {"id": "zusaetze", "typ": "datenfelder", "bezeichnung": "Zusätze und Laufzeit", "spalten": 1, "felder": [
            {"label": "Spurenelemente", "wert": "{{Spurenelemente}}"}, {"label": "Vitamine", "wert": "{{Vitamine}}"},
            {"label": "Katheterblock", "wert": "{{Katheterblock}}"},
            {"label": "Protonenpumpenhemmer", "wert": "{{Plan.Protonenpumpenhemmer}}"},
            {"label": "Gesamt", "wert": "{{Plan.ml}} · {{Plan.kcal}}"},
            {"label": "Laufzeit", "wert": "{{Plan.Stunden}} · {{Plan.Rate}}"},
            {"label": "Tage pro Woche", "wert": "{{Plan.Tage_pro_Woche}}"}]},
        {"id": "positionen", "typ": "tabelle", "bezeichnung": "Weitere Bestandteile", "quelle": "positionen",
         "optionen": {"ausblenden_wenn_leer": True}},
        {"id": "bemerkung", "typ": "text", "bezeichnung": "Bemerkung", "text": "{{Plan.Bemerkung}}",
         "optionen": {"ausblenden_wenn_leer": True}},
        {"id": "hinweis", "typ": "text", "bezeichnung": "Hinweis an Versorger",
         "text": "Bei Rückfragen erreichen Sie uns werktags von 8 bis 16 Uhr unter {{Absender.Telefon}}. "
                 "Änderungen der Zusammensetzung nur nach Rücksprache.", "optionen": {"schrift": "klein"}},
        {"id": "freigabe", "typ": "unterschrift", "bezeichnung": "Freigabe und Unterschrift", "felder": [
            {"label": "Freigegeben am", "wert": "{{Plan.freigegeben_am}}"},
            {"label": "von", "wert": "{{Plan.freigegeben_von}}"}], "linie": "Unterschrift",
         "optionen": {"nicht_teilen": True}},
        {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", "text": FUSSZEILE},
    ],
    "patientendatenblatt": [
        {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf"},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Patientendatenblatt",
         "zusatz_label": "Stand", "zusatz": "{{Heute}}"},
        {"id": "person", "typ": "datenfelder", "bezeichnung": "Person", "spalten": 1, "felder": [
            {"label": "Name", "wert": "{{Patient.Name}}"}, {"label": "Nr.", "wert": "{{Patient.Nummer}}"},
            {"label": "Geboren", "wert": "{{Patient.Geburtsdatum}}"}, {"label": "Anschrift", "wert": "{{Patient.Anschrift}}"},
            {"label": "Telefon", "wert": "{{Patient.Telefon}}"}]},
        {"id": "betreuung", "typ": "datenfelder", "bezeichnung": "Betreuung", "spalten": 1, "felder": [
            {"label": "Hausarzt", "wert": "{{Patient.Hausarzt}}"},
            {"label": "Versorger", "wert": "{{Versorger.Firma}} · {{Versorger.Telefon}}"},
            {"label": "Katheter", "wert": "{{Patient.Katheter}}"},
            {"label": "Nickelallergie", "wert": "{{Patient.Nickelallergie}}"}]},
        {"id": "gewicht", "typ": "datenfelder", "bezeichnung": "Gewicht", "spalten": 3, "felder": [
            {"label": "Aktuell", "wert": "{{Gewicht.aktuell}}"}, {"label": "BMI", "wert": "{{Gewicht.BMI}}"},
            {"label": "Trend", "wert": "{{Gewicht.Trend}}"}]},
        {"id": "diagnose", "typ": "datenfelder", "bezeichnung": "Diagnose", "spalten": 1, "felder": [
            {"label": "Diagnose", "wert": "{{Patient.Diagnose}}"}]},
        {"id": "therapie", "typ": "datenfelder", "bezeichnung": "Aktuelle Therapie", "spalten": 1, "felder": [
            {"label": "Aktuelle Therapie", "wert": "{{Patient.Therapie}}"},
            {"label": "Plan", "wert": "{{Plan.kcal}} · {{Plan.ml}} · {{Plan.Stunden}}"}]},
        {"id": "termine", "typ": "tabelle", "bezeichnung": "Nächste Termine", "quelle": "termine"},
        {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", "text": FUSSZEILE},
    ],
}
