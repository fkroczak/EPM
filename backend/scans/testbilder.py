"""Erfundene Dokumente für Tests und Musterdaten (keine echten Personen): Laborbefund, Arztbrief, BIA-Ausdruck –
als sauberer Scan und als „Foto“ (schräg aufgenommen, mit Schatten, Rauschen und JPEG-Kompression)."""
from __future__ import annotations

import io
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCHRIFTEN = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]


def _schrift(groesse: int, fett: bool = False):
    for pfad in SCHRIFTEN:
        p = Path(pfad.replace("Sans.ttf", "Sans-Bold.ttf") if fett else pfad)
        if p.is_file():
            return ImageFont.truetype(str(p), groesse)
        if Path(pfad).is_file():
            return ImageFont.truetype(pfad, groesse)
    return ImageFont.load_default(groesse)


SPALTEN = [700, 330, 300, 400]

LABOR = [
    ("fett", "Labor Dr. Beispiel & Kollegen – Medizinisches Versorgungszentrum"),
    "Musterstraße 12, 48143 Münster",
    None,
    "Patient: {nachname}, {vorname}      geb. {geburt}      Pat.-Nr. 4711",
    "Eingang: 02.09.2026    Abnahme: 01.09.2026    Befund vom 03.09.2026",
    None,
    ("fett", "Laborbefund"),
    ("tab", ["Untersuchung", "Ergebnis", "Einheit", "Referenzbereich"]),
    ("tab", ["Natrium", "138", "mmol/l", "135 - 145"]),
    ("tab", ["Kalium", "3,2 L", "mmol/l", "3,5 - 5,1"]),
    ("tab", ["Magnesium", "0,68 L", "mmol/l", "0,70 - 1,05"]),
    ("tab", ["Kreatinin", "1,12", "mg/dl", "0,50 - 0,90"]),
    ("tab", ["Albumin", "3,4", "g/dl", "3,5 - 5,2"]),
    ("tab", ["Ferritin", "18", "ng/ml", "15 - 150"]),
    ("tab", ["Zink", "62", "µg/dl", "70 - 120"]),
    None,
    "Beurteilung: Hypokaliämie und Hypomagnesiämie.",
]

BRIEF = [
    ("fett", "Klinikum Beispielstadt – Klinik für Gastroenterologie"),
    None,
    "Beispielstadt, den 15.08.2026",
    None,
    "Sehr geehrte Frau Kollegin,",
    "wir berichten über {vorname} {nachname}, geb. {geburt}.",
    None,
    ("fett", "Diagnosen:"),
    "- Kurzdarmsyndrom nach Dünndarmresektion (K91.2 G)",
    "- V.a. Vitamin-D-Mangel (E55.9 V)",
    None,
    ("fett", "Therapie:"),
    "Parenterale Ernährung an 5 Tagen pro Woche.",
    None,
    "Mit freundlichen kollegialen Grüßen",
]

BIA = [
    ("fett", "Bioelektrische Impedanzanalyse (BIA)"),
    "Datum der Messung: 20.09.2026",
    "Name: {nachname}, {vorname}     Geburtsdatum: {geburt}",
    None,
    ("tab", ["Körpergewicht", "58,4 kg", "", ""]),
    ("tab", ["BMI", "21,2 kg/m²", "", ""]),
    ("tab", ["Phasenwinkel", "4,1 °", "", ""]),
    ("tab", ["Körperwasser (TBW)", "29,8 l", "", ""]),
    ("tab", ["ECW", "47,5 %", "", ""]),
    ("tab", ["Fettmasse", "17,2 kg", "", ""]),
    ("tab", ["BCM", "18,9 kg", "", ""]),
]


def seite(zeilen, *, nachname="Muster", vorname="Erika", geburt="14.03.1961", groesse=34) -> Image.Image:
    """A4 mit 300 dpi, schwarz auf weiß."""
    img = Image.new("RGB", (2480, 3508), "white")
    d = ImageDraw.Draw(img)
    y = 220
    for z in zeilen:
        if z is None:
            y += 40
            continue
        if isinstance(z, tuple) and z[0] == "tab":
            x = 220
            for spalte, breite in zip(z[1], SPALTEN):
                d.text((x, y), spalte, fill="black", font=_schrift(groesse))
                x += breite
            y += int(groesse * 1.6)
            continue
        fett = isinstance(z, tuple) and z[0] == "fett"
        text = (z[1] if fett else z).format(nachname=nachname, vorname=vorname, geburt=geburt)
        d.text((220, y), text, fill="black", font=_schrift(groesse + (6 if fett else 0), fett))
        y += int(groesse * 1.6)
    return img


def png(img: Image.Image, dpi: int = 300, verkleinern: float = 1.0) -> bytes:
    if verkleinern != 1.0:
        img = img.resize((int(img.width * verkleinern), int(img.height * verkleinern)))
    puffer = io.BytesIO()
    img.save(puffer, "PNG", dpi=(dpi, dpi))
    return puffer.getvalue()


def pdf(*bilder: Image.Image, dpi: int = 200) -> bytes:
    """Bild-PDF ohne Textebene (wie vom Scanner)."""
    seiten = [b.convert("RGB").resize((int(b.width * dpi / 300), int(b.height * dpi / 300))) for b in bilder]
    puffer = io.BytesIO()
    seiten[0].save(puffer, "PDF", save_all=True, append_images=seiten[1:], resolution=dpi)
    return puffer.getvalue()


def foto(img: Image.Image, seed: int = 1, staerke: float = 1.0) -> bytes:
    """Wie mit dem Telefon fotografiert: Blatt schräg auf dunklem Tisch, Schatten, Unschärfe, Rauschen, JPEG."""
    rnd = random.Random(seed)
    a = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    h, w = a.shape[:2]
    rand = 300
    grund = (60, 70, 85)
    tisch = np.full((h + 2 * rand, w + 2 * rand, 3), grund, np.uint8)
    tisch[rand:rand + h, rand:rand + w] = a
    H, W = tisch.shape[:2]
    quelle = np.float32([[rand, rand], [rand + w, rand], [rand + w, rand + h], [rand, rand + h]])

    def j():
        return rnd.uniform(-110, 110) * staerke

    ziel = np.float32([[rand + j() + 80, rand + j() + 60], [rand + w + j() - 40, rand + j() + 120],
                       [rand + w + j() - 90, rand + h + j() - 30], [rand + j() + 30, rand + h + j() - 80]])
    m = cv2.getPerspectiveTransform(quelle, ziel)
    tisch = cv2.warpPerspective(tisch, m, (W, H), borderValue=grund)
    yy, xx = np.mgrid[0:H, 0:W]
    schatten = 1.0 - 0.45 * staerke * np.clip((xx / W) * 1.2 - 0.2, 0, 1) * np.clip(1 - yy / H, 0.3, 1)
    tisch = (tisch * schatten[..., None]).clip(0, 255).astype(np.uint8)
    tisch = cv2.GaussianBlur(tisch, (0, 0), 1.2 * staerke)
    tisch = cv2.resize(tisch, (int(W * 0.45), int(H * 0.45)), interpolation=cv2.INTER_AREA)
    rauschen = np.random.default_rng(seed).normal(0, 7 * staerke, tisch.shape)
    tisch = (tisch + rauschen).clip(0, 255).astype(np.uint8)
    ok, kodiert = cv2.imencode(".jpg", tisch, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return kodiert.tobytes()
