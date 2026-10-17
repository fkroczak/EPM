"""
Administration › System (nur mit Recht „Systemverwaltung“, Standard: nur Admin).

GET    /api/system/uebersicht/                 Auslastung (Server bzw. Container), EPM, Anmeldungen, Aktionen
GET    /api/system/verlauf/?zeitraum=24h       Auslastung (vom Systemagenten): 1h, 3h, 24h, 7t, 14t, 1m, 6m
GET    /api/system/auftraege/                  letzte Aufträge (Ergebnisse des Servers werden vorher übernommen)
POST   /api/system/auftraege/                  {aktion, kennwort?, code?, minuten?, hinweis?} → Auftrag an den Server
POST   /api/system/auftraege/<kennung>/abbrechen/   wartenden Auftrag zurückziehen
POST   /api/system/epm/                        {aufgabe, pruefsummen?} → Wartung des EPM, sofort ausgeführt
GET    /api/system/hinweis/                    aktiver Hinweis an alle Benutzer (jeder Angemeldete)
POST   /api/system/hinweis/                    {text, art, minuten?} → Hinweis an alle Benutzer
DELETE /api/system/hinweis/                    Hinweis beenden
DELETE /api/system/sitzungen/<id>/             Anmeldung eines Benutzers beenden
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import zweifaktor
from accounts.permissions import SystemRecht, recht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import benutzername

from . import epm_aufgaben, hochladen, host
from .models import Systemauftrag, Systemhinweis

MINUTEN_ERLAUBT = (0, 5, 10, 15, 30, 60)
# Aufträge der Wartung ohne SSH (F179, system/verwaltung_api.py) – eigene Endpunkte, eigene Bereiche der Seite
VERWALTUNG_AKTIONEN = ("dienst_neustart", "epm_zurueck", "epm_paket", "epm_paket_erstellen", "zertifikat_erneuern",
                       "zertifikat_importieren", "ocr_modelle", "protokoll", "journal_aufraeumen", "images_loeschen",
                       "uhr_einstellen", "notfallpaket",
                       # Zugang (11.10.2026)
                       "ssh_oeffnen", "ssh_schliessen", "netz_hinzufuegen", "netz_entfernen", "https_filter",
                       "fail2ban_entsperren",
                       # Selbstheilung (13.10.2026)
                       "version_bestaetigen", "heilung_schalten",
                       # Signatur der Update-Pakete (17.10.2026)
                       "paket_schluessel_zuruecksetzen", "paket_schluessel_behalten")
# so lange bleibt die Warnung nach dem Beginn stehen (falls der Auftrag sie nicht vorher beendet)
WARNUNG_NACHLAUF = {"updates_installieren": 60, "server_neustart": 15, "epm_neustart": 5, "wiederherstellen": 30,
                    "dienst_neustart": 5, "epm_zurueck": 15, "epm_paket": 30}


def protokoll_art(aktion: str):
    """Aufträge rund um die Sicherungen stehen im Audit-Log unter „Backup“, alle anderen unter „System“."""
    return SystemEreignis.Art.BACKUP if aktion in host.SICHERUNG_AKTIONEN else SystemEreignis.Art.SYSTEM


def _name(a: Systemauftrag) -> str:
    katalog = host.AKTIONEN if a.ziel == Systemauftrag.Ziel.SERVER else epm_aufgaben.AUFGABEN
    return katalog.get(a.aktion, {}).get("name", a.aktion)


class AuftragSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    angefordert_von_name = serializers.SerializerMethodField()
    offen = serializers.BooleanField(read_only=True)

    class Meta:
        model = Systemauftrag
        fields = ["id", "kennung", "ziel", "aktion", "name", "status", "status_name", "offen", "parameter",
                  "angefordert_von_name", "angefordert_am", "begonnen_am", "beendet_am", "ergebnis", "ausgabe",
                  "rueckgabe", "probelauf"]

    def get_name(self, obj):
        return _name(obj)

    def get_angefordert_von_name(self, obj):
        return benutzername(obj.angefordert_von)


def hinweis_daten(h: Systemhinweis | None):
    if h is None:
        return None
    return {"id": h.id, "text": h.text, "art": h.art, "gueltig_bis": h.gueltig_bis, "angelegt_am": h.angelegt_am,
            "angelegt_von_name": benutzername(h.angelegt_von), "auftrag": h.auftrag_id}


def hinweis_beenden(h: Systemhinweis, user=None, request=None):
    h.beendet_am = timezone.now()
    h.beendet_von = user
    h.save(update_fields=["beendet_am", "beendet_von"])
    if request is not None:
        protokolliere(SystemEreignis.Art.SYSTEM, request, objekt="Hinweis an alle Benutzer",
                      ereignis="hinweis_beendet", text=h.text)


def auftraege_abgleichen():
    """Ergebnisse des Systemagenten übernehmen; abgeschlossene Aufträge ins Audit-Log, ihre Warnung beenden."""
    offene = list(Systemauftrag.objects.filter(ziel=Systemauftrag.Ziel.SERVER,
                                               status__in=[Systemauftrag.Status.WARTET, Systemauftrag.Status.LAEUFT])
                  .select_related("angefordert_von"))
    for a in host.abgleichen(offene):
        protokolliere(protokoll_art(a.aktion), benutzer=a.angefordert_von, objekt=_name(a), ereignis="abgeschlossen",
                      aktion=a.aktion, name=_name(a), status=a.status, ergebnis=a.ergebnis, probelauf=a.probelauf)
        if a.aktion != "server_neustart" or a.status == Systemauftrag.Status.FEHLER:
            for h in Systemhinweis.objects.filter(auftrag=a, beendet_am__isnull=True):
                hinweis_beenden(h)


def zugang_ereignisse_uebernehmen(status_host=None):
    """Vom Server selbst ausgeführtes (SSH nach Ablauf der Zeit geschlossen, 11.10.2026) ins Audit-Log – jedes Ereignis
    einmal, erkannt an seiner Kennung."""
    zugang = ((status_host if status_host is not None else host.host_status()) or {}).get("zugang") or {}
    for e in zugang.get("ereignisse") or []:
        kennung = e.get("id") if isinstance(e, dict) else None
        if not isinstance(kennung, str) or not kennung.isalnum() or len(kennung) > 32:
            continue
        if SystemEreignis.objects.filter(art=SystemEreignis.Art.SYSTEM, details__ereignis="ssh_automatisch",
                                         details__kennung=kennung).exists():
            continue
        protokolliere(SystemEreignis.Art.SYSTEM, benutzername="systemagent", objekt="SSH", ereignis="ssh_automatisch",
                      kennung=kennung, ok=bool(e.get("ok")), bis=str(e.get("bis") or "")[:40],
                      zeit=str(e.get("zeit") or "")[:40], ergebnis=str(e.get("text") or "")[:300])


def _hinweis_vom_server(text, stunden=None):
    """Hinweis an alle Benutzer, den der Server selbst auslöst (ohne anlegenden Benutzer); ein aktiver Hinweis eines
    Admins bleibt – der Server drängt sich nicht vor."""
    if Systemhinweis.aktiv() is not None:
        return None
    return Systemhinweis.objects.create(text=text[:500], art=Systemhinweis.Art.WARNUNG, angelegt_von=None,
                                        gueltig_bis=timezone.now() + timedelta(hours=stunden) if stunden else None)


PAKET_HINWEIS = "Sicherheit: Der Schlüssel für Update-Pakete wird zurückgesetzt"


def paket_schluessel_uebernehmen(status_host=None):
    """Signatur der Update-Pakete (17.10.2026): Ereignisse des Agenten (Schlüssel erstmals übernommen, nach 24 Stunden
    zurückgesetzt) einmal ins Audit-Log; solange ein Zurücksetzen beantragt ist, ein Hinweis an alle Benutzer – er
    endet, sobald der Agent keinen Antrag mehr meldet (abgebrochen oder ausgeführt)."""
    s = ((status_host if status_host is not None else host.host_status()) or {}).get("paket_schluessel")
    if not isinstance(s, dict):
        return
    texte = {"uebernommen": "Paket-Schlüssel erstmals übernommen", "zurueckgesetzt": "Paket-Schlüssel zurückgesetzt"}
    for e in s.get("ereignisse") or []:
        kennung = e.get("id") if isinstance(e, dict) else None
        if e.get("art") not in texte or not isinstance(kennung, str) or not kennung.isalnum() or len(kennung) > 32:
            continue
        if SystemEreignis.objects.filter(art=SystemEreignis.Art.SYSTEM, details__ereignis="paket_schluessel",
                                         details__kennung=kennung).exists():
            continue
        fp = str(e.get("fingerabdruck") or "")[:80]
        protokolliere(SystemEreignis.Art.SYSTEM, benutzername="systemagent", objekt=f"{texte[e['art']]}: {fp}"[:200],
                      ereignis="paket_schluessel", kennung=kennung, schluessel_art=e["art"], fingerabdruck=fp,
                      zeit=str(e.get("zeit") or "")[:40], von=str(e.get("von") or "")[:150])
    antrag = s.get("zuruecksetzen")
    aktiv = Systemhinweis.aktiv()
    if isinstance(antrag, dict):
        ab = _zeit_lesen(antrag.get("wirksam_ab"))
        if aktiv is None and ab is not None and ab > timezone.now():
            Systemhinweis.objects.create(
                text=(f"{PAKET_HINWEIS} – wirksam ab {timezone.localtime(ab):%d.%m.%Y %H:%M} Uhr. Wurde das nicht aus der "
                      f"Administration beantragt: sofort unter Administration › System › Software abbrechen.")[:500],
                art=Systemhinweis.Art.WARNUNG, angelegt_von=None, gueltig_bis=ab)
    elif aktiv is not None and aktiv.text.startswith(PAKET_HINWEIS):
        hinweis_beenden(aktiv)


def _zeit_lesen(text):
    from django.utils.dateparse import parse_datetime
    try:
        return parse_datetime(text) if isinstance(text, str) else None
    except ValueError:
        return None


def heilung_ereignisse_uebernehmen(status_host=None):
    """Eingriffe der Selbstheilung (13.10.2026) aus dem Status ins Audit-Log, jeden einmal (Kennung); ein Rückfall auf
    die gute Version und eine knappe Platte zusätzlich als Hinweis an alle Benutzer."""
    heilung = ((status_host if status_host is not None else host.host_status()) or {}).get("heilung") or {}
    if not isinstance(heilung, dict):
        return

    def neu(ereignis, kennung):
        if not isinstance(kennung, str) or not kennung.isalnum() or len(kennung) > 32:
            return False
        return not SystemEreignis.objects.filter(art=SystemEreignis.Art.SYSTEM, details__ereignis=ereignis,
                                                 details__kennung=kennung).exists()

    for e in heilung.get("aktionen") or []:
        if not isinstance(e, dict) or not neu("heilung", e.get("id")):
            continue
        protokolliere(SystemEreignis.Art.SYSTEM, benutzername="systemagent", objekt=f"Selbstheilung: {e.get('dienst', '')}"[:200],
                      ereignis="heilung", kennung=e["id"], dienst=str(e.get("dienst") or "")[:40], heilung_art=str(e.get("art") or "")[:20],
                      ok=bool(e.get("ok")), zeit=str(e.get("zeit") or "")[:40], text=str(e.get("text") or "")[:300],
                      probelauf=bool(e.get("probelauf")))
    r = heilung.get("rueckfall")
    if isinstance(r, dict) and neu("heilung_rueckfall", r.get("id")):
        von, nach = str(r.get("von") or "?")[:60], str(r.get("nach") or "")[:60]
        protokolliere(SystemEreignis.Art.SYSTEM, benutzername="systemagent", objekt="EPM-Version", ereignis="heilung_rueckfall",
                      kennung=r["id"], von=von, nach=nach, ok=bool(r.get("ok")), quelle=str(r.get("quelle") or "")[:20],
                      grund=str(r.get("grund") or "")[:300], zeit=str(r.get("zeit") or "")[:40])
        if nach and r.get("ok"):
            text = (f"EPM wurde auf Version {nach} zurückgeschaltet, weil {von} nicht startete. Datenbank-Migrationen der "
                    f"neuen Version wurden nicht zurückgedreht. Nächste Schritte für die Administration: System › Protokolle "
                    f"(Container backend, Update) ansehen; läuft {nach} nicht sauber, die Sicherung von vor dem Update "
                    f"wiederherstellen; den Fehler beheben und erneut aktualisieren.")
        elif nach:
            text = (f"EPM-Version {von} startet nicht, und das Zurückschalten auf {nach} ist fehlgeschlagen. Administration: "
                    f"System › Protokolle ansehen, notfalls per Konsole „sudo epm-update --versionen“ und „--zurueck“ "
                    f"(Notfallplan Teil E).")
        else:
            text = (f"EPM-Version {von} startet nicht, und es gibt keine andere Version zum Zurückschalten. Administration: "
                    f"System › Protokolle ansehen; notfalls Sicherung wiederherstellen (Notfallplan Teil E).")
        _hinweis_vom_server(text)
    p = heilung.get("platte")
    if isinstance(p, dict) and neu("heilung_platte", p.get("id")):
        from django.template.defaultfilters import filesizeformat

        frei, gesamt = p.get("frei"), p.get("gesamt")
        groesse = f"{filesizeformat(frei)} frei von {filesizeformat(gesamt)}" if isinstance(frei, int) and isinstance(gesamt, int) \
            else "weniger als 1 GB oder 5 % frei"
        protokolliere(SystemEreignis.Art.SYSTEM, benutzername="systemagent", objekt=f"Platte {p.get('bezeichnung', '')}"[:200],
                      ereignis="heilung_platte", kennung=p["id"], pfad=str(p.get("pfad") or "")[:200], frei=frei, gesamt=gesamt)
        _hinweis_vom_server(f"Die Platte des Servers ({p.get('bezeichnung', '')}, {p.get('pfad', '')}) ist fast voll: {groesse}. "
                            "Der Server hat nicht mehr benötigte Docker-Images entfernt. Administration: unter System › Wartung › "
                            "Speicher aufräumen alte Versionen und das Journal entfernen, unter Backup alte Sicherungen löschen.",
                            stunden=host.HEILUNG_PLATTE_HINWEIS_STUNDEN)


def bestaetigung_pruefen(request, was: str):
    """Admin-Passwort und zweiter Faktor (Authenticator, Notfall-Code oder Passkey), wie beim Wiederherstellen (F63). Ohne
    eingerichteten zweiten Faktor geht es nicht (Festlegung 03.10.2026).
    Fehlversuche stehen im Audit-Log, sperren das Konto aber nicht (die Anmeldung selbst ist schon bestätigt)."""
    user = request.user
    kennwort = str(request.data.get("kennwort", ""))
    if not zweifaktor.hat_zweiten_faktor(user):
        return {"code": zweifaktor.OHNE_ZWEITEN_FAKTOR}
    if not kennwort or not user.check_password(kennwort):
        protokolliere(SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, request, grund="bestaetigung", was=was)
        return {"kennwort": "Das Passwort stimmt nicht."}
    if zweifaktor.zweiter_faktor_bestaetigt(request):
        return None
    protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN, request, schritt="bestaetigung", was=was,
                  **({"passkey": True} if zweifaktor.passkey_gesendet(request) else {}))
    return {"code": zweifaktor.fehlertext(request, "Der Code ist ungültig oder wurde schon verwendet.")}


def _sitzungen(request):
    eigene = request.session.session_key if getattr(request, "session", None) else None
    return [{
        "id": s.id, "benutzer": s.benutzer_id, "name": s.benutzer.anzeigename, "benutzername": s.benutzer.username,
        "rolle": s.benutzer.rolle, "browser": s.browser, "ip": s.ip, "angemeldet_am": s.angemeldet_am,
        "zuletzt_am": s.zuletzt_am, "eigene": s.sitzungsschluessel == eigene,
    } for s in epm_aufgaben.angemeldete_sitzungen()]


class UebersichtView(APIView):
    permission_classes = [SystemRecht]

    def get(self, request):
        auftraege_abgleichen()
        ordner = host.ordner_auftraege()
        status_host = host.host_status()
        zugang_ereignisse_uebernehmen(status_host)
        heilung_ereignisse_uebernehmen(status_host)
        paket_schluessel_uebernehmen(status_host)
        return Response({
            "host": status_host,
            "container": host.container_messung(),
            "agent": {
                "verzeichnis": ordner.is_dir(),
                "erreichbar": host.agent_erreichbar(),
            },
            "epm": epm_aufgaben.epm_info(),
            "angemeldet": _sitzungen(request),
            "hinweis": hinweis_daten(Systemhinweis.aktiv()),
            "aktionen": [{"code": code, **{k: v for k, v in a.items() if k != "hinweis"},
                          "sichern": a.get("sichern", False), "warnen": a.get("warnen", False),
                          "erlaubt": not a.get("recht") or request.user.hat_recht(a["recht"])}
                         for code, a in host.AKTIONEN.items() if not a.get("intern")],
            "aufgaben": [{"code": code, **a} for code, a in epm_aufgaben.AUFGABEN.items()],
            # Wartung ohne SSH (F179): Beschreibungen und Bestätigung der eigenen Aufträge, hochgeladene Dateien
            "verwaltung": {code: {k: v for k, v in host.AKTIONEN[code].items() if k not in ("intern", "hinweis")}
                           for code in VERWALTUNG_AKTIONEN},
            "uploads": hochladen.liste(("paket", "ocr")),
            "upload": {"teil": hochladen.TEIL, "max": {a: hochladen.ARTEN[a]["max"] for a in ("paket", "ocr")}},
            "austausch": host.ordner_download().is_dir() and host.ordner_upload().is_dir(),
            "dienste": list(host.DIENSTE),
            "minuten": MINUTEN_ERLAUBT,
            "einstellungen": _einstellungen(),
            # „Datenbank leeren“ nur für die Rolle Admin (Festlegung 03.10.2026, U27)
            "leeren_erlaubt": request.user.ist_admin,
        })


def _einstellungen():
    from stammdaten.models import Einstellungen

    e = Einstellungen.aktuell()
    return {"musterdaten_automatisch": e.musterdaten_automatisch, "import_ausgeblendet": e.import_ausgeblendet}


class EinstellungenView(APIView):
    """Schalter unter Administration › System (Festlegung 03.10.2026): ``musterdaten_automatisch`` – Testbenutzer und
    Testpatienten bei Start/Update anlegen; ``import_ausgeblendet`` – Menüpunkt „Import“ nach der Übernahme aus-
    bzw. wieder einblenden. Historie der Einstellungen und Audit-Log."""

    permission_classes = [SystemRecht]
    NAMEN = {"musterdaten_automatisch": "Musterdaten automatisch anlegen", "import_ausgeblendet": "Import ausgeblendet"}

    def post(self, request):
        from stammdaten.models import Einstellungen

        werte = {k: request.data[k] for k in self.NAMEN if k in request.data}
        if not werte or any(not isinstance(v, bool) for v in werte.values()):
            return Response({"fehler": "Erwartet: musterdaten_automatisch und/oder import_ausgeblendet (true/false)."},
                            status=status.HTTP_400_BAD_REQUEST)
        e = Einstellungen.aktuell()
        for k, v in werte.items():
            if getattr(e, k) != v:
                setattr(e, k, v)
                e._history_user = request.user
                e.save()
                protokolliere(SystemEreignis.Art.SYSTEM, request, objekt="Einstellung", ereignis="einstellung",
                              was=self.NAMEN[k], wert="ja" if v else "nein")
        return Response(_einstellungen())


LEEREN_SCHLUESSEL = "epm_leeren"
LEEREN_MINUTEN = 10


class LeerenVorbereitenView(APIView):
    """„Datenbank leeren“ Schritt 1: Umfang, Konten zur Auswahl und ein Bestätigungscode zum Abtippen (10 Minuten, in
    der Sitzung). Nur Rolle Admin mit Recht „Systemverwaltung“."""

    permission_classes = [SystemRecht]

    def post(self, request):
        import secrets

        from accounts.models import User

        from .leeren import umfang

        if not request.user.ist_admin:
            return Response({"fehler": "Die Datenbank leeren darf nur die Rolle Admin."}, status=status.HTTP_403_FORBIDDEN)
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        bis = timezone.now() + timedelta(minutes=LEEREN_MINUTEN)
        request.session[LEEREN_SCHLUESSEL] = {"code": code, "bis": bis.isoformat()}
        konten = User.objects.order_by("last_name", "first_name", "username")
        return Response({
            "code": code, "gueltig_bis": bis, "umfang": umfang(),
            "benutzer": [{"id": u.id, "anzeigename": u.anzeigename, "benutzername": u.username, "rolle": u.rolle,
                          "ist_test": u.ist_test, "nur_historisch": u.nur_historisch, "eigene": u.pk == request.user.pk}
                         for u in konten],
        })


class LeerenView(APIView):
    """Schritt 2: Auftrag an den Systemagenten (vorher Sicherung). Verlangt den abgetippten Bestätigungscode,
    ``wirklich: true`` (Rückfrage „Wollen Sie wirklich …“), die Auswahl der bleibenden Konten, Passwort und Code der
    Zwei-Faktor-Anmeldung."""

    permission_classes = [SystemRecht]

    def post(self, request):
        from datetime import datetime

        from accounts.models import User

        if not request.user.ist_admin:
            return Response({"fehler": "Die Datenbank leeren darf nur die Rolle Admin."}, status=status.HTTP_403_FORBIDDEN)
        sitzung = request.session.get(LEEREN_SCHLUESSEL) or {}
        if not sitzung or datetime.fromisoformat(sitzung["bis"]) < timezone.now():
            return Response({"bestaetigung": "Der Bestätigungscode ist abgelaufen. Bitte neu anfordern."},
                            status=status.HTTP_400_BAD_REQUEST)
        if "".join(str(request.data.get("bestaetigung", "")).upper().split()) != sitzung["code"]:
            return Response({"bestaetigung": "Der Bestätigungscode stimmt nicht."}, status=status.HTTP_400_BAD_REQUEST)
        if request.data.get("wirklich") is not True:
            return Response({"wirklich": "Bitte bestätigen: Wollen Sie die Datenbank wirklich leeren?"},
                            status=status.HTTP_400_BAD_REQUEST)
        behalten = request.data.get("behalten") or []
        if not isinstance(behalten, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in behalten):
            return Response({"behalten": "Liste der Konten-IDs erwartet."}, status=status.HTTP_400_BAD_REQUEST)
        ids = set(User.objects.filter(pk__in=behalten).values_list("pk", flat=True)) | {request.user.pk}
        with transaction.atomic():
            antwort = auftrag_anlegen(request, "datenbank_leeren", parameter={"behalten": sorted(ids)},
                                      objekt="Datenbank", protokoll_details={"konten_bleiben": len(ids)})
        if antwort.status_code == status.HTTP_201_CREATED:
            request.session.pop(LEEREN_SCHLUESSEL, None)
        return antwort


class VerlaufView(APIView):
    permission_classes = [SystemRecht]

    def get(self, request):
        zeitraum = request.query_params.get("zeitraum") or "24h"
        if zeitraum not in host.ZEITRAEUME:
            return Response({"zeitraum": f"Erlaubt: {', '.join(host.ZEITRAEUME)}."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(host.verlauf(zeitraum))


class AuftraegeView(APIView):
    permission_classes = [SystemRecht]

    def get(self, request):
        auftraege_abgleichen()
        qs = Systemauftrag.objects.select_related("angefordert_von")[:30]
        return Response(AuftragSerializer(qs, many=True).data)

    def post(self, request):
        code = request.data.get("aktion")
        aktion = host.AKTIONEN.get(code) if isinstance(code, str) else None
        if aktion is None or aktion.get("intern"):
            return Response({"aktion": "Unbekannte Aktion."}, status=status.HTTP_400_BAD_REQUEST)
        return auftrag_anlegen(request, code)


def auftrag_anlegen(request, code, parameter=None, geheim=None, objekt=None, protokoll_details=None):
    """Auftrag an den Systemagenten: Recht, Wartezeit und Warnung (warnen), Passwort + 2FA (bestaetigung „2fa“), nicht
    doppelt, ablegen, Hinweis an alle Benutzer, Audit-Log. ``parameter`` stehen auch in der Datenbank, ``geheim`` nur
    in der Auftragsdatei. Antwort: 201 mit dem Auftrag oder 400/403/409/503."""
    aktion = host.AKTIONEN[code]
    if aktion.get("recht") and not request.user.hat_recht(aktion["recht"]):
        from accounts.rechte import NAMEN

        return Response({"fehler": f"Dafür fehlt das Recht „{NAMEN[aktion['recht']]}“."},
                        status=status.HTTP_403_FORBIDDEN)
    minuten = 0
    if aktion.get("warnen"):
        try:
            minuten = int(request.data.get("minuten") or 0)
        except (TypeError, ValueError):
            minuten = -1
        if minuten not in MINUTEN_ERLAUBT:
            return Response({"minuten": "Bitte 0, 5, 10, 15, 30 oder 60 Minuten wählen."},
                            status=status.HTTP_400_BAD_REQUEST)
    if aktion["bestaetigung"] == "2fa":
        fehler = bestaetigung_pruefen(request, aktion["name"])
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
    if not aktion.get("mehrfach") and Systemauftrag.objects.filter(
            ziel=Systemauftrag.Ziel.SERVER, aktion=code,
            status__in=[Systemauftrag.Status.WARTET, Systemauftrag.Status.LAEUFT]).exists():
        return Response({"fehler": f"„{aktion['name']}“ ist schon beauftragt und noch nicht abgeschlossen."},
                        status=status.HTTP_409_CONFLICT)
    werte = dict(parameter or {})
    if aktion.get("warnen"):
        werte["minuten"] = minuten
    auftrag = Systemauftrag.objects.create(ziel=Systemauftrag.Ziel.SERVER, aktion=code, parameter=werte,
                                           angefordert_von=request.user)
    try:
        host.auftrag_ablegen(auftrag, geheim=geheim)
    except host.AuftragNichtMoeglich as e:
        transaction.set_rollback(True)
        return Response({"fehler": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if aktion.get("warnen"):
        beginn = timezone.now() + timedelta(minutes=minuten)
        text = str(request.data.get("hinweis") or "").strip()[:400] or aktion["hinweis"]
        zeit = f"Beginn: {timezone.localtime(beginn):%H:%M} Uhr." if minuten else "Beginn: jetzt."
        vorher = Systemhinweis.aktiv()
        if vorher is not None:
            hinweis_beenden(vorher, request.user)
        Systemhinweis.objects.create(
            text=f"{text} {zeit}"[:500], art=Systemhinweis.Art.WARNUNG, auftrag=auftrag, angelegt_von=request.user,
            gueltig_bis=beginn + timedelta(minutes=WARNUNG_NACHLAUF.get(code, 15)))
    bestaetigt = aktion["bestaetigung"] == "2fa"
    protokolliere(protokoll_art(code), request, objekt=objekt or aktion["name"], ereignis="angefordert",
                  aktion=code, name=aktion["name"], minuten=minuten, bestaetigt=bestaetigt,
                  **({"zweiter_faktor": zweifaktor.hat_zweiten_faktor(request.user)} if bestaetigt else {}),
                  **(protokoll_details or {}))
    return Response(AuftragSerializer(auftrag).data, status=status.HTTP_201_CREATED)


class AuftragAbbrechenView(APIView):
    permission_classes = [SystemRecht]

    def post(self, request, kennung):
        auftrag = Systemauftrag.objects.filter(kennung=kennung, ziel=Systemauftrag.Ziel.SERVER).first()
        return auftrag_zurueckziehen(request, auftrag)


def auftrag_zurueckziehen(request, auftrag: Systemauftrag | None):
    """Wartenden Auftrag zurückziehen: solange der Agent ihn nicht übernommen hat oder er in der Warnzeit wartet."""
    if auftrag is None:
        return Response({"fehler": "Auftrag nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)
    if auftrag.status != Systemauftrag.Status.WARTET or not host.auftrag_zurueckziehen(auftrag):
        return Response({"fehler": "Der Server hat den Auftrag schon übernommen; er kann nicht mehr zurückgezogen "
                                   "werden."}, status=status.HTTP_409_CONFLICT)
    auftrag.status = Systemauftrag.Status.ABGEBROCHEN
    auftrag.beendet_am = timezone.now()
    auftrag.ergebnis = f"Zurückgezogen von {request.user.anzeigename}."
    auftrag.save(update_fields=["status", "beendet_am", "ergebnis"])
    for h in Systemhinweis.objects.filter(auftrag=auftrag, beendet_am__isnull=True):
        hinweis_beenden(h, request.user)
    protokolliere(protokoll_art(auftrag.aktion), request, objekt=_name(auftrag), ereignis="abgebrochen",
                  aktion=auftrag.aktion, name=_name(auftrag))
    return Response(AuftragSerializer(auftrag).data)


class EpmAufgabeView(APIView):
    """Wartung des EPM, sofort ausgeführt (VACUUM über eine eigene Datenbankverbindung, siehe epm_aufgaben)."""

    permission_classes = [SystemRecht]

    def post(self, request):
        code = request.data.get("aufgabe")
        aufgabe = epm_aufgaben.AUFGABEN.get(code) if isinstance(code, str) else None
        if aufgabe is None:
            return Response({"aufgabe": "Unbekannte Aufgabe."}, status=status.HTTP_400_BAD_REQUEST)
        pruefsummen = request.data.get("pruefsummen") in (True, "true", "1", 1)
        auftrag = Systemauftrag.objects.create(ziel=Systemauftrag.Ziel.EPM, aktion=code, angefordert_von=request.user,
                                               status=Systemauftrag.Status.LAEUFT, begonnen_am=timezone.now(),
                                               parameter={"pruefsummen": True} if pruefsummen else {})
        try:
            with transaction.atomic():  # Datenbankfehler einer Aufgabe nur bis hierher zurückrollen
                rc, kurz, details = epm_aufgaben.AUSFUEHRUNG[code](request, pruefsummen=pruefsummen)
        except Exception as e:  # noqa: BLE001 – Ergebnis soll im Auftrag stehen, nicht als 500
            rc, kurz, details = 1, f"Fehler: {e}", f"{type(e).__name__}: {e}"
        auftrag.status = Systemauftrag.Status.ERLEDIGT if rc == 0 else Systemauftrag.Status.FEHLER
        auftrag.rueckgabe = rc
        auftrag.ergebnis = kurz[:500]
        auftrag.ausgabe = details[-20000:]
        auftrag.beendet_am = timezone.now()
        auftrag.save(update_fields=["status", "rueckgabe", "ergebnis", "ausgabe", "beendet_am"])
        protokolliere(SystemEreignis.Art.SYSTEM, request, objekt=aufgabe["name"], ereignis="epm_aufgabe", aktion=code,
                      name=aufgabe["name"], status=auftrag.status, ergebnis=auftrag.ergebnis)
        return Response(AuftragSerializer(auftrag).data)


class HinweisSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500, trim_whitespace=True)
    art = serializers.ChoiceField(choices=Systemhinweis.Art.choices, default=Systemhinweis.Art.INFO)
    minuten = serializers.IntegerField(min_value=0, max_value=7 * 24 * 60, required=False, allow_null=True)


class HinweisView(APIView):
    """Lesen: jeder Angemeldete (Banner oben in jeder Seite). Setzen und beenden: Systemverwaltung."""

    permission_classes = [recht("system_verwalten", lesen=None)]

    def get(self, request):
        # Hinweise des Servers selbst (Rückfall, Platte) sollen alle Benutzer bald sehen, nicht erst, wenn ein Admin die
        # Systemseite öffnet: beim Abruf des Banners den Status des Agenten übernehmen (nur eine kleine Datei lesen)
        try:
            status_host = host.host_status()
            heilung_ereignisse_uebernehmen(status_host)
            paket_schluessel_uebernehmen(status_host)
        except Exception:  # noqa: BLE001 – der Banner darf daran nie scheitern
            pass
        return Response({"hinweis": hinweis_daten(Systemhinweis.aktiv())})

    def post(self, request):
        s = HinweisSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        vorher = Systemhinweis.aktiv()
        if vorher is not None:
            hinweis_beenden(vorher, request.user)
        minuten = s.validated_data.get("minuten")
        h = Systemhinweis.objects.create(
            text=s.validated_data["text"], art=s.validated_data["art"], angelegt_von=request.user,
            gueltig_bis=timezone.now() + timedelta(minutes=minuten) if minuten else None)
        protokolliere(SystemEreignis.Art.SYSTEM, request, objekt="Hinweis an alle Benutzer", ereignis="hinweis",
                      text=h.text, hinweis_art=h.art, minuten=minuten)
        return Response({"hinweis": hinweis_daten(h)}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        h = Systemhinweis.aktiv()
        if h is None:
            return Response({"fehler": "Es gibt keinen aktiven Hinweis."}, status=status.HTTP_404_NOT_FOUND)
        hinweis_beenden(h, request.user, request)
        return Response({"hinweis": None})


class SitzungBeendenView(APIView):
    permission_classes = [SystemRecht]

    def delete(self, request, pk):
        from accounts.models import Sitzung
        from accounts.sitzungen import sitzung_beenden

        s = Sitzung.objects.filter(pk=pk).select_related("benutzer").first()
        if s is None:
            return Response({"fehler": "Anmeldung nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)
        if request.session.session_key and s.sitzungsschluessel == request.session.session_key:
            return Response({"fehler": "Die eigene Anmeldung bitte über „Abmelden“ beenden."},
                            status=status.HTTP_400_BAD_REQUEST)
        protokolliere(SystemEreignis.Art.SYSTEM, request, objekt=s.benutzer.username, ereignis="sitzung_beendet",
                      browser=s.browser, sitzung_ip=s.ip)
        sitzung_beenden(s)
        return Response(status=status.HTTP_204_NO_CONTENT)
