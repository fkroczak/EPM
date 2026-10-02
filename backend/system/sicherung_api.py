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

Passwörter (Sicherungs-Passwort, Zugang zum Ziel) gehen nur in die Auftragsdatei an den Server (0600, der Agent löscht
sie sofort nach dem Lesen) – nie in die Datenbank, das Audit-Log oder eine Antwort. Ausnahme ist das Passwortblatt:
Es druckt das Passwort, das die Oberfläche gerade mitschickt, nachdem es gegen den Prüfwert des Servers geprüft ist.
"""
from urllib.parse import urlsplit

from django.utils import timezone
from rest_framework import status
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
                               protokoll_details={"url": z["url"], "benutzer": z["benutzer"], "ordner": z["ordner"],
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
