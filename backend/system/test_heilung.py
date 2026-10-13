"""
Selbstheilung (13.10.2026): Wächter im Status-Lauf des Systemagenten (Probelauf gegen nachgebildete Docker-Befehle),
die Aufträge „Als gute Version bestätigen“ und „Selbstheilung ein-/ausschalten“, Übernahme der Eingriffe ins Audit-Log
und als Hinweis an alle Benutzer, die Funktionen von epm-update.sh.
"""
import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase
from django.utils import timezone

from audit.models import SystemEreignis
from epm.pruefhilfen import client_fuer

from . import host, verwaltung_api
from .models import Systemauftrag, Systemhinweis
from .test_verwaltung import agent_modul
from .tests import AGENT, Systemverzeichnis

REPO = Path(__file__).resolve().parent.parent.parent
GUT, NEU, ALT = "1.0.0-aaaaaaa", "1.1.0-bbbbbbb", "0.9.0-9999999"


class FalscherDocker:
    """docker compose ps/up/restart, docker image ls/prune, systemd-run – mit Zustand je Container."""

    def __init__(self):
        self.container = {d: {"zustand": "running", "gesundheit": "healthy"} for d in ("db", "backend", "ocr", "web")}
        self.images = {GUT, NEU, ALT}
        self.aufrufe, self.alle = [], []
        self.ps_fehler = False

    def __call__(self, args, **kw):
        args = list(args)
        self.aufrufe.append(args)
        self.alle.append(args)
        if args[:2] == ["docker", "compose"]:
            rest = args[2:]
            if rest[:1] == ["ps"]:
                if self.ps_fehler:
                    return 1, "Cannot connect to the Docker daemon\n"
                liste = [{"Service": d, "Name": f"epm-{d}-1", "State": c["zustand"], "Health": c["gesundheit"],
                          "Image": f"epm-{d}:{GUT}", "Status": "Up"} for d, c in self.container.items() if c["zustand"]]
                return 0, json.dumps(liste)
            if rest[:1] == ["up"]:
                for d in rest[3:]:
                    self.container[d] = {"zustand": "running", "gesundheit": "starting"}
                return 0, ""
            if rest[:1] == ["restart"]:
                self.container[rest[1]] = {"zustand": "running", "gesundheit": "starting"}
                return 0, ""
            return 0, ""
        if args[:3] == ["docker", "image", "ls"]:
            return 0, "".join(f"{t}\t2026-10-{i + 1:02d} 10:00:00 +0200 CEST\n" for i, t in enumerate(sorted(self.images)))
        if args[:3] == ["docker", "image", "prune"]:
            return 0, "Total reclaimed space: 1.2GB\n"
        if args[0] == "systemd-run":
            return 0, ""
        return 0, ""

    def befehle(self, art=None, alle=False):
        return [" ".join(a) for a in (self.alle if alle else self.aufrufe) if art is None or art in a]


class AgentHeilung(SimpleTestCase):
    def setUp(self):
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.modul = agent_modul()
        self.basis = Path(tempfile.mkdtemp(prefix="epm-heilung-"))
        (self.basis / "system").mkdir()
        self.env(GUT, GUT)
        self.docker = FalscherDocker()
        self.a = self.agent()
        self.t = time.mktime((2026, 10, 13, 12, 0, 0, 0, 0, -1))    # feste Uhrzeit: Pausen und Tageskennung bleiben stabil

    def tearDown(self):
        self.stdout.__exit__(None, None, None)
        shutil.rmtree(self.basis, ignore_errors=True)

    def env(self, aktiv, gut, compose="compose.yaml"):
        (self.basis / ".env").write_text(f"COMPOSE_FILE={compose}\nEPM_BIND_IP=10.0.0.1\nEPM_VERSION={aktiv}\n"
                                         + (f"EPM_VERSION_GUT={gut}\n" if gut else ""))

    def agent(self, trocken=False):
        a = self.modul.Agent(str(self.basis), trocken=trocken)
        a.befehl = self.docker
        return a

    def lauf(self, minuten=0, platten=None, laufzeit=1000, agent=None):
        a = agent or self.a
        self.docker.aufrufe.clear()
        return a.heilung_pruefen(a.container(), platten or [], a.epm_versionen(), laufzeit, jetzt=self.t + minuten * 60)

    def zustand(self):
        return json.loads((self.basis / "system" / "heilung.json").read_text())

    def test_alles_gesund(self):
        e = self.lauf()
        self.assertEqual((e["an"], e["aktiv"], e["grund"], e["laufend"], e["gut"], e["gut_ist_laufend"]), (True, True, None, GUT, GUT, True))
        self.assertEqual(self.docker.befehle("up") + self.docker.befehle("restart"), [])
        self.assertEqual(e["aktionen"], [])
        self.assertTrue((self.basis / "system" / "heilung.json").exists())

    def test_fehlender_container_wird_gestartet(self):
        self.docker.container["ocr"] = {"zustand": "exited", "gesundheit": ""}
        self.docker.container["web"] = {"zustand": "", "gesundheit": ""}      # gar nicht da
        e = self.lauf()
        self.assertEqual(self.docker.befehle("up"), ["docker compose up -d --no-recreate ocr web"])
        self.assertEqual([(x["dienst"], x["art"], x["ok"]) for x in e["aktionen"]], [("ocr,web", "start", True)])
        self.assertEqual(self.docker.container["web"]["zustand"], "running")
        # Pause: nicht noch einmal innerhalb von 5 Minuten, danach wieder
        self.docker.container["ocr"] = {"zustand": "exited", "gesundheit": ""}
        self.lauf(minuten=2)
        self.assertEqual(self.docker.befehle("up"), [])
        self.lauf(minuten=6)
        self.assertEqual(self.docker.befehle("up"), ["docker compose up -d --no-recreate ocr"])

    def test_ungesund_dreimal_dann_neustart(self):
        self.docker.container["ocr"]["gesundheit"] = "unhealthy"
        for m in (0, 1):
            e = self.lauf(minuten=m)
            self.assertEqual(self.docker.befehle("restart"), [], m)
        self.assertEqual(e["zaehler"], {"ocr": 2})
        e = self.lauf(minuten=2)
        self.assertEqual(self.docker.befehle("restart"), ["docker compose restart ocr"])
        self.assertEqual(e["zaehler"], {})
        self.assertEqual(e["aktionen"][0]["text"], "Container ocr ist seit 3 Messungen ungesund – wird neu gestartet")
        # Pause: wieder dreimal ungesund, aber keine 5 Minuten seit dem Neustart → kein zweiter
        for m in (3, 4, 5):
            self.docker.container["ocr"]["gesundheit"] = "unhealthy"
            e = self.lauf(minuten=m)
            self.assertEqual(self.docker.befehle("restart"), [], m)
        self.assertEqual(e["zaehler"], {"ocr": 3})
        # gesund dazwischen setzt den Zähler zurück
        self.docker.container["ocr"]["gesundheit"] = "healthy"
        self.assertEqual(self.lauf(minuten=6)["zaehler"], {})
        # „restarting“ (Absturzschleife) zählt wie ungesund; nach der Pause wird neu gestartet
        self.docker.container["ocr"] = {"zustand": "restarting", "gesundheit": ""}
        for m in (7, 8):
            self.lauf(minuten=m)
            self.docker.container["ocr"] = {"zustand": "restarting", "gesundheit": ""}
        self.lauf(minuten=9)
        self.assertEqual(self.docker.befehle("restart"), ["docker compose restart ocr"])

    def test_nur_ein_neustart_je_lauf_db_zuerst(self):
        for d in ("backend", "db"):
            self.docker.container[d]["gesundheit"] = "unhealthy"
        for m in (0, 1, 2):
            self.lauf(minuten=m)
        self.assertEqual(self.docker.befehle("restart"), ["docker compose restart db"])

    def backend_dreimal_neu_starten(self):
        """Backend bleibt ungesund: 3 Neustarte (je 5 Minuten Pause) in 30 Minuten, danach der vierte Anlauf."""
        e = None
        for m in range(0, 27):
            self.docker.container["backend"]["gesundheit"] = "unhealthy"
            e = self.lauf(minuten=m)
        self.assertEqual(self.docker.befehle("restart", alle=True), ["docker compose restart backend"] * 3)
        return e

    def test_rueckfall_auf_gute_version(self):
        self.env(NEU, GUT)
        with mock.patch.object(self.modul, "EPM_UPDATE", sys.executable):
            e = self.backend_dreimal_neu_starten()
        befehle = self.docker.befehle("systemd-run", alle=True)
        self.assertEqual(len(befehle), 1, befehle)
        self.assertEqual(befehle[0].split()[-3:], [sys.executable, "--zurueck", GUT])
        self.assertIn("--unit epm-heilung-rueckfall", befehle[0])
        self.assertEqual((e["rueckfall"]["von"], e["rueckfall"]["nach"], e["rueckfall"]["ok"], e["rueckfall"]["quelle"]),
                         (NEU, GUT, True, "systemagent"))
        self.assertEqual(json.loads((self.basis / "system" / "rueckfall.json").read_text())["id"], e["rueckfall"]["id"])
        self.assertEqual(e["aktionen"][0]["art"], "rueckfall")
        self.assertEqual(e["rueckfall_versucht"], NEU)
        self.assertIn("schon versucht", e["grund"])
        # nicht noch einmal für dieselbe Version: später wieder ein gewöhnlicher Neustart, kein zweiter Rückfall
        with mock.patch.object(self.modul, "EPM_UPDATE", sys.executable):
            for m in (31, 32, 33):
                self.docker.container["backend"]["gesundheit"] = "unhealthy"
                self.lauf(minuten=m)
        self.assertEqual(len(self.docker.befehle("systemd-run", alle=True)), 1)
        self.assertEqual(len(self.docker.befehle("restart", alle=True)), 4)

    def test_kein_rueckfall_wenn_gut_gleich_laufend(self):
        with mock.patch.object(self.modul, "EPM_UPDATE", sys.executable):
            e = self.backend_dreimal_neu_starten()
        self.assertEqual(self.docker.befehle("systemd-run", alle=True), [])
        self.assertFalse(e["rueckfall_moeglich"])
        self.assertIsNone(e["rueckfall"])
        self.assertIn("keine andere gute Version", e["grund"])

    def test_kein_rueckfall_ohne_images_der_guten_version(self):
        self.env(NEU, GUT)
        self.docker.images.discard(GUT)
        with mock.patch.object(self.modul, "EPM_UPDATE", sys.executable):
            e = self.backend_dreimal_neu_starten()
        self.assertEqual(self.docker.befehle("systemd-run", alle=True), [])
        self.assertFalse(e["gut_vorhanden"])

    def test_platte_knapp(self):
        platten = [{"pfad": "/", "bezeichnung": "System", "gesamt": 100 * 1024 ** 3, "frei": 50 * 1024 ** 3},
                   {"pfad": "/srv/epm", "bezeichnung": "EPM-Daten", "gesamt": 100 * 1024 ** 3, "frei": 3 * 1024 ** 3}]
        e = self.lauf(platten=platten)
        self.assertEqual(e["platte"]["bezeichnung"], "EPM-Daten")
        self.assertEqual(self.docker.befehle("prune"), ["docker image prune -f"])
        kennung = e["platte"]["id"]
        # dieselbe Kennung am selben Tag (ein Hinweis), kein zweites Aufräumen in der Stunde
        e = self.lauf(minuten=30, platten=platten)
        self.assertEqual((e["platte"]["id"], self.docker.befehle("prune")), (kennung, []))
        self.assertEqual(self.lauf(minuten=70, platten=platten)["platte"]["id"], kennung)
        self.assertEqual(self.docker.befehle("prune"), ["docker image prune -f"])
        platten[1]["frei"] = 20 * 1024 ** 3
        self.assertIsNone(self.lauf(minuten=80, platten=platten)["platte"])
        self.assertIsNone(self.lauf(platten=[{"pfad": "/", "bezeichnung": "System", "gesamt": 10 * 1024 ** 3,
                                               "frei": 2 * 1024 ** 3}])["platte"])
        self.assertIsNotNone(self.lauf(platten=[{"pfad": "/", "bezeichnung": "System", "gesamt": 10 * 1024 ** 3,
                                                  "frei": 400 * 1024 ** 2}])["platte"])

    def test_ausgeschaltet_und_stillhalten(self):
        self.docker.container["ocr"] = {"zustand": "exited", "gesundheit": ""}
        (self.basis / "system" / "heilung-aus").write_text("x")
        e = self.lauf()
        self.assertEqual((e["an"], e["aktiv"], self.docker.befehle("up")), (False, False, []))
        self.assertIn("ausgeschaltet", e["grund"])
        os.unlink(self.basis / "system" / "heilung-aus")
        (self.basis / "system" / "update-laeuft").write_text("1 jetzt update")
        e = self.lauf()
        self.assertEqual((e["aktiv"], e["grund"], e["update_laeuft"]), (False, "epm-update läuft", True))
        alt = time.time() - 5 * 3600
        os.utime(self.basis / "system" / "update-laeuft", (alt, alt))     # abgestürztes Update: Markierung verfallen
        self.assertTrue(self.lauf()["aktiv"])
        os.unlink(self.basis / "system" / "update-laeuft")
        self.assertEqual(self.lauf(laufzeit=30)["grund"], "Server ist gerade gestartet")
        self.env(GUT, GUT, compose="compose.smoke.yaml")
        self.assertIn("nicht aktiv", self.lauf()["grund"])
        self.env(GUT, GUT)
        with open(self.basis / "system" / "status" / ".sperre", "w") as sperre:
            self.modul.fcntl.flock(sperre, self.modul.fcntl.LOCK_EX)
            self.assertEqual(self.lauf()["grund"], "ein Auftrag läuft")
        self.docker.ps_fehler = True
        self.assertEqual(self.lauf()["grund"], "Container nicht abrufbar")

    def test_probelauf_fuehrt_nichts_aus(self):
        a = self.agent(trocken=True)
        self.docker.container["ocr"] = {"zustand": "exited", "gesundheit": ""}
        e = self.lauf(agent=a)
        self.assertEqual(self.docker.befehle("up"), [])
        self.assertEqual((e["aktionen"][0]["probelauf"], e["aktionen"][0]["art"]), (True, "start"))

    def test_version_bestaetigen_und_schalten(self):
        z = []
        self.env(NEU, GUT)
        self.assertEqual(self.a.version_bestaetigen(z.append), (0, f"Version {NEU} ist jetzt die gute Version – auf sie fällt die "
                                                                    "Selbstheilung zurück."))
        self.assertEqual(self.a.env_lesen()["EPM_VERSION_GUT"], NEU)
        self.assertEqual((self.basis / ".env").read_text().count("EPM_VERSION_GUT="), 1)
        self.assertEqual(self.a.version_bestaetigen(z.append, simuliert=True)[1], f"Probelauf: {NEU} nicht als gute Version eingetragen.")
        self.docker.images.discard(NEU)
        self.assertEqual(self.a.version_bestaetigen(z.append)[0], 2)
        self.env("", "")
        self.assertEqual(self.a.version_bestaetigen(z.append)[0], 2)
        flagge = self.basis / "system" / "heilung-aus"
        self.assertEqual(self.a.heilung_schalten(False, z.append)[0], 0)
        self.assertTrue(flagge.exists())
        self.assertFalse(self.a.heilung_an())
        self.assertEqual(self.a.heilung_schalten(True, z.append)[0], 0)
        self.assertFalse(flagge.exists())
        self.assertEqual(self.a.heilung_schalten(True, z.append)[0], 0)
        self.assertEqual(self.a.heilung_schalten("ja", z.append)[0], 2)
        self.assertEqual(self.a.heilung_schalten(False, z.append, simuliert=True)[1], "Probelauf: Selbstheilung nicht ausgeschaltet.")
        self.assertFalse(flagge.exists())

    def test_geschuetzte_tags_mit_guter_version(self):
        self.env(NEU, ALT)
        self.assertEqual(self.a.geschuetzte_tags(), {NEU, GUT, ALT})

    def test_aktionen_im_backend_und_im_agenten(self):
        for code in ("version_bestaetigen", "heilung_schalten"):
            self.assertIn(code, self.modul.AKTIONEN)
            self.assertIn(code, host.AKTIONEN)

    def test_echter_agent_status_im_probelauf(self):
        """Der Status-Lauf des echten Skripts schreibt „heilung“ – ohne Docker: nicht aktiv, nichts verändert."""
        (self.basis / "epm.conf").write_text('EPM_BASE="/srv/epm"\n')
        p = subprocess.run([sys.executable, str(AGENT), "status", "--basis", str(self.basis), "--trocken",
                            "--einstellungen", str(self.basis / "epm.conf")], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr)
        status = json.loads((self.basis / "system" / "status" / "system.json").read_text())
        h = status["heilung"]
        self.assertEqual((h["an"], h["aktiv"], h["laufend"], h["gut"]), (True, False, GUT, GUT))
        self.assertEqual(h["grund"], "Container nicht abrufbar")
        self.assertTrue((self.basis / "system" / "heilung.json").exists())


@unittest.skipUnless((REPO / "werkzeuge" / "epm-update.sh").exists(), "Skripte nur im Repo")
class Skripte(SimpleTestCase):
    def test_syntax(self):
        for datei in ("werkzeuge/epm-update.sh", "rollout/04-projekt.sh", "rollout/02-docker.sh"):
            p = subprocess.run(["bash", "-n", str(REPO / datei)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)

    def test_epm_update_rueckfall(self):
        """Funktionen von epm-update.sh gegen ein nachgebildetes docker: Start der neuen Version scheitert → zurück auf
        die gute Version, Markierung für den Agenten; Musterdaten bestanden → neue Version wird die gute."""
        h = Path(tempfile.mkdtemp(prefix="epm-update-"))
        try:
            (h / "bin").mkdir()
            (h / "B" / "images").mkdir(parents=True)
            (h / "B" / "system").mkdir()
            docker = h / "bin" / "docker"
            docker.write_text(f'''#!/usr/bin/env bash
case "$*" in
  "compose ps -q backend") echo cid ;;
  "inspect -f {{{{.State.Health.Status}}}} cid") tag=$(grep ^EPM_VERSION= "$B/.env" | cut -d= -f2); grep -qx "$tag" "{h}/gesund" && echo healthy || echo unhealthy ;;
  "image inspect "*) grep -qx "${{3#*:}}" "{h}/images"; exit $? ;;
  "compose logs --tail 40 backend") echo "Traceback: kaputt" ;;
  "compose exec -T backend python manage.py epm_musterdaten") exit 0 ;;
esac
exit 0
''')
            docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
            (h / "images").write_text(f"{GUT}\n{NEU}\n")
            (h / "gesund").write_text(f"{GUT}\n")
            (h / "B" / ".env").write_text(f"COMPOSE_FILE=compose.yaml\nEPM_VERSION={GUT}\nEPM_VERSION_GUT={GUT}\n")
            skript = f'''set -uo pipefail
export B="{h}/B" PATH="{h}/bin:$PATH" PROTOKOLL="{h}/protokoll" TESTS=0
sleep() {{ :; }}
schritt() {{ echo "==> $*"; }}
source <(sed -n '/^alte_entfernen()/,/^while \\[\\[ \\$# -gt 0/p' "{REPO}/werkzeuge/epm-update.sh" | sed '$ d')
umstellen_oder_zurueck {NEU} {GUT}; echo "rc=$?"
echo "env=$(env_wert EPM_VERSION) gut=$(env_wert EPM_VERSION_GUT)"
echo {NEU} >> "{h}/gesund"
umstellen_oder_zurueck {NEU} {GUT}; echo "rc=$?"
ERGEBNIS=""; abschliessen {NEU} {GUT}; echo "rc=$? gut=$(env_wert EPM_VERSION_GUT) $ERGEBNIS"
'''
            p = subprocess.run(["bash", "-c", skript], capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn(f"ABBRUCH: Neue Version {NEU} startet nicht – zurück auf {GUT} (läuft wieder).", p.stdout)
            self.assertIn("Datenbank-Migrationen der neuen Version wurden nicht zurückgedreht", p.stdout)
            self.assertIn(f"rc=1\nenv={GUT} gut={GUT}\n", p.stdout)
            m = json.loads((h / "B" / "system" / "rueckfall.json").read_text())
            self.assertEqual((m["von"], m["nach"], m["ok"], m["quelle"]), (NEU, GUT, True, "epm-update"))
            self.assertIn(f"   Gute Version: {NEU}\n", p.stdout)
            self.assertTrue(p.stdout.endswith(f"rc=0 gut={NEU} Tests übersprungen\n"), p.stdout)
        finally:
            shutil.rmtree(h, ignore_errors=True)


class HeilungApi(Systemverzeichnis):
    def status(self, **heilung):
        daten = {"zeit": timezone.now().isoformat(), "rechner": "epm", "trocken": True,
                 "versionen": {"verfuegbar": True, "aktiv": NEU, "quelle": "git",
                               "liste": [{"tag": t, "erstellt": "", "backend": True, "web": True, "aktiv": t == NEU, "vollstaendig": True}
                                         for t in (NEU, GUT, ALT)]},
                 "heilung": {"an": True, "aktiv": True, "grund": None, "laufend": NEU, "gut": GUT, "gut_vorhanden": True,
                             "gut_ist_laufend": False, "rueckfall": None, "platte": None, "aktionen": [], **heilung}}
        (self.ordner / "status" / "system.json").write_text(json.dumps(daten))

    def auftragsdatei(self):
        dateien = list((self.ordner / "auftraege").glob("*.json"))
        self.assertEqual(len(dateien), 1, dateien)
        return json.loads(dateien[0].read_text())

    def texte(self):
        return [x["beschreibung"] for x in self.a.get("/api/protokoll/?gruppe=system").json()["results"]]

    def test_rechte(self):
        for user in (self.mitarbeiter, self.mediziner):
            c = client_fuer(user)
            self.assertEqual(c.post("/api/system/heilung/bestaetigen/", {}, format="json").status_code, 403)
            self.assertEqual(c.post("/api/system/heilung/schalten/", {"an": False}, format="json").status_code, 403)

    def test_uebersicht_und_verwaltung(self):
        self.status()
        u = self.a.get("/api/system/uebersicht/").json()
        self.assertEqual(u["host"]["heilung"]["gut"], GUT)
        self.assertEqual(u["verwaltung"]["version_bestaetigen"]["bestaetigung"], "einfach")
        self.assertEqual(u["verwaltung"]["heilung_schalten"]["bestaetigung"], "einfach")
        self.assertEqual(verwaltung_api.geschuetzte_tags(u["host"]), {NEU, GUT})

    def test_bestaetigen(self):
        self.status()
        r = self.a.post("/api/system/heilung/bestaetigen/", {}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["aktion"], "version_bestaetigen")
        self.assertIn(f"Version {NEU} als gute Version bestätigen angefordert (bisher {GUT})", self.texte())
        self.assertEqual(self.a.post("/api/system/heilung/bestaetigen/", {}, format="json").status_code, 409)   # schon beauftragt
        Systemauftrag.objects.all().delete()
        self.status(gut=NEU, gut_ist_laufend=True)
        r = self.a.post("/api/system/heilung/bestaetigen/", {}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertIn("schon die gute Version", r.json()["fehler"])

    def test_schalten(self):
        self.status()
        self.assertEqual(self.a.post("/api/system/heilung/schalten/", {"an": "nein"}, format="json").status_code, 400)
        r = self.a.post("/api/system/heilung/schalten/", {"an": False}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"], {"an": False})
        self.assertIn("Selbstheilung ausschalten angefordert", self.texte())

    def test_eingriffe_ins_audit_log_und_hinweis(self):
        aktionen = [{"id": "a" * 16, "zeit": timezone.now().isoformat(), "dienst": "ocr", "art": "neustart", "befehl": "docker compose restart ocr",
                     "ok": True, "rueckgabe": 0, "text": "Container ocr ist seit 3 Messungen ungesund – wird neu gestartet", "ausgabe": "", "probelauf": False},
                    {"id": "b" * 16, "zeit": timezone.now().isoformat(), "dienst": "web", "art": "start", "befehl": "docker compose up -d web",
                     "ok": False, "rueckgabe": 1, "text": "Container web fehlt oder ist beendet – wird gestartet", "ausgabe": "x", "probelauf": False}]
        rueckfall = {"id": "c" * 16, "zeit": timezone.now().isoformat(), "quelle": "systemagent", "von": NEU, "nach": GUT, "ok": True,
                     "grund": f"Backend der Version {NEU} startet nicht (nach 3 Neustarten ungesund)"}
        self.status(aktionen=aktionen, rueckfall=rueckfall, laufend=GUT)
        for _ in (1, 2):
            self.assertEqual(self.a.get("/api/system/uebersicht/").status_code, 200)
        ereignisse = SystemEreignis.objects.filter(benutzername="systemagent")
        self.assertEqual(sorted(ereignisse.values_list("details__ereignis", flat=True)), ["heilung", "heilung", "heilung_rueckfall"])
        texte = self.texte()
        self.assertIn("Selbstheilung: ocr neu gestartet: Container ocr ist seit 3 Messungen ungesund – wird neu gestartet", texte)
        self.assertIn("Selbstheilung: web gestartet – fehlgeschlagen: Container web fehlt oder ist beendet – wird gestartet", texte)
        self.assertIn(f"Selbstheilung: EPM auf Version {GUT} zurückgeschaltet, weil {NEU} nicht startete", texte)
        h = Systemhinweis.aktiv()
        self.assertIsNotNone(h)
        self.assertIsNone(h.angelegt_von)
        self.assertEqual(h.art, Systemhinweis.Art.WARNUNG)
        self.assertIn(f"EPM wurde auf Version {GUT} zurückgeschaltet, weil {NEU} nicht startete", h.text)
        self.assertIn("Migrationen", h.text)
        # jeder Angemeldete sieht den Hinweis, ohne Namen; der Abruf des Banners übernimmt den Stand auch ohne Systemseite
        r = client_fuer(self.mitarbeiter).get("/api/system/hinweis/").json()["hinweis"]
        self.assertEqual((r["text"], r["angelegt_von_name"]), (h.text, None))
        self.assertEqual(Systemhinweis.objects.count(), 1)
        # Platte knapp: Hinweis für 24 Stunden – aber nicht, solange ein Hinweis eines Admins steht
        self.a.delete("/api/system/hinweis/")
        self.a.post("/api/system/hinweis/", {"text": "Wartung heute", "art": "info"}, format="json")
        platte = {"id": "d" * 16, "pfad": "/srv/epm", "bezeichnung": "EPM-Daten", "frei": 500 * 1024 ** 2, "gesamt": 100 * 1024 ** 3}
        self.status(platte=platte)
        client_fuer(self.mitarbeiter).get("/api/system/hinweis/")
        self.assertEqual(Systemhinweis.aktiv().text, "Wartung heute")
        self.assertEqual(SystemEreignis.objects.filter(details__ereignis="heilung_platte").count(), 1)
        self.a.delete("/api/system/hinweis/")
        self.status(platte={**platte, "id": "e" * 16})
        client_fuer(self.mitarbeiter).get("/api/system/hinweis/")
        h = Systemhinweis.aktiv()
        self.assertIn("fast voll:", h.text)
        self.assertIn("frei von", h.text)
        self.assertIsNotNone(h.gueltig_bis)
        self.assertIn("Selbstheilung: Platte EPM-Daten fast voll (/srv/epm) – hängende Images entfernt, Hinweis an alle", self.texte())

    def test_rueckfall_fehlgeschlagen_und_ohne_ziel(self):
        self.status(rueckfall={"id": "f" * 16, "zeit": timezone.now().isoformat(), "quelle": "epm-update", "von": NEU, "nach": GUT, "ok": False,
                               "grund": "x"})
        self.a.get("/api/system/uebersicht/")
        self.assertIn(f"Version {NEU} startet nicht, und das Zurückschalten auf {GUT} ist fehlgeschlagen", Systemhinweis.aktiv().text)
        self.assertIn(f"Selbstheilung: Version {NEU} startet nicht; Zurückschalten auf {GUT} fehlgeschlagen", self.texte())
        self.a.delete("/api/system/hinweis/")
        self.status(rueckfall={"id": "0" * 16, "zeit": timezone.now().isoformat(), "quelle": "epm-update", "von": NEU, "nach": "", "ok": False,
                               "grund": "x"})
        self.a.get("/api/system/uebersicht/")
        self.assertIn("keine andere Version zum Zurückschalten", Systemhinweis.aktiv().text)
        self.assertTrue(any("nicht möglich (keine andere Version)" in t for t in self.texte()))

    @unittest.skipUnless(AGENT.exists(), "rollout/epm-systemagent.py nur im Repo (nicht im Image)")
    def test_echter_agent_im_probelauf(self):
        self.status()
        self.a.post("/api/system/heilung/bestaetigen/", {}, format="json")
        self.a.post("/api/system/heilung/schalten/", {"an": False}, format="json")
        basis = Path(tempfile.mkdtemp(prefix="epm-basis-"))
        try:
            os.symlink(self.ordner, basis / "system")
            (basis / ".env").write_text(f"COMPOSE_FILE=compose.yaml\nEPM_VERSION={NEU}\nEPM_VERSION_GUT={GUT}\n")
            p = subprocess.run([sys.executable, str(AGENT), "auftraege", "--basis", str(basis), "--trocken"],
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("EPM_VERSION_GUT=" + NEU, (basis / ".env").read_text())
            self.assertFalse((self.ordner / "heilung-aus").exists())
        finally:
            shutil.rmtree(basis, ignore_errors=True)
        self.a.get("/api/system/auftraege/")
        ergebnisse = {a.aktion: (a.status, a.ergebnis, a.probelauf) for a in Systemauftrag.objects.all()}
        self.assertEqual(ergebnisse, {
            "version_bestaetigen": ("erledigt", f"Probelauf: {NEU} nicht als gute Version eingetragen.", True),
            "heilung_schalten": ("erledigt", "Probelauf: Selbstheilung nicht ausgeschaltet.", True)})
