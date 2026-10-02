#!/usr/bin/env bash
# EPM – Sicherung: Datenbank (pg_dump) + Patientendokumente + Löschliste, 30 Tage aufbewahrt
# (endgültig gelöschte Akten und Dokumente stecken damit höchstens 30 Tage in älteren Sicherungen)
#
#   sudo epm-backup [--art nachts|von_hand|vor_update|vor_aenderung|vor_wiederherstellung] [--von BENUTZER]
#
# Läuft täglich um 02:00 per systemd-Timer (--art nachts), „Jetzt sichern“ und die Sicherung vor Updates, Neustart und
# Wiederherstellen stößt der Systemagent an (Administration › Backup bzw. › System).
#
# Aufbewahrung: EPM_BACKUP_TAGE (Standard 30; Festlegung 02.10.2026: Sicherungen werden 30 Tage vorgehalten).
#
# Verschlüsselung (Festlegung 02.10.2026: symmetrisch mit einem Passwort, das die Administration in der Oberfläche
# festlegt; Art. 32 DSGVO): Das Passwort liegt nur für root lesbar in /etc/epm/sicherung/passwort-<Nr.>, die aktuelle
# Nummer in /etc/epm/sicherung/aktuell (beides schreibt der Systemagent). Ist eines gesetzt, werden Datenbank, Dokumente
# und Löschliste mit GnuPG verschlüsselt (OpenPGP, AES-256, Endung .gpg). Sonst bleibt alles unverschlüsselt – mit
# Hinweis in der Ausgabe – und wird auch nicht übertragen.
# Von Hand entschlüsseln (Passwort vom Passwortblatt):   gpg -d -o epm-db_….dump epm-db_….dump.gpg
#
# Je Sicherung entstehen:  epm-db_<Stempel>.dump[.gpg], epm-dokumente_<Stempel>.tar.gz[.gpg],
#   epm-loeschliste_<Stempel>.jsonl[.gpg] (falls vorhanden), epm_<Stempel>.sha256 (Prüfsummen, relative Namen) und
#   epm_<Stempel>.json (Zeitpunkt, Art, ausgelöst von, Passwort-Nr., Dateien – ohne Patientendaten).
set -euo pipefail
B="${EPM_BASIS:-/srv/epm}"
ZIEL="$B/backup"
TAGE="${EPM_BACKUP_TAGE:-30}"
KONF="${EPM_SICHERUNG_KONF:-/etc/epm/sicherung}"
PROJEKT="${EPM_COMPOSE_PROJEKT:-}"
ART="nachts"
VON=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --art) ART="${2:-}"; shift ;;
    --von) VON="${2:-}"; shift ;;
    *) sed -n '2,9p' "$0"; exit 2 ;;
  esac
  shift
done
[[ "$ART" =~ ^(nachts|von_hand|vor_update|vor_aenderung|vor_wiederherstellung)$ ]] || { echo "Unbekannte Art: $ART" >&2; exit 2; }
[[ -z "$VON" || "$VON" =~ ^[A-Za-z0-9_.@+-]{1,150}$ ]] || { echo "Ungültiger Benutzername." >&2; exit 2; }
[[ "$TAGE" =~ ^[1-9][0-9]*$ ]] || { echo "EPM_BACKUP_TAGE muss eine Zahl ab 1 sein (ist: $TAGE)." >&2; exit 2; }
STAMP="$(date +%F_%H%M%S)"
BEGINN="$(date +%s)"
cd "$B"
install -d -m 0700 "$ZIEL"

# nie zwei Läufe zugleich (der zweite würde die halbfertigen Dateien des ersten wegräumen)
exec 9>"$ZIEL/.epm-backup.sperre"
flock -n 9 || { echo "epm-backup läuft bereits." >&2; exit 1; }

compose() { if [[ -n "$PROJEKT" ]]; then docker compose -p "$PROJEKT" "$@"; else docker compose "$@"; fi; }

VERSCHLUESSELN=0
NR=""
if [[ -s "$KONF/aktuell" ]]; then
  NR="$(tr -dc '0-9' < "$KONF/aktuell")"
  if [[ -n "$NR" && -s "$KONF/passwort-$NR" ]]; then
    if command -v gpg >/dev/null 2>&1; then
      VERSCHLUESSELN=1
    else
      echo "WARNUNG: Ein Sicherungs-Passwort ist festgelegt, aber GnuPG fehlt (sudo apt install gnupg) – Sicherung unverschlüsselt." >&2
      NR=""
    fi
  else
    echo "WARNUNG: $KONF/aktuell nennt ein Passwort, das fehlt – Sicherung unverschlüsselt." >&2
    NR=""
  fi
fi

# GnuPG ohne Schlüsselbund und ohne zwischengespeichertes Passwort, in einem eigenen Ordner, der danach gelöscht wird
GNUPGHOME="$(mktemp -d)"
export GNUPGHOME
aufraeumen() {
  gpgconf --homedir "$GNUPGHOME" --kill all >/dev/null 2>&1 || true
  rm -rf "$GNUPGHOME"
  rm -f "$ZIEL"/epm-*_"$STAMP".*.teil
}
trap aufraeumen EXIT

# sichern <Zieldatei> <Befehl …>: schreibt die Ausgabe des Befehls nach <Zieldatei> (verschlüsselt nach
# <Zieldatei>.gpg, wenn ein Passwort festgelegt ist). Die Datei bekommt ihren Namen erst, wenn der Befehl UND das
# Schreiben gelungen sind – scheitert pg_dump oder tar, bricht das Skript ab und es bleibt keine halbe Sicherung liegen.
DATEIEN=()
sichern() {
  local ziel="$1"; shift
  if [[ "$VERSCHLUESSELN" == 1 ]]; then
    ziel="$ziel.gpg"
    "$@" | gpg --batch --yes --quiet --no-symkey-cache --pinentry-mode loopback \
      --passphrase-file "$KONF/passwort-$NR" --symmetric --cipher-algo AES256 \
      --s2k-mode 3 --s2k-digest-algo SHA512 --s2k-count 65011712 --compress-algo none -o "$ziel.teil"
  else
    "$@" > "$ziel.teil"
  fi
  mv "$ziel.teil" "$ziel"
  DATEIEN+=("$(basename "$ziel")")
}

sichern "$ZIEL/epm-db_$STAMP.dump" compose exec -T db pg_dump -U epm -d epm -Fc
sichern "$ZIEL/epm-dokumente_$STAMP.tar.gz" tar -C "$B/data" -czf - dokumente
# Löschliste (Art. 17 DSGVO) getrennt sichern. Sie nennt Patientennummern, Zeitpunkte und den eingetragenen Grund
# der Löschung, keine Namen (die Oberfläche bittet, keine hineinzuschreiben). Bei einer Wiederherstellung bleibt die
# aktuelle Löschliste (data/loeschliste/) unangetastet – das Backend löscht beim Start alle Akten und Dokumente erneut,
# die die Sicherung zurückgebracht hat. Auf einem neuen Server die NEUESTE Löschliste dorthin legen; niemals die
# Löschliste eines anderen Systems einspielen.
if [[ -f "$B/data/loeschliste/loeschliste.jsonl" ]]; then
  sichern "$ZIEL/epm-loeschliste_$STAMP.jsonl" cat "$B/data/loeschliste/loeschliste.jsonl"
fi
(cd "$ZIEL" && sha256sum "${DATEIEN[@]}" > "epm_$STAMP.sha256")

# Angaben zur Sicherung (für die Oberfläche, die Übertragung und das Wiederherstellen; keine Patientendaten)
DATEIEN_JSON="$(cd "$ZIEL" && for d in "${DATEIEN[@]}"; do
  printf '{"name":"%s","groesse":%s,"sha256":"%s"}\n' "$d" "$(stat -c %s "$d")" "$(grep -F "  $d" "epm_$STAMP.sha256" | cut -d' ' -f1)"
done | jq -s .)"
jq -n --arg stempel "$STAMP" --arg zeitpunkt "$(date --iso-8601=seconds)" --arg art "$ART" --arg von "$VON" \
  --argjson verschluesselt "$([[ "$VERSCHLUESSELN" == 1 ]] && echo true || echo false)" \
  --arg nr "$NR" --argjson dateien "$DATEIEN_JSON" --arg version "${EPM_VERSION:-$(grep -s '^EPM_VERSION=' "$B/.env" | cut -d= -f2)}" \
  --argjson dauer "$(( $(date +%s) - BEGINN ))" \
  '{version: 1, stempel: $stempel, zeitpunkt: $zeitpunkt, art: $art, ausgeloest_von: $von, verschluesselt: $verschluesselt,
    verfahren: (if $verschluesselt then "gpg-symmetrisch" else "" end), passwort_nr: (if $nr == "" then null else ($nr | tonumber) end),
    epm_version: $version, dauer_s: $dauer, dateien: $dateien}' > "$ZIEL/epm_$STAMP.json.teil"
mv "$ZIEL/epm_$STAMP.json.teil" "$ZIEL/epm_$STAMP.json"
chmod 0600 "$ZIEL/"epm*"_$STAMP."*

# Ablauf: nur die eigenen Dateien, und alles ab dem Alter von $TAGE Tagen (find rundet das Alter auf ganze Tage ab,
# „-mtime +N“ heißt „älter als N+1 Tage“ – deshalb N = TAGE − 1)
find "$ZIEL" -maxdepth 1 -type f \( -name 'epm-*' -o -name 'epm_*.sha256' -o -name 'epm_*.json' \) -mtime +"$((TAGE - 1))" -delete
if [[ "$VERSCHLUESSELN" == 1 ]]; then
  SCHUTZ="verschlüsselt (Passwort Nr. $NR)"
else
  SCHUTZ="UNVERSCHLÜSSELT – Sicherungs-Passwort unter Administration › Backup festlegen"
fi
echo "Sicherung $STAMP fertig, $SCHUTZ: $(du -sh "$ZIEL" | cut -f1) im Backup-Ordner, Aufbewahrung $TAGE Tage"
