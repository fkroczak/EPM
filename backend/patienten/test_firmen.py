"""Zwei Firmen in einem EPM (Anforderung 11.10.2026): DSKM und Regeneration Clinic.

Geprüft mit echter Anmeldung (Sitzung), damit Umschalter, Middleware und Rechte zusammen laufen."""
from datetime import timedelta

from django.utils import timezone

from accounts.models import Mitgliedschaft, Rolle
from audit.models import SystemEreignis
from epm.pruefhilfen import Grundlage, benutzer, echte_anmeldung, mit_zweitem_faktor
from stammdaten.models import Firma, Logo

from .models import Erklaerung, Kontakt, Patient, PatientFirma


class Firmen(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dskm, cls.rg = Firma.objects.get(kuerzel="dskm"), Firma.objects.get(kuerzel="rg")
        # Person in beiden Firmen: bei der DSKM Betrachter, bei der RG Mediziner
        cls.beide = benutzer("beide", Rolle.BETRACHTER)
        Mitgliedschaft.objects.create(benutzer=cls.beide, firma=cls.rg, rolle=Rolle.MEDIZINER)
        # nur RG
        cls.nur_rg = benutzer("nurrg", Rolle.KEINE)
        Mitgliedschaft.objects.create(benutzer=cls.nur_rg, firma=cls.rg, rolle=Rolle.MITARBEITER)
        cls.rg_patient = Patient.objects.create(nachname="Klinik", vorname="Karla", geburtsdatum="1970-01-01")
        PatientFirma.objects.filter(patient=cls.rg_patient).update(firma=cls.rg)
        cls.geteilt = Patient.objects.create(nachname="Geteilt", vorname="Gerd", geburtsdatum="1960-01-01")
        PatientFirma.objects.create(patient=cls.geteilt, firma=cls.rg)

    def anmelden(self, user):
        codes = mit_zweitem_faktor(user, 1)
        return echte_anmeldung(user, codes[0])

    def ids(self, c):
        return {p["id"] for p in c.get("/api/patienten/").json()["results"]}

    def test_bestand_gehoert_der_dskm(self):
        # Akten ohne aktive Firma (vor den Firmen, Import, Befehle) gehören der DSKM
        self.assertEqual(list(PatientFirma.objects.filter(patient=self.patient).values_list("firma__kuerzel", flat=True)),
                         ["dskm"])

    def test_umschalter_und_sichtbarkeit(self):
        c = self.anmelden(self.beide)
        ich = c.get("/api/auth/status/").json()["benutzer"]
        self.assertEqual(ich["firma"], "dskm")
        self.assertEqual([(f["kuerzel"], f["rolle"]) for f in ich["firmen"]], [("dskm", "betrachter"), ("rg", "mediziner")])
        self.assertEqual(ich["rolle"], "betrachter")
        self.assertEqual(self.ids(c), {self.patient.id, self.geteilt.id})
        # Rechte richten sich nach der Rolle in der aktiven Firma
        self.assertNotIn("plaene_freigeben", ich["rechte"])
        r = c.post("/api/auth/firma/", {"firma": "rg"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        ich = r.json()["benutzer"]
        self.assertEqual((ich["firma"], ich["rolle"]), ("rg", "mediziner"))
        self.assertIn("plaene_freigeben", ich["rechte"])
        self.assertEqual(self.ids(c), {self.rg_patient.id, self.geteilt.id})
        # Akte der anderen Firma gibt es nicht
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/").status_code, 404)

    def test_ohne_zugang_kein_wechsel(self):
        c = self.anmelden(self.mitarbeiter)  # nur DSKM
        self.assertEqual(c.post("/api/auth/firma/", {"firma": "rg"}, format="json").status_code, 403)
        c = self.anmelden(self.nur_rg)
        ich = c.get("/api/auth/status/").json()["benutzer"]
        self.assertEqual((ich["firma"], [f["kuerzel"] for f in ich["firmen"]]), ("rg", ["rg"]))
        self.assertEqual(self.ids(c), {self.rg_patient.id, self.geteilt.id})

    def test_neue_akte_und_eintraege_in_der_aktiven_firma(self):
        c = self.anmelden(self.nur_rg)
        r = c.post("/api/patienten/", {"nachname": "Neu", "vorname": "Nora", "geburtsdatum": "1980-02-02"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.json()["id"]
        self.assertEqual(c.get(f"/api/patienten/{pid}/").json()["firmen"], ["rg"])
        r = c.post("/api/kontakte/", {"patient": self.geteilt.id, "text": "<p>Anruf</p>"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["firma_kurz"], "RGC")
        self.assertEqual(Kontakt.objects.get(pk=r.json()["id"]).firma, self.rg)

    def test_zweite_firma_nur_mit_einwilligung(self):
        c = self.anmelden(self.mitarbeiter)
        url = f"/api/patienten/{self.patient.id}/firmen/"
        r = c.post(url, {"firmen": ["dskm", "rg"]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("einwilligung_am", r.json())
        heute = str(timezone.localdate())
        r = c.post(url, {"firmen": ["dskm", "rg"], "einwilligung_am": heute}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["firmen"], r.json()["firmen_einwilligung"]), (["dskm", "rg"], True))
        self.assertTrue(Erklaerung.objects.filter(patient=self.patient, art=Erklaerung.Art.FIRMEN).exists())
        self.assertTrue(SystemEreignis.objects.filter(art=SystemEreignis.Art.AKTE_FIRMEN).exists())
        # mindestens eine Firma; Betrachter dürfen nicht zuordnen
        self.assertEqual(c.post(url, {"firmen": []}, format="json").status_code, 400)
        b = self.anmelden(self.betrachter)
        self.assertEqual(b.post(url, {"firmen": ["dskm"]}, format="json").status_code, 403)
        # widerrufen: eine weitere Firma kommt nicht mehr ohne neue Einwilligung dazu
        Erklaerung.objects.filter(patient=self.patient).update(widerrufen_am=timezone.localdate())
        c.post(url, {"firmen": ["dskm"]}, format="json")
        self.assertEqual(c.post(url, {"firmen": ["dskm", "rg"]}, format="json").status_code, 400)

    def test_anlegen_fuer_beide_firmen(self):
        c = self.anmelden(self.mitarbeiter)
        daten = {"nachname": "Beide", "vorname": "Berta", "geburtsdatum": "1975-03-03", "firmen": ["dskm", "rg"]}
        self.assertEqual(c.post("/api/patienten/", daten, format="json").status_code, 400)
        r = c.post("/api/patienten/", {**daten, "einwilligung_am": str(timezone.localdate() - timedelta(days=1))},
                   format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(c.get(f"/api/patienten/{r.json()['id']}/").json()["firmen"], ["dskm", "rg"])

    def test_import_nur_in_der_dskm(self):
        admin = benutzer("admin2", Rolle.ADMIN)
        Mitgliedschaft.objects.create(benutzer=admin, firma=self.rg, rolle=Rolle.ADMIN)
        c = self.anmelden(admin)
        self.assertIn("altdaten_importieren", c.get("/api/auth/status/").json()["benutzer"]["rechte"])
        rechte = c.post("/api/auth/firma/", {"firma": "rg"}, format="json").json()["benutzer"]["rechte"]
        self.assertNotIn("altdaten_importieren", rechte)
        self.assertEqual(c.get("/api/altimport/").status_code, 403)

    def test_rollen_je_firma_in_der_benutzerverwaltung(self):
        admin = benutzer("admin3", Rolle.ADMIN)
        c = self.anmelden(admin)
        r = c.patch(f"/api/benutzer/{self.mitarbeiter.id}/", {"firmenrollen": {"dskm": "mitarbeiter", "rg": "mediziner"}},
                    format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["firmenrollen"], {"dskm": "mitarbeiter", "rg": "mediziner"})
        self.assertEqual(Mitgliedschaft.objects.get(benutzer=self.mitarbeiter, firma=self.rg).rolle, Rolle.MEDIZINER)
        self.assertEqual(c.patch(f"/api/benutzer/{self.mitarbeiter.id}/", {"firmenrollen": {"rg": "chef"}},
                                 format="json").status_code, 400)

    def test_logo_je_firma(self):
        Logo.objects.create(datei="_system/a.svg", mime="image/svg+xml", sha256="a" * 64, firma=self.dskm)
        rg = Logo.objects.create(datei="_system/b.svg", mime="image/svg+xml", sha256="b" * 64, firma=self.rg)
        self.assertEqual(Logo.aktuell(self.rg), rg)
        self.assertNotEqual(Logo.aktuell(self.dskm), rg)

    def test_testdaten_mit_beiden_firmen(self):
        from .testdaten import testdaten_zuruecksetzen

        testdaten_zuruecksetzen()
        geteilt = Patient.objects.get(ist_test=True, nachname="Mustermann")
        self.assertEqual(sorted(geteilt.firmenzuordnung.values_list("firma__kuerzel", flat=True)), ["dskm", "rg"])
        self.assertEqual(set(Kontakt.objects.filter(patient=geteilt).values_list("firma__kuerzel", flat=True)), {"dskm", "rg"})
        aus_rg = Patient.objects.get(ist_test=True, nachname="Test")
        self.assertEqual(sorted(aus_rg.firmenzuordnung.values_list("firma__kuerzel", flat=True)), ["dskm", "rg"])
        kontakte = list(Kontakt.objects.filter(patient=aus_rg).values_list("firma__kuerzel", flat=True))
        self.assertEqual((kontakte.count("rg") > 1, kontakte.count("dskm")), (True, 1))
        self.assertTrue(Patient.objects.filter(ist_test=True, nachname="Musterfrau",
                                               firmenzuordnung__firma__kuerzel="dskm").exclude(
                                                   firmenzuordnung__firma__kuerzel="rg").exists())
        # Zurücksetzen entfernt auch die Historie der Zuordnung
        testdaten_zuruecksetzen()
        self.assertFalse(PatientFirma.history.filter(patient_id=geteilt.id).exists())

    def test_farben_je_firma(self):
        """Design je Firma (11.10.2026): Farben getrennt, Dichte und Schrift gemeinsam; Kurzname „RGC“."""
        c = self.anmelden(self.beide)
        c.patch("/api/auth/ich/", {"darstellung": {"schema": "individuell", "akzent": "petrol", "dichte": "kompakt"}},
                format="json")
        ich = c.post("/api/auth/firma/", {"firma": "rg"}, format="json").json()["benutzer"]
        self.assertEqual([f["kurzname"] for f in ich["firmen"]], ["DSKM", "RGC"])
        # in der RGC noch keine eigenen Farben: Standard (= Farben der Klinik), Dichte wie in der DSKM
        self.assertEqual((ich["darstellung"].get("schema", "standard"), ich["darstellung"]["dichte"]), ("standard", "kompakt"))
        r = c.patch("/api/auth/ich/", {"darstellung": {"schema": "individuell", "akzent": "salbei", "hintergrund": "salbei",
                                                       "dichte": "normal"}}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["darstellung"]["akzent"], r.json()["darstellung"]["dichte"]), ("salbei", "normal"))
        self.assertNotIn("firmen", r.json()["darstellung"])
        ich = c.post("/api/auth/firma/", {"firma": "dskm"}, format="json").json()["benutzer"]
        self.assertEqual((ich["darstellung"]["akzent"], ich["darstellung"]["dichte"]), ("petrol", "normal"))

    def test_pdf_logo_je_firma(self):
        import base64

        from epm.firma import setze_aktive_firma, zuruecksetzen
        from vorlagen.pdf import STANDARD_LOGO, STANDARD_LOGOS, logo_data_uri

        token = setze_aktive_firma(self.rg)
        try:
            self.assertEqual(base64.b64decode(logo_data_uri().split(",", 1)[1]), STANDARD_LOGOS["rg"].read_bytes())
        finally:
            zuruecksetzen(token)
        self.assertEqual(base64.b64decode(logo_data_uri().split(",", 1)[1]), STANDARD_LOGO.read_bytes())
