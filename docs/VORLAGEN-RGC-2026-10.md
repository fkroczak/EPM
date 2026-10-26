# Vorlagen der Regeneration Clinic in EPM (Oktober 2026)

Stand 14.10.2026. Die Regeneration Clinic SIA hat ihre Word-Vorlagen geliefert: 14 Anforderungen (Labor, Bildgebung,
Funktionsdiagnostik) und zwölf Formulare (Revision 3 vom 12.10.2026, Review und Änderungsprotokoll als Vorlage 00).
Alle sind in EPM als **eigene Schreiben der Firma RGC** hinterlegt – nur dort sichtbar, die DSKM sieht sie nicht.
Gepflegt werden sie unter Vorlagen › Dokumentvorlagen, gedruckt in der Akte über Weitere Aktionen (⋯) › „Schreiben und
E-Mail …“.

Umgesetzt werden die Word-Dateien mit `werkzeuge/rgc-vorlagen.py` nach `backend/vorlagen/statisch/rgc/`. Die
Datenmigrationen `vorlagen/0007_rgc_vorlagen` und `0010_rgc_vorlagen_ergaenzt` legen daraus die eigenen Schreiben an,
jedes nur einmal (Kennung `mitgeliefert`). Danach werden sie wie jede eigene Vorlage gepflegt.

## Formulare (Gruppe „Aufklärungen, Erklärungen und Abrechnung“)

| Nr. | Dokument (Word-Datei) | Version |
|---|---|---|
| 01 | Patientenerklärung Österreich (ÖGK/SVS/BVAEB/KFA), Stundung – `01_Patientenerklaerung_AT_OEGK_Stundung_V6.docx` | V6 |
| 02 | Patientenerklärung Deutschland GKV, Stundung – `02_Patientenerklaerung_GKV_DE_Stundung_V5.docx` | V5 |
| 03 | Patientenerklärung Deutschland BG/UV – `03_Patientenerklaerung_BG_UV_DE_V5.docx` | V5 |
| 04 | Patientenerklärung Deutschland PKV, Stundung – `04_Patientenerklaerung_PKV_DE_Stundung_V5.docx` | V5 |
| 05 | Patientenerklärung stationäre Zusatzversicherung – `05_Patientenerklaerung_Zusatzversicherung_DE_V5.docx` | V5 |
| 06 | Schweigepflichtentbindung allgemein – `06_Schweigepflichtentbindung_allgemein_V6.docx` | V6 |
| 07 | Aufklärung Operation DE/LV (Grundbogen) – `07_Aufklaerung_Operation_Universal_DE-LV_V3.docx` | V3 |
| 08 | Aufklärung Anästhesie DE/LV – `08_Aufklaerung_Anaesthesie_Universal_DE-LV_V3.docx` | V3 |
| 09 | Rückerstattung Selbstzahler ÖGK – `09_Rueckerstattung_Selbstzahler_OEGK_V3.docx` | V3 |
| 10 | Abtretung ÖGK mit Vorauszahlung – `10_Abtretung_formal_OEGK_mit_Vorauszahlung_V4.docx` | V4 |
| 11 | Anlage K – Kostenvoranschlag und Erstattungsprognose – `11_Anlage_K_Kostenvoranschlag_Erstattungsprognose_V2.docx` | V2 |
| 12 | Vollmacht zur anwaltlichen Vertretung – `12_Anwaltsvollmacht_Erstattungsverfahren_V1.docx` | V1 |

## Anforderungen (Gruppe „Anforderungen: Labor, Bildgebung, Funktionsdiagnostik“)

Laboranforderungen 01–10 (Basislabor, Gerinnung und Thrombophilie, Mikronährstoffe, Endokrinologie, Diabetologie,
Immunologie, Allergologie, Mastzellaktivierung, Rheumatologie, Onkologie und Tumormarker), MRT- und
Röntgen-Anforderung, Echokardiographie sowie EKG und Funktionsdiagnostik (`RC_Vorlage_01` bis `RC_Vorlage_14`).

Die Schweigepflichtentbindung der RGC (06) ersetzt nicht den Vordruck „Schweigepflichtentbindung“ von EPM unter Akte ›
Datenschutz; beides steht in der RGC zur Verfügung.

## Laborprofile Malabsorption (14.10.2026)

Grundlage: „Laborprofile Malabsorption – Strukturierte Anforderungsprofile zur Integration in die Klinik-IT“
(Regeneration Clinic SIA, Dokumentversion 1.0, Status Entwurf zur Freigabe). Für Patienten der Stiftung, die in der
Klinik abgenommen werden, auf dem Briefkopf der Klinik. In der Gruppe „Anforderungen“ stehen neun Bögen:

| Kennung | Bogen | Inhalt |
|---|---|---|
| `eigen-rgc-mal00` | Laborprofile Malabsorption – Übersicht und Regelwerk | Profilübersicht, Regeln R1–R11, Monitoring-Intervalle |
| `eigen-rgc-mal01` | MAL-01 Basisprofil Malabsorption (Stufe 1) | 1.01–1.35 |
| `eigen-rgc-mal02a` | MAL-02A Fettmalabsorption (Stufe 2) | 2A.1–2A.6 |
| `eigen-rgc-mal02b` | MAL-02B Ausgeprägte oder langdauernde Malabsorption (Stufe 2) | 2B.1–2B.7 |
| `eigen-rgc-mal02c` | MAL-02C Kurzdarmsyndrom / Darmversagen (Stufe 2) | 2C.1–2C.4 |
| `eigen-rgc-mal03` | MAL-03 Ursachenbezogene Zusatzdiagnostik (Stufe 3) | Teilprofile 03A–03D zum Ankreuzen |
| `eigen-rgc-mal04` | MAL-04 Initialpanel (Vollpanel) | MAL-01 + MAL-02A + MAL-02B, MAL-02C ankreuzbar (R10) |
| `eigen-rgc-mal05` | MAL-05 Monitoring chronische intestinale Insuffizienz | 5.1 zum Eintragen, 5.2, 5.3, Intervalle |
| `eigen-rgc-mal06` | MAL-06 Refeeding-Monitoring | 6.1–6.5, Pflichthinweis Thiamin, Abnahmezeitpunkte |

**Briefpapier:** Die Bögen stehen auf dem Briefpapier der Klinik 1:1 wie im gelieferten Dokument – oben das salbeigrüne Band (#BDC9C2) mit Wellenkante, Logo und Anschrift (Inter), unten das Band mit Postanschrift, Registration No. und Health Institution Code, beides auf jeder Seite; auf der ersten Seite Absenderzeile, Kontakt (Prof. Dr. Markus Masin, Director) und „Riga, Datum“. Eingestellt im Baustein „Briefkopf“ (`"briefpapier": "rgc"`, im Editor „Briefpapier der Regeneration Clinic“); auch für die übrigen RGC-Vorlagen einschaltbar. Maße und Texte in `backend/vorlagen/briefpapier.py`, Schriften Inter und Carlito in `backend/schriften`.

Aufbau jedes Bogens: Patient und Anforderung (Abnahmezeit, Arzt, nüchtern, Dringlichkeit) · Indikation und
Fragestellung · **Röhrchen und Material (Übersicht)** – je Röhrchen die Parameter-Nummern nach Pflicht, optional und
Reflex · je Röhrchen/Material die Parameter mit Status, LOINC und Hinweis · Legende · Pflichthinweise zur Präanalytik ·
Reflexregeln des Profils · Unterschrift. Pflichtparameter sind angekreuzt (☒), optionale und Reflexparameter zum
Ankreuzen (☐); bei MAL-03 wird zuerst das Teilprofil gewählt. Material und LOINC stehen genau wie im Dokument, auch
„prüfen“ (als „im Laborkatalog prüfen“). Reflexparameter aus einem anderen Profil stehen mit ihrem Röhrchen auf dem
Bogen, wenn ein Parameter des Bogens die Regel auslöst (MAL-01: Parathormon 2A.4 nach R7, EDTA-Plasma, gekühlt).

Die Inhalte stehen zusätzlich strukturiert in `backend/vorlagen/statisch/laborprofile-malabsorption.json` (je
Parameter: Profil, Nr., Parameter, Material, LOINC, Status, Regelbezug, Hinweis – die Felder aus Abschnitt 6). Eine
neue Fassung des Dokuments: `python3 werkzeuge/rgc-laborprofile.py LABORPROFILE.docx`, dann eine weitere
Datenmigration; bereits angelegte Bögen ändert sie nicht (dann unter Vorlagen › Dokumentvorlagen eine neue Fassung).

Noch offen (laut Dokument vor Produktivsetzung): LOINC-Codes, Einheiten und Referenzbereiche gegen den Katalog des
beauftragten Labors abgleichen; Röhrchenfarben und Abnahmemengen nennt das Dokument nicht – sie hängen vom
Röhrchensystem des Labors ab und können je Bogen in der Vorlage ergänzt werden. Die Reflexregeln stehen als Hinweise
auf dem Bogen; automatisch nachgefordert wird in EPM nichts (EPM hat keine Laborschnittstelle).

## Was EPM ausfüllt

Aus der Akte eingesetzt werden: Name, Geburtsdatum, Anschrift, Versicherung (Feld „Versicherung/Krankenkasse“ der Akte),
Versichertennummer und – bei den Aufklärungsbögen und der Anlage K – die aktiven Diagnosen mit ICD-Code. Fehlt eine
Angabe in der Akte, steht „—“.

## Was von Hand ausgefüllt wird

Alles Übrige auf dem Ausdruck: IK-Nummer, Aufnahmedatum, Versorgungsform, Vorabgenehmigung, Kooperationspartner,
Einstufungen und Aktenzeichen, Bankdaten-Bezug, alle Ankreuzkästchen (Empfängergruppen, Kommunikationswege,
Anamnesefragen, Verfahren), die Beträge der Anlage K (EPM hat keine Kostendaten), der präanästhesiologische Befund,
Diagnose-/Eingriffsbeschreibungen der Aufklärungsbögen, Name und Kanzlei des Rechtsanwalts (Vorlage 12) sowie
Ort, Datum und Unterschriften.

## Freigabe

Die mitgelieferten Fassungen sind sofort in Gebrauch (Fassung 1). Vor dem Einsatz mit echten Patienten sollte die
Klinik jede Vorlage unter Vorlagen › Dokumentvorlagen prüfen; die offenen Punkte des Reviews stehen unten.

## Noch zu entscheiden (Abschnitt 6 des Reviews der Klinik)

- ÖGK-Stundung (Vorlage 01): Standard oder Einzelfallinstrument.
- Unterzeichnung der Vorlagen 09 und 10: Director oder Chefarzt mit Vertretungsvollmacht.
- Bankverbindung (IBAN/BIC in 01, 09, 10) vor der Freigabe verifizieren.
- Lettische Fassungen von 07 und 08: fachärztliche Gegenlesung (Anästhesiologie, Chirurgie); sprachlich geprüft, nicht
  fachärztlich abgenommen.
- Anwaltsvollmacht (Vorlage 12): Kanzleien für Deutschland und Österreich benennen; der Name wird bei Mandatierung
  eingetragen.
- Lesbarkeitstest der patientenzugewandten Passagen (Versprechen-Kästen, Stundungskästen, Anlage K) durch eine
  nichtjuristische Person.
- Rechtsprüfung: abschließende Freigabe durch je einen Fachjuristen für deutsches, österreichisches und lettisches
  Recht steht aus.
- Eingriffsspezifische Zusatzbögen zu 07 (Orthopädie/Traumatologie, HNO, Adipositas und Stoffwechselerkrankungen)
  sind seit 26.10.2026 als standardisierter Vorschlag mitgeliefert (`eigen-rgc-z07-ortho`, `eigen-rgc-z07-hno`,
  `eigen-rgc-z07-adipositas`, zweisprachig DE/LV) – fachärztliche Prüfung steht aus.

## Dokumentenautomation (26.10.2026)

Alle Vorlagen der RGC kennen zusätzlich die Datenfelder des Behandlungsfalls (`{{Fall.…}}`, `{{Rechnung.…}}`,
`{{Dokument.…}}`, Tabellen „rechnung“ und „leistungen“). Im Fall werden sie automatisch als Paket je Kostenträgertyp
angelegt und ausgefüllt; OP-Bericht, Entlassungsbrief, Konsiliarbericht und Rechnung gibt es je Sprache. Details:
[`DOKUMENTENAUTOMATION-RGC-2026-10.md`](DOKUMENTENAUTOMATION-RGC-2026-10.md).
