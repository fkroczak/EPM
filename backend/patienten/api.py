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
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import AbschlussRecht, AktenRecht, EintragRecht, WiederOeffnenRecht, recht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import ModelClean, RichText, benutzername, patienten_fuer
from stammdaten.models import Auswahlwert

from .kennzahlen import kennzahlen, pruefliste, schnellfilter, zaehler
from .models import Dokument, Gewichtsmessung, Kontakt, Patient, Termin, dokument_pfad


# ================================================================= Patient
class PatientListSerializer(serializers.ModelSerializer):
    versorger_name = serializers.CharField(source="versorger.name", read_only=True, default=None)
    ansprechpartner_name = serializers.CharField(source="ansprechpartner.name", read_only=True, default=None)
    katheter_name = serializers.CharField(source="katheter.wert", read_only=True, default=None)
    ist_abgeschlossen = serializers.BooleanField(read_only=True)
    alter = serializers.SerializerMethodField()
    kennzahlen = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "id", "nummer", "nachname", "vorname", "geburtsdatum", "alter", "ort", "katheter", "katheter_name",
            "versorger", "versorger_name", "ansprechpartner", "ansprechpartner_name", "nickelallergie",
            "ist_abgeschlossen", "abgeschlossen_am", "abschluss_anlass", "ist_test", "kennzahlen",
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
    kopf = serializers.SerializerMethodField()
    angelegt_von_name = serializers.SerializerMethodField()
    # Nur beim Anlegen: „Gewicht bei Aufnahme“ (Entwurf 12) wird als erste Messung gespeichert
    aufnahme_gewicht_kg = serializers.DecimalField(max_digits=5, decimal_places=1, required=False,
                                                   allow_null=True, write_only=True)
    aufnahme_gemessen_am = serializers.DateField(required=False, write_only=True)
    aufnahme_quelle = serializers.ChoiceField(Gewichtsmessung.Quelle.choices, required=False, write_only=True)

    class Meta:
        model = Patient
        fields = [
            "id", "nummer", "nachname", "vorname", "geburtsdatum", "geschlecht",
            "strasse", "plz", "ort", "telefon", "telefon2", "email", "krankenkasse", "hausarzt",
            "ueberweisung_durch", "groesse_cm", "katheter", "versorger", "ansprechpartner", "nickelallergie",
            "diagnose", "therapie", "empfehlung", "bemerkung",
            "abgeschlossen_am", "abschluss_anlass", "abschluss_notiz", "ist_abgeschlossen", "ist_test",
            "angelegt_am", "angelegt_von_name", "geaendert_am", "kopf",
            "aufnahme_gewicht_kg", "aufnahme_gemessen_am", "aufnahme_quelle",
        ]
        read_only_fields = ["abgeschlossen_am", "abschluss_anlass", "abschluss_notiz", "angelegt_am", "geaendert_am"]

    def get_angelegt_von_name(self, obj):
        return benutzername(obj.angelegt_von)

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
            "katheter": obj.katheter.wert if obj.katheter_id else None,
            "versorger": obj.versorger.name if obj.versorger_id else None,
            "ansprechpartner": obj.ansprechpartner.name if obj.ansprechpartner_id else None,
            "ansprechpartner_telefon": (obj.ansprechpartner.telefon or obj.ansprechpartner.mobil)
            if obj.ansprechpartner_id else None,
            "nickelallergie": obj.nickelallergie,
            "aktueller_plan": {"id": plan.id, "gueltig_ab": plan.gueltig_ab, "kcal": plan.kcal,
                               "laufzeit_h": plan.laufzeit_h} if plan else None,
            "naechster_termin": (
                {"id": termin.id, "art": termin.art, "titel": termin.titel, "faellig_am": termin.faellig_am,
                 "uhrzeit": termin.uhrzeit, "ort": termin.ort.wert if termin.ort_id else None,
                 "bei": termin.bei} if termin else None
            ),
            "versionen": {feld: _versionskopf(obj, feld) for feld in TEXTFELDER},
            "zaehler": {
                "kontakte": obj.kontakte.count(),
                "gewichte": obj.gewichte.count(),
                "dokumente": obj.dokumente.filter(ausgeblendet=False).count(),
                "termine_offen": obj.termine.filter(erledigt_am__isnull=True).count(),
                "infusionsplaene": obj.infusionsplaene.count(),
            },
        }

    def validate(self, attrs):
        aufnahme = {k: attrs.pop(k) for k in ("aufnahme_gewicht_kg", "aufnahme_gemessen_am", "aufnahme_quelle")
                    if k in attrs}
        if aufnahme and self.instance is not None:
            raise serializers.ValidationError({"aufnahme_gewicht_kg": "Nur beim Anlegen möglich."})
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
                 ("kein_versorger", "Kein Versorger"), ("kein_kontakt", "Kein Kontakt seit X Monaten")],
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
            return qs.filter(versorger__isnull=True)
        if wert == "kein_kontakt":
            from stammdaten.models import Einstellungen

            grenze = timezone.now() - timedelta(days=30 * Einstellungen.aktuell().kontakt_ueberfaellig_monate)
            aktuell = Kontakt.objects.filter(storniert_am__isnull=True, zeitpunkt__gte=grenze).values("patient_id")
            return qs.exclude(id__in=aktuell)
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


class PatientViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
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
        context["kennzahlen"] = kennzahlen(eintraege)
        daten = PatientListSerializer(eintraege, many=True, context=context).data
        return self.get_paginated_response(daten) if seite is not None else Response(daten)

    @action(detail=False, methods=["get"])
    def zaehler(self, request):
        """Zahlen für „In Betreuung“, „Abgeschlossen“ und die Schnellfilter (Testpatienten zählen nicht)."""
        qs = patienten_fuer(request.user)
        if not request.user.ist_test:
            qs = qs.filter(ist_test=False)
        return Response(zaehler(qs))

    @action(detail=False, methods=["get"], url_path="naechste-nummer")
    def naechste_nummer(self, request):
        """„Nr. 0300 wird automatisch vergeben“ (Entwurf 12)."""
        return Response({"nummer": Patient.naechste_nummer(request.user.ist_test)})

    @transaction.atomic
    def perform_create(self, serializer):
        patient = serializer.save(angelegt_von=self.request.user, ist_test=self.request.user.ist_test)
        messung = getattr(serializer, "aufnahme_messung", None)
        if messung is not None:
            messung.patient = patient
            messung.erfasst_von = self.request.user
            messung.save()

    @action(detail=True, methods=["get"])
    def versionen(self, request, pk=None):
        """Fassungen von Diagnose, Therapie oder Empfehlung (Entwurf 5 · „Versionen“)."""
        feld = request.query_params.get("feld")
        if feld not in TEXTFELDER:
            return Response({"feld": f"Erlaubt: {', '.join(TEXTFELDER)}."}, status=status.HTTP_400_BAD_REQUEST)
        fassungen = feldversionen(self.get_object(), feld)
        return Response({"feld": feld, "version": fassungen[0]["version"] if fassungen else 0, "fassungen": fassungen})

    def perform_update(self, serializer):
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
                      name=f"{patient.nachname}, {patient.vorname}")
        patient.refresh_from_db()
        return Response(PatientSerializer(patient, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="wieder-oeffnen", permission_classes=[WiederOeffnenRecht])
    def wieder_oeffnen(self, request, pk=None):
        patient = self.get_object()
        if not patient.ist_abgeschlossen:
            return Response({"fehler": "Akte ist nicht abgeschlossen."}, status=status.HTTP_400_BAD_REQUEST)
        grund = str(request.data.get("grund", "")).strip()
        if not grund:
            return Response({"grund": "Bitte einen Grund angeben."}, status=status.HTTP_400_BAD_REQUEST)
        vorher = patient.abschluss_anlass
        patient.abgeschlossen_am = None
        patient.abschluss_anlass = ""
        patient.abschluss_notiz = ""
        patient._change_reason = f"Wieder geöffnet: {grund}"
        patient.save()
        protokolliere(SystemEreignis.Art.AKTE_GEOEFFNET, request, objekt=patient.nummer, grund=grund,
                      vorheriger_anlass=vorher, name=f"{patient.nachname}, {patient.vorname}")
        return Response(PatientSerializer(patient, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"])
    def verlauf(self, request, pk=None):
        """Alle Fassungen aller Einträge dieser Akte, neueste zuerst (Entwurf 10).

        Filter ``bereich``: stammdaten, diagnose, therapie, empfehlung, gewichte, kontakte, termine,
        dokumente, infusionsplaene; ``person``: Benutzer-ID. Änderungen an der Akte werden nach Feld auf
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
        return {"aktuell": "freigegeben", "abgeloest": "abgelöst"}.get(h.status, "geändert")
    if name == "stammdaten" and "abgeschlossen_am" in felder:
        return "abgeschlossen" if h.abgeschlossen_am else "wieder geöffnet"
    return "geändert"


def verlauf_eintraege(patient, bereich=None, person=None, grenze=500):
    from infusionen.models import Infusionsplan

    quellen = {
        "akte": Patient.history.filter(id=patient.id),
        "gewichte": Gewichtsmessung.history.filter(patient_id=patient.id),
        "kontakte": Kontakt.history.filter(patient_id=patient.id),
        "termine": Termin.history.filter(patient_id=patient.id),
        "dokumente": Dokument.history.filter(patient_id=patient.id),
        "infusionsplaene": Infusionsplan.history.filter(patient_id=patient.id),
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
    ergebnis = []
    for name, h in eintraege[:grenze]:
        aenderungen = []
        vorher = h.prev_record if h.history_type == "~" else None
        if vorher is not None:
            diff = h.diff_against(vorher)
            aenderungen = [{"feld": c.field, "alt": _kurz(c.old), "neu": _kurz(c.new)} for c in diff.changes]
        basis = {
            "objekt_id": h.id,
            "art": {"+": "angelegt", "~": "geändert", "-": "gelöscht"}[h.history_type],
            "zeitpunkt": h.history_date,
            "person": benutzername(h.history_user),
            "person_id": h.history_user_id,
            "grund": h.history_change_reason,
        }
        if name != "akte":
            ergebnis.append({**basis, "bereich": name, "aktion": _aktion(name, h, aenderungen),
                             "aenderungen": aenderungen})
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
            ergebnis.append({**basis, "bereich": gruppe, "aktion": _aktion("stammdaten", h, liste),
                             "aenderungen": liste})
    return ergebnis


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

    def pruefe_patient(self, patient):
        if not patienten_fuer(self.request.user).filter(pk=patient.pk).exists():
            raise serializers.ValidationError({"patient": "Patient nicht gefunden."})
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

    class Meta:
        model = Termin
        fields = ["id", "patient", "patient_name", "art", "ort", "ort_name", "faellig_am", "uhrzeit", "bei", "titel",
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
def _zuletzt_eingetragen(patienten, anzahl=10):
    """Neueste Einträge aus allen Bereichen (Entwurf 2 · „Zuletzt eingetragen“)."""
    from infusionen.models import Infusionsplan

    ids = list(patienten.values_list("id", flat=True))
    quellen = [
        ("kontakt", "Kontakt", Kontakt.history.filter(patient_id__in=ids, history_type="+")),
        ("gewicht", "Gewicht", Gewichtsmessung.history.filter(patient_id__in=ids, history_type="+")),
        ("dokument", "Dokument", Dokument.history.filter(patient_id__in=ids, history_type="+")),
        ("plan", "Infusionsplan-Entwurf", Infusionsplan.history.filter(patient_id__in=ids, history_type="+")),
        ("plan", "Infusionsplan freigegeben",
         Infusionsplan.history.filter(patient_id__in=ids, history_type="~", status="aktuell", freigegeben_am__isnull=False)),
    ]
    eintraege = []
    for bereich, bezeichnung, qs in quellen:
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
        ergebnis.append({"bereich": bereich, "bezeichnung": bezeichnung, "objekt_id": h.id,
                         "patient": h.patient_id, "name": namen.get(h.patient_id), "zeitpunkt": zeit,
                         "person": benutzername(h.history_user)})
        if len(ergebnis) == anzahl:
            break
    return ergebnis


def startseite_daten(user):
    from infusionen.models import Infusionsplan
    from stammdaten.models import Einstellungen

    heute = timezone.localdate()
    e = Einstellungen.aktuell()
    patienten = patienten_fuer(user).filter(abgeschlossen_am__isnull=True)
    termine = Termin.objects.filter(patient__in=patienten, erledigt_am__isnull=True).select_related(
        "patient", "ort", "angelegt_von")

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

    grenze = heute - timedelta(days=30 * e.plan_alter_warnung_monate)
    plaene = Infusionsplan.objects.filter(patient__in=patienten).select_related("patient", "erstellt_von",
                                                                               "freigegeben_von")

    def pl(qs):
        return [{"id": x.id, "patient": x.patient_id, "name": f"{x.patient.nachname}, {x.patient.vorname}",
                 "gueltig_ab": x.gueltig_ab, "status": x.status, "erstellt_am": x.erstellt_am,
                 "erstellt_von": benutzername(x.erstellt_von), "freigegeben_am": x.freigegeben_am}
                for x in qs[:50]]

    statistik = patienten if user.ist_test else patienten.filter(ist_test=False)
    return {
        "termine": {
            "ueberfaellig": t(termine.filter(faellig_am__lt=heute)),
            "heute": t(termine.filter(faellig_am=heute)),
            "naechste_7_tage": t(termine.filter(faellig_am__gte=heute, faellig_am__lte=heute + timedelta(days=7))),
        },
        "gewichtswarnungen": warnungen,
        "gewicht_schwelle": {"prozent": e.gewicht_warnung_prozent, "monate": e.gewicht_warnung_monate},
        "infusionsplaene": {
            "entwuerfe": pl(plaene.filter(status=Infusionsplan.Status.ENTWURF).order_by("-erstellt_am")),
            "aelter_als_grenze": pl(plaene.filter(status=Infusionsplan.Status.AKTUELL, gueltig_ab__lt=grenze)
                                    .order_by("gueltig_ab")),
            "grenze_monate": e.plan_alter_warnung_monate,
        },
        "pruefen": pruefliste(statistik),
        "zuletzt_eingetragen": _zuletzt_eingetragen(patienten),
        "zahlen": {
            "in_betreuung": statistik.count(),
            "mit_offenem_termin": statistik.filter(termine__erledigt_am__isnull=True).distinct().count(),
        },
    }


class StartseiteViewSet(viewsets.ViewSet):
    permission_classes = [recht("akten_lesen")]

    def list(self, request):
        return Response(startseite_daten(request.user))
