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
from .felder import FELDER, TABELLEN, Fett, Kontext, tabellenspalten, tabellenzeilen

STANDARD_LOGO = Path(__file__).resolve().parent / "statisch" / "logo-stiftung.png"
STANDARD_LOGOS = {"rg": Path(__file__).resolve().parent / "statisch" / "logo-rgc.png"}
LEER = "—"

CSS = """
@page { size: A4; margin: 15mm 17mm %(unten)smm 17mm;
  @bottom-left { content: %(fusszeile)s; white-space: pre; vertical-align: top; padding-top: 4mm;
                 font-family: "IBM Plex Sans", "DejaVu Sans", sans-serif; font-size: 7pt; line-height: 1.45; color: #00325a;
                 width: 150mm; }
  @bottom-right { content: %(rechts)s; vertical-align: top; padding-top: 4mm;
                  font-family: "IBM Plex Sans", "DejaVu Sans", sans-serif; font-size: 7pt; color: #00325a; } }
html { font-family: "IBM Plex Sans", "DejaVu Sans", sans-serif; font-size: 9.5pt; color: #1b1932; line-height: 1.4;
       font-feature-settings: "tnum"; }
body { margin: 0; }
.block { margin: 0 0 3mm 0; }
.briefkopf { display: flex; justify-content: space-between; align-items: flex-end; gap: 8mm; padding-bottom: 3mm;
             border-bottom: 0.5mm solid; }
.briefkopf.ohne-linie { border-bottom: 0; padding-bottom: 1mm; }
.briefkopf img { height: 19mm; max-width: 62mm; object-fit: contain; object-position: left bottom; }
.falzmarke { position: fixed; left: -12mm; width: 2mm; height: 0; border-top: 0.2mm solid #828282; }
.spalten { display: flex; justify-content: space-between; gap: 10mm; }
.spalten .rechts { text-align: right; color: #00325a; }
.spalten .rechts.klein { font-size: 8pt; line-height: 1.5; }
.absender { text-align: right; font-size: 7.5pt; color: #3b3953; line-height: 1.45; }
.titel { display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 1mm; }
.titel h1 { font-size: 1.58em; font-weight: 600; margin: 0; }
/* Ausrichtung des Titels: mitte/rechts stellt Titel und Zusatz untereinander */
.titel.a-mitte { flex-direction: column; align-items: center; }
.titel.a-rechts { flex-direction: column; align-items: flex-end; }
/* Titel rechts neben dem Logo */
.kopftitel { text-align: right; }
.kopftitel h1 { font-size: 1.58em; font-weight: 600; margin: 0 0 0.6mm 0; line-height: 1.2; }
.kopftitel .zusatz { font-size: 1em; }
.kopftitel .zusatz span { color: #3b3953; }
.titel .zusatz { font-size: 1em; }
.titel .zusatz span { color: #5d5b72; }
/* Größen in em: „Schrift klein/groß“ eines Blocks wirkt auf alles darin */
h2 { font-size: 1em; font-weight: 600; margin: 0 0 1.5mm 0; }
/* Bereiche mit Überschrift als Karte wie in der Oberfläche von EPM (Rand, runde Ecken, Kopfzeile der Tabelle hinterlegt) */
.karte { border: 0.6pt solid #d9d8e3; border-radius: 2mm; }
.karte > h2 { padding: 1.5mm 3.5mm 1.1mm 3.5mm; margin: 0; }
.karte > table { width: 100%%; }
.karte .befund th { background: #f1f0f6; border-top: 0.5pt solid #e6e5ee; border-bottom: 0.5pt solid #d9d8e3; }
.karte .befund tr:last-child td { border-bottom: 0; }
.karte .befund th:first-child, .karte .befund td:first-child,
.karte .felder td:first-child { padding-left: 3.5mm; }
.karte .befund th:last-child, .karte .befund td:last-child { padding-right: 3.5mm; }
.karte .ohne-kopf tr:first-child td { border-top: 0.5pt solid #e6e5ee; }
.karten-inhalt { padding: 1.2mm 3.5mm 1.6mm 3.5mm; border-top: 0.5pt solid #e6e5ee; }
.karten-inhalt .richtext p { margin: 0 0 1mm 0; }
table { width: 100%%; border-collapse: collapse; }
.felder td { vertical-align: top; padding: 0.7mm 2.5mm 0.7mm 0; border-bottom: 0.4pt solid #ececf2; }
.felder td.label { color: #5d5b72; }
/* mehrere Paare nebeneinander: Bezeichnung einzeilig („Volumen im Mischbeutel“ brach sonst mitten im Feld um) */
.felder.mehrspaltig td.label { white-space: nowrap; padding-right: 3mm; }
.felder .wert p { margin: 0 0 1mm 0; }
.tabelle th { text-align: left; font-size: 7.5pt; font-weight: 600; color: #5d5b72; border-bottom: 0.6pt solid #c9c8d4;
              padding: 1mm 2mm 1mm 0; }
.tabelle td { border-bottom: 0.4pt solid #e6e5ee; padding: 1.2mm 2mm 1.2mm 0; vertical-align: top; }
/* Laborbefund: Bezeichnung, Wert rechtsbündig, Einheit in eigener Spalte, Rest */
.befund { font-size: 0.95em; }
/* fax-tauglich (Pläne gehen per Fax/Mail): Einheiten und Bezeichnungen dunkel, nichts nur über Farbe */
.befund th { text-align: left; font-size: 0.83em; font-weight: 500; color: #3b3953; border-bottom: 0.6pt solid #d9d8e3;
             padding: 0.9mm 2.5mm 0.8mm 2.5mm; }
.befund td { border-bottom: 0.4pt solid #ececf2; padding: 0.6mm 2.5mm; vertical-align: top; line-height: 1.3; }
.befund .b { width: 40mm; }
.befund .zahl { text-align: right; width: 17mm; white-space: nowrap; }
.befund .einheit { width: 12mm; white-space: nowrap; }
.befund .fett { font-weight: 600; }
.befund td.leer { font-style: italic; }
.befund .wert p { margin: 0 0 1mm 0; }
.bilanz .zahl { width: 30mm; }
/* zwei Blöcke nebeneinander */
.paar { display: flex; justify-content: space-between; align-items: flex-start; }
.paar .b, .paar .befund .b { width: auto; white-space: nowrap; }
/* Kopfkarte wie der Kopf der Akte in EPM */
.kopfkarte { border: 0.6pt solid #d9d8e3; border-radius: 2mm; padding: 2.3mm 3.5mm 2mm; }
.kopfkarte .oben { display: flex; justify-content: space-between; gap: 8mm; align-items: flex-start; }
.kopfkarte .name { font-size: 1.37em; font-weight: 600; line-height: 1.25; }
.kopfkarte .unter { color: #3b3953; font-size: 0.95em; margin-top: 0.6mm; line-height: 1.45; }
.kopfkarte .rechts { text-align: right; font-size: 0.79em; color: #00325a; line-height: 1.45; }
.kopfkarte .zahlen { width: 100%%; border-collapse: collapse; margin-top: 2mm; border-top: 0.5pt solid #e6e5ee; }
.kopfkarte .zahlen td { vertical-align: top; padding: 1.6mm 3mm 0 3mm; border-left: 0.5pt solid #e1e0ea; }
.kopfkarte .zahlen td:first-child { padding-left: 0; border-left: 0; }
.kopfkarte .zahlen .l { display: block; font-size: 0.74em; color: #3b3953; font-weight: 500; }
.kopfkarte .zahlen .w { display: block; font-size: 1em; }
.linie-oben { border-top: 0.6pt solid #d9d8e3; padding-top: 1.8mm; margin-top: 3mm; }
.leer { color: #5d5b72; font-style: italic; }
hr { border: 0; border-top: 0.6pt solid #c9c8d4; margin: 0 0 3.5mm 0; }
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
    # ohne hochgeladenes Logo: das mitgelieferte der aktiven Firma (Regeneration Clinic: eigenes, 11.10.2026)
    from epm.firma import aktive_firma

    firma = aktive_firma()
    standard = STANDARD_LOGOS.get(firma.kuerzel if firma else "", STANDARD_LOGO)
    return "data:image/png;base64," + base64.b64encode(standard.read_bytes()).decode()


def _absender():
    from stammdaten.models import Absenderangaben, Einstellungen

    return Absenderangaben.aktuelle()  # je Firma (11.10.2026)


def briefkopf_html(absender_zeigen=True, linienfarbe="#251F53", falzmarken=False, linie=True, rechts_html=None) -> str:
    a = _absender()
    zeilen = [a.name, f"{a.strasse} · {a.plz} {a.ort}".strip(" ·"),
              " · ".join(t for t in (a.telefon and f"Tel. {a.telefon}", a.fax and f"Fax {a.fax}") if t),
              " · ".join(t for t in (a.email, a.internet) if t)]
    absender = "<br>".join(html.escape(z) for z in zeilen if z) if absender_zeigen else ""
    rechts = rechts_html if rechts_html is not None else f'<div class="absender">{absender}</div>'
    farbe = linienfarbe if re.fullmatch(r"#[0-9A-Fa-f]{6}", linienfarbe or "") else "#251F53"
    # Falzmarken (DIN 5008, wie im Altsystem bei 99 / 148,5 / 198 mm); bezogen auf den Seitenbereich ab 15 mm Rand
    marken = "".join(f'<div class="falzmarke" style="top:{y - 15}mm"></div>' for y in (99, 148.5, 198)) if falzmarken else ""
    klasse = "briefkopf" if linie else "briefkopf ohne-linie"
    return (f'{marken}<div class="{klasse}" style="border-color:{farbe}"><img src="{logo_data_uri()}" alt="Logo">'
            f'{rechts}</div>')


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
            inhalt = _trenner(inhalt)
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


def _trenner(text: str) -> str:
    """Trennpunkte um leere Werte entfernen: „weiblich ·  · Münster“ → „weiblich · Münster“."""
    text = re.sub(r"(?:\s*·\s*){2,}", " · ", text)
    return re.sub(r"^\s*·\s*|\s*·\s*$", "", text)


ZAHL_EINHEIT = re.compile(r"^(−?-?[\d.,]+)\s+([^\s<>]{1,12})$")


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
    if o.get("linie_oben"):
        k.append("linie-oben")
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
    klasse = "felder mehrspaltig" if spalten > 1 else "felder"
    return f'<table class="{klasse}">{"".join(zeilen)}</table>', alle_leer


def _befundliste(ersetze, eintraege, spaltenkoepfe=False) -> tuple[str, bool]:
    """Datenfelder wie im Laborbefund: Bezeichnung | Wert rechtsbündig | Einheit; Texte über die Wertspalten."""
    zeilen, alle_leer = [], True
    for e in eintraege:
        wert, leer = ersetze(e.get("wert", ""))
        alle_leer = alle_leer and leer
        label = f'<td class="b">{html.escape(e.get("label") or "")}</td>'
        m = ZAHL_EINHEIT.match(wert)
        if m:
            zeilen.append(f'<tr>{label}<td class="zahl">{m.group(1)}</td><td class="einheit">{m.group(2)}</td><td></td></tr>')
        elif leer:
            zeilen.append(f'<tr>{label}<td class="zahl">{LEER}</td><td class="einheit"></td><td></td></tr>')
        else:
            zeilen.append(f'<tr>{label}<td class="wert" colspan="3">{wert}</td></tr>')
    kopf = ('<thead><tr><th class="b">Bestandteil</th><th class="zahl">Menge</th><th class="einheit">Einheit</th>'
            '<th></th></tr></thead>') if spaltenkoepfe else ""
    klasse = "befund" if spaltenkoepfe else "befund ohne-kopf"
    return f'<table class="{klasse}">{kopf}<tbody>{"".join(zeilen)}</tbody></table>', alle_leer


def _kopfkarte(ersetze, b) -> str:
    name, _ = ersetze(b.get("text", ""), html_erlaubt=False)
    unter, _ = ersetze.zeilen(b.get("untertitel", ""))
    rechts, _ = ersetze.zeilen(b.get("rechts", ""))
    zellen = []
    for e in b.get("felder") or []:
        wert, _ = ersetze(e.get("wert", ""), html_erlaubt=False)
        zellen.append(f'<td><span class="l">{html.escape(e.get("label") or "")}</span><span class="w">{wert}</span></td>')
    zahlen = f'<table class="zahlen"><tr>{"".join(zellen)}</tr></table>' if zellen else ""
    return (f'<div class="kopfkarte"><div class="oben"><div><div class="name">{name}</div>'
            f'{f"<div class=unter>{unter}</div>" if unter else ""}</div>'
            f'{f"<div class=rechts>{rechts}</div>" if rechts else ""}</div>{zahlen}</div>')


BREITEN = {"drittel": 34, "haelfte": 48.5, "zwei_drittel": 63}


def _nebeneinander(teile: list[tuple[str, str | None]]) -> str:
    """Blöcke mit „neben_vorherigem“ mit dem Block davor in eine Zeile setzen."""
    gruppen: list[list[tuple[str, str | None]]] = []
    for inhalt, neben in teile:
        if neben and gruppen:
            gruppen[-1].append((inhalt, neben))
        else:
            gruppen.append([(inhalt, None)])
    ausgabe = []
    for g in gruppen:
        if len(g) == 1:
            ausgabe.append(g[0][0])
            continue
        abstand = 4
        rechts = [BREITEN[n] for _, n in g[1:]]
        erste = 100 - sum(rechts) - abstand * (len(g) - 1)
        if erste < 15:  # zu schmal: gleich verteilen
            rechts = [(100 - abstand * (len(g) - 1)) / len(g)] * (len(g) - 1)
            erste = rechts[0]
        breiten = [erste, *rechts]
        ausgabe.append('<div class="paar">' + "".join(f'<div style="width:{w:.1f}%">{inhalt}</div>'
                                                      for (inhalt, _), w in zip(g, breiten)) + "</div>")
    return "".join(ausgabe)


def _titel_html(ersetze, b) -> str:
    titel, _ = ersetze(b.get("text", ""), html_erlaubt=False)
    zusatz = ""
    if b.get("zusatz") or b.get("zusatz_label"):
        wert, _ = ersetze(b.get("zusatz", ""), html_erlaubt=False)
        zusatz = f'<div class="zusatz"><span>{html.escape(b.get("zusatz_label") or "")}</span> {wert}</div>'
    return f"<h1>{titel}</h1>{zusatz}"


def bloecke_html(art: str, bloecke: list, kontext: Kontext) -> tuple[str, str | None, str | None]:
    """→ (Inhalt als HTML, Fußzeilentext links, Fußzeile rechts)."""
    ersetze = Ersetzer(art, kontext)
    teile, fuss, rechts = [], None, None
    # Titel „neben dem Logo“: steht rechts im Briefkopf statt in einer eigenen Zeile
    hat_kopf = any(b.get("typ") == "briefkopf" for b in bloecke)
    titel_neben = next((b for b in bloecke if b.get("typ") == "titel" and b.get("neben_logo") and hat_kopf), None)
    for b in bloecke:
        typ = b.get("typ")
        o = b.get("optionen") or {}
        anzahl = len(teile)
        ausblenden = o.get("ausblenden_wenn_leer", False)
        kopf = f"<h2>{html.escape(b['bezeichnung'])}</h2>" if o.get("ueberschrift") and b.get("bezeichnung") else ""
        karte = " karte" if kopf else ""  # Bereich mit Überschrift als Karte wie in der Oberfläche von EPM
        if typ == "briefkopf":
            schrift = " ".join(k for k in _klassen(titel_neben).split() if k.startswith("s-") or k in ("fett", "kursiv")) \
                if titel_neben else ""
            klasse = f"kopftitel {schrift}".strip()
            neben = f'<div class="{klasse}">{_titel_html(ersetze, titel_neben)}</div>' if titel_neben else None
            teile.append(f'<div class="{_klassen(b)}">{briefkopf_html(b.get("absender", True), b.get("linienfarbe"), b.get("falzmarken", False), b.get("mit_linie", True), neben)}</div>')
        elif typ == "zweispaltig":
            links, _ = ersetze.zeilen(b.get("links", ""))
            # eigener Name: „rechts“ ist die rechte Fußzeile (ohne Fußzeilen-Block stand sonst die rechte Spalte unten)
            spalte, _ = ersetze.zeilen(b.get("rechts", ""))
            klein = " klein" if b.get("rechts_klein") else ""
            teile.append(f'<div class="{_klassen(b)} spalten"><div class="links">{links}</div>'
                         f'<div class="rechts{klein}">{spalte}</div></div>')
        elif typ == "titel":
            if b is titel_neben:
                continue
            teile.append(f'<div class="{_klassen(b)} titel">{_titel_html(ersetze, b)}</div>')
        elif typ == "text":
            inhalt, leer = ersetze.zeilen(b.get("text", ""))
            if leer and ausblenden:
                continue
            if kopf:
                inhalt = f'<div class="karten-inhalt">{inhalt}</div>'
            teile.append(f'<div class="{_klassen(b)}{karte}">{kopf}{inhalt}</div>')
        elif typ == "kopfkarte":
            teile.append(f'<div class="{_klassen(b)}">{kopf}{_kopfkarte(ersetze, b)}</div>')
        elif typ == "datenfelder":
            if b.get("darstellung") == "befund":
                tabelle, leer = _befundliste(ersetze, b.get("felder") or [], b.get("spaltenkoepfe", False))
            else:
                tabelle, leer = _feldtabelle(ersetze, b.get("felder") or [], b.get("spalten", 2))
            if leer and ausblenden:
                continue
            teile.append(f'<div class="{_klassen(b)}{karte}">{kopf}{tabelle}</div>')
        elif typ == "tabelle":
            quelle = b.get("quelle")
            spalten = tabellenspalten(art, quelle, kontext)
            ausrichtung = TABELLEN[art][quelle][2]
            zeilen = tabellenzeilen(art, quelle, kontext)
            if not zeilen and ausblenden:
                continue
            klassen = [(" b" if i == 0 else f" {a}" if a else "") for i, a in enumerate(ausrichtung)]

            def zelle(z, k):
                return f'<td class="{(k + (" fett" if isinstance(z, Fett) else "")).strip()}">{html.escape(str(z))}</td>'

            kopfzeile = "".join(f'<th class="{k.strip()}">{html.escape(s)}</th>' for s, k in zip(spalten, klassen))
            koerper = ("".join("<tr>" + "".join(zelle(z, k) for z, k in zip(zeile, klassen)) + "</tr>" for zeile in zeilen)
                       or f'<tr><td class="leer" colspan="{len(spalten)}">keine Einträge</td></tr>')
            art_klasse = "befund bilanz" if quelle == "bilanz" else "befund"
            teile.append(f'<div class="{_klassen(b)}{karte}">{kopf}<table class="{art_klasse}"><thead><tr>{kopfzeile}</tr></thead>'
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
        if len(teile) > anzahl:
            teile[-1] = (teile[-1], o.get("neben_vorherigem"))
    return _nebeneinander(teile), fuss, rechts


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
    from .models import Dokumentvorlage, art_name

    if bloecke is None:
        vorlage = vorlage or Dokumentvorlage.aktive(art)
        bloecke = vorlage.bloecke
    inhalt, fuss, rechts = bloecke_html(art, bloecke, kontext)
    pdf = html_zu_pdf(seite(titel or art_name(art), inhalt, fuss, wasserzeichen, rechts))
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
