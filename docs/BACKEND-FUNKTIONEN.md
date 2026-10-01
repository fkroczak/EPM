# EPM – Nachweis der Backend-Funktionen

Stand: 01.10.2026 · Code-Stand: Commit `d0c3abd` (Backend 0.1) · Grundlage: Altsystem-Datenanalyse mit Entscheidungen,
Entwurf „EPM Oberfläche“ (23 Ansichten), „EPM-Server Aufbau“.

## Statuswerte

| Status | Bedeutung |
|---|---|
| ABGESCHLOSSEN UND GETESTET | über das bestehende Frontend mit echtem Backend und echter Datenbank getestet |
| TEILWEISE ABGESCHLOSSEN | Backend-Teil ganz oder zum Teil vorhanden, Frontend-Anbindung und/oder Teile der Logik fehlen |
| NICHT ABGESCHLOSSEN | beschlossen, aber noch nicht umgesetzt |
| BLOCKIERT DURCH FEHLENDE INFORMATION | Umsetzung hängt an einer offenen fachlichen Frage |

**Keine Funktion ist derzeit ABGESCHLOSSEN UND GETESTET**, weil es noch keinen React-Code gibt. Die Oberfläche liegt nur
als klickbarer Entwurf vor.

Teststatus-Angaben beziehen sich auf die automatischen Tests in `backend/patienten/tests.py`, die auf der Test-VM gegen
PostgreSQL 18 gelaufen sind (01.10.2026: 20 von 21 grün; der eine Fehler lag im Test und ist korrigiert, der erneute
Lauf steht aus).

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
| F10 | Sicherheitsstatus im Konto | 14 Mein Konto | NICHT ABGESCHLOSSEN |
| F11 | Angemeldete Sitzungen anzeigen und abmelden | 14 Mein Konto | NICHT ABGESCHLOSSEN |
| F12 | Automatische Abmeldung nach 30 Minuten | alle | TEILWEISE ABGESCHLOSSEN |
| F13 | Startseite | 2 Start | TEILWEISE ABGESCHLOSSEN |
| F14 | Patientenliste mit Filtern und Suche | 3 Patientenliste | TEILWEISE ABGESCHLOSSEN |
| F15 | Doppelprüfung beim Anlegen | 12 Neuer Patient | TEILWEISE ABGESCHLOSSEN |
| F16 | Patient anlegen | 12 Neuer Patient | TEILWEISE ABGESCHLOSSEN |
| F17 | Akte lesen mit Patientenkopf | 4 Patientenakte | TEILWEISE ABGESCHLOSSEN |
| F18 | Stammdaten, Diagnose, Therapie, Empfehlung ändern | 4 Akte, 5 Diagnose und Therapie | TEILWEISE ABGESCHLOSSEN |
| F19 | Versionen je Textfeld | 5 Diagnose und Therapie | NICHT ABGESCHLOSSEN |
| F20 | Akte abschließen | 4 Akte (Menü ⋯) | TEILWEISE ABGESCHLOSSEN |
| F21 | Akte wieder öffnen | 3 Liste (Abgeschlossen) | TEILWEISE ABGESCHLOSSEN |
| F22 | Verlauf je Akte | 10 Verlauf | TEILWEISE ABGESCHLOSSEN |
| F23 | Akte als PDF | 3 Liste, 4 Akte | NICHT ABGESCHLOSSEN |
| F24 | Verlauf als PDF | 10 Verlauf | NICHT ABGESCHLOSSEN |
| F25 | Gewicht erfassen, korrigieren, lesen | 4 Akte | TEILWEISE ABGESCHLOSSEN |
| F26 | Kontakte anlegen, lesen, durchsuchen | 6 Kontakte | TEILWEISE ABGESCHLOSSEN |
| F27 | Kontakt stornieren | 6 Kontakte | TEILWEISE ABGESCHLOSSEN |
| F28 | Kontakt mit Wiedervorlage in einem Schritt | 6 Kontakte | NICHT ABGESCHLOSSEN |
| F29 | Termine anlegen, ändern, lesen | 2 Start, 4 Akte | TEILWEISE ABGESCHLOSSEN |
| F30 | Termin als erledigt markieren | 2 Start | TEILWEISE ABGESCHLOSSEN |
| F31 | Infusionspläne eines Patienten lesen | 8 Infusionspläne | TEILWEISE ABGESCHLOSSEN |
| F32 | Neuer Plan als Entwurf | 7 Neuer Infusionsplan | TEILWEISE ABGESCHLOSSEN |
| F33 | Entwurf bearbeiten | 7 Neuer Infusionsplan | TEILWEISE ABGESCHLOSSEN |
| F34 | Entwurf verwerfen | 8 Infusionspläne | TEILWEISE ABGESCHLOSSEN |
| F35 | Plan freigeben | 8 Infusionspläne | TEILWEISE ABGESCHLOSSEN |
| F36 | Vergleich mit dem Vorgänger | 8 Infusionspläne | NICHT ABGESCHLOSSEN |
| F37 | Gespeicherte Plan-PDF öffnen mit SHA-256-Prüfung | 8 Infusionspläne | NICHT ABGESCHLOSSEN |
| F38 | Pantozol im Plan | 7, 8 | BLOCKIERT DURCH FEHLENDE INFORMATION |
| F39 | Gesamtvolumen, Laufzeit und Rate | 7, 8 | BLOCKIERT DURCH FEHLENDE INFORMATION |
| F40 | Dokument hochladen | 9 Dokumente | TEILWEISE ABGESCHLOSSEN |
| F41 | Dokumente lesen, Metadaten ändern, ausblenden | 9 Dokumente | TEILWEISE ABGESCHLOSSEN |
| F42 | Datei anzeigen und herunterladen | 9 Dokumente | TEILWEISE ABGESCHLOSSEN |
| F43 | Altdokumente prüfen (Typ, Datumsquelle) | 9 Dokumente, 2 Start | NICHT ABGESCHLOSSEN |
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

Summe (65 Funktionen): 0 abgeschlossen und getestet · 45 teilweise abgeschlossen · 17 nicht abgeschlossen · 3 blockiert.

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
| Benutzer, Vorlagen, Backup | – | – | – | ✓ |

- Migrationen: `accounts`, `stammdaten`, `patienten`, `infusionen`, `audit` je `0001_initial` – **auf der Test-VM erzeugt,
  noch nicht im Repo** (siehe Offene Backend-Funktionen, O-00). Schutz-Trigger werden nach jedem `migrate` gesetzt
  (`audit/schutz.py`).

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
- **Endpunkt:** `POST /api/auth/anmelden/`
- **Request:** `{"benutzername": string, "kennwort": string}`
- **Response 200:** wie F01.
- **Validierung:** beide Felder Pflicht; Konto aktiv; nicht „nur historisch“.
- **Tabellen:** `accounts_user`, `django_session`, `audit_systemereignis`
- **Fehlerfälle:** 400 leer · 401 falsch (Fehlversuch wird protokolliert) · 429 gesperrt · 403 fehlendes CSRF-Token
- **Testschritte:** richtige Daten → nächster Schritt; falsches Kennwort → 401 und Eintrag `anmeldung_fehlgeschlagen`.
- **Teststatus:** Backend-Test grün (`test_erstanmeldung`, `test_sperre_nach_fehlversuchen`). Frontend fehlt.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F03 Zweiter Faktor bei der Anmeldung
- **Zweck:** Anmeldung mit 6-stelligem Code aus der Authenticator-App oder einem Notfall-Code abschließen.
- **Endpunkt:** `POST /api/auth/2fa/`
- **Request:** `{"code": string}` (Leerzeichen erlaubt)
- **Response 200:** wie F01 mit `schritt: "fertig"`.
- **Validierung:** Code passt zu einem bestätigten TOTP-Gerät oder zu einem unverbrauchten Notfall-Code (wird verbraucht).
- **Tabellen:** `otp_totp_totpdevice`, `otp_static_staticdevice`, `otp_static_statictoken`, `audit_systemereignis`
- **Fehlerfälle:** 401 nicht mit Kennwort angemeldet oder Code falsch · 429 zu viele Fehlversuche
- **Testschritte:** Anmeldung mit Kennwort, dann Notfall-Code → `fertig`; derselbe Notfall-Code ein zweites Mal → 401.
- **Teststatus:** Backend-Test grün für Notfall-Code (`test_erstanmeldung`); TOTP-Code nur bei der Einrichtung getestet.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F04 Eigenes Kennwort setzen und ändern
- **Zweck:** Einmal-Kennwort beim ersten Login ersetzen; später Kennwort im Konto ändern.
- **Endpunkt:** `POST /api/auth/kennwort/`
- **Request:** Erstanmeldung `{"neu": string}`; sonst `{"alt": string, "neu": string}`
- **Response 200:** wie F01.
- **Validierung:** mind. 12 Zeichen, nicht ähnlich zum Benutzernamen, nicht häufig, nicht nur Ziffern, ungleich dem bisherigen;
  außerhalb der Erstanmeldung nur voll angemeldet und mit richtigem alten Kennwort.
- **Tabellen:** `accounts_user`, `audit_systemereignis`
- **Fehlerfälle:** 400 zu schwach `{"fehler", "details": [...]}` · 400 altes Kennwort falsch · 401 nicht angemeldet · 403 ohne 2FA
- **Testschritte:** Erstanmeldung → Kennwort setzen → `2fa_einrichten`.
- **Teststatus:** Backend-Test grün für die Erstanmeldung; Änderung im Konto ohne Test.
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
- **Endpunkt:** `POST /api/auth/abmelden/` → `{"schritt": "anmelden"}`
- **Tabellen:** `django_session`, `audit_systemereignis`
- **Teststatus:** im Test `test_erstanmeldung` benutzt, Ergebnis nicht einzeln geprüft.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F08 Konto sperren nach 5 Fehlversuchen
- **Zweck:** Schutz gegen Raten. **Beschluss (Entwurf 17, 20):** Konto bleibt gesperrt, bis der Admin entsperrt; Audit-Log
  zeigt „5 falsche Passwörter in 4 Minuten, Konto gesperrt“ und einen Hinweis mit Link zum Benutzer.
- **Endpunkte:** wirkt in F02/F03; Entsperren über F53.
- **Ist-Stand im Code:** 15 Minuten Wartezeit (`accounts/api.py`, `zu_viele_fehlversuche`), keine dauerhafte Sperre.
- **Tabellen:** `accounts_user` (neu: `gesperrt_am`, `sperrgrund`), `audit_systemereignis`
- **Fehlerfälle:** 429 bzw. künftig 403 „Konto gesperrt“
- **Testschritte:** 5 × falsch → Konto gesperrt; richtiges Kennwort → abgewiesen; Admin entsperrt → Anmeldung klappt.
- **Teststatus:** Backend-Test grün für die bisherige 15-Minuten-Sperre; dauerhafte Sperre nicht umgesetzt.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F09 Eigenes Profil, Darstellung und Startseite speichern
- **Endpunkt:** `GET /api/auth/ich/` → `Ich`; `PATCH /api/auth/ich/` `{"darstellung"?: object, "startseite"?: object}`
- **Validierung:** heute nur „muss ein Objekt sein“. **Fehlt:** Schema für Darstellung (Schema standard/individuell/kontrast/dunkel,
  Akzent aus 7 Farben oder eigene, Hintergrund aus 6 Tönen oder eigene, Kontrast ≥ 4,5:1, Dichte, Schriftgröße, Schriftstärke,
  automatisch dunkel) und Startseite (Karten `termine, gewicht, plaene, pruefen, aktiv` mit Sichtbarkeit und Reihenfolge).
- **Tabellen:** `accounts_user` (`darstellung`, `startseite`)
- **Fehlerfälle:** 400 kein Objekt
- **Teststatus:** kein automatischer Test.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F10 Sicherheitsstatus im Konto
- **Zweck:** „Passwort zuletzt geändert“, „Authenticator eingerichtet am“, „8 von 10 Notfall-Codes übrig“.
- **Endpunkt (geplant):** `GET /api/auth/sicherheit/` → `{"kennwort_geaendert_am", "authenticator_eingerichtet_am", "notfallcodes_uebrig"}`
- **Tabellen:** `accounts_user` (neu: `kennwort_geaendert_am`), `otp_totp_totpdevice` (neu über Protokoll oder Feld), `otp_static_statictoken`
- **Status:** NICHT ABGESCHLOSSEN

### F11 Angemeldete Sitzungen anzeigen und abmelden
- **Zweck:** Liste „Dieser PC · Firefox jetzt“, „Praxis-PC 2 · Edge, zuletzt …“, einzeln abmelden.
- **Endpunkte (geplant):** `GET /api/auth/sitzungen/` → `[{"id", "geraet", "browser", "ip", "zuletzt", "diese": bool}]`;
  `DELETE /api/auth/sitzungen/{id}/`
- **Tabellen (neu):** `accounts_sitzung` (Benutzer, Sitzungsschlüssel, Browser, IP, angemeldet, zuletzt aktiv)
- **Status:** NICHT ABGESCHLOSSEN

### F12 Automatische Abmeldung nach 30 Minuten
- **Umsetzung:** `SESSION_COOKIE_AGE` = 30 min, bei jeder Anfrage verlängert (`EPM_SITZUNG_MINUTEN`).
- **Teststatus:** nicht automatisch getestet.
- **Status:** TEILWEISE ABGESCHLOSSEN (Frontend muss auf 403 mit Wechsel zur Anmeldung reagieren)

---

## B · Startseite

### F13 Startseite
- **Endpunkt:** `GET /api/startseite/`
- **Response 200 (Ist):** `{"termine": {"ueberfaellig", "heute", "naechste_7_tage": [Termin]}, "gewichtswarnungen": [{patient, name,
  nummer, prozent, von, bis, tage, warnung}], "infusionsplaene": {"entwuerfe", "aelter_als_grenze": [{id, patient, name,
  gueltig_ab, status}]}, "zuletzt_eingetragen": [{patient, name, zeitpunkt, person, text}], "zahlen": {...}}`
- **Fehlt (Entwurf 2):** „Nach und nach prüfen“ (Altdokumente Typ prüfen, Nickelallergie nicht erfasst, kein Versorger,
  kein Kontakt seit X Monaten – mit Anzahl und Link), „Zuletzt eingetragen“ über alle Bereiche (Plan, Kontakt, Gewicht,
  Dokument), Backup-Status für die Kopfzeile.
- **Validierung:** Testbenutzer sieht nur Testpatienten; Testpatienten fehlen in den Zahlen.
- **Tabellen:** `patienten_*`, `infusionen_infusionsplan`, `stammdaten_einstellungen`
- **Teststatus:** im Test `Musterdaten.test_anlegen_und_zuruecksetzen` geprüft – auf der VM rot wegen eines Testfehlers
  (korrigiert, erneuter Lauf steht aus).
- **Status:** TEILWEISE ABGESCHLOSSEN

---

## C · Patienten und Akte

### F14 Patientenliste mit Filtern und Suche
- **Endpunkt:** `GET /api/patienten/`
- **Query:** `status=in_betreuung|abgeschlossen`, `versorger`, `ansprechpartner`, `katheter`, `nickelallergie`,
  `suche` (Wörter; Ziffern = Nummer, sonst Name/Ort), `test=nur|ohne`, `ordering=nachname|nummer|geburtsdatum|geaendert_am`
- **Response 200:** Seite mit `[{id, nummer, nachname, vorname, geburtsdatum, ort, versorger, versorger_name, ansprechpartner,
  ansprechpartner_name, ist_abgeschlossen, abschluss_anlass, ist_test}]`
- **Fehlt (Entwurf 3):** Zähler „In Betreuung / Abgeschlossen“, Schnellfilter „Nur mit Hinweisen“, „Gewichtsverlust“,
  „Termin diese Woche“ mit Anzahl, Spalten Gewicht + Trend, Letzter Kontakt, Hinweise, Nickelallergie, Katheter;
  Sortierung nach letztem Kontakt; Suche nach Geburtsdatum.
- **Tabellen:** `patienten_patient`, `patienten_gewichtsmessung`, `patienten_kontakt`, `patienten_termin`
- **Teststatus:** Bereich des Testbenutzers getestet (`test_testbenutzer_sieht_nur_testpatienten`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F15 Doppelprüfung beim Anlegen
- **Endpunkt:** `GET /api/patienten/doppelte/?geburtsdatum=JJJJ-MM-TT&nachname=&vorname=` → bis zu 10 Einträge wie F14
- **Regel:** gleiches Geburtsdatum und Nach- oder Vorname beginnt mit denselben 3 Buchstaben.
- **Teststatus:** Backend-Test grün (`test_doppelte`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F16 Patient anlegen
- **Endpunkt:** `POST /api/patienten/`
- **Request:** Pflicht `nachname`, `vorname`, `geburtsdatum`; optional `geschlecht (w|m|d|"")`, `strasse`, `plz`, `ort`, `telefon`,
  `email`, `hausarzt`, `groesse_cm`, `katheter`, `versorger`, `ansprechpartner`, `nickelallergie (ja|nein|unbekannt)`,
  `diagnose` (formatiert). Im Code zusätzlich `telefon2`, `krankenkasse`, `bemerkung` (siehe Unklarheit U5).
- **Response 201:** Akte wie F17; `nummer` automatisch fortlaufend, Testpatienten ab 9001.
- **Validierung:** Geburtsdatum nicht in der Zukunft; Größe in den Grenzen der Einstellungen; Ansprechpartner gehört zum
  Versorger; Katheter aus Liste „Katheter“.
- **Fehlt (Entwurf 12):** „Gewicht bei Aufnahme“ + „gemessen am“ (legt eine Gewichtsmessung an), „Überweisung /
  Kontaktaufnahme durch“, Anzeige der nächsten Nummer vorab.
- **Tabellen:** `patienten_patient`, `patienten_historicalpatient`
- **Fehlerfälle:** 400 Pflichtfeld/Plausibilität · 403 Rolle Betrachter oder Admin
- **Teststatus:** Backend-Test grün (`test_schreibrechte`, `test_nummern`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F17 Akte lesen mit Patientenkopf
- **Endpunkt:** `GET /api/patienten/{id}/`
- **Response 200:** alle Felder aus F16 plus `abgeschlossen_am`, `abschluss_anlass`, `abschluss_notiz`, `ist_abgeschlossen`,
  `ist_test`, `angelegt_am`, `angelegt_von_name`, `geaendert_am`, `kopf: {gewicht {kg, am}, gewichtstrend {prozent, von, bis,
  tage, warnung}, bmi, katheter, versorger, ansprechpartner, nickelallergie, aktueller_plan {id, gueltig_ab, kcal},
  naechster_termin {...}, zaehler {kontakte, gewichte, dokumente, termine_offen, infusionsplaene}}`
- **Fehlt:** Telefon des Ansprechpartners, Laufzeit des aktuellen Plans im Kopf.
- **Fehlerfälle:** 404 unbekannt oder außerhalb des Bereichs
- **Teststatus:** indirekt getestet (Akte-Tests).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F18 Stammdaten, Diagnose, Therapie, Empfehlung ändern
- **Endpunkt:** `PATCH /api/patienten/{id}/`
- **Validierung:** wie F16; Texte werden auf erlaubte Formatierung bereinigt (`epm/sanitize.py`); Akte darf nicht abgeschlossen sein.
- **Tabellen:** `patienten_patient`, `patienten_historicalpatient`
- **Fehlerfälle:** 400 · 403 Rolle · 409 Akte abgeschlossen
- **Teststatus:** Backend-Test grün (`test_verlauf_zeigt_person_und_aenderung`, `test_abgeschlossene_akte_ist_gesperrt`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F19 Versionen je Textfeld
- **Zweck:** „Version 12 · geändert 12.08.2026, 15:12 von Dr. M. Berger · Versionen“ für Diagnose, Empfehlung, Therapie.
- **Endpunkt (geplant):** `GET /api/patienten/{id}/versionen/?feld=diagnose|therapie|empfehlung` →
  `{"version": n, "geaendert_am", "geaendert_von", "fassungen": [{"version", "zeitpunkt", "person", "text"}]}`;
  Kopfangaben zusätzlich in F17 (`versionen: {diagnose: {version, am, von}, ...}`).
- **Tabellen:** `patienten_historicalpatient` (vorhanden)
- **Status:** NICHT ABGESCHLOSSEN

### F20 Akte abschließen
- **Endpunkt:** `POST /api/patienten/{id}/abschliessen/` `{"anlass": "verstorben"|"therapie_beendet"|"betreuung_gewechselt",
  "datum"?: Datum, "notiz"?: string}` → Akte wie F17
- **Validierung:** Anlass Pflicht; Akte noch offen. **Recht laut Rollenmatrix: nur Mediziner** – der Code erlaubt es auch
  Mitarbeitern (Korrektur K1).
- **Tabellen:** `patienten_patient`, `audit_systemereignis`
- **Fehlerfälle:** 400 Anlass · 403 Rolle · 409 bereits abgeschlossen
- **Teststatus:** Backend-Test grün (mit der falschen Rolle Mitarbeiter).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F21 Akte wieder öffnen
- **Endpunkt:** `POST /api/patienten/{id}/wieder-oeffnen/` `{"grund": string}` → Akte
- **Validierung:** nur Admin; Grund Pflicht; Akte muss abgeschlossen sein. Grund steht in der Historie.
- **Fehlerfälle:** 400 · 403
- **Teststatus:** Backend-Test grün.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F22 Verlauf je Akte
- **Endpunkt:** `GET /api/patienten/{id}/verlauf/?bereich=stammdaten|gewichte|kontakte|termine|dokumente|infusionsplaene&person=<id>`
  → `[{bereich, objekt_id, art (angelegt|geändert|gelöscht), zeitpunkt, person, person_id, grund, aenderungen: [{feld, alt, neu}]}]`
- **Fehlt (Entwurf 10):** Bereiche „Diagnose“ und „Therapie“ getrennt von „Stammdaten“; Aktionen wie „storniert“, „freigegeben“,
  „hochgeladen“ als eigene Bezeichnung.
- **Tabellen:** alle `*_historical*`
- **Teststatus:** Backend-Test grün (`test_verlauf_zeigt_person_und_aenderung`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F23 Akte als PDF / F24 Verlauf als PDF
- **Endpunkte (geplant):** `GET /api/patienten/{id}/pdf/`, `GET /api/patienten/{id}/verlauf/pdf/` → `application/pdf`; Export
  wird im Audit-Log protokolliert (Art `export`).
- **Abhängigkeit:** F51 PDF-Erzeugung, F50 Vorlage „Patientendatenblatt“.
- **Status:** NICHT ABGESCHLOSSEN (beide)

---

## D · Gewicht, Kontakte, Termine

### F25 Gewicht erfassen, korrigieren, lesen
- **Endpunkte:** `GET /api/gewichte/?patient=<id>`, `POST /api/gewichte/`, `PATCH /api/gewichte/{id}/`
- **Request:** `{"patient", "gewicht_kg", "gemessen_am"?, "datum_ungenau"?, "quelle": "telefonisch"|"ambulanz"|"versorger"|"arztbrief"|"altsystem", "notiz"?}`
- **Response:** `{id, patient, gewicht_kg, gemessen_am, datum_ungenau, quelle, notiz, erfasst_am, erfasst_von_name}`
- **Validierung:** Gewicht in den Grenzen der Einstellungen (Standard 20–250 kg); Datum nicht in der Zukunft; Patient im Bereich;
  Akte offen; Patient nicht änderbar.
- **Tabellen:** `patienten_gewichtsmessung`, `patienten_historicalgewichtsmessung`
- **Fehlerfälle:** 400 · 403 · 409
- **Teststatus:** Backend-Test grün (`test_plausibilitaet_gewicht`, `test_gewichtswarnung`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F26 Kontakte anlegen, lesen, durchsuchen
- **Endpunkte:** `GET /api/kontakte/?patient=<id>&search=<text>`, `POST /api/kontakte/`; `PATCH`/`DELETE` → 405
- **Request:** `{"patient", "text" (formatiert, Pflicht), "zeitpunkt"?}` (im Code zusätzlich `art`, Unklarheit U6)
- **Response:** `{id, patient, zeitpunkt, art, art_name, text, erfasst_am, erfasst_von_name, storniert_am, storniert_von_name, storno_grund}`
- **Validierung:** Text bereinigt; Zeitpunkt nicht in der Zukunft; Akte offen. Unveränderlich: Modell + Datenbank-Trigger.
- **Tabellen:** `patienten_kontakt`, `patienten_historicalkontakt`
- **Teststatus:** Backend-Test grün (`KontaktRegeln`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F27 Kontakt stornieren
- **Endpunkt:** `POST /api/kontakte/{id}/storno/` `{"grund": string}` → Kontakt
- **Validierung:** Grund Pflicht; nur einmal; Akte offen. Trigger erlaubt nur die Storno-Felder.
- **Fehlerfälle:** 400 · 403 · 409
- **Teststatus:** Backend-Test grün (`test_storno_genau_einmal`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F28 Kontakt mit Wiedervorlage in einem Schritt
- **Zweck:** Entwurf 6: Kontakt speichern und dabei Rückruf/Wiedervorlage/Praxistermin mit Datum und Uhrzeit anlegen.
- **Endpunkt (geplant):** `POST /api/kontakte/` mit `"wiedervorlage": {"art", "ort"?, "faellig_am", "uhrzeit"?, "titel"?}` –
  beides in einer Transaktion.
- **Tabellen:** `patienten_kontakt`, `patienten_termin`
- **Status:** NICHT ABGESCHLOSSEN

### F29 Termine anlegen, ändern, lesen
- **Endpunkte:** `GET /api/termine/?patient&art&von&bis&offen`, `POST /api/termine/`, `PATCH /api/termine/{id}/`
- **Request:** `{"patient", "art": "praxistermin"|"rueckruf"|"wiedervorlage"|"sonstiges", "faellig_am", "uhrzeit"?, "bei"?, "titel", "notiz"?, "kontakt"?}`
- **Fehlt:** Terminorte als pflegbare Liste statt Freitext `bei` (Entwurf 18: „Terminorte 3“).
- **Validierung:** Kontakt gehört zum Patienten; erledigte Termine nicht änderbar; Akte offen.
- **Tabellen:** `patienten_termin`, `patienten_historicaltermin`
- **Teststatus:** kein eigener Test (nur über Musterdaten/Startseite).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F30 Termin als erledigt markieren
- **Endpunkt:** `POST /api/termine/{id}/erledigt/` → Termin mit `erledigt_am`, `erledigt_von_name`
- **Fehlerfälle:** 400 bereits erledigt · 409 Akte abgeschlossen
- **Teststatus:** kein automatischer Test.
- **Status:** TEILWEISE ABGESCHLOSSEN

---

## E · Infusionspläne

### F31 Infusionspläne eines Patienten lesen
- **Endpunkt:** `GET /api/infusionsplaene/?patient=<id>&status=` → Pläne mit Positionen, `kcal_berechnet`, `kcal`, `geaenderte_felder`
- **Teststatus:** Backend-Test grün (`Infusionsplaene.test_ablauf`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F32 Neuer Plan als Entwurf
- **Endpunkt:** `POST /api/infusionsplaene/entwurf/` `{"patient"}` → 201 Entwurf, vorbelegt mit dem aktuellen Plan
- **Fehlt (Entwurf 7/8):** `"leer": true` („Leer beginnen“) und `"vorlage": <plan-id>` („Als Vorlage für neuen Plan“ aus jedem früheren Plan).
- **Validierung:** nur Mediziner; höchstens ein Entwurf je Patient; Akte offen.
- **Teststatus:** Backend-Test grün.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F33 Entwurf bearbeiten
- **Endpunkt:** `PATCH /api/infusionsplaene/{id}/`
- **Request (Ist):** `basis_praeparat, basis_ml, glucose_praeparat, glucose_g, aminosaeuren_praeparat, aminosaeuren_g, lipide_praeparat,
  lipide_g, albumin_praeparat, albumin_g, kcal_manuell, laufzeit_h, tage_pro_woche, katheterschutz, pantozol_stufe, pantozol_tage,
  bemerkung, positionen[]`
- **Fehlt (Beschluss/Entwurf 7):** feste Felder `natrium_mmol, kalium_mmol, phosphat_mmol, calcium_mmol, magnesium_mmol`,
  `spurenelemente` (ein Präparat), `vitamine` (mehrere Präparate), `gesamtvolumen_ml` (siehe F39); Plausibilitätsgrenzen je Wert.
- **Validierung (Ist):** Präparat passt zur Kategorie; Präparat Pflicht, wenn Menge gesetzt; kcal ≤ Grenze; Pantozol-Regeln.
- **Tabellen:** `infusionen_infusionsplan`, `infusionen_infusionsplanposition`, Historientabellen
- **Fehlerfälle:** 400 · 403 freigegeben oder Rolle · 409
- **Teststatus:** Backend-Test grün für den Ist-Umfang (`test_ablauf`, `test_kcal_manuell_und_grenze`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F34 Entwurf verwerfen
- **Endpunkt:** `DELETE /api/infusionsplaene/{id}/` → 204; nur Entwürfe (Modell + Trigger)
- **Teststatus:** kein automatischer Test.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F35 Plan freigeben
- **Endpunkt:** `POST /api/infusionsplaene/{id}/freigeben/` → Plan mit `status: "aktuell"`; bisheriger aktueller Plan → `abgeloest`
- **Fehlt:** PDF-Erzeugung bei Freigabe mit SHA-256 und Vorlagenversion, Ablage als Dokument „Von EPM erzeugt“ (F51, F50).
- **Validierung:** nur Mediziner; vollständige Prüfung aller Werte; Akte offen.
- **Teststatus:** Backend-Test grün ohne PDF.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F36 Vergleich mit dem Vorgänger
- **Endpunkt (geplant):** `GET /api/infusionsplaene/{id}/vergleich/` → `{"vorgaenger": {id, gueltig_ab}, "zeilen": [{"wert", "vorher", "jetzt", "geaendert"}], "anzahl_geaendert"}`
- **Vorhanden:** `geaenderte_felder` im Plan.
- **Status:** NICHT ABGESCHLOSSEN

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
- **Endpunkt:** `POST /api/dokumente/` (multipart) `patient`, `datei`, `titel`?, `typ`?, `datum`?, `notiz`?
- **Response 201:** `{id, patient, typ, typ_name, titel, datum, notiz, ausgeblendet, originalname, mime, groesse, sha256, herkunft, hochgeladen_am, hochgeladen_von_name}`
- **Validierung:** Datei Pflicht, max. 50 MB; Typ aus Liste „Dokumenttyp“; Akte offen. **Fehlt:** Prüfung auf PDF/JPG/PNG/TXT (Inhalt, nicht nur Endung).
- **Speicherung:** `/data/dokumente/<nummer>/<zufällig>.<endung>`, atomar, SHA-256.
- **Tabellen:** `patienten_dokument`, `patienten_historicaldokument`
- **Teststatus:** Backend-Test grün (`test_dokument_upload_und_download`).
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
- **Zweck:** importierte Dateien tragen „Typ prüfen“ und die Herkunft des Datums (PDF-Metadaten, EXIF, Dateidatum) bis jemand sie bestätigt.
- **Geplant:** Felder `typ_geprueft` (bool), `datum_quelle` (pdf|exif|dateidatum|eingabe); `POST /api/dokumente/{id}/geprueft/`; Zähler auf der Startseite.
- **Status:** NICHT ABGESCHLOSSEN

---

## G · Stammdaten und Vorlagen

### F44 Auswahllisten pflegen
- **Endpunkte:** `GET/POST /api/auswahlwerte/?liste&aktiv`, `PATCH /api/auswahlwerte/{id}/` (kein Löschen)
- **Listen (Ist):** `katheter`, `dokumenttyp`, `kontaktart`. **Fehlt:** `terminort`.
- **Validierung:** Wert je Liste eindeutig; nur Admin schreibt.
- **Tabellen:** `stammdaten_auswahlwert` (+ Historie)
- **Status:** TEILWEISE ABGESCHLOSSEN

### F45 Versorger pflegen
- **Endpunkte:** `GET/POST /api/versorger/`, `PATCH /api/versorger/{id}/`; Deaktivieren über `aktiv: false`
- **Response:** mit `ansprechpartner[]` und `patienten_anzahl`
- **Tabellen:** `stammdaten_versorger` (+ Historie)
- **Status:** TEILWEISE ABGESCHLOSSEN

### F46 Ansprechpartner pflegen
- **Endpunkte:** `GET/POST /api/ansprechpartner/?versorger`, `PATCH /api/ansprechpartner/{id}/`
- **Fehlt:** Feld `zustaendigkeit` („Patienten A–K“); beim Deaktivieren Liste der betroffenen Patienten zum Neuzuordnen.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F47 Präparate pflegen
- **Endpunkte:** `GET/POST /api/praeparate/?kategorie&aktiv`, `PATCH /api/praeparate/{id}/`
- **Fehlt:** Reihenfolge je Kategorie, Anzahl „in Plänen“.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F48 Grenzwerte und Einstellungen
- **Endpunkt:** `GET/PATCH /api/einstellungen/`
- **Ist:** Absender (Umschalter), Gewichtswarnung %, Zeitraum, Plan alt nach Monaten, Grenzen Gewicht/Größe, kcal max.
- **Fehlt:** „Kontakt überfällig nach Monaten“, Min/Max für Energie, Gesamtvolumen, Glucose, Aminosäuren, Lipide, Natrium, Kalium.
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
- **Endpunkte:** `GET /api/benutzer/?rolle&is_active&ist_test&search`, `POST /api/benutzer/` → 201 mit `einmal_kennwort`,
  `PATCH /api/benutzer/{id}/`
- **Felder:** `username, titel, first_name, last_name, kuerzel, funktion, email, rolle, ist_test`; nur lesend: `is_active,
  nur_historisch, muss_kennwort_aendern, last_login, date_joined, anzeigename, zweiter_faktor`
- **Validierung:** nur Admin; Kürzel eindeutig; eigene Admin-Rolle nicht entziehbar; kein Löschen.
- **Tabellen:** `accounts_user`, `audit_systemereignis`
- **Teststatus:** Backend-Test grün für Anlegen (`test_nur_admin_verwaltet_benutzer`).
- **Status:** TEILWEISE ABGESCHLOSSEN

### F53 Benutzer sperren und entsperren
- **Endpunkte:** `POST /api/benutzer/{id}/sperren/`, `POST /api/benutzer/{id}/entsperren/`
- **Validierung:** eigenes Konto nicht sperrbar; historische Benutzer nicht entsperrbar.
- **Teststatus:** kein automatischer Test.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F54 Einmal-Kennwort erzeugen
- **Endpunkt:** `POST /api/benutzer/{id}/einmal-kennwort/` → `{"einmal_kennwort"}`
- **Fehlt:** Gültigkeit (Entwurf: „Gültig bis 01.10.2026, 09:30“), Ablauf wird bei der Anmeldung geprüft.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F55 Zugangsblatt drucken
- **Geplant:** `GET /api/benutzer/{id}/zugangsblatt/` → PDF mit Benutzername, Einmal-Kennwort (nur solange gültig), Anleitung zur Einrichtung.
- **Abhängigkeit:** F51.
- **Status:** NICHT ABGESCHLOSSEN

### F56 2FA zurücksetzen
- **Endpunkt:** `POST /api/benutzer/{id}/2fa-zuruecksetzen/` → `{"einmal_kennwort"}` (löscht Authenticator und Notfall-Codes)
- **Teststatus:** kein automatischer Test.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F57 Testdaten zurücksetzen
- **Endpunkt:** `POST /api/testdaten/zuruecksetzen/` → `{"geloescht", "angelegt"}`; nur Admin; im Wartungsmodus der Trigger
- **Teststatus:** Test korrigiert, erneuter Lauf steht aus.
- **Status:** TEILWEISE ABGESCHLOSSEN

---

## I · Audit und Unveränderlichkeit

### F58 Audit-Log lesen und filtern
- **Endpunkt:** `GET /api/protokoll/?art&benutzer&von&bis&search` → `[{id, zeitpunkt, art, art_name, benutzer, person, benutzername, objekt, details, ip}]`
- **Fehlt (Entwurf 20):** Gruppen-Filter (Anmeldung, Fehlversuch, Benutzer, Vorlage, Backup, Export, Abschluss), Hinweis
  auf gesperrte Konten, Gerät/Browser.
- **Status:** TEILWEISE ABGESCHLOSSEN

### F59 Audit-Log als PDF
- **Geplant:** `GET /api/protokoll/pdf/?von&bis` → PDF; Export wird protokolliert. Abhängigkeit F51.
- **Status:** NICHT ABGESCHLOSSEN

### F60 Unveränderlichkeit
- **Umsetzung:** PostgreSQL-Trigger (`audit/schutz.py`) auf allen Historientabellen und `audit_systemereignis` (kein UPDATE,
  DELETE, TRUNCATE), auf `patienten_kontakt` (nur einmaliges Storno), auf `infusionen_infusionsplan` (nach Freigabe nur
  „aktuell → abgelöst“). Ausnahme nur im Wartungsmodus.
- **Teststatus:** Backend-Test grün (`test_historie_ist_unveraenderlich`, `test_trigger_verhindert_aenderung_in_der_datenbank`).
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

| Nr. | Was fehlt | Warum | Betroffene Dateien | Abhängigkeiten | Nächster Schritt |
|---|---|---|---|---|---|
| O-00 | Migrationen im Repo | nur auf der Test-VM erzeugt; Code konnte in der Entwicklungsumgebung nicht ausgeführt werden | `backend/*/migrations/0001_initial.py` | Datei `migrationen.tar` aus der VM **oder** automatischer Testlauf in GitHub | Dateien ins Repo, `makemigrations --check` in `epm-update` grün |
| O-01 | Frontend (alle Funktionen) | noch kein React-Code | neu: `frontend/` | O-00; API-Verträge in diesem Dokument | Grundgerüst React + shadcn/ui (Base UI), Anmeldung F01–F05 zuerst |
| O-02 | Rolle „Akte abschließen“ nur Mediziner (F20) | Code folgt nicht der Rollenmatrix | `patienten/api.py`, `accounts/permissions.py`, `patienten/tests.py` | – | eigenes Recht `AbschlussRecht`, Test anpassen |
| O-03 | Dauerhafte Kontosperre (F08) | 15-Minuten-Sperre implementiert statt Beschluss | `accounts/models.py`, `accounts/api.py`, Migration `accounts/0002` | O-00 | Felder `gesperrt_am`, `sperrgrund`; Entsperren setzt sie zurück |
| O-04 | Gültigkeit Einmal-Kennwort (F54) | nicht umgesetzt | `accounts/models.py`, `accounts/api.py`, Migration | O-00 | Feld `einmal_kennwort_gueltig_bis`, Prüfung in F02 |
| O-05 | Sicherheitsstatus und Sitzungen (F10, F11) | nicht umgesetzt | `accounts/` (neues Modell `Sitzung`), Migration | O-00 | Modell + Signal bei Anmeldung, Endpunkte |
| O-06 | Darstellung/Startseite prüfen (F09) | nur „Objekt“ geprüft | `accounts/api.py` | – | Serializer mit erlaubten Werten und Kontrastprüfung |
| O-07 | Startseite vollständig (F13) | Teile fehlen | `patienten/api.py` | F43, F62 | „Nach und nach prüfen“, alle Bereiche, Backup-Status |
| O-08 | Patientenliste vollständig (F14) | Spalten, Zähler, Schnellfilter fehlen | `patienten/api.py` | – | Annotationen (letzter Kontakt, letztes Gewicht, Trend, Hinweise), Zähler-Endpunkt |
| O-09 | Neuer Patient vollständig (F16) | Felder fehlen | `patienten/models.py`, `patienten/api.py`, Migration | O-00, U5 | Feld `ueberweisung_durch`, Aufnahmegewicht, `naechste-nummer` |
| O-10 | Versionen je Textfeld (F19) | nicht umgesetzt | `patienten/api.py` | – | Auswertung der Historie je Feld |
| O-11 | Verlauf mit Diagnose/Therapie getrennt (F22) | Bereiche zu grob | `patienten/api.py` | – | Änderungen je Feld in Bereiche aufteilen |
| O-12 | Kontakt mit Wiedervorlage (F28) | nicht umgesetzt | `patienten/api.py` | O-13 | verschachtelter Serializer, eine Transaktion |
| O-13 | Terminorte (F29, F44) | Freitext statt Liste | `stammdaten/models.py`, `patienten/models.py`, Migration | O-00 | Liste `terminort`, Feld `Termin.ort` |
| O-14 | Plan: Elektrolyte, Spurenelemente, Vitamine, Grenzen (F33) | vereinfacht über Positionen | `infusionen/models.py`, `infusionen/api.py`, `stammdaten/models.py`, Migration | O-00, F39 | feste Felder, Grenzwerte in Einstellungen |
| O-15 | Plan leer beginnen / aus Vorlage (F32) | nicht umgesetzt | `infusionen/models.py`, `infusionen/api.py` | – | Parameter `leer`, `vorlage` |
| O-16 | Planvergleich (F36) | nicht umgesetzt | `infusionen/api.py` | O-14 | Endpunkt `vergleich` |
| O-17 | PDF-Erzeugung und Vorlagen (F23, F24, F35, F37, F49, F50, F51, F55, F59) | nicht umgesetzt | neu: `vorlagen/`; `backend/Dockerfile` (WeasyPrint) | O-00 | Vorlagenmodell mit Blöcken, Renderer, Freigabe-PDF |
| O-18 | Altdokumente prüfen, Dateityp prüfen (F40, F43) | nicht umgesetzt | `patienten/models.py`, `patienten/api.py`, Migration | O-00 | Felder, Prüf-Aktion, Inhaltsprüfung |
| O-19 | Ansprechpartner Zuständigkeit, Neuzuordnung (F46) | nicht umgesetzt | `stammdaten/models.py`, `stammdaten/api.py`, Migration | O-00 | Feld + Endpunkt „betroffene Patienten“ |
| O-20 | Präparate Reihenfolge und Nutzung (F47) | nicht umgesetzt | `stammdaten/models.py`, `stammdaten/api.py` | O-14 | Feld `reihenfolge`, Annotation Nutzung |
| O-21 | Einstellungen vollständig (F48) | Grenzen fehlen | `stammdaten/models.py`, Migration | O-00 | Felder ergänzen |
| O-22 | Audit-Log vollständig (F58) | Gruppen, Hinweis, Gerät | `audit/api.py`, `audit/models.py` | O-05 | Gruppen-Filter, Hinweis-Endpunkt |
| O-23 | Backup 02:00 verschlüsselt, Steuerung aus der Oberfläche (F61–F63) | nicht umgesetzt | `rollout/epm-backup.sh`, `rollout/04-projekt.sh`, neu: `audit/backup.py`, systemd-Dienst | U9 | `age`-Schlüssel, Auftragsverzeichnis, Status-Datei, Endpunkte |
| O-24 | Serverskripte angleichen | Festlegungen aus „EPM-Server Aufbau“ fehlen | `rollout/01-basis.sh`, `rollout/02-docker.sh` | – | Adressbereiche, `epm.service`, needrestart, Swap |
| O-25 | Import Altdaten (F65) | Rollout-Schritt 7 | neu: `patienten/management/commands/epm_import_alt.py` | frischer Dump | Import mit Protokoll |

## Unklarheiten (nicht eigenmächtig entschieden)

| Nr. | Frage | Betrifft | Zwischenlösung |
|---|---|---|---|
| U1 | Bedeutung und Einheit von Pantozol 0–3 / Tage | F38 | Werte wie im Altsystem |
| U2 | Gesamtvolumen und Laufzeit eingeben oder berechnen? | F39 | – (blockiert) |
| U3 | „geändert“-Hinweis an einem Kontakt im Entwurf widerspricht „unveränderlich“ | F26 | Beschluss gilt |
| U4 | Plan-Hinweis „6 Monate“ in der Liste vs. 12 Monate in den Grenzwerten | F14 | Grenzwert gilt |
| U5 | Felder Krankenkasse, Telefon 2, Bemerkung (nicht im Entwurf) | F16 | bleiben gespeichert, nicht angezeigt |
| U6 | Kontaktart (nicht im Entwurf) | F26 | bleibt gespeichert, nicht angezeigt |
| U7 | Rolle des Testbenutzers: Mitarbeiter (Entwurf) oder Mediziner (Code) | F57 | Mediziner |
| U8 | Gerätename im Audit-Log oder nur IP/Browser | F58 | IP und Browser |
| U9 | Übertragung zur Nextcloud: Server schiebt oder Gegenseite holt ab | F64 | blockiert |
