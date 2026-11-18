"""Freie Gestaltung am Raster (14.10.2026): 6-Spalten-Raster, Kopf- und Fußband, Anschriftfeld nach DIN 5008."""
import re
import subprocess
import tempfile
from datetime import date

from django.test import TestCase

from patienten.models import Patient

from . import gestaltung
from .bloecke import STARTVORLAGEN, pruefe_bloecke
from .felder import Kontext
from .pdf import bloecke_html, html_zu_pdf, seite
from .tests import PDFTOTEXT, pdf_text

MM = 25.4 / 72  # pt → mm


def woerter(pdf: bytes) -> list[tuple[int, str, float, float]]:
    """(Seite, Wort, x, y) in mm ab der linken oberen Ecke."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf)
        f.flush()
        xml = subprocess.run([PDFTOTEXT, "-bbox", f.name, "-"], capture_output=True, text=True, check=True).stdout
    ergebnis, seite_nr = [], 0
    for zeile in xml.splitlines():
        if "<page " in zeile:
            seite_nr += 1
        m = re.search(r'xMin="([\d.]+)" yMin="([\d.]+)".*>(.*)</word>', zeile)
        if m:
            ergebnis.append((seite_nr, m.group(3), float(m.group(1)) * MM, float(m.group(2)) * MM))
    return ergebnis


def finde(pdf, wort):
    return next(w for w in woerter(pdf) if w[1] == wort)


def text(id_, inhalt, **optionen):
    return {"id": id_, "typ": "text", "text": inhalt, "optionen": optionen}


class RasterTest(TestCase):
    def setUp(self):
        self.k = Kontext(patient=Patient(nachname="Muster", vorname="Erika", strasse="Musterweg 5", plz="48143",
                                         ort="Münster"), heute=date(2026, 10, 14))

    def test_raster_pruefung(self):
        b = [text("a", "Links", raster_von=1, raster_bis=4), text("b", "Rechts", raster_von=5, raster_bis=6,
                                                                 neben_vorherigem="raster")]
        self.assertEqual(pruefe_bloecke("eigen-x", b), [])
        # Überdeckung, verdrehte Spalten, außerhalb des Rasters, falscher Typ
        b[1]["optionen"]["raster_von"] = 4
        self.assertTrue(any("überdeckt" in f for f in pruefe_bloecke("eigen-x", b)))
        b[1]["optionen"].update(raster_von=6, raster_bis=5)
        self.assertTrue(any("links von" in f for f in pruefe_bloecke("eigen-x", b)))
        b[1]["optionen"].update(raster_von=5, raster_bis=7)
        self.assertTrue(any("raster_bis" in f for f in pruefe_bloecke("eigen-x", b)))
        b[1]["optionen"].update(raster_bis=True)
        self.assertTrue(any("raster_bis" in f for f in pruefe_bloecke("eigen-x", b)))
        # ein Block über die ganze Breite lässt keinen Platz daneben
        voll = [text("a", "Ganz"), text("b", "Daneben", raster_von=5, neben_vorherigem="raster")]
        self.assertTrue(any("kein Platz" in f for f in pruefe_bloecke("eigen-x", voll)))
        self.assertTrue(any("davor ein Block im Raster" in f for f in pruefe_bloecke(
            "eigen-x", [{"id": "l", "typ": "leerraum"}, text("b", "x", neben_vorherigem="raster")])))
        self.assertTrue(any("im Raster schmaler" in f for f in pruefe_bloecke(
            "eigen-x", [{"id": "l", "typ": "trennlinie", "optionen": {"raster_von": 2}}])))
        # mitgelieferte Vorlagen mit Drittel/Hälfte bleiben gültig
        self.assertEqual(pruefe_bloecke("infusionsplan", STARTVORLAGEN["infusionsplan"]), [])

    def test_raster_im_pdf(self):
        b = [text("a", "Linksblock", raster_von=1, raster_bis=2), text("b", "Mittelblock", raster_von=3, raster_bis=4,
                                                                      neben_vorherigem="raster"),
             text("c", "Rechtsblock", raster_von=5, raster_bis=6, neben_vorherigem="raster"),
             text("d", "Einzeln", raster_von=4, raster_bis=6)]
        inhalt = bloecke_html("eigen-x", b, self.k)[0]
        self.assertEqual(inhalt.count('class="paar raster"'), 2)
        pdf = html_zu_pdf(seite("x", inhalt))
        satz = 210 - 2 * 17
        for wort, von in (("Linksblock", 1), ("Mittelblock", 3), ("Rechtsblock", 5), ("Einzeln", 4)):
            x = finde(pdf, wort)[2]
            self.assertAlmostEqual(x, 17 + satz * gestaltung.raster_links(von) / 100, delta=1.5, msg=wort)
        # drei Blöcke in einer Zeile stehen auf derselben Höhe
        self.assertAlmostEqual(finde(pdf, "Linksblock")[3], finde(pdf, "Rechtsblock")[3], delta=0.5)


class KopfbandTest(TestCase):
    def setUp(self):
        self.k = Kontext(patient=Patient(nachname="Muster", vorname="Erika"), heute=date(2026, 10, 14))

    def kopf(self, **mehr):
        return {"id": "k", "typ": "briefkopf", "kopfband": "welle", "bandfarbe": "#BDC9C2", "textfarbe": "#23272C",
                "bandhoehe_mm": 40, **mehr}

    def test_pruefung(self):
        self.assertEqual(pruefe_bloecke("eigen-x", [self.kopf(fussband=True, logo_rechts=True)]), [])
        for falsch, meldung in ((self.kopf(kopfband="zickzack"), "Form des Kopfbands"),
                                (self.kopf(bandfarbe="rot"), "Farbe des Bands"),
                                (self.kopf(bandhoehe_mm=200), "Höhe des Kopfbands"),
                                (self.kopf(band_seiten="jede"), "Kopfband auf"),
                                (self.kopf(briefpapier="rgc"), "nur eins")):
            self.assertTrue(any(meldung in f for f in pruefe_bloecke("eigen-x", [falsch])), meldung)

    def test_formen(self):
        for form in gestaltung.FORMEN:
            pfad = gestaltung.band_pfad(form, 210, 40, 10)
            zahlen = [float(z) for z in re.findall(r"-?[\d.]+", pfad)]
            self.assertLessEqual(max(zahlen[1::2]), 50, form)  # Kontrollpunkte höchstens einen Schwung tiefer
            self.assertTrue(pfad.startswith("M0 0 H210"), form)

    def test_band_auf_jeder_seite_und_text_darunter(self):
        b = [self.kopf(fussband=True), text("t", "Zeile\n" * 300),
             {"id": "f", "typ": "fusszeile", "text": "Fußzeile auf dem Band", "rechts": "{Seite}/{Seiten}"}]
        inhalt, fuss, rechts = bloecke_html("eigen-x", b, self.k)
        self.assertIn("position:fixed", inhalt)
        self.assertIn('class="fussband"', inhalt)
        pdf = html_zu_pdf(seite("x", inhalt, fuss, None, rechts))
        seiten = [s for s in pdf_text(pdf).split("\f") if s.strip()]
        self.assertGreater(len(seiten), 1)
        erste = [w for w in woerter(pdf) if w[1] == "Zeile"]
        # Text beginnt unter dem Band (40 mm + 6 mm Abstand) und endet über dem Fußband
        self.assertGreaterEqual(min(w[3] for w in erste), 45.5)
        self.assertLess(max(w[3] for w in erste), 297 - 18)
        self.assertEqual(len([w for w in woerter(pdf) if w[1] == "Fußzeile"]), len(seiten))

    def test_band_nur_erste_seite(self):
        b = [self.kopf(band_seiten="erste"), text("t", "Zeile\n" * 300)]
        pdf = html_zu_pdf(seite("x", bloecke_html("eigen-x", b, self.k)[0]))
        zeilen = [w for w in woerter(pdf) if w[1] == "Zeile"]
        self.assertGreaterEqual(min(w[3] for w in zeilen if w[0] == 1), 45.5)
        self.assertLess(min(w[3] for w in zeilen if w[0] == 2), 20)  # ab Seite 2 der normale Rand von 15 mm


class AnschriftfeldTest(TestCase):
    def setUp(self):
        self.k = Kontext(patient=Patient(nachname="Muster", vorname="Erika", strasse="Musterweg 5", plz="48143",
                                         ort="Münster"), heute=date(2026, 10, 14))
        self.feld = {"id": "din", "typ": "anschriftfeld", "form": "B",
                     "ruecksendung": "Stiftung · Rücksendestraße 1 · 48143 Münster",
                     "text": "{{Patient.Name}}\n{{Patient.Straße}}\n{{Patient.PLZ_Ort}}", "rechts": "Datum: {{Heute}}"}

    def test_pruefung(self):
        b = [{"id": "k", "typ": "briefkopf"}, self.feld, text("t", "Betreff")]
        self.assertEqual(pruefe_bloecke("patientenaufnahme", b), [])
        self.assertTrue(any("höchstens einmal" in f for f in pruefe_bloecke("patientenaufnahme", [*b, {**self.feld, "id": "x"}])))
        self.assertTrue(any("Form A oder B" in f for f in pruefe_bloecke("patientenaufnahme", [{**self.feld, "form": "C"}])))
        self.assertTrue(any("höchstens 6 Zeilen" in f for f in pruefe_bloecke(
            "patientenaufnahme", [{**self.feld, "text": "a\n" * 7}])))
        self.assertTrue(any("erste Seite" in f for f in pruefe_bloecke(
            "patientenaufnahme", [{"id": "u", "typ": "seitenumbruch"}, self.feld])))
        self.assertTrue(any("unbekanntes Datenfeld" in f for f in pruefe_bloecke(
            "patientenaufnahme", [{**self.feld, "rechts": "{{Gibtsnicht}}"}])))

    def test_lage_nach_din(self):
        for form, oben in (("B", 45), ("A", 27)):
            for kopf in ({"id": "k", "typ": "briefkopf", "falzmarken": True},
                         {"id": "k", "typ": "briefkopf", "kopfband": "bogen", "bandhoehe_mm": 30},
                         {"id": "k", "typ": "briefkopf", "briefpapier": "rgc"}):
                b = [kopf, {**self.feld, "form": form}, text("t", "Betreffzeile")]
                inhalt = bloecke_html("patientenaufnahme", b, self.k)[0]
                pdf = html_zu_pdf(seite("x", inhalt))
                _, _, x, y = finde(pdf, "Musterweg")
                name = f"Form {form}, {kopf}"
                self.assertAlmostEqual(x, 20, delta=1, msg=name)
                # zweite Zeile der Anschriftzone: 5 mm Rücksendeangabe + 12,7 mm Zusatzzone + eine Zeile (10 pt × 1,25)
                # + Oberlänge bis zur Oberkante der Buchstaben
                self.assertAlmostEqual(y, oben + 17.7 + 4.4 + 1.7, delta=1, msg=name)
                _, _, x, y = finde(pdf, "Rücksendestraße")
                self.assertGreater(y, oben)
                self.assertLess(y, oben + 5)
                _, _, x, y = finde(pdf, "Datum:")
                self.assertAlmostEqual(x, 125, delta=1, msg=name)
                # der Text des Dokuments beginnt unter dem Anschriftfeld
                self.assertGreater(finde(pdf, "Betreffzeile")[3], gestaltung.DIN[form]["text_ab"] - 1, name)
        # Briefpapier: die Angaben der ersten Seite entfallen, das Anschriftfeld übernimmt sie
        b = [{"id": "k", "typ": "briefkopf", "briefpapier": "rgc"}, self.feld]
        self.assertNotIn("Prof. Dr. Markus Masin", bloecke_html("patientenaufnahme", b, self.k)[0])

    def test_falzmarken_und_querformat(self):
        b = [{"id": "k", "typ": "briefkopf", "falzmarken": True}, self.feld]
        inhalt = bloecke_html("patientenaufnahme", b, self.k)[0]
        self.assertNotIn('class="falzmarke"', inhalt)  # die des Anschriftfelds ersetzen die des Briefkopfs
        self.assertEqual(inhalt.count('class="marke"'), 2)
        self.assertEqual(inhalt.count('class="marke loch"'), 1)
        quer = bloecke_html("patientenaufnahme", b, self.k, quer=True)[0]
        self.assertNotIn("din-bereich", quer)
        self.assertIn("Musterweg 5", quer)


class FusszeileTest(TestCase):
    """Fußzeile mit eigenem Band wie die Kopfzeile (14.10.2026)."""

    def test_eigenes_band(self):
        k = Kontext(patient=Patient(nachname="Muster", vorname="Erika"), heute=date(2026, 10, 14))
        fuss = {"id": "f", "typ": "fusszeile", "text": "{{Absender.Name}}\nVorstand: {{Absender.Vorstand}}",
                "rechts": "{Seite}/{Seiten}", "band": "bogen", "bandfarbe": "#251F53", "textfarbe": "#FFFFFF"}
        b = [{"id": "k", "typ": "briefkopf"}, text("t", "Inhalt"), fuss]
        self.assertEqual(pruefe_bloecke("eigen-x", b), [])
        self.assertTrue(any("Form des Bands" in f for f in pruefe_bloecke("eigen-x", [{**fuss, "band": "zacken"}])))
        self.assertTrue(any("Schriftfarbe" in f for f in pruefe_bloecke("eigen-x", [{**fuss, "textfarbe": "weiß"}])))
        inhalt, f, r = bloecke_html("eigen-x", b, k)
        self.assertIn('class="fussband"', inhalt)
        self.assertIn('fill="#251F53"', inhalt)
        self.assertIn("color: #FFFFFF", inhalt)
        pdf = html_zu_pdf(seite("x", inhalt, f, None, r))
        self.assertIn("Vorstand:", pdf_text(pdf))
        # ohne Band: kein Fußband
        self.assertNotIn('class="fussband"', bloecke_html("eigen-x", [*b[:2], {**fuss, "band": ""}], k)[0])


class BriefkopfTextTest(TestCase):
    """Eigener Absendertext im Briefkopf je Vorlage (18.11.2026)."""

    def test_eigener_text(self):
        k = Kontext(patient=Patient(nachname="Muster", vorname="Erika"), heute=date(2026, 11, 18))
        for kopf in ({"id": "k", "typ": "briefkopf"}, {"id": "k", "typ": "briefkopf", "kopfband": "welle"}):
            b = [{**kopf, "rechts": "Rīga, Brīvības iela 1\n<b>Tel.</b> +371 1234"}, text("t", "Inhalt")]
            self.assertEqual(pruefe_bloecke("patientenaufnahme", b), [])
            inhalt = bloecke_html("patientenaufnahme", b, k)[0]
            self.assertIn("Rīga, Brīvības iela 1<br>&lt;b&gt;Tel.&lt;/b&gt; +371 1234", inhalt)
            # ohne Absender: kein Text
            self.assertNotIn("Rīga", bloecke_html("patientenaufnahme", [{**b[0], "absender": False}, b[1]], k)[0])
        self.assertTrue(any("Absendertext höchstens 8 Zeilen" in f for f in pruefe_bloecke(
            "patientenaufnahme", [{"id": "k", "typ": "briefkopf", "rechts": "a\n" * 9}])))
        self.assertTrue(any("unbekanntes Datenfeld" in f for f in pruefe_bloecke(
            "patientenaufnahme", [{"id": "k", "typ": "briefkopf", "rechts": "{{Gibtsnicht}}"}])))
