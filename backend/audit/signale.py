"""Anmeldungen und Fehlversuche ins Systemprotokoll."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import SystemEreignis, protokolliere


@receiver(user_logged_in, dispatch_uid="epm_login")
def _login(sender, request, user, **kwargs):
    protokolliere(SystemEreignis.Art.ANMELDUNG, request, benutzer=user, schritt="kennwort")


@receiver(user_logged_out, dispatch_uid="epm_logout")
def _logout(sender, request, user, **kwargs):
    if user is not None:
        protokolliere(SystemEreignis.Art.ABMELDUNG, request, benutzer=user)


@receiver(user_login_failed, dispatch_uid="epm_login_failed")
def _login_failed(sender, credentials, request=None, **kwargs):
    protokolliere(
        SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, request,
        benutzername=str(credentials.get("username", ""))[:150],
    )
