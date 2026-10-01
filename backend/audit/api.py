from django_filters import rest_framework as filters
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import NurAdmin

from .models import SystemEreignis, protokolliere
from .texte import GRUPPEN, beschreibung, gruppe, gruppe_name


class SystemEreignisSerializer(serializers.ModelSerializer):
    art_name = serializers.CharField(source="get_art_display", read_only=True)
    person = serializers.SerializerMethodField()
    gruppe = serializers.SerializerMethodField()
    gruppe_name = serializers.SerializerMethodField()
    beschreibung = serializers.SerializerMethodField()

    class Meta:
        model = SystemEreignis
        fields = ["id", "zeitpunkt", "art", "art_name", "gruppe", "gruppe_name", "beschreibung", "benutzer", "person",
                  "benutzername", "objekt", "details", "ip", "geraet"]

    def get_person(self, obj):
        if obj.benutzer:
            return obj.benutzer.anzeigename
        return obj.benutzername or "System"

    def get_gruppe(self, obj):
        return gruppe(obj.art)

    def get_gruppe_name(self, obj):
        return gruppe_name(obj.art)

    def get_beschreibung(self, obj):
        return beschreibung(obj)


class SystemEreignisFilter(filters.FilterSet):
    von = filters.DateFilter(field_name="zeitpunkt", lookup_expr="date__gte")
    bis = filters.DateFilter(field_name="zeitpunkt", lookup_expr="date__lte")
    gruppe = filters.CharFilter(method="filter_gruppe", label="Gruppen, mit Komma getrennt: " + ", ".join(GRUPPEN))

    def filter_gruppe(self, qs, name, wert):
        arten = []
        for g in (t.strip() for t in wert.split(",") if t.strip()):
            if g not in GRUPPEN:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"gruppe": f"Unbekannte Gruppe „{g}“. Erlaubt: {', '.join(GRUPPEN)}."})
            arten += GRUPPEN[g][1]
        return qs.filter(art__in=arten) if arten else qs

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
