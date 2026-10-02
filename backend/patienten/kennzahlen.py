"""
Kennzahlen je Patient für Liste und Startseite: letztes Gewicht mit Trend, letzter Kontakt, Hinweise.

Alles wird mit wenigen Abfragen für viele Patienten auf einmal berechnet (ca. 300 Akten).
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Max, Q
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


def kontakt_grenzen(e=None):
    """Zeitpunkte, vor denen der letzte Kontakt liegen muss: (bald fällig, überfällig) – S04, zwei Stufen."""
    e = e or Einstellungen.aktuell()
    jetzt = timezone.now()
    return (jetzt - timedelta(days=30 * e.kontakt_bald_monate),
            jetzt - timedelta(days=30 * e.kontakt_ueberfaellig_monate))


def kontaktstufe(letzter, grenzen) -> str | None:
    """„ueberfaellig“, „bald“ oder None. Akten ohne jeden Kontakt gelten als überfällig (wie bisher: sie stehen
    unter „Kein Kontakt“, bis der erste Kontakt erfasst ist)."""
    bald, ueberfaellig = grenzen
    if letzter is None or letzter < ueberfaellig:
        return "ueberfaellig"
    if letzter < bald:
        return "bald"
    return None


def kontakt_text(stufe: str, letzter, e) -> str:
    if letzter is None:
        return "Noch kein Kontakt erfasst"
    if stufe == "ueberfaellig":
        return f"Kontakt überfällig (über {e.kontakt_ueberfaellig_monate} Mon.)"
    return f"Kontakt bald fällig (über {e.kontakt_bald_monate} Mon.)"


def kontakt_filter(patienten_qs, art: str):
    """Patientenliste ``?pruefen=``: kein_kontakt (ab „bald fällig“, beide Stufen), kontakt_bald (nur die erste
    Stufe), kontakt_ueberfaellig, wiedereinbestellung (beide Stufen, aber ohne offenen Termin – Kachel S04)."""
    bald, ueberfaellig = kontakt_grenzen()
    gueltig = Kontakt.objects.filter(storniert_am__isnull=True)
    nach_bald = gueltig.filter(zeitpunkt__gte=bald).values("patient_id")
    nach_ueberfaellig = gueltig.filter(zeitpunkt__gte=ueberfaellig).values("patient_id")
    if art == "kontakt_ueberfaellig":
        return patienten_qs.exclude(id__in=nach_ueberfaellig)
    if art == "kontakt_bald":
        return patienten_qs.exclude(id__in=nach_bald).filter(id__in=nach_ueberfaellig)
    qs = patienten_qs.exclude(id__in=nach_bald)
    if art == "wiedereinbestellung":
        qs = qs.exclude(id__in=Termin.objects.filter(erledigt_am__isnull=True).values("patient_id"))
    return qs


def kennzahlen(patienten, liste: bool = False) -> dict:
    """{patient_id: {gewicht, trend, letzter_kontakt, kontakt_stufe, termin_woche, hinweise, …}}

    ``liste``: zusätzlich die Spalten der breiten Patientenliste (S16): nächster Termin, Infusionsplan, fehlende
    Erklärungen zum Datenschutz."""
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
    grenzen = kontakt_grenzen(e)
    naechste, entwuerfe, erklaerungen = {}, set(), {}
    if liste:
        from .models import erklaerungen_stand

        # nächster offener Termin (überfällige zuerst, dann nach Datum)
        for t in (Termin.objects.filter(patient_id__in=ids, erledigt_am__isnull=True)
                  .order_by("patient_id", "faellig_am", "uhrzeit", "id")
                  .values("patient_id", "id", "art", "faellig_am", "uhrzeit", "titel")):
            naechste.setdefault(t["patient_id"], {k: v for k, v in t.items() if k != "patient_id"})
        entwuerfe = set(Infusionsplan.objects.filter(patient_id__in=ids, status=Infusionsplan.Status.ENTWURF)
                        .values_list("patient_id", flat=True))
        pflicht = e.pflicht_erklaerungen
        stand = erklaerungen_stand(ids) if pflicht else {}
        erklaerungen = {pid: [a for a in pflicht if stand.get(pid, {}).get(a, {}).get("status") != "liegt_vor"]
                        for pid in ids}

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
        stufe = kontaktstufe(letzter, grenzen)
        if stufe:
            hinweise.append({"art": "kontakt", "stufe": stufe, "text": kontakt_text(stufe, letzter, e)})
        ergebnis[p.id] = {
            "gewicht": {"kg": reihe[-1][1], "am": reihe[-1][0]} if reihe else None,
            "trend": {"richtung": richtung, "prozent": trend["prozent"], "warnung": trend["warnung"]} if trend else None,
            "letzter_kontakt": letzter,
            "kontakt_stufe": stufe,
            "termin_woche": p.id in mit_termin,
            "hinweise": hinweise,
        }
        if liste:
            gueltig_ab = plaene.get(p.id)
            ergebnis[p.id].update({
                "naechster_termin": naechste.get(p.id),
                "plan": {"gueltig_ab": gueltig_ab, "alt": gueltig_ab is not None and gueltig_ab < plan_grenze,
                         "entwurf": p.id in entwuerfe} if gueltig_ab or p.id in entwuerfe else None,
                "erklaerungen_fehlen": erklaerungen.get(p.id, []),
            })
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
    # Altdokumente (S09): Fortschritt „312 von 1.140 geprüft“ – alle aus dem Altsystem übernommenen Dokumente (dort
    # ohne geprüften Typ angelegt) und davon die noch offenen
    altdokumente = Dokument.objects.filter(patient__in=offen, ausgeblendet=False)
    return {
        "altdokumente": altdokumente.filter(typ_geprueft=False).count(),
        "altdokumente_gesamt": altdokumente.filter(Q(typ_geprueft=False) | Q(herkunft=Dokument.Herkunft.ALTSYSTEM)).count(),
        "nickelallergie_unbekannt": offen.filter(nickelallergie=Patient.Nickelallergie.UNBEKANNT).count(),
        "kein_versorger": offen.filter(versorger__isnull=True, kein_versorger=False).count(),
        # Kontakt fällig in zwei Stufen (S04); „kein_kontakt“ = beide Stufen zusammen
        "kein_kontakt": kontakt_filter(offen, "kein_kontakt").count(),
        "kontakt_bald": kontakt_filter(offen, "kontakt_bald").count(),
        "kontakt_ueberfaellig": kontakt_filter(offen, "kontakt_ueberfaellig").count(),
        "kontakt_monate": e.kontakt_bald_monate,
        "kontakt_bald_monate": e.kontakt_bald_monate,
        "kontakt_ueberfaellig_monate": e.kontakt_ueberfaellig_monate,
        # Datenschutz: Erklärungen nachhalten wie die Nickelallergie; lange ruhende Akten abschließen
        "erklaerungen_fehlen": len(ohne_pflicht_erklaerungen(offen)),
        "abschluss_pruefen": abschluss_pruefen(offen).count(),
        "abschluss_monate": e.abschluss_pruefen_monate,
        "datenschutz_anfragen": Datenschutzanfrage.objects.filter(patient__in=patienten_qs, erledigt_am__isnull=True).count(),
    }
