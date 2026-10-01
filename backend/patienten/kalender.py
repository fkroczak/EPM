"""
Globaler Kalender (Menüpunkt „Kalender“, Wunsch 02.10.2026): alle Termine und Wiedervorlagen aller Patienten,
dazu berechnete Fälligkeiten – Kontakt fällig (Grenzwert „Kontakt überfällig“) und Infusionsplan prüfen (Grenzwert
„Infusionsplan gilt als alt nach“) – und die gesetzlichen Feiertage.

Feiertage: bundesweit plus Nordrhein-Westfalen (Fronleichnam, Allerheiligen), weil der Sitz der Stiftung in
Altenberge (NRW) liegt. Abgeleitet aus der Anschrift; ein anderes Bundesland wäre eine eigene Festlegung.
"""
from datetime import date, timedelta

from django.db.models import Max
from django.utils import timezone

from stammdaten.models import Einstellungen

FEIERTAGE_LAND = "NW"
MAX_TAGE = 400


def ostersonntag(jahr: int) -> date:
    """Gaußsche Osterformel (anonymer gregorianischer Algorithmus)."""
    a = jahr % 19
    b, c = divmod(jahr, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    monat, tag = divmod(h + l_ - 7 * m + 114, 31)
    return date(jahr, monat, tag + 1)


def feiertage(jahr: int, land: str = FEIERTAGE_LAND) -> list[tuple[date, str]]:
    ostern = ostersonntag(jahr)
    tage = [
        (date(jahr, 1, 1), "Neujahr"),
        (ostern - timedelta(days=2), "Karfreitag"),
        (ostern + timedelta(days=1), "Ostermontag"),
        (date(jahr, 5, 1), "Tag der Arbeit"),
        (ostern + timedelta(days=39), "Christi Himmelfahrt"),
        (ostern + timedelta(days=50), "Pfingstmontag"),
        (date(jahr, 10, 3), "Tag der Deutschen Einheit"),
        (date(jahr, 12, 25), "1. Weihnachtstag"),
        (date(jahr, 12, 26), "2. Weihnachtstag"),
    ]
    if land in ("NW", "BW", "BY", "HE", "RP", "SL"):
        tage.append((ostern + timedelta(days=60), "Fronleichnam"))
    if land in ("NW", "BW", "BY", "RP", "SL"):
        tage.append((date(jahr, 11, 1), "Allerheiligen"))
    return sorted(tage)


def feiertage_zwischen(von: date, bis: date):
    ergebnis = []
    for jahr in range(von.year, bis.year + 1):
        ergebnis += [{"datum": d, "name": n} for d, n in feiertage(jahr) if von <= d <= bis]
    return ergebnis


def faelligkeiten(patienten, bis: date):
    """Berechnete Fälligkeiten bis ``bis`` (auch schon überfällige), je offener Akte höchstens eine je Art."""
    from infusionen.models import Infusionsplan

    from .models import Kontakt

    e = Einstellungen.aktuell()
    heute = timezone.localdate()
    offen = list(patienten.filter(abgeschlossen_am__isnull=True)
                 .only("id", "nachname", "vorname", "nummer", "ist_test", "angelegt_am"))
    ids = [p.id for p in offen]
    letzte = dict(Kontakt.objects.filter(patient_id__in=ids, storniert_am__isnull=True)
                  .values("patient_id").annotate(z=Max("zeitpunkt")).values_list("patient_id", "z"))
    plaene = dict(Infusionsplan.objects.filter(patient_id__in=ids, status=Infusionsplan.Status.AKTUELL)
                  .values_list("patient_id", "gueltig_ab"))
    kontakt_tage = 30 * e.kontakt_ueberfaellig_monate
    plan_tage = 30 * e.plan_alter_warnung_monate
    ergebnis = []
    for p in offen:
        basis = {"patient": p.id, "name": f"{p.nachname}, {p.vorname}", "nummer": p.nummer, "ist_test": p.ist_test}
        letzter = letzte.get(p.id)
        seit = timezone.localdate(letzter) if letzter else timezone.localdate(p.angelegt_am)
        faellig = seit + timedelta(days=kontakt_tage)
        if faellig <= bis:
            ergebnis.append({**basis, "art": "kontakt", "faellig_am": faellig, "seit": seit,
                             "ueberfaellig": faellig < heute,
                             "text": f"Kontakt fällig – letzter Kontakt {seit:%d.%m.%Y}" if letzter
                             else "Kontakt fällig – noch kein Kontakt erfasst"})
        gueltig_ab = plaene.get(p.id)
        if gueltig_ab:
            faellig = gueltig_ab + timedelta(days=plan_tage)
            if faellig <= bis:
                ergebnis.append({**basis, "art": "plan", "faellig_am": faellig, "seit": gueltig_ab,
                                 "ueberfaellig": faellig < heute,
                                 "text": f"Infusionsplan prüfen – gültig seit {gueltig_ab:%d.%m.%Y}"})
    ergebnis.sort(key=lambda x: (x["faellig_am"], x["name"]))
    return ergebnis, {"kontakt_monate": e.kontakt_ueberfaellig_monate, "plan_monate": e.plan_alter_warnung_monate}
