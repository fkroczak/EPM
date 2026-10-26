# EPM – Nachweis der Backend-Funktionen

Stand: 10.10.2026 · Code-Stand: Automatisierungen für die Pflege (F184–F186); Infoblatt an die Praxis (F177); Schreiben mit E-Mail (F172–F176); Scans und Texterkennung (F160–F171); Passkey und Telefon (F130–F134); Wünsche aus der Praxis vom 06./07.10.2026 (F110–F124); Fehlerliste vom 02.10.2026 (F98–F106, geändert F03, F05, F09, F20, F31, F52, F72, F85, F86, F97); Runde 7 (Startseite und Oberfläche S01–S17, F90–F97); Runde 6 (Altdaten übernehmen, F65: Werkzeug Administration › Import); Runde 5 (Datensicherung aus der Oberfläche, F61–F64, O-07, O-23, O-24); Runde 4 (Datenschutz nach DSGVO, F74–F83; davor Runde 3 bis `e74f4ff`: PDF-Erzeugung,
Dokumentvorlagen, Rückmeldungen aus dem Testsystem, falsch zugeordnete Dokumente, Löschen nach Art. 17 DSGVO) ·
Grundlage: Altsystem-Datenanalyse mit Entscheidungen, Entwurf „EPM Oberfläche“ (23 Ansichten), „EPM-Server Aufbau“,
Festlegung zu den Rechten vom 01.10.2026, Prüfung nach DSGVO vom 02.10.2026 (`docs/DATENSCHUTZ.md`).

## Statuswerte

| Status | Bedeutung |
|---|---|
| ABGESCHLOSSEN UND GETESTET | über das bestehende Frontend mit echtem Backend und echter Datenbank getestet |
| TEILWEISE ABGESCHLOSSEN | Backend-Teil ganz oder zum Teil vorhanden, Frontend-Anbindung und/oder Teile der Logik fehlen |
| NICHT ABGESCHLOSSEN | beschlossen, aber noch nicht umgesetzt |
| BLOCKIERT DURCH FEHLENDE INFORMATION | Umsetzung hängt an einer offenen fachlichen Frage |

„ABGESCHLOSSEN UND GETESTET“ heißt: Ein Browsertest bedient die Oberfläche (React-Build hinter Nginx) gegen das echte
Django-Backend und PostgreSQL 18 – Frontend → API-Aufruf → Endpunkt → Validierung → Logik → Datenbank → Antwort →
Anzeige – und das Ergebnis ist nach einem Neustart von Backend und Webserver noch da. Den Neustart prüfen
`akte.spec.ts`, `start.spec.ts`, `versorger.spec.ts` und als letzte Datei `zz-neustart.spec.ts`: Sie startet die Container
neu und prüft die Ergebnisse aller anderen Browsertests erneut über die Oberfläche.

Teststatus-Angaben beziehen sich auf zwei Arten automatischer Tests. Beide laufen bei jedem Push in GitHub Actions
(Workflow `.github/workflows/backend.yml`, Ergebnis als Kommentar am Commit):

- **Backend-Tests** (`backend/*/tests.py`) gegen PostgreSQL 18: API-Aufruf → Validierung → Logik → Datenbank → Antwort,
  ohne Oberfläche. Laufen auch nach jedem `sudo epm-update` auf dem Server.
- **Browsertests** (`frontend/e2e/*.spec.ts`, Playwright mit Chromium) gegen den kompletten Stack aus
  `werkzeuge/ci-stack.sh`: dieselbe Compose-Datei, Nginx-Konfiguration und dieselben Images wie auf dem Server, mit
  Musterdaten und eigenen Testkonten je Rolle.

Stand 08.10.2026 (Passkey und Telefon, F130–F134, Pull Request #14): **347 von 347 Backend-Tests** und **108 von 108 Browsertests grün** (Lauf 37714211870; dazu 4 Bildschirmfoto-Tests, nur beim manuellen Start).
Stand 02.10.2026 (Datenschutz F74–F83 und Systemseite/Kalender/Infusionspläne F84–F89 zusammen): **141 von 141 Backend-Tests** und **66 von 66 Browsertests grün** (Lauf 36976550763, Commit `97e5a5b`; dazu 1 Bildschirmfoto-Test, nur beim manuellen Start).
Stand 02.10.2026 (Rechte: Löschen auch Admins, Systemverwaltung als Vertretung): **142 von 142 Backend-Tests** und **66 von 66 Browsertests grün** (Lauf 36989064354, Commit `0cca47d`).
Stand 02.10.2026 (Startseite und Oberfläche S01–S17, F90–F97, Pull Request #7 auf `main` mit Pull Request #6): **236 von 236 Backend-Tests** und **82 von 82 Browsertests grün** (Lauf 37036210226, Commit `33612fa`; dazu 2 Bildschirmfoto-Tests, nur beim manuellen Start).
Stand 02.10.2026 (Behebung der Gegenprüfung, O-27 bis O-29, Pull Request #6): **216 von 216 Backend-Tests** und **74 von 74 Browsertests grün** (Lauf 37031797322, Commit `641936b`; dazu 2 Bildschirmfoto-Tests, nur beim manuellen Start).
Stand 02.10.2026 (Altdaten-Import F65, in `main` als `26084ba`, Pull Request #5): **212 von 212 Backend-Tests** und **74 von 74 Browsertests grün** (Lauf 37018759253 auf `main`; vorher im Pull Request Lauf 37006765744 und auf dem Branch Lauf 37004133307; dazu 2 Bildschirmfoto-Tests, nur beim manuellen Start).
Stand 02.10.2026 (Datensicherung F61–F64 mit O-07, O-23, O-24, in `main` zusammen mit der Rechte-Änderung): **156 von 156 Backend-Tests** und **70 von 70 Browsertests grün** (Lauf 36991958136 auf `main`, Commit `7ba9f35`; vorher im Pull Request #3 Lauf 36990805767; dazu 1 Bildschirmfoto-Test, nur beim manuellen Start).

Sporadische Fehlschläge der Browsertests (kein Produktfehler belegt, Ursache im Test bzw. offen): „Ärzte aus der
gemeinsamen Liste zuordnen …“ tippte gelegentlich, bevor das leere Formular stand (schon auf `main`, Lauf 36942510984;
seit `3935b3a` wartet der Test darauf). „Endgültig löschen: nur Mediziner …“ (F73) fand in Lauf 36950601660 einmal das
gerade hochgeladene Dokument nicht in der Liste; in den Läufen davor und danach nicht aufgetreten, Ursache nicht
geklärt (die Aufzeichnung des Laufs ist von hier aus nicht abrufbar). Der Seitenzustand fehlgeschlagener Tests wird
seit `34c627d` ab dem Seiteninhalt in den Kommentar geschrieben, damit ein erneutes Auftreten auswertbar ist. Neu in Lauf 36986911046 (erster Versuch): „Kontakt mit Wiedervorlage erfassen, suchen, stornieren“ – Kontakt und Wiedervorlage waren gespeichert (Reiter „Kontakte 1“, nächster Termin im Aktenkopf), die Liste zeigte aber noch „0“; im zweiten Versuch desselben Laufs und in Lauf 36985771116 grün, Ursache nicht geklärt (Seite unverändert seit Runde 2).

## Übersicht

| Nr. | Funktion | Ansicht (Entwurf) | Status |
|---|---|---|---|
| 26.10.2026 | Dokumentenautomation der Regeneration Clinic, F193: Behandlungsfall als eine Datenquelle (Kostenträgertyp, Kooperationspartner, Sprache DE/LV/EN, Fachbereich, Behandlung, Texte für OP-Bericht/Entlassungsbrief/Konsil); Dokumentenpaket je Kostenträgertyp (Vorlagen 01–12, Zusatzbogen je Fachbereich, OP-Bericht, Entlassungsbrief, Rechnung); Status Entwurf → erzeugt → final; PDF jederzeit neu erzeugbar, jede Erzeugung eine unveränderliche Fassung mit Prüfsumme und Datenstand; Rechnung mit Leistungspositionen aus dem Leistungskatalog, bis zur Finalisierung änderbar, Storno + neue Rechnung; fortgeschrittene elektronische Signatur (PAdES, pyHanko), extern signierte PDF, Scan der Papierunterschrift oder Finalisieren; DOCX-Rundweg für Freitexte; Zusatzbögen Orthopädie/Traumatologie, HNO, Adipositas zu Vorlage 07; Recht „Fall-Dokumente finalisieren“. App `faelle`, Doku `docs/DOKUMENTENAUTOMATION-RGC-2026-10.md` | Akte › Fälle; Administration › Fälle und Abrechnung | TEILWEISE ABGESCHLOSSEN – Backend-Tests `faelle/tests.py`; Browsertest steht aus |
| 26.10.2026 | Diktate, F192: „Neues Diktat“ auch im Menü „Diktate“ (Patient wählen, Berichtsart, aufnehmen – Entwurf entsteht beim Senden); Menüpunkt für alle mit Recht „Diktieren“ | Menü „Diktate“ | ABGESCHLOSSEN – Typprüfung |
| 23.10.2026 | Diktate, F192: Mikrofon im Bericht (Arztbrief, Konsultationsbericht …) und im Kommentar des Infusionsplans; Aufnahme im Browser (WebM/Opus bzw. MP4/AAC, ≈ 15 MB je Stunde), Abschrift offline im OCR-Dienst mit whisper.cpp (large-v3-turbo q5_0, nur CPU), „sofort“ oder „heute Nacht“, „selbst“ oder „Sekretariat“; Nachhören mit Sprung zum Wort und markierten unsicheren Wörtern, „In den Text übernehmen“; eigene Fachbegriffe; Aufnahme wird bei der Freigabe gelöscht; Recht „Diktieren“, Audit-Art „Diktat“, Berichtsart „Konsultationsbericht“; `GET/POST /api/diktate/…` | Akte › Berichte, Infusionsplan › Kommentar, Menü „Diktate“ | TEILWEISE ABGESCHLOSSEN – 19 Backend-Tests (`backend/diktate/tests.py`, echte Abschrift nur mit Modell, z. B. in CI); im Browser mit simuliertem Mikrofon durchgespielt; Live-Mitschreiben folgt nach dem Aufrüsten (16 GB / 8 Kerne) |
| 15.10.2026 | Neutrales Favicon: statt der Stiftungsfarben (Nachtblau, Orange, Gold) das EPM-Symbol der Anmeldeseite (Schiefer-Petrol #24353D mit weißer Pulslinie, `frontend/public/favicon.svg`); `theme-color` ebenfalls Schiefer-Petrol, Beschreibung im `index.html` ohne Firmennamen („EPM – Elektronisches Patientenmanagement“) | Browser-Tab, Lesezeichen | ABGESCHLOSSEN |
| 15.10.2026 | KI (Experimentell), F191: lokale KI (Qwen3.5 über llama.cpp, nur CPU, offline) liest die Dokumente der Akten nachts nur lesend, erkennt und strukturiert (Dokumenttyp, Metadaten, Laborwerte, Infusionen, Medikation, Diagnosen, Texte), Regelprüfung, Prüf-Queue mit Freigabe und bestätigter Übernahme (Konflikte nur mit Entscheidung), Hinweise Labor ↔ Infusionsplan, Berichtsentwürfe auf Anforderung, Qualitäts-Dashboard, Modell-Registry mit Evaluation/Aktivierung/Rollback, Ressourcensteuerung (Nachtfenster, CPU/RAM/Last, Sicherung), DB-Rolle `epm_ki`, verschlüsselte Zwischendateien, Audit-Art „KI“; `GET/POST /api/ki/…` (docs/KI-API.md); `compose.ki.yaml`, `epm-ki`, `ki-pruefen.sh`, `ki-benchmark.sh`; Einrichtung aus der Oberfläche (Modell wählen, laden/hochladen, Grenzen, Benchmark, Ein/Aus über den Systemagenten) | Menü „KI (Experimentell)“, Akte › KI (Experimentell), Administration › KI | TEILWEISE ABGESCHLOSSEN – 74 Backend-Tests (`backend/ki/test_*.py`); Frontend gebaut und typgeprüft, Browsertest und Lauf mit echtem Modell stehen aus (Ziel-VM mit 16–32 GB noch nicht vorhanden); Training (LoRA) noch nicht gebaut |
| 14.10.2026 | E-Mail-Vorlagen im eigenen Fenster bearbeiten: „E-Mail bearbeiten“ über der Seite oder Doppelklick auf die E-Mail öffnet ein Fenster wie ein E-Mail-Programm (An, Betreff, Anlage, Text); Angaben aus der Akte erscheinen als lesbare Chips (TipTap, `components/TextMitAngaben.tsx`, erst beim Öffnen geladen), Einfügen an der Schreibmarke, getippte `{{…}}` werden zum Chip; Vorschau mit Testpatient (`POST /api/vorlagen/{art}/vorschau/` mit `ausgabe: "email"`). Gespeichert wird weiter reiner Text – die E-Mail geht als Text | Vorlagen › Dokumentvorlagen (Schreiben) | ABGESCHLOSSEN – Browsertest `dokumentvorlagen.spec.ts` „E-Mail-Vorlage im eigenen Fenster …“ lokal grün; Lauf steht aus |
| 14.10.2026 | Fußzeile gestaltbar wie die Kopfzeile, Vorstand und Spendenkonto zentral: Absenderangaben mit `vorstand` und `bankverbindung` (Vorlagen › Briefkopf und Logo, vorbelegt mit den bisherigen Angaben der Stiftung), Datenfelder `{{Absender.Vorstand}}`/`{{Absender.Bankverbindung}}`; Migration `vorlagen 0013` ersetzt den festen Text in allen Vorlagen (freigegebene Fassung → neue Fassung, „freigegeben von“ bleibt, Entwurf an Ort und Stelle); Zeilen der Fußzeile, deren Angaben alle leer sind, entfallen. Baustein Fußzeile mit eigenem Band (`band` gerade/schraeg/welle/bogen, `bandfarbe`, `textfarbe`) und Schaltern „Zeile Vorstand/Spendenkonto“; im Editor an ihrer Stelle unten auf der Seite. Dazu Korrektur `vorlagen 0012` (Wartungsmodus, Rückfall 2.0.26) | Vorlagen › Briefkopf und Logo, Dokumentvorlagen | ABGESCHLOSSEN – Tests `vorlagen.test_rgc.MigrationMitSchutzTest` (Migrationen bei eingeschaltetem Schutz-Trigger), `vorlagen.test_gestaltung.FusszeileTest`; Browsertests `dokumentvorlagen.spec.ts`, `admin.spec.ts` lokal grün; Lauf steht aus |
| 14.10.2026 | Gestaltung am Raster (Kundenwunsch „fast wie Word, mit festen Arretierungspunkten“): Seite im Editor in Millimetern wie die PDF; Abschnitte mit der Maus (Finger/Stift am Griff) verschieben, das Ziel wird angezeigt; 6-Spalten-Raster (Optionen `raster_von`/`raster_bis` 1–6, `neben_vorherigem: "raster"`; ältere Vorlagen mit ⅓/½/⅔ rechnet der Editor um, der Server setzt sie weiter wie bisher); Breite am Rand ziehen; Bausteine aus der Leiste auf die Seite ziehen; Doppelklick schreibt Text/Titel direkt auf der Seite. Briefkopf mit **Kopfband** (`kopfband` gerade/schraeg/welle/bogen, `bandfarbe`, `textfarbe`, `bandhoehe_mm` 20–80, `band_seiten` alle/erste, `logo_rechts`, `fussband`). Neuer Baustein **Anschriftfeld (DIN 5008)** per Schalter „DIN 5008“ (Form A/B, Rücksendeangabe, Anschrift bis 6 Zeilen, Informationsblock, Falz- und Lochmarke; nur Hochformat, vor dem ersten Seitenumbruch). Modul `vorlagen/gestaltung.py`, Editor `vorlagenRaster.ts` | Vorlagen › Dokumentvorlagen | ABGESCHLOSSEN – Tests `vorlagen.test_gestaltung` (9, Lage im PDF nachgemessen), Browsertest `dokumentvorlagen.spec.ts` „Gestaltung am Raster …“; Lauf steht aus |
| 14.10.2026 | Korrespondenz in der Akte (Kundenwunsch): jedes Schreiben an oder über den Patienten wird abgelegt, Status Entwurf → freigegeben → versendet. Neue App `korrespondenz` (Modell `Schreiben` mit Vorlage und -version, Betreff, Empfänger, Freitext, Termin, Momentaufnahme der Blöcke, Freigabe, gespeicherter PDF mit SHA-256, Versandweg/-datum/-notiz; `simple_history`; Datenbank-Trigger `epm_korrespondenz_schutz`: Entwurf frei, danach nur einmal „versendet“). Endpunkte `GET/POST /api/korrespondenz/?patient=&status=`, `PATCH/DELETE …/<id>/` (nur Entwurf), `POST …/vorschau/`, `GET …/<id>/pdf/` (Entwurf: Vorschau; sonst gespeicherte PDF, Prüfsumme geprüft), `POST …/<id>/freigeben/` (neues Recht „Schreiben freigeben“, Standard Mediziner und Admin), `POST …/<id>/versendet/`, `POST …/<id>/kopieren/`, `GET …/<id>/verlauf/`; Audit-Art „Korrespondenz“; Verlauf der Akte Bereich `korrespondenz`; Zähler im Aktenkopf; Kopie der Akte und endgültiges Löschen berücksichtigen die Schreiben. Neue Datenfelder für Schreiben und eigene Schreiben: `Gewicht.aktuell/kg/Datum/BMI/Trend`, `Medikamente.Liste`, `Plan.Kurz` und Felder des aktuellen Infusionsplans, `Schreiben.Betreff/Empfänger/Text/Freigabevermerk`; Tabellen Medikation und Zusammensetzung. Oberfläche: Reiter „Korrespondenz“ mit Status-Filter, „In der Akte ablegen (Entwurf)“ im Dialog „Schreiben und E-Mail“ | Patientenakte › Korrespondenz | ABGESCHLOSSEN – Tests `korrespondenz.tests` (14), Browsertest `korrespondenz.spec.ts` (4); Lauf steht aus |
| 13.10.2026 | Selbstheilung: gute Version (`EPM_VERSION_GUT`), automatischer Rückfall bei fehlgeschlagenem Update, Wächter im Status-Lauf des Systemagenten (fehlende Container starten, ungesunde neu starten, Backend notfalls zurückschalten, knappe Platte), `epm.service` mit Neuversuch, Wartungsseite `wartung.html` (502/503/504), Karte „Selbstheilung“ mit „Als gute Version bestätigen“ und Schalter; `POST /api/system/heilung/bestaetigen/`, `POST /api/system/heilung/schalten/`; Hinweise an alle vom Server (ohne anlegenden Benutzer) | Administration › System › Wartung, Startseite Administration, Hinweis-Banner | ABGESCHLOSSEN – Lauf steht aus; auf der Test-VM zu prüfen: epm.service (systemd ≥ 253), Nginx-Wartungsseite, Healthcheck web (nc), Rückfall über systemd-run |
| 13.10.2026 | Kontoaktionen je Firma | Sperren, Entsperren, Einmal-Passwort, 2FA zurücksetzen, Aus-/Einblenden und Kontodaten (Name, Benutzername, E-Mail, Testbenutzer) ändern darf nur, wer in jeder Firma Admin ist, in der die Person eine Rolle hat (403 mit Nennung der Firma; Konten ohne Rolle irgendwo darf jeder Admin). Rollen je Firma prüft weiter jede Firma für sich. `GET /api/benutzer/` liefert `verwaltbar`; die Benutzerverwaltung sperrt die Knöpfe mit Hinweis. „Alle Testbenutzer ausblenden“ überspringt fremde (`uebersprungen`). Tests `patienten.test_firmen`, `accounts`, `epm.test_sicherheit` (93) |
| 13.10.2026 | Diagnose-Korrekturen nachvollziehbar | Kundenfrage: Jede Änderung einer Diagnose (ICD-Code, Kennzeichen, Bezeichnung, seit, beendet) steht im Verlauf der Akte mit altem und neuem Wert, Person und Zeitpunkt (`GET /api/patienten/<id>/verlauf/?bereich=diagnosen`). Im Reiter Diagnosen je Zeile „Historie“ (öffnet den Verlauf gefiltert); „Neue Diagnose“ zeigt nicht mehr die zuletzt gespeicherten Werte. Test `patienten.test_praxiswuensche.DiagnosenTest` |
| 13.10.2026 | Scans: verständliche Fehler | Kundenmeldung „Fehlermeldungen beim Anklicken“: nicht (mehr) vorhandene Scans/Seiten 404 statt 400, die Ansicht fragt danach nicht weiter nach dem Stand; Speicherordner nicht beschreibbar beim Hochladen → 503 mit Text; fehlende/beschädigte Seitenbilder bei PDF und Zuordnen → Hinweis statt 500; Vorschau- und Einstellungsfehler → 400; Patientenvorschläge stören das Öffnen nicht; `stand.dienst_laeuft` – die Ansicht erklärt, wenn der OCR-Dienst nicht läuft; Seitenbild nicht ladbar → Hinweis statt leerem Rahmen. Tests `scans.tests.FehlerpfadeTest` |
| 10.10.2026 | Vorlagen-Portal einfacher | Übersicht mit Suche, geführter Ablauf mit Live-Vorschau, Angaben per Klick, frühere Fassung wiederherstellen, als eigene Vorlage kopieren (F180). Lauf steht aus |
| 09.10.2026 | Eigene Vorlagen | „+ Neue Vorlage“ unter Vorlagen › Dokumentvorlagen: eigene Schreiben mit E-Mail anlegen, bearbeiten, deaktivieren; in der Akte wählbar (F176). Lauf steht aus |
| F179 | Systemverwaltung ohne SSH: Ampel, Reiter, kompakte Graphen, Sicherungen mehrfach löschen, Dienste, Versionen, Pakete, Zertifikat, Protokolle | Administration › Systemverwaltung, System, Backup | ABGESCHLOSSEN – Lauf steht aus |
| F188 | Notfallpaket und Wiederaufbau-Plan: alles für einen Neuaufbau ohne Internet in einer Datei, Aufbauskript, Offline-Modus der Rollout-Skripte, Ampel-Kachel | Administration › System › Notfall, Systemverwaltung, Hilfe | ABGESCHLOSSEN – Lauf steht aus |
| F181 | Akte ohne Seiten-Scrollen, kompakter Kopf, Reiter nach Bedeutung, PDF neben dem Plan, Plan nach Praxisvorgabe, PDF-Vorschau mit ungespeicherten Eingaben | Patientenakte, Infusionspläne, Plan-Editor | ABGESCHLOSSEN – Lauf steht aus |
| F187 | Hinweise aus Labor und Gewicht im Plan-Editor (ohne Dosisvorschlag) | Plan-Editor | ABGESCHLOSSEN – Lauf steht aus |
| F190 | Entscheidungen der Praxis: Tablet zwei Spalten, Mengen je kg einstellbar, Referenzbereiche nachtragen, Infoblatt ohne Telefontermine | Akte, Vorlagen › Grenzwerte und Labor, Plan-Editor | ABGESCHLOSSEN – Lauf steht aus |
| F01 | Sitzungsstatus und CSRF-Token | 1 Anmeldung | ABGESCHLOSSEN UND GETESTET |
| F02 | Anmeldung mit Benutzername und Kennwort | 1 Anmeldung | ABGESCHLOSSEN UND GETESTET |
| F03 | Zweiter Faktor bei der Anmeldung | 1 Anmeldung | ABGESCHLOSSEN UND GETESTET |
| F04 | Eigenes Kennwort setzen und ändern | 1 Anmeldung, 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F05 | Authenticator einrichten und ersetzen | 1 Anmeldung, 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F06 | Notfall-Codes neu erzeugen | 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F07 | Abmelden | alle Ansichten (Seitenleiste) | ABGESCHLOSSEN UND GETESTET |
| F08 | Wartezeit nach 5, Kontosperre nach 10 Fehlversuchen | 1 Anmeldung, 17 Benutzer, 20 Audit-Log | ABGESCHLOSSEN UND GETESTET |
| F09 | Eigenes Profil, Darstellung, Startseite (Kacheln mit Größe) und Spaltenaufteilung speichern | 14 Mein Konto, 2 Start, alle Seiten mit Spaltenteiler | ABGESCHLOSSEN UND GETESTET |
| F10 | Sicherheitsstatus im Konto | 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F11 | Angemeldete Sitzungen anzeigen und abmelden | 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F12 | Automatische Abmeldung nach 30 Minuten | alle | ABGESCHLOSSEN UND GETESTET |
| F13 | Startseite mit Kennzahlenleiste und Kacheln (S01, S03, S06–S10) | 2 Start | ABGESCHLOSSEN UND GETESTET |
| F14 | Patientenliste mit Filtern und Suche (Spalten je Bildschirmbreite, Vorschau ab 2560 px) | 3 Patientenliste | ABGESCHLOSSEN UND GETESTET |
| F15 | Doppelprüfung beim Anlegen | 12 Neuer Patient | ABGESCHLOSSEN UND GETESTET |
| F16 | Patient anlegen | 12 Neuer Patient | ABGESCHLOSSEN UND GETESTET |
| F17 | Akte lesen mit Patientenkopf | 4 Patientenakte | ABGESCHLOSSEN UND GETESTET |
| F18 | Stammdaten, Diagnose, Therapie, Empfehlung ändern | 4 Akte, 5 Diagnose und Therapie | ABGESCHLOSSEN UND GETESTET |
| F19 | Versionen je Textfeld | 5 Diagnose und Therapie | ABGESCHLOSSEN UND GETESTET |
| F20 | Akte abschließen | 4 Akte (Menü ⋯) | ABGESCHLOSSEN UND GETESTET |
| F21 | Akte wieder öffnen | 3 Liste (Abgeschlossen) | ABGESCHLOSSEN UND GETESTET |
| F22 | Verlauf je Akte | 10 Verlauf | ABGESCHLOSSEN UND GETESTET |
| F23 | Akte als PDF | 3 Liste, 4 Akte | ABGESCHLOSSEN UND GETESTET |
| F24 | Verlauf als PDF | 10 Verlauf | ABGESCHLOSSEN UND GETESTET |
| F25 | Gewicht erfassen, korrigieren, lesen | 4 Akte | ABGESCHLOSSEN UND GETESTET |
| F26 | Kontakte anlegen, lesen, durchsuchen | 6 Kontakte | ABGESCHLOSSEN UND GETESTET |
| F27 | Kontakt stornieren | 6 Kontakte | ABGESCHLOSSEN UND GETESTET |
| F28 | Kontakt mit Wiedervorlage in einem Schritt | 6 Kontakte | ABGESCHLOSSEN UND GETESTET |
| F29 | Termine anlegen, ändern, lesen | 2 Start, 4 Akte | ABGESCHLOSSEN UND GETESTET |
| F30 | Termin als erledigt markieren | 2 Start | ABGESCHLOSSEN UND GETESTET |
| F31 | Infusionspläne eines Patienten lesen | 8 Infusionspläne | ABGESCHLOSSEN UND GETESTET |
| F32 | Neuer Plan als Entwurf | 7 Neuer Infusionsplan | ABGESCHLOSSEN UND GETESTET |
| F33 | Entwurf bearbeiten | 7 Neuer Infusionsplan | ABGESCHLOSSEN UND GETESTET |
| F34 | Entwurf verwerfen | 8 Infusionspläne | ABGESCHLOSSEN UND GETESTET |
| F35 | Plan freigeben | 8 Infusionspläne | ABGESCHLOSSEN UND GETESTET |
| F36 | Vergleich mit dem Vorgänger | 8 Infusionspläne | ABGESCHLOSSEN UND GETESTET |
| F37 | Gespeicherte Plan-PDF öffnen mit SHA-256-Prüfung | 8 Infusionspläne | ABGESCHLOSSEN UND GETESTET |
| F38 | Protonenpumpenhemmer (Pantozol®/Nexium®) im Plan | 7, 8 | ABGESCHLOSSEN UND GETESTET |
| F39 | Gesamtvolumen, Laufzeit und Rate | 7, 8 | ABGESCHLOSSEN UND GETESTET |
| F40 | Dokument hochladen | 9 Dokumente | ABGESCHLOSSEN UND GETESTET |
| F41 | Dokumente lesen, Metadaten ändern, ausblenden | 9 Dokumente | ABGESCHLOSSEN UND GETESTET |
| F42 | Datei anzeigen und herunterladen | 9 Dokumente | ABGESCHLOSSEN UND GETESTET |
| F43 | Altdokumente prüfen (Typ, Datumsquelle) | 9 Dokumente, 2 Start | ABGESCHLOSSEN UND GETESTET |
| F44 | Auswahllisten pflegen | 18 Vorlagen | ABGESCHLOSSEN UND GETESTET |
| F45 | Versorger pflegen | 13 Versorger | ABGESCHLOSSEN UND GETESTET |
| F46 | Ansprechpartner pflegen | 13 Versorger | ABGESCHLOSSEN UND GETESTET |
| F47 | Präparate pflegen | 18 Vorlagen | ABGESCHLOSSEN UND GETESTET |
| F48 | Grenzwerte und Einstellungen (Kontakt bald fällig / überfällig) | 18 Vorlagen | ABGESCHLOSSEN UND GETESTET |
| F49 | Briefkopf, Absender und Logo | 18 Vorlagen | ABGESCHLOSSEN UND GETESTET |
| F50 | Dokumentvorlagen (WYSIWYG) | 19 Dokumentvorlagen | ABGESCHLOSSEN UND GETESTET |
| F51 | PDF-Erzeugung | Grundlage für F23, F24, F35, F37, F50, F55, F59 | ABGESCHLOSSEN UND GETESTET |
| F52 | Benutzer lesen, anlegen, ändern | 17 Benutzer | ABGESCHLOSSEN UND GETESTET |
| F53 | Benutzer sperren und entsperren | 17 Benutzer | ABGESCHLOSSEN UND GETESTET |
| F54 | Einmal-Kennwort erzeugen | 17 Benutzer | ABGESCHLOSSEN UND GETESTET |
| F55 | Zugangsblatt drucken | 17 Benutzer | ABGESCHLOSSEN UND GETESTET |
| F56 | 2FA zurücksetzen | 17 Benutzer | ABGESCHLOSSEN UND GETESTET |
| F57 | Testdaten zurücksetzen | 17 Benutzer | ABGESCHLOSSEN UND GETESTET |
| F58 | Audit-Log lesen und filtern | 20 Audit-Log | ABGESCHLOSSEN UND GETESTET |
| F59 | Audit-Log als PDF | 20 Audit-Log | ABGESCHLOSSEN UND GETESTET |
| F60 | Unveränderlichkeit von Verlauf, Protokoll, Kontakten, Plänen | 10 Verlauf, 20 Audit-Log | ABGESCHLOSSEN UND GETESTET |
| F61 | Tägliche verschlüsselte Sicherung | 11 Backup | ABGESCHLOSSEN UND GETESTET |
| F62 | Sicherungen anzeigen, „Jetzt sichern“ | 11 Backup, 2 Start | ABGESCHLOSSEN UND GETESTET |
| F63 | Wiederherstellen mit Admin-Kennwort und 2FA | 11 Backup | ABGESCHLOSSEN UND GETESTET |
| F64 | Übertragung zur Nextcloud/NAS mit Status | 11 Backup | ABGESCHLOSSEN UND GETESTET |
| F65 | Import der Altdaten (Werkzeug mit Oberfläche) | Administration › Import (neu) | ABGESCHLOSSEN UND GETESTET – mit erfundenem Beispiel-Dump; der echte Dump steht aus |
| F66 | Rechte je Gruppe einstellen | 17 Benutzer (Rechte) | ABGESCHLOSSEN UND GETESTET |
| F67 | Gemeinsame Ärzteliste pflegen | Ärzte (neu) | ABGESCHLOSSEN UND GETESTET |
| F68 | Ärzte eines Patienten (Rolle, Hausarzt im Kopf) | 4 Akte, 12 Neuer Patient | ABGESCHLOSSEN UND GETESTET |
| F69 | Bezugspersonen mit „Auskunft erlaubt“ | 4 Akte | ABGESCHLOSSEN UND GETESTET |
| F70 | „kein“ Katheter/Versorger, Nickelallergie als Auswahl | 4 Akte, 12 Neuer Patient, 3 Liste | ABGESCHLOSSEN UND GETESTET |
| F71 | Nicht Erlaubtes ausblenden, Rechteänderung sofort in der Oberfläche | alle Ansichten | ABGESCHLOSSEN UND GETESTET |
| F72 | Dokument dem richtigen Patienten zuordnen | 9 Dokumente, 10 Verlauf | ABGESCHLOSSEN UND GETESTET |
| F73 | Dokument endgültig löschen (Mediziner und Admin, Kennwort + 2FA + Bestätigungscode) | 9 Dokumente, 10 Verlauf | ABGESCHLOSSEN UND GETESTET |
| F74 | Aufbewahrungsfrist der Akte, Verlängerung im Einzelfall, „Abschluss prüfen“ | 4 Akte (Datenschutz), 2 Start, 18 Vorlagen | ABGESCHLOSSEN UND GETESTET |
| F75 | Erklärungen nachhalten (Datenschutzinformation, Einwilligung, Schweigepflichtentbindung), Widerruf | 4 Akte (Kopf, Datenschutz), 2 Start, 3 Liste | ABGESCHLOSSEN UND GETESTET |
| F76 | Vordrucke der Erklärungen als PDF aus Dokumentvorlagen | 4 Akte (Datenschutz), 19 Dokumentvorlagen | ABGESCHLOSSEN UND GETESTET |
| F77 | Datenschutz-Anfragen mit Frist (Art. 12 Abs. 3 DSGVO) | 4 Akte (Datenschutz), Datenschutz (neu), 2 Start | ABGESCHLOSSEN UND GETESTET |
| F78 | Kopie der Akte als ZIP (Art. 15 Abs. 3 DSGVO) | 4 Akte (Datenschutz) | ABGESCHLOSSEN UND GETESTET |
| F79 | Verarbeitung einschränken, begründete Einsicht, Aufheben (Art. 18 DSGVO) | 4 Akte, Datenschutz (neu) | ABGESCHLOSSEN UND GETESTET |
| F80 | Akte endgültig löschen mit Löschprotokoll (Art. 17 DSGVO; Mediziner und Admin, Kennwort + 2FA + Bestätigungscode) | 4 Akte (Datenschutz), Datenschutz (neu) | ABGESCHLOSSEN UND GETESTET |
| F81 | Übersicht „Datenschutz“ | Datenschutz (neu) | ABGESCHLOSSEN UND GETESTET |
| F82 | Plan nach Freigabe abschließen (Freigabe per E-Mail o. Ä.), Freigabevermerk mit beiden Personen | 8 Infusionspläne | ABGESCHLOSSEN UND GETESTET |
| F83 | Aufbewahrung des Audit-Logs, tägliche Bereinigung | 18 Vorlagen (Grenzwerte), 20 Audit-Log | ABGESCHLOSSEN UND GETESTET |
| F84 | Globaler Kalender mit Fälligkeiten (Kontakt in zwei Stufen) und Feiertagen | Kalender (neu) | ABGESCHLOSSEN UND GETESTET |
| F85 | Übersicht aller Infusionspläne | Infusionspläne (neu) | ABGESCHLOSSEN UND GETESTET |
| F86 | Systemverwaltung: Auslastung, Updates, Container, EPM-Zustand | System (neu) | ABGESCHLOSSEN UND GETESTET |
| F87 | Tätigkeiten für den Server über den Systemagenten (Update, Neustart, Sicherung, Aufräumen) | System | ABGESCHLOSSEN UND GETESTET |
| F88 | Wartung des EPM (Sitzungen, Datenbank, Dokumente, Unveränderlichkeit, Konfiguration, alle abmelden) | System | ABGESCHLOSSEN UND GETESTET |
| F89 | Hinweis an alle Benutzer, angemeldete Benutzer abmelden | System, alle Ansichten | ABGESCHLOSSEN UND GETESTET |
| F90 | Kontakt fällig in zwei Stufen „bald fällig“ und „überfällig“ (S04), Kachel „Wiedereinbestellung fällig“ | 2 Start, 3 Patientenliste, Kalender, 18 Vorlagen | ABGESCHLOSSEN UND GETESTET |
| F91 | Schnellerfassung von der Startseite: Kontakt (mit Wiedervorlage), Gewicht, Termin; Kontakt und Gewicht als zwei Anfragen (S02) | 2 Start | ABGESCHLOSSEN UND GETESTET |
| F92 | Meine Akten: Merkliste (Stern im Aktenkopf) und zuletzt geöffnet, je Person (S05) | 2 Start, 4 Akte | ABGESCHLOSSEN UND GETESTET |
| F93 | Startseite anpassen: Kacheln im festen Raster 1×1/2×1/1×2/2×2, verschieben, Größe ziehen mit Einrasten, je Person (S11, S17) | 2 Start | ABGESCHLOSSEN UND GETESTET |
| F94 | Startseite der Administration: Sicherung, Server, Updates, Konten, Angemeldet, Hinweis, Zugriffe, Testumgebung (S12–S14) | 2 Start | ABGESCHLOSSEN UND GETESTET |
| F95 | Hilfe je Rolle nach tatsächlichen Rechten, mitgeliefert + eigene Ergänzungen mit Historie (S15) | Hilfe (neu), „?“ auf jeder Seite | ABGESCHLOSSEN UND GETESTET |
| F96 | Volle Fensterbreite, Aufteilung der Seiten in Stufen 1440/1920/2560 px (S16) | alle Ansichten | ABGESCHLOSSEN UND GETESTET |
| F97 | Spaltenteiler ziehen mit Einrastpunkten ⅓, ½, ⅔, je Seite, Stufe und Person (S17); in der Akte ersetzt durch F98 | Patientenliste, Plan-Editor | ABGESCHLOSSEN UND GETESTET |
| F98 | Karten im Raster mit Menü „⋯“ (Breite, Höhe, Standardgröße) je Person – Akte Übersicht, Diagnose & Therapie, Kontakte, System | 4–6 Akte, System | ABGESCHLOSSEN UND GETESTET |
| F99 | Zwei-Faktor-Anmeldung freiwillig (Standard), Pflicht für Admins oder alle einstellbar; selbst einrichten und ausschalten; Bestätigungen immer mit Passwort und 2FA (ohne eingerichteten Faktor nicht möglich) | 1 Anmeldung, 14 Mein Konto, 17 Benutzer, alle Bestätigungen | ABGESCHLOSSEN UND GETESTET |
| F100 | Konten „ohne Login“ setzen und mit „Login geben“ wieder einbinden; Rolle „Keine Berechtigung“ ohne Rechte; Testbenutzer-Schalter | 17 Benutzer | ABGESCHLOSSEN UND GETESTET |
| F101 | Testpatient beim Anlegen wählbar (z. B. für Plantests) | 12 Neuer Patient | ABGESCHLOSSEN UND GETESTET |
| F102 | Auslastung mit wählbarem Zeitraum 1 h bis 6 Monate (Mittelwerte und Spitzen), Konten mit direktem Weg | System | ABGESCHLOSSEN UND GETESTET |
| F103 | Sicherung herunterladen, Aufbewahrung 7/14/30 Tage, heruntergeladene Sicherung hochladen und einlesen | 11 Backup | ABGESCHLOSSEN UND GETESTET |
| F104 | Admins auch bei echten Akten: Akte abschließen, Dokument anderem Patienten zuordnen | 4 Akte, 9 Dokumente | ABGESCHLOSSEN UND GETESTET |
| F106 | Recht „Testdaten sehen“ je Gruppe (Testpatienten und Testbenutzer ausblenden); Testbenutzer ausblenden/einblenden | 17 Benutzer, alle Listen | ABGESCHLOSSEN UND GETESTET |
| F105 | Hinweis „Kein Infusionsplan“; „Kein Infusionsplan nötig“ je Patient bestätigen unterdrückt ihn und die Warnung „Plan älter als …“ | 3 Patientenliste, 2 Start, 4 Akte, 8 Infusionspläne, Kalender | ABGESCHLOSSEN UND GETESTET |
| F107 | Datenbank leeren (Ende der Testphase): Akten, Dokumente, Versorger, Ärzte, nicht ausgewählte Benutzer und Audit-Log entfernen; Kontenauswahl, Bestätigungscode, Passwort + 2FA, Rückfrage, vorher Sicherung | System | ABGESCHLOSSEN UND GETESTET |
| F108 | Schalter „Musterdaten automatisch anlegen“ | System | ABGESCHLOSSEN UND GETESTET |
| F109 | Menüpunkt „Import“ nach der Übernahme aus- und wieder einblenden | System, Seitenleiste, Import | ABGESCHLOSSEN UND GETESTET |
| F110 | Infusionstage je Beutelart: PE (Mischbeutel), Zusatzvolumen, infusionsfreie Tage – mit Übernahme in den Folgeplan, Vergleich und PDF | 7 Neuer Infusionsplan | ABGESCHLOSSEN UND GETESTET |
| F111 | Präparate nach der Praxis: Zusatzvolumen (Sterofundin ISO, Ringer-Lösung, Ringer-Lactat, NaCl 0,9 %, Jonosteril), Natrovit, NutriLock/TauroLock, Hinweis am Präparat; Dipeptamin und Omegaven ausgeblendet | 18 Vorlagen › Auswahllisten | ABGESCHLOSSEN UND GETESTET |
| F112 | Katalog der Laborparameter (Gruppen, Einheit, Referenzbereich) | 18 Vorlagen › Labor und Diagnosen | ABGESCHLOSSEN UND GETESTET |
| F113 | Laborbefunde mit Maske statt Abschreiben; freie Zeilen für Tumormarker und genetische Parameter | 4 Akte › Labor & BIA | ABGESCHLOSSEN UND GETESTET |
| F114 | BIA-Messungen (Gewicht, BCM, Fettmasse, ECW, Körperwasser, BMI) mit Beurteilung; Gewicht wandert in den Verlauf | 4 Akte › Labor & BIA | ABGESCHLOSSEN UND GETESTET |
| F115 | Berichte aus der Akte: Entwurf → Freigabe, PDF als Dokument, danach unveränderlich | 4 Akte › Berichte | ABGESCHLOSSEN UND GETESTET |
| F116 | Unterlagen für die Sprechstunde: Diagnosen, Plan, BIA, Labor und Empfehlung auf einem Blatt | 4 Akte | ABGESCHLOSSEN UND GETESTET |
| F117 | Diagnosen mit ICD-Code und Zusatzkennzeichen G/V/Z/A, mitwachsende Liste im Hintergrund | 5 Diagnose & Therapie, 18 Vorlagen | ABGESCHLOSSEN UND GETESTET |
| F118 | Versichertendaten: GKV/PKV, Versicherung, Versichertennummer | 4 Akte, 12 Neuer Patient | ABGESCHLOSSEN UND GETESTET |
| F119 | Hinweise mit „×“ ausblenden – 3, 6 oder 12 Monate Ruhe oder „nicht mehr nötig“, in der Akte zurückholbar | 3 Patientenliste, 4 Akte | ABGESCHLOSSEN UND GETESTET |
| F120 | Ab wann Laborbefund und BIA-Messung als zu alt gelten (Standard 12 Monate, einstellbar) | 2 Startseite, 18 Vorlagen | ABGESCHLOSSEN UND GETESTET |
| F121 | Ein eigener Reiter je Bereich: Diagnosen, Therapie, Labor, BIA | 4 Akte | ABGESCHLOSSEN UND GETESTET |
| F122 | Ein gemeinsames Muster für die Reiter der Akte (außer Dokumente): links die Einträge mit Datum, rechts der gewählte; Knöpfe überall an derselben Stelle | 4–9 Akte | ABGESCHLOSSEN UND GETESTET |
| F123 | EPM aus der Oberfläche aktualisieren (Systemagent-Aktion `epm_update`) | 17 System | ABGESCHLOSSEN UND GETESTET |
| F124 | Ladebalken am oberen Rand bei jeder laufenden Anfrage (Laden, Speichern, Hochladen, PDF, Aufträge) | alle Seiten | ABGESCHLOSSEN (auf Wunsch ohne Testlauf eingespielt) |
| F135 | Aufbau der Patientenakte je Person: Kopfzeile in Gruppen mit ziehbarer Höhe, Seitenleiste mit ziehbarer Breite und senkrechten Reitern, Karteikarte | 4 Akte, 14 Mein Konto | ABGESCHLOSSEN (Tests geschrieben, Lauf steht aus) |
| F136 | Karteikarte: alle Einträge der Akte chronologisch mit Kürzel, Filter, Zeitraum und Kürzelzeile | 4 Akte | ABGESCHLOSSEN (Tests geschrieben, Lauf steht aus) |
| F137 | Ladebalken 5 px und in „Individuell“ in der Akzentfarbe | alle Seiten | ABGESCHLOSSEN (Lauf steht aus) |
| F138 | Fortschritt laufender Aufträge mit ungefährer Restzeit (Backup, Updates, System) | 11 Backup, 17 System | ABGESCHLOSSEN (Lauf steht aus) |
| F139 | Form „Rund“ oder „Eckig“ – am 08.10.2026 wieder entfernt (ersetzt durch F145) | – | ENTFERNT |
| F140 | Unten links nur die Person; Hilfe, Mein Konto, Abmelden im Menü | Seitenleiste | ABGESCHLOSSEN (Lauf steht aus) |
| F141 | Patientenliste ohne Vorschau der Akte; Klick auf die Zeile öffnet die Akte | 3 Patientenliste | ABGESCHLOSSEN (Lauf steht aus) |
| F142 | Kalender: „×“ an jedem Eintrag – Termine und Fälligkeiten ausblenden (3/6/12 Monate oder „nicht mehr nötig“, mit Grund) | 2 Start, 4 Akte, Kalender | ABGESCHLOSSEN (Lauf steht aus) |
| F143 | Teiler und Ränder ohne Punkte-Griff; beim Überfahren breiter und farbig | alle Seiten | ABGESCHLOSSEN (Lauf steht aus) |
| F144 | Rückmeldungen als Overlay: grün quittiert und blendet aus, rot bleibt länger | alle Seiten | ABGESCHLOSSEN (Lauf steht aus) |
| F145 | Weniger Leerraum: Rand des Seiteninhalts und Abstände zwischen den Karten verkleinert | alle Seiten | ABGESCHLOSSEN (Lauf steht aus) |
| F146 | Einheitlich und kompakt: Seitenkopf in einer Zeile, gleiche Steuerhöhen, kleinere Innenabstände, kein Springen; Suche bei Versorger | alle Seiten | ABGESCHLOSSEN (Lauf steht aus) |
| F147 | Ohne Scrollen auf 1080p: Formulare Versorger/Ärzte im 6-Spalten-Raster, Kalender füllt die Fensterhöhe, Benutzermenü bündig | Versorger, Ärzte, Kalender, Seitenleiste | ABGESCHLOSSEN (Lauf steht aus) |
| F148 | Navigation: schmale Leiste mit gleich großen, mittigen Symbolen; Leiste mit Text 224 px; Hauptknöpfe gleich breit; leere Bereiche kompakt | alle Seiten | ABGESCHLOSSEN (Lauf steht aus) |
| F149 | Akte: „Kontakt“ und „Gewicht“ öffnen einen Dialog wie „Termin“ | 4 Akte | ABGESCHLOSSEN (Lauf steht aus) |
| F150 | Ein Dialog je Sache: „Neuer Kontakt“, „+ Gewicht“ und Kürzelzeile K/G öffnen dieselben Dialoge; Wiedervorlage standardmäßig in 14 Tagen, einstellbar | 4 Akte, Vorlagen › Grenzwerte | ABGESCHLOSSEN (Lauf steht aus) |
| F151 | Weniger Wege: „Entwurf fortsetzen“ im Aktenkopf, Dokument aus dem Kopf und per Ziehen auf die Akte, Arzt/Versorger im Dialog anlegen | 4 Akte, Neuer Patient, Arzt zuordnen | ABGESCHLOSSEN (Lauf steht aus) |
| F152 | Bearbeiten sichtbar: „Bearbeiten“ auf Anschrift und Kontakt, Kalender öffnet „Termin ändern“, Karteikarte springt zum Eintrag, Therapie/Empfehlung erst lesen, Größen-Symbol statt „⋯“ | 4 Akte, Kalender | ABGESCHLOSSEN (Lauf steht aus) |
| F153 | Eine Sprache: Bearbeiten / Speichern / Abbrechen / Erledigt / Deaktivieren; Rückfrage vor Verwerfen, Beenden, Deaktivieren; roter Knopf links | Akte, Kalender, alle Dialoge | ABGESCHLOSSEN (Lauf steht aus) |
| F154 | Weniger Wege und Erklärtext: ein Suchfeld (Kopfzeile filtert die Patientenliste), „Prüfen …“ wählbar, Erklärtexte in der Hilfe | Patientenliste, Akte, Hilfe | ABGESCHLOSSEN (Lauf steht aus) |
| F155 | Tastenkürzel: K, G, T, P, Alt+Ziffer in der Akte, Strg Enter in Dialogen, ? Übersicht | 4 Akte, alle Dialoge | ABGESCHLOSSEN (Lauf steht aus) |
| F156 | Versorger/Ärzte und Kalender nach den Entwürfen (PC, Tablet, Telefon) | Versorger, Ärzte, Kalender | ABGESCHLOSSEN (Lauf steht aus) |
| F157 | Rest der Vorschläge: Stift an „Versorgung“, Messpunkt im Diagramm bearbeiten, „Neues Dokument“ | 4 Akte | ABGESCHLOSSEN (Lauf steht aus) |
| F158 | Design und Mein Konto getrennt: eigener Menüpunkt „Design“ (/design) | Benutzermenü, Design, Mein Konto | ABGESCHLOSSEN (Lauf steht aus) |
| F159 | Import: Auffälligkeiten gruppiert mit Regel je Wert, Mehrfachauswahl, Gewichte innerhalb weniger Tage zusammenfassen | Administration › Import | ABGESCHLOSSEN (Lauf steht aus) |

Summe (124 Funktionen, gezählt aus der Tabelle): 123 abgeschlossen und getestet, F124 abgeschlossen ohne Testlauf (F65 mit erfundenem Beispiel-Dump, der echte steht aus) · 0 teilweise abgeschlossen · 0 nicht abgeschlossen · 0 blockiert. (Die Summe vor Runde 7 zählte F65 noch als nicht abgeschlossen.)
Gegenüber Runde 1 ist keine Funktion zurückgestuft worden. Neu ist F66 (Rechte je Gruppe). F38 und F39 sind nach der
Klärung von U1/U2 umgesetzt, F64 ist nach der Klärung von U9 nicht mehr blockiert, aber noch nicht umgesetzt.
Neu in Runde 4 sind F74–F83 (Datenschutz nach DSGVO und Abschließen eines Plans nach Freigabe); offene Fragen dazu stehen
in `docs/DATENSCHUTZ.md` und unten als U16–U24. Runde 5 schließt die Datensicherung ab (F61–F64, dazu der Backup-Status der Startseite in F13); offen ist nur noch der Import der Altdaten (F65) und die Aufbewahrung des Audit-Logs (F83, U18). Runde 7 setzt die Startseiten- und Oberflächen-Erweiterungen S01–S17 aus `claude/startseite-erweiterungen.md` um (F90–F97, dazu erweitert F09, F13, F14, F17, F48, F84). Die Klärungen vom 03.10.2026 bringen F107–F109 (Testphase und Go-live). Die Fehlerliste vom 02.10.2026 bringt F98–F106 und ändert F03, F05, F09, F20, F31, F52, F72, F85, F86, F97 (Abschnitt P). Die Wünsche aus der Praxis vom 06.10.2026 bringen F110–F118 (Abschnitt Q) und 22 offene Fragen U39–U60; die Wünsche vom 07.10.2026 bringen F119–F123 und eine weitere offene Frage (U61).

---

## Gemeinsame Regeln aller Endpunkte

- Basis-URL `/api/`, JSON (Datei-Upload: `multipart/form-data`), Datumswerte ISO 8601, Zeitzone Europe/Berlin.
- Anmeldung über Sitzungs-Cookie `epm_sitzung`; schreibende Aufrufe senden das Cookie `epm_csrf` als Kopfzeile `X-CSRFToken`.
- „Voll angemeldet“ = Kennwort + zweiter Faktor in dieser Sitzung + kein offenes Einmal-Kennwort. Sonst **403**.
- Listen sind seitenweise: `{"count", "next", "previous", "results": [...]}`, 50 je Seite (Stammdatenlisten ohne Seiten).
- Fehlerformat: Feldfehler `{"<feld>": ["Meldung"]}`, allgemeine Fehler `{"fehler": "Meldung"}`.
- Fehlercodes: 400 Validierung · 401 falsche Anmeldedaten · 403 fehlendes Recht, unveränderlicher Datensatz oder
  Datenbank-Trigger · 404 nicht vorhanden oder außerhalb des eigenen Bereichs (Testbenutzer) · 405 Aktion nicht
  vorgesehen (z. B. Kontakt ändern) · 409 Akte abgeschlossen · 429 zu viele Versuche. Akte mit eingeschränkter
  Verarbeitung (F79): in Listen nicht enthalten, Einträge 404, `GET /api/patienten/{id}/` → 403 mit `eingeschraenkt: true`
  (nur Nummer und Zeitpunkt, kein Name).
- Testbenutzer (`ist_test`) sehen und bearbeiten nur Testpatienten.
- Rechte je Gruppe (F66): Die Administration stellt sie in der Oberfläche ein (Benutzer › Rechte), Änderungen gelten ab
  der nächsten Anfrage. Festlegungen vom 01.10.2026: Mediziner sind dem Admin gleichgestellt, ausgenommen
  Benutzerverwaltung und sehr spezifische Eingriffe (abgeschlossene Akten wieder öffnen, Sicherungen, Testdaten).
  Akten abschließen dürfen Mitarbeiter, Mediziner und Admin; Vorlagen pflegen auch Mitarbeiter und Mediziner.
  Admins dürfen alles, Patientendaten schreiben sie aber nur bei Testpatienten – echte Akten sind für sie nur
  lesbar, ein neuer Patient eines Admins wird Testpatient. Standard (✓ = erlaubt, ● = fest, nicht entziehbar,
  T = nur bei Testpatienten, fest; „nur Mediziner und Admin“ = keiner anderen Rolle zuweisbar):

| Recht | Betrachter | Mitarbeiter | Mediziner | Admin |
|---|---|---|---|---|
| Akten lesen | ✓ | ✓ | ✓ | ● |
| Kontakte, Gewichte, Termine, Dokumente erfassen | – | ✓ | ✓ | ✓ T |
| Patienten anlegen, Diagnose, Therapie, Stammdaten ändern | – | ✓ | ✓ | ✓ T |
| Infusionspläne anlegen | – | – | ✓ | ✓ T |
| Infusionspläne freigeben | – | – | ✓ | ✓ T |
| Akten abschließen | – | ✓ | ✓ | ✓ T |
| Dokumente einem anderen Patienten zuordnen (F72) | – | – | ✓ | ✓ T |
| Dokumente endgültig löschen (F73) | – | – | ✓ | ✓ (auch echte Akten; nur Mediziner und Admin) |
| Infusionspläne nach Freigabe abschließen (F82) | – | ✓ | ✓ | ✓ T |
| Datenschutz: Erklärungen und Anfragen erfassen, Kopie der Akte (F75, F77, F78) | – | ✓ | ✓ | ✓ T |
| Datenschutz: Anfragen entscheiden, Verarbeitung einschränken, Einsicht, Aufbewahrung verlängern (F74, F77, F79) | – | – | ✓ | ✓ T |
| Akten endgültig löschen (F80) | – | – | ✓ | ✓ (auch echte Akten; nur Mediziner und Admin) |
| Abgeschlossene Akten wieder öffnen | – | – | – | ✓ |
| Versorger und Ansprechpartner pflegen | – | ✓ | ✓ | ✓ |
| Vorlagen pflegen (Briefkopf, Auswahllisten, Präparate, Grenzwerte) | – | ✓ | ✓ | ✓ |
| Audit-Log lesen | – | – | ✓ | ✓ |
| Benutzer und Rechte verwalten | – | – | – | ● |
| Sicherungen verwalten | – | – | – | ✓ |
| Testdaten zurücksetzen | – | – | – | ✓ |
| Systemverwaltung (Server und EPM) | – | – | – | ✓ (für eine Urlaubsvertretung jeder Gruppe freischaltbar) |

  Testbenutzer bekommen nie Rechte, die über Testpatienten hinaus wirken (Versorger, Vorlagen, Audit-Log, Benutzer,
  Sicherungen, Testdaten, Wiederöffnen). Fehlendes Recht → 403 „Dafür fehlt das Recht „…“.“; abgelaufene Sitzung → 403
  „Anmeldedaten fehlen.“ bzw. „Anmeldung mit zweitem Faktor erforderlich.“, die Oberfläche wechselt dann zur Anmeldung.
  Admin bei einer echten Akte → 403 „Als Admin nur bei Testpatienten möglich …“. Die Oberfläche zeigt diese Meldungen nicht:
  Was jemand nicht darf, wird ausgeblendet; lehnt der Server trotzdem ab (Recht gerade entzogen), erscheint nur ein
  neutraler Hinweis (F71). Jede Antwort an angemeldete Benutzer trägt den Kopf `X-EPM-Rechte` (Kennung des Rechtestands).
- Migrationen liegen im Repo (`backend/*/migrations/`). Ändert sich ein Modell, erzeugt GitHub Actions die Migration,
  legt sie als Commit „Migrationen automatisch erzeugt (CI)“ ab und prüft danach `makemigrations --check`.
  Schutz-Trigger werden nach jedem `migrate` gesetzt (`audit/schutz.py`).
- Tests: `accounts/tests.py`, `patienten/tests.py`, `patienten/test_datenschutz.py`, `infusionen/tests.py`,
  `stammdaten/tests.py`, `vorlagen/tests.py`; gemeinsame Hilfen in
  `epm/pruefhilfen.py`.

---

## A · Anmeldung und Konto

### F01 Sitzungsstatus und CSRF-Token
- **Zweck:** Frontend erfährt beim Laden, welcher Anmeldeschritt ansteht, und erhält das CSRF-Cookie.
- **Endpunkt:** `GET /api/auth/status/`
- **Request:** –
- **Response 200:** `{"schritt": "anmelden" | "kennwort_aendern" | "2fa_einrichten" | "2fa" | "fertig", "benutzer"?: Ich}`;
  `Ich` = `{id, benutzername, anzeigename, titel, vorname, nachname, kuerzel, funktion, rolle, ist_test, darstellung,
  startseite, rechte: [Recht-Code], schreibt_nur_testpatienten: bool}` (nur bei `fertig`; Rechte siehe F66).
- **Validierung:** –
- **Tabellen:** `django_session`, `accounts_user`, `otp_totp_totpdevice`
- **Fehlerfälle:** keine (immer 200)
- **Testschritte:** Aufruf ohne Sitzung → `anmelden`; nach Kennwort → nächster Schritt; nach 2FA → `fertig` mit Benutzer.
- **Teststatus:** Backend-Test grün (`Anmeldung.test_erstanmeldung`). Browsertests grün: jeder beginnt mit `GET /api/auth/status/` (Schritt und
  CSRF-Cookie), dazu `anmeldung.spec.ts` „Anmeldung mit Passwort und Code aus der Authenticator-App, Abmelden“ und `anmeldung.spec.ts` „Erste Anmeldung: eigenes Passwort, Authenticator einrichten, Notfall-Codes“. Sitzungen liegen in PostgreSQL; die Tests mit Neustart arbeiten danach mit derselben
  Sitzung weiter.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F02 Anmeldung mit Benutzername und Kennwort
- **Zweck:** erster Anmeldeschritt.
- **Ansicht:** 1 Anmeldung
- **Endpunkt:** `POST /api/auth/anmelden/`
- **Request:** `{"benutzername": string, "kennwort": string}`
- **Response 200:** wie F01.
- **Validierung:** beide Felder Pflicht; Konto nicht gesperrt; nicht „nur historisch“; Einmal-Kennwort nicht abgelaufen.
- **Tabellen:** `accounts_user`, `accounts_sitzung`, `django_session`, `audit_systemereignis`
- **Fehlerfälle:** 400 leer · 401 falsch (Fehlversuch wird gezählt und mit Versuchsnummer protokolliert) ·
  401 `{"abgelaufen": true}` Einmal-Kennwort abgelaufen · 403 `{"gesperrt": true}` Konto gesperrt (nur bei richtigem
  Kennwort verraten) · 403 fehlendes CSRF-Token · 429 mehr als 30 Versuche je Minute
- **Testschritte:** richtige Daten → nächster Schritt; falsches Kennwort → 401 und Eintrag „Falsches Passwort (n. Versuch)“;
  abgelaufenes Einmal-Kennwort → 401 `abgelaufen`.
- **Teststatus:** Backend-Tests grün (`accounts.tests.Anmeldung.*`). Browsertests grün: `anmeldung.spec.ts` „Anmeldung mit Passwort und Code aus der Authenticator-App, Abmelden“, `anmeldung.spec.ts` „Falsches Passwort wird abgewiesen“, `admin.spec.ts` „Fünf falsche Passwörter sperren das Konto; Admin sieht den Hinweis, setzt 2FA zurück und entsperrt“ (Sperre).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F03 Zweiter Faktor bei der Anmeldung
- **Zweck:** Anmeldung mit 6-stelligem Code aus der Authenticator-App oder einem Notfall-Code abschließen.
- **Ansicht:** 1 Anmeldung
- **Endpunkt:** `POST /api/auth/2fa/`
- **Request:** `{"code": string}` (Leerzeichen erlaubt)
- **Response 200:** wie F01 mit `schritt: "fertig"`.
- **Validierung:** Code passt zu einem bestätigten TOTP-Gerät oder zu einem unverbrauchten Notfall-Code (wird verbraucht).
  Erfolg setzt den Fehlversuchszähler zurück; ein falscher Code zählt als Fehlversuch (F08).
- **Tabellen:** `otp_totp_totpdevice`, `otp_static_staticdevice`, `otp_static_statictoken`, `accounts_user`, `audit_systemereignis`
- **Fehlerfälle:** 401 nicht mit Kennwort angemeldet oder Code falsch · 429 Wartezeit beim fünften Fehlversuch der Sitzung · 403 `gesperrt` beim zehnten am Konto (Abmeldung) · 429
- **Testschritte:** Anmeldung mit Kennwort, dann Notfall-Code → `fertig`, danach 9 Codes übrig.
- **Teststatus:** Backend-Tests grün (`test_erstanmeldung`, `Sitzungen.*`). Browsertests grün: `anmeldung.spec.ts` „Anmeldung mit Passwort und Code aus der Authenticator-App, Abmelden“ (Code aus der Authenticator-App),
  Notfall-Code in `global-setup.ts` und `konto.spec.ts` „Passwort ändern, Notfall-Codes neu, neues Gerät, andere Sitzung beenden“; Neustart geprüft in `zz-neustart.spec.ts` (Anmeldung mit dem Code des neuen Geräts).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F04 Eigenes Kennwort setzen und ändern
- **Zweck:** Einmal-Kennwort beim ersten Login ersetzen; später Kennwort im Konto ändern.
- **Ansicht:** 1 Anmeldung, 14 Mein Konto
- **Endpunkt:** `POST /api/auth/kennwort/`
- **Request:** Erstanmeldung `{"neu": string}`; sonst `{"alt": string, "neu": string}`
- **Response 200:** wie F01.
- **Validierung:** mind. 12 Zeichen, nicht ähnlich zum Benutzernamen, nicht häufig, nicht nur Ziffern, ungleich dem bisherigen;
  außerhalb der Erstanmeldung nur voll angemeldet und mit richtigem alten Kennwort.
- **Logik:** setzt `kennwort_geaendert_am`, löscht die Frist des Einmal-Kennworts, beendet alle **anderen** Sitzungen; die
  eigene Sitzung bleibt (Sitzungsschlüssel wird erneuert und in `accounts_sitzung` nachgeführt).
- **Tabellen:** `accounts_user`, `accounts_sitzung`, `django_session`, `audit_systemereignis`
- **Fehlerfälle:** 400 zu schwach `{"fehler", "details": [...]}` · 400 altes Kennwort falsch · 401 nicht angemeldet · 403 ohne 2FA
- **Testschritte:** Erstanmeldung → Kennwort setzen → `2fa_einrichten`; im Konto ändern → andere Sitzung abgemeldet.
- **Teststatus:** Backend-Tests grün (`test_erstanmeldung`, `Sitzungen.test_kennwortwechsel_beendet_andere_sitzungen`). Browsertests grün:
  `anmeldung.spec.ts` „Erste Anmeldung: eigenes Passwort, Authenticator einrichten, Notfall-Codes“, `konto.spec.ts` „Passwort ändern, Notfall-Codes neu, neues Gerät, andere Sitzung beenden“ (altes Kennwort falsch → Meldung; danach geändert); Neustart geprüft in `zz-neustart.spec.ts` (Anmeldung mit dem neuen Passwort).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F05 Authenticator einrichten und ersetzen
- **Zweck:** Authenticator-App verbinden (erste Anmeldung oder neues Telefon).
- **Endpunkte:** `POST /api/auth/2fa/einrichten/` → `{"otpauth_url": string, "qr_svg": string}`;
  `POST /api/auth/2fa/bestaetigen/` `{"code": string}` → wie F01 plus `"notfallcodes": [10 × string]` (nur einmal sichtbar)
- **Validierung:** eigenes Kennwort muss gesetzt sein; ein vorhandenes Gerät darf nur ersetzen, wer voll angemeldet ist;
  Code muss zum neuen Gerät passen.
- **Tabellen:** `otp_totp_totpdevice`, `otp_static_*`, `audit_systemereignis`
- **Fehlerfälle:** 403 Einmal-Kennwort offen oder Gerät vorhanden ohne 2FA · 400 Code falsch / Einrichtung nicht gestartet
- **Testschritte:** siehe `test_erstanmeldung`; zusätzlich zu testen: Ersetzen im Konto.
- **Teststatus:** Backend-Test grün (Ersteinrichtung). Browsertests grün: `anmeldung.spec.ts` „Erste Anmeldung: eigenes Passwort, Authenticator einrichten, Notfall-Codes“ (Einrichten mit QR-Code/Schlüssel), `konto.spec.ts` „Passwort ändern, Notfall-Codes neu, neues Gerät, andere Sitzung beenden“ („Neues
  Gerät“: neuer Schlüssel, danach neue Notfall-Codes); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F06 Notfall-Codes neu erzeugen
- **Endpunkt:** `POST /api/auth/notfallcodes/` → `{"notfallcodes": [10 × string]}`
- **Zweck/Validierung:** voll angemeldet; alte Codes werden ungültig.
- **Tabellen:** `otp_static_staticdevice`, `otp_static_statictoken`, `audit_systemereignis`
- **Fehlerfälle:** 403 nicht voll angemeldet
- **Teststatus:** Browsertest grün: `konto.spec.ts` „Passwort ändern, Notfall-Codes neu, neues Gerät, andere Sitzung beenden“ (10 neue Codes, Anzeige „10 von 10 übrig“); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F07 Abmelden
- **Ansicht:** alle Ansichten (Seitenleiste)
- **Endpunkt:** `POST /api/auth/abmelden/` → `{"schritt": "anmelden"}`
- **Logik:** Sitzung wird beendet, Eintrag in `accounts_sitzung` entfernt, Abmeldung protokolliert.
- **Tabellen:** `django_session`, `accounts_sitzung`, `audit_systemereignis`
- **Teststatus:** Backend-Test grün (`Sitzungen.test_abmelden_entfernt_sitzung`). Browsertest grün: `anmeldung.spec.ts` „Anmeldung mit Passwort und Code aus der Authenticator-App, Abmelden“ (danach `auth/status` = `anmelden`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F08 Wartezeit nach 5, Kontosperre nach 10 Fehlversuchen
- **Zweck:** Schutz gegen Raten. **Beschluss (Entwurf 17, 20; geändert 17.10.2026):** Nach 5 Fehlversuchen in einer
  Sitzung (Browser) wartet diese 15 Minuten; ein anderer Browser des echten Benutzers bleibt frei. Nach 10 Fehlversuchen in
  Folge am Konto (über alle Sitzungen, ohne gelungene Anmeldung dazwischen) bleibt das Konto gesperrt, bis der Admin
  entsperrt; Audit-Log zeigt „10 falsche Passwörter in n Minuten, Konto gesperrt“ und einen Hinweis mit Link zum Benutzer.
  Gilt auch für die Django-Verwaltung (`/verwaltung/`), dort zählt auch ein richtiges Passwort mit falschem Code.
- **Ansicht:** 1 Anmeldung, 17 Benutzer, 20 Audit-Log
- **Endpunkte:** wirkt in F02/F03 und `/verwaltung/login/`; Hinweis `GET /api/benutzer/hinweise/` → `[{id, benutzername,
  anzeigename, gesperrt_am, sperrgrund, fehlversuche}]`; Entsperren über F53.
- **Logik:** Zähler in der Sitzung (`epm_fehlversuche`, Wartezeit bis `epm_gesperrt_bis`; geprüft vor Konto und Passwort,
  verrät also nichts) und Zähler `fehlversuche` je Konto (falsches Kennwort, falscher 2FA-Code, falscher Passkey); beim
  zehnten: `is_active = false`, `gesperrt_am`, `sperrgrund`, alle Sitzungen beendet, Ereignis `anmeldung_gesperrt` mit
  Anzahl und Minuten seit dem ersten gezählten Fehlversuch. Gelungene Anmeldung setzt beide Zähler zurück. Grenzen
  `EPM_LOGIN_SITZUNG_FEHLVERSUCHE = 5`, `EPM_LOGIN_SITZUNG_SPERRE_MIN = 15`, `EPM_LOGIN_MAX_FEHLVERSUCHE = 10`.
- **Tabellen:** `accounts_user` (`fehlversuche`, `gesperrt_am`, `sperrgrund`), `audit_systemereignis`
- **Fehlerfälle:** 429 `{"fehler": "Zu viele Fehlversuche. Die Anmeldung ist für 15 Minuten gesperrt …", "wartezeit": 15}` ·
  403 `{"fehler": "Das Konto ist gesperrt …", "gesperrt": true}`
- **Testschritte:** 4 × falsch → 401; 5. → 429 (auch mit richtigem Kennwort), anderer Browser kommt hinein, nach 15 Minuten
  frei; mit neuen Sitzungen weiter bis zum 10. → 403 gesperrt; richtiges und falsches Kennwort → gleiche Antwort; Admin
  entsperrt → Anmeldung klappt; Audit-Log zeigt „Falsches Passwort (3. Versuch)“ und „10 falsche Passwörter in n Minuten,
  Konto gesperrt“.
- **Teststatus:** Backend-Test grün (`Anmeldung.test_sperre_nach_fehlversuchen`). Browsertest grün: `admin.spec.ts` „Fünf falsche Passwörter sperren das Konto; Admin sieht den Hinweis, setzt 2FA zurück und entsperrt“ (Meldung an der Anmeldung, Hinweis im
  Audit-Log mit Link zum Benutzer, Entsperren); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F09 Eigenes Profil, Darstellung und Startseite speichern
- **Ansicht:** 14 Mein Konto, 2 Start („Startseite anpassen“)
- **Endpunkt:** `GET /api/auth/ich/` → `Ich` (mit `startseite: {karten, notfallhinweis_bei}` und `aufteilung`);
  `PATCH /api/auth/ich/` `{"darstellung"?: Darstellung, "startseite"?: {"karten"?: [...], "notfallhinweis_bei"?: n|null},
  "aufteilung"?: {"<seite>@<stufe>": [Anteile] | null}}`
- **Darstellung:** `schema` standard|individuell|kontrast|dunkel · `auto_dunkel` bool · `akzent`
  nachtblau|petrol|blau|gruen|orange|aubergine|schiefer|eigen + `akzent_eigen` #RRGGBB · `hintergrund`
  weissgrau|hellgrau|grau|kraeftig|blaugrau|sand|eigen + `hintergrund_eigen` · `dichte` grosszuegig|normal|kompakt|sehrkompakt ·
  `schriftgroesse` klein|normal|gross|sehrgross · `schriftstaerke` normal|kraeftig
- **Startseite (Runde 7, S11):** `karten: [{"id", "sichtbar": bool, "breite": 1|2, "hoehe": 1|2}]` in Anzeigereihenfolge;
  15 Kacheln: klinisch `termine` (2×2), `wieder` (1×2), `meine`, `gewicht`, `plaene`, `pruefen` (je 1×1), `aktiv` (2×1);
  Administration `sicherung` (2×1), `server`, `updates`, `konten`, `angemeldet`, `hinweis`, `zugriffe`, `testumgebung`
  (je 1×1). Fehlende Kacheln werden mit ihrer Standardgröße angehängt – sichtbar die klinischen für alle Rollen außer
  Admin, die der Administration nur für die Rolle Admin; unbekannte gespeicherte fallen weg. Eine leere Liste setzt auf
  den Standard zurück. Ob eine Kachel erscheint, entscheidet zusätzlich das Recht (F94). `notfallhinweis_bei`: der Hinweis
  „Nur noch n Notfall-Codes“ (S08) ist bei dieser Anzahl ausgeblendet und kommt wieder, sobald weniger übrig sind.
- **Spaltenaufteilung (Runde 7, S17, F97):** `aufteilung` je Seite und Fensterstufe – Seiten `patientenliste`,
  `akte_uebersicht`, `akte_kontakte`, `plan_editor`; Stufen `hd` (ab 1440 px), `fhd` (ab 1920 px), `qhd` (ab 2560 px);
  Werte = Positionen der Teiler von links (0–1, ein oder zwei); `null` entfernt den Eintrag (Standard). Andere Einträge
  bleiben beim PATCH erhalten.
- **Validierung:** unbekannte Schlüssel → 400; eigene Akzentfarbe braucht Kontrast ≥ 4,5:1 zu Weiß oder zur Schrift #1B1932;
  eigene Hintergrundfarbe muss hell genug sein (Leuchtdichte ≥ 0,6); Karten nur einmal; Größe nur 1 oder 2; Aufteilung:
  nur bekannte Seiten und Stufen, Teiler aufsteigend, jede Spalte mindestens 15 % breit.
- **Tabellen:** `accounts_user` (`darstellung`, `startseite`, `aufteilung` – neu, Migration `accounts/0004_user_aufteilung`)
- **Fehlerfälle:** 400 `{"<schlüssel>": [...]}`
- **Teststatus:** Backend-Tests grün (`MeinKonto.*`, `test_startseite.KachelnUndTeiler.*`). Browsertests grün: `konto.spec.ts` „Darstellung wählen, eigene Farben prüfen, nach Neuladen erhalten, zurücksetzen“, `start.spec.ts` „Startseite anpassen: ausblenden, verschieben und Größe per Tastatur, Maus und Knopf – je Person gespeichert“, `oberflaeche.spec.ts` „Volle Breite in Stufen: 1920 px mit Spaltenteiler …“; Neustart geprüft in `zz-neustart.spec.ts` (Darstellung „Dunkel“, ausgeblendete Kachel, Kachel „Auffällige Gewichte“ 2×2, Spaltenteiler der Akte auf ⅓ –
  alles vor dem Neustart in der Oberfläche gewählt).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F10 Sicherheitsstatus im Konto
- **Zweck:** „Passwort zuletzt geändert“, „Authenticator eingerichtet am“, „8 von 10 Notfall-Codes übrig“.
- **Ansicht:** 14 Mein Konto
- **Endpunkt:** `GET /api/auth/sicherheit/` → `{"kennwort_geaendert_am", "authenticator_aktiv", "authenticator_eingerichtet_am",
  "notfallcodes_uebrig", "notfallcodes_gesamt"}`
- **Validierung:** voll angemeldet.
- **Tabellen:** `accounts_user` (`kennwort_geaendert_am`), `otp_totp_totpdevice`, `otp_static_statictoken`, `audit_systemereignis`
  (Zeitpunkt der Einrichtung)
- **Fehlerfälle:** 403 nicht voll angemeldet
- **Teststatus:** Backend-Test grün (in `test_erstanmeldung`). Browsertest grün: `konto.spec.ts` „Passwort ändern, Notfall-Codes neu, neues Gerät, andere Sitzung beenden“ („zuletzt geändert“, „x von 10 übrig“, Authenticator
  „aktiv“); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F11 Angemeldete Sitzungen anzeigen und abmelden
- **Zweck:** Liste „Dieser PC · Firefox jetzt“, „Praxis-PC 2 · Edge, zuletzt …“, einzeln abmelden.
- **Ansicht:** 14 Mein Konto
- **Endpunkte:** `GET /api/sitzungen/` → `[{"id", "browser", "ip", "angemeldet_am", "zuletzt_am", "diese": bool}]`;
  `DELETE /api/sitzungen/{id}/` → 204
- **Logik:** Eintrag bei jeder Anmeldung (Signal), „zuletzt aktiv“ höchstens minütlich aktualisiert (Middleware), abgelaufene
  Sitzungen werden beim Lesen entfernt; Sperre, neues Einmal-Kennwort und 2FA-Zurücksetzen beenden alle Sitzungen.
- **Validierung:** nur eigene Sitzungen; die eigene wird über „Abmelden“ beendet.
- **Tabellen:** `accounts_sitzung` (neu), `django_session`
- **Fehlerfälle:** 400 eigene Sitzung · 404 fremde oder abgelaufene Sitzung
- **Testschritte:** zwei Anmeldungen → zwei Einträge, einer `diese`; fremde beenden → dort 403; abgelaufene verschwinden.
- **Teststatus:** Backend-Tests grün (`Sitzungen.*`). Browsertest grün: `konto.spec.ts` „Passwort ändern, Notfall-Codes neu, neues Gerät, andere Sitzung beenden“ (zweite Anmeldung erscheint als anderes Gerät, wird beendet,
  dort danach `anmelden`). Angezeigt werden Browser und IP-Adresse – das reicht (U8 geklärt 01.10.2026).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F12 Automatische Abmeldung nach 30 Minuten
- **Umsetzung:** `SESSION_COOKIE_AGE` = 30 min, bei jeder Anfrage verlängert (`EPM_SITZUNG_MINUTEN`). Die Oberfläche prüft
  bei jedem 401/403 den Anmeldestatus und wechselt zur Anmeldung, wenn die Sitzung nicht mehr gilt.
- **Teststatus:** Backend-Test grün (`Sitzungen.test_sitzung_laeuft_nach_30_minuten_ab`: 30 Minuten, jede Anfrage verlängert). Browsertest grün:
  `anmeldung.spec.ts` „Abgelaufene Sitzung führt zurück zur Anmeldung“ (Sitzung in der Datenbank abgelaufen → nächste Anfrage 403 → Anmeldeseite).
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## B · Startseite

### F13 Startseite
- **Ansicht:** 2 Start (Runde 7: Kennzahlenleiste und Kacheln im festen Raster, Entwurf 2 „Startseite – Erweiterungen“)
- **Endpunkt:** `GET /api/startseite/`
- **Response 200:** `{"termine": {"ueberfaellig", "heute", "naechste_7_tage": [Termin] (heute bis heute + 6)}, "woche": [{datum,
  anzahl, praxistermine, feiertag}] (S03, 7 Tage ab heute, Feiertage aus F84), "gewichtswarnungen": [{patient, name, nummer, gewicht,
  prozent, verlauf: [{am, kg}]}] (stärkster Verlust zuerst; Verlauf = Messungen der letzten 6 Monate mit echten Zeitabständen,
  S06), "gewicht_schwelle": {prozent, monate}, "infusionsplaene": {"entwuerfe", "aelter_als_grenze": [{id, patient, name,
  gueltig_ab, status, erstellt_am, erstellt_von, freigegeben_am}], "grenze_monate", "anzahl_entwuerfe", "anzahl_aelter"} (S07),
  "pruefen": {altdokumente, altdokumente_gesamt (S09 Fortschritt), nickelallergie_unbekannt, kein_versorger, kein_kontakt
  (beide Stufen), kontakt_bald, kontakt_ueberfaellig, kontakt_bald_monate, kontakt_ueberfaellig_monate, kontakt_monate
  (= bald, für ältere Oberflächen), erklaerungen_fehlen, abschluss_pruefen, abschluss_monate, datenschutz_anfragen,
  datenschutz_ueberfaellig (F74, F75, F77 – Anfragen zählen auch für abgeschlossene Akten; ohne Datenschutz-Recht 0)},
  "wiedereinbestellung": siehe F90, "zuletzt_eingetragen": [{bereich (kontakt|gewicht|dokument|plan|termin), bezeichnung,
  objekt_id, patient, name, zeitpunkt, person, person_id}], "zuletzt_von_mir": [… nur eigene Einträge] (S10),
  "zahlen": {in_betreuung, mit_offenem_termin, termine_7_tage, praxistermine_7_tage, termine_ueberfaellig,
  kontakt_ueberfaellig, kontakt_bald} (S01), "notfallcodes": {uebrig, gesamt, eingerichtet, warnen_ab} (S08, F10), "sicherung":
  {zustand (ok|warnung|fehler|unbekannt), letzte_am, verschluesselt, titel, hinweise} (O-07, für alle; ohne Zugangsdaten)}`
- **Oberfläche (Runde 7):** Kennzahlenleiste „In Betreuung“, „Mit offenem Termin“, „Termine in 7 Tagen“, „Kontakt fällig“
  (überfällig + bald), „Termine überfällig“ (SU8: Datensicherung nicht in der Leiste, sie steht als Chip in der Kopfzeile).
  Kacheln: „Termine und Wiedervorlagen“ mit Wochenstreifen (Tag anklicken filtert), „Wiedereinbestellung fällig“ (F90),
  „Meine Akten“ (F92), „Auffällige Gewichte“ mit Mini-Verlauf, „Infusionspläne“ gruppiert „Zur Freigabe“/„Älter als n Mon.“
  mit Link zur Übersicht (F85), „Nach und nach prüfen“ mit Fortschritt der Altdokumente, „Zuletzt eingetragen“ mit „Alle“/
  „Von mir“. Passt ein Inhalt nicht in die Kachel, scrollt sie in sich bzw. zeigt „Alle anzeigen“. Hinweis „Nur noch n
  Notfall-Codes übrig“ (ab 3 oder weniger, ausblendbar), Kopfknöpfe „Kontakt erfassen“, „Gewicht“, „Termin“ (F91).
- **Korrektur (Runde 7):** `mit_offenem_termin` zählte auch Akten ganz ohne Termin (LEFT JOIN); jetzt nur Akten mit
  mindestens einem offenen Termin.
- **Validierung:** Testbenutzer sieht nur Testpatienten; Testpatienten fehlen in Zahlen (auch in allen Kennzahlen der
  Leiste, Runde 7) und Prüfliste; die Kacheln zeigen sie mit dem Hinweis „Test“.
- **Tabellen:** `patienten_*` (+ Historie), `infusionen_infusionsplan`, `stammdaten_einstellungen`
- **Kopfzeile:** Chip „Backup heute 02:00 erfolgreich“ bzw. der wichtigste Hinweis (z. B. „Backup unverschlüsselt“); mit dem Recht „Sicherungen verwalten“ ein Link zu Administration › Backup (F62).
- **Teststatus:** Backend-Tests grün (`Patientenliste.test_startseite`, `test_pruefen_filter`, `Musterdaten.*`, `test_startseite.Startseite.*`). Browsertests grün: `start.spec.ts` „Startseite zeigt Kennzahlen und alle Kacheln im Raster“,
  `start.spec.ts` „Termin von der Startseite anlegen und als erledigt abhaken“ (mit Neustart), `start.spec.ts` „Startseite anpassen: ausblenden, verschieben und Größe …“; Backup-Status: Backend-Test `system.test_sicherung.Uebersicht.test_zustand_fuer_die_startseite`, Browsertest `zzz-sicherung.spec.ts` (Mitarbeiter sieht „Backup heute … erfolgreich“ ohne Link, Admin mit Link zur Seite).
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## C · Patienten und Akte

### F14 Patientenliste mit Filtern und Suche
- **Ansicht:** 3 Patientenliste
- **Endpunkte:** `GET /api/patienten/`, `GET /api/patienten/zaehler/` → `{in_betreuung, abgeschlossen, mit_hinweisen,
  gewichtsverlust, termin_woche}` (ohne Testpatienten)
- **Query:** `status=in_betreuung|abgeschlossen`, `schnellfilter=hinweise|gewichtsverlust|termin_woche`, `suche` (Wörter;
  Datum TT.MM.JJJJ oder JJJJ-MM-TT = Geburtsdatum, Ziffern = Nummer, sonst Name/Vorname/Ort), `pruefen=altdokumente|
  nickelallergie|kein_versorger|kein_kontakt|kontakt_bald|kontakt_ueberfaellig|wiedereinbestellung|erklaerungen|abschluss_pruefen`
  (F74, F75, F90), `versorger`, `ansprechpartner`, `katheter`, `nickelallergie`, `test=nur|ohne`,
  `ordering=letzter_kontakt|nachname|nummer|geburtsdatum|geaendert_am` (Standard: letzter Kontakt, neueste zuerst, ohne Kontakt am Ende)
- **Response 200:** Seite mit `[{id, nummer, nachname, vorname, geburtsdatum, alter, ort, katheter, katheter_name, versorger,
  versorger_name, ansprechpartner, ansprechpartner_name, nickelallergie, ist_abgeschlossen, abgeschlossen_am,
  abschluss_anlass, ist_test, kennzahlen: {gewicht {kg, am}, trend {richtung down|up|flat, prozent, warnung},
  letzter_kontakt, termin_woche, kontakt_stufe (bald|ueberfaellig|null), naechster_termin {id, art, faellig_am, uhrzeit, titel},
  plan {gueltig_ab, alt, entwurf}, erklaerungen_fehlen [Art], hinweise: [{art: gewicht|plan|versorger|kontakt, text, stufe?}]}}]`
- **Logik:** Trend gegen die Messung, die den eingestellten Zeitraum zurückliegt; Pfeil „gleich“ bei weniger als ±1 %
  (Zwischenlösung, siehe U11); Hinweise „Gewicht −8,6 % in 3 Mon.“, „Plan älter als 12 Mon.“, „Kein Versorger“,
  „Kontakt bald fällig (über 4 Mon.)“ / „Kontakt überfällig (über 6 Mon.)“ / „Noch kein Kontakt erfasst“ (Monate aus den
  Einstellungen, U4, F90).
- **Oberfläche (Runde 7, S16/F96):** Spalten je Fensterstufe – unter 1440 px Nr., Name mit Geburtsdatum, Letzter Kontakt,
  Nächster Termin, Hinweise; ab 1440 px zusätzlich Geboren (sortierbar), Katheter, Versorger, Gewicht mit Trend; ab 1920 px
  Plan und Erklärungen; ab 2560 px rechts eine Vorschau der gewählten Akte (Kopfdaten, Hinweise, letzte Kontakte; Zeile
  anklicken oder „Vorschau: Name“), getrennt durch einen Spaltenteiler (F97, Standard ⅔ | ⅓). Hinweis-Chips „Kontakt“ in
  Gelb (bald fällig) bzw. Rot (überfällig).
- **Tabellen:** `patienten_patient`, `patienten_gewichtsmessung`, `patienten_kontakt`, `patienten_termin`,
  `infusionen_infusionsplan`, `stammdaten_einstellungen`
- **Teststatus:** Backend-Tests grün (`Patientenliste.*`, `test_testbenutzer_sieht_nur_testpatienten`, `Patientenliste.test_kontakt_faellig_in_zwei_stufen`). Browsertests grün: `oberflaeche.spec.ts` „Volle Breite in Stufen: 1280 px“ und „… 2560 px mit Vorschau in der Patientenliste …“, `patienten.spec.ts` „Patientenliste: Filter, Schnellfilter, Sortierung, abgeschlossene Akten“ (Freitext,
  Versorger, Ansprechpartner, Schnellfilter, Sortierung, abgeschlossene Akten, Zahl ohne Testpatienten), `patienten.spec.ts` „Betrachter sieht die Liste, aber keinen Knopf „Neuer Patient““, `patienten.spec.ts` „Testzugang: Hinweis dauerhaft sichtbar, nur Testpatienten, neue Patienten werden Testpatienten“, `patienten.spec.ts` „Suche in der Kopfzeile (Strg K) nach Name, Nummer und Geburtsdatum“;
  Neustart geprüft in `zz-neustart.spec.ts` (Suche nach dem neuen Patienten).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F15 Doppelprüfung beim Anlegen
- **Endpunkt:** `GET /api/patienten/doppelte/?geburtsdatum=JJJJ-MM-TT&nachname=&vorname=` → bis zu 10 Einträge wie F14
- **Regel:** gleiches Geburtsdatum und Nach- oder Vorname beginnt mit denselben 3 Buchstaben.
- **Teststatus:** Backend-Test grün (`test_doppelte`). Browsertest grün: `patienten.spec.ts` „Neuer Patient: Prüfung, Doppelung, Anlegen mit Gewicht bei Aufnahme“ (Hinweis auf Musterfrau, Erika; „Nein, andere Person“).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F16 Patient anlegen
- **Ansicht:** 12 Neuer Patient
- **Endpunkte:** `POST /api/patienten/`; `GET /api/patienten/naechste-nummer/` → `{"nummer"}` („Nr. 0300 wird automatisch vergeben“)
- **Request:** Pflicht `nachname`, `vorname`, `geburtsdatum`; optional `geschlecht (w|m|d|"")`, `strasse`, `plz`, `ort`, `telefon`,
  `email`, `hausarzt`, `ueberweisung_durch`, `groesse_cm`, `katheter`, `versorger`, `ansprechpartner`,
  `nickelallergie (ja|nein|unbekannt)`, `diagnose` (formatiert), `aufnahme_gewicht_kg`, `aufnahme_gemessen_am`,
  `aufnahme_quelle` (nur beim Anlegen), `telefon2`, `krankenkasse` (seit 03.10.2026 in Neuer Patient, Stammdaten bearbeiten und
  der Karte „Anschrift und Kontakt“, U5); `bemerkung` (formatiert) als eigene Karte unter Diagnose & Therapie mit Versionen
  (`GET /api/patienten/{id}/versionen/?feld=bemerkung`, Verlauf-Bereich „Bemerkung“).
- **Response 201:** Akte wie F17; `nummer` automatisch fortlaufend, Testpatienten ab 9001.
- **Logik:** Patient und Aufnahmegewicht (als erste Gewichtsmessung, erfasst von der anlegenden Person) in einer Transaktion.
- **Validierung:** Geburtsdatum nicht in der Zukunft; Größe und Aufnahmegewicht in den Grenzen der Einstellungen;
  Ansprechpartner gehört zum Versorger; Katheter aus Liste „Katheter“; Aufnahmegewicht beim Ändern → 400.
- **Tabellen:** `patienten_patient`, `patienten_gewichtsmessung` (+ Historie)
- **Fehlerfälle:** 400 Pflichtfeld/Plausibilität (dann wird nichts gespeichert) · 403 ohne Recht „Patienten anlegen, Diagnose, Therapie, Stammdaten ändern“; ein
  Admin legt automatisch einen Testpatienten an (`naechste-nummer` meldet `testpatient: true`)
- **Teststatus:** Backend-Tests grün (`test_schreibrechte`, `test_nummern`, `test_anlegen_mit_aufnahmegewicht`, `test_versionen_der_textfelder` mit Bemerkung, Krankenkasse, Telefon 2). Browsertests grün: `patienten.spec.ts` „Neuer Patient: Prüfung, Doppelung, Anlegen mit Gewicht bei Aufnahme“; `akte.spec.ts` „Stammdaten bearbeiten …“ (Telefon 2, Krankenkasse) und „Diagnose und Therapie bearbeiten …“ (Bemerkung mit Version und Verlauf)
  (Pflichtfelder in der Oberfläche, Größe vom Backend abgewiesen, Anlegen mit Aufnahmegewicht und Überweisung, Versorger
  aus dem Formular neu anlegen), `admin.spec.ts` „Admin: echte Akten nur lesen, Testpatienten anlegen und bearbeiten“ (Admin legt Testpatienten an), `patienten.spec.ts` „Testzugang: Hinweis dauerhaft sichtbar, nur Testpatienten, neue Patienten werden Testpatienten“ (Testzugang: Nummer ab 9001); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F17 Akte lesen mit Patientenkopf
- **Ansicht:** 4 Patientenakte
- **Endpunkt:** `GET /api/patienten/{id}/`
- **Response 200:** alle Felder aus F16 plus `abgeschlossen_am`, `abschluss_anlass`, `abschluss_notiz`, `ist_abgeschlossen`,
  `ist_test`, `angelegt_am`, `angelegt_von_name`, `geaendert_am`, `kopf: {gewicht {kg, am}, gewichtstrend {prozent, von, bis,
  tage, warnung, vergleich_kg, aktuell_kg}, bmi, katheter, versorger, ansprechpartner, ansprechpartner_telefon,
  nickelallergie, aktueller_plan {id, gueltig_ab, kcal, laufzeit_h}, naechster_termin {id, art, titel, faellig_am, uhrzeit,
  ort, bei}, versionen {diagnose|therapie|empfehlung: {version, zeitpunkt, person}}, zaehler {kontakte, gewichte, dokumente,
  termine_offen, infusionsplaene}, letzter_kontakt (Runde 7, für den Kontextkasten der Schnellerfassung F91), gemerkt (bool,
  Stern „Merken“ im Aktenkopf, F92)}`
- **Fehlerfälle:** 404 unbekannt oder außerhalb des Bereichs
- **Teststatus:** Backend-Tests grün (`test_versionen_der_textfelder`, `test_termin_mit_ort`, `Infusionsplaene.test_ablauf`). Browsertests grün:
  `akte.spec.ts` „Akte aus der Liste öffnen: Kopf mit Kerndaten und Gewichtswarnung“, `layout.spec.ts` „Unter 1280 px stehen die Karten der Akte untereinander“,
  `akte.spec.ts` „Ärzte aus der gemeinsamen Liste zuordnen, Bezugspersonen mit Auskunft pflegen“ (Kopfhöhe bleibt mit Personen gleich;
  „Auskunft an“ führt zur Person).
- **Oberfläche (Runde 7, S16/F96):** Übersicht unter 1440 px untereinander, ab 1440 px zwei Spalten ½ | ½ mit Teiler, ab
  1920 px ⅔ | ⅓ mit zweispaltigem Inhalt links, ab 2560 px Gewichtsdiagramm standardmäßig über 3 Jahre. Kontakte ab 1440 px
  ⅗ | ⅖ mit Teiler, ab 1920 px ⅔ | ⅓ mit Terminen, ab 2560 px fest ½ | ¼ | ¼ (Kontakte, Erreichbarkeit mit Terminen, Verlauf kurz).
- **Oberfläche (02.10.2026):** Kennzahlen im festen Raster (2 Zeilen à 5, schmaler 3 bzw. 2 Spalten), je eine Zeile, Langes
  gekürzt mit vollem Text im Tooltip – mehr Ärzte oder Personen verändern die Höhe nicht. „Auskunft an“: Klick springt zur
  Bezugsperson mit Anschrift und Kontaktdaten und hebt sie kurz hervor.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F18 Stammdaten, Diagnose, Therapie, Empfehlung ändern
- **Ansicht:** 4 Akte, 5 Diagnose und Therapie
- **Endpunkt:** `PATCH /api/patienten/{id}/`
- **Validierung:** wie F16; Texte werden auf erlaubte Formatierung bereinigt (`epm/sanitize.py`); Akte darf nicht abgeschlossen sein.
- **Tabellen:** `patienten_patient`, `patienten_historicalpatient`
- **Fehlerfälle:** 400 · 403 ohne Recht · 409 Akte abgeschlossen
- **Teststatus:** Backend-Tests grün (`test_verlauf_nach_bereichen`, `test_versionen_der_textfelder`, `test_abgeschlossene_akte_ist_gesperrt`).
  Browsertests grün: `akte.spec.ts` „Diagnose und Therapie bearbeiten, Versionen ansehen“, `akte.spec.ts` „Stammdaten bearbeiten, Akte abschließen (Mitarbeiter) und wieder öffnen (Admin)“; Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F19 Versionen je Textfeld
- **Zweck:** „Version 12 · geändert 12.08.2026, 15:12 von Dr. M. Berger · Versionen“ für Diagnose, Empfehlung, Therapie.
- **Ansicht:** 5 Diagnose und Therapie
- **Endpunkt:** `GET /api/patienten/{id}/versionen/?feld=diagnose|therapie|empfehlung` →
  `{"feld", "version": n, "fassungen": [{"version", "zeitpunkt", "person", "text"}]}` (neueste zuerst); Kopfangaben in F17.
- **Logik:** jede tatsächliche Änderung des Feldes in der Historie ist eine Fassung.
- **Tabellen:** `patienten_historicalpatient`
- **Fehlerfälle:** 400 anderes Feld · 404
- **Teststatus:** Backend-Test grün (`test_versionen_der_textfelder`). Browsertest grün: `akte.spec.ts` „Diagnose und Therapie bearbeiten, Versionen ansehen“; Neustart geprüft in `zz-neustart.spec.ts` („Version 2“).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F20 Akte abschließen
- **Ansicht:** 4 Akte (Menü ⋯)
- **Endpunkt:** `POST /api/patienten/{id}/abschliessen/` `{"anlass": "verstorben"|"therapie_beendet"|"betreuung_gewechselt",
  "datum"?: Datum, "notiz"?: string}` → Akte wie F17
- **Validierung:** Recht „Akten abschließen“ (Standard: Mitarbeiter, Mediziner, Admin – Admin nur bei Testpatienten); Anlass Pflicht; Datum gültig und nicht in der Zukunft;
  Akte noch offen.
- **Tabellen:** `patienten_patient`, `audit_systemereignis` („Akte Name, Vorname (Nr. 0077) abgeschlossen, Anlass: …“)
- **Fehlerfälle:** 400 Anlass/Datum · 403 ohne Recht · 409 bereits abgeschlossen
- **Teststatus:** Backend-Tests grün (`test_abschliessen_mit_recht`, `test_abgeschlossene_akte_ist_gesperrt`,
  `test_admin_schreibt_nur_bei_testpatienten`). Browsertests grün: `akte.spec.ts` „Stammdaten bearbeiten, Akte abschließen (Mitarbeiter) und wieder öffnen (Admin)“ (Betrachter ohne Menüpunkt, Mitarbeiter schließt ab,
  Akte danach nur lesbar und unter „Abgeschlossen“), `admin.spec.ts` „Admin: echte Akten nur lesen, Testpatienten anlegen und bearbeiten“; Neustart geprüft in `zz-neustart.spec.ts` (Verlauf).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F21 Akte wieder öffnen
- **Endpunkt:** `POST /api/patienten/{id}/wieder-oeffnen/` `{"grund": string}` → Akte
- **Validierung:** Recht „Abgeschlossene Akten wieder öffnen“ (Standard: Admin); Grund Pflicht; Akte muss abgeschlossen sein. Grund steht in der Historie.
- **Fehlerfälle:** 400 · 403
- **Teststatus:** Backend-Tests grün (`test_abgeschlossene_akte_ist_gesperrt`, `test_admin_schreibt_nur_bei_testpatienten`). Browsertest grün:
  `akte.spec.ts` „Stammdaten bearbeiten, Akte abschließen (Mitarbeiter) und wieder öffnen (Admin)“ (Admin öffnet eine echte Akte mit Grund wieder, danach für ihn wieder nur lesbar); Neustart geprüft in `zz-neustart.spec.ts` (Verlauf „wieder geöffnet“).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F22 Verlauf je Akte
- **Ansicht:** 10 Verlauf
- **Endpunkt:** `GET /api/patienten/{id}/verlauf/?bereich=stammdaten|diagnose|therapie|empfehlung|gewichte|kontakte|termine|
  dokumente|infusionsplaene&person=<id>` → `[{bereich, aktion, objekt_id, art (angelegt|geändert|gelöscht), zeitpunkt, person,
  person_id, grund, aenderungen: [{feld, alt, neu}]}]`
- **Logik:** Änderungen an der Akte werden nach Feld auf Stammdaten, Diagnose, Therapie und Empfehlung verteilt; `aktion`:
  angelegt, geändert, hochgeladen, storniert, erledigt, freigegeben, abgelöst, abgeschlossen, wieder geöffnet.
- **Tabellen:** alle `*_historical*`
- **Teststatus:** Backend-Test grün (`test_verlauf_nach_bereichen`). Browsertest grün: `dokumente.spec.ts` „Dokumente hochladen, Typ am Inhalt prüfen, Metadaten ändern, ausblenden, herunterladen; Verlauf“ (Bereich, Person, Änderung mit alt/neu); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F23 Akte als PDF / F24 Verlauf als PDF
- **Ansicht:** 4 Akte (Menü ⋯ „Akte als PDF“), 10 Verlauf („Als PDF“, mit dem gewählten Bereichsfilter); Anzeige im EPM-eigenen
  PDF-Leser (pdf.js) mit „Herunterladen“.
- **Endpunkte:** `GET /api/patienten/{id}/pdf/` → Patientendatenblatt mit der aktiven Vorlage (auch abgeschlossene Akten, Lesen
  genügt); `GET /api/patienten/{id}/verlauf/pdf/?bereich=…&person=` → Verlauf als Tabelle (Zeitpunkt, Person, Bereich, Aktion,
  Änderungen alt → neu). Beide `application/pdf`; jeder Export steht im Audit-Log (Art `export`, „Akte … als PDF exportiert“).
- **Logik:** Kopf und Fuß kommen aus der aktiven Vorlage „Patientendatenblatt“ (`vorlagen/listen.py`); Testpatienten mit Wasserzeichen
  „TESTDATEN“.
- **Teststatus:** Backend-Test grün (`vorlagen.WeiterePdfs.test_akte_und_verlauf_als_pdf`: Inhalt per `pdftotext`, Export im
  Audit-Log). Browsertests grün: `akte.spec.ts` „Stammdaten bearbeiten, Akte abschließen (Mitarbeiter) und wieder öffnen (Admin)“
  (Betrachter öffnet die Akte als PDF), `pdf-ausgaben.spec.ts` „Verlauf der Akte als PDF, mit Bereichsfilter“ (Lauf 36921980921, Commit `ca9f858`).
- **Status:** ABGESCHLOSSEN UND GETESTET (beide)

---

## D · Gewicht, Kontakte, Termine

### F25 Gewicht erfassen, korrigieren, lesen
- **Ansicht:** 4 Akte
- **Endpunkte:** `GET /api/gewichte/?patient=<id>`, `POST /api/gewichte/`, `PATCH /api/gewichte/{id}/`
- **Request:** `{"patient", "gewicht_kg", "gemessen_am"?, "datum_ungenau"?, "quelle": "telefonisch"|"ambulanz"|"versorger"|"arztbrief"|"altsystem", "notiz"?}`
- **Response:** `{id, patient, gewicht_kg, gemessen_am, datum_ungenau, quelle, notiz, erfasst_am, erfasst_von_name}`
- **Validierung:** Gewicht in den Grenzen der Einstellungen (Standard 20–250 kg); Datum nicht in der Zukunft; Patient im Bereich;
  Akte offen; Patient nicht änderbar.
- **Tabellen:** `patienten_gewichtsmessung`, `patienten_historicalgewichtsmessung`
- **Fehlerfälle:** 400 · 403 · 409
- **Teststatus:** Backend-Tests grün (`test_plausibilitaet_gewicht`, `test_gewichtswarnung`, `test_anlegen_mit_aufnahmegewicht`). Browsertests grün:
  `akte.spec.ts` „Gewicht erfassen, Plausibilität, korrigieren, Zeitraum“ (auch Diagramm mit echten Zeitabständen und Glättung), `akte.spec.ts` „Akte aus der Liste öffnen: Kopf mit Kerndaten und Gewichtswarnung“ (Warnung); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F26 Kontakte anlegen, lesen, durchsuchen
- **Ansicht:** 6 Kontakte
- **Endpunkte:** `GET /api/kontakte/?patient=<id>&search=<text>`, `POST /api/kontakte/`; `PATCH`/`DELETE` → 405
- **Request:** `{"patient", "text" (formatiert, Pflicht), "zeitpunkt"?, "art"? (Kontaktart aus der Liste „Kontaktart“), "wiedervorlage"?}` – Kontaktart seit 03.10.2026 in Kontakte, Schnellerfassung, Kontaktliste, Übersicht und Vorschau der Patientenliste (U6); Liste unter Vorlagen › Auswahllisten › „Kontaktarten“
- **Response:** `{id, patient, zeitpunkt, art, art_name, text, erfasst_am, erfasst_von_name, storniert_am, storniert_von_name,
  storno_grund, termine: [{id, art, faellig_am, uhrzeit, ort, erledigt}]}`
- **Validierung:** Text bereinigt; Zeitpunkt nicht in der Zukunft; Akte offen. Unveränderlich: Modell + Datenbank-Trigger.
- **Tabellen:** `patienten_kontakt`, `patienten_historicalkontakt`
- **Teststatus:** Backend-Tests grün (`KontaktRegeln.*`, `test_kontaktart`). Browsertest grün: `akte.spec.ts` „Kontakt mit Wiedervorlage erfassen, suchen, stornieren“ (mit Kontaktart, mit Neustart); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F27 Kontakt stornieren
- **Endpunkt:** `POST /api/kontakte/{id}/storno/` `{"grund": string}` → Kontakt
- **Validierung:** Grund Pflicht; nur einmal; Akte offen. Trigger erlaubt nur die Storno-Felder.
- **Fehlerfälle:** 400 · 403 · 409
- **Teststatus:** Backend-Test grün (`test_storno_genau_einmal`). Browsertest grün: `akte.spec.ts` „Kontakt mit Wiedervorlage erfassen, suchen, stornieren“ (Grund Pflicht, danach kein Storno-Knopf); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F28 Kontakt mit Wiedervorlage in einem Schritt
- **Zweck:** Entwurf 6: Kontakt speichern und dabei Rückruf/Wiedervorlage/Praxistermin mit Datum und Uhrzeit anlegen.
- **Ansicht:** 6 Kontakte
- **Endpunkt:** `POST /api/kontakte/` mit `"wiedervorlage": {"art": praxistermin|rueckruf|wiedervorlage|sonstiges (Standard
  wiedervorlage), "ort"?: Terminort-ID, "faellig_am", "uhrzeit"?, "titel"?, "notiz"?}`
- **Logik:** Kontakt und Termin in einer Transaktion; Termin verweist auf den Kontakt; Titel ohne Angabe = Art.
- **Validierung:** Datum nicht in der Vergangenheit; Ort aus Liste „Terminort“; bei Fehler wird **nichts** gespeichert.
- **Tabellen:** `patienten_kontakt`, `patienten_termin` (+ Historie)
- **Fehlerfälle:** 400 `{"wiedervorlage": {...}}`
- **Teststatus:** Backend-Tests grün (`test_kontakt_mit_wiedervorlage`, `test_wiedervorlage_wird_geprueft`). Browsertest grün: `akte.spec.ts` „Kontakt mit Wiedervorlage erfassen, suchen, stornieren“; Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F29 Termine anlegen, ändern, lesen
- **Ansicht:** 2 Start, 4 Akte
- **Endpunkte:** `GET /api/termine/?patient&art&von&bis&offen`, `POST /api/termine/`, `PATCH /api/termine/{id}/`
- **Request:** `{"patient", "art": "praxistermin"|"rueckruf"|"wiedervorlage"|"sonstiges", "faellig_am", "uhrzeit"?, "ort"?
  (Terminort-ID), "bei"? (Freitext, bleibt für Altdaten), "titel", "notiz"?, "kontakt"?}`
- **Response:** zusätzlich `ort_name`, `patient_name`, `erledigt_am`, `erledigt_von_name`, `angelegt_von_name`
- **Validierung:** Ort aus Liste „Terminort“; Kontakt gehört zum Patienten; erledigte Termine nicht änderbar; Akte offen.
- **Tabellen:** `patienten_termin`, `patienten_historicaltermin`, `stammdaten_auswahlwert`
- **Teststatus:** Backend-Test grün (`test_termin_mit_ort`). Browsertests grün: `start.spec.ts` „Termin von der Startseite anlegen und als erledigt abhaken“ (Anlegen von der Startseite, mit Neustart), Termin ändern
  und Praxistermin mit Terminort in `akte.spec.ts` „Kontakt mit Wiedervorlage erfassen, suchen, stornieren“; Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F30 Termin als erledigt markieren
- **Ansicht:** 2 Start
- **Endpunkt:** `POST /api/termine/{id}/erledigt/` → Termin mit `erledigt_am`, `erledigt_von_name`
- **Fehlerfälle:** 400 bereits erledigt · 409 Akte abgeschlossen
- **Teststatus:** Backend-Test grün (`test_termin_mit_ort`). Browsertest grün: `start.spec.ts` „Termin von der Startseite anlegen und als erledigt abhaken“ (Abhaken, nach Neustart erledigt).
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## E · Infusionspläne

### F31 Infusionspläne eines Patienten lesen
- **Ansicht:** 8 Infusionspläne. „Ansicht wie PDF“ zeigt die echte PDF (02.10.2026): freigegeben = gespeicherte PDF der Freigabe
  (F37, mit Prüfsumme), Entwurf oder ohne gespeicherte PDF = `GET /api/infusionsplaene/{id}/ansicht/` (aktive Dokumentvorlage,
  Wasserzeichen „ENTWURF“ bzw. „TESTDATEN“, nicht zum Versand). Der Text der Seiten liegt für Bildschirmleser unter der Seite.
- **Endpunkt:** `GET /api/infusionsplaene/?patient=<id>&status=` → Pläne mit allen Werten, `vitamine`, `vitamine_namen`,
  Positionen, `kcal_berechnet`, `kcal`, `gesamtvolumen_ml`, `volumen_gewicht_kg`, `rate_ml_h`, `geaenderte_felder`
- **Teststatus:** Backend-Tests grün (`infusionen.tests.*`, `vorlagen.Vorlagen.test_ansicht_in_der_akte_im_layout_der_vorlage`). Browsertests grün: `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“ (Entwurf als PDF-Ansicht, nach der Freigabe die gespeicherte PDF), `plaene.spec.ts` „Mitarbeiter sieht Pläne, legt aber keine an“; Neustart geprüft in `zz-neustart.spec.ts` (gespeicherte PDF, Prüfsumme stimmt) (Lauf 36938008996, Commit `e709bee`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F32 Neuer Plan als Entwurf
- **Ansicht:** 7 Neuer Infusionsplan
- **Endpunkt:** `POST /api/infusionsplaene/entwurf/` `{"patient", "leer"?: bool, "vorlage"?: Plan-ID}` → 201 Entwurf
- **Logik:** Standard vorbelegt mit dem aktuellen Plan (Werte, Vitamine, Positionen); `leer` = „Leer beginnen“; `vorlage` =
  „Als Vorlage für neuen Plan“ aus einem früheren Plan desselben Patienten. Vorgänger ist immer der aktuelle Plan.
  Erster Plan: Der Editor belegt wie im Altsystem je kg des letzten Gewichts vor (`GET /api/infusionsplaene/vorbelegung/?patient=`
  → `{gewicht_kg, je_kg, werte}`: Glucose 3,5 g, Aminosäuren 1,2 g, Lipide 1 g, Natrium 1,3, Kalium 0,7, Phosphat 0,3,
  Calcium 0,15, Magnesium 0,2 mmol je kg; gerundet auf 0,1 wie die Felder).
- **Validierung:** Recht „Infusionspläne anlegen“ (Standard: Mediziner; Admin nur bei Testpatienten); höchstens ein Entwurf je Patient; Vorlage vom selben Patienten; Akte offen.
- **Fehlerfälle:** 400 Entwurf vorhanden / Vorlage fremd · 403 · 409
- **Teststatus:** Backend-Tests grün (`test_ablauf`, `test_leer_beginnen_und_vorlage`, `test_abgeschlossene_akte`, `test_berechnung_wie_im_altsystem`). Browsertest grün: `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“
  (erster Plan je kg vorbelegt, Folgeplan vorbelegt mit dem aktuellen Plan, „Als Vorlage für neuen Plan“, „Leer beginnen“, nur ein Entwurf
  je Patient).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F33 Entwurf bearbeiten
- **Ansicht:** 7 Neuer Infusionsplan
- **Endpunkt:** `PATCH /api/infusionsplaene/{id}/`
- **Request:** `gueltig_ab, basis_praeparat, basis_ml, glucose_praeparat, glucose_g, aminosaeuren_praeparat, aminosaeuren_g,
  lipide_praeparat, lipide_g, albumin_praeparat, albumin_ml, natrium_mmol, kalium_mmol, phosphat_mmol, calcium_mmol,
  magnesium_mmol, spurenelemente, vitamine[], katheterschutz, kcal_manuell, laufzeit_h, tage_pro_woche, pantozol_stufe,
  pantozol_tage, bemerkung, positionen[]`
- **Validierung:** Präparat passt zur Kategorie (Vitamine nur Vitamin-Präparate); ausgeblendete Präparate nicht neu wählbar
  (bisherige bleiben); Präparat Pflicht, wenn Menge gesetzt; Energie, Glucose, Aminosäuren, Lipide, Natrium, Kalium in den
  Grenzen der Einstellungen; Regeln für den Protonenpumpenhemmer (F38); Gesamtvolumen in den Grenzen (F39).
- **Berechnung wie im Altsystem:** Energie = Glucose·4 + Aminosäuren·4 + Lipide·9,15 kcal; Humanalbumin in ml, ohne Energie.
  Stabilität: Calcium + Magnesium (mmol) ≤ Gesamtvolumen ÷ 100, sonst Hinweis „instabil“ (`ca_mg_mmol`, `ca_mg_grenze_mmol`,
  `ca_mg_stabil`); Speichern bleibt möglich.
- **Tabellen:** `infusionen_infusionsplan`, `infusionen_infusionsplan_vitamine`, `infusionen_infusionsplanposition`, Historientabellen
- **Fehlerfälle:** 400 · 403 freigegeben oder Rolle · 409
- **Teststatus:** Backend-Tests grün (`test_ablauf`, `test_praeparate_werden_geprueft`, `test_ausgeblendetes_praeparat_bleibt_im_neuen_entwurf`,
  `test_kcal_manuell_und_grenze`, `test_gesamtvolumen_rate_und_protonenpumpenhemmer`, `test_berechnung_wie_im_altsystem`).
  Browsertest grün: `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“ (Energie mit 9,15 kcal/g, Ca/Mg stabil und instabil, alle
  Elektrolyte, Spurenelemente, Katheterblock, Vitamine, Energie manuell, Protonenpumpenhemmer mit Zeiten, Gesamtvolumen und
  Rate; Plausibilität im Editor und im Backend; geänderte Werte markiert).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F34 Entwurf verwerfen
- **Ansicht:** 8 Infusionspläne
- **Endpunkt:** `DELETE /api/infusionsplaene/{id}/` → 204; nur Entwürfe (Modell + Trigger), sonst 403
- **Teststatus:** Backend-Tests grün (`test_entwurf_verwerfen`, `test_ablauf`). Browsertest grün: `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F35 Plan freigeben
- **Ansicht:** 8 Infusionspläne
- **Endpunkt:** `POST /api/infusionsplaene/{id}/freigeben/` → Plan mit `status: "aktuell"`; bisheriger aktueller Plan → `abgeloest`
- **Logik:** danach unveränderlich, auch die Vitamin-Zuordnung (Trigger auf `infusionen_infusionsplan_vitamine`). Bei der
  Freigabe entsteht die PDF mit der aktiven Vorlage „Infusionsplan“ (F50/F51) und wird als Dokument „Von EPM erzeugt“ (Typ
  „Infusionsplan“) in der Akte abgelegt; am Plan stehen `pdf_datei`, `pdf_sha256` und `vorlage_version`. Freigabevermerk statt
  Unterschrift: „Maschinell erstellt, geprüft und freigegeben von <Mediziner> am <Datum>.“ Hat der Mediziner außerhalb von
  EPM freigegeben und ein Mitarbeiter schließt ab: F82 (der Vermerk nennt dann beide).
- **Validierung:** Recht „Infusionspläne freigeben“ (Standard: Mediziner; Admin nur bei Testpatienten); vollständige Prüfung aller Werte; Akte offen.
- **Teststatus:** Backend-Tests grün (`test_ablauf`, `test_vitamine_freigegebener_plaene_in_der_datenbank_geschuetzt`,
  `vorlagen.Vorlagen.test_freigabe_speichert_pdf_mit_pruefsumme`). Browsertest grün: `plaene.spec.ts` „Erster Plan, Freigabe,
  Folgeplan mit markierten Änderungen, Verwerfen“ (PDF einseitig, Prüfsumme); Neustart geprüft in `zz-neustart.spec.ts` (Lauf 36921980921, Commit `ca9f858`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F36 Vergleich mit dem Vorgänger
- **Ansicht:** 8 Infusionspläne
- **Endpunkt:** `GET /api/infusionsplaene/{id}/vergleich/` → `{"vorgaenger": {id, gueltig_ab, status} | null, "zeilen":
  [{"schluessel", "wert", "vorher", "jetzt", "geaendert"}], "anzahl_geaendert"}`; Zeilen in der Reihenfolge des Entwurfs
  (Basislösung … Bemerkung), Werte als Anzeigetext („Glucose 70 % · 200 g“, „80 mmol“, „Soluvit N | Vitalipid adult“).
- **Tabellen:** `infusionen_infusionsplan`, `infusionen_infusionsplan_vitamine`
- **Teststatus:** Backend-Test grün (`test_vergleich_mit_vorgaenger`). Browsertest grün: `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“ („2 Werte geändert …“).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F37 Gespeicherte Plan-PDF öffnen mit SHA-256-Prüfung
- **Ansicht:** 8 Infusionspläne („PDF öffnen“ am freigegebenen Plan)
- **Endpunkt:** `GET /api/infusionsplaene/{id}/pdf/` → gespeicherte PDF über X-Accel-Redirect; vorher Prüfsumme gegen
  `pdf_sha256`, Ergebnis im Kopf `X-EPM-Pruefung: ok|abweichend` und `X-EPM-Vorlage-Version`. Die PDF wird nie neu erzeugt.
  Nginx reicht beide Köpfe nach dem internen Umleiten weiter (`rollout/projekt/nginx/epm.conf`; zuvor gingen sie dabei
  verloren). Ohne gespeicherte PDF (Entwurf) zeigt die Akte `GET /api/infusionsplaene/{id}/ansicht/` – mit der aktiven
  Dokumentvorlage erzeugt, Wasserzeichen „ENTWURF“, nicht gespeichert (F31).
- **Anzeige:** „Prüfsumme stimmt: unverändert seit der Freigabe · Dokumentvorlage Version n“ bzw. rote Warnung bei Abweichung.
- **Teststatus:** Backend-Test grün (`vorlagen.Vorlagen.test_freigabe_speichert_pdf_mit_pruefsumme`, auch veränderte Datei →
  „abweichend“). Browsertest grün: `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“;
  Neustart geprüft in `zz-neustart.spec.ts` (Prüfsumme nach dem Neustart) (Lauf 36921980921, Commit `ca9f858`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F38 Protonenpumpenhemmer (Pantozol®/Nexium®) im Plan
- **Ansicht:** 7 Neuer Infusionsplan (Karte „Protonenpumpenhemmer“), 8 Infusionspläne (Ansicht wie PDF, Vergleich)
- **Festlegung 01.10.2026 (U1):** Protonenpumpenhemmer als Kurzinfusion, Auswahl wie im Altsystem (`EPM_infuplan.php`):
  kein · Pantozol® 40 mg · Pantozol® 20 mg · Nexium®; Zeiten morgens, mittags, abends (mehrere möglich).
- **Felder:** `pantozol_stufe` mit den Codes des Altsystems (0 kein, 1 Pantozol® 40 mg, 3 Pantozol® 20 mg, 2 Nexium®), damit
  der Import die Werte unverändert übernimmt; `pantozol_tage` = Zeiten als Bitmaske wie `panzeit` im Altsystem
  (4 morgens + 2 mittags + 1 abends, z. B. 5 = morgens und abends).
- **Validierung:** unbekannter Code → 400 `pantozol_stufe`; Präparat gewählt ohne Zeiten → 400 „Bitte die Zeiten angeben
  (morgens, mittags, abends).“; Zeiten ohne Präparat → 400; Zeiten außerhalb 1–7 → 400 (zusätzlich DB-Constraint).
- **Anzeige:** „Pantozol® 40 mg · morgens, abends“ in der Ansicht wie PDF, im Vergleich und im Verlauf; geänderte Werte markiert.
- **Teststatus:** Backend-Tests grün (`test_gesamtvolumen_rate_und_protonenpumpenhemmer`, `test_praeparate_werden_geprueft`). Browsertest grün:
  `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“ (Präparat wählen, ohne Zeiten abgewiesen, morgens + abends; Folgeplan übernimmt beides; PDF-Ansicht „Pantozol® 40 mg ·
  morgens, abends“; API `pantozol_stufe` 1, `pantozol_tage` 5); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F39 Gesamtvolumen, Laufzeit und Rate
- **Ansicht:** 7 Neuer Infusionsplan (Karte „Gültigkeit, Laufzeit“), 8 Infusionspläne, Übersicht der Akte
- **Festlegung 01.10.2026 (U2):** Gesamtvolumen wird berechnet wie im Altsystem (`$volum = round($gewicht * 35, 2)`),
  die Laufzeit wird eingegeben.
- **Logik:** `gesamtvolumen_ml` = letztes erfasstes Gewicht (nach Messdatum) × 35 ml, auf 2 Stellen; `volumen_gewicht_kg` hält das
  verwendete Gewicht fest. Im Entwurf bei jedem Speichern neu berechnet, mit der Freigabe eingefroren (spätere Gewichte ändern
  einen freigegebenen Plan nicht). Ohne Gewicht bleiben Gesamtvolumen und Rate leer. `rate_ml_h` = Gesamtvolumen ÷ Laufzeit,
  auf 0,1 ml/h. Beide Werte sind nicht eingebbar (nur lesend in der API). Der Editor zeigt sie schon während der Eingabe.
- **Validierung:** Gesamtvolumen in den Grenzen der Einstellungen (`volumen_min_ml`/`volumen_max_ml`, Standard 0–9.000 ml),
  sonst 400 `gesamtvolumen_ml`.
- **Anzeige:** „2.100 ml (35 ml/kg × 60 kg)“ und „175 ml/h“ in der Ansicht wie PDF und im Vergleich; Übersicht der Akte
  „Gesamtvolumen 2.100 ml · Rate 175 ml/h“.
- **Teststatus:** Backend-Test grün (`test_gesamtvolumen_rate_und_protonenpumpenhemmer`: letztes Gewicht nach Messdatum, 60 kg → 2.100 ml,
  12 h → 175 ml/h, nach Freigabe eingefroren, neuer Entwurf mit 70 kg → 2.450 ml, Grenze). Browsertests grün: `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“ (Editor,
  PDF-Ansicht, Übersicht der Akte, API), `admin.spec.ts` „Vorlagen: Logo, Absender, Auswahllisten mit Reihenfolge, Grenzwerte“ (Grenze); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## F · Dokumente

### F40 Dokument hochladen
- **Ansicht:** 9 Dokumente
- **Endpunkt:** `POST /api/dokumente/` (multipart) `patient`, `datei`, `titel`, `typ`?, `datum`?, `notiz`?
- **Response 201:** `{id, patient, typ, typ_name, titel, datum, datum_quelle, typ_geprueft, notiz, ausgeblendet, originalname, mime,
  groesse, sha256, herkunft, hochgeladen_am, hochgeladen_von_name}`
- **Validierung:** Datei Pflicht, max. 50 MB; **Dateityp am Inhalt erkannt** (PDF, JPEG, PNG, Text UTF-8/Windows-1252; alles andere
  → 400, die Endung zählt nicht); Typ aus Liste „Dokumenttyp“; Akte offen.
- **Speicherung:** `/data/dokumente/<nummer>/<zufällig>.<endung>`, atomar, SHA-256, MIME-Typ aus der Inhaltserkennung.
- **Tabellen:** `patienten_dokument`, `patienten_historicaldokument`
- **Teststatus:** Backend-Tests grün (`test_dokument_upload_und_download`, `test_dokumenttyp_am_inhalt`). Browsertest grün: `dokumente.spec.ts` „Dokumente hochladen, Typ am Inhalt prüfen, Metadaten ändern, ausblenden, herunterladen; Verlauf“ (.exe
  abgewiesen, Text und PNG am Inhalt erkannt); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F72 Dokument dem richtigen Patienten zuordnen
- **Zweck:** Ein Dokument liegt beim falschen Patienten (Bernds Unterlagen bei Sabine). Festlegung 02.10.2026: umhängen statt
  nur ausblenden – Sabines Akte zeigt danach weder Inhalt noch Titel noch Bernd.
- **Ansicht:** 9 Dokumente (Dokument markieren › „Anderem Patienten zuordnen“: Patient suchen, Grund, Bestätigung „gehört zu …“)
- **Endpunkt:** `POST /api/dokumente/{id}/umhaengen/` `{"patient": ID, "grund": "…"}` → 200 Dokument
- **Logik:** Datei wandert in den Ordner des richtigen Patienten (atomar), Prüfsumme, Datum, Typ bleiben. Unveränderlicher Eintrag
  `DokumentVorgang` (Trigger). Verlauf der bisherigen Akte: „einer anderen Akte zugeordnet“, frühere Einträge dieses Dokuments
  ohne Titel und Werte; Verlauf der neuen Akte: „von einer anderen Akte übernommen“ mit Grund. Audit-Log (Gruppe „Dokument“):
  Titel, von, nach, Grund.
- **Validierung:** Recht „Dokumente einem anderen Patienten zuordnen“ (Standard: Mediziner; Admin nur bei Testpatienten);
  Grund mindestens 5 Zeichen; Zielpatient sichtbar, nicht derselbe, Testpatient nur zu Testpatient; beide Akten offen;
  von EPM erzeugte Dokumente (Plan-PDFs) nicht.
- **Tabellen:** `patienten_dokument` (+ Historie), `patienten_dokumentvorgang`, `audit_systemereignis`; Migrationen
  `patienten/0004_dokumentvorgang`, `audit/0004_dokumente_umhaengen_loeschen`; für F73 zusätzlich
  `patienten/0005_dokumentvorgang_nachweis`, `patienten/0006_geloeschte_dokumente_schwaerzen`,
  `audit/0005_dokument_loeschung_nachgeholt`
- **Fehlerfälle:** 400 Grund/Patient · 403 ohne Recht bzw. Admin bei echten Akten · 409 Datei fehlt
- **Teststatus:** Backend-Tests grün (`FalschZugeordneteDokumente.test_umhaengen`, `test_systemdokumente_bleiben`). Browsertest
  grün: `dokumente-falsch.spec.ts` „Dokument beim falschen Patienten dem richtigen zuordnen; Verlauf neutral bzw. mit Grund“
  (Datei bei Bernd unverändert, Verlauf beider Akten, Audit-Log); `dokumente.spec.ts`: Mitarbeiter sehen die Aktion nicht
  (Lauf 36938008996, Commit `e709bee`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F73 Dokument endgültig löschen
- **Zweck:** Ein Dokument gehört zu keinem Patienten der Stiftung. Festlegung 02.10.2026: nur Mediziner, doppelt bestätigt
  (Kennwort + Code aus der Authenticator-App + abgetippter Bestätigungscode), im Audit-Log.
- **Ansicht:** 9 Dokumente › „Endgültig löschen“ (Grund, Kennwort, Code, 6-stelliger Bestätigungscode zum Abtippen – nicht
  markierbar)
- **Endpunkte:** `POST /api/dokumente/{id}/loeschen-vorbereiten/` → `{code, gueltig_bis}` (5 Minuten, in der Sitzung);
  `POST /api/dokumente/{id}/loeschen/` `{"grund", "kennwort", "code", "bestaetigung"}` → 204
- **Logik (Art. 17 DSGVO, Klärung U15 vom 02.10.2026):** Datensatz und Datei werden entfernt (Datei nach dem Commit), dazu
  in derselben Transaktion Titel, Original-Dateiname, Notiz und Dokumentdatum in **allen** Historien-Zeilen des Dokuments und
  in seinen Audit-Log-Einträgen (auch den Ablehnungen) → „[entfernt]“ (`patienten/loeschung.py::schwaerze_dokument`).
  Die Schutz-Trigger (`audit/schutz.py`) erlauben genau diese eine Änderung – nur mit `SET LOCAL epm.schwaerzen =
  'dokument:<Nummer>:<SHA-256>'`, nur für dieses Dokument, nur diese Spalten, nur der Platzhalter; jede andere Änderung,
  jedes andere Dokument und jedes Löschen von Protokollzeilen bleibt verboten. Es bleibt der Nachweis ohne Inhalt
  (Art. 5 Abs. 2, Art. 33 Abs. 5 DSGVO; § 630f BGB): `DokumentVorgang` (Nummer, Akte, Person, Zeitpunkt, Grund, SHA-256,
  Pfad), Audit-Log „Dokument Nr. N (Typ, SHA-256 …) aus Akte X endgültig gelöscht – Datei, Titel und Inhalt entfernt
  (Art. 17 DSGVO), Grund: …“ mit Größe und Hochladezeitpunkt, Verlauf „endgültig gelöscht“ mit Grund, frühere Einträge
  ohne Titel. Jede Ablehnung (Code abgelaufen/falsch, Kennwort, 2FA) steht im Audit-Log (Gruppe „Fehlversuch“); dreimal
  falscher Bestätigungscode macht ihn ungültig. Ein falsches Kennwort oder ein falscher Authenticator-Code zählt seit
  Runde 4 wie ein Fehlversuch bei der Anmeldung (F08: beim fünften wird das Konto gesperrt) – auch bei F80. Der Grund bleibt im Protokoll – die Oberfläche bittet, keine Namen oder
  Gesundheitsangaben der fremden Person hineinzuschreiben.
- **Sicherungen und Wiederherstellung:** Ältere Sicherungen enthalten das Dokument bis zu ihrem Ablauf (30 Tage, F61).
  Jede Löschung steht zusätzlich in der Löschliste `data/loeschliste/loeschliste.jsonl` (eigener Ordner, nur Backend,
  weder in der Datenbank noch im Dokumentordner; Inhalt: Nummer, SHA-256, Pfad, Patienten-ID, Benutzer-ID, Zeitpunkt –
  kein Titel); `epm-backup` sichert sie getrennt mit. Bei jedem Start läuft `manage.py epm_loeschungen_nachholen`
  (`entrypoint.sh`): Ist ein gelöschtes Dokument nach einer Wiederherstellung wieder da (gleiche Nummer **und** gleiche
  Prüfsumme), wird es erneut gelöscht und geschwärzt, mit Vorgang und Audit-Eintrag „Löschung eines Dokuments nachgeholt“;
  eine zurückgekommene Datei wird entfernt; fehlt eine Löschung in der Liste, wird sie aus der Datenbank ergänzt. Ein neues
  Dokument, das dieselbe Nummer bekommen hat, bleibt unberührt (andere Prüfsumme). Bei einer Wiederherstellung immer die
  neueste Löschliste behalten (F63).
- **Bestand:** Migration `patienten/0006_geloeschte_dokumente_schwaerzen` schwärzt Dokumente, die vor dieser Version
  gelöscht wurden, und trägt Prüfsumme und Pfad im Vorgang nach.
- **Validierung:** Recht „Dokumente endgültig löschen“ (Mediziner und Admin, keiner anderen Rolle zuweisbar; Admins auch bei
  echten Akten, Festlegung 02.10.2026);
  Grund mindestens 10 Zeichen; Akte offen; keine von EPM erzeugten Dokumente.
- **Fehlerfälle:** 400 je Feld · 403 ohne Recht · 404 schon gelöscht
- **Teststatus:** Backend-Tests grün (`FalschZugeordneteDokumente.test_endgueltig_loeschen` – auch: Titel, Dateiname, Notiz,
  Datum in keiner Historien-Zeile und keinem Audit-Eintrag mehr, Löschliste ohne Titel, Trigger lehnen jede andere Änderung
  ab; `test_loeschung_nach_wiederherstellung_nachholen` – Datensatz, Datei und Historie zurückgespielt → erneut gelöscht und
  geschwärzt, nur Datei zurück → entfernt, gleiche Nummer mit anderem Inhalt bleibt, verlorene Löschliste wird ergänzt;
  `test_migration_schwaerzt_bestehende_loeschungen`; `RechteJeGruppe.test_standard`). Browsertest grün:
  `dokumente-falsch.spec.ts` „Endgültig löschen: nur Mediziner, mit Kennwort, Authenticator-Code und Bestätigungscode“
  (falsches Kennwort abgelehnt und protokolliert, dann gelöscht; Verlauf; Audit-Log in der Oberfläche, Filter „Dokument“ und
  „Fehlversuch“: Nummer und Prüfsumme statt Titel, Titel nirgends); Neustart geprüft in `zz-neustart.spec.ts` (Dokument
  bleibt weg, Verlauf und Audit-Log ohne Titel; beim Neustart läuft das Nachholen) (Lauf 36943685896, Commit `e74f4ff`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F41 Dokumente lesen, Metadaten ändern, ausblenden
- **Endpunkte:** `GET /api/dokumente/?patient&typ&ausgeblendet&search`, `PATCH /api/dokumente/{id}/` (`titel`, `typ`, `datum`, `notiz`, `ausgeblendet`)
- **Teststatus:** Browsertest grün: `dokumente.spec.ts` „Dokumente hochladen, Typ am Inhalt prüfen, Metadaten ändern, ausblenden, herunterladen; Verlauf“ (Typ, Datum, Titel; ausblenden und wieder anzeigen); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F42 Datei anzeigen und herunterladen
- **Endpunkt:** `GET /api/dokumente/{id}/datei/[?anzeigen=1]` → Nginx liefert über `X-Accel-Redirect: /_geschuetzt/dokumente/…`
- **Teststatus:** Backend-Test grün (Kopfzeile). Browsertest grün: `dokumente.spec.ts` „Dokumente hochladen, Typ am Inhalt prüfen, Metadaten ändern, ausblenden, herunterladen; Verlauf“ (Vorschau; Download über Nginx mit X-Accel-Redirect, Inhalt
  unverändert); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F43 Altdokumente prüfen
- **Zweck:** importierte Dateien tragen „Typ prüfen“ und die Herkunft des Datums (PDF-Metadaten, EXIF, Dateidatum), bis jemand
  sie bestätigt.
- **Ansicht:** 9 Dokumente, 2 Start („Nach und nach prüfen“)
- **Endpunkt:** `POST /api/dokumente/{id}/geprueft/` `{"typ"?, "datum"?, "titel"?}` → Dokument mit `typ_geprueft: true`;
  geändertes Datum → `datum_quelle: "eingabe"`. Liste: `GET /api/patienten/?pruefen=altdokumente`; Anzahl in F13.
- **Felder:** `typ_geprueft` (bool, nur über diese Aktion setzbar), `datum_quelle` (eingabe|pdf|exif|dateidatum)
- **Tabellen:** `patienten_dokument` (+ Historie)
- **Fehlerfälle:** 400 Typ aus falscher Liste · 409 Akte abgeschlossen
- **Teststatus:** Backend-Test grün (`test_altdokument_pruefen`). Browsertest grün: `dokumente.spec.ts` „Altdokument prüfen: Typ und Datum bestätigen“; Neustart geprüft in `zz-neustart.spec.ts`. Befüllung beim Import: F65.
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## G · Stammdaten und Vorlagen

### F44 Auswahllisten pflegen
- **Ansicht:** 18 Vorlagen › Auswahllisten
- **Endpunkte:** `GET/POST /api/auswahlwerte/?liste&aktiv`, `PATCH /api/auswahlwerte/{id}/` (kein Löschen)
- **Listen:** `katheter`, `dokumenttyp`, `terminort`, `kontaktart` (U6). Musterwerte wie im Entwurf (Katheter 6, Terminorte 1,
  Dokumenttypen 6); bisher angelegte Werte bleiben erhalten.
- **Validierung:** Wert je Liste eindeutig; schreiben mit Recht „Vorlagen pflegen“ (Standard: Mitarbeiter, Mediziner, Admin); Änderungen im Audit-Log mit alt/neu.
- **Tabellen:** `stammdaten_auswahlwert` (+ Historie)
- **Teststatus:** Backend-Tests grün (`test_auswahllisten_wie_im_entwurf`, `Reihenfolge.*`). Browsertest grün: `admin.spec.ts` „Vorlagen: Logo, Absender, Auswahllisten mit Reihenfolge, Grenzwerte“ (Terminort anlegen,
  Reihenfolge per Tastatur, ausblenden); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F45 Versorger pflegen
- **Ansicht:** 13 Versorger, 12 Neuer Patient („Neu anlegen“)
- **Endpunkte:** `GET/POST /api/versorger/`, `PATCH /api/versorger/{id}/`; Deaktivieren über `aktiv: false`; kein Löschen (405)
- **Response:** mit `ansprechpartner[]` und `patienten_anzahl`
- **Rechte:** Recht „Versorger und Ansprechpartner pflegen“ (Standard: Mitarbeiter, Mediziner, Admin; U10 erledigt)
- **Tabellen:** `stammdaten_versorger` (+ Historie)
- **Teststatus:** Backend-Test grün (`VersorgerUndAnsprechpartner.test_rechte`). Browsertests grün: `versorger.spec.ts` „Versorger anlegen, Ansprechpartner pflegen, deaktivieren mit Neuzuordnung“ (mit Neustart), `versorger.spec.ts` „Betrachter sieht Versorger nur lesend“.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F46 Ansprechpartner pflegen
- **Ansicht:** 13 Versorger
- **Endpunkte:** `GET/POST /api/ansprechpartner/?versorger`, `PATCH /api/ansprechpartner/{id}/`;
  `GET /api/ansprechpartner/{id}/patienten/` (betreute Patienten in Betreuung);
  `POST /api/ansprechpartner/{id}/neu-zuordnen/` `{"ziel": id}` → `{"neu_zugeordnet": n}`
- **Felder:** `name`, `zustaendigkeit` („Patienten A–K“), `telefon`, `mobil`, `email`, `notiz`, `aktiv`; `patienten_anzahl`
- **Validierung:** Ziel aktiv, anderer Ansprechpartner desselben Versorgers; abgeschlossene Akten bleiben unverändert; jede
  Neuzuordnung steht im Verlauf der Akte.
- **Tabellen:** `stammdaten_ansprechpartner`, `patienten_patient` (+ Historie), `audit_systemereignis`
- **Teststatus:** Backend-Test grün (`test_patienten_und_neu_zuordnen`). Browsertest grün: `versorger.spec.ts` „Versorger anlegen, Ansprechpartner pflegen, deaktivieren mit Neuzuordnung“ (Deaktivieren mit Neuzuordnung, mit Neustart).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F47 Präparate pflegen
- **Ansicht:** 18 Vorlagen › Präparate
- **Endpunkte:** `GET/POST /api/praeparate/?kategorie&aktiv`, `PATCH /api/praeparate/{id}/`; kein Löschen (405)
- **Felder:** `kategorie`, `name`, `konzentration`, `einheit`, `reihenfolge`, `aktiv`, `anzeige`; nur lesend `in_plaenen`
  (Anzahl der Pläne, in denen das Präparat vorkommt, auch als Vitamin)
- **Musterwerte:** wie im Entwurf (Basislösungen, Glucose 70 %, 8 Aminosäuren, 7 Lipide, Humanalbumin, 3 Spurenelemente,
  5 Vitamine, 2 Katheterblock); bisherige Einträge bleiben.
- **Teststatus:** Backend-Tests grün (`Praeparate.*`). Browsertest grün: `admin.spec.ts` „Vorlagen: Logo, Absender, Auswahllisten mit Reihenfolge, Grenzwerte“ (Vitamin anlegen und ausblenden); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F48 Grenzwerte und Einstellungen
- **Ansicht:** 18 Vorlagen › Grenzwerte
- **Endpunkt:** `GET/PATCH /api/einstellungen/` (lesen alle, ändern mit Recht „Vorlagen pflegen“)
- **Felder:** Absender; Warnung Gewichtsverlust %, Zeitraum, Plan alt nach Monaten, Kontakt bald fällig nach Monaten
  (`kontakt_bald_monate`, Standard 4, neu in Runde 7) und Kontakt überfällig nach Monaten (`kontakt_ueberfaellig_monate`,
  Standard 6; F90);
  Min/Max für Energie, Gesamtvolumen, Glucose, Aminosäuren, Lipide, Natrium, Kalium, Gewicht, Größe.
  Datenschutz (Karte „Datenschutz“): `aufbewahrung_jahre` (Standard 10, 1–100), `abschluss_pruefen_monate` (Standard 24),
  `protokoll_aufbewahrung_jahre` (Standard 0 = unbegrenzt), `pflicht_erklaerungen` (Liste; Standard alle drei) – F74, F75, F83.
  Diese vier Werte ändert nur, wer zusätzlich das Recht „Datenschutz: Anfragen entscheiden …“ hat (sie bestimmen, wann
  Akten gelöscht werden dürfen und wann Einträge des Audit-Logs entfernt werden); sonst 403, in der Oberfläche nur lesbar.
- **Validierung:** Minimum < Maximum je Paar; „bald fällig“ mindestens 1 Monat und kleiner als „überfällig“ (sonst 400
  `{"kontakt_ueberfaellig_monate": "„Überfällig“ muss später liegen als „bald fällig“."}`); Audit-Log „Grenzwert „Kontakt
  überfällig“ von 6 auf 8 Monate geändert“.
- **Teststatus:** Backend-Tests grün (`EinstellungenPruefen.test_grenzen_und_rechte`, `test_gesamtvolumen_rate_und_protonenpumpenhemmer`).
  Browsertests grün: `admin.spec.ts` „Vorlagen: Logo, Absender, Auswahllisten mit Reihenfolge, Grenzwerte“ (untere > obere Grenze abgewiesen, Grenze für das Gesamtvolumen geändert), Grenzen wirken in
  `akte.spec.ts` „Gewicht erfassen, Plausibilität, korrigieren, Zeitraum“, `patienten.spec.ts` „Neuer Patient: Prüfung, Doppelung, Anlegen mit Gewicht bei Aufnahme“, `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“; Neustart geprüft in `zz-neustart.spec.ts` (Grenzwert vor dem Neustart in der Oberfläche geändert).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F49 Briefkopf, Absender und Logo
- **Ansicht:** 18 Vorlagen (Briefkopf und Logo)
- **Endpunkte:** `GET /api/briefkopf/` → `{aktiv: stiftung|gug, absender: {stiftung, gug: {name, strasse, plz, ort, telefon,
  fax, email, internet, fusszeile}}, arten, logo: {vorhanden, mime, sha256, breite, hoehe, hochgeladen_am}}`;
  `PATCH /api/briefkopf/` `{aktiv?, absender?: {stiftung?: {...}, gug?: {...}}}`; `GET /api/briefkopf/logo/` (öffentlich, auch
  für die Anmeldeseite) und `POST /api/briefkopf/logo/` (multipart `datei`)
- **Validierung:** Schreiben mit Recht „Vorlagen pflegen“; Logo PNG oder SVG bis 2 MB, mindestens 600 px breit, Querformat;
  SVG ohne Skripte, Ereignisse, eingebettete Inhalte und externe Verweise; Änderungen im Audit-Log mit alt/neu.
- **Tabellen:** `stammdaten_absenderangaben`, `stammdaten_logo`, `stammdaten_einstellungen` (+ Historie), Datei im Dokumentenspeicher
- **Gilt für:** neue PDFs (F51); freigegebene behalten ihren Briefkopf. Die Ansicht „wie PDF“ eines Plans zeigt ihn schon jetzt.
- **Teststatus:** Backend-Tests grün (`test_briefkopf_lesen_und_aendern`, `test_logo`). Browsertest grün: `admin.spec.ts` „Vorlagen: Logo, Absender, Auswahllisten mit Reihenfolge, Grenzwerte“ (zu kleines PNG und
  SVG mit Skript abgewiesen, gültiges SVG gespeichert, Telefon geändert mit Vorschau); Neustart geprüft in `zz-neustart.spec.ts` (Logo).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F50 Dokumentvorlagen (WYSIWYG)
- **Ansicht:** 19 Dokumentvorlagen (Administration › Vorlagen › Dokumentvorlagen): Aufbau links, Seite in der Mitte, Eigenschaften
  rechts, „Datenfeld einfügen“ an der Schreibmarke, Vorschau mit Testpatient, Versionen, „Mitgelieferte Startvorlage laden“.
- **Endpunkte:** `GET /api/vorlagen/`, `GET /api/vorlagen/{art}/` (Bausteine, Felder, Tabellen, Optionen), `GET/PUT/DELETE
  /api/vorlagen/{art}/entwurf/`, `POST /api/vorlagen/{art}/veroeffentlichen/`, `GET /api/vorlagen/{art}/versionen/{n}/`,
  `GET /api/vorlagen/{art}/startvorlage/`, `POST /api/vorlagen/{art}/vorschau/` `{patient (nur Testpatient), bloecke?}`.
- **Bausteine:** Briefkopf (Logo, Falzmarken, Linie wahlweise), Titel (wahlweise rechts neben dem Logo), Kopfkarte (wie der Kopf
  der Akte: Name, Zeilen darunter, rechts kleiner Text, Kennzahlen), Text, Zwei Spalten, Datenfelder (Paare oder „wie
  Laborbefund“: Menge rechtsbündig, Einheit eigene Spalte), Tabelle (Zusammensetzung, weitere Bestandteile, Laufzeit und
  Volumen, Termine), Trennlinie, Leerraum, Unterschrift, Seitenumbruch, Fußzeile. Optionen: Schrift, Ausrichtung, fett/kursiv,
  Überschrift (Bereich als Karte), ausblenden wenn leer, nicht teilen, Linie darüber, neben dem vorherigen Block (⅓, ½, ⅔;
  seit 14.10.2026 im 6-Spalten-Raster, dazu Kopfband und Anschriftfeld nach DIN 5008 – siehe Änderungen vom 14.10.2026).
- **Logik:** Platzhalter `{{Feld}}` nur aus der festen Liste je Art (`vorlagen/felder.py`), Fußzeile mit `{Seite}/{Seiten}`;
  Entwurf → Veröffentlichen, je Art eine aktive Version; veröffentlichte Versionen unveränderlich (Modell und Trigger
  `epm_vorlage_schutz`); Änderungen im Audit-Log.
- **Infusionsplan (Startvorlage, Überarbeitung 01.10.2026):** Aufbau wie die PDF des Altsystems, gesetzt wie ein Laborbefund und
  wie die Oberfläche von EPM: Titel neben dem Logo, Kopfkarte (Name, Geschlecht, Geburtsdatum mit Alter, Anschrift; Patienten-Nr.,
  Infusionsplan-Nr., Größe, Gewicht, erstellt am/von), Karten für Zusammensetzung (daneben Mineralstoffe), weitere
  Inhaltsstoffe, weitere Bestandteile, Laufzeit und Volumen (Mischbeutel | Zusatzlösung | Gesamt; Laufzeit 0 → „—“),
  Bemerkungen, Diagnose; Freigabevermerk; fax-tauglich (Pläne gehen per Mail oder Fax, nicht per Post).
- **Teststatus:** Backend-Tests grün (`vorlagen.Vorlagen.*`: Startvorlagen gültig, Entwurf prüfen/veröffentlichen/unveränderlich,
  Vorschau nur mit Testpatient, Inhalt der Plan-PDF, Laufzeit 0, neue Bausteine und Startvorlage, Laborbefund-Darstellung).
  Browsertests grün: `dokumentvorlagen.spec.ts` „Dokumentvorlage Infusionsplan: Text mit Datenfeld, Prüfung, Vorschau,
  Veröffentlichen“, „Betrachter hat keinen Zugang zu den Dokumentvorlagen“; Neustart geprüft in `zz-neustart.spec.ts`
  (veröffentlichte Version) (Lauf 36921980921, Commit `ca9f858`).
- **Überarbeitung 02.10.2026:** Dokumentvorlagen sind ein Bereich der Seite Vorlagen (wie Briefkopf, Auswahllisten, Grenzwerte;
  Adresse `/admin/vorlagen/dokumente`), Knöpfe oben rechts, Rückfrage bei ungespeicherten Änderungen; Felder per Griff oder ▲ ▼
  verschiebbar; Schrift klein/groß wirkt in Vorschau und PDF auf den ganzen Block (Größen in em); Titel-Ausrichtung mitte/rechts.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F51 PDF-Erzeugung
- **Umsetzung:** WeasyPrint im Backend-Image (`vorlagen/pdf.py`), offline: nur eingebettete `data:`-Adressen, keine Netz- oder
  Dateizugriffe; Schrift IBM Plex aus dem Repo (`backend/schriften/`); Kopf/Fuß per `@page`, Seitenzahl „x/y“; Wasserzeichen
  „TESTDATEN“ bzw. „ENTWURF“ (Vorschau); Ablage im Dokumentenverzeichnis mit SHA-256 (`als_dokument`).
- **Teststatus:** Backend-Tests grün (alle PDF-Tests prüfen den Inhalt mit `pdftotext`); Browsertests grün (F23, F24, F35, F37,
  F50, F55, F59) (Lauf 36921980921, Commit `ca9f858`).
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## H · Benutzer

### F52 Benutzer lesen, anlegen, ändern
- **Ansicht:** 17 Benutzer
- **Endpunkte:** `GET /api/benutzer/?rolle&is_active&ist_test&search`, `POST /api/benutzer/` → 201 mit `einmal_kennwort`,
  `PATCH /api/benutzer/{id}/`
- **Felder:** `username, titel, first_name, last_name, kuerzel, funktion, email, rolle, ist_test`; nur lesend: `is_active,
  nur_historisch, muss_kennwort_aendern, einmal_kennwort_gueltig_bis, gesperrt_am, sperrgrund, fehlversuche, last_login,
  date_joined, anzeigename, zweiter_faktor`
- **Validierung:** Recht „Benutzer und Rechte verwalten“; Kürzel eindeutig; die eigene Rolle nicht auf eine ohne Benutzerverwaltung
  änderbar; kein Löschen.
- **Tabellen:** `accounts_user`, `audit_systemereignis`
- **Teststatus:** Backend-Tests grün (`test_nur_admin_verwaltet_benutzer`, `test_neuer_benutzer_hat_frist`). Browsertest grün: `admin.spec.ts` „Benutzer anlegen, Einmal-Kennwort, sperren und entsperren“
  (Anlegen, Anzeige in der Akte, Funktion und Rolle ändern, erste Anmeldung der neuen Person); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F53 Benutzer sperren und entsperren
- **Ansicht:** 17 Benutzer, 20 Audit-Log (Hinweis)
- **Endpunkte:** `POST /api/benutzer/{id}/sperren/`, `POST /api/benutzer/{id}/entsperren/`
- **Logik:** Sperren beendet alle Sitzungen; Entsperren setzt Sperre und Fehlversuchszähler zurück.
- **Validierung:** eigenes Konto nicht sperrbar; historische Benutzer nicht entsperrbar.
- **Teststatus:** Backend-Tests grün (`test_sperre_nach_fehlversuchen`, `Sitzungen.test_sperre_beendet_alle_sitzungen`,
  `Sitzungen.test_admin_sitzung_bleibt_bei_benutzerverwaltung`). Browsertests grün: `admin.spec.ts` „Benutzer anlegen, Einmal-Kennwort, sperren und entsperren“, `admin.spec.ts` „Fünf falsche Passwörter sperren das Konto; Admin sieht den Hinweis, setzt 2FA zurück und entsperrt“; Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F54 Einmal-Kennwort erzeugen
- **Ansicht:** 17 Benutzer
- **Endpunkt:** `POST /api/benutzer/{id}/einmal-kennwort/` → `{"einmal_kennwort", "gueltig_bis"}`
- **Logik:** gültig `EPM_EINMAL_KENNWORT_STUNDEN` (Standard 48 h); Ablauf wird bei der Anmeldung geprüft (F02); alle Sitzungen
  des Benutzers werden beendet.
- **Teststatus:** Backend-Test grün (`test_einmal_kennwort_laeuft_ab`). Browsertest grün: `admin.spec.ts` „Benutzer anlegen, Einmal-Kennwort, sperren und entsperren“ (neues Einmal-Kennwort, das alte gilt nicht mehr).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F55 Zugangsblatt drucken
- **Ansicht:** 17 Benutzer („Zugangsblatt drucken“ neben dem angezeigten Einmal-Kennwort)
- **Endpunkt:** `POST /api/benutzer/{id}/zugangsblatt/` `{kennwort}` → PDF mit Name, Benutzername, Einmal-Kennwort, Gültigkeit,
  Adresse und Anleitung zur Einrichtung (Kennwort, Authenticator, Notfall-Codes). Das Kennwort wird nicht gespeichert; es muss
  zum gültigen Einmal-Kennwort passen. Export im Audit-Log.
- **Teststatus:** Backend-Test grün (`vorlagen.WeiterePdfs.test_zugangsblatt`). Browsertest grün: `admin.spec.ts` „Benutzer
  anlegen, Einmal-Kennwort, sperren und entsperren“ (Lauf 36921980921, Commit `ca9f858`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F56 2FA zurücksetzen
- **Ansicht:** 17 Benutzer
- **Endpunkt:** `POST /api/benutzer/{id}/2fa-zuruecksetzen/` → `{"einmal_kennwort", "gueltig_bis"}` (löscht Authenticator und
  Notfall-Codes, beendet alle Sitzungen)
- **Teststatus:** Backend-Test grün (`Sitzungen.test_admin_sitzung_bleibt_bei_benutzerverwaltung`). Browsertest grün: `admin.spec.ts` „Fünf falsche Passwörter sperren das Konto; Admin sieht den Hinweis, setzt 2FA zurück und entsperrt“; Neustart geprüft in `zz-neustart.spec.ts`
  („2FA: nicht eingerichtet“).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F57 Testdaten zurücksetzen
- **Ansicht:** 17 Benutzer
- **Endpunkt:** `POST /api/testdaten/zuruecksetzen/` → `{"geloescht", "angelegt"}`; Recht „Testdaten zurücksetzen“ (Standard: Admin); im Wartungsmodus der Trigger
- **Musterdaten:** 6 Testpatienten mit Plänen wie im Entwurf (Sterofundin, Glucose 70 %, Glamin, Clinoleic, Elektrolyte,
  Addel N, Soluvit N + Vitalipid adult, Taurolin 2 %), Termin in der „Praxis Dr. Holtmeier“, ein Altdokument „Typ prüfen“;
  seit 11.10.2026 Diagnosen mit ICD-Code, Laborbefunde (Werte teils außerhalb der Referenz) und BIA-Messungen je Profil,
  Test, Hanna ohne Labor und BIA (`patienten/test_testdaten_befunde.py`, `e2e/testdaten-befunde.spec.ts`).
- **Teststatus:** Backend-Test grün (`Musterdaten.test_anlegen_und_zuruecksetzen`). Browsertests grün: `admin.spec.ts` „Testdaten auf Ausgangsstand zurücksetzen (nur Testpatienten)“ (echte Patienten unverändert),
  `patienten.spec.ts` „Testzugang: Hinweis dauerhaft sichtbar, nur Testpatienten, neue Patienten werden Testpatienten“ (Testzugang sieht nur Testpatienten).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F66 Rechte je Gruppe einstellen
- **Zweck:** Die Administration legt fest, welche Gruppe (Rolle) was darf (Festlegung 01.10.2026: granular je Gruppe).
- **Ansicht:** 17 Benutzer, Bereich „Was die Rollen dürfen“
- **Endpunkte:** `GET /api/rechte/` → `{rechte: [{code, name, beschreibung}], rollen: [{code, name}], matrix: {rolle: {recht: bool}},
  fest: [[rolle, recht]], standard: {rolle: [recht]}}`; `PUT /api/rechte/` `{matrix: {rolle: {recht: bool}}}` → wie GET. Die eigenen
  Rechte stehen in `GET /api/auth/status/` bzw. `/api/auth/ich/` (`rechte: [code]`).
- **Logik:** Abweichungen vom Standard (Tabelle unter „Gemeinsame Regeln“) als `Gruppenrecht` gespeichert, mit Historie; jede
  Anfrage liest die aktuelle Matrix, Änderungen gelten sofort; Oberfläche blendet Knöpfe und Bereiche ohne Recht aus (F71).
  Fest: Admins schreiben Patientendaten nur bei Testpatienten (`pruefe_schreibbereich` an allen schreibenden Endpunkten
  der Akte und der Pläne, `schreibt_nur_testpatienten` in `Ich`, in der Matrix als „nur Testpatienten“ markiert); ein neuer
  Patient eines Admins wird Testpatient. GET liefert dazu `nur_testpatienten: {rollen, rechte}`.
- **Validierung:** nur mit Recht „Benutzer und Rechte verwalten“; unbekannte Rolle oder Recht → 400; feste Rechte (Admin: Akten lesen,
  Benutzer und Rechte verwalten) nicht entziehbar → 400; Rechte, die einer Rolle vorbehalten sind (`nur_rollen` in GET;
  02.10.2026: „Dokumente/Akten endgültig löschen“ nur Mediziner und Admin), anderen Rollen nicht zuweisbar → 400 „Dieses Recht
  ist Admin und Mediziner vorbehalten.“, in der Matrix ausgegraut; Testbenutzer ohne Rechte über Testpatienten hinaus.
- **Tabellen:** `accounts_gruppenrecht`, `accounts_historicalgruppenrecht`, `audit_systemereignis` („Rechte geändert“)
- **Fehlerfälle:** 400 · 403 ohne Recht
- **Teststatus:** Backend-Tests grün (`RechteJeGruppe.*`, `Rollen.test_admin_schreibt_nur_bei_testpatienten`,
  `Rollen.test_schreibrechte`). Browsertests grün: `admin.spec.ts` „Rechte je Gruppe: Admin erlaubt Mitarbeitern Pläne, wirkt sofort, Standard wiederherstellen“ (Mitarbeiter darf danach Pläne anlegen, sofort wirksam; feste
  Rechte nicht abwählbar; Standard wiederhergestellt), `admin.spec.ts` „Administration je Recht: Betrachter sieht nichts, Mitarbeiter Vorlagen, Mediziner Vorlagen und Audit-Log“, `admin.spec.ts` „Admin: echte Akten nur lesen, Testpatienten anlegen und bearbeiten“, `akte.spec.ts` „Stammdaten bearbeiten, Akte abschließen (Mitarbeiter) und wieder öffnen (Admin)“, `plaene.spec.ts` „Mitarbeiter sieht Pläne, legt aber keine an“; Neustart geprüft in `zz-neustart.spec.ts` (Recht vor dem Neustart in der
  Oberfläche gesetzt, danach wirksam: Betrachter sieht „Neuer Versorger“; zurück auf Standard).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F71 Nicht Erlaubtes ausblenden, Rechteänderung sofort in der Oberfläche
- **Zweck:** Wunsch aus dem Testsystem (01.10.2026): „Was er nicht weiß, macht ihn nicht heiß“ – wer ein Recht nicht hat, sieht
  die Aktion gar nicht, statt eines Fensters mit „Dafür fehlt das Recht …“. Wird ein Recht während der Arbeit entzogen, verschwindet
  die Aktion ohne neue Anmeldung.
- **Ansicht:** alle; Beispiele: Akte › „Weitere Aktionen“ (Akte abschließen/wieder öffnen, Stammdaten), Aktenkopf (Kontakt, Gewicht,
  Termin), Startseite (Termin, Abhaken), Übersicht (Korrektur, Termin), Kontakte (Stornieren), Pläne (Freigeben, Verwerfen,
  Neuer Plan), Dokumente, Versorger, Ärzte, Administration.
- **Endpunkte:** keine neuen. Jede Antwort unter `/api/` an angemeldete Benutzer trägt `X-EPM-Rechte: <12 Zeichen>` – Kennung aus den
  eigenen Rechten, „nur Testpatienten“ und Testbenutzer (`accounts.rechte.rechte_stand`, gesetzt von `RechteStandMiddleware`).
- **Logik:** Die Oberfläche merkt sich die Kennung. Ändert sie sich, wechselt die Person die Seite (auch zu Seiten aus dem
  Zwischenspeicher, die keine Anfrage stellen) oder lehnt der Server eine Anfrage wegen eines Rechts ab (403
  „fehlt das Recht“ / „nur bei Testpatienten“), lädt sie `GET /api/auth/status/` neu und aktualisiert die Ansicht nur, wenn sich die
  Rechte tatsächlich geändert haben. Ohne Recht: Knöpfe, Menüeinträge, Fenster und Bearbeitungsfelder werden nicht angezeigt
  (Stammdaten von Versorgern, Ärzten und Dokumenten dann als reine Anzeige); Seiten ohne Recht (z. B. Neuer Patient,
  Benutzerverwaltung, Plan-Editor) leiten still auf die übergeordnete Seite. Ist ein Fenster offen, während das Recht wegfällt,
  schließt es und bleibt zu, auch wenn das Recht später zurückkommt. Abgelehnte Aktionen melden nur „Diese Aktion steht nicht mehr
  zur Verfügung. Die Ansicht wurde aktualisiert.“ – ohne Namen des Rechts. Kein Chip „nur lesen“ mehr. Der Server prüft weiter jede
  Anfrage (Ausblenden ersetzt keine Prüfung).
- **Validierung / Fehlerfälle:** unverändert 403 vom Server; die Oberfläche übersetzt sie wie beschrieben.
- **Tabellen:** keine
- **Teststatus:** Backend-Test grün (`RechteJeGruppe.test_rechte_stand_im_antwortkopf`: Kopf stabil, ändert sich mit dem Entzug, fehlt
  ohne Anmeldung). Browsertests grün: `admin.spec.ts` „Recht während der Sitzung entzogen: Aktion verschwindet ohne neue Anmeldung,
  Ablehnung nur neutral“ (offenes Abschluss-Fenster, Admin entzieht das Recht, Klick → Fenster weg, neutraler Hinweis, Eintrag weg,
  Akte nicht abgeschlossen; Recht zurück → Eintrag erscheint ohne Anmeldung, Fenster geht nicht von selbst auf; Erfassen entzogen →
  Kontakt/Gewicht im Kopf beim nächsten Seitenwechsel weg), `admin.spec.ts` Betrachter auf `/admin/benutzer` → Startseite ohne
  Rechte-Meldung, `patienten.spec.ts` `/patienten/neu` ohne Recht → Patientenliste, `versorger.spec.ts` Betrachter sieht
  Stammdaten nur als Anzeige.
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## I · Audit und Unveränderlichkeit

### F58 Audit-Log lesen und filtern
- **Ansicht:** 20 Audit-Log
- **Endpunkt:** `GET /api/protokoll/?gruppe=anmeldung,fehlversuch,benutzer,vorlage,backup,export,abschluss,dokument,datenschutz&benutzer&von&bis&search`
  → `[{id, zeitpunkt, art, art_name, gruppe, gruppe_name, beschreibung, benutzer, person, benutzername, objekt, details, ip, geraet}]`
- **Logik:** `beschreibung` wie im Entwurf („Anmeldung mit 2FA“, „Falsches Passwort (3. Versuch)“, „5 falsche Passwörter in
  4 Minuten, Konto gesperrt“, „Benutzer k.oezdemir angelegt (Mitarbeiter), Einmal-Passwort erzeugt“, „Akte Weber, Anna
  (Nr. 0231) abgeschlossen, Anlass: verstorben“, „Grenzwert „Kontakt überfällig“ von 6 auf 12 Monate geändert“).
  Hinweis auf gesperrte Konten: F08.
- **Validierung:** Recht „Audit-Log lesen“ (Standard: Mediziner, Admin); unbekannte Gruppe → 400.
- **Datenschutz (Runde 4):** Gruppe „Datenschutz“. Einträge zu einer endgültig gelöschten Akte bleiben ohne Namen und Inhalte
  („… – Angaben mit der Akte gelöscht“, F80). Einträge zu einer Akte mit eingeschränkter Verarbeitung sieht ohne Namen, wer
  keine Einsicht nehmen dürfte (F79). Aufbewahrung des Protokolls: F83.
- **Gerät:** IP-Adresse und Browser – das reicht (U8 geklärt 01.10.2026), kein eigener Gerätename.
- **Teststatus:** Backend-Tests grün (`test_sperre_nach_fehlversuchen`, `test_abschliessen_mit_recht`, `test_grenzen_und_rechte`).
  Browsertests grün: `admin.spec.ts` „Benutzer anlegen, Einmal-Kennwort, sperren und entsperren“ (Gruppe „Benutzer“), `admin.spec.ts` „Fünf falsche Passwörter sperren das Konto; Admin sieht den Hinweis, setzt 2FA zurück und entsperrt“ (Hinweis, Gruppe „Fehlversuch“), `admin.spec.ts` „Administration je Recht: Betrachter sieht nichts, Mitarbeiter Vorlagen, Mediziner Vorlagen und Audit-Log“; Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F59 Audit-Log als PDF
- **Ansicht:** 20 Audit-Log („Als PDF“ mit den gewählten Filtern)
- **Endpunkt:** `GET /api/protokoll/pdf/?gruppe&benutzer&von&bis&search` → PDF (Zeitpunkt, Person, Art, Details, Gerät/Adresse);
  der Export wird selbst protokolliert.
- **Teststatus:** Backend-Test grün (`vorlagen.WeiterePdfs.test_audit_log_als_pdf`). Browsertest grün: `pdf-ausgaben.spec.ts`
  „Audit-Log für den gewählten Zeitraum als PDF; der Export steht danach im Audit-Log“ (Lauf 36921980921, Commit `ca9f858`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F60 Unveränderlichkeit
- **Umsetzung:** PostgreSQL-Trigger (`audit/schutz.py`) auf allen Historientabellen und `audit_systemereignis` (kein UPDATE,
  DELETE, TRUNCATE), auf `patienten_kontakt` (nur einmaliges Storno), auf `infusionen_infusionsplan` (nach Freigabe nur
  „aktuell → abgelöst“), auf `infusionen_infusionsplan_vitamine` (Zuordnung nur im Entwurf). Ausnahme nur im Wartungsmodus – und das Schwärzen eines endgültig gelöschten
  Dokuments (F73, Art. 17 DSGVO): nur Titel, Dateiname, Notiz und Datum genau dieses Dokuments, nur durch „[entfernt]“.
  Im Wartungsmodus (nur für die Dauer des Vorgangs, in derselben Transaktion) laufen außerdem das endgültige Löschen einer
  Akte (F80) und die Bereinigung des Audit-Logs nach der eingestellten Aufbewahrung (F83). Das Löschprotokoll
  (`patienten_loeschprotokoll`) kann nur ergänzt werden (Trigger „nur anfügen“).
- **Teststatus:** Backend-Tests grün (`test_historie_ist_unveraenderlich`, `test_trigger_verhindert_aenderung_in_der_datenbank`,
  `test_vitamine_freigegebener_plaene_in_der_datenbank_geschuetzt`). Browsertests grün: `akte.spec.ts` „Kontakt mit Wiedervorlage erfassen, suchen, stornieren“ (Kontakt nur stornieren),
  `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“ (freigegebener Plan ohne „Bearbeiten“), `dokumente.spec.ts` „Dokumente hochladen, Typ am Inhalt prüfen, Metadaten ändern, ausblenden, herunterladen; Verlauf“ (Verlauf nur lesend).
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## J · Backup und Wiederherstellung

Festlegungen 02.10.2026: Verschlüsselung **symmetrisch mit einem Passwort**, das die Administration in der Oberfläche
festlegt (U20); das Passwort liegt nur auf dem Server, damit die nächtliche Sicherung ohne Eingabe läuft, und wird
ausgedruckt im Tresor verwahrt. Sicherungen 30 Tage auf dem Server, täglich um 02:00. Übertragung in einen WebDAV-Ordner
(Nextcloud) mit rclone, Ziel und Zeitfenster pflegt die Administration selbst (U9, Wunsch 01.10.2026). Alles, was den
Server betrifft, läuft über den Systemagenten (F87): Das Backend legt Aufträge ab, der Agent (root) führt sie aus und
schreibt `status/sicherung.json` (Bestand, Verschlüsselung, Ziel ohne Zugangsdaten, Übertragung, Speicher).
Recht „Sicherungen verwalten“ (Standard: nur Admin; Testzugänge nie).

### F61 Tägliche verschlüsselte Sicherung
- **Ansicht:** 11 Backup › Verschlüsselung: Stand (Passwort Nr., festgelegt am, von), Liste der Passwörter, mit denen noch
  Sicherungen verschlüsselt sind; „Passwort festlegen“ (Vorschlag mit 20 Zeichen ohne verwechselbare Zeichen, Wiederholung,
  Admin-Passwort + Code), danach „Passwortblatt drucken“; „Passwort prüfen“ (z. B. das Blatt aus dem Tresor).
- **Endpunkte:** `POST /api/backup/passwort/` `{passwort, passwort2, kennwort, code}` → 201 Auftrag;
  `POST /api/backup/passwort/pruefen/` `{passwort}` → `{stimmt, nr, aktuell}`;
  `POST /api/backup/passwortblatt/` `{passwort}` → PDF (nur mit einem hinterlegten Passwort).
- **Logik:** `/usr/local/sbin/epm-backup --art nachts` per systemd-Timer um **02:00** (`--art von_hand|vor_update|
  vor_aenderung|vor_wiederherstellung`, `--von BENUTZER` bei Aufträgen): `pg_dump`, Dokumente als `.tar.gz`, Löschliste,
  je mit GnuPG verschlüsselt (OpenPGP, AES-256, S2K SHA-512, ohne Schlüsselbund und Zwischenspeicher), dazu
  `epm_<Stempel>.sha256` und `epm_<Stempel>.json` (Zeitpunkt, Art, ausgelöst von, Passwort-Nr., EPM-Version, Dateien –
  keine Patientendaten). Ohne Passwort unverschlüsselt mit Hinweis (Oberfläche und Startseite warnen). Bricht der
  Lauf ab (z. B. `tar` scheitert nach gelungenem Dump), entfernt das Skript alle Dateien dieses Laufs – es bleibt keine
  unvollständige Sicherung liegen (O-27; Test `EchterAgent.test_gescheiterte_sicherung_hinterlaesst_nichts`). Das Passwort
  schreibt der Agent nach `/etc/epm/sicherung/passwort-<Nr.>` (0600, root), die aktuelle Nummer nach `aktuell`; ein neues
  Passwort gilt ab der nächsten Sicherung, ältere bleiben, bis keine Sicherung sie mehr braucht (dann gelöscht). Für das
  Backend schreibt der Agent nur einen scrypt-Prüfwert (`status/sicherung-pruefwerte.json`). Das Passwort steht nie in
  der Datenbank, im Audit-Log, in einer Antwort oder im Status; die Auftragsdatei (0600) löscht der Agent sofort nach dem
  Lesen. Das Passwortblatt druckt das Passwort, das die Oberfläche gerade mitschickt, nach Prüfung gegen den Prüfwert –
  mit Anleitung zum Entschlüsseln ohne EPM (`gpg -d`) und der Liste der noch gebrauchten Passwörter.
- **Validierung / Fehlerfälle:** 16–200 Zeichen, keine Steuerzeichen, kein Leerzeichen am Anfang/Ende, Wiederholung gleich,
  nicht das eigene Anmelde-Passwort, nicht schon hinterlegt (400 je Feld); Admin-Passwort/Code falsch 400; Prüfen und
  Passwortblatt: jeder Versuch im Audit-Log, nach 5 falschen Passwörtern in 15 Minuten 429.
- **Teststatus:** Backend-Tests `system/test_sicherung.py` (`Passwort.*`, `EchterAgent.test_passwort_sicherung_pruefen_und_blatt`:
  Backend → echter Agent → echtes `epm-backup.sh` mit GnuPG → Entschlüsseln mit dem Passwort, mit einem anderen nicht;
  Passwort nirgends außer in `/etc/epm/sicherung`). Browsertest `zzz-sicherung.spec.ts` „Sicherungs-Passwort festlegen und
  Passwortblatt drucken“ (Passwort nicht in der Datenbank – geprüft an einem `pg_dump` –, nicht im Status) und
  „„Jetzt sichern“ verschlüsselt mit dem Passwort aus der Oberfläche“ (Datei auf dem Server mit `gpg` entschlüsselt,
  Prüfsummen).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F62 Sicherungen anzeigen, „Jetzt sichern“
- **Ansicht:** 11 Backup (Entwurf): Kopf mit „Jetzt sichern“, drei Karten (Letzte Sicherung, Übertragung, Speicher), Tabelle
  der Sicherungen (Zeitpunkt, Art, Größe, Schutz, Übertragung, „Wiederherstellen“), Warnung zum Wiederherstellen,
  Verschlüsselung, Übertragung, Tätigkeiten mit Ausgabe und „Zurückziehen“. 2 Start: Chip in der Kopfzeile
  („Backup heute 02:00 erfolgreich“ bzw. der wichtigste Hinweis), für alle sichtbar, mit dem Recht ein Link zur Seite.
- **Endpunkte:** `GET /api/backup/` → `{agent, status, probelauf, kurz: {zustand, letzte_am, verschluesselt, titel,
  hinweise}, letzte, sicherungen: [{stempel, zeitpunkt, art, art_name, ausgeloest_von, verschluesselt, passwort_nr, groesse,
  dateien, uebertragen, uebertragen_am, wiederherstellbar, …}], verschluesselung, ziel, uebertragung, speicher: {belegt,
  gesamt, frei, sicherungen}, aufbewahrung_tage, naechste_sicherung, auftraege, aktionen, minuten, angemeldet}`;
  `POST /api/backup/jetzt/` → 201 Auftrag; `POST /api/backup/auftraege/<kennung>/abbrechen/`.
  `GET /api/startseite/` enthält `sicherung` (siehe F13).
- **Logik:** Zustand: Fehler, wenn der Agent seit 3 Minuten nichts meldet, es keine Sicherung gibt, die letzte älter als 36 h
  ist oder der nächtliche Lauf gescheitert ist; Warnung bei unverschlüsselter letzter Sicherung, ohne Übertragungsziel,
  bei fehlgeschlagener Übertragung oder einer verschlüsselten Sicherung, die seit über einem Tag nicht übertragen ist.
  Aufträge der Seite stehen im Audit-Log unter „Backup“.
- **Teststatus:** Backend-Tests `system/test_sicherung.py` (`Rechte.*`, `Uebersicht.*` inkl. Zustand der Startseite).
  Browsertests `zzz-sicherung.spec.ts` (Recht, „Jetzt sichern“, Tabelle, Startseite).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F63 Wiederherstellen
- **Ansicht:** 11 Backup › „Wiederherstellen“ je Sicherung: Angaben der Sicherung, Warnung, Beginn (sofort oder in 5–60
  Minuten) mit Hinweis an alle Angemeldeten, Admin-Passwort und Code. Während es läuft, ein Hinweis auf der Seite; danach
  müssen sich alle neu anmelden.
- **Endpunkt:** `POST /api/backup/<stempel>/wiederherstellen/` `{kennwort, code, minuten, hinweis?}` → 201 Auftrag.
- **Logik (Agent):** zuerst eine Sicherung des jetzigen Stands (`vor_wiederherstellung`) – schlägt sie fehl, passiert
  nichts. Dann, während EPM noch läuft: Prüfsummen, entschlüsseln (Passwort Nr. der Sicherung), Dump mit
  `pg_restore --list` prüfen, Dokumente in einen Zwischenordner auspacken. Erst dann Backend und Webserver anhalten, Dump in
  eine neue Datenbank einspielen, Datenbanken und Dokumentordner tauschen (Rechte bleiben), starten, auf „gesund“ warten.
  Schlägt ein Schritt fehl, wird der vorige Stand zurückgetauscht und läuft weiter. Die Löschliste bleibt unangetastet; das
  Backend löscht beim Start erneut, was die Sicherung zurückgebracht hat (F73, F80). Der Agent ruft das Nachholen danach
  noch einmal mit `--streng` auf und knüpft seine Meldung an das Ergebnis: „… wurden erneut angewendet“ oder „ACHTUNG:
  Löschungen … konnten nicht vollständig nachgeholt werden“. Das Nachholen hält seinen Stand neben der Löschliste fest
  (`data/loeschliste/nachholen.json`, übersteht eine Wiederherstellung) und schreibt ins Audit-Log (Gruppe „System“),
  wenn es etwas nachgeholt hat oder etwas nicht ging (Fehler eines Schritts, nicht nachgeholte Akten, unlesbare Zeilen
  der Löschliste) – derselbe Fehler nicht bei jedem Start erneut. Ein Fehler erscheint auf der Backup-Seite und in der
  Kopfzeile der Startseite („Löschungen nicht nachgeholt“), bis ein Lauf ohne Fehler durchgeht (Gegenprüfung 02.10.2026,
  O-28; Tests `patienten/test_datenschutz.py` `test_nachholen_meldet_was_nicht_ging`, `system/test_sicherung.py`
  `test_nicht_nachgeholte_loeschungen_sind_ein_fehler`). Vor dem Start vermerkt der Agent die
  Wiederherstellung in `status/wiederherstellungen.json`; das Backend trägt sie beim Start ins Audit-Log der
  zurückgespielten Datenbank ein (wer, wann, welche Sicherung, in welcher Sicherung der Stand davor liegt), legt den
  Auftrag wieder an und beendet **alle Anmeldungen** (`manage.py epm_wiederherstellungen_nachtragen`).
- **Validierung / Fehlerfälle:** Admin-Passwort/Code 400; unbekannte Sicherung 404; ohne Dokumente oder mit `age`
  verschlüsselt 409; Agent meldet sich nicht 409 (ein wartender Auftrag würde zu einem unerwarteten Zeitpunkt zurückspielen);
  schon beauftragt 409.
- **Teststatus:** Backend-Tests `system/test_sicherung.py` (`Wiederherstellen.*` inkl. Nachtragen und Ende aller Sitzungen).
  Browsertest `zzz-sicherung.spec.ts` „Wiederherstellen mit Passwort und 2FA“: echter Ablauf im Stack – danach ist ein
  später angelegter Benutzer weg, alle Anmeldungen sind beendet, Auftrag erledigt, Stand davor als eigene Sicherung,
  Eintrag im Audit-Log. Vorher von Hand geprüft: Rücktausch, wenn das Backend nicht startet.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F64 Übertragung zur Nextcloud/NAS
- **Ansicht:** 11 Backup › Übertragung: Ziel (WebDAV-Adresse, Benutzer, Ordner, Zeitfenster), zuletzt übertragen, offene
  Sicherungen, letzter Fehler; „Ziel festlegen/ändern“ (Admin-Passwort + Code), „Verbindung testen“, „Jetzt übertragen“,
  „Ziel entfernen“ (Admin-Passwort + Code). Tabelle: „übertragen …“ bzw. „wartet auf Zeitfenster“.
- **Endpunkte:** `POST /api/backup/ziel/` `{url, benutzer, ziel_kennwort?, ordner, von, bis, kennwort, code}`;
  `POST /api/backup/ziel/entfernen/` `{kennwort, code}`; `POST /api/backup/ziel/testen/`; `POST /api/backup/uebertragen/`.
- **Logik:** Zugang nur auf dem Server: `/etc/epm/sicherung/rclone.conf` (0600, Passwort mit `rclone obscure`), Angaben
  ohne Passwort in `ziel.json`; leeres Passwort beim Ändern = bisheriges bleibt. Der Status-Lauf (jede Minute) startet im
  Zeitfenster die Übertragung im Hintergrund (`epm-uebertragung.service`), nach einem Fehler frühestens 15 Minuten später
  erneut, höchstens bis zum Ende des Fensters. Übertragen werden nur verschlüsselte Sicherungen mit Prüfsummen und Angaben,
  `rclone copy` und danach `rclone check`; danach entfernt der Agent im Ziel EPM-Sicherungen, die älter als die Aufbewahrung im Ziel sind (Festlegung 03.10.2026: Standard 30 Tage, einstellbar nie/14–365 Tage, die jüngste bleibt immer, andere Dateien nie; `im_ziel_veraltet`, Backend-Test `test_agent_aufbewahrung_im_ziel`, Browsertest `zzz-sicherung.spec.ts`); „Jetzt übertragen“ auch außerhalb des Fensters. Ein neues Ziel
  bekommt alle vorhandenen verschlüsselten Sicherungen. Der Server erreicht das Ziel über den Proxy der OPNsense
  (`EPM_APT_PROXY`); die Adresse muss dort freigegeben sein.
- **Validierung / Fehlerfälle:** nur `https://` (`http://` nur für localhost – Test), keine Zugangsdaten in der Adresse,
  Ordner ohne `\ : ..`, Zeiten HH:MM (von = bis: ganztägig), Passwort beim ersten Festlegen Pflicht (400 je Feld).
- **Teststatus:** Backend-Tests `system/test_sicherung.py` (`Ziel.*`: Prüfungen, Zugang nur in der Auftragsdatei).
  Browsertest `zzz-sicherung.spec.ts` „Übertragungsziel festlegen, Verbindung testen, von Hand und im Zeitfenster
  übertragen“ gegen einen WebDAV-Server (`rclone serve webdav` in `ci-stack.sh`): Dateien im Ziel, nur verschlüsselt,
  automatische Übertragung im Fenster.
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## K · Migration

### F65 Import der Altdaten
- **Wunsch 02.10.2026:** statt eines Befehls auf dem Server ein Werkzeug mit Oberfläche, in dem sich die Zuordnungen
  prüfen und korrigieren lassen. Festlegungen dazu: Ort = Administration › Import (nur Admin, Kennwort + 2FA); Import nur
  in ein System ohne echte Akten, beliebig oft als Probelauf, bis zum Abschließen vollständig zurücknehmbar und mit
  frischem Dump wiederholbar; im Altsystem gelöschte Patienten werden je Patient im Werkzeug entschieden (Standard:
  nicht übernehmen; sonst als abgeschlossene Akte mit Anlass). Anleitung: `docs/ALTDATEN-IMPORT.md`.
- **Ansicht:** Administration › Import mit den Schritten 1 · Dump, 2 · Zuordnungen (Tabellen und Spalten, Benutzer,
  Versorger, Katheter und Werte, Präparate, Gelöschte Patienten, Auffälligkeiten), 3 · Probelauf und Import,
  4 · Dokumente, 5 · Abschließen, Protokolle. Jede Entscheidung wird sofort gespeichert; „Vorschlag“ nimmt sie zurück.
  Offene Punkte stehen oben und sperren Probelauf und Import.
- **Recht:** `altdaten_importieren` („Altdaten übernehmen (Import)“) – fest bei der Rolle Admin, anderen Rollen nicht
  erteilbar, nicht für Testbenutzer. Das ist die eine Ausnahme von „Admins schreiben Patientendaten nur bei
  Testpatienten“ (U12): Die Übernahme legt echte Akten an (U26).
- **Endpunkte** (alle nur mit dem Recht; `409 {"fehler"}` bei einem Hindernis):
  `GET /api/altimport/` (Status, Dump, Tabellen, echte Akten, Bestand der Übernahme, letzte 30 Läufe);
  `POST /api/altimport/dump/` (multipart `datei`, .sql oder .sql.gz, höchstens 50 MB, entpackt 300 MB; `400 {"datei"}`),
  `DELETE /api/altimport/dump/`; `GET /api/altimport/zuordnung/` (Stand der Auswertung, Hindernisse, Bestand des EPM),
  `PATCH /api/altimport/zuordnung/` `{bereich, aenderungen}` (Bereiche `tabellen`, `tabellen_ignoriert`, `spalten`,
  `spalten_ignoriert`, `benutzer`, `versorger`, `werte`, `praeparate`, `geloeschte`, `korrekturen`; `null` = Vorschlag);
  `POST /api/altimport/probelauf/`; `POST /api/altimport/import/` `{kennwort, code}`;
  `GET`/`POST /api/altimport/dokumente/` (Überblick bzw. nächste Etappe); `POST /api/altimport/zuruecknehmen/`
  `{kennwort, code, bestaetigung: "ZURÜCKNEHMEN"}`; `POST /api/altimport/abschliessen/` `{kennwort, code, bestaetigung:
  "ABSCHLIESSEN", ohne_dokumente?}`; `GET /api/altimport/laeufe/<id>/` und `…/text/` (Protokoll als Textdatei).
- **Logik – Dump:** eigener Leser für MySQL-Dumps (mysqldump und phpMyAdmin, mit und ohne Spaltenliste, gepackt, UTF-8
  oder Windows-1252); nicht Lesbares wird mit Stelle gemeldet, nichts übersprungen. Kennwort-Spalten werden beim
  Einlesen geleert und nie gespeichert (Regel 1; erkannt am Namen oder am Inhalt). `TIMESTAMP`-Spalten stehen im Dump
  in UTC (`SET TIME_ZONE='+00:00'`) und werden beim Laden in Ortszeit umgerechnet, `DATETIME` bleibt (Hinweis am Dump).
  Der Dump liegt bis zum Abschließen in der Datenbank (`altimport_alttabelle`), nicht als Datei.
- **Logik – Zuordnungen:** Das Werkzeug schlägt vor, die Administration korrigiert. Tabellen und Spalten werden am Namen
  erkannt (die Spaltennamen des Altsystems sind nicht gesichert – daher zuordenbar); nicht zugeordnete Spalten und
  Tabellen müssen ausdrücklich „nicht übernommen“ werden. Benutzer: Konto im Altsystem → neues Konto mit Rolle nach
  den Rechten des Altsystems (ohne Kennwort; danach Einmal-Kennwort unter Benutzer), nur als Bearbeiter genannte Namen →
  historischer Benutzer ohne Login (Regel 8), oder vorhandener Benutzer. Versorger: gleiche Firma = ein Versorger mit
  Ansprechpartnern (Regel 4). Katheter → Auswahlliste (Regel 9), Nickelallergie und Geschlecht → feste Werte
  (Regel 10). Präparate: vorgeschlagen wird nur bei genauer Übereinstimmung (Groß-/Kleinschreibung, Leerzeichen,
  „20%“/„20 %“ egal); alles andere wird einem Präparat zugeordnet, neu angelegt, in die Bemerkung geschrieben oder
  nicht übernommen (Regel 16). Auffälligkeiten (fehlendes Geburtsdatum, unlesbare oder unplausible Werte, vierstellige
  PLZ …): je Wert „Wert eintragen“, „leer lassen“, „unverändert übernehmen“ oder „nicht übernehmen“; eine Korrektur gilt
  nur, solange im Dump derselbe Wert steht, und nur, wenn sie die Auffälligkeit behebt. Die Zuordnungen bleiben
  unabhängig vom Dump erhalten und gelten für den frischen Dump zum Go-live weiter.
- **Logik – Umsetzung nach den Regeln der Datenanalyse:** Patientennummer = PatientenID (Regel 15; Nummern ab 9001,
  doppelte und im Löschprotokoll stehende Nummern sperren). Gewichte 0/leer/9999 nicht (Regel 5), Messdatum aus
  `lastchange`, als ungenau und „Altsystem“ gekennzeichnet (Regel 2). Größe 0 → leer, unter 3 → ×100 (Regel 6).
  „-“ → leer (Regel 7). Doppelt kodierte Umlaute repariert (ftfy, Regel 3). HTML bereinigt (Regel 11); Linkziele und
  Bilder bleiben als Text bzw. Vermerk stehen. Infusionspläne (Regeln 13, 14, 16): jüngster Plan je Patient „aktuell“,
  ältere „abgelöst“ mit Vorgängerkette, Herkunft „Altsystem“ (ohne Freigabe und ohne gespeicherte PDF), Gesamtvolumen
  = `ml` des Altsystems, Mengen 0 → leer, Energie nur dann „manuell“, wenn sie von der Berechnung abweicht,
  Protonenpumpenhemmer-Codes und Zeiten, Vitamine „A | B“. Einträge tragen in der Historie Bearbeiter und Zeitpunkt
  des Altsystems (Grund „Aus dem Altsystem übernommen“). Nichts geht still verloren: Was in kein Feld passt (zu lang,
  ungültige E-Mail, unbekannte Werte), steht in der Bemerkung; jede Regel zählt im Protokoll, mit Nummern, ohne Namen.
- **Logik – Schreiben:** Probelauf = derselbe Schreibvorgang in einer Transaktion, die zurückgerollt wird; danach
  Zählung „im Altsystem / wird übernommen / nicht übernommen (warum)“. Import nur ohne echte Akten und ohne offene
  Punkte, mit Kennwort und 2FA; danach Prüfung der geschriebenen Mengen gegen die Berechnung – bei Abweichung wird
  nichts gespeichert. Angelegt werden nur die Stammdaten, die übernommene Datensätze brauchen. Zurücknehmen entfernt
  die übernommenen Akten mit allen Einträgen, Historie und Dateien (auch seither Erfasstes) sowie die vom Import
  angelegten Stammdaten und Benutzer, soweit nichts anderes sie verwendet; Dump und Zuordnungen bleiben. Abschließen
  löscht Dump, Zuordnungen und die Nummern in den Protokollen; danach ist alles gesperrt.
- **Logik – Dokumente:** aus `data/import/PatData/<PatientenID des Altsystems>/` auf dem Server (nur lesend
  eingebunden), in Etappen und fortsetzbar; PDF, Bilder (auch GIF, BMP, TIFF, WebP) und Text nach Inhalt; Titel =
  Dateiname, Typ „Sonstiges“, Datum aus PDF/EXIF, sonst Dateidatum; erscheinen unter „Nach und nach prüfen“ (F28).
  Nicht übernommen und aufgelistet: `.php`, `.html`, `.js`, `.svg`, andere Dateitypen, leere Dateien, Verknüpfungen,
  Ordner ohne übernommenen Patienten, nicht lesbare Ordner und Dateien (zählen beim Abschließen wie offene Dokumente).
- **Audit-Log (Gruppe „System“):** Dump geladen/entfernt, Import, Dokumente, Zurücknehmen, Abschließen; neue Konten als
  „bei der Übernahme der Altdaten angelegt“.
- **Tabellen:** `altimport_importstand`, `altimport_alttabelle`, `altimport_importlauf`, `altimport_importobjekt`;
  `infusionen_infusionsplan.herkunft` (neu: `epm` | `altsystem`).
- **Server:** `compose.yaml` bindet `./data/import` nur lesend nach `/data/import` (`EPM_IMPORT`); `rollout/04-projekt.sh`
  legt den Ordner an. Neue Abhängigkeit `ftfy`.
- **Unabhängige Prüfung (zweite Instanz, nur lesend, 02.10.2026):** 13 Befunde, alle behoben (u. a. untaugliche
  Korrektur entsperrte einen offenen Punkt; TIMESTAMP in UTC; Dokumentenordner bei korrigierter Nummer; unlesbare
  Ordner; Fehlertexte mit Zeileninhalt).
- **Teststatus:** Backend-Tests `altimport/test_rein.py` (Dump-Leser, Werte, Umsetzung nach den Regeln, Befunde der
  Prüfung – reines Python) und `altimport/tests.py` gegen PostgreSQL (Rechte, Dump laden, Zuordnungen, Probelauf schreibt
  nichts, Import mit Historie und Schutz-Triggern, übernommene Akten im Alltag, Dokumente in Etappen, Zurücknehmen und
  erneut übernehmen, Abschließen). Browsertest `aa-import.spec.ts` (läuft als erste Datei, solange es keine echten
  Akten gibt): nur Admin; Dump laden und alle Bereiche der Zuordnungen in der Oberfläche korrigieren; Probelauf, Import
  mit Passwort und Notfall-Code, übernommene Akte als Mediziner (Gewichte, Kontakte, Pläne, Dokumente), Dokumente aus
  dem Ordner des CI-Stacks, Zurücknehmen, Protokolle, Audit-Log. Neustart: `zz-neustart.spec.ts` (Dump, Zuordnungen
  und Läufe sind nach dem Neustart da; mit echten Akten ist der Import gesperrt). Bildschirmfotos der Seite beim
  manuellen Start des Workflows (Branch `bildschirmfotos`).
- **Grenze des Nachweises:** Getestet ist mit einem erfundenen Dump, der die 17 Regeln und die bekannten Auffälligkeiten
  nachstellt. Der echte Dump ist hier nie gelaufen – der erste Probelauf mit dem frischen Dump zeigt, ob Spaltennamen
  und Inhalte so sind wie in der Datenanalyse angenommen (dafür sind die Zuordnungen korrigierbar).
- **Status:** ABGESCHLOSSEN UND GETESTET (Werkzeug); die Übernahme der echten Daten selbst ist Rollout-Schritt 7

---

## L · Kontaktdaten der Akte (Runde 3, Festlegung 01.10.2026)

Rückmeldung aus dem Testsystem: Unter den Stammdaten stand nur ein Telefon; je Patient gibt es aber mehrere
Ansprechpersonen (Mutter, Vater, Betreuer/in …), und Ärzte brauchen gepflegte Kontaktdaten. Entscheidungen des Nutzers:
gemeinsame Ärzteliste; „kein“ und „nicht erfasst“ getrennt; Bezugspersonen mit Beziehung als pflegbarer Liste und
„Auskunft erlaubt“. Nichts wird gelöscht: Nicht mehr Aktuelles wird markiert und bleibt im Verlauf der Akte.

### F67 Gemeinsame Ärzteliste pflegen
- **Ansicht:** Ärzte (Seitenleiste, neu), Link „Neu anlegen“ bei „Neuer Patient“
- **Endpunkte:** `GET/POST /api/aerzte/?aktiv&search`, `PATCH /api/aerzte/{id}/`, `GET /api/aerzte/{id}/patienten/`;
  kein Löschen (405), Deaktivieren über `aktiv: false`
- **Felder:** `name` (Pflicht), `praxis`, `fachrichtung`, `strasse`, `plz`, `ort`, `telefon`, `fax`, `email`, `notiz`, `aktiv`;
  nur lesend `patienten_anzahl` (Patienten in Betreuung ohne Testpatienten)
- **Rechte:** Recht „Versorger, Ansprechpartner und Ärzte pflegen“ (bisher „Versorger und Ansprechpartner pflegen“), lesen alle
- **Tabellen:** `stammdaten_arzt` (+ Historie), Audit-Log „Stammdaten“
- **Teststatus:** Backend-Test grün (`Kontaktdaten.test_aerzteliste_und_zuordnung`). Browsertest grün: `akte.spec.ts`
  „Ärzte aus der gemeinsamen Liste zuordnen, Bezugspersonen mit Auskunft pflegen“ (anlegen, Telefon ändern wirkt in der Akte,
  Liste der Patienten); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F68 Ärzte eines Patienten
- **Endpunkte:** `GET/POST /api/patient-aerzte/?patient&aktiv`, `PATCH /api/patient-aerzte/{id}/` (Rolle, Notiz, `aktiv`); 405 bei DELETE;
  beim Anlegen eines Patienten `aufnahme_hausarzt` (Arzt-ID) → Zuordnung „Hausarzt“ in derselben Transaktion
- **Rollen:** hausarzt, facharzt, ueberweisend, klinik, sonstige; je Arzt und Rolle nur eine aktive Zuordnung (DB-Constraint)
- **Kopf der Akte:** `kopf.hausarzt {id, name, praxis, telefon}`, `zaehler.aerzte`
- **Validierung:** Arzt nicht tauschbar (neu zuordnen); deaktivierte Ärzte nicht neu zuordenbar; Recht „Patienten anlegen, Diagnose,
  Therapie, Stammdaten ändern“; Admin nur bei Testpatienten; Akte offen (409)
- **Verlauf:** Bereich `aerzte`, Aktionen angelegt / geändert / nicht mehr zuständig / wieder zuständig
- **Bestand:** Das bisherige Freitextfeld `hausarzt` bleibt (Altdaten) und wird angezeigt, solange es gefüllt ist.
- **Tabellen:** `patienten_patientarzt` (+ Historie)
- **Teststatus:** Backend-Test grün (`Kontaktdaten.test_aerzteliste_und_zuordnung`). Browsertests grün: `akte.spec.ts` (s. F67),
  `patienten.spec.ts` „Neuer Patient: Prüfung, Doppelung, Anlegen mit Gewicht bei Aufnahme“ (Hausarzt beim Anlegen).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F69 Bezugspersonen
- **Endpunkte:** `GET/POST /api/bezugspersonen/?patient&aktiv`, `PATCH /api/bezugspersonen/{id}/`; 405 bei DELETE
- **Felder:** `beziehung` (Liste „beziehung“: Mutter, Vater, Ehepartner/in, Kind, Betreuer/in (gesetzlich), Pflegedienst, Sonstige –
  unter Vorlagen › Auswahllisten erweiterbar), `name` (Pflicht), `telefon`, `mobil`, `email`, `strasse`, `plz`, `ort`, `notiz`,
  `auskunft_erlaubt` (Schweigepflichtentbindung liegt vor), `aktiv`
- **Kopf der Akte:** „Auskunft an“ = aktive Personen mit `auskunft_erlaubt` (`kopf.auskunft`), `zaehler.bezugspersonen`
- **Validierung/Rechte:** wie F68; Beziehung nur aus der Liste „beziehung“
- **Verlauf:** Bereich `bezugspersonen`, Aktionen angelegt / geändert / nicht mehr aktuell / wieder aktuell
- **Tabellen:** `patienten_bezugsperson` (+ Historie)
- **Teststatus:** Backend-Tests grün (`Kontaktdaten.test_bezugspersonen_*`, `test_beziehungsliste_wie_festgelegt`, `Musterdaten`).
  Browsertest grün: `akte.spec.ts` (s. F67); Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F70 „kein“ Katheter/Versorger, Nickelallergie als Auswahl
- **Felder:** `kein_katheter`, `kein_versorger` (bool) am Patienten; DB-Constraints verhindern „kein“ zusammen mit einer Auswahl.
  Wer einen Katheter/Versorger wählt, hebt „kein“ auf.
- **Wirkung:** Hinweis „Versorger nicht erfasst“ und Prüfliste nur noch, wenn weder Versorger noch „kein“ gesetzt ist; Kopf und Liste
  zeigen „kein“ bzw. „nicht erfasst“. Nickelallergie im Dialog „Stammdaten bearbeiten“ als Auswahlliste (nicht erfasst/ja/nein).
- **Teststatus:** Backend-Test grün (`Kontaktdaten.test_kein_katheter_und_kein_versorger`). Browsertest grün: `akte.spec.ts`
  „Stammdaten bearbeiten, Akte abschließen …“; Neustart geprüft in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### Weitere Rückmeldungen aus dem Testsystem (Runde 3)
- **Blau auf Blau:** Links mit Knopf-Stil („Neuer Patient“, „Neuer Plan“, „Öffnen“) erbten die Linkfarbe, weil die Grundregel
  `a { color }` außerhalb einer CSS-Ebene stand und damit jede Komponentenregel schlug. Grundregeln liegen jetzt in `@layer base`.
  Browsertests prüfen den Kontrast ≥ 4,5:1 (`patienten.spec.ts`, `dokumente.spec.ts`).
- **Zähler „0 in Betreuung“:** Testpatienten zählen weiterhin nicht. Nur die Administration sieht ihre Anzahl getrennt
  („zusätzlich n Testpatienten“, „+n Test“; `GET /api/patienten/zaehler/` liefert `testpatienten` nur für Admins).
- **PDF-Vorschau:** Dokumente zeigen PDFs mit pdf.js in EPM (Canvas) statt mit dem PDF-Programm des Browsers (Adobe Reader blendete
  eine schwarze Leiste ein); große Ansicht mit Zoom. Offline, ohne eval/WebAssembly (CSP unverändert). Browsertest `dokumente.spec.ts`
  „PDF-Vorschau und Ansicht in EPM …“.

## M · Datenschutz nach DSGVO (Runde 4, Prüfung und Festlegungen vom 02.10.2026)

Anlass: Prüfung des Projekts auf Anpassungen nach DSGVO (Recht auf Löschung u. a.) im Abgleich mit den Pflichten bei
Patientendaten. Vorschriften, Abwägungen und offene Punkte stehen in `docs/DATENSCHUTZ.md`; hier steht, was EPM tut.
Angaben der Stiftung: Verantwortlich ist allein die Stiftung; Pläne gibt nur Prof. Masin frei, per E-Mail, Mitarbeiter
schließen im System ab; Sicherungen 30 Tage; Aufbewahrung 10 Jahre „soweit bekannt“ (U16).

Gemeinsam für F74–F81: Reiter „Datenschutz“ in der Akte (`/patienten/{id}/datenschutz`), Menüpunkt „Datenschutz“
(`/datenschutz`). Stand der Akte: `GET /api/patienten/{id}/datenschutz/` → `{aufbewahrung, einschraenkung, einsicht_bis,
erklaerungen, stand, pflicht, vorlagen, anfragen, kopien, loeschen}`. Migrationen: `patienten/0007_datenschutz`,
`stammdaten/0008_datenschutz`, `audit/0006_datenschutz`, `infusionen/0005_freigabe_auf_anordnung`,
`vorlagen/0002_datenschutz_freigabevermerk`. Audit-Log: neue Gruppe „Datenschutz“; Einträge zu Akten tragen seitdem
`details.patient_id`. Verlauf der Akte: neue Bereiche `erklaerungen` und `datenschutz`.

### F74 Aufbewahrungsfrist der Akte, Verlängerung im Einzelfall, „Abschluss prüfen“
- **Zweck:** Speicherbegrenzung (Art. 5 Abs. 1 e DSGVO): Die Frist beginnt mit dem Abschluss der Akte; danach darf (F80)
  gelöscht werden. Eine nie abgeschlossene Akte bliebe für immer – deshalb der Hinweis „Abschluss prüfen“.
- **Ansicht:** Akte › Datenschutz › Aufbewahrung; Banner der abgeschlossenen Akte („Aufbewahrung bis …“); Start und
  Patientenliste „Abschluss prüfen“; Vorlagen › Grenzwerte › Datenschutz
- **Endpunkte:** `aufbewahrung` in `GET /api/patienten/{id}/` und `…/datenschutz/` → `{jahre, regulaer_bis, verlaengert_bis,
  grund, bis, abgelaufen, beginn}`; `POST /api/patienten/{id}/aufbewahrung/` `{"bis": "JJJJ-MM-TT", "grund"}` bzw. `{"bis": null}`
  (Verlängerung zurücknehmen); `GET /api/patienten/?pruefen=abschluss_pruefen`
- **Logik:** `beginn` = Abschlussdatum – oder der Tag des letzten (nicht stornierten) Kontakts, wenn der später liegt: Das
  Abschlussdatum lässt sich rückwirkend eintragen (F20), ein Tippfehler im Jahr soll eine Akte nicht sofort löschbar
  machen. Regulär = Beginn + `aufbewahrung_jahre` (Einstellung, Standard 10; es gilt die aktuell eingestellte Zahl für
  alle Akten); `bis` = das spätere Datum aus regulärer Frist und Verlängerung; `abgelaufen`, wenn `bis` vor heute liegt. „Abschluss prüfen“: Akte in Betreuung, älter
  als `abschluss_pruefen_monate` (Standard 24), seitdem kein Kontakt und kein offener Termin in der Zukunft.
- **Validierung:** Verlängern mit Recht „Datenschutz: Anfragen entscheiden …“ (Standard: Mediziner; Admin nur
  Testpatienten); Datum in der Zukunft und nach der regulären Frist; Grund mindestens 10 Zeichen.
- **Tabellen:** `patienten_patient` (`aufbewahrung_bis`, `aufbewahrung_grund`) + Historie, `stammdaten_einstellungen`
- **Teststatus:** Backend-Tests grün (`test_datenschutz.Fristen.test_aufbewahrung_und_frist_der_anfragen` – auch: Abschluss
  elf Jahre zurückdatiert, Kontakt heute → nicht abgelaufen, nicht löschbar; `test_einstellungen` – auch: Mitarbeiter
  ändern die vier Datenschutz-Werte nicht; `test_abschluss_pruefen`, `Einschraenkung.test_aufbewahrung_im_einzelfall_verlaengern`).
  Browsertests grün: `datenschutz.spec.ts` „Anfrage mit Frist, Kopie der Akte, Löschwunsch → eingeschränkt, Einsicht mit
  Grund, Aufheben“ (Stand der Aufbewahrung in der Akte), „Grenzwerte: Fristen des Datenschutzes einstellen“ (Mediziner
  ändert, Mitarbeiter sieht die Werte nur) (Lauf 36969989383, Commit `34c627d`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F75 Erklärungen nachhalten
- **Zweck:** Nachweis, dass informiert wurde und eine Einwilligung bzw. Schweigepflichtentbindung vorliegt (Art. 7 Abs. 1,
  Art. 13 DSGVO) – nachgehalten wie die Nickelallergie: „liegt vor“, „widerrufen“, „nicht erfasst“.
- **Ansicht:** Akte › Datenschutz › Erklärungen; Hinweis im Aktenkopf („Erklärungen fehlen“); Start „Nach und nach prüfen“;
  Patientenliste (Filter aus der Prüfliste)
- **Endpunkte:** `GET/POST /api/erklaerungen/?patient&art` (POST auch `multipart` mit `datei` = Scan → Dokument vom Typ
  „Einwilligung/Datenschutz“ in der Akte), `PATCH /api/erklaerungen/{id}/` (Datum, Notiz, verknüpftes Dokument),
  `POST /api/erklaerungen/{id}/widerrufen/` `{"widerrufen_am"?, "notiz"?}`; kein Löschen.
  Kopf der Akte: `kopf.erklaerungen {stand: {art: {status, am, id}}, pflicht, fehlt}`, `zaehler.erklaerungen`;
  `GET /api/patienten/?pruefen=erklaerungen`; Startseite `pruefen.erklaerungen_fehlen`
- **Felder:** `art` (datenschutzinformation | einwilligung | schweigepflichtentbindung), `erteilt_am`, `dokument`,
  `vorlage_version` (Fassung der Dokumentvorlage beim Erfassen), `notiz`, `widerrufen_am`, `widerruf_notiz`
- **Logik:** Stand je Art = jüngste Erklärung; ein Widerruf wirkt für die Zukunft (Art. 7 Abs. 3 DSGVO), die Erklärung
  bleibt mit Widerrufsdatum stehen. Welche Arten vorliegen sollen, steht in den Einstellungen (`pflicht_erklaerungen`,
  Standard alle drei). Widerruf der Schweigepflichtentbindung: Hinweis, wenn bei Bezugspersonen noch „Auskunft erlaubt“
  steht; Widerruf der Einwilligung: Hinweis, die Folge als Anfrage zu erfassen. Auch bei abgeschlossener Akte möglich
  (ohne neuen Scan). Wird das verknüpfte Dokument einer anderen Akte zugeordnet (F72), löst sich die Verknüpfung.
- **Validierung:** Recht „Datenschutz: Erklärungen und Anfragen erfassen“ (Standard: Mitarbeiter, Mediziner; Admin nur
  Testpatienten); Datum nicht in der Zukunft; Widerruf nicht vor der Erteilung; Dokument aus derselben Akte; Datei wie F40.
- **Tabellen:** `patienten_erklaerung` (+ Historie), `patienten_dokument`, `audit_systemereignis`
- **Fehlerfälle:** 400 je Feld / schon widerrufen · 403 ohne Recht · 404 fremde oder eingeschränkte Akte
- **Teststatus:** Backend-Tests grün (`Erklaerungen.test_erfassen_nachhalten_widerrufen`,
  `test_auch_bei_abgeschlossener_akte`, `Testdaten.test_zuruecksetzen_mit_umgehaengtem_dokument_und_erklaerungen`).
  Browsertest grün: `datenschutz.spec.ts` „Erklärungen nachhalten: Hinweis im Aktenkopf, Vordruck als PDF, erfassen mit
  Scan, Widerruf“; Neustart geprüft in `zz-neustart.spec.ts` „Nach dem Neustart: Datenschutz – …“ (Lauf 36969989383, Commit `34c627d`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F76 Vordrucke der Erklärungen als PDF aus Dokumentvorlagen
- **Zweck:** Datenschutzinformation, Einwilligung und Schweigepflichtentbindung mit den Daten des Patienten ausdrucken –
  wie ein Infusionsplan aus einer pflegbaren Dokumentvorlage (F50/F51).
- **Ansicht:** Akte › Datenschutz › Erklärungen („Vordruck als PDF“); Vorlagen › Dokumentvorlagen (jetzt 5 Arten)
- **Endpunkt:** `GET /api/patienten/{id}/erklaerung-pdf/?art=…` → PDF; Kopfzeilen `X-EPM-Vorlage-Version`,
  `X-EPM-Vorlage-Entwurf`; der Export steht im Audit-Log
- **Logik:** Neue Arten der Dokumentvorlage: `datenschutzinformation`, `einwilligung`, `schweigepflichtentbindung`, mit
  Datenfeldern (Patient, Absender, Versorger, Hausarzt, Bezugspersonen mit Auskunft, Aufbewahrung in Jahren). Die
  mitgelieferten Startvorlagen sind **Entwürfe**: Aufbau nach Art. 13 DSGVO bzw. mit Freiwilligkeit und Widerruf, Lücken
  in [eckigen Klammern], Hinweis zur rechtlichen Prüfung. Solange keine von der Stiftung veröffentlichte Version aktiv
  ist, trägt die PDF das Wasserzeichen „ENTWURF“ und die Oberfläche zeigt „Vorlage noch nicht geprüft“ (U17).
  **Entwurfsmodus manuell abschaltbar (Festlegung 03.10.2026):** Vorlagen › Dokumentvorlagen › „Entwurfsmodus
  ausschalten“ (`POST /api/vorlagen/<art>/entwurfsmodus/ {"aus": true|false}`, Recht „Vorlagen pflegen“, Audit-Log,
  Historie der Einstellungen `vordrucke_ohne_entwurf`, Migration `stammdaten/0010`): Die PDFs der mitgelieferten
  Vorlage tragen dann kein Wasserzeichen und keinen Hinweisblock für die Bearbeiter; Lücken in [eckigen Klammern]
  bleiben stehen. Jederzeit wieder einschaltbar; nach dem Veröffentlichen einer eigenen Version ohnehin ohne Wasserzeichen.
- **Validierung:** Akte lesbar; `art` aus der Liste, sonst 400.
- **Tabellen:** `vorlagen_dokumentvorlage`
- **Teststatus:** Backend-Tests grün (`Erklaerungen.test_pdf_aus_der_dokumentvorlage`,
  `vorlagen.Vorlagen.test_startvorlagen_sind_gueltig_und_rechte`). Browsertest grün: `datenschutz.spec.ts` „Erklärungen
  nachhalten: …“ (PDF mit Namen des Patienten, Entwurfshinweis) (Lauf 36969989383, Commit `34c627d`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F77 Datenschutz-Anfragen mit Frist
- **Zweck:** Anträge betroffener Personen (Auskunft, Berichtigung, Löschung, Einschränkung, Widerruf, Sonstiges) als
  Vorgang: Eingang, Frist, Ergebnis, Mitteilung (Art. 12 Abs. 3 und 4 DSGVO).
- **Ansicht:** Akte › Datenschutz › Anfragen; Datenschutz › Offene Anfragen; Start „Nach und nach prüfen“
- **Endpunkte:** `GET/POST /api/datenschutzanfragen/?patient&art&offen`, `PATCH /api/datenschutzanfragen/{id}/` (solange
  offen; auch `frist_verlaengert` + `verlaengerung_grund`), `POST /api/datenschutzanfragen/{id}/erledigen/` `{"ergebnis":
  "erfuellt|eingeschraenkt|abgelehnt|zurueckgezogen", "begruendung"?, "mitgeteilt_am"?}`; kein Löschen.
  Kopf der Akte: `kopf.datenschutz_anfragen`; Startseite `pruefen.datenschutz_anfragen`
- **Logik:** `frist_bis` = Eingang + 1 Monat, einmal um 2 Monate verlängerbar (nur mit Grund); `ueberfaellig`, wenn offen
  und Frist vorbei. Ergebnis „eingeschraenkt“ („Verarbeitung eingeschränkt statt gelöscht“, § 35 Abs. 3 BDSG) schränkt
  zugleich die Akte ein (F79). Eine Löschung wird nicht hier, sondern mit F80 erfüllt; die offene Anfrage „Löschung“ ist
  dort die Grundlage, wenn die Frist noch läuft. Anfragen gibt es auch zu eingeschränkten Akten – diese sieht und erfasst
  nur, wer Einsicht nehmen dürfte (Recht „entscheiden“; Admins nur bei Testpatienten). Die Startseite zählt offene
  Anfragen aller Akten im Bereich der Person, auch abgeschlossener, und nennt die überfälligen.
- **Validierung:** erfassen/ändern mit Recht „… erfassen“, erledigen mit Recht „… entscheiden“ (Standard: Mediziner);
  „abgelehnt“ und „eingeschraenkt“ nur mit Begründung (mindestens 10 Zeichen, Art. 12 Abs. 4 DSGVO); `mitgeteilt_am`
  nicht vor dem Eingang, nicht in der Zukunft; erledigte Anfragen unveränderlich.
- **Tabellen:** `patienten_datenschutzanfrage` (+ Historie), `audit_systemereignis`
- **Fehlerfälle:** 400 je Feld / schon erledigt · 403 ohne Recht · 404 fremde Akte
- **Teststatus:** Backend-Tests grün (`Anfragen.test_ablauf_mit_frist`,
  `test_loeschung_wird_eingeschraenkt_statt_geloescht`, `Fristen.test_aufbewahrung_und_frist_der_anfragen`). Browsertest
  grün: `datenschutz.spec.ts` „Anfrage mit Frist, Kopie der Akte, Löschwunsch → eingeschränkt, Einsicht mit Grund,
  Aufheben“ (Lauf 36969989383, Commit `34c627d`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F78 Kopie der Akte als ZIP
- **Zweck:** Auskunft mit Kopie der Daten (Art. 15 Abs. 3 DSGVO) in einem Schritt.
- **Ansicht:** Akte › Datenschutz › Aufbewahrung („Kopie der Akte“; darunter die bisher erstellten Kopien)
- **Endpunkt:** `GET /api/patienten/{id}/kopie/` → `Aktenkopie-<Nr>-<Datum>.zip` mit `Akte-<Nr>.pdf` (alle Angaben und
  Einträge: Stammdaten, Diagnose, Therapie, Empfehlung, Bezugspersonen, Ärzte, Gewichte, Kontakte, Termine, Pläne,
  Erklärungen, Anfragen), `Verlauf-<Nr>.pdf`, `Dokumente/` (alle Dateien im Original, auch die Plan-PDFs), `LIESMICH.txt`
  (Inhalt; fehlende Dateien werden genannt)
- **Logik:** Jede Kopie steht im Audit-Log (Export „Kopie der Akte“, ZIP, Anzahl Dokumente) und in der Akte unter „Kopien“.
- **Validierung:** Recht „Datenschutz: Erklärungen und Anfragen erfassen“; Akte lesbar (eingeschränkt: nur mit Einsicht);
  Admins nur bei Testpatienten (403 bei echten Akten).
- **Teststatus:** Backend-Test grün (`Aktenkopie.test_kopie_als_zip`). Browsertest grün: `datenschutz.spec.ts` „Anfrage mit
  Frist, Kopie der Akte, …“ (Download; ZIP enthält Akte, Verlauf und LIESMICH; Eintrag unter „Kopien“) (Lauf 36969989383, Commit `34c627d`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F79 Verarbeitung einschränken, begründete Einsicht, Aufheben
- **Zweck:** Art. 18 DSGVO, § 35 Abs. 3 BDSG: Darf (noch) nicht gelöscht werden, bleibt die Akte gespeichert, wird aber
  nicht mehr verwendet.
- **Ansicht:** Akte › Datenschutz; eingeschränkte Akte: statt der Akte die Ansicht „Verarbeitung eingeschränkt“ mit
  „Einsicht nehmen“ (Grund); Datenschutz › Eingeschränkte Akten
- **Endpunkte:** `POST /api/patienten/{id}/einschraenken/` `{"grund"}` · `POST …/einsicht/` `{"grund"}` → `{bis}` (60
  Minuten, nur für diese Person) · `POST …/einschraenkung-aufheben/` `{"grund", "unterrichtet_am"}` oder `{"grund",
  "unterrichtung_entfaellt": "Begründung"}` · `GET /api/patienten/{id}/` bei eingeschränkter Akte ohne Einsicht → 403
  `{eingeschraenkt: true, id, nummer, eingeschraenkt_am, darf_einsicht, fehler}`
- **Logik:** Eingeschränkte Akten fehlen in Patientenliste, Suche, Startseite, Zählern und allen Eintragslisten
  (`epm/api_basis.py::patienten_fuer`), außer für Personen mit laufender Einsicht. Auch der Stand „Datenschutz“ der Akte
  (Erklärungen, Anfragen, Grund) ist nur mit laufender Einsicht lesbar. Wo eine eingeschränkte Akte trotzdem genannt
  werden muss, damit Fristen und Anfragen nicht untergehen – Übersicht „Datenschutz“ (F81), Liste der Anfragen (F77) –,
  sehen Name und Grund nur Personen, die Einsicht nehmen dürften (`patienten_mit_eingeschraenkten`: Recht „entscheiden“;
  Admins nur bei Testpatienten); alle anderen sehen die Nummer. Im Audit-Log (F58, auch als PDF) erscheinen die Einträge
  zu einer eingeschränkten Akte für Personen ohne Einsichtsrecht ohne Namen, Titel und Freitext („Akte Nr. N
  (Verarbeitung eingeschränkt)“) und sind über die Suche nach dem Namen nicht zu finden; im Django-Admin (`/verwaltung/`)
  erscheinen eingeschränkte Akten, ihre Einträge und ihre Audit-Einträge nicht. Einschränken, jede Einsicht (mit Grund)
  und das Aufheben stehen im Audit-Log (Gruppe „Datenschutz“) und im Verlauf. Die Ansicht nennt vor der Einsicht, wofür
  eingeschränkte Daten verarbeitet werden dürfen (Art. 18 Abs. 2 DSGVO); ob der eingetragene Grund darunter fällt, prüft
  das Programm nicht. Vor dem Aufheben ist die betroffene Person
  zu unterrichten (Art. 18 Abs. 3 DSGVO): Datum der Unterrichtung oder Begründung, warum sie entfällt. Aufheben beendet
  laufende Einsichten. Wieder öffnen (F21) erst nach dem Aufheben (409).
- **Validierung:** Recht „Datenschutz: Anfragen entscheiden, Verarbeitung einschränken“ (Standard: Mediziner; Admin nur
  Testpatienten – eingeschränkte echte Akten kann ein Admin nicht einsehen); nur abgeschlossene Akten; Gründe mindestens
  10 Zeichen.
- **Tabellen:** `patienten_patient` (`eingeschraenkt_am`, `eingeschraenkt_von`, `einschraenkung_grund`) + Historie,
  `patienten_akteneinsicht`, `audit_systemereignis`
- **Fehlerfälle:** 400 Grund / Unterrichtung fehlt / nicht abgeschlossen / schon eingeschränkt · 403 ohne Recht · 404
  (auch: eingeschränkte Akte für Personen, die keine Einsicht nehmen dürften)
- **Teststatus:** Backend-Tests grün (`Einschraenkung.test_eingeschraenkte_akte_verschwindet_und_einsicht` – auch: Stand
  „Datenschutz“ ohne Einsicht für niemanden, Audit-Log der Administration ohne Namen und ohne Treffer bei der
  Namenssuche, andere Suchen vollständig; `Anfragen.test_loeschung_wird_eingeschraenkt_statt_geloescht` – auch: Übersicht
  und Anfragen für Mitarbeiter und Administration ohne Namen). Der Django-Admin ist nicht automatisch getestet. Browsertest grün: `datenschutz.spec.ts` „Anfrage mit
  Frist, Kopie der Akte, Löschwunsch → eingeschränkt, Einsicht mit Grund, Aufheben“ (Akte danach verschlossen – auch für
  die Person, die eingeschränkt hat –, nicht mehr in der Patientenliste, Einsicht erst mit Grund, Aufheben erst mit Datum
  der Unterrichtung, alles im Audit-Log; ein Mitarbeiter sieht in der Übersicht nur die Nummer, weder Namen noch Grund);
  Neustart geprüft in `zz-neustart.spec.ts` (Lauf 36969989383, Commit `34c627d`). Dass Mitarbeiter keine Einsicht nehmen können, prüft der
  Backend-Test.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F80 Akte endgültig löschen mit Löschprotokoll
- **Zweck:** Recht auf Löschung (Art. 17 DSGVO) und Löschen nach Ablauf der Aufbewahrung (Art. 5 Abs. 1 e DSGVO).
- **Ansicht:** Akte › Datenschutz › „Akte endgültig löschen“ (Umfang, Grund, Kennwort, Code aus der Authenticator-App,
  6-stelliger Bestätigungscode zum Abtippen); Datenschutz › Löschprotokoll
- **Endpunkte:** `POST /api/patienten/{id}/loeschen-vorbereiten/` → `{code, gueltig_bis, loeschen, umfang}` (5 Minuten, in
  der Sitzung); `POST /api/patienten/{id}/loeschen/` `{"grund", "kennwort", "code", "bestaetigung"}` → `{geloescht, nummer,
  protokoll}`
- **Wann möglich:** nur abgeschlossene Akten, und entweder ist die Aufbewahrungsfrist abgelaufen (Rechtsgrund `frist`)
  oder es liegt eine offene Anfrage „Löschung“ vor (Rechtsgrund `antrag`; läuft die Frist noch, weist der Dialog darauf
  hin, dass nur gelöscht werden darf, wenn keine Aufbewahrungspflicht entgegensteht – Art. 17 Abs. 3 DSGVO –, sonst F79).
  Sonst 409 mit Hinweis.
- **Logik:** In einer Transaktion, im Wartungsmodus der Trigger: Löschprotokoll schreiben; Akte mit allen Einträgen
  (Kontakte, Gewichte, Termine, Dokumente, Pläne mit Positionen, Bezugspersonen, Ärzte-Zuordnungen, Erklärungen, Anfragen,
  Einsichten) **und der gesamten Historie** entfernen, einschließlich der Historie der Vitamin-Zuordnung der Pläne. Ein
  Dokument gehört zu der Akte, in der es am Ende liegt (oder endgültig gelöscht wurde): Dokumente der gelöschten Akte
  verlieren alle früheren Fassungen – auch die aus der Zeit, in der sie versehentlich in einer anderen Akte lagen; dort
  bleibt nur der neutrale Vorgang „einer anderen Akte zugeordnet“. Ein Dokument, das in einer anderen Akte weiterlebt,
  bleibt mit seinen Fassungen; an seinem Vorgang und Audit-Eintrag entfallen der Verweis auf die gelöschte Akte und der
  Freitext. Im Audit-Log bleiben die Einträge zur Akte als Nachweis (wer, wann, welche Art), verlieren aber Namen, Titel
  und Freitexte → „Akte Nr. N (gelöscht)“ (`audit/bereinigung.py::akte_entfernen`); ein Suchbegriff mit dem Namen in
  einem Eintrag „Audit-Log als PDF“ wird entfernt. Nach dem Commit: Dokumentenordner der Akte löschen, Eintrag in die Löschliste.
  Die Patientennummer wird nicht neu vergeben. Jede Ablehnung (Code, Kennwort, 2FA) steht im Audit-Log; dreimal falscher
  Bestätigungscode macht ihn ungültig.
- **Löschprotokoll** (`patienten_loeschprotokoll`, nur anfügen): Nummer, interne Kennung, Test ja/nein, angelegt am,
  abgeschlossen am, Aufbewahrung bis, Rechtsgrund, Grund, Umfang (Anzahlen, bei Antrag sein Eingangsdatum), Zeitpunkt,
  Person – kein Name, nicht der Anlass des Abschlusses. Der Grund ist Freitext; die Oberfläche bittet, keine Namen
  hineinzuschreiben. Dieselben Angaben stehen in der Löschliste.
- **Sicherungen und Wiederherstellung:** wie F73 – ältere Sicherungen enthalten die Akte bis zu ihrem Ablauf (30 Tage);
  die Löschung steht in der Löschliste (`data/loeschliste/loeschliste.jsonl`, Zeilen mit `akte`), `manage.py
  epm_loeschungen_nachholen` (bei jedem Start) löscht eine zurückgekommene Akte erneut, wenn interne Kennung, Nummer und
  Anlagezeitpunkt übereinstimmen, und gleicht Löschliste und Löschprotokoll gegenseitig ab. Testakten werden nie
  nachgelöscht (ihre Nummern vergibt das Zurücksetzen neu). Jede Zeile wird für sich verarbeitet (eine unlesbare Zeile
  hält die übrigen nicht auf; Dokumente und Akten laufen unabhängig); liegt der Dokumentenordner einer gelöschten Akte
  noch da, wird er entfernt. Grenzen: Es gilt der Stand der Sicherung – was zwischen Sicherung und Löschung geändert
  wurde (etwa ein Dokument, das danach einer anderen Akte zugeordnet wurde), ist wie bei jeder Wiederherstellung
  verloren. Die Löschliste gehört zu genau einem System: nie die eines anderen Systems (Testkopie) einspielen.
- **Validierung:** Rolle Mediziner und Recht „Akten endgültig löschen“ (keiner anderen Rolle zuweisbar); Grund mindestens
  10 Zeichen.
- **Tabellen:** alle Tabellen der Akte und ihre Historien, `patienten_loeschprotokoll`, `audit_systemereignis`
- **Fehlerfälle:** 400 je Feld · 403 nicht Mediziner/ohne Recht · 404 · 409 nicht löschbar
- **Teststatus:** Backend-Tests grün (`AkteLoeschen.test_endgueltig_loeschen_auf_antrag` – auch: kein Name mehr in
  Datenbank, Historie und Audit-Log, Dateien weg, umgehängtes Dokument lebt in der anderen Akte weiter, ein hin- und
  zurückgewechseltes Dokument hinterlässt nichts, der Nachweis einer Dokument-Löschung in der anderen Akte bleibt
  unverändert, Vitamin-Historie weg, Fehlversuch gezählt, Nummer nicht neu vergeben;
  `test_loeschen_nach_ablauf_der_frist`; `test_loeschungen_nach_wiederherstellung_nachholen` – auch: unlesbare Zeile,
  liegen gebliebener Ordner). Browsertest grün:
  `datenschutz.spec.ts` „Akte endgültig löschen: nur Mediziner, mit Kennwort, Authenticator-Code und Bestätigungscode“;
  Neustart geprüft in `zz-neustart.spec.ts` (Akte bleibt weg, Löschprotokoll ohne Namen) (Lauf 36969989383, Commit `34c627d`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F81 Übersicht „Datenschutz“
- **Ansicht:** Datenschutz (Seitenleiste, neu; sichtbar mit einem der beiden Datenschutz-Rechte)
- **Endpunkt:** `GET /api/datenschutz/` → `{anfragen_offen: [Anfrage] (nach Frist), anfragen_ueberfaellig,
  aufbewahrung_abgelaufen: [{id, nummer, name, abgeschlossen_am, aufbewahrung_bis, verlaengert, eingeschraenkt}],
  aufbewahrung_laeuft_ab (nächste 12 Monate), eingeschraenkt: [{id, nummer, name, am, von, grund}], erklaerungen_fehlen,
  abschluss_pruefen, loeschprotokoll: [… letzte 100], einstellungen, darf_entscheiden, anfragen_verborgen}`. Bei einer
  eingeschränkten Akte sind `name`, `von` und `grund` leer, wenn die Person keine Einsicht nehmen dürfte; offene Anfragen
  zu solchen Akten erscheinen dann nur als Anzahl (`anfragen_verborgen`).
- **Validierung:** Recht „… erfassen“ oder „… entscheiden“; Testbenutzer sehen nur Testpatienten und Test-Löschungen.
- **Teststatus:** Backend-Tests grün (`Einschraenkung.*`, `AkteLoeschen.*`, `Anfragen.*` prüfen die Übersicht mit).
  Browsertests grün: `datenschutz.spec.ts` (eingeschränkte Akten, Löschprotokoll ohne Namen, eingestellte Fristen);
  Neustart geprüft in `zz-neustart.spec.ts` (Lauf 36969989383, Commit `34c627d`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F82 Plan nach Freigabe abschließen (Freigabe auf Anordnung)
- **Zweck:** Festlegung 02.10.2026: Prof. Masin gibt Pläne per E-Mail frei, Mitarbeiter dokumentieren und schließen den
  Plan ab. Bisher musste das mit seinem Konto geschehen; der Vermerk „geprüft und freigegeben von …“ muss aber stimmen.
- **Ansicht:** 8 Infusionspläne › Entwurf › „Nach Freigabe abschließen“ (für alle mit dem Recht, die nicht selbst
  freigeben dürfen): Mediziner, Datum, Weg, Nachweis
- **Endpunkte:** `GET /api/infusionsplaene/freigebende/?patient=` → `[{id, name}]`;
  `POST /api/infusionsplaene/{id}/abschliessen/` (multipart) `freigegeben_von`, `freigegeben_am`, `weg`
  (email | telefon | persoenlich | schriftlich), `nachweis`? (Datei) → Plan mit `status: "aktuell"`, `freigabe_weg`,
  `freigabe_datum`, `abgeschlossen_von_name`, `freigabe_nachweis`, `freigabevermerk`
- **Logik:** wie F35 (PDF mit Prüfsumme, Vorgänger abgelöst, unveränderlich), zusätzlich: Nachweis wird als Dokument vom
  Typ „Freigabe“ in der Akte abgelegt und kann weder umgehängt noch gelöscht werden. Freigabevermerk der PDF (Datenfeld
  `{{Plan.Freigabevermerk}}`): „Maschinell erstellt. Geprüft und freigegeben von <Mediziner> am <Datum> (<Weg>); im System
  abgeschlossen von <Person> am <Datum>.“ – bei Freigabe im System unverändert wie F35. Entwürfe zeigen keinen Vermerk.
  Die Migration stellt eine aktive Vorlage mit dem bisherigen festen Satz als neue Version auf das Datenfeld um, einen
  Entwurf an Ort und Stelle. Listen zeigen bei diesen Plänen den Tag der Freigabe, nicht den Zeitpunkt des Abschließens.
  Audit-Log („Infusionsplan nach Freigabe durch <Mediziner> am <Datum> (<Weg>) abgeschlossen“), Verlauf der Akte („nach
  Freigabe abgeschlossen“ mit „freigegeben von … am … (Weg)“) und Startseite nennen den Vorgang so – nicht als Freigabe
  durch die abschließende Person.
- **Validierung:** Recht „Infusionspläne nach Freigabe abschließen“ (Standard: Mitarbeiter, Mediziner; Admin nur
  Testpatienten); `freigegeben_von` = aktiver Mediziner mit Recht „Infusionspläne freigeben“; Datum nicht in der Zukunft
  und nicht vor dem Anlegen des Plans; Nachweis Pflicht bei E-Mail und schriftlich (U24); die aktive Dokumentvorlage
  „Infusionsplan“ muss das Datenfeld `{{Plan.Freigabevermerk}}` enthalten (sonst 400 mit Hinweis – die PDF würde nicht
  nennen, wer abgeschlossen hat; die Freigabe durch den Mediziner selbst bleibt möglich); sonst wie F35.
- **Tabellen:** `infusionen_infusionsplan` (`freigabe_weg`, `freigabe_datum`, `abgeschlossen_von`, `freigabe_nachweis`)
  + Historie, `patienten_dokument`
- **Fehlerfälle:** 400 je Feld · 403 ohne Recht · 409 Akte abgeschlossen
- **Teststatus:** Backend-Tests grün (`FreigabeAufAnordnung.test_abschliessen_nach_freigabe` – auch: Verlauf, Vorlage ohne
  Datenfeld,
  `vorlagen.Vorlagen.test_inhalt_des_plan_pdfs`, `test_migration_stellt_bisherigen_freigabevermerk_um`). Browsertest grün:
  `datenschutz.spec.ts` „Plan nach Freigabe per E-Mail abschließen: Mitarbeiter hält Mediziner, Datum, Weg und Nachweis
  fest“; Neustart geprüft in `zz-neustart.spec.ts` (Lauf 36969989383, Commit `34c627d`).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F83 Aufbewahrung des Audit-Logs, tägliche Bereinigung
- **Zweck:** Auch das Protokoll enthält personenbezogene Daten (Benutzer, IP-Adresse, Aktenbezug). Die Dauer ist
  einstellbar; der Standard ändert nichts (0 = unbegrenzt, U18).
- **Ansicht:** Vorlagen › Grenzwerte › Datenschutz („Audit-Log aufbewahren“); Audit-Log (Hinweistext)
- **Validierung:** ändern nur mit dem Recht „Datenschutz: Anfragen entscheiden …“ (F48); ältere Einträge sind danach
  endgültig weg.
- **Logik:** `audit/bereinigung.py::taeglich` – einmal am Tag (angestoßen beim Öffnen der Startseite): Einträge älter
  als `protokoll_aufbewahrung_jahre` werden entfernt (Wartungsmodus), die Bereinigung steht selbst im Audit-Log
  („Protokoll bereinigt“, Anzahl); außerdem werden abgelaufene Sitzungen entfernt.
- **Teststatus:** Backend-Test grün (`AuditBereinigung.test_aufbewahrung_des_audit_logs`). Browsertest grün für die
  Einstellung (`datenschutz.spec.ts` „Grenzwerte: Fristen des Datenschutzes einstellen“) und seit 03.10.2026 für das
  Entfernen: `datenschutz.spec.ts` „Audit-Log aufbewahren: ältere Einträge entfernt die tägliche Bereinigung …“ (alter
  Eintrag im Backend angelegt und zurückdatiert, Aufbewahrung über die Oberfläche auf 1 Jahr, Neustart, Startseite →
  Eintrag weg, „Audit-Log bereinigt“ im Audit-Log, Einstellung zurück).
- **Status:** ABGESCHLOSSEN UND GETESTET

## N · Kalender, Infusionspläne, Systemverwaltung (Runde 4, Wunsch 02.10.2026)

Wünsche: „Sysadmin-Seite unter Administration für typische Tätigkeiten an der VM und am EPM, mit Übersicht über die
aktuelle Auslastung, natürlich nur für Admin; Rollen und Rechte anpassen und erweitern“, „durch Termine und Fälligkeiten
ein globaler Kalender als Menüpunkt“, „Infusion vielleicht auch als Menüpunkt“. Grundlage für die Systemseite sind die
Festlegungen S12–S14 vom 01.10.2026 (`claude/startseite-erweiterungen.md`): nur Ubuntu-Pakete, Update und Neustart mit
Admin-Kennwort + 2FA, vorher automatische Sicherung, angemeldete Benutzer vorher warnen; der Container bekommt keinen
Zugriff auf den Server (Auftrag und Status über ein gemeinsames Verzeichnis, ausgeführt von systemd-Diensten).

**Recht „Systemverwaltung (Server und EPM)“** (`system_verwalten`): Standard nur Admin. Festlegung 02.10.2026
(Urlaubsregelung): unter Benutzer › Rechte jeder Gruppe freischaltbar und wieder zurücknehmbar – wirkt sofort, steht im
Audit-Log („Rechte geändert“). Die Vertretung bestätigt Update und Neustart mit dem eigenen Passwort und 2FA.
Testzugänge erhalten es nie. Der Admin kann es sich selbst entziehen und wieder geben.
Kalender und Infusionspläne brauchen kein neues Recht: Lesen mit „Akten lesen“, Termine mit „Kontakte, Gewichte,
Termine, Dokumente erfassen“, Pläne mit „Infusionspläne anlegen“ – wie in der Akte.

### F84 Globaler Kalender
- **Ansicht:** Menüpunkt „Kalender“ (Seitenleiste, für alle mit „Akten lesen“): Monat (6 Wochen, Klick auf einen Tag zeigt
  ihn rechts), Woche, Liste; „Überfällig“ (offene Termine, Kontakt fällig, Plan prüfen); Filter nach Art; „Erledigte zeigen“.
  Eintrag anklicken → Einzelheiten, „Akte öffnen“/„Pläne öffnen“, „Ändern“, „Erledigt“, bei Fälligkeiten „Termin anlegen“.
  Neuer Termin mit dem Tag als Vorgabe (gleicher Dialog wie Startseite und Akte).
- **Endpunkt:** `GET /api/kalender/?von=JJJJ-MM-TT&bis=JJJJ-MM-TT&erledigte=0|1&faelligkeiten=0|1` →
  `{von, bis, heute, termine: [Termin], termine_ueberfaellig: [Termin], faelligkeiten: [{art: kontakt|plan, patient, name,
  nummer, ist_test, faellig_am, seit, ueberfaellig, text}], grenzen: {kontakt_monate, plan_monate}, feiertage: [{datum, name}]}`.
  Termine anlegen, ändern, erledigen weiter über F29/F30.
- **Logik:** Fälligkeiten nur für Akten in Betreuung: Kontakt fällig in zwei Stufen (Runde 7, F90) – je Akte ein Eintrag
  „bald fällig“ (letzter Kontakt, sonst Anlage der Akte, + Grenzwert „Kontakt bald fällig“) und einer „überfällig“ (+ Grenzwert
  „Kontakt überfällig“), jeweils mit `stufe`; `grenzen` enthält zusätzlich `kontakt_bald_monate`; Plan prüfen = gültig ab des aktuellen Plans + Grenzwert „Infusionsplan gilt als alt
  nach“ (je 30 Tage pro Monat wie in der Patientenliste). Feiertage bundesweit plus NRW (Fronleichnam, Allerheiligen),
  siehe U25. Überfällige Termine nur offener Akten. Testzugang: nur Testpatienten.
- **Validierung:** von/bis Pflicht, bis ≥ von, höchstens 400 Tage → sonst 400.
- **Tabellen:** `patienten_termin`, `patienten_kontakt`, `infusionen_infusionsplan`, `stammdaten_einstellungen`
- **Teststatus:** Backend-Tests `patienten/test_kalender.py` (`Feiertage.test_ostern_und_nrw`, `Kalender.*`). Browsertests
  `kalender.spec.ts` (Menüpunkt, Überfälliges, Fälligkeit „Plan prüfen“ öffnen, Woche/Liste, Feiertage; Termin an einem Tag
  anlegen, öffnen, abhaken, Erledigte ausblenden; Betrachter ohne Anlegen); Neustart in `zz-neustart.spec.ts`.
- **Oberfläche (Runde 7):** Seitenlisten „Kontakt überfällig“ und „Kontakt bald fällig“ getrennt, Farben je Stufe; ab
  1920 px Kalender ¾ | ¼ mit der Tagesliste in allen Ansichten (Monat, Woche, Liste).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F85 Übersicht aller Infusionspläne
- **Ansicht:** Menüpunkt „Infusionspläne“: Gruppen „Zur Freigabe“ (Entwürfe), „Aktuell“, „Älter als n Mon.“ (Grenzwert),
  „Abgelöst“, „Alle“ mit Anzahl; Suche nach Name/Nummer; „auch abgeschlossene Akten“; Spalten Patient, Status, gültig ab,
  Energie, Laufzeit/Rate, Tage/Woche, erstellt, freigegeben; „PDF“ (gespeicherte PDF mit Prüfsumme wie F37), „Öffnen“ (Akte ›
  Pläne mit diesem Plan). „Neuer Plan“ (Recht „Infusionspläne anlegen“): Patient wählen; gibt es schon einen Entwurf, wird
  dieser geöffnet statt einen zweiten anzulegen. Bearbeiten und Freigeben bleiben in der Akte.
- **Endpunkt:** `GET /api/infusionsplaene/uebersicht/?gruppe=entwuerfe|aktuell|alt|abgeloest|alle&suche=&abgeschlossene=1` →
  `{zaehler: {gruppe: n}, grenze_monate, ergebnisse: [{id, patient, name, nummer, ist_test, patient_abgeschlossen, status,
  gueltig_ab, kcal, laufzeit_h, rate_ml_h, tage_pro_woche, erstellt_am, erstellt_von, freigegeben_am, freigegeben_von, pdf,
  pdf_sha256, aelter_als_grenze}]}` (höchstens 1.000 Zeilen). Unbekannte Gruppe → 400.
- **Tabellen:** `infusionen_infusionsplan`, `patienten_patient`
- **Teststatus:** Backend-Tests `infusionen/test_uebersicht.py`. Browsertests `infusionsplaene.spec.ts` (Gruppen, Suche, PDF
  mit Prüfsumme, Öffnen in der Akte; vorhandener Entwurf statt Doppelanlage; Betrachter ohne „Neuer Plan“).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F86 Systemverwaltung: Übersicht
- **Ansicht:** Administration › System (nur mit Recht „Systemverwaltung“): Kennzahlen CPU, Arbeitsspeicher, Platte,
  Laufzeit, Ubuntu-Updates (davon Sicherheit), letzte Sicherung – mit Balken und Text „hoch“/„kritisch“ ab 75/90 %;
  Auslastung der letzten 24 Stunden (CPU und RAM, Fadenkreuz mit Werten); Server (Betriebssystem, Kernel, Swap, Platten,
  Belegung durch Dokumente/Sicherungen/Image-Dateien, Dienste, Container mit Zustand, ausstehende Pakete); EPM (Version,
  Django/Python/PostgreSQL, Datenbankgröße, Verbindungen, letzte Pflege, Migrationen, Unveränderlichkeit n von n Tabellen,
  Patienten, Dokumente, Konten gesperrt/ohne 2FA/Einmal-Kennwort offen, größte Tabellen); Hinweis bei „Neustart nötig“.
- **Endpunkte:** `GET /api/system/uebersicht/` → `{host (Status vom Systemagenten mit alter_s, aktuell), container (eigene
  Messung: Last, Speicher, Laufzeit, Platz), agent: {verzeichnis, erreichbar}, epm, angemeldet, hinweis, aktionen, aufgaben,
  minuten}`; `GET /api/system/verlauf/` → `{felder, punkte: [[zeit, cpu, ram, last, platte]]}` (1.440 Punkte = 24 h).
- **Logik:** Der Systemagent (`rollout/epm-systemagent.py`, systemd-Timer jede Minute) schreibt `system.json` und
  `verlauf.json` nach `/srv/epm/system/status/` (im Container nur lesbar). Älter als 3 Minuten = Agent läuft nicht: die
  Seite zeigt das und, was das Backend selbst sieht (Last und Speicher aus `/proc`, Platz im Dokumentenverzeichnis).
  Updates: Simulation `apt-get -s upgrade --with-new-pkgs`, zwischengespeichert bis sich Paketlisten oder Paketstand ändern.
- **Fehlerfälle:** 403 ohne Recht (Seite ausgeblendet, F71)
- **Teststatus:** Backend-Tests `system/tests.py` (`Rechte.*`, `Uebersicht.*`). Browsertests `system.spec.ts` „nur für Admin“
  (Menü, Seite, Matrix) und „Auslastung und Status vom Systemagenten“ (CI startet den Agenten im Probelauf).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F87 Tätigkeiten für den Server (Systemagent)
- **Ansicht:** System › Tätigkeiten › Server: Status neu einlesen, Nach Updates suchen, **Ubuntu-Updates installieren**,
  **Server neu starten**, **EPM neu starten** (alle drei mit Passwort + Code aus der Authenticator-App oder Notfall-Code; Beginn
  sofort oder in 5–60 Minuten; Hinweistext an die Benutzer), Sicherung erstellen (zusätzlich Recht „Sicherungen verwalten“),
  Docker aufräumen, Paketreste entfernen. Verlauf der Tätigkeiten mit Status, Ergebnis und Ausgabe; „Zurückziehen“, solange
  der Server den Auftrag nicht übernommen hat. Die Seite fragt alle 3 Sekunden nach, solange ein Auftrag läuft.
- **Endpunkte:** `POST /api/system/auftraege/` `{aktion, kennwort?, code?, minuten?, hinweis?}` → 201 Auftrag;
  `GET /api/system/auftraege/` (letzte 30, übernimmt vorher die Ergebnisse des Agenten);
  `POST /api/system/auftraege/<kennung>/abbrechen/`.
- **Logik:** Das Backend legt `<kennung>.json` in `/srv/epm/system/auftraege/` ab (atomar); die systemd-Pfad-Einheit
  `epm-systemagent.path` startet den Agenten. Der Agent führt nur seine feste Liste aus (nichts aus der Datei wird als
  Befehl benutzt, Dateien ohne Folgen symbolischer Links gelesen), schreibt Zwischenstand und Ergebnis nach
  `status/auftraege/<kennung>.json`. Update und Neustart: vorher `epm-backup` – schlägt die Sicherung fehl, wird nichts
  verändert. Updates: `apt-get update` und `apt-get -y upgrade --with-new-pkgs` (nicht interaktiv, Konfiguration bleibt).
  Mit „warnen“ setzt das Backend einen Hinweis an alle Benutzer mit Uhrzeit des Beginns (F89); er endet mit dem Auftrag
  (beim Neustart nach Ablauf). Derselbe Auftrag nicht doppelt (409). Abschluss steht im Audit-Log (Gruppe „System“).
  Fehlversuche bei Passwort/Code stehen im Audit-Log, sperren das Konto aber nicht.
- **Validierung / Fehlerfälle:** unbekannte Aktion 400; Passwort falsch 400 `{kennwort}`; Code falsch 400 `{code}`; Minuten
  nicht 0/5/10/15/30/60 → 400; 403 ohne Recht; 409 schon beauftragt bzw. nicht mehr zurückziehbar; 503 Auftragsverzeichnis
  fehlt (dann wird nichts gespeichert).
- **Server:** `rollout/04-projekt.sh` installiert `/usr/local/sbin/epm-systemagent`, `epm-systemstatus.timer`,
  `epm-systemagent.path`/`.service` und die Verzeichnisse (`auftraege` 0770 für das Backend, `status` 0755 root);
  `compose.yaml` bindet `auftraege` schreibend und `status` nur lesend ein. `sudo epm-update` richtet das mit ein.
- **Tabellen:** `system_systemauftrag`, `system_systemhinweis`, `audit_systemereignis`
- **Teststatus:** Backend-Tests `system/tests.py` (`Auftraege.*`, darunter `test_echter_agent_im_probelauf`: Backend legt
  ab → Agent führt aus → Backend übernimmt). Browsertests `system.spec.ts` „Status neu einlesen“ (Ergebnis erscheint ohne
  Neuladen) und „Neustart nur mit Passwort und 2FA, vorher Warnung an alle Benutzer“ (falscher Code abgelehnt, Notfall-Code,
  Beginn in 15 Minuten, Warnung beim Mitarbeiter); Neustart in `zz-neustart.spec.ts`. In CI läuft der Agent mit `--trocken`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F88 Wartung des EPM
- **Ansicht:** System › Tätigkeiten › EPM: Abgelaufene Sitzungen bereinigen, Datenbank optimieren (VACUUM ANALYZE),
  Dokumente prüfen (vorhanden, Größe; wahlweise Prüfsummen; Dateien ohne Eintrag werden nur gemeldet), Unveränderlichkeit
  prüfen (fehlende Schutz-Trigger werden wieder gesetzt), Konfiguration prüfen (Django-Sicherheitsprüfung; HSTS und
  HTTPS-Umleitung macht Nginx), Alle anderen Benutzer abmelden.
- **Endpunkt:** `POST /api/system/epm/` `{aufgabe, pruefsummen?}` → Auftrag (Ziel „EPM“) mit Status, Ergebnis, Einzelheiten;
  läuft ohne umschließende Transaktion (VACUUM).
- **Teststatus:** Backend-Tests `system/tests.py` (`EpmWartung.*`: alle Aufgaben, fehlende und veränderte Dateien, gelöschter
  Trigger wird wieder gesetzt, andere Sitzung beendet). Browsertest `system.spec.ts` „Unveränderlichkeit prüfen“.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F89 Hinweis an alle Benutzer, Anmeldungen beenden
- **Ansicht:** Banner oben auf jeder Seite für alle Angemeldeten (Information/Warnung, „Ausblenden“ für die Sitzung), alle
  60 Sekunden abgefragt. System › Hinweis an alle Benutzer: setzen (Dauer 1 h … 1 Woche oder bis zum Beenden), beenden.
  System › Angemeldet: alle gültigen Anmeldungen mit Browser, Adresse, zuletzt aktiv; „Abmelden“ (nicht die eigene).
- **Endpunkte:** `GET /api/system/hinweis/` (jeder Angemeldete), `POST` `{text, art, minuten?}`, `DELETE` (Systemverwaltung);
  `DELETE /api/system/sitzungen/<id>/`.
- **Teststatus:** Backend-Tests `system/tests.py` (`Hinweise.test_hinweis_an_alle`, `Uebersicht.test_angemeldete_sitzungen`).
  Browsertest `system.spec.ts` „eigener Hinweis an alle Benutzer und Eintrag im Audit-Log“.
- **Status:** ABGESCHLOSSEN UND GETESTET

Hinweise zur Abgrenzung: Die Systemseite zeigt die letzte Sicherung und kann eine Sicherung anstoßen; Verschlüsselung,
Übertragung und Wiederherstellen stehen unter Administration › Backup (F61–F64) und nutzen denselben Systemagenten. Die Kacheln der Admin-Startseite
(S12–S14 in `claude/startseite-erweiterungen.md`) sind F94; sie lesen dieselben Endpunkte.
Ein Auftrag mit Wartezeit (Beginn in n Minuten) ist ab der Übernahme durch den Server nicht mehr zurückziehbar; die Warnung
lässt sich jederzeit beenden.

## O · Startseite und Oberfläche (Runde 7, Festlegungen 01./02.10.2026)

Grundlage: `claude/startseite-erweiterungen.md` (S01–S17, SU1–SU10) und Entwurf 2 „EPM Startseite – Erweiterungen“ auf der
Design-Fläche. SU8–SU10 am 02.10.2026 nach den Vorschlägen des Entwurfs geklärt: in der Kennzahlenleiste „Termine
überfällig“ statt Datensicherung (die steht als Chip in der Kopfzeile); unter 1440 px 2 Spalten, unter 900 px 1;
Aufteilung der übrigen Seiten wie im Entwurf vorgeschlagen. Erweitert sind außerdem F09, F13, F14, F17, F48 und F84.

**Fensterstufen** (in der ganzen Oberfläche gleich): „eng“ unter 900 px, „schmal“ 900–1439 px, „hd“ ab 1440 px, „fhd“ ab
1920 px, „qhd“ ab 2560 px. Raster der Startseite: 1 / 2 / 3 / 4 / 5 Spalten.

### F90 Kontakt fällig in zwei Stufen, Wiedereinbestellung
- **Zweck:** „bald fällig“ (Standard 4 Monate) und „überfällig“ (Standard 6 Monate) ohne Kontakt, beide unter Vorlagen ›
  Grenzwerte einstellbar (F48). Gilt in Patientenliste (Hinweis und Filter), Prüfliste, Kennzahlenleiste, Kalender (F84) und
  der Kachel „Wiedereinbestellung fällig“.
- **Datenmigration** `stammdaten/0009_kontakt_zwei_stufen`: der bisherige Wert „Kontakt überfällig“ wird „bald fällig“,
  „überfällig“ = größerer Wert aus 6 und bisher + 2 Monate (bisher 4 → 4/6). Eintrag in der Historie der Einstellungen mit
  Grund „Kontakt fällig in 2 Stufen: bald fällig = bisheriger Wert, überfällig neu (Festlegung 01.10.2026)“.
- **Logik:** Stufe aus dem letzten nicht stornierten Kontakt: älter als „überfällig“ → `ueberfaellig`, älter als „bald“ →
  `bald`; Akten ohne jeden Kontakt gelten als „überfällig“ (wie bisher „Kein Kontakt“; Text „Noch kein Kontakt erfasst“).
  Nur Akten in Betreuung. Monate zu 30 Tagen wie in der Patientenliste.
- **Endpunkte:** `GET /api/patienten/?pruefen=kontakt_bald|kontakt_ueberfaellig|kein_kontakt (beide)|wiedereinbestellung`;
  in `GET /api/startseite/`: `"wiedereinbestellung": {ueberfaellig: [{patient, name, nummer, ist_test, letzter_kontakt,
  stufe}], bald: [...], anzahl_ueberfaellig, anzahl_bald, bald_monate, ueberfaellig_monate}` – Akten mit fälligem Kontakt
  **ohne** offenen Termin, längste Zeit ohne Kontakt zuerst, je Stufe höchstens 50.
- **Kachel:** Anzahl je Stufe, Namen mit „seit …“, Knöpfe „Kontakt erfassen“ (F91 mit dem Patienten vorbelegt) und
  „Termin anlegen“; Link „Alle anzeigen“ zur gefilterten Patientenliste.
- **Validierung:** beide ≥ 1 Monat, „bald“ < „überfällig“ – im Modell (`kontaktstufen_fehler`) und in der API.
- **Tabellen:** `stammdaten_einstellungen` (+ Historie), `patienten_kontakt`, `patienten_termin`
- **Teststatus:** Backend-Tests `patienten/test_startseite.py` (`Kontaktstufen.*`: Migration, Validierung;
  `Startseite.test_wiedereinbestellung_ohne_geplanten_termin`), `Patientenliste.test_kontakt_faellig_in_zwei_stufen`,
  `test_kalender.py` (beide Stufen), `stammdaten/tests.py` (Audit „von 6 auf 8 Monate“). Browsertests `start.spec.ts`
  „Wiedereinbestellung (S04): Stufen und Kontakt direkt aus der Kachel“, `admin.spec.ts` „Vorlagen: … Grenzwerte“ („bald“ ≥
  „überfällig“ abgewiesen), `kalender.spec.ts`; Neustart in `zz-neustart.spec.ts` (bald 9 / überfällig 14 vor dem Neustart
  in der Oberfläche gesetzt, danach geprüft und auf 4 / 6 zurückgestellt).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F91 Schnellerfassung von der Startseite
- **Ansicht:** 2 Start, Kopfknöpfe „Kontakt erfassen“, „Gewicht“, „Termin“; „Kontakt erfassen“ auch in den Kacheln
  „Wiedereinbestellung“ und „Meine Akten“ (dann mit dem Patienten vorbelegt).
- **Dialog „Kontakt erfassen“:** Patient wählen (Suche wie F14), Kontextkasten „Aus der Akte“ (letzter Kontakt, Gewicht mit
  Trend, aktueller Plan, nächster Termin, „Auskunft an“ – aus F17), Datum und Uhrzeit vorbelegt mit jetzt, Notiz
  (formatiert), „Gewicht mit erfassen“ (Gewicht, gemessen am, Quelle; Veränderung zur letzten Messung wird angezeigt),
  „Wiedervorlage anlegen“ (Rückruf/Wiedervorlage/Praxistermin, fällig am mit Schnellwahl, Uhrzeit, Ort bzw. Titel).
- **Speichern (Festlegung SU1):** zwei getrennte Anfragen – zuerst `POST /api/kontakte/` (mit Wiedervorlage, F26/F28), dann
  `POST /api/gewichte/` (F25). Scheitert das Gewicht (z. B. außerhalb der Grenzen), bleibt der Kontakt gespeichert; der
  Dialog meldet „Kontakt gespeichert – Gewicht nicht gespeichert: …“, die Kontaktfelder sind gesperrt und „Gewicht
  speichern“ holt nur das Gewicht nach. „Gewicht“ allein und „Termin“ nutzen F25 bzw. F29.
- **Validierung / Fehlerfälle:** wie F25, F26, F28, F29 (Grenzen der Einstellungen, abgeschlossene Akte 409, Rechte).
- **Teststatus:** Browsertest `oberflaeche.spec.ts` „Schnellerfassung (S02): Kontakt mit Wiedervorlage; das Gewicht
  scheitert getrennt und wird nachgeholt“ (590 kg abgewiesen, Kontakt bleibt, 59,4 kg nachgeholt; danach in der Akte und
  über die API geprüft, Gewicht allein).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F92 Meine Akten: Merkliste und zuletzt geöffnet
- **Ansicht:** Stern „Merken“ im Aktenkopf (F17, `aria-pressed`); Kachel „Meine Akten“ mit „Merkliste“ und „Zuletzt
  geöffnet“ (Gewicht/Trend, nächster Termin, Planentwurf; Knopf „Kontakt erfassen“). Die Akte meldet das Öffnen einmal je
  Aufruf.
- **Endpunkte:** `GET /api/meine-akten/` → `{merkliste: [Zeile], zuletzt: [Zeile]}` mit Zeile `{patient, name, nummer,
  ist_test, ist_abgeschlossen, am, gewicht, trend, naechster_termin, plan_entwurf}`; `POST /api/meine-akten/merken/`
  `{patient}` → 201; `DELETE /api/meine-akten/merken/<patient>/`; `POST /api/meine-akten/geoeffnet/` `{patient}` → 204.
- **Logik:** je Person gespeichert; „zuletzt geöffnet“ behält die 20 jüngsten, die Merkliste höchstens 200. Nur Akten im
  eigenen Bereich (Testzugang: nur Testpatienten; eingeschränkte Akten erscheinen nicht). Wird die Akte endgültig gelöscht
  (F80) oder das Konto entfernt, fallen die Einträge mit weg (CASCADE). Keine Historie (reine Arbeitshilfe der Person, siehe
  `docs/DATENSCHUTZ.md`).
- **Validierung / Fehlerfälle:** 400 unbekannte oder fremde Akte; 400 Merkliste voll; 403 ohne „Akten lesen“.
- **Tabellen:** `patienten_merkeintrag` (neu, Migration `patienten/0008_merkeintrag`; eindeutig je Person, Akte und Art)
- **Teststatus:** Backend-Tests `test_startseite.MeineAkten.*` (merken, zuletzt, Bereich, Wegfall mit der Akte).
  Browsertest `oberflaeche.spec.ts` „Meine Akten (S05): Stern im Aktenkopf, Merkliste und zuletzt geöffnet auf der
  Startseite“.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F93 Startseite anpassen: Kacheln im festen Raster
- **Ansicht:** 2 Start › „Startseite anpassen“: Leiste mit Spaltenzahl der aktuellen Fensterstufe, „Standard“, „Fertig“;
  je Kachel Griff (verschieben), Größenwahl 1×1/2×1/1×2/2×2, „ausblenden“; ausgeblendete Kacheln unten mit „einblenden“.
  Größe per Ziehen an der Ecke unten rechts – ein Rahmen zeigt die Zielgröße („2 × 1 · loslassen zum Einrasten“), die
  Kachel rastet in ganzen Rasterzellen ein. Verschieben per Ziehen am Griff auf eine andere Kachel. Tastatur am Griff:
  Pfeile verschieben, Umschalt + Pfeile ändern die Größe.
- **Raster:** feste Zeilenhöhe; Spalten je Fensterstufe 1/2/3/4/5 (SU9); eine Kachel ist höchstens so breit wie das
  Raster. Passt der Inhalt nicht, scrollt die Kachel in sich oder zeigt „Alle anzeigen“.
- **Speichern:** jede Änderung sofort über F09 (`startseite.karten` mit Größe und Reihenfolge).
- **Teststatus:** Backend-Tests `test_startseite.KachelnUndTeiler.test_standard_je_rolle`,
  `test_groesse_und_reihenfolge_gespeichert`, `accounts/tests.py`. Browsertest `start.spec.ts` „Startseite anpassen:
  ausblenden, verschieben und Größe per Tastatur, Maus und Knopf – je Person gespeichert“; Neustart in `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F94 Startseite der Administration
- **Ansicht:** 2 Start für die Rolle Admin (Standard; jede Person kann Kacheln ein- und ausblenden, angezeigt nur mit dem
  passenden Recht): „Datensicherung“ (letzte Sicherung, Verschlüsselung, Übertragung, Speicher; „Jetzt sichern“ mit
  Rückfrage – Recht „Sicherungen verwalten“, F62), „Server“ (CPU, Arbeitsspeicher, Platte, Laufzeit seit Neustart – F86),
  „Ubuntu-Updates“ (offene Pakete, davon Sicherheit, Hinweis „Neustart nötig“; „Updates installieren“, „Server neu starten“
  mit demselben Dialog wie System: Passwort + 2FA, Beginn, Warnung an alle – F87), „Angemeldet“ (abmelden – F89), „Hinweis an
  alle“ (setzen/beenden – F89), „Konten“ (gesperrt, Einmal-Kennwort offen/abgelaufen, ohne 2FA, Notfall-Codes knapp;
  „Entsperren“, Link zu Benutzer – Recht „Benutzer verwalten“), „Zugriffe · 7 Tage“ (Anmeldungen, Fehlversuche, PDF-Exporte,
  Vorlagen geändert, Wiederherstellungen; jede Zeile öffnet das Audit-Log mit Gruppe und Zeitraum – Recht „Audit-Log
  lesen“), „Testumgebung“ (Testpatienten in Betreuung/abgeschlossen, zuletzt zurückgesetzt; „Testdaten zurücksetzen“ – F57).
  Kopfknopf „Benutzer anlegen“ (öffnet Benutzer mit dem Formular).
- **Neue Endpunkte:** `GET /api/benutzer/konten/` → `[{id, benutzername, anzeigename, rolle, probleme:
  [gesperrt|einmal_kennwort|einmal_kennwort_abgelaufen|ohne_2fa|notfallcodes], gesperrt_am, sperrgrund, fehlversuche,
  einmal_kennwort_gueltig_bis, notfallcodes_uebrig, notfallcodes_gesamt}]` – nur Zustände und Anzahlen, keine Kennwörter,
  Codes oder Prüfsummen; `GET /api/protokoll/zusammenfassung/?tage=7` (1–90) → `{tage, von, zeilen: [{schluessel, text,
  gruppe, anzahl}]}`; `GET /api/testdaten/` → `{in_betreuung, abgeschlossen, zuletzt_am, zuletzt_von}`. Alle übrigen Kacheln
  lesen vorhandene Endpunkte (`/api/backup/`, `/api/system/uebersicht/`, `/api/system/auftraege/`, `/api/system/hinweis/`).
- **Abweichung (markiert):** Die Kachel „Konten“ druckt kein Zugangsblatt – das Einmal-Kennwort wird nur beim Erzeugen
  angezeigt (F54/F55) und ist danach nur als Prüfsumme gespeichert; die Kachel verweist dafür auf Administration › Benutzer.
- **Fehlerfälle:** 403 ohne das jeweilige Recht (Kachel ausgeblendet, F71).
- **Teststatus:** Backend-Tests `test_startseite.AdminKacheln.*` (Konten ohne Geheimnisse, Zugriffe 7 Tage, Testumgebung).
  Browsertest `oberflaeche.spec.ts` „Startseite der Administration (S12–S14): Kacheln nach Rechten, Update nur mit Passwort
  und 2FA“ (Mitarbeiter sieht keine Admin-Kachel; falscher Code abgelehnt, Auftrag mit Notfall-Code, Zugriffe → Audit-Log).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F95 Hilfe je Rolle
- **Ansicht:** Menüpunkt „Hilfe“ (für alle Angemeldeten) und „?“ in der Kopfzeile jeder Seite (`/hilfe?seite=<Pfad>` öffnet
  den passenden Abschnitt, Unterseiten ohne eigenen Abschnitt den der übergeordneten Seite). Inhaltsverzeichnis nach Gruppen,
  Suche über Titel, Text und Ergänzungen; Chip „mitgeliefert · EPM <Version>“; darunter „Ergänzung der Stiftung“ mit
  Historie (alle Fassungen) und – mit dem Recht „Vorlagen pflegen“ – „Ergänzen“/„Bearbeiten“ (Editor wie Dokumentvorlagen).
- **Inhalt:** 45 mitgelieferte Abschnitte in 10 Gruppen (`backend/hilfe/inhalt.py`, mit dem Code versioniert – passt immer
  zur installierten Version), darunter Kalender, Infusionspläne, System, Datenschutz, Backup und Import. Angezeigt werden die
  Abschnitte, für die die Person mindestens eines der genannten Rechte hat (Rechte je Gruppe, F66) – nicht der Rollenname.
- **Endpunkte:** `GET /api/hilfe/` → `{version, darf_ergaenzen, gruppen: [{id, titel, abschnitte: [{id, titel, seiten, html,
  ergaenzung: {text, geaendert_am, geaendert_von, versionen} | null}]}]}`; `PUT /api/hilfe/<abschnitt>/ergaenzung/` `{text}`
  (Recht „Vorlagen pflegen“; leer = entfernen); `GET /api/hilfe/<abschnitt>/ergaenzung/versionen/` → `[{version, zeitpunkt,
  person, text}]`.
- **Logik:** Text wird wie andere formatierte Texte bereinigt (`epm/sanitize.py`); jede Änderung als neue Fassung in der
  Historie (unveränderlich, Löschen nicht vorgesehen) und im Audit-Log (Gruppe „Vorlagen“, Objekt „Hilfe › <Titel>“,
  angelegt/geändert/entfernt). Abschnitte ohne Recht → 404.
- **Tabellen:** `hilfe_hilfeergaenzung`, `hilfe_historicalhilfeergaenzung` (neue App `hilfe`, Migration `0001_initial`)
- **Teststatus:** Backend-Tests `test_startseite.Hilfe.*` (Abschnitte nach Rechten, Ergänzung mit Historie und Audit, jeder
  Abschnitt vollständig). Browsertest `oberflaeche.spec.ts` „Hilfe (S15): „?“ führt zum passenden Abschnitt, Suche,
  Ergänzung mit Historie“ (auch: Betrachter sieht keine Administration und kein „Ergänzen“).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F96 Volle Fensterbreite, Aufteilung in Stufen
- **Umsetzung:** Begrenzung `max-w-[1440px]` in `Seite` entfernt – alle Seiten nutzen die volle Breite (Rand 16 px, ab
  900 px 32 px). Aufteilung je Stufe nach Entwurf 2: Startseite (F93), Patientenliste (F14), Akte Übersicht und Kontakte
  (F17), Plan-Editor (ab 1920 px Eingabe | Summen | PDF-Vorschau im Verhältnis 2 : 1 : 1, ab 2560 px drei Spalten mit zwei
  Teilern, Standard ⅓ | ⅓ | ⅓), Kalender (F84), Neuer
  Patient (ab 1920 px 6, ab 2560 px 8 Felder je Zeile), Dokumente (ab 1920 px Liste | Vorschau 2 : 1), Pläne (ab 1920 px
  breitere Liste), Administration (System 2/3/4 Karten je Zeile, Backup und Datenschutz zwei- bzw. dreispaltig), Hilfe
  (Inhalt | Text).
- **PDF-Vorschau im Plan-Editor:** zeigt den Stand der letzten Speicherung (`/api/infusionsplaene/<id>/ansicht/`); vor der
  ersten Speicherung „sobald der Entwurf gespeichert ist“. Keine Vorschau ungespeicherter Eingaben (abgeleitet, markiert in
  `claude/startseite-erweiterungen.md`).
- **Teststatus:** Browsertests `oberflaeche.spec.ts` „Volle Breite in Stufen: 1280 px“, „… 1920 px …“, „… 2560 px …“
  (Startseite 2/4/5 Spalten, Inhalt über die volle Breite, Spalten der Patientenliste, Aufteilung der Akte, Tagesliste im
  Kalender, Vorschau in der Patientenliste, Plan-Editor mit PDF-Vorschau), `layout.spec.ts`; 3 Spalten bei 1440 px in
  `start.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F97 Spaltenteiler mit Einrastpunkten
- **Ansicht:** senkrechter Teiler zwischen Spalten (Patientenliste ab 2560 px, Akte Übersicht und Kontakte ab 1440 px bis
  1919 px und ab 1920 px – Kontakte ab 2560 px feste Aufteilung ohne Teiler –, Plan-Editor ab 2560 px mit zwei Teilern). Ziehen mit der Maus – rastet bei ⅓, ½, ⅔ und beim Standard der Seite ein, Tooltip zeigt den
  Punkt („⅔ · rastet ein · Doppelklick: Standard“); Doppelklick setzt auf den Standard zurück. Tastatur (Rolle
  `separator`): ←/→ zum nächsten Einrastpunkt, Pos1/Ende erster/letzter, Eingabe = Standard.
- **Speichern:** je Seite, Fensterstufe und Person über F09 (`aufteilung`, `"<seite>@<stufe>"`); Standard = Eintrag
  entfernt.
- **Teststatus:** Backend-Test `test_startseite.KachelnUndTeiler.test_spaltenteiler` (Validierung, Zusammenführen, Zurücksetzen).
  Browsertest `oberflaeche.spec.ts` „Volle Breite in Stufen: 1920 px mit Spaltenteiler (Einrastpunkte ⅓, ½, ⅔, je Person
  gespeichert)“ (Tastatur, Maus, Doppelklick, gespeicherter Wert); Neustart in `zz-neustart.spec.ts` (Teiler der Akte auf ⅓).
- **Status:** ABGESCHLOSSEN UND GETESTET

## P · Fehlerliste vom 02.10.2026

Punkte der Fehlerliste: 1 Infusionspläne-Übersicht und Planansicht, 2 Karten mit „⋯“ statt Teiler in der Akte,
3 Verlauf unter Kontakte, 4 System, 5 Backup, 6 Benutzer und Rechte. Rückfragen geklärt: Punkt 2 „Raster mit ⋯-Menü“,
Punkt 6.4 „Testbenutzer-Schalter“ und zusätzlich „Testpatient definieren für mögliche Plantests“.

**Geänderte Funktionen**
- **F85 Übersicht aller Infusionspläne (1.1, 1.2, 1.4):** „Erstellt“ und „Freigegeben“ immer als Datum (nie „heute“/
  „gestern“), mit Person in derselben Zeile; Laufzeit, Rate und Tage/Woche in einer Spalte „Infusion“, Zeilen ohne
  Umbruch. Der Status zeigt beim Überfahren die Frist: „Frist: TT.MM.JJJJ – ab dann gilt der Plan als alt“ bzw.
  „Frist abgelaufen am …“ (neues Feld `alt_ab` = gültig ab + Grenzwert „Plan-Alter-Warnung“).
- **F31 Infusionspläne eines Patienten (1.3):** „Ansicht wie PDF“ als kleine Vorschau (höchstens 340 px breit, blätterbar)
  wie unter „Dokumente“; Klick auf das Blatt oder „Groß ansehen“ öffnet die große Ansicht mit Zoom in einem Fenster.
- **F97 / F98 (2, 3):** In der Akte gibt es keinen senkrechten Teiler mehr (Patientenliste und Plan-Editor behalten ihn).
  Der Kurz-Verlauf neben den Kontakten (ab 2560 px) entfällt – der Verlauf steht nur im eigenen Reiter.
- **F03, F05, F09, F52** siehe F99 und F100; **F20, F72** siehe F104; **F86** siehe F102.

### F98 Karten im Raster mit Menü „⋯“
- **Ansicht:** Akte › Übersicht (Gewichtsverlauf, Termine, aktueller Plan, Diagnose und Therapie, letzte Kontakte,
  Anschrift, Ärzte, Bezugspersonen), › Diagnose & Therapie (Diagnose, Therapie, Empfehlung, Hinweis), › Kontakte
  (Kontakte, Hinweis, Erreichbarkeit, Termine), Administration › System (Auslastung, Tätigkeiten, Verlauf der
  Tätigkeiten, Server, EPM, Hinweis an alle, Angemeldet). Spalten wie auf der Startseite (1/2/3/4/5 je Fensterstufe;
  System 1/1/2/3/4). Jede Karte hat oben rechts „⋯“: Breite 1 Spalte bis ganze Breite, Höhe automatisch oder 1–4 Zeilen
  (Inhalt scrollt in der Karte), Standardgröße. Karten rücken lückenlos auf (Raster mit 8-px-Zeilen, Höhe gemessen).
- **Speichern:** `PATCH /api/auth/ich/ {"bereiche": {"<seite>": {"<karte>": {"breite": 1–5, "hoehe": 0–4} | null}}}`
  (Feld `User.bereiche`, Migration `accounts/0005`); nur bekannte Seiten und Karten, `null` = Standard.
- **Teststatus:** Backend-Tests `accounts.tests` (Bereiche prüfen, zusammenführen, zurücksetzen). Browsertests
  `oberflaeche.spec.ts` „1920 px – Karten der Akte im Raster …“ (Breite, Höhe, gespeichert, keine Überdeckung,
  Standardgröße, Therapie und Kontakte ohne Verlauf), `system.spec.ts` (Größe der Auslastung), Neustart in
  `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F99 Zwei-Faktor-Anmeldung freiwillig (6.5)
- **Regel:** Modell `Anmelderegeln` (eine Zeile, mit Historie): `freiwillig` (Standard), `admins`, `alle`;
  `GET/PUT /api/benutzer/anmeldung/` (Recht „Benutzer verwalten“, Audit-Log). Wer einen zweiten Faktor eingerichtet hat,
  wird bei der Anmeldung immer danach gefragt. Ist er Pflicht und fehlt, führt die Anmeldung wie bisher zur Einrichtung.
- **Selbst:** Mein Konto › Einrichten (QR-Code, Notfall-Codes); Ausschalten nur solange freiwillig, mit Kennwort und Code
  (`POST /api/auth/2fa/ausschalten/`). Startseite: einmaliger, ausblendbarer Hinweis (`startseite.zweifaktorhinweis_aus`).
- **Bestätigungen** (endgültig löschen F73/F80, Wiederherstellen, Updates/Neustart, Sicherungs-Passwort, Ziel, Import):
  immer Kennwort **und** Code (Festlegung 03.10.2026, U34). Ohne eingerichteten zweiten Faktor wird abgewiesen
  (`accounts.zweifaktor.OHNE_ZWEITEN_FAKTOR`: „Bitte zuerst unter Mein Konto … einrichten“); die Oberfläche zeigt den
  Hinweis mit Verweis auf Mein Konto und lässt den Knopf aus. Der Django-Admin verlangt ebenfalls einen zweiten Faktor.
- **Konten-Kachel und System:** „ohne 2FA“ nur, wo er Pflicht ist; „Notfall-Codes knapp“ nur mit eingerichtetem Faktor.
- **Teststatus:** Backend-Tests `accounts.tests` (Regel, Anmeldung mit und ohne Faktor, Pflicht, Ausschalten, Bestätigung
  ohne Code), `patienten.tests`, `system.tests`. Browsertest `anmeldung.spec.ts` „Erste Anmeldung: eigenes Passwort;
  Zwei-Faktor-Anmeldung freiwillig einrichten und wieder ausschalten“; Bestätigungen mit Code in `system.spec.ts`,
  `zzz-sicherung.spec.ts`, `datenschutz.spec.ts`, `dokumente-falsch.spec.ts` (Testkonten haben einen Faktor).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F100 Ohne Login, Rolle „Keine Berechtigung“, Testbenutzer-Schalter (6.1, 6.2, 6.4)
- **Ohne Login:** `POST /api/benutzer/<id>/ohne-login/` – Konto inaktiv, Kennwort unbrauchbar, Authenticator und
  Notfall-Codes gelöscht, Sitzungen beendet, Rolle `keine`, kein Testzugang; Einträge bleiben zugeordnet. Beim Anlegen
  `{"ohne_login": true}`. Nicht für das eigene Konto.
- **Login geben:** `POST /api/benutzer/<id>/login-geben/ {"rolle": "mitarbeiter"}` – Rolle setzen, Einmal-Kennwort für das
  Zugangsblatt (wie beim Anlegen).
- **Rolle „Keine Berechtigung“ (`keine`):** hat nie Rechte (nicht einstellbar, nicht in der Rechtetabelle); angemeldet sieht
  man nur Startseite, Hilfe und Mein Konto. Bestehende Konten ohne Login bekommen sie per Migration.
- **Testbenutzer:** Schalter im Konto, für Betrachter, Mitarbeiter und Mediziner (nicht Admin, nicht das eigene Konto).
- **Teststatus:** Backend-Tests `accounts.tests`. Browsertest `admin.spec.ts` „Benutzer ohne Login: anlegen, setzen,
  wieder einbinden; Rolle „Keine Berechtigung“; Testbenutzer-Schalter“.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F101 Testpatient beim Anlegen (6.4, Nachtrag)
- **Ansicht:** Neuer Patient › „als Testpatient anlegen“; Nummer ab 9001 (`GET /api/patienten/naechste-nummer/?testpatient=1`),
  `POST /api/patienten/ {"testpatient": true}`. Testbenutzer und Admins legen weiterhin immer Testpatienten an
  (`testpatient_fest`).
- **Teststatus:** Backend-Test `patienten.tests`; Browsertest `patienten.spec.ts` „Neuer Patient als Testpatient …“.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F102 Auslastung mit Zeitraum, Konten mit direktem Weg (4.1–4.3)
- **Zeitraum:** `GET /api/system/verlauf/?zeitraum=1h|3h|24h|7t|14t|1m|6m`. Der Systemagent (Version 3) hält neben den
  Minutenwerten (24 h) Mittelwerte je 15 Minuten (14 Tage), je Stunde (31 Tage) und je 6 Stunden (184 Tage) mit Spitzen
  (`cpu_max`, `ram_max`). Das Diagramm reicht immer über den ganzen Zeitraum, beschriftet Uhrzeit bzw. Datum, zeigt
  Spitzen gestrichelt und folgt der Kartengröße (F98). Die Wahl bleibt im Browser gemerkt.
- **Konten:** Namen (gesperrt, ohne 2FA, offenes Einmal-Kennwort) führen zur Person in der Benutzerverwaltung, das eigene
  Konto ohne 2FA zu Mein Konto › Einrichten; Regel der Zwei-Faktor-Anmeldung mit Verweis zur Einstellung.
- **Hinweis an alle Benutzer (4.3):** Warnungen deutlich größer (Titel, größere Schrift, kräftiger Rand).
- **Teststatus:** Backend-Tests `system.tests` (Zeiträume, Stufen). Browsertest `system.spec.ts` „System: Auslastung …“.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F103 Sicherung herunterladen, Aufbewahrung, hochladen (5.1–5.3)
- **Aufbewahrung:** `POST /api/backup/aufbewahrung/ {"tage": 7|14|30}` (Passwort und Code) → Auftrag an den
  Systemagenten, Datei `/etc/epm/sicherung/aufbewahrung`; `epm-backup.sh` liest sie (sonst `EPM_BACKUP_TAGE`, sonst 30).
  Wirkt mit der nächsten Sicherung; im Übertragungsziel gilt dessen eigene Aufbewahrung (F64, Standard 30 Tage).
- **Herunterladen:** `POST /api/backup/<stempel>/bereitstellen/` (Passwort und Code) → der Agent legt
  `epm-sicherung_<stempel>.tar` (alle Dateien der Sicherung unverändert, verschlüsselte bleiben verschlüsselt) für 2 Stunden
  in `<EPM_BASE>/system/download` (root:101, 0750); `GET /api/backup/<stempel>/datei/` liefert sie über Nginx
  (`X-Accel-Redirect`, Ort `/_geschuetzt/sicherung/`), jeder Abruf im Audit-Log.
- **Hochladen:** `POST /api/backup/hochladen/ {name, groesse}` → Stücke zu 4 MiB mit `PUT …/hochladen/<id>/?versatz=n`
  (unterbrochene Verbindung setzt an der Stelle des Servers fort), `DELETE` verwirft. `POST …/<id>/einlesen/
  {passwort?}` → der Agent prüft (nur Dateien genau einer Sicherung, Datenbank und Dokumente vorhanden, Prüfsummen,
  bestehende Sicherung wird nie überschrieben, Platz) und übernimmt sie mit Art „Hochgeladen“. Ist sie mit einem
  unbekannten Passwort verschlüsselt (anderer EPM-Server), wird das mitgegebene geprüft und als eigene Passwort-Nummer
  („fremd“) hinterlegt; ohne bzw. mit falschem Passwort bleibt die Datei liegen und lässt sich mit Passwort erneut
  einlesen. Zurückgespielt wird nur mit „Wiederherstellen“ (F63).
- **Teststatus:** Backend-Tests `system.test_sicherung` (Aufbewahrung, Bereitstellen, Datei, Stücke, Versatz, Einlesen).
  Browsertest `zzz-sicherung.spec.ts` „Backup: Aufbewahrung wählen, Sicherung herunterladen und als neue Sicherung wieder
  hochladen“ (echter Systemagent und echtes GnuPG in CI; Ablehnung einer schon vorhandenen Sicherung).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F104 Admins auch bei echten Akten (6.3)
- **Regel:** `accounts.rechte.AUCH_BEI_ECHTEN_AKTEN` = Akten abschließen, Dokumente einem anderen Patienten zuordnen,
  endgültig löschen (F73, F80). Alle anderen Patientendaten schreiben Admins weiterhin nur bei Testpatienten (U12).
- **Teststatus:** Backend-Tests `patienten.tests`; Browsertest `admin.spec.ts` „Admin: echte Akten nur lesen …“ (schließt
  eine echte Akte ab).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F105 Kein Infusionsplan nötig (Ergänzung zur Fehlerliste, 02.10.2026)
- **Anlass:** „Infusionspläne müssen erstellt werden, einige Patienten benötigen keinen – Option, dies zu bestätigen und
  damit die Warnung auf der Startseite usw. zu unterdrücken.“
- **Hinweis (neu, abgeleitet):** Akte in Betreuung ohne aktuell gültigen (freigegebenen) Plan → Hinweis „Kein
  Infusionsplan“ in der Patientenliste (zählt bei „Nur mit Hinweisen“), Filter `?pruefen=ohne_plan`, Eintrag in „Nach
  und nach prüfen“ auf der Startseite (`pruefen.ohne_plan`), Hinweis in der Akte (Übersicht, Infusionspläne).
- **Bestätigen:** `POST /api/patienten/<id>/kein-plan/ {"kein_plan": true, "grund": "…"}` (Recht „Akten bearbeiten“,
  Admins nur bei Testpatienten, nicht bei abgeschlossenen Akten); `{"kein_plan": false}` hebt auf. Felder `kein_plan`,
  `kein_plan_grund`, `kein_plan_am`, `kein_plan_von` (Migration `patienten/0009`), im Verlauf der Akte. Unterdrückt
  für diesen Patienten: „Kein Infusionsplan“, „Plan älter als …“ (Patientenliste, Startseite, Gruppe „Älter als …“ der
  Übersicht, Status „aktuell, alt“), „Infusionsplan prüfen“ im Kalender. Aktenkopf: „Aktueller Plan: nicht nötig“.
- **Ende:** Mit der nächsten Freigabe (oder dem Abschließen nach Freigabe) eines Plans endet die Bestätigung von selbst.
- **Teststatus:** Backend-Tests `infusionen.tests.KeinPlanNoetig` (Hinweis, Filter, Startseite, Rechte, Aufheben, alter
  Plan ohne Warnung in Liste/Startseite/Übersicht/Kalender, Freigabe hebt auf). Browsertest `infusionsplaene.spec.ts`
  „Kein Infusionsplan nötig: bestätigen unterdrückt den Hinweis, aufheben bringt ihn zurück“.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F106 Testdaten ausblenden (Ergänzung vom 03.10.2026)
- **Anlass:** „Ausblenden / Entfernen der Testuser für alle durch Berechtigung möglich.“ Rückfragen geklärt:
  Testbenutzer **und** Testpatienten; Entfernen heißt **immer nur ausblenden** (nichts wird gelöscht).
- **Recht „Testdaten sehen (Testpatienten und Testbenutzer)“** (`testdaten_sehen`), unter Benutzer › Rechte je Gruppe:
  ohne das Recht gibt es Testpatienten nicht (`patienten_fuer` – Liste, Suche, Akte, Kalender, Startseite, Pläne,
  Auswahlfelder) und Testbenutzer erscheinen in keiner Liste (`sichtbare_benutzer`); einen Testpatienten kann man dann
  nicht anlegen. Standard: alle Rollen (wie bisher). Admin fest (legt nur Testpatienten an). Testbenutzer sehen ihre
  Testpatienten immer.
- **Testbenutzer ausblenden:** `POST /api/benutzer/<id>/ausblenden/` (nur Testbenutzer, nicht das eigene Konto),
  `POST /api/benutzer/testbenutzer-ausblenden/` (alle), `POST /api/benutzer/<id>/einblenden/`. Ausblenden sperrt,
  beendet alle Anmeldungen und setzt `ausgeblendet_am` (Migration `accounts/0006`); das Konto fehlt in der
  Benutzerliste (außer `?ausgeblendete=1`, „Ausgeblendete zeigen“), in Konten, Anmeldung/2FA und Systemzahlen.
  Einträge bleiben zugeordnet; Entsperren geht nur über „Einblenden“. Audit-Log.
- **Teststatus:** Backend-Tests `accounts.tests.TestdatenAusblenden`. Browsertest `admin.spec.ts` „Testbenutzer
  ausblenden und wieder einblenden; Recht „Testdaten sehen“ je Gruppe“.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F107–F109 Testphase und Go-live (Klärung U27/U32 vom 03.10.2026)
- **Anlass:** „Menüpunkt in System ‚Datenbank löschen‘ mit 2FA, ablesbarem Code und Passwort und einer ‚Wollen Sie wirklich
  die Datenbank löschen‘-Abfrage, um eine leere Datenbank zu bekommen. Des Weiteren der Punkt, um nicht automatisch
  Testpatienten anzulegen.“ – „Import nach dem Import ausblenden, wieder einblendbar.“ Rückfragen geklärt: alles aus der
  Testphase muss weg (Einträge, Dokumente, Benutzer, Patienten, Versorger, Ärzte), Präparate und Vorlagen bleiben;
  vorher immer sichern; welche Konten bleiben, wird im Dialog ausgewählt; das Audit-Log wird ebenfalls geleert.
- **Karte „Testphase und Go-live“** unter Administration › System (Recht „Systemverwaltung“).
- **F107 Datenbank leeren** (nur Rolle Admin): `POST /api/system/leeren/vorbereiten/` liefert Umfang, alle Konten und
  einen Bestätigungscode (6 Zeichen, 10 Minuten, in der Sitzung). `POST /api/system/leeren/` mit `bestaetigung`
  (abgetippter Code), `wirklich: true` (Rückfrage „Wollen Sie wirklich die Datenbank löschen?“ – „Nein, zurück“ /
  „Ja, Datenbank leeren“), `behalten` (Konten-IDs; das eigene Konto bleibt immer), `kennwort`, `code` (2FA, Pflicht),
  `minuten`, `hinweis` → Auftrag `datenbank_leeren` an den Systemagenten. Der Agent sichert vorher (Art
  „vor_leeren“, auf der Backup-Seite „Vor Datenbank leeren“; ohne Sicherung wird nicht geleert) und ruft `manage.py epm_datenbank_leeren` auf
  (`system/leeren.py`). Entfernt: alle Akten (echte und Testpatienten) mit Einträgen, Plänen, Dokumenten, Historie und
  Dateien, Löschprotokoll und Löschliste, Merklisten, Stand und Läufe des Altdaten-Imports, Versorger mit
  Ansprechpartnern, Ärzte, die nicht ausgewählten Benutzer (Verweise darauf gehen auf das ausführende Konto bzw. werden
  geleert) und das Audit-Log; alle anderen Anmeldungen werden beendet. Es bleiben Präparate, Auswahllisten, Grenzwerte,
  Briefkopf, Dokumentvorlagen, Rechte, Hilfe-Ergänzungen und die Sicherungen. Das Audit-Log beginnt mit „Datenbank
  geleert“ (Anzahlen, Sicherung vorher); Wiederherstellungen aus der Zeit davor werden danach nicht noch einmal
  nachgetragen (sonst endeten erneut alle Anmeldungen). Der Dialog schlägt vor: echte Konten bleiben, Testkonten und Konten ohne Login
  gehen.
- **F108 Musterdaten automatisch anlegen** (`Einstellungen.musterdaten_automatisch`, Standard an): aus → `epm_musterdaten`
  legt beim Start nur noch Auswahllisten und Präparate an, keine Testkonten und Testpatienten. „Datenbank leeren“
  schaltet ihn aus. „Testdaten zurücksetzen“ (F57) bleibt davon unberührt.
- **F109 Import ausblenden** (`Einstellungen.import_ausgeblendet`): der Menüpunkt „Import“ verschwindet für alle; die
  Seite bleibt über die Karte erreichbar und weist auf das Wiedereinblenden hin. `GET /api/auth/ich/` liefert
  `import_ausgeblendet`.
- Beide Schalter: `POST /api/system/einstellungen/` (`musterdaten_automatisch`, `import_ausgeblendet`, je Wahrheitswert),
  Historie der Einstellungen und Audit-Log. Migration `stammdaten/0011`.
- **Teststatus:** Backend-Tests `system.test_leeren` (Ablauf und Prüfungen, Leeren, Schalter, Systemagent). Browsertest
  `zzzz-leeren.spec.ts` (läuft als letzte Datei; beim manuellen Start mit Bildschirmfotos übersprungen).
- **Status:** ABGESCHLOSSEN UND GETESTET


## Q · Wünsche aus der Praxis (Alice, 06.10.2026)

Grundlage: zwei E-Mails vom 06.10.2026 (sieben Punkte, dazu die Liste der Laborparameter). Fachliches Konzept und
alle offenen Fragen stehen in `docs/WUENSCHE-PRAXIS-2026-10-06.md`.

### F110 Infusionstage je Beutelart
- **Anlass:** „Ist es möglich, dass man die Infusionstage pro Woche hinterlegen kann, gern auch unabhängig von der
  Zusammensetzung des Infusionsplanes. Beispiel: PE 5x / Woche, Elektrolytbeutel: 2x / Woche, Infusionsfreie Tage: keine.“
- **Felder am Plan:** `tage_pro_woche` (bisher „Tage pro Woche“, jetzt **PE / Mischbeutel**), `zusatz_tage_pro_woche`
  (Zusatzvolumen, „Elektrolytbeutel“), `freie_tage_pro_woche` (infusionsfreie Tage, 0 = keine).
  Migration `infusionen/0007`, Prüfregeln 1–7 bzw. 0–6 als Datenbank-Bedingung.
- **Plausibilität:** Höchstens `7 − max(PE, Zusatz)` infusionsfreie Tage – mehr passen nicht zu den Infusionstagen.
- **Übernahme in den Folgeplan:** Alle drei Felder stehen in `PLANFELDER` und werden beim neuen Entwurf vorbelegt
  (Alices Vermutung stimmt, das war schon so). Sie erscheinen im Vergleich mit dem Vorgänger (`VERGLEICHSZEILEN`).
- **PDF:** Datenfelder `{{Plan.Tage_pro_Woche}}`, `{{Plan.Zusatz_pro_Woche}}`, `{{Plan.Infusionsfreie_Tage}}`;
  der Block „Infusionstage“ steht in der Startvorlage. **Bestehende Installationen** behalten ihre aktive
  Vorlagenversion – der Block ist dort unter Vorlagen › Dokumentvorlagen einmal zu ergänzen.
- **Teststatus:** Backend-Tests `patienten.test_praxiswuensche.InfusionstageTest`. Browsertest
  `praxiswuensche.spec.ts` „Infusionstage je Beutelart im Plan-Editor“.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U39–U41.

### F111 Präparate: Zusatzvolumen, Natrovit, Taurolidin, Hinweis am Präparat
- **Anlass:** „Dipeptamen und Omegaven können eigentlich raus. Beim Zusatzvolumen bräuchte ich die folgenden
  Präparate: Sterofundin ISO, Ringer-Lösung, Ringer-Lactat, NaCl 0,9%, Jonosteril. Bei den Vitaminen bitte noch
  ergänzen: Natrovit … Nachbesserung beim Taurolidin: NutriLock (reines Taurolidin 2%) und TauroLock (Taurolidin mit Citrat).“
- **Neues Feld `Praeparat.hinweis`** (Migration `stammdaten/0012`): kurzer Text, erscheint bei der Auswahl und auf der
  Plan-PDF. Gepflegt unter Vorlagen › Auswahllisten.
- **Datenmigration `stammdaten/0013`:** „Sterofundin“ → **Sterofundin ISO**, „Ringer-Infusionslösung“ → **Ringer-Lösung**,
  „Junosteril“ → **Jonosteril** (Tippfehler); **Ringer-Lactat** neu; **Natrovit** (Hinweis „baugleich zu Cernevit,
  günstiger (Regressgefahr)“), **NutriLock** (Hinweis „reines Taurolidin 2 %“), **TauroLock** (Hinweis „Taurolidin mit
  Citrat“). **Dipeptamin** und **Omegaven** werden ausgeblendet – bestehende Pläne behalten sie, neu wählbar sind sie
  nicht mehr (in EPM wird nichts gelöscht).
- **Teststatus:** Backend-Tests `patienten.test_praxiswuensche.PraeparateTest`.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U42, U43.

### F112 Katalog der Laborparameter
- **Anlass:** „Ich muss jedes Labor händisch abschreiben … Ist es vielleicht möglich gewisse Standard-Parameter
  vorzugeben, wo ich dann nur den gemessenen Wert und meinetwegen die Messeinheit eintragen kann.“
- **Modell `stammdaten.Laborparameter`** (Migration `stammdaten/0012`): Gruppe (15 Gruppen), Name, Kurzname, Einheit,
  Referenzbereich von/bis (freiwillig), Reihenfolge, aktiv. Nie gelöscht, nur deaktiviert.
- **Vorbelegt** mit Alices Liste (`patienten.testdaten.LABORPARAMETER`, auch als Datenmigration `stammdaten/0013`):
  Transaminasen, Nierenwerte, Eisenhaushalt, Eiweiß-/Fettstoffwechsel, Elektrolyte, Spurenelemente, Hämatologie,
  Vitamine, Knochenstoffwechsel, Pankreasenzyme, Blutzucker/Diabetes, Schilddrüse. „Vitamin B1, B2, B6, B12,
  Folsäure“ und „Vitamin D, D3, Calcidiol, Calcitriol“ je als eigener Parameter (U46).
- **API:** `/api/laborparameter/` (lesen: jeder Angemeldete – die Erfassungsmaske braucht den Katalog; schreiben:
  Recht „Vorlagen pflegen“), `POST /api/laborparameter/reihenfolge/`. Oberfläche: Vorlagen › Labor und Diagnosen.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U44–U46.

### F113 Laborbefunde erfassen
- **Modelle `befunde.Laborbefund` und `befunde.Laborwert`** (neue App, Migration `befunde/0001`): Befund mit
  Abnahmedatum, Labor, Beurteilung (formatiert) und optional dem Originalbefund als Dokument der Akte; je Wert
  Parameter aus dem Katalog **oder** Freitextname (Tumormarker, genetische Parameter), Zahl **oder** Werttext
  („< 0,1“, „negativ“), Einheit und Referenzbereich (aus dem Katalog vorbelegt, überschreibbar).
- **Regeln:** Teil der Akte (gesperrt, sobald die Akte abgeschlossen ist), Historie je Befund und je Wert; ein
  Parameter nur einmal je Befund; eine Zeile braucht eine Bezeichnung und einen Wert (Datenbank-Bedingungen).
  Beim Ändern werden die Zeilen vollständig ersetzt – für die Maske eindeutig.
- **API:** `/api/laborbefunde/?patient=` (lesen, anlegen, ändern; Recht „Kontakte, Gewichte, Termine, Dokumente
  erfassen“), `GET /api/laborbefunde/verlauf/?patient=&parameter=` für den Verlauf eines Parameters (U58).
- **Oberfläche:** Reiter „Labor & BIA“ der Akte; die Maske zeigt die Parameter nach Gruppen, eingetragen wird nur der
  Wert. Darunter freie Zeilen für weitere Parameter.
- **Teststatus:** Backend-Tests `befunde.tests.LaborTest`. Browsertest `praxiswuensche.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U47, U48, U58.

### F114 BIA-Messungen
- **Anlass:** „Bei den BIA-Messungen wäre es das gleiche … Gewicht (kg), BCM (kg), Fettmasse (kg), ECW (%),
  Körperwasser (L), BMI. Und gern noch ein Feld, wo man eine Zusammenfassung / Beurteilung eintragen kann.“
- **Modell `befunde.BiaMessung`:** genau diese Werte, dazu Beurteilung (formatiert), optional das Geräteprotokoll als
  Dokument, abgeleitet `bmi_berechnet` (aus Gewicht und hinterlegter Größe) und `magermasse_kg`.
- **Gewicht in den Verlauf:** Häkchen beim Speichern (`gewicht_uebernehmen`, vorbelegt „ja“) legt eine
  Gewichtsmessung an und verknüpft sie – doppelte Einträge sind so ausgeschlossen (U50).
- **Plausibilität:** Gewichtsgrenzen wie beim Gewicht, ECW 0–100 %, Fettmasse und BCM nicht größer als das Gewicht,
  Körperwasser nicht mehr Liter als das Gewicht Kilogramm, mindestens ein Messwert.
- **Teststatus:** Backend-Tests `befunde.tests.BiaTest`. Browsertest `praxiswuensche.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U49, U50.

### F115 Berichte aus der Akte
- **Anlass:** „Kann man dann direkt Berichte für die Patienten innerhalb der Patientenakte verfassen? Gern auch mit
  der Option ‚Entwurf‘ und ‚Freigabe‘.“
- **Modell `berichte.Bericht`** (neue App, Migration `berichte/0001`): Titel, Berichtsart (neue Auswahlliste
  „Berichtsarten“), Datum, Empfänger, Inhalt (formatiert), Status **Entwurf → freigegeben**.
- **Freigabe:** neues Recht **„Berichte freigeben“** (Standard: Mediziner und Admin, je Gruppe umstellbar – U54).
  `POST /api/berichte/<id>/freigeben/` erzeugt die PDF aus der neuen Dokumentvorlage **„Bericht“**, legt sie als
  Dokument der Akte ab (Prüfsumme und Vorlagenversion wie beim Plan) und macht den Bericht unveränderlich –
  im Modell **und** per Datenbank-Trigger (`epm_bericht_schutz`). Korrektur = neuer Bericht. Audit-Log
  `bericht_freigegeben`.
- **Teststatus:** Backend-Tests `berichte.tests.BerichtTest` (inkl. Trigger). Browsertest `praxiswuensche.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U54, U55, U59.

### F116 Unterlagen für die Sprechstunde
- **Anlass:** „Ist es vielleicht für die Vorarbeit zur Sprechstunde möglich, die aktuellsten Daten (BIA, Labor,
  Infusionsplan, Diagnosen, letzte Empfehlungen) in einem Dokument zu bündeln?“
- **`GET /api/patienten/<id>/sprechstunde/`** erzeugt die PDF aus der neuen Dokumentvorlage „Unterlagen für die
  Sprechstunde“: Patientenkopf mit Gewicht, BMI und Trend, Diagnosen (ICD), Diagnose-Freitext, aktueller
  Infusionsplan mit Zusammensetzung und Infusionstagen, letzte BIA-Messung mit Beurteilung, letzter Laborbefund mit
  Beurteilung, letzte Empfehlung. `?ablegen=1` legt das Blatt zusätzlich als Dokument der Akte ab (Recht „Einträge
  erfassen“, nur bei offenen Akten). Audit-Log `sprechstunde_erzeugt`.
- **Teststatus:** Backend-Tests `patienten.test_praxiswuensche.SprechstundeTest`. Browsertest `praxiswuensche.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U56, U60.

### F117 Diagnosen mit ICD-Code
- **Anlass:** „Kann man im Hintergrund eine Liste mitführen (lassen), wo man Diagnosen mit dem jeweiligen ICD-Code
  einfügt, und diese ICD dann auch in der Diagnose-Liste mit auftauchen. Bsp: Kurzdarmsyndrom [K91.2G] …“
- **Modell `patienten.Diagnose`** (Migration `patienten/0010`): Bezeichnung, ICD-Code, Zusatzkennzeichen
  **G/V/Z/A** (Pflicht), „besteht seit“, Notiz, Reihenfolge, aktiv/beendet. Anzeige `Kurzdarmsyndrom [K91.2G]`.
  Nicht gelöscht, sondern auf „nicht mehr zutreffend“ gesetzt; jede Fassung im Verlauf.
- **Katalog `stammdaten.Diagnosevorlage`:** ICD-Code und Bezeichnung. Jede neue Kombination aus einer Akte wandert
  automatisch in den Katalog (U53) und wird beim nächsten Eintragen vorgeschlagen; gepflegt unter Vorlagen › Labor
  und Diagnosen.
- **Prüfung:** ICD-Format `^[A-Z]\d{2}(\.\d{1,2})?[+*!]?$`, Kleinschreibung wird vereinheitlicht.
- **Das lange Freitextfeld „Diagnose“ bleibt daneben bestehen** (U51); die Akte zeigt beides.
- **Teststatus:** Backend-Tests `patienten.test_praxiswuensche.DiagnosenTest`. Browsertest `praxiswuensche.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U51–U53.

### F118 Versichertendaten
- **Anlass:** „In Anbetracht der Debatten mit den Krankenkassen ist es nötig, dass wir auch die Versichertendaten der
  Patienten in den Stammdaten dokumentieren. Da wäre der Oberpunkt GKV oder PKV, und dann die Versicherung und
  Versichertennummer.“
- **Felder am Patienten** (Migration `patienten/0010`): `versicherungsart` (GKV, PKV, Selbstzahler, Sonstige, nicht
  erfasst), `versichertennummer`. Das bisherige Feld `krankenkasse` behält seinen Spaltennamen und heißt in der
  Oberfläche **„Versicherung“** – es geht nichts verloren und nichts muss umgezogen werden.
- **Sichtbar** in Stammdaten, „Neuer Patient“, der Übersicht der Akte, der Kopie der Akte (Art. 15 DSGVO) und als
  Datenfelder `{{Patient.Versicherungsart}}`, `{{Patient.Versicherung}}`, `{{Patient.Versichertennummer}}`.
- **Teststatus:** Backend-Tests `patienten.test_praxiswuensche.VersichertendatenTest`. Browsertest
  `praxiswuensche.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U57.

### F119 Hinweise mit „×“ ausblenden
- **Anlass:** „Alle Meldungen können mit einem x entfernt werden (wenn akut keine Erneuerung benötigt wird).“
  Rückfrage vom 07.10.2026 geklärt: **beim Wegklicken wird gewählt, wie lange Ruhe sein soll – oder dass es nicht
  mehr nötig ist.**
- **Modell `patienten.Hinweisruhe`** (Migration `patienten/0011`): Akte, Art des Hinweises (Gewichtsverlust, Plan zu
  alt, kein Plan, Versorger nicht erfasst, Kontakt fällig, Labor zu alt, BIA zu alt), `bis` (Frist) oder leer für
  „nicht mehr nötig“, Grund, Person und Zeitpunkt. Gelöscht wird nichts: Das Zurückholen trägt `aufgehoben_am` und
  die Person ein, `delete()` ist gesperrt. Eine Datenbankregel lässt je Akte und Art nur **eine laufende**
  Stummschaltung zu.
- **Fristen:** 3, 6 oder 12 Monate – danach erscheint der Hinweis von allein wieder – oder „nicht mehr nötig“, dann
  bleibt er weg, bis jemand ihn in der Akte wieder einschaltet. Nochmal wegklicken verlängert: die bisherige
  Stummschaltung endet, die neue tritt an ihre Stelle (beides bleibt im Verlauf).
- **`GET`/`POST /api/patienten/<id>/hinweis-ruhe/`:** `{"art": "labor", "monate": 6, "grund": "…"}` schaltet stumm,
  `{"art": "labor", "dauerhaft": true}` heißt „nicht mehr nötig“, `{"art": "labor", "aufheben": true}` holt den
  Hinweis zurück. Recht „Akten bearbeiten“, nur bei offenen Akten.
- **Oberfläche:** Jeder Hinweis-Chip der Patientenliste hat ein **×**; der Dialog fragt die Frist und den Grund ab.
  Was gerade ausgeblendet ist, steht in der Übersicht der Akte unter **„Ausgeblendete Hinweise“** mit Grund, Person
  und Frist – dort auch „Wieder einschalten“. Alles steht im Verlauf der Akte (Bereich „Hinweise ausgeblendet“).
  Startseite und Patientenliste zählen stummgeschaltete Akten nicht mehr mit, damit Kachel und Liste dasselbe zeigen.
- **Löschen und Kopie:** `Hinweisruhe` samt Historie wird beim endgültigen Löschen entfernt und in `umfang()` gezählt.
- **Teststatus:** Backend-Tests `patienten.tests.HinweiseStummschalten` (13 Tests, inkl. Datenbankregel und
  Löschsperre). Browsertest `praxiswuensche.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET. Offen: U61.

### F120 Ab wann ein Befund als zu alt gilt
- **Anlass:** „12 Monate als zu alt für Befunde, jedoch einstellbar unter Vorlage.“
- **Einstellungen** (Migration `stammdaten/0014`): `labor_alter_warnung_monate` und `bia_alter_warnung_monate`,
  Standard **12 Monate**, mindestens 1 Monat, einstellbar unter **Vorlagen › Grenzwerte** neben der Grenze für den
  Infusionsplan.
- **Hinweise je Akte:** „Kein Laborbefund“ bzw. „Labor älter als N Mon.“ und dasselbe für die BIA-Messung – nur bei
  Akten in Betreuung. Sie erscheinen als Chip in der Patientenliste (und lassen sich dort mit **×** ausblenden, F119).
- **Startseite „Nach und nach prüfen“:** zwei neue Zeilen „Laborbefund fehlt oder ist älter als N Monate“ und
  „BIA-Messung fehlt oder ist älter als N Monate“, mit Sprung in die Patientenliste
  (`?pruefen=labor_faellig` bzw. `bia_faellig`).
- **In der Akte** nennen die Reiter „Labor“ und „BIA“ oben das Datum der letzten Erfassung und warnen, wenn es über
  der Grenze liegt.
- **Teststatus:** Backend-Tests `patienten.tests.BefundGrenzwerte` (9 Tests). Browsertest `praxiswuensche.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET.

### F121 Ein eigener Reiter je Bereich der Akte
- **Anlass:** „Teile alles in einzelne Menüpunkte, auch Diagnose, Therapie und Befunde.“ Rückfrage vom 07.10.2026
  geklärt: **nur Reiter in der Akte**, keine zusätzlichen Einträge in der Seitenleiste; der Reiter „Therapie“ zeigt,
  **wann sie zuletzt geändert** wurde.
- **Aufteilung:** „Diagnose & Therapie“ wird zu **„Diagnosen“** (Liste mit ICD-Code und Freitext „Diagnose“) und
  **„Therapie“** (Therapie, Empfehlung, Bemerkung); „Labor & BIA“ wird zu **„Labor“** und **„BIA“**. Die Reiter
  tragen jetzt Zähler für Diagnosen, Laborbefunde, BIA-Messungen und Berichte und brechen bei schmalem Fenster um.
- **Alte Adressen:** `/patienten/<id>/befunde` leitet auf `/labor` weiter, damit gespeicherte Links weiter stimmen.
- **Karten im Raster:** neue Seite `akte_diagnosen`; `akte_therapie` enthält jetzt Therapie, Empfehlung, Bemerkung und
  den Hinweis. Dabei behoben: Die Karte **Bemerkung** war nie in der Liste der verstellbaren Karten – ihr Menü „⋯“
  lief ins Leere (Fehler seit F97).
- **Übersicht der Akte:** neue Karte **„Labor und BIA“** mit der letzten Erfassung und dem Weg in die beiden Reiter;
  die Karte „Diagnose und Therapie“ führt jetzt in beide Reiter.
- **Teststatus:** Browsertests `praxiswuensche.spec.ts`, `akte.spec.ts`, `oberflaeche.spec.ts`, `zz-neustart.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET.

### F123 EPM aus der Oberfläche aktualisieren
- **Anlass:** „Und eine `sudo epm-update` aus der UI unter System sollte möglich sein. Dann können nachfolgende
  Pushes installiert werden.“
- **Neue Aktion `epm_update`** im Katalog des Systemagenten (`system/host.py` und `rollout/epm-systemagent.py`):
  Passwort und zweiter Faktor, Warnung an die angemeldeten Benutzer mit Beginn sofort bis 60 Minuten, wie beim
  Neustart. Der Agent ruft `/usr/local/sbin/epm-update --ohne-tests` auf – getestet wird vor jedem Push in der CI.
- **Keine zusätzliche Sicherung davor:** `epm-update` sichert selbst, bevor es umstellt; zwei Sicherungen
  hintereinander wären nur Wartezeit.
- **Während des Umstellens** ist die Oberfläche kurz nicht erreichbar. Der Auftrag läuft auf dem Server weiter (der
  Agent ist ein Dienst auf dem Host, kein Container) und das Ergebnis erscheint danach unter Aufträge samt Ausgabe.
  Schlägt das Update fehl, bleibt die bisherige Version in Betrieb.
- **Die Oberfläche brauchte keine eigene Zeile:** Administration › System zeigt den Katalog der Aktionen seit F57
  von sich aus, mit Name, Beschreibung und den Hinweisen „Passwort + 2FA“ und „warnt Benutzer“.
- **Neuer Test `test_aktionen_im_backend_und_im_agenten_sind_dieselben`:** Backend und Agent führen zwei getrennte
  Listen derselben Aktionen. Weicht eine ab, nähme das Backend einen Auftrag an, den der Agent nicht ausführt – der
  Auftrag bliebe ohne Ergebnis liegen. Der Test vergleicht Codes, Namen und „Sicherung vorher“.
- **Teststatus:** Backend-Tests `system.tests.Auftraege` (Aktion, Rechte, zweiter Faktor, Gleichstand der Kataloge,
  echter Agent im Probelauf). Browsertest `system.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET.

### F122 Ein gemeinsames Muster für alle Reiter der Akte
- **Anlass:** „Die UI bitte auf allen Reitern in der Patientenakte vereinheitlichen, damit es überall gleich
  aussieht. Ich fände die Ansicht ähnlich der vom Infusionsplan relativ gut … Alle Knöpfe sollten auf jedem Reiter
  an der möglichst gleichen Position sein. Wir wollen nicht suchen.“ Dazu: „ggf. auch ein wenig kompakter, da der
  Bildschirm überfüllt wirkt.“
- **`Aktenseite.tsx`** gibt die Form vor: links die Einträge mit Datum, rechts der gewählte. Feste Plätze –
  Überschrift mit Anzahl links oben, darunter der Hauptknopf („Neue Diagnose“, „Neuer Laborbefund“, „Neuer
  Kontakt“ …), darunter die Liste, darunter der erklärende Satz; rechts der Kopf mit Titel und Zusatz, die
  Aktionen zum Eintrag immer oben rechts. Welcher Eintrag rechts steht, merkt sich die Adresse (`?befund=`,
  `?kontakt=` …), damit ein Link darauf zeigt und ein Neuladen die Auswahl behält – wie beim Infusionsplan.
  Die Abstände sind knapper als in den alten Karten.
- **Umgestellt:** Diagnosen, Therapie, Empfehlung, Labor, BIA, Berichte, Kontakte. Der Infusionsplan hatte die Form
  schon; Übersicht (Raster mit „⋯“), Verlauf (Tabelle) und Datenschutz (Vorgänge) behalten ihre. **Dokumente** war
  kurz mit umgestellt und ist auf Wunsch vom 07.10.2026 wieder in der ursprünglichen Form: Tabelle links mit Typ,
  Datum, Größe und Herkunft, Details rechts – „Dokumente müssten wie ursprünglich verwaltet werden.“
- **Diagnosen fasst beides zusammen** (Wunsch): die ICD-Liste und der frühere Freitext, der jetzt **Notizen**
  heißt und obenan in der Liste steht – mit seinem Datum, wie jeder andere Eintrag.
- **Therapie und Empfehlung** sind eigene Reiter; links stehen ihre Fassungen mit Datum, die aktuelle ist
  bearbeitbar, ältere sind nur lesbar. Damit ist auch „wann zuletzt geändert“ auf einen Blick zu sehen, ohne
  einen eigenen Dialog für die Versionen.
- **Bemerkung ist aus der Oberfläche verschwunden** („haben wir noch nie verwendet“). Das Feld bleibt: Der
  Altdaten-Import legt dort ab, was nicht ins vorgesehene Feld passte – im Wortlaut des Altsystems, damit nichts
  verloren geht (`altimport/umsetzung.py`, „extras“). Damit das nicht unsichtbar wird, zeigt die Übersicht es als
  **„Hinweise aus der Altdaten-Übernahme“**, nur lesbar und nur, wenn etwas drinsteht; im Verlauf steht es wie
  bisher. Die Rasterseiten `akte_diagnosen`, `akte_therapie` und `akte_kontakte` entfallen damit; gespeicherte
  Größen dieser Seiten bleiben unbeachtet liegen.
- **Verlauf:** Der Bereichsfilter ist mit den neuen Bereichen zu lang für eine Knopfreihe geworden und jetzt eine
  Auswahlliste, passend zur Person-Auswahl daneben.
- **Teststatus:** Browsertests `akte.spec.ts`, `praxiswuensche.spec.ts`, `dokumente.spec.ts`, `oberflaeche.spec.ts`,
  `zz-neustart.spec.ts`, `datenschutz.spec.ts`, `aa-import.spec.ts` – an das neue Muster angepasst.
- **Status:** ABGESCHLOSSEN UND GETESTET.

### F124 Ladebalken am oberen Rand
- **Anlass:** „Ich brauche Ladebalken bzw. Darstellung, was passiert, bei Updates, Speichern etc. Der obere
  Bildbereich soll als Ladebalken … in Orange (oder passend zum Farbschema) wie ein Ladebalken sich füllen und sich
  bewegen.“ Vorbild: die Umsetzung im Smokeping-Projekt.
- **`lib/laden.ts`** zählt die laufenden Anfragen; `api` und `apiDatei` melden jede Anfrage an und ab (auch bei
  Fehler oder Abbruch). Damit erfasst der Balken alles, was auf den Server wartet – Laden, Speichern, Hochladen,
  PDFs, die Abfragen der Aufträge –, unabhängig von der Abfrage-Bibliothek.
- **`Ladebalken.tsx`** in der Shell, ganz oben über allem (3 px, nimmt keine Klicks an): Läuft eine Anfrage länger
  als 150 ms, füllt sich der Balken in Orange (`--ladebalken`, je Farbschema), ein Lichtstreifen wandert darüber;
  sind alle Anfragen beantwortet, läuft er einmal voll und blendet aus. Kürzere Anfragen zeigen nichts – sonst
  flackerte er bei jeder Statusabfrage. Bei „weniger Bewegung“ (Systemeinstellung) ohne Animation.
- **Hintergrundarbeit** (Ergänzung 07.10.2026): Läuft ein Auftrag des Systemagenten – etwa „EPM aktualisieren“ –,
  melden die Seiten System und Backup das über `useHintergrundarbeit()`. Der Balken bleibt dann durchgehend in
  Bewegung (ein wandernder Abschnitt statt der Füllung), bis der Auftrag beendet ist; die kurzen Statusabfragen alle
  drei Sekunden ändern daran nichts. „Wie der Verlauf der Tätigkeit: so lange aktiv, bis der Job gelaufen ist.“
- **Status:** ABGESCHLOSSEN. Auf Wunsch ohne Testlauf eingespielt (`[skip ci]`); ein Browsertest steht noch aus.

## R · Passkey und Telefon (Festlegung 08.10.2026)

Festlegungen vom 08.10.2026: „Stiftungsseite“ = das ganze neue EPM. Passkey **statt des Authenticator-Codes** (zweiter
Faktor nach dem Passwort, neben App und Notfall-Codes; gilt auch für alle Bestätigungen). Aufruf künftig über einen
**Namen mit Zertifikat einer eigenen CA** (Passkeys gehen nicht über eine IP-Adresse). Mobile Ansicht „sofern möglich“:
Hauptarbeitsplatz bleibt der PC, am Telefon Pläne schnell freigeben, kurze Blicke in die Akte und Notizen. Damit gilt
„nur PC, keine Tablet-Optimierung“ (Altsystem-Datenanalyse) nicht mehr.

### F130 Passkey einrichten, umbenennen, entfernen
- **Ansicht:** Mein Konto › Anmeldung und Sicherheit › „Passkeys“ (Liste mit Name, angelegt, zuletzt verwendet,
  synchronisiert; „Passkey hinzufügen“, umbenennen, entfernen); erste Anmeldung mit Pflicht zum zweiten Faktor:
  Umschalter „Passkey | Authenticator-App“.
- **Endpunkte:** `POST /api/auth/passkey/optionen/` `{zweck: "registrieren"}` → Optionen für
  `navigator.credentials.create` (Challenge 5 Minuten in der Sitzung, einmal gültig; vorhandene Passkeys ausgeschlossen;
  User Verification Pflicht); `POST /api/auth/passkey/registrieren/` `{antwort, name}` → Status mit `passkey_neu` und –
  beim ersten zweiten Faktor ohne Notfall-Codes – `notfallcodes` (10, wie beim Authenticator); `GET /api/auth/passkeys/`;
  `PATCH /api/auth/passkeys/<id>/` `{name}`; `POST /api/auth/passkeys/<id>/entfernen/` `{kennwort, code | passkey}`.
- **Logik:** Modell `accounts.Passkey` ist ein django-otp-Gerät (öffentlicher Schlüssel, Zähler, Verbindungen, AAGUID,
  synchronisiert); Prüfung mit `py_webauthn` 2.x (`accounts/passkey.py`), Herkunft = `EPM_PASSKEY_ORIGINS` (Standard:
  `DJANGO_CSRF_TRUSTED_ORIGINS`), RP-ID = erster Name darin (`EPM_PASSKEY_RP_ID` überschreibt). Höchstens 10 je Konto.
  Der letzte zweite Faktor lässt sich nur entfernen, solange er freiwillig ist; dann gehen auch die Notfall-Codes.
  „2FA zurücksetzen“, „ohne Login“ und „Zwei-Faktor-Anmeldung ausschalten“ löschen auch Passkeys
  (`zweifaktor.faktoren_loeschen`).
- **Validierung:** Name ≤ 64 Zeichen; Antwort nur für diese Herkunft und RP-ID, mit User Verification, Challenge
  einmal; über eine IP-Adresse 400 mit Grund (`passkey.verfuegbar`).
- **Tabellen:** `accounts_passkey` (Migration `accounts/0008_passkey`)
- **Audit-Log:** `2fa_eingerichtet` bzw. `2fa_zurueckgesetzt` mit `passkey: <Name>`
- **Teststatus:** Backend-Tests `accounts.test_passkey.Passkeys.*` mit Software-Authenticator (echte P-256-Signaturen).
  Browsertest `passkey.spec.ts` (virtueller Authenticator des Browsers); Neustart in `zz-neustart.spec.ts`
  (Schlüssel in ein neues virtuelles Gerät übernommen, Anmeldung und Entfernen nach dem Neustart).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F131 Anmelden mit Passkey
- **Ansicht:** Anmeldung › nach dem Passwort „Mit Passkey anmelden“ (Umschalter „Passkey | Code“, wenn beides da ist);
  über eine IP-Adresse ein Hinweis auf den Namen, dann nur Code bzw. Notfall-Code.
- **Endpunkte:** `GET /api/auth/status/` → zusätzlich `passkey: {verfuegbar, rp_id, grund}` und im Schritt „2fa“
  `faktoren: {authenticator, passkey}`; `POST /api/auth/passkey/optionen/` `{zweck: "anmelden"}`;
  `POST /api/auth/passkey/` `{antwort}` → wie `POST /api/auth/2fa/` (Sitzung mit django-otp bestätigt).
- **Fehlerfälle:** 400 Aufgabe fehlt/abgelaufen · 401 Passkey nicht erkannt (zählt als Fehlversuch, beim fünften
  gesperrt) · 403 gesperrt
- **Teststatus:** Backend-Tests (Anmeldung, falsche Herkunft, fremde Challenge, Wiederholung derselben Antwort, ohne
  User Verification, Passkey eines anderen Kontos); Browsertest `passkey.spec.ts`.
- **Status:** ABGESCHLOSSEN UND GETESTET

### F132 Bestätigen mit Passkey
- **Ansicht:** jedes Feld „Code aus der Authenticator-App“ bei Bestätigungen (Backup, System, Import, Dokument und Akte
  endgültig löschen, Zwei-Faktor ausschalten, Passkey entfernen) ist jetzt der Baustein `useZweiterFaktor`
  (`components/ZweiterFaktor.tsx`): „Passkey | Code“, „Mit Passkey bestätigen“ → „Passkey bestätigt“.
- **Endpunkte:** unverändert; statt `code` geht `passkey` (Antwort auf Optionen mit Zweck „bestaetigen“) mit.
  `zweifaktor.zweiter_faktor_bestaetigt(request)` an allen Stellen (`system.api.bestaetigung_pruefen`, Import, Löschen).
- **Logik:** Das Kennwort wird zuerst geprüft – bei falschem Kennwort bleibt die Passkey-Antwort gültig. Eine geprüfte
  Antwort gilt genau einmal. Beim endgültigen Löschen bleiben Notfall-Codes ausgeschlossen, der Passkey zählt.
- **Teststatus:** Backend-Tests `test_bestaetigung_mit_passkey_statt_code`, `PasskeyBeiSystemauftraegen`;
  Browsertest `passkey.spec.ts` (Ausschalten mit Passkey, erst falsches, dann richtiges Passwort) und
  `zz-neustart.spec.ts` (Passkey entfernen mit Passkey).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F133 EPM am Telefon
- **Ansicht (unter 768 px):** Leiste unten (Start, Patienten, ＋ Notiz, Pläne → „Zur Freigabe“, Menü), Menü als
  Schublade mit allen Bereichen, Kopfzeile mit Zurück, Titel, Suche (Lupe) und Hilfe; Patientenliste und
  Infusionspläne als Karten; Akte: Reiter seitlich wischen, gewählter Eintrag bzw. Plan steht vor der Liste
  (Freigeben ohne Scrollen), Antippen eines Eintrags holt ihn in den Blick; Dialoge fast bildschirmfüllend, einspaltig;
  16 px in Eingabefeldern, Ziele zum Antippen ≥ 44 px; „＋ Notiz“ in einer offenen Akte für diesen Patienten.
- **Logik:** `lib/stufen.ts` `useMobil()` (unter 768 px), `detailZeigen()`; nur Oberfläche, keine neuen Endpunkte.
- **Teststatus:** Browsertest `mobil.spec.ts` (Pixel 7 mit Touch): Leiste, Menü, Suche, Zurück, keine Seite breiter als
  der Bildschirm (Start, Kalender, Akte, Patienten, Infusionspläne, Konto, Hilfe, Versorger), Entwurf über „Pläne“
  öffnen und freigeben, Notiz über die Leiste. Bildschirmfotos `bildschirmfotos-mobil.spec.ts` (manueller Start).
- **Status:** ABGESCHLOSSEN UND GETESTET

### F134 Zertifikat der eigenen CA (Server)
- **Werkzeug:** `sudo epm-zertifikat einrichten | erneuern | importieren CRT KEY [CA] | status`
  (`rollout/epm-zertifikat.sh`, von `04-projekt.sh` nach `/usr/local/sbin` installiert). CA mit P-256, 10 Jahre,
  **Namensbeschränkung** auf `EPM_WEB_NAME` und die Verwaltungs-IP; Serverzertifikat 397 Tage mit Kette.
  Stammzertifikat unter `https://<Name>/epm-ca.crt` (Nginx, öffentlich) und `/etc/epm/ca/epm-ca.crt`; CA-Schlüssel nur
  root, offline sichern. Ein neuer Server legt das Zertifikat gleich so an (`04-projekt.sh`), ein bestehendes bleibt bis
  zum Aufruf von `einrichten`.
- **Teststatus:** Skript lokal gegen OpenSSL 3 geprüft (CA, Kette, Namensbeschränkung, Erneuern).
- **Status:** ABGESCHLOSSEN (Server-Werkzeug; im Browsertest-Stack gibt es keine eigene CA)


## S · Aufbau der Patientenakte (Wunsch 08.10.2026)

> „Können wir 3 verschiedene Ansichten für Patienten erstellen? Das aktuelle mit den wichtigsten Daten in der Kopfzeile.
> Das zweite, das im linken Viertel die wichtigsten Daten anzeigt und die Buttons … an den oberen Rand setzt, die Reiter
> rechts davon, jedoch nicht als horizontale, sondern vertikale Reiter. Und eine andere Ansicht, die für eine
> Arzt-Software sinnvoll wäre.“ Nach den Entwürfen: Kopfzeile mit Abstufungen wie die Seitenleiste; Knöpfe in der
> Seitenleiste über dem Namen, etwas kleiner; Seitenleiste schmaler und selbst verstellbar, Kopfleiste ebenso; das Menü
> links bleibt 1:1; Auswahl unter Mein Konto.

### F135 Aufbau der Patientenakte je Person
- **Ansicht:** Mein Konto › Karte „Patientenakte“ (drei Ansichten mit Skizze; je nach Wahl Höhe des Kopfs bzw. Breite
  der Seitenleiste). Gilt für die Person an jedem PC; am Telefon (unter 768 px) immer „Kopfzeile“.
  - **Kopfzeile** (Standard): Name, Merken, Hinweise (Testpatient, abgeschlossen, Erklärungen) und CAVE (Nickelallergie,
    Gewichtsverlust) in einer Zeile, Knöpfe rechts; darunter die Angaben in vier Gruppen nebeneinander mit Trennlinie –
    Ernährung (Gewicht mit Trend, BMI mit Größe, aktueller Plan, Katheter), Versorgung (Versorger, Ansprechpartner,
    Hausarzt), Termine und Kontakt (nächster Termin, letzter Kontakt, Telefon), Hinweise und Auskunft (Nickelallergie,
    Auskunft an, Versicherung). Griff unter dem Kopf: nach oben/unten ziehen in drei Stufen „Nur Name“, „Eine Zeile“
    (Gewicht, Plan, Termin, Versorger, Nickelallergie), „Alle Angaben“; ↑ ↓ per Tastatur, Doppelklick = alle Angaben.
  - **Seitenleiste:** links eine Leiste (Standard 300 px) mit den Knöpfen Kontakt, Gewicht, Termin, Neuer Plan, ⋯ (klein)
    über dem Namen, darunter dieselben Gruppen untereinander; die Leiste bleibt beim Scrollen stehen. Rechts davon
    senkrechte Reiter in Gruppen (Akte, Betreuung, Befunde, Unterlagen), dann der Inhalt. Breite am rechten Rand ziehen,
    rastet bei 240/300/360/420/480 px ein, ← → per Tastatur, Doppelklick = 300 px. Unter 1280 px stehen Leiste, Reiter
    (waagerecht) und Inhalt untereinander.
  - **Karteikarte:** schmale Kopfzeile mit Name, Nummer, Geburtsdatum, CAVE, Gewicht, BMI, Plan, Termin und den Knöpfen;
    waagerechte Reiter mit „Karteikarte“ vorn; rechts (ab 1440 px) eine feste Spalte mit allen Gruppen. Eine frisch
    geöffnete Akte beginnt mit der Karteikarte (F136), „Übersicht“ bleibt als Reiter erreichbar.
- **Übersicht neben Leiste oder Spalte:** Das Raster der Karten richtet sich dort nach der tatsächlichen Breite statt
  nach der Fensterbreite (sonst wären bei 1920 px vier Spalten auf rund 1 000 px gedrängt). In der Kopfzeile unverändert.
- **Endpunkt:** `PATCH /api/auth/ich/ {darstellung}` – drei neue Werte in `DarstellungSerializer`: `aktenansicht`
  (`kopfzeile` | `seitenleiste` | `karteikarte`, Standard `kopfzeile`), `aktenkopf` (`minimal` | `kompakt` | `voll`,
  Standard `voll`), `aktenleiste_breite` (240–480, Standard 300). Ältere gespeicherte Darstellungen ohne diese Werte
  gelten als Standard; „Auf Standard zurücksetzen“ setzt sie mit zurück. Keine Migration (Feld `User.darstellung` ist JSON).
- **Dateien:** `seiten/akte/ansicht.tsx` (Hook `useDarstellung`, Griffe), `seiten/akte/Akte.tsx` (drei Aufbauten aus
  denselben Bausteinen), `seiten/Konto.tsx`, `seiten/akte/Uebersicht.tsx`, `index.css`.
- **Teststatus:** Backend-Test `accounts.tests.MeinKonto.test_aktenansicht` (speichern, Standard, ungültige Werte).
  Browsertest `aktenansicht.spec.ts` (Kopfzeile: Gruppen, Stufen per Tastatur und Ziehen, nach Neuladen erhalten;
  Seitenleiste: Knöpfe über dem Namen, senkrechte Reiter, Breite per Tastatur und Ziehen mit Einrasten, nach Neuladen
  erhalten, unter 1280 px ohne Griff; Karteikarte; zurücksetzen). Die bestehenden Tests der Akte laufen mit der
  Kopfzeile (Kennzahlen, Auskunft, Nickelallergie „nicht erfasst“, Kopfhöhe mit Bezugspersonen gleich).
- **Status:** ABGESCHLOSSEN – Tests geschrieben, noch nicht gelaufen: GitHub Actions startete am 08.10.2026 keine Jobs (Abrechnung des Kontos), die Arbeitsumgebung hatte keinen Zugriff auf PyPI, npm und Docker Hub. Geprüft: Syntax und Typen der eigenen Dateien (TypeScript mit Platzhaltern für die Bibliotheken)

### F136 Karteikarte mit Kürzelzeile
- **Ansicht:** Akte › Reiter „Karteikarte“ (`/patienten/{id}/kartei`, in jeder Ansicht aufrufbar, als Reiter nur in der
  Ansicht „Karteikarte“). Alle Einträge chronologisch, neueste zuerst, nach Monaten getrennt: Kürzel K Kontakt, G Gewicht,
  T Termin bzw. WV Wiedervorlage/Rückruf, P Infusionsplan, L Laborbefund, BIA BIA-Messung, D Diagnose (ICD), DOK
  Dokument, B Bericht – mit Datum (Kontakte mit Uhrzeit), Text, Zusatz (storniert, erledigt, freigegeben, beendet) und
  Person. Stornierte Kontakte und beendete Diagnosen durchgestrichen. Filter je Art mit Anzahl, Zeitraum 12 Monate /
  3 Jahre / alle. Ein Klick auf einen Eintrag öffnet den passenden Reiter.
- **Kürzelzeile** (nur mit Recht „Einträge erfassen“): „K Text“ öffnet „Neuer Kontakt“ mit dem Text, „G 61,2“ die
  Gewichtserfassung mit dem Wert, „T“/„WV“ den Termin, „P“ einen neuen Plan (mit Recht). Gespeichert wird erst im
  Formular – Kontakte bleiben nach dem Speichern unveränderlich. Unbekannte Kürzel melden sich.
- **Endpunkte:** keine neuen; gelesen werden `kontakte/`, `gewichte/`, `termine/`, `infusionsplaene/`, `dokumente/`
  (ohne ausgeblendete), `laborbefunde/`, `bia-messungen/`, `diagnosen/`, `berichte/` je `?patient=`. Fehlt ein Bereich
  (z. B. ohne Recht), steht ein Hinweis darunter, der Rest bleibt sichtbar.
- **Teststatus:** Browsertest `aktenansicht.spec.ts` (Einträge K und G, Filter, Übersicht erreichbar, „K Text“ → Kontakt
  gespeichert und in der Karteikarte, „G 61,2“ → Wert vorbelegt, unbekanntes Kürzel).
- **Status:** ABGESCHLOSSEN – Tests geschrieben, noch nicht gelaufen: GitHub Actions startete am 08.10.2026 keine Jobs (Abrechnung des Kontos), die Arbeitsumgebung hatte keinen Zugriff auf PyPI, npm und Docker Hub. Geprüft: Syntax und Typen der eigenen Dateien (TypeScript mit Platzhaltern für die Bibliotheken)

### F137 Ladebalken dicker und passend zum Farbschema
- **Wunsch 08.10.2026:** „Den Ladebalken ein wenig dicker … Ist es farbresponsiv mit dem Design?“ – Vorher 3 px; Farbe je
  Schema (Standard Orange #e8730c, Dunkel #ffa64d, Hoher Kontrast #c25400), in „Individuell“ aber immer Orange.
- **Jetzt:** 5 px; in „Individuell“ folgt `--ladebalken` der gewählten Akzentfarbe (`individuelleFarben`), die übrigen
  Schemata behalten ihre abgestimmte Farbe.
- **Status:** ABGESCHLOSSEN – Lauf steht aus (siehe F135)

### F138 Fortschritt laufender Aufträge mit ungefährer Zeit
- **Wunsch 08.10.2026:** „Fortschrittsbalken mit ungefährer Zeitangabe in gleicher Farbe wie der Ladebalken beim Backup
  oder Update.“
- **Ansicht:** Administration › Backup und › System: oben die Karte „Laufende Tätigkeiten“ (nur wenn etwas läuft oder
  wartet), dazu in der Tabelle unter dem Status. Balken in `--ladebalken`, Text „42 % · noch ca. 3 Min. (üblich
  ca. 6 Min.)“; wartet ein Auftrag mit verzögertem Beginn: „beginnt in ca. 12 Min.“.
- **Logik (`components/AuftragFortschritt.tsx`):** Der Systemagent meldet keinen Prozentstand. Geschätzt wird aus dem
  Median der letzten fünf erledigten Aufträge derselben Aktion (Beginn → Ende), ohne solche aus Erfahrungswerten
  (z. B. Sicherung 3 Min., EPM aktualisieren 15 Min., „geschätzt“ im Text). Höchstens 95 %, bis der Auftrag fertig
  ist; dauert er länger als üblich, sagt der Text das und der Balken läuft als Bewegung weiter. Keine neuen Endpunkte.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F139 Form „Rund“ oder „Eckig“
- **Wunsch 08.10.2026:** „Das runde Design mit dem verschwendeten Platz bitte mit einem eckigen Design ausstatten und die
  Abstände weglassen … Runde und eckige Design sollen im Menü Mein Konto einstellbar sein.“
- **Ansicht:** Mein Konto › Darstellung › „Form“: Rund (Standard) | Eckig. Eckig: keine Rundungen (Karten, Knöpfe,
  Felder, Chips, Reiter, Balken; Kreise wie Kürzel und Farbfelder bleiben rund), kein Schatten, kein Rand um den
  Seiteninhalt und keine Abstände zwischen den Karten (Startseite, Übersicht der Akte, Spalten, Konto, Backup, System,
  Aktenansichten); die Linien benachbarter Karten liegen übereinander. Innerhalb der Karten bleiben die Abstände.
- **Endpunkt:** `PATCH /api/auth/ich/ {darstellung: {form: "rund" | "eckig"}}` (Standard „rund“, ohne Migration).
- **Teststatus:** Backend-Test `MeinKonto.test_form`; Browsertest `konto.spec.ts` „Form „Eckig“ …“.
- **Status:** ENTFERNT am 08.10.2026 („Das eckige Design kann wieder raus, als auch der Menüpunkt dazu.“). Ein noch gespeichertes `form` wird im Backend still verworfen und in der Oberfläche nicht mehr angewendet. Ersetzt durch F145.

### F140 Benutzermenü unten links
- **Wunsch 08.10.2026:** „Unten links nur [die Person] anzeigen lassen. Beim Klick darauf dann die Menüpunkte.“
- **Ansicht:** Seitenleiste unten: Kürzel, Name, Rolle als ein Knopf; Klick öffnet nach oben Hilfe, Mein Konto,
  Abmelden. Am Telefon (Schublade) bleiben die drei Einträge offen sichtbar. Die übrigen Menüpunkte sind unverändert.
- **Teststatus:** `konto.spec.ts` (Menü öffnen, Mein Konto); `anmeldung.spec.ts` und `passkey.spec.ts` melden sich über das
  Menü ab.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F141 Patientenliste ohne Vorschau
- **Wunsch 08.10.2026:** „Patienten ohne Vorschau der Akte. Man muss auf die Akte klicken, um sie zu sehen.“
- **Ansicht:** Die Vorschau rechts neben der Liste (ab 2560 px, F14/F97) und der Knopf „Vorschau“ entfallen, ebenso der
  Teiler der Patientenliste. Ein Klick auf die Zeile (auch bei abgeschlossenen Akten) öffnet die Akte; Links und
  Knöpfe in der Zeile behalten ihre Wirkung. Die übrigen Spalten je Fensterstufe bleiben.
- **Teststatus:** `oberflaeche.spec.ts` „Volle Breite in Stufen: 2560 px ohne Vorschau …“ (kein Teiler, keine Vorschau,
  Klick auf die Zeile öffnet die Akte).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F142 Kalender: Einträge mit „×“ ausblenden
- **Wunsch 08.10.2026:** „Kalender → Termine alle mit einem ×. Dann wie beim Patienten Abfrage bzgl. Ausblenden des
  Hinweises.“ Rückfrage geklärt: auch echte Termine werden wie Hinweise ausgeblendet (nicht abgehakt).
- **Ansicht:** Jeder Eintrag im Kalender (Monat, Woche, Liste, Tagesliste, Überfällig) hat rechts ein **×**. Es öffnet
  den Dialog der Hinweise (F119): 3, 6 oder 12 Monate oder „nicht mehr nötig“, dazu ein Grund.
  - **Fälligkeiten** („Kontakt bald fällig/überfällig“, „Plan prüfen“): schaltet den Hinweis der Akte stumm (F119,
    Arten `kontakt` bzw. `plan`) – die Fälligkeit verschwindet aus dem Kalender, ebenso der Hinweis in Liste und Akte.
    Recht „Akten bearbeiten“.
  - **Termine** (Praxistermin, Rückruf, Wiedervorlage, Sonstiges): der Termin verschwindet aus Kalender, Startseite,
    „Nächster Termin“ der Akte und der Patientenliste und aus der Terminkarte der Übersicht. Recht „Einträge erfassen“,
    nicht bei erledigten Terminen.
  - In der Akte stehen ausgeblendete Termine unter **„Ausgeblendete Hinweise“** mit Frist, Grund, Person und Zeitpunkt –
    „Wieder einschalten“. In der Karteikarte (F136) bleibt der Termin mit dem Zusatz „ausgeblendet“ sichtbar.
- **Endpunkt:** `POST /api/termine/<id>/ausblenden/` `{"monate": 3|6|12, "grund"}` · `{"dauerhaft": true, "grund"}` ·
  `{"aufheben": true}`; Filter `GET /api/termine/?ausgeblendet=true|false`. Termin-Antwort zusätzlich `ausgeblendet`,
  `ausgeblendet_bis`, `ausgeblendet_dauerhaft`, `ausblende_grund`, `ausgeblendet_am`, `ausgeblendet_von_name`.
  Der Kalender (`GET /api/kalender/`) lässt ausgeblendete Termine und stummgeschaltete Fälligkeiten weg.
- **Tabellen:** `patienten_termin` + Historie (Migration `patienten/0012_termin_ausblenden`, von Hand geschrieben);
  jede Fassung steht im Verlauf der Akte (Bereich „Termine“).
- **Teststatus:** Backend-Tests `test_kalender.Kalender.test_termin_ausblenden`, `test_faelligkeit_folgt_der_hinweisruhe`;
  Browsertest `kalender.spec.ts` „Termin mit „×“ ausblenden …“.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F143 Griffe ohne Punkte
- **Wunsch 08.10.2026:** „Kann man das [Punkte-Griff] überall entfernen? Die [Linie] soll sich beim Hovern so verändern,
  dass man sieht, dass man die Größe ändern kann.“
- **Ansicht:** Spaltenteiler (Patientenakte, Plan-Editor, Kontakte …), Rand der Seitenleiste der Akte und Griff unter
  dem Aktenkopf ohne Punkte. Beim Überfahren oder mit Tastaturfokus wird die Linie 4 px breit in der Akzentfarbe, der
  Mauszeiger zeigt „Größe ändern“; beim Ziehen erscheint weiter der Hinweis zum Einrasten.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F144 Rückmeldungen als Overlay
- **Wunsch 08.10.2026:** „Beim Speichern hatte ich beim ursprünglichen EPM ein grünes Overlay, das sich nach ein paar
  Sekunden ausgeblendet hat … Auch kurze rote Fehler wurden so angezeigt, blieben aber länger stehen.“
- **Ansicht (`components/ui/hinweise.tsx`):** statt der kleinen Meldung unten rechts ein Overlay oben in der Mitte
  (unter der Kopfzeile, am Telefon unter der Titelleiste), kräftig grün mit Haken bzw. rot mit Warnzeichen, weicher
  Ein- und Ausblendeffekt. Grün steht ca. 3 s, rot ca. 9 s; „×“ schließt sofort. Gleiche Meldungen kurz hintereinander
  erscheinen nur einmal, höchstens vier gleichzeitig. Das Overlay fängt keine Klicks ab (nur das „×“). Farben je Schema
  (`--ok`/`--auf-ok`, `--fehler`/`--auf-fehler`), bei „Hoher Kontrast“ mit Rahmen. Alle bisherigen Meldungen (über 90
  Stellen) nutzen es ohne Änderung.
- **Teststatus:** `oberflaeche.spec.ts` „Rückmeldung als Overlay …“.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F145 Weniger Leerraum
- **Wunsch 08.10.2026:** „Verkleinere jedoch das Padding, damit nicht so viel Platz verschwendet wird.“
- **Ansicht (für alle, ohne Einstellung):** Rand des Seiteninhalts 16 px statt 32 px (seitlich) und 12/16 px statt
  16/28 px (oben/unten), am Telefon 8 px; Kopfzeile seitlich 16 px. Abstand zwischen Karten und Bereichen einheitlich
  12 px (`--abstand`) statt 16–20 px – Startseite, Übersicht der Akte, Spalten, Konto, Backup, System, Aktenansichten.
  Spaltenteiler 12 px statt 20 px breit. Innerhalb der Karten bleibt alles, wie es ist.
  Ansicht „Seitenleiste“ der Akte wie im Entwurf: Leiste mit den Angaben (weiß) und senkrechte Reiter (grau, mit
  Trennlinie) bündig an der Navigation über die volle Höhe, ohne Kartenrahmen; die Angaben bleiben beim Scrollen oben
  stehen. Nur der Inhalt rechts hat Rand (18/20 px) und runde Karten. Unter 1280 px untereinander, ebenfalls bündig.
- **Teststatus:** `konto.spec.ts` „Benutzermenü unten links; weniger Rand …“ (16 px, keine Wahl „Form“ mehr); Backend-Test
  `MeinKonto.test_form_wird_ignoriert`.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F146 Einheitlich und kompakt, Suche bei Versorger
- **Wunsch 08.10.2026:** „Alle Menüpunkte und Untermenüs verschwenden extrem viel Platz. Ich brauche den Platz, es muss
  aber lesbar und übersichtlich sein. Bei Versorger gibt es keine Suchfunktion. … Buttons bei Infusionsplänen,
  Versorger und Ärzte von der Größe anpassen … wenn man zwischen den Menüs schaltet, springt alles.“
- **Kein Springen:** Platz für den Scrollbalken ist immer reserviert (`scrollbar-gutter: stable`) – Seiten mit und ohne
  Scrollbalken stehen an derselben Stelle. Der Seitenkopf (`Seitenkopf`) ist auf allen 14 Seiten einzeilig: Titel 20 px,
  Unterzeile daneben gekürzt (ganz im Tooltip), rechts die Knöpfe – überall gleich hoch.
- **Gleiche Steuerhöhe:** Umschalter (Aktiv/Inaktiv/Alle, Ansichten) sind jetzt genau so hoch wie Knöpfe und Felder
  (vorher 2 px höher). Dichte „Normal“ 32 px statt 36 px (Großzügig 36, Kompakt 30, Sehr kompakt 26); Tabellenköpfe
  in Steuerhöhe.
- **Weniger Leerraum:** Innenabstand der Karten einheitlich 16 px seitlich und 12 px oben/unten (vorher 18–22 px),
  am Telefon 12 px seitlich; Abstände zwischen Karten auf allen Seiten 12 px (30 weitere Bereiche umgestellt).
- **Versorger:** Suchfeld „Versorger filtern“ über der Liste wie bei den Ärzten – Firma, Ort, PLZ, Straße, Telefon,
  E-Mail und Ansprechpartner (Name, Telefon, Mobil, Zuständigkeit), mehrere Wörter = alle müssen passen.
- **Teststatus:** `versorger.spec.ts` „Versorger suchen …“.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F147 Ohne Scrollen auf 1080p
- **Wunsch 08.10.2026:** „Man muss teilweise scrollen, um alles sehen zu können … auf einem 1080p-Monitor nicht müsste.“
  „Bitte überall verdichten. Bei Kalender muss ich auch scrollen.“ „Die Ausrichtung bzw. Größe des Menüs ist komisch.“
- **Versorger und Ärzte:** Detailformular im 6-Spalten-Raster – Firma/Name über die ganze Breite; Praxis | Fachrichtung;
  Straße | PLZ | Ort in einer Zeile; Telefon | Fax | E-Mail in einer Zeile; Notiz zweizeilig. Felder allgemein enger
  (Beschriftung 3 px über dem Feld statt 6 px, Zeilenabstand 8 px). Hinweistexte unten in einer kleinen Zeile statt drei
  Absätzen; der Namenshinweis „mit Titel …“ steht als Platzhalter im Feld. Ansprechpartner-Zeilen enger; „Patienten in
  Betreuung“ beim Arzt zweispaltig, ab 12 Zeilen scrollt nur die Liste. Am Telefon einspaltig.
- **Kalender:** Die sechs Wochen des Monats füllen genau die Fensterhöhe (mindestens 84 px je Tag), Woche und Liste enger.
- **Benutzermenü unten links:** so breit wie der Knopf und bündig darüber, Einträge wie im Hauptmenü (gleiche Höhe,
  Symbole, Schrift).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F148 Navigation gleichmäßig und schmaler
- **Wunsch 08.10.2026:** „Warum sind nicht alle Menüpunkte gleich groß? Kann die Seitenmenüleiste auch schmaler werden?
  Warum ist das Menü nicht mittig, wenn klein?“
- **Ansicht:** Zwischen 768 und 1440 px (nur Symbole) ist jeder Eintrag 40 × 36 px groß und das Symbol mittig – vorher
  saß es links und der markierte Eintrag war breiter als das Symbol; der Benutzerknopf unten ist dort ebenfalls mittig.
  Ab 1440 px ist die Leiste mit Text 224 statt 256 px breit (Logo passt sich an). Der Hauptknopf im Seitenkopf („Neuer
  Versorger“, „Neuer Arzt“, „Neuer Plan“ …) ist überall mindestens 160 px breit. Leere Bereiche („Keine …“) mit
  12 statt 24 px Abstand.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F149 Kontakt und Gewicht als Dialog in der Akte
- **Wunsch 08.10.2026:** „Warum kann im Patienten selbst Kontakt und Gewicht als Button nicht ähnlich sein wie die
  Erfassung von Terminen? Fühlt sich intuitiver an.“
- **Ansicht:** Die Knöpfe „Kontakt“ und „Gewicht“ im Aktenkopf (alle drei Aktenansichten) öffnen jetzt dieselben
  Dialoge wie die Schnellerfassung der Startseite – mit diesem Patienten vorgegeben: „Kontakt erfassen“ (Text, Art,
  auf Wunsch mit Gewicht und Wiedervorlage, Kasten „Aus der Akte“) und „Gewicht erfassen“ (Wert, Quelle, Datum, Vergleich).
  Vorher sprang „Kontakt“ in den Reiter Kontakte und „Gewicht“ zur Gewichtskarte der Übersicht. Die Seite bleibt jetzt,
  wo sie ist; nach dem Speichern sind Kopf, Listen und Startseite aktuell. Die Kürzelzeile der Karteikarte (F136) bleibt
  wie sie ist. Ebenso öffnet „+ Kontakt“ auf der Karte „Letzte Kontakte“ der Übersicht diesen Dialog – vorher sprang der
  Link in den Reiter Kontakte, ohne den Dialog zu öffnen (Fehler seit F122).
- **Teststatus:** `akte.spec.ts` (Dialoge öffnen mit vorgegebenem Patienten).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F150 Ein Dialog je Sache, Wiedervorlage einstellbar
- **Wunsch 08.10.2026:** Umsetzung des Dokuments „EPM intuitiver – Vorschläge“ (Abschnitt „Erfassen“): jede Sache wird
  überall mit demselben Dialog erfasst. Dazu: „Standard 14 Tagen jedoch anpassbar“ (Vorgabe der Wiedervorlage).
- **Ansicht:** „Neuer Kontakt“ im Reiter Kontakte, „+ Kontakt“ der Übersicht und „K Text“ der Kürzelzeile öffnen den
  Dialog „Kontakt erfassen“ (Text aus der Kürzelzeile vorbelegt, die Karteikarte bleibt stehen). Der bisherige eigene
  Dialog „Neuer Kontakt“ entfällt; seine Möglichkeiten (Kontaktart, Rückruf/Wiedervorlage/Praxistermin mit Ort,
  Sonstiges, Uhrzeit) hat der gemeinsame Dialog. Die Gewichtskarte hat kein eigenes Formular mehr: „+ Gewicht“ und
  „G 61,2“ öffnen „Gewicht erfassen“ (Wert vorbelegt). Die letzte Messung lässt sich direkt korrigieren – Klick auf
  den Wert oder „Korrigieren“ im Kartenkopf; ältere Messungen weiterhin über „Messwerte anzeigen“. Die Karte „Termine“
  steht nicht mehr zusätzlich im Reiter Kontakte (Übersicht und Kalender zeigen sie).
- **Wiedervorlage:** „Wiedervorlage anlegen“ im Kontakt-Dialog schlägt standardmäßig „in 14 Tagen“ vor (vorher je nach
  Stelle 7 oder 14 Tage). Der Wert ist unter Vorlagen › Grenzwerte › „Wiedervorlage nach Kontakt in … Tagen“ einstellbar
  (1–365, neues Feld `Einstellungen.wiedervorlage_tage`, Migration `stammdaten/0015`); im Dialog bleibt das Datum je
  Kontakt frei änderbar, die Schnellwahl zeigt den eingestellten Wert.
- **Teststatus:** `patienten/test_startseite.py` (Standard 14, Grenzen, Speichern), `akte.spec.ts`, `aktenansicht.spec.ts`,
  `admin.spec.ts`, `zz-neustart.spec.ts` angepasst.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F151 Weniger Wege beim Erfassen
- **Wunsch 08.10.2026:** Umsetzung „EPM intuitiver – Vorschläge“ (Abschnitte „Erfassen“ und „Weniger Wege“).
- **Entwurf fortsetzen:** Gibt es einen Entwurf eines Infusionsplans, zeigt der Aktenkopf „Entwurf fortsetzen“ (öffnet
  den Entwurf zum Bearbeiten) statt „Neuer Plan“. Dazu liefert der Aktenkopf `kopf.plan_entwurf` (`id`, `erstellt_am`).
- **Dokumente:** „Weitere Aktionen › Dokument hochladen …“ und Dateien irgendwo auf die geöffnete Akte ziehen
  (ganzflächiger Hinweis „Datei loslassen …“). Die Seite bleibt, wo sie ist; jede Datei wird grün bzw. rot quittiert.
  Im Reiter Dokumente bleibt dessen eigene Ablage mit Fortschrittsliste zuständig (keine doppelten Uploads).
- **Arzt/Versorger anlegen:** „Neu anlegen“ bei Versorger und Hausarzt in „Neuer Patient“ sowie „Neuen Arzt anlegen“ in
  „Arzt zuordnen“ öffnen einen Dialog (Name, Anschrift, Telefon, Fax, E-Mail; beim Arzt Praxis und Fachrichtung). Nach
  „Anlegen“ ist der neue Eintrag gleich ausgewählt; das Formular bleibt mit allen Eingaben stehen. Vorher führte der
  Link auf die Seite Versorger bzw. Ärzte und die Eingaben gingen verloren.
- **Teststatus:** `infusionen/tests.py` (`plan_entwurf`), `plaene.spec.ts`, `dokumente.spec.ts`, `patienten.spec.ts`.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F152 Bearbeiten sichtbar
- **Wunsch 08.10.2026:** Umsetzung „EPM intuitiver – Vorschläge“ (Abschnitt „Bearbeiten sichtbar“): Was sich ändern
  lässt, zeigt das dort, wo es steht.
- **Anschrift und Kontakt:** Karte der Übersicht mit „Bearbeiten“ (öffnet „Stammdaten bearbeiten“, bisher nur über
  „Weitere Aktionen“ oder „nicht erfasst“).
- **Gewicht:** letzte Messung direkt korrigieren (siehe F150).
- **Kalender:** Klick auf einen offenen Termin, den die Person ändern darf, öffnet gleich „Termin ändern“ – mit
  „Erledigt“, „Akte öffnen“ und „Angelegt … von …“. Erledigte Termine, Fälligkeiten und Personen ohne Recht sehen wie
  bisher die Ansicht des Eintrags.
- **Karteikarte:** Klick auf eine Zeile öffnet genau diesen Eintrag im Reiter (Kontakt, Plan, Labor, BIA, Diagnose,
  Dokument, Bericht; per `?kontakt=`, `?plan=`, `?befund=`, `?messung=`, `?eintrag=`, `?dokument=`, `?bericht=`), eine
  beendete Diagnose samt „beendete anzeigen“. Offene Termine öffnen „Termin ändern“, ohne die Karteikarte zu verlassen.
- **Therapie und Empfehlung:** erst lesen, „Bearbeiten“ öffnet den Editor (vorher war er immer offen); ein leerer Text
  öffnet ihn gleich. Im Editor heißt „Verwerfen“ jetzt „Abbrechen“ (eine Sprache, F153).
- **Kartengröße:** Das Menü für Breite und Höhe der Karten (Übersicht, System) öffnet sich über ein Größen-Symbol statt
  „⋯“ – „⋯“ ließ weitere Aktionen erwarten. Dezent, bis die Maus über der Karte ist.
- **Teststatus:** `akte.spec.ts`, `kalender.spec.ts`, `aktenansicht.spec.ts`.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F153 Eine Sprache in Knöpfen und Rückfragen
- **Wunsch 08.10.2026:** Umsetzung „EPM intuitiver – Vorschläge“ (Abschnitt „Eine Sprache“).
- **Wörter:** „Ändern“ und „Korrigieren“ heißen „Bearbeiten“ (Labor, BIA, Diagnose, Kalender, Gewichtsmessung; Dialoge
  „Termin bearbeiten“, „Messung bearbeiten“). Der Knopf zum Sichern heißt in Dialogen „Speichern“ statt „Termin
  speichern“, „Gewicht speichern“, „Zuordnen“, „Erfassen“ oder „n Werte speichern“ (Labor zeigt die Zahl in Klammern).
  Ausnahmen mit Folge bleiben: „Freigeben“, „Entwurf speichern“, „Als Entwurf speichern“. Anlegen bleibt „Neuer/Neue X“
  bzw. „+ X“ („Neuer Termin“ statt „Termin anlegen“). „Erledigen“ (Datenschutz-Anfragen) heißt „Erledigt“ mit Haken;
  die Kästchen auf Startseite und Übersicht zeigen „Erledigt“ beim Überfahren. Bezugspersonen und Arzt-Zuordnungen:
  „Deaktivieren“ / „Wieder aktivieren“ statt „Nicht mehr aktuell/zuständig“ bzw. „Wieder aktuell/zuständig“.
  Diagnosen behalten „Beenden“ (fachlich richtig). Im Editor von Texten heißt „Verwerfen“ jetzt „Abbrechen“.
- **Rückfragen:** Einheitlicher Dialog (`components/Bestaetigen.tsx`) vor „Bericht verwerfen“ (löschte bisher sofort),
  „Diagnose beenden“, „Bezugsperson deaktivieren“, „Arzt deaktivieren“ (Versorger/Ärzte siehe F156).
- **Anordnung:** In allen Dialogen steht ein roter Knopf (löschen, verwerfen, deaktivieren, endgültig …) links, getrennt
  von „Abbrechen“ und „Speichern“/„Freigeben“ rechts (`.dialog-fuss .btn.dng`).
- **Teststatus:** `akte.spec.ts`, `kalender.spec.ts`, `start.spec.ts`, `datenschutz.spec.ts`, `dokumente-falsch.spec.ts`,
  `oberflaeche.spec.ts`, `praxiswuensche.spec.ts` (Diagnose beenden, Bericht verwerfen mit Rückfrage, roter Knopf links).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F154 Ein Suchfeld, Prüffilter wählbar, Erklärtexte in der Hilfe
- **Wunsch 08.10.2026:** Umsetzung „EPM intuitiver – Vorschläge“ (Abschnitte „Weniger Wege“ und „Weniger Erklärtext“).
- **Ein Suchfeld:** Auf der Patientenliste filtert das Suchfeld oben in der Kopfzeile direkt die Liste (`?suche=`,
  verzögert übernommen; Beschriftung „Liste filtern“); das zweite Feld „Liste filtern“ über der Liste entfällt. Der
  Begriff steht als Chip bei den Filtern (mit „×“), „Filter zurücksetzen“ leert auch das Feld oben. Auf allen anderen
  Seiten schlägt das Feld wie bisher Patienten zum Öffnen vor.
- **Prüfen …:** Die zwölf Prüffilter (Kontakt fällig, Nickelallergie offen, Erklärungen fehlen …) sind in der
  Patientenliste direkt wählbar; vorher nur über Links von Startseite und Datenschutz.
- **Erklärtexte:** Lange Unterzeilen und Fußtexte (Kalender, Versorger, Ärzte, Datenschutz, Mein Konto, abgeschlossene
  Akten, Reiter Diagnosen, Labor, BIA, Therapie, Empfehlung) stehen jetzt in der Hilfe zur jeweiligen Seite („?“ oben
  rechts). Auf der Seite bleibt nur ein Satz, wo eine Handlung Folgen hat (Kontakte: „werden nicht geändert, sondern
  storniert“; Berichte: „Freigegebene Berichte sind unveränderlich“). Neue Hilfe-Abschnitte „Labor und BIA“, „Berichte“,
  „Tastenkürzel in der Akte“; überarbeitet: Patientenliste, Neuer Patient, Aktenkopf, Karten vergrößern,
  Stammdaten/Diagnose/Therapie, Kontakt erfassen, Termine, Kalender, Gewicht.
- **Leere Reiter:** Ohne Einträge zeigt der Detailbereich keinen Hinweis „Links … wählen“ mehr; die Liste sagt, was
  fehlt, der Hauptknopf („Neuer …“) steht direkt darüber. Leere Patientenliste mit „Neuer Patient“.
- **Fußzeile der Patientenliste:** „Klick auf die Zeile öffnet die Akte“ (vorher „auf den Namen“).
- **Teststatus:** `patienten.spec.ts` (Suche über die Kopfzeile, Chip, Prüfen-Auswahl).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F155 Tastenkürzel in der Akte
- **Wunsch 08.10.2026:** Umsetzung „EPM intuitiver – Vorschläge“ (Abschnitt „Schneller mit der Tastatur“).
- **In einer geöffneten Akte** (nicht in Eingabefeldern, nicht bei offenem Dialog oder Menü): **K** Kontakt erfassen,
  **G** Gewicht erfassen, **T** Neuer Termin, **P** Neuer Plan bzw. Entwurf fortsetzen (je nur mit Recht),
  **Alt+1 … Alt+9, Alt+0** die ersten zehn Reiter in ihrer Reihenfolge, **?** Übersicht der Kürzel (Dialog).
- **In jedem Dialog:** **Strg Enter** (Mac ⌘ Enter) löst den Hauptknopf unten rechts aus (Speichern, Freigeben …),
  sofern er nicht gesperrt ist; **Esc** schließt wie bisher.
- **Lernen nebenbei:** Die Knöpfe im Aktenkopf und die Reiter zeigen ihr Kürzel beim Überfahren (z. B. „Kontakt
  erfassen (K)“, „Kontakte (Alt+5)“). Hilfe-Abschnitt „Tastenkürzel in der Akte“.
- **Teststatus:** `akte.spec.ts` (K, G mit Strg Enter, T ohne Wirkung im Eingabefeld, Alt+Ziffer, ?, P ohne Recht).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F156 Versorger, Ärzte und Kalender nach den Entwürfen
- **Wunsch 08.10.2026:** „Kann man Versorger und Ärzte nicht besser lösen? … Kann man Kalender nicht besser lösen vom
  Aufbau?“ – umgesetzt nach den Entwürfen für PC (1920 × 1080), Tablet (1024 × 768) und Telefon (390 × 844).
- **Versorger und Ärzte** (gemeinsamer Aufbau `components/StammListe.tsx`): links eine schmale Liste (300 px, ab 1280 px
  340 px) mit Suche, „Aktiv n | Inaktiv n | Alle“, je Eintrag Name, Ort/Fachrichtung, Zahl der Ansprechpartner und
  rechts die Patientenzahl; sie scrollt in sich. Rechts der gewählte Eintrag zum **Lesen**: Kopf mit Name, Status,
  „n Patienten · anzeigen“ (Versorger: Patientenliste gefiltert), **Bearbeiten** und Menü „⋯“ (Deaktivieren mit Rückfrage
  bzw. Wieder aktivieren); darunter Anschrift, Erreichbarkeit und Notiz nebeneinander, Ansprechpartner als Tabelle
  (Name, Zuständigkeit, Telefon, Patienten mit Link), Patienten in Betreuung drei-/zwei-/einspaltig (erst zwölf, dann
  „… n weitere“; Versorger sortierbar nach Name oder Ansprechpartner; Nickel-Hinweis). „Bearbeiten“ und „Neuer …“
  öffnen das Formular an derselben Stelle (Abbrechen/Speichern). Telefon: erst die Liste, ein Eintrag öffnet sich ganz,
  „‹ Liste“ führt zurück (Zurück im Browser ebenso).
- **Kalender:** eine Werkzeugzeile (Titel, ‹ Heute ›, Monat, Monat/Woche/Liste, **Anzeigen ▾**, + Termin). „Anzeigen“
  fasst die sechs Arten und „Erledigte zeigen“ mit der Farblegende in einem Menü zusammen. Der Monat füllt die
  Fensterhöhe; rechts (ab 1280 px) eine Spalte mit den Reitern **Tag** (gewählter Tag, nächste 7 Tage, „+ Termin am …“),
  **Überfällig n** (offene Termine, Kontakt überfällig, Plan prüfen) und **Fällig n** (Kontakt bald fällig). Tablet:
  kompakter Monat, die Reiter darunter. Telefon: Wochenband (7 Tage mit Punkt bei Einträgen), Reiter Tag | Überfällig |
  Woche, ‹ › blättern wochenweise.
- **Hilfe:** Abschnitte Versorger, Ärzte und Kalender beschreiben den neuen Aufbau.
- **Teststatus:** `versorger.spec.ts` (Lesen/Bearbeiten, Deaktivieren über „⋯“ mit Rückfrage, Telefon Liste ↔ Eintrag),
  `akte.spec.ts` (Ärzte), `kalender.spec.ts` (Reiter, Anzeigen ▾, eine Zeile, 1080p ohne Scrollen, Telefon),
  `oberflaeche.spec.ts`.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F157 Restliche Vorschläge „Bearbeiten sichtbar“ und „Erfassen“
- **Versorgung im Aktenkopf:** Die Gruppe „Versorgung“ (Versorger, Ansprechpartner, Hausarzt) hat einen Stift, der
  „Stammdaten bearbeiten“ öffnet (nur mit Recht; „Weitere Aktionen“ behält den Eintrag).
- **Gewichtsdiagramm:** Ein Klick (oder Enter) auf einen Messpunkt öffnet „Messung bearbeiten“ für genau diese Messung.
- **Reiter Dokumente:** Hauptknopf **Neues Dokument** (vorher „Auswählen“) an derselben Stelle wie bei den anderen
  Reitern; die Ablage nennt, dass Dateien auch irgendwo auf die Akte gezogen werden können (F151).
- **Teststatus:** `akte.spec.ts` (Stift an „Versorgung“, Klick auf Messpunkt).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F158 Design und Mein Konto als getrennte Menüpunkte
- **Wunsch 09.10.2026:** „Bitte Design und Mein Konto voneinander trennen und als separate Menüpunkte anbieten.“
- **Menü:** Das Benutzermenü unten links (und die Schublade am Telefon) bietet jetzt Hilfe, **Design**, Mein Konto und
  Abmelden. Neues Symbol „Palette“.
- **Design** (`/design`): Farbschema, Akzent, Hintergrund, Dichte, Schrift, Aufbau der Patientenakte, „Auf Standard
  zurücksetzen“ und „Startseite anpassen“ – unverändert gespeichert je Person (`darstellung`).
- **Mein Konto** (`/konto`): Profil, Anmeldung und Sicherheit (Kennwort, Zwei-Faktor, Passkeys, Notfall-Codes) und
  angemeldete Geräte. Links wie „/konto#zwei-faktor“ funktionieren wie bisher.
- **Hilfe:** neuer Abschnitt „Design“ (zum „?“ auf /design), „Mein Konto“ angepasst.
- **Teststatus:** `konto.spec.ts` (Menü mit Design, getrennte Seiten), `aktenansicht.spec.ts`, `zz-neustart.spec.ts`,
  `bildschirmfotos-mobil.spec.ts` auf /design umgestellt.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F159 Import: Regeln je Wert, Mehrfachauswahl, Gewichte zusammenfassen
- **Wunsch 09.10.2026** (nach dem ersten Probelauf mit dem echten Dump: 200 Auffälligkeiten, davon rund 150 „Gewicht 1 kg“):
  „Kann ich eine Mehrfachauswahl haben, um bestimmte Werte, z. B. Gewicht 1 kg, nicht übernehmen zu können? Sonst muss ich
  200 Werte händisch anhaken. Vielleicht auch zusammenfassen, wenn die Meldungen gleich sind.“ Und: „Beim Import muss
  geprüft werden, ob bei einem Patienten mehrere Gewichtsanpassungen innerhalb von 1–2 Tagen durchgeführt worden sind.
  Hierbei soll die genommen werden, die als letztes angepasst worden ist. Somit vermeiden wir Dopplungen.“
- **Ansicht:** Auffälligkeiten „Gruppiert“ (Standard) oder „Einzeln mit Auswahl“. Eine Gruppe = gleiche Tabelle, gleiches
  Feld, gleicher Wert im Dump (Anzahl Zeilen und Patienten); offene und große Gruppen zuerst; „Zeilen zeigen“ klappt die
  einzelnen Zeilen auf. Je Gruppe „Für alle mit diesem Wert“: die Entscheidungen, die für alle Zeilen der Gruppe möglich
  sind (bei „Wert eintragen“ mit Eingabe). Einzeln: Häkchen je Zeile, „Alle sichtbaren“, „Alle n auswählen“, Filter nach
  Angabe; Sammelentscheidung mit den gemeinsamen Möglichkeiten oder „Entscheidungen der Auswahl zurücknehmen“. Darüber
  die Karte „Gewichte zusammenfassen“ (nicht / 1–7 Tage, Standard 2) mit Zahl und Liste (übernommen ↔ ersetzt).
- **Endpunkte:** `PATCH /api/altimport/zuordnung/` mit den neuen Bereichen `regeln` (`{"Tabelle:Feld:Wert": {art, wert?} |
  null}`; der Server prüft, dass die Entscheidung für alle Zeilen der Gruppe möglich ist, und speichert Wahlmöglichkeiten
  und Befund mit) und `einstellungen` (`{"gewichte_tage": 0–14 | null}`). Die Mehrfachauswahl nutzt `korrekturen` mit
  mehreren Schlüsseln in einem Aufruf. `GET` liefert je Auffälligkeit `gruppe` und `regel`, dazu `zusammengefasst`
  (`tage`, `anzahl`, `patienten`, `gruppen` – die ersten 300).
- **Logik – Regeln:** Eine Regel gilt für jede Zeile, in der das Feld genau diesen Wert hat (ohne Rand-Leerraum; NULL wie
  leer) – unabhängig von der Zeilennummer, also auch für neue Zeilen im frischen Dump. Eine Entscheidung zur einzelnen
  Zeile hat Vorrang. Eine Regel, deren Entscheidung für eine Auffälligkeit nicht vorgesehen ist, wirkt dort nicht
  (z. B. kann eine PLZ-Regel nie eine Akte auslassen). Ausgelassene Zeilen bleiben mit „per Regel“ sichtbar und änderbar.
- **Logik – Gewichte zusammenfassen:** je Patient nach Erfassungszeitpunkt (`lastchange`) sortiert; eine Gruppe beginnt
  beim ersten Eintrag und umfasst alle Einträge bis zu N × 24 Stunden danach (keine Kette: ein Eintrag danach beginnt
  eine neue Gruppe). Übernommen wird der zuletzt erfasste, bei gleichem Zeitpunkt der spätere im Dump. Das läuft nach
  allen Entscheidungen und Platzhalter-Regeln, sodass ein ausgelassener Wert keinen echten verdrängt. Zählung
  „zusammengefasst“, Protokoll Regel 2 mit den Nummern der ersetzten Einträge.
- **Geklärt 09.10.2026 (U64):** „innerhalb von 1–2 Tagen“ = Zeitfenster ab dem ersten Eintrag, Standard 2 Tage
  (48 Stunden); einstellbar. Ein „unverändert übernommenes“ unplausibles Gewicht (z. B. 1 kg) zählt beim Zusammenfassen
  mit und kann als jüngster Eintrag gewinnen – deshalb solche Werte zuerst per Regel „nicht übernehmen“.
- **Teststatus:** `test_rein.py` Klasse `RegelnUndZusammenfassen` (Regel für alle Zeilen auch im frischen Dump, Vorrang
  der Einzelentscheidung, Regel mit Wert, unpassende Regel, Zusammenfassen 2/1/0 Tage, nach den Entscheidungen) – lokal
  grün; `tests.py` `test_regeln_mehrfachauswahl_und_zusammenfassen` (Schnittstelle, Prüfungen); `aa-import.spec.ts`
  (Gruppe mit Regel, Mehrfachauswahl, Karte „Gewichte zusammenfassen“). Am 09.10.2026 lokal gegen PostgreSQL 16 geprüft:
  alle 357 Backend-Tests grün (davon 62 im Import), nachdem der seit F158 rote Test `test_form_wird_ignoriert` behoben
  war (das verworfene Feld „form“ stand noch im Serializer der Darstellung und wurde gespeichert). Typprüfung der
  geänderten Oberfläche grün; der Browsertest steht aus (GitHub Actions startete wegen des Ausgabenlimits nicht).
- **Status:** ABGESCHLOSSEN – Browserlauf steht aus

## T · Scans und Texterkennung (Festlegung 08.10.2026)

> „Ich habe teilweise handgescannte Dokumente, teilweise Bilder mit Text. Das alles nach Möglichkeit OCR erkennen lassen.“
> – gedruckter Text, ohne externen Dienst. „Einen weiteren Menüpunkt … mit dem Namen Scans oder OCR. Hier wird dann ein
> Scan hochgeladen und ggf. angepasst. Anschließend OCR durchgeführt. … dem Patienten zugeordnet werden oder einfach zum
> Rauskopieren bereitgestellt. Die Textdokumente stehen bis zur eigenen Löschung oder 7 Tage bereit. Vorlage kann
> Zeitraum erweitern.“ Präzisiert: eigener Menüpunkt in der Reihenfolge direkt nach „Datenschutz“; verlängern können
> **beide** (Admin global, Mitarbeiter je Scan); automatische Bereinigung; „höchstbeste Erkennung für schlechte
> Dokumente, da teilweise Patienten die Sachen einscannen“; kein Info-Blatt für Patienten; meist Arztbriefe, Diagnosen,
> Blutwerte, BIA – „Werte automatisch beim Patienten in den entsprechenden Punkten ausfüllen“ (nach Bestätigung).

### F160 Menüpunkt „Scans“
- **Ansicht:** `/scans`, eigener Menüpunkt nach „Datenschutz“ mit Zahl der erkannten, noch nicht zugeordneten Scans
  (Punkt, solange etwas erkannt wird). Links die Liste (Vorschaubild, Status, erkannte Art, Seiten, von wem, „gelöscht in
  n Tagen“, Suche in Titel/Datei/Person, belegter Speicher), rechts der gewählte Scan oder die Ablage zum Hochladen
  (Knopf, Ziehen auf die Seite, mehrere Dateien = mehrere Scans). PDF, JPG, PNG, TIFF, WEBP, HEIC; Größe wie beim
  Dokument-Upload (`EPM_UPLOAD_MAX_MB`), bis `EPM_SCANS_MAX_SEITEN` (50) Seiten je Scan.
- **Recht:** neues Recht „Scans bearbeiten“ (`scans_bearbeiten`), Standard Mitarbeiter, Mitarbeiter (erweitert),
  Mediziner, Admin; Betrachter sehen den Menüpunkt nicht. Scans eines Testbenutzers sind nur mit „Testdaten sehen“
  sichtbar und nur Testpatienten zuzuordnen.
- **Startseite:** Hinweis „n Scans warten auf Zuordnung / laufen in 24 Stunden ab / Speicher fast voll“.
- **Ablage:** eigener Ordner `data/scans` (Volume für Backend und OCR-Dienst), je Scan ein Ordner mit zufälligem Namen;
  Datenbank: `scans.Scan`, `scans.ScanSeite`.
- **Endpunkte:** `GET/POST /api/scans/`, `GET/PATCH/DELETE /api/scans/{id}/`, `GET /api/scans/stand/`,
  `POST …/verlaengern/`, `…/erneut/`, `…/auswerten/`, `…/reihenfolge/`, `…/aufteilen/`, `…/zusammenfuehren/`,
  `…/zuordnen/`; `GET …/pdf/`, `…/textdatei/`, `…/pruefen/?patient=`; Seiten: `GET …/seiten/{sid}/bild/?art=bild|roh|klein`,
  `PATCH …/seiten/{sid}/`, `POST …/seiten/{sid}/bereich/`, `DELETE …/seiten/{sid}/entfernen/`.
- **Audit-Log:** neue Art „Scan“ (hochgeladen, verlängert, gelöscht, abgelaufen, zugeordnet) – vor dem Zuordnen ohne
  Titel (Datensparsamkeit).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F161 Seite anpassen
- **Automatisch** je Seite: Blatt im Foto finden (Ecken), Perspektive entzerren, Drehung (Tesseract-OSD), Schräglage
  (Projektionsprofil), Schatten/ungleichmäßiges Licht ausgleichen (Hintergrund-Division), Rauschen mindern, auf
  Schrifthöhe skalieren, Sauvola-Binarisierung; bei gewölbten Seiten (Buchfalz, geknicktes Blatt) Glätten mit UVDoc.
- **Von Hand** („Anpassen“, Dialog): Ecken ziehen, links/rechts drehen, Glätten, Schräglage, Schatten, Modus
  (Automatisch, Graustufen, Schwarz-Weiß, Farbe), Kontrast, Helligkeit, Original anzeigen. „Übernehmen“ bereitet die
  Seite neu auf und erkennt sie neu. Dazu: Seite entfernen, Reihenfolge ändern, Stapel ab einer Seite aufteilen, zwei
  Scans zusammenführen.
- **Bereich neu erkennen:** Rechteck aufziehen → nur dieser Ausschnitt wird mit stärkerer Vergrößerung neu gelesen.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F162 Texterkennung ohne externen Dienst
- **OCR-Dienst:** eigener Container `ocr` (gleiches Image, `manage.py epm_ocr`), arbeitet die Warteschlange ab
  (`select_for_update(skip_locked)`), Lebenszeichen je Auftrag, drei Versuche, Fortschritt je Seite.
- **Zwei Verfahren, zusammengeführt:** Tesseract 5 mit dem genauesten deutschen Modell (`tessdata_best`, im Repo unter
  `backend/scans/modelle/tesseract/`) und PP-OCRv5 (PaddleOCR, als ONNX über onnxruntime; Modelle beim Bau des Images
  aus `huggingface.co/monkt/paddleocr-onnx`, feste Revision, geprüft gegen `modelle.json`). Stimmen beide überein, gilt
  das Wort als sicher; weichen sie ab, wird das sicherere genommen und das Wort als **unsicher** (unter 80 %) mit der
  anderen Lesart markiert. PDF mit Textebene: der Text wird übernommen, nicht neu gelesen.
- **Fachwörter:** Namen und Kurznamen des Laborkatalogs und eine eigene Liste (Vorlagen › Grenzwerte) helfen Tesseract
  beim Lesen.
- **Ansicht:** Seitenbild mit markierten unsicheren Wörtern (abschaltbar), Text daneben (Reihen mit Tabulator getrennt,
  lässt sich in eine Tabelle einfügen), Sicherheit in % und Zahl der unsicheren Wörter, „gelesen mit …“.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F163 Einem Patienten zuordnen
- **Ablauf:** „Zuordnen“ → Patient (Vorschlag aus Name/Geburtsdatum im Dokument), Titel, Datum (aus dem Dokument),
  Dokumenttyp, Notiz; Prüfung „passt das Dokument zum Patienten?“ (Name, Geburtsdatum). Gespeichert wird in **einer**
  Transaktion: Dokument in der Akte (Herkunft „Scan“) als durchsuchbare PDF, auf Wunsch zusätzlich die unveränderte
  Datei, dazu der erkannte Text (`patienten.DokumentText`) und die gewählten Werte (F166). Danach wird der Scan entfernt.
- **In der Akte:** Reiter Dokumente sucht auch im erkannten Text; Kennzeichen „Text“; „Erkannter Text“ zum Lesen und
  Kopieren (`GET /api/dokumente/{id}/text/`); Quelle „Aus ‚Scans‘ zugeordnet am … (Text erkannt)“.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F164 Text herauskopieren und herunterladen
- „Text kopieren“ (ganzer Scan oder je Seite; ohne sicheren Kontext über ein Textfeld), „Als Text herunterladen“ (.txt),
  „Als durchsuchbare PDF herunterladen“ (Seitenbilder mit unsichtbarem Text).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F165 Aufbewahrung und automatische Bereinigung
- **Regeln** (Vorlagen › Grenzwerte › „Scans und Texterkennung“): nicht zugeordnete Scans löschen nach **7 Tagen**
  (1–365), verlängern um **7 Tage** je Klick, höchstens **30 Tage** ab dem Hochladen (nicht kürzer als die Frist),
  Speicher-Obergrenze (Standard 2000 MB) und Zahl der Scans (Standard 300); Fachwörter. Mitarbeiter verlängern je Scan
  („verlängern“, bis zur Höchstdauer), löschen von Hand jederzeit.
- **Bereinigung:** der OCR-Dienst räumt stündlich auf: abgelaufene Scans endgültig löschen (Datenbank und Dateien,
  Audit-Log „abgelaufen“ mit Anzahl), verwaiste Ordner und Reste nach 24 Stunden, Scans ohne Dateien (nach einer
  Wiederherstellung) und hängende Aufträge zurücksetzen. Abgelaufene Scans sind schon vor dem Aufräumen nicht mehr
  sichtbar.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F166 Werte in die Akte übernehmen (nach Bestätigung)
- **Erkannt** wird die Art (Laborbefund, BIA-Messung, Arztbrief), dazu Dokumentdatum, Abnahmedatum, Labor.
  - **Labor:** Zeilen „Parameter – Wert – Einheit – Referenz“ gegen den Laborkatalog (Name, eingebaute Synonyme, neues
    Feld **Suchbegriffe** je Parameter unter Vorlagen › Kataloge); Einheiten repariert (`mg/di` → mg/dl, `ng/mi` → ng/ml)
    und in die Katalogeinheit umgerechnet (z. B. Albumin g/dl → g/l, Zink µg/dl → µg/l, Stoffmengen über die Molmasse);
    Referenz und Kennzeichen H/L; Werte außerhalb plausibler Grenzen werden nicht vorgeschlagen.
  - **BIA:** Phasenwinkel, Resistanz, Reaktanz, Zellmasse, ECM/BCM, Fett, Magermasse, Wasser … nach Beschriftung.
  - **Diagnosen:** ICD-10-Codes nur im Zusammenhang („Diagnose“, „ICD“) und Abschnitte wie „Diagnosen“, „Beurteilung“.
- **Prüfansicht** im Zuordnen-Dialog: jede Zeile mit Häkchen, editierbar, ein Klick zeigt die Stelle im Bild; unsichere
  Werte sind **nicht** vorgewählt („Erkennung unsicher – bitte mit dem Original vergleichen“). Gespeichert wird nur,
  was angehakt ist: Laborbefund mit Werten (Beurteilung als Text), BIA-Messung (Gewicht auf Wunsch in den Verlauf),
  Diagnosen in die strukturierte Liste, Abschnitte als Anhang an Diagnose/Therapie/Empfehlung.
- **Rechte beim Zuordnen:** zusätzlich „Kontakte, Gewichte, Termine, Dokumente erfassen“; Diagnosen und Texte zusätzlich
  „Patienten anlegen, Diagnose, Therapie, Stammdaten ändern“ (Admins wie überall nur bei Testpatienten).
  Knopf nennt, was übernommen wird („In die Akte legen + 6 Laborwerte“).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F167 Texterkennung unter Administration › System
- Karte „Texterkennung“: bereitstehende Verfahren (Tesseract, Modell, PP-OCRv5 ja/nein), Lebenszeichen des OCR-Dienstes,
  Warteschlange, Speicher; `epm_info` liefert dasselbe. Fehlen die PP-OCR-Modelle im Image, arbeitet die Erkennung mit
  Tesseract allein und sagt das hier und in „Scans“.
- **Betrieb:** Compose-Dienst `ocr` mit Speichergrenze und Healthcheck; `data/scans` legt `04-projekt.sh` an; beim
  Wiederherstellen hält der Systemagent auch `ocr` an. **Modelle offline:** `werkzeuge/ocr-modelle.sh vorbereiten` (bzw. `ocr-modelle.ps1`
  unter Windows) lädt die Modelle auf einem beliebigen Rechner mit Internet und prüft sie gegen `modelle.json`;
  `sudo epm-ocr-modelle einspielen DATEI.tar` legt sie auf der Test-VM nach `/srv/epm/ocr-modelle`, `epm-update` legt
  sie vor dem Bau in den Bau-Kontext (`scans/modelle/dateien/`, nicht im Repo) und baut ein vorhandenes Image ohne
  Modelle neu; das Update meldet „Texterkennung: Tesseract + PP-OCRv5“ bzw. „nur Tesseract“. **Scan-Dateien sind nicht in der Sicherung** (laufen ohnehin
  nach Tagen ab); zugeordnete Dokumente sind es.
- **Teststatus (für F160–F167):** `scans/tests.py` (24 Tests gegen PostgreSQL mit echter Erkennung: Foto mit
  Perspektive/Schatten/Drehung, Laborwerte und Umrechnung, BIA, Verlängern bis Höchstdauer, Bereinigung, Zuordnen in
  einer Transaktion, Rechte, Testdaten) – lokal grün; volle Backend-Suite lokal. Browsertest `e2e/scans.spec.ts`
  (Foto hochladen → erkennen → kopieren → zuordnen mit Laborwerten → Suche im Text der Akte; Anpassen, Verlängern,
  Löschen; Betrachter ohne Menüpunkt) – Ablauf lokal im Browser durchgespielt, **CI-Lauf steht aus** (GitHub Actions
  läuft derzeit nicht: Abrechnung).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F168 Texterkennung auf kleinen Servern: Sparmodus und Absturzschutz
- **Anlass 09.10.2026 (Test-VM, 4 GB RAM, 2 Kerne):** „Seite 2 wird nicht erkannt, dauert bisher 3-mal so lange wie
  die erste Seite.“ Befund: Swap voll, OCR-Dienst neu gestartet. Großes Zeilenmodell + Glätten + der wachsende
  Speicher von onnxruntime bei wechselnden Bildgrößen übersteigen den RAM; nach dem Absturz blieb der Scan bis zur
  stündlichen Bereinigung auf „wird erkannt“. Festlegung: **Sparmodus**; ein späterer Umzug auf einen VPS mit 8 GB ist
  möglich und braucht keine Einstellung.
- **Sparmodus** (`EPM_OCR_MODUS` = auto | voll | sparsam; auto: unter 2,5 GB für den Dienst): kleines Zeilenmodell
  PP-OCRv5_mobile_det (4,8 MB, Apache-2.0, Prüfsumme in `modelle.json`, eigene Quelle), kein Glätten, Zeilensuche
  bis 1536 px. Voller Modus: server_det, UVDoc, 2048 px. Systemseite und „Scans“ zeigen den Modus („· Sparmodus“).
- **Speichergrenze und Kerne nach dem Server** (`04-projekt.sh`, nur wenn in `/srv/epm/.env` noch nicht gesetzt):
  unter 6 GB RAM 1,5 GB, unter 12 GB 3 GB, sonst 4 GB (`EPM_OCR_SPEICHER`); Kerne = Anzahl − 1, mindestens 2,
  höchstens 6 (`EPM_OCR_THREADS`). Test-VM → 1,5 GB/2 Kerne → Sparmodus; VPS 1000 G12 (8 GB, 4 Kerne) → 3 GB/3 Kerne →
  voller Modus. Kein zusätzlicher Swap für den Container (`memswap_limit`): Reicht der Speicher nicht, bricht der
  Dienst ab, statt die VM ins Auslagern zu treiben.
- **Speicher:** onnxruntime ohne Speicher-Arena und Speichermuster (gibt den Speicher nach jeder Seite zurück),
  Aufräumen nach jeder Seite.
- **Schneller im Sparmodus (09.10.2026):** mit PP-OCR nur ein Tesseract-Durchgang (die zweite Lesart liefert PP-OCR),
  spart rund ein Drittel der Zeit je Seite; ohne PP-OCR bleiben beide Durchgänge für den Abgleich.
- **Absturzschutz:** Der Dienst schreibt während der Erkennung alle 20 s ein Lebenszeichen (eigener Faden). Fehlt es
  90 s lang, kommt der Scan sofort wieder in die Warteschlange (vorher: bis zu einer Stunde). Je Seite wird ein
  abgebrochener Versuch erkannt (`begonnen_am`, `abbrueche`): 1. Wiederholung sparsam (ohne Glätten, kleinere
  Zeilensuche), 2. nur Tesseract, nach dem 3. Abbruch nur diese Seite als Fehler mit Hinweis; andere Seiten laufen
  weiter. Nach vier Abbrüchen ohne Fortschritt: Scan als Fehler („Erneut erkennen“ möglich). Reguläres Beenden
  (Update, `docker stop`) stellt den Scan sofort zurück und zählt nicht als Abbruch.
- **Anzeige:** Fortschritt innerhalb der Seite („Seite 2 von 3: PP-OCR liest“); Seite mit Hinweis, wenn sie sparsam
  erkannt wurde; Systemseite: „in Arbeit“/„wartend“ getrennt, Speicher des Dienstes (belegt, Höchststand, Grenze –
  ab 90 % mit Hinweis, `EPM_OCR_SPEICHER` zu erhöhen), Zahl der Seiten mit Abbrüchen.
- **Teststatus:** `scans/tests.py` (Absturz mitten in Seite 2 → Sparstufe 1, dritter Abbruch markiert nur die Seite,
  Stufe 2 nur Tesseract, zu viele Abbrüche, geplantes Beenden, Herzschlag, Moduswahl nach Speicher). Speicherbedarf
  der Modelle auf der Test-VM: **Lauf steht aus** (hier nicht messbar, die Modelle sind in dieser Umgebung nicht ladbar).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F169 Werte von Hand in Labor und BIA übertragen
- **Wunsch 09.10.2026:** „Mir fehlt die Möglichkeit, die Werte direkt in ein Labor oder BIA zu übertragen. Die Felder
  liegen ja vor.“ – „Es muss halt sauber die Werte in die Felder übertragen und performant sein.“
- **Zuordnen:** „Laborbefund übernehmen“ und „BIA-Messung übernehmen“ stehen immer zur Wahl, auch wenn die Art nicht
  erkannt wurde (anderes Gerät, anderes Layout). Feld anklicken → Hinweis über dem Bild („Für Gewicht eine Zahl im Bild
  anklicken“) → Wort im Bild anklicken: die Zahl steht im Feld (aus „3,21L“ wird 3,21; ein Referenzbereich „3,5-5,1“
  füllt von und bis; Einheit als Text). Tippen geht weiter. Das Bild bleibt beim Scrollen der Felder stehen.
- **Labor:** „+ Wert“ fügt eine Zeile hinzu (Parameter aus dem Katalog – Einheit wird vorbelegt – oder Name als
  Freitext). Übernommen werden angehakte Zeilen mit Wert und Parameter/Name. Abnahmedatum wird mit dem Datum aus dem
  Dokument vorbelegt.
- **BIA:** alle Felder der BIA-Messung (Gewicht, BCM, Fettmasse, ECW %, Körperwasser, BMI), weitere Werte als
  Beurteilung. Erkennung erweitert um Bezeichnungen gängiger Geräte (deutsch/englisch: seca, Data Input/Nutriguard,
  Akern, InBody, Tanita, RJL, Bodystat); ECW als Verhältnis („ECW/TBW 0,385“) wird mit Hinweis in Prozent umgerechnet;
  Skelettmuskelmasse, ICW, viszerales Fett u. a. als weitere Werte (U66).
- **Teststatus:** `scans/tests.py` (BIA anderer Geräte); `e2e/scans.spec.ts` „Werte von Hand übertragen“ (BIA nicht
  erkannt → Gewicht per Klick ins Bild, Laborwert ergänzt, gespeichert und in der Akte geprüft) – Ablauf lokal im
  Browser durchgespielt; CI-Lauf steht aus.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F170 „Text erkennen“ an Dokumenten der Akte (OCRmyPDF)
- **Festlegung 09.10.2026:** Automatisch erkannt wird nur, was über „Scans“ kommt (U65). Dokumente, die direkt in der
  Akte liegen (auch aus dem Altsystem), bekommen einen Knopf, der sie erkennt und die Datei „überschreibt“. Auf
  Nachfrage mit **OCRmyPDF** statt der Scans-Erkennung, weil das Aussehen der Seiten so erhalten bleibt.
- **Akte › Dokumente › Details:** „Text erkennen“ (bzw. „Text neu erkennen“) mit Rückfrage. Der OCR-Dienst legt mit
  OCRmyPDF (Tesseract, deutsches Modell) eine unsichtbare Textebene über die Seiten und ersetzt die Datei durch diese
  **PDF/A**: `--rotate-pages`, `--skip-text` (Seiten mit Text bleiben), `--optimize 1` (verlustfrei); Bilder werden zur
  PDF. Titel, Typ, Datum, Notiz bleiben; Dateiname endet auf .pdf. Danach: Kennzeichen „Text“, Suche im Reiter
  Dokumente, „Erkannter Text“ zum Kopieren. Fortschritt und Fehler stehen am Dokument; die Akte bleibt benutzbar.
- **Nicht möglich:** von EPM erzeugte Dokumente, Freigabe-Nachweise von Infusionsplänen, andere Dateitypen als PDF,
  JPG, PNG, TIFF, abgeschlossene Akten. Recht: wie Dokumente bearbeiten (Admins nur bei Testpatienten).
- **Sicher ersetzen:** neue Datei schreiben → Datenbank in einer Transaktion (nur wenn die Prüfsumme noch die vom
  Anfordern ist und die Akte offen) → alte Datei löschen; scheitert etwas, bleibt das Dokument unverändert und die
  neue Datei wird entfernt. Verlauf: „Text erkannt: Datei durch dieselbe PDF mit Textebene ersetzt“; Audit-Log (neue
  Art „Text eines Dokuments erkannt“) mit beiden Prüfsummen und Seitenzahl. OCRmyPDF-Fehler werden verständlich
  gemeldet (verschlüsselt, keine lesbare PDF, kein Text gefunden …); „PDF/A nicht möglich“ ergibt eine gültige PDF.
- **Art. 17 DSGVO:** Durch das Ersetzen hat ein Dokument mehrere Prüfsummen. Endgültiges Löschen schwärzt jetzt alle
  Fassungen in Historie und Audit-Log und schreibt die früheren Prüfsummen in die Löschliste (`fruehere_sha256`);
  das Nachholen nach einer Wiederherstellung erkennt das Dokument auch mit einer früheren Prüfsumme (vorher wäre ein
  Dokument aus einer Sicherung von vor dem Ersetzen zurückgekommen).
- **Betrieb:** Ghostscript (AGPL) und OCRmyPDF (MPL-2.0) im Image; der OCR-Container bindet `data/dokumente` ein.
  Aufträge laufen nach den Scans; Lebenszeichen, Abbruch und geplantes Beenden wie F168; erledigte Aufträge werden
  nach 30 Tagen entfernt. Administration › System zeigt „OCRmyPDF bereit“.
- **Endpunkte:** `POST /api/dokumente/{id}/text-erkennen/` (202, idempotent); `GET /api/dokumente/{id}/` liefert
  `erkennung` (Status, Schritt, Fehler) und `text_erkennbar`.
- **Teststatus:** `scans/test_dokumente.py` – Ersetzen, Befehl, Fehlerfälle, geänderte Datei, abgeschlossene Akte,
  Rechte, Abbruch, Löschung früherer Fassungen (mit einem Ersatz für das externe Programm); **der Test mit dem echten
  OCRmyPDF** ist in CI Pflicht (`EPM_OCRMYPDF_PFLICHT`), lief hier aber nicht (OCRmyPDF in dieser Umgebung nicht
  installierbar). `e2e/scans.spec.ts` „Akte: Text erkennen und Werte übernehmen“. **Lauf steht aus.**
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F171 „Werte übernehmen“ aus einem Dokument der Akte
- **Akte › Dokumente › Details:** „Werte übernehmen“ legt eine Arbeitskopie des Dokuments in „Scans“ an (Kennzeichen
  „aus der Akte“) und öffnet sie. Erkennung und Prüfansicht wie bei einem Scan (Laborbefund, BIA, Diagnosen, Texte;
  Feld anklicken → Wert im Bild anklicken, F169). Der Patient steht fest; **es entsteht kein neues Dokument** –
  Laborbefund und BIA-Messung werden mit dem vorhandenen Dokument verknüpft. Hatte das Dokument noch keinen Text,
  wird der erkannte Text ergänzt (durchsuchbar, Datei unverändert). Danach ist die Arbeitskopie entfernt.
- **Schutz:** Arbeitskopien sieht nur, wer die Akte sieht (z. B. nicht nach einer Einschränkung nach Art. 18);
  beim endgültigen Löschen des Dokuments werden sie samt Dateien sofort entfernt; sonst gilt die Aufbewahrung der Scans.
- **Endpunkt:** `POST /api/dokumente/{id}/werte-uebernehmen/` → `{"scan": ID}` (vorhandene Arbeitskopie desselben
  Benutzers wird wiederverwendet); Zuordnen einer Arbeitskopie ohne Titel/Typ/Datum, nur mit gewählten Werten.
- **Teststatus:** `scans/test_dokumente.py` (Werte aus Akte-Dokument, kein neues Dokument, Patient fest, Sichtbarkeit)
  mit der echten Erkennung; im Browser lokal durchgespielt.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

## U · Schreiben mit E-Mail (Vorlagen von Alice Hessel, 09.10.2026)

Alice hat ihre Vorlagen geschickt (Patientenaufnahme, Reisebescheinigung mit ADAC-Attest, Patientenankündigung,
Fallzusammenfassungen von Prof. Masin, Merkblätter) und eine Terminbestätigung gewünscht. Wunsch von Filip: PDFs mit
dem Namen nach Bedarf erstellen und vorgefertigte E-Mail-Texte **mit Anhang** zum Versand vorbereiten.
Übersicht und Rückfragen: `docs/VORLAGEN-ALICE-2026-10-09.md`.

### F172 Schreiben aus der Akte: PDF und fertige E-Mail
- **Akte › ⋯ › „Schreiben und E-Mail …“** (Recht „Kontakte, Gewichte, Termine, Dokumente erfassen“, offene Akten):
  Patientenaufnahme (benötigte Unterlagen), Terminbestätigung Sprechstunde (Termin wählen; Praxis Dr. Holtmeier,
  Gesundheitskarte mitbringen, keine Überweisung nötig), Reisebescheinigung (Briefkopf Dr. Holtmeier, deutsch/englisch,
  Wörter nach Geschlecht: „der Patientin/des Patienten“, „Mrs./Mr.“, „her/his“).
- **Reisebescheinigung + ADAC-Attest:** Das ärztliche Attest des ADAC hängt als zweite Seite an
  (`vorlagen/statisch/adac-attest.pdf`); Name mit Geburtsdatum, Ort „Münster“, Datum und auf Wunsch die Reisedauer in
  Tagen sind eingetragen, die übrigen Felder (Medikamente, Unterschrift) bleiben ausfüllbar (pypdf).
- **E-Mail:** Neuer Baustein „E-Mail“ in den Dokumentvorlagen (Betreff und Text mit Datenfeldern, nicht auf der PDF,
  höchstens einmal, nur bei den Schreiben). Im Dialog sind Empfänger (E-Mail der Akte), Betreff und Text änderbar.
  „E-Mail vorbereiten“ lädt eine **.eml** mit Text, PDF und gewählten Anlagen; `X-Unsent: 1` → Outlook öffnet sie als
  Entwurf zum Absenden (ein `mailto:`-Link kann keine Anhänge mitgeben). Außerdem „PDF ansehen/herunterladen“,
  „Text kopieren“ und „in der Akte ablegen“ (Dokumenttyp „Schreiben“, Migration `stammdaten/0017`).
- **Neue Datenfelder:** `Patient.Vorname_Name`, `Patient.Briefanrede` („Sehr geehrte Frau …“), `Patient.der_Patientin`,
  `Patient.die_Patientin`, `Patient.ihre`, `Patient.ihrer`, `Patient.Mrs`, `Patient.her`, `Benutzer.Name`,
  `Termin.Datum` (mit Wochentag), `Termin.Uhrzeit`, `Termin.Ort`, `Termin.bei`, `Termin.Titel`.
- **Endpunkt:** `POST /api/patienten/{id}/schreiben/` `{"art", "ausgabe": "pdf"|"email"|"eml", "termin"?, "tage"?,
  "attest"?, "ablegen"?, "anlagen"?, "betreff"?, "text"?, "an"?}`; Audit-Log „Export“ mit Art und Ausgabe.
  Vorschau im Editor: `POST /api/vorlagen/{art}/vorschau/` mit `"ausgabe": "email"` liefert Betreff und Text.
- **Nebenbei behoben:** Eine Vorlage mit „Zwei Spalten“, aber ohne Fußzeile, druckte die rechte Spalte unten rechts
  auf jede Seite (Variablenname in `pdf.bloecke_html`).
- **Teststatus:** `vorlagen/test_schreiben.py` (PDF, E-Mail-Text, .eml mit Anhängen, Ablage, Rechte, fremder
  Termin, Attest-Felder, Geschlecht); im Browser lokal durchgespielt.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F173 Patientenankündigung aus dem Kalender
- **Kalender › „Ankündigung“:** Zeitraum (Vorgabe: Woche des gewählten Tages) und Terminort der Sprechstunde wählen →
  alle Praxistermine im Zeitraum nach Tag und Uhrzeit, ohne Testpatienten und ausgeblendete Termine. Termine an
  einem anderen Ort stehen mit diesem Ort als Hinweis (bei „Telefon“/„Video“ mit der Telefonnummer der Akte), dazu
  der Freitext „bei/Ort“ des Termins (z. B. „1 h, Neuaufnahme“, „+ Labor“). PDF zum Faxen oder E-Mail wie F172.
- **Vorlage** „Patientenankündigung Sprechstunde“ mit Tabelle „Termine im Zeitraum“ und dem Datenfeld
  `Termine.Liste` (Text für die E-Mail), `Zeitraum`, `Zeitraum.von/bis`, `Terminort`, `Anzahl`.
- **Endpunkt:** `POST /api/kalender/ankuendigung/` `{"von", "bis", "ort"?, "ausgabe", …}` (höchstens zwei Monate).
- **Teststatus:** `vorlagen/test_schreiben.py` (Reihenfolge, Hinweis, ohne Testpatient und Wiedervorlage, .eml).
- **Geändert durch F177 (10.10.2026):** Knopf heißt „Praxis informieren“, Dialog „Infoblatt an die Praxis“; mit
  gewähltem Ort stehen nur noch die Termine an diesem Ort auf dem Blatt (Telefon/Video auf Wunsch).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F174 Anlagen für E-Mails
- **Vorlagen › „Anlagen für E-Mails“:** PDFs hochladen (höchstens 20 MB), öffnen, deaktivieren (nie löschen).
  Mitgeliefert und beim ersten Aufruf angelegt: Leitfaden Kurzdarmsyndrom und Zottentraining, Handlungsempfehlung
  Aspiration NutriLock/TauroLock, Blutuntersuchung – Schreiben an Hausärzte. Im Dialog der Schreiben ankreuzbar.
- **Ablage:** `EPM_DOKUMENTE/anlagen/` (mit in der Datensicherung), Modell `vorlagen.Anlage` mit Historie.
- **Endpunkte:** `GET/POST /api/anlagen/`, `PATCH /api/anlagen/{id}/`, `GET /api/anlagen/{id}/datei/`.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F175 Fallzusammenfassung mit einheitlicher Gliederung
- Neue Berichtsart „Fallzusammenfassung“ (Migration `stammdaten/0017`). Im Bericht-Dialog „Gliederung einfügen“:
  12 Abschnitte, zusammengeführt aus den Fallzusammenfassungen von Prof. Masin (Kaufmann, Wilkening, Steiner,
  Quante): Anlass und Unterlagen · Diagnosen · Anamnese und Verlauf · Symptomatik · Ernährungsstatus/Anthropometrie
  (GLIM) · Ernährungstherapie · Medikation/Allergien · Labor · Bildgebung · Beurteilung · Empfehlungen · Offene Fragen
  und Unstimmigkeiten. Hinweise in [eckigen Klammern] werden überschrieben; Freigabe und PDF wie jeder Bericht (F115).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F176 Eigene Vorlagen (Schreiben selbst anlegen)
- **Wunsch Filip 09.10.2026:** „Unter Vorlagen manuell Schreiben hinzufügen – Button für Dokumentvorlage erstellen.“
- **Vorlagen › Dokumentvorlagen › „+ Neue Vorlage“:** Name, Beschreibung und „beim Erzeugen einen Termin wählen“.
  Die Vorlage startet als Brief an den Patienten (Briefkopf, Absenderzeile, Anschrift, Titel = Name, Anrede, Text in
  [eckigen Klammern], Gruß, Fußzeile) mit E-Mail-Baustein und ist sofort als Version 1 aktiv; danach wie jede Vorlage
  bearbeiten, Vorschau, veröffentlichen. „Name und Einstellungen“ ändert Name, Beschreibung, Termin und aktiv
  (deaktiviert = in der Akte nicht mehr wählbar; gelöscht wird nichts, Versionen bleiben).
- **Akte:** Eigene Vorlagen stehen im Dialog „Schreiben und E-Mail“ unter „Eigene Vorlagen“ – PDF, E-Mail (.eml),
  Ablage wie F172. Datenfelder: Patient, Anrede, Absender, Benutzer und Termin.
- **Technik:** Modell `vorlagen.EigenesSchreiben` (Kennung `eigen-…`, Historie); die Art einer `Dokumentvorlage` ist
  dafür keine feste Auswahl mehr (Migration `vorlagen/0005`). Endpunkte: `POST /api/vorlagen/` (anlegen),
  `PATCH /api/vorlagen/{art}/eigen/`, `GET /api/schreiben/` (wählbare Schreiben der Akte).
- **Teststatus:** `vorlagen/test_schreiben.py::test_eigenes_schreiben`; im Browser lokal durchgespielt.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F177 Infoblatt an die Praxis (alle Termine in der Praxis Holtmeier auf einem Blatt)
- **Anlass (10.10.2026):** Die Patientenankündigung (F173) war zu versteckt („Ankündigung“ im Kalender), und die
  Pflegekräfte hielten sie für ein Schreiben zu einem Patienten. Gewünscht: alle Patiententermine, die im Kalender mit
  der Praxis Holtmeier vereinbart sind, als ein Informationsblatt an die Praxis – zu einem festen Zeitpunkt.
- **Kalender › „Praxis informieren“** (Recht „Kontakte, Gewichte, Termine, Dokumente erfassen“; Telefon: Briefsymbol
  mit gleichlautender Beschriftung für Screenreader) öffnet **„Infoblatt an die Praxis“**: große Auswahl
  „Nächste Woche“ (Mo–So) | „Übernächste Woche“ | „Nächster Monat“ | „Eigener Zeitraum“ (von/bis; Vorgabe je nach
  Einstellung nächste Woche oder nächster Monat), Ort (vorbelegt: Terminort mit „Holtmeier“ im Namen) und
  „Telefon- und Videotermine auch aufführen“. Darunter die Vorschau „Diese N Patienten stehen auf dem Infoblatt“ nach
  Tagen mit Uhrzeit, Name (Link zur Akte) und Hinweis, Markierung **neu** bzw. „verschoben, vorher …“, „Zuletzt
  erstellt am … von … für …“, die Termine, die auf dem letzten Blatt standen und jetzt fehlen, und ein verständlicher
  leerer Zustand. Darunter wie bisher PDF ansehen/herunterladen und E-Mail vorbereiten (F172); ohne Termine sind die
  Knöpfe aus.
- **Nur Termine am gewählten Ort:** Mit Ort stehen nur Praxistermine an diesem Ort auf dem Blatt, mit `telefon_mit`
  zusätzlich Telefon-/Videotermine (Hinweis mit Telefonnummer wie bisher), andere Orte fehlen. Praxistermine **ohne
  Ort** fehlen und erscheinen als Warnung „Bei diesen Terminen fehlt der Ort – bitte im Termin eintragen“ mit Link zur
  Akte und „Ort eintragen“ (öffnet den Termin, Ort ist vorgeschlagen). Ohne Ort („– alle Praxistermine –“) wie F173.
- **Termin:** Bei Art „Praxistermin“ ist der Ort mit „Holtmeier“ im Namen vorbelegt, solange kein Ort gewählt ist
  (auch beim Bearbeiten eines Praxistermins ohne Ort); „—“ lässt sich bewusst wählen, dann erscheint der Hinweis,
  dass der Termin nicht auf dem Infoblatt steht.
- **Merken, was verschickt wurde:** Modell `patienten.Ankuendigung` (Migration `patienten/0015`): erstellt am, Person,
  von, bis, Ort, mit Telefonterminen, Ausgabe (pdf/eml), Anzahl und Schnappschuss `[{termin, datum, uhrzeit}]` –
  **ohne Namen**. Angelegt bei „PDF herunterladen“ und „E-Mail vorbereiten“ (.eml), nicht bei der Vorschau-Liste,
  dem E-Mail-Text und „PDF ansehen“ (`"vorschau": true` – nur angesehen, nicht verschickt). „neu“ =
  Termin fehlt im Schnappschuss des zuletzt erstellten Blatts (gleicher Ort), das diesen Tag umfasst, oder steht dort
  mit anderer Uhrzeit; für Tage ohne früheres Blatt ist nichts „neu“. Keine Historie (das Modell ist selbst das
  Protokoll); das Erzeugen steht außerdem wie bisher als „Export“ im Audit-Log (nur Zeitraum, Anzahl, Ausgabe).
- **Löschung:** Beim endgültigen Löschen einer Akte (Art. 17) und beim Zurücksetzen der Testdaten entfernt
  `datenschutz.akten_entfernen` die Termine dieser Akte (auch aus der Historie bekannte Nummern) aus allen
  Schnappschüssen; die Anzahl bleibt. „Datenbank leeren“ entfernt alle Infoblätter.
- **Erinnerung auf der Startseite:** Einstellungen `infoblatt_rhythmus` (woche = nächste Kalenderwoche Mo–So |
  monat = nächster Kalendermonat | aus) und `infoblatt_vorlauf_tage` (Standard: woche, 3 Tage; 1–6 bei wöchentlich,
  1–27 bei monatlich), gepflegt unter Vorlagen › Grenzwerte › „Infoblatt an die Praxis“ (Migration
  `stammdaten/0018`). Ab Beginn − Vorlauf bis zum Beginn zeigt die Startseite „Praxis Holtmeier informieren: X Termine
  vom … bis …“ mit Knopf „Infoblatt erstellen“ (öffnet den Dialog mit genau diesem Zeitraum) – nur mit dem Recht
  „Einträge erfassen“, nur wenn im Zeitraum Termine stehen (auch solche ohne Ort) und solange kein Blatt (dieser Ort
  oder alle Orte) die Tage mit Terminen umfasst.
- **Endpunkte:** `POST /api/kalender/ankuendigung/` `{"von", "bis", "ort"?, "telefon_mit"?: bool, "ausgabe":
  "liste"|"pdf"|"email"|"eml", …}` – `liste` liefert `{von, bis, ort, telefon_mit, anzahl, termine: [{termin,
  patient, name, datum, uhrzeit, hinweis, neu, vorher}], ohne_ort: [...], entfallen: [...], letzte: {erstellt_am,
  von_name, von, bis, anzahl, ausgabe} | null}`. `GET /api/startseite/` → `infoblatt: {von, bis, rhythmus, anzahl,
  ohne_ort, ort} | null`; `GET /api/kalender/` → `infoblatt_rhythmus`. Logik in `patienten/infoblatt.py`.
- **Hilfe:** neuer Abschnitt „Infoblatt an die Praxis (alle Termine bei Dr. Holtmeier)“ (Kalender und Startseite).
- **Teststatus:** `patienten/test_infoblatt.py` (Ortsfilter, `telefon_mit`, Vorschau-JSON, Prüfungen und Rechte,
  Schnappschuss ohne Namen, „neu“/verschoben/entfallen, Art.-17-Löschung, Erinnerung mit Startseite, Einstellungen),
  `vorlagen/test_schreiben.py::test_patientenankuendigung` angepasst; Browsertests `kalender.spec.ts` („Praxis
  informieren“ mit Vorschau, Ort eintragen, PDF) und `mobil.spec.ts` (Dialog am Telefon) – Lauf steht aus.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

## V · Bedienung für Pflegekräfte (10.10.2026)

Auftrag: EPM soll von Pflegekräften ohne nennenswerte IT-Erfahrung intuitiv bedient werden können. Befunde, Umsetzung
und Empfehlungen stehen in `docs/BEDIENBARKEIT-2026-10-10.md`. Akte, Navigation und Infusionspläne werden parallel
strukturell überarbeitet und sind hier bewusst nur in Texten berührt.

### F178 Verständliche Rückmeldungen, nachsichtige Eingaben, nächste Schritte
- **Eingaben:** Datumsfelder verstehen neben „14.03.1968“ auch „14.3.68“, „14,3,68“ (Komma vom Ziffernblock), „14/3/1968“,
  „14-3-1968“, „14031968“, „140368“, „heute“ und „gestern“ (`eingabeDatum`, wirkt in allen Formularen). Die Uhrzeit im
  Dialog „Kontakt erfassen“ geht auch als „10.30“, „1030“, „930“ oder „10“; ein Fehler steht jetzt am Feld Uhrzeit.
- **Rückmeldungen:** „Kontakt erfassen“ sagt neben dem gesperrten Knopf, was fehlt („Zuerst den Patienten wählen.“ /
  „Zum Speichern bitte eine Notiz schreiben.“). „Neuer Patient“ fasst fehlende Angaben oben zusammen, springt zum
  ersten roten Feld und bestätigt das Anlegen mit Name und Nummer.
- **Fehlermeldungen mit Lösungsweg:** keine Verbindung (statt der englischen Browsermeldung „Failed to fetch“), Server
  nicht erreichbar (502/503), Zeitüberschreitung (504), Serverfehler (500), Datei zu groß (413); Anmeldung mit
  Hinweis auf Schreibweise, Feststelltaste und Sperre nach fünf Fehlversuchen, Code mit Hinweis auf den 30-Sekunden-Wechsel;
  Warnung bei eingeschalteter Feststelltaste im Passwortfeld. Verbindungsfehler werden wie bisher zweimal wiederholt.
- **Leere Zustände:** Die Patientenliste ohne Treffer nennt den Suchbegriff, gibt einen Suchtipp und bietet „Alle Filter
  entfernen“, „In abgeschlossenen Akten suchen“ und „Neuer Patient“. Die Patientenauswahl in Dialogen erklärt zu kurze
  Eingaben und fehlende Treffer. Dokumente ohne Eintrag sagen, wie man eines ablegt; „1 Dokument“ statt „1 Dokumente“.
- **Sprache:** „PDF/A mit unsichtbarer Textebene“, „Audit-Log“ und Programmnamen der Texterkennung (PP-OCR, Tesseract)
  aus den Texten für die Pflege genommen (Programmnamen bleiben im Tooltip). Menüs hinter „⋯“ zeigen ihren Namen als Tooltip.
- **Hilfe:** neue Abschnitte „Die wichtigsten Wege im Alltag“ und „Wenn etwas nicht klappt“ ganz oben; Anmelden und
  Dokumente an die Oberfläche angeglichen („Passwort“, „Weiter“, „Neues Dokument“); zweizeilige Einträge im Inhalt der
  Hilfe überlappen nicht mehr. Aufzählungen in formatiertem Text (Notizen, Hilfe) zeigen wieder Punkte bzw. Nummern.
- **„Passwort“ statt „Kennwort“** (Entscheidung vom 10.10.2026) in allen Texten des Backends außer `vorlagen` und
  `infusionen` (Meldungen, Audit-Texte, Hilfe, Einrichtungsbefehle) und in der Anmeldung; Bezeichner, API-Felder,
  Modelle und Migrationen unverändert. Administration, Akte und Zugangsblatt folgen beim Abgleich.
- **Fachbegriffe erklärt** (Entscheidung vom 10.10.2026): Baustein `<Begriff>` (Popover von Base UI; Hover, Fokus,
  Antippen, `aria-describedby`) mit den Texten aus `lib/begriffe.ts` (BIA, Entwurf, BMI, PE, Wiedervorlage,
  Wiedereinbestellung, GLIM, Testpatient, storniert); eingesetzt in Patientenliste, „Kontakt erfassen“ und Scans.
- **Teststatus:** `npm run typecheck` und `npm run build` grün; Backend-Tests `accounts` (u. a. `/api/hilfe/`) grün;
  Datums-/Uhrzeiteingabe stichprobenartig geprüft; Patientenliste, Neuer Patient, Anmeldung, Kontaktdialog und Hilfe am
  PC (1440 px) und Telefon (390 px) per Bildschirmfoto gegen die Entwicklungsumgebung geprüft. **Browsertests: Lauf steht aus.**
- **Status:** ABGESCHLOSSEN – Lauf steht aus

## W · Systemverwaltung ohne SSH (10.10.2026)

Auftrag: „Der Praxismanager soll sich nie wieder per SSH auf den Server schalten müssen.“ Alles, was bisher nur per SSH
ging, läuft jetzt als Auftrag über den Systemagenten (`rollout/epm-systemagent.py`, feste Allowlist `AKTIONEN`,
Version 5) – mit Bestätigung wie unter Tätigkeiten (Rückfrage bzw. Passwort + zweiter Faktor über
`bestaetigung_pruefen`), mit Eintrag im Audit-Log und im Probelauf (`--trocken`) simuliert. Per SSH bleibt nur die
Ersteinrichtung des Servers (`rollout/01…05`, `epm-git-einrichten.sh`, `epm-zertifikat einrichten` für die eigene CA).

### F179 Systemverwaltung: Ampel, Reiter, kompakte Graphen, Wartung ohne SSH
- **F179a Sicherungen mit Mehrfachauswahl löschen** (Administration › Backup › Sicherungen): Checkbox je Zeile,
  „alle auswählen“ (außer der jüngsten), Leiste „N ausgewählt · Größe“, Knopf „N Sicherungen löschen“ → Dialog mit
  Anzahl, Größe, Liste, Hinweis „endgültig“ und Warnung, wenn Sicherungen nirgends sonst liegen (nicht übertragen /
  kein Ziel); Bestätigung mit Passwort und 2FA. Die **jüngste Sicherung ist nie löschbar** (Backend und Agent).
  `POST /api/backup/loeschen/` `{"stempel": [...], "kennwort", "code"}` (Recht „Sicherungen verwalten“; 1–200 Stempel,
  Muster `JJJJ-MM-TT_HHMM[SS]`, keine Doppelten, alle bekannt, Agent muss laufen, kein Wiederherstellen offen).
  Agent-Aktion `sicherung_loeschen`: prüft noch einmal, sucht die Dateien über den Ordnerinhalt (dieselben Muster wie
  die Liste), löscht nur gewöhnliche Dateien (symbolische Links werden übersprungen), nimmt die Sperre der Sicherung,
  bricht ab, solange eine Übertragung läuft, entfernt eine bereitgelegte Download-Kopie und den Übertragungsstand.
  Audit-Log „Backup“: Stempel, Anzahl, Größe, Zahl der unverschlüsselten, bestätigt.
- **F179b Systemverwaltung** (`/admin`, neuer Menüpunkt, Recht Systemverwaltung oder Sicherungen verwalten): Ampel für
  Systemagent, Dienste/Container, Speicherplatz, Ubuntu-Updates (Sicherheitsupdates, Neustart nötig), Zertifikat
  (Ablauf < 30 Tage Hinweis, < 7 Fehler, selbst signiert Hinweis), Texterkennung, Uhrzeit/NTP, letzte Sicherung,
  Übertragung, fehlgeschlagene Aufträge in 24 h; jede Kachel führt zum passenden Reiter. Daneben „Häufige Aufgaben“
  (Jetzt sichern, Ubuntu-Updates, EPM aktualisieren, Server neu starten, Dienste, Software, Zertifikat, Protokolle,
  Hinweis an alle, Benutzer, Audit-Log) und die Auslastung als kleiner Verlauf.
- **F179c Reiter statt Endlos-Seiten**: Administration › System: Übersicht · Wartung · Software · Zertifikat ·
  Protokolle · Anmeldungen und Hinweis · Verlauf · Testphase; Administration › Backup: Sicherungen · Verschlüsselung ·
  Übertragung · Tätigkeiten. Reiter in der Adresse (`?reiter=…`), am Telefon seitlich wischbar
  (`components/ui/reiter.tsx`).
- **F179d Graphen kompakt**: CPU, Arbeitsspeicher und Platte als Zahl mit kleinem Verlauf (24 h,
  `components/ui/sparkline.tsx`); „Größer anzeigen“ bzw. Klick auf die Karte öffnet das große Diagramm mit Zeitraum
  im Dialog (`seiten/admin/auslastung.tsx`). Backup: Größe je Sicherung als kleine Säulen, groß im Dialog.
- **F179e Dienste einzeln neu starten** (Wartung): backend, web, ocr, db; `POST /api/system/dienste/neustart/`
  `{"dienst", "minuten", "hinweis"?, "kennwort", "code"}`, warnt die Angemeldeten; Agent `dienst_neustart`
  (`docker compose restart <dienst>`).
- **F179f Version zurückschalten** (Software): Liste der vorhandenen Versionen (Images `epm-backend`/`epm-web` vom
  Agenten im Status, laufende aus `.env`); `POST /api/system/versionen/zurueck/` `{"tag", "minuten", …}` (Muster
  `X.Y.Z-<commit>`, muss vollständig vorhanden und nicht aktiv sein, Agent muss laufen); Agent `epm_zurueck`: vorher
  Sicherung (`vor_update`), dann `epm-update --zurueck TAG`.
- **F179g Update-Paket hochladen und erstellen** (Software): Hochladen in Stücken wie bei Sicherungen
  (`system/hochladen.py`, gemeinsam für Sicherung/Paket/OCR, Arten getrennt: ein Paket lässt sich nicht als Sicherung
  einlesen und umgekehrt); `POST /api/system/hochladen/` `{"art": "paket"|"ocr", "name", "groesse"}`, `PUT …/<upload>/
  ?versatz=N`, `DELETE …/<upload>/`, `POST …/<upload>/einspielen/`. Agent `epm_paket`: kopiert die Datei in einen nur
  für root beschreibbaren Ordner (das Backend kann sie danach nicht mehr ändern), berechnet die SHA-256 (steht in der
  Ausgabe zum Vergleich mit der Test-VM), prüft das tar (nur `TAG`, `VERSION`, `SHA256SUMS`, `SHA256SUMS.sig`, `paket-signatur.pub`, `images.tar`,
  `rollout/…`, `werkzeuge/…`; keine Verweise, keine absoluten Pfade, kein „..“), dann `epm-update --paket … --ohne-tests`
  (prüft zuerst die Signatur gegen `/etc/epm/paket-vertraut.pub`; fehlt er, gegen den mitgelieferten
  `paket-signatur.pub`, der dann übernommen wird – siehe README –, dann die Prüfsummen, sichert, stellt um).
  `POST /api/system/pakete/schluessel/zuruecksetzen/` (Rolle Admin, Passwort + 2FA) bzw. `…/behalten/`: Agent
  `paket_schluessel_zuruecksetzen` legt den Antrag unter `/etc/epm/paket-vertraut.zuruecksetzen` ab und löscht den
  Schlüssel erst 24 h später (Statuslauf); bis dahin Hinweis an alle Benutzer, Ereignisse im Audit-Log (`paket_schluessel`). `epm_paket_erstellen` (`POST /api/system/pakete/erstellen/`): `epm-update
  --paket-erstellen`, Paket 2 Stunden unter `system/download/`; `GET /api/system/pakete/<datei>/` (X-Accel, Audit-Log).
- **F179h OCR-Modelle einspielen** (Software): Upload Art `ocr`, Agent `ocr_modelle` prüft den Inhalt (`modelle.json`,
  `dateien/…`) und ruft `epm-ocr-modelle einspielen` auf; Vorrat auf dem Server und Stand im Image werden angezeigt.
- **F179i Zertifikat** (Zertifikat): Inhaber, Namen, Aussteller, Ablauf, eigene CA/selbst signiert (Agent liest
  `nginx/certs/epm.crt` mit openssl), Stammzertifikat `/epm-ca.crt` zum Herunterladen. `POST /api/system/zertifikat/
  erneuern/` (nur mit eigener CA; `epm-zertifikat erneuern`), `POST /api/system/zertifikat/importieren/`
  `{"zertifikat", "schluessel", "ca"?}` als PEM: Backend prüft Lesbarkeit, Schlüssel passt, Kette zur CA
  (cryptography); Zertifikat, Schlüssel und CA nur in der Auftragsdatei (`geheim`, 0600) – im Audit-Log nur Inhaber,
  Aussteller, Ablauf, Fingerabdruck. Agent schreibt sie in einen temporären Ordner (0700) und ruft `epm-zertifikat
  importieren` auf.
- **F179j Protokolle** (nur lesend): backend, web, ocr, db (`docker compose logs --tail N`), Systemagent, nächtliche
  Sicherung, Übertragung (`journalctl -u …`), letztes Update (`/var/log/epm-update.log`); 100/500/2000 Zeilen.
  `POST /api/system/protokolle/` `{"quelle", "zeilen"}` → Agent `protokoll` legt den Text unter
  `status/protokolle/<Auftrag>.log` ab (0640, Gruppe des Backends, nach 1 Stunde gelöscht) – **nicht** in der
  Datenbank; `GET /api/system/protokolle/<kennung>/` (`?herunterladen=1` als Datei, Audit-Log). Filter in der Oberfläche.
- **F179k Status erweitert**: Versionen, Pakete, Zertifikat, Uhrzeit/NTP (`timedatectl`), OCR-Vorrat, vorhandene
  Werkzeuge; „Neustart nötig“ und Speicher wie bisher.
- **Begriffe**: „Passwort“ statt „Kennwort“ in den sichtbaren Texten von Benutzer, System, Backup, Startseite
  (Administration), Hilfe Administration/Backup; Erklärungen beim Draufzeigen für Systemagent, Container, CA,
  Update-Paket, Übertragungsziel (`lib/begriffe.ts`).
- **Teststatus:** Backend `system/test_verwaltung.py` (Mehrfach-Löschen: Rechte, Validierung, Pfadtricks, jüngste,
  Agent nicht erreichbar, Audit-Log; echter Agent löscht echt und folgt keinem Verweis; Probeläufe aller neuen Aktionen;
  Uploads mit Inhaltsprüfung inkl. Verweis/„..“/fremder Datei; Zertifikat-Import ohne Schlüssel in der Datenbank;
  Protokolle; Stand im Status) – 112 Tests `system accounts audit` lokal grün. Browsertests `system.spec.ts` (neuer
  Test Systemverwaltung) lokal grün gegen Vite + Django + Agent im Probelauf; `zzz-sicherung.spec.ts` (neuer Test
  Mehrfach-Löschen) braucht den CI-Stack.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

- **F179l Zeitplan der nächtlichen Sicherung** (Nachtrag 10.10.2026; Backup › Sicherungen, „Zeitplan … Ändern“):
  Uhrzeit (HH:MM) und täglich/werktags; `POST /api/backup/zeitplan/` `{"uhrzeit", "tage", "kennwort", "code"}` (Recht
  „Sicherungen verwalten“, Passwort + 2FA). Agent `sicherung_zeitplan` schreibt das Drop-in
  `/etc/systemd/system/epm-backup.timer.d/zeitplan.conf` (`OnCalendar=` leeren, dann `*-*-* HH:MM:00` bzw.
  `Mon..Fri *-*-* HH:MM:00`), `systemctl daemon-reload`, Timer neu; der Status meldet den Zeitplan, die Seite zeigt
  ihn und „nächste“. Warnung, wenn das Übertragungsfenster mehr als 3 Stunden nach der Sicherung öffnet oder kurz
  danach endet (`sicherung.zeitplan_hinweis`, gleich im Dialog). Bleibt auch mit `--sicherung-echt` ein Probelauf.
- **F179m Speicher aufräumen** (System › Wartung): Journal-Belegung (`journalctl --disk-usage`, alle 15 Minuten) und
  Aufräumen mit fester Auswahl (`--vacuum-size` 100M/200M/500M/1G, `--vacuum-time` 2 Wochen bis 6 Monate; einfache
  Rückfrage; `POST /api/system/journal/aufraeumen/`). Alte Versionen: Image-Dateien `images/epm-<TAG>.tar`, Update-Pakete
  `images/epm-paket-<TAG>.tar` und Docker-Images `epm-backend/epm-web:<TAG>` mehrfach auswählbar löschen
  (`POST /api/system/images/loeschen/` `{"dateien", "tags", …}`, Passwort + 2FA). Die laufende und die vorherige
  Version (für „Zurückschalten“) sind geschützt – im Backend und im Agenten; ist die laufende Version nicht bekannt,
  wird nichts gelöscht. Docker-Images werden ohne `-f` entfernt (ein benutztes lehnt docker ab).
- **F179n Uhrzeit einstellen** (System › Wartung): Zeitzone (Allowlist aus `timedatectl list-timezones`), NTP an/aus,
  bis zu 4 Zeitserver (Name oder IP, streng geprüft; für den abgeschotteten Betrieb z. B. die OPNsense) – je nach
  Server als chrony-Quelle (`/etc/chrony/sources.d/epm.sources`, öffentliche Pools aus/wieder an) oder
  systemd-timesyncd-Drop-in (`/etc/systemd/timesyncd.conf.d/epm.conf`), wie `rollout/01-basis.sh`; bei
  ausgeschaltetem NTP Uhrzeit von Hand (`timedatectl set-time`) mit Warnung. Abweichung Server–Browser wird angezeigt.
  `POST /api/system/uhr/` `{"zeitzone"?, "ntp", "server", "zeit"?, …}`, Passwort + 2FA.
- **F179o OCR-Modelle einspielen** jetzt mit Passwort + 2FA wie das Update-Paket.
- **Teststatus Nachtrag:** `system/test_verwaltung.py` Klasse `Nachtrag` (Prüfung der Eingaben, Rechte, Drop-ins für
  Timer, timesyncd und chrony in eigenen Ordnern, Schutz der laufenden und vorherigen Version, echter Agent im
  Probelauf); Browsertests `system.spec.ts` (Wartung: Journal, geschützte Versionen, Uhrzeit – lokal grün) und
  `zzz-sicherung.spec.ts` (Zeitplan, braucht den CI-Stack). Agent Version 6.

**Bewusst nicht umgesetzt (Empfehlungen):**
- *Protokolle ohne Patientendaten*: Container-Protokolle können in Fehlermeldungen Inhalte enthalten; sie werden
  deshalb nur auf Anforderung gelesen, nicht gespeichert und nach 1 Stunde gelöscht. Eine Maskierung (Namen,
  Geburtsdaten) wäre unzuverlässig und ist nicht eingebaut.
- *Update-Pakete signieren*: Die Prüfsummen im Paket schützen vor Beschädigung, nicht vor einem untergeschobenen Paket.
  Schutz heute: nur mit Recht Systemverwaltung, Passwort + 2FA, SHA-256 zum Vergleich. Empfehlung: Signatur mit einem
  Schlüssel der Test-VM, den der VPS kennt.

## X · Vorlagen-Portal einfacher (10.10.2026)

Wunsch: „Erweitere das Vorlagen-Portal um eine intuitivere Bedienung für Praxismanager und Krankenschwestern.“
Zielgruppe: Pflegekräfte ohne IT-Erfahrung und ein Praxismanager mit IT-Erfahrung.

### F180 Vorlagen in Alltagssprache, geführter Ablauf, Angaben per Klick, frühere Fassung, Kopie
- **Prüfung vorher (Stolperstellen):** Startseite der Vorlagen war direkt der Briefkopf; zwölf Dokumentvorlagen als
  eine lange Knopfreihe ohne Erklärung, wofür sie sind und wo sie benutzt werden („Bericht“ und „Unterlagen für die
  Sprechstunde“ waren gar nicht erreichbar); Begriffe Entwurf/Version/Veröffentlichen/Baustein/Datenfeld; Platzhalter
  als `{{Patient.Briefanrede}}` in Schreibmaschinenschrift; Datenfeld einfügen ging nur nach vorherigem Klick ins
  Textfeld, sonst passierte nichts; Vorschau nur im Dialog; „laden“ einer Version ohne Hinweis, dass danach noch
  gespeichert und veröffentlicht werden muss; Auswahllisten ohne Hinweis, wo sie benutzt werden; Reihenfolge nur per
  Ziehen/Tastatur (am Tablet schwer).
- **Vorlagen › Übersicht** (neue Startseite, Adresse `/admin/vorlagen`): Kacheln „Briefe, Formulare und E-Mail-Texte“,
  „Briefkopf und Logo“, „Medikamente und Präparate“, „Auswahllisten“, „Labor und Diagnosen“, „Grenzwerte und
  Fristen“, „Anlagen für E-Mails“ – je mit „Wofür?“, „Wo benutzt?“ und dem Namen im Menü. **Suche** „Was möchten Sie
  ändern?“ über Vorlagen, Listen, Präparate, Einträge und Anlagen. Hinweis auf Vorlagen mit noch nicht freigegebenen
  Änderungen. Jeder Bereich hat eine Adresse (`?bereich=listen&liste=vitamine`), „Zurück“ im Browser funktioniert.
- **Dokumentvorlagen:** zuerst die **Liste** aller Vorlagen nach Gruppen (Briefe und E-Mails an Patienten, Eigene
  Vorlagen, Pläne/Berichte/Unterlagen, Vordrucke zum Datenschutz) mit Beschreibung, „Wo benutzt“ und Stand („in
  Gebrauch · Fassung n“, „Änderungen noch nicht freigegeben“, „Mustertext, noch nicht geprüft“, „deaktiviert“);
  Suche. Im Editor (`?art=…`) Kopf mit Name, Zweck und Ort, **geführter Ablauf** „1 · Bearbeiten → 2 · Vorschau prüfen
  → 3 · Freigeben“; **Live-Vorschau** (echte PDF mit wählbarem Testpatienten und E-Mail-Text) in der Mitte neben den
  Eigenschaften, folgt jeder Änderung nach 0,7 s; der Freigabe-Dialog weist darauf hin, wenn der Stand noch nicht in
  der Vorschau zu sehen war. In der Oberfläche heißt eine Version jetzt **Fassung** und Veröffentlichen
  **Freigeben**; Baustein/Block heißen **Abschnitt** (API und Audit-Log unverändert).
- **Angaben aus der Akte per Klick:** Feldeinfüger mit lesbaren Namen nach Gruppen (Patient, Termin, Absender …) und
  Suche; ein Klick fügt auch ohne vorheriges Hineinklicken ins erste Textfeld des markierten Abschnitts ein (an der
  Schreibmarke, wenn schon hineingeklickt wurde). Platzhalter erscheinen auf der Seite und unter dem Textfeld als
  lesbare Chips („Briefanrede“), unbekannte rot.
- **Frühere Fassung ansehen/wiederherstellen:** „ansehen“ zeigt die PDF der Fassung mit Testpatient, „wiederherstellen“
  übernimmt sie als gespeicherten Entwurf (Notiz „wiederhergestellt aus Fassung n“); in Gebrauch erst nach Freigeben.
- **Als eigene Vorlage kopieren** (Schreiben außer der Patientenankündigung): neue eigene Vorlage (F176) mit Text und
  Aufbau der Fassung in Gebrauch, sofort in der Akte wählbar; mit Termin, wenn die Vorlage Termin-Angaben benutzt.
- **Auswahllisten:** Gliederung „Präparate für Infusionspläne“ / „Weitere Auswahllisten“, je Liste „Wo benutzt“,
  ▲ ▼ je Zeile für Tablet und Telefon, Suche in langen Listen, „wird angeboten“/„ausgeblendet“ mit Erklärung
  „Ausblenden statt löschen“. Kleine **„?“-Erklärungen** an Aufbau, Fassungen, Angaben und Auswahllisten.
- **Verlassen mit ungespeicherten Änderungen** an einer Dokumentvorlage fragt nach – auch bei „Zurück“, anderer
  Vorlage, anderer Seite (React Router `useBlocker`) und beim Schließen/Neuladen des Fensters (`beforeunload`).
- **Nebenbei behoben:** PDF-Anzeigen zeigten „Anzeige nicht möglich: … ArrayBuffer … already detached“, wenn pdf.js
  dieselben Daten ein zweites Mal lud (der Puffer geht an den Worker) – im Entwicklungsmodus (StrictMode) bei jeder
  Vorschau mit `laden`; `components/PdfAnsicht.tsx` gibt pdf.js jetzt eine Kopie.
- **Endpunkte:** `GET /api/vorlagen/` und `/api/vorlagen/{art}/` liefern zusätzlich `gruppe`, `wofuer`, `wo`, je
  Datenfeld `bezeichnung` und `gruppe` (`vorlagen/portal.py`; `felder.py` unverändert).
  `POST /api/vorlagen/{art}/versionen/{n}/wiederherstellen/` (ersetzt einen vorhandenen Entwurf, geprüft mit
  `pruefe_bloecke`, Audit-Log „Fassung n als Entwurf wiederhergestellt“).
  `POST /api/vorlagen/{art}/duplizieren/` `{"name", "beschreibung"?, "mit_termin"?}` → 201 mit der Übersicht der neuen
  eigenen Vorlage; 400, wenn die Vorlage Datenfelder oder Tabellen enthält, die eigene Schreiben nicht kennen.
  Keine Migration.
- **Teststatus:** `vorlagen/test_portal.py` (5 Tests: Beschreibungen, lesbare Felder, Wiederherstellen mit Rechten und
  Ersetzen des Entwurfs, Kopieren, Kopieren nur mit erlaubten Feldern). Browsertests angepasst
  (`dokumentvorlagen.spec.ts`, `admin.spec.ts`, `mobil.spec.ts`, `zz-neustart.spec.ts`) und neu „Vorlagen-Portal:
  Suche, Angabe per Klick, geführter Ablauf, frühere Fassung, Kopie als eigene Vorlage“; lokal gegen Vite + Django
  (PostgreSQL 16) grün, Lauf im CI steht aus.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

## Z · Texterkennung lernt mit (10.10.2026)

Auftrag: Die Texterkennung (F160 ff.) soll aus den Korrekturen der Pflegekräfte lernen – Stufe 1, feste Regeln statt
Sprachmodell, komplett offline. Dazu der Zusatzauftrag, den Patienten aus dem Scan zu erkennen. Die Prüfung, ob EPM
zur Laufzeit etwas nach außen schickt, steht in `docs/OFFLINE-BETRIEB-2026-10-10.md`.

### F182 Texterkennung lernt aus Korrekturen (gelernte Zuordnungen, Kennzahl, offline)
- **Lernen beim Übernehmen** (`scans/lernen.py`, `aus_zuordnung`): `POST /api/scans/{id}/zuordnen/` nimmt zusätzlich
  `herkunft` = `{"labor": [{"index": Nr. der erkannten Zeile | null, "stelle": {seite, box} | null}, …], "bia":
  {feld: {seite, box} | null}, "diagnosen": [Nr. | null, …]}` (die Oberfläche schickt es mit). Verglichen wird, was
  erkannt und was übernommen wurde; gelernt werden
  - erkannte Bezeichnung → gewählter Laborparameter (auch bei Zeilen, die nur als Freitext erkannt wurden),
  - Lesefehler in Bezeichnungen (ähnlich gelesen, z. B. „Kreatimin“ → Kreatinin; bei Diagnosen Bezeichnung und Code),
  - von Hand ergänzte Labor- und BIA-Werte: die Bezeichnung links neben der im Bild angeklickten Zahl
    (`auswertung.etikett_an`), z. B. „Aktive Zellen“ → BCM,
  - je Absender (erkannter `labor_name`) die Spaltenlage der Werte (linke Kante, Zeichenbreite; ab drei
    linksbündigen, unverändert übernommenen Werten).
  Gespeichert wird je Absender und allgemein (`GelernteZuordnung`: Art, Quelle, erkannter Text normalisiert und wie
  gelesen, Ziel, Bestätigungen, erstmals/zuletzt am, zuletzt von, gesperrt, Lesefehler). Wird eine gelernte
  Zuordnung nicht übernommen, verliert sie eine Bestätigung (bei 0 entfällt sie). Testzugänge lernen nicht mit.
- **Keine Patientendaten:** kein Bezug zu Patient, Scan oder Dokument, keine Werte, keine Namen. Bezeichnungen mit
  Datum, langen Zahlen, Wörtern zur Person („Name“, „geb.“, „Patient“, „Straße“ …) oder dem Namen des Patienten
  werden verworfen (`lernen.zulaessig`). Darum bleibt das Gelernte, wenn Scans, Dokumente oder Akten gelöscht werden;
  es ist in der Datensicherung (pg_dump der ganzen Datenbank). „Datenbank leeren“ soll es mit leeren:
  `scans.lernen.leeren()` steht bereit, der Aufruf in `system/leeren.py` fehlt noch (Bereich eines anderen Auftrags,
  siehe Unklarheiten U74).
- **Anwenden** (`auswertung.Gelerntes`, `_suche_parameter`): Reihenfolge sicher Gelerntes (erst dasselbe Labor, dann
  allgemein) → Katalog und Suchbegriffe → gelernter Vorschlag → ähnliche Schreibweise. Ab `SCHWELLE` = 2
  Bestätigungen ist eine Zuordnung sicher (vorgewählt, Hinweis „gelernt: so schon n-mal übernommen“), darunter nur
  Vorschlag (`zuordnung: "gelernt_vorschlag"`, nicht vorgewählt, Kennzeichen „gelernt?“). Gesperrte Zuordnungen
  („nie wieder so zuordnen“) fallen auf jeder Stufe weg, auch bei Synonymen und Ähnlichkeit; allgemein gesperrt gilt
  für alle Labore. Gleiches für BIA-Felder und Diagnosen (sicher: korrigierte Bezeichnung und Code eingesetzt;
  Vorschlag: Knopf „„…“?“ in der Prüfansicht). Die gelernte Spaltenlage hilft, wenn auf einer Seite zu wenige Werte
  stehen, um die Spalte selbst zu finden (Pfeil vor dem Wert, als „1“ gelesen). Häufig bestätigte Bezeichnungen (ab
  2, ohne Lesefehler) kommen in die Wörterliste für Tesseract (`--user-words`). In die Akte kommt weiterhin nichts
  ohne Bestätigung.
- **Verwalten:** Scans › „Gelernte Zuordnungen“ (`/scans?bereich=gelernt`): Liste mit Suche, Filter nach Art und
  Labor, Sperren/Entsperren, Löschen (mit Rückfrage), Erklärung in einfacher Sprache. API: `GET /api/scans/gelernt/
  ?suche=&art=&quelle=` (`allgemein` = nur allgemeine), `PATCH /api/scans/gelernt/{id}/ {"gesperrt": bool}`,
  `DELETE /api/scans/gelernt/{id}/`; beides im Audit-Log (nur Bezeichnung und Ziel). Recht „Scans“ oder „Vorlagen
  pflegen“; Testzugänge nur lesen.
- **Messen:** Kennzahl „Wie oft musste korrigiert werden“ (`KorrekturZaehler` je Monat und Art: übernommene und davon
  geänderte oder von Hand ergänzte Werte; nur Zahlen). `GET /api/scans/kennzahl/` → 12 Monate, aktueller Monat,
  Vormonat, Trend in Prozentpunkten. Unten in der Scan-Liste „korrigiert im Okt.: 33,3 % ▼ 16,7“, ein Klick öffnet die
  große Ansicht (Säulen je Monat, Tabelle je Art).
- **Komplett offline:** EPM nutzt weder PaddleOCR noch PaddleX (die Modelle werden als ONNX mit onnxruntime gelesen),
  es gibt keinen Programmteil, der Modelle laden könnte. Zusätzlich setzt `paddle.offline_erzwingen()` die Schalter
  gegen Downloads und Telemetrie (Hugging Face, PaddleX), `EPM_OCR_MODELLE` muss ein Verzeichnis sein, `_sitzung`
  öffnet nur vorhandene Dateien. Tesseract liest nur `EPM_TESSDATA` (im Image: deutsches Modell aus dem Repo, osd aus
  dem Paket). Test `OfflineTest` erkennt eine Seite, während jeder Netzwerkzugriff verboten ist – mit PP-OCR, falls
  die Modelle da sind, und ohne (nur Tesseract).
- **Teststatus:** `scans/test_lernen.py` (Anwenden je Labor vor allgemein, Schwelle, Sperren/Löschen, Lernen beim
  Übernehmen, von Hand ergänzte Werte, Diagnose/BIA, keine Personendaten, Testzugang, Kennzahl, Verwalten und
  Rechte, Leeren, Offline) und die übrigen Tests von `scans`, `befunde`, `system`, `hilfe` grün (155 Tests,
  nacheinander; mit `--parallel` bricht der Testrunner hier schon an `scans.test_dokumente` ab – nicht übertragbarer
  Traceback, unabhängig von F182); lokal ohne PP-OCR-Modelle (kein Zugang zu huggingface.co), d. h. Erkennung nur mit
  Tesseract. `npm run typecheck` und `npm run build` grün.
  **Browsertests: Lauf steht aus.**
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F183 Scan erkennt den Patienten
- **Lesen:** `auswertung.patient_hinweise` liest zusätzlich Namen nach „Patient:“, „Name:“, „Frau“, „Herr“, „über“,
  „Versicherte(r)“ … (`namen`); Geburtsdaten wie bisher (auch „26.11.1970 ♀ 54 Jahre“, siehe `fusion.datum_und_alter_trennen`).
- **Vorschlagen** (`dienst.patient_vorschlaege`, im `GET /api/scans/{id}/` als `vorschlaege`): nur Akten aus
  `patienten_fuer` (Testzugang nur Testpatienten, eingeschränkte Akten nicht). Nachname und Vorname exakt oder mit
  Lesefehlern (1 Fehler ab 4, 2 ab 8 Zeichen, nur unter den gelesenen Namen), Geburtsdatum exakt als starkes Merkmal;
  passt das Geburtsdatum im Dokument nicht, sinkt der Treffer. Je Vorschlag `stufe`: „sicher“ (Name und
  Geburtsdatum), „wahrscheinlich“, „unsicher“; `grund` in Worten („Name und Geburtsdatum erkannt“, „Name ähnlich
  gelesen („Musler“)“, „Geburtsdatum im Dokument passt nicht“).
- **Oberfläche:** oben in der Scan-Ansicht und beim Zuordnen „Wahrscheinlich: Erika Muster, geb. 14.03.1968 –
  übernehmen?“ mit Begründung; mehrere Treffer als Auswahl, unsichere nur als Hinweis. Nie automatisch: Der Patient
  wird erst mit einem Klick gewählt (die frühere Vorauswahl beim Öffnen von „Zuordnen“ entfällt), in die Akte erst
  mit „In die Akte legen“.
- **Datenschutz:** Die Hinweise bleiben im Server (nicht in der Antwort), werden nicht gelernt und nicht protokolliert –
  außer im bestehenden Audit-Eintrag beim Zuordnen.
- **Teststatus:** exakter Treffer, Lesefehler im Namen, zwei Gleichnamige mit verschiedenem Geburtsdatum, fremde
  (eingeschränkte) Akte und Testzugang, kein Treffer (`PatientErkennenTest`) grün. **Browsertests: Lauf steht aus.**
### F189 Erkennung verbessern: falsch erkannt anmerken, richtigen Bereich markieren
- **Falsch erkannt** (`POST /api/scans/{id}/falsch/` `{"art": "labor"|"bia"|"diagnose", "index": Nr. bzw. BIA-Feld,
  "grund": "falsche_zeile"|"falscher_wert"|"gehoert_nicht_dazu"}`, `lernen.falsch_erkannt`): In der Prüfansicht hat
  jede erkannte Labor-Zeile, jeder BIA-Wert und jede Diagnose den Knopf „Falsch erkannt“ mit Grund. Wirkt sofort (die
  Zeile verschwindet, im Scan als `verworfen` markiert, bleibt es auch bei neuer Auswertung) und lernt:
  - *gehört nicht dazu* (Kopfzeile, Referenzbereich, Datum): Bezeichnung für diesen Absender „nicht auswerten“
    (`GelernteZuordnung.Art.IGNORIEREN`, gilt ab der ersten Anmerkung, nur für dieses Labor bzw. ohne Labor allgemein);
  - *falsche Zeile*: gelernte Zuordnung verliert eine Bestätigung; eine nur ähnlich geratene (bzw. ein BIA-Feld) wird
    für diesen Absender gesperrt; ein exakter Katalogtreffer bleibt (meist ist dann die Zeile verrutscht);
  - *falscher Wert*: nichts gelernt.
  Gezählt als `verworfen` in der Kennzahl (`KorrekturZaehler.verworfen`). Keine Patientendaten: Bezeichnungen mit
  Wörtern, die im Dokument als Name gelesen wurden (F183-Hinweise), Datum oder Angaben zur Person werden nicht
  gelernt. Audit-Log nur mit Art und Grund, ohne Inhalt. Testzugänge und pausiertes Lernen: verwerfen ja, lernen nein.
- **Richtigen Bereich markieren** (`POST /api/scans/{id}/seiten/{sid}/ausschnitt/` `{"box": [x, y, b, h]}` relativ
  0–1, `dienst.bereich_lesen`, `scans/ocr/ausschnitt.py`): Knopf „Bereich markieren“ beim Laborbefund, dann Rahmen im
  Bild aufziehen – mit Maus oder Finger (Pointer-Ereignisse mit `touch-action: none`, Koordinaten relativ zur
  angezeigten Größe, also auch bei Zoom richtig; abgebrochene Touch-Gesten verwerfen den Rahmen). Der Server liest nur
  diesen Ausschnitt mit Tesseract: Rand dazu, auf etwa 40 px Texthöhe vergrößert (höchstens 4-fach), psm 7 bei einer
  Zeile, sonst psm 6 (Tabelle, jede Zeile ein Vorschlag), Fachwörterliste wie sonst; offline, im Backend. Die Lage
  wird auf die ganze Seite zurückgerechnet. Die Zeilen kommen **hinten** an `auswertung.labor.werte` (die Nummern der
  übrigen Vorschläge bleiben, die Prüfansicht fügt sie an) und in `ScanSeite.info["zusatz"]` (bleiben bei neuer
  Auswertung; „Erneut erkennen“ verwirft sie). Ohne erkennbaren Wert erscheint der gelesene Text als Freitext, nicht
  vorgewählt. Grenzen: Rahmen mindestens 1 % breit, innerhalb der Seite (über den Rand wird begrenzt), keine
  unendlichen Werte, Seite erkannt, Scan nicht in Arbeit; Recht „Scans“, nur sichtbare Scans. Fehlt Tesseract: 503
  mit verständlicher Meldung. Die Klick-ins-Bild-Funktionen (F169, „+ Wert“) bleiben für einzelne Werte.
- **Bereich lernen:** Werden Werte aus einem markierten Bereich übernommen, merkt sich EPM den Bereich je Absender
  (`Art.BEREICH`, nur Lage `bereich` = [x, y, b, h], ähnliche Bereiche ab 50 % Überdeckung werden gemittelt). Ab der
  Schwelle liest der OCR-Dienst beim nächsten Befund dieses Labors den Bereich von sich aus nach
  (`dienst.bereiche_nachlesen` nach der Erkennung) – die Auswertung findet die Werte dann dort.
- **Steuerung des Lernens** (`GET|PATCH /api/scans/gelernt/steuerung/`, Modell `LernEinstellung`): „Lernen
  pausieren“ (nichts Neues lernen, Gelerntes weiter anwenden, Kennzahl weiter zählen) und „Sicher ab“ 1–3
  Bestätigungen (`lernen.schwelle()`, gilt für Anwendung, Wörterliste und Bereiche). Ändern nur mit „Vorlagen pflegen“
  (keine Testzugänge), im Audit-Log (`lernen_gesteuert`, vorher/nachher). Zusammengefasst, wer was darf: lernen tut jedes
  Zuordnen mit Recht „Scans“ (Testzugänge nie); ansehen, sperren, löschen mit „Scans“ oder „Vorlagen pflegen“;
  pausieren und Schwelle mit „Vorlagen pflegen“; die Kennzahl zeigt, ob es besser wird.
- **Anleitung:** Hilfe › Scans „So verbessern Sie die Erkennung“ (vier Schritte mit Beispielen) und „Wer darf was?“;
  in Zuordnen der einmal eingeblendete Hinweis „So helfen Sie EPM, besser zu lesen“ (wegklickbar, über „Besser lesen
  helfen“ wieder aufrufbar); unter „Gelernte Zuordnungen“ der Kasten „Falsches korrigieren“; Begriffe „Texterkennung“
  und „gelernt“ in `lib/begriffe.ts`; Blatt zum Ausdrucken `docs/SCANS-VERBESSERN.md`.
- **Teststatus:** `scans/test_verbessern.py` (Ausschnitt wirklich mit Tesseract gelesen: Tabelle zeilenweise, Werte,
  Lage innerhalb des Rahmens; Grenzen, Rechte, fremde Seite; Bereich gelernt und beim nächsten Befund nachgelesen;
  „falsch erkannt“: ignorieren je Labor, sperren, Bestätigung weniger, falscher Wert, BIA, Diagnose, keine
  Personendaten, pausiert, Testzugang, Fehler; Steuerung mit Recht, Grenzen und Audit-Log) grün, dazu `scans` und
  `befunde` (`--parallel 1`). Browsertests in `scans.spec.ts` ergänzt (falsch erkannt, Bereich mit Maus und mit
  Touch-Ereignissen, Steuerung) – **Lauf steht aus** (hier kein Docker).
- **Status:** ABGESCHLOSSEN – Lauf steht aus

## Y · Akte entschlankt (10.10.2026)

Wunsch: „Vor allem soll die Patientenakte deutlich entschlankt werden. Unterpunkte wie Diagnosen, Therapien und
Empfehlungen sowie die Infusionspläne sollen einfacher erreichbar sein. Im besten Fall muss man auf der Seite nicht
scrollen. Beim Infusionsplan sollen die PDFs einfach einsehbar sein, und die Pläne sollen sich nach den Vorgaben der
Praxis erstellen lassen.“ Befunde, Messung vorher/nachher und Rückfragen: `docs/UI-UX-AKTE-2026-10-10.md`.

### F181 Akte ohne Seiten-Scrollen, PDF neben dem Plan, Plan nach Praxisvorgabe
- **Kopf (Ansicht „Kopfzeile“, Stufe „Alle Angaben“):** Name, Nummer, Geschlecht (Buchstabe, ausgeschrieben im Tooltip),
  Geburtsdatum und Knöpfe in einer Zeile; vier Kennzahlen zweizeilig; Versorgung/Hinweise eine Zeile, unter 1280 px
  hinter „Versorgung und Hinweise ▾“. Knopf **Dokument** im Kopf (vorher „⋯ › Dokument hochladen …“). Gruppen und
  Testkennungen (`kennzahlen`, Gruppen „Ernährung“, „Versorgung“ …) unverändert. Bei 1366 × 768 endet der Kopf bei
  258 px statt 346 px.
- **Reiter:** Übersicht, Diagnosen, Therapie, Empfehlung, Infusionspläne, Kontakte groß; Labor, BIA, Berichte,
  Dokumente kleiner nach einem Strich; Verlauf und Datenschutz klein am rechten Rand. Alle bleiben eigene Reiter
  (F121); Alt+Ziffer folgt der neuen Reihenfolge.
- **Fenster füllen (ab 1024 × 600 px, seit F190 ab 1280 × 600 px):** `Seite fuellen` (Shell) begrenzt die Seite auf die Fensterhöhe; unter den
  Reitern liegt `.akte-flaeche`, die bei Bedarf scrollt; Reiter mit zwei Spalten (`.akte-spalten`: Diagnosen,
  Therapie, Empfehlung, Kontakte, Infusionspläne, Labor, BIA, Berichte, Dokumente, Datenschutz) scrollen ab 1280 px je
  Spalte. Kopf und Reiter bleiben stehen. Darunter (Telefon, Tablet hochkant) scrollt die Seite wie bisher.
- **Übersicht:** sechs Karten statt neun (Gewicht · Aktueller Infusionsplan · Diagnosen, Therapie, Empfehlung ·
  Kontakte und Termine · Labor und BIA · Personen und Anschrift). Spalten nach der tatsächlichen Breite (1366 px: 3,
  1920 px: 4); im Fenster zwei Reihen mit fester Höhe (`--raster-zeile` aus der verfügbaren Höhe, auf das 8-px-Raster
  gerundet), Inhalt scrollt in der Karte. Größe je Karte weiter über das Menü (je Person); Standardhöhe im Fenster
  1 Zeile. Gewichtsdiagramm zeichnet in der echten Größe (`GewichtsDiagramm masse`). Plan-Karte mit „PDF ansehen“ und
  Hinweis auf einen offenen Entwurf.
- **Akte › Infusionspläne:** PDF in voller Spaltenhöhe neben der Liste (`PdfLeser einpassen`: „Ganze Seite“, sonst auf
  die Breite, wenn die Seite sonst unter 360 px schmal wäre), „Groß ansehen“, „Herunterladen“; Herkunft
  (gespeicherte PDF mit Prüfsumme bzw. Ansicht mit aktiver Dokumentvorlage) darunter; Umschalter „Vergleich mit
  Vorgänger“ mit Zahl der Änderungen.
- **Menüpunkt Infusionspläne:** „PDF“ an jedem Plan (Entwürfe: `ansicht/`); ab 1920 px rechts neben der Tabelle.
- **Plan-Editor:** „Mengen nach Praxisvorgabe“ (je kg des letzten Gewichts wie im Altsystem, `GET …/vorbelegung/`) auch
  beim Folgeplan; Karte **Prüfung vor der Freigabe** (Gewicht vorhanden/≤ 3 Monate, seit F190 6 Monate und einstellbar, Präparat zu jeder Menge, Ca/Mg
  stabil, Infusionstage stimmig, Laufzeit, Protonenpumpenhemmer mit Zeiten); **PDF-Vorschau** mit den Eingaben im
  Formular auf jeder Bildschirmgröße (neuer Plan: einmal als Entwurf gespeichert).
- **Hinweise im Kopf (Nacharbeit 10.10.2026):** ein Hinweis steht direkt als Chip da; ab zwei Hinweisen ein Chip
  „N Hinweise ▾“ (rot und „· n überfällig“, wenn Überfälliges dabei ist), der die Liste mit den einzelnen Chips und
  ihrem „×“ aufklappt (Ausblenden über den RuheDialog, F119). Am Telefon stehen die Hinweise unter „Versorgung und
  Hinweise (N) ▾“. Gemessen mit einer Akte mit 5 Hinweisen und 3 fehlenden Erklärungen: 1366 × 768, 1920 × 1080 und
  1024 × 768 ohne Seiten-Scrollen (vorher auch, aber Kopf mit sieben Chips in zwei Zeilen, Ende bei 297 px; jetzt
  271 px, eine Chipzeile). `HinweisChipsKompakt` in `components/HinweisChips.tsx`; Browsertest `layout.spec.ts`.
- **Navigation:** Administration ab drei Seiten als Gruppe zum Aufklappen (`nav-administration`, gemerkt je Browser,
  auf `/admin…` offen); Routen unverändert.
- **PDF-Anzeige:** pdf.js als „legacy“-Fassung aus demselben Paket (keine neue Abhängigkeit) – mit der Standardfassung
  blieben Seiten in nicht ganz aktuellen Browsern (Chromium 141) beim Laden stehen.
- **Endpunkt:** `POST /api/infusionsplaene/{id}/vorschau/` – Body wie `PATCH`; nur Entwürfe (sonst 400), Recht
  „Infusionspläne anlegen“, Akte offen; Prüfung wie beim Speichern (400 mit Feldfehlern). Die Werte werden in einer
  Transaktion eingetragen, die PDF mit der aktiven Vorlage erzeugt (Wasserzeichen „ENTWURF“), danach wird
  zurückgerollt – keine Änderung, keine neue Fassung im Verlauf. Antwort `application/pdf`, Kopf
  `X-EPM-Vorlage-Version`. Keine Migration.
- **Teststatus:** Backend `infusionen.tests.PlanVorschau` (Vorschau zeigt die Eingabe, Datenbank und Verlauf
  unverändert, Wasserzeichen; Prüfung wie beim Speichern, ohne Recht 403, freigegebener Plan 400) – grün, alle
  `infusionen`-Tests grün (17). Browsertests angepasst: `layout.spec.ts` (neu: 1366 × 768 und 1920 × 1080 ohne
  Seiten-Scrollen, sechs Karten, Kopf bleibt stehen), `oberflaeche.spec.ts` (sechs Karten, Standardhöhe),
  `plaene.spec.ts` (PDF neben der Liste, Herunterladen, Groß ansehen), `dokumente.spec.ts` (Knopf „Dokument“),
  Administration aufklappen (`hilfen.adminNavigation` in `admin`, `system`, `aa-import`, `zz-neustart`,
  `zzz-sicherung`, `zzzz-leeren`), Begriffe in Beschriftungen (`akte`, `oberflaeche`, `praxiswuensche`). Lokal gegen
  Vite + Django (PostgreSQL 16, Chromium 141) grün: `layout`, `akte` (bis auf den Neustart über Docker),
  `aktenansicht`, `plaene`, `infusionsplaene`, `mobil`, `dokumente`, `praxiswuensche`, `oberflaeche` bis auf
  „Volle Breite: 1280 px“ (Startseite, Breite von `main` um die Scrollleiste zu klein – nicht von F181 berührt).
  CI-Lauf steht aus.
## AA · Automatisierungen für die Pflege (10.10.2026)

Ziel: Automatisierungen nehmen der Pflege Arbeit ab, versenden aber nie von allein etwas und schreiben nichts
ungefragt in die Akte – am Ende entscheidet immer ein Klick der Pflegekraft. Alles läuft offline.

### F184 Tagesliste „Heute zu tun“ (Startseite)
- **Oberfläche:** Bereich „Heute zu tun“ ganz oben auf der Startseite für alle mit „Akten lesen“ außer der
  Administration (deren Startseite bleibt unverändert). Kurze, priorisierte Liste mit Anzahl: Termine heute (Uhrzeit,
  Patient, Ort; „erledigt“ zum Abhaken), fällige oder überfällige Rückrufe und Wiedervorlagen (abhaken), Infoblatt an
  die Praxis fällig (Knopf „Infoblatt erstellen“, ersetzt den bisherigen Einzelhinweis aus F177), Terminbestätigung
  fehlt (F185, Knopf „Bestätigung vorbereiten“), überfällige Kontakte ohne geplanten Termin (Grenze aus den
  Einstellungen, zur gefilterten Patientenliste), Infusionspläne zur Prüfung, Scans zum Zuordnen (ersetzt „Scans
  warten auf Zuordnung“ im Scan-Hinweis; Warnungen zu Ablauf und Speicher bleiben dort), Praxistermine ohne Ort
  (Knopf „Ort eintragen“ öffnet den Termin) und fehlende Angaben (F186, je Regel „3 Akten ohne Telefonnummer“ mit Klick
  auf die gefilterte Liste). Je Gruppe höchstens drei Einträge, danach „… und n weitere“. Erledigtes verschwindet
  sofort; leer: „Für heute ist alles erledigt.“ Fachbegriffe (Wiedervorlage, Wiedereinbestellung) mit Erklärung
  (`Begriff`). Kacheln und Kennzahlen darunter bleiben, wie jede Person sie eingerichtet hat.
- **Endpunkt:** `GET /api/startseite/` liefert zusätzlich `tagesliste` (`patienten/api.py: tagesliste`):
  `termine_heute`, `rueckrufe` (+ `rueckrufe_anzahl`, `rueckrufe_ueberfaellig`), `kontakt_ueberfaellig`,
  `kontakt_monate`, `plaene_pruefen`, `fehlende_angaben` (Anzahl Akten je Regel), `gewicht_fehlt_monate`,
  `bestaetigung_fehlt` und `ohne_ort` (beide nur mit „Einträge erfassen“). Ohne Testpatienten (Testzugänge: nur
  Testpatienten) und ohne abgeschlossene Akten. Offene Scans holt die Oberfläche wie bisher aus `GET /api/scans/stand/`.
- **Teststatus:** `patienten/test_automatisierungen.py` › `Tagesliste` (Inhalt ohne Testpatienten und abgeschlossene
  Akten, Erledigtes verschwindet, Rechte, Testzugang, Einstellung). Browsertest `start.spec.ts` „Heute zu tun“.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F185 Terminbestätigung automatisch vorbereiten
- **Ablauf:** Speichert die Pflegekraft einen neuen Praxistermin oder verschiebt ihn (Datum, Uhrzeit, Ort, Art) für
  einen Patienten mit vollständiger Anschrift oder E-Mail-Adresse, fragt EPM direkt danach „Terminbestätigung an Frau
  X schicken?“ (`components/TerminBestaetigung.tsx`, aus `TerminDialog` – damit überall, wo Termine gespeichert
  werden: Startseite, Kalender, Akte). „Ja, Bestätigung vorbereiten“ öffnet „Schreiben und E-Mail“ (F172) mit Art
  „terminbestaetigung“ und genau diesem Termin; „Nicht jetzt“ schließt. Im Termin steht „Terminbestätigung: fehlt“
  bzw. „erstellt am …“ mit Knopf „Bestätigung erstellen“/„Erneut erstellen“.
- **Vermerk:** `Termin.bestaetigung_am`, `bestaetigung_von` (Migration `patienten/0016`). Gesetzt, wenn
  `POST /api/patienten/{id}/schreiben/` mit `art: "terminbestaetigung"` eine PDF oder E-Mail (.eml) erzeugt – nicht
  bei `ausgabe: "email"` (nur Text für den Dialog) und nicht bei „PDF ansehen“ (`vorschau: true`); nicht ohne
  Schreibrecht an der Akte (Admin bei echten Akten), nicht bei erledigten Terminen oder abgeschlossenen Akten. Im
  Verlauf der Akte als „Terminbestätigung erstellt“. Ändern sich Datum, Uhrzeit oder Ort, wird der Vermerk geleert.
- **Termin-API:** `TerminSerializer` liefert `bestaetigung_am`, `bestaetigung_von_name` und bei Praxisterminen
  `bestaetigung: {angebot, email, anrede}` (`angebot`: Einstellung an, Anschrift oder E-Mail, Termin offen und nicht
  vorbei, Akte in Betreuung).
- **Einstellung:** `Einstellungen.terminbestaetigung_anbieten` (Standard an, Migration `stammdaten/0019`), unter
  Vorlagen › Grenzwerte „Terminbestätigung“. Aus: keine Frage und keine Zeile in der Tagesliste.
- **Teststatus:** `test_automatisierungen.py` › `Terminbestaetigung` (Angebot, ohne Anschrift/E-Mail, Einstellung,
  Vermerk nach PDF/E-Mail und nicht nach Vorschau, andere Schreiben, Verschieben, Admin). Browsertest
  `kalender.spec.ts` „Terminbestätigung nach dem Speichern“.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

### F186 Fehlende Angaben melden
- **Regeln** (`patienten/luecken.py`), nur Akten in Betreuung, ohne Testpatienten: kein Arzt zugeordnet und kein
  Hausarzt im Freitext (`hausarzt`); weder Telefon noch Telefon 2 und keine aktive Kontaktperson mit Telefon/Mobil
  (`telefon`); keine Gewichtsmessung in den letzten X Monaten (`gewicht_fehlt`, Einstellung
  `gewicht_fehlt_monate`, Standard 3, 1–120, Vorlagen › Grenzwerte); keine aktive Diagnose und leeres Feld Diagnose
  (`diagnose`); offener Praxistermin in den nächsten 8 Wochen ohne Ort, nur wenn es den Terminort der Praxis gibt –
  wie beim Infoblatt (`termin_ort`, `infoblatt.praxisort`/`aufteilen`).
- **Anzeige:** als zusätzliche Hinweisarten in `kennzahlen` (Patientenliste mit „×“ zum Ausblenden für 3/6/12 Monate
  oder „nicht mehr nötig“, `Hinweisruhe.Art` erweitert, Migration `patienten/0016`); Detail einer Akte liefert im
  `kopf` jetzt `hinweise` und `hinweise_stumm` (zum Anzeigen mit `HinweisChips` im Aktenkopf – die Anzeige in der
  Akte selbst ist noch nicht eingebaut). Tagesliste: Anzahl je Regel (ausgeblendete zählen nicht), Klick auf
  `/patienten?pruefen=ohne_telefon|ohne_hausarzt|ohne_gewicht|ohne_diagnose|termin_ohne_ort`.
- **Teststatus:** `test_automatisierungen.py` › `FehlendeAngaben` (je Regel, Ausnahmen, Hinweis in Akte und Liste,
  Ausblenden, Filter) und `Einstellungsfelder`.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

## AB · Hinweise im Infusionsplan (10.10.2026)

Wunsch (Plan-Punkt 2, freigegeben): Beim Erstellen eines Plans soll sichtbar sein, was Labor und Gewicht seit dem
letzten Plan sagen – sachlich und **ohne Dosisvorschlag**.

> **Grenze zur Medizinprodukte-Verordnung:** Die Hinweise zeigen nur, was in der Akte steht, und bitten ums Prüfen. Sie
> schlagen nie eine Menge vor und berechnen keine Dosis. Eine Software, die aus Patientendaten Therapiemengen ableitet,
> wäre ggf. ein Medizinprodukt nach MDR (Regel 11). Neue Hinweise bitte ebenso formulieren („… bitte prüfen“, nie
> „… auf x erhöhen“). So steht es auch als Kommentar in `infusionen/hinweise.py` und `PlanEditor.tsx`.

### F187 Hinweise aus Labor und Gewicht im Plan-Editor
- **Ansicht:** Plan-Editor, rechte Spalte unter „Prüfung vor der Freigabe“: Karte **Hinweise aus Labor und Gewicht**
  (Begriff „Referenzbereich“ mit Erklärung). Am Telefon untereinander, lange Zeilen brechen um.
  - **Laborwerte außerhalb des Referenzbereichs** seit dem letzten Plan (Tag der Freigabe des Vorgängers bzw. des
    aktuellen Plans; ohne Plan: innerhalb „Laborbefund gilt als alt nach“), nur für Parameter, deren Bestandteil
    gerade im Formular vorkommt: Natrium, Kalium, Phosphat, Calcium, Magnesium → gleichnamige Parameter; Humanalbumin →
    Albumin; Glucose → Glucose; Lipide → Triglyceride; Spurenelemente → Kupfer, Zink, Selen, Mangan; Vitamine → Gruppe
    Vitamine. Text z. B. „Magnesium 0,58 mmol/l am 02.10.2026 – unter dem Referenzbereich (0,66–1,07). Bitte prüfen.“,
    Pfeil ↑/↓, darunter der **Verlauf der letzten drei Werte** mit Trend (steigend, fallend, gleichbleibend,
    schwankend). Referenz aus dem Wert, sonst aus dem Katalog (U44: im Katalog meist leer).
  - **Gewicht:** Änderung seit dem Bezugsplan (Gewicht, mit dem dessen Gesamtvolumen berechnet wurde) ab der Grenze
    „Warnung Gewichtsverlust“ (Standard 5 %), auf- und abwärts: „… von 60 auf 54 kg gesunken (−10 %). Mengen je kg und
    Gesamtvolumen bitte prüfen.“
  - **Eigene Pläne:** ein Bestandteil, der in den letzten drei freigegebenen Plänen jeweils erhöht bzw. verringert
    wurde („Kalium wurde in den letzten 3 Plänen jeweils erhöht (40 → 50 → 60 mmol) …“).
  - **Kein bzw. altes Labor** („Laborbefund gilt als alt nach“, F120): Hinweis mit **Blutuntersuchung anfordern**
    (öffnet „Schreiben und E-Mail“ der Akte, dort die Anlage „Blutuntersuchung“ anhaken) und **Schreiben
    „Blutuntersuchung“ ansehen** (Anlage aus F174).
- **Endpunkt:** `GET /api/infusionsplaene/hinweise/?patient=ID&plan=ID&bestandteile=natrium,kalium,…` →
  `{seit, bezug, bestandteile, hinweise: [{art: labor|labor_alt|gewicht|plaene, stufe, text, …}]}`; `plan` = der
  Entwurf (Bezug ist sein Vorgänger), `bestandteile` = was im Formular vorkommt (sonst aus Entwurf bzw. aktuellem Plan;
  unbekannte werden ignoriert). Lesen mit „Akten lesen“; Patient außerhalb des eigenen Bereichs (z. B. Testzugang und
  echte Akte) bzw. fremder Plan → 400. Keine Migration, keine Speicherung.
- **Dateien:** `backend/infusionen/hinweise.py`, `infusionen/api.py`, `frontend/src/seiten/akte/PlanEditor.tsx`
  (`HinweiseAusLabor`), `lib/begriffe.ts` (`referenzbereich`), `seiten/akte/Akte.tsx` (`schreibenOeffnen`).
- **Teststatus:** Backend `infusionen.tests.PlanHinweise` (6 Tests: außerhalb des Referenzbereichs mit Verlauf und
  Trend, nicht im Plan vorkommende Parameter ignoriert, Bestandteile aus dem Formular, Werte vor dem letzten Plan zählen
  nicht, kein/altes Labor, Gewichtsänderung mit Grenze, Statistik der eigenen Pläne, Rechte, Testzugang und
  Testpatient, keine Mengenempfehlung im Text); `manage.py test infusionen befunde patienten` grün (207). Browsertest
  `plaene.spec.ts` „Hinweise aus Labor und Gewicht im Plan-Editor …“ lokal grün (Vite + Django, Chromium 141). CI-Lauf
  steht aus.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

## AC · Notfallpaket (10.10.2026)

Ziel: Nach einem Totalausfall (Festplatte, Diebstahl, Brand) baut die Praxis EPM auf neuer Hardware wieder auf – ohne
Internet, ohne Entwickler, mit einem gedruckten Plan.

### F188 Notfallpaket und Wiederaufbau-Plan
- **Paket** (`epm-notfall-<TAG>-<JJJJ-MM-TT_hhmm>.tar`, Systemagent-Aktion `notfallpaket`, `AGENT_VERSION` 7, im
  Gleichschritt mit `system/host.py`): `images/` (`docker save` genau der laufenden Images, Tag aus `.env`),
  `rollout/` (Skripte 01–04, Agent, `epm-update`, `epm-notfall-aufbau.sh`), `code/` (Compose, `docs/`), `debs/`
  (Debian-Pakete für 01/02/03 per `apt-cache depends --recurse` + `apt-get download`, sonst aus dem apt-Cache; was fehlt,
  steht in `INHALT.json` › `fehlt`), `ocr-modelle/`, wahlweise `sicherung/` (jüngste Sicherung, verschlüsselt wie
  immer), `konfiguration/` (`epm.conf` ohne Geheimnisse, Einstellungen ohne Zugangsdaten), `ca/` (Zertifikat; Schlüssel
  nur als `ca.key.gpg`, symmetrisch mit dem Sicherungs-Passwort – ohne gesetztes Passwort kein Schlüssel und keine
  Sicherung), `NOTFALLPLAN.pdf`/`.md`, `INHALT.json`, `SHA256SUMS`. **Nicht hinein:** Sicherungs-Passwort,
  WebDAV-Zugang, Django-Secret, DB-Passwort (werden beim Aufbau neu erzeugt; Sitzungen enden, TOTP und Passkeys bleiben
  gültig, da in der Datenbank bzw. an `EPM_WEB_NAME` gebunden). Datei 0640 im Download-Ordner, 6 Stunden bereit.
- **Oberfläche:** System › Reiter **Notfall**: letztes Paket (Zeit, Version, Größe, SHA-256, was fehlt), Hinweis bei
  älter als 30 Tage oder neuerer EPM-Version, „Notfallpaket erstellen“ mit Schätzung und Wahl „jüngste Sicherung mit
  hinein“ (Passwort + zweiter Faktor), Download-Link, Wiederaufbau-Plan zum Lesen und als PDF. Systemverwaltung:
  Ampel-Kachel „Notfallpaket“ (zuletzt erstellt … / älter als 30 Tage / noch nie) und Eintrag unter „Häufige Aufgaben“.
  Hilfe-Abschnitt „Notfallpaket und Wiederaufbau nach Totalausfall“ mit Link auf das PDF.
- **API:** `POST /api/system/notfall/` `{mit_sicherung, kennwort, code}` (Recht Systemverwaltung, 2FA, Agent aktuell,
  prüft freien Speicher gegen die Schätzung: 2 × Schätzung + 512 MB, sonst 409); `GET /api/system/notfall/<datei>/`
  (X-Accel, Audit „Notfallpaket heruntergeladen“); `GET /api/system/notfallplan/?art=html|pdf|md` (auch mit „Sicherungen
  verwalten“; `art` statt `format`, da DRF `format` selbst auswertet). `manage.py epm_notfallplan --format md|html|pdf`
  erzeugt den Plan für den Agenten.
- **Plan:** `docs/NOTFALLPLAN.md` (gleich `backend/system/notfallplan.md`, ein Test hält beide gleich): nummerierte
  Schritte, Kapitel „nur EPM kaputt“ und „nur die Datenbank kaputt“, Checkliste zum Ausdrucken, Dauer 1,5–3 Stunden.
- **Aufbau:** `rollout/epm-notfall-aufbau.sh [--probelauf] [--mit-internet]`: Prüfsummen, Ubuntu-Version, `epm.conf`
  und Netz, Sicherungs-Passwort, `debs/*.deb`, 01/02 mit `EPM_OFFLINE=1` (überspringt `apt-get update`/Repository), CA
  entschlüsseln, 04, `docker load`, Start, `epm-systemagent notfall-einspielen` (Sicherung einlesen, Passwort setzen,
  wiederherstellen), 03 nur wenn ein SSH-Schlüssel hinterlegt ist. Ohne Shell im Agenten (Listen-Aufrufe), Audit-Log
  für Anfordern und Herunterladen.
- **Teststatus:** `system/test_notfall.py` (17 Tests mit `Auftraege`): Rechte, 2FA, ohne Agent 409, Audit-Texte,
  Download/X-Accel, Plan in drei Formaten; Agent im Prozess mit nachgebildetem `docker save`: Inhalt, Prüfsummen, keine
  Geheimnisse in irgendeiner Datei, CA-Schlüssel mit dem Passwort entschlüsselbar, Rechte 0640, ohne Passwort kein
  Schlüssel und keine Sicherung, Trockenlauf, Fristen; Probelauf des Aufbauskripts (und Abbruch bei verändertem Paket);
  Browsertest Reiter Notfall und Ampel. **Nicht geprüft:** echter Neuaufbau auf frischem Ubuntu, echtes
  `apt-get download`/`docker save`/`docker load`, PDF aus dem Container im Agenten, `notfall-einspielen` von Ende zu Ende.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

## AD · Entscheidungen der Praxis (10.10.2026)

Antworten des Auftraggebers auf die Rückfragen aus F181, F187 und F177 (`docs/UI-UX-AKTE-2026-10-10.md`,
`docs/VORLAGEN-ALICE-2026-10-09.md`).

### F190 Tablet mit zwei Spalten, Mengen je kg einstellbar, Referenzbereiche nachtragen, Infoblatt ohne Telefontermine
- **Tablet 1024 × 768:** zwei breite Spalten in der Übersicht der Akte, die Seite darf scrollen (vorher drei schmale
  Spalten ohne Scrollen). Das Fenster ohne Seiten-Scrollen gilt jetzt ab 1280 × 600 px (`index.css`, `.seite-fuellt`;
  `Uebersicht.tsx`: Spalten nach Breite der Fläche, unter 1100 px zwei). Ab 1366 × 768 unverändert kein Seiten-Scrollen.
- **Mengen je kg für „Mengen nach Praxisvorgabe“:** Vorlagen › Grenzwerte, Karte „Mengen je kg für ‚Mengen nach
  Praxisvorgabe‘“ – je Bestandteil ein Feld mit Einheit (Glucose, Aminosäuren, Lipide in g/kg; Natrium, Kalium, Phosphat,
  Calcium, Magnesium in mmol/kg), 0 = nicht vorbelegen. Neue Felder `Einstellungen.vorgabe_*_kg` (Migration
  `stammdaten/0020_praxisvorgabe_je_kg`, Startwerte = Werte des Altsystems 3,5 / 1,2 / 1 / 1,3 / 0,7 / 0,3 / 0,15 /
  0,2) und `vorgabe_geaendert_am` (gesetzt, sobald sich ein Wert ändert). Prüfung 0 bis Obergrenze (Glucose 10 g/kg,
  Aminosäuren und Lipide 5 g/kg, Natrium und Kalium 10 mmol/kg, Phosphat, Calcium, Magnesium 5 mmol/kg) im Serializer
  und im Modell; Historie wie alle Einstellungen, Audit-Log „Einstellungen“ mit Feldnamen. `GET …/vorbelegung/` nutzt
  die Einstellung und liefert `stand`; der Plan-Editor zeigt neben „Mengen nach Praxisvorgabe“ „nach Praxisvorgabe vom
  <Datum>“ (bzw. „Startwerte wie im Altsystem“), der Tooltip die Mengen je kg.
- **Referenzbereiche im Laborkatalog:** Vorlagen › Labor und Diagnosen › Laborparameter hat oben „Ohne Referenzbereich
  (N)“ – Liste der aktiven Parameter ohne Bereich, zuerst die für die Infusionsplan-Hinweise (Na, K, Ca, Mg, P, Albumin,
  Glucose, Triglyceride, Cu, Zn, Se, Mn, dann Vitamine; markiert „Infusionsplan“), mit Erklärtext (vom eigenen Labor
  übernehmen; gilt nur, wenn ein Befund keinen eigenen Bereich mitbringt). Adresse
  `/admin/vorlagen?bereich=kataloge&labor=ohne_referenz`. EPM trägt **keine** Referenzwerte selbst ein.
  Im Plan-Editor (F187) neuer dezenter Hinweis `referenz_fehlt`: „Für Kalium und Magnesium ist kein Referenzbereich
  hinterlegt – Hinweise aus dem Labor sind deshalb unvollständig …“, mit Link zum Katalog nur für „Vorlagen pflegen“.
- **Telefon- und Videotermine auf dem Infoblatt:** Nein, der Standard bleibt aus (U72 geschlossen); keine Änderung am
  Code.
- **Labor-Hinweise (F187) zählen ab dem Tag der Freigabe des letzten Plans** – entschieden 10.10.2026, so bleibt es.
- **Gewicht vor der Freigabe:** „bitte prüfen“ nach **6 Monaten** (entschieden 10.10.2026; vorher vorläufig 3 Monate fest im
  Plan-Editor). Neue Einstellung `plan_gewicht_alter_monate` (Standard 6, 1–60) in derselben Migration, unter Vorlagen ›
  Grenzwerte in der Karte der Mengen je kg; „Prüfung vor der Freigabe“ nutzt sie. Eine frühere Einstellung mit Wert 3 gab
  es nicht, daher genügt der Standardwert (keine Umstellung bestehender Werte nötig).
- **Teststatus:** Backend `infusionen.tests.PlanPraxisvorgabe` (Vorbelegung nutzt die Einstellung, Grenzen, Historie,
  Stand, Audit-Log), `PlanHinweise.test_fehlender_referenzbereich_im_katalog`; `manage.py test infusionen stammdaten
  befunde patienten` grün. Browsertests `layout.spec.ts` (Tablet zwei Spalten, scrollen erlaubt, nichts ragt heraus),
  `plaene.spec.ts` (Praxisvorgabe geändert → Editor nutzt die neuen Mengen und nennt den Stand). Lokal grün, CI-Lauf
  steht aus.
- **Status:** ABGESCHLOSSEN – Lauf steht aus

## Offene Backend-Funktionen

Erledigt in Runde 1 (01.10.2026): O-00 Migrationen im Repo (CI), O-02 Abschluss nur Mediziner, O-03 dauerhafte Sperre,
O-04 Frist Einmal-Kennwort, O-05 Sicherheitsstatus und Sitzungen, O-06 Darstellung/Startseite prüfen, O-07 Startseite
(ohne Backup-Status), O-08 Patientenliste, O-09 Neuer Patient, O-10 Versionen, O-11 Verlauf nach Bereichen, O-12 Kontakt
mit Wiedervorlage, O-13 Terminorte, O-14 Plan mit Elektrolyten/Spurenelementen/Vitaminen/Grenzen (ohne Gesamtvolumen),
O-15 Leer/Vorlage, O-16 Planvergleich, O-18 Altdokumente und Dateityp, O-19 Ansprechpartner, O-20 Präparate, O-21
Einstellungen (ohne Gesamtvolumen), O-22 Audit-Log (ohne Gerätename). Alle mit Backend-Tests gegen PostgreSQL.

Erledigt in Runde 2 (01.10.2026): O-01 Frontend für alle umgesetzten Funktionen (React, Browsertests gegen den echten Stack in
GitHub Actions, Neustart-Nachweis), O-26 Tests für F05, F06, F41, F56 (als Browsertests), Rechte je Gruppe (F66), Briefkopf und
Logo (F49), O-14 Gesamtvolumen im Plan und seine Grenzen (F39, F48; nach Klärung U2), O-22 Gerät im Audit-Log (U8: IP und
Browser reichen). Funktionen, die noch fehlen, zeigt die Oberfläche als „folgt“ (ausgegraut) – nichts davon ist nachgebildet.

Erledigt in Runde 3 (01.10.2026): O-17 PDF-Erzeugung und Dokumentvorlagen (F23, F24, F35, F37, F50, F51, F55, F59).

Erledigt in Runde 5 (02.10.2026): O-07 Backup-Status auf der Startseite (F13), O-23 Datensicherung aus der Oberfläche (F61–F64: Sicherung um 02:00, Passwort für die Verschlüsselung in der Oberfläche, Übertragung mit rclone, Wiederherstellen; geprüft gegen einen WebDAV-Testserver in CI), O-24 Serverskripte nach „EPM-Server Aufbau“ (needrestart startet Dienste außer Docker/containerd selbst neu, eigene Docker-Adressbereiche, `epm.service`, Journal dauerhaft mit 1 GB/6 Monaten, Swap, wöchentliches Docker-Aufräumen, Warnung ohne eigenes Volume für `/srv`). Abweichung: `epm.service` legt `04-projekt.sh` an (nicht `02-docker.sh`), damit `sudo epm-update` es auch auf bestehenden Servern einrichtet.

Erledigt nach der Gegenprüfung vom 02.10.2026: O-27 abgebrochene Sicherung hinterlässt keine Dateien (F61), O-28 Nachholen der Löschungen wird überwacht – Stand, Audit-Log, Backup- und Startseite, Meldung des Wiederherstellens (F63, F73, F80), O-29 Import: Patient mit im EPM gelöschter Nummer lässt sich ausnehmen (F65).

| Nr. | Was fehlt | Warum | Betroffene Dateien | Abhängigkeiten | Nächster Schritt |
|---|---|---|---|---|---|
| O-25 | Altdaten übernehmen (Rollout-Schritt 7) | Werkzeug ist fertig (F65); die Übernahme selbst steht aus | – | frischer Dump des Altsystems, Dokumentenordner `PatData` auf dem Server | nach `docs/ALTDATEN-IMPORT.md`: Dump laden, Zuordnungen prüfen, Probelauf, Import, Dokumente, Akten prüfen, Abschließen |

## Unklarheiten (nicht eigenmächtig entschieden)

| Nr. | Frage | Betrifft | Zwischenlösung |
|---|---|---|---|
| U1 | ~~Bedeutung und Einheit von Pantozol 0–3 / Tage~~ **Geklärt 01.10.2026:** Pantozol® 40 mg, Pantozol® 20 mg, Nexium®; Zeiten morgens, mittags, abends. Codes wie in `EPM_infuplan.php` (1 = 40 mg, 3 = 20 mg, 2 = Nexium®, 0 = kein; Zeiten 4/2/1 addiert) | F38 | – |
| U2 | ~~Gesamtvolumen und Laufzeit eingeben oder berechnen?~~ **Geklärt 01.10.2026:** Gesamtvolumen = Gewicht × 35 ml (wie im Altsystem), Laufzeit manuell; Rate = Gesamtvolumen ÷ Laufzeit | F39, F48 | – |
| U3 | „geändert“-Hinweis an einem Kontakt im Entwurf widerspricht „unveränderlich“ | F26 | Beschluss gilt – **bestätigt 03.10.2026: bleibt so** |
| U4 | ~~Plan-Hinweis „6 Monate“ in der Liste vs. 12 Monate in den Grenzwerten~~ **Bestätigt 03.10.2026:** es gilt der eingestellte Grenzwert (Text nennt die eingestellten Monate) | F14 | – |
| U5 | ~~Felder Krankenkasse, Telefon 2, Bemerkung (nicht im Entwurf)~~ **Geklärt 03.10.2026:** anzeigen – Telefon 2 und Krankenkasse in Neuer Patient, Stammdaten und „Anschrift und Kontakt“; Bemerkung als Karte unter Diagnose & Therapie mit Versionen und Verlauf | F16, F17, F19 | – |
| U6 | ~~Kontaktart (nicht im Entwurf)~~ **Geklärt 03.10.2026:** anzeigen – Auswahl beim Erfassen (Kontakte, Schnellerfassung), Anzeige in Kontaktliste, Übersicht und Vorschau; Liste „Kontaktarten“ unter Vorlagen › Auswahllisten | F26, F91 | – |
| U7 | ~~Rolle des Testbenutzers: Mitarbeiter (Entwurf) oder Mediziner (Code)~~ **Geklärt 03.10.2026:** Mitarbeiter; je Konto auf Betrachter, Mitarbeiter (erweitert) oder Mediziner umstellbar (Testbenutzer-Schalter, F100) | F57 | – |
| U8 | ~~Gerätename im Audit-Log oder nur IP/Browser~~ **Geklärt 01.10.2026:** IP und Browser reichen | F11, F58 | – |
| U9 | ~~Übertragung zur Nextcloud: Server schiebt oder Gegenseite holt ab~~ **Geklärt 01.10.2026:** Server schiebt in einen WebDAV-Ordner, Werkzeug rclone (Festlegung 01.10.2026) | F64 | – |
| U10 | ~~Wer pflegt Versorger und Ansprechpartner?~~ **Erledigt 01.10.2026:** Rechte sind je Gruppe einstellbar (F66); Standard Mitarbeiter, Mediziner und Admin | F45, F46 | – |
| U11 | ~~Ab welcher Änderung zeigt der Trend-Pfeil „gleich“?~~ **Bestätigt 01.10.2026:** weniger als ±1 % = gleich | F14 | – |
| U12 | ~~Darf der Admin auch Patientendaten schreiben?~~ **Geklärt 01.10.2026:** Admins dürfen alles, Patientendaten schreiben sie nur bei Testpatienten; echte Akten nur lesen, Wiederöffnen, Benutzer und Sicherungen bleiben | F66 | – |
| U13 | ~~Energie im Infusionsplan: Lipide 9 oder 9,15 kcal/g, Albumin mit oder ohne Energie?~~ **Geklärt 01.10.2026:** wie in `EPM_infuplan.php`: Lipide 9,15 kcal/g, Humanalbumin in ml ohne Energie | F33, F39 | – |
| U14 | ~~Stabilitätsprüfung Calcium + Magnesium und Vorbelegung des ersten Plans je kg übernehmen?~~ **Geklärt 01.10.2026:** ja, beides wie im Altsystem (Stabilität als Hinweis, Speichern bleibt möglich); Präparate werden beim ersten Plan **nicht** vorausgewählt | F32, F33 | – |
| U15 | ~~Muss beim endgültigen Löschen auch der Titel aus Historie und Audit-Log verschwinden?~~ **Geklärt 02.10.2026: nach geltender DSGVO.** Titel, Dateiname, Notiz und Datum werden überall entfernt (Art. 17 Abs. 1 d, Art. 5 Abs. 1 c/e); es bleibt der Nachweis ohne Inhalt (Art. 5 Abs. 2, Art. 33 Abs. 5; § 630f BGB); Sicherungen laufen nach 30 Tagen ab (Festlegung 02.10.2026, vorher 14), nach einer Wiederherstellung wird erneut gelöscht | F73 | – |
| U16 | Rechtsgrundlage der Verarbeitung (Einwilligung nach Art. 9 Abs. 2 a oder Art. 9 Abs. 2 h DSGVO) und Herkunft der 10 Jahre Aufbewahrung – § 630f BGB verpflichtet Behandelnde; die Stiftung „vermittelt“, die Praxis führt eigene Akten. Anfrage an die Stiftung ist formuliert, Antwort offen | F74, F80 | 10 Jahre als einstellbarer Standard; vor Ablauf Löschung nur auf Antrag und nach Entscheidung des Mediziners |
| U17 | Texte der drei Vordrucke (Zwecke, Empfänger, Rechtsgrundlage, Speicherdauer, Datenschutzbeauftragte/r, Aufsichtsbehörde) | F76 | Entwürfe mit Lücken, Wasserzeichen „ENTWURF“ bis zur Veröffentlichung durch die Stiftung – **seit 03.10.2026 je Vordruck manuell abschaltbar** (Vorlagen › Dokumentvorlagen › „Entwurfsmodus ausschalten“, F76) |
| U18 | ~~Wie lange wird das Audit-Log aufbewahrt?~~ **Geklärt 03.10.2026:** unbegrenzt (Standard 0); in EPM einstellbar (Vorlagen › Grenzwerte › Datenschutz) | F83 | – |
| U19 | ~~„Abschluss prüfen“ nach wie vielen Monaten ohne Kontakt? Welche Erklärungen sollen vorliegen?~~ **Bestätigt 03.10.2026:** 24 Monate; alle drei – einstellbar | F74, F75 | – |
| U20 | ~~Verschlüsselung der Sicherungen: Wer erzeugt und verwahrt den privaten Schlüssel?~~ **Geklärt 02.10.2026:** symmetrisch mit einem Passwort, das die Administration in der Oberfläche festlegt; es liegt nur auf dem Server (root) und ausgedruckt im Tresor (Passwortblatt) | F61 | – |
| U21 | ~~Aufbewahrung der Sicherungen in der Nextcloud und auf der NAS~~ **Geklärt 03.10.2026:** auch dort 30 Tage; der Systemagent entfernt nach jeder Übertragung ältere EPM-Sicherungen im Ziel (einstellbar: nie, 14–365 Tage; die jüngste bleibt immer, fremde Dateien werden nie angefasst). Was die NAS aus der Nextcloud spiegelt, folgt deren Einstellung. Geheimhaltungsverpflichtung der Dienstleister (§ 203 StGB) bleibt organisatorisch | F64 | – |
| U22 | ~~Sollen Mitarbeiter Pläne auch anlegen dürfen?~~ **Geklärt 03.10.2026:** Recht bleibt je Gruppe umstellbar; neue Rolle „Mitarbeiter (erweitert)“ (Standard wie Mitarbeiter + Infusionspläne anlegen) für feinere Verteilung | F32, F66 | – |
| U23 | ~~Einschränkung nur bei abgeschlossenen Akten – reicht das?~~ **Bestätigt 03.10.2026:** ja | F79 | – |
| U24 | ~~Nachweis bei Freigabe per Telefon oder persönlich~~ **Bestätigt 03.10.2026:** ohne Nachweis möglich (Pflicht nur bei E-Mail und schriftlich) | F82 | – |
| U25 | ~~Feiertage im Kalender: welches Bundesland?~~ **Geklärt 02.10.2026:** NRW (Sitz der Stiftung in Altenberge) | F84 | – |
| U26 | ~~Import durch die Administration legt echte Akten an – Ausnahme von U12?~~ **Bestätigt 03.10.2026:** ja, Admins dürfen den Import mit echten Daten durchführen (nur über Administration › Import, eigenes Recht, Kennwort + 2FA, Audit-Log) | F65 | – |
| U27 | ~~Echte Akten aus der Testphase sperren den Import – wie kommt man zu einem leeren System?~~ **Geklärt 03.10.2026:** Administration › System › „Datenbank leeren“ (F107: alles aus der Testphase inkl. Löschprotokoll, Versorger, Ärzte, Benutzer nach Auswahl und Audit-Log; Präparate und Vorlagen bleiben; vorher Sicherung; Bestätigungscode, Passwort, 2FA, Rückfrage) und Schalter „Musterdaten automatisch anlegen“ (F108) | F65, F107, F108 | – |
| U28 | ~~Dokumente anderer Dateitypen im Ordner des Altsystems (Word, Excel …)~~ **Bestätigt 03.10.2026:** nicht übernehmen (veränderbar); sie werden einzeln aufgelistet, der Ordner bleibt unverändert | F65 | – |
| U29 | Zeitangaben: Welchen Typ haben `lastchange`, `created`, `deleted_at` im echten Altsystem? `TIMESTAMP` steht im Dump in UTC und wird umgerechnet, `DATETIME` gilt als Ortszeit | F65 | am echten Dump prüfen – das Werkzeug zeigt nach dem Laden einen Hinweis, wenn es umgerechnet hat |
| U30 | Infusionspläne aus dem Altsystem: ohne Freigabe und ohne gespeicherte PDF (im Altsystem gab es beides nicht); Mengen 0 → leer; Energie nur dann als „manuell“, wenn sie von der Berechnung abweicht; jüngster Plan je Patient „aktuell“ | F65 | so umgesetzt (Regeln 13 und 16 der Datenanalyse); in der Akte als „aus dem Altsystem“ gekennzeichnet – **bestätigt 03.10.2026** |
| U31 | ~~Rolle der Konten aus dem Altsystem~~ **Bestätigt 03.10.2026:** Vorschlag aus dessen Rechtestufe (100 Betrachter, 1000 Mitarbeiter, 10000 Mediziner, 100000 Admin), je Konto im Werkzeug änderbar – die Berechtigung wird beim Import gesetzt; Konten entstehen ohne Kennwort | F65 | – |
| U32 | Nach dem Abschließen enthalten ältere Sicherungen aus der Testphase und der Ordner `data/import` auf dem Server weiterhin Altdaten (auch der nicht übernommenen Patienten) | F65, F61 | organisatorisch löschen (`docs/DATENSCHUTZ.md`); das Werkzeug weist beim Abschließen darauf hin – **bestätigt 03.10.2026**; dazu Menüpunkt „Import“ unter System aus- und wieder einblendbar (F109) |
| U34 | ~~Bestätigungen ohne zweiten Faktor nur mit Kennwort?~~ **Geklärt 03.10.2026: nein.** Endgültig löschen, Wiederherstellen, Updates, Neustart, Sicherung und Import verlangen immer den zweiten Faktor; wer sie ausführt (Mediziner, Administration …), muss ihn einrichten – ohne geht es nicht | F99 | – |
| U35 | Hochgeladene Sicherung eines anderen Servers mit fremdem Passwort: Das Passwort wird auf diesem Server (root, 0600) als eigene Nummer hinterlegt, damit sich die Sicherung wiederherstellen lässt | F103 | so umgesetzt; das aktuelle Sicherungs-Passwort dieses Servers bleibt unverändert – **bestätigt 03.10.2026** |
| U36 | Geänderte Aufbewahrung wirkt erst mit der nächsten Sicherung (dann werden ältere entfernt), nicht sofort | F103 | so umgesetzt; der Dialog sagt es – **bestätigt 03.10.2026** |
| U37 | „Kein Infusionsplan nötig“: Wer darf bestätigen? Gilt auch eine offene Entwurfsfassung als „kein Plan“? | F105 | Recht „Akten bearbeiten“ (wie „kein Versorger“; unter Benutzer › Rechte umstellbar); ein Entwurf allein zählt nicht als Plan – der Hinweis bleibt bis zur Freigabe – **bestätigt 03.10.2026** |
| U38 | ~~„Testdaten sehen“ für den Admin abschaltbar?~~ **Bestätigt 03.10.2026:** nein, für den Admin fest | F106 | – |
| U33 | Vor dem Abschließen: Ein nach Art. 17 endgültig gelöschtes **Dokument** käme nach „Zurücknehmen“ und erneutem Import wieder (neue Nummer, die Löschliste erkennt es nicht). Eine endgültig gelöschte **Akte** kommt nicht wieder: Ihre Nummer steht im Löschprotokoll; der Patient erscheint unter „Auffälligkeiten“ und lässt sich nur „nicht übernehmen“ – eine andere Nummer ist nicht wählbar (O-29, behoben 02.10.2026) | F65, F73, F80 | Dokumente: betrifft nur die Zeit vor dem Abschließen (Testphase); nach dem Abschließen ist der Dump gelöscht – **bestätigt 03.10.2026** |

| U39 | **Infusionstage:** Reichen Zahlen pro Woche, oder sollen konkrete Wochentage hinterlegt werden (Mo/Mi/Fr)? | F110 | Zahlen je Beutelart + Zahl der infusionsfreien Tage |
| U40 | Ist mit „Elektrolytbeutel“ das **Zusatzvolumen** des Plans gemeint (Sterofundin ISO, Ringer …) oder ein weiterer, eigener Beutel? | F110 | Zusatzvolumen |
| U41 | „Weitere Bestandteile“ haben ein Freitextfeld **Häufigkeit** („täglich“, „Mo/Mi/Fr“). Auch auf Tage pro Woche umstellen? | F110 | bleibt Freitext |
| U42 | Dipeptamin und Omegaven **ausblenden** (bestehende Pläne behalten sie) statt löschen – richtig? | F111 | ausblenden |
| U43 | Umbenennen von Sterofundin/Ringer/Junosteril wirkt auch auf **alte Pläne** (ein Katalogeintrag). So gewollt, oder neue Einträge daneben? Folge für die Übernahme: Das „Sterofundin“ des Altsystems trifft jetzt keinen Eintrag mehr automatisch und muss im Import einmal von Hand auf „Sterofundin ISO“ gelegt werden – das ist Absicht, denn ob beides dasselbe Präparat ist, entscheidet kein Programm | F111, F65 | umbenennen; eine Zuordnung mehr beim Import |
| U44 | Labor: **Referenzbereiche** je Parameter hinterlegen und abweichende Werte markieren? In der Mail nicht gewünscht, aber jedes Labor liefert sie mit | F112 | Felder vorhanden, bleiben leer; keine Markierung, bis das geklärt ist |
| U45 | Labor: Die **Einheiten** sind vorbelegt (GPT U/l, Kreatinin mg/dl, Natrium mmol/l …). Bitte einmal gegenlesen | F112 | Vorbelegung nach `docs/WUENSCHE-PRAXIS-2026-10-06.md`, je Wert überschreibbar |
| U46 | „Vitamin B1, B2, B6, B12, Folsäure“ und „Vitamin D, D3, Calcidiol, Calcitriol“ als **je eigener Parameter** – richtig? | F112 | je eigener Parameter |
| U47 | Labor: Werte wie **„< 0,1“ oder „negativ“** als Text erlauben (dann kein Verlauf für diesen Wert)? | F113 | Text erlaubt, Zahl bevorzugt |
| U48 | Soll der **hochgeladene Originalbefund** am Laborbefund hängen (statt nur in den Dokumenten zu liegen)? | F113 | Verknüpfung vorhanden, freiwillig |
| U49 | BIA: **BMI** aus Gewicht und Größe berechnen oder den Gerätewert eintragen? | F114 | Feld zum Eintragen, mit berechnetem Vorschlag daneben |
| U50 | Soll das **BIA-Gewicht** in den Gewichtsverlauf übernommen werden? | F114 | Häkchen beim Speichern, vorbelegt „ja“ |
| U51 | Bleibt das bisherige **Freitextfeld „Diagnose“** neben der strukturierten Liste bestehen? | F117 | beides nebeneinander |
| U52 | Neben G/V/Z/A auch eine **Seitenangabe** (rechts/links/beidseits)? | F117 | nein |
| U53 | Soll der Diagnose-Katalog bei **jeder neuen Eingabe** wachsen oder nur unter Vorlagen gepflegt werden? | F117 | wächst automatisch, unter Vorlagen korrigierbar |
| U54 | Berichte: Wer darf **freigeben** – nur Mediziner oder auch Mitarbeiter? Braucht es eine Freigabe auf Anordnung wie bei den Plänen (F82)? | F115 | eigenes Recht „Berichte freigeben“, Standard Mediziner; keine Freigabe auf Anordnung |
| U55 | Soll der freigegebene Bericht automatisch als **PDF in die Dokumente** wandern? | F115 | ja (wie die Plan-PDF) |
| U56 | Sprechstundenblatt: Stimmt der **Umfang**, fehlt etwas (Therapie, Kontakte der letzten Monate, Termine)? | F116 | Umfang nach `docs/WUENSCHE-PRAXIS-2026-10-06.md` |
| U57 | Versichertendaten: Reichen Art, Versicherung und Nummer, oder braucht es mehr (Versichertenstatus, Kostenträger-/IK-Nummer, Genehmigung bis, Befreiung)? | F118 | die drei Angaben |
| U58 | Soll es einen **Verlauf je Laborparameter** geben (Diagramm wie beim Gewicht, z. B. Ferritin über 2 Jahre)? | F113 | Endpunkt vorhanden, in der Oberfläche noch nicht gezeichnet |
| U59 | Welche **Berichtsarten** sollen in der Auswahlliste stehen? | F115 | Arztbrief, Verlaufsbericht, Stellungnahme, Sonstiges – unter Vorlagen änderbar |
| U60 | Sprechstundenblatt: Nur **PDF** oder zusätzlich eine Ansicht am Bildschirm? | F116 | PDF |
| U61 | Soll ein ausgeblendeter Hinweis auch dann **weg bleiben**, wenn sich die Lage ändert (z. B. „Kein Laborbefund“ ausgeblendet, danach wird einer erfasst)? Derzeit ja – die Stummschaltung läuft ab oder wird aufgehoben, der Hinweis entsteht ohnehin nur neu, wenn die Lage es hergibt | F119 | Stummschaltung bleibt bis zur Frist |
| U62 | Unter welchem **Namen** soll EPM erreichbar sein (z. B. `epm.stiftung.lan`), und soll die CA auf dem Server (`epm-zertifikat einrichten`) oder auf der OPNsense liegen (`epm-zertifikat importieren`)? | F134, F130 | Name aus `EPM_WEB_NAME`, CA auf dem Server; beides unterstützt |
| U63 | Soll das **Freigeben eines Plans** (am Telefon wie am PC) zusätzlich mit Passkey bzw. Code bestätigt werden? Heute genügt die Anmeldung, wie bisher beschlossen | F36, F132 | unverändert: ohne zusätzliche Bestätigung |
| U64 | ~~Gewichte zusammenfassen: Fenster ab dem ersten Eintrag oder je Kalendertag?~~ **Geklärt 09.10.2026:** Fenster ab dem ersten Eintrag, Standard 2 × 24 Stunden; im Werkzeug einstellbar | F159 | – |

| U65 | ~~Auto-OCR auch für Dokumente aus der Akte und dem Altsystem?~~ **Geklärt 09.10.2026:** automatisch nur, was über „Scans“ kommt; Dokumente in der Akte bekommen „Text erkennen“ (OCRmyPDF, ersetzt die Datei durch dieselbe PDF/A mit Textebene) und „Werte übernehmen“ | F170, F171 | umgesetzt |
| U66 | ~~Welches BIA-Gerät?~~ **Geklärt 09.10.2026:** unterschiedliche Geräte (Patienten deutschlandweit) – allgemeine Erkennung nach Beschriftung, gängige Bezeichnungen der Geräte (auch englisch) werden ergänzt | F166, F169 | umgesetzt (F169) |
| U67 | ~~PP-OCRv5-Modelle beim Bau von huggingface.co laden?~~ **Geklärt 09.10.2026:** Modelle offline vorbereiten (`werkzeuge/ocr-modelle.sh` bzw. `.ps1`) und auf der Test-VM mit `epm-ocr-modelle einspielen` ablegen; `epm-update` baut sie ein. Ohne sie: nur Tesseract | F167 | – |
| U68 | ~~Scan-Dateien nicht in der Sicherung~~ **Bestätigt 09.10.2026:** richtig so; Scans lassen sich jederzeit selbst sofort löschen | F165, F61 | – |
| U69 | ~~Startseite: Kachel oder Hinweis?~~ **Bestätigt 09.10.2026:** Hinweis | F160 | – |
| U70 | ~~Geänderte Frist auch für vorhandene Scans?~~ **Bestätigt 09.10.2026:** nur für neue Scans | F165 | – |
| U71 | ~~Textwerte („< 0,1“, „negativ“) aus Scans übernehmen?~~ **Bestätigt 09.10.2026:** nein, nur Zahlen | F166, U47 | – |
| U72 | ~~Sollen Telefon- und Videotermine standardmäßig mit auf das Infoblatt an die Praxis (Rückfrage an Alice, `docs/VORLAGEN-ALICE-2026-10-09.md`)?~~ **Entschieden 10.10.2026: Nein, Standard bleibt aus** (F190) | F177 | standardmäßig nicht; im Dialog ankreuzbar |
| U73 | In welchem Rhythmus und wie viele Tage vorher soll das Infoblatt verschickt werden (Rückfrage an Alice)? | F177 | wöchentlich (nächste Woche Mo–So), Erinnerung 3 Tage vorher; unter Vorlagen › Grenzwerte änderbar |
| U74 | ~~„Datenbank leeren“ soll auch die gelernten Zuordnungen und die Kennzahl leeren: `scans.lernen.leeren()` steht bereit, der Aufruf in `system/leeren.py` (`datenbank_leeren`, plus `umfang`) gehört zu einem anderen Auftrag und fehlt noch. Ebenso entfernt das Leeren keine nicht zugeordneten Scans (`scans.Scan` mit Dateien unter `EPM_SCANS`, enthalten Patientendaten; sie laufen erst nach der Aufbewahrungsfrist ab)~~ **Erledigt 10.10.2026:** `datenbank_leeren` entfernt alle Scans samt Dateien (der Stand des OCR-Dienstes in `.dienst` bleibt) und ruft `scans.lernen.leeren()` auf; `umfang` zählt die Scans; Test `system/test_leeren.py` | F182 | – |
| U75 | Gelernte Zuordnungen sind laut Auftrag auch für „Vorlagen pflegen“ gedacht; die API lässt das zu, in der Oberfläche liegt der Bereich aber unter Scans (Route und Menü nur mit Recht „Scans“). Ein Link unter Vorlagen › Labor wäre der Weg für Rollen ohne „Scans“ | F182 | Standardrollen haben beide Rechte; Link unter Vorlagen nicht gesetzt (anderer Auftrag) |

## Änderungsprotokoll

| Datum | Stand | Änderung |
|---|---|---|
| 14.10.2026 | Scans: Diagnosen ohne ICD-Code im Brief | Kundenwunsch: PDF-Briefe nennen Diagnosen meist nur im Freitext. Jede Zeile unter „Diagnosen:“ (auch Entlassungs-, Neben-, Dauerdiagnosen, Vorerkrankungen) ohne Code wird ein eigener Vorschlag (`scans/ocr/auswertung.py`: `_freitext_diagnosen`, `freitext: true`, hinter den Diagnosen mit Code; umbrochene Zeilen zusammengesetzt, Messwerte und Fließtext ausgelassen, „V.a.“/„Z.n.“ → Kennzeichen). Code aus dem Gelernten, sonst aus Vorlagen › Diagnosen (`aus_liste`: gleiche Wörter mit kleinen Lesefehlern; 1,0 → `zuordnung: liste`, angehakt; ab 0,6 → `liste_vorschlag`, nicht angehakt; Gleichstand → unspezifische Form). Ohne Treffer bleibt der Code leer, nicht angehakt. Der ICD-Code bleibt Pflicht (Entscheidung 14.10.2026): Zuordnen sperrt „In die Akte legen“, solange eine angehakte Diagnose ohne Code ist; Bezeichnung mit Auswahlliste der Diagnoseliste setzt den Code. Ergänzte Codes werden gelernt. Der Freitext bleibt zusätzlich unter „Texte“. Tests `scans.tests.AuswertungTest.test_arztbrief_diagnosen_ohne_icd`, `scans.test_lernen` |
| 14.10.2026 | Briefpapier der Regeneration Clinic 1:1 | Neuer Wert `briefpapier` im Baustein „Briefkopf“ (`vorlagen/briefpapier.py`, Prüfung in `bloecke.py`): Kopfband mit Wellenkante, Logo (`statisch/briefpapier/rgc-logo.png`, freigestellt) und Anschrift sowie Fußband mit Postanschrift und Registrierdaten als SVG in Seitengröße, fest positioniert und damit auf jeder Seite; Seitenränder 47/17,6/31/25 mm, Fußzeilentext links entfällt, Seitenzahl über dem Band; erste Seite mit Absenderzeile, Kontakt und „Riga, Datum“ (`absender`). Maße und Farben aus dem Briefpapier der Klinik (pt wie im Original). Schriften Inter und Carlito in `schriften/`. Laborprofile MAL-00 bis MAL-06 nutzen es; Datenmigration `vorlagen/0012_rgc_laborprofile_briefpapier` stellt unbearbeitete mitgelieferte Fassungen um. Editor: Schalter „Briefpapier der Regeneration Clinic“. Tests `vorlagen/test_rgc.py` (`test_briefpapier`). |
| 14.10.2026 | Laborprofile Malabsorption der Regeneration Clinic | Das Dokument „Laborprofile Malabsorption – Strukturierte Anforderungsprofile zur Integration in die Klinik-IT“ (Version 1.0) als Laboranforderungen auf dem Briefkopf der Klinik: neun eigene Schreiben der Firma RGC in der Gruppe „anforderungen“ – MAL-01, MAL-02A, MAL-02B, MAL-02C, MAL-03 (A–D), MAL-04 (Vollpanel aus MAL-01, 02A, 02B), MAL-05, MAL-06 und eine Übersicht mit Regelwerk R1–R11 und Monitoring-Intervallen (Kennungen `eigen-rgc-mal00` … `eigen-rgc-mal06`). Jeder Bogen ist nach Röhrchen bzw. Material geordnet (Material genau wie im Dokument), mit Röhrchenübersicht, Status P/O/R (Pflicht angekreuzt), LOINC, Hinweis, Pflichthinweisen zur Präanalytik (glutenhaltige Kost, geformter Stuhl, Spurenelement-Röhrchen, lichtgeschützt, gekühlt, nüchtern) und den Regeln des Profils; Reflexparameter aus anderen Profilen mit ihrem Röhrchen (MAL-01: Parathormon 2A.4 nach R7). Strukturierte Daten je Parameter (Felder aus Abschnitt 6 des Dokuments) in `vorlagen/statisch/laborprofile-malabsorption.json`. Umgesetzt mit `werkzeuge/rgc-laborprofile.py DOCX`; Datenmigration `vorlagen/0011_rgc_laborprofile` (nur Fehlendes). Doku `docs/VORLAGEN-RGC-2026-10.md`. Tests `vorlagen/test_rgc.py`. |
| 13.10.2026 | Weitere Word-Vorlagen der Regeneration Clinic | Die Vorlagen 01–05 (Patientenerklärungen Österreich, GKV, BG/UV, PKV, stationäre Zusatzversicherung), 11 (Anlage K) und 12 (Anwaltsvollmacht) ergänzen die mitgelieferten eigenen Schreiben der Firma RGC (Gruppe „formulare“). Umgesetzt mit `werkzeuge/rgc-vorlagen.py` nach `vorlagen/statisch/rgc/`; die Datenmigration `vorlagen/0010_rgc_vorlagen_ergaenzt` ruft `vorlagen.rgc.anlegen` erneut auf (nur Fehlendes, Kennung `mitgeliefert`). Die zuvor geplanten festen Arten `rgc_…` entfallen; alle RGC-Vorlagen laufen über eigene Schreiben je Firma. Grenzen angehoben: Textblock 6000 Zeichen, Bezeichnung 160. Doku `docs/VORLAGEN-RGC-2026-10.md`. Test `vorlagen/test_rgc.py`. |
| 13.10.2026 | Medikationsplan im Querformat | Seitenformat je Dokumentvorlage: `Dokumentvorlage.ausrichtung` (hoch/quer, Migration `vorlagen/0008`, mit Historie), `@page size: A4 landscape`, Falzmarken nur im Hochformat, Wasserzeichen angepasst, breitere Spalten Wirkstoff/Handelsname/Grund (`.quer .medikamente`). Startvorlage „Medikationsplan“ im Querformat (`STARTAUSRICHTUNG`; Migration `vorlagen/0009` löst eine nie von Hand veröffentlichte Startvorlage durch Fassung 2 im Querformat ab). Editor: Schalter Hochformat/Querformat bei `QUERFORMAT` (Medikationsplan, Sprechstunde, Patientendatenblatt), Entwurf `PUT …/entwurf/ {bloecke, ausrichtung}`, Vorschau mit `ausrichtung`, Seite im Editor im gewählten Format; `erzeuge_aus_vorlage(…, ausrichtung=)`. Test prüft die MediaBox. |
| 13.10.2026 | Dokumentvorlagen je Firma („Gemischt“) | `Dokumentvorlage.firma` (leer = gemeinsam; Migration `vorlagen/0008`), Eindeutigkeit von Entwurf, aktiver Fassung und Versionsnummern je (Art, Firma) mit `nulls_distinct=False`. `aktive(art, firma=None)`: eigene aktive Fassung der (aktiven) Firma, sonst die gemeinsame; `zustaendig()` bestimmt, welche Vorlage Entwurf, Fassungen, Wiederherstellen und Veröffentlichen betreffen; `gemeinsame()`, `eigene_anlegen()` (Kopie der gemeinsamen aktiven Fassung, sofort aktiv, Fassungen zählen je Firma, Wasserzeichen-Status der Kopie bleibt), `eigene_entfernen()` (aktiv → abgelöst, Entwurf verworfen). Alle PDF-Wege (`erzeuge_aus_vorlage`, Erklärungen, Medikationsplan, Schreiben, Infusionsplan, Sprechstunde) nehmen damit die Vorlage der aktiven Firma. `POST /api/vorlagen/{art}/firma/ {eigene}`; Übersicht mit `firma` (aktiv, name, mehrere, eigene, gebunden, moeglich) und `aktiv.firma`; Entwurfsmodus je Firma (`Einstellungen.vordrucke_ohne_entwurf` mit `art@firma`, Prüfung über `vordruck_schluessel_gueltig` – gilt nun auch für „firmen“). Eigene Schreiben haben ihre Firma selbst (`EigenesSchreiben.firma`). Oberfläche: Chips „gemeinsam“/„eigene Vorlage RGC“, Hinweis im Editor, Knöpfe „Eigene Vorlage für … anlegen“ und „Eigene Vorlage entfernen“ mit Rückfrage; Hilfe „Dokumentvorlagen“. Tests `vorlagen/tests.py` (`VorlagenJeFirma`). |
| 13.10.2026 | Fehlertexte der API an einer Stelle | `epm/fehlertexte.py` ersetzt die DRF-Standardtexte („Dieses Feld ist zwingend erforderlich.“, „Gib eine gültige E-Mail Adresse an.“, „Stelle sicher, dass … nicht mehr als 100 Zeichen …“) für alle Felder durch kurze Sätze im Ton der Oberfläche: „Bitte ausfüllen.“, „Bitte eine gültige E-Mail-Adresse angeben.“, „Höchstens {max_length} Zeichen.“, „Bitte als TT.MM.JJJJ angeben.“, „„x“ steht nicht zur Auswahl.“, „Eintrag 7 gibt es nicht (mehr).“, „Gibt es schon – bitte einen anderen Wert wählen.“ (auch für `unique=True` am Modell). Angewendet beim Start (`epm/apps.py`, App `epm` in `INSTALLED_APPS`); eigene `error_messages` einzelner Felder bleiben. Test `epm/test_fehlertexte.py` |
| 13.10.2026 | Testpatienten im echten Betrieb (Kundenfrage) | Geprüft und mit `patienten/test_testpatienten_sichtbar.py` festgehalten: Ohne das Recht „Testdaten sehen“ (je Gruppe unter Administration › Benutzer › Rechte) gibt es Testpatienten für diese Person nirgends – Liste, Suche, Zähler, Doppelungsprüfung, Kalender, Startseite, Merkliste, Infusionspläne, Termine, Kontakte, Berichte, Befunde, Gewichte, Dokumente, Versorger-Akten, Scan-Zuordnung (alles über `epm.api_basis.patienten_fuer`); direkte Aufrufe liefern 404, Anlegen 400. Keine Lücke gefunden. Einrichtung in der Praxis: Recht „Testdaten sehen“ für Betrachter, Mitarbeiter und Mediziner ausschalten (Admins behalten es fest), Testbenutzer unter Benutzer „ausblenden“; wer Testpatienten braucht, bekommt sie als Testbenutzer |
| 13.10.2026 | Oberfläche: Dialoge, Pflichtfelder, Reiter, Hilfe | Dialoge „Neu“ beginnen leer (Labor, BIA, Berichte, Termin; Kontaktpersonen, Kontakt und Gewicht verwerfen den letzten Fehler) – vorher standen die Werte des zuletzt bearbeiteten Eintrags noch drin. Pflichtfeld-Fehler in „Neuer Patient“, Stammdaten-Dialog und „Neu anlegen“ (Arzt/Versorger) verschwinden, sobald das Feld stimmt; die Zusammenfassung „n Felder sind rot markiert“ zählt mit. Reiter der Akte zwischen 768 und 1600 px kompakt und seitlich wischbar statt in zwei Zeilen (jeder Bereich bleibt ein Reiter, F121). Hilfe `benutzer`, `kalender`, `notfallcodes`: kürzere Sätze, Listen |
| 13.10.2026 | Vorlagen der Regeneration Clinic | 19 Word-Vorlagen der RGC als eigene Schreiben der Firma RGC (Datenmigration `vorlagen/0007`, Quelle `vorlagen/statisch/rgc/*.json`, umgesetzt mit `werkzeuge/rgc-vorlagen.py`): 14 Anforderungen (Labor 01–10, MRT, Röntgen, Echokardiographie, EKG/Funktionsdiagnostik, zweisprachig LV/DE) und 5 Formulare (Schweigepflichtentbindung, Aufklärung Operation und Anästhesie DE/LV, Rückerstattung und Abtretung ÖGK). Patientendaten als Datenfelder (Name, Geburtsdatum, Anschrift, Patienten-ID, Datum, Versicherung, Versichertennummer, E-Mail, Telefon, Diagnosen mit ICD), der Rest zum Ankreuzen bzw. Ausfüllen; Fett/kursiv innerhalb eines Absatzes entfällt. `EigenesSchreiben.firma` (nur in dieser Firma sichtbar; ohne aktive Firma gilt die DSKM; neue eigene Vorlagen gehören der aktiven Firma), `gruppe` (neu „anforderungen“, „formulare“; in der Akte als eigene Gruppen) und `mitgeliefert` (Migration `vorlagen/0006`). Textblöcke mit Option `spalten` 2/3. Briefkopf der RGC aus den Vorlagen vorbelegt (nur leere Felder). Neue Vorlagen der RGC: `werkzeuge/rgc-vorlagen.py ORDNER` und eine weitere Datenmigration. Tests `vorlagen/test_rgc.py`. |
| 11.10.2026 | Zugang: SSH auf Zeit, erlaubte Netze, Firewall | Neuer Reiter Administration › System › Zugang. SSH ist im Betrieb aus und wird für 1, 4 oder 8 Stunden geöffnet (Passwort und 2FA; wahlweise nur für die eigene Adresse, befristet); der Status-Lauf des Systemagenten (jede Minute) schließt es danach selbst (ufw-Regeln des SSH-Ports weg, `systemctl disable --now ssh.socket ssh.service`) und meldet das ins Audit-Log (`ssh_automatisch`). Bestehende Server: ohne `/etc/epm/zugang.json` gilt SSH als „dauerhaft offen (Ersteinrichtung)“ – nichts schließt sich von selbst. Erlaubte Netze je Dienst (HTTPS/SSH, bis 20, CIDR geprüft, nichts breiter als /8 bzw. /32, für EPM nur IPv4; 0.0.0.0/0 nur für EPM und nur ausdrücklich bestätigt), Schutz vor dem Aussperren (nie das letzte HTTPS-Netz, nie das Netz der Geräteadresse laut Nginx/`client_ip`, im Backend und im Agenten geprüft). „Netzfilter für EPM“ (Kette `EPM-HTTPS` aus `DOCKER-USER`), weil Docker ufw bei veröffentlichten Ports umgeht. Stand von ufw (Standards, Regeln) und Fail2ban (Jails, gesperrte Adressen, „Entsperren“) im Status des Agenten. Endpunkte `/api/system/zugang/…`, Agent-Aktionen `ssh_oeffnen`, `ssh_schliessen`, `netz_hinzufuegen`, `netz_entfernen`, `https_filter`, `fail2ban_entsperren`, Agent-Befehl `zugang-anwenden` (aus `rollout/03-security.sh` nach `ufw --force reset`). Tests `system/test_zugang.py`. |
| 11.10.2026 | Schalter „Technische Verwaltung“ | Django-Admin und API-Browseroberfläche schaltet ein Admin unter Administration › System › Wartung für 1 oder 8 Stunden ein (`PUT /api/system/technik/ {stunden}`, `Einstellungen.technik_bis`, Migration `stammdaten/0023`); danach von selbst aus, Audit-Log. `epm/technik.py`: `TechnikMiddleware` (404 auf `/verwaltung/`, solange aus) und Inhaltsverhandlung ohne Browseroberfläche. `EPM_DJANGO_ADMIN`/`EPM_API_BROWSABLE` in `backend.env` legen fest (dann wirkt der Schalter nicht); `rollout/04-projekt.sh` entfernt die zuvor gesetzten „=0“ einmalig (Markierung `# epm: verwaltung-schalter`) und legt `backend.env` nicht mehr neu an, nur weil `EPM_DJANGO_ADMIN` fehlt. Entwicklung: `DB_CONN_MAX_AGE`. Tests: `system/test_technik.py`. |
| 11.10.2026 | WeasyPrint 70, Verwaltung aus | WeasyPrint `>=70,<71` (schließt CVE-2026-106443; PDFs unverändert). Django-Admin (`/verwaltung/`) und API-Browseroberfläche standardmäßig aus (`EPM_DJANGO_ADMIN`, `EPM_API_BROWSABLE`); `rollout/04-projekt.sh` schaltet beides bei `epm-update` auf bestehenden Servern einmalig ab (Markierung in `backend.env`, ein späteres bewusstes Einschalten bleibt). |
| 11.10.2026 | Rollen nur durch Admins der jeweiligen Firma | Festlegung: Rollen einer Firma vergibt nur, wer dort selbst Admin ist (`admin_firmen` in `epm/firma.py`, Prüfung im `BenutzerSerializer`; „Login geben“ vergibt die Rolle in der aktiven Firma; „ohne Login“ nur, wenn man in allen Firmen der Person Admin ist). Oberfläche: Rollen-Auswahl fremder Firmen gesperrt mit Hinweis; neue Benutzer erhalten eine Rolle nur in der aktiven Firma. Behoben: Rollen weiterer Firmen wurden beim Anlegen nicht gespeichert. Zweiter Faktor bleibt freiwillig (Festlegung). |
| 11.10.2026 | Musterdaten erweitert | Alle sechs Testpatienten mit Therapie (Text „Aktuell“ je Patient und Verlauf in 2–5 Schritten, `TEST_THERAPIE`), Medikamentenplan (Dauer-, Bedarfs- und abgesetzte Medikation; Demo, Karl mit abgesetzten nach Abschluss), je einer weiteren Diagnose (Mustermann, Beispiel, Probe, Test, Demo), älteren Labor- und BIA-Befunden (Mustermann: 4 Labore inkl. Vitamin D und Calprotectin, 4 BIA; Probe: 3 Labore inkl. Ferritin/Hämoglobin). Hinweise der Profile (kein Labor/keine BIA bei Test, alte Befunde bei Beispiel/Probe) bleiben. |
| 11.10.2026 | Stammzertifikat für alle | Wunsch „Zertifikat exportierbar“: Download des Stammzertifikats (`/epm-ca.crt`, öffentlich, ohne Schlüssel) für jede Person unter Mein Konto › Gerät einrichten und auf der Anmeldeseite („Dieses Gerät einrichten“), mit Anleitung je Gerät (Windows, Mac, iPhone/iPad, Android). Für iPhone/iPad ein Profil `/epm-ca.mobileconfig` (`epm-zertifikat` schreibt es, Nginx liefert es; fehlt es, baut der Browser es aus dem Zertifikat). Komponente `Stammzertifikat.tsx`, auch unter Administration › System › Zertifikat. |
| 11.10.2026 | Medikamentenplan | Kundenwunsch „Medikamentenplan als neuer Punkt beim Patienten“: Modell `patienten.Medikament` (Migration `patienten/0021`, mit Historie, Firma je Eintrag) nach dem bundeseinheitlichen Medikationsplan – Wirkstoff, Handelsname, Stärke, Darreichungsform, Dosierung morgens/mittags/abends/zur Nacht oder frei, Einheit, Bedarfsmedikation, Hinweise, Grund, seit; nie gelöscht, sondern abgesetzt (Datum, Grund). API `/api/medikamente/?patient=&aktiv=&bedarf=` (Recht „Akten bearbeiten“ zum Schreiben), `POST …/{id}/absetzen/` (`absetzgrund`, `abgesetzt_am`) und `…/{id}/ansetzen/`; Zähler `kopf.zaehler.medikamente`; Verlauf (Bereich `medikamente`), Kopie der Akte und endgültiges Löschen (`akten_entfernen`, Historie) berücksichtigen die Medikamente. Neue Dokumentvorlage **Medikationsplan** (`vorlagen` Art `medikationsplan`, Tabellen `medikamente` und `bedarfsmedikation`) und `GET /api/patienten/{id}/medikationsplan-pdf/` (Audit EXPORT). Oberfläche: Reiter „Medikamente“ nach „Diagnosen“ (Tabelle am PC, Karten am Telefon, „Abgesetzt“ aufklappbar), Karteikarte (Kürzel M), Hinweis in der Übersicht, Hilfe „Medikamentenplan“; Musterdaten mit Medikamenten bei drei Testpatienten. |
| 11.10.2026 | Neutrale Anmeldeseite | Vor der Anmeldung keine Firma im Vordergrund: Fläche in Schiefer-Petrol mit Pulslinie und Leitsatz, eigene EPM-Wortmarke (`EpmMarke.tsx`), neutraler Akzent; unten „Gemeinsam genutzt von …“ aus `organisation.firmen` (`/api/auth/status/`). Logo und Farben der Firma erscheinen nach der Anmeldung. |
| 11.10.2026 | Regeneration Clinic in eigenen Farben | Farbliche Trennung der Firmen: in der RGC Seitenleiste, Kopfzeile, Menüleiste und Schublade in Salbeigrün (#BEC9C3), Akzent Anthrazit (#23262B) nach dem Auftritt der Klinik (`index.css`, `data-firma`, Token `--leiste`); mitgeliefertes Logo der Klinik (`logo-rgc.png`, hell in „Dunkel“; auch auf PDFs, solange kein eigenes hochgeladen ist). **Design je Firma**: Farbeinstellungen (Schema, Akzent, Hintergrund) gelten je Firma, „Standard“ = Farben der Firma; Dichte, Schrift und Aufbau der Akte gelten in beiden (`darstellung["firmen"]`). Neue Farben „Anthrazit (RGC)“, „Salbeigrün (RGC)“, Hintergrund „Salbei (RGC)“. Kurzname „RGC“ statt „RG“ (Migration `stammdaten/0022`). |
| 11.10.2026 | Zwei Firmen: DSKM und Regeneration Clinic | Neue Anforderung: EPM für DSKM und RG. `stammdaten.Firma` (Migrationen `stammdaten/0021`, `patienten/0019–0020`, `accounts/0010` u. a.): alle bestehenden Akten, Einträge und Logos gehören der DSKM. **Aktive Firma** je Sitzung (`epm/firma.py`, `FirmaMiddleware`, `POST /api/auth/firma/`), Umschalter unter dem Logo (Seitenleiste, schmale Leiste als Kürzel, Telefon in der Schublade, Firma im Kopf). **Rolle je Firma**: DSKM = `User.rolle`, weitere Firmen `accounts.Mitgliedschaft`; Rechte nach der Rolle der aktiven Firma (`wirksame_rolle`), Benutzerverwaltung mit „Rolle DSKM“/„Rolle RG“ (`firmenrollen`). **Akten je Firma** (`patienten.PatientFirma`): `patienten_fuer` filtert nach der aktiven Firma; neue Akten gehören der aktiven Firma; zweite Firma nur mit Einwilligung zum Austausch (neue Erklärungsart `firmen` samt Vordruck, `POST /api/patienten/{id}/firmen/`, Audit `akte_firmen`); Auswahl beim Anlegen und im Aktenkopf (Chip „DSKM · RG“, Dialog „Betreuende Firmen“). **Gemeinsame Akte**: jeder Eintrag vermerkt die Firma (`AktenEintrag.firma`, `firma_kurz`), angezeigt als kleine Marke. **Gemischte Stammdaten**: Logo und Absender je Firma (Absender `rg`), Versorger, Ärzte, Präparate, Laborparameter, Auswahllisten und Grenzwerte gemeinsam. Scans je Firma. **Import nur DSKM** (Recht `altdaten_importieren` entfällt in Firmen ohne `altdaten`). Löschen nach Art. 17 entfernt auch die Historie der Zuordnung. Musterdaten: Max Mustermann (aufgenommen bei der DSKM) und Hanna Test (aufgenommen bei der RG) in beiden Firmen; Testzugang auch in der RG. Tests: `patienten/test_firmen.py` (10), `e2e/firmen.spec.ts` (3). |
| 11.10.2026 | Hinweise und Erreichbarkeit | „Kein Gewicht seit X Mon.“ bei neuen Akten erst X Monate nach dem Anlegen (`luecken.py`); „Nickelallergie nicht erfasst“ als Hinweis der Akte (Art `nickelallergie`, Migration `patienten/0018`), wegklickbar wie die übrigen, entfällt bei „kein Katheter“, zählt in Prüfliste und Filter nur offen (`kennzahlen.nickel_offen`); Kontakte › Erreichbarkeit zeigt Bezugspersonen mit Auskunftserlaubnis; Rezept für eine intuitive Web-App `docs/PWA-REZEPT-2026-10-11.md` |
| 11.10.2026 | Musterdaten mit Befunden | Testpatienten (`patienten/testdaten.py`, auch „Testdaten zurücksetzen“ und `epm_musterdaten`) bringen Diagnosen mit ICD-Code und Kennzeichen (je 2–4, eine beendet), Laborbefunde (bis zu 4 Zeitpunkte, Referenzbereich je Zeile, Werte teils außerhalb – z. B. Magnesium fallend bei Musterfrau, sichtbar im Plan-Editor) und BIA-Messungen (bis zu 3 Zeitpunkte, Gewicht aus dem Verlauf, ohne Übernahme) mit; Test, Hanna bewusst ohne Labor und BIA („Kein Laborbefund“/„Keine BIA-Messung“), Beispiel, Paula mit altem Labor, Probe, Jonas mit alter BIA. Gleiche Prüfungen wie über die API (`full_clean`), neue Diagnosen wandern in die Liste unter Vorlagen › Diagnosen (U53); bisherige Musterdaten unverändert. Backend-Tests `patienten/test_testdaten_befunde.py`, Browsertest `e2e/testdaten-befunde.spec.ts` (Lauf steht aus) |
| 11.10.2026 | Hilfe mit Bildern | Wunsch „Seiteninterne Hilfe mit Screenshots und kurzen animierten GIFs“: 12 Bildschirmfotos und 3 GIFs (Patient suchen, Kontakt erfassen, am Telefon offenen Punkt antippen) in 14 Abschnitten, nur Testpatienten, wichtige Knöpfe rot umrandet; `<figure class="hilfe-bild">` mit Alternativtext und Bildunterschrift, GIFs in `<picture>` mit Standbild für „Bewegung reduzieren“, PC-Bilder öffnen per Klick groß. Dateien in `frontend/public/hilfe-bilder/` (zusammen ca. 1,6 MB), erzeugt mit `node werkzeuge/hilfe-bilder.mjs` (Playwright, PC 1366×768 bzw. 1366×1000 für Fenster, Telefon 390×844 doppelt aufgelöst; `werkzeuge/hilfe-gif.py` setzt GIFs mit Pillow zusammen). Nginx: `/hilfe-bilder/` mit 404 statt App-Seite, einen Tag zwischengespeichert. Test `test_bilder_vorhanden_und_beschrieben`. Nebenbei behoben: Fenster (Dialoge) und Trefferliste der Suche rutschten seit „Verweise führen zur Stelle“ ans Seitenende (Kartenregel `position: relative` traf auch feste Karten); Suche der Hilfe liest Texte ohne Bilder zu laden |
| 11.10.2026 | Verweise führen zur Stelle | Klick auf offene Punkte (Liste, Aktenkopf) führt zum passenden Reiter bzw. Dialog (`frontend/src/lib/sprungziele.ts`: Labor, BIA, Pläne, Kontakte, Diagnosen, Stammdaten, Gewicht); Termine (Patientenliste, Startseite, Aktenkopf, Kontakte, Übersicht) öffnen „Termin bearbeiten“, ohne Recht bzw. erledigt den Kalender an diesem Tag. „Nickelallergie nicht erfasst“ als Hinweis wie die übrigen, auch im Aktenkopf. Dokumentvorschau öffnet das Dokument groß. Chips brechen um statt herauszuragen. Terminbestätigung „Schon bestätigt …“ (telefonisch, persönlich, anderweitig): `POST /api/termine/{id}/bestaetigt/ {weg}`, Feld `bestaetigung_weg` (Migration `patienten/0017`), im Verlauf „Terminbestätigung telefonisch“ usw.; verschoben = fehlt wieder |
| 11.10.2026 | Versionsnummer automatisch | Letzte Stelle der Version zählt je Änderung auf main hoch (`werkzeuge/version.sh`, genutzt von `epm-update`, `bauen.sh`/`bauen.ps1`, Update- und Notfallpaket); VERSION bleibt der von Hand gesetzte Grundstand (2.0.0 → 2.0.1 mit PR #45, 2.0.2 mit diesem Stand). Benutzer am Telefon: Formular direkt unter der Liste |
| 10.10.2026 | Entscheidungen der Praxis | Tablet mit zwei Spalten und Scrollen, Mengen je kg unter Vorlagen › Grenzwerte (Migration mit den Werten des Altsystems, Historie, Audit-Log, Stand im Plan-Editor), Gewicht für den Plan nach 6 Monaten „bitte prüfen“ (einstellbar), Labor-Hinweise ab Freigabe des letzten Plans (entschieden), Laborparameter „Ohne Referenzbereich“ zum Nachtragen und Hinweis im Plan-Editor, Telefontermine bleiben vom Infoblatt aus (U72) (F190). Lauf steht aus |
| 10.10.2026 | Version 2.0.0 | Zweite Fassung von EPM: Versionsnummer von 0.2.0 auf 2.0.0 (Festlegung Filip 10.10.2026); enthält F177–F189. Images heißen `epm-backend:2.0.0-<Commit>` |
| 10.10.2026 | Hinweise im Infusionsplan | Plan-Editor zeigt Laborwerte außerhalb des Referenzbereichs seit dem letzten Plan (nur Bestandteile des Plans) mit Verlauf der letzten drei Werte, deutliche Gewichtsänderung, Entwicklung der eigenen Pläne und fehlendes Labor mit „Blutuntersuchung anfordern“ – nur zum Prüfen, ohne Dosisvorschlag (MDR) (F187). Lauf steht aus |
| 10.10.2026 | Erkennung verbessern | „Falsch erkannt“ mit Grund (verwirft sofort, lernt „nicht auswerten“/Sperre/weniger Bestätigungen je Labor), „Bereich markieren“ liest nur den aufgezogenen Rahmen mit Tesseract neu (Maus und Touch, Tabelle zeilenweise) und lernt den Bereich je Labor, Steuerung des Lernens (pausieren, Schwelle 1–3), Anleitung in Hilfe, Prüfansicht und `docs/SCANS-VERBESSERN.md` (F189). Lauf steht aus |
| 10.10.2026 | Notfallpaket | Notfallpaket mit Images, Rollout-Skripten, Debian-Paketen, OCR-Modellen, wahlweise jüngster Sicherung, Einstellungen ohne Geheimnisse, verschlüsseltem CA-Schlüssel, Prüfsummen und Plan; Aufbauskript `epm-notfall-aufbau.sh` mit Probelauf, Offline-Modus der Rollout-Skripte, Reiter „Notfall“, Ampel-Kachel, `docs/NOTFALLPLAN.md` (F188). Lauf steht aus |
| 10.10.2026 | Nachtrag Systemverwaltung | Zeitplan der nächtlichen Sicherung (Uhrzeit, täglich/werktags, Warnung zum Übertragungsfenster), Journal und alte Versionen aufräumen (laufende und vorherige geschützt), Uhrzeit mit eigenem Zeitserver einstellen, OCR-Modelle mit 2FA (F179l–F179o). Lauf steht aus |
| 10.10.2026 | Texterkennung lernt mit | Gelernte Zuordnungen aus Korrekturen beim Übernehmen (Labor, BIA, Diagnosen, Spaltenlage je Labor; ohne Patientendaten), Anwendung vor der Ähnlichkeitssuche mit Schwelle, Bereich „Gelernte Zuordnungen“, Kennzahl „korrigiert“ (F182); Patient aus Name und Geburtsdatum vorschlagen, nur per Klick (F183); Offline-Prüfung (`docs/OFFLINE-BETRIEB-2026-10-10.md`). Lauf steht aus |
| 10.10.2026 | Akte entschlankt | Akte ab 1024 × 600 px ohne Seiten-Scrollen (Kopf und Reiter bleiben stehen, Inhalt scrollt in Karte bzw. Spalte), kompakter Kopf, Reiter nach Bedeutung (Infusionspläne nach Empfehlung, Verlauf/Datenschutz klein), Übersicht mit sechs Karten in zwei Reihen, PDF des Plans in voller Höhe neben der Liste und im Menüpunkt Infusionspläne, Plan nach Praxisvorgabe je kg, Prüfung vor der Freigabe, PDF-Vorschau mit ungespeicherten Eingaben (`POST …/vorschau/`), Administration zum Aufklappen (F181). Lauf steht aus |
| 10.10.2026 | Automatisierungen für die Pflege | Startseite „Heute zu tun“ mit Terminen, Rückrufen, Infoblatt, fehlenden Bestätigungen, Kontakten, Plänen, Scans und fehlenden Angaben (F184); „Terminbestätigung schicken?“ nach dem Speichern eines Praxistermins mit Vermerk am Termin (F185); fehlende Angaben als Hinweise (Hausarzt, Telefon, Gewicht, Diagnose, Termin ohne Ort), ausblendbar (F186). Lauf steht aus |
| 10.10.2026 | Systemverwaltung ohne SSH | Neue Seite Systemverwaltung mit Ampel und häufigen Aufgaben; System und Backup in Reitern; Graphen klein, groß im Dialog; Sicherungen mit Mehrfachauswahl löschen; Dienste einzeln neu starten, Version zurückschalten, Update-Paket und OCR-Modelle hochladen, Paket erstellen, Zertifikat erneuern/importieren, Protokolle ansehen – alles über den Systemagenten (F179). Lauf steht aus |
| 10.10.2026 | Vorlagen-Portal einfacher | Übersicht mit Kacheln in Alltagssprache und Suche, Liste der Dokumentvorlagen mit Zweck/Ort/Stand, geführter Ablauf Bearbeiten → Vorschau → Freigeben mit Live-Vorschau, Angaben aus der Akte per Klick als lesbare Chips, frühere Fassung ansehen/wiederherstellen, als eigene Vorlage kopieren, ▲ ▼ und „Wo benutzt“ in den Auswahllisten, Warnung beim Verlassen (F180). Lauf steht aus |
| 10.10.2026 | Bedienung für Pflegekräfte | Nachsichtige Datums-/Uhrzeiteingabe, Fehlermeldungen mit Lösungsweg, leere Zustände mit nächstem Schritt, Hilfe „Die wichtigsten Wege im Alltag“ und „Wenn etwas nicht klappt“, weniger Fachjargon (F178, `docs/BEDIENBARKEIT-2026-10-10.md`). Lauf steht aus |
| 10.10.2026 | Infoblatt an die Praxis | Kalender › „Praxis informieren“: Infoblatt mit allen Terminen in der Praxis Holtmeier, Zeitraum per Knopf, Vorschau mit „neu“ und Warnung bei fehlendem Ort, nur Termine am gewählten Ort (Telefon/Video wahlweise), gemerkte Blätter ohne Namen, Erinnerung auf der Startseite, Ort im Termin vorbelegt (F177). Lauf steht aus |
| 09.10.2026 | Schreiben mit E-Mail | Vorlagen von Alice: Patientenaufnahme, Terminbestätigung, Reisebescheinigung mit ADAC-Attest als PDF und als fertige E-Mail (.eml mit Anhang) aus der Akte (F172), Patientenankündigung aus dem Kalender (F173), Anlagen für E-Mails (F174), Fallzusammenfassung mit Gliederung (F175). Lauf steht aus |
| 09.10.2026 | Text erkennen in der Akte | „Text erkennen“ mit OCRmyPDF (PDF/A mit Textebene, Datei ersetzt, Art.-17-Löschung über alle Fassungen) (F170), „Werte übernehmen“ aus Akte-Dokumenten ohne neues Dokument (F171), Sparmodus mit einem Tesseract-Durchgang (F168). Lauf steht aus |
| 09.10.2026 | Texterkennung auf kleinen Servern, Werte von Hand | Sparmodus (kleines Zeilenmodell, ohne Glätten) und Speichergrenze nach RAM, Absturzschutz mit Lebenszeichen und Sparstufen je Seite (F168); Labor/BIA immer übertragbar, Wert per Klick ins Bild, „+ Wert“, mehr BIA-Bezeichnungen (F169). Lauf steht aus |
| 09.10.2026 | OCR-Modelle offline | `ocr-modelle.sh vorbereiten/einspielen/status`, `ocr-modelle.ps1`, `epm-update` baut die Modelle ein und meldet den Stand der Texterkennung (U67) |
| 09.10.2026 | Scans: Rückmeldungen | U65–U71 geklärt bzw. bestätigt; OCR-Knopf für Akten-Dokumente, BIA-Bezeichnungen und Modelle im Update folgen |
| 09.10.2026 | Scans und Texterkennung | Neuer Menüpunkt „Scans“: Hochladen, Seite anpassen, Erkennung ohne externen Dienst (Tesseract best + PP-OCRv5, OCR-Dienst), Text kopieren, Zuordnen mit Übernahme von Labor/BIA/Diagnosen, Aufbewahrung 7/7/30 Tage mit Bereinigung (F160–F167). Lauf steht aus |
| 09.10.2026 | Design eigener Menüpunkt | Design (/design) und Mein Konto (/konto) getrennt, beide im Benutzermenü (F158). Lauf steht aus |
| 08.10.2026 | Rest der Vorschläge | Stift an „Versorgung“, Messpunkt bearbeiten, „Neues Dokument“ (F157). Damit ist „EPM intuitiver – Vorschläge“ vollständig umgesetzt. Lauf steht aus |
| 08.10.2026 | Versorger/Ärzte, Kalender | Neuer Aufbau nach den Entwürfen für PC, Tablet und Telefon: Liste + Eintrag zum Lesen, Kalender mit einer Werkzeugzeile, „Anzeigen ▾“ und Reitern (F156). Lauf steht aus |
| 08.10.2026 | Tastenkürzel | K, G, T, P, Alt+Ziffer und ? in der Akte, Strg Enter in Dialogen, Kürzel im Tooltip (F155). Lauf steht aus |
| 08.10.2026 | Ein Suchfeld, Prüfen, Hilfe | Kopfzeile filtert die Patientenliste, „Prüfen …“ wählbar, Erklärtexte in die Hilfe, leere Reiter ohne Doppelhinweis (F154). Lauf steht aus |
| 08.10.2026 | Eine Sprache | Bearbeiten/Speichern/Abbrechen/Erledigt/Deaktivieren überall; Rückfrage vor Bericht verwerfen, Diagnose beenden, Deaktivieren; roter Knopf links (F153). Lauf steht aus |
| 08.10.2026 | Bearbeiten sichtbar | „Bearbeiten“ auf Anschrift und Kontakt, Kalender öffnet „Termin ändern“ mit „Erledigt“, Karteikarte springt zum Eintrag, Therapie/Empfehlung erst lesen, Größen-Symbol (F152). Lauf steht aus |
| 08.10.2026 | Weniger Wege | „Entwurf fortsetzen“ im Aktenkopf, Dokumente aus dem Kopf und per Ziehen auf die Akte, Arzt/Versorger im Dialog anlegen (F151). Lauf steht aus |
| 08.10.2026 | Ein Dialog je Sache | „Neuer Kontakt“, „+ Gewicht“, Kürzelzeile K/G öffnen dieselben Dialoge; letzte Messung direkt korrigieren; Wiedervorlage standardmäßig 14 Tage, unter Vorlagen › Grenzwerte einstellbar (F150). Lauf steht aus |
| 08.10.2026 | Kontakt/Gewicht als Dialog | Akte: „Kontakt“ und „Gewicht“ öffnen Dialoge wie „Termin“ (F149). Lauf steht aus |
| 08.10.2026 | Navigation | Gleich große, mittige Symbole in der schmalen Leiste, Leiste mit Text 224 px, gleich breite Hauptknöpfe, kompakte Leerzustände (F148). Entwürfe für Versorger/Ärzte und Kalender (PC, Tablet, Telefon) zur Abstimmung. Lauf steht aus |
| 08.10.2026 | Ohne Scrollen auf 1080p | Versorger/Ärzte-Formular im 6-Spalten-Raster, engere Felder, Kalender in Fensterhöhe, Benutzermenü bündig (F147). Lauf steht aus |
| 08.10.2026 | Einheitlich und kompakt | Seitenkopf einzeilig auf allen Seiten, gleiche Steuerhöhen (Umschalter = Knöpfe), Dichte „Normal“ 32 px, Karten mit 16/12 px Innenabstand, Scrollbalken-Platz reserviert gegen Springen; Suche bei Versorger (F146). Lauf steht aus |
| 08.10.2026 | Form entfernt, weniger Leerraum | Form „Rund/Eckig“ samt Menüpunkt entfernt (F139); gespeicherte Werte werden verworfen. Stattdessen für alle weniger Rand und kleinere Abstände zwischen den Karten (F145). Dabei aufgefallen: Das Feld `form` war im Backend nie angekommen – „Eckig“ hätte sich auf der Test-VM nicht speichern lassen; mit dem Entfernen erledigt |
| 08.10.2026 | Behebung nach `epm-update` | Frontend baute nicht: In `RuheDialog` (F142) lieferte die Speicherfunktion je nach Ziel einen Termin oder eine Hinweisruhe – TypeScript verlangte einen Typ (`HinweisChips.tsx`, Rückgabe jetzt `Promise<unknown>`). Backend-Image samt Migration `patienten/0012` lief auf der Test-VM ohne Befund durch |
| 08.10.2026 | Rückmeldungen (Wunsch 08.10.2026) | Grünes bzw. rotes Overlay oben in der Mitte wie im alten EPM: grün ca. 3 s, rot ca. 9 s, „×“ schließt (F144). Lauf steht aus (GitHub Actions wegen Abrechnung gesperrt) |
| 08.10.2026 | Kalender ausblenden, Griffe (Wunsch 08.10.2026) | „×“ an jedem Kalendereintrag: Fälligkeiten schalten den Hinweis der Akte stumm, Termine werden mit Frist oder „nicht mehr nötig“ und Grund ausgeblendet und lassen sich in der Akte zurückholen (F142, Migration `patienten/0012`, von Hand geschrieben – `makemigrations --check` auf der Test-VM prüft sie). Der Kalender berücksichtigt jetzt auch stummgeschaltete Hinweise (vorher nicht). Teiler ohne Punkte-Griff, beim Überfahren hervorgehoben (F143). Lauf steht aus (GitHub Actions wegen Abrechnung gesperrt) |
| 08.10.2026 | Form, Fortschritt, Benutzermenü (Wunsch 08.10.2026) | Ladebalken 5 px, in „Individuell“ in der Akzentfarbe (F137); Fortschritt laufender Aufträge mit ungefährer Restzeit aus der Dauer früherer Aufträge, Karte „Laufende Tätigkeiten“ auf Backup und System (F138); Form „Rund“/„Eckig“ unter Mein Konto, eckig ohne Rundungen und ohne Abstände zwischen den Karten (F139, `darstellung.form`, ohne Migration); unten links nur die Person, Hilfe/Mein Konto/Abmelden im Menü (F140); Patientenliste ohne Vorschau, Klick auf die Zeile öffnet die Akte (F141). GitHub Actions startete wegen der Abrechnung des Kontos weiterhin keine Jobs; die Tests sind geschrieben, der Lauf steht aus |
| 08.10.2026 | Aufbau der Patientenakte (Wunsch 08.10.2026) | Drei Ansichten der Akte je Person unter Mein Konto › Patientenakte (F135): Kopfzeile mit den Angaben in vier Gruppen und Griff für die Höhe (nur Name · eine Zeile · alle Angaben), Seitenleiste mit Knöpfen über dem Namen, ziehbarer Breite (240–480 px, rastet ein) und senkrechten Reitern, Karteikarte wie in einer Arztsoftware mit fester Spalte rechts. Karteikarte mit allen Einträgen chronologisch, Filter, Zeitraum und Kürzelzeile K/G/T/WV/P (F136, neuer Reiter `kartei`). Darstellung um `aktenansicht`, `aktenkopf`, `aktenleiste_breite` erweitert (ohne Migration). CAVE (Nickelallergie, Gewichtsverlust) steht jetzt in jeder Ansicht beim Namen. Das Menü links ist unverändert. Die Arbeitsumgebung hatte keinen Zugriff auf PyPI, npm und Docker Hub, GitHub Actions startete wegen der Abrechnung des Kontos keine Jobs – Backend-Test und Browsertest sind geschrieben, aber noch nicht gelaufen (zuerst auf der Test-VM mit `sudo epm-update`) |
| 08.10.2026 | Passkey und Telefon (Pull Request #14) | Passkeys (WebAuthn) als zweiter Faktor statt oder neben dem Authenticator-Code – einrichten, umbenennen, entfernen unter Mein Konto, Anmeldung und alle Bestätigungen mit Passkey (F130–F132; Modell `accounts.Passkey` als django-otp-Gerät, Migration `accounts/0008`, `py_webauthn` 2.x, Baustein `useZweiterFaktor` an allen Bestätigungen). Eigene CA mit Namensbeschränkung und Serverzertifikat (`sudo epm-zertifikat`, F134), Stammzertifikat unter `/epm-ca.crt`. Mobile Ansicht (F133): Leiste unten mit Notiz und Plänen, Menü als Schublade, Karten statt Tabellen, Akte mit Detail vor der Liste, Dialoge und Eingaben für Touch. Hilfe-Abschnitte „Passkey statt Code“ und „EPM am Telefon“. Offene Fragen U62, U63. Dabei gefunden und behoben: Wer den Passkey entfernte, mit dem die Sitzung bestätigt war, war danach abgemeldet (Sitzung läuft jetzt mit einem verbliebenen Gerät weiter). Nach den Bildschirmfotos am Telefon (Lauf 37710345563) behoben: Kartenköpfe (z. B. „Diagnosen und Therapie“ mit drei Knöpfen) brechen um statt die Seite zu verbreitern, die Spalte „Versichertennummer“ überlappte (auch am PC), der Kalender startet am Telefon als Liste. Browsertests „Ärzte zuordnen …“ und „Benutzer ohne Login …“ stabilisiert (Meldung genau bzw. die letzte gesucht). Lauf 37714211870: 347 von 347 Backend-Tests, 108 von 108 Browsertests |
| 06.10.2026 | Wünsche aus der Praxis (Alice, 06.10.2026) | Infusionstage je Beutelart mit Übernahme in den Folgeplan, Vergleich und PDF (F110, Migration `infusionen/0007`); Präparate nach der Mail – Zusatzvolumen umbenannt und ergänzt, Natrovit, NutriLock/TauroLock, Hinweisfeld am Präparat, Dipeptamin und Omegaven ausgeblendet (F111, Migrationen `stammdaten/0012`, `0013`); Katalog der Laborparameter mit Alices Liste und Erfassungsmaske nach Gruppen (F112, F113, neue App `befunde`); BIA-Maske mit Beurteilung und Übernahme des Gewichts (F114); Berichte in der Akte mit Entwurf/Freigabe, PDF als Dokument und Trigger-Schutz (F115, neue App `berichte`, neues Recht „Berichte freigeben“); Sprechstundenblatt (F116); Diagnosen mit ICD-Code und mitwachsendem Katalog (F117, Migration `patienten/0010`); Versichertendaten GKV/PKV, Versicherung, Versichertennummer (F118). Neue Dokumentvorlagen „Bericht“ und „Unterlagen für die Sprechstunde“ (Migration `vorlagen/0003`), Audit-Arten `bericht_freigegeben` und `sprechstunde_erzeugt` (`audit/0008`). Endgültiges Löschen, Kopie der Akte und Verlauf um die neuen Bereiche erweitert. Konzept und 22 offene Fragen (U39–U60) in `docs/WUENSCHE-PRAXIS-2026-10-06.md`. Die Migrationen sind von Hand geschrieben (die Arbeitsumgebung hatte keinen Zugriff auf PyPI und npm); `makemigrations` in CI meldet dazu „No changes detected“. Die neuen Apps stehen jetzt auch in der `makemigrations`-Zeile des Workflows. Lauf 37525732042: 311 von 311 Backend-Tests, 98 von 98 Browsertests. Davor fand CI drei echte Fehler, die hier behoben sind: der Plan-Serializer gab die neuen Infusionstage-Felder weder aus noch nahm er sie entgegen (dadurch griff auch deren Prüfung nicht), der ICD-Code wurde nicht in Großschreibung vereinheitlicht, und das Frontend baute wegen eines doppelten Schlüssels in der Feldliste des Verlaufs nicht. Nebenwirkung der Umbenennung: Beim Altdaten-Import trifft „Sterofundin“ keinen Katalogeintrag mehr automatisch und wird einmal von Hand auf „Sterofundin ISO“ gelegt (U43) |
| 07.10.2026 | Dokumente zurückgesetzt | Der Reiter Dokumente ist wieder in seiner ursprünglichen Form (Tabelle links, Details rechts); die übrigen Reiter behalten das gemeinsame Muster aus F122. Auf Wunsch ohne Testlauf eingespielt (`[skip ci]`); die Datei entspricht Zeile für Zeile dem Stand `8ccda52`, der zuletzt grün war |
| 07.10.2026 | Wünsche aus der Praxis (07.10.2026) | Hinweise mit „×“ ausblenden – beim Wegklicken 3, 6 oder 12 Monate Ruhe oder „nicht mehr nötig“, mit Grund, Person und Zeitpunkt, in der Akte unter „Ausgeblendete Hinweise“ zurückholbar, alles im Verlauf (F119, neues Modell `patienten.Hinweisruhe`, Migration `patienten/0011`); Grenzen „gilt als alt“ für Laborbefund und BIA-Messung, Standard 12 Monate, einstellbar unter Vorlagen › Grenzwerte, mit Hinweis je Akte, zwei neuen Zeilen in „Nach und nach prüfen“ und zwei neuen Filtern der Patientenliste (F120, Migration `stammdaten/0014`); ein eigener Reiter je Bereich – „Diagnose & Therapie“ wird zu „Diagnosen“ und „Therapie“ (mit „zuletzt geändert“), „Labor & BIA“ zu „Labor“ und „BIA“, mit Zählern, Weiterleitung der alten Adresse und neuer Karte „Labor und BIA“ in der Übersicht (F121). Dabei behoben: Die Karte „Bemerkung“ war nie in der Liste der verstellbaren Karten, ihr Menü „⋯“ lief ins Leere (seit F97). Eine weitere offene Frage: U61 |
| 03.10.2026 | Klärungen U3–U6, U31 (Branch `klaerungen-u3-u6-2026-10-03`) | Telefon 2, Krankenkasse und Bemerkung sichtbar und bearbeitbar, Bemerkung mit Versionen und eigenem Bereich im Verlauf (U5); Kontaktart beim Erfassen und in den Listen, Auswahlliste „Kontaktarten“ (U6); U3, U4, U31 bestätigt; F83 mit Browsertest abgeschlossen |
| 03.10.2026 | Klärungen U26–U33 (Branch `bereinigen-2026-10-03`) | Administration › System, Karte „Testphase und Go-live“: Datenbank leeren (F107, Systemagent-Aktion `datenbank_leeren`, Befehl `epm_datenbank_leeren`), Schalter „Musterdaten automatisch anlegen“ (F108) und „Import ausblenden“ (F109); Migration `stammdaten/0011`; U26, U28, U30, U32, U33 bestätigt, U27 geklärt. Systemagent über `sudo epm-update` aktualisieren |
| 03.10.2026 | Klärungen U7, U16–U24, U38 | Entwurfsmodus der Vordrucke manuell abschaltbar (F76, Migration `stammdaten/0010`); Aufbewahrung im Übertragungsziel, Standard 30 Tage, Systemagent räumt nach jeder Übertragung auf (F64, U21); Rolle „Mitarbeiter (erweitert)“ (Migration `accounts/0007`, U22); Testbenutzer der Musterdaten als Mitarbeiter (U7); U18, U19, U23, U24, U38 bestätigt |
| 02.10.2026 | Fehlerliste (Branch `fehlerliste-2026-10-02`) | Infusionspläne: Datum statt „heute/gestern“, Frist beim Überfahren des Status, kompakte Tabelle, Planansicht als kleine Vorschau mit großer Ansicht per Klick (F85, F31). Akte und System: Karten im Raster mit „⋯“ statt Teiler, je Person (F98); Kurz-Verlauf unter Kontakte entfernt. System: Zeitraum der Auslastung 1 h–6 Monate, Konten mit Links, größere Warnungen (F102). Backup: Herunterladen, Aufbewahrung 7/14/30 Tage, Hochladen und Einlesen (F103). Benutzer: ohne Login setzen/Login geben, Rolle „Keine Berechtigung“, Testbenutzer-Schalter (F100); Testpatient beim Anlegen (F101); Admins schließen Akten ab und ordnen Dokumente zu, auch bei echten Akten (F104); Zwei-Faktor-Anmeldung freiwillig (F99). Migration `accounts/0005`; Systemagent Version 3; neue Ordner `system/download`, `system/upload` (über `sudo epm-update`). U34–U36. Ergänzung: Hinweis „Kein Infusionsplan“ und Bestätigung „Kein Infusionsplan nötig“ je Patient (F105, Migration `patienten/0009`, U37). 03.10.2026: Recht „Testdaten sehen“ und Testbenutzer ausblenden (F106, Migration `accounts/0006`, U38). 03.10.2026: U34 geklärt – Bestätigungen immer mit zweitem Faktor, ohne eingerichteten Faktor abgewiesen; U35–U37 bestätigt |
| 02.10.2026 | Runde 7 (Startseite und Oberfläche, Pull Request #7: `f24bbb7`, `a6d1903`, `33612fa`) | S01–S17 aus `claude/startseite-erweiterungen.md` nach Entwurf 2, SU8–SU10 geklärt: Kennzahlenleiste, Kacheln im festen Raster mit Größe/Reihenfolge je Person und Ziehen mit Einrasten (F93), Schnellerfassung mit zwei Anfragen (F91), Meine Akten (F92), Kontakt fällig in zwei Stufen 4/6 Monate mit Datenmigration (F90), Admin-Startseite (F94), Hilfe je Rolle mit Ergänzungen (F95), volle Breite in Stufen (F96), Spaltenteiler ⅓/½/⅔ (F97); F09, F13, F14, F17, F48, F84 erweitert. Korrektur „Mit offenem Termin“ (zählte Akten ohne Termin). Kennzahlen ohne Testpatienten. Migrationen `stammdaten/0009`, `patienten/0008`, `accounts/0004`, `hilfe/0001`. Abgeleitete Punkte A1–A19 im Projekt-Dokument markiert. Lauf 37036210226: 236 von 236 Backend-Tests, 82 von 82 Browsertests (vorher Lauf 37033921101: ein Browsertest zog an einer Kachel außerhalb des Fensters – Testfehler, behoben) |
| 02.10.2026 | Behebung der Gegenprüfung (O-27 bis O-29) | `epm-backup.sh` entfernt bei einem Abbruch alle Dateien des Laufs (vorher blieb nach gescheitertem `tar` der Datenbank-Dump als unvollständige Sicherung liegen und wäre mit übertragen worden). `epm_loeschungen_nachholen` hält sein Ergebnis fest (Stand neben der Löschliste, Audit-Log, Hinweis auf Backup- und Startseite), zählt unlesbare Zeilen der Löschliste und endet mit `--streng` als Fehler; der Systemagent knüpft die Meldung des Wiederherstellens daran. Import: Patient, dessen Nummer im Löschprotokoll steht, erscheint als Auffälligkeit und lässt sich nur ausnehmen |
| 02.10.2026 | Gegenprüfung Datensicherung/Löschliste | `docs/DATENSCHUTZ.md` gegen `epm-backup.sh`, Systemagent und Start des Backends geprüft (Skript in einer Simulation gelaufen: verschlüsselt, Prüfsummen, Löschliste in der Sicherung, gescheiterter Dump hinterlässt nichts). Im Dokument ergänzt: unverschlüsselt ohne Passwort, Löschliste auf einem neuen Server, Nachholen nicht überwacht, Sicherung von vor dem Abschließen der Altdaten-Übernahme. Offen: O-27 bis O-29; U33 berichtigt |
| 02.10.2026 | Runde 6 (Altdaten-Import, Pull Request #5, in `main` als `26084ba`) | Werkzeug Administration › Import (F65) statt des geplanten Befehls `epm_import_alt` (Wunsch 02.10.2026): Dump im Browser laden, Zuordnungen prüfen und korrigieren, Probelauf, Import mit Kennwort + 2FA, Dokumente aus dem Ordner auf dem Server, Zurücknehmen, Abschließen; neues Recht „Altdaten übernehmen“ (nur Admin); Infusionspläne mit Herkunft „Altsystem“; unabhängige Prüfung mit 13 behobenen Befunden; U26–U33 gestellt; Anleitung `docs/ALTDATEN-IMPORT.md` |
| 02.10.2026 | Runde 5 (Pull Request #3, in `main` als `b1949ca`–`7ba9f35`) | Datensicherung aus der Oberfläche (O-23): Administration › Backup nach Entwurf 11 (F61–F64) – Passwort für die Verschlüsselung in der Oberfläche festlegen (U20 geklärt: symmetrisch, GnuPG/AES-256; Passwortblatt für den Tresor, Prüfen), Sicherung täglich 02:00 und „Jetzt sichern“, Übertragung in einen WebDAV-Ordner mit rclone im Zeitfenster, Wiederherstellen mit Admin-Passwort und 2FA (vorher Sicherung, Rücktausch bei Fehlern, Löschliste bleibt, danach Audit-Log und alle neu anmelden). Backup-Status in der Kopfzeile der Startseite (O-07, F13). Serverskripte nach „EPM-Server Aufbau“ (O-24). Audit-Gruppe „Backup“ für alle Tätigkeiten rund um Sicherungen. CI meldet Ergebnisse auch bei Pull Requests am Commit. Lauf 36986911046: 155 von 155 Backend-Tests, 70 von 70 Browsertests; nach dem Zusammenführen mit der Rechte-Änderung Lauf 36990805767 und auf `main` Lauf 36991958136: je 156 von 156 und 70 von 70 |
| 02.10.2026 | Runde 4 (Systemseite, Kalender, Infusionspläne) | Neues Recht „Systemverwaltung“ (nur Admin); Administration › System mit Systemagent auf dem Server (F86–F89, Festlegungen S12–S14); globaler Kalender mit Fälligkeiten und Feiertagen (F84); Übersicht aller Infusionspläne (F85); Audit-Gruppe „System“; Feiertage NRW (U25). Nummern ab F84, damit parallele Arbeiten (F72 ff.) nicht kollidieren |
| 02.10.2026 | Runde 4 (Updates VPS) | Festlegung: VPS ohne Verbindung zu GitHub und ohne Build (`EPM_UPDATE_QUELLE="paket"`); `sudo epm-update --paket-erstellen` auf der Test-VM packt die dort laufende, getestete Version (Images, Rollout-Dateien, Systemagent, `epm-update`, SHA-256), `sudo epm-update --paket DATEI` spielt sie auf dem VPS ein (Prüfsummen, Backup, Umstellen, Tests) |
| 02.10.2026 | Rechte (Festlegung) | Endgültig löschen (F73 Dokumente, F80 Akten) auch Admins – auch bei echten Akten, als Ausnahme von „Admins schreiben Patientendaten nur bei Testpatienten“; alle Bestätigungen und Prüfungen unverändert. Systemverwaltung für eine Urlaubsvertretung je Gruppe freischaltbar (Standard weiter nur Admin) |
| 01.10.2026 | Runde 1 (`c387b7b`–`0e25377`) | Backend für F01–F22, F25–F36, F40–F48, F52–F54, F56–F58, F60 mit Backend-Tests; Nachweis angelegt |
| 01.10.2026 | Runde 2 (`9eae348`) | Rechte je Gruppe (F66) nach Festlegung: Mediziner wie Admin außer Benutzerverwaltung, Wiederöffnen, Sicherungen, Testdaten; U10 erledigt, U11 bestätigt, U12 neu; Briefkopf und Logo (F49) |
| 01.10.2026 | Runde 2 (`2b76a0a`–`39b86b9`) | Frontend: Anmeldung, Start, Patientenliste, Neuer Patient, Versorger, Akte (Übersicht, Diagnose & Therapie, Kontakte, Pläne, Dokumente, Verlauf); Browsertests im echten Stack in GitHub Actions |
| 01.10.2026 | Runde 2 (`d1eae4e`–`0ea3e18`) | Mein Konto und Administration (Benutzer, Rechte, Vorlagen, Audit-Log) im Frontend; Bildschirmgrößen; abgelaufene Sitzung führt zur Anmeldung |
| 01.10.2026 | Runde 2 (`04c9f4f`–`43d4fe1`) | Termine in der Akte ändern; Backend meldet zu schnelle 2FA-Bestätigung mit 429; Fehlersuche in CI (Seitenzustand, Audit-Log als Kommentar). Ursache beendeter Admin-Sitzungen in den Browsertests behoben (Testhilfe, kein Produktfehler) |
| 01.10.2026 | Runde 2 (`ceaa105`) | Patientenliste: ein kurz nach „Filter zurücksetzen“ gewählter Filter ging verloren – behoben |
| 01.10.2026 | Runde 2 (`06b4167`) | Neustart-Nachweis aller Browsertest-Ergebnisse über die Oberfläche; Plan-Editor füllt direkt nach einer Freigabe mit dem neuen Plan vor (vorher leer); Häkchen in den Auswahllisten schalten sofort um; Farbeingabe in „Mein Konto“ geht beim Verlassen nicht verloren; Status von 50 Funktionen auf ABGESCHLOSSEN UND GETESTET |
| 01.10.2026 | Runde 2 (`15dae20`) | Rechte nach Festlegung: Mitarbeiter schließen Akten ab und pflegen Vorlagen; Admins alles, Patientendaten nur bei Testpatienten (U12 geklärt) |
| 01.10.2026 | Runde 2 (`d7b3411`) | Plan-Editor: „Energie manuell“ ergänzt (war im Backend vorhanden, fehlte in der Oberfläche); Browsertests für Kopfzeilensuche, Testzugang, Vorlage und Leer beginnen, alle Elektrolyte, Praxistermin mit Ort, Diagramm |
| 01.10.2026 | Runde 2 (`eae8bc3`–`a985fa5`) | Klärung U1, U2, U8, U9 umgesetzt: Protonenpumpenhemmer mit Zeiten (F38) und berechnetes Gesamtvolumen mit Rate und Grenze (F39, F48) auf ABGESCHLOSSEN UND GETESTET; F11/F58 ohne Gerätename-Lücke; F64 nicht mehr blockiert. U13/U14 gestellt |
| 01.10.2026 | Runde 2 (`f865cde`–`a985fa5`) | Klärung U13/U14 umgesetzt: Energie mit Lipiden 9,15 kcal/g, Humanalbumin in ml ohne Energie (Feld `albumin_ml`), Hinweis zur Ca/Mg-Stabilität, erster Plan je kg Körpergewicht vorbelegt (`GET /api/infusionsplaene/vorbelegung/?patient=`) |
| 01.10.2026 | Runde 3 (`c3aacfa`–`1718dc3`) | Rückmeldungen aus dem Testsystem: Blau auf Blau behoben, Testpatienten-Zahl nur für Admin, PDF-Anzeige mit pdf.js, Ärzteliste (F67/F68), Bezugspersonen (F69), „kein“ Katheter/Versorger und Nickelallergie als Auswahl (F70); Backend-Image mit IBM Plex aus dem Repo (Debian 13 hat kein `fonts-ibm-plex`) |
| 02.10.2026 | Runde 3 (`6c6a97a`–`e74f4ff`) | U15 nach DSGVO geklärt und umgesetzt (F73): Titel, Dateiname, Notiz und Datum endgültig gelöschter Dokumente auch aus Historie und Audit-Log entfernt (kontrollierte Trigger-Ausnahme), Nachweis ohne Inhalt, Löschliste mit Nachholen nach einer Wiederherstellung, Bestand per Migration; Audit-Log mit Filter „Dokument“. Fehler behoben: bei „Neuer Arzt“/„Neuer Versorger“ ging eine schon begonnene Eingabe verloren, wenn die Liste erst danach fertig geladen war. Browsertest Rechte stabilisiert (`b306c79`). Lauf 36943685896: 100/100 Backend-Tests, 49/49 Browsertests |
| 02.10.2026 | Runde 4 (`e9b953d`–`08b15db`) | Datenschutz nach DSGVO (`docs/DATENSCHUTZ.md`): Aufbewahrungsfrist je Akte mit Verlängerung und „Abschluss prüfen“ (F74); Erklärungen nachhalten mit Vordrucken aus Dokumentvorlagen (F75, F76); Anfragen mit Frist (F77); Kopie der Akte (F78); Verarbeitung einschränken mit begründeter Einsicht (F79); Akte endgültig löschen mit Löschprotokoll, Löschliste und Nachholen nach einer Wiederherstellung (F80); Übersicht „Datenschutz“ (F81); Plan nach Freigabe per E-Mail abschließen, Freigabevermerk nennt beide Personen (F82); Aufbewahrung des Audit-Logs einstellbar (F83). Vier neue Rechte. Testdaten-Zurücksetzen nutzt dieselbe Löschlogik (behebt einen Abbruch bei umgehängten Dokumenten). Wartungsmodus der Trigger gilt nur noch für den Vorgang statt bis zum Ende der Transaktion. Sicherungen 30 statt 14 Tage, Verschlüsselung mit `age` vorbereitet (F61). Unklarheiten U16–U24 |
| 02.10.2026 | Runde 4 (`e292ae7`–`34c627d`) | Unabhängige Prüfung der Datenschutz-Änderung (zweite Instanz, nur lesend) und Behebung ihrer Befunde: Reste nach dem Löschen einer Akte (Fassungen eines Dokuments aus der Zeit in einer anderen Akte, Titel bei hin- und zurückgewechseltem Dokument, Vitamin-Historie, Suchbegriff im Audit-Log); Nachweis einer Dokument-Löschung in der anderen Akte wurde beim Löschen fälschlich umgeschrieben; eingeschränkte Akten waren mit Namen sichtbar (Übersicht und Anfragen für Mitarbeiter und Administration, Audit-Log, Django-Admin); Fristen des Datenschutzes waren mit „Vorlagen pflegen“ änderbar; Kopie echter Akten durch Admins; Startseite zählte Anfragen zu abgeschlossenen Akten nicht; Aufbewahrungsfrist beginnt nicht vor dem letzten Kontakt; Abschließen nach Freigabe nur mit dem Datenfeld „Freigabevermerk“ in der Vorlage; Verlauf und Listen nennen bei Freigabe außerhalb von EPM den Mediziner und den Tag der Freigabe; Fehlversuche beim endgültigen Löschen zählen (F73, F80); Nachholen von Löschungen robuster; Sicherung hinterlässt bei Fehlern keine halbe Datei, Löschliste mitverschlüsselt; Löschprotokoll ohne Anlass des Abschlusses |
| 02.10.2026 | Runde 3 (`df02dda`–`e709bee`) | Rückmeldungen zur PDF-Funktion: Dokumentvorlagen als Bereich der Vorlagen, Felder verschiebbar, Schriftgröße und Titel-Ausrichtung wirksam, Planansicht in der Akte = echte PDF (F31), Aktenkopf mit festem Raster und anklickbarem „Auskunft an“ (F17). Neu: Dokument dem richtigen Patienten zuordnen (F72) und endgültig löschen nur durch Mediziner mit Kennwort, 2FA und Bestätigungscode (F73). Fehler behoben: Datenmigration „Kontakt überfällig“ brach auf bestehender Datenbank ab (Grund > 100 Zeichen); Grund beim Wiederöffnen begrenzt |
| 01.10.2026 | Runde 3 (`0624527`–`ca9f858`) | PDF-Erzeugung mit WeasyPrint (F51), Dokumentvorlagen mit Editor (F50), Freigabe-PDF mit SHA-256 und Prüfung beim Öffnen (F35, F37; Nginx reicht `X-EPM-Pruefung` weiter), Akte, Verlauf, Audit-Log und Zugangsblatt als PDF (F23, F24, F59, F55). Infusionsplan-PDF nach dem Altsystem, auf Wunsch neu gestaltet wie ein Laborbefund und wie die Oberfläche (Kopfkarte, Karten, Menge/Einheit in eigenen Spalten, Titel neben dem Logo, ohne Linie, fax-tauglich, einseitig); Laufzeit 0 als „—“; neue Bausteine und Optionen im Editor; Datenfeld-Einfügen nimmt den aktuellen Feldinhalt (Fehler behoben) |
| 01.10.2026 | Runde 3 (`a30b26d`) | „Kein Kontakt seit …“ nach 4 statt 12 Monaten (Patienten kommen meist quartalsweise): Standard in den Einstellungen, Datenmigration stellt einen unveränderten Wert 12 um (mit Grund in der Historie); wirkt auf Hinweis in der Patientenliste und „Nach und nach prüfen“ auf der Startseite; Backend-Test `test_kontakt_ueberfaellig_nach_4_monaten` |
| 01.10.2026 | Runde 3 (`b37d606` und folgende) | Nicht Erlaubtes ausblenden (F71): keine Fenster oder Meldungen mit „Dafür fehlt das Recht“ mehr; Rechteänderungen wirken in der Oberfläche ohne neue Anmeldung (Kopf `X-EPM-Rechte`); abgelehnte Aktionen nur mit neutralem Hinweis; ausgeblendete Fenster öffnen sich nicht von selbst wieder |

### F191 KI (Experimentell) – lokale Erkennung, Strukturierung und Prüf-Queue
- **Anlass:** Auftrag vom 14.10.2026 (Plan und Entscheidungen: `docs/KI-ERWEITERUNG-PLAN-2026-10-14.md`).
- **Umfang:** App `backend/ki` (Modelle, Pipeline, Steuerung, Verknüpfung, Übernahme, Berichte, Evaluation, Qualität,
  API), Dienst `manage.py epm_ki` (Container `ki-worker`), Modell-Container `ki-modell` (`rollout/ki/`), Oberfläche
  `frontend/src/seiten/ki/`, `seiten/akte/KiAkte.tsx`, `seiten/admin/KiVerwaltung.tsx`, Werkzeuge `werkzeuge/ki*.sh`.
- **Sicherheit:** nichts ohne Bestätigung in die Akte; DB-Rolle `epm_ki` ohne Schreibrecht auf die Akte; nur internes
  Netz, nur erlaubte Rechner, kein Proxy; Zwischendateien AES-256-GCM; Audit mit Modell, SHA-256, Prompt-Fassung.
- **Neu außerhalb der App:** optionales Feld `Laborbefund.abgenommen_um` (Migration `befunde/0003`), Audit-Art „KI“
  (`audit/0014`), sechs Rechte `ki_*`, Marke `system/status/backup-laeuft` in `epm-backup.sh`, `epm-update` behält
  `compose.ki.yaml`, wenn `ki-aktiv` existiert.
- **Teststatus:** `ki/test_bausteine.py` (Zeitfenster, Hysterese, Hardwareprüfung, Regelprüfung, Client offline,
  Verschlüsselung, Pseudonymisierung, Benchmark), `ki/test_verarbeitung.py` (Queue, echte Texterkennung + Modell-
  Attrappe, Abbruch/Fortsetzen, Dienst `--einmal`, Löschen, Verknüpfung gesichert/wahrscheinlich/weiterhin/keine
  Maßnahme), `ki/test_api.py` (Rechte, Firmen, Korrektur, Konflikte 409, Ersetzen/Ergänzen, Admin nur Testpatienten,
  Infusionsplan als Altsystem-Plan, Medikation/Diagnose/Text/Datum, Berichte mit Gegenprüfung, Modellwechsel mit 2FA,
  Qualität, Evaluation, DB-Rolle).
- **Status:** TEILWEISE ABGESCHLOSSEN – Lauf mit echtem Modell und Benchmark auf der Ziel-VM stehen aus; Browsertest
  noch nicht geschrieben; Trainingslauf (LoRA auf CPU) bewusst noch nicht gebaut.

### F192 Diktate – Aufnahme im Browser, Abschrift offline
- **Anlass:** Wunsch vom 23.10.2026: Der Mediziner diktiert Pläne, Arztbriefe und Konsultationsberichte; die Texte
  sollen im Layout der Stiftung entstehen. Festlegungen: Korrektur je nach Fall selbst oder durch das Sekretariat;
  kurze Diktate sofort, lange über Nacht; Aufnahme bis zur Freigabe aufbewahren; nur er diktiert (Recht je Gruppe);
  Windows-PC, Mac und Handy, nur im VPN; bei Infusionsplänen nur der Kommentar; freigeben darf wie bei
  Infusionsplänen jeder mit dem Recht.
- **Umfang:** App `backend/diktate` (Modell `Diktat`, `Begriffsliste`, Abschrift `abschrift.py`, Warteschlange
  `dienst.py`, API), Abschrift im OCR-Dienst (`scans/management/commands/epm_ocr.py`: „sofort“ vor Scans, „nachts“ im
  Nachtfenster `EPM_DIKTAT_NACHT`, Standard 21–7 Uhr, nach den Scans), Modell in `scans/modelle/modelle.json`
  (optional – fehlt es, arbeitet die Texterkennung normal), Oberfläche `components/Diktat.tsx`, `seiten/Diktate.tsx`,
  `seiten/akte/Berichte.tsx`, `seiten/akte/PlanEditor.tsx`.
- **Ressourcen:** kein eigener Container; das Sprachmodell (≈ 550 MB, im Speicher ≈ 1 GB) wird erst beim ersten
  Diktat geladen und nach 5 Minuten ohne Diktat freigegeben; Rechenkerne wie die Texterkennung (`EPM_OCR_THREADS`,
  eigene Zahl mit `EPM_DIKTAT_THREADS`); niedrige Priorität wie der OCR-Dienst. Der OCR-Dienst braucht dafür
  mindestens 3 GB (`EPM_OCR_SPEICHER=3g`; `04-projekt.sh` setzt unter 6 GB RAM nur 1536m) – sonst bleibt die Abschrift
  aus und die Oberfläche nennt den Grund, statt dass der Dienst an seiner Speichergrenze abbricht.
- **Ansagen:** „neuer Absatz“, „neue Zeile“, „Doppelpunkt“, „Klammer auf/zu“, „Schrägstrich“, „Fragezeichen“,
  „Ausrufezeichen“. Satzzeichen setzt die Abschrift selbst („Punkt“ bleibt ein Wort).
- **Fachbegriffe:** eigene Liste je Person (`PUT /api/diktate/begriffe/`), Name, Diagnosen der Akte und Präparate gehen
  als Vorlage an die Abschrift (höchstens 700 Zeichen).
- **Datenschutz:** Aufnahme unter `data/scans/diktate/` (nicht in der Sicherung, Rechte 0640, zufälliger Name),
  gelöscht mit der Freigabe des Berichts bzw. nach der Übernahme in den Kommentar, beim Verwerfen und mit der Akte;
  Kommentar-Diktate ohne Übernahme nach 3 Tagen; Audit-Art „Diktat“ (aufgenommen, abgeschrieben, übernommen,
  verworfen). Siehe `docs/DATENSCHUTZ.md` § 8.
- **API:** `POST /api/diktate/` (multipart; Recht „Diktieren“), `GET /api/diktate/?bericht=`, `GET …/offen/`
  (Sekretariat), `GET …/{id}/audio/`, `POST …/{id}/uebernommen/`, `POST …/{id}/erneut/`, `DELETE …/{id}/`
  (Einträge erfassen), `GET|PUT …/begriffe/`, `GET …/stand/`.
- **Teststatus:** `diktate/tests.py` – Rechte, Prüfungen beim Hochladen, Abschrift mit Modell-Attrappe, Sekretariat,
  Freigabe wartet auf laufende Abschrift und löscht die Aufnahme, Freigabe durch einen anderen Mediziner, Kommentar,
  Verwerfen, Fehler und erneut, Nachtfenster, Abbruch, Aufräumen, Begriffe, Vorlage, WebM/WAV lesen, Ansagen; echte
  Abschrift mit whisper.cpp, sobald das Modell bereitliegt (CI lädt es mit den OCR-Modellen).
- **Status:** TEILWEISE ABGESCHLOSSEN – Qualität der Abschrift mit echten Diktaten auf dem Server prüfen; Live-
  Mitschreiben (Text erscheint beim Sprechen) erst nach dem Aufrüsten auf 16 GB / 8 Kerne.

### F193 Dokumentenautomation der Regeneration Clinic – Fall, Paket, Fassungen, Rechnung, Signatur
- **Anlass:** Anforderungsspezifikation „Dokumentenautomation RGC“ vom 26.10.2026 (inkl. Editierbarkeit nach
  PDF-Erzeugung): Vorlagen, Rechnung, OP-Bericht, Entlassungsbrief und Konsiliarbericht aus einem Falldatensatz – einfach,
  flexibel, nachvollziehbar. Abnahmekriterium: Nach Erzeugung einer PDF kann der Inhalt noch geändert und die PDF neu
  erzeugt werden; erst nach Unterschrift/Signatur ist die Fassung unveränderlich; alle Versionen sind nachvollziehbar.
- **Umfang:** App `backend/faelle` – Modelle `Behandlungsfall`, `FallDokument` (Entwurf → erzeugt → final),
  `DokumentVersion` (nur anfügen), `Rechnungsposition`, Stammdaten `Leistung` (Leistungskatalog), `Kostentraegertyp`
  (mit Paketregel), `Kooperationspartner`, `Unterzeichner` (mit Zertifikat), `Zaehler` (Fall- und Rechnungsnummern);
  `pakete.py` (Paketregeln), `erzeugung.py` (Erzeugen, Finalisieren, Signatur, Storno, DOCX), `felder.py`
  (Platzhalter `Fall.*`, `Rechnung.*`, `Dokument.*`, `Leistungen.Summe`, Tabellen „rechnung“ und „leistungen“ in allen
  eigenen Schreiben), `startvorlagen.py` (Fall-Dokumente je Sprache, Zusatzbögen zu 07). Datenmigration
  `faelle/0002` (Kostenträgertypen mit Paket, Eibach/ARS/WC4/AIWA, Dr. Markus Gottwald, Prof. Dr. Markus Masin,
  Dokumenttyp „Rechnung“, 12 Fall-Vorlagen, 3 Zusatzbögen) und `faelle/0003` (Formulare 01–12 mit Feldern des Falls,
  nur unveränderte Vorlagen, vor dem Import in Fassung 1, danach als Fassung 2; Feldfehler der Word-Umsetzung behoben, `faelle/formulare.py`). Trigger `epm_falldokument_schutz`,
  `epm_rechnungsposition_schutz` (auch INSERT), `faelle_dokumentversion` nur anfügen (`audit/schutz.py`).
- **API:** `/api/faelle/` (+ `paket/`, `abschliessen/`, `wieder-oeffnen/`), `/api/falldokumente/` (+ `vorschau/`,
  `erzeugen/`, `versionen/`, `pdf/?fassung=N`, `docx/` GET/POST, `finalisieren/`, `stornieren/`),
  `/api/rechnungspositionen/`, `/api/leistungen/` (+ `import/`), `/api/kostentraegertypen/` (+ `optionen/`),
  `/api/kooperationspartner/`, `/api/unterzeichner/` (+ `{id}/zertifikat/`). Rechte: Fälle und PDFs mit „Einträge
  erfassen“, Finalisieren/Signieren/Stornieren mit „Fall-Dokumente finalisieren“ (Standard Mediziner), Stammdaten mit
  „Vorlagen pflegen“; Admins wie überall nur bei Testpatienten.
- **Nachvollziehbarkeit:** jede Fassung mit PDF (Dokument der Akte, bis final ausgeblendet), SHA-256 (beim Abruf
  geprüft), Vorlagenversion, Datenstand, Person, Zeitpunkt, Grund; Audit-Art „Behandlungsfall und Dokumente“; Verlauf
  der Akte (Bereiche „faelle“, „falldokumente“); simple-history an allen Modellen; Akte endgültig löschen entfernt Fälle,
  Fassungen und Historie mit.
- **Teststatus:** `faelle/tests.py` – Stammdaten und Vorlagen (gültige Blöcke), Paket je Kostenträgertyp mit
  Zusatzbogen, OP-Bericht aus Falldaten, Rechnung änderbar bis zur Finalisierung (Abnahmekriterium), Finalisieren nur mit
  aktueller Fassung, Storno mit neuer Rechnung, Sprachen EN/LV, Signatur mit selbst ausgestelltem Zertifikat, extern
  signierte PDF, Scan, DOCX-Rundweg, CSV-Import, Löschen der Akte; Trigger gegen direkte Änderungen.
- **Status:** TEILWEISE ABGESCHLOSSEN – Browsertest für Akte › Fälle fehlt; Preise, Bankverbindung der RGC,
  fachärztliche Prüfung der Zusatzbögen und lettischen Texte stehen aus (`docs/DOKUMENTENAUTOMATION-RGC-2026-10.md`).
