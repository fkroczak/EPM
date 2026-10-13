"""Fehlertexte der API (epm/fehlertexte.py): kurz, freundlich, überall gleich."""
from epm.pruefhilfen import Grundlage, client_fuer


class FehlertexteTest(Grundlage):
    def test_pflichtfeld_leer_und_laenge(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/patienten/", {"vorname": "", "email": "nicht-gueltig", "nachname": "x" * 101}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        f = r.json()
        self.assertEqual(f["geburtsdatum"], ["Bitte ausfüllen."])
        self.assertEqual(f["vorname"], ["Bitte ausfüllen."])
        self.assertEqual(f["email"], ["Bitte eine gültige E-Mail-Adresse angeben."])
        self.assertEqual(f["nachname"], ["Höchstens 100 Zeichen."])

    def test_datum_zahl_auswahl_und_verweis(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/patienten/", {"nachname": "A", "vorname": "B", "geburtsdatum": "31.12.1970",
                                       "geschlecht": "x", "versorger": 999999, "groesse_cm": "abc"}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        f = r.json()
        self.assertEqual(f["geburtsdatum"], ["Bitte als TT.MM.JJJJ angeben."])
        self.assertEqual(f["geschlecht"], ["„x“ steht nicht zur Auswahl."])
        self.assertEqual(f["versorger"], ["Eintrag 999999 gibt es nicht (mehr)."])
        self.assertEqual(f["groesse_cm"], ["Bitte eine Zahl angeben."])
        r = c.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "viel", "gemessen_am": "2026-01-01"}, format="json")
        self.assertEqual(r.json()["gewicht_kg"], ["Bitte eine Zahl angeben."])
