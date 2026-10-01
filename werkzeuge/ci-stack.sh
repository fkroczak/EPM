#!/usr/bin/env bash
# EPM – kompletter Betriebs-Stack für die Browsertests (GitHub Actions oder ein Entwickler-Rechner mit Docker).
# Gleiche compose.yaml, Nginx-Konfiguration und Images wie auf dem Server, nur an 127.0.0.1:443 gebunden.
#
#   werkzeuge/ci-stack.sh start     Images bauen, Stack starten, Musterdaten und Testkonten anlegen
#   werkzeuge/ci-stack.sh stop      Stack beenden und Daten löschen
#   werkzeuge/ci-stack.sh logs      Protokolle von Backend und Nginx
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"
B="${EPM_CI_BASIS:-/tmp/epm-ci}"
TAG="${EPM_CI_TAG:-ci}"
DOCKER="docker"; [[ $EUID -eq 0 ]] || DOCKER="sudo docker"
compose() { (cd "$B" && $DOCKER compose -p epm-ci "$@"); }

case "${1:-start}" in
  stop)
    compose down -v --remove-orphans 2>/dev/null || true
    sudo rm -rf "$B"
    exit 0 ;;
  logs)
    compose logs --tail 200 backend web
    exit 0 ;;
  start) ;;
  *) sed -n 2,8p "$0"; exit 1 ;;
esac

echo "==> Images bauen (epm-backend:$TAG, epm-web:$TAG)"
$DOCKER build --quiet -t "epm-backend:$TAG" backend >/dev/null
$DOCKER build --quiet -t "epm-web:$TAG" frontend >/dev/null

echo "==> Projektverzeichnis $B"
sudo rm -rf "$B"
mkdir -p "$B/secrets" "$B/nginx/certs" "$B/data/dokumente"
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
sudo chmod 0750 "$B/data"; sudo chmod 2770 "$B/data/dokumente"
sudo chown 101:101 "$B/nginx/certs/"*
sudo chmod 0400 "$B/nginx/certs/epm.key"

echo "==> Stack starten"
compose up -d --quiet-pull
for _ in $(seq 1 60); do
  status="$($DOCKER inspect -f '{{.State.Health.Status}}' "$(compose ps -q backend)" 2>/dev/null || true)"
  [[ "$status" == "healthy" ]] && break
  sleep 3
done
if [[ "$status" != "healthy" ]]; then
  echo "Backend startet nicht:"; compose logs --tail 80 backend; exit 1
fi

echo "==> Musterdaten und Testkonten"
compose exec -T backend python manage.py epm_musterdaten
compose exec -T backend python manage.py shell < "$REPO/frontend/e2e/vorbereiten.py"
for _ in $(seq 1 20); do
  curl -ksf https://localhost/api/auth/status/ >/dev/null && break
  sleep 1
done
curl -ksf https://localhost/ | grep -q '<div id="root"' && echo "Stack bereit: https://localhost"
