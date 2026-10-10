"""API des Menüpunkts „Scans“ (F160–F167). Alle Endpunkte unter ``/api/scans/``.

Recht „Scans: hochladen, erkennen, zuordnen“ für alles; Zuordnen zusätzlich „Einträge erfassen“ für die Akte
(Admins wie überall nur bei Testpatienten), Diagnosen und Texte in die Akte zusätzlich „Akten bearbeiten“.
"""
from __future__ import annotations

import html
import re
from urllib.parse import quote

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import nur_recht
from audit.models import SystemEreignis, protokolliere
from audit.bereinigung import akte_text
from epm.api_basis import benutzername, patienten_fuer, pruefe_schreibbereich
from epm.sanitize import bereinige_html
from stammdaten.models import Auswahlwert, Einstellungen

from . import dienst, lernen
from .models import GelernteZuordnung, Scan, ScanSeite

A = SystemEreignis.Art
ScansRecht = nur_recht("scans_bearbeiten")


class GelerntRecht(permissions.BasePermission):
    """Gelernte Zuordnungen und Kennzahl (F182): wer Scans bearbeitet oder die Kataloge pflegt (Vorlagen pflegen).
    Ändern (sperren, löschen) nicht für Testzugänge – das Gelernte wirkt für alle."""

    message = "Dafür fehlt das Recht „Scans: hochladen, erkennen, zuordnen“ oder „Vorlagen pflegen“."

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated and (u.hat_recht("scans_bearbeiten") or u.hat_recht("vorlagen_pflegen"))):
            return False
        return request.method in permissions.SAFE_METHODS or not getattr(u, "ist_test", False)


GELERNT_AKTIONEN = {"gelernt", "gelernt_eintrag", "kennzahl"}


def _fehler(text: str, code=status.HTTP_400_BAD_REQUEST, feld: str = "fehler"):
    return Response({feld: text}, status=code)


# ---------------------------------------------------------------- Darstellung
class SeiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanSeite
        fields = ["id", "nr", "status", "fehler", "roh_breite", "roh_hoehe", "herkunft", "kamera", "einstellungen",
                  "info", "auftrag", "breite", "hoehe", "ergebnis", "text", "sicherheit", "unsicher", "erkannt_am",
                  "textebene_vorhanden"]

    textebene_vorhanden = serializers.SerializerMethodField()

    def get_textebene_vorhanden(self, obj):
        return bool(obj.textebene)


class ScanListeSerializer(serializers.ModelSerializer):
    hochgeladen_von_name = serializers.SerializerMethodField()
    seiten_anzahl = serializers.SerializerMethodField()
    vorschau = serializers.SerializerMethodField()
    arten = serializers.SerializerMethodField()
    hoechst_bis = serializers.SerializerMethodField()
    verlaengerbar = serializers.SerializerMethodField()
    eigener = serializers.SerializerMethodField()
    quelle = serializers.SerializerMethodField()

    class Meta:
        model = Scan
        fields = ["id", "titel", "originalname", "mime", "groesse", "status", "fortschritt", "schritt", "fehler",
                  "hochgeladen_am", "hochgeladen_von_name", "eigener", "ist_test", "laeuft_ab_am", "hoechst_bis",
                  "verlaengerbar", "verlaengert_anzahl", "seiten_anzahl", "vorschau", "sicherheit", "unsicher",
                  "arten", "dokumentdatum", "verfahren", "belegt", "erkannt_am", "dauer_s", "quelle"]

    def get_hochgeladen_von_name(self, obj):
        return benutzername(obj.hochgeladen_von)

    def get_eigener(self, obj):
        return obj.hochgeladen_von_id == self.context["request"].user.id

    def get_quelle(self, obj):
        """Arbeitskopie eines Akte-Dokuments („Werte übernehmen“, F171): Dokument und Patient."""
        d = obj.quelldokument
        if d is None:
            return None
        p = d.patient
        return {"dokument": d.id, "titel": d.titel, "patient": {"id": p.id, "nummer": p.nummer, "nachname": p.nachname,
                "vorname": p.vorname, "geburtsdatum": p.geburtsdatum, "ist_test": p.ist_test}}

    def get_seiten_anzahl(self, obj):
        return len(obj.seiten.all())

    def get_vorschau(self, obj):
        erste = next((s for s in sorted(obj.seiten.all(), key=lambda s: (s.nr, s.id)) if s.klein), None)
        return f"/api/scans/{obj.id}/seiten/{erste.id}/bild/?art=klein&v={erste.klein}" if erste else None

    def get_arten(self, obj):
        return (obj.auswertung or {}).get("arten", [])

    def _hoechst(self, obj):
        tage = self.context.get("hoechst_tage")
        if tage is None:
            tage = Einstellungen.aktuell().scans_hoechst_tage
            self.context["hoechst_tage"] = tage
        from datetime import timedelta

        return obj.hochgeladen_am + timedelta(days=tage)

    def get_hoechst_bis(self, obj):
        return self._hoechst(obj)

    def get_verlaengerbar(self, obj):
        from datetime import timedelta

        return self._hoechst(obj) > obj.laeuft_ab_am + timedelta(minutes=1)


class ScanSerializer(ScanListeSerializer):
    seiten = serializers.SerializerMethodField()
    auswertung = serializers.SerializerMethodField()

    class Meta(ScanListeSerializer.Meta):
        fields = ScanListeSerializer.Meta.fields + ["text", "seiten", "auswertung"]

    def get_seiten(self, obj):
        return SeiteSerializer(obj.seiten.order_by("nr", "id"), many=True).data

    def get_auswertung(self, obj):
        a = dict(obj.auswertung or {})
        # Hinweise auf den Patienten bleiben im Server (Abgleich), die Oberfläche bekommt die Vorschläge
        a.pop("patient", None)
        return a


def _belegt_text(n: int) -> str:
    return f"{n / 1024 / 1024:.0f} MB"


class ScanViewSet(viewsets.GenericViewSet):
    permission_classes = [ScansRecht]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    pagination_class = None

    def get_permissions(self):
        if getattr(self, "action", None) in GELERNT_AKTIONEN:
            return [GelerntRecht()]
        return super().get_permissions()

    def get_queryset(self):
        return (dienst.sichtbare_scans(self.request.user).filter(laeuft_ab_am__gt=timezone.now())
                .select_related("hochgeladen_von").prefetch_related("seiten"))

    def _scan(self, pk, bearbeitbar=False) -> Scan:
        scan = self.get_queryset().filter(pk=pk).first()
        if scan is None:
            raise serializers.ValidationError({"fehler": "Diesen Scan gibt es nicht (mehr)."})
        if bearbeitbar and not scan.bearbeitbar:
            raise _Konflikt("Der Scan wird gerade erkannt. Bitte einen Moment warten.")
        return scan

    def _seite(self, scan: Scan, sid) -> ScanSeite:
        seite = scan.seiten.filter(pk=sid).first()
        if seite is None:
            raise serializers.ValidationError({"fehler": "Diese Seite gibt es nicht (mehr)."})
        return seite

    # ------------------------------------------------------------ Liste, Hochladen, Ändern, Löschen
    def list(self, request):
        dienst.bereinigen_hoechstens_stuendlich()
        qs = self.get_queryset()
        suche = (request.query_params.get("suche") or "").strip()
        if suche:
            from django.db.models import Q

            qs = qs.filter(Q(text__icontains=suche) | Q(titel__icontains=suche) | Q(originalname__icontains=suche))
        return Response(ScanListeSerializer(qs, many=True, context={"request": request}).data)

    def create(self, request):
        dateien = request.FILES.getlist("dateien") or request.FILES.getlist("datei")
        titel = str(request.data.get("titel") or "").strip()[:200]
        try:
            scan = dienst.neuer_scan(dateien, request.user, titel)
        except dienst.ScanFehler as fehler:
            return _fehler(str(fehler), feld="datei")
        protokolliere(A.SCAN, request, objekt=str(scan), aktion="hochgeladen", scan=scan.pk, dateien=len(dateien),
                      groesse=scan.groesse, sha256=scan.sha256)
        return Response(ScanSerializer(scan, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        scan = self._scan(pk)
        daten = ScanSerializer(scan, context={"request": request}).data
        daten["vorschlaege"] = dienst.patient_vorschlaege(scan, request.user) if scan.status == Scan.Status.FERTIG else []
        return Response(daten)

    def partial_update(self, request, pk=None):
        scan = self._scan(pk)
        titel = str(request.data.get("titel") or "").strip()
        if not titel:
            return _fehler("Bitte einen Titel angeben.", feld="titel")
        Scan.objects.filter(pk=scan.pk).update(titel=titel[:200])
        scan.refresh_from_db()
        return Response(ScanSerializer(scan, context={"request": request}).data)

    def destroy(self, request, pk=None):
        scan = self._scan(pk)
        seiten = scan.seiten.count()
        with transaction.atomic():
            protokolliere(A.SCAN, request, objekt=str(scan), aktion="geloescht", scan=scan.pk, seiten=seiten,
                          sha256=scan.sha256)
            dienst.entfernen(scan)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def stand(self, request):
        """Zähler für Navigation und Startseite, Grenzen der Aufbewahrung, bereitstehende Verfahren."""
        e = Einstellungen.aktuell()
        daten = dienst.stand(request.user)
        daten.update({"frist_tage": e.scans_frist_tage, "hoechst_tage": e.scans_hoechst_tage,
                      "verlaengerung_tage": e.scans_verlaengerung_tage, "max_mb": e.scans_max_mb,
                      "max_seiten": settings.EPM_SCANS_MAX_SEITEN, "upload_max_mb": settings.EPM_UPLOAD_MAX_MB})
        if str(request.query_params.get("verfahren", "")) == "1":
            daten["verfahren"] = dienst.verfahren()
            daten["dienst"] = dienst.dienst_stand()
        return Response(daten)

    # ------------------------------------------------------------ Gelernte Zuordnungen und Kennzahl (F182)
    @action(detail=False, methods=["get"])
    def gelernt(self, request):
        """Liste der gelernten Zuordnungen: ``?suche=…&art=labor|bia|diagnose|spalte&quelle=<normalisiert>|allgemein``."""
        from django.db.models import Q

        qs = GelernteZuordnung.objects.select_related("parameter", "zuletzt_von")
        art = request.query_params.get("art") or ""
        if art in GelernteZuordnung.Art.values:
            qs = qs.filter(art=art)
        quelle = request.query_params.get("quelle")
        if quelle == "allgemein":
            qs = qs.filter(quelle="")
        elif quelle:
            qs = qs.filter(quelle=quelle)
        suche = (request.query_params.get("suche") or "").strip()
        if suche:
            qs = qs.filter(Q(erkannt_anzeige__icontains=suche) | Q(erkannt__icontains=suche)
                           | Q(ziel_text__icontains=suche) | Q(ziel__icontains=suche)
                           | Q(quelle_anzeige__icontains=suche))
        qs = qs.order_by("-zuletzt_am", "-id")[:1000]
        quellen = (GelernteZuordnung.objects.exclude(quelle="").order_by("quelle")
                   .values_list("quelle", "quelle_anzeige").distinct())
        return Response({
            "eintraege": [_gelernt_daten(g) for g in qs],
            "quellen": [{"quelle": q, "name": n or q} for q, n in dict(quellen).items()],
            "schwelle": lernen.auswertung.SCHWELLE,
            "darf_aendern": not getattr(request.user, "ist_test", False),
        })

    @action(detail=False, methods=["patch", "delete"], url_path=r"gelernt/(?P<gid>\d+)")
    def gelernt_eintrag(self, request, gid=None):
        """Sperren bzw. entsperren (``{"gesperrt": true}`` = „nie wieder so zuordnen“) oder löschen."""
        g = GelernteZuordnung.objects.filter(pk=gid).first()
        if g is None:
            return _fehler("Diese gelernte Zuordnung gibt es nicht (mehr).", status.HTTP_404_NOT_FOUND)
        beschreibung = {"bereich": g.art, "quelle": g.quelle_anzeige or "allgemein", "erkannt": g.erkannt_anzeige,
                        "ziel": g.ziel_text or g.ziel}
        if request.method == "DELETE":
            g.delete()
            protokolliere(A.SCAN, request, objekt="Gelernte Zuordnung", aktion="gelernt_geloescht", **beschreibung)
            return Response(status=status.HTTP_204_NO_CONTENT)
        if not isinstance(request.data.get("gesperrt"), bool):
            return _fehler("Bitte „gesperrt“ angeben.", feld="gesperrt")
        g.gesperrt = request.data["gesperrt"]
        g.zuletzt_von = request.user
        g.save(update_fields=["gesperrt", "zuletzt_von"])
        protokolliere(A.SCAN, request, objekt="Gelernte Zuordnung",
                      aktion="gelernt_gesperrt" if g.gesperrt else "gelernt_entsperrt", **beschreibung)
        return Response(_gelernt_daten(g))

    @action(detail=False, methods=["get"])
    def kennzahl(self, request):
        """Wie oft musste korrigiert werden? Anteil je Monat (letzte 12), dazu Trend zum Vormonat."""
        return Response(lernen.kennzahl())

    @action(detail=True, methods=["post"])
    def verlaengern(self, request, pk=None):
        scan = self._scan(pk)
        try:
            dienst.verlaengern(scan, request.user, request)
        except dienst.ScanFehler as fehler:
            return _fehler(str(fehler))
        scan.refresh_from_db()
        return Response(ScanSerializer(scan, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def erneut(self, request, pk=None):
        """Nach einem Fehler oder nach geänderten Einstellungen: alle Seiten neu erkennen."""
        scan = self._scan(pk, bearbeitbar=True)
        with transaction.atomic():
            scan.seiten.update(status=ScanSeite.Status.WARTET, auftrag={"art": "seite"}, fehler="")
            if not scan.seiten.exists():
                # Seiten noch nicht angelegt (Fehler beim Laden): der Dienst beginnt von vorn
                pass
            Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.WARTET, fehler="", schritt="in der Warteschlange",
                                                   fortschritt=0, versuche=0)
        scan.refresh_from_db()
        return Response(ScanSerializer(scan, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def auswerten(self, request, pk=None):
        """Werte neu ermitteln (z. B. nachdem der Laborkatalog ergänzt wurde)."""
        scan = self._scan(pk, bearbeitbar=True)
        if scan.status != Scan.Status.FERTIG:
            return _fehler("Der Scan ist noch nicht erkannt.")
        dienst.auswerten(scan)
        Scan.objects.filter(pk=scan.pk).update(auswertung=scan.auswertung, dokumentdatum=scan.dokumentdatum)
        return self.retrieve(request, pk)

    # ------------------------------------------------------------ Seiten
    @action(detail=True, methods=["get"], url_path=r"seiten/(?P<sid>\d+)/bild")
    def seitenbild(self, request, pk=None, sid=None):
        scan = self._scan(pk)
        seite = self._seite(scan, sid)
        art = request.query_params.get("art", "bild")
        name = {"bild": seite.bild, "roh": seite.roh, "klein": seite.klein, "grau": seite.grau}.get(art)
        if not name:
            return _fehler("Dieses Bild gibt es (noch) nicht.", status.HTTP_404_NOT_FOUND)
        pfad = seite.datei(name)
        if not pfad.is_file():
            return _fehler("Die Bilddatei fehlt.", status.HTTP_404_NOT_FOUND)
        mime = "image/png" if name.endswith(".png") else "image/jpeg"
        antwort = FileResponse(open(pfad, "rb"), content_type=mime)
        # Name der Datei wechselt mit jeder neuen Aufbereitung – darf im Browser zwischengespeichert werden
        antwort["Cache-Control"] = "private, max-age=3600"
        antwort["X-Content-Type-Options"] = "nosniff"
        return antwort

    @action(detail=True, methods=["patch"], url_path=r"seiten/(?P<sid>\d+)")
    def seite(self, request, pk=None, sid=None):
        """Einstellungen einer Seite ändern (Ecken, Drehung, Glätten, Schräglage, Modus, Kontrast, Helligkeit,
        Textebene) – die Seite wird danach neu aufbereitet und erkannt."""
        from .ocr.aufbereitung import Einstellungen as SeitenEinstellungen

        scan = self._scan(pk, bearbeitbar=True)
        seite = self._seite(scan, sid)
        roh = request.data.get("einstellungen")
        if not isinstance(roh, dict):
            return _fehler("Bitte Einstellungen angeben.", feld="einstellungen")
        neu = SeitenEinstellungen.aus_json(roh).als_json()
        neu["textebene"] = roh.get("textebene", True) is not False
        with transaction.atomic():
            ScanSeite.objects.filter(pk=seite.pk).update(einstellungen=neu, status=ScanSeite.Status.WARTET,
                                                         auftrag={"art": "seite"}, fehler="")
            Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.WARTET, schritt="in der Warteschlange",
                                                   fortschritt=0, fehler="", versuche=0)
        scan.refresh_from_db()
        return Response(ScanSerializer(scan, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path=r"seiten/(?P<sid>\d+)/vorschau")
    def vorschau(self, request, pk=None, sid=None):
        """Vorschau beim Anpassen: die Seite mit den übergebenen Einstellungen aufbereitet (ohne Erkennung, verkleinert,
        ohne Glätten). Nichts wird gespeichert."""
        scan = self._scan(pk)
        seite = self._seite(scan, sid)
        roh = request.data.get("einstellungen")
        if not isinstance(roh, dict):
            return _fehler("Bitte Einstellungen angeben.", feld="einstellungen")
        if not seite.roh:
            return _fehler("Diese Seite hat (noch) kein Bild.", status.HTTP_404_NOT_FOUND)
        try:
            bild, mime = dienst.vorschau(seite, roh)
        except dienst.ScanFehler as fehler:
            return _fehler(str(fehler))
        antwort = HttpResponse(bild, content_type=mime)
        antwort["Cache-Control"] = "no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        return antwort

    @action(detail=True, methods=["post"], url_path=r"seiten/(?P<sid>\d+)/bereich")
    def bereich(self, request, pk=None, sid=None):
        """Einen Bereich neu erkennen: ``{"box": [x, y, b, h] (0–1), "staerke": -50…50}``."""
        scan = self._scan(pk, bearbeitbar=True)
        seite = self._seite(scan, sid)
        if seite.status != ScanSeite.Status.FERTIG or not seite.grau:
            return _fehler("Die Seite ist noch nicht erkannt.")
        box = request.data.get("box")
        try:
            box = [float(v) for v in box]
            staerke = int(request.data.get("staerke") or 0)
        except (TypeError, ValueError):
            return _fehler("Bitte einen Bereich angeben.", feld="box")
        if len(box) != 4 or box[2] <= 0.005 or box[3] <= 0.005 or not all(0 <= v <= 1 for v in box):
            return _fehler("Bitte einen Bereich auf der Seite markieren.", feld="box")
        with transaction.atomic():
            ScanSeite.objects.filter(pk=seite.pk).update(
                auftrag={"art": "bereich", "box": box, "staerke": max(-50, min(50, staerke))})
            Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.WARTET, schritt="Bereich wird neu erkannt",
                                                   fortschritt=0, fehler="", versuche=0)
        scan.refresh_from_db()
        return Response(ScanSerializer(scan, context={"request": request}).data)

    @action(detail=True, methods=["delete"], url_path=r"seiten/(?P<sid>\d+)/entfernen")
    def seite_entfernen(self, request, pk=None, sid=None):
        scan = self._scan(pk, bearbeitbar=True)
        seite = self._seite(scan, sid)
        if scan.seiten.count() <= 1:
            return _fehler("Die letzte Seite kann nicht entfernt werden – stattdessen den Scan löschen.")
        dateien = [seite.roh, seite.bild, seite.grau, seite.klein]
        with transaction.atomic():
            seite.delete()
            for nr, s in enumerate(scan.seiten.order_by("nr", "id"), 1):
                if s.nr != nr:
                    ScanSeite.objects.filter(pk=s.pk).update(nr=nr)
            if scan.status == Scan.Status.FERTIG:
                scan.refresh_from_db()
                dienst.auswerten(scan)
                scan.save()
        for name in dateien:
            if name:
                (scan.pfad / name).unlink(missing_ok=True)
        dienst.belegung_aktualisieren(scan)
        scan.refresh_from_db()
        return Response(ScanSerializer(scan, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reihenfolge(self, request, pk=None):
        """``{"seiten": [ID, …]}`` – neue Reihenfolge aller Seiten."""
        scan = self._scan(pk, bearbeitbar=True)
        ids = request.data.get("seiten")
        vorhanden = list(scan.seiten.values_list("id", flat=True))
        if not isinstance(ids, list) or sorted(int(i) for i in ids) != sorted(vorhanden):
            return _fehler("Bitte alle Seiten in der neuen Reihenfolge angeben.", feld="seiten")
        with transaction.atomic():
            for nr, sid in enumerate(ids, 1):
                ScanSeite.objects.filter(pk=int(sid), scan=scan).update(nr=nr)
            if scan.status == Scan.Status.FERTIG:
                scan.refresh_from_db()
                dienst.auswerten(scan)
                scan.save()
        scan.refresh_from_db()
        return Response(ScanSerializer(scan, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def aufteilen(self, request, pk=None):
        """Stapel trennen: ``{"ab": Seiten-ID}`` – diese und alle folgenden Seiten werden ein eigener Scan."""
        import secrets
        import shutil

        scan = self._scan(pk, bearbeitbar=True)
        seiten = list(scan.seiten.order_by("nr", "id"))
        ab = next((i for i, s in enumerate(seiten) if str(s.id) == str(request.data.get("ab"))), None)
        if ab is None or ab == 0:
            return _fehler("Bitte die Seite wählen, mit der der neue Scan beginnt (nicht die erste).", feld="ab")
        if scan.status not in (Scan.Status.FERTIG, Scan.Status.FEHLER):
            return _fehler("Erst nach der Erkennung aufteilbar.")
        weg = seiten[ab:]
        ordner = secrets.token_hex(16)
        ziel = settings.EPM_SCANS / ordner
        ziel.mkdir(mode=0o750, parents=True)
        try:
            with transaction.atomic():
                neu = Scan.objects.create(
                    titel=f"{scan.titel} (ab Seite {weg[0].nr})"[:200], originalname=scan.originalname,
                    mime=scan.mime, groesse=0, sha256=scan.sha256, ordner=ordner, hochgeladen_von=scan.hochgeladen_von,
                    ist_test=scan.ist_test, laeuft_ab_am=scan.laeuft_ab_am, status=scan.status,
                    verlaengert_anzahl=scan.verlaengert_anzahl, erkannt_am=scan.erkannt_am,
                    auswertung={"originale": []})
                Scan.objects.filter(pk=neu.pk).update(hochgeladen_am=scan.hochgeladen_am)
                for nr, s in enumerate(weg, 1):
                    for name in (s.roh, s.bild, s.grau, s.klein):
                        if name and (scan.pfad / name).is_file():
                            shutil.copy2(scan.pfad / name, ziel / name)
                    ScanSeite.objects.filter(pk=s.pk).update(scan=neu, nr=nr)
                for teil in (scan, neu):
                    teil.refresh_from_db()
                    if teil.status == Scan.Status.FERTIG:
                        dienst.auswerten(teil)
                        teil.save()
        except BaseException:
            shutil.rmtree(ziel, ignore_errors=True)
            raise
        for s in weg:
            for name in (s.roh, s.bild, s.grau, s.klein):
                if name:
                    (scan.pfad / name).unlink(missing_ok=True)
        dienst.belegung_aktualisieren(scan)
        dienst.belegung_aktualisieren(neu)
        protokolliere(A.SCAN, request, objekt=str(scan), aktion="aufgeteilt", scan=scan.pk, neu=neu.pk,
                      seiten=len(weg))
        return Response({"scan": ScanSerializer(self._scan(pk), context={"request": request}).data,
                         "neu": neu.pk}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def zusammenfuehren(self, request, pk=None):
        """``{"mit": Scan-ID}`` – dessen Seiten werden hinten angehängt, der andere Scan entfällt."""
        import shutil

        scan = self._scan(pk, bearbeitbar=True)
        try:
            anderer = self._scan(int(request.data.get("mit")), bearbeitbar=True)
        except (TypeError, ValueError):
            return _fehler("Bitte den Scan wählen, der angehängt werden soll.", feld="mit")
        if anderer.pk == scan.pk:
            return _fehler("Ein Scan kann nicht mit sich selbst zusammengeführt werden.", feld="mit")
        if anderer.ist_test != scan.ist_test:
            return _fehler("Scans eines Testzugangs und andere Scans werden nicht zusammengeführt.", feld="mit")
        if Scan.Status.FERTIG not in (scan.status,) or anderer.status != Scan.Status.FERTIG:
            return _fehler("Beide Scans müssen erkannt sein.")
        start = scan.seiten.count()
        kopiert = []
        with transaction.atomic():
            for i, s in enumerate(anderer.seiten.order_by("nr", "id"), 1):
                for name in (s.roh, s.bild, s.grau, s.klein):
                    if name and (anderer.pfad / name).is_file():
                        shutil.copy2(anderer.pfad / name, scan.pfad / name)
                        kopiert.append(scan.pfad / name)
                ScanSeite.objects.filter(pk=s.pk).update(scan=scan, nr=start + i)
            laeuft = max(scan.laeuft_ab_am, anderer.laeuft_ab_am)
            Scan.objects.filter(pk=scan.pk).update(laeuft_ab_am=laeuft)
            protokolliere(A.SCAN, request, objekt=str(scan), aktion="zusammengefuehrt", scan=scan.pk,
                          mit=anderer.pk)
            dienst.entfernen(Scan.objects.get(pk=anderer.pk))
            scan.refresh_from_db()
            dienst.auswerten(scan)
            scan.save()
        dienst.belegung_aktualisieren(scan)
        return Response(ScanSerializer(self._scan(pk), context={"request": request}).data)

    # ------------------------------------------------------------ Ergebnis: PDF, Text
    def _pdf(self, scan: Scan) -> bytes:
        from .ocr import pdf

        seiten = []
        for s in scan.seiten.order_by("nr", "id"):
            if s.status != ScanSeite.Status.FERTIG or not s.bild:
                raise serializers.ValidationError({"fehler": f"Seite {s.nr} ist nicht erkannt."})
            bild = dienst.lade_bild(s.datei(s.bild), grau=s.bild.endswith(".png") or
                                    (s.einstellungen or {}).get("modus", "graustufen") != "farbe")
            seiten.append((bild, s.ergebnis))
        return pdf.erstellen(seiten, scan.titel)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Durchsuchbare PDF (Seitenbilder mit unsichtbarem Text) zum Herunterladen."""
        scan = self._scan(pk)
        if scan.status != Scan.Status.FERTIG:
            return _fehler("Der Scan ist noch nicht erkannt.")
        daten = self._pdf(scan)
        protokolliere(A.EXPORT, request, objekt=str(scan), was="Scan", format="PDF")
        antwort = HttpResponse(daten, content_type="application/pdf")
        name = re.sub(r"[^\w\-. äöüÄÖÜß]", "_", scan.titel)[:120] or "Scan"
        antwort["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name + '.pdf')}"
        antwort["Cache-Control"] = "private, no-store"
        return antwort

    @action(detail=True, methods=["get"])
    def textdatei(self, request, pk=None):
        scan = self._scan(pk)
        protokolliere(A.EXPORT, request, objekt=str(scan), was="Scan", format="Text")
        antwort = HttpResponse(scan.text, content_type="text/plain; charset=utf-8")
        name = re.sub(r"[^\w\-. äöüÄÖÜß]", "_", scan.titel)[:120] or "Scan"
        antwort["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name + '.txt')}"
        antwort["Cache-Control"] = "private, no-store"
        return antwort

    # ------------------------------------------------------------ Zuordnen
    @action(detail=True, methods=["get"])
    def pruefen(self, request, pk=None):
        """Passt das Dokument zum gewählten Patienten? ``?patient=ID`` → Hinweise (leer = nichts aufgefallen)."""
        scan = self._scan(pk)
        pid = str(request.query_params.get("patient") or "")
        patient = patienten_fuer(request.user).filter(pk=pid).first() if pid.isdigit() else None
        if patient is None:
            return _fehler("Patient nicht gefunden.", feld="patient")
        return Response({"hinweise": dienst.zuordnung_pruefen(scan, patient)})

    @action(detail=True, methods=["post"])
    def zuordnen(self, request, pk=None):
        return zuordnen(self, request, pk)


BIA_NAMEN = {"gewicht_kg": "Gewicht (kg)", "bcm_kg": "BCM (kg)", "fettmasse_kg": "Fettmasse (kg)",
             "ecw_prozent": "ECW (%)", "koerperwasser_l": "Körperwasser (l)", "bmi": "BMI"}


def _gelernt_daten(g: GelernteZuordnung) -> dict:
    if g.art == GelernteZuordnung.Art.LABOR:
        ziel = g.parameter.name if g.parameter else g.ziel_text or g.ziel
    elif g.art == GelernteZuordnung.Art.BIA:
        ziel = BIA_NAMEN.get(g.ziel, g.ziel)
    elif g.art == GelernteZuordnung.Art.DIAGNOSE:
        ziel = f"{g.ziel_text} ({g.ziel})"
    else:
        ziel = f"Werte ab {round(100 * (g.spalte_x or 0))} % der Seitenbreite"
    return {"id": g.id, "art": g.art, "art_name": g.get_art_display(), "quelle": g.quelle,
            "quelle_name": g.quelle_anzeige or ("allgemein" if not g.quelle else g.quelle),
            "erkannt": g.erkannt_anzeige or g.erkannt, "ziel": ziel, "bestaetigt": g.bestaetigt,
            "sicher": g.bestaetigt >= lernen.auswertung.SCHWELLE, "gesperrt": g.gesperrt, "lesefehler": g.lesefehler,
            "zuletzt_am": g.zuletzt_am, "zuletzt_von": benutzername(g.zuletzt_von)}


class _Konflikt(serializers.ValidationError):
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, text):
        super().__init__({"fehler": text})


# ---------------------------------------------------------------- Zuordnen (eigene Funktion, weil umfangreich)
def _absaetze(text: str) -> str:
    """Erkannter Text → einfaches HTML (Absätze) für die Textfelder der Akte."""
    zeilen = [z.strip() for z in (text or "").replace("\t", "  ").splitlines()]
    return "".join(f"<p>{html.escape(z)}</p>" for z in zeilen if z)


def _dokument_anlegen(view, scan, patient, user, titel, typ, datum, notiz, original, originale_info, geschrieben):
    """Neues Dokument aus dem Scan (durchsuchbare PDF mit Text), auf Wunsch zusätzlich die Originale."""
    from patienten.api import speichere_datei
    from patienten.models import Dokument, DokumentText

    upload = ContentFile(view._pdf(scan), name=f"{titel}.pdf")
    meta = speichere_datei(patient, upload, "application/pdf")
    geschrieben.append(settings.EPM_DOKUMENTE / meta["datei"])
    dok = Dokument(patient=patient, typ=typ, titel=titel, datum=datum or scan.dokumentdatum, notiz=notiz,
                   herkunft=Dokument.Herkunft.SCAN, hochgeladen_von=user,
                   datum_quelle=Dokument.DatumQuelle.EINGABE, **meta)
    dok._history_user = user
    dok.save()
    DokumentText.objects.create(dokument=dok, text=scan.text, sicherheit=scan.sicherheit,
                                verfahren=", ".join(scan.verfahren or [])[:100],
                                erkannt_am=scan.erkannt_am or timezone.now())
    weitere = []
    if original:
        for nr, (pfad, info) in enumerate(zip(dienst.originale(scan), originale_info), 1):
            zusatz = f" {nr}" if len(originale_info) > 1 else ""
            upload = ContentFile(pfad.read_bytes(), name=info.get("name") or pfad.name)
            m = speichere_datei(patient, upload, info.get("mime"))
            geschrieben.append(settings.EPM_DOKUMENTE / m["datei"])
            o = Dokument(patient=patient, typ=typ, titel=f"{titel} (Original{zusatz})"[:200],
                         datum=dok.datum, herkunft=Dokument.Herkunft.SCAN, hochgeladen_von=user, **m)
            o._history_user = user
            o.save()
            weitere.append(o.id)
    return dok, weitere


def zuordnen(view: ScanViewSet, request, pk):
    """Scan → Dokument der Akte (durchsuchbare PDF mit erkanntem Text), dazu auf Wunsch:

    - ``original``: die hochgeladenen Dateien zusätzlich als Dokumente (nur PDF, JPG, PNG),
    - ``labor``: Laborbefund wie in der Maske (``abgenommen_am``, ``labor``, ``beurteilung``, ``werte``),
    - ``bia``: BIA-Messung wie in der Maske (mit ``gewicht_uebernehmen``),
    - ``diagnosen``: Liste wie unter Diagnosen (``bezeichnung``, ``icd_code``, ``kennzeichen``, ``seit``),
    - ``texte``: ``{"diagnose": "…", "therapie": "…", "empfehlung": "…"}`` – wird an das Textfeld angehängt.

    Alles in einer Transaktion: Ist etwas davon ungültig, entsteht nichts. Danach ist der Scan aus „Scans“ entfernt.

    Arbeitskopie eines Akte-Dokuments („Werte übernehmen“, F171): kein neues Dokument; Patient ist der des Dokuments,
    Laborbefund und BIA-Messung werden mit dem vorhandenen Dokument verknüpft."""
    from befunde.api import BiaMessungSerializer, LaborbefundSerializer
    from patienten.api import DiagnoseSerializer
    from patienten.models import DokumentText
    from stammdaten.models import Diagnosevorlage

    user = request.user
    if not user.hat_recht("eintraege_erfassen"):
        raise PermissionError("Dafür fehlt das Recht „Kontakte, Gewichte, Termine, Dokumente erfassen“.")
    scan = view._scan(pk, bearbeitbar=True)
    if scan.status != Scan.Status.FERTIG:
        return _fehler("Der Scan ist noch nicht erkannt.")
    d = request.data if isinstance(request.data, dict) else {}
    quelle = scan.quelldokument
    pid = str(d.get("patient") or "")
    patient = patienten_fuer(user).filter(pk=pid).first() if pid.isdigit() else None
    if quelle is not None:
        patient = patienten_fuer(user).filter(pk=quelle.patient_id).first()
        if patient is None:
            return _fehler("Die Akte des Dokuments ist nicht zugänglich.", feld="patient")
        if pid.isdigit() and int(pid) != quelle.patient_id:
            return _fehler("Werte aus einem Dokument gehen nur in dessen Akte.", feld="patient")
    if patient is None:
        return _fehler("Bitte den Patienten wählen.", feld="patient")
    if scan.ist_test and not patient.ist_test:
        return _fehler("Scans eines Testzugangs lassen sich nur Testpatienten zuordnen.", feld="patient")
    pruefe_schreibbereich(user, patient)
    patient.pruefe_bearbeitbar()
    fehler = {}
    titel = str(d.get("titel") or scan.titel).strip()[:200]
    if not titel:
        fehler["titel"] = "Bitte einen Titel angeben."
    typ = None
    if d.get("typ"):
        typ = Auswahlwert.objects.filter(pk=d.get("typ"), liste=Auswahlwert.Liste.DOKUMENTTYP).first()
        if typ is None:
            fehler["typ"] = "Ungültiger Dokumenttyp."
    datum = None
    if d.get("datum"):
        from datetime import date

        try:
            datum = date.fromisoformat(str(d["datum"]))
        except ValueError:
            fehler["datum"] = "Bitte ein Datum angeben."
        else:
            if datum > timezone.localdate():
                fehler["datum"] = "Das Datum liegt in der Zukunft."
    notiz = str(d.get("notiz") or "")[:2000]
    diagnosen = d.get("diagnosen") or []
    texte = {k: str(v) for k, v in (d.get("texte") or {}).items() if k in ("diagnose", "therapie", "empfehlung")
             and str(v).strip()}
    if (diagnosen or texte) and not user.hat_recht("akten_bearbeiten"):
        raise PermissionError("Dafür fehlt das Recht „Patienten anlegen, Diagnose, Therapie, Stammdaten ändern“.")
    originale_info = (scan.auswertung or {}).get("originale", [])
    original = bool(d.get("original"))
    erlaubt = {"application/pdf", "image/jpeg", "image/png"}
    if original and any(o.get("mime") not in erlaubt for o in originale_info):
        fehler["original"] = "Das Original kann nur bei PDF, JPG oder PNG zusätzlich abgelegt werden."
    if quelle is not None:
        fehler.pop("titel", None)
        fehler.pop("original", None)
        if not (d.get("labor") or d.get("bia") or diagnosen or texte):
            fehler["fehler"] = "Bitte mindestens einen Laborbefund, eine BIA-Messung, Diagnosen oder Texte wählen."
    if fehler:
        return Response(fehler, status=status.HTTP_400_BAD_REQUEST)

    geschrieben = []
    try:
        with transaction.atomic():
            if quelle is not None:
                dok, weitere = quelle, []
                titel = dok.titel
                if not DokumentText.objects.filter(dokument=dok).exists():
                    # die Erkennung der Arbeitskopie macht das Dokument auch durchsuchbar (die Datei bleibt)
                    DokumentText.objects.create(dokument=dok, text=scan.text, sicherheit=scan.sicherheit,
                                                verfahren=", ".join(scan.verfahren or [])[:100],
                                                erkannt_am=scan.erkannt_am or timezone.now())
            else:
                dok, weitere = _dokument_anlegen(view, scan, patient, user, titel, typ, datum, notiz, original,
                                                 originale_info, geschrieben)
            ergebnis = {"dokument": dok.id, "originale": weitere, "patient": patient.id}
            uebernommen = {}
            ctx = {"request": request}
            if d.get("labor"):
                daten = {**d["labor"], "patient": patient.id, "dokument": dok.id}
                s = LaborbefundSerializer(data=daten, context=ctx)
                if not s.is_valid():
                    raise _Ungueltig({"labor": s.errors})
                befund = s.save(erfasst_von=user)
                ergebnis["laborbefund"] = befund.id
                uebernommen["laborwerte"] = befund.werte.count()
            if d.get("bia"):
                daten = {**d["bia"], "patient": patient.id, "dokument": dok.id}
                s = BiaMessungSerializer(data=daten, context=ctx)
                if not s.is_valid():
                    raise _Ungueltig({"bia": s.errors})
                gewicht = s.validated_data.pop("gewicht_uebernehmen", True)
                messung = s.save(erfasst_von=user)
                if gewicht:
                    messung.gewicht_uebernehmen(user)
                ergebnis["bia"] = messung.id
                uebernommen["bia"] = 1
            if diagnosen:
                ids, fehlerliste = [], []
                for eintrag in diagnosen:
                    s = DiagnoseSerializer(data={**eintrag, "patient": patient.id}, context=ctx)
                    if not s.is_valid():
                        fehlerliste.append(s.errors)
                        continue
                    fehlerliste.append({})
                    diag = s.save(angelegt_von=user)
                    Diagnosevorlage.objects.get_or_create(icd_code=diag.icd_code, bezeichnung=diag.bezeichnung)
                    ids.append(diag.id)
                if any(fehlerliste):
                    raise _Ungueltig({"diagnosen": fehlerliste})
                ergebnis["diagnosen"] = ids
                uebernommen["diagnosen"] = len(ids)
            if texte:
                herkunft = f"Aus „{html.escape(titel)}“" + (f" vom {dok.datum:%d.%m.%Y}" if dok.datum else "") \
                    + (" (Dokument):" if quelle is not None else " (Scan):")
                for feld, text in texte.items():
                    alt = getattr(patient, feld) or ""
                    neu = f"{alt}<p><em>{herkunft}</em></p>{_absaetze(text)}"
                    setattr(patient, feld, bereinige_html(neu))
                patient._history_user = user
                patient.save()
                uebernommen["texte"] = len(texte)
            # Texterkennung lernt mit (F182): nur Bezeichnungen, keine Werte und keine Angaben zur Person
            gelernt = lernen.aus_zuordnung(scan, d, user, patient)
            if gelernt["gelernt"]:
                uebernommen["gelernt"] = gelernt["gelernt"]
            protokolliere(A.SCAN, request, objekt=str(scan),
                          aktion="werte_uebernommen" if quelle is not None else "zugeordnet", scan=scan.pk, dokument=dok.id,
                          akte=akte_text(patient), patient_id=patient.id, titel=titel, uebernommen=uebernommen,
                          seiten=scan.seiten.count())
            dienst.entfernen(scan)
    except BaseException:
        for pfad in geschrieben:
            pfad.unlink(missing_ok=True)
        raise
    return Response(ergebnis, status=status.HTTP_201_CREATED)


class _Ungueltig(serializers.ValidationError):
    pass
