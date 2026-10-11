# EPM – Elektronisches Patienten-Management

| Ordner | Inhalt |
|---|---|
| `backend/` | Django-Backend (siehe `backend/README.md`) |
| `frontend/` | Oberfläche: React, TypeScript, Vite, Tailwind, Base UI (Bausteine im Stil von shadcn/ui), TipTap; Browsertests in `frontend/e2e/` (Playwright) |
| `rollout/` | Server-Einrichtung: `01-basis.sh` … `05-backend.sh`, Compose, Nginx |
| `werkzeuge/` | `epm-update.sh` (Update in einem Schritt), `ci-stack.sh` (kompletter Stack für die Browsertests), `epm-git-einrichten.sh`, `bauen.sh`/`bauen.ps1`, `hilfe-bilder.mjs` (Bilder der Hilfe) |
| `docs/BACKEND-FUNKTIONEN.md` | Nachweis aller Funktionen mit API-Verträgen, Tests und Status |
| `VERSION` | Grundstand der Versionsnummer (X.Y.Z). Die letzte Stelle zählt automatisch je Änderung auf main hoch (`werkzeuge/version.sh`: 2.0.0 + 3 Merges = 2.0.3); neue Funktionen bzw. Hauptversion: VERSION von Hand auf 2.1.0 bzw. 3.0.0 setzen, die Zählung beginnt neu. Die Images heißen `epm-backend:<Version>-<Commit>` und `epm-web:<Version>-<Commit>` |

## Images

- `epm-backend` – Django mit Gunicorn (`backend/Dockerfile`); dasselbe Image läuft als OCR-Dienst (Compose-Dienst `ocr`,
  Menüpunkt „Scans“). Die Texterkennung arbeitet nur auf dem Server: Tesseract mit dem deutschen Modell liegt im Repo,
  die PP-OCRv5-Modelle lädt der Bau von `huggingface.co` (Proxy-Freigabe; ohne Zugang entsteht das Image trotzdem und
  erkennt nur mit Tesseract – Administration › System zeigt es). **Offline nachreichen:** auf einem PC mit Internet
  `werkzeuge/ocr-modelle.sh vorbereiten` (Windows: `werkzeuge\ocr-modelle.ps1`) → Datei per `scp` auf die Test-VM →
  `sudo epm-ocr-modelle einspielen DATEI.tar` → `sudo epm-update` (baut das Image mit den Modellen neu;
  `sudo epm-ocr-modelle status` zeigt den Stand) – oder in EPM unter Administration › System › Software
  „OCR-Modelle einspielen“ (Datei hochladen statt scp) und danach „EPM aktualisieren“
  Auf Servern mit wenig RAM (unter 6 GB) arbeitet die Texterkennung automatisch im Sparmodus (kleines Zeilenmodell,
  ohne Glätten); Speichergrenze und Rechenkerne des OCR-Dienstes trägt `04-projekt.sh` einmalig nach dem Server in
  `/srv/epm/.env` ein (`EPM_OCR_SPEICHER`, `EPM_OCR_THREADS`, Modus erzwingen mit `EPM_OCR_MODUS=voll|sparsam`)
- `epm-web` – Nginx mit dem gebauten Frontend (`frontend/Dockerfile`). Zum Bauen braucht der Server Zugang zu
  `registry.npmjs.org` (Proxy-Freigabe); ohne Zugang die Images mit `werkzeuge/bauen.sh` auf einem anderen Rechner bauen
  und als `epm-<VERSION>.tar` mit `rollout/05-backend.sh` einspielen.

## Server ohne SSH warten (10.10.2026)
Unter **Administration › Systemverwaltung** stehen Zustand (Ampel) und die häufigen Aufgaben; alles Weitere unter
Administration › System (Reiter Wartung, Software, Zertifikat, Protokolle) und › Backup. Updates, Neustart, Dienste,
Zurückschalten, Update-Pakete, OCR-Modelle, Zertifikat, Protokolle und Sicherungen laufen über den Systemagenten –
gefährliche Aktionen mit Passwort und zweitem Faktor, alles im Audit-Log. SSH braucht es nur noch für die
Ersteinrichtung des Servers (`rollout/01…05`, `epm-git-einrichten.sh`, einmalig `epm-zertifikat einrichten`) und wenn
der Systemagent selbst nicht läuft.

Uhrzeit: Zeitzone, Zeitsynchronisation und eigener Zeitserver (ohne Internet z. B. die OPNsense; sonst
`EPM_NTP_SERVER` in `/etc/epm/epm.conf` bei der Ersteinrichtung) unter Administration › System › Wartung › Uhrzeit.

## Test-VM aktualisieren
Oder in EPM unter Administration › System: „EPM aktualisieren“ (Wartung), Versionen und „Zurückschalten“, „Update-Paket
erstellen“ (Software).
```bash
sudo epm-update                # holen, bauen (Backend und Frontend), Backup, starten, Musterdaten, Tests
sudo epm-update --versionen    # vorhandene Versionen
sudo epm-update --zurueck TAG  # zurückschalten (beide Images)
sudo epm-update --paket-erstellen  # Update-Paket der laufenden, getesteten Version für den VPS
```

## VPS ohne Internet (Festlegung 02.10.2026)
Der VPS bekommt keine Verbindung zu GitHub und baut nichts selbst: In `/etc/epm/epm.conf` steht
`EPM_UPDATE_QUELLE="paket"`. Auf der Test-VM erzeugt `sudo epm-update --paket-erstellen` aus der dort laufenden und
getesteten Version eine Datei `epm-paket-<TAG>.tar` (Images, Rollout-Dateien, Systemagent, `epm-update`, Prüfsummen).
```bash
scp /srv/epm/images/epm-paket-<TAG>.tar epmadmin@VPS:~/      # vom PC bzw. der Test-VM
sudo epm-update --paket ~/epm-paket-<TAG>.tar                 # auf dem VPS: prüfen, Backup, umstellen, Tests
```
Oder ohne scp und SSH: auf der Test-VM unter Administration › System › Software „Update-Paket erstellen“ und
herunterladen, auf dem VPS dort „Update-Paket einspielen“ (hochladen, SHA-256 vergleichen, mit Passwort und 2FA
bestätigen).
Die Konfiguration des Servers liegt in `/etc/epm/epm.conf` (nicht im Repo). Die Oberfläche ist danach unter
`https://<EPM_WEB_NAME>/` erreichbar, die Django-Verwaltung unter `/verwaltung/` (nur Rolle Admin).

## Zertifikat und Passkeys
Passkeys (zweiter Faktor mit Fingerabdruck, Gesicht oder PIN) gehen nur über einen Namen mit einem Zertifikat, dem die
Geräte vertrauen – nicht über die IP-Adresse. Dafür gibt es eine eigene CA (nur für den EPM-Namen gültig):
```bash
sudo epm-zertifikat einrichten   # CA + Serverzertifikat für EPM_WEB_NAME, Nginx lädt neu
sudo epm-zertifikat status       # Name, Aussteller, Ablauf (Serverzertifikat 397 Tage: jährlich „erneuern“)
```
Das Stammzertifikat liegt unter `https://<EPM_WEB_NAME>/epm-ca.crt` (für iPhone/iPad als Profil
`/epm-ca.mobileconfig`, schreibt `epm-zertifikat` bei jedem Einrichten/Erneuern/Importieren; auf bestehenden Servern
einmal `sudo epm-zertifikat erneuern` bzw. `importieren`, sonst baut der Browser das Profil selbst) und wird einmal je
PC/Telefon installiert – zum Herunterladen für alle unter Mein Konto › Gerät einrichten und auf der Anmeldeseite
(Anleitung in EPM unter Hilfe › „Passkey statt Code“). Den Namen auf der OPNsense per Unbound-Überschreibung auf die
Server-IP zeigen lassen. Ein Zertifikat einer anderen CA (z. B. der OPNsense): `sudo epm-zertifikat importieren CRT KEY CA`.
Status, Erneuern und Importieren gehen auch in EPM unter Administration › System › Zertifikat; nur das erstmalige
Einrichten der eigenen CA (`epm-zertifikat einrichten`) bleibt Teil der Ersteinrichtung per SSH.

## Datensicherung
Täglich um 02:00 (`epm-backup.timer`; Uhrzeit und „täglich/werktags“ in EPM unter Administration › Backup › Zeitplan,
als Drop-in `epm-backup.timer.d/zeitplan.conf`), 30 Tage auf dem Server unter `/srv/epm/backup` (unter Administration › Backup
auf 7, 14 oder 30 Tage einstellbar). Gesteuert wird alles unter
Administration › Backup: Passwort für die Verschlüsselung festlegen und das Passwortblatt im Tresor verwahren,
Übertragungsziel (WebDAV, z. B. Nextcloud mit App-Passwort) mit Zeitfenster, „Jetzt sichern“, Wiederherstellen (eigenes
Passwort und Code aus der Authenticator-App – die Zwei-Faktor-Anmeldung ist dafür nötig), Sicherung als eine Datei herunterladen und
wieder hochladen (z. B. von der Migrationsmaschine; Austausch über `/srv/epm/system/download` und `…/upload`). Passwort und Zugang liegen nur auf dem Server in `/etc/epm/sicherung` (root, 0600). Die Adresse des
Ziels muss im Proxy der OPNsense freigegeben sein. Nicht mehr gebrauchte Sicherungen lassen sich in der Liste ankreuzen
und gesammelt löschen (die jüngste bleibt immer); Protokolle der nächtlichen Sicherung und der Übertragung stehen unter
Administration › System › Protokolle. Ohne EPM entschlüsseln: `gpg -d -o epm-db_….dump epm-db_….dump.gpg`.

## Notfallpaket und Wiederaufbau (10.10.2026)
Administration › System › Notfall › „Notfallpaket erstellen“ (Passwort und zweiter Faktor) packt alles für einen
Neuaufbau ohne Internet in `epm-notfall-<TAG>-<Datum>.tar`: Images, Rollout-Skripte, Debian-Pakete, OCR-Modelle,
wahlweise die jüngste Sicherung, Einstellungen ohne Geheimnisse, CA (Schlüssel mit dem Sicherungs-Passwort
verschlüsselt), `SHA256SUMS`, `INHALT.json` und den Plan. Nach jedem Update und spätestens alle 30 Tage neu erstellen,
zwei Kopien getrennt lagern. Aufbau auf frischem Ubuntu Server: auspacken, im Ordner `sudo ./epm-notfall-aufbau.sh`
(`--probelauf` zeigt nur, was geschähe); die Rollout-Skripte laufen dabei mit `EPM_OFFLINE=1`. Plan:
[`docs/NOTFALLPLAN.md`](docs/NOTFALLPLAN.md).

## Bilder der Hilfe (11.10.2026)
Die Hilfe zeigt Bildschirmfotos und kurze GIFs (Wunsch 11.10.2026). Sie liegen in `frontend/public/hilfe-bilder/`
(Auslieferung unter `/hilfe-bilder/…`, im Image mit dabei) und stehen in `backend/hilfe/inhalt.py`. Neu erzeugen, z. B.
nach Änderungen an der Oberfläche – EPM muss laufen (Entwicklung: Vite auf 127.0.0.1:5173 mit Django):

```bash
cd frontend && npm ci && cd ..                       # Playwright aus frontend/node_modules
EPM_KENNWORT=… [EPM_CODE=…] node werkzeuge/hilfe-bilder.mjs          # alle Bilder
node werkzeuge/hilfe-bilder.mjs kontakt telefon                      # nur Bilder mit diesen Namen
```

Angemeldet wird mit einem **Testbenutzer** (Vorgabe `hilfe.bilder`, Rolle Mediziner), der nur die Testpatienten sieht –
das Werkzeug bricht bei anderen Konten ab. Die Sitzung bleibt in `werkzeuge/.hilfe-bilder-sitzung.json` (nicht im Repo).
Weitere Einstellungen: `EPM_URL` (Vorgabe `http://127.0.0.1:5173`), `EPM_BENUTZER`, `EPM_CHROMIUM` (Vorgabe
`/opt/pw-browsers/chromium`, leer = Chromium von Playwright), `EPM_PYTHON` (Python mit Pillow für GIFs und Verkleinern,
`werkzeuge/hilfe-gif.py`). Gespeichert wird nichts: Fenster werden nur geöffnet und mit Escape verworfen. Am Ende steht
eine Liste mit Größe und Maßen; ändern sich Maße, `width`/`height` in `inhalt.py` anpassen – der Test
`patienten.test_startseite.Hilfe` prüft Dateien, Alternativtexte und Seitenverhältnisse.

## Tests
Bei jedem Push laufen in GitHub Actions (`.github/workflows/backend.yml`):
1. Backend-Tests gegen PostgreSQL 18 (`backend/*/tests.py`), fehlende Migrationen werden erzeugt und eingecheckt.
2. Frontend: Typprüfung und Bau, danach `werkzeuge/ci-stack.sh start` (gleiche Compose-Datei, Nginx-Konfiguration und
   Images wie auf dem Server, mit Musterdaten und Testkonten) und die Browsertests `frontend/e2e/*.spec.ts`.

Beide Ergebnisse stehen als Kommentar am Commit.

Lokal mit Docker: `werkzeuge/ci-stack.sh start`, dann in `frontend/` `npm ci && npx playwright test`,
zum Schluss `werkzeuge/ci-stack.sh stop`.
