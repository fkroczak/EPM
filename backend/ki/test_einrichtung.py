"""KI (Experimentell): Einrichtung aus der Oberfläche – Auswahl der Modelle (Backend und Systemagent gleich),
Aufträge an den Agenten mit Recht und zweitem Faktor, Upload eines Modell-Pakets, Grenzen im Agenten, Benchmarks."""
import contextlib
import io
import json
import shutil
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from accounts.models import Rolle
from audit.models import SystemEreignis
from epm.pruefhilfen import KENNWORT, benutzer, client_fuer
from ki.katalog import KATALOG, mit_hardware
from ki.models import KiModellversion
from system import host
from system.models import Systemauftrag
from system.test_verwaltung import agent_modul, host_status_schreiben
from system.tests import Systemverzeichnis

GB = 1024 ** 3


class Katalog(SimpleTestCase):
    def test_backend_und_agent_kennen_dieselben_modelle(self):
        agent = agent_modul()
        self.assertEqual({k["schluessel"]: (k["repo"], k["quant"]) for k in KATALOG}, agent.KI_KATALOG)

    def test_alle_aktionen_im_backend_und_im_agenten(self):
        agent = agent_modul()
        for code in ("ki_modelle", "ki_modell_laden", "ki_modell_loeschen", "ki_einrichten", "ki_aus", "ki_grenzen",
                     "ki_benchmark"):
            self.assertIn(code, agent.AKTIONEN)
            self.assertIn(code, host.AKTIONEN)
            self.assertEqual(host.AKTIONEN[code]["recht"], "ki_verwalten")
            self.assertTrue(host.AKTIONEN[code]["intern"])

    def test_empfehlung_nach_hardware(self):
        heute = mit_hardware(4 * GB, 2, set())
        self.assertFalse(any(k["passt"] for k in heute))
        self.assertFalse(any(k.get("empfohlen") for k in heute))
        sechzehn = {k["schluessel"]: k for k in mit_hardware(16 * GB, 8, {"qwen3.5-4b-q4_k_m.gguf"})}
        self.assertTrue(sechzehn["qwen3.5-4b-q4"]["empfohlen"])
        self.assertTrue(sechzehn["qwen3.5-4b-q4"]["eingespielt"])
        self.assertFalse(sechzehn["qwen3.5-4b-q8"]["eingespielt"])
        self.assertFalse(sechzehn["qwen3.5-9b-q4"]["passt"])
        zweiunddreissig = {k["schluessel"]: k for k in mit_hardware(32 * GB, 8, set())}
        self.assertTrue(zweiunddreissig["qwen3.5-4b-q8"]["empfohlen"])
        self.assertTrue(zweiunddreissig["qwen3.5-9b-q4"]["passt"])


class AgentKi(SimpleTestCase):
    def setUp(self):
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.modul = agent_modul()
        self.basis = Path(tempfile.mkdtemp(prefix="epm-ki-agent-"))
        (self.basis / ".env").write_text("COMPOSE_FILE=compose.yaml\nKI_SPEICHER=6g\n")
        self.a = self.modul.Agent(str(self.basis), trocken=True)

    def tearDown(self):
        self.stdout.__exit__(None, None, None)
        shutil.rmtree(self.basis, ignore_errors=True)

    def test_grenzen_pruefen_und_speichern(self):
        z = []
        self.assertEqual(self.a.ki_grenzen({"KI_SPEICHER": "999g"}, z.append)[0], 2)
        self.assertEqual(self.a.ki_grenzen({"KI_THREADS": "-1"}, z.append)[0], 2)
        self.assertEqual(self.a.ki_grenzen({"KI_THREADS": "4; rm -rf /"}, z.append)[0], 2)
        self.assertEqual(self.a.ki_grenzen({}, z.append)[0], 2)
        rc, text = self.a.ki_grenzen({"KI_SPEICHER": "10G", "KI_THREADS": "6"}, z.append, simuliert=True)
        self.assertEqual((rc, text), (0, "Probelauf: Grenzen nicht gespeichert."))
        self.assertIn("KI_SPEICHER=6g", (self.basis / ".env").read_text())
        rc, _ = self.a.ki_grenzen({"KI_SPEICHER": "10G", "KI_THREADS": "6"}, z.append)
        self.assertEqual(rc, 0)
        env = self.a.env_lesen()
        self.assertEqual((env["KI_SPEICHER"], env["KI_THREADS"]), ("10g", "6"))

    def test_nur_modelle_aus_der_liste_und_nur_mit_internet(self):
        z = []
        self.assertEqual(self.a.ki_aktion("ki_modell_laden", {"variante": "http://boese/x"}, z.append)[0], 2)
        konf = self.basis / "epm.conf"
        konf.write_text('EPM_UPDATE_QUELLE="paket"\n')
        self.modul.lese_konf.__defaults__ = (str(konf),)  # eigenes Modul je Test: nichts zurückzusetzen
        self.assertFalse(self.a.ki_download_erlaubt())
        rc, text = self.a.ki_aktion("ki_modell_laden", {"variante": "qwen3.5-4b-q4"}, z.append)
        self.assertEqual(rc, 2)
        self.assertIn("hochladen", text)
        konf.write_text('EPM_UPDATE_QUELLE="paket"\nEPM_KI_DOWNLOAD="1"\n')
        self.assertTrue(self.a.ki_download_erlaubt())
        self.assertEqual(self.a.ki_aktion("ki_modell_loeschen", {"datei": "../../etc/passwd"}, z.append)[0], 2)
        self.assertEqual(self.a.ki_aktion("ki_unbekannt", {}, z.append)[0], 2)

    def test_stand_liest_modelle_varianten_und_grenzen(self):
        vorrat = self.basis / "ki-modelle"
        vorrat.mkdir()
        (vorrat / "qwen3.5-4b-q4_k_m.gguf").write_bytes(b"x" * 10)
        (vorrat / "MODELLE.txt").write_text("NAME=Qwen3.5-4B Q4_K_M\nDATEI=qwen3.5-4b-q4_k_m.gguf\nQUANT=Q4_K_M\n")
        stand = self.a.ki_stand()
        self.assertFalse(stand["eingerichtet"])
        self.assertEqual(stand["modelle"], [{"datei": "qwen3.5-4b-q4_k_m.gguf", "groesse": 10}])
        self.assertEqual(stand["varianten"][0]["datei"], "qwen3.5-4b-q4_k_m.gguf")
        self.assertEqual(stand["grenzen"]["KI_SPEICHER"], "6g")


@override_settings(EPM_KI=Path(tempfile.gettempdir()) / "epm-ki-einrichtung")
class Einrichtung(Systemverzeichnis):
    url = "/api/ki/einrichtung/"

    def setUp(self):
        super().setUp()
        from django.conf import settings

        shutil.rmtree(settings.EPM_KI, ignore_errors=True)
        settings.EPM_KI.mkdir(parents=True)
        host_status_schreiben(self.ordner, speicher={"gesamt": 16 * GB, "verfuegbar": 12 * GB}, cpu={"kerne": 8},
                              ki={"eingerichtet": False, "download_erlaubt": True, "modelle": [], "avx2": True,
                                  "grenzen": {"KI_SPEICHER": ""}})

    def bestaetigt(self, nr, **daten):
        return {"kennwort": KENNWORT, "code": self.admin_codes[nr], **daten}

    def test_stand_mit_katalog_und_empfehlung(self):
        r = self.a.get(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertTrue(d["agent"]["aktuell"])
        self.assertEqual(d["hardware"]["kerne"], 8)
        self.assertTrue(d["server"]["download_erlaubt"])
        self.assertEqual(next(k for k in d["katalog"] if k.get("empfohlen"))["schluessel"], "qwen3.5-4b-q4")
        self.assertEqual(d["uploads"], [])

    def test_nur_mit_recht(self):
        mitarbeiter = benutzer("einricht-ma", Rolle.MITARBEITER)
        self.assertEqual(client_fuer(mitarbeiter).get(self.url).status_code, 403)
        self.assertEqual(client_fuer(mitarbeiter).post(self.url, {"aktion": "einrichten"}, format="json").status_code,
                         403)

    def test_laden_nur_aus_der_liste_mit_zweitem_faktor(self):
        self.assertEqual(self.a.post(self.url, {"aktion": "laden", "variante": "irgendwas"}, format="json")
                         .status_code, 400)
        self.assertEqual(self.a.post(self.url, {"aktion": "formatieren"}, format="json").status_code, 400)
        r = self.a.post(self.url, {"aktion": "laden", "variante": "qwen3.5-4b-q4"}, format="json")
        self.assertEqual(r.status_code, 400)  # ohne Passwort und Code
        r = self.a.post(self.url, self.bestaetigt(0, aktion="laden", variante="qwen3.5-4b-q4"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        auftrag = Systemauftrag.objects.get(aktion="ki_modell_laden")
        self.assertEqual(auftrag.parameter, {"variante": "qwen3.5-4b-q4"})
        dateien = [json.loads(p.read_text()) for p in (self.ordner / "auftraege").iterdir()]
        self.assertEqual([d["aktion"] for d in dateien], ["ki_modell_laden"])
        self.assertEqual(dateien[0]["parameter"], {"variante": "qwen3.5-4b-q4"})
        self.assertTrue(SystemEreignis.objects.filter(art=SystemEreignis.Art.KI,
                                                      details__aktion="einrichtung_laden").exists())
        self.assertEqual(len(self.a.get(self.url).json()["auftraege"]), 1)

    def test_aktives_modell_nicht_loeschen(self):
        KiModellversion.objects.create(name="A", datei="aktiv.gguf", sha256="a" * 64, status="aktiv")
        r = self.a.post(self.url, self.bestaetigt(0, aktion="loeschen", datei="aktiv.gguf"), format="json")
        self.assertEqual(r.status_code, 400)
        r = self.a.post(self.url, self.bestaetigt(0, aktion="loeschen", datei="../x.gguf"), format="json")
        self.assertEqual(r.status_code, 400)
        r = self.a.post(self.url, self.bestaetigt(0, aktion="loeschen", datei="alt.gguf"), format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_grenzen_und_benchmark_ohne_zweiten_faktor(self):
        self.assertEqual(self.a.post(self.url, {"aktion": "grenzen"}, format="json").status_code, 400)
        r = self.a.post(self.url, {"aktion": "grenzen", "KI_SPEICHER": "8g", "KI_THREADS": 6}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Systemauftrag.objects.get(aktion="ki_grenzen").parameter,
                         {"KI_SPEICHER": "8g", "KI_THREADS": "6"})
        r = self.a.post(self.url, {"aktion": "benchmark", "eigene": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_modell_paket_hochladen_und_einspielen(self):
        self.assertEqual(self.a.post("/api/ki/hochladen/", {"name": "x.zip", "groesse": 5}, format="json")
                         .status_code, 400)
        r = self.a.post("/api/ki/hochladen/", {"name": "epm-ki-modelle.tar", "groesse": 4}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        kennung = r.json()["upload"]
        teil = f"/api/ki/hochladen/{kennung}/"
        r = self.a.post(f"{teil}einspielen/", self.bestaetigt(0), format="json")
        self.assertEqual(r.status_code, 409)  # noch nicht vollständig
        r = self.a.put(f"{teil}?versatz=0", b"TEST", content_type="application/octet-stream")
        self.assertIn(r.status_code, (200, 204), r.content)
        self.assertEqual(self.a.get(self.url).json()["uploads"][0]["name"], "epm-ki-modelle.tar")
        r = self.a.post(f"{teil}einspielen/", self.bestaetigt(1), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Systemauftrag.objects.get(aktion="ki_modelle").parameter["upload"], kennung)
        self.assertEqual(self.a.delete(teil).status_code, 409)  # der Server verarbeitet sie gerade

    def test_benchmarks(self):
        from django.conf import settings

        (settings.EPM_KI / "benchmark-20261015-0300.json").write_text(json.dumps(
            [{"variante": "qwen3.5-4b-q4", "laden_s": 12, "ram_max_gb": 5.1, "je_kategorie": {"labor": {"f1": 0.9}}}]))
        (settings.EPM_KI / "anderes.json").write_text("{}")
        r = self.a.get("/api/ki/benchmarks/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)
        self.assertEqual(r.json()[0]["varianten"][0]["ram_max_gb"], 5.1)
