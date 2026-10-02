#!/usr/bin/env bash
# EPM – Schritt 4a: Projektverzeichnis, Secrets, Zertifikat, Rauchtest-Stack
# Aufruf: sudo ./04-projekt.sh      (mehrfach ausführbar, überschreibt keine Secrets)
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }
cd "$(dirname "$0")"
KONF=/etc/epm/epm.conf; [[ -f "$KONF" ]] || KONF=./epm.conf
[[ -f "$KONF" ]] || { echo "Keine epm.conf gefunden (/etc/epm/epm.conf oder hier)."; exit 1; }
source "$KONF"
B="$EPM_BASE"

echo "==> Verzeichnisse unter $B"
install -d -m 0755 "$B" "$B/nginx" "$B/images"
install -d -m 0700 "$B/secrets" "$B/backup"
# Dokumente: Backend schreibt (UID $EPM_APP_UID), Nginx liest über Gruppe 101; setgid vererbt die Gruppe
install -d -m 0750 -o "$EPM_APP_UID" -g 101 "$B/data"
install -d -m 2750 -o "$EPM_APP_UID" -g 101 "$B/data/dokumente"
chown "$EPM_APP_UID:101" "$B/data" "$B/data/dokumente"; chmod 0750 "$B/data"; chmod 2750 "$B/data/dokumente"
# Löschliste (Art. 17 DSGVO): nur das Backend; bewusst nicht im Dokumentordner, damit eine Wiederherstellung sie nicht ersetzt
install -d -m 0700 -o "$EPM_APP_UID" -g 101 "$B/data/loeschliste"
chown "$EPM_APP_UID:101" "$B/data/loeschliste"; chmod 0700 "$B/data/loeschliste"
# Übernahme der Altdaten (Administration › Import): Hierhin kommen die Dokumente des Altsystems (PatData/<PatientenID>/…).
# Das Backend liest nur (Gruppe 101); setgid vererbt die Gruppe an alles, was hineinkopiert wird.
install -d -m 2750 -o root -g 101 "$B/data/import"
chown root:101 "$B/data/import"; chmod 2750 "$B/data/import"
install -d -m 0750 -o 101 -g 101 "$B/nginx/certs"
# Systemverwaltung (Administration › System): das Backend legt Aufträge ab, der Systemagent (root) schreibt den Status
install -d -m 0755 "$B/system" "$B/system/status" "$B/system/status/auftraege"
install -d -m 0770 -o "$EPM_APP_UID" -g 101 "$B/system/auftraege"
chown "$EPM_APP_UID:101" "$B/system/auftraege"; chmod 0770 "$B/system/auftraege"

echo "==> Projektdateien kopieren"
install -m 0644 projekt/compose.yaml projekt/compose.smoke.yaml "$B/"
install -m 0644 projekt/nginx/rauchtest.conf projekt/nginx/epm.conf "$B/nginx/"
if [[ ! -f "$B/backend.env" ]] || ! grep -q EPM_DJANGO_ADMIN "$B/backend.env"; then
  [[ -f "$B/backend.env" ]] && cp "$B/backend.env" "$B/backend.env.alt"
  sed -e "s/epm\.test/$EPM_WEB_NAME/g" projekt/backend.env.beispiel > "$B/backend.env"
  chmod 0600 "$B/backend.env"
fi
# Zugriff auch über die IP der Verwaltungskarte (das Zertifikat enthält sie): Django muss sie als Host und Herkunft kennen,
# sonst weist es jede Anfrage mit 400 (Host) bzw. 403 (CSRF) ab. Ergänzt nur, was fehlt; eigene Einträge bleiben.
if ! grep -qE "^DJANGO_ALLOWED_HOSTS=(.*,)?$EPM_MGMT_IP(,|$)" "$B/backend.env"; then
  sed -i -E "s/^(DJANGO_ALLOWED_HOSTS=.*)$/\1,$EPM_MGMT_IP/" "$B/backend.env"
fi
if ! grep -qE "^DJANGO_CSRF_TRUSTED_ORIGINS=(.*,)?https://$EPM_MGMT_IP(,|$)" "$B/backend.env"; then
  sed -i -E "s#^(DJANGO_CSRF_TRUSTED_ORIGINS=.*)\$#\1,https://$EPM_MGMT_IP#" "$B/backend.env"
fi

echo "==> Secrets (nur beim ersten Mal erzeugt)"
[[ -s "$B/secrets/db_password" ]]       || openssl rand -base64 32 | tr -d '\n=/+' > "$B/secrets/db_password"
[[ -s "$B/secrets/django_secret_key" ]] || openssl rand -base64 64 | tr -d '\n' > "$B/secrets/django_secret_key"
chmod 0644 "$B/secrets/"*       # Ordner ist 0700: auf dem Host nur für root lesbar

echo "==> TLS-Zertifikat für $EPM_WEB_NAME (selbst signiert, 5 Jahre)"
if [[ ! -s "$B/nginx/certs/epm.crt" ]]; then
  openssl req -x509 -newkey rsa:3072 -sha256 -days 1825 -nodes \
    -keyout "$B/nginx/certs/epm.key" -out "$B/nginx/certs/epm.crt" \
    -subj "/CN=$EPM_WEB_NAME/O=EPM" \
    -addext "subjectAltName=DNS:$EPM_WEB_NAME,IP:$EPM_MGMT_IP" \
    -addext "extendedKeyUsage=serverAuth" 2>/dev/null
fi
chown 101:101 "$B/nginx/certs/"*; chmod 0400 "$B/nginx/certs/epm.key"; chmod 0444 "$B/nginx/certs/epm.crt"

echo "==> .env (Compose-Variablen)"
if [[ ! -f "$B/.env" ]]; then
  cat > "$B/.env" <<EOF
# Welche Compose-Datei aktiv ist: Rauchtest, bis Backend/Frontend da sind
COMPOSE_FILE=compose.smoke.yaml
EPM_BIND_IP=$EPM_MGMT_IP
EPM_VERSION=0.1.0
EOF
  chmod 0600 "$B/.env"
fi

echo "==> Backup-Skript und täglicher Timer (02:30)"
install -m 0750 epm-backup.sh /usr/local/sbin/epm-backup
cat > /etc/systemd/system/epm-backup.service <<EOF
[Unit]
Description=EPM Backup (Datenbank + Dokumente)
After=docker.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/epm-backup
EOF
cat > /etc/systemd/system/epm-backup.timer <<'EOF'
[Unit]
Description=EPM Backup täglich
[Timer]
OnCalendar=*-*-* 02:30
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now epm-backup.timer

echo "==> Systemagent (Administration › System: Auslastung, Updates, Neustart aus der Oberfläche)"
install -m 0750 epm-systemagent.py /usr/local/sbin/epm-systemagent
cat > /etc/systemd/system/epm-systemstatus.service <<'EOF'
[Unit]
Description=EPM Systemstatus messen (Auslastung, Updates, Container, Sicherung)
After=docker.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/epm-systemagent status
Nice=10
EOF
cat > /etc/systemd/system/epm-systemstatus.timer <<'EOF'
[Unit]
Description=EPM Systemstatus jede Minute
[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=5s
[Install]
WantedBy=timers.target
EOF
cat > /etc/systemd/system/epm-systemagent.service <<'EOF'
[Unit]
Description=EPM Systemagent: Aufträge aus der Oberfläche ausführen (feste Liste)
After=docker.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/epm-systemagent auftraege
TimeoutStartSec=6h
EOF
cat > /etc/systemd/system/epm-systemagent.path <<EOF
[Unit]
Description=EPM Systemagent: auf neue Aufträge warten
[Path]
PathExistsGlob=$B/system/auftraege/*.json
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now epm-systemstatus.timer epm-systemagent.path

echo
tree -a -L 2 "$B" 2>/dev/null || ls -la "$B"
echo
echo "Fertig. Weiter mit:  cd $B && sudo docker compose up -d"
