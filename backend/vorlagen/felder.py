"""Feste Liste der Platzhalter je Vorlagenart (Entwurf 18: „Nur diese Felder sind erlaubt“).

Jedes Feld liefert den Text, wie er auf dem PDF steht (deutsche Schreibweise), oder None, wenn es leer ist.
Felder mit ``html=True`` liefern bereits bereinigtes HTML (Diagnose, Therapie, Bemerkung).
"""
from dataclasses import dataclass
from datetime import date
from typing import Callable

from django.utils import timezone


@dataclass(frozen=True)
class Feld:
    beschreibung: str
    wert: Callable  # (Kontext) -> str | None
    html: bool = False


@dataclass
class Kontext:
    patient: object
    plan: object = None
    heute: date = None

    def __post_init__(self):
        self.heute = self.heute or timezone.localdate()
        self._cache = {}

    def merke(self, schluessel, funktion):
        if schluessel not in self._cache:
            self._cache[schluessel] = funktion()
        return self._cache[schluessel]


def datum(d) -> str | None:
    if d is None:
        return None
    if hasattr(d, "astimezone"):
        d = timezone.localtime(d)
        return d.strftime("%d.%m.%Y, %H:%M Uhr")
    return d.strftime("%d.%m.%Y")


def _zahl(wert, einheit=""):
    from infusionen.models import _zahl as zahl

    return zahl(wert, einheit) if wert is not None else None


def _anzeige(k, schluessel):
    from infusionen.models import _anzeige as anzeige

    return anzeige(k.plan, schluessel) if k.plan is not None else None


def _letztes_gewicht(k):
    return k.merke("gewicht", lambda: k.patient.letzte_messung())


def _hausarzt(k):
    p = k.patient
    z = p.aerzte.filter(aktiv=True, rolle="hausarzt").select_related("arzt").first() if p.pk else None
    if z:
        return str(z.arzt)
    return p.hausarzt or None


def _anschrift(p):
    teile = [p.strasse, f"{p.plz} {p.ort}".strip()]
    return ", ".join(t for t in teile if t) or None


def _trend(k):
    t = k.merke("trend", lambda: k.patient.gewichtstrend())
    if not t:
        return None
    vz = "+" if t["prozent"] > 0 else ""
    return f"{vz}{_zahl(t['prozent'], '%')} seit {datum(t['von'])}".replace("-", "−")


def _absender(k):
    from stammdaten.models import Absenderangaben, Einstellungen

    return k.merke("absender", lambda: Absenderangaben.alle()[Einstellungen.aktuell().absender])


def _person(u):
    if u is None:
        return None
    from epm.api_basis import benutzername

    return benutzername(u)


def _praeparat(feld):
    return lambda k: str(getattr(k.plan, feld)) if k.plan is not None and getattr(k.plan, f"{feld}_id") else None


def _menge(feld, einheit):
    return lambda k: _zahl(getattr(k.plan, feld), einheit) if k.plan is not None else None


def _plan(funktion):
    return lambda k: funktion(k.plan) if k.plan is not None else None


GEMEINSAM = {
    "Patient.Name": Feld("Nachname, Vorname", lambda k: f"{k.patient.nachname}, {k.patient.vorname}"),
    "Patient.Nummer": Feld("Patientennummer", lambda k: str(k.patient.nummer) if k.patient.nummer else None),
    "Patient.Geburtsdatum": Feld("Geburtsdatum", lambda k: datum(k.patient.geburtsdatum)),
    "Versorger.Firma": Feld("Versorger", lambda k: k.patient.versorger.name if k.patient.versorger_id else None),
    "Versorger.Telefon": Feld("Telefon des Versorgers",
                              lambda k: (k.patient.versorger.telefon or None) if k.patient.versorger_id else None),
    "Ansprechpartner.Name": Feld("Ansprechpartner beim Versorger",
                                 lambda k: k.patient.ansprechpartner.name if k.patient.ansprechpartner_id else None),
    "Ansprechpartner.Telefon": Feld("Telefon des Ansprechpartners",
                                    lambda k: (k.patient.ansprechpartner.telefon or None)
                                    if k.patient.ansprechpartner_id else None),
    "Heute": Feld("Datum der Erstellung", lambda k: datum(k.heute)),
    "Absender.Name": Feld("Name des Absenders (Vorlagen › Briefkopf)", lambda k: _absender(k).name or None),
    "Absender.Telefon": Feld("Telefon des Absenders", lambda k: _absender(k).telefon or None),
    "Absender.E-Mail": Feld("E-Mail des Absenders", lambda k: _absender(k).email or None),
    "Absender.Fußzeile": Feld("Fußzeile des Absenders", lambda k: _absender(k).fusszeile or None),
}

INFUSIONSPLAN = {
    **GEMEINSAM,
    "Patient.Gewicht": Feld("Gewicht, mit dem der Plan berechnet ist",
                            lambda k: _zahl(k.plan.volumen_gewicht_kg, "kg") if k.plan is not None
                            and k.plan.volumen_gewicht_kg is not None
                            else (_zahl(_letztes_gewicht(k).gewicht_kg, "kg") if _letztes_gewicht(k) else None)),
    "Plan.gültig_ab": Feld("gültig ab", _plan(lambda p: datum(p.gueltig_ab))),
    "Plan.kcal": Feld("Energie (kcal)", lambda k: _anzeige(k, "kcal")),
    "Plan.ml": Feld("Gesamtvolumen (Gewicht × 35 ml)", _plan(lambda p: _zahl(p.gesamtvolumen_ml, "ml"))),
    "Plan.Stunden": Feld("Laufzeit (h)", _plan(lambda p: _zahl(p.laufzeit_h, "h"))),
    "Plan.Rate": Feld("Rate (ml/h)", _plan(lambda p: _zahl(p.rate_ml_h, "ml/h"))),
    "Plan.Tage_pro_Woche": Feld("Tage pro Woche", _plan(lambda p: _zahl(p.tage_pro_woche, "× pro Woche"))),
    "Plan.Protonenpumpenhemmer": Feld("Protonenpumpenhemmer mit Zeiten", lambda k: _anzeige(k, "pantozol")),
    "Plan.CaMg": Feld("Calcium + Magnesium und Stabilität",
                      _plan(lambda p: None if p.ca_mg_stabil is None else
                            f"{_zahl(p.ca_mg_mmol, 'mmol')} (Grenze {_zahl(p.ca_mg_grenze_mmol, 'mmol')}): "
                            f"{'stabil' if p.ca_mg_stabil else 'instabil'}")),
    "Plan.freigegeben_am": Feld("Freigabe (Datum, Uhrzeit)", _plan(lambda p: datum(p.freigegeben_am))),
    "Plan.freigegeben_von": Feld("Freigegeben von", _plan(lambda p: _person(p.freigegeben_von))),
    "Plan.Bemerkung": Feld("Bemerkung zum Plan", _plan(lambda p: p.bemerkung or None), html=True),
    "Basis.Präparat": Feld("Basislösung", _praeparat("basis_praeparat")),
    "Basis.ml": Feld("Basislösung (ml)", _menge("basis_ml", "ml")),
    "Glucose.Präparat": Feld("Glucose-Präparat", _praeparat("glucose_praeparat")),
    "Glucose.g": Feld("Glucose (g)", _menge("glucose_g", "g")),
    "Amino.Präparat": Feld("Aminosäuren-Präparat", _praeparat("aminosaeuren_praeparat")),
    "Amino.g": Feld("Aminosäuren (g)", _menge("aminosaeuren_g", "g")),
    "Lipide.Präparat": Feld("Lipid-Präparat", _praeparat("lipide_praeparat")),
    "Lipide.g": Feld("Lipide (g)", _menge("lipide_g", "g")),
    "Albumin.Präparat": Feld("Humanalbumin-Präparat", _praeparat("albumin_praeparat")),
    "Albumin.ml": Feld("Humanalbumin (ml)", _menge("albumin_ml", "ml")),
    "Na": Feld("Natrium (mmol)", _menge("natrium_mmol", "mmol")),
    "K": Feld("Kalium (mmol)", _menge("kalium_mmol", "mmol")),
    "PO4": Feld("Phosphat (mmol)", _menge("phosphat_mmol", "mmol")),
    "Ca": Feld("Calcium (mmol)", _menge("calcium_mmol", "mmol")),
    "Mg": Feld("Magnesium (mmol)", _menge("magnesium_mmol", "mmol")),
    "Spurenelemente": Feld("Spurenelemente", _praeparat("spurenelemente")),
    "Vitamine": Feld("Vitamine", lambda k: _anzeige(k, "vitamine")),
    "Katheterblock": Feld("Katheterblock / Medikament", _praeparat("katheterschutz")),
}

PATIENTENDATENBLATT = {
    **GEMEINSAM,
    "Patient.Anschrift": Feld("Anschrift", lambda k: _anschrift(k.patient)),
    "Patient.Telefon": Feld("Telefon", lambda k: k.patient.telefon or None),
    "Patient.E-Mail": Feld("E-Mail", lambda k: k.patient.email or None),
    "Patient.Hausarzt": Feld("Hausarzt", _hausarzt),
    "Patient.Katheter": Feld("Katheter",
                             lambda k: "kein Katheter" if k.patient.kein_katheter
                             else (str(k.patient.katheter) if k.patient.katheter_id else None)),
    "Patient.Nickelallergie": Feld("Nickelallergie", lambda k: k.patient.get_nickelallergie_display()),
    "Patient.Größe": Feld("Größe", lambda k: _zahl(k.patient.groesse_cm, "cm")),
    "Patient.Diagnose": Feld("Diagnose (formatiert)", lambda k: k.patient.diagnose or None, html=True),
    "Patient.Therapie": Feld("Therapie (formatiert)", lambda k: k.patient.therapie or None, html=True),
    "Patient.Empfehlung": Feld("Empfehlung (formatiert)", lambda k: k.patient.empfehlung or None, html=True),
    "Gewicht.aktuell": Feld("letztes Gewicht mit Datum",
                            lambda k: f"{_zahl(_letztes_gewicht(k).gewicht_kg, 'kg')} am {datum(_letztes_gewicht(k).gemessen_am)}"
                            if _letztes_gewicht(k) else None),
    "Gewicht.BMI": Feld("BMI", lambda k: _zahl(k.patient.bmi) if k.patient.bmi is not None else None),
    "Gewicht.Trend": Feld("Veränderung im eingestellten Zeitraum", _trend),
    "Plan.kcal": INFUSIONSPLAN["Plan.kcal"],
    "Plan.ml": INFUSIONSPLAN["Plan.ml"],
    "Plan.Stunden": INFUSIONSPLAN["Plan.Stunden"],
    "Plan.Rate": INFUSIONSPLAN["Plan.Rate"],
    "Plan.gültig_ab": INFUSIONSPLAN["Plan.gültig_ab"],
}

FELDER = {"infusionsplan": INFUSIONSPLAN, "patientendatenblatt": PATIENTENDATENBLATT}

# Tabellen mit festem Aufbau je Art (Spalten stehen fest, damit nichts Falsches gedruckt werden kann)
TABELLEN = {
    "infusionsplan": {
        "zusammensetzung": ("Zusammensetzung (Komponente, Präparat, Menge)", ["Komponente", "Präparat", "Menge"]),
        "positionen": ("Weitere Bestandteile des Plans", ["Präparat", "Menge", "Häufigkeit", "Bemerkung"]),
    },
    "patientendatenblatt": {
        "termine": ("Nächste offene Termine (bis zu 3)", ["Datum", "Art", "Titel", "Ort"]),
    },
}


def tabellenzeilen(art: str, quelle: str, k: Kontext) -> list[list[str]]:
    if quelle == "zusammensetzung":
        if k.plan is None:
            return []
        p = k.plan
        zeilen = [
            ("Basislösung", p.basis_praeparat if p.basis_praeparat_id else None, _zahl(p.basis_ml, "ml")),
            ("Glucose", p.glucose_praeparat if p.glucose_praeparat_id else None, _zahl(p.glucose_g, "g")),
            ("Aminosäuren", p.aminosaeuren_praeparat if p.aminosaeuren_praeparat_id else None, _zahl(p.aminosaeuren_g, "g")),
            ("Lipide", p.lipide_praeparat if p.lipide_praeparat_id else None, _zahl(p.lipide_g, "g")),
            ("Humanalbumin", p.albumin_praeparat if p.albumin_praeparat_id else None, _zahl(p.albumin_ml, "ml")),
        ]
        return [[a, str(b) if b else "—", c or "—"] for a, b, c in zeilen if b or c]
    if quelle == "positionen":
        if k.plan is None or not k.plan.pk:
            return []
        return [[str(x.praeparat), _zahl(x.menge, x.einheit) or "—", x.haeufigkeit or "—", x.bemerkung or "—"]
                for x in k.plan.positionen.select_related("praeparat")]
    if quelle == "termine":
        from patienten.models import Termin

        termine = (Termin.objects.filter(patient=k.patient, erledigt_am__isnull=True, faellig_am__gte=k.heute)
                   .select_related("ort").order_by("faellig_am", "uhrzeit")[:3]) if k.patient.pk else []
        return [[datum(t.faellig_am) + (f", {t.uhrzeit:%H:%M} Uhr" if t.uhrzeit else ""), t.get_art_display(), t.titel,
                 str(t.ort) if t.ort_id else (t.bei or "—")] for t in termine]
    return []
