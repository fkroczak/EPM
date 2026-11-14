"""API von „KI (Experimentell)“ – alle Endpunkte unter ``/api/ki/``.

Rechte (``accounts/rechte.py``, Festlegung 14.10.2026): ansehen ``ki_ansehen``; korrigieren, freigeben, ablehnen,
erneut verarbeiten ``ki_pruefen``; in die Akte übernehmen ``ki_uebernehmen`` plus das Recht der Akte; Berichtsentwurf
``ki_berichte``; Einstellungen und Modelle ``ki_verwalten``; Trainingsfreigabe ``ki_training_freigeben``.

Sichtbar ist nur, was zur aktiven Firma gehört (DSKM nur DSKM, RGC nur RGC): die Akte muss in der Firma liegen
(``patienten_fuer``) und das Dokument in dieser Firma erfasst sein (oder ohne Firma, z. B. ältere Dokumente).

Das Backend spricht nie selbst mit dem Modell: es legt Aufträge an, der KI-Dienst arbeitet sie ab.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import Angemeldet, nur_recht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import benutzername, patienten_fuer, pruefe_schreibbereich
from epm.pagination import Seiten

from . import chat, eingang, uebernahme
from .pipeline import alte_felder_entfernen
from .pruefung import PLANFELDER
from .models import (Dokumenttyp, KiAufgabe, KiBerichtsauftrag, KiChat, KiChatAnhang, KiChatNachricht, KiEinstellung,
                     KiEvaluationsfall, KiEvaluationslauf, KiFeld, KiHinweis, KiKorrektur, KiModellversion,
                     KiPromptvorlage, KiVorgang, KiZusammenfassung)

A = SystemEreignis.Art
S = KiVorgang.Status
AnsehenRecht = nur_recht("ki_ansehen")
VerwaltenRecht = nur_recht("ki_verwalten")


def _fehler(text: str, code=status.HTTP_400_BAD_REQUEST, feld: str = "fehler"):
    return Response({feld: text}, status=code)


def _recht(user, code: str):
    if not user.hat_recht(code):
        from accounts.rechte import NAMEN

        raise PermissionError(f"Dafür fehlt das Recht „{NAMEN[code]}“.")


def vorgaenge_fuer(user):
    """Vorgänge im Bereich der Person: Akte sichtbar (Firma, Testdaten, Einschränkung) und Dokument der Firma."""
    qs = KiVorgang.objects.filter(patient__in=patienten_fuer(user))
    firma = getattr(user, "firma", None)
    if firma is not None:
        qs = qs.filter(Q(firma__isnull=True) | Q(firma=firma))
    return qs


# ---------------------------------------------------------------------------------------------- Darstellung
FELD_SCHLUESSEL = {
    "meta": None,
    "labor": {"parameter", "parameter_name", "erkannt_als", "freitext_name", "wert", "wert_text", "einheit",
              "referenz_von", "referenz_bis", "datum", "uhrzeit", "markierung"},
    "infusion": {"substanz", "planfeld", "menge", "einheit", "von", "bis", "uhrzeit", "applikation", "haeufigkeit",
                 "kontext"},
    "medikation": {"wirkstoff", "handelsname", "staerke", "dosierung", "seit", "grund", "aktiv"},
    "diagnose": {"bezeichnung", "icd_code"},
    "text": {"text", "aktenabschnitt"},
}
META_SCHLUESSEL = {"wert", "typ_id"}


class FeldSerializer(serializers.ModelSerializer):
    gruppe_name = serializers.CharField(source="get_gruppe_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    endwert = serializers.JSONField(read_only=True)
    korrekturen = serializers.SerializerMethodField()
    unsicher = serializers.SerializerMethodField()
    geaendert_von_name = serializers.SerializerMethodField()

    class Meta:
        model = KiFeld
        fields = ["id", "gruppe", "gruppe_name", "schluessel", "nr", "wert", "korrigiert", "endwert", "konfidenz",
                  "unsicher", "quelle", "belege", "status", "status_name", "entscheidung", "ziel", "korrekturen",
                  "geaendert_am", "geaendert_von_name"]

    def get_korrekturen(self, obj):
        return len(obj.korrekturen.all())

    def get_unsicher(self, obj):
        grenze = self.context.get("unsicher_unter", 0.7)
        return obj.konfidenz is not None and obj.konfidenz < grenze

    def get_geaendert_von_name(self, obj):
        return benutzername(obj.geaendert_von)


class VorgangListeSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    dokumenttyp_name = serializers.CharField(source="get_dokumenttyp_display", read_only=True)
    patient_name = serializers.SerializerMethodField()
    patient_nummer = serializers.IntegerField(source="patient.nummer", read_only=True)
    dokument_titel = serializers.CharField(source="dokument.titel", read_only=True)
    dokument_datum = serializers.DateField(source="dokument.datum", read_only=True)
    felder_offen = serializers.IntegerField(read_only=True)
    felder_unsicher = serializers.IntegerField(read_only=True)
    firma_name = serializers.SerializerMethodField()

    class Meta:
        model = KiVorgang
        fields = ["id", "status", "status_name", "dokument", "dokument_titel", "dokument_datum", "patient",
                  "patient_name", "patient_nummer", "firma", "firma_name", "dokumenttyp", "dokumenttyp_name",
                  "typ_konfidenz", "ocr_konfidenz", "seiten", "schritt", "fortschritt", "fehler", "prioritaet",
                  "erstellt_am", "fertig_am", "felder_offen", "felder_unsicher", "metadaten"]

    def get_patient_name(self, obj):
        return f"{obj.patient.nachname}, {obj.patient.vorname}"

    def get_firma_name(self, obj):
        return obj.firma.kuerzel.upper() if obj.firma_id else ""


class VorgangSerializer(VorgangListeSerializer):
    felder = serializers.SerializerMethodField()
    seiten_liste = serializers.SerializerMethodField()
    dokument_mime = serializers.CharField(source="dokument.mime", read_only=True)
    modell = serializers.SerializerMethodField()
    geprueft_von_name = serializers.SerializerMethodField()
    angefordert_von_name = serializers.SerializerMethodField()
    uebernahmen = serializers.SerializerMethodField()

    class Meta(VorgangListeSerializer.Meta):
        fields = VorgangListeSerializer.Meta.fields + [
            "felder", "seiten_liste", "dokument_mime", "zusammenfassung", "ocr_text", "verfahren", "modell",
            "prompt_version", "dauer_s", "geprueft_von_name", "geprueft_am", "ablehnungsgrund", "angefordert_von_name",
            "angefordert_am", "uebernahmen"]

    def get_felder(self, obj):
        return FeldSerializer(obj.felder.prefetch_related("korrekturen").select_related("geaendert_von"), many=True,
                              context=self.context).data

    def get_seiten_liste(self, obj):
        return [{"nr": s.nr, "text": s.text, "vision_text": s.vision_text, "konfidenz": s.konfidenz,
                 "verfahren": s.verfahren, "dauer_s": s.dauer_s} for s in obj.seiten_liste.all()]

    def get_modell(self, obj):
        mv = obj.modellversion
        return {"name": mv.name, "sha256": mv.sha256, "id": mv.pk} if mv else None

    def get_geprueft_von_name(self, obj):
        return benutzername(obj.geprueft_von)

    def get_angefordert_von_name(self, obj):
        return benutzername(obj.angefordert_von)

    def get_uebernahmen(self, obj):
        return [{"zeitpunkt": u.zeitpunkt, "benutzer": benutzername(u.benutzer), "ziele": u.ziele,
                 "felder": len(u.felder)} for u in obj.uebernahmen.select_related("benutzer")]


def _zeit_filter(qs, request):
    p = request.query_params
    for name, lookup in (("von", "erstellt_am__date__gte"), ("bis", "erstellt_am__date__lte")):
        if p.get(name):
            try:
                qs = qs.filter(**{lookup: dt.date.fromisoformat(p[name])})
            except ValueError:
                pass
    return qs


# ---------------------------------------------------------------------------------------------- Vorgänge
class KiVorgangViewSet(viewsets.GenericViewSet):
    """Prüf-Queue: ``GET /api/ki/vorgaenge/?status=zur_pruefung,teilweise&patient=&dokumenttyp=&konfidenz_unter=
    &fehler=1&von=&bis=&suche=``."""

    permission_classes = [AnsehenRecht]
    pagination_class = Seiten

    def get_queryset(self):
        return vorgaenge_fuer(self.request.user).select_related("patient", "dokument", "firma", "modellversion")

    def _vorgang(self, pk, sperren=False) -> KiVorgang:
        v = self.get_queryset().filter(pk=pk).first()
        if v is None:
            from rest_framework.exceptions import NotFound

            raise NotFound("Diesen KI-Vorgang gibt es nicht (mehr) oder er gehört nicht zu Ihrer Firma.")
        if sperren:  # Felder ändern erst nach einer laufenden Übernahme (uebernahme.uebernehmen sperrt ebenso)
            v.refresh_from_db(from_queryset=KiVorgang.objects.select_for_update())
        return v

    def _ctx(self):
        return {"request": self.request, "unsicher_unter": KiEinstellung.laden().feld_unsicher}

    def list(self, request):
        p = request.query_params
        einst = KiEinstellung.laden()
        qs = self.get_queryset().annotate(
            felder_offen=Count("felder", filter=Q(felder__status__in=["offen", "freigegeben"])),
            felder_unsicher=Count("felder", filter=Q(felder__konfidenz__lt=einst.feld_unsicher,
                                                     felder__status="offen")))
        if p.get("status"):
            qs = qs.filter(status__in=[s for s in p["status"].split(",") if s in S.values])
        if p.get("patient", "").isdigit():
            qs = qs.filter(patient_id=int(p["patient"]))
        if p.get("dokumenttyp"):
            qs = qs.filter(dokumenttyp__in=p["dokumenttyp"].split(","))
        if p.get("konfidenz_unter"):
            try:
                qs = qs.filter(ocr_konfidenz__lt=float(p["konfidenz_unter"]))
            except ValueError:
                pass
        if p.get("fehler") in ("1", "true"):
            qs = qs.filter(status=S.FEHLER)
        if p.get("suche"):
            q = p["suche"].strip()
            qs = qs.filter(Q(dokument__titel__icontains=q) | Q(ocr_text__icontains=q) | Q(patient__nachname__icontains=q))
        qs = _zeit_filter(qs, request)
        ordnung = {"neu": ["-erstellt_am", "-id"], "alt": ["erstellt_am", "id"],
                   "konfidenz": ["ocr_konfidenz", "id"]}.get(p.get("ordnung", ""), ["-prioritaet", "-erstellt_am", "-id"])
        seite = self.paginate_queryset(qs.order_by(*ordnung))
        return self.get_paginated_response(VorgangListeSerializer(seite, many=True).data)

    def retrieve(self, request, pk=None):
        v = self._vorgang(pk)
        daten = VorgangSerializer(v, context=self._ctx()).data
        daten["vorschau"] = uebernahme.vorschau(v) if v.status in (*KiVorgang.PRUEFBAR, S.UEBERNOMMEN) else []
        daten["rechte"] = {c: request.user.hat_recht(c) for c in ("ki_pruefen", "ki_uebernehmen")}
        return Response(daten)

    @action(detail=False)
    def zaehler(self, request):
        je = dict(self.get_queryset().values_list("status").annotate(n=Count("id")))
        return Response({"je_status": je, "zur_pruefung": je.get(S.ZUR_PRUEFUNG, 0) + je.get(S.TEILWEISE, 0)})

    @action(detail=False, methods=["post"])
    def anfordern(self, request):
        """Ein Dokument ausdrücklich verarbeiten lassen (läuft auch tagsüber, mit Vorrang)."""
        from patienten.models import Dokument

        _recht(request.user, "ki_pruefen")
        did = str(request.data.get("dokument") or "")
        dok = Dokument.objects.filter(pk=did, patient__in=patienten_fuer(request.user),
                                      ausgeblendet=False).first() if did.isdigit() else None
        if dok is None:
            return _fehler("Dokument nicht gefunden.", feld="dokument")
        if dok.mime not in eingang.LESBAR:
            return _fehler("Dieses Dateiformat kann die Texterkennung nicht lesen.", feld="dokument")
        firma = getattr(request.user, "firma", None)
        if firma is not None and dok.firma_id not in (None, firma.pk):
            return _fehler("Das Dokument gehört zu einer anderen Firma.", feld="dokument")
        if dok.patient.eingeschraenkt_am is not None:
            return _fehler("Die Verarbeitung dieser Akte ist eingeschränkt.", feld="dokument")
        v = eingang.anfordern(dok, request.user)
        protokolliere(A.KI, request, objekt=str(v), aktion="angefordert", vorgang=v.pk, dokument=dok.pk,
                      patient_id=dok.patient_id)
        return Response(VorgangListeSerializer(self.get_queryset().get(pk=v.pk)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"felder/(?P<fid>\d+)")
    def feld(self, request, pk=None, fid=None):
        """Feld korrigieren (jede Änderung versioniert) oder Entscheidung bei Konflikt setzen."""
        _recht(request.user, "ki_pruefen")
        v = self._vorgang(pk, sperren=True)
        if v.status not in KiVorgang.PRUEFBAR:
            return _fehler("Dieser Vorgang ist nicht (mehr) zur Prüfung vorgelegt.")
        f = v.felder.filter(pk=fid).first()
        if f is None:
            return _fehler("Feld nicht gefunden.", status.HTTP_404_NOT_FOUND)
        if f.status == KiFeld.Status.UEBERNOMMEN:
            return _fehler("Das Feld ist schon übernommen.")
        d = request.data if isinstance(request.data, dict) else {}
        with transaction.atomic():
            if "wert" in d:
                neu = d["wert"]
                erlaubt = FELD_SCHLUESSEL[f.gruppe] or META_SCHLUESSEL
                if not isinstance(neu, dict) or set(neu) - erlaubt:
                    return _fehler(f"Erlaubte Angaben: {', '.join(sorted(erlaubt))}.", feld="wert")
                pf = neu.get("planfeld")
                if pf and (not isinstance(pf, str) or pf not in PLANFELDER):  # nie Patient, Status, Herkunft …
                    return _fehler(f"Planfeld: erlaubt sind {', '.join(PLANFELDER)}.", feld="wert")
                fehlerart = d.get("fehlerart") or KiKorrektur.Fehlerart.SONSTIGES
                if fehlerart not in KiKorrektur.Fehlerart.values:
                    return _fehler("Unbekannte Fehlerart.", feld="fehlerart")
                alt = f.endwert
                zusammen = {**alt, **neu}
                if f.gruppe == KiFeld.Gruppe.LABOR and "parameter_name" in neu and "parameter" not in neu:
                    # anderer Parameter: wieder dem Laborkatalog zuordnen (sonst Freitext)
                    from .pruefung import Katalog

                    name = str(neu.get("parameter_name") or "").strip()[:150]
                    param, _art = Katalog().finden(name) if name else (None, "")
                    zusammen.update({"parameter": param.id if param else None,
                                     "parameter_name": param.name if param else None,
                                     "erkannt_als": name, "freitext_name": "" if param else name})
                if zusammen != alt:
                    version = (f.korrekturen.order_by("-version").values_list("version", flat=True).first() or 0) + 1
                    KiKorrektur.objects.create(feld=f, version=version, alt=alt, neu=zusammen, fehlerart=fehlerart,
                                               kommentar=str(d.get("kommentar") or "")[:300], benutzer=request.user)
                    f.korrigiert = zusammen
                    protokolliere(A.KI, request, objekt=str(v), aktion="korrigiert", vorgang=v.pk, feld=f.pk,
                                  gruppe=f.gruppe, fehlerart=fehlerart, version=version, patient_id=v.patient_id)
            if "entscheidung" in d:
                if d["entscheidung"] not in KiFeld.Entscheidung.values:
                    return _fehler("Unbekannte Entscheidung.", feld="entscheidung")
                f.entscheidung = d["entscheidung"]
            if "status" in d:
                if d["status"] not in (KiFeld.Status.OFFEN, KiFeld.Status.FREIGEGEBEN, KiFeld.Status.VERWORFEN):
                    return _fehler("Unbekannter Status.", feld="status")
                f.status = d["status"]
            f.geaendert_von = request.user
            f.save()
        return Response(FeldSerializer(f, context=self._ctx()).data)

    @action(detail=True, methods=["post"])
    def freigeben(self, request, pk=None):
        """Mehrere Felder auf einmal: ``{"felder": [ids] | "alle": true, "status": "freigegeben"|"verworfen"|"offen"}``.
        „Alle“ gibt nur sicher erkannte Felder frei – unsichere bleiben offen und brauchen einen eigenen Blick."""
        _recht(request.user, "ki_pruefen")
        v = self._vorgang(pk, sperren=True)
        if v.status not in KiVorgang.PRUEFBAR:
            return _fehler("Dieser Vorgang ist nicht (mehr) zur Prüfung vorgelegt.")
        ziel = request.data.get("status") or KiFeld.Status.FREIGEGEBEN
        if ziel not in (KiFeld.Status.OFFEN, KiFeld.Status.FREIGEGEBEN, KiFeld.Status.VERWORFEN):
            return _fehler("Unbekannter Status.", feld="status")
        qs = v.felder.exclude(status=KiFeld.Status.UEBERNOMMEN)
        if request.data.get("alle"):
            qs = [f for f in qs if uebernahme.uebernehmbar(f)]
            if ziel == KiFeld.Status.FREIGEGEBEN:
                grenze = KiEinstellung.laden().feld_unsicher
                qs = [f for f in qs if f.konfidenz is None or f.konfidenz >= grenze or f.korrigiert is not None]
        else:
            ids = [int(i) for i in request.data.get("felder") or [] if str(i).isdigit()]
            qs = list(qs.filter(pk__in=ids))
        for f in qs:
            f.status, f.geaendert_von = ziel, request.user
            f.save(update_fields=["status", "geaendert_von", "geaendert_am"])
        protokolliere(A.KI, request, objekt=str(v), aktion=f"felder_{ziel}", vorgang=v.pk,
                      felder=[f.pk for f in qs], patient_id=v.patient_id)
        return Response({"geaendert": len(qs)})

    @action(detail=True)
    def vorschau(self, request, pk=None):
        return Response(uebernahme.vorschau(self._vorgang(pk)))

    @action(detail=True, methods=["post"])
    def uebernehmen(self, request, pk=None):
        """``{"felder": [ids], "entscheidungen": {"<id>": "neu|ergaenzen|ersetzen|verwerfen"}, "bestaetigt": true}``.
        409 mit ``konflikte``, wenn für einen Konflikt die Entscheidung fehlt – dann wird nichts geschrieben."""
        _recht(request.user, "ki_uebernehmen")
        v = self._vorgang(pk)
        if v.status not in KiVorgang.PRUEFBAR:
            return _fehler("Dieser Vorgang ist nicht (mehr) zur Prüfung vorgelegt.")
        if request.data.get("bestaetigt") is not True:
            return _fehler("Bitte die Übernahme in die Akte ausdrücklich bestätigen.", feld="bestaetigt")
        if v.ist_test and not v.patient.ist_test:
            return _fehler("Unstimmigkeit Testdaten.")
        ids = [int(i) for i in request.data.get("felder") or [] if str(i).isdigit()]
        entscheidungen = request.data.get("entscheidungen") or {}
        if not isinstance(entscheidungen, dict):
            return _fehler("Entscheidungen bitte je Feld angeben.", feld="entscheidungen")
        try:
            erg = uebernahme.uebernehmen(v, ids, entscheidungen, request)
        except uebernahme.Konflikt as k:
            return Response({"fehler": str(k), "konflikte": k.konflikte}, status=status.HTTP_409_CONFLICT)
        except uebernahme.Ungueltig as u:
            return Response({"fehler": str(u), **u.fehler}, status=status.HTTP_400_BAD_REQUEST)
        return Response(erg, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def ablehnen(self, request, pk=None):
        _recht(request.user, "ki_pruefen")
        v = self._vorgang(pk)
        grund = str(request.data.get("grund") or "").strip()
        if not grund:
            return _fehler("Bitte einen Grund angeben.", feld="grund")
        if v.status not in (*KiVorgang.PRUEFBAR, S.FEHLER, S.NACHVERARBEITUNG):
            return _fehler("Dieser Vorgang lässt sich nicht ablehnen.")
        with transaction.atomic():
            v.felder.filter(status__in=[KiFeld.Status.OFFEN, KiFeld.Status.FREIGEGEBEN]).update(
                status=KiFeld.Status.VERWORFEN, geaendert_von=request.user, geaendert_am=timezone.now())
            v.status, v.ablehnungsgrund = S.ABGELEHNT, grund[:2000]
            v.geprueft_von, v.geprueft_am = request.user, timezone.now()
            v.save(update_fields=["status", "ablehnungsgrund", "geprueft_von", "geprueft_am"])
            protokolliere(A.KI, request, objekt=str(v), aktion="abgelehnt", vorgang=v.pk, grund=grund[:300],
                          patient_id=v.patient_id)
        return Response({"status": v.status})

    @action(detail=True, methods=["post"])
    def erneut(self, request, pk=None):
        """Erneut verarbeiten (z. B. nach einem Fehler oder mit neuem Modell). Bereits übernommene Felder bleiben;
        korrigierte Felder bleiben als verworfen für die Qualitätsauswertung erhalten."""
        _recht(request.user, "ki_pruefen")
        v = self._vorgang(pk)
        if v.status in KiVorgang.IN_ARBEIT:
            return _fehler("Der Vorgang wird gerade verarbeitet.", status.HTTP_409_CONFLICT)
        nachher = request.data.get("nachverarbeitung") is True
        with transaction.atomic():
            alte_felder_entfernen(v)
            v.seiten_liste.all().delete()
            v.status = S.NACHVERARBEITUNG if nachher else S.NEU
            v.prioritaet, v.angefordert_von, v.angefordert_am = KiEinstellung.laden().prio_angefordert, \
                request.user, timezone.now()
            v.versuche, v.fehler, v.schritt, v.fortschritt = 0, "", "", 0
            v.save()
            protokolliere(A.KI, request, objekt=str(v), aktion="nachverarbeitung" if nachher else "erneut",
                          vorgang=v.pk, patient_id=v.patient_id)
        return Response({"status": v.status})

    @action(detail=False, methods=["post"])
    def neu_lesen(self, request):
        """„Jetzt neu lesen“ (Administration › KI › Nachtaufgaben): ``{"vorgaenge": [ids]}`` oder Filter
        ``{"seit_tagen", "dokumenttypen", "nur_anderes_modell", "hoechstens"}`` – gleiche Logik wie die Nachtaufgabe
        ``neu_lesen`` (``eingang.neu_lesen``), nur Vorgänge der eigenen Firma. → ``{"vorgemerkt": n}``."""
        from .aufgaben import NEU_LESEN_PARAMETER, parameter_pruefen

        _recht(request.user, "ki_verwalten")
        d = request.data if isinstance(request.data, dict) else {}
        if "vorgaenge" in d:
            ids = d["vorgaenge"]
            if not isinstance(ids, list) or not ids or any(not str(i).isdigit() for i in ids):
                return _fehler("Bitte eine Liste von Vorgängen angeben.", feld="vorgaenge")
            ids = [int(i) for i in ids][:eingang.NEU_LESEN_MAX]
            n = eingang.neu_lesen(vorgaenge=ids, hoechstens=len(ids), basis=vorgaenge_fuer(request.user))
            filter_ = {"vorgaenge": len(ids)}
        else:
            try:
                p = parameter_pruefen("neu_lesen", d, NEU_LESEN_PARAMETER)
            except ValueError as e:
                return Response({k.removeprefix("parameter."): v for k, v in e.args[0].items()},
                                status=status.HTTP_400_BAD_REQUEST)
            n = eingang.neu_lesen(**p, basis=vorgaenge_fuer(request.user))
            filter_ = p
        eingang.prioritaeten_aktualisieren()
        protokolliere(A.KI, request, objekt="KI-Vorgänge", aktion="neu_lesen", vorgemerkt=n, **filter_)
        return Response({"vorgemerkt": n})


# ---------------------------------------------------------------------------------------------- Hinweise
class KiHinweisViewSet(viewsets.GenericViewSet):
    """Historische Zusammenhänge Labor ↔ Infusionsplan: ``GET /api/ki/hinweise/?patient=ID&alle=1``.
    Nur Entscheidungshilfe – keine medizinische Bewertung."""

    permission_classes = [AnsehenRecht]

    def get_queryset(self):
        return KiHinweis.objects.filter(patient__in=patienten_fuer(self.request.user))

    def list(self, request):
        qs = self.get_queryset()
        pid = request.query_params.get("patient", "")
        if pid.isdigit():
            qs = qs.filter(patient_id=int(pid))
        if request.query_params.get("alle") not in ("1", "true"):
            qs = qs.exclude(status=KiHinweis.Status.AUSGEBLENDET)
        return Response([{
            "id": h.id, "patient": h.patient_id, "art": h.art, "art_name": h.get_art_display(), "stufe": h.stufe,
            "stufe_name": h.get_stufe_display(), "parameter": h.parameter, "text": h.text, "zeitpunkt": h.zeitpunkt,
            "belege": h.belege, "status": h.status, "aktualisiert_am": h.aktualisiert_am,
        } for h in qs.order_by("-zeitpunkt", "-id")[:500]])

    def partial_update(self, request, pk=None):
        h = self.get_queryset().filter(pk=pk).first()
        if h is None:
            return _fehler("Hinweis nicht gefunden.", status.HTTP_404_NOT_FOUND)
        neu = request.data.get("status")
        if neu not in KiHinweis.Status.values:
            return _fehler("Unbekannter Status.", feld="status")
        h.status, h.geaendert_von = neu, request.user
        h.save(update_fields=["status", "geaendert_von", "aktualisiert_am"])
        return Response({"id": h.id, "status": h.status})


# ---------------------------------------------------------------------------------------------- Berichte
class BerichtAuftragSerializer(serializers.ModelSerializer):
    art_name = serializers.CharField(source="get_art_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    angefordert_von_name = serializers.SerializerMethodField()
    modell = serializers.SerializerMethodField()
    kennzeichnung = serializers.SerializerMethodField()

    class Meta:
        model = KiBerichtsauftrag
        fields = ["id", "patient", "art", "art_name", "von", "bis", "dokumenttypen", "status", "status_name",
                  "angefordert_von_name", "angefordert_am", "fakten", "entwurf", "pruefung", "fehler", "modell",
                  "fertig_am", "bericht", "kennzeichnung"]
        read_only_fields = ["status", "fakten", "entwurf", "pruefung", "fehler", "fertig_am", "bericht"]

    def get_angefordert_von_name(self, obj):
        return benutzername(obj.angefordert_von)

    def get_modell(self, obj):
        return obj.modellversion.name if obj.modellversion_id else None

    def get_kennzeichnung(self, obj):
        from .berichte import KENNZEICHNUNG

        return KENNZEICHNUNG

    def validate_dokumenttypen(self, wert):
        from .berichte import ALLE_QUELLEN

        if not isinstance(wert, list) or set(wert) - set(ALLE_QUELLEN):
            raise serializers.ValidationError(f"Erlaubt: {', '.join(ALLE_QUELLEN)}.")
        return wert

    def validate(self, attrs):
        if attrs.get("von") and attrs.get("bis") and attrs["von"] > attrs["bis"]:
            raise serializers.ValidationError({"bis": "Das Ende liegt vor dem Beginn."})
        return attrs


class KiBerichtViewSet(viewsets.GenericViewSet):
    """Berichtsentwurf nur auf Anforderung: ``POST /api/ki/berichte/`` (Patient, Art, Zeitraum, Quellen) →
    der KI-Dienst erstellt den Entwurf; ``POST …/{id}/speichern/`` legt ihn als Bericht-Entwurf in die Akte."""

    permission_classes = [AnsehenRecht]
    serializer_class = BerichtAuftragSerializer

    def get_queryset(self):
        return KiBerichtsauftrag.objects.filter(patient__in=patienten_fuer(self.request.user)).select_related(
            "angefordert_von", "modellversion")

    def list(self, request):
        qs = self.get_queryset()
        pid = request.query_params.get("patient", "")
        if pid.isdigit():
            qs = qs.filter(patient_id=int(pid))
        return Response(BerichtAuftragSerializer(qs[:100], many=True).data)

    def retrieve(self, request, pk=None):
        b = self.get_queryset().filter(pk=pk).first()
        if b is None:
            return _fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        return Response(BerichtAuftragSerializer(b).data)

    def create(self, request):
        _recht(request.user, "ki_berichte")
        s = BerichtAuftragSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        patient = s.validated_data["patient"]
        if not patienten_fuer(request.user).filter(pk=patient.pk).exists():
            return _fehler("Akte nicht gefunden.", feld="patient")
        b = s.save(angefordert_von=request.user, firma=getattr(request.user, "firma", None))
        protokolliere(A.KI, request, objekt=f"Berichtsentwurf {b.pk}", aktion="bericht_angefordert",
                      patient_id=patient.id, berichtsart=b.art)
        return Response(BerichtAuftragSerializer(b).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def speichern(self, request, pk=None):
        """Als Bericht-Entwurf in die Akte (Reiter „Berichte“), wahlweise mit bearbeitetem Text. Freigeben kann ihn
        danach nur, wer „Berichte freigeben“ darf – wie jeden Bericht."""
        from berichte.models import Bericht
        from stammdaten.models import Auswahlwert

        from .berichte import als_html

        _recht(request.user, "ki_berichte")
        _recht(request.user, "eintraege_erfassen")
        b = self.get_queryset().filter(pk=pk).first()
        if b is None:
            return _fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        # sperren und Status neu lesen: Zweimal gleichzeitig „Speichern“ ergäbe sonst zwei Berichte
        b.refresh_from_db(from_queryset=KiBerichtsauftrag.objects.select_for_update())
        if b.status == KiBerichtsauftrag.Status.GESPEICHERT:
            return _fehler("Der Entwurf ist schon als Bericht gespeichert.", status.HTTP_409_CONFLICT)
        if b.status != KiBerichtsauftrag.Status.FERTIG:
            return _fehler("Der Entwurf ist noch nicht fertig oder schon gespeichert.")
        pruefe_schreibbereich(request.user, b.patient)
        b.patient.pruefe_bearbeitbar()
        text = request.data.get("text")
        text = b.entwurf if not isinstance(text, str) or not text.strip() else text
        titel = str(request.data.get("titel") or f"KI-Entwurf: {b.get_art_display()}")[:200]
        art = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.BERICHTART, wert__in=["Verlaufsbericht",
                                                                                        "Sonstiges"]).first()
        with transaction.atomic():
            bericht = Bericht(patient=b.patient, titel=titel, art=art, inhalt=als_html(b, text),
                              erstellt_von=request.user)
            bericht._history_user = request.user
            bericht.save()
            b.bericht, b.status = bericht, KiBerichtsauftrag.Status.GESPEICHERT
            if text != b.entwurf:
                b.pruefung = {**(b.pruefung or {}), "bearbeitet": True}
            b.save(update_fields=["bericht", "status", "pruefung"])
            protokolliere(A.KI, request, objekt=f"Berichtsentwurf {b.pk}", aktion="bericht_gespeichert",
                          patient_id=b.patient_id, bericht=bericht.pk, bearbeitet=text != b.entwurf)
        return Response({"bericht": bericht.pk}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def verwerfen(self, request, pk=None):
        _recht(request.user, "ki_berichte")
        b = self.get_queryset().filter(pk=pk).first()
        if b is None:
            return _fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        if b.status == KiBerichtsauftrag.Status.GESPEICHERT:
            return _fehler("Schon als Bericht gespeichert – dort verwerfen.")
        b.status = KiBerichtsauftrag.Status.VERWORFEN
        b.save(update_fields=["status"])
        protokolliere(A.KI, request, objekt=f"Berichtsentwurf {b.pk}", aktion="bericht_verworfen",
                      patient_id=b.patient_id)
        return Response({"status": b.status})


# ---------------------------------------------------------------------------------------------- KI-Chat
class PromptvorlageSerializer(serializers.ModelSerializer):
    geaendert_von_name = serializers.SerializerMethodField()

    class Meta:
        model = KiPromptvorlage
        fields = ["id", "name", "beschreibung", "anweisung", "temperatur", "aktiv", "reihenfolge", "mitgeliefert",
                  "geaendert_am", "geaendert_von_name"]
        read_only_fields = ["mitgeliefert", "geaendert_am"]

    def get_geaendert_von_name(self, obj):
        return benutzername(obj.geaendert_von) if obj.geaendert_von_id else None

    def validate_temperatur(self, wert):
        if not (0 <= wert <= 1):
            raise serializers.ValidationError("Erlaubt: 0–1.")
        return wert

    def validate_anweisung(self, wert):
        if not wert.strip():
            raise serializers.ValidationError("Bitte eine Anweisung eingeben.")
        if len(wert) > 4000:
            raise serializers.ValidationError("Höchstens 4000 Zeichen.")
        return wert.strip()


class KiPromptvorlageViewSet(viewsets.ModelViewSet):
    """Promptvorlagen des KI-Chats: lesen mit „KI ansehen“ oder „Vorlagen pflegen“, ändern nur „Vorlagen pflegen“
    (Administration › Vorlagen › KI-Prompts). Mitgelieferte Vorlagen lassen sich ändern und ausblenden, nicht löschen."""

    permission_classes = [Angemeldet]
    serializer_class = PromptvorlageSerializer
    pagination_class = None

    def get_queryset(self):
        u = self.request.user
        if not (u.hat_recht("ki_ansehen") or u.hat_recht("vorlagen_pflegen")):
            raise PermissionError("Dafür fehlt das Recht „KI (Experimentell): ansehen“.")
        qs = KiPromptvorlage.objects.select_related("geaendert_von")
        if self.request.query_params.get("alle") != "1":
            qs = qs.filter(aktiv=True)
        return qs

    def perform_create(self, serializer):
        _recht(self.request.user, "vorlagen_pflegen")
        v = serializer.save(geaendert_von=self.request.user)
        protokolliere(A.KI, self.request, objekt=f"KI-Promptvorlage {v.pk}", aktion="promptvorlage_angelegt",
                      name=v.name)

    def perform_update(self, serializer):
        _recht(self.request.user, "vorlagen_pflegen")
        v = serializer.save(geaendert_von=self.request.user)
        protokolliere(A.KI, self.request, objekt=f"KI-Promptvorlage {v.pk}", aktion="promptvorlage_geaendert",
                      name=v.name, aktiv=v.aktiv)

    def perform_destroy(self, instance):
        _recht(self.request.user, "vorlagen_pflegen")
        if instance.mitgeliefert:
            raise serializers.ValidationError({"fehler": "Mitgelieferte Vorlagen lassen sich nur ausblenden."})
        protokolliere(A.KI, self.request, objekt=f"KI-Promptvorlage {instance.pk}", aktion="promptvorlage_geloescht",
                      name=instance.name)
        instance.delete()


class ChatAnhangSerializer(serializers.ModelSerializer):
    patient_nummer = serializers.IntegerField(source="patient.nummer", read_only=True, default=None)

    class Meta:
        model = KiChatAnhang
        fields = ["id", "herkunft", "name", "groesse", "seiten", "seiten_fertig", "status", "fehler", "dokument",
                  "patient", "patient_nummer"]


class ChatNachrichtSerializer(serializers.ModelSerializer):
    anhaenge = ChatAnhangSerializer(many=True, read_only=True)

    class Meta:
        model = KiChatNachricht
        fields = ["id", "rolle", "text", "status", "schritt", "vorlage_name", "pruefung", "fehler", "modell",
                  "dauer_s", "erstellt_am", "fertig_am", "anhaenge"]


class ChatSerializer(serializers.ModelSerializer):
    vorlage_name = serializers.SerializerMethodField()
    wartet = serializers.SerializerMethodField()

    class Meta:
        model = KiChat
        fields = ["id", "titel", "vorlage", "vorlage_name", "erstellt_am", "aktualisiert_am", "wartet"]

    def get_vorlage_name(self, obj):
        return obj.vorlage.name if obj.vorlage_id else None

    def get_wartet(self, obj):
        return obj.nachrichten.filter(status__in=[KiChatNachricht.Status.WARTET,
                                                  KiChatNachricht.Status.LAEUFT]).exists()


class KiChatViewSet(viewsets.GenericViewSet):
    """KI-Chat: ``GET/POST /api/ki/chats/``, ``GET/DELETE …/{id}/``, ``POST …/{id}/nachricht/`` {text, vorlage,
    dokumente: [ID aus der Akte], dateien: [Upload] (multipart)}.

    Jede Person sieht **ausschließlich ihre eigenen** Unterhaltungen – der Filter ``benutzer=request.user`` gilt für
    alle Rollen, auch Admins; fremde Chats antworten mit 404. Inhalte stehen nicht im Audit-Log."""

    permission_classes = [AnsehenRecht]
    serializer_class = ChatSerializer

    def get_queryset(self):
        return KiChat.objects.filter(benutzer=self.request.user).select_related("vorlage")

    def _chat(self, pk) -> KiChat | None:
        return self.get_queryset().filter(pk=pk).first()

    def _antwort(self, c: KiChat):
        nachrichten = c.nachrichten.prefetch_related(
            Prefetch("anhaenge", KiChatAnhang.objects.defer("datei", "text").select_related("patient")))
        return {**ChatSerializer(c).data,
                "nachrichten": ChatNachrichtSerializer(nachrichten, many=True).data,
                "aufbewahrung_tage": chat.aufbewahrung_tage()}

    def list(self, request):
        return Response(ChatSerializer(self.get_queryset()[:100], many=True).data)

    def retrieve(self, request, pk=None):
        c = self._chat(pk)
        if c is None:
            return _fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        return Response(self._antwort(c))

    def create(self, request):
        _recht(request.user, "ki_berichte")
        vorlage = self._vorlage(request.data.get("vorlage"))
        c = KiChat.objects.create(benutzer=request.user, firma=getattr(request.user, "firma", None), vorlage=vorlage,
                                  titel=str(request.data.get("titel") or "")[:200])
        protokolliere(A.KI, request, objekt=f"KI-Chat {c.pk}", aktion="chat_begonnen")
        return Response(self._antwort(c), status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        c = self._chat(pk)
        if c is None:
            return _fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        c.delete()
        protokolliere(A.KI, request, objekt=f"KI-Chat {pk}", aktion="chat_geloescht")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _vorlage(wert) -> KiPromptvorlage | None:
        if wert in (None, ""):
            return None
        try:
            return KiPromptvorlage.objects.get(pk=int(wert), aktiv=True)
        except (KiPromptvorlage.DoesNotExist, TypeError, ValueError):
            raise serializers.ValidationError({"vorlage": "Unbekannte oder ausgeblendete Vorlage."})

    @staticmethod
    def _akten_dokumente(request) -> list:
        """Gewählte Dokumente aus Akten – nur solche, die die Person in der Akte sehen darf."""
        from patienten.models import Dokument

        ids = request.data.getlist("dokumente") if hasattr(request.data, "getlist") else \
            (request.data.get("dokumente") or [])
        if not isinstance(ids, list):
            raise serializers.ValidationError({"dokumente": "Liste von Dokumenten erwartet."})
        firma = getattr(request.user, "firma", None)
        aus = []
        for wert in ids[:50]:
            dok = Dokument.objects.filter(pk=wert, patient__in=patienten_fuer(request.user), ausgeblendet=False) \
                .select_related("patient").first() if str(wert).isdigit() else None
            if dok is None or (firma is not None and dok.firma_id not in (None, firma.pk)):
                raise serializers.ValidationError({"dokumente": "Dokument nicht gefunden."})
            if dok.mime not in eingang.LESBAR:
                raise serializers.ValidationError(
                    {"dokumente": f"„{dok.titel}“: dieses Dateiformat kann die Texterkennung nicht lesen."})
            aus.append(dok)
        return aus

    @staticmethod
    def _dateien(request) -> list:
        from django.conf import settings

        dateien = request.FILES.getlist("dateien")
        for d in dateien:
            if d.size > settings.EPM_UPLOAD_MAX_MB * 1024 * 1024:
                raise serializers.ValidationError(
                    {"dateien": f"„{d.name}“ ist größer als {settings.EPM_UPLOAD_MAX_MB} MB."})
        if len(dateien) > 20:
            raise serializers.ValidationError({"dateien": "Höchstens 20 Dateien je Nachricht."})
        return dateien

    @action(detail=False, methods=["post"])
    def diktat(self, request):
        """Diktat → gegliederter Bericht (14.11.2026): ``{"diktat": ID}`` legt eine eigene Unterhaltung mit der Vorlage
        „Diktat als Brief gliedern“ an; der KI-Dienst schreibt den Entwurf wie jede Chat-Antwort (Vorrang, auch
        tagsüber). In den Bericht kommt er erst, wenn die Person ihn in der Diktat-Liste übernimmt."""
        from diktate.models import Diktat

        _recht(request.user, "ki_berichte")
        did = str(request.data.get("diktat") or "")
        d = (Diktat.objects.filter(pk=did, patient__in=patienten_fuer(request.user)).select_related("bericht__art")
             .first() if did.isdigit() else None)
        if d is None:
            return _fehler("Diktat nicht gefunden.", status.HTTP_404_NOT_FOUND)
        if d.status != Diktat.Status.FERTIG or not d.text.strip():
            return _fehler("Das Diktat ist noch nicht abgeschrieben.")
        text = chat.html_zu_text(d.text)
        if len(text) > chat.MAX_ZEICHEN:
            return _fehler(f"Das Diktat ist länger als {chat.MAX_ZEICHEN} Zeichen.")
        vorlage = KiPromptvorlage.objects.filter(name=chat.DIKTAT_VORLAGE, aktiv=True).first()
        art = (getattr(getattr(d.bericht, "art", None), "wert", "") or "").strip() if d.bericht_id else ""
        berichtsart = art or (d.bericht.titel if d.bericht_id else "") or "Arztbrief"
        with transaction.atomic():
            c = KiChat.objects.create(benutzer=request.user, firma=getattr(request.user, "firma", None),
                                      vorlage=vorlage, titel=f"Diktat vom {timezone.localtime(d.erstellt_am):%d.%m.%Y}"
                                                             f" → {berichtsart}"[:200])
            KiChatNachricht.objects.create(chat=c, rolle=KiChatNachricht.Rolle.NUTZER,
                                           text=f"Berichtsart: {berichtsart}\n\nAbschrift des Diktats:\n{text}")
            KiChatNachricht.objects.create(
                chat=c, rolle=KiChatNachricht.Rolle.KI, status=KiChatNachricht.Status.WARTET,
                vorlage_name=vorlage.name if vorlage else chat.DIKTAT_VORLAGE,
                anweisung=vorlage.anweisung if vorlage else chat.DIKTAT_ANWEISUNG,
                temperatur=vorlage.temperatur if vorlage else Decimal("0.10"))
        protokolliere(A.KI, request, objekt=f"KI-Chat {c.pk}", aktion="diktat_gliedern", diktat=d.pk,
                      patient_id=d.patient_id, zeichen=len(text))
        return Response(self._antwort(c), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], parser_classes=[JSONParser, MultiPartParser, FormParser])
    def nachricht(self, request, pk=None):
        from scans.ocr.laden import dateityp

        _recht(request.user, "ki_berichte")
        text = str(request.data.get("text") or "").strip()
        dokumente, dateien = self._akten_dokumente(request), self._dateien(request)
        if not text and not dokumente and not dateien:
            return _fehler("Bitte einen Text eingeben oder ein Dokument anhängen.", feld="text")
        if len(text) > chat.MAX_ZEICHEN:
            return _fehler(f"Höchstens {chat.MAX_ZEICHEN} Zeichen je Nachricht.", feld="text")
        hochgeladen = []
        for d in dateien:
            daten = d.read()
            mime = dateityp(daten[:64])
            if mime is None:
                return _fehler(f"„{d.name}“: erlaubt sind PDF und Bilder (JPG, PNG, TIFF, WEBP, BMP, HEIC).",
                               feld="dateien")
            hochgeladen.append((d.name[:255], mime, daten))
        with transaction.atomic():
            c = self.get_queryset().select_for_update(of=("self",)).filter(pk=pk).first()
            if c is None:
                return _fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
            if c.nachrichten.filter(status__in=[KiChatNachricht.Status.WARTET,
                                                KiChatNachricht.Status.LAEUFT]).exists():
                return _fehler("Die KI schreibt noch an der letzten Antwort.", status.HTTP_409_CONFLICT)
            vorlage = self._vorlage(request.data["vorlage"]) if "vorlage" in request.data else c.vorlage
            c.vorlage = vorlage
            if not c.titel:
                namen = [n for n, _m, _d in hochgeladen] + [d.titel for d in dokumente]
                c.titel = (" ".join(text.split()) or ", ".join(namen))[:60]
            c.save(update_fields=["vorlage", "titel", "aktualisiert_am"])
            frage = KiChatNachricht.objects.create(chat=c, rolle=KiChatNachricht.Rolle.NUTZER, text=text)
            for name, mime, daten in hochgeladen:
                KiChatAnhang.objects.create(nachricht=frage, herkunft=KiChatAnhang.Herkunft.UPLOAD, name=name,
                                            mime=mime, groesse=len(daten), datei=daten)
            for dok in dokumente:
                KiChatAnhang.objects.create(nachricht=frage, herkunft=KiChatAnhang.Herkunft.AKTE, dokument=dok,
                                            patient=dok.patient, name=dok.titel[:255], mime=dok.mime,
                                            groesse=dok.groesse)
            KiChatNachricht.objects.create(
                chat=c, rolle=KiChatNachricht.Rolle.KI, status=KiChatNachricht.Status.WARTET,
                vorlage_name=vorlage.name if vorlage else "", anweisung=vorlage.anweisung if vorlage else "",
                temperatur=vorlage.temperatur if vorlage else Decimal("0.10"))
        protokolliere(A.KI, request, objekt=f"KI-Chat {c.pk}", aktion="chat_nachricht",
                      vorlage=vorlage.name if vorlage else "", zeichen=len(text), dateien=len(hochgeladen))
        # Zugriff auf Akten-Dokumente: wie jede Einsicht mit Patient und Dokument im Protokoll (ohne Inhalt)
        for dok in dokumente:
            protokolliere(A.KI, request, objekt=f"KI-Chat {c.pk}", aktion="chat_dokument_aus_akte",
                          dokument=dok.pk, patient_id=dok.patient_id)
        return Response(self._antwort(c), status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------------------------- Administration
EINSTELLUNG_FELDER = ["aktiv", "nacht_beginn", "nacht_ende", "zeitzone", "worker_nacht", "worker_tag",
                      "max_cpu_prozent", "min_ram_frei_mb", "max_last_je_kern", "pause_bei_sicherung",
                      "altbestand_lesen", "max_seiten", "bild_max_px", "ocr_schwelle", "feld_unsicher",
                      "verknuepfung_stunden", "beispiele_max", "aufbewahrung_tage", "training_erlaubt",
                      "training_nur_wochenende",
                      # Priorisierung, Akte auf einen Blick, Diktat-Nachtfenster, Chat-Aufbewahrung (14.11.2026)
                      "prio_angefordert", "prio_termin", "termin_tage", "prio_neu", "neu_tage", "prio_neu_lesen",
                      "prio_altbestand", "chat_vorrang", "zusammenfassung_tagsueber",
                      "zusammenfassung_ohne_termin_tage", "diktat_nacht_beginn", "diktat_nacht_ende", "chat_tage"]
PRIO_STUFEN = ["prio_termin", "prio_neu", "prio_neu_lesen", "prio_altbestand"]


class EinstellungSerializer(serializers.ModelSerializer):
    geaendert_von_name = serializers.SerializerMethodField()
    rechtsgrundlage_geprueft_von_name = serializers.SerializerMethodField()
    worker_max = serializers.SerializerMethodField()

    class Meta:
        model = KiEinstellung
        fields = EINSTELLUNG_FELDER + ["rechtsgrundlage", "rechtsgrundlage_geprueft_am",
                                       "rechtsgrundlage_geprueft_von_name", "geaendert_am", "geaendert_von_name",
                                       "worker_max"]
        read_only_fields = ["rechtsgrundlage", "rechtsgrundlage_geprueft_am", "geaendert_am"]

    def get_geaendert_von_name(self, obj):
        return benutzername(obj.geaendert_von)

    def get_rechtsgrundlage_geprueft_von_name(self, obj):
        return benutzername(obj.rechtsgrundlage_geprueft_von)

    def get_worker_max(self, obj):
        return KiEinstellung.worker_max()

    def validate_zeitzone(self, wert):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(wert)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Unbekannte Zeitzone.")
        return wert

    def validate(self, attrs):
        grenzen = {"worker_nacht": (1, KiEinstellung.worker_max()), "worker_tag": (0, KiEinstellung.worker_max()),
                   "max_cpu_prozent": (10, 100), "min_ram_frei_mb": (256, 65536), "max_seiten": (1, 500),
                   "bild_max_px": (512, 4096), "verknuepfung_stunden": (1, 336), "aufbewahrung_tage": (1, 90),
                   "beispiele_max": (0, 40), "prio_angefordert": (0, 100), "prio_termin": (0, 100),
                   "termin_tage": (0, 30), "prio_neu": (0, 100), "neu_tage": (1, 90), "prio_neu_lesen": (0, 100),
                   "prio_altbestand": (0, 100), "zusammenfassung_ohne_termin_tage": (7, 730),
                   "diktat_nacht_beginn": (0, 23), "diktat_nacht_ende": (0, 23), "chat_tage": (1, 365)}
        fehler = {}
        for feld, (unten, oben) in grenzen.items():
            if feld in attrs and not (unten <= attrs[feld] <= oben):
                fehler[feld] = f"Erlaubt: {unten}–{oben}."
        for feld in ("ocr_schwelle", "feld_unsicher"):
            if feld in attrs and not (0 <= attrs[feld] <= 1):
                fehler[feld] = "Erlaubt: 0–1."
        if "max_last_je_kern" in attrs and not (0.2 <= attrs["max_last_je_kern"] <= 10):
            fehler["max_last_je_kern"] = "Erlaubt: 0,2–10."
        inst = self.instance
        # „angefordert“ = Priorität ab prio_angefordert: jede andere Stufe muss darunter liegen, sonst nähme der
        # Tagesbetrieb (worker_tag = 0) z. B. Dokumente mit Termin wie angeforderte
        angefordert = attrs.get("prio_angefordert", getattr(inst, "prio_angefordert", 10))
        if not fehler:
            zu_hoch = [f for f in PRIO_STUFEN if attrs.get(f, getattr(inst, f, 0)) >= angefordert]
            if zu_hoch:
                fehler["prio_angefordert"] = "Angeforderte Dokumente brauchen die höchste Priorität (größer als alle " \
                                             "anderen Stufen)."
                for f in zu_hoch:
                    if f in attrs:
                        fehler[f] = f"Muss kleiner sein als „angefordert“ ({angefordert})."
        if attrs.get("training_erlaubt") and not (inst and inst.rechtsgrundlage_geprueft_am):
            fehler["training_erlaubt"] = "Erst die Rechtsgrundlagen-Prüfung dokumentieren."
        if fehler:
            raise serializers.ValidationError(fehler)
        return attrs


class EinstellungenView(APIView):
    permission_classes = [VerwaltenRecht]

    def get(self, request):
        return Response(EinstellungSerializer(KiEinstellung.laden()).data)

    def put(self, request):
        e = KiEinstellung.laden()
        s = EinstellungSerializer(e, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        geaendert = {k: str(v) for k, v in s.validated_data.items() if getattr(e, k) != v}
        alt_angefordert = e.prio_angefordert
        with transaction.atomic():
            s.save(geaendert_von=request.user)
            # Wartende Vorgänge an geänderte Stufen anpassen („angefordert“ bleibt, was angefordert war)
            eingang.prioritaeten_umstellen(alt_angefordert, e)
            if {"prio_termin", "termin_tage", "prio_angefordert"} & set(geaendert):
                eingang.prioritaeten_aktualisieren(e)
        if geaendert:
            protokolliere(A.KI, request, objekt="KI-Einstellungen", aktion="einstellungen", geaendert=geaendert)
        return Response(EinstellungSerializer(e).data)


class RechtsgrundlageView(APIView):
    """Rechtsgrundlagen-Prüfung für das Training dokumentieren (Passwort + zweiter Faktor)."""

    permission_classes = [nur_recht("ki_training_freigeben")]

    def post(self, request):
        from system.api import bestaetigung_pruefen

        text = str(request.data.get("rechtsgrundlage") or "").strip()
        if len(text) < 40:
            return _fehler("Bitte Rechtsgrundlage, Zweck, Umfang und Pseudonymisierung beschreiben (mind. 40 Zeichen).",
                           feld="rechtsgrundlage")
        fehler = bestaetigung_pruefen(request, "ki_rechtsgrundlage")
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        e = KiEinstellung.laden()
        e.rechtsgrundlage, e.rechtsgrundlage_geprueft_von = text[:5000], request.user
        e.rechtsgrundlage_geprueft_am = timezone.now()
        e.save(update_fields=["rechtsgrundlage", "rechtsgrundlage_geprueft_von", "rechtsgrundlage_geprueft_am",
                              "geaendert_am"])
        protokolliere(A.KI, request, objekt="KI-Training", aktion="rechtsgrundlage", text=text[:500])
        return Response(EinstellungSerializer(e).data)


def _gerade_in_arbeit(user) -> dict:
    """Was der KI-Dienst gerade tut und was als Nächstes dran ist (Übersicht „KI (Experimentell)“).

    Dokumente und Berichte nur im Bereich der Person (Firma, Testdaten …); was außerhalb liegt, nur als Anzahl.
    Chats: nur die Anzahl – und ob die eigene Antwort darunter ist; nie Inhalt oder Person fremder Chats."""
    ANGEFORDERT_AB = KiEinstellung.laden().prio_angefordert

    def vorgang(v: KiVorgang) -> dict:
        return {"id": v.id, "dokument_titel": v.dokument.titel, "dokument_datum": v.dokument.datum,
                "patient": v.patient_id, "patient_name": f"{v.patient.nachname}, {v.patient.vorname}",
                "patient_nummer": v.patient.nummer, "schritt": v.schritt, "fortschritt": v.fortschritt,
                "seiten": v.seiten, "begonnen_am": v.begonnen_am, "angefordert": v.prioritaet >= ANGEFORDERT_AB,
                "status": v.status}

    sichtbar = vorgaenge_fuer(user).select_related("dokument", "patient")
    laufend = list(sichtbar.filter(status__in=KiVorgang.IN_ARBEIT).order_by("begonnen_am", "id"))
    alle_laufend = KiVorgang.objects.filter(status__in=KiVorgang.IN_ARBEIT).count()
    wartend = sichtbar.filter(status=S.NEU, patient__eingeschraenkt_am__isnull=True,
                              patient__abgeschlossen_am__isnull=True, dokument__ausgeblendet=False)
    berichte = (KiBerichtsauftrag.objects.filter(status=KiBerichtsauftrag.Status.LAEUFT,
                                                 patient__in=patienten_fuer(user)).select_related("patient"))
    chats = KiChatNachricht.objects.filter(status=KiChatNachricht.Status.LAEUFT)
    return {
        "dokumente": [vorgang(v) for v in laufend],
        "dokumente_andere": max(0, alle_laufend - len(laufend)),
        "berichte": [{"id": b.id, "art_name": b.get_art_display(), "patient": b.patient_id,
                      "patient_name": f"{b.patient.nachname}, {b.patient.vorname}"} for b in berichte],
        "chats": chats.count(),
        "chat_eigener": chats.filter(chat__benutzer=user).exists(),
        "naechste": [vorgang(v) for v in wartend.order_by("-prioritaet", "id")[:3]],
        "wartend": wartend.count(),
        "wartend_angefordert": wartend.filter(prioritaet__gte=ANGEFORDERT_AB).count(),
    }


class StandView(APIView):
    """Stand des KI-Dienstes und der Queue (für die Liste und die Administration)."""

    permission_classes = [AnsehenRecht]

    def get(self, request):
        from .dienst import stand_lesen
        from .steuerung import im_fenster

        e = KiEinstellung.laden()
        dienst = stand_lesen()
        daten = {"dienst": dienst, "nachtfenster": {"beginn": e.nacht_beginn, "ende": e.nacht_ende,
                                                     "zeitzone": e.zeitzone,
                                                     "jetzt": im_fenster(timezone.now(), e.nacht_beginn,
                                                                         e.nacht_ende, e.zeitzone)},
                 "aktiv": e.aktiv}
        daten["arbeit"] = _gerade_in_arbeit(request.user)
        if request.user.hat_recht("ki_verwalten"):
            daten["queue"] = eingang.stand()
            mv = KiModellversion.aktiv("vision")
            daten["modell"] = {"id": mv.pk, "name": mv.name} if mv else None
        return Response(daten)


class ModellSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    aktiviert_von_name = serializers.SerializerMethodField()

    class Meta:
        model = KiModellversion
        fields = ["id", "name", "rolle", "datei", "projektor", "sha256", "groesse", "quantisierung", "status",
                  "status_name", "evaluation", "notiz", "eingespielt_am", "aktiviert_am", "aktiviert_von_name"]
        read_only_fields = ["status", "evaluation", "eingespielt_am", "aktiviert_am"]

    def get_aktiviert_von_name(self, obj):
        return benutzername(obj.aktiviert_von)

    def validate_sha256(self, wert):
        import re

        if not re.fullmatch(r"[0-9a-f]{64}", wert or ""):
            raise serializers.ValidationError("SHA-256 als 64 Hex-Zeichen.")
        return wert

    def validate_datei(self, wert):
        import re

        if not re.fullmatch(r"[A-Za-z0-9._-]{1,200}\.gguf", wert or ""):
            raise serializers.ValidationError("Nur der Dateiname einer GGUF-Datei im Modellordner.")
        return wert

    def validate_projektor(self, wert):
        import re

        if wert and not re.fullmatch(r"[A-Za-z0-9._-]{1,200}\.gguf", wert):
            raise serializers.ValidationError("Nur der Dateiname einer GGUF-Datei im Modellordner.")
        return wert


class ModelleViewSet(viewsets.GenericViewSet):
    """Modell-Registry: ``GET/POST /api/ki/modelle/``; aktivieren (= auch zurückschalten) mit Passwort + 2. Faktor."""

    permission_classes = [VerwaltenRecht]

    def list(self, request):
        return Response(ModellSerializer(KiModellversion.objects.select_related("aktiviert_von"), many=True).data)

    def create(self, request):
        s = ModellSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        mv = s.save()
        protokolliere(A.KI, request, objekt=str(mv), aktion="modell_eingespielt", modell=mv.name, sha256=mv.sha256,
                      datei=mv.datei)
        return Response(ModellSerializer(mv).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def evaluieren(self, request, pk=None):
        """Evaluationslauf anlegen; der KI-Dienst führt ihn im Nachtfenster aus (oder mit ``epm_ki --einmal``)."""
        mv = KiModellversion.objects.filter(pk=pk).first()
        if mv is None:
            return _fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        if not KiEvaluationsfall.objects.exists():
            return _fehler("Noch keine Evaluationsfälle – zuerst aus geprüften Vorgängen erzeugen.")
        lauf = KiEvaluationslauf.objects.create(modellversion=mv)
        if mv.status == KiModellversion.Status.EINGESPIELT:
            mv.status = KiModellversion.Status.EVALUATION
            mv.save(update_fields=["status"])
        protokolliere(A.KI, request, objekt=str(mv), aktion="evaluation_angefordert", lauf=lauf.pk)
        return Response({"lauf": lauf.pk}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def aktivieren(self, request, pk=None):
        from system.api import bestaetigung_pruefen

        from .modellwahl import aktivieren as wechseln

        mv = KiModellversion.objects.filter(pk=pk).first()
        if mv is None:
            return _fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        if mv.status == KiModellversion.Status.GESPERRT:
            return _fehler("Gesperrte Modelle lassen sich nicht aktivieren.")
        if mv.status == KiModellversion.Status.AKTIV:
            return _fehler("Dieses Modell ist bereits aktiv.")
        if mv.status == KiModellversion.Status.EINGESPIELT and request.data.get("ohne_evaluation") is not True:
            return _fehler("Vor dem Wechsel bitte evaluieren (oder ausdrücklich ohne Evaluation aktivieren).")
        fehler = bestaetigung_pruefen(request, "ki_modell_aktivieren")
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        bisher = wechseln(mv, request.user)
        protokolliere(A.KI, request, objekt=str(mv), aktion="modell_aktiviert", modell=mv.name, sha256=mv.sha256,
                      bisher=bisher.name if bisher else "", bisher_sha256=bisher.sha256 if bisher else "",
                      ohne_evaluation=mv.evaluation == {})
        return Response(ModellSerializer(mv).data)

    @action(detail=True, methods=["post"])
    def sperren(self, request, pk=None):
        mv = KiModellversion.objects.filter(pk=pk).first()
        if mv is None:
            return _fehler("Nicht gefunden.", status.HTTP_404_NOT_FOUND)
        if mv.status == KiModellversion.Status.AKTIV:
            return _fehler("Das aktive Modell lässt sich nicht sperren – zuerst ein anderes aktivieren.")
        mv.status = KiModellversion.Status.GESPERRT
        mv.save(update_fields=["status"])
        protokolliere(A.KI, request, objekt=str(mv), aktion="modell_gesperrt", modell=mv.name)
        return Response(ModellSerializer(mv).data)


# ---------------------------------------------------------------------------------------------- Qualität
class QualitaetView(APIView):
    """Qualitäts-Dashboard aus den Mitarbeiterkorrekturen (Auftrag 7)."""

    permission_classes = [AnsehenRecht]

    def get(self, request):
        from .qualitaet import kennzahlen

        return Response(kennzahlen(vorgaenge_fuer(request.user)))


class EvaluationView(APIView):
    """Evaluationsfälle: ``GET`` Übersicht; ``POST {"aktion": "erzeugen"}`` aus geprüften Vorgängen (pseudonymisiert,
    ``ki_verwalten``); ``POST {"aktion": "training_freigeben", "faelle": [ids]}`` (``ki_training_freigeben``, nur mit
    dokumentierter Rechtsgrundlage)."""

    permission_classes = [Angemeldet]

    def get(self, request):
        if not (request.user.hat_recht("ki_verwalten") or request.user.hat_recht("ki_training_freigeben")):
            raise PermissionError("Dafür fehlt das Recht „KI (Experimentell): verwalten“.")
        faelle = KiEvaluationsfall.objects.all()
        return Response({
            "faelle": faelle.count(), "training_freigegeben": faelle.filter(training_freigegeben=True).count(),
            "je_typ": dict(Counter(faelle.values_list("dokumenttyp", flat=True))),
            "liste": [{"id": f.id, "dokumenttyp": f.dokumenttyp, "eingabe_text": f.eingabe_text[:3000],
                       "erwartet": f.erwartet, "training_freigegeben": f.training_freigegeben,
                       "freigegeben_von": benutzername(f.freigegeben_von), "erstellt_am": f.erstellt_am}
                      for f in faelle[:200]],
            "laeufe": [{"id": lauf.id, "modell": lauf.modellversion.name, "gestartet_am": lauf.gestartet_am,
                        "fertig_am": lauf.fertig_am, "faelle": lauf.faelle, "ergebnis": lauf.ergebnis,
                        "fehler": lauf.fehler}
                       for lauf in KiEvaluationslauf.objects.select_related("modellversion")[:50]],
        })

    def post(self, request):
        from .evaluation import faelle_erzeugen

        aktion = request.data.get("aktion")
        if aktion == "erzeugen":
            _recht(request.user, "ki_verwalten")
            n = faelle_erzeugen()
            protokolliere(A.KI, request, objekt="KI-Evaluation", aktion="faelle_erzeugt", anzahl=n)
            return Response({"neu": n}, status=status.HTTP_201_CREATED)
        if aktion == "training_freigeben":
            _recht(request.user, "ki_training_freigeben")
            if not KiEinstellung.laden().rechtsgrundlage_geprueft_am:
                return _fehler("Zuerst die Rechtsgrundlagen-Prüfung dokumentieren.")
            ids = [int(i) for i in request.data.get("faelle") or [] if str(i).isdigit()]
            n = KiEvaluationsfall.objects.filter(pk__in=ids, training_freigegeben=False).update(
                training_freigegeben=True, freigegeben_von=request.user, freigegeben_am=timezone.now())
            protokolliere(A.KI, request, objekt="KI-Training", aktion="training_freigegeben", faelle=ids, anzahl=n)
            return Response({"freigegeben": n})
        return _fehler("Unbekannte Aktion.", feld="aktion")


DOKUMENTTYPEN = [{"wert": w, "name": n} for w, n in Dokumenttyp.choices]


# ---------------------------------------------------------------------------------------------- Einrichtung (Server)
# Wunsch 15.10.2026: Einrichten, Modelle wählen, laden bzw. hochladen, Grenzen, Benchmark, Ausschalten – alles aus der
# Oberfläche statt per SSH. Ausgeführt vom Systemagenten auf dem Server (system/host.py, Aktionen „ki_*“).
EINRICHTUNG_AKTIONEN = {"einrichten": "ki_einrichten", "aus": "ki_aus", "grenzen": "ki_grenzen",
                        "benchmark": "ki_benchmark", "laden": "ki_modell_laden", "loeschen": "ki_modell_loeschen"}


class EinrichtungView(APIView):
    """``GET``: Stand auf dem Server (eingerichtet, Modelldateien, Grenzen, Hardware), Auswahl der Modelle mit
    Empfehlung, laufende und letzte Aufträge, begonnene Uploads. ``POST {"aktion": …}``: Auftrag an den Systemagenten
    (Passwort + zweiter Faktor für einrichten, aus, laden, löschen)."""

    permission_classes = [VerwaltenRecht]

    def get(self, request):
        from system import hochladen, host
        from system.api import AuftragSerializer, auftraege_abgleichen
        from system.models import Systemauftrag

        from .katalog import mit_hardware

        auftraege_abgleichen()
        status_ = host.host_status() or {}
        ki = status_.get("ki") or {}
        speicher = status_.get("speicher") or {}
        kerne = (status_.get("cpu") or {}).get("kerne")
        dateien = {m.get("datei", "") for m in ki.get("modelle") or []}
        auftraege = Systemauftrag.objects.filter(ziel=Systemauftrag.Ziel.SERVER, aktion__startswith="ki_") \
            .select_related("angefordert_von").order_by("-angefordert_am")[:15]
        return Response({
            "agent": {"aktuell": bool(status_.get("aktuell")), "alter_s": status_.get("alter_s")},
            "server": ki, "hardware": {"ram": speicher.get("gesamt"), "ram_frei": speicher.get("verfuegbar"),
                                       "kerne": kerne, "avx2": ki.get("avx2")},
            "katalog": mit_hardware(speicher.get("gesamt"), kerne, dateien),
            "auftraege": AuftragSerializer(auftraege, many=True).data,
            "uploads": hochladen.liste(["ki"]),
            "upload_max": hochladen.ARTEN["ki"]["max"],
        })

    def post(self, request):
        from system.api import auftrag_anlegen

        from .katalog import NACH_SCHLUESSEL

        aktion = request.data.get("aktion")
        code = EINRICHTUNG_AKTIONEN.get(aktion if isinstance(aktion, str) else "")
        if code is None:
            return _fehler(f"Erlaubt: {', '.join(EINRICHTUNG_AKTIONEN)}.", feld="aktion")
        parameter, objekt = {}, None
        if aktion == "laden":
            variante = request.data.get("variante")
            if variante not in NACH_SCHLUESSEL:
                return _fehler("Bitte ein Modell aus der Liste wählen.", feld="variante")
            parameter, objekt = {"variante": variante}, NACH_SCHLUESSEL[variante]["name"]
        elif aktion == "loeschen":
            import re

            datei = str(request.data.get("datei") or "")
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,200}\.gguf", datei):
                return _fehler("Unbekannte Modelldatei.", feld="datei")
            aktiv = KiModellversion.aktiv()
            if aktiv and aktiv.datei == datei:
                return _fehler("Das ist das aktive Modell – zuerst ein anderes aktivieren.", feld="datei")
            parameter, objekt = {"datei": datei}, datei
        elif aktion == "grenzen":
            for name in ("KI_SPEICHER", "KI_WORKER_SPEICHER", "KI_THREADS", "KI_WORKER_MAX", "KI_KONTEXT"):
                wert = request.data.get(name)
                if wert not in (None, ""):
                    parameter[name] = str(wert).strip()[:10]
            if not parameter:
                return _fehler("Bitte mindestens einen Wert angeben.")
        elif aktion == "benchmark":
            parameter = {"eigene": request.data.get("eigene") is True}
        antwort = auftrag_anlegen(request, code, parameter=parameter, objekt=objekt)
        if antwort.status_code == status.HTTP_201_CREATED:
            protokolliere(A.KI, request, objekt=objekt or code, aktion=f"einrichtung_{aktion}", parameter=parameter)
        return antwort


class KiHochladenView(APIView):
    """Modell-Paket in Stücken hochladen (wie Update-Paket und OCR-Modelle): ``POST {"name", "groesse"}``."""

    permission_classes = [VerwaltenRecht]

    def post(self, request):
        from system import hochladen
        from system.verwaltung_api import ORDNER_FEHLT

        return hochladen.beginnen(request, "ki", ORDNER_FEHLT)


class KiHochladenTeilView(APIView):
    permission_classes = [VerwaltenRecht]

    def get_parsers(self):
        from rest_framework.parsers import JSONParser

        from system import hochladen

        return [hochladen.RohParser(), JSONParser()]

    def put(self, request, kennung):
        from system import hochladen

        pfad, meta = hochladen.finde(kennung, ["ki"])
        if pfad is None:
            return _fehler("Dieser Upload ist nicht (mehr) bekannt. Bitte neu beginnen.", status.HTTP_404_NOT_FOUND)
        return hochladen.teil_anhaengen(request, pfad, meta)

    def delete(self, request, kennung):
        from system import hochladen
        from system.models import Systemauftrag

        pfad, meta = hochladen.finde(kennung, ["ki"])
        if pfad is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if Systemauftrag.objects.filter(aktion="ki_modelle", parameter__upload=kennung,
                                        status__in=[Systemauftrag.Status.WARTET, Systemauftrag.Status.LAEUFT]).exists():
            return _fehler("Der Server verarbeitet diese Datei gerade.", status.HTTP_409_CONFLICT)
        hochladen.entfernen(pfad)
        return Response(status=status.HTTP_204_NO_CONTENT)


class KiEinspielenView(APIView):
    """Vollständig hochgeladenes Modell-Paket an den Systemagenten (Passwort + zweiter Faktor)."""

    permission_classes = [VerwaltenRecht]

    def post(self, request, kennung):
        from system import hochladen
        from system.api import auftrag_anlegen

        pfad, meta = hochladen.finde(kennung, ["ki"])
        if pfad is None:
            return _fehler("Dieser Upload ist nicht (mehr) bekannt. Bitte neu beginnen.", status.HTTP_404_NOT_FOUND)
        erhalten = pfad.stat().st_size
        if erhalten != meta.get("groesse"):
            return Response({"fehler": "Die Datei ist noch nicht vollständig hochgeladen.", "erhalten": erhalten},
                            status=status.HTTP_409_CONFLICT)
        name = str(meta.get("name") or "")
        return auftrag_anlegen(request, "ki_modelle", parameter={"upload": kennung, "datei": name},
                               objekt=f"KI-Modelle {name}"[:200], protokoll_details={"datei": name, "groesse": erhalten})


class BenchmarkView(APIView):
    """Ergebnisse des Benchmarks (``data/ki/benchmark-<Datum>.json``, geschrieben von werkzeuge/ki-benchmark.sh)."""

    permission_classes = [VerwaltenRecht]

    def get(self, request):
        import json
        import re

        from django.conf import settings

        aus = []
        try:
            namen = sorted((p for p in settings.EPM_KI.iterdir()
                            if re.fullmatch(r"benchmark-\d{8}-\d{4}\.json", p.name)), reverse=True)[:10]
        except OSError:
            namen = []
        for p in namen:
            try:
                varianten = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            aus.append({"datei": p.name, "zeit": p.name[10:23], "varianten": [
                {"variante": v.get("variante"), "laden_s": v.get("laden_s"), "ram_max_gb": v.get("ram_max_gb"),
                 "cpu_mittel": v.get("cpu_mittel"), "je_kategorie": v.get("je_kategorie") or {}}
                for v in varianten if isinstance(v, dict)]})
        return Response(aus)


# ---------------------------------------------------------------------------------------------- Akte auf einen Blick
def zusammenfassung_daten(z: KiZusammenfassung) -> dict:
    return {"id": z.id, "patient": z.patient_id, "grund": z.grund,
            "termin_datum": z.termin.faellig_am if z.termin_id else None, "von": z.von, "bis": z.bis,
            "von_grund": z.von_grund or None, "status": z.status, "entwurf": z.entwurf, "fakten": z.fakten,
            "pruefung": z.pruefung or None, "fehler": z.fehler,
            "modell": z.modellversion.name if z.modellversion_id else None, "erstellt_am": z.erstellt_am,
            "fertig_am": z.fertig_am, "angefordert_von_name": benutzername(z.angefordert_von)}


class KiZusammenfassungViewSet(viewsets.GenericViewSet):
    """„Akte auf einen Blick“ (14.11.2026): ``GET /api/ki/zusammenfassungen/?patient=ID`` (neueste zuerst, höchstens
    5) und ``POST`` ``{"patient": ID}`` → neue Zusammenfassung auf Anforderung (409, solange eine wartet oder läuft).

    Sichtbar wie die Vorgänge: Akte im Bereich der Person (Firma, Testdaten, Einschränkung) und die Zusammenfassung in
    deren Firma angefordert oder ohne Firma (nachts für einen Termin vorbereitet). Inhalte nie ins Audit-Log."""

    permission_classes = [AnsehenRecht]

    def get_queryset(self):
        qs = KiZusammenfassung.objects.filter(patient__in=patienten_fuer(self.request.user))
        firma = getattr(self.request.user, "firma", None)
        if firma is not None:
            qs = qs.filter(Q(firma__isnull=True) | Q(firma=firma))
        return qs.select_related("termin", "modellversion", "angefordert_von")

    def list(self, request):
        pid = request.query_params.get("patient", "")
        if not pid.isdigit():
            return _fehler("Bitte eine Akte angeben.", feld="patient")
        qs = self.get_queryset().filter(patient_id=int(pid)).order_by("-erstellt_am", "-id")[:5]
        return Response([zusammenfassung_daten(z) for z in qs])

    def create(self, request):
        from patienten.models import Patient

        _recht(request.user, "ki_berichte")
        pid = str(request.data.get("patient") or "")
        with transaction.atomic():
            # Akte sperren: zweimal gleichzeitig „Neu erstellen“ ergäbe sonst zwei wartende
            p = (Patient.objects.select_for_update().filter(pk=pid, pk__in=patienten_fuer(request.user)).first()
                 if pid.isdigit() else None)
            if p is None:
                return _fehler("Akte nicht gefunden.", feld="patient")
            if p.eingeschraenkt_am is not None:
                return _fehler("Die Verarbeitung dieser Akte ist eingeschränkt.", feld="patient")
            if KiZusammenfassung.objects.filter(patient=p, status__in=KiZusammenfassung.OFFEN).exists():
                return _fehler("Für diese Akte wird gerade eine Zusammenfassung erstellt.", status.HTTP_409_CONFLICT)
            z = KiZusammenfassung.objects.create(patient=p, firma=getattr(request.user, "firma", None),
                                                 grund=KiZusammenfassung.Grund.ANGEFORDERT,
                                                 angefordert_von=request.user)
        protokolliere(A.KI, request, objekt=f"Akte auf einen Blick {z.pk}", aktion="zusammenfassung_angefordert",
                      patient_id=p.pk)
        return Response(zusammenfassung_daten(self.get_queryset().get(pk=z.pk)), status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------------------------- Nachtaufgaben
class AufgabeSerializer(serializers.ModelSerializer):
    art_name = serializers.CharField(source="get_art_display", read_only=True)
    naechster_lauf = serializers.SerializerMethodField()
    geaendert_von_name = serializers.SerializerMethodField()
    uhrzeit = serializers.TimeField(format="%H:%M")

    class Meta:
        model = KiAufgabe
        fields = ["id", "name", "art", "art_name", "aktiv", "wochentage", "uhrzeit", "parameter", "naechster_lauf",
                  "letzter_lauf", "letztes_ergebnis", "jetzt_angefordert", "geaendert_am", "geaendert_von_name"]
        read_only_fields = ["letzter_lauf", "letztes_ergebnis", "jetzt_angefordert", "geaendert_am"]

    def get_naechster_lauf(self, obj):
        from .aufgaben import naechster_lauf

        return naechster_lauf(obj)

    def get_geaendert_von_name(self, obj):
        return benutzername(obj.geaendert_von) if obj.geaendert_von_id else None

    def validate_name(self, wert):
        if not wert.strip():
            raise serializers.ValidationError("Bitte einen Namen eingeben.")
        return wert.strip()

    def validate_wochentage(self, wert):
        if not isinstance(wert, list) or not wert or any(isinstance(t, bool) or t not in range(7) for t in wert):
            raise serializers.ValidationError("Mindestens ein Wochentag (0 = Montag … 6 = Sonntag).")
        return sorted(set(wert))

    def validate(self, attrs):
        from .aufgaben import parameter_pruefen

        art = attrs.get("art", getattr(self.instance, "art", None))
        if art is None:
            raise serializers.ValidationError({"art": "Bitte eine Art wählen."})
        if "parameter" in attrs or "art" in attrs or self.instance is None:
            vorher = self.instance.parameter if self.instance is not None and art == self.instance.art else {}
            try:
                attrs["parameter"] = parameter_pruefen(art, attrs.get("parameter", vorher))
            except ValueError as e:
                raise serializers.ValidationError(e.args[0])
        return attrs


class KiAufgabeViewSet(viewsets.ModelViewSet):
    """Nachtaufgaben (Administration › KI): ``GET/POST /api/ki/aufgaben/``, ``PATCH/DELETE …/{id}/``,
    ``POST …/{id}/jetzt/`` (läuft beim nächsten Durchlauf des KI-Dienstes). Recht „KI verwalten“."""

    permission_classes = [VerwaltenRecht]
    serializer_class = AufgabeSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return KiAufgabe.objects.select_related("geaendert_von")

    def perform_create(self, serializer):
        a = serializer.save(geaendert_von=self.request.user)
        protokolliere(A.KI, self.request, objekt=f"KI-Aufgabe {a.pk}", aktion="aufgabe_angelegt",
                      aufgabenart=a.art, name=a.name, aktiv=a.aktiv)

    def perform_update(self, serializer):
        a = serializer.save(geaendert_von=self.request.user)
        protokolliere(A.KI, self.request, objekt=f"KI-Aufgabe {a.pk}", aktion="aufgabe_geaendert",
                      aufgabenart=a.art, name=a.name, aktiv=a.aktiv, wochentage=a.wochentage, uhrzeit=str(a.uhrzeit),
                      parameter=a.parameter)

    def perform_destroy(self, instance):
        protokolliere(A.KI, self.request, objekt=f"KI-Aufgabe {instance.pk}", aktion="aufgabe_geloescht",
                      aufgabenart=instance.art, name=instance.name)
        instance.delete()

    @action(detail=True, methods=["post"])
    def jetzt(self, request, pk=None):
        a = self.get_object()
        # update statt save: „geändert am“ bleibt – sonst fiele der heutige Lauf zur Uhrzeit weg
        KiAufgabe.objects.filter(pk=a.pk).update(jetzt_angefordert=True)
        a.refresh_from_db()
        protokolliere(A.KI, request, objekt=f"KI-Aufgabe {a.pk}", aktion="aufgabe_jetzt", aufgabenart=a.art)
        return Response(AufgabeSerializer(a).data)
