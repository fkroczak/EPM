"""API der Dokumentenautomation (Anforderungsspezifikation RGC, 26.10.2026).

Fälle der Akte – ``/api/faelle/?patient=ID``: anlegen, ändern, ``POST …/{id}/paket/`` (Dokumente des Pakets anlegen),
``POST …/{id}/abschliessen/`` bzw. ``…/wieder-oeffnen/``.

Dokumente eines Falls – ``/api/falldokumente/?fall=ID``: anlegen (Art, ggf. Vorlage), ändern (Titel, Freitext,
Rechnungsdatum, Zahlungsziel) und Entwürfe entfernen, solange nicht final; ``GET …/{id}/vorschau/`` (aktueller Stand,
Wasserzeichen VORSCHAU), ``POST …/{id}/erzeugen/`` (neue Fassung), ``GET …/{id}/versionen/``,
``GET …/{id}/pdf/?fassung=N`` (gespeicherte Fassung, Prüfsumme geprüft; ohne Angabe die neueste),
``GET/POST …/{id}/docx/`` (Freitexte als DOCX herunterladen bzw. bearbeitete DOCX übernehmen → neue Fassung),
``POST …/{id}/finalisieren/`` (Recht „Fall-Dokumente finalisieren“; ``weg`` signatur | signatur_extern | scan |
finalisiert, ``unterzeichner``, ``kennwort``, ``datei``, ``notiz``), ``POST …/{id}/stornieren/`` (finale Rechnung).

Rechnungspositionen – ``/api/rechnungspositionen/?dokument=ID`` (bis zur Finalisierung; ``leistung`` übernimmt Text
und Preis aus dem Katalog). Stammdaten (Recht „Vorlagen pflegen“, lesen alle): ``/api/leistungen/`` (+ ``import/``
als CSV), ``/api/kostentraegertypen/`` (+ ``optionen/``), ``/api/kooperationspartner/``, ``/api/unterzeichner/``
(+ ``{id}/zertifikat/`` hochladen bzw. entfernen – die Person selbst oder wer Vorlagen pflegt).

Fälle anlegen, ändern und PDFs erzeugen darf, wer Einträge erfassen darf; Admins wie überall nur bei Testpatienten.
"""
import csv
import hashlib
import io
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import HttpResponse
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import EintragRecht, FinalisierenRecht, StammdatenRecht
from audit.bereinigung import akte_text
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import FirmaFeld, ModelClean, benutzername, patienten_fuer, wahr
from patienten.api import AktenEintragViewSet
from stammdaten.api import OhneLoeschen

from . import erzeugung
from .models import (Behandlungsfall, DokumentVersion, FallDokument, Kooperationspartner, Kostentraegertyp, Leistung,
                     Rechnungsposition, Unterzeichner)
from .pakete import FESTE_ARTEN, titel_fuer


def _log(request, dok_oder_fall, aktion, **details):
    if isinstance(dok_oder_fall, FallDokument):
        objekt = f"Falldokument {dok_oder_fall.pk}"
        details = {"titel": dok_oder_fall.titel, "fall": dok_oder_fall.fall.nummer, **details}
    else:
        objekt = f"Fall {dok_oder_fall.nummer}"
    protokolliere(SystemEreignis.Art.FALL, request, objekt=objekt, aktion=aktion,
                  patient=dok_oder_fall.patient.nummer, patient_id=dok_oder_fall.patient_id, **details)


# ====================================================================== Stammdaten
class KostentraegertypSerializer(ModelClean, serializers.ModelSerializer):
    class Meta:
        model = Kostentraegertyp
        fields = ["id", "kuerzel", "name", "land", "beschreibung", "paket", "reihenfolge", "aktiv"]

    def validate_paket(self, paket):
        from .pakete import pruefe_paket

        fehler = pruefe_paket(paket)
        if fehler:
            raise serializers.ValidationError(fehler)
        return paket


class KooperationspartnerSerializer(ModelClean, serializers.ModelSerializer):
    class Meta:
        model = Kooperationspartner
        fields = ["id", "name", "kurzname", "anschrift", "kontakt", "aktiv"]


class UnterzeichnerSerializer(ModelClean, serializers.ModelSerializer):
    hat_zertifikat = serializers.BooleanField(read_only=True)
    benutzer_name = serializers.SerializerMethodField()

    class Meta:
        model = Unterzeichner
        fields = ["id", "name", "funktion", "benutzer", "benutzer_name", "hat_zertifikat", "zertifikat_info",
                  "zertifikat_bis", "reihenfolge", "aktiv"]
        read_only_fields = ["zertifikat_info", "zertifikat_bis"]

    def get_benutzer_name(self, obj):
        return benutzername(obj.benutzer)

    def update(self, instance, validated_data):
        # anderes Konto: das hinterlegte Zertifikat gehört der bisherigen Person
        if "benutzer" in validated_data and validated_data["benutzer"] != instance.benutzer:
            instance.zertifikat, instance.zertifikat_info, instance.zertifikat_bis = None, "", None
        return super().update(instance, validated_data)


class LeistungSerializer(ModelClean, serializers.ModelSerializer):
    class Meta:
        model = Leistung
        fields = ["id", "code", "bezeichnung", "bezeichnung_lv", "bezeichnung_en", "gruppe", "einheit", "preis",
                  "ust_satz", "aktiv"]


class KostentraegertypViewSet(OhneLoeschen):
    queryset = Kostentraegertyp.objects.all()
    serializer_class = KostentraegertypSerializer
    filterset_fields = ["aktiv"]
    pagination_class = None

    @action(detail=False, methods=["get"])
    def optionen(self, request):
        """Was in ein Paket kann: feste Dokumentarten und die Vorlagen der RGC (ohne die Fall-Vorlagen selbst)."""
        from vorlagen.models import EigenesSchreiben
        from vorlagen.portal import GRUPPEN

        liste = [{"wert": k, "name": v, "gruppe": "Dokumente des Falls"} for k, v in FESTE_ARTEN.items()]
        liste += [{"wert": e.schluessel, "name": e.name, "gruppe": GRUPPEN.get(e.gruppe, e.gruppe)}
                  for e in EigenesSchreiben.objects.filter(aktiv=True).exclude(gruppe="fall")
                  .order_by("gruppe", "name")]
        return Response(liste)


class KooperationspartnerViewSet(OhneLoeschen):
    queryset = Kooperationspartner.objects.all()
    serializer_class = KooperationspartnerSerializer
    filterset_fields = ["aktiv"]
    search_fields = ["name", "kurzname"]
    pagination_class = None


class UnterzeichnerViewSet(OhneLoeschen):
    queryset = Unterzeichner.objects.select_related("benutzer")
    serializer_class = UnterzeichnerSerializer
    filterset_fields = ["aktiv"]
    pagination_class = None
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action == "zertifikat":
            return [EintragRecht()]
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def konten(self, request):
        """Benutzerkonten zum Verknüpfen (nur Name und ID; ohne Testbenutzer und Konten ohne Login)."""
        from accounts.models import User
        from epm.api_basis import sichtbare_benutzer

        if not request.user.hat_recht("vorlagen_pflegen"):
            raise PermissionError("Dafür fehlt das Recht „Vorlagen pflegen“.")
        qs = sichtbare_benutzer(request.user, User.objects.filter(is_active=True, ist_test=False))
        return Response([{"id": u.pk, "name": benutzername(u)} for u in qs.order_by("last_name", "first_name")])

    @action(detail=True, methods=["post", "delete"])
    def zertifikat(self, request, pk=None):
        """PKCS#12-Datei mit Kennwort hochladen (geprüft, Kennwort wird nicht gespeichert) bzw. entfernen."""
        u = self.get_object()
        if request.method == "DELETE":
            if u.benutzer_id != request.user.pk and not request.user.hat_recht("vorlagen_pflegen"):
                raise PermissionError("Das Zertifikat entfernt die Person selbst oder wer Vorlagen pflegt.")
            u.zertifikat, u.zertifikat_info, u.zertifikat_bis = None, "", None
            u.save(update_fields=["zertifikat", "zertifikat_info", "zertifikat_bis"])
            protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt=f"Unterzeichner: {u}",
                          aktion="Zertifikat entfernt")
            return Response(self.get_serializer(u).data)
        # Hochladen nur die Person selbst – sonst könnte jemand mit eigenem Zertifikat unter fremdem Namen signieren
        if u.benutzer_id is None or u.benutzer_id != request.user.pk:
            raise PermissionError("Das Zertifikat hinterlegt nur die Person selbst, angemeldet mit dem verknüpften "
                                  "Benutzerkonto.")
        datei = request.FILES.get("datei")
        if datei is None or datei.size > 1024 * 1024:
            return Response({"datei": "Bitte die PKCS#12-Datei (.p12/.pfx, höchstens 1 MB) wählen."},
                            status=status.HTTP_400_BAD_REQUEST)
        inhalt = datei.read()
        info = zertifikat_lesen(inhalt, str(request.data.get("kennwort") or ""))
        u.zertifikat, u.zertifikat_info, u.zertifikat_bis = inhalt, info["info"], info["bis"]
        u.save(update_fields=["zertifikat", "zertifikat_info", "zertifikat_bis"])
        protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt=f"Unterzeichner: {u}",
                      aktion="Zertifikat hinterlegt", zertifikat=info["info"])
        return Response(self.get_serializer(u).data)


def zertifikat_lesen(inhalt: bytes, kennwort: str) -> dict:
    from cryptography.hazmat.primitives.serialization import pkcs12

    try:
        schluessel, zert, _ = pkcs12.load_key_and_certificates(inhalt, kennwort.encode() or None)
    except Exception:
        raise serializers.ValidationError({"kennwort": "Datei oder Kennwort passen nicht (PKCS#12 erwartet)."})
    if schluessel is None or zert is None:
        raise serializers.ValidationError({"datei": "Die Datei enthält keinen privaten Schlüssel mit Zertifikat."})
    bis = zert.not_valid_after_utc
    return {"info": f"{zert.subject.rfc4514_string()} · ausgestellt von {zert.issuer.rfc4514_string()}"[:300],
            "bis": bis}


class LeistungViewSet(OhneLoeschen):
    queryset = Leistung.objects.all()
    serializer_class = LeistungSerializer
    filterset_fields = ["aktiv", "gruppe"]
    search_fields = ["code", "bezeichnung", "bezeichnung_lv", "bezeichnung_en"]
    pagination_class = None
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @action(detail=False, methods=["post"], url_path="import")
    @transaction.atomic
    def importieren(self, request):
        """CSV (Semikolon, UTF-8, Kopfzeile): code;bezeichnung;bezeichnung_lv;bezeichnung_en;gruppe;einheit;preis;
        ust_satz. Bekannte Codes werden aktualisiert, neue angelegt. Fehlerhafte Zeilen → nichts wird übernommen."""
        datei = request.FILES.get("datei")
        if datei is None or datei.size > 2 * 1024 * 1024:
            return Response({"datei": "Bitte eine CSV-Datei (höchstens 2 MB) wählen."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            text = datei.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response({"datei": "Die Datei ist nicht UTF-8-kodiert."}, status=status.HTTP_400_BAD_REQUEST)
        leser = csv.DictReader(io.StringIO(text), delimiter=";")
        if not leser.fieldnames or not {"code", "bezeichnung", "preis"} <= {f.strip() for f in leser.fieldnames}:
            return Response({"datei": "Kopfzeile mit mindestens code;bezeichnung;preis erwartet."},
                            status=status.HTTP_400_BAD_REQUEST)
        fehler, neu, geaendert = [], 0, 0
        for nr, zeile in enumerate(leser, 2):
            z = {(k or "").strip(): (v or "").strip() for k, v in zeile.items()}
            try:
                preis = Decimal(z.get("preis", "").replace(".", "").replace(",", ".") if "," in z.get("preis", "")
                                else z.get("preis", ""))
                ust = Decimal((z.get("ust_satz") or "0").replace(",", "."))
            except InvalidOperation:
                fehler.append(f"Zeile {nr}: Preis bzw. USt. ist keine Zahl.")
                continue
            daten = {k: z[k] for k in ("bezeichnung", "bezeichnung_lv", "bezeichnung_en", "gruppe", "einheit")
                     if z.get(k)}
            daten.update(preis=preis, ust_satz=ust)
            if not z.get("code") or not z.get("bezeichnung"):
                fehler.append(f"Zeile {nr}: Code und Bezeichnung fehlen.")
                continue
            obj = Leistung.objects.filter(code=z["code"]).first()
            s = LeistungSerializer(obj, data={"code": z["code"], **daten}, partial=obj is not None)
            if not s.is_valid():
                fehler.append(f"Zeile {nr}: " + "; ".join(f"{k}: {' '.join(map(str, v))}" for k, v in s.errors.items()))
                continue
            s.save()
            neu, geaendert = (neu + 1, geaendert) if obj is None else (neu, geaendert + 1)
        if fehler:
            transaction.set_rollback(True)
            return Response({"datei": fehler[:20]}, status=status.HTTP_400_BAD_REQUEST)
        protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt="Leistungskatalog", aktion="CSV übernommen",
                      neu=neu, geaendert=geaendert)
        return Response({"neu": neu, "geaendert": geaendert})


# ====================================================================== Fälle
class FallSerializer(FirmaFeld, ModelClean, serializers.ModelSerializer):
    kostentraegertyp_name = serializers.CharField(source="kostentraegertyp.name", read_only=True)
    kooperationspartner_name = serializers.CharField(source="kooperationspartner.name", read_only=True, default=None)
    behandelnder_arzt_name = serializers.CharField(source="behandelnder_arzt.name", read_only=True, default=None)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    erstellt_von_name = serializers.SerializerMethodField()
    dokumente_stand = serializers.SerializerMethodField()

    class Meta:
        model = Behandlungsfall
        fields = ["id", "patient", "nummer", "status", "status_name", "titel", "kostentraegertyp",
                  "kostentraegertyp_name", "kostentraeger", "land", "versichertennummer", "aktenzeichen",
                  "kooperationspartner", "kooperationspartner_name", "rechnungsempfaenger", "sprache", "fachbereich",
                  "aufnahme", "entlassung", "op_datum", "eingriff", "diagnose", "behandelnder_arzt",
                  "behandelnder_arzt_name", "operateur", "assistenz", "anaesthesie", "op_indikation", "op_verlauf",
                  "op_befund", "entlass_verlauf", "entlass_befunde", "entlass_medikation", "entlass_empfehlung",
                  "konsil_empfaenger", "konsil_fragestellung", "konsil_befund", "konsil_beurteilung", "bemerkung",
                  "erstellt_am", "erstellt_von_name", "dokumente_stand"]
        read_only_fields = ["nummer", "status", "erstellt_am"]

    def get_erstellt_von_name(self, obj):
        return benutzername(obj.erstellt_von)

    def get_dokumente_stand(self, obj):
        stand = {"entwurf": 0, "erzeugt": 0, "final": 0}
        for s in obj.dokumente.values_list("status", flat=True):
            stand[s] = stand.get(s, 0) + 1
        return stand

    def validate_patient(self, patient):
        if self.instance and patient != self.instance.patient:
            raise serializers.ValidationError("Der Patient kann nicht geändert werden.")
        request = self.context.get("request")
        if request is not None and not patienten_fuer(request.user).filter(pk=patient.pk).exists():
            raise serializers.ValidationError("Patient nicht gefunden.")
        return patient

    def _aktiv(self, wert, feld):
        if wert is not None and not wert.aktiv and (self.instance is None or getattr(self.instance, f"{feld}_id") != wert.pk):
            raise serializers.ValidationError("Dieser Eintrag ist ausgeblendet.")
        return wert

    def validate_kostentraegertyp(self, wert):
        return self._aktiv(wert, "kostentraegertyp")

    def validate_kooperationspartner(self, wert):
        return self._aktiv(wert, "kooperationspartner")

    def validate_behandelnder_arzt(self, wert):
        return self._aktiv(wert, "behandelnder_arzt")


class FallViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, mixins.DestroyModelMixin):
    model = Behandlungsfall
    serializer_class = FallSerializer
    filterset_fields = ["patient", "status"]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().select_related("kostentraegertyp", "kooperationspartner", "behandelnder_arzt",
                                                     "erstellt_von")

    @transaction.atomic
    def perform_create(self, serializer):
        patient = serializer.validated_data["patient"]
        self.pruefe_patient(patient)
        daten = serializer.validated_data
        fall = serializer.save(erstellt_von=self.request.user,
                               versichertennummer=daten.get("versichertennummer") or patient.versichertennummer,
                               kostentraeger=daten.get("kostentraeger") or patient.krankenkasse)
        _log(self.request, fall, "Fall angelegt", typ=str(fall.kostentraegertyp))
        if wahr(self.request.query_params.get("paket", "1")):
            from .pakete import paket_anlegen

            neu = paket_anlegen(fall, self.request.user)
            if neu:
                _log(self.request, fall, "Dokumentenpaket angelegt", dokumente=[d.titel for d in neu])

    def perform_update(self, serializer):
        fall = serializer.instance
        self.pruefe_patient(fall.patient)
        fall.pruefe_offen()
        fall._history_user = self.request.user
        serializer.save()

    def perform_destroy(self, instance):
        self.pruefe_patient(instance.patient)
        instance._history_user = self.request.user
        nummer = instance.nummer
        with transaction.atomic():
            for d in instance.dokumente.all():
                d.delete()
            instance.delete()
        protokolliere(SystemEreignis.Art.FALL, self.request, objekt=f"Fall {nummer}", aktion="Fall entfernt",
                      patient=instance.patient.nummer, patient_id=instance.patient_id)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def paket(self, request, pk=None):
        from .pakete import paket_anlegen

        fall = self.get_object()
        self.pruefe_patient(fall.patient)
        neu = paket_anlegen(fall, request.user)
        if neu:
            _log(request, fall, "Dokumentenpaket ergänzt", dokumente=[d.titel for d in neu])
        return Response({"neu": len(neu), "dokumente": FallDokumentSerializer(neu, many=True,
                                                                              context=self.get_serializer_context()).data})

    @action(detail=True, methods=["post"])
    def abschliessen(self, request, pk=None):
        fall = self.get_object()
        self.pruefe_patient(fall.patient)
        fall.status = Behandlungsfall.Status.ABGESCHLOSSEN
        fall._history_user = request.user
        fall.save(update_fields=["status", "geaendert_am"])
        _log(request, fall, "Fall abgeschlossen")
        return Response(self.get_serializer(fall).data)

    @action(detail=True, methods=["post"], url_path="wieder-oeffnen")
    def wieder_oeffnen(self, request, pk=None):
        fall = self.get_object()
        self.pruefe_patient(fall.patient)
        fall.status = Behandlungsfall.Status.OFFEN
        fall._history_user = request.user
        fall.save(update_fields=["status", "geaendert_am"])
        _log(request, fall, "Fall wieder geöffnet")
        return Response(self.get_serializer(fall).data)


# ====================================================================== Dokumente des Falls
class VersionSerializer(serializers.ModelSerializer):
    art_name = serializers.CharField(source="get_art_display", read_only=True)
    erzeugt_von_name = serializers.SerializerMethodField()
    mime = serializers.CharField(source="pdf.mime", read_only=True)

    class Meta:
        model = DokumentVersion
        fields = ["id", "nummer", "art", "art_name", "final", "sha256", "vorlage", "vorlage_version", "grund",
                  "erzeugt_am", "erzeugt_von_name", "pdf", "docx", "mime"]

    def get_erzeugt_von_name(self, obj):
        return benutzername(obj.erzeugt_von)


class FallDokumentSerializer(FirmaFeld, serializers.ModelSerializer):
    art_name = serializers.CharField(source="get_art_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    final_weg_name = serializers.CharField(source="get_final_weg_display", read_only=True)
    final_von_name = serializers.SerializerMethodField()
    unterzeichner_name = serializers.CharField(source="unterzeichner.name", read_only=True, default=None)
    storniert_von_name = serializers.SerializerMethodField()
    stornorechnung = serializers.SerializerMethodField()
    versionen_anzahl = serializers.SerializerMethodField()
    letzte_version = serializers.SerializerMethodField()
    veraltet = serializers.SerializerMethodField()
    summe = serializers.SerializerMethodField()
    hat_docx = serializers.SerializerMethodField()
    titel = serializers.CharField(max_length=200, required=False, allow_blank=True)

    class Meta:
        model = FallDokument
        fields = ["id", "patient", "fall", "art", "art_name", "vorlage", "titel", "status", "status_name", "aus_paket",
                  "freitext", "rechnungsnummer", "rechnungsdatum", "zahlungsziel_tage", "storno_zu", "storniert_am",
                  "storniert_von_name", "storno_grund", "stornorechnung", "unterzeichner", "unterzeichner_name",
                  "final_weg", "final_weg_name", "final_am", "final_von_name", "erstellt_am", "versionen_anzahl",
                  "letzte_version", "veraltet", "summe", "hat_docx"]
        read_only_fields = ["patient", "status", "aus_paket", "rechnungsnummer", "storno_zu", "storniert_am",
                            "storno_grund", "final_weg", "final_am", "erstellt_am"]

    def get_final_von_name(self, obj):
        return benutzername(obj.final_von)

    def get_storniert_von_name(self, obj):
        return benutzername(obj.storniert_von)

    def get_stornorechnung(self, obj):
        s = getattr(obj, "stornorechnung", None) if obj.pk else None
        return s.pk if s else None

    def get_versionen_anzahl(self, obj):
        return obj.versionen.count() if obj.pk else 0

    def get_letzte_version(self, obj):
        v = obj.letzte_version() if obj.pk else None
        return VersionSerializer(v).data if v else None

    def get_veraltet(self, obj):
        return bool(obj.pk) and obj.status == FallDokument.Status.ERZEUGT and erzeugung.ist_veraltet(obj)

    def get_summe(self, obj):
        return str(obj.summen()["brutto"]) if obj.pk and obj.ist_rechnung else None

    def get_hat_docx(self, obj):
        return obj.art == FallDokument.Art.RECHNUNG or obj.art in Behandlungsfall.FREITEXTE or obj.art == FallDokument.Art.VORLAGE

    def validate_fall(self, fall):
        if self.instance and fall != self.instance.fall:
            raise serializers.ValidationError("Der Fall kann nicht geändert werden.")
        request = self.context.get("request")
        if request is not None and not patienten_fuer(request.user).filter(pk=fall.patient_id).exists():
            raise serializers.ValidationError("Fall nicht gefunden.")
        return fall

    def validate_art(self, art):
        if self.instance and art != self.instance.art:
            raise serializers.ValidationError("Die Art kann nicht geändert werden.")
        if art == FallDokument.Art.STORNO:
            raise serializers.ValidationError("Stornorechnungen entstehen über „Stornieren“.")
        return art

    def validate_unterzeichner(self, wert):
        if wert is not None and not wert.aktiv:
            raise serializers.ValidationError("Diese Person ist nicht (mehr) unterschriftsberechtigt.")
        return wert

    def validate(self, attrs):
        from vorlagen.models import EigenesSchreiben

        art = attrs.get("art", self.instance.art if self.instance else None)
        vorlage = attrs.get("vorlage", self.instance.vorlage if self.instance else "")
        if self.instance and "vorlage" in attrs and attrs["vorlage"] != self.instance.vorlage:
            raise serializers.ValidationError({"vorlage": "Die Vorlage kann nicht geändert werden."})
        if art == FallDokument.Art.VORLAGE:
            if not EigenesSchreiben.objects.filter(schluessel=vorlage, aktiv=True).exclude(gruppe="fall").exists():
                raise serializers.ValidationError({"vorlage": "Bitte eine Vorlage wählen."})
        else:
            attrs["vorlage"] = ""
        if not self.instance and not (attrs.get("titel") or "").strip():
            attrs["titel"] = titel_fuer(art, vorlage)
        if "titel" in attrs and not attrs["titel"].strip():
            raise serializers.ValidationError({"titel": "Bitte einen Titel angeben."})
        if "zahlungsziel_tage" in attrs and attrs["zahlungsziel_tage"] > 365:
            raise serializers.ValidationError({"zahlungsziel_tage": "Höchstens 365 Tage."})
        return attrs


class FallDokumentViewSet(AktenEintragViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin):
    model = FallDokument
    serializer_class = FallDokumentSerializer
    filterset_fields = ["patient", "fall", "status", "art"]
    pagination_class = None
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return super().get_queryset().select_related("fall", "unterzeichner", "final_von", "storniert_von")

    def get_permissions(self):
        if self.action in ("finalisieren", "stornieren"):
            return [FinalisierenRecht()]
        return super().get_permissions()

    @transaction.atomic
    def perform_create(self, serializer):
        fall = serializer.validated_data["fall"]
        self.pruefe_patient(fall.patient)
        fall.pruefe_offen()
        dok = serializer.save(patient=fall.patient, erstellt_von=self.request.user)
        _log(self.request, dok, "Dokument angelegt")

    def perform_update(self, serializer):
        dok = serializer.instance
        self.pruefe_patient(dok.patient)
        dok.pruefe_aenderbar()
        dok.fall.pruefe_offen()
        if dok.art == FallDokument.Art.STORNO and set(serializer.validated_data) - {"unterzeichner"}:
            raise serializers.ValidationError({"fehler": "Eine Stornorechnung wird nicht geändert – nur die "
                                                         "unterschreibende Person lässt sich wählen."})
        dok._history_user = self.request.user
        serializer.save()

    def perform_destroy(self, instance):
        self.pruefe_patient(instance.patient)
        instance._history_user = self.request.user
        titel, fall, patient = instance.titel, instance.fall, instance.patient
        instance.delete()
        protokolliere(SystemEreignis.Art.FALL, self.request, objekt=f"Fall {fall.nummer}", aktion="Entwurf entfernt",
                      titel=titel, patient=patient.nummer, patient_id=patient.pk)

    # ---------------------------------------------------------------- PDF
    @action(detail=True, methods=["get"])
    def vorschau(self, request, pk=None):
        from vorlagen.api import pdf_antwort

        dok = self.get_object()
        return pdf_antwort(erzeugung.vorschau(dok, request.user), f"Vorschau-{dok.titel}.pdf")

    @action(detail=True, methods=["post"])
    def erzeugen(self, request, pk=None):
        dok = self.get_object()
        self.pruefe_patient(dok.patient)
        grund = str(request.data.get("grund") or "").strip()[:300]
        v = erzeugung.erzeugen(dok, request.user, grund=grund)
        dok.refresh_from_db()
        _log(request, dok, "PDF erzeugt", fassung=v.nummer, sha256=v.sha256, grund=grund,
             rechnungsnummer=dok.rechnungsnummer)
        return Response(self.get_serializer(dok).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def versionen(self, request, pk=None):
        dok = self.get_object()
        return Response(VersionSerializer(dok.versionen.select_related("erzeugt_von", "pdf").order_by("-nummer"),
                                          many=True).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Gespeicherte Fassung (``?fassung=N``, sonst die neueste) – Prüfsumme wird geprüft."""
        from vorlagen.api import pdf_antwort

        dok = self.get_object()
        qs = dok.versionen.select_related("pdf")
        nummer = request.query_params.get("fassung")
        v = qs.filter(nummer=int(nummer)).first() if nummer and nummer.isdigit() else qs.order_by("-nummer").first()
        if v is None or not v.pdf.pfad.is_file():
            return Response({"fehler": "Diese Fassung gibt es nicht."}, status=status.HTTP_404_NOT_FOUND)
        daten = v.pdf.pfad.read_bytes()
        if hashlib.sha256(daten).hexdigest() != v.sha256:
            return Response({"fehler": "Die Prüfsumme der Datei stimmt nicht. Bitte die Administration informieren."},
                            status=status.HTTP_409_CONFLICT)
        protokolliere(SystemEreignis.Art.EXPORT, request, objekt=akte_text(dok.patient), was="Dokument eines Falls",
                      falldokument=dok.pk, fassung=v.nummer, patient_id=dok.patient_id)
        if v.pdf.mime == "application/pdf":
            return pdf_antwort(daten, v.pdf.originalname)
        from urllib.parse import quote

        antwort = HttpResponse(daten, content_type=v.pdf.mime)
        antwort["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(v.pdf.originalname)}"
        antwort["Cache-Control"] = "private, no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        return antwort

    @action(detail=True, methods=["get", "post"])
    def docx(self, request, pk=None):
        from urllib.parse import quote

        dok = self.get_object()
        if request.method == "GET":
            daten = erzeugung.docx_export(dok)
            antwort = HttpResponse(daten, content_type="application/vnd.openxmlformats-officedocument."
                                                       "wordprocessingml.document")
            name = erzeugung._dateiname(dok, "zur-Bearbeitung", "docx")
            antwort["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
            antwort["Cache-Control"] = "private, no-store"
            protokolliere(SystemEreignis.Art.EXPORT, request, objekt=akte_text(dok.patient), was="DOCX eines Falls",
                          falldokument=dok.pk, patient_id=dok.patient_id)
            return antwort
        self.pruefe_patient(dok.patient)
        datei = request.FILES.get("datei")
        if datei is None:
            return Response({"datei": "Bitte die bearbeitete DOCX-Datei wählen."}, status=status.HTTP_400_BAD_REQUEST)
        geaendert, v = erzeugung.docx_import(dok, datei, request.user)
        dok.refresh_from_db()
        _log(request, dok, "DOCX übernommen", fassung=v.nummer, felder=geaendert, sha256=v.sha256)
        return Response(self.get_serializer(dok).data)

    # ---------------------------------------------------------------- final
    @action(detail=True, methods=["post"])
    def finalisieren(self, request, pk=None):
        dok = self.get_object()
        self.pruefe_patient(dok.patient)
        d = request.data
        unterzeichner = None
        if d.get("unterzeichner"):
            unterzeichner = Unterzeichner.objects.filter(pk=d.get("unterzeichner")).first()
            if unterzeichner is None:
                return Response({"unterzeichner": "Unbekannte Person."}, status=status.HTTP_400_BAD_REQUEST)
        weg = str(d.get("weg") or "")
        v = erzeugung.finalisieren(dok, request.user, weg, unterzeichner=unterzeichner, datei=request.FILES.get("datei"),
                                   kennwort=str(d.get("kennwort") or ""), notiz=str(d.get("notiz") or ""))
        dok.refresh_from_db()
        _log(request, dok, "finalisiert", weg=dok.get_final_weg_display(), fassung=v.nummer, sha256=v.sha256,
             unterzeichner=str(dok.unterzeichner or ""), rechnungsnummer=dok.rechnungsnummer)
        return Response(self.get_serializer(dok).data)

    @action(detail=True, methods=["post"])
    def stornieren(self, request, pk=None):
        dok = self.get_object()
        self.pruefe_patient(dok.patient)
        storno, neu = erzeugung.stornieren(dok, request.user, str(request.data.get("grund") or ""),
                                           neue_rechnung=wahr(request.data.get("neue_rechnung", True)))
        dok.refresh_from_db()
        _log(request, dok, "storniert", grund=dok.storno_grund, rechnungsnummer=dok.rechnungsnummer,
             stornorechnung=storno.rechnungsnummer, neue_rechnung=neu.pk if neu else None)
        ctx = self.get_serializer_context()
        return Response({"rechnung": self.get_serializer(dok).data,
                         "storno": FallDokumentSerializer(storno, context=ctx).data,
                         "neu": FallDokumentSerializer(neu, context=ctx).data if neu else None})


# ====================================================================== Rechnungspositionen
class PositionSerializer(ModelClean, serializers.ModelSerializer):
    betrag = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    text = serializers.CharField(max_length=500, required=False, allow_blank=True)
    einzelpreis = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    class Meta:
        model = Rechnungsposition
        fields = ["id", "dokument", "reihenfolge", "leistung", "code", "text", "datum", "menge", "einheit",
                  "einzelpreis", "ust_satz", "betrag"]

    def validate_dokument(self, dok):
        if self.instance and dok != self.instance.dokument:
            raise serializers.ValidationError("Die Rechnung kann nicht gewechselt werden.")
        request = self.context.get("request")
        if request is not None and not patienten_fuer(request.user).filter(pk=dok.patient_id).exists():
            raise serializers.ValidationError("Rechnung nicht gefunden.")
        if not dok.ist_rechnung:
            raise serializers.ValidationError("Positionen gibt es nur an Rechnungen.")
        return dok

    def validate(self, attrs):
        leistung = attrs.get("leistung")
        if leistung is not None and (self.instance is None or self.instance.leistung_id != leistung.pk):
            if not leistung.aktiv:
                raise serializers.ValidationError({"leistung": "Diese Leistung ist ausgeblendet."})
            dok = attrs.get("dokument") or self.instance.dokument
            # Text und Preis aus dem Katalog, wenn nicht ausdrücklich angegeben
            attrs.setdefault("code", leistung.code)
            if not (attrs.get("text") or "").strip():
                attrs["text"] = leistung.text(dok.fall.sprache)[:500]
            attrs.setdefault("einzelpreis", leistung.preis)
            attrs.setdefault("einheit", leistung.einheit)
            attrs.setdefault("ust_satz", leistung.ust_satz)
        if self.instance is None and "einzelpreis" not in attrs:
            raise serializers.ValidationError({"einzelpreis": "Bitte einen Preis angeben."})
        dok = attrs.get("dokument") or (self.instance.dokument if self.instance else None)
        if dok is not None and dok.art == FallDokument.Art.RECHNUNG and attrs.get("menge") is not None \
                and attrs["menge"] < 0:
            raise serializers.ValidationError({"menge": "Gutschriften bitte über „Stornieren“."})
        return super().validate(attrs)


class PositionViewSet(viewsets.ModelViewSet):
    serializer_class = PositionSerializer
    permission_classes = [EintragRecht]
    filterset_fields = ["dokument"]
    pagination_class = None

    def get_queryset(self):
        return Rechnungsposition.objects.filter(dokument__patient__in=patienten_fuer(self.request.user)) \
            .select_related("dokument", "dokument__patient")

    def _pruefe(self, dok):
        from epm.api_basis import pruefe_schreibbereich

        pruefe_schreibbereich(self.request.user, dok.patient)
        dok.pruefe_aenderbar()
        dok.fall.pruefe_offen()

    def perform_create(self, serializer):
        dok = serializer.validated_data["dokument"]
        self._pruefe(dok)
        if "reihenfolge" not in serializer.validated_data:
            letzte = dok.positionen.order_by("-reihenfolge").values_list("reihenfolge", flat=True).first() or 0
            serializer.validated_data["reihenfolge"] = letzte + 10
        serializer.save()

    def perform_update(self, serializer):
        self._pruefe(serializer.instance.dokument)
        serializer.instance._history_user = self.request.user
        serializer.save()

    def perform_destroy(self, instance):
        self._pruefe(instance.dokument)
        instance._history_user = self.request.user
        instance.delete()
