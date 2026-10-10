"""Hinweise aus Labor und Gewicht für den Plan-Editor (F187, Wunsch 10.10.2026).

WICHTIG – keine Dosisempfehlung: Diese Hinweise zeigen nur, was in der Akte steht (Laborwerte außerhalb des
Referenzbereichs, Verlauf der letzten Werte, wie sich die eigenen Pläne entwickelt haben, Gewichtsänderung, fehlendes
Labor) – jeweils mit der Bitte, zu prüfen. Sie schlagen nie eine Menge vor und berechnen keine Dosis. Eine Software, die
aus Patientendaten Therapiemengen ableitet, wäre ggf. ein Medizinprodukt nach MDR (Regel 11). Neue Hinweise bitte
ebenso formulieren: „… bitte prüfen“, nie „… auf x erhöhen“.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

# Welche Laborparameter zu welchem Bestandteil des Plans gehören (Namen wie im Katalog, patienten/testdaten.py).
# Hinweise gibt es nur zu Parametern, deren Bestandteil im Plan vorkommt – ein Kupferwert ohne Spurenelemente im
# Plan ist für diesen Plan kein Thema.
BESTANDTEILE: dict[str, dict] = {
    "natrium": {"text": "Natrium", "feld": "natrium_mmol", "parameter": ["Natrium"]},
    "kalium": {"text": "Kalium", "feld": "kalium_mmol", "parameter": ["Kalium"]},
    "phosphat": {"text": "Phosphat", "feld": "phosphat_mmol", "parameter": ["Phosphat"]},
    "calcium": {"text": "Calcium", "feld": "calcium_mmol", "parameter": ["Calcium"]},
    "magnesium": {"text": "Magnesium", "feld": "magnesium_mmol", "parameter": ["Magnesium"]},
    "albumin": {"text": "Humanalbumin", "feld": "albumin_ml", "parameter": ["Albumin"]},
    "glucose": {"text": "Glucose", "feld": "glucose_g", "parameter": ["Glucose"]},
    "lipide": {"text": "Lipide", "feld": "lipide_g", "parameter": ["Triglyceride"]},
    "spurenelemente": {"text": "Spurenelemente", "feld": "spurenelemente", "parameter": ["Kupfer", "Zink", "Selen", "Mangan"]},
    "vitamine": {"text": "Vitamine", "feld": "vitamine", "gruppe": "vitamine"},
}
# Zahlenfelder, deren Entwicklung über die eigenen Pläne gezeigt wird (Statistik der Akte)
VERLAUF_FELDER = [
    ("natrium_mmol", "Natrium", "mmol"), ("kalium_mmol", "Kalium", "mmol"), ("phosphat_mmol", "Phosphat", "mmol"),
    ("calcium_mmol", "Calcium", "mmol"), ("magnesium_mmol", "Magnesium", "mmol"), ("glucose_g", "Glucose", "g"),
    ("aminosaeuren_g", "Aminosäuren", "g"), ("lipide_g", "Lipide", "g"), ("albumin_ml", "Humanalbumin", "ml"),
]


def zahl(wert) -> str:
    """Deutsche Schreibweise ohne überflüssige Nullen: 0.5800 → „0,58“."""
    if wert is None:
        return "—"
    text = f"{Decimal(wert):f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def bestandteile_aus_plan(plan) -> set[str]:
    """Welche Bestandteile im Plan vorkommen (Menge > 0 bzw. Präparat gewählt)."""
    da = set()
    for schluessel, b in BESTANDTEILE.items():
        feld = b["feld"]
        if feld == "vitamine":
            if plan.pk and plan.vitamine.exists():
                da.add(schluessel)
        elif feld == "spurenelemente":
            if plan.spurenelemente_id:
                da.add(schluessel)
        elif getattr(plan, feld) not in (None, 0, Decimal(0)):
            da.add(schluessel)
    return da


def _bezugsplan(patient, plan):
    """Der Plan, seit dem gezählt wird: Vorgänger des Entwurfs bzw. der aktuelle Plan."""
    from .models import Infusionsplan

    if plan is not None and plan.vorgaenger_id:
        return plan.vorgaenger
    return (Infusionsplan.objects.filter(patient=patient, status=Infusionsplan.Status.AKTUELL)
            .order_by("-gueltig_ab", "-id").first())


def _referenz(w):
    von = w.referenz_von if w.referenz_von is not None else (w.parameter.referenz_von if w.parameter_id else None)
    bis = w.referenz_bis if w.referenz_bis is not None else (w.parameter.referenz_bis if w.parameter_id else None)
    return von, bis


def _richtung_ausserhalb(wert, von, bis):
    if wert is None:
        return None
    if von is not None and wert < von:
        return "niedrig"
    if bis is not None and wert > bis:
        return "hoch"
    return None


def _trend(werte):
    """„steigend“, „fallend“ oder „gleichbleibend“ über die (bis zu drei) Werte, älteste zuerst."""
    if len(werte) < 2:
        return None
    schritte = [b - a for a, b in zip(werte, werte[1:])]
    if all(s > 0 for s in schritte):
        return "steigend"
    if all(s < 0 for s in schritte):
        return "fallend"
    if all(s == 0 for s in schritte):
        return "gleichbleibend"
    return "wechselnd"


def labor_hinweise(patient, bestandteile: set[str], seit) -> list[dict]:
    """Je Laborparameter, der zu einem Bestandteil des Plans gehört: der jüngste Wert seit ``seit``, falls außerhalb des
    Referenzbereichs – mit Datum, Referenz, Richtung und dem Verlauf der letzten drei Werte."""
    from befunde.models import Laborwert

    bedingung = Q()
    zuordnung = {}
    for schluessel in bestandteile:
        b = BESTANDTEILE.get(schluessel)
        if not b:
            continue
        if "gruppe" in b:
            bedingung |= Q(parameter__gruppe=b["gruppe"])
        else:
            bedingung |= Q(parameter__name__in=b["parameter"])
            for name in b["parameter"]:
                zuordnung[name] = b["text"]
    if not bedingung:
        return []
    werte = (Laborwert.objects.filter(bedingung, befund__patient=patient, wert__isnull=False)
             .select_related("parameter", "befund").order_by("parameter_id", "-befund__abgenommen_am", "-id"))
    je_parameter: dict[int, list] = {}
    for w in werte:
        je_parameter.setdefault(w.parameter_id, []).append(w)
    ergebnis = []
    for liste in je_parameter.values():
        neuester = liste[0]
        if seit is not None and neuester.befund.abgenommen_am < seit:
            continue
        von, bis = _referenz(neuester)
        richtung = _richtung_ausserhalb(neuester.wert, von, bis)
        if richtung is None:
            continue
        p = neuester.parameter
        letzte = list(reversed(liste[:3]))
        einheit = neuester.einheit or p.einheit
        referenz = (f"{zahl(von)}–{zahl(bis)}" if von is not None and bis is not None
                    else f"ab {zahl(von)}" if von is not None else f"bis {zahl(bis)}")
        text = (f"{p.name} {zahl(neuester.wert)} {einheit} am {neuester.befund.abgenommen_am:%d.%m.%Y} – "
                f"{'unter' if richtung == 'niedrig' else 'über'} dem Referenzbereich ({referenz}). Bitte prüfen.").replace("  ", " ")
        ergebnis.append({
            "art": "labor", "stufe": "warn", "parameter": p.name, "bestandteil": zuordnung.get(p.name, p.get_gruppe_display()),
            "wert": neuester.wert, "einheit": einheit, "am": neuester.befund.abgenommen_am, "referenz_von": von,
            "referenz_bis": bis, "richtung": richtung, "text": text,
            "verlauf": [{"am": w.befund.abgenommen_am, "wert": w.wert} for w in letzte],
            "trend": _trend([w.wert for w in letzte]),
        })
    ergebnis.sort(key=lambda h: h["parameter"])
    return ergebnis


def referenz_fehlt_hinweis(bestandteile: set[str]) -> dict | None:
    """Für Parameter, die zum Plan gehören, steht im Laborkatalog kein Referenzbereich (Entscheidung der Praxis
    10.10.2026, F190): Hinweise aus dem Labor sind dann unvollständig – Befunde ohne eigenen Bereich werden nicht
    bewertet. Die Werte pflegt die Praxis selbst unter Vorlagen › Labor und Diagnosen; EPM trägt keine ein."""
    from stammdaten.models import Laborparameter

    namen, vitamine = [], 0
    for schluessel in sorted(bestandteile, key=lambda k: list(BESTANDTEILE).index(k) if k in BESTANDTEILE else 99):
        b = BESTANDTEILE.get(schluessel)
        if not b:
            continue
        ohne = Laborparameter.objects.filter(aktiv=True, referenz_von__isnull=True, referenz_bis__isnull=True)
        if "gruppe" in b:
            vitamine = ohne.filter(gruppe=b["gruppe"]).count()
        else:
            namen += list(ohne.filter(name__in=b["parameter"]).order_by("reihenfolge", "name").values_list("name", flat=True))
    teile = namen + ([f"{vitamine} Vitamin{'e' if vitamine != 1 else ''}"] if vitamine else [])
    if not teile:
        return None
    liste = ", ".join(teile[:-1]) + (" und " if len(teile) > 1 else "") + teile[-1]
    return {"art": "referenz_fehlt", "stufe": "info", "parameter": namen,
            "text": f"Für {liste} ist kein Referenzbereich hinterlegt – Hinweise aus dem Labor sind deshalb unvollständig "
                    f"(Befunde ohne eigenen Bereich werden nicht bewertet). Bitte prüfen."}


def plan_statistik(patient) -> list[dict]:
    """Wie sich die freigegebenen Pläne der Akte entwickelt haben: ein Bestandteil, der in den letzten drei Plänen
    jeweils erhöht bzw. verringert wurde (nur eine Beobachtung, keine Bewertung)."""
    from .models import Infusionsplan

    plaene = list(Infusionsplan.objects.filter(patient=patient).exclude(status=Infusionsplan.Status.ENTWURF)
                  .order_by("-gueltig_ab", "-id")[:3])
    if len(plaene) < 3:
        return []
    plaene.reverse()
    ergebnis = []
    for feld, text, einheit in VERLAUF_FELDER:
        werte = [getattr(p, feld) for p in plaene]
        if any(w is None for w in werte):
            continue
        trend = _trend(werte)
        if trend not in ("steigend", "fallend"):
            continue
        reihe = " → ".join(zahl(w) for w in werte)
        ergebnis.append({
            "art": "plaene", "stufe": "info", "feld": feld, "trend": trend,
            "text": f"{text} wurde in den letzten 3 Plänen jeweils {'erhöht' if trend == 'steigend' else 'verringert'} "
                    f"({reihe} {einheit}). Zur Einordnung – bitte prüfen, ob das so weitergehen soll.",
        })
    return ergebnis


def gewicht_hinweis(patient, bezug, einstellungen) -> dict | None:
    """Deutliche Gewichtsänderung seit dem Plan, auf den sich der neue bezieht (Grenze: „Warnung Gewichtsverlust“
    der Einstellungen) – damit Mengen je kg und Gesamtvolumen (35 ml/kg) zum aktuellen Gewicht passen."""
    from patienten.models import Gewichtsmessung

    letzte = Gewichtsmessung.objects.filter(patient=patient).order_by("-gemessen_am", "-id").first()
    if letzte is None or bezug is None:
        return None
    vorher = bezug.volumen_gewicht_kg
    if vorher is None:
        m = (Gewichtsmessung.objects.filter(patient=patient, gemessen_am__lte=bezug.gueltig_ab)
             .order_by("-gemessen_am", "-id").first())
        vorher = m.gewicht_kg if m else None
    if not vorher:
        return None
    prozent = (letzte.gewicht_kg - vorher) / vorher * 100
    if abs(prozent) < einstellungen.gewicht_warnung_prozent:
        return None
    richtung = "gestiegen" if prozent > 0 else "gesunken"
    return {
        "art": "gewicht", "stufe": "warn", "vorher_kg": vorher, "jetzt_kg": letzte.gewicht_kg, "am": letzte.gemessen_am,
        "prozent": round(prozent, 1),
        "text": f"Gewicht seit dem Plan vom {bezug.gueltig_ab:%d.%m.%Y} von {zahl(vorher)} auf {zahl(letzte.gewicht_kg)} kg "
                f"{richtung} ({'+' if prozent > 0 else '−'}{zahl(abs(round(prozent, 1)))} %). Mengen je kg und "
                f"Gesamtvolumen bitte prüfen.",
    }


def labor_alt_hinweis(patient, einstellungen) -> dict | None:
    """Kein Laborbefund oder der letzte ist älter als „Laborbefund gilt als alt nach“ (F120)."""
    from befunde.models import Laborbefund
    from vorlagen.models import Anlage

    letzter = Laborbefund.objects.filter(patient=patient).order_by("-abgenommen_am").values_list("abgenommen_am", flat=True).first()
    grenze = timezone.localdate() - timedelta(days=30 * einstellungen.labor_alter_warnung_monate)
    if letzter is not None and letzter >= grenze:
        return None
    anlage = Anlage.objects.filter(mitgeliefert="blutuntersuchung", aktiv=True).values_list("id", flat=True).first()
    text = ("Noch kein Laborbefund in der Akte." if letzter is None
            else f"Laborwerte älter als {einstellungen.labor_alter_warnung_monate} Monate (letzter Befund vom {letzter:%d.%m.%Y}).")
    return {"art": "labor_alt", "stufe": "warn", "letzter": letzter, "anlage": anlage,
            "text": f"{text} Für die Planung bitte aktuelle Werte prüfen bzw. eine Blutuntersuchung anfordern."}


def hinweise(patient, plan=None, bestandteile: set[str] | None = None) -> dict:
    """Alle Hinweise für den Plan-Editor. ``bestandteile``: was im Formular gerade vorkommt (sonst aus ``plan``, sonst
    aus dem aktuellen Plan)."""
    from stammdaten.models import Einstellungen

    e = Einstellungen.aktuell()
    bezug = _bezugsplan(patient, plan)
    if bestandteile is None:
        quelle = plan or bezug
        bestandteile = bestandteile_aus_plan(quelle) if quelle is not None else set()
    # „seit dem letzten Plan“: ab dessen Freigabe (ohne Plan: innerhalb der Frist, ab der Labor als alt gilt)
    if bezug is not None:
        seit = bezug.freigabe_tag or bezug.gueltig_ab
    else:
        seit = timezone.localdate() - timedelta(days=30 * e.labor_alter_warnung_monate)
    liste = []
    alt = labor_alt_hinweis(patient, e)
    if alt:
        liste.append(alt)
    gewicht = gewicht_hinweis(patient, bezug, e)
    if gewicht:
        liste.append(gewicht)
    liste += labor_hinweise(patient, bestandteile, seit)
    liste += plan_statistik(patient)
    fehlt = referenz_fehlt_hinweis(bestandteile)
    if fehlt:
        liste.append(fehlt)
    return {"seit": seit, "bezug": bezug.id if bezug else None, "bestandteile": sorted(bestandteile), "hinweise": liste}
