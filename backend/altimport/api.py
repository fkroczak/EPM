"""
Administration › Import (nur mit Recht „Altdaten übernehmen“, nur Admin): Übernahme der Altdaten (F65).

GET    /api/altimport/                    Stand: Dump, Vorbedingungen, übernommener Bestand, letzte Läufe
POST   /api/altimport/dump/               Dump hochladen (multipart „datei“: .sql oder .sql.gz)
DELETE /api/altimport/dump/               geladenen Dump entfernen (Zuordnungen bleiben)
GET    /api/altimport/zuordnung/          Zuordnungen mit Vorschlägen, offenen Punkten, Zählung und Protokoll
PATCH  /api/altimport/zuordnung/          {bereich, aenderungen} → Entscheidungen speichern (null = zurücknehmen)
POST   /api/altimport/probelauf/          alles schreiben und zurückrollen → Lauf mit Zählung und Protokoll
POST   /api/altimport/import/             {kennwort, code} → Altdaten übernehmen
GET    /api/altimport/dokumente/          Überblick über den Dokumentenordner auf dem Server
POST   /api/altimport/dokumente/          nächste Etappe der Dokumente übernehmen
POST   /api/altimport/zuruecknehmen/      {kennwort, code, bestaetigung: "ZURÜCKNEHMEN"} → alles Übernommene entfernen
POST   /api/altimport/abschliessen/       {kennwort, code, bestaetigung: "ABSCHLIESSEN", ohne_dokumente?} → Go-live
GET    /api/altimport/laeufe/<id>/        ein Lauf mit Protokoll;  …/text/ dasselbe als Textdatei
"""
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import ImportRecht
from epm.api_basis import benutzername

from . import dienst
from .dump import DumpFehler
from .felder import ANLAESSE, KATEGORIEN, ROLLEN
from .models import Alttabelle, Importlauf, Importstand

S = Importstand.Status


def _abgelehnt(f: dienst.Hindernis):
    return Response({"fehler": str(f)}, status=status.HTTP_409_CONFLICT)


def lauf_daten(lauf: Importlauf, mit_protokoll: bool = False) -> dict:
    daten = {"id": lauf.id, "art": lauf.art, "art_name": lauf.get_art_display(), "begonnen_am": lauf.begonnen_am,
             "beendet_am": lauf.beendet_am, "person": benutzername(lauf.benutzer), "erfolgreich": lauf.erfolgreich,
             "dump_name": lauf.dump_name, "zahlen": lauf.zahlen, "fehler": lauf.fehler}
    if mit_protokoll:
        daten["protokoll"] = lauf.protokoll
    return daten


def stand_daten(stand: Importstand) -> dict:
    daten = {
        "status": stand.status, "status_name": stand.get_status_display(),
        "dump": None, "tabellen": [], "echte_akten": dienst.echte_akten(),
        "importiert_am": stand.importiert_am, "importiert_von": benutzername(stand.importiert_von),
        "abgeschlossen_am": stand.abgeschlossen_am, "abgeschlossen_von": benutzername(stand.abgeschlossen_von),
        "uebernommen": dienst.bestand_der_uebernahme() if stand.status == S.IMPORTIERT else None,
        "dokumentenordner": str(dienst.dokumentenordner()),
        "upload_max_mb": settings.EPM_UPLOAD_MAX_MB,
        "laeufe": [lauf_daten(x) for x in Importlauf.objects.select_related("benutzer")[:30]],
    }
    if stand.status in (S.GELADEN, S.IMPORTIERT):
        daten["dump"] = {"name": stand.dump_name, "sha256": stand.dump_sha256, "groesse": stand.dump_groesse,
                         "geladen_am": stand.dump_geladen_am, "geladen_von": benutzername(stand.dump_geladen_von),
                         "hinweise": stand.dump_hinweise}
        daten["tabellen"] = [{"name": t.name, "spalten": len(t.spalten), "zeilen": len(t.zeilen)}
                             for t in Alttabelle.objects.all()]
    return daten


class StandView(APIView):
    permission_classes = [ImportRecht]

    def get(self, request):
        return Response(stand_daten(Importstand.aktuell()))


class DumpView(APIView):
    permission_classes = [ImportRecht]
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        datei = request.FILES.get("datei")
        if datei is None:
            return Response({"datei": "Bitte den Dump auswählen (.sql oder .sql.gz)."}, status=status.HTTP_400_BAD_REQUEST)
        grenze = settings.EPM_UPLOAD_MAX_MB * 1024 * 1024
        if datei.size > grenze:
            return Response({"datei": f"Die Datei ist größer als {settings.EPM_UPLOAD_MAX_MB} MB. Bitte gepackt hochladen "
                                      f"(.sql.gz)."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            stand = dienst.dump_laden(datei.read(), datei.name, request.user, request)
        except DumpFehler as f:
            return Response({"datei": str(f)}, status=status.HTTP_400_BAD_REQUEST)
        except dienst.Hindernis as f:
            return _abgelehnt(f)
        return Response(stand_daten(stand), status=status.HTTP_201_CREATED)

    def delete(self, request):
        try:
            stand = dienst.dump_entfernen(request.user, request)
        except dienst.Hindernis as f:
            return _abgelehnt(f)
        return Response(stand_daten(stand))


class ZuordnungView(APIView):
    permission_classes = [ImportRecht]

    def _daten(self, stand):
        if stand.status != S.GELADEN:
            return {"status": stand.status, "stand": None, "hindernisse": [], "bestand": None}
        vorhandenes = dienst.bestand()
        e = dienst.stand_berechnen(stand, vorhandenes)
        return {
            "status": stand.status, "stand": e.als_dict(), "hindernisse": dienst.vorbedingungen(stand, e),
            "bestand": {k: vorhandenes[k] for k in ("benutzer", "versorger", "ansprechpartner", "katheter", "praeparate")},
            "auswahl": {"rollen": list(ROLLEN), "anlaesse": ANLAESSE, "kategorien": KATEGORIEN},
        }

    def get(self, request):
        return Response(self._daten(Importstand.aktuell()))

    def patch(self, request):
        try:
            stand = dienst.zuordnung_speichern(str(request.data.get("bereich", "")), request.data.get("aenderungen"),
                                               request.user, request)
        except dienst.Hindernis as f:
            return _abgelehnt(f)
        return Response(self._daten(stand))


class ProbelaufView(APIView):
    permission_classes = [ImportRecht]

    def post(self, request):
        return Response(lauf_daten(dienst.probelauf(request.user), mit_protokoll=True))


def _bestaetigt(request, was: str, wort: str | None = None):
    """Kennwort und zweiter Faktor; bei unumkehrbaren Schritten zusätzlich das abgetippte Wort. → Fehler oder None."""
    from system.api import bestaetigung_pruefen

    if wort is not None:
        if "".join(str(request.data.get("bestaetigung", "")).upper().split()) != wort:
            return {"bestaetigung": f"Bitte zur Bestätigung „{wort}“ eintippen."}
    return bestaetigung_pruefen(request, was)


class ImportView(APIView):
    permission_classes = [ImportRecht]

    def post(self, request):
        fehler = _bestaetigt(request, "Altdaten übernehmen")
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        try:
            lauf = dienst.importiere(request.user, request)
        except dienst.Hindernis as f:
            return _abgelehnt(f)
        return Response(lauf_daten(lauf, mit_protokoll=True),
                        status=status.HTTP_201_CREATED if lauf.erfolgreich else status.HTTP_200_OK)


class DokumenteView(APIView):
    permission_classes = [ImportRecht]

    def get(self, request):
        return Response(dienst.dokumente_stand())

    def post(self, request):
        try:
            return Response(dienst.dokumente_uebernehmen(request.user, request))
        except dienst.Hindernis as f:
            return _abgelehnt(f)


class ZuruecknehmenView(APIView):
    permission_classes = [ImportRecht]

    def post(self, request):
        fehler = _bestaetigt(request, "Übernahme der Altdaten zurücknehmen", "ZURÜCKNEHMEN")
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        try:
            lauf = dienst.zuruecknehmen(request.user, request)
        except dienst.Hindernis as f:
            return _abgelehnt(f)
        return Response(lauf_daten(lauf, mit_protokoll=True))


class AbschliessenView(APIView):
    permission_classes = [ImportRecht]

    def post(self, request):
        fehler = _bestaetigt(request, "Übernahme der Altdaten abschließen", "ABSCHLIESSEN")
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        try:
            lauf = dienst.abschliessen(request.user, request,
                                       ohne_dokumente=request.data.get("ohne_dokumente") in (True, "true", "1", 1))
        except dienst.Hindernis as f:
            return _abgelehnt(f)
        return Response(lauf_daten(lauf, mit_protokoll=True))


BEREICHE = {"benutzer": "Benutzer", "versorger": "Versorger", "patienten": "Patienten", "gewichte": "Gewichte",
            "kontakte": "Kontakte", "infusionen": "Infusionspläne", "benutzerdaten": "Benutzer"}
ZAHLEN = [("patienten", "Patienten"), ("gewichte", "Gewichte"), ("kontakte", "Kontakte"), ("infusionen", "Infusionspläne")]
NICHT = {"geloescht": "im Altsystem gelöscht", "ausgelassen": "auf Entscheidung ausgelassen", "fehler": "wegen offener Auffälligkeit",
         "patient_nicht_uebernommen": "Patient wird nicht übernommen", "ohne_patient": "ohne Patient",
         "platzhalter": "Platzhalter (leer, 0, 9999)", "leer": "ohne Text"}


def lauf_als_text(lauf: Importlauf) -> str:
    """Importprotokoll als Text – zum Ablegen bei den Unterlagen der Migration. Nennt Nummern, keine Namen."""
    from django.utils import timezone

    zeilen = [f"EPM – Übernahme der Altdaten: {lauf.get_art_display()}",
              f"Zeitpunkt: {timezone.localtime(lauf.begonnen_am):%d.%m.%Y %H:%M} · Person: {benutzername(lauf.benutzer) or '—'}",
              f"Dump: {lauf.dump_name or '—'}" + (f" (SHA-256 {lauf.dump_sha256})" if lauf.dump_sha256 else ""),
              f"Ergebnis: {'erfolgreich' if lauf.erfolgreich else 'nicht erfolgreich'}", ""]
    if lauf.fehler:
        zeilen += ["Fehler / Hindernisse:", *[f"  {z}" for z in lauf.fehler.splitlines()], ""]
    z = lauf.zahlen or {}
    if any(k in z for k, _ in ZAHLEN):
        zeilen.append("Zählung alt gegen neu:")
        for schluessel, titel in ZAHLEN:
            x = z.get(schluessel) or {}
            nicht = ", ".join(f"{n} {NICHT.get(k, k)}" for k, n in (x.get("nicht") or {}).items())
            zeilen.append(f"  {titel}: {x.get('alt', 0)} im Altsystem, {x.get('neu', 0)} übernommen"
                          + (f" (nicht übernommen: {nicht})" if nicht else ""))
        zeilen.append("")
    if lauf.protokoll:
        zeilen.append("Protokoll:")
        for p in lauf.protokoll:
            regel = f"Regel {p.get('regel')}" if p.get("regel") else "allgemein"
            beispiele = f" – z. B. Nr. {', '.join(p['beispiele'])}" if p.get("beispiele") else ""
            zeilen.append(f"  [{p.get('stufe', '')}] {BEREICHE.get(p.get('bereich'), p.get('bereich', ''))}, {regel}: "
                          f"{p.get('anzahl', 0)} × {p.get('text', '')}{beispiele}")
    return "\r\n".join(zeilen) + "\r\n"


class LaufView(APIView):
    permission_classes = [ImportRecht]

    def get(self, request, pk, text=False):
        lauf = Importlauf.objects.select_related("benutzer").filter(pk=pk).first()
        if lauf is None:
            return Response({"fehler": "Lauf nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)
        if text:
            antwort = HttpResponse(lauf_als_text(lauf), content_type="text/plain; charset=utf-8")
            antwort["Content-Disposition"] = f'attachment; filename="EPM-Altdaten-{lauf.art}-{lauf.id}.txt"'
            antwort["Cache-Control"] = "private, no-store"
            return antwort
        return Response(lauf_daten(lauf, mit_protokoll=True))
