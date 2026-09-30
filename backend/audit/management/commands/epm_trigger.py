from django.core.management.base import BaseCommand

from audit.schutz import installiere_trigger


class Command(BaseCommand):
    help = "Setzt die Schutz-Trigger (Protokolle unveränderlich) neu. Läuft sonst automatisch nach migrate."

    def handle(self, *args, **opt):
        installiere_trigger()
        self.stdout.write("Schutz-Trigger gesetzt.")
