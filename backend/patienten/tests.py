"""
Prüft die fachlichen Regeln gegen die echte PostgreSQL-Datenbank.

Aufruf im Container:
    sudo docker compose run --rm backend python manage.py test
"""
import tempfile
from pathlib import Path
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from accounts.models import Rolle, User
from audit.models import SystemEreignis, protokolliere
from infusionen.models import Infusionsplan
from stammdaten.models import Praeparat

from .models import Gewichtsmessung, Kontakt, Patient
from .testdaten import stammdaten_anlegen, testdaten_zuruecksetzen, testpatienten_anlegen

TMP = tempfile.mkdtemp(prefix="epm-test-")


def benutzer(name, rolle, ist_test=False):
    u = User(username=name, first_name=name.title(), last_name="Tester", rolle=rolle, ist_test=ist_test,
             muss_kennwort_aendern=False)
    u.set_password("ein-sicheres-Kennwort-123")
    u.save()
    return u


def client_fuer(user):
    """API-Client mit vollständiger Anmeldung (Kennwort + zweiter Faktor)."""
    c = APIClient()
    user.is_verified = lambda: True
    c.force_authenticate(user)
    return c


@override_settings(EPM_DOKUMENTE=Path(TMP), EPM_X_ACCEL=True)
class Grundlage(TestCase):
    @classmethod
    def setUpTestData(cls):
        stammdaten_anlegen()
        cls.mitarbeiter = benutzer("mitarbeiter", Rolle.MITARBEITER)
        cls.mediziner = benutzer("mediziner", Rolle.MEDIZINER)
        cls.betrachter = benutzer("betrachter", Rolle.BETRACHTER)
        cls.admin = benutzer("admin", Rolle.ADMIN)
        cls.patient = Patient.objects.create(nachname="Echt", vorname="Anna",
                                             geburtsdatum=timezone.localdate() - timedelta(days=20000))

    def neuer_kontakt(self, client=None, patient=None):
        c = client or client_fuer(self.mitarbeiter)
        r = c.post("/api/kontakte/", {"patient": (patient or self.patient).id, "text": "<p>Hallo <script>x</script></p>"},
                   format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()


class KontaktRegeln(Grundlage):
    def test_text_wird_bereinigt(self):
        k = self.neuer_kontakt()
        self.assertNotIn("script", k["text"])

    def test_kontakt_nicht_aenderbar(self):
        k = self.neuer_kontakt()
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.patch(f"/api/kontakte/{k['id']}/", {"text": "neu"}, format="json").status_code, 405)
        self.assertEqual(c.delete(f"/api/kontakte/{k['id']}/").status_code, 405)
        obj = Kontakt.objects.get(pk=k["id"])
        obj.text = "geändert"
        with self.assertRaises(PermissionError):
            obj.save()

    def test_trigger_verhindert_aenderung_in_der_datenbank(self):
        k = self.neuer_kontakt()
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("UPDATE patienten_kontakt SET text = 'x' WHERE id = %s", [k["id"]])

    def test_storno_genau_einmal(self):
        k = self.neuer_kontakt()
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.post(f"/api/kontakte/{k['id']}/storno/", {"grund": ""}, format="json").status_code, 400)
        r = c.post(f"/api/kontakte/{k['id']}/storno/", {"grund": "falscher Patient"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["storno_grund"], "falscher Patient")
        self.assertEqual(c.post(f"/api/kontakte/{k['id']}/storno/", {"grund": "nochmal"}, format="json").status_code, 400)


class Revisionssicherheit(Grundlage):
    def test_historie_ist_unveraenderlich(self):
        protokolliere(SystemEreignis.Art.EXPORT, benutzername="test")  # damit das Protokoll nicht leer ist
        self.patient.diagnose = "<p>neu</p>"
        self.patient.save()
        for sql in ("UPDATE patienten_historicalpatient SET nachname = 'x'",
                    "DELETE FROM patienten_historicalpatient",
                    "DELETE FROM audit_systemereignis"):
            with self.subTest(sql=sql), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(sql)

    def test_verlauf_zeigt_person_und_aenderung(self):
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"/api/patienten/{self.patient.id}/", {"therapie": "<p>Neue Therapie</p>"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        v = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=stammdaten").json()
        self.assertEqual(v[0]["art"], "geändert")
        self.assertEqual(v[0]["person"], self.mitarbeiter.anzeigename)
        self.assertIn("therapie", [a["feld"] for a in v[0]["aenderungen"]])


class Akte(Grundlage):
    def test_abgeschlossene_akte_ist_gesperrt(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post(f"/api/patienten/{self.patient.id}/abschliessen/", {"anlass": "verstorben"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        r = c.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "60.0"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(c.patch(f"/api/patienten/{self.patient.id}/", {"ort": "x"}, format="json").status_code, 409)
        # Wieder öffnen nur Admin, mit Grund
        self.assertEqual(c.post(f"/api/patienten/{self.patient.id}/wieder-oeffnen/", {"grund": "x"}, format="json").status_code, 403)
        a = client_fuer(self.admin)
        self.assertEqual(a.post(f"/api/patienten/{self.patient.id}/wieder-oeffnen/", {}, format="json").status_code, 400)
        self.assertEqual(a.post(f"/api/patienten/{self.patient.id}/wieder-oeffnen/", {"grund": "Irrtum"}, format="json").status_code, 200)

    def test_plausibilitaet_gewicht(self):
        c = client_fuer(self.mitarbeiter)
        for kg in ("0", "9999"):
            r = c.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": kg}, format="json")
            self.assertEqual(r.status_code, 400, kg)

    def test_gewichtswarnung(self):
        heute = timezone.localdate()
        for tage, kg in [(120, "70.0"), (95, "70.0"), (0, "65.0")]:
            Gewichtsmessung.objects.create(patient=self.patient, gewicht_kg=Decimal(kg),
                                           gemessen_am=heute - timedelta(days=tage))
        trend = self.patient.gewichtstrend()
        self.assertTrue(trend["warnung"])
        self.assertEqual(trend["prozent"], Decimal("-7.1"))

    def test_doppelte(self):
        c = client_fuer(self.mitarbeiter)
        r = c.get(f"/api/patienten/doppelte/?geburtsdatum={self.patient.geburtsdatum}&nachname=Echtmann")
        self.assertEqual([p["id"] for p in r.json()], [self.patient.id])

    def test_nummern(self):
        p = Patient.objects.create(nachname="B", vorname="C", geburtsdatum="1970-01-01")
        t = Patient.objects.create(nachname="T", vorname="T", geburtsdatum="1970-01-01", ist_test=True)
        self.assertEqual(p.nummer, self.patient.nummer + 1)
        self.assertEqual(t.nummer, 9001)

    def test_dokument_upload_und_download(self):
        c = client_fuer(self.mitarbeiter)
        datei = SimpleUploadedFile("brief.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = c.post("/api/dokumente/", {"patient": self.patient.id, "titel": "Brief", "datei": datei}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.json()["sha256"]), 64)
        d = c.get(f"/api/dokumente/{r.json()['id']}/datei/")
        self.assertTrue(d["X-Accel-Redirect"].startswith("/_geschuetzt/dokumente/"))


class Rollen(Grundlage):
    def test_schreibrechte(self):
        daten = {"nachname": "Neu", "vorname": "Nora", "geburtsdatum": "1980-02-02"}
        self.assertEqual(client_fuer(self.betrachter).post("/api/patienten/", daten, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.admin).post("/api/patienten/", daten, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.mitarbeiter).post("/api/patienten/", daten, format="json").status_code, 201)
        self.assertEqual(client_fuer(self.betrachter).get("/api/patienten/").status_code, 200)

    def test_nur_admin_verwaltet_benutzer(self):
        self.assertEqual(client_fuer(self.mediziner).get("/api/benutzer/").status_code, 403)
        r = client_fuer(self.admin).post("/api/benutzer/", {"username": "neu", "rolle": "mitarbeiter",
                                                             "first_name": "N", "last_name": "N"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("einmal_kennwort", r.json())

    def test_ohne_zweiten_faktor_kein_zugriff(self):
        c = APIClient()
        c.force_authenticate(self.mitarbeiter)  # kein is_verified
        self.assertEqual(c.get("/api/patienten/").status_code, 403)

    def test_testbenutzer_sieht_nur_testpatienten(self):
        tester = benutzer("tester", Rolle.MEDIZINER, ist_test=True)
        testpat = Patient.objects.create(nachname="T", vorname="T", geburtsdatum="1970-01-01", ist_test=True)
        r = client_fuer(tester).get("/api/patienten/").json()
        self.assertEqual([p["id"] for p in r["results"]], [testpat.id])
        self.assertEqual(client_fuer(tester).get(f"/api/patienten/{self.patient.id}/").status_code, 404)
        r = client_fuer(tester).post("/api/kontakte/", {"patient": self.patient.id, "text": "x"}, format="json")
        self.assertEqual(r.status_code, 400)


class Infusionsplaene(Grundlage):
    def plan_daten(self):
        p = Praeparat.objects
        return {
            "glucose_praeparat": p.get(name="Glucose", konzentration="50 %").id, "glucose_g": "200",
            "aminosaeuren_praeparat": p.get(name="Aminoplasmal").id, "aminosaeuren_g": "70",
            "lipide_praeparat": p.get(name="SMOFlipid").id, "lipide_g": "40",
            "positionen": [{"praeparat": p.get(name="Cernevit").id, "menge": "10", "einheit": "ml"}],
        }

    def test_ablauf(self):
        c = client_fuer(self.mediziner)
        self.assertEqual(client_fuer(self.mitarbeiter).post("/api/infusionsplaene/entwurf/",
                                                            {"patient": self.patient.id}, format="json").status_code, 403)
        e1 = c.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id}, format="json").json()
        r = c.patch(f"/api/infusionsplaene/{e1['id']}/", self.plan_daten(), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["kcal"], 200 * 4 + 70 * 4 + 40 * 9)
        self.assertEqual(c.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id}, format="json").status_code, 400)
        self.assertEqual(c.post(f"/api/infusionsplaene/{e1['id']}/freigeben/").status_code, 200)
        # freigegeben → unveränderlich
        self.assertEqual(c.patch(f"/api/infusionsplaene/{e1['id']}/", {"glucose_g": "1"}, format="json").status_code, 403)
        # neuer Entwurf ist vorbelegt, Änderungen werden markiert
        e2 = c.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id}, format="json").json()
        self.assertEqual(e2["glucose_g"], 200)
        self.assertEqual(len(e2["positionen"]), 1)
        r = c.patch(f"/api/infusionsplaene/{e2['id']}/", {"glucose_g": "150"}, format="json").json()
        self.assertEqual(r["geaenderte_felder"], ["glucose_g"])
        c.post(f"/api/infusionsplaene/{e2['id']}/freigeben/")
        status = dict(Infusionsplan.objects.filter(patient=self.patient).values_list("id", "status"))
        self.assertEqual(status, {e1["id"]: "abgeloest", e2["id"]: "aktuell"})

    def test_kcal_manuell_und_grenze(self):
        c = client_fuer(self.mediziner)
        e = c.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id}, format="json").json()
        self.assertEqual(c.patch(f"/api/infusionsplaene/{e['id']}/", {"kcal_manuell": 1800}, format="json").json()["kcal"], 1800)
        self.assertEqual(c.patch(f"/api/infusionsplaene/{e['id']}/", {"kcal_manuell": 433564}, format="json").status_code, 400)


class Anmeldung(TestCase):
    def setUp(self):
        cache.clear()  # Drosselung der Anmeldung zurücksetzen
        self.user = User(username="neu", first_name="Nina", last_name="Neu", rolle=Rolle.MITARBEITER)
        self.kennwort = self.user.neues_einmal_kennwort()
        self.user.save()
        self.c = APIClient(enforce_csrf_checks=False)

    def test_erstanmeldung(self):
        r = self.c.post("/api/auth/anmelden/", {"benutzername": "neu", "kennwort": self.kennwort}, format="json")
        self.assertEqual(r.json()["schritt"], "kennwort_aendern")
        self.assertEqual(self.c.get("/api/patienten/").status_code, 403)
        # 2FA darf erst nach eigenem Kennwort eingerichtet werden
        self.assertEqual(self.c.post("/api/auth/2fa/einrichten/").status_code, 403)
        r = self.c.post("/api/auth/kennwort/", {"neu": "Ein-langes-neues-Kennwort-42"}, format="json")
        self.assertEqual(r.json()["schritt"], "2fa_einrichten")
        r = self.c.post("/api/auth/2fa/einrichten/")
        self.assertIn("<svg", r.json()["qr_svg"])
        geraet = TOTPDevice.objects.get(user=self.user)
        code = f"{totp(geraet.bin_key, geraet.step, geraet.t0, geraet.digits):06d}"
        r = self.c.post("/api/auth/2fa/bestaetigen/", {"code": code}, format="json")
        self.assertEqual(r.json()["schritt"], "fertig", r.content)
        self.assertEqual(len(r.json()["notfallcodes"]), 10)
        self.assertEqual(self.c.get("/api/patienten/").status_code, 200)
        # nächste Anmeldung: Kennwort + Notfallcode
        self.c.post("/api/auth/abmelden/")
        self.c.post("/api/auth/anmelden/", {"benutzername": "neu", "kennwort": "Ein-langes-neues-Kennwort-42"}, format="json")
        self.assertEqual(self.c.get("/api/auth/status/").json()["schritt"], "2fa")
        r = self.c.post("/api/auth/2fa/", {"code": r.json()["notfallcodes"][0]}, format="json")
        self.assertEqual(r.json()["schritt"], "fertig")

    def test_sperre_nach_fehlversuchen(self):
        for _ in range(5):
            self.assertEqual(self.c.post("/api/auth/anmelden/", {"benutzername": "neu", "kennwort": "falsch"},
                                         format="json").status_code, 401)
        r = self.c.post("/api/auth/anmelden/", {"benutzername": "neu", "kennwort": self.kennwort}, format="json")
        self.assertEqual(r.status_code, 429)
        self.assertEqual(SystemEreignis.objects.filter(art="anmeldung_fehlgeschlagen").count(), 5)


@override_settings(EPM_DOKUMENTE=Path(TMP))
class Musterdaten(TestCase):
    def test_anlegen_und_zuruecksetzen(self):
        call_command("epm_musterdaten", stdout=open("/dev/null", "w"))
        self.assertEqual(Patient.objects.filter(ist_test=True).count(), 6)
        self.assertTrue(Infusionsplan.objects.filter(status="entwurf").exists())
        self.assertEqual(testpatienten_anlegen(), 0)  # wiederholbar
        r = testdaten_zuruecksetzen()
        self.assertEqual(r, {"geloescht": 6, "angelegt": 6})
        tester = User.objects.get(username="test")
        tester.muss_kennwort_aendern = False  # Einmal-Kennwort gilt hier als bereits ersetzt
        start = client_fuer(tester).get("/api/startseite/").json()
        self.assertTrue(start["gewichtswarnungen"])
        self.assertTrue(start["termine"]["ueberfaellig"])
        self.assertTrue(start["infusionsplaene"]["aelter_als_grenze"])
