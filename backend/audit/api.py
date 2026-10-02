from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import AuditRecht, TestdatenRecht

from .bereinigung import akte_bedingung, verbergen
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
    permission_classes = [AuditRecht]
    filterset_class = SystemEreignisFilter
    search_fields = ["benutzername", "objekt"]

    # Akten mit eingeschränkter Verarbeitung (Art. 18 DSGVO): Wer keine Einsicht nehmen dürfte (z. B. die
    # Administration bei echten Akten), sieht die Einträge ohne Namen, Titel und Freitext – und findet sie nicht
    # über die Suche nach dem Namen.
    def _verborgen(self) -> dict:
        if not hasattr(self, "_verborgen_cache"):
            from epm.api_basis import patienten_mit_eingeschraenkten
            from patienten.models import Patient

            sichtbar = patienten_mit_eingeschraenkten(self.request.user).values("id")
            self._verborgen_cache = dict(Patient.objects.filter(eingeschraenkt_am__isnull=False)
                                         .exclude(id__in=sichtbar).values_list("id", "nummer"))
        return self._verborgen_cache

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        if self.request.query_params.get("search"):
            # über positive Treffer ausschließen: ein verneinter Vergleich auf ``details`` ließe auch alle Einträge
            # ohne diesen Schlüssel fallen (NULL)
            for pid, nummer in self._verborgen().items():
                qs = qs.exclude(id__in=SystemEreignis.objects.filter(akte_bedingung(pid, nummer)).values("id"))
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        seite = self.paginate_queryset(qs)
        eintraege = verbergen(list(seite if seite is not None else qs), self._verborgen())
        daten = self.get_serializer(eintraege, many=True).data
        return self.get_paginated_response(daten) if seite is not None else Response(daten)

    def retrieve(self, request, *args, **kwargs):
        e = self.get_object()
        verbergen([e], self._verborgen())
        return Response(self.get_serializer(e).data)

    @action(detail=False, methods=["get"])
    def pdf(self, request):
        """Audit-Log für einen Zeitraum als PDF (F59), mit denselben Filtern wie die Liste; höchstens 5.000 Einträge."""
        from vorlagen.api import pdf_antwort
        from vorlagen.listen import protokoll_pdf

        qs = self.filter_queryset(self.get_queryset())[:5000]
        p = request.query_params
        teile = []
        if p.get("von") or p.get("bis"):
            teile.append(f"Zeitraum {p.get('von') or '…'} bis {p.get('bis') or '…'}")
        if p.get("gruppe"):
            teile.append(f"Art {p.get('gruppe')}")
        if p.get("search"):
            teile.append(f"Suche „{p.get('search')}“")
        pdf = protokoll_pdf(verbergen(list(qs), self._verborgen()), " · ".join(teile))
        protokolliere(SystemEreignis.Art.EXPORT, request, objekt=" · ".join(teile) or "alle Einträge", was="Audit-Log")
        return pdf_antwort(pdf, f"Audit-Log-{timezone.localdate():%Y-%m-%d}.pdf")


class TestdatenViewSet(viewsets.ViewSet):
    """Admin: alle Testpatienten löschen und die Musterdaten neu anlegen."""

    permission_classes = [TestdatenRecht]

    @action(detail=False, methods=["post"])
    def zuruecksetzen(self, request):
        from patienten.testdaten import testdaten_zuruecksetzen

        ergebnis = testdaten_zuruecksetzen()
        protokolliere(SystemEreignis.Art.TESTDATEN, request, **ergebnis)
        return Response(ergebnis)
