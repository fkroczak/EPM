#!/usr/bin/env bash
# EPM – Versionsnummer berechnen (Festlegung 11.10.2026: „bitte automatisch hochzählen“).
#
#   werkzeuge/version.sh [ORDNER]     gibt z. B. 2.0.3 aus
#
# Die Datei VERSION enthält den Grundstand X.Y.Z. Die letzte Stelle zählt automatisch hoch: um die Zahl der Änderungen
# auf main (jeder Merge bzw. Push, erste Elternlinie) seit dem Commit, der VERSION zuletzt geändert hat. Beispiel:
# VERSION 2.0.0, danach drei Merges → 2.0.3. Neue Funktionen bzw. eine neue Hauptversion: VERSION von Hand auf 2.1.0
# bzw. 3.0.0 setzen – die Zählung beginnt dann wieder bei 0. Ohne Git (Paket auf dem VPS, Notfallpaket) steht die
# fertige Nummer schon in VERSION und wird unverändert ausgegeben.
set -euo pipefail
cd "${1:-$(dirname "$0")/..}"
basis="$(tr -d " \t\r\n" < VERSION)"
[[ "$basis" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || { echo "VERSION ungültig: „$basis“ (erwartet X.Y.Z)" >&2; exit 1; }
haupt="${BASH_REMATCH[1]}"; neben="${BASH_REMATCH[2]}"; stand="${BASH_REMATCH[3]}"
n=0
if git rev-parse --git-dir >/dev/null 2>&1; then
  if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
    echo "Hinweis: flacher Klon – die Versionsnummer zählt ohne vollständige Historie nicht hoch ($basis)" >&2
  else
    seit="$(git log -1 --first-parent --format=%H -- VERSION)"
    [[ -n "$seit" ]] && n="$(git rev-list --count --first-parent "$seit..HEAD")"
  fi
elif [[ -e .git ]]; then
  echo "Hinweis: Git kann $PWD nicht lesen – Versionsnummer ohne Zählung ($basis)" >&2
fi
echo "$haupt.$neben.$((stand + n))"
