"""Scans und Texterkennung (F160–F167) gegen die echte Datenbank – mit echter Erkennung (Tesseract, PP-OCR).

Die Erkennung läuft hier im Testprozess (``dienst.bearbeiten``) statt im OCR-Dienst; es sind dieselben Funktionen.
In GitHub Actions müssen beide Verfahren bereitstehen (``EPM_OCR_PADDLE_PFLICHT=1``).
"""
import io
import os
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from accounts.models import Rolle
from audit.models import SystemEreignis
from befunde.models import BiaMessung, Laborbefund
from epm.pruefhilfen import Grundlage, benutzer, client_fuer
from patienten.models import Diagnose, Dokument, DokumentText, Gewichtsmessung, Patient
from stammdaten.models import Einstellungen

from . import dienst, testbilder
from .models import Scan, ScanSeite
from .ocr import auswertung, einheiten, fusion, laden
from .ocr.erkennung import seite_erkennen, verfahren_stand

SCANS = Path(tempfile.mkdtemp(prefix="epm-scans-test-"))
KATALOG_BEISPIEL = [
    {"id": 1, "name": "Natrium", "kurzname": "Na", "einheit": "mmol/l", "gruppe": "elektrolyte", "suchbegriffe": ""},
    {"id": 2, "name": "Kalium", "kurzname": "K", "einheit": "mmol/l", "gruppe": "elektrolyte", "suchbegriffe": ""},
    {"id": 3, "name": "Albumin", "kurzname": "", "einheit": "g/l", "gruppe": "eiweiss_fett", "suchbegriffe": ""},
    {"id": 4, "name": "Kreatinin", "kurzname": "Krea", "einheit": "mg/dl", "gruppe": "niere", "suchbegriffe": ""},
    {"id": 5, "name": "GPT (ALT)", "kurzname": "GPT", "einheit": "U/l", "gruppe": "transaminasen",
     "suchbegriffe": ""},
    {"id": 6, "name": "Zink", "kurzname": "Zn", "einheit": "µg/l", "gruppe": "spurenelemente", "suchbegriffe": ""},
    {"id": 7, "name": "Ferritin", "kurzname": "", "einheit": "µg/l", "gruppe": "eisen", "suchbegriffe": "Ferr."},
]


def _seite(*reihen):
    """Ergebnis-JSON einer Seite aus Reihen von Wörtern (Sicherheit 0,95)."""
    aus, y = [], 10
    for r in reihen:
        x, stuecke = 10, []
        for wort in r.split():
            stuecke.append([wort, x, y, 10 * len(wort), 20, 0.95])
            x += 10 * len(wort) + 12
        aus.append([{"q": "t", "w": stuecke}])
        y += 30
    return {"breite": 2000, "hoehe": 3000, "reihen": aus}


# ======================================================================= ohne Datenbank, ohne Erkennung
class SparmodusTest(SimpleTestCase):
    def test_modus_nach_speicher_und_einstellung(self):
        from unittest import mock

        from .ocr import paddle

        with mock.patch.dict(os.environ, {"EPM_OCR_MODUS": "auto"}):
            with mock.patch.object(paddle, "speicher_mb", return_value=1536):
                self.assertEqual(paddle.modus(), "sparsam")   # Test-VM: 4 GB RAM, Grenze 1,5 GB
            with mock.patch.object(paddle, "speicher_mb", return_value=3072):
                self.assertEqual(paddle.modus(), "voll")      # VPS mit 8 GB, Grenze 3 GB
            with mock.patch.object(paddle, "speicher_mb", return_value=None):
                self.assertEqual(paddle.modus(), "voll")
        with mock.patch.dict(os.environ, {"EPM_OCR_MODUS": "sparsam"}):
            self.assertEqual(paddle.modus(), "sparsam")
        with mock.patch.dict(os.environ, {"EPM_OCR_MODUS": "voll"}), \
                mock.patch.object(paddle, "speicher_mb", return_value=1000):
            self.assertEqual(paddle.modus(), "voll")

    def test_speicher_wird_gelesen(self):
        from .ocr import paddle

        mb = paddle.speicher_mb()
        self.assertTrue(mb is None or mb > 100)


class EinheitenTest(SimpleTestCase):
    def test_lesefehler_der_einheiten(self):
        """Typische Fehler der Erkennung („dI“, „Hg/dl“ statt „µg/dl“, „mmol/1“) werden repariert."""
        for gelesen, richtig in [("mg/dI", "mg/dl"), ("g/di", "g/dl"), ("Hg/di", "µg/dl"), ("Mg/dl", "µg/dl"),
                                 ("ug/l", "µg/l"), ("U/I", "U/l"), ("mmol/1", "mmol/l"), ("ng/mli", "ng/ml"),
                                 ("G/l", "G/l"), ("g/l", "g/l"), ("%", "%")]:
            self.assertEqual(einheiten.einheit(gelesen), richtig, gelesen)
        self.assertIsNone(einheiten.einheit("Hauptstraße"))

    def test_einheiten_mit_zusatz_und_ohne_schraegstrich(self):
        """„pg/Ery“ (MCH), „ml/min/1,73m²KOF“ (eGFR), „l/l“ (Hämatokrit), Schrägstrich nicht gelesen („mmol1“)."""
        for gelesen, richtig in [("pg/Ery", "pg"), ("ml/min/1,73m²KOF", "ml/min/1,73 m²"),
                                 ("ml/min/1,73m2KOF", "ml/min/1,73 m²"), ("l/l", "l/l"), ("I/l", "l/l"),
                                 ("mmol1", "mmol/l"), ("mmolI", "mmol/l"), ("µmol1", "µmol/l"), ("mgdl", "mg/dl")]:
            self.assertEqual(einheiten.einheit(gelesen), richtig, gelesen)
        self.assertEqual(einheiten.faktor("l/l", "%"), Decimal(100))

    def test_einheit_erschliessen(self):
        """Ohne gelesene Einheit: Hämatokrit 0,37 passt nur zu l/l; ein plausibler Wert bleibt in der Katalogeinheit."""
        self.assertEqual(einheiten.einheit_raten("haematokrit", Decimal("0.37"), "%"), "l/l")
        self.assertIsNone(einheiten.einheit_raten("haematokrit", Decimal("37"), "%"))
        self.assertIsNone(einheiten.einheit_raten("tumormarker", Decimal("0.37"), "%"))

    def test_umrechnung(self):
        self.assertEqual(einheiten.faktor("g/dl", "g/l"), Decimal(10))
        self.assertEqual(einheiten.faktor("ng/ml", "µg/l"), Decimal(1))
        self.assertEqual(einheiten.faktor("pg/ml", "ng/l"), Decimal(1))
        # Stoffmenge ↔ Masse nur mit Molmasse des Stoffs
        f = einheiten.faktor("mg/dl", "µmol/l", "kreatinin")
        self.assertAlmostEqual(float(f), 88.4, places=1)
        self.assertIsNone(einheiten.faktor("mg/dl", "µmol/l", None))
        self.assertIsNone(einheiten.faktor("U/l", "mg/dl"))

    def test_zahlen(self):
        self.assertEqual(einheiten.zahl("3,2"), Decimal("3.2"))
        self.assertEqual(einheiten.zahl("1.234,5"), Decimal("1234.5"))
        self.assertEqual(einheiten.zahl("0.68"), Decimal("0.68"))
        self.assertIsNone(einheiten.zahl("12-"))

    def test_plausibilitaet(self):
        self.assertTrue(einheiten.plausibel("albumin", Decimal("3.4"), "g/dl"))
        self.assertFalse(einheiten.plausibel("albumin", Decimal("340"), "g/l"))  # Komma verloren
        self.assertIsNone(einheiten.plausibel("tumormarker", Decimal("1"), "U/ml"))


class AuswertungTest(SimpleTestCase):
    def test_laborwerte_mit_umrechnung_und_markierung(self):
        seite = _seite("Labor Dr. Beispiel MVZ", "Abnahme: 01.09.2026",
                       "Natrium 138 mmol/l 135 - 145", "Kalium 3,2 L mmol/l 3,5 - 5,1",
                       "Albumin 3,4 g/dl 3,5 - 5,2", "Kreatinin 1,12 mg/dI 0,50 - 0,90",
                       "GPT (ALAT) 35 U/l < 35", "Zink 62 Hg/di 70 - 120", "Ferr. 18 ng/ml",
                       "Tumormarker CA 19-9 < 2,0 U/ml < 37")
        a = auswertung.auswerten([seite], KATALOG_BEISPIEL)
        self.assertIn("labor", a["arten"])
        self.assertEqual(a["datum"], "2026-09-01")
        self.assertEqual(a["datum_quelle"], "abnahme")
        werte = {w["parameter_name"] or w["freitext_name"]: w for w in a["labor"]["werte"]}
        self.assertEqual(werte["Natrium"]["wert"], "138")
        self.assertEqual((werte["Natrium"]["referenz_von"], werte["Natrium"]["referenz_bis"]), ("135", "145"))
        self.assertEqual(werte["Kalium"]["wert"], "3.2")
        self.assertEqual(werte["Kalium"]["markierung"], "L")
        # g/dl → g/l (Einheit des Katalogs), Referenz mit umgerechnet
        self.assertEqual(werte["Albumin"]["wert"], "34")
        self.assertEqual(werte["Albumin"]["einheit"], "g/l")
        self.assertEqual(werte["Albumin"]["referenz_von"], "35")
        self.assertEqual(werte["Kreatinin"]["einheit"], "mg/dl")
        self.assertEqual(werte["GPT (ALT)"]["referenz_bis"], "35")
        # „Hg/di“ ist „µg/dl“: 62 µg/dl = 620 µg/l
        self.assertEqual(werte["Zink"]["wert"], "620")
        # Suchbegriff aus dem Katalog
        self.assertEqual(werte["Ferritin"]["wert"], "18")
        # nicht im Katalog: nur als Freitext, nicht vorgewählt; unter der Messgrenze als Text
        frei = werte["Tumormarker CA 19-9"]
        self.assertIsNone(frei["parameter"])
        self.assertFalse(frei["vorschlag"])
        self.assertEqual(frei["wert_text"], "< 2,0")

    def test_unplausibler_wert_nicht_vorgewaehlt(self):
        a = auswertung.auswerten([_seite("Natrium 1380 mmol/l", "Kalium 4,1 mmol/l", "Albumin 40 g/l")],
                                 KATALOG_BEISPIEL)
        natrium = next(w for w in a["labor"]["werte"] if w["parameter_name"] == "Natrium")
        self.assertFalse(natrium["vorschlag"])
        self.assertTrue(any("außerhalb" in h for h in natrium["hinweise"]))

    def test_kleines_blutbild_mit_methode_in_klammern_und_pfeilen(self):
        """Befund wie von Laboren üblich: Methode in Klammern hinter kurzen Namen (MCH, CRP, GGT), Pfeile vor
        auffälligen Werten, die die Erkennung als „1“ oder „!“ liest, Hämatokrit in l/l ohne gelesene Einheit."""
        katalog = KATALOG_BEISPIEL + [
            {"id": 20, "name": "Hämoglobin", "kurzname": "Hb", "einheit": "g/dl", "gruppe": "", "suchbegriffe": ""},
            {"id": 21, "name": "Hämatokrit", "kurzname": "Hkt", "einheit": "%", "gruppe": "", "suchbegriffe": ""},
            {"id": 22, "name": "MCH", "kurzname": "", "einheit": "pg", "gruppe": "", "suchbegriffe": ""},
            {"id": 23, "name": "MCV", "kurzname": "", "einheit": "fl", "gruppe": "", "suchbegriffe": ""},
            {"id": 24, "name": "CRP", "kurzname": "", "einheit": "mg/l", "gruppe": "", "suchbegriffe": ""},
            {"id": 25, "name": "Gamma-GT", "kurzname": "γ-GT", "einheit": "U/l", "gruppe": "", "suchbegriffe": ""},
            {"id": 26, "name": "GFR (CKD-EPI)", "kurzname": "", "einheit": "ml/min/1,73 m²", "gruppe": "",
             "suchbegriffe": ""},
            {"id": 27, "name": "Eisen", "kurzname": "", "einheit": "µg/dl", "gruppe": "", "suchbegriffe": ""},
        ]
        # Etikett links, Werte linksbündig ab x = 700 (10 Pixel je Zeichen); ein Pfeil ragt ein Zeichen heraus
        zeilen = [("Hamoglobin (Photometrie)", "12.4", 700, "g/dl 11.5 - 16.0"),
                  ("Hämatokrit (berechnet)", "0.37", 700, "M 0.36 - 0.48"),
                  ("MCH (berechnet)", "!27.7", 690, "pg/Ery 28.0 - 33.0"),
                  ("MCV (berechnet)", "83.3", 700, "fl 80.0 - 96.0"),
                  ("Eisen (Photometrie)", "10.8", 700, "µmol/l 10.7 - 32.2"),
                  ("Eisen (Umrechnung)", "60.3", 700, "µg/dl 60 - 180"),
                  ("Kalium (ISE)", "3.67", 700, "mmol1 3.5 - 5.1"),
                  ("eGFRCrea nach CKD-EPI (2009)", "188", 690, "ml/min/1,73m²KOF ≥ 90"),
                  ("GGT (Photometrie)", "25", 700, "U/l < 40"),
                  ("CRP (Turbidimetrie)", "118.69", 690, "mg/l < 5.0")]
        reihen, y = [], 10
        for etikett, wert, x_wert, rest in zeilen:
            woerter, x = [], 10
            for wort in etikett.split():
                woerter.append([wort, x, y, 10 * len(wort), 20, 0.95])
                x += 10 * len(wort) + 12
            woerter.append([wert, x_wert, y, 10 * len(wert), 20, 0.95])
            x = x_wert + 10 * len(wert) + 30
            for wort in rest.split():
                woerter.append([wort, x, y, 10 * len(wort), 20, 0.95])
                x += 10 * len(wort) + 12
            reihen.append([{"q": "p", "w": woerter}])
            y += 30
        werte = auswertung.laborwerte(auswertung.reihen_aus([{"breite": 2000, "hoehe": 3000, "reihen": reihen}]),
                                      katalog)
        gewaehlt = {w["parameter_name"]: w for w in werte if w["vorschlag"]}
        self.assertEqual(set(gewaehlt), {"Hämoglobin", "Hämatokrit", "MCH", "MCV", "Eisen", "Kalium",
                                         "GFR (CKD-EPI)", "Gamma-GT", "CRP"})
        self.assertEqual(gewaehlt["Hämoglobin"]["zuordnung"], "aehnlich")
        # 0,37 l/l → 37 %
        self.assertEqual((gewaehlt["Hämatokrit"]["wert"], gewaehlt["Hämatokrit"]["referenz_von"]), ("37", "36"))
        # Pfeile: „!27.7“, „188“ und „118.69“ mit herausragender „1“
        self.assertEqual((gewaehlt["MCH"]["wert"], gewaehlt["MCH"]["markierung"]), ("27.7", "↓"))
        self.assertEqual((gewaehlt["GFR (CKD-EPI)"]["wert"], gewaehlt["GFR (CKD-EPI)"]["markierung"]), ("88", "↓"))
        self.assertEqual((gewaehlt["CRP"]["wert"], gewaehlt["CRP"]["markierung"]), ("18.69", "↑"))
        self.assertTrue(any("Pfeil" in h for h in gewaehlt["CRP"]["hinweise"]))
        self.assertEqual(gewaehlt["Kalium"]["einheit_gelesen"], "mmol1")
        # Eisen steht zweimal im Befund: vorgewählt ist die Zeile, die schon in der Einheit des Katalogs steht
        self.assertEqual(gewaehlt["Eisen"]["wert"], "60.3")
        self.assertEqual(len([w for w in werte if w["parameter_name"] == "Eisen"]), 2)

    def test_vorwert_mit_datum_und_pfeile_als_eigenes_wort(self):
        """Spalte „Vorwert“ mit Datum („7,9 (19.11.24)“) macht aus der Zeile keine Kopfzeile – der Befund gilt als
        Labor. Pfeile als eigenes Wort („|“, „1“ vor dem Wert), „G/l“ als „GA“ gelesen."""
        katalog = KATALOG_BEISPIEL + [
            {"id": 30, "name": "Leukozyten", "kurzname": "", "einheit": "/nl", "gruppe": "", "suchbegriffe": ""},
            {"id": 31, "name": "Erythrozyten", "kurzname": "", "einheit": "/pl", "gruppe": "", "suchbegriffe": ""},
            {"id": 32, "name": "Thrombozyten", "kurzname": "", "einheit": "/nl", "gruppe": "", "suchbegriffe": ""},
        ]
        a = auswertung.auswerten([_seite(
            "Kostenträger Kasse Endbefund 30.01.2025", "Eingang 19.11.2024 08:54",
            "Leukozyten 1 9,7 GA 4,0 - 9,0 7,9 (19.11.24)", "Erythrozyten | 3,6 TA 3,9 - 5,3 3,9 (19.11.24)",
            "Thrombozyten 353 GA 150 - 400 390 (19.11.24)", "Natrium 144 mmol/4 136 - 145 145 (05.09.24)",
            "Kalium - Plasma 4,6 mmol4 3,4 - 5,1 4,6 (05.09.24)", "Albumin i.S. (phot.) 45,8 g/ 35,0 - 52,0 45,6 (19.11.24)",
            "Kalium 1 3,5 - 5,1")], katalog)
        self.assertIn("labor", a["arten"])
        werte = [w for w in a["labor"]["werte"] if w["vorschlag"]]
        w = {x["parameter_name"]: x for x in werte}
        self.assertEqual((w["Leukozyten"]["wert"], w["Leukozyten"]["markierung"], w["Leukozyten"]["einheit_gelesen"]),
                         ("9.7", "↑", "GA"))
        self.assertEqual((w["Erythrozyten"]["wert"], w["Erythrozyten"]["markierung"]), ("3.6", "↓"))
        self.assertFalse(any("Pfeil" in h for h in w["Erythrozyten"]["hinweise"]))
        self.assertEqual(w["Natrium"]["referenz_bis"], "145")
        self.assertEqual(w["Kalium"]["wert"], "4.6")  # die erste Kalium-Zeile; „Kalium 1 3,5 - 5,1“ bleibt Wert 1
        self.assertEqual([x["wert"] for x in a["labor"]["werte"] if x["parameter_name"] == "Kalium"], ["4.6", "1"])
        self.assertEqual(w["Albumin"]["wert"], "45.8")

    def test_ausstehend_erlaeuterung_und_referenz_an_der_einheit(self):
        """„folgt“ wird nicht vorgewählt; „Vitamin D-Mangel: < 50“ (Beurteilungsstufe) ist kein Wert;
        „ml/min/1.73qm> 60“: das Zeichen des Referenzbereichs klebt an der Einheit."""
        katalog = KATALOG_BEISPIEL + [
            {"id": 40, "name": "Vitamin D", "kurzname": "", "einheit": "µg/l", "gruppe": "", "suchbegriffe": ""},
            {"id": 41, "name": "GFR (CKD-EPI)", "kurzname": "", "einheit": "ml/min/1,73 m²", "gruppe": "",
             "suchbegriffe": ""}]
        a = auswertung.auswerten([_seite("Zink (ICP-MS) folgt", "Vitamin D-Mangel: < 50",
                                         "GFR (rechn. nach CKD-EPI) 85 ml/min/1.73qm> 60 85 (07.03.23)",
                                         "Natrium 143 mmol/l 133-150", "Kalium (Plasma) 4.0 mmol/l 3.4-5.1")], katalog)
        werte = {w["parameter_name"]: w for w in a["labor"]["werte"]}
        self.assertFalse(werte["Zink"]["vorschlag"])
        self.assertNotIn("Vitamin D", werte)
        gfr = werte["GFR (CKD-EPI)"]
        self.assertEqual((gfr["wert"], gfr["referenz_von"], gfr["einheit"]), ("85", "60", "ml/min/1,73 m²"))

    def test_eins_ohne_pfeil_bleibt(self):
        """Eine „1“ in der Wertespalte ist kein Pfeil: Thrombozyten 195, Leukozyten 11,2 bleiben."""
        katalog = KATALOG_BEISPIEL + [
            {"id": 30, "name": "Thrombozyten", "kurzname": "", "einheit": "/nl", "gruppe": "", "suchbegriffe": ""}]
        a = auswertung.auswerten([_seite("Thrombozyten 195 G/l 140 - 360", "Natrium 138 mmol/l",
                                         "Kalium 4,1 mmol/l", "Albumin 40 g/l", "Zink 101 µg/l")], katalog)
        werte = {w["parameter_name"]: w for w in a["labor"]["werte"]}
        self.assertEqual(werte["Thrombozyten"]["wert"], "195")
        self.assertEqual(werte["Zink"]["wert"], "101")

    def test_bia(self):
        seite = _seite("Bioelektrische Impedanzanalyse", "Datum der Messung: 20.09.2026",
                       "Körpergewicht 58,4 kg", "BMI 21,2 kg/m?", "Körperwasser (TBW) 29,81",
                       "ECW 47,5 %", "Fettmasse 17,2 kg", "BCM 18,9 kg", "Phasenwinkel 4,1 °")
        a = auswertung.auswerten([seite], KATALOG_BEISPIEL)
        self.assertIn("bia", a["arten"])
        self.assertEqual(a["datum"], "2026-09-20")
        w = a["bia"]["werte"]
        self.assertEqual(w["gewicht_kg"]["wert"], "58.4")
        self.assertEqual(w["bmi"]["wert"], "21.2")
        # „29,8 l“ als „29,81“ gelesen
        self.assertEqual(w["koerperwasser_l"]["wert"], "29.8")
        self.assertTrue(w["koerperwasser_l"]["hinweise"])
        self.assertEqual(w["ecw_prozent"]["wert"], "47.5")
        self.assertEqual(w["fettmasse_kg"]["wert"], "17.2")
        self.assertEqual(w["bcm_kg"]["wert"], "18.9")
        self.assertEqual(a["bia"]["weitere"][0]["name"], "Phasenwinkel")

    def test_bia_andere_geraete(self):
        """Englisches Protokoll (InBody-Art): ECW/TBW als Verhältnis, Muskelmasse unter „weitere“."""
        seite = _seite("Body Composition Analysis 12.09.2026", "Weight 72,3 kg", "Total Body Water 38,1 L",
                       "ECW/TBW 0,385", "Body Fat Mass 21,0 kg", "Skeletal Muscle Mass 28,4 kg", "Phase Angle 5,2 °")
        a = auswertung.auswerten([seite], KATALOG_BEISPIEL)
        self.assertIn("bia", a["arten"])
        w = a["bia"]["werte"]
        self.assertEqual(w["gewicht_kg"]["wert"], "72.3")
        self.assertEqual(w["koerperwasser_l"]["wert"], "38.1")
        self.assertEqual(w["fettmasse_kg"]["wert"], "21")
        self.assertEqual(w["ecw_prozent"]["wert"], "38.5")
        self.assertTrue(w["ecw_prozent"]["hinweise"])
        self.assertEqual({x["name"] for x in a["bia"]["weitere"]}, {"Skelettmuskelmasse", "Phasenwinkel"})

    def test_arztbrief(self):
        seite = _seite("Klinikum Beispielstadt", "Beispielstadt, den 15.08.2026", "Sehr geehrte Frau Kollegin,",
                       "wir berichten über Erika Muster, geb. 14.03.1961.", "Diagnosen:",
                       "- Kurzdarmsyndrom nach Dünndarmresektion (K91.2 G)", "- V.a. Vitamin-D-Mangel (E55.9)",
                       "- Z.n. Cholezystektomie (Z90.4)", "Vitamin B12 niedrig", "Therapie:",
                       "Parenterale Ernährung an 5 Tagen.", "Mit freundlichen Grüßen")
        a = auswertung.auswerten([seite], KATALOG_BEISPIEL)
        self.assertIn("arztbrief", a["arten"])
        self.assertEqual(a["datum"], "2026-08-15")
        d = {x["icd_code"]: x for x in a["diagnosen"]}
        self.assertEqual(set(d), {"K91.2", "E55.9", "Z90.4"})  # „Vitamin B12“ ist kein ICD-Code
        self.assertEqual(d["K91.2"]["kennzeichen"], "G")
        self.assertEqual(d["E55.9"]["kennzeichen"], "V")
        self.assertEqual(d["Z90.4"]["kennzeichen"], "Z")
        self.assertTrue(d["K91.2"]["bezeichnung"].startswith("Kurzdarmsyndrom"))
        self.assertIn("Parenterale", a["abschnitte"]["therapie"])
        self.assertEqual(a["patient"]["geburtsdaten"], ["1961-03-14"])

    def test_tesseract_zeile_uebereinander_wird_geteilt(self):
        """Fasst Tesseract übereinander stehende Wörter zu einer Zeile zusammen, werden daraus wieder Zeilen;
        unsichere Riesenwörter über mehrere Zeilen entfallen."""
        from .ocr.tesseract import TWort
        woerter = [TWort("Eisen", 100, 466, 90, 30, 0.9, (4, 1, 1)), TWort("10.8", 700, 466, 40, 30, 0.9, (4, 1, 1)),
                   TWort("Kalium", 100, 537, 110, 30, 0.9, (4, 1, 1)), TWort("3.67", 700, 537, 40, 30, 0.9, (4, 1, 1)),
                   TWort("Natrium", 100, 600, 110, 30, 0.9, (4, 2, 1)),
                   TWort("En", 100, 291, 300, 245, 0.08, (4, 3, 1))]
        stuecke = fusion.tesseract_stuecke(woerter)
        texte = sorted(s.text for s in stuecke)
        self.assertEqual(texte, ["10.8", "3.67", "Eisen", "Kalium", "Natrium"])

    def test_datum_und_alter_getrennt(self):
        """„26.11.1970 ♀ 54 Jahre“ als „26.11.197054 Jahre“ gelesen → Datum und Alter wieder getrennt."""
        W = fusion.Wort
        aus = fusion.datum_und_alter_trennen([W("geb.", 0, 0, 40, 20, 0.9), W("26.11.197054", 50, 0, 120, 20, 0.9),
                                              W("Jahre", 180, 0, 50, 20, 0.9)])
        self.assertEqual([w.t for w in aus], ["geb.", "26.11.1970", "54", "Jahre"])
        # ohne „Jahre“ dahinter bleibt das Wort, wie es ist
        self.assertEqual([w.t for w in fusion.datum_und_alter_trennen([W("26.11.197054", 0, 0, 120, 20, 0.9)])],
                         ["26.11.197054"])
        d = fusion.seite_json([fusion.Stueck(aus, "p").rahmen()], 1000, 1000, ["paddle"])
        a = auswertung.patient_hinweise(auswertung.reihen_aus([d]))
        self.assertEqual(a["geburtsdaten"], ["1970-11-26"])

    def test_vergleich_zweier_lesarten(self):
        """Übereinstimmung macht sicher; Abweichung bleibt markiert und nennt die andere Lesart."""
        W = fusion.Wort
        a = [W("Natrium", 0, 0, 70, 20, 0.9), W("138", 80, 0, 30, 20, 0.9), W("mmol/l", 120, 0, 60, 20, 0.6)]
        b = [W("Natrium", 0, 0, 70, 20, 0.85), W("138", 80, 0, 30, 20, 0.95), W("mmol/I", 120, 0, 60, 20, 0.7)]
        aus = fusion.vergleiche(a, b)
        self.assertGreater(aus[0].c, 0.9)
        self.assertGreater(aus[1].c, 0.95)
        self.assertLess(aus[2].c, fusion.UNSICHER)
        self.assertIn(aus[2].alt, ("mmol/l", "mmol/I"))


class LadenTest(SimpleTestCase):
    def test_formate(self):
        img = testbilder.seite(testbilder.LABOR)
        mime, seiten = laden.seiten_laden(testbilder.png(img, verkleinern=0.5))
        self.assertEqual((mime, len(seiten)), ("image/png", 1))
        mime, seiten = laden.seiten_laden(testbilder.pdf(img, testbilder.seite(testbilder.BRIEF)))
        self.assertEqual((mime, len(seiten)), ("application/pdf", 2))
        self.assertIsNone(seiten[0].digital)  # Bild-PDF ohne Textebene
        with self.assertRaises(laden.Unlesbar):
            laden.seiten_laden(b"PK\x03\x04 kein Bild")

    def test_pdf_mit_textebene(self):
        from reportlab.pdfgen import canvas

        puffer = io.BytesIO()
        c = canvas.Canvas(puffer)
        for i, z in enumerate(["Laborbefund vom 03.09.2026", "Natrium 138 mmol/l 135 - 145",
                               "Kalium 4,1 mmol/l 3,5 - 5,1", "Albumin 40 g/l 35 - 52"]):
            c.drawString(72, 760 - 20 * i, z)
        c.save()
        _, seiten = laden.seiten_laden(puffer.getvalue())
        self.assertTrue(seiten[0].digital)
        _, ergebnis = seite_erkennen(seiten[0], {})
        self.assertEqual(ergebnis["verfahren"], ["textebene"])
        text = fusion.text_aus_json(ergebnis)
        self.assertIn("Natrium", text)
        self.assertIn("138 mmol/l", text)


# ======================================================================= Erkennung (Tesseract, PP-OCR)
class ErkennungTest(SimpleTestCase):
    def test_verfahren_bereit(self):
        stand = verfahren_stand()
        self.assertTrue(stand["tesseract"]["bereit"], stand)
        if os.environ.get("EPM_OCR_PADDLE_PFLICHT") == "1":
            self.assertTrue(stand["paddle"]["bereit"], stand)
            self.assertTrue(stand["paddle"]["glaetten"], stand)

    def test_foto_eines_laborbefunds(self):
        """Schräg fotografiert, mit Schatten und Rauschen: Blatt wird gefunden, entzerrt und gelesen."""
        from .ocr.paddle import Paddle

        roh = testbilder.foto(testbilder.seite(testbilder.LABOR), seed=3)
        _, seiten = laden.seiten_laden(roh)
        auf, ergebnis = seite_erkennen(seiten[0], {}, paddle=Paddle.laden())
        self.assertEqual(auf.info.get("ecken_quelle"), "auto")
        text = fusion.text_aus_json(ergebnis)
        for wort in ("Laborbefund", "Natrium", "Kalium", "Magnesium", "Kreatinin", "Albumin", "Hypokaliämie"):
            self.assertIn(wort, text)
        a = auswertung.auswerten([ergebnis], KATALOG_BEISPIEL)
        werte = {w["parameter_name"]: w for w in a["labor"]["werte"] if w["parameter_name"]}
        self.assertEqual(werte["Natrium"]["wert"], "138")
        self.assertEqual(werte["Kalium"]["wert"], "3.2")
        self.assertEqual(werte["Albumin"]["wert"], "34")
        self.assertEqual(a["datum"], "2026-09-01")
        if os.environ.get("EPM_OCR_PADDLE_PFLICHT") == "1":
            self.assertIn("paddle", ergebnis["verfahren"])

    def test_gedrehter_scan(self):
        """Auf dem Kopf eingescannt und leicht schief: Ausrichtung und Schräglage werden korrigiert."""
        img = testbilder.seite(testbilder.BRIEF).rotate(181.5, expand=True, fillcolor="white")
        _, seiten = laden.seiten_laden(testbilder.png(img, dpi=200, verkleinern=0.67))
        auf, ergebnis = seite_erkennen(seiten[0], {})
        self.assertEqual(auf.info.get("drehung"), 180)
        text = fusion.text_aus_json(ergebnis)
        self.assertIn("Kurzdarmsyndrom", text)
        self.assertIn("K91.2", text)

    def test_durchsuchbare_pdf(self):
        import pypdfium2 as pdfium

        from .ocr import pdf

        _, seiten = laden.seiten_laden(testbilder.png(testbilder.seite(testbilder.BIA), verkleinern=0.67))
        auf, ergebnis = seite_erkennen(seiten[0], {})
        daten = pdf.erstellen([(auf.bild, ergebnis)], "BIA")
        doc = pdfium.PdfDocument(daten)
        text = doc[0].get_textpage().get_text_range()
        self.assertIn("Phasenwinkel", text)
        self.assertIn("Körpergewicht", text)


# ======================================================================= API, Dienst, Rechte
@override_settings(EPM_SCANS=SCANS)
class ScansApiTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.testpatient = Patient.objects.create(nachname="Muster", vorname="Erika", ist_test=True,
                                                 geburtsdatum="1961-03-14")
        cls.testzugang = benutzer("tessa", Rolle.MITARBEITER, ist_test=True)

    def hochladen(self, inhalt: bytes, name="befund.png", client=None):
        c = client or client_fuer(self.mitarbeiter)
        r = c.post("/api/scans/", {"dateien": [SimpleUploadedFile(name, inhalt)]}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def erkennen(self):
        """Wie der OCR-Dienst: alle wartenden Aufträge abarbeiten."""
        from .ocr.paddle import Paddle

        paddle = Paddle.laden()
        while (scan := dienst.auftrag_holen()) is not None:
            dienst.bearbeiten(scan, paddle)

    def labor_png(self, **namen):
        return testbilder.png(testbilder.seite(testbilder.LABOR, **namen), verkleinern=0.67)

    def test_ablauf_hochladen_erkennen_zuordnen_mit_werten(self):
        c = client_fuer(self.mitarbeiter)
        scan = self.hochladen(self.labor_png(), "Labor Muster.png")
        self.assertEqual(scan["status"], "wartet")
        self.assertEqual(scan["titel"], "Labor Muster")
        self.erkennen()
        r = c.get(f"/api/scans/{scan['id']}/")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d["status"], "fertig", d.get("fehler"))
        self.assertEqual(d["seiten_anzahl"], 1)
        self.assertIn("Kalium", d["text"])
        self.assertIn("labor", d["auswertung"]["arten"])
        self.assertNotIn("patient", d["auswertung"])  # Hinweise bleiben im Server
        # Vorschlag: Name und Geburtsdatum stehen im Dokument
        self.assertEqual([v["id"] for v in d["vorschlaege"]], [self.testpatient.id])
        # Bilder der Seite
        seite = d["seiten"][0]
        for art in ("bild", "klein", "roh"):
            b = c.get(f"/api/scans/{scan['id']}/seiten/{seite['id']}/bild/?art={art}")
            self.assertEqual(b.status_code, 200, art)
        # Zuordnungsprüfung: passt zu Erika Muster, nicht zu Anna Echt
        self.assertEqual(c.get(f"/api/scans/{scan['id']}/pruefen/?patient={self.testpatient.id}").json()["hinweise"],
                         [])
        self.assertTrue(c.get(f"/api/scans/{scan['id']}/pruefen/?patient={self.patient.id}").json()["hinweise"])
        # Zuordnen mit Werten aus der Prüfansicht
        werte = [w for w in d["auswertung"]["labor"]["werte"] if w["vorschlag"]]
        self.assertGreaterEqual(len(werte), 5)
        r = c.post(f"/api/scans/{scan['id']}/zuordnen/", {
            "patient": self.testpatient.id, "titel": "Laborbefund 01.09.2026", "datum": "2026-09-03",
            "labor": {"abgenommen_am": d["auswertung"]["datum"], "labor": d["auswertung"]["labor"]["name"],
                      "werte": [{"parameter": w["parameter"], "wert": w["wert"], "einheit": w["einheit"],
                                 "referenz_von": w["referenz_von"], "referenz_bis": w["referenz_bis"]}
                                for w in werte]},
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        e = r.json()
        dok = Dokument.objects.get(pk=e["dokument"])
        self.assertEqual(dok.patient, self.testpatient)
        self.assertEqual(dok.herkunft, Dokument.Herkunft.SCAN)
        self.assertEqual(dok.mime, "application/pdf")
        self.assertTrue(dok.pfad.is_file())
        self.assertIn("Kalium", DokumentText.objects.get(dokument=dok).text)
        befund = Laborbefund.objects.get(pk=e["laborbefund"])
        self.assertEqual(befund.dokument, dok)
        self.assertEqual(str(befund.abgenommen_am), "2026-09-01")
        kalium = befund.werte.get(parameter__name="Kalium")
        self.assertEqual(kalium.wert, Decimal("3.2"))
        albumin = befund.werte.get(parameter__name="Albumin")
        self.assertEqual((albumin.wert, albumin.einheit), (Decimal("34"), "g/l"))
        # Scan ist aus „Scans“ verschwunden, Dateien mit
        self.assertFalse(Scan.objects.filter(pk=scan["id"]).exists())
        self.assertEqual(c.get(f"/api/scans/{scan['id']}/").status_code, 400)
        # Dokument ist über den erkannten Text auffindbar
        r = c.get(f"/api/dokumente/?patient={self.testpatient.id}&search=Hypokali")
        self.assertEqual([x["id"] for x in r.json()["results"]], [dok.id])
        self.assertTrue(r.json()["results"][0]["hat_text"])
        self.assertIn("Kalium", c.get(f"/api/dokumente/{dok.id}/text/").json()["text"])
        # Audit-Log: hochgeladen (ohne Titel), zugeordnet (mit Akte)
        ereignisse = SystemEreignis.objects.filter(art=SystemEreignis.Art.SCAN).order_by("id")
        self.assertEqual([x.details["aktion"] for x in ereignisse], ["hochgeladen", "zugeordnet"])
        self.assertNotIn("titel", ereignisse[0].details)
        self.assertEqual(ereignisse[1].details["patient_id"], self.testpatient.id)

    def test_bia_und_arztbrief_zuordnen(self):
        c = client_fuer(self.mediziner)
        bild = testbilder.pdf(testbilder.seite(testbilder.BIA), testbilder.seite(testbilder.BRIEF))
        scan = self.hochladen(bild, "Unterlagen.pdf", client=c)
        self.erkennen()
        d = c.get(f"/api/scans/{scan['id']}/").json()
        self.assertEqual(d["status"], "fertig", d.get("fehler"))
        self.assertEqual(d["seiten_anzahl"], 2)
        self.assertIn("bia", d["auswertung"]["arten"])
        self.assertIn("arztbrief", d["auswertung"]["arten"])
        bia = {k: v["wert"] for k, v in d["auswertung"]["bia"]["werte"].items()}
        self.assertEqual(bia.get("gewicht_kg"), "58.4")
        diagnosen = d["auswertung"]["diagnosen"]
        self.assertEqual({x["icd_code"] for x in diagnosen}, {"K91.2", "E55.9"})
        r = c.post(f"/api/scans/{scan['id']}/zuordnen/", {
            "patient": self.testpatient.id,
            "bia": {"gemessen_am": "2026-09-20", **bia, "gewicht_uebernehmen": True},
            "diagnosen": [{"bezeichnung": x["bezeichnung"], "icd_code": x["icd_code"],
                           "kennzeichen": x["kennzeichen"]} for x in diagnosen],
            "texte": {"therapie": d["auswertung"]["abschnitte"]["therapie"]},
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        m = BiaMessung.objects.get(pk=r.json()["bia"])
        self.assertEqual(m.gewicht_kg, Decimal("58.4"))
        self.assertTrue(Gewichtsmessung.objects.filter(patient=self.testpatient, gewicht_kg=Decimal("58.4")).exists())
        self.assertEqual(Diagnose.objects.filter(patient=self.testpatient).count(), 2)
        self.testpatient.refresh_from_db()
        self.assertIn("Parenterale", self.testpatient.therapie)
        self.assertIn("(Scan)", self.testpatient.therapie)

    def test_fehler_beim_zuordnen_legt_nichts_an(self):
        c = client_fuer(self.mitarbeiter)
        scan = self.hochladen(self.labor_png())
        self.erkennen()
        r = c.post(f"/api/scans/{scan['id']}/zuordnen/", {
            "patient": self.testpatient.id,
            "labor": {"abgenommen_am": "2026-09-01", "werte": [{"parameter": None, "freitext_name": "", "wert": "1"}]},
        }, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("labor", r.json())
        self.assertFalse(Dokument.objects.filter(patient=self.testpatient).exists())
        self.assertTrue(Scan.objects.filter(pk=scan["id"]).exists())
        # Mitarbeiter dürfen keine Diagnosen eintragen? Doch – „Akten bearbeiten“ haben sie (Standard)
        # Betrachter sehen „Scans“ gar nicht
        self.assertEqual(client_fuer(self.betrachter).get("/api/scans/").status_code, 403)

    def test_admin_nur_testpatienten_testzugang_nur_eigene(self):
        scan = self.hochladen(self.labor_png(nachname="Echt", vorname="Anna"), client=client_fuer(self.admin))
        self.erkennen()
        r = client_fuer(self.admin).post(f"/api/scans/{scan['id']}/zuordnen/", {"patient": self.patient.id},
                                         format="json")
        self.assertEqual(r.status_code, 403, r.content)
        # Testzugang sieht den Scan des Admins nicht; sein eigener ist nur Testpatienten zuzuordnen
        t = client_fuer(self.testzugang)
        self.assertEqual(t.get("/api/scans/").json(), [])
        eigener = self.hochladen(self.labor_png(), client=t)
        self.assertTrue(Scan.objects.get(pk=eigener["id"]).ist_test)
        self.assertEqual([s["id"] for s in t.get("/api/scans/").json()], [eigener["id"]])

    def test_aufbewahrung_verlaengern_und_bereinigen(self):
        e = Einstellungen.aktuell()
        e.scans_frist_tage, e.scans_hoechst_tage, e.scans_verlaengerung_tage = 7, 10, 7
        e.save()
        c = client_fuer(self.mitarbeiter)
        scan = self.hochladen(self.labor_png())
        obj = Scan.objects.get(pk=scan["id"])
        self.assertAlmostEqual((obj.laeuft_ab_am - obj.hochgeladen_am).total_seconds(), 7 * 86400, delta=60)
        r = c.post(f"/api/scans/{scan['id']}/verlaengern/")
        self.assertEqual(r.status_code, 200, r.content)
        obj.refresh_from_db()
        # nie über die Höchstdauer ab dem Hochladen
        self.assertAlmostEqual((obj.laeuft_ab_am - obj.hochgeladen_am).total_seconds(), 10 * 86400, delta=60)
        self.assertFalse(r.json()["verlaengerbar"])
        r = c.post(f"/api/scans/{scan['id']}/verlaengern/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Höchstdauer", r.json()["fehler"])
        # abgelaufen: verschwindet aus der Liste und wird mit Dateien gelöscht
        pfad = obj.pfad
        self.assertTrue(pfad.is_dir())
        Scan.objects.filter(pk=obj.pk).update(laeuft_ab_am=timezone.now() - timedelta(minutes=1))
        self.assertEqual(c.get("/api/scans/").json(), [])
        with self.captureOnCommitCallbacks(execute=True):
            ergebnis = dienst.bereinigen()
        self.assertEqual(ergebnis["abgelaufen"], 1)
        self.assertFalse(Scan.objects.filter(pk=obj.pk).exists())
        self.assertFalse(pfad.exists())
        self.assertTrue(SystemEreignis.objects.filter(art=SystemEreignis.Art.SCAN, details__aktion="abgelaufen").exists())

    def test_obergrenzen(self):
        e = Einstellungen.aktuell()
        e.scans_max_anzahl = 10
        e.save()
        for _ in range(10):
            Scan.objects.create(titel="x", originalname="x", mime="image/png", groesse=1, sha256="0",
                                ordner=os.urandom(8).hex(), laeuft_ab_am=timezone.now() + timedelta(days=1))
        r = client_fuer(self.mitarbeiter).post("/api/scans/", {"dateien": [SimpleUploadedFile("a.png", self.labor_png())]},
                                               format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Obergrenze", r.json()["datei"])
        stand = client_fuer(self.mitarbeiter).get("/api/scans/stand/").json()
        self.assertEqual(stand["anzahl_alle"], 10)

    def test_einstellungen_pruefen(self):
        c = client_fuer(self.mitarbeiter)
        r = c.patch("/api/einstellungen/", {"scans_frist_tage": 20, "scans_hoechst_tage": 10}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("scans_hoechst_tage", r.json())
        r = c.patch("/api/einstellungen/", {"ocr_fachwoerter": "Teduglutid\nNatrovit\nzwei Wörter"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = c.patch("/api/einstellungen/", {"scans_frist_tage": 14, "scans_hoechst_tage": 60,
                                            "ocr_fachwoerter": "Teduglutid\nNatrovit\nTeduglutid"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["ocr_fachwoerter"], "Teduglutid\nNatrovit")

    def test_seiten_bearbeiten_aufteilen_zusammenfuehren(self):
        c = client_fuer(self.mitarbeiter)
        bilder = [testbilder.seite(testbilder.LABOR), testbilder.seite(testbilder.BRIEF),
                  testbilder.seite(testbilder.BIA)]
        scan = self.hochladen(testbilder.pdf(*bilder, dpi=150), "Stapel.pdf")
        self.erkennen()
        d = c.get(f"/api/scans/{scan['id']}/").json()
        self.assertEqual(d["seiten_anzahl"], 3)
        ids = [s["id"] for s in d["seiten"]]
        # Reihenfolge ändern
        r = c.post(f"/api/scans/{scan['id']}/reihenfolge/", {"seiten": [ids[2], ids[0], ids[1]]}, format="json")
        self.assertEqual([s["id"] for s in r.json()["seiten"]], [ids[2], ids[0], ids[1]])
        # Einstellungen einer Seite: neu aufbereiten und erkennen (Drehung von Hand)
        r = c.patch(f"/api/scans/{scan['id']}/seiten/{ids[0]}/", {"einstellungen": {"drehung": 0, "modus": "sw"}},
                    format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["status"], "wartet")
        # während der Erkennung gesperrt
        Scan.objects.filter(pk=scan["id"]).update(status=Scan.Status.LAEUFT)
        self.assertEqual(c.post(f"/api/scans/{scan['id']}/reihenfolge/", {"seiten": ids}, format="json").status_code,
                         409)
        Scan.objects.filter(pk=scan["id"]).update(status=Scan.Status.WARTET)
        self.erkennen()
        seite = ScanSeite.objects.get(pk=ids[0])
        self.assertEqual(seite.status, "fertig")
        self.assertEqual(seite.einstellungen["modus"], "sw")
        self.assertTrue(seite.bild.endswith(".png"))
        # Bereich neu erkennen
        r = c.post(f"/api/scans/{scan['id']}/seiten/{ids[0]}/bereich/", {"box": [0, 0, 1, 0.3], "staerke": 10},
                   format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.erkennen()
        seite.refresh_from_db()
        self.assertEqual(seite.ergebnis.get("bereiche"), [[0, 0, 1, 0.3]])
        self.assertIn("Laborbefund", seite.text)
        # aufteilen: ab der dritten Seite (BIA, nach der Umsortierung die erste … hier: Brief)
        r = c.post(f"/api/scans/{scan['id']}/aufteilen/", {"ab": ids[1]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        neu = r.json()["neu"]
        self.assertEqual(r.json()["scan"]["seiten_anzahl"], 2)
        self.assertEqual(c.get(f"/api/scans/{neu}/").json()["seiten_anzahl"], 1)
        bild = c.get(f"/api/scans/{neu}/seiten/{ids[1]}/bild/?art=bild")
        self.assertEqual(bild.status_code, 200)
        # wieder zusammenführen
        with self.captureOnCommitCallbacks(execute=True):
            r = c.post(f"/api/scans/{scan['id']}/zusammenfuehren/", {"mit": neu}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["seiten_anzahl"], 3)
        self.assertFalse(Scan.objects.filter(pk=neu).exists())
        # Seite entfernen
        r = c.delete(f"/api/scans/{scan['id']}/seiten/{ids[2]}/entfernen/")
        self.assertEqual(r.json()["seiten_anzahl"], 2)
        # PDF und Text herunterladen
        r = c.get(f"/api/scans/{scan['id']}/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))
        r = c.get(f"/api/scans/{scan['id']}/textdatei/")
        self.assertIn("Kurzdarmsyndrom", r.content.decode())
        # löschen
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(c.delete(f"/api/scans/{scan['id']}/").status_code, 204)
        self.assertFalse(Scan.objects.exists())

    def test_unlesbare_datei_und_erneut(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/scans/", {"dateien": [SimpleUploadedFile("x.docx", b"PK\x03\x04abc")]}, format="multipart")
        self.assertEqual(r.status_code, 400)
        # beschädigtes PNG: Kopf stimmt, Inhalt nicht → Fehler beim Erkennen, „erneut“ möglich
        scan = self.hochladen(b"\x89PNG\r\n\x1a\n" + b"kaputt" * 10, "kaputt.png")
        self.erkennen()
        d = c.get(f"/api/scans/{scan['id']}/").json()
        self.assertEqual(d["status"], "fehler")
        self.assertIn("Bild", d["fehler"])
        r = c.post(f"/api/scans/{scan['id']}/erneut/")
        self.assertEqual(r.json()["status"], "wartet")

    # ---------------------------------------------------------------- Absturzschutz (09.10.2026)
    def _zwei_seiten(self):
        """Scan mit zwei Seiten, Seiten angelegt, aber noch nicht erkannt."""
        inhalt = testbilder.pdf(testbilder.seite(testbilder.LABOR), testbilder.seite(testbilder.LABOR))
        scan = Scan.objects.get(pk=self.hochladen(inhalt, "zwei.pdf")["id"])
        dienst.seiten_anlegen(scan)
        return scan

    def test_abgebrochener_dienst_seite_wird_sparsam_wiederholt(self):
        """Der Dienst stirbt mitten in Seite 2 (Speichergrenze): Nach 90 s ohne Lebenszeichen ist der Scan wieder in
        der Warteschlange, Seite 1 bleibt erkannt, Seite 2 wird in Sparstufe 1 erkannt."""
        scan = self._zwei_seiten()
        s1, s2 = scan.seiten.order_by("nr")
        # Seite 1 schon fertig, Seite 2 begonnen – dann Absturz
        geholt = dienst.auftrag_holen()
        self.assertEqual(geholt.pk, scan.pk)
        dienst.seite_erkennen(s1, None, None)
        ScanSeite.objects.filter(pk=s2.pk).update(begonnen_am=timezone.now())
        # frisches Lebenszeichen: noch nicht zurücksetzen
        self.assertEqual(dienst.haengende_zuruecksetzen(), 0)
        Scan.objects.filter(pk=scan.pk).update(lebenszeichen=timezone.now() - timedelta(seconds=120))
        self.assertEqual(dienst.haengende_zuruecksetzen(), 1)
        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.WARTET)
        self.erkennen()
        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.FERTIG, scan.fehler)
        s1.refresh_from_db(); s2.refresh_from_db()
        self.assertEqual(s1.status, ScanSeite.Status.FERTIG)
        self.assertNotIn("sparstufe", s1.info)
        self.assertEqual(s2.status, ScanSeite.Status.FERTIG)
        self.assertEqual(s2.info.get("sparstufe"), 1)
        self.assertEqual((s2.abbrueche, s2.begonnen_am), (0, None))
        self.assertIn("Kalium", s2.text)
        self.assertEqual(dienst.stand()["abbrueche"], 1)
        self.assertEqual(scan.versuche, 0)

    def test_dritter_abbruch_markiert_nur_die_seite(self):
        scan = self._zwei_seiten()
        s1, s2 = scan.seiten.order_by("nr")
        ScanSeite.objects.filter(pk=s2.pk).update(begonnen_am=timezone.now(), abbrueche=2)
        self.erkennen()
        scan.refresh_from_db(); s1.refresh_from_db(); s2.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.FERTIG)
        self.assertEqual(s1.status, ScanSeite.Status.FERTIG)
        self.assertEqual(s2.status, ScanSeite.Status.FEHLER)
        self.assertIn("3-mal abgebrochen", s2.fehler)
        self.assertIsNone(s2.begonnen_am)

    def test_sparstufe_2_nur_tesseract(self):
        roh = laden.seiten_laden(self.labor_png(), 5)[1][0]
        _auf, daten = seite_erkennen(roh, {}, paddle=object(), stufe=2)  # PP-OCR wird gar nicht angefasst
        self.assertEqual(daten["verfahren"], ["tesseract"])
        schritte = []
        auf, _d = seite_erkennen(roh, {}, stufe=1, schritt=schritte.append)
        self.assertEqual(auf.info["sparstufe"], 1)
        self.assertIn("Tesseract liest", schritte)
        self.assertEqual(schritte[0], "Blatt suchen und entzerren")

    def test_zu_viele_abbrueche_ohne_fortschritt(self):
        scan = self._zwei_seiten()
        Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.LAEUFT, versuche=dienst.MAX_VERSUCHE,
                                               lebenszeichen=timezone.now() - timedelta(minutes=5))
        dienst.haengende_zuruecksetzen()
        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.FEHLER)
        self.assertIn("mehrfach abgebrochen", scan.fehler)

    def test_geplantes_beenden_zaehlt_nicht_als_abbruch(self):
        scan = self._zwei_seiten()
        geholt = dienst.auftrag_holen()
        s2 = scan.seiten.order_by("nr").last()
        ScanSeite.objects.filter(pk=s2.pk).update(begonnen_am=timezone.now())
        dienst.geplant_beendet(geholt)
        scan.refresh_from_db(); s2.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.WARTET)
        self.assertEqual(scan.versuche, 0)
        self.assertIsNone(s2.begonnen_am)
        self.erkennen()
        s2.refresh_from_db()
        self.assertNotIn("sparstufe", s2.info)

    def test_herzschlag_schreibt_lebenszeichen(self):
        import time as zeit

        scan = self._zwei_seiten()
        geholt = dienst.auftrag_holen()
        alt = timezone.now() - timedelta(minutes=10)
        Scan.objects.filter(pk=scan.pk).update(lebenszeichen=alt)
        aufrufe = []
        # der Faden schlägt im Takt (eigene Verbindung – sieht die Testdaten der offenen Transaktion nicht) …
        with dienst.herzschlag(geholt, zusatz=lambda: aufrufe.append(1), takt=0.05):
            zeit.sleep(0.4)
        self.assertGreaterEqual(len(aufrufe), 3)
        # … und jeder Schlag schreibt das Lebenszeichen
        dienst.herzschlag(geholt).schlag()
        scan.refresh_from_db()
        self.assertGreater(scan.lebenszeichen, alt)
        self.assertEqual(dienst.haengende_zuruecksetzen(), 0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(SCANS, ignore_errors=True)
