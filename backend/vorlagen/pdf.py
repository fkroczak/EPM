"""PDF-Erzeugung (F51): Vorlagenblöcke → HTML → PDF mit WeasyPrint.

Offline: Es werden keine externen Ressourcen geladen (nur eingebettete data:-URLs, z. B. das Logo).
Schrift: IBM Plex Sans aus dem Image (backend/schriften/, ins Image kopiert), wie in der Oberfläche.
"""
import base64
import hashlib
import html
import re
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile

from .bloecke import PLATZHALTER
from .felder import FELDER, TABELLEN, Kontext, tabellenzeilen

STANDARD_LOGO = Path(__file__).resolve().parent / "statisch" / "logo-stiftung.png"
LEER = "—"

CSS = """
@page { size: A4; margin: 15mm 17mm %(unten)smm 17mm;
  @bottom-left { content: %(fusszeile)s; white-space: pre; vertical-align: top; padding-top: 4mm;
                 font-family: "IBM Plex Sans", "DejaVu Sans", sans-serif; font-size: 7pt; line-height: 1.45; color: #00325a;
                 width: 150mm; }
  @bottom-right { content: %(rechts)s; vertical-align: top; padding-top: 4mm;
                  font-family: "IBM Plex Sans", "DejaVu Sans", sans-serif; font-size: 7pt; color: #00325a; } }
html { font-family: "IBM Plex Sans", "DejaVu Sans", sans-serif; font-size: 9.5pt; color: #1b1932; line-height: 1.4; }
body { margin: 0; }
.block { margin: 0 0 4.5mm 0; }
.briefkopf { display: flex; justify-content: space-between; align-items: flex-end; gap: 8mm; padding-bottom: 3mm;
             border-bottom: 0.5mm solid; }
.briefkopf img { height: 19mm; max-width: 62mm; object-fit: contain; object-position: left bottom; }
.falzmarke { position: fixed; left: -12mm; width: 2mm; height: 0; border-top: 0.2mm solid #828282; }
.spalten { display: flex; justify-content: space-between; gap: 10mm; }
.spalten .rechts { text-align: right; color: #00325a; }
.spalten .rechts.klein { font-size: 8pt; line-height: 1.5; }
.absender { text-align: right; font-size: 7.5pt; color: #3b3953; line-height: 1.45; }
.titel { display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 1mm; }
.titel h1 { font-size: 15pt; font-weight: 600; margin: 0; }
.titel .zusatz { font-size: 9.5pt; }
.titel .zusatz span { color: #5d5b72; }
h2 { font-size: 8pt; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; color: #5d5b72; margin: 0 0 1.5mm 0; }
table { width: 100%%; border-collapse: collapse; }
.felder td { vertical-align: top; padding: 0.9mm 2.5mm 0.9mm 0; border-bottom: 0.4pt solid #ececf2; }
.felder td.label { color: #5d5b72; }
.felder .wert p { margin: 0 0 1mm 0; }
.tabelle th { text-align: left; font-size: 7.5pt; font-weight: 600; color: #5d5b72; border-bottom: 0.6pt solid #c9c8d4;
              padding: 1mm 2mm 1mm 0; }
.tabelle td { border-bottom: 0.4pt solid #e6e5ee; padding: 1.2mm 2mm 1.2mm 0; vertical-align: top; }
.leer { color: #5d5b72; font-style: italic; }
hr { border: 0; border-top: 0.6pt solid #c9c8d4; margin: 0 0 4.5mm 0; }
.unterschrift .linie { margin-top: 12mm; width: 75mm; border-top: 0.6pt solid #1b1932; padding-top: 1mm;
                       font-size: 7.5pt; color: #5d5b72; }
.s-klein { font-size: 8pt; } .s-gross { font-size: 11.5pt; }
.fett { font-weight: 600; } .kursiv { font-style: italic; }
.a-mitte { text-align: center; } .a-rechts { text-align: right; }
.zusammen { break-inside: avoid; }
.umbruch { break-before: page; }
.wasserzeichen { position: fixed; top: 105mm; left: 0; right: 0; text-align: center; font-size: 80pt; font-weight: 700;
                 letter-spacing: .12em; color: rgba(0, 0, 0, .07); transform: rotate(-30deg); }
.richtext ul, .richtext ol { margin: 0 0 1mm 0; padding-left: 5mm; }
.richtext h1, .richtext h2, .richtext h3 { font-size: 10pt; margin: 1.5mm 0 1mm 0; text-transform: none; color: #1b1932;
                                          letter-spacing: 0; }
"""


def nur_eingebettet(url, *args, **kwargs):
    """URL-Fetcher für WeasyPrint: nur data:-URLs, keine Netzwerk- oder Dateizugriffe."""
    if not url.startswith("data:"):
        raise ValueError("Externe Ressourcen sind in EPM-PDFs nicht erlaubt.")
    from weasyprint import default_url_fetcher

    return default_url_fetcher(url)


def logo_data_uri() -> str:
    from stammdaten.models import Logo

    logo = Logo.aktuell()
    if logo is not None:
        pfad = settings.EPM_DOKUMENTE / logo.datei
        if pfad.is_file():
            return f"data:{logo.mime};base64,{base64.b64encode(pfad.read_bytes()).decode()}"
    return "data:image/png;base64," + base64.b64encode(STANDARD_LOGO.read_bytes()).decode()


def _absender():
    from stammdaten.models import Absenderangaben, Einstellungen

    return Absenderangaben.alle()[Einstellungen.aktuell().absender]


def briefkopf_html(absender_zeigen=True, linienfarbe="#251F53", falzmarken=False) -> str:
    a = _absender()
    zeilen = [a.name, f"{a.strasse} · {a.plz} {a.ort}".strip(" ·"),
              " · ".join(t for t in (a.telefon and f"Tel. {a.telefon}", a.fax and f"Fax {a.fax}") if t),
              " · ".join(t for t in (a.email, a.internet) if t)]
    absender = "<br>".join(html.escape(z) for z in zeilen if z) if absender_zeigen else ""
    farbe = linienfarbe if re.fullmatch(r"#[0-9A-Fa-f]{6}", linienfarbe or "") else "#251F53"
    # Falzmarken (DIN 5008, wie im Altsystem bei 99 / 148,5 / 198 mm); bezogen auf den Seitenbereich ab 15 mm Rand
    marken = "".join(f'<div class="falzmarke" style="top:{y - 15}mm"></div>' for y in (99, 148.5, 198)) if falzmarken else ""
    return (f'{marken}<div class="briefkopf" style="border-color:{farbe}"><img src="{logo_data_uri()}" alt="Logo">'
            f'<div class="absender">{absender}</div></div>')


def _css_string(text: str) -> str:
    """CSS-Zeichenkette; Zeilenumbrüche als \\A (mit white-space: pre in der Fußzeile)."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\A ") + '"'


def fusszeile_css(text: str | None) -> str:
    """Fußzeilentext → CSS-``content`` mit Seitenzählern ({Seite}, {Seiten})."""
    if not text:
        return '""'
    teile = []
    for stueck in re.split(r"(\{Seite\}|\{Seiten\})", text):
        if stueck == "{Seite}":
            teile.append("counter(page)")
        elif stueck == "{Seiten}":
            teile.append("counter(pages)")
        elif stueck:
            teile.append(_css_string(stueck))
    return " ".join(teile) or '""'


class Ersetzer:
    """Setzt Platzhalter ein: Text wird maskiert, HTML-Felder (bereinigt gespeichert) bleiben HTML."""

    def __init__(self, art: str, kontext: Kontext):
        self.felder = FELDER[art]
        self.k = kontext

    def wert(self, name):
        feld = self.felder.get(name)
        if feld is None:
            return None, False
        try:
            w = feld.wert(self.k)
        except AttributeError:
            w = None
        return (w if w not in ("", None) else None), feld.html

    def __call__(self, text: str, html_erlaubt=True, leer_zeichen=LEER):
        """→ (html, alle_leer). ``alle_leer`` ist True, wenn es Platzhalter gibt und keiner einen Wert hat."""
        stuecke, namen, gefuellt = [], 0, 0
        pos = 0
        for m in PLATZHALTER.finditer(text or ""):
            stuecke.append(self._statisch(text[pos:m.start()]))
            namen += 1
            w, ist_html = self.wert(m.group(1).strip())
            if w is None:
                stuecke.append(leer_zeichen)
            else:
                gefuellt += 1
                stuecke.append(f'<div class="richtext">{w}</div>' if ist_html and html_erlaubt
                               else self._statisch(str(w)))
            pos = m.end()
        stuecke.append(self._statisch((text or "")[pos:]))
        alle_leer = namen > 0 and gefuellt == 0
        if alle_leer and leer_zeichen:
            return leer_zeichen, True  # z. B. „— · —“ wird zu „—“
        return "".join(stuecke), alle_leer

    def zeilen(self, text: str) -> tuple[str, bool]:
        """Mehrzeiliger Text: Zeilen, deren Datenfelder alle leer sind und die sonst nichts Wesentliches enthalten
        (z. B. „* {{Patient.Geburtsdatum}}“ ohne Datum), entfallen ganz."""
        ausgabe, alle_leer, gesehen = [], True, False
        for zeile in (text or "").split("\n"):
            inhalt, leer = self(zeile, leer_zeichen="")
            if PLATZHALTER.search(zeile):
                gesehen = True
                rest = PLATZHALTER.sub("", zeile).strip(" *·,:;-–/")
                if leer and not rest:
                    continue
                alle_leer = alle_leer and leer
            ausgabe.append(inhalt)
        return "<br>".join(ausgabe), gesehen and alle_leer

    def text(self, text: str) -> str:
        """Nur Text (Fußzeile): Platzhalter ohne HTML einsetzen."""
        return PLATZHALTER.sub(lambda m: str(self.wert(m.group(1).strip())[0] or ""), text or "")

    @staticmethod
    def _statisch(t: str) -> str:
        return html.escape(t).replace("\n", "<br>")


def _klassen(b) -> str:
    o = b.get("optionen") or {}
    k = ["block"]
    if o.get("schrift") in ("klein", "gross"):
        k.append(f"s-{o['schrift']}")
    if o.get("fett"):
        k.append("fett")
    if o.get("kursiv"):
        k.append("kursiv")
    if o.get("ausrichtung") in ("mitte", "rechts"):
        k.append(f"a-{o['ausrichtung']}")
    if o.get("nicht_teilen"):
        k.append("zusammen")
    return " ".join(k)


def _feldtabelle(ersetze, eintraege, spalten) -> tuple[str, bool]:
    """Bezeichnung links, Wert rechts (wie im Entwurf); ``spalten`` Paare nebeneinander."""
    zellen, alle_leer = [], True
    breite = 100 / spalten
    for e in eintraege:
        wert, leer = ersetze(e.get("wert", ""))
        alle_leer = alle_leer and leer
        zellen.append(f'<td class="label" style="width:{breite * 0.36:.2f}%">{html.escape(e.get("label") or "")}</td>'
                      f'<td class="wert" style="width:{breite * 0.64:.2f}%">{wert}</td>')
    zeilen = ["<tr>" + "".join(zellen[i:i + spalten]) + "</tr>" for i in range(0, len(zellen), spalten)]
    return f'<table class="felder">{"".join(zeilen)}</table>', alle_leer


def bloecke_html(art: str, bloecke: list, kontext: Kontext) -> tuple[str, str | None, str | None]:
    """→ (Inhalt als HTML, Fußzeilentext links, Fußzeile rechts)."""
    ersetze = Ersetzer(art, kontext)
    teile, fuss, rechts = [], None, None
    for b in bloecke:
        typ = b.get("typ")
        o = b.get("optionen") or {}
        ausblenden = o.get("ausblenden_wenn_leer", False)
        kopf = f"<h2>{html.escape(b['bezeichnung'])}</h2>" if o.get("ueberschrift") and b.get("bezeichnung") else ""
        if typ == "briefkopf":
            teile.append(f'<div class="{_klassen(b)}">{briefkopf_html(b.get("absender", True), b.get("linienfarbe"), b.get("falzmarken", False))}</div>')
        elif typ == "zweispaltig":
            links, _ = ersetze.zeilen(b.get("links", ""))
            rechts, _ = ersetze.zeilen(b.get("rechts", ""))
            klein = " klein" if b.get("rechts_klein") else ""
            teile.append(f'<div class="{_klassen(b)} spalten"><div class="links">{links}</div>'
                         f'<div class="rechts{klein}">{rechts}</div></div>')
        elif typ == "titel":
            titel, _ = ersetze(b.get("text", ""), html_erlaubt=False)
            zusatz = ""
            if b.get("zusatz") or b.get("zusatz_label"):
                wert, leer = ersetze(b.get("zusatz", ""), html_erlaubt=False)
                zusatz = (f'<div class="zusatz"><span>{html.escape(b.get("zusatz_label") or "")}</span> {wert}</div>')
            teile.append(f'<div class="{_klassen(b)} titel"><h1>{titel}</h1>{zusatz}</div>')
        elif typ == "text":
            inhalt, leer = ersetze.zeilen(b.get("text", ""))
            if leer and ausblenden:
                continue
            teile.append(f'<div class="{_klassen(b)}">{kopf}{inhalt}</div>')
        elif typ == "datenfelder":
            tabelle, leer = _feldtabelle(ersetze, b.get("felder") or [], b.get("spalten", 2))
            if leer and ausblenden:
                continue
            teile.append(f'<div class="{_klassen(b)}">{kopf}{tabelle}</div>')
        elif typ == "tabelle":
            quelle = b.get("quelle")
            spalten = TABELLEN[art][quelle][1]
            zeilen = tabellenzeilen(art, quelle, kontext)
            if not zeilen and ausblenden:
                continue
            kopfzeile = "".join(f"<th>{html.escape(s)}</th>" for s in spalten)
            koerper = ("".join("<tr>" + "".join(f"<td>{html.escape(str(z))}</td>" for z in zeile) + "</tr>" for zeile in zeilen)
                       or f'<tr><td class="leer" colspan="{len(spalten)}">keine Einträge</td></tr>')
            teile.append(f'<div class="{_klassen(b)}">{kopf}<table class="tabelle"><thead><tr>{kopfzeile}</tr></thead>'
                         f"<tbody>{koerper}</tbody></table></div>")
        elif typ == "trennlinie":
            teile.append("<hr>")
        elif typ == "leerraum":
            teile.append(f'<div style="height:{int(b.get("hoehe_mm", 6))}mm"></div>')
        elif typ == "unterschrift":
            felder = ""
            if b.get("felder"):
                felder, _ = _feldtabelle(ersetze, b["felder"], len(b["felder"]) if len(b["felder"]) <= 4 else 2)
            linie = f'<div class="linie">{html.escape(b.get("linie") or "Unterschrift")}</div>'
            teile.append(f'<div class="{_klassen(b)} unterschrift">{kopf}{felder}{linie}</div>')
        elif typ == "seitenumbruch":
            teile.append('<div class="umbruch"></div>')
        elif typ == "fusszeile":
            fuss = ersetze.text(b.get("text", ""))
            rechts = ersetze.text(b.get("rechts", ""))
    return "".join(teile), fuss, rechts


def seite(titel: str, inhalt: str, fusszeile: str | None = None, wasserzeichen: str | None = None,
          rechts: str | None = "{Seite}/{Seiten}") -> str:
    zeichen = f'<div class="wasserzeichen">{html.escape(wasserzeichen)}</div>' if wasserzeichen else ""
    zeilen = (fusszeile or "").count("\n") + 1 if fusszeile else 1
    css = CSS % {"fusszeile": fusszeile_css(fusszeile), "rechts": fusszeile_css(rechts),
                 "unten": f"{max(18, 10 + 3.6 * zeilen):.0f}"}
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{html.escape(titel)}</title>'
            f'<meta name="author" content="EPM"><style>{css}</style></head>'
            f"<body>{zeichen}{inhalt}</body></html>")


def html_zu_pdf(dokument_html: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=dokument_html, url_fetcher=nur_eingebettet).write_pdf()


def wasserzeichen_fuer(patient, plan=None, vorschau=False) -> str | None:
    if vorschau or (plan is not None and plan.status == "entwurf"):
        return "ENTWURF"
    if patient is not None and patient.ist_test:
        return "TESTDATEN"
    return None


def erzeuge_aus_vorlage(art: str, kontext: Kontext, vorlage=None, bloecke=None, wasserzeichen=None,
                        titel: str = "") -> tuple[bytes, int | None]:
    """PDF aus der aktiven (oder übergebenen) Vorlage. → (PDF, Vorlagenversion)."""
    from .models import Dokumentvorlage

    if bloecke is None:
        vorlage = vorlage or Dokumentvorlage.aktive(art)
        bloecke = vorlage.bloecke
    inhalt, fuss, rechts = bloecke_html(art, bloecke, kontext)
    pdf = html_zu_pdf(seite(titel or Dokumentvorlage.Art(art).label, inhalt, fuss, wasserzeichen, rechts))
    return pdf, (vorlage.version if vorlage is not None else None)


def sha256(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def als_dokument(patient, pdf: bytes, titel: str, typ_wert: str, datum, benutzer, dateiname: str):
    """Legt die PDF als Dokument „Von EPM erzeugt“ in der Akte ab (Dateisystem + SHA-256)."""
    from patienten.api import speichere_datei
    from patienten.models import Dokument
    from stammdaten.models import Auswahlwert

    meta = speichere_datei(patient, ContentFile(pdf, name=dateiname), "application/pdf")
    typ = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.DOKUMENTTYP, wert=typ_wert).first()
    dok = Dokument(patient=patient, typ=typ, titel=titel[:200], datum=datum, hochgeladen_von=benutzer,
                   datum_quelle=Dokument.DatumQuelle.EINGABE, **meta)
    dok.herkunft = Dokument.Herkunft.SYSTEM
    dok._history_user = benutzer
    dok.save()
    return dok
