"""Kennzahlen des Qualitäts-Dashboards aus den Prüfungen und Korrekturen der Mitarbeiter (Auftrag 7).

Gezählt wird je Feld, sobald ein Mensch darüber entschieden hat (übernommen oder verworfen):

- **unverändert richtig**: übernommen ohne Korrektur,
- **korrigiert**: übernommen nach Korrektur (Fehlerart aus der Korrektur),
- **verworfen**: Vorschlag war falsch oder unnötig (Näherung – auch Doppelte werden verworfen).

Genauigkeit = unverändert richtig / entschiedene Felder. OCR-Fehlerrate = Anteil der entschiedenen Felder mit einer
Korrektur „Zeichen falsch gelesen“. Dazu der Verlauf je Monat und der Vergleich je Modell- und Prompt-Fassung.
"""
from collections import Counter, defaultdict

from django.db.models import Count, Exists, OuterRef, Sum
from django.db.models.functions import TruncMonth

from .models import KiFeld, KiKorrektur, KiVorgang

GRUPPEN = {"labor": "Laborwerte", "infusion": "Infusionspläne", "medikation": "Medikation", "diagnose": "Diagnosen",
           "text": "Texte", "dokumenttyp": "Dokumenttyp"}


def _quote(teil, ganz):
    return round(teil / ganz, 3) if ganz else None


def kennzahlen(vorgaenge) -> dict:
    felder = KiFeld.objects.filter(vorgang__in=vorgaenge)
    korrigiert = KiKorrektur.objects.filter(feld=OuterRef("pk"))
    entschieden = (felder.filter(status__in=[KiFeld.Status.UEBERNOMMEN, KiFeld.Status.VERWORFEN])
                   .annotate(hat_korrektur=Exists(korrigiert))
                   .values("gruppe", "schluessel", "status", "hat_korrektur", "vorgang__modellversion__name",
                           "vorgang__prompt_version"))
    je_gruppe = defaultdict(Counter)
    je_modell = defaultdict(Counter)
    for f in entschieden:
        gruppe = "dokumenttyp" if f["schluessel"] == "dokumenttyp" else f["gruppe"]
        if gruppe not in GRUPPEN:
            continue
        art = ("verworfen" if f["status"] == KiFeld.Status.VERWORFEN
               else "korrigiert" if f["hat_korrektur"] else "richtig")
        je_gruppe[gruppe][art] += 1
        modell = f"{f['vorgang__modellversion__name'] or 'nur Regeln'} · {f['vorgang__prompt_version'] or '–'}"
        je_modell[modell][art] += 1
    korrekturen = KiKorrektur.objects.filter(feld__vorgang__in=vorgaenge)
    fehlerarten = Counter(dict(korrekturen.values_list("fehlerart").annotate(n=Count("id"))))
    gesamt = sum(sum(c.values()) for c in je_gruppe.values())
    lesefehler = korrekturen.filter(fehlerart=KiKorrektur.Fehlerart.LESEFEHLER).values("feld").distinct().count()
    verlauf = []
    monate = (korrekturen.annotate(monat=TruncMonth("zeitpunkt")).values("monat").annotate(n=Count("id"))
              .order_by("monat"))
    entschieden_monat = dict(felder.filter(status__in=[KiFeld.Status.UEBERNOMMEN, KiFeld.Status.VERWORFEN])
                             .annotate(monat=TruncMonth("geaendert_am")).values_list("monat")
                             .annotate(n=Count("id")))
    for m in list(monate)[-12:]:
        basis = entschieden_monat.get(m["monat"], 0)
        verlauf.append({"monat": m["monat"].date().isoformat()[:7], "korrekturen": m["n"], "entschieden": basis,
                        "quote": _quote(m["n"], basis)})
    vg = KiVorgang.objects.filter(pk__in=vorgaenge.values("pk"))
    seiten = vg.filter(dauer_s__isnull=False).aggregate(s=Sum("seiten"), d=Sum("dauer_s"))
    return {
        "gruppen": [{"gruppe": g, "name": GRUPPEN[g], **je_gruppe[g], "entschieden": sum(je_gruppe[g].values()),
                     "genauigkeit": _quote(je_gruppe[g]["richtig"], sum(je_gruppe[g].values()))}
                    for g in GRUPPEN],
        "ocr_fehlerrate": _quote(lesefehler, gesamt),
        "korrekturen": sum(fehlerarten.values()),
        "fehlerarten": [{"fehlerart": k, "name": KiKorrektur.Fehlerart(k).label, "anzahl": n}
                        for k, n in fehlerarten.most_common()],
        "verlauf": verlauf,
        "modelle": [{"modell": m, **c, "entschieden": sum(c.values()), "genauigkeit": _quote(c["richtig"],
                                                                                              sum(c.values()))}
                    for m, c in sorted(je_modell.items())],
        "vorgaenge": dict(vg.values_list("status").annotate(n=Count("id"))),
        "sekunden_je_seite": round(seiten["d"] / seiten["s"], 1) if seiten["s"] else None,
    }
