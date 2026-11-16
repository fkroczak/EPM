"""Sicherheitsprüfung (11.10.2026): Anmeldung, Rechte und Trennung der Firmen über alle Endpunkte.

Die Endpunkte werden aus den URL-Mustern gelesen – ein neuer Endpunkt ist damit automatisch mitgeprüft:
- ohne Anmeldung und mit halber Anmeldung (Passwort ja, zweiter Faktor offen) gibt es keine Daten;
- wer in der Regeneration Clinic arbeitet, erreicht Akten, die nur der DSKM gehören, über keinen Weg – weder lesend
  (Liste, Einzelabruf, Filter ``?patient=``, Suche, PDF, Datei) noch schreibend (Änderung, Aktion, neuer Eintrag mit
  fremder ``patient``-ID im Inhalt).
"""
import re
from datetime import timedelta

from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import get_resolver
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Mitgliedschaft, Rolle
from audit.models import SystemEreignis
from epm.pruefhilfen import KENNWORT, Grundlage, benutzer, client_fuer, echte_anmeldung, mit_zweitem_faktor
from patienten.models import Kontakt, Patient, PatientFirma
from stammdaten.models import Auswahlwert, Firma

# Ohne vollständige Anmeldung erreichbar (Anmeldung selbst, Logo der Anmeldeseite)
OEFFENTLICH = {"api/auth/status/", "api/auth/anmelden/", "api/auth/2fa/", "api/auth/abmelden/", "api/auth/kennwort/",
               "api/auth/2fa/einrichten/", "api/auth/2fa/bestaetigen/", "api/auth/passkey/optionen/",
               "api/auth/passkey/", "api/auth/passkey/registrieren/", "api/briefkopf/logo/"}
GEHEIM = "Zqxgeheim"  # Nachname der fremden Akten – darf in keiner Antwort stehen
WERTE = {"art": "arztbrief", "version": "1", "stempel": "20261011-0000", "kennung": "00000000-0000-0000-0000-000000000000",
         "datei": "x.pdf", "abschnitt": "start", "gid": "1"}


def routen():
    """(Pfad mit Platzhaltern, View-Klasse, Methoden) für alle API-Endpunkte (ohne die Varianten mit Format-Endung)."""
    ergebnis = []

    def gehe(muster, vorne=""):
        for m in muster:
            pfad = vorne + str(m.pattern)
            if hasattr(m, "url_patterns"):
                gehe(m.url_patterns, pfad)
                continue
            if "(?P<format>" in pfad or not pfad.startswith("api/"):
                continue
            cls = getattr(m.callback, "cls", None) or getattr(m.callback, "view_class", None)
            aktionen = getattr(m.callback, "actions", None)
            if aktionen:
                methoden = sorted(aktionen)
            else:
                methoden = [x for x in ("get", "post", "put", "patch", "delete") if hasattr(cls, x)]
            ergebnis.append((pfad.replace("^", "").replace("$", ""), cls, methoden))

    gehe(get_resolver().url_patterns)
    return ergebnis


def url_mit(pfad, werte):
    def ersetze(m):
        return str(werte.get(m.group(1) or m.group(2), "1"))

    return "/" + re.sub(r"\(\?P<(\w+)>[^)]*\)|<(?:\w+:)?(\w+)>", ersetze, pfad).replace("\\.", ".")


def modell_von(cls):
    for weg in (lambda: cls.model, lambda: cls.queryset.model, lambda: cls.serializer_class.Meta.model):
        try:
            return weg()
        except AttributeError:
            continue
    return None


class OhneAnmeldung(Grundlage):
    """Jeder Endpunkt außer der Anmeldung verlangt die vollständige Anmeldung."""

    def pruefe_alle(self, c, wer):
        c.raise_request_exception = False
        offen = []
        for pfad, cls, methoden in routen():
            if pfad in OEFFENTLICH:
                continue
            url = url_mit(pfad, {**WERTE, "pk": self.patient.id, "patient": self.patient.id})
            for methode in methoden:
                r = getattr(c, methode)(url, {}, format="json")
                if r.status_code not in (401, 403, 404, 405):
                    offen.append(f"{methode.upper()} {url} → {r.status_code}")
        self.assertEqual(offen, [], f"{wer}: ohne vollständige Anmeldung erreichbar")

    def test_anonym(self):
        self.pruefe_alle(APIClient(), "anonym")

    def test_halb_angemeldet(self):
        mit_zweitem_faktor(self.mediziner)
        c = APIClient()
        r = c.post("/api/auth/anmelden/", {"benutzername": "mediziner", "kennwort": KENNWORT}, format="json")
        self.assertEqual(r.json()["schritt"], "2fa")
        self.pruefe_alle(c, "Passwort ohne zweiten Faktor")

    def test_einmal_kennwort_offen(self):
        self.mediziner.muss_kennwort_aendern = True
        self.mediziner.save()
        c = APIClient()
        r = c.post("/api/auth/anmelden/", {"benutzername": "mediziner", "kennwort": KENNWORT}, format="json")
        self.assertEqual(r.json()["schritt"], "kennwort_aendern")
        self.pruefe_alle(c, "Einmal-Passwort noch nicht ersetzt")


class FirmenDaten(Grundlage):
    """Daten für die Prüfungen über alle Endpunkte: Akten nur der DSKM mit Einträgen jeder Art, Konten in beiden
    Firmen."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from patienten.testdaten import testdaten_zuruecksetzen

        testdaten_zuruecksetzen()
        cls.rg = Firma.objects.get(kuerzel="rg")
        # Fremde Akten: der echte Patient der Grundlage und ein Testpatient, beide nur DSKM, mit Einträgen jeder Art
        m = client_fuer(cls.mediziner)
        cls.fremd = [cls.patient, Patient.objects.get(ist_test=True, nachname="Musterfrau")]
        for p in cls.fremd:
            Patient.objects.filter(pk=p.pk).update(nachname=GEHEIM)
            assert list(PatientFirma.objects.filter(patient=p).values_list("firma__kuerzel", flat=True)) == ["dskm"]
        # zusätzlich zu den Musterdaten: Kontakt, Dokument (mit Datei), Bericht, Datenschutzanfrage, Merkliste
        test = cls.fremd[1]
        r = m.post("/api/kontakte/", {"patient": test.id, "text": "<p>geheimer Kontakt</p>"}, format="json")
        assert r.status_code == 201, r.content
        r = m.post("/api/dokumente/", {"patient": test.id, "titel": "Brief",
                                       "datei": SimpleUploadedFile("b.pdf", b"%PDF-1.4 geheim", "application/pdf")},
                   format="multipart")
        assert r.status_code == 201, r.content
        art = Auswahlwert.objects.get(liste=Auswahlwert.Liste.BERICHTART, wert="Arztbrief")
        r = m.post("/api/berichte/", {"patient": test.id, "art": art.id, "titel": "Bericht", "inhalt": "<p>geheim</p>"},
                   format="json")
        assert r.status_code == 201, r.content
        r = m.post("/api/datenschutzanfragen/", {"patient": test.id, "art": "auskunft", "gestellt_von": "Patientin"},
                   format="json")
        assert r.status_code == 201, r.content
        m.post("/api/meine-akten/merken/", {"patient": test.id}, format="json")
        Kontakt.objects.create(patient=cls.patient, text="<p>echt</p>", zeitpunkt=timezone.now(), erfasst_von=cls.mediziner)
        # Person in beiden Firmen: in der DSKM Betrachter, in der Regeneration Clinic Mediziner (alle Rechte dort)
        cls.rg_mediziner = benutzer("rgmed", Rolle.BETRACHTER)
        Mitgliedschaft.objects.create(benutzer=cls.rg_mediziner, firma=cls.rg, rolle=Rolle.MEDIZINER)
        # Admin nur in der Regeneration Clinic
        cls.rg_admin = benutzer("rgadmin", Rolle.KEINE)
        Mitgliedschaft.objects.create(benutzer=cls.rg_admin, firma=cls.rg, rolle=Rolle.ADMIN)

    def anmelden(self, user, firma="rg"):
        c = echte_anmeldung(user, mit_zweitem_faktor(user, 1)[0])
        r = c.post("/api/auth/firma/", {"firma": firma}, format="json")
        self.assertEqual(r.json()["benutzer"]["firma"], firma)
        return c

    def ziele(self):
        """{Modell: [IDs]} aller Einträge der fremden Akten."""
        ids = [p.id for p in self.fremd]
        ziele = {Patient: ids}
        for modell in apps.get_models():
            if modell.__name__.startswith("Historical"):
                continue
            for f in modell._meta.concrete_fields:
                if f.is_relation and f.related_model is Patient:
                    ziele.setdefault(modell, []).extend(
                        modell.objects.filter(**{f"{f.name}__in": ids}).values_list("pk", flat=True))
        return ziele

    def stand(self):
        """Zählstand aller Daten der fremden Akten (inkl. Historie) – ändert er sich, wurde geschrieben."""
        ids = [p.id for p in self.fremd]
        stand = {}
        for modell in apps.get_models():
            for f in modell._meta.concrete_fields:
                if f.is_relation and f.related_model is Patient or (
                        modell.__name__.startswith("Historical") and f.name == "patient_id"):
                    stand[f"{modell.__name__}.{f.name}"] = modell.objects.filter(**{f"{f.name}__in": ids}).count()
        stand["historie_patient"] = Patient.history.filter(id__in=ids).count()
        stand["dokumente_geaendert"] = sorted(
            apps.get_model("patienten", "Dokument").objects.filter(patient__in=ids).values_list("id", "titel"))
        return stand

    def leck(self, r, ids) -> str | None:
        inhalt = r.content.decode("utf-8", "replace") if not getattr(r, "streaming", False) else ""
        if GEHEIM in inhalt:
            return "Name der fremden Akte in der Antwort"
        for pid in ids:
            if re.search(rf'"(patient|patient_id)":\s*{pid}\b', inhalt):
                return f"Patient {pid} in der Antwort"
        if r.get("X-Accel-Redirect") or getattr(r, "streaming", False):
            return "Datei ausgeliefert"
        if r.get("Content-Type", "").startswith("application/pdf") and r.status_code == 200:
            from io import BytesIO

            from pypdf import PdfReader

            text = " ".join("".join(seite.extract_text() or "" for seite in PdfReader(BytesIO(r.content)).pages).split())
            text = text.replace(f"Suche „{GEHEIM}“", "")  # der eigene Suchbegriff im Audit-Log, keine fremde Akte
            if GEHEIM in text:
                return "Name der fremden Akte im PDF"
        return None

    def sweep(self, c, auslassen=()):
        c.raise_request_exception = False  # Serverfehler als Befund sammeln, nicht abbrechen
        ziele = self.ziele()
        pids = ziele[Patient]
        vorher, ereignisse = self.stand(), SystemEreignis.objects.count()
        funde = []
        heute = timezone.localdate()
        historie = Patient.history.filter(id__in=pids).count()
        for pfad, cls, methoden in routen():
            if pfad.startswith(("api/auth/", "api/testdaten/", *auslassen)):
                continue
            modell = modell_von(cls)
            if "<pk>" in pfad or "<int:pk>" in pfad:
                schluessel = ziele.get(modell) or pids
            else:
                schluessel = [None]
            for pk in schluessel:
                for pid in pids:
                    url = url_mit(pfad, {**WERTE, "pk": pk, "patient": pid})
                    for methode in methoden:
                        if methode == "get":
                            # Filter und Suche, Zeitraum für Kalender und Übersichten
                            r = c.get(url, {"patient": pid, "search": GEHEIM, "suche": GEHEIM, "q": GEHEIM,
                                            "von": str(heute - timedelta(days=200)), "bis": str(heute + timedelta(days=199))})
                        else:
                            daten = {"patient": pid, "patienten": [pid], "ziel": pid, "text": "<p>x</p>",
                                     "grund": "Prüfung", "titel": "x", "inhalt": "<p>x</p>", "art": "auskunft"}
                            r = getattr(c, methode)(url, daten, format="json")
                        # jede Änderung an der Akte selbst sofort der Anfrage zuordnen
                        neu = Patient.history.filter(id__in=pids).count()
                        if neu != historie:
                            funde.append(f"{methode.upper()} {url} → {r.status_code}: Akte geändert")
                            historie = neu
                        if r.status_code >= 500:
                            funde.append(f"{methode.upper()} {url} → {r.status_code}")
                        grund = self.leck(r, pids)
                        if grund and r.status_code < 300:
                            funde.append(f"{methode.upper()} {url} → {r.status_code}: {grund}")
        for e in SystemEreignis.objects.order_by("id")[ereignisse:]:
            if (e.details or {}).get("patient_id") in pids:
                funde.append(f"Audit-Eintrag zur fremden Akte: {e.get_art_display()} {e.objekt}")
        self.maxDiff = None
        self.assertEqual(funde, [])
        self.assertEqual(self.stand(), vorher, "Daten der fremden Akten wurden geändert")


class FirmenTrennung(FirmenDaten):
    """Regeneration Clinic gegen DSKM: fremde Akten über keinen Endpunkt lesen oder ändern."""

    def test_mediziner_der_anderen_firma(self):
        self.sweep(self.anmelden(self.rg_mediziner))

    def test_listen_und_kalender_ohne_filter(self):
        c = self.anmelden(self.rg_mediziner)
        heute = timezone.localdate()
        for url in ("/api/patienten/", "/api/patienten/?status=abgeschlossen", "/api/startseite/", "/api/termine/",
                    "/api/kontakte/", "/api/dokumente/", "/api/infusionsplaene/", "/api/infusionsplaene/uebersicht/",
                    "/api/datenschutz/", "/api/datenschutzanfragen/", "/api/erklaerungen/", "/api/berichte/",
                    "/api/meine-akten/", "/api/scans/", f"/api/kalender/?von={heute - timedelta(days=200)}"
                    f"&bis={heute + timedelta(days=199)}"):
            r = c.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertIsNone(self.leck(r, [p.id for p in self.fremd]), url)
        # Gegenprobe: in der DSKM erscheinen die Akten (sonst prüfte der Test nichts)
        c.post("/api/auth/firma/", {"firma": "dskm"}, format="json")
        self.assertIsNotNone(self.leck(c.get("/api/patienten/"), [p.id for p in self.fremd]))
        kalender = c.get(f"/api/kalender/?von={heute - timedelta(days=200)}&bis={heute + timedelta(days=199)}")
        self.assertIsNotNone(self.leck(kalender, [p.id for p in self.fremd]))

    def test_dokument_hochladen_in_fremde_akte(self):
        c = self.anmelden(self.rg_mediziner)
        for p in self.fremd:
            datei = SimpleUploadedFile("b.pdf", b"%PDF-1.4 x", "application/pdf")
            r = c.post("/api/dokumente/", {"patient": p.id, "titel": "x", "datei": datei}, format="multipart")
            self.assertIn(r.status_code, (400, 403, 404), r.content)

    def test_rolle_je_firma(self):
        """In der DSKM nur Betrachter: dort nichts schreiben, obwohl Mediziner in der Regeneration Clinic."""
        c = self.anmelden(self.rg_mediziner, firma="dskm")
        r = c.post("/api/kontakte/", {"patient": self.patient.id, "text": "<p>x</p>"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/").status_code, 200)
        # zurück in die Regeneration Clinic: dort kein Zugriff auf die DSKM-Akte
        c.post("/api/auth/firma/", {"firma": "rg"}, format="json")
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/").status_code, 404)

    def test_firma_ohne_mitgliedschaft(self):
        c = self.anmelden(self.rg_admin)
        self.assertEqual(c.post("/api/auth/firma/", {"firma": "dskm"}, format="json").status_code, 403)
        # auch eine manipulierte Sitzung gibt keinen Zugang
        s = c.session
        s["epm_firma"] = "dskm"
        s.save()
        self.assertEqual(c.get("/api/auth/status/").json()["benutzer"]["firma"], "rg")
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/").status_code, 404)


class FirmenTrennungAdmin(FirmenDaten):
    """Wie FirmenTrennung für den Admin der anderen Firma – eigene Klasse, damit der parallele Testlauf beide
    Durchläufe über alle Endpunkte gleichzeitig ausführen kann (15.11.2026)."""

    def test_admin_der_anderen_firma(self):
        # Benutzer, Server, Sicherung, Import, Modell-Pakete der KI: gemeinsame Verwaltung, nicht je Akte (eigene Tests)
        self.sweep(self.anmelden(self.rg_admin), auslassen=("api/benutzer/", "api/system/", "api/backup/",
                                                            "api/altimport/", "api/sitzungen/", "api/rechte/",
                                                            "api/ki/hochladen/"))


class Rechte(Grundlage):
    """Rollen, Rechteausweitung und geschützte Felder (Massenzuweisung)."""

    def test_massenzuweisung_akte(self):
        c = client_fuer(self.mitarbeiter)
        vorher = Patient.objects.get(pk=self.patient.pk)
        r = c.patch(f"/api/patienten/{self.patient.id}/", {"ist_test": True, "nummer": 8888, "angelegt_von": self.admin.id,
                                                           "eingeschraenkt_am": "2026-01-01T00:00:00Z",
                                                           "abgeschlossen_am": "2026-01-01T00:00:00Z"}, format="json")
        p = Patient.objects.get(pk=self.patient.pk)
        self.assertEqual((p.ist_test, p.nummer, p.angelegt_von_id, p.eingeschraenkt_am, p.abgeschlossen_am),
                         (vorher.ist_test, vorher.nummer, vorher.angelegt_von_id, None, None))

    def test_massenzuweisung_testbenutzer(self):
        test = benutzer("tester", Rolle.MITARBEITER, ist_test=True)
        c = client_fuer(test)
        r = c.post("/api/patienten/", {"nachname": "T", "vorname": "T", "geburtsdatum": "1980-01-01", "ist_test": False},
                   format="json")
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.json()["id"]
        self.assertTrue(Patient.objects.get(pk=pid).ist_test)
        r = c.patch(f"/api/patienten/{pid}/", {"ist_test": False}, format="json")
        self.assertTrue(Patient.objects.get(pk=pid).ist_test)
        # echte Akten gibt es für Testbenutzer nicht
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/").status_code, 404)
        r = c.post("/api/kontakte/", {"patient": self.patient.id, "text": "<p>x</p>"}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

    def test_massenzuweisung_eintrag(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/kontakte/", {"patient": self.patient.id, "text": "<p>x</p>", "erfasst_von": self.admin.id,
                                      "storniert_am": "2026-01-01T00:00:00Z", "firma": 2, "erfasst_am": "2020-01-01T00:00:00Z"},
                   format="json")
        self.assertEqual(r.status_code, 201, r.content)
        k = Kontakt.objects.get(pk=r.json()["id"])
        self.assertEqual((k.erfasst_von_id, k.storniert_am), (self.mitarbeiter.id, None))
        self.assertNotEqual(k.erfasst_am.year, 2020)

    def test_eigene_rolle_nicht_ueber_ich(self):
        c = client_fuer(self.betrachter)
        r = c.patch("/api/auth/ich/", {"rolle": "admin", "is_superuser": True, "is_staff": True, "ist_test": True,
                                       "firmenrollen": {"rg": "admin"}, "rechte": ["benutzer_verwalten"]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.betrachter.refresh_from_db()
        self.assertEqual((self.betrachter.rolle, self.betrachter.is_superuser, self.betrachter.is_staff,
                          self.betrachter.ist_test), (Rolle.BETRACHTER, False, False, False))
        self.assertFalse(Mitgliedschaft.objects.filter(benutzer=self.betrachter).exists())
        self.assertEqual(c.patch(f"/api/benutzer/{self.betrachter.id}/", {"rolle": "admin"}, format="json").status_code, 403)
        self.assertEqual(c.put("/api/rechte/", {"matrix": {"betrachter": {"benutzer_verwalten": True}}},
                               format="json").status_code, 403)

    def test_benutzerverwaltung_ohne_superuser(self):
        c = client_fuer(self.admin)
        r = c.patch(f"/api/benutzer/{self.mitarbeiter.id}/", {"is_superuser": True, "is_staff": True, "password": "x",
                                                              "fehlversuche": 0, "gesperrt_am": None}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.mitarbeiter.refresh_from_db()
        self.assertEqual((self.mitarbeiter.is_superuser, self.mitarbeiter.is_staff), (False, False))
        self.assertTrue(self.mitarbeiter.check_password(KENNWORT))


class NurLesen(FirmenDaten):
    """Betrachter schreiben nirgends; Mitarbeiter geben keine Pläne frei; Verwaltung nur mit eigenem Recht."""

    EIGENES = ("api/auth/", "api/meine-akten/", "api/sitzungen/")  # eigenes Konto und eigene Merkliste

    def test_betrachter_schreibt_nirgends(self):
        c = self.anmelden(self.betrachter, firma="dskm")
        c.raise_request_exception = False
        test = Patient.objects.filter(ist_test=True).values_list("id", flat=True)
        ziele = {Patient: list(test)}
        for modell in apps.get_models():
            if any(f.is_relation and f.related_model is Patient for f in modell._meta.concrete_fields) \
                    and not modell.__name__.startswith("Historical"):
                ziele[modell] = list(modell.objects.filter(patient__in=test).values_list("pk", flat=True)[:3]) \
                    if hasattr(modell, "patient") else []
        funde = []
        anzahl = SystemEreignis.objects.count()
        for pfad, cls, methoden in routen():
            if pfad.startswith(self.EIGENES):
                continue
            werte = ziele.get(modell_von(cls)) or list(test)[:2]
            for pk in (werte[:2] if "pk>" in pfad else [None]):
                url = url_mit(pfad, {**WERTE, "pk": pk, "patient": werte[0]})
                for methode in methoden:
                    if methode in ("get", "head", "options"):
                        continue
                    r = getattr(c, methode)(url, {"patient": test[0], "text": "<p>x</p>"}, format="json")
                    if r.status_code < 300 or r.status_code >= 500:
                        funde.append(f"{methode.upper()} {url} → {r.status_code}")
        self.assertEqual(funde, [])
        neu = SystemEreignis.objects.order_by("id")[anzahl:]
        self.assertEqual([e.get_art_display() for e in neu if e.art not in (SystemEreignis.Art.ANMELDUNG,)], [])

    def test_verwaltung_nur_mit_recht(self):
        for user in (self.mitarbeiter, self.mediziner):
            c = client_fuer(user)
            for url in ("/api/benutzer/", "/api/rechte/", "/api/system/uebersicht/", "/api/backup/", "/api/altimport/",
                        "/api/testdaten/", "/api/system/protokolle/"):
                self.assertEqual(c.get(url).status_code, 403, f"{user.username} {url}")
            self.assertEqual(c.post("/api/testdaten/zuruecksetzen/").status_code, 403)
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.get("/api/protokoll/").status_code, 403)

    def test_mitarbeiter_gibt_keinen_plan_frei(self):
        from infusionen.models import Infusionsplan

        plan = Infusionsplan.objects.filter(status=Infusionsplan.Status.ENTWURF).first() or Infusionsplan.objects.first()
        c = client_fuer(self.mitarbeiter)
        r = c.post(f"/api/infusionsplaene/{plan.id}/freigeben/", {"code": "123456", "kennwort": KENNWORT}, format="json")
        self.assertEqual(r.status_code, 403, r.content)


class Sitzungen(Grundlage):
    """CSRF, Sitzungs-ID, Abmelden, Sperre nach Fehlversuchen auch beim zweiten Faktor, Notfall-Codes."""

    def test_csrf_wird_verlangt(self):
        codes = mit_zweitem_faktor(self.mitarbeiter, 1)
        c = APIClient(enforce_csrf_checks=True)
        # Anmeldung selbst nur mit Token (gegen Login-CSRF)
        r = c.post("/api/auth/anmelden/", {"benutzername": "mitarbeiter", "kennwort": KENNWORT}, format="json")
        self.assertEqual(r.status_code, 403)
        c.get("/api/auth/status/")
        token = c.cookies["epm_csrf"].value
        r = c.post("/api/auth/anmelden/", {"benutzername": "mitarbeiter", "kennwort": KENNWORT}, format="json",
                   HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 200, r.content)
        token = c.cookies["epm_csrf"].value  # nach der Anmeldung neu
        r = c.post("/api/auth/2fa/", {"code": codes[0]}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.json()["schritt"], "fertig")
        daten = {"patient": self.patient.id, "text": "<p>x</p>"}
        self.assertEqual(c.post("/api/kontakte/", daten, format="json").status_code, 403)
        self.assertEqual(c.post("/api/kontakte/", daten, format="json", HTTP_X_CSRFTOKEN="falsch" * 6).status_code, 403)
        r = c.post("/api/kontakte/", daten, format="json", HTTP_X_CSRFTOKEN=c.cookies["epm_csrf"].value)
        self.assertEqual(r.status_code, 201, r.content)

    def test_neue_sitzungs_id_und_abmelden(self):
        codes = mit_zweitem_faktor(self.mitarbeiter, 1)
        c = APIClient()
        c.get("/api/auth/status/")
        c.session.save()
        vorher = c.session.session_key
        c.post("/api/auth/anmelden/", {"benutzername": "mitarbeiter", "kennwort": KENNWORT}, format="json")
        self.assertNotEqual(c.cookies["epm_sitzung"].value, vorher)
        c.post("/api/auth/2fa/", {"code": codes[0]}, format="json")
        alt = c.cookies["epm_sitzung"].value
        self.assertEqual(c.get("/api/patienten/").status_code, 200)
        c.post("/api/auth/abmelden/")
        # das alte Sitzungs-Cookie gilt nicht mehr
        d = APIClient()
        d.cookies["epm_sitzung"] = alt
        self.assertEqual(d.get("/api/patienten/").status_code, 403)

    def test_sperre_nach_falschen_codes(self):
        codes = mit_zweitem_faktor(self.mitarbeiter, 2)
        c = APIClient()
        c.post("/api/auth/anmelden/", {"benutzername": "mitarbeiter", "kennwort": KENNWORT}, format="json")
        for i in range(4):
            self.assertEqual(c.post("/api/auth/2fa/", {"code": f"falsch{i}"}, format="json").status_code, 401)
        # fünfter falscher Code: diese Sitzung wartet 15 Minuten, auch ein gültiger Code hilft dort nicht
        self.assertEqual(c.post("/api/auth/2fa/", {"code": "falsch4"}, format="json").status_code, 429)
        self.assertEqual(c.post("/api/auth/2fa/", {"code": codes[1]}, format="json").status_code, 429)
        # neue Sitzung: das Konto zählt weiter, der zehnte Fehlversuch in Folge sperrt es
        c = APIClient()
        c.post("/api/auth/anmelden/", {"benutzername": "mitarbeiter", "kennwort": KENNWORT}, format="json")
        for i in range(4):
            self.assertEqual(c.post("/api/auth/2fa/", {"code": f"falsch{i}"}, format="json").status_code, 401)
        r = c.post("/api/auth/2fa/", {"code": "falsch9"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.mitarbeiter.refresh_from_db()
        self.assertIsNotNone(self.mitarbeiter.gesperrt_am)
        # gesperrt: auch Passwort und gültiger Notfall-Code helfen nicht
        c = APIClient()
        self.assertEqual(c.post("/api/auth/anmelden/", {"benutzername": "mitarbeiter", "kennwort": KENNWORT},
                                format="json").status_code, 403)
        self.assertEqual(c.post("/api/auth/2fa/", {"code": codes[0]}, format="json").status_code, 401)

    def test_notfallcode_nur_einmal(self):
        codes = mit_zweitem_faktor(self.mitarbeiter, 2)
        echte_anmeldung(self.mitarbeiter, codes[0])
        c = APIClient()
        c.post("/api/auth/anmelden/", {"benutzername": "mitarbeiter", "kennwort": KENNWORT}, format="json")
        self.assertEqual(c.post("/api/auth/2fa/", {"code": codes[0]}, format="json").status_code, 401)
        self.assertEqual(c.get("/api/patienten/").status_code, 403)

    def test_kennwort_aendern_zaehlt_fehlversuche(self):
        c = echte_anmeldung(self.mitarbeiter, mit_zweitem_faktor(self.mitarbeiter, 1)[0])
        for _ in range(9):
            r = c.post("/api/auth/kennwort/", {"alt": "falsch", "neu": "Ein-ganz-neues-Passwort-77"}, format="json")
            self.assertEqual(r.status_code, 400)
        r = c.post("/api/auth/kennwort/", {"alt": "falsch", "neu": "Ein-ganz-neues-Passwort-77"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.mitarbeiter.refresh_from_db()
        self.assertFalse(self.mitarbeiter.is_active)

    def test_pflicht_fuer_admins_auch_in_weiterer_firma(self):
        from accounts.models import Anmelderegeln
        from accounts.zweifaktor import pflicht

        Anmelderegeln.objects.update_or_create(pk=Anmelderegeln.aktuell().pk, defaults={"zweiter_faktor": "admins"})
        rg_admin = benutzer("rgadmin", Rolle.KEINE)
        Mitgliedschaft.objects.create(benutzer=rg_admin, firma=Firma.objects.get(kuerzel="rg"), rolle=Rolle.ADMIN)
        self.assertTrue(pflicht(rg_admin))
        self.assertTrue(pflicht(self.admin))
        self.assertFalse(pflicht(self.mitarbeiter))
        c = APIClient()
        r = c.post("/api/auth/anmelden/", {"benutzername": "rgadmin", "kennwort": KENNWORT}, format="json")
        self.assertEqual(r.json()["schritt"], "2fa_einrichten")
        self.assertEqual(c.get("/api/patienten/").status_code, 403)

    def test_einstellungen_fuer_den_betrieb(self):
        from django.conf import settings

        self.assertEqual(settings.SESSION_COOKIE_AGE, 30 * 60)
        # Ablauf je Anfrage verlängert die SitzungMiddleware; die Daten der Sitzung schreibt nur, wer sie ändert
        self.assertTrue(not settings.SESSION_SAVE_EVERY_REQUEST and settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual((settings.SESSION_COOKIE_SAMESITE, settings.CSRF_COOKIE_SAMESITE), ("Strict", "Strict"))
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertEqual(settings.EPM_LOGIN_MAX_FEHLVERSUCHE, 10)
        self.assertEqual((settings.EPM_LOGIN_SITZUNG_FEHLVERSUCHE, settings.EPM_LOGIN_SITZUNG_SPERRE_MIN), (5, 15))
        # Drosselung der Anmeldung gemeinsam für alle Gunicorn-Prozesse
        self.assertEqual(settings.CACHES["default"]["BACKEND"], "django.core.cache.backends.db.DatabaseCache")


class PdfUndDateien(Grundlage):
    """PDF-Erzeugung ohne Zugriff nach außen, Eingaben ohne HTML-Einschleusung, Uploads und Downloads."""

    def test_pdf_laedt_nichts_von_aussen(self):
        from vorlagen.pdf import html_zu_pdf, nur_eingebettet

        abrufer = nur_eingebettet()
        for url in ("file:///etc/passwd", "http://169.254.169.254/latest/meta-data/", "https://example.org/x.css",
                    "ftp://example.org/x"):
            with self.assertRaises(ValueError):
                abrufer.fetch(url)
        self.assertEqual(abrufer.fetch("data:text/plain;base64,aGFsbG8=").read(), b"hallo")
        pdf = html_zu_pdf('<link rel="stylesheet" href="file:///etc/passwd"><img src="file:///etc/hostname">'
                          '<p style="background:url(http://127.0.0.1:9/)">x</p>')
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_fusszeile_ohne_html_einschleusung(self):
        from io import BytesIO

        from pypdf import PdfReader

        from vorlagen.pdf import html_zu_pdf, seite

        name = "Muster</style><h1>EINGESCHLEUST</h1><style>"
        pdf = html_zu_pdf(seite("Test", "<p>Inhalt</p>", fusszeile=name))
        text = " ".join(s.extract_text() for s in PdfReader(BytesIO(pdf)).pages)
        # der Name steht als Text in der Fußzeile, nicht als Überschrift im Dokument
        self.assertIn("</style><h1>EINGESCHLEUST</h1>", text)

    def test_kein_postscript_ueber_pillow(self):
        from io import BytesIO

        from PIL import Image, UnidentifiedImageError

        eps = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nshowpage\n"
        with self.assertRaises(UnidentifiedImageError):
            Image.open(BytesIO(eps))
        self.assertNotIn("EPS", Image.ID)

    def test_richtext_wird_bereinigt(self):
        c = client_fuer(self.mitarbeiter)
        boese = ('<p onclick="x()">a</p><script>alert(1)</script><img src=x onerror=alert(1)>'
                 '<a href="javascript:alert(1)">l</a><svg><script>1</script></svg><iframe src="//x"></iframe>'
                 '<p style="background:url(//x)">b</p>')
        r = c.patch(f"/api/patienten/{self.patient.id}/", {"diagnose": boese}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        gespeichert = Patient.objects.get(pk=self.patient.pk).diagnose
        for teil in ("<script", "onerror", "onclick", "javascript:", "<img", "<svg", "<iframe", "style=", "<a "):
            self.assertNotIn(teil, gespeichert)

    def test_logo_svg_mit_skript_abgelehnt(self):
        c = client_fuer(self.mitarbeiter)
        for svg in (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                    b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>',
                    b'<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///etc/passwd"/></svg>',
                    b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg>&x;</svg>'):
            r = c.post("/api/briefkopf/logo/", {"datei": SimpleUploadedFile("l.svg", svg, "image/svg+xml")},
                       format="multipart")
            self.assertEqual(r.status_code, 400, svg)

    def test_dateiname_ohne_kopfzeilen_einschleusung(self):
        c = client_fuer(self.mitarbeiter)
        datei = SimpleUploadedFile('a"\r\nX-Boese: 1;../../etc/passwd.pdf', b"%PDF-1.4 x", "application/pdf")
        r = c.post("/api/dokumente/", {"patient": self.patient.id, "titel": "x", "datei": datei}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        from patienten.models import Dokument

        dok = Dokument.objects.get(pk=r.json()["id"])
        self.assertNotIn("..", dok.datei)
        self.assertTrue(dok.datei.startswith(f"{self.patient.nummer}/"))
        r = c.get(f"/api/dokumente/{dok.id}/datei/")
        self.assertNotIn("X-Boese", r.headers)
        self.assertNotIn("\n", r["Content-Disposition"])
        # nur PDF, JPG, PNG und Text – kein HTML, SVG oder ausführbares
        for name, inhalt in (("x.html", b"<html><script>alert(1)</script>"), ("x.svg", b"<svg onload=alert(1)>"),
                             ("x.exe", b"MZ\x90\x00\x03\x00\x00\x00")):
            r = c.post("/api/dokumente/", {"patient": self.patient.id, "titel": "x",
                                           "datei": SimpleUploadedFile(name, inhalt, "text/html")}, format="multipart")
            if r.status_code == 201:
                self.assertTrue(Dokument.objects.get(pk=r.json()["id"]).mime.startswith("text/plain"), name)
            else:
                self.assertEqual(r.status_code, 400, name)

    def test_fehler_ohne_details(self):
        c = client_fuer(self.mitarbeiter)
        c.raise_request_exception = False
        r = c.get("/api/patienten/999999/")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b"Traceback", r.content)
        r = c.post("/api/auth/anmelden/", {"benutzername": "gibtsnicht", "kennwort": "x"}, format="json")
        r2 = c.post("/api/auth/anmelden/", {"benutzername": "mitarbeiter", "kennwort": "x"}, format="json")
        # keine Unterscheidung zwischen unbekanntem Namen und falschem Passwort
        self.assertEqual((r.status_code, r.json()), (r2.status_code, r2.json()))


class PasswortHashes(SimpleTestCase):
    """Die Tests hashen mit MD5 (epm/testlauf.py) – im Betrieb muss es beim starken Django-Standard bleiben."""

    def test_betrieb_nutzt_pbkdf2(self):
        import epm.settings as betrieb
        from django.conf import global_settings

        hasher = getattr(betrieb, "PASSWORD_HASHERS", global_settings.PASSWORD_HASHERS)
        self.assertEqual(hasher[0], "django.contrib.auth.hashers.PBKDF2PasswordHasher")
        self.assertNotIn("MD5", " ".join(hasher))

    def test_testlauf_prueft_weiter_echt(self):
        """Auch mit dem schnellen Hasher: falsches Passwort scheitert, ein PBKDF2-Hash aus dem Betrieb gilt weiter."""
        from django.contrib.auth.hashers import check_password, make_password

        self.assertFalse(check_password("falsch", make_password(KENNWORT)))
        self.assertTrue(check_password(KENNWORT, make_password(KENNWORT, hasher="pbkdf2_sha256")))
