"""PDFs mit festem Aufbau (F24 Verlauf, F59 Audit-Log, F55 Zugangsblatt) und die Akte als Patientendatenblatt (F23).

Kopf und Fuß kommen aus der aktiven Vorlage „Patientendatenblatt“ (Briefkopf- und Fußzeilen-Block), damit alle PDFs
gleich aussehen und die Administration Kopf und Fuß an einer Stelle pflegt.
"""
import html

from django.utils import timezone

from .felder import Kontext, datum
from .pdf import Ersetzer, briefkopf_html, html_zu_pdf, seite


def _kopf_fuss(patient=None):
    from .models import Dokumentvorlage

    v = Dokumentvorlage.aktive(Dokumentvorlage.Art.PATIENTENDATENBLATT)
    kopf = next((b for b in v.bloecke if b.get("typ") == "briefkopf"), None)
    fuss = next((b for b in v.bloecke if b.get("typ") == "fusszeile"), None)
    ersetze = Ersetzer("patientendatenblatt", Kontext(patient=patient)) if patient is not None else None
    kopf_html = briefkopf_html(kopf.get("absender", True), kopf.get("linienfarbe"), kopf.get("falzmarken", False),
                               kopf.get("mit_linie", True)) \
        if kopf else briefkopf_html()
    text = rechts = None
    if fuss and ersetze is not None:
        text, rechts = ersetze.text(fuss.get("text", "")), ersetze.text(fuss.get("rechts", ""))
    elif fuss:
        # ohne Patient (Audit-Log, Zugangsblatt): nur Absender-Felder und das Datum einsetzen
        from .felder import FELDER

        e = Ersetzer("patientendatenblatt", Kontext(patient=None))
        e.felder = {k: f for k, f in FELDER["patientendatenblatt"].items() if k.startswith("Absender.") or k == "Heute"}
        text, rechts = e.text(fuss.get("text", "")), e.text(fuss.get("rechts", ""))
    return f'<div class="block">{kopf_html}</div>', text, (rechts if rechts is not None else "{Seite}/{Seiten}")


def _tabelle(spalten, zeilen, breiten=None) -> str:
    kopf = "".join(f'<th{f" style=width:{breiten[i]}" if breiten else ""}>{html.escape(s)}</th>' for i, s in enumerate(spalten))
    koerper = "".join("<tr>" + "".join(f"<td>{z}</td>" for z in zeile) + "</tr>" for zeile in zeilen) \
        or f'<tr><td class="leer" colspan="{len(spalten)}">keine Einträge</td></tr>'
    return f'<table class="tabelle"><thead><tr>{kopf}</tr></thead><tbody>{koerper}</tbody></table>'


def _titel(text, zusatz="") -> str:
    return (f'<div class="block titel"><h1>{html.escape(text)}</h1>'
            f'<div class="zusatz">{html.escape(zusatz)}</div></div>')


def _zeitpunkt(z) -> str:
    return timezone.localtime(z).strftime("%d.%m.%Y %H:%M")


# --------------------------------------------------------------------------------------------- F23
def akte_pdf(patient) -> bytes:
    """Akte als PDF: Patientendatenblatt mit der aktiven Vorlage (auch abgeschlossene Akten)."""
    from infusionen.models import Infusionsplan

    from .pdf import erzeuge_aus_vorlage, wasserzeichen_fuer

    plan = Infusionsplan.objects.filter(patient=patient, status=Infusionsplan.Status.AKTUELL).first()
    pdf, _ = erzeuge_aus_vorlage("patientendatenblatt", Kontext(patient=patient, plan=plan),
                                 wasserzeichen=wasserzeichen_fuer(patient),
                                 titel=f"Patientendatenblatt {patient.nachname}, {patient.vorname}")
    return pdf


# --------------------------------------------------------------------------------------------- F116
def sprechstunde_kontext(patient) -> Kontext:
    """Der jeweils aktuellste Stand aller Bereiche in einem Kontext (F116): aktueller Infusionsplan, letzte
    BIA-Messung, letzter Laborbefund. Diagnosen und Empfehlung kommen über die Felder des Patienten dazu."""
    from befunde.models import BiaMessung, Laborbefund
    from infusionen.models import Infusionsplan

    plan = Infusionsplan.objects.filter(patient=patient, status=Infusionsplan.Status.AKTUELL).first()
    labor = (Laborbefund.objects.filter(patient=patient).order_by("-abgenommen_am", "-id")
             .prefetch_related("werte__parameter").first())
    bia = BiaMessung.objects.filter(patient=patient).order_by("-gemessen_am", "-id").first()
    return Kontext(patient=patient, plan=plan, labor=labor, bia=bia)


def sprechstunde_pdf(patient) -> bytes:
    """Unterlagen für die Sprechstunde als PDF (F116)."""
    from .pdf import erzeuge_aus_vorlage, wasserzeichen_fuer

    pdf, _ = erzeuge_aus_vorlage("sprechstunde", sprechstunde_kontext(patient),
                                 wasserzeichen=wasserzeichen_fuer(patient),
                                 titel=f"Unterlagen für die Sprechstunde – {patient.nachname}, {patient.vorname}")
    return pdf


# --------------------------------------------------------------------------------------------- Medikationsplan
def medikationsplan_pdf(patient) -> bytes:
    """Medikationsplan als PDF (Wunsch 11.10.2026): Dauer- und Bedarfsmedikation mit der aktiven Vorlage."""
    from .pdf import erzeuge_aus_vorlage, wasserzeichen_fuer

    pdf, _ = erzeuge_aus_vorlage("medikationsplan", Kontext(patient=patient),
                                 wasserzeichen=wasserzeichen_fuer(patient),
                                 titel=f"Medikationsplan {patient.nachname}, {patient.vorname}")
    return pdf


# --------------------------------------------------------------------------------------------- Kopie der Akte
def _e(wert) -> str:
    return html.escape(str(wert)) if wert not in (None, "") else "—"


def _paare(zeilen) -> str:
    """Bezeichnung links, Wert rechts; leere Werte entfallen."""
    inhalt = "".join(f'<tr><td class="label" style="width:32%">{html.escape(a)}</td><td class="wert">{b}</td></tr>'
                     for a, b in zeilen if b not in (None, "", "—"))
    return f'<table class="felder">{inhalt}</table>' if inhalt else '<div class="leer">keine Angaben</div>'


def _abschnitt(titel: str, inhalt: str) -> str:
    return f'<div class="block"><h2 class="abschnitt">{html.escape(titel)}</h2>{inhalt}</div>'


def _text(html_text: str) -> str:
    """Formatierter Text der Akte (beim Speichern bereinigtes HTML)."""
    return f'<div class="richtext">{html_text}</div>' if html_text else ""


def aktenkopie_pdf(patient) -> bytes:
    """Die vollständige Akte als PDF für die Kopie nach Art. 15 Abs. 3 DSGVO: alle Angaben und alle Einträge –
    auch stornierte Kontakte, erledigte Termine, abgelöste Pläne und ausgeblendete Dokumente (als Liste; die Dateien
    selbst liegen der Kopie im Original bei). Fester Aufbau, Kopf und Fuß wie die übrigen PDFs."""
    from infusionen.models import VERGLEICHSZEILEN, _anzeige
    from patienten.models import Erklaerung

    from epm.api_basis import benutzername

    p = patient
    kopf, fuss, rechts = _kopf_fuss(p)
    teile = [kopf, _titel("Kopie der Akte", f"Stand {datum(timezone.localdate())}")]

    hausarzt = p.aerzte.filter(aktiv=True, rolle="hausarzt").select_related("arzt").first()
    teile.append(_abschnitt("Stammdaten", _paare([
        ("Patienten-Nr.", _e(p.nummer)), ("Name", _e(f"{p.nachname}, {p.vorname}")),
        ("Geburtsdatum", _e(datum(p.geburtsdatum))), ("Geschlecht", _e(p.get_geschlecht_display() if p.geschlecht else "")),
        ("Anschrift", _e(", ".join(t for t in (p.strasse, f"{p.plz} {p.ort}".strip()) if t))),
        ("Telefon", _e(p.telefon)), ("Telefon 2", _e(p.telefon2)), ("E-Mail", _e(p.email)),
        ("Versicherungsart", _e(p.versicherungsart_text())),
        ("Versicherung", _e(p.krankenkasse)), ("Versichertennummer", _e(p.versichertennummer)),
        ("Hausarzt", _e(hausarzt.arzt if hausarzt else p.hausarzt)),
        ("Überweisung / Kontaktaufnahme durch", _e(p.ueberweisung_durch)),
        ("Größe", _e(f"{p.groesse_cm} cm".replace(".", ",") if p.groesse_cm is not None else "")),
        ("Katheter", _e("kein Katheter" if p.kein_katheter else (p.katheter.wert if p.katheter_id else ""))),
        ("Versorger", _e("kein Versorger" if p.kein_versorger else (p.versorger.name if p.versorger_id else ""))),
        ("Ansprechpartner beim Versorger", _e(p.ansprechpartner.name if p.ansprechpartner_id else "")),
        ("Nickelallergie", _e(p.get_nickelallergie_display())),
        ("Akte angelegt", _e(f"{_zeitpunkt(p.angelegt_am)} · {benutzername(p.angelegt_von) or '—'}")),
        ("Akte abgeschlossen", _e(f"{datum(p.abgeschlossen_am)} · {p.get_abschluss_anlass_display()}"
                                  + (f" · {p.abschluss_notiz}" if p.abschluss_notiz else "")) if p.abgeschlossen_am else ""),
    ])))
    diagnosen = [[_e(d.bezeichnung), _e(f"{d.icd_code}{d.kennzeichen}"), _e(d.get_kennzeichen_display()),
                  _e(datum(d.seit)), "zutreffend" if d.aktiv else f"beendet am {datum(d.beendet_am)}", _e(d.notiz)]
                 for d in p.diagnosen.order_by("reihenfolge", "id")]
    teile.append(_abschnitt("Diagnosen (ICD)", _tabelle(
        ["Diagnose", "ICD", "Kennzeichen", "seit", "Stand", "Notiz"], diagnosen,
        [None, "20mm", "34mm", "22mm", "30mm", None])))

    schritte = [[_e(datum(t.datum)), _e(t.text), "aktuell" if t.aktiv else "entfernt"]
                for t in p.therapieschritte.order_by("datum", "id")]
    if schritte:
        teile.append(_abschnitt("Therapie (Verlauf)", _tabelle(["Datum", "Schritt", "Stand"], schritte,
                                                               ["24mm", None, "24mm"])))

    # Medikamentenplan (Wunsch 11.10.2026): auch abgesetzte Medikamente
    medikamente = [[_e(" ".join(t for t in (m.wirkstoff, m.staerke) if t)), _e(m.handelsname), _e(m.darreichungsform),
                    _e(m.dosierung or ("bei Bedarf" if m.bedarf else "")), _e(m.grund), _e(datum(m.seit)),
                    "aktuell" if m.aktiv else _e(f"abgesetzt am {datum(m.abgesetzt_am)}"
                                                  + (f": {m.absetzgrund}" if m.absetzgrund else ""))]
                   for m in p.medikamente.order_by("-aktiv", "bedarf", "reihenfolge", "id")]
    if medikamente:
        teile.append(_abschnitt("Medikamente", _tabelle(
            ["Wirkstoff", "Handelsname", "Form", "Dosierung", "Grund", "seit", "Stand"], medikamente,
            [None, None, "20mm", "28mm", None, "20mm", "30mm"])))

    # Eingriffe der RGC (21.11.2026): Therapie oder Operation mit OPS- und ICD-Code
    eingriffe = [[_e(e.get_art_display()), _e(e.bezeichnung), _e(e.ops_codes), _e(f"{e.icd_code}{e.kennzeichen}"),
                  _e(e.get_status_display() + (f" {datum(e.datum)}" if e.datum else "")),
                  _e(" · ".join(t for t in (e.genehmigung, e.notiz, "" if e.aktiv else "entfernt") if t))]
                 for e in p.eingriffe.order_by("datum", "id")]
    if eingriffe:
        teile.append(_abschnitt("Eingriffe (Therapie und Operation)", _tabelle(
            ["Art", "Eingriff", "OPS", "ICD", "Stand", "Genehmigung, Notiz"], eingriffe,
            ["20mm", None, "26mm", "18mm", "30mm", None])))

    for titel, text in (("Diagnose (Freitext)", p.diagnose), ("Therapie", p.therapie),
                        ("Empfehlung", p.empfehlung), ("Befunde", p.befunde),
                        ("Bemerkung", p.bemerkung)):
        if text:
            teile.append(_abschnitt(titel, _text(text)))

    personen = [[_e(b.beziehung.wert if b.beziehung_id else ""), _e(b.name), _e(b.telefon or b.mobil), _e(b.email),
                 _e(", ".join(t for t in (b.strasse, f"{b.plz} {b.ort}".strip()) if t)),
                 "ja" if b.auskunft_erlaubt else "nein", "aktuell" if b.aktiv else "nicht mehr aktuell", _e(b.notiz)]
                for b in p.bezugspersonen.select_related("beziehung")]
    teile.append(_abschnitt("Bezugspersonen", _tabelle(
        ["Beziehung", "Name", "Telefon", "E-Mail", "Anschrift", "Auskunft", "Stand", "Notiz"], personen)))
    aerzte = [[_e(z.get_rolle_display()), _e(z.arzt), _e(z.arzt.telefon), "zuständig" if z.aktiv else "nicht mehr zuständig",
               _e(z.notiz)] for z in p.aerzte.select_related("arzt")]
    teile.append(_abschnitt("Ärzte", _tabelle(["Rolle", "Arzt", "Telefon", "Stand", "Notiz"], aerzte)))

    gewichte = [[_e(datum(g.gemessen_am)) + (" (ungefähr)" if g.datum_ungenau else ""),
                 _e(f"{g.gewicht_kg} kg".replace(".", ",")), _e(g.get_quelle_display()), _e(g.notiz),
                 _e(benutzername(g.erfasst_von))] for g in p.gewichte.select_related("erfasst_von").order_by("gemessen_am", "id")]
    teile.append(_abschnitt("Gewichte", _tabelle(["Datum", "Gewicht", "Quelle", "Notiz", "erfasst von"], gewichte,
                                                ["24mm", "20mm", "28mm", None, "34mm"])))

    kontakte = []
    for k in p.kontakte.select_related("art", "erfasst_von", "storniert_von").order_by("zeitpunkt", "id"):
        storno = (f'<div class="klein">storniert am {html.escape(_zeitpunkt(k.storniert_am))} von '
                  f'{_e(benutzername(k.storniert_von))} · Grund: {_e(k.storno_grund)}</div>') if k.storniert_am else ""
        kontakte.append([_e(_zeitpunkt(k.zeitpunkt)), _e(k.art.wert if k.art_id else ""), _text(k.text) + storno,
                         _e(benutzername(k.erfasst_von))])
    teile.append(_abschnitt("Kontakte", _tabelle(["Zeitpunkt", "Art", "Text", "erfasst von"], kontakte,
                                                ["26mm", "30mm", None, "34mm"])))

    termine = [[_e(datum(t.faellig_am)) + (f", {t.uhrzeit:%H:%M} Uhr" if t.uhrzeit else ""), _e(t.get_art_display()),
                _e(t.titel) + (f'<div class="klein">{_e(t.notiz)}</div>' if t.notiz else ""),
                _e(t.ort.wert if t.ort_id else t.bei),
                _e(f"erledigt am {datum(timezone.localtime(t.erledigt_am).date())}" if t.erledigt_am else "offen")]
               for t in p.termine.select_related("ort").order_by("faellig_am", "id")]
    teile.append(_abschnitt("Termine", _tabelle(["Datum", "Art", "Titel", "Ort", "Stand"], termine,
                                               ["30mm", "26mm", None, "32mm", "32mm"])))

    for plan in p.infusionsplaene.select_related("erstellt_von", "freigegeben_von", "abgeschlossen_von").order_by("gueltig_ab", "id"):
        zeilen = [(bezeichnung, _text(_anzeige(plan, schluessel)) if schluessel == "bemerkung" and _anzeige(plan, schluessel)
                   else _e(_anzeige(plan, schluessel))) for schluessel, bezeichnung in VERGLEICHSZEILEN]
        zeilen.append(("Erstellt", _e(f"{_zeitpunkt(plan.erstellt_am)} · {benutzername(plan.erstellt_von) or '—'}")))
        zeilen.append(("Freigabe", _e(plan.freigabevermerk or "")))
        teile.append(_abschnitt(f"Infusionsplan gültig ab {datum(plan.gueltig_ab)} ({plan.get_status_display()})",
                                _paare(zeilen)))
    if not p.infusionsplaene.exists():
        teile.append(_abschnitt("Infusionspläne", '<div class="leer">keine Einträge</div>'))

    dokumente = [[_e(datum(d.datum)), _e(d.typ.wert if d.typ_id else ""),
                  _e(d.titel) + (" (ausgeblendet)" if d.ausgeblendet else "")
                  + (f'<div class="klein">{_e(d.notiz)}</div>' if d.notiz else ""),
                  _e(d.originalname), _e(d.get_herkunft_display())]
                 for d in p.dokumente.select_related("typ").order_by("datum", "id")]
    teile.append(_abschnitt("Dokumente (die Dateien liegen dieser Kopie im Original bei)", _tabelle(
        ["Datum", "Typ", "Titel", "Datei", "Herkunft"], dokumente, ["22mm", "30mm", None, "46mm", "26mm"])))

    for befund in p.laborbefunde.prefetch_related("werte__parameter").order_by("abgenommen_am", "id"):
        zeilen = [[_e(w.bezeichnung), _e(w.anzeige_wert), _e(w.einheit),
                   _e(f"{w.referenz_von or ''} – {w.referenz_bis or ''}".strip(" –")), _e(w.bemerkung)]
                  for w in befund.werte.all()]
        inhalt = _tabelle(["Parameter", "Wert", "Einheit", "Referenz", "Bemerkung"], zeilen,
                          [None, "22mm", "22mm", "30mm", None])
        if befund.beurteilung:
            inhalt += _text(befund.beurteilung)
        teile.append(_abschnitt(f"Laborbefund vom {datum(befund.abgenommen_am)}"
                                + (f" · {befund.labor}" if befund.labor else ""), inhalt))
    if not p.laborbefunde.exists():
        teile.append(_abschnitt("Laborbefunde", '<div class="leer">keine Einträge</div>'))

    bia = [[_e(datum(b.gemessen_am)), _e(b.gewicht_kg), _e(b.bcm_kg), _e(b.fettmasse_kg), _e(b.ecw_prozent),
            _e(b.koerperwasser_l), _e(b.bmi), _e(b.phasenwinkel_grad), _text(b.beurteilung) if b.beurteilung else "—"]
           for b in p.bia_messungen.order_by("gemessen_am", "id")]
    teile.append(_abschnitt("BIA-Messungen", _tabelle(
        ["Datum", "Gewicht (kg)", "BCM (kg)", "Fettmasse (kg)", "ECW (%)", "Körperwasser (l)", "BMI", "Phasenw. (°)",
         "Beurteilung"],
        bia, ["22mm", "20mm", "18mm", "22mm", "16mm", "24mm", "14mm", "18mm", None])))

    for b in p.berichte.select_related("art", "erstellt_von", "freigegeben_von").order_by("datum", "id"):
        kopfzeilen = [("Art", _e(b.art.wert if b.art_id else "")), ("Datum", _e(datum(b.datum))),
                      ("Empfänger", _e(b.empfaenger)), ("Stand", _e(b.get_status_display())),
                      ("Erstellt", _e(f"{_zeitpunkt(b.erstellt_am)} · {benutzername(b.erstellt_von) or '—'}")),
                      ("Freigabe", _e(b.freigabevermerk or ""))]
        teile.append(_abschnitt(f"Bericht: {b.titel}", _paare(kopfzeilen) + _text(b.inhalt or "")))
    if not p.berichte.exists():
        teile.append(_abschnitt("Berichte", '<div class="leer">keine Einträge</div>'))

    # Korrespondenz (14.10.2026): jedes Schreiben mit Stand, Empfänger und Versand; die PDFs liegen bei den Dokumenten
    schreiben = [[_e(datum(timezone.localtime(s.erstellt_am).date())), _e(s.titel), _e(s.vorlage_name),
                  _e(s.empfaenger), _e(s.get_status_display()),
                  _e(f"{datum(s.versendet_am)} · {s.get_versandweg_display()}" if s.versendet_am else "")]
                 for s in p.korrespondenz.order_by("erstellt_am", "id")]
    teile.append(_abschnitt("Korrespondenz", _tabelle(
        ["angelegt", "Betreff", "Vorlage", "Empfänger", "Stand", "versendet"], schreiben)))

    erklaerungen = [[_e(e.get_art_display()), _e(datum(e.erteilt_am)),
                     _e(f"widerrufen am {datum(e.widerrufen_am)}" if e.widerrufen_am else "liegt vor"),
                     _e(" · ".join(t for t in (e.notiz, e.widerruf_notiz) if t))]
                    for e in Erklaerung.objects.filter(patient=p).order_by("erteilt_am", "id")]
    teile.append(_abschnitt("Erklärungen zum Datenschutz", _tabelle(["Erklärung", "erteilt am", "Stand", "Notiz"], erklaerungen)))
    anfragen = [[_e(a.get_art_display()), _e(datum(a.eingegangen_am)), _e(a.gestellt_von), _e(a.inhalt),
                 _e(f"{a.get_ergebnis_display()} · {a.begruendung}".strip(" ·") if a.erledigt_am else "offen")]
                for a in p.datenschutzanfragen.order_by("eingegangen_am", "id")]
    teile.append(_abschnitt("Datenschutz-Anfragen", _tabelle(
        ["Anfrage", "eingegangen", "gestellt von", "Inhalt", "Ergebnis"], anfragen)))

    stil = ("<style>.tabelle { font-size: 8pt; } .klein { font-size: 7pt; color: #5d5b72; margin-top: 0.8mm; }"
            " h2.abschnitt { font-size: 11pt; margin: 4mm 0 1.5mm 0; break-after: avoid; }"
            " .tabelle .richtext p { margin: 0 0 1mm 0; }</style>")
    return html_zu_pdf(seite(f"Kopie der Akte {p.nachname}, {p.vorname}", "".join(teile) + stil, fuss,
                             "TESTDATEN" if p.ist_test else None, rechts))


# --------------------------------------------------------------------------------------------- F24
BEREICHE = {"stammdaten": "Stammdaten", "diagnose": "Diagnose (Text)", "therapie": "Therapie",
            "empfehlung": "Empfehlung", "befunde": "Befunde", "gewichte": "Gewicht", "kontakte": "Kontakt", "termine": "Termin",
            "dokumente": "Dokument", "infusionsplaene": "Infusionsplan", "bezugspersonen": "Bezugsperson",
            "aerzte": "Arzt", "erklaerungen": "Erklärung", "datenschutz": "Datenschutz",
            # Wünsche aus der Praxis vom 06.10.2026 (F112–F117)
            "diagnosen": "Diagnose (ICD)", "laborbefunde": "Laborbefund", "bia_messungen": "BIA-Messung",
            "berichte": "Bericht", "therapieschritte": "Therapie (Verlauf)",
            # Korrespondenz (14.10.2026)
            "korrespondenz": "Schreiben",
            # Behandlungsfälle der RGC (26.10.2026)
            "faelle": "Behandlungsfall", "falldokumente": "Dokument eines Falls",
            # Medikamentenplan (Wunsch 11.10.2026)
            "medikamente": "Medikament",
            # Eingriffe der RGC (21.11.2026)
            "eingriffe": "Eingriff",
            # Hinweise stummschalten (Wunsch 07.10.2026, F119)
            "hinweisruhe": "Hinweis stummgeschaltet"}


def verlauf_pdf(patient, eintraege, filter_text="") -> bytes:
    kopf, fuss, rechts = _kopf_fuss(patient)
    zeilen = []
    for e in eintraege:
        aenderungen = "<br>".join(
            f"{html.escape(a['feld'])}: {html.escape(_kurz(a['alt']))} → {html.escape(_kurz(a['neu']))}"
            for a in e.get("aenderungen", [])[:8])
        details = html.escape(e.get("beschreibung") or "") + (f'<div class="klein">{aenderungen}</div>' if aenderungen else "")
        zeilen.append([html.escape(_zeitpunkt(e["zeitpunkt"])), html.escape(e.get("person") or "System"),
                       html.escape(BEREICHE.get(e["bereich"], e["bereich"])), html.escape(e.get("aktion") or ""), details])
    p = patient
    inhalt = (kopf + _titel("Verlauf der Akte", f"Stand {datum(timezone.localdate())}")
              + f'<div class="block">{html.escape(f"{p.nachname}, {p.vorname}")} · Nr. {p.nummer} · geboren '
              f'{datum(p.geburtsdatum)}{(" · " + html.escape(filter_text)) if filter_text else ""} · {len(eintraege)} Einträge</div>'
              + f'<div class="block">{_tabelle(["Zeitpunkt", "Person", "Bereich", "Aktion", "Details"], zeilen, ["24mm", "32mm", "24mm", "22mm", None])}</div>')
    zeichen = "TESTDATEN" if p.ist_test else None
    return html_zu_pdf(seite(f"Verlauf {p.nachname}, {p.vorname}", inhalt + STIL_KLEIN, fuss, zeichen, rechts))


def _kurz(wert, laenge=120) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", str(wert or ""))
    text = " ".join(html.unescape(text).split()) or "—"
    return text if len(text) <= laenge else text[:laenge] + " …"


STIL_KLEIN = "<style>.tabelle { font-size: 8pt; } .klein { font-size: 7pt; color: #5d5b72; margin-top: 0.8mm; }</style>"


# --------------------------------------------------------------------------------------------- F59
def protokoll_pdf(ereignisse, filter_text="") -> bytes:
    from audit.texte import beschreibung, gruppe_name

    kopf, fuss, rechts = _kopf_fuss()
    zeilen = []
    for e in ereignisse:
        person = e.benutzer.anzeigename if e.benutzer else (e.benutzername or "System")
        zeilen.append([html.escape(_zeitpunkt(e.zeitpunkt)), html.escape(person),
                       html.escape(gruppe_name(e.art) or e.get_art_display()), html.escape(beschreibung(e)),
                       html.escape(" · ".join(t for t in (e.geraet, e.ip or "") if t))])
    inhalt = (kopf + _titel("Audit-Log", f"erstellt {datum(timezone.now())}")
              + f'<div class="block">{html.escape(filter_text or "alle Einträge")} · {len(zeilen)} Einträge</div>'
              + f'<div class="block">{_tabelle(["Zeitpunkt", "Person", "Art", "Details", "Gerät / Adresse"], zeilen, ["24mm", "30mm", "22mm", None, "34mm"])}</div>')
    return html_zu_pdf(seite("Audit-Log", inhalt + STIL_KLEIN, fuss, None, rechts))


# --------------------------------------------------------------------------------------------- F55
def zugangsblatt_pdf(user, kennwort: str, adresse: str) -> bytes:
    kopf, fuss, rechts = _kopf_fuss()
    gueltig = datum(user.einmal_kennwort_gueltig_bis) if user.einmal_kennwort_gueltig_bis else "—"
    angaben = [("Name", user.anzeigename), ("Benutzername", user.username), ("Einmal-Passwort", kennwort),
               ("gültig bis", gueltig), ("Adresse", adresse)]
    felder = "".join(f'<tr><td class="label" style="width:35%">{html.escape(a)}</td>'
                     f'<td class="wert{" mono" if a in ("Benutzername", "Einmal-Passwort") else ""}">{html.escape(b or "—")}</td></tr>'
                     for a, b in angaben)
    schritte = [
        "EPM im Browser öffnen (nur im Netz der Stiftung bzw. über das VPN erreichbar) und mit Benutzername und "
        "Einmal-Passwort anmelden.",
        "Ein eigenes Passwort wählen (mindestens 12 Zeichen). Das Einmal-Passwort gilt danach nicht mehr.",
        "Die Authenticator-App auf dem Telefon öffnen (z. B. Microsoft oder Google Authenticator), den angezeigten "
        "QR-Code scannen und den 6-stelligen Code eingeben.",
        "Die 10 Notfall-Codes ausdrucken oder sicher aufbewahren. Sie ersetzen das Telefon, falls es verloren geht.",
    ]
    liste = "".join(f"<li>{html.escape(s)}</li>" for s in schritte)
    inhalt = (kopf + _titel("Zugang zu EPM", f"erstellt {datum(timezone.localdate())}")
              + f'<div class="block"><table class="felder">{felder}</table></div>'
              + f'<div class="block"><h2>So richten Sie den Zugang ein</h2><ol class="schritte">{liste}</ol></div>'
              + '<div class="block s-klein">Dieses Blatt enthält ein Passwort: bitte persönlich übergeben und nach der '
                'ersten Anmeldung vernichten. Bei Problemen hilft die Administration.</div>'
              + "<style>.mono { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 12pt; }"
                " .schritte li { margin-bottom: 2mm; }</style>")
    return html_zu_pdf(seite("Zugang zu EPM", inhalt, fuss, None, rechts))


# --------------------------------------------------------------------------------------------- F61 Passwortblatt
def sicherungs_passwortblatt_pdf(passwort: str, nr: int, aktuell: bool, gesetzt_am: str, gesetzt_von: str,
                                 verfahren: str, adresse: str, aufbewahrung_tage: int, versionen: list) -> bytes:
    """Blatt für den Tresor (Festlegung 02.10.2026): das Sicherungs-Passwort und wie man ohne EPM an die Daten kommt.
    Das Passwort kommt aus der Oberfläche und ist vorher gegen den Prüfwert des Servers geprüft."""
    kopf, fuss, rechts = _kopf_fuss()
    angaben = [("Passwort Nr.", f"{nr}" + ("" if aktuell else " (nicht mehr das aktuelle)")),
               ("festgelegt", f"{gesetzt_am} von {gesetzt_von}" if gesetzt_von else gesetzt_am),
               ("EPM", adresse), ("Verfahren", verfahren or "GnuPG (OpenPGP), AES-256, symmetrisch")]
    felder = "".join(f'<tr><td class="label" style="width:30%">{html.escape(a)}</td><td class="wert">{_e(b)}</td></tr>'
                     for a, b in angaben)
    gruppen = ""
    if " " not in passwort:
        teile = [passwort[i:i + 4] for i in range(0, len(passwort), 4)]
        gruppen = ('<div class="gruppen">' + "".join(f"<span>{html.escape(t)}</span>" for t in teile)
                   + '</div><div class="s-klein">dasselbe in Vierergruppen zum Abschreiben – die Lücken gehören nicht '
                     'zum Passwort</div>')
    zeilen = [[html.escape(str(v.get("nr", ""))), html.escape(v.get("gesetzt_am") or ""),
               html.escape(v.get("gesetzt_von") or ""), html.escape(str(v.get("sicherungen", 0)))] for v in versionen]
    befehle = "\n".join([
        "sha256sum -c epm_<Stempel>.sha256",
        "gpg -d -o epm-db_<Stempel>.dump epm-db_<Stempel>.dump.gpg",
        "gpg -d -o epm-dokumente_<Stempel>.tar.gz epm-dokumente_<Stempel>.tar.gz.gpg",
        "gpg -d -o epm-loeschliste_<Stempel>.jsonl epm-loeschliste_<Stempel>.jsonl.gpg",
    ])
    inhalt = (
        kopf + _titel("Sicherungs-Passwort", f"Nr. {nr} · gedruckt {datum(timezone.localdate())}")
        + f'<div class="block"><div class="passwort">{html.escape(passwort)}</div>{gruppen}</div>'
        + f'<div class="block"><table class="felder">{felder}</table></div>'
        + _abschnitt("Wofür", "<p>Mit diesem Passwort sind die Sicherungen von EPM verschlüsselt – Datenbank, Dokumente "
                              "und Löschliste, auf dem Server und in der Nextcloud bzw. auf der NAS. Ohne das Passwort "
                              "lassen sich diese Sicherungen nicht mehr lesen; niemand kann es wiederherstellen.</p>")
        + _abschnitt("Aufbewahren", "<p>Im Tresor aufbewahren, nie zusammen mit den Sicherungen. Nicht fotografieren, "
                                    "nicht per E-Mail oder Chat weitergeben. Ein neues Passwort gilt ab der nächsten "
                                    f"Sicherung; ältere Sicherungen bleiben mit ihrem Passwort verschlüsselt. Dieses Blatt "
                                    f"daher aufheben, bis es keine Sicherung mit Nr. {nr} mehr gibt – auf dem Server "
                                    f"{aufbewahrung_tage} Tage, in der Nextcloud und auf der NAS so lange, wie die "
                                    "Dateien dort liegen.</p>")
        + _abschnitt("Zurückspielen", "<p>In EPM: Administration › Backup › „Wiederherstellen“ (das Passwort liegt auf "
                                      "dem Server, hier wird es nicht gebraucht). Ohne EPM, z. B. auf einem neuen Server, "
                                      "eine Sicherung erst prüfen, dann jede Datei mit diesem Passwort entschlüsseln:</p>"
                                      f'<pre class="befehle">{html.escape(befehle)}</pre>'
                                      "<p>Danach die Datenbank mit <i>pg_restore</i> einspielen, die Dokumente nach "
                                      "/srv/epm/data/dokumente auspacken und die neueste Löschliste nach "
                                      "/srv/epm/data/loeschliste/loeschliste.jsonl legen (nie die Löschliste eines anderen "
                                      "Systems).</p>")
        + (_abschnitt("Passwörter, mit denen noch Sicherungen verschlüsselt sind",
                      _tabelle(["Nr.", "festgelegt", "von", "Sicherungen"], zeilen, ["14mm", "40mm", None, "28mm"]))
           if zeilen else "")
        + '<div class="block s-klein">Dieses Blatt enthält ein Passwort: nicht kopieren, nicht weitergeben. Bei Verlust '
          'sofort unter Administration › Backup ein neues Sicherungs-Passwort festlegen.</div>'
        + "<style>.passwort { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 15pt;"
          " word-break: break-all; padding: 3mm 4mm; border: 0.4mm solid #251F53; border-radius: 2mm; }"
          " .gruppen { margin-top: 2mm; font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 12pt; }"
          " .gruppen span { margin-right: 4mm; }"
          " .befehle { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 8.5pt;"
          " white-space: pre-wrap; margin: 1mm 0; }</style>")
    return html_zu_pdf(seite("Sicherungs-Passwort", inhalt, fuss, None, rechts))
