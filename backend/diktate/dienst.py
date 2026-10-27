"""Warteschlange der Diktate – vom Backend (Hochladen, Übernehmen, Freigabe) und vom OCR-Dienst (Abschreiben).

Reihenfolge im OCR-Dienst: Diktate „sofort“ vor Scans (jemand wartet auf den Text), Diktate „nachts“ nur im
Nachtfenster (``EPM_DIKTAT_NACHT``, Standard 21–7 Uhr) und nach den Scans.
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils import timezone

from .models import Diktat, diktat_ordner

log = logging.getLogger("epm.diktate")

HAENGT_NACH = timedelta(seconds=90)
MAX_VERSUCHE = 3
# Kommentare zu Infusionsplänen, die niemand übernommen hat, und Reste ohne Datensatz
PLAN_AUFBEWAHREN = timedelta(days=3)
# nicht zugeordnete Diktate (27.10.2026): so lange wie Scans ohne Zuordnung
OHNE_ZUORDNUNG_AUFBEWAHREN = timedelta(days=7)
MAX_DAUER_S = 60 * 60
MAX_BYTES = 40 * 1024 * 1024
ENDUNGEN = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac",
            "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav", "video/webm": "webm"}


def nachtfenster(jetzt=None) -> bool:
    wert = os.environ.get("EPM_DIKTAT_NACHT", "21-7")
    try:
        ab, bis = (int(x) for x in wert.split("-"))
    except ValueError:
        ab, bis = 21, 7
    stunde = timezone.localtime(jetzt or timezone.now()).hour
    return stunde >= ab or stunde < bis if ab > bis else ab <= stunde < bis


# ---------------------------------------------------------------- Backend
def speichern(diktat: Diktat, hochgeladen) -> Diktat:
    """Aufnahme unter einem zufälligen Namen ablegen (nur der Dienst und das Backend lesen sie)."""
    mime = (getattr(hochgeladen, "content_type", "") or "").split(";")[0].strip().lower()
    endung = ENDUNGEN.get(mime)
    if endung is None:
        raise ValueError("Dieses Tonformat wird nicht unterstützt.")
    if hochgeladen.size > MAX_BYTES:
        raise ValueError("Die Aufnahme ist zu groß (höchstens 40 MB, etwa eine Stunde).")
    if hochgeladen.size < 200:
        raise ValueError("Die Aufnahme ist leer.")
    ordner = diktat_ordner()
    ordner.mkdir(mode=0o750, parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}.{endung}"
    ziel = ordner / name
    with open(ziel, "xb") as f:
        for teil in hochgeladen.chunks():
            f.write(teil)
    os.chmod(ziel, 0o640)
    diktat.datei, diktat.mime, diktat.groesse = name, mime, hochgeladen.size
    try:
        diktat.save()
    except BaseException:
        ziel.unlink(missing_ok=True)
        raise
    return diktat


def aufnahme_loeschen(diktat: Diktat, text_auch: bool = False):
    """Aufnahme löschen (nach dem Commit), Datensatz bleibt als Nachweis: wer wann wie lange diktiert hat."""
    pfad = diktat.pfad
    felder = {"datei": "", "audio_geloescht_am": timezone.now()}
    if text_auch:
        felder.update(text="", woerter=[])
    Diktat.objects.filter(pk=diktat.pk).update(**felder)
    if pfad is not None:
        transaction.on_commit(lambda: pfad.unlink(missing_ok=True))


def bei_freigabe(bericht):
    """Bericht wird freigegeben: Läuft noch eine Abschrift, wartet die Freigabe; sonst Aufnahmen und Abschriften
    löschen – der Text steht jetzt im Bericht."""
    from django.core.exceptions import ValidationError

    if Diktat.objects.filter(bericht=bericht, status__in=[Diktat.Status.WARTET, Diktat.Status.LAEUFT]).exists():
        raise ValidationError("Ein Diktat zu diesem Bericht wird noch abgeschrieben. Bitte warten, bis es fertig ist, "
                              "oder das Diktat verwerfen.")
    for d in Diktat.objects.filter(bericht=bericht, audio_geloescht_am__isnull=True):
        aufnahme_loeschen(d, text_auch=True)
    Diktat.objects.filter(bericht=bericht).exclude(text="").update(text="", woerter=[])


# ---------------------------------------------------------------- OCR-Dienst
def auftrag_holen(nachts: bool = False) -> Diktat | None:
    with transaction.atomic():
        qs = Diktat.objects.select_for_update(skip_locked=True).filter(status=Diktat.Status.WARTET)
        qs = qs.filter(wann=Diktat.Wann.NACHTS) if nachts else qs.filter(wann=Diktat.Wann.SOFORT)
        d = qs.order_by("erstellt_am", "id").first()
        if d is None:
            return None
        jetzt = timezone.now()
        d.status, d.lebenszeichen, d.schritt, d.fehler = Diktat.Status.LAEUFT, jetzt, "wird abgeschrieben", ""
        d.versuche += 1
        d.save(update_fields=["status", "lebenszeichen", "schritt", "fehler", "versuche"])
        return d


def haengende_zuruecksetzen() -> int:
    anzahl = 0
    for d in Diktat.objects.filter(status=Diktat.Status.LAEUFT, lebenszeichen__lt=timezone.now() - HAENGT_NACH):
        anzahl += 1
        if d.versuche >= MAX_VERSUCHE:
            Diktat.objects.filter(pk=d.pk).update(
                status=Diktat.Status.FEHLER, schritt="",
                fehler="Die Abschrift wurde mehrfach abgebrochen (vermutlich an der Speichergrenze des "
                       "Erkennungsdienstes). „Erneut abschreiben“ versucht es noch einmal.")
        else:
            Diktat.objects.filter(pk=d.pk).update(status=Diktat.Status.WARTET, schritt="nach einem Abbruch erneut "
                                                                                       "in der Warteschlange")
    return anzahl


def geplant_beendet(d: Diktat):
    Diktat.objects.filter(pk=d.pk, status=Diktat.Status.LAEUFT).update(
        status=Diktat.Status.WARTET, schritt="Erkennungsdienst neu gestartet – geht gleich weiter",
        versuche=Greatest(F("versuche") - 1, 0))


def abschreiben(d: Diktat, abschreiber, abbrechen=lambda: False, lebenszeichen=None) -> Diktat:
    """Ein Diktat abschreiben; Fehler landen verständlich am Diktat, der Dienst läuft weiter."""
    from audit.models import SystemEreignis, protokolliere

    from . import abschrift
    from .models import Begriffsliste

    t0 = time.monotonic()
    try:
        if d.pfad is None or not d.pfad.is_file():
            raise abschrift.AbschriftFehler("Die Aufnahme ist nicht mehr vorhanden.")
        Diktat.objects.filter(pk=d.pk).update(schritt="Aufnahme wird gelesen", lebenszeichen=timezone.now())
        audio = abschrift.audio_laden(d.pfad)
        eigene = Begriffsliste.objects.filter(benutzer_id=d.erstellt_von_id).values_list("begriffe", flat=True).first()
        vorlage = abschrift.vorlage(d.patient, eigene or "", d.zweck)
        Diktat.objects.filter(pk=d.pk).update(schritt="wird abgeschrieben", lebenszeichen=timezone.now())
        def fortschritt(anteil: float):
            Diktat.objects.filter(pk=d.pk).update(schritt=f"wird abgeschrieben ({round(anteil * 100)} %)",
                                                  lebenszeichen=timezone.now())
            if lebenszeichen is not None:
                lebenszeichen()

        woerter = abschreiber.abschreiben(audio, vorlage, abbrechen=abbrechen, fortschritt=fortschritt)
        if abbrechen():
            geplant_beendet(d)
            return d
        text = abschrift.als_html(abschrift.klartext(woerter))
        jetzt = timezone.now()
        Diktat.objects.filter(pk=d.pk, status=Diktat.Status.LAEUFT).update(
            status=Diktat.Status.FERTIG, text=text, woerter=woerter, modell=abschrift.MODELL_NAME,
            rechenzeit_s=round(time.monotonic() - t0, 1), abgeschrieben_am=jetzt, schritt="",
            dauer_s=d.dauer_s or round(len(audio) / abschrift.ABTASTRATE, 1))
        protokolliere(SystemEreignis.Art.DIKTAT, benutzername="ocr", objekt=f"Diktat {d.pk}", aktion="abgeschrieben",
                      patient=d.patient.nummer if d.patient_id else None, woerter=len(woerter), unsicher=abschrift.unsichere(woerter),
                      rechenzeit_s=round(time.monotonic() - t0, 1))
    except abschrift.AbschriftFehler as e:
        Diktat.objects.filter(pk=d.pk).update(status=Diktat.Status.FEHLER, fehler=str(e)[:300], schritt="")
    except Exception:  # noqa: BLE001
        log.exception("Abschrift von Diktat %s fehlgeschlagen", d.pk)
        Diktat.objects.filter(pk=d.pk).update(status=Diktat.Status.FEHLER, schritt="",
                                              fehler="Die Abschrift ist fehlgeschlagen. „Erneut abschreiben“ "
                                                     "versucht es noch einmal.")
    d.refresh_from_db()
    return d


def bereinigen() -> int:
    """Stündlich: nicht übernommene Kommentar-Diktate nach 3 Tagen, nicht zugeordnete Diktate nach 7 Tagen (wie Scans),
    Dateien ohne Datensatz nach einem Tag."""
    grenze = timezone.now() - PLAN_AUFBEWAHREN
    alte = list(Diktat.objects.filter(zweck=Diktat.Zweck.PLAN, erstellt_am__lt=grenze))
    alte += list(Diktat.objects.filter(patient__isnull=True, erstellt_am__lt=timezone.now() - OHNE_ZUORDNUNG_AUFBEWAHREN)
                 .exclude(status=Diktat.Status.LAEUFT))
    for d in alte:
        d.delete()
    ordner = diktat_ordner()
    bekannte = set(Diktat.objects.exclude(datei="").values_list("datei", flat=True))
    weg = 0
    if ordner.is_dir():
        for f in ordner.iterdir():
            try:
                if f.is_file() and f.name not in bekannte and time.time() - f.stat().st_mtime > 86400:
                    f.unlink()
                    weg += 1
            except OSError:
                pass
    return len(alte) + weg


def stand() -> dict:
    from scans.dienst import dienst_stand

    d = dienst_stand() or {}
    diktat = d.get("diktat") or {}
    laeuft = bool(d.get("laeuft"))
    bereit = laeuft and bool(diktat.get("bereit"))
    if bereit:
        grund = ""
    elif not laeuft:
        grund = "Der Erkennungsdienst läuft gerade nicht."
    else:
        grund = diktat.get("grund") or ""
    return {
        "bereit": bereit,
        "grund": grund,
        "dienst_laeuft": laeuft,
        "wartend": Diktat.objects.filter(status__in=[Diktat.Status.WARTET, Diktat.Status.LAEUFT]).count(),
    }
