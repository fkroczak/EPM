"""API für Erklärungen (Datenschutzinformation, Einwilligung, Schweigepflichtentbindung), Datenschutz-Anfragen und
die Übersicht „Datenschutz“.

GET/POST  /api/erklaerungen/?patient=ID         Erklärungen einer Akte; POST auch als multipart mit ``datei`` (Scan)
PATCH     /api/erklaerungen/ID/                 Datum, Notiz, verknüpftes Dokument
POST      /api/erklaerungen/ID/widerrufen/      {"widerrufen_am"?, "notiz"?}
GET/POST  /api/datenschutzanfragen/?patient=ID&offen=true
PATCH     /api/datenschutzanfragen/ID/          solange offen (auch Frist verlängern, mit Grund)
POST      /api/datenschutzanfragen/ID/erledigen/  {"ergebnis", "begruendung"?, "mitgeteilt_am"?}
GET       /api/datenschutz/                     Übersicht: offene Anfragen, eingeschränkte und löschbare Akten,
                                                Löschprotokoll
"""
from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import DatenschutzEntscheidenRecht, DatenschutzLesen, DatenschutzRecht
from audit.bereinigung import akte_text
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import (ModelClean, benutzername, patienten_fuer, patienten_mit_eingeschraenkten,
                           pruefe_schreibbereich)
from stammdaten.models import Auswahlwert, Einstellungen

from .api import AktenEintragViewSet, erkenne_dateityp, speichere_datei
from .datenschutz import einschraenken, einschraenkung_daten
from .kennzahlen import pruefliste
from .models import Datenschutzanfrage, Dokument, Erklaerung, Loeschprotokoll, plus_jahre

DOKUMENTTYP_ERKLAERUNG = "Einwilligung/Datenschutz"


# ================================================================= Erklärungen
class ErklaerungSerializer(ModelClean, serializers.ModelSerializer):
    art_name = serializers.CharField(source="get_art_display", read_only=True)
    status = serializers.SerializerMethodField()
    dokument_titel = serializers.CharField(source="dokument.titel", read_only=True, default=None)
    erfasst_von_name = serializers.SerializerMethodField()
    datei = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Erklaerung
        fields = ["id", "patient", "art", "art_name", "status", "erteilt_am", "dokument", "dokument_titel", "datei",
                  "vorlage_version", "notiz", "widerrufen_am", "widerruf_notiz", "erfasst_am", "erfasst_von_name"]
        read_only_fields = ["vorlage_version", "widerrufen_am", "widerruf_notiz", "erfasst_am"]

    def get_status(self, obj):
        return "widerrufen" if obj.widerrufen_am else "liegt_vor"

    def get_erfasst_von_name(self, obj):
        return benutzername(obj.erfasst_von)

    def validate(self, attrs):
        datei = attrs.pop("datei", None)
        attrs = super().validate(attrs)
        if self.instance is not None:
            for feld in ("patient", "art"):
                if feld in attrs and attrs[feld] != getattr(self.instance, feld):
                    raise serializers.ValidationError({feld: "Kann nicht geändert werden; bitte eine neue Erklärung erfassen."})
            if datei is not None:
                raise serializers.ValidationError({"datei": "Bitte das Dokument in der Akte hochladen und hier verknüpfen."})
        patient = attrs.get("patient") or self.instance.patient
        dokument = attrs.get("dokument")
        if dokument is not None and dokument.patient_id != patient.id:
            raise serializers.ValidationError({"dokument": "Das Dokument gehört zu einer anderen Akte."})
        if datei is not None:
            if dokument is not None:
                raise serializers.ValidationError({"datei": "Entweder eine Datei hochladen oder ein Dokument der Akte wählen."})
            if datei.size > settings.EPM_UPLOAD_MAX_MB * 1024 * 1024:
                raise serializers.ValidationError({"datei": f"Datei größer als {settings.EPM_UPLOAD_MAX_MB} MB."})
            self.erkannter_typ = erkenne_dateityp(datei)
            if self.erkannter_typ is None:
                raise serializers.ValidationError({"datei": "Erlaubt sind PDF, JPG, PNG und TXT."})
            self.upload = datei
        return attrs


class ErklaerungViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                        mixins.CreateModelMixin, mixins.UpdateModelMixin):
    """Erklärungen des Patienten. Kein Löschen: ein Widerruf wird eingetragen, eine neue Erklärung neu erfasst.
    Auch bei abgeschlossenen Akten möglich (ein Widerruf kann nach dem Abschluss eingehen)."""

    model = Erklaerung
    serializer_class = ErklaerungSerializer
    permission_classes = [DatenschutzRecht]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["patient", "art"]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().select_related("dokument", "erfasst_von")

    def pruefe_patient(self, patient):
        if not patienten_fuer(self.request.user).filter(pk=patient.pk).exists():
            raise serializers.ValidationError({"patient": "Patient nicht gefunden."})
        pruefe_schreibbereich(self.request.user, patient)

    @transaction.atomic
    def perform_create(self, serializer):
        from vorlagen.models import Dokumentvorlage

        patient = serializer.validated_data["patient"]
        self.pruefe_patient(patient)
        art = serializer.validated_data["art"]
        dokument = serializer.validated_data.get("dokument")
        upload = getattr(serializer, "upload", None)
        if upload is not None:
            patient.pruefe_bearbeitbar()  # in eine abgeschlossene Akte kommt kein neues Dokument
            meta = speichere_datei(patient, upload, serializer.erkannter_typ)
            typ = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.DOKUMENTTYP, wert=DOKUMENTTYP_ERKLAERUNG).first()
            dokument = Dokument(patient=patient, typ=typ, datum=serializer.validated_data["erteilt_am"],
                                titel=f"{Erklaerung.Art(art).label} (unterschrieben)"[:200],
                                hochgeladen_von=self.request.user, **meta)
            dokument._history_user = self.request.user
            try:
                dokument.save()
            except BaseException:
                dokument.pfad.unlink(missing_ok=True)
                raise
        serializer.save(erfasst_von=self.request.user, dokument=dokument,
                        vorlage_version=Dokumentvorlage.aktive(art).version)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        serializer.save()

    @action(detail=True, methods=["post"])
    def widerrufen(self, request, pk=None):
        """Widerruf eintragen (wirkt für die Zukunft, Art. 7 Abs. 3 DSGVO). ``{"widerrufen_am"?, "notiz"?}``"""
        e = self.get_object()
        self.pruefe_patient(e.patient)
        if e.widerrufen_am:
            return Response({"fehler": "Diese Erklärung ist bereits widerrufen."}, status=status.HTTP_400_BAD_REQUEST)
        tag = timezone.localdate()
        if request.data.get("widerrufen_am"):
            try:
                tag = serializers.DateField().to_internal_value(request.data["widerrufen_am"])
            except serializers.ValidationError as f:
                return Response({"widerrufen_am": f.detail}, status=status.HTTP_400_BAD_REQUEST)
        e.widerrufen_am = tag
        e.widerruf_notiz = str(request.data.get("notiz", "")).strip()[:300]
        e.clean()
        e._history_user = request.user
        e.save()
        protokolliere(SystemEreignis.Art.DATENSCHUTZ, request, objekt=akte_text(e.patient), patient_id=e.patient_id,
                      aktion=f"Widerruf eingetragen: {e.get_art_display()}")
        daten = self.get_serializer(e).data
        if e.art == Erklaerung.Art.SCHWEIGEPFLICHTENTBINDUNG and e.patient.bezugspersonen.filter(aktiv=True, auskunft_erlaubt=True).exists():
            daten["hinweis"] = "Bei den Bezugspersonen ist noch „Auskunft erlaubt“ eingetragen. Bitte prüfen."
        elif e.art == Erklaerung.Art.EINWILLIGUNG:
            daten["hinweis"] = ("Der Widerruf wirkt für die Zukunft. Bitte als Datenschutz-Anfrage erfassen, was daraus folgt "
                                "(z. B. Betreuung beenden, Akte abschließen).")
        return Response(daten)


# ================================================================= Anfragen betroffener Personen
class DatenschutzanfrageSerializer(ModelClean, serializers.ModelSerializer):
    art_name = serializers.CharField(source="get_art_display", read_only=True)
    ergebnis_name = serializers.CharField(source="get_ergebnis_display", read_only=True)
    patient_name = serializers.SerializerMethodField()
    patient_nummer = serializers.IntegerField(source="patient.nummer", read_only=True)
    patient_ist_test = serializers.BooleanField(source="patient.ist_test", read_only=True)
    patient_eingeschraenkt = serializers.BooleanField(source="patient.ist_eingeschraenkt", read_only=True)
    frist_bis = serializers.DateField(read_only=True)
    ueberfaellig = serializers.BooleanField(read_only=True)
    ist_offen = serializers.BooleanField(read_only=True)
    erfasst_von_name = serializers.SerializerMethodField()
    erledigt_von_name = serializers.SerializerMethodField()

    class Meta:
        model = Datenschutzanfrage
        fields = ["id", "patient", "patient_name", "patient_nummer", "patient_ist_test", "patient_eingeschraenkt",
                  "art", "art_name", "eingegangen_am", "gestellt_von", "inhalt", "frist_verlaengert",
                  "verlaengerung_grund", "frist_bis", "ueberfaellig", "ist_offen", "ergebnis", "ergebnis_name",
                  "begruendung", "mitgeteilt_am", "erledigt_am", "erledigt_von_name", "erfasst_am", "erfasst_von_name"]
        read_only_fields = ["ergebnis", "begruendung", "mitgeteilt_am", "erledigt_am", "erfasst_am"]

    def get_patient_name(self, obj):
        return f"{obj.patient.nachname}, {obj.patient.vorname}"

    def get_erfasst_von_name(self, obj):
        return benutzername(obj.erfasst_von)

    def get_erledigt_von_name(self, obj):
        return benutzername(obj.erledigt_von)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None and "patient" in attrs and attrs["patient"] != self.instance.patient:
            raise serializers.ValidationError({"patient": "Der Patient kann nicht geändert werden."})
        return attrs


class DatenschutzanfrageFilter(filters.FilterSet):
    offen = filters.BooleanFilter(field_name="erledigt_am", lookup_expr="isnull")

    class Meta:
        model = Datenschutzanfrage
        fields = ["patient", "art"]


class DatenschutzanfrageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                                mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Anfragen (Auskunft, Berichtigung, Löschung, Einschränkung, Widerruf) als Vorgang mit Frist. Erfassen mit
    „Datenschutz: Erklärungen und Anfragen erfassen“, erledigen mit „Datenschutz: Anfragen entscheiden“.
    Anfragen gibt es auch zu Akten, deren Verarbeitung eingeschränkt ist – diese sieht und bearbeitet nur, wer
    Einsicht nehmen dürfte (Recht „entscheiden“; Admins nur bei Testpatienten)."""

    serializer_class = DatenschutzanfrageSerializer
    permission_classes = [DatenschutzRecht]
    filterset_class = DatenschutzanfrageFilter
    pagination_class = None

    def _patienten(self):
        return patienten_mit_eingeschraenkten(self.request.user)

    def get_queryset(self):
        return (Datenschutzanfrage.objects.filter(patient__in=self._patienten())
                .select_related("patient", "erfasst_von", "erledigt_von"))

    def _pruefe(self, patient):
        if not self._patienten().filter(pk=patient.pk).exists():
            raise serializers.ValidationError({"patient": "Patient nicht gefunden."})
        pruefe_schreibbereich(self.request.user, patient)

    def perform_create(self, serializer):
        patient = serializer.validated_data["patient"]
        self._pruefe(patient)
        a = serializer.save(erfasst_von=self.request.user)
        protokolliere(SystemEreignis.Art.DATENSCHUTZ, self.request, objekt=akte_text(patient), patient_id=patient.id,
                      aktion=f"Anfrage erfasst: {a.get_art_display()}, Frist {a.frist_bis:%d.%m.%Y}")

    def perform_update(self, serializer):
        a = serializer.instance
        self._pruefe(a.patient)
        if not a.ist_offen:
            raise serializers.ValidationError({"fehler": "Erledigte Anfragen können nicht geändert werden."})
        verlaengert = not a.frist_verlaengert and serializer.validated_data.get("frist_verlaengert")
        a = serializer.save()
        if verlaengert:
            protokolliere(SystemEreignis.Art.DATENSCHUTZ, self.request, objekt=akte_text(a.patient),
                          patient_id=a.patient_id,
                          aktion=f"Frist der Anfrage „{a.get_art_display()}“ verlängert bis {a.frist_bis:%d.%m.%Y}")

    @action(detail=True, methods=["post"], permission_classes=[DatenschutzEntscheidenRecht])
    @transaction.atomic
    def erledigen(self, request, pk=None):
        """Anfrage mit Ergebnis abschließen: ``{"ergebnis": "erfuellt|eingeschraenkt|abgelehnt|zurueckgezogen",
        "begruendung"?, "mitgeteilt_am"?}``. „eingeschraenkt“ schränkt zugleich die Verarbeitung der Akte ein.
        Eine Löschung wird nicht hier, sondern mit „Akte endgültig löschen“ erfüllt."""
        a = self.get_object()
        self._pruefe(a.patient)
        if not a.ist_offen:
            return Response({"fehler": "Diese Anfrage ist bereits erledigt."}, status=status.HTTP_400_BAD_REQUEST)
        E = Datenschutzanfrage.Ergebnis
        ergebnis = request.data.get("ergebnis")
        begruendung = str(request.data.get("begruendung", "")).strip()
        fehler, mitgeteilt = {}, None
        if ergebnis not in E.values:
            fehler["ergebnis"] = "Bitte das Ergebnis wählen."
        elif ergebnis == E.ERFUELLT and a.art == Datenschutzanfrage.Art.LOESCHUNG:
            fehler["ergebnis"] = ("Eine Löschung wird mit „Akte endgültig löschen“ erfüllt (Mediziner oder Admin). Steht eine "
                                  "Aufbewahrungspflicht entgegen: „Verarbeitung eingeschränkt statt gelöscht“.")
        elif ergebnis in (E.ABGELEHNT, E.EINGESCHRAENKT) and len(begruendung) < 10:
            # Art. 12 Abs. 4 DSGVO: Wird der Antrag nicht (voll) erfüllt, sind der Person die Gründe mitzuteilen
            fehler["begruendung"] = "Bitte die Begründung angeben (sie wird der Person mitgeteilt)."
        if request.data.get("mitgeteilt_am"):
            try:
                mitgeteilt = serializers.DateField().to_internal_value(request.data["mitgeteilt_am"])
            except serializers.ValidationError as f:
                fehler["mitgeteilt_am"] = f.detail
            else:
                if mitgeteilt > timezone.localdate():
                    fehler["mitgeteilt_am"] = "Das Datum liegt in der Zukunft."
                elif mitgeteilt < a.eingegangen_am:
                    fehler["mitgeteilt_am"] = "Das Datum liegt vor dem Eingang der Anfrage."
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        if ergebnis == E.EINGESCHRAENKT and not a.patient.ist_eingeschraenkt:
            einschraenken(a.patient, request.user, begruendung, request)
        a.ergebnis, a.begruendung, a.mitgeteilt_am = ergebnis, begruendung, mitgeteilt
        a.erledigt_am, a.erledigt_von = timezone.now(), request.user
        a._history_user = request.user
        a.save()
        protokolliere(SystemEreignis.Art.DATENSCHUTZ, request, objekt=akte_text(a.patient), patient_id=a.patient_id,
                      aktion=f"Anfrage erledigt: {a.get_art_display()} – {a.get_ergebnis_display()}", ergebnis=ergebnis)
        return Response(self.get_serializer(a).data)


# ================================================================= Übersicht
class DatenschutzViewSet(viewsets.ViewSet):
    """Übersicht „Datenschutz“: was zu tun ist (offene Anfragen mit Frist, Akten mit abgelaufener Aufbewahrung),
    welche Akten eingeschränkt sind, und das Löschprotokoll."""

    permission_classes = [DatenschutzLesen]

    def list(self, request):
        user = request.user
        e = Einstellungen.aktuell()
        heute = timezone.localdate()
        # Alle Akten im Bereich der Person – auch eingeschränkte, damit Fristen nicht untergehen. Von einer
        # eingeschränkten Akte sieht aber nur, wer Einsicht nehmen dürfte, mehr als die Nummer.
        alle = patienten_fuer(user, eingeschraenkte=True)
        mit_namen = set(patienten_mit_eingeschraenkten(user).values_list("id", flat=True))

        def name(p):
            return f"{p.nachname}, {p.vorname}" if p.id in mit_namen else None

        anfragen = (Datenschutzanfrage.objects.filter(patient__in=alle, erledigt_am__isnull=True)
                    .select_related("patient", "erfasst_von", "erledigt_von"))
        offene = sorted((a for a in anfragen if a.patient_id in mit_namen), key=lambda a: a.frist_bis)
        abgelaufen, bald = [], []
        geschlossen = alle.filter(abgeschlossen_am__isnull=False).annotate(
            kontakt_zuletzt=Max("kontakte__zeitpunkt", filter=Q(kontakte__storniert_am__isnull=True)))
        for p in geschlossen.order_by("abgeschlossen_am", "nummer"):
            a = p.aufbewahrung(e.aufbewahrung_jahre, letzter_kontakt=p.kontakt_zuletzt)
            zeile = {"id": p.id, "nummer": p.nummer, "name": name(p), "ist_test": p.ist_test,
                     "abgeschlossen_am": p.abgeschlossen_am, "aufbewahrung_bis": a["bis"],
                     "verlaengert": bool(a["verlaengert_bis"] and a["bis"] == a["verlaengert_bis"]),
                     "eingeschraenkt": p.ist_eingeschraenkt}
            if a["abgelaufen"]:
                abgelaufen.append(zeile)
            elif a["bis"] <= plus_jahre(heute, 1):
                bald.append(zeile)
        eingeschraenkt = [
            {"id": p.id, "nummer": p.nummer, "name": name(p), "ist_test": p.ist_test,
             **(einschraenkung_daten(p) if p.id in mit_namen else {"am": p.eingeschraenkt_am, "von": None, "grund": None})}
            for p in alle.filter(eingeschraenkt_am__isnull=False).select_related("eingeschraenkt_von").order_by("-eingeschraenkt_am")
        ]
        protokoll = Loeschprotokoll.objects.select_related("geloescht_von")
        if user.ist_test:
            protokoll = protokoll.filter(ist_test=True)
        statistik = patienten_fuer(user) if user.ist_test else patienten_fuer(user).filter(ist_test=False)
        pruefen = pruefliste(statistik)
        return Response({
            "anfragen_offen": DatenschutzanfrageSerializer(offene, many=True).data,
            "anfragen_ueberfaellig": sum(1 for a in offene if a.ueberfaellig),
            # offene Anfragen zu eingeschränkten Akten, die diese Person nicht sieht (nur die Anzahl)
            "anfragen_verborgen": sum(1 for a in anfragen if a.patient_id not in mit_namen),
            "aufbewahrung_abgelaufen": abgelaufen,
            "aufbewahrung_laeuft_ab": bald,
            "eingeschraenkt": eingeschraenkt,
            "erklaerungen_fehlen": pruefen["erklaerungen_fehlen"],
            "abschluss_pruefen": pruefen["abschluss_pruefen"],
            "loeschprotokoll": [
                {"id": x.id, "nummer": x.nummer, "ist_test": x.ist_test, "geloescht_am": x.geloescht_am,
                 "geloescht_von": benutzername(x.geloescht_von), "rechtsgrund": x.rechtsgrund,
                 "rechtsgrund_name": x.get_rechtsgrund_display(), "grund": x.grund,
                 "abgeschlossen_am": x.abgeschlossen_am, "aufbewahrung_bis": x.aufbewahrung_bis, "umfang": x.umfang}
                for x in protokoll[:100]
            ],
            "einstellungen": {"aufbewahrung_jahre": e.aufbewahrung_jahre,
                              "abschluss_pruefen_monate": e.abschluss_pruefen_monate,
                              "protokoll_aufbewahrung_jahre": e.protokoll_aufbewahrung_jahre,
                              "pflicht_erklaerungen": e.pflicht_erklaerungen},
            "darf_entscheiden": user.hat_recht("datenschutz_entscheiden"),
        })
