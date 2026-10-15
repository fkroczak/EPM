"""Datenbank-Rolle ``epm_ki`` für den KI-Dienst einrichten bzw. nachziehen (läuft nach jeder Migration).

    python manage.py epm_ki_dbrolle      # Passwort aus EPM_KI_DB_PASSWORD_FILE; ohne Datei: nichts zu tun
"""
import os
from pathlib import Path

from django.core.management.base import BaseCommand

from ki.dbrolle import einrichten


class Command(BaseCommand):
    help = "Datenbank-Rolle des KI-Dienstes (nur KI-Tabellen schreiben) einrichten."

    def handle(self, *args, **opt):
        datei = os.environ.get("EPM_KI_DB_PASSWORD_FILE", "")
        if not datei or not Path(datei).is_file():
            self.stdout.write("KI-Dienst nicht eingerichtet (kein EPM_KI_DB_PASSWORD_FILE) – nichts zu tun.")
            return
        passwort = Path(datei).read_text().strip()
        if not passwort:
            self.stdout.write("EPM_KI_DB_PASSWORD_FILE ist leer – nichts zu tun.")
            return
        e = einrichten(passwort)
        self.stdout.write(f"Rolle {e['rolle']}: {'angelegt' if e['neu'] else 'aktualisiert'}, schreibt "
                          f"{len(e['schreiben'])} KI-Tabellen, liest {e['lesen']} Tabellen.")
