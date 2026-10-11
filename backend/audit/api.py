from datetime import timedelta

from django.db.models import Q
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

    # Akten außerhalb des eigenen Bereichs (Sicherheitsprüfung 11.10.2026): Wer in der Regeneration Clinic das
    # Audit-Log liest, sieht die Einträge zu Akten, die nur der DSKM gehören (und umgekehrt), ohne Namen und Inhalt –
    # wie bei eingeschränkten Akten. Ebenso Testpatienten für Personen ohne „Testdaten sehen“.
    def _fremde(self) -> dict:
        if not hasattr(self, "_fremde_cache"):
            from epm.api_basis import patienten_fuer
            from patienten.models import Patient

            eigene = patienten_fuer(self.request.user, eingeschraenkte=True).values("id")
            self._fremde_cache = dict(Patient.objects.exclude(id__in=eigene).values_list("id", "nummer"))
        return self._fremde_cache

    def _bereinigt(self, eintraege):
        return verbergen(verbergen(eintraege, self._verborgen()), self._fremde(), "andere Firma")

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        if self.request.query_params.get("search"):
            # über positive Treffer ausschließen: ein verneinter Vergleich auf ``details`` ließe auch alle Einträge
            # ohne diesen Schlüssel fallen (NULL)
            for pid, nummer in self._verborgen().items():
                qs = qs.exclude(id__in=SystemEreignis.objects.filter(akte_bedingung(pid, nummer)).values("id"))
            fremde = self._fremde()
            if fremde:
                nummern = "|".join(str(n) for n in sorted(set(fremde.values())))
                treffer = (Q(details__patient_id__in=list(fremde)) | Q(details__nach_id__in=list(fremde))
                           | Q(objekt__regex=rf"(\(Nr\. ({nummern})\)|/ Patient ({nummern}))$"))
                qs = qs.exclude(id__in=SystemEreignis.objects.filter(treffer).values("id"))
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        seite = self.paginate_queryset(qs)
        eintraege = self._bereinigt(list(seite if seite is not None else qs))
        daten = self.get_serializer(eintraege, many=True).data
        return self.get_paginated_response(daten) if seite is not None else Response(daten)

    def retrieve(self, request, *args, **kwargs):
        e = self.get_object()
        self._bereinigt([e])
        return Response(self.get_serializer(e).data)

    @action(detail=False, methods=["get"])
    def zusammenfassung(self, request):
        """Admin-Startseite, Kachel „Zugriffe · 7 Tage“ (S12): Anzahl je Art im Zeitraum (``?tage=7``, 1–90).
        Jede Zeile verweist auf das Audit-Log mit derselben Gruppe (``gruppe``) und demselben Zeitraum."""
        try:
            tage = min(max(int(request.query_params.get("tage", 7)), 1), 90)
        except ValueError:
            tage = 7
        seit = timezone.now() - timedelta(days=tage)
        qs = SystemEreignis.objects.filter(zeitpunkt__gte=seit)
        A = SystemEreignis.Art
        zeilen = [
            ("anmeldungen", "Anmeldungen", "anmeldung", qs.filter(art=A.ANMELDUNG)),
            ("fehlversuche", "Fehlversuche", "fehlversuch", qs.filter(art__in=GRUPPEN["fehlversuch"][1])),
            ("exporte", "PDF-Exporte", "export", qs.filter(art=A.EXPORT)),
            ("vorlagen", "Vorlagen geändert", "vorlage", qs.filter(art__in=[A.VORLAGE, A.STAMMDATEN])),
            ("wiederherstellungen", "Sicherungen wiederhergestellt", "backup",
             qs.filter(art=A.BACKUP, details__ereignis="wiederhergestellt")),
        ]
        return Response({"tage": tage, "von": timezone.localdate(seit),
                         "zeilen": [{"schluessel": k, "text": t, "gruppe": g, "anzahl": q.count()}
                                    for k, t, g, q in zeilen]})

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
        pdf = protokoll_pdf(self._bereinigt(list(qs)), " · ".join(teile))
        protokolliere(SystemEreignis.Art.EXPORT, request, objekt=" · ".join(teile) or "alle Einträge", was="Audit-Log")
        return pdf_antwort(pdf, f"Audit-Log-{timezone.localdate():%Y-%m-%d}.pdf")


class TestdatenViewSet(viewsets.ViewSet):
    """Admin: alle Testpatienten löschen und die Musterdaten neu anlegen."""

    permission_classes = [TestdatenRecht]

    def list(self, request):
        """Admin-Startseite, Kachel „Testumgebung“ (S12): Anzahl der Testpatienten, letztes Zurücksetzen."""
        from patienten.models import Patient

        zuletzt = SystemEreignis.objects.filter(art=SystemEreignis.Art.TESTDATEN).select_related("benutzer").first()
        test = Patient.objects.filter(ist_test=True)
        return Response({
            "in_betreuung": test.filter(abgeschlossen_am__isnull=True).count(),
            "abgeschlossen": test.filter(abgeschlossen_am__isnull=False).count(),
            "zuletzt_am": zuletzt.zeitpunkt if zuletzt else None,
            "zuletzt_von": (zuletzt.benutzer.anzeigename if zuletzt.benutzer else zuletzt.benutzername) if zuletzt else None,
        })

    @action(detail=False, methods=["post"])
    def zuruecksetzen(self, request):
        from patienten.testdaten import testdaten_zuruecksetzen

        ergebnis = testdaten_zuruecksetzen()
        protokolliere(SystemEreignis.Art.TESTDATEN, request, **ergebnis)
        return Response(ergebnis)
