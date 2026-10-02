# EPM – Nachweis der Backend-Funktionen

Stand: 02.10.2026 · Code-Stand: Runde 3 (bis `e74f4ff`: PDF-Erzeugung, Dokumentvorlagen, Rückmeldungen aus dem Testsystem, falsch zugeordnete Dokumente, Löschen nach Art. 17 DSGVO) ·
Grundlage: Altsystem-Datenanalyse mit Entscheidungen, Entwurf „EPM Oberfläche“ (23 Ansichten), „EPM-Server Aufbau“,
Festlegung zu den Rechten vom 01.10.2026.

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

Stand 02.10.2026: **100 von 100 Backend-Tests** und **49 von 49 Browsertests grün** (Lauf 36943685896, Commit `e74f4ff`).

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
| F09 | Eigenes Profil, Darstellung und Startseite speichern | 14 Mein Konto, 2 Start | ABGESCHLOSSEN UND GETESTET |
| F10 | Sicherheitsstatus im Konto | 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F11 | Angemeldete Sitzungen anzeigen und abmelden | 14 Mein Konto | ABGESCHLOSSEN UND GETESTET |
| F12 | Automatische Abmeldung nach 30 Minuten | alle | ABGESCHLOSSEN UND GETESTET |
| F13 | Startseite | 2 Start | TEILWEISE ABGESCHLOSSEN |
| F14 | Patientenliste mit Filtern und Suche | 3 Patientenliste | ABGESCHLOSSEN UND GETESTET |
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
| F48 | Grenzwerte und Einstellungen | 18 Vorlagen | ABGESCHLOSSEN UND GETESTET |
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
| F61 | Tägliche verschlüsselte Sicherung | 11 Backup | TEILWEISE ABGESCHLOSSEN |
| F62 | Sicherungen anzeigen, „Jetzt sichern“ | 11 Backup, 2 Start | NICHT ABGESCHLOSSEN |
| F63 | Wiederherstellen mit Admin-Kennwort und 2FA | 11 Backup | NICHT ABGESCHLOSSEN |
| F64 | Übertragung zur Nextcloud/NAS mit Status | 11 Backup | NICHT ABGESCHLOSSEN |
| F65 | Import der Altdaten | – (Rollout-Schritt 7) | NICHT ABGESCHLOSSEN |
| F66 | Rechte je Gruppe einstellen | 17 Benutzer (Rechte) | ABGESCHLOSSEN UND GETESTET |
| F67 | Gemeinsame Ärzteliste pflegen | Ärzte (neu) | ABGESCHLOSSEN UND GETESTET |
| F68 | Ärzte eines Patienten (Rolle, Hausarzt im Kopf) | 4 Akte, 12 Neuer Patient | ABGESCHLOSSEN UND GETESTET |
| F69 | Bezugspersonen mit „Auskunft erlaubt“ | 4 Akte | ABGESCHLOSSEN UND GETESTET |
| F70 | „kein“ Katheter/Versorger, Nickelallergie als Auswahl | 4 Akte, 12 Neuer Patient, 3 Liste | ABGESCHLOSSEN UND GETESTET |
| F71 | Nicht Erlaubtes ausblenden, Rechteänderung sofort in der Oberfläche | alle Ansichten | ABGESCHLOSSEN UND GETESTET |
| F72 | Dokument dem richtigen Patienten zuordnen | 9 Dokumente, 10 Verlauf | ABGESCHLOSSEN UND GETESTET |
| F73 | Dokument endgültig löschen (nur Mediziner, Kennwort + 2FA + Bestätigungscode) | 9 Dokumente, 10 Verlauf | ABGESCHLOSSEN UND GETESTET |

Summe (71 Funktionen): 57 abgeschlossen und getestet · 3 teilweise abgeschlossen · 11 nicht abgeschlossen · 0 blockiert.
Gegenüber Runde 1 ist keine Funktion zurückgestuft worden. Neu ist F66 (Rechte je Gruppe). F38 und F39 sind nach der
Klärung von U1/U2 umgesetzt, F64 ist nach der Klärung von U9 nicht mehr blockiert, aber noch nicht umgesetzt.

---

## Gemeinsame Regeln aller Endpunkte

- Basis-URL `/api/`, JSON (Datei-Upload: `multipart/form-data`), Datumswerte ISO 8601, Zeitzone Europe/Berlin.
- Anmeldung über Sitzungs-Cookie `epm_sitzung`; schreibende Aufrufe senden das Cookie `epm_csrf` als Kopfzeile `X-CSRFToken`.
- „Voll angemeldet“ = Kennwort + zweiter Faktor in dieser Sitzung + kein offenes Einmal-Kennwort. Sonst **403**.
- Listen sind seitenweise: `{"count", "next", "previous", "results": [...]}`, 50 je Seite (Stammdatenlisten ohne Seiten).
- Fehlerformat: Feldfehler `{"<feld>": ["Meldung"]}`, allgemeine Fehler `{"fehler": "Meldung"}`.
- Fehlercodes: 400 Validierung · 401 falsche Anmeldedaten · 403 fehlendes Recht, unveränderlicher Datensatz oder
  Datenbank-Trigger · 404 nicht vorhanden oder außerhalb des eigenen Bereichs (Testbenutzer) · 405 Aktion nicht
  vorgesehen (z. B. Kontakt ändern) · 409 Akte abgeschlossen · 429 zu viele Versuche.
- Testbenutzer (`ist_test`) sehen und bearbeiten nur Testpatienten.
- Rechte je Gruppe (F66): Die Administration stellt sie in der Oberfläche ein (Benutzer › Rechte), Änderungen gelten ab
  der nächsten Anfrage. Festlegungen vom 01.10.2026: Mediziner sind dem Admin gleichgestellt, ausgenommen
  Benutzerverwaltung und sehr spezifische Eingriffe (abgeschlossene Akten wieder öffnen, Sicherungen, Testdaten).
  Akten abschließen dürfen Mitarbeiter, Mediziner und Admin; Vorlagen pflegen auch Mitarbeiter und Mediziner.
  Admins dürfen alles, Patientendaten schreiben sie aber nur bei Testpatienten – echte Akten sind für sie nur
  lesbar, ein neuer Patient eines Admins wird Testpatient. Standard (✓ = erlaubt, ● = fest, nicht entziehbar,
  T = nur bei Testpatienten, fest; „nur Mediziner“ = keiner anderen Rolle zuweisbar):

| Recht | Betrachter | Mitarbeiter | Mediziner | Admin |
|---|---|---|---|---|
| Akten lesen | ✓ | ✓ | ✓ | ● |
| Kontakte, Gewichte, Termine, Dokumente erfassen | – | ✓ | ✓ | ✓ T |
| Patienten anlegen, Diagnose, Therapie, Stammdaten ändern | – | ✓ | ✓ | ✓ T |
| Infusionspläne anlegen | – | – | ✓ | ✓ T |
| Infusionspläne freigeben | – | – | ✓ | ✓ T |
| Akten abschließen | – | ✓ | ✓ | ✓ T |
| Dokumente einem anderen Patienten zuordnen (F72) | – | – | ✓ | ✓ T |
| Dokumente endgültig löschen (F73) | – | – | ✓ | – (nur Mediziner) |
| Abgeschlossene Akten wieder öffnen | – | – | – | ✓ |
| Versorger und Ansprechpartner pflegen | – | ✓ | ✓ | ✓ |
| Vorlagen pflegen (Briefkopf, Auswahllisten, Präparate, Grenzwerte) | – | ✓ | ✓ | ✓ |
| Audit-Log lesen | – | – | ✓ | ✓ |
| Benutzer und Rechte verwalten | – | – | – | ● |
| Sicherungen verwalten | – | – | – | ✓ |
| Testdaten zurücksetzen | – | – | – | ✓ |

  Testbenutzer bekommen nie Rechte, die über Testpatienten hinaus wirken (Versorger, Vorlagen, Audit-Log, Benutzer,
  Sicherungen, Testdaten, Wiederöffnen). Fehlendes Recht → 403 „Dafür fehlt das Recht „…“.“; abgelaufene Sitzung → 403
  „Anmeldedaten fehlen.“ bzw. „Anmeldung mit zweitem Faktor erforderlich.“, die Oberfläche wechselt dann zur Anmeldung.
  Admin bei einer echten Akte → 403 „Als Admin nur bei Testpatienten möglich …“. Die Oberfläche zeigt diese Meldungen nicht:
  Was jemand nicht darf, wird ausgeblendet; lehnt der Server trotzdem ab (Recht gerade entzogen), erscheint nur ein
  neutraler Hinweis (F71). Jede Antwort an angemeldete Benutzer trägt den Kopf `X-EPM-Rechte` (Kennung des Rechtestands).
- Migrationen liegen im Repo (`backend/*/migrations/`). Ändert sich ein Modell, erzeugt GitHub Actions die Migration,
  legt sie als Commit „Migrationen automatisch erzeugt (CI)“ ab und prüft danach `makemigrations --check`.
  Schutz-Trigger werden nach jedem `migrate` gesetzt (`audit/schutz.py`).
- Tests: `accounts/tests.py`, `patienten/tests.py`, `infusionen/tests.py`, `stammdaten/tests.py`; gemeinsame Hilfen in
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
- **Endpunkt:** `GET /api/auth/ich/` → `Ich`; `PATCH /api/auth/ich/` `{"darstellung"?: Darstellung, "startseite"?: {"karten": [...]}}`
- **Darstellung:** `schema` standard|individuell|kontrast|dunkel · `auto_dunkel` bool · `akzent`
  nachtblau|petrol|blau|gruen|orange|aubergine|schiefer|eigen + `akzent_eigen` #RRGGBB · `hintergrund`
  weissgrau|hellgrau|grau|kraeftig|blaugrau|sand|eigen + `hintergrund_eigen` · `dichte` grosszuegig|normal|kompakt|sehrkompakt ·
  `schriftgroesse` klein|normal|gross|sehrgross · `schriftstaerke` normal|kraeftig
- **Startseite:** `karten: [{"id": termine|gewicht|plaene|pruefen|aktiv, "sichtbar": bool}]` in Anzeigereihenfolge; fehlende Karten
  werden sichtbar angehängt.
- **Validierung:** unbekannte Schlüssel → 400; eigene Akzentfarbe braucht Kontrast ≥ 4,5:1 zu Weiß oder zur Schrift #1B1932;
  eigene Hintergrundfarbe muss hell genug sein (Leuchtdichte ≥ 0,6); Karten nur einmal.
- **Tabellen:** `accounts_user` (`darstellung`, `startseite`)
- **Fehlerfälle:** 400 `{"<schlüssel>": [...]}`
- **Teststatus:** Backend-Tests grün (`MeinKonto.*`). Browsertests grün: `konto.spec.ts` „Darstellung wählen, eigene Farben prüfen, nach Neuladen erhalten, zurücksetzen“, `start.spec.ts` „Startseite anpassen: Karte ausblenden bleibt gespeichert“; Neustart geprüft in `zz-neustart.spec.ts` (Darstellung „Dunkel“ und ausgeblendete Karte,
  beide vor dem Neustart in der Oberfläche gewählt).
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
- **Ansicht:** 2 Start
- **Endpunkt:** `GET /api/startseite/`
- **Response 200:** `{"termine": {"ueberfaellig", "heute", "naechste_7_tage": [Termin]}, "gewichtswarnungen": [{patient, name,
  nummer, gewicht, prozent}] (stärkster Verlust zuerst), "gewicht_schwelle": {prozent, monate}, "infusionsplaene":
  {"entwuerfe", "aelter_als_grenze": [{id, patient, name, gueltig_ab, status, erstellt_am, erstellt_von, freigegeben_am}],
  "grenze_monate"}, "pruefen": {altdokumente, nickelallergie_unbekannt, kein_versorger, kein_kontakt, kontakt_monate},
  "zuletzt_eingetragen": [{bereich (kontakt|gewicht|dokument|plan), bezeichnung, objekt_id, patient, name, zeitpunkt, person}],
  "zahlen": {in_betreuung, mit_offenem_termin}}`
- **Validierung:** Testbenutzer sieht nur Testpatienten; Testpatienten fehlen in Zahlen und Prüfliste.
- **Tabellen:** `patienten_*` (+ Historie), `infusionen_infusionsplan`, `stammdaten_einstellungen`
- **Fehlt:** Backup-Status für die Kopfzeile (hängt an F62).
- **Teststatus:** Backend-Tests grün (`Patientenliste.test_startseite`, `test_pruefen_filter`, `Musterdaten.*`). Browsertests grün: `start.spec.ts` „Startseite zeigt Termine, Gewichte, Pläne, Prüfliste und Zuletzt eingetragen“,
  `start.spec.ts` „Termin von der Startseite anlegen und als erledigt abhaken“ (mit Neustart), `start.spec.ts` „Startseite anpassen: Karte ausblenden bleibt gespeichert“. Es fehlt der Backup-Status (F62), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

---

## C · Patienten und Akte

### F14 Patientenliste mit Filtern und Suche
- **Ansicht:** 3 Patientenliste
- **Endpunkte:** `GET /api/patienten/`, `GET /api/patienten/zaehler/` → `{in_betreuung, abgeschlossen, mit_hinweisen,
  gewichtsverlust, termin_woche}` (ohne Testpatienten)
- **Query:** `status=in_betreuung|abgeschlossen`, `schnellfilter=hinweise|gewichtsverlust|termin_woche`, `suche` (Wörter;
  Datum TT.MM.JJJJ oder JJJJ-MM-TT = Geburtsdatum, Ziffern = Nummer, sonst Name/Vorname/Ort), `pruefen=altdokumente|
  nickelallergie|kein_versorger|kein_kontakt`, `versorger`, `ansprechpartner`, `katheter`, `nickelallergie`, `test=nur|ohne`,
  `ordering=letzter_kontakt|nachname|nummer|geburtsdatum|geaendert_am` (Standard: letzter Kontakt, neueste zuerst, ohne Kontakt am Ende)
- **Response 200:** Seite mit `[{id, nummer, nachname, vorname, geburtsdatum, alter, ort, katheter, katheter_name, versorger,
  versorger_name, ansprechpartner, ansprechpartner_name, nickelallergie, ist_abgeschlossen, abgeschlossen_am,
  abschluss_anlass, ist_test, kennzahlen: {gewicht {kg, am}, trend {richtung down|up|flat, prozent, warnung},
  letzter_kontakt, termin_woche, hinweise: [{art: gewicht|plan|versorger|kontakt, text}]}}]`
- **Logik:** Trend gegen die Messung, die den eingestellten Zeitraum zurückliegt; Pfeil „gleich“ bei weniger als ±1 %
  (Zwischenlösung, siehe U11); Hinweise „Gewicht −8,6 % in 3 Mon.“, „Plan älter als 12 Mon.“, „Kein Versorger“,
  „Kein Kontakt seit über 12 Mon.“ (Monate aus den Einstellungen, U4).
- **Tabellen:** `patienten_patient`, `patienten_gewichtsmessung`, `patienten_kontakt`, `patienten_termin`,
  `infusionen_infusionsplan`, `stammdaten_einstellungen`
- **Teststatus:** Backend-Tests grün (`Patientenliste.*`, `test_testbenutzer_sieht_nur_testpatienten`). Browsertests grün: `patienten.spec.ts` „Patientenliste: Filter, Schnellfilter, Sortierung, abgeschlossene Akten“ (Freitext,
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
  termine_offen, infusionsplaene}}`
- **Fehlerfälle:** 404 unbekannt oder außerhalb des Bereichs
- **Teststatus:** Backend-Tests grün (`test_versionen_der_textfelder`, `test_termin_mit_ort`, `Infusionsplaene.test_ablauf`). Browsertests grün:
  `akte.spec.ts` „Akte aus der Liste öffnen: Kopf mit Kerndaten und Gewichtswarnung“, `layout.spec.ts` „Unter 1280 px stehen die Karten der Akte untereinander“,
  `akte.spec.ts` „Ärzte aus der gemeinsamen Liste zuordnen, Bezugspersonen mit Auskunft pflegen“ (Kopfhöhe bleibt mit Personen gleich;
  „Auskunft an“ führt zur Person).
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
  Unterschrift: „Maschinell erstellt, geprüft und freigegeben von <Mediziner> am <Datum>.“
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
  falscher Bestätigungscode macht ihn ungültig. Der Grund bleibt im Protokoll – die Oberfläche bittet, keine Namen oder
  Gesundheitsangaben der fremden Person hineinzuschreiben.
- **Sicherungen und Wiederherstellung:** Ältere Sicherungen enthalten das Dokument bis zu ihrem Ablauf (14 Tage, F61).
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
- **Validierung:** Rolle Mediziner und Recht „Dokumente endgültig löschen“ (nur Mediziner, keiner anderen Rolle zuweisbar);
  Grund mindestens 10 Zeichen; Akte offen; keine von EPM erzeugten Dokumente.
- **Fehlerfälle:** 400 je Feld · 403 nicht Mediziner/ohne Recht · 404 schon gelöscht
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
- **Felder:** Absender; Warnung Gewichtsverlust %, Zeitraum, Plan alt nach Monaten, Kontakt überfällig nach Monaten;
  Min/Max für Energie, Gesamtvolumen, Glucose, Aminosäuren, Lipide, Natrium, Kalium, Gewicht, Größe.
- **Validierung:** Minimum < Maximum je Paar; Audit-Log „Grenzwert „Kontakt überfällig“ von 6 auf 12 Monate geändert“.
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
  02.10.2026: „Dokumente endgültig löschen“ nur Mediziner), anderen Rollen nicht zuweisbar → 400 „Dieses Recht ist Mediziner
  vorbehalten.“, in der Matrix ausgegraut; Testbenutzer ohne Rechte über Testpatienten hinaus.
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
- **Endpunkt:** `GET /api/protokoll/?gruppe=anmeldung,fehlversuch,benutzer,vorlage,backup,export,abschluss&benutzer&von&bis&search`
  → `[{id, zeitpunkt, art, art_name, gruppe, gruppe_name, beschreibung, benutzer, person, benutzername, objekt, details, ip, geraet}]`
- **Logik:** `beschreibung` wie im Entwurf („Anmeldung mit 2FA“, „Falsches Passwort (3. Versuch)“, „5 falsche Passwörter in
  4 Minuten, Konto gesperrt“, „Benutzer k.oezdemir angelegt (Mitarbeiter), Einmal-Kennwort erzeugt“, „Akte Weber, Anna
  (Nr. 0231) abgeschlossen, Anlass: verstorben“, „Grenzwert „Kontakt überfällig“ von 6 auf 12 Monate geändert“).
  Hinweis auf gesperrte Konten: F08.
- **Validierung:** Recht „Audit-Log lesen“ (Standard: Mediziner, Admin); unbekannte Gruppe → 400.
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
- **Teststatus:** Backend-Tests grün (`test_historie_ist_unveraenderlich`, `test_trigger_verhindert_aenderung_in_der_datenbank`,
  `test_vitamine_freigegebener_plaene_in_der_datenbank_geschuetzt`). Browsertests grün: `akte.spec.ts` „Kontakt mit Wiedervorlage erfassen, suchen, stornieren“ (Kontakt nur stornieren),
  `plaene.spec.ts` „Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen“ (freigegebener Plan ohne „Bearbeiten“), `dokumente.spec.ts` „Dokumente hochladen, Typ am Inhalt prüfen, Metadaten ändern, ausblenden, herunterladen; Verlauf“ (Verlauf nur lesend).
- **Status:** ABGESCHLOSSEN UND GETESTET

---

## J · Backup und Wiederherstellung

### F61 Tägliche verschlüsselte Sicherung
- **Ist:** `/usr/local/sbin/epm-backup` + systemd-Timer 02:30: `pg_dump` und Dokumente als `.tar.gz`, Löschliste (F73) als
  eigene Datei, SHA-256, 14 Tage.
- **Fehlt:** Uhrzeit 02:00, Verschlüsselung mit `age`, Status-Datei für das Backend.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F62 Sicherungen anzeigen, „Jetzt sichern“
- **Geplant:** `GET /api/backup/` → `{"letzte": {...}, "uebertragung": {...}, "speicher": {"belegt", "gesamt"}, "sicherungen": [{zeitpunkt, art, groesse, verschluesselt, uebertragen}]}`;
  `POST /api/backup/jetzt/`. Der Container bekommt keinen Zugriff auf den Host: Auftrag und Status laufen über ein gemeinsames
  Verzeichnis, ausgeführt von einem systemd-Dienst auf dem Server.
- **Status:** NICHT ABGESCHLOSSEN

### F63 Wiederherstellen
- **Geplant:** `POST /api/backup/{id}/wiederherstellen/` `{"kennwort", "code"}`; vorher automatische Sicherung des aktuellen Stands;
  Protokoll im Audit-Log. Die aktuelle Löschliste (`data/loeschliste/`) bleibt dabei unangetastet (auf einem neuen Server: die
  neueste aus den Sicherungen); der anschließende Start des Backends löscht und schwärzt endgültig gelöschte Dokumente erneut
  (F73, Art. 17 DSGVO).
- **Status:** NICHT ABGESCHLOSSEN

### F64 Übertragung zur Nextcloud/NAS
- **Festlegung 01.10.2026 (U9):** Der Server schiebt – wie heute: ein rsync-Dienst überträgt die Sicherungen in einen
  WebDAV-Ordner (Nextcloud, von dort auf die NAS gespiegelt).
- **Geplant:** nach der nächtlichen Sicherung (F61) überträgt ein systemd-Dienst auf dem Host die verschlüsselten Dateien per
  rsync in den WebDAV-Ordner; Ergebnis („übertragen am …“ bzw. Fehler) in der Status-Datei, angezeigt in F62 und auf der
  Startseite (F13). Zugangsdaten nur auf dem Host (`/etc/epm`), nicht im Container.
- **Festlegung 01.10.2026:** Ziel (WebDAV-Adresse, Benutzer, Kennwort, Zeitfenster) pflegt die Administration selbst in der
  Oberfläche und kann es jederzeit ändern; Zugangsdaten nicht im Code oder in Dateien von Hand.
- **Festlegung 01.10.2026:** Übertragung mit rclone (WebDAV direkt, ohne Einbinden per davfs2; nur geänderte Dateien, mit Prüfsumme).
- **Status:** NICHT ABGESCHLOSSEN

---

## K · Migration

### F65 Import der Altdaten
- **Geplant:** Befehl `manage.py epm_import_alt` nach den 17 Regeln der Datenanalyse, Importprotokoll, Zählungen alt gegen neu.
- **Abhängigkeit:** frischer `mysqldump` (die Tabellen `gewichte`/`kontakte` im alten Dump haben kein `lastchange`).
- **Status:** NICHT ABGESCHLOSSEN

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

| Nr. | Was fehlt | Warum | Betroffene Dateien | Abhängigkeiten | Nächster Schritt |
|---|---|---|---|---|---|
| O-07 | Backup-Status auf der Startseite (F13) | hängt an der Backup-Steuerung | `patienten/api.py` | O-23 | Status-Datei lesen |
| O-23 | Backup 02:00 verschlüsselt, Steuerung aus der Oberfläche, Übertragung mit rclone in den WebDAV-Ordner (F61–F64; U9) | nicht umgesetzt | `rollout/epm-backup.sh`, `rollout/04-projekt.sh`, neu: `audit/backup.py`, systemd-Dienste | WebDAV-Adresse und Zugang trägt die Administration selbst in der Oberfläche ein (Wunsch 01.10.2026; verschlüsselt gespeichert), Test gegen einen WebDAV-Testserver in CI | `age`-Schlüssel, Auftragsverzeichnis, Status-Datei, Endpunkte, rclone-Dienst |
| O-24 | Serverskripte angleichen | Festlegungen aus „EPM-Server Aufbau“ fehlen | `rollout/01-basis.sh`, `rollout/02-docker.sh` | – | Adressbereiche, `epm.service`, needrestart, Swap |
| O-25 | Import Altdaten (F65) | Rollout-Schritt 7 | neu: `patienten/management/commands/epm_import_alt.py` | frischer Dump | Import mit Protokoll, setzt `typ_geprueft`/`datum_quelle` |

## Unklarheiten (nicht eigenmächtig entschieden)

| Nr. | Frage | Betrifft | Zwischenlösung |
|---|---|---|---|
| U1 | ~~Bedeutung und Einheit von Pantozol 0–3 / Tage~~ **Geklärt 01.10.2026:** Pantozol® 40 mg, Pantozol® 20 mg, Nexium®; Zeiten morgens, mittags, abends. Codes wie in `EPM_infuplan.php` (1 = 40 mg, 3 = 20 mg, 2 = Nexium®, 0 = kein; Zeiten 4/2/1 addiert) | F38 | – |
| U2 | ~~Gesamtvolumen und Laufzeit eingeben oder berechnen?~~ **Geklärt 01.10.2026:** Gesamtvolumen = Gewicht × 35 ml (wie im Altsystem), Laufzeit manuell; Rate = Gesamtvolumen ÷ Laufzeit | F39, F48 | – |
| U3 | „geändert“-Hinweis an einem Kontakt im Entwurf widerspricht „unveränderlich“ | F26 | Beschluss gilt |
| U4 | Plan-Hinweis „6 Monate“ in der Liste vs. 12 Monate in den Grenzwerten | F14 | Grenzwert gilt (Text nennt die eingestellten Monate) |
| U5 | Felder Krankenkasse, Telefon 2, Bemerkung (nicht im Entwurf) | F16 | bleiben gespeichert, nicht angezeigt |
| U6 | Kontaktart (nicht im Entwurf) | F26 | bleibt gespeichert, nicht angezeigt |
| U7 | Rolle des Testbenutzers: Mitarbeiter (Entwurf) oder Mediziner (Code) | F57 | Mediziner |
| U8 | ~~Gerätename im Audit-Log oder nur IP/Browser~~ **Geklärt 01.10.2026:** IP und Browser reichen | F11, F58 | – |
| U9 | ~~Übertragung zur Nextcloud: Server schiebt oder Gegenseite holt ab~~ **Geklärt 01.10.2026:** Server schiebt in einen WebDAV-Ordner, Werkzeug rclone (Festlegung 01.10.2026) | F64 | – |
| U10 | ~~Wer pflegt Versorger und Ansprechpartner?~~ **Erledigt 01.10.2026:** Rechte sind je Gruppe einstellbar (F66); Standard Mitarbeiter, Mediziner und Admin | F45, F46 | – |
| U11 | ~~Ab welcher Änderung zeigt der Trend-Pfeil „gleich“?~~ **Bestätigt 01.10.2026:** weniger als ±1 % = gleich | F14 | – |
| U12 | ~~Darf der Admin auch Patientendaten schreiben?~~ **Geklärt 01.10.2026:** Admins dürfen alles, Patientendaten schreiben sie nur bei Testpatienten; echte Akten nur lesen, Wiederöffnen, Benutzer und Sicherungen bleiben | F66 | – |
| U13 | ~~Energie im Infusionsplan: Lipide 9 oder 9,15 kcal/g, Albumin mit oder ohne Energie?~~ **Geklärt 01.10.2026:** wie in `EPM_infuplan.php`: Lipide 9,15 kcal/g, Humanalbumin in ml ohne Energie | F33, F39 | – |
| U14 | ~~Stabilitätsprüfung Calcium + Magnesium und Vorbelegung des ersten Plans je kg übernehmen?~~ **Geklärt 01.10.2026:** ja, beides wie im Altsystem (Stabilität als Hinweis, Speichern bleibt möglich); Präparate werden beim ersten Plan **nicht** vorausgewählt | F32, F33 | – |
| U15 | ~~Muss beim endgültigen Löschen auch der Titel aus Historie und Audit-Log verschwinden?~~ **Geklärt 02.10.2026: nach geltender DSGVO.** Titel, Dateiname, Notiz und Datum werden überall entfernt (Art. 17 Abs. 1 d, Art. 5 Abs. 1 c/e); es bleibt der Nachweis ohne Inhalt (Art. 5 Abs. 2, Art. 33 Abs. 5; § 630f BGB); Sicherungen laufen nach 14 Tagen ab, nach einer Wiederherstellung wird erneut gelöscht | F73 | – |

## Änderungsprotokoll

| Datum | Stand | Änderung |
|---|---|---|
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
| 02.10.2026 | Runde 3 (`df02dda`–`e709bee`) | Rückmeldungen zur PDF-Funktion: Dokumentvorlagen als Bereich der Vorlagen, Felder verschiebbar, Schriftgröße und Titel-Ausrichtung wirksam, Planansicht in der Akte = echte PDF (F31), Aktenkopf mit festem Raster und anklickbarem „Auskunft an“ (F17). Neu: Dokument dem richtigen Patienten zuordnen (F72) und endgültig löschen nur durch Mediziner mit Kennwort, 2FA und Bestätigungscode (F73). Fehler behoben: Datenmigration „Kontakt überfällig“ brach auf bestehender Datenbank ab (Grund > 100 Zeichen); Grund beim Wiederöffnen begrenzt |
| 01.10.2026 | Runde 3 (`0624527`–`ca9f858`) | PDF-Erzeugung mit WeasyPrint (F51), Dokumentvorlagen mit Editor (F50), Freigabe-PDF mit SHA-256 und Prüfung beim Öffnen (F35, F37; Nginx reicht `X-EPM-Pruefung` weiter), Akte, Verlauf, Audit-Log und Zugangsblatt als PDF (F23, F24, F59, F55). Infusionsplan-PDF nach dem Altsystem, auf Wunsch neu gestaltet wie ein Laborbefund und wie die Oberfläche (Kopfkarte, Karten, Menge/Einheit in eigenen Spalten, Titel neben dem Logo, ohne Linie, fax-tauglich, einseitig); Laufzeit 0 als „—“; neue Bausteine und Optionen im Editor; Datenfeld-Einfügen nimmt den aktuellen Feldinhalt (Fehler behoben) |
| 01.10.2026 | Runde 3 (`a30b26d`) | „Kein Kontakt seit …“ nach 4 statt 12 Monaten (Patienten kommen meist quartalsweise): Standard in den Einstellungen, Datenmigration stellt einen unveränderten Wert 12 um (mit Grund in der Historie); wirkt auf Hinweis in der Patientenliste und „Nach und nach prüfen“ auf der Startseite; Backend-Test `test_kontakt_ueberfaellig_nach_4_monaten` |
| 01.10.2026 | Runde 3 (`b37d606` und folgende) | Nicht Erlaubtes ausblenden (F71): keine Fenster oder Meldungen mit „Dafür fehlt das Recht“ mehr; Rechteänderungen wirken in der Oberfläche ohne neue Anmeldung (Kopf `X-EPM-Rechte`); abgelehnte Aktionen nur mit neutralem Hinweis; ausgeblendete Fenster öffnen sich nicht von selbst wieder |
