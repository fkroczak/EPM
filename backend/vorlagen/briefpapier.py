"""Briefpapier einer Firma (14.10.2026): der gedruckte Briefkopf 1:1 wie auf dem Briefpapier der Klinik.

Statt Logo und Absender im Textfluss (``pdf.briefkopf_html``) liegt das Briefpapier auf jeder Seite: oben das farbige
Band mit Wellenkante, Logo und Anschrift, unten das Band mit Postanschrift und Registrierdaten. Auf der ersten Seite
stehen darunter die Absenderzeile, die Kontaktangaben und Ort mit Datum. Gewählt wird es im Baustein „Briefkopf“
(``"briefpapier": "rgc"``); ``"absender": false`` lässt die Angaben der ersten Seite weg.

Maße, Farben und Schriften stammen aus dem Briefpapier der Regeneration Clinic (PDF vom 14.10.2026, A4 = 595,3 × 841,9
pt): Positionen hier in pt wie im Original, die Wellenkante als derselbe Bézier-Pfad. Schriften: Inter (Briefkopf und
Fußband) und Carlito (Absenderzeile und Kontakt) aus ``backend/schriften``.
"""
import base64
import html
from dataclasses import dataclass, field
from pathlib import Path

ORDNER = Path(__file__).resolve().parent / "statisch" / "briefpapier"
PT = 25.4 / 72  # 1 pt in mm


@dataclass(frozen=True)
class Briefpapier:
    name: str
    farbe: str  # Bänder
    text: str  # Schrift in den Bändern
    logo: str  # Datei in statisch/briefpapier (PNG mit Transparenz)
    logo_pt: tuple  # x, y, Breite, Höhe
    kopf_pfad: str  # obere Fläche mit Wellenkante (SVG-Pfad in pt)
    fuss_pfad: str
    anschrift: list  # rechts im Kopfband; erste Zeile fett
    anschrift_rechts_pt: float
    anschrift_oben_pt: float
    fuss_links: list  # Fußband: erste Spalte (fett)
    fuss_rechts: list  # zweite Spalte (fett); "" = halbe Leerzeile
    fuss_x_pt: tuple
    fuss_oben_pt: tuple  # Oberkante der ersten Zeile je Spalte
    absenderzeile: str
    kontakt: list = field(default_factory=list)
    ort: str = ""
    # Seitenränder in mm (oben, rechts, unten, links): Text unter der Wellenkante und über dem Fußband
    raender: tuple = (47, 17.6, 31, 25)


BRIEFPAPIERE = {
    "rgc": Briefpapier(
        name="Briefpapier der Regeneration Clinic",
        farbe="#BDC9C2", text="#23272C", logo="rgc-logo.png", logo_pt=(35.708, 9.726, 198.118, 96.437),
        kopf_pfad="M -10.94 -8.2 L 606.39 -8.2 L 606.39 97.52 C 297.7 97.52 297.7 137.83 -10.94 114.95 Z",
        fuss_pfad="M -0.65 853.49 L -0.65 770.19 L 594.41 770.19 L 594.41 853.49 Z",
        anschrift=["Regeneration Clinic SIA", "Jana Asara iela 3", "LV-1009 Riga", "Latvia",
                   "info@regeneration-clinic.eu"],
        anschrift_rechts_pt=540.4, anschrift_oben_pt=20.8,
        fuss_links=["Regeneration Clinic SIA", "Postal Address:", "Gertrudes iela 53-7", "LV-1011 Riga", "Latvia"],
        fuss_rechts=["Registration No.: 40203593175", "", "Health Institution Code: 001000289",
                     "www.regeneration-clinic.eu", "info@regeneration-clinic.eu"],
        fuss_x_pt=(77.6, 297.1), fuss_oben_pt=(774.3, 779.1),
        absenderzeile="Regeneration Clinic SIA• Gertrudes iela 53-7 • LV-1011 Riga • Latvia",
        kontakt=["Prof. Dr. Markus Masin", "Director", "Telefon: +371 28717452",
                 "E-Mail: m.masin@regeneration-clinic.eu"],
        ort="Riga",
    ),
}


def auswahl() -> dict:
    """Kennung → Name (für die Prüfung der Blöcke und den Editor)."""
    return {k: b.name for k, b in BRIEFPAPIERE.items()}



# Schriftmaße von Inter: Oberkante der Zeile bis Grundlinie (Oberlänge 0,969 em); Zeilenabstand 1,21 em
OBERLAENGE = 0.969
ZEILE = 1.21


def css(kennung: str) -> str:
    """Seitenränder und Fußzeile für das Briefpapier; gilt für alle Seiten (nach dem allgemeinen ``@page``)."""
    b = BRIEFPAPIERE[kennung]
    oben, rechts, unten, links = b.raender
    return (f"@page {{ margin: {oben}mm {rechts}mm {unten}mm {links}mm; "
            # Postanschrift und Registrierdaten stehen im Fußband; die Seitenzahl bleibt rechts über dem Band
            "@bottom-left { content: none; } "
            "@bottom-right { padding-top: 0.6mm; vertical-align: top; } }"
            # ein Ersatzelement (SVG) wird nicht auf zwei Seiten verteilt – Text im Fußband bleibt auf seiner Seite
            ".briefpapier { position: fixed; z-index: -1; "
            f"left: -{links}mm; top: -{oben}mm; width: 210mm; height: 297mm; }}"
            ".briefpapier svg { display: block; width: 210mm; height: 297mm; }"
            '.briefpapier-erste { font-family: "Carlito", "IBM Plex Sans", "DejaVu Sans", sans-serif; '
            "color: #000; margin: 0 0 8mm 0; }"
            ".briefpapier-erste .zeile { font-size: 8pt; line-height: 10pt; margin: 0 0 4.6mm 0; }"
            ".briefpapier-erste .kontakt { font-size: 11pt; line-height: 13.4pt; "
            f"margin-left: {(313.4 * PT) - links:.2f}mm; }}"
            ".briefpapier-erste .kontakt p { margin: 0; }")


def _text(zeilen, x, oben, groesse, anker="start", fett_erste=False, alle_fett=False) -> str:
    """Zeilen als SVG-Text; ``oben`` = Oberkante der ersten Zeile in pt, "" = halbe Leerzeile."""
    teile, y = [], oben
    for i, z in enumerate(zeilen):
        if z == "":
            y += groesse * ZEILE / 2
            continue
        gewicht = "700" if alle_fett or (fett_erste and i == 0) else "400"
        teile.append(f'<text x="{x}" y="{y + groesse * OBERLAENGE:.2f}" text-anchor="{anker}" '
                     f'font-weight="{gewicht}">{html.escape(z)}</text>')
        y += groesse * ZEILE
    return "".join(teile)


def seiten_html(kennung: str) -> str:
    """Bänder, Logo, Anschrift und Fußband als eine Grafik in Seitengröße – fest positioniert, also auf jeder Seite."""
    b = BRIEFPAPIERE[kennung]
    logo = base64.b64encode((ORDNER / b.logo).read_bytes()).decode()
    x, y, w, h = b.logo_pt
    schrift = 'font-family="Inter, IBM Plex Sans, DejaVu Sans, sans-serif"'
    return (f'<div class="briefpapier"><svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 595.304 841.89">'
            f'<path fill="{b.farbe}" d="{b.kopf_pfad}"/><path fill="{b.farbe}" d="{b.fuss_pfad}"/>'
            f'<image x="{x}" y="{y}" width="{w}" height="{h}" xlink:href="data:image/png;base64,{logo}"/>'
            f'<g fill="{b.text}" {schrift} font-size="10">'
            f"{_text(b.anschrift, b.anschrift_rechts_pt, b.anschrift_oben_pt, 10, 'end', fett_erste=True)}</g>"
            f'<g fill="{b.text}" {schrift} font-size="8">'
            f"{_text(b.fuss_links, b.fuss_x_pt[0], b.fuss_oben_pt[0], 8, alle_fett=True)}"
            f"{_text(b.fuss_rechts, b.fuss_x_pt[1], b.fuss_oben_pt[1], 8, alle_fett=True)}</g></svg></div>")


def erste_seite_html(kennung: str, datum: str) -> str:
    """Absenderzeile, Kontakt und Ort mit Datum unter dem Kopfband (nur am Anfang des Dokuments)."""
    b = BRIEFPAPIERE[kennung]
    kontakt = "".join(f"<p>{html.escape(z)}</p>" for z in b.kontakt)
    ort = f"<p>&nbsp;</p><p>&nbsp;</p><p>{html.escape(b.ort)}, {html.escape(datum)}</p>" if b.ort else ""
    return (f'<div class="briefpapier-erste"><div class="zeile">{html.escape(b.absenderzeile)}</div>'
            f'<div class="kontakt">{kontakt}{ort}</div></div>')
