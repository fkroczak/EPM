"""Zeitliche und inhaltliche Verknüpfung von Laborwerten und Infusionsplänen (Auftrag 4) – regelbasiert, kein Modell.

Beispiel: Kalium 3,1 mmol/l am 12.03. um 06:10, im Infusionsplan ab 12.03. Kalium 20 → 40 mmol
→ „Kalium niedrig (3,1 mmol/l, 12.03.2026 06:10), anschließend Kaliumsubstitution dokumentiert …“.

Regeln:
- Zeitfenster zwischen Laborwert und Maßnahme: ``verknuepfung_stunden`` (Standard 48 h, Administration › KI).
- Maßnahme bei niedrigem Wert: Zugabe neu angesetzt oder Menge erhöht; bei hohem Wert: Menge verringert oder
  abgesetzt. Die Dosisänderung ergibt sich aus der Versionskette der Pläne (``vorgaenger``) bzw. dem vorherigen Plan.
- Folgewert (Wiederholungsmessung) nach der Maßnahme innerhalb von ``FOLGE_TAGE``: normalisiert oder weiterhin
  auffällig. Mehrere Messungen am selben Tag: die erste auffällige löst aus, die weiteren sind Wiederholungen.
- **Gesichert** nur, wenn Laborwert und Plan freigegebene Inhalte der Akte sind, die Reihenfolge eindeutig ist
  (Uhrzeit der Entnahme bekannt oder Plan an einem späteren Tag) und die Dosisänderung belegt ist. Alles andere –
  auch jeder Wert, der nur als KI-Vorschlag vorliegt – ist **wahrscheinlich**.
- Keine Bewertung, keine Empfehlung: die Texte beschreiben nur, was dokumentiert ist.
"""
import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction

from scans.ocr import auswertung

from .models import KiEinstellung, KiFeld, KiHinweis
from .pruefung import PLANFELDER, dezimal

FOLGE_TAGE = 7
TZ = ZoneInfo("Europe/Berlin")
# Stoff im Labor → Feld im Infusionsplan
STOFF_FELD = {stoff: feld for feld, (stoff, _b) in PLANFELDER.items() if stoff}
NAMEN = {"kalium": "Kalium", "natrium": "Natrium", "phosphat": "Phosphat", "calcium": "Calcium",
         "magnesium": "Magnesium", "albumin": "Albumin", "glucose": "Glucose"}
MASSNAHME = {"kalium": "Kaliumsubstitution", "natrium": "Natriumzugabe", "phosphat": "Phosphatsubstitution",
             "calcium": "Calciumsubstitution", "magnesium": "Magnesiumsubstitution", "albumin": "Albumingabe",
             "glucose": "Glucosezufuhr"}
EINHEIT = {"kalium_mmol": "mmol", "natrium_mmol": "mmol", "phosphat_mmol": "mmol", "calcium_mmol": "mmol",
           "magnesium_mmol": "mmol", "albumin_ml": "ml", "glucose_g": "g"}


@dataclass
class Laborereignis:
    stoff: str
    wert: Decimal
    einheit: str
    ref_von: Decimal | None
    ref_bis: Decimal | None
    zeit: dt.datetime
    genau: bool                 # Uhrzeit bekannt
    quelle: str                 # akte | ki
    kennung: int
    lage: str = ""              # niedrig | hoch | normal | ""

    def __post_init__(self):
        if self.ref_von is not None and self.wert < self.ref_von:
            self.lage = "niedrig"
        elif self.ref_bis is not None and self.wert > self.ref_bis:
            self.lage = "hoch"
        elif self.ref_von is not None or self.ref_bis is not None:
            self.lage = "normal"

    def beleg(self) -> dict:
        return {"quelle": self.quelle, "id": self.kennung, "wert": _zahl(self.wert), "einheit": self.einheit,
                "zeit": self.zeit.isoformat(), "uhrzeit_bekannt": self.genau, "lage": self.lage}


@dataclass
class Planereignis:
    feld: str
    menge: Decimal | None
    vorher: Decimal | None
    vorher_bekannt: bool
    zeit: dt.datetime
    genau: bool
    quelle: str                 # akte | ki
    kennung: int
    extra: dict = field(default_factory=dict)

    def beleg(self) -> dict:
        return {"quelle": self.quelle, "id": self.kennung, "feld": self.feld, "menge": _zahl(self.menge),
                "vorher": _zahl(self.vorher), "zeit": self.zeit.isoformat(), **self.extra}


def _zahl(d: Decimal | None) -> str | None:
    if d is None:
        return None
    return format(d.normalize(), "f").replace(".", ",")


def _zeit(datum: dt.date, uhr: dt.time | None) -> dt.datetime:
    return dt.datetime.combine(datum, uhr or dt.time(0, 0), tzinfo=TZ)


def _stoff(name: str) -> str | None:
    n = auswertung.norm(name)
    stoff = auswertung.STOFF.get(n)
    if stoff in STOFF_FELD:
        return stoff
    for s in STOFF_FELD:
        if n == s or n.startswith(s + " "):
            return s
    return None


def laborereignisse(patient) -> list[Laborereignis]:
    from befunde.models import Laborwert

    aus = []
    werte = (Laborwert.objects.filter(befund__patient=patient, wert__isnull=False)
             .select_related("befund", "parameter"))
    for w in werte:
        name = w.parameter.name if w.parameter_id else w.freitext_name
        stoff = _stoff(name)
        if stoff is None:
            continue
        rv = w.referenz_von if w.referenz_von is not None else (w.parameter.referenz_von if w.parameter_id else None)
        rb = w.referenz_bis if w.referenz_bis is not None else (w.parameter.referenz_bis if w.parameter_id else None)
        aus.append(Laborereignis(stoff, w.wert, w.einheit, rv, rb, _zeit(w.befund.abgenommen_am, w.befund.abgenommen_um),
                                 w.befund.abgenommen_um is not None, "akte", w.pk))
    felder = (KiFeld.objects.filter(vorgang__patient=patient, gruppe=KiFeld.Gruppe.LABOR)
              .exclude(status__in=[KiFeld.Status.VERWORFEN, KiFeld.Status.UEBERNOMMEN]).select_related("vorgang"))
    for f in felder:
        w = f.endwert
        stoff = _stoff(w.get("parameter_name") or w.get("erkannt_als") or "")
        zahl = dezimal(w.get("wert"))
        datum = w.get("datum") or (f.vorgang.metadaten or {}).get("dokumentdatum")
        if stoff is None or zahl is None or not datum:
            continue
        try:
            d = dt.date.fromisoformat(str(datum)[:10])
        except ValueError:
            continue
        uhr = None
        if w.get("uhrzeit"):
            try:
                uhr = dt.time.fromisoformat(w["uhrzeit"])
            except ValueError:
                uhr = None
        aus.append(Laborereignis(stoff, zahl, w.get("einheit") or "", dezimal(w.get("referenz_von")),
                                 dezimal(w.get("referenz_bis")), _zeit(d, uhr), uhr is not None, "ki", f.pk))
    aus.sort(key=lambda e: e.zeit)
    return aus


def planereignisse(patient) -> list[Planereignis]:
    from infusionen.models import Infusionsplan

    aus = []
    plaene = list(Infusionsplan.objects.filter(patient=patient)
                  .exclude(status=Infusionsplan.Status.ENTWURF).order_by("gueltig_ab", "id"))
    for i, plan in enumerate(plaene):
        vorher_plan = plan.vorgaenger if plan.vorgaenger_id else (plaene[i - 1] if i else None)
        for feld in STOFF_FELD.values():
            menge = getattr(plan, feld)
            vorher = getattr(vorher_plan, feld) if vorher_plan else None
            if menge == vorher:
                continue
            aus.append(Planereignis(feld, menge, vorher, vorher_plan is not None, _zeit(plan.gueltig_ab, None), False,
                                    "akte", plan.pk, {"gueltig_ab": plan.gueltig_ab.isoformat(),
                                                      "herkunft": plan.herkunft}))
    felder = (KiFeld.objects.filter(vorgang__patient=patient, gruppe=KiFeld.Gruppe.INFUSION)
              .exclude(status__in=[KiFeld.Status.VERWORFEN, KiFeld.Status.UEBERNOMMEN]))
    letzte: dict[str, Decimal | None] = {}
    ki = []
    for f in felder:
        w = f.endwert
        feld = w.get("planfeld")
        if feld not in EINHEIT or not w.get("von"):
            continue
        try:
            d = dt.date.fromisoformat(w["von"])
        except ValueError:
            continue
        uhr = None
        if w.get("uhrzeit"):
            try:
                uhr = dt.time.fromisoformat(w["uhrzeit"])
            except ValueError:
                pass
        ki.append((f, feld, d, uhr, dezimal(w.get("menge"))))
    for f, feld, d, uhr, menge in sorted(ki, key=lambda x: (x[2], x[3] or dt.time(0))):
        vorher = letzte.get(feld)
        aus.append(Planereignis(feld, menge, vorher, feld in letzte, _zeit(d, uhr), uhr is not None, "ki", f.pk,
                                {"substanz": f.endwert.get("substanz")}))
        letzte[feld] = menge
    aus.sort(key=lambda e: e.zeit)
    return aus


def _passend(lage: str, p: Planereignis) -> bool:
    neu = p.menge or Decimal(0)
    alt = p.vorher or Decimal(0)
    if lage == "niedrig":
        return neu > alt
    if lage == "hoch":
        return neu < alt
    return False


def _datum(e) -> str:
    return e.zeit.strftime("%d.%m.%Y %H:%M") if e.genau else e.zeit.strftime("%d.%m.%Y")


def _gesichert(lab: Laborereignis, plan: Planereignis) -> bool:
    if lab.quelle != "akte" or plan.quelle != "akte" or not plan.vorher_bekannt:
        return False
    if plan.zeit.date() > lab.zeit.date():
        return True
    return lab.genau and plan.genau and plan.zeit > lab.zeit


def hinweise_berechnen(labor: list[Laborereignis], plaene: list[Planereignis], stunden: int) -> list[dict]:
    aus = []
    fenster = dt.timedelta(hours=stunden)
    for stoff, feld in STOFF_FELD.items():
        werte = [e for e in labor if e.stoff == stoff]
        massnahmen = [p for p in plaene if p.feld == feld]
        plan_vorhanden = any(p.quelle == "akte" or p.menge for p in plaene)
        name = NAMEN[stoff]
        tage_gesehen = set()
        for i, lab in enumerate(werte):
            if lab.lage not in ("niedrig", "hoch"):
                continue
            tag = (lab.zeit.date(), lab.lage)
            if tag in tage_gesehen:
                continue  # Wiederholungsmessung am selben Tag
            tage_gesehen.add(tag)
            wiederholungen = [w.beleg() for w in werte if w is not lab and w.zeit.date() == lab.zeit.date()]
            # ohne Uhrzeit kann die Maßnahme am selben Tag vor oder nach der Entnahme liegen → ganzer Tag zählt
            beginn = lab.zeit if lab.genau else _zeit(lab.zeit.date(), None)
            ende = (lab.zeit if lab.genau else _zeit(lab.zeit.date() + dt.timedelta(days=1), None)) + fenster
            treffer = [p for p in massnahmen if beginn <= p.zeit <= ende and _passend(lab.lage, p)]
            wort = "niedrig" if lab.lage == "niedrig" else "erhöht"
            lab_text = f"{name} {wort} ({_zahl(lab.wert)} {lab.einheit}, {_datum(lab)})".replace(" ,", ",")
            if treffer:
                p = treffer[0]
                stufe = KiHinweis.Stufe.GESICHERT if _gesichert(lab, p) else KiHinweis.Stufe.WAHRSCHEINLICH
                einheit = EINHEIT[feld]
                aenderung = (f"{_zahl(p.vorher) or '0'} → {_zahl(p.menge) or '0'} {einheit}"
                             if p.vorher_bekannt or p.vorher is not None else f"{_zahl(p.menge) or '0'} {einheit}")
                was = MASSNAHME[stoff] if lab.lage == "niedrig" else f"Verringerung der {name}menge"
                text = (f"{lab_text}, anschließend {was} dokumentiert "
                        f"(Infusionsplan ab {p.zeit.strftime('%d.%m.%Y')}: {aenderung}).")
                belege = {"labor": [lab.beleg()], "plan": [q.beleg() for q in treffer],
                          "wiederholungen": wiederholungen}
                aus.append({"art": KiHinweis.Art.SUBSTITUTION, "stufe": stufe, "parameter": name, "text": text,
                            "zeitpunkt": lab.zeit, "belege": belege,
                            "schluessel": f"substitution:{stoff}:{lab.quelle}:{lab.kennung}"})
                folge = next((w for w in werte[i + 1:] if w.zeit > p.zeit and w.lage
                              and w.zeit <= p.zeit + dt.timedelta(days=FOLGE_TAGE)), None)
                if folge is not None:
                    if folge.lage == "normal":
                        art = KiHinweis.Art.NORMALISIERT
                        text = (f"{name} nach {MASSNAHME[stoff] if lab.lage == 'niedrig' else 'Anpassung'} "
                                f"im Referenzbereich ({_zahl(folge.wert)} {folge.einheit}, {_datum(folge)}).")
                    else:
                        art = KiHinweis.Art.WEITERHIN
                        wort2 = "niedrig" if folge.lage == "niedrig" else "erhöht"
                        text = (f"{name} nach {MASSNAHME[stoff] if lab.lage == 'niedrig' else 'Anpassung'} "
                                f"weiterhin {wort2} ({_zahl(folge.wert)} {folge.einheit}, {_datum(folge)}).")
                    folge_stufe = stufe if folge.quelle == "akte" else KiHinweis.Stufe.WAHRSCHEINLICH
                    aus.append({"art": art, "stufe": folge_stufe, "parameter": name, "text": text.replace(" ,", ","),
                                "zeitpunkt": folge.zeit, "belege": {**belege, "folge": [folge.beleg()]},
                                "schluessel": f"{art}:{stoff}:{lab.quelle}:{lab.kennung}"})
            elif plan_vorhanden and lab.lage == "niedrig":
                vorher = next((w for w in reversed(werte[:i]) if w.zeit.date() < lab.zeit.date() and w.lage), None)
                weiter = "weiterhin " if vorher is not None and vorher.lage == "niedrig" else ""
                text = (f"{name} {weiter}niedrig ({_zahl(lab.wert)} {lab.einheit}, {_datum(lab)}), keine nachfolgende "
                        f"{MASSNAHME[stoff]} im erfassten Zeitraum erkannt.").replace(" ,", ",")
                stufe = (KiHinweis.Stufe.GESICHERT if lab.quelle == "akte"
                         and all(p.quelle == "akte" for p in massnahmen) else KiHinweis.Stufe.WAHRSCHEINLICH)
                aus.append({"art": KiHinweis.Art.KEINE_MASSNAHME, "stufe": stufe, "parameter": name, "text": text,
                            "zeitpunkt": lab.zeit,
                            "belege": {"labor": [lab.beleg()], "plan": [], "wiederholungen": wiederholungen,
                                       "zeitfenster_stunden": stunden},
                            "schluessel": f"keine:{stoff}:{lab.quelle}:{lab.kennung}"})
    return aus


def fuer_patient(patient) -> int:
    """Hinweise eines Patienten neu berechnen; → Zahl der Hinweise. Der Status (gesehen/ausgeblendet) bleibt."""
    stunden = KiEinstellung.laden().verknuepfung_stunden
    neu = hinweise_berechnen(laborereignisse(patient), planereignisse(patient), stunden)
    with transaction.atomic():
        schluessel = set()
        for h in neu:
            schluessel.add(h["schluessel"])
            KiHinweis.objects.update_or_create(
                patient=patient, schluessel=h["schluessel"],
                defaults={k: h[k] for k in ("art", "stufe", "parameter", "text", "zeitpunkt", "belege")})
        KiHinweis.objects.filter(patient=patient).exclude(schluessel__in=schluessel).delete()
    return len(neu)
