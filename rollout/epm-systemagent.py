#!/usr/bin/env python3
"""
EPM – Systemagent auf dem Server (Administration › System).

Das Backend läuft im Container ohne Zugriff auf den Server. Es legt Aufträge als JSON-Dateien in
``<EPM_BASE>/system/auftraege/`` ab; dieser Agent (root, systemd) führt nur die unten fest eingetragenen
Aktionen aus und schreibt Status und Ergebnisse nach ``<EPM_BASE>/system/status/`` (für den Container nur lesbar).

    epm-systemagent status      Auslastung, Updates, Container, Sicherung messen (Timer, jede Minute)
    epm-systemagent auftraege   wartende Aufträge ausführen (systemd-Pfad-Einheit, sobald eine Datei da ist)
    epm-systemagent schleife    beides fortlaufend (Browsertests in CI, ohne systemd)

Optionen: --basis DIR (statt EPM_BASE aus /etc/epm/epm.conf), --projekt NAME (Compose-Projekt),
          --trocken (nichts verändern: Updates, Neustart, Sicherung und Aufräumen nur simulieren).

Sicherheit: Aus einer Auftragsdatei werden nur „aktion“ (feste Liste) und „minuten“ (0–60) verwendet; nichts aus
der Datei wird als Befehl ausgeführt. Dateien werden ohne Folgen symbolischer Links gelesen.
"""
import argparse
import fcntl
import json
import os
import re
import socket
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone

VERSION = 1
KONF = "/etc/epm/epm.conf"
BACKUP_SKRIPT = "/usr/local/sbin/epm-backup"
VERLAUF_PUNKTE = 1440            # 24 Stunden bei einer Messung je Minute
AUSGABE_MAX = 20000              # Zeichen Ausgabe je Auftrag
ERGEBNISSE_BEHALTEN = 200
ID_MUSTER = re.compile(r"^[0-9a-f]{32}$")

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
}

APT_ENV = {"DEBIAN_FRONTEND": "noninteractive", "NEEDRESTART_MODE": "a", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}


def jetzt_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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


class Agent:
    def __init__(self, basis, projekt=None, trocken=False):
        self.basis = basis
        self.projekt = projekt
        self.trocken = trocken
        self.auftraege = os.path.join(basis, "system", "auftraege")
        self.status = os.path.join(basis, "system", "status")
        self.ergebnisse = os.path.join(self.status, "auftraege")
        for d in (self.status, self.ergebnisse):
            os.makedirs(d, mode=0o755, exist_ok=True)

    # ------------------------------------------------------------ Hilfen
    def schreibe(self, pfad, daten):
        """Atomar schreiben (für den Container lesbar: 0644)."""
        tmp = f"{pfad}.tmp{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False, indent=1, default=str)
        os.chmod(tmp, 0o644)
        os.replace(tmp, pfad)

    def lies(self, pfad, standard=None):
        try:
            with open(pfad, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return standard

    def befehl(self, args, env=None, cwd=None, zeitlimit=3600):
        """Befehl ausführen, Ausgabe (stdout+stderr) und Rückgabe liefern. Nie über eine Shell."""
        umgebung = dict(os.environ)
        umgebung.update(env or {})
        try:
            p = subprocess.run(args, cwd=cwd, env=umgebung, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, errors="replace", timeout=zeitlimit, check=False)
            return p.returncode, p.stdout
        except FileNotFoundError:
            return 127, f"Programm nicht gefunden: {args[0]}\n"
        except subprocess.TimeoutExpired as e:
            return 124, (e.stdout or "") + f"\nAbgebrochen nach {zeitlimit} s\n"

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
        ordner = os.path.join(self.basis, "backup")
        try:
            dateien = [os.path.join(ordner, d) for d in os.listdir(ordner)]
        except OSError:
            return {"verfuegbar": False}
        dumps = sorted((p for p in dateien if p.endswith(".dump")), key=lambda p: os.stat(p).st_mtime)
        gesamt = sum(os.stat(p).st_size for p in dateien if os.path.isfile(p))
        if not dumps:
            return {"verfuegbar": True, "anzahl": 0, "gesamt": gesamt, "letzte_am": None}
        letzte = dumps[-1]
        stempel = os.path.basename(letzte)[len("epm-db_"):-len(".dump")]
        zugehoerig = [p for p in dateien if stempel in os.path.basename(p)]
        return {
            "verfuegbar": True,
            "anzahl": len(dumps),
            "gesamt": gesamt,
            "letzte_am": datetime.fromtimestamp(os.stat(letzte).st_mtime, timezone.utc).astimezone().isoformat(
                timespec="seconds"),
            "letzte_groesse": sum(os.stat(p).st_size for p in zugehoerig),
        }

    def dienste(self):
        ergebnis = {}
        for name in ("docker", "epm-backup.timer", "epm-systemstatus.timer", "epm-systemagent.path"):
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
                "sicherungen": self.groesse(os.path.join(self.basis, "backup")),
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
        try:
            minuten = max(0, min(60, int((daten.get("parameter") or {}).get("minuten") or 0)))
        except (TypeError, ValueError):
            minuten = 0
        protokoll = []

        def zeile(text):
            protokoll.append(text)
            self.ergebnis(auftrag_id, ausgabe="".join(protokoll)[-AUSGABE_MAX:])

        start = jetzt_iso()
        self.ergebnis(auftrag_id, status="laeuft", aktion=aktion, begonnen_am=start, ausgabe="", ergebnis="",
                      trocken=self.trocken)
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
            rc, kurz = self.ausfuehren(aktion, zeile, auftrag_id)
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

    def sichern(self, zeile):
        if self.trocken:
            zeile("\n(Probelauf) Sicherung würde jetzt mit epm-backup erstellt.\n")
            return 0
        if not os.path.exists(BACKUP_SKRIPT):
            zeile(f"\n{BACKUP_SKRIPT} fehlt – Sicherung nicht möglich.\n")
            return 1
        return self.schritt("Sicherung", [BACKUP_SKRIPT], zeile, zeitlimit=3 * 3600)

    def ausfuehren(self, aktion, zeile, auftrag_id):
        t = self.trocken
        name, vorher_sichern = AKTIONEN[aktion]
        if t:
            zeile("Probelauf: Es wird nichts verändert.\n")
        if vorher_sichern:
            zeile("Zuerst wird eine Sicherung erstellt.\n")
            if self.sichern(zeile) != 0:
                return 1, "Abgebrochen: Die Sicherung vorher ist fehlgeschlagen. Es wurde nichts verändert."

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
            rc = self.sichern(zeile)
            return rc, ("Sicherung erstellt." if not t else "Probelauf: Sicherung nicht erstellt.") if rc == 0 else \
                "Sicherung fehlgeschlagen."

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


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("befehl", choices=["status", "auftraege", "schleife"])
    p.add_argument("--basis")
    p.add_argument("--projekt")
    p.add_argument("--trocken", action="store_true")
    a = p.parse_args(argv)
    basis = a.basis or lese_konf().get("EPM_BASE") or "/srv/epm"
    trocken = a.trocken or os.environ.get("EPM_SYSTEM_TROCKEN") == "1"
    agent = Agent(basis, projekt=a.projekt, trocken=trocken)
    if a.befehl == "status":
        agent.status_schreiben()
    elif a.befehl == "auftraege":
        agent.auftraege_ausfuehren()
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
