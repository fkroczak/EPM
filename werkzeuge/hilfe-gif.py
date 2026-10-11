#!/usr/bin/env python3
"""
Bilder für die Hilfe nachbearbeiten (Wunsch 11.10.2026: Hilfe mit Bildschirmfotos und kurzen GIFs).
Wird von ``werkzeuge/hilfe-bilder.mjs`` aufgerufen; braucht Pillow.

  hilfe-gif.py gif <ziel.gif> <standbild.png> <standbild-nr> <breite> <ausschnitt> <bild1.png> <bild2.png> …
      Einzelbilder (gleich groß) → GIF mit ca. 1,2 s je Bild (letztes Bild länger), Endlosschleife, eine gemeinsame
      adaptive Palette. Dazu ein Standbild (Bild Nr. <standbild-nr>, ab 1) für „Bewegung reduzieren“.
  hilfe-gif.py png <ziel.png> <quelle.png> <breite> <ausschnitt>
      Bildschirmfoto übernehmen; breiter als <breite> → verkleinert, größer als ca. 250 KB → auf 256 Farben reduziert.

<breite> 0 = Originalgröße behalten. <ausschnitt> „x,y,breite,höhe“ in Bildpunkten der Quelle (Bildschirmfoto des
sichtbaren Bereichs), „-“ = ganzes Bild.
"""
import os
import sys

from PIL import Image

DAUER_MS = 1200          # je Einzelbild
DAUER_LETZTES_MS = 2400  # das Ergebnis etwas länger stehen lassen, bevor es von vorn beginnt
PNG_GRENZE = 250 * 1024


def _laden(quelle: str, ausschnitt: str, breite: str) -> Image.Image:
    with Image.open(quelle) as b:
        bild = b.convert("RGB")
    if ausschnitt != "-":
        x, y, w, h = (int(v) for v in ausschnitt.split(","))
        bild = bild.crop((x, y, min(x + w, bild.width), min(y + h, bild.height)))
    return _breite(bild, int(breite))


def _breite(bild: Image.Image, breite: int) -> Image.Image:
    if breite and bild.width > breite:
        hoehe = round(bild.height * breite / bild.width)
        return bild.resize((breite, hoehe), Image.LANCZOS)
    return bild


def png_speichern(bild: Image.Image, ziel: str) -> None:
    bild = bild.convert("RGB")
    bild.save(ziel, optimize=True)
    if os.path.getsize(ziel) > PNG_GRENZE:
        # Oberflächen haben wenige Farben: 256 Farben sehen gleich aus und sind ein Bruchteil so groß
        bild.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(ziel, optimize=True)


def png(ziel: str, quelle: str, breite: str, ausschnitt: str = "-") -> None:
    png_speichern(_laden(quelle, ausschnitt, breite), ziel)


def gif(ziel: str, standbild: str, nr: str, breite: str, ausschnitt: str, *quellen: str) -> None:
    bilder = [_laden(q, ausschnitt, breite) for q in quellen]
    groesse = bilder[0].size
    bilder = [b if b.size == groesse else b.resize(groesse, Image.LANCZOS) for b in bilder]
    # Eine Palette für alle Bilder (aus allen zusammen berechnet) – sonst flackern Flächen beim Bildwechsel
    muster = Image.new("RGB", (groesse[0], groesse[1] * len(bilder)))
    for i, b in enumerate(bilder):
        muster.paste(b, (0, i * groesse[1]))
    palette = muster.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    einzel = [b.quantize(palette=palette, dither=Image.Dither.NONE) for b in bilder]
    dauer = [DAUER_MS] * (len(einzel) - 1) + [DAUER_LETZTES_MS]
    einzel[0].save(ziel, save_all=True, append_images=einzel[1:], duration=dauer, loop=0, optimize=True, disposal=1)
    png_speichern(bilder[int(nr) - 1], standbild)


if __name__ == "__main__":
    art, *argumente = sys.argv[1:]
    {"gif": gif, "png": png}[art](*argumente)
