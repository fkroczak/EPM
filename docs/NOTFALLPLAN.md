# EPM – Notfallplan: Wiederaufbau nach einem Ausfall

Stand 10.10.2026 · gilt für EPM mit Notfallpaket (F188). Diese Datei liegt im Notfallpaket als `NOTFALLPLAN.md` und
`NOTFALLPLAN.pdf`, im Repository unter `docs/NOTFALLPLAN.md` und in EPM unter Administration › System › Notfall.

**Wofür:** Der Server ist komplett ausgefallen (Platte defekt, VPS weg, Verschlüsselungstrojaner). EPM wird auf neuer
Hardware oder einer neuen VM wieder aufgebaut – **ohne Internet**, nur mit dem Notfallpaket, dem Ubuntu-
Installationsmedium und dem Passwortblatt aus dem Tresor.

**Wie lange:** etwa 1,5 bis 3 Stunden. Ubuntu installieren 30–45 Minuten, Aufbau aus dem Notfallpaket 20–40 Minuten,
Sicherung einspielen 10–60 Minuten (je nach Menge der Dokumente), Prüfen und Geräte 20 Minuten.

**Wer:** jemand mit IT-Grundwissen, der eine Tastatur am Server bedienen und Befehle abtippen kann. Befehle stehen
in grauen Kästen; Groß- und Kleinschreibung beachten.

---

## Teil A · Vorbereitung im Normalbetrieb (einmal einrichten, regelmäßig wiederholen)

1. **Notfallpaket erstellen** – in EPM unter Administration › System › Notfall: „Notfallpaket erstellen“ (Passwort und
   Code aus der Authenticator-App). Danach „Herunterladen“.
   - Erneut erstellen **nach jedem EPM-Update** und mindestens **alle 30 Tage** (die Ampel der Systemverwaltung
     erinnert daran).
   - Mit oder ohne die jüngste Sicherung: „mit Sicherung“ ist bequemer; wer die Sicherungen ohnehin getrennt (NAS,
     Nextcloud) aufbewahrt, kann sie weglassen.
2. **Notfallpaket lagern** – auf einem USB-Stick oder der NAS, **getrennt vom Server**, am besten zwei Kopien an zwei
   Orten. Die Datei heißt `epm-notfall-<Version>-<Datum>.tar`. Die angezeigte SHA-256 auf dem Zettel im Tresor notieren.
3. **Ubuntu-Installationsmedium** bereithalten: USB-Stick mit **Ubuntu Server in genau der Version des Servers** (steht
   im Notfallpaket in `INHALT.json` unter „ubuntu“ und in EPM unter System › Übersicht). Andere Versionen können mit
   den Paketen im Notfallpaket nicht zusammenpassen.
4. **Passwortblatt im Tresor**: das Sicherungs-Passwort (Administration › Backup › Verschlüsselung › Passwortblatt).
   Ohne dieses Passwort lässt sich keine Sicherung lesen – auch nicht vom Hersteller.
5. **Probe** einmal im Jahr: das Notfallpaket auf einer Test-VM aufbauen (Teil C), danach die Test-VM wieder löschen.

### Checkliste „Was ich im Notfall brauche“

- [ ] Notfallpaket `epm-notfall-….tar` (USB-Stick oder NAS) und die SHA-256 vom Zettel
- [ ] Ubuntu-Server-USB-Stick in der passenden Version
- [ ] Passwortblatt der Sicherung (Tresor)
- [ ] neue Hardware oder VM: mind. 4 Kerne, 8 GB RAM, Platte mind. doppelt so groß wie Dokumente + Sicherungen
- [ ] Zugang zur OPNsense (DNS-Eintrag, ggf. Zeitserver) und die IP-Adresse, unter der EPM erreichbar sein soll
- [ ] falls vorhanden: die jüngste Sicherung von der NAS/Nextcloud (`epm-sicherung_….tar`), wenn das Paket keine enthält
- [ ] SSH-Schlüssel des Admin-PCs (nur für Schritt 3 der Härtung; ohne ihn bleibt SSH vorerst so, wie Ubuntu es einrichtet)

---

## Teil B · Neue Hardware oder VM mit Ubuntu installieren

**Schritt B1 – Ubuntu Server installieren.** Vom USB-Stick starten, „Ubuntu Server“ wählen, Sprache Deutsch, Tastatur
Deutsch. Netzwerk: die Verwaltungs-Netzwerkkarte bekommt **dieselbe IP-Adresse wie der alte Server** (steht in
`konfiguration/epm.conf` als `EPM_MGMT_IP`). Benutzer `epmadmin` anlegen, „OpenSSH server“ ankreuzen, keine weiteren
Pakete („Featured snaps“ leer lassen).

- *Danach sehen Sie:* die Anmeldung `epm login:`.
- *Wenn nicht:* Netzwerk später mit `sudo nano /etc/netplan/50-cloud-init.yaml` einstellen und `sudo netplan apply`.

**Schritt B2 – anmelden und Netzwerkkarte prüfen.**

```
ip -brief addr
```

- *Danach sehen Sie:* eine Zeile mit der IP-Adresse aus `EPM_MGMT_IP`, z. B. `enp0s8 UP 192.168.56.10/24`. Den Namen
  der Karte (hier `enp0s8`) merken – er muss zu `EPM_MGMT_IF` passen.
- *Wenn nicht:* IP in Netplan eintragen (siehe B1).

---

## Teil C · EPM aus dem Notfallpaket aufbauen

**Schritt C1 – Notfallpaket auf den Server kopieren.** USB-Stick anstecken:

```
lsblk
sudo mkdir -p /mnt/usb && sudo mount /dev/sdb1 /mnt/usb
mkdir -p ~/notfall && cp /mnt/usb/epm-notfall-*.tar ~/notfall/
```

(`/dev/sdb1` aus der Ausgabe von `lsblk` nehmen: das Gerät mit der Größe des USB-Sticks.) Von der NAS geht es auch
per `scp` vom Admin-PC: `scp epm-notfall-….tar epmadmin@<IP>:~/notfall/`.

**Schritt C2 – Prüfsumme der Datei vergleichen.**

```
sha256sum ~/notfall/epm-notfall-*.tar
```

- *Danach sehen Sie:* eine lange Zeichenfolge – sie muss **genau** der SHA-256 vom Zettel bzw. aus EPM entsprechen.
- *Wenn nicht:* die Datei ist beschädigt oder nicht die richtige. Zweite Kopie nehmen.

**Schritt C3 – auspacken und Inhalt prüfen.**

```
cd ~/notfall && tar -xf epm-notfall-*.tar && sha256sum -c --quiet SHA256SUMS && echo PRUEFSUMMEN OK
```

- *Danach sehen Sie:* `PRUEFSUMMEN OK`.
- *Wenn nicht:* eine Zeile `… FEHLER` nennt die beschädigte Datei – zweite Kopie des Notfallpakets nehmen.

**Schritt C4 – Einstellungen prüfen.** Die Einstellungen des alten Servers liegen ohne Passwörter in
`konfiguration/epm.conf`:

```
nano ~/notfall/konfiguration/epm.conf
```

Prüfen bzw. anpassen: `EPM_MGMT_IF` (Name der Netzwerkkarte aus B2), `EPM_MGMT_IP`, `EPM_WEB_NAME`, `EPM_NTP_SERVER`.
Speichern mit Strg+O, Enter, Strg+X.

**Schritt C5 – Aufbau starten (ein Befehl).**

```
cd ~/notfall && sudo ./epm-notfall-aufbau.sh
```

Das Skript arbeitet ohne Internet und zeigt jeden Schritt an: Pakete aus `debs/` installieren (Docker und
Werkzeuge), Ubuntu einrichten (`01-basis.sh`), Docker (`02-docker.sh`), Projektordner, Secrets, Zertifikat, Systemagent
(`04-projekt.sh`), Programme laden (`docker load`), EPM starten. Es fragt nach dem **Sicherungs-Passwort** (vom
Passwortblatt) – damit wird die eigene Zertifizierungsstelle (CA) entschlüsselt und die Sicherung eingespielt.

- *Danach sehen Sie:* `EPM läuft wieder` und die Adresse `https://<EPM_WEB_NAME>/`.
- *Wenn nicht:* Das Skript nennt den Schritt, der fehlschlug. Häufige Ursachen:
  - „Pakete fehlen“: Die Ubuntu-Version passt nicht zum Paket (siehe `INHALT.json`), oder im Paket fehlten Pakete
    (Liste „fehlt“ in `INHALT.json`). Dann einmalig mit Internet: `sudo ./epm-notfall-aufbau.sh --mit-internet`.
  - „Backend startet nicht“: `cd /srv/epm && sudo docker compose logs --tail 50 backend` ansehen.
  - Das Skript lässt sich nach einer Korrektur **erneut starten**; erledigte Schritte schaden nicht.

**Schritt C6 – Sicherung einspielen** (macht das Skript selbst, wenn das Paket eine Sicherung enthält). Liegt die
Sicherung getrennt vor (NAS, Nextcloud: Datei `epm-sicherung_….tar`):

```
sudo epm-systemagent notfall-einspielen ~/epm-sicherung_<Zeitpunkt>.tar
```

Das Sicherungs-Passwort eingeben (vom Passwortblatt). Hat man nur die einzelnen Dateien aus der Nextcloud
(`epm-db_….dump.gpg`, `epm-dokumente_….tar.gz.gpg`, `epm_….sha256`, `epm_….json`), vorher zu einer Datei packen:
`tar -cf ~/epm-sicherung_<Zeitpunkt>.tar epm-db_… epm-dokumente_… epm_…`.

- *Danach sehen Sie:* `Sicherung wiederhergestellt`.
- *Wenn nicht:* „Passwort passt nicht“: anderes Passwortblatt (ältere Sicherungen haben evtl. ein älteres Passwort).

**Schritt C7 – prüfen.** Am Admin-PC `https://<EPM_WEB_NAME>/` öffnen (ggf. vorher Teil D1) und:

1. mit dem eigenen Benutzer anmelden – Passwort und Code aus der Authenticator-App gelten weiter;
2. eine Akte öffnen, ein Dokument ansehen;
3. unter Scans eine Testseite hochladen (Texterkennung);
4. Administration › Systemverwaltung: alle Kacheln grün bzw. nur bekannte Hinweise; Administration › Backup:
   „Jetzt sichern“.

---

## Teil D · Danach

**D1 – Name und Zertifikat.** Auf der OPNsense unter Dienste › Unbound DNS › Überschreibungen den EPM-Namen auf die
IP des neuen Servers zeigen lassen (meist bleibt alles gleich). War die eigene CA im Notfallpaket (verschlüsselt mit
dem Sicherungs-Passwort), hat das Skript nur ein neues Serverzertifikat derselben CA ausgestellt – **die Geräte merken
nichts**. Sonst wurde eine neue CA angelegt: Auf jedem PC und Telefon das neue Stammzertifikat
`https://<EPM_WEB_NAME>/epm-ca.crt` installieren (Anleitung in EPM unter Hilfe › „Passkey statt Code“). Passkeys gehen
weiter, solange der EPM-Name gleich bleibt.

**D2 – Übertragungsziel neu einrichten.** Administration › Backup › Übertragung › „Ziel festlegen“: Adresse, Benutzer
und Ordner stehen in `konfiguration/einstellungen.json`; das Passwort für das Ziel (App-Passwort der Nextcloud) neu
eingeben bzw. neu erzeugen.

**D3 – Zeitplan, Zeitserver, Aufbewahrung** wie in `konfiguration/einstellungen.json` einstellen (Administration ›
Backup › Zeitplan, System › Wartung › Uhrzeit).

**D4 – erste neue Sicherung** (Administration › Backup › „Jetzt sichern“) und danach ein **neues Notfallpaket**
erstellen und wegsichern.

**D5 – Härtung.** Den SSH-Schlüssel des Admin-PCs hinterlegen (`ssh-copy-id epmadmin@<IP>`), dann
`sudo /srv/epm-code/rollout/03-security.sh` (Firewall, nur Schlüssel). Das Aufbauskript überspringt diesen Schritt,
solange kein Schlüssel hinterlegt ist.

### Was neu entsteht, was bleibt

- **Neu erzeugt** (stehen absichtlich nicht im Notfallpaket): Datenbank-Passwort, Djangos geheimer Schlüssel
  (`/srv/epm/secrets/`). Folge: Alle Anmeldungen enden; **Passwörter, Authenticator-Codes, Notfall-Codes und Passkeys
  der Benutzer bleiben gültig** (sie stehen in der Datenbank bzw. auf den Geräten).
- **Nicht im Paket, aus dem Tresor:** Sicherungs-Passwort (Passwortblatt), Passwort des Übertragungsziels.
- **Aus der Sicherung:** alle Akten, Dokumente, Benutzer, Vorlagen, Einstellungen, das Audit-Log und die Löschliste
  (endgültig gelöschte Akten bleiben gelöscht).
- **Verloren** sind nur Eingaben nach dem Zeitpunkt der Sicherung und Scans, die noch nicht zugeordnet waren.

---

## Teil E · Wenn nur EPM kaputt ist, der Server aber läuft

Kein Neuaufbau nötig – alles in der Oberfläche:

1. **Nach einem Update geht etwas nicht:** Administration › System › Software › Versionen: „Zurückschalten“ auf die
   vorherige Version (vorher sichert der Server automatisch).
2. **Ein Dienst hängt** (z. B. Texterkennung): System › Wartung › Dienste › „Neu starten“.
3. **Fehler ansehen:** System › Protokolle (Container backend, Systemagent, Sicherung, Update).
4. **Daten sind falsch oder gelöscht:** Administration › Backup › Sicherungen › „Wiederherstellen“ bei der
   passenden Sicherung (Passwort und Code; vorher sichert der Server den jetzigen Stand).

Kommt man nicht mehr in die Oberfläche: per SSH `sudo epm-update --versionen` und `sudo epm-update --zurueck <Version>`.

## Teil F · Wenn nur die Datenbank kaputt ist

Symptom: EPM zeigt Fehler „500“ auf allen Seiten, im Protokoll des Backends stehen Datenbankfehler.

1. Administration › Backup › Sicherungen › jüngste unbeschädigte Sicherung › „Wiederherstellen“. Ersetzt Datenbank und
   Dokumente; die Löschliste bleibt.
2. Geht die Oberfläche gar nicht mehr: per SSH die Sicherung über den Systemagenten einspielen:
   `sudo epm-systemagent notfall-einspielen /srv/epm/system/download/epm-sicherung_<Zeitpunkt>.tar` (die Datei zuvor
   unter Backup › „Herunterladen“ bereitgestellt bzw. von der NAS kopiert).
3. Danach „Jetzt sichern“ und den Fehler (Protokoll) an die Betreuung geben.

---

## Notfall-Checkliste zum Ausdrucken

| ✓ | Schritt | Befehl / Ort |
|---|---|---|
| ☐ | Notfallpaket, Ubuntu-Stick, Passwortblatt bereit | Tresor, NAS/USB |
| ☐ | Ubuntu Server (gleiche Version) installieren, IP wie bisher, Benutzer epmadmin | B1 |
| ☐ | Netzwerkkarte prüfen | `ip -brief addr` |
| ☐ | Paket kopieren | `cp /mnt/usb/epm-notfall-*.tar ~/notfall/` |
| ☐ | SHA-256 mit Zettel vergleichen | `sha256sum ~/notfall/epm-notfall-*.tar` |
| ☐ | Auspacken und prüfen | `tar -xf … && sha256sum -c --quiet SHA256SUMS` |
| ☐ | Einstellungen prüfen (Karte, IP, Name) | `nano konfiguration/epm.conf` |
| ☐ | Aufbau starten, Sicherungs-Passwort eingeben | `sudo ./epm-notfall-aufbau.sh` |
| ☐ | Anmelden, Akte öffnen, Testscan, Ampel | Browser |
| ☐ | DNS auf der OPNsense, ggf. neue CA auf Geräte | D1 |
| ☐ | Übertragungsziel neu (Passwort des Ziels) | D2 |
| ☐ | Jetzt sichern, neues Notfallpaket erstellen | D4 |
| ☐ | SSH-Schlüssel, Härtung | D5 |

Dauer gesamt: etwa 1,5 bis 3 Stunden.
