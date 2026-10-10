"""Notfallplan (F188) auf die Standardausgabe – für den Systemagenten, der ihn ins Notfallpaket legt:

    python manage.py epm_notfallplan --format md|html|pdf
"""
import sys

from django.core.management.base import BaseCommand

from system import notfallplan


class Command(BaseCommand):
    help = "Notfallplan als Markdown, HTML oder PDF auf die Standardausgabe schreiben"

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=["md", "html", "pdf"], default="md")

    def handle(self, *args, **optionen):
        art = optionen["format"]
        if art == "pdf":
            sys.stdout.buffer.write(notfallplan.zu_pdf())
            sys.stdout.buffer.flush()
        elif art == "html":
            self.stdout.write(notfallplan.zu_html(), ending="")
        else:
            self.stdout.write(notfallplan.markdown(), ending="")
