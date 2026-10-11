#!/usr/bin/env bash
# EPM – TLS-Zertifikat aus einer eigenen Zertifizierungsstelle (CA), Voraussetzung für Passkeys (Festlegung 08.10.2026)
#
# Passkeys funktionieren nur, wenn EPM über einen Namen (z. B. epm.stiftung.lan) mit einem Zertifikat aufgerufen
# wird, dem das Gerät vertraut – nicht über eine IP-Adresse und nicht mit einer Zertifikatswarnung. Dafür gibt es
# eine eigene CA: Ihr Stammzertifikat wird einmal auf jedem PC und Telefon installiert, danach gilt jedes von ihr
# ausgestellte EPM-Zertifikat ohne Warnung. Die CA darf per Namensbeschränkung NUR Zertifikate für den EPM-Namen
# (und die Verwaltungs-IP) ausstellen – ein verlorener CA-Schlüssel taugt so nicht für fremde Seiten.
#
#   sudo epm-zertifikat einrichten         CA anlegen (falls noch keine da ist) und Serverzertifikat ausstellen
#   sudo epm-zertifikat erneuern           neues Serverzertifikat derselben CA (z. B. jährlich, Gültigkeit 397 Tage)
#   sudo epm-zertifikat importieren CRT KEY [CA]   Zertifikat einer anderen CA (z. B. OPNsense) übernehmen
#   sudo epm-zertifikat status             Name, Aussteller, Ablauf
#
# Das Stammzertifikat liegt danach unter /etc/epm/ca/epm-ca.crt und ist im Browser unter https://<Name>/epm-ca.crt
# abrufbar (öffentlich, enthält keinen Schlüssel). Den CA-Schlüssel (/etc/epm/ca/epm-ca.key) mit dem Passwortblatt
# der Sicherung offline verwahren; ohne ihn lässt sich nur eine neue CA anlegen (dann alle Geräte neu einrichten).
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }
KONF=/etc/epm/epm.conf
[[ -f "$KONF" ]] || KONF="$(dirname "$0")/epm.conf"
[[ -f "$KONF" ]] || { echo "Keine epm.conf gefunden (/etc/epm/epm.conf)."; exit 1; }
# shellcheck disable=SC1090
source "$KONF"
B="${EPM_BASE:-/srv/epm}"
NAME="${EPM_WEB_NAME:?EPM_WEB_NAME fehlt in $KONF}"
IP="${EPM_MGMT_IP:-}"
CA=/etc/epm/ca
CERTS="$B/nginx/certs"
TAGE_SERVER=397          # Apple/Google akzeptieren höchstens 398 Tage
TAGE_CA=3650

ist_ip() { [[ "$1" =~ ^[0-9]+(\.[0-9]+){3}$ || "$1" == *:* ]]; }

pruefe_name() {
  if ist_ip "$NAME"; then
    echo "EPM_WEB_NAME ist eine IP-Adresse ($NAME). Für Passkeys bitte einen Namen eintragen (z. B. epm.stiftung.lan)"
    echo "und auf der OPNsense unter Dienste › Unbound DNS › Überschreibungen auf $IP zeigen lassen."
    exit 1
  fi
}

# Profil für iPhone/iPad mit dem Stammzertifikat (öffentlich, ohne Schlüssel): https://<Name>/epm-ca.mobileconfig
profil_schreiben() {
  [[ -s "$CERTS/epm-ca.crt" ]] || { rm -f "$CERTS/epm-ca.mobileconfig"; return 0; }
  local der uuid1 uuid2
  der=$(openssl x509 -in "$CERTS/epm-ca.crt" -outform der | base64 -w0)
  uuid1=$(cat /proc/sys/kernel/random/uuid); uuid2=$(cat /proc/sys/kernel/random/uuid)
  cat > "$CERTS/epm-ca.mobileconfig" <<PROFIL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>PayloadContent</key><array><dict>
    <key>PayloadCertificateFileName</key><string>epm-ca.crt</string>
    <key>PayloadContent</key><data>$der</data>
    <key>PayloadDisplayName</key><string>EPM Stammzertifikat</string>
    <key>PayloadIdentifier</key><string>epm.stammzertifikat.$uuid2</string>
    <key>PayloadType</key><string>com.apple.security.root</string>
    <key>PayloadUUID</key><string>$uuid2</string>
    <key>PayloadVersion</key><integer>1</integer>
  </dict></array>
  <key>PayloadDescription</key><string>Stammzertifikat für EPM ($NAME) – nötig für Passkeys und eine Verbindung ohne Warnung.</string>
  <key>PayloadDisplayName</key><string>EPM Stammzertifikat</string>
  <key>PayloadIdentifier</key><string>epm.profil.$uuid1</string>
  <key>PayloadType</key><string>Configuration</string>
  <key>PayloadUUID</key><string>$uuid1</string>
  <key>PayloadVersion</key><integer>1</integer>
</dict></plist>
PROFIL
  chmod 0444 "$CERTS/epm-ca.mobileconfig"
}

nginx_neu_laden() {
  profil_schreiben
  chown 101:101 "$CERTS"/epm.crt "$CERTS"/epm.key "$CERTS"/epm-ca.crt "$CERTS"/epm-ca.mobileconfig 2>/dev/null || true
  chmod 0400 "$CERTS/epm.key"; chmod 0444 "$CERTS/epm.crt"; [[ -f "$CERTS/epm-ca.crt" ]] && chmod 0444 "$CERTS/epm-ca.crt"
  if (cd "$B" && docker compose ps --status running -q web 2>/dev/null | grep -q .); then
    (cd "$B" && docker compose exec -T web nginx -s reload) && echo "   Nginx hat das neue Zertifikat geladen."
  fi
}

ca_anlegen() {
  install -d -m 0700 "$CA"
  if [[ -s "$CA/epm-ca.key" && -s "$CA/epm-ca.crt" ]]; then
    echo "   CA vorhanden: $(openssl x509 -in "$CA/epm-ca.crt" -noout -subject -enddate | tr '\n' ' ')"
    return
  fi
  echo "==> Eigene CA anlegen (10 Jahre, nur für $NAME${IP:+ und $IP})"
  local beschraenkung="permitted;DNS:$NAME"
  [[ -n "$IP" ]] && ! ist_ip "$NAME" && beschraenkung+=",permitted;IP:$IP/255.255.255.255"
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -sha256 -days "$TAGE_CA" -nodes \
    -keyout "$CA/epm-ca.key" -out "$CA/epm-ca.crt" \
    -subj "/CN=EPM Stiftung CA ($NAME)/O=EPM" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -addext "nameConstraints=critical,$beschraenkung" \
    -addext "subjectKeyIdentifier=hash" 2>/dev/null
  chmod 0600 "$CA/epm-ca.key"; chmod 0644 "$CA/epm-ca.crt"
}

server_ausstellen() {
  [[ -s "$CA/epm-ca.key" ]] || { echo "Keine CA vorhanden – zuerst: sudo epm-zertifikat einrichten"; exit 1; }
  echo "==> Serverzertifikat für $NAME (${TAGE_SERVER} Tage)"
  local tmp; tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' RETURN
  local san="DNS:$NAME"; [[ -n "$IP" ]] && san+=",IP:$IP"
  openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -keyout "$tmp/epm.key" -out "$tmp/epm.csr" \
    -subj "/CN=$NAME/O=EPM" 2>/dev/null
  cat > "$tmp/ext.cnf" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=$san
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
EOF
  openssl x509 -req -in "$tmp/epm.csr" -CA "$CA/epm-ca.crt" -CAkey "$CA/epm-ca.key" -CAcreateserial \
    -CAserial "$CA/epm-ca.srl" -sha256 -days "$TAGE_SERVER" -extfile "$tmp/ext.cnf" -out "$tmp/epm.crt" 2>/dev/null
  openssl verify -CAfile "$CA/epm-ca.crt" "$tmp/epm.crt" >/dev/null
  install -d -m 0750 -o 101 -g 101 "$CERTS"
  # Kette (Server + CA), damit Geräte, die nur die CA kennen, den Weg sofort finden
  cat "$tmp/epm.crt" "$CA/epm-ca.crt" > "$CERTS/epm.crt"
  install -m 0400 "$tmp/epm.key" "$CERTS/epm.key"
  install -m 0444 "$CA/epm-ca.crt" "$CERTS/epm-ca.crt"
  nginx_neu_laden
}

hinweise() {
  cat <<EOF

Fertig. Nächste Schritte (einmal je Gerät, Anleitung auch in EPM unter Hilfe › Passkey):
  1. DNS: Auf der OPNsense $NAME auf ${IP:-die Server-IP} zeigen lassen (Unbound › Überschreibungen).
  2. Stammzertifikat holen: https://$NAME/epm-ca.crt  (oder /etc/epm/ca/epm-ca.crt)
     Windows: Doppelklick › Zertifikat installieren › Lokaler Computer › „Vertrauenswürdige Stammzertifizierungsstellen“
     iPhone:  Profil laden › Einstellungen › Allgemein › VPN und Geräteverwaltung › installieren,
              danach Einstellungen › Allgemein › Info › Zertifikatsvertrauenseinstellungen › EPM CA einschalten
     Android: Einstellungen › Sicherheit › Verschlüsselung und Anmeldedaten › Zertifikat installieren › CA-Zertifikat
  3. EPM künftig über https://$NAME/ aufrufen (nicht mehr über die IP), dann unter Mein Konto einen Passkey anlegen.
  CA-Schlüssel /etc/epm/ca/epm-ca.key offline sichern (z. B. ausgedruckt/auf USB im Tresor).
EOF
}

status_zeigen() {
  local crt="$CERTS/epm.crt"
  [[ -s "$crt" ]] || { echo "Kein Zertifikat unter $crt."; exit 1; }
  echo "Zertifikat:  $(openssl x509 -in "$crt" -noout -subject | sed 's/^subject=//')"
  echo "Aussteller:  $(openssl x509 -in "$crt" -noout -issuer | sed 's/^issuer=//')"
  echo "Namen:       $(openssl x509 -in "$crt" -noout -ext subjectAltName 2>/dev/null | tail -n +2 | xargs)"
  echo "Gültig bis:  $(openssl x509 -in "$crt" -noout -enddate | cut -d= -f2)"
  if [[ -s "$CA/epm-ca.crt" ]] && openssl verify -CAfile "$CA/epm-ca.crt" <(openssl x509 -in "$crt") >/dev/null 2>&1; then
    echo "Eigene CA:   ja ($CA/epm-ca.crt) – Passkeys möglich über https://$NAME/"
  elif [[ "$(openssl x509 -in "$crt" -noout -subject)" == "$(openssl x509 -in "$crt" -noout -issuer | sed 's/^issuer/subject/')" ]]; then
    echo "Eigene CA:   nein, selbst signiert – Browser warnen, Passkeys gehen so nicht (sudo epm-zertifikat einrichten)"
  else
    echo "Eigene CA:   fremde CA (importiert)"
  fi
  if ! openssl x509 -in "$crt" -noout -checkend $((30*86400)) >/dev/null; then
    echo "WARNUNG: läuft in weniger als 30 Tagen ab – sudo epm-zertifikat erneuern"
  fi
}

case "${1:-status}" in
  einrichten) pruefe_name; ca_anlegen; server_ausstellen; status_zeigen; hinweise ;;
  erneuern)   pruefe_name; server_ausstellen; status_zeigen ;;
  importieren)
    crt="${2:?Zertifikat (PEM) angeben}"; key="${3:?Schlüssel (PEM) angeben}"; ca_datei="${4:-}"
    openssl x509 -in "$crt" -noout -checkhost "$NAME" | grep -q "does match" \
      || { echo "Das Zertifikat gilt nicht für $NAME."; exit 1; }
    [[ "$(openssl x509 -in "$crt" -noout -pubkey | openssl sha256)" == "$(openssl pkey -in "$key" -pubout | openssl sha256)" ]] \
      || { echo "Schlüssel und Zertifikat passen nicht zusammen."; exit 1; }
    install -d -m 0750 -o 101 -g 101 "$CERTS"
    if [[ -n "$ca_datei" ]]; then
      openssl verify -CAfile "$ca_datei" "$crt" >/dev/null || { echo "Zertifikat stammt nicht von dieser CA."; exit 1; }
      cat "$crt" "$ca_datei" > "$CERTS/epm.crt"; install -m 0444 "$ca_datei" "$CERTS/epm-ca.crt"
    else
      install -m 0444 "$crt" "$CERTS/epm.crt"
    fi
    install -m 0400 "$key" "$CERTS/epm.key"
    nginx_neu_laden; status_zeigen ;;
  status) status_zeigen ;;
  *) sed -n 2,16p "$0"; exit 1 ;;
esac
