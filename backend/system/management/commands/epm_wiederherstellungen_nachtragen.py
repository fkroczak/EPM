"""
Wiederherstellungen ins Audit-Log eintragen und alle Anmeldungen beenden (F63).

Läuft bei jedem Start des Backends (entrypoint.sh, nach den Migrationen, vor dem Nachholen der Löschungen). Nach einer
Wiederherstellung startet das Backend mit der zurückgespielten Datenbank; sie kennt den Auftrag nicht. Der Systemagent
hat ihn vorher in ``status/wiederherstellungen.json`` vermerkt – von dort kommt der Eintrag. Ohne Befund passiert nichts.

    docker compose exec backend python manage.py epm_wiederherstellungen_nachtragen
"""
from django.core.management.base import BaseCommand

from system.sicherung import wiederherstellungen_nachtragen


class Command(BaseCommand):
    help = "Trägt Wiederherstellungen aus dem Status des Servers ins Audit-Log ein und beendet alle Anmeldungen."

    def handle(self, *args, **opts):
        anzahl = wiederherstellungen_nachtragen()
        if anzahl:
            self.stdout.write(f"{anzahl} Wiederherstellung(en) im Audit-Log eingetragen, alle Anmeldungen beendet.")
