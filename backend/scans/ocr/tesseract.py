"""Erkennung 1: Tesseract 5 (LSTM) mit dem genauesten deutschen Modell (tessdata_best, Apache-2.0).

Ausgabe je Wort: Text, Lage (Pixel), Sicherheit 0–1 und die Zugehörigkeit zu Block/Absatz/Zeile, damit die
Zusammenführung Zeilen bilden kann.
"""
from __future__ import annotations

import csv
import io
import os
import subprocess
import tempfile
from dataclasses import dataclass

import cv2
import numpy as np

from .aufbereitung import tessdata_umgebung, tesseract_befehl


@dataclass
class TWort:
    text: str
    x: int
    y: int
    w: int
    h: int
    c: float          # 0–1
    zeile: tuple      # (Block, Absatz, Zeile) – eindeutig je Seite


def verfuegbar() -> tuple[bool, str]:
    """(nutzbar, Beschreibung) – für die Systemseite."""
    try:
        aus = subprocess.run([*tesseract_befehl(), "--list-langs"], capture_output=True, text=True, timeout=20,
                             env=tessdata_umgebung())
        version = subprocess.run([*tesseract_befehl(), "--version"], capture_output=True, text=True, timeout=20,
                                 env=tessdata_umgebung())
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"Tesseract nicht gefunden ({e})"
    sprachen = {z.strip() for z in aus.stdout.splitlines()[1:]}
    erste = (version.stdout or version.stderr).splitlines()[:1]
    text = (erste[0] if erste else "tesseract").strip()
    if "deu" not in sprachen:
        return False, f"{text}: deutsches Modell fehlt"
    return True, f"{text} · Sprachen: {', '.join(sorted(sprachen))}"


def erkennen(bild: np.ndarray, *, psm: int = 3, woerterliste: str | None = None, timeout: int = 240) -> list[TWort]:
    """Wörter eines (Graustufen- oder Schwarz-Weiß-)Bildes. ``woerterliste``: Datei mit Fachwörtern (je Zeile eins)."""
    with tempfile.TemporaryDirectory(prefix="epm-tess-") as tmp:
        pfad = os.path.join(tmp, "s.png")
        cv2.imwrite(pfad, bild)
        befehl = [*tesseract_befehl(), pfad, "stdout", "-l", "deu", "--oem", "1", "--psm", str(psm),
                  "-c", "preserve_interword_spaces=1", "-c", "tessedit_create_tsv=1", "-c", "tessedit_create_txt=0",
                  "--dpi", "300"]
        # DPI angeben: sonst schätzt Tesseract und meldet „Invalid resolution“
        if woerterliste and os.path.isfile(woerterliste):
            befehl += ["--user-words", woerterliste]
        aus = subprocess.run(befehl, capture_output=True, text=True, timeout=timeout, env=tessdata_umgebung())
    if aus.returncode != 0:
        raise RuntimeError(f"Tesseract: {(aus.stderr or '').strip()[:300]}")
    return lese_tsv(aus.stdout)


def lese_tsv(tsv: str) -> list[TWort]:
    woerter = []
    leser = csv.reader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    kopf = next(leser, None)
    if not kopf:
        return woerter
    idx = {name: i for i, name in enumerate(kopf)}
    for z in leser:
        if len(z) < len(kopf) or z[idx["level"]] != "5":
            continue
        text = z[idx["text"]].strip()
        if not text:
            continue
        try:
            konf = float(z[idx["conf"]])
        except ValueError:
            continue
        if konf < 0:
            continue
        woerter.append(TWort(
            text=text, x=int(z[idx["left"]]), y=int(z[idx["top"]]), w=int(z[idx["width"]]), h=int(z[idx["height"]]),
            c=max(0.0, min(1.0, konf / 100.0)),
            zeile=(int(z[idx["block_num"]]), int(z[idx["par_num"]]), int(z[idx["line_num"]])),
        ))
    return woerter
