"""
Administration › Backup (F61–F64, Recht „Sicherungen verwalten“, Standard: nur Admin).

GET  /api/backup/                                  Sicherungen, Verschlüsselung, Ziel, Übertragung, Speicher, Aufträge
POST /api/backup/jetzt/                            Sicherung jetzt erstellen (Auftrag an den Server)
POST /api/backup/passwort/                         {passwort, passwort2, kennwort, code} → neues Sicherungs-Passwort
POST /api/backup/passwort/pruefen/                 {passwort} → passt es zu einem hinterlegten Passwort?
POST /api/backup/passwortblatt/                    {passwort} → Passwortblatt als PDF (nur mit dem richtigen Passwort)
POST /api/backup/ziel/                             {url, benutzer, ziel_kennwort?, ordner, von, bis, kennwort, code}
POST /api/backup/ziel/entfernen/                   {kennwort, code}
POST /api/backup/ziel/testen/                      Verbindung zum Ziel testen
POST /api/backup/uebertragen/                      noch nicht übertragene Sicherungen jetzt übertragen
POST /api/backup/<stempel>/wiederherstellen/       {kennwort, code, minuten, hinweis?}
POST /api/backup/auftraege/<kennung>/abbrechen/    wartenden Auftrag zurückziehen
POST /api/backup/aufbewahrung/                     {tage: 7 | 14 | 30, kennwort, code}
POST /api/backup/<stempel>/bereitstellen/          {kennwort, code} → Sicherung für 2 Stunden zum Herunterladen bereitlegen
GET  /api/backup/<stempel>/datei/                  die bereitgestellte Sicherung (epm-sicherung_<Stempel>.tar)
POST /api/backup/hochladen/                        {name, groesse} → {upload, teil}: Hochladen einer Sicherung beginnen
PUT  /api/backup/hochladen/<upload>/?versatz=N     nächstes Stück (application/octet-stream, höchstens „teil“ Bytes)
DELETE /api/backup/hochladen/<upload>/             hochgeladene Datei verwerfen
POST /api/backup/hochladen/<upload>/einlesen/      {passwort?} → der Server prüft die Sicherung und nimmt sie in die Liste

Der zweite Faktor ist freiwillig (Festlegung 02.10.2026): „code“ wird nur geprüft, wenn die Person einen eingerichtet hat.

Passwörter (Sicherungs-Passwort, Zugang zum Ziel) gehen nur in die Auftragsdatei an den Server (0600, der Agent löscht
sie sofort nach dem Lesen) – nie in die Datenbank, das Audit-Log oder eine Antwort. Ausnahme ist das Passwortblatt:
Es druckt das Passwort, das die Oberfläche gerade mitschickt, nachdem es gegen den Prüfwert des Servers geprüft ist.
"""
import json
import os
import uuid
from urllib.parse import quote, urlsplit

from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import BaseParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import nur_recht
from audit.models import SystemEreignis, protokolliere

from . import epm_aufgaben, host, sicherung
from .api import MINUTEN_ERLAUBT, AuftragSerializer, auftraege_abgleichen, auftrag_anlegen, auftrag_zurueckziehen
from .models import Systemauftrag

BackupRecht = nur_recht("backup_verwalten")
STEUERZEICHEN = {chr(i) for i in range(32)} | {"\x7f"}


def _fehler(feld, text, code=status.HTTP_400_BAD_REQUEST):
    return Response({feld: text}, status=code)


def _zeitpunkt_text(text):
    z = host._zeit(text)
    if z is None:
        return str(text or "")
    if timezone.is_naive(z):
        z = timezone.make_aware(z)
    return f"{timezone.localtime(z):%d.%m.%Y %H:%M}"


def _sicherung_daten(s: dict) -> dict:
    wiederherstellbar = bool(s.get("dokumente")) and s.get("verfahren") != "age"
    return {**s, "art_name": sicherung.ARTEN.get(s.get("art"), "Unbekannt"), "uebertragen": bool(s.get("uebertragen_am")),
            "wiederherstellbar": wiederherstellbar,
            "nicht_wiederherstellbar_weil": "" if wiederherstellbar else (
                "mit öffentlichem Schlüssel (age) verschlüsselt – nur von Hand" if s.get("verfahren") == "age"
                else "ohne Dokumente")}


class UebersichtView(APIView):
    permission_classes = [BackupRecht]

    def get(self, request):
        auftraege_abgleichen()
        sicherung.wiederherstellungen_nachtragen()
        kurz, daten = sicherung.kurzstatus(mit_daten=True)
        d = daten or {}
        platz = (d.get("speicher") or {}).get("platz") or {}
        liste = [_sicherung_daten(s) for s in sicherung.sicherungen(daten)]
        host_status = host.host_status() or {}
        eigene = request.session.session_key if getattr(request, "session", None) else None
        andere = sorted({s.benutzer.anzeigename for s in epm_aufgaben.angemeldete_sitzungen()
                         if s.sitzungsschluessel != eigene})
        return Response({
            "agent": {"verzeichnis": host.ordner_auftraege().is_dir(), "erreichbar": host.agent_erreichbar()},
            "status": {"vorhanden": daten is not None, "aktuell": bool(d.get("aktuell")), "zeit": d.get("zeit"),
                       "alter_s": d.get("alter_s")},
            "probelauf": bool(host_status.get("trocken")),
            "kurz": kurz,
            "letzte": liste[0] if liste else None,
            "sicherungen": liste,
            "verschluesselung": d.get("verschluesselung") or {"eingerichtet": False, "aktuell": None, "versionen": [],
                                                               "verfahren": ""},
            "ziel": d.get("ziel") or {"eingerichtet": False},
            "uebertragung": d.get("uebertragung") or {},
            "speicher": {"sicherungen": (d.get("speicher") or {}).get("sicherungen"), "gesamt": platz.get("gesamt"),
                         "frei": platz.get("frei"),
                         "belegt": platz["gesamt"] - platz["frei"] if platz.get("gesamt") is not None
                         and platz.get("frei") is not None else None},
            "aufbewahrung_tage": d.get("aufbewahrung_tage"),
            "aufbewahrung_auswahl": list(sicherung.AUFBEWAHRUNG_TAGE),
            # Herunterladen und Hochladen (Fehlerliste 02.10.2026, 5.1 und 5.3)
            "austausch": host.ordner_download().is_dir() and host.ordner_upload().is_dir(),
            "bereitgestellt": sicherung.bereitgestellt(daten),
            "uploads": sicherung.uploads(),
            "upload": {"teil": sicherung.UPLOAD_TEIL, "max": sicherung.UPLOAD_MAX},
            "naechste_sicherung": d.get("naechste_sicherung"),
            "nachts_fehlgeschlagen": bool(d.get("nachts_fehlgeschlagen")),
            "gpg": d.get("gpg"),
            "wiederherstellungen": d.get("wiederherstellungen") or [],
            "auftraege": AuftragSerializer(
                Systemauftrag.objects.filter(ziel=Systemauftrag.Ziel.SERVER, aktion__in=host.SICHERUNG_AKTIONEN)
                .select_related("angefordert_von")[:20], many=True).data,
            "aktionen": {code: {k: v for k, v in host.AKTIONEN[code].items() if k not in ("intern", "recht")}
                         for code in host.SICHERUNG_AKTIONEN},
            "minuten": MINUTEN_ERLAUBT,
            "angemeldet": andere,
            "passwort": {"min": sicherung.PASSWORT_MIN, "max": sicherung.PASSWORT_MAX},
        })


class JetztView(APIView):
    permission_classes = [BackupRecht]

    def post(self, request):
        return auftrag_anlegen(request, "sicherung")


class PasswortView(APIView):
    """Neues Sicherungs-Passwort (Festlegung 02.10.2026: symmetrisch, in der Oberfläche festgelegt). Es gilt ab der
    nächsten Sicherung; ältere Sicherungen bleiben mit ihrem Passwort lesbar, solange es sie gibt (30 Tage)."""

    permission_classes = [BackupRecht]

    def post(self, request):
        passwort = request.data.get("passwort")
        passwort2 = request.data.get("passwort2")
        if not isinstance(passwort, str) or not (sicherung.PASSWORT_MIN <= len(passwort) <= sicherung.PASSWORT_MAX):
            return _fehler("passwort", f"Das Passwort muss {sicherung.PASSWORT_MIN} bis {sicherung.PASSWORT_MAX} "
                                       "Zeichen lang sein.")
        if any(z in STEUERZEICHEN for z in passwort):
            return _fehler("passwort", "Das Passwort darf keine Zeilenumbrüche oder Steuerzeichen enthalten.")
        if passwort.strip() != passwort:
            return _fehler("passwort", "Das Passwort darf nicht mit einem Leerzeichen beginnen oder enden.")
        if passwort2 != passwort:
            return _fehler("passwort2", "Die beiden Eingaben stimmen nicht überein.")
        if request.user.check_password(passwort):
            return _fehler("passwort", "Bitte nicht das eigene Anmelde-Passwort verwenden.")
        if sicherung.passwort_nr(passwort) is not None:
            return _fehler("passwort", "Dieses Passwort ist schon hinterlegt. Bitte ein neues wählen.")
        return auftrag_anlegen(request, "sicherung_passwort", geheim={"passwort": passwort},
                               objekt="Sicherungs-Passwort")


def _passwort_geprueft(request):
    """Gemeinsam für Prüfen und Passwortblatt: (nr | None, Fehlerantwort | None). Jeder Versuch steht im Audit-Log;
    nach 5 falschen Passwörtern in 15 Minuten ist die Prüfung für diese Person kurz gesperrt."""
    if sicherung.pruefung_gesperrt(request.user):
        return None, Response({"fehler": f"Zu viele falsche Passwörter. Bitte in {sicherung.PRUEF_MINUTEN} Minuten "
                                         "erneut versuchen."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    passwort = request.data.get("passwort")
    nr = sicherung.passwort_nr(passwort) if isinstance(passwort, str) else None
    if nr is None:
        protokolliere(SystemEreignis.Art.BACKUP, request, objekt="Sicherungs-Passwort", ereignis="passwort_falsch")
    return nr, None


class PasswortPruefenView(APIView):
    permission_classes = [BackupRecht]

    def post(self, request):
        nr, antwort = _passwort_geprueft(request)
        if antwort is not None:
            return antwort
        aktuell = ((sicherung.status() or {}).get("verschluesselung") or {}).get("aktuell")
        if nr is not None:
            protokolliere(SystemEreignis.Art.BACKUP, request, objekt="Sicherungs-Passwort", ereignis="passwort_geprueft",
                          nr=nr)
        return Response({"stimmt": nr is not None, "nr": nr, "aktuell": nr is not None and nr == aktuell})


class PasswortblattView(APIView):
    permission_classes = [BackupRecht]

    def post(self, request):
        from vorlagen.api import pdf_antwort
        from vorlagen.listen import sicherungs_passwortblatt_pdf

        nr, antwort = _passwort_geprueft(request)
        if antwort is not None:
            return antwort
        if nr is None:
            return _fehler("passwort", "Das Passwort passt zu keinem Sicherungs-Passwort auf dem Server.")
        daten = sicherung.status() or {}
        versl = daten.get("verschluesselung") or {}
        version = next((v for v in versl.get("versionen") or [] if v.get("nr") == nr), {})
        pdf = sicherungs_passwortblatt_pdf(
            passwort=request.data["passwort"], nr=nr, aktuell=nr == versl.get("aktuell"),
            gesetzt_am=_zeitpunkt_text(version.get("gesetzt_am")), gesetzt_von=version.get("gesetzt_von") or "",
            verfahren=versl.get("verfahren") or "", adresse=f"https://{request.get_host()}/",
            aufbewahrung_tage=daten.get("aufbewahrung_tage") or 30,
            versionen=[{**v, "gesetzt_am": _zeitpunkt_text(v.get("gesetzt_am"))} for v in versl.get("versionen") or []
                       if not v.get("entfernt_am")])
        protokolliere(SystemEreignis.Art.BACKUP, request, objekt="Sicherungs-Passwort", ereignis="passwortblatt", nr=nr)
        return pdf_antwort(pdf, f"EPM-Sicherungspasswort-Nr-{nr}.pdf")


def ziel_pruefen(daten, neu: bool):
    """Dieselben Regeln wie im Systemagenten (der prüft noch einmal). Rückgabe: (Fehler | None, Angaben)."""
    url = str(daten.get("url") or "").strip()
    teile = urlsplit(url)
    lokal = teile.hostname in ("localhost", "127.0.0.1", "::1")
    if teile.scheme not in ("https", "http") or not teile.hostname or (teile.scheme == "http" and not lokal) \
            or teile.username or teile.password or teile.query or teile.fragment or len(url) > 500 \
            or any(z in url for z in " \r\n\t\"'\\"):
        return {"url": "Bitte die WebDAV-Adresse mit https:// angeben (ohne Benutzer und Passwort in der Adresse)."}, None
    benutzer = str(daten.get("benutzer") or "").strip()
    if not benutzer or len(benutzer) > 200 or any(z in STEUERZEICHEN for z in benutzer):
        return {"benutzer": "Bitte den Benutzernamen angeben."}, None
    ordner = str(daten.get("ordner") or "").strip().strip("/")
    if len(ordner) > 300 or any(z in ordner for z in "\\:") or any(z in STEUERZEICHEN for z in ordner) \
            or ".." in ordner.split("/"):
        return {"ordner": "Der Ordner darf keine Sonderzeichen wie \\ : .. enthalten."}, None
    werte = {}
    for feld in ("von", "bis"):
        werte[feld] = str(daten.get(feld) or "")
        if not sicherung.ZEIT_MUSTER.match(werte[feld]):
            return {feld: "Bitte als Uhrzeit angeben, z. B. 02:00."}, None
    kennwort = daten.get("ziel_kennwort")
    if kennwort in ("", None):
        kennwort = None
        if neu:
            return {"ziel_kennwort": "Bitte das Passwort für das Ziel angeben (z. B. ein App-Passwort der Nextcloud)."}, None
    elif not isinstance(kennwort, str) or len(kennwort) > 500 or any(z in "\r\n\0" for z in kennwort):
        return {"ziel_kennwort": "Das Passwort für das Ziel ist ungültig."}, None
    return None, {"url": url.rstrip("/"), "benutzer": benutzer, "ordner": ordner, **werte, "kennwort": kennwort}


class ZielView(APIView):
    permission_classes = [BackupRecht]

    def post(self, request):
        bisher = ((sicherung.status() or {}).get("ziel") or {}).get("eingerichtet")
        fehler, z = ziel_pruefen(request.data, neu=not bisher)
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        kennwort = z.pop("kennwort")
        return auftrag_anlegen(request, "sicherung_ziel", parameter=z,
                               geheim={"kennwort": kennwort} if kennwort else None,
                               objekt=f"Übertragungsziel {urlsplit(z['url']).hostname}",
                               # „benutzer“ hieße in protokolliere() die handelnde Person – daher ziel_benutzer
                               protokoll_details={"url": z["url"], "ziel_benutzer": z["benutzer"], "ordner": z["ordner"],
                                                  "zeitfenster": f"{z['von']}–{z['bis']}",
                                                  "zugang_neu": kennwort is not None})


class ZielEntfernenView(APIView):
    permission_classes = [BackupRecht]

    def post(self, request):
        return auftrag_anlegen(request, "sicherung_ziel_entfernen")


class ZielTestenView(APIView):
    permission_classes = [BackupRecht]

    def post(self, request):
        return auftrag_anlegen(request, "sicherung_ziel_testen")


class UebertragenView(APIView):
    permission_classes = [BackupRecht]

    def post(self, request):
        return auftrag_anlegen(request, "sicherung_uebertragen")


class WiederherstellenView(APIView):
    """F63: Ersetzt Datenbank und Dokumente durch den Stand der Sicherung – mit Admin-Passwort und 2FA, vorher eine
    Sicherung des jetzigen Stands, Warnung an alle Angemeldeten; die Löschliste bleibt (Art. 17 DSGVO)."""

    permission_classes = [BackupRecht]

    def post(self, request, stempel):
        daten = sicherung.status()
        if daten is None or not daten.get("aktuell"):
            # ein Auftrag, der wartet, bis der Agent wieder läuft, würde zu einem unerwarteten Zeitpunkt zurückspielen
            return Response({"fehler": "Der Systemagent auf dem Server meldet sich gerade nicht. Wiederherstellen ist "
                                       "erst möglich, wenn er wieder läuft."}, status=status.HTTP_409_CONFLICT)
        s = sicherung.finde(stempel, daten)
        if s is None:
            return Response({"fehler": "Diese Sicherung gibt es auf dem Server nicht (mehr)."},
                            status=status.HTTP_404_NOT_FOUND)
        s = _sicherung_daten(s)
        if not s["wiederherstellbar"]:
            return Response({"fehler": f"Diese Sicherung lässt sich hier nicht zurückspielen "
                                       f"({s['nicht_wiederherstellbar_weil']})."}, status=status.HTTP_409_CONFLICT)
        zeit = _zeitpunkt_text(s.get("zeitpunkt"))
        return auftrag_anlegen(request, "wiederherstellen",
                               parameter={"stempel": s["stempel"], "sicherung_zeitpunkt": s.get("zeitpunkt")},
                               objekt=f"Sicherung vom {zeit}",
                               protokoll_details={"stempel": s["stempel"], "sicherung_zeitpunkt": s.get("zeitpunkt")})


class AuftragAbbrechenView(APIView):
    permission_classes = [BackupRecht]

    def post(self, request, kennung):
        auftrag = Systemauftrag.objects.filter(kennung=kennung, ziel=Systemauftrag.Ziel.SERVER,
                                               aktion__in=host.SICHERUNG_AKTIONEN).first()
        return auftrag_zurueckziehen(request, auftrag)


class AufbewahrungView(APIView):
    """Wie lange Sicherungen auf dem Server bleiben (Fehlerliste 02.10.2026, 5.2): 7, 14 oder 30 Tage. Ältere
    entfernt die nächste Sicherung; im Übertragungsziel wird nie gelöscht."""

    permission_classes = [BackupRecht]

    def post(self, request):
        tage = request.data.get("tage")
        if isinstance(tage, bool) or tage not in sicherung.AUFBEWAHRUNG_TAGE:
            return _fehler("tage", "Bitte 7, 14 oder 30 Tage wählen.")
        return auftrag_anlegen(request, "sicherung_aufbewahrung", parameter={"tage": tage},
                               objekt="Aufbewahrung der Sicherungen", protokoll_details={"tage": tage})


AUSTAUSCH_FEHLT = ("Die Ordner für das Herunter- und Hochladen von Sicherungen fehlen. Bitte auf dem Server einmal "
                   "„sudo epm-update“ (bzw. rollout/04-projekt.sh) ausführen.")


class BereitstellenView(APIView):
    """5.1: Sicherung herunterladen. Der Server legt sie als eine Datei für 2 Stunden bereit (Auftrag an den
    Systemagenten, mit Passwort und zweitem Faktor bestätigt); danach GET …/datei/."""

    permission_classes = [BackupRecht]

    def post(self, request, stempel):
        if not host.ordner_download().is_dir():
            return Response({"fehler": AUSTAUSCH_FEHLT}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        s = sicherung.finde(stempel)
        if s is None:
            return Response({"fehler": "Diese Sicherung gibt es auf dem Server nicht (mehr)."},
                            status=status.HTTP_404_NOT_FOUND)
        return auftrag_anlegen(request, "sicherung_bereitstellen", parameter={"stempel": s["stempel"]},
                               objekt=f"Sicherung vom {_zeitpunkt_text(s.get('zeitpunkt'))}",
                               protokoll_details={"stempel": s["stempel"], "sicherung_zeitpunkt": s.get("zeitpunkt"),
                                                  "verschluesselt": bool(s.get("verschluesselt"))})


class DateiView(APIView):
    """Die bereitgestellte Sicherung ausliefern (Nginx per X-Accel-Redirect); jeder Abruf steht im Audit-Log."""

    permission_classes = [BackupRecht]

    def get(self, request, stempel):
        if not sicherung.STEMPEL_MUSTER.match(stempel):
            return Response({"fehler": "Unbekannte Sicherung."}, status=status.HTTP_404_NOT_FOUND)
        name = sicherung.buendel_name(stempel)
        pfad = host.ordner_download() / name
        if not pfad.is_file():
            return Response({"fehler": "Diese Sicherung liegt nicht (mehr) zum Herunterladen bereit. Bitte erneut "
                                       "„Herunterladen“ wählen."}, status=status.HTTP_404_NOT_FOUND)
        s = sicherung.finde(stempel) or {}
        protokolliere(SystemEreignis.Art.BACKUP, request, objekt=f"Sicherung {stempel}", ereignis="heruntergeladen",
                      stempel=stempel, sicherung_zeitpunkt=s.get("zeitpunkt"), groesse=pfad.stat().st_size,
                      verschluesselt=bool(s.get("verschluesselt")))
        if settings.EPM_X_ACCEL:
            antwort = HttpResponse(content_type="application/x-tar")
            antwort["X-Accel-Redirect"] = "/_geschuetzt/sicherung/" + name
        else:
            antwort = FileResponse(open(pfad, "rb"), content_type="application/x-tar")
        antwort["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
        antwort["Cache-Control"] = "private, no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        return antwort


class RohParser(BaseParser):
    """Ein Stück der hochgeladenen Datei, unverändert (höchstens ``UPLOAD_TEIL`` Bytes je Anfrage)."""

    media_type = "application/octet-stream"

    def parse(self, stream, media_type=None, parser_context=None):
        return stream.read(sicherung.UPLOAD_TEIL + 1)


def _upload(kennung):
    """(Pfad der Datei, Angaben) eines begonnenen Uploads oder (None, None)."""
    if not sicherung.ID_MUSTER.match(kennung or ""):
        return None, None
    ordner = host.ordner_upload()
    meta = host._lies(ordner / f"{kennung}.json")
    pfad = ordner / f"{kennung}.teil"
    if not isinstance(meta, dict) or not pfad.is_file() or pfad.is_symlink():
        return None, None
    return pfad, meta


class HochladenView(APIView):
    """5.3: Sicherung hochladen – in Stücken, damit auch große Dateien (Dokumente!) sicher ankommen und der Fortschritt
    sichtbar ist. Die Datei landet in einem eigenen Ordner; erst „einlesen“ prüft sie auf dem Server und nimmt sie
    in die Liste der Sicherungen auf. Zurückgespielt wird nur mit „Wiederherstellen“ (eigene Bestätigung)."""

    permission_classes = [BackupRecht]

    def post(self, request):
        ordner = host.ordner_upload()
        if not ordner.is_dir():
            return Response({"fehler": AUSTAUSCH_FEHLT}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        name = os.path.basename(str(request.data.get("name") or "").replace("\\", "/"))[:200]
        groesse = request.data.get("groesse")
        if not name.lower().endswith(".tar") or any(z in STEUERZEICHEN for z in name):
            return _fehler("name", "Bitte die Datei wählen, die „Herunterladen“ geliefert hat "
                                   "(epm-sicherung_<Zeitpunkt>.tar).")
        if isinstance(groesse, bool) or not isinstance(groesse, int) or not (0 < groesse <= sicherung.UPLOAD_MAX):
            return _fehler("groesse", "Die Datei ist leer oder zu groß.")
        try:
            frei = os.statvfs(ordner)
            # Platz für die hochgeladene Datei und für das Auspacken in den Backup-Ordner
            if frei.f_bavail * frei.f_frsize < 2 * groesse + 64 * 1024 * 1024:
                return _fehler("groesse", "Auf dem Server ist dafür zu wenig Speicher frei.")
        except OSError:
            pass
        kennung = uuid.uuid4().hex
        try:
            fd = os.open(ordner / f"{kennung}.teil", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
            os.close(fd)
            with open(ordner / f"{kennung}.json", "w", encoding="utf-8") as f:
                json.dump({"name": name, "groesse": groesse, "von": request.user.get_username(),
                           "begonnen_am": timezone.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)
        except OSError as e:
            return Response({"fehler": f"Die Datei konnte nicht angelegt werden ({e.strerror}). Rechte des Ordners für "
                                       "hochgeladene Sicherungen prüfen."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        protokolliere(SystemEreignis.Art.BACKUP, request, objekt="Sicherung hochladen", ereignis="upload_begonnen",
                      datei=name, groesse=groesse, upload=kennung)
        return Response({"upload": kennung, "teil": sicherung.UPLOAD_TEIL, "erhalten": 0, "groesse": groesse},
                        status=status.HTTP_201_CREATED)


class HochladenTeilView(APIView):
    permission_classes = [BackupRecht]
    parser_classes = [RohParser, JSONParser]

    def put(self, request, kennung):
        pfad, meta = _upload(kennung)
        if pfad is None:
            return Response({"fehler": "Dieser Upload ist nicht (mehr) bekannt. Bitte neu beginnen."},
                            status=status.HTTP_404_NOT_FOUND)
        daten = request.data
        if not isinstance(daten, (bytes, bytearray)) or not daten:
            return _fehler("fehler", "Erwartet wird ein Stück der Datei (application/octet-stream).")
        if len(daten) > sicherung.UPLOAD_TEIL:
            return _fehler("fehler", "Das Stück ist zu groß.", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        erhalten = pfad.stat().st_size
        try:
            versatz = int(request.query_params.get("versatz", ""))
        except ValueError:
            versatz = -1
        if versatz != erhalten:
            # z. B. nach einer unterbrochenen Verbindung: Die Oberfläche setzt an der gemeldeten Stelle fort
            return Response({"fehler": "Das Stück passt nicht an das bisher Empfangene.", "erhalten": erhalten},
                            status=status.HTTP_409_CONFLICT)
        if erhalten + len(daten) > meta.get("groesse", 0):
            return _fehler("fehler", "Es kommt mehr an, als angekündigt wurde.")
        with open(pfad, "ab") as f:
            f.write(daten)
        return Response({"erhalten": erhalten + len(daten), "groesse": meta.get("groesse")})

    def delete(self, request, kennung):
        pfad, meta = _upload(kennung)
        if pfad is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if Systemauftrag.objects.filter(ziel=Systemauftrag.Ziel.SERVER, aktion="sicherung_einlesen",
                                        parameter__upload=kennung,
                                        status__in=[Systemauftrag.Status.WARTET, Systemauftrag.Status.LAEUFT]).exists():
            return Response({"fehler": "Der Server liest diese Datei gerade ein."}, status=status.HTTP_409_CONFLICT)
        for datei in (pfad, pfad.with_suffix(".json")):
            try:
                os.unlink(datei)
            except OSError:
                pass
        protokolliere(SystemEreignis.Art.BACKUP, request, objekt="Sicherung hochladen", ereignis="upload_abgebrochen",
                      datei=str(meta.get("name") or ""), upload=kennung)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EinlesenView(APIView):
    """Vollständig hochgeladene Sicherung einlesen (Auftrag an den Systemagenten). ``passwort``: das Passwort der
    Sicherung, falls sie mit einem verschlüsselt ist, das dieser Server nicht kennt (Sicherung eines anderen
    EPM-Servers) – es geht nur in die Auftragsdatei, nie in die Datenbank oder das Audit-Log."""

    permission_classes = [BackupRecht]

    def post(self, request, kennung):
        pfad, meta = _upload(kennung)
        if pfad is None:
            return Response({"fehler": "Dieser Upload ist nicht (mehr) bekannt. Bitte neu beginnen."},
                            status=status.HTTP_404_NOT_FOUND)
        erhalten = pfad.stat().st_size
        if erhalten != meta.get("groesse"):
            return Response({"fehler": "Die Datei ist noch nicht vollständig hochgeladen.", "erhalten": erhalten},
                            status=status.HTTP_409_CONFLICT)
        passwort = request.data.get("passwort")
        if passwort in ("", None):
            passwort = None
        elif not isinstance(passwort, str) or len(passwort) > sicherung.PASSWORT_MAX \
                or any(z in STEUERZEICHEN for z in passwort):
            return _fehler("passwort", "Das Passwort der Sicherung ist ungültig.")
        name = str(meta.get("name") or "")
        return auftrag_anlegen(request, "sicherung_einlesen", parameter={"upload": kennung, "datei": name},
                               geheim={"passwort": passwort} if passwort else None,
                               objekt=f"Sicherung {name}"[:200],
                               protokoll_details={"datei": name, "groesse": erhalten, "mit_passwort": passwort is not None})
