# EPM – Nachweis der Backend-Funktionen

Stand: 01.10.2026 · Code-Stand: Runde 1 (Commits `c387b7b` bis `0e25377`) · Grundlage: Altsystem-Datenanalyse mit
Entscheidungen, Entwurf „EPM Oberfläche“ (23 Ansichten), „EPM-Server Aufbau“.

## Statuswerte

| Status | Bedeutung |
|---|---|
| ABGESCHLOSSEN UND GETESTET | über das bestehende Frontend mit echtem Backend und echter Datenbank getestet |
| TEILWEISE ABGESCHLOSSEN | Backend-Teil ganz oder zum Teil vorhanden, Frontend-Anbindung und/oder Teile der Logik fehlen |
| NICHT ABGESCHLOSSEN | beschlossen, aber noch nicht umgesetzt |
| BLOCKIERT DURCH FEHLENDE INFORMATION | Umsetzung hängt an einer offenen fachlichen Frage |

**Keine Funktion ist derzeit ABGESCHLOSSEN UND GETESTET**, weil es noch keinen React-Code gibt. Die Oberfläche liegt nur
als klickbarer Entwurf vor.

Teststatus-Angaben beziehen sich auf die automatischen Tests in `backend/*/tests.py`. Sie laufen bei jedem Push in
GitHub Actions gegen ein echtes PostgreSQL 18 (Workflow `.github/workflows/backend.yml`, Ergebnis als Kommentar am
Commit) und nach jedem `sudo epm-update` auf dem Server. Stand 01.10.2026: **57 von 57 Tests grün** (Lauf 36827241798, Commit `0e25377`).
„Backend-Test grün“ heißt: API-Aufruf → Validierung → Logik → Datenbank → Antwort geprüft, ohne Oberfläche.

## Übersicht

| Nr. | Funktion | Ansicht (Entwurf) | Status |
|---|---|---|---|
| F01 | Sitzungsstatus und CSRF-Token | 1 Anmeldung | TEILWEISE ABGESCHLOSSEN |
| F02 | Anmeldung mit Benutzername und Kennwort | 1 Anmeldung | TEILWEISE ABGESCHLOSSEN |
| F03 | Zweiter Faktor bei der Anmeldung | 1 Anmeldung | TEILWEISE ABGESCHLOSSEN |
| F04 | Eigenes Kennwort setzen und ändern | 1 Anmeldung, 14 Mein Konto | TEILWEISE ABGESCHLOSSEN |
| F05 | Authenticator einrichten und ersetzen | 1 Anmeldung, 14 Mein Konto | TEILWEISE ABGESCHLOSSEN |
| F06 | Notfall-Codes neu erzeugen | 14 Mein Konto | TEILWEISE ABGESCHLOSSEN |
| F07 | Abmelden | alle Ansichten (Seitenleiste) | TEILWEISE ABGESCHLOSSEN |
| F08 | Konto sperren nach 5 Fehlversuchen | 1 Anmeldung, 17 Benutzer, 20 Audit-Log | TEILWEISE ABGESCHLOSSEN |
| F09 | Eigenes Profil, Darstellung und Startseite speichern | 14 Mein Konto, 2 Start | TEILWEISE ABGESCHLOSSEN |
| F10 | Sicherheitsstatus im Konto | 14 Mein Konto | TEILWEISE ABGESCHLOSSEN |
| F11 | Angemeldete Sitzungen anzeigen und abmelden | 14 Mein Konto | TEILWEISE ABGESCHLOSSEN |
| F12 | Automatische Abmeldung nach 30 Minuten | alle | TEILWEISE ABGESCHLOSSEN |
| F13 | Startseite | 2 Start | TEILWEISE ABGESCHLOSSEN |
| F14 | Patientenliste mit Filtern und Suche | 3 Patientenliste | TEILWEISE ABGESCHLOSSEN |
| F15 | Doppelprüfung beim Anlegen | 12 Neuer Patient | TEILWEISE ABGESCHLOSSEN |
| F16 | Patient anlegen | 12 Neuer Patient | TEILWEISE ABGESCHLOSSEN |
| F17 | Akte lesen mit Patientenkopf | 4 Patientenakte | TEILWEISE ABGESCHLOSSEN |
| F18 | Stammdaten, Diagnose, Therapie, Empfehlung ändern | 4 Akte, 5 Diagnose und Therapie | TEILWEISE ABGESCHLOSSEN |
| F19 | Versionen je Textfeld | 5 Diagnose und Therapie | TEILWEISE ABGESCHLOSSEN |
| F20 | Akte abschließen | 4 Akte (Menü ⋯) | TEILWEISE ABGESCHLOSSEN |
| F21 | Akte wieder öffnen | 3 Liste (Abgeschlossen) | TEILWEISE ABGESCHLOSSEN |
| F22 | Verlauf je Akte | 10 Verlauf | TEILWEISE ABGESCHLOSSEN |
| F23 | Akte als PDF | 3 Liste, 4 Akte | NICHT ABGESCHLOSSEN |
| F24 | Verlauf als PDF | 10 Verlauf | NICHT ABGESCHLOSSEN |
| F25 | Gewicht erfassen, korrigieren, lesen | 4 Akte | TEILWEISE ABGESCHLOSSEN |
| F26 | Kontakte anlegen, lesen, durchsuchen | 6 Kontakte | TEILWEISE ABGESCHLOSSEN |
| F27 | Kontakt stornieren | 6 Kontakte | TEILWEISE ABGESCHLOSSEN |
| F28 | Kontakt mit Wiedervorlage in einem Schritt | 6 Kontakte | TEILWEISE ABGESCHLOSSEN |
| F29 | Termine anlegen, ändern, lesen | 2 Start, 4 Akte | TEILWEISE ABGESCHLOSSEN |
| F30 | Termin als erledigt markieren | 2 Start | TEILWEISE ABGESCHLOSSEN |
| F31 | Infusionspläne eines Patienten lesen | 8 Infusionspläne | TEILWEISE ABGESCHLOSSEN |
| F32 | Neuer Plan als Entwurf | 7 Neuer Infusionsplan | TEILWEISE ABGESCHLOSSEN |
| F33 | Entwurf bearbeiten | 7 Neuer Infusionsplan | TEILWEISE ABGESCHLOSSEN |
| F34 | Entwurf verwerfen | 8 Infusionspläne | TEILWEISE ABGESCHLOSSEN |
| F35 | Plan freigeben | 8 Infusionspläne | TEILWEISE ABGESCHLOSSEN |
| F36 | Vergleich mit dem Vorgänger | 8 Infusionspläne | TEILWEISE ABGESCHLOSSEN |
| F37 | Gespeicherte Plan-PDF öffnen mit SHA-256-Prüfung | 8 Infusionspläne | NICHT ABGESCHLOSSEN |
| F38 | Pantozol im Plan | 7, 8 | BLOCKIERT DURCH FEHLENDE INFORMATION |
| F39 | Gesamtvolumen, Laufzeit und Rate | 7, 8 | BLOCKIERT DURCH FEHLENDE INFORMATION |
| F40 | Dokument hochladen | 9 Dokumente | TEILWEISE ABGESCHLOSSEN |
| F41 | Dokumente lesen, Metadaten ändern, ausblenden | 9 Dokumente | TEILWEISE ABGESCHLOSSEN |
| F42 | Datei anzeigen und herunterladen | 9 Dokumente | TEILWEISE ABGESCHLOSSEN |
| F43 | Altdokumente prüfen (Typ, Datumsquelle) | 9 Dokumente, 2 Start | TEILWEISE ABGESCHLOSSEN |
| F44 | Auswahllisten pflegen | 18 Vorlagen | TEILWEISE ABGESCHLOSSEN |
| F45 | Versorger pflegen | 13 Versorger | TEILWEISE ABGESCHLOSSEN |
| F46 | Ansprechpartner pflegen | 13 Versorger | TEILWEISE ABGESCHLOSSEN |
| F47 | Präparate pflegen | 18 Vorlagen | TEILWEISE ABGESCHLOSSEN |
| F48 | Grenzwerte und Einstellungen | 18 Vorlagen | TEILWEISE ABGESCHLOSSEN |
| F49 | Briefkopf, Absender und Logo | 18 Vorlagen | NICHT ABGESCHLOSSEN |
| F50 | Dokumentvorlagen (WYSIWYG) | 19 Dokumentvorlagen | NICHT ABGESCHLOSSEN |
| F51 | PDF-Erzeugung | Grundlage für F23, F24, F35, F37, F50, F55, F59 | NICHT ABGESCHLOSSEN |
| F52 | Benutzer lesen, anlegen, ändern | 17 Benutzer | TEILWEISE ABGESCHLOSSEN |
| F53 | Benutzer sperren und entsperren | 17 Benutzer | TEILWEISE ABGESCHLOSSEN |
| F54 | Einmal-Kennwort erzeugen | 17 Benutzer | TEILWEISE ABGESCHLOSSEN |
| F55 | Zugangsblatt drucken | 17 Benutzer | NICHT ABGESCHLOSSEN |
| F56 | 2FA zurücksetzen | 17 Benutzer | TEILWEISE ABGESCHLOSSEN |
| F57 | Testdaten zurücksetzen | 17 Benutzer | TEILWEISE ABGESCHLOSSEN |
| F58 | Audit-Log lesen und filtern | 20 Audit-Log | TEILWEISE ABGESCHLOSSEN |
| F59 | Audit-Log als PDF | 20 Audit-Log | NICHT ABGESCHLOSSEN |
| F60 | Unveränderlichkeit von Verlauf, Protokoll, Kontakten, Plänen | 10 Verlauf, 20 Audit-Log | TEILWEISE ABGESCHLOSSEN |
| F61 | Tägliche verschlüsselte Sicherung | 11 Backup | TEILWEISE ABGESCHLOSSEN |
| F62 | Sicherungen anzeigen, „Jetzt sichern“ | 11 Backup, 2 Start | NICHT ABGESCHLOSSEN |
| F63 | Wiederherstellen mit Admin-Kennwort und 2FA | 11 Backup | NICHT ABGESCHLOSSEN |
| F64 | Übertragung zur Nextcloud/NAS mit Status | 11 Backup | BLOCKIERT DURCH FEHLENDE INFORMATION |
| F65 | Import der Altdaten | – (Rollout-Schritt 7) | NICHT ABGESCHLOSSEN |

Summe (65 Funktionen): 0 abgeschlossen und getestet · 51 teilweise abgeschlossen · 11 nicht abgeschlossen · 3 blockiert.
Gegenüber dem Stand vor Runde 1 ist keine Funktion zurückgestuft worden.

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
- Rechte (Rollenmatrix aus dem Entwurf 17 · Benutzer):

| Recht | Betrachter | Mitarbeiter | Mediziner | Admin |
|---|---|---|---|---|
| Akten lesen | ✓ | ✓ | ✓ | ✓ |
| Kontakte, Gewichte, Termine erfassen | – | ✓ | ✓ | – |
| Diagnose, Therapie, Stammdaten ändern | – | ✓ | ✓ | – |
| Infusionspläne anlegen und freigeben | – | – | ✓ | – |
| Akten abschließen / wieder öffnen | – | – | ✓ / – | – / ✓ |
| Versorger und Ansprechpartner pflegen (U10) | – | ✓ | ✓ | ✓ |
| Benutzer, Vorlagen, Backup | – | – | – | ✓ |

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
  startseite, rechte: {patienten_bearbeiten, plaene_bearbeiten, administration}}` (nur bei `fertig`).
- **Validierung:** –
- **Tabellen:** `django_session`, `accounts_user`, `otp_totp_totpdevice`
- **Fehlerfälle:** keine (immer 200)
- **Testschritte:** Aufruf ohne Sitzung → `anmelden`; nach Kennwort → nächster Schritt; nach 2FA → `fertig` mit Benutzer.
- **Teststatus:** Backend-Test grün (`Anmeldung.test_erstanmeldung`, 01.10.2026). Frontend fehlt.
- **Status:** TEILWEISE ABGESCHLOSSEN

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
- **Teststatus:** Backend-Tests grün (`accounts.tests.Anmeldung.*`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

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
- **Teststatus:** Backend-Test grün für Notfall-Code (`test_erstanmeldung`, `Sitzungen.*`); TOTP-Code nur bei der Einrichtung getestet.
  Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

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
- **Teststatus:** Backend-Tests grün (`test_erstanmeldung`, `Sitzungen.test_kennwortwechsel_beendet_andere_sitzungen`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F05 Authenticator einrichten und ersetzen
- **Zweck:** Authenticator-App verbinden (erste Anmeldung oder neues Telefon).
- **Endpunkte:** `POST /api/auth/2fa/einrichten/` → `{"otpauth_url": string, "qr_svg": string}`;
  `POST /api/auth/2fa/bestaetigen/` `{"code": string}` → wie F01 plus `"notfallcodes": [10 × string]` (nur einmal sichtbar)
- **Validierung:** eigenes Kennwort muss gesetzt sein; ein vorhandenes Gerät darf nur ersetzen, wer voll angemeldet ist;
  Code muss zum neuen Gerät passen.
- **Tabellen:** `otp_totp_totpdevice`, `otp_static_*`, `audit_systemereignis`
- **Fehlerfälle:** 403 Einmal-Kennwort offen oder Gerät vorhanden ohne 2FA · 400 Code falsch / Einrichtung nicht gestartet
- **Testschritte:** siehe `test_erstanmeldung`; zusätzlich zu testen: Ersetzen im Konto.
- **Teststatus:** Backend-Test grün für die Ersteinrichtung.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F06 Notfall-Codes neu erzeugen
- **Endpunkt:** `POST /api/auth/notfallcodes/` → `{"notfallcodes": [10 × string]}`
- **Zweck/Validierung:** voll angemeldet; alte Codes werden ungültig.
- **Tabellen:** `otp_static_staticdevice`, `otp_static_statictoken`, `audit_systemereignis`
- **Fehlerfälle:** 403 nicht voll angemeldet
- **Teststatus:** kein automatischer Test.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F07 Abmelden
- **Ansicht:** alle Ansichten (Seitenleiste)
- **Endpunkt:** `POST /api/auth/abmelden/` → `{"schritt": "anmelden"}`
- **Logik:** Sitzung wird beendet, Eintrag in `accounts_sitzung` entfernt, Abmeldung protokolliert.
- **Tabellen:** `django_session`, `accounts_sitzung`, `audit_systemereignis`
- **Teststatus:** Backend-Test grün (`Sitzungen.test_abmelden_entfernt_sitzung`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

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
- **Teststatus:** Backend-Test grün (`Anmeldung.test_sperre_nach_fehlversuchen`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

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
- **Teststatus:** Backend-Tests grün (`MeinKonto.*`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F10 Sicherheitsstatus im Konto
- **Zweck:** „Passwort zuletzt geändert“, „Authenticator eingerichtet am“, „8 von 10 Notfall-Codes übrig“.
- **Ansicht:** 14 Mein Konto
- **Endpunkt:** `GET /api/auth/sicherheit/` → `{"kennwort_geaendert_am", "authenticator_aktiv", "authenticator_eingerichtet_am",
  "notfallcodes_uebrig", "notfallcodes_gesamt"}`
- **Validierung:** voll angemeldet.
- **Tabellen:** `accounts_user` (`kennwort_geaendert_am`), `otp_totp_totpdevice`, `otp_static_statictoken`, `audit_systemereignis`
  (Zeitpunkt der Einrichtung)
- **Fehlerfälle:** 403 nicht voll angemeldet
- **Teststatus:** Backend-Test grün (in `test_erstanmeldung`: 10 von 10, nach Notfall-Code 9). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

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
- **Teststatus:** Backend-Tests grün (`Sitzungen.*`). Gerätename statt Browser: Unklarheit U8. Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F12 Automatische Abmeldung nach 30 Minuten
- **Umsetzung:** `SESSION_COOKIE_AGE` = 30 min, bei jeder Anfrage verlängert (`EPM_SITZUNG_MINUTEN`).
- **Teststatus:** nicht automatisch getestet.
- **Status:** TEILWEISE ABGESCHLOSSEN (Frontend muss auf 403 mit Wechsel zur Anmeldung reagieren)

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
- **Teststatus:** Backend-Tests grün (`Patientenliste.test_startseite`, `test_pruefen_filter`, `Musterdaten.*`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
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
- **Teststatus:** Backend-Tests grün (`Patientenliste.*`, `test_testbenutzer_sieht_nur_testpatienten`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F15 Doppelprüfung beim Anlegen
- **Endpunkt:** `GET /api/patienten/doppelte/?geburtsdatum=JJJJ-MM-TT&nachname=&vorname=` → bis zu 10 Einträge wie F14
- **Regel:** gleiches Geburtsdatum und Nach- oder Vorname beginnt mit denselben 3 Buchstaben.
- **Teststatus:** Backend-Test grün (`test_doppelte`).
- **Status:** TEILWEISE ABGESCHLOSSEN

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
- **Fehlerfälle:** 400 Pflichtfeld/Plausibilität (dann wird nichts gespeichert) · 403 Rolle Betrachter oder Admin
- **Teststatus:** Backend-Tests grün (`test_schreibrechte`, `test_nummern`, `test_anlegen_mit_aufnahmegewicht`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

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
- **Teststatus:** Backend-Tests grün (Kopf geprüft in `test_versionen_der_textfelder`, `test_termin_mit_ort`,
  `Infusionsplaene.test_ablauf`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F18 Stammdaten, Diagnose, Therapie, Empfehlung ändern
- **Ansicht:** 4 Akte, 5 Diagnose und Therapie
- **Endpunkt:** `PATCH /api/patienten/{id}/`
- **Validierung:** wie F16; Texte werden auf erlaubte Formatierung bereinigt (`epm/sanitize.py`); Akte darf nicht abgeschlossen sein.
- **Tabellen:** `patienten_patient`, `patienten_historicalpatient`
- **Fehlerfälle:** 400 · 403 Rolle · 409 Akte abgeschlossen
- **Teststatus:** Backend-Tests grün (`test_verlauf_nach_bereichen`, `test_versionen_der_textfelder`,
  `test_abgeschlossene_akte_ist_gesperrt`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F19 Versionen je Textfeld
- **Zweck:** „Version 12 · geändert 12.08.2026, 15:12 von Dr. M. Berger · Versionen“ für Diagnose, Empfehlung, Therapie.
- **Ansicht:** 5 Diagnose und Therapie
- **Endpunkt:** `GET /api/patienten/{id}/versionen/?feld=diagnose|therapie|empfehlung` →
  `{"feld", "version": n, "fassungen": [{"version", "zeitpunkt", "person", "text"}]}` (neueste zuerst); Kopfangaben in F17.
- **Logik:** jede tatsächliche Änderung des Feldes in der Historie ist eine Fassung.
- **Tabellen:** `patienten_historicalpatient`
- **Fehlerfälle:** 400 anderes Feld · 404
- **Teststatus:** Backend-Test grün (`test_versionen_der_textfelder`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F20 Akte abschließen
- **Ansicht:** 4 Akte (Menü ⋯)
- **Endpunkt:** `POST /api/patienten/{id}/abschliessen/` `{"anlass": "verstorben"|"therapie_beendet"|"betreuung_gewechselt",
  "datum"?: Datum, "notiz"?: string}` → Akte wie F17
- **Validierung:** **nur Mediziner** (Rollenmatrix, `AbschlussRecht`); Anlass Pflicht; Datum gültig und nicht in der Zukunft;
  Akte noch offen.
- **Tabellen:** `patienten_patient`, `audit_systemereignis` („Akte Name, Vorname (Nr. 0077) abgeschlossen, Anlass: …“)
- **Fehlerfälle:** 400 Anlass/Datum · 403 Rolle · 409 bereits abgeschlossen
- **Teststatus:** Backend-Tests grün (`test_abschliessen_nur_mediziner`, `test_abgeschlossene_akte_ist_gesperrt`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F21 Akte wieder öffnen
- **Endpunkt:** `POST /api/patienten/{id}/wieder-oeffnen/` `{"grund": string}` → Akte
- **Validierung:** nur Admin; Grund Pflicht; Akte muss abgeschlossen sein. Grund steht in der Historie.
- **Fehlerfälle:** 400 · 403
- **Teststatus:** Backend-Test grün.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F22 Verlauf je Akte
- **Ansicht:** 10 Verlauf
- **Endpunkt:** `GET /api/patienten/{id}/verlauf/?bereich=stammdaten|diagnose|therapie|empfehlung|gewichte|kontakte|termine|
  dokumente|infusionsplaene&person=<id>` → `[{bereich, aktion, objekt_id, art (angelegt|geändert|gelöscht), zeitpunkt, person,
  person_id, grund, aenderungen: [{feld, alt, neu}]}]`
- **Logik:** Änderungen an der Akte werden nach Feld auf Stammdaten, Diagnose, Therapie und Empfehlung verteilt; `aktion`:
  angelegt, geändert, hochgeladen, storniert, erledigt, freigegeben, abgelöst, abgeschlossen, wieder geöffnet.
- **Tabellen:** alle `*_historical*`
- **Teststatus:** Backend-Test grün (`test_verlauf_nach_bereichen`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F23 Akte als PDF / F24 Verlauf als PDF
- **Endpunkte (geplant):** `GET /api/patienten/{id}/pdf/`, `GET /api/patienten/{id}/verlauf/pdf/` → `application/pdf`; Export
  wird im Audit-Log protokolliert (Art `export`).
- **Abhängigkeit:** F51 PDF-Erzeugung, F50 Vorlage „Patientendatenblatt“.
- **Status:** NICHT ABGESCHLOSSEN (beide)

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
- **Teststatus:** Backend-Tests grün (`test_plausibilitaet_gewicht`, `test_gewichtswarnung`, `test_anlegen_mit_aufnahmegewicht`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F26 Kontakte anlegen, lesen, durchsuchen
- **Ansicht:** 6 Kontakte
- **Endpunkte:** `GET /api/kontakte/?patient=<id>&search=<text>`, `POST /api/kontakte/`; `PATCH`/`DELETE` → 405
- **Request:** `{"patient", "text" (formatiert, Pflicht), "zeitpunkt"?, "wiedervorlage"?}` (im Code zusätzlich `art`, Unklarheit U6)
- **Response:** `{id, patient, zeitpunkt, art, art_name, text, erfasst_am, erfasst_von_name, storniert_am, storniert_von_name,
  storno_grund, termine: [{id, art, faellig_am, uhrzeit, ort, erledigt}]}`
- **Validierung:** Text bereinigt; Zeitpunkt nicht in der Zukunft; Akte offen. Unveränderlich: Modell + Datenbank-Trigger.
- **Tabellen:** `patienten_kontakt`, `patienten_historicalkontakt`
- **Teststatus:** Backend-Tests grün (`KontaktRegeln.*`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F27 Kontakt stornieren
- **Endpunkt:** `POST /api/kontakte/{id}/storno/` `{"grund": string}` → Kontakt
- **Validierung:** Grund Pflicht; nur einmal; Akte offen. Trigger erlaubt nur die Storno-Felder.
- **Fehlerfälle:** 400 · 403 · 409
- **Teststatus:** Backend-Test grün (`test_storno_genau_einmal`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F28 Kontakt mit Wiedervorlage in einem Schritt
- **Zweck:** Entwurf 6: Kontakt speichern und dabei Rückruf/Wiedervorlage/Praxistermin mit Datum und Uhrzeit anlegen.
- **Ansicht:** 6 Kontakte
- **Endpunkt:** `POST /api/kontakte/` mit `"wiedervorlage": {"art": praxistermin|rueckruf|wiedervorlage|sonstiges (Standard
  wiedervorlage), "ort"?: Terminort-ID, "faellig_am", "uhrzeit"?, "titel"?, "notiz"?}`
- **Logik:** Kontakt und Termin in einer Transaktion; Termin verweist auf den Kontakt; Titel ohne Angabe = Art.
- **Validierung:** Datum nicht in der Vergangenheit; Ort aus Liste „Terminort“; bei Fehler wird **nichts** gespeichert.
- **Tabellen:** `patienten_kontakt`, `patienten_termin` (+ Historie)
- **Fehlerfälle:** 400 `{"wiedervorlage": {...}}`
- **Teststatus:** Backend-Tests grün (`test_kontakt_mit_wiedervorlage`, `test_wiedervorlage_wird_geprueft`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F29 Termine anlegen, ändern, lesen
- **Ansicht:** 2 Start, 4 Akte
- **Endpunkte:** `GET /api/termine/?patient&art&von&bis&offen`, `POST /api/termine/`, `PATCH /api/termine/{id}/`
- **Request:** `{"patient", "art": "praxistermin"|"rueckruf"|"wiedervorlage"|"sonstiges", "faellig_am", "uhrzeit"?, "ort"?
  (Terminort-ID), "bei"? (Freitext, bleibt für Altdaten), "titel", "notiz"?, "kontakt"?}`
- **Response:** zusätzlich `ort_name`, `patient_name`, `erledigt_am`, `erledigt_von_name`, `angelegt_von_name`
- **Validierung:** Ort aus Liste „Terminort“; Kontakt gehört zum Patienten; erledigte Termine nicht änderbar; Akte offen.
- **Tabellen:** `patienten_termin`, `patienten_historicaltermin`, `stammdaten_auswahlwert`
- **Teststatus:** Backend-Test grün (`test_termin_mit_ort`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F30 Termin als erledigt markieren
- **Ansicht:** 2 Start
- **Endpunkt:** `POST /api/termine/{id}/erledigt/` → Termin mit `erledigt_am`, `erledigt_von_name`
- **Fehlerfälle:** 400 bereits erledigt · 409 Akte abgeschlossen
- **Teststatus:** Backend-Test grün (`test_termin_mit_ort`: erledigt, danach nicht mehr änderbar). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

---

## E · Infusionspläne

### F31 Infusionspläne eines Patienten lesen
- **Ansicht:** 8 Infusionspläne
- **Endpunkt:** `GET /api/infusionsplaene/?patient=<id>&status=` → Pläne mit allen Werten, `vitamine`, `vitamine_namen`,
  Positionen, `kcal_berechnet`, `kcal`, `geaenderte_felder`
- **Teststatus:** Backend-Tests grün (`infusionen.tests.*`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F32 Neuer Plan als Entwurf
- **Ansicht:** 7 Neuer Infusionsplan
- **Endpunkt:** `POST /api/infusionsplaene/entwurf/` `{"patient", "leer"?: bool, "vorlage"?: Plan-ID}` → 201 Entwurf
- **Logik:** Standard vorbelegt mit dem aktuellen Plan (Werte, Vitamine, Positionen); `leer` = „Leer beginnen“; `vorlage` =
  „Als Vorlage für neuen Plan“ aus einem früheren Plan desselben Patienten. Vorgänger ist immer der aktuelle Plan.
- **Validierung:** nur Mediziner; höchstens ein Entwurf je Patient; Vorlage vom selben Patienten; Akte offen.
- **Fehlerfälle:** 400 Entwurf vorhanden / Vorlage fremd · 403 · 409
- **Teststatus:** Backend-Tests grün (`test_ablauf`, `test_leer_beginnen_und_vorlage`, `test_abgeschlossene_akte`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F33 Entwurf bearbeiten
- **Ansicht:** 7 Neuer Infusionsplan
- **Endpunkt:** `PATCH /api/infusionsplaene/{id}/`
- **Request:** `gueltig_ab, basis_praeparat, basis_ml, glucose_praeparat, glucose_g, aminosaeuren_praeparat, aminosaeuren_g,
  lipide_praeparat, lipide_g, albumin_praeparat, albumin_g, natrium_mmol, kalium_mmol, phosphat_mmol, calcium_mmol,
  magnesium_mmol, spurenelemente, vitamine[], katheterschutz, kcal_manuell, laufzeit_h, tage_pro_woche, pantozol_stufe,
  pantozol_tage, bemerkung, positionen[]`
- **Validierung:** Präparat passt zur Kategorie (Vitamine nur Vitamin-Präparate); ausgeblendete Präparate nicht neu wählbar
  (bisherige bleiben); Präparat Pflicht, wenn Menge gesetzt; Energie, Glucose, Aminosäuren, Lipide, Natrium, Kalium in den
  Grenzen der Einstellungen; Pantozol-Regeln.
- **Tabellen:** `infusionen_infusionsplan`, `infusionen_infusionsplan_vitamine`, `infusionen_infusionsplanposition`, Historientabellen
- **Fehlerfälle:** 400 · 403 freigegeben oder Rolle · 409
- **Fehlt:** Gesamtvolumen (F39, blockiert).
- **Teststatus:** Backend-Tests grün (`test_ablauf`, `test_praeparate_werden_geprueft`,
  `test_ausgeblendetes_praeparat_bleibt_im_neuen_entwurf`, `test_kcal_manuell_und_grenze`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F34 Entwurf verwerfen
- **Ansicht:** 8 Infusionspläne
- **Endpunkt:** `DELETE /api/infusionsplaene/{id}/` → 204; nur Entwürfe (Modell + Trigger), sonst 403
- **Teststatus:** Backend-Tests grün (`test_entwurf_verwerfen`, `test_ablauf`: freigegebener Plan → 403). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F35 Plan freigeben
- **Ansicht:** 8 Infusionspläne
- **Endpunkt:** `POST /api/infusionsplaene/{id}/freigeben/` → Plan mit `status: "aktuell"`; bisheriger aktueller Plan → `abgeloest`
- **Logik:** danach unveränderlich, auch die Vitamin-Zuordnung (Trigger auf `infusionen_infusionsplan_vitamine`).
- **Fehlt:** PDF-Erzeugung bei Freigabe mit SHA-256 und Vorlagenversion, Ablage als Dokument „Von EPM erzeugt“ (F51, F50).
- **Validierung:** nur Mediziner; vollständige Prüfung aller Werte; Akte offen.
- **Teststatus:** Backend-Tests grün ohne PDF (`test_ablauf`, `test_vitamine_freigegebener_plaene_in_der_datenbank_geschuetzt`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F36 Vergleich mit dem Vorgänger
- **Ansicht:** 8 Infusionspläne
- **Endpunkt:** `GET /api/infusionsplaene/{id}/vergleich/` → `{"vorgaenger": {id, gueltig_ab, status} | null, "zeilen":
  [{"schluessel", "wert", "vorher", "jetzt", "geaendert"}], "anzahl_geaendert"}`; Zeilen in der Reihenfolge des Entwurfs
  (Basislösung … Bemerkung), Werte als Anzeigetext („Glucose 70 % · 200 g“, „80 mmol“, „Soluvit N | Vitalipid adult“).
- **Tabellen:** `infusionen_infusionsplan`, `infusionen_infusionsplan_vitamine`
- **Teststatus:** Backend-Test grün (`test_vergleich_mit_vorgaenger`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F37 Gespeicherte Plan-PDF öffnen mit SHA-256-Prüfung
- **Endpunkt (geplant):** `GET /api/infusionsplaene/{id}/pdf/` → PDF über X-Accel-Redirect; vorher Prüfsumme gegen `pdf_sha256`,
  Ergebnis im Kopf `X-EPM-Pruefung: ok|abweichend`.
- **Abhängigkeit:** F35 mit PDF.
- **Status:** NICHT ABGESCHLOSSEN

### F38 Pantozol im Plan
- **Ist:** Felder `pantozol_stufe` (0–3) und `pantozol_tage` (1–7) wie im Altsystem gespeichert und geprüft.
- **Offen:** Bedeutung und Einheit (Entwurf: „[BEDEUTUNG?] · [EINHEIT?]“), davon hängen Beschriftung und PDF ab.
- **Status:** BLOCKIERT DURCH FEHLENDE INFORMATION

### F39 Gesamtvolumen, Laufzeit und Rate
- **Ist:** `laufzeit_h` vorhanden; Gesamtvolumen und Rate (ml/h) fehlen.
- **Offen:** Werden Gesamtvolumen und Laufzeit eingegeben oder aus den Präparaten berechnet? Der Entwurf zeigt sie auf dem Plan,
  aber nicht im Eingabeformular.
- **Status:** BLOCKIERT DURCH FEHLENDE INFORMATION

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
- **Teststatus:** Backend-Tests grün (`test_dokument_upload_und_download`, `test_dokumenttyp_am_inhalt`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F41 Dokumente lesen, Metadaten ändern, ausblenden
- **Endpunkte:** `GET /api/dokumente/?patient&typ&ausgeblendet&search`, `PATCH /api/dokumente/{id}/` (`titel`, `typ`, `datum`, `notiz`, `ausgeblendet`)
- **Teststatus:** kein automatischer Test.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F42 Datei anzeigen und herunterladen
- **Endpunkt:** `GET /api/dokumente/{id}/datei/[?anzeigen=1]` → Nginx liefert über `X-Accel-Redirect: /_geschuetzt/dokumente/…`
- **Teststatus:** Kopfzeile getestet; Auslieferung durch Nginx nicht getestet.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F43 Altdokumente prüfen
- **Zweck:** importierte Dateien tragen „Typ prüfen“ und die Herkunft des Datums (PDF-Metadaten, EXIF, Dateidatum), bis jemand
  sie bestätigt.
- **Ansicht:** 9 Dokumente, 2 Start („Nach und nach prüfen“)
- **Endpunkt:** `POST /api/dokumente/{id}/geprueft/` `{"typ"?, "datum"?, "titel"?}` → Dokument mit `typ_geprueft: true`;
  geändertes Datum → `datum_quelle: "eingabe"`. Liste: `GET /api/patienten/?pruefen=altdokumente`; Anzahl in F13.
- **Felder:** `typ_geprueft` (bool, nur über diese Aktion setzbar), `datum_quelle` (eingabe|pdf|exif|dateidatum)
- **Tabellen:** `patienten_dokument` (+ Historie)
- **Fehlerfälle:** 400 Typ aus falscher Liste · 409 Akte abgeschlossen
- **Teststatus:** Backend-Test grün (`test_altdokument_pruefen`). Befüllung beim Import: F65. Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

---

## G · Stammdaten und Vorlagen

### F44 Auswahllisten pflegen
- **Ansicht:** 18 Vorlagen › Auswahllisten
- **Endpunkte:** `GET/POST /api/auswahlwerte/?liste&aktiv`, `PATCH /api/auswahlwerte/{id}/` (kein Löschen)
- **Listen:** `katheter`, `dokumenttyp`, `terminort`, `kontaktart` (U6). Musterwerte wie im Entwurf (Katheter 6, Terminorte 1,
  Dokumenttypen 6); bisher angelegte Werte bleiben erhalten.
- **Validierung:** Wert je Liste eindeutig; nur Admin schreibt; Änderungen im Audit-Log mit alt/neu.
- **Tabellen:** `stammdaten_auswahlwert` (+ Historie)
- **Teststatus:** Backend-Test grün für die Musterwerte (`test_auswahllisten_wie_im_entwurf`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F45 Versorger pflegen
- **Ansicht:** 13 Versorger, 12 Neuer Patient („Neu anlegen“)
- **Endpunkte:** `GET/POST /api/versorger/`, `PATCH /api/versorger/{id}/`; Deaktivieren über `aktiv: false`; kein Löschen (405)
- **Response:** mit `ansprechpartner[]` und `patienten_anzahl`
- **Rechte:** Mitarbeiter, Mediziner, Admin (Unklarheit U10)
- **Tabellen:** `stammdaten_versorger` (+ Historie)
- **Teststatus:** Backend-Test grün (`VersorgerUndAnsprechpartner.test_rechte`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F46 Ansprechpartner pflegen
- **Ansicht:** 13 Versorger
- **Endpunkte:** `GET/POST /api/ansprechpartner/?versorger`, `PATCH /api/ansprechpartner/{id}/`;
  `GET /api/ansprechpartner/{id}/patienten/` (betreute Patienten in Betreuung);
  `POST /api/ansprechpartner/{id}/neu-zuordnen/` `{"ziel": id}` → `{"neu_zugeordnet": n}`
- **Felder:** `name`, `zustaendigkeit` („Patienten A–K“), `telefon`, `mobil`, `email`, `notiz`, `aktiv`; `patienten_anzahl`
- **Validierung:** Ziel aktiv, anderer Ansprechpartner desselben Versorgers; abgeschlossene Akten bleiben unverändert; jede
  Neuzuordnung steht im Verlauf der Akte.
- **Tabellen:** `stammdaten_ansprechpartner`, `patienten_patient` (+ Historie), `audit_systemereignis`
- **Teststatus:** Backend-Test grün (`test_patienten_und_neu_zuordnen`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F47 Präparate pflegen
- **Ansicht:** 18 Vorlagen › Präparate
- **Endpunkte:** `GET/POST /api/praeparate/?kategorie&aktiv`, `PATCH /api/praeparate/{id}/`; kein Löschen (405)
- **Felder:** `kategorie`, `name`, `konzentration`, `einheit`, `reihenfolge`, `aktiv`, `anzeige`; nur lesend `in_plaenen`
  (Anzahl der Pläne, in denen das Präparat vorkommt, auch als Vitamin)
- **Musterwerte:** wie im Entwurf (Basislösungen, Glucose 70 %, 8 Aminosäuren, 7 Lipide, Humanalbumin, 3 Spurenelemente,
  5 Vitamine, 2 Katheterblock); bisherige Einträge bleiben.
- **Teststatus:** Backend-Tests grün (`Praeparate.*`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F48 Grenzwerte und Einstellungen
- **Ansicht:** 18 Vorlagen › Grenzwerte
- **Endpunkt:** `GET/PATCH /api/einstellungen/` (lesen alle, ändern Admin)
- **Felder:** Absender; Warnung Gewichtsverlust %, Zeitraum, Plan alt nach Monaten, Kontakt überfällig nach Monaten;
  Min/Max für Energie, Glucose, Aminosäuren, Lipide, Natrium, Kalium, Gewicht, Größe.
- **Validierung:** Minimum < Maximum je Paar; Audit-Log „Grenzwert „Kontakt überfällig“ von 6 auf 12 Monate geändert“.
- **Fehlt:** Grenzen für das Gesamtvolumen (hängt an F39/U2).
- **Teststatus:** Backend-Test grün (`EinstellungenPruefen.test_grenzen_und_rechte`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F49 Briefkopf, Absender und Logo
- **Geplant:** je Absender (Stiftung, gUG) Name, Straße, PLZ, Ort, Telefon, Fax, E-Mail, Internet, Fußzeile; Logo-Upload (PNG/SVG);
  gilt für neue PDFs, freigegebene behalten ihren Briefkopf. Endpunkte `GET/PATCH /api/briefkopf/`, `POST /api/briefkopf/logo/`.
- **Status:** NICHT ABGESCHLOSSEN

### F50 Dokumentvorlagen (WYSIWYG)
- **Geplant:** Vorlagen „Infusionsplan“ und „Patientendatenblatt“ aus Blöcken (Briefkopf, Text, Datenfelder, Tabelle, Unterschrift,
  Fußzeile, Trennlinie, Leerraum, Seitenumbruch); Platzhalter aus fester Liste; Entwurf → Veröffentlichen, je Art eine aktive
  Version; Vorschau mit Testpatient. Endpunkte `GET /api/vorlagen/`, `GET/PUT /api/vorlagen/{art}/entwurf/`,
  `POST /api/vorlagen/{art}/veroeffentlichen/`, `GET /api/vorlagen/{art}/vorschau/?patient=`.
- **Status:** NICHT ABGESCHLOSSEN

### F51 PDF-Erzeugung
- **Geplant:** WeasyPrint im Backend-Image (offline, keine externen Ressourcen), HTML aus Vorlagenblöcken, Wasserzeichen für
  Testpatienten, Ablage im Dokumentenverzeichnis mit SHA-256.
- **Status:** NICHT ABGESCHLOSSEN

---

## H · Benutzer

### F52 Benutzer lesen, anlegen, ändern
- **Ansicht:** 17 Benutzer
- **Endpunkte:** `GET /api/benutzer/?rolle&is_active&ist_test&search`, `POST /api/benutzer/` → 201 mit `einmal_kennwort`,
  `PATCH /api/benutzer/{id}/`
- **Felder:** `username, titel, first_name, last_name, kuerzel, funktion, email, rolle, ist_test`; nur lesend: `is_active,
  nur_historisch, muss_kennwort_aendern, einmal_kennwort_gueltig_bis, gesperrt_am, sperrgrund, fehlversuche, last_login,
  date_joined, anzeigename, zweiter_faktor`
- **Validierung:** nur Admin; Kürzel eindeutig; eigene Admin-Rolle nicht entziehbar; kein Löschen.
- **Tabellen:** `accounts_user`, `audit_systemereignis`
- **Teststatus:** Backend-Tests grün (`test_nur_admin_verwaltet_benutzer`, `test_neuer_benutzer_hat_frist`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F53 Benutzer sperren und entsperren
- **Ansicht:** 17 Benutzer, 20 Audit-Log (Hinweis)
- **Endpunkte:** `POST /api/benutzer/{id}/sperren/`, `POST /api/benutzer/{id}/entsperren/`
- **Logik:** Sperren beendet alle Sitzungen; Entsperren setzt Sperre und Fehlversuchszähler zurück.
- **Validierung:** eigenes Konto nicht sperrbar; historische Benutzer nicht entsperrbar.
- **Teststatus:** Backend-Tests grün (`test_sperre_nach_fehlversuchen`, `Sitzungen.test_sperre_beendet_alle_sitzungen`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F54 Einmal-Kennwort erzeugen
- **Ansicht:** 17 Benutzer
- **Endpunkt:** `POST /api/benutzer/{id}/einmal-kennwort/` → `{"einmal_kennwort", "gueltig_bis"}`
- **Logik:** gültig `EPM_EINMAL_KENNWORT_STUNDEN` (Standard 48 h); Ablauf wird bei der Anmeldung geprüft (F02); alle Sitzungen
  des Benutzers werden beendet.
- **Teststatus:** Backend-Test grün (`test_einmal_kennwort_laeuft_ab`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F55 Zugangsblatt drucken
- **Geplant:** `GET /api/benutzer/{id}/zugangsblatt/` → PDF mit Benutzername, Einmal-Kennwort (nur solange gültig), Anleitung zur Einrichtung.
- **Abhängigkeit:** F51.
- **Status:** NICHT ABGESCHLOSSEN

### F56 2FA zurücksetzen
- **Ansicht:** 17 Benutzer
- **Endpunkt:** `POST /api/benutzer/{id}/2fa-zuruecksetzen/` → `{"einmal_kennwort", "gueltig_bis"}` (löscht Authenticator und
  Notfall-Codes, beendet alle Sitzungen)
- **Teststatus:** kein automatischer Test.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F57 Testdaten zurücksetzen
- **Ansicht:** 17 Benutzer
- **Endpunkt:** `POST /api/testdaten/zuruecksetzen/` → `{"geloescht", "angelegt"}`; nur Admin; im Wartungsmodus der Trigger
- **Musterdaten:** 6 Testpatienten mit Plänen wie im Entwurf (Sterofundin, Glucose 70 %, Glamin, Clinoleic, Elektrolyte,
  Addel N, Soluvit N + Vitalipid adult, Taurolin 2 %), Termin in der „Praxis Dr. Holtmeier“, ein Altdokument „Typ prüfen“.
- **Teststatus:** Backend-Test grün (`Musterdaten.test_anlegen_und_zuruecksetzen`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

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
- **Validierung:** nur Admin; unbekannte Gruppe → 400.
- **Fehlt:** Gerätename („Praxis-PC 1“) – Unklarheit U8; angezeigt werden Browser und Adresse.
- **Teststatus:** Backend-Tests grün (`test_sperre_nach_fehlversuchen`, `test_abschliessen_nur_mediziner`,
  `test_grenzen_und_rechte`). Frontend fehlt (noch kein React-Code), daher nicht ABGESCHLOSSEN UND GETESTET.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F59 Audit-Log als PDF
- **Geplant:** `GET /api/protokoll/pdf/?von&bis` → PDF; Export wird protokolliert. Abhängigkeit F51.
- **Status:** NICHT ABGESCHLOSSEN

### F60 Unveränderlichkeit
- **Umsetzung:** PostgreSQL-Trigger (`audit/schutz.py`) auf allen Historientabellen und `audit_systemereignis` (kein UPDATE,
  DELETE, TRUNCATE), auf `patienten_kontakt` (nur einmaliges Storno), auf `infusionen_infusionsplan` (nach Freigabe nur
  „aktuell → abgelöst“), auf `infusionen_infusionsplan_vitamine` (Zuordnung nur im Entwurf). Ausnahme nur im Wartungsmodus.
- **Teststatus:** Backend-Tests grün (`test_historie_ist_unveraenderlich`, `test_trigger_verhindert_aenderung_in_der_datenbank`,
  `test_vitamine_freigegebener_plaene_in_der_datenbank_geschuetzt`).
- **Status:** TEILWEISE ABGESCHLOSSEN (Anzeige über Verlauf/Audit-Log im Frontend fehlt)

---

## J · Backup und Wiederherstellung

### F61 Tägliche verschlüsselte Sicherung
- **Ist:** `/usr/local/sbin/epm-backup` + systemd-Timer 02:30: `pg_dump` und Dokumente als `.tar.gz`, SHA-256, 14 Tage.
- **Fehlt:** Uhrzeit 02:00, Verschlüsselung mit `age`, Status-Datei für das Backend.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F62 Sicherungen anzeigen, „Jetzt sichern“
- **Geplant:** `GET /api/backup/` → `{"letzte": {...}, "uebertragung": {...}, "speicher": {"belegt", "gesamt"}, "sicherungen": [{zeitpunkt, art, groesse, verschluesselt, uebertragen}]}`;
  `POST /api/backup/jetzt/`. Der Container bekommt keinen Zugriff auf den Host: Auftrag und Status laufen über ein gemeinsames
  Verzeichnis, ausgeführt von einem systemd-Dienst auf dem Server.
- **Status:** NICHT ABGESCHLOSSEN

### F63 Wiederherstellen
- **Geplant:** `POST /api/backup/{id}/wiederherstellen/` `{"kennwort", "code"}`; vorher automatische Sicherung des aktuellen Stands;
  Protokoll im Audit-Log.
- **Status:** NICHT ABGESCHLOSSEN

### F64 Übertragung zur Nextcloud/NAS
- **Offen:** Schiebt der Server per rsync im Zeitfenster, oder holt die Gegenseite ab? Davon hängt der Status „übertragen …“ ab.
- **Status:** BLOCKIERT DURCH FEHLENDE INFORMATION

---

## K · Migration

### F65 Import der Altdaten
- **Geplant:** Befehl `manage.py epm_import_alt` nach den 17 Regeln der Datenanalyse, Importprotokoll, Zählungen alt gegen neu.
- **Abhängigkeit:** frischer `mysqldump` (die Tabellen `gewichte`/`kontakte` im alten Dump haben kein `lastchange`).
- **Status:** NICHT ABGESCHLOSSEN

---

## Offene Backend-Funktionen

Erledigt in Runde 1 (01.10.2026): O-00 Migrationen im Repo (CI), O-02 Abschluss nur Mediziner, O-03 dauerhafte Sperre,
O-04 Frist Einmal-Kennwort, O-05 Sicherheitsstatus und Sitzungen, O-06 Darstellung/Startseite prüfen, O-07 Startseite
(ohne Backup-Status), O-08 Patientenliste, O-09 Neuer Patient, O-10 Versionen, O-11 Verlauf nach Bereichen, O-12 Kontakt
mit Wiedervorlage, O-13 Terminorte, O-14 Plan mit Elektrolyten/Spurenelementen/Vitaminen/Grenzen (ohne Gesamtvolumen),
O-15 Leer/Vorlage, O-16 Planvergleich, O-18 Altdokumente und Dateityp, O-19 Ansprechpartner, O-20 Präparate, O-21
Einstellungen (ohne Gesamtvolumen), O-22 Audit-Log (ohne Gerätename). Alle mit Backend-Tests gegen PostgreSQL.

| Nr. | Was fehlt | Warum | Betroffene Dateien | Abhängigkeiten | Nächster Schritt |
|---|---|---|---|---|---|
| O-01 | Frontend (alle Funktionen) | noch kein React-Code | neu: `frontend/` | API-Verträge in diesem Dokument | Grundgerüst React + shadcn/ui (Base UI), Anmeldung F01–F05 zuerst, Playwright-Tests in CI |
| O-07 | Backup-Status auf der Startseite (F13) | hängt an der Backup-Steuerung | `patienten/api.py` | O-23 | Status-Datei lesen |
| O-14 | Gesamtvolumen im Plan und seine Grenzen (F33, F39, F48) | fachlich offen | `infusionen/models.py`, `stammdaten/models.py` | U2 | nach Klärung Feld oder Berechnung |
| O-17 | PDF-Erzeugung und Vorlagen (F23, F24, F35, F37, F49, F50, F51, F55, F59) | nicht umgesetzt | neu: `vorlagen/`; `backend/Dockerfile` (WeasyPrint) | – | Vorlagenmodell mit Blöcken, Renderer, Freigabe-PDF mit SHA-256 |
| O-22 | Gerätename im Audit-Log (F58) | fachlich offen | `audit/models.py` | U8 | nach Klärung |
| O-23 | Backup 02:00 verschlüsselt, Steuerung aus der Oberfläche (F61–F63) | nicht umgesetzt | `rollout/epm-backup.sh`, `rollout/04-projekt.sh`, neu: `audit/backup.py`, systemd-Dienst | U9 für F64 | `age`-Schlüssel, Auftragsverzeichnis, Status-Datei, Endpunkte |
| O-24 | Serverskripte angleichen | Festlegungen aus „EPM-Server Aufbau“ fehlen | `rollout/01-basis.sh`, `rollout/02-docker.sh` | – | Adressbereiche, `epm.service`, needrestart, Swap |
| O-25 | Import Altdaten (F65) | Rollout-Schritt 7 | neu: `patienten/management/commands/epm_import_alt.py` | frischer Dump | Import mit Protokoll, setzt `typ_geprueft`/`datum_quelle` |
| O-26 | Tests für F05 (Ersetzen im Konto), F06, F41, F56 | noch nicht geschrieben | `accounts/tests.py`, `patienten/tests.py` | – | Tests ergänzen |

## Unklarheiten (nicht eigenmächtig entschieden)

| Nr. | Frage | Betrifft | Zwischenlösung |
|---|---|---|---|
| U1 | Bedeutung und Einheit von Pantozol 0–3 / Tage | F38 | Werte wie im Altsystem |
| U2 | Gesamtvolumen und Laufzeit eingeben oder berechnen? | F39 | – (blockiert) |
| U3 | „geändert“-Hinweis an einem Kontakt im Entwurf widerspricht „unveränderlich“ | F26 | Beschluss gilt |
| U4 | Plan-Hinweis „6 Monate“ in der Liste vs. 12 Monate in den Grenzwerten | F14 | Grenzwert gilt (Text nennt die eingestellten Monate) |
| U5 | Felder Krankenkasse, Telefon 2, Bemerkung (nicht im Entwurf) | F16 | bleiben gespeichert, nicht angezeigt |
| U6 | Kontaktart (nicht im Entwurf) | F26 | bleibt gespeichert, nicht angezeigt |
| U7 | Rolle des Testbenutzers: Mitarbeiter (Entwurf) oder Mediziner (Code) | F57 | Mediziner |
| U8 | Gerätename im Audit-Log oder nur IP/Browser | F58 | IP und Browser |
| U9 | Übertragung zur Nextcloud: Server schiebt oder Gegenseite holt ab | F64 | blockiert |
| U10 | Wer pflegt Versorger und Ansprechpartner? Rollenmatrix: nur Admin pflegt Vorlagen; Entwurf 12 hat „Neu anlegen“ beim Versorger im Formular „Neuer Patient“ (Mitarbeiter) | F45, F46 | Mitarbeiter, Mediziner und Admin |
| U11 | Ab welcher Änderung zeigt der Trend-Pfeil „gleich“? | F14 | weniger als ±1 % = gleich |
