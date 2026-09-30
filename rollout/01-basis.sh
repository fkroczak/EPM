#!/usr/bin/env bash
# EPM – Schritt 1: Basis-Einrichtung Ubuntu Server 26.04 LTS
# Aufruf: sudo ./01-basis.sh
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }
cd "$(dirname "$0")"
KONF=/etc/epm/epm.conf; [[ -f "$KONF" ]] || KONF=./epm.conf
[[ -f "$KONF" ]] || { echo "Keine epm.conf gefunden (/etc/epm/epm.conf oder hier)."; exit 1; }
source "$KONF"
export DEBIAN_FRONTEND=noninteractive

echo "==> Hostname, Zeitzone, Sprache"
hostnamectl set-hostname "$EPM_HOSTNAME"
grep -q "$EPM_HOSTNAME" /etc/hosts || echo "127.0.1.1 $EPM_HOSTNAME" >> /etc/hosts
timedatectl set-timezone Europe/Berlin
locale-gen de_DE.UTF-8 >/dev/null

echo "==> APT-Proxy (nur VPS)"
if [[ -n "$EPM_APT_PROXY" ]]; then
  cat > /etc/apt/apt.conf.d/95epm-proxy <<EOF
Acquire::http::Proxy "$EPM_APT_PROXY";
Acquire::https::Proxy "$EPM_APT_PROXY";
EOF
  export http_proxy="$EPM_APT_PROXY" https_proxy="$EPM_APT_PROXY"
else
  rm -f /etc/apt/apt.conf.d/95epm-proxy
fi

echo "==> needrestart: Dienste nur auflisten, nicht selbst neu starten"
mkdir -p /etc/needrestart/conf.d
echo "\$nrconf{restart} = 'l';" > /etc/needrestart/conf.d/90-epm.conf

echo "==> System aktualisieren"
apt-get update
apt-get -y full-upgrade
apt-get -y install ca-certificates curl gnupg vim htop rsync unzip jq tree \
  unattended-upgrades apt-listchanges age openssl

echo "==> Automatische Sicherheitsupdates, ohne Neustart"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
cat > /etc/apt/apt.conf.d/52epm-unattended <<'EOF'
// Nur Sicherheitsupdates von Ubuntu; Docker wird manuell aktualisiert
Unattended-Upgrade::Allowed-Origins {
        "${distro_id}:${distro_codename}-security";
        "${distro_id}ESMApps:${distro_codename}-apps-security";
        "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Package-Blacklist {
        "docker-ce"; "docker-ce-cli"; "containerd.io";
        "docker-buildx-plugin"; "docker-compose-plugin";
};
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF
systemctl enable --now unattended-upgrades

echo "==> Zeit (VPS: von der OPNsense)"
if [[ -n "$EPM_NTP_SERVER" ]]; then
  if [[ -d /etc/chrony/sources.d ]]; then
    for f in /etc/chrony/sources.d/*.sources; do
      [[ -e "$f" && "$f" != */epm.sources ]] && mv "$f" "$f.aus"
    done
    echo "server $EPM_NTP_SERVER iburst" > /etc/chrony/sources.d/epm.sources
    sed -i 's/^\(pool .*\)/# \1/' /etc/chrony/chrony.conf
    systemctl restart chrony
  else
    mkdir -p /etc/systemd/timesyncd.conf.d
    printf "[Time]\nNTP=%s\nFallbackNTP=\n" "$EPM_NTP_SERVER" > /etc/systemd/timesyncd.conf.d/epm.conf
    systemctl restart systemd-timesyncd
  fi
fi

echo "==> Journal begrenzen"
mkdir -p /etc/systemd/journald.conf.d
printf "[Journal]\nSystemMaxUse=1G\n" > /etc/systemd/journald.conf.d/90-epm.conf
systemctl restart systemd-journald

echo "==> Projektverzeichnis"
install -d -m 0755 "$EPM_BASE"

echo
echo "Fertig. Neustart empfohlen, falls ein neuer Kernel installiert wurde:"
[[ -f /var/run/reboot-required ]] && echo "  -> Neustart ERFORDERLICH: sudo reboot" || echo "  -> kein Neustart nötig"
