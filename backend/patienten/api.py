"""API der Patientenakte."""
import hashlib
import mimetypes
import os
import tempfile
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import NurAdmin, PatientendatenRecht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import ModelClean, RichText, benutzername, patienten_fuer
from stammdaten.models import Auswahlwert

from .models import Dokument, Gewichtsmessung, Kontakt, Patient, Termin, dokument_pfad


# ================================================================= Patient
class PatientListSerializer(serializers.ModelSerializer):
    versorger_name = serializers.CharField(source="versorger.name", read_only=True, default=None)
    ansprechpartner_name = serializers.CharField(source="ansprechpartner.name", read_only=True, default=None)
    ist_abgeschlossen = serializers.BooleanField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id", "nummer", "nachname", "vorname", "geburtsdatum", "ort", "versorger", "versorger_name",
            "ansprechpartner", "ansprechpartner_name", "ist_abgeschlossen", "abschluss_anlass", "ist_test",
        ]


class PatientSerializer(ModelClean, serializers.ModelSerializer):
    diagnose = RichText()
    therapie = RichText()
    empfehlung = RichText()
    bemerkung = RichText()
    ist_abgeschlossen = serializers.BooleanField(read_only=True)
    kopf = serializers.SerializerMethodField()
    angelegt_von_name = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "id", "nummer", "nachname", "vorname", "geburtsdatum", "geschlecht",
            "strasse", "plz", "ort", "telefon", "telefon2", "email", "krankenkasse", "hausarzt",
            "groesse_cm", "katheter", "versorger", "ansprechpartner", "nickelallergie",
            "diagnose", "therapie", "empfehlung", "bemerkung",
            "abgeschlossen_am", "abschluss_anlass", "abschluss_notiz", "ist_abgeschlossen", "ist_test",
            "angelegt_am", "angelegt_von_name", "geaendert_am", "kopf",
        ]
        read_only_fields = ["abgeschlossen_am", "abschluss_anlass", "abschluss_notiz", "angelegt_am", "geaendert_am"]

    def get_angelegt_von_name(self, obj):
        return benutzername(obj.angelegt_von)

    def get_kopf(self, obj):
        """Kerndaten für den Patientenkopf (nur in der Einzelansicht)."""
        if self.context.get("view") and self.context["view"].action == "list":
            return None
        from infusionen.models import Infusionsplan

        letzte = obj.letzte_messung()
        plan = obj.infusionsplaene.filter(status=Infusionsplan.Status.AKTUELL).first()
        termin = obj.termine.filter(erledigt_am__isnull=True, faellig_am__gte=timezone.localdate()).first()
        return {
            "gewicht": {"kg": letzte.gewicht_kg, "am": letzte.gemessen_am} if letzte else None,
            "gewichtstrend": obj.gewichtstrend(),
            "bmi": obj.bmi,
            "katheter": obj.katheter.wert if obj.katheter_id else None,
            "versorger": obj.versorger.name if obj.versorger_id else None,
            "ansprechpartner": obj.ansprechpartner.name if obj.ansprechpartner_id else None,
            "nickelallergie": obj.nickelallergie,
            "aktueller_plan": {"id": plan.id, "gueltig_ab": plan.gueltig_ab, "kcal": plan.kcal} if plan else None,
            "naechster_termin": (
                {"id": termin.id, "art": termin.art, "titel": termin.titel, "faellig_am": termin.faellig_am,
                 "uhrzeit": termin.uhrzeit, "bei": termin.bei} if termin else None
            ),
            "zaehler": {
                "kontakte": obj.kontakte.count(),
                "gewichte": obj.gewichte.count(),
                "dokumente": obj.dokumente.filter(ausgeblendet=False).count(),
                "termine_offen": obj.termine.filter(erledigt_am__isnull=True).count(),
                "infusionsplaene": obj.infusionsplaene.count(),
            },
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        for feld, liste in (("katheter", Auswahlwert.Liste.KATHETER),):
            wert = attrs.get(feld)
            if wert is not None and wert.liste != liste:
                raise serializers.ValidationError({feld: "Ungültiger Wert für diese Liste."})
        return attrs


class PatientFilter(filters.FilterSet):
    status = filters.ChoiceFilter(
        choices=[("in_betreuung", "In Betreuung"), ("abgeschlossen", "Abgeschlossen")], method="filter_status"
    )
    test = filters.ChoiceFilter(choices=[("nur", "nur Testpatienten"), ("ohne", "ohne Testpatienten")],
                                method="filter_test")
    suche = filters.CharFilter(method="filter_suche", label="Name, Vorname, Ort oder Patientennummer")

    class Meta:
        model = Patient
        fields = ["versorger", "ansprechpartner", "katheter", "nickelallergie"]

    def filter_status(self, qs, name, wert):
        return qs.filter(abgeschlossen_am__isnull=(wert == "in_betreuung"))

    def filter_suche(self, qs, name, wert):
        for wort in wert.split():
            if wort.isdigit():
                qs = qs.filter(nummer=int(wort))
            else:
                qs = qs.filter(Q(nachname__icontains=wort) | Q(vorname__icontains=wort) | Q(ort__icontains=wort))
        return qs

    def filter_test(self, qs, name, wert):
        return qs.filter(ist_test=(wert == "nur"))


class PatientViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                     mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [PatientendatenRecht]
    filterset_class = PatientFilter
    ordering_fields = ["nachname", "nummer", "geburtsdatum", "geaendert_am"]

    def get_queryset(self):
        return patienten_fuer(self.request.user).select_related("versorger", "ansprechpartner", "katheter",
                                                                "angelegt_von")

    def get_serializer_class(self):
        return PatientListSerializer if self.action == "list" else PatientSerializer

    def perform_create(self, serializer):
        serializer.save(angelegt_von=self.request.user, ist_test=self.request.user.ist_test)

    def perform_update(self, serializer):
        serializer.instance.pruefe_bearbeitbar()
        serializer.save()

    @action(detail=False, methods=["get"])
    def doppelte(self, request):
        """Mögliche Doppelungen vor dem Anlegen: gleiches Geburtsdatum und ähnlicher Name."""
        geb = request.query_params.get("geburtsdatum")
        nach = (request.query_params.get("nachname") or "").strip()
        vor = (request.query_params.get("vorname") or "").strip()
        if not geb:
            return Response([])
        qs = self.get_queryset().filter(geburtsdatum=geb)
        name = Q()
        if nach:
            name |= Q(nachname__istartswith=nach[:3])
        if vor:
            name |= Q(vorname__istartswith=vor[:3])
        if name:
            qs = qs.filter(name)
        return Response(PatientListSerializer(qs[:10], many=True).data)

    @action(detail=True, methods=["post"])
    def abschliessen(self, request, pk=None):
        patient = self.get_object()
        patient.pruefe_bearbeitbar()
        anlass = request.data.get("anlass")
        if anlass not in Patient.Abschlussanlass.values:
            return Response({"anlass": "Bitte Anlass wählen."}, status=status.HTTP_400_BAD_REQUEST)
        patient.abgeschlossen_am = request.data.get("datum") or timezone.localdate()
        patient.abschluss_anlass = anlass
        patient.abschluss_notiz = str(request.data.get("notiz", ""))[:2000]
        patient.save()
        protokolliere(SystemEreignis.Art.AKTE_ABGESCHLOSSEN, request, objekt=patient.nummer, anlass=anlass)
        patient.refresh_from_db()
        return Response(PatientSerializer(patient, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="wieder-oeffnen", permission_classes=[NurAdmin])
    def wieder_oeffnen(self, request, pk=None):
        patient = self.get_object()
        if not patient.ist_abgeschlossen:
            return Response({"fehler": "Akte ist nicht abgeschlossen."}, status=status.HTTP_400_BAD_REQUEST)
        grund = str(request.data.get("grund", "")).strip()
        if not grund:
            return Response({"grund": "Bitte einen Grund angeben."}, status=status.HTTP_400_BAD_REQUEST)
        vorher = patient.abschluss_anlass
        patient.abgeschlossen_am = None
        patient.abschluss_anlass = ""
        patient.abschluss_notiz = ""
        patient._change_reason = f"Wieder geöffnet: {grund}"
        patient.save()
        protokolliere(SystemEreignis.Art.AKTE_GEOEFFNET, request, objekt=patient.nummer, grund=grund,
                      vorheriger_anlass=vorher)
        return Response(PatientSerializer(patient, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"])
    def verlauf(self, request, pk=None):
        """Alle Fassungen aller Einträge dieser Akte, neueste zuerst. Filter: bereich, person."""
        patient = self.get_object()
        from infusionen.models import Infusionsplan

        quellen = {
            "stammdaten": Patient.history.filter(id=patient.id),
            "gewichte": Gewichtsmessung.history.filter(patient_id=patient.id),
            "kontakte": Kontakt.history.filter(patient_id=patient.id),
            "termine": Termin.history.filter(patient_id=patient.id),
            "dokumente": Dokument.history.filter(patient_id=patient.id),
            "infusionsplaene": Infusionsplan.history.filter(patient_id=patient.id),
        }
        bereich = request.query_params.get("bereich")
        if bereich:
            quellen = {k: v for k, v in quellen.items() if k == bereich}
        person = request.query_params.get("person")
        eintraege = []
        for name, qs in quellen.items():
            qs = qs.select_related("history_user")
            if person:
                qs = qs.filter(history_user_id=person)
            for h in qs.order_by("-history_date")[:500]:
                eintraege.append((name, h))
        eintraege.sort(key=lambda e: e[1].history_date, reverse=True)
        ergebnis = []
        for name, h in eintraege[:500]:
            aenderungen = []
            vorher = h.prev_record if h.history_type == "~" else None
            if vorher is not None:
                diff = h.diff_against(vorher)
                aenderungen = [{"feld": c.field, "alt": _kurz(c.old), "neu": _kurz(c.new)} for c in diff.changes]
            ergebnis.append({
                "bereich": name,
                "objekt_id": h.id,
                "art": {"+": "angelegt", "~": "geändert", "-": "gelöscht"}[h.history_type],
                "zeitpunkt": h.history_date,
                "person": benutzername(h.history_user),
                "person_id": h.history_user_id,
                "grund": h.history_change_reason,
                "aenderungen": aenderungen,
            })
        return Response(ergebnis)


def _kurz(wert, laenge=300):
    text = "" if wert is None else str(wert)
    return text if len(text) <= laenge else text[:laenge] + " …"


# ================================================================= Einträge der Akte
class AktenEintragViewSet(viewsets.GenericViewSet):
    """Gemeinsame Regeln: nur Patienten im eigenen Bereich, Filter ?patient=ID."""

    permission_classes = [PatientendatenRecht]
    filterset_fields = ["patient"]

    def get_queryset(self):
        return self.model.objects.filter(patient__in=patienten_fuer(self.request.user)).select_related("patient")

    def pruefe_patient(self, patient):
        if not patienten_fuer(self.request.user).filter(pk=patient.pk).exists():
            raise serializers.ValidationError({"patient": "Patient nicht gefunden."})
        patient.pruefe_bearbeitbar()


class GewichtSerializer(ModelClean, serializers.ModelSerializer):
    erfasst_von_name = serializers.SerializerMethodField()

    class Meta:
        model = Gewichtsmessung
        fields = ["id", "patient", "gewicht_kg", "gemessen_am", "datum_ungenau", "quelle", "notiz",
                  "erfasst_am", "erfasst_von_name"]
        read_only_fields = ["erfasst_am"]

    def get_erfasst_von_name(self, obj):
        return benutzername(obj.erfasst_von)

    def validate_patient(self, patient):
        if self.instance and patient != self.instance.patient:
            raise serializers.ValidationError("Der Patient kann nicht geändert werden.")
        return patient


class GewichtViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     mixins.CreateModelMixin, mixins.UpdateModelMixin):
    model = Gewichtsmessung
    serializer_class = GewichtSerializer
    ordering_fields = ["gemessen_am"]

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(erfasst_von=self.request.user)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        serializer.save()


class KontaktSerializer(serializers.ModelSerializer):
    text = RichText(required=True, allow_blank=False)
    erfasst_von_name = serializers.SerializerMethodField()
    storniert_von_name = serializers.SerializerMethodField()
    art_name = serializers.CharField(source="art.wert", read_only=True, default=None)

    class Meta:
        model = Kontakt
        fields = ["id", "patient", "zeitpunkt", "art", "art_name", "text", "erfasst_am", "erfasst_von_name",
                  "storniert_am", "storniert_von_name", "storno_grund"]
        read_only_fields = ["erfasst_am", "storniert_am", "storno_grund"]

    def get_erfasst_von_name(self, obj):
        return benutzername(obj.erfasst_von)

    def get_storniert_von_name(self, obj):
        return benutzername(obj.storniert_von)

    def validate_art(self, art):
        if art is not None and art.liste != Auswahlwert.Liste.KONTAKTART:
            raise serializers.ValidationError("Ungültige Kontaktart.")
        return art

    def validate_zeitpunkt(self, wert):
        if wert > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError("Zeitpunkt liegt in der Zukunft.")
        return wert


class KontaktViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     mixins.CreateModelMixin):
    """Kontakte: anlegen und lesen. Ändern/Löschen gibt es nicht, nur Storno."""

    model = Kontakt
    serializer_class = KontaktSerializer
    search_fields = ["text"]

    def get_queryset(self):
        return super().get_queryset().select_related("erfasst_von", "storniert_von", "art")

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(erfasst_von=self.request.user)

    @action(detail=True, methods=["post"])
    def storno(self, request, pk=None):
        kontakt = self.get_object()
        self.pruefe_patient(kontakt.patient)
        kontakt.stornieren(request.user, str(request.data.get("grund", "")))
        return Response(self.get_serializer(kontakt).data)


class TerminSerializer(serializers.ModelSerializer):
    erledigt_von_name = serializers.SerializerMethodField()
    angelegt_von_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = Termin
        fields = ["id", "patient", "patient_name", "art", "faellig_am", "uhrzeit", "bei", "titel", "notiz",
                  "kontakt", "erledigt_am", "erledigt_von_name", "angelegt_am", "angelegt_von_name"]
        read_only_fields = ["erledigt_am", "angelegt_am"]

    def get_erledigt_von_name(self, obj):
        return benutzername(obj.erledigt_von)

    def get_angelegt_von_name(self, obj):
        return benutzername(obj.angelegt_von)

    def get_patient_name(self, obj):
        return f"{obj.patient.nachname}, {obj.patient.vorname}"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        patient = attrs.get("patient") or (self.instance and self.instance.patient)
        kontakt = attrs.get("kontakt")
        if kontakt and kontakt.patient_id != patient.id:
            raise serializers.ValidationError({"kontakt": "Kontakt gehört zu einem anderen Patienten."})
        if self.instance and "patient" in attrs and attrs["patient"] != self.instance.patient:
            raise serializers.ValidationError({"patient": "Der Patient kann nicht geändert werden."})
        return attrs


class TerminFilter(filters.FilterSet):
    von = filters.DateFilter(field_name="faellig_am", lookup_expr="gte")
    bis = filters.DateFilter(field_name="faellig_am", lookup_expr="lte")
    offen = filters.BooleanFilter(field_name="erledigt_am", lookup_expr="isnull")

    class Meta:
        model = Termin
        fields = ["patient", "art"]


class TerminViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    mixins.CreateModelMixin, mixins.UpdateModelMixin):
    model = Termin
    serializer_class = TerminSerializer
    filterset_class = TerminFilter
    filterset_fields = None
    ordering_fields = ["faellig_am"]

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(angelegt_von=self.request.user)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        if serializer.instance.erledigt_am:
            raise serializers.ValidationError({"fehler": "Erledigte Termine können nicht geändert werden."})
        serializer.save()

    @action(detail=True, methods=["post"])
    def erledigt(self, request, pk=None):
        termin = self.get_object()
        self.pruefe_patient(termin.patient)
        if termin.erledigt_am:
            return Response({"fehler": "Termin ist bereits erledigt."}, status=status.HTTP_400_BAD_REQUEST)
        termin.erledigen(request.user)
        return Response(self.get_serializer(termin).data)


class DokumentSerializer(serializers.ModelSerializer):
    hochgeladen_von_name = serializers.SerializerMethodField()
    typ_name = serializers.CharField(source="typ.wert", read_only=True, default=None)
    datei = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Dokument
        fields = ["id", "patient", "typ", "typ_name", "titel", "datum", "notiz", "ausgeblendet", "datei",
                  "originalname", "mime", "groesse", "sha256", "herkunft", "hochgeladen_am", "hochgeladen_von_name"]
        read_only_fields = ["originalname", "mime", "groesse", "sha256", "herkunft", "hochgeladen_am"]

    def get_hochgeladen_von_name(self, obj):
        return benutzername(obj.hochgeladen_von)

    def validate_typ(self, typ):
        if typ is not None and typ.liste != Auswahlwert.Liste.DOKUMENTTYP:
            raise serializers.ValidationError("Ungültiger Dokumenttyp.")
        return typ

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get("datei"):
            raise serializers.ValidationError({"datei": "Bitte eine Datei auswählen."})
        if self.instance is not None and ("datei" in attrs or "patient" in attrs and attrs["patient"] != self.instance.patient):
            raise serializers.ValidationError({"fehler": "Datei und Patient können nicht geändert werden."})
        datei = attrs.get("datei")
        if datei and datei.size > settings.EPM_UPLOAD_MAX_MB * 1024 * 1024:
            raise serializers.ValidationError({"datei": f"Datei größer als {settings.EPM_UPLOAD_MAX_MB} MB."})
        return attrs


def speichere_datei(patient, upload) -> dict:
    """Schreibt die Datei atomar ins Dokumentenverzeichnis und berechnet SHA-256."""
    relativ = dokument_pfad(patient, upload.name)
    ziel = settings.EPM_DOKUMENTE / relativ
    ziel.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    h = hashlib.sha256()
    groesse = 0
    fd, tmp = tempfile.mkstemp(dir=ziel.parent, prefix=".upload-")
    try:
        with os.fdopen(fd, "wb") as f:
            for teil in upload.chunks():
                h.update(teil)
                groesse += len(teil)
                f.write(teil)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o640)
        os.replace(tmp, ziel)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    mime = upload.content_type or mimetypes.guess_type(upload.name)[0] or "application/octet-stream"
    return {"datei": relativ, "originalname": upload.name[:255], "mime": mime[:100], "groesse": groesse,
            "sha256": h.hexdigest()}


class DokumentViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, mixins.UpdateModelMixin):
    model = Dokument
    serializer_class = DokumentSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["patient", "typ", "ausgeblendet"]
    search_fields = ["titel", "originalname", "notiz"]

    def perform_create(self, serializer):
        patient = serializer.validated_data["patient"]
        self.pruefe_patient(patient)
        upload = serializer.validated_data.pop("datei")
        meta = speichere_datei(patient, upload)
        titel = serializer.validated_data.get("titel") or upload.name
        serializer.save(hochgeladen_von=self.request.user, titel=titel[:200], **meta)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        serializer.save()

    @action(detail=True, methods=["get"])
    def datei(self, request, pk=None):
        """Download: in Produktion liefert Nginx die Datei (X-Accel-Redirect), Django prüft nur das Recht."""
        dok = self.get_object()
        inline = request.query_params.get("anzeigen") == "1"
        art = "inline" if inline else "attachment"
        name = dok.originalname.replace('"', "")
        from urllib.parse import quote
        dispo = f"{art}; filename*=UTF-8''{quote(name)}"
        if settings.EPM_X_ACCEL:
            antwort = HttpResponse(content_type=dok.mime)
            antwort["X-Accel-Redirect"] = settings.EPM_X_ACCEL_PREFIX + dok.datei
        else:
            antwort = FileResponse(open(dok.pfad, "rb"), content_type=dok.mime)
        antwort["Content-Disposition"] = dispo
        antwort["Cache-Control"] = "private, no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        return antwort


# ================================================================= Startseite
def startseite_daten(user):
    from infusionen.models import Infusionsplan
    from stammdaten.models import Einstellungen

    heute = timezone.localdate()
    e = Einstellungen.aktuell()
    patienten = patienten_fuer(user).filter(abgeschlossen_am__isnull=True)
    termine = Termin.objects.filter(patient__in=patienten, erledigt_am__isnull=True).select_related("patient")

    def t(qs):
        return TerminSerializer(qs[:50], many=True).data

    warnungen = []
    for p in patienten.filter(gewichte__gemessen_am__gte=heute - timedelta(days=30 * e.gewicht_warnung_monate)).distinct():
        trend = p.gewichtstrend()
        if trend and trend["warnung"]:
            warnungen.append({"patient": p.id, "name": f"{p.nachname}, {p.vorname}", "nummer": p.nummer, **trend})

    grenze = heute - timedelta(days=30 * e.plan_alter_warnung_monate)
    plaene = Infusionsplan.objects.filter(patient__in=patienten).select_related("patient")

    def pl(qs):
        return [{"id": x.id, "patient": x.patient_id, "name": f"{x.patient.nachname}, {x.patient.vorname}",
                 "gueltig_ab": x.gueltig_ab, "status": x.status} for x in qs[:50]]

    zuletzt = (
        Kontakt.objects.filter(patient__in=patienten).select_related("patient", "erfasst_von").order_by("-erfasst_am")[:10]
    )
    return {
        "termine": {
            "ueberfaellig": t(termine.filter(faellig_am__lt=heute)),
            "heute": t(termine.filter(faellig_am=heute)),
            "naechste_7_tage": t(termine.filter(faellig_am__gt=heute, faellig_am__lte=heute + timedelta(days=7))),
        },
        "gewichtswarnungen": warnungen,
        "infusionsplaene": {
            "entwuerfe": pl(plaene.filter(status=Infusionsplan.Status.ENTWURF)),
            "aelter_als_grenze": pl(plaene.filter(status=Infusionsplan.Status.AKTUELL, gueltig_ab__lt=grenze)),
        },
        "zuletzt_eingetragen": [
            {"patient": k.patient_id, "name": f"{k.patient.nachname}, {k.patient.vorname}",
             "zeitpunkt": k.erfasst_am, "person": benutzername(k.erfasst_von), "text": _kurz(k.text, 160)}
            for k in zuletzt
        ],
        "zahlen": {
            "in_betreuung": patienten.filter(ist_test=False).count(),
            "mit_offenem_termin": patienten.filter(termine__erledigt_am__isnull=True).distinct().count(),
        },
    }


class StartseiteViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response(startseite_daten(request.user))
