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


def _alter(k):
    g = k.patient.geburtsdatum
    if not g:
        return None
    h = k.heute
    return f"{h.year - g.year - ((h.month, h.day) < (g.month, g.day))} J."


def _anschrift(p):
    teile = [p.strasse, f"{p.plz} {p.ort}".strip()]
    return ", ".join(t for t in teile if t) or None


def _trend(k):
    t = k.merke("trend", lambda: k.patient.gewichtstrend())
    if not t:
        return None
    vz = "+" if t["prozent"] > 0 else ""
    return f"{vz}{_zahl(t['prozent'], '%')} seit {datum(t['von'])}".replace("-", "−")


PPI_ANORDNUNG = {
    1: "Pantozol® Kurzinfusion 1 Amp. 40 mg in 50 ml Trägerlösung",
    2: "Nexium® Kurzinfusion 1 Amp. 40 mg in 50 ml Trägerlösung",
    3: "Pantozol® Kurzinfusion 1 Amp. 20 mg in 50 ml Trägerlösung",
}


def _ppi_anordnung(p):
    """Wie auf der alten PDF: Präparat und Schema morgens-mittags-abends, z. B. 1-0-1."""
    text = PPI_ANORDNUNG.get(p.pantozol_stufe)
    if not text:
        return None
    m = p.pantozol_tage or 0
    return f"{text} · {'-'.join('1' if m & bit else '0' for bit in (4, 2, 1))}"


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
    "Patient.Geschlecht": Feld("weiblich / männlich / divers",
                               lambda k: k.patient.get_geschlecht_display() if k.patient.geschlecht else None),
    "Patient.Alter": Feld("Alter in Jahren am Erstellungstag (z. B. 52 J.)", lambda k: _alter(k)),
    "Patient.Anrede": Feld("Frau / Herr (aus dem Geschlecht)",
                           lambda k: {"w": "Frau", "m": "Herr"}.get(k.patient.geschlecht)),
    "Patient.Straße": Feld("Straße", lambda k: k.patient.strasse or None),
    "Patient.PLZ_Ort": Feld("PLZ und Ort", lambda k: f"{k.patient.plz} {k.patient.ort}".strip() or None),
    "Patient.Anschrift": Feld("Anschrift in einer Zeile", lambda k: _anschrift(k.patient)),
    "Patient.Größe": Feld("Größe", lambda k: _zahl(k.patient.groesse_cm, "cm")),
    "Patient.Diagnose": Feld("Diagnose (formatiert)", lambda k: k.patient.diagnose or None, html=True),
    "Absender.Name": Feld("Name des Absenders (Vorlagen › Briefkopf)", lambda k: _absender(k).name or None),
    "Absender.Straße": Feld("Straße des Absenders", lambda k: _absender(k).strasse or None),
    "Absender.PLZ_Ort": Feld("PLZ und Ort des Absenders",
                             lambda k: f"{_absender(k).plz} {_absender(k).ort}".strip() or None),
    "Absender.Fax": Feld("Fax des Absenders", lambda k: _absender(k).fax or None),
    "Absender.Internet": Feld("Internetadresse des Absenders", lambda k: _absender(k).internet or None),
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
    "Plan.ml": Feld("Gesamtvolumen (Mischbeutel + Zusatzvolumen)", _plan(lambda p: _zahl(p.volumen_summe_ml, "ml"))),
    "Plan.Mischbeutel": Feld("Volumen im Mischbeutel (Gewicht × 35 ml)", _plan(lambda p: _zahl(p.gesamtvolumen_ml, "ml"))),
    "Plan.Zusatzvolumen": Feld("Zusatzvolumen (Basislösung)", _plan(lambda p: _zahl(p.basis_ml, "ml"))),
    "Plan.Nummer": Feld("Nummer des Infusionsplans", _plan(lambda p: str(p.pk) if p.pk else None)),
    "Plan.erstellt_von": Feld("Erstellt von", _plan(lambda p: _person(p.erstellt_von))),
    "Plan.erstellt_am": Feld("Erstellt am (Datum)",
                             _plan(lambda p: datum(timezone.localtime(p.erstellt_am).date()) if p.erstellt_am else None)),
    # Tag, an dem der Mediziner freigegeben hat (bei Freigabe außerhalb von EPM das dabei angegebene Datum)
    "Plan.freigegeben_datum": Feld("Freigabe durch den Mediziner (nur Datum)", _plan(lambda p: datum(p.freigabe_tag))),
    "Plan.Freigabevermerk": Feld("Freigabevermerk: wer freigegeben hat, wann und auf welchem Weg; wer abgeschlossen hat",
                                 _plan(lambda p: p.freigabevermerk)),
    "Plan.Freigabeweg": Feld("Weg der Freigabe (im System, per E-Mail, telefonisch …)",
                             _plan(lambda p: p.get_freigabe_weg_display() if p.freigabe_weg else None)),
    "Plan.abgeschlossen_von": Feld("Im System abgeschlossen von (leer, wenn der Mediziner selbst freigegeben hat)",
                                   _plan(lambda p: _person(p.abgeschlossen_von) if p.abgeschlossen_von_id else None)),
    "Plan.Stunden": Feld("Laufzeit (h)", _plan(lambda p: _zahl(p.laufzeit_h, "h"))),
    "Plan.Rate": Feld("Rate (ml/h)", _plan(lambda p: _zahl(p.rate_ml_h, "ml/h"))),
    "Plan.Tage_pro_Woche": Feld("Tage pro Woche", _plan(lambda p: _zahl(p.tage_pro_woche, "× pro Woche"))),
    "Plan.Protonenpumpenhemmer": Feld("Protonenpumpenhemmer mit Zeiten", lambda k: _anzeige(k, "pantozol")),
    "Plan.Protonenpumpenhemmer_Anordnung": Feld("Protonenpumpenhemmer wie auf der alten PDF (… in 50 ml Trägerlösung · 1-0-1)",
                                                _plan(lambda p: _ppi_anordnung(p))),
    "Plan.CaMg": Feld("Calcium + Magnesium und Stabilität",
                      _plan(lambda p: None if p.ca_mg_stabil is None else
                            f"{_zahl(p.ca_mg_mmol, 'mmol')} (Grenze {_zahl(p.ca_mg_grenze_mmol, 'mmol')}): "
                            f"{'stabil' if p.ca_mg_stabil else 'instabil'}")),
    "Plan.freigegeben_am": Feld("Freigabe (Datum, Uhrzeit; bei Freigabe außerhalb von EPM nur das Datum)",
                                _plan(lambda p: datum(p.freigabe_datum) if p.abgeschlossen_von_id else datum(p.freigegeben_am))),
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
    "Patient.Telefon": Feld("Telefon", lambda k: k.patient.telefon or None),
    "Patient.E-Mail": Feld("E-Mail", lambda k: k.patient.email or None),
    "Patient.Hausarzt": Feld("Hausarzt", _hausarzt),
    "Patient.Katheter": Feld("Katheter",
                             lambda k: "kein Katheter" if k.patient.kein_katheter
                             else (str(k.patient.katheter) if k.patient.katheter_id else None)),
    "Patient.Nickelallergie": Feld("Nickelallergie", lambda k: k.patient.get_nickelallergie_display()),
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

def _auskunft_personen(k):
    p = k.patient
    if not p.pk:
        return None
    personen = p.bezugspersonen.filter(aktiv=True, auskunft_erlaubt=True).select_related("beziehung")
    return ", ".join(f"{b.name} ({b.beziehung.wert})" if b.beziehung_id else b.name for b in personen) or None


def _aufbewahrung_jahre(k):
    from stammdaten.models import Einstellungen

    return str(Einstellungen.aktuell().aufbewahrung_jahre)


# Erklärungen zum Datenschutz: Angaben zur Person und zu den Stellen, an die Daten gehen
ERKLAERUNG = {
    **{name: feld for name, feld in GEMEINSAM.items() if name != "Patient.Diagnose"},
    "Patient.Telefon": PATIENTENDATENBLATT["Patient.Telefon"],
    "Patient.E-Mail": PATIENTENDATENBLATT["Patient.E-Mail"],
    "Patient.Hausarzt": PATIENTENDATENBLATT["Patient.Hausarzt"],
    "Patient.Krankenkasse": Feld("Krankenkasse", lambda k: k.patient.krankenkasse or None),
    "Bezugspersonen.Auskunft": Feld("Bezugspersonen, denen Auskunft gegeben werden darf", _auskunft_personen),
    "Aufbewahrung.Jahre": Feld("Aufbewahrung nach Abschluss der Akte in Jahren (Vorlagen › Grenzwerte)",
                               _aufbewahrung_jahre),
}

FELDER = {"infusionsplan": INFUSIONSPLAN, "patientendatenblatt": PATIENTENDATENBLATT,
          "datenschutzinformation": ERKLAERUNG, "einwilligung": ERKLAERUNG, "schweigepflichtentbindung": ERKLAERUNG}

# Tabellen mit festem Aufbau je Art (Spalten stehen fest, damit nichts Falsches gedruckt werden kann).
# (Name, Spalten, Ausrichtung je Spalte): "zahl" rechtsbündig, "einheit" schmal und grau – wie im Laborbefund.
TABELLEN = {
    "infusionsplan": {
        "zusammensetzung": ("Zusammensetzung (Bestandteil, Menge, Einheit, Präparat)",
                            ["Bestandteil", "Menge", "Einheit", "Präparat"], ["", "zahl", "einheit", ""]),
        "positionen": ("Weitere Bestandteile des Plans", ["Präparat", "Menge", "Einheit", "Häufigkeit", "Bemerkung"],
                       ["", "zahl", "einheit", "", ""]),
        "bilanz": ("Laufzeit und Volumen (Mischbeutel, Zusatzlösung, Gesamt)",
                   ["", "Mischbeutel", "Zusatzlösung", "Gesamt", ""], ["", "zahl", "zahl", "zahl", "einheit"]),
    },
    "patientendatenblatt": {
        "termine": ("Nächste offene Termine (bis zu 3)", ["Datum", "Art", "Titel", "Ort"], ["", "", "", ""]),
    },
    "datenschutzinformation": {}, "einwilligung": {}, "schweigepflichtentbindung": {},
}


class Fett(str):
    """Zelle, die fett gedruckt wird (z. B. Gesamtwerte)."""


def tabellenspalten(art: str, quelle: str, k: Kontext) -> list[str]:
    spalten = list(TABELLEN[art][quelle][1])
    if quelle == "bilanz" and k.plan is not None and k.plan.basis_praeparat_id:
        spalten[2] = f"Zusatzlösung · {k.plan.basis_praeparat}"
    return spalten


def _zahl_ohne(wert):
    """Zahl ohne Einheit, 0 und leer als „—“ (viele Altpläne haben keine Laufzeit)."""
    return _zahl(wert) if wert else "—"


def tabellenzeilen(art: str, quelle: str, k: Kontext) -> list[list[str]]:
    if quelle == "zusammensetzung":
        if k.plan is None:
            return []
        p = k.plan
        zeilen = [
            ("Basislösung", p.basis_praeparat if p.basis_praeparat_id else None, p.basis_ml, "ml"),
            ("Glucose", p.glucose_praeparat if p.glucose_praeparat_id else None, p.glucose_g, "g"),
            ("Aminosäuren", p.aminosaeuren_praeparat if p.aminosaeuren_praeparat_id else None, p.aminosaeuren_g, "g"),
            ("Lipide", p.lipide_praeparat if p.lipide_praeparat_id else None, p.lipide_g, "g"),
            ("Humanalbumin", p.albumin_praeparat if p.albumin_praeparat_id else None, p.albumin_ml, "ml"),
        ]
        return [[a, _zahl(c) if c is not None else "—", e if c is not None else "", str(b) if b else "—"]
                for a, b, c, e in zeilen if b or c is not None]
    if quelle == "positionen":
        if k.plan is None or not k.plan.pk:
            return []
        return [[str(x.praeparat), _zahl(x.menge) if x.menge is not None else "—", x.einheit if x.menge is not None else "",
                 x.haeufigkeit or "—", x.bemerkung or "—"]
                for x in k.plan.positionen.select_related("praeparat")]
    if quelle == "bilanz":
        if k.plan is None:
            return []
        p = k.plan
        kcal = _zahl(p.kcal) if p.kcal else "—"
        laufzeit, rate = _zahl_ohne(p.laufzeit_h), _zahl_ohne(p.rate_ml_h)
        return [
            ["Kalorien", kcal, "—", Fett(kcal), "kcal"],
            ["Volumen", _zahl_ohne(p.gesamtvolumen_ml), _zahl_ohne(p.basis_ml), Fett(_zahl_ohne(p.volumen_summe_ml)), "ml"],
            ["Laufzeit", "", "", laufzeit, "h" if laufzeit != "—" else ""],
            ["Laufmenge je Stunde", "", "", rate, "ml/h" if rate != "—" else ""],
        ]
    if quelle == "termine":
        from patienten.models import Termin

        termine = (Termin.objects.filter(patient=k.patient, erledigt_am__isnull=True, faellig_am__gte=k.heute)
                   .select_related("ort").order_by("faellig_am", "uhrzeit")[:3]) if k.patient.pk else []
        return [[datum(t.faellig_am) + (f", {t.uhrzeit:%H:%M} Uhr" if t.uhrzeit else ""), t.get_art_display(), t.titel,
                 str(t.ort) if t.ort_id else (t.bei or "—")] for t in termine]
    return []
