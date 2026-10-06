# Wünsche aus der Praxis (Alice, 06.10.2026)

Grundlage: zwei E-Mails von Alice vom 06.10.2026 (sieben Punkte zum neuen EPM, dazu die Liste der
Laborparameter). Dieses Dokument hält fest, **was umgesetzt wird**, **wie** es im Datenmodell abgebildet ist
und **welche Fragen offen sind**.

Die Fragen sind eilig: Alice ist **nur diese Woche erreichbar** und ab 19.10.2026 wieder da. Alles, was bis
dahin nicht geklärt ist, bleibt in der Zwischenlösung stehen und wird nicht eigenmächtig anders entschieden
(Arbeitsweise wie bisher: Unklarheiten markieren, nicht abweichend lösen).

Funktionsnummern schließen an `docs/BACKEND-FUNKTIONEN.md` an: **F110 ff.**, Unklarheiten **U39 ff.**

---

## 1 · Infusionsplan (F110, F111)

### Was umgesetzt wird

**Tage pro Woche je Beutelart (F110).** Bisher hat der Plan ein einziges Feld „Tage pro Woche“. Es bekommt
die Bedeutung „PE (Mischbeutel)“ und zwei Begleiter:

| Feld | Bedeutung | Beispiel aus der Mail |
|---|---|---|
| `tage_pro_woche` | PE / Mischbeutel, Tage pro Woche | PE 5× / Woche |
| `zusatz_tage_pro_woche` | Zusatzvolumen („Elektrolytbeutel“), Tage pro Woche | Elektrolytbeutel 2× / Woche |
| `freie_tage_pro_woche` | infusionsfreie Tage pro Woche | keine = 0 |

Alle drei sind unabhängig von der Zusammensetzung eintragbar, stehen im Vergleich mit dem Vorgänger, werden
in den Folgeplan übernommen und erscheinen auf der PDF. Plausibilität: `freie_tage_pro_woche` darf höchstens
`7 − max(PE, Zusatz)` sein – mehr freie Tage passen rechnerisch nicht zu den Infusionstagen.

**Übernahme der Werte in den neuen Plan.** War schon so (`PLANFELDER` in `infusionen/models.py`); die drei
Felder oben kommen dort dazu. Alices Vermutung stimmt also.

**Präparate (F111).** Das Präparat bekommt ein Feld „Hinweis“ (kurzer Text, erscheint bei der Auswahl und auf
der PDF-Zeile). Damit lassen sich Dinge wie „baugleich zu Cernevit“ oder „reines Taurolidin 2 %“ dort
hinterlegen, wo sie gebraucht werden.

| Kategorie | Änderung |
|---|---|
| Zusatzvolumen (Basislösung) | „Sterofundin“ → **Sterofundin ISO**, „Ringer-Infusionslösung“ → **Ringer-Lösung**, „Junosteril“ → **Jonosteril** (Tippfehler); **Ringer-Lactat** neu; **NaCl 0,9 %** bleibt |
| Vitamine | **Natrovit** neu, Hinweis „baugleich zu Cernevit, günstiger (Regressgefahr)“ |
| Katheterschutz | **NutriLock** (Hinweis „reines Taurolidin 2 %“) und **TauroLock** (Hinweis „Taurolidin mit Citrat“) neu; Taurolin und Taurolidin Nova bleiben für bestehende Pläne |
| Medikament | **Dipeptamin** ausgeblendet; **Omegaven** ausgeblendet, falls vorhanden |

Ausgeblendet heißt: in bestehenden Plänen bleibt alles stehen, neu auswählbar ist es nicht mehr. Präparate
werden in EPM grundsätzlich nicht gelöscht.

### Offene Fragen

| Nr. | Frage | Zwischenlösung |
|---|---|---|
| U39 | Reichen **Zahlen** pro Woche, oder sollen konkrete **Wochentage** hinterlegt werden (Mo/Mi/Fr)? | Zahlen je Beutelart + Zahl der infusionsfreien Tage |
| U40 | Ist mit „Elektrolytbeutel“ das **Zusatzvolumen** des Plans gemeint (Sterofundin ISO, Ringer …) oder ein weiterer, eigener Beutel? | Zusatzvolumen |
| U41 | „Weitere Bestandteile“ haben heute ein Freitextfeld **Häufigkeit** („täglich“, „Mo/Mi/Fr“). Soll das auch auf Tage pro Woche umgestellt werden? | bleibt Freitext |
| U42 | Dipeptamin und Omegaven **ausblenden** (bestehende Pläne behalten sie) statt löschen – richtig? | ausblenden |
| U43 | Umbenennen von Sterofundin/Ringer/Junosteril wirkt auch auf **alte Pläne**, weil es nur einen Katalogeintrag gibt. Soll das so sein, oder sollen neue Einträge daneben entstehen? | umbenennen (Tippfehler und Präzisierung, kein anderes Präparat) |

---

## 2 · Laborbefunde (F112, F113)

### Was umgesetzt wird

Neue App `befunde` mit drei Modellen:

- **`Laborparameter`** – der Katalog. Felder: Gruppe, Name, Einheit, Referenzbereich (von/bis, optional),
  Reihenfolge, aktiv. Gepflegt unter *Vorlagen › Laborparameter* (Recht „Vorlagen pflegen“), genau wie
  Präparate und Auswahllisten. Vorbelegt mit Alices Liste.
- **`Laborbefund`** – ein Befund je Abnahme: Patient, Abnahmedatum, Labor (Freitext), Beurteilung
  (formatierter Text), optional das hochgeladene Original als Dokument. Teil der Akte, also mit Verlauf und
  gesperrt, sobald die Akte abgeschlossen ist.
- **`Laborwert`** – eine Zeile je Parameter: Verweis auf den Katalog **oder** ein Freitextname (für
  Tumormarker und genetische Parameter), Wert als Zahl, alternativ Werttext („< 0,1“, „negativ“), Einheit
  (aus dem Katalog vorbelegt, überschreibbar), Referenzbereich.

Die Erfassungsmaske zeigt die Parameter nach Gruppen; eingetragen wird nur der Wert, Einheit steht schon da.
Leere Zeilen werden nicht gespeichert. Am Ende eine Zeile „weiterer Parameter“ für alles, was nicht im
Katalog steht.

Gruppen und Parameter nach der zweiten Mail: Transaminasen, Nierenwerte, Eisenhaushalt, Eiweiß- und
Fettstoffwechsel, Elektrolyte, Spurenelemente, Hämatologie, Vitamine, Knochenstoffwechsel, Pankreasenzyme,
Blutzucker/Diabetes, Schilddrüse.

### Offene Fragen

| Nr. | Frage | Zwischenlösung |
|---|---|---|
| U44 | **Referenzbereiche** je Parameter hinterlegen und abweichende Werte markieren? In der Mail nicht gewünscht, aber jedes Labor liefert sie mit | Felder vorhanden, bleiben leer; keine Markierung, bis das geklärt ist |
| U45 | Die **Einheiten** sind vorbelegt (GPT U/l, Kreatinin mg/dl, Natrium mmol/l …). Bitte einmal gegenlesen – Labore schreiben teils andere | Vorbelegung wie unten, je Wert überschreibbar |
| U46 | „Vitamin B1, B2, B6, B12, Folsäure“ und „Vitamin D, D3, Calcidiol, Calcitriol“ sind als **je eigene Parameter** angelegt – richtig? | je eigener Parameter |
| U47 | Werte wie **„< 0,1“ oder „negativ“**: als Text erlaubt (dann gibt es für diesen Wert keinen Verlauf/kein Diagramm)? | Text erlaubt, Zahl bevorzugt |
| U48 | Soll der **hochgeladene Original-Befund** am Laborbefund hängen (statt nur in den Dokumenten zu liegen)? | Verknüpfung vorhanden, freiwillig |
| U58 | Soll es einen **Verlauf je Parameter** geben (Diagramm wie beim Gewicht, z. B. Ferritin über 2 Jahre)? | vorgesehen, aber nur wenn gewünscht |

---

## 3 · BIA-Messungen (F114)

### Was umgesetzt wird

Modell `BiaMessung` in derselben App, als Eintrag der Akte: Datum, Gewicht (kg), BCM (kg), Fettmasse (kg),
ECW (%), Körperwasser (l), BMI, Beurteilung (formatierter Text), optional das Geräteprotokoll als Dokument.
Eigene Karte in der Akte mit Liste und Verlauf.

### Offene Fragen

| Nr. | Frage | Zwischenlösung |
|---|---|---|
| U49 | **BMI** aus Gewicht und Größe berechnen oder den Wert des Geräts eintragen? | Feld zum Eintragen, mit berechnetem Vorschlag daneben |
| U50 | Soll das **BIA-Gewicht** auch in den Gewichtsverlauf der Akte übernommen werden? | Häkchen beim Speichern, vorbelegt „ja“ |

---

## 4 · Berichte in der Akte (F115)

### Was umgesetzt wird

Modell `Bericht` als Eintrag der Akte: Titel, Art (Auswahlliste, z. B. Arztbrief, Verlaufsbericht,
Stellungnahme), Datum, Inhalt (formatierter Text), Status **Entwurf → freigegeben**. Entwürfe sind
bearbeitbar, mit der Freigabe entsteht eine PDF aus einer neuen Dokumentvorlage „Bericht“; sie wird als
Dokument der Akte abgelegt (Prüfsumme und Vorlagenversion wie beim Infusionsplan) und der Bericht ist danach
unveränderlich. Korrektur = neue Fassung.

### Offene Fragen

| Nr. | Frage | Zwischenlösung |
|---|---|---|
| U54 | Wer darf **freigeben** – nur Mediziner (wie beim Infusionsplan) oder auch Mitarbeiter? | eigenes Recht „Berichte freigeben“, Standard Mediziner; je Gruppe umstellbar |
| U55 | Soll der freigegebene Bericht automatisch als **PDF in die Dokumente** der Akte wandern? | ja (wie die Plan-PDF) |
| U59 | Welche **Berichtsarten** sollen in der Auswahlliste stehen? | Arztbrief, Verlaufsbericht, Stellungnahme, Sonstiges – unter Vorlagen änderbar |

---

## 5 · Unterlagen für die Sprechstunde (F116)

### Was umgesetzt wird

Eine Schaltfläche in der Akte erzeugt ein Sprechstundenblatt als PDF aus einer neuen Dokumentvorlage:
Patientenkopf, Diagnosen, aktueller Infusionsplan, letzte BIA-Messung, letzter Laborbefund, letzte
Empfehlung, Gewichtsverlauf der eingestellten Monate. Auf Wunsch zusätzlich in den Dokumenten ablegbar.

### Offene Fragen

| Nr. | Frage | Zwischenlösung |
|---|---|---|
| U56 | Stimmt der **Umfang**, fehlt etwas (Therapie? Kontakte der letzten Monate? Termine?) | Umfang wie oben |
| U60 | Nur **PDF** oder zusätzlich eine Ansicht am Bildschirm zum Durchgehen? | PDF; Ansicht leicht nachrüstbar |

---

## 6 · Diagnosen mit ICD (F117)

### Was umgesetzt wird

- **`Diagnose`** je Akte: Bezeichnung, ICD-Code, Zusatzkennzeichen **G** (gesichert), **V** (Verdacht),
  **Z** (Zustand nach), **A** (Ausschluss), Datum „seit“, Notiz, aktiv/beendet. Anzeige wie gewünscht:
  `Kurzdarmsyndrom [K91.2 G]`.
- **`Diagnosevorlage`** – die Liste im Hintergrund: ICD-Code und Bezeichnung, gepflegt unter *Vorlagen ›
  Diagnosen*. Beim Eintragen wird daraus vorgeschlagen; ein neuer Eintrag wandert in den Katalog, damit die
  Liste von allein mitwächst.

Der ICD-Code wird auf das Format geprüft (Buchstabe, zwei Ziffern, optional Punkt und ein bis zwei Stellen),
das Zusatzkennzeichen ist Pflicht.

### Offene Fragen

| Nr. | Frage | Zwischenlösung |
|---|---|---|
| U51 | Das bisherige **Freitextfeld „Diagnose“** bleibt zusätzlich bestehen (lange Texte, Versionen). Soll es bleiben, oder soll die Liste es ersetzen? | beides nebeneinander |
| U52 | Soll es neben G/V/Z/A auch eine **Seitenangabe** (rechts/links/beidseits) geben? | nein |
| U53 | Soll der Katalog bei **jeder neuen Eingabe** automatisch wachsen oder nur unter Vorlagen gepflegt werden? | wächst automatisch, unter Vorlagen korrigierbar |

---

## 7 · Versichertendaten (F118)

### Was umgesetzt wird

In den Stammdaten des Patienten:

| Feld | Werte |
|---|---|
| Versicherungsart | GKV, PKV, Selbstzahler, Sonstige, nicht erfasst |
| Versicherung | bisheriges Feld „Krankenkasse“, Beschriftung geändert – keine Daten gehen verloren |
| Versichertennummer | Freitext |

Sichtbar in Stammdaten, „Neuer Patient“ und auf dem Patientendatenblatt.

### Offene Frage

| Nr. | Frage | Zwischenlösung |
|---|---|---|
| U57 | Reichen die drei Angaben, oder braucht es für die Debatten mit den Kassen mehr (Versichertenstatus, Kostenträger-/IK-Nummer, Genehmigung bis, Befreiung)? | die drei Angaben |

---

## Vorbelegung der Laborparameter

Reihenfolge und Gruppen wie in Alices Mail; Einheiten als Vorschlag (U45).

| Gruppe | Parameter (Einheit) |
|---|---|
| Transaminasen | GPT (ALT) U/l · GOT (AST) U/l · Gamma-GT U/l · ALKP U/l · Bilirubin gesamt mg/dl · Bilirubin indirekt mg/dl · Bilirubin direkt mg/dl |
| Nierenwerte | Kreatinin mg/dl · GFR (CKD-EPI) ml/min/1,73 m² · GFR ml/min · Harnstoff mg/dl · Harnsäure mg/dl · Cystatin-C mg/l |
| Eisenhaushalt | Eisen µg/dl · Ferritin µg/l · Transferrin mg/dl · Transferrinsättigung % |
| Eiweiß- und Fettstoffwechsel | Triglyceride mg/dl · Albumin g/l · Gesamteiweiß g/l · CRP mg/l |
| Elektrolyte | Natrium mmol/l · Kalium mmol/l · Calcium mmol/l · Magnesium mmol/l · Phosphat mmol/l · Chlorid mmol/l |
| Spurenelemente | Kupfer µg/l · Zink µg/l · Selen µg/l · Mangan µg/l |
| Hämatologie | Leukozyten /nl · Erythrozyten /pl · Hämoglobin g/dl · Hämatokrit % · MCV fl · MCHC g/dl · MCH pg · Thrombozyten /nl · Lymphozyten % |
| Vitamine | Vitamin A µg/l · Vitamin B1 µg/l · Vitamin B2 µg/l · Vitamin B6 µg/l · Vitamin B12 ng/l · Folsäure µg/l · Vitamin K1 µg/l · Vitamin K2 µg/l · Vitamin E mg/l · Vitamin D µg/l · Vitamin D3 µg/l · Calcidiol (25-OH-Vitamin D) ng/ml · Calcitriol (1,25-(OH)₂-Vitamin D) pg/ml |
| Knochenstoffwechsel | Parathormon pg/ml |
| Pankreasenzyme | Amylase U/l · Lipase U/l |
| Blutzucker / Diabetes | C-Peptid ng/ml · HbA1c % · Glucose mg/dl · Insulin mU/l |
| Schilddrüse | TSH (basal) mU/l · fT3 pg/ml · fT4 ng/dl |
