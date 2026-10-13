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
    # Wünsche aus der Praxis vom 06.10.2026: Bericht (F115) und Sprechstundenblatt (F116). Beim
    # Sprechstundenblatt werden ``plan``, ``labor`` und ``bia`` mit dem jeweils aktuellsten Stand gefüllt.
    bericht: object = None
    labor: object = None
    bia: object = None
    # Schreiben aus der Akte (Vorlagen von Alice, 09.10.2026, F172): Termin der Terminbestätigung; bei der
    # Patientenankündigung (ohne Patient) der Zeitraum, der Terminort und die Termine darin
    termin: object = None
    zeitraum: tuple = None
    terminort: object = None
    termine: list = None
    benutzer: object = None

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


def _diagnosen(k):
    """Aktive Diagnosen der Akte, eine je Zeile: „Kurzdarmsyndrom [K91.2G]“ (F117)."""
    if not k.patient.pk:
        return None
    eintraege = k.merke("diagnosen", lambda: list(k.patient.diagnosen.filter(aktiv=True)))
    return "\n".join(d.anzeige for d in eintraege) or None


def _absender(k):
    from stammdaten.models import Absenderangaben, Einstellungen

    return k.merke("absender", lambda: Absenderangaben.aktuelle())


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
    "Patient.Diagnosen": Feld("Diagnoseliste mit ICD-Code, eine je Zeile (z. B. Kurzdarmsyndrom [K91.2G])",
                              lambda k: _diagnosen(k)),
    "Patient.Versicherungsart": Feld("GKV / PKV / Selbstzahler",
                                     lambda k: k.patient.get_versicherungsart_display()
                                     if k.patient.versicherungsart else None),
    "Patient.Versicherung": Feld("Name der Versicherung", lambda k: k.patient.krankenkasse or None),
    "Patient.Versichertennummer": Feld("Versichertennummer", lambda k: k.patient.versichertennummer or None),
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

def _je_geschlecht(weiblich, maennlich, sonst):
    return lambda k: {"w": weiblich, "m": maennlich}.get(k.patient.geschlecht, sonst)


WOCHENTAGE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


def tag_lang(d) -> str | None:
    """„Montag, 17.08.2026“"""
    return f"{WOCHENTAGE[d.weekday()]}, {d:%d.%m.%Y}" if d else None


def _termin(funktion):
    return lambda k: funktion(k.termin) if k.termin is not None else None


# Anschreiben an Patienten (F172): Anrede und die Wörter, die vom Geschlecht abhängen (Reisebescheinigung)
ANSCHREIBEN = {
    "Patient.Vorname_Name": Feld("Vorname Nachname", lambda k: f"{k.patient.vorname} {k.patient.nachname}".strip()),
    "Patient.Briefanrede": Feld("Sehr geehrte Frau … / Sehr geehrter Herr … / Guten Tag Vorname Nachname",
                                lambda k: {"w": f"Sehr geehrte Frau {k.patient.nachname}",
                                           "m": f"Sehr geehrter Herr {k.patient.nachname}"}.get(
                                    k.patient.geschlecht, f"Guten Tag {k.patient.vorname} {k.patient.nachname}")),
    "Patient.E-Mail": Feld("E-Mail", lambda k: k.patient.email or None),
    "Patient.Telefon": Feld("Telefon", lambda k: k.patient.telefon or None),
    "Patient.der_Patientin": Feld("der Patientin / des Patienten",
                                  _je_geschlecht("der Patientin", "des Patienten", "der Patientin bzw. des Patienten")),
    "Patient.die_Patientin": Feld("die Patientin / der Patient",
                                  _je_geschlecht("die Patientin", "der Patient", "die Patientin bzw. der Patient")),
    "Patient.ihre": Feld("ihre / seine", _je_geschlecht("ihre", "seine", "ihre bzw. seine")),
    "Patient.ihrer": Feld("ihrer / seiner", _je_geschlecht("ihrer", "seiner", "ihrer bzw. seiner")),
    "Patient.Mrs": Feld("englische Anrede: Mrs. / Mr. (leer bei divers)", _je_geschlecht("Mrs.", "Mr.", None)),
    "Patient.her": Feld("englisch: her / his / their", _je_geschlecht("her", "his", "their")),
    "Benutzer.Name": Feld("wer das Schreiben erstellt (angemeldete Person)", lambda k: _person(k.benutzer)),
}

TERMIN = {
    "Termin.Datum": Feld("Tag des Termins mit Wochentag (Montag, 17.08.2026)", _termin(lambda t: tag_lang(t.faellig_am))),
    "Termin.Uhrzeit": Feld("Uhrzeit des Termins (14:30 Uhr)",
                           _termin(lambda t: f"{t.uhrzeit:%H:%M} Uhr" if t.uhrzeit else None)),
    "Termin.Ort": Feld("Terminort", _termin(lambda t: str(t.ort) if t.ort_id else None)),
    "Termin.bei": Feld("bei/Ort (Freitext) des Termins", _termin(lambda t: t.bei or None)),
    "Termin.Titel": Feld("Titel des Termins", _termin(lambda t: t.titel or None)),
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
    "Plan.Tage_pro_Woche": Feld("PE (Mischbeutel): Tage pro Woche",
                                _plan(lambda p: _zahl(p.tage_pro_woche, "× pro Woche"))),
    "Plan.Zusatz_pro_Woche": Feld("Zusatzvolumen („Elektrolytbeutel“): Tage pro Woche",
                                  _plan(lambda p: _zahl(p.zusatz_tage_pro_woche, "× pro Woche"))),
    "Plan.Infusionsfreie_Tage": Feld("Infusionsfreie Tage pro Woche („keine“ bei 0)",
                                     lambda k: _anzeige(k, "freie_tage_pro_woche")),
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

def _bericht(funktion):
    return lambda k: funktion(k.bericht) if k.bericht is not None else None


# Bericht aus der Akte (F115)
BERICHT = {
    **GEMEINSAM,
    "Patient.Telefon": PATIENTENDATENBLATT["Patient.Telefon"],
    "Patient.Hausarzt": PATIENTENDATENBLATT["Patient.Hausarzt"],
    "Bericht.Titel": Feld("Titel des Berichts", _bericht(lambda b: b.titel or None)),
    "Bericht.Art": Feld("Berichtsart", _bericht(lambda b: str(b.art) if b.art_id else None)),
    "Bericht.Datum": Feld("Datum des Berichts", _bericht(lambda b: datum(b.datum))),
    "Bericht.Empfänger": Feld("Empfänger", _bericht(lambda b: b.empfaenger or None)),
    "Bericht.Inhalt": Feld("Inhalt des Berichts (formatiert)", _bericht(lambda b: b.inhalt or None), html=True),
    "Bericht.erstellt_von": Feld("Erstellt von", _bericht(lambda b: _person(b.erstellt_von))),
    "Bericht.Freigabevermerk": Feld("Freigabevermerk: wer freigegeben hat und wann",
                                    _bericht(lambda b: b.freigabevermerk)),
}


def _labor(funktion):
    return lambda k: funktion(k.labor) if k.labor is not None else None


def _bia(funktion):
    return lambda k: funktion(k.bia) if k.bia is not None else None


# Unterlagen für die Sprechstunde (F116): der jeweils aktuellste Stand aller Bereiche auf einem Blatt
SPRECHSTUNDE = {
    **GEMEINSAM,
    "Patient.Telefon": PATIENTENDATENBLATT["Patient.Telefon"],
    "Patient.Hausarzt": PATIENTENDATENBLATT["Patient.Hausarzt"],
    "Patient.Katheter": PATIENTENDATENBLATT["Patient.Katheter"],
    "Patient.Nickelallergie": PATIENTENDATENBLATT["Patient.Nickelallergie"],
    "Patient.Therapie": PATIENTENDATENBLATT["Patient.Therapie"],
    "Patient.Empfehlung": PATIENTENDATENBLATT["Patient.Empfehlung"],
    "Gewicht.aktuell": PATIENTENDATENBLATT["Gewicht.aktuell"],
    "Gewicht.BMI": PATIENTENDATENBLATT["Gewicht.BMI"],
    "Gewicht.Trend": PATIENTENDATENBLATT["Gewicht.Trend"],
    "Plan.gültig_ab": INFUSIONSPLAN["Plan.gültig_ab"],
    "Plan.kcal": INFUSIONSPLAN["Plan.kcal"],
    "Plan.ml": INFUSIONSPLAN["Plan.ml"],
    "Plan.Stunden": INFUSIONSPLAN["Plan.Stunden"],
    "Plan.Rate": INFUSIONSPLAN["Plan.Rate"],
    "Plan.Tage_pro_Woche": INFUSIONSPLAN["Plan.Tage_pro_Woche"],
    "Plan.Zusatz_pro_Woche": INFUSIONSPLAN["Plan.Zusatz_pro_Woche"],
    "Plan.Infusionsfreie_Tage": INFUSIONSPLAN["Plan.Infusionsfreie_Tage"],
    "Plan.Protonenpumpenhemmer_Anordnung": INFUSIONSPLAN["Plan.Protonenpumpenhemmer_Anordnung"],
    "Plan.Bemerkung": INFUSIONSPLAN["Plan.Bemerkung"],
    "Spurenelemente": INFUSIONSPLAN["Spurenelemente"],
    "Vitamine": INFUSIONSPLAN["Vitamine"],
    "Katheterblock": INFUSIONSPLAN["Katheterblock"],
    "Labor.Datum": Feld("Abnahmedatum des letzten Laborbefunds", _labor(lambda b: datum(b.abgenommen_am))),
    "Labor.Labor": Feld("Labor des letzten Befunds", _labor(lambda b: b.labor or None)),
    "Labor.Beurteilung": Feld("Beurteilung des letzten Laborbefunds (formatiert)",
                              _labor(lambda b: b.beurteilung or None), html=True),
    "BIA.Datum": Feld("Datum der letzten BIA-Messung", _bia(lambda b: datum(b.gemessen_am))),
    "BIA.Gewicht": Feld("BIA: Gewicht", _bia(lambda b: _zahl(b.gewicht_kg, "kg"))),
    "BIA.BCM": Feld("BIA: BCM", _bia(lambda b: _zahl(b.bcm_kg, "kg"))),
    "BIA.Fettmasse": Feld("BIA: Fettmasse", _bia(lambda b: _zahl(b.fettmasse_kg, "kg"))),
    "BIA.ECW": Feld("BIA: extrazelluläres Wasser", _bia(lambda b: _zahl(b.ecw_prozent, "%"))),
    "BIA.Körperwasser": Feld("BIA: Körperwasser", _bia(lambda b: _zahl(b.koerperwasser_l, "l"))),
    "BIA.BMI": Feld("BIA: BMI", _bia(lambda b: _zahl(b.bmi))),
    "BIA.Beurteilung": Feld("Beurteilung der letzten BIA-Messung (formatiert)",
                            _bia(lambda b: b.beurteilung or None), html=True),
}

def _medikamente(k, bedarf: bool):
    """Aktuelle Medikamente der Akte (Wunsch 11.10.2026): Dauer- bzw. Bedarfsmedikation in der Reihenfolge des Plans."""
    if not k.patient.pk:
        return []
    alle = k.merke("medikamente", lambda: list(k.patient.medikamente.filter(aktiv=True)
                                                .order_by("reihenfolge", "wirkstoff", "id")))
    return [m for m in alle if m.bedarf == bedarf]


# Medikationsplan (Wunsch 11.10.2026): Patient, Absender und die Medikamente als Tabellen
MEDIKATIONSPLAN = {
    **GEMEINSAM,
    "Patient.Hausarzt": PATIENTENDATENBLATT["Patient.Hausarzt"],
    "Patient.Nickelallergie": PATIENTENDATENBLATT["Patient.Nickelallergie"],
    "Gewicht.aktuell": PATIENTENDATENBLATT["Gewicht.aktuell"],
    "Medikamente.Anzahl": Feld("Zahl der aktuellen Medikamente (Dauer- und Bedarfsmedikation)",
                               lambda k: str(len(_medikamente(k, False)) + len(_medikamente(k, True)))),
}

# Schreiben aus der Akte (F172)
PATIENTENAUFNAHME = {**GEMEINSAM, **ANSCHREIBEN}
TERMINBESTAETIGUNG = {**GEMEINSAM, **ANSCHREIBEN, **TERMIN}
REISEBESCHEINIGUNG = {**GEMEINSAM, **ANSCHREIBEN, "Patient.Diagnosen": GEMEINSAM["Patient.Diagnosen"]}

# Patientenankündigung (F173): ohne Patient – Absender, Datum, Zeitraum und Terminort
ANKUENDIGUNG = {
    **{name: feld for name, feld in GEMEINSAM.items() if name.startswith("Absender.") or name == "Heute"},
    "Zeitraum.von": Feld("erster Tag (Montag, 17.08.2026)", lambda k: tag_lang(k.zeitraum[0]) if k.zeitraum else None),
    "Zeitraum.bis": Feld("letzter Tag (Mittwoch, 19.08.2026)", lambda k: tag_lang(k.zeitraum[1]) if k.zeitraum else None),
    "Zeitraum": Feld("Zeitraum (17.08.2026 bis 19.08.2026, an einem Tag nur das Datum)",
                     lambda k: None if not k.zeitraum else datum(k.zeitraum[0]) if k.zeitraum[0] == k.zeitraum[1]
                     else f"{datum(k.zeitraum[0])} bis {datum(k.zeitraum[1])}"),
    "Terminort": Feld("gewählter Terminort", lambda k: str(k.terminort) if k.terminort is not None else None),
    "Anzahl": Feld("Zahl der angekündigten Termine", lambda k: str(len(k.termine or []))),
    "Termine.Liste": Feld("Termine als Text, nach Tagen geordnet (für die E-Mail)", lambda k: termine_als_text(k)),
    "Benutzer.Name": ANSCHREIBEN["Benutzer.Name"],
}

# Eigene Schreiben (F176): unter Vorlagen › Dokumentvorlagen angelegt, Kennung „eigen-…“. Sie haben alle dieselben
# Datenfelder: Patient, Anrede, Absender und – wenn beim Erzeugen ein Termin gewählt ist – den Termin.
EIGEN_PRAEFIX = "eigen-"
EIGEN = {**GEMEINSAM, **ANSCHREIBEN, **TERMIN}


def ist_eigen(art) -> bool:
    return isinstance(art, str) and art.startswith(EIGEN_PRAEFIX) and len(art) > len(EIGEN_PRAEFIX)


class JeArt(dict):
    """Wert je Vorlagenart; eigene Schreiben teilen sich einen Wert (``eigen``)."""

    def __init__(self, werte, eigen):
        super().__init__(werte)
        self.eigen = eigen

    def __missing__(self, art):
        if ist_eigen(art):
            return self.eigen() if callable(self.eigen) else self.eigen
        raise KeyError(art)

    def __contains__(self, art):
        return super().__contains__(art) or ist_eigen(art)


# Patientenerklärungen der Regeneration Clinic (Vorlagen 01–12, Oktober 2026): Angaben zur Person wie die Erklärungen
RGC_ARTEN = ("rgc_erklaerung_at", "rgc_erklaerung_gkv", "rgc_erklaerung_bguv", "rgc_erklaerung_pkv",
             "rgc_erklaerung_zusatz", "rgc_schweigepflicht", "rgc_aufklaerung_op", "rgc_aufklaerung_anaesthesie",
             "rgc_vereinbarung_oegk", "rgc_abtretung_oegk", "rgc_anlage_k", "rgc_anwaltsvollmacht")
RGC_ERKLAERUNG = {**ERKLAERUNG, "Patient.Diagnosen": GEMEINSAM["Patient.Diagnosen"]}

FELDER = {"infusionsplan": INFUSIONSPLAN, "patientendatenblatt": PATIENTENDATENBLATT,
          "datenschutzinformation": ERKLAERUNG, "einwilligung": ERKLAERUNG, "schweigepflichtentbindung": ERKLAERUNG,
          "firmen": ERKLAERUNG, **{a: RGC_ERKLAERUNG for a in RGC_ARTEN},
          "bericht": BERICHT, "sprechstunde": SPRECHSTUNDE, "medikationsplan": MEDIKATIONSPLAN,
          "patientenaufnahme": PATIENTENAUFNAHME, "terminbestaetigung": TERMINBESTAETIGUNG,
          "reisebescheinigung": REISEBESCHEINIGUNG, "patientenankuendigung": ANKUENDIGUNG}
FELDER = JeArt(FELDER, EIGEN)

MEDIKAMENT_SPALTEN = ["Wirkstoff", "Handelsname", "Stärke", "Form", "Mo", "Mi", "Ab", "Zn", "Einheit", "Hinweise",
                      "Grund"]
MEDIKAMENT_AUSRICHTUNG = ["", "handel", "knapp", "form", "dosis", "dosis", "dosis", "dosis", "einheit", "", "grund"]

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
    "datenschutzinformation": {}, "einwilligung": {}, "schweigepflichtentbindung": {}, "firmen": {},
    **{a: {} for a in RGC_ARTEN},
    "bericht": {
        "diagnosen": ("Diagnosen mit ICD-Code", ["Diagnose", "ICD", "seit"], ["", "", ""]),
    },
    "sprechstunde": {
        "diagnosen": ("Diagnosen mit ICD-Code", ["Diagnose", "ICD", "seit"], ["", "", ""]),
        "labor": ("Letzter Laborbefund (Parameter, Wert, Einheit, Referenz)",
                  ["Parameter", "Wert", "Einheit", "Referenz"], ["", "zahl", "einheit", ""]),
        "bia": ("Letzte BIA-Messung", ["Merkmal", "Wert", "Einheit"], ["", "zahl", "einheit"]),
        "zusammensetzung": ("Zusammensetzung des aktuellen Infusionsplans",
                            ["Bestandteil", "Menge", "Einheit", "Präparat"], ["", "zahl", "einheit", ""]),
        "bilanz": ("Laufzeit und Volumen (Mischbeutel, Zusatzlösung, Gesamt)",
                   ["", "Mischbeutel", "Zusatzlösung", "Gesamt", ""], ["", "zahl", "zahl", "zahl", "einheit"]),
    },
    # Medikamentenplan (Wunsch 11.10.2026), Spalten wie im bundeseinheitlichen Medikationsplan
    "medikationsplan": {
        "medikamente": ("Dauermedikation (Wirkstoff, Handelsname, Stärke, Form, Mo–Mi–Ab–Zn, Einheit, Hinweise, Grund)",
                        MEDIKAMENT_SPALTEN, MEDIKAMENT_AUSRICHTUNG),
        "bedarfsmedikation": ("Bedarfsmedikation (wie die Dauermedikation; Dosierung je Gabe)",
                              MEDIKAMENT_SPALTEN, MEDIKAMENT_AUSRICHTUNG),
    },
    "patientenaufnahme": {}, "terminbestaetigung": {},
    "reisebescheinigung": {
        "diagnosen": ("Diagnosen mit ICD-Code", ["Diagnose", "ICD", "seit"], ["", "", ""]),
    },
    "patientenankuendigung": {
        "ankuendigung": ("Termine im Zeitraum (Tag, Uhrzeit, Patient, Hinweis)",
                         ["Tag", "Uhrzeit", "Patient", "Hinweis"], ["", "", "", ""]),
    },
}
TABELLEN = JeArt(TABELLEN, {"diagnosen": ("Diagnosen mit ICD-Code", ["Diagnose", "ICD", "seit"], ["", "", ""])})


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
    if quelle == "diagnosen":
        if not k.patient.pk:
            return []
        eintraege = k.merke("diagnosen", lambda: list(k.patient.diagnosen.filter(aktiv=True)))
        return [[d.bezeichnung, f"{d.icd_code}{d.kennzeichen}", datum(d.seit) or "—"] for d in eintraege]
    if quelle in ("medikamente", "bedarfsmedikation"):
        zeilen = []
        for m in _medikamente(k, quelle == "bedarfsmedikation"):
            hinweise = " · ".join(t for t in (m.dosierung_frei, m.hinweise) if t)
            zeilen.append([m.wirkstoff, m.handelsname or "—", m.staerke or "—", m.darreichungsform or "—",
                           *((getattr(m, f) or ("0" if m.schema else "")) for f in m.DOSIERFELDER),
                           m.einheit or "", hinweise or "—", m.grund or "—"])
        return zeilen
    if quelle == "labor":
        if k.labor is None:
            return []
        zeilen = []
        for w in k.labor.werte.select_related("parameter"):
            referenz = "—"
            if w.referenz_von is not None or w.referenz_bis is not None:
                referenz = f"{_zahl(w.referenz_von) or ''} – {_zahl(w.referenz_bis) or ''}".strip(" –")
            wert = w.anzeige_wert
            zeilen.append([w.bezeichnung, Fett(wert) if w.ausserhalb else wert, w.einheit or "", referenz])
        return zeilen
    if quelle == "bia":
        if k.bia is None:
            return []
        b = k.bia
        zeilen = [("Gewicht", b.gewicht_kg, "kg"), ("BCM", b.bcm_kg, "kg"), ("Fettmasse", b.fettmasse_kg, "kg"),
                  ("Magermasse", b.magermasse_kg, "kg"), ("ECW (extrazelluläres Wasser)", b.ecw_prozent, "%"),
                  ("Körperwasser", b.koerperwasser_l, "l"), ("BMI", b.bmi, "")]
        return [[name, _zahl(wert), einheit] for name, wert, einheit in zeilen if wert is not None]
    if quelle == "ankuendigung":
        zeilen, vorher = [], None
        for t in k.termine or []:
            tag = tag_lang(t.faellig_am)
            zeilen.append([Fett(tag) if tag != vorher else "", f"{t.uhrzeit:%H:%M}" if t.uhrzeit else "—",
                           f"{t.patient.vorname} {t.patient.nachname}", ankuendigung_hinweis(t, k.terminort) or ""])
            vorher = tag
        return zeilen
    if quelle == "termine":
        from patienten.models import Termin

        termine = (Termin.objects.filter(patient=k.patient, erledigt_am__isnull=True, faellig_am__gte=k.heute)
                   .select_related("ort").order_by("faellig_am", "uhrzeit")[:3]) if k.patient.pk else []
        return [[datum(t.faellig_am) + (f", {t.uhrzeit:%H:%M} Uhr" if t.uhrzeit else ""), t.get_art_display(), t.titel,
                 str(t.ort) if t.ort_id else (t.bei or "—")] for t in termine]
    return []


def ist_telefonort(ort) -> bool:
    """Telefon- oder Videotermin? Erkannt am Namen des Terminorts („Telefon“, „Video“)."""
    return ort is not None and any(w in str(ort).lower() for w in ("telefon", "video"))


def ankuendigung_hinweis(t, terminort=None) -> str | None:
    """Hinweis zu einem Termin der Patientenankündigung (F173): ein abweichender Terminort – bei Telefon- oder
    Videoterminen mit der Telefonnummer der Akte – und der Freitext „bei/Ort“ (z. B. „1 h, Neuaufnahme“)."""
    teile = []
    if t.ort_id and (terminort is None or t.ort_id != terminort.pk):
        ort = str(t.ort)
        if ist_telefonort(ort):
            nummer = t.patient.telefon or t.patient.telefon2
            ort = f"{ort} {nummer}" if nummer else ort
        teile.append(ort)
    if t.bei:
        teile.append(t.bei)
    return " · ".join(teile) or None


def termine_als_text(k) -> str | None:
    """Die Termine der Patientenankündigung als Text, je Tag eine Überschrift (F173)."""
    zeilen, vorher = [], None
    for t in k.termine or []:
        if t.faellig_am != vorher:
            if zeilen:
                zeilen.append("")
            zeilen.append(tag_lang(t.faellig_am))
            vorher = t.faellig_am
        hinweis = ankuendigung_hinweis(t, k.terminort)
        zeilen.append(f"{t.uhrzeit:%H:%M}" if t.uhrzeit else "—")
        zeilen[-1] += f"  {t.patient.vorname} {t.patient.nachname}" + (f" → {hinweis}" if hinweis else "")
    return "\n".join(zeilen) or None
