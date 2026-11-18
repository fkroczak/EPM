"""Dreisprachigkeit der Laborparameter (RGC, 18.11.2026): Übersetzungen, Werterkennung, Auszug, Export und Import."""
from django.core.files.uploadedfile import SimpleUploadedFile

from epm.pruefhilfen import Grundlage, client_fuer
from scans.dienst import katalog
from scans.ocr import auswertung

from .models import Laborparameter


class Uebersetzungen(Grundlage):
    def test_startwerte_fuer_den_mitgelieferten_katalog(self):
        phosphat = Laborparameter.objects.get(name="Phosphat")
        self.assertEqual(phosphat.name_en, "Phosphate")
        self.assertTrue(phosphat.name_lv.startswith("Fosfors"))
        self.assertEqual(phosphat.name_in("lv"), phosphat.name_lv)
        self.assertEqual(Laborparameter(name="X").name_in("en"), "X")  # ohne Übersetzung: Deutsch
        self.assertFalse(Laborparameter.objects.filter(name_lv="").exists())

    def test_lettische_befunde_treffen_den_deutschen_parameter(self):
        index, eintraege = auswertung.katalog_index(katalog())

        def finde(label):
            p, _art, _t = auswertung._suche_parameter(label, index, eintraege)
            return p.name if p else None

        # Beispielbefunde der RGC (Paula Stradiņa slimnīca) – ohne eigene Parameter anzulegen
        self.assertEqual(finde("Fosfors neorganiskais"), "Phosphat")
        self.assertEqual(finde("Fosfāts"), "Phosphat")
        self.assertEqual(finde("Varš serumā"), "Kupfer")
        self.assertEqual(finde("Hemoglobīns"), "Hämoglobin")
        self.assertEqual(finde("Hematokrīts"), "Hämatokrit")
        self.assertEqual(finde("Leikocīti"), "Leukozyten")
        self.assertEqual(finde("Trombocīti"), "Thrombozyten")
        self.assertEqual(finde("MCV Eritroc.vid.tilp."), "MCV")
        self.assertEqual(finde("MCH Vid.Hb saturs er."), "MCH")
        self.assertEqual(finde("MCHC Vid.Hb konc.er."), "MCHC")
        self.assertEqual(finde("Total protein"), "Gesamteiweiß")
        # anderer Wert, auch wenn der Name gleich anfängt
        self.assertIsNone(finde("Kalcijs jonizētais"))
        self.assertIsNone(finde("Calcium ionisiert"))
        self.assertIsNone(finde("TSH receptoru antivielas"))
        # kurze Kürzel ohne abgekürzte Erläuterung bleiben gesperrt
        self.assertIsNone(finde("K gesamt"))
        self.assertIsNone(finde("RDW Eritr. anizocit."))  # nicht im Katalog

    def test_eigene_uebersetzung_wird_erkannt(self):
        p = Laborparameter.objects.get(name="Lipase")
        p.name_lv = "Aizkuņģa lipāze"
        p.save()
        index, eintraege = auswertung.katalog_index(katalog())
        treffer, _art, _t = auswertung._suche_parameter("Aizkuņģa lipāze", index, eintraege)
        self.assertEqual(treffer.id, p.id)


class ExportImport(Grundlage):
    def test_nur_mit_recht(self):
        c = client_fuer(self.betrachter)
        self.assertEqual(c.get("/api/laborparameter/export/").status_code, 403)
        self.assertEqual(c.get("/api/laborparameter/aus-vorlagen/").status_code, 403)
        self.assertEqual(c.post("/api/laborparameter/import/", {"zeilen": []}, format="json").status_code, 403)

    def test_export_und_reimport_mit_id(self):
        c = client_fuer(self.mitarbeiter)
        r = c.get("/api/laborparameter/export/")
        self.assertEqual(r.status_code, 200)
        text = r.content.decode("utf-8-sig")
        self.assertTrue(text.startswith("id;gruppe;name_de;name_en;name_lv"))
        self.assertIn("Phosphat;Phosphate;Fosfors", text)
        # Lettischen Namen in der Datei ändern und wieder einspielen: Vorschau, dann übernehmen
        neu = text.replace("Fosfors (neorganiskais)", "Fosfors neorganiskais")
        datei = SimpleUploadedFile("labor.csv", neu.encode("utf-8-sig"), content_type="text/csv")
        r = c.post("/api/laborparameter/import/", {"datei": datei}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        geaendert = [z for z in r.json()["zeilen"] if z["status"] == "ergaenzt"]
        self.assertEqual([z["name"] for z in geaendert], ["Phosphat"])
        self.assertEqual(geaendert[0]["aenderungen"]["name_lv"][1], "Fosfors neorganiskais")
        self.assertEqual(Laborparameter.objects.get(name="Phosphat").name_lv, "Fosfors (neorganiskais)")  # nur Vorschau
        r = c.post("/api/laborparameter/import/", {"zeilen": geaendert, "uebernehmen": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["ergaenzt"], ["Phosphat"])
        self.assertEqual(Laborparameter.objects.get(name="Phosphat").name_lv, "Fosfors neorganiskais")

    def test_aus_rgc_vorlagen(self):
        c = client_fuer(self.mitarbeiter)
        r = c.get("/api/laborparameter/aus-vorlagen/")
        self.assertEqual(r.status_code, 200, r.content)
        zeilen = r.json()["zeilen"]
        nach_name = {z["name"]: z for z in zeilen}
        self.assertEqual(nach_name["Phosphat"]["status"], "vorhanden")  # Übersetzungen schon da
        self.assertIn("Laboranforderung Basislabor", nach_name["Phosphat"]["quellen"])
        self.assertEqual(nach_name["Retikulozyten"]["status"], "neu")
        self.assertEqual(nach_name["Retikulozyten"]["name_lv"], "Retikulocīti")
        self.assertEqual(nach_name["GAD-Antikörper"]["name_en"], "GAD antibodies")
        # keine Bildgebung, keine Röhrchenübersicht
        self.assertFalse([z for z in zeilen if "Kontrastmittel" in (z.get("zeile") or "")])
        self.assertFalse([z for z in zeilen if "Pflicht:" in (z.get("zeile") or "")])
        # nur Angehaktes wird angelegt
        vorher = Laborparameter.objects.count()
        r = c.post("/api/laborparameter/import/", {"zeilen": [nach_name["Retikulozyten"]], "uebernehmen": True},
                   format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["neu"], ["Retikulozyten"])
        self.assertEqual(Laborparameter.objects.count(), vorher + 1)
        p = Laborparameter.objects.get(name="Retikulozyten")
        self.assertEqual((p.gruppe, p.name_lv, p.name_en), ("haematologie", "Retikulocīti", "Reticulocytes"))
        # CSV zum Herunterladen
        r = c.get("/api/laborparameter/aus-vorlagen/?als=csv")
        self.assertIn("Retikulozyten;Reticulocytes;Retikulocīti", r.content.decode("utf-8-sig"))

    def test_fehler_ohne_deutschen_namen(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/laborparameter/import/", {"zeilen": [{"name": "", "name_lv": "Kaut kas"}], "uebernehmen": True},
                   format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("deutsche Name", r.json()["fehler"])


class SpracheImKonto(Grundlage):
    def test_sprache_speichern_und_pruefen(self):
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.get("/api/auth/ich/").json()["sprache"], "de")
        r = c.patch("/api/auth/ich/", {"sprache": "lv"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["sprache"], "lv")
        self.assertEqual(c.patch("/api/auth/ich/", {"sprache": "fr"}, format="json").status_code, 400)
