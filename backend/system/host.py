"""
Verbindung zum Systemagenten auf dem Server (rollout/epm-systemagent.py).

Der Container hat keinen Zugriff auf den Server. Aufträge werden als JSON-Datei in ``EPM_SYSTEM/auftraege/`` abgelegt;
der Agent (root, systemd) führt nur seine fest eingetragenen Aktionen aus und schreibt Status und Ergebnisse nach
``EPM_SYSTEM/status/`` (im Container nur lesbar). Fehlt der Agent, misst das Backend, was es aus dem Container sieht.
"""
import json
import os
import re
from datetime import datetime

from django.conf import settings
from django.utils import timezone

# Code -> Angaben. Dieselben Aktionen stehen im Agenten (AKTIONEN); andere führt er nicht aus.
# bestaetigung: "keine" | "einfach" (Rückfrage) | "2fa" (Admin-Passwort und – wenn ein zweiter Faktor eingerichtet
# ist – der Code; Festlegungen 01. und 02.10.2026)
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
    # Wunsch 07.10.2026 (F123): Aktualisieren aus der Oberfläche, damit spätere Stände ohne Terminal eingespielt
    # werden können. Das Skript sichert selbst, bevor es umstellt – deshalb hier kein zusätzliches „sichern“.
    "epm_update": {
        "name": "EPM aktualisieren", "bestaetigung": "2fa", "warnen": True,
        "beschreibung": "Neuen Stand holen, Images bauen, sichern und umstellen (sudo epm-update), ohne Testlauf – "
                        "getestet wird vor jedem Push. Dauert je nach Server 10 bis 30 Minuten; beim Umstellen ist "
                        "EPM kurz nicht erreichbar. Geht etwas schief, läuft die bisherige Version weiter.",
        "hinweis": "EPM wird auf einen neuen Stand gebracht. Beim Umstellen ist es kurz nicht erreichbar – "
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
    # Festlegung 03.10.2026 (U27): vor dem Go-live alles aus der Testphase entfernen (system/leeren.py). Nur über
    # /api/system/leeren/ (Bestätigungscode abtippen, Rückfrage, Auswahl der Konten), vorher immer eine Sicherung.
    "datenbank_leeren": {
        "name": "Datenbank leeren", "bestaetigung": "2fa", "sichern": True, "warnen": True, "intern": True,
        "beschreibung": "Entfernt alle Akten, Dokumente, Versorger, Ärzte, Benutzer (außer den ausgewählten) und das "
                        "Audit-Log. Präparate, Vorlagen und Einstellungen bleiben. Vorher automatische Sicherung.",
        "hinweis": "EPM wird geleert (Ende der Testphase). Alle Anmeldungen werden beendet – bitte nichts mehr eingeben.",
    },
    "pakete_aufraeumen": {
        "name": "Paketreste entfernen", "bestaetigung": "einfach",
        "beschreibung": "Nicht mehr benötigte Pakete (z. B. alte Kernel) und den Paketcache entfernen.",
    },
    # Administration › Backup (intern: nicht unter System › Tätigkeiten, nur über /api/backup/…)
    "sicherung_passwort": {
        "name": "Sicherungs-Passwort festlegen", "bestaetigung": "2fa", "recht": "backup_verwalten", "intern": True,
        "beschreibung": "Neues Passwort für die Verschlüsselung der Sicherungen; ältere bleiben mit ihrem Passwort lesbar.",
    },
    "sicherung_ziel": {
        "name": "Übertragungsziel festlegen", "bestaetigung": "2fa", "recht": "backup_verwalten", "intern": True,
        "beschreibung": "WebDAV-Ordner (Nextcloud) und Zeitfenster für die Übertragung der Sicherungen.",
    },
    "sicherung_ziel_entfernen": {
        "name": "Übertragungsziel entfernen", "bestaetigung": "2fa", "recht": "backup_verwalten", "intern": True,
        "beschreibung": "Sicherungen bleiben danach nur auf dem Server.",
    },
    "sicherung_ziel_testen": {
        "name": "Verbindung zum Übertragungsziel testen", "bestaetigung": "keine", "recht": "backup_verwalten",
        "intern": True, "beschreibung": "Anmeldung am WebDAV-Ordner prüfen und den Ordner anlegen, falls er fehlt.",
    },
    "sicherung_uebertragen": {
        "name": "Sicherungen jetzt übertragen", "bestaetigung": "einfach", "recht": "backup_verwalten", "intern": True,
        "beschreibung": "Noch nicht übertragene, verschlüsselte Sicherungen jetzt zum Ziel kopieren (auch außerhalb des "
                        "Zeitfensters).",
    },
    "sicherung_aufbewahrung": {
        "name": "Aufbewahrung der Sicherungen festlegen", "bestaetigung": "2fa", "recht": "backup_verwalten",
        "intern": True,
        "beschreibung": "Wie lange Sicherungen auf dem Server bleiben: 7, 14 oder 30 Tage. Ältere entfernt die nächste "
                        "Sicherung.",
    },
    "sicherung_bereitstellen": {
        "name": "Sicherung zum Herunterladen bereitstellen", "bestaetigung": "2fa", "recht": "backup_verwalten",
        "intern": True,
        "beschreibung": "Legt die Sicherung als eine Datei für 2 Stunden zum Herunterladen bereit (verschlüsselte "
                        "bleiben verschlüsselt).",
    },
    "sicherung_einlesen": {
        "name": "Hochgeladene Sicherung einlesen", "bestaetigung": "einfach", "recht": "backup_verwalten",
        "intern": True,
        "beschreibung": "Prüft eine hochgeladene Sicherung (Inhalt, Prüfsummen, Passwort) und nimmt sie in die Liste auf. "
                        "Zurückgespielt wird erst mit „Wiederherstellen“.",
    },
    "wiederherstellen": {
        "name": "Sicherung wiederherstellen", "bestaetigung": "2fa", "recht": "backup_verwalten", "intern": True,
        "sichern": True, "warnen": True,
        "beschreibung": "Ersetzt Datenbank und Dokumente durch den Stand der Sicherung. Vorher automatische Sicherung des "
                        "jetzigen Stands; die Löschliste bleibt.",
        "hinweis": "EPM wird auf eine Sicherung zurückgesetzt und ist einige Minuten nicht erreichbar. Eingaben nach dem "
                   "Zeitpunkt der Sicherung gehen verloren; danach bitte neu anmelden.",
    },
    # ---- Systemverwaltung ohne SSH (Wunsch 10.10.2026, F179): was bisher nur per SSH ging. „intern“: nur über eigene
    # Endpunkte mit geprüften Angaben (Stempel, Version, Dienst, Upload, Protokoll), nicht unter „Tätigkeiten“.
    "sicherung_loeschen": {
        "name": "Sicherungen löschen", "bestaetigung": "2fa", "recht": "backup_verwalten", "intern": True,
        "beschreibung": "Ausgewählte Sicherungen endgültig vom Server löschen. Die jüngste Sicherung bleibt immer; im "
                        "Übertragungsziel gilt dessen eigene Aufbewahrung.",
    },
    "dienst_neustart": {
        "name": "Dienst neu starten", "bestaetigung": "2fa", "warnen": True, "intern": True,
        "beschreibung": "Einen einzelnen Container neu starten (backend, web, ocr oder db), z. B. wenn er hängt.",
        "hinweis": "Ein Teil von EPM wird neu gestartet und ist kurz nicht erreichbar – bitte Eingaben vorher speichern.",
    },
    "epm_zurueck": {
        "name": "EPM-Version zurückschalten", "bestaetigung": "2fa", "sichern": True, "warnen": True, "intern": True,
        "beschreibung": "Auf eine frühere, noch vorhandene Version umstellen (sudo epm-update --zurueck). Vorher "
                        "automatische Sicherung; Datenbank-Migrationen werden nicht zurückgedreht.",
        "hinweis": "EPM wird auf eine frühere Version umgestellt und ist kurz nicht erreichbar – bitte Eingaben vorher "
                   "speichern.",
    },
    "epm_paket": {
        "name": "Update-Paket einspielen", "bestaetigung": "2fa", "warnen": True, "intern": True,
        "beschreibung": "Ein hochgeladenes Update-Paket der Test-VM prüfen und einspielen (sudo epm-update --paket). "
                        "epm-update sichert vorher; geht etwas schief, läuft die bisherige Version weiter.",
        "hinweis": "EPM wird auf einen neuen Stand gebracht. Beim Umstellen ist es kurz nicht erreichbar – bitte "
                   "Eingaben vorher speichern.",
    },
    "epm_paket_erstellen": {
        "name": "Update-Paket erstellen", "bestaetigung": "einfach", "intern": True,
        "beschreibung": "Paket der laufenden, getesteten Version für einen Server ohne Internet (sudo epm-update "
                        "--paket-erstellen, nur Test-VM); es liegt danach 2 Stunden zum Herunterladen bereit.",
    },
    "zertifikat_erneuern": {
        "name": "Zertifikat erneuern", "bestaetigung": "2fa", "intern": True,
        "beschreibung": "Neues Serverzertifikat der eigenen CA ausstellen (sudo epm-zertifikat erneuern, 397 Tage); "
                        "Geräte, die der CA vertrauen, merken nichts davon.",
    },
    "zertifikat_importieren": {
        "name": "Zertifikat importieren", "bestaetigung": "2fa", "intern": True,
        "beschreibung": "Zertifikat einer anderen CA (z. B. der OPNsense) mit Schlüssel und CA-Zertifikat übernehmen "
                        "(sudo epm-zertifikat importieren).",
    },
    "ocr_modelle": {
        # Nachtrag 10.10.2026: wie die anderen Uploads, die Dateien auf den Server bringen, mit Passwort und 2FA
        "name": "OCR-Modelle einspielen", "bestaetigung": "2fa", "intern": True,
        "beschreibung": "Offline vorbereitete Modelle der zweiten Texterkennung prüfen und ablegen (sudo epm-ocr-modelle "
                        "einspielen); das nächste „EPM aktualisieren“ baut sie ins Image.",
    },
    "protokoll": {
        "name": "Protokoll abrufen", "bestaetigung": "keine", "intern": True, "mehrfach": True,
        "beschreibung": "Letzte Zeilen eines Protokolls (Container, Systemagent, Sicherung, Update) – nur lesend.",
    },
    # ---- Nachtrag 10.10.2026 (F179l–F179n)
    "sicherung_zeitplan": {
        "name": "Zeitplan der Sicherung festlegen", "bestaetigung": "2fa", "recht": "backup_verwalten", "intern": True,
        "beschreibung": "Uhrzeit der nächtlichen Sicherung (täglich oder werktags). Der Server stellt den Timer um.",
    },
    "journal_aufraeumen": {
        "name": "Journal aufräumen", "bestaetigung": "einfach", "intern": True,
        "beschreibung": "Ältere Einträge des Systemprotokolls (Journal) entfernen – auf eine Größe oder ein Alter.",
    },
    "images_loeschen": {
        "name": "Alte Versionen löschen", "bestaetigung": "2fa", "intern": True,
        "beschreibung": "Gespeicherte Image-Dateien, Update-Pakete und Docker-Images alter Versionen löschen. Die "
                        "laufende und die vorherige Version (für „Zurückschalten“) bleiben immer.",
    },
    "uhr_einstellen": {
        "name": "Uhrzeit einstellen", "bestaetigung": "2fa", "intern": True,
        "beschreibung": "Zeitzone, Zeitsynchronisation (NTP) mit eigenem Zeitserver, z. B. der OPNsense, oder die "
                        "Uhrzeit von Hand.",
    },
}

# Aktionen der Seite Administration › Backup (für deren Liste der Tätigkeiten)
SICHERUNG_AKTIONEN = ("sicherung", "sicherung_passwort", "sicherung_ziel", "sicherung_ziel_entfernen",
                      "sicherung_ziel_testen", "sicherung_uebertragen", "sicherung_aufbewahrung",
                      "sicherung_bereitstellen", "sicherung_einlesen", "wiederherstellen", "sicherung_loeschen",
                      "sicherung_zeitplan")

# Systemverwaltung ohne SSH (10.10.2026): dieselben Listen und Muster wie im Agenten (der prüft noch einmal)
DIENSTE = ("backend", "web", "ocr", "db")
TAG_MUSTER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40}$")
PAKET_MUSTER = re.compile(r"^epm-paket-([0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40})\.tar$")
PROTOKOLLE = {
    "backend": "Container backend (Django)", "web": "Container web (Nginx)", "ocr": "Container ocr (Texterkennung)",
    "db": "Container db (PostgreSQL)", "systemagent": "Systemagent", "backup": "Nächtliche Sicherung",
    "uebertragung": "Übertragung der Sicherungen", "update": "Letztes EPM-Update (/var/log/epm-update.log)",
}
PROTOKOLL_ZEILEN = (100, 500, 2000)
LOESCHEN_MAX = 200
# Nachtrag 10.10.2026: wie im Agenten
ZEITPLAN_TAGE = ("taeglich", "werktags")
JOURNAL_GROESSE = ("100M", "200M", "500M", "1G")
JOURNAL_ZEIT = ("2weeks", "1month", "3months", "6months")
IMAGE_DATEI_MUSTER = re.compile(r"^epm-(paket-)?([0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{7,40})\.tar$")
ZEITZONE_MUSTER = re.compile(r"^[A-Za-z]+(/[A-Za-z0-9_+-]+){0,2}$|^UTC$")
NTP_SERVER_MUSTER = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}"
                               r"[A-Za-z0-9])?$|^[0-9a-fA-F:]{2,39}$")
NTP_SERVER_MAX = 4
ZEIT_SETZEN_MUSTER = re.compile(r"^20[2-9][0-9]-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]) ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$")

STATUS_VERALTET_S = 180   # der Agent misst jede Minute; älter heißt: Agent läuft nicht


def ordner_auftraege():
    return settings.EPM_SYSTEM / "auftraege"


def ordner_status():
    return settings.EPM_SYSTEM / "status"


def ordner_download():
    """Zum Herunterladen bereitgestellte Sicherungen (schreibt der Agent; Backend und Webserver lesen nur)."""
    return settings.EPM_SYSTEM / "download"


def ordner_upload():
    """Hochgeladene Sicherungen, Update-Pakete und OCR-Modelle (schreibt das Backend, der Agent übernimmt sie und
    entfernt sie)."""
    return settings.EPM_SYSTEM / "upload"


def protokoll_datei(auftrag):
    """Vom Agenten abgerufenes Protokoll (``status/protokolle/<Auftrag>.log``, nach 1 Stunde entfernt)."""
    return ordner_status() / "protokolle" / f"{auftrag.kennung.hex}.log"


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


# Zeiträume der Auslastung (Fehlerliste 02.10.2026, 4.1): Code -> (Bezeichnung, Sekunden, Stufe des Agenten).
# „minute“ sind die Messungen je Minute (24 Stunden), die gröberen Stufen Mittelwerte mit Spitzen.
ZEITRAEUME = {
    "1h": ("1 Stunde", 3600, "minute"),
    "3h": ("3 Stunden", 3 * 3600, "minute"),
    "24h": ("24 Stunden", 24 * 3600, "minute"),
    "7t": ("7 Tage", 7 * 86400, "viertelstunde"),
    "14t": ("14 Tage", 14 * 86400, "viertelstunde"),
    "1m": ("1 Monat", 31 * 86400, "stunde"),
    "6m": ("6 Monate", 184 * 86400, "vierteltag"),
}
VERLAUF_FELDER = ["zeit", "cpu", "ram", "last", "platte"]


def verlauf(zeitraum: str = "24h"):
    """Auslastung im gewählten Zeitraum: {"felder", "punkte", "zeitraum", "schritt_s", "von", "bis", "zeitraeume"}.
    Reicht der Verlauf noch nicht so weit zurück (der Agent sammelt erst seit seiner Einrichtung), beginnt er später."""
    name, sekunden, stufe = ZEITRAEUME.get(zeitraum) or ZEITRAEUME["24h"]
    zeitraum = zeitraum if zeitraum in ZEITRAEUME else "24h"
    daten = _lies(ordner_status() / "verlauf.json")
    daten = daten if isinstance(daten, dict) else {}
    if stufe == "minute":
        punkte, felder, schritt = daten.get("punkte"), daten.get("felder"), 60
    else:
        teil = (daten.get("stufen") or {}).get(stufe) if isinstance(daten.get("stufen"), dict) else None
        teil = teil if isinstance(teil, dict) else {}
        punkte, felder, schritt = teil.get("punkte"), teil.get("felder"), teil.get("sekunden") or 0
    punkte = [p for p in punkte or [] if isinstance(p, list) and p and isinstance(p[0], (int, float))]
    bis = int(timezone.now().timestamp())
    von = bis - sekunden
    return {
        "felder": felder if isinstance(felder, list) else VERLAUF_FELDER,
        "punkte": [p for p in punkte if p[0] >= von],
        "zeitraum": zeitraum, "name": name, "schritt_s": schritt, "von": von, "bis": bis,
        "zeitraeume": [{"code": c, "name": n} for c, (n, _s, _st) in ZEITRAEUME.items()],
    }


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


def auftrag_ablegen(auftrag, geheim=None):
    """Auftragsdatei für den Agenten schreiben (atomar: erst .tmp, dann umbenennen – der Agent liest nur *.json).
    ``geheim`` (Passwörter) steht nur in dieser Datei (0600, der Agent löscht sie sofort nach dem Lesen), nie in der
    Datenbank."""
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
    if geheim:
        daten["geheim"] = geheim
    tmp = ordner / f".{auftrag.kennung.hex}.tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
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
