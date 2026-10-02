"""Gemeinsame Daten für die Tests des Imports: erfundener Beispiel-Dump und ein Bestand wie nach ``epm_musterdaten``.

Alle Namen sind frei erfunden. Der Dump liegt als Datei vor, weil ihn auch der Browsertest hochlädt.
"""
from pathlib import Path

BEISPIEL = Path(__file__).resolve().parent / "testdaten" / "beispiel-dump.sql"

GRENZEN = {"gewicht_min_kg": "20", "gewicht_max_kg": "250", "groesse_min_cm": "100", "groesse_max_cm": "230",
           "kcal_min_tag": 0, "kcal_max_tag": 5000, "glucose_min_g": 0, "glucose_max_g": 1000,
           "aminosaeuren_min_g": 0, "aminosaeuren_max_g": 300, "lipide_min_g": 0, "lipide_max_g": 200,
           "natrium_min_mmol": 0, "natrium_max_mmol": 500, "kalium_min_mmol": 0, "kalium_max_mmol": 300,
           "volumen_min_ml": 0, "volumen_max_ml": 9000}


def bestand() -> dict:
    """Bestand des EPM, wie ihn ``dienst.bestand()`` aus der Datenbank liest – hier fest vorgegeben."""
    praeparate = [
        ("basisloesung", "Sterofundin", ""), ("basisloesung", "NaCl", "0,9 %"), ("aminosaeuren", "Glamin", "13,4 %"),
        ("lipide", "Clinoleic", "20 %"), ("spurenelemente", "Addel N", ""), ("vitamine", "Soluvit N", ""),
        ("vitamine", "Vitalipid adult", ""), ("vitamine", "Cernevit", ""), ("katheterschutz", "Taurolin", "2 %"),
        ("albumin", "Humanalbumin", "20 %"), ("glucose", "Glucose", "70 %"), ("aminosaeuren", "Aminoplasmal", "10 %"),
        ("lipide", "SMOF-Lipid", ""), ("lipide", "Lipovenös MCT", "20 %"), ("lipide", "Lipovenös MCT", "10 %"),
    ]
    return {
        "benutzer": [{"id": 1, "username": "e.beispiel", "vorname": "Eva", "nachname": "Beispiel", "ist_test": False},
                     {"id": 2, "username": "admin", "vorname": "", "nachname": "Admin", "ist_test": False},
                     {"id": 3, "username": "test", "vorname": "Tessa", "nachname": "Test", "ist_test": True}],
        "versorger": [], "ansprechpartner": [],
        "katheter": [{"id": 10, "wert": "Port"}, {"id": 11, "wert": "ZVK"}],
        "praeparate": [{"id": i, "kategorie": k, "name": n, "konzentration": c}
                       for i, (k, n, c) in enumerate(praeparate, 1)],
        "grenzen": dict(GRENZEN), "testnummer_ab": 9001,
    }


def entscheidungen() -> dict:
    """Zuordnungen, mit denen der Beispiel-Dump ohne offene Punkte übernommen werden kann."""
    return {
        "werte": {"nickel": {"vielleicht": "unbekannt"}},
        "praeparate": {
            "lipide": {"clinoleik 20%": {"art": "praeparat", "id": 4}},
            "medikamente": {"heparin 100 i.e. nach bedarf": {"art": "neu", "name": "Heparin", "konzentration": "",
                                                             "kategorie": "medikament"}},
        },
        "geloeschte": {"4": {"art": "abgeschlossen", "anlass": "therapie_beendet"}},
        "korrekturen": {"patienten:3:geburtsdatum": {"art": "wert", "wert": "1988-07-21", "alt": "0000-00-00"}},
    }
