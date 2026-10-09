"""Erkennung 2: PaddleOCR PP-OCRv5 über onnxruntime (Apache-2.0), dazu UVDoc zum Glätten gewellter Seiten.

- Zeilenerkennung (Detection): PP-OCRv5_server_det – findet Textzeilen auch auf Fotos mit Schatten und Rauschen.
- Texterkennung (Recognition): latin_PP-OCRv5_mobile_rec – lateinische Schrift mit Umlauten und ß.
- Glätten: UVDoc – entzerrt gewölbte oder geknickte Seiten.

Sparmodus (Server mit wenig RAM, Festlegung 09.10.2026 für die Test-VM mit 4 GB): kleines Zeilenmodell
PP-OCRv5_mobile_det, kein Glätten, kleinere Zeilensuche. ``EPM_OCR_MODUS`` = auto (Standard: Sparmodus, wenn der
Container bzw. Server weniger als SPAR_GRENZE_MB Speicher hat) | voll | sparsam.

Es ist ein reines Texterkennungsmodell, kein Sprachmodell: Es liest Zeichen, schlägt nichts vor und ergänzt nichts.
Die Modelle liegen im Image (``EPM_OCR_MODELLE``, Herkunft und Prüfsummen in ``scans/modelle.json``); zur Laufzeit
wird nichts nachgeladen. Fehlen sie, arbeitet die Erkennung nur mit Tesseract – die Systemseite und „Scans“ sagen das.
"""
from __future__ import annotations

import math
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

DET = "detection/v5/det.onnx"
DET_KLEIN = "detection/v5-mobile/det.onnx"
SPAR_GRENZE_MB = 2500
DET_MAX_KLEIN = 1536
REC = "languages/latin/rec.onnx"
DICT = "languages/latin/dict.txt"
UVDOC = "preprocessing/doc-unwarping/UVDoc.onnx"

MITTEL = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STREUUNG = np.array([0.229, 0.224, 0.225], dtype=np.float32)

DET_MAX_SEITE = int(os.environ.get("EPM_OCR_DET_MAX", "2048"))
DET_SCHWELLE = 0.3
DET_BOX_SCHWELLE = 0.55
DET_UNCLIP = 1.6
REC_HOEHE = 48
REC_BREITE = 320
REC_STAPEL = 8


@dataclass
class PZeile:
    """Eine erkannte Textzeile: Ecken im Seitenbild (oben links, oben rechts, unten rechts, unten links),
    Text, Sicherheit und je Zeichen (Text, x-Anteil Anfang/Ende in der Zeile 0–1, Sicherheit)."""

    ecken: np.ndarray
    text: str
    c: float
    zeichen: list


def modell_ordner() -> Path:
    return Path(os.environ.get("EPM_OCR_MODELLE", "/opt/ocr-modelle"))


def _sitzung(pfad: Path):
    import onnxruntime as ort

    opt = ort.SessionOptions()
    threads = int(os.environ.get("EPM_OCR_THREADS", "2"))
    opt.intra_op_num_threads = max(1, threads)
    opt.inter_op_num_threads = 1
    opt.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    # Jede Seite hat eine andere Größe: Mit Speicher-Arena und Speichermuster behält onnxruntime den Höchststand jeder
    # Größe und wächst von Seite zu Seite – bis zur Speichergrenze des Containers (Seite 2 bricht ab). Ohne beides
    # wird der Speicher nach jedem Lauf zurückgegeben; das kostet wenig Zeit.
    opt.enable_cpu_mem_arena = False
    opt.enable_mem_pattern = False
    opt.log_severity_level = 3
    return ort.InferenceSession(str(pfad), sess_options=opt, providers=["CPUExecutionProvider"])


def speicher_mb() -> int | None:
    """Speicher, der dem Dienst zusteht: Grenze des Containers (cgroup v2/v1), sonst RAM des Rechners."""
    for pfad in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            wert = Path(pfad).read_text().strip()
        except OSError:
            continue
        if wert.isdigit() and int(wert) < 1 << 50:  # „max“ bzw. riesiger Wert = keine Grenze
            return int(wert) // (1024 * 1024)
    try:
        for zeile in Path("/proc/meminfo").read_text().splitlines():
            if zeile.startswith("MemTotal:"):
                return int(zeile.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def modus() -> str:
    """"voll" oder "sparsam" – aus EPM_OCR_MODUS bzw. (auto) aus dem verfügbaren Speicher."""
    wahl = os.environ.get("EPM_OCR_MODUS", "auto").strip().lower()
    if wahl in ("voll", "sparsam"):
        return wahl
    mb = speicher_mb()
    return "sparsam" if mb is not None and mb < SPAR_GRENZE_MB else "voll"


class Paddle:
    """Lädt die Modelle einmal je Prozess (der Worker hält sie im Speicher)."""

    _instanz = None
    _sperre = threading.Lock()

    def __init__(self, ordner: Path, sparsam: bool = False):
        self.ordner = ordner
        # Sparmodus: kleines Zeilenmodell (falls vorhanden), kein Glätten, kleinere Zeilensuche
        self.sparsam = sparsam
        klein = ordner / DET_KLEIN
        self.det_name = "mobile_det" if sparsam and klein.is_file() else "server_det"
        self.det = _sitzung(klein if self.det_name == "mobile_det" else ordner / DET)
        self.det_max = DET_MAX_KLEIN if sparsam else DET_MAX_SEITE
        self.rec = _sitzung(ordner / REC)
        zeichen = (ordner / DICT).read_text(encoding="utf-8").splitlines()
        self.dict = [z for z in zeichen if z != ""] if zeichen and zeichen[-1] == "" else zeichen
        self.uvdoc = _sitzung(ordner / UVDOC) if (not sparsam and (ordner / UVDOC).is_file()) else None
        form = self.rec.get_inputs()[0].shape
        self.rec_hoehe = form[2] if isinstance(form[2], int) and form[2] > 0 else REC_HOEHE

    @classmethod
    def laden(cls) -> "Paddle | None":
        with cls._sperre:
            if cls._instanz is None:
                ordner = modell_ordner()
                if not (((ordner / DET).is_file() or (ordner / DET_KLEIN).is_file())
                        and (ordner / REC).is_file() and (ordner / DICT).is_file()):
                    return None
                sparsam = modus() == "sparsam" or not (ordner / DET).is_file()
                cls._instanz = cls(ordner, sparsam=sparsam)
            return cls._instanz

    # ------------------------------------------------------------ Zeilen finden
    def zeilen_finden(self, bild: np.ndarray, det_max: int | None = None) -> list[np.ndarray]:
        bgr = bild if bild.ndim == 3 else cv2.cvtColor(bild, cv2.COLOR_GRAY2BGR)
        h, w = bgr.shape[:2]
        f = min(1.0, min(det_max or self.det_max, self.det_max) / max(h, w))
        nh = max(32, int(round(h * f / 32)) * 32)
        nw = max(32, int(round(w * f / 32)) * 32)
        klein = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_LINEAR)
        x = (klein.astype(np.float32) / 255.0 - MITTEL) / STREUUNG
        x = x.transpose(2, 0, 1)[None].astype(np.float32)
        karte = self.det.run(None, {self.det.get_inputs()[0].name: x})[0]
        karte = np.asarray(karte).reshape(karte.shape[-2], karte.shape[-1])
        return db_boxen(karte, w / nw, h / nh, w, h)

    # ------------------------------------------------------------ Zeilen lesen
    def lesen(self, bild: np.ndarray, boxen: list[np.ndarray]) -> list[PZeile]:
        bgr = bild if bild.ndim == 3 else cv2.cvtColor(bild, cv2.COLOR_GRAY2BGR)
        ausschnitte = [zuschneiden(bgr, b) for b in boxen]
        reihenfolge = np.argsort([a.shape[1] / max(a.shape[0], 1) for a in ausschnitte])
        ergebnis: list[PZeile | None] = [None] * len(boxen)
        for start in range(0, len(reihenfolge), REC_STAPEL):
            nummern = reihenfolge[start:start + REC_STAPEL]
            stapel = [ausschnitte[i] for i in nummern]
            hoehe = self.rec_hoehe
            max_verh = max(REC_BREITE / REC_HOEHE, *(a.shape[1] / max(a.shape[0], 1) for a in stapel))
            breite = int(math.ceil(hoehe * max_verh))
            x = np.zeros((len(stapel), 3, hoehe, breite), dtype=np.float32)
            genutzt = []
            for j, a in enumerate(stapel):
                verh = a.shape[1] / max(a.shape[0], 1)
                nb = min(breite, max(1, int(math.ceil(hoehe * verh))))
                r = cv2.resize(a, (nb, hoehe), interpolation=cv2.INTER_LINEAR).astype(np.float32)
                r = (r / 255.0 - 0.5) / 0.5
                x[j, :, :, :nb] = r.transpose(2, 0, 1)
                genutzt.append(nb / breite)
            aus = self.rec.run(None, {self.rec.get_inputs()[0].name: x})[0]
            for j, i in enumerate(nummern):
                text, c, zeichen = ctc_lesen(aus[j], self.dict, genutzt[j])
                ergebnis[i] = PZeile(ecken=boxen[i], text=text, c=c, zeichen=zeichen)
        return [z for z in ergebnis if z is not None and z.text.strip()]

    def erkennen(self, bild: np.ndarray, det_max: int | None = None) -> list[PZeile]:
        return self.lesen(bild, self.zeilen_finden(bild, det_max))

    # ------------------------------------------------------------ Glätten
    def glaetten(self, bild: np.ndarray) -> np.ndarray:
        if self.uvdoc is None:
            raise RuntimeError("Modell zum Glätten (UVDoc) fehlt")
        bgr = bild if bild.ndim == 3 else cv2.cvtColor(bild, cv2.COLOR_GRAY2BGR)
        h, w = bgr.shape[:2]
        f = min(1.0, 2600 / max(h, w))
        if f < 1:
            bgr = cv2.resize(bgr, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        x = rgb.transpose(2, 0, 1)[None]
        aus = np.asarray(self.uvdoc.run(None, {self.uvdoc.get_inputs()[0].name: x})[0])
        if aus.ndim == 4 and aus.shape[1] == 3:
            # Ausgabe ist das entzerrte Bild (0–1, RGB)
            img = np.clip(aus[0].transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8)
            return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        if aus.ndim == 4 and aus.shape[1] == 2:
            # Ausgabe ist ein Gitter (-1…1): auf Bildgröße bringen und das Bild danach abtasten
            gitter = aus[0].transpose(1, 2, 0)
            hh, ww = bgr.shape[:2]
            gitter = cv2.resize(gitter, (ww, hh), interpolation=cv2.INTER_LINEAR)
            karte_x = ((gitter[..., 0] + 1) / 2 * (ww - 1)).astype(np.float32)
            karte_y = ((gitter[..., 1] + 1) / 2 * (hh - 1)).astype(np.float32)
            return cv2.remap(bgr, karte_x, karte_y, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        raise RuntimeError(f"unerwartete Ausgabe des Glättungsmodells {aus.shape}")


# ---------------------------------------------------------------- Nachbearbeitung (ohne Modell prüfbar)
def ordne(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=np.float32).reshape(4, 2)
    nach_x = p[np.argsort(p[:, 0])]
    links, rechts = nach_x[:2], nach_x[2:]
    tl, bl = links[np.argsort(links[:, 1])]
    tr, br = rechts[np.argsort(rechts[:, 1])]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _box_wert(karte: np.ndarray, box: np.ndarray) -> float:
    h, w = karte.shape
    xmin = int(np.clip(np.floor(box[:, 0].min()), 0, w - 1))
    xmax = int(np.clip(np.ceil(box[:, 0].max()), 0, w - 1))
    ymin = int(np.clip(np.floor(box[:, 1].min()), 0, h - 1))
    ymax = int(np.clip(np.ceil(box[:, 1].max()), 0, h - 1))
    maske = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
    pts = box.copy()
    pts[:, 0] -= xmin
    pts[:, 1] -= ymin
    cv2.fillPoly(maske, [pts.round().astype(np.int32)], 1)
    if maske.sum() == 0:
        return 0.0
    return float(cv2.mean(karte[ymin:ymax + 1, xmin:xmax + 1], maske)[0])


def db_boxen(karte: np.ndarray, fx: float, fy: float, breite: int, hoehe: int) -> list[np.ndarray]:
    """Wahrscheinlichkeitskarte (DB) → Zeilen als Vierecke in Bildkoordinaten, von oben nach unten sortiert."""
    maske = (karte > DET_SCHWELLE).astype(np.uint8) * 255
    konturen, _ = cv2.findContours(maske, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxen = []
    for k in konturen[:3000]:
        if len(k) < 3:
            continue
        (cx, cy), (rw, rh), winkel = cv2.minAreaRect(k)
        if min(rw, rh) < 2.5:
            continue
        box = cv2.boxPoints(((cx, cy), (rw, rh), winkel))
        if _box_wert(karte, box) < DET_BOX_SCHWELLE:
            continue
        flaeche, umfang = rw * rh, 2 * (rw + rh)
        d = flaeche * DET_UNCLIP / max(umfang, 1e-6)
        rw2, rh2 = rw + 2 * d, rh + 2 * d
        if min(rw2, rh2) < 5:
            continue
        box = ordne(cv2.boxPoints(((cx, cy), (rw2, rh2), winkel)))
        box[:, 0] = np.clip(box[:, 0] * fx, 0, breite - 1)
        box[:, 1] = np.clip(box[:, 1] * fy, 0, hoehe - 1)
        boxen.append(box)
    # oben nach unten, in einer Zeile links nach rechts
    boxen.sort(key=lambda b: (b[:, 1].min(), b[:, 0].min()))
    for i in range(len(boxen) - 1):
        for j in range(i, -1, -1):
            if abs(boxen[j + 1][0, 1] - boxen[j][0, 1]) < 10 and boxen[j + 1][0, 0] < boxen[j][0, 0]:
                boxen[j], boxen[j + 1] = boxen[j + 1], boxen[j]
            else:
                break
    return boxen


def zuschneiden(bild: np.ndarray, box: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = box
    b = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    b, h = max(b, 2), max(h, 2)
    ziel = np.array([[0, 0], [b, 0], [b, h], [0, h]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl], dtype=np.float32), ziel)
    aus = cv2.warpPerspective(bild, m, (b, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    if h / b >= 1.5:
        aus = np.rot90(aus)
    return np.ascontiguousarray(aus)


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def ctc_lesen(wahrsch: np.ndarray, zeichensatz: list[str], genutzt: float = 1.0) -> tuple[str, float, list]:
    """CTC-Dekodierung (gierig). ``genutzt``: Anteil der Eingabebreite, der Bild war (Rest aufgefüllt).
    Zeichen: (Text, Anfang 0–1, Ende 0–1, Sicherheit) bezogen auf die Breite des Ausschnitts."""
    p = np.asarray(wahrsch, dtype=np.float32)
    if p.min() < 0 or not np.allclose(p.sum(axis=-1), 1.0, atol=0.05):
        p = _softmax(p)
    schritte, klassen = p.shape
    alphabet = ["\u0000"] + list(zeichensatz)
    if klassen == len(alphabet) + 1:
        alphabet.append(" ")
    idx = p.argmax(axis=1)
    wert = p.max(axis=1)
    zeichen, vorher = [], 0
    t = 0
    while t < schritte:
        k = int(idx[t])
        if k == 0 or k >= len(alphabet):
            vorher = k
            t += 1
            continue
        if k == vorher:
            t += 1
            continue
        ende = t
        while ende + 1 < schritte and int(idx[ende + 1]) == k:
            ende += 1
        c = float(wert[t:ende + 1].max())
        anf = t / schritte / max(genutzt, 1e-6)
        end = (ende + 1) / schritte / max(genutzt, 1e-6)
        zeichen.append((alphabet[k], min(anf, 1.0), min(end, 1.0), c))
        vorher = k
        t = ende + 1
    text = "".join(z[0] for z in zeichen).strip()
    sicher = float(np.mean([z[3] for z in zeichen if z[0] != " "])) if zeichen else 0.0
    return text, sicher, zeichen
