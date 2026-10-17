"""API der Laborbefunde und BIA-Messungen (F112–F114).

Erfassen und Ändern mit dem Recht „Kontakte, Gewichte, Termine, Dokumente erfassen“ – es ist dieselbe Art
Eintrag in der Akte. Gelöscht wird nicht; eine falsche Erfassung wird korrigiert, jede Fassung steht im
Verlauf.
"""
from django.db import transaction
from rest_framework import mixins, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from epm.api_basis import ModelClean, RichText, benutzername, patienten_fuer, FirmaFeld
from patienten.api import AktenEintragViewSet
from stammdaten.models import Laborparameter

from .models import BiaMessung, Laborbefund, Laborwert


class _PatientFest:
    def validate_patient(self, patient):
        if self.instance and patient != self.instance.patient:
            raise serializers.ValidationError("Der Patient kann nicht geändert werden.")
        return patient


class LaborwertSerializer(ModelClean, serializers.ModelSerializer):
    bezeichnung = serializers.CharField(read_only=True)
    anzeige_wert = serializers.CharField(read_only=True)
    ausserhalb = serializers.CharField(read_only=True, allow_null=True)
    gruppe = serializers.CharField(source="parameter.gruppe", read_only=True, default=None)
    gruppe_name = serializers.CharField(source="parameter.get_gruppe_display", read_only=True, default=None)

    class Meta:
        model = Laborwert
        fields = ["id", "parameter", "freitext_name", "bezeichnung", "wert", "wert_text", "anzeige_wert", "einheit",
                  "referenz_von", "referenz_bis", "ausserhalb", "bemerkung", "reihenfolge", "gruppe", "gruppe_name"]
        read_only_fields = ["id"]


class LaborbefundSerializer(FirmaFeld, ModelClean, _PatientFest, serializers.ModelSerializer):
    werte = LaborwertSerializer(many=True, required=False)
    beurteilung = RichText()
    erfasst_von_name = serializers.SerializerMethodField()
    anzahl_werte = serializers.IntegerField(read_only=True)
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = Laborbefund
        fields = ["id", "patient", "patient_name", "abgenommen_am", "abgenommen_um", "labor", "beurteilung", "dokument", "werte",
                  "anzahl_werte", "erfasst_am", "erfasst_von_name"]
        read_only_fields = ["erfasst_am"]

    def get_erfasst_von_name(self, obj):
        return benutzername(obj.erfasst_von)

    def get_patient_name(self, obj):
        return f"{obj.patient.nachname}, {obj.patient.vorname}"

    def validate_dokument(self, dokument):
        if dokument is not None and dokument.ausgeblendet:
            raise serializers.ValidationError("Dieses Dokument ist ausgeblendet.")
        return dokument

    def validate_werte(self, werte):
        gesehen = set()
        for zeile in werte:
            parameter = zeile.get("parameter")
            if parameter is None:
                continue
            if parameter.pk in gesehen:
                raise serializers.ValidationError(f"„{parameter.name}“ steht zweimal im Befund.")
            gesehen.add(parameter.pk)
            if not parameter.aktiv:
                raise serializers.ValidationError(f"„{parameter.name}“ ist ausgeblendet und nicht mehr wählbar.")
        return werte

    def _werte_schreiben(self, befund, werte):
        """Die Zeilen eines Befunds werden immer vollständig ersetzt – das ist für die Maske eindeutig."""
        for alt in list(befund.werte.all()):
            alt.delete()
        for nr, zeile in enumerate(werte):
            parameter = zeile.get("parameter")
            if parameter is not None and not zeile.get("einheit"):
                zeile["einheit"] = parameter.einheit
            if parameter is not None and zeile.get("referenz_von") is None and zeile.get("referenz_bis") is None:
                zeile["referenz_von"], zeile["referenz_bis"] = parameter.referenz_von, parameter.referenz_bis
            wert = Laborwert(befund=befund, reihenfolge=zeile.pop("reihenfolge", nr), **zeile)
            wert.full_clean()
            wert._history_user = self.context["request"].user
            wert.save()

    @transaction.atomic
    def create(self, validated_data):
        werte = validated_data.pop("werte", [])
        befund = super().create(validated_data)
        self._werte_schreiben(befund, werte)
        return befund

    @transaction.atomic
    def update(self, instance, validated_data):
        werte = validated_data.pop("werte", None)
        befund = super().update(instance, validated_data)
        if werte is not None:
            self._werte_schreiben(befund, werte)
        return befund


class LaborbefundViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         mixins.CreateModelMixin, mixins.UpdateModelMixin):
    """Laborbefunde je Patient: ``?patient=ID``. Die Maske holt sich den Katalog über ``/api/laborparameter/``."""

    model = Laborbefund
    serializer_class = LaborbefundSerializer
    pagination_class = None

    def get_queryset(self):
        return (super().get_queryset().select_related("erfasst_von", "dokument")
                .prefetch_related("werte__parameter"))

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(erfasst_von=self.request.user)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        serializer.save()

    @action(detail=False, methods=["get"])
    def verlauf(self, request):
        """Werte eines Parameters über die Zeit (für das Diagramm, U58):
        ``?patient=ID&parameter=ID``. Nur Zeilen mit einer Zahl."""
        patient = request.query_params.get("patient")
        parameter = request.query_params.get("parameter")
        if not (patient and parameter):
            raise serializers.ValidationError({"fehler": "Bitte Patient und Parameter angeben."})
        if not patienten_fuer(request.user).filter(pk=patient).exists():
            raise serializers.ValidationError({"patient": "Patient nicht gefunden."})
        werte = (Laborwert.objects
                 .filter(befund__patient_id=patient, parameter_id=parameter, wert__isnull=False)
                 .select_related("befund", "parameter").order_by("befund__abgenommen_am", "befund_id"))
        p = Laborparameter.objects.filter(pk=parameter).first()
        return Response({
            "parameter": {"id": p.id, "name": p.name, "einheit": p.einheit,
                          "referenz_von": p.referenz_von, "referenz_bis": p.referenz_bis} if p else None,
            "punkte": [{"datum": w.befund.abgenommen_am, "wert": w.wert, "einheit": w.einheit,
                        "befund": w.befund_id, "ausserhalb": w.ausserhalb} for w in werte],
        })


class BiaMessungSerializer(FirmaFeld, ModelClean, _PatientFest, serializers.ModelSerializer):
    beurteilung = RichText()
    erfasst_von_name = serializers.SerializerMethodField()
    bmi_berechnet = serializers.DecimalField(max_digits=4, decimal_places=1, read_only=True)
    magermasse_kg = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    # Häkchen der Maske: Gewicht zusätzlich in den Gewichtsverlauf eintragen (U50)
    gewicht_uebernehmen = serializers.BooleanField(write_only=True, required=False, default=True)

    class Meta:
        model = BiaMessung
        fields = ["id", "patient", "gemessen_am", "gewicht_kg", "bcm_kg", "fettmasse_kg", "ecw_prozent",
                  "koerperwasser_l", "bmi", "bmi_berechnet", "magermasse_kg", "beurteilung", "dokument",
                  "gewichtsmessung", "gewicht_uebernehmen", "erfasst_am", "erfasst_von_name"]
        read_only_fields = ["erfasst_am", "gewichtsmessung"]

    def get_erfasst_von_name(self, obj):
        return benutzername(obj.erfasst_von)

    def validate_dokument(self, dokument):
        if dokument is not None and dokument.ausgeblendet:
            raise serializers.ValidationError("Dieses Dokument ist ausgeblendet.")
        return dokument


class BiaMessungViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                        mixins.CreateModelMixin, mixins.UpdateModelMixin):
    """BIA-Messungen je Patient: ``?patient=ID``."""

    model = BiaMessung
    serializer_class = BiaMessungSerializer
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().select_related("erfasst_von", "dokument", "gewichtsmessung")

    @transaction.atomic
    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        uebernehmen = serializer.validated_data.pop("gewicht_uebernehmen", True)
        messung = serializer.save(erfasst_von=self.request.user)
        if uebernehmen:
            messung.gewicht_uebernehmen(self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        uebernehmen = serializer.validated_data.pop("gewicht_uebernehmen", False)
        messung = serializer.save()
        if uebernehmen or messung.gewichtsmessung_id:  # schon übernommen: Korrektur nachziehen
            messung.gewicht_uebernehmen(self.request.user)
