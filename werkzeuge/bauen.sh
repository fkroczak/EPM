#!/usr/bin/env bash
# EPM – Images (Backend und Frontend) auf Linux bauen (z. B. in der Test-VM) und als Datei speichern
# Aufruf im Ordner mit diesem Skript:   ./bauen.sh            (Version aus werkzeuge/version.sh)
#                                       ./bauen.sh 0.2.1      (andere Version)
set -euo pipefail
cd "$(dirname "$0")/.."
# Ohne Angabe gilt die Version des Projekts – sonst entstünde ein Paket mit einer alten Nummer, das beim
# Einspielen eine neuere Fassung überschreibt (Stolperstein 06.10.2026).
VERSION="${1:-$(werkzeuge/version.sh)}"   # Grundstand aus VERSION, letzte Stelle zählt je Änderung auf main hoch
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Version nicht erkannt: „$VERSION“ (erwartet X.Y.Z)."; exit 1; }
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

echo "==> Baue epm-web:$VERSION (Frontend)"
$DOCKER build -t "epm-web:$VERSION" frontend

echo "==> Speichere beide Images"
$DOCKER save "$IMAGE" "epm-web:$VERSION" -o "epm-$VERSION.tar"
[[ $EUID -eq 0 ]] || sudo chown "$(id -u):$(id -g)" "epm-$VERSION.tar"
echo
echo "Fertig: $PWD/epm-$VERSION.tar"
echo "Weiter mit:  cd ~/epm-rollout && sudo ./05-backend.sh $PWD/epm-$VERSION.tar"
