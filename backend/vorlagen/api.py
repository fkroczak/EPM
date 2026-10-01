"""API der Dokumentvorlagen (F50): Aufbau lesen, Entwurf bearbeiten, veröffentlichen, Versionen, Vorschau als PDF.

GET    /api/vorlagen/                         beide Arten mit aktiver Version, Entwurf und Versionen
GET    /api/vorlagen/{art}/                   Bausteine, erlaubte Datenfelder, Tabellen, Versionen
GET    /api/vorlagen/{art}/entwurf/           Blöcke des Entwurfs (ohne Entwurf: der aktiven Version)
PUT    /api/vorlagen/{art}/entwurf/           {"bloecke": [...]} → Entwurf speichern (geprüft)
DELETE /api/vorlagen/{art}/entwurf/           Entwurf verwerfen
POST   /api/vorlagen/{art}/veroeffentlichen/  Entwurf wird neue aktive Version
GET    /api/vorlagen/{art}/versionen/{n}/     Blöcke einer Version
GET    /api/vorlagen/{art}/startvorlage/      Blöcke der mitgelieferten Startvorlage (als Grundlage für einen Entwurf)
POST   /api/vorlagen/{art}/vorschau/          {"patient": ID (Testpatient), "bloecke"?} → PDF mit Wasserzeichen ENTWURF
"""
from django.db import transaction
from django.http import Http404, HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import recht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import benutzername, patienten_fuer

from .bloecke import OPTIONEN, TYPEN, pruefe_bloecke
from .felder import FELDER, TABELLEN, Kontext
from .models import Dokumentvorlage
from .pdf import erzeuge_aus_vorlage

VorlagenRecht = recht("vorlagen_pflegen", lesen="vorlagen_pflegen")


def _art(art):
    if art not in Dokumentvorlage.Art.values:
        raise Http404("Unbekannte Vorlagenart.")
    return art


def _version(v: Dokumentvorlage | None):
    if v is None:
        return None
    return {"id": v.id, "version": v.version, "status": v.status, "notiz": v.notiz,
            "erstellt_am": v.erstellt_am, "geaendert_am": v.geaendert_am,
            "geaendert_von": benutzername(v.geaendert_von or v.erstellt_von),
            "veroeffentlicht_am": v.veroeffentlicht_am, "veroeffentlicht_von": benutzername(v.veroeffentlicht_von)}


def _uebersicht(art):
    aktiv = Dokumentvorlage.aktive(art)
    versionen = Dokumentvorlage.objects.filter(art=art).exclude(status=Dokumentvorlage.Status.ENTWURF) \
        .select_related("veroeffentlicht_von").order_by("-version")
    return {"art": art, "name": Dokumentvorlage.Art(art).label, "aktiv": _version(aktiv),
            "entwurf": _version(Dokumentvorlage.entwurf_von(art)), "versionen": [_version(v) for v in versionen]}


class VorlagenView(APIView):
    permission_classes = [VorlagenRecht]

    def get(self, request):
        return Response([_uebersicht(a) for a in Dokumentvorlage.Art.values])


class VorlageView(APIView):
    permission_classes = [VorlagenRecht]

    def get(self, request, art):
        art = _art(art)
        return Response({
            **_uebersicht(art),
            "bausteine": [{"typ": k, "name": v} for k, v in TYPEN.items()],
            "felder": [{"name": k, "beschreibung": f.beschreibung, "html": f.html} for k, f in FELDER[art].items()],
            "tabellen": [{"quelle": k, "name": v[0], "spalten": v[1]} for k, v in TABELLEN[art].items()],
            "optionen": {k: sorted(v) if isinstance(v, set) else "bool" for k, v in OPTIONEN.items()},
        })


class EntwurfView(APIView):
    permission_classes = [VorlagenRecht]

    def get(self, request, art):
        art = _art(art)
        entwurf = Dokumentvorlage.entwurf_von(art)
        quelle = entwurf or Dokumentvorlage.aktive(art)
        return Response({"ist_entwurf": entwurf is not None, "grundlage": quelle.version, **_version(quelle),
                         "bloecke": quelle.bloecke})

    @transaction.atomic
    def put(self, request, art):
        art = _art(art)
        bloecke = request.data.get("bloecke")
        fehler = pruefe_bloecke(art, bloecke)
        if fehler:
            return Response({"bloecke": fehler}, status=status.HTTP_400_BAD_REQUEST)
        entwurf = Dokumentvorlage.objects.select_for_update().filter(art=art, status=Dokumentvorlage.Status.ENTWURF).first()
        neu = entwurf is None
        if neu:
            entwurf = Dokumentvorlage(art=art, erstellt_von=request.user)
        entwurf.bloecke = bloecke
        entwurf.geaendert_von = request.user
        entwurf._history_user = request.user
        entwurf.save()
        if neu:
            protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {entwurf.get_art_display()}",
                          aktion="Entwurf angelegt")
        return Response({"ist_entwurf": True, **_version(entwurf), "bloecke": entwurf.bloecke})

    def delete(self, request, art):
        art = _art(art)
        entwurf = Dokumentvorlage.entwurf_von(art)
        if entwurf is None:
            return Response({"fehler": "Es gibt keinen Entwurf."}, status=status.HTTP_404_NOT_FOUND)
        entwurf._history_user = request.user
        entwurf.delete()
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {Dokumentvorlage.Art(art).label}",
                      aktion="Entwurf verworfen")
        return Response(status=status.HTTP_204_NO_CONTENT)


class VeroeffentlichenView(APIView):
    permission_classes = [VorlagenRecht]

    def post(self, request, art):
        art = _art(art)
        entwurf = Dokumentvorlage.entwurf_von(art)
        if entwurf is None:
            return Response({"fehler": "Es gibt keinen Entwurf zum Veröffentlichen."}, status=status.HTTP_400_BAD_REQUEST)
        entwurf._history_user = request.user
        entwurf.veroeffentlichen(request.user)
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {entwurf.get_art_display()}",
                      aktion=f"Version {entwurf.version} veröffentlicht")
        return Response(_uebersicht(art))


class VersionView(APIView):
    permission_classes = [VorlagenRecht]

    def get(self, request, art, version):
        art = _art(art)
        v = Dokumentvorlage.objects.filter(art=art, version=version).first()
        if v is None:
            raise Http404("Version nicht gefunden.")
        return Response({**_version(v), "bloecke": v.bloecke})


class StartvorlageView(APIView):
    """Mitgelieferte Startvorlage, z. B. wenn sie nach einem Update neu gestaltet ist und schon eine Version aktiv ist."""
    permission_classes = [VorlagenRecht]

    def get(self, request, art):
        from .bloecke import STARTVORLAGEN

        return Response({"bloecke": STARTVORLAGEN[_art(art)]})


def pdf_antwort(pdf: bytes, dateiname: str, inline=True) -> HttpResponse:
    from urllib.parse import quote

    antwort = HttpResponse(pdf, content_type="application/pdf")
    antwort["Content-Disposition"] = f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(dateiname)}"
    antwort["Cache-Control"] = "private, no-store"
    antwort["X-Content-Type-Options"] = "nosniff"
    return antwort


class VorschauView(APIView):
    """Vorschau mit einem Testpatienten (Entwurf 18) – echte Akten erscheinen nie in der Vorschau."""

    permission_classes = [VorlagenRecht]

    def post(self, request, art):
        art = _art(art)
        patient = patienten_fuer(request.user).filter(pk=request.data.get("patient"), ist_test=True).first()
        if patient is None:
            return Response({"patient": "Bitte einen Testpatienten wählen."}, status=status.HTTP_400_BAD_REQUEST)
        bloecke = request.data.get("bloecke")
        if bloecke is None:
            quelle = Dokumentvorlage.entwurf_von(art) or Dokumentvorlage.aktive(art)
            bloecke = quelle.bloecke
        fehler = pruefe_bloecke(art, bloecke)
        if fehler:
            return Response({"bloecke": fehler}, status=status.HTTP_400_BAD_REQUEST)
        from infusionen.models import Infusionsplan

        plan = Infusionsplan.objects.filter(patient=patient, status=Infusionsplan.Status.AKTUELL).first()
        if plan is None and art == Dokumentvorlage.Art.INFUSIONSPLAN:
            plan = Infusionsplan.objects.filter(patient=patient).order_by("-gueltig_ab", "-id").first()
        if art == Dokumentvorlage.Art.INFUSIONSPLAN and plan is None:
            return Response({"patient": "Dieser Testpatient hat noch keinen Infusionsplan."},
                            status=status.HTTP_400_BAD_REQUEST)
        pdf, _ = erzeuge_aus_vorlage(art, Kontext(patient=patient, plan=plan), bloecke=bloecke, wasserzeichen="ENTWURF",
                                     titel=f"Vorschau {Dokumentvorlage.Art(art).label}")
        return pdf_antwort(pdf, f"Vorschau-{art}.pdf")
