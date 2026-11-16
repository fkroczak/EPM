"""OCR-Dienst (Container ``ocr``): arbeitet die Warteschlange der Scans ab und räumt stündlich auf.

    python manage.py epm_ocr            # Dauerbetrieb
    python manage.py epm_ocr --einmal   # alle wartenden Scans, dann Ende (Tests, Fehlersuche)
    python manage.py epm_ocr --stand    # bereitstehende Verfahren anzeigen
"""
import json
import logging
import os
import signal
import threading
import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from diktate import abschrift as diktat_abschrift, dienst as diktat_dienst
from diktate.models import Diktat
from scans import dienst, dokumente
from scans.ocr.erkennung import verfahren_stand
from scans.ocr.paddle import Paddle

log = logging.getLogger("epm.scans")


class Command(BaseCommand):
    help = "Texterkennung für „Scans“: Warteschlange abarbeiten, abgelaufene Scans löschen."

    def add_arguments(self, parser):
        parser.add_argument("--einmal", action="store_true", help="alle wartenden Aufträge, dann beenden")
        parser.add_argument("--stand", action="store_true", help="Stand der Verfahren ausgeben und beenden")

    def handle(self, *args, einmal=False, stand=False, **opt):
        if stand:
            for name, s in verfahren_stand().items():
                self.stdout.write(f"{name}: {'bereit' if s['bereit'] else 'NICHT bereit'} – {s['text']}")
            return
        try:  # niedrige Priorität: das EPM bleibt flüssig, auch während einer langen Erkennung
            os.nice(int(os.environ.get("EPM_OCR_NICE", "10")))
        except OSError:
            pass
        ende = {"jetzt": False, "scan": None}

        if einmal:
            def stopp(*_):
                ende["jetzt"] = True

            signal.signal(signal.SIGTERM, stopp)
            signal.signal(signal.SIGINT, stopp)
        else:
            # Beenden (docker stop, Update): Ein eigener Faden nimmt das Signal sofort an – auch mitten in einer
            # Seite, wo der Hauptfaden in onnxruntime oder Tesseract steckt –, stellt den laufenden Scan zurück in
            # die Warteschlange (zählt nicht als Abbruch) und beendet den Prozess.
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})

            def warten():
                signal.sigwait({signal.SIGTERM, signal.SIGINT})
                ende["jetzt"] = True
                try:
                    aktuell = ende["scan"]
                    if isinstance(aktuell, Diktat):
                        diktat_dienst.geplant_beendet(aktuell)
                    elif isinstance(aktuell, dokumente.DokumentErkennung):
                        dokumente.geplant_beendet(aktuell)
                    elif aktuell is not None:
                        dienst.geplant_beendet(aktuell)
                    log.info("OCR-Dienst beendet")
                finally:
                    os._exit(0)

            threading.Thread(target=warten, name="epm-ocr-signal", daemon=True).start()
        try:
            paddle = Paddle.laden()
        except Exception:  # noqa: BLE001 – ohne PP-OCR weiter mit Tesseract (Systemseite zeigt es)
            log.exception("PP-OCR-Modelle nicht ladbar – Erkennung nur mit Tesseract")
            paddle = None
        stand_text = verfahren_stand()
        # Diktate (23.10.2026): Modell erst beim ersten Diktat laden, nach Leerlauf wieder freigeben
        abschreiber = diktat_abschrift.Abschreiber()
        bereit, grund = diktat_abschrift.bereitschaft()
        diktat_stand = {"bereit": bereit, "grund": grund, "modell": diktat_abschrift.MODELL_NAME,
                        "threads": diktat_abschrift.threads()}
        log.info("Diktate: %s", "bereit" if bereit else grund)
        log.info("OCR-Dienst bereit: Tesseract %s, PP-OCR %s", stand_text["tesseract"]["text"],
                 stand_text["paddle"]["text"])
        lebt = Path(os.environ.get("EPM_OCR_LEBT", "/tmp/epm-ocr-lebt"))
        start = timezone.now()
        zaehler = {"bearbeitet": 0, "zuletzt_stand": 0.0}

        def lebenszeichen():
            """Datei für den Healthcheck und – alle 30 s – Stand für die Systemseite (das Backend liest die Datei;
            es lädt selbst keine Modelle). Läuft auch mitten in einer Erkennung (Herzschlag)."""
            try:
                lebt.touch()
            except OSError:
                pass
            if time.monotonic() - zaehler["zuletzt_stand"] > 30:
                zaehler["zuletzt_stand"] = time.monotonic()
                stand_schreiben({"gestartet": start.isoformat(timespec="seconds"),
                                 "lebenszeichen": timezone.now().isoformat(timespec="seconds"),
                                 "verfahren": stand_text, "bearbeitet": zaehler["bearbeitet"], "diktat": diktat_stand,
                                 "threads": os.environ.get("EPM_OCR_THREADS", "2"), "speicher": speicher()})

        while not ende["jetzt"]:
            lebenszeichen()
            try:
                close_old_connections()
                dienst.bereinigen_hoechstens_stuendlich()
                # nach einem Neustart (z. B. Speichergrenze erreicht): abgebrochene Aufträge sofort wieder einreihen
                dienst.haengende_zuruecksetzen()
                diktat_dienst.haengende_zuruecksetzen()
                # Diktate „sofort“ zuerst (jemand wartet auf den Text), „nachts“ nur im Nachtfenster nach den Scans
                diktat = diktat_dienst.auftrag_holen() if diktat_stand["bereit"] else None
                scan = None if diktat is not None else dienst.auftrag_holen()
                # „Text erkennen“ an Dokumenten der Akte (F170), wenn keine Scans warten
                auftrag = None if diktat is not None or scan is not None else dokumente.auftrag_holen()
                if diktat is None and scan is None and auftrag is None and diktat_stand["bereit"] \
                        and diktat_dienst.nachtfenster():
                    diktat = diktat_dienst.auftrag_holen(nachts=True)
            except Exception:  # noqa: BLE001 – z. B. Datenbank startet noch oder Migration läuft
                log.exception("Warteschlange nicht lesbar – neuer Versuch in 10 Sekunden")
                time.sleep(10)
                continue
            if diktat is not None:
                log.info("Schreibe ab: %s", diktat)
                ende["scan"] = diktat
                try:
                    with dienst.herzschlag(diktat, zusatz=lebenszeichen):
                        fertig_d = diktat_dienst.abschreiben(diktat, abschreiber, abbrechen=lambda: ende["jetzt"],
                                                             lebenszeichen=lebenszeichen)
                    log.info("%s: %s (%s s)", fertig_d, fertig_d.get_status_display(), fertig_d.rechenzeit_s)
                except Exception:  # noqa: BLE001 – ein Diktat darf den Dienst nicht beenden
                    log.exception("Abschrift %s abgebrochen", diktat)
                ende["scan"] = None
                zaehler["bearbeitet"] += 1
                continue
            abschreiber.freigeben_wenn_ruhig()
            if scan is None and auftrag is not None:
                log.info("Text erkennen: %s", auftrag)
                ende["scan"] = auftrag

                def melden(text, a=auftrag):
                    dokumente.DokumentErkennung.objects.filter(pk=a.pk).update(schritt=text[:120],
                                                                                lebenszeichen=timezone.now())

                try:
                    with dienst.herzschlag(auftrag, zusatz=lebenszeichen):
                        fertig_a = dokumente.ausfuehren(auftrag, schritt=melden)
                    log.info("%s: %s", fertig_a, fertig_a.get_status_display())
                except Exception:  # noqa: BLE001 – ein Auftrag darf den Dienst nicht beenden
                    log.exception("Auftrag %s abgebrochen", auftrag)
                ende["scan"] = None
                zaehler["bearbeitet"] += 1
                continue
            if scan is None:
                if einmal:
                    break
                freigaben_im_leerlauf()
                time.sleep(2)
                continue
            log.info("Erkenne %s", scan)
            ende["scan"] = scan
            try:
                with dienst.herzschlag(scan, zusatz=lebenszeichen):
                    fertig = dienst.bearbeiten(scan, paddle, abbrechen=lambda: ende["jetzt"])
                log.info("%s: %s (%s s)", fertig, fertig.get_status_display(), fertig.dauer_s)
            except Exception:  # noqa: BLE001 – z. B. Scan während der Erkennung gelöscht, Datenbank weg
                log.exception("Erkennung von %s abgebrochen", scan)
            ende["scan"] = None
            zaehler["bearbeitet"] += 1
        close_old_connections()


_DATENPFLEGE_ALLE_S = 6 * 3600
_zuletzt_datenpflege = [0.0]


def freigaben_im_leerlauf():
    """Menü „Freigaben“ (16.11.2026): abgelaufene 60-s-Fenster umsetzen, auch wenn niemand die Seite offen hat; alle
    6 Stunden neue Datenpflege-Vorschläge aus Altdaten-Freitext. Fehler halten die Erkennung nie an."""
    from freigaben import datenpflege, dienst as freigaben_dienst
    from patienten.models import Patient

    try:
        freigaben_dienst.faellige_umsetzen()
        if time.monotonic() - _zuletzt_datenpflege[0] > _DATENPFLEGE_ALLE_S:
            _zuletzt_datenpflege[0] = time.monotonic()
            n = datenpflege.alle_erstellen(Patient.objects.filter(eingeschraenkt_am__isnull=True))
            if n:
                log.info("Datenpflege: %s neue Vorschläge im Menü „Freigaben“", n)
    except Exception:  # noqa: BLE001
        log.exception("Freigaben im Leerlauf fehlgeschlagen")


def speicher() -> dict | None:
    """Speicher des Containers (cgroup v2): belegt, Höchststand seit dem Start, Grenze – in Bytes."""
    basis = Path("/sys/fs/cgroup")

    def lies(name):
        try:
            wert = (basis / name).read_text().strip()
        except OSError:
            return None
        return None if wert == "max" else int(wert) if wert.isdigit() else None

    belegt = lies("memory.current")
    if belegt is None:
        return None
    return {"belegt": belegt, "hoechst": lies("memory.peak"), "grenze": lies("memory.max")}


def stand_schreiben(daten: dict):
    ziel = settings.EPM_SCANS / ".dienst"
    try:
        ziel.mkdir(mode=0o750, parents=True, exist_ok=True)
        tmp = ziel / "stand.json.neu"
        tmp.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, ziel / "stand.json")
    except OSError:
        log.warning("Stand des OCR-Dienstes nicht schreibbar (%s)", ziel)
