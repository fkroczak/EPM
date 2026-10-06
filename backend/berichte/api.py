"""API der Berichte aus der Akte (F115): anlegen, bearbeiten, verwerfen, freigeben.

Entwürfe schreibt, wer Einträge in der Akte erfassen darf. Freigeben darf nur, wer das Recht „Berichte
freigeben“ hat (Standard: Mediziner, je Gruppe umstellbar – U54). Mit der Freigabe entsteht die PDF als
Dokument der Akte; danach ist der Bericht unveränderlich.
"""
from django.db import transaction
from rest_framework import mixins, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import BerichtFreigabeRecht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import ModelClean, RichText, benutzername
from patienten.api import AktenEintragViewSet
from stammdaten.models import Auswahlwert

from .models import Bericht


class BerichtSerializer(ModelClean, serializers.ModelSerializer):
    inhalt = RichText()
    art_name = serializers.CharField(source="art.wert", read_only=True, default=None)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    erstellt_von_name = serializers.SerializerMethodField()
    freigegeben_von_name = serializers.SerializerMethodField()
    freigabevermerk = serializers.CharField(read_only=True)
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = Bericht
        fields = ["id", "patient", "patient_name", "status", "status_name", "art", "art_name", "titel", "datum",
                  "empfaenger", "inhalt", "erstellt_am", "erstellt_von_name", "freigegeben_am",
                  "freigegeben_von_name", "freigabevermerk", "dokument", "pdf_sha256", "vorlage_version"]
        read_only_fields = ["status", "erstellt_am", "freigegeben_am", "dokument", "pdf_sha256", "vorlage_version"]

    def get_erstellt_von_name(self, obj):
        return benutzername(obj.erstellt_von)

    def get_freigegeben_von_name(self, obj):
        return benutzername(obj.freigegeben_von)

    def get_patient_name(self, obj):
        return f"{obj.patient.nachname}, {obj.patient.vorname}"

    def validate_patient(self, patient):
        if self.instance and patient != self.instance.patient:
            raise serializers.ValidationError("Der Patient kann nicht geändert werden.")
        return patient

    def validate_art(self, wert):
        if wert is not None and wert.liste != Auswahlwert.Liste.BERICHTART:
            raise serializers.ValidationError("Ungültiger Wert für die Liste „Berichtsarten“.")
        if wert is not None and not wert.aktiv and (self.instance is None or self.instance.art_id != wert.id):
            raise serializers.ValidationError("Diese Berichtsart ist ausgeblendet.")
        return wert


class BerichtViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin):
    """Berichte je Patient: ``?patient=ID&status=entwurf``. Gelöscht werden nur Entwürfe."""

    model = Bericht
    serializer_class = BerichtSerializer
    filterset_fields = ["patient", "status"]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().select_related("art", "erstellt_von", "freigegeben_von", "dokument")

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(erstellt_von=self.request.user)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        if not serializer.instance.ist_entwurf:
            raise PermissionError("Freigegebene Berichte sind unveränderlich. Bitte einen neuen Bericht anlegen.")
        serializer.save()

    def perform_destroy(self, instance):
        self.pruefe_patient(instance.patient)
        if not instance.ist_entwurf:
            raise PermissionError("Nur Entwürfe können verworfen werden.")
        instance.delete()

    @action(detail=True, methods=["post"], permission_classes=[BerichtFreigabeRecht])
    @transaction.atomic
    def freigeben(self, request, pk=None):
        bericht = self.get_object()
        self.pruefe_patient(bericht.patient)
        bericht._history_user = request.user
        bericht.freigeben(request.user)
        protokolliere(SystemEreignis.Art.BERICHT_FREIGEGEBEN, request, objekt=f"Bericht {bericht.pk}",
                      patient=bericht.patient.nummer, titel=bericht.titel)
        return Response(self.get_serializer(bericht).data, status=status.HTTP_200_OK)
