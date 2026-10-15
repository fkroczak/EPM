"""API der Dokumentvorlagen (F50): Aufbau lesen, Entwurf bearbeiten, veröffentlichen, Versionen, Vorschau als PDF.

GET    /api/vorlagen/                         beide Arten mit aktiver Version, Entwurf und Versionen
GET    /api/vorlagen/{art}/                   Bausteine, erlaubte Datenfelder, Tabellen, Versionen
GET    /api/vorlagen/{art}/entwurf/           Blöcke des Entwurfs (ohne Entwurf: der aktiven Version)
PUT    /api/vorlagen/{art}/entwurf/           {"bloecke": [...]} → Entwurf speichern (geprüft)
DELETE /api/vorlagen/{art}/entwurf/           Entwurf verwerfen
POST   /api/vorlagen/{art}/veroeffentlichen/  Entwurf wird neue aktive Version
GET    /api/vorlagen/{art}/versionen/{n}/     Blöcke einer Version
GET    /api/vorlagen/{art}/startvorlage/      Blöcke der mitgelieferten Startvorlage (als Grundlage für einen Entwurf)
POST   /api/vorlagen/{art}/versionen/{n}/wiederherstellen/  frühere Fassung als Entwurf übernehmen (F180)
POST   /api/vorlagen/{art}/duplizieren/       {"name", "beschreibung"?, "mit_termin"?} → eigene Vorlage als Kopie (F180)
POST   /api/vorlagen/{art}/vorschau/          {"patient": ID (Testpatient), "bloecke"?, "ausrichtung"?} → PDF mit
                                              Wasserzeichen ENTWURF; mit "ausgabe": "email" → {"betreff", "text"}
POST   /api/vorlagen/{art}/firma/             {"eigene": true|false} → eigene Vorlage der aktiven Firma anlegen (Kopie
                                              der gemeinsamen) bzw. ablegen (wieder die gemeinsame nutzen)

Vorlagen je Firma (11.10.2026): Alle Aufrufe gelten für die Vorlage, die in der aktiven Firma gilt – ihre eigene,
wenn sie eine hat, sonst die gemeinsame (``Dokumentvorlage.zustaendig``). Der Entwurf speichert auch das Seitenformat
(``ausrichtung`` hoch/quer, 13.10.2026).

Anlagen für die E-Mails der Schreiben (F174):
GET    /api/anlagen/                          aktive Anlagen (alle mit ?alle=1, nur mit „Vorlagen pflegen“)
POST   /api/anlagen/                          multipart: name, beschreibung?, datei (PDF, höchstens 20 MB)
PATCH  /api/anlagen/{id}/                     name, beschreibung, aktiv, reihenfolge
GET    /api/anlagen/{id}/datei/               die PDF
"""
import re

from django.db import transaction
from django.http import Http404, HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import recht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import benutzername, patienten_fuer
from epm.firma import aktive_firma

from .bloecke import MIT_EMAIL, OPTIONEN, QUERFORMAT, TYPEN, pruefe_bloecke
from .felder import FELDER, TABELLEN, Kontext, ist_eigen
from .models import NUR_FIRMA, Dokumentvorlage, EigenesSchreiben, art_name, art_sichtbar, gibt_es_art
from .pdf import erzeuge_aus_vorlage
from .portal import art_info, feld_info

VorlagenRecht = recht("vorlagen_pflegen", lesen="vorlagen_pflegen")


def _art(art):
    if not gibt_es_art(art) or not art_sichtbar(art):
        raise Http404("Unbekannte Vorlagenart.")
    return art


def _version(v: Dokumentvorlage | None):
    if v is None:
        return None
    return {"id": v.id, "version": v.version, "status": v.status, "notiz": v.notiz, "ausrichtung": v.ausrichtung,
            "firma": v.firma.kuerzel if v.firma_id else None,
            "erstellt_am": v.erstellt_am, "geaendert_am": v.geaendert_am,
            "geaendert_von": benutzername(v.geaendert_von or v.erstellt_von),
            "veroeffentlicht_am": v.veroeffentlicht_am, "veroeffentlicht_von": benutzername(v.veroeffentlicht_von)}


def _ausrichtung(daten, sonst: str) -> str:
    """Seitenformat aus der Anfrage (hoch/quer), ohne Angabe wie bisher; ungültig → ValueError."""
    wert = daten.get("ausrichtung", sonst)
    if wert not in Dokumentvorlage.Ausrichtung.values:
        raise ValueError("Bitte „hoch“ oder „quer“.")
    return wert


def _firma_info(art, ziel) -> dict:
    """Vorlagen je Firma (11.10.2026): nutzt die aktive Firma die gemeinsame Vorlage oder ihre eigene?"""
    from epm.firma import aktive_firma
    from stammdaten.models import Firma

    firma = aktive_firma()
    mehrere = Firma.objects.filter(aktiv=True).count() > 1
    return {"aktiv": firma.kuerzel if firma else None, "name": firma.kurzname if firma else None,
            "mehrere": mehrere, "eigene": ziel is not None, "gebunden": art in NUR_FIRMA,
            # eigene Vorlage anlegen/ablegen: nur mit mehreren Firmen, nicht bei fest zugeordneten oder eigenen Schreiben
            "moeglich": mehrere and firma is not None and art not in NUR_FIRMA and not ist_eigen(art)}


def _uebersicht(art):
    aktiv = Dokumentvorlage.aktive(art)
    ziel = Dokumentvorlage.zustaendig(art)
    versionen = Dokumentvorlage.objects.filter(art=art, firma=ziel).exclude(status=Dokumentvorlage.Status.ENTWURF) \
        .select_related("veroeffentlicht_von").order_by("-version")
    from stammdaten.models import Einstellungen

    from .fassung1 import import_durchgefuehrt

    eigen = EigenesSchreiben.objects.filter(schluessel=art).first()
    nur_fassung_1 = not import_durchgefuehrt()
    return {"art": art, "name": art_name(art), "aktiv": _version(aktiv),
            # eigenes Schreiben (F176): Beschreibung, Termin, aktiv
            "eigen": {"beschreibung": eigen.beschreibung, "mit_termin": eigen.mit_termin, "aktiv": eigen.aktiv}
            if eigen else None,
            # Vorlagen-Portal (F180): wofür, wo in der Praxis benutzt, Gruppe der Übersicht
            **art_info(art, eigen.beschreibung if eigen else "", eigen.gruppe if eigen else None),
            "entwurf": _version(Dokumentvorlage.entwurf_von(art)), "versionen": [_version(v) for v in versionen],
            # vor dem Import der Altdaten ersetzt Freigeben die Fassung 1 (vorlagen.fassung1)
            "nur_fassung_1": nur_fassung_1,
            "naechste_fassung": 1 if nur_fassung_1 else max([v.version for v in versionen] or [0]) + 1,
            "firma": _firma_info(art, ziel),
            # Seitenformat (13.10.2026): das der aktiven Fassung; der Editor bietet Querformat bei breiten Tabellen an
            "ausrichtung": aktiv.ausrichtung, "querformat_moeglich": art in QUERFORMAT,
            # Vordrucke: Wasserzeichen „ENTWURF“ (Startvorlage ungeprüft) und ob es manuell abgeschaltet ist (U17)
            "entwurfsmodus": {"moeglich": art in Dokumentvorlage.VORDRUCKE and aktiv.veroeffentlicht_von_id is None,
                              "aktiv": aktiv.im_entwurfsmodus,
                              "aus": aktiv.entwurfsmodus_schluessel in (Einstellungen.aktuell().vordrucke_ohne_entwurf or [])}}


class VorlagenView(APIView):
    permission_classes = [VorlagenRecht]

    def get(self, request):
        arten = [*(a for a in Dokumentvorlage.Art.values if art_sichtbar(a)),
                 *EigenesSchreiben.sichtbare().values_list("schluessel", flat=True)]
        return Response([_uebersicht(a) for a in arten])

    @transaction.atomic
    def post(self, request):
        """Eigenes Schreiben anlegen (F176): ``{"name", "beschreibung"?, "mit_termin"?}``. Die Startvorlage (Brief an
        den Patienten mit E-Mail) wird gleich als Version 1 aktiv und kann danach bearbeitet werden."""
        e = EigenesSchreiben(erstellt_von=request.user, firma=aktive_firma())
        fehler = _eigen_setzen(e, request.data, neu=True)
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        e._history_user = request.user
        e.save()
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {e.name}", aktion="eigenes Schreiben angelegt")
        return Response(_uebersicht(e.schluessel), status=status.HTTP_201_CREATED)


def _eigen_setzen(e, d, neu=False) -> dict:
    fehler = {}
    if neu or "name" in d:
        name = d.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            fehler["name"] = "Bitte einen Namen angeben (höchstens 100 Zeichen)."
        elif (EigenesSchreiben.objects.filter(name__iexact=name.strip()).exclude(pk=e.pk).exists()
              or name.strip().lower() in {x.label.lower() for x in Dokumentvorlage.Art}):
            fehler["name"] = "Diesen Namen gibt es schon."
        else:
            e.name = name.strip()
    if "beschreibung" in d:
        if not isinstance(d["beschreibung"], str) or len(d["beschreibung"]) > 300:
            fehler["beschreibung"] = "Höchstens 300 Zeichen."
        else:
            e.beschreibung = d["beschreibung"].strip()
    for feld in ("mit_termin", "aktiv"):
        if feld in d:
            if not isinstance(d[feld], bool):
                fehler[feld] = "Bitte true oder false."
            else:
                setattr(e, feld, d[feld])
    return fehler


class EigenesSchreibenView(APIView):
    """``PATCH /api/vorlagen/{art}/eigen/`` – Name, Beschreibung, Termin wählen, aktiv (F176)."""

    permission_classes = [VorlagenRecht]

    def patch(self, request, art):
        e = EigenesSchreiben.sichtbare().filter(schluessel=art).first()
        if e is None:
            raise Http404("Kein eigenes Schreiben.")
        fehler = _eigen_setzen(e, request.data)
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        e._history_user = request.user
        e.save()
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {e.name}",
                      aktion="eigenes Schreiben geändert")
        return Response(_uebersicht(art))


class SchreibenListeView(APIView):
    """``GET /api/schreiben/`` – die Schreiben, die sich aus der Akte erzeugen lassen (F172, F176)."""

    permission_classes = [recht("eintraege_erfassen", lesen="eintraege_erfassen")]

    def get(self, request):
        from .schreiben import AUS_DER_AKTE

        liste = [{"art": a, "name": art_name(a), "beschreibung": v["beschreibung"], "termin": v["termin"], "eigen": False}
                 for a, v in AUS_DER_AKTE.items()]
        from .portal import GRUPPEN

        liste += [{"art": e.schluessel, "name": e.name, "beschreibung": e.beschreibung, "termin": e.mit_termin,
                   "eigen": True, "gruppe": e.gruppe, "gruppe_name": GRUPPEN.get(e.gruppe, GRUPPEN["eigen"])}
                  for e in EigenesSchreiben.sichtbare().filter(aktiv=True).order_by("gruppe", "name")]
        return Response(liste)


class VorlageView(APIView):
    permission_classes = [VorlagenRecht]

    def get(self, request, art):
        art = _art(art)
        return Response({
            **_uebersicht(art),
            "bausteine": [{"typ": k, "name": v} for k, v in TYPEN.items() if k != "email" or art in MIT_EMAIL],
            "felder": [{"name": k, "beschreibung": f.beschreibung, "html": f.html, **feld_info(k, f.beschreibung)}
                       for k, f in FELDER[art].items()],
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
        ziel = Dokumentvorlage.zustaendig(art)
        entwurf = Dokumentvorlage.objects.select_for_update().filter(art=art, firma=ziel,
                                                                     status=Dokumentvorlage.Status.ENTWURF).first()
        neu = entwurf is None
        if neu:
            entwurf = Dokumentvorlage(art=art, firma=ziel, erstellt_von=request.user,
                                      ausrichtung=Dokumentvorlage.aktive(art).ausrichtung)
        try:
            entwurf.ausrichtung = _ausrichtung(request.data, entwurf.ausrichtung)
        except ValueError as e:
            return Response({"ausrichtung": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        entwurf.bloecke = bloecke
        entwurf.geaendert_von = request.user
        entwurf._history_user = request.user
        entwurf.save()
        if neu:
            protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {entwurf}",
                          aktion="Entwurf angelegt")
        return Response({"ist_entwurf": True, **_version(entwurf), "bloecke": entwurf.bloecke})

    def delete(self, request, art):
        art = _art(art)
        entwurf = Dokumentvorlage.entwurf_von(art)
        if entwurf is None:
            return Response({"fehler": "Es gibt keinen Entwurf."}, status=status.HTTP_404_NOT_FOUND)
        entwurf._history_user = request.user
        entwurf.delete()
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {art_name(art)}",
                      aktion="Entwurf verworfen")
        return Response(status=status.HTTP_204_NO_CONTENT)


class EntwurfsmodusView(APIView):
    """Wasserzeichen „ENTWURF“ auf einem Vordruck manuell ab- oder wieder einschalten (Festlegung 03.10.2026, U17):
    ``POST {"aus": true}``. Gilt, solange die mitgelieferte Startvorlage aktiv ist; nach dem Veröffentlichen einer
    eigenen Version entfällt das Wasserzeichen ohnehin. Steht im Audit-Log und in der Historie der Einstellungen."""

    permission_classes = [VorlagenRecht]

    def post(self, request, art):
        from stammdaten.models import Einstellungen

        art = _art(art)
        if art not in Dokumentvorlage.VORDRUCKE:
            return Response({"fehler": "Den Entwurfsmodus gibt es nur bei den Vordrucken zum Datenschutz."},
                            status=status.HTTP_400_BAD_REQUEST)
        aus = request.data.get("aus")
        if not isinstance(aus, bool):
            return Response({"aus": "Bitte true oder false."}, status=status.HTTP_400_BAD_REQUEST)
        e = Einstellungen.aktuell()
        schluessel = Dokumentvorlage.aktive(art).entwurfsmodus_schluessel  # je Firma, wenn sie eine eigene hat
        liste = [a for a in (e.vordrucke_ohne_entwurf or []) if a != schluessel] + ([schluessel] if aus else [])
        if sorted(liste) != sorted(e.vordrucke_ohne_entwurf or []):
            e.vordrucke_ohne_entwurf = sorted(liste)
            e._history_user = request.user
            e.save()
            protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {art_name(art)}",
                          aktion="Wasserzeichen „ENTWURF“ ausgeschaltet" if aus else "Wasserzeichen „ENTWURF“ eingeschaltet")
        return Response(_uebersicht(art))


class VeroeffentlichenView(APIView):
    permission_classes = [VorlagenRecht]

    def post(self, request, art):
        art = _art(art)
        entwurf = Dokumentvorlage.entwurf_von(art)
        if entwurf is None:
            return Response({"fehler": "Es gibt keinen Entwurf zum Veröffentlichen."}, status=status.HTTP_400_BAD_REQUEST)
        entwurf._history_user = request.user
        entwurf.veroeffentlichen(request.user)
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {entwurf}",
                      aktion=f"Version {entwurf.version} veröffentlicht")
        return Response(_uebersicht(art))


class VersionView(APIView):
    permission_classes = [VorlagenRecht]

    def get(self, request, art, version):
        art = _art(art)
        v = Dokumentvorlage.objects.filter(art=art, firma=Dokumentvorlage.zustaendig(art), version=version).first()
        if v is None:
            raise Http404("Version nicht gefunden.")
        return Response({**_version(v), "bloecke": v.bloecke})


class StartvorlageView(APIView):
    """Mitgelieferte Startvorlage, z. B. wenn sie nach einem Update neu gestaltet ist und schon eine Version aktiv ist."""
    permission_classes = [VorlagenRecht]

    def get(self, request, art):
        from .bloecke import STARTVORLAGEN

        return Response({"bloecke": STARTVORLAGEN[_art(art)]})


class WiederherstellenView(APIView):
    """Frühere Fassung wiederherstellen (F180): Ihre Blöcke werden der Entwurf (ein bestehender Entwurf wird ersetzt).
    In Gebrauch ist sie erst nach dem Freigeben – wie jede andere Änderung; die Fassungen selbst bleiben unverändert."""

    permission_classes = [VorlagenRecht]

    @transaction.atomic
    def post(self, request, art, version):
        art = _art(art)
        ziel = Dokumentvorlage.zustaendig(art)
        v = Dokumentvorlage.objects.filter(art=art, firma=ziel, version=version).first()
        if v is None:
            raise Http404("Fassung nicht gefunden.")
        fehler = pruefe_bloecke(art, v.bloecke)
        if fehler:
            # z. B. ein Datenfeld, das es nach einem Update nicht mehr gibt
            return Response({"bloecke": fehler}, status=status.HTTP_400_BAD_REQUEST)
        entwurf = Dokumentvorlage.objects.select_for_update().filter(art=art, firma=ziel,
                                                                     status=Dokumentvorlage.Status.ENTWURF).first()
        if entwurf is None:
            entwurf = Dokumentvorlage(art=art, firma=ziel, erstellt_von=request.user)
        entwurf.bloecke = v.bloecke
        entwurf.ausrichtung = v.ausrichtung
        entwurf.notiz = f"wiederhergestellt aus Fassung {v.version}"
        entwurf.geaendert_von = request.user
        entwurf._history_user = request.user
        entwurf.save()
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {art_name(art)}",
                      aktion=f"Fassung {v.version} als Entwurf wiederhergestellt")
        return Response({"ist_entwurf": True, **_version(entwurf), "bloecke": entwurf.bloecke})


class DuplizierenView(APIView):
    """Vorlage als Grundlage für eine eigene Vorlage kopieren (F180): ``{"name", "beschreibung"?, "mit_termin"?}``.
    Kopiert wird die Fassung in Gebrauch; die Kopie ist sofort als Fassung 1 in Gebrauch (wie „+ Neue Vorlage“, F176).
    Geht nur, wenn alle Datenfelder und Tabellen auch in eigenen Schreiben erlaubt sind (also bei den Schreiben)."""

    permission_classes = [VorlagenRecht]

    @transaction.atomic
    def post(self, request, art):
        from django.utils import timezone

        art = _art(art)
        quelle = Dokumentvorlage.aktive(art)
        e = EigenesSchreiben(erstellt_von=request.user, firma=aktive_firma())
        daten = {"beschreibung": "", "mit_termin": "Termin.Datum" in str(quelle.bloecke), **request.data}
        fehler = _eigen_setzen(e, daten, neu=True)
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        pruefung = pruefe_bloecke("eigen-kopie", quelle.bloecke)
        if pruefung:
            return Response({"fehler": f"„{art_name(art)}“ lässt sich nicht als eigene Vorlage kopieren: Sie enthält "
                                       "Angaben, die es in eigenen Schreiben nicht gibt.", "bloecke": pruefung},
                            status=status.HTTP_400_BAD_REQUEST)
        e._history_user = request.user
        e.save()
        Dokumentvorlage.objects.create(art=e.schluessel, version=1, status=Dokumentvorlage.Status.AKTIV,
                                       bloecke=quelle.bloecke, ausrichtung=quelle.ausrichtung, erstellt_von=request.user,
                                       notiz=f"Kopie von „{art_name(art)}“, Fassung {quelle.version}",
                                       veroeffentlicht_am=timezone.now(), veroeffentlicht_von=request.user)
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {e.name}",
                      aktion=f"als Kopie von „{art_name(art)}“ (Fassung {quelle.version}) angelegt")
        return Response(_uebersicht(e.schluessel), status=status.HTTP_201_CREATED)


class FirmaVorlageView(APIView):
    """Eigene Vorlage der aktiven Firma (Festlegung „Gemischt“, 11.10.2026): ``POST {"eigene": true}`` legt sie als
    Kopie der gemeinsamen aktiven Fassung an (sofort in Gebrauch, Fassungen zählen je Firma); ``{"eigene": false}``
    legt sie ab (aktive Fassung abgelöst, Entwurf verworfen) – es gilt wieder die gemeinsame Vorlage."""

    permission_classes = [VorlagenRecht]

    def post(self, request, art):
        from django.core.exceptions import ValidationError

        from epm.firma import aktive_firma
        from stammdaten.models import Einstellungen

        art = _art(art)
        firma = aktive_firma()
        eigene = request.data.get("eigene")
        if not isinstance(eigene, bool):
            return Response({"eigene": "Bitte true oder false."}, status=status.HTTP_400_BAD_REQUEST)
        if firma is None or art in NUR_FIRMA or ist_eigen(art):
            return Response({"fehler": "Für diese Vorlage gibt es keine Vorlage je Firma."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            if eigene:
                v = Dokumentvorlage.eigene_anlegen(art, firma, request.user)
                aktion = f"eigene Vorlage für {firma.kurzname} angelegt (Fassung {v.version})"
            else:
                anzahl = Dokumentvorlage.eigene_entfernen(art, firma)
                aktion = f"eigene Vorlage für {firma.kurzname} abgelegt ({anzahl} Fassung abgelöst)"
                e = Einstellungen.aktuell()
                schluessel = f"{art}@{firma.kuerzel}"
                if schluessel in (e.vordrucke_ohne_entwurf or []):
                    e.vordrucke_ohne_entwurf = [a for a in e.vordrucke_ohne_entwurf if a != schluessel]
                    e._history_user = request.user
                    e.save()
        except ValidationError as e:
            return Response({"fehler": " ".join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {art_name(art)}", aktion=aktion)
        return Response(_uebersicht(art))


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
        quelle = Dokumentvorlage.entwurf_von(art) or Dokumentvorlage.aktive(art)
        if bloecke is None:
            bloecke = quelle.bloecke
        fehler = pruefe_bloecke(art, bloecke)
        if fehler:
            return Response({"bloecke": fehler}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ausrichtung = _ausrichtung(request.data, quelle.ausrichtung)
        except ValueError as e:
            return Response({"ausrichtung": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        from infusionen.models import Infusionsplan

        plan = Infusionsplan.objects.filter(patient=patient, status=Infusionsplan.Status.AKTUELL).first()
        if plan is None and art == Dokumentvorlage.Art.INFUSIONSPLAN:
            plan = Infusionsplan.objects.filter(patient=patient).order_by("-gueltig_ab", "-id").first()
        if art == Dokumentvorlage.Art.INFUSIONSPLAN and plan is None:
            return Response({"patient": "Dieser Testpatient hat noch keinen Infusionsplan."},
                            status=status.HTTP_400_BAD_REQUEST)
        kontext = Kontext(patient=patient, plan=plan, benutzer=request.user)
        if art in VORSCHAU_SCHREIBEN:
            kontext = VORSCHAU_SCHREIBEN[art](patient, request.user)
        elif art not in Dokumentvorlage.Art.values:
            kontext = _vorschau_termin(patient, request.user)  # eigenes Schreiben (F176), ggf. mit Termin
        elif art == Dokumentvorlage.Art.SPRECHSTUNDE:
            # Vorschau mit dem aktuellsten Stand des Testpatienten (F116)
            from .listen import sprechstunde_kontext

            kontext = sprechstunde_kontext(patient)
        elif art == Dokumentvorlage.Art.BERICHT:
            from berichte.models import Bericht

            bericht = Bericht.objects.filter(patient=patient).order_by("-datum", "-id").first()
            if bericht is None:
                return Response({"patient": "Dieser Testpatient hat noch keinen Bericht."},
                                status=status.HTTP_400_BAD_REQUEST)
            kontext = Kontext(patient=patient, plan=plan, bericht=bericht)
        if request.data.get("ausgabe") == "email":
            # Text der E-Mail zur Kontrolle im Editor (F172)
            from .schreiben import email_aus_vorlage

            return Response(email_aus_vorlage(art, kontext, bloecke) or {"betreff": "", "text": ""})
        pdf, _ = erzeuge_aus_vorlage(art, kontext, bloecke=bloecke, wasserzeichen="ENTWURF",
                                     titel=f"Vorschau {art_name(art)}", ausrichtung=ausrichtung)
        if art == Dokumentvorlage.Art.REISEBESCHEINIGUNG:
            from .schreiben import anhaengen, reise_attest

            pdf = anhaengen(pdf, [reise_attest(kontext)])
        return pdf_antwort(pdf, f"Vorschau-{art}.pdf")


def _vorschau_termin(patient, benutzer):
    """Terminbestätigung: nächster Termin des Testpatienten, sonst ein gedachter in einer Woche um 14:30 Uhr."""
    from datetime import time, timedelta

    from django.utils import timezone

    from patienten.models import Termin

    termin = (Termin.objects.filter(patient=patient).order_by("-faellig_am").first()
              or Termin(patient=patient, art=Termin.Art.PRAXISTERMIN, titel="Sprechstunde",
                        faellig_am=timezone.localdate() + timedelta(days=7), uhrzeit=time(14, 30)))
    return Kontext(patient=patient, termin=termin, benutzer=benutzer)


def _vorschau_ankuendigung(patient, benutzer):
    """Patientenankündigung: die Termine der Testpatienten in den nächsten 14 Tagen."""
    from datetime import timedelta

    from django.utils import timezone

    from patienten.models import Termin

    von = timezone.localdate()
    bis = von + timedelta(days=14)
    # nur Testpatienten im eigenen Bereich (aktive Firma, Sicherheitsprüfung 11.10.2026)
    termine = list(Termin.objects.filter(patient__in=patienten_fuer(benutzer), patient__ist_test=True,
                                         faellig_am__range=(von, bis))
                   .select_related("patient", "ort").order_by("faellig_am", "uhrzeit", "id")[:40])
    return Kontext(patient=None, zeitraum=(von, bis), termine=termine, benutzer=benutzer)


VORSCHAU_SCHREIBEN = {
    "patientenaufnahme": lambda p, u: Kontext(patient=p, benutzer=u),
    "reisebescheinigung": lambda p, u: Kontext(patient=p, benutzer=u),
    "terminbestaetigung": _vorschau_termin,
    "patientenankuendigung": _vorschau_ankuendigung,
}


# ------------------------------------------------------------------------------------------------ Anlagen (F174)
MAX_ANLAGE = 20 * 1024 * 1024


def _anlage(a):
    return {"id": a.id, "name": a.name, "beschreibung": a.beschreibung, "dateiname": a.dateiname,
            "groesse": a.groesse, "aktiv": a.aktiv, "reihenfolge": a.reihenfolge, "mitgeliefert": bool(a.mitgeliefert),
            "hochgeladen_am": a.hochgeladen_am, "hochgeladen_von": benutzername(a.hochgeladen_von)}


class AnlagenView(APIView):
    """Lesen: jeder Angemeldete mit Rechten; hochladen und ändern: „Vorlagen pflegen“."""

    permission_classes = [recht("vorlagen_pflegen", lesen=None)]

    def get(self, request):
        from .models import Anlage

        Anlage.mitgelieferte_anlegen()
        qs = Anlage.objects.select_related("hochgeladen_von")
        if not (request.query_params.get("alle") == "1" and request.user.hat_recht("vorlagen_pflegen")):
            qs = qs.filter(aktiv=True)
        return Response([_anlage(a) for a in qs])

    def post(self, request):
        from django.conf import settings

        from .models import Anlage
        from .pdf import sha256

        datei = request.FILES.get("datei")
        name = (request.data.get("name") or "").strip()
        fehler = {}
        if not name or len(name) > 150:
            fehler["name"] = "Bitte einen Namen angeben (höchstens 150 Zeichen)."
        if datei is None:
            fehler["datei"] = "Bitte eine PDF-Datei wählen."
        elif datei.size > MAX_ANLAGE:
            fehler["datei"] = "Die Datei ist größer als 20 MB."
        daten = b""
        if datei is not None and "datei" not in fehler:
            daten = datei.read()
            if not daten.startswith(b"%PDF-"):
                fehler["datei"] = "Nur PDF-Dateien."
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        pruefsumme = sha256(daten)
        ziel = f"anlagen/{pruefsumme[:24]}.pdf"
        (settings.EPM_DOKUMENTE / "anlagen").mkdir(parents=True, exist_ok=True)
        if Anlage.objects.filter(datei=ziel).exists():
            return Response({"datei": "Diese Datei ist schon als Anlage hinterlegt."}, status=status.HTTP_400_BAD_REQUEST)
        (settings.EPM_DOKUMENTE / ziel).write_bytes(daten)
        dateiname = re.sub(r"[^\w.\- ]+", "", datei.name or "")[:140].strip() or "Anlage.pdf"
        if not dateiname.lower().endswith(".pdf"):
            dateiname += ".pdf"
        a = Anlage(name=name, beschreibung=(request.data.get("beschreibung") or "")[:300], datei=ziel,
                   dateiname=dateiname, sha256=pruefsumme, groesse=len(daten), hochgeladen_von=request.user)
        a._history_user = request.user
        a.save()
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Anlage {a.name}", aktion="hochgeladen")
        return Response(_anlage(a), status=status.HTTP_201_CREATED)


class AnlageView(APIView):
    permission_classes = [recht("vorlagen_pflegen", lesen=None)]

    def patch(self, request, pk):
        from .models import Anlage

        a = Anlage.objects.filter(pk=pk).first()
        if a is None:
            raise Http404("Anlage nicht gefunden.")
        d = request.data
        fehler = {}
        if "name" in d:
            if not isinstance(d["name"], str) or not d["name"].strip() or len(d["name"]) > 150:
                fehler["name"] = "Bitte einen Namen angeben (höchstens 150 Zeichen)."
            else:
                a.name = d["name"].strip()
        if "beschreibung" in d:
            if not isinstance(d["beschreibung"], str) or len(d["beschreibung"]) > 300:
                fehler["beschreibung"] = "Höchstens 300 Zeichen."
            else:
                a.beschreibung = d["beschreibung"]
        if "aktiv" in d:
            if not isinstance(d["aktiv"], bool):
                fehler["aktiv"] = "Bitte true oder false."
            else:
                a.aktiv = d["aktiv"]
        if "reihenfolge" in d:
            if not isinstance(d["reihenfolge"], int) or isinstance(d["reihenfolge"], bool) or not 0 <= d["reihenfolge"] <= 32000:
                fehler["reihenfolge"] = "Zahl von 0 bis 32000."
            else:
                a.reihenfolge = d["reihenfolge"]
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        a._history_user = request.user
        a.save()
        protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Anlage {a.name}", aktion="geändert")
        return Response(_anlage(a))


class AnlageDateiView(APIView):
    permission_classes = [recht("vorlagen_pflegen", lesen=None)]

    def get(self, request, pk):
        from .models import Anlage

        a = Anlage.objects.filter(pk=pk).first()
        if a is None or not a.pfad.is_file():
            raise Http404("Anlage nicht gefunden.")
        return pdf_antwort(a.pfad.read_bytes(), a.dateiname)
