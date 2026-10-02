"""
Kennzahlen je Patient für Liste und Startseite: letztes Gewicht mit Trend, letzter Kontakt, Hinweise.

Alles wird mit wenigen Abfragen für viele Patienten auf einmal berechnet (ca. 300 Akten).
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from stammdaten.models import Einstellungen

from .models import Gewichtsmessung, Kontakt, Patient, Termin, berechne_trend

TREND_SPANNE = Decimal("1.0")  # unter ±1 % gilt das Gewicht als gleichbleibend (Pfeil →)


def _deutsch(zahl: Decimal) -> str:
    return f"{zahl:+.1f}".replace("-", "−").replace(".", ",")


def woche(heute=None):
    """Montag bis Sonntag der laufenden Kalenderwoche."""
    heute = heute or timezone.localdate()
    montag = heute - timedelta(days=heute.weekday())
    return montag, montag + timedelta(days=6)


def kennzahlen(patienten) -> dict:
    """{patient_id: {gewicht, trend, letzter_kontakt, termin_woche, hinweise, …}}"""
    from infusionen.models import Infusionsplan

    patienten = list(patienten)
    ids = [p.id for p in patienten]
    if not ids:
        return {}
    e = Einstellungen.aktuell()
    heute = timezone.localdate()

    messungen = defaultdict(list)
    for pid, datum, kg in (Gewichtsmessung.objects.filter(patient_id__in=ids)
                           .order_by("patient_id", "gemessen_am", "id")
                           .values_list("patient_id", "gemessen_am", "gewicht_kg")):
        messungen[pid].append((datum, kg))
    kontakte = dict(
        Kontakt.objects.filter(patient_id__in=ids, storniert_am__isnull=True)
        .values("patient_id").annotate(z=Max("zeitpunkt")).values_list("patient_id", "z")
    )
    plaene = dict(
        Infusionsplan.objects.filter(patient_id__in=ids, status=Infusionsplan.Status.AKTUELL)
        .values_list("patient_id", "gueltig_ab")
    )
    montag, sonntag = woche(heute)
    mit_termin = set(
        Termin.objects.filter(patient_id__in=ids, erledigt_am__isnull=True, faellig_am__range=(montag, sonntag))
        .values_list("patient_id", flat=True)
    )
    plan_grenze = heute - timedelta(days=30 * e.plan_alter_warnung_monate)
    kontakt_grenze = timezone.now() - timedelta(days=30 * e.kontakt_ueberfaellig_monate)

    ergebnis = {}
    for p in patienten:
        reihe = messungen.get(p.id, [])
        trend = berechne_trend(reihe, e)
        richtung = None
        if trend:
            richtung = "down" if trend["prozent"] <= -TREND_SPANNE else "up" if trend["prozent"] >= TREND_SPANNE else "flat"
        hinweise = []
        if trend and trend["warnung"]:
            hinweise.append({"art": "gewicht",
                             "text": f"Gewicht {_deutsch(trend['prozent'])} % in {e.gewicht_warnung_monate} Mon."})
        if p.id in plaene and plaene[p.id] < plan_grenze:
            hinweise.append({"art": "plan", "text": f"Plan älter als {e.plan_alter_warnung_monate} Mon."})
        if not p.versorger_id and not p.kein_versorger:  # „kein Versorger“ ist bewusst so erfasst
            hinweise.append({"art": "versorger", "text": "Versorger nicht erfasst"})
        letzter = kontakte.get(p.id)
        if letzter is None or letzter < kontakt_grenze:
            hinweise.append({"art": "kontakt",
                             "text": f"Kein Kontakt seit über {e.kontakt_ueberfaellig_monate} Mon."})
        ergebnis[p.id] = {
            "gewicht": {"kg": reihe[-1][1], "am": reihe[-1][0]} if reihe else None,
            "trend": {"richtung": richtung, "prozent": trend["prozent"], "warnung": trend["warnung"]} if trend else None,
            "letzter_kontakt": letzter,
            "termin_woche": p.id in mit_termin,
            "hinweise": hinweise,
        }
    return ergebnis


def _nur_ids(patienten_qs):
    """Nur die Spalten, die ``kennzahlen`` braucht (ohne select_related der Listenansicht)."""
    return patienten_qs.select_related(None).only("id", "versorger", "kein_versorger")


def schnellfilter(patienten_qs, art: str):
    """IDs für „Nur mit Hinweisen“, „Gewichtsverlust“, „Termin diese Woche“ (Entwurf 3)."""
    werte = kennzahlen(_nur_ids(patienten_qs))
    if art == "hinweise":
        return [pid for pid, k in werte.items() if k["hinweise"]]
    if art == "gewichtsverlust":
        return [pid for pid, k in werte.items() if k["trend"] and k["trend"]["warnung"]]
    if art == "termin_woche":
        return [pid for pid, k in werte.items() if k["termin_woche"]]
    return list(werte)


def zaehler(patienten_qs) -> dict:
    """Zahlen für die Knöpfe der Patientenliste. Testpatienten zählen nicht (außer für Testbenutzer)."""
    offen = patienten_qs.filter(abgeschlossen_am__isnull=True)
    werte = kennzahlen(_nur_ids(offen))
    return {
        "in_betreuung": offen.count(),
        "abgeschlossen": patienten_qs.filter(abgeschlossen_am__isnull=False).count(),
        "mit_hinweisen": sum(1 for k in werte.values() if k["hinweise"]),
        "gewichtsverlust": sum(1 for k in werte.values() if k["trend"] and k["trend"]["warnung"]),
        "termin_woche": sum(1 for k in werte.values() if k["termin_woche"]),
    }


def ohne_pflicht_erklaerungen(patienten_qs) -> list:
    """IDs der Akten, in denen eine der Erklärungen fehlt (oder widerrufen ist), die laut Einstellung vorliegen
    sollen (Vorlagen › Grenzwerte: Datenschutzinformation, Einwilligung, Schweigepflichtentbindung)."""
    from .models import erklaerungen_stand

    pflicht = Einstellungen.aktuell().pflicht_erklaerungen
    ids = list(patienten_qs.values_list("id", flat=True))
    if not pflicht or not ids:
        return []
    stand = erklaerungen_stand(ids)
    return [pid for pid in ids
            if any(stand.get(pid, {}).get(art, {}).get("status") != "liegt_vor" for art in pflicht)]


def abschluss_pruefen(patienten_qs):
    """Akten in Betreuung ohne Kontakt seit der eingestellten Zeit und ohne offenen Termin: Ist die Betreuung
    beendet? Erst mit dem Abschluss beginnt die Aufbewahrungsfrist – eine nie abgeschlossene Akte bliebe für immer."""
    monate = Einstellungen.aktuell().abschluss_pruefen_monate
    grenze = timezone.now() - timedelta(days=30 * monate)
    mit_kontakt = Kontakt.objects.filter(storniert_am__isnull=True, zeitpunkt__gte=grenze).values("patient_id")
    mit_termin = Termin.objects.filter(erledigt_am__isnull=True, faellig_am__gte=timezone.localdate()).values("patient_id")
    return (patienten_qs.filter(abgeschlossen_am__isnull=True, angelegt_am__lt=grenze)
            .exclude(id__in=mit_kontakt).exclude(id__in=mit_termin))


def pruefliste(patienten_qs) -> dict:
    """„Nach und nach prüfen“ auf der Startseite (Entwurf 2)."""
    from .models import Datenschutzanfrage, Dokument

    e = Einstellungen.aktuell()
    offen = patienten_qs.filter(abgeschlossen_am__isnull=True)
    grenze = timezone.now() - timedelta(days=30 * e.kontakt_ueberfaellig_monate)
    mit_kontakt = (Kontakt.objects.filter(patient__in=offen, storniert_am__isnull=True, zeitpunkt__gte=grenze)
                   .values_list("patient_id", flat=True))
    return {
        "altdokumente": Dokument.objects.filter(patient__in=offen, typ_geprueft=False, ausgeblendet=False).count(),
        "nickelallergie_unbekannt": offen.filter(nickelallergie=Patient.Nickelallergie.UNBEKANNT).count(),
        "kein_versorger": offen.filter(versorger__isnull=True, kein_versorger=False).count(),
        "kein_kontakt": offen.exclude(id__in=mit_kontakt).count(),
        "kontakt_monate": e.kontakt_ueberfaellig_monate,
        # Datenschutz: Erklärungen nachhalten wie die Nickelallergie; lange ruhende Akten abschließen
        "erklaerungen_fehlen": len(ohne_pflicht_erklaerungen(offen)),
        "abschluss_pruefen": abschluss_pruefen(offen).count(),
        "abschluss_monate": e.abschluss_pruefen_monate,
        "datenschutz_anfragen": Datenschutzanfrage.objects.filter(patient__in=patienten_qs, erledigt_am__isnull=True).count(),
    }
