"""Aufteilung der Tests auf mehrere CI-Rechner (epm/testlauf.py): keine Klasse fehlt, keine läuft doppelt."""
from django.test import SimpleTestCase

from epm.testlauf import aufteilen, teil_lesen, testzeiten


class AufteilenTest(SimpleTestCase):
    def test_jede_klasse_genau_einmal(self):
        klassen = {f"app.tests.K{i}": i % 7 + 1 for i in range(50)}
        zeiten = {"app.tests.K3": 60.0, "app.tests.K9": 30.0}
        for anzahl in (1, 2, 3, 4, 7):
            with self.subTest(anzahl=anzahl):
                teile = aufteilen(klassen, anzahl, zeiten)
                self.assertEqual(len(teile), anzahl)
                alle = [k for t in teile for k in t]
                self.assertEqual(sorted(alle), sorted(klassen))
                self.assertEqual(len(alle), len(set(alle)))

    def test_gleichmaessig_nach_zeit(self):
        klassen = {"a.A": 1, "a.B": 1, "a.C": 1, "a.D": 1}
        zeiten = {"a.A": 100.0, "a.B": 60.0, "a.C": 50.0, "a.D": 10.0}
        teile = aufteilen(klassen, 2, zeiten)
        self.assertEqual(sorted(sorted(t) for t in teile), [["a.A", "a.D"], ["a.B", "a.C"]])

    def test_gleiches_ergebnis_unabhaengig_von_der_reihenfolge(self):
        klassen = {f"app.tests.K{i}": 3 for i in range(20)}
        umgekehrt = dict(reversed(list(klassen.items())))
        self.assertEqual(aufteilen(klassen, 3, {}), aufteilen(umgekehrt, 3, {}))

    def test_teil_lesen(self):
        self.assertIsNone(teil_lesen(""))
        self.assertEqual(teil_lesen("2/3"), (2, 3))
        for falsch in ("0/3", "4/3", "x", "1-2"):
            with self.subTest(falsch), self.assertRaises(ValueError):
                teil_lesen(falsch)

    def test_gemessene_zeiten_vorhanden(self):
        zeiten = testzeiten()
        self.assertGreater(len(zeiten), 50)
        self.assertIn("epm.test_sicherheit.FirmenTrennung", zeiten)
