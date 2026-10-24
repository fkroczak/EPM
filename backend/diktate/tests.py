"""Diktate: Hochladen, Rechte, Abschrift (mit Ersatz für das Modell), Übernehmen, Löschen der Aufnahme bei der
Freigabe, Aufräumen, Text aus den Ansagen. Mit Sprachmodell (EPM_OCR_MODELLE) zusätzlich eine echte Abschrift."""
import io
import math
import os
import shutil
import struct
import tempfile
import unittest
import wave
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from accounts.models import Rolle
from accounts.rechte import STANDARD
from audit.models import SystemEreignis
from berichte.models import Bericht
from epm.pruefhilfen import Grundlage, client_fuer
from patienten.models import Diagnose

from . import abschrift, dienst
from .models import Begriffsliste, Diktat


def wav_bytes(sekunden=1.0, rate=16000) -> bytes:
    puffer = io.BytesIO()
    with wave.open(puffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                               for i in range(int(sekunden * rate))))
    return puffer.getvalue()


def webm_bytes(sekunden=1.0) -> bytes:
    """Wie aus dem Browser (MediaRecorder): WebM mit Opus, 48 kHz."""
    import av
    import numpy as np

    puffer = io.BytesIO()
    with av.open(puffer, "w", format="webm") as ziel:
        spur = ziel.add_stream("libopus", rate=48000, layout="mono")
        werte = (np.sin(2 * np.pi * 440 * np.arange(int(48000 * sekunden)) / 48000) * 8000).astype(np.int16)
        frame = av.AudioFrame.from_ndarray(werte.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = 48000
        for paket in spur.encode(frame):
            ziel.mux(paket)
        for paket in spur.encode(None):
            ziel.mux(paket)
    return puffer.getvalue()


class ErsatzAbschreiber:
    """Statt des Modells: feste Wörter (mit führendem Leerzeichen wie whisper)."""

    def __init__(self, woerter=None):
        self.woerter = woerter or [[" Sehr", 0, 300, 0.95], [" geehrte", 300, 700, 0.9], [" Kollegin", 700, 1200, 0.3],
                                   [" neuer", 1300, 1500, 0.9], [" Absatz", 1500, 1800, 0.9],
                                   [" die", 1900, 2000, 0.9], [" Patientin", 2000, 2500, 0.9], [".", 2500, 2550, 0.9]]
        self.vorlagen = []

    def abschreiben(self, audio, vorlage="", abbrechen=lambda: False, fortschritt=None):
        self.vorlagen.append(vorlage)
        if fortschritt:
            fortschritt(0.5)
        return self.woerter


class MitAblage(Grundlage):
    def setUp(self):
        super().setUp()
        self.ablage = Path(tempfile.mkdtemp(prefix="epm-diktat-test-"))
        self.addCleanup(shutil.rmtree, self.ablage, ignore_errors=True)
        einstellung = override_settings(EPM_SCANS=self.ablage)
        einstellung.enable()
        self.addCleanup(einstellung.disable)

    def bericht(self, **extra):
        return Bericht.objects.create(patient=self.patient, titel="Arztbrief", erstellt_von=self.mediziner, **extra)

    def hochladen(self, client=None, bericht=None, zweck="bericht", **extra):
        c = client or client_fuer(self.mediziner)
        daten = {"patient": self.patient.id, "zweck": zweck, "dauer_s": "1.0", "wann": "sofort",
                 "uebergabe": "selbst",
                 "datei": SimpleUploadedFile("diktat.webm", extra.pop("inhalt", None) or webm_bytes(),
                                             content_type=extra.pop("mime", "audio/webm;codecs=opus")), **extra}
        if bericht is not None:
            daten["bericht"] = bericht.id
        return c.post("/api/diktate/", daten, format="multipart")


class DiktatApiTest(MitAblage):
    def test_mediziner_diktiert_mitarbeiter_nicht(self):
        b = self.bericht()
        r = self.hochladen(bericht=b)
        self.assertEqual(r.status_code, 201, r.content)
        d = Diktat.objects.get(pk=r.json()["id"])
        self.assertEqual(d.status, "wartet")
        self.assertTrue(d.pfad.is_file())
        self.assertEqual(d.mime, "audio/webm")
        self.assertEqual(oct(d.pfad.stat().st_mode & 0o777), "0o640")
        self.assertTrue(SystemEreignis.objects.filter(art="diktat", details__aktion="aufgenommen").exists())
        r = self.hochladen(client=client_fuer(self.mitarbeiter), bericht=b)
        self.assertEqual(r.status_code, 403, r.content)
        self.assertIn("diktieren", STANDARD[Rolle.MEDIZINER])
        self.assertNotIn("diktieren", STANDARD[Rolle.MITARBEITER])

    def test_pruefungen_beim_hochladen(self):
        b = self.bericht()
        self.assertEqual(self.hochladen().status_code, 400)  # Bericht fehlt
        self.assertEqual(self.hochladen(bericht=b, mime="application/pdf").status_code, 400)
        self.assertEqual(self.hochladen(bericht=b, inhalt=b"x" * 50).status_code, 400)
        self.assertEqual(self.hochladen(bericht=b, dauer_s="7200").status_code, 400)
        Bericht.objects.filter(pk=b.pk).update(status="freigegeben")
        self.assertEqual(self.hochladen(bericht=b).status_code, 400)
        self.assertEqual(Diktat.objects.count(), 0)
        self.assertEqual(list(self.ablage.glob("diktate/*")), [])
        # Kommentar zum Infusionsplan: ohne Bericht
        self.assertEqual(self.hochladen(zweck="plan").status_code, 201)

    def test_abschrift_uebernehmen_und_sekretariat(self):
        b = self.bericht()
        r = self.hochladen(bericht=b, uebergabe="sekretariat")
        d = Diktat.objects.get(pk=r.json()["id"])
        Begriffsliste.objects.create(benutzer=self.mediziner, begriffe="Teduglutid\nKurzdarmsyndrom")
        auftrag = dienst.auftrag_holen()
        self.assertEqual(auftrag.pk, d.pk)
        ersatz = ErsatzAbschreiber()
        zeichen = []
        fertig = dienst.abschreiben(auftrag, ersatz, lebenszeichen=lambda: zeichen.append(1))
        self.assertEqual(zeichen, [1])
        self.assertEqual(fertig.status, "fertig", fertig.fehler)
        self.assertEqual(fertig.text, "<p>Sehr geehrte Kollegin</p><p>Die Patientin.</p>")
        self.assertIn("Teduglutid", ersatz.vorlagen[0])
        self.assertIn("Anna Echt", ersatz.vorlagen[0])
        sekretariat = client_fuer(self.mitarbeiter)
        offen = sekretariat.get("/api/diktate/offen/").json()
        self.assertEqual([x["id"] for x in offen], [d.pk])
        self.assertNotIn("woerter", offen[0])
        self.assertEqual(sekretariat.get("/api/diktate/stand/").json()["offen"], 1)
        voll = sekretariat.get(f"/api/diktate/{d.pk}/").json()
        self.assertEqual(voll["unsicher"], 1)
        self.assertEqual(sekretariat.get(f"/api/diktate/{d.pk}/audio/").status_code, 200)
        r = sekretariat.post(f"/api/diktate/{d.pk}/uebernommen/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()["uebernommen_am"])
        self.assertTrue(r.json()["audio"])  # zum Nachhören bis zur Freigabe
        self.assertEqual(sekretariat.get("/api/diktate/offen/").json(), [])

    def test_freigabe_wartet_auf_abschrift_und_loescht_aufnahme(self):
        b = self.bericht(inhalt="<p>Text</p>")
        d = Diktat.objects.get(pk=self.hochladen(bericht=b).json()["id"])
        pfad = d.pfad
        r = client_fuer(self.mediziner).post(f"/api/berichte/{b.pk}/freigeben/")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("noch abgeschrieben", r.content.decode())
        dienst.abschreiben(dienst.auftrag_holen(), ErsatzAbschreiber())
        with self.captureOnCommitCallbacks(execute=True):
            r = client_fuer(self.mediziner).post(f"/api/berichte/{b.pk}/freigeben/")
        self.assertEqual(r.status_code, 200, r.content)
        d.refresh_from_db()
        self.assertEqual((d.datei, d.text, d.woerter), ("", "", []))
        self.assertIsNotNone(d.audio_geloescht_am)
        self.assertFalse(pfad.exists())

    def test_jeder_mit_freigaberecht_gibt_frei(self):
        """Wie bei Infusionsplänen: nicht nur, wer diktiert hat."""
        from accounts.models import User

        zweiter = User.objects.create_user("zweiter", password="x", rolle=Rolle.MEDIZINER, muss_kennwort_aendern=False)
        b = self.bericht(inhalt="<p>Text</p>")
        self.assertEqual(self.hochladen(bericht=b).status_code, 201)
        dienst.abschreiben(dienst.auftrag_holen(), ErsatzAbschreiber())
        r = client_fuer(zweiter).post(f"/api/berichte/{b.pk}/freigeben/")
        self.assertEqual(r.status_code, 200, r.content)

    def test_kommentar_aufnahme_weg_nach_uebernahme(self):
        d = Diktat.objects.get(pk=self.hochladen(zweck="plan").json()["id"])
        pfad = d.pfad
        dienst.abschreiben(dienst.auftrag_holen(), ErsatzAbschreiber())
        with self.captureOnCommitCallbacks(execute=True):
            r = client_fuer(self.mediziner).post(f"/api/diktate/{d.pk}/uebernommen/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()["audio"])
        self.assertFalse(pfad.exists())

    def test_verwerfen_des_berichts_loescht_aufnahme(self):
        b = self.bericht()
        d = Diktat.objects.get(pk=self.hochladen(bericht=b).json()["id"])
        pfad = d.pfad
        with self.captureOnCommitCallbacks(execute=True):
            r = client_fuer(self.mitarbeiter).delete(f"/api/berichte/{b.pk}/")
        self.assertEqual(r.status_code, 204, r.content)
        self.assertFalse(Diktat.objects.exists())
        self.assertFalse(pfad.exists())

    def test_fehler_und_erneut(self):
        b = self.bericht()
        d = Diktat.objects.get(pk=self.hochladen(bericht=b, inhalt=b"kein Ton " * 100).json()["id"])
        d = dienst.abschreiben(dienst.auftrag_holen(), abschrift.Abschreiber())
        self.assertEqual(d.status, "fehler")
        self.assertIn("ließ sich nicht lesen", d.fehler)
        r = client_fuer(self.mitarbeiter).post(f"/api/diktate/{d.pk}/erneut/")
        self.assertEqual(r.json()["status"], "wartet")

    def test_nachts_nur_im_nachtfenster(self):
        b = self.bericht()
        self.hochladen(bericht=b, wann="nachts")
        self.assertIsNone(dienst.auftrag_holen())
        self.assertIsNotNone(dienst.auftrag_holen(nachts=True))
        nacht = timezone.localtime(timezone.now()).replace(hour=23)
        with mock.patch.dict(os.environ, {"EPM_DIKTAT_NACHT": "21-7"}):
            self.assertFalse(dienst.nachtfenster(nacht.replace(hour=12)))
            self.assertTrue(dienst.nachtfenster(nacht))
            self.assertTrue(dienst.nachtfenster(nacht.replace(hour=3)))

    def test_haengende_zurueck(self):
        b = self.bericht()
        self.hochladen(bericht=b)
        d = dienst.auftrag_holen()
        Diktat.objects.filter(pk=d.pk).update(lebenszeichen=timezone.now() - timedelta(minutes=5))
        self.assertEqual(dienst.haengende_zuruecksetzen(), 1)
        self.assertEqual(Diktat.objects.get(pk=d.pk).status, "wartet")

    def test_aufraeumen(self):
        d = Diktat.objects.get(pk=self.hochladen(zweck="plan").json()["id"])
        rest = self.ablage / "diktate" / "rest.webm"
        rest.write_bytes(b"x")
        os.utime(rest, (0, 0))
        Diktat.objects.filter(pk=d.pk).update(erstellt_am=timezone.now() - timedelta(days=4))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(dienst.bereinigen(), 2)
        self.assertFalse(Diktat.objects.exists())
        self.assertFalse(rest.exists())

    def test_eigene_begriffe(self):
        c = client_fuer(self.mediziner)
        self.assertEqual(c.get("/api/diktate/begriffe/").json(), {"begriffe": ""})
        r = c.put("/api/diktate/begriffe/", {"begriffe": "Teduglutid"}, format="json")
        self.assertEqual(r.json(), {"begriffe": "Teduglutid"})

    def test_vorlage_mit_diagnosen(self):
        Diagnose.objects.create(patient=self.patient, bezeichnung="Kurzdarmsyndrom", icd_code="K91.2")
        text = abschrift.vorlage(self.patient, "Teduglutid, Revestive")
        self.assertTrue(text.startswith("Ärztliches Diktat"))
        self.assertLess(text.index("Teduglutid"), text.index("Kurzdarmsyndrom"))
        self.assertLessEqual(len(text), abschrift.VORLAGE_MAX + 1)


class BereitschaftTest(SimpleTestCase):
    def test_zu_wenig_speicher(self):
        with tempfile.NamedTemporaryFile() as f, mock.patch.dict(os.environ, {"EPM_DIKTAT_MODELL": f.name}), \
                mock.patch.object(abschrift, "speichergrenze", return_value=1536 * 1024 ** 2):
            bereit, grund = abschrift.bereitschaft()
        self.assertFalse(bereit)
        self.assertIn("EPM_OCR_SPEICHER=3g", grund)
        with tempfile.NamedTemporaryFile() as f, mock.patch.dict(os.environ, {"EPM_DIKTAT_MODELL": f.name}), \
                mock.patch.object(abschrift, "speichergrenze", return_value=None):
            self.assertEqual(abschrift.bereitschaft(), (True, ""))

    def test_stand_ohne_dienst(self):
        with mock.patch("scans.dienst.dienst_stand", return_value=None), \
                mock.patch.object(Diktat.objects, "filter") as f:
            f.return_value.count.return_value = 0
            aus = dienst.stand()
        self.assertEqual((aus["bereit"], aus["grund"]), (False, "Der Erkennungsdienst läuft gerade nicht."))


class AudioTest(SimpleTestCase):
    def test_webm_und_wav(self):
        with tempfile.TemporaryDirectory() as ordner:
            for name, daten, sekunden in (("a.webm", webm_bytes(2.0), 2.0), ("a.wav", wav_bytes(1.0, 44100), 1.0)):
                pfad = Path(ordner) / name
                pfad.write_bytes(daten)
                audio = abschrift.audio_laden(pfad)
                self.assertAlmostEqual(len(audio) / 16000, sekunden, delta=0.1)
                self.assertLessEqual(float(abs(audio).max()), 1.0)


class TextTest(SimpleTestCase):
    def test_ansagen(self):
        self.assertEqual(abschrift.als_html("sehr geehrte Frau Kollegin, neuer Absatz. vielen Dank Doppelpunkt "
                                            "Befund Klammer auf alt Klammer zu neue Zeile gut."),
                         "<p>Sehr geehrte Frau Kollegin</p><p>Vielen Dank: Befund (alt)<br>Gut.</p>")

    def test_doppelpunkt_vor_absatz(self):
        self.assertEqual(abschrift.als_html("sehr geehrter Herr Kollege Doppelpunkt neuer Absatz wir berichten."),
                         "<p>Sehr geehrter Herr Kollege:</p><p>Wir berichten.</p>")

    def test_punkt_bleibt_wort(self):
        self.assertEqual(abschrift.als_html("Ein wichtiger Punkt ist <das> Gewicht."),
                         "<p>Ein wichtiger Punkt ist &lt;das&gt; Gewicht.</p>")

    def test_unsichere(self):
        self.assertEqual(abschrift.unsichere([[" a", 0, 1, 0.2], [" b", 1, 2, 0.9]]), 1)


@unittest.skipUnless(abschrift.modell_bereit(), "Sprachmodell für Diktate nicht vorhanden")
class EchteAbschriftTest(SimpleTestCase):
    def test_modell_laedt_und_schreibt_ab(self):
        """Ein Ton ohne Sprache: das Modell läuft durch und liefert Wörter im erwarteten Format (oder keine)."""
        with tempfile.TemporaryDirectory() as ordner:
            pfad = Path(ordner) / "ton.wav"
            pfad.write_bytes(wav_bytes(2.0))
            woerter = abschrift.Abschreiber().abschreiben(abschrift.audio_laden(pfad), "Ärztliches Diktat.")
        for w in woerter:
            self.assertEqual(len(w), 4)
            self.assertIsInstance(w[0], str)
            self.assertLessEqual(w[1], w[2])
            self.assertTrue(0 <= w[3] <= 1)
