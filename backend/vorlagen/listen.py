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
    kopf_html = briefkopf_html(kopf.get("absender", True), kopf.get("linienfarbe"), kopf.get("falzmarken", False)) \
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


# --------------------------------------------------------------------------------------------- F24
BEREICHE = {"stammdaten": "Stammdaten", "diagnose": "Diagnose", "therapie": "Therapie", "empfehlung": "Empfehlung",
            "gewichte": "Gewicht", "kontakte": "Kontakt", "termine": "Termin", "dokumente": "Dokument",
            "infusionsplaene": "Infusionsplan", "bezugspersonen": "Bezugsperson", "aerzte": "Arzt"}


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
    angaben = [("Name", user.anzeigename), ("Benutzername", user.username), ("Einmal-Kennwort", kennwort),
               ("gültig bis", gueltig), ("Adresse", adresse)]
    felder = "".join(f'<tr><td class="label" style="width:35%">{html.escape(a)}</td>'
                     f'<td class="wert{" mono" if a in ("Benutzername", "Einmal-Kennwort") else ""}">{html.escape(b or "—")}</td></tr>'
                     for a, b in angaben)
    schritte = [
        "EPM im Browser öffnen (nur im Netz der Stiftung bzw. über das VPN erreichbar) und mit Benutzername und "
        "Einmal-Kennwort anmelden.",
        "Ein eigenes Kennwort wählen (mindestens 12 Zeichen). Das Einmal-Kennwort gilt danach nicht mehr.",
        "Die Authenticator-App auf dem Telefon öffnen (z. B. Microsoft oder Google Authenticator), den angezeigten "
        "QR-Code scannen und den 6-stelligen Code eingeben.",
        "Die 10 Notfall-Codes ausdrucken oder sicher aufbewahren. Sie ersetzen das Telefon, falls es verloren geht.",
    ]
    liste = "".join(f"<li>{html.escape(s)}</li>" for s in schritte)
    inhalt = (kopf + _titel("Zugang zu EPM", f"erstellt {datum(timezone.localdate())}")
              + f'<div class="block"><table class="felder">{felder}</table></div>'
              + f'<div class="block"><h2>So richten Sie den Zugang ein</h2><ol class="schritte">{liste}</ol></div>'
              + '<div class="block s-klein">Dieses Blatt enthält ein Kennwort: bitte persönlich übergeben und nach der '
                'ersten Anmeldung vernichten. Bei Problemen hilft die Administration.</div>'
              + "<style>.mono { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 12pt; }"
                " .schritte li { margin-bottom: 2mm; }</style>")
    return html_zu_pdf(seite("Zugang zu EPM", inhalt, fuss, None, rechts))
