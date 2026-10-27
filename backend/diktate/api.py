"""API der Diktate.

- ``POST diktate/`` (multipart: patient, bericht?, zweck, wann, uebergabe, dauer_s, datei) – Recht „Diktieren“
- ``GET diktate/?patient=&bericht=&zweck=`` – lesen mit „Akten lesen“; ``GET diktate/offen/`` – Liste fürs Sekretariat
- ``GET diktate/{id}/audio/`` – Aufnahme zum Nachhören (bis zur Freigabe)
- ``POST diktate/{id}/uebernommen/`` – Text ist im Bericht bzw. im Kommentar; beim Kommentar wird die Aufnahme gelöscht
- ``GET diktate/eingang/`` – noch keinem Patienten zugeordnete Diktate (eigene; mit „Einträge erfassen“ alle);
  ``POST diktate/{id}/zuordnen/`` (patient, bericht? | art?, titel?) – Patient und Bericht (neuer Entwurf) setzen
- ``POST diktate/{id}/erneut/`` – nach einem Fehler noch einmal abschreiben; ``DELETE diktate/{id}/`` – verwerfen
- ``GET|PUT diktate/begriffe/`` – eigene Fachbegriffe; ``GET diktate/stand/`` – Dienst bereit, wartende Diktate
Übernehmen, erneut abschreiben und verwerfen darf, wer Einträge erfassen darf (das Sekretariat).
"""
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import mixins, serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import Angemeldet, recht
from audit.models import SystemEreignis, protokolliere
from accounts.rechte import sieht_testdaten
from epm.api_basis import benutzername, patienten_fuer
from patienten.api import AktenEintragViewSet

from . import abschrift, dienst
from .models import Begriffsliste, Diktat

DiktierRecht = recht("diktieren")


class DiktatSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    erstellt_von_name = serializers.SerializerMethodField()
    uebernommen_von_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    patient_nummer = serializers.IntegerField(source="patient.nummer", read_only=True, default=None)
    bericht_titel = serializers.CharField(source="bericht.titel", read_only=True, default=None)
    bericht_status = serializers.CharField(source="bericht.status", read_only=True, default=None)
    audio = serializers.SerializerMethodField()
    unsicher = serializers.SerializerMethodField()
    datei = serializers.FileField(write_only=True)

    class Meta:
        model = Diktat
        fields = ["id", "patient", "patient_name", "patient_nummer", "bericht", "bericht_titel", "bericht_status",
                  "zweck", "status", "status_name", "wann", "uebergabe", "dauer_s", "text", "woerter", "unsicher",
                  "modell", "rechenzeit_s", "schritt", "fehler", "erstellt_am", "erstellt_von_name",
                  "abgeschrieben_am", "uebernommen_am", "uebernommen_von_name", "audio", "datei"]
        read_only_fields = ["status", "text", "woerter", "modell", "rechenzeit_s", "schritt", "fehler", "erstellt_am",
                            "abgeschrieben_am", "uebernommen_am"]

    def to_representation(self, obj):
        daten = super().to_representation(obj)
        if self.context.get("kurz"):  # Liste fürs Sekretariat: ohne Text und Wörter
            daten.pop("woerter", None)
            daten.pop("text", None)
        return daten

    def get_erstellt_von_name(self, obj):
        return benutzername(obj.erstellt_von)

    def get_uebernommen_von_name(self, obj):
        return benutzername(obj.uebernommen_von)

    def get_patient_name(self, obj):
        return f"{obj.patient.nachname}, {obj.patient.vorname}" if obj.patient_id else None

    def get_audio(self, obj):
        return bool(obj.datei)

    def get_unsicher(self, obj):
        return abschrift.unsichere(obj.woerter or [])

    def validate_dauer_s(self, wert):
        if wert < 0 or wert > dienst.MAX_DAUER_S:
            raise serializers.ValidationError("Ein Diktat darf höchstens eine Stunde lang sein.")
        return wert

    def validate(self, daten):
        bericht, patient = daten.get("bericht"), daten.get("patient")
        if patient is None:
            # ohne Patient (27.10.2026): nur fürs spätere Zuordnen zu einem Bericht
            if bericht is not None or daten.get("zweck", Diktat.Zweck.BERICHT) != Diktat.Zweck.BERICHT:
                raise serializers.ValidationError({"patient": "Bitte den Patienten angeben."})
            return daten
        if daten.get("zweck", Diktat.Zweck.BERICHT) == Diktat.Zweck.BERICHT:
            if bericht is None:
                raise serializers.ValidationError({"bericht": "Bitte den Bericht angeben."})
            if bericht.patient_id != patient.pk:
                raise serializers.ValidationError({"bericht": "Der Bericht gehört zu einem anderen Patienten."})
            if not bericht.ist_entwurf:
                raise serializers.ValidationError({"bericht": "Der Bericht ist schon freigegeben."})
        elif bericht is not None:
            raise serializers.ValidationError({"bericht": "Ein Kommentar gehört zu keinem Bericht."})
        return daten


class DiktatViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    mixins.DestroyModelMixin):
    model = Diktat
    serializer_class = DiktatSerializer
    filterset_fields = ["patient", "bericht", "zweck", "status"]
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in ("create", "begriffe"):
            return [DiktierRecht()]
        if self.action == "stand":
            return [Angemeldet()]
        return super().get_permissions()

    def get_queryset(self):
        u = self.request.user
        ohne = Q(patient__isnull=True)
        if not u.hat_recht("eintraege_erfassen"):
            ohne &= Q(erstellt_von=u)  # nicht zugeordnet: die eigenen; das Sekretariat sieht alle
        elif getattr(u, "ist_test", False):
            ohne &= Q(erstellt_von__ist_test=True)
        elif not sieht_testdaten(u):
            ohne &= Q(erstellt_von__ist_test=False)
        return (Diktat.objects.filter(Q(patient__in=patienten_fuer(u)) | ohne)
                .select_related("patient", "bericht", "erstellt_von", "uebernommen_von"))

    def _pruefe(self, d: Diktat):
        """Ändern: mit Patient nach dessen Akte, ohne Patient wer es aufgenommen hat oder das Sekretariat."""
        if d.patient_id:
            self.pruefe_patient(d.patient)
        elif d.erstellt_von_id != self.request.user.pk and not self.request.user.hat_recht("eintraege_erfassen"):
            raise serializers.ValidationError({"fehler": "Dafür fehlt das Recht."})

    def perform_create(self, serializer):
        if serializer.validated_data.get("patient") is not None:
            self.pruefe_patient(serializer.validated_data["patient"])
        datei = serializer.validated_data.pop("datei")
        diktat = Diktat(**serializer.validated_data, erstellt_von=self.request.user)
        try:
            dienst.speichern(diktat, datei)
        except ValueError as e:
            raise serializers.ValidationError({"datei": str(e)}) from e
        serializer.instance = diktat
        protokolliere(SystemEreignis.Art.DIKTAT, self.request, objekt=f"Diktat {diktat.pk}", aktion="aufgenommen",
                      patient=diktat.patient.nummer if diktat.patient_id else None, dauer_s=round(diktat.dauer_s), wann=diktat.wann,
                      uebergabe=diktat.uebergabe)

    def perform_destroy(self, instance):
        self._pruefe(instance)
        protokolliere(SystemEreignis.Art.DIKTAT, self.request, objekt=f"Diktat {instance.pk}", aktion="verworfen",
                      patient=instance.patient.nummer if instance.patient_id else None)
        instance.delete()

    @action(detail=False)
    def offen(self, request):
        """Fürs Sekretariat: abgegebene Diktate, deren Text noch nicht im Bericht ist."""
        qs = (self.get_queryset().filter(uebergabe=Diktat.Uebergabe.SEKRETARIAT, uebernommen_am__isnull=True,
                                         zweck=Diktat.Zweck.BERICHT, bericht__status="entwurf")
              .order_by("erstellt_am", "id"))
        return Response(DiktatSerializer(qs, many=True, context={**self.get_serializer_context(), "kurz": True}).data)

    @action(detail=False)
    def eingang(self, request):
        """Noch keinem Patienten zugeordnete Diktate, neueste zuerst (wie der Eingang der Scans)."""
        qs = self.get_queryset().filter(patient__isnull=True).order_by("-erstellt_am", "-id")
        return Response(DiktatSerializer(qs, many=True, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def zuordnen(self, request, pk=None):
        """Einem Patienten zuordnen: an einen Bericht-Entwurf (``bericht``) oder an einen neuen (``art``, ``titel``)."""
        from berichte.api import BerichtSerializer
        from berichte.models import Bericht

        d = self.get_object()
        self._pruefe(d)
        if d.patient_id:
            raise serializers.ValidationError({"fehler": "Das Diktat ist schon zugeordnet."})
        pid = str(request.data.get("patient") or "")
        patient = patienten_fuer(request.user).filter(pk=pid).first() if pid.isdigit() else None
        if patient is None:
            raise serializers.ValidationError({"patient": "Bitte den Patienten wählen."})
        self.pruefe_patient(patient)
        if d.erstellt_von is not None and d.erstellt_von.ist_test and not patient.ist_test:
            raise serializers.ValidationError({"patient": "Diktate eines Testzugangs lassen sich nur Testpatienten zuordnen."})
        bid = str(request.data.get("bericht") or "")
        if bid:
            bericht = Bericht.objects.filter(pk=bid if bid.isdigit() else None, patient=patient).first()
            if bericht is None:
                raise serializers.ValidationError({"bericht": "Der Bericht gehört zu einem anderen Patienten."})
            if not bericht.ist_entwurf:
                raise serializers.ValidationError({"bericht": "Der Bericht ist schon freigegeben."})
        else:
            titel = str(request.data.get("titel") or "").strip()
            art = request.data.get("art") or None
            if not titel and art:
                from stammdaten.models import Auswahlwert

                titel = Auswahlwert.objects.filter(pk=art).values_list("wert", flat=True).first() or ""
            s = BerichtSerializer(data={"patient": patient.pk, "art": art, "datum": timezone.localdate().isoformat(),
                                        "titel": titel or f"Diktat vom {timezone.localtime(d.erstellt_am):%d.%m.%Y}",
                                        "empfaenger": "", "inhalt": ""}, context=self.get_serializer_context())
            s.is_valid(raise_exception=True)
            bericht = s.save(erstellt_von=request.user)
        Diktat.objects.filter(pk=d.pk).update(patient=patient, bericht=bericht)
        protokolliere(SystemEreignis.Art.DIKTAT, request, objekt=f"Diktat {d.pk}", aktion="zugeordnet",
                      patient=patient.nummer, bericht=bericht.pk)
        d.refresh_from_db()
        return Response(self.get_serializer(d).data)

    @action(detail=True)
    def audio(self, request, pk=None):
        d = self.get_object()
        if d.pfad is None or not d.pfad.is_file():
            return Response({"fehler": "Die Aufnahme ist nicht mehr vorhanden."}, status=status.HTTP_404_NOT_FOUND)
        antwort = FileResponse(open(d.pfad, "rb"), content_type=d.mime or "application/octet-stream")
        antwort["Cache-Control"] = "no-store"
        return antwort

    @action(detail=True, methods=["post"])
    def uebernommen(self, request, pk=None):
        d = self.get_object()
        if not d.patient_id:
            raise serializers.ValidationError({"fehler": "Bitte das Diktat erst einem Patienten zuordnen."})
        self.pruefe_patient(d.patient)
        if d.status != Diktat.Status.FERTIG:
            raise serializers.ValidationError({"fehler": "Das Diktat ist noch nicht abgeschrieben."})
        Diktat.objects.filter(pk=d.pk).update(uebernommen_am=d.uebernommen_am or timezone.now(),
                                              uebernommen_von=d.uebernommen_von or request.user)
        if d.zweck == Diktat.Zweck.PLAN:
            dienst.aufnahme_loeschen(d, text_auch=True)
        protokolliere(SystemEreignis.Art.DIKTAT, request, objekt=f"Diktat {d.pk}", aktion="uebernommen",
                      patient=d.patient.nummer)
        d.refresh_from_db()
        return Response(self.get_serializer(d).data)

    @action(detail=True, methods=["post"])
    def erneut(self, request, pk=None):
        d = self.get_object()
        self._pruefe(d)
        if d.status != Diktat.Status.FEHLER or not d.datei:
            raise serializers.ValidationError({"fehler": "Nur ein fehlgeschlagenes Diktat mit Aufnahme lässt sich "
                                                         "erneut abschreiben."})
        Diktat.objects.filter(pk=d.pk).update(status=Diktat.Status.WARTET, fehler="", versuche=0,
                                              wann=Diktat.Wann.SOFORT, schritt="")
        d.refresh_from_db()
        return Response(self.get_serializer(d).data)

    @action(detail=False, methods=["get", "put"])
    def begriffe(self, request):
        liste, _ = Begriffsliste.objects.get_or_create(benutzer=request.user)
        if request.method == "PUT":
            text = str(request.data.get("begriffe", ""))[:5000]
            liste.begriffe = text
            liste.save(update_fields=["begriffe", "geaendert_am"])
        return Response({"begriffe": liste.begriffe})

    @action(detail=False)
    def stand(self, request):
        aus = dienst.stand()
        if request.user.hat_recht("eintraege_erfassen"):
            aus["offen"] = self.get_queryset().filter(uebergabe=Diktat.Uebergabe.SEKRETARIAT,
                                                      uebernommen_am__isnull=True, zweck=Diktat.Zweck.BERICHT,
                                                      bericht__status="entwurf").count()
        return Response(aus)
