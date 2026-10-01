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
from django.db.models import Q
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

from .models import Rolle, Sitzung, User
from .sitzungen import aktive_sitzungen, alle_sitzungen_beenden, schluessel_erneuert, sitzung_beenden
from .permissions import Angemeldet, BenutzerRecht, ist_verifiziert

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


def fehlversuch(user, request, art):
    """Zählt einen Fehlversuch; beim fünften wird das Konto gesperrt (bis der Admin entsperrt)."""
    user.fehlversuche += 1
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
    user.save(update_fields=["fehlversuche"])
    return False


GESPERRT_TEXT = "Das Konto ist gesperrt. Bitte an die Administration wenden."


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
        "rechte": user.rechte,
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
        konto = User.objects.filter(username=name, nur_historisch=False).first()
        if konto is not None and konto.ist_gesperrt:
            # Sperre nur verraten, wenn das Kennwort stimmt (sonst wie ein normaler Fehlversuch)
            if konto.check_password(kennwort):
                protokolliere(SystemEreignis.Art.ANMELDUNG_GESPERRT, request, benutzer=konto, versuch_trotz_sperre=True)
                return fehler(GESPERRT_TEXT, status.HTTP_403_FORBIDDEN, gesperrt=True)
            protokolliere(SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, request, benutzername=name)
            return fehler("Benutzername oder Kennwort falsch.", status.HTTP_401_UNAUTHORIZED)
        user = authenticate(request, username=name, password=kennwort)  # Fehlversuch → Signal → Protokoll
        if user is None:
            if konto is not None and konto.is_active and fehlversuch(konto, request, "kennwort"):
                return fehler(GESPERRT_TEXT, status.HTTP_403_FORBIDDEN, gesperrt=True)
            return fehler("Benutzername oder Kennwort falsch.", status.HTTP_401_UNAUTHORIZED)
        if user.einmal_kennwort_abgelaufen:
            protokolliere(SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, request, benutzer=user, grund="einmal_kennwort_abgelaufen")
            return fehler("Das Einmal-Kennwort ist abgelaufen. Bitte bei der Administration ein neues anfordern.",
                          status.HTTP_401_UNAUTHORIZED, abgelaufen=True)
        login(request, user)  # Sitzungs-ID wird erneuert
        return status_antwort(request)


class ZweiterFaktorView(OffenerView):
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return fehler("Bitte zuerst mit Kennwort anmelden.", status.HTTP_401_UNAUTHORIZED)
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


AKZENTE = ["nachtblau", "petrol", "blau", "gruen", "orange", "aubergine", "schiefer", "eigen"]
HINTERGRUENDE = ["weissgrau", "hellgrau", "grau", "kraeftig", "blaugrau", "sand", "eigen"]
KARTEN = ["termine", "gewicht", "plaene", "pruefen", "aktiv"]
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

    def to_internal_value(self, data):
        if isinstance(data, dict):
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
    id = serializers.ChoiceField(KARTEN)
    sichtbar = serializers.BooleanField(default=True)


class StartseiteSerializer(serializers.Serializer):
    """Karten der Startseite in Anzeigereihenfolge (Entwurf 2 · „Startseite anpassen“)."""

    karten = KarteSerializer(many=True)

    def validate_karten(self, karten):
        ids = [k["id"] for k in karten]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Jede Karte darf nur einmal vorkommen.")
        # fehlende Karten hinten sichtbar anhängen, damit nichts verloren geht
        return karten + [{"id": k, "sichtbar": True} for k in KARTEN if k not in ids]


class IchView(APIView):
    """Eigenes Konto: Daten lesen, Darstellung und Startseite speichern."""

    permission_classes = [Angemeldet]

    def get(self, request):
        return Response(ich_daten(request.user))

    def patch(self, request):
        user = request.user
        felder = []
        if "darstellung" in request.data:
            s = DarstellungSerializer(data=request.data["darstellung"])
            s.is_valid(raise_exception=True)
            user.darstellung = dict(s.validated_data)
            felder.append("darstellung")
        if "startseite" in request.data:
            s = StartseiteSerializer(data=request.data["startseite"])
            s.is_valid(raise_exception=True)
            user.startseite = {"karten": [dict(k) for k in s.validated_data["karten"]]}
            felder.append("startseite")
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
class BenutzerSerializer(serializers.ModelSerializer):
    anzeigename = serializers.CharField(read_only=True)
    zweiter_faktor = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "titel", "first_name", "last_name", "kuerzel", "funktion", "email",
            "rolle", "ist_test", "is_active", "nur_historisch", "anzeigename", "zweiter_faktor",
            "muss_kennwort_aendern", "einmal_kennwort_gueltig_bis", "gesperrt_am", "sperrgrund",
            "fehlversuche", "last_login", "date_joined",
        ]
        read_only_fields = ["is_active", "nur_historisch", "muss_kennwort_aendern", "einmal_kennwort_gueltig_bis",
                            "gesperrt_am", "sperrgrund", "fehlversuche", "last_login", "date_joined"]

    def get_zweiter_faktor(self, obj):
        return hat_zweiten_faktor(obj)

    def validate_kuerzel(self, wert):
        return wert or None


class BenutzerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Benutzer anlegen/ändern/sperren. Löschen gibt es nicht."""

    queryset = User.objects.all()
    serializer_class = BenutzerSerializer
    permission_classes = [BenutzerRecht]
    search_fields = ["username", "first_name", "last_name", "kuerzel"]
    filterset_fields = ["rolle", "is_active", "ist_test"]

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = User(**s.validated_data)
        kennwort = user.neues_einmal_kennwort()
        user.save()
        protokolliere(SystemEreignis.Art.BENUTZER_ANGELEGT, request, objekt=user.username, rolle=user.rolle,
                      einmal_kennwort_gueltig_bis=user.einmal_kennwort_gueltig_bis.isoformat())
        daten = self.get_serializer(user).data
        daten["einmal_kennwort"] = kennwort
        return Response(daten, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def hinweise(self, request):
        """Gesperrte Konten für den Hinweis im Audit-Log."""
        gesperrt = User.objects.filter(gesperrt_am__isnull=False, nur_historisch=False).order_by("-gesperrt_am")
        return Response([{"id": u.id, "benutzername": u.username, "anzeigename": u.anzeigename,
                          "gesperrt_am": u.gesperrt_am, "sperrgrund": u.sperrgrund, "fehlversuche": u.fehlversuche}
                         for u in gesperrt])

    def perform_update(self, serializer):
        from .rechte import matrix

        user = serializer.instance
        neue_rolle = serializer.validated_data.get("rolle", user.rolle)
        if user == self.request.user and not matrix()[neue_rolle]["benutzer_verwalten"]:
            raise serializers.ValidationError({"rolle": "Mit dieser Rolle könntest du Benutzer nicht mehr verwalten. "
                                                        "Die eigene Rolle bitte von einer anderen Person ändern lassen."})
        vorher = {f: getattr(user, f) for f in serializer.validated_data}
        user = serializer.save()
        geaendert = {f: [str(vorher[f]), str(getattr(user, f))] for f in vorher if vorher[f] != getattr(user, f)}
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, self.request, objekt=user.username, aenderungen=geaendert)

    @action(detail=True, methods=["post"])
    def sperren(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return fehler("Das eigene Konto kann nicht gesperrt werden.")
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
        vorher = user.sperrgrund
        user.entsperren()
        user.save(update_fields=User.SPERR_FELDER)
        protokolliere(SystemEreignis.Art.BENUTZER_GEAENDERT, request, objekt=user.username, entsperrt=True,
                      sperrgrund=vorher)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"], url_path="einmal-kennwort")
    def einmal_kennwort(self, request, pk=None):
        """Kennwort vergessen: neues Einmal-Kennwort für das Zugangsblatt."""
        user = self.get_object()
        if user.nur_historisch:
            return fehler("Historische Benutzer haben keinen Zugang.")
        kennwort = user.neues_einmal_kennwort()
        user.save(update_fields=User.EINMAL_FELDER)
        alle_sitzungen_beenden(user)
        protokolliere(SystemEreignis.Art.EINMAL_KENNWORT, request, objekt=user.username)
        return Response({"einmal_kennwort": kennwort, "gueltig_bis": user.einmal_kennwort_gueltig_bis})

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
        from .rechte import CODES, FEST, NAMEN, matrix

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
                elif (rolle, code) in FEST and not wert:
                    fehlerliste[f"{rolle}.{code}"] = "Dieses Recht ist fest und kann nicht entzogen werden."
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
        from .rechte import FEST, RECHTE, STANDARD, matrix

        return {
            "rechte": [{"code": c, "name": n, "beschreibung": b} for c, n, b in RECHTE],
            "rollen": [{"code": c, "name": n} for c, n in Rolle.choices],
            "matrix": matrix(),
            "fest": sorted([r, c] for r, c in FEST),
            "standard": {str(r): sorted(v) for r, v in STANDARD.items()},
        }
