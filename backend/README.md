# EPM Backend

Django 5.2 LTS · Django REST Framework · PostgreSQL 18 · django-otp (TOTP + Notfall-Codes) · django-simple-history

## Apps
| App | Inhalt |
|---|---|
| `accounts` | Benutzer (Titel, Kürzel, Rolle, Testbenutzer), Anmeldung mit Einmal-Kennwort, 2FA freiwillig oder Pflicht (`Anmelderegeln`), Konten ohne Login (Rolle „Keine Berechtigung“) |
| `stammdaten` | Auswahllisten (Katheter, Dokumenttyp, Kontaktart), Versorger + Ansprechpartner, Präparate, Einstellungen |
| `patienten` | Patient, Gewichtsmessung, Kontakt (unveränderlich, Storno), Termin, Dokument (Dateisystem + SHA-256) |
| `infusionen` | Infusionsplan (Entwurf → aktuell → abgelöst, Vorgänger, kcal), Positionen |
| `audit` | Systemprotokoll, DB-Trigger (Historie/Protokoll unveränderlich), Wartungsmodus |

## API (alle unter `/api/`, Sitzung + CSRF, voll angemeldet = Kennwort + 2FA, sofern eingerichtet oder Pflicht)
- `auth/status` · `auth/anmelden` · `auth/2fa` · `auth/kennwort` · `auth/2fa/einrichten` · `auth/2fa/bestaetigen` · `auth/abmelden` · `auth/ich` · `auth/notfallcodes`
- `startseite/` – Termine (überfällig/heute/7 Tage), Gewichtswarnungen, Planhinweise, zuletzt eingetragen
- `patienten/` (+ `doppelte/`, `{id}/abschliessen/`, `{id}/wieder-oeffnen/`, `{id}/verlauf/`), Filter `suche`, `status`, `versorger` …
- `gewichte/`, `kontakte/` (+ `{id}/storno/`), `termine/` (+ `{id}/erledigt/`), `dokumente/` (+ `{id}/datei/`)
- `infusionsplaene/` (+ `entwurf/`, `{id}/freigeben/`)
- `versorger/`, `ansprechpartner/`, `praeparate/`, `auswahlwerte/`, `einstellungen/`
- Admin: `benutzer/` (+ `sperren`, `entsperren`, `einmal-kennwort`, `2fa-zuruecksetzen`), `protokoll/`, `testdaten/zuruecksetzen/`

## Befehle (im Container: `sudo docker compose exec backend python manage.py …`)
- `epm_musterdaten [--nur-stammdaten] [--zuruecksetzen]`
- `epm_admin_anlegen <name> --vorname … --nachname …` · `epm_zugang_einrichten <name>` (Kennwort + QR im Terminal)
- `epm_trigger` (Schutz-Trigger neu setzen; läuft sonst automatisch nach `migrate`)
- Tests: `sudo docker compose run --rm backend python manage.py test`

## Noch offen (spätere Schritte)
Dokumentvorlagen + PDF (WeasyPrint), Backup/Restore aus der Oberfläche, Import der Altdaten (Schritt 7).
