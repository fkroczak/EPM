"""Anweisungen an das lokale Modell und das JSON-Schema der Extraktion.

Jede Änderung hier ändert die Ergebnisse: dann ``PROMPT_VERSION`` erhöhen. Die Version steht an jedem Rohergebnis
und Vorgang (Audit, Vergleich von Modell- und Prompt-Fassungen im Qualitäts-Dashboard).

Grundsätze in allen Anweisungen: nur wiedergeben, was im Dokument steht; nichts ergänzen oder erfinden; fehlende
Angaben als ``null``; keine Bewertung, keine Diagnose, keine Empfehlung.
"""
PROMPT_VERSION = "2026-11-14.1"  # + Korrekturhinweise (ki/beispiele.py)

DOKUMENTTYPEN = ["labor", "arztbericht", "entlassbericht", "verlauf", "infusionsplan", "medikationsplan",
                 "pflegebericht", "sonstiges"]

GRUNDSATZ = (
    "Du arbeitest in einem medizinischen Dokumentationssystem ausschließlich als Erkennungsdienst. "
    "Gib nur wieder, was tatsächlich im Dokument steht. Ergänze nichts, rate nichts, erfinde keine Werte, Daten oder "
    "Diagnosen. Fehlt eine Angabe oder ist sie unleserlich, setze null. Bewerte nichts medizinisch, stelle keine "
    "Diagnose und gib keine Empfehlung. Ein Mensch prüft jedes Ergebnis."
)

TRANSKRIPTION = GRUNDSATZ + (
    " Aufgabe: Schreibe den gesamten Text der Seite vollständig und wörtlich ab – auch Handschrift, Stempel und "
    "Tabellen. Fasse nicht zusammen und lasse nichts weg. Tabellen: eine Zeile je Tabellenzeile, Spalten durch "
    "Tabulator getrennt. Unleserliche Stellen als [?]. Keine Erklärungen, nur der Text."
)

EXTRAKTION = GRUNDSATZ + (
    " Aufgabe: Lies das Seitenbild und den beigefügten Text der klassischen Texterkennung (er kann Lesefehler "
    "enthalten; maßgeblich ist das Bild) und gib die Angaben als JSON nach dem Schema zurück. "
    "Dokumenttyp: labor (Laborbefund, Laborreihe), arztbericht, entlassbericht, verlauf (Verlaufsdokumentation), "
    "infusionsplan, medikationsplan, pflegebericht oder sonstiges. "
    "Laborwerte: Parametername wie gedruckt, Wert genau wie gedruckt (Komma beibehalten), Einheit, Referenzbereich "
    "wie gedruckt, Datum und Uhrzeit der Entnahme nur, wenn angegeben, Markierung (H, L, +, -, ↑, ↓) nur, wenn gedruckt. "
    "Infusionen: Substanz, Menge mit Einheit, Zeitraum (von/bis), Applikationsart, Häufigkeit, Zusammenhang wie im "
    "Text. Daten immer als JJJJ-MM-TT, Uhrzeiten als HH:MM. "
    "Zusammenfassung: höchstens drei sachliche Sätze darüber, was im Dokument steht – ohne eigene Bewertung."
)

ZUSAMMENFASSUNG = GRUNDSATZ + (
    " Aufgabe: Fasse die folgenden Seitenzusammenfassungen eines Dokuments in höchstens fünf sachlichen Sätzen "
    "zusammen. Nur Inhalte, die dort stehen."
)

BERICHT = GRUNDSATZ + (
    " Aufgabe: Formuliere aus den nummerierten Fakten einen sachlichen Berichtsentwurf auf Deutsch. Verwende "
    "ausschließlich diese Fakten und belege jede Aussage mit der Nummer in eckigen Klammern, z. B. [3]. Keine "
    "Zahl, kein Datum und keine Diagnose, die nicht in den Fakten steht. Keine Empfehlung, keine Bewertung, keine "
    "Prognose. Fehlen Angaben, schreibe „nicht dokumentiert“. Gliedere mit kurzen Absätzen."
)

_TEXT = {"type": ["string", "null"]}
_DATUM = {"type": ["string", "null"], "description": "JJJJ-MM-TT"}

EXTRAKTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["dokumenttyp", "dokumentdatum", "laborwerte", "infusionen", "medikamente", "diagnosen",
                 "zusammenfassung"],
    "properties": {
        "dokumenttyp": {"type": "string", "enum": DOKUMENTTYPEN},
        "dokumentdatum": _DATUM,
        "erstellungsdatum": _DATUM,
        "absender": _TEXT,
        "fall": {"type": ["string", "null"], "description": "Fall-, Aufenthalts- oder Auftragsnummer"},
        "sprache": _TEXT,
        "vertraulich": {"type": ["boolean", "null"]},
        "patient": {
            "type": "object", "additionalProperties": False,
            "properties": {"name": _TEXT, "geburtsdatum": _DATUM},
        },
        "laborwerte": {
            "type": "array", "maxItems": 120,
            "items": {
                "type": "object", "additionalProperties": False, "required": ["parameter", "wert"],
                "properties": {"parameter": {"type": "string"}, "wert": {"type": "string"}, "einheit": _TEXT,
                               "referenz": _TEXT, "datum": _DATUM, "uhrzeit": _TEXT, "markierung": _TEXT},
            },
        },
        "infusionen": {
            "type": "array", "maxItems": 60,
            "items": {
                "type": "object", "additionalProperties": False, "required": ["substanz"],
                "properties": {"substanz": {"type": "string"}, "menge": _TEXT, "einheit": _TEXT, "von": _DATUM,
                               "bis": _DATUM, "uhrzeit": _TEXT, "applikation": _TEXT, "haeufigkeit": _TEXT,
                               "kontext": _TEXT},
            },
        },
        "medikamente": {
            "type": "array", "maxItems": 60,
            "items": {
                "type": "object", "additionalProperties": False, "required": ["wirkstoff"],
                "properties": {"wirkstoff": {"type": "string"}, "handelsname": _TEXT, "staerke": _TEXT,
                               "dosierung": _TEXT, "seit": _DATUM, "grund": _TEXT},
            },
        },
        "diagnosen": {
            "type": "array", "maxItems": 40,
            "items": {"type": "object", "additionalProperties": False, "required": ["bezeichnung"],
                      "properties": {"bezeichnung": {"type": "string"}, "icd_code": _TEXT}},
        },
        "zusammenfassung": {"type": "string"},
        "verlauf": _TEXT,
        "offene_punkte": {"type": "array", "maxItems": 20, "items": {"type": "string"}},
    },
}


def extraktion_text(ocr_text: str, seite: int, seiten: int, hinweise: str = "") -> str:
    """``hinweise``: frühere Korrekturen der Mitarbeiter (``ki.beispiele``) – stehen vor dem Text der Seite."""
    vorne = f"{hinweise}\n\n" if hinweise else ""
    return (f"{vorne}Seite {seite} von {seiten}. Text der klassischen Texterkennung (kann Fehler enthalten):\n"
            f"<<<\n{ocr_text[:12000]}\n>>>")


def bericht_text(art: str, fakten: list[dict]) -> str:
    zeilen = "\n".join(f"[{f['nr']}] {f['text']}" for f in fakten)
    return f"Berichtsart: {art}.\nFakten:\n{zeilen}"
