"""
Administration › System: Wartung ohne SSH (Wunsch 10.10.2026, F179 – „Der Praxismanager soll sich nie wieder per SSH
auf den Server schalten müssen“). Alles läuft als Auftrag über den Systemagenten (feste Liste, geprüfte Angaben), mit
Bestätigung wie unter Tätigkeiten und mit Eintrag im Audit-Log. Recht „Systemverwaltung“.

POST   /api/system/dienste/neustart/              {dienst, minuten, hinweis?, kennwort, code} → einen Container neu starten
POST   /api/system/versionen/zurueck/             {tag, minuten, hinweis?, kennwort, code} → frühere Version (vorher Sicherung)
POST   /api/system/pakete/erstellen/              Update-Paket der laufenden Version erstellen (Test-VM)
GET    /api/system/pakete/<datei>/                bereitgestelltes Update-Paket herunterladen
POST   /api/system/hochladen/                     {art: "paket" | "ocr", name, groesse} → {upload, teil}
PUT    /api/system/hochladen/<upload>/?versatz=N  nächstes Stück (application/octet-stream)
DELETE /api/system/hochladen/<upload>/            hochgeladene Datei verwerfen
POST   /api/system/hochladen/<upload>/einspielen/ {minuten?, hinweis?, kennwort?, code?} → Paket bzw. Modelle einspielen
POST   /api/system/zertifikat/erneuern/           {kennwort, code}
POST   /api/system/zertifikat/importieren/        {zertifikat, schluessel, ca?, kennwort, code} (PEM als Text)
POST   /api/system/protokolle/                    {quelle, zeilen} → der Agent liest das Protokoll (nur lesend)
GET    /api/system/protokolle/<kennung>/          abgerufenes Protokoll; ?herunterladen=1 als Datei

Schlüssel (und das Zertifikat selbst) gehen nur in die Auftragsdatei an den Server (0600, der Agent löscht sie sofort) –
nie in die Datenbank oder das Audit-Log; dort stehen nur Inhaber, Aussteller, Ablauf und Fingerabdruck.
Protokolle legt der Agent für eine Stunde ab; sie werden nicht in der Datenbank gespeichert.
"""
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import SystemRecht
from audit.models import SystemEreignis, protokolliere

from . import hochladen, host
from .api import auftrag_anlegen
from .models import Systemauftrag

ORDNER_FEHLT = ("Die Ordner für das Hoch- und Herunterladen fehlen. Bitte auf dem Server einmal „sudo epm-update“ "
                "(bzw. rollout/04-projekt.sh) ausführen.")
PEM_MAX = 20000


def _fehler(feld, text, code=status.HTTP_400_BAD_REQUEST):
    return Response({feld: text}, status=code)


def _agent_aktuell():
    """Aufträge, die EPM umstellen, nur mit laufendem Agenten: ein Auftrag, der wartet, bis er wieder läuft, würde zu
    einem unerwarteten Zeitpunkt umstellen."""
    if not host.agent_erreichbar():
        return Response({"fehler": "Der Systemagent auf dem Server meldet sich gerade nicht. Das ist erst möglich, wenn "
                                   "er wieder läuft."}, status=status.HTTP_409_CONFLICT)
    return None


class DienstNeustartView(APIView):
    permission_classes = [SystemRecht]

    def post(self, request):
        dienst = request.data.get("dienst")
        if dienst not in host.DIENSTE:
            return _fehler("dienst", f"Erlaubt: {', '.join(host.DIENSTE)}.")
        return auftrag_anlegen(request, "dienst_neustart", parameter={"dienst": dienst}, objekt=f"Dienst {dienst}",
                               protokoll_details={"dienst": dienst})


class ZurueckView(APIView):
    """Auf eine frühere Version umstellen, die noch als Image auf dem Server liegt (``epm-update --zurueck``)."""

    permission_classes = [SystemRecht]

    def post(self, request):
        tag = request.data.get("tag")
        if not isinstance(tag, str) or not host.TAG_MUSTER.match(tag):
            return _fehler("tag", "Unbekannte Version.")
        antwort = _agent_aktuell()
        if antwort is not None:
            return antwort
        versionen = ((host.host_status() or {}).get("versionen") or {})
        eintrag = next((v for v in versionen.get("liste") or [] if isinstance(v, dict) and v.get("tag") == tag), None)
        if eintrag is None or not eintrag.get("vollstaendig"):
            return _fehler("tag", "Diese Version liegt auf dem Server nicht (vollständig) vor.")
        if eintrag.get("aktiv") or versionen.get("aktiv") == tag:
            return _fehler("tag", "Diese Version läuft bereits.")
        return auftrag_anlegen(request, "epm_zurueck", parameter={"tag": tag}, objekt=f"Version {tag}",
                               protokoll_details={"tag": tag, "bisher": versionen.get("aktiv") or ""})


class PaketErstellenView(APIView):
    permission_classes = [SystemRecht]

    def post(self, request):
        return auftrag_anlegen(request, "epm_paket_erstellen")


class PaketDateiView(APIView):
    """Bereitgestelltes Update-Paket ausliefern (Nginx per X-Accel-Redirect, derselbe Ordner wie bei Sicherungen)."""

    permission_classes = [SystemRecht]

    def get(self, request, datei):
        m = host.PAKET_MUSTER.match(datei or "")
        pfad = host.ordner_download() / datei if m else None
        if pfad is None or not pfad.is_file() or pfad.is_symlink():
            return Response({"fehler": "Dieses Update-Paket liegt nicht (mehr) zum Herunterladen bereit."},
                            status=status.HTTP_404_NOT_FOUND)
        protokolliere(SystemEreignis.Art.SYSTEM, request, objekt=f"Update-Paket {m.group(1)}",
                      ereignis="paket_heruntergeladen", tag=m.group(1), groesse=pfad.stat().st_size)
        if settings.EPM_X_ACCEL:
            antwort = HttpResponse(content_type="application/x-tar")
            antwort["X-Accel-Redirect"] = "/_geschuetzt/sicherung/" + datei
        else:
            antwort = FileResponse(open(pfad, "rb"), content_type="application/x-tar")
        antwort["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(datei)}"
        antwort["Cache-Control"] = "private, no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        return antwort


# ------------------------------------------------------------------ Hochladen: Update-Paket, OCR-Modelle
ARTEN = ("paket", "ocr")
AKTION_JE_ART = {"paket": "epm_paket", "ocr": "ocr_modelle"}


class HochladenView(APIView):
    permission_classes = [SystemRecht]

    def post(self, request):
        art = request.data.get("art")
        if art not in ARTEN:
            return _fehler("art", "Erlaubt: paket, ocr.")
        return hochladen.beginnen(request, art, ORDNER_FEHLT)


def _laeuft(kennung):
    return Systemauftrag.objects.filter(ziel=Systemauftrag.Ziel.SERVER, aktion__in=list(AKTION_JE_ART.values()),
                                        parameter__upload=kennung,
                                        status__in=[Systemauftrag.Status.WARTET, Systemauftrag.Status.LAEUFT]).exists()


class HochladenTeilView(APIView):
    permission_classes = [SystemRecht]
    parser_classes = [hochladen.RohParser, JSONParser]

    def put(self, request, kennung):
        pfad, meta = hochladen.finde(kennung, ARTEN)
        if pfad is None:
            return Response({"fehler": "Dieser Upload ist nicht (mehr) bekannt. Bitte neu beginnen."},
                            status=status.HTTP_404_NOT_FOUND)
        return hochladen.teil_anhaengen(request, pfad, meta)

    def delete(self, request, kennung):
        pfad, meta = hochladen.finde(kennung, ARTEN)
        if pfad is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if _laeuft(kennung):
            return Response({"fehler": "Der Server verarbeitet diese Datei gerade."}, status=status.HTTP_409_CONFLICT)
        hochladen.entfernen(pfad)
        protokolliere(SystemEreignis.Art.SYSTEM, request, objekt=f"{hochladen.ARTEN[hochladen.art_von(meta)]['name']} "
                      "hochladen", ereignis="upload_abgebrochen", datei=str(meta.get("name") or ""), upload=kennung,
                      upload_art=hochladen.art_von(meta))
        return Response(status=status.HTTP_204_NO_CONTENT)


class EinspielenView(APIView):
    """Vollständig hochgeladenes Update-Paket bzw. OCR-Modelle an den Agenten: er kopiert die Datei in einen Ordner, den
    das Backend nicht beschreiben kann, prüft den Inhalt (nur bekannte Namen, keine Verweise) und übergibt sie an
    ``epm-update --paket`` bzw. ``epm-ocr-modelle einspielen`` (beide prüfen die Prüfsummen)."""

    permission_classes = [SystemRecht]

    def post(self, request, kennung):
        pfad, meta = hochladen.finde(kennung, ARTEN)
        if pfad is None:
            return Response({"fehler": "Dieser Upload ist nicht (mehr) bekannt. Bitte neu beginnen."},
                            status=status.HTTP_404_NOT_FOUND)
        erhalten = pfad.stat().st_size
        if erhalten != meta.get("groesse"):
            return Response({"fehler": "Die Datei ist noch nicht vollständig hochgeladen.", "erhalten": erhalten},
                            status=status.HTTP_409_CONFLICT)
        art = hochladen.art_von(meta)
        name = str(meta.get("name") or "")
        return auftrag_anlegen(request, AKTION_JE_ART[art], parameter={"upload": kennung, "datei": name},
                               objekt=f"{hochladen.ARTEN[art]['name']} {name}"[:200],
                               protokoll_details={"datei": name, "groesse": erhalten})


# ------------------------------------------------------------------ Zertifikat
class ZertifikatErneuernView(APIView):
    permission_classes = [SystemRecht]

    def post(self, request):
        z = ((host.host_status() or {}).get("zertifikat") or {})
        if z and not z.get("ca_schluessel"):
            return Response({"fehler": "Auf dem Server gibt es keine eigene CA – erneuern geht nur mit ihr. Ein Zertifikat "
                                       "einer anderen CA bitte über „Zertifikat importieren“ austauschen."},
                            status=status.HTTP_409_CONFLICT)
        return auftrag_anlegen(request, "zertifikat_erneuern", objekt="Serverzertifikat")


def pem_angaben(crt: str, key: str, ca: str | None):
    """PEM prüfen, so weit es das Backend kann: lesbar, Schlüssel passt zum Zertifikat, Zertifikat stammt von der CA.
    Rückgabe (Fehler | None, Angaben fürs Audit-Log). Ob es für den Namen des Servers gilt, prüft epm-zertifikat."""
    for feld, text, marke in (("zertifikat", crt, "CERTIFICATE"), ("schluessel", key, "PRIVATE KEY"),
                              ("ca", ca, "CERTIFICATE")):
        if feld == "ca" and not text:
            continue
        if not isinstance(text, str) or len(text) > PEM_MAX or "\0" in text or f"{marke}-----" not in text:
            return {feld: "Bitte eine PEM-Datei wählen (Text, beginnt mit „-----BEGIN …“)."}, None
    if len(crt) + len(key) + len(ca or "") > 3 * PEM_MAX - 10000:
        # die Auftragsdatei an den Agenten darf höchstens 64 KB groß sein
        return {"zertifikat": "Zertifikat, Schlüssel und CA sind zusammen zu groß (höchstens 50.000 Zeichen)."}, None
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
    except ImportError:  # pragma: no cover – kommt mit webauthn ins Image
        return None, {}
    try:
        zert = x509.load_pem_x509_certificate(crt.encode())
    except ValueError:
        return {"zertifikat": "Das Zertifikat ist nicht lesbar."}, None
    try:
        schluessel = serialization.load_pem_private_key(key.encode(), password=None)
    except (ValueError, TypeError):
        return {"schluessel": "Der Schlüssel ist nicht lesbar oder mit einem Passwort geschützt (bitte ohne Passwort "
                              "exportieren)."}, None
    oeffentlich = serialization.PublicFormat.SubjectPublicKeyInfo
    if schluessel.public_key().public_bytes(serialization.Encoding.PEM, oeffentlich) != \
            zert.public_key().public_bytes(serialization.Encoding.PEM, oeffentlich):
        return {"schluessel": "Schlüssel und Zertifikat passen nicht zusammen."}, None
    if ca:
        try:
            aussteller = x509.load_pem_x509_certificate(ca.encode())
            zert.verify_directly_issued_by(aussteller)
        except Exception:  # noqa: BLE001 – jede Abweichung (Signatur, Verfahren) heißt: nicht von dieser CA
            return {"ca": "Das Zertifikat stammt nicht von dieser CA."}, None
    return None, {"inhaber": zert.subject.rfc4514_string()[:200], "aussteller": zert.issuer.rfc4514_string()[:200],
                  "gueltig_bis": zert.not_valid_after_utc.isoformat(),
                  "fingerabdruck": zert.fingerprint(hashes.SHA256()).hex()}


class ZertifikatImportierenView(APIView):
    permission_classes = [SystemRecht]

    def post(self, request):
        crt, key, ca = request.data.get("zertifikat"), request.data.get("schluessel"), request.data.get("ca") or None
        fehler, angaben = pem_angaben(crt, key, ca)
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        return auftrag_anlegen(request, "zertifikat_importieren", parameter={"mit_ca": bool(ca)},
                               geheim={"zertifikat": crt, "schluessel": key, **({"ca": ca} if ca else {})},
                               objekt="Serverzertifikat", protokoll_details={**angaben, "mit_ca": bool(ca)})


# ------------------------------------------------------------------ Protokolle (nur lesend)
class ProtokolleView(APIView):
    permission_classes = [SystemRecht]

    def get(self, request):
        return Response({"quellen": [{"quelle": q, "name": n} for q, n in host.PROTOKOLLE.items()],
                         "zeilen": list(host.PROTOKOLL_ZEILEN)})

    def post(self, request):
        quelle, zeilen = request.data.get("quelle"), request.data.get("zeilen", 500)
        if quelle not in host.PROTOKOLLE:
            return _fehler("quelle", "Unbekanntes Protokoll.")
        if isinstance(zeilen, bool) or zeilen not in host.PROTOKOLL_ZEILEN:
            return _fehler("zeilen", "Bitte 100, 500 oder 2000 Zeilen wählen.")
        return auftrag_anlegen(request, "protokoll", parameter={"quelle": quelle, "zeilen": zeilen},
                               objekt=host.PROTOKOLLE[quelle], protokoll_details={"quelle": quelle, "zeilen": zeilen})


class ProtokollView(APIView):
    """Das vom Agenten abgerufene Protokoll; jeder Abruf als Datei steht im Audit-Log."""

    permission_classes = [SystemRecht]

    def get(self, request, kennung):
        a = Systemauftrag.objects.filter(kennung=kennung, ziel=Systemauftrag.Ziel.SERVER, aktion="protokoll").first()
        if a is None:
            return Response({"fehler": "Protokoll nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)
        pfad = host.protokoll_datei(a)
        try:
            with open(pfad, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            return Response({"fehler": "Das Protokoll liegt nicht (mehr) bereit (nach einer Stunde entfernt) – bitte neu "
                                       "abrufen."}, status=status.HTTP_404_NOT_FOUND)
        quelle = str(a.parameter.get("quelle") or "")
        if request.query_params.get("herunterladen"):
            protokolliere(SystemEreignis.Art.SYSTEM, request, objekt=host.PROTOKOLLE.get(quelle, quelle),
                          ereignis="protokoll_heruntergeladen", quelle=quelle)
            antwort = HttpResponse(text, content_type="text/plain; charset=utf-8")
            name = f"epm-protokoll-{quelle}-{a.angefordert_am:%Y-%m-%d_%H%M}.txt"
            antwort["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
            antwort["Cache-Control"] = "private, no-store"
            antwort["X-Content-Type-Options"] = "nosniff"
            return antwort
        return Response({"quelle": quelle, "name": host.PROTOKOLLE.get(quelle, quelle),
                         "zeilen": a.parameter.get("zeilen"), "abgerufen_am": a.beendet_am or a.angefordert_am,
                         "text": text})
