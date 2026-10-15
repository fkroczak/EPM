"""Evaluationsdatensatz und Vergleich von Modellversionen (Auftrag 7).

- ``faelle_erzeugen()``: aus geprüften Vorgängen (übernommen oder teilweise) je ein pseudonymisierter Fall –
  Eingabe ist der OCR-Text, Erwartung sind die vom Mitarbeiter bestätigten Werte (Dokumenttyp, Laborwerte,
  Infusionen, Diagnosen). Seitenbilder werden aus Datenschutzgründen nicht aufgehoben; die Evaluation prüft deshalb
  die Strukturierung aus dem Text, die Lesequalität zeigt das Qualitäts-Dashboard aus den Korrekturen.
- ``lauf_ausfuehren()``: der KI-Dienst lässt das Modell (aktiv oder als Probe geladen) alle Fälle strukturieren und
  vergleicht: Treffer beim Dokumenttyp, Precision/Recall/F1 für Laborwerte und Infusionen, Dauer je Fall.
  Das Ergebnis steht an der Modellversion; ein Admin vergleicht alt und neu und entscheidet über den Wechsel.
"""
import time

from django.utils import timezone

from scans.ocr import auswertung

from . import prompts
from .modell import Client, ModellFehler
from .models import KiEvaluationsfall, KiEvaluationslauf, KiFeld, KiVorgang
from .pruefung import dezimal, planfeld
from .pseudonym import pseudonymisieren


def _labor_schluessel(w: dict) -> tuple:
    name = auswertung.norm(w.get("parameter_name") or w.get("erkannt_als") or w.get("parameter") or "")
    zahl = dezimal(w.get("wert"))
    return name, str(zahl.normalize()) if zahl is not None else (w.get("wert_text") or "").strip().lower()


def _infusion_schluessel(w: dict) -> tuple:
    zahl = dezimal(w.get("menge"))
    return (w.get("planfeld") or planfeld(w.get("substanz") or "") or auswertung.norm(w.get("substanz") or ""),
            str(zahl.normalize()) if zahl is not None else "")


def faelle_erzeugen(limit: int = 500) -> int:
    vorhanden = set(KiEvaluationsfall.objects.exclude(vorgang=None).values_list("vorgang_id", flat=True))
    neu = 0
    for v in (KiVorgang.objects.filter(status__in=[KiVorgang.Status.UEBERNOMMEN, KiVorgang.Status.TEILWEISE])
              .exclude(pk__in=vorhanden).select_related("patient").order_by("-id")[:limit]):
        bestaetigt = [f for f in v.felder.all() if f.status == KiFeld.Status.UEBERNOMMEN]
        if not bestaetigt:
            continue
        typ = next((f.endwert.get("wert") for f in v.felder.all() if f.schluessel == "dokumenttyp"
                    and f.status != KiFeld.Status.VERWORFEN), v.dokumenttyp)
        erwartet = {
            "dokumenttyp": typ,
            "laborwerte": [list(_labor_schluessel(f.endwert)) for f in bestaetigt if f.gruppe == "labor"],
            "infusionen": [list(_infusion_schluessel(f.endwert)) for f in bestaetigt if f.gruppe == "infusion"],
            "diagnosen": sorted({f.endwert.get("icd_code") for f in bestaetigt if f.gruppe == "diagnose"} - {""}),
        }
        KiEvaluationsfall.objects.create(vorgang=v, dokumenttyp=typ or "",
                                         eingabe_text=pseudonymisieren(v.ocr_text, v.patient)[:20000],
                                         erwartet=erwartet)
        neu += 1
    return neu


def _f1(erwartet: set, gefunden: set) -> dict:
    treffer = len(erwartet & gefunden)
    p = treffer / len(gefunden) if gefunden else (1.0 if not erwartet else 0.0)
    r = treffer / len(erwartet) if erwartet else 1.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def lauf_ausfuehren(lauf: KiEvaluationslauf, client: Client, abbrechen=lambda: None) -> KiEvaluationslauf:
    from .pruefung import Katalog

    katalog = Katalog()

    def katalogname(name: str) -> str:
        param, _art = katalog.finden(name or "")
        return param.name if param else (name or "")

    faelle = list(KiEvaluationsfall.objects.all()[:300])
    typ_treffer, dauer = 0, []
    lab_e, lab_g, inf_e, inf_g = set(), set(), set(), set()
    abgebrochen = False
    for i, fall in enumerate(faelle):
        if abbrechen():
            abgebrochen = True
            lauf.fehler = "unterbrochen (Nachtfenster zu Ende oder Pause) – läuft in der nächsten Nacht neu"
            break
        t0 = time.monotonic()
        try:
            e = client.chat(prompts.EXTRAKTION, prompts.extraktion_text(fall.eingabe_text, 1, 1),
                            schema=prompts.EXTRAKTION_SCHEMA, max_tokens=2500).json()
        except ModellFehler as fehler:
            lauf.fehler = str(fehler)[:500]
            continue
        dauer.append(time.monotonic() - t0)
        if e.get("dokumenttyp") == fall.erwartet.get("dokumenttyp"):
            typ_treffer += 1
        lab_e |= {(i, *k) for k in map(tuple, fall.erwartet.get("laborwerte") or [])}
        lab_g |= {(i, *_labor_schluessel({"erkannt_als": katalogname(x.get("parameter")), "wert": x.get("wert")}))
                  for x in e.get("laborwerte") or []}
        inf_e |= {(i, *k) for k in map(tuple, fall.erwartet.get("infusionen") or [])}
        inf_g |= {(i, *_infusion_schluessel(x)) for x in e.get("infusionen") or []}
    n = len(dauer)
    lauf.faelle = n
    lauf.ergebnis = {
        "faelle": n, "dokumenttyp_genauigkeit": round(typ_treffer / n, 3) if n else None,
        "laborwerte": _f1(lab_e, lab_g), "infusionen": _f1(inf_e, inf_g),
        "dauer_s_mittel": round(sum(dauer) / n, 1) if n else None,
        "prompt_version": prompts.PROMPT_VERSION,
    }
    if not abgebrochen:
        lauf.fertig_am = timezone.now()
    lauf.save()
    if lauf.fertig_am and n:
        mv = lauf.modellversion
        mv.evaluation = {**lauf.ergebnis, "lauf": lauf.pk, "am": lauf.fertig_am.isoformat(timespec="seconds")}
        mv.save(update_fields=["evaluation"])
    return lauf
