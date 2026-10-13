# Vorlagen der Regeneration Clinic in EPM (Oktober 2026)

Stand 13.10.2026. Die Regeneration Clinic SIA hat zwölf Word-Vorlagen geliefert (Revision 3 vom 12.10.2026, Review und
Änderungsprotokoll als Vorlage 00). Sie sind in EPM als Dokumentvorlagen der Firma **RGC** hinterlegt – nur dort
sichtbar, die DSKM sieht sie nicht. Gepflegt werden sie unter Vorlagen › Dokumentvorlagen (Gruppe „Regeneration
Clinic – Patientenerklärungen und Vereinbarungen“), gedruckt in der Akte unter Datenschutz › „Vordrucke der
Regeneration Clinic“.

## Übernommene Dokumente

| Nr. | Dokument (Word-Datei) | Version · Stand | Art in EPM |
|---|---|---|---|
| 01 | Patientenerklärung Österreich (ÖGK/SVS/BVAEB/KFA), Stundung – `01_Patientenerklaerung_AT_OEGK_Stundung_V6.docx` | V6 · 10/2026 | `rgc_erklaerung_at` |
| 02 | Patientenerklärung Deutschland GKV, Stundung – `02_Patientenerklaerung_GKV_DE_Stundung_V5.docx` | V5 · 10/2026 | `rgc_erklaerung_gkv` |
| 03 | Patientenerklärung Deutschland BG/UV – `03_Patientenerklaerung_BG_UV_DE_V5.docx` | V5 · 10/2026 | `rgc_erklaerung_bguv` |
| 04 | Patientenerklärung Deutschland PKV, Stundung – `04_Patientenerklaerung_PKV_DE_Stundung_V5.docx` | V5 · 10/2026 | `rgc_erklaerung_pkv` |
| 05 | Patientenerklärung Stationäre Zusatzversicherung – `05_Patientenerklaerung_Zusatzversicherung_DE_V5.docx` | V5 · 10/2026 | `rgc_erklaerung_zusatz` |
| 06 | Schweigepflichtentbindung allgemein – `06_Schweigepflichtentbindung_allgemein_V6.docx` | V6 · 10/2026 | `rgc_schweigepflicht` |
| 07 | Aufklärung Operation DE/LV (Grundbogen) – `07_Aufklaerung_Operation_Universal_DE-LV_V3.docx` | V3 · 10/2026 | `rgc_aufklaerung_op` |
| 08 | Aufklärung Anästhesie DE/LV – `08_Aufklaerung_Anaesthesie_Universal_DE-LV_V3.docx` | V3 · 10/2026 | `rgc_aufklaerung_anaesthesie` |
| 09 | Vergütungs- und Rückerstattungsvereinbarung ÖGK (Selbstzahler) – `09_Rueckerstattung_Selbstzahler_OEGK_V3.docx` | V3 · 10/2026 | `rgc_vereinbarung_oegk` |
| 10 | Abtretungs- und Bevollmächtigungserklärung ÖGK mit Vorauszahlung – `10_Abtretung_formal_OEGK_mit_Vorauszahlung_V4.docx` | V4 · 10/2026 | `rgc_abtretung_oegk` |
| 11 | Anlage K – Kostenvoranschlag, Erstattungsprognose, Patienteninformation – `11_Anlage_K_Kostenvoranschlag_Erstattungsprognose_V2.docx` | V2 · 10/2026 | `rgc_anlage_k` |
| 12 | Vollmacht zur anwaltlichen Vertretung (Blankovollmacht, DE/AT) – `12_Anwaltsvollmacht_Erstattungsverfahren_V1.docx` | V1 · 10/2026 | `rgc_anwaltsvollmacht` |

Die Texte sind wörtlich übernommen (`backend/vorlagen/rgc_import.py` liest die Word-Dateien ohne Umformulierung
und schreibt `backend/vorlagen/statisch/rgc/<art>.json`). Jede Vorlage beginnt mit Briefkopf, Titel und der Zeile
„Vorlage NN · Version · Stand“; Überschriften, Kästen, Aufzählungen, Ankreuzkästchen, Tabellen („Rechtsstellung der
Klinik im Überblick“, Kostenaufstellung A–F, Anamnesefragen) und Unterschriftszeilen folgen dem Original. Die
zweisprachigen Bögen 07 und 08 enthalten beide Sprachfassungen in der Reihenfolge der Vorlage. Die Schweigepflichtentbindung
der RGC (06) ersetzt nicht den Vordruck „Schweigepflichtentbindung“ von EPM; beides steht in der RGC zur Verfügung.

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

## Entwurfsmodus

Wie die übrigen Vordrucke tragen die PDFs das Wasserzeichen „ENTWURF“, bis die Praxis jede Vorlage unter Vorlagen ›
Dokumentvorlagen einmal geprüft und freigegeben hat (oder den Entwurfsmodus für die Vorlage ausschaltet). Die Vorlagen
sind nicht Pflicht-Erklärungen und werden in der Akte nicht nachgehalten.

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
