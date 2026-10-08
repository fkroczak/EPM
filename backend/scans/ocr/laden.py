"""Datei → Seiten als Bild.

Erkannt wird am Inhalt, nicht an der Endung. PDF-Seiten werden mit 300 dpi gerastert; hat eine Seite eine echte
Textebene (z. B. ein Laborbefund, der als PDF aus der Laborsoftware kommt), wird deren Text mit Lage übernommen –
eine Erkennung ist dann nicht nötig und wäre nur schlechter.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps, ImageSequence

try:  # HEIC/HEIF (Fotos vom iPhone) – freiwillig, ohne das Paket werden sie abgewiesen
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC = True
except Exception:  # noqa: BLE001
    HEIC = False

Image.MAX_IMAGE_PIXELS = 120_000_000  # Schutz vor „Dekompressionsbomben“; ein A4-Scan mit 600 dpi hat 35 Mio.

DPI_PDF = 300
MAX_SEITE_PX = 4200          # längere Seite nach dem Rastern bzw. Laden (A4 mit 300 dpi: 3508)
MIN_TEXT_DIGITAL = 40        # so viele sichtbare Zeichen, dann gilt eine PDF-Seite als „mit Textebene“


class Unlesbar(ValueError):
    """Datei ist kein unterstütztes Format oder beschädigt."""


@dataclass
class Rohseite:
    bild: np.ndarray                      # BGR, uint8
    herkunft: str                         # "pdf" | "bild"
    dpi: float | None = None
    # PDF mit Textebene: Wörter [text, x, y, w, h] in Pixeln dieses Bildes
    digital: list[list] | None = None
    exif: dict = field(default_factory=dict)


def dateityp(kopf: bytes) -> str | None:
    """MIME-Typ am Inhalt erkennen (unterstützte Formate), sonst None."""
    if kopf.startswith(b"%PDF-"):
        return "application/pdf"
    if kopf.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if kopf.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if kopf[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    if kopf[:4] == b"RIFF" and kopf[8:12] == b"WEBP":
        return "image/webp"
    if kopf[:2] == b"BM":
        return "image/bmp"
    if kopf[4:8] == b"ftyp" and kopf[8:12] in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heim", b"heis"):
        return "image/heic" if HEIC else None
    return None


def _pil_zu_bgr(img: Image.Image) -> np.ndarray:
    if img.mode in ("RGBA", "LA", "P"):
        hinten = Image.new("RGB", img.size, "white")
        rgba = img.convert("RGBA")
        hinten.paste(rgba, mask=rgba.split()[-1])
        img = hinten
    elif img.mode != "RGB":
        img = img.convert("RGB")
    a = np.asarray(img)
    return np.ascontiguousarray(a[:, :, ::-1])


def _begrenzen(bild: np.ndarray, faktor_dpi: float | None) -> tuple[np.ndarray, float | None]:
    import cv2

    h, w = bild.shape[:2]
    lang = max(h, w)
    if lang <= MAX_SEITE_PX:
        return bild, faktor_dpi
    f = MAX_SEITE_PX / lang
    bild = cv2.resize(bild, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
    return bild, (faktor_dpi * f if faktor_dpi else None)


def _pdf_seiten(daten: bytes, max_seiten: int) -> list[Rohseite]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(daten)
    except Exception as e:  # noqa: BLE001
        raise Unlesbar("Die PDF-Datei lässt sich nicht öffnen (beschädigt oder mit Kennwort geschützt).") from e
    try:
        if len(pdf) == 0:
            raise Unlesbar("Die PDF-Datei hat keine Seiten.")
        if len(pdf) > max_seiten:
            raise Unlesbar(f"Die PDF-Datei hat {len(pdf)} Seiten – höchstens {max_seiten} auf einmal.")
        seiten = []
        for i in range(len(pdf)):
            seite = pdf[i]
            breite_pt, hoehe_pt = seite.get_size()
            skala = DPI_PDF / 72
            lang = max(breite_pt, hoehe_pt) * skala
            if lang > MAX_SEITE_PX:
                skala *= MAX_SEITE_PX / lang
            bild = seite.render(scale=skala, rotation=0, fill_color=(255, 255, 255, 255)).to_pil()
            bgr = _pil_zu_bgr(bild)
            # gedrehte Seiten (/Rotate): die Lage der Zeichen passte nicht zum gerasterten Bild – dann erkennen
            woerter = _pdf_woerter(seite, skala, bgr.shape[0]) if seite.get_rotation() == 0 else None
            seiten.append(Rohseite(bild=bgr, herkunft="pdf", dpi=skala * 72, digital=woerter))
            seite.close()
        return seiten
    finally:
        pdf.close()


def _pdf_woerter(seite, skala: float, hoehe_px: int) -> list[list] | None:
    """Wörter der Textebene mit Lage in Pixeln – nur, wenn die Seite genug echten Text hat."""
    try:
        tp = seite.get_textpage()
    except Exception:  # noqa: BLE001
        return None
    try:
        anzahl = tp.count_chars()
        if anzahl < MIN_TEXT_DIGITAL:
            return None
        sichtbar = sum(1 for c in tp.get_text_range(0, anzahl) if not c.isspace())
        if sichtbar < MIN_TEXT_DIGITAL:
            return None
        woerter, aktuell, box = [], [], None
        text = tp.get_text_range(0, anzahl)

        def abschliessen():
            nonlocal aktuell, box
            if aktuell and box:
                l, b, r, t = box  # PDF-Koordinaten: Ursprung unten links
                x, y = l * skala, hoehe_px - t * skala
                woerter.append(["".join(aktuell), round(x, 1), round(y, 1), round((r - l) * skala, 1),
                                round((t - b) * skala, 1)])
            aktuell, box = [], None

        for i in range(min(anzahl, len(text))):
            c = text[i]
            if c.isspace() or c in "\u0000￾￿":
                abschliessen()
                continue
            try:
                l, b, r, t = tp.get_charbox(i)
            except Exception:  # noqa: BLE001
                continue
            if r <= l or t <= b:
                continue
            if box is not None and (l - box[2]) > max(2.5, (t - b) * 0.6):  # großer Abstand ohne Leerzeichen
                abschliessen()
            aktuell.append(c)
            box = [l, b, r, t] if box is None else [min(box[0], l), min(box[1], b), max(box[2], r), max(box[3], t)]
        abschliessen()
        return woerter or None
    finally:
        tp.close()


def _bild_seiten(daten: bytes, max_seiten: int) -> list[Rohseite]:
    try:
        img = Image.open(io.BytesIO(daten))
        img.load()
    except Exception as e:  # noqa: BLE001
        raise Unlesbar("Das Bild lässt sich nicht öffnen (beschädigt oder unbekanntes Format).") from e
    seiten = []
    for nr, rahmen in enumerate(ImageSequence.Iterator(img)):
        if nr >= max_seiten:
            raise Unlesbar(f"Die Datei hat mehr als {max_seiten} Seiten.")
        einzel = ImageOps.exif_transpose(rahmen.copy()) or rahmen.copy()
        dpi = None
        info_dpi = einzel.info.get("dpi") or img.info.get("dpi")
        if info_dpi:
            try:
                d = float(info_dpi[0])
                dpi = d if 50 <= d <= 1200 else None
            except (TypeError, ValueError, IndexError):
                dpi = None
        exif = {}
        try:
            roh = img.getexif()
            # 271 Hersteller, 272 Modell: Foto einer Kamera bzw. eines Telefons
            exif = {k: str(roh.get(n))[:60] for k, n in (("hersteller", 271), ("modell", 272)) if roh.get(n)}
        except Exception:  # noqa: BLE001
            pass
        bgr, dpi = _begrenzen(_pil_zu_bgr(einzel), dpi)
        seiten.append(Rohseite(bild=bgr, herkunft="bild", dpi=dpi, exif=exif))
    if not seiten:
        raise Unlesbar("Die Datei enthält kein Bild.")
    return seiten


def seiten_laden(daten: bytes, max_seiten: int = 50) -> tuple[str, list[Rohseite]]:
    """(MIME-Typ, Seiten). Wirft ``Unlesbar`` mit einer verständlichen Meldung."""
    mime = dateityp(daten[:64])
    if mime is None:
        raise Unlesbar("Erlaubt sind PDF, JPG, PNG, TIFF, WEBP, BMP" + (" und HEIC" if HEIC else "") + ".")
    if mime == "application/pdf":
        return mime, _pdf_seiten(daten, max_seiten)
    return mime, _bild_seiten(daten, max_seiten)
