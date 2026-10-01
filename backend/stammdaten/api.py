"""Stammdaten: lesen dürfen alle, ändern nur der Admin. Gelöscht wird nichts, nur deaktiviert."""
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import StammdatenRecht, VersorgerRecht
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
    patienten_anzahl = serializers.SerializerMethodField()

    class Meta:
        model = Ansprechpartner
        fields = ["id", "versorger", "name", "zustaendigkeit", "telefon", "mobil", "email", "notiz", "aktiv",
                  "patienten_anzahl"]

    def get_patienten_anzahl(self, obj):
        return obj.patienten.filter(abgeschlossen_am__isnull=True, ist_test=False).count()


class AnsprechpartnerViewSet(OhneLoeschen):
    permission_classes = [VersorgerRecht]
    queryset = Ansprechpartner.objects.select_related("versorger")
    serializer_class = AnsprechpartnerSerializer
    filterset_fields = ["versorger", "aktiv"]
    pagination_class = None

    @action(detail=True, methods=["get"])
    def patienten(self, request, pk=None):
        """Betreute Patienten (in Betreuung) – zum Neuzuordnen, z. B. vor dem Deaktivieren."""
        from patienten.api import PatientListSerializer
        from epm.api_basis import patienten_fuer

        ap = self.get_object()
        qs = patienten_fuer(request.user).filter(ansprechpartner=ap, abgeschlossen_am__isnull=True)
        return Response(PatientListSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="neu-zuordnen")
    def neu_zuordnen(self, request, pk=None):
        """Alle Patienten dieses Ansprechpartners einem anderen desselben Versorgers zuordnen."""
        from patienten.models import Patient

        ap = self.get_object()
        ziel = Ansprechpartner.objects.filter(pk=request.data.get("ziel"), versorger=ap.versorger, aktiv=True).first()
        if ziel is None or ziel == ap:
            return Response({"ziel": "Bitte einen anderen, aktiven Ansprechpartner desselben Versorgers wählen."},
                            status=status.HTTP_400_BAD_REQUEST)
        anzahl = 0
        for p in Patient.objects.filter(ansprechpartner=ap, abgeschlossen_am__isnull=True):
            p.ansprechpartner = ziel
            p._history_user = request.user
            p.save()  # einzeln, damit jede Änderung im Verlauf der Akte steht
            anzahl += 1
        protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt=f"Ansprechpartner: {ap}",
                      aktion="Patienten neu zugeordnet", ziel=str(ziel), anzahl=anzahl)
        return Response({"neu_zugeordnet": anzahl})


class VersorgerSerializer(serializers.ModelSerializer):
    ansprechpartner = AnsprechpartnerSerializer(many=True, read_only=True)
    patienten_anzahl = serializers.IntegerField(source="patienten.count", read_only=True)

    class Meta:
        model = Versorger
        fields = ["id", "name", "strasse", "plz", "ort", "telefon", "fax", "email", "notiz", "aktiv",
                  "ansprechpartner", "patienten_anzahl"]


class VersorgerViewSet(OhneLoeschen):
    permission_classes = [VersorgerRecht]
    queryset = Versorger.objects.prefetch_related("ansprechpartner")
    serializer_class = VersorgerSerializer
    filterset_fields = ["aktiv"]
    search_fields = ["name", "ort"]
    pagination_class = None


class PraeparatSerializer(serializers.ModelSerializer):
    anzeige = serializers.CharField(source="__str__", read_only=True)
    in_plaenen = serializers.IntegerField(read_only=True)

    class Meta:
        model = Praeparat
        fields = ["id", "kategorie", "name", "konzentration", "einheit", "reihenfolge", "aktiv", "anzeige", "in_plaenen"]


def _praeparate_mit_nutzung():
    """Anzahl der Pläne, in denen ein Präparat vorkommt (Entwurf 18: Spalte „in Plänen“)."""
    from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
    from django.db.models.functions import Coalesce

    from infusionen.models import Infusionsplan

    felder = ["basis_praeparat", "glucose_praeparat", "aminosaeuren_praeparat", "lipide_praeparat",
              "albumin_praeparat", "katheterschutz", "spurenelemente", "vitamine"]
    bedingung = Q()
    for f in felder:
        bedingung |= Q(**{f: OuterRef("pk")})
    anzahl = (
        Infusionsplan.objects.filter(bedingung).order_by().annotate(gruppe=Value(1))
        .values("gruppe").annotate(n=Count("pk", distinct=True)).values("n")
    )
    return Praeparat.objects.annotate(in_plaenen=Coalesce(Subquery(anzahl, output_field=IntegerField()), 0))


class PraeparatViewSet(OhneLoeschen):
    queryset = Praeparat.objects.all()
    serializer_class = PraeparatSerializer
    filterset_fields = ["kategorie", "aktiv"]
    search_fields = ["name"]
    pagination_class = None

    def get_queryset(self):
        return _praeparate_mit_nutzung()


class EinstellungenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Einstellungen
        exclude = ["id"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        e = self.instance
        for unten, oben in Einstellungen.GRENZPAARE:
            if attrs.get(unten, getattr(e, unten)) >= attrs.get(oben, getattr(e, oben)):
                raise serializers.ValidationError({unten: "Untere Grenze muss kleiner als obere Grenze sein."})
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
