"""
„Meine Akten“ (S05): Merkliste (Stern im Aktenkopf) und zuletzt geöffnete Akten – je Person, nur für sie sichtbar.

GET    /api/meine-akten/                      {merkliste: [...], zuletzt: [...]} mit Gewicht, Trend, nächstem Termin
POST   /api/meine-akten/merken/               {patient} → auf die Merkliste
DELETE /api/meine-akten/merken/<patient>/     von der Merkliste nehmen
POST   /api/meine-akten/geoeffnet/            {patient} → „zuletzt geöffnet“ (die Akte meldet sich beim Öffnen)

Lesen und Schreiben mit „Akten lesen“: Es sind Lesezeichen der Person, keine Einträge in der Akte. Angeboten werden nur
Akten im eigenen Bereich (Testzugänge: nur Testpatienten; eingeschränkte Akten nur während einer Einsicht).
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import nur_recht
from epm.api_basis import patienten_fuer

from .kennzahlen import kennzahlen
from .models import Merkeintrag

# so viele zuletzt geöffnete Akten werden je Person behalten (ältere fallen weg)
ZULETZT_ANZAHL = 20
MERKLISTE_MAX = 200


def _patient(request):
    try:
        pid = int(request.data.get("patient"))
    except (TypeError, ValueError):
        return None
    return patienten_fuer(request.user).filter(pk=pid).first()


def meine_akten(user) -> dict:
    bereich = patienten_fuer(user)
    eintraege = list(Merkeintrag.objects.filter(benutzer=user, patient__in=bereich).select_related("patient"))
    patienten = {e.patient_id: e.patient for e in eintraege}
    werte = kennzahlen(list(patienten.values()), liste=True)

    def zeile(e):
        p = e.patient
        k = werte.get(p.id, {})
        plan = k.get("plan") or {}
        return {"patient": p.id, "name": f"{p.nachname}, {p.vorname}", "nummer": p.nummer, "ist_test": p.ist_test,
                "ist_abgeschlossen": p.abgeschlossen_am is not None, "am": e.zeitpunkt,
                "gewicht": k.get("gewicht"), "trend": k.get("trend"), "naechster_termin": k.get("naechster_termin"),
                "plan_entwurf": bool(plan.get("entwurf"))}

    return {
        "merkliste": [zeile(e) for e in eintraege if e.art == Merkeintrag.Art.MERKLISTE],
        "zuletzt": [zeile(e) for e in eintraege if e.art == Merkeintrag.Art.GEOEFFNET][:ZULETZT_ANZAHL],
    }


class MeineAktenView(APIView):
    permission_classes = [nur_recht("akten_lesen")]

    def get(self, request):
        return Response(meine_akten(request.user))


class MerkenView(APIView):
    permission_classes = [nur_recht("akten_lesen")]

    def post(self, request, patient=None):  # die Akte steht im Inhalt; ``patient`` aus dem Pfad gilt nur für DELETE
        patient = _patient(request)
        if patient is None:
            return Response({"patient": "Akte nicht gefunden."}, status=status.HTTP_400_BAD_REQUEST)
        if Merkeintrag.objects.filter(benutzer=request.user, art=Merkeintrag.Art.MERKLISTE).count() >= MERKLISTE_MAX:
            return Response({"patient": f"Die Merkliste fasst höchstens {MERKLISTE_MAX} Akten."},
                            status=status.HTTP_400_BAD_REQUEST)
        Merkeintrag.objects.get_or_create(benutzer=request.user, patient=patient, art=Merkeintrag.Art.MERKLISTE)
        return Response(meine_akten(request.user), status=status.HTTP_201_CREATED)

    def delete(self, request, patient=None):
        if patient is None:  # DELETE ohne Akte (/api/meine-akten/merken/) – vorher ein Serverfehler
            return Response({"patient": "Akte nicht gefunden."}, status=status.HTTP_400_BAD_REQUEST)
        Merkeintrag.objects.filter(benutzer=request.user, patient_id=patient, art=Merkeintrag.Art.MERKLISTE).delete()
        return Response(meine_akten(request.user))


class GeoeffnetView(APIView):
    permission_classes = [nur_recht("akten_lesen")]

    def post(self, request):
        patient = _patient(request)
        if patient is None:
            return Response({"patient": "Akte nicht gefunden."}, status=status.HTTP_400_BAD_REQUEST)
        Merkeintrag.objects.update_or_create(benutzer=request.user, patient=patient, art=Merkeintrag.Art.GEOEFFNET,
                                             defaults={"zeitpunkt": timezone.now()})
        alte = (Merkeintrag.objects.filter(benutzer=request.user, art=Merkeintrag.Art.GEOEFFNET)
                .order_by("-zeitpunkt", "-id").values_list("id", flat=True)[ZULETZT_ANZAHL:])
        Merkeintrag.objects.filter(id__in=list(alte)).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
