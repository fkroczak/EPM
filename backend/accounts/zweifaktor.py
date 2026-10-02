"""
Zweiter Faktor (Authenticator-App, Notfall-Codes): eingerichtet? Pflicht? Code gültig?

Festlegung 02.10.2026: Der zweite Faktor ist freiwillig (``Anmelderegeln``); die Administration kann ihn für Admins oder
für alle zur Pflicht machen. Wer ihn eingerichtet hat, meldet sich immer damit an. Bestätigungen mit Kennwort und Code
(endgültig löschen, Wiederherstellen, Updates, Neustart …) verlangen den Code von allen, die einen zweiten Faktor
haben; ohne zweiten Faktor genügt dort das Kennwort.
"""
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import Anmelderegeln, Rolle


def hat_zweiten_faktor(user) -> bool:
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def regel() -> str:
    return Anmelderegeln.aktuell().zweiter_faktor


def pflicht(user) -> bool:
    """Muss diese Person einen zweiten Faktor haben?"""
    wert = regel()
    if wert == Anmelderegeln.ZweiterFaktor.ALLE:
        return True
    return wert == Anmelderegeln.ZweiterFaktor.ADMINS and getattr(user, "rolle", None) == Rolle.ADMIN


def code_gueltig(user, code: str, notfallcodes: bool = True) -> bool:
    """Code aus der Authenticator-App (oder, wenn erlaubt, ein Notfall-Code – der damit verbraucht ist)."""
    code = str(code or "").replace(" ", "")
    if not code:
        return False
    geraete = list(TOTPDevice.objects.filter(user=user, confirmed=True))
    if notfallcodes:
        geraete += list(StaticDevice.objects.filter(user=user, confirmed=True))
    return any(g.verify_token(code) for g in geraete)


def code_bestaetigt(user, code: str, notfallcodes: bool = True) -> bool:
    """Für Bestätigungen in der Sitzung: ohne eingerichteten zweiten Faktor genügt das Kennwort."""
    if not hat_zweiten_faktor(user):
        return True
    return code_gueltig(user, code, notfallcodes=notfallcodes)
