"""
Musterdaten: Auswahllisten, Präparate, Testversorger, Testbenutzer und Testpatienten.

Alles ist wiederholbar (legt nur an, was fehlt). Testpatienten tragen ist_test=True und
Nummern ab 9001, zählen in keiner Statistik und sind für den Testbenutzer die einzigen
sichtbaren Akten. Alle Namen sind frei erfunden. Seit dem Wunsch 11.10.2026 mit Diagnosen, Laborbefunden und
BIA-Messungen (TEST_DIAGNOSEN, TEST_LABOR, TEST_BIA).
"""
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import Rolle, User
from audit.schutz import wartungsmodus
from infusionen.models import Infusionsplan
from stammdaten.models import (Ansprechpartner, Arzt, Auswahlwert, Einstellungen, Laborparameter,
                               Praeparat, Versorger)

from .models import Bezugsperson, Dokument, Erklaerung, Gewichtsmessung, Kontakt, Patient, PatientArzt, Termin

TESTBENUTZER = "test"

# Werte wie im Entwurf „EPM Oberfläche“ (18 · Vorlagen › Auswahllisten, 7 · Neuer Infusionsplan).
# Die Administration pflegt sie danach selbst; gelöscht wird nichts.
AUSWAHLWERTE = {
    Auswahlwert.Liste.KATHETER: ["Port", "Hickman", "Broviac", "PICC", "Port 1-Kammer", "Port 2-Kammer"],
    # „Einwilligung/Datenschutz“: unterschriebene Erklärungen; „Freigabe“: Nachweis der Freigabe eines Plans (E-Mail)
    # „Bericht“ und „Sprechstunde“: von EPM erzeugte PDFs (F115, F116); „BIA“: Geräteprotokoll der Messung
    Auswahlwert.Liste.DOKUMENTTYP: ["Arztbrief", "Labor", "BIA", "Infusionsplan", "Bild", "Patientendatenblatt",
                                    "Bericht", "Sprechstunde", "Schreiben", "Sonstiges", "Einwilligung/Datenschutz", "Freigabe"],
    Auswahlwert.Liste.TERMINORT: ["Praxis Dr. Holtmeier", "Telefon/Video"],
    # Festlegung 01.10.2026: Beziehung der Bezugsperson, unter Vorlagen › Auswahllisten erweiterbar
    Auswahlwert.Liste.BEZIEHUNG: ["Mutter", "Vater", "Ehepartner/in", "Kind", "Betreuer/in (gesetzlich)",
                                  "Pflegedienst", "Sonstige"],
    # Kontaktarten bleiben wie bisher angelegt – die Liste im Entwurf ist noch offen (U6).
    Auswahlwert.Liste.KONTAKTART: ["Telefon (Anruf erhalten)", "Telefon (angerufen)", "Persönlich", "E-Mail",
                                  "Brief/Fax", "Versorger", "Sonstiges"],
    # Berichte aus der Akte (Wunsch 06.10.2026, F115; Liste unter Vorlagen › Auswahllisten änderbar – U59)
    Auswahlwert.Liste.BERICHTART: ["Arztbrief", "Verlaufsbericht", "Stellungnahme", "Sonstiges"],
}

K = Praeparat.Kategorie
PRAEPARATE = [
    # Zusatzvolumen nach der Mail vom 06.10.2026 (F111)
    (K.BASISLOESUNG, "Sterofundin ISO", ""), (K.BASISLOESUNG, "NaCl", "0,9 %"),
    (K.BASISLOESUNG, "Ringer-Lösung", ""), (K.BASISLOESUNG, "Ringer-Lactat", ""),
    (K.BASISLOESUNG, "Jonosteril", ""),
    (K.GLUCOSE, "Glucose", "70 %"),
    (K.AMINOSAEUREN, "Glamin", "13,4 %"), (K.AMINOSAEUREN, "Nephrotect", "10,0 %"),
    (K.AMINOSAEUREN, "Aminoplasmal", "10 %"), (K.AMINOSAEUREN, "Aminosteril 8 % Hepa", "8,0 %"),
    (K.AMINOSAEUREN, "Aminoplasmal E 15 % kohlenhydratfrei", "15,0 %"), (K.AMINOSAEUREN, "Nephrosteril", "7,0 %"),
    (K.AMINOSAEUREN, "Aminoplasmal Hepa", "10,0 %"), (K.AMINOSAEUREN, "Aminomel Nephro", ""),
    (K.LIPIDE, "Clinoleic", "20 %"), (K.LIPIDE, "Lipovenös MCT", "20 %"), (K.LIPIDE, "Lipofundin MCT", "20 %"),
    (K.LIPIDE, "SMOF-Lipid", ""), (K.LIPIDE, "Lipidem", ""), (K.LIPIDE, "Lipovenös", "20 %"),
    (K.LIPIDE, "Lipovenös MCT", "10 %"),
    (K.ALBUMIN, "Humanalbumin", "20 %"),
    (K.SPURENELEMENTE, "Addel N", ""), (K.SPURENELEMENTE, "Tracitrans plus", ""),
    (K.SPURENELEMENTE, "Addel Trace", ""),
    (K.VITAMINE, "Soluvit N", ""), (K.VITAMINE, "Vitalipid adult", ""), (K.VITAMINE, "Frekavit fettlöslich", ""),
    (K.VITAMINE, "Frekavit wasserlöslich", ""), (K.VITAMINE, "Cernevit", ""),
    (K.VITAMINE, "Natrovit", "", "baugleich zu Cernevit, günstiger (Regressgefahr)"),
    (K.KATHETERSCHUTZ, "Taurolin", "2 %"), (K.KATHETERSCHUTZ, "Taurolidin Nova", "2,0 %"),
    (K.KATHETERSCHUTZ, "NutriLock", "2 %", "reines Taurolidin 2 %"),
    (K.KATHETERSCHUTZ, "TauroLock", "", "Taurolidin mit Citrat"),
    # Bisherige Einträge ohne Gegenstück im Entwurf bleiben im Katalog (Elektrolytzusätze, Medikamente).
    (K.ELEKTROLYTE, "Kaliumchlorid", "7,45 %"), (K.ELEKTROLYTE, "Natriumhydrogencarbonat", "8,4 %"),
    (K.ELEKTROLYTE, "Magnesiumsulfat", "10 %"), (K.ELEKTROLYTE, "Calciumgluconat", "10 %"),
    (K.MEDIKAMENT, "Pantozol i.v.", "40 mg"),
    # Dipeptamin und Omegaven entfallen (Wunsch 06.10.2026, F111): Die Migration blendet vorhandene Einträge
    # aus; neu angelegt werden sie nicht mehr.
]


# Laborparameter nach der Mail von Alice vom 06.10.2026 (F112). Reihenfolge und Gruppen wie dort; die Einheiten
# sind ein Vorschlag und je Wert überschreibbar (U45). Referenzbereiche bleiben leer, bis sie geklärt sind (U44).
G = Laborparameter.Gruppe
LABORPARAMETER = [
    (G.TRANSAMINASEN, "GPT (ALT)", "U/l", "GPT"), (G.TRANSAMINASEN, "GOT (AST)", "U/l", "GOT"),
    (G.TRANSAMINASEN, "Gamma-GT", "U/l", "γ-GT"), (G.TRANSAMINASEN, "ALKP", "U/l", "AP"),
    (G.TRANSAMINASEN, "Bilirubin gesamt", "mg/dl", "Bili ges."),
    (G.TRANSAMINASEN, "Bilirubin indirekt", "mg/dl", "Bili ind."),
    (G.TRANSAMINASEN, "Bilirubin direkt", "mg/dl", "Bili dir."),
    (G.NIERE, "Kreatinin", "mg/dl", "Krea"), (G.NIERE, "GFR (CKD-EPI)", "ml/min/1,73 m²", "GFR CKD-EPI"),
    (G.NIERE, "GFR", "ml/min", "GFR"), (G.NIERE, "Harnstoff", "mg/dl", ""),
    (G.NIERE, "Harnsäure", "mg/dl", ""), (G.NIERE, "Cystatin-C", "mg/l", ""),
    (G.EISEN, "Eisen", "µg/dl", ""), (G.EISEN, "Ferritin", "µg/l", ""),
    (G.EISEN, "Transferrin", "mg/dl", ""), (G.EISEN, "Transferrinsättigung", "%", "TfS"),
    (G.EIWEISS_FETT, "Triglyceride", "mg/dl", "TG"), (G.EIWEISS_FETT, "Albumin", "g/l", ""),
    (G.EIWEISS_FETT, "Gesamteiweiß", "g/l", "GE"), (G.EIWEISS_FETT, "CRP", "mg/l", ""),
    (G.ELEKTROLYTE, "Natrium", "mmol/l", "Na"), (G.ELEKTROLYTE, "Kalium", "mmol/l", "K"),
    (G.ELEKTROLYTE, "Calcium", "mmol/l", "Ca"), (G.ELEKTROLYTE, "Magnesium", "mmol/l", "Mg"),
    (G.ELEKTROLYTE, "Phosphat", "mmol/l", "PO4"), (G.ELEKTROLYTE, "Chlorid", "mmol/l", "Cl"),
    (G.SPURENELEMENTE, "Kupfer", "µg/l", "Cu"), (G.SPURENELEMENTE, "Zink", "µg/l", "Zn"),
    (G.SPURENELEMENTE, "Selen", "µg/l", "Se"), (G.SPURENELEMENTE, "Mangan", "µg/l", "Mn"),
    (G.HAEMATOLOGIE, "Leukozyten", "/nl", "Leuko"), (G.HAEMATOLOGIE, "Erythrozyten", "/pl", "Ery"),
    (G.HAEMATOLOGIE, "Hämoglobin", "g/dl", "Hb"), (G.HAEMATOLOGIE, "Hämatokrit", "%", "Hkt"),
    (G.HAEMATOLOGIE, "MCV", "fl", ""), (G.HAEMATOLOGIE, "MCHC", "g/dl", ""), (G.HAEMATOLOGIE, "MCH", "pg", ""),
    (G.HAEMATOLOGIE, "Thrombozyten", "/nl", "Thrombo"), (G.HAEMATOLOGIE, "Lymphozyten", "%", "Lympho"),
    # „Vitamin B1, B2, B6, B12, Folsäure“ und „Vitamin D, D3, Calcidiol, Calcitriol“ je als eigener Parameter (U46)
    (G.VITAMINE, "Vitamin A", "µg/l", ""), (G.VITAMINE, "Vitamin B1", "µg/l", ""),
    (G.VITAMINE, "Vitamin B2", "µg/l", ""), (G.VITAMINE, "Vitamin B6", "µg/l", ""),
    (G.VITAMINE, "Vitamin B12", "ng/l", ""), (G.VITAMINE, "Folsäure", "µg/l", ""),
    (G.VITAMINE, "Vitamin K1", "µg/l", ""), (G.VITAMINE, "Vitamin K2", "µg/l", ""),
    (G.VITAMINE, "Vitamin E", "mg/l", ""), (G.VITAMINE, "Vitamin D", "µg/l", ""),
    (G.VITAMINE, "Vitamin D3", "µg/l", ""),
    (G.VITAMINE, "Calcidiol (25-Hydroxy-Vitamin D)", "ng/ml", "25-OH-D"),
    (G.VITAMINE, "Calcitriol (1,25-Dihydroxy-Vitamin D)", "pg/ml", "1,25-OH₂-D"),
    (G.KNOCHEN, "Parathormon", "pg/ml", "PTH"),
    (G.PANKREAS, "Amylase", "U/l", ""), (G.PANKREAS, "Lipase", "U/l", ""),
    (G.DIABETES, "C-Peptid", "ng/ml", ""), (G.DIABETES, "HbA1c", "%", ""),
    (G.DIABETES, "Glucose", "mg/dl", "Glu"), (G.DIABETES, "Insulin", "mU/l", ""),
    (G.SCHILDDRUESE, "TSH (basal)", "mU/l", "TSH"), (G.SCHILDDRUESE, "fT3", "pg/ml", ""),
    (G.SCHILDDRUESE, "fT4", "ng/dl", ""),
]


def stammdaten_anlegen() -> dict:
    neu = {"auswahlwerte": 0, "praeparate": 0}
    for liste, werte in AUSWAHLWERTE.items():
        for i, wert in enumerate(werte):
            _, angelegt = Auswahlwert.objects.get_or_create(liste=liste, wert=wert, defaults={"reihenfolge": (i + 1) * 10})
            neu["auswahlwerte"] += angelegt
    for eintrag in PRAEPARATE:
        kategorie, name, konz = eintrag[0], eintrag[1], eintrag[2]
        hinweis = eintrag[3] if len(eintrag) > 3 else ""
        _, angelegt = Praeparat.objects.get_or_create(
            kategorie=kategorie, name=name, konzentration=konz,
            defaults={"einheit": "mg" if konz.endswith("mg") else "ml", "hinweis": hinweis},
        )
        neu["praeparate"] += angelegt
    neu["laborparameter"] = 0
    for i, (gruppe, name, einheit, kurz) in enumerate(LABORPARAMETER):
        _, angelegt = Laborparameter.objects.get_or_create(
            gruppe=gruppe, name=name,
            defaults={"einheit": einheit, "kurzname": kurz, "reihenfolge": (i + 1) * 10},
        )
        neu["laborparameter"] += angelegt
    Einstellungen.aktuell()
    return neu


def testbenutzer_anlegen():
    """Legt den Testbenutzer an (Rolle Mitarbeiter – Festlegung 03.10.2026, U7; unter Benutzer auf Betrachter,
    Mitarbeiter (erweitert) oder Mediziner umstellbar). Gibt das Einmal-Passwort zurück, falls neu."""
    user, angelegt = User.objects.get_or_create(
        username=TESTBENUTZER,
        defaults={"first_name": "Tessa", "last_name": "Test", "titel": "", "kuerzel": "TT",
                  "funktion": "Testzugang für Schulung und Prüfung nach Updates",
                  "rolle": Rolle.MITARBEITER, "ist_test": True},
    )
    if not angelegt:
        return user, None
    kennwort = user.neues_einmal_kennwort()
    user.save()
    return user, kennwort


def _testversorger():
    v1, _ = Versorger.objects.get_or_create(
        name="Testversorger Nord (fiktiv)",
        defaults={"strasse": "Musterweg 1", "plz": "48143", "ort": "Münster", "telefon": "0251 000000"},
    )
    v2, _ = Versorger.objects.get_or_create(
        name="Testversorger Süd (fiktiv)",
        defaults={"strasse": "Beispielstraße 5", "plz": "44135", "ort": "Dortmund", "telefon": "0231 000000"},
    )
    a = {}
    for v, name in [(v1, "Frau Beispiel"), (v1, "Herr Muster"), (v2, "Frau Probe")]:
        a[name], _ = Ansprechpartner.objects.get_or_create(versorger=v, name=name, defaults={"telefon": "0000 0000"})
    return v1, v2, a


def _testaerzte():
    """Fiktive Ärzte für die Musterdaten (gemeinsame Ärzteliste)."""
    hausarzt, _ = Arzt.objects.get_or_create(
        name="Dr. med. Anna Hausmann (fiktiv)",
        defaults={"praxis": "Hausarztpraxis Test", "fachrichtung": "Allgemeinmedizin", "strasse": "Testweg 3",
                  "plz": "48341", "ort": "Altenberge", "telefon": "0000 111111", "fax": "0000 111112"},
    )
    facharzt, _ = Arzt.objects.get_or_create(
        name="Dr. med. Bernd Beispiel (fiktiv)",
        defaults={"praxis": "Gastroenterologie Test", "fachrichtung": "Gastroenterologie", "plz": "48143",
                  "ort": "Münster", "telefon": "0000 222222", "email": "praxis@example.org"},
    )
    return hausarzt, facharzt


# Erklärungen zum Datenschutz je Testpatient: (Art, Tage seit Erteilung, Tage seit Widerruf oder None).
# Die übrigen Testpatienten haben keine – so zeigt die Startseite „Erklärungen fehlen“.
TEST_ERKLAERUNGEN = {
    0: [("datenschutzinformation", 400, None), ("einwilligung", 400, None), ("schweigepflichtentbindung", 400, None)],
    1: [("datenschutzinformation", 300, None), ("einwilligung", 300, None), ("schweigepflichtentbindung", 300, 20)],
}

# Bezugspersonen je Testpatient: (Beziehung, Name, Telefon, Auskunft erlaubt)
TEST_BEZUGSPERSONEN = {
    0: [("Ehepartner/in", "Hans Musterfrau (fiktiv)", "0000 333333", True)],
    1: [("Betreuer/in (gesetzlich)", "Betreuungsbüro Test (fiktiv)", "0000 444444", True),
        ("Kind", "Lena Mustermann (fiktiv)", "0000 555555", False)],
    2: [("Mutter", "Maria Beispiel (fiktiv)", "0000 666666", True)],
}

TESTPATIENTEN = [
    # nachname, vorname, geburtsdatum, geschlecht, groesse, versorger-idx, ansprechpartner, katheter, nickel, profil
    ("Musterfrau", "Erika", date(1961, 3, 14), "w", Decimal("166"), 0, "Frau Beispiel", "Port", "nein", "stabil"),
    ("Mustermann", "Max", date(1954, 11, 2), "m", Decimal("181"), 0, "Herr Muster", "Hickman", "unbekannt", "abnahme"),
    ("Beispiel", "Paula", date(1988, 7, 21), "w", Decimal("159"), 1, "Frau Probe", "Broviac", "ja", "zunahme"),
    ("Probe", "Jonas", date(1975, 1, 30), "m", Decimal("176"), 1, "Frau Probe", "PICC", "unbekannt", "stabil"),
    ("Test", "Hanna", date(1949, 9, 9), "w", Decimal("162"), 0, "Frau Beispiel", "Port", "nein", "neu"),
    ("Demo", "Karl", date(1958, 5, 17), "m", Decimal("172"), 1, "Frau Probe", "Port", "nein", "abgeschlossen"),
]

# Zwei Firmen (11.10.2026): Max Mustermann wird von DSKM und Regeneration Clinic betreut (mit Einwilligung),
# Hanna Test nur von der Regeneration Clinic; alle anderen nur von der DSKM.
TEST_FIRMEN = {1: ("dskm", "rg"), 4: ("rg",)}

DIAGNOSEN = [
    "<p><strong>Kurzdarmsyndrom</strong> nach ausgedehnter Dünndarmresektion (Testdaten).</p>"
    "<p>Restdünndarmlänge ca. 80 cm, Colon in Kontinuität.</p>",
    "<p>Chronisches Darmversagen bei Morbus Crohn (Testdaten).</p><ul><li>Z. n. mehreren Resektionen</li></ul>",
    "<p>Mangelernährung bei Motilitätsstörung (Testdaten).</p>",
]

# Befunde der Testpatienten (Wunsch 11.10.2026): Diagnosen mit ICD-Code, Laborbefunde und BIA-Messungen, damit Reiter,
# Hinweise („Kein Laborbefund“, „Labor älter als …“, „BIA älter als …“) und der Plan-Editor (Werte außerhalb des
# Referenzbereichs mit Verlauf) ohne Handarbeit zu prüfen sind. Schlüssel = Index in TESTPATIENTEN.
# Diagnosen: (Bezeichnung, ICD-Code, Kennzeichen, besteht seit (Tage), Notiz, beendet vor (Tage) oder None)
TEST_DIAGNOSEN = {
    0: [("Kurzdarmsyndrom", "K91.2", "G", 2600, "Restdünndarm ca. 80 cm, Colon in Kontinuität", None),
        ("Mesenterialinfarkt mit Dünndarmresektion", "K55.0", "Z", 2650, "", None),
        ("Eisenmangelanämie", "D50.9", "G", 400, "", None),
        ("Störung des Magnesiumstoffwechsels", "E83.4", "V", 20, "Kontrolle im nächsten Labor", None)],
    1: [("Crohn-Krankheit des Dünndarmes", "K50.0", "G", 9000, "mehrere Resektionen", None),
        ("Kurzdarmsyndrom", "K91.2", "G", 1800, "", None),
        ("Erhebliche Energie- und Eiweißmangelernährung", "E43", "G", 120, "", None),
        ("Infektion durch Katheter", "T82.7", "G", 260, "Portinfektion, Port belassen", 200)],
    2: [("Chronische intestinale Pseudoobstruktion", "K59.8", "G", 3000, "", None),
        ("Mäßige Energie- und Eiweißmangelernährung", "E44.0", "G", 900, "", None),
        ("Osteoporose", "M81.99", "V", 100, "Knochendichtemessung angefordert", None)],
    3: [("Kurzdarmsyndrom", "K91.2", "G", 1500, "", None),
        ("Strahlenenteritis", "K52.0", "G", 1600, "nach Bestrahlung im Becken", None),
        ("Hypertriglyzeridämie", "E78.1", "G", 150, "", None),
        ("Chronische Nierenkrankheit, Stadium 3", "N18.3", "V", 60, "", None)],
    4: [("Crohn-Krankheit des Dünndarmes", "K50.0", "G", 9000, "", None),
        ("Mangelernährung", "E46", "V", 30, "Erstvorstellung, Labor und BIA folgen", None)],
    5: [("Motilitätsstörung des Dünndarms", "K59.8", "G", 1400, "", None),
        ("Erhebliche Energie- und Eiweißmangelernährung", "E43", "Z", 1400, "Darmfunktion wieder ausreichend", 30)],
}

# Laborparameter mit üblichem Wert und Referenzbereich, wie ihn das Labor auf dem Befund angibt. Der Katalog selbst
# bleibt ohne Referenzbereich (U44) – die Werte stehen je Zeile wie bei einem abgeschriebenen Befund.
# Name wie im Katalog: (üblicher Wert, Referenz von, Referenz bis, Nachkommastellen)
LABORWERTE = {
    "Natrium": (139, "135", "145", 0), "Kalium": (4.2, "3.5", "5.1", 1), "Calcium": (2.30, "2.15", "2.55", 2),
    "Magnesium": (0.85, "0.66", "1.07", 2), "Phosphat": (1.10, "0.87", "1.45", 2), "Chlorid": (102, "98", "107", 0),
    "Kreatinin": (0.85, "0.5", "1.1", 2), "Harnstoff": (30, "17", "43", 0),
    "GPT (ALT)": (24, "0", "35", 0), "GOT (AST)": (22, "0", "35", 0), "Gamma-GT": (28, "0", "40", 0),
    "ALKP": (80, "35", "105", 0), "Bilirubin gesamt": (0.6, "0.1", "1.2", 1),
    "Albumin": (41, "35", "52", 0), "CRP": (2.0, "0", "5", 1), "Triglyceride": (120, "0", "150", 0),
    "Glucose": (95, "70", "110", 0), "Hämoglobin": (13.4, "12.0", "16.0", 1), "Leukozyten": (6.5, "4.0", "10.0", 1),
    "Thrombozyten": (250, "150", "400", 0),
    # nur im erweiterten Befund (Spurenelemente, Vitamine, Eisen)
    "Ferritin": (90, "30", "300", 0), "Zink": (850, "700", "1200", 0), "Selen": (95, "70", "150", 0),
    "Kupfer": (1000, "700", "1400", 0), "Vitamin B12": (420, "190", "900", 0), "Folsäure": (8.0, "3.0", "17.0", 1),
    "Calcidiol (25-Hydroxy-Vitamin D)": (34, "30", "100", 0),
}
LABOR_ERWEITERT = {"Ferritin", "Zink", "Selen", "Kupfer", "Vitamin B12", "Folsäure", "Calcidiol (25-Hydroxy-Vitamin D)"}

# Laborbefunde je Testpatient: Abnahme vor (Tagen), älteste zuerst; „erweitert“ = Befunde mit Spurenelementen und
# Vitaminen; „abweichend“ = feste Werte je Befund (None = üblicher Wert), bewusst teils außerhalb der Referenz.
# Neuester Befund „vor 0 Tagen“: Hinweise im Plan-Editor zählen ab der Freigabe des letzten Plans (F190), und die
# Pläne der Musterdaten sind heute freigegeben.
# Profil 4 (neu) bleibt ohne Labor und BIA → Hinweise „Kein Laborbefund“ / „Keine BIA-Messung“;
# Profil 2 hat nur alte Befunde → „Labor älter als 12 Mon.“; Profil 3 eine alte BIA → „BIA älter als 12 Mon.“
TEST_LABOR = {
    0: {"tage": [365, 182, 91, 0], "erweitert": {0, 3}, "labor": "Testlabor Münster (fiktiv)",
        "abweichend": {"Magnesium": [0.84, 0.79, 0.71, 0.58], "Ferritin": [45, None, 31, 22]},
        "beurteilung": "<p>Magnesium erniedrigt und fallend, Ferritin erniedrigt – bitte prüfen (Testdaten).</p>"},
    1: {"tage": [120, 60, 0], "erweitert": {2}, "labor": "Testlabor Münster (fiktiv)",
        "abweichend": {"Kalium": [3.9, 3.6, 3.2], "Albumin": [36, 33, 29], "CRP": [4.0, 9.5, 14.2]},
        "freitext": [(2, "Calprotectin im Stuhl", None, "> 500", "µg/g")],
        "beurteilung": "<p>Kalium und Albumin fallend, CRP steigend – Entzündungsaktivität (Testdaten).</p>"},
    2: {"tage": [540, 450], "erweitert": {1}, "labor": "Kliniklabor Test (fiktiv)",
        "abweichend": {"Triglyceride": [165, 210], "Gamma-GT": [45, 68], "Calcidiol (25-Hydroxy-Vitamin D)": [None, 18]},
        "beurteilung": "<p>Triglyceride und γ-GT erhöht, Vitamin-D-Mangel (Testdaten).</p>"},
    3: {"tage": [200, 20], "erweitert": {1}, "labor": "Testlabor Münster (fiktiv)",
        "abweichend": {"Triglyceride": [140, 185], "Kreatinin": [1.0, 1.3]},
        "beurteilung": "<p>Triglyceride und Kreatinin erhöht (Testdaten).</p>"},
    5: {"tage": [400, 120], "erweitert": set(), "labor": "Testlabor Münster (fiktiv)", "abweichend": {},
        "beurteilung": "<p>Unauffällig (Testdaten).</p>"},
}

# BIA-Messungen je Testpatient: (vor Tagen, Anteil BCM, Anteil Fettmasse, ECW %); das Gewicht kommt aus dem
# Gewichtsverlauf. Profil „abnahme“: BCM fällt, ECW steigt.
TEST_BIA = {
    0: [(400, 0.36, 0.28, 46.0), (210, 0.37, 0.27, 45.5), (30, 0.37, 0.27, 45.0)],
    1: [(300, 0.38, 0.22, 44.0), (120, 0.35, 0.20, 47.5), (10, 0.31, 0.18, 51.0)],
    2: [(250, 0.30, 0.20, 50.0), (60, 0.33, 0.23, 47.0)],
    3: [(500, 0.40, 0.22, 44.5)],
    5: [(200, 0.39, 0.24, 44.0)],
}


def _nutzer(user, obj):
    obj._history_user = user  # Bearbeiter in der Historie
    return obj


def _gewichte(patient, user, profil, heute, rnd):
    start = {"stabil": 64.0, "abnahme": 78.0, "zunahme": 48.0, "neu": 58.0, "abgeschlossen": 70.0}[profil]
    monate = 2 if profil == "neu" else 36
    for m in range(monate, -1, -1):
        tag = heute - timedelta(days=30 * m + rnd.randint(0, 9))
        if profil == "abnahme":
            kg = start - (36 - m) * 0.1 - (6.0 if m <= 2 else 0) - (2.0 if m == 0 else 0)
        elif profil == "zunahme":
            kg = start + (36 - m) * 0.25
        else:
            kg = start + rnd.uniform(-1.2, 1.2)
        _nutzer(user, Gewichtsmessung(
            patient=patient, gewicht_kg=Decimal(str(round(kg, 1))), gemessen_am=tag, erfasst_von=user,
            quelle=rnd.choice([Gewichtsmessung.Quelle.TELEFONISCH, Gewichtsmessung.Quelle.VERSORGER,
                               Gewichtsmessung.Quelle.AMBULANZ]),
        )).save()


def _kontakte(patient, user, heute, rnd, art):
    texte = [
        "<p>Patientin/Patient telefonisch erreicht, Befinden stabil. Infusion läuft ohne Probleme.</p>",
        "<p>Versorger meldet Lieferung für nächste Woche bestätigt.</p>",
        "<p>Rückfrage zur Laufzeit der Infusion, <strong>Laufzeit auf 12 h</strong> belassen.</p>",
        "<p>Gewicht telefonisch durchgegeben, Rückruf in 4 Wochen vereinbart.</p>",
    ]
    kontakte = []
    for i in range(rnd.randint(3, 6)):
        zeit = timezone.make_aware(datetime.combine(heute - timedelta(days=20 * i + rnd.randint(0, 5)),
                                                    time(9 + rnd.randint(0, 7), rnd.choice([0, 15, 30, 45]))))
        k = _nutzer(user, Kontakt(patient=patient, zeitpunkt=zeit, art=art, text=rnd.choice(texte), erfasst_von=user))
        k.save()
        kontakte.append(k)
    return kontakte


def _diagnosen(patient, user, heute, eintraege):
    """Diagnosen mit denselben Regeln wie über die API (``full_clean``); neue Kombinationen wandern wie dort in die
    Liste unter Vorlagen › Diagnosen (U53)."""
    from stammdaten.models import Diagnosevorlage

    from .models import Diagnose

    for nr, (bezeichnung, icd, kennzeichen, seit, notiz, beendet) in enumerate(eintraege):
        d = _nutzer(user, Diagnose(
            patient=patient, bezeichnung=bezeichnung, icd_code=icd, kennzeichen=kennzeichen,
            seit=heute - timedelta(days=seit), notiz=notiz, reihenfolge=(nr + 1) * 10, aktiv=beendet is None,
            beendet_am=heute - timedelta(days=beendet) if beendet is not None else None, angelegt_von=user))
        d.full_clean()
        d.save()
        Diagnosevorlage.objects.get_or_create(icd_code=d.icd_code, bezeichnung=d.bezeichnung)


def _laborbefunde(patient, user, heute, rnd, daten):
    """Laborbefunde wie über die Maske: Parameter aus dem Katalog (nur aktive), Einheit aus dem Katalog,
    Referenzbereich je Zeile; Werte ohne feste Abweichung schwanken leicht innerhalb der Referenz."""
    from befunde.models import Laborbefund, Laborwert

    katalog = {p.name: p for p in Laborparameter.objects.filter(aktiv=True, name__in=LABORWERTE)}
    anzahl = len(daten["tage"])
    for nr, tage in enumerate(daten["tage"]):
        neuester = nr == anzahl - 1
        befund = _nutzer(user, Laborbefund(
            patient=patient, abgenommen_am=heute - timedelta(days=tage), labor=daten["labor"],
            beurteilung=daten["beurteilung"] if neuester else "", erfasst_von=user))
        befund.full_clean()
        befund.save()
        zeilen = []
        for name, (ueblich, von, bis, stellen) in LABORWERTE.items():
            fest = daten["abweichend"].get(name, [None] * anzahl)[nr]
            if name not in katalog or (fest is None and name in LABOR_ERWEITERT and nr not in daten["erweitert"]):
                continue
            von, bis = Decimal(von), Decimal(bis)
            if fest is None:
                wert = min(max(Decimal(str(round(ueblich * rnd.uniform(0.94, 1.06), stellen))), von), bis)
            else:
                wert = Decimal(str(fest))
            p = katalog[name]
            zeilen.append(Laborwert(befund=befund, parameter=p, wert=wert, einheit=p.einheit,
                                    referenz_von=von, referenz_bis=bis))
        for befund_nr, name, wert, wert_text, einheit in daten.get("freitext", []):
            if befund_nr == nr:
                zeilen.append(Laborwert(befund=befund, freitext_name=name, wert=wert, wert_text=wert_text,
                                        einheit=einheit))
        for i, zeile in enumerate(zeilen):
            zeile.reihenfolge = i
            zeile.full_clean()
            _nutzer(user, zeile).save()


def _bia_messungen(patient, user, heute, messungen):
    """BIA-Messungen mit dem Gewicht aus dem Gewichtsverlauf (ohne Übernahme in den Verlauf – sonst änderten sich
    Trend und Gewichtshinweise der Musterdaten); Plausibilität wie über die API (``full_clean``)."""
    from befunde.models import BiaMessung

    for tage, bcm, fett, ecw in messungen:
        tag = heute - timedelta(days=tage)
        gewicht = (Gewichtsmessung.objects.filter(patient=patient, gemessen_am__lte=tag)
                   .order_by("-gemessen_am", "-id").values_list("gewicht_kg", flat=True).first()
                   or patient.gewichte.order_by("gemessen_am", "id").values_list("gewicht_kg", flat=True).first())
        if gewicht is None:
            continue
        zehntel = Decimal("0.1")
        fettmasse = (gewicht * Decimal(str(fett))).quantize(zehntel)
        meter = patient.groesse_cm / Decimal(100)
        m = _nutzer(user, BiaMessung(
            patient=patient, gemessen_am=tag, gewicht_kg=gewicht, bcm_kg=(gewicht * Decimal(str(bcm))).quantize(zehntel),
            fettmasse_kg=fettmasse, ecw_prozent=Decimal(str(ecw)),
            koerperwasser_l=((gewicht - fettmasse) * Decimal("0.73")).quantize(zehntel),
            bmi=(gewicht / (meter * meter)).quantize(zehntel),
            beurteilung="<p>BCM vermindert, ECW erhöht – Hinweis auf Mangelernährung (Testdaten).</p>" if ecw >= 50
            else "<p>Körperzusammensetzung stabil (Testdaten).</p>",
            erfasst_von=user))
        m.full_clean()
        m.save()


def _plan(patient, user, p, gueltig_ab, glucose, aa, lipide, freigeben=True):
    """Plan wie im Entwurf 8: Sterofundin, Glucose 70 %, Glamin, Clinoleic, Elektrolyte, Zusätze."""
    plan = Infusionsplan.neuer_entwurf(patient, user)
    plan.gueltig_ab = gueltig_ab
    plan.basis_praeparat = p("basisloesung", "Sterofundin")
    plan.basis_ml = 500
    plan.glucose_praeparat, plan.glucose_g = p("glucose", "Glucose", "70 %"), Decimal(glucose)
    plan.aminosaeuren_praeparat, plan.aminosaeuren_g = p("aminosaeuren", "Glamin"), Decimal(aa)
    plan.lipide_praeparat, plan.lipide_g = p("lipide", "Clinoleic"), Decimal(lipide)
    plan.natrium_mmol, plan.kalium_mmol, plan.phosphat_mmol = Decimal(78), Decimal(40), Decimal(18)
    plan.calcium_mmol, plan.magnesium_mmol = Decimal(7), Decimal(10)
    plan.spurenelemente = p("spurenelemente", "Addel N")
    plan.katheterschutz = p("katheterschutz", "Taurolin")
    plan.laufzeit_h = Decimal("12")
    plan.tage_pro_woche = 5
    plan.pantozol_stufe, plan.pantozol_tage = 1, 5
    plan.bemerkung = "<p>Testplan – keine echte Verordnung.</p>"
    _nutzer(user, plan).save()
    plan.vitamine.set([p("vitamine", "Soluvit N"), p("vitamine", "Vitalipid adult")])
    if freigeben:
        # Musterdaten: ohne Prüfung des Rechts „Pläne freigeben“ – der Testbenutzer ist seit 03.10.2026 (U7) standardmäßig
        # Mitarbeiter; die Freigabe nennt ihn trotzdem (fiktive Testdaten, Wasserzeichen „TESTDATEN“)
        plan._freigabe(mediziner=user, abschliessend=None, weg=Infusionsplan.Freigabeweg.SYSTEM,
                       datum=timezone.localdate(), nachweis=None)
    return plan


@transaction.atomic
def testpatienten_anlegen() -> int:
    if Patient.objects.filter(ist_test=True).exists():
        return 0
    rnd = random.Random(20260930)  # immer dieselben Daten
    heute = timezone.localdate()
    user, _ = testbenutzer_anlegen()
    v1, v2, ansprech = _testversorger()
    hausarzt, facharzt = _testaerzte()
    beziehungen = {a.wert: a for a in Auswahlwert.objects.filter(liste=Auswahlwert.Liste.BEZIEHUNG)}
    katheter = {a.wert: a for a in Auswahlwert.objects.filter(liste=Auswahlwert.Liste.KATHETER)}
    art = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.KONTAKTART).first()
    doktyp = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.DOKUMENTTYP, wert="Arztbrief").first()
    terminort = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.TERMINORT).first()
    sonstiges = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.DOKUMENTTYP, wert="Sonstiges").first()

    def p(kat, name, konz=None):
        qs = Praeparat.objects.filter(kategorie=kat, name=name)
        if konz is not None:
            qs = qs.filter(konzentration=konz)
        return qs.first()

    from epm.firma import setze_aktive_firma, zuruecksetzen
    from stammdaten.models import Firma

    firmen = {f.kuerzel: f for f in Firma.objects.all()}
    # der Testbenutzer arbeitet auch in der Regeneration Clinic, um den Umschalter auszuprobieren
    if "rg" in firmen:
        from accounts.models import Mitgliedschaft

        Mitgliedschaft.objects.get_or_create(benutzer=user, firma=firmen["rg"], defaults={"rolle": Rolle.MITARBEITER})

    def in_firma(i):
        """Einträge in der ersten Firma der Akte erfassen (Akte und Einträge vermerken sie)."""
        return setze_aktive_firma(firmen.get(TEST_FIRMEN.get(i, ("dskm",))[0]))

    angelegt = []
    for i, (nach, vor, geb, geschl, groesse, vi, ap, kath, nickel, profil) in enumerate(TESTPATIENTEN):
        token = in_firma(i)
        pat = _nutzer(user, Patient(
            nachname=nach, vorname=vor, geburtsdatum=geb, geschlecht=geschl, groesse_cm=groesse,
            versorger=(v1, v2)[vi], ansprechpartner=ansprech[ap], katheter=katheter.get(kath), nickelallergie=nickel,
            strasse=f"Teststraße {i + 1}", plz="48341", ort="Altenberge", telefon="0000 000000",
            diagnose=DIAGNOSEN[i % len(DIAGNOSEN)],
            therapie=f"<p><strong>Aktuell:</strong> parenterale Ernährung 7×/Woche über {kath}.</p>"
                     f"<p><strong>Verlauf:</strong></p><ul><li>{(heute - timedelta(days=700)):%d.%m.%Y} Beginn HPE</li>"
                     f"<li>{(heute - timedelta(days=200)):%d.%m.%Y} Umstellung Lipide</li></ul>",
            empfehlung="<p>Gewichtskontrolle alle 4 Wochen (Testdaten).</p>",
            ist_test=True, angelegt_von=user,
        ))
        pat.save()
        _gewichte(pat, user, profil, heute, rnd)
        _nutzer(user, PatientArzt(patient=pat, arzt=hausarzt, rolle=PatientArzt.Rolle.HAUSARZT, angelegt_von=user)).save()
        if i in (0, 1):
            _nutzer(user, PatientArzt(patient=pat, arzt=facharzt, rolle=PatientArzt.Rolle.FACHARZT,
                                      notiz="Kontrolle halbjährlich (Testdaten)", angelegt_von=user)).save()
        for beziehung, bname, tel, auskunft in TEST_BEZUGSPERSONEN.get(i, []):
            _nutzer(user, Bezugsperson(patient=pat, beziehung=beziehungen.get(beziehung), name=bname, telefon=tel,
                                       auskunft_erlaubt=auskunft, angelegt_von=user)).save()
        for e_art, seit, widerruf in TEST_ERKLAERUNGEN.get(i, []):
            _nutzer(user, Erklaerung(
                patient=pat, art=e_art, erteilt_am=heute - timedelta(days=seit), erfasst_von=user,
                notiz="Testdaten", widerrufen_am=heute - timedelta(days=widerruf) if widerruf else None,
                widerruf_notiz="Widerruf telefonisch (Testdaten)" if widerruf else "")).save()
        kontakte = _kontakte(pat, user, heute, rnd, art)

        if profil != "neu":
            _plan(pat, user, p, heute - timedelta(days=500), 150, 60, 30)
            if i != 3:  # Patient 4 behält den alten Plan → Hinweis „älter als 12 Monate“
                _plan(pat, user, p, heute - timedelta(days=90 + 40 * i), 175, 70, 40)
        if profil == "stabil" and i == 0:
            _plan(pat, user, p, heute, 200, 70, 40, freigeben=False)  # offener Entwurf

        # Termine: überfällig, heute, nächste Woche, später
        faellig = [heute - timedelta(days=3), heute, heute + timedelta(days=5), heute + timedelta(days=40)]
        arten = [Termin.Art.RUECKRUF, Termin.Art.WIEDERVORLAGE, Termin.Art.PRAXISTERMIN, Termin.Art.WIEDERVORLAGE]
        _nutzer(user, Termin(
            patient=pat, art=arten[i % 4], faellig_am=faellig[i % 4],
            uhrzeit=time(10, 30) if arten[i % 4] == Termin.Art.PRAXISTERMIN else None,
            ort=terminort if arten[i % 4] == Termin.Art.PRAXISTERMIN else None,
            titel={Termin.Art.RUECKRUF: "Rückruf wegen Gewicht", Termin.Art.WIEDERVORLAGE: "Plan prüfen",
                   Termin.Art.PRAXISTERMIN: "Kontrolltermin"}[arten[i % 4]],
            kontakt=kontakte[0], angelegt_von=user,
        )).save()

        if i == 0:
            _beispieldokument(pat, user, doktyp)
            _beispieldokument(pat, None, sonstiges, altsystem=True)
        if len(TEST_FIRMEN.get(i, ())) > 1:
            from .firmen import firmen_setzen

            firmen_setzen(pat, list(TEST_FIRMEN[i]), user, einwilligung_am=heute - timedelta(days=60))
            # ein Kontakt aus der zweiten Firma: in der gemeinsamen Akte steht an jedem Eintrag, wo er erfasst wurde
            zweite = setze_aktive_firma(firmen[TEST_FIRMEN[i][1]])
            _nutzer(user, Kontakt(patient=pat, art=art, zeitpunkt=timezone.now() - timedelta(days=2),
                                  text="<p>Rückfrage der Regeneration Clinic zur Infusionsdauer (Testdaten).</p>",
                                  erfasst_von=user)).save()
            zuruecksetzen(zweite)
        zuruecksetzen(token)
        angelegt.append((i, pat, profil))

    # Diagnosen, Labor und BIA (Wunsch 11.10.2026) erst nach allen Akten: So bleiben Gewichte, Kontakte und Pläne der
    # bisherigen Musterdaten trotz desselben Zufallsgenerators unverändert.
    for i, pat, profil in angelegt:
        token = in_firma(i)
        _diagnosen(pat, user, heute, TEST_DIAGNOSEN.get(i, []))
        if i in TEST_LABOR:
            _laborbefunde(pat, user, heute, rnd, TEST_LABOR[i])
        _bia_messungen(pat, user, heute, TEST_BIA.get(i, []))
        # abgeschlossen erst danach – eine abgeschlossene Akte nimmt keine Einträge mehr an
        if profil == "abgeschlossen":
            pat.abgeschlossen_am = heute - timedelta(days=30)
            pat.abschluss_anlass = Patient.Abschlussanlass.THERAPIE_BEENDET
            pat.abschluss_notiz = "Darmfunktion ausreichend, HPE beendet (Testdaten)."
            _nutzer(user, pat).save()
        zuruecksetzen(token)
    return len(TESTPATIENTEN)


def _beispieldokument(patient, user, typ, altsystem=False):
    """Ein hochgeladener Beispiel-Arztbrief; mit altsystem=True ein übernommenes Altdokument,
    dessen Typ und Datum noch geprüft werden müssen (Startseite „Nach und nach prüfen“)."""
    import hashlib

    from .models import dokument_pfad

    if altsystem:
        name, titel = "Altdokument-Scan.txt", "Altdokument aus dem bisherigen System"
        text = "Übernommenes Altdokument (TESTDATEN) – Typ und Datum bitte prüfen.\n"
    else:
        name, titel = "Beispiel-Arztbrief.txt", "Beispiel-Arztbrief"
        text = ("Beispiel-Arztbrief (TESTDATEN)\n\nDieser Brief ist frei erfunden und dient nur zum Testen "
                "von Upload, Anzeige und Download im EPM.\n")
    inhalt = text.encode("utf-8")
    relativ = dokument_pfad(patient, name)
    ziel = settings.EPM_DOKUMENTE / relativ
    ziel.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    ziel.write_bytes(inhalt)
    _nutzer(user, Dokument(
        patient=patient, typ=typ, titel=titel,
        datum=timezone.localdate() - timedelta(days=400 if altsystem else 14),
        datei=relativ, originalname=name, mime="text/plain; charset=utf-8",
        groesse=len(inhalt), sha256=hashlib.sha256(inhalt).hexdigest(), hochgeladen_von=user,
        herkunft=Dokument.Herkunft.ALTSYSTEM if altsystem else Dokument.Herkunft.UPLOAD,
        datum_quelle=Dokument.DatumQuelle.DATEIDATUM if altsystem else Dokument.DatumQuelle.EINGABE,
        typ_geprueft=not altsystem,
    )).save()


def testdaten_zuruecksetzen() -> dict:
    """Löscht alle Testpatienten samt Historie und Dateien und legt die Musterdaten neu an."""
    from .datenschutz import akten_entfernen, dateien_entfernen

    with wartungsmodus():
        testpatienten = list(Patient.objects.filter(ist_test=True).values_list("id", "nummer"))
        ids = [i for i, _ in testpatienten]
        # dieselbe Routine wie beim endgültigen Löschen einer Akte (Einträge, Pläne, Dokument-Vorgänge, Historie)
        akten_entfernen(ids)
    for _, nummer in testpatienten:
        dateien_entfernen(nummer)
    angelegt = testpatienten_anlegen()
    return {"geloescht": len(ids), "angelegt": angelegt}
