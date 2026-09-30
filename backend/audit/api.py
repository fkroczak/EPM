from django_filters import rest_framework as filters
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import NurAdmin

from .models import SystemEreignis, protokolliere


class SystemEreignisSerializer(serializers.ModelSerializer):
    art_name = serializers.CharField(source="get_art_display", read_only=True)
    person = serializers.SerializerMethodField()

    class Meta:
        model = SystemEreignis
        fields = ["id", "zeitpunkt", "art", "art_name", "benutzer", "person", "benutzername", "objekt", "details", "ip"]

    def get_person(self, obj):
        return obj.benutzer.anzeigename if obj.benutzer else obj.benutzername


class SystemEreignisFilter(filters.FilterSet):
    von = filters.DateFilter(field_name="zeitpunkt", lookup_expr="date__gte")
    bis = filters.DateFilter(field_name="zeitpunkt", lookup_expr="date__lte")

    class Meta:
        model = SystemEreignis
        fields = ["art", "benutzer"]


class SystemEreignisViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Systemprotokoll (nur lesen, nur Admin)."""

    queryset = SystemEreignis.objects.select_related("benutzer")
    serializer_class = SystemEreignisSerializer
    permission_classes = [NurAdmin]
    filterset_class = SystemEreignisFilter
    search_fields = ["benutzername", "objekt"]


class TestdatenViewSet(viewsets.ViewSet):
    """Admin: alle Testpatienten löschen und die Musterdaten neu anlegen."""

    permission_classes = [NurAdmin]

    @action(detail=False, methods=["post"])
    def zuruecksetzen(self, request):
        from patienten.testdaten import testdaten_zuruecksetzen

        ergebnis = testdaten_zuruecksetzen()
        protokolliere(SystemEreignis.Art.TESTDATEN, request, **ergebnis)
        return Response(ergebnis)
