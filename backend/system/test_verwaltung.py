"""Systemverwaltung ohne SSH (Wunsch 10.10.2026, F179): Sicherungen mit Mehrfachauswahl löschen, Dienste einzeln neu
starten, Version zurückschalten, Update-Paket und OCR-Modelle hochladen und einspielen, Zertifikat erneuern und
importieren, Protokolle ansehen – Rechte, Prüfungen, Audit-Log und der echte Systemagent (Probelauf bzw. echt in eigenen
Verzeichnissen). Schlüssel dürfen nie in der Datenbank landen."""
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import timedelta
from pathlib import Path

from django.utils import timezone

from audit.models import SystemEreignis
from epm.pruefhilfen import KENNWORT, client_fuer

from .models import Systemauftrag, Systemhinweis
from .test_sicherung import Backupverzeichnis, eine_sicherung
from .tests import AGENT

ALT, MITTE, NEU = "2026-09-20_020000", "2026-09-25_020000", "2026-10-01_020000"


def agent_modul():
    spec = importlib.util.spec_from_file_location("epm_systemagent", AGENT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def tar_mit(dateien: dict, verweise: dict | None = None) -> bytes:
    puffer = io.BytesIO()
    with tarfile.open(fileobj=puffer, mode="w") as tar:
        for name, inhalt in dateien.items():
            info = tarfile.TarInfo(name)
            info.size = len(inhalt)
            tar.addfile(info, io.BytesIO(inhalt))
        for name, ziel in (verweise or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = ziel
            tar.addfile(info)
    return puffer.getvalue()


GUTES_PAKET = {"./TAG": b"0.9.1-1a2b3c4\n", "./VERSION": b"0.9.1\n", "./SHA256SUMS": b"", "./images.tar": b"IMAGES",
               "./rollout/04-projekt.sh": b"#!/bin/sh\n", "./werkzeuge/epm-update.sh": b"#!/bin/sh\n"}


def host_status_schreiben(ordner, **extra):
    """system.json, wie der Agent es schreibt (nur die Teile, die hier zählen)."""
    daten = {"zeit": timezone.now().isoformat(), "rechner": "epm", "trocken": True,
             "versionen": {"verfuegbar": True, "aktiv": "0.9.2-bbbbbbb", "quelle": "git", "liste": [
                 {"tag": "0.9.2-bbbbbbb", "erstellt": "2026-10-09", "backend": True, "web": True, "aktiv": True,
                  "vollstaendig": True},
                 {"tag": "0.9.1-aaaaaaa", "erstellt": "2026-10-01", "backend": True, "web": True, "aktiv": False,
                  "vollstaendig": True},
                 {"tag": "0.9.0-ccccccc", "erstellt": "2026-09-20", "backend": True, "web": False, "aktiv": False,
                  "vollstaendig": False}]},
             "zertifikat": {"vorhanden": True, "ca_schluessel": False, "tage": 200}}
    daten.update(extra)
    (ordner / "status" / "system.json").write_text(json.dumps(daten))


class SicherungenLoeschen(Backupverzeichnis):
    url = "/api/backup/loeschen/"

    def drei(self):
        return self.status_schreiben(sicherungen=[eine_sicherung(NEU, alter_h=2), eine_sicherung(MITTE, alter_h=120),
                                                  eine_sicherung(ALT, alter_h=260, verschluesselt=False)])

    def test_rechte_und_pruefungen(self):
        self.drei()
        m = client_fuer(self.mediziner)
        self.assertEqual(m.post(self.url, {"stempel": [ALT]}, format="json").status_code, 403)
        code = self.admin_codes[0]
        faelle = [None, "2026-09-20_020000", [], ["../../etc/passwd"], ["2026-09-20_0200;rm"], [ALT, ALT], [1],
                  ["2026-09-21_020000"], [NEU], [ALT, NEU], [f"x{i}" for i in range(201)]]
        for stempel in faelle:
            with self.subTest(stempel=stempel):
                r = self.a.post(self.url, {"stempel": stempel, "kennwort": KENNWORT, "code": code}, format="json")
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn("stempel", r.json())
        self.assertIn("jüngste", self.a.post(self.url, {"stempel": [NEU]}, format="json").json()["stempel"])
        # ohne Passwort und zweiten Faktor kein Auftrag
        r = self.a.post(self.url, {"stempel": [ALT]}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["kennwort"]))
        self.assertEqual(self.auftragsdateien(), [])
        # Agent meldet sich nicht: nichts beauftragen (würde sonst irgendwann später löschen)
        daten = self.drei()
        daten["zeit"] = (timezone.now() - timedelta(minutes=10)).isoformat()
        (self.ordner / "status" / "sicherung.json").write_text(json.dumps(daten))
        r = self.a.post(self.url, {"stempel": [ALT], "kennwort": KENNWORT, "code": code}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.auftragsdateien(), [])

    def test_auftrag_und_audit_log(self):
        self.drei()
        r = self.a.post(self.url, {"stempel": [MITTE, ALT], "kennwort": KENNWORT, "code": self.admin_codes[0]},
                        format="json")
        self.assertEqual(r.status_code, 201, r.content)
        datei = self.auftragsdatei()
        self.assertEqual((datei["aktion"], datei["parameter"]), ("sicherung_loeschen", {"stempel": [ALT, MITTE]}))
        e = SystemEreignis.objects.get(art="backup", details__ereignis="angefordert")
        self.assertEqual((e.details["anzahl"], e.details["groesse"], e.details["unverschluesselt"], e.details["bestaetigt"]),
                         (2, 8192, 1, True))
        self.assertEqual(e.objekt, "2 Sicherungen")
        texte = [x["beschreibung"] for x in self.a.get("/api/protokoll/?gruppe=backup").json()["results"]]
        self.assertIn(f"2 Sicherung(en) zum Löschen angefordert ({ALT}, {MITTE}; zusammen 0 MB), mit Passwort und 2FA "
                      "bestätigt", texte)
        # in der Liste der Tätigkeiten der Backup-Seite; nicht doppelt
        d = self.a.get("/api/backup/").json()
        self.assertEqual(d["auftraege"][0]["aktion"], "sicherung_loeschen")
        self.assertEqual(d["aktionen"]["sicherung_loeschen"]["bestaetigung"], "2fa")
        r = self.a.post(self.url, {"stempel": [ALT], "kennwort": KENNWORT, "code": self.admin_codes[1]}, format="json")
        self.assertEqual(r.status_code, 409)


class EchterAgentLoeschen(Backupverzeichnis):
    """Backend legt ab → echter Agent löscht im eigenen Backup-Ordner (ohne Probelauf) – nur die Dateien der gewählten
    Sicherungen, nie über einen symbolischen Link hinaus, nie die jüngste."""

    def setUp(self):
        super().setUp()
        self.basis = Path(tempfile.mkdtemp(prefix="epm-basis-"))
        os.symlink(self.ordner, self.basis / "system")
        self.konf = self.basis / "konf"
        b = self.basis / "backup"
        b.mkdir()
        for st in (ALT, MITTE, NEU):
            for n in (f"epm-db_{st}.dump.gpg", f"epm-dokumente_{st}.tar.gz.gpg", f"epm_{st}.sha256"):
                (b / n).write_bytes(b"x" * 1000)
        (b / "notizen.txt").write_text("bleibt")
        # ein Verweis mit dem Namen einer Datei der Sicherung zeigt nach draußen: wird nicht verfolgt
        self.draussen = self.basis / "wichtig.json"
        self.draussen.write_text("{}")
        os.symlink(self.draussen, b / f"epm_{ALT}.json")
        os.utime(b / f"epm-db_{NEU}.dump.gpg")

    def tearDown(self):
        shutil.rmtree(self.basis, ignore_errors=True)
        super().tearDown()

    def agent(self, *extra):
        p = subprocess.run([sys.executable, str(AGENT), "auftraege", "--basis", str(self.basis), "--konf", str(self.konf),
                            *extra], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr)

    def auftrag_direkt(self, parameter):
        """Auftragsdatei ohne Backend – so prüft der Agent selbst."""
        kennung = os.urandom(16).hex()
        (self.ordner / "auftraege" / f"{kennung}.json").write_text(json.dumps(
            {"id": kennung, "aktion": "sicherung_loeschen", "parameter": parameter, "angefordert_von": "admin"}))
        return kennung

    def ergebnis(self, kennung):
        return json.loads((self.ordner / "status" / "auftraege" / f"{kennung}.json").read_text())

    def test_loeschen(self):
        modul = agent_modul()
        a = modul.Agent(str(self.basis), konf=str(self.konf))
        self.assertEqual([s["stempel"] for s in a.sicherungen()][0], NEU)
        a.sicherung_status_schreiben()
        # der Agent prüft selbst: unbekannt, Pfadtricks, jüngste
        falsch = self.auftrag_direkt({"stempel": ["../../wichtig"]})
        juengste = self.auftrag_direkt({"stempel": [MITTE, NEU]})
        self.agent()
        self.assertIn("Ungültige Auswahl", self.ergebnis(falsch)["ergebnis"])
        self.assertIn("jüngste Sicherung bleibt", self.ergebnis(juengste)["ergebnis"])
        self.assertEqual(len(list((self.basis / "backup").glob("epm-db_*"))), 3)
        # Probelauf: nichts gelöscht
        probe = self.auftrag_direkt({"stempel": [ALT]})
        self.agent("--trocken")
        self.assertEqual((self.ergebnis(probe)["status"], self.ergebnis(probe)["ergebnis"]),
                         ("erledigt", "Probelauf: 1 Sicherung(en) nicht gelöscht."))
        self.assertTrue((self.basis / "backup" / f"epm-db_{ALT}.dump.gpg").exists())
        # über das Backend, echt
        r = self.a.post("/api/backup/loeschen/", {"stempel": [ALT, MITTE], "kennwort": KENNWORT,
                                                  "code": self.admin_codes[0]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.agent()
        d = self.a.get("/api/backup/").json()
        auftrag = d["auftraege"][0]
        self.assertEqual(auftrag["status"], "erledigt", auftrag["ausgabe"])
        self.assertIn("2 Sicherung(en) gelöscht", auftrag["ergebnis"])
        self.assertIn("Übersprungen (keine gewöhnliche Datei)", auftrag["ausgabe"])
        self.assertEqual([s["stempel"] for s in d["sicherungen"]], [NEU])
        rest = sorted(p.name for p in (self.basis / "backup").iterdir() if not p.name.startswith("."))
        self.assertEqual(rest, sorted([f"epm-db_{NEU}.dump.gpg", f"epm-dokumente_{NEU}.tar.gz.gpg", f"epm_{NEU}.sha256",
                                       f"epm_{ALT}.json", "notizen.txt"]))
        self.assertEqual(self.draussen.read_text(), "{}")
        self.assertTrue(SystemEreignis.objects.filter(art="backup", details__ereignis="abgeschlossen",
                                                      details__aktion="sicherung_loeschen").exists())


class Wartung(Backupverzeichnis):
    """Dienste, Versionen, Zertifikat, Protokolle: Rechte, Prüfungen, Aufträge."""

    def test_nur_mit_recht_systemverwaltung(self):
        m = client_fuer(self.mediziner)
        for methode, url in (("post", "/api/system/dienste/neustart/"), ("post", "/api/system/versionen/zurueck/"),
                             ("post", "/api/system/pakete/erstellen/"), ("get", "/api/system/pakete/epm-paket-0.9.1-aaaaaaa.tar/"),
                             ("post", "/api/system/hochladen/"), ("post", "/api/system/zertifikat/erneuern/"),
                             ("post", "/api/system/zertifikat/importieren/"), ("post", "/api/system/protokolle/"),
                             ("get", "/api/system/protokolle/")):
            with self.subTest(url=url):
                r = m.post(url, {}, format="json") if methode == "post" else m.get(url)
                self.assertEqual(r.status_code, 403)
        self.assertEqual(self.auftragsdateien(), [])

    def test_dienst_neu_starten(self):
        url = "/api/system/dienste/neustart/"
        for dienst in (None, "nginx", "backend; reboot", ["backend"]):
            with self.subTest(dienst=dienst):
                self.assertEqual(self.a.post(url, {"dienst": dienst, "minuten": 0}, format="json").status_code, 400)
        r = self.a.post(url, {"dienst": "ocr", "minuten": 0}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["kennwort"]))
        r = self.a.post(url, {"dienst": "ocr", "minuten": 5, "kennwort": KENNWORT, "code": self.admin_codes[0]},
                        format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"], {"dienst": "ocr", "minuten": 5})
        self.assertIn("kurz nicht erreichbar", Systemhinweis.aktiv().text)
        texte = [x["beschreibung"] for x in self.a.get("/api/protokoll/?gruppe=system").json()["results"]]
        self.assertIn("Neustart des Dienstes „ocr“ angefordert, Beginn in 5 Min., mit Passwort und 2FA bestätigt", texte)

    def test_version_zurueckschalten(self):
        url = "/api/system/versionen/zurueck/"
        daten = {"kennwort": KENNWORT, "code": self.admin_codes[0], "minuten": 0}
        self.assertEqual(self.a.post(url, {**daten, "tag": "latest"}, format="json").status_code, 400)
        # ohne laufenden Agenten nicht
        self.assertEqual(self.a.post(url, {**daten, "tag": "0.9.1-aaaaaaa"}, format="json").status_code, 409)
        host_status_schreiben(self.ordner)
        for tag, text in (("0.9.3-ddddddd", "nicht (vollständig)"), ("0.9.0-ccccccc", "nicht (vollständig)"),
                          ("0.9.2-bbbbbbb", "läuft bereits")):
            with self.subTest(tag=tag):
                r = self.a.post(url, {**daten, "tag": tag}, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn(text, r.json()["tag"])
        r = self.a.post(url, {**daten, "tag": "0.9.1-aaaaaaa"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"], {"tag": "0.9.1-aaaaaaa", "minuten": 0})
        texte = [x["beschreibung"] for x in self.a.get("/api/protokoll/?gruppe=system").json()["results"]]
        self.assertIn("Zurückschalten auf Version 0.9.1-aaaaaaa angefordert (bisher 0.9.2-bbbbbbb), mit Passwort und 2FA "
                      "bestätigt", texte)
        # Übersicht: Beschreibung mit „vorher Sicherung“
        d = self.a.get("/api/system/uebersicht/").json()
        self.assertTrue(d["verwaltung"]["epm_zurueck"]["sichern"])
        self.assertEqual(d["host"]["versionen"]["aktiv"], "0.9.2-bbbbbbb")
        self.assertEqual(d["dienste"], ["backend", "web", "ocr", "db"])

    def test_zertifikat(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
        from datetime import datetime, timezone as tz

        def zert(name, schluessel, aussteller=None, aussteller_schluessel=None):
            jetzt = datetime.now(tz.utc)
            return (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
                    .issuer_name(aussteller or x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
                    .public_key(schluessel.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(jetzt).not_valid_after(jetzt + timedelta(days=365))
                    .sign(aussteller_schluessel or schluessel, hashes.SHA256()))

        def pem(z):
            return z.public_bytes(serialization.Encoding.PEM).decode()

        def key_pem(k):
            return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()).decode()

        ca_key, srv_key, fremd_key = (ec.generate_private_key(ec.SECP256R1()) for _ in range(3))
        ca = zert("Test CA", ca_key)
        srv = zert("epm.test", srv_key, ca.subject, ca_key)
        url = "/api/system/zertifikat/importieren/"
        b = {"kennwort": KENNWORT, "code": self.admin_codes[0]}
        faelle = [({"zertifikat": "kein PEM", "schluessel": key_pem(srv_key)}, "zertifikat"),
                  ({"zertifikat": pem(srv), "schluessel": key_pem(fremd_key)}, "schluessel"),
                  ({"zertifikat": pem(srv), "schluessel": key_pem(srv_key), "ca": pem(zert("Andere", fremd_key))}, "ca"),
                  ({"zertifikat": pem(srv) * 50, "schluessel": key_pem(srv_key)}, "zertifikat")]
        for daten, feld in faelle:
            with self.subTest(feld=feld):
                r = self.a.post(url, {**b, **daten}, format="json")
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn(feld, r.json())
        r = self.a.post(url, {**b, "zertifikat": pem(srv), "schluessel": key_pem(srv_key), "ca": pem(ca)}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        datei = self.auftragsdatei()
        self.assertEqual(datei["geheim"]["schluessel"], key_pem(srv_key))
        self.assertEqual(datei["parameter"], {"mit_ca": True})
        self.nirgends_in_der_datenbank("PRIVATE KEY")
        self.nirgends_in_der_datenbank(key_pem(srv_key).splitlines()[1])
        e = SystemEreignis.objects.get(details__aktion="zertifikat_importieren", details__ereignis="angefordert")
        self.assertEqual((e.details["inhaber"], e.details["aussteller"]), ("CN=epm.test", "CN=Test CA"))
        # erneuern geht nur mit eigener CA
        host_status_schreiben(self.ordner)
        r = self.a.post("/api/system/zertifikat/erneuern/", b, format="json")
        self.assertEqual(r.status_code, 409)
        host_status_schreiben(self.ordner, zertifikat={"vorhanden": True, "ca_schluessel": True})
        r = self.a.post("/api/system/zertifikat/erneuern/", {"kennwort": KENNWORT, "code": self.admin_codes[1]},
                        format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_protokolle(self):
        url = "/api/system/protokolle/"
        self.assertEqual(self.a.get(url).json()["zeilen"], [100, 500, 2000])
        for daten in ({"quelle": "/etc/shadow", "zeilen": 100}, {"quelle": "backend", "zeilen": 99},
                      {"quelle": "backend", "zeilen": True}):
            with self.subTest(daten=daten):
                self.assertEqual(self.a.post(url, daten, format="json").status_code, 400)
        # nur lesend, ohne Bestätigung; mehrere gleichzeitig möglich
        r1 = self.a.post(url, {"quelle": "backend", "zeilen": 100}, format="json")
        r2 = self.a.post(url, {"quelle": "web", "zeilen": 100}, format="json")
        self.assertEqual((r1.status_code, r2.status_code), (201, 201))
        a = Systemauftrag.objects.get(kennung=r1.json()["kennung"])
        self.assertEqual(self.a.get(f"{url}{a.kennung}/").status_code, 404)    # noch nicht abgerufen
        datei = self.ordner / "status" / "protokolle" / f"{a.kennung.hex}.log"
        datei.parent.mkdir()
        datei.write_text("2026-10-10T08:00:00 backend | GET /api/start/ 200\n")
        d = self.a.get(f"{url}{a.kennung}/").json()
        self.assertEqual((d["quelle"], d["zeilen"]), ("backend", 100))
        self.assertIn("GET /api/start/", d["text"])
        r = self.a.get(f"{url}{a.kennung}/?herunterladen=1")
        self.assertEqual(r["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn("attachment", r["Content-Disposition"])
        texte = [x["beschreibung"] for x in self.a.get("/api/protokoll/?gruppe=system").json()["results"]]
        self.assertIn("Protokoll heruntergeladen: Container backend (Django)", texte)
        self.assertIn("Protokoll abgerufen: Container web (Nginx) (letzte 100 Zeilen)", texte)


class Hochladen(Backupverzeichnis):
    """Update-Paket und OCR-Modelle statt per scp: in Stücken hochladen, einspielen lassen; der echte Agent prüft im
    Probelauf den Inhalt und räumt den Upload weg."""

    def hochladen(self, inhalt: bytes, name: str, art: str) -> str:
        r = self.a.post("/api/system/hochladen/", {"art": art, "name": name, "groesse": len(inhalt)}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        kennung = r.json()["upload"]
        for versatz in range(0, len(inhalt), 4000):
            r = self.a.put(f"/api/system/hochladen/{kennung}/?versatz={versatz}", inhalt[versatz:versatz + 4000],
                           content_type="application/octet-stream")
            self.assertEqual(r.status_code, 200, r.content)
        return kennung

    def agent(self):
        basis = Path(tempfile.mkdtemp(prefix="epm-basis-"))
        try:
            os.symlink(self.ordner, basis / "system")
            p = subprocess.run([sys.executable, str(AGENT), "auftraege", "--basis", str(basis), "--trocken"],
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.a.get("/api/system/auftraege/")      # Ergebnisse des Agenten übernehmen
            return basis, sorted(x.name for x in (basis / "images").iterdir()) if (basis / "images").exists() else []
        finally:
            shutil.rmtree(basis, ignore_errors=True)

    def test_pruefungen(self):
        url = "/api/system/hochladen/"
        for daten in ({"art": "sicherung", "name": "x.tar", "groesse": 5}, {"art": "paket", "name": "x.zip", "groesse": 5},
                      {"art": "paket", "name": "x.tar", "groesse": 0}, {"art": "ocr", "name": "x.tar", "groesse": 10 ** 12}):
            with self.subTest(daten=daten):
                self.assertEqual(self.a.post(url, daten, format="json").status_code, 400)
        kennung = self.hochladen(b"abc", "epm-paket-0.9.1-1a2b3c4.tar", "paket")
        # ein Update-Paket ist keine Sicherung: nicht in deren Liste, nicht dort einzulesen oder zu verwerfen
        self.assertEqual(self.a.get("/api/backup/").json()["uploads"], [])
        self.assertEqual(self.a.post(f"/api/backup/hochladen/{kennung}/einlesen/", {}, format="json").status_code, 404)
        self.assertEqual(self.a.put(f"/api/backup/hochladen/{kennung}/?versatz=3", b"d",
                                    content_type="application/octet-stream").status_code, 404)
        d = self.a.get("/api/system/uebersicht/").json()
        self.assertEqual([(u["upload"], u["art"], u["vollstaendig"]) for u in d["uploads"]], [(kennung, "paket", True)])
        # umgekehrt: eine hochgeladene Sicherung lässt sich hier nicht einspielen
        r = self.a.post("/api/backup/hochladen/", {"name": "epm-sicherung_x.tar", "groesse": 3}, format="json")
        self.assertEqual(self.a.post(f"/api/system/hochladen/{r.json()['upload']}/einspielen/", {}, format="json")
                         .status_code, 404)
        # verwerfen
        self.assertEqual(self.a.delete(f"/api/system/hochladen/{kennung}/").status_code, 204)
        self.assertFalse((self.ordner / "upload" / f"{kennung}.teil").exists())
        texte = [x["beschreibung"] for x in self.a.get("/api/protokoll/?gruppe=system").json()["results"]]
        self.assertIn("Hochladen begonnen (Update-Paket hochladen): epm-paket-0.9.1-1a2b3c4.tar", texte)
        self.assertIn("Hochgeladene Datei verworfen (Update-Paket hochladen): epm-paket-0.9.1-1a2b3c4.tar", texte)

    def test_paket_einspielen_im_probelauf(self):
        gut = self.hochladen(tar_mit(GUTES_PAKET), "epm-paket-0.9.1-1a2b3c4.tar", "paket")
        r = self.a.post(f"/api/system/hochladen/{gut}/einspielen/", {"minuten": 0}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["kennwort"]))
        r = self.a.post(f"/api/system/hochladen/{gut}/einspielen/", {"minuten": 0, "kennwort": KENNWORT,
                                                                      "code": self.admin_codes[0]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.auftragsdatei()["parameter"]["upload"], gut)
        self.assertEqual(self.a.delete(f"/api/system/hochladen/{gut}/").status_code, 409)   # wird gerade verarbeitet
        _basis, images = self.agent()
        a = Systemauftrag.objects.get(aktion="epm_paket")
        self.assertEqual(a.status, "erledigt", a.ausgabe)
        self.assertEqual(a.ergebnis, "Probelauf: Update-Paket 0.9.1-1a2b3c4 geprüft, nicht eingespielt.")
        self.assertIn("SHA-256", a.ausgabe)
        self.assertEqual(list((self.ordner / "upload").iterdir()), [])
        self.assertEqual(images, [])     # die geprüfte Kopie ist wieder weg
        # fremder Inhalt: Verweis, Pfad nach oben, unbekannte Datei, kein tar
        for inhalt, name in ((tar_mit(GUTES_PAKET, {"./rollout/boese": "/etc/shadow"}), "verweis"),
                             (tar_mit({**GUTES_PAKET, "../../etc/cron.d/x": b"x"}), "pfad"),
                             (tar_mit({**GUTES_PAKET, "./boese.sh": b"x"}), "unbekannt"),
                             (b"kein tar" * 200, "kaputt")):
            with self.subTest(fall=name):
                k = self.hochladen(inhalt, "epm-paket-x.tar", "paket")
                Systemauftrag.objects.filter(aktion="epm_paket").delete()
                r = self.a.post(f"/api/system/hochladen/{k}/einspielen/", {"minuten": 0, "kennwort": KENNWORT,
                                                                            "code": self.admin_codes[1 + len(name) % 4]},
                                format="json")
                self.drosselung_aufheben()
                self.assertEqual(r.status_code, 201, r.content)
                self.agent()
                a = Systemauftrag.objects.get(aktion="epm_paket")
                self.assertEqual(a.status, "fehler", a.ausgabe)
                self.assertIn("kein Update-Paket", a.ergebnis)
                self.assertEqual(list((self.ordner / "upload").iterdir()), [])

    def test_ocr_modelle_im_probelauf(self):
        k = self.hochladen(tar_mit({"modelle.json": b"{}", "dateien/detection/v5/det.onnx": b"ONNX"}),
                           "epm-ocr-modelle-abc.tar", "ocr")
        r = self.a.post(f"/api/system/hochladen/{k}/einspielen/", {}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.agent()
        a = Systemauftrag.objects.get(aktion="ocr_modelle")
        self.assertEqual((a.status, a.ergebnis), ("erledigt", "Probelauf: OCR-Modelle geprüft, nicht eingespielt."))


class AgentTeile(Backupverzeichnis):
    """Teile des Agenten einzeln: Inhalt von Paketen, Protokolle, Probeläufe der neuen Aufträge, Stand."""

    def setUp(self):
        super().setUp()
        self.modul = agent_modul()
        self.basis = Path(tempfile.mkdtemp(prefix="epm-basis-"))
        os.symlink(self.ordner, self.basis / "system")

    def tearDown(self):
        shutil.rmtree(self.basis, ignore_errors=True)
        super().tearDown()

    def test_tar_pruefen(self):
        pfad = self.basis / "p.tar"
        pruefen = self.modul.Agent.tar_pruefen
        pfad.write_bytes(tar_mit(GUTES_PAKET))
        fehler, namen, tag = pruefen(str(pfad), self.modul.PAKET_INHALT)
        self.assertIsNone(fehler)
        self.assertEqual(tag, "0.9.1-1a2b3c4")
        self.assertIn("rollout/04-projekt.sh", namen)
        for inhalt in (tar_mit({"/etc/passwd": b"x"}), tar_mit({"rollout/../../x": b"x"}),
                       tar_mit({}, {"rollout/a": "/"}), tar_mit({"TAG": b"x", "dateien/x": b"x"})):
            pfad.write_bytes(inhalt)
            self.assertIsNotNone(pruefen(str(pfad), self.modul.PAKET_INHALT)[0])
        pfad.write_bytes(tar_mit({"modelle.json": b"{}", "dateien/a/b.onnx": b"x"}))
        self.assertIsNone(pruefen(str(pfad), self.modul.OCR_INHALT)[0])

    def test_protokoll_nur_in_einer_datei(self):
        a = self.modul.Agent(str(self.basis))
        aufrufe = []

        def befehl(args, **kw):
            aufrufe.append(args)
            return 0, "".join(f"Zeile {i}\n" for i in range(5))

        a.befehl = befehl
        ausgabe = []
        kennung = "a" * 32
        rc, text = a.protokoll_abrufen("backend", 100, kennung, ausgabe.append)
        self.assertEqual((rc, text), (0, "Container backend (Django): 5 Zeilen."))
        self.assertEqual(aufrufe[0][-6:], ["logs", "--no-color", "--timestamps", "--tail", "100", "backend"])
        datei = self.ordner / "status" / "protokolle" / f"{kennung}.log"
        self.assertEqual(datei.read_text().count("\n"), 5)
        self.assertEqual(stat.S_IMODE(datei.stat().st_mode), 0o640)
        self.assertNotIn("Zeile 3", "".join(ausgabe))      # nicht in der Ausgabe des Auftrags
        rc, _ = a.protokoll_abrufen("systemagent", 500, "b" * 32, ausgabe.append)
        self.assertEqual(aufrufe[1][:6], ["journalctl", "--no-pager", "-o", "short-iso", "-n", "500"])
        self.assertIn("epm-systemagent.service", aufrufe[1])
        self.assertEqual(a.protokoll_abrufen("../x", 100, "c" * 32, ausgabe.append)[0], 2)
        self.assertEqual(a.protokoll_abrufen("backend", 7, "c" * 32, ausgabe.append)[0], 2)

    def test_probelaeufe(self):
        a = self.modul.Agent(str(self.basis), trocken=True)
        z = []
        self.assertEqual(a.ausfuehren("dienst_neustart", z.append, "d" * 32, parameter={"dienst": "ocr"})[0], 0)
        self.assertEqual(a.ausfuehren("dienst_neustart", z.append, "d" * 32, parameter={"dienst": "sh"})[0], 2)
        self.assertEqual(a.ausfuehren("epm_zurueck", z.append, "d" * 32, parameter={"tag": "0.9.1-aaaaaaa"}),
                         (0, "Probelauf: nicht auf 0.9.1-aaaaaaa zurückgeschaltet."))
        self.assertEqual(a.ausfuehren("epm_zurueck", z.append, "d" * 32, parameter={"tag": "; reboot"})[0], 2)
        self.assertEqual(a.ausfuehren("zertifikat_erneuern", z.append, "d" * 32)[0], 0)
        self.assertEqual(a.ausfuehren("zertifikat_importieren", z.append, "d" * 32, geheim={"zertifikat": "x"})[0], 2)
        self.assertEqual(a.ausfuehren("epm_paket_erstellen", z.append, "d" * 32), (0, "Probelauf: kein Paket erstellt."))
        # Paket ohne Upload, Upload einer anderen Art
        self.assertEqual(a.ausfuehren("epm_paket", z.append, "d" * 32, parameter={"upload": "../x"})[0], 2)
        (self.ordner / "upload" / f"{'e' * 32}.teil").write_bytes(b"x")
        (self.ordner / "upload" / f"{'e' * 32}.json").write_text(json.dumps({"art": "sicherung", "groesse": 1}))
        self.assertEqual(a.ausfuehren("epm_paket", z.append, "d" * 32, parameter={"upload": "e" * 32})[0], 2)
        self.assertTrue((self.ordner / "upload" / f"{'e' * 32}.teil").exists())
        # echt, aber ohne die Werkzeuge auf dem Server: klare Meldung statt Fehler
        echt = self.modul.Agent(str(self.basis))
        self.assertIn("nicht eingerichtet", echt.ausfuehren("zertifikat_importieren", z.append, "d" * 32, geheim={
            "zertifikat": "-----BEGIN CERTIFICATE-----\nx\n-----END CERTIFICATE-----\n",
            "schluessel": "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----\n"})[1])
        self.assertIn("Unbekannte Version", echt.ausfuehren("epm_zurueck", z.append, "d" * 32, parameter={"tag": "x"})[1])

    def test_stand_im_status(self):
        certs = self.basis / "nginx" / "certs"
        certs.mkdir(parents=True)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                        "-keyout", str(self.basis / "k.pem"), "-out", str(certs / "epm.crt"), "-subj", "/CN=epm.test",
                        "-days", "30", "-addext", "subjectAltName=DNS:epm.test"], capture_output=True, check=True)
        (self.basis / "images").mkdir()
        (self.basis / "images" / "epm-paket-0.9.1-1a2b3c4.tar").write_bytes(b"x" * 10)
        (self.basis / "images" / "epm-0.9.1-1a2b3c4.tar").write_bytes(b"x")
        a = self.modul.Agent(str(self.basis))
        z = a.zertifikat()
        self.assertTrue(z["vorhanden"] and z["selbst_signiert"])
        self.assertIn(z["tage"], (29, 30))
        self.assertIn("epm.test", z["namen"])
        self.assertEqual([p["tag"] for p in a.pakete()["erstellt"]], ["0.9.1-1a2b3c4"])
        (self.basis / "ocr-modelle" / "x").mkdir(parents=True)
        (self.basis / "ocr-modelle" / "x" / "a.onnx").write_bytes(b"abc")
        self.assertEqual((a.ocr_vorrat()["dateien"], a.ocr_vorrat()["groesse"]), (1, 3))
