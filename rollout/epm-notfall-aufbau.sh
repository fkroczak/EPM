#!/usr/bin/env bash
# EPM – Wiederaufbau aus dem Notfallpaket (F188, docs/NOTFALLPLAN.md Teil C)
#
# Liegt im ausgepackten Notfallpaket ganz oben. Baut EPM auf einem frisch installierten Ubuntu Server (gleiche Version
# wie der alte Server) ohne Internet wieder auf: Prüfsummen, Debian-Pakete aus debs/, 01-basis.sh und 02-docker.sh im
# Offline-Modus (EPM_OFFLINE=1), CA (Schlüssel mit dem Sicherungs-Passwort entschlüsselt), 04-projekt.sh (Ordner, neue
# Secrets, Zertifikat, Systemagent), Images laden, EPM starten, Sicherung einspielen, Härtung (wenn ein SSH-Schlüssel
# hinterlegt ist).
#
#   sudo ./epm-notfall-aufbau.sh                 aufbauen (fragt nach dem Sicherungs-Passwort)
#   sudo ./epm-notfall-aufbau.sh --mit-internet  Pakete aus den Paketquellen statt aus debs/ (falls dort etwas fehlt)
#   ./epm-notfall-aufbau.sh --probelauf          nur prüfen und anzeigen, was geschähe (ohne root, ändert nichts)
#
# Mehrfach ausführbar: Nach einem Abbruch die Ursache beheben und erneut starten – erledigte Schritte schaden nicht.
# Das Sicherungs-Passwort kann auch über EPM_SICHERUNG_PASSWORT kommen (sonst wird es abgefragt, nie angezeigt).
set -euo pipefail
HIER="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROBE=0
ONLINE=0
for a in "$@"; do
  case "$a" in
    --probelauf) PROBE=1 ;;
    --mit-internet) ONLINE=1 ;;
    -h|--hilfe) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unbekannte Angabe: $a (siehe --hilfe)"; exit 2 ;;
  esac
done
[[ $PROBE -eq 1 || $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen: sudo ./epm-notfall-aufbau.sh"; exit 1; }

SCHRITT="Start"
schritt() { SCHRITT="$*"; echo; echo "==> $*"; }
trap 'echo; echo "ABBRUCH bei „$SCHRITT“ (Zeile $LINENO). Ursache beheben und das Skript erneut starten – erledigte Schritte schaden nicht."' ERR
# Befehl anzeigen und – außer im Probelauf – ausführen
tu() { echo "   \$ $*"; if [[ $PROBE -eq 1 ]]; then return 0; fi; "$@"; }
wert() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1]));
for k in sys.argv[2].split("."): d=(d or {}).get(k) if isinstance(d, dict) else None
print("" if d is None else d)' "$HIER/INHALT.json" "$1"; }

[[ $PROBE -eq 1 ]] && echo "PROBELAUF: Es wird nichts verändert."

schritt "1/11 Prüfsummen des Notfallpakets"
(cd "$HIER" && sha256sum --quiet -c SHA256SUMS) || { echo "Prüfsummen stimmen nicht – Paket beschädigt. Zweite Kopie nehmen."; exit 1; }
TAG="$(tr -d '[:space:]' < "$HIER/TAG")"
[[ "$TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40}$ ]] || { echo "Version im Paket nicht erkannt: $TAG"; exit 1; }
echo "   Prüfsummen in Ordnung · EPM $TAG · erstellt $(wert erstellt) auf $(wert rechner)"
FEHLT="$(python3 -c 'import json,sys; print("; ".join(json.load(open(sys.argv[1])).get("fehlt") or []))' "$HIER/INHALT.json")"
[[ -n "$FEHLT" ]] && echo "   Hinweis – im Paket fehlt: $FEHLT"

schritt "2/11 Ubuntu-Version"
SOLL="$(wert ubuntu.version_id)"
IST="$(. /etc/os-release && echo "${VERSION_ID:-}")"
echo "   Paket für Ubuntu ${SOLL:-?} · dieser Rechner: Ubuntu ${IST:-?}"
if [[ -n "$SOLL" && "$SOLL" != "$IST" && $ONLINE -eq 0 ]]; then
  echo "   WARNUNG: Die Debian-Pakete im Notfallpaket passen evtl. nicht. Besser Ubuntu $SOLL installieren"
  echo "   oder mit Internet aufbauen: sudo ./epm-notfall-aufbau.sh --mit-internet"
  if [[ $PROBE -eq 0 ]]; then read -rp "   Trotzdem fortfahren? (j/n) " antwort; [[ "$antwort" == j ]] || exit 1; fi
fi

schritt "3/11 Einstellungen (/etc/epm/epm.conf)"
if [[ ! -f /etc/epm/epm.conf ]]; then
  tu install -d -m 0755 /etc/epm
  tu install -m 0644 "$HIER/konfiguration/epm.conf" /etc/epm/epm.conf
fi
KONF=/etc/epm/epm.conf; [[ -f "$KONF" ]] || KONF="$HIER/konfiguration/epm.conf"
# shellcheck disable=SC1090
source "$KONF"
B="${EPM_BASE:-/srv/epm}"
echo "   Name $EPM_WEB_NAME · Netzwerkkarte $EPM_MGMT_IF · IP $EPM_MGMT_IP · Ordner $B"
if ! ip -br addr show "$EPM_MGMT_IF" 2>/dev/null | grep -q "${EPM_MGMT_IP%/*}"; then
  echo "   WARNUNG: Die Karte $EPM_MGMT_IF hat nicht die IP $EPM_MGMT_IP. Bitte /etc/epm/epm.conf bzw. Netplan anpassen"
  echo "   (Notfallplan B2/C4), sonst ist EPM nach dem Aufbau nicht erreichbar."
  if [[ $PROBE -eq 0 ]]; then read -rp "   Trotzdem fortfahren? (j/n) " antwort; [[ "$antwort" == j ]] || exit 1; fi
fi

schritt "4/11 Sicherungs-Passwort"
PASSWORT="${EPM_SICHERUNG_PASSWORT:-}"
if [[ -z "$PASSWORT" && $PROBE -eq 0 ]] && { [[ -f "$HIER/ca/epm-ca.key.gpg" ]] || compgen -G "$HIER/sicherung/*.tar" >/dev/null; }; then
  read -rsp "   Sicherungs-Passwort (vom Passwortblatt im Tresor; leer, wenn keins): " PASSWORT; echo
fi
echo "   ${PASSWORT:+erhalten (wird nicht angezeigt)}${PASSWORT:-keins angegeben}"

schritt "5/11 Debian-Pakete"
if [[ $ONLINE -eq 1 ]]; then
  export EPM_OFFLINE=0
  echo "   mit Internet: die Rollout-Skripte holen die Pakete aus den Paketquellen"
else
  export EPM_OFFLINE=1
  shopt -s nullglob
  DEBS=("$HIER"/debs/*.deb)
  shopt -u nullglob
  if [[ ${#DEBS[@]} -eq 0 ]]; then
    echo "   Im Notfallpaket sind keine Debian-Pakete. Mit Internet aufbauen: sudo ./epm-notfall-aufbau.sh --mit-internet"
    [[ $PROBE -eq 1 ]] || exit 1
  else
    echo "   ${#DEBS[@]} Pakete aus debs/ (ohne Internet)"
    tu apt-get install -y -q --no-install-recommends "${DEBS[@]}"
  fi
fi

schritt "6/11 Ubuntu einrichten und Docker (01-basis.sh, 02-docker.sh)"
tu "$HIER/rollout/01-basis.sh"
tu "$HIER/rollout/02-docker.sh"

schritt "7/11 Eigene Zertifizierungsstelle (CA)"
if [[ -f "$HIER/ca/epm-ca.key.gpg" && ! -s /etc/epm/ca/epm-ca.key ]]; then
  tu install -d -m 0700 /etc/epm/ca
  if [[ $PROBE -eq 0 ]]; then
    heim="$(mktemp -d)"
    printf '%s' "$PASSWORT" | gpg --homedir "$heim" --batch --quiet --pinentry-mode loopback --passphrase-fd 0 \
      -d -o /etc/epm/ca/epm-ca.key "$HIER/ca/epm-ca.key.gpg" \
      || { gpgconf --homedir "$heim" --kill all; rm -rf "$heim"; echo "   Das Passwort passt nicht zum CA-Schlüssel."; false; }
    gpgconf --homedir "$heim" --kill all 2>/dev/null || true; rm -rf "$heim"
    chmod 0600 /etc/epm/ca/epm-ca.key
  else
    echo "   \$ gpg -d ca/epm-ca.key.gpg > /etc/epm/ca/epm-ca.key   (mit dem Sicherungs-Passwort)"
  fi
  tu install -m 0644 "$HIER/ca/epm-ca.crt" /etc/epm/ca/epm-ca.crt
  echo "   Dieselbe CA wie bisher: Geräte, die ihr vertrauen, brauchen nichts Neues."
elif [[ -s /etc/epm/ca/epm-ca.key ]]; then
  echo "   CA schon vorhanden."
else
  echo "   Keine CA im Paket: 04-projekt.sh legt eine neue an – danach das neue Stammzertifikat auf allen Geräten"
  echo "   installieren (Notfallplan D1)."
fi

schritt "8/11 Projekt, Secrets, Zertifikat, Systemagent (04-projekt.sh)"
tu "$HIER/rollout/04-projekt.sh"
# Code-Ordner wie bei einem Update-Paket: epm-update kennt dann Version und Rollout-Dateien
tu install -d -m 0750 /srv/epm-code
for teil in rollout werkzeuge VERSION TAG; do
  [[ -e "$HIER/$teil" ]] && tu cp -a "$HIER/$teil" /srv/epm-code/
done
[[ -f "$HIER/werkzeuge/epm-update.sh" ]] && tu install -m 0750 "$HIER/werkzeuge/epm-update.sh" /usr/local/sbin/epm-update
[[ -f "$HIER/werkzeuge/ocr-modelle.sh" ]] && tu install -m 0750 "$HIER/werkzeuge/ocr-modelle.sh" /usr/local/sbin/epm-ocr-modelle

schritt "9/11 Programme laden und EPM starten"
tu docker load -i "$HIER/images/images.tar"
tu install -m 0600 "$HIER/images/images.tar" "$B/images/epm-$TAG.tar"
if [[ -d "$HIER/ocr-modelle" ]]; then
  tu install -d -m 0755 "$B/ocr-modelle"
  tu cp -a "$HIER/ocr-modelle/." "$B/ocr-modelle/"
fi
tu sed -i -e 's/^COMPOSE_FILE=.*/COMPOSE_FILE=compose.yaml/' -e "s/^EPM_VERSION=.*/EPM_VERSION=$TAG/" "$B/.env"
if [[ $PROBE -eq 0 ]]; then
  (cd "$B" && docker compose up -d --remove-orphans)
  status=""
  for _ in $(seq 1 100); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$(cd "$B" && docker compose ps -q backend)" 2>/dev/null || true)"
    [[ "$status" == "healthy" ]] && break
    sleep 3
  done
  [[ "$status" == "healthy" ]] || { (cd "$B" && docker compose logs --tail 40 backend); echo "   Backend startet nicht."; false; }
  echo "   EPM läuft."
else
  echo "   \$ docker compose up -d   (warten, bis das Backend bereit ist)"
fi

schritt "10/11 Sicherung einspielen"
shopt -s nullglob
SICHERUNGEN=("$HIER"/sicherung/*.tar)
shopt -u nullglob
if [[ ${#SICHERUNGEN[@]} -gt 0 ]]; then
  if [[ $PROBE -eq 0 ]]; then
    EPM_SICHERUNG_PASSWORT="$PASSWORT" /usr/local/sbin/epm-systemagent notfall-einspielen "${SICHERUNGEN[0]}"
  else
    echo "   \$ epm-systemagent notfall-einspielen ${SICHERUNGEN[0]##*/}   (mit dem Sicherungs-Passwort)"
  fi
else
  echo "   Keine Sicherung im Paket. Sicherung von der NAS/Nextcloud einspielen:"
  echo "   sudo epm-systemagent notfall-einspielen ~/epm-sicherung_<Zeitpunkt>.tar   (Notfallplan C6)"
fi

schritt "11/11 Härtung (SSH nur mit Schlüssel, Firewall)"
ADMIN_HOME="$(getent passwd "${EPM_ADMIN_USER:-epmadmin}" | cut -d: -f6 || true)"
if [[ -n "$ADMIN_HOME" && -s "$ADMIN_HOME/.ssh/authorized_keys" ]]; then
  tu "$HIER/rollout/03-security.sh"
else
  echo "   Übersprungen: Für ${EPM_ADMIN_USER:-epmadmin} ist noch kein SSH-Schlüssel hinterlegt. Später (Notfallplan D5):"
  echo "   ssh-copy-id ${EPM_ADMIN_USER:-epmadmin}@$EPM_MGMT_IP  und dann  sudo /srv/epm-code/rollout/03-security.sh"
fi

echo
echo "────────────────────────────────────────────"
if [[ $PROBE -eq 1 ]]; then
  echo " Probelauf beendet – das Notfallpaket ist vollständig lesbar."
else
  echo " EPM läuft wieder: https://$EPM_WEB_NAME/"
fi
echo " Weiter mit Notfallplan Teil C7 (prüfen) und Teil D (DNS, Übertragungsziel, neue Sicherung, Notfallpaket)."
echo "────────────────────────────────────────────"
