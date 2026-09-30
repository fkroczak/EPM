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
install -d -m 0755 /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
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

echo
docker --version
docker compose version
docker info --format 'Speicher: {{.Driver}} | Logging: {{.LoggingDriver}} | Live-Restore: {{.LiveRestoreEnabled}}'
echo
echo "Fertig. Docker startet ab jetzt mit dem System."
echo "Hinweis: epmadmin wird bewusst NICHT in die Gruppe 'docker' aufgenommen (wäre root-gleich)."
echo "Docker-Befehle daher mit sudo ausführen."
