#!/usr/bin/env python3
"""
EPM – Systemagent auf dem Server (Administration › System und › Backup).

Das Backend läuft im Container ohne Zugriff auf den Server. Es legt Aufträge als JSON-Dateien in
``<EPM_BASE>/system/auftraege/`` ab; dieser Agent (root, systemd) führt nur die unten fest eingetragenen
Aktionen aus und schreibt Status und Ergebnisse nach ``<EPM_BASE>/system/status/`` (für den Container nur lesbar).

    epm-systemagent status      Auslastung, Updates, Container, Sicherungen messen (Timer, jede Minute); stößt im
                                Zeitfenster die Übertragung der Sicherungen an
    epm-systemagent auftraege   wartende Aufträge ausführen (systemd-Pfad-Einheit, sobald eine Datei da ist)
    epm-systemagent uebertragen verschlüsselte Sicherungen zum Ziel übertragen (vom Status-Lauf angestoßen)
    epm-systemagent schleife    Status und Aufträge fortlaufend (Browsertests in CI, ohne systemd)

Optionen: --basis DIR (statt EPM_BASE aus /etc/epm/epm.conf), --projekt NAME (Compose-Projekt),
          --konf DIR (Passwort und Übertragungsziel der Sicherungen, Standard /etc/epm/sicherung),
          --backup-skript DATEI (Standard /usr/local/sbin/epm-backup),
          --trocken (nichts verändern: Updates, Neustart, Sicherung und Aufräumen nur simulieren),
          --sicherung-echt (mit --trocken: Sicherung, Übertragung und Wiederherstellen trotzdem echt – CI).

Sicherheit: Aus einer Auftragsdatei werden nur „aktion“ (feste Liste) und deren fest vorgesehene, geprüfte Angaben
verwendet (Minuten, Benutzername, Stempel einer oder mehrerer Sicherungen, Sicherungs-Passwort, Übertragungsziel,
Version, Dienst, Kennung eines Uploads, Protokoll und Zeilenzahl, Zertifikat als PEM) – jeweils gegen ein festes Muster
bzw. eine feste Liste geprüft. Nichts davon wird als Befehl oder über eine Shell ausgeführt; Passwörter und Schlüssel
gehen nur in Dateien (0600, root) bzw. über die Standardeingabe an rclone und stehen nie in Ergebnissen oder Ausgaben.
Dateien werden ohne Folgen symbolischer Links gelesen und nach dem Lesen sofort gelöscht. Hochgeladene Pakete und
Modelle werden vor der Prüfung in einen Ordner kopiert, den das Backend nicht beschreiben kann.
"""
import argparse
import fcntl
from collections import deque
import hashlib
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

VERSION = 6  # 5: Systemverwaltung ohne SSH (10.10.2026); 6: Zeitplan der Sicherung, Journal und Images aufräumen, Uhrzeit
KONF = "/etc/epm/epm.conf"
BACKUP_SKRIPT = "/usr/local/sbin/epm-backup"
KONF_SICHERUNG = "/etc/epm/sicherung"
VERLAUF_PUNKTE = 1440            # 24 Stunden bei einer Messung je Minute
# Verlauf über längere Zeiträume (Administration › System: 7 Tage bis 6 Monate): Mittelwerte in gröberen Stufen,
# dazu die Spitzen von CPU und Arbeitsspeicher. (Name, Sekunden je Punkt, Anzahl Punkte)
VERLAUF_STUFEN = (("viertelstunde", 900, 1344),   # 14 Tage
                  ("stunde", 3600, 744),           # 31 Tage
                  ("vierteltag", 21600, 736))      # 184 Tage
VERLAUF_FELDER = ["zeit", "cpu", "ram", "last", "platte"]
AUFBEWAHRUNG_TAGE = (7, 14, 30)  # wählbar unter Administration › Backup (Festlegung 02.10.2026)
# Aufbewahrung im Übertragungsziel (Festlegung 03.10.2026): Standard 30 Tage, 0 = nie löschen
ZIEL_AUFBEWAHRUNG = (0, 14, 30, 60, 90, 180, 365)
ZIEL_AUFBEWAHRUNG_STANDARD = 30
BUENDEL_MUSTER = re.compile(r"^epm-sicherung_(\d{4}-\d{2}-\d{2}_\d{4}(?:\d{2})?)\.tar$")
BUENDEL_STUNDEN = 2              # so lange liegt eine zum Herunterladen bereitgestellte Sicherung bereit
UPLOAD_ALT_STUNDEN = 24          # abgebrochene Uploads werden danach entfernt
AUSGABE_MAX = 20000              # Zeichen Ausgabe je Auftrag
ERGEBNISSE_BEHALTEN = 200
ID_MUSTER = re.compile(r"^[0-9a-f]{32}$")
STEMPEL_MUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}(\d{2})?$")
BENUTZER_MUSTER = re.compile(r"^[A-Za-z0-9_.@+-]{1,150}$")
ZEIT_MUSTER = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATEI_MUSTER = re.compile(
    r"^epm-(db|dokumente|loeschliste)_(\d{4}-\d{2}-\d{2}_\d{4}(?:\d{2})?)\.(dump|tar\.gz|jsonl)(\.gpg|\.age)?$")
NEBEN_MUSTER = re.compile(r"^epm_(\d{4}-\d{2}-\d{2}_\d{4}(?:\d{2})?)\.(sha256|json)$")
PASSWORT_MIN, PASSWORT_MAX = 16, 200
UEBERTRAGUNG_WIEDERHOLEN_S = 15 * 60
ARTEN = ("nachts", "von_hand", "vor_update", "vor_aenderung", "vor_wiederherstellung", "vor_leeren", "hochgeladen")
APP_UID, APP_GID = 10001, 101

# Aktion -> (Bezeichnung, vorher sichern). Dieselbe Liste steht in backend/system/host.py.
AKTIONEN = {
    "status_aktualisieren": ("Status neu einlesen", False),
    "updates_suchen": ("Nach Updates suchen", False),
    "updates_installieren": ("Ubuntu-Updates installieren", True),
    "server_neustart": ("Server neu starten", True),
    "epm_neustart": ("EPM neu starten", False),
    "epm_update": ("EPM aktualisieren", False),   # epm-update sichert selbst, bevor es umstellt
    "sicherung": ("Sicherung erstellen", False),
    "docker_aufraeumen": ("Docker aufräumen", False),
    "pakete_aufraeumen": ("Paketreste entfernen", False),
    # Administration › Backup
    "sicherung_passwort": ("Sicherungs-Passwort festlegen", False),
    "sicherung_ziel": ("Übertragungsziel festlegen", False),
    "sicherung_ziel_entfernen": ("Übertragungsziel entfernen", False),
    "sicherung_ziel_testen": ("Verbindung zum Übertragungsziel testen", False),
    "sicherung_uebertragen": ("Sicherungen jetzt übertragen", False),
    "sicherung_aufbewahrung": ("Aufbewahrung der Sicherungen festlegen", False),
    "sicherung_bereitstellen": ("Sicherung zum Herunterladen bereitstellen", False),
    "sicherung_einlesen": ("Hochgeladene Sicherung einlesen", False),
    "wiederherstellen": ("Sicherung wiederherstellen", True),
    # Administration › System: Ende der Testphase (U27)
    "datenbank_leeren": ("Datenbank leeren", True),
    # Systemverwaltung ohne SSH (10.10.2026, F179)
    "sicherung_loeschen": ("Sicherungen löschen", False),
    "dienst_neustart": ("Dienst neu starten", False),
    "epm_zurueck": ("EPM-Version zurückschalten", True),
    "epm_paket": ("Update-Paket einspielen", False),           # epm-update sichert selbst, bevor es umstellt
    "epm_paket_erstellen": ("Update-Paket erstellen", False),
    "zertifikat_erneuern": ("Zertifikat erneuern", False),
    "zertifikat_importieren": ("Zertifikat importieren", False),
    "ocr_modelle": ("OCR-Modelle einspielen", False),
    "protokoll": ("Protokoll abrufen", False),
    # Nachtrag 10.10.2026 (F179l–F179n)
    "sicherung_zeitplan": ("Zeitplan der Sicherung festlegen", False),
    "journal_aufraeumen": ("Journal aufräumen", False),
    "images_loeschen": ("Alte Versionen löschen", False),
    "uhr_einstellen": ("Uhrzeit einstellen", False),
}
# Aktionen, die Sicherungen schreiben, übertragen oder zurückspielen – und das Leeren der Datenbank, das nur den
# EPM-Stack betrifft: mit --sicherung-echt auch im Probelauf echt (Browsertests gegen den echten Stack)
SICHERUNG_AKTIONEN = {"sicherung", "sicherung_passwort", "sicherung_ziel", "sicherung_ziel_entfernen",
                      "sicherung_ziel_testen", "sicherung_uebertragen", "sicherung_aufbewahrung",
                      "sicherung_bereitstellen", "sicherung_einlesen", "wiederherstellen", "datenbank_leeren",
                      "sicherung_loeschen"}
# (sicherung_zeitplan ändert systemd auf dem Server und bleibt deshalb auch mit --sicherung-echt ein Probelauf)
# Art der Sicherung, die eine Aktion vorher erstellt
VORHER_ART = {"updates_installieren": "vor_update", "server_neustart": "vor_aenderung",
              "wiederherstellen": "vor_wiederherstellung", "datenbank_leeren": "vor_leeren", "epm_zurueck": "vor_update"}

# Systemverwaltung ohne SSH (10.10.2026): feste Werkzeuge auf dem Server, feste Dienste, feste Protokolle
EPM_UPDATE = "/usr/local/sbin/epm-update"
EPM_ZERTIFIKAT = "/usr/local/sbin/epm-zertifikat"
EPM_OCR_MODELLE = "/usr/local/sbin/epm-ocr-modelle"
CA_ORDNER = "/etc/epm/ca"
LOESCHEN_MAX = 200                # Sicherungen je Auftrag „Sicherungen löschen“
TAG_MUSTER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40}$")
PAKET_MUSTER = re.compile(r"^epm-paket-([0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40})\.tar$")
DIENSTE = ("backend", "web", "ocr", "db")
# Protokolle (nur lesend): Quelle -> Bezeichnung. Container über docker compose logs, Dienste über journalctl,
# das Update über seine Protokolldatei. Andere Quellen gibt es nicht.
PROTOKOLLE = {
    "backend": "Container backend (Django)", "web": "Container web (Nginx)", "ocr": "Container ocr (Texterkennung)",
    "db": "Container db (PostgreSQL)", "systemagent": "Systemagent", "backup": "Nächtliche Sicherung",
    "uebertragung": "Übertragung der Sicherungen", "update": "Letztes EPM-Update (/var/log/epm-update.log)",
}
PROTOKOLL_JOURNAL = {"systemagent": ["epm-systemagent.service", "epm-systemstatus.service"],
                     "backup": ["epm-backup.service"], "uebertragung": ["epm-uebertragung.service"]}
PROTOKOLL_ZEILEN = (100, 500, 2000)
PROTOKOLL_STUNDEN = 1             # so lange liegt ein abgerufenes Protokoll für die Oberfläche bereit
PROTOKOLL_MAX = 2 * 1024 * 1024   # Bytes je abgerufenem Protokoll
PEM_MAX = 20000                   # Zeichen je PEM-Datei beim Zertifikat-Import
# Inhalt eines Update-Pakets (epm-update --paket-erstellen) und der vorbereiteten OCR-Modelle: nur diese Namen,
# nur Dateien und Ordner – keine Verweise, keine absoluten Pfade, kein „..“
PAKET_INHALT = re.compile(r"^(TAG|VERSION|SHA256SUMS|images\.tar|(rollout|werkzeuge)(/[A-Za-z0-9._+-]+)*)$")
OCR_INHALT = re.compile(r"^(modelle\.json|dateien(/[A-Za-z0-9._+-]+)*)$")
# Zeitplan der nächtlichen Sicherung (Drop-in für epm-backup.timer): Uhrzeit HH:MM, nur diese Wochentag-Muster
ZEITPLAN_TAGE = {"taeglich": "*-*-*", "werktags": "Mon..Fri *-*-*"}
ZEITPLAN_STANDARD = {"uhrzeit": "02:00", "tage": "taeglich"}
ZEITPLAN_DATEI = "epm-backup.timer.d/zeitplan.conf"
# Journal aufräumen: feste Auswahl (journalctl --vacuum-size / --vacuum-time)
JOURNAL_GROESSE = ("100M", "200M", "500M", "1G")
JOURNAL_ZEIT = ("2weeks", "1month", "3months", "6months")
JOURNAL_CACHE_S = 15 * 60
# Image-Dateien unter <EPM_BASE>/images: gespeicherte Images je Version und Update-Pakete
IMAGE_DATEI_MUSTER = re.compile(r"^epm-(paket-)?([0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40})\.tar$")
# Uhrzeit: Zeitzone wie „Europe/Berlin“, Zeitserver als Name oder IP-Adresse, Zeit „JJJJ-MM-TT HH:MM:SS“
ZEITZONE_MUSTER = re.compile(r"^[A-Za-z]+(/[A-Za-z0-9_+-]+){0,2}$|^UTC$")
NTP_SERVER_MUSTER = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}"
                               r"[A-Za-z0-9])?$|^[0-9a-fA-F:]{2,39}$")
NTP_SERVER_MAX = 4
ZEIT_SETZEN_MUSTER = re.compile(r"^20[2-9][0-9]-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]) ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$")

APT_ENV = {"DEBIAN_FRONTEND": "noninteractive", "NEEDRESTART_MODE": "a", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}


def stempel_zeit(stempel):
    """„2026-10-03_0200“ bzw. „…_020000“ → datetime (UTC, wie der Server die Sicherung benannt hat: Ortszeit wird
    hier nicht gebraucht – es geht um Tage) oder None."""
    for form in ("%Y-%m-%d_%H%M%S", "%Y-%m-%d_%H%M"):
        try:
            return datetime.strptime(stempel, form).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return None


def im_ziel_veraltet(namen, tage, jetzt=None):
    """Welche Dateien im Übertragungsziel älter als ``tage`` sind und entfernt werden: nur Dateien von EPM-Sicherungen
    (Namen wie im Backup-Ordner), nach dem Zeitstempel im Namen; die jüngste Sicherung im Ziel bleibt immer, alles
    andere im Ordner wird nie angefasst. ``tage`` 0 = nie löschen."""
    if not tage:
        return []
    jetzt = jetzt or datetime.now(timezone.utc)
    je_stempel = {}
    for name in namen:
        name = name.strip()
        m = DATEI_MUSTER.match(name)
        stempel = m.group(2) if m else (NEBEN_MUSTER.match(name).group(1) if NEBEN_MUSTER.match(name) else None)
        if stempel and stempel_zeit(stempel):
            je_stempel.setdefault(stempel, []).append(name)
    if not je_stempel:
        return []
    juengste = max(je_stempel, key=stempel_zeit)
    grenze = jetzt - timedelta(days=tage)
    return sorted(n for st, liste in je_stempel.items() if st != juengste and stempel_zeit(st) < grenze for n in liste)


def jetzt_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def zeit_aus(text):
    try:
        return datetime.fromisoformat(text) if text else None
    except (TypeError, ValueError):
        return None


def lese_konf(pfad=KONF):
    werte = {}
    try:
        with open(pfad, encoding="utf-8") as f:
            for zeile in f:
                m = re.match(r'^\s*([A-Z_][A-Z0-9_]*)=["\']?([^"\'#]*)["\']?', zeile)
                if m:
                    werte[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    return werte


def im_zeitfenster(von, bis, jetzt=None):
    """„02:00“–„03:00“; über Mitternacht („23:00“–„01:00“) möglich; von == bis heißt: ganztägig."""
    jetzt = jetzt or datetime.now()
    m = jetzt.hour * 60 + jetzt.minute
    a = int(von[:2]) * 60 + int(von[3:])
    b = int(bis[:2]) * 60 + int(bis[3:])
    if a == b:
        return True
    return a <= m < b if a < b else (m >= a or m < b)


def fenster_rest_s(von, bis, jetzt=None):
    """Sekunden bis zum Ende des laufenden Zeitfensters (für rclone --max-duration)."""
    jetzt = jetzt or datetime.now()
    a = int(von[:2]) * 60 + int(von[3:])
    b = int(bis[:2]) * 60 + int(bis[3:])
    if a == b:
        return None
    ende = jetzt.replace(hour=b // 60, minute=b % 60, second=0, microsecond=0)
    if ende <= jetzt:
        ende += timedelta(days=1)
    return int((ende - jetzt).total_seconds())


def naechstes_fenster(von, bis, jetzt=None):
    jetzt = jetzt or datetime.now()
    if im_zeitfenster(von, bis, jetzt):
        return jetzt
    beginn = jetzt.replace(hour=int(von[:2]), minute=int(von[3:]), second=0, microsecond=0)
    if beginn <= jetzt:
        beginn += timedelta(days=1)
    return beginn


class Agent:
    def __init__(self, basis, projekt=None, trocken=False, konf=None, backup_skript=None, sicherung_echt=False):
        self.basis = basis
        self.projekt = projekt
        self.trocken = trocken
        self.sicherung_echt = sicherung_echt
        self.konf = konf or KONF_SICHERUNG
        self.backup_skript = backup_skript or BACKUP_SKRIPT
        self.auftraege = os.path.join(basis, "system", "auftraege")
        self.status = os.path.join(basis, "system", "status")
        self.ergebnisse = os.path.join(self.status, "auftraege")
        self.backup = os.path.join(basis, "backup")
        # Austausch mit dem Backend: bereitgestellte Sicherungen (liest Nginx aus) und hochgeladene (schreibt das Backend)
        self.download = os.path.join(basis, "system", "download")
        self.upload = os.path.join(basis, "system", "upload")
        # abgerufene Protokolle (Administration › System › Protokolle): nur für das Backend lesbar, nach 1 Stunde weg
        self.protokolle = os.path.join(self.status, "protokolle")
        # Systemdateien (in den Tests eigene Ordner): Drop-ins für Timer und Zeitsynchronisation
        self.systemd = "/etc/systemd/system"
        self.timesyncd = "/etc/systemd/timesyncd.conf.d"
        self.chrony = "/etc/chrony"
        einstellungen = lese_konf()
        self.proxy = einstellungen.get("EPM_APT_PROXY", "")
        try:
            self.app_uid = int(einstellungen.get("EPM_APP_UID") or APP_UID)
        except ValueError:
            self.app_uid = APP_UID
        for d in (self.status, self.ergebnisse):
            os.makedirs(d, mode=0o755, exist_ok=True)

    def simuliert(self, aktion):
        return self.trocken and not (self.sicherung_echt and aktion in SICHERUNG_AKTIONEN)

    # ------------------------------------------------------------ Hilfen
    def schreibe(self, pfad, daten, modus=0o644, kompakt=False):
        """Atomar schreiben (für den Container lesbar: 0644; Geheimes 0600)."""
        tmp = f"{pfad}.tmp{os.getpid()}"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, modus)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if kompakt:
                json.dump(daten, f, ensure_ascii=False, separators=(",", ":"), default=str)
            else:
                json.dump(daten, f, ensure_ascii=False, indent=1, default=str)
        os.chmod(tmp, modus)
        os.replace(tmp, pfad)

    def lies(self, pfad, standard=None):
        try:
            with open(pfad, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return standard

    def befehl(self, args, env=None, cwd=None, zeitlimit=3600, eingabe=None):
        """Befehl ausführen, Ausgabe (stdout+stderr) und Rückgabe liefern. Nie über eine Shell."""
        umgebung = dict(os.environ)
        umgebung.update(env or {})
        try:
            p = subprocess.run(args, cwd=cwd, env=umgebung, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, errors="replace", timeout=zeitlimit, check=False, input=eingabe)
            return p.returncode, p.stdout
        except FileNotFoundError:
            return 127, f"Programm nicht gefunden: {args[0]}\n"
        except subprocess.TimeoutExpired as e:
            aus = e.stdout or ""
            if isinstance(aus, bytes):
                aus = aus.decode(errors="replace")
            return 124, aus + f"\nAbgebrochen nach {zeitlimit} s\n"

    def compose(self, *args):
        basis = ["docker", "compose"] + (["-p", self.projekt] if self.projekt else [])
        return basis + list(args)

    # ------------------------------------------------------------ Messungen
    @staticmethod
    def cpu_prozent(dauer=1.0):
        def lesen():
            with open("/proc/stat") as f:
                werte = [int(x) for x in f.readline().split()[1:]]
            leer = werte[3] + (werte[4] if len(werte) > 4 else 0)
            return sum(werte), leer
        try:
            g1, l1 = lesen()
            time.sleep(dauer)
            g2, l2 = lesen()
            return round(100.0 * (1 - (l2 - l1) / max(1, g2 - g1)), 1)
        except (OSError, ValueError, IndexError):
            return None

    @staticmethod
    def speicher():
        werte = {}
        try:
            with open("/proc/meminfo") as f:
                for zeile in f:
                    name, rest = zeile.split(":", 1)
                    werte[name] = int(rest.split()[0]) * 1024
        except (OSError, ValueError):
            return None
        return {"gesamt": werte.get("MemTotal"), "verfuegbar": werte.get("MemAvailable"),
                "swap_gesamt": werte.get("SwapTotal"), "swap_frei": werte.get("SwapFree")}

    @staticmethod
    def platte(pfad, bezeichnung):
        try:
            s = os.statvfs(pfad)
        except OSError:
            return None
        return {"pfad": pfad, "bezeichnung": bezeichnung, "gesamt": s.f_blocks * s.f_frsize,
                "frei": s.f_bavail * s.f_frsize, "geraet": os.stat(pfad).st_dev}

    @staticmethod
    def groesse(pfad):
        gesamt = 0
        for wurzel, _ordner, dateien in os.walk(pfad, followlinks=False):
            for d in dateien:
                try:
                    gesamt += os.lstat(os.path.join(wurzel, d)).st_size
                except OSError:
                    pass
        return gesamt

    @staticmethod
    def betriebssystem():
        name = ""
        try:
            with open("/etc/os-release") as f:
                for zeile in f:
                    if zeile.startswith("PRETTY_NAME="):
                        name = zeile.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return name

    def updates(self):
        """Ausstehende Pakete aus einer Simulation (apt-get -s); zwischengespeichert, solange sich die Paketlisten
        und der Paketstand nicht ändern."""
        listen = "/var/lib/apt/lists"
        dpkg = "/var/lib/dpkg/status"
        try:
            schluessel = [os.stat(listen).st_mtime, os.stat(dpkg).st_mtime]
        except OSError:
            return {"verfuegbar": False, "hinweis": "Kein apt auf diesem System."}
        cache_pfad = os.path.join(self.status, ".apt-cache.json")
        cache = self.lies(cache_pfad) or {}
        if cache.get("schluessel") == schluessel and cache.get("updates"):
            return cache["updates"]
        rc, aus = self.befehl(["apt-get", "-s", "-o", "Debug::NoLocking=true", "upgrade", "--with-new-pkgs"],
                              env=APT_ENV, zeitlimit=300)
        pakete = []
        for zeile in aus.splitlines():
            m = re.match(r"^Inst (\S+)(?: \[([^\]]+)\])? \((\S+) (.*)\)", zeile)
            if m:
                pakete.append({"name": m.group(1), "von": m.group(2) or "", "nach": m.group(3),
                               "sicherheit": "-security" in m.group(4)})
        zurueck = []
        m = re.search(r"kept back:\n((?:  .*\n)+)", aus)
        if m:
            zurueck = m.group(1).split()
        geprueft = None
        for stempel in ("/var/lib/apt/periodic/update-success-stamp", listen):
            try:
                geprueft = datetime.fromtimestamp(os.stat(stempel).st_mtime, timezone.utc).astimezone().isoformat(
                    timespec="seconds")
                break
            except OSError:
                continue
        ergebnis = {
            "verfuegbar": rc == 0,
            "anzahl": len(pakete),
            "sicherheit": sum(1 for p in pakete if p["sicherheit"]),
            "pakete": pakete[:300],
            "zurueckgehalten": zurueck[:50],
            "listen_am": geprueft,
            "berechnet_am": jetzt_iso(),
            "hinweis": "" if rc == 0 else (aus.strip().splitlines() or [""])[-1][:300],
        }
        self.schreibe(cache_pfad, {"schluessel": schluessel, "updates": ergebnis})
        return ergebnis

    def container(self):
        rc, aus = self.befehl(self.compose("ps", "--all", "--format", "json"), cwd=self.basis, zeitlimit=30)
        if rc != 0:
            return {"verfuegbar": False, "liste": [], "hinweis": aus.strip()[-300:]}
        liste = []
        zeilen = aus.strip()
        eintraege = []
        if zeilen.startswith("["):
            try:
                eintraege = json.loads(zeilen)
            except ValueError:
                eintraege = []
        else:
            for zeile in zeilen.splitlines():
                try:
                    eintraege.append(json.loads(zeile))
                except ValueError:
                    pass
        for e in eintraege:
            liste.append({"dienst": e.get("Service", ""), "name": e.get("Name", ""), "zustand": e.get("State", ""),
                          "gesundheit": e.get("Health", ""), "image": e.get("Image", ""), "status": e.get("Status", "")})
        return {"verfuegbar": True, "liste": sorted(liste, key=lambda x: x["dienst"])}

    def sicherung(self):
        """Kurzfassung für Administration › System (Einzelheiten in sicherung.json)."""
        if not os.path.isdir(self.backup):
            return {"verfuegbar": False}
        liste = self.sicherungen()
        gesamt = self.groesse(self.backup)
        if not liste:
            return {"verfuegbar": True, "anzahl": 0, "gesamt": gesamt, "letzte_am": None}
        letzte = liste[0]
        return {"verfuegbar": True, "anzahl": len(liste), "gesamt": gesamt, "letzte_am": letzte["zeitpunkt"],
                "letzte_groesse": letzte["groesse"], "letzte_verschluesselt": letzte["verschluesselt"]}

    def dienste(self):
        ergebnis = {}
        for name in ("docker", "epm.service", "epm-backup.timer", "epm-systemstatus.timer", "epm-systemagent.path"):
            _rc, aus = self.befehl(["systemctl", "is-active", name], zeitlimit=10)
            wert = (aus.strip().splitlines() or [""])[0]
            ergebnis[name] = wert if wert in ("active", "inactive", "failed", "activating", "deactivating") \
                else "unbekannt"
        return ergebnis

    # ------------------------------------------------------------ Systemverwaltung ohne SSH: Stand (10.10.2026)
    def epm_versionen(self):
        """Vorhandene EPM-Versionen (Images epm-backend und epm-web) für „Zurückschalten“, die laufende aus .env."""
        aktiv = ""
        try:
            with open(os.path.join(self.basis, ".env"), encoding="utf-8") as f:
                for z in f:
                    if z.startswith("EPM_VERSION="):
                        aktiv = z.split("=", 1)[1].strip().strip("\"'")
        except OSError:
            pass
        quelle = lese_konf().get("EPM_UPDATE_QUELLE") or "git"
        je_tag = {}
        for image in ("epm-backend", "epm-web"):
            rc, aus = self.befehl(["docker", "image", "ls", image, "--format", "{{.Tag}}\t{{.CreatedAt}}"], zeitlimit=30)
            if rc != 0:
                return {"verfuegbar": False, "aktiv": aktiv, "quelle": quelle, "liste": [],
                        "hinweis": (aus.strip().splitlines() or [""])[-1][:200]}
            for z in aus.splitlines():
                tag, _, erstellt = z.partition("\t")
                tag = tag.strip()
                if not TAG_MUSTER.match(tag):
                    continue
                e = je_tag.setdefault(tag, {"tag": tag, "erstellt": "", "backend": False, "web": False})
                e[image[4:]] = True
                if image == "epm-backend":
                    e["erstellt"] = erstellt.strip()
        liste = sorted(je_tag.values(), key=lambda e: (e["erstellt"], e["tag"]), reverse=True)[:30]
        for e in liste:
            e["aktiv"] = e["tag"] == aktiv
            e["vollstaendig"] = e["backend"] and e["web"]
        return {"verfuegbar": True, "aktiv": aktiv, "quelle": quelle, "liste": liste}

    def pakete(self):
        """Update-Pakete: erstellte unter images/, zum Herunterladen bereitgestellte unter system/download/."""
        def liste(ordner, stunden=None):
            ergebnis = []
            try:
                namen = sorted(os.listdir(ordner))
            except OSError:
                return ergebnis
            for n in namen:
                m = PAKET_MUSTER.match(n)
                if not m:
                    continue
                try:
                    info = os.lstat(os.path.join(ordner, n))
                except OSError:
                    continue
                if not stat.S_ISREG(info.st_mode):
                    continue
                e = {"tag": m.group(1), "datei": n, "groesse": info.st_size,
                     "zeit": datetime.fromtimestamp(info.st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds")}
                if stunden:
                    e["bis"] = datetime.fromtimestamp(info.st_mtime + stunden * 3600, timezone.utc).astimezone().isoformat(
                        timespec="seconds")
                ergebnis.append(e)
            return ergebnis
        return {"erstellt": liste(os.path.join(self.basis, "images")), "bereit": liste(self.download, BUENDEL_STUNDEN)}

    def zertifikat(self):
        """Serverzertifikat (Nginx): Name, Aussteller, Ablauf – ob eine eigene CA da ist (erneuern möglich) und ob das
        Stammzertifikat unter /epm-ca.crt abrufbar ist."""
        certs = os.path.join(self.basis, "nginx", "certs")
        crt = os.path.join(certs, "epm.crt")
        ergebnis = {"vorhanden": os.path.isfile(crt), "name": lese_konf().get("EPM_WEB_NAME", ""),
                    "ca_schluessel": os.path.isfile(os.path.join(CA_ORDNER, "epm-ca.key")),
                    "ca_download": os.path.isfile(os.path.join(certs, "epm-ca.crt"))}
        if not ergebnis["vorhanden"]:
            return ergebnis
        rc, aus = self.befehl(["openssl", "x509", "-in", crt, "-noout", "-subject", "-issuer", "-enddate", "-startdate"],
                              env={"LC_ALL": "C"}, zeitlimit=15)
        if rc != 0:
            ergebnis["hinweis"] = "Zertifikat nicht lesbar."
            return ergebnis
        werte = {}
        for z in aus.splitlines():
            k, _, v = z.partition("=")
            werte[k.strip()] = v.strip()
        ergebnis.update({"inhaber": werte.get("subject", ""), "aussteller": werte.get("issuer", "")})
        for feld, schluessel in (("gueltig_bis", "notAfter"), ("gueltig_ab", "notBefore")):
            try:
                z = datetime.strptime(" ".join(werte.get(schluessel, "").split()), "%b %d %H:%M:%S %Y %Z")
                ergebnis[feld] = z.replace(tzinfo=timezone.utc).astimezone().isoformat(timespec="seconds")
            except ValueError:
                ergebnis[feld] = None
        if ergebnis.get("gueltig_bis"):
            ergebnis["tage"] = int((datetime.fromisoformat(ergebnis["gueltig_bis"]) - datetime.now(timezone.utc))
                                   .total_seconds() // 86400)
        rc, aus = self.befehl(["openssl", "x509", "-in", crt, "-noout", "-ext", "subjectAltName"], zeitlimit=15)
        ergebnis["namen"] = " ".join(aus.splitlines()[1:]).strip()[:500] if rc == 0 else ""
        ergebnis["selbst_signiert"] = bool(ergebnis["inhaber"]) and ergebnis["inhaber"] == ergebnis["aussteller"]
        ergebnis["eigene_ca"] = False
        ca = os.path.join(CA_ORDNER, "epm-ca.crt")
        if os.path.isfile(ca):
            rc, _aus = self.befehl(["openssl", "verify", "-CAfile", ca, crt], zeitlimit=15)
            ergebnis["eigene_ca"] = rc == 0
        return ergebnis

    def uhr(self):
        rc, aus = self.befehl(["timedatectl", "show", "-p", "NTPSynchronized", "-p", "NTP", "-p", "Timezone"], zeitlimit=10)
        werte = dict(z.split("=", 1) for z in aus.splitlines() if "=" in z) if rc == 0 else {}
        return {"verfuegbar": rc == 0, "synchronisiert": werte.get("NTPSynchronized") == "yes",
                "ntp": werte.get("NTP") == "yes", "zeitzone": werte.get("Timezone", ""),
                "zeit_unix": time.time(), "server": self.ntp_server(), "dienst": self.ntp_dienst(),
                "zeitzonen": self.zeitzonen()}

    def ntp_dienst(self):
        """chrony (Ubuntu-Server mit chrony) oder systemd-timesyncd"""
        return "chrony" if os.path.isdir(os.path.join(self.chrony, "sources.d")) else "timesyncd"

    def ntp_server(self):
        """Eingetragene Zeitserver (von rollout/01-basis.sh bzw. aus der Oberfläche)"""
        if self.ntp_dienst() == "chrony":
            pfad, muster = os.path.join(self.chrony, "sources.d", "epm.sources"), re.compile(r"^\s*(?:server|pool)\s+(\S+)")
        else:
            pfad, muster = os.path.join(self.timesyncd, "epm.conf"), None
        try:
            with open(pfad, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return []
        if muster:
            return [m.group(1) for m in (muster.match(z) for z in text.splitlines()) if m]
        m = re.search(r"^NTP=(.*)$", text, re.M)
        return m.group(1).split() if m else []

    def zeitzonen(self):
        """Erlaubte Zeitzonen (timedatectl list-timezones), einmal je Tag gelesen"""
        cache = os.path.join(self.status, ".zeitzonen.json")
        daten = self.lies(cache) or {}
        if daten.get("liste") and time.time() - daten.get("zeit", 0) < 86400:
            return daten["liste"]
        rc, aus = self.befehl(["timedatectl", "list-timezones"], zeitlimit=20)
        liste = [z.strip() for z in aus.splitlines() if ZEITZONE_MUSTER.match(z.strip())] if rc == 0 else []
        if liste:
            self.schreibe(cache, {"zeit": time.time(), "liste": liste}, kompakt=True)
        return liste

    def journal(self):
        """Belegung des Journals (journalctl --disk-usage), höchstens alle 15 Minuten gemessen"""
        cache = os.path.join(self.status, ".journal.json")
        daten = self.lies(cache) or {}
        if daten.get("zeit") and time.time() - daten["zeit"] < JOURNAL_CACHE_S:
            return daten.get("journal")
        rc, aus = self.befehl(["journalctl", "--disk-usage"], zeitlimit=30)
        m = re.search(r"take up ([0-9.]+)([KMGT]?)", aus)
        if rc != 0 or not m:
            ergebnis = {"verfuegbar": False}
        else:
            faktor = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}[m.group(2)]
            ergebnis = {"verfuegbar": True, "groesse": int(float(m.group(1)) * faktor)}
        self.schreibe(cache, {"zeit": time.time(), "journal": ergebnis})
        return ergebnis

    def geschuetzte_tags(self, versionen=None):
        """Laufende und vorherige Version (für „Zurückschalten“) – nie löschen. Ohne Liste der Versionen: None."""
        v = versionen or self.epm_versionen()
        if not v.get("verfuegbar") or not v.get("aktiv"):
            return None
        tags = [e["tag"] for e in v["liste"]]
        geschuetzt = {v["aktiv"]}
        if v["aktiv"] in tags:
            i = tags.index(v["aktiv"])
            if i + 1 < len(tags):
                geschuetzt.add(tags[i + 1])
        else:
            geschuetzt.update(tags[:1])
        return geschuetzt

    def image_dateien(self, versionen=None):
        """Image-Dateien und Update-Pakete unter images/ mit Version, Größe und Schutz"""
        geschuetzt = self.geschuetzte_tags(versionen) or set()
        ordner = os.path.join(self.basis, "images")
        liste = []
        try:
            namen = sorted(os.listdir(ordner))
        except OSError:
            return liste
        for n in namen:
            m = IMAGE_DATEI_MUSTER.match(n)
            if not m:
                continue
            try:
                info = os.lstat(os.path.join(ordner, n))
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            liste.append({"datei": n, "tag": m.group(2), "art": "paket" if m.group(1) else "images", "groesse": info.st_size,
                          "zeit": datetime.fromtimestamp(info.st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds"),
                          "geschuetzt": m.group(2) in geschuetzt})
        return sorted(liste, key=lambda e: e["zeit"], reverse=True)

    def zeitplan(self):
        """Zeitplan der nächtlichen Sicherung aus dem Drop-in (sonst Standard 02:00 täglich)"""
        try:
            with open(os.path.join(self.systemd, ZEITPLAN_DATEI), encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return {**ZEITPLAN_STANDARD, "eingestellt": False}
        m = re.search(r"^OnCalendar=(Mon\.\.Fri )?\*-\*-\* ([0-2][0-9]:[0-5][0-9])", text, re.M)
        if not m:
            return {**ZEITPLAN_STANDARD, "eingestellt": False}
        return {"uhrzeit": m.group(2), "tage": "werktags" if m.group(1) else "taeglich", "eingestellt": True}

    def ocr_vorrat(self):
        """Offline eingespielte Modelle der zweiten Texterkennung (epm-ocr-modelle einspielen)."""
        ordner = os.path.join(self.basis, "ocr-modelle")
        anzahl, groesse, neu = 0, 0, 0.0
        for wurzel, _ordner, dateien in os.walk(ordner, followlinks=False):
            for d in dateien:
                try:
                    info = os.lstat(os.path.join(wurzel, d))
                except OSError:
                    continue
                anzahl += 1
                groesse += info.st_size
                neu = max(neu, info.st_mtime)
        return {"vorhanden": anzahl > 0, "dateien": anzahl, "groesse": groesse,
                "geaendert": datetime.fromtimestamp(neu, timezone.utc).astimezone().isoformat(timespec="seconds")
                if neu else None}

    @staticmethod
    def werkzeuge():
        return {"epm_update": os.path.exists(EPM_UPDATE), "epm_zertifikat": os.path.exists(EPM_ZERTIFIKAT),
                "epm_ocr_modelle": os.path.exists(EPM_OCR_MODELLE)}

    def status_schreiben(self):
        try:
            with open("/proc/uptime") as f:
                laufzeit = int(float(f.read().split()[0]))
        except (OSError, ValueError):
            laufzeit = None
        cpu = self.cpu_prozent()
        speicher = self.speicher()
        platten, geraete = [], set()
        for pfad, bez in (("/", "System"), (self.basis, "EPM-Daten"), ("/var/lib/docker", "Docker")):
            p = self.platte(pfad, bez)
            if p and p["geraet"] not in geraete:
                geraete.add(p["geraet"])
                platten.append(p)
        for p in platten:
            p.pop("geraet", None)
        neustart_pakete = []
        try:
            with open("/var/run/reboot-required.pkgs") as f:
                neustart_pakete = sorted(set(f.read().split()))
        except OSError:
            pass
        status = {
            "version": VERSION,
            "zeit": jetzt_iso(),
            "rechner": socket.gethostname(),
            "system": self.betriebssystem(),
            "kernel": os.uname().release,
            "laufzeit_s": laufzeit,
            "cpu": {"kerne": os.cpu_count(), "last": [round(x, 2) for x in os.getloadavg()], "prozent": cpu},
            "speicher": speicher,
            "platten": platten,
            "groessen": {
                "dokumente": self.groesse(os.path.join(self.basis, "data", "dokumente")),
                "sicherungen": self.groesse(self.backup),
                "images": self.groesse(os.path.join(self.basis, "images")),
            },
            "updates": self.updates(),
            "neustart_noetig": os.path.exists("/var/run/reboot-required"),
            "neustart_pakete": neustart_pakete,
            "container": self.container(),
            "sicherung": self.sicherung(),
            "dienste": self.dienste(),
            # Systemverwaltung ohne SSH (10.10.2026)
            "versionen": self.epm_versionen(),
            "pakete": self.pakete(),
            "zertifikat": self.zertifikat(),
            "uhr": self.uhr(),
            "ocr_vorrat": self.ocr_vorrat(),
            "werkzeuge": self.werkzeuge(),
            "journal": self.journal(),
            "image_dateien": self.image_dateien(),
            "protokolle": [{"quelle": q, "name": n} for q, n in PROTOKOLLE.items()],
            "trocken": self.trocken,
        }
        self.schreibe(os.path.join(self.status, "system.json"), status)
        self.verlauf_ergaenzen(status)
        try:
            self.austausch_aufraeumen()
            self.sicherung_status_schreiben()
            self.passwoerter_aufraeumen()
            self.uebertragung_anstossen()
        except Exception as e:  # noqa: BLE001 – der Status der Maschine soll trotzdem stehen
            print(f"Sicherung: {e}", file=sys.stderr)
        return status

    def verlauf_ergaenzen(self, status):
        pfad = os.path.join(self.status, "verlauf.json")
        verlauf = self.lies(pfad) or {}
        punkte = verlauf.get("punkte") or []
        sp = status.get("speicher") or {}
        ram = None
        if sp.get("gesamt") and sp.get("verfuegbar") is not None:
            ram = round(100.0 * (1 - sp["verfuegbar"] / sp["gesamt"]), 1)
        daten = next((p for p in status["platten"] if p["bezeichnung"] == "EPM-Daten"), None) or (
            status["platten"][0] if status["platten"] else None)
        platte = round(100.0 * (1 - daten["frei"] / daten["gesamt"]), 1) if daten and daten["gesamt"] else None
        punkte.append([int(time.time()), status["cpu"]["prozent"], ram, status["cpu"]["last"][0], platte])
        punkte = punkte[-VERLAUF_PUNKTE:]
        stufen = self.verlauf_stufen(verlauf.get("stufen"), punkte)  # 7 Tage bis 6 Monate
        self.schreibe(pfad, {"felder": VERLAUF_FELDER, "punkte": punkte, "stufen": stufen}, kompakt=True)

    @staticmethod
    def verlauf_stufen(stufen, punkte):
        """Gröbere Stufen fortschreiben: Je Stufe wird der laufende Abschnitt (z. B. die Viertelstunde, in die die
        letzte Messung fällt) aus den Minutenwerten neu gemittelt – Mittelwert je Feld, dazu die Spitzen von CPU und
        Arbeitsspeicher. Fehlende Werte (None) zählen nicht mit."""
        stufen = stufen if isinstance(stufen, dict) else {}
        ergebnis = {}
        for name, sekunden, anzahl in VERLAUF_STUFEN:
            alt = stufen.get(name) if isinstance(stufen.get(name), dict) else {}
            liste = [p for p in (alt.get("punkte") or []) if isinstance(p, list) and len(p) == 7]
            # ab dem letzten gespeicherten Abschnitt neu rechnen (beim ersten Mal: alles aus den Minutenwerten)
            ab = liste[-1][0] if liste else 0
            abschnitte = {}
            for p in punkte:
                beginn = p[0] - p[0] % sekunden
                if beginn >= ab:
                    abschnitte.setdefault(beginn, []).append(p)
            for beginn in sorted(abschnitte):
                teil = abschnitte[beginn]

                def mittel(i, teil=teil):
                    werte = [p[i] for p in teil if p[i] is not None]
                    return round(sum(werte) / len(werte), 2) if werte else None

                def spitze(i, teil=teil):
                    werte = [p[i] for p in teil if p[i] is not None]
                    return max(werte) if werte else None

                punkt = [beginn, mittel(1), mittel(2), mittel(3), mittel(4), spitze(1), spitze(2)]
                if liste and liste[-1][0] == beginn:
                    liste[-1] = punkt
                else:
                    liste.append(punkt)
            ergebnis[name] = {"sekunden": sekunden, "felder": VERLAUF_FELDER + ["cpu_max", "ram_max"],
                              "punkte": liste[-anzahl:]}
        return ergebnis

    # ------------------------------------------------------------ Sicherungen: Bestand
    def sicherungen(self):
        """Alle Sicherungen im Backup-Ordner, neueste zuerst – aus den Angaben je Sicherung (epm_<Stempel>.json) bzw.,
        für ältere Sicherungen ohne diese Datei, aus den Dateinamen."""
        try:
            namen = os.listdir(self.backup)
        except OSError:
            return []
        gruppen = {}
        for n in namen:
            m = DATEI_MUSTER.match(n)
            if m:
                g = gruppen.setdefault(m.group(2), {"dateien": {}, "json": False, "sha256": False})
                g["dateien"][m.group(1)] = n
                continue
            m = NEBEN_MUSTER.match(n)
            if m:
                g = gruppen.setdefault(m.group(1), {"dateien": {}, "json": False, "sha256": False})
                g[m.group(2)] = True
        uebertragen = (self.uebertragung_stand().get("uebertragen") or {})
        ziel = self.ziel_lesen()
        kennung = self.ziel_kennung(ziel) if ziel else None
        liste = []
        for stempel, g in gruppen.items():
            if "db" not in g["dateien"]:
                continue
            meta = self.lies(os.path.join(self.backup, f"epm_{stempel}.json")) if g["json"] else None
            meta = meta if isinstance(meta, dict) else {}
            groesse = 0
            for name in g["dateien"].values():
                try:
                    groesse += os.stat(os.path.join(self.backup, name)).st_size
                except OSError:
                    pass
            db = g["dateien"]["db"]
            verschluesselt = db.endswith(".gpg") or db.endswith(".age")
            try:
                zeitpunkt = meta.get("zeitpunkt") or datetime.fromtimestamp(
                    os.stat(os.path.join(self.backup, db)).st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds")
            except OSError:
                zeitpunkt = None
            uebertragen_am = (uebertragen.get(kennung) or {}).get(stempel) if kennung else None
            liste.append({
                "stempel": stempel,
                "zeitpunkt": zeitpunkt,
                "art": meta.get("art") if meta.get("art") in ARTEN else "unbekannt",
                "ausgeloest_von": meta.get("ausgeloest_von") or "",
                "verschluesselt": verschluesselt,
                "verfahren": "gpg" if db.endswith(".gpg") else ("age" if db.endswith(".age") else ""),
                "passwort_nr": meta.get("passwort_nr") if isinstance(meta.get("passwort_nr"), int) else None,
                "groesse": groesse,
                "dateien": sorted(g["dateien"].values()),
                "dokumente": "dokumente" in g["dateien"],
                "loeschliste": "loeschliste" in g["dateien"],
                "pruefsummen": g["sha256"],
                "epm_version": meta.get("epm_version") or "",
                "uebertragen_am": uebertragen_am,
            })
        liste.sort(key=lambda s: (s["zeitpunkt"] or "", s["stempel"]), reverse=True)
        return liste

    # ------------------------------------------------------------ Sicherungen: Passwort
    def passwort_stand(self):
        stand = self.lies(os.path.join(self.konf, "passwort.json")) or {}
        if not isinstance(stand.get("versionen"), list):
            stand = {"aktuell": None, "versionen": []}
        return stand

    def konf_ordner(self):
        os.makedirs(self.konf, mode=0o700, exist_ok=True)
        os.chmod(self.konf, 0o700)

    def passwort_setzen(self, passwort, von, zeile):
        if not isinstance(passwort, str) or not (PASSWORT_MIN <= len(passwort) <= PASSWORT_MAX) \
                or any(z in passwort for z in "\r\n\0"):
            return 2, f"Das Passwort muss {PASSWORT_MIN} bis {PASSWORT_MAX} Zeichen lang sein (ohne Zeilenumbruch)."
        self.konf_ordner()
        stand = self.passwort_stand()
        nr = max([v.get("nr", 0) for v in stand["versionen"]] + [0]) + 1
        pfad = os.path.join(self.konf, f"passwort-{nr}")
        fd = os.open(pfad, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(passwort)
        salz = os.urandom(16)
        wert = hashlib.scrypt(passwort.encode(), salt=salz, n=2 ** 14, r=8, p=1, dklen=32)
        stand["versionen"].append({"nr": nr, "gesetzt_am": jetzt_iso(), "gesetzt_von": von or "",
                                   "pruefwert": {"verfahren": "scrypt", "n": 2 ** 14, "r": 8, "p": 1,
                                                 "salz": salz.hex(), "wert": wert.hex()}})
        stand["aktuell"] = nr
        self.schreibe(os.path.join(self.konf, "passwort.json"), stand, modus=0o600)
        tmp = os.path.join(self.konf, f".aktuell.{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f"{nr}\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, os.path.join(self.konf, "aktuell"))
        zeile(f"Passwort Nr. {nr} gespeichert (nur für root lesbar). Es gilt ab der nächsten Sicherung.\n")
        self.sicherung_status_schreiben()
        return 0, f"Sicherungs-Passwort Nr. {nr} festgelegt. Es gilt ab der nächsten Sicherung."

    def passwort_datei(self, nr):
        pfad = os.path.join(self.konf, f"passwort-{nr}")
        return pfad if os.path.isfile(pfad) else None

    def passwoerter_aufraeumen(self):
        """Ältere Passwörter werden gebraucht, solange es Sicherungen damit gibt (30 Tage); danach entfernt."""
        stand = self.passwort_stand()
        if not stand["versionen"]:
            return
        benutzt = {s["passwort_nr"] for s in self.sicherungen() if s["passwort_nr"]}
        geaendert = False
        for v in stand["versionen"]:
            nr = v.get("nr")
            if nr == stand.get("aktuell") or nr in benutzt or v.get("entfernt_am"):
                continue
            pfad = os.path.join(self.konf, f"passwort-{nr}")
            try:
                os.unlink(pfad)
            except FileNotFoundError:
                pass
            v["entfernt_am"] = jetzt_iso()
            geaendert = True
        if geaendert:
            self.schreibe(os.path.join(self.konf, "passwort.json"), stand, modus=0o600)

    # ------------------------------------------------------------ Sicherungen: Übertragungsziel
    def ziel_lesen(self):
        ziel = self.lies(os.path.join(self.konf, "ziel.json"))
        return ziel if isinstance(ziel, dict) and ziel.get("url") else None

    @staticmethod
    def ziel_kennung(ziel):
        return hashlib.sha256(f"{ziel.get('url')}|{ziel.get('benutzer')}|{ziel.get('ordner')}".encode()).hexdigest()[:12]

    @staticmethod
    def ziel_pruefen(p):
        """Angaben aus der Oberfläche prüfen; Rückgabe (fehlertext | None, bereinigte Angaben)."""
        url = str(p.get("url") or "").strip()
        teile = urlsplit(url)
        lokal = teile.hostname in ("localhost", "127.0.0.1", "::1")
        if teile.scheme not in ("https", "http") or not teile.hostname or (teile.scheme == "http" and not lokal) \
                or teile.username or teile.password or teile.query or teile.fragment or len(url) > 500 \
                or any(z in url for z in " \r\n\t\"'\\"):
            return "Bitte die WebDAV-Adresse mit https:// angeben (ohne Benutzer und Passwort in der Adresse).", None
        benutzer = str(p.get("benutzer") or "").strip()
        if not benutzer or len(benutzer) > 200 or any(z in benutzer for z in "\r\n\t\0"):
            return "Bitte den Benutzernamen angeben.", None
        ordner = str(p.get("ordner") or "").strip().strip("/")
        if len(ordner) > 300 or any(z in ordner for z in "\r\n\t\0\\:") or ".." in ordner.split("/"):
            return "Der Ordner darf keine Sonderzeichen wie \\ : .. enthalten.", None
        von, bis = str(p.get("von") or ""), str(p.get("bis") or "")
        if not ZEIT_MUSTER.match(von) or not ZEIT_MUSTER.match(bis):
            return "Bitte das Zeitfenster als Uhrzeit angeben (z. B. 02:00 bis 03:00).", None
        kennwort = p.get("kennwort")
        if kennwort is not None and (not isinstance(kennwort, str) or len(kennwort) > 500
                                     or any(z in kennwort for z in "\r\n\0")):
            return "Das Passwort für das Ziel ist ungültig.", None
        tage = p.get("aufbewahrung_tage", ZIEL_AUFBEWAHRUNG_STANDARD)
        if isinstance(tage, bool) or tage not in ZIEL_AUFBEWAHRUNG:
            return "Aufbewahrung im Ziel: bitte nie, 14, 30, 60, 90, 180 oder 365 Tage wählen.", None
        return None, {"url": url.rstrip("/"), "benutzer": benutzer, "ordner": ordner, "von": von, "bis": bis,
                      "kennwort": kennwort or None, "aufbewahrung_tage": tage}

    def rclone_konf(self):
        return os.path.join(self.konf, "rclone.conf")

    def ziel_setzen(self, p, von, zeile):
        fehler, z = self.ziel_pruefen(p)
        if fehler:
            return 2, fehler
        if not shutil.which("rclone"):
            return 1, "rclone fehlt auf dem Server (sudo apt install rclone bzw. rollout/04-projekt.sh)."
        self.konf_ordner()
        alt = self.ziel_lesen()
        verschleiert = None
        if z["kennwort"]:
            rc, aus = self.befehl(["rclone", "obscure", "-"], eingabe=z["kennwort"], zeitlimit=30)
            if rc != 0 or not aus.strip():
                return 1, "Das Passwort konnte nicht für rclone gespeichert werden."
            verschleiert = aus.strip().splitlines()[-1]
        else:
            # Passwort unverändert: aus der bisherigen rclone-Konfiguration übernehmen
            try:
                with open(self.rclone_konf(), encoding="utf-8") as f:
                    m = re.search(r"^pass = (\S+)$", f.read(), re.M)
                    verschleiert = m.group(1) if m else None
            except OSError:
                verschleiert = None
            if not verschleiert:
                return 2, "Bitte das Passwort für das Ziel angeben."
        hersteller = "nextcloud" if "/remote.php/" in z["url"] else "other"
        inhalt = (f"[epm-ziel]\ntype = webdav\nurl = {z['url']}\nvendor = {hersteller}\n"
                  f"user = {z['benutzer']}\npass = {verschleiert}\n")
        tmp = self.rclone_konf() + f".tmp{os.getpid()}"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(inhalt)
        os.replace(tmp, self.rclone_konf())
        ziel = {"url": z["url"], "benutzer": z["benutzer"], "ordner": z["ordner"], "von": z["von"], "bis": z["bis"],
                "aufbewahrung_tage": z["aufbewahrung_tage"],
                "hersteller": hersteller, "gesetzt_am": jetzt_iso(), "gesetzt_von": von or ""}
        self.schreibe(os.path.join(self.konf, "ziel.json"), ziel, modus=0o600)
        zeile(f"Ziel gespeichert: {z['url']} · Ordner „{z['ordner'] or '/'}“ · Zeitfenster {z['von']}–{z['bis']} · "
              f"Aufbewahrung im Ziel: {self.aufbewahrung_text(z['aufbewahrung_tage'])}\n")
        if alt and self.ziel_kennung(alt) != self.ziel_kennung(ziel):
            zeile("Neues Ziel: Die vorhandenen verschlüsselten Sicherungen werden im nächsten Zeitfenster dorthin übertragen.\n")
        self.sicherung_status_schreiben()
        return 0, f"Übertragungsziel festgelegt ({teile_host(z['url'])}, Zeitfenster {z['von']}–{z['bis']})."

    @staticmethod
    def ziel_aufbewahrung(ziel):
        """Tage, die Sicherungen im Ziel bleiben (0 = nie löschen); ältere Ziele ohne Angabe: Standard 30."""
        tage = (ziel or {}).get("aufbewahrung_tage", ZIEL_AUFBEWAHRUNG_STANDARD)
        return tage if not isinstance(tage, bool) and tage in ZIEL_AUFBEWAHRUNG else ZIEL_AUFBEWAHRUNG_STANDARD

    @staticmethod
    def aufbewahrung_text(tage):
        return "nie löschen" if not tage else f"{tage} Tage"

    def ziel_aufraeumen(self, ziel, zeile):
        """Sicherungen im Ziel, die älter als die Aufbewahrung sind, entfernen (Festlegung 03.10.2026). Nur nach einer
        erfolgreichen Übertragung, nur Dateien von EPM-Sicherungen im eingestellten Ordner, die jüngste bleibt immer.
        Ein Fehler hier lässt die Übertragung gelingen und steht in der Ausgabe."""
        tage = self.ziel_aufbewahrung(ziel)
        if not tage:
            return 0
        rc, aus = self.rclone(["lsf", self.ziel_pfad(ziel), "--files-only", "--max-depth", "1"], zeile, zeitlimit=600)
        if rc != 0:
            zeile("Aufräumen im Ziel: Inhalt nicht lesbar – nichts entfernt.\n")
            return 0
        weg = im_ziel_veraltet(aus.splitlines(), tage)
        if not weg:
            zeile(f"Aufräumen im Ziel: nichts älter als {tage} Tage.\n")
            return 0
        liste_pfad = os.path.join(self.backup, ".ziel-aufraeumen.liste")
        with open(liste_pfad, "w", encoding="utf-8") as f:
            f.write("\n".join(weg) + "\n")
        try:
            rc, _ = self.rclone(["delete", self.ziel_pfad(ziel), "--files-from-raw", liste_pfad, "--max-depth", "1",
                                 "-v"], zeile, zeitlimit=3600)
        finally:
            try:
                os.unlink(liste_pfad)
            except OSError:
                pass
        stempel = sorted({n.split("_", 1)[1].split(".", 1)[0] for n in weg})
        if rc != 0:
            zeile("Aufräumen im Ziel fehlgeschlagen – Ausgabe prüfen. Die Sicherungen bleiben dort vorerst liegen.\n")
            return 0
        zeile(f"Aufräumen im Ziel: {len(stempel)} Sicherung(en) älter als {tage} Tage entfernt ({', '.join(stempel)}).\n")
        return len(stempel)

    def ziel_entfernen(self, zeile):
        for name in ("ziel.json", "rclone.conf"):
            try:
                os.unlink(os.path.join(self.konf, name))
            except FileNotFoundError:
                pass
        zeile("Übertragungsziel und Zugangsdaten entfernt.\n")
        self.sicherung_status_schreiben()
        return 0, "Übertragungsziel entfernt – Sicherungen bleiben nur auf dem Server."

    def rclone(self, args, zeile, zeitlimit=3600):
        env = {"RCLONE_CONFIG": self.rclone_konf(), "NO_PROXY": "localhost,127.0.0.1,::1"}
        if self.proxy:
            env.update({"HTTPS_PROXY": self.proxy, "HTTP_PROXY": self.proxy})
        befehl = ["rclone", "--config", self.rclone_konf()] + args
        zeile(f"\n$ rclone {' '.join(args)}\n")
        rc, aus = self.befehl(befehl, env=env, zeitlimit=zeitlimit)
        zeile(aus[-8000:])
        return rc, aus

    def ziel_pfad(self, ziel):
        return f"epm-ziel:{ziel['ordner']}" if ziel.get("ordner") else "epm-ziel:"

    def ziel_testen(self, zeile):
        ziel = self.ziel_lesen()
        if not ziel:
            return 2, "Es ist noch kein Übertragungsziel festgelegt."
        if not shutil.which("rclone"):
            return 1, "rclone fehlt auf dem Server (sudo apt install rclone bzw. rollout/04-projekt.sh)."
        if ziel.get("ordner"):
            rc, _ = self.rclone(["mkdir", self.ziel_pfad(ziel)], zeile, zeitlimit=120)
            if rc != 0:
                return 1, "Verbindung fehlgeschlagen – Adresse, Benutzer, Passwort und Proxy-Freigabe prüfen."
        rc, aus = self.rclone(["lsjson", self.ziel_pfad(ziel), "--files-only", "--max-depth", "1"], zeile, zeitlimit=120)
        if rc != 0:
            return 1, "Verbindung fehlgeschlagen – Adresse, Benutzer, Passwort und Proxy-Freigabe prüfen."
        try:
            anzahl = len(json.loads(aus[aus.index("["):]))
        except ValueError:
            anzahl = 0
        return 0, f"Verbindung in Ordnung: {anzahl} Dateien im Zielordner."

    # ------------------------------------------------------------ Sicherungen: Übertragung
    def uebertragung_pfad(self):
        return os.path.join(self.backup, ".uebertragung.json")

    def uebertragung_stand(self):
        stand = self.lies(self.uebertragung_pfad()) or {}
        if not isinstance(stand.get("uebertragen"), dict):
            stand["uebertragen"] = {}
        return stand

    def offene_uebertragungen(self, ziel=None):
        ziel = ziel or self.ziel_lesen()
        if not ziel:
            return []
        kennung = self.ziel_kennung(ziel)
        erledigt = self.uebertragung_stand()["uebertragen"].get(kennung) or {}
        return [s for s in self.sicherungen() if s["verschluesselt"] and s["verfahren"] == "gpg"
                and s["stempel"] not in erledigt]

    def uebertragung_laeuft(self):
        try:
            with open(os.path.join(self.backup, ".uebertragung.sperre"), "a") as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    return True
                fcntl.flock(f, fcntl.LOCK_UN)
        except OSError:
            return False
        return False

    def uebertragung_anstossen(self):
        """Im Status-Lauf: liegt eine noch nicht übertragene, verschlüsselte Sicherung vor und ist das Zeitfenster
        offen, startet die Übertragung im Hintergrund (nach einem Fehler frühestens 15 Minuten später erneut)."""
        ziel = self.ziel_lesen()
        if not ziel or not os.path.isdir(self.backup) or self.simuliert("sicherung_uebertragen"):
            return
        if not im_zeitfenster(ziel["von"], ziel["bis"]) or not self.offene_uebertragungen(ziel):
            return
        stand = self.uebertragung_stand()
        letzter = zeit_aus(stand.get("letzter_versuch"))
        if stand.get("letzter_fehler") and letzter and \
                (datetime.now(timezone.utc) - letzter).total_seconds() < UEBERTRAGUNG_WIEDERHOLEN_S:
            return
        if self.uebertragung_laeuft():
            return
        if os.environ.get("INVOCATION_ID") and os.path.exists("/etc/systemd/system/epm-uebertragung.service"):
            # eigener Dienst: der Status-Lauf ist ein kurzer oneshot, dessen Prozesse systemd am Ende beendet
            self.befehl(["systemctl", "start", "--no-block", "epm-uebertragung.service"], zeitlimit=30)
        else:
            args = [sys.executable, os.path.abspath(__file__), "uebertragen", "--basis", self.basis, "--konf", self.konf]
            if self.projekt:
                args += ["--projekt", self.projekt]
            subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)

    def uebertragen(self, zeile, manuell=False):
        """Verschlüsselte Sicherungen (und ihre Prüfsummen und Angaben) zum Ziel kopieren – nie Unverschlüsseltes.
        Automatisch nur im Zeitfenster und höchstens bis zu seinem Ende. Danach entfernt ``ziel_aufraeumen`` im Ziel die
        Sicherungen, die älter als die dort eingestellte Aufbewahrung sind (Standard 30 Tage, „nie“ wählbar)."""
        ziel = self.ziel_lesen()
        if not ziel:
            return 2, "Es ist noch kein Übertragungsziel festgelegt."
        if not self.passwort_stand().get("aktuell"):
            return 2, "Ohne Sicherungs-Passwort wird nichts übertragen – bitte zuerst das Passwort festlegen."
        if not shutil.which("rclone"):
            return 1, "rclone fehlt auf dem Server (sudo apt install rclone bzw. rollout/04-projekt.sh)."
        if not manuell and not im_zeitfenster(ziel["von"], ziel["bis"]):
            return 0, "Außerhalb des Zeitfensters – nichts übertragen."
        os.makedirs(self.backup, mode=0o700, exist_ok=True)
        with open(os.path.join(self.backup, ".uebertragung.sperre"), "a") as sperre:
            try:
                fcntl.flock(sperre, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return 1, "Eine Übertragung läuft bereits."
            offen = self.offene_uebertragungen(ziel)
            stand = self.uebertragung_stand()
            stand.update({"letzter_versuch": jetzt_iso(), "laeuft_seit": jetzt_iso(), "manuell": manuell})
            self.schreibe(self.uebertragung_pfad(), stand, modus=0o600)
            self.sicherung_status_schreiben()
            if not offen:
                entfernt = self.ziel_aufraeumen(ziel, zeile)
                stand.update({"laeuft_seit": None, "letzter_fehler": "", "letzter_erfolg": jetzt_iso()})
                if entfernt:
                    stand["im_ziel_entfernt"] = {"am": jetzt_iso(), "anzahl": entfernt}
                self.schreibe(self.uebertragung_pfad(), stand, modus=0o600)
                self.sicherung_status_schreiben()
                return 0, "Alle verschlüsselten Sicherungen sind schon übertragen." + (
                    f" Im Ziel {entfernt} ältere Sicherung(en) entfernt." if entfernt else "")
            liste = []
            for s in offen:
                liste.extend(s["dateien"])
                for endung in ("sha256", "json"):
                    if os.path.exists(os.path.join(self.backup, f"epm_{s['stempel']}.{endung}")):
                        liste.append(f"epm_{s['stempel']}.{endung}")
            liste_pfad = os.path.join(self.backup, ".uebertragung.liste")
            with open(liste_pfad, "w", encoding="utf-8") as f:
                f.write("\n".join(liste) + "\n")
            zeile(f"{len(offen)} Sicherung(en), {len(liste)} Dateien → {ziel['url']} · Ordner „{ziel['ordner'] or '/'}“\n")
            args = ["copy", self.backup, self.ziel_pfad(ziel), "--files-from-raw", liste_pfad, "--no-traverse",
                    "--retries", "3", "--low-level-retries", "10", "--stats-one-line", "--stats", "60s", "-v"]
            rest = None if manuell else fenster_rest_s(ziel["von"], ziel["bis"])
            if rest:
                args += ["--max-duration", f"{rest}s", "--cutoff-mode", "soft"]
            rc, _ = self.rclone(args, zeile, zeitlimit=6 * 3600)
            if rc == 0:
                rc, _ = self.rclone(["check", self.backup, self.ziel_pfad(ziel), "--files-from-raw", liste_pfad,
                                     "--one-way", "--size-only"], zeile, zeitlimit=3600)
            try:
                os.unlink(liste_pfad)
            except OSError:
                pass
            stand = self.uebertragung_stand()
            stand["laeuft_seit"] = None
            if rc == 0:
                kennung = self.ziel_kennung(ziel)
                erledigt = stand["uebertragen"].setdefault(kennung, {})
                for s in offen:
                    erledigt[s["stempel"]] = jetzt_iso()
                vorhanden = {s["stempel"] for s in self.sicherungen()}
                for k in list(stand["uebertragen"]):
                    stand["uebertragen"][k] = {st: z for st, z in stand["uebertragen"][k].items() if st in vorhanden}
                entfernt = self.ziel_aufraeumen(ziel, zeile)
                if entfernt:
                    stand["im_ziel_entfernt"] = {"am": jetzt_iso(), "anzahl": entfernt}
                stand.update({"letzter_erfolg": jetzt_iso(), "letzter_fehler": ""})
                ergebnis = f"{len(offen)} Sicherung(en) übertragen und geprüft." + (
                    f" Im Ziel {entfernt} ältere Sicherung(en) entfernt." if entfernt else "")
            else:
                stand["letzter_fehler"] = ("Übertragung fehlgeschlagen oder Zeitfenster vorbei – Ausgabe prüfen "
                                           "(Adresse, Zugang, Proxy-Freigabe).")
                ergebnis = stand["letzter_fehler"]
            self.schreibe(self.uebertragung_pfad(), stand, modus=0o600)
            self.sicherung_status_schreiben()
            return (0 if rc == 0 else 1), ergebnis

    # ------------------------------------------------------------ Sicherungen: Aufbewahrung
    def aufbewahrung_tage(self):
        """Tage, die Sicherungen auf dem Server bleiben: Auswahl aus der Oberfläche (``<konf>/aufbewahrung``), sonst
        EPM_BACKUP_TAGE aus /etc/epm/epm.conf, sonst 30."""
        try:
            with open(os.path.join(self.konf, "aufbewahrung"), encoding="utf-8") as f:
                wert = int(f.read().strip())
            if wert >= 1:
                return wert
        except (OSError, ValueError):
            pass
        try:
            return max(1, int(lese_konf().get("EPM_BACKUP_TAGE") or 30))
        except ValueError:
            return 30

    def aufbewahrung_setzen(self, tage, zeile):
        if isinstance(tage, bool) or tage not in AUFBEWAHRUNG_TAGE:
            return 2, "Bitte 7, 14 oder 30 Tage wählen."
        self.konf_ordner()
        vorher = self.aufbewahrung_tage()
        tmp = os.path.join(self.konf, f".aufbewahrung.{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f"{tage}\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, os.path.join(self.konf, "aufbewahrung"))
        zeile(f"Aufbewahrung: {tage} Tage (bisher {vorher}). Ältere Sicherungen entfernt die nächste Sicherung.\n")
        self.sicherung_status_schreiben()
        return 0, f"Sicherungen bleiben {tage} Tage auf dem Server (bisher {vorher})."

    # ------------------------------------------------------------ Sicherungen: herunterladen und hochladen
    def austausch_ordner(self):
        """Ordner für den Austausch mit dem Backend (falls rollout/04-projekt.sh sie noch nicht angelegt hat)."""
        os.makedirs(self.download, mode=0o750, exist_ok=True)
        os.makedirs(self.upload, mode=0o770, exist_ok=True)
        if os.geteuid() == 0:
            os.chown(self.download, 0, APP_GID)
            os.chmod(self.download, 0o750)
            os.chown(self.upload, self.app_uid, APP_GID)
            os.chmod(self.upload, 0o770)

    def bereitgestellt(self):
        """Zum Herunterladen bereitgestellte Sicherungen: [{stempel, datei, groesse, bis}]"""
        liste = []
        try:
            namen = os.listdir(self.download)
        except OSError:
            return liste
        for n in sorted(namen):
            m = BUENDEL_MUSTER.match(n)
            if not m:
                continue
            try:
                info = os.lstat(os.path.join(self.download, n))
            except OSError:
                continue
            bis = datetime.fromtimestamp(info.st_mtime + BUENDEL_STUNDEN * 3600, timezone.utc).astimezone()
            liste.append({"stempel": m.group(1), "datei": n, "groesse": info.st_size,
                          "bis": bis.isoformat(timespec="seconds")})
        return liste

    def austausch_aufraeumen(self):
        """Bereitgestellte Sicherungen nach 2 Stunden und liegengebliebene Uploads nach 24 Stunden entfernen."""
        jetzt = time.time()
        for ordner, stunden in ((self.download, BUENDEL_STUNDEN), (self.upload, UPLOAD_ALT_STUNDEN),
                                (self.protokolle, PROTOKOLL_STUNDEN)):
            try:
                namen = os.listdir(ordner)
            except OSError:
                continue
            for n in namen:
                pfad = os.path.join(ordner, n)
                try:
                    info = os.lstat(pfad)
                    if stat.S_ISREG(info.st_mode) and jetzt - info.st_mtime > stunden * 3600:
                        os.unlink(pfad)
                except OSError:
                    pass

    def bereitstellen(self, stempel, zeile):
        """Eine Sicherung als eine Datei (epm-sicherung_<Stempel>.tar: Datenbank, Dokumente, Löschliste, Prüfsummen,
        Angaben) zum Herunterladen bereitlegen – für 2 Stunden, lesbar nur für Backend und Webserver (Gruppe 101).
        Die Dateien bleiben, wie sie sind: verschlüsselte Sicherungen bleiben verschlüsselt."""
        if not isinstance(stempel, str) or not STEMPEL_MUSTER.match(stempel):
            return 2, "Unbekannte Sicherung."
        s = next((x for x in self.sicherungen() if x["stempel"] == stempel), None)
        if s is None:
            return 2, f"Die Sicherung {stempel} gibt es auf dem Server nicht (mehr)."
        self.austausch_ordner()
        namen = list(s["dateien"])
        for endung in ("sha256", "json"):
            if os.path.exists(os.path.join(self.backup, f"epm_{stempel}.{endung}")):
                namen.append(f"epm_{stempel}.{endung}")
        try:
            frei = os.statvfs(self.download)
            if frei.f_bavail * frei.f_frsize < s["groesse"] + 64 * 1024 * 1024:
                return 1, "Zu wenig freier Speicher auf dem Server, um die Sicherung bereitzustellen."
        except OSError:
            pass
        ziel = os.path.join(self.download, f"epm-sicherung_{stempel}.tar")
        tmp = f"{ziel}.teil"
        zeile(f"Sicherung vom {s['zeitpunkt']} ({stempel}): {len(namen)} Dateien, "
              f"{'verschlüsselt' if s['verschluesselt'] else 'UNVERSCHLÜSSELT'}.\n")
        try:
            with tarfile.open(tmp, "w") as tar:
                for n in namen:
                    tar.add(os.path.join(self.backup, n), arcname=n, recursive=False)
            if os.geteuid() == 0:
                os.chown(tmp, 0, APP_GID)
            os.chmod(tmp, 0o640)
            os.replace(tmp, ziel)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        groesse = os.stat(ziel).st_size
        zeile(f"Bereitgestellt: {os.path.basename(ziel)} ({groesse} Bytes), {BUENDEL_STUNDEN} Stunden lang.\n")
        self.sicherung_status_schreiben()
        return 0, f"Sicherung zum Herunterladen bereit ({BUENDEL_STUNDEN} Stunden)."

    def passwort_passt(self, datei, passwort_datei):
        """Lässt sich die verschlüsselte Datei mit diesem Passwort lesen? (entschlüsselt nach /dev/null)"""
        heim = tempfile.mkdtemp(prefix="epm-gpg-")
        try:
            rc, _aus = self.befehl(["gpg", "--homedir", heim, "--batch", "--yes", "--quiet", "--no-symkey-cache",
                                    "--pinentry-mode", "loopback", "--passphrase-file", passwort_datei, "--decrypt",
                                    "-o", "/dev/null", datei], zeitlimit=3 * 3600)
        finally:
            self.befehl(["gpgconf", "--homedir", heim, "--kill", "all"], zeitlimit=30)
            shutil.rmtree(heim, ignore_errors=True)
        return rc == 0

    def einlesen(self, kennung, passwort, von, zeile):
        """Hochgeladene Sicherung (epm-sicherung_<Stempel>.tar, wie sie „Herunterladen“ liefert) prüfen und in den
        Backup-Ordner übernehmen: nur die bekannten Dateinamen einer Sicherung, Prüfsummen müssen stimmen, eine
        vorhandene Sicherung wird nie überschrieben. Ist sie mit einem Passwort verschlüsselt, das dieser Server
        nicht kennt (Sicherung eines anderen EPM-Servers), wird das mitgegebene Passwort geprüft und für diese
        Sicherung hinterlegt. Danach steht sie in der Liste und lässt sich wie jede andere wiederherstellen."""
        if not isinstance(kennung, str) or not ID_MUSTER.match(kennung):
            return 2, "Unbekannter Upload."
        quelle = os.path.join(self.upload, f"{kennung}.teil")
        neben = os.path.join(self.upload, f"{kennung}.json")

        def weg():
            for pfad in (quelle, neben):
                try:
                    os.unlink(pfad)
                except OSError:
                    pass

        try:
            fd = os.open(quelle, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            return 2, "Die hochgeladene Datei liegt nicht (mehr) auf dem Server."
        arbeit = os.path.join(self.backup, f".einlesen-{kennung[:12]}")
        try:
            with os.fdopen(fd, "rb") as f:
                if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                    return 2, "Die hochgeladene Datei ist keine gewöhnliche Datei."
                try:
                    tar = tarfile.open(fileobj=f, mode="r:")
                except (tarfile.TarError, OSError):
                    weg()
                    return 1, "Die Datei ist keine Sicherung von EPM (kein tar-Archiv, wie es „Herunterladen“ liefert)."
                with tar:
                    try:
                        glieder = tar.getmembers()
                    except (tarfile.TarError, OSError):
                        weg()
                        return 1, "Die Datei ist beschädigt (tar-Archiv nicht lesbar)."
                    stempel, namen = None, []
                    for g in glieder:
                        m = DATEI_MUSTER.match(g.name) or NEBEN_MUSTER.match(g.name)
                        st = (m.group(2) if DATEI_MUSTER.match(g.name) else m.group(1)) if m else None
                        if not g.isreg() or not m or (stempel and st != stempel) or g.name in namen:
                            weg()
                            return 1, ("Die Datei ist keine Sicherung von EPM: Sie enthält etwas anderes als die Dateien "
                                       "genau einer Sicherung.")
                        stempel = st
                        namen.append(g.name)
                    daten = [n for n in namen if DATEI_MUSTER.match(n)]
                    if not any(n.startswith("epm-db_") for n in daten) or \
                            not any(n.startswith("epm-dokumente_") for n in daten):
                        weg()
                        return 1, "Die Sicherung ist unvollständig: Datenbank oder Dokumente fehlen."
                    if any(n.endswith(".age") for n in daten):
                        weg()
                        return 1, ("Diese Sicherung ist mit einem öffentlichen Schlüssel (age) verschlüsselt und lässt "
                                   "sich hier nicht zurückspielen.")
                    if any(x["stempel"] == stempel for x in self.sicherungen()) or \
                            any(os.path.exists(os.path.join(self.backup, n)) for n in namen):
                        weg()
                        return 1, f"Die Sicherung {stempel} gibt es auf diesem Server schon – nichts verändert."
                    bedarf = sum(g.size for g in glieder)
                    try:
                        frei = os.statvfs(self.backup)
                        if frei.f_bavail * frei.f_frsize < bedarf + 64 * 1024 * 1024:
                            return 1, "Zu wenig freier Speicher im Backup-Ordner. Die hochgeladene Datei bleibt liegen."
                    except OSError:
                        pass
                    shutil.rmtree(arbeit, ignore_errors=True)
                    os.makedirs(arbeit, mode=0o700)
                    zeile(f"Sicherung {stempel}: {len(namen)} Dateien auspacken …\n")
                    for g in glieder:
                        quelle_f = tar.extractfile(g)
                        ziel_fd = os.open(os.path.join(arbeit, g.name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                        with os.fdopen(ziel_fd, "wb") as ziel_f:
                            shutil.copyfileobj(quelle_f, ziel_f, 1 << 20)
            # Prüfsummen (im Arbeitsordner)
            if f"epm_{stempel}.sha256" in namen:
                with open(os.path.join(arbeit, f"epm_{stempel}.sha256"), encoding="utf-8", errors="replace") as f:
                    soll = {}
                    for z in f.read().splitlines():
                        teile = z.split(None, 1)
                        if len(teile) == 2:
                            soll[os.path.basename(teile[1].strip().lstrip("*"))] = teile[0]
                for n in daten:
                    h = hashlib.sha256()
                    with open(os.path.join(arbeit, n), "rb") as f:
                        for block in iter(lambda: f.read(1 << 20), b""):
                            h.update(block)
                    if soll.get(n) != h.hexdigest():
                        weg()
                        return 1, f"Die Sicherung ist beschädigt: Prüfsumme von {n} stimmt nicht. Nichts übernommen."
                zeile("Prüfsummen stimmen.\n")
            else:
                zeile("Die Sicherung enthält keine Prüfsummen – ohne Prüfung übernommen.\n")
            # Verschlüsselung: Welches hinterlegte Passwort passt? Sonst das mitgegebene prüfen und hinterlegen.
            verschluesselt = any(n.endswith(".gpg") for n in daten)
            nr = None
            if verschluesselt:
                if not all(n.endswith(".gpg") for n in daten):
                    weg()
                    return 1, "Die Sicherung ist nur teilweise verschlüsselt – nichts übernommen."
                if not shutil.which("gpg"):
                    return 1, "GnuPG fehlt auf dem Server (sudo apt install gnupg). Die hochgeladene Datei bleibt liegen."
                probe = min((os.path.join(arbeit, n) for n in daten), key=os.path.getsize)
                stand = self.passwort_stand()
                for v in sorted(stand["versionen"], key=lambda v: -(v.get("nr") or 0)):
                    datei = self.passwort_datei(v.get("nr"))
                    if datei and self.passwort_passt(probe, datei):
                        nr = v["nr"]
                        zeile(f"Verschlüsselt mit dem hinterlegten Sicherungs-Passwort Nr. {nr}.\n")
                        break
                if nr is None:
                    if not isinstance(passwort, str) or not passwort:
                        return 3, ("Die Sicherung ist mit einem Passwort verschlüsselt, das dieser Server nicht kennt. "
                                   "Bitte beim Einlesen das Passwort dieser Sicherung angeben (vom Passwortblatt des "
                                   "anderen Servers). Die hochgeladene Datei bleibt bis dahin liegen.")
                    if not (1 <= len(passwort) <= PASSWORT_MAX) or any(z in passwort for z in "\r\n\0"):
                        return 3, "Das angegebene Passwort ist ungültig. Die hochgeladene Datei bleibt liegen."
                    self.konf_ordner()
                    probe_pw = os.path.join(self.konf, f".probe-{kennung[:12]}")
                    fd = os.open(probe_pw, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(passwort)
                    passt = False
                    try:
                        passt = self.passwort_passt(probe, probe_pw)
                    finally:
                        if not passt:
                            os.unlink(probe_pw)
                    if not passt:
                        return 3, ("Das angegebene Passwort passt nicht zu dieser Sicherung. Die hochgeladene Datei "
                                   "bleibt liegen – bitte erneut mit dem richtigen Passwort einlesen.")
                    nr = max([v.get("nr", 0) for v in stand["versionen"]] + [0]) + 1
                    os.replace(probe_pw, os.path.join(self.konf, f"passwort-{nr}"))
                    salz = os.urandom(16)
                    wert = hashlib.scrypt(passwort.encode(), salt=salz, n=2 ** 14, r=8, p=1, dklen=32)
                    stand["versionen"].append({"nr": nr, "gesetzt_am": jetzt_iso(), "gesetzt_von": von or "",
                                               "fremd": True,
                                               "pruefwert": {"verfahren": "scrypt", "n": 2 ** 14, "r": 8, "p": 1,
                                                             "salz": salz.hex(), "wert": wert.hex()}})
                    self.schreibe(os.path.join(self.konf, "passwort.json"), stand, modus=0o600)
                    zeile(f"Passwort der Sicherung geprüft und als Nr. {nr} hinterlegt (nur für diese Sicherung; das "
                          "aktuelle Sicherungs-Passwort dieses Servers bleibt).\n")
            # Angaben zur Sicherung: Herkunft und – für das Wiederherstellen – die hiesige Nummer des Passworts
            meta_pfad = os.path.join(arbeit, f"epm_{stempel}.json")
            meta = self.lies(meta_pfad) if f"epm_{stempel}.json" in namen else None
            meta = meta if isinstance(meta, dict) else {"version": 1, "stempel": stempel}
            if meta.get("art") in ARTEN and meta.get("art") != "hochgeladen":
                meta["art_urspruenglich"] = meta["art"]
            meta.update({"art": "hochgeladen", "ausgeloest_von": von or "", "hochgeladen_am": jetzt_iso(),
                         "verschluesselt": verschluesselt, "passwort_nr": nr})
            self.schreibe(meta_pfad, meta, modus=0o600)
            if f"epm_{stempel}.json" not in namen:
                namen.append(f"epm_{stempel}.json")
            for n in namen:
                os.chmod(os.path.join(arbeit, n), 0o600)
                os.replace(os.path.join(arbeit, n), os.path.join(self.backup, n))
            weg()
            self.sicherung_status_schreiben()
            return 0, (f"Sicherung {stempel} übernommen ({'verschlüsselt' if verschluesselt else 'unverschlüsselt'}). "
                       "Sie steht in der Liste und lässt sich wiederherstellen.")
        finally:
            shutil.rmtree(arbeit, ignore_errors=True)

    # ------------------------------------------------------------ Sicherungen: Status für das Backend
    def sicherung_status_schreiben(self):
        stand = self.passwort_stand()
        versionen = []
        pruefwerte = []
        liste = self.sicherungen()
        for v in stand["versionen"]:
            nr = v.get("nr")
            versionen.append({"nr": nr, "gesetzt_am": v.get("gesetzt_am"), "gesetzt_von": v.get("gesetzt_von", ""),
                              "entfernt_am": v.get("entfernt_am"), "fremd": bool(v.get("fremd")),
                              "sicherungen": sum(1 for s in liste if s["passwort_nr"] == nr)})
            if v.get("pruefwert") and not v.get("entfernt_am"):
                pruefwerte.append({"nr": nr, **v["pruefwert"]})
        ziel = self.ziel_lesen()
        ue = self.uebertragung_stand()
        offen = self.offene_uebertragungen(ziel) if ziel else []
        naechstes = None
        if ziel:
            n = naechstes_fenster(ziel["von"], ziel["bis"])
            naechstes = n.astimezone().isoformat(timespec="seconds")
        try:
            s = os.statvfs(self.backup)
            platz = {"gesamt": s.f_blocks * s.f_frsize, "frei": s.f_bavail * s.f_frsize}
        except OSError:
            platz = None
        naechste_sicherung = None
        rc, aus = self.befehl(["systemctl", "show", "epm-backup.timer", "-p", "NextElapseUSecRealtime", "--value"],
                              zeitlimit=10)
        if rc == 0 and aus.strip() and aus.strip() != "n/a":
            naechste_sicherung = aus.strip()
        # ist der letzte Lauf des Timers (nachts, 02:00) gescheitert? (ohne systemd-Einheit, z. B. in CI: nein)
        _rc, aus = self.befehl(["systemctl", "is-failed", "epm-backup.service"], zeitlimit=10)
        nachts_fehlgeschlagen = (aus.strip().splitlines() or [""])[0] == "failed"
        status = {
            "version": 1,
            "zeit": jetzt_iso(),
            "verschluesselung": {
                "eingerichtet": bool(stand.get("aktuell") and self.passwort_datei(stand["aktuell"])),
                "aktuell": stand.get("aktuell"),
                "verfahren": "GnuPG (OpenPGP), AES-256, symmetrisch mit Passwort",
                "versionen": versionen,
            },
            "ziel": ({k: ziel.get(k) for k in ("url", "benutzer", "ordner", "von", "bis", "hersteller", "gesetzt_am",
                                                "gesetzt_von")}
                     | {"eingerichtet": True, "aufbewahrung_tage": self.ziel_aufbewahrung(ziel)}) if ziel
            else {"eingerichtet": False},
            "uebertragung": {
                "letzter_versuch": ue.get("letzter_versuch"),
                "letzter_erfolg": ue.get("letzter_erfolg"),
                "letzter_fehler": ue.get("letzter_fehler") or "",
                "laeuft": bool(ue.get("laeuft_seit")) and self.uebertragung_laeuft(),
                "offen": len(offen),
                "im_zeitfenster": im_zeitfenster(ziel["von"], ziel["bis"]) if ziel else False,
                "naechstes_fenster": naechstes,
                "rclone": bool(shutil.which("rclone")),
                "im_ziel_entfernt": ue.get("im_ziel_entfernt"),
            },
            "sicherungen": liste,
            "speicher": {"platz": platz, "sicherungen": sum(x["groesse"] for x in liste)},
            "aufbewahrung_tage": self.aufbewahrung_tage(),
            "aufbewahrung_auswahl": list(AUFBEWAHRUNG_TAGE),
            "bereitgestellt": self.bereitgestellt(),
            "austausch": os.path.isdir(self.download) and os.path.isdir(self.upload),
            "naechste_sicherung": naechste_sicherung,
            "zeitplan": self.zeitplan(),
            "nachts_fehlgeschlagen": nachts_fehlgeschlagen,
            "gpg": bool(shutil.which("gpg")),
            "wiederherstellungen": (self.lies(os.path.join(self.status, "wiederherstellungen.json")) or [])[-20:],
        }
        self.schreibe(os.path.join(self.status, "sicherung.json"), status)
        # Prüfwerte (scrypt) der Passwörter: damit das Backend ein eingegebenes Passwort prüfen kann (Passwortblatt)
        self.schreibe(os.path.join(self.status, "sicherung-pruefwerte.json"), {"pruefwerte": pruefwerte})
        return status

    # ------------------------------------------------------------ Sicherungen: Wiederherstellen
    def pruefsummen_pruefen(self, stempel, dateien, zeile):
        pfad = os.path.join(self.backup, f"epm_{stempel}.sha256")
        try:
            with open(pfad, encoding="utf-8") as f:
                zeilen = f.read().splitlines()
        except OSError:
            zeile("Keine Prüfsummen zu dieser Sicherung – Prüfung übersprungen.\n")
            return True
        soll = {}
        for z in zeilen:
            teile = z.split(None, 1)
            if len(teile) == 2:
                soll[os.path.basename(teile[1].strip().lstrip("*"))] = teile[0]
        for name in dateien:
            h = hashlib.sha256()
            with open(os.path.join(self.backup, name), "rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    h.update(block)
            if soll.get(name) and soll[name] != h.hexdigest():
                zeile(f"Prüfsumme stimmt nicht: {name}\n")
                return False
        zeile("Prüfsummen stimmen.\n")
        return True

    def entschluesseln(self, quelle, ziel, nr, zeile):
        """gpg mit dem Passwort Nr. nr; ``ziel`` None: auf die Standardausgabe (Rückgabe: Popen)."""
        datei = self.passwort_datei(nr) if nr else None
        kandidaten = [datei] if datei else []
        stand = self.passwort_stand()
        for v in sorted(stand["versionen"], key=lambda v: -(v.get("nr") or 0)):
            p = self.passwort_datei(v.get("nr"))
            if p and p not in kandidaten:
                kandidaten.append(p)
        if not kandidaten:
            zeile("Es ist kein Sicherungs-Passwort auf dem Server hinterlegt.\n")
            return False
        for p in kandidaten:
            heim = tempfile.mkdtemp(prefix="epm-gpg-")
            try:
                rc, aus = self.befehl(["gpg", "--homedir", heim, "--batch", "--yes", "--quiet", "--no-symkey-cache",
                                       "--pinentry-mode", "loopback", "--passphrase-file", p, "--decrypt",
                                       "-o", ziel, quelle], zeitlimit=3 * 3600)
            finally:
                self.befehl(["gpgconf", "--homedir", heim, "--kill", "all"], zeitlimit=30)
                shutil.rmtree(heim, ignore_errors=True)
            if rc == 0:
                return True
            try:
                os.unlink(ziel)
            except OSError:
                pass
        zeile(f"{os.path.basename(quelle)} ließ sich mit keinem hinterlegten Passwort entschlüsseln.\n")
        return False

    def psql(self, sql, zeile, datenbank="postgres"):
        return self.schritt("SQL", self.compose("exec", "-T", "db", "psql", "-U", "epm", "-d", datenbank,
                                                "-v", "ON_ERROR_STOP=1", "-q", "-c", sql),
                            zeile, cwd=self.basis, zeitlimit=600)

    def umbenennen(self, alt, neu, zeile, versuche=5):
        """ALTER DATABASE … RENAME braucht eine Datenbank ohne Verbindungen (auch Autovacuum) – mehrfach versuchen."""
        for _ in range(versuche):
            self.psql(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{alt}' "
                      "AND pid <> pg_backend_pid()", zeile)
            if self.psql(f"ALTER DATABASE {alt} RENAME TO {neu}", zeile) == 0:
                return True
            time.sleep(2)
        return False

    def backend_gesund(self, zeile, sekunden=300):
        ende = time.time() + sekunden
        while time.time() < ende:
            rc, cid = self.befehl(self.compose("ps", "-q", "backend"), cwd=self.basis, zeitlimit=30)
            cid = cid.strip().splitlines()[0] if rc == 0 and cid.strip() else ""
            if cid:
                rc, zustand = self.befehl(["docker", "inspect", "-f", "{{.State.Health.Status}}", cid], zeitlimit=30)
                if zustand.strip() == "healthy":
                    zeile("Backend läuft wieder.\n")
                    return True
            time.sleep(3)
        zeile("Das Backend ist nach 5 Minuten nicht bereit.\n")
        return False

    def wiederherstellen(self, stempel, von, auftrag_id, zeile, vorher=None):
        """Sicherung zurückspielen: prüfen und entschlüsseln (EPM läuft noch), dann Backend und Webserver anhalten,
        Datenbank in eine neue Datenbank laden und tauschen, Dokumentordner tauschen, starten. Schlägt ein Schritt nach
        dem Anhalten fehl, wird der vorige Stand zurückgetauscht. Die Löschliste bleibt unangetastet (Art. 17 DSGVO);
        das Backend löscht beim Start erneut, was die Sicherung zurückgebracht hat."""
        if not isinstance(stempel, str) or not STEMPEL_MUSTER.match(stempel):
            return 2, "Unbekannte Sicherung."
        s = next((x for x in self.sicherungen() if x["stempel"] == stempel), None)
        if s is None:
            return 2, f"Die Sicherung {stempel} gibt es auf dem Server nicht (mehr)."
        if s["verfahren"] == "age":
            return 2, "Diese Sicherung ist mit einem öffentlichen Schlüssel (age) verschlüsselt – bitte von Hand zurückspielen."
        db = next(d for d in s["dateien"] if d.startswith("epm-db_"))
        dok = next((d for d in s["dateien"] if d.startswith("epm-dokumente_")), None)
        if not dok:
            return 2, "Zu dieser Sicherung fehlen die Dokumente – sie wird nicht zurückgespielt."
        beginn = jetzt_iso()
        # vorher_stempel: die Sicherung des Stands direkt davor – Einträge danach (auch im Audit-Log) stehen dort
        protokoll = {"id": auftrag_id, "stempel": stempel, "sicherung_zeitpunkt": s["zeitpunkt"],
                     "angefordert_von": von, "begonnen_am": beginn, "vorher_stempel": vorher}

        def vermerken(zustand, text=""):
            """Eintrag in status/wiederherstellungen.json (je Auftrag einer). „umgestellt“ steht dort, BEVOR das Backend
            mit der zurückgespielten Datenbank startet: Es trägt die Wiederherstellung beim Start ins Audit-Log ein und
            beendet alle Anmeldungen. Scheitert der Start, steht „fehler“ dort, bevor der vorige Stand wieder startet."""
            pfad = os.path.join(self.status, "wiederherstellungen.json")
            liste = [e for e in (self.lies(pfad) or []) if isinstance(e, dict) and e.get("id") != auftrag_id]
            eintrag = {**protokoll, "status": zustand, "ergebnis": text}
            if zustand in ("erledigt", "fehler"):
                eintrag["beendet_am"] = jetzt_iso()
            liste.append(eintrag)
            self.schreibe(pfad, liste[-50:])

        def fertig(rc, text):
            vermerken("erledigt" if rc == 0 else "fehler", text)
            return rc, text

        zeile(f"Sicherung vom {s['zeitpunkt']} ({stempel}), {'verschlüsselt' if s['verschluesselt'] else 'unverschlüsselt'}.\n")
        if not self.pruefsummen_pruefen(stempel, s["dateien"], zeile):
            return fertig(1, "Abgebrochen: Die Sicherung ist beschädigt (Prüfsumme). Es wurde nichts verändert.")
        arbeit = os.path.join(self.backup, f".wiederherstellung-{auftrag_id[:12]}")
        daten = os.path.join(self.basis, "data")
        staging = os.path.join(daten, f".wiederherstellung-{auftrag_id[:12]}")
        alt_dok = os.path.join(daten, f".dokumente-vorher-{auftrag_id[:12]}")
        alt_db = f"epm_vorher_{auftrag_id[:12]}"
        os.makedirs(arbeit, mode=0o700, exist_ok=True)
        try:
            # 1. Vorbereiten, solange EPM läuft
            dump = os.path.join(arbeit, "epm.dump")
            if s["verschluesselt"]:
                zeile("Datenbank entschlüsseln …\n")
                if not self.entschluesseln(os.path.join(self.backup, db), dump, s["passwort_nr"], zeile):
                    return fertig(1, "Abgebrochen: Die Sicherung ließ sich nicht entschlüsseln. Es wurde nichts verändert.")
            else:
                shutil.copyfile(os.path.join(self.backup, db), dump)
            os.chmod(dump, 0o600)
            with open(dump, "rb") as f:
                p = subprocess.run(self.compose("exec", "-T", "db", "pg_restore", "--list"), cwd=self.basis, stdin=f,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=600, check=False)
            if p.returncode != 0:
                zeile(p.stderr.decode(errors="replace")[-2000:])
                return fertig(1, "Abgebrochen: Der Datenbank-Teil der Sicherung ist nicht lesbar. Es wurde nichts verändert.")
            zeile("Datenbank-Teil gelesen und geprüft.\n")
            shutil.rmtree(staging, ignore_errors=True)
            os.makedirs(staging, mode=0o750)
            zeile("Dokumente auspacken …\n")
            if s["verschluesselt"]:
                tar_datei = os.path.join(arbeit, "dokumente.tar.gz")
                if not self.entschluesseln(os.path.join(self.backup, dok), tar_datei, s["passwort_nr"], zeile):
                    return fertig(1, "Abgebrochen: Die Dokumente ließen sich nicht entschlüsseln. Es wurde nichts verändert.")
            else:
                tar_datei = os.path.join(self.backup, dok)
            rc = self.schritt("Dokumente", ["tar", "-C", staging, "--numeric-owner", "-xpzf", tar_datei], zeile,
                              zeitlimit=3 * 3600)
            if rc != 0 or not os.path.isdir(os.path.join(staging, "dokumente")):
                return fertig(1, "Abgebrochen: Die Dokumente ließen sich nicht auspacken. Es wurde nichts verändert.")
            if s["verschluesselt"]:
                os.unlink(tar_datei)

            # 2. Umstellen (EPM ist kurz nicht erreichbar)
            sperre = open(os.path.join(self.backup, ".epm-backup.sperre"), "a")
            fcntl.flock(sperre, fcntl.LOCK_EX)  # keine nächtliche Sicherung mitten im Umstellen
            try:
                return fertig(*self.umstellen(dump, staging, alt_dok, alt_db, zeile, vermerken))
            finally:
                fcntl.flock(sperre, fcntl.LOCK_UN)
                sperre.close()
        finally:
            shutil.rmtree(arbeit, ignore_errors=True)
            shutil.rmtree(staging, ignore_errors=True)

    def umstellen(self, dump, staging, alt_dok, alt_db, zeile, vermerken=lambda *a: None):
        daten = os.path.join(self.basis, "data")
        dok = os.path.join(daten, "dokumente")
        zeile("\nBackend und Webserver anhalten …\n")
        self.schritt("Anhalten", self.compose("stop", "backend", "ocr", "web"), zeile, cwd=self.basis, zeitlimit=300)
        db_getauscht = dok_getauscht = False
        try:
            if self.psql("DROP DATABASE IF EXISTS epm_wiederherstellung", zeile) != 0 or \
                    self.psql("CREATE DATABASE epm_wiederherstellung OWNER epm", zeile) != 0:
                raise RuntimeError("Neue Datenbank ließ sich nicht anlegen.")
            zeile("Datenbank einspielen …\n")
            with open(dump, "rb") as f:
                p = subprocess.run(self.compose("exec", "-T", "db", "pg_restore", "-U", "epm", "-d",
                                                "epm_wiederherstellung", "--no-owner", "--role=epm", "--exit-on-error"),
                                   cwd=self.basis, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=3 * 3600, check=False)
            zeile(p.stdout.decode(errors="replace")[-4000:])
            if p.returncode != 0:
                raise RuntimeError("Die Datenbank ließ sich nicht einspielen.")
            if not self.umbenennen("epm", alt_db, zeile):
                raise RuntimeError("Die bisherige Datenbank ließ sich nicht beiseitelegen.")
            if not self.umbenennen("epm_wiederherstellung", "epm", zeile):
                self.umbenennen(alt_db, "epm", zeile)
                raise RuntimeError("Die wiederhergestellte Datenbank ließ sich nicht umbenennen.")
            db_getauscht = True
            zeile("Datenbank getauscht.\n")
            modus = stat.S_IMODE(os.stat(dok).st_mode) if os.path.isdir(dok) else 0o2750
            if os.path.isdir(dok):
                os.rename(dok, alt_dok)
            os.rename(os.path.join(staging, "dokumente"), dok)
            dok_getauscht = True
            self.schritt("Rechte", ["chown", "-R", f"{self.app_uid}:{APP_GID}", dok], zeile, zeitlimit=3600)
            os.chmod(dok, modus)
            zeile("Dokumente getauscht.\n")
            vermerken("umgestellt")
            self.schritt("Starten", self.compose("up", "-d", "backend", "ocr", "web"), zeile, cwd=self.basis, zeitlimit=600)
            if not self.backend_gesund(zeile):
                raise RuntimeError("Das Backend startet mit der wiederhergestellten Sicherung nicht.")
        except Exception as e:  # noqa: BLE001 – zurücktauschen, dann melden
            zeile(f"\nFEHLER: {e}\nVorigen Stand zurückstellen …\n")
            self.schritt("Anhalten", self.compose("stop", "backend", "ocr", "web"), zeile, cwd=self.basis, zeitlimit=300)
            if db_getauscht:
                self.umbenennen("epm", "epm_fehlgeschlagen", zeile)
                self.umbenennen(alt_db, "epm", zeile)
                self.psql("DROP DATABASE IF EXISTS epm_fehlgeschlagen", zeile)
            else:
                self.psql("DROP DATABASE IF EXISTS epm_wiederherstellung", zeile)
            if dok_getauscht:
                shutil.rmtree(dok, ignore_errors=True)
            if os.path.isdir(alt_dok) and not os.path.isdir(dok):
                os.rename(alt_dok, dok)
            vermerken("fehler", f"Wiederherstellen fehlgeschlagen ({e}) – der vorige Stand läuft weiter.")
            self.schritt("Starten", self.compose("up", "-d", "backend", "ocr", "web"), zeile, cwd=self.basis, zeitlimit=600)
            self.backend_gesund(zeile)
            return 1, f"Wiederherstellen fehlgeschlagen ({e}) – der vorige Stand läuft weiter."
        # Erfolg: den beiseitegelegten Stand entfernen (er steckt in der Sicherung, die vorher erstellt wurde)
        self.psql(f"DROP DATABASE IF EXISTS {alt_db}", zeile)
        shutil.rmtree(alt_dok, ignore_errors=True)
        # Löschungen nach Art. 17 DSGVO: Das Backend holt sie beim Start nach, meldet einen Fehler dort aber nur als
        # Warnung (der Start darf daran nicht scheitern). Deshalb hier noch einmal mit „--streng“ – der Befehl ist
        # beliebig oft ausführbar – und die Meldung an dessen Ergebnis knüpfen.
        zeile("\nLöschungen nach Art. 17 DSGVO prüfen …\n")
        rc = self.schritt("Löschungen", self.compose("exec", "-T", "backend", "python", "manage.py",
                                                    "epm_loeschungen_nachholen", "--streng"),
                          zeile, cwd=self.basis, zeitlimit=1800)
        if rc != 0:
            return 0, ("Sicherung wiederhergestellt. Alle Benutzer müssen sich neu anmelden. ACHTUNG: Löschungen nach "
                       "Art. 17 DSGVO konnten nicht vollständig nachgeholt werden – siehe Audit-Log (System) und "
                       "Backup-Seite.")
        return 0, ("Sicherung wiederhergestellt. Alle Benutzer müssen sich neu anmelden; Löschungen nach Art. 17 DSGVO "
                   "wurden erneut angewendet.")

    # ------------------------------------------------------------ Aufträge
    def ergebnis(self, auftrag_id, **werte):
        pfad = os.path.join(self.ergebnisse, f"{auftrag_id}.json")
        daten = self.lies(pfad) or {"id": auftrag_id}
        daten.update(werte)
        self.schreibe(pfad, daten)
        return daten

    def auftraege_ausfuehren(self):
        """Alle wartenden Aufträge der Reihe nach (eine Sperre verhindert parallele Läufe)."""
        os.makedirs(self.auftraege, exist_ok=True)
        with open(os.path.join(self.status, ".sperre"), "w") as sperre:
            fcntl.flock(sperre, fcntl.LOCK_EX)
            while True:
                dateien = sorted(d for d in os.listdir(self.auftraege) if d.endswith(".json"))
                if not dateien:
                    break
                for name in dateien:
                    self.auftrag(os.path.join(self.auftraege, name))
        self.ergebnisse_aufraeumen()

    def auftrag_lesen(self, pfad):
        try:
            fd = os.open(pfad, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            return None
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                os.close(fd)
                return None
            with os.fdopen(fd, encoding="utf-8") as f:
                return json.loads(f.read(65536))
        except (OSError, ValueError):
            return None

    def auftrag(self, pfad):
        daten = self.auftrag_lesen(pfad)
        try:
            os.unlink(pfad)
        except OSError:
            pass
        auftrag_id = (daten or {}).get("id", "")
        if not isinstance(daten, dict) or not isinstance(auftrag_id, str) or not ID_MUSTER.match(auftrag_id):
            return
        aktion = daten.get("aktion")
        if aktion not in AKTIONEN:
            self.ergebnis(auftrag_id, status="fehler", aktion=str(aktion)[:40], begonnen_am=jetzt_iso(), beendet_am=jetzt_iso(), rueckgabe=2,
                          ergebnis="Unbekannte Aktion – nichts ausgeführt.", ausgabe="")
            return
        parameter = daten.get("parameter") if isinstance(daten.get("parameter"), dict) else {}
        geheim = daten.get("geheim") if isinstance(daten.get("geheim"), dict) else {}
        von = daten.get("angefordert_von") if isinstance(daten.get("angefordert_von"), str) else ""
        von = von if BENUTZER_MUSTER.match(von or "") else ""
        try:
            minuten = max(0, min(60, int(parameter.get("minuten") or 0)))
        except (TypeError, ValueError):
            minuten = 0
        protokoll = []

        def zeile(text):
            protokoll.append(text)
            self.ergebnis(auftrag_id, ausgabe="".join(protokoll)[-AUSGABE_MAX:])

        start = jetzt_iso()
        simuliert = self.simuliert(aktion)
        self.ergebnis(auftrag_id, status="laeuft", aktion=aktion, begonnen_am=start, ausgabe="", ergebnis="",
                      trocken=simuliert)
        if minuten:
            beginn = datetime.fromtimestamp(time.time() + minuten * 60).strftime("%H:%M")
            if self.trocken:
                zeile(f"Probelauf: würde {minuten} Minuten bis {beginn} Uhr warten (angemeldete Benutzer sind gewarnt).\n")
            else:
                self.ergebnis(auftrag_id, ergebnis=f"Beginnt um {beginn} Uhr (angemeldete Benutzer sind gewarnt).")
                zeile(f"Warte {minuten} Minuten bis {beginn} Uhr …\n")
                time.sleep(minuten * 60)
        rc, kurz = 0, ""
        try:
            rc, kurz = self.ausfuehren(aktion, zeile, auftrag_id, parameter=parameter, geheim=geheim, von=von)
        except Exception as e:  # noqa: BLE001 – jeder Fehler soll im Ergebnis stehen
            rc, kurz = 1, f"Fehler: {e}"
            zeile(f"\n{type(e).__name__}: {e}\n")
        if aktion != "server_neustart" or rc != 0:
            try:
                self.status_schreiben()
            except Exception as e:  # noqa: BLE001
                zeile(f"\nStatus konnte nicht gemessen werden: {e}\n")
        self.ergebnis(auftrag_id, status="erledigt" if rc == 0 else "fehler", rueckgabe=rc, beendet_am=jetzt_iso(),
                      ergebnis=kurz, ausgabe="".join(protokoll)[-AUSGABE_MAX:])

    def schritt(self, titel, args, zeile, env=None, cwd=None, zeitlimit=3600, eingabe=None):
        zeile(f"\n$ {' '.join(args)}\n")
        rc, aus = self.befehl(args, env=env, cwd=cwd, zeitlimit=zeitlimit, eingabe=eingabe)
        zeile(aus)
        if rc != 0:
            zeile(f"→ {titel}: Rückgabe {rc}\n")
        return rc

    def sichern(self, zeile, art="von_hand", von="", simuliert=False):
        if simuliert:
            zeile("\n(Probelauf) Sicherung würde jetzt mit epm-backup erstellt.\n")
            return 0
        if not os.path.exists(self.backup_skript):
            zeile(f"\n{self.backup_skript} fehlt – Sicherung nicht möglich.\n")
            return 1
        env = {"EPM_BASIS": self.basis, "EPM_SICHERUNG_KONF": self.konf, "EPM_BACKUP_TAGE": str(self.aufbewahrung_tage())}
        if self.projekt:
            env["EPM_COMPOSE_PROJEKT"] = self.projekt
        args = [self.backup_skript, "--art", art] + (["--von", von] if von else [])
        rc = self.schritt("Sicherung", args, zeile, env=env, cwd=self.basis, zeitlimit=3 * 3600)
        try:
            self.sicherung_status_schreiben()
        except Exception as e:  # noqa: BLE001
            zeile(f"Status der Sicherungen nicht geschrieben: {e}\n")
        return rc

    def ausfuehren(self, aktion, zeile, auftrag_id, parameter=None, geheim=None, von=""):
        parameter = parameter or {}
        geheim = geheim or {}
        t = self.simuliert(aktion)
        name, vorher_sichern = AKTIONEN[aktion]
        if t:
            zeile("Probelauf: Es wird nichts verändert.\n")
        if aktion == "wiederherstellen" and not t:
            # erst prüfen, dann die Sicherung vorher – eine unbekannte Sicherung soll nichts auslösen
            stempel = parameter.get("stempel")
            if not isinstance(stempel, str) or not STEMPEL_MUSTER.match(stempel) or \
                    not any(s["stempel"] == stempel for s in self.sicherungen()):
                return 2, f"Die Sicherung {stempel} gibt es auf dem Server nicht (mehr)."
        if aktion == "epm_zurueck" and not t:
            # erst prüfen, dann die Sicherung vorher – eine unbekannte Version soll nichts auslösen
            fehler = self.zurueck_pruefen(parameter.get("tag"))
            if fehler:
                return 2, fehler
        vorher = None
        if vorher_sichern:
            zeile("Zuerst wird eine Sicherung erstellt.\n")
            if self.sichern(zeile, art=VORHER_ART.get(aktion, "vor_aenderung"), von=von,
                            simuliert=self.simuliert("sicherung")) != 0:
                return 1, "Abgebrochen: Die Sicherung vorher ist fehlgeschlagen. Es wurde nichts verändert."
            if not self.simuliert("sicherung"):
                vorher = (self.sicherungen() or [{}])[0].get("stempel")

        if aktion == "status_aktualisieren":
            zeile("Status wird gemessen.\n")
            return 0, "Status aktualisiert."

        if aktion == "updates_suchen":
            if os.geteuid() != 0:
                zeile("Paketlisten können nur als root aktualisiert werden; vorhandene Listen werden ausgewertet.\n")
            elif self.schritt("Paketlisten", ["apt-get", "update", "-q"], zeile, env=APT_ENV, zeitlimit=900) != 0:
                return 1, "Paketlisten konnten nicht geladen werden (Proxy/Allowlist prüfen)."
            u = self.updates()
            return 0, (f"{u.get('anzahl', 0)} Updates verfügbar, davon {u.get('sicherheit', 0)} Sicherheitsupdates."
                       if u.get("verfuegbar") else "Updates konnten nicht ermittelt werden.")

        if aktion == "updates_installieren":
            if not t and os.geteuid() == 0:
                if self.schritt("Paketlisten", ["apt-get", "update", "-q"], zeile, env=APT_ENV, zeitlimit=900) != 0:
                    return 1, "Paketlisten konnten nicht geladen werden (Proxy/Allowlist prüfen). Nichts installiert."
            args = ["apt-get", "-y", "-q", "-o", "Dpkg::Options::=--force-confdef", "-o",
                    "Dpkg::Options::=--force-confold", "upgrade", "--with-new-pkgs"]
            if t:
                args = ["apt-get", "-s", "-o", "Debug::NoLocking=true", "upgrade", "--with-new-pkgs"]
            rc = self.schritt("Updates", args, zeile, env=APT_ENV, zeitlimit=3 * 3600)
            if rc != 0:
                return rc, "Installation der Updates fehlgeschlagen – Ausgabe prüfen."
            neustart = os.path.exists("/var/run/reboot-required")
            return 0, ("Updates installiert." if not t else "Probelauf: Updates simuliert.") + (
                " Ein Neustart des Servers ist nötig." if neustart else "")

        if aktion == "server_neustart":
            self.ergebnis(auftrag_id, status="erledigt", rueckgabe=0, beendet_am=jetzt_iso(),
                          ergebnis="Neustart eingeleitet." if not t else "Probelauf: Neustart nicht ausgeführt.")
            if t:
                zeile("\n(Probelauf) systemctl reboot\n")
                return 0, "Probelauf: Neustart nicht ausgeführt."
            zeile("\n$ systemctl reboot\n")
            self.befehl(["systemctl", "reboot"], zeitlimit=60)
            return 0, "Neustart eingeleitet."

        if aktion == "epm_update":
            # Aktualisieren aus der Oberfläche (Wunsch 07.10.2026, F123). Das Skript holt den Stand, baut, sichert
            # und stellt um; seine ausführliche Ausgabe steht in /var/log/epm-update.log. Ohne Terminal gibt es
            # keine Tastatur, deshalb ausdrücklich ohne Standardeingabe.
            skript = "/usr/local/sbin/epm-update"
            args = [skript] if parameter.get("tests") else [skript, "--ohne-tests"]
            if t:
                zeile(f"\n(Probelauf) {' '.join(args)}\n")
                return 0, "Probelauf: EPM nicht aktualisiert."
            if not os.path.exists(skript):
                return 2, "Auf diesem Server ist „epm-update“ nicht eingerichtet."
            zeile("EPM wird aktualisiert. Beim Umstellen ist die Oberfläche kurz nicht erreichbar; der Auftrag\n"
                  "läuft auf dem Server weiter, das Ergebnis steht danach hier.\n")
            rc = self.schritt("Update", args, zeile, cwd=self.basis, zeitlimit=4 * 3600, eingabe="")
            if rc == 0:
                return 0, "EPM ist aktualisiert."
            return rc, ("Das Update ist fehlgeschlagen – die Ausgabe steht oben, ausführlich in "
                        "/var/log/epm-update.log. Die bisherige Version läuft weiter.")

        if aktion == "epm_neustart":
            if t:
                zeile(f"\n(Probelauf) {' '.join(self.compose('restart'))}\n")
                return 0, "Probelauf: EPM nicht neu gestartet."
            rc = self.schritt("Neustart", self.compose("restart"), zeile, cwd=self.basis, zeitlimit=600)
            return rc, "EPM neu gestartet." if rc == 0 else "EPM-Neustart fehlgeschlagen."

        if aktion == "sicherung":
            rc = self.sichern(zeile, art="von_hand", von=von, simuliert=t)
            return rc, ("Sicherung erstellt." if not t else "Probelauf: Sicherung nicht erstellt.") if rc == 0 else \
                "Sicherung fehlgeschlagen."

        if aktion == "sicherung_passwort":
            if t:
                return 0, "Probelauf: Passwort nicht gespeichert."
            return self.passwort_setzen(geheim.get("passwort"), von, zeile)

        if aktion == "sicherung_ziel":
            if t:
                return 0, "Probelauf: Ziel nicht gespeichert."
            return self.ziel_setzen({**parameter, "kennwort": geheim.get("kennwort")}, von, zeile)

        if aktion == "sicherung_ziel_entfernen":
            return (0, "Probelauf: Ziel nicht entfernt.") if t else self.ziel_entfernen(zeile)

        if aktion == "sicherung_ziel_testen":
            return (0, "Probelauf: Verbindung nicht getestet.") if t else self.ziel_testen(zeile)

        if aktion == "sicherung_uebertragen":
            return (0, "Probelauf: nichts übertragen.") if t else self.uebertragen(zeile, manuell=True)

        if aktion == "sicherung_aufbewahrung":
            return (0, "Probelauf: Aufbewahrung nicht geändert.") if t else \
                self.aufbewahrung_setzen(parameter.get("tage"), zeile)

        if aktion == "sicherung_bereitstellen":
            return (0, "Probelauf: nichts bereitgestellt.") if t else self.bereitstellen(parameter.get("stempel"), zeile)

        if aktion == "sicherung_einlesen":
            return (0, "Probelauf: nichts eingelesen.") if t else \
                self.einlesen(parameter.get("upload"), geheim.get("passwort"), von, zeile)

        if aktion == "wiederherstellen":
            if t:
                zeile(f"\n(Probelauf) Sicherung {parameter.get('stempel')} würde zurückgespielt.\n")
                return 0, "Probelauf: nichts zurückgespielt."
            return self.wiederherstellen(parameter.get("stempel"), von, auftrag_id, zeile, vorher=vorher)

        if aktion == "datenbank_leeren":
            return self.leeren(parameter.get("behalten"), von, zeile, vorher=vorher, simuliert=t)

        # Systemverwaltung ohne SSH (10.10.2026, F179)
        if aktion == "sicherung_loeschen":
            return self.sicherungen_loeschen(parameter.get("stempel"), zeile, simuliert=t)

        if aktion == "dienst_neustart":
            return self.dienst_neu_starten(parameter.get("dienst"), zeile, simuliert=t)

        if aktion == "epm_zurueck":
            return self.zurueckschalten(parameter.get("tag"), zeile, simuliert=t)

        if aktion == "epm_paket":
            return self.paket_einspielen(parameter.get("upload"), zeile, simuliert=t)

        if aktion == "epm_paket_erstellen":
            return self.paket_erstellen(zeile, simuliert=t)

        if aktion == "zertifikat_erneuern":
            if t:
                zeile(f"\n(Probelauf) {EPM_ZERTIFIKAT} erneuern\n")
                return 0, "Probelauf: Zertifikat nicht erneuert."
            if not os.path.exists(EPM_ZERTIFIKAT):
                return 2, "Auf diesem Server ist „epm-zertifikat“ nicht eingerichtet."
            if not os.path.isfile(os.path.join(CA_ORDNER, "epm-ca.key")):
                return 2, ("Es gibt keine eigene CA auf dem Server – erneuern geht nur mit ihr. Ein Zertifikat einer "
                           "anderen CA bitte über „Zertifikat importieren“ austauschen.")
            rc = self.schritt("Zertifikat", [EPM_ZERTIFIKAT, "erneuern"], zeile, zeitlimit=300, eingabe="")
            return (0, "Neues Serverzertifikat ausgestellt; Nginx hat es geladen.") if rc == 0 else \
                (rc, "Erneuern fehlgeschlagen – Ausgabe prüfen. Das bisherige Zertifikat gilt weiter.")

        if aktion == "zertifikat_importieren":
            return self.zertifikat_importieren(geheim, zeile, simuliert=t)

        if aktion == "ocr_modelle":
            return self.ocr_einspielen(parameter.get("upload"), zeile, simuliert=t)

        if aktion == "sicherung_zeitplan":
            return self.zeitplan_setzen(parameter.get("uhrzeit"), parameter.get("tage"), zeile, simuliert=t)

        if aktion == "journal_aufraeumen":
            return self.journal_aufraeumen(parameter.get("art"), parameter.get("wert"), zeile, simuliert=t)

        if aktion == "images_loeschen":
            return self.images_loeschen(parameter.get("dateien"), parameter.get("tags"), zeile, simuliert=t)

        if aktion == "uhr_einstellen":
            return self.uhr_einstellen(parameter, zeile, simuliert=t)

        if aktion == "protokoll":
            return self.protokoll_abrufen(parameter.get("quelle"), parameter.get("zeilen"), auftrag_id, zeile)

        if aktion == "docker_aufraeumen":
            if t:
                rc = self.schritt("Images", ["docker", "image", "ls", "--filter", "dangling=true"], zeile, zeitlimit=60)
                return 0, "Probelauf: nicht mehr benutzte Images nur angezeigt."
            rc = self.schritt("Images", ["docker", "image", "prune", "-f"], zeile, zeitlimit=900)
            rc2 = self.schritt("Build-Zwischenstände", ["docker", "builder", "prune", "-f"], zeile, zeitlimit=900)
            return (rc or rc2), "Nicht mehr benutzte Docker-Daten entfernt (markierte Versionen bleiben)." \
                if not (rc or rc2) else "Aufräumen fehlgeschlagen."

        if aktion == "pakete_aufraeumen":
            args = ["apt-get", "-y", "-q", "autoremove", "--purge"] if not t else ["apt-get", "-s", "autoremove"]
            rc = self.schritt("Pakete", args, zeile, env=APT_ENV, zeitlimit=1800)
            if rc == 0 and not t:
                rc = self.schritt("Paketcache", ["apt-get", "-q", "autoclean"], zeile, env=APT_ENV, zeitlimit=600)
            return rc, ("Nicht mehr benötigte Pakete entfernt." if not t else "Probelauf: nur simuliert.") if rc == 0 \
                else "Aufräumen fehlgeschlagen."

        return 2, f"{name}: nicht umgesetzt."

    # ------------------------------------------------------------ Systemverwaltung ohne SSH: Aufträge (10.10.2026)
    def sicherungen_loeschen(self, liste, zeile, simuliert=False):
        """Ausgewählte Sicherungen aus dem Backup-Ordner löschen (Administration › Backup, Mehrfachauswahl). Gelöscht
        werden nur Dateien, deren Name genau zu einer EPM-Sicherung mit diesem Stempel passt (dieselben Muster wie die
        Liste) – gefunden über den Ordnerinhalt, nie über einen Pfad aus dem Auftrag. Die jüngste Sicherung bleibt
        immer; im Übertragungsziel wird nichts gelöscht (dort gilt die eigene Aufbewahrung)."""
        if not isinstance(liste, list) or not liste or len(liste) > LOESCHEN_MAX \
                or any(not isinstance(s, str) or not STEMPEL_MUSTER.match(s) for s in liste) or len(set(liste)) != len(liste):
            return 2, "Ungültige Auswahl – nichts gelöscht."
        vorhanden = self.sicherungen()
        bekannt = {s["stempel"]: s for s in vorhanden}
        fehlen = [s for s in liste if s not in bekannt]
        if fehlen:
            return 2, f"Diese Sicherungen gibt es auf dem Server nicht (mehr): {', '.join(fehlen[:5])} – nichts gelöscht."
        if vorhanden[0]["stempel"] in liste:
            return 2, "Die jüngste Sicherung bleibt immer erhalten – nichts gelöscht."
        groesse = sum(bekannt[s]["groesse"] for s in liste)
        zeile(f"{len(liste)} Sicherung(en), zusammen {groesse} Bytes: {', '.join(sorted(liste))}\n")
        if simuliert:
            zeile("(Probelauf) Die Dateien würden jetzt gelöscht.\n")
            return 0, f"Probelauf: {len(liste)} Sicherung(en) nicht gelöscht."
        if self.uebertragung_laeuft():
            return 1, "Gerade läuft eine Übertragung zum Ziel – bitte danach erneut löschen. Nichts gelöscht."
        with open(os.path.join(self.backup, ".epm-backup.sperre"), "a") as sperre:
            try:
                fcntl.flock(sperre, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return 1, "Gerade läuft eine Sicherung – bitte danach erneut löschen. Nichts gelöscht."
            weg = set(liste)
            entfernt, frei = 0, 0
            for n in sorted(os.listdir(self.backup)):
                m = DATEI_MUSTER.match(n)
                st = m.group(2) if m else (NEBEN_MUSTER.match(n).group(1) if NEBEN_MUSTER.match(n) else None)
                if st not in weg:
                    continue
                pfad = os.path.join(self.backup, n)
                try:
                    info = os.lstat(pfad)
                    if not stat.S_ISREG(info.st_mode):
                        zeile(f"Übersprungen (keine gewöhnliche Datei): {n}\n")
                        continue
                    os.unlink(pfad)
                    entfernt += 1
                    frei += info.st_size
                except OSError as e:
                    zeile(f"Nicht gelöscht: {n} ({e.strerror})\n")
            # eine zum Herunterladen bereitgelegte Kopie gehört dazu
            for st in weg:
                try:
                    os.unlink(os.path.join(self.download, f"epm-sicherung_{st}.tar"))
                except OSError:
                    pass
            fcntl.flock(sperre, fcntl.LOCK_UN)
        stand = self.uebertragung_stand()
        for k in list(stand["uebertragen"]):
            stand["uebertragen"][k] = {st: z for st, z in stand["uebertragen"][k].items() if st not in weg}
        self.schreibe(self.uebertragung_pfad(), stand, modus=0o600)
        rest = {s["stempel"] for s in self.sicherungen()} & weg
        self.sicherung_status_schreiben()
        zeile(f"{entfernt} Dateien gelöscht, {frei} Bytes frei.\n")
        if rest:
            return 1, f"Nicht alle Sicherungen ließen sich löschen ({', '.join(sorted(rest))}) – Ausgabe prüfen."
        return 0, f"{len(liste)} Sicherung(en) gelöscht ({frei // (1024 * 1024)} MB frei)."

    def dienst_neu_starten(self, dienst, zeile, simuliert=False):
        if dienst not in DIENSTE:
            return 2, "Unbekannter Dienst – nichts neu gestartet."
        args = self.compose("restart", dienst)
        if simuliert:
            zeile(f"\n(Probelauf) {' '.join(args)}\n")
            return 0, f"Probelauf: Dienst „{dienst}“ nicht neu gestartet."
        rc = self.schritt("Neustart", args, zeile, cwd=self.basis, zeitlimit=600)
        if rc == 0 and dienst in ("backend", "db"):
            self.backend_gesund(zeile, sekunden=180)
        return rc, f"Dienst „{dienst}“ neu gestartet." if rc == 0 else f"Neustart von „{dienst}“ fehlgeschlagen."

    def zurueck_pruefen(self, tag):
        if not isinstance(tag, str) or not TAG_MUSTER.match(tag):
            return "Unbekannte Version – nichts umgestellt."
        v = self.epm_versionen()
        e = next((x for x in v["liste"] if x["tag"] == tag), None)
        if e is None or not e["vollstaendig"]:
            return f"Die Version {tag} ist auf dem Server nicht (vollständig) vorhanden – nichts umgestellt."
        if e["aktiv"]:
            return f"Die Version {tag} läuft bereits."
        if not os.path.exists(EPM_UPDATE):
            return "Auf diesem Server ist „epm-update“ nicht eingerichtet."
        return None

    def zurueckschalten(self, tag, zeile, simuliert=False):
        """Auf eine frühere, noch vorhandene Version umstellen (epm-update --zurueck). Datenbank-Migrationen werden
        dabei nicht zurückgedreht – deshalb vorher eine Sicherung (AKTIONEN: vorher sichern)."""
        if simuliert:
            if not isinstance(tag, str) or not TAG_MUSTER.match(tag):
                return 2, "Unbekannte Version – nichts umgestellt."
            zeile(f"\n(Probelauf) {EPM_UPDATE} --zurueck {tag}\n")
            return 0, f"Probelauf: nicht auf {tag} zurückgeschaltet."
        fehler = self.zurueck_pruefen(tag)
        if fehler:
            return 2, fehler
        rc = self.schritt("Zurückschalten", [EPM_UPDATE, "--zurueck", tag], zeile, cwd=self.basis, zeitlimit=1800,
                          eingabe="")
        if rc == 0:
            return 0, (f"EPM läuft jetzt mit Version {tag}. Datenbank-Migrationen wurden nicht zurückgedreht – bei "
                       "Fehlern die Sicherung von eben wiederherstellen.")
        return rc, "Zurückschalten fehlgeschlagen – Ausgabe prüfen."

    def upload_uebernehmen(self, kennung, art, zeile):
        """Hochgeladene Datei (Update-Paket, OCR-Modelle) aus dem Upload-Ordner in einen nur für root beschreibbaren
        Ordner kopieren – danach kann das Backend sie nicht mehr verändern – und dabei die SHA-256 berechnen.
        Rückgabe: (Pfad, Angaben, Fehlertext)."""
        if not isinstance(kennung, str) or not ID_MUSTER.match(kennung):
            return None, None, "Unbekannter Upload."
        quelle = os.path.join(self.upload, f"{kennung}.teil")
        neben = os.path.join(self.upload, f"{kennung}.json")
        try:
            fd = os.open(neben, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, encoding="utf-8") as f:
                meta = json.loads(f.read(65536))
        except (OSError, ValueError):
            meta = None
        if not isinstance(meta, dict) or meta.get("art") != art:
            return None, None, "Die hochgeladene Datei liegt nicht (mehr) auf dem Server."
        try:
            fd = os.open(quelle, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            return None, None, "Die hochgeladene Datei liegt nicht (mehr) auf dem Server."
        ordner = os.path.join(self.basis, "images")
        os.makedirs(ordner, mode=0o755, exist_ok=True)
        ziel = os.path.join(ordner, f".eingang-{kennung}.tar")
        h = hashlib.sha256()
        groesse = 0
        with os.fdopen(fd, "rb") as f:
            info = os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size != meta.get("groesse"):
                return None, None, "Die hochgeladene Datei ist unvollständig."
            try:
                frei = os.statvfs(ordner)
                if frei.f_bavail * frei.f_frsize < 2 * info.st_size + 256 * 1024 * 1024:
                    return None, None, "Zu wenig freier Speicher auf dem Server."
            except OSError:
                pass
            zfd = os.open(ziel, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(zfd, "wb") as z:
                for block in iter(lambda: f.read(1 << 20), b""):
                    h.update(block)
                    z.write(block)
                    groesse += len(block)
        for pfad in (quelle, neben):
            try:
                os.unlink(pfad)
            except OSError:
                pass
        name = str(meta.get("name") or "")[:200]
        zeile(f"Datei „{name}“, {groesse} Bytes, SHA-256 {h.hexdigest()}\n")
        return ziel, {"name": name, "groesse": groesse, "sha256": h.hexdigest()}, None

    @staticmethod
    def tar_pruefen(pfad, muster):
        """Nur Dateien und Ordner mit erlaubten Namen (``muster``), keine Verweise, keine absoluten Pfade, kein „..“.
        Rückgabe: (Fehlertext | None, Namen, Inhalt der kleinen Datei „TAG“)."""
        try:
            with tarfile.open(pfad, "r:") as tar:
                namen, tag = set(), ""
                for g in tar.getmembers():
                    name = g.name[2:] if g.name.startswith("./") else g.name
                    name = name.rstrip("/")
                    if name in ("", "."):
                        continue
                    if not (g.isreg() or g.isdir()) or name.startswith("/") or ".." in name.split("/") \
                            or not muster.match(name):
                        return f"unerwarteter Inhalt „{name[:80]}“", None, ""
                    namen.add(name)
                    if name == "TAG" and g.isreg() and g.size < 200:
                        tag = tar.extractfile(g).read().decode(errors="replace").strip()
                return None, namen, tag
        except (tarfile.TarError, OSError, EOFError):
            return "kein lesbares tar-Archiv", None, ""

    def paket_einspielen(self, kennung, zeile, simuliert=False):
        """Update-Paket (epm-update --paket-erstellen auf der Test-VM) einspielen: statt scp hochgeladen, hier geprüft
        (Inhalt, Version) und an „epm-update --paket“ übergeben, das die Prüfsummen prüft, sichert und umstellt."""
        pfad, info, fehler = self.upload_uebernehmen(kennung, "paket", zeile)
        if fehler:
            return 2, fehler
        try:
            fehler, namen, tag = self.tar_pruefen(pfad, PAKET_INHALT)
            if fehler:
                return 1, f"Das ist kein Update-Paket von EPM ({fehler}). Nichts umgestellt."
            if not {"TAG", "SHA256SUMS", "images.tar"} <= namen or not TAG_MUSTER.match(tag):
                return 1, "Das Update-Paket ist unvollständig (Version, Prüfsummen oder Images fehlen). Nichts umgestellt."
            zeile(f"Version {tag} · SHA-256 der Datei: {info['sha256']} (mit der Anzeige auf der Test-VM vergleichen)\n")
            if simuliert:
                zeile(f"\n(Probelauf) {EPM_UPDATE} --paket … --ohne-tests\n")
                return 0, f"Probelauf: Update-Paket {tag} geprüft, nicht eingespielt."
            if not os.path.exists(EPM_UPDATE):
                return 2, "Auf diesem Server ist „epm-update“ nicht eingerichtet."
            zeile("EPM wird umgestellt. Die Oberfläche ist dabei kurz nicht erreichbar; das Ergebnis steht danach hier.\n")
            rc = self.schritt("Update-Paket", [EPM_UPDATE, "--paket", pfad, "--ohne-tests"], zeile, cwd=self.basis,
                              zeitlimit=4 * 3600, eingabe="")
            if rc == 0:
                return 0, f"Update-Paket {tag} eingespielt – EPM läuft mit der neuen Version."
            return rc, ("Einspielen fehlgeschlagen – Ausgabe oben, ausführlich in /var/log/epm-update.log. Die "
                        "bisherige Version läuft weiter.")
        finally:
            try:
                os.unlink(pfad)
            except OSError:
                pass

    def paket_erstellen(self, zeile, simuliert=False):
        """Update-Paket der laufenden Version erstellen (nur Test-VM mit Code aus GitHub) und für 2 Stunden zum
        Herunterladen bereitlegen – statt es per scp abzuholen."""
        if simuliert:
            zeile(f"\n(Probelauf) {EPM_UPDATE} --paket-erstellen\n")
            return 0, "Probelauf: kein Paket erstellt."
        if not os.path.exists(EPM_UPDATE):
            return 2, "Auf diesem Server ist „epm-update“ nicht eingerichtet."
        rc = self.schritt("Paket", [EPM_UPDATE, "--paket-erstellen"], zeile, cwd=self.basis, zeitlimit=2 * 3600,
                          eingabe="")
        if rc != 0:
            return rc, "Paket erstellen fehlgeschlagen – Ausgabe prüfen (geht nur auf der Test-VM mit Code aus GitHub)."
        erstellt = sorted(self.pakete()["erstellt"], key=lambda p: p["zeit"], reverse=True)
        if not erstellt:
            return 1, "Das Paket wurde nicht gefunden."
        p = erstellt[0]
        self.austausch_ordner()
        quelle = os.path.join(self.basis, "images", p["datei"])
        ziel = os.path.join(self.download, p["datei"])
        try:
            frei = os.statvfs(self.download)
            if frei.f_bavail * frei.f_frsize < p["groesse"] + 256 * 1024 * 1024:
                return 0, f"Update-Paket {p['tag']} erstellt; zum Herunterladen ist zu wenig Speicher frei."
        except OSError:
            pass
        tmp = f"{ziel}.teil"
        try:
            shutil.copyfile(quelle, tmp, follow_symlinks=False)
            if os.geteuid() == 0:
                os.chown(tmp, 0, APP_GID)
            os.chmod(tmp, 0o640)
            os.replace(tmp, ziel)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return 0, f"Update-Paket {p['tag']} erstellt; es liegt {BUENDEL_STUNDEN} Stunden zum Herunterladen bereit."

    @staticmethod
    def pem_pruefen(text, art):
        if not isinstance(text, str) or not text.strip() or len(text) > PEM_MAX or "\0" in text:
            return False
        if art == "schluessel":
            return "-----BEGIN" in text and "PRIVATE KEY-----" in text
        return "-----BEGIN CERTIFICATE-----" in text and "-----END CERTIFICATE-----" in text

    def zertifikat_importieren(self, geheim, zeile, simuliert=False):
        """Zertifikat einer anderen CA (z. B. der OPNsense) übernehmen: Zertifikat, Schlüssel und – falls vorhanden – das
        CA-Zertifikat kommen nur über die Auftragsdatei (0600, sofort gelöscht), liegen hier nur kurz in einem Ordner
        für root und gehen an „epm-zertifikat importieren“ (prüft Name, Schlüssel und Kette)."""
        crt, key, ca = geheim.get("zertifikat"), geheim.get("schluessel"), geheim.get("ca")
        if not self.pem_pruefen(crt, "zertifikat") or not self.pem_pruefen(key, "schluessel") \
                or (ca and not self.pem_pruefen(ca, "zertifikat")):
            return 2, "Zertifikat, Schlüssel oder CA-Zertifikat fehlen oder sind kein PEM – nichts geändert."
        zeile("Zertifikat und Schlüssel (PEM) erhalten" + (", dazu das CA-Zertifikat.\n" if ca else ".\n"))
        if simuliert:
            zeile(f"\n(Probelauf) {EPM_ZERTIFIKAT} importieren CRT KEY{' CA' if ca else ''}\n")
            return 0, "Probelauf: Zertifikat nicht übernommen."
        if not os.path.exists(EPM_ZERTIFIKAT):
            return 2, "Auf diesem Server ist „epm-zertifikat“ nicht eingerichtet."
        ordner = tempfile.mkdtemp(prefix="epm-zertifikat-")
        try:
            dateien = []
            for name, inhalt in (("epm.crt", crt), ("epm.key", key), ("ca.crt", ca)):
                if not inhalt:
                    continue
                pfad = os.path.join(ordner, name)
                fd = os.open(pfad, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(inhalt.replace("\r\n", "\n"))
                dateien.append(pfad)
            rc = self.schritt("Zertifikat", [EPM_ZERTIFIKAT, "importieren", *dateien], zeile, zeitlimit=300, eingabe="")
        finally:
            shutil.rmtree(ordner, ignore_errors=True)
        return (0, "Zertifikat übernommen; Nginx hat es geladen.") if rc == 0 else \
            (rc, "Übernehmen fehlgeschlagen – Ausgabe prüfen (Name, Schlüssel, Kette). Das bisherige Zertifikat gilt weiter.")

    def ocr_einspielen(self, kennung, zeile, simuliert=False):
        """Offline vorbereitete OCR-Modelle (werkzeuge/ocr-modelle.sh vorbereiten) einspielen – statt scp hochgeladen.
        „epm-ocr-modelle einspielen“ prüft die Prüfsummen; das nächste „EPM aktualisieren“ baut sie ins Image."""
        pfad, _info, fehler = self.upload_uebernehmen(kennung, "ocr", zeile)
        if fehler:
            return 2, fehler
        try:
            fehler, namen, _tag = self.tar_pruefen(pfad, OCR_INHALT)
            if fehler:
                return 1, f"Das sind keine vorbereiteten OCR-Modelle ({fehler}). Nichts eingespielt."
            if "modelle.json" not in namen or not any(n.startswith("dateien/") for n in namen):
                return 1, "Die Datei enthält keine Modelle (modelle.json und Ordner „dateien“ fehlen). Nichts eingespielt."
            if simuliert:
                zeile(f"\n(Probelauf) {EPM_OCR_MODELLE} einspielen …\n")
                return 0, "Probelauf: OCR-Modelle geprüft, nicht eingespielt."
            if not os.path.exists(EPM_OCR_MODELLE):
                return 2, "Auf diesem Server ist „epm-ocr-modelle“ nicht eingerichtet (kommt mit „EPM aktualisieren“)."
            rc = self.schritt("OCR-Modelle", [EPM_OCR_MODELLE, "einspielen", pfad], zeile, zeitlimit=1800, eingabe="")
            if rc == 0:
                return 0, "OCR-Modelle eingespielt. Mit „EPM aktualisieren“ baut der Server sie ins Image ein."
            return rc, "Einspielen fehlgeschlagen – Ausgabe prüfen (Prüfsummen, passende Modell-Liste)."
        finally:
            try:
                os.unlink(pfad)
            except OSError:
                pass

    def protokoll_abrufen(self, quelle, zeilen, auftrag_id, zeile):
        """Letzte Zeilen eines Protokolls (nur lesend, auch im Probelauf echt) in ``status/protokolle/<Auftrag>.log``
        schreiben – nur für root und die Gruppe des Backends lesbar, nach 1 Stunde entfernt. Der Inhalt kommt nicht in
        die Ausgabe des Auftrags und damit nicht in die Datenbank."""
        if quelle not in PROTOKOLLE or isinstance(zeilen, bool) or zeilen not in PROTOKOLL_ZEILEN:
            return 2, "Unbekanntes Protokoll."
        if quelle in DIENSTE:
            rc, text = self.befehl(self.compose("logs", "--no-color", "--timestamps", "--tail", str(zeilen), quelle),
                                   cwd=self.basis, zeitlimit=120)
        elif quelle in PROTOKOLL_JOURNAL:
            args = ["journalctl", "--no-pager", "-o", "short-iso", "-n", str(zeilen)]
            for einheit in PROTOKOLL_JOURNAL[quelle]:
                args += ["-u", einheit]
            rc, text = self.befehl(args, zeitlimit=120)
        else:
            try:
                with open("/var/log/epm-update.log", encoding="utf-8", errors="replace") as f:
                    rc, text = 0, "".join(deque(f, maxlen=zeilen))
            except OSError:
                rc, text = 1, "Es gibt noch kein Protokoll eines Updates (/var/log/epm-update.log).\n"
        text = text[-PROTOKOLL_MAX:]
        os.makedirs(self.protokolle, mode=0o750, exist_ok=True)
        if os.geteuid() == 0:
            os.chown(self.protokolle, 0, APP_GID)
            os.chmod(self.protokolle, 0o750)
        pfad = os.path.join(self.protokolle, f"{auftrag_id}.log")
        tmp = f"{pfad}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        if os.geteuid() == 0:
            os.chown(tmp, 0, APP_GID)
        os.replace(tmp, pfad)
        anzahl = text.count("\n")
        zeile(f"{PROTOKOLLE[quelle]}: {anzahl} Zeilen abgerufen (liegt eine Stunde zum Ansehen bereit).\n")
        if rc != 0:
            return 1, f"{PROTOKOLLE[quelle]}: nicht vollständig lesbar (Rückgabe {rc}) – was zu lesen war, steht unten."
        return 0, f"{PROTOKOLLE[quelle]}: {anzahl} Zeilen."

    def leeren(self, behalten, von, zeile, vorher=None, simuliert=False):
        """Datenbank leeren (U27): alle Akten, Dokumente, Versorger, Ärzte, nicht ausgewählte Benutzer und das Audit-Log
        entfernen – im Backend (``manage.py epm_datenbank_leeren``), nach der Sicherung oben."""
        if not isinstance(behalten, list) or not all(isinstance(x, int) and not isinstance(x, bool) and x > 0
                                                     for x in behalten):
            return 2, "Ungültige Auswahl der Konten – nichts verändert."
        if not von:
            return 2, "Unbekannter Auftraggeber – nichts verändert."
        if not vorher and not simuliert:
            return 1, "Ohne Sicherung vorher wird nicht geleert – nichts verändert."
        args = ["epm_datenbank_leeren", "--von", von, "--behalten", ",".join(str(x) for x in behalten),
                "--sicherung", vorher or "", "--ja"]
        if simuliert:
            zeile(f"\n(Probelauf) würde ausführen: manage.py {' '.join(args)}\n")
            return 0, "Probelauf: nichts geleert."
        rc = self.schritt("Leeren", self.compose("exec", "-T", "backend", "python", "manage.py", *args), zeile,
                          cwd=self.basis, zeitlimit=3600)
        if rc != 0:
            return 1, f"Leeren fehlgeschlagen – die Sicherung {vorher} enthält den Stand davor."
        return 0, (f"Datenbank geleert (Sicherung vorher: {vorher}). Alle anderen Anmeldungen sind beendet; Musterdaten "
                   "werden nicht mehr automatisch angelegt.")

    # ------------------------------------------------------------ Nachtrag 10.10.2026: Zeitplan, Aufräumen, Uhrzeit
    def zeitplan_setzen(self, uhrzeit, tage, zeile, simuliert=False):
        """Zeitplan der nächtlichen Sicherung: Drop-in für epm-backup.timer (OnCalendar), daemon-reload, Timer neu."""
        if not isinstance(uhrzeit, str) or not ZEIT_MUSTER.match(uhrzeit) or tage not in ZEITPLAN_TAGE:
            return 2, "Ungültiger Zeitplan – bitte Uhrzeit (HH:MM) und täglich oder werktags wählen."
        inhalt = ("# Zeitplan aus Administration › Backup (epm-systemagent)\n[Timer]\nOnCalendar=\n"
                  f"OnCalendar={ZEITPLAN_TAGE[tage]} {uhrzeit}:00\n")
        text = f"{'werktags (Mo–Fr)' if tage == 'werktags' else 'täglich'} um {uhrzeit} Uhr"
        zeile(f"Zeitplan: {text}\n{inhalt}")
        if simuliert:
            return 0, f"Probelauf: Zeitplan ({text}) nicht gesetzt."
        pfad = os.path.join(self.systemd, ZEITPLAN_DATEI)
        os.makedirs(os.path.dirname(pfad), mode=0o755, exist_ok=True)
        tmp = f"{pfad}.tmp{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(inhalt)
        os.chmod(tmp, 0o644)
        os.replace(tmp, pfad)
        rc = self.schritt("systemd", ["systemctl", "daemon-reload"], zeile, zeitlimit=60)
        if rc == 0:
            rc = self.schritt("Timer", ["systemctl", "restart", "epm-backup.timer"], zeile, zeitlimit=60)
        self.sicherung_status_schreiben()
        if rc != 0:
            return rc, f"Zeitplan gespeichert ({text}), aber systemd hat ihn nicht übernommen – Ausgabe prüfen."
        return 0, f"Die Sicherung läuft ab jetzt {text}."

    def journal_aufraeumen(self, art, wert, zeile, simuliert=False):
        if art == "groesse" and wert in JOURNAL_GROESSE:
            args = ["journalctl", f"--vacuum-size={wert}"]
        elif art == "zeit" and wert in JOURNAL_ZEIT:
            args = ["journalctl", f"--vacuum-time={wert}"]
        else:
            return 2, "Ungültige Auswahl – nichts aufgeräumt."
        if simuliert:
            zeile(f"\n(Probelauf) {' '.join(args)}\n")
            return 0, "Probelauf: Journal nicht aufgeräumt."
        rc = self.schritt("Journal", args, zeile, zeitlimit=600)
        try:
            os.unlink(os.path.join(self.status, ".journal.json"))
        except OSError:
            pass
        j = self.journal() or {}
        return (0, "Journal aufgeräumt" + (f" – belegt jetzt {j['groesse'] // (1024 * 1024)} MB." if j.get("groesse") else ".")) \
            if rc == 0 else (rc, "Aufräumen des Journals fehlgeschlagen.")

    def images_loeschen(self, dateien, tags, zeile, simuliert=False):
        """Alte Image-Dateien/Update-Pakete unter images/ und alte Docker-Images von EPM löschen. Die laufende und die
        vorherige Version (Zurückschalten) bleiben immer; ohne Liste der Versionen wird nichts gelöscht."""
        dateien = dateien or []
        tags = tags or []
        if not isinstance(dateien, list) or not isinstance(tags, list) or not (dateien or tags) \
                or len(dateien) + len(tags) > 100 \
                or any(not isinstance(d, str) or not IMAGE_DATEI_MUSTER.match(d) for d in dateien) \
                or any(not isinstance(x, str) or not TAG_MUSTER.match(x) for x in tags):
            return 2, "Ungültige Auswahl – nichts gelöscht."
        v = self.epm_versionen()
        geschuetzt = self.geschuetzte_tags(v)
        if geschuetzt is None:
            return 1, "Die laufende Version ist nicht zu ermitteln – zur Sicherheit wird nichts gelöscht."
        betroffen = sorted({IMAGE_DATEI_MUSTER.match(d).group(2) for d in dateien} | set(tags))
        if betroffen and set(betroffen) & geschuetzt:
            return 2, (f"Die laufende und die vorherige Version ({', '.join(sorted(geschuetzt))}) bleiben immer – "
                       "nichts gelöscht.")
        vorhanden = {e["datei"] for e in self.image_dateien(v)}
        bekannt = {e["tag"] for e in v["liste"]}
        fehlen = [d for d in dateien if d not in vorhanden] + [x for x in tags if x not in bekannt]
        if fehlen:
            return 2, f"Nicht (mehr) vorhanden: {', '.join(fehlen[:5])} – nichts gelöscht."
        zeile(f"Geschützt: {', '.join(sorted(geschuetzt))}\nDateien: {', '.join(dateien) or '—'}\n"
              f"Docker-Images: {', '.join(tags) or '—'}\n")
        if simuliert:
            return 0, f"Probelauf: {len(dateien)} Dateien und {len(tags)} Versionen nicht gelöscht."
        frei, fehler = 0, 0
        for d in dateien:
            pfad = os.path.join(self.basis, "images", d)
            try:
                info = os.lstat(pfad)
                if stat.S_ISREG(info.st_mode):
                    os.unlink(pfad)
                    frei += info.st_size
            except OSError as e:
                fehler += 1
                zeile(f"Nicht gelöscht: {d} ({e.strerror})\n")
        for x in tags:
            for image in ("epm-backend", "epm-web"):
                # ohne -f: ein Image, das ein Container benutzt, lehnt docker ab
                if self.schritt("Image", ["docker", "image", "rm", f"{image}:{x}"], zeile, zeitlimit=300) != 0:
                    fehler += 1
        if fehler:
            return 1, f"Nicht alles ließ sich löschen ({fehler} Fehler) – Ausgabe prüfen."
        return 0, f"{len(dateien)} Dateien ({frei // (1024 * 1024)} MB) und {len(tags)} Versionen gelöscht."

    def uhr_einstellen(self, p, zeile, simuliert=False):
        """Zeitzone, Zeitsynchronisation (an/aus, eigene Zeitserver z. B. die OPNsense) und – ohne NTP – die Uhrzeit."""
        zone, ntp, server, zeit = p.get("zeitzone"), p.get("ntp"), p.get("server"), p.get("zeit")
        if not isinstance(ntp, bool) or not isinstance(server, list) or len(server) > NTP_SERVER_MAX \
                or any(not isinstance(s, str) or not NTP_SERVER_MUSTER.match(s) for s in server):
            return 2, "Ungültige Angaben zur Zeitsynchronisation – nichts geändert."
        if zone is not None and (not isinstance(zone, str) or not ZEITZONE_MUSTER.match(zone)):
            return 2, "Unbekannte Zeitzone – nichts geändert."
        if zone is not None and self.zeitzonen() and zone not in self.zeitzonen():
            return 2, f"Die Zeitzone „{zone}“ kennt der Server nicht – nichts geändert."
        if zeit is not None and (ntp or not isinstance(zeit, str) or not ZEIT_SETZEN_MUSTER.match(zeit)):
            return 2, "Die Uhrzeit lässt sich nur bei ausgeschalteter Zeitsynchronisation setzen (JJJJ-MM-TT HH:MM:SS)."
        schritte = []
        if zone:
            schritte.append(("Zeitzone", ["timedatectl", "set-timezone", zone]))
        dienst = self.ntp_dienst()
        zeile(f"Zeitsynchronisation über {dienst}: {'an' if ntp else 'aus'}; Zeitserver: {' '.join(server) or 'Standard'}\n")
        if simuliert:
            for titel, args in schritte:
                zeile(f"(Probelauf) {' '.join(args)}\n")
            zeile(f"(Probelauf) Zeitserver eintragen, timedatectl set-ntp {'true' if ntp else 'false'}"
                  + (f", timedatectl set-time '{zeit}'" if zeit else "") + "\n")
            return 0, "Probelauf: Uhrzeit nicht geändert."
        for titel, args in schritte:
            if self.schritt(titel, args, zeile, zeitlimit=60) != 0:
                return 1, "Die Zeitzone ließ sich nicht setzen – nichts weiter geändert."
        if dienst == "chrony":
            pfad = os.path.join(self.chrony, "sources.d", "epm.sources")
            if server:
                with open(pfad, "w", encoding="utf-8") as f:
                    f.write("".join(f"server {s} iburst\n" for s in server))
            elif os.path.exists(pfad):
                os.unlink(pfad)
            konf = os.path.join(self.chrony, "chrony.conf")
            try:
                with open(konf, encoding="utf-8") as f:
                    text = f.read()
                # eigene Zeitserver: öffentliche Pools aus; ohne eigene wieder an (wie rollout/01-basis.sh)
                neu = re.sub(r"^(pool .*)$", r"# \1", text, flags=re.M) if server else \
                    re.sub(r"^# (pool .*)$", r"\1", text, flags=re.M)
                if neu != text:
                    with open(konf, "w", encoding="utf-8") as f:
                        f.write(neu)
            except OSError:
                pass
            einheit = "chrony"
        else:
            pfad = os.path.join(self.timesyncd, "epm.conf")
            if server:
                os.makedirs(self.timesyncd, mode=0o755, exist_ok=True)
                with open(pfad, "w", encoding="utf-8") as f:
                    f.write(f"[Time]\nNTP={' '.join(server)}\nFallbackNTP=\n")
            elif os.path.exists(pfad):
                os.unlink(pfad)
            einheit = "systemd-timesyncd"
        self.schritt("Zeitsynchronisation", ["timedatectl", "set-ntp", "true" if ntp else "false"], zeile, zeitlimit=60)
        if ntp:
            self.schritt("Zeitserver", ["systemctl", "restart", einheit], zeile, zeitlimit=60)
        if zeit:
            if self.schritt("Uhrzeit", ["timedatectl", "set-time", zeit], zeile, zeitlimit=60) != 0:
                return 1, "Die Uhrzeit ließ sich nicht setzen – Ausgabe prüfen."
        return 0, ("Zeitsynchronisation an" + (f" (Zeitserver {', '.join(server)})" if server else "") if ntp
                   else "Zeitsynchronisation aus" + (f", Uhrzeit auf {zeit} gesetzt" if zeit else "")) + \
            (f"; Zeitzone {zone}" if zone else "") + "."

    def ergebnisse_aufraeumen(self):
        try:
            dateien = sorted((os.path.join(self.ergebnisse, d) for d in os.listdir(self.ergebnisse)
                              if d.endswith(".json")), key=lambda p: os.stat(p).st_mtime)
        except OSError:
            return
        for p in dateien[:-ERGEBNISSE_BEHALTEN]:
            try:
                os.unlink(p)
            except OSError:
                pass


def teile_host(url):
    return urlsplit(url).hostname or url


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("befehl", choices=["status", "auftraege", "uebertragen", "schleife"])
    p.add_argument("--basis")
    p.add_argument("--projekt")
    p.add_argument("--konf")
    p.add_argument("--backup-skript")
    p.add_argument("--trocken", action="store_true")
    p.add_argument("--sicherung-echt", action="store_true")
    a = p.parse_args(argv)
    basis = a.basis or lese_konf().get("EPM_BASE") or "/srv/epm"
    trocken = a.trocken or os.environ.get("EPM_SYSTEM_TROCKEN") == "1"
    agent = Agent(basis, projekt=a.projekt, trocken=trocken, konf=a.konf, backup_skript=a.backup_skript,
                  sicherung_echt=a.sicherung_echt)
    if a.befehl == "status":
        agent.status_schreiben()
    elif a.befehl == "auftraege":
        agent.auftraege_ausfuehren()
    elif a.befehl == "uebertragen":
        rc, text = agent.uebertragen(lambda t: sys.stdout.write(t))
        print(text)
        return rc
    else:
        letzte = 0.0
        while True:
            if time.time() - letzte >= 60:
                letzte = time.time()
                try:
                    agent.status_schreiben()
                except Exception as e:  # noqa: BLE001
                    print(f"Status: {e}", file=sys.stderr)
            try:
                agent.auftraege_ausfuehren()
            except Exception as e:  # noqa: BLE001
                print(f"Aufträge: {e}", file=sys.stderr)
            time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
