"""Zeitfenster und Ressourcenschutz des KI-Dienstes (Auftrag 2 und 3).

- **Nacht** (Standard 21:00–07:00, Europe/Berlin, Administration › KI): mehrere Aufträge parallel.
- **Tag**: minimale Hintergrundlast – nur ausdrücklich angeforderte Dokumente, einer nach dem anderen (oder so viele
  wie unter „tagsüber“ eingestellt).
- **Pause**: während der Sicherung, wenn freier Speicher, CPU oder Systemlast die Grenzen überschreiten, oder
  tagsüber, solange Scans der Mitarbeiter warten (die haben Vorrang).
- **Sparsam**: knapp unter den Grenzen – nur ein Auftrag, kleinere Bilder, keine zweite Lesung durch das Modell.
- **Aus**: Hauptschalter aus oder Server zu klein (unter ``KI_MIN_RAM_GB`` bzw. ``KI_MIN_KERNE``; der heutige VPS mit
  4 GB bleibt so unberührt).

Gemessen wird live im Container (``/proc`` zeigt die Werte des Servers) und ergänzend aus dem Status des
Systemagenten (``system/status/system.json``). Hysterese: Nach einer Pause wegen Last geht es erst weiter, wenn die
Werte deutlich unter den Grenzen liegen – kein ständiges Hin und Her.
"""
import datetime as dt
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings

SICHERUNG_MARKE = "backup-laeuft"
SICHERUNG_MAX_S = 6 * 3600  # ältere Marke: die Sicherung ist abgebrochen, ohne aufzuräumen


@dataclass
class Last:
    cpu_prozent: float | None = None
    ram_frei_mb: int | None = None
    ram_gesamt_mb: int | None = None
    last1: float | None = None
    kerne: int = 1
    sicherung_laeuft: bool = False
    quelle: str = "proc"

    def als_dict(self) -> dict:
        return {"cpu_prozent": self.cpu_prozent, "ram_frei_mb": self.ram_frei_mb, "ram_gesamt_mb": self.ram_gesamt_mb,
                "last1": self.last1, "kerne": self.kerne, "sicherung_laeuft": self.sicherung_laeuft,
                "quelle": self.quelle}


@dataclass
class Entscheidung:
    modus: str                 # nacht | tag | pause | aus
    parallel: int              # wie viele Aufträge gleichzeitig laufen dürfen
    nur_angefordert: bool      # tagsüber: nur ausdrücklich angeforderte
    sparsam: bool = False
    grund: str = ""
    last: dict = field(default_factory=dict)
    wegen_last: bool = False   # Pause wegen CPU/Speicher/Systemlast – laufende Aufträge dürfen zu Ende laufen

    def als_dict(self) -> dict:
        return {"modus": self.modus, "parallel": self.parallel, "nur_angefordert": self.nur_angefordert,
                "sparsam": self.sparsam, "grund": self.grund, "last": self.last}


def im_fenster(jetzt: dt.datetime, beginn: dt.time, ende: dt.time, zeitzone: str = "Europe/Berlin") -> bool:
    """Liegt ``jetzt`` im Zeitfenster? Fenster über Mitternacht (21–07) wie innerhalb eines Tages (01–05);
    Sommer-/Winterzeit über die Zeitzone. Beginn = Ende heißt: rund um die Uhr."""
    ortszeit = jetzt.astimezone(ZoneInfo(zeitzone)).time()
    if beginn == ende:
        return True
    if beginn < ende:
        return beginn <= ortszeit < ende
    return ortszeit >= beginn or ortszeit < ende


def ist_wochenende(jetzt: dt.datetime, zeitzone: str = "Europe/Berlin") -> bool:
    """Sa 00:00 bis Mo 07:00 (Training am Wochenende, Entscheidung 14.10.2026)."""
    t = jetzt.astimezone(ZoneInfo(zeitzone))
    return t.weekday() >= 5 or (t.weekday() == 0 and t.hour < 7)


def _meminfo() -> dict:
    werte = {}
    try:
        for zeile in Path("/proc/meminfo").read_text().splitlines():
            name, _, rest = zeile.partition(":")
            werte[name] = int(rest.strip().split()[0]) // 1024  # kB → MB
    except (OSError, ValueError, IndexError):
        pass
    return werte


def _cpu_zaehler() -> tuple[int, int] | None:
    try:
        teile = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        zahlen = [int(x) for x in teile]
    except (OSError, ValueError, IndexError):
        return None
    leer = zahlen[3] + (zahlen[4] if len(zahlen) > 4 else 0)
    return sum(zahlen), leer


class Messung:
    """Misst die Auslastung; die CPU-Last ergibt sich aus der Differenz zweier Aufrufe."""

    def __init__(self):
        self._vorher = _cpu_zaehler()

    def messen(self) -> Last:
        last = Last(kerne=os.cpu_count() or 1)
        mem = _meminfo()
        if "MemAvailable" in mem:
            last.ram_frei_mb = mem["MemAvailable"]
            last.ram_gesamt_mb = mem.get("MemTotal")
        try:
            last.last1 = round(os.getloadavg()[0], 2)
        except OSError:
            pass
        jetzt = _cpu_zaehler()
        if jetzt and self._vorher and jetzt[0] > self._vorher[0]:
            gesamt, leer = jetzt[0] - self._vorher[0], jetzt[1] - self._vorher[1]
            last.cpu_prozent = round(100.0 * (1 - leer / gesamt), 1)
        self._vorher = jetzt
        status = settings.EPM_SYSTEM / "status"
        # Systemagent: frischer Wert vom Server selbst (z. B. wenn /proc im Container eingeschränkt ist)
        try:
            agent = json.loads((status / "system.json").read_text())
            if last.cpu_prozent is None and isinstance(agent.get("cpu"), dict):
                last.cpu_prozent = agent["cpu"].get("prozent")
                last.quelle = "systemagent"
        except (OSError, ValueError):
            pass
        try:
            last.sicherung_laeuft = time.time() - (status / SICHERUNG_MARKE).stat().st_mtime < SICHERUNG_MAX_S
        except OSError:
            last.sicherung_laeuft = False
        return last


def hardware_ausreichend(last: Last) -> tuple[bool, str]:
    """Mindestausstattung für das Vision-Modell (Plan, Entscheidung 14.10.2026: 4–8 Kerne, 16–32 GB)."""
    if os.environ.get("KI_HARDWARE_PRUEFEN", "1") == "0":
        return True, ""
    min_gb = float(os.environ.get("KI_MIN_RAM_GB", "12"))
    min_kerne = int(os.environ.get("KI_MIN_KERNE", "4"))
    if last.ram_gesamt_mb is not None and last.ram_gesamt_mb < min_gb * 1024 * 0.95:
        return False, f"Server zu klein für das KI-Modell: {last.ram_gesamt_mb / 1024:.1f} GB RAM, nötig {min_gb:g} GB"
    if last.kerne < min_kerne:
        return False, f"Server zu klein für das KI-Modell: {last.kerne} Kerne, nötig {min_kerne}"
    return True, ""


class Steuerung:
    """Entscheidet vor jedem neuen Auftrag, ob und wie viel gearbeitet werden darf (mit Hysterese)."""

    ERHOLT_CPU = 15       # so viele Prozentpunkte unter der Grenze geht es nach einer Pause weiter
    ERHOLT_RAM_MB = 512   # so viel mehr freier Speicher als die Grenze

    def __init__(self):
        self.pausiert_wegen_last = False

    def entscheiden(self, einst, last: Last, jetzt: dt.datetime, *, scans_warten: bool = False) -> Entscheidung:
        info = last.als_dict()
        if not einst.aktiv:
            return Entscheidung("aus", 0, True, grund="KI ist ausgeschaltet (Administration › KI).", last=info)
        ok, grund = hardware_ausreichend(last)
        if not ok:
            return Entscheidung("aus", 0, True, grund=grund, last=info)
        if einst.pause_bei_sicherung and last.sicherung_laeuft:
            return Entscheidung("pause", 0, True, grund="Die Sicherung läuft.", last=info)

        zu_hoch, knapp, gruende = self._last_pruefen(einst, last)
        if zu_hoch:
            self.pausiert_wegen_last = True
            return Entscheidung("pause", 0, True, grund="; ".join(gruende), last=info, wegen_last=True)
        nacht = im_fenster(jetzt, einst.nacht_beginn, einst.nacht_ende, einst.zeitzone)
        if not nacht and scans_warten:
            return Entscheidung("pause", 0, True, grund="Scans der Mitarbeiter haben Vorrang.", last=info)

        obergrenze = einst.worker_max()
        if nacht:
            parallel = max(1, min(einst.worker_nacht, obergrenze))
            if scans_warten:
                parallel = max(1, parallel - 1)
            e = Entscheidung("nacht", parallel, False, last=info)
        else:
            parallel = min(einst.worker_tag, obergrenze) if einst.worker_tag else 1
            e = Entscheidung("tag", parallel, einst.worker_tag == 0, last=info)
        if knapp:
            e.parallel, e.sparsam = 1, True
            e.grund = "Auslastung knapp: " + "; ".join(gruende)
        return e

    def _last_pruefen(self, einst, last: Last) -> tuple[bool, bool, list[str]]:
        """→ (zu hoch, knapp, Gründe). Nach einer Pause gelten bis zur Erholung strengere Grenzen."""
        gruende, zu_hoch, knapp = [], False, False
        cpu_grenze = einst.max_cpu_prozent - (self.ERHOLT_CPU if self.pausiert_wegen_last else 0)
        ram_grenze = einst.min_ram_frei_mb + (self.ERHOLT_RAM_MB if self.pausiert_wegen_last else 0)
        last_grenze = einst.max_last_je_kern * (0.7 if self.pausiert_wegen_last else 1)
        if last.ram_frei_mb is not None:
            if last.ram_frei_mb < ram_grenze:
                zu_hoch = True
                gruende.append(f"freier Speicher {last.ram_frei_mb} MB (Grenze {ram_grenze} MB)")
            elif last.ram_frei_mb < ram_grenze * 1.5:
                knapp = True
                gruende.append(f"freier Speicher {last.ram_frei_mb} MB")
        if last.cpu_prozent is not None:
            if last.cpu_prozent > cpu_grenze:
                zu_hoch = True
                gruende.append(f"CPU {last.cpu_prozent:.0f} % (Grenze {cpu_grenze} %)")
            elif last.cpu_prozent > cpu_grenze * 0.8:
                knapp = True
                gruende.append(f"CPU {last.cpu_prozent:.0f} %")
        if last.last1 is not None and last.kerne:
            je_kern = last.last1 / last.kerne
            if je_kern > last_grenze:
                zu_hoch = True
                gruende.append(f"Systemlast {je_kern:.2f} je Kern (Grenze {last_grenze:.2f})")
        if not zu_hoch:
            self.pausiert_wegen_last = False
        return zu_hoch, knapp and not zu_hoch, gruende
