"""
Passkeys (WebAuthn) als zweiter Faktor – Festlegung 08.10.2026: statt oder neben dem Code aus der Authenticator-App,
bei der Anmeldung und bei jeder Bestätigung mit Passwort und zweitem Faktor (endgültig löschen, Wiederherstellen,
Updates, Import …).

Ablauf (immer zwei Schritte, die Aufgabe des Servers liegt in der Sitzung und gilt einmal, 5 Minuten):
  1. ``optionen(request, zweck)``  → Optionen für ``navigator.credentials.create/get`` (Challenge in der Sitzung)
  2. ``registrieren(request, …)`` bzw. ``pruefen(request, antwort, zweck)`` mit der Antwort des Browsers

Voraussetzung: Aufruf über einen Namen mit gültigem Zertifikat (``EPM_PASSKEY_ORIGINS``/``EPM_PASSKEY_RP_ID``).
Über eine IP-Adresse lehnen Browser Passkeys ab; ``verfuegbar()`` meldet dann ``False`` mit Grund.
"""
import ipaddress
import logging
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone
from webauthn import (
    generate_authentication_options, generate_registration_options, verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json_dict
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria, AuthenticatorTransport, PublicKeyCredentialDescriptor, ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import Passkey

log = logging.getLogger(__name__)

SITZUNG = "epm_passkey"
GUELTIG = timedelta(minutes=5)
ZWECKE = ("registrieren", "anmelden", "bestaetigen")
MAX_PASSKEYS = 10


class PasskeyFehler(Exception):
    """Fehler mit einer Meldung für die Oberfläche."""


def _ist_ip(name: str) -> bool:
    try:
        ipaddress.ip_address(name.strip("[]"))
        return True
    except ValueError:
        return False


def origins() -> list[str]:
    return [o.rstrip("/") for o in settings.EPM_PASSKEY_ORIGINS if o.startswith("https://")]


def rp_id() -> str:
    if settings.EPM_PASSKEY_RP_ID:
        return settings.EPM_PASSKEY_RP_ID
    # erste Adresse mit Namen; die IP der Verwaltungskarte steht oft zusätzlich in DJANGO_CSRF_TRUSTED_ORIGINS
    namen = [urlsplit(o).hostname or "" for o in origins()]
    return next((n for n in namen if n and not _ist_ip(n)), namen[0] if namen else "")


def verfuegbar() -> dict:
    """Für Oberfläche und Prüfungen: Passkeys möglich? Sonst mit Grund."""
    rp = rp_id()
    if not rp or not origins():
        return {"verfuegbar": False, "rp_id": "", "grund": "Für Passkeys ist keine Adresse eingerichtet "
                "(EPM_PASSKEY_ORIGINS bzw. DJANGO_CSRF_TRUSTED_ORIGINS mit https://<Name>)."}
    if _ist_ip(rp):
        return {"verfuegbar": False, "rp_id": rp, "grund": "Passkeys brauchen einen Namen statt einer IP-Adresse "
                "(z. B. https://epm.stiftung.lan mit Zertifikat der eigenen CA)."}
    return {"verfuegbar": True, "rp_id": rp, "grund": ""}


def _pruefe_verfuegbar():
    stand = verfuegbar()
    if not stand["verfuegbar"]:
        raise PasskeyFehler(stand["grund"])
    return stand["rp_id"]


def _transports(werte) -> list[AuthenticatorTransport]:
    erlaubt = {t.value for t in AuthenticatorTransport}
    return [AuthenticatorTransport(t) for t in (werte or []) if t in erlaubt]


def _beschreibung(p: Passkey) -> PublicKeyCredentialDescriptor:
    return PublicKeyCredentialDescriptor(id=base64url_to_bytes(p.credential_id), transports=_transports(p.transports))


def _merken(request, zweck: str, challenge: bytes):
    request.session[SITZUNG] = {"zweck": zweck, "challenge": bytes_to_base64url(challenge),
                                "bis": (timezone.now() + GUELTIG).isoformat()}


def _challenge(request, zweck: str, verbrauchen: bool) -> bytes:
    from datetime import datetime

    stand = request.session.get(SITZUNG) or {}
    if stand.get("zweck") != zweck or not stand.get("challenge"):
        raise PasskeyFehler("Die Anfrage für den Passkey fehlt oder ist abgelaufen. Bitte erneut versuchen.")
    if datetime.fromisoformat(stand["bis"]) < timezone.now():
        request.session.pop(SITZUNG, None)
        raise PasskeyFehler("Die Anfrage für den Passkey ist abgelaufen. Bitte erneut versuchen.")
    if verbrauchen:
        request.session.pop(SITZUNG, None)
    return base64url_to_bytes(stand["challenge"])


def optionen(request, zweck: str) -> dict:
    """Optionen für den Browser (JSON, Bytes als Base64URL). Für „anmelden“ und „bestaetigen“ nur die Passkeys dieser
    Person (sie hat sich davor mit dem Passwort angemeldet), für „registrieren“ ohne die schon vorhandenen."""
    if zweck not in ZWECKE:
        raise PasskeyFehler("Unbekannter Zweck.")
    rp = _pruefe_verfuegbar()
    user = request.user
    vorhanden = list(Passkey.objects.filter(user=user, confirmed=True))
    if zweck == "registrieren":
        if len(vorhanden) >= MAX_PASSKEYS:
            raise PasskeyFehler(f"Mehr als {MAX_PASSKEYS} Passkeys je Konto sind nicht vorgesehen.")
        opt = generate_registration_options(
            rp_id=rp, rp_name=settings.EPM_PASSKEY_NAME,
            user_id=f"epm-{user.pk}".encode(), user_name=user.username, user_display_name=user.anzeigename,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED),
            exclude_credentials=[_beschreibung(p) for p in vorhanden],
            timeout=120_000,
        )
    else:
        if not vorhanden:
            raise PasskeyFehler("Für dieses Konto ist kein Passkey eingerichtet.")
        opt = generate_authentication_options(
            rp_id=rp, allow_credentials=[_beschreibung(p) for p in vorhanden],
            user_verification=UserVerificationRequirement.REQUIRED, timeout=120_000,
        )
    _merken(request, zweck, opt.challenge)
    return options_to_json_dict(opt)


def registrieren(request, antwort, name: str) -> Passkey:
    """Antwort von ``navigator.credentials.create`` prüfen und den Passkey speichern."""
    rp = _pruefe_verfuegbar()
    challenge = _challenge(request, "registrieren", verbrauchen=True)
    try:
        ergebnis = verify_registration_response(
            credential=antwort, expected_challenge=challenge, expected_rp_id=rp, expected_origin=origins(),
            require_user_verification=True,
        )
    except Exception as e:  # jede ungültige Antwort (Aufbau, Signatur, Herkunft) gleich behandeln
        log.info("Passkey-Registrierung abgelehnt: %s", e)
        raise PasskeyFehler("Der Passkey konnte nicht eingerichtet werden. Bitte erneut versuchen.") from e
    kennung = bytes_to_base64url(ergebnis.credential_id)
    if Passkey.objects.filter(credential_id=kennung).exists():
        raise PasskeyFehler("Dieser Passkey ist bereits eingerichtet.")
    transports = antwort.get("response", {}).get("transports", []) if isinstance(antwort, dict) else []
    return Passkey.objects.create(
        user=request.user, name=(str(name or "").strip() or "Passkey")[:64], confirmed=True,
        credential_id=kennung, public_key=ergebnis.credential_public_key, sign_count=ergebnis.sign_count,
        transports=[t for t in transports if isinstance(t, str)][:8], aaguid=str(ergebnis.aaguid or "")[:36],
        synchronisiert=bool(ergebnis.credential_backed_up),
    )


def pruefen(request, antwort, zweck: str) -> Passkey | None:
    """Antwort von ``navigator.credentials.get`` prüfen: gültig → der verwendete Passkey (Zähler und „zuletzt“
    aktualisiert), sonst None. Die Aufgabe des Servers ist danach verbraucht – eine Antwort gilt genau einmal."""
    rp = _pruefe_verfuegbar()
    challenge = _challenge(request, zweck, verbrauchen=True)
    kennung = antwort.get("id") if isinstance(antwort, dict) else None
    passkey = (Passkey.objects.select_for_update().filter(user=request.user, confirmed=True, credential_id=kennung)
               .first() if isinstance(kennung, str) else None)
    if passkey is None:
        return None
    try:
        ergebnis = verify_authentication_response(
            credential=antwort, expected_challenge=challenge, expected_rp_id=rp, expected_origin=origins(),
            credential_public_key=bytes(passkey.public_key), credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except Exception as e:
        log.info("Passkey-Prüfung abgelehnt (%s): %s", zweck, e)
        return None
    passkey.sign_count = ergebnis.new_sign_count
    passkey.synchronisiert = bool(ergebnis.credential_backed_up)
    passkey.zuletzt_am = timezone.now()
    passkey.save(update_fields=["sign_count", "synchronisiert", "zuletzt_am"])
    return passkey


def daten(p: Passkey) -> dict:
    return {"id": p.id, "name": p.name, "angelegt_am": p.angelegt_am, "zuletzt_am": p.zuletzt_am,
            "synchronisiert": p.synchronisiert}
