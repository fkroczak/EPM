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
# Gibt es die Datei und das Programm, werden Datenbank, Dokumente und Löschliste verschlüsselt (Endung .age). Sonst
# bleibt alles wie bisher unverschlüsselt – mit einem Hinweis in der Ausgabe.
# Entschlüsseln:  age -d -i epm-backup-schluessel.txt -o epm-db_….dump epm-db_….dump.age
set -euo pipefail
B="${EPM_BASIS:-/srv/epm}"
ZIEL="$B/backup"
TAGE="${EPM_BACKUP_TAGE:-30}"
EMPFAENGER="$B/secrets/backup-empfaenger.txt"
STAMP="$(date +%F_%H%M)"
[[ "$TAGE" =~ ^[1-9][0-9]*$ ]] || { echo "EPM_BACKUP_TAGE muss eine Zahl ab 1 sein (ist: $TAGE)." >&2; exit 2; }
cd "$B"

# nie zwei Läufe zugleich (der zweite würde die halbfertigen Dateien des ersten wegräumen)
exec 9>"$ZIEL/.epm-backup.sperre"
flock -n 9 || { echo "epm-backup läuft bereits." >&2; exit 1; }

VERSCHLUESSELN=0
if [[ -s "$EMPFAENGER" ]]; then
  if command -v age >/dev/null 2>&1; then
    VERSCHLUESSELN=1
  else
    echo "WARNUNG: $EMPFAENGER ist vorhanden, aber das Programm „age“ fehlt (sudo apt install age) – Sicherung unverschlüsselt." >&2
  fi
fi

# sichern <Zieldatei> <Befehl …>: schreibt die Ausgabe des Befehls nach <Zieldatei> (verschlüsselt nach
# <Zieldatei>.age, wenn eingerichtet). Die Datei bekommt ihren Namen erst, wenn der Befehl UND das Schreiben
# gelungen sind – scheitert pg_dump oder tar, bricht das Skript ab und es bleibt keine halbe Sicherung liegen.
sichern() {
  local ziel="$1"; shift
  if [[ "$VERSCHLUESSELN" == 1 ]]; then
    ziel="$ziel.age"
    "$@" | age -R "$EMPFAENGER" -o "$ziel.teil"
  else
    "$@" > "$ziel.teil"
  fi
  mv "$ziel.teil" "$ziel"
}
trap 'rm -f "$ZIEL"/epm-*_"$STAMP".*.teil' EXIT

sichern "$ZIEL/epm-db_$STAMP.dump" docker compose exec -T db pg_dump -U epm -d epm -Fc
sichern "$ZIEL/epm-dokumente_$STAMP.tar.gz" tar -C "$B/data" -czf - dokumente
# Löschliste (Art. 17 DSGVO) getrennt sichern. Sie nennt Patientennummern, Zeitpunkte und den eingetragenen Grund
# der Löschung, keine Namen (die Oberfläche bittet, keine hineinzuschreiben). Bei einer Wiederherstellung immer die
# NEUESTE Löschliste behalten bzw. nach data/loeschliste/ legen – das Backend löscht beim Start alle Akten und
# Dokumente erneut, die die Sicherung zurückgebracht hat. Niemals die Löschliste eines anderen Systems einspielen.
if [[ -f "$B/data/loeschliste/loeschliste.jsonl" ]]; then
  sichern "$ZIEL/epm-loeschliste_$STAMP.jsonl" cat "$B/data/loeschliste/loeschliste.jsonl"
fi
sha256sum "$ZIEL/"epm-*"_$STAMP."* > "$ZIEL/epm_$STAMP.sha256"
chmod 0600 "$ZIEL/"epm*"_$STAMP."*

# Ablauf: nur die eigenen Dateien, und alles ab dem Alter von $TAGE Tagen (find rundet das Alter auf ganze Tage ab,
# „-mtime +N“ heißt „älter als N+1 Tage“ – deshalb N = TAGE − 1)
find "$ZIEL" -maxdepth 1 -type f \( -name 'epm-*' -o -name 'epm_*.sha256' \) -mtime +"$((TAGE - 1))" -delete
if [[ "$VERSCHLUESSELN" == 1 ]]; then ART="verschlüsselt"; else ART="unverschlüsselt (Verschlüsselung einrichten: siehe Kopf von epm-backup)"; fi
echo "Backup $STAMP fertig, $ART: $(du -sh "$ZIEL" | cut -f1) im Backup-Ordner, Aufbewahrung $TAGE Tage"
