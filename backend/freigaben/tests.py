"""Menü „Freigaben“: Datenpflege aus Altdaten-Freitext, Freigabe mit 60 s Rückgängig, Infusionspläne."""
from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer
from infusionen.models import Infusionsplan
from infusionen.tests import PlanHilfen
from patienten.models import Bezugsperson, Patient, PatientArzt
from stammdaten.models import Arzt

from . import datenpflege, dienst
from .models import Datenpflegevorschlag, Freigabe

TELEFON = "015788255675 (Hr. Pohlmann) 0157 8902 6736 (Fr. Pohlmann) 0524242667"
HAUSARZT = "Dr. Klaus Heuwing, Alleestr. 10, 46282 Dorsten / T. 02362-26960 / dorsten@praxis-heuwing.de"


class Erkennung(SimpleTestCase):
    pat = SimpleNamespace(vorname="Klaus", nachname="Pohlmann", geschlecht="m")

    def test_telefon_mit_namen(self):
        eintraege, rest = datenpflege.telefon_zerlegen(TELEFON)
        self.assertEqual(rest, "")
        self.assertEqual([e["nummer"] for e in eintraege], ["015788255675", "0157 8902 6736", "0524242667"])
        self.assertEqual(datenpflege.person_einordnen("Hr. Pohlmann", self.pat), {"eigen": True})
        frau = datenpflege.person_einordnen("Fr. Pohlmann", self.pat)
        self.assertEqual((frau["eigen"], frau["beziehung"], frau["name"], frau["sicher"]),
                         (False, "Ehefrau", "Frau Pohlmann", False))

    def test_beziehung_aus_dem_text(self):
        eintraege, _ = datenpflege.telefon_zerlegen("Tochter Anna 0171 1234567, 05242 4711 (abends)")
        self.assertEqual(eintraege[0]["label"], "Tochter Anna")
        p = datenpflege.person_einordnen("Tochter Anna", self.pat)
        self.assertEqual((p["beziehung"], p["name"], p["sicher"]), ("Tochter", "Anna", True))
        self.assertFalse(datenpflege._ist_person("abends"))
        self.assertTrue(datenpflege.ist_mobil("0171 1234567"))
        self.assertFalse(datenpflege.ist_mobil("05242 4711"))

    def test_zwei_nummern_nur_mit_leerzeichen(self):
        eintraege, _ = datenpflege.telefon_zerlegen("0524 242667 0171 1234567")
        self.assertEqual([e["nummer"] for e in eintraege], ["0524 242667", "0171 1234567"])

    def test_arzt_aus_freitext(self):
        w = datenpflege.arzt_zerlegen(HAUSARZT)
        self.assertEqual({k: w[k] for k in ("name", "strasse", "plz", "ort", "telefon", "email")},
                         {"name": "Dr. Klaus Heuwing", "strasse": "Alleestr. 10", "plz": "46282", "ort": "Dorsten",
                          "telefon": "02362-26960", "email": "dorsten@praxis-heuwing.de"})
        w = datenpflege.arzt_zerlegen("Praxis Dr. Meyer, Hauptstr. 5 33378 Rheda-Wiedenbrück, Tel. 05242 12345, "
                                      "Fax 05242 12346")
        self.assertEqual((w["plz"], w["telefon"], w["fax"]), ("33378", "05242 12345", "05242 12346"))

    def test_hinweise_der_uebernahme(self):
        html = ("<p>frei</p><p><strong>Telefon (vollständig, laut Altsystem):</strong> 0157 1 (Fr. X)</p>"
                "<p><strong>Größe (laut Altsystem):</strong> 2,5 m</p>")
        h = datenpflege.hinweise(html)
        self.assertEqual([(x["feld"], x["inhalt"]) for x in h], [("telefon", "0157 1 (Fr. X)"), (None, "2,5 m")])


class Ablauf(PlanHilfen, Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.pohlmann = Patient.objects.create(
            nachname="Pohlmann", vorname="Klaus", geschlecht="m", geburtsdatum=timezone.localdate() - timedelta(days=25000),
            telefon="015788255675 (Hr. Pohlmann) 0157 8902 6736 (Fr. …", hausarzt=HAUSARZT[:150],
            bemerkung=f"<p>sonst</p><p><strong>Telefon (vollständig, laut Altsystem):</strong> {TELEFON}</p>")

    def liste(self, c):
        r = c.get("/api/freigaben/")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def vorschlag(self, c):
        self.assertEqual(c.post("/api/freigaben/suchen/", {}, format="json").status_code, 200)
        return next(v for v in self.liste(c)["datenpflege"] if v["patient"]["id"] == self.pohlmann.id)

    def nach_ablauf(self):
        return dienst.faellige_umsetzen(timezone.now() + timedelta(seconds=61))

    def test_freigabe_mit_rueckgaengig_und_umsetzung(self):
        c = client_fuer(self.mitarbeiter)
        v = self.vorschlag(c)
        arten = [(s["art"], s.get("feld") or s.get("rolle") or s.get("titel")) for s in v["schritte"]]
        self.assertEqual(arten, [("bezugsperson", None), ("feld", "telefon"), ("feld", "telefon2"),
                                 ("hinweis", "Telefon (vollständig, laut Altsystem)"), ("arzt", "hausarzt"),
                                 ("feld", "hausarzt")])
        person = v["schritte"][0]
        self.assertEqual(person["werte"], {"beziehung": "Ehefrau", "name": "Frau Pohlmann", "telefon": "",
                                           "mobil": "0157 8902 6736", "email": ""})
        self.assertEqual(v["schritte"][1]["neu"], "015788255675")
        self.assertEqual(v["schritte"][2]["neu"], "0524242667")
        self.assertEqual(v["schritte"][4]["arzt_wahl"], "neu")

        # freigeben → noch nichts in der Akte; zurücknehmen geht
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertGreater(r.json()["sekunden"], 50)
        self.assertEqual(Bezugsperson.objects.filter(patient=self.pohlmann).count(), 0)
        self.assertEqual(Arzt.objects.count(), 0)
        self.assertEqual(c.post(f"/api/freigaben/{r.json()['id']}/zuruecknehmen/").status_code, 200)
        self.assertEqual(self.nach_ablauf(), 0)
        self.assertEqual(Bezugsperson.objects.filter(patient=self.pohlmann).count(), 0)

        # erneut freigeben (Beziehung korrigiert), nach 60 s umgesetzt
        v = self.liste(c)["datenpflege"][0]
        v["schritte"][0]["werte"]["beziehung"] = "Ehefrau"
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.nach_ablauf(), 1)
        self.assertEqual(Freigabe.objects.get(pk=r.json()["id"]).status, "umgesetzt")
        p = Patient.objects.get(pk=self.pohlmann.pk)
        self.assertEqual((p.telefon, p.telefon2, p.hausarzt, p.bemerkung), ("015788255675", "0524242667", "",
                                                                             "<p>sonst</p>"))
        b = Bezugsperson.objects.get(patient=p)
        self.assertEqual((b.name, b.beziehung.wert, b.mobil, b.angelegt_von), ("Frau Pohlmann", "Ehefrau",
                                                                               "0157 8902 6736", self.mitarbeiter))
        z = PatientArzt.objects.get(patient=p)
        self.assertEqual((z.rolle, z.arzt.name, z.arzt.plz, z.arzt.email),
                         ("hausarzt", "Dr. Klaus Heuwing", "46282", "dorsten@praxis-heuwing.de"))
        self.assertEqual(Datenpflegevorschlag.objects.get(pk=v["id"]).status, "umgesetzt")
        self.assertEqual(self.liste(c)["datenpflege"], [])

        # derselbe Hausarzt bei einer zweiten Akte: Treffer statt Doppel
        zweite = Patient.objects.create(nachname="Beispiel", vorname="Berta", geschlecht="w",
                                        geburtsdatum=timezone.localdate() - timedelta(days=20000),
                                        hausarzt="Dr. med. Klaus Heuwing, Dorsten")
        c.post("/api/freigaben/suchen/", {"patient": zweite.id}, format="json")
        v2 = self.liste(c)["datenpflege"][0]
        self.assertEqual(v2["schritte"][0]["arzt_wahl"], z.arzt_id)
        c.post(f"/api/freigaben/datenpflege/{v2['id']}/freigeben/", {"schritte": v2["schritte"]}, format="json")
        self.nach_ablauf()
        self.assertEqual(Arzt.objects.count(), 1)
        self.assertEqual(PatientArzt.objects.get(patient=zweite).arzt_id, z.arzt_id)

    def test_abhaengigkeit_ohne_bezugsperson_bleibt_telefon(self):
        """Wird die Bezugsperson abgewählt, darf ihre Nummer nicht aus dem Telefonfeld verschwinden."""
        c = client_fuer(self.mitarbeiter)
        v = self.vorschlag(c)
        v["schritte"][0]["an"] = False
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.nach_ablauf()
        p = Patient.objects.get(pk=self.pohlmann.pk)
        self.assertEqual(p.telefon, self.pohlmann.telefon)
        self.assertIn("Telefon (vollständig", p.bemerkung)
        self.assertEqual(p.hausarzt, "")  # Arzt-Schritte unabhängig davon umgesetzt
        self.assertFalse(Bezugsperson.objects.filter(patient=p).exists())

    def test_akte_inzwischen_geaendert(self):
        c = client_fuer(self.mitarbeiter)
        v = self.vorschlag(c)
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        Patient.objects.filter(pk=self.pohlmann.pk).update(telefon="0800 1")
        self.nach_ablauf()
        f = Freigabe.objects.get(pk=r.json()["id"])
        self.assertEqual(f.status, "fehler")
        self.assertIn("inzwischen geändert", f.fehler)
        self.assertFalse(Bezugsperson.objects.filter(patient=self.pohlmann).exists())
        self.assertEqual(Datenpflegevorschlag.objects.get(pk=v["id"]).status, "veraltet")

    def test_rechte(self):
        self.assertEqual(client_fuer(self.betrachter).get("/api/freigaben/").status_code, 403)
        c = client_fuer(self.mitarbeiter)
        v = self.vorschlag(c)
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        # zurücknehmen nur, wer freigegeben hat
        self.assertEqual(client_fuer(self.mediziner).post(f"/api/freigaben/{r.json()['id']}/zuruecknehmen/")
                         .status_code, 403)
        # Admins schreiben nur bei Testpatienten: Freigabe wird gleich abgelehnt
        self.assertEqual(client_fuer(self.admin).post(f"/api/freigaben/datenpflege/{v['id']}/verwerfen/").status_code,
                         200 if self.admin.hat_recht("akten_bearbeiten") else 403)

    def test_infusionsplan_im_menue(self):
        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        c.patch(f"/api/infusionsplaene/{e['id']}/", self.plan_daten(), format="json")
        daten = self.liste(c)
        self.assertEqual([p["id"] for p in daten["plaene"]], [e["id"]])
        self.assertTrue(daten["plaene"][0]["zeilen"])
        self.assertEqual(client_fuer(self.mitarbeiter).post(f"/api/freigaben/plaene/{e['id']}/freigeben/")
                         .status_code, 403)
        r = c.post(f"/api/freigaben/plaene/{e['id']}/freigeben/")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Infusionsplan.objects.get(pk=e["id"]).status, "entwurf")
        self.assertEqual(self.liste(c)["plaene"], [])  # wartet: nicht doppelt anbieten
        self.nach_ablauf()
        self.assertEqual(Infusionsplan.objects.get(pk=e["id"]).status, "aktuell", Freigabe.objects.get().fehler)


class KiGegenlesen(Grundlage):
    def test_ki_ergaenzt_nur_die_beziehung(self):
        from ki.modell import Antwort

        p = Patient.objects.create(nachname="Kunz", vorname="Otto", geschlecht="m", telefon="05242 1 (Frau Lehmann 0171 5555555)",
                                   geburtsdatum=timezone.localdate() - timedelta(days=25000))
        p.telefon = "05242 123456, Frau Lehmann 0171 5555555"
        p.save()
        v = datenpflege.erstellen(p)
        person = next(s for s in v.schritte if s["art"] == "bezugsperson")
        self.assertEqual((person["werte"]["beziehung"], person["sicher"], v.ki_offen), ("", False, True))

        class Modell:
            def chat(self, *a, **k):
                return Antwort('{"nummern": [{"nummer": "0171 5555555", "eigen": false, "beziehung": "Tochter", '
                               '"name": "Frau Lehmann", "sicher": true}, {"nummer": "x", "eigen": false, '
                               '"beziehung": "Erfunden", "name": "", "sicher": true}]}', 0.1)

        v = datenpflege.ki_pruefen(v, Modell())
        person = next(s for s in v.schritte if s["art"] == "bezugsperson")
        self.assertEqual((person["werte"]["beziehung"], person["werte"]["mobil"], v.verfahren, v.ki_offen),
                         ("Tochter", "0171 5555555", "regeln+ki", False))
        self.assertIn("KI schlägt", person["hinweis"])
