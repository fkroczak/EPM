"""Freie Gestaltung am Raster (14.10.2026): 6-Spalten-Raster, Kopf- und Fußband, Anschriftfeld nach DIN 5008.

Raster: Die Breite des Satzspiegels ist in 6 Spalten mit festem Abstand geteilt. Ein Block steht von Spalte
``raster_von`` bis ``raster_bis`` (ohne Angabe über die ganze Breite); ``neben_vorherigem: "raster"`` setzt ihn in die
Zeile des vorherigen Blocks. Mehr Arretierungspunkte gibt es bewusst nicht, damit die Dokumente einheitlich bleiben.
Dieselben Maße rechnet der Editor (``Dokumentvorlagen.tsx``), damit die Seite im Editor wie die PDF aussieht.

Kopfband: farbige Fläche oben (gerade, schräg, wellig oder als Bogen) mit Logo und Absender, wahlweise auf jeder
Seite oder nur auf der ersten; dazu auf Wunsch ein Fußband in derselben Farbe, auf dem die Fußzeile steht.

Anschriftfeld (DIN 5008, Fensterumschlag): Form A (hochgestellt) oder B (tiefgestellt), Rücksendeangabe, Anschrift und
Informationsblock rechts an den festen Stellen der ersten Seite; der Text des Dokuments beginnt darunter.
"""
import html

SPALTEN = 6
ABSTAND = 2.8  # Abstand zwischen den Spalten in % der Breite
SPALTE = (100 - (SPALTEN - 1) * ABSTAND) / SPALTEN


def raster_links(von: int) -> float:
    """Linke Kante von Spalte ``von`` in %."""
    return (von - 1) * (SPALTE + ABSTAND)


def raster_breite(von: int, bis: int) -> float:
    return (bis - von + 1) * SPALTE + (bis - von) * ABSTAND


def raster_von_bis(optionen: dict) -> tuple[int, int]:
    von = optionen.get("raster_von") or 1
    return von, optionen.get("raster_bis") or SPALTEN


def raster_zeile(teile: list[tuple[str, tuple[int, int]]]) -> str:
    """Blöcke einer Zeile an ihre Spalten setzen (Breite und Abstand zum vorherigen in %)."""
    ausgabe, rechts = [], 0.0
    for inhalt, (von, bis) in teile:
        links = raster_links(von)
        ausgabe.append(f'<div class="raster-zelle" style="margin-left:{links - rechts:.3f}%;'
                       f'width:{raster_breite(von, bis):.3f}%">{inhalt}</div>')
        rechts = links + raster_breite(von, bis)
    return '<div class="paar raster">' + "".join(ausgabe) + "</div>"


# ------------------------------------------------------------------------------------------------ Kopf- und Fußband
FORMEN = {"gerade": "Eckig (gerade Kante)", "schraeg": "Schräg", "welle": "Wellig", "bogen": "Bogen"}
BAND_SEITEN = {"alle", "erste"}
BAND_HOEHE = (20, 80)  # mm
BAND_ABSTAND = 6  # mm zwischen Band und Text


def band_pfad(form: str, breite: float, hoehe: float, schwung: float) -> str:
    """Fläche von oben bis zur Unterkante; die Unterkante liegt zwischen ``hoehe - schwung`` und ``hoehe``."""
    w, h, a = breite, hoehe, schwung
    if form == "schraeg":
        return f"M0 0 H{w} V{h - a:.2f} L0 {h} Z"
    if form == "welle":
        m, d = h - a / 2, a * 2 / 3
        return (f"M0 0 H{w} V{m:.2f} C{w * 5 / 6:.2f} {m + d:.2f} {w * 4 / 6:.2f} {m + d:.2f} {w / 2:.2f} {m:.2f} "
                f"S{w / 6:.2f} {m - d:.2f} 0 {m:.2f} Z")
    if form == "bogen":
        return f"M0 0 H{w} V{h - a:.2f} Q{w / 2:.2f} {h + a:.2f} 0 {h - a:.2f} Z"
    return f"M0 0 H{w} V{h} H0 Z"


def schwung(hoehe: float, fuss=False) -> float:
    return min(6 if fuss else 10, hoehe * 0.3)


def band_svg(form: str, breite: float, hoehe: float, farbe: str, gespiegelt=False) -> str:
    pfad = band_pfad(form, breite, hoehe, schwung(hoehe, gespiegelt))
    spiegel = f' transform="translate(0 {hoehe}) scale(1 -1)"' if gespiegelt else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {breite} {hoehe}" preserveAspectRatio="none" '
            f'style="display:block;width:{breite}mm;height:{hoehe}mm"><path fill="{farbe}" d="{pfad}"{spiegel}/></svg>')


# ------------------------------------------------------------------------------------------------ DIN 5008
# Maße in mm ab der linken oberen Ecke des Blatts: Anschriftfeld 85 × 45 (5 mm Rücksendeangabe, 12,7 mm Zusatz- und
# Vermerkzone, 27,3 mm Anschrift), Informationsblock ab 125 mm, Text ab der Bezugszeichenzeile bzw. dem Betreff.
DIN = {
    "A": {"oben": 27, "info_oben": 32, "text_ab": 80.46, "falz": (87, 192)},
    "B": {"oben": 45, "info_oben": 50, "text_ab": 98.46, "falz": (105, 210)},
}
DIN_LINKS, DIN_BREITE, DIN_HOEHE, DIN_INFO_LINKS, DIN_INFO_BREITE = 20, 85, 45, 125, 75
LOCHMARKE = 148.5
MAX_ANSCHRIFT_ZEILEN = 6  # Anschriftzone; darüber bleibt die Zusatz- und Vermerkzone (12,7 mm) frei


def din_css() -> str:
    return (".din-bereich { position: relative; display: flow-root; }"
            ".din-feld { position: absolute; overflow: hidden; }"
            ".din-ruecksendung { font-size: 6.5pt; line-height: 1.2; color: #3b3953; height: 5mm; padding-top: 1.5mm;"
            "  white-space: nowrap; overflow: hidden; }"
            ".din-ruecksendung span { border-bottom: 0.3pt solid #3b3953; }"
            ".din-anschrift { padding-top: 12.7mm; font-size: 10pt; line-height: 1.25; }"
            ".din-info { font-size: 8.5pt; line-height: 1.45; }"
            ".marke { position: absolute; width: 3mm; height: 0; border-top: 0.2mm solid #828282; }"
            ".marke.loch { width: 5mm; }")


def falzmarken_html(oben_mm: float, links_mm: float, form: str) -> str:
    """Falzmarken und Lochmarke nach DIN 5008, bezogen auf einen Bereich, der ``oben_mm``/``links_mm`` vom Blattrand
    beginnt (5 mm vom linken Rand)."""
    marken = [f'<div class="marke" style="top:{y - oben_mm:.2f}mm;left:{5 - links_mm:.2f}mm"></div>'
              for y in DIN[form]["falz"]]
    marken.append(f'<div class="marke loch" style="top:{LOCHMARKE - oben_mm:.2f}mm;left:{4 - links_mm:.2f}mm"></div>')
    return "".join(marken)


def anschriftfeld_html(ruecksendung: str, anschrift: str, info: str, form: str, oben_mm: float, links_mm: float,
                       falzmarken: bool) -> str:
    """Rücksendeangabe, Anschrift und Informationsblock an den festen Stellen; Lage relativ zum Seitenbereich."""
    d = DIN[form]
    feld = (f'<div class="din-feld" style="top:{d["oben"] - oben_mm:.2f}mm;left:{DIN_LINKS - links_mm:.2f}mm;'
            f'width:{DIN_BREITE}mm;height:{DIN_HOEHE}mm">'
            f'<div class="din-ruecksendung">{f"<span>{ruecksendung}</span>" if ruecksendung else ""}</div>'
            f'<div class="din-anschrift">{anschrift}</div></div>')
    rechts = (f'<div class="din-feld din-info" style="top:{d["info_oben"] - oben_mm:.2f}mm;'
              f'left:{DIN_INFO_LINKS - links_mm:.2f}mm;width:{DIN_INFO_BREITE}mm">{info}</div>') if info else ""
    marken = falzmarken_html(oben_mm, links_mm, form) if falzmarken else ""
    return feld + rechts + marken


def din_hoehe(form: str, oben_mm: float) -> float:
    """Mindesthöhe des Bereichs bis zum Beginn des Textes."""
    return max(0.0, DIN[form]["text_ab"] - oben_mm)


def escape(text: str) -> str:
    return html.escape(text or "")
