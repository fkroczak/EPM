"""Erkennung verbessern (F189): „Falsch erkannt“ anmerken, richtigen Bereich markieren und nur ihn neu lesen,
Steuerung des Lernens (pausieren, Schwelle).

Der Bereich wird wirklich mit Tesseract gelesen (erfundener Laborbefund aus ``testbilder``); die übrigen Tests
arbeiten ohne Erkennung mit vorgegebenen Wörtern wie ``test_lernen``.
"""
import secrets
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import SkipTest

import cv2
import numpy as np
from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from accounts.models import Rolle
from audit.models import SystemEreignis
from epm.pruefhilfen import Grundlage, benutzer, client_fuer
from patienten.models import Patient
from stammdaten.models import Laborparameter

from . import dienst, lernen, testbilder
from .models import GelernteZuordnung, KorrekturZaehler, LernEinstellung, Scan, ScanSeite
from .ocr import auswertung
from .ocr.tesseract import verfuegbar
from .test_lernen import _param, _scan

SCANS = Path(tempfile.mkdtemp(prefix="epm-scans-verbessern-"))
# Laborbefund aus testbilder (A4, 300 dpi): Kopf oben, Tabelle ab etwa 18 % der Höhe; Kalium und Magnesium liegen
# zwischen 19 % und 22,5 % der Seitenhöhe
KALIUM_MAGNESIUM = [0.07, 0.190, 0.75, 0.034]


def _scan_mit_bild(user, *, ist_test=False) -> tuple[Scan, ScanSeite]:
    """Erkannter Scan, dessen Seite das Bild des Laborbefunds ist – ohne erkannte Reihen (wie eine schlecht gelesene
    Seite), damit nur der markierte Bereich Werte liefert."""
    ordner = secrets.token_hex(16)
    pfad = settings.EPM_SCANS / ordner
    pfad.mkdir(parents=True)
    grau = cv2.cvtColor(np.array(testbilder.seite(testbilder.LABOR)), cv2.COLOR_RGB2GRAY)
    cv2.imwrite(str(pfad / "grau.png"), grau)
    h, b = grau.shape
    scan = Scan.objects.create(titel="Befund", originalname="b.png", mime="image/png", groesse=1, sha256="0" * 64,
                               ordner=ordner, hochgeladen_von=user, ist_test=ist_test, status=Scan.Status.FERTIG,
                               laeuft_ab_am=timezone.now() + timedelta(days=7),
                               auswertung={"originale": [{"name": "b.png", "mime": "image/png"}]})
    seite = ScanSeite.objects.create(
        scan=scan, nr=1, roh="grau.png", bild="grau.png", grau="grau.png", breite=b, hoehe=h,
        status=ScanSeite.Status.FERTIG, text="Labor Dr. Beispiel & Kollegen – Medizinisches Versorgungszentrum",
        ergebnis={"breite": b, "hoehe": h, "reihen": [[{"q": "t", "w": [
            ["Labor", 220, 220, 130, 40, 0.95], ["Dr.", 360, 220, 60, 40, 0.95], ["Beispiel", 430, 220, 170, 40, 0.95],
            ["MVZ", 610, 220, 90, 40, 0.95]]}]]})
    dienst.auswerten(scan)
    scan.save()
    return scan, seite


@override_settings(EPM_SCANS=SCANS)
class BereichTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.testpatient = Patient.objects.create(nachname="Muster", vorname="Erika", ist_test=True,
                                                 geburtsdatum="1961-03-14")
        _param("Kalium", "mmol/l")
        _param("Magnesium", "mmol/l")

    def setUp(self):
        if not verfuegbar()[0]:
            raise SkipTest("Tesseract fehlt")

    def test_nur_den_bereich_lesen_tabelle_zeilenweise(self):
        scan, seite = _scan_mit_bild(self.mitarbeiter)
        self.assertEqual(scan.auswertung["labor"]["werte"], [])
        c = client_fuer(self.mitarbeiter)
        r = c.post(f"/api/scans/{scan.id}/seiten/{seite.id}/ausschnitt/", {"box": KALIUM_MAGNESIUM}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        werte = d["scan"]["auswertung"]["labor"]["werte"]
        neu = [werte[i] for i in d["neu"]]
        namen = {w["parameter_name"] for w in neu}
        self.assertEqual(namen, {"Kalium", "Magnesium"})     # Tabelle: jede Zeile ein Vorschlag
        kalium = next(w for w in neu if w["parameter_name"] == "Kalium")
        self.assertEqual(kalium["wert"], "3.2")
        self.assertEqual(kalium["bereich"], KALIUM_MAGNESIUM)
        self.assertTrue(kalium["hinweise"][0].startswith("aus dem markierten Bereich"))
        # Lage in Koordinaten der ganzen Seite, innerhalb des Rahmens
        x, y, b, h = kalium["box"]
        bx, by, bb, bh = KALIUM_MAGNESIUM
        self.assertTrue(bx - 0.01 <= x and x + b <= bx + bb + 0.01 and by - 0.01 <= y and y + h <= by + bh + 0.01,
                        kalium["box"])
        # bleibt erhalten, wenn der Scan neu ausgewertet wird
        dienst.auswerten(Scan.objects.get(pk=scan.pk))
        self.assertIn("zusatz", ScanSeite.objects.get(pk=seite.pk).info)

    def test_grenzen_und_rechte(self):
        scan, seite = _scan_mit_bild(self.mitarbeiter)
        c = client_fuer(self.mitarbeiter)
        url = f"/api/scans/{scan.id}/seiten/{seite.id}/ausschnitt/"
        for box in ([0.1, 0.1, 0.001, 0.001], [1.2, 0.1, 0.1, 0.1], [-0.1, 0.1, 0.2, 0.1], "x", [0.1, 0.2], None,
                    [0.1, 0.1, "nan", 0.1]):
            r = c.post(url, {"box": box}, format="json")
            self.assertEqual(r.status_code, 400, (box, r.content))
        # über den Rand hinaus wird begrenzt
        self.assertEqual(c.post(url, {"box": [0.9, 0.95, 0.5, 0.5]}, format="json").status_code, 200)
        self.assertEqual(client_fuer(self.betrachter).post(url, {"box": KALIUM_MAGNESIUM}, format="json").status_code,
                         403)
        # Scan eines anderen Testzugangs: nicht sichtbar
        tessa = benutzer("tessa", Rolle.MITARBEITER, ist_test=True)
        self.assertEqual(client_fuer(tessa).post(url, {"box": KALIUM_MAGNESIUM}, format="json").status_code, 400)
        # fremde Seite
        anderer, andere_seite = _scan_mit_bild(self.mitarbeiter)
        r = c.post(f"/api/scans/{scan.id}/seiten/{andere_seite.id}/ausschnitt/", {"box": KALIUM_MAGNESIUM},
                   format="json")
        self.assertEqual(r.status_code, 400)

    def test_bereich_wird_gelernt_und_beim_naechsten_befund_gelesen(self):
        LernEinstellung.objects.update_or_create(id=LernEinstellung.aktuell().id, defaults={"schwelle": 1})
        scan, seite = _scan_mit_bild(self.mitarbeiter)
        c = client_fuer(self.mitarbeiter)
        d = c.post(f"/api/scans/{scan.id}/seiten/{seite.id}/ausschnitt/", {"box": KALIUM_MAGNESIUM},
                   format="json").json()
        werte = d["scan"]["auswertung"]["labor"]["werte"]
        r = c.post(f"/api/scans/{scan.id}/zuordnen/", {
            "patient": self.testpatient.id, "titel": "Labor",
            "labor": {"abgenommen_am": "2026-09-01", "labor": werte[d["neu"][0]].get("labor", ""),
                      "werte": [{"parameter": werte[i]["parameter"], "wert": werte[i]["wert"],
                                 "einheit": werte[i]["einheit"]} for i in d["neu"]]},
            "herkunft": {"labor": [{"index": i} for i in d["neu"]]}}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        g = GelernteZuordnung.objects.get(art="bereich")
        self.assertEqual((g.quelle, g.bereich), ("labor dr beispiel mvz", KALIUM_MAGNESIUM))
        self.assertEqual(lernen.gelerntes().bereiche, {"labor dr beispiel mvz": [KALIUM_MAGNESIUM]})
        # nächster Befund desselben Labors: der OCR-Dienst liest den Bereich von sich aus nach
        scan2, seite2 = _scan_mit_bild(self.mitarbeiter)
        self.assertEqual(dienst.bereiche_nachlesen(scan2), 1)
        dienst.auswerten(scan2)
        namen = {w["parameter_name"] for w in scan2.auswertung["labor"]["werte"]}
        self.assertTrue({"Kalium", "Magnesium"} <= namen, namen)
        # ohne Inhalt: nur die Lage ist gespeichert
        self.assertFalse(GelernteZuordnung.objects.filter(art="bereich", erkannt__icontains="kalium").exists())


@override_settings(EPM_SCANS=SCANS)
class FalschTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.kreatinin = _param("Kreatinin")
        _param("Natrium", "mmol/l")

    ZEILEN = ("Labor Nord MVZ", "Patient: Muster, Erika  geb. 14.03.1961", "Natrium 138 mmol/l 135 - 145",
              "Kreatimin 1,1 mg/dl 0,5 - 0,9", "Referenzbereich 2 mg/dl", "Muster 35 mg/dl")

    def index(self, scan, erkannt):
        return next(i for i, w in enumerate(scan.auswertung["labor"]["werte"]) if w["erkannt_als"] == erkannt)

    def falsch(self, scan, index, grund, art="labor", user=None):
        r = client_fuer(user or self.mitarbeiter).post(f"/api/scans/{scan.id}/falsch/",
                                                       {"art": art, "index": index, "grund": grund}, format="json")
        return r

    def test_gehoert_nicht_dazu_wird_fuer_dieses_labor_ignoriert(self):
        scan = _scan(self.mitarbeiter, *self.ZEILEN)
        i = self.index(scan, "Referenzbereich")
        r = self.falsch(scan, i, "gehoert_nicht_dazu")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["gelernt"], "ignorieren")
        scan.refresh_from_db()
        self.assertEqual(scan.auswertung["labor"]["werte"][i]["verworfen"], "gehoert_nicht_dazu")
        g = GelernteZuordnung.objects.get(art="ignorieren")
        self.assertEqual((g.quelle, g.erkannt), ("labor nord mvz", "referenzbereich"))
        # nächster Befund dieses Labors: die Zeile kommt nicht mehr; bei einem anderen Labor schon
        scan2 = _scan(self.mitarbeiter, *self.ZEILEN)
        self.assertNotIn("Referenzbereich", [w["erkannt_als"] for w in scan2.auswertung["labor"]["werte"]])
        scan3 = _scan(self.mitarbeiter, "Labor Süd MVZ", *self.ZEILEN[1:])
        self.assertIn("Referenzbereich", [w["erkannt_als"] for w in scan3.auswertung["labor"]["werte"]])
        # gezählt, im Audit-Log ohne Inhalt
        self.assertEqual(KorrekturZaehler.objects.get(art="labor").verworfen, 1)
        e = SystemEreignis.objects.filter(details__aktion="falsch_angemerkt").get()
        self.assertEqual(e.details["grund"], "gehoert_nicht_dazu")
        self.assertNotIn("Referenzbereich", str(e.details))
        # verworfen bleibt verworfen, auch nach neuer Auswertung
        dienst.auswerten(scan)
        self.assertNotIn("Referenzbereich", [w["erkannt_als"] for w in scan.auswertung["labor"]["werte"]
                                              if not w.get("verworfen")])

    def test_falsche_zeile_sperrt_aehnliches_und_schwaecht_gelerntes(self):
        scan = _scan(self.mitarbeiter, *self.ZEILEN)
        i = self.index(scan, "Kreatimin")
        self.assertEqual(scan.auswertung["labor"]["werte"][i]["zuordnung"], "aehnlich")
        self.assertEqual(self.falsch(scan, i, "falsche_zeile").json()["gelernt"], "gesperrt")
        g = GelernteZuordnung.objects.get(art="labor", erkannt="kreatimin")
        self.assertTrue(g.gesperrt)
        self.assertEqual(g.quelle, "labor nord mvz")
        scan2 = _scan(self.mitarbeiter, *self.ZEILEN)
        self.assertIsNone(scan2.auswertung["labor"]["werte"][self.index(scan2, "Kreatimin")]["parameter"])
        # gelernte Zuordnung verliert eine Bestätigung
        GelernteZuordnung.objects.all().delete()
        GelernteZuordnung.objects.create(art="labor", quelle="", erkannt="kreatimin", ziel=str(self.kreatinin.id),
                                         bestaetigt=3, parameter=self.kreatinin)
        scan3 = _scan(self.mitarbeiter, *self.ZEILEN)
        i = self.index(scan3, "Kreatimin")
        self.assertEqual(scan3.auswertung["labor"]["werte"][i]["zuordnung"], "gelernt")
        self.assertEqual(self.falsch(scan3, i, "falsche_zeile").json()["gelernt"], "widersprochen")
        self.assertEqual(GelernteZuordnung.objects.get(erkannt="kreatimin").bestaetigt, 2)
        # falscher Wert: nichts gelernt, nur gezählt
        self.assertEqual(self.falsch(scan3, self.index(scan3, "Natrium"), "falscher_wert").json()["gelernt"], "")
        self.assertEqual(KorrekturZaehler.objects.get(art="labor").verworfen, 3)

    def test_keine_personendaten_pausieren_testzugang_und_fehler(self):
        scan = _scan(self.mitarbeiter, *self.ZEILEN)
        # „Muster“ steht im Dokument als Name: wird nicht gelernt
        self.assertEqual(self.falsch(scan, self.index(scan, "Muster"), "gehoert_nicht_dazu").json()["gelernt"], "")
        self.assertFalse(GelernteZuordnung.objects.filter(erkannt__contains="muster").exists())
        # pausiert: verworfen, aber nichts gelernt
        LernEinstellung.objects.filter(pk=LernEinstellung.aktuell().pk).update(pausiert=True)
        self.assertEqual(self.falsch(scan, self.index(scan, "Referenzbereich"), "gehoert_nicht_dazu").json()["gelernt"],
                         "")
        LernEinstellung.objects.update(pausiert=False)
        self.assertFalse(GelernteZuordnung.objects.exists())
        # Testzugang lernt nicht
        tessa = benutzer("tessa", Rolle.MITARBEITER, ist_test=True)
        eigener = _scan(tessa, *self.ZEILEN, ist_test=True)
        r = self.falsch(eigener, self.index(eigener, "Referenzbereich"), "gehoert_nicht_dazu", user=tessa)
        self.assertEqual(r.json()["gelernt"], "")
        self.assertFalse(GelernteZuordnung.objects.exists())
        # Fehler: unbekannter Grund, Zeile, Art; Betrachter
        self.assertEqual(self.falsch(scan, 0, "weiss_nicht").status_code, 400)
        self.assertEqual(self.falsch(scan, 99, "falscher_wert").status_code, 400)
        self.assertEqual(self.falsch(scan, 0, "falscher_wert", art="foto").status_code, 400)
        self.assertEqual(self.falsch(scan, 0, "falscher_wert", user=self.betrachter).status_code, 403)

    def test_bia_und_diagnose(self):
        scan = _scan(self.mediziner, "Klinikum Beispielstadt", "Diagnosen:", "- Kurzdarmsyndrom (K91.2 G)",
                     "Körpergewicht 58,4 kg", "BMI 21,2 kg/m²")
        r = self.falsch(scan, "gewicht_kg", "falsche_zeile", art="bia", user=self.mediziner)
        self.assertEqual(r.json()["gelernt"], "gesperrt")
        self.assertTrue(GelernteZuordnung.objects.get(art="bia", erkannt="koerpergewicht").gesperrt)
        scan2 = _scan(self.mediziner, "Klinikum Beispielstadt", "Körpergewicht 58,4 kg", "BMI 21,2 kg/m²")
        self.assertNotIn("gewicht_kg", scan2.auswertung["bia"]["werte"])
        r = self.falsch(scan, 0, "gehoert_nicht_dazu", art="diagnose", user=self.mediziner)
        self.assertEqual(r.json()["gelernt"], "ignorieren")
        scan3 = _scan(self.mediziner, "Klinikum Beispielstadt", "Diagnosen:", "- Kurzdarmsyndrom (K91.2 G)")
        self.assertEqual(scan3.auswertung["diagnosen"], [])


class SteuerungTest(Grundlage):
    def test_pausieren_und_schwelle_mit_recht_und_audit(self):
        c = client_fuer(self.mitarbeiter)   # Mitarbeiter pflegen Vorlagen (Standard)
        r = c.get("/api/scans/gelernt/steuerung/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["pausiert"], r.json()["schwelle"], r.json()["darf_steuern"]), (False, 2, True))
        r = c.patch("/api/scans/gelernt/steuerung/", {"pausiert": True, "schwelle": 1}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["pausiert"], r.json()["schwelle"]), (True, 1))
        self.assertTrue(lernen.pausiert())
        self.assertEqual(lernen.gelerntes().schwelle, 1)
        e = SystemEreignis.objects.filter(details__aktion="lernen_gesteuert").get()
        self.assertEqual(e.details["nachher"], {"pausiert": True, "schwelle": 1})
        for falsch in ({"schwelle": 0}, {"schwelle": 4}, {"schwelle": "x"}, {"pausiert": "ja"}):
            self.assertEqual(c.patch("/api/scans/gelernt/steuerung/", falsch, format="json").status_code, 400, falsch)
        # Schwelle 1: eine Bestätigung reicht für „sicher“
        g = auswertung.Gelerntes({("labor", "", "blutsalz k", ): [("2", "Kalium", 1)]}, set(), {}, schwelle=1)
        self.assertTrue(g.finden("labor", "", "blutsalz k").sicher)
        # ohne „Vorlagen pflegen“ nur lesen; Betrachter gar nicht; Testzugang nicht ändern
        self.assertEqual(client_fuer(self.betrachter).get("/api/scans/gelernt/steuerung/").status_code, 403)
        tessa = benutzer("tessa", Rolle.MITARBEITER, ist_test=True)
        self.assertEqual(client_fuer(tessa).patch("/api/scans/gelernt/steuerung/", {"schwelle": 3},
                                                  format="json").status_code, 403)
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/scans/gelernt/").json()["steuerung"]["schwelle"], 1)
