"""API der Infusionspläne: Entwurf anlegen (vorbelegt), bearbeiten, freigeben, verwerfen."""
from django.db import transaction
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import PlanRecht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import ModelClean, RichText, benutzername, patienten_fuer
from stammdaten.models import Praeparat

from .models import Infusionsplan, InfusionsplanPosition


class PositionSerializer(serializers.ModelSerializer):
    praeparat_name = serializers.CharField(source="praeparat.__str__", read_only=True)
    kategorie = serializers.CharField(source="praeparat.kategorie", read_only=True)

    class Meta:
        model = InfusionsplanPosition
        fields = ["id", "praeparat", "praeparat_name", "kategorie", "menge", "einheit", "haeufigkeit",
                  "bemerkung", "reihenfolge"]
        read_only_fields = ["id"]


PRAEPARAT_FELDER = {
    "basis_praeparat": Praeparat.Kategorie.BASISLOESUNG,
    "glucose_praeparat": Praeparat.Kategorie.GLUCOSE,
    "aminosaeuren_praeparat": Praeparat.Kategorie.AMINOSAEUREN,
    "lipide_praeparat": Praeparat.Kategorie.LIPIDE,
    "albumin_praeparat": Praeparat.Kategorie.ALBUMIN,
    "spurenelemente": Praeparat.Kategorie.SPURENELEMENTE,
    "katheterschutz": Praeparat.Kategorie.KATHETERSCHUTZ,
}


class InfusionsplanSerializer(ModelClean, serializers.ModelSerializer):
    positionen = PositionSerializer(many=True, required=False)
    vitamine = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=Praeparat.objects.filter(kategorie=Praeparat.Kategorie.VITAMINE)
    )
    vitamine_namen = serializers.SerializerMethodField()
    bemerkung = RichText()
    kcal_berechnet = serializers.IntegerField(read_only=True)
    kcal = serializers.IntegerField(read_only=True)
    geaenderte_felder = serializers.SerializerMethodField()
    erstellt_von_name = serializers.SerializerMethodField()
    freigegeben_von_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = Infusionsplan
        fields = [
            "id", "patient", "patient_name", "status", "vorgaenger", "gueltig_ab",
            "basis_praeparat", "basis_ml", "glucose_praeparat", "glucose_g", "aminosaeuren_praeparat",
            "aminosaeuren_g", "lipide_praeparat", "lipide_g", "albumin_praeparat", "albumin_g",
            "natrium_mmol", "kalium_mmol", "phosphat_mmol", "calcium_mmol", "magnesium_mmol",
            "spurenelemente", "vitamine", "vitamine_namen",
            "kcal_manuell", "kcal_berechnet", "kcal", "laufzeit_h", "tage_pro_woche", "katheterschutz",
            "pantozol_stufe", "pantozol_tage", "bemerkung", "positionen", "geaenderte_felder",
            "erstellt_am", "erstellt_von_name", "freigegeben_am", "freigegeben_von_name",
            "pdf_datei", "pdf_sha256", "vorlage_version",
        ]
        read_only_fields = ["patient", "status", "vorgaenger", "erstellt_am", "freigegeben_am",
                            "pdf_datei", "pdf_sha256", "vorlage_version"]

    def get_vitamine_namen(self, obj):
        return [str(p) for p in obj.vitamine.all()]

    def get_geaenderte_felder(self, obj):
        return obj.geaenderte_felder()

    def get_erstellt_von_name(self, obj):
        return benutzername(obj.erstellt_von)

    def get_freigegeben_von_name(self, obj):
        return benutzername(obj.freigegeben_von)

    def get_patient_name(self, obj):
        return f"{obj.patient.nachname}, {obj.patient.vorname}"

    def validate(self, attrs):
        for feld, kategorie in PRAEPARAT_FELDER.items():
            p = attrs.get(feld)
            if p is not None and p.kategorie != kategorie:
                raise serializers.ValidationError({feld: "Präparat passt nicht zu diesem Feld."})
            # ausgeblendete Präparate nur behalten, nicht neu wählen (Entwurf 18)
            if p is not None and not p.aktiv and (self.instance is None or getattr(self.instance, f"{feld}_id") != p.id):
                raise serializers.ValidationError({feld: "Dieses Präparat ist ausgeblendet und kann nicht neu gewählt werden."})
        if "vitamine" in attrs and self.instance is not None:
            bisher = set(self.instance.vitamine.values_list("pk", flat=True))
            neu_ausgeblendet = [str(p) for p in attrs["vitamine"] if not p.aktiv and p.pk not in bisher]
            if neu_ausgeblendet:
                raise serializers.ValidationError({"vitamine": f"Ausgeblendet: {', '.join(neu_ausgeblendet)}."})
        return super().validate(attrs)

    @transaction.atomic
    def update(self, instance, validated_data):
        positionen = validated_data.pop("positionen", None)
        vitamine = validated_data.pop("vitamine", None)
        instance = super().update(instance, validated_data)
        if vitamine is not None:
            instance.vitamine.set(vitamine)
        if positionen is not None:
            # Positionen komplett ersetzen (einfach und eindeutig für den Editor)
            for alt in list(instance.positionen.all()):
                alt.delete()
            for i, daten in enumerate(positionen):
                daten.setdefault("reihenfolge", i)
                InfusionsplanPosition.objects.create(plan=instance, **daten)
        return instance


class InfusionsplanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                           mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """
    GET    /api/infusionsplaene/?patient=ID      Pläne eines Patienten
    POST   /api/infusionsplaene/entwurf/          {"patient": ID, "leer"?: bool, "vorlage"?: Plan-ID}
                                                  → neuer Entwurf (vorbelegt mit aktuellem Plan bzw. Vorlage)
    GET    /api/infusionsplaene/ID/vergleich/     alle Werte neben denen des Vorgängers
    PATCH  /api/infusionsplaene/ID/               Entwurf bearbeiten
    POST   /api/infusionsplaene/ID/freigeben/     Entwurf wird aktueller Plan
    DELETE /api/infusionsplaene/ID/               Entwurf verwerfen
    """

    serializer_class = InfusionsplanSerializer
    permission_classes = [PlanRecht]
    filterset_fields = ["patient", "status"]

    def get_queryset(self):
        return (
            Infusionsplan.objects.filter(patient__in=patienten_fuer(self.request.user))
            .select_related("patient", "erstellt_von", "freigegeben_von", "vorgaenger")
            .prefetch_related("positionen__praeparat", "vitamine")
        )

    def perform_update(self, serializer):
        if serializer.instance.status != Infusionsplan.Status.ENTWURF:
            raise PermissionError("Freigegebene Pläne sind unveränderlich. Bitte einen neuen Plan anlegen.")
        serializer.instance.patient.pruefe_bearbeitbar()
        serializer.save()

    def perform_destroy(self, instance):
        instance.patient.pruefe_bearbeitbar()
        for p in list(instance.positionen.all()):
            p.delete()
        instance.delete()

    @action(detail=False, methods=["post"])
    def entwurf(self, request):
        patient = patienten_fuer(request.user).filter(pk=request.data.get("patient")).first()
        if patient is None:
            return Response({"patient": "Patient nicht gefunden."}, status=status.HTTP_400_BAD_REQUEST)
        vorlage = None
        if request.data.get("vorlage"):
            vorlage = Infusionsplan.objects.filter(pk=request.data["vorlage"], patient=patient).first()
            if vorlage is None:
                return Response({"vorlage": "Plan nicht gefunden."}, status=status.HTTP_400_BAD_REQUEST)
        leer = str(request.data.get("leer", "")).lower() in ("1", "true", "ja")
        plan = Infusionsplan.neuer_entwurf(patient, request.user, leer=leer, vorlage=vorlage)
        return Response(self.get_serializer(plan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def vergleich(self, request, pk=None):
        return Response(self.get_object().vergleich())

    @action(detail=True, methods=["post"])
    def freigeben(self, request, pk=None):
        plan = self.get_object()
        plan.freigeben(request.user)
        protokolliere(SystemEreignis.Art.PLAN_FREIGEGEBEN, request, objekt=f"Plan {plan.id} / Patient {plan.patient.nummer}")
        plan.refresh_from_db()
        return Response(self.get_serializer(plan).data)

