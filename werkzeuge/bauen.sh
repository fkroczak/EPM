#!/usr/bin/env bash
# EPM – Backend-Image auf Linux bauen (z. B. in der Test-VM) und als Datei speichern
# Aufruf im Ordner mit diesem Skript:   ./bauen.sh            (Version 0.1.0)
#                                       ./bauen.sh 0.1.1      (andere Version)
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-0.1.0}"
IMAGE="epm-backend:$VERSION"
DOCKER="docker"; [[ $EUID -eq 0 ]] || DOCKER="sudo docker"

echo "==> Baue $IMAGE"
$DOCKER build -t "$IMAGE" backend

if [[ ! -f backend/patienten/migrations/0001_initial.py ]]; then
  echo "==> Erzeuge die Datenbank-Migrationen (nur beim ersten Mal)"
  $DOCKER run --rm -e DJANGO_DEBUG=1 -u "$(id -u):$(id -g)" -v "$PWD/backend:/app" "$IMAGE" \
    python manage.py makemigrations accounts stammdaten patienten infusionen audit
  echo "==> Baue erneut, jetzt mit Migrationen"
  $DOCKER build -t "$IMAGE" backend
fi

echo "==> Prüfe Projekt und Migrationen"
$DOCKER run --rm -e DJANGO_DEBUG=1 "$IMAGE" python manage.py check
$DOCKER run --rm -e DJANGO_DEBUG=1 "$IMAGE" python manage.py makemigrations --check --dry-run

echo "==> Speichere $IMAGE"
$DOCKER save "$IMAGE" -o "epm-backend-$VERSION.tar"
[[ $EUID -eq 0 ]] || sudo chown "$(id -u):$(id -g)" "epm-backend-$VERSION.tar"
echo
echo "Fertig: $PWD/epm-backend-$VERSION.tar"
echo "Weiter mit:  cd ~/epm-rollout && sudo ./05-backend.sh $PWD/epm-backend-$VERSION.tar"
