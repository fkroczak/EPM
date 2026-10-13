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
    "plaene": "Pläne, Berichte und Unterlagen",
    "datenschutz": "Vordrucke zum Datenschutz",
    # Word-Vorlagen 01–12 der Regeneration Clinic SIA (Revision 3, Oktober 2026), nur in der Firma RGC
    "rgc": "Regeneration Clinic – Patientenerklärungen und Vereinbarungen",
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
    "rgc_erklaerung_at": ("rgc", "Vorlage 01: Patientenerklärung bei Aufnahme für österreichisch Versicherte (ÖGK, SVS, "
                          "BVAEB, KFA) – Stundung des Kassenanteils, Inkassozession, Zahlungsanweisung, Vollmachten.",
                          "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_erklaerung_gkv": ("rgc", "Vorlage 02: Patientenerklärung bei Aufnahme für gesetzlich Versicherte in Deutschland "
                           "(GKV) – Stundung des Erstattungsanteils, Abtretung, Vollmachten.",
                           "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_erklaerung_bguv": ("rgc", "Vorlage 03: Patientenerklärung bei Aufnahme nach Arbeitsunfall oder Berufskrankheit "
                            "(BG/UV, Deutschland) – Kostenübernahme, Abtretung, Vollmachten.",
                            "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_erklaerung_pkv": ("rgc", "Vorlage 04: Patientenerklärung bei Aufnahme für privat Versicherte in Deutschland "
                           "(PKV) – Stundung, Abtretung, Vollmachten.",
                           "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_erklaerung_zusatz": ("rgc", "Vorlage 05: Patientenerklärung bei stationärer Zusatzversicherung (Deutschland) – "
                              "Tagegeld, Abtretung, Vollmachten.",
                              "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_schweigepflicht": ("rgc", "Vorlage 06: Entbindung von der ärztlichen Schweigepflicht mit ankreuzbaren "
                            "Empfängergruppen, Kommunikationswegen und Verfahrensvollmacht (Anlage zu 01–05, 09, 10).",
                            "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_aufklaerung_op": ("rgc", "Vorlage 07: Aufklärung und Einwilligung zur Operation, deutsch und lettisch – "
                           "Grundbogen, nur gültig mit eingriffsspezifischer Ergänzung.",
                           "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_aufklaerung_anaesthesie": ("rgc", "Vorlage 08: Aufklärung und Einwilligung zur Anästhesie, deutsch und "
                                    "lettisch, mit präanästhesiologischem Befundblock.",
                                    "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_vereinbarung_oegk": ("rgc", "Vorlage 09: Vergütungs- und Rückerstattungsvereinbarung für Selbstzahler mit "
                              "österreichischem Versicherungsträger (ÖGK).",
                              "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_abtretung_oegk": ("rgc", "Vorlage 10: Abtretungs- und Bevollmächtigungserklärung ÖGK mit Vorauszahlung des "
                           "Eigenanteils.", "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_anlage_k": ("rgc", "Vorlage 11: Anlage K – Kostenvoranschlag, Erstattungsprognose (Tabelle A–F), "
                     "Abrechnungsmatrix, Vorprüfung und Patienteninformation; Beträge von Hand eintragen.",
                     "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
    "rgc_anwaltsvollmacht": ("rgc", "Vorlage 12: Vollmacht zur anwaltlichen Vertretung im Erstattungs-, Widerspruchs- "
                             "und Klageverfahren (Deutschland/Österreich); Name der Kanzlei wird eingetragen.",
                             "Akte › Datenschutz › „Vordrucke der Regeneration Clinic“"),
}


def art_info(art: str, beschreibung: str = "") -> dict:
    """``{"gruppe", "wofuer", "wo"}`` für die Übersicht; eigene Schreiben mit ihrer Beschreibung (F176)."""
    if ist_eigen(art):
        return {"gruppe": "eigen", "wofuer": beschreibung or "Eigenes Schreiben an den Patienten mit E-Mail-Text.",
                "wo": f"{SCHREIBEN_WO} › „Eigene Vorlagen“"}
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
