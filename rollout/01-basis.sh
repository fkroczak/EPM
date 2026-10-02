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

echo "==> needrestart: Dienste nach Updates selbst neu starten – außer Docker und containerd („EPM-Server Aufbau“ A4)"
# Deren Neustart würde alle Container und damit EPM stoppen; das passiert nur im Wartungsfenster.
mkdir -p /etc/needrestart/conf.d
rm -f /etc/needrestart/conf.d/90-epm.conf
cat > /etc/needrestart/conf.d/50-epm.conf <<'NEEDRESTART'
$nrconf{restart} = 'a';
$nrconf{override_rc}{qr(^(docker|containerd)\.service$)} = 0;
NEEDRESTART

echo "==> System aktualisieren"
apt-get update
apt-get -y full-upgrade
apt-get -y install ca-certificates curl gnupg vim htop rsync unzip jq tree \
  unattended-upgrades apt-listchanges needrestart openssl rclone

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
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF
systemctl enable --now unattended-upgrades

echo "==> Zeit (VPS: von der OPNsense)"
timedatectl set-ntp true 2>/dev/null || true
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

echo "==> Journal dauerhaft speichern, höchstens 1 GB und 6 Monate"
mkdir -p /etc/systemd/journald.conf.d
printf "[Journal]\nStorage=persistent\nSystemMaxUse=1G\nMaxRetentionSec=6month\n" > /etc/systemd/journald.conf.d/90-epm.conf
systemctl restart systemd-journald

echo "==> Projektverzeichnis"
install -d -m 0755 "$EPM_BASE"
# Eigenes Volume für /srv („EPM-Server Aufbau“ A2): laufen Daten oder Sicherungen voll, bleibt das System lauffähig
if ! mountpoint -q /srv && ! mountpoint -q "$EPM_BASE" && [[ "$(df --output=target "$EPM_BASE" | tail -1)" == "/" ]]; then
  echo "WARNUNG: $EPM_BASE liegt auf der Root-Partition. Empfohlen: eigenes LVM-Volume für /srv."
fi

echo "==> Swap (2 GB, falls keiner da ist)"
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
swapon --show

echo
echo "Fertig. Neustart empfohlen, falls ein neuer Kernel installiert wurde:"
[[ -f /var/run/reboot-required ]] && echo "  -> Neustart ERFORDERLICH: sudo reboot" || echo "  -> kein Neustart nötig"
