#!/usr/bin/env bash
# EPM – Update in einem Schritt.
#
# Test-VM (EPM_UPDATE_QUELLE="git", Standard): Code von GitHub holen, Images bauen, Backup, starten, Musterdaten, Tests.
#   sudo epm-update                     neuesten Stand von GitHub holen und ausrollen
#   sudo epm-update --ohne-tests        ohne Testlauf (schneller)
#   sudo epm-update --paket-erstellen   Update-Paket der laufenden (getesteten) Version für den VPS schreiben
#
# VPS ohne Internet (EPM_UPDATE_QUELLE="paket" in /etc/epm/epm.conf): kein git, kein Build auf dem Server –
# nur ein auf der Test-VM erstelltes Paket einspielen (per scp übertragen):
#   sudo epm-update --paket /pfad/epm-paket-TAG.tar [--ohne-tests]
#
# Überall:
#   sudo epm-update --zurueck TAG       auf eine frühere Version zurückschalten (z. B. 0.1.1-3fa2c1d)
#   sudo epm-update --versionen         vorhandene Versionen anzeigen
#
# Die Ausgaben der Bauschritte stehen in /var/log/epm-update.log (je Lauf neu). Bricht ein Schritt ab, nennt das
# Skript Schritt, Zeile und Exitcode und zeigt die letzten Zeilen des Protokolls. Wird der Lauf vom Kernel
# beendet (Speichermangel), bleibt das Protokoll als einzige Spur – dann dort hineinsehen.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }

CODE=/srv/epm-code
KONF=/etc/epm/epm.conf
[[ -f "$KONF" ]] || { echo "Fehlt: $KONF (siehe epm-git-einrichten.sh)"; exit 1; }
source "$KONF"
B="$EPM_BASE"
QUELLE="${EPM_UPDATE_QUELLE:-git}"
TESTS=1
PAKET=""

PROTOKOLL=/var/log/epm-update.log
LETZTER_SCHRITT="Start"
schritt() { LETZTER_SCHRITT="$*"; echo; echo "==> $*"; }

# Ohne das hier endete ein fehlgeschlagener Schritt stumm (set -e, Ausgaben im Protokoll): Der Trap nennt
# Schritt, Zeile und Exitcode und zeigt die letzten Zeilen des Protokolls (Stolperstein 07.10.2026).
abbruch() {
  local code=$1 zeile=$2 befehl=$3
  echo
  echo "ABBRUCH bei „$LETZTER_SCHRITT“ (Zeile $zeile, Exitcode $code)"
  echo "   Befehl: $befehl"
  if [[ $code -ge 128 ]]; then
    echo "   Exitcode über 128 heißt: abgebrochen durch Signal $((code - 128))" \
         "– 137 = vom Kernel wegen Speichermangel beendet (siehe: dmesg -T | tail -30), 130 = Strg-C."
  fi
  if [[ -s "$PROTOKOLL" ]]; then
    echo "   Letzte Zeilen aus $PROTOKOLL:"
    tail -n 25 "$PROTOKOLL" | sed 's/^/   /'
  fi
  echo "Nichts wurde umgestellt; die laufende Version bleibt unverändert."
  exit "$code"
}
trap 'abbruch $? $LINENO "$BASH_COMMAND"' ERR
# Protokoll je Lauf neu; Ausgaben der Bauschritte landen dort statt in /dev/null
: > "$PROTOKOLL" 2>/dev/null || PROTOKOLL=/dev/null
chmod 0600 "$PROTOKOLL" 2>/dev/null || true

alte_entfernen() {
  # „Die neuesten N behalten, den Rest löschen“. Bewusst ohne ``ls … | grep … | tail …``: Trifft das Muster
  # nichts (oder filtert grep alles weg), scheitert die Pipeline, und ``set -e`` mit ``pipefail`` beendete den
  # Lauf an dieser Stelle stumm – das war die Ursache des Abbruchs vom 07.10.2026.
  local behalten="$1" ohne="$2"; shift 2
  local datei
  local -a kandidaten=() sortiert=()
  for datei in "$@"; do
    [[ -f "$datei" ]] || continue                  # unaufgelöstes Muster: es gibt keine solche Datei
    if [[ -n "$ohne" && "$datei" == *"$ohne"* ]]; then continue; fi
    kandidaten+=("$datei")
  done
  (( ${#kandidaten[@]} > behalten )) || return 0
  while IFS= read -r datei; do sortiert+=("$datei"); done < <(
    stat -c '%Y %n' -- "${kandidaten[@]}" | sort -rn | cut -d' ' -f2-)
  rm -f -- "${sortiert[@]:behalten}"
}

starte_version() {
  local tag="$1"
  sed -i -e 's/^COMPOSE_FILE=.*/COMPOSE_FILE=compose.yaml/' -e "s/^EPM_VERSION=.*/EPM_VERSION=$tag/" "$B/.env"
  (cd "$B" && docker compose up -d --remove-orphans)
  schritt "Warte auf das Backend"
  local status=""
  for _ in $(seq 1 60); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$(cd "$B" && docker compose ps -q backend)" 2>/dev/null || true)"
    [[ "$status" == "healthy" ]] && return 0
    sleep 3
  done
  echo "Backend startet nicht. Letzte Meldungen:"
  (cd "$B" && docker compose logs --tail 40 backend)
  return 1
}

paket_erstellen() {
  # Die laufende Version – auf der Test-VM gebaut und getestet – samt Rollout-Dateien in eine Datei packen.
  local tag; tag="$(grep ^EPM_VERSION= "$B/.env" | cut -d= -f2)"
  docker image inspect "epm-backend:$tag" >/dev/null 2>&1 && docker image inspect "epm-web:$tag" >/dev/null 2>&1 \
    || { echo "Images der laufenden Version $tag fehlen."; exit 1; }
  local commit="${tag##*-}"
  [[ -d "$CODE/.git" ]] || { echo "Paket erstellen geht nur auf der Test-VM (mit $CODE aus GitHub)."; exit 1; }
  git -C "$CODE" cat-file -e "$commit^{commit}" 2>/dev/null || { echo "Commit $commit fehlt in $CODE."; exit 1; }
  local tmp; tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN
  schritt "Paket für Version $tag (Commit $commit)"
  git -C "$CODE" archive "$commit" rollout werkzeuge/epm-update.sh VERSION | tar -x -C "$tmp"
  echo "$tag" > "$tmp/TAG"
  docker save "epm-backend:$tag" "epm-web:$tag" -o "$tmp/images.tar"
  (cd "$tmp" && find . -type f ! -name SHA256SUMS -printf '%P\n' | sort | xargs sha256sum > SHA256SUMS)
  local ziel="$B/images/epm-paket-$tag.tar"
  tar -C "$tmp" -cf "$ziel" .
  chmod 0644 "$ziel"
  echo
  echo "Fertig: $ziel ($(du -h "$ziel" | cut -f1))"
  echo "SHA-256: $(sha256sum "$ziel" | cut -d' ' -f1)"
  echo "Übertragen, z. B.:  scp $ziel epmadmin@VPS:~/"
  echo "Auf dem VPS:        sudo epm-update --paket ~/$(basename "$ziel")"
  echo "Dort zeigt epm-update dieselbe SHA-256 an – vergleichen."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --versionen)
      docker image ls epm-backend --format '{{.Tag}}\t{{.CreatedSince}}'
      echo "aktiv: $(grep ^EPM_VERSION= "$B/.env" | cut -d= -f2)"
      exit 0 ;;
    --zurueck)
      TAG="${2:?Version angeben, siehe: sudo epm-update --versionen}"
      docker image inspect "epm-backend:$TAG" >/dev/null || { echo "Version $TAG nicht vorhanden."; exit 1; }
      docker image inspect "epm-web:$TAG" >/dev/null || { echo "Frontend-Image epm-web:$TAG fehlt."; exit 1; }
      starte_version "$TAG"
      echo "Zurückgeschaltet auf $TAG. Achtung: Datenbank-Migrationen werden dabei nicht zurückgedreht."
      exit 0 ;;
    --paket-erstellen) paket_erstellen; exit 0 ;;
    --paket) PAKET="${2:?Paketdatei angeben, z. B. sudo epm-update --paket ~/epm-paket-0.2.0-1a2b3c4.tar}"; shift ;;
    --ohne-tests) TESTS=0 ;;
    *) sed -n '2,18p' "$0"; exit 1 ;;
  esac
  shift
done

if [[ -n "$PAKET" ]]; then
  # ------------------------------------------------------------ Paket einspielen (VPS, ohne Internet)
  [[ -f "$PAKET" ]] || { echo "Datei $PAKET nicht gefunden."; exit 1; }
  if [[ -d "$CODE/.git" ]]; then
    echo "Hier ist $CODE mit GitHub verbunden (Test-VM) – Updates mit „sudo epm-update“."
    echo "Pakete sind für Server mit EPM_UPDATE_QUELLE=\"paket\" gedacht."
    exit 1
  fi
  schritt "Paket prüfen"
  echo "   SHA-256: $(sha256sum "$PAKET" | cut -d' ' -f1)  (mit der Anzeige auf der Test-VM vergleichen)"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  tar -C "$TMP" -xf "$PAKET"
  (cd "$TMP" && sha256sum --quiet -c SHA256SUMS) || { echo "ABBRUCH: Paket beschädigt. Nichts wurde umgestellt."; exit 1; }
  TAG="$(tr -d '[:space:]' < "$TMP/TAG")"
  [[ "$TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40}$ ]] || { echo "ABBRUCH: Version „$TAG“ nicht erkannt."; exit 1; }
  echo "   Version $TAG, Inhalt vollständig"

  schritt "Projektdateien aktualisieren (Compose, Nginx, Skripte, Systemagent)"
  rm -rf "$CODE"
  install -d -m 0750 "$CODE"
  cp -a "$TMP/rollout" "$TMP/werkzeuge" "$TMP/VERSION" "$TMP/TAG" "$CODE/"
  find "$CODE" -name '*.sh' -exec chmod +x {} +
  (cd "$CODE/rollout" && ./04-projekt.sh >/dev/null)
  install -m 0750 "$CODE/werkzeuge/epm-update.sh" /usr/local/sbin/epm-update

  schritt "Images laden (epm-backend:$TAG, epm-web:$TAG)"
  docker load -i "$TMP/images.tar" | sed 's/^/   /'
  install -m 0600 "$TMP/images.tar" "$B/images/epm-$TAG.tar"
  alte_entfernen 5 /epm-paket- "$B"/images/epm-*.tar
else
  # ------------------------------------------------------------ von GitHub holen und bauen (Test-VM)
  if [[ "$QUELLE" == "paket" ]]; then
    echo "Dieser Server bekommt Updates nur als Paket (EPM_UPDATE_QUELLE=\"paket\" in $KONF)."
    echo "Paket auf der Test-VM erstellen:  sudo epm-update --paket-erstellen"
    echo "Hier einspielen:                  sudo epm-update --paket ~/epm-paket-TAG.tar"
    exit 1
  fi
schritt "Code von GitHub holen"
git -C "$CODE" fetch --quiet origin
ALT="$(git -C "$CODE" rev-parse --short HEAD)"
git -C "$CODE" reset --quiet --hard origin/main
NEU="$(git -C "$CODE" rev-parse --short HEAD)"
TAG="$(tr -d '[:space:]' < "$CODE/VERSION")-$NEU"
if [[ "$ALT" != "$NEU" ]]; then
  git -C "$CODE" log --oneline "$ALT..$NEU" | sed 's/^/   /'
else
  echo "   keine neuen Änderungen ($NEU)"
fi

schritt "Projektdateien aktualisieren (Compose, Nginx, Skripte)"
(cd "$CODE/rollout" && ./04-projekt.sh >/dev/null)
install -m 0750 "$CODE/werkzeuge/epm-update.sh" /usr/local/sbin/epm-update
install -m 0750 "$CODE/werkzeuge/ocr-modelle.sh" /usr/local/sbin/epm-ocr-modelle

# OCR-Modelle (PP-OCRv5, UVDoc): offline vorbereitet und mit „epm-ocr-modelle einspielen“ abgelegt → in den
# Bau-Kontext legen; der Bau übernimmt sie von dort statt sie von huggingface.co zu laden.
MODELLE_VORRAT="$B/ocr-modelle"
MODELLE_KONTEXT="$CODE/backend/scans/modelle/dateien"
MODELLE_DA=0
if [[ -d "$MODELLE_VORRAT" ]] && python3 "$CODE/backend/scans/modelle/holen.py" --nur-pruefen "$MODELLE_VORRAT" >/dev/null 2>&1; then
  rm -rf "$MODELLE_KONTEXT"; mkdir -p "$MODELLE_KONTEXT"; cp -a "$MODELLE_VORRAT/." "$MODELLE_KONTEXT/"
  MODELLE_DA=1
fi
# Ein schon gebautes Image ohne Modelle wird neu gebaut, sobald die Modelle bereitliegen.
if [[ $MODELLE_DA -eq 1 ]] && docker image inspect "epm-backend:$TAG" >/dev/null 2>&1 \
   && ! docker run --rm --entrypoint test "epm-backend:$TAG" -f /opt/ocr-modelle/detection/v5/det.onnx 2>/dev/null; then
  echo "   OCR-Modelle liegen bereit – epm-backend:$TAG wird mit ihnen neu gebaut"
  docker image rm "epm-backend:$TAG" >/dev/null
fi

if docker image inspect "epm-backend:$TAG" >/dev/null 2>&1 && docker image inspect "epm-web:$TAG" >/dev/null 2>&1; then
  schritt "Images epm-backend:$TAG und epm-web:$TAG sind schon gebaut"
else
  schritt "Image epm-backend:$TAG bauen"
  docker build -t "epm-backend:$TAG" "$CODE/backend" >>"$PROTOKOLL" 2>&1
  if docker run --rm --entrypoint test "epm-backend:$TAG" -f /opt/ocr-modelle/detection/v5/det.onnx 2>/dev/null; then
    echo "   Texterkennung: Tesseract + PP-OCRv5"
  else
    echo "   Texterkennung: nur Tesseract – PP-OCRv5-Modelle fehlen (kein Zugang zu huggingface.co?)."
    echo "   Offline nachreichen: werkzeuge/ocr-modelle.sh vorbereiten (PC) → sudo epm-ocr-modelle einspielen DATEI → sudo epm-update"
  fi
  docker run --rm -e DJANGO_DEBUG=1 "epm-backend:$TAG" python manage.py check
  if ! docker run --rm -e DJANGO_DEBUG=1 "epm-backend:$TAG" python manage.py makemigrations --check --dry-run >/dev/null; then
    echo "ABBRUCH: Im Code fehlen Datenbank-Migrationen. Nichts wurde umgestellt."
    exit 1
  fi
  schritt "Image epm-web:$TAG bauen (Frontend, braucht Zugang zu registry.npmjs.org)"
  docker build -t "epm-web:$TAG" "$CODE/frontend" >>"$PROTOKOLL" 2>&1
  docker save "epm-backend:$TAG" "epm-web:$TAG" -o "$B/images/epm-$TAG.tar"
  chmod 0600 "$B/images/epm-$TAG.tar"
  # nur die letzten 5 Image-Dateien behalten (Update-Pakete für den VPS: die letzten 3)
  alte_entfernen 5 /epm-paket- "$B"/images/epm-*.tar
  alte_entfernen 3 "" "$B"/images/epm-paket-*.tar
fi

fi

schritt "Backup vor dem Umstellen"
if (cd "$B" && docker compose ps --status running -q db | grep -q .); then
  /usr/local/sbin/epm-backup --art vor_update
fi

schritt "Version $TAG starten (Migrationen laufen automatisch)"
starte_version "$TAG"

schritt "Musterdaten prüfen"
(cd "$B" && docker compose exec -T backend python manage.py epm_musterdaten)

if [[ $TESTS -eq 1 ]]; then
  schritt "Tests (eigene Test-Datenbank, echte Daten bleiben unberührt)"
  LOG=/var/log/epm-tests.log
  # ``</dev/null``: Ohne das hängt die Standardeingabe am Terminal – in die Zwischenablage geratener Text landete
  # dann im laufenden Testcontainer und ein darin enthaltenes Strg-C brach den Lauf ab (Stolperstein 06.10.2026).
  if (cd "$B" && docker compose run --rm -T backend python manage.py test) </dev/null >"$LOG" 2>&1; then
    ERGEBNIS="Tests OK"
  else
    ERGEBNIS="TESTS FEHLGESCHLAGEN – Ausgabe oben, vollständig in $LOG"
  fi
  grep -v " WARNING django.request: " "$LOG" | tail -25
else
  ERGEBNIS="Tests übersprungen"
fi

echo
echo "────────────────────────────────────────────"
echo " EPM $TAG läuft – $ERGEBNIS"
echo " https://$EPM_WEB_NAME/"
echo " Zurück auf die vorige Version: sudo epm-update --versionen"
echo "────────────────────────────────────────────"
