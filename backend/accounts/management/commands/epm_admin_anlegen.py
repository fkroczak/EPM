from django.core.management.base import BaseCommand, CommandError

from accounts.models import Rolle, User
from audit.models import SystemEreignis, protokolliere


class Command(BaseCommand):
    help = "Legt einen Admin mit Einmal-Passwort an (beim ersten Login: eigenes Passwort + Authenticator)."

    def add_arguments(self, parser):
        parser.add_argument("benutzername")
        parser.add_argument("--vorname", default="")
        parser.add_argument("--nachname", default="")
        parser.add_argument("--titel", default="")
        parser.add_argument("--kuerzel", default=None)
        parser.add_argument("--neues-kennwort", action="store_true",
                            help="Vorhandenem Benutzer ein neues Einmal-Passwort geben (Notfall-Zugang)")

    def handle(self, *args, **opt):
        name = opt["benutzername"].strip()
        user = User.objects.filter(username=name).first()
        if user and not opt["neues_kennwort"]:
            raise CommandError(f"Benutzer '{name}' existiert bereits (--neues-kennwort für ein neues Einmal-Passwort).")
        if not user:
            user = User(username=name, first_name=opt["vorname"], last_name=opt["nachname"], titel=opt["titel"],
                        kuerzel=opt["kuerzel"] or None, rolle=Rolle.ADMIN, is_superuser=True)
        if opt["neues_kennwort"]:
            from accounts.zweifaktor import faktoren_loeschen
            faktoren_loeschen(user)
            user.is_active = True
        kennwort = user.neues_einmal_kennwort()
        user.save()
        protokolliere(SystemEreignis.Art.EINMAL_KENNWORT, benutzername="manage.py", objekt=user.username,
                      quelle="Kommandozeile")
        self.stdout.write("")
        self.stdout.write(f"  Benutzer:       {user.username} (Rolle Admin)")
        self.stdout.write(self.style.WARNING(f"  Einmal-Passwort: {kennwort}"))
        self.stdout.write("  Beim ersten Login: eigenes Passwort wählen, dann Authenticator-App einrichten.")
        self.stdout.write("")
