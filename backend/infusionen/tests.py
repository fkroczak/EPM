"""Infusionspläne: Entwurf → Freigabe → unveränderlich, Vorbelegung, Vergleich (echte Datenbank)."""
from datetime import timedelta

from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer
from patienten.models import Patient
from stammdaten.models import Praeparat

from .models import Infusionsplan


def praeparat(name, konzentration=None):
    qs = Praeparat.objects.filter(name=name)
    if konzentration is not None:
        qs = qs.filter(konzentration=konzentration)
    return qs.get()


class Infusionsplaene(Grundlage):
    def plan_daten(self):
        """Werte wie im Entwurf 7 · Neuer Infusionsplan."""
        return {
            "basis_praeparat": praeparat("Sterofundin").id, "basis_ml": 500,
            "glucose_praeparat": praeparat("Glucose", "70 %").id, "glucose_g": "200",
            "aminosaeuren_praeparat": praeparat("Glamin").id, "aminosaeuren_g": "70",
            "lipide_praeparat": praeparat("Clinoleic").id, "lipide_g": "40",
            "natrium_mmol": "78", "kalium_mmol": "40", "phosphat_mmol": "18", "calcium_mmol": "7",
            "magnesium_mmol": "10",
            "spurenelemente": praeparat("Addel N").id,
            "vitamine": [praeparat("Soluvit N").id, praeparat("Vitalipid adult").id],
            "katheterschutz": praeparat("Taurolin").id,
            "laufzeit_h": "12", "tage_pro_woche": 5,
            "positionen": [{"praeparat": praeparat("Dipeptamin").id, "menge": "100", "einheit": "ml"}],
        }

    def entwurf(self, client=None, **extra):
        c = client or client_fuer(self.mediziner)
        r = c.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id, **extra}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def freigegebener_plan(self, **werte):
        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        daten = {**self.plan_daten(), **werte}
        r = c.patch(f"/api/infusionsplaene/{e['id']}/", daten, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(c.post(f"/api/infusionsplaene/{e['id']}/freigeben/").status_code, 200)
        return Infusionsplan.objects.get(pk=e["id"])

    def test_ablauf(self):
        c = client_fuer(self.mediziner)
        self.assertEqual(client_fuer(self.mitarbeiter).post("/api/infusionsplaene/entwurf/",
                                                            {"patient": self.patient.id}, format="json").status_code, 403)
        e1 = self.entwurf(c)
        r = c.patch(f"/api/infusionsplaene/{e1['id']}/", self.plan_daten(), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        plan = r.json()
        self.assertEqual(plan["kcal"], 200 * 4 + 70 * 4 + 40 * 9)
        self.assertEqual(plan["vitamine_namen"], ["Soluvit N", "Vitalipid adult"])
        self.assertEqual(float(plan["natrium_mmol"]), 78.0)
        self.assertEqual(len(plan["positionen"]), 1)
        self.assertEqual(c.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id}, format="json").status_code, 400)
        self.assertEqual(c.post(f"/api/infusionsplaene/{e1['id']}/freigeben/").status_code, 200)
        # freigegeben → unveränderlich (auch Vitamine)
        self.assertEqual(c.patch(f"/api/infusionsplaene/{e1['id']}/", {"glucose_g": "1"}, format="json").status_code, 403)
        self.assertEqual(c.patch(f"/api/infusionsplaene/{e1['id']}/", {"vitamine": []}, format="json").status_code, 403)
        self.assertEqual(c.delete(f"/api/infusionsplaene/{e1['id']}/").status_code, 403)
        # neuer Entwurf ist vorbelegt, Änderungen werden markiert
        e2 = self.entwurf(c)
        self.assertEqual(float(e2["glucose_g"]), 200)
        self.assertEqual(e2["vorgaenger"], e1["id"])
        self.assertEqual(len(e2["vitamine"]), 2)
        self.assertEqual(len(e2["positionen"]), 1)
        self.assertEqual(e2["geaenderte_felder"], [])
        r = c.patch(f"/api/infusionsplaene/{e2['id']}/", {"glucose_g": "150"}, format="json").json()
        self.assertEqual(r["geaenderte_felder"], ["glucose_g"])
        r = c.patch(f"/api/infusionsplaene/{e2['id']}/", {"vitamine": [praeparat("Cernevit").id]}, format="json").json()
        self.assertEqual(r["geaenderte_felder"], ["glucose_g", "vitamine"])
        c.post(f"/api/infusionsplaene/{e2['id']}/freigeben/")
        status = dict(Infusionsplan.objects.filter(patient=self.patient).values_list("id", "status"))
        self.assertEqual(status, {e1["id"]: "abgeloest", e2["id"]: "aktuell"})
        # Vitamine des abgelösten Plans bleiben erhalten
        self.assertEqual(Infusionsplan.objects.get(pk=e1["id"]).vitamine.count(), 2)
        kopf = c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual(kopf["aktueller_plan"]["id"], e2["id"])
        self.assertEqual(float(kopf["aktueller_plan"]["laufzeit_h"]), 12.0)

    def test_entwurf_verwerfen(self):
        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        c.patch(f"/api/infusionsplaene/{e['id']}/", self.plan_daten(), format="json")
        self.assertEqual(c.delete(f"/api/infusionsplaene/{e['id']}/").status_code, 204)
        self.assertFalse(Infusionsplan.objects.filter(pk=e["id"]).exists())

    def test_vitamine_freigegebener_plaene_in_der_datenbank_geschuetzt(self):
        plan = self.freigegebener_plan()
        with self.assertRaises(PermissionError), transaction.atomic():
            plan.vitamine.clear()
        cernevit = praeparat("Cernevit")
        for sql, args in [
            ("INSERT INTO infusionen_infusionsplan_vitamine (infusionsplan_id, praeparat_id) VALUES (%s, %s)",
             [plan.id, cernevit.id]),
            ("DELETE FROM infusionen_infusionsplan_vitamine WHERE infusionsplan_id = %s", [plan.id]),
            ("UPDATE infusionen_infusionsplan_vitamine SET praeparat_id = %s WHERE infusionsplan_id = %s",
             [cernevit.id, plan.id]),
        ]:
            with self.subTest(sql=sql.split()[0]), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(sql, args)
        self.assertEqual(plan.vitamine.count(), 2)

    def test_vergleich_mit_vorgaenger(self):
        alt = self.freigegebener_plan()
        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        c.patch(f"/api/infusionsplaene/{e['id']}/", {"glucose_g": "150", "natrium_mmol": "80"}, format="json")
        v = c.get(f"/api/infusionsplaene/{e['id']}/vergleich/").json()
        self.assertEqual(v["vorgaenger"]["id"], alt.id)
        zeilen = {z["schluessel"]: z for z in v["zeilen"]}
        self.assertEqual({k for k, z in zeilen.items() if z["geaendert"]}, {"glucose", "natrium_mmol", "kcal"})
        self.assertEqual(v["anzahl_geaendert"], 3)
        self.assertEqual(zeilen["glucose"]["vorher"], "Glucose 70 % · 200 g")
        self.assertEqual(zeilen["glucose"]["jetzt"], "Glucose 70 % · 150 g")
        self.assertEqual(zeilen["natrium_mmol"]["jetzt"], "80 mmol")
        self.assertEqual(zeilen["vitamine"]["jetzt"], "Soluvit N | Vitalipid adult")
        self.assertEqual(zeilen["laufzeit_h"]["jetzt"], "12 h")
        self.assertEqual(zeilen["basis"]["jetzt"], "Sterofundin · 500 ml")
        # erster Plan ohne Vorgänger
        v = c.get(f"/api/infusionsplaene/{alt.id}/vergleich/").json()
        self.assertIsNone(v["vorgaenger"])
        self.assertEqual(v["anzahl_geaendert"], 0)

    def test_leer_beginnen_und_vorlage(self):
        a = self.freigegebener_plan()
        b = self.freigegebener_plan(glucose_g="150")
        c = client_fuer(self.mediziner)
        leer = self.entwurf(c, leer=True)
        self.assertIsNone(leer["glucose_g"])
        self.assertEqual(leer["vitamine"], [])
        self.assertEqual(leer["vorgaenger"], b.id)  # Vergleich immer gegen den aktuellen Plan
        c.delete(f"/api/infusionsplaene/{leer['id']}/")
        aus_vorlage = self.entwurf(c, vorlage=a.id)
        self.assertEqual(float(aus_vorlage["glucose_g"]), 200)
        self.assertEqual(aus_vorlage["vorgaenger"], b.id)
        self.assertEqual(aus_vorlage["geaenderte_felder"], ["glucose_g"])
        c.delete(f"/api/infusionsplaene/{aus_vorlage['id']}/")
        anderer = Patient.objects.create(nachname="Anders", vorname="A", geburtsdatum="1966-06-06")
        r = c.post("/api/infusionsplaene/entwurf/", {"patient": anderer.id, "vorlage": a.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_praeparate_werden_geprueft(self):
        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        url = f"/api/infusionsplaene/{e['id']}/"
        faelle = [
            ({"glucose_praeparat": praeparat("Clinoleic").id}, "glucose_praeparat"),   # falsche Kategorie
            ({"spurenelemente": praeparat("Soluvit N").id}, "spurenelemente"),
            ({"vitamine": [praeparat("Addel N").id]}, "vitamine"),                    # kein Vitamin
            ({"glucose_g": "1500", "glucose_praeparat": praeparat("Glucose").id}, "glucose_g"),  # über Grenze
            ({"natrium_mmol": "600"}, "natrium_mmol"),
            ({"lipide_g": "40"}, "lipide_praeparat"),                                   # Menge ohne Präparat
            ({"pantozol_stufe": 1}, "pantozol_tage"),
        ]
        for daten, feld in faelle:
            with self.subTest(daten=daten):
                r = c.patch(url, daten, format="json")
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn(feld, r.json())
        # ausgeblendete Präparate können nicht neu gewählt werden
        lipid = praeparat("Lipidem")
        lipid.aktiv = False
        lipid.save()
        r = c.patch(url, {"lipide_praeparat": lipid.id}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("ausgeblendet", r.json()["lipide_praeparat"][0])

    def test_ausgeblendetes_praeparat_bleibt_im_neuen_entwurf(self):
        self.freigegebener_plan()
        glamin = praeparat("Glamin")
        glamin.aktiv = False
        glamin.save()
        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        self.assertEqual(e["aminosaeuren_praeparat"], glamin.id)
        r = c.patch(f"/api/infusionsplaene/{e['id']}/", {"aminosaeuren_g": "60"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(c.post(f"/api/infusionsplaene/{e['id']}/freigeben/").status_code, 200)

    def test_kcal_manuell_und_grenze(self):
        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        self.assertEqual(c.patch(f"/api/infusionsplaene/{e['id']}/", {"kcal_manuell": 1800}, format="json").json()["kcal"], 1800)
        self.assertEqual(c.patch(f"/api/infusionsplaene/{e['id']}/", {"kcal_manuell": 433564}, format="json").status_code, 400)

    def test_abgeschlossene_akte(self):
        self.freigegebener_plan()
        self.patient.abgeschlossen_am = timezone.localdate() - timedelta(days=1)
        self.patient.abschluss_anlass = Patient.Abschlussanlass.THERAPIE_BEENDET
        self.patient.save()
        r = client_fuer(self.mediziner).post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id},
                                             format="json")
        self.assertEqual(r.status_code, 409)
