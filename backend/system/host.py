"""
Verbindung zum Systemagenten auf dem Server (rollout/epm-systemagent.py).

Der Container hat keinen Zugriff auf den Server. Aufträge werden als JSON-Datei in ``EPM_SYSTEM/auftraege/`` abgelegt;
der Agent (root, systemd) führt nur seine fest eingetragenen Aktionen aus und schreibt Status und Ergebnisse nach
``EPM_SYSTEM/status/`` (im Container nur lesbar). Fehlt der Agent, misst das Backend, was es aus dem Container sieht.
"""
import json
import os
from datetime import datetime

from django.conf import settings
from django.utils import timezone

# Code -> Angaben. Dieselben Aktionen stehen im Agenten (AKTIONEN); andere führt er nicht aus.
# bestaetigung: "keine" | "einfach" (Rückfrage) | "2fa" (Admin-Kennwort und Code, Festlegung 01.10.2026)
# sichern: der Agent erstellt vorher eine Sicherung; warnen: angemeldete Benutzer bekommen vorher einen Hinweis
AKTIONEN = {
    "status_aktualisieren": {
        "name": "Status neu einlesen", "bestaetigung": "keine",
        "beschreibung": "Auslastung, Updates, Container und Sicherung jetzt messen (sonst jede Minute).",
    },
    "updates_suchen": {
        "name": "Nach Updates suchen", "bestaetigung": "keine",
        "beschreibung": "Paketlisten über den Proxy laden und ausstehende Ubuntu-Updates zählen.",
    },
    "updates_installieren": {
        "name": "Ubuntu-Updates installieren", "bestaetigung": "2fa", "sichern": True, "warnen": True,
        "beschreibung": "Vorher automatische Sicherung. Docker-Updates starten EPM kurz neu.",
        "hinweis": "Auf dem Server werden Updates installiert. EPM kann dabei kurz nicht erreichbar sein – "
                   "bitte Eingaben vorher speichern.",
    },
    "server_neustart": {
        "name": "Server neu starten", "bestaetigung": "2fa", "sichern": True, "warnen": True,
        "beschreibung": "Vorher automatische Sicherung. EPM ist einige Minuten nicht erreichbar.",
        "hinweis": "Der Server wird neu gestartet. EPM ist danach einige Minuten nicht erreichbar – "
                   "bitte Eingaben vorher speichern.",
    },
    "epm_neustart": {
        "name": "EPM neu starten", "bestaetigung": "2fa", "warnen": True,
        "beschreibung": "Datenbank, Backend und Webserver neu starten (z. B. nach Hängern). Etwa eine Minute.",
        "hinweis": "EPM wird neu gestartet und ist etwa eine Minute nicht erreichbar – bitte Eingaben vorher speichern.",
    },
    "sicherung": {
        "name": "Sicherung erstellen", "bestaetigung": "einfach", "recht": "backup_verwalten",
        "beschreibung": "Datenbank und Dokumente jetzt sichern (wie die nächtliche Sicherung).",
    },
    "docker_aufraeumen": {
        "name": "Docker aufräumen", "bestaetigung": "einfach",
        "beschreibung": "Nicht mehr benutzte Images und Build-Zwischenstände löschen; markierte Versionen für "
                        "„Zurückschalten“ bleiben.",
    },
    "pakete_aufraeumen": {
        "name": "Paketreste entfernen", "bestaetigung": "einfach",
        "beschreibung": "Nicht mehr benötigte Pakete (z. B. alte Kernel) und den Paketcache entfernen.",
    },
}

STATUS_VERALTET_S = 180   # der Agent misst jede Minute; älter heißt: Agent läuft nicht


def ordner_auftraege():
    return settings.EPM_SYSTEM / "auftraege"


def ordner_status():
    return settings.EPM_SYSTEM / "status"


def _lies(pfad):
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _zeit(text):
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def host_status():
    """Status vom Server (``system.json``) mit Alter; ``None``, wenn der Agent noch nie gemessen hat."""
    daten = _lies(ordner_status() / "system.json")
    if not isinstance(daten, dict):
        return None
    zeit = _zeit(daten.get("zeit"))
    alter = int((timezone.now() - zeit).total_seconds()) if zeit else None
    daten["alter_s"] = alter
    daten["aktuell"] = alter is not None and alter <= STATUS_VERALTET_S
    return daten


def verlauf():
    daten = _lies(ordner_status() / "verlauf.json")
    if not isinstance(daten, dict):
        return {"felder": ["zeit", "cpu", "ram", "last", "platte"], "punkte": []}
    return daten


def agent_erreichbar() -> bool:
    status = host_status()
    return bool(status and status.get("aktuell"))


def container_messung():
    """Was das Backend selbst sieht: Last und Arbeitsspeicher des Servers (/proc ist nicht getrennt), Platz im
    Dokumentenverzeichnis. Ersatz, solange der Systemagent keinen Status liefert."""
    ergebnis = {"kerne": os.cpu_count(), "last": None, "speicher": None, "laufzeit_s": None, "platten": []}
    try:
        ergebnis["last"] = [round(x, 2) for x in os.getloadavg()]
    except OSError:
        pass
    try:
        werte = {}
        with open("/proc/meminfo") as f:
            for zeile in f:
                name, rest = zeile.split(":", 1)
                werte[name] = int(rest.split()[0]) * 1024
        ergebnis["speicher"] = {"gesamt": werte.get("MemTotal"), "verfuegbar": werte.get("MemAvailable"),
                                "swap_gesamt": werte.get("SwapTotal"), "swap_frei": werte.get("SwapFree")}
    except (OSError, ValueError):
        pass
    try:
        with open("/proc/uptime") as f:
            ergebnis["laufzeit_s"] = int(float(f.read().split()[0]))
    except (OSError, ValueError):
        pass
    for pfad, bezeichnung in ((settings.EPM_DOKUMENTE, "EPM-Daten"),):
        try:
            s = os.statvfs(pfad)
            ergebnis["platten"].append({"pfad": str(pfad), "bezeichnung": bezeichnung,
                                        "gesamt": s.f_blocks * s.f_frsize, "frei": s.f_bavail * s.f_frsize})
        except OSError:
            pass
    return ergebnis


class AuftragNichtMoeglich(Exception):
    pass


def auftrag_ablegen(auftrag):
    """Auftragsdatei für den Agenten schreiben (atomar: erst .tmp, dann umbenennen – der Agent liest nur *.json)."""
    ordner = ordner_auftraege()
    if not ordner.is_dir():
        raise AuftragNichtMoeglich(
            "Das Auftragsverzeichnis fehlt. Bitte auf dem Server einmal „sudo epm-update“ bzw. rollout/04-projekt.sh "
            "ausführen (richtet den Systemagenten ein).")
    daten = {
        "id": auftrag.kennung.hex,
        "aktion": auftrag.aktion,
        "parameter": auftrag.parameter,
        "angefordert_von": auftrag.angefordert_von.get_username(),
        "angefordert_am": auftrag.angefordert_am.isoformat(),
    }
    tmp = ordner / f".{auftrag.kennung.hex}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False)
        os.replace(tmp, ordner / f"{auftrag.kennung.hex}.json")
    except OSError as e:
        raise AuftragNichtMoeglich(
            f"Der Auftrag konnte nicht abgelegt werden ({e.strerror}). Rechte des Auftragsverzeichnisses prüfen.") from e


def auftrag_zurueckziehen(auftrag) -> bool:
    """Nur solange der Agent die Datei noch nicht übernommen hat."""
    try:
        os.unlink(ordner_auftraege() / f"{auftrag.kennung.hex}.json")
        return True
    except OSError:
        return False


def abgleichen(auftraege):
    """Ergebnisse des Agenten in die offenen Aufträge übernehmen. Liefert die abgeschlossenen Aufträge."""
    from .models import Systemauftrag

    fertig = []
    for a in auftraege:
        if a.ziel != Systemauftrag.Ziel.SERVER or not a.offen:
            continue
        daten = _lies(ordner_status() / "auftraege" / f"{a.kennung.hex}.json")
        if not isinstance(daten, dict) or daten.get("status") not in ("laeuft", "erledigt", "fehler"):
            continue
        felder = {
            "status": daten["status"],
            "begonnen_am": _zeit(daten.get("begonnen_am")) or a.begonnen_am,
            "beendet_am": _zeit(daten.get("beendet_am")),
            "ergebnis": str(daten.get("ergebnis") or "")[:500],
            "ausgabe": str(daten.get("ausgabe") or "")[-20000:],
            "rueckgabe": daten.get("rueckgabe") if isinstance(daten.get("rueckgabe"), int) else None,
            "probelauf": bool(daten.get("trocken")),
        }
        geaendert = [k for k, v in felder.items() if getattr(a, k) != v]
        if not geaendert:
            continue
        for k, v in felder.items():
            setattr(a, k, v)
        a.save(update_fields=geaendert)
        if a.status in (Systemauftrag.Status.ERLEDIGT, Systemauftrag.Status.FEHLER):
            fertig.append(a)
    return fertig
