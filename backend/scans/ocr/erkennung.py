"""Eine Seite erkennen: Aufbereitung → beide Verfahren → Zusammenführung. Dazu „Bereich neu erkennen“."""
from __future__ import annotations

import time

import cv2
import numpy as np

from . import fusion, tesseract
from .aufbereitung import Aufbereitet, Einstellungen, aufbereiten, sauvola
from .laden import Rohseite
from .paddle import Paddle


def verfahren_stand(laden: bool = True) -> dict:
    """Welche Verfahren stehen bereit (für Systemseite und „Scans“)? ``laden=False`` prüft nur, ob die Modelldateien
    da sind – so lädt das Backend (Gunicorn) nie die Modelle in den Speicher; das tut nur der OCR-Dienst."""
    from .paddle import DET, DET_KLEIN, DICT, REC, UVDOC, modell_ordner, modus, speicher_mb

    ok, text = tesseract.verfuegbar()
    p = None
    fehler = ""
    ordner = modell_ordner()
    vorhanden = ((ordner / DET).is_file() or (ordner / DET_KLEIN).is_file()) and all(
        (ordner / f).is_file() for f in (REC, DICT))
    if laden and vorhanden:
        try:
            p = Paddle.laden()
        except Exception as e:  # noqa: BLE001 – defekte Modelldatei: anzeigen statt abstürzen
            fehler = str(e)[:300]
    bereit = p is not None if laden else vorhanden
    if p is not None:
        sparsam, det_name, glaetten = p.sparsam, p.det_name, bool(p.uvdoc)
    else:  # ohne Laden (Backend): so, wie der Dienst es mit demselben Image und derselben Umgebung täte
        sparsam = modus() == "sparsam" or not (ordner / DET).is_file()
        det_name = "mobile_det" if sparsam and (ordner / DET_KLEIN).is_file() else "server_det"
        glaetten = not sparsam and (ordner / UVDOC).is_file()
    from ..dokumente import verfuegbar as ocrmypdf_verfuegbar

    o_ok, o_text = ocrmypdf_verfuegbar()
    return {
        "tesseract": {"bereit": ok, "text": text},
        # „Text erkennen“ an Dokumenten der Akte (F170)
        "ocrmypdf": {"bereit": o_ok, "text": o_text},
        "paddle": {"bereit": bereit, "glaetten": glaetten, "sparsam": sparsam if bereit else False,
                   "speicher_mb": speicher_mb(),
                   "text": (f"PP-OCRv5 (Zeilen: {det_name}, Schrift: latin_mobile_rec)"
                            + (" · Sparmodus" if sparsam else "")) if bereit else
                   (f"Modelle nicht ladbar: {fehler}" if fehler else "Modelle nicht vorhanden")},
    }


def _digital(roh: Rohseite) -> dict | None:
    """Textebene einer PDF-Seite als Ergebnis – nur, wenn sie lesbar ist (keine Zeichensalat-Ebene eines Kopierers)."""
    if not roh.digital:
        return None
    text = " ".join(w[0] for w in roh.digital)
    if fusion.plausibel(text) < 0.85:
        return None
    woerter = [fusion.Wort(t, x, y, w, h, 1.0) for t, x, y, w, h in roh.digital]
    # Wörter → Stücke: gleiche Höhe und kleine Lücke = ein Stück
    woerter.sort(key=lambda w: (round((w.y + w.h / 2) / max(w.h, 1)), w.x))
    stuecke: list[fusion.Stueck] = []
    for w in woerter:
        letztes = stuecke[-1] if stuecke else None
        if letztes:
            v = letztes.woerter[-1]
            gleiche_zeile = abs((v.y + v.h / 2) - (w.y + w.h / 2)) < 0.5 * max(v.h, w.h)
            if gleiche_zeile and 0 <= w.x - (v.x + v.w) < 2.2 * max(v.h, w.h):
                letztes.woerter.append(w)
                continue
        stuecke.append(fusion.Stueck([w], "d"))
    stuecke = [s.rahmen() for s in stuecke]
    h, b = roh.bild.shape[:2]
    return fusion.seite_json(stuecke, b, h, ["textebene"])


# Sparstufen nach abgebrochenen Versuchen (der Dienst wurde während der Seite beendet, meist an der Speichergrenze):
# 1 = ohne Glätten und mit kleinerer Zeilensuche, 2 = nur Tesseract
SPARSTUFEN = {1: "sparsam erkannt (ohne Glätten, kleinere Zeilensuche)", 2: "nur mit Tesseract erkannt"}
DET_MAX_SPARSAM = 1280


def seite_erkennen(roh: Rohseite, einstellungen: dict | None, *, woerterliste: str | None = None,
                   paddle: Paddle | None = None, textebene: bool = True, stufe: int = 0,
                   schritt=None) -> tuple[Aufbereitet, dict]:
    """→ (aufbereitete Seite, Ergebnis-JSON mit Reihen, Verfahren, Zeiten).

    ``stufe``: Sparstufe (siehe SPARSTUFEN); ``schritt``: Funktion(text), meldet den Teilschritt (Fortschritt)."""
    melden = schritt or (lambda _t: None)
    if stufe >= 2:
        paddle = None
    t0 = time.monotonic()
    e = Einstellungen.aus_json(einstellungen)
    if textebene:
        digital = _digital(roh)
        if digital is not None:
            grau = cv2.cvtColor(roh.bild, cv2.COLOR_BGR2GRAY)
            anzeige = roh.bild if e.modus == "farbe" else grau
            auf = Aufbereitet(bild=anzeige, grau=grau, sw=grau, info={"textebene": True,
                                                                       "groesse": [grau.shape[1], grau.shape[0]]})
            digital["zeit"] = round(time.monotonic() - t0, 2)
            return auf, digital
    auf = aufbereiten(roh.bild, e, herkunft=roh.herkunft, kamera=bool(roh.exif),
                      glaetter=paddle.glaetten if (paddle and paddle.uvdoc and stufe < 1) else None, schritt=melden)
    if stufe:
        auf.info["sparstufe"] = stufe
    t1 = time.monotonic()
    melden("Tesseract liest")
    tg = fusion.tesseract_stuecke(tesseract.erkennen(auf.grau, woerterliste=woerterliste))
    # Sparmodus mit PP-OCR: ein Tesseract-Durchgang genügt – die zweite Lesart liefert PP-OCR (spart rund ein Drittel
    # der Zeit). Ohne PP-OCR bleiben beide Durchgänge, sonst gäbe es keinen Abgleich und keine unsicheren Wörter.
    if paddle is not None and getattr(paddle, "sparsam", False):
        ts = []
        auf.info["tesseract_einmal"] = True
    else:
        melden("Tesseract liest (Schwarz-Weiß)")
        ts = fusion.tesseract_stuecke(tesseract.erkennen(auf.sw, woerterliste=woerterliste))
    t2 = time.monotonic()
    pz = None
    verfahren = ["tesseract"]
    if paddle is not None:
        melden("PP-OCR liest")
        pz = [fusion.paddle_stueck(z) for z in
              paddle.erkennen(auf.grau, det_max=DET_MAX_SPARSAM if stufe >= 1 else None)]
        verfahren.insert(0, "paddle")
    melden("Ergebnisse zusammenführen")
    t3 = time.monotonic()
    stuecke = fusion.zusammenfuehren(pz, tg, ts)
    h, b = auf.grau.shape[:2]
    daten = fusion.seite_json(stuecke, b, h, verfahren)
    daten["zeit"] = {"aufbereitung": round(t1 - t0, 2), "tesseract": round(t2 - t1, 2),
                     "paddle": round(t3 - t2, 2) if paddle else None, "gesamt": round(time.monotonic() - t0, 2)}
    return auf, daten


def bereich_erkennen(grau: np.ndarray, daten: dict, box: list[float], *, staerke: int = 0,
                     woerterliste: str | None = None, paddle: Paddle | None = None) -> dict:
    """Einen Bereich (x, y, b, h relativ 0–1) neu erkennen: vergrößert, Kontrast ``staerke`` (-50…50), Tesseract mit
    „ein Textblock“ und PP-OCR. Die Wörter im Bereich werden ersetzt; der Rest der Seite bleibt."""
    H, W = grau.shape[:2]
    x0 = int(max(0, min(1, box[0])) * W)
    y0 = int(max(0, min(1, box[1])) * H)
    x1 = int(max(0, min(1, box[0] + box[2])) * W)
    y1 = int(max(0, min(1, box[1] + box[3])) * H)
    if x1 - x0 < 8 or y1 - y0 < 8:
        raise ValueError("Der Bereich ist zu klein.")
    ausschnitt = grau[y0:y1, x0:x1]
    faktor = 2.0 if max(ausschnitt.shape) < 2500 else 1.0
    gross = cv2.resize(ausschnitt, None, fx=faktor, fy=faktor, interpolation=cv2.INTER_CUBIC)
    if staerke:
        a = 1.0 + staerke / 50.0 * 0.8
        gross = np.clip((gross.astype(np.float32) - 128.0) * a + 128.0, 0, 255).astype(np.uint8)
    rand = 20
    gross = cv2.copyMakeBorder(gross, rand, rand, rand, rand, cv2.BORDER_CONSTANT, value=255)
    tg = fusion.tesseract_stuecke(tesseract.erkennen(gross, psm=6, woerterliste=woerterliste))
    ts = fusion.tesseract_stuecke(tesseract.erkennen(sauvola(gross), psm=6, woerterliste=woerterliste))
    pz = [fusion.paddle_stueck(z) for z in paddle.erkennen(gross)] if paddle else None
    neu = fusion.zusammenfuehren(pz, tg, ts)
    for s in neu:  # zurück in Seitenkoordinaten
        for w in s.woerter:
            w.x = (w.x - rand) / faktor + x0
            w.y = (w.y - rand) / faktor + y0
            w.w /= faktor
            w.h /= faktor
        s.rahmen()
    # bisherige Stücke außerhalb des Bereichs behalten (Wörter im Bereich entfallen)
    alt = []
    for r in daten.get("reihen", []):
        for s in r:
            woerter = [fusion.Wort(*w[:6], alt=w[6] if len(w) > 6 else None) for w in s["w"]]
            bleiben = [w for w in woerter if not (x0 <= w.x + w.w / 2 <= x1 and y0 <= w.y + w.h / 2 <= y1)]
            if bleiben:
                alt.append(fusion.Stueck(bleiben, s.get("q", "t")).rahmen())
    ergebnis = fusion.seite_json(alt + neu, daten.get("breite", W), daten.get("hoehe", H),
                                 daten.get("verfahren", ["tesseract"]))
    for k in ("zeit",):
        if k in daten:
            ergebnis[k] = daten[k]
    ergebnis["bereiche"] = (daten.get("bereiche") or []) + [[round(v, 4) for v in box]]
    return ergebnis
