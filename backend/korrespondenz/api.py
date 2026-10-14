"""API der Korrespondenz (Reiter „Korrespondenz“ der Akte, 14.10.2026).

``/api/korrespondenz/?patient=ID&status=entwurf|freigegeben|versendet`` – Liste und Anlegen (Entwurf);
``/api/korrespondenz/{id}/`` – ansehen, ändern und löschen (nur Entwürfe);
``POST /api/korrespondenz/vorschau/`` – PDF eines noch nicht gespeicherten Schreibens (Wasserzeichen ENTWURF);
``GET …/{id}/pdf/`` – Entwurf: Vorschau; freigegeben: die gespeicherte PDF (Prüfsumme wird geprüft);
``POST …/{id}/freigeben/`` – Recht „Schreiben freigeben“; ``POST …/{id}/versendet/`` – ``{"versandweg", "versendet_am",
"versand_notiz"?}``; ``POST …/{id}/kopieren/`` – neuer Entwurf; ``GET …/{id}/verlauf/`` – alle Fassungen.

Entwürfe anlegen, ändern, löschen, kopieren und den Versand vermerken darf, wer Einträge erfassen darf
(„Kontakte, Gewichte, Termine, Dokumente erfassen“); Admins wie überall nur bei Testpatienten.
"""
import hashlib

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import mixins, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import SchreibenFreigabeRecht
from audit.bereinigung import akte_text
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import FirmaFeld, ModelClean, benutzername, patienten_fuer
from patienten.api import AktenEintragViewSet
from patienten.models import Termin

from .models import MAX_TEXT, Schreiben


class SchreibenSerializer(FirmaFeld, ModelClean, serializers.ModelSerializer):
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    versandweg_name = serializers.CharField(source="get_versandweg_display", read_only=True)
    erstellt_von_name = serializers.SerializerMethodField()
    freigegeben_von_name = serializers.SerializerMethodField()
    versendet_von_name = serializers.SerializerMethodField()
    freigabevermerk = serializers.CharField(read_only=True)
    termin_text = serializers.SerializerMethodField()
    text = serializers.CharField(required=False, allow_blank=True, max_length=MAX_TEXT, trim_whitespace=False)
    termin = serializers.PrimaryKeyRelatedField(queryset=Termin.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Schreiben
        fields = ["id", "patient", "status", "status_name", "vorlage", "vorlage_name", "vorlage_version", "titel",
                  "empfaenger", "text", "termin", "termin_text", "optionen", "kopie_von", "erstellt_am",
                  "erstellt_von_name", "freigegeben_am", "freigegeben_von_name", "freigabevermerk", "dokument",
                  "pdf_sha256", "versendet_am", "versandweg", "versandweg_name", "versand_notiz", "versendet_von_name",
                  "versand_erfasst_am"]
        read_only_fields = ["status", "vorlage_name", "vorlage_version", "kopie_von", "erstellt_am", "freigegeben_am",
                            "dokument", "pdf_sha256", "versendet_am", "versandweg", "versand_notiz",
                            "versand_erfasst_am"]

    def get_erstellt_von_name(self, obj):
        return benutzername(obj.erstellt_von)

    def get_freigegeben_von_name(self, obj):
        return benutzername(obj.freigegeben_von)

    def get_versendet_von_name(self, obj):
        return benutzername(obj.versendet_von)

    def get_termin_text(self, obj):
        t = obj.termin
        if t is None:
            return None
        return f"{t.faellig_am:%d.%m.%Y}" + (f", {t.uhrzeit:%H:%M} Uhr" if t.uhrzeit else "") + \
            (f" · {t.titel}" if t.titel else "")

    def validate_patient(self, patient):
        if self.instance and patient != self.instance.patient:
            raise serializers.ValidationError("Der Patient kann nicht geändert werden.")
        request = self.context.get("request")
        if request is not None and not patienten_fuer(request.user).filter(pk=patient.pk).exists():
            raise serializers.ValidationError("Patient nicht gefunden.")
        return patient

    def validate_titel(self, wert):
        return " ".join(wert.split())

    def validate_empfaenger(self, wert):
        return wert.strip()

    def validate_optionen(self, wert):
        if wert in (None, ""):
            return {}
        if not isinstance(wert, dict) or set(wert) - {"attest", "tage"}:
            raise serializers.ValidationError("Nur „attest“ und „tage“.")
        tage = wert.get("tage")
        if tage not in (None, "") and (not isinstance(tage, int) or isinstance(tage, bool) or not 1 <= tage <= 999):
            raise serializers.ValidationError("Reisedauer in Tagen (1 bis 999).")
        if "attest" in wert and not isinstance(wert["attest"], bool):
            raise serializers.ValidationError("„attest“: ja oder nein.")
        return {k: v for k, v in wert.items() if v not in (None, "")}

    def validate(self, attrs):
        from vorlagen.schreiben import schreiben_aus_akte

        vorlage = attrs.get("vorlage", self.instance.vorlage if self.instance else None)
        patient = attrs.get("patient", self.instance.patient if self.instance else None)
        angaben = schreiben_aus_akte(vorlage)
        if angaben is None:
            raise serializers.ValidationError({"vorlage": "Bitte eine Vorlage wählen."})
        termin = attrs.get("termin", self.instance.termin if self.instance else None)
        if angaben["termin"]:
            if termin is None:
                raise serializers.ValidationError({"termin": "Bitte einen Termin wählen."})
            if patient is not None and termin.patient_id != patient.id:
                raise serializers.ValidationError({"termin": "Der Termin gehört zu einer anderen Akte."})
        elif termin is not None and patient is not None and termin.patient_id != patient.id:
            raise serializers.ValidationError({"termin": "Der Termin gehört zu einer anderen Akte."})
        return super().validate(attrs)

    def _speichern(self, instanz, daten):
        from vorlagen.models import art_name

        request = self.context.get("request")
        for feld, wert in daten.items():
            setattr(instanz, feld, wert)
        instanz.vorlage_name = art_name(instanz.vorlage)[:200]
        if request is not None:
            instanz._history_user = request.user
        instanz.save()
        return instanz

    def create(self, validated_data):
        return self._speichern(Schreiben(), validated_data)

    def update(self, instance, validated_data):
        return self._speichern(instance, validated_data)


class SchreibenViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                       mixins.UpdateModelMixin, mixins.DestroyModelMixin):
    """Korrespondenz je Patient: ``?patient=ID&status=…``. Gelöscht werden nur Entwürfe."""

    model = Schreiben
    serializer_class = SchreibenSerializer
    filterset_fields = ["patient", "status"]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().select_related("erstellt_von", "freigegeben_von", "versendet_von", "termin",
                                                     "dokument")

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(erstellt_von=self.request.user)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        if not serializer.instance.ist_entwurf:
            raise PermissionError("Freigegebene Schreiben sind unveränderlich. Bitte als neuen Entwurf kopieren.")
        serializer.save()

    def perform_destroy(self, instance):
        self.pruefe_patient(instance.patient)
        if not instance.ist_entwurf:
            raise PermissionError("Nur Entwürfe können gelöscht werden.")
        instance._history_user = self.request.user
        nummer, titel = instance.pk, instance.titel
        instance.delete()
        protokolliere(SystemEreignis.Art.KORRESPONDENZ, self.request, objekt=f"Schreiben {nummer}",
                      aktion="Entwurf gelöscht", titel=titel, patient=instance.patient.nummer,
                      patient_id=instance.patient_id)

    # ---------------------------------------------------------------- PDF
    def _pdf_antwort(self, pdf, schreiben):
        from vorlagen.api import pdf_antwort

        return pdf_antwort(pdf, schreiben.dateiname)

    @action(detail=False, methods=["post"])
    def vorschau(self, request):
        """PDF eines noch nicht gespeicherten Schreibens (wie „Anlegen“), mit Wasserzeichen ENTWURF."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        daten = {k: v for k, v in serializer.validated_data.items()}
        schreiben = Schreiben(**daten, erstellt_von=request.user)
        pdf, _, _ = schreiben.erzeuge_pdf(wasserzeichen="ENTWURF")
        return self._pdf_antwort(pdf, schreiben)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Entwurf: Vorschau mit der aktiven Vorlage; freigegeben/versendet: die bei der Freigabe gespeicherte PDF."""
        schreiben = self.get_object()
        if schreiben.ist_entwurf:
            try:
                schreiben.pruefe_vorlage()
            except DjangoValidationError as e:
                return Response(e.message_dict, status=status.HTTP_400_BAD_REQUEST)
            pdf, _, _ = schreiben.erzeuge_pdf(wasserzeichen="ENTWURF")
            return self._pdf_antwort(pdf, schreiben)
        dok = schreiben.dokument
        if dok is None or not dok.pfad.is_file():
            return Response({"fehler": "Die PDF dieses Schreibens gibt es nicht mehr."}, status=status.HTTP_404_NOT_FOUND)
        pdf = dok.pfad.read_bytes()
        if hashlib.sha256(pdf).hexdigest() != schreiben.pdf_sha256:
            return Response({"fehler": "Die Prüfsumme der PDF stimmt nicht. Bitte die Administration informieren."},
                            status=status.HTTP_409_CONFLICT)
        protokolliere(SystemEreignis.Art.EXPORT, request, objekt=akte_text(schreiben.patient), was="Schreiben",
                      schreiben=schreiben.pk, patient_id=schreiben.patient_id)
        return self._pdf_antwort(pdf, schreiben)

    # ---------------------------------------------------------------- Status
    @action(detail=True, methods=["post"], permission_classes=[SchreibenFreigabeRecht])
    @transaction.atomic
    def freigeben(self, request, pk=None):
        schreiben = self.get_object()
        self.pruefe_patient(schreiben.patient)
        schreiben._history_user = request.user
        schreiben.freigeben(request.user)
        protokolliere(SystemEreignis.Art.KORRESPONDENZ, request, objekt=f"Schreiben {schreiben.pk}",
                      aktion="freigegeben", titel=schreiben.titel, vorlage=schreiben.vorlage_name,
                      patient=schreiben.patient.nummer, patient_id=schreiben.patient_id, sha256=schreiben.pdf_sha256)
        return Response(self.get_serializer(schreiben).data)

    @action(detail=True, methods=["post"])
    def versendet(self, request, pk=None):
        schreiben = self.get_object()
        self.pruefe_patient(schreiben.patient)
        d = request.data
        am = None
        if d.get("versendet_am"):
            try:
                am = serializers.DateField().to_internal_value(d["versendet_am"])
            except serializers.ValidationError:
                return Response({"versendet_am": "Bitte als Datum angeben."}, status=status.HTTP_400_BAD_REQUEST)
        schreiben._history_user = request.user
        schreiben.als_versendet(request.user, am, str(d.get("versandweg") or ""), str(d.get("versand_notiz") or "").strip())
        protokolliere(SystemEreignis.Art.KORRESPONDENZ, request, objekt=f"Schreiben {schreiben.pk}",
                      aktion="versendet", titel=schreiben.titel, weg=schreiben.get_versandweg_display(),
                      am=schreiben.versendet_am.isoformat(), patient=schreiben.patient.nummer,
                      patient_id=schreiben.patient_id)
        return Response(self.get_serializer(schreiben).data)

    @action(detail=True, methods=["post"])
    def kopieren(self, request, pk=None):
        """Korrektur eines freigegebenen Schreibens: neuer Entwurf mit denselben Angaben."""
        schreiben = self.get_object()
        self.pruefe_patient(schreiben.patient)
        neu = schreiben.kopie(request.user)
        return Response(self.get_serializer(neu).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def verlauf(self, request, pk=None):
        """Alle Fassungen dieses Schreibens, neueste zuerst (Änderungsverlauf)."""
        schreiben = self.get_object()
        namen = {f.name: str(f.verbose_name) for f in Schreiben._meta.get_fields() if hasattr(f, "verbose_name")}
        eintraege = []
        for h in schreiben.history.select_related("history_user").order_by("-history_date", "-history_id"):
            aenderungen = []
            vorher = h.prev_record if h.history_type == "~" else None
            if vorher is not None:
                for c in h.diff_against(vorher, excluded_fields=["bloecke"]).changes:
                    aenderungen.append({"feld": c.field, "name": namen.get(c.field, c.field),
                                        "alt": _kurz(c.old), "neu": _kurz(c.new)})
            eintraege.append({"zeitpunkt": h.history_date, "person": benutzername(h.history_user),
                              "aktion": _aktion(h, vorher), "status": h.status, "aenderungen": aenderungen})
        return Response(eintraege)


def _kurz(wert, laenge=200):
    text = "" if wert is None else str(wert)
    return text if len(text) <= laenge else text[:laenge] + " …"


def _aktion(h, vorher) -> str:
    if h.history_type == "+":
        return "als Kopie angelegt" if h.kopie_von else "angelegt"
    if h.history_type == "-":
        return "gelöscht"
    if vorher is not None and vorher.status != h.status:
        return {"freigegeben": "freigegeben", "versendet": "als versendet vermerkt"}.get(h.status, "geändert")
    return "geändert"

