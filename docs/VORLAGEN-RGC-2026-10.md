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
- Eingriffsspezifische Zusatzbögen zu 07/08 (Orthopädie/Traumatologie, HNO, Adipositaschirurgie) sind laut Review der
  nächste Schritt und nicht Teil dieser Lieferung.
