"""Vorlagen-Portal einfacher (F180): Beschreibung in Alltagssprache, lesbare Datenfelder, frühere Fassung
wiederherstellen, Vorlage als eigene Vorlage kopieren."""
from audit.models import SystemEreignis
from epm.pruefhilfen import Grundlage, client_fuer

from .models import Dokumentvorlage, EigenesSchreiben
from .tests import import_erledigt


class PortalTest(Grundlage):
    def setUp(self):
        self.c = client_fuer(self.mitarbeiter)

    def test_uebersicht_in_alltagssprache(self):
        liste = {v["art"]: v for v in self.c.get("/api/vorlagen/").json()}
        # alle festen Arten mit „Wofür?“, „Wo benutzt?“ und Gruppe – auch Bericht und Sprechstunde
        for art in Dokumentvorlage.Art.values:
            self.assertTrue(liste[art]["wofuer"], art)
            self.assertTrue(liste[art]["wo"], art)
            self.assertIn(liste[art]["gruppe"], {"schreiben", "plaene", "datenschutz", "rgc"}, art)
        self.assertIn("Schreiben und E-Mail", liste["terminbestaetigung"]["wo"])
        self.assertIn("Kalender", liste["patientenankuendigung"]["wo"])
        self.assertEqual(liste["einwilligung"]["gruppe"], "datenschutz")

    def test_datenfelder_mit_lesbarem_namen_und_gruppe(self):
        felder = {f["name"]: f for f in self.c.get("/api/vorlagen/terminbestaetigung/").json()["felder"]}
        self.assertEqual(felder["Patient.Briefanrede"]["bezeichnung"], "Briefanrede („Sehr geehrte Frau …“)")
        self.assertEqual(felder["Patient.Briefanrede"]["gruppe"], "Patient")
        self.assertEqual(felder["Termin.Uhrzeit"]["gruppe"], "Termin")
        self.assertEqual(felder["Absender.Telefon"]["gruppe"], "Absender (Briefkopf)")
        self.assertEqual(felder["Heute"]["bezeichnung"], "Heutiges Datum")
        # ohne eigenen Namen: kurze Beschreibung aus felder.py
        plan = {f["name"]: f for f in self.c.get("/api/vorlagen/infusionsplan/").json()["felder"]}
        self.assertEqual(plan["Plan.kcal"]["bezeichnung"], "Energie (kcal)")
        self.assertEqual(plan["Plan.kcal"]["gruppe"], "Infusionsplan")
        for f in plan.values():
            self.assertLessEqual(len(f["bezeichnung"]), 60, f["name"])

    def test_fruehere_fassung_wiederherstellen(self):
        import_erledigt()
        art = "patientenaufnahme"
        alt = self.c.get(f"/api/vorlagen/{art}/entwurf/").json()["bloecke"]
        v1 = Dokumentvorlage.aktive(art).version
        neu = [b for b in alt if b["typ"] != "fusszeile"]
        self.assertEqual(self.c.put(f"/api/vorlagen/{art}/entwurf/", {"bloecke": neu}, format="json").status_code, 200)
        self.assertEqual(self.c.post(f"/api/vorlagen/{art}/veroeffentlichen/").status_code, 200)
        self.assertEqual(Dokumentvorlage.aktive(art).version, v1 + 1)

        # Betrachter darf nicht, unbekannte Fassung gibt es nicht
        self.assertEqual(client_fuer(self.betrachter).post(f"/api/vorlagen/{art}/versionen/{v1}/wiederherstellen/")
                         .status_code, 403)
        self.assertEqual(self.c.post(f"/api/vorlagen/{art}/versionen/999/wiederherstellen/").status_code, 404)

        r = self.c.post(f"/api/vorlagen/{art}/versionen/{v1}/wiederherstellen/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["ist_entwurf"], r.json()["notiz"]), (True, f"wiederhergestellt aus Fassung {v1}"))
        self.assertEqual(r.json()["bloecke"], alt)
        # in Gebrauch bleibt die neue Fassung, bis freigegeben ist; die Fassungen selbst bleiben unverändert
        self.assertEqual(Dokumentvorlage.aktive(art).version, v1 + 1)
        self.assertEqual(Dokumentvorlage.objects.get(art=art, version=v1).bloecke, alt)
        self.assertTrue(SystemEreignis.objects.filter(details__aktion=f"Fassung {v1} als Entwurf wiederhergestellt").exists())
        # ein vorhandener Entwurf wird ersetzt (es gibt je Art nur einen)
        self.assertEqual(self.c.post(f"/api/vorlagen/{art}/versionen/{v1 + 1}/wiederherstellen/").status_code, 200)
        self.assertEqual(Dokumentvorlage.objects.filter(art=art, status="entwurf").count(), 1)
        self.assertEqual(Dokumentvorlage.entwurf_von(art).bloecke, neu)
        self.assertEqual(self.c.post(f"/api/vorlagen/{art}/veroeffentlichen/").json()["aktiv"]["version"], v1 + 2)

    def test_als_eigene_vorlage_kopieren(self):
        quelle = Dokumentvorlage.aktive("terminbestaetigung")
        self.assertEqual(client_fuer(self.betrachter).post("/api/vorlagen/terminbestaetigung/duplizieren/",
                                                           {"name": "x"}, format="json").status_code, 403)
        self.assertEqual(self.c.post("/api/vorlagen/terminbestaetigung/duplizieren/", {"name": ""}, format="json")
                         .status_code, 400)
        r = self.c.post("/api/vorlagen/terminbestaetigung/duplizieren/",
                        {"name": "Terminbestätigung Klinik", "beschreibung": "für Termine in der Klinik"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertTrue(d["art"].startswith("eigen-"))
        self.assertEqual((d["name"], d["aktiv"]["version"], d["gruppe"], d["wofuer"]),
                         ("Terminbestätigung Klinik", 1, "eigen", "für Termine in der Klinik"))
        # mit Termin, weil die Vorlage den Termin benutzt
        self.assertTrue(EigenesSchreiben.objects.get(schluessel=d["art"]).mit_termin)
        kopie = Dokumentvorlage.aktive(d["art"])
        self.assertEqual(kopie.bloecke, quelle.bloecke)
        self.assertIn("Kopie von „Terminbestätigung Sprechstunde“", kopie.notiz)
        # die Kopie ist in der Akte wählbar
        self.assertIn(d["art"], [x["art"] for x in self.c.get("/api/schreiben/").json()])
        # derselbe Name geht kein zweites Mal
        self.assertEqual(self.c.post("/api/vorlagen/terminbestaetigung/duplizieren/",
                                     {"name": "terminbestätigung klinik"}, format="json").status_code, 400)

    def test_kopieren_nur_mit_erlaubten_feldern(self):
        """Der Infusionsplan hat Datenfelder des Plans – die gibt es in eigenen Schreiben nicht."""
        vorher = EigenesSchreiben.objects.count()
        r = self.c.post("/api/vorlagen/infusionsplan/duplizieren/", {"name": "Plan-Kopie"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("lässt sich nicht als eigene Vorlage kopieren", r.json()["fehler"])
        self.assertEqual(EigenesSchreiben.objects.count(), vorher)
