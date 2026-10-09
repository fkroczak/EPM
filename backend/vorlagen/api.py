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
                                              mit "ausgabe": "email" → {"betreff", "text"} der Schreiben

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

from .bloecke import MIT_EMAIL, OPTIONEN, TYPEN, pruefe_bloecke
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
    from stammdaten.models import Einstellungen

    return {"art": art, "name": Dokumentvorlage.Art(art).label, "aktiv": _version(aktiv),
            "entwurf": _version(Dokumentvorlage.entwurf_von(art)), "versionen": [_version(v) for v in versionen],
            # Vordrucke: Wasserzeichen „ENTWURF“ (Startvorlage ungeprüft) und ob es manuell abgeschaltet ist (U17)
            "entwurfsmodus": {"moeglich": art in Dokumentvorlage.VORDRUCKE and aktiv.veroeffentlicht_von_id is None,
                              "aktiv": aktiv.im_entwurfsmodus,
                              "aus": art in (Einstellungen.aktuell().vordrucke_ohne_entwurf or [])}}


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
            "bausteine": [{"typ": k, "name": v} for k, v in TYPEN.items() if k != "email" or art in MIT_EMAIL],
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
        liste = [a for a in (e.vordrucke_ohne_entwurf or []) if a != art] + ([art] if aus else [])
        if sorted(liste) != sorted(e.vordrucke_ohne_entwurf or []):
            e.vordrucke_ohne_entwurf = sorted(liste)
            e._history_user = request.user
            e.save()
            protokolliere(SystemEreignis.Art.VORLAGE, request, objekt=f"Dokumentvorlage {Dokumentvorlage.Art(art).label}",
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
        kontext = Kontext(patient=patient, plan=plan, benutzer=request.user)
        if art in VORSCHAU_SCHREIBEN:
            kontext = VORSCHAU_SCHREIBEN[art](patient, request.user)
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
                                     titel=f"Vorschau {Dokumentvorlage.Art(art).label}")
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
    termine = list(Termin.objects.filter(patient__ist_test=True, faellig_am__range=(von, bis))
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
