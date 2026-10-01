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
        self.assertEqual(plan["kcal"], 1446)  # 200·4 + 70·4 + 40·9,15 wie im Altsystem
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
        self.assertEqual(zeilen["kcal"]["vorher"], "1.446 kcal")  # deutsche Schreibweise wie auf dem Plan
        self.assertEqual(zeilen["kcal"]["jetzt"], "1.246 kcal")
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

    def test_gesamtvolumen_rate_und_protonenpumpenhemmer(self):
        """Festlegung 01.10.2026: Gesamtvolumen = letztes Gewicht × 35 ml (wie im Altsystem), Laufzeit wird eingegeben,
        Rate = Gesamtvolumen ÷ Laufzeit; Protonenpumpenhemmer mit den Codes des Altsystems, Zeiten als Bitmaske."""
        c = client_fuer(self.mediziner)
        m = client_fuer(self.mitarbeiter)
        e = self.entwurf(c)
        url = f"/api/infusionsplaene/{e['id']}/"
        self.assertIsNone(c.get(url).json()["gesamtvolumen_ml"])  # ohne Gewicht kein Volumen
        vorher = str(timezone.localdate() - timedelta(days=30))
        m.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "58.0", "gemessen_am": vorher}, format="json")
        m.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "60.0"}, format="json")
        r = c.patch(url, {**self.plan_daten(), "pantozol_stufe": 1, "pantozol_tage": 5}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        p = r.json()
        self.assertEqual([p["gesamtvolumen_ml"], p["volumen_gewicht_kg"], p["laufzeit_h"], p["rate_ml_h"]], [2100, 60, 12, 175])
        zeilen = {z["schluessel"]: z for z in c.get(url + "vergleich/").json()["zeilen"]}
        self.assertEqual(zeilen["gesamtvolumen"]["jetzt"], "2.100 ml (35 ml/kg × 60 kg)")
        self.assertEqual(zeilen["rate"]["jetzt"], "175 ml/h")
        self.assertEqual(zeilen["pantozol"]["jetzt"], "Pantozol® 40 mg · morgens, abends")
        self.assertEqual(zeilen["pantozol"]["wert"], "Protonenpumpenhemmer")
        # Freigabe friert das Volumen ein; ein neuer Entwurf rechnet mit dem neuen Gewicht
        self.assertEqual(c.post(url + "freigeben/").status_code, 200)
        m.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "70.0"}, format="json")
        self.assertEqual(c.get(url).json()["gesamtvolumen_ml"], 2100)
        e2 = self.entwurf(c)
        url2 = f"/api/infusionsplaene/{e2['id']}/"
        self.assertEqual(c.get(url2).json()["gesamtvolumen_ml"], 2450)
        # Plausibilitätsgrenze für das Gesamtvolumen
        a = client_fuer(self.admin)
        self.assertEqual(a.patch("/api/einstellungen/", {"volumen_max_ml": 2000}, format="json").status_code, 200)
        r = c.patch(url2, {"bemerkung": "<p>x</p>"}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("gesamtvolumen_ml", r.json())
        a.patch("/api/einstellungen/", {"volumen_max_ml": 9000}, format="json")
        # Protonenpumpenhemmer: Codes 0–3 wie im Altsystem, Zeiten Pflicht, wenn gewählt
        for daten, feld in [({"pantozol_stufe": 2, "pantozol_tage": None}, "pantozol_tage"),
                            ({"pantozol_stufe": 0, "pantozol_tage": 4}, "pantozol_tage"),
                            ({"pantozol_stufe": 3, "pantozol_tage": 8}, "pantozol_tage"),
                            ({"pantozol_stufe": 9}, "pantozol_stufe")]:
            with self.subTest(daten=daten):
                r = c.patch(url2, daten, format="json")
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn(feld, r.json())
        r = c.patch(url2, {"pantozol_stufe": 3, "pantozol_tage": 7}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        zeilen = {z["schluessel"]: z for z in c.get(url2 + "vergleich/").json()["zeilen"]}
        self.assertEqual(zeilen["pantozol"]["jetzt"], "Pantozol® 20 mg · morgens, mittags, abends")
        self.assertEqual(zeilen["pantozol"]["vorher"], "Pantozol® 40 mg · morgens, abends")

    def test_berechnung_wie_im_altsystem(self):
        """Festlegung 01.10.2026: Lipide 9,15 kcal/g, Humanalbumin in ml ohne Energie; Ca + Mg ≤ Gesamtvolumen ÷ 100;
        erster Plan je kg Körpergewicht vorbelegt."""
        c = client_fuer(self.mediziner)
        m = client_fuer(self.mitarbeiter)
        url_vb = f"/api/infusionsplaene/vorbelegung/?patient={self.patient.id}"
        self.assertEqual(c.get(url_vb).json()["werte"], None)  # ohne Gewicht keine Vorbelegung
        m.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "60.0"}, format="json")
        vb = c.get(url_vb).json()
        self.assertEqual(vb["gewicht_kg"], 60)
        self.assertEqual(vb["werte"], {"glucose_g": 210, "aminosaeuren_g": 72, "lipide_g": 60, "natrium_mmol": 78,
                                       "kalium_mmol": 42, "phosphat_mmol": 18, "calcium_mmol": 9, "magnesium_mmol": 12})
        m.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "73.5"}, format="json")
        self.assertEqual(c.get(url_vb).json()["werte"]["calcium_mmol"], 11.0)  # 11,025 → Feldgenauigkeit 0,1
        self.assertEqual(client_fuer(self.betrachter).get(url_vb).status_code, 200)

        e = self.entwurf(c)
        url = f"/api/infusionsplaene/{e['id']}/"
        r = c.patch(url, {"glucose_g": "100", "glucose_praeparat": praeparat("Glucose", "70 %").id,
                          "lipide_g": "50", "lipide_praeparat": praeparat("Clinoleic").id,
                          "albumin_ml": "100", "albumin_praeparat": praeparat("Humanalbumin").id,
                          "calcium_mmol": "10", "magnesium_mmol": "15"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        p = r.json()
        self.assertEqual(p["kcal"], 858)  # 100·4 + 50·9,15 = 857,5 → 858; Albumin zählt nicht
        self.assertEqual(p["albumin_ml"], 100)
        # 73,5 kg × 35 = 2.572,5 ml → Grenze 25,73 mmol; 10 + 15 = 25 → stabil
        self.assertEqual([p["ca_mg_mmol"], p["ca_mg_grenze_mmol"], p["ca_mg_stabil"]], [25, 25.73, True])
        zeilen = {z["schluessel"]: z for z in c.get(url + "vergleich/").json()["zeilen"]}
        self.assertEqual(zeilen["albumin"]["jetzt"], "Humanalbumin 20 % · 100 ml")
        # instabil ist nur ein Hinweis wie im Altsystem, Speichern bleibt möglich
        r = c.patch(url, {"magnesium_mmol": "16"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["ca_mg_stabil"], False)

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
