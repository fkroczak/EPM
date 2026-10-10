# EPM komplett offline – Prüfung vom 10.10.2026

Vorgabe des Auftraggebers: Alles bleibt auf dem Server. EPM darf zur Laufzeit nichts aus dem Internet nachladen und
muss vollständig abgeschottet arbeiten können. Geprüft im Zuge von F182 („Texterkennung lernt mit“) am Code-Stand
nach `e0e5585` (inklusive Systemverwaltung F179 und Vorlagen-Portal F180).

Kurz: **Im laufenden Betrieb baut EPM selbst keine Verbindung nach außen auf.** Nach außen gehen nur Dinge, die ein
Admin bewusst einrichtet oder auslöst (Übertragung der Sicherungen per WebDAV, Ubuntu-Updates, EPM-Update auf der
Test-VM) sowie Grundfunktionen des Betriebssystems, die das Rollout so einstellt (automatische Sicherheitsupdates,
Zeitabgleich). Ein Leck in EPM wurde nicht gefunden; abgesichert wurde die Texterkennung (siehe 2.1).

## 1. Was geprüft wurde

| Bereich | Wie geprüft | Ergebnis |
|---|---|---|
| Backend (Django, alle Apps) | Suche nach `requests`, `httpx`, `urllib.request`, `urlopen`, `socket`, `smtplib`, `http.client`, `subprocess` mit `pip`/`npm`/`curl`/`wget` | keine Laufzeit-Zugriffe nach außen. `urllib.parse` nur zum Bauen von Dateinamen/Adressen. Kein E-Mail-Versand (E-Mails entstehen als `.eml` zum Herunterladen, F172) |
| PDF-Erzeugung (WeasyPrint) | `vorlagen/pdf.py` | eigener URL-Fetcher `nur_eingebettet`: nur `data:`-Adressen, alles andere wird abgewiesen – auch Bilder oder Schriften aus Vorlagen, die ins Netz zeigen |
| Passkeys (webauthn) | `accounts/passkey.py` | Prüfung lokal, keine Abfrage von Herstellerdaten (FIDO MDS) |
| Texterkennung PP-OCRv5 | `scans/ocr/paddle.py`, `erkennung.py` | EPM nutzt **weder PaddleOCR noch PaddleX**; die ONNX-Modelle werden direkt mit onnxruntime gelesen – es gibt keinen Programmteil, der Modelle herunterladen könnte. Abgesichert, siehe 2.1 |
| Texterkennung Tesseract, OCRmyPDF, Ghostscript | `scans/ocr/tesseract.py`, `aufbereitung.py`, `dokumente.py` | reine Programme ohne Netz. Tesseract liest nur `EPM_TESSDATA` (Image: `deu.traineddata` aus dem Repo, `osd`/`eng` aus dem Ubuntu-Paket) |
| Modelle laden (`scans/modelle/holen.py`) | Aufrufer gesucht | nur beim **Bau** des Images (Dockerfile, Stufe `modelle`), im CI und in `werkzeuge/ocr-modelle.sh` bzw. als Prüfung (`--nur-pruefen`) in `epm-update`; nie zur Laufzeit. Offline: Modelle als Datei einspielen (Systemverwaltung › „OCR-Modelle einspielen“, F179, oder `epm-ocr-modelle einspielen`) |
| Frontend | `index.html`, CSS, alle Quellen, gebautes `dist/` nach `http(s)://` durchsucht | keine externen Skripte, Schriften, Bilder, CDN, Google Fonts, Telemetrie. Schriften IBM Plex über `@fontsource` im Bundle; pdf.js-Worker, CMaps, Standardschriften, WASM und ICC-Profile liegen unter `/pdfjs/` im eigenen Server. Treffer im Bundle sind nur Namensräume (w3.org, adobe), Doku-Links in Fehlermeldungen von Bibliotheken und Beispieltexte – nichts davon wird geladen |
| Browser-Absicherung | `rollout/projekt/nginx/epm.conf` | Content-Security-Policy `default-src 'self'` (+ `data:` für Bilder): selbst ein versehentlich eingebauter externer Verweis würde im Browser blockiert |
| Container und Netz | `rollout/projekt/compose.yaml` | Datenbank, Backend und OCR-Dienst hängen nur am Netz `intern` (`internal: true`, **kein Weg nach außen**). Nur Nginx (`web`) hängt zusätzlich an `extern`, um Port 443 anzubieten; er leitet nur an `backend:8000` weiter, kein `resolver`, kein OCSP-Stapling. Healthchecks fragen nur `localhost` bzw. eine Datei |
| Start des Backends | `backend/entrypoint.sh` | Migrationen, Löschliste, `collectstatic`, Gunicorn – kein `pip`, kein `npm`, kein Download |
| Systemagent | `rollout/epm-systemagent.py` (inkl. F179) | nur auf Auftrag aus der Oberfläche; Netz nur für die unten genannten Aktionen. „Ausstehende Updates“ ist eine Simulation (`apt-get -s`) mit den vorhandenen Paketlisten, ohne Netz |
| Systemverwaltung im Backend | `backend/system/*` (inkl. F179) | legt nur Aufträge als Dateien ab; Hochladen von Update-Paketen und OCR-Modellen statt Download |
| Datensicherung | `rollout/epm-backup.sh` | lokal (`pg_dump`, `tar`), Übertragung nur, wenn ein WebDAV-Ziel eingerichtet ist |

## 2. Was abgestellt bzw. abgesichert wurde

### 2.1 Texterkennung: nie ein Download (F182)
- `paddle.offline_erzwingen()` setzt beim Laden die Schalter, mit denen Paddle, PaddleX und Hugging Face jeden
  Download und jede Telemetrie unterlassen (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`,
  `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True`, `PADDLEOCR_DISABLE_AUTO_DOWNLOAD=1`, `DISABLE_MODEL_SOURCE_CHECK=True`,
  `DO_NOT_TRACK=1`) – für den Fall, dass eine dieser Bibliotheken einmal ins Image kommt.
- `EPM_OCR_MODELLE` muss ein Verzeichnis sein (eine Adresse wird abgewiesen); `_sitzung` öffnet nur vorhandene
  Dateien. Fehlen die Modelle, arbeitet die Erkennung nur mit Tesseract weiter (wie bisher, Hinweis in „Scans“ und
  in der Systemverwaltung).
- Test `scans/test_lernen.py`, `OfflineTest`: verbietet während der Erkennung jeden Netzwerkzugriff
  (`socket.connect`, `socket.create_connection`, `socket.getaddrinfo` gepatcht, nur Unix-Sockets erlaubt) und erkennt
  trotzdem einen Laborbefund – mit PP-OCR, wenn die Modelle da sind, und ohne PP-OCR (nur Tesseract). Er prüft außerdem
  die Schalter und dass eine Adresse als Modellordner abgewiesen wird.
- Gelernte Zuordnungen (F182) liegen in der eigenen Datenbank; nichts davon verlässt den Server.

### 2.2 Keine weiteren Lecks in EPM
In EPM selbst gab es nichts abzustellen. Die Punkte in Abschnitt 4 liegen außerhalb des Auftrags (Rollout,
Betriebssystem, Systemagent) und sind dort zu entscheiden.

## 3. Was nach außen geht und warum (nur wenn eingerichtet oder ausgelöst)

| Verbindung | Wer | Wann | Abschalten |
|---|---|---|---|
| WebDAV (z. B. Nextcloud) für die Übertragung der Sicherungen | Systemagent mit `rclone` | **nur wenn eingerichtet** (Administration › Backup › Ziel), im eingestellten Zeitfenster; „Verbindung prüfen“ auf Knopfdruck | Ziel entfernen |
| Ubuntu-Paketquellen (`apt-get update/upgrade`) | Systemagent | **nur auf Knopfdruck** in der Systemverwaltung („Ubuntu-Updates einspielen“), über `EPM_APT_PROXY`, falls gesetzt | nicht auslösen |
| Ubuntu-Sicherheitsupdates automatisch (`unattended-upgrades`, täglich) | Betriebssystem | vom Rollout eingerichtet (`rollout/01-basis.sh`), über den APT-Proxy | `/etc/apt/apt.conf.d/20auto-upgrades` auf `"0"` oder Proxy sperren; dann Updates per Paket/Hand |
| Zeitabgleich (NTP) | Betriebssystem (chrony/timesyncd) | immer; mit `EPM_NTP_SERVER` nur zur OPNsense, **ohne Angabe zu den Ubuntu-Standardservern** (`ntp.ubuntu.com`) | `EPM_NTP_SERVER` setzen (Rollout trägt ihn ein und leert die Fallbacks) |
| EPM-Update auf der Test-VM (`EPM_UPDATE_QUELLE="git"`) | `epm-update` (Knopf „EPM aktualisieren“ oder Konsole) | **nur wenn ausgelöst**: GitHub (`git fetch`), Docker Hub (Basis-Images), PyPI, npm-Registry, huggingface.co (PP-OCR-Modelle, falls nicht vorrätig) – alles beim **Bau** | VPS: `EPM_UPDATE_QUELLE="paket"` (Festlegung 02.10.2026): kein git, kein Bau, Update als geprüfte Datei hochladen (F179) |
| Erst-Einrichtung (`rollout/0x-*.sh`) | Admin | einmalig: apt, `download.docker.com`, Docker-Images | – |
| Browser der Benutzer | – | EPM-Seiten laden nur vom eigenen Server (CSP `default-src 'self'`) | – |

## 4. Funde außerhalb des Auftrags (nur gemeldet, nicht geändert)

1. **`rollout/01-basis.sh` – Ubuntu-Standarddienste, die von sich aus ins Netz gehen**: `motd-news`
   (`motd.ubuntu.com`), Ubuntu-Pro/ESM-Hinweise von apt (`esm.ubuntu.com`, `contracts.canonical.com`), ggf. `snapd`
   (Store), `apport`/`whoopsie` (Absturzberichte), `popularity-contest`, `cloud-init` auf VPS. Das Rollout schaltet sie
   nicht ab. Vorschlag für das Rollout:
   `sed -i 's/^ENABLED=1/ENABLED=0/' /etc/default/motd-news; systemctl disable --now motd-news.timer;
   pro config set apt_news=false; systemctl disable --now apport.service whoopsie.service 2>/dev/null;
   apt-get purge -y popularity-contest; snap list >/dev/null 2>&1 && systemctl disable --now snapd.service snapd.socket`.
   Ohne Weg nach außen (Abschnitt 5) laufen diese Versuche ohnehin ins Leere.
2. **Zeitabgleich ohne `EPM_NTP_SERVER`** fragt die Ubuntu-Server; auf abgeschotteten Servern immer setzen.
3. **`unattended-upgrades`** ist ein gewollter, aber automatischer Weg nach außen (Abschnitt 3); bei völliger
   Abschottung abschalten und Updates als Paket einspielen.
4. **`rollout/epm-systemagent.py` und `backend/system/*` (F179)**: keine ungewollten Verbindungen gefunden. Netz nur
   bei „EPM aktualisieren“ im Git-Modus, „Ubuntu-Updates“ und WebDAV (Abschnitt 3). OCR-Modelle und Update-Pakete
   kommen als hochgeladene, geprüfte Datei.
5. **„Datenbank leeren“** (`backend/system/leeren.py`): leert die gelernten Zuordnungen noch nicht (Aufruf
   `scans.lernen.leeren()` fehlt) und entfernt keine nicht zugeordneten Scans (U74 in `docs/BACKEND-FUNKTIONEN.md`).
   Kein Leck nach außen, aber für das Leeren vor dem Go-live nachzutragen.

## 5. So prüft man, dass der Server abgeschottet läuft

Ziel: ausgehende Verbindungen sperren, eingehendes HTTPS/SSH aus dem Verwaltungsnetz erlauben, dann EPM
durchprobieren. Docker verwaltet eigene nftables-Regeln; deshalb die Sperre in der Kette `DOCKER-USER` (für
Container) **und** in `output` (für den Rechner selbst) setzen.

### 5.1 Sperren (nftables, als root)
```bash
# Rechner selbst: nur Loopback, bestehende Verbindungen (z. B. Ihre SSH-Sitzung) und das Verwaltungsnetz
nft add table inet epm_offline
nft add chain inet epm_offline aus '{ type filter hook output priority 0; policy drop; }'
nft add rule inet epm_offline aus oif lo accept
nft add rule inet epm_offline aus ct state established,related accept
nft add rule inet epm_offline aus ip daddr 192.168.56.0/24 accept          # Verwaltungsnetz (anpassen)
nft add rule inet epm_offline aus log prefix '"EPM-OFFLINE aus: "' counter drop
# Container: nichts nach außen (Docker-Netze untereinander bleiben erlaubt)
iptables -I DOCKER-USER -o "$(ip route show default | awk '{print $5; exit}')" -m conntrack ! --ctstate ESTABLISHED,RELATED -j LOG --log-prefix "EPM-OFFLINE docker: "
iptables -I DOCKER-USER -o "$(ip route show default | awk '{print $5; exit}')" -m conntrack ! --ctstate ESTABLISHED,RELATED -j DROP
```
Mit ufw geht es ebenso: `ufw default deny outgoing; ufw allow out on lo; ufw allow out to 192.168.56.0/24; ufw enable`
(für Container zusätzlich die `DOCKER-USER`-Regel oben, ufw greift dort nicht).

Aufheben: `nft delete table inet epm_offline` und die beiden `DOCKER-USER`-Regeln mit `iptables -D …` entfernen.

### 5.2 Durchprobieren (mit Sperre)
1. Anmelden (Passwort und zweiter Faktor bzw. Passkey), Startseite, Patientenliste, Akte öffnen.
2. Kontakt, Gewicht, Termin erfassen; Dokument hochladen, als PDF ansehen (pdf.js lädt Worker und Schriften vom Server).
3. Scans: Foto eines Laborbefunds hochladen, warten bis „erkannt“, zuordnen und Werte übernehmen; Systemverwaltung
   zeigt, ob PP-OCR bereitsteht. „Text erkennen“ an einem Dokument der Akte (OCRmyPDF).
4. Gelernte Zuordnungen öffnen, Kennzahl „korrigiert“ anklicken.
5. Schreiben/Bericht als PDF erzeugen, E-Mail (`.eml`) herunterladen, Infoblatt an die Praxis.
6. Sicherung starten (lokal); Systemverwaltung öffnen.
7. Danach im Kernelprotokoll nach blockierten Versuchen suchen:
   `journalctl -k --since "-1h" | grep EPM-OFFLINE` – erwartet: **keine** Einträge aus EPM. Einträge von
   `unattended-upgrades`, NTP oder `motd-news` gehören zum Betriebssystem (Abschnitt 3/4).
8. Gegenprobe: `docker compose exec backend python -c "import socket; socket.create_connection(('1.1.1.1', 443), 3)"`
   muss scheitern (Netz `intern` ohne Ausgang), ebenso für den Dienst `ocr`.

### 5.3 Im Test
`python manage.py test scans.test_lernen.OfflineTest` – Erkennung mit verbotenem Netzwerk (siehe 2.1).
