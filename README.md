# EPM – Elektronisches Patienten-Management

| Ordner | Inhalt |
|---|---|
| `backend/` | Django-Backend (siehe `backend/README.md`) |
| `frontend/` | Oberfläche: React, TypeScript, Vite, Tailwind, Base UI (Bausteine im Stil von shadcn/ui), TipTap; Browsertests in `frontend/e2e/` (Playwright) |
| `rollout/` | Server-Einrichtung: `01-basis.sh` … `05-backend.sh`, Compose, Nginx |
| `werkzeuge/` | `epm-update.sh` (Update in einem Schritt), `ci-stack.sh` (kompletter Stack für die Browsertests), `epm-git-einrichten.sh`, `bauen.sh`/`bauen.ps1` |
| `docs/BACKEND-FUNKTIONEN.md` | Nachweis aller Funktionen mit API-Verträgen, Tests und Status |
| `VERSION` | Versionsnummer; die Images heißen `epm-backend:<VERSION>-<Commit>` und `epm-web:<VERSION>-<Commit>` |

## Images

- `epm-backend` – Django mit Gunicorn (`backend/Dockerfile`)
- `epm-web` – Nginx mit dem gebauten Frontend (`frontend/Dockerfile`). Zum Bauen braucht der Server Zugang zu
  `registry.npmjs.org` (Proxy-Freigabe); ohne Zugang die Images mit `werkzeuge/bauen.sh` auf einem anderen Rechner bauen
  und als `epm-<VERSION>.tar` mit `rollout/05-backend.sh` einspielen.

## Test-VM aktualisieren
```bash
sudo epm-update                # holen, bauen (Backend und Frontend), Backup, starten, Musterdaten, Tests
sudo epm-update --versionen    # vorhandene Versionen
sudo epm-update --zurueck TAG  # zurückschalten (beide Images)
```
Die Konfiguration des Servers liegt in `/etc/epm/epm.conf` (nicht im Repo). Die Oberfläche ist danach unter
`https://<EPM_WEB_NAME>/` erreichbar, die Django-Verwaltung unter `/verwaltung/` (nur Rolle Admin).

## Tests
Bei jedem Push laufen in GitHub Actions (`.github/workflows/backend.yml`):
1. Backend-Tests gegen PostgreSQL 18 (`backend/*/tests.py`), fehlende Migrationen werden erzeugt und eingecheckt.
2. Frontend: Typprüfung und Bau, danach `werkzeuge/ci-stack.sh start` (gleiche Compose-Datei, Nginx-Konfiguration und
   Images wie auf dem Server, mit Musterdaten und Testkonten) und die Browsertests `frontend/e2e/*.spec.ts`.

Beide Ergebnisse stehen als Kommentar am Commit.

Lokal mit Docker: `werkzeuge/ci-stack.sh start`, dann in `frontend/` `npm ci && npx playwright test`,
zum Schluss `werkzeuge/ci-stack.sh stop`.
