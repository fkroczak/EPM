"""Eingangsqueue des KI-Dienstes: alle Dokumente der Akten, nur lesend (Entscheidung 14.10.2026).

Fortlaufend: neue Dokumente zuerst (höhere Priorität), der Altbestand nach und nach, jüngste zuerst. Ausgenommen:

- Dokumente, die EPM selbst erzeugt hat (PDF von Plänen, Berichten, Schreiben – deren Inhalt ist schon strukturiert),
- ausgeblendete Dokumente,
- Akten mit eingeschränkter Verarbeitung (Art. 18 DSGVO) – sie werden nicht gelesen, auch nicht von der KI,
- abgeschlossene Akten (dort ließe sich ohnehin nichts übernehmen),
- Dateiformate, die die Texterkennung nicht liest.

Ein Dokument wird je Fassung (SHA-256) einmal verarbeitet. „Erneut verarbeiten“ setzt einen Vorgang zurück.
"""
import datetime as dt

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from .models import KiEinstellung, KiVorgang

LESBAR = ("application/pdf", "image/jpeg", "image/png", "image/tiff", "image/webp", "image/bmp", "image/heic",
          "image/heif")
NEU_TAGE = 7
PRIORITAET_NEU = 5
PRIORITAET_ANGEFORDERT = 10


def offene_dokumente():
    from patienten.models import Dokument

    vorhanden = KiVorgang.objects.filter(dokument=OuterRef("pk"))
    return (Dokument.objects
            .filter(ausgeblendet=False, mime__in=LESBAR, patient__eingeschraenkt_am__isnull=True,
                    patient__abgeschlossen_am__isnull=True)
            .exclude(herkunft=Dokument.Herkunft.SYSTEM)
            .exclude(Exists(vorhanden)))


def vormerken(anzahl: int = 200, *, altbestand: bool | None = None) -> int:
    """Bis zu ``anzahl`` Dokumente in die Queue legen; → Zahl neu vorgemerkter."""
    if altbestand is None:
        altbestand = KiEinstellung.laden().altbestand_lesen
    grenze = timezone.now() - dt.timedelta(days=NEU_TAGE)
    qs = offene_dokumente()
    if not altbestand:
        qs = qs.filter(hochgeladen_am__gte=grenze)
    neu = 0
    for dok in qs.select_related("patient").order_by("-hochgeladen_am", "-id")[:anzahl]:
        try:
            with transaction.atomic():
                KiVorgang.objects.create(
                    dokument=dok, patient=dok.patient, firma_id=dok.firma_id, sha256=dok.sha256,
                    ist_test=dok.patient.ist_test,
                    prioritaet=PRIORITAET_NEU if dok.hochgeladen_am >= grenze else 0)
                neu += 1
        except IntegrityError:
            continue  # gleichzeitig von einem anderen Worker vorgemerkt
    return neu


def anfordern(dokument, benutzer) -> KiVorgang:
    """Mitarbeiter fordert die Verarbeitung ausdrücklich an (läuft auch tagsüber, mit Vorrang)."""
    v = KiVorgang.objects.filter(dokument=dokument, sha256=dokument.sha256).first()
    jetzt = timezone.now()
    if v is None:
        v = KiVorgang.objects.create(dokument=dokument, patient=dokument.patient, firma_id=dokument.firma_id,
                                     sha256=dokument.sha256, ist_test=dokument.patient.ist_test,
                                     prioritaet=PRIORITAET_ANGEFORDERT, angefordert_von=benutzer, angefordert_am=jetzt)
        return v
    if v.status in (KiVorgang.Status.NEU, KiVorgang.Status.FEHLER, KiVorgang.Status.NACHVERARBEITUNG):
        if v.status == KiVorgang.Status.FEHLER:
            v.status, v.versuche = KiVorgang.Status.NEU, 0
        v.prioritaet, v.angefordert_von, v.angefordert_am = PRIORITAET_ANGEFORDERT, benutzer, jetzt
        v.fehler = ""
        v.save(update_fields=["status", "versuche", "prioritaet", "angefordert_von", "angefordert_am", "fehler"])
    return v


def stand() -> dict:
    """Fortschritt für die Administration: wie viel des Bestands schon gelesen ist."""
    from django.db.models import Count

    je_status = dict(KiVorgang.objects.values_list("status").annotate(n=Count("id")))
    offen = offene_dokumente().count()
    return {"je_status": je_status, "noch_nicht_vorgemerkt": offen,
            "gesamt": sum(je_status.values()) + offen}
