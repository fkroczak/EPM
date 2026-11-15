#!/usr/bin/env bash
# EPM – kompletter Betriebs-Stack für die Browsertests (GitHub Actions oder ein Entwickler-Rechner mit Docker).
# Gleiche compose.yaml, Nginx-Konfiguration und Images wie auf dem Server, nur an 127.0.0.1:443 gebunden.
#
#   werkzeuge/ci-stack.sh start     Images bauen, Stack starten, Musterdaten und Testkonten anlegen
#   werkzeuge/ci-stack.sh stop      Stack beenden und Daten löschen
#   werkzeuge/ci-stack.sh logs      Protokolle von Backend und Nginx
#   werkzeuge/ci-stack.sh protokoll Audit-Log und abgewiesene Anfragen (Fehlersuche)
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"
B="${EPM_CI_BASIS:-/tmp/epm-ci}"
TAG="${EPM_CI_TAG:-ci}"
DOCKER="docker"; [[ $EUID -eq 0 ]] || DOCKER="sudo docker"
# WebDAV-Ziel für die Übertragung der Sicherungen (Browsertest sicherung.spec.ts): rclone serve webdav, nur lokal
WEBDAV="${EPM_CI_WEBDAV:-/tmp/epm-ci-webdav}"
WEBDAV_ADRESSE="127.0.0.1:8099"
compose() { (cd "$B" && $DOCKER compose -p epm-ci "$@"); }

case "${1:-start}" in
  stop)
    sudo pkill -f "epm-systemagent.py schleife" 2>/dev/null || true
    pkill -f "rclone serve webdav" 2>/dev/null || true
    compose down -v --remove-orphans 2>/dev/null || true
    sudo rm -rf "$B" "$WEBDAV"
    exit 0 ;;
  logs)
    compose logs --tail 200 backend ocr web
    exit 0 ;;
  protokoll)
    # Zur Fehlersuche nach fehlgeschlagenen Browsertests: Anmeldungen und Benutzerverwaltung aus dem Audit-Log,
    # abgewiesene Anfragen (kompakt, ohne das erwartete 404 für ein fehlendes Logo) und Fehler im Backend
    echo "--- Audit-Log: Anmeldung, Sitzungen, Benutzer, Rechte ---"
    compose exec -T backend python manage.py shell -c "
from audit.models import SystemEreignis as E
arten = [a for a in E.Art.values if a.startswith(('anmeldung', 'abmeldung', 'kennwort', '2fa', 'benutzer', 'rechte', 'einmal', 'testdaten'))]
for e in E.objects.filter(art__in=arten).order_by('id')[:200]:
    name = e.benutzername or (e.benutzer.username if e.benutzer else '-')
    print(e.zeitpunkt.strftime('%H:%M:%S'), e.art, name, e.objekt or '', str(e.details)[:120])
"
    echo "--- abgewiesene Anfragen ---"
    compose logs --no-log-prefix web 2>/dev/null | grep -E '" (40[0-9]|5[0-9][0-9]) ' \
      | grep -v -E 'briefkopf/logo/ HTTP/[0-9.]+" 404|"curl/' \
      | sed -E 's/^[^[]*\[[^:]*:([0-9:]+)[^]]*\] "([A-Z]+) ([^ ]+) ([^"]*)" ([0-9]+) [0-9]+ "([^"]*)".*/\1 \5 \2 \3 \4 (\6)/' | head -150
    echo "--- Fehler im Backend ---"
    compose logs --no-log-prefix backend 2>/dev/null | grep -E -A4 'Traceback|ERROR|Internal Server Error' | tail -80
    exit 0 ;;
  start) ;;
  *) sed -n 2,8p "$0"; exit 1 ;;
esac

if [[ -n "${EPM_CI_OHNE_BAU:-}" ]]; then
  # CI: Images hat der Workflow schon gebaut (docker buildx bake mit Zwischenspeicher, werkzeuge/ci-bilder.hcl)
  echo "==> Images vorhanden (epm-backend:$TAG, epm-web:$TAG)"
  $DOCKER image inspect "epm-backend:$TAG" "epm-web:$TAG" >/dev/null
else
  echo "==> Images bauen (epm-backend:$TAG, epm-web:$TAG)"
  for bild in backend web; do
    ordner=$([ "$bild" = web ] && echo frontend || echo backend)
    if ! $DOCKER build --progress=plain -t "epm-$bild:$TAG" "$ordner" >"/tmp/bau-$bild.log" 2>&1; then
      echo "Bau von epm-$bild fehlgeschlagen, letzte Zeilen:"; tail -80 "/tmp/bau-$bild.log"; exit 1
    fi
  done
fi

echo "==> Projektverzeichnis $B"
sudo rm -rf "$B"
mkdir -p "$B/secrets" "$B/nginx/certs" "$B/data/dokumente" "$B/data/loeschliste" "$B/data/import" "$B/data/scans" "$B/system/auftraege" "$B/system/status/auftraege" \
  "$B/system/download" "$B/system/upload" "$B/backup" "$B/konf-sicherung"
chmod 0700 "$B/backup" "$B/konf-sicherung"
cp rollout/projekt/compose.yaml "$B/"
cp rollout/projekt/nginx/epm.conf "$B/nginx/"
openssl rand -hex 24 > "$B/secrets/db_password"
openssl rand -hex 48 > "$B/secrets/django_secret_key"
openssl req -x509 -newkey rsa:2048 -sha256 -days 2 -nodes -keyout "$B/nginx/certs/epm.key" -out "$B/nginx/certs/epm.crt" \
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null
sed -e "s#^DJANGO_ALLOWED_HOSTS=.*#DJANGO_ALLOWED_HOSTS=localhost#" \
    -e "s#^DJANGO_CSRF_TRUSTED_ORIGINS=.*#DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost#" \
    -e "s#^GUNICORN_WORKERS=.*#GUNICORN_WORKERS=2#" \
    rollout/projekt/backend.env.beispiel > "$B/backend.env"
cat > "$B/.env" <<EOF
COMPOSE_FILE=compose.yaml
EPM_BIND_IP=127.0.0.1
EPM_VERSION=$TAG
EOF
chmod 0644 "$B/secrets/"*
sudo chown -R 10001:101 "$B/data"
sudo chmod 0750 "$B/data"; sudo chmod 2770 "$B/data/dokumente"; sudo chmod 0700 "$B/data/loeschliste"
sudo chown 10001:101 "$B/system/auftraege"; sudo chmod 0770 "$B/system/auftraege"
sudo chown root:101 "$B/system/download"; sudo chmod 0750 "$B/system/download"
sudo chown 10001:101 "$B/system/upload"; sudo chmod 0770 "$B/system/upload"
sudo chown -R root:root "$B/system/status"; sudo chmod -R 0755 "$B/system/status"
sudo chown 101:101 "$B/nginx/certs/"*
sudo chmod 0400 "$B/nginx/certs/epm.key"

echo "==> Stack starten"
compose up -d --quiet-pull
# Bereit, sobald das Backend über Nginx antwortet (Migrationen fertig). Nicht auf „healthy“ warten: Docker prüft erst
# nach dem Intervall des Healthchecks (30 s) – das kostete in jedem CI-Teil bis zu 30 s.
bereit=""
for _ in $(seq 1 180); do
  if curl -ksf https://localhost/api/auth/status/ -o /dev/null; then bereit=1; break; fi
  laeuft="$($DOCKER inspect -f '{{.State.Running}}' "$(compose ps -aq backend)" 2>/dev/null || true)"
  [[ "$laeuft" == "false" ]] && break
  sleep 1
done
if [[ -z "$bereit" ]]; then
  echo "Backend startet nicht:"; compose logs --tail 80 backend; exit 1
fi

echo "==> Systemagent im Probelauf (wie auf dem Server; Updates, Neustart und Aufräumen nur simuliert,"
echo "    Sicherung, Übertragung und Wiederherstellen echt – mit epm-backup aus dem Repo)"
sudo pkill -f "epm-systemagent.py schleife" 2>/dev/null || true
sudo nohup python3 "$REPO/rollout/epm-systemagent.py" schleife --basis "$B" --projekt epm-ci --trocken --sicherung-echt \
  --konf "$B/konf-sicherung" --backup-skript "$REPO/rollout/epm-backup.sh" > /tmp/epm-systemagent.log 2>&1 &

if command -v rclone >/dev/null 2>&1; then
  echo "==> WebDAV-Testziel für die Übertragung ($WEBDAV_ADRESSE, Benutzer epm-ci)"
  pkill -f "rclone serve webdav" 2>/dev/null || true
  rm -rf "$WEBDAV"; mkdir -p "$WEBDAV"
  nohup rclone serve webdav "$WEBDAV" --addr "$WEBDAV_ADRESSE" --user epm-ci --pass "WebDAV-Test-2026" \
    > /tmp/epm-webdav.log 2>&1 &
else
  echo "WARNUNG: rclone fehlt – kein WebDAV-Testziel (sudo apt-get install rclone)"
fi
for _ in $(seq 1 30); do [[ -s "$B/system/status/system.json" ]] && break; sleep 1; done
[[ -s "$B/system/status/system.json" ]] && echo "Systemagent misst" || { echo "Systemagent liefert keinen Status:"; cat /tmp/epm-systemagent.log; }

echo "==> Musterdaten und Testkonten"
compose exec -T backend python manage.py epm_musterdaten
compose exec -T backend python manage.py shell < "$REPO/frontend/e2e/vorbereiten.py"
for _ in $(seq 1 20); do
  curl -ksf https://localhost/api/auth/status/ >/dev/null && break
  sleep 1
done
curl -ksf https://localhost/ | grep -q '<div id="root"' && echo "Stack bereit: https://localhost"
