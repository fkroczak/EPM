"""Eingangsqueue des KI-Dienstes: alle Dokumente der Akten, nur lesend (Entscheidung 14.10.2026).

Fortlaufend: neue Dokumente zuerst (höhere Priorität), der Altbestand nach und nach, jüngste zuerst. Ausgenommen:

- Dokumente, die EPM selbst erzeugt hat (PDF von Plänen, Berichten, Schreiben – deren Inhalt ist schon strukturiert),
- ausgeblendete Dokumente,
- Akten mit eingeschränkter Verarbeitung (Art. 18 DSGVO) – sie werden nicht gelesen, auch nicht von der KI,
- abgeschlossene Akten (dort ließe sich ohnehin nichts übernehmen),
- Dateiformate, die die Texterkennung nicht liest.

Ein Dokument wird je Fassung (SHA-256) einmal verarbeitet. „Erneut verarbeiten“ setzt einen Vorgang zurück.

Priorisierung (14.11.2026, Administration › KI › Priorisierung, ``KiEinstellung.prio_*``): angefordert > Akte mit
Praxistermin in den nächsten Tagen > neu > neu lesen > Altbestand. Die Konstanten unten sind nur noch die Standardwerte.
„Angefordert“ ist, was mindestens ``prio_angefordert`` hat; alle anderen Stufen liegen darunter (die API prüft das,
``begrenzt`` sichert es zusätzlich ab), damit der Tagesbetrieb mit ``worker_tag = 0`` nur Angefordertes nimmt.
"""
import datetime as dt

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .models import KiEinstellung, KiModellversion, KiVorgang

LESBAR = ("application/pdf", "image/jpeg", "image/png", "image/tiff", "image/webp", "image/bmp", "image/heic",
          "image/heif")
NEU_TAGE = 7
PRIORITAET_NEU = 5
PRIORITAET_ANGEFORDERT = 10
PRIORITAET_TERMIN = 8
PRIORITAET_NEU_LESEN = 3
NEU_LESEN_MAX = 5000


def begrenzt(prioritaet: int, einst: KiEinstellung) -> int:
    """Nicht angeforderte Arbeit bleibt unter der Stufe „angefordert“."""
    return max(0, min(prioritaet, einst.prio_angefordert - 1))


def termin_patienten(einst: KiEinstellung | None = None, tage: int | None = None):
    """Akten mit Praxistermin zwischen heute und heute + ``tage`` (nicht ausgeblendet) – als ``patient_id``-Abfrage."""
    from patienten.models import Termin

    einst = einst or KiEinstellung.laden()
    tage = einst.termin_tage if tage is None else tage
    heute = timezone.localdate()
    bis = heute + dt.timedelta(days=tage)
    return (Termin.objects.filter(art=Termin.Art.PRAXISTERMIN, faellig_am__range=(heute, bis),
                                  ausgeblendet_dauerhaft=False)
            .filter(Q(ausgeblendet_bis__isnull=True) | Q(ausgeblendet_bis__lt=heute))
            .values("patient_id"))


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
    einst = KiEinstellung.laden()
    if altbestand is None:
        altbestand = einst.altbestand_lesen
    grenze = timezone.now() - dt.timedelta(days=einst.neu_tage)
    neu_prio, alt_prio = begrenzt(einst.prio_neu, einst), begrenzt(einst.prio_altbestand, einst)
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
                    prioritaet=neu_prio if dok.hochgeladen_am >= grenze else alt_prio)
                neu += 1
        except IntegrityError:
            continue  # gleichzeitig von einem anderen Worker vorgemerkt
    return neu


def prioritaeten_aktualisieren(einst: KiEinstellung | None = None) -> int:
    """Termin-Vorrang: wartende Vorgänge von Akten mit Praxistermin in den nächsten ``termin_tage`` Tagen auf
    mindestens ``prio_termin`` heben (nie senken, nie bis „angefordert“). Läuft im 10-Minuten-Takt beim Vormerken
    und nach jeder Nachtaufgabe; → Zahl angehobener Vorgänge."""
    einst = einst or KiEinstellung.laden()
    ziel = begrenzt(einst.prio_termin, einst)
    if not einst.termin_tage or ziel <= 0:
        return 0
    return (KiVorgang.objects.filter(status=KiVorgang.Status.NEU, prioritaet__lt=ziel,
                                     patient_id__in=termin_patienten(einst))
            .update(prioritaet=ziel))


def prioritaeten_umstellen(alt_angefordert: int, einst: KiEinstellung) -> int:
    """Nach einer Änderung von ``prio_angefordert``: Wartende so umstellen, dass „angefordert“ weiter genau die
    ausdrücklich angeforderten sind (die übrigen bleiben darunter)."""
    neu = einst.prio_angefordert
    if neu == alt_angefordert:
        return 0
    wartend = KiVorgang.objects.filter(status__in=KiVorgang.WARTEND)
    n = wartend.filter(prioritaet__lt=alt_angefordert, prioritaet__gte=neu).update(prioritaet=max(0, neu - 1))
    return n + wartend.filter(prioritaet__gte=alt_angefordert).update(prioritaet=neu)


def neu_lesen(*, seit_tagen: int | None = 30, dokumenttypen: list | None = None, nur_anderes_modell: bool = True,
              hoechstens: int = 200, vorgaenge: list[int] | None = None, basis=None) -> int:
    """Dokumente mit dem aktiven Modell erneut lesen (Nachtaufgabe ``neu_lesen`` und „Jetzt neu lesen“): wie
    „Erneut verarbeiten“, aber mit der Priorität ``prio_neu_lesen`` – läuft also nachts.

    Ausgenommen: Vorgänge in Arbeit oder ohnehin wartend, übernommene und abgelehnte (dort hat ein Mensch
    entschieden – die gehen nur einzeln über „Erneut verarbeiten“), und was die Queue ohnehin nicht liest
    (ausgeblendete Dokumente, eingeschränkte oder abgeschlossene Akten). ``vorgaenge``: genau diese (statt Filter);
    ``basis``: Ausgangsmenge (die API gibt die Vorgänge der Firma der Person). → Zahl vorgemerkter Vorgänge."""
    from .pipeline import alte_felder_entfernen

    S = KiVorgang.Status
    einst = KiEinstellung.laden()
    qs = (basis if basis is not None else KiVorgang.objects.all()).exclude(
        status__in=[*KiVorgang.IN_ARBEIT, *KiVorgang.WARTEND, S.UEBERNOMMEN, S.ABGELEHNT]).filter(
        dokument__ausgeblendet=False, patient__eingeschraenkt_am__isnull=True, patient__abgeschlossen_am__isnull=True)
    if vorgaenge is not None:
        qs = qs.filter(pk__in=vorgaenge)
    else:
        if seit_tagen:
            qs = qs.filter(dokument__hochgeladen_am__gte=timezone.now() - dt.timedelta(days=seit_tagen))
        if dokumenttypen:
            qs = qs.filter(dokumenttyp__in=dokumenttypen)
        if nur_anderes_modell:
            aktiv = KiModellversion.aktiv("vision")
            qs = qs.exclude(modellversion=aktiv) if aktiv else qs.filter(modellversion__isnull=False)
    hoechstens = max(1, min(int(hoechstens or 1), NEU_LESEN_MAX))
    ids = list(qs.order_by("-dokument__hochgeladen_am", "-id").values_list("id", flat=True)[:hoechstens])
    prio = begrenzt(einst.prio_neu_lesen, einst)
    anzahl = 0
    for vid in ids:
        with transaction.atomic():
            # gesperrt und Status neu gelesen: hat der KI-Dienst ihn inzwischen geholt, bleibt er unberührt
            v = (KiVorgang.objects.select_for_update(skip_locked=True, of=("self",))
                 .filter(pk=vid).exclude(status__in=[*KiVorgang.IN_ARBEIT, *KiVorgang.WARTEND, S.UEBERNOMMEN,
                                                     S.ABGELEHNT]).first())
            if v is None:
                continue
            alte_felder_entfernen(v)
            v.seiten_liste.all().delete()
            v.status, v.prioritaet = S.NEU, prio
            v.versuche, v.fehler, v.schritt, v.fortschritt = 0, "", "", 0
            v.save(update_fields=["status", "prioritaet", "versuche", "fehler", "schritt", "fortschritt"])
            anzahl += 1
    return anzahl


def anfordern(dokument, benutzer) -> KiVorgang:
    """Mitarbeiter fordert die Verarbeitung ausdrücklich an (läuft auch tagsüber, mit Vorrang)."""
    v = KiVorgang.objects.filter(dokument=dokument, sha256=dokument.sha256).first()
    jetzt = timezone.now()
    prio = KiEinstellung.laden().prio_angefordert
    if v is None:
        v = KiVorgang.objects.create(dokument=dokument, patient=dokument.patient, firma_id=dokument.firma_id,
                                     sha256=dokument.sha256, ist_test=dokument.patient.ist_test,
                                     prioritaet=prio, angefordert_von=benutzer, angefordert_am=jetzt)
        return v
    if v.status in (KiVorgang.Status.NEU, KiVorgang.Status.FEHLER, KiVorgang.Status.NACHVERARBEITUNG):
        if v.status == KiVorgang.Status.FEHLER:
            v.status, v.versuche = KiVorgang.Status.NEU, 0
        v.prioritaet, v.angefordert_von, v.angefordert_am = prio, benutzer, jetzt
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
