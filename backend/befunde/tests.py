"""Laborbefunde und BIA-Messungen (F112–F114) gegen die echte Datenbank."""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer
from stammdaten.models import Laborparameter

from .models import BiaMessung, Laborbefund


def parameter(name) -> Laborparameter:
    return Laborparameter.objects.get(name=name)


class LaborTest(Grundlage):
    def test_katalog_ist_angelegt(self):
        """Alices Liste steht als Katalog bereit – mit Gruppen und vorbelegten Einheiten (F112)."""
        self.assertGreaterEqual(Laborparameter.objects.count(), 60)
        self.assertEqual(parameter("GPT (ALT)").einheit, "U/l")
        self.assertEqual(parameter("Kreatinin").gruppe, Laborparameter.Gruppe.NIERE)
        # je eigener Parameter statt einer Sammelzeile (U46)
        for name in ("Vitamin B1", "Vitamin B12", "Folsäure", "Vitamin K1", "Vitamin K2",
                     "Calcidiol (25-Hydroxy-Vitamin D)", "Calcitriol (1,25-Dihydroxy-Vitamin D)"):
            self.assertTrue(Laborparameter.objects.filter(name=name).exists(), name)

    def test_katalog_lesen_ohne_vorlagenrecht(self):
        """Die Erfassungsmaske braucht den Katalog – lesen darf ihn jeder Angemeldete."""
        r = client_fuer(self.betrachter).get("/api/laborparameter/?aktiv=true")
        self.assertEqual(r.status_code, 200, r.content)
        namen = [p["name"] for p in r.json()]
        self.assertIn("Ferritin", namen)

    def test_befund_mit_werten_anlegen(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/laborbefunde/", {
            "patient": self.patient.id, "abgenommen_am": "2026-10-01", "labor": "Labor Dr. Wagner",
            "beurteilung": "<p>Ferritin niedrig <script>x</script></p>",
            "werte": [
                {"parameter": parameter("Ferritin").id, "wert": "18"},
                {"parameter": parameter("Natrium").id, "wert": "138", "einheit": "mmol/l"},
                # Freitext für Tumormarker und genetische Parameter (nicht im Katalog)
                {"freitext_name": "CA 19-9", "wert": "12.4", "einheit": "U/ml"},
                # Angabe, die keine Zahl ist (U47)
                {"freitext_name": "HFE-Mutation", "wert_text": "negativ"},
            ],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertEqual(d["anzahl_werte"], 4)
        # Einheit wird aus dem Katalog vorbelegt, wenn sie nicht mitgeschickt wird
        werte = {w["bezeichnung"]: w for w in d["werte"]}
        self.assertEqual(werte["Ferritin"]["einheit"], "µg/l")
        self.assertEqual(werte["CA 19-9"]["anzeige_wert"], "12,4")
        self.assertEqual(werte["HFE-Mutation"]["anzeige_wert"], "negativ")
        self.assertNotIn("<script>", d["beurteilung"])

    def test_leere_und_doppelte_werte_abgelehnt(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/laborbefunde/", {"patient": self.patient.id, "werte": [
            {"parameter": parameter("Ferritin").id}]}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        r = c.post("/api/laborbefunde/", {"patient": self.patient.id, "werte": [
            {"parameter": parameter("Ferritin").id, "wert": "18"},
            {"parameter": parameter("Ferritin").id, "wert": "20"}]}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("zweimal", str(r.content, "utf-8"))

    def test_abnahme_in_der_zukunft_abgelehnt(self):
        c = client_fuer(self.mitarbeiter)
        morgen = (timezone.localdate() + timedelta(days=1)).isoformat()
        r = c.post("/api/laborbefunde/", {"patient": self.patient.id, "abgenommen_am": morgen,
                                          "werte": [{"freitext_name": "X", "wert": "1"}]}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

    def test_werte_werden_beim_aendern_ersetzt(self):
        c = client_fuer(self.mitarbeiter)
        befund = c.post("/api/laborbefunde/", {"patient": self.patient.id, "werte": [
            {"parameter": parameter("Ferritin").id, "wert": "18"}]}, format="json").json()
        r = c.patch(f"/api/laborbefunde/{befund['id']}/", {"werte": [
            {"parameter": parameter("Ferritin").id, "wert": "25"},
            {"parameter": parameter("Zink").id, "wert": "700"}]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["anzahl_werte"], 2)
        self.assertEqual(Laborbefund.objects.get(pk=befund["id"]).werte.get(parameter__name="Ferritin").wert,
                         Decimal("25"))

    def test_verlauf_eines_parameters(self):
        """Werte eines Parameters über die Zeit – Grundlage für ein Diagramm (U58)."""
        c = client_fuer(self.mitarbeiter)
        for tag, wert in (("2026-04-01", "12"), ("2026-07-01", "30"), ("2026-10-01", "48")):
            c.post("/api/laborbefunde/", {"patient": self.patient.id, "abgenommen_am": tag, "werte": [
                {"parameter": parameter("Ferritin").id, "wert": wert}]}, format="json")
        r = c.get(f"/api/laborbefunde/verlauf/?patient={self.patient.id}&parameter={parameter('Ferritin').id}")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d["parameter"]["einheit"], "µg/l")
        self.assertEqual([p["wert"] for p in d["punkte"]], [12.0, 30.0, 48.0])

    def test_referenzbereich_markiert_abweichung(self):
        p = parameter("Ferritin")
        p.referenz_von, p.referenz_bis = Decimal("30"), Decimal("300")
        p.save()
        c = client_fuer(self.mitarbeiter)
        d = c.post("/api/laborbefunde/", {"patient": self.patient.id, "werte": [
            {"parameter": p.id, "wert": "18"}]}, format="json").json()
        self.assertEqual(d["werte"][0]["ausserhalb"], "niedrig")

    def test_betrachter_darf_nicht_erfassen(self):
        r = client_fuer(self.betrachter).post("/api/laborbefunde/", {"patient": self.patient.id, "werte": [
            {"freitext_name": "X", "wert": "1"}]}, format="json")
        self.assertEqual(r.status_code, 403, r.content)


class BiaTest(Grundlage):
    def werte(self, **extra):
        return {"patient": self.patient.id, "gemessen_am": "2026-10-01", "gewicht_kg": "62.4", "bcm_kg": "24.1",
                "fettmasse_kg": "18.6", "ecw_prozent": "46.2", "koerperwasser_l": "32.8", "bmi": "21.6",
                "beurteilung": "<p>stabil</p>", **extra}

    def test_messung_anlegen_mit_gewichtsuebernahme(self):
        """Das Gewicht der BIA landet auf Wunsch im Gewichtsverlauf – einmal eingetragen genügt (U50)."""
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/bia-messungen/", self.werte(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertIsNotNone(d["gewichtsmessung"])
        self.assertEqual(d["magermasse_kg"], 43.8)
        messung = self.patient.gewichte.get()
        self.assertEqual(messung.gewicht_kg, Decimal("62.4"))
        self.assertEqual(messung.notiz, "aus der BIA-Messung")

    def test_korrektur_geht_in_den_gewichtsverlauf(self):
        c = client_fuer(self.mitarbeiter)
        d = c.post("/api/bia-messungen/", self.werte(), format="json").json()
        r = c.patch(f"/api/bia-messungen/{d['id']}/", {"gewicht_kg": "61.0", "gemessen_am": "2026-09-30"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        messung = self.patient.gewichte.get()
        self.assertEqual((messung.gewicht_kg, str(messung.gemessen_am)), (Decimal("61.0"), "2026-09-30"))
        self.assertEqual(messung.history.first().history_user, self.mitarbeiter)

    def test_ohne_uebernahme_kein_gewichtseintrag(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/bia-messungen/", self.werte(gewicht_uebernehmen=False), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.json()["gewichtsmessung"])
        self.assertEqual(self.patient.gewichte.count(), 0)

    def test_bmi_vorschlag_aus_groesse(self):
        self.patient.groesse_cm = Decimal("170.0")
        self.patient.save()
        c = client_fuer(self.mitarbeiter)
        d = c.post("/api/bia-messungen/", self.werte(bmi=None), format="json").json()
        self.assertEqual(d["bmi_berechnet"], 21.6)
        self.assertIsNone(d["bmi"])

    def test_unplausible_werte_abgelehnt(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/bia-messungen/", self.werte(fettmasse_kg="80.0"), format="json")
        self.assertEqual(r.status_code, 400, r.content)
        r = c.post("/api/bia-messungen/", self.werte(ecw_prozent="140.0"), format="json")
        self.assertEqual(r.status_code, 400, r.content)

    def test_phasenwinkel(self):
        """Phasenwinkel als eigenes Feld (Wunsch DSKM 16.11.2026); allein reicht er als Messwert."""
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/bia-messungen/", {"patient": self.patient.id, "gemessen_am": "2026-10-01",
                                           "phasenwinkel_grad": "4.6"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["phasenwinkel_grad"], 4.6)
        r = c.post("/api/bia-messungen/", self.werte(phasenwinkel_grad="45.0"), format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("phasenwinkel_grad", r.json())

    def test_leere_messung_abgelehnt(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/bia-messungen/", {"patient": self.patient.id, "gemessen_am": "2026-10-01"}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

    def test_abgeschlossene_akte_gesperrt(self):
        self.patient.abgeschlossen_am = timezone.localdate()
        self.patient.abschluss_anlass = self.patient.Abschlussanlass.THERAPIE_BEENDET
        self.patient.save()
        r = client_fuer(self.mitarbeiter).post("/api/bia-messungen/", self.werte(), format="json")
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(BiaMessung.objects.count(), 0)
