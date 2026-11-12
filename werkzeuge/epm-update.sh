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
# Signatur (17.10.2026): Ein Paket bringt Skripte mit, die hier als root laufen (04-projekt.sh). Die Test-VM
# signiert deshalb die Prüfsummen mit /etc/epm/paket-signatur (ssh-keygen -Y sign; beim ersten Paket von selbst
# angelegt) und legt den öffentlichen Schlüssel bei. Der VPS prüft die Signatur, BEVOR er etwas auspackt oder ausführt:
# gegen /etc/epm/paket-vertraut.pub, und wenn es den noch nicht gibt, gegen den mitgelieferten Schlüssel, den er dann
# übernimmt („trust on first use“). Zurücksetzen nur aus der Oberfläche, wirksam nach 24 Stunden (Systemagent).
#   sudo epm-update --paket DATEI --ohne-signatur   nur für alte, unsignierte Pakete, solange kein Schlüssel gespeichert ist
#
# Überall:
#   sudo epm-update --zurueck TAG       auf eine frühere Version zurückschalten (z. B. 0.1.1-3fa2c1d)
#   sudo epm-update --versionen         vorhandene Versionen anzeigen
#   sudo epm-update --gut [TAG]         die laufende (oder genannte) Version als „gute Version“ bestätigen
#
# Selbstheilung (13.10.2026): In $B/.env steht neben EPM_VERSION die zuletzt bewährte Version EPM_VERSION_GUT. Ein Update
# merkt sich vorher die laufende Version und erhebt die neue erst zur guten, wenn das Backend gesund ist, die
# Musterdaten stimmen und – wenn sie laufen – die Tests bestanden sind. Startet die neue Version nicht, schaltet das
# Skript selbst auf die gute zurück und hinterlässt in $B/system/rueckfall.json eine Markierung, die der Systemagent
# als Hinweis in EPM anzeigt. Während des Laufs liegt $B/system/update-laeuft, damit der Wächter des Systemagenten
# nicht dazwischenfunkt.
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
OHNE_SIGNATUR=0
SIGNATUR_SCHLUESSEL=/etc/epm/paket-signatur          # privat, nur auf der Test-VM
SIGNATUR_VERTRAUT=/etc/epm/paket-vertraut.pub       # auf dem VPS: beim ersten Paket übernommen

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
  if [[ "${UMGESTELLT:-0}" == 1 ]]; then
    echo "EPM läuft mit $(env_wert EPM_VERSION); gute Version (Rückfall): $(env_wert EPM_VERSION_GUT)."
  else
    echo "Nichts wurde umgestellt; die laufende Version bleibt unverändert."
  fi
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
  # ``ohne``: Teilstrings (durch Leerzeichen getrennt) – passende Dateien zählen nicht und bleiben (Pakete, gute Version)
  local behalten="$1" ohne="$2"; shift 2
  local datei muster uebergehen
  local -a kandidaten=() sortiert=()
  for datei in "$@"; do
    [[ -f "$datei" ]] || continue                  # unaufgelöstes Muster: es gibt keine solche Datei
    uebergehen=0
    for muster in $ohne; do [[ "$datei" == *"$muster"* ]] && uebergehen=1; done
    (( uebergehen )) && continue
    kandidaten+=("$datei")
  done
  (( ${#kandidaten[@]} > behalten )) || return 0
  while IFS= read -r datei; do sortiert+=("$datei"); done < <(
    stat -c '%Y %n' -- "${kandidaten[@]}" | sort -rn | cut -d' ' -f2-)
  rm -f -- "${sortiert[@]:behalten}"
}

env_wert() { grep "^$1=" "$B/.env" 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '"' ; }
env_setzen() {
  # Schlüssel in $B/.env setzen oder anhängen (ohne sed-Sonderzeichen im Wert: Tags bestehen aus Ziffern, Punkt, Minus, hex)
  if grep -q "^$1=" "$B/.env" 2>/dev/null; then sed -i "s/^$1=.*/$1=$2/" "$B/.env"; else echo "$1=$2" >> "$B/.env"; fi
}
version_vorhanden() { docker image inspect "epm-backend:$1" >/dev/null 2>&1 && docker image inspect "epm-web:$1" >/dev/null 2>&1; }

gut_setzen() {
  env_setzen EPM_VERSION_GUT "$1"
  rm -f "$B/system/rueckfall.json"    # ein früherer Rückfall ist damit erledigt
  echo "   Gute Version: $1"
}
# Die gute Version, auf die ein fehlgeschlagener Start zurückfällt: EPM_VERSION_GUT, sonst die bisher laufende –
# jeweils nur, wenn beide Images noch da sind.
rueckfall_ziel() {
  local gut; gut="$(env_wert EPM_VERSION_GUT)"
  local kandidat
  for kandidat in "$gut" "$1"; do
    [[ -n "$kandidat" && "$kandidat" != "$2" ]] || continue
    version_vorhanden "$kandidat" && { echo "$kandidat"; return 0; }
  done
  return 1
}

# Markierung für den Systemagenten (Status „Selbstheilung“, Hinweis an alle Benutzer): wer, wann, von, nach, warum
rueckfall_markieren() {
  local von="$1" nach="$2" grund="$3" ok="$4"
  install -d -m 0755 "$B/system"
  printf '{"id": "%s", "zeit": "%s", "quelle": "epm-update", "von": "%s", "nach": "%s", "ok": %s, "grund": "%s"}\n' \
    "$(date +%s)$$" "$(date -Iseconds)" "$von" "$nach" "$ok" "$grund" > "$B/system/rueckfall.json.tmp"
  chmod 0644 "$B/system/rueckfall.json.tmp"; mv "$B/system/rueckfall.json.tmp" "$B/system/rueckfall.json"
}
update_laeuft_setzen() { install -d -m 0755 "$B/system"; echo "$$ $(date -Iseconds) $1" > "$B/system/update-laeuft"; }
TMP=""
aufraeumen_exit() { rm -f "$B/system/update-laeuft"; [[ -n "$TMP" ]] && rm -rf "$TMP"; return 0; }

starte_version() {
  local tag="$1"
  # KI (Experimentell, 14.10.2026): eingerichtet (Marke von `epm-ki einrichten`) → deren Container bleiben dabei
  local dateien="compose.yaml"
  [[ -f "$B/ki-aktiv" && -f "$B/compose.ki.yaml" ]] && dateien="compose.yaml:compose.ki.yaml"
  sed -i -e "s/^COMPOSE_FILE=.*/COMPOSE_FILE=$dateien/" -e "s/^EPM_VERSION=.*/EPM_VERSION=$tag/" "$B/.env"
  (cd "$B" && docker compose up -d --remove-orphans) || return 1
  # KI: Startskript von ki-modell geändert (04-projekt.sh) → Container neu starten, damit es gilt
  if [[ "$dateien" == *compose.ki.yaml* && -f "$B/ki-modell-start.geaendert" ]]; then
    (cd "$B" && docker compose restart ki-modell) || true
    rm -f "$B/ki-modell-start.geaendert"
  fi
  schritt "Warte auf das Backend"
  local status=""
  for _ in $(seq 1 60); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$(cd "$B" && docker compose ps -q backend)" 2>/dev/null || true)"
    [[ "$status" == "healthy" ]] && return 0
    sleep 3
  done
  echo "Backend startet nicht. Letzte Meldungen:"
  (cd "$B" && docker compose logs --tail 40 backend) || true
  return 1
}

# Neue Version starten; startet sie nicht, von selbst auf die gute Version zurück (Festlegung 13.10.2026).
# Aufruf unter ``if``: ein Fehlschlag löst nicht den ERR-Trap aus, sondern den Rückfall hier.
umstellen_oder_zurueck() {
  local tag="$1" vorher="$2"
  if starte_version "$tag"; then return 0; fi
  local ziel
  if ! ziel="$(rueckfall_ziel "$vorher" "$tag")"; then
    rueckfall_markieren "$tag" "" "Version $tag startet nicht; keine andere Version mit beiden Images vorhanden" false
    echo
    echo "ABBRUCH: Neue Version $tag startet nicht – und es gibt keine frühere Version zum Zurückschalten."
    echo "   Protokoll: $PROTOKOLL · Container: docker compose logs backend"
    return 1
  fi
  schritt "Zurück auf die gute Version $ziel"
  local ok=true
  starte_version "$ziel" || ok=false
  rueckfall_markieren "$tag" "$ziel" "Version $tag startet nicht (Backend nach 180 s nicht gesund)" "$ok"
  echo
  if [[ "$ok" == true ]]; then
    echo "ABBRUCH: Neue Version $tag startet nicht – zurück auf $ziel (läuft wieder)."
  else
    echo "ABBRUCH: Neue Version $tag startet nicht – und auch $ziel startet nicht. Bitte: docker compose logs backend"
  fi
  echo "   Datenbank-Migrationen der neuen Version wurden nicht zurückgedreht; läuft $ziel damit nicht sauber, die"
  echo "   Sicherung von vor dem Update wiederherstellen (Administration › Backup). Fehlerursache: $PROTOKOLL,"
  echo "   Administration › System › Protokolle › „Container backend“."
  return 1
}

# Nach dem Start: Musterdaten, Tests; erst danach wird die neue Version zur guten (nur wenn alles bestand)
abschliessen() {
  local tag="$1" vorher="$2"
  schritt "Musterdaten prüfen"
  if ! (cd "$B" && docker compose exec -T backend python manage.py epm_musterdaten); then
    echo "Musterdaten fehlgeschlagen – $tag läuft, bleibt aber unbestätigt (gute Version weiterhin $(env_wert EPM_VERSION_GUT))."
    ERGEBNIS="MUSTERDATEN FEHLGESCHLAGEN"
    return 1
  fi
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
    [[ "$ERGEBNIS" == "Tests OK" ]] || { echo "   $tag bleibt unbestätigt; gute Version weiterhin $(env_wert EPM_VERSION_GUT)."; return 0; }
  else
    ERGEBNIS="Tests übersprungen"
  fi
  gut_setzen "$tag"
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
  echo "${tag%-*}" > "$tmp/VERSION"   # berechnete Nummer (ohne Git auf dem VPS nicht mehr ableitbar)
  docker save "epm-backend:$tag" "epm-web:$tag" -o "$tmp/images.tar"
  if [[ ! -f "$SIGNATUR_SCHLUESSEL" ]]; then
    (umask 077 && ssh-keygen -q -t ed25519 -N '' -C "epm-paket $(hostname)" -f "$SIGNATUR_SCHLUESSEL")
    echo "   Signaturschlüssel angelegt: $SIGNATUR_SCHLUESSEL"
  fi
  chmod 0600 "$SIGNATUR_SCHLUESSEL"
  [[ -s "$SIGNATUR_SCHLUESSEL.pub" ]] || ssh-keygen -y -f "$SIGNATUR_SCHLUESSEL" > "$SIGNATUR_SCHLUESSEL.pub"
  chmod 0644 "$SIGNATUR_SCHLUESSEL.pub"
  cp "$SIGNATUR_SCHLUESSEL.pub" "$tmp/paket-signatur.pub"   # für das erste Paket auf einem VPS (steht in SHA256SUMS)
  (cd "$tmp" && find . -type f ! -name SHA256SUMS -printf '%P\n' | sort | xargs sha256sum > SHA256SUMS)
  ssh-keygen -Y sign -q -f "$SIGNATUR_SCHLUESSEL" -n epm-paket "$tmp/SHA256SUMS"   # → SHA256SUMS.sig
  echo "   Signiert: $(ssh-keygen -lf "$SIGNATUR_SCHLUESSEL.pub" | cut -d' ' -f2)"
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
      echo "aktiv: $(env_wert EPM_VERSION)"
      echo "gut:   $(env_wert EPM_VERSION_GUT)"
      exit 0 ;;
    --zurueck)
      TAG="${2:?Version angeben, siehe: sudo epm-update --versionen}"
      docker image inspect "epm-backend:$TAG" >/dev/null || { echo "Version $TAG nicht vorhanden."; exit 1; }
      docker image inspect "epm-web:$TAG" >/dev/null || { echo "Frontend-Image epm-web:$TAG fehlt."; exit 1; }
      update_laeuft_setzen "zurueck $TAG"; trap aufraeumen_exit EXIT
      if ! starte_version "$TAG"; then echo "ABBRUCH: $TAG startet nicht (Backend nicht gesund)."; exit 1; fi
      echo "Zurückgeschaltet auf $TAG. Achtung: Datenbank-Migrationen werden dabei nicht zurückgedreht."
      exit 0 ;;
    --gut)
      TAG="${2:-$(env_wert EPM_VERSION)}"
      [[ "$TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40}$ ]] || { echo "Version „$TAG“ nicht erkannt."; exit 1; }
      version_vorhanden "$TAG" || { echo "Version $TAG ist nicht (vollständig) vorhanden."; exit 1; }
      gut_setzen "$TAG"
      exit 0 ;;
    --paket-erstellen) paket_erstellen; exit 0 ;;
    --paket) PAKET="${2:?Paketdatei angeben, z. B. sudo epm-update --paket ~/epm-paket-2.0.0-1a2b3c4.tar}"; shift ;;
    --ohne-tests) TESTS=0 ;;
    --ohne-signatur) OHNE_SIGNATUR=1 ;;
    *) sed -n '2,23p' "$0"; exit 1 ;;
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
  trap aufraeumen_exit EXIT
  # Erst nur Prüfsummen und Signatur auspacken und die Signatur prüfen; ab hier gilt nur diese geprüfte Liste.
  install -d -m 0700 "$TMP/pruefung" "$TMP/paket"
  tar -C "$TMP/pruefung" -xf "$PAKET" ./SHA256SUMS 2>/dev/null || { echo "ABBRUCH: Paket ohne Prüfsummen. Nichts wurde umgestellt."; exit 1; }
  tar -C "$TMP/pruefung" -xf "$PAKET" ./SHA256SUMS.sig 2>/dev/null || true
  ERSTMALS=0
  SCHLUESSEL=""
  if [[ -f "$SIGNATUR_VERTRAUT" ]]; then
    SCHLUESSEL="$SIGNATUR_VERTRAUT"
  elif [[ -s "$TMP/pruefung/SHA256SUMS.sig" ]] && tar -C "$TMP/pruefung" -xf "$PAKET" ./paket-signatur.pub 2>/dev/null; then
    SCHLUESSEL="$TMP/pruefung/paket-signatur.pub"   # erstes Paket: noch kein Schlüssel gespeichert
    ERSTMALS=1
  fi
  if [[ -n "$SCHLUESSEL" ]]; then
    [[ -s "$TMP/pruefung/SHA256SUMS.sig" ]] \
      || { echo "ABBRUCH: Paket ist nicht signiert (dieser Server verlangt eine Signatur). Nichts wurde umgestellt."; exit 1; }
    printf 'epm-paket %s\n' "$(head -n1 "$SCHLUESSEL")" > "$TMP/pruefung/erlaubt"
    ssh-keygen -Y verify -f "$TMP/pruefung/erlaubt" -I epm-paket -n epm-paket -s "$TMP/pruefung/SHA256SUMS.sig" \
      < "$TMP/pruefung/SHA256SUMS" >/dev/null \
      || { echo "ABBRUCH: Signatur des Pakets ungültig (anderer Schlüssel als gespeichert? Dann Administration › System ›"
           echo "   Software › „Paket-Schlüssel zurücksetzen“, wirksam nach 24 Stunden). Nichts wurde umgestellt."; exit 1; }
    if [[ $ERSTMALS -eq 1 ]]; then
      echo "   Signatur gültig (mitgelieferter Schlüssel – noch keiner gespeichert, er wird übernommen)"
    else
      echo "   Signatur gültig ($SIGNATUR_VERTRAUT)"
    fi
  elif [[ $OHNE_SIGNATUR -eq 1 ]]; then
    echo "   WARNUNG: Paket ohne Signatur, kein Schlüssel gespeichert – ohne Signaturprüfung (--ohne-signatur)."
  else
    echo "ABBRUCH: Das Paket ist nicht signiert (alte Test-VM?). Bitte auf der Test-VM ein neues Paket erstellen."
    echo "   Nur auf der Konsole und nur ohne gespeicherten Schlüssel: sudo epm-update --paket DATEI --ohne-signatur"
    exit 1
  fi
  tar -C "$TMP/paket" -xf "$PAKET"
  # nur Dateien und Ordner, und jede Datei muss in der geprüften Liste stehen
  if [[ -n "$(find "$TMP/paket" -mindepth 1 ! -type f ! -type d -print -quit)" ]] \
     || ! diff -q <(cd "$TMP/paket" && find . -type f ! -path ./SHA256SUMS ! -path ./SHA256SUMS.sig -printf '%P\n' | sort) \
                  <(sed 's/^[0-9a-f]\{64\}  //' "$TMP/pruefung/SHA256SUMS" | sort) >/dev/null \
     || ! (cd "$TMP/paket" && sha256sum --quiet --strict -c "$TMP/pruefung/SHA256SUMS"); then
    echo "ABBRUCH: Paket beschädigt oder verändert. Nichts wurde umgestellt."; exit 1
  fi
  if [[ $ERSTMALS -eq 1 ]]; then
    # geprüft: der Schlüssel steht in den signierten Prüfsummen und hat sie signiert
    install -m 0644 "$TMP/paket/paket-signatur.pub" "$SIGNATUR_VERTRAUT"
    echo "   Paket-Schlüssel erstmals übernommen: $(ssh-keygen -lf "$SIGNATUR_VERTRAUT" | cut -d' ' -f2)"
  fi
  TAG="$(tr -d '[:space:]' < "$TMP/paket/TAG")"
  [[ "$TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40}$ ]] || { echo "ABBRUCH: Version „$TAG“ nicht erkannt."; exit 1; }
  echo "   Version $TAG, Inhalt vollständig"

  schritt "Projektdateien aktualisieren (Compose, Nginx, Skripte, Systemagent)"
  rm -rf "$CODE"
  install -d -m 0750 "$CODE"
  cp -a "$TMP/paket/rollout" "$TMP/paket/werkzeuge" "$TMP/paket/VERSION" "$TMP/paket/TAG" "$CODE/"
  find "$CODE" -name '*.sh' -exec chmod +x {} +
  (cd "$CODE/rollout" && ./04-projekt.sh >/dev/null)
  install -m 0750 "$CODE/werkzeuge/epm-update.sh" /usr/local/sbin/epm-update

  schritt "Images laden (epm-backend:$TAG, epm-web:$TAG)"
  docker load -i "$TMP/paket/images.tar" | sed 's/^/   /'
  install -m 0600 "$TMP/paket/images.tar" "$B/images/epm-$TAG.tar"
  alte_entfernen 5 "/epm-paket- $(env_wert EPM_VERSION_GUT)" "$B"/images/epm-*.tar
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
# Versionsnummer zählt mit jeder Änderung auf main hoch (werkzeuge/version.sh); ältere Stände ohne das Skript: VERSION
if [[ -x "$CODE/werkzeuge/version.sh" ]]; then VER="$("$CODE/werkzeuge/version.sh" "$CODE")"; else VER="$(tr -d '[:space:]' < "$CODE/VERSION")"; fi
TAG="$VER-$NEU"
if [[ "$ALT" != "$NEU" ]]; then
  git -C "$CODE" log --oneline "$ALT..$NEU" | sed 's/^/   /'
else
  echo "   keine neuen Änderungen ($NEU)"
fi

schritt "Projektdateien aktualisieren (Compose, Nginx, Skripte)"
(cd "$CODE/rollout" && ./04-projekt.sh >/dev/null)
install -m 0750 "$CODE/werkzeuge/epm-update.sh" /usr/local/sbin/epm-update
install -m 0750 "$CODE/werkzeuge/ocr-modelle.sh" /usr/local/sbin/epm-ocr-modelle
install -m 0750 "$CODE/werkzeuge/ki.sh" /usr/local/sbin/epm-ki          # KI (Experimentell), 14.10.2026

# OCR-Modelle (PP-OCRv5, UVDoc): offline vorbereitet und mit „epm-ocr-modelle einspielen“ abgelegt → in den
# Bau-Kontext legen; der Bau übernimmt sie von dort statt sie von huggingface.co zu laden.
MODELLE_VORRAT="$B/ocr-modelle"
MODELLE_KONTEXT="$CODE/backend/scans/modelle/dateien"
MODELLE_DA=0
if [[ -d "$MODELLE_VORRAT" ]]; then
  # auch ein unvollständiger Vorrat hilft (z. B. vor einer neuen Datei in modelle.json): der Bau übernimmt, was die
  # Prüfsumme besteht, und lädt nur den Rest
  rm -rf "$MODELLE_KONTEXT"; mkdir -p "$MODELLE_KONTEXT"; cp -a "$MODELLE_VORRAT/." "$MODELLE_KONTEXT/"
  if python3 "$CODE/backend/scans/modelle/holen.py" --nur-pruefen "$MODELLE_VORRAT" >/dev/null 2>&1; then
    MODELLE_DA=1
  else
    echo "   OCR-Modelle: Vorrat unvollständig – fehlende Dateien lädt der Bau (sonst: epm-ocr-modelle neu vorbereiten)"
  fi
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
  # nur die letzten 5 Image-Dateien behalten (Update-Pakete für den VPS: die letzten 3); die gute Version immer
  alte_entfernen 5 "/epm-paket- $(env_wert EPM_VERSION_GUT)" "$B"/images/epm-*.tar
  alte_entfernen 3 "" "$B"/images/epm-paket-*.tar
fi

fi

VORHER="$(env_wert EPM_VERSION)"
# Erstes Update mit Selbstheilung: die bisher laufende Version gilt als gut, wenn ihre Images noch da sind
if [[ -z "$(env_wert EPM_VERSION_GUT)" && -n "$VORHER" ]] && version_vorhanden "$VORHER"; then gut_setzen "$VORHER"; fi
update_laeuft_setzen "update $TAG"; trap aufraeumen_exit EXIT

schritt "Backup vor dem Umstellen"
if (cd "$B" && docker compose ps --status running -q db | grep -q .); then
  /usr/local/sbin/epm-backup --art vor_update
fi

schritt "Version $TAG starten (Migrationen laufen automatisch)"
if ! umstellen_oder_zurueck "$TAG" "$VORHER"; then exit 1; fi
UMGESTELLT=1

ERGEBNIS=""
abschliessen "$TAG" "$VORHER" || true

echo
echo "────────────────────────────────────────────"
echo " EPM $TAG läuft – $ERGEBNIS"
echo " Gute Version (Rückfall der Selbstheilung): $(env_wert EPM_VERSION_GUT)"
echo " https://$EPM_WEB_NAME/"
echo " Zurück auf die vorige Version: sudo epm-update --versionen"
echo "────────────────────────────────────────────"
[[ "$ERGEBNIS" == "MUSTERDATEN FEHLGESCHLAGEN" ]] && exit 1
exit 0
