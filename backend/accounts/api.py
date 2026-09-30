"""
Anmeldung (Kennwort → ggf. eigenes Kennwort → Authenticator-App → Code) und Benutzerverwaltung.

Ablauf beim ersten Login:
  1. POST /api/auth/anmelden          Benutzername + Einmal-Kennwort
  2. POST /api/auth/kennwort          eigenes Kennwort wählen
  3. POST /api/auth/2fa/einrichten    QR-Code für die Authenticator-App
  4. POST /api/auth/2fa/bestaetigen   ersten Code eingeben → Notfall-Codes (einmalig angezeigt)
Danach bei jeder Anmeldung: 1. und POST /api/auth/2fa mit dem aktuellen Code.

Fehler werden als Antwort zurückgegeben (nicht als Exception), damit das
Protokoll der Fehlversuche nicht mit der Transaktion zurückgerollt wird.
"""
from io import BytesIO

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, password_validation, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
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

from .models import Rolle, User
from .permissions import Angemeldet, NurAdmin, ist_verifiziert

ANZAHL_NOTFALLCODES = 10


# ---------------------------------------------------------------- Hilfen
def hat_zweiten_faktor(user) -> bool:
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def naechster_schritt(request) -> str:
    user = request.user
    if not user.is_authenticated:
        return "anmelden"
    if user.muss_kennwort_aendern:
        return "kennwort_aendern"
    if not hat_zweiten_faktor(user):
        return "2fa_einrichten"
    if not ist_verifiziert(user):
        return "2fa"
    return "fertig"


def zu_viele_fehlversuche(benutzername: str) -> bool:
    seit = timezone.now() - settings.EPM_LOGIN_SPERRE
    letzte_erfolgreiche = (
        SystemEreignis.objects.filter(benutzername__iexact=benutzername, art=SystemEreignis.Art.ANMELDUNG)
        .order_by("-zeitpunkt").values_list("zeitpunkt", flat=True).first()
    )
    if letzte_erfolgreiche and letzte_erfolgreiche > seit:
        seit = letzte_erfolgreiche
    fehler = SystemEreignis.objects.filter(
        benutzername__iexact=benutzername,
        zeitpunkt__gt=seit,
        art__in=[SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN],
    ).count()
    return fehler >= settings.EPM_LOGIN_MAX_FEHLVERSUCHE


def fehler(text, code=status.HTTP_400_BAD_REQUEST, **extra):
    return Response({"fehler": text, **extra}, status=code)


def ich_daten(user):
    return {
        "id": user.id,
        "benutzername": user.username,
        "anzeigename": user.anzeigename,
        "titel": user.titel,
        "vorname": user.first_name,
        "nachname": user.last_name,
        "kuerzel": user.kuerzel,
        "funktion": user.funktion,
        "rolle": user.rolle,
        "ist_test": user.ist_test,
        "darstellung": user.darstellung,
        "startseite": user.startseite,
        "rechte": {
            "patienten_bearbeiten": user.darf_patienten_bearbeiten,
            "plaene_bearbeiten": user.darf_plaene_bearbeiten,
            "administration": user.ist_admin,
        },
    }


def status_antwort(request, **extra):
    daten = {"schritt": naechster_schritt(request), **extra}
    if daten["schritt"] == "fertig":
        daten["benutzer"] = ich_daten(request.user)
    return Response(daten)


# ---------------------------------------------------------------- Anmeldung
@method_decorator(csrf_protect, name="dispatch")
class OffenerView(APIView):
    """Endpunkte der Anmeldung: brauchen keine vollständige Anmeldung, aber immer ein CSRF-Token."""

    permission_classes = [AllowAny]
    throttle_scope = "anmeldung"


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
            return fehler("Benutzername und Kennwort angeben.")
        if zu_viele_fehlversuche(name):
            protokolliere(SystemEreignis.Art.ANMELDUNG_GESPERRT, request, benutzername=name)
            return fehler("Zu viele Fehlversuche. Bitte in 15 Minuten erneut versuchen.", status.HTTP_429_TOO_MANY_REQUESTS)
        user = authenticate(request, username=name, password=kennwort)  # Fehlversuch → Signal → Protokoll
        if user is None:
            return fehler("Benutzername oder Kennwort falsch.", status.HTTP_401_UNAUTHORIZED)
        login(request, user)  # Sitzungs-ID wird erneuert
        return status_antwort(request)


class ZweiterFaktorView(OffenerView):
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return fehler("Bitte zuerst mit Kennwort anmelden.", status.HTTP_401_UNAUTHORIZED)
        if zu_viele_fehlversuche(user.username):
            logout(request)
            return fehler("Zu viele Fehlversuche. Bitte in 15 Minuten erneut versuchen.", status.HTTP_429_TOO_MANY_REQUESTS)
        code = str(request.data.get("code", "")).replace(" ", "")
        for geraet in [*TOTPDevice.objects.filter(user=user, confirmed=True),
                       *StaticDevice.objects.filter(user=user, confirmed=True)]:
            if geraet.verify_token(code):
                otp_login(request, geraet)
                if isinstance(geraet, StaticDevice):
                    protokolliere(SystemEreignis.Art.ANMELDUNG, request, schritt="notfallcode",
                                  verbleibend=geraet.token_set.count())
                else:
                    protokolliere(SystemEreignis.Art.ANMELDUNG, request, schritt="2fa")
                return status_antwort(request)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN, request)
        return fehler("Code ungültig.", status.HTTP_401_UNAUTHORIZED)


class KennwortView(OffenerView):
    """Eigenes Kennwort setzen: beim ersten Login ohne altes Kennwort, sonst mit."""

    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return fehler("Nicht angemeldet.", status.HTTP_401_UNAUTHORIZED)
        erstanmeldung = user.muss_kennwort_aendern
        if not erstanmeldung:
            if not ist_verifiziert(user):
                return fehler("Anmeldung mit zweitem Faktor erforderlich.", status.HTTP_403_FORBIDDEN)
            if not user.check_password(str(request.data.get("alt", ""))):
                return fehler("Bisheriges Kennwort ist falsch.")
        neu = str(request.data.get("neu", ""))
        if user.check_password(neu):
            return fehler("Das neue Kennwort muss sich vom bisherigen unterscheiden.")
        try:
            password_validation.validate_password(neu, user)
        except DjangoValidationError as e:
            return fehler("Kennwort zu schwach.", details=e.messages)
        user.set_password(neu)
        user.muss_kennwort_aendern = False
        user.save(update_fields=["password", "muss_kennwort_aendern"])
        update_session_auth_hash(request, user)
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
            return fehler("Erst anmelden und eigenes Kennwort setzen.", status.HTTP_403_FORBIDDEN)
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
            return fehler("Erst anmelden und eigenes Kennwort setzen.", status.HTTP_403_FORBIDDEN)
        geraet = TOTPDevice.objects.filter(user=user, confirmed=False).order_by("-id").first()
        if not geraet:
            return fehler("Bitte zuerst die Einrichtung starten.")
        if hat_zweiten_faktor(user) and not ist_verifiziert(user):
            return fehler("Authenticator ist bereits eingerichtet.", status.HTTP_403_FORBIDDEN)
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


class AbmeldenView(OffenerView):
    def post(self, request):
        logout(request)
        return Response({"schritt": "anmelden"})


class IchView(APIView):
    """Eigenes Konto: Daten lesen, Darstellung und Startseite speichern, neue Notfall-Codes."""

    permission_classes = [Angemeldet]

    def get(self, request):
        return Response(ich_daten(request.user))

    def patch(self, request):
        user = request.user
        for feld in ("darstellung", "startseite"):
            if feld in request.data:
                if not isinstance(request.data[feld], dict):
                    return fehler(f"{feld} muss ein Objekt sein.")
                setattr(user, feld, request.data[feld])
        user.save(update_fields=["darstellung", "startseite"])
        return Response(ich_daten(user))


class NotfallcodesView(APIView):
    permission_classes = [Angemeldet]

    def post(self, request):
        codes = neue_notfallcodes(request.user)
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_EINGERICHTET, request, notfallcodes_neu=True)
        return Response({"notfallcodes": codes})


# ---------------------------------------------------------------- Benutzerverwaltung (Admin)
class BenutzerSerializer(serializers.ModelSerializer):
    anzeigename = serializers.CharField(read_only=True)
    zweiter_faktor = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "titel", "first_name", "last_name", "kuerzel", "funktion", "email",
            "rolle", "ist_test", "is_active", "nur_historisch", "anzeigename", "zweiter_faktor",
            "muss_kennwort_aendern", "last_login", "date_joined",
        ]
        read_only_fields = ["is_active", "nur_historisch", "muss_kennwort_aendern", "last_login", "date_joined"]

    def get_zweiter_faktor(self, obj):
        return hat_zweiten_faktor(obj)

    def validate_kuerzel(self, wert):
        return wert or None


class BenutzerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Benutzer anlegen/ändern/sperren. Löschen gibt es nicht."""

    queryset = User.objects.all()
    serializer_class = BenutzerSerializer
    permission_classes = [NurAdmin]
    search_fields = ["username", "first_name", "last_name", "kuerzel"]
    filterset_fields = ["rolle", "is_active", "ist_test"]

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = User(**s.validated_data)
        kennwort = user.neues_einmal_kennwort()
        user.save()
        protokolliere(SystemEreignis.Art.BENUTZER_ANGELEGT, request, objekt=user.username, rolle=user.rolle)
        daten = self.get_serializer(user).data
        daten["einmal_kennwort"] = kennwort
        return Response(daten, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        user = serializer.instance
        if user == self.request.user and serializer.validated_data.get("rolle", user.rolle) != Rolle.ADMIN:
            raise serializers.ValidationError({"rolle": "Die eigene Admin-Rolle kann nicht entzogen werden."})
        vorher = {f: getattr(user, f) for f in serializer.validated_data}
        user = serializer.save()
        geaendert = {f: [str(vorher[f]), str(getattr(user, f))] for f in vorher if vorher[f] != getattr(user, f)}
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, self.request, objekt=user.username, aenderungen=geaendert)

    @action(detail=True, methods=["post"])
    def sperren(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return fehler("Das eigene Konto kann nicht gesperrt werden.")
        user.is_active = False
        user.save(update_fields=["is_active"])
        protokolliere(SystemEreignis.Art.BENUTZER_GESPERRT, request, objekt=user.username)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def entsperren(self, request, pk=None):
        user = self.get_object()
        if user.nur_historisch:
            return fehler("Historische Benutzer haben keinen Zugang.")
        user.is_active = True
        user.save(update_fields=["is_active"])
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, request, objekt=user.username, entsperrt=True)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"], url_path="einmal-kennwort")
    def einmal_kennwort(self, request, pk=None):
        """Kennwort vergessen: neues Einmal-Kennwort für das Zugangsblatt."""
        user = self.get_object()
        if user.nur_historisch:
            return fehler("Historische Benutzer haben keinen Zugang.")
        kennwort = user.neues_einmal_kennwort()
        user.save(update_fields=["password", "muss_kennwort_aendern"])
        protokolliere(SystemEreignis.Art.EINMAL_KENNWORT, request, objekt=user.username)
        return Response({"einmal_kennwort": kennwort})

    @action(detail=True, methods=["post"], url_path="2fa-zuruecksetzen")
    def zweiten_faktor_zuruecksetzen(self, request, pk=None):
        """Telefon verloren: Authenticator und Notfall-Codes löschen.

        Zusätzlich gibt es ein neues Einmal-Kennwort: Nur wer das Zugangsblatt vom Admin
        erhält, kann den neuen Authenticator einrichten – das bisherige Kennwort allein reicht nicht.
        """
        user = self.get_object()
        if user.nur_historisch:
            return fehler("Historische Benutzer haben keinen Zugang.")
        TOTPDevice.objects.filter(user=user).delete()
        StaticDevice.objects.filter(user=user).delete()
        kennwort = user.neues_einmal_kennwort()
        user.save(update_fields=["password", "muss_kennwort_aendern"])
        protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_ZURUECKGESETZT, request, objekt=user.username)
        return Response({"einmal_kennwort": kennwort})
