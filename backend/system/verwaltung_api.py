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
POST   /api/system/journal/aufraeumen/            {art: "groesse" | "zeit", wert} (feste Auswahl)
POST   /api/system/images/loeschen/               {dateien: [...], tags: [...], kennwort, code} – laufende und vorherige
                                                  Version bleiben immer
POST   /api/system/uhr/                           {zeitzone?, ntp, server: [...], zeit?, kennwort, code}
POST   /api/system/notfall/                       {mit_sicherung, kennwort, code} → Notfallpaket erstellen (F188)
GET    /api/system/notfall/<datei>/               bereitgestelltes Notfallpaket herunterladen (Audit-Log)
GET    /api/system/notfallplan/?art=html|pdf|md      Wiederaufbau-Plan (auch mit Recht „Sicherungen verwalten“)

Schlüssel (und das Zertifikat selbst) gehen nur in die Auftragsdatei an den Server (0600, der Agent löscht sie sofort) –
nie in die Datenbank oder das Audit-Log; dort stehen nur Inhaber, Aussteller, Ablauf und Fingerabdruck.
Protokolle legt der Agent für eine Stunde ab; sie werden nicht in der Datenbank gespeichert.
"""
import os
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


# ------------------------------------------------------------------ Nachtrag 10.10.2026: Aufräumen und Uhrzeit
class JournalView(APIView):
    """Systemprotokoll (Journal) auf eine Größe oder ein Alter verkleinern (feste Auswahl), einfache Rückfrage."""

    permission_classes = [SystemRecht]

    def post(self, request):
        art, wert = request.data.get("art"), request.data.get("wert")
        if not ((art == "groesse" and wert in host.JOURNAL_GROESSE) or (art == "zeit" and wert in host.JOURNAL_ZEIT)):
            return _fehler("wert", "Bitte eine Größe (100M, 200M, 500M, 1G) oder ein Alter (2weeks, 1month, 3months, "
                                   "6months) wählen.")
        return auftrag_anlegen(request, "journal_aufraeumen", parameter={"art": art, "wert": wert}, objekt="Journal",
                               protokoll_details={"journal_art": art, "wert": wert})


def geschuetzte_tags(status_host: dict) -> set | None:
    """Wie im Agenten: laufende Version und die nächstältere (für „Zurückschalten“)."""
    v = (status_host or {}).get("versionen") or {}
    if not v.get("verfuegbar") or not v.get("aktiv"):
        return None
    tags = [e.get("tag") for e in v.get("liste") or [] if isinstance(e, dict)]
    geschuetzt = {v["aktiv"]}
    if v["aktiv"] in tags:
        i = tags.index(v["aktiv"])
        if i + 1 < len(tags):
            geschuetzt.add(tags[i + 1])
    else:
        geschuetzt.update(tags[:1])
    return geschuetzt


class ImagesLoeschenView(APIView):
    """Alte Image-Dateien, Update-Pakete und Docker-Images löschen; laufende und vorherige Version nie."""

    permission_classes = [SystemRecht]

    def post(self, request):
        dateien, tags = request.data.get("dateien") or [], request.data.get("tags") or []
        if not isinstance(dateien, list) or not isinstance(tags, list) or not (dateien or tags) \
                or len(dateien) + len(tags) > 100 \
                or any(not isinstance(d, str) or not host.IMAGE_DATEI_MUSTER.match(d) for d in dateien) \
                or any(not isinstance(t, str) or not host.TAG_MUSTER.match(t) for t in tags) \
                or len(set(dateien)) != len(dateien) or len(set(tags)) != len(tags):
            return _fehler("dateien", "Bitte Dateien bzw. Versionen aus der Liste wählen.")
        antwort = _agent_aktuell()
        if antwort is not None:
            return antwort
        h = host.host_status() or {}
        geschuetzt = geschuetzte_tags(h)
        if geschuetzt is None:
            return Response({"fehler": "Die laufende Version ist nicht bekannt – zur Sicherheit wird nichts gelöscht."},
                            status=status.HTTP_409_CONFLICT)
        betroffen = {host.IMAGE_DATEI_MUSTER.match(d).group(2) for d in dateien} | set(tags)
        if betroffen & geschuetzt:
            return _fehler("dateien", f"Die laufende und die vorherige Version ({', '.join(sorted(geschuetzt))}) bleiben "
                                      "immer – bitte abwählen.")
        vorhanden = {e.get("datei"): e for e in h.get("image_dateien") or [] if isinstance(e, dict)}
        bekannt = {e.get("tag") for e in (h.get("versionen") or {}).get("liste") or [] if isinstance(e, dict)}
        fehlen = [d for d in dateien if d not in vorhanden] + [t for t in tags if t not in bekannt]
        if fehlen:
            return _fehler("dateien", f"Nicht (mehr) vorhanden: {', '.join(fehlen[:5])}.")
        groesse = sum(int(vorhanden[d].get("groesse") or 0) for d in dateien)
        return auftrag_anlegen(request, "images_loeschen", parameter={"dateien": sorted(dateien), "tags": sorted(tags)},
                               objekt="Alte Versionen",
                               protokoll_details={"dateien": sorted(dateien), "tags": sorted(tags), "groesse": groesse})


class UhrView(APIView):
    """Zeitzone, Zeitsynchronisation mit eigenen Zeitservern (abgeschotteter Betrieb: z. B. die OPNsense) oder die
    Uhrzeit von Hand. Passwort und zweiter Faktor: TOTP-Codes, Passkeys und Zertifikate hängen an der Uhrzeit."""

    permission_classes = [SystemRecht]

    def post(self, request):
        d = request.data
        zone, ntp, server, zeit = d.get("zeitzone") or None, d.get("ntp"), d.get("server", []), d.get("zeit") or None
        if not isinstance(ntp, bool):
            return _fehler("ntp", "Bitte Zeitsynchronisation an oder aus wählen.")
        if isinstance(server, str):
            server = server.replace(",", " ").split()
        if not isinstance(server, list) or len(server) > host.NTP_SERVER_MAX \
                or any(not isinstance(s, str) or not host.NTP_SERVER_MUSTER.match(s) for s in server):
            return _fehler("server", f"Bis zu {host.NTP_SERVER_MAX} Zeitserver als Name (z. B. opnsense.stiftung.lan) oder "
                                     "IP-Adresse, durch Leerzeichen getrennt.")
        zonen = ((host.host_status() or {}).get("uhr") or {}).get("zeitzonen") or []
        if zone is not None and (not isinstance(zone, str) or not host.ZEITZONE_MUSTER.match(zone)
                                 or (zonen and zone not in zonen)):
            return _fehler("zeitzone", "Unbekannte Zeitzone.")
        if zeit is not None and (ntp or not isinstance(zeit, str) or not host.ZEIT_SETZEN_MUSTER.match(zeit)):
            return _fehler("zeit", "Die Uhrzeit lässt sich nur bei ausgeschalteter Zeitsynchronisation setzen "
                                   "(JJJJ-MM-TT HH:MM:SS).")
        parameter = {"ntp": ntp, "server": server, **({"zeitzone": zone} if zone else {}), **({"zeit": zeit} if zeit else {})}
        return auftrag_anlegen(request, "uhr_einstellen", parameter=parameter, objekt="Uhrzeit des Servers",
                               protokoll_details=parameter)


# ------------------------------------------------------------------ Notfallpaket und Notfallplan (F188)
class NotfallView(APIView):
    """Notfallpaket erstellen: der Agent packt alles für einen Wiederaufbau ohne Internet in eine Datei. Mit Passwort
    und zweitem Faktor – das Paket enthält auf Wunsch die jüngste Sicherung."""

    permission_classes = [SystemRecht]

    def post(self, request):
        mit_sicherung = request.data.get("mit_sicherung", True)
        if not isinstance(mit_sicherung, bool):
            return _fehler("mit_sicherung", "Bitte ja oder nein.")
        antwort = _agent_aktuell()
        if antwort is not None:
            return antwort
        if not host.ordner_download().is_dir():
            return Response({"fehler": ORDNER_FEHLT}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        n = ((host.host_status() or {}).get("notfall") or {})
        try:
            frei = os.statvfs(host.ordner_download())
            schaetzung = int(n.get("schaetzung") or 0)
            if schaetzung and frei.f_bavail * frei.f_frsize < 2 * schaetzung + 512 * 1024 * 1024:
                return Response({"fehler": f"Zu wenig freier Speicher: nötig etwa {(2 * schaetzung) // 2 ** 20 + 512} MB, "
                                           f"frei {frei.f_bavail * frei.f_frsize // 2 ** 20} MB. Vorher aufräumen "
                                           "(System › Wartung)."}, status=status.HTTP_409_CONFLICT)
        except OSError:
            pass
        return auftrag_anlegen(request, "notfallpaket", parameter={"mit_sicherung": mit_sicherung}, objekt="Notfallpaket",
                               protokoll_details={"mit_sicherung": mit_sicherung})


class NotfallDateiView(APIView):
    """Das bereitgestellte Notfallpaket ausliefern (Nginx per X-Accel-Redirect); jeder Abruf steht im Audit-Log."""

    permission_classes = [SystemRecht]

    def get(self, request, datei):
        m = host.NOTFALL_MUSTER.match(datei or "")
        pfad = host.ordner_download() / datei if m else None
        if pfad is None or not pfad.is_file() or pfad.is_symlink():
            return Response({"fehler": "Dieses Notfallpaket liegt nicht (mehr) zum Herunterladen bereit."},
                            status=status.HTTP_404_NOT_FOUND)
        protokolliere(SystemEreignis.Art.SYSTEM, request, objekt="Notfallpaket", ereignis="notfall_heruntergeladen",
                      datei=datei, groesse=pfad.stat().st_size)
        if settings.EPM_X_ACCEL:
            antwort = HttpResponse(content_type="application/x-tar")
            antwort["X-Accel-Redirect"] = "/_geschuetzt/sicherung/" + datei
        else:
            antwort = FileResponse(open(pfad, "rb"), content_type="application/x-tar")
        antwort["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(datei)}"
        antwort["Cache-Control"] = "private, no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        return antwort


class NotfallplanRecht(SystemRecht):
    """Den Plan lesen dürfen alle mit Systemverwaltung oder „Sicherungen verwalten“."""

    def has_permission(self, request, view):
        from accounts.permissions import voll_angemeldet

        u = request.user
        # wie alle Rechte: nur voll angemeldet (mit zweitem Faktor, wo verlangt)
        return voll_angemeldet(u) and (u.hat_recht("system_verwalten") or u.hat_recht("backup_verwalten"))


class NotfallplanView(APIView):
    permission_classes = [NotfallplanRecht]

    def get(self, request):
        from . import notfallplan

        art = request.query_params.get("art", "html")  # nicht „format“: das wertet DRF selbst aus
        if art == "pdf":
            antwort = HttpResponse(notfallplan.zu_pdf(), content_type="application/pdf")
            antwort["Content-Disposition"] = "inline; filename*=UTF-8''EPM-Notfallplan.pdf"
            return antwort
        if art == "md":
            antwort = HttpResponse(notfallplan.markdown(), content_type="text/markdown; charset=utf-8")
            antwort["Content-Disposition"] = "attachment; filename*=UTF-8''NOTFALLPLAN.md"
            return antwort
        return Response({"html": notfallplan.zu_html()})


# ------------------------------------------------------------------ Technische Verwaltung (Django-Admin, API-Ansicht)
class TechnikView(APIView):
    """GET Stand; PUT ``{"stunden": 0 | 1 | 8}`` – Django-Admin und API-Browseroberfläche für eine begrenzte Zeit
    einschalten bzw. sofort ausschalten (Wunsch 11.10.2026). Jede Änderung steht im Audit-Log."""

    permission_classes = [SystemRecht]

    def _stand(self):
        from epm import technik

        technik.vergessen()
        bis = technik.technik_bis()
        return {"an": technik.geschaltet(), "bis": bis if technik.geschaltet() else None,
                "django_admin": technik.django_admin_an(), "api_ansicht": technik.api_ansicht_an(),
                "fest": {"django_admin": settings.EPM_DJANGO_ADMIN, "api_ansicht": settings.EPM_API_BROWSABLE}}

    def get(self, request):
        return Response(self._stand())

    def put(self, request):
        from datetime import timedelta

        from django.utils import timezone

        from stammdaten.models import Einstellungen

        stunden = request.data.get("stunden")
        if isinstance(stunden, bool) or stunden not in (0, 1, 8):
            return Response({"stunden": "Bitte 0 (aus), 1 oder 8 Stunden wählen."}, status=status.HTTP_400_BAD_REQUEST)
        e = Einstellungen.aktuell()
        e.technik_bis = timezone.now() + timedelta(hours=stunden) if stunden else None
        e._history_user = request.user
        e.save(update_fields=["technik_bis"])
        protokolliere(SystemEreignis.Art.SYSTEM, request, objekt="Technische Verwaltung (Django-Admin, API-Ansicht)",
                      an=bool(stunden), stunden=stunden)
        return Response(self._stand())
