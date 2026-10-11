"""Musterdaten mit Befunden (Wunsch 11.10.2026): Die Testpatienten bringen Diagnosen mit ICD-Code, Laborbefunde und
BIA-Messungen mit – je Profil verschieden, damit Reiter, Hinweise und Plan-Editor ohne Handarbeit zu prüfen sind."""
from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from befunde.models import BiaMessung, Laborbefund, Laborwert
from epm.pruefhilfen import Grundlage, client_fuer
from infusionen.models import Infusionsplan
from stammdaten.models import Diagnosevorlage

from .kennzahlen import kennzahlen
from .models import Diagnose, Gewichtsmessung, Patient
from .testdaten import TEST_BIA, TEST_DIAGNOSEN, TEST_LABOR, TESTPATIENTEN, testdaten_zuruecksetzen, testpatienten_anlegen


def testpatient(nachname) -> Patient:
    return Patient.objects.get(ist_test=True, nachname=nachname)


def labor_stand():
    """Alle Laborwerte der Testpatienten in fester Reihenfolge – zum Vergleich zweier Durchläufe."""
    return list(Laborwert.objects.filter(befund__patient__ist_test=True)
                .order_by("befund__patient__nachname", "befund__abgenommen_am", "reihenfolge")
                .values_list("befund__patient__nachname", "befund__abgenommen_am", "parameter__name",
                             "freitext_name", "wert", "wert_text"))


class TestdatenBefunde(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        testpatienten_anlegen()

    def test_anzahl_je_profil(self):
        """Diagnosen, Labor und BIA wie festgelegt; Profil „neu“ (Test, Hanna) ohne Labor und BIA."""
        for i, eintrag in enumerate(TESTPATIENTEN):
            p = testpatient(eintrag[0])
            with self.subTest(eintrag[0]):
                self.assertEqual(p.diagnosen.count(), len(TEST_DIAGNOSEN[i]))
                self.assertEqual(p.laborbefunde.count(), len(TEST_LABOR[i]["tage"]) if i in TEST_LABOR else 0)
                self.assertEqual(p.bia_messungen.count(), len(TEST_BIA.get(i, [])))
        hanna = testpatient("Test")
        self.assertEqual((hanna.laborbefunde.count(), hanna.bia_messungen.count()), (0, 0))
        self.assertTrue(hanna.diagnosen.exists())
        # mehrere Zeitpunkte, damit es einen Verlauf gibt
        erika = testpatient("Musterfrau")
        self.assertEqual(erika.laborbefunde.values("abgenommen_am").distinct().count(), 4)
        self.assertEqual(erika.bia_messungen.values("gemessen_am").distinct().count(), 3)
        # beendete Diagnose mit Datum (nicht gelöscht) – „beendete anzeigen“ hat etwas zu zeigen
        beendet = Diagnose.objects.get(patient=testpatient("Mustermann"), aktiv=False)
        self.assertEqual((beendet.icd_code, beendet.beendet_am), ("T82.7", timezone.localdate() - timedelta(days=200)))
        # die abgeschlossene Akte hat ihre Befunde aus der Zeit vor dem Abschluss
        karl = testpatient("Demo")
        self.assertIsNotNone(karl.abgeschlossen_am)
        self.assertEqual((karl.laborbefunde.count(), karl.bia_messungen.count()), (2, 1))

    def test_regeln_wie_ueber_die_api(self):
        """Dieselben Prüfungen wie über die API: ICD-Format, Datum nicht in der Zukunft, BIA plausibel; die Liste
        unter Vorlagen › Diagnosen wächst mit (U53)."""
        heute = timezone.localdate()
        for d in Diagnose.objects.filter(patient__ist_test=True):
            d.full_clean()
        for b in Laborbefund.objects.filter(patient__ist_test=True):
            b.full_clean()
            self.assertLessEqual(b.abgenommen_am, heute)
        for w in Laborwert.objects.filter(befund__patient__ist_test=True):
            w.full_clean()
            if w.parameter_id:
                self.assertTrue(w.parameter.aktiv)
                self.assertEqual(w.einheit, w.parameter.einheit)
        for m in BiaMessung.objects.filter(patient__ist_test=True):
            m.full_clean()
            self.assertLessEqual(m.fettmasse_kg, m.gewicht_kg)
            # das Gewicht kommt aus dem Verlauf und wird nicht noch einmal eingetragen
            self.assertIsNone(m.gewichtsmessung_id)
            self.assertTrue(Gewichtsmessung.objects.filter(patient=m.patient, gewicht_kg=m.gewicht_kg).exists())
        self.assertTrue(Diagnosevorlage.objects.filter(icd_code="K91.2", bezeichnung="Kurzdarmsyndrom").exists())
        self.assertEqual(Diagnosevorlage.objects.filter(icd_code="K91.2", bezeichnung="Kurzdarmsyndrom").count(), 1)
        self.assertTrue(Laborwert.objects.filter(befund__patient__ist_test=True, parameter__isnull=True,
                                                 wert__isnull=True, wert_text="> 500").exists())

    def test_werte_ausserhalb_der_referenz(self):
        werte = Laborwert.objects.filter(befund__patient__ist_test=True)
        richtungen = {(w.befund.patient.nachname, w.bezeichnung, w.befund.abgenommen_am): w.ausserhalb
                      for w in werte.select_related("befund__patient", "parameter")}
        heute = timezone.localdate()
        self.assertEqual(richtungen[("Musterfrau", "Magnesium", heute)], "niedrig")
        self.assertEqual(richtungen[("Musterfrau", "Ferritin", heute)], "niedrig")
        self.assertEqual(richtungen[("Mustermann", "CRP", heute)], "hoch")
        self.assertEqual(richtungen[("Mustermann", "Kalium", heute)], "niedrig")
        self.assertEqual(richtungen[("Probe", "Triglyceride", heute - timedelta(days=20))], "hoch")
        # nur die bewusst gesetzten Werte weichen ab – alle übrigen liegen in der Referenz
        abweichend = {(n, b) for (n, b, _), r in richtungen.items() if r}
        erwartet = {(TESTPATIENTEN[i][0], name) for i, d in TEST_LABOR.items() for name in d["abweichend"]}
        self.assertTrue(abweichend <= erwartet, abweichend - erwartet)
        self.assertGreaterEqual(len(abweichend), 8)
        # Akte ohne abweichende Werte
        self.assertFalse(any(r for (n, _, _), r in richtungen.items() if n == "Demo"))

    def test_hinweise_in_den_kennzahlen(self):
        """„Kein Laborbefund“/„Keine BIA-Messung“ (Test, Hanna), „Labor älter als 12 Mon.“ (Beispiel, Paula),
        „BIA älter als 12 Mon.“ (Probe, Jonas); die übrigen ohne Befund-Hinweis."""
        werte = kennzahlen(Patient.objects.filter(ist_test=True))
        hinweise = {p.nachname: {h["art"]: h["text"] for h in werte[p.id]["hinweise"] if h["art"] in ("labor", "bia")}
                    for p in Patient.objects.filter(ist_test=True)}
        self.assertEqual(hinweise["Test"], {"labor": "Kein Laborbefund", "bia": "Keine BIA-Messung"})
        self.assertEqual(hinweise["Beispiel"], {"labor": "Labor älter als 12 Mon."})
        self.assertEqual(hinweise["Probe"], {"bia": "BIA älter als 12 Mon."})
        for name in ("Musterfrau", "Mustermann", "Demo"):
            self.assertEqual(hinweise[name], {}, name)
        erika = testpatient("Musterfrau")
        self.assertEqual(werte[erika.id]["labor"], {"am": timezone.localdate(), "alt": False})
        # Startseite des Testzugangs: „Labor fällig“ und „BIA fällig“ je zweimal
        tester = User.objects.get(username="test")
        tester.muss_kennwort_aendern = False  # Einmal-Kennwort gilt hier als bereits ersetzt
        pruefen = client_fuer(tester).get("/api/startseite/").json()["pruefen"]
        self.assertEqual((pruefen["labor_faellig"], pruefen["bia_faellig"]), (2, 2))

    def test_akten_apis_liefern_die_daten(self):
        c = client_fuer(self.mediziner)
        erika, max_, hanna = testpatient("Musterfrau"), testpatient("Mustermann"), testpatient("Test")
        diagnosen = c.get(f"/api/diagnosen/?patient={erika.id}").json()
        diagnosen = diagnosen["results"] if isinstance(diagnosen, dict) else diagnosen
        self.assertIn("Kurzdarmsyndrom [K91.2G]", [d["anzeige"] for d in diagnosen])
        self.assertIn("Störung des Magnesiumstoffwechsels [E83.4V]", [d["anzeige"] for d in diagnosen])
        befunde = c.get(f"/api/laborbefunde/?patient={erika.id}").json()
        self.assertEqual(len(befunde), 4)
        neuester = befunde[0]
        self.assertEqual(neuester["abgenommen_am"], timezone.localdate().isoformat())
        mg = next(w for w in neuester["werte"] if w["bezeichnung"] == "Magnesium")
        self.assertEqual((mg["anzeige_wert"], mg["einheit"], mg["ausserhalb"]), ("0,58", "mmol/l", "niedrig"))
        self.assertEqual(mg["gruppe"], "elektrolyte")
        verlauf = c.get(f"/api/laborbefunde/verlauf/?patient={erika.id}&parameter={mg['parameter']}").json()
        self.assertEqual([p["wert"] for p in verlauf["punkte"]], [0.84, 0.79, 0.71, 0.58])
        bia = c.get(f"/api/bia-messungen/?patient={max_.id}").json()
        self.assertEqual(len(bia), 3)
        # Verlauf beim Profil „abnahme“: BCM fällt, ECW steigt
        self.assertLess(bia[0]["bcm_kg"], bia[-1]["bcm_kg"])
        self.assertGreater(bia[0]["ecw_prozent"], bia[-1]["ecw_prozent"])
        self.assertIsNotNone(bia[0]["bmi_berechnet"])
        self.assertEqual(c.get(f"/api/laborbefunde/?patient={hanna.id}").json(), [])
        self.assertEqual(c.get(f"/api/bia-messungen/?patient={hanna.id}").json(), [])
        # der Testzugang sieht dasselbe
        tester = User.objects.get(username="test")
        tester.muss_kennwort_aendern = False  # Einmal-Kennwort gilt hier als bereits ersetzt
        self.assertEqual(len(client_fuer(tester).get(f"/api/laborbefunde/?patient={erika.id}").json()), 4)

    def test_hinweise_im_plan_editor(self):
        """Magnesium unter der Referenz mit fallendem Verlauf im Entwurf von Musterfrau (F187); ohne Labor der Hinweis
        „Noch kein Laborbefund“."""
        from infusionen.hinweise import hinweise

        erika = testpatient("Musterfrau")
        entwurf = Infusionsplan.objects.get(patient=erika, status=Infusionsplan.Status.ENTWURF)
        liste = hinweise(erika, entwurf)["hinweise"]
        mg = next(h for h in liste if h["art"] == "labor" and h["parameter"] == "Magnesium")
        self.assertEqual((mg["richtung"], mg["trend"]), ("niedrig", "fallend"))
        self.assertEqual([str(v["wert"]) for v in mg["verlauf"]], ["0.7900", "0.7100", "0.5800"])
        self.assertFalse(any(h["art"] == "labor_alt" for h in liste))
        self.assertIn("labor", {h["art"] for h in hinweise(testpatient("Mustermann"))["hinweise"]})
        ohne = hinweise(testpatient("Test"))["hinweise"]
        self.assertTrue(any(h["art"] == "labor_alt" and h["text"].startswith("Noch kein Laborbefund") for h in ohne))
        alt = hinweise(testpatient("Beispiel"))["hinweise"]
        self.assertTrue(any(h["art"] == "labor_alt" and h["text"].startswith("Laborwerte älter als 12 Monate") for h in alt))

    def test_zuruecksetzen_legt_alles_gleich_wieder_an(self):
        """Zurücksetzen entfernt die Befunde mit den Akten und legt sie neu an – mit denselben Werten."""
        vorher = labor_stand()
        alte_befunde = list(Laborbefund.objects.filter(patient__ist_test=True).values_list("id", flat=True))
        zahlen = (Diagnose.objects.filter(patient__ist_test=True).count(),
                  Laborbefund.objects.filter(patient__ist_test=True).count(),
                  BiaMessung.objects.filter(patient__ist_test=True).count())
        katalog = Diagnosevorlage.objects.count()
        self.assertEqual(testdaten_zuruecksetzen(), {"geloescht": 6, "angelegt": 6})
        self.assertFalse(Laborbefund.objects.filter(id__in=alte_befunde).exists())
        self.assertFalse(Laborwert.objects.filter(befund_id__in=alte_befunde).exists())
        self.assertEqual((Diagnose.objects.filter(patient__ist_test=True).count(),
                          Laborbefund.objects.filter(patient__ist_test=True).count(),
                          BiaMessung.objects.filter(patient__ist_test=True).count()), zahlen)
        self.assertEqual(zahlen, (sum(map(len, TEST_DIAGNOSEN.values())), sum(len(d["tage"]) for d in TEST_LABOR.values()),
                                  sum(map(len, TEST_BIA.values()))))
        self.assertEqual(labor_stand(), vorher)
        # die Liste unter Vorlagen › Diagnosen bekommt keine doppelten Einträge
        self.assertEqual(Diagnosevorlage.objects.count(), katalog)
