"""Modelle der zweiten Erkennung laden und prüfen (beim Bau des Images, in GitHub Actions, auf dem PC).

    python scans/modelle/holen.py ZIELORDNER                 # laden (oder aus dateien/ übernehmen) und prüfen
    python scans/modelle/holen.py --nur-pruefen ORDNER       # nur prüfen, nichts laden

Liegen die Dateien schon neben dieser Liste in ``dateien/`` (offline vorbereitet mit ``werkzeuge/ocr-modelle.sh``;
``epm-update`` legt sie vor dem Bau dorthin), werden sie von dort übernommen – der Bau braucht dann keinen Zugang zu
huggingface.co. Jede Datei wird gegen ihre Prüfsumme aus ``modelle.json`` geprüft (SHA-256, bei kleinen Textdateien die Git-Kennung);
was schon vorhanden und richtig ist, wird nicht erneut geladen. Ohne Python-Pakete außer der Standardbibliothek;
ein Proxy aus ``HTTPS_PROXY`` wird benutzt. Rückgabe 0 = alles da, 1 = etwas fehlt.
"""
import hashlib
import shutil
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

LISTE = Path(__file__).with_name("modelle.json")
VORRAT = Path(__file__).with_name("dateien")


def pruefen(pfad: Path, eintrag: dict) -> bool:
    if not pfad.is_file() or pfad.stat().st_size != eintrag["groesse"]:
        return False
    daten = pfad.read_bytes()
    if "sha256" in eintrag:
        return hashlib.sha256(daten).hexdigest() == eintrag["sha256"]
    kopf = f"blob {len(daten)}\0".encode()
    return hashlib.sha1(kopf + daten).hexdigest() == eintrag["git_sha1"]


def holen(ziel: Path, laden: bool = True) -> bool:
    liste = json.loads(LISTE.read_text(encoding="utf-8"))
    alles_da = True
    for eintrag in liste["dateien"]:
        pfad = ziel / eintrag["pfad"]
        if pruefen(pfad, eintrag):
            print(f"vorhanden  {eintrag['pfad']}")
            continue
        vorrat = VORRAT / eintrag["pfad"]
        if laden and vorrat.resolve() != pfad.resolve() and pruefen(vorrat, eintrag):
            pfad.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(vorrat, pfad)
            print(f"übernommen {eintrag['pfad']} (offline vorbereitet)")
            continue
        if not laden:
            print(f"FEHLT      {eintrag['pfad']}", file=sys.stderr)
            alles_da = False
            continue
        pfad.parent.mkdir(parents=True, exist_ok=True)
        url = eintrag.get("url") or liste["quelle"] + eintrag["pfad"]
        for versuch in range(1, 4):
            tmp = pfad.with_suffix(pfad.suffix + ".teil")
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "EPM-Bau"}),
                                            timeout=120) as antwort, open(tmp, "wb") as f:
                    while teil := antwort.read(1 << 20):
                        f.write(teil)
                os.replace(tmp, pfad)
            except OSError as fehler:
                print(f"Versuch {versuch}: {eintrag['pfad']}: {fehler}", file=sys.stderr)
                tmp.unlink(missing_ok=True)
                time.sleep(3 * versuch)
                continue
            if pruefen(pfad, eintrag):
                print(f"geladen    {eintrag['pfad']} ({eintrag['groesse'] / 1e6:.1f} MB)")
                break
            print(f"Prüfsumme falsch: {eintrag['pfad']}", file=sys.stderr)
            pfad.unlink(missing_ok=True)
        else:
            alles_da = False
    if laden:
        (ziel / "LIZENZ.txt").write_text(liste["lizenz"] + "\n", encoding="utf-8")
    return alles_da


if __name__ == "__main__":
    argumente = sys.argv[1:]
    nur_pruefen = "--nur-pruefen" in argumente
    argumente = [a for a in argumente if a != "--nur-pruefen"]
    if len(argumente) != 1:
        sys.exit(__doc__)
    ok = holen(Path(argumente[0]), laden=not nur_pruefen)
    print("Modelle vollständig" if ok else "WARNUNG: Modelle unvollständig – die Erkennung arbeitet dann nur mit Tesseract")
    sys.exit(0 if ok else 1)
