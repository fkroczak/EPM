"""Vorlagen-Portal in Alltagssprache (F180, Wunsch 10.10.2026: „intuitiver für Praxismanager und Pflegekräfte“).

Je Vorlagenart: wofür sie ist, wo sie in der Praxis benutzt wird und zu welcher Gruppe sie gehört. Je Datenfeld ein
kurzer Name für den Feldeinfüger („Briefanrede“ statt ``{{Patient.Briefanrede}}``) und eine Gruppe (Patient,
Termin, Absender …). Die Datenfelder selbst und ihre Prüfung bleiben in ``felder.py``.
"""
from .felder import ist_eigen

# Gruppen der Liste „Briefe und Formulare“ in der Reihenfolge der Anzeige
GRUPPEN = {
    "schreiben": "Briefe und E-Mails an Patienten",
    "eigen": "Eigene Vorlagen",
    # mitgelieferte Vorlagen der Regeneration Clinic (13.10.2026)
    "anforderungen": "Anforderungen: Labor, Bildgebung, Funktionsdiagnostik",
    "formulare": "Aufklärungen, Erklärungen und Abrechnung",
    "plaene": "Pläne, Berichte und Unterlagen",
    "datenschutz": "Vordrucke zum Datenschutz",
}

SCHREIBEN_WO = "Akte › Weitere Aktionen (⋯) › „Schreiben und E-Mail …“"

ARTEN = {
    "patientenaufnahme": ("schreiben", "Brief bzw. E-Mail an neue Patienten: welche Unterlagen wir vor dem ersten Termin brauchen.",
                          SCHREIBEN_WO),
    "terminbestaetigung": ("schreiben", "Bestätigt einen Sprechstundentermin mit Adresse und dem, was mitzubringen ist.",
                           f"{SCHREIBEN_WO} – dort den Termin wählen"),
    "reisebescheinigung": ("schreiben", "Ärztliche Bescheinigung für Reisen (deutsch und englisch); das ADAC-Attest hängt "
                           "als zweite Seite an.", SCHREIBEN_WO),
    "patientenankuendigung": ("schreiben", "Infoblatt an die Praxis Holtmeier: alle Patienten, die in die Sprechstunde "
                              "kommen – zum Faxen oder per E-Mail.", "Kalender › „Praxis informieren“ (Infoblatt an die Praxis)"),
    "infusionsplan": ("plaene", "Der Infusionsplan als PDF für Patient, Versorger und Pflegedienst.",
                      "Entsteht bei der Freigabe eines Plans; Akte › Infusionspläne › „PDF öffnen“"),
    "patientendatenblatt": ("plaene", "Alle wichtigen Angaben zum Patienten auf einem Blatt: Anschrift, Versorgung, "
                            "Katheter, Therapie, Gewicht.", "Akte › Weitere Aktionen (⋯) › „Akte als PDF“"),
    "sprechstunde": ("plaene", "Der aktuelle Stand für die Sprechstunde: Plan, letztes Labor, BIA und Empfehlung.",
                     "Akte › Weitere Aktionen (⋯) › „Unterlagen für die Sprechstunde“"),
    "medikationsplan": ("plaene", "Der Medikamentenplan des Patienten zum Mitgeben: Dauer- und Bedarfsmedikation mit "
                        "Dosierung morgens, mittags, abends und zur Nacht.",
                        "Akte › Medikamente › „Medikationsplan als PDF“"),
    "bericht": ("plaene", "Aussehen der Berichte, z. B. Fallzusammenfassung oder Arztbrief, als PDF.",
                "Akte › Berichte › „Freigeben“ legt die PDF in der Akte ab"),
    "datenschutzinformation": ("datenschutz", "Information zum Datenschutz zum Aushändigen an den Patienten.",
                               "Akte › Datenschutz › „Vordruck als PDF“"),
    "einwilligung": ("datenschutz", "Einwilligung in die Datenverarbeitung zum Unterschreiben.",
                     "Akte › Datenschutz › „Vordruck als PDF“"),
    "schweigepflichtentbindung": ("datenschutz", "Entbindung von der Schweigepflicht (z. B. gegenüber Hausarzt oder "
                                  "Versorger) zum Unterschreiben.", "Akte › Datenschutz › „Vordruck als PDF“"),
    "firmen": ("datenschutz", "Einwilligung, dass DSKM und Regeneration Clinic die Akte gemeinsam führen, zum "
               "Unterschreiben.", "Akte › Datenschutz › „Vordruck als PDF“"),
}


def art_info(art: str, beschreibung: str = "", gruppe: str | None = None) -> dict:
    """``{"gruppe", "wofuer", "wo"}`` für die Übersicht; eigene Schreiben mit ihrer Beschreibung (F176) und Gruppe."""
    if ist_eigen(art):
        return {"gruppe": gruppe if gruppe in GRUPPEN else "eigen", "wofuer": beschreibung or "Eigenes Schreiben an den Patienten mit E-Mail-Text.",
                "wo": f"{SCHREIBEN_WO} › „{GRUPPEN.get(gruppe) or GRUPPEN['eigen']}“"}
    gruppe, wofuer, wo = ARTEN.get(art, ("plaene", "", ""))
    return {"gruppe": gruppe, "wofuer": wofuer, "wo": wo}


# Gruppe eines Datenfelds nach dem Teil vor dem Punkt; was hier fehlt, steht unter „Weitere Angaben“
FELD_GRUPPEN = {
    "Patient": "Patient", "Termin": "Termin", "Absender": "Absender (Briefkopf)", "Heute": "Datum und Absender",
    "Benutzer": "Datum und Absender", "Versorger": "Versorger", "Ansprechpartner": "Versorger",
    "Plan": "Infusionsplan", "Basis": "Infusionsplan", "Glucose": "Infusionsplan", "Amino": "Infusionsplan",
    "Lipide": "Infusionsplan", "Albumin": "Infusionsplan", "Na": "Infusionsplan", "K": "Infusionsplan",
    "PO4": "Infusionsplan", "Ca": "Infusionsplan", "Mg": "Infusionsplan", "Spurenelemente": "Infusionsplan",
    "Vitamine": "Infusionsplan", "Katheterblock": "Infusionsplan", "Gewicht": "Gewicht", "Bericht": "Bericht",
    "Labor": "Labor und BIA", "BIA": "Labor und BIA", "Bezugspersonen": "Datenschutz", "Aufbewahrung": "Datenschutz",
    "Zeitraum": "Infoblatt an die Praxis", "Terminort": "Infoblatt an die Praxis", "Anzahl": "Infoblatt an die Praxis",
    "Termine": "Infoblatt an die Praxis", "Medikamente": "Medikamente",
}

# Kurze Namen der häufigsten Felder in Alltagssprache; die übrigen nehmen ihre Beschreibung aus ``felder.py``
BEZEICHNUNG = {
    "Patient.Name": "Name (Nachname, Vorname)",
    "Patient.Vorname_Name": "Vorname und Nachname",
    "Patient.Briefanrede": "Briefanrede („Sehr geehrte Frau …“)",
    "Patient.Anrede": "Frau / Herr",
    "Patient.Nummer": "Patientennummer",
    "Patient.Geburtsdatum": "Geburtsdatum",
    "Patient.Alter": "Alter",
    "Patient.Geschlecht": "Geschlecht",
    "Patient.Straße": "Straße",
    "Patient.PLZ_Ort": "PLZ und Ort",
    "Patient.Anschrift": "Anschrift in einer Zeile",
    "Patient.Größe": "Größe",
    "Patient.Diagnose": "Diagnose (Freitext)",
    "Patient.Diagnosen": "Diagnosen mit ICD-Code",
    "Patient.Versicherungsart": "Versicherungsart (GKV/PKV)",
    "Patient.Versicherung": "Krankenversicherung",
    "Patient.Krankenkasse": "Krankenkasse",
    "Patient.Versichertennummer": "Versichertennummer",
    "Patient.E-Mail": "E-Mail-Adresse",
    "Patient.Telefon": "Telefonnummer",
    "Patient.Hausarzt": "Hausarzt",
    "Patient.der_Patientin": "„der Patientin“ / „des Patienten“",
    "Patient.die_Patientin": "„die Patientin“ / „der Patient“",
    "Patient.ihre": "„ihre“ / „seine“",
    "Patient.ihrer": "„ihrer“ / „seiner“",
    "Patient.Mrs": "englisch „Mrs.“ / „Mr.“",
    "Patient.her": "englisch „her“ / „his“",
    "Heute": "Heutiges Datum",
    "Benutzer.Name": "Ihr Name (wer das Schreiben erstellt)",
    "Termin.Datum": "Tag des Termins (mit Wochentag)",
    "Termin.Uhrzeit": "Uhrzeit des Termins",
    "Termin.Ort": "Ort des Termins",
    "Termin.bei": "Hinweis zum Termin („bei/Ort“)",
    "Termin.Titel": "Titel des Termins",
    "Absender.Name": "Name der Einrichtung",
    "Absender.Straße": "Straße",
    "Absender.PLZ_Ort": "PLZ und Ort",
    "Absender.Telefon": "Telefon",
    "Absender.Fax": "Fax",
    "Absender.E-Mail": "E-Mail",
    "Absender.Internet": "Internetadresse",
    "Absender.Fußzeile": "Fußzeile",
    "Versorger.Firma": "Versorger",
    "Versorger.Telefon": "Telefon des Versorgers",
    "Ansprechpartner.Name": "Ansprechpartner",
    "Ansprechpartner.Telefon": "Telefon des Ansprechpartners",
}


def feld_info(name: str, beschreibung: str) -> dict:
    """``{"bezeichnung", "gruppe"}`` eines Datenfelds für den Feldeinfüger."""
    bezeichnung = BEZEICHNUNG.get(name)
    if bezeichnung is None:
        bezeichnung = beschreibung if len(beschreibung) <= 48 else beschreibung.split(" (")[0].split(":")[0]
    return {"bezeichnung": bezeichnung, "gruppe": FELD_GRUPPEN.get(name.split(".")[0], "Weitere Angaben")}
