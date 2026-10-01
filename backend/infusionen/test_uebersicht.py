"""Menüpunkt „Infusionspläne“: alle Pläne aller Patienten mit Gruppen und Suche (echte Datenbank)."""
from datetime import timedelta

from django.utils import timezone

from accounts.models import Rolle
from audit.schutz import wartungsmodus
from epm.pruefhilfen import Grundlage, benutzer, client_fuer
from patienten.models import Patient

from .models import Infusionsplan


class Uebersicht(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.zweiter = Patient.objects.create(nachname="Zweit", vorname="Zora", geburtsdatum="1980-02-02")
        cls.test = Patient.objects.create(nachname="Probe", vorname="Tom", geburtsdatum="1970-01-01", ist_test=True)
        cls.alt = Infusionsplan.neuer_entwurf(cls.patient, cls.mediziner)
        cls.alt.freigeben(cls.mediziner)
        with wartungsmodus():
            Infusionsplan.objects.filter(pk=cls.alt.pk).update(gueltig_ab=timezone.localdate() - timedelta(days=500))
        cls.entwurf = Infusionsplan.neuer_entwurf(cls.zweiter, cls.mediziner)
        cls.testentwurf = Infusionsplan.neuer_entwurf(cls.test, cls.mediziner)

    def test_gruppen_und_suche(self):
        c = client_fuer(self.betrachter)
        d = c.get("/api/infusionsplaene/uebersicht/", {"gruppe": "entwuerfe"}).json()
        self.assertEqual(d["zaehler"]["entwuerfe"], 2)
        self.assertEqual(d["zaehler"]["aktuell"], 1)
        self.assertEqual(d["zaehler"]["alt"], 1)
        self.assertEqual(d["grenze_monate"], 12)
        self.assertEqual({z["id"] for z in d["ergebnisse"]}, {self.entwurf.id, self.testentwurf.id})
        zeile = c.get("/api/infusionsplaene/uebersicht/", {"gruppe": "alt"}).json()["ergebnisse"][0]
        self.assertEqual(zeile["id"], self.alt.id)
        self.assertTrue(zeile["aelter_als_grenze"])
        self.assertTrue(zeile["pdf"])
        self.assertEqual(zeile["name"], "Echt, Anna")
        self.assertEqual(zeile["freigegeben_von"], self.mediziner.anzeigename)
        d = c.get("/api/infusionsplaene/uebersicht/", {"gruppe": "alle", "suche": "zwei"}).json()
        self.assertEqual([z["id"] for z in d["ergebnisse"]], [self.entwurf.id])
        d = c.get("/api/infusionsplaene/uebersicht/", {"gruppe": "alle", "suche": str(self.zweiter.nummer)}).json()
        self.assertEqual([z["id"] for z in d["ergebnisse"]], [self.entwurf.id])
        self.assertEqual(c.get("/api/infusionsplaene/uebersicht/", {"gruppe": "x"}).status_code, 400)

    def test_abgeschlossene_und_testzugang(self):
        Patient.objects.filter(pk=self.zweiter.pk).update(abgeschlossen_am=timezone.now(),
                                                          abschluss_anlass=Patient.Abschlussanlass.THERAPIE_BEENDET)
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.get("/api/infusionsplaene/uebersicht/", {"gruppe": "entwuerfe"}).json()["zaehler"]
                         ["entwuerfe"], 1)
        d = c.get("/api/infusionsplaene/uebersicht/", {"gruppe": "entwuerfe", "abgeschlossene": 1}).json()
        self.assertEqual(d["zaehler"]["entwuerfe"], 2)
        tester = client_fuer(benutzer("tester", Rolle.MEDIZINER, ist_test=True))
        d = tester.get("/api/infusionsplaene/uebersicht/", {"gruppe": "alle"}).json()
        self.assertEqual([z["id"] for z in d["ergebnisse"]], [self.testentwurf.id])
