# Ladezeiten messen (Performance-Prüfung 14.11.2026)

Werkzeuge der Messung aus `docs/PERFORMANCE-PRUEFUNG-2026-11-14.md`, nur für Entwicklung und Prüfung – nie auf einem
Server mit echten Daten. Die Pfade (`/var/tmp/mess`, `/var/tmp/epm-vorher`) sind die der Prüfung; zum Wiederholen
diesen Ordner nach `/var/tmp/mess` kopieren oder die Pfade anpassen.

| Datei | Zweck |
|---|---|
| `mess_mw.py`, `settings_mess.py` | Django-Einstellungen mit Middleware, die je Antwort `X-Mess-Q` (SQL-Abfragen) und `X-Mess-Ms` (Serverzeit) setzt |
| `start.sh` / `start-vorher.sh` | neuer Stand (gunicorn :8000) bzw. alter Stand aus einem `git worktree` (:8001) starten |
| `server.mjs` | Prüfserver wie Nginx im Betrieb: HTTP/2 + TLS, `/assets/` ein Jahr im Cache, gzip, `/api` an gunicorn |
| `messen.mjs` | Chromium (Playwright) meldet sich an und ruft 29 Seiten auf; misst „fertig“ (keine offene Anfrage und kein Ladehinweis mehr), FCP, Anfragen, SQL, Serverzeit |

## Ablauf

```bash
# PostgreSQL mit Musterdaten (epm_musterdaten, mehr Akten), Testkonten: frontend/e2e/vorbereiten.py
git worktree add /var/tmp/epm-vorher <alter Commit>          # Vergleichsstand
openssl req -x509 -newkey rsa:2048 -nodes -keyout /var/tmp/mess/tls.key -out /var/tmp/mess/tls.crt -days 30 -subj "/CN=127.0.0.1"
./start.sh; ./start-vorher.sh
node server.mjs /home/user/EPM/frontend/dist 8443 8000 &
node server.mjs /var/tmp/epm-vorher/frontend/dist 8444 8001 &
# DROSSEL=1: 40 ms Latenz, 20 Mbit/s (wie VPN); SPA=1: Navigation per Klick in der Anwendung statt Neuladen
BASIS=https://127.0.0.1:8444 SPA=1 DROSSEL=1 node messen.mjs vorher-spa.json 3
BASIS=https://127.0.0.1:8443 SPA=1 DROSSEL=1 node messen.mjs nachher-spa.json 3
```

Die Anmeldung nutzt die Notfall-Codes der Testkonten (je einmal gültig, 40 je Konto); `vorbereiten.py` setzt sie
zurück, danach `/var/tmp/mess/notfallcodes.json` löschen.
