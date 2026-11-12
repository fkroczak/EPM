#!/bin/sh
# EPM – Startskript im Container ki-modell (KI (Experimentell), 14.10.2026).
#
# Startet llama-server (llama.cpp, nur CPU) mit dem freigegebenen Modell und hält es aktuell:
#   /steuerung/probe.env   vorübergehend ein Kandidat für einen Evaluationslauf (schreibt der KI-Dienst, nachts)
#   /steuerung/aktiv.env   das freigegebene Modell (schreibt das Backend beim Aktivieren/Zurückschalten)
#   KI_MODELL_DATEI …      Vorgabe aus .env, solange noch kein Modell aktiviert wurde
#   /steuerung/schlafen    tagsüber ohne Arbeit: llama-server beenden, Speicher freigeben
# Vor jedem Start wird die SHA-256 der Modelldatei geprüft (einmal je Datei und Containerstart).
# Kein Download, kein Netz: llama-server bekommt nur lokale Dateien (-m/--mmproj), der Container hängt nur am Netz
# „intern“ (internal: true).
set -u
MODELLE=/modelle
STEUERUNG=/steuerung
LEBT=/tmp/ki-modell-lebt
PID=""
AKTUELL=""

log() { echo "$(date '+%F %T') ki-modell: $*"; }

# Wert aus einer KEY=VALUE-Datei lesen – ohne sie auszuführen (keine Shell-Auswertung fremder Inhalte)
wert() { [ -f "$1" ] && sed -n "s/^$2=//p" "$1" | head -n1 | tr -cd 'A-Za-z0-9._#-' ; }

stoppen() {
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    log "beende llama-server ($PID)"
    kill "$PID" 2>/dev/null
    i=0
    while kill -0 "$PID" 2>/dev/null && [ $i -lt 30 ]; do sleep 1; i=$((i + 1)); done
    kill -9 "$PID" 2>/dev/null
  fi
  PID=""
}

trap 'stoppen; exit 0' TERM INT

pruefen() {  # Datei, erwartete SHA-256 → 0 wenn ok (Ergebnis je Datei gemerkt)
  datei="$1"; sha_soll="$2"
  [ -f "$MODELLE/$datei" ] || { log "Modelldatei fehlt: $datei"; return 1; }
  [ -z "$sha_soll" ] && { log "WARNUNG: keine Prüfsumme für $datei angegeben"; return 0; }
  [ -f "/tmp/geprueft-$sha_soll" ] && return 0
  log "prüfe SHA-256 von $datei …"
  ist=$(sha256sum "$MODELLE/$datei" | cut -d' ' -f1)
  if [ "$ist" != "$sha_soll" ]; then
    log "FEHLER: Prüfsumme von $datei stimmt nicht (ist $ist, soll $sha_soll) – Modell wird nicht geladen"
    return 1
  fi
  touch "/tmp/geprueft-$sha_soll"
}

starten() {  # Datei, Projektor, Alias
  set -- -m "$MODELLE/$1" --host 0.0.0.0 --port 8080 --alias "$3" \
    -t "${KI_THREADS:-4}" -c "${KI_KONTEXT:-16384}" --parallel "${KI_SLOTS:-2}" \
    -ngl 0 --jinja ${2:+--mmproj "$MODELLE/$2"}
  # mehrere Plätze (Chat neben einem Dokument): gemeinsamer Kontextspeicher statt je Platz ein Teil – kein
  # zusätzlicher Arbeitsspeicher, jede Anfrage kann weiter den ganzen Kontext nutzen
  [ "${KI_SLOTS:-2}" -gt 1 ] 2>/dev/null && set -- "$@" --kv-unified
  # weitere Schalter für llama-server aus .env (KI_LLAMA_ARGS), z. B. „--image-max-tokens 1024“
  # shellcheck disable=SC2086
  [ -n "${KI_LLAMA_ARGS:-}" ] && set -- "$@" $(printf %s "$KI_LLAMA_ARGS" | tr -cd 'A-Za-z0-9 ._=-')
  log "starte llama-server: $*"
  llama-server "$@" &
  PID=$!
}

while :; do
  touch "$LEBT"
  if [ -f "$STEUERUNG/probe.env" ]; then
    quelle="$STEUERUNG/probe.env"
  elif [ -f "$STEUERUNG/aktiv.env" ]; then
    quelle="$STEUERUNG/aktiv.env"
  else
    quelle=""
  fi
  if [ -n "$quelle" ]; then
    datei=$(wert "$quelle" DATEI); projektor=$(wert "$quelle" PROJEKTOR)
    sha=$(wert "$quelle" SHA256); alias=$(wert "$quelle" ALIAS)
  else
    datei=$(printf %s "${KI_MODELL_DATEI:-}" | tr -cd 'A-Za-z0-9._-')
    projektor=$(printf %s "${KI_PROJEKTOR_DATEI:-}" | tr -cd 'A-Za-z0-9._-')
    sha=$(printf %s "${KI_MODELL_SHA256:-}" | tr -cd '0-9a-f')
    alias="$datei#$(printf %s "$sha" | cut -c1-12)"
  fi
  if [ -f "$STEUERUNG/schlafen" ] && [ "$quelle" != "$STEUERUNG/probe.env" ]; then
    [ -n "$PID" ] && log "schlafen (tagsüber ohne Arbeit)"
    stoppen; AKTUELL=""
  elif [ -z "$datei" ]; then
    [ -z "$AKTUELL" ] || stoppen
    AKTUELL=""
    log "kein Modell eingerichtet (epm-ki einspielen / Administration › KI)"
    sleep 50
  else
    soll="$datei|$projektor|$sha"
    if [ "$soll" != "$AKTUELL" ] || [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
      stoppen
      if pruefen "$datei" "$sha" && { [ -z "$projektor" ] || [ -f "$MODELLE/$projektor" ]; }; then
        starten "$datei" "$projektor" "$alias"
        AKTUELL="$soll"
      else
        AKTUELL=""
        sleep 50
      fi
    fi
  fi
  sleep 10
done
