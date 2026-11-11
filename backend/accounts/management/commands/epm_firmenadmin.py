"""Macht eine Person zum Admin einer Firma (Anforderung 11.10.2026: Rollen je Firma).

Eine Rolle in einer Firma vergibt in der Oberfläche nur ein Admin dieser Firma. Den ersten Admin einer Firma (z. B. der
Regeneration Clinic) kann deshalb niemand in der Oberfläche ernennen – dafür ist dieser Befehl da. Er steht im Audit-Log.

    sudo docker compose exec backend python manage.py epm_firmenadmin admin rg
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from accounts.models import Mitgliedschaft, Rolle, User
from audit.models import SystemEreignis, protokolliere
from stammdaten.models import Firma


class Command(BaseCommand):
    help = "Gibt einer Person die Rolle Admin in einer Firma (erster Admin einer Firma, z. B. der Regeneration Clinic)."

    def add_arguments(self, parser):
        parser.add_argument("benutzername")
        parser.add_argument("firma", help="Kürzel oder Kurzname der Firma, z. B. rg oder dskm")

    def handle(self, *args, **opt):
        user = User.objects.filter(username=opt["benutzername"].strip()).first()
        if user is None:
            raise CommandError(f"Benutzer '{opt['benutzername']}' gibt es nicht.")
        if user.nur_historisch or not user.is_active:
            raise CommandError(f"'{user.username}' ist gesperrt oder ohne Login – bitte zuerst in EPM freigeben.")
        if user.ist_test:
            raise CommandError(f"'{user.username}' ist Testbenutzer – Testbenutzer können nicht Admin sein.")

        name = opt["firma"].strip()
        firma = Firma.objects.filter(Q(kuerzel__iexact=name) | Q(kurzname__iexact=name)).first()
        if firma is None:
            vorhanden = ", ".join(Firma.objects.values_list("kuerzel", flat=True))
            raise CommandError(f"Firma '{name}' gibt es nicht (vorhanden: {vorhanden}).")

        if firma.kuerzel == Firma.DSKM:
            # die DSKM-Rolle ist User.rolle (Hauptfirma)
            vorher = user.rolle
            user.rolle = Rolle.ADMIN
            user._history_user = None
            user.save(update_fields=["rolle"])
        else:
            m, _ = Mitgliedschaft.objects.get_or_create(benutzer=user, firma=firma)
            vorher = m.rolle
            m.rolle = Rolle.ADMIN
            m._history_user = None
            m.save()

        if vorher == Rolle.ADMIN:
            self.stdout.write(f"{user.username} ist bei {firma.name} bereits Admin – nichts geändert.")
            return
        feld = "rolle" if firma.kuerzel == Firma.DSKM else f"rolle_{firma.kuerzel}"
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, benutzername="manage.py", objekt=user.username,
                      quelle="Kommandozeile", aenderungen={feld: [vorher, Rolle.ADMIN]})
        self.stdout.write(self.style.SUCCESS(f"{user.username} ist jetzt Admin bei {firma.name} (vorher: {vorher})."))
        self.stdout.write("Bitte einmal ab- und wieder anmelden.")
