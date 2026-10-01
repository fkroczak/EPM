"""Stammdaten: Präparate mit Nutzung, Versorger/Ansprechpartner, Einstellungen (echte Datenbank)."""
from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer
from infusionen.models import Infusionsplan
from patienten.models import Patient

from .models import Ansprechpartner, Auswahlwert, Einstellungen, Praeparat, Versorger


class Praeparate(Grundlage):
    def test_in_plaenen(self):
        glamin = Praeparat.objects.get(name="Glamin")
        soluvit = Praeparat.objects.get(name="Soluvit N")
        plan = Infusionsplan.neuer_entwurf(self.patient, self.mediziner)
        plan.aminosaeuren_praeparat, plan.aminosaeuren_g = glamin, 70
        plan.save()
        plan.vitamine.set([soluvit])
        plan.freigeben(self.mediziner)
        Infusionsplan.neuer_entwurf(self.patient, self.mediziner)  # übernimmt Glamin und Soluvit N

        c = client_fuer(self.betrachter)  # lesen dürfen alle
        werte = {p["name"]: p["in_plaenen"] for p in c.get("/api/praeparate/").json()}
        self.assertEqual(werte["Glamin"], 2)
        self.assertEqual(werte["Soluvit N"], 2)
        self.assertEqual(werte["Clinoleic"], 0)
        einzeln = c.get(f"/api/praeparate/{glamin.id}/").json()
        self.assertEqual(einzeln["in_plaenen"], 2)

    def test_nur_admin_pflegt_kein_loeschen(self):
        neu = {"kategorie": "lipide", "name": "Omegaven", "konzentration": "10 %", "einheit": "ml", "reihenfolge": 5}
        self.assertEqual(client_fuer(self.mediziner).post("/api/praeparate/", neu, format="json").status_code, 403)
        a = client_fuer(self.admin)
        r = a.post("/api/praeparate/", neu, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(a.delete(f"/api/praeparate/{r.json()['id']}/").status_code, 405)
        r = a.patch(f"/api/praeparate/{r.json()['id']}/", {"aktiv": False}, format="json")
        self.assertFalse(r.json()["aktiv"])
        lipide = [p["name"] for p in a.get("/api/praeparate/?kategorie=lipide&aktiv=true").json()]
        self.assertNotIn("Omegaven", lipide)

    def test_auswahllisten_wie_im_entwurf(self):
        orte = list(Auswahlwert.objects.filter(liste="terminort").values_list("wert", flat=True))
        self.assertEqual(orte, ["Praxis Dr. Holtmeier"])
        katheter = list(Auswahlwert.objects.filter(liste="katheter").order_by("reihenfolge")
                        .values_list("wert", flat=True))
        self.assertEqual(katheter, ["Port", "Hickman", "Broviac", "PICC", "Port 1-Kammer", "Port 2-Kammer"])


class VersorgerUndAnsprechpartner(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.v = Versorger.objects.create(name="Homecare Nord")
        cls.ap1 = Ansprechpartner.objects.create(versorger=cls.v, name="Frau Alt", zustaendigkeit="Münsterland")
        cls.ap2 = Ansprechpartner.objects.create(versorger=cls.v, name="Herr Neu")
        cls.fremd = Ansprechpartner.objects.create(versorger=Versorger.objects.create(name="Andere GmbH"), name="X")
        cls.p1 = Patient.objects.create(nachname="Eins", vorname="E", geburtsdatum="1970-01-01",
                                        versorger=cls.v, ansprechpartner=cls.ap1)
        cls.p2 = Patient.objects.create(nachname="Zwei", vorname="Z", geburtsdatum="1971-01-01",
                                        versorger=cls.v, ansprechpartner=cls.ap1,
                                        abgeschlossen_am=timezone.localdate(), abschluss_anlass="verstorben")

    def test_rechte(self):
        neu = {"name": "Versorger aus Neuer Patient"}
        self.assertEqual(client_fuer(self.betrachter).post("/api/versorger/", neu, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.mitarbeiter).post("/api/versorger/", neu, format="json").status_code, 201)
        ap = {"versorger": self.v.id, "name": "Frau Drei", "zustaendigkeit": "Ruhrgebiet"}
        self.assertEqual(client_fuer(self.mediziner).post("/api/ansprechpartner/", ap, format="json").status_code, 201)
        self.assertEqual(client_fuer(self.admin).delete(f"/api/versorger/{self.v.id}/").status_code, 405)

    def test_patienten_und_neu_zuordnen(self):
        c = client_fuer(self.mitarbeiter)
        daten = c.get(f"/api/ansprechpartner/{self.ap1.id}/").json()
        self.assertEqual((daten["patienten_anzahl"], daten["zustaendigkeit"]), (1, "Münsterland"))
        self.assertEqual([p["id"] for p in c.get(f"/api/ansprechpartner/{self.ap1.id}/patienten/").json()],
                         [self.p1.id])
        url = f"/api/ansprechpartner/{self.ap1.id}/neu-zuordnen/"
        for ziel in (self.fremd.id, self.ap1.id, 99999, None):
            with self.subTest(ziel=ziel):
                self.assertEqual(c.post(url, {"ziel": ziel}, format="json").status_code, 400)
        r = c.post(url, {"ziel": self.ap2.id}, format="json")
        self.assertEqual(r.json(), {"neu_zugeordnet": 1})
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p1.ansprechpartner, self.ap2)
        self.assertEqual(self.p2.ansprechpartner, self.ap1)  # abgeschlossene Akte bleibt unverändert
        v = c.get(f"/api/patienten/{self.p1.id}/verlauf/?bereich=stammdaten").json()
        self.assertEqual(v[0]["person"], self.mitarbeiter.anzeigename)
        self.assertIn("ansprechpartner", [a["feld"] for a in v[0]["aenderungen"]])


class EinstellungenPruefen(Grundlage):
    def test_grenzen_und_rechte(self):
        a = client_fuer(self.admin)
        self.assertEqual(client_fuer(self.mediziner).get("/api/einstellungen/").status_code, 200)
        self.assertEqual(client_fuer(self.mediziner).patch("/api/einstellungen/", {"kcal_max_tag": 3000},
                                                           format="json").status_code, 403)
        r = a.patch("/api/einstellungen/", {"glucose_min_g": 1200}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("glucose_min_g", r.json())
        r = a.patch("/api/einstellungen/", {"natrium_min_mmol": 10, "natrium_max_mmol": 5}, format="json")
        self.assertEqual(r.status_code, 400)
        r = a.patch("/api/einstellungen/", {"kontakt_ueberfaellig_monate": 6, "kalium_max_mmol": 250}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        e = Einstellungen.aktuell()
        self.assertEqual((e.kontakt_ueberfaellig_monate, e.kalium_max_mmol), (6, 250))
        eintrag = a.get("/api/protokoll/?gruppe=vorlage").json()["results"][0]
        self.assertEqual(eintrag["gruppe_name"], "Vorlage")
        self.assertIn("„Kontakt überfällig“ von 12 auf 6 Monate geändert", eintrag["beschreibung"])
        self.assertIn("„Kalium maximal“ von 300 auf 250 mmol geändert", eintrag["beschreibung"])
