#!/usr/bin/env bash
# EPM – Schritt 3: Härtung (SSH, Firewall, Fail2ban, Kernel)
# Aufruf: sudo ./03-security.sh
# VORHER: SSH-Schlüssel vom PC hinterlegt und Login mit Schlüssel getestet!
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }
cd "$(dirname "$0")"
KONF=/etc/epm/epm.conf; [[ -f "$KONF" ]] || KONF=./epm.conf
[[ -f "$KONF" ]] || { echo "Keine epm.conf gefunden (/etc/epm/epm.conf oder hier)."; exit 1; }
source "$KONF"
export DEBIAN_FRONTEND=noninteractive
[[ -n "$EPM_APT_PROXY" ]] && export http_proxy="$EPM_APT_PROXY" https_proxy="$EPM_APT_PROXY"

ADMIN_HOME="$(getent passwd "$EPM_ADMIN_USER" | cut -d: -f6)"
if [[ ! -s "$ADMIN_HOME/.ssh/authorized_keys" ]]; then
  echo "ABBRUCH: $ADMIN_HOME/.ssh/authorized_keys fehlt oder ist leer."
  echo "Erst den SSH-Schlüssel vom PC hinterlegen (Teil B), sonst sperrst du dich aus."
  exit 1
fi
ip -br addr show "$EPM_MGMT_IF" >/dev/null 2>&1 || { echo "ABBRUCH: Netzwerkkarte $EPM_MGMT_IF nicht gefunden."; exit 1; }

apt-get update
apt-get -y install ufw fail2ban

echo "==> SSH: nur Schlüssel, kein root, nur $EPM_ADMIN_USER"
cat > /etc/ssh/sshd_config.d/10-epm.conf <<EOF
Port $EPM_SSH_PORT
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
AllowUsers $EPM_ADMIN_USER
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
sshd -t
systemctl restart ssh

echo "==> Firewall (UFW): eingehend nur SSH und HTTPS aus $EPM_MGMT_NET über $EPM_MGMT_IF"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow in on "$EPM_MGMT_IF" from "$EPM_MGMT_NET" to any port "$EPM_SSH_PORT" proto tcp comment 'SSH'
ufw allow in on "$EPM_MGMT_IF" from "$EPM_MGMT_NET" to any port 443 proto tcp comment 'HTTPS EPM'
ufw logging low
ufw --force enable
# Wichtig: Docker umgeht UFW bei veröffentlichten Ports. Deshalb bindet die
# Compose-Datei Port 443 ausschließlich an $EPM_MGMT_IP.

echo "==> Fail2ban für SSH"
cat > /etc/fail2ban/jail.d/epm.local <<'EOF'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5
backend  = systemd

[sshd]
enabled = true
EOF
systemctl enable fail2ban
systemctl restart fail2ban

echo "==> Kernel-Einstellungen"
cat > /etc/sysctl.d/90-epm.conf <<'EOF'
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.tcp_syncookies = 1
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
kernel.unprivileged_bpf_disabled = 1
net.core.bpf_jit_harden = 2
EOF
sysctl --system >/dev/null

echo "==> root-Passwort sperren, AppArmor prüfen"
passwd -l root >/dev/null
aa-status --enabled && echo "AppArmor aktiv" || echo "WARNUNG: AppArmor nicht aktiv"

echo
ufw status verbose
echo
echo "Fertig. JETZT in einem ZWEITEN Fenster testen: ssh $EPM_ADMIN_USER@$EPM_MGMT_IP"
echo "Erst wenn das klappt, dieses Fenster schließen."
