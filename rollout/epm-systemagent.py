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
verwendet (Minuten, Benutzername, Stempel einer Sicherung, Sicherungs-Passwort, Übertragungsziel). Nichts davon wird
als Befehl oder über eine Shell ausgeführt; Passwörter gehen nur in Dateien (0600, root) bzw. über die Standardeingabe
an rclone und stehen nie in Ergebnissen oder Ausgaben. Dateien werden ohne Folgen symbolischer Links gelesen und
nach dem Lesen sofort gelöscht.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

VERSION = 2
KONF = "/etc/epm/epm.conf"
BACKUP_SKRIPT = "/usr/local/sbin/epm-backup"
KONF_SICHERUNG = "/etc/epm/sicherung"
VERLAUF_PUNKTE = 1440            # 24 Stunden bei einer Messung je Minute
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
ARTEN = ("nachts", "von_hand", "vor_update", "vor_aenderung", "vor_wiederherstellung")
APP_UID, APP_GID = 10001, 101

# Aktion -> (Bezeichnung, vorher sichern). Dieselbe Liste steht in backend/system/host.py.
AKTIONEN = {
    "status_aktualisieren": ("Status neu einlesen", False),
    "updates_suchen": ("Nach Updates suchen", False),
    "updates_installieren": ("Ubuntu-Updates installieren", True),
    "server_neustart": ("Server neu starten", True),
    "epm_neustart": ("EPM neu starten", False),
    "sicherung": ("Sicherung erstellen", False),
    "docker_aufraeumen": ("Docker aufräumen", False),
    "pakete_aufraeumen": ("Paketreste entfernen", False),
    # Administration › Backup
    "sicherung_passwort": ("Sicherungs-Passwort festlegen", False),
    "sicherung_ziel": ("Übertragungsziel festlegen", False),
    "sicherung_ziel_entfernen": ("Übertragungsziel entfernen", False),
    "sicherung_ziel_testen": ("Verbindung zum Übertragungsziel testen", False),
    "sicherung_uebertragen": ("Sicherungen jetzt übertragen", False),
    "wiederherstellen": ("Sicherung wiederherstellen", True),
}
# Aktionen, die Sicherungen schreiben, übertragen oder zurückspielen: mit --sicherung-echt auch im Probelauf echt
SICHERUNG_AKTIONEN = {"sicherung", "sicherung_passwort", "sicherung_ziel", "sicherung_ziel_entfernen",
                      "sicherung_ziel_testen", "sicherung_uebertragen", "wiederherstellen"}
# Art der Sicherung, die eine Aktion vorher erstellt
VORHER_ART = {"updates_installieren": "vor_update", "server_neustart": "vor_aenderung",
              "wiederherstellen": "vor_wiederherstellung"}

APT_ENV = {"DEBIAN_FRONTEND": "noninteractive", "NEEDRESTART_MODE": "a", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}


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
    def schreibe(self, pfad, daten, modus=0o644):
        """Atomar schreiben (für den Container lesbar: 0644; Geheimes 0600)."""
        tmp = f"{pfad}.tmp{os.getpid()}"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, modus)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
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
            "trocken": self.trocken,
        }
        self.schreibe(os.path.join(self.status, "system.json"), status)
        self.verlauf_ergaenzen(status)
        try:
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
        self.schreibe(pfad, {"felder": ["zeit", "cpu", "ram", "last", "platte"], "punkte": punkte[-VERLAUF_PUNKTE:]})

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
        return None, {"url": url.rstrip("/"), "benutzer": benutzer, "ordner": ordner, "von": von, "bis": bis,
                      "kennwort": kennwort or None}

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
                "hersteller": hersteller, "gesetzt_am": jetzt_iso(), "gesetzt_von": von or ""}
        self.schreibe(os.path.join(self.konf, "ziel.json"), ziel, modus=0o600)
        zeile(f"Ziel gespeichert: {z['url']} · Ordner „{z['ordner'] or '/'}“ · Zeitfenster {z['von']}–{z['bis']}\n")
        if alt and self.ziel_kennung(alt) != self.ziel_kennung(ziel):
            zeile("Neues Ziel: Die vorhandenen verschlüsselten Sicherungen werden im nächsten Zeitfenster dorthin übertragen.\n")
        self.sicherung_status_schreiben()
        return 0, f"Übertragungsziel festgelegt ({teile_host(z['url'])}, Zeitfenster {z['von']}–{z['bis']})."

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
        """Verschlüsselte Sicherungen (und ihre Prüfsummen und Angaben) zum Ziel kopieren – nie löschen, nie
        Unverschlüsseltes. Automatisch nur im Zeitfenster und höchstens bis zu seinem Ende."""
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
                stand.update({"laeuft_seit": None, "letzter_fehler": "", "letzter_erfolg": jetzt_iso()})
                self.schreibe(self.uebertragung_pfad(), stand, modus=0o600)
                self.sicherung_status_schreiben()
                return 0, "Alle verschlüsselten Sicherungen sind schon übertragen."
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
                stand.update({"letzter_erfolg": jetzt_iso(), "letzter_fehler": ""})
                ergebnis = f"{len(offen)} Sicherung(en) übertragen und geprüft."
            else:
                stand["letzter_fehler"] = ("Übertragung fehlgeschlagen oder Zeitfenster vorbei – Ausgabe prüfen "
                                           "(Adresse, Zugang, Proxy-Freigabe).")
                ergebnis = stand["letzter_fehler"]
            self.schreibe(self.uebertragung_pfad(), stand, modus=0o600)
            self.sicherung_status_schreiben()
            return (0 if rc == 0 else 1), ergebnis

    # ------------------------------------------------------------ Sicherungen: Status für das Backend
    def sicherung_status_schreiben(self):
        stand = self.passwort_stand()
        versionen = []
        pruefwerte = []
        liste = self.sicherungen()
        for v in stand["versionen"]:
            nr = v.get("nr")
            versionen.append({"nr": nr, "gesetzt_am": v.get("gesetzt_am"), "gesetzt_von": v.get("gesetzt_von", ""),
                              "entfernt_am": v.get("entfernt_am"),
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
                                                "gesetzt_von")} | {"eingerichtet": True}) if ziel else {"eingerichtet": False},
            "uebertragung": {
                "letzter_versuch": ue.get("letzter_versuch"),
                "letzter_erfolg": ue.get("letzter_erfolg"),
                "letzter_fehler": ue.get("letzter_fehler") or "",
                "laeuft": bool(ue.get("laeuft_seit")) and self.uebertragung_laeuft(),
                "offen": len(offen),
                "im_zeitfenster": im_zeitfenster(ziel["von"], ziel["bis"]) if ziel else False,
                "naechstes_fenster": naechstes,
                "rclone": bool(shutil.which("rclone")),
            },
            "sicherungen": liste,
            "speicher": {"platz": platz, "sicherungen": sum(x["groesse"] for x in liste)},
            "aufbewahrung_tage": int(lese_konf().get("EPM_BACKUP_TAGE") or 30),
            "naechste_sicherung": naechste_sicherung,
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
        self.schritt("Anhalten", self.compose("stop", "backend", "web"), zeile, cwd=self.basis, zeitlimit=300)
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
            self.schritt("Starten", self.compose("up", "-d", "backend", "web"), zeile, cwd=self.basis, zeitlimit=600)
            if not self.backend_gesund(zeile):
                raise RuntimeError("Das Backend startet mit der wiederhergestellten Sicherung nicht.")
        except Exception as e:  # noqa: BLE001 – zurücktauschen, dann melden
            zeile(f"\nFEHLER: {e}\nVorigen Stand zurückstellen …\n")
            self.schritt("Anhalten", self.compose("stop", "backend", "web"), zeile, cwd=self.basis, zeitlimit=300)
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
            self.schritt("Starten", self.compose("up", "-d", "backend", "web"), zeile, cwd=self.basis, zeitlimit=600)
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

    def schritt(self, titel, args, zeile, env=None, cwd=None, zeitlimit=3600):
        zeile(f"\n$ {' '.join(args)}\n")
        rc, aus = self.befehl(args, env=env, cwd=cwd, zeitlimit=zeitlimit)
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
        env = {"EPM_BASIS": self.basis, "EPM_SICHERUNG_KONF": self.konf}
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

        if aktion == "wiederherstellen":
            if t:
                zeile(f"\n(Probelauf) Sicherung {parameter.get('stempel')} würde zurückgespielt.\n")
                return 0, "Probelauf: nichts zurückgespielt."
            return self.wiederherstellen(parameter.get("stempel"), von, auftrag_id, zeile, vorher=vorher)

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
