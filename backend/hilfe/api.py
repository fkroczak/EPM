"""
Hilfe (S15): mitgelieferte Abschnitte je nach Rechten der Person, dazu eigene Ergänzungen der Stiftung.

GET  /api/hilfe/                                  {version, darf_ergaenzen, gruppen: [{id, titel, abschnitte: [...]}]}
PUT  /api/hilfe/<abschnitt>/ergaenzung/           {text} – Ergänzung schreiben (leer = entfernen); Recht „Vorlagen pflegen“
GET  /api/hilfe/<abschnitt>/ergaenzung/versionen/ frühere Fassungen der Ergänzung (neueste zuerst)

Ergänzungen sieht, wer den Abschnitt sieht. Schreiben steht mit Abschnitt und Umfang im Audit-Log (Art „Vorlage“).
"""
import re

from django.conf import settings
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import Angemeldet, recht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import RichText, benutzername

from .inhalt import ABSCHNITTE, GRUPPEN
from .models import Hilfeergaenzung

ABSCHNITT = {a["id"]: a for a in ABSCHNITTE}


def sichtbar(user, abschnitt, rechte=None) -> bool:
    """``rechte``: schon ermittelte Rechte der Person (``rechte_fuer``) – spart je Abschnitt eine Abfrage."""
    if rechte is not None:
        return not abschnitt["rechte"] or any(r in rechte for r in abschnitt["rechte"])
    return not abschnitt["rechte"] or any(user.hat_recht(r) for r in abschnitt["rechte"])


def _fassungen(abschnitt_id: str) -> list:
    """Fassungen der Ergänzung, neueste zuerst; aufeinanderfolgende gleiche Texte zählen einmal."""
    fassungen, vorher = [], None
    for h in (Hilfeergaenzung.history.filter(abschnitt=abschnitt_id).order_by("history_date", "history_id")
              .select_related("history_user")):
        if h.text != vorher:
            fassungen.append({"version": len(fassungen) + 1, "zeitpunkt": h.history_date,
                              "person": benutzername(h.history_user), "text": h.text})
        vorher = h.text
    return list(reversed(fassungen))


def _ergaenzung(abschnitt_id: str, ergaenzungen: dict):
    e = ergaenzungen.get(abschnitt_id)
    if e is None:
        return None
    fassungen = _fassungen(abschnitt_id)
    if not e.text and not fassungen:
        return None
    letzte = fassungen[0] if fassungen else None
    return {"text": e.text, "geaendert_am": letzte["zeitpunkt"] if letzte else None,
            "geaendert_von": letzte["person"] if letzte else None, "versionen": len(fassungen)}


class HilfeView(APIView):
    permission_classes = [Angemeldet]

    def get(self, request):
        from accounts.rechte import rechte_fuer

        user = request.user
        rechte = rechte_fuer(user)  # einmal je Anfrage statt je Abschnitt
        ergaenzungen = {e.abschnitt: e for e in Hilfeergaenzung.objects.all()}
        gruppen = []
        for gid, titel in GRUPPEN:
            abschnitte = [{"id": a["id"], "titel": a["titel"], "seiten": a["seiten"], "html": a["html"].strip(),
                           "ergaenzung": _ergaenzung(a["id"], ergaenzungen)}
                          for a in ABSCHNITTE if a["gruppe"] == gid and sichtbar(user, a, rechte)]
            if abschnitte:
                gruppen.append({"id": gid, "titel": titel, "abschnitte": abschnitte})
        return Response({"version": settings.EPM_VERSION or None, "darf_ergaenzen": "vorlagen_pflegen" in rechte,
                         "gruppen": gruppen})


class ErgaenzungSerializer(serializers.Serializer):
    text = RichText(max_length=20000)


class ErgaenzungView(APIView):
    permission_classes = [recht("vorlagen_pflegen", lesen=None)]

    def put(self, request, abschnitt):
        a = ABSCHNITT.get(abschnitt)
        if a is None or not sichtbar(request.user, a):
            return Response({"fehler": "Diesen Abschnitt gibt es nicht."}, status=status.HTTP_404_NOT_FOUND)
        s = ErgaenzungSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        text = s.validated_data["text"]
        leer = not re.sub(r"<[^>]*>|&nbsp;|\s", "", text)
        with transaction.atomic():
            e = Hilfeergaenzung.objects.select_for_update().filter(abschnitt=abschnitt).first()
            vorher = e.text if e else ""
            neu = "" if leer else text
            if e is None and not neu:
                return Response({"ergaenzung": None})
            if e is not None and e.text == neu:
                return Response({"ergaenzung": _ergaenzung(abschnitt, {abschnitt: e})})
            e = e or Hilfeergaenzung(abschnitt=abschnitt)
            e.text = neu
            e._history_user = request.user
            e.save()
        aktion = "Ergänzung entfernt" if not neu else ("Ergänzung geändert" if vorher else "Ergänzung angelegt")
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Hilfe › {a['titel']}", aktion=aktion,
                      abschnitt=abschnitt, zeichen=len(neu))
        return Response({"ergaenzung": _ergaenzung(abschnitt, {abschnitt: e})})


class VersionenView(APIView):
    permission_classes = [Angemeldet]

    def get(self, request, abschnitt):
        a = ABSCHNITT.get(abschnitt)
        if a is None or not sichtbar(request.user, a):
            return Response({"fehler": "Diesen Abschnitt gibt es nicht."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_fassungen(abschnitt))
