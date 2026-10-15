"""Benchmark einer Modellvariante (im Container ki-worker; gestartet von werkzeuge/ki-benchmark.sh).

    python manage.py epm_ki_benchmark --url http://epm-ki-bench:8080 [--eigene /data/ki/benchmark] \
        [--grosses-pdf 20] [--max-px 1600]

Gibt das Ergebnis als JSON aus (je Seite und je Kategorie: Sekunden je Seite, Tokens/s, CER, Laborwert-F1).
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ki.benchmark import ausfuehren


class Command(BaseCommand):
    help = "Modellvariante messen: Qualität (CER, Laborwerte) und Geschwindigkeit."

    def add_arguments(self, parser):
        parser.add_argument("--url", required=True)
        parser.add_argument("--eigene", default="")
        parser.add_argument("--grosses-pdf", type=int, default=20)
        parser.add_argument("--max-px", type=int, default=1600)

    def handle(self, *args, url, eigene, grosses_pdf, max_px, **opt):
        erg = ausfuehren(url, eigene=Path(eigene) if eigene else None, grosses_pdf=grosses_pdf, max_px=max_px)
        self.stdout.write(json.dumps(erg, ensure_ascii=False))
