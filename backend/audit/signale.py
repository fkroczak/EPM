"""Anmeldungen und Fehlversuche ins Systemprotokoll."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import SystemEreignis, protokolliere


@receiver(user_logged_in, dispatch_uid="epm_login")
def _login(sender, request, user, **kwargs):
    from accounts.zweifaktor import hat_zweiten_faktor, pflicht

    # zweiter Faktor freiwillig (Festlegung 02.10.2026): ohne ihn ist die Anmeldung mit dem Kennwort abgeschlossen
    offen = hat_zweiten_faktor(user) or pflicht(user)
    protokolliere(SystemEreignis.Art.ANMELDUNG, request, benutzer=user, schritt="kennwort" if offen else "ohne_2fa")


@receiver(user_logged_out, dispatch_uid="epm_logout")
def _logout(sender, request, user, **kwargs):
    if user is not None:
        protokolliere(SystemEreignis.Art.ABMELDUNG, request, benutzer=user)


@receiver(user_login_failed, dispatch_uid="epm_login_failed")
def _login_failed(sender, credentials, request=None, **kwargs):
    from accounts.models import User

    name = str(credentials.get("username", ""))[:150]
    konto = User.objects.filter(username=name, nur_historisch=False, is_active=True).first()
    details = {"versuch": konto.fehlversuche + 1} if konto is not None else {}
    protokolliere(SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, request, benutzername=name, **details)
    # Django-Verwaltung (/verwaltung/): Fehlversuche zählen wie in der App, sonst ließe sich das Passwort dort ohne
    # Sperre ausprobieren. Die Anmeldung der App zählt selbst (accounts.api.AnmeldenView) – nicht doppelt.
    if konto is not None and request is not None and request.path.startswith("/verwaltung/"):
        from accounts.api import fehlversuch

        fehlversuch(konto, request, "kennwort")
