"""
Zweiter Faktor (Authenticator-App, Notfall-Codes): eingerichtet? Pflicht? Code gültig?

Festlegung 02.10.2026: Der zweite Faktor ist freiwillig (``Anmelderegeln``); die Administration kann ihn für Admins oder
für alle zur Pflicht machen. Wer ihn eingerichtet hat, meldet sich immer damit an.
Festlegung 03.10.2026: Bestätigungen mit Kennwort und Code (endgültig löschen, Wiederherstellen, Updates, Neustart,
Sicherungs-Passwort, Übertragungsziel, Import …) verlangen **immer** den zweiten Faktor. Wer keinen eingerichtet hat,
muss ihn zuerst unter Mein Konto einrichten – ohne geht es nicht.
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


OHNE_ZWEITEN_FAKTOR = ("Dafür ist die Zwei-Faktor-Anmeldung nötig. Bitte zuerst unter Mein Konto › Anmeldung und "
                       "Sicherheit die Authenticator-App einrichten.")


def code_bestaetigt(user, code: str, notfallcodes: bool = True) -> bool:
    """Für Bestätigungen in der Sitzung: nur mit eingerichtetem zweitem Faktor und gültigem Code
    (Festlegung 03.10.2026). Ohne zweiten Faktor vorher mit ``hat_zweiten_faktor`` prüfen und
    ``OHNE_ZWEITEN_FAKTOR`` melden."""
    return hat_zweiten_faktor(user) and code_gueltig(user, code, notfallcodes=notfallcodes)
