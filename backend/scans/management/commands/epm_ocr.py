"""OCR-Dienst (Container ``ocr``): arbeitet die Warteschlange der Scans ab und räumt stündlich auf.

    python manage.py epm_ocr            # Dauerbetrieb
    python manage.py epm_ocr --einmal   # alle wartenden Scans, dann Ende (Tests, Fehlersuche)
    python manage.py epm_ocr --stand    # bereitstehende Verfahren anzeigen
"""
import json
import logging
import os
import signal
import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from scans import dienst
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
        ende = {"jetzt": False}

        def stopp(*_):
            ende["jetzt"] = True

        signal.signal(signal.SIGTERM, stopp)
        signal.signal(signal.SIGINT, stopp)
        try:
            paddle = Paddle.laden()
        except Exception:  # noqa: BLE001 – ohne PP-OCR weiter mit Tesseract (Systemseite zeigt es)
            log.exception("PP-OCR-Modelle nicht ladbar – Erkennung nur mit Tesseract")
            paddle = None
        stand_text = verfahren_stand()
        log.info("OCR-Dienst bereit: Tesseract %s, PP-OCR %s", stand_text["tesseract"]["text"],
                 stand_text["paddle"]["text"])
        lebt = Path(os.environ.get("EPM_OCR_LEBT", "/tmp/epm-ocr-lebt"))
        start = timezone.now()
        zuletzt_stand = 0.0
        bearbeitet = 0
        while not ende["jetzt"]:
            try:
                lebt.touch()
            except OSError:
                pass
            if time.monotonic() - zuletzt_stand > 30:
                # Stand für die Systemseite (das Backend liest die Datei; es lädt selbst keine Modelle)
                zuletzt_stand = time.monotonic()
                stand_schreiben({"gestartet": start.isoformat(timespec="seconds"),
                                 "lebenszeichen": timezone.now().isoformat(timespec="seconds"),
                                 "verfahren": stand_text, "bearbeitet": bearbeitet,
                                 "threads": os.environ.get("EPM_OCR_THREADS", "2")})
            try:
                close_old_connections()
                dienst.bereinigen_hoechstens_stuendlich()
                scan = dienst.auftrag_holen()
            except Exception:  # noqa: BLE001 – z. B. Datenbank startet noch oder Migration läuft
                log.exception("Warteschlange nicht lesbar – neuer Versuch in 10 Sekunden")
                time.sleep(10)
                continue
            if scan is None:
                if einmal:
                    break
                time.sleep(2)
                continue
            log.info("Erkenne %s", scan)
            fertig = dienst.bearbeiten(scan, paddle, abbrechen=lambda: ende["jetzt"])
            bearbeitet += 1
            log.info("%s: %s (%s s)", fertig, fertig.get_status_display(), fertig.dauer_s)
        close_old_connections()


def stand_schreiben(daten: dict):
    ziel = settings.EPM_SCANS / ".dienst"
    try:
        ziel.mkdir(mode=0o750, parents=True, exist_ok=True)
        tmp = ziel / "stand.json.neu"
        tmp.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, ziel / "stand.json")
    except OSError:
        log.warning("Stand des OCR-Dienstes nicht schreibbar (%s)", ziel)
