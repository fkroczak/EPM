"""Bildaufbereitung vor der Erkennung – automatisch, je Seite von Hand überschreibbar.

Reihenfolge: Blatt im Foto finden und entzerren (Perspektive) → gewellte Seite glätten (UVDoc, nur Fotos) →
Ausrichtung in 90°-Schritten (Tesseract-OSD) → Schräglage (Projektionsprofil) → Schatten und ungleichmäßige
Ausleuchtung ausgleichen → Rauschen entfernen → auf Lesegröße skalieren.

Die Einstellungen einer Seite (``einstellungen`` als JSON in der Datenbank) und was automatisch erkannt wurde
(``info``) werden gespeichert, damit die Oberfläche beides zeigen und der Mensch es korrigieren kann.
Koordinaten von Hand gesetzter Ecken sind relativ (0–1) zum geladenen Rohbild.
"""
from __future__ import annotations

import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field

import cv2
import numpy as np

ZIEL_TEXTHOEHE = 28           # mittlere Höhe der Zeichen (Pixel), bei der Tesseract und PP-OCR am besten lesen
MAX_SEITE_AUFBEREITET = 5600  # längere Seite nach dem Skalieren


@dataclass
class Einstellungen:
    """Was der Mensch je Seite festlegen kann. ``None`` bzw. „auto“ heißt: automatisch."""

    ecken: str | list = "auto"            # "auto" | "aus" | [[x, y] × 4] relativ (oben links, oben rechts, unten rechts, unten links)
    glaetten: str = "auto"                # "auto" | "ein" | "aus"
    drehung: int | None = None            # None = automatisch, sonst 0/90/180/270 im Uhrzeigersinn
    schraeglage: str | float = "auto"     # "auto" | "aus" | Winkel in Grad (positiv = gegen den Uhrzeigersinn drehen)
    schatten: bool = True                 # Schatten/Ausleuchtung ausgleichen
    modus: str = "graustufen"             # Anzeige und PDF: "graustufen" | "farbe" | "sw"
    kontrast: int = 0                     # -50 … 50
    helligkeit: int = 0                   # -50 … 50

    @classmethod
    def aus_json(cls, d: dict | None) -> "Einstellungen":
        d = d or {}
        e = cls()
        ecken = d.get("ecken", "auto")
        if isinstance(ecken, list) and len(ecken) == 4 and all(
                isinstance(p, (list, tuple)) and len(p) == 2 for p in ecken):
            e.ecken = [[min(1.0, max(0.0, float(p[0]))), min(1.0, max(0.0, float(p[1])))] for p in ecken]
        elif ecken in ("auto", "aus"):
            e.ecken = ecken
        if d.get("glaetten") in ("auto", "ein", "aus"):
            e.glaetten = d["glaetten"]
        if d.get("drehung") in (0, 90, 180, 270):
            e.drehung = int(d["drehung"])
        s = d.get("schraeglage", "auto")
        if s in ("auto", "aus"):
            e.schraeglage = s
        else:
            try:
                e.schraeglage = max(-45.0, min(45.0, float(s)))
            except (TypeError, ValueError):
                e.schraeglage = "auto"
        e.schatten = d.get("schatten", True) is not False
        if d.get("modus") in ("graustufen", "farbe", "sw"):
            e.modus = d["modus"]
        for feld_ in ("kontrast", "helligkeit"):
            try:
                setattr(e, feld_, max(-50, min(50, int(d.get(feld_, 0)))))
            except (TypeError, ValueError):
                pass
        return e

    def als_json(self) -> dict:
        return {"ecken": self.ecken, "glaetten": self.glaetten, "drehung": self.drehung,
                "schraeglage": self.schraeglage, "schatten": self.schatten, "modus": self.modus,
                "kontrast": self.kontrast, "helligkeit": self.helligkeit}


@dataclass
class Aufbereitet:
    bild: np.ndarray            # für Anzeige und PDF (Graustufen, Farbe oder Schwarz-Weiß)
    grau: np.ndarray            # für die Erkennung: Graustufen, ausgeglichen
    sw: np.ndarray              # für die Erkennung: Schwarz-Weiß (Sauvola)
    info: dict = field(default_factory=dict)


# ---------------------------------------------------------------- Hilfen
def _grau(bild: np.ndarray) -> np.ndarray:
    return bild if bild.ndim == 2 else cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY)


def _verkleinern(bild: np.ndarray, lang: int) -> tuple[np.ndarray, float]:
    h, w = bild.shape[:2]
    f = min(1.0, lang / max(h, w))
    if f >= 1.0:
        return bild, 1.0
    return cv2.resize(bild, (max(1, round(w * f)), max(1, round(h * f))), interpolation=cv2.INTER_AREA), f


def ordne_ecken(p: np.ndarray) -> np.ndarray:
    """Vier Punkte → oben links, oben rechts, unten rechts, unten links."""
    p = np.asarray(p, dtype=np.float32).reshape(4, 2)
    s = p.sum(axis=1)
    d = np.diff(p, axis=1).ravel()
    return np.array([p[np.argmin(s)], p[np.argmin(d)], p[np.argmax(s)], p[np.argmax(d)]], dtype=np.float32)


def sauvola(grau: np.ndarray, fenster: int | None = None, k: float = 0.2, r: float = 128.0) -> np.ndarray:
    """Schwarz-Weiß nach Sauvola (örtlich angepasste Schwelle): blasse und graue Stellen bleiben erhalten."""
    if fenster is None:
        fenster = max(15, (min(grau.shape[:2]) // 60) | 1)
    g = grau.astype(np.float32)
    mittel = cv2.boxFilter(g, -1, (fenster, fenster), borderType=cv2.BORDER_REPLICATE)
    quad = cv2.boxFilter(g * g, -1, (fenster, fenster), borderType=cv2.BORDER_REPLICATE)
    std = np.sqrt(np.maximum(quad - mittel * mittel, 0))
    schwelle = mittel * (1 + k * (std / r - 1))
    return np.where(g > schwelle, 255, 0).astype(np.uint8)


def texthoehe(grau: np.ndarray) -> float | None:
    """Mittlere Höhe der Zeichen in Pixeln (aus zusammenhängenden dunklen Flächen), None ohne Text."""
    klein, f = _verkleinern(grau, 2000)
    sw = sauvola(klein)
    anzahl, _, stats, _ = cv2.connectedComponentsWithStats(255 - sw, connectivity=8)
    if anzahl < 10:
        return None
    h = stats[1:, cv2.CC_STAT_HEIGHT].astype(np.float32)
    w = stats[1:, cv2.CC_STAT_WIDTH].astype(np.float32)
    flaeche = stats[1:, cv2.CC_STAT_AREA].astype(np.float32)
    gross = max(klein.shape[:2])
    ok = (h >= 4) & (h <= gross * 0.08) & (w <= gross * 0.2) & (w / np.maximum(h, 1) < 4) & (flaeche >= 8)
    if ok.sum() < 10:
        return None
    return float(np.median(h[ok])) / f


# ---------------------------------------------------------------- Blatt im Foto
def blatt_finden(bild: np.ndarray) -> tuple[np.ndarray | None, float]:
    """Ecken des Blatts (Pixel, geordnet) und eine Sicherheit 0–1. None, wenn kein klares Blatt zu sehen ist
    (z. B. ein Scan ohne Rand – dann bleibt das Bild, wie es ist)."""
    klein, f = _verkleinern(bild, 900)
    grau = cv2.GaussianBlur(_grau(klein), (5, 5), 0)
    H, W = grau.shape[:2]
    gesamt = float(H * W)
    kandidaten = []

    def pruefe(kontur):
        flaeche = cv2.contourArea(kontur)
        if flaeche < 0.18 * gesamt:
            return
        umfang = cv2.arcLength(kontur, True)
        for eps in (0.015, 0.025, 0.04, 0.06, 0.08):
            ann = cv2.approxPolyDP(kontur, eps * umfang, True)
            if len(ann) == 4 and cv2.isContourConvex(ann):
                kandidaten.append(ordne_ecken(ann.reshape(4, 2)))
                return
        # kein sauberes Viereck: kleinstes umschließendes, gedrehtes Rechteck
        box = cv2.boxPoints(cv2.minAreaRect(kontur))
        if cv2.contourArea(box) < 1.25 * flaeche:
            kandidaten.append(ordne_ecken(box))

    # 1. helles Blatt auf dunklerem Grund
    _, otsu = cv2.threshold(grau, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    otsu = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    for k in sorted(cv2.findContours(otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea,
                    reverse=True)[:3]:
        pruefe(k)
    # 2. Kanten
    kanten = cv2.Canny(grau, 40, 120)
    kanten = cv2.dilate(kanten, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    for k in sorted(cv2.findContours(kanten, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea,
                    reverse=True)[:3]:
        pruefe(k)
    bestes, beste_wertung = None, 0.0
    for ecken in kandidaten:
        flaeche = cv2.contourArea(ecken)
        anteil = flaeche / gesamt
        if anteil > 0.97:
            continue  # das ganze Bild – nichts zuzuschneiden
        maske = np.zeros_like(grau)
        cv2.fillConvexPoly(maske, ecken.astype(np.int32), 255)
        innen = float(grau[maske > 0].mean())
        aussen_pixel = grau[maske == 0]
        aussen = float(aussen_pixel.mean()) if aussen_pixel.size > 100 else innen
        kontrast = (innen - aussen) / 255.0
        if kontrast < 0.06:
            continue  # Blatt hebt sich nicht vom Grund ab
        wertung = anteil * 0.6 + min(kontrast * 2, 0.4)
        if wertung > beste_wertung:
            bestes, beste_wertung = ecken, wertung
    if bestes is None:
        return None, 0.0
    return bestes / f, min(1.0, beste_wertung)


def entzerren(bild: np.ndarray, ecken: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = ordne_ecken(ecken)
    breite = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    hoehe = int(round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))))
    breite, hoehe = max(breite, 10), max(hoehe, 10)
    ziel = np.array([[0, 0], [breite - 1, 0], [breite - 1, hoehe - 1], [0, hoehe - 1]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl], dtype=np.float32), ziel)
    return cv2.warpPerspective(bild, m, (breite, hoehe), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------- Ausrichtung und Schräglage
def tesseract_befehl() -> list[str]:
    return [os.environ.get("EPM_TESSERACT", "tesseract")]


def tessdata_umgebung() -> dict:
    env = dict(os.environ)
    if os.environ.get("EPM_TESSDATA"):
        env["TESSDATA_PREFIX"] = os.environ["EPM_TESSDATA"]
    env.setdefault("OMP_THREAD_LIMIT", os.environ.get("EPM_OCR_THREADS", "2"))
    return env


def osd(grau: np.ndarray) -> tuple[int, float] | None:
    """Ausrichtung nach Tesseract: (Drehung im Uhrzeigersinn 0/90/180/270, Sicherheit). None ohne Ergebnis."""
    klein, _ = _verkleinern(grau, 2200)
    with tempfile.TemporaryDirectory(prefix="epm-osd-") as tmp:
        pfad = os.path.join(tmp, "s.png")
        cv2.imwrite(pfad, klein)
        try:
            aus = subprocess.run([*tesseract_befehl(), pfad, "stdout", "--psm", "0"], capture_output=True, text=True,
                                 timeout=60, env=tessdata_umgebung())
        except (OSError, subprocess.TimeoutExpired):
            return None
    drehen, sicher = None, 0.0
    for zeile in aus.stdout.splitlines():
        if zeile.startswith("Rotate:"):
            try:
                drehen = int(zeile.split(":")[1]) % 360
            except ValueError:
                pass
        elif zeile.startswith("Orientation confidence:"):
            try:
                sicher = float(zeile.split(":")[1])
            except ValueError:
                pass
    if drehen not in (0, 90, 180, 270):
        return None
    return drehen, sicher


def drehen(bild: np.ndarray, grad: int) -> np.ndarray:
    grad %= 360
    if grad == 90:
        return cv2.rotate(bild, cv2.ROTATE_90_CLOCKWISE)
    if grad == 180:
        return cv2.rotate(bild, cv2.ROTATE_180)
    if grad == 270:
        return cv2.rotate(bild, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return bild


def schraeglage(grau: np.ndarray) -> float:
    """Winkel der Textzeilen in Grad (positiv: Zeilen steigen nach rechts an). Projektionsprofil auf einem
    verkleinerten Schwarz-Weiß-Bild: Bei der richtigen Drehung sind die Zeilen am schärfsten getrennt."""
    klein, _ = _verkleinern(grau, 1400)
    sw = 255 - sauvola(klein)
    if (sw > 0).mean() < 0.002:
        return 0.0
    h, w = sw.shape
    mitte = (w / 2, h / 2)

    def guete(winkel):
        m = cv2.getRotationMatrix2D(mitte, winkel, 1.0)
        r = cv2.warpAffine(sw, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        profil = r.sum(axis=1, dtype=np.float64)
        return float(np.var(np.diff(profil)))

    bester = max(np.arange(-8.0, 8.01, 0.5), key=guete)
    fein = max(np.arange(bester - 0.5, bester + 0.51, 0.1), key=guete)
    return float(round(fein, 2))


def drehen_frei(bild: np.ndarray, winkel: float) -> np.ndarray:
    """Um ``winkel`` Grad gegen den Uhrzeigersinn drehen; das Bild wird so vergrößert, dass nichts abgeschnitten wird."""
    if abs(winkel) < 0.05:
        return bild
    h, w = bild.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), winkel, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    rand = 255 if bild.ndim == 2 else (255, 255, 255)
    return cv2.warpAffine(bild, m, (nw, nh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=rand)


# ---------------------------------------------------------------- Ausleuchtung, Rauschen, Größe
def hintergrund(grau: np.ndarray, zeichen: float | None) -> np.ndarray:
    """Helligkeit des Papiers an jeder Stelle (Text „weggefiltert“): Grundlage, um Schatten auszugleichen."""
    klein, f = _verkleinern(grau, 1000)
    z = (zeichen or 30) * f
    k = int(max(7, min(61, z * 2.5))) | 1
    hg = cv2.morphologyEx(klein, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    hg = cv2.medianBlur(hg, max(3, (k // 2) | 1))
    hg = cv2.GaussianBlur(hg, (0, 0), k / 3)
    return cv2.resize(hg, (grau.shape[1], grau.shape[0]), interpolation=cv2.INTER_LINEAR)


def ausleuchtung(bild: np.ndarray, zeichen: float | None) -> np.ndarray:
    """Teilt durch den Hintergrund: Papier wird überall gleich hell, Schatten verschwinden, Schrift bleibt."""
    grau = _grau(bild)
    hg = np.maximum(hintergrund(grau, zeichen).astype(np.float32), 1.0)
    if bild.ndim == 2:
        aus = grau.astype(np.float32) / hg * 255.0
    else:
        aus = bild.astype(np.float32) / hg[..., None] * 255.0
    return np.clip(aus, 0, 255).astype(np.uint8)


def strecken(grau: np.ndarray) -> np.ndarray:
    """Kontrast strecken: dunkelste 0,5 % → schwarz, Papier → weiß."""
    unten, oben = np.percentile(grau, [0.5, 90])
    if oben - unten < 30:
        return grau
    aus = (grau.astype(np.float32) - unten) * (255.0 / (oben - unten))
    return np.clip(aus, 0, 255).astype(np.uint8)


def rauschen(grau: np.ndarray) -> float:
    """Geschätzte Stärke des Bildrauschens (Standardabweichung auf dem Papier)."""
    klein, _ = _verkleinern(grau, 1500)
    hp = klein.astype(np.float32) - cv2.GaussianBlur(klein, (0, 0), 1.5).astype(np.float32)
    papier = klein > np.percentile(klein, 60)
    if papier.sum() < 1000:
        return 0.0
    return float(np.median(np.abs(hp[papier])) * 1.4826)


def anpassen(bild: np.ndarray, kontrast: int, helligkeit: int) -> np.ndarray:
    if not kontrast and not helligkeit:
        return bild
    a = 1.0 + kontrast / 50.0 * 0.8
    b = helligkeit * 2.0
    return np.clip((bild.astype(np.float32) - 128.0) * a + 128.0 + b, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- Gesamtablauf
def aufbereiten(rohbild: np.ndarray, e: Einstellungen, *, herkunft: str = "bild", kamera: bool = False,
                glaetter=None) -> Aufbereitet:
    """Rohbild (BGR) → aufbereitete Seite. ``glaetter``: Funktion BGR → BGR (UVDoc) oder None.

    Als Foto gilt ein Bild (keine PDF-Seite) mit Kameradaten oder mit einem Blatt, das sich vom Grund abhebt."""
    info: dict = {}
    bild = rohbild

    # 1. Blatt im Bild finden und entzerren
    ecken = None
    if isinstance(e.ecken, list):
        h, w = bild.shape[:2]
        ecken = np.array([[p[0] * w, p[1] * h] for p in e.ecken], dtype=np.float32)
        info["ecken_quelle"] = "hand"
    elif e.ecken == "auto":
        ecken, sicher = blatt_finden(bild)
        if ecken is not None:
            # ein Stück nach innen: sonst bleibt am Rand ein Streifen vom Tisch stehen (dunkler Rahmen)
            mitte = ecken.mean(axis=0)
            ecken = mitte + (ecken - mitte) * 0.985
            info["ecken_quelle"] = "auto"
            info["ecken_sicherheit"] = round(sicher, 2)
    foto = herkunft == "bild" and (kamera or (ecken is not None and info.get("ecken_quelle") == "auto"))
    info["foto"] = foto
    if ecken is not None:
        h, w = bild.shape[:2]
        info["ecken"] = [[round(float(x) / w, 4), round(float(y) / h, 4)] for x, y in ordne_ecken(ecken)]
        bild = entzerren(bild, ecken)

    # 2. gewellte Seite glätten (UVDoc) – automatisch nur bei Fotos
    if glaetter is not None and (e.glaetten == "ein" or (e.glaetten == "auto" and foto)):
        try:
            bild = glaetter(bild)
            info["geglaettet"] = True
        except Exception as fehler:  # noqa: BLE001 – Glätten ist ein Zusatz; ohne geht es weiter
            info["geglaettet"] = False
            info["glaetten_fehler"] = str(fehler)[:200]

    # 3. Ausrichtung in 90°-Schritten
    if e.drehung is not None:
        bild = drehen(bild, e.drehung)
        info["drehung"] = e.drehung
        info["drehung_quelle"] = "hand"
    else:
        ergebnis = osd(_grau(bild))
        if ergebnis and ergebnis[0] and ergebnis[1] >= 1.5:
            bild = drehen(bild, ergebnis[0])
            info["drehung"] = ergebnis[0]
            info["drehung_quelle"] = "auto"
            info["drehung_sicherheit"] = round(ergebnis[1], 2)
        else:
            info["drehung"] = 0

    # 4. Schräglage
    if e.schraeglage == "auto":
        winkel = schraeglage(_grau(bild))
    elif e.schraeglage == "aus":
        winkel = 0.0
    else:
        winkel = float(e.schraeglage)
    if abs(winkel) >= 0.1:
        bild = drehen_frei(bild, winkel)
    info["schraeglage"] = round(winkel, 2)

    # 5. Ausleuchtung, Rauschen, Größe
    grau = _grau(bild)
    zeichen = texthoehe(grau)
    info["texthoehe"] = round(zeichen, 1) if zeichen else None
    if e.schatten:
        bild = ausleuchtung(bild, zeichen)
        grau = _grau(bild)
    sigma = rauschen(grau)
    info["rauschen"] = round(sigma, 1)
    if sigma > 3.5:
        staerke = float(min(18.0, 1.3 * sigma + 2))
        grau = cv2.fastNlMeansDenoising(grau, None, h=staerke, templateWindowSize=7, searchWindowSize=21)
        if bild.ndim == 3 and e.modus == "farbe":
            bild = cv2.fastNlMeansDenoisingColored(bild, None, staerke, staerke, 7, 21)
        info["entrauscht"] = round(staerke, 1)
    grau = strecken(grau)

    faktor = 1.0
    if zeichen:
        faktor = max(0.5, min(3.0, ZIEL_TEXTHOEHE / zeichen))
        if 0.85 <= faktor <= 1.2:
            faktor = 1.0
    h, w = grau.shape[:2]
    if max(h, w) * faktor > MAX_SEITE_AUFBEREITET:
        faktor = MAX_SEITE_AUFBEREITET / max(h, w)
    if faktor != 1.0:
        groesse = (max(1, round(w * faktor)), max(1, round(h * faktor)))
        verfahren = cv2.INTER_CUBIC if faktor > 1 else cv2.INTER_AREA
        grau = cv2.resize(grau, groesse, interpolation=verfahren)
        bild = cv2.resize(bild, groesse, interpolation=verfahren)
    info["skala"] = round(faktor, 3)

    sw = sauvola(grau)
    if e.modus == "sw":
        anzeige = sw
    elif e.modus == "farbe" and bild.ndim == 3:
        anzeige = bild
    else:
        anzeige = grau
    anzeige = anpassen(anzeige, e.kontrast, e.helligkeit)
    if e.kontrast or e.helligkeit:
        # Was der Mensch sieht, soll auch gelesen werden
        grau = anpassen(grau, e.kontrast, e.helligkeit)
        sw = sauvola(grau)
    info["groesse"] = [int(grau.shape[1]), int(grau.shape[0])]
    return Aufbereitet(bild=anzeige, grau=grau, sw=sw, info=info)
