"""KI (Experimentell): Eingangsqueue, Verarbeitung (echte Texterkennung + Modell-Attrappe), Dienst, Verknüpfung
Labor ↔ Infusionsplan, Datenschutz (Löschen) – gegen die echte Datenbank."""
import datetime as dt
import os
import shutil
from decimal import Decimal
from pathlib import Path
from unittest import mock, skipUnless
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.utils import timezone

from audit.models import SystemEreignis
from befunde.models import Laborbefund, Laborwert
from epm.pruefhilfen import GleicheSeiteEinmalErkennen, Grundlage
from infusionen.models import Infusionsplan
from ki import eingang, pipeline
from ki.models import KiFeld, KiHinweis, KiRohergebnis, KiVorgang
from ki.testhilfen import EXTRAKTION_LABOR, KI_TMP, Attrappe, dokument, labor_png
from ki.verknuepfung import fuer_patient
from patienten.models import Dokument
from stammdaten.models import Laborparameter

TESSERACT = shutil.which("tesseract") is not None
BERLIN = ZoneInfo("Europe/Berlin")


@override_settings(EPM_KI=Path(KI_TMP))
class EingangTest(Grundlage):
    def test_vormerken_nur_lesbare_offene_akten(self):
        gut = dokument(self.patient, b"%PDF-1.4 x", name="a.pdf", mime="application/pdf")
        dokument(self.patient, b"x", name="b.txt", mime="text/plain", titel="Notiz")
        eigen = dokument(self.patient, b"%PDF-1.4 y", name="c.pdf", mime="application/pdf", titel="Plan-PDF")
        Dokument.objects.filter(pk=eigen.pk).update(herkunft=Dokument.Herkunft.SYSTEM)
        weg = dokument(self.patient, b"%PDF-1.4 z", name="d.pdf", mime="application/pdf", ausgeblendet=True)
        self.assertEqual(eingang.vormerken(), 1)
        self.assertEqual(list(KiVorgang.objects.values_list("dokument_id", flat=True)), [gut.pk])
        v = KiVorgang.objects.get()
        self.assertEqual((v.status, v.prioritaet, v.sha256), ("neu", eingang.PRIORITAET_NEU, gut.sha256))
        self.assertEqual(eingang.vormerken(), 0)  # nicht doppelt
        self.assertNotIn(weg.pk, KiVorgang.objects.values_list("dokument_id", flat=True))

    def test_eingeschraenkte_und_abgeschlossene_akten_nicht(self):
        dokument(self.patient, b"%PDF-1.4 x", name="a.pdf", mime="application/pdf")
        type(self.patient).objects.filter(pk=self.patient.pk).update(eingeschraenkt_am=timezone.now())
        self.assertEqual(eingang.vormerken(), 0)

    def test_anfordern_mit_vorrang(self):
        d = dokument(self.patient, b"%PDF-1.4 x", name="a.pdf", mime="application/pdf")
        v = eingang.anfordern(d, self.mitarbeiter)
        self.assertEqual((v.prioritaet, v.angefordert_von), (eingang.PRIORITAET_ANGEFORDERT, self.mitarbeiter))
        KiVorgang.objects.filter(pk=v.pk).update(status="fehler", versuche=3)
        v = eingang.anfordern(d, self.mediziner)
        self.assertEqual((v.status, v.versuche, v.angefordert_von), ("neu", 0, self.mediziner))


@skipUnless(TESSERACT, "Tesseract fehlt")
@override_settings(EPM_KI=Path(KI_TMP))
class VerarbeitungTest(GleicheSeiteEinmalErkennen, Grundlage):
    def setUp(self):
        super().setUp()
        self.dok = dokument(self.patient, labor_png(nachname="Echt", vorname="Anna"))
        eingang.vormerken()
        self.v = KiVorgang.objects.get(dokument=self.dok)

    def test_mit_modell_vorschlaege_ohne_akte_zu_aendern(self):
        modell = Attrappe(extraktion={**EXTRAKTION_LABOR, "patient": {"name": "Echt, Anna"}})
        v = pipeline.verarbeiten(self.v, pipeline.Rahmen(client=modell))
        self.assertEqual(v.status, KiVorgang.Status.ZUR_PRUEFUNG)
        self.assertEqual(v.dokumenttyp, "labor")
        self.assertIn("vision", v.verfahren)
        self.assertEqual(v.seiten, 1)
        felder = {(f.gruppe, f.wert.get("parameter_name") or f.schluessel): f for f in v.felder.all()}
        kalium = felder[("labor", "Kalium")]
        self.assertEqual(kalium.wert["wert"], "3.2")
        self.assertEqual(kalium.wert["uhrzeit"], "06:10")
        self.assertEqual(kalium.wert["markierung"], "↓")
        self.assertEqual(kalium.quelle, "vision+regeln")
        self.assertTrue(kalium.belege["im_ocr_text"])
        # Werte, die nur die Regeln fanden (Magnesium, Albumin …), kommen dazu
        self.assertIn(("labor", "Magnesium"), felder)
        self.assertEqual(felder[("labor", "Magnesium")].quelle, "regeln")
        self.assertEqual(felder[("meta", "dokumentdatum")].wert["wert"], "2026-09-01")
        # Patient im Dokument passt zur Akte (Echt, Anna)
        self.assertTrue(felder[("meta", "patient")].wert["passt"])
        self.assertEqual(KiRohergebnis.objects.filter(vorgang=v, art="extraktion").count(), 1)
        self.assertEqual(modell.anfragen[-1]["schema"], True)
        # nichts in der Akte, Audit mit Modell und Prompt-Fassung
        self.assertFalse(Laborbefund.objects.exists())
        e = SystemEreignis.objects.get(art=SystemEreignis.Art.KI, details__aktion="verarbeitet")
        self.assertEqual(e.details["prompt_version"], v.prompt_version)
        self.assertEqual(e.benutzername, "ki-dienst")
        # Zwischendateien sind nach der Verarbeitung weg
        self.assertFalse((Path(KI_TMP) / "vorgaenge" / str(v.pk)).exists())

    def test_patient_im_dokument_passt_nicht(self):
        v = pipeline.verarbeiten(self.v, pipeline.Rahmen(client=Attrappe()))  # Attrappe liest „Muster, Erika“
        patient = v.felder.get(schluessel="patient")
        self.assertFalse(patient.wert["passt"])
        self.assertLess(patient.konfidenz, 0.5)

    def test_ohne_modell_nur_regeln(self):
        v = pipeline.verarbeiten(self.v, pipeline.Rahmen(client=None))
        self.assertEqual(v.status, KiVorgang.Status.ZUR_PRUEFUNG)
        self.assertIn("Kein KI-Modell", v.metadaten["hinweis"])
        labor = [f for f in v.felder.all() if f.gruppe == "labor"]
        self.assertTrue(labor)
        self.assertTrue(all(f.quelle == "regeln" for f in labor))
        self.assertEqual(v.dokumenttyp, "labor")

    def test_abbruch_und_fortsetzen_an_der_seite(self):
        aufrufe = {"n": 0}

        def abbrechen():
            aufrufe["n"] += 1
            return "Nachtfenster zu Ende" if aufrufe["n"] == 2 else None

        with self.assertRaises(pipeline.Abgebrochen):
            pipeline.verarbeiten(self.v, pipeline.Rahmen(client=Attrappe(), abbrechen=abbrechen))
        self.assertEqual(self.v.seiten_liste.count(), 1)  # Stufe 1 fertig, Bild verschlüsselt aufgehoben
        self.assertTrue(any((Path(KI_TMP) / "vorgaenge" / str(self.v.pk)).iterdir()))
        v = pipeline.verarbeiten(self.v, pipeline.Rahmen(client=Attrappe()))
        self.assertEqual(v.status, KiVorgang.Status.ZUR_PRUEFUNG)
        self.assertEqual(v.seiten_liste.count(), 1)

    def test_dokument_geaendert(self):
        KiVorgang.objects.filter(pk=self.v.pk).update(sha256="0" * 64)
        self.v.refresh_from_db()
        with self.assertRaises(ValueError):
            pipeline.verarbeiten(self.v, pipeline.Rahmen(client=None))

    @mock.patch.dict(os.environ, {"KI_HARDWARE_PRUEFEN": "0", "KI_MAX_CPU_PROZENT": "100"})
    def test_dienst_einmal_ohne_modell(self):
        from ki.management.commands.epm_ki import Dienst
        from ki.models import KiEinstellung

        KiEinstellung.laden()
        KiEinstellung.objects.filter(pk=1).update(max_cpu_prozent=100, min_ram_frei_mb=256, max_last_je_kern=10)
        with override_settings(EPM_KI_MODELL_URL=""):
            Dienst(einmal=True).laufen()
        self.v.refresh_from_db()
        self.assertEqual(self.v.status, KiVorgang.Status.ZUR_PRUEFUNG, self.v.fehler)
        from ki.dienst import stand_lesen

        stand = stand_lesen()
        self.assertFalse(stand["modell"]["eingerichtet"])


@override_settings(EPM_KI=Path(KI_TMP))
class DienstQueueTest(Grundlage):
    def test_angeforderte_zuerst_haengende_zurueck_fehler_nach_drei(self):
        from ki import dienst

        a = dokument(self.patient, b"%PDF-1.4 a", name="a.pdf", mime="application/pdf")
        b = dokument(self.patient, b"%PDF-1.4 b", name="b.pdf", mime="application/pdf")
        eingang.vormerken()
        eingang.anfordern(a, self.mitarbeiter)
        v = dienst.auftrag_holen(nur_angefordert=True, nachverarbeitung=False)
        self.assertEqual((v.dokument_id, v.status, v.versuche), (a.pk, "in_verarbeitung", 1))
        self.assertIsNone(dienst.auftrag_holen(nur_angefordert=True, nachverarbeitung=False))
        w = dienst.auftrag_holen(nur_angefordert=False, nachverarbeitung=False)
        self.assertEqual(w.dokument_id, b.pk)
        # ohne Lebenszeichen zurück in die Queue
        KiVorgang.objects.filter(pk=v.pk).update(lebenszeichen=timezone.now() - dt.timedelta(minutes=10))
        self.assertEqual(dienst.haengende_zuruecksetzen(), 1)
        v.refresh_from_db()
        self.assertEqual(v.status, "neu")
        # zurückstellen zählt nicht als Versuch; Fehler nach drei Versuchen endgültig
        dienst.zurueckstellen(w, "Pause")
        w.refresh_from_db()
        self.assertEqual((w.status, w.versuche), ("neu", 0))
        KiVorgang.objects.filter(pk=w.pk).update(versuche=3)
        dienst.fehlgeschlagen(w, "kaputt")
        w.refresh_from_db()
        self.assertEqual((w.status, w.fehler), ("fehler", "kaputt"))

    def test_nachverarbeitung_nur_mit_modell(self):
        from ki import dienst

        dokument(self.patient, b"%PDF-1.4 a", name="a.pdf", mime="application/pdf")
        eingang.vormerken()
        KiVorgang.objects.update(status="nachverarbeitung")
        self.assertIsNone(dienst.auftrag_holen(nur_angefordert=False, nachverarbeitung=False))
        self.assertIsNotNone(dienst.auftrag_holen(nur_angefordert=False, nachverarbeitung=True))

    def test_loeschen_des_dokuments_nimmt_ki_daten_mit(self):
        d = dokument(self.patient, b"%PDF-1.4 a", name="a.pdf", mime="application/pdf")
        eingang.vormerken()
        v = KiVorgang.objects.get()
        KiFeld.objects.create(vorgang=v, gruppe="labor", schluessel="laborwert", wert={"wert": "1"})
        Dokument.objects.filter(pk=d.pk).delete()
        self.assertFalse(KiVorgang.objects.exists())
        self.assertFalse(KiFeld.objects.exists())


class VerknuepfungTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.kalium = Laborparameter.objects.get(name="Kalium")

    def labor(self, tag, wert, uhr=None):
        b = Laborbefund.objects.create(patient=self.patient, abgenommen_am=tag, abgenommen_um=uhr)
        Laborwert.objects.create(befund=b, parameter=self.kalium, wert=Decimal(wert), einheit="mmol/l",
                                 referenz_von=Decimal("3.5"), referenz_bis=Decimal("5.1"))
        return b

    def plan(self, tag, kalium, vorgaenger=None):
        return Infusionsplan.objects.create(patient=self.patient, status=Infusionsplan.Status.ABGELOEST,
                                            gueltig_ab=tag, kalium_mmol=kalium, vorgaenger=vorgaenger,
                                            herkunft=Infusionsplan.Herkunft.ALTSYSTEM)

    def hinweise(self):
        fuer_patient(self.patient)
        return {h.art: h for h in KiHinweis.objects.filter(patient=self.patient)}

    def test_niedrig_substitution_normalisiert_gesichert(self):
        t = dt.date(2026, 3, 12)
        alt = self.plan(t - dt.timedelta(days=20), Decimal("20"))
        self.labor(t, "3.1", dt.time(6, 10))
        self.plan(t + dt.timedelta(days=1), Decimal("40"), vorgaenger=alt)
        self.labor(t + dt.timedelta(days=3), "4.0")
        h = self.hinweise()
        s = h[KiHinweis.Art.SUBSTITUTION]
        self.assertEqual(s.stufe, KiHinweis.Stufe.GESICHERT)
        self.assertEqual(s.text, "Kalium niedrig (3,1 mmol/l, 12.03.2026 06:10), anschließend Kaliumsubstitution "
                                 "dokumentiert (Infusionsplan ab 13.03.2026: 20 → 40 mmol).")
        self.assertIn("im Referenzbereich", h[KiHinweis.Art.NORMALISIERT].text)
        self.assertEqual(h[KiHinweis.Art.NORMALISIERT].stufe, KiHinweis.Stufe.GESICHERT)
        self.assertNotIn(KiHinweis.Art.KEINE_MASSNAHME, h)

    def test_weiterhin_niedrig_und_ohne_uhrzeit_wahrscheinlich(self):
        t = dt.date(2026, 3, 12)
        alt = self.plan(t - dt.timedelta(days=20), Decimal("20"))
        self.labor(t, "3.1")                         # ohne Uhrzeit
        self.plan(t, Decimal("40"), vorgaenger=alt)  # am selben Tag: Reihenfolge unklar
        self.labor(t + dt.timedelta(days=2), "3.3")
        h = self.hinweise()
        self.assertEqual(h[KiHinweis.Art.SUBSTITUTION].stufe, KiHinweis.Stufe.WAHRSCHEINLICH)
        self.assertIn("weiterhin niedrig (3,3 mmol/l", h[KiHinweis.Art.WEITERHIN].text)

    def test_keine_massnahme_im_zeitfenster(self):
        t = dt.date(2026, 3, 12)
        self.plan(t - dt.timedelta(days=20), Decimal("20"))
        self.labor(t - dt.timedelta(days=5), "3.2")
        self.labor(t, "3.0", dt.time(7, 0))
        self.labor(t, "3.1", dt.time(12, 0))  # Wiederholungsmessung am selben Tag
        self.plan(t + dt.timedelta(days=4), Decimal("40"))  # außerhalb von 48 h
        fuer_patient(self.patient)
        keine = KiHinweis.objects.filter(patient=self.patient, art=KiHinweis.Art.KEINE_MASSNAHME).order_by("zeitpunkt")
        self.assertEqual(keine.count(), 2)
        letzter = keine.last()
        self.assertEqual(letzter.text, "Kalium weiterhin niedrig (3 mmol/l, 12.03.2026 07:00), keine nachfolgende "
                                       "Kaliumsubstitution im erfassten Zeitraum erkannt.")
        self.assertEqual(len(letzter.belege["wiederholungen"]), 1)

    def test_ohne_infusionsplan_kein_hinweis_und_status_bleibt(self):
        self.labor(dt.date(2026, 3, 12), "3.0")
        self.assertEqual(self.hinweise(), {})
        self.plan(dt.date(2026, 3, 1), Decimal("20"))
        h = self.hinweise()[KiHinweis.Art.KEINE_MASSNAHME]
        h.status = KiHinweis.Status.AUSGEBLENDET
        h.save()
        fuer_patient(self.patient)
        h.refresh_from_db()
        self.assertEqual(h.status, KiHinweis.Status.AUSGEBLENDET)

    def test_ki_vorschlaege_hoechstens_wahrscheinlich(self):
        d = dokument(self.patient, b"%PDF-1.4 a", name="a.pdf", mime="application/pdf")
        v = KiVorgang.objects.create(dokument=d, patient=self.patient, sha256=d.sha256, status="zur_pruefung",
                                     metadaten={"dokumentdatum": "2026-03-12"})
        KiFeld.objects.create(vorgang=v, gruppe="labor", schluessel="laborwert", wert={
            "parameter": self.kalium.pk, "parameter_name": "Kalium", "wert": "3.1", "einheit": "mmol/l",
            "referenz_von": "3.5", "referenz_bis": "5.1", "datum": "2026-03-12", "uhrzeit": "06:10"})
        KiFeld.objects.create(vorgang=v, gruppe="infusion", schluessel="position", wert={
            "substanz": "KCl", "planfeld": "kalium_mmol", "menge": "40", "von": "2026-03-12", "uhrzeit": "08:00"})
        h = self.hinweise()[KiHinweis.Art.SUBSTITUTION]
        self.assertEqual(h.stufe, KiHinweis.Stufe.WAHRSCHEINLICH)
        self.assertEqual(h.belege["labor"][0]["quelle"], "ki")
        # verworfen → Hinweis verschwindet
        v.felder.update(status="verworfen")
        self.assertEqual(self.hinweise(), {})
