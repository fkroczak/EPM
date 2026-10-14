"""Texterkennung lernt mit (F182), Scan erkennt den Patienten (F183), komplett offline.

Die Scans entstehen hier ohne Erkennung: Seiten mit vorgegebenen Wörtern (wie das Ergebnis der Erkennung), damit die
Tests schnell sind und genau prüfen, was gelernt und angewandt wird. Der Offline-Test erkennt dagegen wirklich.
"""
import secrets
import socket
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from accounts.models import Rolle
from befunde.models import Laborbefund
from epm.pruefhilfen import Grundlage, benutzer, client_fuer
from patienten.models import Patient
from stammdaten.models import Laborparameter

from . import dienst, lernen, testbilder
from .models import GelernteZuordnung, KorrekturZaehler, Scan, ScanSeite
from .ocr import auswertung
from .tests import KATALOG_BEISPIEL, _seite

SCANS = Path(tempfile.mkdtemp(prefix="epm-scans-lernen-"))


def _gelernt(*eintraege, gesperrt=(), spalten=None):
    """Gelerntes für reine Tests: (Art, Quelle, Bezeichnung, Ziel, Zieltext, Bestätigungen)."""
    e = {}
    for art, quelle, erkannt, ziel, text, n in eintraege:
        e.setdefault((art, quelle, erkannt), []).append((str(ziel), text, n))
    return auswertung.Gelerntes(e, set(gesperrt), spalten or {})


# ======================================================================= Anwenden (ohne Datenbank)
class AnwendenTest(SimpleTestCase):
    def werte(self, gelernt, *zeilen, kopf="Labor Nord MVZ"):
        a = auswertung.auswerten([_seite(kopf, *zeilen)], KATALOG_BEISPIEL, gelernt=gelernt)
        return {w["erkannt_als"]: w for w in a["labor"]["werte"]}

    def test_unbekannte_bezeichnung_gelernt_sicher_und_als_vorschlag(self):
        zeile = "Blutsalz-K 3,9 mmol/l 3,5 - 5,1"
        ohne = self.werte(None, zeile)["Blutsalz-K"]
        self.assertIsNone(ohne["parameter"])
        # einmal bestätigt: nur Vorschlag, nicht vorgewählt, gekennzeichnet
        w = self.werte(_gelernt(("labor", "", "blutsalz k", 2, "Kalium", 1)), zeile)["Blutsalz-K"]
        self.assertEqual((w["parameter"], w["zuordnung"], w["vorschlag"]), (2, "gelernt_vorschlag", False))
        self.assertTrue(any("gelernt" in h for h in w["hinweise"]))
        # ab der Schwelle sicher: vorgewählt
        w = self.werte(_gelernt(("labor", "", "blutsalz k", 2, "Kalium", auswertung.SCHWELLE)), zeile)["Blutsalz-K"]
        self.assertEqual((w["parameter"], w["zuordnung"], w["vorschlag"]), (2, "gelernt", True))

    def test_labor_vor_allgemein(self):
        zeile = "Elyt-A 140 mmol/l 135 - 145"
        g = _gelernt(("labor", "labor nord mvz", "elyt a", 1, "Natrium", 2), ("labor", "", "elyt a", 2, "Kalium", 5))
        self.assertEqual(self.werte(g, zeile)["Elyt-A"]["parameter"], 1)                  # dasselbe Labor
        self.assertEqual(self.werte(g, zeile, kopf="Labor Süd MVZ")["Elyt-A"]["parameter"], 2)  # anderes: allgemein
        # Für dieses Labor nur ein Vorschlag, allgemein sicher → das sichere allgemeine gewinnt
        g = _gelernt(("labor", "labor nord mvz", "elyt a", 1, "Natrium", 1), ("labor", "", "elyt a", 2, "Kalium", 3))
        self.assertEqual(self.werte(g, zeile)["Elyt-A"]["zuordnung"], "gelernt")
        self.assertEqual(self.werte(g, zeile)["Elyt-A"]["parameter"], 2)

    def test_gelernt_vor_aehnlichkeit_und_katalog(self):
        # „Kreatimin“ wäre ähnlich zu Kreatinin; das Labor meint damit (gelernt) etwas anderes
        g = _gelernt(("labor", "labor nord mvz", "kreatimin", 3, "Albumin", 2))
        self.assertEqual(self.werte(None, "Kreatimin 1,1 mg/dl")["Kreatimin"]["zuordnung"], "aehnlich")
        self.assertEqual(self.werte(g, "Kreatimin 1,1 mg/dl")["Kreatimin"]["parameter"], 3)

    def test_gesperrt(self):
        zeile = "Kreatimin 1,1 mg/dl 0,5 - 0,9"
        # gesperrt: auch die Ähnlichkeitssuche darf so nicht mehr zuordnen
        g = _gelernt(gesperrt={("labor", "", "kreatimin", "4")})
        w = self.werte(g, zeile)["Kreatimin"]
        self.assertIsNone(w["parameter"])
        # gesperrte gelernte Zuordnung wird nicht angewandt; nur für ein anderes Labor gesperrt → gilt hier weiter
        g = _gelernt(("labor", "", "blutsalz k", 2, "Kalium", 4), gesperrt={("labor", "", "blutsalz k", "2")})
        self.assertIsNone(self.werte(g, "Blutsalz-K 3,9 mmol/l")["Blutsalz-K"]["parameter"])
        g = _gelernt(("labor", "", "blutsalz k", 2, "Kalium", 4), gesperrt={("labor", "labor sued", "blutsalz k", "2")})
        self.assertEqual(self.werte(g, "Blutsalz-K 3,9 mmol/l")["Blutsalz-K"]["parameter"], 2)

    def test_bia_und_diagnose_gelernt(self):
        seite = _seite("Messprotokoll 20.09.2026", "Aktive Zellen 18,9 kg", "Körpergewicht 58,4 kg")
        g = _gelernt(("bia", "", "aktive zellen", "bcm_kg", "bcm_kg", 2))
        a = auswertung.auswerten([seite], KATALOG_BEISPIEL, gelernt=g)
        self.assertEqual(a["bia"]["werte"]["bcm_kg"]["wert"], "18.9")
        self.assertEqual(a["bia"]["werte"]["bcm_kg"]["zuordnung"], "gelernt")
        self.assertTrue(a["bia"]["werte"]["bcm_kg"]["vorschlag"])
        brief = _seite("Klinikum Beispielstadt", "Diagnosen:", "- Kurzdarmsyndorm (K91.2 G)")
        g = _gelernt(("diagnose", "klinikum beispielstadt", "kurzdarmsyndorm", "K91.2", "Kurzdarmsyndrom", 2))
        d = auswertung.auswerten([brief], KATALOG_BEISPIEL, gelernt=g)["diagnosen"][0]
        self.assertEqual((d["bezeichnung"], d["zuordnung"], d["erkannt_als"]),
                         ("Kurzdarmsyndrom", "gelernt", "Kurzdarmsyndorm"))
        g = _gelernt(("diagnose", "", "kurzdarmsyndorm", "K91.2", "Kurzdarmsyndrom", 1))
        d = auswertung.auswerten([brief], KATALOG_BEISPIEL, gelernt=g)["diagnosen"][0]
        self.assertEqual(d["bezeichnung"], "Kurzdarmsyndorm")   # nur Vorschlag
        self.assertEqual(d["gelernt"]["bezeichnung"], "Kurzdarmsyndrom")
        # Diagnose ohne Code im Brief: der gelernte Code wird eingesetzt
        brief = _seite("Klinikum Beispielstadt", "Diagnosen:", "- Kurzdarmsyndrom")
        g = _gelernt(("diagnose", "", "kurzdarmsyndrom", "K91.2", "Kurzdarmsyndrom", 2))
        d = auswertung.auswerten([brief], KATALOG_BEISPIEL, gelernt=g)["diagnosen"][0]
        self.assertEqual((d["icd_code"], d["zuordnung"], d["vorschlag"]), ("K91.2", "gelernt", True))

    def test_spaltenlage_je_labor(self):
        # Zwei Werte – zu wenige, um die Spalte selbst zu finden; mit der gelernten Lage wird „118.69“ als ↑18.69 gelesen
        seite = {"breite": 1000, "hoehe": 1000, "reihen": [
            [{"q": "t", "w": [["Labor", 10, 10, 50, 20, 0.95], ["Nord", 70, 10, 40, 20, 0.95], ["MVZ", 120, 10, 30, 20, 0.95]]}],
            [{"q": "t", "w": [["Zink", 10, 50, 40, 20, 0.95], ["118.69", 290, 50, 60, 20, 0.95],
                              ["µg/l", 400, 50, 40, 20, 0.95], ["70", 500, 50, 20, 20, 0.95], ["-", 525, 50, 5, 20, 0.95],
                              ["120", 535, 50, 30, 20, 0.95]]}],
        ]}
        ohne = auswertung.auswerten([seite], KATALOG_BEISPIEL)["labor"]["werte"][0]
        self.assertEqual(ohne["wert"], "118.69")
        g = _gelernt(spalten={"labor nord mvz": (0.30, 0.01)})
        mit = auswertung.auswerten([seite], KATALOG_BEISPIEL, gelernt=g)["labor"]["werte"][0]
        self.assertEqual((mit["wert"], mit["markierung"]), ("18.69", "↓"))

    def test_etikett_an_der_stelle(self):
        reihen = auswertung.reihen_aus([_seite("Blutsalz-K 3,9 mmol/l")])
        wert = reihen[0][1]
        self.assertEqual(auswertung.etikett_an(reihen, 0, list(wert.box)), "Blutsalz-K")
        self.assertEqual(auswertung.etikett_an(reihen, 0, list(reihen[0][0].box)), "")
        self.assertEqual(auswertung.etikett_an(reihen, 3, list(wert.box)), "")


# ======================================================================= Lernen beim Übernehmen
def _scan(user, *zeilen, ist_test=False) -> Scan:
    """Erkannter Scan mit einer Seite aus ``zeilen`` (ohne Erkennung, mit weißem Seitenbild für die PDF)."""
    ordner = secrets.token_hex(16)
    pfad = settings.EPM_SCANS / ordner
    pfad.mkdir(parents=True)
    cv2.imwrite(str(pfad / "bild.png"), np.full((300, 200), 255, dtype=np.uint8))
    scan = Scan.objects.create(titel="Befund", originalname="b.png", mime="image/png", groesse=1, sha256="0" * 64,
                               ordner=ordner, hochgeladen_von=user, ist_test=ist_test, status=Scan.Status.FERTIG,
                               laeuft_ab_am=timezone.now() + timedelta(days=7),
                               auswertung={"originale": [{"name": "b.png", "mime": "image/png"}]})
    seite = _seite(*zeilen)
    seite.update(breite=200, hoehe=300)
    for r in seite["reihen"]:
        for s in r:
            for w in s["w"]:
                w[1], w[2], w[3], w[4] = w[1] / 10, w[2] / 10, w[3] / 10, w[4] / 10
    ScanSeite.objects.create(scan=scan, nr=1, roh="bild.png", bild="bild.png", grau="bild.png", breite=200, hoehe=300,
                             status=ScanSeite.Status.FERTIG, ergebnis=seite, text="\n".join(zeilen))
    dienst.auswerten(scan)
    scan.save()
    return scan


def _param(name, einheit="mg/dl"):
    p = Laborparameter.objects.filter(name=name).first()
    return p or Laborparameter.objects.create(name=name, einheit=einheit, gruppe="sonstiges")


@override_settings(EPM_SCANS=SCANS)
class LernenTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.testpatient = Patient.objects.create(nachname="Muster", vorname="Erika", ist_test=True,
                                                 geburtsdatum="1961-03-14")
        cls.harnstoff = _param("Harnstoff")
        cls.kreatinin = _param("Kreatinin")
        cls.natrium = _param("Natrium", "mmol/l")

    ZEILEN = ("Labor Nord MVZ", "Abnahme: 01.09.2026", "Natrium 138 mmol/l 135 - 145", "Kreatimin 1,1 mg/dl 0,5 - 0,9",
              "Blutharnstoff 35 mg/dl 10 - 50")

    def zuordnen(self, scan, werte, herkunft, client=None, **extra):
        c = client or client_fuer(self.mitarbeiter)
        r = c.post(f"/api/scans/{scan.id}/zuordnen/", {
            "patient": self.testpatient.id, "titel": "Labor",
            "labor": {"abgenommen_am": "2026-09-01", "labor": "Labor Nord MVZ", "werte": werte},
            "herkunft": {"labor": herkunft}, **extra}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def uebernehmen(self, scan, harnstoff_wert="35"):
        """Wie die Prüfansicht: Natrium unverändert, Kreatimin → Kreatinin (ähnlich), Blutharnstoff → Harnstoff."""
        a = scan.auswertung["labor"]["werte"]
        i = {w["erkannt_als"]: n for n, w in enumerate(a)}
        werte = [{"parameter": self.natrium.id, "wert": "138", "einheit": "mmol/l"},
                 {"parameter": self.kreatinin.id, "wert": "1.1", "einheit": "mg/dl"},
                 {"parameter": self.harnstoff.id, "wert": harnstoff_wert, "einheit": "mg/dl"}]
        herkunft = [{"index": i["Natrium"]}, {"index": i["Kreatimin"]}, {"index": i["Blutharnstoff"]}]
        return self.zuordnen(scan, werte, herkunft)

    def test_lernen_beim_uebernehmen_und_anwenden(self):
        scan = _scan(self.mitarbeiter, *self.ZEILEN)
        w = {x["erkannt_als"]: x for x in scan.auswertung["labor"]["werte"]}
        self.assertIsNone(w["Blutharnstoff"]["parameter"])
        self.uebernehmen(scan)
        g = GelernteZuordnung.objects.filter(art="labor", erkannt="blutharnstoff")
        self.assertEqual({(x.quelle, x.ziel, x.bestaetigt) for x in g},
                         {("labor nord mvz", str(self.harnstoff.id), 1), ("", str(self.harnstoff.id), 1)})
        self.assertEqual(g.first().zuletzt_von, self.mitarbeiter)
        krea = GelernteZuordnung.objects.get(art="labor", erkannt="kreatimin", quelle="")
        self.assertTrue(krea.lesefehler)
        # Natrium war genau erkannt und unverändert: nichts zu lernen
        self.assertFalse(GelernteZuordnung.objects.filter(erkannt="natrium").exists())
        # nächster Befund desselben Labors: Vorschlag (einmal bestätigt), nach dem zweiten Mal sicher
        scan2 = _scan(self.mitarbeiter, *self.ZEILEN)
        w = {x["erkannt_als"]: x for x in scan2.auswertung["labor"]["werte"]}
        self.assertEqual((w["Blutharnstoff"]["parameter"], w["Blutharnstoff"]["zuordnung"]),
                         (self.harnstoff.id, "gelernt_vorschlag"))
        self.assertFalse(w["Blutharnstoff"]["vorschlag"])
        self.uebernehmen(scan2)
        scan3 = _scan(self.mitarbeiter, *self.ZEILEN)
        w = {x["erkannt_als"]: x for x in scan3.auswertung["labor"]["werte"]}
        self.assertEqual(w["Blutharnstoff"]["zuordnung"], "gelernt")
        self.assertTrue(w["Blutharnstoff"]["vorschlag"])
        # nichts davon steht ohne Zuordnen in einer Akte
        self.assertEqual(Laborbefund.objects.filter(patient=self.testpatient).count(), 2)
        # häufig bestätigt → Wörterliste für Tesseract, Lesefehler nicht
        self.assertIn("Blutharnstoff", lernen.woerter())
        self.assertNotIn("Kreatimin", lernen.woerter())
        datei = SCANS / "woerter.txt"
        dienst.woerterliste_schreiben(datei)
        self.assertIn("Blutharnstoff", datei.read_text(encoding="utf-8").split())

    def test_von_hand_ergaenzter_wert_ueber_die_stelle(self):
        scan = _scan(self.mitarbeiter, "Labor Nord MVZ", "Natrium 138 mmol/l", "Kalium 4,1 mmol/l",
                     "Harnstoffwert gesamt 35")
        self.assertFalse(any(w["erkannt_als"].startswith("Harnstoffwert") for w in scan.auswertung["labor"]["werte"]))
        reihen = auswertung.reihen_aus([scan.seiten.first().ergebnis])
        wert = next(t for r in reihen for t in r if t.text == "35")
        self.zuordnen(scan, [{"parameter": self.harnstoff.id, "wert": "35", "einheit": "mg/dl"}],
                      [{"index": None, "stelle": {"seite": 0, "box": list(wert.box)}}])
        self.assertTrue(GelernteZuordnung.objects.filter(art="labor", erkannt="harnstoffwert gesamt",
                                                         ziel=str(self.harnstoff.id)).exists())

    def test_keine_personendaten(self):
        # Das Modell hat keinen Bezug zu Patient, Scan oder Dokument und keine Wertfelder
        felder = {f.name for f in GelernteZuordnung._meta.get_fields()}
        verweise = {f.related_model._meta.label for f in GelernteZuordnung._meta.get_fields() if f.is_relation}
        self.assertEqual(verweise, {"stammdaten.Laborparameter", settings.AUTH_USER_MODEL})
        self.assertFalse(felder & {"patient", "scan", "dokument", "wert", "wert_text", "befund", "text"})
        self.assertFalse({f.name for f in KorrekturZaehler._meta.get_fields()} - {"id", "monat", "art", "uebernommen",
                                                                                     "korrigiert", "verworfen"})
        # Bezeichnungen mit Name, Datum oder Angaben zur Person werden nie gelernt
        self.assertFalse(lernen.zulaessig("Muster Erika", self.testpatient))
        self.assertFalse(lernen.zulaessig("Kontrolle 14.03.1961"))
        self.assertFalse(lernen.zulaessig("Geb. Datum"))
        self.assertFalse(lernen.zulaessig("Vers.-Nr 1234567"))
        self.assertTrue(lernen.zulaessig("Harnstoff-N", self.testpatient))
        scan = _scan(self.mitarbeiter, "Labor Nord MVZ", "Natrium 138 mmol/l", "Muster Erika 35")
        reihen = auswertung.reihen_aus([scan.seiten.first().ergebnis])
        wert = next(t for r in reihen for t in r if t.text == "35")
        self.zuordnen(scan, [{"parameter": self.harnstoff.id, "wert": "35", "einheit": "mg/dl"}],
                      [{"index": None, "stelle": {"seite": 0, "box": list(wert.box)}}])
        self.assertFalse(GelernteZuordnung.objects.filter(erkannt__contains="muster").exists())
        # Werte und Namen stehen nirgends im Gelernten
        for g in GelernteZuordnung.objects.all():
            daten = " ".join(str(v) for v in (g.erkannt, g.erkannt_anzeige, g.ziel, g.ziel_text, g.quelle))
            self.assertNotIn("Muster", daten)
            self.assertNotIn("138", daten)

    def test_testzugang_lernt_nicht(self):
        tessa = benutzer("tessa", Rolle.MITARBEITER, ist_test=True)
        scan = _scan(tessa, *self.ZEILEN, ist_test=True)
        a = scan.auswertung["labor"]["werte"]
        i = {w["erkannt_als"]: n for n, w in enumerate(a)}
        self.zuordnen(scan, [{"parameter": self.harnstoff.id, "wert": "35", "einheit": "mg/dl"}],
                      [{"index": i["Blutharnstoff"]}], client=client_fuer(tessa))
        self.assertFalse(GelernteZuordnung.objects.exists())
        self.assertFalse(KorrekturZaehler.objects.exists())

    def test_diagnose_und_bia_lernen(self):
        c = client_fuer(self.mediziner)
        scan = _scan(self.mediziner, "Klinikum Beispielstadt", "Diagnosen:", "- Kurzdarmsyndorm (K91.2 G)",
                     "Aktive Zellen 18,9 kg", "Körpergewicht 58,4 kg")
        reihen = auswertung.reihen_aus([scan.seiten.first().ergebnis])
        wert = next(t for r in reihen for t in r if t.text == "18,9")
        r = c.post(f"/api/scans/{scan.id}/zuordnen/", {
            "patient": self.testpatient.id, "titel": "Brief",
            "bia": {"gemessen_am": "2026-09-20", "gewicht_kg": "58.4", "bcm_kg": "18.9", "gewicht_uebernehmen": False},
            "diagnosen": [{"bezeichnung": "Kurzdarmsyndrom", "icd_code": "K91.2", "kennzeichen": "G"}],
            "herkunft": {"bia": {"bcm_kg": {"seite": 0, "box": list(wert.box)}}, "diagnosen": [0]},
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(GelernteZuordnung.objects.filter(art="bia", erkannt="aktive zellen", ziel="bcm_kg").exists())
        d = GelernteZuordnung.objects.get(art="diagnose", quelle="", erkannt="kurzdarmsyndorm")
        self.assertEqual((d.ziel, d.ziel_text), ("K91.2", "Kurzdarmsyndrom"))
        # Kennzahl: BIA-BCM von Hand (korrigiert), Gewicht unverändert; Diagnose korrigiert
        z = {k.art: (k.uebernommen, k.korrigiert) for k in KorrekturZaehler.objects.all()}
        self.assertEqual(z["bia"], (2, 1))
        self.assertEqual(z["diagnose"], (1, 1))

    def test_diagnose_ohne_code_lernen(self):
        """Steht im Brief kein Code, wird der ergänzte Code gelernt und beim nächsten Brief eingesetzt."""
        c = client_fuer(self.mediziner)
        scan = _scan(self.mediziner, "Klinikum Beispielstadt", "Diagnosen:", "- Lipödem Stadium II")
        # nicht in der Diagnoseliste
        d = scan.auswertung["diagnosen"][0]
        self.assertEqual((d["icd_code"], d["vorschlag"]), ("", False))
        # ohne Code nimmt die Akte die Diagnose nicht an
        r = c.post(f"/api/scans/{scan.id}/zuordnen/", {
            "patient": self.testpatient.id, "titel": "Brief", "herkunft": {"diagnosen": [0]},
            "diagnosen": [{"bezeichnung": "Lipödem Stadium II", "icd_code": "", "kennzeichen": "G"}]}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        r = c.post(f"/api/scans/{scan.id}/zuordnen/", {
            "patient": self.testpatient.id, "titel": "Brief", "herkunft": {"diagnosen": [0]},
            "diagnosen": [{"bezeichnung": "Lipödem Stadium II", "icd_code": "E88.21", "kennzeichen": "G"}]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        g = GelernteZuordnung.objects.get(art="diagnose", quelle="", erkannt="lipoedem stadium ii")
        self.assertEqual((g.ziel, g.ziel_text), ("E88.21", "Lipödem Stadium II"))
        neu = _scan(self.mediziner, "Klinikum Beispielstadt", "Diagnosen:", "- Lipödem Stadium II")
        self.assertEqual(neu.auswertung["diagnosen"][0]["icd_code"], "E88.21")

    def test_kennzahl(self):
        scan = _scan(self.mitarbeiter, *self.ZEILEN)
        self.uebernehmen(scan)
        z = KorrekturZaehler.objects.get(art="labor")
        # Natrium und Kreatinin unverändert übernommen, Blutharnstoff musste zugeordnet werden
        self.assertEqual((z.uebernommen, z.korrigiert), (3, 1))
        scan = _scan(self.mitarbeiter, *self.ZEILEN)
        self.uebernehmen(scan, harnstoff_wert="36")   # jetzt gelernt, aber den Wert korrigiert
        k = client_fuer(self.mitarbeiter).get("/api/scans/kennzahl/").json()
        self.assertEqual(len(k["monate"]), 12)
        self.assertEqual((k["aktuell"]["uebernommen"], k["aktuell"]["korrigiert"]), (6, 2))
        self.assertEqual(k["aktuell"]["anteil"], 33.3)
        self.assertEqual(k["aktuell"]["monat"], timezone.localdate().replace(day=1).isoformat())
        # Vormonat für den Trend
        vor = (timezone.localdate().replace(day=1) - timedelta(days=1)).replace(day=1)
        KorrekturZaehler.objects.create(monat=vor, art="labor", uebernommen=10, korrigiert=5)
        k = lernen.kennzahl()
        self.assertEqual(k["vormonat"]["anteil"], 50.0)
        self.assertEqual(k["trend"], -16.7)

    def test_verwalten_sperren_loeschen_und_rechte(self):
        scan = _scan(self.mitarbeiter, *self.ZEILEN)
        self.uebernehmen(scan)
        c = client_fuer(self.mitarbeiter)
        r = c.get("/api/scans/gelernt/?suche=harnstoff")
        self.assertEqual(r.status_code, 200, r.content)
        liste = r.json()["eintraege"]
        self.assertEqual({e["quelle_name"] for e in liste}, {"Labor Nord MVZ", "allgemein"})
        self.assertEqual({e["ziel"] for e in liste}, {"Harnstoff"})
        self.assertEqual(r.json()["quellen"], [{"quelle": "labor nord mvz", "name": "Labor Nord MVZ"}])
        self.assertEqual(len(c.get("/api/scans/gelernt/?quelle=allgemein&art=labor").json()["eintraege"]), 2)
        allgemein = next(e for e in liste if e["quelle"] == "")
        # sperren: „nie wieder so zuordnen“ – gilt dann bei allen Laboren
        r = c.patch(f"/api/scans/gelernt/{allgemein['id']}/", {"gesperrt": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["gesperrt"])
        scan2 = _scan(self.mitarbeiter, *self.ZEILEN)
        w = {x["erkannt_als"]: x for x in scan2.auswertung["labor"]["werte"]}
        self.assertIsNone(w["Blutharnstoff"]["parameter"])
        # löschen
        eigen = next(e for e in liste if e["quelle"])
        self.assertEqual(c.delete(f"/api/scans/gelernt/{eigen['id']}/").status_code, 204)
        self.assertFalse(GelernteZuordnung.objects.filter(pk=eigen["id"]).exists())
        self.assertEqual(c.delete(f"/api/scans/gelernt/{eigen['id']}/").status_code, 404)
        # Rechte: Betrachter nicht; Testzugang nur lesen
        self.assertEqual(client_fuer(self.betrachter).get("/api/scans/gelernt/").status_code, 403)
        tessa = benutzer("tessa", Rolle.MITARBEITER, ist_test=True)
        t = client_fuer(tessa)
        self.assertEqual(t.get("/api/scans/gelernt/").status_code, 200)
        self.assertEqual(t.delete(f"/api/scans/gelernt/{allgemein['id']}/").status_code, 403)

    def test_leeren_und_loeschen_von_scans_und_akten(self):
        scan = _scan(self.mitarbeiter, *self.ZEILEN)
        self.uebernehmen(scan)
        anzahl = GelernteZuordnung.objects.count()
        self.assertGreater(anzahl, 0)
        # Gelerntes bleibt, wenn Scans und Akten gelöscht werden (keine Personendaten)
        Scan.objects.all().delete()
        from audit.schutz import wartungsmodus
        from patienten.datenschutz import akten_entfernen

        with wartungsmodus():
            akten_entfernen([self.testpatient.id])
        self.assertEqual(GelernteZuordnung.objects.count(), anzahl)
        # „Datenbank leeren“: lernen.leeren()
        self.assertEqual(lernen.leeren(), anzahl)
        self.assertFalse(GelernteZuordnung.objects.exists() or KorrekturZaehler.objects.exists())


# ======================================================================= F183: Scan erkennt den Patienten
@override_settings(EPM_SCANS=SCANS)
class PatientErkennenTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.erika = Patient.objects.create(nachname="Muster", vorname="Erika", geburtsdatum="1968-03-14")
        cls.erika2 = Patient.objects.create(nachname="Muster", vorname="Erika", geburtsdatum="1975-07-01")
        cls.hans = Patient.objects.create(nachname="Beispielmann", vorname="Hans", geburtsdatum="1950-01-02")

    def vorschlaege(self, *zeilen, user=None):
        scan = _scan(user or self.mitarbeiter, *zeilen)
        return dienst.patient_vorschlaege(scan, user or self.mitarbeiter)

    def test_exakter_treffer(self):
        v = self.vorschlaege("Labor Nord MVZ", "Patient: Muster, Erika   geb. 14.03.1968", "Natrium 138 mmol/l")
        self.assertEqual(v[0]["id"], self.erika.id)
        self.assertEqual(v[0]["stufe"], "sicher")
        self.assertIn("Name und Geburtsdatum erkannt", v[0]["grund"])

    def test_lesefehler_im_namen(self):
        v = self.vorschlaege("Klinikum Beispielstadt", "wir berichten über Frau Hans Beispielmonn, geb. 02.01.1950")
        self.assertEqual(v[0]["id"], self.hans.id)
        self.assertEqual(v[0]["stufe"], "sicher")
        self.assertIn("ähnlich gelesen", v[0]["grund"])
        # ohne Geburtsdatum nur ein Hinweis bzw. wahrscheinlich, nie sicher
        v = self.vorschlaege("Name: Beispielmonn, Hans")
        self.assertEqual([x["id"] for x in v], [self.hans.id])
        self.assertNotEqual(v[0]["stufe"], "sicher")

    def test_zwei_gleichnamige_mit_verschiedenem_geburtsdatum(self):
        v = self.vorschlaege("Name: Muster, Erika     Geburtsdatum: 01.07.1975")
        self.assertEqual(v[0]["id"], self.erika2.id)
        self.assertEqual(v[0]["stufe"], "sicher")
        andere = next(x for x in v if x["id"] == self.erika.id)
        self.assertEqual(andere["stufe"], "unsicher")
        self.assertIn("passt nicht", andere["grund"])
        # ohne Geburtsdatum im Dokument: beide gleich wahrscheinlich, keiner sicher
        v = self.vorschlaege("Name: Muster, Erika")
        self.assertEqual({x["id"] for x in v}, {self.erika.id, self.erika2.id})
        self.assertEqual({x["stufe"] for x in v}, {"wahrscheinlich"})

    def test_fremde_akte_nicht_vorgeschlagen(self):
        # eingeschränkte Akte (Art. 18 DSGVO) sieht die Person nicht
        Patient.objects.filter(pk=self.hans.pk).update(eingeschraenkt_am=timezone.now())
        self.assertEqual(self.vorschlaege("Patient: Beispielmann, Hans  geb. 02.01.1950"), [])
        # Testzugang sieht nur Testpatienten
        tessa = benutzer("tessa", Rolle.MITARBEITER, ist_test=True)
        self.assertEqual(self.vorschlaege("Patient: Muster, Erika  geb. 14.03.1968", user=tessa), [])

    def test_kein_treffer(self):
        self.assertEqual(self.vorschlaege("Patient: Unbekannt, Otto  geb. 05.05.1955", "Natrium 138 mmol/l"), [])
        self.assertEqual(self.vorschlaege("Natrium 138 mmol/l"), [])

    def test_wird_nicht_gelernt_und_nicht_ausgeliefert(self):
        scan = _scan(self.mitarbeiter, "Patient: Muster, Erika   geb. 14.03.1968")
        r = client_fuer(self.mitarbeiter).get(f"/api/scans/{scan.id}/").json()
        self.assertNotIn("patient", r["auswertung"])
        self.assertEqual(r["vorschlaege"][0]["id"], self.erika.id)
        self.assertFalse(GelernteZuordnung.objects.exists())


# ======================================================================= Komplett offline
class _KeinNetz:
    """Verbietet jeden Netzwerkzugriff (außer zur Datenbank über den Unix-Socket bzw. localhost, den Django braucht)."""

    def __init__(self):
        self.versuche = []

    def __enter__(self):
        echt_connect = socket.socket.connect

        def connect(sock, adresse, *a, **k):
            if sock.family == socket.AF_UNIX:
                return echt_connect(sock, adresse, *a, **k)
            self.versuche.append(adresse)
            raise OSError(f"Netzwerk im Test verboten: {adresse}")

        def create_connection(adresse, *a, **k):
            self.versuche.append(adresse)
            raise OSError(f"Netzwerk im Test verboten: {adresse}")

        def getaddrinfo(host, *a, **k):
            self.versuche.append(host)
            raise socket.gaierror(f"Namensauflösung im Test verboten: {host}")

        self._patches = [mock.patch.object(socket.socket, "connect", connect),
                         mock.patch.object(socket, "create_connection", create_connection),
                         mock.patch.object(socket, "getaddrinfo", getaddrinfo)]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *_):
        for p in self._patches:
            p.stop()
        return False


class OfflineTest(SimpleTestCase):
    def test_schalter_gegen_downloads(self):
        import os

        from .ocr import paddle

        for name, wert in paddle.OFFLINE_UMGEBUNG.items():
            self.assertEqual(os.environ.get(name), wert, name)
        with mock.patch.dict(os.environ, {"EPM_OCR_MODELLE": "https://example.org/modelle"}):
            with self.assertRaises(ValueError):
                paddle.modell_ordner()
        with self.assertRaises(FileNotFoundError):
            paddle._sitzung(Path("https://example.org/det.onnx"))

    def test_erkennung_ohne_netz(self):
        """Seite erkennen, während jeder Netzwerkzugriff verboten ist: mit PP-OCR (falls die Modelle da sind) und
        sauber ohne – dann nur Tesseract."""
        from .ocr import erkennung, laden, paddle
        from .ocr.tesseract import verfuegbar

        if not verfuegbar()[0]:
            self.skipTest("Tesseract fehlt")
        bild = testbilder.png(testbilder.seite(testbilder.LABOR), verkleinern=0.67)
        with _KeinNetz() as netz:
            _, roh = laden.seiten_laden(bild)
            p = paddle.Paddle.laden()
            _, daten = erkennung.seite_erkennen(roh[0], {}, paddle=p)
            text = auswertung.reihen_aus([daten])
            # ohne Paddle (Modelle fehlen oder lassen sich nicht laden): Tesseract allein
            with mock.patch.object(paddle, "modell_ordner", return_value=Path("/gibt/es/nicht")):
                paddle.Paddle._instanz, alt = None, paddle.Paddle._instanz
                try:
                    self.assertIsNone(paddle.Paddle.laden())
                finally:
                    paddle.Paddle._instanz = alt
                _, nur_t = erkennung.seite_erkennen(roh[0], {}, paddle=None)
        self.assertEqual(netz.versuche, [])
        self.assertIn("Kalium", " ".join(t.text for r in text for t in r))
        self.assertIn("Kalium", " ".join(t.text for r in auswertung.reihen_aus([nur_t]) for t in r))
        self.assertEqual(nur_t.get("verfahren"), ["tesseract"])
