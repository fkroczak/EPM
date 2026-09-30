#!/usr/bin/env bash
# EPM – Backup: Datenbank (pg_dump) + Patientendokumente, 14 Tage aufbewahrt
# Aufruf: sudo epm-backup   (läuft täglich per systemd-Timer)
set -euo pipefail
B=/srv/epm
ZIEL="$B/backup"
STAMP="$(date +%F_%H%M)"
cd "$B"

docker compose exec -T db pg_dump -U epm -d epm -Fc > "$ZIEL/epm-db_$STAMP.dump"
tar -C "$B/data" -czf "$ZIEL/epm-dokumente_$STAMP.tar.gz" dokumente
sha256sum "$ZIEL/"*"_$STAMP."* > "$ZIEL/epm_$STAMP.sha256"
chmod 0600 "$ZIEL/"*"_$STAMP."*

find "$ZIEL" -maxdepth 1 -type f -mtime +14 -delete
echo "Backup $STAMP fertig: $(du -sh "$ZIEL" | cut -f1) im Backup-Ordner"
