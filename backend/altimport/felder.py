"""
Katalog des Altsystems: welche Angaben das Werkzeug je Tabelle erwartet und unter welchen Spaltennamen es sie
sucht (Datenanalyse vom 23.02.2024: MySQL 8, sechs Tabellen, keine Fremdschlüssel).

Die Spaltennamen sind Vorschläge. Was im Dump anders heißt, ordnet die Administration in der Oberfläche zu; die
Zuordnung wird unabhängig vom Dump gespeichert und gilt für den frischen Dump zum Go-live weiter.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Feld:
    name: str
    titel: str
    vorschlag: tuple = ()
    pflicht: bool = False
    hinweis: str = ""


@dataclass(frozen=True)
class Tabelle:
    name: str
    titel: str
    ziel: str
    vorschlag: tuple
    felder: tuple
    # Spalten, die bewusst nicht übernommen werden: {spaltenname klein: Begründung}
    ohne: dict

    def feld(self, name: str) -> Feld:
        return next(f for f in self.felder if f.name == name)


TABELLEN = (
    Tabelle("benutzerdaten", "Benutzer", "Benutzer (Konto oder historischer Benutzer ohne Login)",
            ("benutzerdaten", "benutzer", "users", "user"),
            (Feld("benutzername", "Benutzername", ("benutzername", "username", "user", "login", "name"), pflicht=True),
             Feld("rechte", "Rechte (100 / 1000 / 10000 / 100000)", ("rechte", "recht", "rolle", "level")),
             Feld("vorname", "Vorname", ("vorname",)),
             Feld("nachname", "Nachname", ("nachname", "familienname"))),
            {"id": "technische Nummer des Kontos, wird nicht gebraucht"}),
    Tabelle("versorger", "Versorger", "Versorger und Ansprechpartner",
            ("versorger",),
            (Feld("id", "Nummer des Versorgers", ("versorgerid", "versorger_id", "id"), pflicht=True),
             Feld("firma", "Firma", ("firma", "unternehmen")),
             Feld("name", "Name (Ansprechpartner)", ("name", "ansprechpartner")),
             Feld("email", "E-Mail", ("email", "e-mail", "mail")),
             Feld("tel", "Telefon", ("tel", "telefon", "telefonnummer"))),
            {}),
    Tabelle("patienten", "Patienten", "Patientenakten",
            ("patienten", "patient"),
            (Feld("nummer", "Patientennummer", ("patientenid", "patientid", "patid", "id"), pflicht=True,
                  hinweis="wird als Patientennummer übernommen (Regel 15)"),
             Feld("nachname", "Nachname", ("name", "nachname"), pflicht=True),
             Feld("vorname", "Vorname", ("vorname",), pflicht=True),
             Feld("geschlecht", "Geschlecht", ("geschlecht", "sex")),
             Feld("geburtsdatum", "Geburtsdatum", ("geburtsdatum", "gebdat", "geboren"), pflicht=True),
             Feld("strasse", "Straße", ("adresse", "strasse", "anschrift")),
             Feld("plz", "PLZ", ("plz",)),
             Feld("ort", "Ort", ("stadt", "ort", "wohnort")),
             Feld("email", "E-Mail", ("email", "e-mail", "mail")),
             Feld("telefon", "Telefon", ("telefonnummer", "telefon", "tel")),
             Feld("hausarzt", "Hausarzt (Freitext)", ("barzt", "hausarzt", "arzt")),
             Feld("versorger", "Versorger (Nummer)", ("versorger", "versorgerid", "versorger_id")),
             Feld("diagnose", "Diagnose", ("diagnose",)),
             Feld("therapie", "Therapie", ("therapie",)),
             Feld("kontaktaufnahme", "Überweisung / Kontaktaufnahme durch", ("kontaktaufnahme",)),
             Feld("empfehlung", "Empfehlung", ("empfehlung",)),
             Feld("groesse", "Größe", ("groesse", "größe", "grosse")),
             Feld("katheter", "Katheter", ("katheter",)),
             Feld("nickel", "Nickelallergie", ("nickall", "nickelallergie", "nickel")),
             Feld("bearbeiter", "Zuletzt bearbeitet von", ("edit", "bearbeiter")),
             Feld("geaendert", "Zuletzt geändert am", ("lastchange", "geaendert")),
             Feld("geloescht", "Gelöscht am", ("deleted_at", "geloescht"))),
            {"gewicht": "redundant zur Tabelle der Gewichte (Regel 9)",
             "dokumente": "Pfad zum Ordner; die Dateien kommen aus dem Dokumentenordner (Schritt „Dokumente“)"}),
    Tabelle("gewichte", "Gewichte", "Gewichtsmessungen",
            ("gewichte", "gewicht"),
            (Feld("id", "Nummer der Messung", ("gewichtid", "gewichteid", "id")),
             Feld("patient", "Patientennummer", ("patid", "patientenid", "patientid", "patient"), pflicht=True),
             Feld("gewicht", "Gewicht (kg)", ("gewicht", "kg"), pflicht=True),
             Feld("zeit", "Erfasst am", ("lastchange", "datum", "created"), pflicht=True,
                  hinweis="Näherung für das Messdatum (Regel 2) – fehlt die Spalte, bitte einen frischen Dump ziehen"),
             Feld("bearbeiter", "Erfasst von", ("edit", "bearbeiter", "created_by"))),
            {}),
    Tabelle("kontakte", "Kontakte", "Kontakte",
            ("kontakte", "kontakt"),
            (Feld("id", "Nummer des Kontakts", ("kontaktid", "kontakteid", "id")),
             Feld("patient", "Patientennummer", ("patid", "patientenid", "patientid", "patient"), pflicht=True),
             Feld("text", "Text", ("kontakt", "text", "notiz"), pflicht=True),
             Feld("zeit", "Erfasst am", ("lastchange", "datum", "created"), pflicht=True,
                  hinweis="Zeitpunkt des Kontakts (Regel 2) – fehlt die Spalte, bitte einen frischen Dump ziehen"),
             Feld("bearbeiter", "Erfasst von", ("edit", "bearbeiter", "created_by"))),
            {}),
    Tabelle("infusionen", "Infusionspläne", "Infusionspläne",
            ("infusionen", "infusion", "infusionsplaene"),
            (Feld("id", "Nummer des Plans", ("infusionenid", "infusionid", "infid", "id")),
             Feld("patient", "Patientennummer", ("patid", "patientenid", "patientid", "patient"), pflicht=True),
             Feld("erstellt", "Angelegt am", ("created", "created_at", "erstellt"),
                  hinweis="gilt als „gültig ab“; fehlt der Wert, gilt „zuletzt geändert am“"),
             Feld("ersteller", "Angelegt von", ("created_by", "ersteller")),
             Feld("geaendert", "Zuletzt geändert am", ("lastchange", "geaendert")),
             Feld("bearbeiter", "Zuletzt bearbeitet von", ("edit", "bearbeiter")),
             Feld("kcal", "Energie (kcal)", ("kcal",)),
             Feld("gesamt_ml", "Volumen im Mischbeutel (ml)", ("ml",)),
             Feld("basis_ml", "Basislösung (ml)", ("volml",)),
             Feld("basis", "Basislösung (Präparat)", ("voll",)),
             Feld("glucose_g", "Glucose (g)", ("glucose", "gluco")),
             Feld("glucose", "Glucose (Präparat)", ("glucosel", "glucol")),
             Feld("amino_g", "Aminosäuren (g)", ("amino",)),
             Feld("amino", "Aminosäuren (Präparat)", ("aminol",)),
             Feld("dipeptamin", "Dipeptamin", ("dipeptamin",), hinweis="im Bestand nie genutzt (Regel 13)"),
             Feld("albumin_ml", "Humanalbumin (ml)", ("human",)),
             Feld("albumin", "Humanalbumin (Präparat)", ("humanl",)),
             Feld("lipide_g", "Lipide (g)", ("lipide", "fett")),
             Feld("lipide", "Lipide (Präparat)", ("lipidel", "fettl")),
             Feld("omegaven", "Omegaven", ("omegaven",), hinweis="im Bestand nie genutzt (Regel 13)"),
             Feld("natrium", "Natrium (mmol)", ("natrium", "na")),
             Feld("kalium", "Kalium (mmol)", ("kalium", "k")),
             Feld("phosphat", "Phosphat (mmol)", ("phosphat", "pho", "po4")),
             Feld("calcium", "Calcium (mmol)", ("calcium", "ca")),
             Feld("magnesium", "Magnesium (mmol)", ("magnesium", "mg")),
             Feld("spurenelemente", "Spurenelemente (Präparat)", ("spurenelemente", "spur", "spuren")),
             Feld("vitamine", "Vitamine (Präparate, „A | B“)", ("vitamine", "vita", "vitamin")),
             Feld("medikamente", "Katheterblock / Medikamente", ("medi", "medikamente", "medikament")),
             Feld("laufzeit_h", "Laufzeit (h)", ("lzh", "lz", "laufzeit")),
             Feld("laufrate", "Laufrate (ml/h)", ("lzml",), hinweis="nur 8× gefüllt (Regel 13); steht danach in der Bemerkung"),
             Feld("kommentar", "Kommentar", ("kommentar", "bemerkung")),
             Feld("pantozol", "Protonenpumpenhemmer (0–3)", ("pantozol",)),
             Feld("panzeit", "Zeiten (Bitmaske 4/2/1)", ("panzeit",))),
            {}),
)
JE_NAME = {t.name: t for t in TABELLEN}

# Rechte des Altsystems → Rolle (Datenanalyse: benutzerdaten.Rechte)
RECHTE = {"100": "betrachter", "1000": "mitarbeiter", "10000": "mediziner", "100000": "admin"}
ROLLEN = ("betrachter", "mitarbeiter", "mediziner", "admin")

# Präparat-Freitexte der Infusionen: Feld des Katalogs → (Bezeichnung, Kategorie der Präparate, mehrere mit „|“?)
PRAEPARATFELDER = {
    "basis": ("Basislösung", "basisloesung", False),
    "glucose": ("Glucose", "glucose", False),
    "amino": ("Aminosäuren", "aminosaeuren", False),
    "albumin": ("Humanalbumin", "albumin", False),
    "lipide": ("Lipide", "lipide", False),
    "spurenelemente": ("Spurenelemente", "spurenelemente", True),
    "vitamine": ("Vitamine", "vitamine", True),
    "medikamente": ("Katheterblock / Medikamente", "", True),
}
# Für „Katheterblock / Medikamente“ wählbare Kategorien neuer Präparate
MEDI_KATEGORIEN = ("katheterschutz", "medikament", "elektrolyte", "sonstiges")
KATEGORIEN = {"basisloesung": "Basislösung", "glucose": "Glucose", "aminosaeuren": "Aminosäuren", "lipide": "Lipide",
              "albumin": "Albumin", "elektrolyte": "Elektrolyte", "vitamine": "Vitamine",
              "spurenelemente": "Spurenelemente", "katheterschutz": "Katheterschutz", "medikament": "Medikament",
              "sonstiges": "Sonstiges"}

# Längen der Zielfelder (Zeichen), damit nichts stillschweigend abgeschnitten wird
LAENGEN = {"nachname": 100, "vorname": 100, "strasse": 150, "plz": 10, "ort": 100, "telefon": 50, "email": 254,
           "hausarzt": 150, "kontaktaufnahme": 200, "versorger_name": 150, "ansprechpartner_name": 150,
           "auswahlwert": 100, "praeparat_name": 150, "praeparat_konzentration": 60, "benutzername": 150,
           "personenname": 150, "position_bemerkung": 200}

ANLAESSE = {"verstorben": "Verstorben", "therapie_beendet": "Therapie beendet",
            "betreuung_gewechselt": "Betreuung gewechselt"}
