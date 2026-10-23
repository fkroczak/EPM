#!/usr/bin/env bash
# Modelle der zweiten Texterkennung (PP-OCRv5, UVDoc) und das Sprachmodell für Diktate offline vorbereiten und auf der Test-VM einspielen.
#
# Hintergrund: Beim Bau des Backend-Images werden die Modelle sonst von huggingface.co geladen. Hat der Server dafür
# keine Freigabe im Proxy, entsteht das Image trotzdem – die Erkennung arbeitet dann nur mit Tesseract.
# Mit diesem Skript lädt ein beliebiger Rechner mit Internet die Dateien (geprüft gegen die Prüfsummen in
# backend/scans/modelle/modelle.json), und die Test-VM baut sie beim nächsten Update ein.
#
#   1. Auf einem Rechner mit Internet (Linux, macOS, WSL; unter Windows ohne WSL: ocr-modelle.ps1):
#        werkzeuge/ocr-modelle.sh vorbereiten                 → epm-ocr-modelle-<Revision>.tar (≈ 680 MB mit dem Sprachmodell für Diktate)
#   2. Datei auf die Test-VM kopieren:
#        scp epm-ocr-modelle-*.tar epmadmin@TEST-VM:~/
#   3. Auf der Test-VM:
#        sudo epm-ocr-modelle einspielen ~/epm-ocr-modelle-<Revision>.tar
#        sudo epm-update                                       (baut das Image mit den Modellen neu)
#      Stand prüfen:  sudo epm-ocr-modelle status
#
# Der VPS braucht nichts davon: Er bekommt fertige Pakete von der Test-VM, die Modelle stecken im Image.
set -euo pipefail

HIER="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
# Im Repo: werkzeuge/ → ../backend/scans/modelle; auf dem Server installiert: Code unter /srv/epm-code
if [[ -f "$HIER/../backend/scans/modelle/modelle.json" ]]; then
  MODELLE="$(cd "$HIER/../backend/scans/modelle" && pwd)"
else
  MODELLE=/srv/epm-code/backend/scans/modelle
fi
LISTE="$MODELLE/modelle.json"
HOLEN="$MODELLE/holen.py"
KONF=/etc/epm/epm.conf
VORRAT_SERVER="/srv/epm/ocr-modelle"
if [[ -f "$KONF" ]]; then
  # shellcheck disable=SC1090
  source "$KONF"
  VORRAT_SERVER="${EPM_BASE:-/srv/epm}/ocr-modelle"
fi

hilfe() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
[[ -f "$LISTE" && -f "$HOLEN" ]] || { echo "Nicht gefunden: $LISTE bzw. $HOLEN"; exit 1; }
command -v python3 >/dev/null || { echo "python3 fehlt (unter Windows: werkzeuge/ocr-modelle.ps1)."; exit 1; }
revision() { python3 -c 'import json,sys,re; q=json.load(open(sys.argv[1]))["quelle"]; print(re.findall(r"[0-9a-f]{40}", q)[0][:12])' "$LISTE"; }

vorbereiten() {
  local ziel="${1:-$PWD/epm-ocr-modelle-$(revision).tar}"
  local tmp; tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' RETURN
  echo "==> Modelle laden und prüfen (Quelle: $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["quelle"])' "$LISTE"))"
  python3 "$HOLEN" "$tmp/dateien"
  cp "$LISTE" "$tmp/modelle.json"
  tar -C "$tmp" -cf "$ziel" modelle.json dateien
  echo
  echo "Fertig: $ziel ($(du -h "$ziel" | cut -f1))"
  echo "Weiter:  scp \"$ziel\" epmadmin@TEST-VM:~/   und dort   sudo epm-ocr-modelle einspielen ~/$(basename "$ziel")"
}

einspielen() {
  local datei="${1:-}"
  [[ -n "$datei" && -f "$datei" ]] || { echo "Bitte die vorbereitete Datei angeben: sudo epm-ocr-modelle einspielen DATEI.tar"; exit 1; }
  [[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }
  local tmp; tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' RETURN
  tar -C "$tmp" -xf "$datei"
  [[ -d "$tmp/dateien" ]] || { echo "Die Datei enthält keine Modelle (Ordner „dateien“ fehlt)."; exit 1; }
  if ! cmp -s "$tmp/modelle.json" "$LISTE"; then
    echo "Hinweis: Die Datei wurde für eine andere Modell-Liste vorbereitet; geprüft wird gegen die aktuelle im Code."
  fi
  echo "==> Prüfen gegen $LISTE"
  if ! python3 "$HOLEN" --nur-pruefen "$tmp/dateien"; then
    echo "ABBRUCH: Dateien fehlen oder Prüfsummen stimmen nicht – bitte mit dem aktuellen Code neu vorbereiten."
    exit 1
  fi
  install -d -m 0755 "$VORRAT_SERVER"
  cp -a "$tmp/dateien/." "$VORRAT_SERVER/"
  chmod -R a+rX "$VORRAT_SERVER"
  echo
  echo "Eingespielt nach $VORRAT_SERVER. Jetzt:  sudo epm-update   (baut das Backend-Image mit den Modellen neu)"
}

status() {
  echo "Modell-Liste:  $LISTE"
  echo "Vorrat:        $VORRAT_SERVER"
  if [[ -d "$VORRAT_SERVER" ]] && python3 "$HOLEN" --nur-pruefen "$VORRAT_SERVER" >/dev/null 2>&1; then
    echo "               vollständig und geprüft"
  else
    echo "               fehlt oder unvollständig"
  fi
  if command -v docker >/dev/null && [[ -f "${EPM_BASE:-/srv/epm}/.env" ]]; then
    local tag; tag="$(sed -n 's/^EPM_VERSION=//p' "${EPM_BASE:-/srv/epm}/.env" | head -1)"
    if [[ -n "$tag" ]]; then
      if docker run --rm --entrypoint test "epm-backend:$tag" -f /opt/ocr-modelle/detection/v5/det.onnx 2>/dev/null; then
        echo "Image:         epm-backend:$tag enthält die Modelle (Erkennung mit Tesseract + PP-OCRv5)"
      else
        echo "Image:         epm-backend:$tag ohne Modelle (Erkennung nur mit Tesseract)"
      fi
    fi
  fi
}

case "${1:-}" in
  vorbereiten) shift; vorbereiten "$@" ;;
  einspielen)  shift; einspielen "$@" ;;
  status)      status ;;
  -h|--hilfe|"") hilfe 0 ;;
  *) echo "Unbekannt: $1"; hilfe 1 ;;
esac
