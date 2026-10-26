"""Datenfelder und Tabellen des Behandlungsfalls für die Vorlagen (Platzhalter ``{{Fall.…}}``, ``{{Rechnung.…}}``,
``{{Dokument.…}}``, Tabellen „rechnung“ und „leistungen“).

Sie stehen in allen eigenen Schreiben (also auch in den Word-Vorlagen der RGC, Revision 3) zur Verfügung. Ohne Fall
(Schreiben aus der Korrespondenz) bleiben sie leer. Beträge, Daten und Spaltenköpfe richten sich nach der Sprache des
Falls (DE/LV/EN).
"""
from decimal import Decimal

from vorlagen.felder import Feld, datum

TEXTE = {
    "rechnung": {"de": "Rechnung", "lv": "Rēķins", "en": "Invoice"},
    "storno": {"de": "Stornorechnung", "lv": "Kredītrēķins", "en": "Cancellation invoice"},
    "storno_zu": {"de": "Storno zu Rechnung {n} vom {d}", "lv": "Anulē rēķinu {n} no {d}",
                  "en": "Cancels invoice {n} dated {d}"},
    "zahlbar": {"de": "Zahlbar ohne Abzug bis {d}.", "lv": "Apmaksāt bez atlaides līdz {d}.",
                "en": "Payable without deduction by {d}."},
    "ust_frei": {"de": "Steuerfreie Heilbehandlung.", "lv": "Ar PVN neapliekams ārstniecības pakalpojums.",
                 "en": "VAT-exempt medical treatment."},
    "signiert": {"de": "Elektronisch signiert von {p} am {d}.", "lv": "Elektroniski parakstījis {p} {d}.",
                 "en": "Electronically signed by {p} on {d}."},
}
SPALTEN = {
    "rechnung": {"de": ["Pos.", "Leistungsnr.", "Leistung", "Datum", "Menge", "Einzelpreis", "Betrag (EUR)"],
                 "lv": ["Poz.", "Kods", "Pakalpojums", "Datums", "Daudz.", "Cena", "Summa (EUR)"],
                 "en": ["Item", "Code", "Service", "Date", "Qty", "Unit price", "Amount (EUR)"]},
    "leistungen": {"de": ["Leistungsnr.", "Leistung", "Menge", "Betrag (EUR)"],
                   "lv": ["Kods", "Pakalpojums", "Daudz.", "Summa (EUR)"],
                   "en": ["Code", "Service", "Qty", "Amount (EUR)"]},
}
TABELLEN = {
    "rechnung": ("Rechnungspositionen des Dokuments (Pos., Leistungsnr., Leistung, Datum, Menge, Einzelpreis, Betrag)",
                 SPALTEN["rechnung"]["de"], ["knapp", "knapp", "", "knapp", "zahl", "zahl", "zahl"]),
    "leistungen": ("Leistungen der aktuellen Rechnung des Falls (für Anlage K: Leistungsnr., Leistung, Menge, Betrag)",
                   SPALTEN["leistungen"]["de"], ["knapp", "", "zahl", "zahl"]),
}


def sprache(k) -> str:
    """Sprache des Falls – die Formulare der RGC (Art „vorlage“, deutsch bzw. DE/LV) immer deutsch."""
    fall = getattr(k, "fall", None)
    dok = getattr(k, "falldokument", None)
    if fall is None or (dok is not None and dok.art == dok.Art.VORLAGE):
        return "de"
    return fall.sprache


def text(k, schluessel, **werte) -> str:
    return TEXTE[schluessel][sprache(k)].format(**werte)


def betrag(wert, k=None) -> str | None:
    """1234.5 → „1.234,50“ (DE/LV) bzw. „1,234.50“ (EN)."""
    if wert is None:
        return None
    s = f"{Decimal(wert):,.2f}"
    if k is not None and sprache(k) == "en":
        return s
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# Einheiten des Leistungskatalogs (deutsch gepflegt) in der Sprache des Falls
EINHEITEN = {"Stück": ("gab.", "pcs"), "Stunde": ("st.", "h"), "Stunden": ("st.", "h"), "Tag": ("diena", "day"),
             "Tage": ("dienas", "days"), "Nacht": ("nakts", "night"), "Eingriff": ("operācija", "procedure"),
             "Pauschale": ("fiksēta maksa", "flat rate"), "Sitzung": ("seanss", "session")}


def einheit(wert: str, k) -> str:
    s = sprache(k)
    if s == "de" or wert not in EINHEITEN:
        return wert
    return EINHEITEN[wert][0 if s == "lv" else 1]


def menge(wert) -> str:
    w = Decimal(wert).normalize()
    s = f"{w:f}"
    return s.replace(".", ",")


def _fall(funktion):
    return lambda k: funktion(k.fall) if getattr(k, "fall", None) is not None else None


def _dok(funktion):
    return lambda k: funktion(k.falldokument) if getattr(k, "falldokument", None) is not None else None


def _rechnung(funktion):
    def wert(k):
        d = getattr(k, "falldokument", None)
        return funktion(d, k) if d is not None and d.ist_rechnung else None
    return wert


def _empfaenger(f) -> str | None:
    if f.rechnungsempfaenger.strip():
        return f.rechnungsempfaenger.strip()
    p = f.patient
    zeilen = [f"{p.vorname} {p.nachname}", p.strasse, f"{p.plz} {p.ort}".strip()]
    return "\n".join(z for z in zeilen if z) or None


def _summen(d):
    return d.summen()


def _faellig(d, k):
    if not d.rechnungsdatum:
        return None
    from datetime import timedelta

    return text(k, "zahlbar", d=datum(d.rechnungsdatum + timedelta(days=d.zahlungsziel_tage)))


def _titel(d, k):
    if d.art == d.Art.STORNO:
        return text(k, "storno")
    return text(k, "rechnung")


def _bezug(d, k):
    if d.art != d.Art.STORNO or d.storno_zu is None:
        return None
    o = d.storno_zu
    return text(k, "storno_zu", n=o.rechnungsnummer or "—", d=datum(o.rechnungsdatum) or "—")


def _ust_hinweis(d, k):
    return text(k, "ust_frei") if not _summen(d)["ust"] else None


def _aktuelle_rechnung(fall):
    from .models import FallDokument

    return (fall.dokumente.filter(art=FallDokument.Art.RECHNUNG, storniert_am__isnull=True)
            .order_by("-id").first())


FELDER = {
    "Fall.Nummer": Feld("Fallnummer (F-2026-0001)", _fall(lambda f: f.nummer or None)),
    "Fall.Titel": Feld("Bezeichnung des Falls", _fall(lambda f: f.titel or None)),
    "Fall.Kostenträgertyp": Feld("Kostenträgertyp (z. B. Deutschland GKV)", _fall(lambda f: str(f.kostentraegertyp))),
    "Fall.Kostenträger": Feld("Kostenträger (z. B. AOK Bayern)", _fall(lambda f: f.kostentraeger or None)),
    "Fall.Land": Feld("Land des Kostenträgers", _fall(lambda f: f.land or f.kostentraegertyp.land or None)),
    "Fall.Versichertennummer": Feld("Versichertennummer im Fall (sonst aus der Akte)",
                                    _fall(lambda f: f.versichertennummer or f.patient.versichertennummer or None)),
    "Fall.Aktenzeichen": Feld("Aktenzeichen bzw. Genehmigung des Kostenträgers", _fall(lambda f: f.aktenzeichen or None)),
    "Fall.Kooperationspartner": Feld("Kooperationspartner",
                                     _fall(lambda f: f.kooperationspartner.name if f.kooperationspartner_id else None)),
    "Fall.Kooperationspartner_Anschrift": Feld(
        "Anschrift des Kooperationspartners",
        _fall(lambda f: (f.kooperationspartner.anschrift or None) if f.kooperationspartner_id else None)),
    "Fall.Sprache": Feld("Sprache des Falls", _fall(lambda f: f.get_sprache_display())),
    "Fall.Fachbereich": Feld("Fachbereich", _fall(lambda f: f.get_fachbereich_display() if f.fachbereich else None)),
    "Fall.Aufnahme": Feld("Aufnahmedatum", _fall(lambda f: datum(f.aufnahme))),
    "Fall.Entlassung": Feld("Entlassungsdatum", _fall(lambda f: datum(f.entlassung))),
    "Fall.Zeitraum": Feld("Behandlungszeitraum (Aufnahme – Entlassung)",
                          _fall(lambda f: " – ".join(x for x in (datum(f.aufnahme), datum(f.entlassung)) if x) or None)),
    "Fall.OP_Datum": Feld("OP-Datum", _fall(lambda f: datum(f.op_datum))),
    "Fall.Eingriff": Feld("Eingriff", _fall(lambda f: f.eingriff or None)),
    "Fall.Diagnose": Feld("Diagnose(n) des Falls", _fall(lambda f: f.diagnose or None)),
    "Fall.Arzt": Feld("Behandelnder Arzt", _fall(lambda f: f.behandelnder_arzt.name if f.behandelnder_arzt_id else None)),
    "Fall.Operateur": Feld("Operateur", _fall(lambda f: f.operateur or None)),
    "Fall.Assistenz": Feld("Assistenz", _fall(lambda f: f.assistenz or None)),
    "Fall.Anästhesie": Feld("Anästhesie", _fall(lambda f: f.anaesthesie or None)),
    "Fall.OP_Indikation": Feld("Indikation zur Operation", _fall(lambda f: f.op_indikation or None)),
    "Fall.OP_Verlauf": Feld("OP-Verlauf", _fall(lambda f: f.op_verlauf or None)),
    "Fall.OP_Befund": Feld("OP-Befund / Ergebnis", _fall(lambda f: f.op_befund or None)),
    "Fall.Verlauf": Feld("Verlauf (Entlassungsbrief)", _fall(lambda f: f.entlass_verlauf or None)),
    "Fall.Befunde": Feld("Befunde (Entlassungsbrief)", _fall(lambda f: f.entlass_befunde or None)),
    "Fall.Entlassmedikation": Feld("Medikation bei Entlassung", _fall(lambda f: f.entlass_medikation or None)),
    "Fall.Empfehlung": Feld("Empfehlung / Procedere", _fall(lambda f: f.entlass_empfehlung or None)),
    "Fall.Konsil_an": Feld("Konsil an (Empfänger)", _fall(lambda f: f.konsil_empfaenger or None)),
    "Fall.Konsil_Fragestellung": Feld("Fragestellung des Konsils", _fall(lambda f: f.konsil_fragestellung or None)),
    "Fall.Konsil_Befund": Feld("Befund des Konsils", _fall(lambda f: f.konsil_befund or None)),
    "Fall.Konsil_Beurteilung": Feld("Beurteilung / Empfehlung des Konsils",
                                    _fall(lambda f: f.konsil_beurteilung or None)),
    "Fall.Rechnungsempfänger": Feld("Rechnungsempfänger (sonst Patient mit Anschrift)", _fall(_empfaenger)),
    "Dokument.Titel": Feld("Titel des Dokuments", _dok(lambda d: d.titel or None)),
    "Dokument.Freitext": Feld("Zusätzlicher Text des Dokuments", _dok(lambda d: d.freitext or None)),
    "Dokument.Unterzeichner": Feld("Unterschriftsberechtigte Person (bei der Finalisierung bzw. der Arzt des Falls)",
                                   lambda k: _unterzeichner(k)),
    "Dokument.Unterzeichner_Funktion": Feld("Funktion der unterschriftsberechtigten Person",
                                            lambda k: _unterzeichner(k, funktion=True)),
    "Rechnung.Titel": Feld("Rechnung / Stornorechnung (in der Sprache des Falls)", _rechnung(_titel)),
    "Rechnung.Nummer": Feld("Rechnungsnummer (RGC-2026-0001)", _rechnung(lambda d, k: d.rechnungsnummer)),
    "Rechnung.Datum": Feld("Rechnungsdatum", _rechnung(lambda d, k: datum(d.rechnungsdatum))),
    "Rechnung.Zahlungsziel": Feld("Zahlbar bis … (aus Rechnungsdatum und Zahlungsziel)", _rechnung(_faellig)),
    "Rechnung.Bezug": Feld("bei Storno: stornierte Rechnung mit Datum", _rechnung(_bezug)),
    "Rechnung.Netto": Feld("Summe netto (EUR)", _rechnung(lambda d, k: betrag(_summen(d)["netto"], k))),
    "Rechnung.USt": Feld("Umsatzsteuer (EUR)", _rechnung(lambda d, k: betrag(_summen(d)["ust"], k))),
    "Rechnung.Summe": Feld("Gesamtbetrag (EUR)", _rechnung(lambda d, k: betrag(_summen(d)["brutto"], k))),
    "Rechnung.USt_Hinweis": Feld("Hinweis „Steuerfreie Heilbehandlung“ bei 0 % USt.", _rechnung(_ust_hinweis)),
    "Leistungen.Summe": Feld("Gesamtbetrag der aktuellen Rechnung des Falls (für Anlage K)",
                             lambda k: _leistungen_summe(k)),
}


def _unterzeichner(k, funktion=False):
    d = getattr(k, "falldokument", None)
    u = d.unterzeichner if d is not None and d.unterzeichner_id else None
    if u is None and getattr(k, "fall", None) is not None and k.fall.behandelnder_arzt_id:
        u = k.fall.behandelnder_arzt
    if u is None:
        return None
    return (u.funktion or None) if funktion else u.name


def _leistungen_summe(k):
    fall = getattr(k, "fall", None)
    if fall is None or not fall.pk:
        return None
    r = _aktuelle_rechnung(fall)
    return betrag(r.summen()["brutto"], k) if r is not None else None


def spalten(quelle: str, k) -> list[str]:
    return list(SPALTEN[quelle][sprache(k)])


def zeilen(quelle: str, k) -> list[list[str]]:
    from vorlagen.felder import Fett

    if quelle == "rechnung":
        d = getattr(k, "falldokument", None)
        if d is None or not d.pk or not d.ist_rechnung:
            return []
        z = [[str(i), p.code or "—", p.text, datum(p.datum) or "—", f"{menge(p.menge)} {einheit(p.einheit, k)}".strip(),
              betrag(p.einzelpreis, k), betrag(p.betrag, k)]
             for i, p in enumerate(d.positionen.all(), 1)]
        s = d.summen()
        if s["ust"]:
            z.append(["", "", "Netto" if sprache(k) == "de" else "Neto" if sprache(k) == "lv" else "Net", "", "", "",
                      betrag(s["netto"], k)])
            for satz, wert in s["ust_saetze"].items():
                z.append(["", "", f"USt. {menge(satz)} %" if sprache(k) == "de" else f"PVN {menge(satz)} %"
                          if sprache(k) == "lv" else f"VAT {menge(satz)} %", "", "", "", betrag(wert, k)])
        z.append(["", "", Fett({"de": "Gesamtbetrag", "lv": "Kopā", "en": "Total"}[sprache(k)]), "", "", "",
                  Fett(betrag(s["brutto"], k))])
        return z
    if quelle == "leistungen":
        fall = getattr(k, "fall", None)
        if fall is None or not fall.pk:
            return []
        r = _aktuelle_rechnung(fall)
        if r is None:
            return []
        z = [[p.code or "—", p.text, f"{menge(p.menge)} {einheit(p.einheit, k)}".strip(), betrag(p.betrag, k)]
             for p in r.positionen.all()]
        z.append(["", Fett({"de": "Gesamtbetrag", "lv": "Kopā", "en": "Total"}[sprache(k)]), "",
                  Fett(betrag(r.summen()["brutto"], k))])
        return z
    return []


# Welche Felder des Falls ein Platzhalter liest – für „veraltet“: Ein Dokument gilt nur dann als veraltet, wenn sich
# Angaben geändert haben, die seine Vorlage tatsächlich verwendet (eine Änderung am OP-Bericht betrifft die Rechnung nicht)
QUELLEN = {
    "Fall.Nummer": ["nummer"], "Fall.Titel": ["titel"], "Fall.Kostenträgertyp": ["kostentraegertyp_id"],
    "Fall.Kostenträger": ["kostentraeger"], "Fall.Land": ["land", "kostentraegertyp_id"],
    "Fall.Versichertennummer": ["versichertennummer"], "Fall.Aktenzeichen": ["aktenzeichen"],
    "Fall.Kooperationspartner": ["kooperationspartner_id"], "Fall.Kooperationspartner_Anschrift": ["kooperationspartner_id"],
    "Fall.Sprache": ["sprache"], "Fall.Fachbereich": ["fachbereich"], "Fall.Aufnahme": ["aufnahme"],
    "Fall.Entlassung": ["entlassung"], "Fall.Zeitraum": ["aufnahme", "entlassung"], "Fall.OP_Datum": ["op_datum"],
    "Fall.Eingriff": ["eingriff"], "Fall.Diagnose": ["diagnose"], "Fall.Arzt": ["behandelnder_arzt_id"],
    "Fall.Operateur": ["operateur"], "Fall.Assistenz": ["assistenz"], "Fall.Anästhesie": ["anaesthesie"],
    "Fall.OP_Indikation": ["op_indikation"], "Fall.OP_Verlauf": ["op_verlauf"], "Fall.OP_Befund": ["op_befund"],
    "Fall.Verlauf": ["entlass_verlauf"], "Fall.Befunde": ["entlass_befunde"],
    "Fall.Entlassmedikation": ["entlass_medikation"], "Fall.Empfehlung": ["entlass_empfehlung"],
    "Fall.Konsil_an": ["konsil_empfaenger"], "Fall.Konsil_Fragestellung": ["konsil_fragestellung"],
    "Fall.Konsil_Befund": ["konsil_befund"], "Fall.Konsil_Beurteilung": ["konsil_beurteilung"],
    "Fall.Rechnungsempfänger": ["rechnungsempfaenger"], "Dokument.Unterzeichner": ["behandelnder_arzt_id"],
    "Dokument.Unterzeichner_Funktion": ["behandelnder_arzt_id"],
}


def verwendete_fallfelder(bloecke) -> set[str]:
    """Felder des Falls, die die Blöcke einer Vorlage über Platzhalter lesen (Sprache immer: sie wählt die Vorlage)."""
    import json

    from vorlagen.bloecke import platzhalter

    text = json.dumps(bloecke, ensure_ascii=False)
    felder = {"sprache"}
    for name in platzhalter(text):
        felder.update(QUELLEN.get(name, []))
    # Summe bzw. Tabelle der Leistungen (Anlage K, 09, 10): liest die aktuelle Rechnung des Falls
    if "Leistungen." in text or '"quelle": "leistungen"' in text:
        felder.add("leistungen")
    return felder
