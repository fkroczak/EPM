"""API der Infusionspläne: Entwurf anlegen (vorbelegt), bearbeiten, freigeben, verwerfen."""
import hashlib
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, HttpResponse
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import FreigabeRecht, PlanAbschlussRecht, PlanRecht, recht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import ModelClean, RichText, benutzername, patienten_fuer, pruefe_schreibbereich
from stammdaten.models import Praeparat

from .models import Infusionsplan, InfusionsplanPosition, vorbelegung


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
    gesamtvolumen_ml = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    volumen_gewicht_kg = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    volumen_summe_ml = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    rate_ml_h = serializers.DecimalField(max_digits=7, decimal_places=1, read_only=True)
    ca_mg_mmol = serializers.DecimalField(max_digits=7, decimal_places=1, read_only=True)
    ca_mg_grenze_mmol = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    ca_mg_stabil = serializers.BooleanField(read_only=True, allow_null=True)
    geaenderte_felder = serializers.SerializerMethodField()
    erstellt_von_name = serializers.SerializerMethodField()
    freigegeben_von_name = serializers.SerializerMethodField()
    abgeschlossen_von_name = serializers.SerializerMethodField()
    freigabe_weg_name = serializers.CharField(source="get_freigabe_weg_display", read_only=True)
    freigabevermerk = serializers.CharField(read_only=True)
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = Infusionsplan
        fields = [
            "id", "patient", "patient_name", "status", "vorgaenger", "gueltig_ab",
            "basis_praeparat", "basis_ml", "glucose_praeparat", "glucose_g", "aminosaeuren_praeparat",
            "aminosaeuren_g", "lipide_praeparat", "lipide_g", "albumin_praeparat", "albumin_ml",
            "natrium_mmol", "kalium_mmol", "phosphat_mmol", "calcium_mmol", "magnesium_mmol",
            "ca_mg_mmol", "ca_mg_grenze_mmol", "ca_mg_stabil", "spurenelemente", "vitamine", "vitamine_namen",
            "kcal_manuell", "kcal_berechnet", "kcal", "gesamtvolumen_ml", "volumen_gewicht_kg", "volumen_summe_ml", "laufzeit_h", "rate_ml_h",
            "tage_pro_woche", "katheterschutz",
            "pantozol_stufe", "pantozol_tage", "bemerkung", "positionen", "geaenderte_felder",
            "erstellt_am", "erstellt_von_name", "freigegeben_am", "freigegeben_von_name",
            "freigabe_weg", "freigabe_weg_name", "freigabe_datum", "abgeschlossen_von_name", "freigabe_nachweis",
            "freigabevermerk",
            "pdf_datei", "pdf_sha256", "vorlage_version",
        ]
        read_only_fields = ["patient", "status", "vorgaenger", "erstellt_am", "freigegeben_am",
                            "freigabe_weg", "freigabe_datum", "freigabe_nachweis",
                            "pdf_datei", "pdf_sha256", "vorlage_version"]

    def get_vitamine_namen(self, obj):
        return [str(p) for p in obj.vitamine.all()]

    def get_geaenderte_felder(self, obj):
        return obj.geaenderte_felder()

    def get_erstellt_von_name(self, obj):
        return benutzername(obj.erstellt_von)

    def get_freigegeben_von_name(self, obj):
        return benutzername(obj.freigegeben_von)

    def get_abgeschlossen_von_name(self, obj):
        return benutzername(obj.abgeschlossen_von)

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
    GET    /api/infusionsplaene/vorbelegung/?patient=ID  Werte für den ersten Plan je kg Körpergewicht (wie im Altsystem)
    GET    /api/infusionsplaene/ID/vergleich/     alle Werte neben denen des Vorgängers
    PATCH  /api/infusionsplaene/ID/               Entwurf bearbeiten
    POST   /api/infusionsplaene/ID/freigeben/     Entwurf wird aktueller Plan (der Mediziner gibt selbst frei)
    POST   /api/infusionsplaene/ID/abschliessen/  Entwurf wird aktueller Plan, nachdem der Mediziner außerhalb von EPM
                                                  freigegeben hat: {"freigegeben_von": Benutzer-ID, "freigegeben_am",
                                                  "weg": email|telefon|persoenlich|schriftlich, "nachweis": Datei}
    GET    /api/infusionsplaene/freigebende/?patient=ID  Mediziner, die freigeben dürfen (für die Auswahl)
    DELETE /api/infusionsplaene/ID/               Entwurf verwerfen
    """

    serializer_class = InfusionsplanSerializer
    permission_classes = [PlanRecht]
    filterset_fields = ["patient", "status"]

    def get_queryset(self):
        return (
            Infusionsplan.objects.filter(patient__in=patienten_fuer(self.request.user))
            .select_related("patient", "erstellt_von", "freigegeben_von", "abgeschlossen_von", "vorgaenger")
            .prefetch_related("positionen__praeparat", "vitamine")
        )

    def perform_update(self, serializer):
        if serializer.instance.status != Infusionsplan.Status.ENTWURF:
            raise PermissionError("Freigegebene Pläne sind unveränderlich. Bitte einen neuen Plan anlegen.")
        pruefe_schreibbereich(self.request.user, serializer.instance.patient)
        serializer.instance.patient.pruefe_bearbeitbar()
        serializer.save()

    def perform_destroy(self, instance):
        pruefe_schreibbereich(self.request.user, instance.patient)
        instance.patient.pruefe_bearbeitbar()
        for p in list(instance.positionen.all()):
            p.delete()
        instance.delete()

    @action(detail=False, methods=["post"])
    def entwurf(self, request):
        patient = patienten_fuer(request.user).filter(pk=request.data.get("patient")).first()
        if patient is None:
            return Response({"patient": "Patient nicht gefunden."}, status=status.HTTP_400_BAD_REQUEST)
        pruefe_schreibbereich(request.user, patient)
        vorlage = None
        if request.data.get("vorlage"):
            vorlage = Infusionsplan.objects.filter(pk=request.data["vorlage"], patient=patient).first()
            if vorlage is None:
                return Response({"vorlage": "Plan nicht gefunden."}, status=status.HTTP_400_BAD_REQUEST)
        leer = str(request.data.get("leer", "")).lower() in ("1", "true", "ja")
        plan = Infusionsplan.neuer_entwurf(patient, request.user, leer=leer, vorlage=vorlage)
        return Response(self.get_serializer(plan).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def uebersicht(self, request):
        """Alle Pläne aller Patienten (Menüpunkt „Infusionspläne“, Wunsch 02.10.2026).

        GET /api/infusionsplaene/uebersicht/?gruppe=entwuerfe|aktuell|alt|abgeloest|alle&suche=&abgeschlossene=1
        → {"zaehler": {gruppe: n}, "grenze_monate", "ergebnisse": [kompakte Zeilen]} – höchstens 1.000 Zeilen.
        Ohne „abgeschlossene=1“ nur Pläne von Akten in Betreuung."""
        from datetime import timedelta

        from django.db.models import Q
        from django.utils import timezone

        from stammdaten.models import Einstellungen

        p = request.query_params
        gruppe = p.get("gruppe") or "aktuell"
        if gruppe not in ("entwuerfe", "aktuell", "alt", "abgeloest", "alle"):
            return Response({"gruppe": "Erlaubt: entwuerfe, aktuell, alt, abgeloest, alle."},
                            status=status.HTTP_400_BAD_REQUEST)
        e = Einstellungen.aktuell()
        grenze = timezone.localdate() - timedelta(days=30 * e.plan_alter_warnung_monate)
        qs = (Infusionsplan.objects.filter(patient__in=patienten_fuer(request.user))
              .select_related("patient", "erstellt_von", "freigegeben_von"))
        if str(p.get("abgeschlossene", "")).lower() not in ("1", "true", "ja"):
            qs = qs.filter(patient__abgeschlossen_am__isnull=True)
        suche = (p.get("suche") or "").strip()
        if suche:
            bedingung = Q(patient__nachname__icontains=suche) | Q(patient__vorname__icontains=suche)
            if suche.isdigit():
                bedingung |= Q(patient__nummer=int(suche))
            qs = qs.filter(bedingung)
        gruppen = {
            "entwuerfe": qs.filter(status=Infusionsplan.Status.ENTWURF),
            "aktuell": qs.filter(status=Infusionsplan.Status.AKTUELL),
            "alt": qs.filter(status=Infusionsplan.Status.AKTUELL, gueltig_ab__lt=grenze),
            "abgeloest": qs.filter(status=Infusionsplan.Status.ABGELOEST),
            "alle": qs,
        }
        reihenfolge = {"entwuerfe": ["-erstellt_am"], "aktuell": ["patient__nachname", "patient__vorname"],
                       "alt": ["gueltig_ab"], "abgeloest": ["-gueltig_ab"], "alle": ["-gueltig_ab", "-id"]}[gruppe]
        zeilen = [{
            "id": x.id, "patient": x.patient_id, "name": f"{x.patient.nachname}, {x.patient.vorname}",
            "nummer": x.patient.nummer, "ist_test": x.patient.ist_test,
            "patient_abgeschlossen": x.patient.abgeschlossen_am is not None,
            "status": x.status, "gueltig_ab": x.gueltig_ab, "kcal": x.kcal, "laufzeit_h": x.laufzeit_h,
            "rate_ml_h": x.rate_ml_h, "tage_pro_woche": x.tage_pro_woche,
            "erstellt_am": x.erstellt_am, "erstellt_von": benutzername(x.erstellt_von),
            "freigegeben_am": x.freigegeben_am, "freigegeben_von": benutzername(x.freigegeben_von),
            "pdf": bool(x.pdf_sha256), "pdf_sha256": x.pdf_sha256 or None,
            "aelter_als_grenze": x.status == Infusionsplan.Status.AKTUELL and x.gueltig_ab < grenze,
        } for x in gruppen[gruppe].order_by(*reihenfolge, "id")[:1000]]
        return Response({"zaehler": {k: v.count() for k, v in gruppen.items()},
                         "grenze_monate": e.plan_alter_warnung_monate, "ergebnisse": zeilen})

    @action(detail=False, methods=["get"])
    def vorbelegung(self, request):
        patient = patienten_fuer(request.user).filter(pk=request.query_params.get("patient")).first()
        if patient is None:
            return Response({"patient": "Patient nicht gefunden."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(vorbelegung(patient))

    @action(detail=True, methods=["get"])
    def vergleich(self, request, pk=None):
        return Response(self.get_object().vergleich())

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Gespeicherte PDF des freigegebenen Plans (F37): vorher Prüfsumme gegen ``pdf_sha256``,
        Ergebnis im Kopf ``X-EPM-Pruefung: ok|abweichend``. Die PDF wird nie neu erzeugt."""
        plan = self.get_object()
        if not plan.pdf_datei:
            return Response({"fehler": "Für diesen Plan ist keine PDF gespeichert (vor Einführung der PDF-Erzeugung "
                                       "freigegeben oder noch Entwurf)."}, status=status.HTTP_404_NOT_FOUND)
        pfad = settings.EPM_DOKUMENTE / plan.pdf_datei
        if not pfad.is_file():
            return Response({"fehler": "Die gespeicherte PDF fehlt im Dokumentenverzeichnis."},
                            status=status.HTTP_404_NOT_FOUND)
        h = hashlib.sha256()
        with open(pfad, "rb") as f:
            for teil in iter(lambda: f.read(1 << 16), b""):
                h.update(teil)
        pruefung = "ok" if h.hexdigest() == plan.pdf_sha256 else "abweichend"
        name = f"Infusionsplan-{plan.patient.nummer}-{plan.gueltig_ab:%Y-%m-%d}.pdf"
        if settings.EPM_X_ACCEL:
            antwort = HttpResponse(content_type="application/pdf")
            antwort["X-Accel-Redirect"] = settings.EPM_X_ACCEL_PREFIX + plan.pdf_datei
        else:
            antwort = FileResponse(open(pfad, "rb"), content_type="application/pdf")
        antwort["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(name)}"
        antwort["Cache-Control"] = "private, no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        antwort["X-EPM-Pruefung"] = pruefung
        antwort["X-EPM-Vorlage-Version"] = str(plan.vorlage_version or "")
        antwort["Access-Control-Expose-Headers"] = "X-EPM-Pruefung, X-EPM-Vorlage-Version"
        return antwort

    @action(detail=True, methods=["get"])
    def ansicht(self, request, pk=None):
        """Plan im Layout der aktiven Dokumentvorlage, zum Anzeigen in der Akte (nicht zum Versand): Entwürfe mit
        Wasserzeichen „ENTWURF“, Testpatienten „TESTDATEN“. Für freigegebene Pläne mit gespeicherter PDF gilt
        ``pdf/`` (das Original); diese Ansicht dient Plänen ohne gespeicherte PDF (Entwurf, vor Einführung freigegeben)."""
        from vorlagen.api import pdf_antwort
        from vorlagen.felder import Kontext
        from vorlagen.pdf import erzeuge_aus_vorlage, wasserzeichen_fuer

        plan = self.get_object()
        pdf, version = erzeuge_aus_vorlage("infusionsplan", Kontext(patient=plan.patient, plan=plan),
                                           wasserzeichen=wasserzeichen_fuer(plan.patient, plan),
                                           titel=f"Infusionsplan {plan.patient.nachname}, {plan.patient.vorname}")
        antwort = pdf_antwort(pdf, f"Infusionsplan-{plan.patient.nummer}-{plan.gueltig_ab:%Y-%m-%d}-Ansicht.pdf")
        antwort["X-EPM-Vorlage-Version"] = str(version or "")
        return antwort

    @action(detail=True, methods=["post"], permission_classes=[FreigabeRecht])
    def freigeben(self, request, pk=None):
        plan = self.get_object()
        pruefe_schreibbereich(request.user, plan.patient)
        plan.freigeben(request.user)
        protokolliere(SystemEreignis.Art.PLAN_FREIGEGEBEN, request, objekt=f"Plan {plan.id} / Patient {plan.patient.nummer}",
                      patient_id=plan.patient_id)
        plan.refresh_from_db()
        return Response(self.get_serializer(plan).data)

    @action(detail=False, methods=["get"], permission_classes=[recht("plaene_abschliessen", lesen="plaene_abschliessen")])
    def freigebende(self, request):
        """Mediziner, die Infusionspläne freigeben dürfen – zur Auswahl beim Abschließen nach Freigabe."""
        from accounts.models import Rolle, User

        patient = patienten_fuer(request.user).filter(pk=request.query_params.get("patient") or 0).first()
        qs = User.objects.filter(rolle=Rolle.MEDIZINER, is_active=True, nur_historisch=False)
        if patient is None or not patient.ist_test:
            qs = qs.filter(ist_test=False)
        return Response([{"id": u.id, "name": benutzername(u)} for u in qs if u.hat_recht("plaene_freigeben")])

    @action(detail=True, methods=["post"], permission_classes=[PlanAbschlussRecht],
            parser_classes=[JSONParser, MultiPartParser, FormParser])
    def abschliessen(self, request, pk=None):
        """Freigabe auf Anordnung (Festlegung 02.10.2026): Der Mediziner hat den Entwurf außerhalb von EPM geprüft und
        freigegeben (z. B. per E-Mail); die Person, die ihn hier abschließt, hält fest, wer freigegeben hat, wann, auf
        welchem Weg, und hängt den Nachweis an. Bei E-Mail und schriftlicher Freigabe ist der Nachweis Pflicht.
        Der Freigabevermerk auf der PDF nennt beide Personen."""
        from accounts.models import User
        from patienten.api import erkenne_dateityp, speichere_datei
        from patienten.models import Dokument
        from stammdaten.models import Auswahlwert

        plan = self.get_object()
        pruefe_schreibbereich(request.user, plan.patient)
        fehler, datum = {}, None
        mediziner_id = str(request.data.get("freigegeben_von", ""))
        mediziner = User.objects.filter(pk=mediziner_id).first() if mediziner_id.isdigit() else None
        weg = str(request.data.get("weg", ""))
        try:
            datum = serializers.DateField().to_internal_value(request.data.get("freigegeben_am") or "")
        except serializers.ValidationError:
            fehler["freigegeben_am"] = "Bitte das Datum der Freigabe angeben."
        upload = request.FILES.get("nachweis")
        typ = None
        if upload is not None:
            if upload.size > settings.EPM_UPLOAD_MAX_MB * 1024 * 1024:
                fehler["nachweis"] = f"Datei größer als {settings.EPM_UPLOAD_MAX_MB} MB."
            else:
                typ = erkenne_dateityp(upload)
                if typ is None:
                    fehler["nachweis"] = "Erlaubt sind PDF, JPG, PNG und TXT."
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        nachweis = None
        try:
            with transaction.atomic():
                if upload is not None:
                    plan.patient.pruefe_bearbeitbar()
                    meta = speichere_datei(plan.patient, upload, typ)
                    nachweis = Dokument(
                        patient=plan.patient, datum=datum, hochgeladen_von=request.user,
                        typ=Auswahlwert.objects.filter(liste=Auswahlwert.Liste.DOKUMENTTYP, wert="Freigabe").first(),
                        titel=f"Freigabe Infusionsplan gültig ab {plan.gueltig_ab:%d.%m.%Y}"[:200], **meta)
                    nachweis._history_user = request.user
                    nachweis.save()
                plan._history_user = request.user
                plan.abschliessen_auf_anordnung(request.user, mediziner, datum, weg, nachweis)
                protokolliere(SystemEreignis.Art.PLAN_FREIGEGEBEN, request,
                              objekt=f"Plan {plan.id} / Patient {plan.patient.nummer}", patient_id=plan.patient_id,
                              auf_anordnung=True, weg=plan.get_freigabe_weg_display(),
                              freigegeben_von=benutzername(mediziner), freigegeben_am=f"{datum:%d.%m.%Y}")
        except BaseException:
            if nachweis is not None:
                nachweis.pfad.unlink(missing_ok=True)
            raise
        plan.refresh_from_db()
        return Response(self.get_serializer(plan).data)

