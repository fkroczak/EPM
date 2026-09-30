"""Stammdaten: lesen dürfen alle, ändern nur der Admin. Gelöscht wird nichts, nur deaktiviert."""
from rest_framework import mixins, serializers, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import StammdatenRecht
from audit.models import SystemEreignis, protokolliere

from .models import Ansprechpartner, Auswahlwert, Einstellungen, Praeparat, Versorger


class OhneLoeschen(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                   mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [StammdatenRecht]

    def perform_create(self, serializer):
        obj = serializer.save()
        protokolliere(SystemEreignis.Art.STAMMDATEN, self.request, objekt=f"{obj._meta.verbose_name}: {obj}",
                      aktion="angelegt")

    def perform_update(self, serializer):
        obj = serializer.save()
        protokolliere(SystemEreignis.Art.STAMMDATEN, self.request, objekt=f"{obj._meta.verbose_name}: {obj}",
                      aktion="geändert", felder=sorted(serializer.validated_data))


class AuswahlwertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auswahlwert
        fields = ["id", "liste", "wert", "reihenfolge", "aktiv"]


class AuswahlwertViewSet(OhneLoeschen):
    queryset = Auswahlwert.objects.all()
    serializer_class = AuswahlwertSerializer
    filterset_fields = ["liste", "aktiv"]
    pagination_class = None


class AnsprechpartnerSerializer(serializers.ModelSerializer):
    patienten_anzahl = serializers.IntegerField(source="patienten.count", read_only=True)

    class Meta:
        model = Ansprechpartner
        fields = ["id", "versorger", "name", "telefon", "mobil", "email", "notiz", "aktiv", "patienten_anzahl"]


class AnsprechpartnerViewSet(OhneLoeschen):
    queryset = Ansprechpartner.objects.select_related("versorger")
    serializer_class = AnsprechpartnerSerializer
    filterset_fields = ["versorger", "aktiv"]
    pagination_class = None


class VersorgerSerializer(serializers.ModelSerializer):
    ansprechpartner = AnsprechpartnerSerializer(many=True, read_only=True)
    patienten_anzahl = serializers.IntegerField(source="patienten.count", read_only=True)

    class Meta:
        model = Versorger
        fields = ["id", "name", "strasse", "plz", "ort", "telefon", "fax", "email", "notiz", "aktiv",
                  "ansprechpartner", "patienten_anzahl"]


class VersorgerViewSet(OhneLoeschen):
    queryset = Versorger.objects.prefetch_related("ansprechpartner")
    serializer_class = VersorgerSerializer
    filterset_fields = ["aktiv"]
    search_fields = ["name", "ort"]
    pagination_class = None


class PraeparatSerializer(serializers.ModelSerializer):
    anzeige = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Praeparat
        fields = ["id", "kategorie", "name", "konzentration", "einheit", "aktiv", "anzeige"]


class PraeparatViewSet(OhneLoeschen):
    queryset = Praeparat.objects.all()
    serializer_class = PraeparatSerializer
    filterset_fields = ["kategorie", "aktiv"]
    search_fields = ["name"]
    pagination_class = None


class EinstellungenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Einstellungen
        exclude = ["id"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        e = self.instance
        g_min = attrs.get("gewicht_min_kg", e.gewicht_min_kg)
        g_max = attrs.get("gewicht_max_kg", e.gewicht_max_kg)
        h_min = attrs.get("groesse_min_cm", e.groesse_min_cm)
        h_max = attrs.get("groesse_max_cm", e.groesse_max_cm)
        if g_min >= g_max or h_min >= h_max:
            raise serializers.ValidationError("Untere Grenze muss kleiner als obere Grenze sein.")
        return attrs


class EinstellungenView(APIView):
    permission_classes = [StammdatenRecht]

    def get(self, request):
        return Response(EinstellungenSerializer(Einstellungen.aktuell()).data)

    def patch(self, request):
        s = EinstellungenSerializer(Einstellungen.aktuell(), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt="Einstellungen", felder=sorted(s.validated_data))
        return Response(s.data)
