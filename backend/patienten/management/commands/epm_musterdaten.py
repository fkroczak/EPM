from django.core.management.base import BaseCommand

from patienten.testdaten import (
    stammdaten_anlegen, testbenutzer_anlegen, testdaten_zuruecksetzen, testpatienten_anlegen,
)


class Command(BaseCommand):
    help = "Legt Auswahllisten, Präparate, Testbenutzer und Testpatienten (ab Nr. 9001) an."

    def add_arguments(self, parser):
        parser.add_argument("--nur-stammdaten", action="store_true",
                            help="Nur Auswahllisten und Präparate (für den Echtbetrieb)")
        parser.add_argument("--zuruecksetzen", action="store_true",
                            help="Alle Testpatienten löschen und neu anlegen")

    def handle(self, *args, **opt):
        neu = stammdaten_anlegen()
        self.stdout.write(f"Stammdaten: {neu['auswahlwerte']} Auswahlwerte, {neu['praeparate']} Präparate neu.")
        if opt["nur_stammdaten"]:
            return
        from stammdaten.models import Einstellungen

        if not opt["zuruecksetzen"] and not Einstellungen.aktuell().musterdaten_automatisch:
            # nach „Datenbank leeren“ bzw. unter Administration › System abgeschaltet (Festlegung 03.10.2026)
            self.stdout.write("Musterdaten: automatisches Anlegen ist abgeschaltet (Administration › System).")
            return
        user, kennwort = testbenutzer_anlegen()
        if kennwort:
            self.stdout.write(self.style.WARNING(
                f"Testbenutzer '{user.username}' angelegt. Einmal-Passwort: {kennwort}"))
        else:
            self.stdout.write(f"Testbenutzer '{user.username}' ist vorhanden.")
        if opt["zuruecksetzen"]:
            r = testdaten_zuruecksetzen()
            self.stdout.write(f"Testdaten zurückgesetzt: {r['geloescht']} gelöscht, {r['angelegt']} angelegt.")
        else:
            anzahl = testpatienten_anlegen()
            self.stdout.write(f"Testpatienten: {anzahl} neu angelegt." if anzahl else "Testpatienten sind vorhanden.")
