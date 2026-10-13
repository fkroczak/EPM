"""Mitgelieferte Vorlagen der Regeneration Clinic (13.10.2026): angelegt, gültig, nur in der Firma RGC sichtbar."""
from datetime import date

from accounts.models import Mitgliedschaft, Rolle
from epm.firma import setze_aktive_firma, zuruecksetzen
from epm.pruefhilfen import Grundlage, client_fuer, echte_anmeldung, mit_zweitem_faktor
from patienten.models import Patient, PatientFirma
from stammdaten.models import Firma

from .bloecke import pruefe_bloecke
from .felder import Kontext
from .models import Dokumentvorlage, EigenesSchreiben
from .pdf import bloecke_html, erzeuge_aus_vorlage
from .rgc import vorlagen
from .tests import kompakt, pdf_text


class RgcVorlagenTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rg = Firma.objects.get(kuerzel="rg")
        Mitgliedschaft.objects.create(benutzer=cls.admin, firma=cls.rg, rolle=Rolle.ADMIN)

    def test_alle_vorlagen_angelegt_und_gueltig(self):
        quellen = vorlagen()
        self.assertEqual(len(quellen), 19)
        rgc = EigenesSchreiben.objects.filter(firma=self.rg)
        self.assertEqual(rgc.count(), 19)
        self.assertEqual(rgc.filter(gruppe="anforderungen").count(), 14)
        self.assertEqual(rgc.filter(gruppe="formulare").count(), 5)
        for e in rgc:
            v = Dokumentvorlage.objects.get(art=e.schluessel, status="aktiv")
            self.assertEqual(pruefe_bloecke(e.schluessel, v.bloecke), [], e.name)

    def test_nur_in_der_firma_rgc(self):
        c = echte_anmeldung(self.admin, mit_zweitem_faktor(self.admin, 1)[0])
        namen = {v["name"] for v in c.get("/api/vorlagen/").json()}
        self.assertNotIn("Laboranforderung Basislabor", namen)  # in der DSKM nicht zu sehen
        self.assertNotIn("Laboranforderung Basislabor", {v["name"] for v in client_fuer(self.admin).get("/api/vorlagen/").json()})
        self.assertEqual(c.get("/api/vorlagen/eigen-rgc-a01/").status_code, 404)
        self.assertEqual(c.post("/api/auth/firma/", {"firma": "rg"}, format="json").status_code, 200)
        liste = {v["name"]: v for v in c.get("/api/vorlagen/").json()}
        self.assertEqual(liste["Laboranforderung Basislabor"]["gruppe"], "anforderungen")
        self.assertEqual(liste["Aufklärung Operation (DE/LV)"]["gruppe"], "formulare")
        schreiben = {s["name"]: s for s in c.get("/api/schreiben/").json()}
        self.assertEqual(schreiben["MRT-Anforderung"]["gruppe_name"],
                         "Anforderungen: Labor, Bildgebung, Funktionsdiagnostik")
        # neu angelegte eigene Vorlagen gehören der aktiven Firma
        r = c.post("/api/vorlagen/", {"name": "Laborbrief RGC"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(EigenesSchreiben.objects.get(name="Laborbrief RGC").firma, self.rg)

    def test_pdf_mit_patientendaten(self):
        token = setze_aktive_firma(self.rg)
        try:
            p = Patient.objects.create(nachname="Bērziņa", vorname="Ilze", geschlecht="w", nummer=4711,
                                       geburtsdatum=date(1970, 5, 3))
            PatientFirma.objects.filter(patient=p).update(firma=self.rg)
            pdf, version = erzeuge_aus_vorlage("eigen-rgc-a01", Kontext(patient=p), titel="Basislabor")
            text = kompakt(pdf_text(pdf))
            self.assertEqual(version, 1)
            for erwartet in ("Bērziņa, Ilze", "4711", "Basislabor", "Retikulozyten", "Regeneration Clinic SIA"):
                self.assertIn(kompakt(erwartet), text)
            pdf, _ = erzeuge_aus_vorlage("eigen-rgc-f07", Kontext(patient=p), titel="Aufklärung")
            self.assertIn(kompakt("16. Einwilligungserklärung · Piekrišanas apliecinājums"), kompakt(pdf_text(pdf)))
        finally:
            zuruecksetzen(token)

    def test_text_in_spalten(self):
        p = Patient(nachname="A", vorname="B")
        b = [{"id": "t", "typ": "text", "text": "☐ a\n☐ b\n☐ c", "optionen": {"spalten": 3}}]
        self.assertEqual(pruefe_bloecke("eigen-x", b), [])
        self.assertIn("sp-3", bloecke_html("eigen-x", b, Kontext(patient=p))[0])
        b[0]["optionen"]["spalten"] = 4
        self.assertTrue(pruefe_bloecke("eigen-x", b))
