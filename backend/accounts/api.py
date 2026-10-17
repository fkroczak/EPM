"""
Anmeldung (Passwort → ggf. eigenes Passwort → Authenticator-App → Code) und Benutzerverwaltung.

Ablauf beim ersten Login:
  1. POST /api/auth/anmelden          Benutzername + Einmal-Passwort
  2. POST /api/auth/kennwort          eigenes Passwort wählen
  3. POST /api/auth/2fa/einrichten    QR-Code für die Authenticator-App
  4. POST /api/auth/2fa/bestaetigen   ersten Code eingeben → Notfall-Codes (einmalig angezeigt)
Danach bei jeder Anmeldung: 1. und POST /api/auth/2fa mit dem aktuellen Code.

Passkey statt Code (Festlegung 08.10.2026, accounts/passkey.py):
  POST /api/auth/passkey/optionen/      {"zweck": "anmelden"|"bestaetigen"|"registrieren"} → Optionen für den Browser
  POST /api/auth/passkey/               Antwort des Browsers → Anmeldung abgeschlossen (wie POST /api/auth/2fa)
  POST /api/auth/passkey/registrieren/  {"antwort", "name"} → Passkey gespeichert (erster zweiter Faktor: Notfall-Codes)
  GET  /api/auth/passkeys/              eigene Passkeys; PATCH /api/auth/passkeys/<id>/ {"name"} umbenennen;
  POST /api/auth/passkeys/<id>/entfernen/ mit Passwort und zweitem Faktor

Der zweite Faktor ist freiwillig (Festlegung 02.10.2026, ``Anmelderegeln``): Ohne Pflicht entfallen 3. und 4.; wer
die Authenticator-App trotzdem einrichtet (Mein Konto), meldet sich danach immer mit Code an und kann sie dort mit
POST /api/auth/2fa/ausschalten wieder ausschalten. Die Administration kann die Pflicht für Admins oder für alle setzen
(GET/PUT /api/benutzer/anmeldung/).

Fehler werden als Antwort zurückgegeben (nicht als Exception), damit das
Protokoll der Fehlversuche nicht mit der Transaktion zurückgerollt wird.
"""
from io import BytesIO

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, password_validation, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django_otp import login as otp_login
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import SystemEreignis, protokolliere
from epm.api_basis import sichtbare_benutzer, wahr

from .models import Anmelderegeln, Rolle, Sitzung, User
from .sitzungen import aktive_sitzungen, alle_sitzungen_beenden, schluessel_erneuert, sitzung_beenden
from .permissions import Angemeldet, BenutzerRecht, ist_verifiziert, voll_angemeldet, zweiter_faktor_erfuellt
from .rechte import schreibt_nur_testpatienten
from . import passkey as passkeys
from .models import Passkey
from .zweifaktor import (
    faktoren_loeschen, fehlertext as faktor_fehlertext, hat_authenticator, hat_passkey, hat_zweiten_faktor,
    passkey_gesendet, pflicht as zweiter_faktor_pflicht, zweiter_faktor_bestaetigt,
)

ANZAHL_NOTFALLCODES = 10
# S08: Hinweis auf der Startseite, sobald nur noch so viele Notfall-Codes übrig sind (abgeleitet: bei 3 von 10 bleibt
# Zeit, neue zu erzeugen; ohne Codes ist bei Verlust des Telefons keine Anmeldung möglich)
NOTFALLCODES_WARNEN_AB = 3


def notfallcodes_stand(user) -> dict:
    return {"uebrig": StaticToken.objects.filter(device__user=user).count(), "gesamt": ANZAHL_NOTFALLCODES,
            "eingerichtet": StaticDevice.objects.filter(user=user, confirmed=True).exists(),
            "warnen_ab": NOTFALLCODES_WARNEN_AB}


# ---------------------------------------------------------------- Hilfen
def naechster_schritt(request) -> str:
    user = request.user
    if not user.is_authenticated:
        return "anmelden"
    if user.muss_kennwort_aendern:
        return "kennwort_aendern"
    if not hat_zweiten_faktor(user):
        # freiwillig (Festlegung 02.10.2026): ohne Pflicht ist die Anmeldung mit dem Kennwort fertig
        return "2fa_einrichten" if zweiter_faktor_pflicht(user) else "fertig"
    if not ist_verifiziert(user):
        return "2fa"
    return "fertig"


def fehlversuch(user, request, art):
    """Zählt einen Fehlversuch; beim fünften wird das Konto gesperrt (bis der Admin entsperrt). Gezählt wird in der
    Datenbank: mehrere Server-Prozesse zählen sonst jeder vom eigenen, veralteten Stand aus weiter."""
    User.objects.filter(pk=user.pk).update(fehlversuche=F("fehlversuche") + 1)
    user.refresh_from_db(fields=["fehlversuche"])
    if user.fehlversuche >= settings.EPM_LOGIN_MAX_FEHLVERSUCHE:
        user.sperren(f"{user.fehlversuche} Fehlversuche bei der Anmeldung")
        user.save(update_fields=User.SPERR_FELDER)
        # „5 falsche Passwörter in 4 Minuten“: Zeit seit dem ersten der gezählten Fehlversuche
        zeiten = list(
            SystemEreignis.objects.filter(
                Q(benutzer=user) | Q(benutzername=user.username),
                art__in=[SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN],
            ).order_by("-zeitpunkt").values_list("zeitpunkt", flat=True)[:user.fehlversuche]
        )
        minuten = max(1, round((timezone.now() - zeiten[-1]).total_seconds() / 60)) if zeiten else None
        protokolliere(SystemEreignis.Art.ANMELDUNG_GESPERRT, request, benutzer=user,
                      fehlversuche=user.fehlversuche, minuten=minuten, letzter_fehler=art)
        return True
    return False


def rollen_entziehen(user, von):
    """Rollen in weiteren Firmen auf „Keine Berechtigung“ (die Rolle bei der DSKM setzt ``User.save`` bei „ohne Login“
    selbst zurück)."""
    from .models import Mitgliedschaft

    for m in Mitgliedschaft.objects.filter(benutzer=user).exclude(rolle=Rolle.KEINE):
        m.rolle = Rolle.KEINE
        m._history_user = von
        m.save()


GESPERRT_TEXT = "Das Konto ist gesperrt. Bitte an die Administration wenden."


def bestaetigung_fehlgeschlagen(request, art: str):
    """Falsches Passwort oder falscher Authenticator-Code bei einer Bestätigung in der Sitzung (endgültiges Löschen):
    zählt wie ein Fehlversuch bei der Anmeldung – sonst ließe sich das Passwort dort beliebig oft probieren.
    Liefert die Antwort „gesperrt“, wenn das Konto damit gesperrt wurde, sonst None."""
    if fehlversuch(request.user, request, art):
        return Response({"fehler": GESPERRT_TEXT}, status=status.HTTP_403_FORBIDDEN)
    return None


def bestaetigung_gelungen(request):
    if request.user.fehlversuche:
        request.user.fehlversuche = 0
        request.user.save(update_fields=["fehlversuche"])


def fehler(text, code=status.HTTP_400_BAD_REQUEST, **extra):
    return Response({"fehler": text, **extra}, status=code)


def nur_admin_ueberall(request):
    """403, wenn die Person nicht in jeder Firma Admin ist – für Einstellungen, die für alle Firmen gelten."""
    from epm.firma import admin_ueberall

    if not admin_ueberall(request.user):
        return fehler("Das gilt für alle Firmen. Ändern darf es nur, wer in jeder Firma Admin ist.",
                      status.HTTP_403_FORBIDDEN)
    return None


def firmen_daten(user):
    """Firmen mit Zugang (Umschalter oben links) und die aktive (Anforderung 11.10.2026)."""
    from epm.firma import mitgliedschaften, waehle
    from stammdaten.models import Firma

    if not hasattr(user, "firma"):
        waehle(user)
    return {
        "firma": user.firma.kuerzel if user.firma else None,
        "firmen": [{"kuerzel": f.kuerzel, "name": f.name, "kurzname": f.kurzname, "rolle": r, "altdaten": f.altdaten}
                   for f, r in mitgliedschaften(user).items()],
        # alle aktiven Firmen (Auswahl, welchen Firmen eine Akte zugeordnet ist)
        "alle_firmen": [{"kuerzel": f.kuerzel, "name": f.name, "kurzname": f.kurzname}
                        for f in Firma.objects.filter(aktiv=True).order_by("reihenfolge", "id")],
    }


def ich_daten(user):
    from epm.firma import wirksame_rolle

    firmen = firmen_daten(user)
    return {
        "id": user.id,
        "benutzername": user.username,
        "anzeigename": user.anzeigename,
        "titel": user.titel,
        "vorname": user.first_name,
        "nachname": user.last_name,
        "kuerzel": user.kuerzel,
        "funktion": user.funktion,
        # Rolle in der aktiven Firma (11.10.2026); die Rollen je Firma stehen unter ``firmen``
        "rolle": wirksame_rolle(user),
        **firmen,
        "ist_test": user.ist_test,
        "darstellung": darstellung_fuer(user),
        "startseite": {**(user.startseite or {}), "karten": startseite_karten(user)},
        "aufteilung": user.aufteilung or {},
        "bereiche": user.bereiche or {},
        # zweiter Faktor: eingerichtet? Pflicht? (Bestätigungen verlangen ihn immer – ohne ihn keine Bestätigung)
        "zweiter_faktor": hat_zweiten_faktor(user),
        "zweiter_faktor_pflicht": zweiter_faktor_pflicht(user),
        # womit bestätigt werden kann (Festlegung 08.10.2026): Code aus der App und/oder Passkey
        "authenticator": hat_authenticator(user),
        "passkey": hat_passkey(user),
        "rechte": user.rechte,
        # Admins: Patientendaten nur bei Testpatienten schreiben (Oberfläche blendet Knöpfe bei echten Akten aus)
        "schreibt_nur_testpatienten": schreibt_nur_testpatienten(user),
        # Menüpunkt „Import“ nach der Übernahme ausgeblendet (Administration › System, Festlegung 03.10.2026)
        "import_ausgeblendet": _import_ausgeblendet(),
    }


def _import_ausgeblendet() -> bool:
    from stammdaten.models import Einstellungen

    return Einstellungen.aktuell().import_ausgeblendet


def organisation():
    """Name und Anschrift des aktiven Absenders – für die Anmeldeseite (öffentlich, keine Patientendaten)."""
    from stammdaten.models import Absenderangaben, Einstellungen

    from stammdaten.models import Firma

    a = Absenderangaben.alle()[Einstellungen.aktuell().absender]
    return {"name": a.name, "anschrift": " · ".join(t for t in (a.strasse, f"{a.plz} {a.ort}".strip()) if t),
            # neutrale Anmeldeseite (11.10.2026): welche Einrichtungen EPM gemeinsam nutzen
            "firmen": [{"kurzname": f.kurzname, "name": f.name}
                       for f in Firma.objects.filter(aktiv=True).order_by("reihenfolge", "id")]}


def status_antwort(request, **extra):
    daten = {"schritt": naechster_schritt(request), "organisation": organisation(),
             # Passkeys möglich? (nur über den eingerichteten Namen, nicht über eine IP-Adresse)
             "passkey": passkeys.verfuegbar(), **extra}
    if daten["schritt"] == "2fa":
        # womit sich die Person im zweiten Schritt anmelden kann
        daten["faktoren"] = {"authenticator": hat_authenticator(request.user), "passkey": hat_passkey(request.user)}
    if daten["schritt"] == "fertig":
        daten["benutzer"] = ich_daten(request.user)
    return Response(daten)


# ---------------------------------------------------------------- Anmeldung
@method_decorator(csrf_protect, name="dispatch")
class OffenerView(APIView):
    """Endpunkte der Anmeldung: brauchen keine vollständige Anmeldung, aber immer ein CSRF-Token."""

    permission_classes = [AllowAny]
    throttle_scope = "anmeldung"


class FirmaView(APIView):
    """Firma wechseln (Umschalter oben links, Anforderung 11.10.2026): ``{"firma": "rg"}``. Nur Firmen, in denen die
    Person Zugang hat; die Wahl gilt für diese Sitzung. Antwort wie ``/api/auth/status/``."""

    def post(self, request):
        from epm.firma import SITZUNG, mitgliedschaften, waehle

        kuerzel = str((request.data if isinstance(request.data, dict) else {}).get("firma") or "")
        if kuerzel not in {f.kuerzel for f in mitgliedschaften(request.user)}:
            return fehler("Für diese Firma hast du keinen Zugang.", status.HTTP_403_FORBIDDEN)
        request.session[SITZUNG] = kuerzel
        waehle(request.user, kuerzel)
        return status_antwort(request)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class StatusView(OffenerView):
    throttle_classes = []  # wird oft abgefragt, ändert nichts

    def get(self, request):
        return status_antwort(request)


class AnmeldenView(OffenerView):
    def post(self, request):
        name = str(request.data.get("benutzername", "")).strip()
        kennwort = str(request.data.get("kennwort", ""))
        if not name or not kennwort:
            return fehler("Benutzername und Passwort angeben.")
        konto = User.objects.filter(username=name, nur_historisch=False).first()
        if konto is not None and konto.ist_gesperrt:
            # gleiche Antwort mit richtigem und falschem Kennwort – das Kennwort wird gar nicht geprüft, sonst ließe es
            # sich am gesperrten Konto ohne Grenze ausprobieren
            protokolliere(SystemEreignis.Art.ANMELDUNG_GESPERRT, request, benutzer=konto, versuch_trotz_sperre=True)
            return fehler(GESPERRT_TEXT, status.HTTP_403_FORBIDDEN, gesperrt=True)
        user = authenticate(request, username=name, password=kennwort)  # Fehlversuch → Signal → Protokoll
        if user is None:
            if konto is not None and konto.is_active and fehlversuch(konto, request, "kennwort"):
                return fehler(GESPERRT_TEXT, status.HTTP_403_FORBIDDEN, gesperrt=True)
            return fehler("Benutzername oder Passwort falsch.", status.HTTP_401_UNAUTHORIZED)
        if user.einmal_kennwort_abgelaufen:
            protokolliere(SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, request, benutzer=user, grund="einmal_kennwort_abgelaufen")
            return fehler("Das Einmal-Passwort ist abgelaufen. Bitte bei der Administration ein neues anfordern.",
                          status.HTTP_401_UNAUTHORIZED, abgelaufen=True)
        login(request, user)  # Sitzungs-ID wird erneuert
        if naechster_schritt(request) == "fertig" and user.fehlversuche:
            # ohne zweiten Faktor ist die Anmeldung hier abgeschlossen (sonst setzt der Code die Fehlversuche zurück)
            user.fehlversuche = 0
            user.save(update_fields=["fehlversuche"])
        return status_antwort(request)


class ZweiterFaktorView(OffenerView):
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return fehler("Bitte zuerst mit Passwort anmelden.", status.HTTP_401_UNAUTHORIZED)
        code = str(request.data.get("code", "")).replace(" ", "")
        for geraet in [*TOTPDevice.objects.filter(user=user, confirmed=True),
                       *StaticDevice.objects.filter(user=user, confirmed=True)]:
            if geraet.verify_token(code):
                otp_login(request, geraet)
                if user.fehlversuche:
                    user.fehlversuche = 0
                    user.save(update_fields=["fehlversuche"])
                if isinstance(geraet, StaticDevice):
                    protokolliere(SystemEreignis.Art.ANMELDUNG, request, schritt="notfallcode",
                                  verbleibend=geraet.token_set.count())
                else:
                    protokolliere(SystemEreignis.Art.ANMELDUNG, request, schritt="2fa")
                return status_antwort(request)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN, request, versuch=user.fehlversuche + 1)
        if fehlversuch(user, request, "2fa"):
            logout(request)
            return fehler(GESPERRT_TEXT, status.HTTP_403_FORBIDDEN, gesperrt=True)
        return fehler("Code ungültig.", status.HTTP_401_UNAUTHORIZED)


class KennwortView(OffenerView):
    """Eigenes Passwort setzen: beim ersten Login ohne altes Passwort, sonst mit."""

    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return fehler("Nicht angemeldet.", status.HTTP_401_UNAUTHORIZED)
        erstanmeldung = user.muss_kennwort_aendern
        if not erstanmeldung:
            if not zweiter_faktor_erfuellt(user):
                return fehler("Anmeldung mit zweitem Faktor erforderlich.", status.HTTP_403_FORBIDDEN)
            if not user.check_password(str(request.data.get("alt", ""))):
                # zählt wie ein Fehlversuch bei der Anmeldung (Sicherheitsprüfung 11.10.2026): sonst ließe sich das
                # Passwort mit einer übernommenen Sitzung hier beliebig oft probieren
                protokolliere(SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, request, grund="bestaetigung",
                              was="Passwort ändern")
                return bestaetigung_fehlgeschlagen(request, "kennwort_aendern") or fehler("Bisheriges Passwort ist falsch.")
        neu = str(request.data.get("neu", ""))
        if user.check_password(neu):
            return fehler("Das neue Passwort muss sich vom bisherigen unterscheiden.")
        try:
            password_validation.validate_password(neu, user)
        except DjangoValidationError as e:
            return fehler("Passwort zu schwach.", details=e.messages)
        user.set_password(neu)
        user.muss_kennwort_aendern = False
        user.einmal_kennwort_gueltig_bis = None
        user.kennwort_geaendert_am = timezone.now()
        user.save(update_fields=["password", "muss_kennwort_aendern", "einmal_kennwort_gueltig_bis",
                                 "kennwort_geaendert_am"])
        alter_schluessel = request.session.session_key
        update_session_auth_hash(request, user)  # erneuert den Sitzungsschlüssel
        schluessel_erneuert(alter_schluessel, request.session.session_key)
        alle_sitzungen_beenden(user, ausser=request.session.session_key)
        protokolliere(SystemEreignis.Art.KENNWORT_GEAENDERT, request, erstanmeldung=erstanmeldung)
        return status_antwort(request)


def _qr_svg(daten: str) -> str:
    bild = qrcode.make(daten, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    puffer = BytesIO()
    bild.save(puffer)
    return puffer.getvalue().decode("utf-8")


class ZweiterFaktorEinrichtenView(OffenerView):
    def post(self, request):
        user = request.user
        if not user.is_authenticated or user.muss_kennwort_aendern:
            return fehler("Erst anmelden und eigenes Passwort setzen.", status.HTTP_403_FORBIDDEN)
        # Ein bestehendes Gerät darf nur ersetzt werden, wer bereits voll angemeldet ist
        if hat_zweiten_faktor(user) and not ist_verifiziert(user):
            return fehler("Authenticator ist bereits eingerichtet.", status.HTTP_403_FORBIDDEN)
        TOTPDevice.objects.filter(user=user, confirmed=False).delete()
        geraet = TOTPDevice.objects.create(user=user, name="Authenticator-App", confirmed=False)
        return Response({"otpauth_url": geraet.config_url, "qr_svg": _qr_svg(geraet.config_url)})


class ZweiterFaktorBestaetigenView(OffenerView):
    def post(self, request):
        user = request.user
        if not user.is_authenticated or user.muss_kennwort_aendern:
            return fehler("Erst anmelden und eigenes Passwort setzen.", status.HTTP_403_FORBIDDEN)
        geraet = TOTPDevice.objects.filter(user=user, confirmed=False).order_by("-id").first()
        if not geraet:
            return fehler("Bitte zuerst die Einrichtung starten.")
        if hat_zweiten_faktor(user) and not ist_verifiziert(user):
            return fehler("Authenticator ist bereits eingerichtet.", status.HTTP_403_FORBIDDEN)
        erlaubt, _ = geraet.verify_is_allowed()
        if not erlaubt:  # django-otp sperrt nach einem Fehlversuch kurz (1 s, 2 s, 4 s …)
            return fehler("Zu schnell hintereinander. Bitte ein paar Sekunden warten und den neuen Code eingeben.",
                          status.HTTP_429_TOO_MANY_REQUESTS)
        if not geraet.verify_token(str(request.data.get("code", "")).replace(" ", "")):
            protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN, request, schritt="einrichten")
            return fehler("Code ungültig. Bitte Uhrzeit des Telefons prüfen und erneut versuchen.")
        TOTPDevice.objects.filter(user=user, confirmed=True).delete()  # altes Gerät ersetzen
        geraet.confirmed = True
        geraet.save()
        otp_login(request, geraet)
        codes = neue_notfallcodes(user)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_EINGERICHTET, request)
        return status_antwort(request, notfallcodes=codes)


def neue_notfallcodes(user) -> list[str]:
    StaticDevice.objects.filter(user=user).delete()
    geraet = StaticDevice.objects.create(user=user, name="Notfall-Codes", confirmed=True)
    codes = []
    for _ in range(ANZAHL_NOTFALLCODES):
        code = StaticToken.random_token()
        StaticToken.objects.create(device=geraet, token=code)
        codes.append(code)
    return codes


class ZweiterFaktorAusschaltenView(APIView):
    """Eigenen zweiten Faktor ausschalten (nur solange er freiwillig ist): mit Passwort und einem gültigen Code oder
    Passkey. Authenticator, Passkeys und Notfall-Codes werden gelöscht; die Anmeldung braucht danach nur noch das Passwort."""

    permission_classes = [Angemeldet]

    def post(self, request):
        user = request.user
        if not hat_zweiten_faktor(user):
            return fehler("Es ist kein zweiter Faktor eingerichtet.")
        if zweiter_faktor_pflicht(user):
            return fehler("Der zweite Faktor ist für dieses Konto Pflicht und kann nicht ausgeschaltet werden.",
                          status.HTTP_403_FORBIDDEN)
        if not user.check_password(str(request.data.get("kennwort", ""))):
            protokolliere(SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, request, grund="bestaetigung",
                          was="Zweiten Faktor ausschalten")
            return bestaetigung_fehlgeschlagen(request, "2fa_aus_kennwort") or Response(
                {"kennwort": "Das Passwort stimmt nicht."}, status=status.HTTP_400_BAD_REQUEST)
        if not zweiter_faktor_bestaetigt(request):
            protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN, request, schritt="bestaetigung",
                          was="Zweiten Faktor ausschalten")
            return bestaetigung_fehlgeschlagen(request, "2fa_aus_code") or Response(
                {"code": faktor_fehlertext(request, "Der Code ist ungültig oder wurde schon verwendet.")},
                status=status.HTTP_400_BAD_REQUEST)
        bestaetigung_gelungen(request)
        faktoren_loeschen(user)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_ZURUECKGESETZT, request, objekt=user.username, selbst=True)
        return Response(ich_daten(user))


class AbmeldenView(OffenerView):
    def post(self, request):
        logout(request)
        return Response({"schritt": "anmelden"})


# ---------------------------------------------------------------- Passkeys (Festlegung 08.10.2026)
def _darf_einrichten(user) -> bool:
    """Wie beim Authenticator: angemeldet, eigenes Passwort gesetzt; wer schon einen zweiten Faktor hat, muss ihn in
    dieser Sitzung bestätigt haben."""
    return bool(user.is_authenticated and not user.muss_kennwort_aendern
                and (not hat_zweiten_faktor(user) or ist_verifiziert(user)))


class PasskeyOptionenView(OffenerView):
    """Schritt 1 für jeden Passkey-Vorgang: Optionen für ``navigator.credentials.create`` bzw. ``.get``."""

    def post(self, request):
        user = request.user
        zweck = str(request.data.get("zweck", ""))
        if not user.is_authenticated:
            return fehler("Bitte zuerst mit Passwort anmelden.", status.HTTP_401_UNAUTHORIZED)
        if zweck == "registrieren" and not _darf_einrichten(user):
            return fehler("Erst vollständig anmelden.", status.HTTP_403_FORBIDDEN)
        if zweck == "anmelden" and user.muss_kennwort_aendern:
            return fehler("Erst ein eigenes Passwort setzen.", status.HTTP_403_FORBIDDEN)
        if zweck == "bestaetigen" and not voll_angemeldet(user):
            return fehler(Angemeldet.message, status.HTTP_403_FORBIDDEN)
        try:
            return Response(passkeys.optionen(request, zweck))
        except passkeys.PasskeyFehler as e:
            return fehler(str(e))


class PasskeyAnmeldenView(OffenerView):
    """Zweiter Schritt der Anmeldung mit Passkey statt Code (wie POST /api/auth/2fa)."""

    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return fehler("Bitte zuerst mit Passwort anmelden.", status.HTTP_401_UNAUTHORIZED)
        antwort = request.data.get("antwort")
        if not isinstance(antwort, dict):
            return fehler("Antwort des Passkeys fehlt.")
        try:
            geraet = passkeys.pruefen(request, antwort, "anmelden")
        except passkeys.PasskeyFehler as e:
            return fehler(str(e))
        if geraet is not None:
            otp_login(request, geraet)
            if user.fehlversuche:
                user.fehlversuche = 0
                user.save(update_fields=["fehlversuche"])
            protokolliere(SystemEreignis.Art.ANMELDUNG, request, schritt="passkey", passkey=geraet.name)
            return status_antwort(request)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN, request, versuch=user.fehlversuche + 1,
                      passkey=True)
        if fehlversuch(user, request, "passkey"):
            logout(request)
            return fehler(GESPERRT_TEXT, status.HTTP_403_FORBIDDEN, gesperrt=True)
        return fehler("Der Passkey wurde nicht erkannt.", status.HTTP_401_UNAUTHORIZED)


class PasskeyRegistrierenView(OffenerView):
    """Passkey einrichten – bei der ersten Anmeldung (statt der Authenticator-App) oder unter Mein Konto. Ist es der
    erste zweite Faktor, gilt die Sitzung damit als bestätigt und es gibt Notfall-Codes (wie beim Authenticator)."""

    def post(self, request):
        user = request.user
        if not _darf_einrichten(user):
            return fehler("Erst vollständig anmelden.", status.HTTP_403_FORBIDDEN)
        antwort = request.data.get("antwort")
        if not isinstance(antwort, dict):
            return fehler("Antwort des Passkeys fehlt.")
        erster = not hat_zweiten_faktor(user)
        try:
            geraet = passkeys.registrieren(request, antwort, str(request.data.get("name", "")))
        except passkeys.PasskeyFehler as e:
            protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN, request, schritt="einrichten", passkey=True)
            return fehler(str(e))
        if not ist_verifiziert(user):
            otp_login(request, geraet)
        extra = {}
        if erster and not StaticDevice.objects.filter(user=user, confirmed=True).exists():
            extra["notfallcodes"] = neue_notfallcodes(user)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_EINGERICHTET, request, passkey=geraet.name)
        return status_antwort(request, passkey_neu=passkeys.daten(geraet), **extra)


class PasskeysView(APIView):
    permission_classes = [Angemeldet]

    def get(self, request):
        return Response([passkeys.daten(p) for p in Passkey.objects.filter(user=request.user, confirmed=True)])


class PasskeyView(APIView):
    """Eigenen Passkey umbenennen."""

    permission_classes = [Angemeldet]

    def patch(self, request, pk):
        geraet = Passkey.objects.filter(user=request.user, pk=pk).first()
        if geraet is None:
            return fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"name": "Bitte einen Namen angeben."}, status=status.HTTP_400_BAD_REQUEST)
        geraet.name = name[:64]
        geraet.save(update_fields=["name"])
        return Response(passkeys.daten(geraet))


class PasskeyEntfernenView(APIView):
    """Eigenen Passkey entfernen – mit Passwort und zweitem Faktor (Code oder ein Passkey, auch dieser). Der letzte
    zweite Faktor lässt sich nur entfernen, solange er freiwillig ist; dann gehen auch die Notfall-Codes."""

    permission_classes = [Angemeldet]

    def post(self, request, pk):
        user = request.user
        geraet = Passkey.objects.filter(user=user, pk=pk).first()
        if geraet is None:
            return fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        letzter = not hat_authenticator(user) and not Passkey.objects.filter(user=user, confirmed=True).exclude(pk=pk).exists()
        if letzter and zweiter_faktor_pflicht(user):
            return fehler("Der zweite Faktor ist für dieses Konto Pflicht. Bitte zuerst die Authenticator-App oder einen "
                          "weiteren Passkey einrichten.", status.HTTP_403_FORBIDDEN)
        if not user.check_password(str(request.data.get("kennwort", ""))):
            protokolliere(SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, request, grund="bestaetigung",
                          was="Passkey entfernen")
            return bestaetigung_fehlgeschlagen(request, "passkey_aus_kennwort") or Response(
                {"kennwort": "Das Passwort stimmt nicht."}, status=status.HTTP_400_BAD_REQUEST)
        if not zweiter_faktor_bestaetigt(request):
            protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN, request, schritt="bestaetigung",
                          was="Passkey entfernen", **({"passkey": True} if passkey_gesendet(request) else {}))
            return bestaetigung_fehlgeschlagen(request, "passkey_aus_code") or Response(
                {"code": faktor_fehlertext(request, "Der Code ist ungültig oder wurde schon verwendet.")},
                status=status.HTTP_400_BAD_REQUEST)
        bestaetigung_gelungen(request)
        name = geraet.name
        sitzung_damit = getattr(getattr(user, "otp_device", None), "persistent_id", None) == geraet.persistent_id
        geraet.delete()
        if letzter:
            StaticDevice.objects.filter(user=user).delete()
        elif sitzung_damit:
            # Mit diesem Passkey war die Sitzung bestätigt: Ohne Ersatz gälte sie nicht mehr als angemeldet. Den zweiten
            # Faktor hat die Person gerade eben bestätigt – die Sitzung läuft mit einem verbliebenen Gerät weiter.
            ersatz = (TOTPDevice.objects.filter(user=user, confirmed=True).first()
                      or Passkey.objects.filter(user=user, confirmed=True).first())
            if ersatz is not None:
                otp_login(request, ersatz)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_ZURUECKGESETZT, request, objekt=user.username, selbst=True,
                      passkey=name, letzter=letzter)
        return Response(ich_daten(user))


AKZENTE = ["nachtblau", "petrol", "blau", "gruen", "orange", "aubergine", "schiefer", "anthrazit", "salbei", "eigen"]
HINTERGRUENDE = ["weissgrau", "hellgrau", "grau", "kraeftig", "blaugrau", "sand", "salbei", "eigen"]
# Farbeinstellungen gelten je Firma (Wunsch 11.10.2026: Regeneration Clinic in ihren eigenen Farben); Dichte, Schrift
# und Aufbau der Akte gelten für die Person in allen Firmen. Die Farben weiterer Firmen stehen unter
# ``darstellung["firmen"][kuerzel]``, die der DSKM wie bisher oben.
FARBFELDER = ("schema", "auto_dunkel", "akzent", "akzent_eigen", "hintergrund", "hintergrund_eigen")


def darstellung_fuer(user) -> dict:
    """Darstellung in der aktiven Firma (ohne die gespeicherten Farben anderer Firmen)."""
    gespeichert = dict(user.darstellung or {})
    je_firma = gespeichert.pop("firmen", None) or {}
    firma = getattr(user, "firma", None)
    if firma is None or firma.kuerzel == "dskm":
        return gespeichert
    allgemein = {k: v for k, v in gespeichert.items() if k not in FARBFELDER}
    return {**allgemein, **(je_firma.get(firma.kuerzel) or {})}


def darstellung_speichern(user, werte: dict) -> dict:
    """Geprüfte Darstellung speichern: Farben in der aktiven Firma, alles andere für alle Firmen."""
    neu = dict(user.darstellung or {})
    firma = getattr(user, "firma", None)
    if firma is None or firma.kuerzel == "dskm":
        neu.update(werte)
        return neu
    je_firma = dict(neu.get("firmen") or {})
    je_firma[firma.kuerzel] = {k: v for k, v in werte.items() if k in FARBFELDER}
    neu.update({k: v for k, v in werte.items() if k not in FARBFELDER})
    neu["firmen"] = je_firma
    return neu
# Kacheln der Startseite (S11) in Standardreihenfolge: Standardgröße (Spalten × Zeilen im Raster) und Gruppe.
# Klinische Kacheln sind standardmäßig für alle sichtbar außer der Rolle Admin, die Kacheln der Administration
# (S12–S14) nur für die Rolle Admin. Jede Person kann jede Kachel ein- oder ausblenden; ob sie erscheint, entscheidet
# zusätzlich das Recht (Sicherung: „Sicherungen verwalten“, Server/Updates/Angemeldet/Hinweis: „Systemverwaltung“,
# Konten: „Benutzer verwalten“, Zugriffe: „Audit-Log lesen“, Testumgebung: „Testdaten zurücksetzen“).
KARTEN = {
    "termine": (2, 2, "klinik"), "wieder": (1, 2, "klinik"), "meine": (1, 1, "klinik"), "gewicht": (1, 1, "klinik"),
    "plaene": (1, 1, "klinik"), "pruefen": (1, 1, "klinik"), "aktiv": (2, 1, "klinik"),
    "sicherung": (2, 1, "admin"), "server": (1, 1, "admin"), "updates": (1, 1, "admin"), "konten": (1, 1, "admin"),
    "angemeldet": (1, 1, "admin"), "hinweis": (1, 1, "admin"), "zugriffe": (1, 1, "admin"),
    "testumgebung": (1, 1, "admin"),
}
GROESSEN = (1, 2)

# Spaltenteiler (S17): Seiten mit Teiler und Fensterstufen (hd ab 1440 px, fhd ab 1920 px, qhd ab 2560 px)
TEILER_SEITEN = ("patientenliste", "akte_uebersicht", "akte_kontakte", "plan_editor")
TEILER_STUFEN = ("hd", "fhd", "qhd")
TEILER_MIN_SPALTE = 0.15  # keine Spalte schmaler als 15 % (sonst wäre sie nicht mehr bedienbar)


# Größe der Karten je Seite (Fehlerliste 02.10.2026, Punkt 2 und 4.1): wie die Kacheln der Startseite im Raster, je
# Person. Breite in Spalten des Rasters (1–5, begrenzt auf die Spalten des Fensters), Höhe in Rasterzeilen
# (0 = automatisch nach Inhalt, sonst 1–4 feste Zeilen, der Inhalt scrollt dann in der Karte).
BEREICH_SEITEN = {
    "akte_uebersicht": ("gewicht", "therapie", "termine", "plan", "kontakte", "stamm", "aerzte", "bezug", "befunde"),
    # eigene Reiter seit 07.10.2026 (F121): Diagnosen und Therapie getrennt
    "akte_diagnosen": ("diagnosen", "diagnose", "hinweis"),
    "akte_therapie": ("therapie", "empfehlung", "bemerkung", "hinweis"),
    "akte_kontakte": ("kontakte", "hinweis", "erreichbarkeit", "termine"),
    "system": ("verlauf", "taetigkeiten", "auftraege", "server", "epm", "hinweis", "angemeldet", "texterkennung"),
}
BEREICH_BREITEN = (1, 2, 3, 4, 5)
BEREICH_HOEHEN = (0, 1, 2, 3, 4)


def pruefe_bereiche(daten) -> dict:
    """{"<seite>": {"<karte>": {"breite": 1–5, "hoehe": 0–4} | null} | null} prüfen; null setzt die Karte bzw. die
    ganze Seite auf den Standard zurück."""
    if not isinstance(daten, dict):
        raise serializers.ValidationError({"bereiche": "Erwartet wird ein Objekt."})
    ergebnis = {}
    for seite, karten in daten.items():
        if seite not in BEREICH_SEITEN:
            raise serializers.ValidationError({"bereiche": f"Unbekannte Seite „{seite}“."})
        if karten is None:
            ergebnis[seite] = None
            continue
        if not isinstance(karten, dict):
            raise serializers.ValidationError({"bereiche": "Je Seite wird ein Objekt mit den Karten erwartet."})
        ergebnis[seite] = {}
        for karte, groesse in karten.items():
            if karte not in BEREICH_SEITEN[seite]:
                raise serializers.ValidationError({"bereiche": f"Unbekannte Karte „{karte}“ auf „{seite}“."})
            if groesse is None:
                ergebnis[seite][karte] = None
                continue
            breite = groesse.get("breite") if isinstance(groesse, dict) else None
            hoehe = groesse.get("hoehe") if isinstance(groesse, dict) else None
            if (isinstance(breite, bool) or breite not in BEREICH_BREITEN
                    or isinstance(hoehe, bool) or hoehe not in BEREICH_HOEHEN):
                raise serializers.ValidationError(
                    {"bereiche": "Breite 1 bis 5 Spalten, Höhe 0 (automatisch) bis 4 Zeilen."})
            ergebnis[seite][karte] = {"breite": breite, "hoehe": hoehe}
    return ergebnis


def startseite_karten(user, gespeichert=None) -> list[dict]:
    """Alle Kacheln in Anzeigereihenfolge: gespeicherte zuerst (unbekannte fallen weg), fehlende mit ihrem Standard
    hinten angehängt – so geht nichts verloren, und neue Kacheln einer späteren Version erscheinen von selbst."""
    if gespeichert is None:
        gespeichert = (user.startseite or {}).get("karten", [])
    admin = getattr(user, "rolle", None) == Rolle.ADMIN
    ergebnis, ids = [], set()
    for k in gespeichert if isinstance(gespeichert, list) else []:
        if not isinstance(k, dict) or k.get("id") not in KARTEN or k["id"] in ids:
            continue
        breite, hoehe, _ = KARTEN[k["id"]]
        ergebnis.append({"id": k["id"], "sichtbar": bool(k.get("sichtbar", True)),
                         "breite": k["breite"] if k.get("breite") in GROESSEN else breite,
                         "hoehe": k["hoehe"] if k.get("hoehe") in GROESSEN else hoehe})
        ids.add(k["id"])
    for kid, (breite, hoehe, gruppe) in KARTEN.items():
        if kid not in ids:
            ergebnis.append({"id": kid, "sichtbar": (gruppe == "admin") == admin, "breite": breite, "hoehe": hoehe})
    return ergebnis
TINTE = "#1B1932"


def _luminanz(hexfarbe: str) -> float:
    werte = [int(hexfarbe[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [w / 12.92 if w <= 0.03928 else ((w + 0.055) / 1.055) ** 2.4 for w in werte]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _kontrast(a: str, b: str) -> float:
    x, y = _luminanz(a), _luminanz(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


class DarstellungSerializer(serializers.Serializer):
    """Darstellung je Person (Entwurf 14 · Mein Konto); unbekannte Schlüssel werden abgewiesen."""

    schema = serializers.ChoiceField(["standard", "individuell", "kontrast", "dunkel"], default="standard")
    auto_dunkel = serializers.BooleanField(default=False)
    akzent = serializers.ChoiceField(AKZENTE, default="nachtblau")
    akzent_eigen = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False, allow_blank=True)
    hintergrund = serializers.ChoiceField(HINTERGRUENDE, default="hellgrau")
    hintergrund_eigen = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False, allow_blank=True)
    dichte = serializers.ChoiceField(["grosszuegig", "normal", "kompakt", "sehrkompakt"], default="normal")
    schriftgroesse = serializers.ChoiceField(["klein", "normal", "gross", "sehrgross"], default="normal")
    schriftstaerke = serializers.ChoiceField(["normal", "kraeftig"], default="normal")
    # Aufbau der Patientenakte (Wunsch 08.10.2026): Kopfzeile mit Gruppen, Seitenleiste mit senkrechten Reitern oder
    # Karteikarte wie in einer Arztsoftware; Höhe des Kopfs in drei Stufen, Breite der Seitenleiste in Pixeln
    aktenansicht = serializers.ChoiceField(["kopfzeile", "seitenleiste", "karteikarte"], default="kopfzeile")
    aktenkopf = serializers.ChoiceField(["minimal", "kompakt", "voll"], default="voll")
    aktenleiste_breite = serializers.IntegerField(min_value=240, max_value=480, default=300)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            # „form“ (rund/eckig) gab es nur kurz am 08.10.2026 – ältere Oberflächen schicken es evtl. noch mit
            data = {k: v for k, v in data.items() if k != "form"}
            unbekannt = set(data) - set(self.fields)
            if unbekannt:
                raise serializers.ValidationError({k: "Unbekannte Einstellung." for k in unbekannt})
        return super().to_internal_value(data)

    def validate(self, attrs):
        if attrs.get("akzent") == "eigen":
            farbe = attrs.get("akzent_eigen")
            if not farbe:
                raise serializers.ValidationError({"akzent_eigen": "Bitte eine Farbe wählen."})
            if _kontrast(farbe, "#FFFFFF") < 4.5 and _kontrast(farbe, TINTE) < 4.5:
                raise serializers.ValidationError({"akzent_eigen": "Auf dieser Farbe ist weder weiße noch dunkle "
                                                   "Schrift gut lesbar. Bitte eine hellere oder dunklere wählen."})
        if attrs.get("hintergrund") == "eigen":
            farbe = attrs.get("hintergrund_eigen")
            if not farbe:
                raise serializers.ValidationError({"hintergrund_eigen": "Bitte eine Farbe wählen."})
            if _luminanz(farbe) < 0.6:
                raise serializers.ValidationError({"hintergrund_eigen": "Diese Farbe ist zu dunkel, Schrift wäre "
                                                   "schlecht lesbar. Bitte eine hellere wählen oder „Dunkel“ nehmen."})
        return attrs


class KarteSerializer(serializers.Serializer):
    id = serializers.ChoiceField(list(KARTEN))
    sichtbar = serializers.BooleanField(default=True)
    # Größe im Raster (S11): Spalten × Zeilen, je 1 oder 2
    breite = serializers.ChoiceField(GROESSEN, required=False)
    hoehe = serializers.ChoiceField(GROESSEN, required=False)


class StartseiteSerializer(serializers.Serializer):
    """Kacheln der Startseite in Anzeigereihenfolge mit Größe (Entwurf 2 · „Startseite anpassen“, S11). Eine leere
    Liste setzt auf den Standard zurück. ``notfallhinweis_bei``: Hinweis zu den Notfall-Codes bei dieser Anzahl
    ausgeblendet (S08) – er erscheint wieder, sobald weniger Codes übrig sind."""

    karten = KarteSerializer(many=True, required=False)
    notfallhinweis_bei = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    # Hinweis „Zweiter Faktor nicht eingerichtet“ ausgeblendet (solange er freiwillig ist)
    zweifaktorhinweis_aus = serializers.BooleanField(required=False)

    def validate_karten(self, karten):
        ids = [k["id"] for k in karten]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Jede Karte darf nur einmal vorkommen.")
        return karten


def pruefe_aufteilung(daten) -> dict:
    """{"<seite>@<stufe>": [Anteile] | null} prüfen (S17). Anteile sind die Positionen der Teiler von links (0–1),
    aufsteigend, jede Spalte mindestens 15 % breit; null setzt die Seite auf den Standard zurück."""
    if not isinstance(daten, dict):
        raise serializers.ValidationError({"aufteilung": "Erwartet wird ein Objekt."})
    ergebnis = {}
    for schluessel, werte in daten.items():
        seite, _, stufe = str(schluessel).partition("@")
        if seite not in TEILER_SEITEN or stufe not in TEILER_STUFEN:
            raise serializers.ValidationError({"aufteilung": f"Unbekannte Seite oder Stufe „{schluessel}“."})
        if werte is None:
            ergebnis[schluessel] = None
            continue
        if (not isinstance(werte, list) or not 1 <= len(werte) <= 2
                or not all(isinstance(w, (int, float)) and not isinstance(w, bool) for w in werte)):
            raise serializers.ValidationError({"aufteilung": "Ein oder zwei Teiler als Zahlen zwischen 0 und 1."})
        grenzen = [0.0, *werte, 1.0]
        if any(b - a < TEILER_MIN_SPALTE - 1e-9 for a, b in zip(grenzen, grenzen[1:])):
            raise serializers.ValidationError({"aufteilung": "Jede Spalte muss mindestens 15 % breit sein."})
        ergebnis[schluessel] = [round(float(w), 4) for w in werte]
    return ergebnis


class IchView(APIView):
    """Eigenes Konto: Daten lesen; Darstellung, Startseite, Spaltenteiler und Größe der Karten speichern."""

    permission_classes = [Angemeldet]

    def get(self, request):
        return Response(ich_daten(request.user))

    def patch(self, request):
        user = request.user
        felder = []
        if "darstellung" in request.data:
            s = DarstellungSerializer(data=request.data["darstellung"])
            s.is_valid(raise_exception=True)
            user.darstellung = darstellung_speichern(user, dict(s.validated_data))
            felder.append("darstellung")
        if "startseite" in request.data:
            s = StartseiteSerializer(data=request.data["startseite"])
            s.is_valid(raise_exception=True)
            neu = dict(user.startseite or {})
            if "karten" in s.validated_data:
                neu["karten"] = startseite_karten(user, [dict(k) for k in s.validated_data["karten"]])
            if "notfallhinweis_bei" in s.validated_data:
                neu["notfallhinweis_bei"] = s.validated_data["notfallhinweis_bei"]
            if "zweifaktorhinweis_aus" in s.validated_data:
                neu["zweifaktorhinweis_aus"] = s.validated_data["zweifaktorhinweis_aus"]
            user.startseite = neu
            felder.append("startseite")
        if "aufteilung" in request.data:
            neu = dict(user.aufteilung or {})
            for schluessel, werte in pruefe_aufteilung(request.data["aufteilung"]).items():
                if werte is None:
                    neu.pop(schluessel, None)
                else:
                    neu[schluessel] = werte
            user.aufteilung = neu
            felder.append("aufteilung")
        if "bereiche" in request.data:
            neu = {k: dict(v) for k, v in (user.bereiche or {}).items() if isinstance(v, dict)}
            for seite, karten in pruefe_bereiche(request.data["bereiche"]).items():
                if karten is None:
                    neu.pop(seite, None)
                    continue
                stand = neu.setdefault(seite, {})
                for karte, groesse in karten.items():
                    if groesse is None:
                        stand.pop(karte, None)
                    else:
                        stand[karte] = groesse
                if not stand:
                    neu.pop(seite, None)
            user.bereiche = neu
            felder.append("bereiche")
        if felder:
            user.save(update_fields=felder)
        return Response(ich_daten(user))


class SicherheitView(APIView):
    """„Anmeldung und Sicherheit“ in Mein Konto."""

    permission_classes = [Angemeldet]

    def get(self, request):
        user = request.user
        geraet = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        eingerichtet = (
            SystemEreignis.objects.filter(benutzer=user, art=SystemEreignis.Art.ZWEITER_FAKTOR_EINGERICHTET)
            .exclude(details__has_key="notfallcodes_neu").order_by("-zeitpunkt").values_list("zeitpunkt", flat=True).first()
        )
        return Response({
            "kennwort_geaendert_am": user.kennwort_geaendert_am,
            "authenticator_aktiv": geraet is not None,
            "authenticator_eingerichtet_am": eingerichtet,
            "notfallcodes_uebrig": StaticToken.objects.filter(device__user=user).count(),
            "notfallcodes_gesamt": ANZAHL_NOTFALLCODES,
            # freiwillig (Festlegung 02.10.2026): ohne Pflicht lässt sich der zweite Faktor ausschalten
            "zweiter_faktor_pflicht": zweiter_faktor_pflicht(user),
            # Passkeys (Festlegung 08.10.2026)
            "passkeys": [passkeys.daten(p) for p in Passkey.objects.filter(user=user, confirmed=True)],
            "passkey": passkeys.verfuegbar(),
        })


class SitzungSerializer(serializers.ModelSerializer):
    diese = serializers.SerializerMethodField()

    class Meta:
        model = Sitzung
        fields = ["id", "browser", "ip", "angemeldet_am", "zuletzt_am", "diese"]

    def get_diese(self, obj):
        return obj.sitzungsschluessel == self.context["request"].session.session_key


class SitzungenViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Eigene Anmeldungen anzeigen und einzeln beenden."""

    serializer_class = SitzungSerializer
    permission_classes = [Angemeldet]
    pagination_class = None

    def get_queryset(self):
        return aktive_sitzungen(self.request.user)

    def perform_destroy(self, instance):
        if instance.sitzungsschluessel == self.request.session.session_key:
            raise serializers.ValidationError({"fehler": "Die eigene Sitzung wird über „Abmelden“ beendet."})
        sitzung_beenden(instance)


class NotfallcodesView(APIView):
    permission_classes = [Angemeldet]

    def post(self, request):
        codes = neue_notfallcodes(request.user)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_EINGERICHTET, request, notfallcodes_neu=True)
        return Response({"notfallcodes": codes})


# ---------------------------------------------------------------- Benutzerverwaltung (Admin)
# Testbenutzer (sehen und bearbeiten nur Testpatienten) gibt es für diese Rollen; Admins schreiben ohnehin nur bei
# Testpatienten und verlören als Testbenutzer die Verwaltung
TESTBENUTZER_ROLLEN = (Rolle.BETRACHTER, Rolle.MITARBEITER, Rolle.MITARBEITER_PLUS, Rolle.MEDIZINER)


class BenutzerSerializer(serializers.ModelSerializer):
    anzeigename = serializers.CharField(read_only=True)
    zweiter_faktor = serializers.SerializerMethodField()
    zweiter_faktor_pflicht = serializers.SerializerMethodField()
    # Rolle je Firma (Anforderung 11.10.2026): {"dskm": "mediziner", "rg": "keine"}; DSKM = ``rolle``
    firmenrollen = serializers.SerializerMethodField()
    # darf die anfragende Admin-Person das Konto kontoweit verwalten (sperren, Einmal-Passwort, Kontodaten …)? Nur,
    # wer in jeder Firma mit Rolle der Person Admin ist (Festlegung 11.10.2026) – die Oberfläche sperrt sonst die Knöpfe
    verwaltbar = serializers.SerializerMethodField()

    def get_firmenrollen(self, obj):
        from epm.firma import rollen_je_firma

        return {f.kuerzel: r for f, r in rollen_je_firma(obj).items()}

    def get_verwaltbar(self, obj):
        from epm.firma import darf_konto_verwalten

        request = self.context.get("request")
        if request is None or not getattr(obj, "pk", None):
            return True
        return darf_konto_verwalten(request.user, obj)[0]

    def _firmenrollen_eingabe(self):
        werte = self.initial_data.get("firmenrollen") if isinstance(self.initial_data, dict) else None
        return werte if isinstance(werte, dict) else None

    def _firmenrollen_speichern(self, user):
        from stammdaten.models import Firma

        from .models import Mitgliedschaft

        werte = self._firmenrollen_eingabe()
        if not werte:
            return {}
        geaendert = {}
        for firma in Firma.objects.filter(kuerzel__in=list(werte)).exclude(kuerzel="dskm"):
            m, _ = Mitgliedschaft.objects.get_or_create(benutzer=user, firma=firma)
            if m.rolle != werte[firma.kuerzel]:
                geaendert[f"rolle_{firma.kuerzel}"] = [m.rolle, werte[firma.kuerzel]]
                m.rolle = werte[firma.kuerzel]
                m._history_user = self.context["request"].user if "request" in self.context else None
                m.save()
        return geaendert

    def create(self, validated_data):
        user = super().create(validated_data)
        self.firmen_geaendert = self._firmenrollen_speichern(user)
        return user

    def update(self, instance, validated_data):
        user = super().update(instance, validated_data)
        self.firmen_geaendert = self._firmenrollen_speichern(user)
        return user

    class Meta:
        model = User
        fields = [
            "id", "username", "titel", "first_name", "last_name", "kuerzel", "funktion", "email",
            "rolle", "firmenrollen", "verwaltbar", "ist_test", "is_active", "nur_historisch", "anzeigename", "zweiter_faktor",
            "zweiter_faktor_pflicht", "muss_kennwort_aendern", "einmal_kennwort_gueltig_bis", "gesperrt_am", "sperrgrund",
            "fehlversuche", "last_login", "date_joined", "ausgeblendet_am",
        ]
        read_only_fields = ["is_active", "nur_historisch", "muss_kennwort_aendern", "einmal_kennwort_gueltig_bis",
                            "gesperrt_am", "sperrgrund", "fehlversuche", "last_login", "date_joined", "ausgeblendet_am"]

    def get_zweiter_faktor(self, obj):
        return hat_zweiten_faktor(obj)

    def get_zweiter_faktor_pflicht(self, obj):
        return zweiter_faktor_pflicht(obj)

    def validate_kuerzel(self, wert):
        return wert or None

    def validate(self, attrs):
        konto = self.instance
        rolle = attrs.get("rolle", konto.rolle if konto else Rolle.BETRACHTER)
        test = attrs.get("ist_test", konto.ist_test if konto else False)
        if konto is not None and konto.nur_historisch:
            if "rolle" in attrs and attrs["rolle"] != Rolle.KEINE:
                raise serializers.ValidationError({"rolle": "Ohne Login hat das Konto keine Rechte. Bitte zuerst "
                                                            "„Login geben“."})
            if attrs.get("ist_test"):
                raise serializers.ValidationError({"ist_test": "Ohne Login gibt es keinen Testzugang."})
        elif test and rolle not in TESTBENUTZER_ROLLEN:
            raise serializers.ValidationError({"ist_test": "Testbenutzer gibt es für Betrachter, Mitarbeiter, Mitarbeiter (erweitert) und "
                                                           "Mediziner."})
        # Rollen in weiteren Firmen (11.10.2026); die DSKM-Rolle kommt als ``rolle``
        werte = self._firmenrollen_eingabe()
        if werte:
            from stammdaten.models import Firma

            if "dskm" in werte:
                attrs["rolle"] = rolle = werte["dskm"]
            bekannt = set(Firma.objects.values_list("kuerzel", flat=True))
            for k, r in werte.items():
                if k not in bekannt:
                    raise serializers.ValidationError({"firmenrollen": f"Unbekannte Firma: {k}."})
                if r not in Rolle.values:
                    raise serializers.ValidationError({"firmenrollen": f"Unbekannte Rolle: {r}."})
                if konto is not None and konto.nur_historisch and r != Rolle.KEINE:
                    raise serializers.ValidationError({"firmenrollen": "Ohne Login hat das Konto keine Rechte."})
                if test and r not in (*TESTBENUTZER_ROLLEN, Rolle.KEINE):
                    raise serializers.ValidationError({"firmenrollen": "Testbenutzer gibt es für Betrachter, Mitarbeiter, "
                                                                       "Mitarbeiter (erweitert) und Mediziner."})
        self._pruefe_firmenhoheit(attrs, werte or {})
        return attrs

    def _pruefe_firmenhoheit(self, attrs, werte):
        """Eine Rolle in einer Firma vergibt oder ändert nur, wer dort selbst Admin ist (Festlegung 11.10.2026)."""
        from epm.firma import admin_firmen, rollen_je_firma

        request = self.context.get("request")
        if request is None:
            return
        erlaubt = admin_firmen(request.user)
        bisher = {f.kuerzel: (f, r) for f, r in rollen_je_firma(self.instance).items()} if self.instance else {}
        if not bisher:
            from stammdaten.models import Firma

            bisher = {f.kuerzel: (f, Rolle.KEINE) for f in Firma.objects.filter(aktiv=True)}
        neu = {k: r for k, r in werte.items() if k != "dskm"}
        if "rolle" in attrs:
            neu["dskm"] = attrs["rolle"]
        elif self.instance is None:
            neu["dskm"] = User._meta.get_field("rolle").default
        for kuerzel, rolle in neu.items():
            firma, vorher = bisher.get(kuerzel, (None, Rolle.KEINE))
            if rolle != vorher and kuerzel not in erlaubt:
                name = firma.name if firma else kuerzel
                feld = "rolle" if kuerzel == "dskm" else "firmenrollen"
                raise serializers.ValidationError({feld: f"Die Rolle bei {name} vergibt nur ein Admin dieser Firma."})


class BenutzerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Benutzer anlegen/ändern/sperren. Löschen gibt es nicht."""

    queryset = User.objects.all()
    serializer_class = BenutzerSerializer
    permission_classes = [BenutzerRecht]
    search_fields = ["username", "first_name", "last_name", "kuerzel"]
    filterset_fields = ["rolle", "is_active", "ist_test"]

    def get_queryset(self):
        """Ausgeblendete Testbenutzer nur mit ``?ausgeblendete=1`` in der Liste (einzeln immer erreichbar, damit man sie
        wieder einblenden kann); Testbenutzer nur mit Recht „Testdaten sehen“ (Festlegung 03.10.2026)."""
        ausgeblendete = self.action != "list" or wahr(self.request.query_params.get("ausgeblendete"))
        return sichtbare_benutzer(self.request.user, User.objects.all(), ausgeblendete=ausgeblendete)

    # Felder, die das Konto als Ganzes betreffen (nicht die Rolle je Firma): ändern darf sie nur, wer in jeder Firma
    # mit Rolle der Person Admin ist (Festlegung 11.10.2026); Rollen prüft der Serializer je Firma
    KONTO_FELDER = ("username", "titel", "first_name", "last_name", "kuerzel", "funktion", "email", "ist_test")

    def _konto_fremd(self, request, user):
        """403-Antwort, wenn die Admin-Person das Konto nicht kontoweit verwalten darf, sonst None."""
        from epm.firma import darf_konto_verwalten, konto_verwalten_hinweis

        erlaubt, fehlend = darf_konto_verwalten(request.user, user)
        return None if erlaubt else fehler(konto_verwalten_hinweis(fehlend), status.HTTP_403_FORBIDDEN)

    def _ausblenden(self, request, user):
        user.sperren("Testbenutzer ausgeblendet")
        user.ausgeblendet_am = timezone.now()
        user.save(update_fields=User.SPERR_FELDER + ["ausgeblendet_am"])
        alle_sitzungen_beenden(user)
        protokolliere(SystemEreignis.Art.BENUTZER_GESPERRT, request, objekt=user.username, ausgeblendet=True)

    @action(detail=True, methods=["post"])
    def ausblenden(self, request, pk=None):
        """Testbenutzer ausblenden (Festlegung 03.10.2026): gesperrt, alle Anmeldungen beendet, aus allen Listen
        genommen – nicht gelöscht; Einträge bleiben zugeordnet. Zurück mit „einblenden“."""
        user = self.get_object()
        if not user.ist_test:
            return fehler("Ausblenden gibt es nur für Testbenutzer. Echte Konten werden gesperrt oder ohne Login gesetzt.")
        if user == request.user:
            return fehler("Das eigene Konto kann nicht ausgeblendet werden.")
        if user.ausgeblendet_am:
            return fehler("Der Testbenutzer ist bereits ausgeblendet.")
        if (antwort := self._konto_fremd(request, user)) is not None:
            return antwort
        self._ausblenden(request, user)
        return Response(self.get_serializer(user).data)

    @action(detail=False, methods=["post"], url_path="testbenutzer-ausblenden")
    def testbenutzer_ausblenden(self, request):
        """Alle Testbenutzer auf einmal ausblenden (außer dem eigenen Konto). Testbenutzer mit Rolle in einer Firma,
        in der die Admin-Person kein Admin ist, bleiben stehen (``uebersprungen``)."""
        from epm.firma import darf_konto_verwalten

        konten = list(User.objects.filter(ist_test=True, ausgeblendet_am__isnull=True, nur_historisch=False)
                      .exclude(pk=request.user.pk))
        eigene = [u for u in konten if darf_konto_verwalten(request.user, u)[0]]
        for user in eigene:
            self._ausblenden(request, user)
        return Response({"ausgeblendet": len(eigene), "uebersprungen": len(konten) - len(eigene)})

    @action(detail=True, methods=["post"])
    def einblenden(self, request, pk=None):
        """Ausgeblendeten Testbenutzer wieder einblenden und entsperren."""
        user = self.get_object()
        if not user.ausgeblendet_am:
            return fehler("Der Benutzer ist nicht ausgeblendet.")
        if (antwort := self._konto_fremd(request, user)) is not None:
            return antwort
        user.ausgeblendet_am = None
        user.entsperren()
        user.save(update_fields=User.SPERR_FELDER + ["ausgeblendet_am"])
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, request, objekt=user.username, eingeblendet=True)
        return Response(self.get_serializer(user).data)

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        if request.data.get("ohne_login") in (True, "true", "1", 1):
            # nur als Name für Einträge (z. B. frühere Mitarbeiter): ohne Kennwort, ohne Rechte
            user = User(**{**s.validated_data, "nur_historisch": True})
            user.save()
            s._firmenrollen_speichern(user)
            protokolliere(SystemEreignis.Art.BENUTZER_ANGELEGT, request, objekt=user.username, rolle=user.rolle,
                          ohne_login=True)
            return Response(self.get_serializer(user).data, status=status.HTTP_201_CREATED)
        user = User(**s.validated_data)
        kennwort = user.neues_einmal_kennwort()
        user.save()
        # Rollen in weiteren Firmen (der Serializer legt das Konto hier nicht selbst an)
        s._firmenrollen_speichern(user)
        protokolliere(SystemEreignis.Art.BENUTZER_ANGELEGT, request, objekt=user.username, rolle=user.rolle,
                      einmal_kennwort_gueltig_bis=user.einmal_kennwort_gueltig_bis.isoformat())
        daten = self.get_serializer(user).data
        daten["einmal_kennwort"] = kennwort
        return Response(daten, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get", "put"], url_path="anmeldung")
    def anmeldung(self, request):
        """Anmelderegeln: ob der zweite Faktor freiwillig ist, Pflicht für Admins oder Pflicht für alle
        (Festlegung 02.10.2026: freiwillig). ``PUT {"zweiter_faktor": "freiwillig" | "admins" | "alle"}``."""
        regeln = Anmelderegeln.aktuell()
        if request.method == "PUT":
            if (antwort := nur_admin_ueberall(request)) is not None:
                return antwort
            wert = request.data.get("zweiter_faktor")
            if wert not in Anmelderegeln.ZweiterFaktor.values:
                return Response({"zweiter_faktor": "Erlaubt: freiwillig, admins, alle."},
                                status=status.HTTP_400_BAD_REQUEST)
            if wert != regeln.zweiter_faktor:
                vorher = regeln.zweiter_faktor
                regeln.zweiter_faktor = wert
                regeln._history_user = request.user
                regeln.save()
                namen = dict(Anmelderegeln.ZweiterFaktor.choices)
                protokolliere(SystemEreignis.Art.RECHTE_GEAENDERT, request, objekt="Anmeldung",
                              zweiter_faktor=[namen[vorher], namen[wert]])
        konten = User.objects.filter(nur_historisch=False, is_active=True, ausgeblendet_am__isnull=True)
        ohne = [u for u in konten if not hat_zweiten_faktor(u)]
        return Response({
            "zweiter_faktor": regeln.zweiter_faktor,
            "auswahl": [{"wert": w, "name": n} for w, n in Anmelderegeln.ZweiterFaktor.choices],
            "geaendert_am": regeln.geaendert_am,
            # aktive Konten ohne zweiten Faktor – sie müssten ihn bei „Pflicht“ mit der nächsten Anfrage einrichten
            "ohne_zweiten_faktor": [{"id": u.id, "anzeigename": u.anzeigename, "rolle": u.rolle} for u in ohne],
        })

    @action(detail=True, methods=["post"])
    def zugangsblatt(self, request, pk=None):
        """Zugangsblatt als PDF (F55). Das Einmal-Passwort ist nur als Prüfsumme gespeichert; die Oberfläche schickt es
        mit, solange sie es anzeigt. Es wird geprüft und muss noch gültig sein."""
        from vorlagen.api import pdf_antwort
        from vorlagen.listen import zugangsblatt_pdf

        user = self.get_object()
        kennwort = str(request.data.get("kennwort", ""))
        if not user.muss_kennwort_aendern or user.einmal_kennwort_abgelaufen:
            return fehler("Für diesen Benutzer gibt es kein gültiges Einmal-Passwort. Bitte ein neues erzeugen.")
        if not kennwort or not user.check_password(kennwort):
            return fehler("Das Einmal-Passwort passt nicht zu diesem Benutzer.")
        adresse = f"https://{request.get_host()}/"
        pdf = zugangsblatt_pdf(user, kennwort, adresse)
        protokolliere(SystemEreignis.Art.EXPORT, request, objekt=user.username, was="Zugangsblatt")
        return pdf_antwort(pdf, f"Zugang-{user.username}.pdf")

    @action(detail=False, methods=["get"])
    def hinweise(self, request):
        """Gesperrte Konten für den Hinweis im Audit-Log."""
        gesperrt = sichtbare_benutzer(request.user, User.objects.filter(gesperrt_am__isnull=False, nur_historisch=False)
                                      ).order_by("-gesperrt_am")
        return Response([{"id": u.id, "benutzername": u.username, "anzeigename": u.anzeigename,
                          "gesperrt_am": u.gesperrt_am, "sperrgrund": u.sperrgrund, "fehlversuche": u.fehlversuche}
                         for u in gesperrt])

    @action(detail=False, methods=["get"])
    def konten(self, request):
        """Admin-Startseite, Kachel „Konten“ (S12): Konten, um die sich die Administration kümmern sollte – gesperrt,
        Einmal-Passwort offen oder abgelaufen, ohne zweiten Faktor, Notfall-Codes knapp. Ohne Passwörter oder Codes,
        nur Zustände und Anzahlen."""
        zeilen = []
        for u in sichtbare_benutzer(request.user, User.objects.filter(nur_historisch=False)).order_by("last_name", "first_name"):
            codes = StaticToken.objects.filter(device__user=u).count()
            probleme = []
            if u.gesperrt_am:
                probleme.append("gesperrt")
            if u.muss_kennwort_aendern and u.einmal_kennwort_gueltig_bis:
                probleme.append("einmal_kennwort_abgelaufen" if u.einmal_kennwort_abgelaufen else "einmal_kennwort")
            elif not u.gesperrt_am and u.is_active:
                # zweiter Faktor freiwillig: Er fehlt nur, wo er Pflicht ist; Notfall-Codes zählen nur mit Authenticator
                hat = hat_zweiten_faktor(u)
                if not hat and zweiter_faktor_pflicht(u):
                    probleme.append("ohne_2fa")
                elif hat and codes <= NOTFALLCODES_WARNEN_AB:
                    probleme.append("notfallcodes")
            if probleme:
                zeilen.append({"id": u.id, "benutzername": u.username, "anzeigename": u.anzeigename,
                               "rolle": u.rolle, "probleme": probleme, "gesperrt_am": u.gesperrt_am,
                               "sperrgrund": u.sperrgrund, "fehlversuche": u.fehlversuche,
                               "einmal_kennwort_gueltig_bis": u.einmal_kennwort_gueltig_bis,
                               "notfallcodes_uebrig": codes, "notfallcodes_gesamt": ANZAHL_NOTFALLCODES})
        return Response(zeilen)

    def perform_update(self, serializer):
        from .rechte import matrix

        user = serializer.instance
        neue_rolle = serializer.validated_data.get("rolle", user.rolle)
        if user == self.request.user and not matrix()[neue_rolle]["benutzer_verwalten"]:
            raise serializers.ValidationError({"rolle": "Mit dieser Rolle könntest du Benutzer nicht mehr verwalten. "
                                                        "Die eigene Rolle bitte von einer anderen Person ändern lassen."})
        if user == self.request.user and serializer.validated_data.get("ist_test") and not user.ist_test:
            raise serializers.ValidationError({"ist_test": "Das eigene Konto kann nicht zum Testbenutzer werden."})
        vorher = {f: getattr(user, f) for f in serializer.validated_data}
        # Kontodaten (nicht die Rolle je Firma) ändert nur, wer das Konto kontoweit verwalten darf; unveränderte
        # Felder stören nicht – die Oberfläche schickt das ganze Formular
        if any(f in self.KONTO_FELDER and vorher[f] != v for f, v in serializer.validated_data.items()):
            from epm.firma import darf_konto_verwalten, konto_verwalten_hinweis

            erlaubt, fehlend = darf_konto_verwalten(self.request.user, user)
            if not erlaubt:
                # PermissionError → 403 {"fehler": …} wie bei den Aktionen (epm.api_basis.exception_handler)
                raise PermissionError(konto_verwalten_hinweis(fehlend))
        user = serializer.save()
        geaendert = {f: [str(vorher[f]), str(getattr(user, f))] for f in vorher if vorher[f] != getattr(user, f)}
        geaendert.update(getattr(serializer, "firmen_geaendert", {}))
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, self.request, objekt=user.username, aenderungen=geaendert)

    @action(detail=True, methods=["post"])
    def sperren(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return fehler("Das eigene Konto kann nicht gesperrt werden.")
        if (antwort := self._konto_fremd(request, user)) is not None:
            return antwort
        user.sperren("durch die Administration")
        user.save(update_fields=User.SPERR_FELDER)
        alle_sitzungen_beenden(user)
        protokolliere(SystemEreignis.Art.BENUTZER_GESPERRT, request, objekt=user.username)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def entsperren(self, request, pk=None):
        user = self.get_object()
        if user.nur_historisch:
            return fehler("Historische Benutzer haben keinen Zugang.")
        if user.ausgeblendet_am:
            return fehler("Der Testbenutzer ist ausgeblendet. Bitte „Einblenden“ wählen.")
        if (antwort := self._konto_fremd(request, user)) is not None:
            return antwort
        vorher = user.sperrgrund
        user.entsperren()
        user.save(update_fields=User.SPERR_FELDER)
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, request, objekt=user.username, entsperrt=True,
                      sperrgrund=vorher)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"], url_path="ohne-login")
    def ohne_login(self, request, pk=None):
        """Konto auf „ohne Login“ setzen (Fehlerliste 02.10.2026): Die Person kann sich nicht mehr anmelden und hat
        keine Rechte mehr (Rolle „Keine Berechtigung“); ihre Einträge bleiben ihr zugeordnet. Passwort, Authenticator
        und Notfall-Codes werden gelöscht, alle Anmeldungen beendet. Zurück geht es mit „Login geben“."""
        user = self.get_object()
        if user == request.user:
            return fehler("Das eigene Konto kann nicht auf „ohne Login“ gesetzt werden.")
        if user.nur_historisch:
            return fehler("Das Konto ist bereits ohne Login.")
        from epm.firma import admin_firmen, mitgliedschaften

        fremd = [f.name for f in mitgliedschaften(user) if f.kuerzel not in admin_firmen(request.user)]
        if fremd:
            return fehler(f"Das Konto hat auch eine Rolle bei {', '.join(fremd)}. „Ohne Login“ setzt dort ebenfalls "
                          "alle Rechte zurück – das darf nur, wer in jeder dieser Firmen Admin ist.",
                          status.HTTP_403_FORBIDDEN)
        vorher = user.rolle
        user.nur_historisch = True
        user.gesperrt_am = None
        user.sperrgrund = ""
        user.fehlversuche = 0
        user.muss_kennwort_aendern = True
        user.einmal_kennwort_gueltig_bis = None
        user.save()
        rollen_entziehen(user, request.user)
        faktoren_loeschen(user)
        alle_sitzungen_beenden(user)
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, request, objekt=user.username, ohne_login=True,
                      rolle_vorher=vorher)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"], url_path="login-geben")
    def login_geben(self, request, pk=None):
        """Konto ohne Login wieder einbinden: ``{"rolle": "mitarbeiter"}`` → Rolle setzen und ein Einmal-Passwort
        für das Zugangsblatt erzeugen (wie beim Anlegen)."""
        user = self.get_object()
        if not user.nur_historisch:
            return fehler("Dieses Konto hat bereits einen Login.")
        rolle = request.data.get("rolle") or Rolle.MITARBEITER
        if rolle not in Rolle.values:
            return Response({"rolle": "Unbekannte Rolle."}, status=status.HTTP_400_BAD_REQUEST)
        # die Rolle gilt in der Firma, in der die Admin-Person gerade arbeitet – und nur, wenn sie dort Admin ist
        from epm.firma import admin_firmen

        from .models import Mitgliedschaft

        firma = getattr(request.user, "firma", None)
        kuerzel = firma.kuerzel if firma else "dskm"
        if kuerzel not in admin_firmen(request.user):
            return fehler("Die Rolle in dieser Firma vergibt nur ein Admin dieser Firma.", status.HTTP_403_FORBIDDEN)
        user.nur_historisch = False
        if kuerzel == "dskm":
            user.rolle = rolle
        user.entsperren()
        kennwort = user.neues_einmal_kennwort()
        user.save()
        # Rollen aus der Zeit vor „ohne Login“ (oder beim Anlegen ohne Login mitgegeben) leben nicht wieder auf
        rollen_entziehen(user, request.user)
        if kuerzel != "dskm":
            Mitgliedschaft.objects.update_or_create(benutzer=user, firma=firma, defaults={"rolle": rolle})
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, request, objekt=user.username, login_gegeben=True,
                      rolle=rolle, einmal_kennwort_gueltig_bis=user.einmal_kennwort_gueltig_bis.isoformat())
        daten = self.get_serializer(user).data
        daten["einmal_kennwort"] = kennwort
        return Response(daten)

    @action(detail=True, methods=["post"], url_path="einmal-kennwort")
    def einmal_kennwort(self, request, pk=None):
        """Passwort vergessen: neues Einmal-Passwort für das Zugangsblatt."""
        user = self.get_object()
        if user.nur_historisch:
            return fehler("Historische Benutzer haben keinen Zugang.")
        if (antwort := self._konto_fremd(request, user)) is not None:
            return antwort
        kennwort = user.neues_einmal_kennwort()
        user.save(update_fields=User.EINMAL_FELDER)
        alle_sitzungen_beenden(user)
        protokolliere(SystemEreignis.Art.EINMAL_KENNWORT, request, objekt=user.username)
        return Response({"einmal_kennwort": kennwort, "gueltig_bis": user.einmal_kennwort_gueltig_bis})

    @action(detail=True, methods=["post"], url_path="2fa-zuruecksetzen")
    def zweiten_faktor_zuruecksetzen(self, request, pk=None):
        """Telefon verloren: Authenticator, Passkeys und Notfall-Codes löschen.

        Zusätzlich gibt es ein neues Einmal-Passwort: Nur wer das Zugangsblatt vom Admin
        erhält, kann den neuen Authenticator einrichten – das bisherige Passwort allein reicht nicht.
        """
        user = self.get_object()
        if user.nur_historisch:
            return fehler("Historische Benutzer haben keinen Zugang.")
        if (antwort := self._konto_fremd(request, user)) is not None:
            return antwort
        faktoren_loeschen(user)
        kennwort = user.neues_einmal_kennwort()
        user.save(update_fields=User.EINMAL_FELDER)
        alle_sitzungen_beenden(user)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_ZURUECKGESETZT, request, objekt=user.username)
        return Response({"einmal_kennwort": kennwort, "gueltig_bis": user.einmal_kennwort_gueltig_bis})


class RechteView(APIView):
    """Rechte je Gruppe (Entwurf 17 · „Was die Rollen dürfen“), einstellbar durch die Administration.

    GET  /api/rechte/   → {"rechte": [{code, name, beschreibung}], "rollen": [{code, name}],
                           "matrix": {rolle: {recht: bool}}, "fest": [[rolle, recht]], "standard": {...}}
    PUT  /api/rechte/   {"matrix": {rolle: {recht: bool}}} → wie GET
    """

    permission_classes = [BenutzerRecht]

    def get(self, request):
        return Response(self._daten())

    def put(self, request):
        from .models import Gruppenrecht
        from .rechte import CODES, FEST, NAMEN, NUR_ROLLEN, OHNE_RECHTE, matrix

        if (antwort := nur_admin_ueberall(request)) is not None:
            return antwort
        eingabe = request.data.get("matrix")
        if not isinstance(eingabe, dict):
            return fehler("Bitte die Matrix übergeben.")
        fehlerliste = {}
        for rolle, werte in eingabe.items():
            if rolle not in Rolle.values or not isinstance(werte, dict):
                fehlerliste[rolle] = "Unbekannte Rolle."
                continue
            for code, wert in werte.items():
                if code not in NAMEN or not isinstance(wert, bool):
                    fehlerliste[f"{rolle}.{code}"] = "Unbekanntes Recht oder kein Ja/Nein."
                elif rolle in OHNE_RECHTE and wert:
                    fehlerliste[f"{rolle}.{code}"] = "Diese Rolle hat keine Rechte."
                elif (rolle, code) in FEST and not wert:
                    fehlerliste[f"{rolle}.{code}"] = "Dieses Recht ist fest und kann nicht entzogen werden."
                elif wert and code in NUR_ROLLEN and rolle not in NUR_ROLLEN[code]:
                    namen = " und ".join(dict(Rolle.choices)[r] for r in sorted(NUR_ROLLEN[code]))
                    fehlerliste[f"{rolle}.{code}"] = f"Dieses Recht ist {namen} vorbehalten."
        if fehlerliste:
            return Response(fehlerliste, status=status.HTTP_400_BAD_REQUEST)
        vorher = matrix()
        aenderungen = []
        rollennamen = dict(Rolle.choices)
        for rolle, werte in eingabe.items():
            for code in CODES:
                if code not in werte or werte[code] == vorher[rolle][code]:
                    continue
                eintrag = Gruppenrecht.objects.filter(rolle=rolle, recht=code).first() or Gruppenrecht(
                    rolle=rolle, recht=code)
                eintrag.erlaubt = werte[code]
                eintrag._history_user = request.user
                eintrag.save()
                aenderungen.append({"rolle": rollennamen[rolle], "recht": NAMEN[code], "erlaubt": werte[code]})
        if aenderungen:
            protokolliere(SystemEreignis.Art.RECHTE_GEAENDERT, request, objekt="Rechte der Gruppen",
                          aenderungen=aenderungen)
        return Response(self._daten())

    def _daten(self):
        from .rechte import (AUCH_BEI_ECHTEN_AKTEN, FEST, NUR_ROLLEN, NUR_TESTPATIENTEN_SCHREIBEN, OHNE_RECHTE,
                             PATIENTENDATEN_SCHREIBEN, RECHTE, STANDARD, matrix)

        return {
            # Rollen, die Patientendaten nur bei Testpatienten schreiben, und welche Rechte das betrifft
            # (nicht: endgültig löschen, Dokumente zuordnen, Akten abschließen – die gelten auch bei echten Akten)
            "nur_testpatienten": {"rollen": sorted(NUR_TESTPATIENTEN_SCHREIBEN),
                                  "rechte": sorted(PATIENTENDATEN_SCHREIBEN - AUCH_BEI_ECHTEN_AKTEN)},
            # Rollen ohne jedes Recht (nicht einstellbar; Konten ohne Login)
            "ohne_rechte": sorted(OHNE_RECHTE),
            "rechte": [{"code": c, "name": n, "beschreibung": b} for c, n, b in RECHTE],
            "rollen": [{"code": c, "name": n} for c, n in Rolle.choices],
            "matrix": matrix(),
            "fest": sorted([r, c] for r, c in FEST),
            # Rechte, die nur bestimmte Rollen haben können (z. B. endgültig löschen: nur Mediziner)
            "nur_rollen": {c: sorted(r) for c, r in NUR_ROLLEN.items()},
            "standard": {str(r): sorted(v) for r, v in STANDARD.items()},
        }
