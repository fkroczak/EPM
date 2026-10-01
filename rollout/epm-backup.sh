#!/usr/bin/env bash
# EPM – Backup: Datenbank (pg_dump) + Patientendokumente + Löschliste, 14 Tage aufbewahrt
# (endgültig gelöschte Dokumente stecken damit höchstens 14 Tage in älteren Sicherungen)
# Aufruf: sudo epm-backup   (läuft täglich per systemd-Timer)
set -euo pipefail
B=/srv/epm
ZIEL="$B/backup"
STAMP="$(date +%F_%H%M)"
cd "$B"

docker compose exec -T db pg_dump -U epm -d epm -Fc > "$ZIEL/epm-db_$STAMP.dump"
tar -C "$B/data" -czf "$ZIEL/epm-dokumente_$STAMP.tar.gz" dokumente
# Löschliste (Art. 17 DSGVO) getrennt sichern. Bei einer Wiederherstellung immer die NEUESTE Löschliste behalten
# bzw. nach data/loeschliste/ legen – das Backend löscht beim Start alles erneut, was die Sicherung zurückgebracht hat.
if [[ -f "$B/data/loeschliste/loeschliste.jsonl" ]]; then
  cp "$B/data/loeschliste/loeschliste.jsonl" "$ZIEL/epm-loeschliste_$STAMP.jsonl"
fi
sha256sum "$ZIEL/"*"_$STAMP."* > "$ZIEL/epm_$STAMP.sha256"
chmod 0600 "$ZIEL/"*"_$STAMP."*

find "$ZIEL" -maxdepth 1 -type f -mtime +14 -delete
echo "Backup $STAMP fertig: $(du -sh "$ZIEL" | cut -f1) im Backup-Ordner"
