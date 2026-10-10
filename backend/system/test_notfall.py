"""Notfallpaket und Wiederaufbau-Plan (F188): Rechte, Bestätigung, Audit-Log, Plan als HTML/PDF/Markdown, der Agent baut
ein Paket in eigenen Verzeichnissen (docker und apt nachgestellt, GnuPG echt) – Inhalt, Prüfsummen, keine Geheimnisse,
CA-Schlüssel nur verschlüsselt – und das Aufbauskript aus dem Paket läuft im Probelauf durch."""
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from audit.models import SystemEreignis
from epm.pruefhilfen import KENNWORT, client_fuer

from .models import Systemauftrag
from .test_sicherung import Backupverzeichnis
from .test_verwaltung import agent_modul, host_status_schreiben
from .tests import AGENT

REPO = AGENT.parent.parent
PASSWORT = "Tresor-Passwort-2026-Notfall"
DB_PASSWORT = "db-geheim-Ohne-Gleichen-4711"
DJANGO_SECRET = "django-secret-xyz-0815-niemals-ins-paket"
ZIEL_PASS = "OBSCURED-rclone-pass-abc123"
ST = "2026-10-09_020000"


class NotfallApi(Backupverzeichnis):
    def test_rechte_bestaetigung_audit(self):
        m = client_fuer(self.mediziner)
        self.assertEqual(m.post("/api/system/notfall/", {}, format="json").status_code, 403)
        self.assertEqual(m.get("/api/system/notfallplan/").status_code, 403)
        url = "/api/system/notfall/"
        self.assertEqual(self.a.post(url, {"mit_sicherung": "ja"}, format="json").status_code, 400)
        # ohne laufenden Agenten nicht
        self.assertEqual(self.a.post(url, {"mit_sicherung": True}, format="json").status_code, 409)
        host_status_schreiben(self.ordner, notfall={"schaetzung": 1000})
        r = self.a.post(url, {"mit_sicherung": True}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["kennwort"]))
        r = self.a.post(url, {"mit_sicherung": False, "kennwort": KENNWORT, "code": self.admin_codes[0]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"], {"mit_sicherung": False})
        texte = [x["beschreibung"] for x in self.a.get("/api/protokoll/?gruppe=system").json()["results"]]
        self.assertIn("Notfallpaket angefordert (ohne jüngste Sicherung), mit Passwort und 2FA bestätigt", texte)
        self.assertEqual(self.a.get("/api/system/uebersicht/").json()["verwaltung"]["notfallpaket"]["bestaetigung"], "2fa")

    def test_herunterladen(self):
        name = "epm-notfall-0.9.2-bbbbbbb-2026-10-10_1200.tar"
        self.assertEqual(self.a.get(f"/api/system/notfall/{name}/").status_code, 404)
        self.assertEqual(self.a.get("/api/system/notfall/..%2Fstatus%2Fsystem.json/").status_code, 404)
        (self.ordner / "download" / name).write_bytes(b"tar")
        r = self.a.get(f"/api/system/notfall/{name}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Accel-Redirect"], f"/_geschuetzt/sicherung/{name}")
        self.assertEqual(client_fuer(self.mediziner).get(f"/api/system/notfall/{name}/").status_code, 403)
        self.assertTrue(SystemEreignis.objects.filter(details__ereignis="notfall_heruntergeladen").exists())

    def test_plan_html_pdf_markdown(self):
        from . import notfallplan

        d = self.a.get("/api/system/notfallplan/").json()
        self.assertIn("<h1>EPM – Notfallplan", d["html"])
        self.assertIn("<pre><code>cd ~/notfall &amp;&amp; sudo ./epm-notfall-aufbau.sh</code></pre>", d["html"])
        self.assertIn("<table>", d["html"])                    # Checkliste zum Ausdrucken
        self.assertNotIn("<script", d["html"])
        r = self.a.get("/api/system/notfallplan/?art=pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertIn("Teil C", self.a.get("/api/system/notfallplan/?art=md").content.decode())
        # Plan im Repository und im Backend gleich (docs/ gibt es im Image nicht)
        docs = REPO / "docs" / "NOTFALLPLAN.md"
        if docs.exists():
            self.assertEqual(docs.read_text(encoding="utf-8"), notfallplan.markdown())
        self.assertIn("&lt;b&gt;", notfallplan.zu_html("Text mit <b>"))


@unittest.skipUnless(AGENT.exists() and shutil.which("gpg") and shutil.which("openssl"),
                     "Systemagent nur im Repo, GnuPG und openssl nötig")
class NotfallAgent(Backupverzeichnis):
    def setUp(self):
        super().setUp()
        self.modul = agent_modul()
        self.basis = Path(tempfile.mkdtemp(prefix="epm-basis-"))
        os.symlink(self.ordner, self.basis / "system")
        b = self.basis
        (b / ".env").write_text("COMPOSE_FILE=compose.yaml\nEPM_VERSION=0.9.2-bbbbbbb\n")
        shutil.copy(REPO / "rollout" / "projekt" / "compose.yaml", b / "compose.yaml")
        (b / "secrets").mkdir()
        (b / "secrets" / "db_password").write_text(DB_PASSWORT)
        (b / "secrets" / "django_secret_key").write_text(DJANGO_SECRET)
        (b / "backup").mkdir()
        for n in (f"epm-db_{ST}.dump.gpg", f"epm-dokumente_{ST}.tar.gz.gpg", f"epm_{ST}.sha256"):
            (b / "backup" / n).write_bytes(b"verschluesselt" * 10)
        (b / "ocr-modelle" / "detection").mkdir(parents=True)
        (b / "ocr-modelle" / "detection" / "det.onnx").write_bytes(b"ONNX")
        # Code des Servers (wie /srv/epm-code): die echten Rollout-Dateien
        self.code = b / "code"
        shutil.copytree(REPO / "rollout", self.code / "rollout", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (self.code / "werkzeuge").mkdir(parents=True)
        shutil.copy(REPO / "werkzeuge" / "epm-update.sh", self.code / "werkzeuge")
        (self.code / "docs").mkdir()
        shutil.copy(REPO / "backend" / "system" / "notfallplan.md", self.code / "docs" / "NOTFALLPLAN.md")
        (self.code / "VERSION").write_text("0.9.2\n")
        # eigene CA
        self.ca = b / "ca"
        self.ca.mkdir()
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                        "-keyout", str(self.ca / "epm-ca.key"), "-out", str(self.ca / "epm-ca.crt"), "-subj", "/CN=EPM CA",
                        "-days", "30"], capture_output=True, check=True)
        self.konf = b / "konf"
        (b / "epm.conf").write_text('EPM_HOSTNAME="epm"\nEPM_WEB_NAME="epm.test"\nEPM_MGMT_IF="enp0s8"\n'
                                    'EPM_MGMT_IP="192.168.56.10"\nEPM_NTP_SERVER="10.0.0.1"\nEPM_BASE="/srv/epm"\n'
                                    'EPM_PROXY_PASSWORT="nie-ins-paket-99"\n')

    def tearDown(self):
        shutil.rmtree(self.basis, ignore_errors=True)
        super().tearDown()

    def agent(self, mit_passwort=True):
        a = self.modul.Agent(str(self.basis), konf=str(self.konf))
        a.code, a.ca_ordner, a.konf_datei = str(self.code), str(self.ca), str(self.basis / "epm.conf")
        if mit_passwort:
            a.passwort_setzen(PASSWORT, "admin", lambda t: None)
        a.konf_ordner()
        (self.konf / "ziel.json").write_text(json.dumps({"url": "https://cloud.example.org/dav", "benutzer": "epm",
                                                         "ordner": "EPM", "von": "02:00", "bis": "05:00"}))
        (self.konf / "rclone.conf").write_text(f"[epm-ziel]\ntype = webdav\npass = {ZIEL_PASS}\n")
        echt = a.befehl

        def befehl(args, **kw):
            if args[:2] == ["docker", "save"]:
                Path(args[3]).write_bytes(b"IMAGES:" + " ".join(args[4:]).encode())
                return 0, ""
            if args[:3] == ["docker", "image", "inspect"]:
                return 0, "1000\n2000\n3000\n"
            return echt(args, **kw)

        a.befehl = befehl

        def debs(ziel, zeile):
            os.makedirs(ziel, exist_ok=True)
            Path(ziel, "docker-ce_1.0_amd64.deb").write_bytes(b"deb")
            return ["Debian-Paket rclone (Probe)"]

        a.debs_sammeln = debs
        return a

    def auspacken(self, datei):
        ziel = self.basis / "aus"
        ziel.mkdir()
        with tarfile.open(datei) as tar:
            for g in tar.getmembers():
                self.assertFalse(g.name.startswith("/") or ".." in g.name.split("/"), g.name)
                self.assertTrue(g.isreg() or g.isdir(), g.name)
            tar.extractall(ziel, filter="data")
        return ziel

    def test_paket_inhalt_pruefsummen_keine_geheimnisse(self):
        a = self.agent()
        ausgabe = []
        rc, text = a.notfallpaket(True, "a" * 32, ausgabe.append)
        self.assertEqual(rc, 0, "".join(ausgabe))
        stand = json.loads((self.ordner / "status" / "notfall.json").read_text())
        datei = self.ordner / "download" / stand["datei"]
        self.assertRegex(stand["datei"], r"^epm-notfall-0\.9\.2-bbbbbbb-\d{4}-\d{2}-\d{2}_\d{4}\.tar$")
        self.assertEqual(stat.S_IMODE(datei.stat().st_mode), 0o640)
        self.assertEqual(stand["groesse"], datei.stat().st_size)
        self.assertFalse(any(p.name.startswith(".notfall-") for p in (self.basis / "images").iterdir()))  # Arbeitsordner weg
        aus = self.auspacken(datei)
        # Prüfsummen über alles außer SHA256SUMS
        summen = dict(reversed(z.split("  ", 1)) for z in (aus / "SHA256SUMS").read_text().splitlines())
        import hashlib
        alle = sorted(str(p.relative_to(aus)) for p in aus.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
        self.assertEqual(sorted(summen), alle)
        for rel, soll in summen.items():
            self.assertEqual(hashlib.sha256((aus / rel).read_bytes()).hexdigest(), soll, rel)
        # Inhalt
        inhalt = json.loads((aus / "INHALT.json").read_text())
        self.assertEqual((inhalt["epm_version"], inhalt["mit_sicherung"], inhalt["sicherung"]), ("0.9.2-bbbbbbb", True, ST))
        self.assertEqual(inhalt["images"], ["postgres:18-alpine", "epm-backend:0.9.2-bbbbbbb", "epm-web:0.9.2-bbbbbbb"])
        self.assertIn("Debian-Paket rclone (Probe)", inhalt["fehlt"])
        self.assertIn("NOTFALLPLAN.pdf (Backend nicht erreichbar)", inhalt["fehlt"])
        self.assertEqual((aus / "images" / "images.tar").read_bytes(),
                         b"IMAGES:postgres:18-alpine epm-backend:0.9.2-bbbbbbb epm-web:0.9.2-bbbbbbb")
        for rel in ("TAG", "VERSION", "rollout/01-basis.sh", "rollout/epm-systemagent.py", "rollout/projekt/compose.yaml",
                    "werkzeuge/epm-update.sh", "debs/docker-ce_1.0_amd64.deb", "ocr-modelle/detection/det.onnx",
                    f"sicherung/epm-sicherung_{ST}.tar", "konfiguration/epm.conf", "konfiguration/einstellungen.json",
                    "ca/epm-ca.crt", "ca/epm-ca.key.gpg", "NOTFALLPLAN.md"):
            self.assertTrue((aus / rel).is_file(), rel)
        self.assertTrue(os.access(aus / "epm-notfall-aufbau.sh", os.X_OK))
        self.assertTrue(os.access(aus / "rollout" / "04-projekt.sh", os.X_OK))
        with tarfile.open(aus / "sicherung" / f"epm-sicherung_{ST}.tar") as t:
            self.assertEqual(sorted(t.getnames()), sorted([f"epm-db_{ST}.dump.gpg", f"epm-dokumente_{ST}.tar.gz.gpg",
                                                          f"epm_{ST}.sha256"]))
        konf = (aus / "konfiguration" / "epm.conf").read_text()
        self.assertIn('EPM_WEB_NAME="epm.test"', konf)
        self.assertNotIn("EPM_PROXY_PASSWORT", konf)
        einstellungen = json.loads((aus / "konfiguration" / "einstellungen.json").read_text())
        self.assertEqual(einstellungen["uebertragungsziel"]["url"], "https://cloud.example.org/dav")
        # keine Geheimnisse – in keiner Datei, auch nicht im Plan oder der Konfiguration
        ca_schluessel = (self.ca / "epm-ca.key").read_text().splitlines()[1]
        for p in aus.rglob("*"):
            if p.is_file():
                inhalt_bytes = p.read_bytes()
                for geheim in (PASSWORT, DB_PASSWORT, DJANGO_SECRET, ZIEL_PASS, "nie-ins-paket-99", ca_schluessel):
                    self.assertNotIn(geheim.encode(), inhalt_bytes, f"{geheim[:12]}… in {p.relative_to(aus)}")
        # der CA-Schlüssel lässt sich mit dem Sicherungs-Passwort entschlüsseln
        heim = tempfile.mkdtemp(prefix="epm-gpg-")
        try:
            p = subprocess.run(["gpg", "--homedir", heim, "--batch", "--quiet", "--pinentry-mode", "loopback",
                                "--passphrase-fd", "0", "-d", str(aus / "ca" / "epm-ca.key.gpg")], input=PASSWORT.encode(),
                               capture_output=True, timeout=60)
            self.assertEqual(p.stdout, (self.ca / "epm-ca.key").read_bytes(), p.stderr)
        finally:
            subprocess.run(["gpgconf", "--homedir", heim, "--kill", "all"], capture_output=True)
            shutil.rmtree(heim, ignore_errors=True)
        # Aufbauskript aus dem Paket: Probelauf ohne root, ohne Netz, ohne etwas zu ändern
        p = subprocess.run(["bash", str(aus / "epm-notfall-aufbau.sh"), "--probelauf"], capture_output=True, text=True,
                           timeout=120, cwd=aus, env={**os.environ, "EPM_SICHERUNG_PASSWORT": ""})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for erwartet in ("Prüfsummen in Ordnung · EPM 0.9.2-bbbbbbb", "debs/", "01-basis.sh", "02-docker.sh",
                         "04-projekt.sh", "docker load -i", f"notfall-einspielen epm-sicherung_{ST}.tar",
                         "Dieselbe CA wie bisher", "Probelauf beendet"):
            self.assertIn(erwartet, p.stdout)
        # ein verändertes Paket lehnt das Skript ab
        (aus / "rollout" / "04-projekt.sh").write_text("#!/bin/sh\necho boese\n")
        p = subprocess.run(["bash", str(aus / "epm-notfall-aufbau.sh"), "--probelauf"], capture_output=True, text=True,
                           timeout=120, cwd=aus)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("Paket beschädigt", p.stdout)

    def test_ohne_passwort_kein_ca_schluessel_ohne_sicherung(self):
        a = self.agent(mit_passwort=False)
        rc, _ = a.notfallpaket(False, "b" * 32, lambda t: None)
        self.assertEqual(rc, 0)
        stand = json.loads((self.ordner / "status" / "notfall.json").read_text())
        self.assertFalse(stand["mit_sicherung"])
        self.assertTrue(any("CA-Schlüssel" in f for f in stand["fehlt"]))
        with tarfile.open(self.ordner / "download" / stand["datei"]) as t:
            namen = t.getnames()
        self.assertIn("ca/epm-ca.crt", namen)
        self.assertNotIn("ca/epm-ca.key.gpg", namen)
        self.assertFalse(any(n.startswith("sicherung") for n in namen))

    def test_probelauf_status_und_pruefungen(self):
        a = self.agent()
        a.trocken = True
        rc, text = a.ausfuehren("notfallpaket", lambda t: None, "c" * 32, parameter={"mit_sicherung": True})
        self.assertEqual(rc, 0)
        self.assertIn("Probelauf: kein Notfallpaket erstellt", text)
        self.assertEqual(list((self.ordner / "download").iterdir()), [])
        n = a.notfall_stand()
        self.assertEqual((n["letztes"], n["bereit"], n["eigene_ca"], n["passwort"]), (None, [], True, True))
        self.assertGreater(n["schaetzung"], 400 * 1024 * 1024)
        # ohne laufende Version bzw. ohne Rollout-Dateien: nichts
        (self.basis / ".env").write_text("EPM_VERSION=latest\n")
        self.assertEqual(self.modul.Agent(str(self.basis)).notfallpaket(True, "d" * 32, lambda t: None)[0], 2)
        (self.basis / ".env").write_text("EPM_VERSION=0.9.2-bbbbbbb\n")
        a.trocken = False
        a.code = str(self.basis / "fehlt")
        rc, text = a.notfallpaket(True, "e" * 32, lambda t: None)
        self.assertEqual(rc, 1)
        self.assertIn("Rollout-Dateien fehlen", text)
        # Notfallpakete liegen 6 Stunden bereit, andere Dateien 2
        import time
        alt = time.time() - 3 * 3600
        for n in ("epm-notfall-0.9.2-bbbbbbb-2026-10-10_1200.tar", f"epm-sicherung_{ST}.tar"):
            (self.ordner / "download" / n).write_bytes(b"x")
            os.utime(self.ordner / "download" / n, (alt, alt))
        a.austausch_aufraeumen()
        self.assertEqual([p.name for p in (self.ordner / "download").iterdir()],
                         ["epm-notfall-0.9.2-bbbbbbb-2026-10-10_1200.tar"])
        self.assertEqual(a.notfall_einspielen(str(self.basis / "gibt-es-nicht.tar"), None, lambda t: None)[0], 2)

    def test_echter_agent_im_probelauf(self):
        host_status_schreiben(self.ordner, notfall={"schaetzung": 1000})
        r = self.a.post("/api/system/notfall/", {"mit_sicherung": True, "kennwort": KENNWORT, "code": self.admin_codes[0]},
                        format="json")
        self.assertEqual(r.status_code, 201, r.content)
        p = subprocess.run(["python3", str(AGENT), "auftraege", "--basis", str(self.basis), "--trocken"],
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.a.get("/api/system/auftraege/")
        auftrag = Systemauftrag.objects.get(aktion="notfallpaket")
        self.assertEqual(auftrag.status, "erledigt", auftrag.ausgabe)
        self.assertTrue(auftrag.probelauf)
