"""
Zweiter Faktor (Authenticator-App, Notfall-Codes): eingerichtet? Pflicht? Code gültig?

Festlegung 02.10.2026: Der zweite Faktor ist freiwillig (``Anmelderegeln``); die Administration kann ihn für Admins oder
für alle zur Pflicht machen. Wer ihn eingerichtet hat, meldet sich immer damit an.
Festlegung 03.10.2026: Bestätigungen mit Passwort und Code (endgültig löschen, Wiederherstellen, Updates, Neustart,
Sicherungs-Passwort, Übertragungsziel, Import …) verlangen **immer** den zweiten Faktor. Wer keinen eingerichtet hat,
muss ihn zuerst unter Mein Konto einrichten – ohne geht es nicht.
Festlegung 08.10.2026: Ein Passkey (WebAuthn, accounts/passkey.py) ist ein gleichwertiger zweiter Faktor – bei der
Anmeldung und bei jeder Bestätigung. Die Oberfläche schickt dann statt ``code`` die Antwort des Browsers als
``passkey`` mit (``zweiter_faktor_bestaetigt``).
"""
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import Anmelderegeln, Passkey, Rolle


def hat_authenticator(user) -> bool:
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def hat_passkey(user) -> bool:
    return Passkey.objects.filter(user=user, confirmed=True).exists()


def hat_zweiten_faktor(user) -> bool:
    return hat_authenticator(user) or hat_passkey(user)


def nutzer_mit_zweitem_faktor() -> set:
    """IDs aller Konten mit eingerichtetem zweitem Faktor (Authenticator oder Passkey)."""
    return (set(TOTPDevice.objects.filter(confirmed=True).values_list("user_id", flat=True))
            | set(Passkey.objects.filter(confirmed=True).values_list("user_id", flat=True)))


def faktoren_loeschen(user):
    """Authenticator, Passkeys und Notfall-Codes löschen (2FA zurücksetzen, ohne Login, ausschalten)."""
    TOTPDevice.objects.filter(user=user).delete()
    Passkey.objects.filter(user=user).delete()
    StaticDevice.objects.filter(user=user).delete()


def regel() -> str:
    return Anmelderegeln.aktuell().zweiter_faktor


def pflicht(user) -> bool:
    """Muss diese Person einen zweiten Faktor haben?"""
    wert = regel()
    if wert == Anmelderegeln.ZweiterFaktor.ALLE:
        return True
    return wert == Anmelderegeln.ZweiterFaktor.ADMINS and ist_admin_in_einer_firma(user)


def ist_admin_in_einer_firma(user) -> bool:
    """Admin bei der DSKM (``rolle``) oder in einer weiteren Firma (``Mitgliedschaft``). Sicherheitsprüfung 11.10.2026:
    Vorher galt „Pflicht für Admins“ nur für die DSKM-Rolle – ein Admin nur der Regeneration Clinic blieb ohne."""
    from .models import Mitgliedschaft

    if getattr(user, "rolle", None) == Rolle.ADMIN:
        return True
    return bool(getattr(user, "pk", None)) and Mitgliedschaft.objects.filter(benutzer=user, rolle=Rolle.ADMIN).exists()


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
                       "Sicherheit die Authenticator-App oder einen Passkey einrichten.")
PASSKEY_UNGUELTIG = "Der Passkey konnte nicht bestätigt werden. Bitte erneut versuchen."


def code_bestaetigt(user, code: str, notfallcodes: bool = True) -> bool:
    """Für Bestätigungen in der Sitzung: nur mit eingerichtetem zweitem Faktor und gültigem Code
    (Festlegung 03.10.2026). Ohne zweiten Faktor vorher mit ``hat_zweiten_faktor`` prüfen und
    ``OHNE_ZWEITEN_FAKTOR`` melden."""
    return hat_zweiten_faktor(user) and code_gueltig(user, code, notfallcodes=notfallcodes)


def passkey_gesendet(request) -> bool:
    return bool(getattr(request, "data", None) and isinstance(request.data.get("passkey"), dict))


def zweiter_faktor_bestaetigt(request, notfallcodes: bool = True) -> bool:
    """Bestätigung in der Sitzung mit dem zweiten Faktor aus der Anfrage: ``passkey`` (Antwort des Browsers auf
    ``POST /api/auth/passkey/optionen/`` mit Zweck „bestaetigen“) oder ``code`` (Authenticator, ggf. Notfall-Code).
    Wie ``code_bestaetigt`` nur mit eingerichtetem zweitem Faktor."""
    user = request.user
    if not hat_zweiten_faktor(user):
        return False
    if passkey_gesendet(request):
        from .passkey import PasskeyFehler, pruefen

        try:
            return pruefen(request, request.data["passkey"], "bestaetigen") is not None
        except PasskeyFehler:
            return False
    return code_gueltig(user, request.data.get("code", ""), notfallcodes=notfallcodes)


def fehlertext(request, standard: str) -> str:
    """Meldung bei abgelehnter Bestätigung: beim Passkey eine eigene, sonst die bisherige zum Code."""
    return PASSKEY_UNGUELTIG if passkey_gesendet(request) else standard
