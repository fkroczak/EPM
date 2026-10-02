#!/usr/bin/env bash
# EPM – Schritt 2: Docker Engine + Compose aus dem offiziellen Docker-Repository, mit Autostart
# Aufruf: sudo ./02-docker.sh
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }
cd "$(dirname "$0")"
KONF=/etc/epm/epm.conf; [[ -f "$KONF" ]] || KONF=./epm.conf
[[ -f "$KONF" ]] || { echo "Keine epm.conf gefunden (/etc/epm/epm.conf oder hier)."; exit 1; }
source "$KONF"
export DEBIAN_FRONTEND=noninteractive
[[ -n "$EPM_APT_PROXY" ]] && export http_proxy="$EPM_APT_PROXY" https_proxy="$EPM_APT_PROXY"

echo "==> Konfliktpakete entfernen (falls vorhanden)"
for p in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  apt-get -y remove "$p" >/dev/null 2>&1 || true
done

echo "==> Docker-Repository einrichten"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
CODENAME="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")"
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $CODENAME
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update

echo "==> Docker installieren"
apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Docker-Daemon konfigurieren"
# Eigene Adressbereiche („EPM-Server Aufbau“ B3): Docker nimmt sonst 172.17.0.0/16 und aufwärts – das kollidiert gern mit
# VPN-Pools, und VPN-Nutzer erreichen den Server dann nicht mehr. Darf weder im LAN noch im SSL-VPN-Pool vorkommen.
DOCKER_BIP="${EPM_DOCKER_BIP:-10.231.0.1/24}"       # Standard-Bridge docker0
DOCKER_POOL="${EPM_DOCKER_POOL:-10.231.16.0/20}"    # Pool für Compose-Netze (je /24)
install -d -m 0755 /etc/docker
cat > /etc/docker/daemon.json <<EOF
{
  "bip": "$DOCKER_BIP",
  "default-address-pools": [ { "base": "$DOCKER_POOL", "size": 24 } ],
  "log-driver": "local",
  "log-opts": { "max-size": "20m", "max-file": "5" },
  "live-restore": true,
  "no-new-privileges": true,
  "userland-proxy": false,
  "icc": false
}
EOF

echo "==> Autostart"
systemctl enable containerd.service docker.service
systemctl restart docker
# Läuft EPM schon (Server wird nachgerüstet): Netze werden nur beim Anlegen adressiert – Stack einmal ab- und wieder
# aufbauen, damit seine Netze im Adressbereich oben entstehen (Daten und Volumes bleiben).
if [[ -f "$EPM_BASE/.env" ]] && (cd "$EPM_BASE" && docker compose ps -q | grep -q .); then
  echo "==> EPM-Stack neu aufbauen (Netze im neuen Adressbereich)"
  (cd "$EPM_BASE" && docker compose down)
  if [[ -f /etc/systemd/system/epm.service ]]; then systemctl restart epm.service; else (cd "$EPM_BASE" && docker compose up -d); fi
fi

echo "==> Wöchentliches Aufräumen (nur verwaiste Images und alter Build-Cache, „EPM-Server Aufbau“ B6)"
# KEIN „prune --all“ und nie „--volumes“: die älteren Images auf dem Server sind der Rückweg nach einem Update
# (sudo epm-update --zurueck). Alte Versionen löscht man bewusst von Hand.
cat > /etc/cron.weekly/docker-cleanup <<'CRON'
#!/bin/sh
docker image prune --force
docker builder prune --force --filter "until=168h"
CRON
chmod +x /etc/cron.weekly/docker-cleanup

echo
docker --version
docker compose version
docker info --format 'Speicher: {{.Driver}} | Logging: {{.LoggingDriver}} | Live-Restore: {{.LiveRestoreEnabled}}'
ip -brief addr show docker0 2>/dev/null || true
echo
echo "Fertig. Docker startet ab jetzt mit dem System; den EPM-Stack startet epm.service (eingerichtet von 04-projekt.sh)."
echo "Hinweis: epmadmin wird bewusst NICHT in die Gruppe 'docker' aufgenommen (wäre root-gleich)."
echo "Docker-Befehle daher mit sudo ausführen."
