# EPM – Altdaten übernehmen (Administration › Import)

Stand: 02.10.2026 · Funktion F65 in `docs/BACKEND-FUNKTIONEN.md` · Grundlage: Altsystem-Datenanalyse (17 Regeln)

Das Werkzeug übernimmt die Daten des bisherigen Systems (MySQL, 6 Tabellen, Dokumente in `PatData/`) in das EPM.
Es schlägt Zuordnungen vor; die Administration prüft und korrigiert sie in der Oberfläche. Getestet ist es mit einem
**erfundenen** Dump, der die Regeln der Datenanalyse nachstellt. Der echte Dump ist noch nie gelaufen – der erste
Probelauf zeigt, wo Vorschläge nicht passen.

## Grundsätze

- **Nur Admin**, mit eigenem Recht „Altdaten übernehmen (Import)“. Import, Zurücknehmen und Abschließen verlangen
  Passwort und zweiten Faktor und stehen im Audit-Log.
- **Nur in ein System ohne echte Akten.** Testpatienten (ab Nr. 9001) stören nicht. Die Patientennummern des
  Altsystems werden übernommen; sie müssen frei sein und dürfen nicht im Löschprotokoll stehen.
- **Probelauf beliebig oft:** schreibt alles wie der Import und rollt es zurück.
- **Bis zum Abschließen zurücknehmbar:** Zurücknehmen entfernt alles Übernommene wieder; Dump und Zuordnungen bleiben.
  So lässt sich in der Testphase üben und zum Go-live mit einem frischen Dump wiederholen.
- **Nichts geht still verloren:** Was nicht übernommen wird, steht mit Grund und Anzahl im Protokoll; was in kein Feld
  passt, steht in der Bemerkung der Akte bzw. des Plans.
- **Kennwörter des Altsystems werden nie gespeichert.** Konten entstehen ohne Kennwort.

## 1 · Dump ziehen

Gebraucht wird ein **frischer** MySQL-Dump mit Struktur (`CREATE TABLE`) und Daten aller sechs Tabellen
(`benutzerdaten`, `versorger`, `patienten`, `gewichte`, `kontakte`, `infusionen`). Im Dump vom 23.02.2024 fehlt bei
`gewichte` und `kontakte` die Spalte `lastchange` – ohne sie gibt es kein Messdatum und keinen Kontaktzeitpunkt.

Beispiel auf dem Server des Altsystems (Namen anpassen):

```
mysqldump --single-transaction -u BENUTZER -p DATENBANK > epm-alt-JJJJMMTT.sql
gzip epm-alt-JJJJMMTT.sql        # optional; das Werkzeug liest .sql und .sql.gz (bis 50 MB, entpackt 300 MB)
```

Ein Export aus phpMyAdmin (Format SQL, Struktur und Daten) geht ebenso. Den Dump verschlüsselt übertragen und nach dem
Laden vom Arbeitsrechner löschen – er enthält alle Patientendaten.

## 2 · Dokumente bereitstellen

Die Dokumente kommen nicht über den Browser. Sie liegen auf dem EPM-Server im Projektordner:

```
/srv/epm/data/import/PatData/<PatientenID des Altsystems>/…
```

- Mit Zeitstempeln kopieren (z. B. `rsync -a`), damit das Dateidatum als Dokumentdatum erhalten bleibt.
- Für das Backend lesbar machen: `sudo chgrp -R 101 /srv/epm/data/import/PatData` und
  `sudo chmod -R g+rX /srv/epm/data/import/PatData`. Nicht lesbare Ordner zeigt das Werkzeug an.
- Der Ordner ist im Container nur lesend eingebunden; das Werkzeug kopiert, der Ordner bleibt unverändert.
- Rund 5 GB: Vorher freien Speicher prüfen (Schritt 4 zeigt ihn an; unter 200 MB frei hält die Übernahme an).

## 3 · Die Schritte im Werkzeug

**1 · Dump.** Datei wählen, „Dump laden“. Angezeigt werden Tabellen mit Zeilenzahl, Prüfsumme und Hinweise (z. B.
geleerte Kennwort-Spalten, umgerechnete `TIMESTAMP`-Spalten). Ein neuer Dump ersetzt den alten; die Zuordnungen
bleiben.

**2 · Zuordnungen.** Oben stehen die offenen Punkte; erst wenn keiner mehr offen ist, sind Probelauf und Import
möglich. Jede Änderung wird sofort gespeichert, „Vorschlag“ nimmt sie zurück.

| Bereich | Was zu prüfen ist |
|---|---|
| Tabellen und Spalten | Welche Spalte des Dumps welche Angabe im EPM füllt. Nicht zugeordnete Spalten und Tabellen ausdrücklich „nicht übernehmen“. |
| Benutzer | Je Name: vorhandener Benutzer, neues Konto (Rolle prüfen!), historischer Benutzer ohne Login, oder ohne Bearbeiter. |
| Versorger | Gleiche Firma = ein Versorger mit Ansprechpartnern; „-“ und leere Zeilen = leer. |
| Katheter und Werte | Katheter → Einträge der Auswahlliste; unbekannte Werte bei Nickelallergie/Geschlecht zuordnen. |
| Präparate | Schreibvarianten dem richtigen Präparat zuordnen, sonst entstehen doppelte Einträge. Unbekanntes: neu anlegen, als Text in die Bemerkung oder nicht übernehmen. |
| Gelöschte Patienten | Standard: nicht übernehmen. Sonst als abgeschlossene Akte mit Anlass und Abschlussdatum (ab dann läuft die Aufbewahrungsfrist). |
| Auffälligkeiten | Einzelne Werte: fehlendes Geburtsdatum (muss entschieden werden), unlesbare oder unplausible Zahlen, vierstellige PLZ, Gewichte ohne Zeitpunkt … Steht eine Patientennummer im Löschprotokoll des EPM (endgültig gelöschte Akte), lässt sich dieser Patient nur „nicht übernehmen“. |

**3 · Probelauf und Import.** Der Probelauf zeigt die Zählung „im Altsystem / wird übernommen / nicht übernommen
(warum)“ und das Protokoll nach Regeln. Bitte die Zählung gegen das Altsystem halten, bevor importiert wird. „Altdaten
übernehmen …“ verlangt Passwort und Code. Schlägt etwas fehl, bleibt die Datenbank unverändert.

**4 · Dokumente.** „Dokumente übernehmen“ läuft in Etappen und lässt sich anhalten und fortsetzen. Titel = Dateiname,
Typ „Sonstiges“, Datum aus PDF/EXIF oder Dateidatum. Die Dokumente erscheinen auf der Startseite unter „Nach und nach
prüfen“. Die Karte „Wird nicht übernommen“ listet, was liegen bleibt – bitte ansehen.

**5 · Abschließen.** Erst wenn die Akten geprüft sind (siehe unten). Danach ist Zurücknehmen nicht mehr möglich; Dump,
Zuordnungen und die Nummern in den Protokollen werden gelöscht. Wer die Protokolle aufbewahren will, lädt sie vorher
unter „Protokolle“ als Textdatei herunter.

## 4 · Nach dem Import prüfen

- Zählung des Imports gegen das Altsystem (Patienten, Gewichte, Kontakte, Pläne).
- Stichproben in den Akten als Mediziner/Mitarbeiter: Stammdaten, Umlaute, Diagnose/Therapie (Formatierung),
  Gewichtsverlauf, Kontakte mit Datum und Bearbeiter, Infusionspläne (aktueller Plan, Vorgänger, Präparate,
  Protonenpumpenhemmer, Bemerkung), Versorger und Ansprechpartner, Dokumente.
- Uhrzeiten der Kontakte gegen das Altsystem: Stimmen sie nicht (1–2 Stunden Versatz), bitte melden – dann liegt es
  am Spaltentyp im Dump (U29).
- Neue Konten: unter Administration › Benutzer je Person ein Einmal-Kennwort erzeugen; Rollen prüfen.
- Passt etwas nicht: zurücknehmen, Zuordnung korrigieren, erneut übernehmen.

## 5 · Ablauf zum Go-live

1. Altsystem für Eingaben sperren.
2. Frischen Dump ziehen; Dokumentenordner nachziehen (`rsync -a` überträgt nur Neues).
3. Im EPM: frischen Dump laden (ein vorher zum Üben importierter Stand wird davor zurückgenommen). Die Zuordnungen
   gelten weiter; neue offene Punkte (neue Benutzer, Präparate, Auffälligkeiten) entscheiden.
4. Probelauf, Zählung prüfen, Import, Dokumente.
5. Akten prüfen, Einmal-Kennwörter ausgeben.
6. Abschließen. Danach: Dump und Kopien löschen, Ordner `data/import/PatData` auf dem Server löschen, Altsystem
   abschalten (siehe `docs/DATENSCHUTZ.md`, Punkt 6).

## Was das Werkzeug nach den Regeln der Datenanalyse tut

| Regel | Umsetzung |
|---|---|
| 1 | Kennwort-Spalten werden beim Einlesen geleert; Konten ohne Kennwort, 2FA bei der ersten Anmeldung. |
| 2 | `lastchange` = Messdatum bzw. Kontaktzeitpunkt; Gewichte als „Datum ungenau“ mit Quelle „Altsystem“. |
| 3 | Doppelt kodierte Umlaute („Ã¼“) werden je Feld repariert (ftfy), auch in Dateinamen der Dokumente. |
| 4 | Verweis auf fehlenden Versorger → leer; Gewichte, Kontakte, Pläne ohne Patient → nicht übernommen (gezählt). |
| 5 | Gewichte 0, leer oder 9999 → nicht übernommen. |
| 6 | Größe 0 → leer; unter 3 → Meter, × 100. |
| 7 | „-“ und ähnliche Platzhalter → leer. |
| 8 | Bearbeiter-Namen → Benutzer; ohne Konto als historische Benutzer ohne Login. |
| 9, 10 | Katheter → Auswahlliste; Nickelallergie ja / nein / unbekannt. |
| 11 | HTML wird auf erlaubte Formatierung bereinigt; Linkziele bleiben als Text, Bilder als Vermerk. |
| 13, 14, 16 | Pläne: jüngster je Patient „aktuell“, ältere „abgelöst“ mit Vorgänger; Präparat-Freitexte → Präparate; Vitamine „A \| B“; Protonenpumpenhemmer mit Zeiten; Felder ohne Gegenstück im EPM → Bemerkung. |
| 15 | PatientenID = Patientennummer. |

## Offene Fragen

Siehe „Unklarheiten“ U26–U33 in `docs/BACKEND-FUNKTIONEN.md` – unter anderem: echte Akten aus der Testphase sperren den
Import (U27), andere Dateitypen im Dokumentenordner (U28), Spaltentyp der Zeitangaben (U29), Rollen der Konten (U31).
