"""
Administration › Backup (F61–F64, O-07, O-23): was das Backend über die Sicherungen weiß.

Die Sicherungen liegen auf dem Server (``/srv/epm/backup``), Passwort und Übertragungsziel nur für root lesbar unter
``/etc/epm/sicherung`` – beides erreicht der Container nicht. Der Systemagent schreibt jede Minute
``EPM_SYSTEM/status/sicherung.json`` (Bestand, Verschlüsselung, Ziel ohne Zugangsdaten, Übertragung, Speicher) und
``sicherung-pruefwerte.json`` (scrypt-Prüfwerte der Passwörter, damit ein eingegebenes Passwort geprüft werden kann –
für das Passwortblatt; das Passwort selbst kennt nur der Server). Aufträge (sichern, Passwort, Ziel, übertragen,
wiederherstellen) gehen wie unter Administration › System als Auftragsdatei an den Agenten (``host``).
"""
import hashlib
import hmac
import re
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import host

STEMPEL_MUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}(\d{2})?$")
ID_MUSTER = re.compile(r"^[0-9a-f]{32}$")
ZEIT_MUSTER = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
PASSWORT_MIN, PASSWORT_MAX = 16, 200            # wie im Systemagenten
SICHERUNG_ALT_H = 36                             # letzte Sicherung älter: Warnung (die nächtliche fehlt)
UEBERTRAGUNG_ALT_H = 26                          # verschlüsselte Sicherung so lange nicht übertragen: Warnung
PRUEF_FEHLVERSUCHE, PRUEF_MINUTEN = 5, 15        # falsche Sicherungs-Passwörter je Person, danach kurz gesperrt
ARTEN = {"nachts": "Automatisch", "von_hand": "Von Hand", "vor_update": "Vor Update", "vor_aenderung": "Vor Neustart",
         "vor_wiederherstellung": "Vor Wiederherstellung", "unbekannt": "Unbekannt"}


def status():
    """``sicherung.json`` vom Agenten mit Alter; ``None``, wenn er sie (noch) nicht geschrieben hat."""
    daten = host._lies(host.ordner_status() / "sicherung.json")
    if not isinstance(daten, dict):
        return None
    zeit = host._zeit(daten.get("zeit"))
    alter = int((timezone.now() - zeit).total_seconds()) if zeit else None
    daten["alter_s"] = alter
    daten["aktuell"] = alter is not None and alter <= host.STATUS_VERALTET_S
    if not isinstance(daten.get("sicherungen"), list):
        daten["sicherungen"] = []
    return daten


def sicherungen(daten=None):
    daten = daten if daten is not None else status()
    return [s for s in (daten or {}).get("sicherungen", []) if isinstance(s, dict) and s.get("stempel")]


def finde(stempel: str, daten=None):
    if not isinstance(stempel, str) or not STEMPEL_MUSTER.match(stempel):
        return None
    return next((s for s in sicherungen(daten) if s["stempel"] == stempel), None)


# ------------------------------------------------------------------ Passwort prüfen (Passwortblatt)
def _pruefwerte():
    daten = host._lies(host.ordner_status() / "sicherung-pruefwerte.json")
    werte = (daten or {}).get("pruefwerte") if isinstance(daten, dict) else None
    return [w for w in werte or [] if isinstance(w, dict)]


def passwort_nr(passwort: str):
    """Nummer der Passwort-Version, zu der das Passwort passt (scrypt wie im Agenten), sonst ``None``."""
    if not isinstance(passwort, str) or not (PASSWORT_MIN <= len(passwort) <= PASSWORT_MAX):
        return None
    for w in _pruefwerte():
        try:
            n, r, p = int(w["n"]), int(w["r"]), int(w["p"])
            if w.get("verfahren") != "scrypt" or not (2 ** 10 <= n <= 2 ** 18 and 1 <= r <= 16 and 1 <= p <= 4):
                continue
            soll = bytes.fromhex(w["wert"])
            ist = hashlib.scrypt(passwort.encode(), salt=bytes.fromhex(w["salz"]), n=n, r=r, p=p, dklen=len(soll),
                                 maxmem=256 * 1024 * 1024)
        except (KeyError, TypeError, ValueError):
            continue
        if hmac.compare_digest(ist, soll):
            return w.get("nr")
    return None


def pruefung_gesperrt(user) -> bool:
    """Schutz gegen Raten über die Prüfung: nach 5 falschen Passwörtern in 15 Minuten kurz keine weitere."""
    from audit.models import SystemEreignis

    seit = timezone.now() - timedelta(minutes=PRUEF_MINUTEN)
    return SystemEreignis.objects.filter(art=SystemEreignis.Art.BACKUP, benutzer=user, zeitpunkt__gte=seit,
                                         details__ereignis="passwort_falsch").count() >= PRUEF_FEHLVERSUCHE


# ------------------------------------------------------------------ Zustand (Startseite, Backup-Seite)
def _alter_h(text):
    zeit = host._zeit(text)
    return (timezone.now() - zeit).total_seconds() / 3600 if zeit else None


def _loeschungen_hinweis():
    """Konnten endgültige Löschungen (Art. 17 DSGVO) beim letzten Lauf nicht vollständig nachgeholt werden – etwa nach
    einer Wiederherstellung –, ist das ein Fehler, den jemand sehen muss (O-28). Der Stand liegt neben der Löschliste."""
    from patienten.loeschung import nachholen_stand

    stand = nachholen_stand()
    if not stand or stand["status"] != "fehler":
        return None
    return (2, "Löschungen nicht nachgeholt",
            "Endgültige Löschungen (Art. 17 DSGVO) konnten nicht vollständig nachgeholt werden – siehe Audit-Log "
            "(System). Nach der Behebung: Backend neu starten.")


def kurzstatus(daten=None, mit_daten=False):
    """Zustand der Sicherung für die Kopfzeile der Startseite (O-07): ``zustand`` ok | warnung | fehler | unbekannt,
    letzte Sicherung, Hinweise (schlimmste zuerst). Enthält keine Zugangsdaten und nichts aus den Akten."""
    daten = daten if daten is not None else status()
    hinweise = []   # (stufe, kurz, text): 2 = fehler, 1 = warnung; „kurz“ für die Kopfzeile der Startseite
    liste = sicherungen(daten)
    letzte = liste[0] if liste else None
    loeschungen = _loeschungen_hinweis()
    if daten is None:
        ergebnis = {"zustand": "unbekannt", "letzte_am": None, "verschluesselt": None, "titel": "Backup-Status fehlt",
                    "hinweise": ["Kein Status vom Server – der Systemagent ist nicht eingerichtet."]}
        if loeschungen:
            ergebnis.update(zustand="fehler", titel=loeschungen[1])
            ergebnis["hinweise"].insert(0, loeschungen[2])
        return (ergebnis, daten) if mit_daten else ergebnis
    if loeschungen:
        hinweise.append(loeschungen)
    if not daten.get("aktuell"):
        hinweise.append((2, "Backup-Status veraltet",
                         "Der Server meldet seit mehr als 3 Minuten keinen Stand der Sicherungen."))
    if letzte is None:
        hinweise.append((2, "Noch kein Backup", "Es gibt noch keine Sicherung."))
    else:
        alter = _alter_h(letzte.get("zeitpunkt"))
        if alter is None or alter > SICHERUNG_ALT_H:
            hinweise.append((2, "Backup älter als 36 h", "Die letzte Sicherung ist älter als 36 Stunden."))
        if not letzte.get("verschluesselt"):
            hinweise.append((1, "Backup unverschlüsselt",
                             "Die letzte Sicherung ist unverschlüsselt – Sicherungs-Passwort festlegen."))
    if daten.get("nachts_fehlgeschlagen"):
        hinweise.append((2, "Backup fehlgeschlagen", "Die letzte nächtliche Sicherung ist fehlgeschlagen."))
    ziel = daten.get("ziel") or {}
    ue = daten.get("uebertragung") or {}
    if not ziel.get("eingerichtet"):
        hinweise.append((1, "Backup nur auf dem Server",
                         "Sicherungen liegen nur auf dem Server – Übertragungsziel festlegen."))
    else:
        if ue.get("letzter_fehler"):
            hinweise.append((1, "Übertragung fehlgeschlagen", "Die letzte Übertragung ist fehlgeschlagen."))
        offen_alt = [s for s in liste if s.get("verschluesselt") and s.get("verfahren") == "gpg"
                     and not s.get("uebertragen_am") and (_alter_h(s.get("zeitpunkt")) or 0) > UEBERTRAGUNG_ALT_H]
        if offen_alt:
            hinweise.append((1, "Backup nicht übertragen",
                             f"{len(offen_alt)} Sicherung(en) seit über einem Tag nicht übertragen."))
    hinweise.sort(key=lambda h: -h[0])
    stufe = hinweise[0][0] if hinweise else 0
    ergebnis = {
        "zustand": {0: "ok", 1: "warnung", 2: "fehler"}[stufe],
        "letzte_am": letzte.get("zeitpunkt") if letzte else None,
        "verschluesselt": letzte.get("verschluesselt") if letzte else None,
        "titel": hinweise[0][1] if hinweise else "",
        "hinweise": [t for _, _k, t in hinweise],
    }
    return (ergebnis, daten) if mit_daten else ergebnis


# ------------------------------------------------------------------ nach einer Wiederherstellung
def wiederherstellungen_nachtragen() -> int:
    """Wiederherstellungen ins Audit-Log der (zurückgespielten) Datenbank eintragen und alle Anmeldungen beenden.

    Der Agent vermerkt eine Wiederherstellung in ``status/wiederherstellungen.json`` (Zustand „umgestellt“), bevor das
    Backend mit der zurückgespielten Datenbank startet. Diese Datenbank kennt den Auftrag und alles danach nicht –
    deshalb hier: Eintrag im Audit-Log (wer, wann, welche Sicherung, wo der Stand davor gesichert ist), der Auftrag in
    der Liste der Tätigkeiten und das Ende aller Anmeldungen (sonst gälten Sitzungen aus der Zeit der Sicherung wieder).
    Läuft beim Start (entrypoint.sh) und vorsichtshalber beim Abruf der Backup-Seite; je Wiederherstellung einmal."""
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session

    from accounts.models import Sitzung
    from audit.models import SystemEreignis, protokolliere

    from .models import Systemauftrag

    liste = host._lies(host.ordner_status() / "wiederherstellungen.json")
    if not isinstance(liste, list):
        return 0
    anzahl = 0
    for e in liste:
        if not isinstance(e, dict) or e.get("status") not in ("umgestellt", "erledigt"):
            continue
        kennung = str(e.get("id") or "")
        if not ID_MUSTER.match(kennung):
            continue
        if SystemEreignis.objects.filter(art=SystemEreignis.Art.BACKUP, details__ereignis="wiederhergestellt",
                                         details__auftrag=kennung).exists():
            continue
        von = str(e.get("angefordert_von") or "")[:150]
        with transaction.atomic():
            user = get_user_model().objects.filter(username=von).first() if von else None
            auftrag = Systemauftrag.objects.filter(kennung=uuid.UUID(kennung)).first()
            if auftrag is None and user is not None:
                auftrag = Systemauftrag.objects.create(
                    kennung=uuid.UUID(kennung), ziel=Systemauftrag.Ziel.SERVER, aktion="wiederherstellen",
                    parameter={"stempel": e.get("stempel"), "sicherung_zeitpunkt": e.get("sicherung_zeitpunkt")},
                    angefordert_von=user, begonnen_am=host._zeit(e.get("begonnen_am")),
                    # „umgestellt“: der Agent schließt den Auftrag gleich ab; das Ergebnis übernimmt der Abgleich
                    status=Systemauftrag.Status.LAEUFT if e["status"] == "umgestellt" else Systemauftrag.Status.ERLEDIGT,
                    beendet_am=host._zeit(e.get("beendet_am")), ergebnis=str(e.get("ergebnis") or "")[:500])
                if host._zeit(e.get("begonnen_am")):
                    Systemauftrag.objects.filter(pk=auftrag.pk).update(angefordert_am=host._zeit(e["begonnen_am"]))
            protokolliere(SystemEreignis.Art.BACKUP, benutzer=user, benutzername=von,
                          objekt=f"Sicherung {e.get('stempel', '')}", ereignis="wiederhergestellt", auftrag=kennung,
                          stempel=e.get("stempel"), sicherung_zeitpunkt=e.get("sicherung_zeitpunkt"),
                          vorher_stempel=e.get("vorher_stempel"), begonnen_am=e.get("begonnen_am"))
            Session.objects.all().delete()
            Sitzung.objects.all().delete()
        anzahl += 1
    return anzahl
