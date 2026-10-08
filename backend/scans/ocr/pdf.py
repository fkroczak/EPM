"""Durchsuchbare PDF: je Seite das aufbereitete Bild, darüber unsichtbar der erkannte Text an seiner Stelle.

So bleibt die Seite genau so, wie sie aussieht, und der Text lässt sich trotzdem suchen, markieren und kopieren.
Die Seite bekommt die Größe von A4 (Hoch- oder Querformat nach dem Bild).
"""
from __future__ import annotations

import io

import cv2
import numpy as np

A4_KURZ = 595.28
A4_LANG = 841.89


def _seitengroesse(b: int, h: int) -> tuple[float, float]:
    if h >= b:
        breite = A4_KURZ
        return breite, breite * h / b
    breite = A4_LANG
    return breite, breite * h / b


def _text1252(t: str) -> str:
    """Standardschrift der PDF kennt Windows-1252 (ä, ö, ü, ß, µ, ², °, €, –) – anderes wird zu „?“."""
    return t.encode("cp1252", "replace").decode("cp1252")


def erstellen(seiten: list[tuple[np.ndarray, dict]], titel: str = "", autor: str = "EPM") -> bytes:
    """``seiten``: (Bild in Graustufen/BGR/SW, Ergebnis-JSON mit Reihen in Pixeln dieses Bildes)."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    puffer = io.BytesIO()
    c = canvas.Canvas(puffer, pageCompression=1)
    c.setTitle(titel or "Scan")
    c.setAuthor(autor)
    c.setCreator("EPM – Scans")
    for bild, daten in seiten:
        h, b = bild.shape[:2]
        pb, ph = _seitengroesse(b, h)
        c.setPageSize((pb, ph))
        sw = bild.ndim == 2 and np.isin(bild, (0, 255)).all()
        if sw:
            ok, kodiert = cv2.imencode(".png", bild, [cv2.IMWRITE_PNG_BILEVEL, 1])
        else:
            ok, kodiert = cv2.imencode(".jpg", bild, [cv2.IMWRITE_JPEG_QUALITY, 82])
        c.drawImage(ImageReader(io.BytesIO(kodiert.tobytes())), 0, 0, width=pb, height=ph)
        fx, fy = pb / max(daten.get("breite") or b, 1), ph / max(daten.get("hoehe") or h, 1)
        for reihe in daten.get("reihen", []):
            for stueck in reihe:
                for w in stueck["w"]:
                    text = _text1252(str(w[0]))
                    if not text.strip():
                        continue
                    x, y, ww, wh = w[1] * fx, w[2] * fy, w[3] * fx, w[4] * fy
                    groesse = max(1.0, wh * 0.9)
                    breite_text = stringWidth(text, "Helvetica", groesse)
                    t = c.beginText()
                    t.setTextRenderMode(3)  # unsichtbar
                    t.setFont("Helvetica", groesse)
                    t.setHorizScale(max(10.0, min(400.0, ww / breite_text * 100.0)) if breite_text > 0 else 100.0)
                    t.setTextOrigin(x, ph - y - wh * 0.8)
                    t.textOut(text)
                    c.drawText(t)
        c.showPage()
    c.save()
    return puffer.getvalue()
