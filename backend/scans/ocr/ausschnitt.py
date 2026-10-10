"""Nur einen Bereich der Seite lesen (F189 „richtigen Bereich markieren“): Ausschnitt vergrößern und mit Tesseract
lesen – auf dem Server, offline, ohne die übrige Seite anzufassen.

Anders als „Bereich neu erkennen“ (F165, beide Verfahren, ersetzt den Text der Seite an dieser Stelle) liefert dies
zusätzliche Reihen für die Werte: Ist der Bereich eine Tabelle, wird jede Zeile ein eigener Vorschlag. Die Lage der
Wörter wird in Pixel der ganzen Seite zurückgerechnet, damit „Stelle zeigen“ und das Lernen der Spaltenlage passen.
"""
from __future__ import annotations

import cv2
import numpy as np

from . import tesseract

# Mindestgröße des Bereichs (relativ zur Seite) und in Pixeln; Text wird auf etwa diese Höhe vergrößert
MIN_REL = 0.01
MIN_PIXEL = 12
ZIEL_TEXTHOEHE = 40
MAX_SEITE = 4200


class BereichFehler(ValueError):
    """Verständliche Meldung für die Oberfläche."""


def pruefen(box) -> list[float]:
    """[x, y, Breite, Höhe] relativ 0–1 prüfen und auf die Seite begrenzen."""
    try:
        x, y, b, h = (float(v) for v in box)
    except (TypeError, ValueError):
        raise BereichFehler("Bitte einen Bereich auf der Seite markieren.") from None
    if not all(np.isfinite([x, y, b, h])) or b < MIN_REL or h < MIN_REL / 2 or x < 0 or y < 0 or x >= 1 or y >= 1:
        raise BereichFehler("Der Bereich ist zu klein oder liegt außerhalb der Seite – bitte einen größeren Rahmen ziehen.")
    b, h = min(b, 1 - x), min(h, 1 - y)
    return [round(x, 5), round(y, 5), round(b, 5), round(h, 5)]


def _texthoehe(grau: np.ndarray) -> float:
    """Grobe Schätzung der Zeilenhöhe im Ausschnitt (aus dem Zeilenprofil dunkler Pixel)."""
    sw = grau < 128 if grau.mean() > 127 else grau > 128
    zeilen = sw.mean(axis=1) > 0.01
    laengen, n = [], 0
    for z in zeilen:
        if z:
            n += 1
        elif n:
            laengen.append(n)
            n = 0
    if n:
        laengen.append(n)
    laengen = [x for x in laengen if x >= 4]
    return float(np.median(laengen)) if laengen else 0.0


def lesen(grau: np.ndarray, box: list[float], woerterliste: str | None = None) -> dict:
    """Ausschnitt ``box`` (relativ) der Seite ``grau`` lesen → Ergebnis-JSON wie eine Seite (Pixel der ganzen Seite)."""
    h_seite, b_seite = grau.shape[:2]
    x0, y0 = int(box[0] * b_seite), int(box[1] * h_seite)
    x1, y1 = int(round((box[0] + box[2]) * b_seite)), int(round((box[1] + box[3]) * h_seite))
    # etwas Rand, damit angeschnittene Buchstaben ganz drin sind
    rand = max(2, int(0.004 * b_seite))
    x0, y0, x1, y1 = max(0, x0 - rand), max(0, y0 - rand), min(b_seite, x1 + rand), min(h_seite, y1 + rand)
    if x1 - x0 < MIN_PIXEL or y1 - y0 < MIN_PIXEL / 2:
        raise BereichFehler("Der Bereich ist zu klein – bitte einen größeren Rahmen ziehen.")
    stueck = grau[y0:y1, x0:x1]
    if stueck.ndim == 3:
        stueck = cv2.cvtColor(stueck, cv2.COLOR_BGR2GRAY)
    th = _texthoehe(stueck)
    faktor = ZIEL_TEXTHOEHE / th if th else 2.0
    faktor = max(1.0, min(4.0, faktor, MAX_SEITE / max(stueck.shape)))
    gross = cv2.resize(stueck, None, fx=faktor, fy=faktor, interpolation=cv2.INTER_CUBIC) if faktor > 1.01 else stueck
    gross = cv2.copyMakeBorder(gross, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    # eine Zeile (breit und flach) → psm 7; sonst ein Block mit mehreren Zeilen (Tabelle) → psm 6
    eine_zeile = th and (y1 - y0) < 2.2 * th
    woerter = tesseract.erkennen(gross, psm=7 if eine_zeile else 6, woerterliste=woerterliste, timeout=90)
    zeilen: dict[tuple, list] = {}
    for w in woerter:
        x = (w.x - 20) / faktor + x0
        y = (w.y - 20) / faktor + y0
        zeilen.setdefault(w.zeile, []).append([w.text, round(x, 1), round(y, 1), round(w.w / faktor, 1),
                                               round(w.h / faktor, 1), round(w.c, 3)])
    reihen = []
    for _, ws in sorted(zeilen.items(), key=lambda kv: min(w[2] for w in kv[1])):
        ws.sort(key=lambda w: w[1])
        reihen.append([{"q": "t", "w": ws}])
    return {"breite": int(b_seite), "hoehe": int(h_seite), "reihen": reihen, "verfahren": ["tesseract"],
            "box": box}
