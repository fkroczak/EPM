#!/usr/bin/env bash
# EPM – Backup: Datenbank (pg_dump) + Patientendokumente + Löschliste, 30 Tage aufbewahrt
# (endgültig gelöschte Akten und Dokumente stecken damit höchstens 30 Tage in älteren Sicherungen)
# Aufruf: sudo epm-backup   (läuft täglich per systemd-Timer)
#
# Aufbewahrung: EPM_BACKUP_TAGE (Standard 30; Festlegung 02.10.2026: Sicherungen werden 30 Tage vorgehalten).
#
# Verschlüsselung (empfohlen, sobald Sicherungen den Server verlassen – NAS, Nextcloud; Art. 32 DSGVO):
#   1. einmalig auf einem ANDEREN Rechner:  age-keygen -o epm-backup-schluessel.txt
#      Die Datei ist der private Schlüssel: sicher verwahren (ohne ihn ist keine Wiederherstellung möglich), nicht auf dem Server.
#   2. die Zeile „# public key: age1…“ daraus (nur der Teil age1…) nach /srv/epm/secrets/backup-empfaenger.txt
#   3. sudo apt install age
# Gibt es die Datei und das Programm, werden Datenbank und Dokumente verschlüsselt (Endung .age). Sonst bleibt alles
# wie bisher unverschlüsselt – mit einem Hinweis in der Ausgabe.
# Entschlüsseln:  age -d -i epm-backup-schluessel.txt -o epm-db_….dump epm-db_….dump.age
set -euo pipefail
B="${EPM_BASIS:-/srv/epm}"
ZIEL="$B/backup"
TAGE="${EPM_BACKUP_TAGE:-30}"
EMPFAENGER="$B/secrets/backup-empfaenger.txt"
STAMP="$(date +%F_%H%M)"
cd "$B"

VERSCHLUESSELN=0
if [[ -s "$EMPFAENGER" ]]; then
  if command -v age >/dev/null 2>&1; then
    VERSCHLUESSELN=1
  else
    echo "WARNUNG: $EMPFAENGER ist vorhanden, aber das Programm „age“ fehlt (sudo apt install age) – Sicherung unverschlüsselt." >&2
  fi
fi

# schreibt die Standardeingabe nach $1 (verschlüsselt nach $1.age, wenn eingerichtet); unvollständige Dateien bleiben nicht liegen
sichern() {
  local ziel="$1"
  if [[ "$VERSCHLUESSELN" == 1 ]]; then
    ziel="$ziel.age"
    age -R "$EMPFAENGER" -o "$ziel.teil"
  else
    cat > "$ziel.teil"
  fi
  mv "$ziel.teil" "$ziel"
}
trap 'rm -f "$ZIEL"/*.teil' EXIT

docker compose exec -T db pg_dump -U epm -d epm -Fc | sichern "$ZIEL/epm-db_$STAMP.dump"
tar -C "$B/data" -czf - dokumente | sichern "$ZIEL/epm-dokumente_$STAMP.tar.gz"
# Löschliste (Art. 17 DSGVO) getrennt sichern – unverschlüsselt, sie enthält keine Namen und keine Inhalte. Bei einer
# Wiederherstellung immer die NEUESTE Löschliste behalten bzw. nach data/loeschliste/ legen – das Backend löscht beim
# Start alle Akten und Dokumente erneut, die die Sicherung zurückgebracht hat.
if [[ -f "$B/data/loeschliste/loeschliste.jsonl" ]]; then
  cp "$B/data/loeschliste/loeschliste.jsonl" "$ZIEL/epm-loeschliste_$STAMP.jsonl"
fi
sha256sum "$ZIEL/"*"_$STAMP."* > "$ZIEL/epm_$STAMP.sha256"
chmod 0600 "$ZIEL/"*"_$STAMP."*

find "$ZIEL" -maxdepth 1 -type f -mtime +"$TAGE" -delete
if [[ "$VERSCHLUESSELN" == 1 ]]; then ART="verschlüsselt"; else ART="unverschlüsselt (Verschlüsselung einrichten: siehe Kopf von epm-backup)"; fi
echo "Backup $STAMP fertig, $ART: $(du -sh "$ZIEL" | cut -f1) im Backup-Ordner, Aufbewahrung $TAGE Tage"
