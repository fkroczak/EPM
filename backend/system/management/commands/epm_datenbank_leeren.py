"""Datenbank leeren (U27) – nur über den Systemagenten aufrufen (Administration › System › „Datenbank leeren“, nach einer
Sicherung). Siehe ``system/leeren.py``."""
import json

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from audit.models import SystemEreignis, protokolliere
from system.leeren import datenbank_leeren


class Command(BaseCommand):
    help = "Alle Akten, Dokumente, Versorger, Ärzte, Benutzer (außer --behalten) und das Audit-Log entfernen."

    def add_arguments(self, parser):
        parser.add_argument("--von", required=True, help="Benutzername des Kontos, das den Auftrag gegeben hat")
        parser.add_argument("--behalten", default="", help="IDs der Konten, die bleiben (Komma-getrennt)")
        parser.add_argument("--sicherung", default="", help="Zeitstempel der Sicherung vorher (für das Audit-Log)")
        parser.add_argument("--ja", action="store_true", help="ohne diese Angabe passiert nichts")

    def handle(self, *args, **opt):
        if not opt["ja"]:
            raise CommandError("Nur mit --ja (die Oberfläche fragt vorher mehrfach nach).")
        von = User.objects.filter(username=opt["von"], nur_historisch=False).first()
        if von is None:
            raise CommandError(f"Unbekanntes Konto: {opt['von']}")
        try:
            behalten = [int(x) for x in opt["behalten"].split(",") if x.strip()]
        except ValueError:
            raise CommandError("--behalten: Zahlen mit Komma getrennt") from None
        zahlen = datenbank_leeren(von, behalten)
        protokolliere(SystemEreignis.Art.SYSTEM, benutzer=von, objekt="Datenbank", ereignis="datenbank_geleert",
                      sicherung=opt["sicherung"], **{k: v for k, v in zahlen.items() if k != "benutzer_behalten"},
                      benutzer_behalten=len(zahlen["benutzer_behalten"]))
        self.stdout.write(json.dumps(zahlen, ensure_ascii=False))
