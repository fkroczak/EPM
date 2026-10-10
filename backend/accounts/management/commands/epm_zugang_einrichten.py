"""
Zugang direkt auf dem Server einrichten: eigenes Passwort + Authenticator-App (QR im Terminal).

Für den ersten Admin und zum Testen, solange es noch kein Frontend gibt:
    sudo docker compose exec backend python manage.py epm_zugang_einrichten admin
"""
import getpass

import qrcode
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.api import neue_notfallcodes
from accounts.models import User
from audit.models import SystemEreignis, protokolliere


class Command(BaseCommand):
    help = "Passwort setzen und Authenticator-App einrichten (interaktiv, im Terminal)."

    def add_arguments(self, parser):
        parser.add_argument("benutzername")

    def handle(self, *args, **opt):
        user = User.objects.filter(username=opt["benutzername"]).first()
        if not user or user.nur_historisch:
            raise CommandError("Benutzer nicht gefunden.")

        # 1. Kennwort
        while True:
            k1 = getpass.getpass("Neues Passwort (mind. 12 Zeichen): ")
            k2 = getpass.getpass("Passwort wiederholen: ")
            if k1 != k2:
                self.stderr.write("Passwörter stimmen nicht überein.")
                continue
            try:
                password_validation.validate_password(k1, user)
                break
            except ValidationError as e:
                self.stderr.write(" ".join(e.messages))

        # 2. Authenticator
        geraet = TOTPDevice(user=user, name="Authenticator-App", confirmed=False)
        geraet.save()
        qr = qrcode.QRCode(border=1)
        qr.add_data(geraet.config_url)
        qr.make(fit=True)
        self.stdout.write("\nMit der Authenticator-App scannen (Terminal-Fenster ggf. vergrößern):\n")
        qr.print_ascii(out=self.stdout._out, invert=True)
        schluessel = geraet.config_url.split("secret=")[1].split("&")[0]
        self.stdout.write(f"\nOder Schlüssel von Hand eingeben: {schluessel}\n")
        for _ in range(3):
            code = input("6-stelliger Code aus der App: ").strip().replace(" ", "")
            if geraet.verify_token(code):
                break
            self.stderr.write("Code ungültig – Uhrzeit von Telefon und Server prüfen.")
        else:
            geraet.delete()
            raise CommandError("Abgebrochen, nichts geändert.")

        with transaction.atomic():
            TOTPDevice.objects.filter(user=user, confirmed=True).delete()
            geraet.confirmed = True
            geraet.save()
            user.set_password(k1)
            user.muss_kennwort_aendern = False
            user.is_active = True
            user.save()
            codes = neue_notfallcodes(user)
            protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_EINGERICHTET, benutzer=user, quelle="Kommandozeile")

        self.stdout.write(self.style.SUCCESS("\nZugang eingerichtet."))
        self.stdout.write("Notfall-Codes (je einmal gültig, ausdrucken und sicher verwahren):")
        for c in codes:
            self.stdout.write(f"   {c}")
        self.stdout.write("")
