#!/usr/bin/env bash
# EPM – einmalig: Server mit dem privaten GitHub-Repo verbinden (nur lesend) und epm-update einrichten.
# Aufruf: sudo ./epm-git-einrichten.sh BESITZER/REPO
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }
REPO="${1:?Bitte Repo angeben, z. B. sudo ./epm-git-einrichten.sh deinname/epm}"
CODE=/srv/epm-code
SCHLUESSEL=/root/.ssh/epm_github

echo "==> Konfiguration nach /etc/epm/epm.conf"
install -d -m 0750 /etc/epm
if [[ ! -f /etc/epm/epm.conf ]]; then
  for q in "$(dirname "$0")/../rollout/epm.conf" "$HOME/epm-rollout/epm.conf" "/home/${SUDO_USER:-}/epm-rollout/epm.conf"; do
    [[ -f "$q" ]] && { install -m 0640 "$q" /etc/epm/epm.conf; echo "   übernommen aus $q"; break; }
  done
fi
[[ -f /etc/epm/epm.conf ]] || { echo "Keine epm.conf gefunden – bitte nach /etc/epm/epm.conf kopieren."; exit 1; }

echo "==> Git installieren"
apt-get -y -qq install git >/dev/null

echo "==> Lese-Schlüssel für GitHub (Deploy Key)"
install -d -m 0700 /root/.ssh
[[ -f "$SCHLUESSEL" ]] || ssh-keygen -q -t ed25519 -N "" -C "epm-server-$(hostname)" -f "$SCHLUESSEL"
grep -q "Host github-epm" /root/.ssh/config 2>/dev/null || cat >> /root/.ssh/config <<CONF
Host github-epm
    HostName github.com
    User git
    IdentityFile $SCHLUESSEL
    IdentitiesOnly yes
CONF
chmod 0600 /root/.ssh/config
ssh-keyscan -t ed25519 github.com 2>/dev/null >> /root/.ssh/known_hosts
sort -u -o /root/.ssh/known_hosts /root/.ssh/known_hosts

until git ls-remote "git@github-epm:$REPO.git" >/dev/null 2>&1; do
  echo
  echo "Diesen Schlüssel im Repo eintragen: github.com/$REPO → Settings → Deploy keys → Add deploy key"
  echo "(Titel z. B. epm-test, KEIN Haken bei „Allow write access“):"
  echo
  cat "$SCHLUESSEL.pub"
  echo
  read -r -p "Eingetragen? Dann Enter drücken … "
done
echo "   Zugriff auf $REPO klappt."

echo "==> Code nach $CODE"
if [[ -d "$CODE/.git" ]]; then
  git -C "$CODE" remote set-url origin "git@github-epm:$REPO.git"
else
  git clone --quiet "git@github-epm:$REPO.git" "$CODE"
fi
chmod 0750 "$CODE"
find "$CODE" -name '*.sh' -exec chmod +x {} +

install -m 0750 "$CODE/werkzeuge/epm-update.sh" /usr/local/sbin/epm-update
echo
echo "Fertig. Ab jetzt reicht:  sudo epm-update"
