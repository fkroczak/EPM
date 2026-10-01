#!/usr/bin/env bash
# EPM – Schritt 4/5: Images (Backend und Frontend) laden, auf den Betriebs-Stack umstellen, Musterdaten anlegen
# Aufruf: sudo ./05-backend.sh ~/epm-0.2.0.tar        (gebaut mit werkzeuge/bauen.sh bzw. bauen.ps1)
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }
cd "$(dirname "$0")"
KONF=/etc/epm/epm.conf; [[ -f "$KONF" ]] || KONF=./epm.conf
[[ -f "$KONF" ]] || { echo "Keine epm.conf gefunden (/etc/epm/epm.conf oder hier)."; exit 1; }
source "$KONF"
B="$EPM_BASE"

TAR="${1:?Bitte die Image-Datei angeben, z. B. ~/epm-0.2.0.tar}"
[[ -f "$TAR" ]] || { echo "Datei $TAR nicht gefunden."; exit 1; }
VERSION="$(basename "$TAR" .tar)"; VERSION="${VERSION#epm-backend-}"; VERSION="${VERSION#epm-}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Version nicht erkannt (erwartet epm-X.Y.Z.tar)."; exit 1; }

echo "==> Projektdateien aktualisieren"
./04-projekt.sh >/dev/null

echo "==> Image laden (Version $VERSION)"
install -m 0600 "$TAR" "$B/images/"
docker load -i "$B/images/$(basename "$TAR")"
docker image inspect "epm-web:$VERSION" >/dev/null 2>&1 || {
  echo "Im Paket fehlt das Frontend-Image epm-web:$VERSION – bitte mit dem aktuellen bauen.sh/bauen.ps1 neu bauen."; exit 1; }

echo "==> Auf den Betriebs-Stack umstellen"
sed -i -e 's/^COMPOSE_FILE=.*/COMPOSE_FILE=compose.yaml/' -e "s/^EPM_VERSION=.*/EPM_VERSION=$VERSION/" "$B/.env"
cd "$B"
docker compose up -d --remove-orphans

echo "==> Warte auf das Backend (Migrationen laufen beim ersten Start)"
for i in $(seq 1 60); do
  status="$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q backend)" 2>/dev/null || true)"
  [[ "$status" == "healthy" ]] && break
  sleep 3
done
if [[ "$status" != "healthy" ]]; then
  echo "Backend ist nicht bereit. Letzte Meldungen:"
  docker compose logs --tail 40 backend
  exit 1
fi

echo "==> Musterdaten (Auswahllisten, Präparate, Testbenutzer, Testpatienten)"
docker compose exec -T backend python manage.py epm_musterdaten

echo
docker compose ps
echo
echo "Fertig. Als Nächstes den Admin anlegen und einrichten:"
echo "  cd $B"
echo "  sudo docker compose exec backend python manage.py epm_admin_anlegen admin --vorname Vorname --nachname Nachname"
echo "  sudo docker compose exec backend python manage.py epm_zugang_einrichten admin"
