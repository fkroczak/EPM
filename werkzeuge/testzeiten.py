#!/usr/bin/env python3
"""Laufzeiten je Testklasse für die Aufteilung der Backend-Tests auf mehrere CI-Rechner (backend/epm/testlauf.py).

Liest die Ausgabe von ``manage.py test --durations 0`` (eine oder mehrere Dateien, z. B. die Ausgaben aller Teile
eines CI-Laufs) und schreibt backend/epm/testzeiten.json neu:

    python3 werkzeuge/testzeiten.py test-ausgabe-*.txt

Neu zu erfassen, wenn sich die Teile deutlich ungleich lang laufen (Zeiten stehen im CI-Kommentar je Teil).
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ZIEL = Path(__file__).resolve().parent.parent / "backend" / "epm" / "testzeiten.json"
ZEILE = re.compile(r"^([0-9.]+)s\s+\S+ \(([\w.]+)\.\w+\)\s*$")


def main(dateien):
    klassen = Counter()
    for datei in dateien:
        for zeile in Path(datei).read_text(encoding="utf-8", errors="replace").splitlines():
            if t := ZEILE.match(zeile):
                klassen[t[2]] += float(t[1])
    if not klassen:
        sys.exit("keine Laufzeiten gefunden – mit --durations 0 testen")
    ZIEL.write_text(json.dumps({
        "hinweis": "Sekunden je Testklasse (Summe der Tests), erzeugt mit werkzeuge/testzeiten.py",
        "klassen": {k: round(v, 1) for k, v in sorted(klassen.items())},
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(klassen)} Klassen, zusammen {sum(klassen.values()):.0f} s → {ZIEL}")


if __name__ == "__main__":
    main(sys.argv[1:])
