# EPM – Nachweis der Backend-Funktionen

Stand: 02.10.2026 · Code-Stand: Fehlerliste vom 02.10.2026 (F98–F106, geändert F03, F05, F09, F20, F31, F52, F72, F85, F86, F97); Runde 7 (Startseite und Oberfläche S01–S17, F90–F97); Runde 6 (Altdaten übernehmen, F65: Werkzeug Administration › Import); Runde 5 (Datensicherung aus der Oberfläche, F61–F64, O-07, O-23, O-24); Runde 4 (Datenschutz nach DSGVO, F74–F83; davor Runde 3 bis `e74f4ff`: PDF-Erzeugung,
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
| F01 | Sitzungsstatus und CSRF-Token | 1 Anmeldung | ABGESCHLOSSEN UND GETESTET |
| F02 | Anmeldung mit Benutzername und Kennwort | 1 Anmeldung | ABGESCHLOSSEN UND GETESTET |
| F03 | Zweiter Faktor bei der Anmeldung | 1 Anmeldung | ABGESCHLOSSEN UND GETESTET |
| F04 | Eigenes Kennwort setzen und ändern | 1 Anmeldung, 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F05 | Authenticator einrichten und ersetzen | 1 Anmeldung, 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F06 | Notfall-Codes neu erzeugen | 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F07 | Abmelden | alle Ansichten (Seitenleiste) | ABGESCHLOSSEN UND GETESTET |
| F08 | Konto sperren nach 5 Fehlversuchen | 1 Anmeldung, 17 Benutzer, 20 Audit-Log | ABGESCHLOSSEN UND GETESTET |
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
| F83 | Aufbewahrung des Audit-Logs, tägliche Bereinigung | 18 Vorlagen (Grenzwerte), 20 Audit-Log | TEILWEISE ABGESCHLOSSEN |
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

Summe (106 Funktionen, gezählt aus der Tabelle): 105 abgeschlossen und getestet (F65 mit erfundenem Beispiel-Dump, der echte steht aus) · 1 teilweise abgeschlossen (F83) · 0 nicht abgeschlossen · 0 blockiert. (Die Summe vor Runde 7 zählte F65 noch als nicht abgeschlossen.)
Gegenüber Runde 1 ist keine Funktion zurückgestuft worden. Neu ist F66 (Rechte je Gruppe). F38 und F39 sind nach der
Klärung von U1/U2 umgesetzt, F64 ist nach der Klärung von U9 nicht mehr blockiert, aber noch nicht umgesetzt.
Neu in Runde 4 sind F74–F83 (Datenschutz nach DSGVO und Abschließen eines Plans nach Freigabe); offene Fragen dazu stehen
in `docs/DATENSCHUTZ.md` und unten als U16–U24. Runde 5 schließt die Datensicherung ab (F61–F64, dazu der Backup-Status der Startseite in F13); offen ist nur noch der Import der Altdaten (F65) und die Aufbewahrung des Audit-Logs (F83, U18). Runde 7 setzt die Startseiten- und Oberflächen-Erweiterungen S01–S17 aus `claude/startseite-erweiterungen.md` um (F90–F97, dazu erweitert F09, F13, F14, F17, F48, F84). Die Fehlerliste vom 02.10.2026 bringt F98–F106 und ändert F03, F05, F09, F20, F31, F52, F72, F85, F86, F97 (Abschnitt P).

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
- **Fehlerfälle:** 401 nicht mit Kennwort angemeldet oder Code falsch · 403 `gesperrt` beim fünften Fehlversuch (Abmeldung) · 429
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

### F08 Konto sperren nach 5 Fehlversuchen
- **Zweck:** Schutz gegen Raten. **Beschluss (Entwurf 17, 20):** Konto bleibt gesperrt, bis der Admin entsperrt; Audit-Log
  zeigt „5 falsche Passwörter in 4 Minuten, Konto gesperrt“ und einen Hinweis mit Link zum Benutzer.
- **Ansicht:** 1 Anmeldung, 17 Benutzer, 20 Audit-Log
- **Endpunkte:** wirkt in F02/F03; Hinweis `GET /api/benutzer/hinweise/` → `[{id, benutzername, anzeigename, gesperrt_am,
  sperrgrund, fehlversuche}]`; Entsperren über F53.
- **Logik:** Zähler `fehlversuche` je Konto (falsches Kennwort und falscher 2FA-Code); beim fünften: `is_active = false`,
  `gesperrt_am`, `sperrgrund`, alle Sitzungen beendet, Ereignis `anmeldung_gesperrt` mit Anzahl und Minuten seit dem ersten
  gezählten Fehlversuch. Erfolgreicher zweiter Faktor setzt den Zähler zurück. Grenze `EPM_LOGIN_MAX_FEHLVERSUCHE = 5`.
- **Tabellen:** `accounts_user` (`fehlversuche`, `gesperrt_am`, `sperrgrund`), `audit_systemereignis`
- **Fehlerfälle:** 403 `{"fehler": "Das Konto ist gesperrt …", "gesperrt": true}`
- **Testschritte:** 4 × falsch → 401; 5. → 403 gesperrt; richtiges Kennwort → 403; falsches → 401; Admin entsperrt →
  Anmeldung klappt; Audit-Log zeigt „Falsches Passwort (3. Versuch)“ und „5 falsche Passwörter in n Minuten, Konto gesperrt“.
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
  `aufnahme_quelle` (nur beim Anlegen). Im Code zusätzlich `telefon2`, `krankenkasse`, `bemerkung` (Unklarheit U5).
- **Response 201:** Akte wie F17; `nummer` automatisch fortlaufend, Testpatienten ab 9001.
- **Logik:** Patient und Aufnahmegewicht (als erste Gewichtsmessung, erfasst von der anlegenden Person) in einer Transaktion.
- **Validierung:** Geburtsdatum nicht in der Zukunft; Größe und Aufnahmegewicht in den Grenzen der Einstellungen;
  Ansprechpartner gehört zum Versorger; Katheter aus Liste „Katheter“; Aufnahmegewicht beim Ändern → 400.
- **Tabellen:** `patienten_patient`, `patienten_gewichtsmessung` (+ Historie)
- **Fehlerfälle:** 400 Pflichtfeld/Plausibilität (dann wird nichts gespeichert) · 403 ohne Recht „Patienten anlegen, Diagnose, Therapie, Stammdaten ändern“; ein
  Admin legt automatisch einen Testpatienten an (`naechste-nummer` meldet `testpatient: true`)
- **Teststatus:** Backend-Tests grün (`test_schreibrechte`, `test_nummern`, `test_anlegen_mit_aufnahmegewicht`). Browsertests grün: `patienten.spec.ts` „Neuer Patient: Prüfung, Doppelung, Anlegen mit Gewicht bei Aufnahme“
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
- **Request:** `{"patient", "text" (formatiert, Pflicht), "zeitpunkt"?, "wiedervorlage"?}` (im Code zusätzlich `art`, Unklarheit U6)
- **Response:** `{id, patient, zeitpunkt, art, art_name, text, erfasst_am, erfasst_von_name, storniert_am, storniert_von_name,
  storno_grund, termine: [{id, art, faellig_am, uhrzeit, ort, erledigt}]}`
- **Validierung:** Text bereinigt; Zeitpunkt nicht in der Zukunft; Akte offen. Unveränderlich: Modell + Datenbank-Trigger.
- **Tabellen:** `patienten_kontakt`, `patienten_historicalkontakt`
- **Teststatus:** Backend-Tests grün (`KontaktRegeln.*`). Browsertest grün: `akte.spec.ts` „Kontakt mit Wiedervorlage erfassen, suchen, stornieren“ (mit Neustart); Neustart geprüft in `zz-neustart.spec.ts`.
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
  Überschrift (Bereich als Karte), ausblenden wenn leer, nicht teilen, Linie darüber, neben dem vorherigen Block (⅓, ½, ⅔).
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
  Addel N, Soluvit N + Vitalipid adult, Taurolin 2 %), Termin in der „Praxis Dr. Holtmeier“, ein Altdokument „Typ prüfen“.
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
  4 Minuten, Konto gesperrt“, „Benutzer k.oezdemir angelegt (Mitarbeiter), Einmal-Kennwort erzeugt“, „Akte Weber, Anna
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
  Einstellung (`datenschutz.spec.ts` „Grenzwerte: Fristen des Datenschutzes einstellen“). Das Entfernen alter Einträge
  ist nur im Backend-Test geprüft (über die Oberfläche lassen sich keine alten Einträge erzeugen), daher nicht
  ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

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
| U3 | „geändert“-Hinweis an einem Kontakt im Entwurf widerspricht „unveränderlich“ | F26 | Beschluss gilt |
| U4 | Plan-Hinweis „6 Monate“ in der Liste vs. 12 Monate in den Grenzwerten | F14 | Grenzwert gilt (Text nennt die eingestellten Monate) |
| U5 | Felder Krankenkasse, Telefon 2, Bemerkung (nicht im Entwurf) | F16 | bleiben gespeichert, nicht angezeigt |
| U6 | Kontaktart (nicht im Entwurf) | F26 | bleibt gespeichert, nicht angezeigt |
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
| U26 | Den Import führt die Administration durch und legt dabei echte Akten an – Ausnahme von U12 („Admins schreiben Patientendaten nur bei Testpatienten“). So gewollt? | F65 | ja, nur über Administration › Import (eigenes Recht, Kennwort + 2FA, Audit-Log) |
| U27 | Echte (nicht Test-)Akten aus der Testphase sperren den Import; ihre Nummern bleiben nach dem endgültigen Löschen (F80) im Löschprotokoll und sind für die Übernahme gesperrt. Soll das Werkzeug solche Akten entfernen dürfen? | F65 | nein – übernommen wird nur in ein System ohne echte Akten (Festlegung 02.10.2026); auf einem Server, auf dem schon echte Akten angelegt wurden, braucht der Go-live eine frische Datenbank |
| U28 | Dokumente anderer Dateitypen im Ordner des Altsystems (Word, Excel …) | F65 | werden nicht übernommen, aber einzeln aufgelistet; der Ordner bleibt unverändert |
| U29 | Zeitangaben: Welchen Typ haben `lastchange`, `created`, `deleted_at` im echten Altsystem? `TIMESTAMP` steht im Dump in UTC und wird umgerechnet, `DATETIME` gilt als Ortszeit | F65 | am echten Dump prüfen – das Werkzeug zeigt nach dem Laden einen Hinweis, wenn es umgerechnet hat |
| U30 | Infusionspläne aus dem Altsystem: ohne Freigabe und ohne gespeicherte PDF (im Altsystem gab es beides nicht); Mengen 0 → leer; Energie nur dann als „manuell“, wenn sie von der Berechnung abweicht; jüngster Plan je Patient „aktuell“ | F65 | so umgesetzt (Regeln 13 und 16 der Datenanalyse); in der Akte als „aus dem Altsystem“ gekennzeichnet |
| U31 | Rolle der Konten aus dem Altsystem: Vorschlag aus dessen Rechtestufe (100 Betrachter, 1000 Mitarbeiter, 10000 Mediziner, 100000 Admin) | F65 | Vorschlag, je Konto im Werkzeug änderbar; Konten entstehen ohne Kennwort |
| U32 | Nach dem Abschließen enthalten ältere Sicherungen aus der Testphase und der Ordner `data/import` auf dem Server weiterhin Altdaten (auch der nicht übernommenen Patienten) | F65, F61 | organisatorisch löschen (`docs/DATENSCHUTZ.md`); das Werkzeug weist beim Abschließen darauf hin |
| U34 | ~~Bestätigungen ohne zweiten Faktor nur mit Kennwort?~~ **Geklärt 03.10.2026: nein.** Endgültig löschen, Wiederherstellen, Updates, Neustart, Sicherung und Import verlangen immer den zweiten Faktor; wer sie ausführt (Mediziner, Administration …), muss ihn einrichten – ohne geht es nicht | F99 | – |
| U35 | Hochgeladene Sicherung eines anderen Servers mit fremdem Passwort: Das Passwort wird auf diesem Server (root, 0600) als eigene Nummer hinterlegt, damit sich die Sicherung wiederherstellen lässt | F103 | so umgesetzt; das aktuelle Sicherungs-Passwort dieses Servers bleibt unverändert – **bestätigt 03.10.2026** |
| U36 | Geänderte Aufbewahrung wirkt erst mit der nächsten Sicherung (dann werden ältere entfernt), nicht sofort | F103 | so umgesetzt; der Dialog sagt es – **bestätigt 03.10.2026** |
| U37 | „Kein Infusionsplan nötig“: Wer darf bestätigen? Gilt auch eine offene Entwurfsfassung als „kein Plan“? | F105 | Recht „Akten bearbeiten“ (wie „kein Versorger“; unter Benutzer › Rechte umstellbar); ein Entwurf allein zählt nicht als Plan – der Hinweis bleibt bis zur Freigabe – **bestätigt 03.10.2026** |
| U38 | ~~„Testdaten sehen“ für den Admin abschaltbar?~~ **Bestätigt 03.10.2026:** nein, für den Admin fest | F106 | – |
| U33 | Vor dem Abschließen: Ein nach Art. 17 endgültig gelöschtes **Dokument** käme nach „Zurücknehmen“ und erneutem Import wieder (neue Nummer, die Löschliste erkennt es nicht). Eine endgültig gelöschte **Akte** kommt nicht wieder: Ihre Nummer steht im Löschprotokoll; der Patient erscheint unter „Auffälligkeiten“ und lässt sich nur „nicht übernehmen“ – eine andere Nummer ist nicht wählbar (O-29, behoben 02.10.2026) | F65, F73, F80 | Dokumente: betrifft nur die Zeit vor dem Abschließen (Testphase); nach dem Abschließen ist der Dump gelöscht |

## Änderungsprotokoll

| Datum | Stand | Änderung |
|---|---|---|
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
