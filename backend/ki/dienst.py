"""Warteschlange des KI-Dienstes: Aufträge holen, Lebenszeichen, Abbrüche, Fehler.

Muster wie beim OCR-Dienst („Scans“): Aufträge werden mit ``SELECT … FOR UPDATE SKIP LOCKED`` geholt (mehrere
Worker-Fäden stören sich nicht), ein Faden schreibt während der Arbeit Lebenszeichen, ein Vorgang ohne Lebenszeichen
kommt nach ``HAENGT_NACH`` zurück in die Queue (nach ``MAX_VERSUCHE`` als Fehler).
"""
import datetime as dt
import json
import logging
import os
import threading

from django.conf import settings

from django.db import connection, transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils import timezone

from .models import KiBerichtsauftrag, KiVorgang

log = logging.getLogger("epm.ki")
S = KiVorgang.Status
HAENGT_NACH = dt.timedelta(minutes=5)
HERZSCHLAG_S = 20
MAX_VERSUCHE = 3
ANGEFORDERT_AB = 10


def auftrag_holen(*, nur_angefordert: bool, nachverarbeitung: bool) -> KiVorgang | None:
    """Nächster Vorgang: angeforderte zuerst, dann neue Dokumente, dann der Altbestand.
    ``nachverarbeitung``: auch Vorgänge, die auf das Modell gewartet haben (nur wenn es bereit ist)."""
    status = [S.NEU] + ([S.NACHVERARBEITUNG] if nachverarbeitung else [])
    with transaction.atomic():
        qs = (KiVorgang.objects.select_for_update(skip_locked=True, of=("self",))
              .filter(status__in=status, patient__eingeschraenkt_am__isnull=True,
                      patient__abgeschlossen_am__isnull=True, dokument__ausgeblendet=False))
        if nur_angefordert:
            qs = qs.filter(prioritaet__gte=ANGEFORDERT_AB)
        v = qs.order_by("-prioritaet", "id").first()
        if v is None:
            return None
        jetzt = timezone.now()
        v.status, v.begonnen_am, v.lebenszeichen = S.IN_VERARBEITUNG, jetzt, jetzt
        v.versuche += 1
        v.schritt, v.fortschritt = "wird vorbereitet", 0
        v.save(update_fields=["status", "begonnen_am", "lebenszeichen", "versuche", "schritt", "fortschritt"])
        return v


def fortschritt(vorgang: KiVorgang, text: str, prozent: int | None = None):
    felder = {"schritt": text[:120], "lebenszeichen": timezone.now()}
    if prozent is not None:
        felder["fortschritt"] = max(0, min(100, prozent))
    KiVorgang.objects.filter(pk=vorgang.pk).update(**felder)


def zurueckstellen(vorgang: KiVorgang, grund: str):
    """Abgebrochen (Nachtfenster zu Ende, Pause, Dienst beendet): zählt nicht als Versuch; bereits erkannte Seiten
    bleiben – es geht dort weiter."""
    KiVorgang.objects.filter(pk=vorgang.pk, status__in=KiVorgang.IN_ARBEIT).update(
        status=S.NEU, schritt=f"unterbrochen: {grund}"[:120], versuche=Greatest(F("versuche") - 1, 0))


def fehlgeschlagen(vorgang: KiVorgang, fehler: str):
    v = KiVorgang.objects.filter(pk=vorgang.pk).first()
    if v is None:
        return
    endgueltig = v.versuche >= MAX_VERSUCHE
    KiVorgang.objects.filter(pk=v.pk).update(
        status=S.FEHLER if endgueltig else S.NEU, fehler=fehler[:2000], schritt="",
        prioritaet=min(v.prioritaet, 0) if not endgueltig else v.prioritaet)


def haengende_zuruecksetzen() -> int:
    anzahl = 0
    grenze = timezone.now() - HAENGT_NACH
    for v in KiVorgang.objects.filter(status__in=KiVorgang.IN_ARBEIT, lebenszeichen__lt=grenze):
        anzahl += 1
        if v.versuche >= MAX_VERSUCHE:
            KiVorgang.objects.filter(pk=v.pk).update(
                status=S.FEHLER, schritt="",
                fehler="Die Verarbeitung wurde mehrfach abgebrochen (KI-Dienst beendet, vermutlich an seiner "
                       "Speichergrenze). „Erneut verarbeiten“ versucht es noch einmal.")
        else:
            KiVorgang.objects.filter(pk=v.pk).update(status=S.NEU, schritt="nach einem Abbruch erneut in der Queue")
    KiBerichtsauftrag.objects.filter(status=KiBerichtsauftrag.Status.LAEUFT, lebenszeichen__lt=grenze).update(
        status=KiBerichtsauftrag.Status.WARTET)
    return anzahl


def bericht_holen() -> KiBerichtsauftrag | None:
    with transaction.atomic():
        b = (KiBerichtsauftrag.objects.select_for_update(skip_locked=True)
             .filter(status=KiBerichtsauftrag.Status.WARTET).order_by("angefordert_am", "id").first())
        if b is None:
            return None
        b.status, b.lebenszeichen = KiBerichtsauftrag.Status.LAEUFT, timezone.now()
        b.save(update_fields=["status", "lebenszeichen"])
        return b


class herzschlag:
    """Solange der Block läuft, schreibt ein Faden alle ``HERZSCHLAG_S`` Sekunden das Lebenszeichen."""

    def __init__(self, obj, zusatz=None, takt: float = HERZSCHLAG_S):
        self.modell, self.pk, self.zusatz, self.takt = type(obj), obj.pk, zusatz, takt
        self._stopp = threading.Event()
        self._faden = threading.Thread(target=self._lauf, name="epm-ki-herzschlag", daemon=True)

    def _lauf(self):
        while not self._stopp.wait(self.takt):
            try:
                self.modell.objects.filter(pk=self.pk).update(lebenszeichen=timezone.now())
                if self.zusatz:
                    self.zusatz()
            except Exception:  # noqa: BLE001 – ein verpasstes Lebenszeichen ist kein Grund abzubrechen
                pass
        connection.close()  # eigene Verbindung dieses Fadens

    def __enter__(self):
        self._faden.start()
        return self

    def __exit__(self, *exc):
        self._stopp.set()
        self._faden.join(timeout=5)
        return False


def stand_schreiben(daten: dict):
    """Stand des KI-Dienstes für Administration › KI (das Backend liest die Datei, es spricht nie selbst mit dem
    Modell-Dienst)."""
    ziel = settings.EPM_KI / ".dienst"
    try:
        ziel.mkdir(mode=0o750, parents=True, exist_ok=True)
        tmp = ziel / "stand.json.neu"
        tmp.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, ziel / "stand.json")
    except OSError:
        log.warning("Stand des KI-Dienstes nicht schreibbar (%s)", ziel)


def stand_lesen() -> dict | None:
    try:
        daten = json.loads((settings.EPM_KI / ".dienst" / "stand.json").read_text())
    except (OSError, ValueError):
        return None
    zeit = daten.get("lebenszeichen")
    try:
        alter = (timezone.now() - dt.datetime.fromisoformat(zeit)).total_seconds() if zeit else None
    except ValueError:
        alter = None
    daten["alter_s"] = int(alter) if alter is not None else None
    daten["laeuft"] = alter is not None and alter < 120
    return daten
