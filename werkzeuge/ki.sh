#!/usr/bin/env bash
# EPM – KI (Experimentell, 14.10.2026): Modelle offline vorbereiten, einspielen, KI einrichten und verwalten.
# Auf dem Server installiert als `epm-ki` (epm-update). Plan: docs/KI-ERWEITERUNG-PLAN-2026-10-14.md,
# Betrieb: docs/KI-BETRIEB.md.
#
#   1. Auf einem Rechner mit Internet (Linux, macOS, WSL; Docker nur für --mit-image):
#        werkzeuge/ki.sh vorbereiten [Q4_K_M Q8_0 …] [--repo NAME] [--mit-image [LLAMA_IMAGE]]
#          → epm-ki-modelle-<Datum>.tar  (Modelle, Vision-Projektor, SHA256SUMS, MODELLE.txt, ggf. Images)
#   2. Datei auf den Server kopieren (scp) und dort:
#        sudo epm-ki einspielen ~/epm-ki-modelle-<Datum>.tar     prüft Prüfsummen, legt nach /srv/epm/ki-modelle
#        sudo epm-ki pruefen                                       Hardware der VM und Empfehlung
#        sudo epm-ki einrichten                                    Secrets, Ordner, Grenzen, Container, Modell
#   Danach:
#        sudo epm-ki status            Container, Modell, Zeitfenster, Queue
#        sudo epm-ki benchmark         Modelle/Quantisierungen messen (werkzeuge/ki-benchmark.sh)
#        sudo epm-ki aus               KI-Container stoppen und aus der Compose-Konfiguration nehmen (Daten bleiben)
#        sudo epm-ki laden REPO QUANT  nur Test-VM bzw. EPM_KI_DOWNLOAD="1": Modell direkt laden und einspielen
#        sudo epm-ki loeschen DATEI    eingespielte Modelldatei löschen (nie die aktive)
#   Alles davon geht auch aus EPM: Administration › KI › Einrichtung (über den Systemagenten).
#
# Die KI-Container hängen nur am Netz „intern“ ohne Weg nach außen. Unter 12 GB RAM / 4 Kernen bleibt der KI-Dienst
# von selbst aus.
set -euo pipefail

HIER="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
KONF=/etc/epm/epm.conf
B=/srv/epm
if [[ -f "$KONF" ]]; then
  # shellcheck disable=SC1090
  source "$KONF"
  B="${EPM_BASE:-/srv/epm}"
fi
CODE="${EPM_CODE:-/srv/epm-code}"
[[ -d "$HIER/../rollout/ki" ]] && CODE="$(cd "$HIER/.." && pwd)"
VORRAT="$B/ki-modelle"
REPO_STANDARD="${KI_HF_REPO:-bartowski/Qwen_Qwen3.5-4B-GGUF}"
LLAMA_STANDARD="${KI_LLAMA_IMAGE:-ghcr.io/ggml-org/llama.cpp:server}"

hilfe() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
fehler() { echo "FEHLER: $*" >&2; exit 1; }
root() { [[ $EUID -eq 0 ]] || fehler "Bitte mit sudo ausführen."; }
env_setzen() {  # Schlüssel, Wert → in $B/.env setzen (vorhandenen Wert ersetzen)
  local k="$1" v="$2"
  if grep -q "^$k=" "$B/.env" 2>/dev/null; then sed -i "s|^$k=.*|$k=$v|" "$B/.env"; else echo "$k=$v" >> "$B/.env"; fi
}

# --------------------------------------------------------------------------------------------- vorbereiten (PC)
vorbereiten() {
  local repo="$REPO_STANDARD" mit_image="" quants=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo) repo="$2"; shift ;;
      --mit-image) mit_image="${2:-$LLAMA_STANDARD}"; [[ "${2:-}" == --* || -z "${2:-}" ]] && mit_image="$LLAMA_STANDARD" || shift ;;
      -h|--hilfe) hilfe ;;
      *) quants+=("$1") ;;
    esac
    shift
  done
  [[ ${#quants[@]} -gt 0 ]] || quants=(Q4_K_M Q8_0)
  command -v curl >/dev/null || fehler "curl fehlt."
  local ziel; ziel="$(mktemp -d)"
  trap "rm -rf '$ziel'" EXIT  # Wert jetzt einsetzen: beim Beenden ist die lokale Variable weg
  echo "==> Dateiliste von huggingface.co/$repo"
  local liste
  liste="$(curl -fsSL "https://huggingface.co/api/models/$repo" | grep -o '"rfilename":"[^"]*"' | cut -d'"' -f4)" \
    || fehler "Repository $repo nicht erreichbar."
  local projektor
  projektor="$(echo "$liste" | grep -i 'mmproj' | grep -i 'f16' | head -n1)"
  [[ -n "$projektor" ]] || projektor="$(echo "$liste" | grep -i 'mmproj' | head -n1)"
  [[ -n "$projektor" ]] || fehler "Kein Vision-Projektor (mmproj) in $repo – ohne ihn kann das Modell keine Bilder lesen."
  : > "$ziel/MODELLE.txt"
  local q datei
  for q in "${quants[@]}"; do
    datei="$(echo "$liste" | grep -v -i mmproj | grep -i -- "-$q\.gguf$" | head -n1)"
    [[ -n "$datei" ]] || { echo "   $q: nicht in $repo – übersprungen"; continue; }
    echo "==> $datei"
    curl -fL --retry 3 -o "$ziel/$datei" "https://huggingface.co/$repo/resolve/main/$datei"
    printf 'NAME=%s %s\nDATEI=%s\nPROJEKTOR=%s\nQUANT=%s\n\n' "$(basename "$repo" | sed 's/-GGUF$//;s/^Qwen_//')" \
      "$q" "$datei" "$projektor" "$q" >> "$ziel/MODELLE.txt"
  done
  grep -q '^DATEI=' "$ziel/MODELLE.txt" || fehler "Keine der gewünschten Quantisierungen gefunden (${quants[*]})."
  echo "==> $projektor"
  curl -fL --retry 3 -o "$ziel/$projektor" "https://huggingface.co/$repo/resolve/main/$projektor"
  curl -fsSL "https://huggingface.co/$repo/raw/main/README.md" -o "$ziel/README-Modell.md" || true
  echo "Quelle: https://huggingface.co/$repo · geladen $(date -Iseconds). Lizenz: siehe README-Modell.md bzw. die" \
       "Modellkarte des Basismodells (Qwen) – vor dem Einsatz prüfen." > "$ziel/HERKUNFT.txt"
  if [[ -n "$mit_image" ]]; then
    command -v docker >/dev/null || fehler "--mit-image braucht Docker."
    echo "==> Image ki-modell aus $mit_image bauen"
    docker pull "$mit_image"
    local digest tag
    digest="$(docker inspect --format '{{index .RepoDigests 0}}' "$mit_image" 2>/dev/null || echo "$mit_image")"
    tag="$(date +%Y%m%d)"
    docker build -q -f "$CODE/rollout/ki/Dockerfile.ki-modell" --build-arg "LLAMA_IMAGE=$digest" \
      -t "epm-ki-modell:$tag" "$CODE/rollout/ki" >/dev/null
    docker save "epm-ki-modell:$tag" -o "$ziel/epm-ki-modell-$tag.image.tar"
    echo "IMAGE=epm-ki-modell:$tag" > "$ziel/IMAGE.txt"
    echo "LLAMA=$digest" >> "$ziel/IMAGE.txt"
  fi
  (cd "$ziel" && sha256sum -- *.gguf *.txt *.md $(ls ./*.image.tar 2>/dev/null) > SHA256SUMS)
  local paket="$PWD/epm-ki-modelle-$(date +%Y%m%d).tar"
  tar -cf "$paket" -C "$ziel" .
  echo "Fertig: $paket ($(du -h "$paket" | cut -f1)). Auf den Server kopieren und dort: sudo epm-ki einspielen DATEI"
}

# --------------------------------------------------------------------------------------------- einspielen (Server)
einspielen() {
  root
  local paket="${1:-}"
  [[ -f "$paket" ]] || fehler "Datei fehlt: sudo epm-ki einspielen ~/epm-ki-modelle-<Datum>.tar"
  local tmp; tmp="$(mktemp -d -p "$B")"
  trap "rm -rf '$tmp'" EXIT
  # nur einfache Dateinamen (kein ../, keine Links)
  if tar -tf "$paket" | grep -vE '^(\./)?[A-Za-z0-9._-]+$' | grep -vqx './'; then
    fehler "Unerwarteter Inhalt im Paket (nur Dateien ohne Unterordner erlaubt)."
  fi
  tar -xf "$paket" -C "$tmp" --no-same-owner --no-same-permissions
  (cd "$tmp" && sha256sum -c --quiet SHA256SUMS) || fehler "Prüfsummen stimmen nicht – Paket beschädigt."
  install -d -m 0755 "$VORRAT"
  local f
  for f in "$tmp"/*.gguf; do
    install -m 0644 "$f" "$VORRAT/"
  done
  cat "$tmp/MODELLE.txt" >> "$VORRAT/MODELLE.txt"
  cp "$tmp/SHA256SUMS" "$VORRAT/SHA256SUMS.$(date +%Y%m%d%H%M)"
  [[ -f "$tmp/HERKUNFT.txt" ]] && cp "$tmp/HERKUNFT.txt" "$VORRAT/"
  [[ -f "$tmp/README-Modell.md" ]] && cp "$tmp/README-Modell.md" "$VORRAT/"
  for f in "$tmp"/*.image.tar; do
    [[ -f "$f" ]] || continue
    echo "==> Image laden ($(basename "$f"))"
    docker load -i "$f" >/dev/null
    env_setzen KI_MODELL_IMAGE_TAG "$(sed -n 's/^IMAGE=epm-ki-modell://p' "$tmp/IMAGE.txt")"
  done
  echo "Eingespielt nach $VORRAT:"; ls -lh "$VORRAT"/*.gguf | awk '{print "   " $5 "  " $9}'
  if [[ -f "$B/ki-aktiv" ]]; then
    registrieren 0 "$tmp/MODELLE.txt"
    echo "Registriert – unter Administration › KI › Modelle evaluieren und aktivieren."
  else
    echo "Weiter: KI einrichten (Administration › KI › Einrichtung oder sudo epm-ki einrichten)"
  fi
}

# registrieren <erste aktivieren 0|1> <MODELLE.txt>: Varianten in der Modell-Registry von EPM eintragen
registrieren() {
  local aktiv="$1" liste="$2" name="" datei="" projektor="" quant=""
  while IFS= read -r zeile; do
    case "$zeile" in
      NAME=*) name="${zeile#NAME=}" ;;
      DATEI=*) datei="${zeile#DATEI=}" ;;
      PROJEKTOR=*) projektor="${zeile#PROJEKTOR=}" ;;
      QUANT=*) quant="${zeile#QUANT=}"
        (cd "$B" && docker compose exec -T backend python manage.py epm_ki_modell --registrieren "$datei" \
          --projektor "$projektor" --name "$name" --quantisierung "$quant" $([[ $aktiv == 1 ]] && echo --aktivieren)) \
          || echo "WARNUNG: $datei nicht registriert (Backend erreichbar?)"
        aktiv=0 ;;
    esac
  done < "$liste"
}

# --------------------------------------------------------------------------------------------- laden (Server)
laden() {
  root
  local repo="${1:-}" quant="${2:-}"
  [[ "$repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ && "$quant" =~ ^[A-Za-z0-9_]+$ ]] || fehler "laden REPO QUANT"
  local tmp; tmp="$(mktemp -d -p "$B")"
  local mit_image=""
  local tag; tag="$(sed -n 's/^KI_MODELL_IMAGE_TAG=//p' "$B/.env" 2>/dev/null)"
  if [[ -z "$tag" ]] || ! docker image inspect "epm-ki-modell:$tag" >/dev/null 2>&1; then mit_image="--mit-image"; fi
  echo "==> $repo $quant laden (Systemagent auf dem Server; die KI-Container selbst haben keinen Weg nach außen)"
  # Zwischendateien unter /srv/epm statt /tmp (dort ist oft wenig Platz)
  ( cd "$tmp" && TMPDIR="$tmp" vorbereiten "$quant" --repo "$repo" $mit_image ) || { rm -rf "$tmp"; fehler "Laden fehlgeschlagen."; }
  local paket; paket="$(ls "$tmp"/epm-ki-modelle-*.tar | head -n1)"
  ( einspielen "$paket" ) || { rm -rf "$tmp"; fehler "Einspielen fehlgeschlagen."; }
  rm -rf "$tmp"
}

# --------------------------------------------------------------------------------------------- loeschen (Server)
loeschen() {
  root
  local datei="${1:-}"
  [[ "$datei" =~ ^[A-Za-z0-9._-]{1,200}\.gguf$ && -f "$VORRAT/$datei" ]] || fehler "Unbekannte Modelldatei: $datei"
  local aktiv; aktiv="$(sed -n 's/^DATEI=//p' "$B/data/ki/modell/aktiv.env" 2>/dev/null)"
  [[ -n "$aktiv" ]] || aktiv="$(sed -n 's/^KI_MODELL_DATEI=//p' "$B/.env" 2>/dev/null)"
  [[ "$datei" != "$aktiv" ]] || fehler "$datei ist das aktive Modell – zuerst ein anderes aktivieren."
  if grep -q "^PROJEKTOR=$datei$" "$VORRAT/MODELLE.txt" 2>/dev/null; then
    fehler "$datei ist ein Vision-Projektor, den noch Modelle brauchen."
  fi
  rm -f "$VORRAT/$datei"
  # Abschnitt der Variante aus MODELLE.txt nehmen
  awk -v d="DATEI=$datei" 'BEGIN{RS=""; ORS="\n\n"} index($0, d"\n")==0 && $0 !~ d"$"' "$VORRAT/MODELLE.txt" > "$VORRAT/MODELLE.txt.neu" \
    && mv "$VORRAT/MODELLE.txt.neu" "$VORRAT/MODELLE.txt"
  (cd "$B" && docker compose exec -T backend python manage.py epm_ki_modell --entfernt "$datei" 2>/dev/null) || true
  echo "$datei gelöscht."
}

# --------------------------------------------------------------------------------------------- einrichten (Server)
erste_variante() { sed -n "s/^$1=//p" "$VORRAT/MODELLE.txt" | head -n1; }

einrichten() {
  root
  [[ -f "$B/.env" && -f "$B/compose.yaml" ]] || fehler "EPM ist hier nicht eingerichtet ($B)."
  [[ -f "$B/compose.ki.yaml" ]] || install -m 0644 "$CODE/rollout/projekt/compose.ki.yaml" "$B/"
  [[ -f "$B/ki-modell-start.sh" ]] || install -m 0755 "$CODE/rollout/ki/ki-modell-start.sh" "$B/"
  ls "$VORRAT"/*.gguf >/dev/null 2>&1 || fehler "Keine Modelle in $VORRAT – zuerst: sudo epm-ki einspielen DATEI"
  echo "==> Hardware"
  local json; json="$("$CODE/werkzeuge/ki-pruefen.sh" --json)"
  local ram kerne
  ram="$(echo "$json" | sed -n 's/.*"ram_mb": \([0-9]*\).*/\1/p' | head -n1)"
  kerne="$(echo "$json" | sed -n 's/.*"kerne": \([0-9]*\).*/\1/p' | head -n1)"
  echo "   $kerne Kerne, $ram MB RAM"
  if (( ram < 11500 || kerne < 4 )); then
    echo "WARNUNG: Unter 12 GB RAM / 4 Kernen bleibt der KI-Dienst aus. Eingerichtet wird trotzdem (für später)."
  fi
  echo "==> Secrets und Ordner"
  [[ -s "$B/secrets/ki_db_password" ]] || openssl rand -base64 32 | tr -d '\n=/+' > "$B/secrets/ki_db_password"
  [[ -s "$B/secrets/ki_schluessel" ]] || openssl rand -hex 32 | tr -d '\n' > "$B/secrets/ki_schluessel"
  chmod 0644 "$B/secrets/ki_db_password" "$B/secrets/ki_schluessel"   # Ordner 0700: nur root auf dem Host
  install -d -m 0750 -o 10001 -g 101 "$B/data/ki" "$B/data/ki/modell"
  chmod 0755 "$B/data/ki/modell"   # ki-modell (eigener Benutzer) liest die Steuerdateien
  echo "==> Grenzen nach Hardware (.env – eigene Werte bleiben)"
  local speicher threads worker
  speicher="$(echo "$json" | sed -n 's/.*"KI_SPEICHER": "\([0-9a-z]*\)".*/\1/p')"
  threads="$(echo "$json" | sed -n 's/.*"KI_THREADS": \([0-9]*\).*/\1/p')"
  worker="$(echo "$json" | sed -n 's/.*"KI_WORKER_SPEICHER": "\([0-9a-z]*\)".*/\1/p')"
  grep -q '^KI_SPEICHER=' "$B/.env" || env_setzen KI_SPEICHER "${speicher:-6g}"
  grep -q '^KI_THREADS=' "$B/.env" || env_setzen KI_THREADS "${threads:-2}"
  grep -q '^KI_WORKER_SPEICHER=' "$B/.env" || env_setzen KI_WORKER_SPEICHER "${worker:-2g}"
  local datei projektor
  datei="$(erste_variante DATEI)"; projektor="$(erste_variante PROJEKTOR)"
  env_setzen KI_MODELL_DATEI "$datei"
  env_setzen KI_PROJEKTOR_DATEI "$projektor"
  env_setzen KI_MODELL_SHA256 "$(sha256sum "$VORRAT/$datei" | cut -d' ' -f1)"
  echo "==> Image ki-modell"
  local tag; tag="$(sed -n 's/^KI_MODELL_IMAGE_TAG=//p' "$B/.env")"
  if [[ -z "$tag" ]] || ! docker image inspect "epm-ki-modell:$tag" >/dev/null 2>&1; then
    echo "   nicht vorhanden – baue aus $LLAMA_STANDARD (braucht Zugang zu ghcr.io; sonst: vorbereiten --mit-image)"
    tag="$(date +%Y%m%d)"
    docker build -q -f "$CODE/rollout/ki/Dockerfile.ki-modell" --build-arg "LLAMA_IMAGE=$LLAMA_STANDARD" \
      -t "epm-ki-modell:$tag" "$CODE/rollout/ki" >/dev/null
    env_setzen KI_MODELL_IMAGE_TAG "$tag"
  fi
  echo "==> Compose: compose.ki.yaml dazunehmen und starten"
  touch "$B/ki-aktiv"
  env_setzen COMPOSE_FILE "compose.yaml:compose.ki.yaml"
  (cd "$B" && docker compose up -d)
  echo "==> Warte auf das Backend (Migrationen)"
  local status=""
  for _ in $(seq 1 60); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$(cd "$B" && docker compose ps -q backend)" 2>/dev/null || true)"
    [[ "$status" == "healthy" ]] && break
    sleep 3
  done
  [[ "$status" == "healthy" ]] || fehler "Backend wird nicht gesund – docker compose logs --tail 50 backend"
  echo "==> Modelle registrieren"
  registrieren 1 "$VORRAT/MODELLE.txt"
  echo
  echo "Fertig. Administration › KI zeigt Zeitfenster, Auslastung und Modelle; die Prüf-Queue steht im Menü"
  echo "„KI (Experimentell)“. Erste Nacht abwarten oder ein Dokument in der Akte ausdrücklich verarbeiten lassen."
}

status() {
  echo "==> Container"; (cd "$B" && docker compose ps ki-modell ki-worker 2>/dev/null) || echo "   nicht eingerichtet"
  echo "==> Modelle"; (cd "$B" && docker compose exec -T backend python manage.py epm_ki_modell --liste 2>/dev/null) || true
  echo "==> Stand"; (cd "$B" && docker compose exec -T ki-worker python manage.py epm_ki --stand 2>/dev/null) || true
  [[ -f "$B/data/ki/modell/schlafen" ]] && echo "   Modell schläft (tagsüber ohne Arbeit, Speicher freigegeben)"
  return 0
}

aus() {
  root
  rm -f "$B/ki-aktiv"
  (cd "$B" && docker compose stop ki-worker ki-modell 2>/dev/null; docker compose rm -f ki-worker ki-modell ki-init 2>/dev/null) || true
  env_setzen COMPOSE_FILE "compose.yaml"
  echo "KI-Container gestoppt und aus der Konfiguration genommen. Daten (Prüf-Queue, Hinweise, Modelle) bleiben."
  echo "Wieder einschalten: sudo epm-ki einrichten"
}

benchmark() {
  root
  EPM_BASIS="$B" "$CODE/werkzeuge/ki-benchmark.sh" --modelle "$VORRAT" "$@"
}

case "${1:-}" in
  vorbereiten) shift; vorbereiten "$@" ;;
  einspielen) shift; einspielen "$@" ;;
  pruefen) shift; "$CODE/werkzeuge/ki-pruefen.sh" "$@" ;;
  einrichten) einrichten ;;
  laden) shift; laden "$@" ;;
  loeschen) shift; loeschen "$@" ;;
  status) status ;;
  aus) aus ;;
  benchmark) shift; benchmark "$@" ;;
  ""|-h|--hilfe|hilfe) hilfe ;;
  *) echo "Unbekannt: $1"; hilfe 1 ;;
esac
