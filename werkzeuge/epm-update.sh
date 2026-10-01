#!/usr/bin/env bash
# EPM – Update in einem Schritt: Code holen, Image bauen, starten, Musterdaten, Tests.
#
#   sudo epm-update                 neuesten Stand von GitHub holen und ausrollen
#   sudo epm-update --ohne-tests    ohne Testlauf (schneller)
#   sudo epm-update --zurueck TAG   auf eine frühere Version zurückschalten (z. B. 0.1.1-3fa2c1d)
#   sudo epm-update --versionen     vorhandene Versionen anzeigen
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }

CODE=/srv/epm-code
KONF=/etc/epm/epm.conf
[[ -f "$KONF" ]] || { echo "Fehlt: $KONF (siehe epm-git-einrichten.sh)"; exit 1; }
source "$KONF"
B="$EPM_BASE"
TESTS=1

schritt() { echo; echo "==> $*"; }

starte_version() {
  local tag="$1"
  sed -i -e 's/^COMPOSE_FILE=.*/COMPOSE_FILE=compose.yaml/' -e "s/^EPM_VERSION=.*/EPM_VERSION=$tag/" "$B/.env"
  (cd "$B" && docker compose up -d --remove-orphans)
  schritt "Warte auf das Backend"
  local status=""
  for _ in $(seq 1 60); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$(cd "$B" && docker compose ps -q backend)" 2>/dev/null || true)"
    [[ "$status" == "healthy" ]] && return 0
    sleep 3
  done
  echo "Backend startet nicht. Letzte Meldungen:"
  (cd "$B" && docker compose logs --tail 40 backend)
  return 1
}

case "${1:-}" in
  --versionen)
    docker image ls epm-backend --format '{{.Tag}}\t{{.CreatedSince}}'
    echo "aktiv: $(grep ^EPM_VERSION= "$B/.env" | cut -d= -f2)"
    exit 0 ;;
  --zurueck)
    TAG="${2:?Version angeben, siehe: sudo epm-update --versionen}"
    docker image inspect "epm-backend:$TAG" >/dev/null || { echo "Version $TAG nicht vorhanden."; exit 1; }
    docker image inspect "epm-web:$TAG" >/dev/null || { echo "Frontend-Image epm-web:$TAG fehlt."; exit 1; }
    starte_version "$TAG"
    echo "Zurückgeschaltet auf $TAG. Achtung: Datenbank-Migrationen werden dabei nicht zurückgedreht."
    exit 0 ;;
  --ohne-tests) TESTS=0 ;;
  "") ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac

schritt "Code von GitHub holen"
git -C "$CODE" fetch --quiet origin
ALT="$(git -C "$CODE" rev-parse --short HEAD)"
git -C "$CODE" reset --quiet --hard origin/main
NEU="$(git -C "$CODE" rev-parse --short HEAD)"
TAG="$(tr -d '[:space:]' < "$CODE/VERSION")-$NEU"
if [[ "$ALT" != "$NEU" ]]; then
  git -C "$CODE" log --oneline "$ALT..$NEU" | sed 's/^/   /'
else
  echo "   keine neuen Änderungen ($NEU)"
fi

schritt "Projektdateien aktualisieren (Compose, Nginx, Skripte)"
(cd "$CODE/rollout" && ./04-projekt.sh >/dev/null)
install -m 0750 "$CODE/werkzeuge/epm-update.sh" /usr/local/sbin/epm-update

if docker image inspect "epm-backend:$TAG" >/dev/null 2>&1 && docker image inspect "epm-web:$TAG" >/dev/null 2>&1; then
  schritt "Images epm-backend:$TAG und epm-web:$TAG sind schon gebaut"
else
  schritt "Image epm-backend:$TAG bauen"
  docker build --quiet -t "epm-backend:$TAG" "$CODE/backend" >/dev/null
  docker run --rm -e DJANGO_DEBUG=1 "epm-backend:$TAG" python manage.py check
  if ! docker run --rm -e DJANGO_DEBUG=1 "epm-backend:$TAG" python manage.py makemigrations --check --dry-run >/dev/null; then
    echo "ABBRUCH: Im Code fehlen Datenbank-Migrationen. Nichts wurde umgestellt."
    exit 1
  fi
  schritt "Image epm-web:$TAG bauen (Frontend, braucht Zugang zu registry.npmjs.org)"
  docker build --quiet -t "epm-web:$TAG" "$CODE/frontend" >/dev/null
  docker save "epm-backend:$TAG" "epm-web:$TAG" -o "$B/images/epm-$TAG.tar"
  chmod 0600 "$B/images/epm-$TAG.tar"
  # nur die letzten 5 Image-Dateien behalten
  ls -1t "$B"/images/epm-*.tar 2>/dev/null | tail -n +6 | xargs -r rm -f
fi

schritt "Backup vor dem Umstellen"
if (cd "$B" && docker compose ps --status running -q db | grep -q .); then
  /usr/local/sbin/epm-backup
fi

schritt "Version $TAG starten (Migrationen laufen automatisch)"
starte_version "$TAG"

schritt "Musterdaten prüfen"
(cd "$B" && docker compose exec -T backend python manage.py epm_musterdaten)

if [[ $TESTS -eq 1 ]]; then
  schritt "Tests (eigene Test-Datenbank, echte Daten bleiben unberührt)"
  LOG=/var/log/epm-tests.log
  if (cd "$B" && docker compose run --rm -T backend python manage.py test) >"$LOG" 2>&1; then
    ERGEBNIS="Tests OK"
  else
    ERGEBNIS="TESTS FEHLGESCHLAGEN – Ausgabe oben, vollständig in $LOG"
  fi
  grep -v " WARNING django.request: " "$LOG" | tail -25
else
  ERGEBNIS="Tests übersprungen"
fi

echo
echo "────────────────────────────────────────────"
echo " EPM $TAG läuft – $ERGEBNIS"
echo " https://$EPM_WEB_NAME/verwaltung/"
echo " Zurück auf die vorige Version: sudo epm-update --versionen"
echo "────────────────────────────────────────────"
