"""Doppelungsprüfung beim Anlegen (F15, erweitert 16.10.2026): Schreibweisen, vertauschte Namen, Tippfehler,
Tag/Monat vertauscht, abgeschlossene und eingeschränkte Akten, Grund und Rangfolge."""
from datetime import date, timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer

from .dubletten import GRUND, abstand, bewerte, namensteile, normalisiere
from .models import Patient

GEB = date(1960, 3, 7)


class NormalisierungTest(SimpleTestCase):
    """Reine Hilfsfunktionen ohne Datenbank."""

    def test_schreibweisen(self):
        self.assertEqual(normalisiere("Müller"), normalisiere("MUELLER"))
        self.assertEqual(normalisiere("Strauß"), "strauss")
        self.assertEqual(normalisiere("Lefèvre"), "lefevre")
        self.assertEqual(normalisiere("Müller-Lüdenscheidt"), normalisiere("Mueller Luedenscheidt"))
        self.assertEqual(normalisiere("von Bergen"), "bergen")
        self.assertEqual(normalisiere("van der Berg"), "berg")
        self.assertEqual(normalisiere("De"), "de")  # nur Zusatz: bleibt stehen
        self.assertEqual(namensteile("Müller-Lüdenscheidt"), ["mueller", "luedenscheidt"])

    def test_abstand(self):
        self.assertEqual(abstand("kitten", "sitting"), 3)
        self.assertEqual(abstand("schmidt", "schmitt"), 1)
        self.assertEqual(abstand("abc", "xyzabc", grenze=1), 2)

    def test_rang(self):
        self.assertEqual(bewerte("Müller", "Jörg", GEB, "Müller", "Jörg", GEB), 0)
        self.assertEqual(bewerte("Mueller", "Joerg", GEB, "Müller", "Jörg", GEB), 1)
        self.assertEqual(bewerte("Jörg", "Müller", GEB, "Müller", "Jörg", GEB), 2)
        self.assertEqual(bewerte("Müller", "Jörg", GEB, "Müller", "Jörg", date(1960, 7, 3)), 3)
        self.assertEqual(bewerte("Schmitt", "Klaus", GEB, "Schmidt", "Klaus", GEB), 4)
        self.assertEqual(bewerte("Hofmansthal", "Ulrike", GEB, "Hoffmannsthal", "Ulrike", GEB), 4)  # ab 8 Zeichen: 2
        self.assertIsNone(bewerte("Bauer", "Eva", GEB, "Kowalski", "Peter", GEB))
        self.assertIsNone(bewerte("Müller", "Jörg", GEB, "Müller", "Jörg", date(1960, 7, 4)))
        # Tag/Monat vertauscht nur bei gleichem vollständigem Namen
        self.assertIsNone(bewerte("Schmitt", "Klaus", GEB, "Schmidt", "Klaus", date(1960, 7, 3)))
        self.assertEqual(set(GRUND), set(range(7)))


class DoppelteApiTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        neu = lambda n, v, g=GEB, **k: Patient.objects.create(nachname=n, vorname=v, geburtsdatum=g, **k)
        cls.mueller = neu("Müller-Lüdenscheidt", "Jörg")
        cls.schmidt = neu("Schmidt", "Klaus", date(1971, 7, 3))
        cls.berg = neu("von Bergen", "Renée", date(1980, 1, 2), abgeschlossen_am=date(2020, 1, 1),
                       abschluss_anlass=Patient.Abschlussanlass.THERAPIE_BEENDET)
        cls.anders = neu("Kowalski", "Peter")
        cls.verborgen = neu("Geheimhaus", "Gerda", date(1966, 6, 16))
        Patient.objects.filter(pk=cls.verborgen.pk).update(eingeschraenkt_am=timezone.now())

    def frage(self, geb, nachname="", vorname="", user=None, **extra):
        r = client_fuer(user or self.mitarbeiter).get("/api/patienten/doppelte/", {
            "geburtsdatum": str(geb), "nachname": nachname, "vorname": vorname, **extra})
        self.assertEqual(r.status_code, 200, r.content)
        return r

    def test_bisheriger_vertrag(self):
        """Ohne ``hinweise`` weiter eine Liste wie die Patientenliste, nur um ``grund`` und ``rang`` erweitert."""
        daten = self.frage(self.patient.geburtsdatum, "Echtmann").json()
        self.assertEqual([p["id"] for p in daten], [self.patient.id])
        self.assertEqual(daten[0]["grund"], GRUND[5])
        for feld in ("nummer", "nachname", "vorname", "geburtsdatum", "ist_abgeschlossen"):
            self.assertIn(feld, daten[0])
        self.assertEqual(self.frage("", "Echt").json(), [])
        self.assertEqual(self.frage("kein-datum", "Echt").json(), [])

    def test_umlaute_und_doppelname(self):
        for nach, vor in [("Mueller", "Joerg"), ("MÜLLER", "jörg"), ("Lüdenscheidt", "Jörg"),
                          ("Mueller Luedenscheidt", "Jorg")]:
            ids = [p["id"] for p in self.frage(GEB, nach, vor).json()]
            self.assertIn(self.mueller.id, ids, (nach, vor))
        p = self.frage(GEB, "Mueller-Luedenscheidt", "Joerg").json()[0]
        self.assertEqual((p["id"], p["grund"], p["rang"]), (self.mueller.id, GRUND[1], 1))

    def test_exakt_zuerst(self):
        daten = self.frage(GEB, "Müller-Lüdenscheidt", "Jörg").json()
        self.assertEqual(daten[0]["id"], self.mueller.id)
        self.assertEqual(daten[0]["grund"], "gleicher Name und Geburtsdatum")
        self.assertEqual([p["rang"] for p in daten], sorted(p["rang"] for p in daten))

    def test_vertauscht(self):
        p = self.frage(GEB, "Jörg", "Müller-Lüdenscheidt").json()[0]
        self.assertEqual((p["id"], p["grund"]), (self.mueller.id, "Vor-/Nachname vertauscht"))

    def test_tippfehler(self):
        p = self.frage(date(1971, 7, 3), "Schmitt", "Klaus").json()
        self.assertEqual([(x["id"], x["grund"]) for x in p], [(self.schmidt.id, "ähnliche Schreibweise")])
        self.assertEqual(self.frage(date(1971, 7, 3), "Bauer", "Eva").json(), [])

    def test_tag_monat_vertauscht(self):
        p = self.frage(date(1971, 3, 7), "Schmidt", "Klaus").json()
        self.assertEqual([(x["id"], x["grund"]) for x in p], [(self.schmidt.id, "Tag/Monat vertauscht")])
        # nur bei gleichem vollständigem Namen
        self.assertEqual(self.frage(date(1971, 3, 7), "Schmidt", "Karl").json(), [])

    def test_abgeschlossene_akte_und_namenszusatz(self):
        p = self.frage(date(1980, 1, 2), "Bergen", "Renee").json()
        self.assertEqual([(x["id"], x["ist_abgeschlossen"], x["rang"]) for x in p], [(self.berg.id, True, 1)])

    def test_eingeschraenkte_akte_ohne_angaben(self):
        """Art. 18: weder in der Liste noch im Hinweis Name, Nummer oder Kennung der Akte."""
        geb = date(1966, 6, 16)
        r = self.frage(geb, "Geheimhaus", "Gerda")
        self.assertEqual(r.json(), [])
        r = self.frage(geb, "Geheimhaus", "Gerda", hinweise="1")
        daten = r.json()
        self.assertEqual(daten["treffer"], [])
        self.assertEqual(daten["eingeschraenkt"], "Es gibt eine eingeschränkte Akte mit gleichem Geburtsdatum.")
        text = r.content.decode()
        for verboten in ("Geheimhaus", "Gerda", f'"id":{self.verborgen.id}', str(self.verborgen.nummer)):
            self.assertNotIn(verboten, text.replace(" ", ""))
        # anderer Name: kein Hinweis; anderes Geburtsdatum: kein Hinweis
        self.assertIsNone(self.frage(geb, "Bauer", "Eva", hinweise="1").json()["eingeschraenkt"])
        self.assertIsNone(self.frage(date(1966, 6, 17), "Geheimhaus", "Gerda", hinweise="1").json()["eingeschraenkt"])

    def test_eingeschraenkte_akte_mit_einsicht_normal(self):
        from .models import Akteneinsicht

        Akteneinsicht.objects.create(patient=self.verborgen, benutzer=self.mitarbeiter, grund="Prüfung",
                                     bis=timezone.now() + timedelta(hours=1))
        daten = self.frage(date(1966, 6, 16), "Geheimhaus", "Gerda", hinweise="1").json()
        self.assertEqual([p["id"] for p in daten["treffer"]], [self.verborgen.id])
        self.assertIsNone(daten["eingeschraenkt"])

    def test_testpatienten_im_bereich(self):
        """Testpatienten wie bisher: Testbenutzer sehen nur Testpatienten, echte Akten nicht."""
        from epm.pruefhilfen import benutzer
        from accounts.models import Rolle

        test = Patient.objects.create(nachname="Müller", vorname="Jörg", geburtsdatum=GEB, ist_test=True)
        tester = benutzer("tester_dubletten", Rolle.MITARBEITER, ist_test=True)
        ids = [p["id"] for p in self.frage(GEB, "Mueller", "Joerg", user=tester).json()]
        self.assertEqual(ids, [test.id])
