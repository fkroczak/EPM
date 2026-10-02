"""API der Patientenakte."""
import hashlib
import mimetypes
import os
import tempfile
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F, Max, Q
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.models import Rolle
from accounts.permissions import (AbschlussRecht, AktenRecht, EintragRecht, LoeschenRecht, UmhaengenRecht,
                                  WiederOeffnenRecht, recht)
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import (ModelClean, RichText, benutzername, legt_testpatienten_an, patienten_fuer,
                            patienten_mit_eingeschraenkten, pruefe_schreibbereich)
from stammdaten.models import Auswahlwert

from audit.bereinigung import akte_text
from stammdaten.models import Arzt

from .datenschutz import DatenschutzAktionen
from .kennzahlen import (abschluss_pruefen, kennzahlen, kontakt_filter, ohne_pflicht_erklaerungen, pruefliste,
                         schnellfilter, zaehler)
from .loeschung import PLATZHALTER, schwaerze_dokument, trage_ein
from .models import (Bezugsperson, Datenschutzanfrage, Dokument, DokumentVorgang, Erklaerung, Gewichtsmessung,
                     Kontakt, Patient, PatientArzt, Termin, dokument_pfad)


# ================================================================= Patient
class PatientListSerializer(serializers.ModelSerializer):
    versorger_name = serializers.CharField(source="versorger.name", read_only=True, default=None)
    ansprechpartner_name = serializers.CharField(source="ansprechpartner.name", read_only=True, default=None)
    katheter_name = serializers.CharField(source="katheter.wert", read_only=True, default=None)
    ist_abgeschlossen = serializers.BooleanField(read_only=True)
    ist_eingeschraenkt = serializers.BooleanField(read_only=True)
    alter = serializers.SerializerMethodField()
    kennzahlen = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "id", "nummer", "nachname", "vorname", "geburtsdatum", "alter", "ort", "katheter", "katheter_name",
            "versorger", "versorger_name", "ansprechpartner", "ansprechpartner_name", "nickelallergie",
            "kein_katheter", "kein_versorger",
            "ist_abgeschlossen", "abgeschlossen_am", "abschluss_anlass", "ist_test", "ist_eingeschraenkt",
            "kennzahlen",
        ]

    def get_alter(self, obj):
        heute = timezone.localdate()
        g = obj.geburtsdatum
        return heute.year - g.year - ((heute.month, heute.day) < (g.month, g.day))

    def get_kennzahlen(self, obj):
        """Gewicht + Trend, letzter Kontakt, Hinweise (nur wenn die Ansicht sie berechnet hat)."""
        return self.context.get("kennzahlen", {}).get(obj.id)


class PatientSerializer(ModelClean, serializers.ModelSerializer):
    diagnose = RichText()
    therapie = RichText()
    empfehlung = RichText()
    bemerkung = RichText()
    ist_abgeschlossen = serializers.BooleanField(read_only=True)
    ist_eingeschraenkt = serializers.BooleanField(read_only=True)
    aufbewahrung = serializers.SerializerMethodField()
    kopf = serializers.SerializerMethodField()
    angelegt_von_name = serializers.SerializerMethodField()
    # Nur beim Anlegen: „Gewicht bei Aufnahme“ (Entwurf 12) wird als erste Messung gespeichert
    aufnahme_gewicht_kg = serializers.DecimalField(max_digits=5, decimal_places=1, required=False,
                                                   allow_null=True, write_only=True)
    aufnahme_gemessen_am = serializers.DateField(required=False, write_only=True)
    aufnahme_quelle = serializers.ChoiceField(Gewichtsmessung.Quelle.choices, required=False, write_only=True)
    # Nur beim Anlegen: Hausarzt aus der Ärzteliste (wird als Zuordnung „Hausarzt“ gespeichert)
    aufnahme_hausarzt = serializers.PrimaryKeyRelatedField(queryset=Arzt.objects.all(), required=False,
                                                           allow_null=True, write_only=True)

    class Meta:
        model = Patient
        fields = [
            "id", "nummer", "nachname", "vorname", "geburtsdatum", "geschlecht",
            "strasse", "plz", "ort", "telefon", "telefon2", "email", "krankenkasse", "hausarzt",
            "ueberweisung_durch", "groesse_cm", "katheter", "versorger", "ansprechpartner", "nickelallergie",
            "kein_katheter", "kein_versorger",
            "diagnose", "therapie", "empfehlung", "bemerkung",
            "abgeschlossen_am", "abschluss_anlass", "abschluss_notiz", "ist_abgeschlossen", "ist_test",
            "ist_eingeschraenkt", "eingeschraenkt_am", "aufbewahrung",
            "angelegt_am", "angelegt_von_name", "geaendert_am", "kopf",
            "aufnahme_gewicht_kg", "aufnahme_gemessen_am", "aufnahme_quelle", "aufnahme_hausarzt",
        ]
        read_only_fields = ["abgeschlossen_am", "abschluss_anlass", "abschluss_notiz", "angelegt_am", "geaendert_am",
                            "eingeschraenkt_am"]

    def get_angelegt_von_name(self, obj):
        return benutzername(obj.angelegt_von)

    def get_aufbewahrung(self, obj):
        """Aufbewahrungsfrist (nur bei abgeschlossenen Akten): bis wann, verlängert, abgelaufen."""
        if not obj.pk or not obj.ist_abgeschlossen or (self.context.get("view") and self.context["view"].action == "list"):
            return None
        return obj.aufbewahrung()

    def get_kopf(self, obj):
        """Kerndaten für den Patientenkopf (nur in der Einzelansicht)."""
        if self.context.get("view") and self.context["view"].action == "list":
            return None
        from infusionen.models import Infusionsplan

        letzte = obj.letzte_messung()
        plan = obj.infusionsplaene.filter(status=Infusionsplan.Status.AKTUELL).first()
        termin = obj.termine.filter(erledigt_am__isnull=True, faellig_am__gte=timezone.localdate()).first()
        return {
            "gewicht": {"kg": letzte.gewicht_kg, "am": letzte.gemessen_am} if letzte else None,
            "gewichtstrend": obj.gewichtstrend(),
            "bmi": obj.bmi,
            "katheter": obj.katheter.wert if obj.katheter_id else ("kein" if obj.kein_katheter else None),
            "versorger": obj.versorger.name if obj.versorger_id else ("kein" if obj.kein_versorger else None),
            "kein_katheter": obj.kein_katheter,
            "kein_versorger": obj.kein_versorger,
            # Wem darf Auskunft gegeben werden (Schweigepflichtentbindung), für Telefonate sofort sichtbar
            "auskunft": [
                {"id": b.id, "name": b.name, "beziehung": b.beziehung.wert if b.beziehung_id else None,
                 "telefon": b.telefon or b.mobil}
                for b in obj.bezugspersonen.filter(aktiv=True, auskunft_erlaubt=True).select_related("beziehung")
            ],
            "hausarzt": next((
                {"id": z.arzt_id, "name": z.arzt.name, "praxis": z.arzt.praxis, "telefon": z.arzt.telefon}
                for z in obj.aerzte.filter(aktiv=True, rolle=PatientArzt.Rolle.HAUSARZT).select_related("arzt")
            ), None),
            "ansprechpartner": obj.ansprechpartner.name if obj.ansprechpartner_id else None,
            "ansprechpartner_telefon": (obj.ansprechpartner.telefon or obj.ansprechpartner.mobil)
            if obj.ansprechpartner_id else None,
            "nickelallergie": obj.nickelallergie,
            # Erklärungen zum Datenschutz, nachgehalten wie die Nickelallergie (nicht erfasst / liegt vor / widerrufen)
            "erklaerungen": _erklaerungen_kopf(obj),
            "datenschutz_anfragen": obj.datenschutzanfragen.filter(erledigt_am__isnull=True).count(),
            "aktueller_plan": {"id": plan.id, "gueltig_ab": plan.gueltig_ab, "kcal": plan.kcal,
                               "laufzeit_h": plan.laufzeit_h} if plan else None,
            "naechster_termin": (
                {"id": termin.id, "art": termin.art, "titel": termin.titel, "faellig_am": termin.faellig_am,
                 "uhrzeit": termin.uhrzeit, "ort": termin.ort.wert if termin.ort_id else None,
                 "bei": termin.bei} if termin else None
            ),
            "versionen": {feld: _versionskopf(obj, feld) for feld in TEXTFELDER},
            # Schnellerfassung (S02): letzter Kontakt im Kontextkasten; Merkliste (S05): Stern im Aktenkopf
            "letzter_kontakt": obj.kontakte.filter(storniert_am__isnull=True).aggregate(z=Max("zeitpunkt"))["z"],
            "gemerkt": _gemerkt(self.context.get("request"), obj),
            "zaehler": {
                "kontakte": obj.kontakte.count(),
                "gewichte": obj.gewichte.count(),
                "dokumente": obj.dokumente.filter(ausgeblendet=False).count(),
                "termine_offen": obj.termine.filter(erledigt_am__isnull=True).count(),
                "infusionsplaene": obj.infusionsplaene.count(),
                "bezugspersonen": obj.bezugspersonen.filter(aktiv=True).count(),
                "aerzte": obj.aerzte.filter(aktiv=True).count(),
                "erklaerungen": obj.erklaerungen.count(),
            },
        }

    def validate(self, attrs):
        aufnahme = {k: attrs.pop(k) for k in ("aufnahme_gewicht_kg", "aufnahme_gemessen_am", "aufnahme_quelle")
                    if k in attrs}
        if aufnahme and self.instance is not None:
            raise serializers.ValidationError({"aufnahme_gewicht_kg": "Nur beim Anlegen möglich."})
        hausarzt = attrs.pop("aufnahme_hausarzt", None)
        if hausarzt is not None:
            if self.instance is not None:
                raise serializers.ValidationError({"aufnahme_hausarzt": "Nur beim Anlegen möglich; danach unter „Ärzte“."})
            if not hausarzt.aktiv:
                raise serializers.ValidationError({"aufnahme_hausarzt": "Dieser Arzt ist deaktiviert."})
            self.aufnahme_hausarzt = hausarzt
        # Wer einen Katheter bzw. Versorger wählt, hebt „kein“ auf (und umgekehrt leert „kein“ die Auswahl nicht stillschweigend)
        if attrs.get("katheter") is not None and "kein_katheter" not in attrs:
            attrs["kein_katheter"] = False
        if attrs.get("versorger") is not None and "kein_versorger" not in attrs:
            attrs["kein_versorger"] = False
        if aufnahme.get("aufnahme_gewicht_kg") is not None:
            messung = Gewichtsmessung(
                gewicht_kg=aufnahme["aufnahme_gewicht_kg"],
                gemessen_am=aufnahme.get("aufnahme_gemessen_am") or timezone.localdate(),
                quelle=aufnahme.get("aufnahme_quelle") or Gewichtsmessung.Quelle.TELEFONISCH,
            )
            try:
                messung.clean()
            except DjangoValidationError as fehler:
                raise serializers.ValidationError({"aufnahme_gewicht_kg": fehler.messages})
            self.aufnahme_messung = messung
        attrs = super().validate(attrs)
        for feld, liste in (("katheter", Auswahlwert.Liste.KATHETER),):
            wert = attrs.get(feld)
            if wert is not None and wert.liste != liste:
                raise serializers.ValidationError({feld: "Ungültiger Wert für diese Liste."})
        return attrs


def _gemerkt(request, patient) -> bool:
    from .models import Merkeintrag

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return False
    return Merkeintrag.objects.filter(benutzer=user, patient=patient, art=Merkeintrag.Art.MERKLISTE).exists()


def _erklaerungen_kopf(patient) -> dict:
    """{"stand": {art: {status, am, id}}, "pflicht": [...], "fehlt": [...]} für den Patientenkopf."""
    from stammdaten.models import Einstellungen

    from .datenschutz import stand_daten

    stand = stand_daten(patient)
    pflicht = Einstellungen.aktuell().pflicht_erklaerungen
    return {"stand": stand, "pflicht": pflicht,
            "fehlt": [art for art in pflicht if stand[art]["status"] != "liegt_vor"]}


def _datum(text: str):
    """„14.03.1968“ oder „1968-03-14“ als Datum, sonst None."""
    from datetime import datetime

    for muster in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(text, muster).date()
        except ValueError:
            continue
    return None


TEXTFELDER = ("diagnose", "therapie", "empfehlung")


def feldversionen(patient, feld: str) -> list:
    """Fassungen eines Textfelds (neueste zuerst): Version, Zeitpunkt, Person, Text."""
    fassungen = []
    vorher = None
    for h in patient.history.order_by("history_date", "history_id").select_related("history_user"):
        text = getattr(h, feld)
        if text != vorher and (text or vorher is not None):
            fassungen.append({"version": len(fassungen) + 1, "zeitpunkt": h.history_date,
                              "person": benutzername(h.history_user), "text": text})
        vorher = text
    return list(reversed(fassungen))


def _versionskopf(patient, feld):
    """„Version 12 · geändert 12.08.2026, 15:12 von Dr. M. Berger“"""
    fassungen = feldversionen(patient, feld)
    if not fassungen:
        return None
    return {"version": fassungen[0]["version"], "zeitpunkt": fassungen[0]["zeitpunkt"], "person": fassungen[0]["person"]}


class PatientFilter(filters.FilterSet):
    status = filters.ChoiceFilter(
        choices=[("in_betreuung", "In Betreuung"), ("abgeschlossen", "Abgeschlossen")], method="filter_status"
    )
    test = filters.ChoiceFilter(choices=[("nur", "nur Testpatienten"), ("ohne", "ohne Testpatienten")],
                                method="filter_test")
    suche = filters.CharFilter(method="filter_suche", label="Name, Vorname, Ort, Patientennummer oder Geburtsdatum")
    pruefen = filters.ChoiceFilter(
        choices=[("altdokumente", "Altdokumente prüfen"), ("nickelallergie", "Nickelallergie nicht erfasst"),
                 ("kein_versorger", "Versorger nicht erfasst"),
                 ("kein_kontakt", "Kontakt fällig (bald fällig und überfällig)"),
                 ("kontakt_bald", "Kontakt bald fällig"), ("kontakt_ueberfaellig", "Kontakt überfällig"),
                 ("wiedereinbestellung", "Wiedereinbestellung fällig (Kontakt fällig, kein Termin geplant)"),
                 ("erklaerungen", "Erklärungen zum Datenschutz fehlen"),
                 ("abschluss_pruefen", "Abschluss prüfen (lange kein Kontakt)")],
        method="filter_pruefen",
    )

    class Meta:
        model = Patient
        fields = ["versorger", "ansprechpartner", "katheter", "nickelallergie"]

    def filter_pruefen(self, qs, name, wert):
        from .models import Dokument

        if wert == "altdokumente":
            return qs.filter(id__in=Dokument.objects.filter(typ_geprueft=False, ausgeblendet=False).values("patient_id"))
        if wert == "nickelallergie":
            return qs.filter(nickelallergie=Patient.Nickelallergie.UNBEKANNT)
        if wert == "kein_versorger":
            # „kein Versorger“ (bewusst keiner) ist kein offener Punkt
            return qs.filter(versorger__isnull=True, kein_versorger=False)
        if wert in ("kein_kontakt", "kontakt_bald", "kontakt_ueberfaellig", "wiedereinbestellung"):
            return kontakt_filter(qs, wert)  # S04: zwei Stufen „bald fällig“ und „überfällig“
        if wert == "erklaerungen":
            return qs.filter(id__in=ohne_pflicht_erklaerungen(qs.order_by()))
        if wert == "abschluss_pruefen":
            return qs.filter(id__in=abschluss_pruefen(Patient.objects.all()).values("id"))
        return qs

    def filter_status(self, qs, name, wert):
        return qs.filter(abgeschlossen_am__isnull=(wert == "in_betreuung"))

    def filter_suche(self, qs, name, wert):
        for wort in wert.split():
            datum = _datum(wort)
            if datum:
                qs = qs.filter(geburtsdatum=datum)
            elif wort.isdigit():
                qs = qs.filter(nummer=int(wort))
            else:
                qs = qs.filter(Q(nachname__icontains=wort) | Q(vorname__icontains=wort) | Q(ort__icontains=wort))
        return qs

    def filter_test(self, qs, name, wert):
        return qs.filter(ist_test=(wert == "nur"))


class PatientViewSet(DatenschutzAktionen, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                     mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """
    Liste: ``?status=in_betreuung|abgeschlossen``, ``schnellfilter=hinweise|gewichtsverlust|termin_woche``,
    ``suche``, ``versorger``, ``ansprechpartner``, ``katheter``, ``nickelallergie``, ``pruefen``,
    ``ordering=letzter_kontakt|-letzter_kontakt|nachname|nummer|geburtsdatum`` (Standard: letzter Kontakt, neueste zuerst).
    """

    permission_classes = [AktenRecht]
    filterset_class = PatientFilter
    ordering_fields = ["nachname", "nummer", "geburtsdatum", "geaendert_am", "letzter_kontakt", "abgeschlossen_am"]

    def get_queryset(self):
        qs = patienten_fuer(self.request.user).select_related("versorger", "ansprechpartner", "katheter",
                                                              "angelegt_von")
        if self.action == "list":
            qs = qs.annotate(letzter_kontakt=Max("kontakte__zeitpunkt",
                                                 filter=Q(kontakte__storniert_am__isnull=True)))
            if not self.request.query_params.get("ordering"):
                qs = qs.order_by(F("letzter_kontakt").desc(nulls_last=True), "nachname", "vorname")
        return qs

    def get_serializer_class(self):
        return PatientListSerializer if self.action == "list" else PatientSerializer

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        ordnung = request.query_params.get("ordering", "")
        if ordnung.lstrip("-") in ("letzter_kontakt", "abgeschlossen_am"):
            # Akten ohne Kontakt bzw. Abschluss stehen immer am Ende, bei gleichem Wert nach Name
            feld = F(ordnung.lstrip("-"))
            qs = qs.order_by(feld.desc(nulls_last=True) if ordnung.startswith("-") else feld.asc(nulls_last=True),
                             "nachname", "vorname")
        art = request.query_params.get("schnellfilter")
        if art in ("hinweise", "gewichtsverlust", "termin_woche"):
            qs = qs.filter(id__in=schnellfilter(qs, art))
        seite = self.paginate_queryset(qs)
        eintraege = seite if seite is not None else list(qs)
        context = self.get_serializer_context()
        context["kennzahlen"] = kennzahlen(eintraege, liste=True)
        daten = PatientListSerializer(eintraege, many=True, context=context).data
        return self.get_paginated_response(daten) if seite is not None else Response(daten)

    @action(detail=False, methods=["get"])
    def zaehler(self, request):
        """Zahlen für „In Betreuung“, „Abgeschlossen“ und die Schnellfilter (Testpatienten zählen nicht)."""
        qs = patienten_fuer(request.user)
        if request.user.ist_test:
            return Response(zaehler(qs))
        daten = zaehler(qs.filter(ist_test=False))
        # Testpatienten zählen nicht mit, stehen aber in der Liste. Die Administration sieht ihre Anzahl
        # getrennt daneben (Festlegung 01.10.2026: nur für den Admin), alle anderen nur die echten Zahlen.
        if getattr(request.user, "rolle", None) == Rolle.ADMIN:
            test = qs.filter(ist_test=True)
            daten["testpatienten"] = {
                "in_betreuung": test.filter(abgeschlossen_am__isnull=True).count(),
                "abgeschlossen": test.filter(abgeschlossen_am__isnull=False).count(),
            }
        return Response(daten)

    @action(detail=False, methods=["get"], url_path="naechste-nummer")
    def naechste_nummer(self, request):
        """„Nr. 0300 wird automatisch vergeben“ (Entwurf 12)."""
        return Response({"nummer": Patient.naechste_nummer(legt_testpatienten_an(request.user)),
                         "testpatient": legt_testpatienten_an(request.user)})

    @transaction.atomic
    def perform_create(self, serializer):
        # Testbenutzer und Admins legen nur Testpatienten an
        patient = serializer.save(angelegt_von=self.request.user, ist_test=legt_testpatienten_an(self.request.user))
        messung = getattr(serializer, "aufnahme_messung", None)
        if messung is not None:
            messung.patient = patient
            messung.erfasst_von = self.request.user
            messung.save()
        hausarzt = getattr(serializer, "aufnahme_hausarzt", None)
        if hausarzt is not None:
            PatientArzt.objects.create(patient=patient, arzt=hausarzt, rolle=PatientArzt.Rolle.HAUSARZT,
                                       angelegt_von=self.request.user)

    @action(detail=True, methods=["get"])
    def versionen(self, request, pk=None):
        """Fassungen von Diagnose, Therapie oder Empfehlung (Entwurf 5 · „Versionen“)."""
        feld = request.query_params.get("feld")
        if feld not in TEXTFELDER:
            return Response({"feld": f"Erlaubt: {', '.join(TEXTFELDER)}."}, status=status.HTTP_400_BAD_REQUEST)
        fassungen = feldversionen(self.get_object(), feld)
        return Response({"feld": feld, "version": fassungen[0]["version"] if fassungen else 0, "fassungen": fassungen})

    def perform_update(self, serializer):
        pruefe_schreibbereich(self.request.user, serializer.instance)
        serializer.instance.pruefe_bearbeitbar()
        serializer.save()

    @action(detail=False, methods=["get"])
    def doppelte(self, request):
        """Mögliche Doppelungen vor dem Anlegen: gleiches Geburtsdatum und ähnlicher Name."""
        geb = request.query_params.get("geburtsdatum")
        nach = (request.query_params.get("nachname") or "").strip()
        vor = (request.query_params.get("vorname") or "").strip()
        if not geb:
            return Response([])
        qs = self.get_queryset().filter(geburtsdatum=geb)
        name = Q()
        if nach:
            name |= Q(nachname__istartswith=nach[:3])
        if vor:
            name |= Q(vorname__istartswith=vor[:3])
        if name:
            qs = qs.filter(name)
        return Response(PatientListSerializer(qs[:10], many=True).data)

    @action(detail=True, methods=["post"], permission_classes=[AbschlussRecht])
    def abschliessen(self, request, pk=None):
        patient = self.get_object()
        pruefe_schreibbereich(request.user, patient)
        patient.pruefe_bearbeitbar()
        anlass = request.data.get("anlass")
        if anlass not in Patient.Abschlussanlass.values:
            return Response({"anlass": "Bitte Anlass wählen."}, status=status.HTTP_400_BAD_REQUEST)
        datum = timezone.localdate()
        if request.data.get("datum"):
            try:
                datum = serializers.DateField().to_internal_value(request.data["datum"])
            except serializers.ValidationError as fehler_datum:
                return Response({"datum": fehler_datum.detail}, status=status.HTTP_400_BAD_REQUEST)
            if datum > timezone.localdate():
                return Response({"datum": ["Das Datum liegt in der Zukunft."]}, status=status.HTTP_400_BAD_REQUEST)
        patient.abgeschlossen_am = datum
        patient.abschluss_anlass = anlass
        patient.abschluss_notiz = str(request.data.get("notiz", ""))[:2000]
        patient.save()
        protokolliere(SystemEreignis.Art.AKTE_ABGESCHLOSSEN, request, objekt=patient.nummer, anlass=anlass,
                      name=f"{patient.nachname}, {patient.vorname}", patient_id=patient.id)
        patient.refresh_from_db()
        return Response(PatientSerializer(patient, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="wieder-oeffnen", permission_classes=[WiederOeffnenRecht])
    def wieder_oeffnen(self, request, pk=None):
        patient = self.get_object()
        if not patient.ist_abgeschlossen:
            return Response({"fehler": "Akte ist nicht abgeschlossen."}, status=status.HTTP_400_BAD_REQUEST)
        if patient.ist_eingeschraenkt:
            return Response({"fehler": "Die Verarbeitung dieser Akte ist eingeschränkt. Bitte zuerst die Einschränkung "
                                       "aufheben (Reiter „Datenschutz“)."}, status=status.HTTP_409_CONFLICT)
        grund = str(request.data.get("grund", "")).strip()
        if not grund:
            return Response({"grund": "Bitte einen Grund angeben."}, status=status.HTTP_400_BAD_REQUEST)
        vorher = patient.abschluss_anlass
        patient.abgeschlossen_am = None
        patient.abschluss_anlass = ""
        patient.abschluss_notiz = ""
        patient._change_reason = f"Wieder geöffnet: {grund}"[:100]  # Feld der Historie fasst 100 Zeichen
        patient.save()
        protokolliere(SystemEreignis.Art.AKTE_GEOEFFNET, request, objekt=patient.nummer, grund=grund,
                      vorheriger_anlass=vorher, name=f"{patient.nachname}, {patient.vorname}", patient_id=patient.id)
        return Response(PatientSerializer(patient, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Akte als PDF (F23): Patientendatenblatt mit der aktiven Vorlage, auch für abgeschlossene Akten."""
        from vorlagen.api import pdf_antwort
        from vorlagen.listen import akte_pdf

        patient = self.get_object()
        pdf = akte_pdf(patient)
        protokolliere(SystemEreignis.Art.EXPORT, request, objekt=akte_text(patient), was="Akte", patient_id=patient.id)
        return pdf_antwort(pdf, f"Patientendatenblatt-{patient.nummer}-{timezone.localdate():%Y-%m-%d}.pdf")

    @action(detail=True, methods=["get"], url_path="verlauf/pdf")
    def verlauf_pdf(self, request, pk=None):
        """Verlauf als PDF (F24), mit denselben Filtern wie die Ansicht."""
        from vorlagen.api import pdf_antwort
        from vorlagen.listen import BEREICHE, verlauf_pdf

        patient = self.get_object()
        bereich = request.query_params.get("bereich") or None
        person = request.query_params.get("person") or None
        eintraege = verlauf_eintraege(patient, bereich, person)
        filter_text = " · ".join(t for t in (
            f"Bereich {BEREICHE.get(bereich, bereich)}" if bereich else "",
            f"Person {eintraege[0]['person']}" if person and eintraege else "") if t)
        pdf = verlauf_pdf(patient, eintraege, filter_text)
        protokolliere(SystemEreignis.Art.EXPORT, request, objekt=akte_text(patient), was="Verlauf",
                      bereich=bereich or "", person=person or "", patient_id=patient.id)
        return pdf_antwort(pdf, f"Verlauf-{patient.nummer}-{timezone.localdate():%Y-%m-%d}.pdf")

    @action(detail=True, methods=["get"])
    def verlauf(self, request, pk=None):
        """Alle Fassungen aller Einträge dieser Akte, neueste zuerst (Entwurf 10).

        Filter ``bereich``: stammdaten, diagnose, therapie, empfehlung, gewichte, kontakte, termine,
        dokumente, infusionsplaene, bezugspersonen, aerzte, erklaerungen, datenschutz; ``person``: Benutzer-ID. Änderungen an der Akte werden nach Feld auf
        die Bereiche Stammdaten, Diagnose, Therapie und Empfehlung verteilt.
        """
        patient = self.get_object()
        bereich = request.query_params.get("bereich") or None
        person = request.query_params.get("person") or None
        return Response(verlauf_eintraege(patient, bereich, person))


def _aktion(name, h, aenderungen):
    """Fachliche Bezeichnung der Aktion („storniert“, „freigegeben“ …)."""
    felder = {a["feld"] for a in aenderungen}
    if h.history_type == "+":
        return {"dokumente": "hochgeladen"}.get(name, "angelegt")
    if h.history_type == "-":
        return "gelöscht"
    if name == "kontakte" and "storniert_am" in felder:
        return "storniert"
    if name == "termine" and "erledigt_am" in felder:
        return "erledigt"
    if name == "infusionsplaene" and "status" in felder:
        if h.status == "aktuell" and h.abgeschlossen_von_id:
            # der Mediziner hat außerhalb von EPM freigegeben; die eintragende Person hat nur abgeschlossen
            return "nach Freigabe abgeschlossen"
        return {"aktuell": "freigegeben", "abgeloest": "abgelöst"}.get(h.status, "geändert")
    if name == "bezugspersonen" and "aktiv" in felder:
        return "wieder aktuell" if h.aktiv else "nicht mehr aktuell"
    if name == "aerzte" and "aktiv" in felder:
        return "wieder zuständig" if h.aktiv else "nicht mehr zuständig"
    if name == "stammdaten" and "abgeschlossen_am" in felder:
        return "abgeschlossen" if h.abgeschlossen_am else "wieder geöffnet"
    if name == "stammdaten" and "eingeschraenkt_am" in felder:
        return "Verarbeitung eingeschränkt" if h.eingeschraenkt_am else "Einschränkung aufgehoben"
    if name == "stammdaten" and "aufbewahrung_bis" in felder:
        return "Aufbewahrung verlängert" if h.aufbewahrung_bis else "Verlängerung zurückgenommen"
    if name == "erklaerungen" and "widerrufen_am" in felder:
        return "widerrufen"
    if name == "datenschutz" and "erledigt_am" in felder:
        return "erledigt"
    if name == "datenschutz" and "frist_verlaengert" in felder:
        return "Frist verlängert"
    return "geändert"


def _deutsch(wert, stellen=None) -> str:
    """1480 → „1.480“, Decimal("54.6") → „54,6“ (deutsche Schreibweise)."""
    from decimal import Decimal

    if wert is None:
        return "—"
    if stellen is not None:
        text = f"{wert:,.{stellen}f}"
    elif isinstance(wert, Decimal):
        text = f"{wert.normalize():,f}"
    else:
        text = f"{wert:,}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def _klartext(html: str, laenge=200) -> str:
    import html as html_mod
    import re

    text = html_mod.unescape(re.sub(r"<[^>]+>", " ", html or ""))
    return _kurz(" ".join(text.split()), laenge)


def _beschreibung(name, h, aktion) -> str:
    """Kurzbeschreibung des Eintrags für die Spalte „Details“ (Entwurf 10)."""
    try:
        if name == "gewichte":
            return f"{_deutsch(h.gewicht_kg, 1)} kg, gemessen am {h.gemessen_am:%d.%m.%Y}"
        if name == "kontakte":
            if aktion == "storniert":
                return f"Kontakt vom {timezone.localtime(h.zeitpunkt):%d.%m.%Y, %H:%M} · Grund: {h.storno_grund}"
            return _klartext(h.text)
        if name == "termine":
            zeit = f" {h.uhrzeit:%H:%M}" if h.uhrzeit else ""
            return f"{dict(Termin.Art.choices).get(h.art, h.art)} · {h.faellig_am:%d.%m.%Y}{zeit} · {h.titel}"
        if name == "dokumente":
            groesse = f"{_deutsch(h.groesse / 1024 / 1024, 1)} MB" if h.groesse >= 1024 * 1024 else f"{max(1, round(h.groesse / 1024))} KB"
            titel = "Titel entfernt (DSGVO)" if h.titel == PLATZHALTER else h.titel
            return f"{titel} · {groesse} · SHA-256 {h.sha256[:4]}…{h.sha256[-4:]}"
        if name == "infusionsplaene":
            plan = h.instance
            teile = [f"{_deutsch(plan.kcal)} kcal"]
            if h.laufzeit_h is not None:
                teile.append(f"{_deutsch(h.laufzeit_h)} h")
            teile.append(f"gültig ab {h.gueltig_ab:%d.%m.%Y}")
            if h.abgeschlossen_von_id and h.freigegeben_von_id and h.freigabe_datum:
                from accounts.models import User

                weg = dict(type(plan).Freigabeweg.choices).get(h.freigabe_weg, "")
                teile.append(f"freigegeben von {benutzername(User.objects.filter(pk=h.freigegeben_von_id).first())} "
                             f"am {h.freigabe_datum:%d.%m.%Y}{f' ({weg})' if weg else ''}")
            return " · ".join(teile)
        if name == "bezugspersonen":
            beziehung = Auswahlwert.objects.filter(pk=h.beziehung_id).values_list("wert", flat=True).first()
            teile = [t for t in (beziehung, h.name, h.telefon or h.mobil) if t]
            if h.auskunft_erlaubt:
                teile.append("Auskunft erlaubt")
            return " · ".join(teile)
        if name == "aerzte":
            arzt = Arzt.objects.filter(pk=h.arzt_id).first()
            return " · ".join(t for t in (dict(PatientArzt.Rolle.choices).get(h.rolle, h.rolle), str(arzt or ""), h.notiz) if t)
        if name == "erklaerungen":
            teile = [dict(Erklaerung.Art.choices).get(h.art, h.art), f"vom {h.erteilt_am:%d.%m.%Y}"]
            if h.widerrufen_am:
                teile.append(f"widerrufen am {h.widerrufen_am:%d.%m.%Y}")
            return " · ".join(teile)
        if name == "datenschutz":
            teile = [f"Anfrage: {dict(Datenschutzanfrage.Art.choices).get(h.art, h.art)}",
                     f"eingegangen am {h.eingegangen_am:%d.%m.%Y}"]
            if h.ergebnis:
                teile.append(f"Ergebnis: {dict(Datenschutzanfrage.Ergebnis.choices).get(h.ergebnis, h.ergebnis)}")
            return " · ".join(teile)
        if name == "akte":
            if aktion == "Verarbeitung eingeschränkt":
                return f"Grund: {h.einschraenkung_grund}"
            if aktion == "Aufbewahrung verlängert":
                return f"bis {h.aufbewahrung_bis:%d.%m.%Y} · Grund: {h.aufbewahrung_grund}"
            if aktion == "abgeschlossen":
                return f"Anlass: {dict(Patient.Abschlussanlass.choices).get(h.abschluss_anlass, h.abschluss_anlass)}"
            if h.history_type == "+":
                return "Akte angelegt"
    except Exception:  # noqa: BLE001 – Beschreibung ist nur Anzeige
        return ""
    return ""


def verlauf_eintraege(patient, bereich=None, person=None, grenze=500):
    from infusionen.models import Infusionsplan

    quellen = {
        "akte": Patient.history.filter(id=patient.id),
        "gewichte": Gewichtsmessung.history.filter(patient_id=patient.id),
        "kontakte": Kontakt.history.filter(patient_id=patient.id),
        "termine": Termin.history.filter(patient_id=patient.id),
        "dokumente": Dokument.history.filter(patient_id=patient.id),
        "infusionsplaene": Infusionsplan.history.filter(patient_id=patient.id),
        "bezugspersonen": Bezugsperson.history.filter(patient_id=patient.id),
        "aerzte": PatientArzt.history.filter(patient_id=patient.id),
        "erklaerungen": Erklaerung.history.filter(patient_id=patient.id),
        "datenschutz": Datenschutzanfrage.history.filter(patient_id=patient.id),
    }
    if bereich and bereich not in ("stammdaten", *TEXTFELDER):
        quellen = {k: v for k, v in quellen.items() if k == bereich}
    elif bereich:
        quellen = {"akte": quellen["akte"]}
    eintraege = []
    for name, qs in quellen.items():
        qs = qs.select_related("history_user")
        if person:
            qs = qs.filter(history_user_id=person)
        for h in qs.order_by("-history_date")[:grenze]:
            eintraege.append((name, h))
    eintraege.sort(key=lambda e: e[1].history_date, reverse=True)
    # Dokumente, die diese Akte verlassen haben (einem anderen Patienten zugeordnet oder endgültig gelöscht), bzw. von
    # einer anderen Akte übernommen wurden (Festlegung 02.10.2026)
    vorgaenge = list(DokumentVorgang.objects.filter(Q(von_patient=patient) | Q(nach_patient=patient)).select_related("person"))
    weg = {v.dokument_id: v for v in vorgaenge if v.von_patient_id == patient.id}
    her = {v.dokument_id: v for v in vorgaenge if v.nach_patient_id == patient.id}
    ergebnis = []
    for name, h in eintraege[:grenze]:
        aenderungen = []
        vorher = h.prev_record if h.history_type == "~" else None
        if vorher is not None:
            diff = h.diff_against(vorher)
            aenderungen = [{"feld": c.field, "alt": _kurz(c.old), "neu": _kurz(c.new)} for c in diff.changes]
        if name == "dokumente":
            # gleiche Nummer UND gleiche Prüfsumme (nach einer Wiederherstellung kann eine Nummer neu vergeben sein)
            w, n = (v if v is not None and (not v.sha256 or v.sha256 == h.sha256) else None
                    for v in (weg.get(h.id), her.get(h.id)))
            if w is not None or n is not None:
                ergebnis.append(_dokument_vorgang_eintrag(h, w, n, vorher, aenderungen))
                continue
        basis = {
            "objekt_id": h.id,
            "art": {"+": "angelegt", "~": "geändert", "-": "gelöscht"}[h.history_type],
            "zeitpunkt": h.history_date,
            "person": benutzername(h.history_user),
            "person_id": h.history_user_id,
            "grund": h.history_change_reason,
        }
        if name != "akte":
            aktion = _aktion(name, h, aenderungen)
            ergebnis.append({**basis, "bereich": name, "aktion": aktion, "aenderungen": aenderungen,
                             "beschreibung": _beschreibung(name, h, aktion)})
            continue
        # Akte: je Bereich ein Eintrag (Stammdaten / Diagnose / Therapie / Empfehlung)
        gruppen = {}
        for a in aenderungen:
            gruppen.setdefault(a["feld"] if a["feld"] in TEXTFELDER else "stammdaten", []).append(a)
        if h.history_type != "~":
            gruppen = {"stammdaten": []}
        for gruppe, liste in gruppen.items():
            if bereich and bereich != gruppe:
                continue
            aktion = _aktion("stammdaten", h, liste)
            ergebnis.append({**basis, "bereich": gruppe, "aktion": aktion, "aenderungen": liste,
                             "beschreibung": _beschreibung("akte", h, aktion)})
    # die Zuordnung zu einer anderen Akte steht hier neutral, ohne den anderen Patienten und ohne Titel
    for v in weg.values():
        if v.art != DokumentVorgang.Art.UMGEHAENGT or (bereich and bereich != "dokumente") or (person and str(v.person_id) != str(person)):
            continue
        ergebnis.append({"objekt_id": v.dokument_id, "art": "geändert", "zeitpunkt": v.zeitpunkt,
                         "person": benutzername(v.person), "person_id": v.person_id, "grund": None, "bereich": "dokumente",
                         "aktion": "einer anderen Akte zugeordnet", "aenderungen": [],
                         "beschreibung": "Dokument wurde einer anderen Akte zugeordnet."})
    ergebnis.sort(key=lambda e: e["zeitpunkt"], reverse=True)
    return ergebnis


def _dokument_vorgang_eintrag(h, weg, her, vorher, aenderungen) -> dict:
    """Verlaufseintrag eines Dokuments, das umgehängt oder gelöscht wurde: in der bisherigen Akte neutral
    (kein Titel, keine Werte), in der neuen Akte „von einer anderen Akte übernommen“ mit Grund."""
    basis = {"objekt_id": h.id, "art": {"+": "angelegt", "~": "geändert", "-": "gelöscht"}[h.history_type],
             "zeitpunkt": h.history_date, "person": benutzername(h.history_user), "person_id": h.history_user_id,
             "bereich": "dokumente"}
    if her is not None and h.patient_id == her.nach_patient_id and vorher is not None and vorher.patient_id != h.patient_id:
        return {**basis, "aktion": "von einer anderen Akte übernommen", "grund": her.grund, "aenderungen": [],
                "beschreibung": _beschreibung("dokumente", h, "übernommen")}
    if weg is not None and h.patient_id == weg.von_patient_id:
        if weg.art == DokumentVorgang.Art.GELOESCHT and h.history_type == "-":
            return {**basis, "aktion": "endgültig gelöscht", "grund": weg.grund, "aenderungen": [],
                    "beschreibung": "Dokument endgültig gelöscht (Datei und Inhalt entfernt)."}
        spaeter = "später endgültig gelöscht" if weg.art == DokumentVorgang.Art.GELOESCHT else "später einer anderen Akte zugeordnet"
        return {**basis, "aktion": _aktion("dokumente", h, aenderungen), "grund": None, "aenderungen": [],
                "beschreibung": f"Dokument ({spaeter})"}
    return {**basis, "aktion": _aktion("dokumente", h, aenderungen), "grund": h.history_change_reason,
            "aenderungen": aenderungen, "beschreibung": _beschreibung("dokumente", h, _aktion("dokumente", h, aenderungen))}


def _kurz(wert, laenge=300):
    text = "" if wert is None else str(wert)
    return text if len(text) <= laenge else text[:laenge] + " …"


# ================================================================= Einträge der Akte
class AktenEintragViewSet(viewsets.GenericViewSet):
    """Gemeinsame Regeln: nur Patienten im eigenen Bereich, Filter ?patient=ID."""

    permission_classes = [EintragRecht]
    filterset_fields = ["patient"]

    def get_queryset(self):
        return self.model.objects.filter(patient__in=patienten_fuer(self.request.user)).select_related("patient")

    def pruefe_patient(self, patient, loeschen: bool = False):
        if not patienten_fuer(self.request.user).filter(pk=patient.pk).exists():
            raise serializers.ValidationError({"patient": "Patient nicht gefunden."})
        pruefe_schreibbereich(self.request.user, patient, loeschen=loeschen)
        patient.pruefe_bearbeitbar()


class GewichtSerializer(ModelClean, serializers.ModelSerializer):
    erfasst_von_name = serializers.SerializerMethodField()

    class Meta:
        model = Gewichtsmessung
        fields = ["id", "patient", "gewicht_kg", "gemessen_am", "datum_ungenau", "quelle", "notiz",
                  "erfasst_am", "erfasst_von_name"]
        read_only_fields = ["erfasst_am"]

    def get_erfasst_von_name(self, obj):
        return benutzername(obj.erfasst_von)

    def validate_patient(self, patient):
        if self.instance and patient != self.instance.patient:
            raise serializers.ValidationError("Der Patient kann nicht geändert werden.")
        return patient


class GewichtViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     mixins.CreateModelMixin, mixins.UpdateModelMixin):
    model = Gewichtsmessung
    serializer_class = GewichtSerializer
    ordering_fields = ["gemessen_am"]

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(erfasst_von=self.request.user)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        serializer.save()


def _pruefe_terminort(ort):
    if ort is not None and ort.liste != Auswahlwert.Liste.TERMINORT:
        raise serializers.ValidationError("Ungültiger Terminort.")
    return ort


class WiedervorlageSerializer(serializers.Serializer):
    """Termin, der zusammen mit einem Kontakt angelegt wird (Entwurf 6 · „Wiedervorlage“)."""

    art = serializers.ChoiceField(Termin.Art.choices, default=Termin.Art.WIEDERVORLAGE)
    ort = serializers.PrimaryKeyRelatedField(queryset=Auswahlwert.objects.filter(aktiv=True), required=False,
                                             allow_null=True)
    faellig_am = serializers.DateField()
    uhrzeit = serializers.TimeField(required=False, allow_null=True)
    titel = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notiz = serializers.CharField(required=False, allow_blank=True)

    def validate_ort(self, ort):
        return _pruefe_terminort(ort)

    def validate_faellig_am(self, datum):
        if datum < timezone.localdate():
            raise serializers.ValidationError("Das Datum liegt in der Vergangenheit.")
        return datum


class KontaktSerializer(serializers.ModelSerializer):
    text = RichText(required=True, allow_blank=False)
    erfasst_von_name = serializers.SerializerMethodField()
    storniert_von_name = serializers.SerializerMethodField()
    art_name = serializers.CharField(source="art.wert", read_only=True, default=None)
    wiedervorlage = WiedervorlageSerializer(write_only=True, required=False, allow_null=True)
    termine = serializers.SerializerMethodField()

    class Meta:
        model = Kontakt
        fields = ["id", "patient", "zeitpunkt", "art", "art_name", "text", "erfasst_am", "erfasst_von_name",
                  "storniert_am", "storniert_von_name", "storno_grund", "wiedervorlage", "termine"]
        read_only_fields = ["erfasst_am", "storniert_am", "storno_grund"]

    def get_termine(self, obj):
        return [{"id": t.id, "art": t.art, "faellig_am": t.faellig_am, "uhrzeit": t.uhrzeit,
                 "ort": t.ort.wert if t.ort_id else None, "erledigt": t.erledigt_am is not None}
                for t in obj.termine.all()]

    def validate_text(self, text):
        if not text.strip():
            raise serializers.ValidationError("Bitte einen Text eingeben.")
        return text

    @transaction.atomic
    def create(self, validated_data):
        wv = validated_data.pop("wiedervorlage", None)
        kontakt = super().create(validated_data)
        if wv:
            titel = wv.get("titel") or dict(Termin.Art.choices)[wv["art"]]
            Termin.objects.create(
                patient=kontakt.patient, kontakt=kontakt, art=wv["art"], ort=wv.get("ort"),
                faellig_am=wv["faellig_am"], uhrzeit=wv.get("uhrzeit"), titel=titel[:200],
                notiz=wv.get("notiz", ""), angelegt_von=kontakt.erfasst_von,
            )
        return kontakt

    def get_erfasst_von_name(self, obj):
        return benutzername(obj.erfasst_von)

    def get_storniert_von_name(self, obj):
        return benutzername(obj.storniert_von)

    def validate_art(self, art):
        if art is not None and art.liste != Auswahlwert.Liste.KONTAKTART:
            raise serializers.ValidationError("Ungültige Kontaktart.")
        return art

    def validate_zeitpunkt(self, wert):
        if wert > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError("Zeitpunkt liegt in der Zukunft.")
        return wert


class KontaktViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     mixins.CreateModelMixin):
    """Kontakte: anlegen und lesen. Ändern/Löschen gibt es nicht, nur Storno."""

    model = Kontakt
    serializer_class = KontaktSerializer
    search_fields = ["text"]

    def get_queryset(self):
        return (super().get_queryset().select_related("erfasst_von", "storniert_von", "art")
                .prefetch_related("termine__ort"))

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(erfasst_von=self.request.user)

    @action(detail=True, methods=["post"])
    def storno(self, request, pk=None):
        kontakt = self.get_object()
        self.pruefe_patient(kontakt.patient)
        kontakt.stornieren(request.user, str(request.data.get("grund", "")))
        return Response(self.get_serializer(kontakt).data)


class TerminSerializer(serializers.ModelSerializer):
    ort_name = serializers.CharField(source="ort.wert", read_only=True, default=None)
    erledigt_von_name = serializers.SerializerMethodField()
    angelegt_von_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    patient_ist_test = serializers.BooleanField(source="patient.ist_test", read_only=True)

    class Meta:
        model = Termin
        fields = ["id", "patient", "patient_name", "patient_ist_test", "art", "ort", "ort_name", "faellig_am", "uhrzeit", "bei", "titel",
                  "notiz", "kontakt", "erledigt_am", "erledigt_von_name", "angelegt_am", "angelegt_von_name"]
        read_only_fields = ["erledigt_am", "angelegt_am"]

    def get_erledigt_von_name(self, obj):
        return benutzername(obj.erledigt_von)

    def get_angelegt_von_name(self, obj):
        return benutzername(obj.angelegt_von)

    def get_patient_name(self, obj):
        return f"{obj.patient.nachname}, {obj.patient.vorname}"

    def validate_ort(self, ort):
        return _pruefe_terminort(ort)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        patient = attrs.get("patient") or (self.instance and self.instance.patient)
        kontakt = attrs.get("kontakt")
        if kontakt and kontakt.patient_id != patient.id:
            raise serializers.ValidationError({"kontakt": "Kontakt gehört zu einem anderen Patienten."})
        if self.instance and "patient" in attrs and attrs["patient"] != self.instance.patient:
            raise serializers.ValidationError({"patient": "Der Patient kann nicht geändert werden."})
        return attrs


class TerminFilter(filters.FilterSet):
    von = filters.DateFilter(field_name="faellig_am", lookup_expr="gte")
    bis = filters.DateFilter(field_name="faellig_am", lookup_expr="lte")
    offen = filters.BooleanFilter(field_name="erledigt_am", lookup_expr="isnull")

    class Meta:
        model = Termin
        fields = ["patient", "art"]


class TerminViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    mixins.CreateModelMixin, mixins.UpdateModelMixin):
    model = Termin
    serializer_class = TerminSerializer
    filterset_class = TerminFilter
    filterset_fields = None
    ordering_fields = ["faellig_am"]

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(angelegt_von=self.request.user)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        if serializer.instance.erledigt_am:
            raise serializers.ValidationError({"fehler": "Erledigte Termine können nicht geändert werden."})
        serializer.save()

    @action(detail=True, methods=["post"])
    def erledigt(self, request, pk=None):
        termin = self.get_object()
        self.pruefe_patient(termin.patient)
        if termin.erledigt_am:
            return Response({"fehler": "Termin ist bereits erledigt."}, status=status.HTTP_400_BAD_REQUEST)
        termin.erledigen(request.user)
        return Response(self.get_serializer(termin).data)


class DokumentSerializer(serializers.ModelSerializer):
    hochgeladen_von_name = serializers.SerializerMethodField()
    typ_name = serializers.CharField(source="typ.wert", read_only=True, default=None)
    datei = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Dokument
        fields = ["id", "patient", "typ", "typ_name", "titel", "datum", "datum_quelle", "typ_geprueft", "notiz",
                  "ausgeblendet", "datei", "originalname", "mime", "groesse", "sha256", "herkunft", "hochgeladen_am",
                  "hochgeladen_von_name"]
        read_only_fields = ["originalname", "mime", "groesse", "sha256", "herkunft", "hochgeladen_am",
                            "datum_quelle", "typ_geprueft"]

    def get_hochgeladen_von_name(self, obj):
        return benutzername(obj.hochgeladen_von)

    def validate_typ(self, typ):
        if typ is not None and typ.liste != Auswahlwert.Liste.DOKUMENTTYP:
            raise serializers.ValidationError("Ungültiger Dokumenttyp.")
        return typ

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get("datei"):
            raise serializers.ValidationError({"datei": "Bitte eine Datei auswählen."})
        if self.instance is not None and ("datei" in attrs or "patient" in attrs and attrs["patient"] != self.instance.patient):
            raise serializers.ValidationError({"fehler": "Datei und Patient können nicht geändert werden."})
        datei = attrs.get("datei")
        if datei and datei.size > settings.EPM_UPLOAD_MAX_MB * 1024 * 1024:
            raise serializers.ValidationError({"datei": f"Datei größer als {settings.EPM_UPLOAD_MAX_MB} MB."})
        if datei:
            mime = erkenne_dateityp(datei)
            if mime is None:
                raise serializers.ValidationError({"datei": "Erlaubt sind PDF, JPG, PNG und TXT."})
            self.erkannter_typ = mime
        return attrs


def erkenne_dateityp(upload):
    """Dateityp am Inhalt erkennen (nicht an der Endung): PDF, JPEG, PNG oder Text. Sonst None."""
    upload.seek(0)
    kopf = upload.read(2048)
    upload.seek(0)
    if kopf.startswith(b"%PDF-"):
        return "application/pdf"
    if kopf.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if kopf.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if b"\x00" in kopf:
        return None
    for kodierung in ("utf-8", "cp1252"):
        try:
            kopf.decode(kodierung)
            return f"text/plain; charset={'utf-8' if kodierung == 'utf-8' else 'windows-1252'}"
        except UnicodeDecodeError:
            continue
    return None


def speichere_datei(patient, upload, mime: str | None = None) -> dict:
    """Schreibt die Datei atomar ins Dokumentenverzeichnis und berechnet SHA-256."""
    relativ = dokument_pfad(patient, upload.name)
    ziel = settings.EPM_DOKUMENTE / relativ
    ziel.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    h = hashlib.sha256()
    groesse = 0
    fd, tmp = tempfile.mkstemp(dir=ziel.parent, prefix=".upload-")
    try:
        with os.fdopen(fd, "wb") as f:
            for teil in upload.chunks():
                h.update(teil)
                groesse += len(teil)
                f.write(teil)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o640)
        os.replace(tmp, ziel)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    mime = mime or upload.content_type or mimetypes.guess_type(upload.name)[0] or "application/octet-stream"
    return {"datei": relativ, "originalname": upload.name[:255], "mime": mime[:100], "groesse": groesse,
            "sha256": h.hexdigest()}


class DokumentViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, mixins.UpdateModelMixin):
    model = Dokument
    serializer_class = DokumentSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["patient", "typ", "ausgeblendet"]
    search_fields = ["titel", "originalname", "notiz"]

    def perform_create(self, serializer):
        patient = serializer.validated_data["patient"]
        self.pruefe_patient(patient)
        upload = serializer.validated_data.pop("datei")
        meta = speichere_datei(patient, upload, getattr(serializer, "erkannter_typ", None))
        titel = serializer.validated_data.get("titel") or upload.name
        serializer.save(hochgeladen_von=self.request.user, titel=titel[:200], **meta)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        serializer.save()

    @action(detail=True, methods=["post"])
    def geprueft(self, request, pk=None):
        """Altdokument bestätigen: Typ und Datum stimmen (optional mit Korrektur)."""
        dok = self.get_object()
        self.pruefe_patient(dok.patient)
        s = DokumentSerializer(dok, data={k: v for k, v in request.data.items() if k in ("typ", "datum", "titel")},
                               partial=True, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        if "datum" in s.validated_data and s.validated_data["datum"] != dok.datum:
            dok.datum_quelle = Dokument.DatumQuelle.EINGABE
        for feld, wert in s.validated_data.items():
            setattr(dok, feld, wert)
        dok.typ_geprueft = True
        dok._history_user = request.user
        dok.save()
        return Response(DokumentSerializer(dok, context=self.get_serializer_context()).data)

    # ------------------------------------------------ falsch zugeordnet: umhängen oder endgültig löschen
    def _nicht_systemdokument(self, dok):
        from infusionen.models import Infusionsplan

        if dok.herkunft == Dokument.Herkunft.SYSTEM:
            raise serializers.ValidationError({"fehler": "Von EPM erzeugte Dokumente (z. B. die PDF eines freigegebenen "
                                                         "Infusionsplans) gehören zu ihrem Plan und bleiben unverändert."})
        if Infusionsplan.objects.filter(freigabe_nachweis=dok).exists():
            raise serializers.ValidationError({"fehler": "Dieses Dokument ist der Nachweis der Freigabe eines "
                                                         "Infusionsplans und bleibt bei seinem Plan."})

    @action(detail=True, methods=["post"], permission_classes=[UmhaengenRecht])
    def umhaengen(self, request, pk=None):
        """Dokument beim falschen Patienten: dem richtigen zuordnen (Festlegung 02.10.2026).
        ``{"patient": ID, "grund": "…"}``. Datei und Prüfsumme bleiben; die bisherige Akte zeigt das Dokument danach
        nur noch neutral, die neue „von einer anderen Akte übernommen“ mit Grund; vollständig im Audit-Log."""
        dok = self.get_object()
        self._nicht_systemdokument(dok)
        grund = str(request.data.get("grund", "")).strip()
        ziel_id = str(request.data.get("patient", ""))
        ziel = patienten_fuer(request.user).filter(pk=ziel_id).first() if ziel_id.isdigit() else None
        fehler = {}
        if len(grund) < 5:
            fehler["grund"] = "Bitte den Grund angeben (mindestens 5 Zeichen)."
        if ziel is None:
            fehler["patient"] = "Bitte den richtigen Patienten auswählen."
        elif ziel.pk == dok.patient_id:
            fehler["patient"] = "Das Dokument gehört bereits zu diesem Patienten."
        elif ziel.ist_test != dok.patient.ist_test:
            fehler["patient"] = "Dokumente wechseln nicht zwischen Testpatienten und echten Akten."
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        alt = dok.patient
        self.pruefe_patient(alt)
        self.pruefe_patient(ziel)
        quelle = dok.pfad
        if not quelle.is_file():
            return Response({"fehler": "Die Datei fehlt im Dokumentenverzeichnis. Bitte die Administration informieren."},
                            status=status.HTTP_409_CONFLICT)
        neu_relativ = dokument_pfad(ziel, dok.originalname)
        ziel_pfad = settings.EPM_DOKUMENTE / neu_relativ
        ziel_pfad.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        os.replace(quelle, ziel_pfad)  # gleiches Dateisystem: atomar
        try:
            with transaction.atomic():
                dok.patient = ziel
                dok.datei = neu_relativ
                dok._history_user = request.user
                dok._change_reason = "Von einer anderen Akte übernommen"
                dok.save()
                # war das Dokument als unterschriebenes Blatt an einer Erklärung der bisherigen Akte verknüpft,
                # endet die Verknüpfung (die Erklärung selbst bleibt)
                for erklaerung in Erklaerung.objects.filter(dokument=dok):
                    erklaerung.dokument = None
                    erklaerung._history_user = request.user
                    erklaerung._change_reason = "Verknüpftes Dokument einer anderen Akte zugeordnet"
                    erklaerung.save()
                DokumentVorgang.objects.create(art=DokumentVorgang.Art.UMGEHAENGT, dokument_id=dok.id, von_patient=alt,
                                               nach_patient=ziel, grund=grund, person=request.user, sha256=dok.sha256,
                                               datei=neu_relativ)
                protokolliere(SystemEreignis.Art.DOKUMENT_UMGEHAENGT, request, objekt=f"Dokument {dok.id}",
                              titel=dok.titel, von=f"{alt.nachname}, {alt.vorname} (Nr. {alt.nummer})",
                              nach=f"{ziel.nachname}, {ziel.vorname} (Nr. {ziel.nummer})", grund=grund,
                              sha256=dok.sha256, patient_id=alt.id, nach_id=ziel.id)
        except BaseException:
            os.replace(ziel_pfad, quelle)  # Datenbank unverändert → Datei zurück
            raise
        return Response(DokumentSerializer(dok, context=self.get_serializer_context()).data)

    LOESCHCODE = "epm_loeschcode"
    LOESCH_MINUTEN = 5

    @action(detail=True, methods=["post"], url_path="loeschen-vorbereiten", permission_classes=[LoeschenRecht])
    def loeschen_vorbereiten(self, request, pk=None):
        """Schritt 1 des endgültigen Löschens: Bestätigungscode für dieses Dokument (5 Minuten, in der Sitzung)."""
        import secrets

        dok = self.get_object()
        self._nicht_systemdokument(dok)
        self.pruefe_patient(dok.patient, loeschen=True)
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        bis = timezone.now() + timedelta(minutes=self.LOESCH_MINUTEN)
        request.session[self.LOESCHCODE] = {"dokument": dok.id, "code": code, "bis": bis.isoformat(), "versuche": 0}
        return Response({"code": code, "gueltig_bis": bis})

    @action(detail=True, methods=["post"], permission_classes=[LoeschenRecht])
    def loeschen(self, request, pk=None):
        """Schritt 2: endgültig löschen (Mediziner und Admin, Recht „Dokumente endgültig löschen“) mit Grund, Kennwort, Code aus der Authenticator-App und dem
        abgetippten Bestätigungscode. Datei und Inhalt sind danach weg; Audit-Log und Verlauf („endgültig gelöscht“)
        bleiben. Jede Ablehnung steht im Audit-Log."""
        from datetime import datetime

        from django_otp.plugins.otp_totp.models import TOTPDevice

        dok = self.get_object()
        self._nicht_systemdokument(dok)
        self.pruefe_patient(dok.patient, loeschen=True)
        grund = str(request.data.get("grund", "")).strip()
        if len(grund) < 10:
            return Response({"grund": "Bitte den Grund angeben (mindestens 10 Zeichen)."}, status=status.HTTP_400_BAD_REQUEST)

        def abgelehnt(feld, meldung):
            protokolliere(SystemEreignis.Art.DOKUMENT_LOESCHEN_ABGELEHNT, request, objekt=f"Dokument {dok.id}",
                          titel=dok.titel, fehler=meldung, sha256=dok.sha256, patient_id=dok.patient_id)
            return Response({feld: meldung}, status=status.HTTP_400_BAD_REQUEST)

        sitzung = request.session.get(self.LOESCHCODE) or {}
        if sitzung.get("dokument") != dok.id or datetime.fromisoformat(sitzung["bis"]) < timezone.now():
            request.session.pop(self.LOESCHCODE, None)
            return abgelehnt("bestaetigung", "Der Bestätigungscode ist abgelaufen. Bitte einen neuen anfordern.")
        eingabe = "".join(ch for ch in str(request.data.get("bestaetigung", "")).upper() if ch.isalnum())
        if eingabe != sitzung["code"]:
            sitzung["versuche"] = sitzung.get("versuche", 0) + 1
            if sitzung["versuche"] >= 3:
                request.session.pop(self.LOESCHCODE, None)
                return abgelehnt("bestaetigung", "Bestätigungscode dreimal falsch. Bitte einen neuen anfordern.")
            request.session[self.LOESCHCODE] = sitzung
            return abgelehnt("bestaetigung", "Der Bestätigungscode stimmt nicht.")
        from accounts.api import bestaetigung_fehlgeschlagen, bestaetigung_gelungen

        if not request.user.check_password(str(request.data.get("kennwort", ""))):
            antwort = abgelehnt("kennwort", "Kennwort falsch.")
            return bestaetigung_fehlgeschlagen(request, "loeschen_kennwort") or antwort
        code = str(request.data.get("code", "")).replace(" ", "")
        if not any(g.verify_token(code) for g in TOTPDevice.objects.filter(user=request.user, confirmed=True)):
            antwort = abgelehnt("code", "Code aus der Authenticator-App falsch oder schon verwendet.")
            return bestaetigung_fehlgeschlagen(request, "loeschen_2fa") or antwort
        bestaetigung_gelungen(request)
        request.session.pop(self.LOESCHCODE, None)
        pfad = dok.pfad
        dok_id, sha, datei = dok.id, dok.sha256, dok.datei
        akte = f"{dok.patient.nachname}, {dok.patient.vorname} (Nr. {dok.patient.nummer})"
        with transaction.atomic():
            vorgang = DokumentVorgang.objects.create(art=DokumentVorgang.Art.GELOESCHT, dokument_id=dok_id,
                                                     von_patient=dok.patient, grund=grund, person=request.user,
                                                     sha256=sha, datei=datei)
            # Art. 17 DSGVO (U15): kein Titel, kein Dateiname im Nachweis – nur Typ, Größe, Prüfsumme, Zeitpunkte
            protokolliere(SystemEreignis.Art.DOKUMENT_GELOESCHT, request, objekt=f"Dokument {dok_id}", akte=akte,
                          grund=grund, sha256=sha, groesse=dok.groesse, typ=dok.typ.wert if dok.typ else "",
                          hochgeladen_am=dok.hochgeladen_am.isoformat() if dok.hochgeladen_am else "",
                          patient_id=dok.patient_id)
            dok._history_user = request.user
            dok._change_reason = "Endgültig gelöscht"
            dok.delete()
            schwaerze_dokument(dok_id, sha)
            eintrag = {"dokument": dok_id, "sha256": sha, "datei": datei, "patient": vorgang.von_patient_id,
                       "person": request.user.id, "geloescht_am": timezone.now().isoformat(timespec="seconds")}
            transaction.on_commit(lambda: trage_ein(eintrag), robust=True)
            transaction.on_commit(lambda: pfad.unlink(missing_ok=True), robust=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def datei(self, request, pk=None):
        """Download: in Produktion liefert Nginx die Datei (X-Accel-Redirect), Django prüft nur das Recht."""
        dok = self.get_object()
        inline = request.query_params.get("anzeigen") == "1"
        art = "inline" if inline else "attachment"
        name = dok.originalname.replace('"', "")
        from urllib.parse import quote
        dispo = f"{art}; filename*=UTF-8''{quote(name)}"
        if settings.EPM_X_ACCEL:
            antwort = HttpResponse(content_type=dok.mime)
            antwort["X-Accel-Redirect"] = settings.EPM_X_ACCEL_PREFIX + dok.datei
        else:
            antwort = FileResponse(open(dok.pfad, "rb"), content_type=dok.mime)
        antwort["Content-Disposition"] = dispo
        antwort["Cache-Control"] = "private, no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        return antwort


# ================================================================= Startseite
# ================================================================= Bezugspersonen und Ärzte der Akte
class _StammEintragViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                           mixins.CreateModelMixin, mixins.UpdateModelMixin):
    """Teil der Stammdaten der Akte: schreiben mit „Patienten anlegen, Diagnose, Therapie, Stammdaten ändern“.
    Kein Löschen (405): nicht mehr Aktuelles wird mit ``aktiv: false`` markiert und bleibt im Verlauf."""

    permission_classes = [AktenRecht]
    filterset_fields = ["patient", "aktiv"]
    pagination_class = None

    def perform_create(self, serializer):
        self.pruefe_patient(serializer.validated_data["patient"])
        serializer.save(angelegt_von=self.request.user)

    def perform_update(self, serializer):
        self.pruefe_patient(serializer.instance.patient)
        serializer.save()


class _PatientFest:
    def validate_patient(self, patient):
        if self.instance and patient != self.instance.patient:
            raise serializers.ValidationError("Der Patient kann nicht geändert werden.")
        return patient


class BezugspersonSerializer(_PatientFest, serializers.ModelSerializer):
    beziehung_name = serializers.CharField(source="beziehung.wert", read_only=True, default=None)
    angelegt_von_name = serializers.SerializerMethodField()

    class Meta:
        model = Bezugsperson
        fields = ["id", "patient", "beziehung", "beziehung_name", "name", "telefon", "mobil", "email", "strasse",
                  "plz", "ort", "notiz", "auskunft_erlaubt", "aktiv", "angelegt_am", "angelegt_von_name"]
        read_only_fields = ["angelegt_am"]

    def get_angelegt_von_name(self, obj):
        return benutzername(obj.angelegt_von)

    def validate_name(self, wert):
        if not wert.strip():
            raise serializers.ValidationError("Bitte einen Namen eingeben.")
        return wert.strip()

    def validate_beziehung(self, wert):
        if wert is not None and wert.liste != Auswahlwert.Liste.BEZIEHUNG:
            raise serializers.ValidationError("Ungültiger Wert für die Liste „Beziehung“.")
        if wert is not None and not wert.aktiv and (self.instance is None or self.instance.beziehung_id != wert.id):
            raise serializers.ValidationError("Dieser Wert ist ausgeblendet.")
        return wert


class BezugspersonViewSet(_StammEintragViewSet):
    """Bezugspersonen (Mutter, Vater, Betreuer/in …) je Patient: ``?patient=ID&aktiv=true``."""

    model = Bezugsperson
    serializer_class = BezugspersonSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("beziehung", "angelegt_von")


class ArztKurzSerializer(serializers.ModelSerializer):
    class Meta:
        model = Arzt
        fields = ["id", "name", "praxis", "fachrichtung", "strasse", "plz", "ort", "telefon", "fax", "email", "aktiv"]


class PatientArztSerializer(_PatientFest, serializers.ModelSerializer):
    arzt_daten = ArztKurzSerializer(source="arzt", read_only=True)
    rolle_name = serializers.CharField(source="get_rolle_display", read_only=True)
    angelegt_von_name = serializers.SerializerMethodField()

    class Meta:
        model = PatientArzt
        fields = ["id", "patient", "arzt", "arzt_daten", "rolle", "rolle_name", "notiz", "aktiv", "angelegt_am",
                  "angelegt_von_name"]
        read_only_fields = ["angelegt_am"]

    def get_angelegt_von_name(self, obj):
        return benutzername(obj.angelegt_von)

    def validate_arzt(self, arzt):
        if self.instance is not None and arzt != self.instance.arzt:
            raise serializers.ValidationError("Der Arzt kann nicht getauscht werden; bitte neu zuordnen.")
        if self.instance is None and not arzt.aktiv:
            raise serializers.ValidationError("Dieser Arzt ist deaktiviert.")
        return arzt

    def validate(self, attrs):
        attrs = super().validate(attrs)
        patient = attrs.get("patient") or self.instance.patient
        arzt = attrs.get("arzt") or self.instance.arzt
        rolle = attrs.get("rolle") or (self.instance.rolle if self.instance else PatientArzt.Rolle.HAUSARZT)
        aktiv = attrs.get("aktiv", self.instance.aktiv if self.instance else True)
        if aktiv:
            doppelt = PatientArzt.objects.filter(patient=patient, arzt=arzt, rolle=rolle, aktiv=True)
            if self.instance is not None:
                doppelt = doppelt.exclude(pk=self.instance.pk)
            if doppelt.exists():
                raise serializers.ValidationError({"arzt": "Dieser Arzt ist mit dieser Rolle bereits zugeordnet."})
        return attrs


class PatientArztViewSet(_StammEintragViewSet):
    """Ärzte eines Patienten aus der gemeinsamen Ärzteliste: ``?patient=ID&aktiv=true``."""

    model = PatientArzt
    serializer_class = PatientArztSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("arzt", "angelegt_von")


def _zuletzt_eingetragen(patienten, anzahl=10, person=None):
    """Neueste Einträge aus allen Bereichen (Entwurf 2 · „Zuletzt eingetragen“); ``person``: nur eigene (S10)."""
    from infusionen.models import Infusionsplan

    ids = list(patienten.values_list("id", flat=True))
    quellen = [
        ("kontakt", "Kontakt", Kontakt.history.filter(patient_id__in=ids, history_type="+")),
        ("gewicht", "Gewicht", Gewichtsmessung.history.filter(patient_id__in=ids, history_type="+")),
        ("dokument", "Dokument", Dokument.history.filter(patient_id__in=ids, history_type="+")),
        ("termin", "Termin angelegt", Termin.history.filter(patient_id__in=ids, history_type="+")),
        ("termin", "Termin erledigt",
         Termin.history.filter(patient_id__in=ids, history_type="~", erledigt_am__isnull=False)),
        ("plan", "Infusionsplan-Entwurf", Infusionsplan.history.filter(patient_id__in=ids, history_type="+")),
        ("plan", "Infusionsplan freigegeben",
         Infusionsplan.history.filter(patient_id__in=ids, history_type="~", status="aktuell", freigegeben_am__isnull=False)),
    ]
    eintraege = []
    for bereich, bezeichnung, qs in quellen:
        if person is not None:
            qs = qs.filter(history_user=person)
        if bezeichnung == "Termin erledigt":
            # nur die Fassung, in der „erledigt“ gesetzt wurde (spätere Änderungen eines erledigten Termins nicht)
            qs = qs.filter(history_date__lte=F("erledigt_am") + timedelta(seconds=5))
        for h in qs.select_related("history_user").order_by("-history_date")[:anzahl]:
            eintraege.append((h.history_date, bereich, bezeichnung, h))
    eintraege.sort(key=lambda e: e[0], reverse=True)
    namen = dict((p.id, f"{p.nachname}, {p.vorname}") for p in patienten.filter(id__in={e[3].patient_id for e in eintraege}))
    ergebnis = []
    gesehen = set()
    for zeit, bereich, bezeichnung, h in eintraege:
        schluessel = (bereich, h.id, bezeichnung)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        if bezeichnung == "Infusionsplan freigegeben" and h.abgeschlossen_von_id:
            bezeichnung = "Infusionsplan nach Freigabe abgeschlossen"  # freigegeben hat der Mediziner, außerhalb von EPM
        ergebnis.append({"bereich": bereich, "bezeichnung": bezeichnung, "objekt_id": h.id,
                         "patient": h.patient_id, "name": namen.get(h.patient_id), "zeitpunkt": zeit,
                         "person": benutzername(h.history_user), "person_id": h.history_user_id})
        if len(ergebnis) == anzahl:
            break
    return ergebnis


def _wiedereinbestellung(patienten, e, grenze=50):
    """S04 „Wiedereinbestellung fällig“: Akten in Betreuung, deren letzter Kontakt über „bald fällig“ bzw. „überfällig“
    zurückliegt und für die kein offener Termin geplant ist. Längste Zeit ohne Kontakt zuerst."""
    from .kennzahlen import kontakt_grenzen, kontaktstufe

    offen = kontakt_filter(patienten.filter(abgeschlossen_am__isnull=True), "wiedereinbestellung")
    zeilen = list(offen.annotate(letzter=Max("kontakte__zeitpunkt", filter=Q(kontakte__storniert_am__isnull=True)))
                  .order_by(F("letzter").asc(nulls_first=True), "nachname", "vorname")
                  .values("id", "nachname", "vorname", "nummer", "ist_test", "letzter"))
    grenzen = kontakt_grenzen(e)
    stufen = {"ueberfaellig": [], "bald": []}
    for z in zeilen:
        stufe = kontaktstufe(z["letzter"], grenzen)
        if stufe:
            stufen[stufe].append({"patient": z["id"], "name": f"{z['nachname']}, {z['vorname']}", "nummer": z["nummer"],
                                  "ist_test": z["ist_test"], "letzter_kontakt": z["letzter"], "stufe": stufe})
    return {
        "ueberfaellig": stufen["ueberfaellig"][:grenze], "bald": stufen["bald"][:grenze],
        "anzahl_ueberfaellig": len(stufen["ueberfaellig"]), "anzahl_bald": len(stufen["bald"]),
        "bald_monate": e.kontakt_bald_monate, "ueberfaellig_monate": e.kontakt_ueberfaellig_monate,
    }


def _gewichtsverlauf(patient_ids, tage=180):
    """Mini-Verlauf je Patient (S06): Messungen der letzten 6 Monate mit echten Zeitabständen."""
    seit = timezone.localdate() - timedelta(days=tage)
    verlauf = {}
    for pid, am, kg_ in (Gewichtsmessung.objects.filter(patient_id__in=list(patient_ids), gemessen_am__gte=seit)
                         .order_by("patient_id", "gemessen_am", "id").values_list("patient_id", "gemessen_am", "gewicht_kg")):
        verlauf.setdefault(pid, []).append({"am": am, "kg": kg_})
    return verlauf


def _woche(termine_qs, heute):
    """Wochenstreifen (S03): die 7 Tage ab heute mit Anzahl offener Termine, davon Praxistermine, und Feiertagen."""
    from .kalender import feiertage_zwischen

    bis = heute + timedelta(days=6)
    feiertage = {f["datum"]: f["name"] for f in feiertage_zwischen(heute, bis)}
    zaehlung = {}
    for datum_, art in termine_qs.filter(faellig_am__range=(heute, bis)).values_list("faellig_am", "art"):
        z = zaehlung.setdefault(datum_, [0, 0])
        z[0] += 1
        z[1] += art == Termin.Art.PRAXISTERMIN
    return [{"datum": heute + timedelta(days=i), "anzahl": zaehlung.get(heute + timedelta(days=i), [0, 0])[0],
             "praxistermine": zaehlung.get(heute + timedelta(days=i), [0, 0])[1],
             "feiertag": feiertage.get(heute + timedelta(days=i))} for i in range(7)]


def startseite_daten(user):
    from accounts.api import notfallcodes_stand
    from infusionen.models import Infusionsplan
    from stammdaten.models import Einstellungen

    heute = timezone.localdate()
    e = Einstellungen.aktuell()
    patienten = patienten_fuer(user).filter(abgeschlossen_am__isnull=True)
    termine = Termin.objects.filter(patient__in=patienten, erledigt_am__isnull=True).select_related(
        "patient", "ort", "angelegt_von")
    sieben_tage = termine.filter(faellig_am__gte=heute, faellig_am__lte=heute + timedelta(days=6))

    def t(qs):
        return TerminSerializer(qs.order_by("faellig_am", "uhrzeit")[:100], many=True).data

    werte = kennzahlen(patienten.only("id", "versorger", "nachname", "vorname", "nummer"))
    gewicht_liste = {p.id: p for p in patienten.only("id", "nachname", "vorname", "nummer")}
    warnungen = sorted(
        ({"patient": pid, "name": f"{gewicht_liste[pid].nachname}, {gewicht_liste[pid].vorname}",
          "nummer": gewicht_liste[pid].nummer, "gewicht": k["gewicht"], "prozent": k["trend"]["prozent"]}
         for pid, k in werte.items() if k["trend"] and k["trend"]["warnung"]),
        key=lambda w: w["prozent"],
    )
    verlauf = _gewichtsverlauf(w["patient"] for w in warnungen)
    for w in warnungen:
        w["verlauf"] = verlauf.get(w["patient"], [])

    grenze = heute - timedelta(days=30 * e.plan_alter_warnung_monate)
    plaene = Infusionsplan.objects.filter(patient__in=patienten).select_related("patient", "erstellt_von",
                                                                               "freigegeben_von")
    entwuerfe = plaene.filter(status=Infusionsplan.Status.ENTWURF).order_by("-erstellt_am")
    alte = plaene.filter(status=Infusionsplan.Status.AKTUELL, gueltig_ab__lt=grenze).order_by("gueltig_ab")

    def pl(qs):
        return [{"id": x.id, "patient": x.patient_id, "name": f"{x.patient.nachname}, {x.patient.vorname}",
                 "gueltig_ab": x.gueltig_ab, "status": x.status, "erstellt_am": x.erstellt_am,
                 "erstellt_von": benutzername(x.erstellt_von), "freigegeben_am": x.freigegeben_am}
                for x in qs[:50]]

    statistik = patienten if user.ist_test else patienten.filter(ist_test=False)
    pruefen = pruefliste(statistik)
    # Datenschutz-Anfragen betreffen oft abgeschlossene Akten (Löschung, Auskunft) – hier zählen alle Akten im
    # Bereich der Person, für die sie Anfragen sieht; ohne Datenschutz-Recht erscheint nichts.
    pruefen["datenschutz_anfragen"] = pruefen["datenschutz_ueberfaellig"] = 0
    if user.hat_recht("datenschutz_bearbeiten") or user.hat_recht("datenschutz_entscheiden"):
        bereich = patienten_mit_eingeschraenkten(user)
        offen = list(Datenschutzanfrage.objects.filter(
            patient__in=bereich if user.ist_test else bereich.filter(ist_test=False), erledigt_am__isnull=True))
        pruefen["datenschutz_anfragen"] = len(offen)
        pruefen["datenschutz_ueberfaellig"] = sum(1 for a in offen if a.ueberfaellig)
    wieder = _wiedereinbestellung(patienten, e)
    return {
        "termine": {
            "ueberfaellig": t(termine.filter(faellig_am__lt=heute)),
            "heute": t(termine.filter(faellig_am=heute)),
            # heute und die 6 folgenden Tage – wie der Wochenstreifen und die Kennzahl „Termine in 7 Tagen“
            "naechste_7_tage": t(sieben_tage),
        },
        "woche": _woche(termine, heute),
        "gewichtswarnungen": warnungen,
        "gewicht_schwelle": {"prozent": e.gewicht_warnung_prozent, "monate": e.gewicht_warnung_monate},
        "infusionsplaene": {
            "entwuerfe": pl(entwuerfe),
            "aelter_als_grenze": pl(alte),
            "anzahl_entwuerfe": entwuerfe.count(),
            "anzahl_aelter": alte.count(),
            "grenze_monate": e.plan_alter_warnung_monate,
        },
        "pruefen": pruefen,
        "wiedereinbestellung": wieder,
        "zuletzt_eingetragen": _zuletzt_eingetragen(patienten),
        "zuletzt_von_mir": _zuletzt_eingetragen(patienten, person=user),
        "zahlen": {
            # Statistik ohne Testpatienten (für Testzugänge: nur Testpatienten)
            "in_betreuung": statistik.count(),
            # nur Akten mit mindestens einem offenen Termin (vorher zählten auch Akten ganz ohne Termin mit: der Filter
            # über die Verknüpfung traf bei fehlendem Termin auf NULL)
            "mit_offenem_termin": statistik.filter(
                id__in=Termin.objects.filter(erledigt_am__isnull=True).values("patient_id")).count(),
            # wie die Kacheln „Termine und Wiedervorlagen“ und „Wiedereinbestellung fällig“
            "termine_7_tage": sieben_tage.count(),
            "praxistermine_7_tage": sieben_tage.filter(art=Termin.Art.PRAXISTERMIN).count(),
            "termine_ueberfaellig": termine.filter(faellig_am__lt=heute).count(),
            "kontakt_ueberfaellig": wieder["anzahl_ueberfaellig"],
            "kontakt_bald": wieder["anzahl_bald"],
        },
        # S08: Hinweis „Nur noch n Notfall-Codes übrig“ für die angemeldete Person
        "notfallcodes": notfallcodes_stand(user),
        # Kopfzeile (O-07): Zustand der Sicherungen vom Systemagenten – für alle sichtbar, ohne Zugangsdaten
        "sicherung": sicherung_kurz(),
    }


def sicherung_kurz():
    from system.sicherung import kurzstatus

    return kurzstatus()


class StartseiteViewSet(viewsets.ViewSet):
    permission_classes = [recht("akten_lesen")]

    def list(self, request):
        from audit.bereinigung import taeglich

        taeglich()  # abgelaufene Sitzungen, Audit-Log nach der eingestellten Aufbewahrung (höchstens einmal am Tag)
        return Response(startseite_daten(request.user))


class KalenderViewSet(viewsets.ViewSet):
    """
    GET /api/kalender/?von=JJJJ-MM-TT&bis=JJJJ-MM-TT&erledigte=1&faelligkeiten=0
    Globaler Kalender: Termine aller Patienten im Zeitraum, offene überfällige Termine, berechnete Fälligkeiten
    (Kontakt, Infusionsplan) und Feiertage. Lesen mit „Akten lesen“; Termine anlegen/ändern über /api/termine/.
    """

    permission_classes = [recht("akten_lesen")]

    def list(self, request):
        from .kalender import MAX_TAGE, faelligkeiten, feiertage_zwischen

        p = request.query_params
        von, bis = _datum(p.get("von", "")), _datum(p.get("bis", ""))
        fehler = {}
        if von is None:
            fehler["von"] = "Bitte ein Datum (JJJJ-MM-TT) angeben."
        if bis is None:
            fehler["bis"] = "Bitte ein Datum (JJJJ-MM-TT) angeben."
        if not fehler and bis < von:
            fehler["bis"] = "„bis“ liegt vor „von“."
        if not fehler and (bis - von).days > MAX_TAGE:
            fehler["bis"] = f"Höchstens {MAX_TAGE} Tage auf einmal."
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        heute = timezone.localdate()
        patienten = patienten_fuer(request.user)
        termine = (Termin.objects.filter(patient__in=patienten).select_related("patient", "ort", "angelegt_von",
                                                                                "erledigt_von")
                   .order_by("faellig_am", F("uhrzeit").asc(nulls_first=True), "id"))
        im_zeitraum = termine.filter(faellig_am__range=(von, bis))
        if str(p.get("erledigte", "1")).lower() in ("0", "false", "nein"):
            im_zeitraum = im_zeitraum.filter(erledigt_am__isnull=True)
        ueberfaellig = termine.filter(erledigt_am__isnull=True, faellig_am__lt=heute,
                                      patient__abgeschlossen_am__isnull=True)
        daten = {
            "von": von, "bis": bis, "heute": heute,
            "termine": TerminSerializer(im_zeitraum[:2000], many=True).data,
            "termine_ueberfaellig": TerminSerializer(ueberfaellig[:300], many=True).data,
            "faelligkeiten": [],
            "grenzen": {},
            "feiertage": feiertage_zwischen(von, bis),
        }
        if str(p.get("faelligkeiten", "1")).lower() not in ("0", "false", "nein"):
            daten["faelligkeiten"], daten["grenzen"] = faelligkeiten(patienten, bis)
        return Response(daten)
