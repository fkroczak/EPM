# EPM – Elektronisches Patienten-Management

| Ordner | Inhalt |
|---|---|
| `backend/` | Django-Backend (siehe `backend/README.md`) |
| `rollout/` | Server-Einrichtung: `01-basis.sh` … `05-backend.sh`, Compose, Nginx |
| `werkzeuge/` | `epm-update.sh` (Update in einem Schritt), `epm-git-einrichten.sh`, `bauen.sh`/`bauen.ps1` |
| `VERSION` | Versionsnummer; das Image heißt `epm-backend:<VERSION>-<Commit>` |

## Test-VM aktualisieren
```bash
sudo epm-update                # holen, bauen, Backup, starten, Musterdaten, Tests
sudo epm-update --versionen    # vorhandene Versionen
sudo epm-update --zurueck TAG  # zurückschalten
```
Die Konfiguration des Servers liegt in `/etc/epm/epm.conf` (nicht im Repo).
