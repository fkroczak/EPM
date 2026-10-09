"""Schreiben aus der Akte und aus dem Kalender (Vorlagen von Alice Hessel, 09.10.2026; F172–F174).

Aus einer Dokumentvorlage mit E-Mail-Block entstehen
- die PDF (zum Drucken, Faxen oder als Anhang) und
- eine fertige E-Mail als ``.eml`` mit Empfänger, Betreff, Text und der PDF (und gewählten Anlagen) im Anhang.
  Outlook öffnet die Datei dank ``X-Unsent: 1`` als Entwurf, der nur noch abgeschickt werden muss; ein
  ``mailto:``-Link kann keine Anhänge mitgeben.

Die Reisebescheinigung gehört mit dem ärztlichen Attest des ADAC zusammen: Das Formular hängt als zweite Seite an,
Name, Ort und Datum sind schon eingetragen, die übrigen Felder bleiben ausfüllbar.
"""
import html
import io
import re
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate
from pathlib import Path

from .bloecke import PLATZHALTER
from .felder import FELDER, Kontext, datum
from .models import Dokumentvorlage
from .pdf import erzeuge_aus_vorlage

ADAC_ATTEST = Path(__file__).resolve().parent / "statisch" / "adac-attest.pdf"
ATTEST_FELDER = {
    "name": "Name des PatientenPatients namenom du patientnombre del paciente",
    "ort": "Ortplacelugar",
    "datum": "Datumdatefecha",
    "tage": ("Tage", "Days", "Jours", "Dias"),
}

# Schreiben aus der Akte (je Patient) und ob sie einen Termin brauchen
AUS_DER_AKTE = {
    Dokumentvorlage.Art.PATIENTENAUFNAHME: {"termin": False, "beschreibung": "Welche Daten und Unterlagen wir vorab brauchen"},
    Dokumentvorlage.Art.TERMINBESTAETIGUNG: {"termin": True, "beschreibung": "Termin in der Praxis Dr. Holtmeier, "
                                             "Gesundheitskarte mitbringen, keine Überweisung nötig"},
    Dokumentvorlage.Art.REISEBESCHEINIGUNG: {"termin": False, "beschreibung": "Briefkopf Dr. Holtmeier, deutsch/englisch, "
                                             "mit ärztlichem Attest des ADAC"},
}


def schreiben_aus_akte(art) -> dict | None:
    """Feste Schreiben und aktive eigene Schreiben (F176): → {"termin": bool} oder None."""
    if art in AUS_DER_AKTE:
        return AUS_DER_AKTE[art]
    from .models import EigenesSchreiben

    e = EigenesSchreiben.objects.filter(schluessel=art, aktiv=True).first() if isinstance(art, str) else None
    return {"termin": e.mit_termin, "beschreibung": e.beschreibung} if e else None


def _klartext(wert: str) -> str:
    """Bereinigtes HTML der Akte (Diagnose, Bemerkung …) als Text für die E-Mail."""
    wert = re.sub(r"<\s*(br|/p|/li|/h[1-6])\s*/?>", "\n", wert, flags=re.I)
    wert = re.sub(r"<li[^>]*>", "• ", wert, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", wert)).strip()


def ersetze_text(art: str, kontext: Kontext, text: str) -> str:
    """Platzhalter als Text einsetzen (E-Mail): leere Werte entfallen, Zeilen nur aus leeren Feldern auch."""
    felder = FELDER[art]

    def wert(name):
        feld = felder.get(name)
        if feld is None:
            return ""
        try:
            w = feld.wert(kontext)
        except AttributeError:
            w = None
        if w in (None, ""):
            return ""
        return _klartext(str(w)) if feld.html else str(w)

    zeilen = []
    for zeile in (text or "").split("\n"):
        neu = PLATZHALTER.sub(lambda m: wert(m.group(1).strip()), zeile)
        if PLATZHALTER.search(zeile) and not neu.strip() and not PLATZHALTER.sub("", zeile).strip():
            continue
        zeilen.append(neu.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(zeilen)).strip()


def email_aus_vorlage(art: str, kontext: Kontext, bloecke=None) -> dict | None:
    """→ {"betreff", "text"} aus dem E-Mail-Block der aktiven Vorlage (None, wenn sie keinen hat)."""
    if bloecke is None:
        bloecke = Dokumentvorlage.aktive(art).bloecke
    block = next((b for b in bloecke if b.get("typ") == "email"), None)
    if block is None:
        return None
    return {"betreff": " ".join(ersetze_text(art, kontext, block.get("betreff", "")).split()),
            "text": ersetze_text(art, kontext, block.get("text", ""))}


def reise_attest(kontext: Kontext, ort: str = "Münster", tage: int | None = None) -> bytes:
    """Ärztliches Attest des ADAC (Medikamente und Material für die Reise) mit Name, Ort und Datum."""
    from pypdf import PdfReader, PdfWriter

    p = kontext.patient
    werte = {ATTEST_FELDER["name"]: f"{p.vorname} {p.nachname}" + (f", geb. {datum(p.geburtsdatum)}"
                                                                     if p.geburtsdatum else ""),
             ATTEST_FELDER["ort"]: ort, ATTEST_FELDER["datum"]: datum(kontext.heute)}
    if tage:
        werte.update({f: str(tage) for f in ATTEST_FELDER["tage"]})
    schreiber = PdfWriter(clone_from=PdfReader(ADAC_ATTEST))
    schreiber.update_page_form_field_values(schreiber.pages[0], werte, auto_regenerate=False)
    schreiber.set_need_appearances_writer(True)
    puffer = io.BytesIO()
    schreiber.write(puffer)
    return puffer.getvalue()


def anhaengen(pdf: bytes, weitere: list[bytes]) -> bytes:
    """PDFs hintereinander; Formularfelder der angehängten bleiben ausfüllbar."""
    from pypdf import PdfReader, PdfWriter

    schreiber = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    for daten in weitere:
        schreiber.append(PdfReader(io.BytesIO(daten)))
    schreiber.set_need_appearances_writer(True)
    puffer = io.BytesIO()
    schreiber.write(puffer)
    return puffer.getvalue()


def schreiben_pdf(art: str, kontext: Kontext, wasserzeichen=None, titel="", attest=True, ort="Münster",
                  tage=None) -> tuple[bytes, int | None]:
    pdf, version = erzeuge_aus_vorlage(art, kontext, wasserzeichen=wasserzeichen, titel=titel)
    if art == Dokumentvorlage.Art.REISEBESCHEINIGUNG and attest:
        pdf = anhaengen(pdf, [reise_attest(kontext, ort=ort, tage=tage)])
    return pdf, version


def eml(an: str, betreff: str, text: str, anhaenge: list[tuple[str, bytes]]) -> bytes:
    """E-Mail als Entwurf (``X-Unsent: 1``): Outlook öffnet sie zum Bearbeiten und Senden."""
    nachricht = EmailMessage(policy=SMTP)
    if an:
        nachricht["To"] = an
    nachricht["Subject"] = betreff
    nachricht["Date"] = formatdate(localtime=True)
    nachricht["X-Unsent"] = "1"
    nachricht.set_content(text)
    for dateiname, daten in anhaenge:
        nachricht.add_attachment(daten, maintype="application", subtype="pdf", filename=dateiname)
    return nachricht.as_bytes()


def eml_antwort(daten: bytes, dateiname: str):
    from urllib.parse import quote

    from django.http import HttpResponse

    antwort = HttpResponse(daten, content_type="message/rfc822")
    antwort["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(dateiname)}"
    antwort["Cache-Control"] = "private, no-store"
    antwort["X-Content-Type-Options"] = "nosniff"
    return antwort


def dateiname_sicher(text: str) -> str:
    return re.sub(r"[^\w.-]+", "-", text, flags=re.UNICODE).strip("-")[:80] or "Schreiben"


AUSGABEN = ("pdf", "email", "eml")


def anlagen_aus(ids) -> list:
    from .models import Anlage

    if ids in (None, ""):
        return []
    if not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise ValueError("Anlagen als Liste von Nummern angeben.")
    anlagen = list(Anlage.objects.filter(pk__in=ids, aktiv=True))
    if len(anlagen) != len(set(ids)):
        raise ValueError("Eine gewählte Anlage gibt es nicht (mehr).")
    return anlagen


def ausgeben(request, art: str, kontext: Kontext, dateiname: str, titel: str, wasserzeichen=None, an: str = "",
             pdf_optionen: dict | None = None):
    """Gemeinsame Ausgabe für Akte und Kalender: ``ausgabe`` = pdf | email (Vorschau des Textes) | eml.

    → (Antwort, PDF oder None). Bei ``eml`` dürfen Betreff, Text und Empfänger aus der Anfrage stammen (im Dialog
    angepasst); sonst gelten die Werte aus der Vorlage."""
    from rest_framework import status
    from rest_framework.response import Response

    from .api import pdf_antwort

    d = request.data
    ausgabe = d.get("ausgabe", "pdf")
    if ausgabe not in AUSGABEN:
        return Response({"ausgabe": "pdf, email oder eml."}, status=status.HTTP_400_BAD_REQUEST), None
    mail = email_aus_vorlage(art, kontext) or {"betreff": titel, "text": ""}
    if ausgabe == "email":
        return Response({"an": an, **mail, "dateiname": f"{dateiname}.pdf"}), None
    try:
        anlagen = anlagen_aus(d.get("anlagen")) if ausgabe == "eml" else []
    except ValueError as e:
        return Response({"anlagen": str(e)}, status=status.HTTP_400_BAD_REQUEST), None
    pdf, _ = schreiben_pdf(art, kontext, wasserzeichen=wasserzeichen, titel=titel, **(pdf_optionen or {}))
    if ausgabe == "pdf":
        return pdf_antwort(pdf, f"{dateiname}.pdf"), pdf
    fehler = {}
    for feld, laenge in (("betreff", 200), ("text", 20000), ("an", 300)):
        wert = d.get(feld)
        if wert is not None and (not isinstance(wert, str) or len(wert) > laenge):
            fehler[feld] = f"Text mit höchstens {laenge} Zeichen."
    if fehler:
        return Response(fehler, status=status.HTTP_400_BAD_REQUEST), None
    betreff = " ".join((d.get("betreff") if d.get("betreff") is not None else mail["betreff"]).split())
    text = d.get("text") if d.get("text") is not None else mail["text"]
    empfaenger = (d.get("an") if d.get("an") is not None else an).strip()
    anhaenge = [(f"{dateiname}.pdf", pdf)]
    for a in anlagen:
        if a.pfad.is_file():
            anhaenge.append((a.dateiname, a.pfad.read_bytes()))
    return eml_antwort(eml(empfaenger, betreff, text, anhaenge), f"{dateiname}.eml"), pdf
