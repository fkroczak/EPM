"""„Text erkennen“ an Dokumenten der Akte (F170) und „Werte übernehmen“ aus einem Dokument (F171).

- ``EchtesOcrmypdfTest`` ruft das echte OCRmyPDF (mit Ghostscript und Tesseract) auf. Ohne die Programme wird er
  übersprungen – in GitHub Actions und im Image sind sie Pflicht (``EPM_OCRMYPDF_PFLICHT=1``).
- ``TextErkennenTest`` prüft Auftrag, Ersetzen, Fehlerfälle, Rechte und Löschung. Das externe Programm OCRmyPDF wird
  dort durch ``_ocrmypdf_ersatz`` vertreten, der eine PDF mit Textebene schreibt (wie OCRmyPDF es tut).
- ``WerteUebernehmenTest`` läuft vollständig mit der echten Erkennung von „Scans“.
"""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from accounts.models import Rolle
from audit.models import SystemEreignis
from befunde.models import BiaMessung, Laborbefund
from epm.pruefhilfen import GleicheSeiteEinmalErkennen, Grundlage, benutzer, client_fuer
from patienten.models import Dokument, DokumentText, Patient

from . import dienst, dokumente, testbilder
from .models import DokumentErkennung, Scan

TMP = Path(tempfile.mkdtemp(prefix="epm-akte-ocr-"))


def _pdf_mit_text(text: str, seiten: int = 1) -> bytes:
    """PDF mit Textebene (wie die Ausgabe von OCRmyPDF)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    puffer = io.BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    for _ in range(seiten):
        y = 780
        for zeile in text.splitlines():
            c.drawString(60, y, zeile)
            y -= 16
        c.showPage()
    c.save()
    return puffer.getvalue()


def _ocrmypdf_ersatz(rueckgabe=0, text="Labor\nKalium 3,4 mmol/l\nAlbumin 34 g/l", aufrufe=None):
    """Vertritt das externe Programm: schreibt die Ausgabedatei (letztes Argument) und meldet ``rueckgabe``."""
    def lauf(befehl, **kw):
        if aufrufe is not None:
            aufrufe.append((befehl, kw))
        if rueckgabe in (0, 10):
            Path(befehl[-1]).write_bytes(_pdf_mit_text(text, 2))
        return subprocess.CompletedProcess(befehl, rueckgabe, stdout="", stderr="" if rueckgabe in (0, 10) else
                                           "ERROR: Something went wrong")
    return lauf


@override_settings(EPM_DOKUMENTE=TMP / "dokumente", EPM_SCANS=TMP / "scans",
                   EPM_LOESCHLISTE=TMP / "loeschliste.jsonl")
class Basis(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.testpatient = Patient.objects.create(nachname="Muster", vorname="Erika", ist_test=True,
                                                 geburtsdatum="1961-03-14")

    def hochladen(self, inhalt: bytes, name: str, patient=None, client=None) -> Dokument:
        c = client or client_fuer(self.mitarbeiter)
        r = c.post("/api/dokumente/", {"patient": (patient or self.patient).id, "titel": "Befund",
                                       "datei": SimpleUploadedFile(name, inhalt)}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        return Dokument.objects.get(pk=r.json()["id"])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)


class TextErkennenTest(Basis):
    def anfordern(self, dok, client=None):
        c = client or client_fuer(self.mitarbeiter)
        return c.post(f"/api/dokumente/{dok.id}/text-erkennen/")

    def ausfuehren(self, ersatz):
        # on_commit (alte Datei löschen) wie im Betrieb ausführen
        with mock.patch.object(dokumente.subprocess, "run", side_effect=ersatz), \
                self.captureOnCommitCallbacks(execute=True):
            a = dokumente.auftrag_holen()
            self.assertIsNotNone(a)
            return dokumente.ausfuehren(a)

    def test_ersetzt_datei_durch_pdf_mit_text(self):
        dok = self.hochladen(testbilder.png(testbilder.seite(testbilder.LABOR)), "befund.png")
        alt_pfad, alt_sha = dok.pfad, dok.sha256
        r = self.anfordern(dok)
        self.assertEqual(r.status_code, 202, r.content)
        self.assertEqual(r.json()["erkennung"]["status"], "wartet")
        # ein zweites Anfordern legt keinen zweiten Auftrag an
        self.anfordern(dok)
        self.assertEqual(DokumentErkennung.objects.filter(dokument=dok).count(), 1)
        aufrufe = []
        a = self.ausfuehren(_ocrmypdf_ersatz(aufrufe=aufrufe))
        self.assertEqual(a.status, DokumentErkennung.Status.FERTIG, a.fehler)
        befehl = aufrufe[0][0]
        self.assertEqual(befehl[0], "ocrmypdf")
        for teil in ("--skip-text", "--rotate-pages", "--image-dpi"):
            self.assertIn(teil, befehl)
        self.assertEqual(befehl[befehl.index("--output-type") + 1], "pdfa")
        dok.refresh_from_db()
        self.assertEqual(dok.mime, "application/pdf")
        self.assertEqual(dok.originalname, "befund.pdf")
        self.assertNotEqual(dok.sha256, alt_sha)
        self.assertTrue(dok.pfad.is_file())
        self.assertFalse(alt_pfad.exists())
        self.assertEqual(dok.titel, "Befund")  # Titel, Typ, Datum bleiben
        self.assertIn("Kalium", DokumentText.objects.get(dokument=dok).text)
        self.assertEqual(a.seiten, 2)
        e = SystemEreignis.objects.get(art=SystemEreignis.Art.DOKUMENT_TEXT_ERKANNT)
        self.assertEqual(e.details["sha256_vorher"], alt_sha)
        self.assertEqual(e.details["sha256"], dok.sha256)
        self.assertEqual(e.benutzer, self.mitarbeiter)
        self.assertEqual(dok.history.first().history_change_reason,
                         "Text erkannt: Datei durch dieselbe PDF mit Textebene ersetzt")
        # in der Akte: Text vorhanden, Suche findet ihn
        c = client_fuer(self.mitarbeiter)
        d = c.get(f"/api/dokumente/{dok.id}/").json()
        self.assertTrue(d["hat_text"])
        self.assertEqual(d["erkennung"]["status"], "fertig")
        treffer = c.get(f"/api/dokumente/?patient={self.patient.id}&search=Albumin").json()
        self.assertEqual([x["id"] for x in treffer.get("results", treffer)], [dok.id])

    def test_pdfa_nicht_moeglich_bleibt_gueltige_pdf(self):
        dok = self.hochladen(testbilder.pdf(testbilder.seite(testbilder.LABOR)), "scan.pdf")
        self.anfordern(dok)
        a = self.ausfuehren(_ocrmypdf_ersatz(rueckgabe=10))
        self.assertEqual(a.status, DokumentErkennung.Status.FERTIG)
        self.assertIn("PDF/A", a.schritt)

    def test_fehler_lassen_das_dokument_unveraendert(self):
        dok = self.hochladen(testbilder.pdf(testbilder.seite(testbilder.LABOR)), "scan.pdf")
        sha, pfad = dok.sha256, dok.pfad
        vorher = set(pfad.parent.iterdir())
        for rueckgabe, erwartet in [(8, "verschlüsselt"), (4, "keine lesbare PDF"), (99, "Fehler 99")]:
            self.anfordern(dok)
            a = self.ausfuehren(_ocrmypdf_ersatz(rueckgabe=rueckgabe))
            self.assertEqual(a.status, DokumentErkennung.Status.FEHLER)
            self.assertIn(erwartet, a.fehler)
        # kein Text erkannt
        self.anfordern(dok)
        a = self.ausfuehren(_ocrmypdf_ersatz(text=""))
        self.assertIn("kein Text", a.fehler)
        dok.refresh_from_db()
        self.assertEqual((dok.sha256, dok.pfad), (sha, pfad))
        self.assertTrue(pfad.is_file())
        self.assertFalse(DokumentText.objects.filter(dokument=dok).exists())
        # keine verwaisten Dateien neben dem Original
        self.assertEqual(set(pfad.parent.iterdir()), vorher)

    def test_inzwischen_geaenderte_datei_und_abgeschlossene_akte(self):
        dok = self.hochladen(testbilder.pdf(testbilder.seite(testbilder.LABOR)), "scan.pdf")
        self.anfordern(dok)
        Dokument.objects.filter(pk=dok.pk).update(sha256="0" * 64)
        a = self.ausfuehren(_ocrmypdf_ersatz())
        self.assertIn("inzwischen geändert", a.fehler)
        Dokument.objects.filter(pk=dok.pk).update(sha256=a.sha256_vorher)
        self.anfordern(dok)
        Patient.objects.filter(pk=self.patient.pk).update(abgeschlossen_am=timezone.localdate(),
                                                          abschluss_anlass="therapie_beendet")
        a = self.ausfuehren(_ocrmypdf_ersatz())
        self.assertIn("abgeschlossen", a.fehler)
        dok.refresh_from_db()
        self.assertEqual(dok.sha256, a.sha256_vorher)
        self.assertTrue(dok.pfad.is_file())

    def test_nicht_moeglich_und_rechte(self):
        txt = self.hochladen(b"nur Text", "notiz.txt")
        r = self.anfordern(txt)
        self.assertEqual(r.status_code, 400)
        self.assertIn("PDF, JPG, PNG und TIFF", r.json()["fehler"])
        self.assertFalse(client_fuer(self.mitarbeiter).get(f"/api/dokumente/{txt.id}/").json()["text_erkennbar"]["moeglich"])
        dok = self.hochladen(testbilder.pdf(testbilder.seite(testbilder.LABOR)), "scan.pdf")
        self.assertEqual(self.anfordern(dok, client_fuer(self.betrachter)).status_code, 403)
        # Admins schreiben echte Akten nicht
        self.assertEqual(self.anfordern(dok, client_fuer(self.admin)).status_code, 403)

    def test_abbruch_und_geplantes_beenden(self):
        from datetime import timedelta

        dok = self.hochladen(testbilder.pdf(testbilder.seite(testbilder.LABOR)), "scan.pdf")
        self.anfordern(dok)
        a = dokumente.auftrag_holen()
        dokumente.geplant_beendet(a)
        a.refresh_from_db()
        self.assertEqual((a.status, a.versuche), ("wartet", 0))
        for _ in range(dokumente.MAX_VERSUCHE):
            a = dokumente.auftrag_holen()
            DokumentErkennung.objects.filter(pk=a.pk).update(lebenszeichen=timezone.now() - timedelta(minutes=5))
            dienst.haengende_zuruecksetzen()
        a.refresh_from_db()
        self.assertEqual(a.status, "fehler")
        self.assertIn("mehrfach abgebrochen", a.fehler)

    def test_loeschen_nach_art17_erfasst_auch_die_fruehere_fassung(self):
        """Nach „Text erkennen“ hat das Dokument eine neue Prüfsumme. Wird es gelöscht und danach eine Sicherung von
        vorher zurückgespielt, muss das Nachholen der Löschung es auch mit der alten Prüfsumme finden."""
        from patienten.loeschung import trage_ein
        from patienten.management.commands.epm_loeschungen_nachholen import nachholen

        dok = self.hochladen(testbilder.pdf(testbilder.seite(testbilder.LABOR)), "scan.pdf")
        alt_sha = dok.sha256
        self.anfordern(dok)
        self.ausfuehren(_ocrmypdf_ersatz())
        dok.refresh_from_db()
        neu_sha = dok.sha256
        fruehere = sorted({x for x in dok.history.values_list("sha256", flat=True) if x and x != neu_sha})
        self.assertEqual(fruehere, [alt_sha])
        # Stand der älteren Sicherung: Dokument mit der alten Prüfsumme; die Löschliste kennt die Löschung danach
        Dokument.objects.filter(pk=dok.pk).update(sha256=alt_sha)
        trage_ein({"dokument": dok.id, "sha256": neu_sha, "datei": dok.datei, "patient": self.patient.id,
                   "person": self.mediziner.id, "geloescht_am": timezone.now().isoformat(timespec="seconds"),
                   "fruehere_sha256": fruehere})
        ergebnis = nachholen()
        self.assertEqual(ergebnis["dokumente"], 1)
        self.assertFalse(Dokument.objects.filter(pk=dok.pk).exists())
        # Titel auch in der Historie der früheren Fassung geschwärzt
        from patienten.loeschung import PLATZHALTER

        self.assertEqual(set(Dokument.history.filter(id=dok.id).values_list("titel", flat=True)), {PLATZHALTER})


class EchtesOcrmypdfTest(Basis):
    """Mit dem echten OCRmyPDF: Seite ohne Text → PDF/A mit Textebene, Text gefunden, Seitenzahl gleich."""

    def setUp(self):
        ok, text = dokumente.verfuegbar()
        if not ok:
            if os.environ.get("EPM_OCRMYPDF_PFLICHT") == "1":
                self.fail(f"OCRmyPDF muss bereitstehen: {text}")
            raise unittest.SkipTest(f"OCRmyPDF nicht vorhanden ({text})")

    def test_echte_erkennung(self):
        import pypdfium2 as pdfium

        dok = self.hochladen(testbilder.pdf(testbilder.seite(testbilder.LABOR), testbilder.seite(testbilder.BRIEF)),
                             "zwei.pdf")
        client_fuer(self.mitarbeiter).post(f"/api/dokumente/{dok.id}/text-erkennen/")
        a = dokumente.ausfuehren(dokumente.auftrag_holen())
        self.assertEqual(a.status, "fertig", a.fehler)
        dok.refresh_from_db()
        text = DokumentText.objects.get(dokument=dok).text
        self.assertIn("Kalium", text)
        self.assertIn("Kurzdarm", text)
        self.assertEqual(len(pdfium.PdfDocument(dok.pfad.read_bytes())), 2)
        self.assertEqual(a.seiten, 2)


class WerteUebernehmenTest(GleicheSeiteEinmalErkennen, Basis):
    def test_werte_aus_akte_dokument_ohne_neues_dokument(self):
        c = client_fuer(self.mitarbeiter)
        dok = self.hochladen(testbilder.png(testbilder.seite(testbilder.LABOR), verkleinern=0.67), "labor.png",
                             patient=self.testpatient)
        r = c.post(f"/api/dokumente/{dok.id}/werte-uebernehmen/")
        self.assertEqual(r.status_code, 201, r.content)
        scan_id = r.json()["scan"]
        # noch einmal: derselbe Scan
        self.assertEqual(c.post(f"/api/dokumente/{dok.id}/werte-uebernehmen/").json()["scan"], scan_id)
        while (s := dienst.auftrag_holen()) is not None:
            dienst.bearbeiten(s)
        d = c.get(f"/api/scans/{scan_id}/").json()
        self.assertEqual(d["status"], "fertig", d.get("fehler"))
        self.assertEqual(d["quelle"]["dokument"], dok.id)
        self.assertEqual(d["quelle"]["patient"]["id"], self.testpatient.id)
        werte = [w for w in d["auswertung"]["labor"]["werte"] if w["vorschlag"]]
        labor = {"abgenommen_am": "2026-09-01", "labor": "Labor Dr. Beispiel",
                 "werte": [{"parameter": w["parameter"], "wert": w["wert"], "einheit": w["einheit"]} for w in werte]}
        # nichts gewählt / falscher Patient
        self.assertEqual(c.post(f"/api/scans/{scan_id}/zuordnen/", {"patient": self.testpatient.id},
                                format="json").status_code, 400)
        r = c.post(f"/api/scans/{scan_id}/zuordnen/", {"patient": self.patient.id, "labor": labor}, format="json")
        self.assertEqual(r.status_code, 400)
        anzahl = Dokument.objects.count()
        r = c.post(f"/api/scans/{scan_id}/zuordnen/", {"labor": labor}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Dokument.objects.count(), anzahl)  # kein neues Dokument
        befund = Laborbefund.objects.get(pk=r.json()["laborbefund"])
        self.assertEqual(befund.dokument_id, dok.id)
        self.assertEqual(befund.patient_id, self.testpatient.id)
        self.assertGreaterEqual(befund.werte.count(), 5)
        self.assertIn("Kalium", DokumentText.objects.get(dokument=dok).text)
        self.assertFalse(Scan.objects.filter(pk=scan_id).exists())
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.SCAN, details__aktion="werte_uebernommen").get()
        self.assertEqual(e.details["dokument"], dok.id)

    def test_arbeitskopie_nur_fuer_wer_die_akte_sieht(self):
        dok = self.hochladen(testbilder.png(testbilder.seite(testbilder.LABOR), verkleinern=0.67), "labor.png")
        r = client_fuer(self.mitarbeiter).post(f"/api/dokumente/{dok.id}/werte-uebernehmen/")
        scan_id = r.json()["scan"]
        self.assertEqual(client_fuer(self.betrachter).post(f"/api/dokumente/{dok.id}/werte-uebernehmen/").status_code,
                         403)
        # Einschränkung (Art. 18): Arbeitskopie für andere nicht mehr sichtbar
        with mock.patch("epm.api_basis.patienten_fuer", return_value=Patient.objects.none()):
            self.assertFalse(dienst.sichtbare_scans(self.mediziner).filter(pk=scan_id).exists())
        self.assertTrue(dienst.sichtbare_scans(self.mediziner).filter(pk=scan_id).exists())


class SparmodusEinDurchgangTest(SimpleTestCase):
    def test_ein_tesseract_durchgang_mit_pp_ocr_im_sparmodus(self):
        from .ocr import erkennung, laden, tesseract

        class PaddleSparsam:
            sparsam, uvdoc = True, None

            def erkennen(self, bild, det_max=None):
                return []

        roh = laden.seiten_laden(testbilder.png(testbilder.seite(testbilder.LABOR), verkleinern=0.67), 5)[1][0]
        echt = tesseract.erkennen
        laeufe = []

        def zaehlen(*a, **k):
            laeufe.append(1)
            return echt(*a, **k)

        with mock.patch.object(tesseract, "erkennen", side_effect=zaehlen):
            auf, daten = erkennung.seite_erkennen(roh, {}, paddle=PaddleSparsam())
        self.assertEqual(len(laeufe), 1)
        self.assertTrue(auf.info["tesseract_einmal"])
        self.assertIn("Kalium", erkennung.fusion.text_aus_json(daten))
        laeufe.clear()
        with mock.patch.object(tesseract, "erkennen", side_effect=zaehlen):
            erkennung.seite_erkennen(roh, {}, paddle=None)
        self.assertEqual(len(laeufe), 2)  # ohne PP-OCR: beide Durchgänge für den Abgleich
