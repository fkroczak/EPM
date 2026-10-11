"""Stammdaten: lesen dürfen alle, ändern nur der Admin. Gelöscht wird nichts, nur deaktiviert."""
import re

from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import StammdatenRecht, VersorgerRecht
from audit.models import SystemEreignis, protokolliere

from .models import (Absenderangaben, Ansprechpartner, Arzt, Auswahlwert, Diagnosevorlage, Einstellungen,
                     Laborparameter, Logo, Praeparat, Versorger)


def _text(wert):
    from decimal import Decimal

    if wert is None or isinstance(wert, (bool, int, str)):
        return wert
    if isinstance(wert, (list, tuple)):
        return ", ".join(str(w) for w in wert) or "–"
    if isinstance(wert, Decimal):
        text = f"{wert:f}"
        return text.rstrip("0").rstrip(".").replace(".", ",") if "." in text else text
    return str(wert)


EINHEITEN = {"_monate": "Monate", "_jahre": "Jahre", "_prozent": "%", "_kg": "kg", "_cm": "cm", "_mmol": "mmol", "_g": "g",
             "_tag": "kcal", "_ml": "ml"}


def aenderungen_von(obj, vorher: dict):
    """{feld: [alt, neu, einheit]} und Feldbezeichnungen für das Audit-Log („von 6 auf 12 Monate geändert“)."""
    aenderungen, namen = {}, {}
    for feld, alt in vorher.items():
        neu = getattr(obj, feld)
        if alt != neu:
            einheit = next((e for endung, e in EINHEITEN.items() if feld.endswith(endung)), "")
            aenderungen[feld] = [_text(alt), _text(neu), einheit]
            try:
                namen[feld] = str(obj._meta.get_field(feld).verbose_name)
            except Exception:  # noqa: BLE001 – nur Beschriftung
                namen[feld] = feld
    return aenderungen, namen


class OhneLoeschen(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                   mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [StammdatenRecht]

    def perform_create(self, serializer):
        obj = serializer.save()
        protokolliere(SystemEreignis.Art.STAMMDATEN, self.request, objekt=f"{obj._meta.verbose_name}: {obj}",
                      aktion="angelegt")

    def perform_update(self, serializer):
        vorher = {f: getattr(serializer.instance, f) for f in serializer.validated_data}
        obj = serializer.save()
        aenderungen, namen = aenderungen_von(obj, vorher)
        protokolliere(SystemEreignis.Art.STAMMDATEN, self.request, objekt=f"{obj._meta.verbose_name}: {obj}",
                      aktion="geändert", felder=sorted(serializer.validated_data), aenderungen=aenderungen,
                      bezeichnungen=namen)


def neue_reihenfolge(request, queryset, gruppenfeld: str):
    """Reihenfolge per Ziehen speichern: {"ids": [...]} – alle aus derselben Liste/Kategorie."""
    ids = request.data.get("ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids) or len(set(ids)) != len(ids):
        return Response({"ids": "Bitte die IDs in der neuen Reihenfolge übergeben."}, status=status.HTTP_400_BAD_REQUEST)
    objekte = {o.id: o for o in queryset.filter(id__in=ids)}
    gruppen = {getattr(o, gruppenfeld) for o in objekte.values()}
    if len(objekte) != len(ids) or len(gruppen) != 1:
        return Response({"ids": "Unbekannte IDs oder gemischte Listen."}, status=status.HTTP_400_BAD_REQUEST)
    for i, pk in enumerate(ids):
        o = objekte[pk]
        if o.reihenfolge != (i + 1) * 10:
            o.reihenfolge = (i + 1) * 10
            o._history_user = request.user
            o.save(update_fields=["reihenfolge"])
    gruppe = gruppen.pop()
    protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt=f"{queryset.model._meta.verbose_name_plural}: {gruppe}",
                  aktion="Reihenfolge geändert")
    return Response({"reihenfolge": ids})


class AuswahlwertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auswahlwert
        fields = ["id", "liste", "wert", "reihenfolge", "aktiv"]


class AuswahlwertViewSet(OhneLoeschen):
    queryset = Auswahlwert.objects.all()
    serializer_class = AuswahlwertSerializer
    filterset_fields = ["liste", "aktiv"]
    pagination_class = None

    @action(detail=False, methods=["post"])
    def reihenfolge(self, request):
        return neue_reihenfolge(request, Auswahlwert.objects.all(), "liste")


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
    patienten_anzahl = serializers.SerializerMethodField()

    class Meta:
        model = Versorger
        fields = ["id", "name", "strasse", "plz", "ort", "telefon", "fax", "email", "notiz", "aktiv",
                  "ansprechpartner", "patienten_anzahl"]

    def get_patienten_anzahl(self, obj):
        """„94 Patienten in Betreuung“ (Entwurf 13): ohne abgeschlossene Akten und Testpatienten."""
        return obj.patienten.filter(abgeschlossen_am__isnull=True, ist_test=False).count()


class VersorgerViewSet(OhneLoeschen):
    permission_classes = [VersorgerRecht]
    queryset = Versorger.objects.prefetch_related("ansprechpartner")
    serializer_class = VersorgerSerializer
    filterset_fields = ["aktiv"]
    search_fields = ["name", "ort"]
    pagination_class = None


class ArztSerializer(serializers.ModelSerializer):
    patienten_anzahl = serializers.SerializerMethodField()

    class Meta:
        model = Arzt
        fields = ["id", "name", "praxis", "fachrichtung", "strasse", "plz", "ort", "telefon", "fax", "email", "notiz",
                  "aktiv", "patienten_anzahl"]

    def validate_name(self, wert):
        if not wert.strip():
            raise serializers.ValidationError("Bitte einen Namen eingeben.")
        return wert.strip()

    def get_patienten_anzahl(self, obj):
        """Zugeordnete Patienten in Betreuung (ohne Testpatienten), wie bei den Versorgern."""
        return (obj.zuordnungen.filter(aktiv=True, patient__abgeschlossen_am__isnull=True, patient__ist_test=False)
                .values("patient_id").distinct().count())


class ArztViewSet(OhneLoeschen):
    """Gemeinsame Ärzteliste (Festlegung 01.10.2026). Pflegen mit dem Recht „Versorger, Ansprechpartner und
    Ärzte pflegen“; lesen alle Angemeldeten. Nie löschen, nur deaktivieren."""

    permission_classes = [VersorgerRecht]
    queryset = Arzt.objects.all()
    serializer_class = ArztSerializer
    filterset_fields = ["aktiv"]
    search_fields = ["name", "praxis", "fachrichtung", "ort"]
    pagination_class = None

    @action(detail=True, methods=["get"])
    def patienten(self, request, pk=None):
        """Patienten in Betreuung, denen dieser Arzt zugeordnet ist (mit Rolle)."""
        from patienten.api import PatientListSerializer
        from epm.api_basis import patienten_fuer

        arzt = self.get_object()
        qs = patienten_fuer(request.user).filter(aerzte__arzt=arzt, aerzte__aktiv=True,
                                                 abgeschlossen_am__isnull=True).distinct()
        return Response(PatientListSerializer(qs, many=True).data)


class PraeparatSerializer(serializers.ModelSerializer):
    anzeige = serializers.CharField(source="__str__", read_only=True)
    in_plaenen = serializers.IntegerField(read_only=True)

    class Meta:
        model = Praeparat
        fields = ["id", "kategorie", "name", "konzentration", "einheit", "hinweis", "reihenfolge", "aktiv",
                  "anzeige", "in_plaenen"]


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

    @action(detail=False, methods=["post"])
    def reihenfolge(self, request):
        return neue_reihenfolge(request, Praeparat.objects.all(), "kategorie")


class EinstellungenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Einstellungen
        exclude = ["id"]
        # Vorlagen › Dokumentvorlagen › Entwurfsmodus; Administration › System
        read_only_fields = ["vordrucke_ohne_entwurf", "musterdaten_automatisch", "import_ausgeblendet"]

    def validate(self, attrs):
        from .models import ERKLAERUNGSARTEN, kontaktstufen_fehler

        attrs = super().validate(attrs)
        e = self.instance
        for unten, oben in Einstellungen.GRENZPAARE:
            if attrs.get(unten, getattr(e, unten)) >= attrs.get(oben, getattr(e, oben)):
                raise serializers.ValidationError({unten: "Untere Grenze muss kleiner als obere Grenze sein."})
        # Kontakt fällig in zwei Stufen (S04): „bald fällig“ vor „überfällig“
        fehler = kontaktstufen_fehler(attrs.get("kontakt_bald_monate", getattr(e, "kontakt_bald_monate", None)),
                                      attrs.get("kontakt_ueberfaellig_monate",
                                                getattr(e, "kontakt_ueberfaellig_monate", None)))
        if fehler:
            raise serializers.ValidationError(fehler)
        from .models import scans_fehler

        fehler = scans_fehler(*(attrs.get(f, getattr(e, f, None)) for f in (
            "scans_frist_tage", "scans_hoechst_tage", "scans_verlaengerung_tage", "scans_max_mb", "scans_max_anzahl")))
        if fehler:
            raise serializers.ValidationError(fehler)
        if "ocr_fachwoerter" in attrs:
            woerter = [w.strip() for w in attrs["ocr_fachwoerter"].splitlines() if w.strip()]
            if len(woerter) > 5000 or any(len(w) > 60 or " " in w for w in woerter):
                raise serializers.ValidationError({"ocr_fachwoerter": "Je Zeile ein Wort ohne Leerzeichen (höchstens "
                                                                      "60 Zeichen, höchstens 5000 Wörter)."})
            attrs["ocr_fachwoerter"] = "\n".join(dict.fromkeys(woerter))
        from .models import vorgabe_fehler

        fehler = vorgabe_fehler({f: attrs[f] for f in Einstellungen.VORGABE_JE_KG if f in attrs})
        if fehler:
            raise serializers.ValidationError(fehler)
        if "plan_gewicht_alter_monate" in attrs and not 1 <= attrs["plan_gewicht_alter_monate"] <= 60:
            raise serializers.ValidationError({"plan_gewicht_alter_monate": "Bitte 1 bis 60 Monate angeben."})
        if "gewicht_fehlt_monate" in attrs and not 1 <= attrs["gewicht_fehlt_monate"] <= 120:
            raise serializers.ValidationError({"gewicht_fehlt_monate": "Bitte 1 bis 120 Monate angeben."})
        if "wiedervorlage_tage" in attrs and not 1 <= attrs["wiedervorlage_tage"] <= 365:
            raise serializers.ValidationError({"wiedervorlage_tage": "Bitte 1 bis 365 Tage angeben."})
        # Infoblatt an die Praxis (F177): Vorlauf kürzer als der Zeitraum, sonst stünde der Hinweis immer da
        rhythmus = attrs.get("infoblatt_rhythmus", getattr(e, "infoblatt_rhythmus", "woche"))
        vorlauf = attrs.get("infoblatt_vorlauf_tage", getattr(e, "infoblatt_vorlauf_tage", 3))
        hoechstens = 6 if rhythmus == "woche" else 27
        if ("infoblatt_vorlauf_tage" in attrs or "infoblatt_rhythmus" in attrs) and not 1 <= vorlauf <= hoechstens:
            raise serializers.ValidationError({"infoblatt_vorlauf_tage": f"Bitte 1 bis {hoechstens} Tage angeben."})
        # Datenschutz: Fristen und die Erklärungen, die vorliegen sollen
        if "aufbewahrung_jahre" in attrs and not 1 <= attrs["aufbewahrung_jahre"] <= 100:
            raise serializers.ValidationError({"aufbewahrung_jahre": "Bitte 1 bis 100 Jahre angeben."})
        if "abschluss_pruefen_monate" in attrs and attrs["abschluss_pruefen_monate"] < 1:
            raise serializers.ValidationError({"abschluss_pruefen_monate": "Bitte mindestens 1 Monat angeben."})
        if "pflicht_erklaerungen" in attrs:
            liste = attrs["pflicht_erklaerungen"]
            if (not isinstance(liste, list) or any(a not in ERKLAERUNGSARTEN for a in liste)
                    or len(set(liste)) != len(liste)):
                raise serializers.ValidationError({"pflicht_erklaerungen": "Unbekannte Erklärung."})
            attrs["pflicht_erklaerungen"] = [a for a in ERKLAERUNGSARTEN if a in liste]  # feste Reihenfolge
        return attrs


# Diese Einstellungen entscheiden, wann Akten gelöscht werden dürfen und wann Einträge des Audit-Logs entfernt
# werden – sie ändert nur, wer auch über Datenschutz-Anfragen entscheidet (nicht jede Person mit „Vorlagen pflegen“).
DATENSCHUTZ_FELDER = ["aufbewahrung_jahre", "abschluss_pruefen_monate", "protokoll_aufbewahrung_jahre",
                      "pflicht_erklaerungen"]


class EinstellungenView(APIView):
    permission_classes = [StammdatenRecht]

    def get(self, request):
        return Response(EinstellungenSerializer(Einstellungen.aktuell()).data)

    def patch(self, request):
        e = Einstellungen.aktuell()
        s = EinstellungenSerializer(e, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        geaendert = [f for f in DATENSCHUTZ_FELDER if f in s.validated_data and s.validated_data[f] != getattr(e, f)]
        if geaendert and not request.user.hat_recht("datenschutz_entscheiden"):
            raise PermissionError("Dafür fehlt das Recht „Datenschutz: Anfragen entscheiden, Verarbeitung einschränken“.")
        vorher = {f: getattr(e, f) for f in s.validated_data}
        s.save()
        aenderungen, namen = aenderungen_von(s.instance, vorher)
        protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt="Einstellungen", felder=sorted(s.validated_data),
                      aenderungen=aenderungen, bezeichnungen=namen)
        return Response(s.data)


# ================================================================= Briefkopf und Logo (Entwurf 18)
ABSENDER_FELDER = ["name", "strasse", "plz", "ort", "telefon", "fax", "email", "internet", "fusszeile"]


class AbsenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Absenderangaben
        fields = ABSENDER_FELDER


def briefkopf_daten():
    from epm.firma import aktive_firma

    e = Einstellungen.aktuell()
    logo = Logo.aktuell()
    firma = aktive_firma()
    return {
        "aktiv": e.absender,
        # je Firma (11.10.2026): welcher Briefkopf und welches Logo gerade gelten
        "firma": {"kuerzel": firma.kuerzel, "name": firma.name, "absender": firma.absender or e.absender}
        if firma else None,
        "absender": {art: AbsenderSerializer(obj).data for art, obj in Absenderangaben.alle().items()},
        "arten": [{"code": c, "name": n} for c, n in Einstellungen.Absender.choices],
        "logo": {"vorhanden": logo is not None, "mime": logo.mime, "sha256": logo.sha256, "breite": logo.breite,
                 "hoehe": logo.hoehe, "hochgeladen_am": logo.hochgeladen_am} if logo else {"vorhanden": False},
    }


class BriefkopfView(APIView):
    """GET (alle Angemeldeten) und PATCH (Recht „Vorlagen pflegen“):
    {"aktiv"?: "stiftung"|"gug", "absender"?: {"stiftung"?: {...}, "gug"?: {...}}}"""

    permission_classes = [StammdatenRecht]

    def get(self, request):
        return Response(briefkopf_daten())

    def patch(self, request):
        from django.db import transaction

        aktiv = request.data.get("aktiv")
        absender = request.data.get("absender") or {}
        if aktiv is not None and aktiv not in Einstellungen.Absender.values:
            return Response({"aktiv": "Unbekannter Absender."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(absender, dict) or set(absender) - set(Einstellungen.Absender.values):
            return Response({"absender": "Unbekannter Absender."}, status=status.HTTP_400_BAD_REQUEST)
        vorhanden = Absenderangaben.alle()
        serializers_ = {}
        for art, werte in absender.items():
            s = AbsenderSerializer(vorhanden[art], data=werte, partial=True)
            if not s.is_valid():
                return Response({"absender": {art: s.errors}}, status=status.HTTP_400_BAD_REQUEST)
            serializers_[art] = s
        geaendert = []
        with transaction.atomic():
            for art, s in serializers_.items():
                vorher = {f: getattr(s.instance, f) for f in s.validated_data}
                s.instance._history_user = request.user
                s.save()
                aenderungen, namen = aenderungen_von(s.instance, vorher)
                if aenderungen:
                    geaendert.append((art, aenderungen, namen))
            if aktiv is not None:
                e = Einstellungen.aktuell()
                if e.absender != aktiv:
                    vorher = {"absender": e.absender}
                    e.absender = aktiv
                    e.save()
                    aenderungen, namen = aenderungen_von(e, vorher)
                    geaendert.append(("auswahl", aenderungen, namen))
        for art, aenderungen, namen in geaendert:
            protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Briefkopf ({art})", aenderungen=aenderungen,
                          bezeichnungen=namen)
        return Response(briefkopf_daten())


def _png_groesse(kopf: bytes):
    if kopf[:8] != b"\x89PNG\r\n\x1a\n" or kopf[12:16] != b"IHDR":
        return None
    return int.from_bytes(kopf[16:20], "big"), int.from_bytes(kopf[20:24], "big")


def _svg_pruefen(inhalt: bytes) -> str | None:
    """Fehlermeldung oder None. Kein Skript, keine Ereignisse, keine externen Verweise."""
    import xml.etree.ElementTree as ET

    if b"<!DOCTYPE" in inhalt or b"<!ENTITY" in inhalt:
        return "SVG mit DOCTYPE oder Entitäten wird nicht angenommen."
    try:
        wurzel = ET.fromstring(inhalt)
    except ET.ParseError:
        return "Die Datei ist kein gültiges SVG."
    if not wurzel.tag.endswith("svg"):
        return "Die Datei ist kein SVG."
    for el in wurzel.iter():
        name = el.tag.rsplit("}", 1)[-1].lower()
        if name in ("script", "foreignobject", "iframe", "embed", "object"):
            return "SVG mit Skripten oder eingebetteten Inhalten wird nicht angenommen."
        for attr, wert in el.attrib.items():
            a = attr.rsplit("}", 1)[-1].lower()
            if a.startswith("on"):
                return "SVG mit Ereignis-Attributen wird nicht angenommen."
            if a == "href" and not (wert.startswith("#") or wert.startswith("data:image/")):
                return "SVG mit externen Verweisen wird nicht angenommen."
    return None


class LogoView(APIView):
    """GET: das aktuelle Logo (öffentlich, auch für die Anmeldeseite). POST: neues Logo (PNG oder SVG).
    Je Firma (11.10.2026): das Logo der aktiven Firma bzw. ``?firma=rg``; hochgeladen wird für die aktive Firma."""

    permission_classes = [StammdatenRecht]
    MAX_BYTES = 2 * 1024 * 1024

    def get_permissions(self):
        from rest_framework.permissions import AllowAny

        return [AllowAny()] if self.request.method == "GET" else super().get_permissions()

    def get(self, request):
        from django.conf import settings
        from django.http import FileResponse, Http404

        from stammdaten.models import Firma

        firma = Firma.objects.filter(kuerzel=request.query_params.get("firma") or "", aktiv=True).first()
        logo = Logo.aktuell(firma)
        if logo is None:
            raise Http404("Kein Logo hochgeladen.")
        pfad = settings.EPM_DOKUMENTE / logo.datei
        if not pfad.exists():
            raise Http404("Logo-Datei fehlt.")
        antwort = FileResponse(open(pfad, "rb"), content_type=logo.mime)
        antwort["Cache-Control"] = "private, max-age=300"
        antwort["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
        antwort["ETag"] = f'"{logo.sha256}"'
        return antwort

    def post(self, request):
        import hashlib
        import os
        import tempfile

        from django.conf import settings

        datei = request.FILES.get("datei")
        if datei is None:
            return Response({"datei": "Bitte eine Datei auswählen."}, status=status.HTTP_400_BAD_REQUEST)
        if datei.size > self.MAX_BYTES:
            return Response({"datei": "Das Logo darf höchstens 2 MB groß sein."}, status=status.HTTP_400_BAD_REQUEST)
        inhalt = datei.read()
        breite = hoehe = None
        groesse = _png_groesse(inhalt[:32])
        if groesse:
            mime, endung = "image/png", "png"
            breite, hoehe = groesse
            if breite < 600:
                return Response({"datei": f"Das Logo ist {breite} px breit, nötig sind mindestens 600 px."},
                                status=status.HTTP_400_BAD_REQUEST)
            if breite <= hoehe:
                return Response({"datei": "Bitte ein Logo im Querformat hochladen."}, status=status.HTTP_400_BAD_REQUEST)
        elif b"<svg" in inhalt[:4096]:
            meldung = _svg_pruefen(inhalt)
            if meldung:
                return Response({"datei": meldung}, status=status.HTTP_400_BAD_REQUEST)
            mime, endung = "image/svg+xml", "svg"
        else:
            return Response({"datei": "Erlaubt sind PNG und SVG."}, status=status.HTTP_400_BAD_REQUEST)
        from epm.firma import aktive_firma

        firma = aktive_firma()
        sha = hashlib.sha256(inhalt).hexdigest()
        relativ = f"_system/logo-{f'{firma.kuerzel}-' if firma else ''}{sha[:16]}.{endung}"
        ziel = settings.EPM_DOKUMENTE / relativ
        ziel.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        if not ziel.exists():
            fd, tmp = tempfile.mkstemp(dir=ziel.parent, prefix=".logo-")
            with os.fdopen(fd, "wb") as f:
                f.write(inhalt)
            os.chmod(tmp, 0o640)
            os.replace(tmp, ziel)
        logo = Logo.objects.filter(datei=relativ).first()
        if logo is None:
            logo = Logo.objects.create(datei=relativ, mime=mime, sha256=sha, breite=breite, hoehe=hoehe,
                                       hochgeladen_von=request.user, firma=firma)
        else:  # dasselbe Logo erneut: wieder als aktuelles markieren
            Logo.objects.filter(pk=logo.pk).update(hochgeladen_am=timezone.now(), hochgeladen_von=request.user)
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt="Logo", aktion="Logo hochgeladen", sha256=sha,
                      mime=mime)
        return Response(briefkopf_daten(), status=status.HTTP_201_CREATED)


# ================================================================= Laborparameter (F112) und Diagnosen (F117)
class LaborparameterSerializer(serializers.ModelSerializer):
    gruppe_name = serializers.CharField(source="get_gruppe_display", read_only=True)
    in_befunden = serializers.IntegerField(read_only=True)

    class Meta:
        model = Laborparameter
        fields = ["id", "gruppe", "gruppe_name", "name", "kurzname", "einheit", "referenz_von", "referenz_bis",
                  "reihenfolge", "aktiv", "in_befunden", "suchbegriffe"]

    def validate_suchbegriffe(self, wert):
        teile = [t.strip() for t in re.split(r"[;,\n]", wert or "") if t.strip()]
        return ", ".join(dict.fromkeys(teile))[:300]

    def validate_name(self, wert):
        if not wert.strip():
            raise serializers.ValidationError("Bitte einen Namen angeben.")
        return wert.strip()

    def validate(self, attrs):
        von = attrs.get("referenz_von", getattr(self.instance, "referenz_von", None))
        bis = attrs.get("referenz_bis", getattr(self.instance, "referenz_bis", None))
        if von is not None and bis is not None and von > bis:
            raise serializers.ValidationError({"referenz_bis": "„Referenz bis“ muss größer oder gleich „Referenz von“ sein."})
        return attrs


class LaborparameterViewSet(OhneLoeschen):
    """Katalog der Laborwerte (Vorlagen › Laborparameter). Lesen darf jeder Angemeldete – die Erfassungsmaske
    eines Befunds braucht ihn –, ändern nur mit „Vorlagen pflegen“."""

    queryset = Laborparameter.objects.all()
    serializer_class = LaborparameterSerializer
    filterset_fields = ["gruppe", "aktiv"]
    search_fields = ["name", "kurzname"]
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Count

        return Laborparameter.objects.annotate(in_befunden=Count("werte", distinct=True))

    @action(detail=False, methods=["post"])
    def reihenfolge(self, request):
        return neue_reihenfolge(request, Laborparameter.objects.all(), "gruppe")


class DiagnosevorlageSerializer(serializers.ModelSerializer):
    anzeige = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Diagnosevorlage
        fields = ["id", "icd_code", "bezeichnung", "aktiv", "anzeige", "angelegt_am"]
        read_only_fields = ["angelegt_am"]

    def validate(self, attrs):
        from django.core.exceptions import ValidationError as DjangoValidationError

        eintrag = self.instance or Diagnosevorlage()
        for feld, wert in attrs.items():
            setattr(eintrag, feld, wert)
        try:
            eintrag.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict if hasattr(e, "error_dict") else {"fehler": e.messages})
        attrs["icd_code"] = eintrag.icd_code
        return attrs


class DiagnosevorlageViewSet(OhneLoeschen):
    """Die Liste der Diagnosen mit ICD-Code (Vorlagen › Diagnosen). Sie wächst beim Eintragen in einer Akte
    von allein mit (F117); hier wird sie korrigiert und ausgeblendet."""

    queryset = Diagnosevorlage.objects.all()
    serializer_class = DiagnosevorlageSerializer
    filterset_fields = ["aktiv"]
    search_fields = ["bezeichnung", "icd_code"]
    pagination_class = None
