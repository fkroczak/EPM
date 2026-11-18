# Dreisprachigkeit der Regeneration Clinic (18.11.2026)

Die RGC arbeitet künftig auf Deutsch, Englisch und Lettisch. Festlegungen (Rückfragen vom 18.11.2026):

| Frage | Entscheidung |
|---|---|
| Umfang der Oberfläche | stufenweise: zuerst Sprachschalter, Menü, Seitentitel, Reiter der Akte, Labor; danach Bereich für Bereich |
| Wer sieht den Schalter | nur in der Firma RGC; die DSKM bleibt deutsch |
| Speicherung | im Benutzerkonto (gilt auf allen Geräten) |
| Neue Parameter beim Import | Vorschau; neu angelegt wird nur, was angehakt ist |

## Oberfläche
* Flaggen (Deutschland, Vereinigtes Königreich, Lettland) rechts in der Kopfzeile, am Telefon im Kopf –
  `frontend/src/components/layout/SprachSchalter.tsx`. Speichern: `PATCH /api/auth/ich/ {"sprache": "lv"}`.
* `frontend/src/lib/sprache.tsx`: `useSprache()`, `useT()` (deutscher Text → Übersetzung, sonst Deutsch),
  Wörterbuch `frontend/src/lib/uebersetzungen.ts`. Weitere Bereiche: Texte durch `t()` schicken und Einträge ergänzen.
* Labor: `frontend/src/lib/labor.ts` – Parameter- und Gruppennamen in der gewählten Sprache (Akte › Labor:
  Erfassungsmaske und Befund; der deutsche Name steht im Tooltip).

## Laborparameter
* `Laborparameter.name` = Deutsch, dazu `name_en`, `name_lv` (Migration `stammdaten/0027`, füllt die Übersetzungen
  des mitgelieferten Katalogs). Neue Gruppen: Gerinnung, Hormone, Immunologie und Autoantikörper, Allergologie und
  Mastzellen, Urin und Stuhl.
* Werte werden sprachunabhängig gespeichert (`Laborwert.parameter`). Ein lettischer Befund mit „Fosfors neorganiskais“
  landet beim Parameter „Phosphat“ – in jeder Sprache derselbe Verlauf.
* Wörterbuch `backend/stammdaten/laborbegriffe.py`: rund 230 Parameter DE · EN · LV mit Gruppe, Einheit, Kurzname und
  weiteren Schreibweisen aus den RGC-Vorlagen und lettischen Befunden.

## Texterkennung (Scans und KI)
* Der Katalogindex (`scans/ocr/auswertung.katalog_index`) kennt je Parameter den deutschen, englischen und lettischen
  Namen, die Synonyme, die Suchbegriffe und alle Schreibweisen des Wörterbuchs. Dieselbe Zuordnung nutzt die KI
  (`ki/pruefung.Katalog`); das Modell liest den Namen wie gedruckt, ohne zu übersetzen.
* Kürzel aus drei Großbuchstaben mit abgekürzter Erläuterung („MCV Eritroc.vid.tilp.“, „MCH Vid.Hb saturs er.“)
  treffen den Parameter.
* Begriffe des Wörterbuchs, die einen *anderen* Wert bezeichnen, sperren die Zuordnung über den Wortanfang:
  „Kalcijs jonizētais“/„Calcium ionisiert“ wird nicht mehr zu Calcium, „TSH receptoru antivielas“ nicht zu TSH.
* „Rezultāts sekos“ (Ergebnis folgt), „pending“, „negatīvs/pozitīvs“ gelten als Textwerte bzw. ausstehend.

## Export und Import (Vorlagen › Laborparameter, Recht „Vorlagen pflegen“)
* **Exportieren (CSV)** – `GET /api/laborparameter/export/`: Semikolon, UTF-8 mit BOM (Excel), Spalten
  `id;gruppe;name_de;name_en;name_lv;kurzname;einheit;referenz_von;referenz_bis;suchbegriffe;aktiv`.
* **Importieren (CSV)** – `POST /api/laborparameter/import/` mit `datei` → Vorschau; mit `zeilen` und
  `uebernehmen: true` → übernehmen. Mit `id` ändert eine Zeile alle gefüllten Spalten des Parameters; ohne `id` wird
  über Namen/Übersetzungen/Synonyme zugeordnet und nur Englisch und Lettisch ergänzt. Leere Zellen löschen nichts.
* **Aus RGC-Vorlagen übernehmen** – `GET /api/laborparameter/aus-vorlagen/` (Vorschau) bzw. `?als=csv`: alle
  Ankreuzzeilen der aktiven Laboranforderungen und Laborprofile der RGC (MRT, Röntgen, Echo, EKG und Röhrchenübersichten
  bleiben außen vor), über das Wörterbuch zugeordnet. Status je Zeile: *ergänzt vorhandenen* (vorgewählt),
  *schon vorhanden*, *neuer Parameter*, *unklar* (Profile wie „Kleines Blutbild“, Funktionstests). Namen und Gruppe neuer
  bzw. unklarer Zeilen lassen sich in der Vorschau korrigieren.
* Alles steht im Audit-Log („Laborparameter exportiert/importiert“).
