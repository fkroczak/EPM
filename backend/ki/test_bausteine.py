"""KI (Experimentell): Zeitfenster und Ressourcenschutz, Regelprüfung, Modell-Client (offline), Verschlüsselung,
Pseudonymisierung – ohne Datenbankbezug, wo es geht."""
import datetime as dt
import os
import socket
import time
from decimal import Decimal
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, TestCase, override_settings

from ki import krypto, pruefung
from ki.modell import Client, ModellFehler, NichtErlaubt, pruefe_adresse
from ki.pseudonym import pseudonymisieren
from ki.steuerung import Last, Steuerung, im_fenster, ist_wochenende
from ki.testhilfen import KI_TMP, ModellServer

BERLIN = ZoneInfo("Europe/Berlin")


class Einst:
    """Einstellungen ohne Datenbank (wie ``KiEinstellung``)."""

    def __init__(self, **k):
        self.aktiv = True
        self.nacht_beginn, self.nacht_ende, self.zeitzone = dt.time(21), dt.time(7), "Europe/Berlin"
        self.worker_nacht, self.worker_tag = 2, 0
        self.max_cpu_prozent, self.min_ram_frei_mb, self.max_last_je_kern = 80, 1536, 1.5
        self.pause_bei_sicherung = True
        self.__dict__.update(k)

    @staticmethod
    def worker_max():
        return 4


def last(**k) -> Last:
    werte = {"cpu_prozent": 20.0, "ram_frei_mb": 12000, "ram_gesamt_mb": 32000, "last1": 1.0, "kerne": 8}
    werte.update(k)
    return Last(**werte)


@mock.patch.dict(os.environ, {"KI_HARDWARE_PRUEFEN": "1", "KI_MIN_RAM_GB": "12", "KI_MIN_KERNE": "4"})
class SteuerungTest(SimpleTestCase):
    def zeit(self, h, m=0, tag=14, monat=10):
        return dt.datetime(2026, monat, tag, h, m, tzinfo=BERLIN)

    def test_zeitfenster_ueber_mitternacht_und_zeitumstellung(self):
        b, e = dt.time(21), dt.time(7)
        self.assertTrue(im_fenster(self.zeit(21), b, e))
        self.assertTrue(im_fenster(self.zeit(3), b, e))
        self.assertFalse(im_fenster(self.zeit(7), b, e))
        self.assertFalse(im_fenster(self.zeit(12), b, e))
        # Fenster innerhalb eines Tages und „rund um die Uhr“
        self.assertTrue(im_fenster(self.zeit(2), dt.time(1), dt.time(5)))
        self.assertFalse(im_fenster(self.zeit(6), dt.time(1), dt.time(5)))
        self.assertTrue(im_fenster(self.zeit(12), dt.time(0), dt.time(0)))
        # UTC-Zeitpunkt: 20:30 UTC im Oktober (Sommerzeit) = 22:30 Berlin, im Dezember = 21:30
        self.assertTrue(im_fenster(dt.datetime(2026, 10, 14, 20, 30, tzinfo=dt.UTC), b, e))
        self.assertFalse(im_fenster(dt.datetime(2026, 10, 14, 18, 30, tzinfo=dt.UTC), b, e))
        self.assertTrue(im_fenster(dt.datetime(2026, 12, 14, 20, 30, tzinfo=dt.UTC), b, e))

    def test_wochenende(self):
        self.assertTrue(ist_wochenende(dt.datetime(2026, 10, 17, 12, tzinfo=BERLIN)))   # Samstag
        self.assertTrue(ist_wochenende(dt.datetime(2026, 10, 19, 5, tzinfo=BERLIN)))    # Montag früh
        self.assertFalse(ist_wochenende(dt.datetime(2026, 10, 19, 8, tzinfo=BERLIN)))

    def test_nachts_parallel_tagsueber_nur_angefordert(self):
        s = Steuerung()
        e = s.entscheiden(Einst(), last(), self.zeit(23))
        self.assertEqual((e.modus, e.parallel, e.nur_angefordert), ("nacht", 2, False))
        e = s.entscheiden(Einst(), last(), self.zeit(10))
        self.assertEqual((e.modus, e.parallel, e.nur_angefordert), ("tag", 1, True))
        e = s.entscheiden(Einst(worker_tag=2), last(), self.zeit(10))
        self.assertEqual((e.parallel, e.nur_angefordert), (2, False))
        # Obergrenze KI_WORKER_MAX
        self.assertEqual(s.entscheiden(Einst(worker_nacht=9), last(), self.zeit(23)).parallel, 4)

    def test_server_zu_klein_bleibt_aus(self):
        e = Steuerung().entscheiden(Einst(), last(ram_gesamt_mb=4096, kerne=2), self.zeit(23))
        self.assertEqual((e.modus, e.parallel), ("aus", 0))
        self.assertIn("zu klein", e.grund)
        with mock.patch.dict(os.environ, {"KI_HARDWARE_PRUEFEN": "0"}):
            self.assertEqual(Steuerung().entscheiden(Einst(), last(ram_gesamt_mb=4096, kerne=2),
                                                     self.zeit(23)).modus, "nacht")

    def test_aus_und_sicherung(self):
        self.assertEqual(Steuerung().entscheiden(Einst(aktiv=False), last(), self.zeit(23)).modus, "aus")
        e = Steuerung().entscheiden(Einst(), last(sicherung_laeuft=True), self.zeit(2))
        self.assertEqual((e.modus, e.grund), ("pause", "Die Sicherung läuft."))
        self.assertEqual(Steuerung().entscheiden(Einst(pause_bei_sicherung=False), last(sicherung_laeuft=True),
                                                 self.zeit(2)).modus, "nacht")

    def test_last_pause_hysterese_und_sparsam(self):
        s = Steuerung()
        e = s.entscheiden(Einst(), last(ram_frei_mb=1000), self.zeit(23))
        self.assertEqual(e.modus, "pause")
        self.assertIn("freier Speicher", e.grund)
        # knapp über der Grenze: noch Pause (Hysterese: Grenze + 512 MB)
        self.assertEqual(s.entscheiden(Einst(), last(ram_frei_mb=1800), self.zeit(23)).modus, "pause")
        # deutlich darüber: weiter, aber sparsam (unter dem 1,5-Fachen)
        e = s.entscheiden(Einst(), last(ram_frei_mb=2200), self.zeit(23))
        self.assertEqual((e.modus, e.parallel, e.sparsam), ("nacht", 1, True))
        e = s.entscheiden(Einst(), last(cpu_prozent=95), self.zeit(23))
        self.assertEqual(e.modus, "pause")
        self.assertEqual(s.entscheiden(Einst(), last(cpu_prozent=70), self.zeit(23)).modus, "pause")  # < 80-15 nötig
        self.assertEqual(s.entscheiden(Einst(), last(cpu_prozent=40), self.zeit(23)).modus, "nacht")
        self.assertEqual(s.entscheiden(Einst(), last(last1=20, kerne=8), self.zeit(23)).modus, "pause")

    def test_scans_haben_vorrang(self):
        e = Steuerung().entscheiden(Einst(), last(), self.zeit(10), scans_warten=True)
        self.assertEqual(e.modus, "pause")
        e = Steuerung().entscheiden(Einst(), last(), self.zeit(23), scans_warten=True)
        self.assertEqual((e.modus, e.parallel), ("nacht", 1))

    def test_sicherung_an_der_marke_erkannt(self):
        from ki.steuerung import Messung

        with override_settings(EPM_SYSTEM=Path(KI_TMP) / "system"):
            status = Path(KI_TMP) / "system" / "status"
            status.mkdir(parents=True, exist_ok=True)
            marke = status / "backup-laeuft"
            marke.touch()
            self.assertTrue(Messung().messen().sicherung_laeuft)
            alt = time.time() - 7 * 3600
            os.utime(marke, (alt, alt))
            self.assertFalse(Messung().messen().sicherung_laeuft)
            marke.unlink()


class PruefungTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from patienten.testdaten import stammdaten_anlegen

        stammdaten_anlegen()

    def test_zahlen_bereiche_daten(self):
        self.assertEqual(pruefung.dezimal("3,2 L"), Decimal("3.2"))
        self.assertEqual(pruefung.dezimal("< 0,5"), Decimal("0.5"))
        self.assertIsNone(pruefung.dezimal("negativ"))
        self.assertEqual(pruefung.referenz("3,5 - 5,1"), (Decimal("3.5"), Decimal("5.1")))
        self.assertEqual(pruefung.referenz("< 5"), (None, Decimal("5")))
        self.assertEqual(pruefung.referenz("> 60"), (Decimal("60"), None))
        self.assertEqual(pruefung.datum("2026-03-12"), dt.date(2026, 3, 12))
        self.assertEqual(pruefung.datum("12.03.2026"), dt.date(2026, 3, 12))
        self.assertIsNone(pruefung.datum("2999-01-01"))
        self.assertEqual(pruefung.uhrzeit("06:10 Uhr"), dt.time(6, 10))
        self.assertIsNone(pruefung.uhrzeit("25:00"))

    def test_laborwert_belegt_und_gegengeprueft(self):
        k = pruefung.Katalog()
        text = "Kalium 3,2 L mmol/l 3,5 - 5,1"
        erg = pruefung.laborwert({"parameter": "Kalium", "wert": "3,2", "einheit": "mmol/l", "referenz": "3,5 - 5,1"},
                                 k, ocr_text=text, seite=1, seite_konfidenz=0.95,
                                 regeln=[{"parameter": erg_id(k, "Kalium"), "wert": "3.2"}])
        self.assertEqual(erg["wert"]["parameter_name"], "Kalium")
        self.assertEqual(erg["wert"]["wert"], "3.2")
        self.assertEqual(erg["wert"]["markierung"], "↓")
        self.assertEqual(erg["quelle"], "vision+regeln")
        self.assertGreaterEqual(erg["konfidenz"], 0.9)
        self.assertTrue(erg["belege"]["im_ocr_text"])

    def test_laborwert_unplausibel_und_nicht_belegt(self):
        k = pruefung.Katalog()
        erg = pruefung.laborwert({"parameter": "Kalium", "wert": "32", "einheit": "mmol/l"}, k,
                                 ocr_text="Kalium 3,2 mmol/l", seite=1, seite_konfidenz=0.95)
        self.assertLess(erg["konfidenz"], 0.5)
        hinweise = " ".join(erg["belege"]["hinweise"])
        self.assertIn("Messbereich", hinweise)
        self.assertIn("nicht im Text", hinweise)
        frei = pruefung.laborwert({"parameter": "Tumormarker XY", "wert": "negativ"}, k, ocr_text="", seite=1,
                                  seite_konfidenz=None)
        self.assertIsNone(frei["wert"]["parameter"])
        self.assertEqual(frei["wert"]["wert_text"], "negativ")
        self.assertEqual(frei["wert"]["freitext_name"], "Tumormarker XY")

    def test_infusion_planfeld_und_diagnose(self):
        self.assertEqual(pruefung.planfeld("KCl 7,45 %"), "kalium_mmol")
        self.assertEqual(pruefung.planfeld("Glycophos"), "phosphat_mmol")
        self.assertIsNone(pruefung.planfeld("Vitamin K"))
        erg = pruefung.infusion({"substanz": "Kaliumchlorid", "menge": "40 mmol", "von": "2026-03-12",
                                 "uhrzeit": "08:00"}, ocr_text="KCl 40 mmol ab 12.03.", seite=1)
        self.assertEqual((erg["wert"]["planfeld"], erg["wert"]["menge"], erg["wert"]["einheit"]),
                         ("kalium_mmol", "40", "mmol"))
        self.assertEqual(erg["wert"]["uhrzeit"], "08:00")
        d = pruefung.diagnose({"bezeichnung": "Kurzdarmsyndrom", "icd_code": "K91.2"}, ocr_text="K91.2 G", seite=1)
        self.assertEqual(d["wert"]["icd_code"], "K91.2")
        falsch = pruefung.diagnose({"bezeichnung": "X", "icd_code": "Kurzdarm"}, ocr_text="", seite=1)
        self.assertEqual(falsch["wert"]["icd_code"], "")

    def test_patient_abgleich(self):
        class P:
            nachname, vorname, geburtsdatum = "Muster", "Erika", dt.date(1961, 3, 14)

        self.assertTrue(pruefung.patient_abgleich({"name": "Muster, Erika", "geburtsdatum": "1961-03-14"},
                                                  P)["wert"]["passt"])
        anders = pruefung.patient_abgleich({"name": "Beispiel, Max", "geburtsdatum": "1950-01-01"}, P)
        self.assertFalse(anders["wert"]["passt"])
        self.assertEqual(len(anders["belege"]["hinweise"]), 2)
        self.assertIsNone(pruefung.patient_abgleich({}, P))


def erg_id(katalog, name):
    return next(p["id"] for p in katalog.parameter.values() if p["name"] == name)


@override_settings(EPM_KI_ERLAUBTE_HOSTS=["ki-modell", "localhost", "127.0.0.1"])
class ModellClientTest(SimpleTestCase):
    def test_nur_erlaubte_rechner_im_internen_netz(self):
        self.assertEqual(pruefe_adresse("http://ki-modell:8080/"), "http://ki-modell:8080")
        for url in ("https://ki-modell:8080", "http://api.example.com/v1", "http://user:pw@ki-modell:8080",
                    "http://ki-modell.evil.com", "ftp://ki-modell", "http://ki-modell:8080/?x=1", ""):
            with self.assertRaises(NichtErlaubt, msg=url):
                pruefe_adresse(url)

    def test_anfrage_mit_bild_und_schema_ohne_proxy(self):
        with ModellServer('{"dokumenttyp": "labor"}') as srv, \
                mock.patch.dict(os.environ, {"HTTP_PROXY": "http://10.255.255.1:9", "HTTPS_PROXY":
                                             "http://10.255.255.1:9", "http_proxy": "http://10.255.255.1:9"}):
            c = Client(srv.url, zeitlimit_s=10)
            self.assertTrue(c.bereit()["bereit"])
            a = c.chat("System", "Text", bilder=[b"\xff\xd8bild"], schema={"type": "object"})
            self.assertEqual(a.json(), {"dokumenttyp": "labor"})
            anfrage = srv.anfragen[0]
            self.assertEqual(anfrage["response_format"]["type"], "json_schema")
            self.assertEqual(anfrage["chat_template_kwargs"], {"enable_thinking": False})
            inhalt = anfrage["messages"][1]["content"]
            self.assertTrue(inhalt[0]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
            self.assertEqual(anfrage["temperature"], 0.0)

    def test_fehler_werden_modellfehler(self):
        with ModellServer("kein json", status=500) as srv:
            with self.assertRaises(ModellFehler):
                Client(srv.url, zeitlimit_s=5).chat("s", "t")
        with ModellServer("kein json") as srv:
            with self.assertRaises(ModellFehler):
                Client(srv.url, zeitlimit_s=5).chat("s", "t", schema={}).json()
        c = Client("http://127.0.0.1:9", zeitlimit_s=2)
        self.assertFalse(c.bereit()["bereit"])

    def test_keine_verbindung_nach_aussen(self):
        """Wie OfflineTest bei „Scans“: nur Verbindungen zu 127.0.0.1 sind erlaubt."""
        original = socket.socket.connect

        def connect(sock, adresse):
            if isinstance(adresse, tuple) and adresse[0] not in ("127.0.0.1", "::1"):
                raise AssertionError(f"Verbindung nach außen: {adresse}")
            return original(sock, adresse)

        with ModellServer() as srv, mock.patch.object(socket.socket, "connect", connect):
            Client(srv.url, zeitlimit_s=5).chat("s", "t")
            with self.assertRaises(NichtErlaubt):
                Client("http://example.com")


class KryptoTest(SimpleTestCase):
    def test_verschluesselt_mit_bezug(self):
        with override_settings(EPM_KI=Path(KI_TMP), EPM_KI_SCHLUESSEL_FILE=""):
            pfad = krypto.ablage("test", "datei.bin")
            krypto.schreiben(pfad, b"geheim", "vorgang:1")
            roh = pfad.read_bytes()
            self.assertNotIn(b"geheim", roh)
            self.assertEqual(oct(pfad.stat().st_mode)[-3:], "600")
            self.assertEqual(krypto.lesen(pfad, "vorgang:1"), b"geheim")
            with self.assertRaises(Exception):
                krypto.lesen(pfad, "vorgang:2")

    def test_eigener_schluessel_und_aufraeumen(self):
        datei = Path(KI_TMP) / "schluessel"
        datei.write_text("ab" * 32)
        with override_settings(EPM_KI=Path(KI_TMP), EPM_KI_SCHLUESSEL_FILE=str(datei)):
            blob = krypto.verschluesseln(b"x")
            self.assertEqual(krypto.entschluesseln(blob), b"x")
            alt = krypto.vorgang_ordner(999)
            alt.mkdir(parents=True, exist_ok=True)
            os.utime(alt, (time.time() - 20 * 86400,) * 2)
            behalten = krypto.vorgang_ordner(998)
            behalten.mkdir(parents=True, exist_ok=True)
            os.utime(behalten, (time.time() - 20 * 86400,) * 2)
            self.assertEqual(krypto.aufraeumen(14, behalten={998}), 1)
            self.assertFalse(alt.exists())
            self.assertTrue(behalten.exists())
        datei.write_text("zu kurz")
        krypto._schluessel_cache.clear()
        with override_settings(EPM_KI_SCHLUESSEL_FILE=str(datei)):
            with self.assertRaises(ValueError):
                krypto.verschluesseln(b"x")
        krypto._schluessel_cache.clear()


class PseudonymTest(SimpleTestCase):
    def test_angaben_zur_person_ersetzt(self):
        class P:
            nachname, vorname, geburtsdatum, nummer = "Muster-Beispiel", "Erika", dt.date(1961, 3, 14), 4711

        text = ("Patient: Muster-Beispiel, Erika geb. 14.03.1961 Pat.-Nr. 4711, Musterstraße 12, 48143 Münster, "
                "Tel. 0251 123456, erika@example.org, A123456789. Kalium 3,2 mmol/l am 01.09.2026")
        t = pseudonymisieren(text, P)
        for verboten in ("Muster", "Erika", "14.03.1961", "4711", "Musterstraße", "48143", "123456", "example.org",
                         "A123456789"):
            self.assertNotIn(verboten, t, verboten)
        self.assertIn("Kalium 3,2 mmol/l am 01.09.2026", t)


class BenchmarkTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from patienten.testdaten import stammdaten_anlegen

        stammdaten_anlegen()

    def test_zeichenfehlerrate(self):
        from ki.benchmark import cer

        self.assertEqual(cer("Kalium 3,2", "Kalium 3,2"), 0.0)
        self.assertEqual(cer("abcd", "abed"), 0.25)
        self.assertIsNone(cer("", "x"))

    def test_seite_messen_gegen_modellserver(self):
        import json as _json

        from ki.benchmark import seite_messen, synthetische_seiten

        seiten = synthetische_seiten(grosses_pdf=2)
        self.assertEqual([s["kategorie"] for s in seiten], ["tabelle", "foto", "brief", "grosses_pdf"])
        self.assertIn(["Kalium", "3.2"], seiten[0]["laborwerte"])
        antwort = _json.dumps({"dokumenttyp": "labor", "laborwerte": [{"parameter": "Kalium", "wert": "3,2"}]})
        with ModellServer(antwort) as srv:
            erg = seite_messen(Client(srv.url, zeitlimit_s=10), seiten[0], pruefung.Katalog(), 800)
        self.assertEqual(erg["seiten"], 1)
        self.assertEqual(erg["dokumenttyp"], "labor")
        self.assertEqual(erg["laborwerte"]["precision"], 1.0)
        self.assertIsNotNone(erg["cer"])
