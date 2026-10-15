"""Doppelungsprüfung beim Anlegen (F15, erweitert 16.10.2026): Namen vergleichbar machen und Treffer bewerten.

Reine Python-Funktionen ohne Django – die Datenbank liefert nur die Kandidaten mit gleichem (oder Tag/Monat
vertauschtem) Geburtsdatum (``PatientViewSet.doppelte``), der Feinvergleich läuft hier. Bei einigen tausend Akten
sind das je Geburtsdatum nur eine Handvoll Zeilen; so braucht es keine Datenbank-Erweiterung (``unaccent`` ist in den
Migrationen nicht eingerichtet).

Regeln, Rang (kleiner = wichtiger) und Grund:

0. gleicher Name und Geburtsdatum (Schreibweise wörtlich gleich, Groß/Klein egal)
1. gleicher Name in anderer Schreibweise (Umlaute/ß, Akzente, Bindestrich/Leerzeichen, Namenszusatz „von“, „van“ …)
2. Vor- und Nachname vertauscht
3. gleicher Name, Tag und Monat des Geburtsdatums vertauscht (z. B. 03.07. statt 07.03.)
4. ähnliche Schreibweise: Tippfehler (Levenshtein-Abstand ≤ 1, ab 8 Zeichen ≤ 2) oder ein Teil eines Doppelnamens
5. Name beginnt mit denselben 3 Buchstaben (bisherige Regel, jetzt auf die vergleichbare Schreibweise angewandt)
6. nur gleiches Geburtsdatum (ohne Namensangabe, wie bisher)
"""
import unicodedata
from datetime import date

# Zeichen, die vor dem Entfernen der Akzente ersetzt werden (sonst würde aus „ä“ nur „a“)
ERSETZEN = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "æ": "ae", "œ": "oe", "ø": "oe", "ł": "l", "đ": "d"}

# Namenszusätze, die am Anfang eines Namens wegfallen dürfen („von Bergen“ = „Bergen“)
ZUSAETZE = {"von", "vom", "van", "de", "der", "den", "zu", "zum", "zur", "und", "di", "da", "du", "del", "della",
            "le", "la", "ten", "ter", "op"}

# Gründe (Text für die Warnkarte)
GRUND = {
    0: "gleicher Name und Geburtsdatum",
    1: "gleicher Name (andere Schreibweise) und Geburtsdatum",
    2: "Vor-/Nachname vertauscht",
    3: "Tag/Monat vertauscht",
    4: "ähnliche Schreibweise",
    5: "gleiches Geburtsdatum, Name beginnt gleich",
    6: "gleiches Geburtsdatum",
}

EINGESCHRAENKT_HINWEIS = "Es gibt eine eingeschränkte Akte mit gleichem Geburtsdatum."


def namensteile(name: str) -> list[str]:
    """„Müller-Lüdenscheidt“ → [„mueller“, „luedenscheidt“]; „von der Heide“ → [„heide“]; „José“ → [„jose“].

    Klein, Umlaute und ß ausgeschrieben, Akzente entfernt, Apostrophe weg („O'Brien“ → „obrien“), alles andere
    (Bindestrich, Leerzeichen, Punkt) trennt. Führende Namenszusätze fallen weg, solange danach noch etwas bleibt."""
    text = (name or "").lower()
    text = "".join(ERSETZEN.get(z, z) for z in text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(z for z in text if not unicodedata.combining(z))
    text = text.replace("'", "").replace("’", "").replace("`", "").replace("´", "")
    teile = "".join(z if z.isalnum() else " " for z in text).split()
    while len(teile) > 1 and teile[0] in ZUSAETZE:
        teile = teile[1:]
    return teile


def normalisiere(name: str) -> str:
    """Vergleichbare Schreibweise eines Namens ohne Trenner: „Müller-Lüdenscheidt“ und „Mueller Luedenscheidt“
    → „muellerluedenscheidt“; „von Bergen“ → „bergen“."""
    return "".join(namensteile(name))


def abstand(a: str, b: str, grenze: int | None = None) -> int:
    """Levenshtein-Abstand (Einfügen, Löschen, Ersetzen je 1). Mit ``grenze`` bricht die Rechnung ab, sobald
    der Abstand sicher größer ist (Ergebnis dann ``grenze + 1``)."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if grenze is not None and len(a) - len(b) > grenze:
        return grenze + 1
    vorher = list(range(len(b) + 1))
    for i, za in enumerate(a, 1):
        jetzt = [i]
        for j, zb in enumerate(b, 1):
            jetzt.append(min(vorher[j] + 1, jetzt[j - 1] + 1, vorher[j - 1] + (za != zb)))
        if grenze is not None and min(jetzt) > grenze:
            return grenze + 1
        vorher = jetzt
    return vorher[-1]


def erlaubter_abstand(a: str, b: str) -> int:
    """Tippfehler-Toleranz: 1, bei Namen ab 8 Zeichen 2; sehr kurze Namen (unter 4 Zeichen) nur exakt."""
    laenge = min(len(a), len(b))
    if laenge < 4:
        return 0
    return 2 if laenge >= 8 else 1


def aehnlich(a: str, b: str) -> bool:
    """Zwei Namen gelten als ähnlich, wenn ihre vergleichbare Schreibweise höchstens einen kleinen Tippfehler
    auseinanderliegt oder ein Namensteil (Doppelname) gleich bzw. fast gleich ist."""
    na, nb = normalisiere(a), normalisiere(b)
    if not na or not nb:
        return False
    if abstand(na, nb, erlaubter_abstand(na, nb)) <= erlaubter_abstand(na, nb):
        return True
    ta, tb = namensteile(a), namensteile(b)
    if len(ta) == 1 and len(tb) == 1:
        return False  # schon oben verglichen
    for x in ta:
        for y in tb:
            if len(x) < 3 or len(y) < 3:
                continue
            if abstand(x, y, erlaubter_abstand(x, y)) <= erlaubter_abstand(x, y):
                return True
    return False


def tag_monat_getauscht(geb: date) -> date | None:
    """03.07.1960 → 07.03.1960; None, wenn Tag = Monat oder der Tag kein Monat sein kann (> 12)."""
    if geb.day == geb.month or geb.day > 12:
        return None
    try:
        return geb.replace(day=geb.month, month=geb.day)
    except ValueError:  # pragma: no cover – Tag ≤ 12 ist in jedem Monat gültig
        return None


def bewerte(nachname: str, vorname: str, geb: date, k_nachname: str, k_vorname: str, k_geb: date) -> int | None:
    """Rang eines Kandidaten (siehe Modulbeschreibung) oder None, wenn er nicht gemeldet wird.

    ``nachname``/``vorname``/``geb``: Eingabe im Formular; ``k_…``: vorhandene Akte."""
    nach, vor = normalisiere(nachname), normalisiere(vorname)
    k_nach, k_vor = normalisiere(k_nachname), normalisiere(k_vorname)
    gleiches_datum = k_geb == geb
    if not gleiches_datum:
        # nur Tag/Monat vertauscht – dann muss der vollständige Name (vergleichbar) gleich sein
        if nach and vor and k_geb == tag_monat_getauscht(geb) and (nach, vor) == (k_nach, k_vor):
            return 3
        return None
    if not nach and not vor:
        return 6  # wie bisher: ohne Namen alle mit gleichem Geburtsdatum
    if nach and vor:
        if (nachname.strip().lower(), vorname.strip().lower()) == (k_nachname.strip().lower(), k_vorname.strip().lower()):
            return 0
        if (nach, vor) == (k_nach, k_vor):
            return 1
        if (nach, vor) == (k_vor, k_nach):
            return 2
    if (nach and aehnlich(nachname, k_nachname)) or (vor and aehnlich(vorname, k_vorname)):
        return 4
    if nach and vor and (aehnlich(nachname, k_vorname) and aehnlich(vorname, k_nachname)):
        return 2  # vertauscht und dazu ein kleiner Tippfehler
    # bisherige Regel: Nach- oder Vorname beginnt mit denselben 3 Buchstaben
    if (nach and k_nach.startswith(nach[:3])) or (vor and k_vor.startswith(vor[:3])):
        return 5
    # bisherige Regel wörtlich (falls die Normalisierung einen Anfang verschiebt, z. B. „von …“)
    if (nachname.strip() and k_nachname.lower().startswith(nachname.strip()[:3].lower())) or \
            (vorname.strip() and k_vorname.lower().startswith(vorname.strip()[:3].lower())):
        return 5
    return None
