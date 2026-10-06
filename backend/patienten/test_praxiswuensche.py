"""Wünsche aus der Praxis vom 06.10.2026: Diagnosen mit ICD (F117), Versichertendaten (F118),
Infusionstage je Beutelart (F110) und das Sprechstundenblatt (F116)."""
import shutil
import unittest
from datetime import timedelta

from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer
from stammdaten.models import Diagnosevorlage, Praeparat

from .models import Diagnose


class DiagnosenTest(Grundlage):
    def anlegen(self, client=None, **extra):
        c = client or client_fuer(self.mitarbeiter)
        daten = {"patient": self.patient.id, "bezeichnung": "Kurzdarmsyndrom", "icd_code": "K91.2",
                 "kennzeichen": "G", **extra}
        return c.post("/api/diagnosen/", daten, format="json")

    def test_anzeige_mit_icd_und_kennzeichen(self):
        r = self.anlegen()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["anzeige"], "Kurzdarmsyndrom [K91.2G]")

    def test_katalog_waechst_mit(self):
        """Die Liste im Hintergrund füllt sich beim Eintragen von allein (U53)."""
        self.anlegen()
        self.anlegen(bezeichnung="Osteoporose", icd_code="M81.99", kennzeichen="G")
        self.assertEqual(
            sorted(Diagnosevorlage.objects.values_list("icd_code", "bezeichnung")),
            [("K91.2", "Kurzdarmsyndrom"), ("M81.99", "Osteoporose")],
        )
        # dieselbe Diagnose erneut erzeugt keinen zweiten Katalogeintrag
        self.anlegen()
        self.assertEqual(Diagnosevorlage.objects.count(), 2)

    def test_icd_format_wird_geprueft(self):
        for falsch in ("K912", "91.2", "K91.222", "Kurzdarm"):
            r = self.anlegen(icd_code=falsch)
            self.assertEqual(r.status_code, 400, f"{falsch}: {r.content}")

    def test_kleinschreibung_wird_vereinheitlicht(self):
        r = self.anlegen(icd_code="k91.2")
        self.assertEqual(r.json()["icd_code"], "K91.2")

    def test_nicht_mehr_zutreffend_statt_loeschen(self):
        d = self.anlegen().json()
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"/api/diagnosen/{d['id']}/", {"aktiv": False}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["beendet_am"], timezone.localdate().isoformat())
        self.assertEqual(c.delete(f"/api/diagnosen/{d['id']}/").status_code, 405)
        self.assertEqual(Diagnose.objects.count(), 1)

    def test_freitextfeld_bleibt_daneben_bestehen(self):
        """Die strukturierte Liste ersetzt das lange Diagnosefeld nicht (U51)."""
        self.anlegen()
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"/api/patienten/{self.patient.id}/", {"diagnose": "<p>Ausführlicher Text</p>"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("Ausführlicher Text", r.json()["diagnose"])
        self.assertEqual(self.patient.diagnosen.count(), 1)

    def test_betrachter_darf_nicht_eintragen(self):
        self.assertEqual(self.anlegen(client_fuer(self.betrachter)).status_code, 403)


class VersichertendatenTest(Grundlage):
    def test_art_versicherung_und_nummer(self):
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"/api/patienten/{self.patient.id}/",
                    {"versicherungsart": "gkv", "krankenkasse": "AOK NordWest",
                     "versichertennummer": "A123456789"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual((d["versicherungsart"], d["krankenkasse"], d["versichertennummer"]),
                         ("gkv", "AOK NordWest", "A123456789"))

    def test_unbekannte_art_abgelehnt(self):
        r = client_fuer(self.mitarbeiter).patch(f"/api/patienten/{self.patient.id}/",
                                                {"versicherungsart": "privatpatient"}, format="json")
        self.assertEqual(r.status_code, 400, r.content)


class InfusionstageTest(Grundlage):
    def plan(self, **extra):
        c = client_fuer(self.mediziner)
        c.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "60.0"}, format="json")
        e = c.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id}, format="json").json()
        r = c.patch(f"/api/infusionsplaene/{e['id']}/", {"laufzeit_h": "12", **extra}, format="json")
        return c, e, r

    def test_tage_je_beutelart(self):
        """PE 5× / Woche, Zusatzvolumen 2× / Woche, keine infusionsfreien Tage (F110)."""
        c, e, r = self.plan(tage_pro_woche=5, zusatz_tage_pro_woche=2, freie_tage_pro_woche=0)
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual((d["tage_pro_woche"], d["zusatz_tage_pro_woche"], d["freie_tage_pro_woche"]), (5, 2, 0))

    def test_zu_viele_freie_tage_abgelehnt(self):
        c, e, r = self.plan(tage_pro_woche=5, freie_tage_pro_woche=4)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("höchstens 2", str(r.content, "utf-8"))

    def test_werte_wandern_in_den_folgeplan(self):
        """Beim neuen Plan sind die Werte des aktuellen schon eingetragen – auch die neuen Felder."""
        c, e, r = self.plan(tage_pro_woche=5, zusatz_tage_pro_woche=2, freie_tage_pro_woche=0)
        c.post(f"/api/infusionsplaene/{e['id']}/freigeben/")
        neu = c.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id}, format="json").json()
        self.assertEqual((neu["tage_pro_woche"], neu["zusatz_tage_pro_woche"], neu["freie_tage_pro_woche"]), (5, 2, 0))

    def test_vergleich_zeigt_die_neuen_zeilen(self):
        c, e, r = self.plan(tage_pro_woche=5, zusatz_tage_pro_woche=2, freie_tage_pro_woche=0)
        c.post(f"/api/infusionsplaene/{e['id']}/freigeben/")
        neu = c.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id}, format="json").json()
        c.patch(f"/api/infusionsplaene/{neu['id']}/", {"zusatz_tage_pro_woche": 3}, format="json")
        zeilen = {z["schluessel"]: z for z in
                  c.get(f"/api/infusionsplaene/{neu['id']}/vergleich/").json()["zeilen"]}
        self.assertEqual(zeilen["zusatz_tage_pro_woche"]["vorher"], "2 × pro Woche")
        self.assertEqual(zeilen["zusatz_tage_pro_woche"]["jetzt"], "3 × pro Woche")
        self.assertTrue(zeilen["zusatz_tage_pro_woche"]["geaendert"])
        self.assertEqual(zeilen["freie_tage_pro_woche"]["jetzt"], "keine")


class PraeparateTest(Grundlage):
    def test_zusatzvolumen_nach_der_mail(self):
        namen = set(Praeparat.objects.filter(kategorie=Praeparat.Kategorie.BASISLOESUNG, aktiv=True)
                    .values_list("name", flat=True))
        self.assertTrue({"Sterofundin ISO", "Ringer-Lösung", "Ringer-Lactat", "NaCl", "Jonosteril"} <= namen, namen)

    def test_natrovit_und_taurolidin_mit_hinweis(self):
        natrovit = Praeparat.objects.get(name="Natrovit")
        self.assertEqual(natrovit.kategorie, Praeparat.Kategorie.VITAMINE)
        self.assertIn("Cernevit", natrovit.hinweis)
        self.assertEqual(Praeparat.objects.get(name="NutriLock").hinweis, "reines Taurolidin 2 %")
        self.assertEqual(Praeparat.objects.get(name="TauroLock").hinweis, "Taurolidin mit Citrat")

    def test_dipeptamin_und_omegaven_nicht_mehr_waehlbar(self):
        self.assertFalse(Praeparat.objects.filter(name__iexact="Dipeptamin", aktiv=True).exists())
        self.assertFalse(Praeparat.objects.filter(name__iexact="Omegaven", aktiv=True).exists())


class SprechstundeTest(Grundlage):
    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext fehlt")
    def test_blatt_buendelt_den_aktuellen_stand(self):
        from vorlagen.tests import kompakt, pdf_text

        c = client_fuer(self.mediziner)
        c.post("/api/diagnosen/", {"patient": self.patient.id, "bezeichnung": "Kurzdarmsyndrom",
                                   "icd_code": "K91.2", "kennzeichen": "G"}, format="json")
        c.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "60.0"}, format="json")
        c.post("/api/bia-messungen/", {"patient": self.patient.id, "gemessen_am": "2026-10-01",
                                       "bcm_kg": "24.1", "ecw_prozent": "46.2",
                                       "beurteilung": "<p>Zellmasse stabil</p>"}, format="json")
        from stammdaten.models import Laborparameter

        ferritin = Laborparameter.objects.get(name="Ferritin")
        c.post("/api/laborbefunde/", {"patient": self.patient.id, "abgenommen_am": "2026-10-02",
                                      "labor": "Labor Dr. Wagner",
                                      "werte": [{"parameter": ferritin.id, "wert": "18"}]}, format="json")
        c.patch(f"/api/patienten/{self.patient.id}/", {"empfehlung": "<p>Eisen oral ergänzen</p>"}, format="json")

        r = c.get(f"/api/patienten/{self.patient.id}/sprechstunde/")
        self.assertEqual(r.status_code, 200, r.content)
        text = kompakt(pdf_text(r.content))
        for erwartet in ("Unterlagen für die Sprechstunde", "Kurzdarmsyndrom", "K91.2G", "Ferritin",
                         "Labor Dr. Wagner", "Zellmasse stabil", "Eisen oral ergänzen"):
            self.assertIn(kompakt(erwartet), text, erwartet)

    def test_ablegen_erzeugt_ein_dokument(self):
        c = client_fuer(self.mediziner)
        c.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "60.0"}, format="json")
        r = c.get(f"/api/patienten/{self.patient.id}/sprechstunde/?ablegen=1")
        self.assertEqual(r.status_code, 200, r.content)
        dok = self.patient.dokumente.get()
        self.assertEqual(dok.typ.wert, "Sprechstunde")
        self.assertTrue(dok.titel.startswith("Unterlagen für die Sprechstunde"))

    def test_abgeschlossene_akte_nur_ansehen(self):
        self.patient.abgeschlossen_am = timezone.localdate() - timedelta(days=1)
        self.patient.abschluss_anlass = self.patient.Abschlussanlass.THERAPIE_BEENDET
        self.patient.save()
        c = client_fuer(self.mediziner)
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/sprechstunde/").status_code, 200)
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/sprechstunde/?ablegen=1").status_code, 409)
