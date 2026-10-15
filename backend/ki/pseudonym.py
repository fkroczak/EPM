"""Pseudonymisierung für Evaluations- und Trainingsbeispiele (Auftrag 7).

Ersetzt Angaben zur Person durch Platzhalter: Name, Vorname, Geburtsdatum und Nummer der Akte, dazu typische Muster
(Geburtsdatum hinter „geb.“, Telefon, E-Mail, Versichertennummer, IBAN, Straße mit Hausnummer, Postleitzahl mit Ort).

Wichtig: Das ist eine **Heuristik**. Pseudonymisierte Daten bleiben personenbezogen (Art. 4 Nr. 5 DSGVO). Deshalb
gehen Beispiele nur nach Sichtprüfung und ausdrücklicher Freigabe durch eine berechtigte Person ins Training, und
nur, wenn die Rechtsgrundlagen-Prüfung dokumentiert ist (Administration › KI).
"""
import re

MUSTER = [
    (re.compile(r"(?i)\b(geb\.?|geboren(?: am)?|geburtsdatum:?)\s*\d{1,2}\.\d{1,2}\.\d{2,4}"), r"\1 [GEBURTSDATUM]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[E-MAIL]"),
    (re.compile(r"\bDE\d{2}(?:\s?\d{4}){4}\s?\d{2}\b"), "[IBAN]"),
    (re.compile(r"\b[A-Z]\d{9}\b"), "[VERSICHERTENNUMMER]"),
    (re.compile(r"(?<!\d)(?:\+49|0)\s?\d{2,5}[\s/-]?\d{3,}(?:[\s-]?\d+)*"), "[TELEFON]"),
    (re.compile(r"(?i)\b[\wäöüß.-]+(?:straße|str\.|weg|allee|platz|gasse|ring)\s+\d+\s?[a-z]?\b"), "[ANSCHRIFT]"),
    (re.compile(r"\b\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+(?:[\s-][A-ZÄÖÜ][a-zäöüß]+)?\b"), "[PLZ ORT]"),
]


def pseudonymisieren(text: str, patient=None) -> str:
    t = text or ""
    for muster, ersatz in MUSTER:  # zuerst die Muster (sonst zerreißt ein ersetzter Name z. B. die E-Mail-Adresse)
        t = muster.sub(ersatz, t)
    if patient is not None:
        ersatz = []
        for wert, platzhalter in ((getattr(patient, "nachname", ""), "[NACHNAME]"),
                                  (getattr(patient, "vorname", ""), "[VORNAME]")):
            for teil in re.split(r"[\s-]+", wert or ""):
                if len(teil) >= 2:
                    ersatz.append((teil, platzhalter))
        for teil, platzhalter in sorted(ersatz, key=lambda x: -len(x[0])):
            t = re.sub(rf"(?i)\b{re.escape(teil)}\b", platzhalter, t)
        geb = getattr(patient, "geburtsdatum", None)
        if geb:
            for form in (f"{geb:%d.%m.%Y}", f"{geb.day}.{geb.month}.{geb.year}", f"{geb:%d.%m.%y}", geb.isoformat()):
                t = t.replace(form, "[GEBURTSDATUM]")
        nummer = getattr(patient, "nummer", None)
        if nummer:
            t = re.sub(rf"\b{nummer}\b", "[AKTENNUMMER]", t)
    return t
