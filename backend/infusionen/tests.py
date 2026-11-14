"""Infusionspläne: Entwurf → Freigabe → unveränderlich, Vorbelegung, Vergleich (echte Datenbank)."""
from datetime import timedelta
from decimal import Decimal

from django.db import DatabaseError, connection, transaction
from django.test.utils import CaptureQueriesContext
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


class PlanHilfen:
    """Entwurf anlegen und freigeben (gemeinsam für die Testklassen der Pläne)."""

    def plan_daten(self):
        """Werte wie im Entwurf 7 · Neuer Infusionsplan."""
        return {
            "basis_praeparat": praeparat("Sterofundin ISO").id, "basis_ml": 500,
            "glucose_praeparat": praeparat("Glucose", "70 %").id, "glucose_g": "200",
            "aminosaeuren_praeparat": praeparat("Glamin").id, "aminosaeuren_g": "70",
            "lipide_praeparat": praeparat("Clinoleic").id, "lipide_g": "40",
            "natrium_mmol": "78", "kalium_mmol": "40", "phosphat_mmol": "18", "calcium_mmol": "7",
            "magnesium_mmol": "10",
            "spurenelemente": praeparat("Addel N").id,
            "vitamine": [praeparat("Soluvit N").id, praeparat("Vitalipid adult").id],
            "katheterschutz": praeparat("Taurolin").id,
            "laufzeit_h": "12", "tage_pro_woche": 5,
            "positionen": [{"praeparat": praeparat("Pantozol i.v.").id, "menge": "100", "einheit": "ml"}],
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


class Infusionsplaene(PlanHilfen, Grundlage):
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
        # Aktenkopf kennt den offenen Entwurf („Entwurf fortsetzen“, 08.10.2026)
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]["plan_entwurf"]["id"], e2["id"])
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
        self.assertIsNone(kopf["plan_entwurf"])

    def test_liste_ohne_abfragen_je_plan(self):
        """Liste der Pläne einer Akte: „geänderte Felder“ nutzt die vorgeladenen Vitamine und Positionen (auch des
        Vorgängers) – vorher vier Abfragen je Plan."""
        c = client_fuer(self.mediziner)
        url = f"/api/infusionsplaene/?patient={self.patient.id}&seitengroesse=2000"

        def abfragen():
            with CaptureQueriesContext(connection) as q:
                r = c.get(url)
            self.assertEqual(r.status_code, 200)
            return len(q), r.json()["results"]

        self.freigegebener_plan()
        self.freigegebener_plan(glucose_g="150")
        c.get(url)  # erste Anfrage der Sitzung hat eigene Abfragen (Sitzung)
        vorher, plaene = abfragen()
        self.assertEqual(plaene[0]["geaenderte_felder"], ["glucose_g"])
        self.freigegebener_plan(glucose_g="150", vitamine=[praeparat("Cernevit").id])
        pantozol = {"praeparat": praeparat("Pantozol i.v.").id, "menge": "50", "einheit": "ml"}
        self.freigegebener_plan(glucose_g="150", vitamine=[praeparat("Cernevit").id], positionen=[pantozol])
        nachher, plaene = abfragen()
        self.assertEqual(len(plaene), 4)
        self.assertEqual([p["geaenderte_felder"] for p in plaene],
                         [["positionen"], ["vitamine"], ["glucose_g"], []])
        self.assertEqual(nachher, vorher)

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

    def test_freigabe_geht_vom_gespeicherten_stand_aus(self):
        """Veraltete Kopie (vorab geladene Positionen) darf weder PDF noch Datensatz verfälschen; zweite Freigabe scheitert."""
        from unittest import mock

        from django.core.exceptions import ValidationError

        from patienten.models import Dokument

        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        c.patch(f"/api/infusionsplaene/{e['id']}/", self.plan_daten(), format="json")
        alt1 = Infusionsplan.objects.prefetch_related("positionen").get(pk=e["id"])
        alt2 = Infusionsplan.objects.get(pk=e["id"])
        list(alt1.positionen.all())
        c.patch(f"/api/infusionsplaene/{e['id']}/", {"glucose_g": "150", "positionen": [
            {"praeparat": praeparat("Pantozol i.v.").id, "menge": "50", "einheit": "ml"}]}, format="json")
        gesehen = {}
        original = Infusionsplan._pdf_ablegen

        def merken(plan, benutzer):
            gesehen["glucose_g"] = plan.glucose_g
            gesehen["mengen"] = [p.menge for p in plan.positionen.all()]
            return original(plan, benutzer)

        with mock.patch.object(Infusionsplan, "_pdf_ablegen", merken):
            alt1.freigeben(self.mediziner)
        self.assertEqual(gesehen, {"glucose_g": Decimal("150"), "mengen": [Decimal("50")]})
        self.assertEqual(Infusionsplan.objects.get(pk=e["id"]).glucose_g, Decimal("150"))
        anzahl = Dokument.objects.filter(patient=self.patient).count()
        with self.assertRaises(ValidationError):
            alt2.freigeben(self.mediziner)
        self.assertEqual(Dokument.objects.filter(patient=self.patient).count(), anzahl)

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
        self.assertEqual(zeilen["basis"]["jetzt"], "Sterofundin ISO · 500 ml")
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
        # Mischbeutel 60 kg × 35 = 2.100 ml, Zusatzvolumen (Basislösung) 500 ml, Rate aus der Summe: 2.600 ÷ 12 = 216,7
        self.assertEqual([p["gesamtvolumen_ml"], p["volumen_gewicht_kg"], p["volumen_summe_ml"], p["laufzeit_h"], p["rate_ml_h"]],
                         [2100, 60, 2600, 12, 216.7])
        zeilen = {z["schluessel"]: z for z in c.get(url + "vergleich/").json()["zeilen"]}
        self.assertEqual(zeilen["mischbeutel"]["jetzt"], "2.100 ml (35 ml/kg × 60 kg)")
        self.assertEqual(zeilen["mischbeutel"]["wert"], "Volumen im Mischbeutel")
        self.assertEqual(zeilen["gesamtvolumen"]["jetzt"], "2.600 ml")
        self.assertEqual(zeilen["rate"]["jetzt"], "216,7 ml/h")
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

    def test_volumen_von_hand_und_glucose_ohne_praeparat(self):
        """Wunsch 27.10.2026: Mischbeutel und Gesamtvolumen von Hand; Glucose braucht kein Präparat (wählt die Apotheke)."""
        c = client_fuer(self.mediziner)
        client_fuer(self.mitarbeiter).post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "60.0"}, format="json")
        e = self.entwurf(c)
        url = f"/api/infusionsplaene/{e['id']}/"
        daten = {**self.plan_daten(), "glucose_praeparat": None, "mischbeutel_ml_manuell": "1995"}
        r = c.patch(url, daten, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        p = r.json()
        self.assertEqual([p["glucose_praeparat"], p["glucose_g"]], [None, 200])
        # 1.995 + 500 = 2.495 ml; Rate 2.495 ÷ 12 = 207,9
        self.assertEqual([p["gesamtvolumen_ml"], p["volumen_summe_ml"], p["rate_ml_h"]], [1995, 2495, 207.9])
        zeilen = {z["schluessel"]: z for z in c.get(url + "vergleich/").json()["zeilen"]}
        self.assertEqual(zeilen["mischbeutel"]["jetzt"], "1.995 ml (manuell)")
        r = c.patch(url, {"gesamtvolumen_ml_manuell": "2400"}, format="json")
        self.assertEqual([r.json()["volumen_summe_ml"], r.json()["rate_ml_h"]], [2400, 200])
        for feld in ("mischbeutel_ml_manuell", "gesamtvolumen_ml_manuell"):
            with self.subTest(feld=feld):
                r = c.patch(url, {feld: "0"}, format="json")
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn(feld, r.json())
        # leer = wieder berechnet
        r = c.patch(url, {"mischbeutel_ml_manuell": None, "gesamtvolumen_ml_manuell": None}, format="json")
        self.assertEqual([r.json()["gesamtvolumen_ml"], r.json()["volumen_summe_ml"]], [2100, 2600])
        self.assertEqual(c.post(url + "freigeben/").status_code, 200)

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


class KeinPlanNoetig(PlanHilfen, Grundlage):
    """Ergänzung zur Fehlerliste 02.10.2026: Akten in Betreuung ohne Infusionsplan bekommen einen Hinweis; wer bestätigt,
    dass ein Patient keinen braucht, unterdrückt ihn und die Warnung „Plan älter als …“. Die nächste Freigabe eines
    Plans hebt die Bestätigung wieder auf."""

    def liste(self, **filter):
        r = client_fuer(self.mitarbeiter).get("/api/patienten/", {"status": "in_betreuung", **filter})
        self.assertEqual(r.status_code, 200, r.content)
        return {p["id"]: p for p in r.json()["results"]}

    def test_hinweis_bestaetigen_aufheben(self):
        p = self.liste()[self.patient.id]
        self.assertIn("ohne_plan", [h["art"] for h in p["kennzahlen"]["hinweise"]])
        self.assertIn(self.patient.id, self.liste(pruefen="ohne_plan"))
        start = client_fuer(self.mitarbeiter).get("/api/startseite/").json()
        self.assertGreaterEqual(start["pruefen"]["ohne_plan"], 1)
        # Betrachter darf nicht, Admin nur bei Testpatienten
        url = f"/api/patienten/{self.patient.id}/kein-plan/"
        self.assertEqual(client_fuer(self.betrachter).post(url, {"kein_plan": True}, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.admin).post(url, {"kein_plan": True}, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.mitarbeiter).post(url, {"kein_plan": "ja"}, format="json").status_code, 400)
        r = client_fuer(self.mitarbeiter).post(url, {"kein_plan": True, "grund": "nur orale Ernährung"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        kopf = r.json()["kopf"]["kein_plan"]
        self.assertEqual(kopf["grund"], "nur orale Ernährung")
        self.assertTrue(kopf["von"])
        p = self.liste()[self.patient.id]
        self.assertNotIn("ohne_plan", [h["art"] for h in p["kennzahlen"]["hinweise"]])
        self.assertNotIn(self.patient.id, self.liste(pruefen="ohne_plan"))
        # steht in der Historie (Verlauf der Akte)
        self.assertTrue(self.patient.history.filter(kein_plan=True).exists())
        r = client_fuer(self.mitarbeiter).post(url, {"kein_plan": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["kopf"]["kein_plan"])
        self.assertIn(self.patient.id, self.liste(pruefen="ohne_plan"))

    def test_alter_plan_ohne_warnung_und_freigabe_hebt_auf(self):
        from stammdaten.models import Einstellungen

        alt = timezone.localdate() - timedelta(days=30 * Einstellungen.aktuell().plan_alter_warnung_monate + 10)
        # aktueller Plan von vor der Grenze (wie aus dem Altsystem übernommen; freigegebene Pläne sind unveränderlich)
        Infusionsplan.objects.bulk_create([Infusionsplan(patient=self.patient, status=Infusionsplan.Status.AKTUELL,
                                                         gueltig_ab=alt, herkunft=Infusionsplan.Herkunft.ALTSYSTEM,
                                                         erstellt_von=self.mediziner)])
        c = client_fuer(self.mediziner)
        self.assertIn("plan", [h["art"] for h in self.liste()[self.patient.id]["kennzahlen"]["hinweise"]])
        self.assertEqual(len(c.get("/api/startseite/").json()["infusionsplaene"]["aelter_als_grenze"]), 1)
        self.assertEqual(c.get("/api/infusionsplaene/uebersicht/?gruppe=alt").json()["zaehler"]["alt"], 1)
        self.assertEqual(c.post(f"/api/patienten/{self.patient.id}/kein-plan/", {"kein_plan": True},
                                format="json").status_code, 200)
        arten = [h["art"] for h in self.liste()[self.patient.id]["kennzahlen"]["hinweise"]]
        self.assertNotIn("plan", arten)
        self.assertNotIn("ohne_plan", arten)
        self.assertEqual(c.get("/api/startseite/").json()["infusionsplaene"]["aelter_als_grenze"], [])
        uebersicht = c.get("/api/infusionsplaene/uebersicht/?gruppe=aktuell").json()
        self.assertEqual(uebersicht["zaehler"]["alt"], 0)
        self.assertEqual([(z["aelter_als_grenze"], z["kein_plan"]) for z in uebersicht["ergebnisse"]], [(False, True)])
        from patienten.kalender import faelligkeiten

        eintraege, _ = faelligkeiten(Patient.objects.all(), timezone.localdate() + timedelta(days=400))
        self.assertFalse([x for x in eintraege if x["art"] == "plan"])
        # neuer Plan freigegeben → Patient braucht wieder einen Plan
        self.freigegebener_plan()
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.kein_plan)


class PlanVorschau(PlanHilfen, Grundlage):
    """PDF-Vorschau mit den ungespeicherten Eingaben des Editors (F181): nichts wird gespeichert."""

    def test_vorschau_zeigt_eingaben_und_speichert_nichts(self):
        import unittest

        from vorlagen.tests import PDFTOTEXT, kompakt, pdf_text

        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        self.assertEqual(c.patch(f"/api/infusionsplaene/{e['id']}/", self.plan_daten(), format="json").status_code, 200)
        vorher = c.get(f"/api/infusionsplaene/{e['id']}/").json()
        fassungen = Infusionsplan.history.filter(id=e["id"]).count()
        r = c.post(f"/api/infusionsplaene/{e['id']}/vorschau/",
                   {"aminosaeuren_g": "85", "laufzeit_h": "14", "positionen": []}, format="json")
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        # in der Datenbank unverändert, auch keine neue Fassung im Verlauf
        nachher = c.get(f"/api/infusionsplaene/{e['id']}/").json()
        for feld in ("aminosaeuren_g", "laufzeit_h", "positionen", "vitamine"):
            self.assertEqual(nachher[feld], vorher[feld], feld)
        self.assertEqual(Infusionsplan.history.filter(id=e["id"]).count(), fassungen)
        if not PDFTOTEXT:
            raise unittest.SkipTest("pdftotext fehlt – Inhalt der Vorschau nicht geprüft")
        text = kompakt(pdf_text(r.content))
        self.assertIn("85g", text)
        self.assertNotIn("Pantozoli.v.", text)  # Positionen der Eingabe (leer), nicht die gespeicherten
        self.assertIn("ENTWURF", kompakt(pdf_text(r.content, roh=True)))

    def test_vorschau_prueft_wie_speichern_und_nur_fuer_entwuerfe(self):
        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        # gleiche Prüfung wie beim Speichern: Präparat passt nicht zum Feld
        r = c.post(f"/api/infusionsplaene/{e['id']}/vorschau/", {"glucose_praeparat": praeparat("Glamin").id}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("glucose_praeparat", r.json())
        # ohne Recht „Infusionspläne anlegen“ keine Vorschau
        self.assertEqual(client_fuer(self.mitarbeiter).post(f"/api/infusionsplaene/{e['id']}/vorschau/", {},
                                                            format="json").status_code, 403)
        self.assertEqual(c.delete(f"/api/infusionsplaene/{e['id']}/").status_code, 204)
        plan = self.freigegebener_plan()
        self.assertEqual(c.post(f"/api/infusionsplaene/{plan.id}/vorschau/", {}, format="json").status_code, 400)


class PlanHinweise(PlanHilfen, Grundlage):
    """Hinweise aus Labor und Gewicht im Plan-Editor (F187): nur zum Prüfen, nie eine Mengenempfehlung (MDR)."""

    URL = "/api/infusionsplaene/hinweise/"

    def gewicht(self, kg, tage_her=0, patient=None):
        r = client_fuer(self.mitarbeiter).post("/api/gewichte/", {
            "patient": (patient or self.patient).id, "gewicht_kg": kg,
            "gemessen_am": str(timezone.localdate() - timedelta(days=tage_her))}, format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def befund(self, tage_her, werte, patient=None):
        from stammdaten.models import Laborparameter

        r = client_fuer(self.mitarbeiter).post("/api/laborbefunde/", {
            "patient": (patient or self.patient).id, "abgenommen_am": str(timezone.localdate() - timedelta(days=tage_her)),
            "werte": [{"parameter": Laborparameter.objects.get(name=n).id, "wert": w, "referenz_von": v, "referenz_bis": b}
                      for n, w, v, b in werte],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def abrufen(self, client=None, patient=None, **parameter):
        c = client or client_fuer(self.mediziner)
        r = c.get(self.URL, {"patient": (patient or self.patient).id, **parameter})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_ausserhalb_des_referenzbereichs_mit_trend_nur_fuer_bestandteile_des_plans(self):
        self.gewicht("60.0", 1)
        self.freigegebener_plan()  # Magnesium, Natrium, Spurenelemente und Vitamine im Plan; kein Albumin
        # ältere Magnesiumwerte für den Verlauf, der jüngste nach dem Plan
        self.befund(60, [("Magnesium", "0.90", "0.66", "1.07")])
        self.befund(30, [("Magnesium", "0.75", "0.66", "1.07")])
        self.befund(0, [("Magnesium", "0.58", "0.66", "1.07"), ("Natrium", "140", "135", "145"),
                        ("Kupfer", "2000", "700", "1500"), ("Ferritin", "5", "30", "400"), ("Albumin", "20", "35", "52")])
        d = self.abrufen()
        labor = {h["parameter"]: h for h in d["hinweise"] if h["art"] == "labor"}
        self.assertEqual(set(labor), {"Magnesium", "Kupfer"})  # Natrium im Bereich; Ferritin, Albumin nicht im Plan
        mg = labor["Magnesium"]
        heute = timezone.localdate()
        self.assertEqual(mg["text"], f"Magnesium 0,58 mmol/l am {heute:%d.%m.%Y} – unter dem Referenzbereich (0,66–1,07). Bitte prüfen.")
        self.assertEqual(mg["richtung"], "niedrig")
        self.assertEqual(mg["trend"], "fallend")
        self.assertEqual([float(v["wert"]) for v in mg["verlauf"]], [0.9, 0.75, 0.58])
        self.assertEqual(labor["Kupfer"]["richtung"], "hoch")
        self.assertEqual(labor["Kupfer"]["bestandteil"], "Spurenelemente")
        # was im Formular gerade vorkommt, entscheidet: nur Natrium → kein Magnesium-Hinweis
        nur_natrium = self.abrufen(bestandteile="natrium,unbekannt")
        self.assertEqual(nur_natrium["bestandteile"], ["natrium"])
        self.assertFalse([h for h in nur_natrium["hinweise"] if h["art"] == "labor"])
        # mit Albumin im Formular erscheint der Albuminwert
        self.assertIn("Albumin", [h["parameter"] for h in self.abrufen(bestandteile="albumin")["hinweise"] if h["art"] == "labor"])
        # nie eine Mengenempfehlung: jeder Hinweis bittet ums Prüfen
        for h in d["hinweise"]:
            self.assertIn("prüfen", h["text"])
            self.assertNotRegex(h["text"], r"(?i)empfehl|erhöhen auf|reduzieren auf|dosis")

    def test_werte_vor_dem_letzten_plan_zaehlen_nicht(self):
        self.befund(20, [("Magnesium", "0.50", "0.66", "1.07")])
        self.gewicht("60.0", 1)
        self.freigegebener_plan()
        self.assertFalse([h for h in self.abrufen()["hinweise"] if h["art"] == "labor"])

    def test_kein_labor_und_altes_labor(self):
        d = self.abrufen()
        alt = [h for h in d["hinweise"] if h["art"] == "labor_alt"]
        self.assertEqual(len(alt), 1)
        self.assertIn("Noch kein Laborbefund", alt[0]["text"])
        self.assertIn("anlage", alt[0])  # Link „Blutuntersuchung anfordern“ (Anlage aus F174, falls vorhanden)
        self.befund(400, [("Natrium", "140", "135", "145")])
        alt = [h for h in self.abrufen()["hinweise"] if h["art"] == "labor_alt"]
        self.assertIn("Laborwerte älter als 12 Monate", alt[0]["text"])
        self.befund(10, [("Natrium", "140", "135", "145")])
        self.assertFalse([h for h in self.abrufen()["hinweise"] if h["art"] == "labor_alt"])

    def test_gewicht_deutlich_geaendert_seit_dem_plan(self):
        self.gewicht("60.0", 10)
        self.freigegebener_plan()
        self.befund(0, [("Natrium", "140", "135", "145")])
        self.assertFalse([h for h in self.abrufen()["hinweise"] if h["art"] == "gewicht"])
        self.gewicht("57.6", 0)  # −4 %: unter der Grenze (5 %)
        self.assertFalse([h for h in self.abrufen()["hinweise"] if h["art"] == "gewicht"])
        self.gewicht("54.0", 0)  # −10 %
        g = [h for h in self.abrufen()["hinweise"] if h["art"] == "gewicht"]
        self.assertEqual(len(g), 1)
        self.assertIn("von 60 auf 54 kg gesunken (−10 %)", g[0]["text"])

    def test_statistik_der_eigenen_plaene(self):
        self.gewicht("60.0", 1)
        for kalium in ("40", "50", "60"):
            self.freigegebener_plan(kalium_mmol=kalium)
        plaene = [h for h in self.abrufen()["hinweise"] if h["art"] == "plaene"]
        self.assertEqual([h["feld"] for h in plaene], ["kalium_mmol"])
        self.assertIn("Kalium wurde in den letzten 3 Plänen jeweils erhöht (40 → 50 → 60 mmol)", plaene[0]["text"])

    def test_rechte_und_testpatient(self):
        from accounts.models import Rolle
        from epm.pruefhilfen import benutzer

        self.assertEqual(client_fuer(self.betrachter).get(self.URL, {"patient": self.patient.id}).status_code, 200)
        self.assertEqual(client_fuer(benutzer("ohne", Rolle.KEINE)).get(self.URL, {"patient": self.patient.id}).status_code, 403)
        testzugang = client_fuer(benutzer("testzugang", Rolle.MEDIZINER, ist_test=True))
        # Testzugang sieht nur Testpatienten
        self.assertEqual(testzugang.get(self.URL, {"patient": self.patient.id}).status_code, 400)
        test = Patient.objects.create(nachname="Test", vorname="Tina", geburtsdatum="1970-01-01", ist_test=True)
        self.befund(0, [("Magnesium", "0.58", "0.66", "1.07")], patient=test)
        d = self.abrufen(client=testzugang, patient=test, bestandteile="magnesium")
        self.assertEqual([h["parameter"] for h in d["hinweise"] if h["art"] == "labor"], ["Magnesium"])
        # fremder Plan als Bezug → 400
        plan = self.freigegebener_plan()
        self.assertEqual(client_fuer(self.mediziner).get(self.URL, {"patient": test.id, "plan": plan.id}).status_code, 400)

    def test_fehlender_referenzbereich_im_katalog(self):
        """F190: Fehlt im Katalog der Referenzbereich eines Parameters, der zum Plan gehört, sagt der Editor, dass die
        Hinweise unvollständig sind – EPM trägt keine Bereiche selbst ein."""
        from stammdaten.models import Laborparameter

        d = self.abrufen(bestandteile="kalium,magnesium")
        fehlt = [h for h in d["hinweise"] if h["art"] == "referenz_fehlt"]
        self.assertEqual(len(fehlt), 1)
        self.assertIn("Für Kalium und Magnesium ist kein Referenzbereich hinterlegt", fehlt[0]["text"])
        kalium = Laborparameter.objects.get(name="Kalium")
        kalium.referenz_von, kalium.referenz_bis = Decimal("3.5"), Decimal("5.1")
        kalium.save()
        fehlt = [h for h in self.abrufen(bestandteile="kalium,magnesium")["hinweise"] if h["art"] == "referenz_fehlt"]
        self.assertEqual(fehlt[0]["parameter"], ["Magnesium"])
        # nicht im Plan → kein Hinweis zu fehlenden Bereichen
        self.assertFalse([h for h in self.abrufen(bestandteile="kalium")["hinweise"] if h["art"] == "referenz_fehlt"])
        # Katalogbereich gilt, wenn der Befund keinen eigenen mitbringt
        self.befund(0, [("Kalium", "6.0", None, None)])
        self.assertIn("Kalium", [h["parameter"] for h in self.abrufen(bestandteile="kalium")["hinweise"] if h["art"] == "labor"])
        # Vitamine als Gruppe gezählt
        self.assertRegex([h for h in self.abrufen(bestandteile="vitamine")["hinweise"] if h["art"] == "referenz_fehlt"][0]["text"],
                         r"Für \d+ Vitamine ist kein Referenzbereich")


class PlanPraxisvorgabe(PlanHilfen, Grundlage):
    """Mengen je kg für „Mengen nach Praxisvorgabe“ unter Vorlagen › Grenzwerte (Entscheidung der Praxis, F190)."""

    def test_vorbelegung_nutzt_einstellung_mit_grenzen_und_historie(self):
        from stammdaten.models import Einstellungen

        e = Einstellungen.aktuell()
        # Startwerte wie im Altsystem
        self.assertEqual([e.vorgabe_glucose_g_kg, e.vorgabe_magnesium_mmol_kg], [Decimal("3.5"), Decimal("0.2")])
        self.assertIsNone(e.vorgabe_geaendert_am)
        client_fuer(self.mitarbeiter).post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "60.0"}, format="json")
        c = client_fuer(self.mediziner)
        v = c.get(f"/api/infusionsplaene/vorbelegung/?patient={self.patient.id}").json()
        self.assertEqual(float(v["werte"]["glucose_g"]), 210.0)  # 60 × 3,5
        self.assertIsNone(v["stand"])
        a = client_fuer(self.admin)
        fassungen = Einstellungen.history.count()
        # Grenzen: nicht negativ, nicht unplausibel hoch
        r = a.patch("/api/einstellungen/", {"vorgabe_glucose_g_kg": "-1"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("vorgabe_glucose_g_kg", r.json())
        self.assertEqual(a.patch("/api/einstellungen/", {"vorgabe_kalium_mmol_kg": "11"}, format="json").status_code, 400)
        r = a.patch("/api/einstellungen/", {"vorgabe_glucose_g_kg": "4", "vorgabe_kalium_mmol_kg": "0"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()["vorgabe_geaendert_am"])
        self.assertEqual(Einstellungen.history.count(), fassungen + 1)
        v = c.get(f"/api/infusionsplaene/vorbelegung/?patient={self.patient.id}").json()
        self.assertEqual([float(v["werte"]["glucose_g"]), float(v["werte"]["kalium_mmol"])], [240.0, 0.0])
        self.assertIsNotNone(v["stand"])
        # Gewicht für den Plan gilt nach 6 Monaten als alt (Entscheidung 10.10.2026), einstellbar 1–60 Monate
        self.assertEqual(Einstellungen.aktuell().plan_gewicht_alter_monate, 6)
        self.assertEqual(a.patch("/api/einstellungen/", {"plan_gewicht_alter_monate": 0}, format="json").status_code, 400)
        self.assertEqual(a.patch("/api/einstellungen/", {"plan_gewicht_alter_monate": 4}, format="json").status_code, 200)
        # andere Einstellungen ändern den Stand der Vorgabe nicht
        stand = Einstellungen.aktuell().vorgabe_geaendert_am
        self.assertEqual(a.patch("/api/einstellungen/", {"kcal_max_tag": 4800}, format="json").status_code, 200)
        self.assertEqual(Einstellungen.aktuell().vorgabe_geaendert_am, stand)
        # im Audit-Log
        from audit.models import SystemEreignis

        self.assertTrue(SystemEreignis.objects.filter(objekt="Einstellungen", details__felder__contains=["vorgabe_glucose_g_kg"]).exists())
