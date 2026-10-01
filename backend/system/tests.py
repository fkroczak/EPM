"""Administration › System: Rechte, Übersicht, Aufträge an den Server (Agent simuliert und echt im Probelauf),
Wartung des EPM, Hinweise an alle Benutzer (echte Datenbank)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from django.test import override_settings
from django.utils import timezone

from accounts.models import Gruppenrecht, Rolle
from audit.models import SystemEreignis
from epm.pruefhilfen import Grundlage, benutzer, client_fuer, mit_zweitem_faktor
from epm.pruefhilfen import KENNWORT
from patienten.models import Dokument

from .models import Systemauftrag, Systemhinweis

AGENT = Path(__file__).resolve().parent.parent.parent / "rollout" / "epm-systemagent.py"


class Systemverzeichnis(Grundlage):
    """Je Test ein eigenes Verzeichnis wie auf dem Server: auftraege/ (Backend schreibt), status/ (Agent schreibt)."""

    def setUp(self):
        self.ordner = Path(tempfile.mkdtemp(prefix="epm-system-"))
        (self.ordner / "auftraege").mkdir()
        (self.ordner / "status" / "auftraege").mkdir(parents=True)
        self.einstellung = override_settings(EPM_SYSTEM=self.ordner)
        self.einstellung.enable()
        self.admin_codes = mit_zweitem_faktor(self.admin, anzahl_codes=6)
        self.a = client_fuer(self.admin)

    def tearDown(self):
        self.einstellung.disable()
        shutil.rmtree(self.ordner, ignore_errors=True)

    def drosselung_aufheben(self):
        """django-otp sperrt nach einem falschen Code kurz jeden weiteren Versuch (1 s); im Test sofort weiter."""
        from django_otp.plugins.otp_static.models import StaticDevice
        from django_otp.plugins.otp_totp.models import TOTPDevice

        for modell in (StaticDevice, TOTPDevice):
            modell.objects.filter(user=self.admin).update(throttling_failure_timestamp=None, throttling_failure_count=0)

    def auftragsdateien(self):
        return sorted(p.name for p in (self.ordner / "auftraege").glob("*.json"))


class Rechte(Systemverzeichnis):
    def test_nur_admin(self):
        self.assertIn("system_verwalten", self.admin.rechte)
        for user in (self.mediziner, self.mitarbeiter, self.betrachter):
            with self.subTest(rolle=user.rolle):
                self.assertNotIn("system_verwalten", user.rechte)
                c = client_fuer(user)
                self.assertEqual(c.get("/api/system/uebersicht/").status_code, 403)
                self.assertEqual(c.post("/api/system/auftraege/", {"aktion": "updates_suchen"}, format="json")
                                 .status_code, 403)
                self.assertEqual(c.post("/api/system/epm/", {"aufgabe": "schutz_pruefen"}, format="json")
                                 .status_code, 403)
        # Testzugang als Admin: nie Systemverwaltung
        test_admin = benutzer("testadmin", Rolle.ADMIN, ist_test=True)
        self.assertNotIn("system_verwalten", test_admin.rechte)
        self.assertEqual(client_fuer(test_admin).get("/api/system/uebersicht/").status_code, 403)

    def test_anderen_rollen_nicht_erteilbar(self):
        r = self.a.put("/api/rechte/", {"matrix": {"mediziner": {"system_verwalten": True}}}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Admin vorbehalten", str(r.json()))
        self.assertFalse(Gruppenrecht.objects.filter(recht="system_verwalten").exists())
        daten = self.a.get("/api/rechte/").json()
        self.assertEqual(daten["nur_rollen"]["system_verwalten"], ["admin"])
        self.assertFalse(daten["matrix"]["mediziner"]["system_verwalten"])
        # auch ein Eintrag direkt in der Datenbank wirkt nicht
        Gruppenrecht.objects.create(rolle=Rolle.MEDIZINER, recht="system_verwalten", erlaubt=True)
        self.assertNotIn("system_verwalten", self.mediziner.rechte)
        # Admin selbst darf es abgeben und wieder bekommen
        r = self.a.put("/api/rechte/", {"matrix": {"admin": {"system_verwalten": False}}}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.a.get("/api/system/uebersicht/").status_code, 403)
        self.a.put("/api/rechte/", {"matrix": {"admin": {"system_verwalten": True}}}, format="json")
        self.assertEqual(self.a.get("/api/system/uebersicht/").status_code, 200)


class Uebersicht(Systemverzeichnis):
    def test_ohne_agent_misst_der_container(self):
        d = self.a.get("/api/system/uebersicht/").json()
        self.assertIsNone(d["host"])
        self.assertEqual(d["agent"], {"verzeichnis": True, "erreichbar": False})
        self.assertIsNotNone(d["container"]["speicher"]["gesamt"])
        self.assertTrue(d["container"]["platten"])
        self.assertEqual(d["epm"]["migrationen_offen"], 0)
        self.assertEqual(d["epm"]["schutz"]["fehlend"], [])
        self.assertGreater(d["epm"]["schutz"]["erwartet"], 5)
        self.assertGreater(d["epm"]["datenbank"]["groesse"], 0)
        self.assertEqual(d["epm"]["patienten"]["in_betreuung"], 1)
        codes = {x["code"]: x for x in d["aktionen"]}
        self.assertEqual(codes["server_neustart"]["bestaetigung"], "2fa")
        self.assertTrue(codes["server_neustart"]["sichern"] and codes["server_neustart"]["warnen"])
        self.assertTrue(codes["sicherung"]["erlaubt"])
        self.assertIn("dokumente_pruefen", {x["code"] for x in d["aufgaben"]})

    def test_status_vom_server(self):
        status = {"zeit": timezone.now().isoformat(), "rechner": "epm", "cpu": {"kerne": 2, "last": [0.2, 0.1, 0.1],
                  "prozent": 7.5}, "updates": {"verfuegbar": True, "anzahl": 3, "sicherheit": 1}}
        (self.ordner / "status" / "system.json").write_text(json.dumps(status))
        d = self.a.get("/api/system/uebersicht/").json()
        self.assertTrue(d["host"]["aktuell"])
        self.assertTrue(d["agent"]["erreichbar"])
        self.assertEqual(d["host"]["updates"]["anzahl"], 3)
        # veraltet (Agent läuft nicht mehr)
        status["zeit"] = (timezone.now() - timedelta(minutes=10)).isoformat()
        (self.ordner / "status" / "system.json").write_text(json.dumps(status))
        d = self.a.get("/api/system/uebersicht/").json()
        self.assertFalse(d["host"]["aktuell"])
        self.assertFalse(d["agent"]["erreichbar"])
        (self.ordner / "status" / "verlauf.json").write_text(json.dumps({"punkte": [[1, 5, 40, 0.1, 30]]}))
        self.assertEqual(self.a.get("/api/system/verlauf/").json()["punkte"], [[1, 5, 40, 0.1, 30]])

    def test_angemeldete_sitzungen(self):
        from epm.pruefhilfen import echte_anmeldung

        codes = mit_zweitem_faktor(self.mitarbeiter)
        echte_anmeldung(self.mitarbeiter, codes[0])
        d = self.a.get("/api/system/uebersicht/").json()
        eintrag = next(s for s in d["angemeldet"] if s["benutzername"] == "mitarbeiter")
        self.assertEqual(eintrag["browser"], "Firefox 140 · Windows")
        self.assertEqual(self.a.delete(f"/api/system/sitzungen/{eintrag['id']}/").status_code, 204)
        d = self.a.get("/api/system/uebersicht/").json()
        self.assertFalse(any(s["benutzername"] == "mitarbeiter" for s in d["angemeldet"]))
        self.assertTrue(SystemEreignis.objects.filter(art="system", details__ereignis="sitzung_beendet").exists())


class Auftraege(Systemverzeichnis):
    def test_auftrag_ablegen_und_zurueckziehen(self):
        r = self.a.post("/api/system/auftraege/", {"aktion": "updates_suchen"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        auftrag = r.json()
        self.assertEqual(auftrag["status"], "wartet")
        self.assertEqual(auftrag["name"], "Nach Updates suchen")
        dateien = self.auftragsdateien()
        self.assertEqual(len(dateien), 1)
        inhalt = json.loads((self.ordner / "auftraege" / dateien[0]).read_text())
        self.assertEqual(inhalt["aktion"], "updates_suchen")
        self.assertEqual(inhalt["id"], auftrag["kennung"].replace("-", ""))
        # derselbe Auftrag nicht doppelt
        self.assertEqual(self.a.post("/api/system/auftraege/", {"aktion": "updates_suchen"}, format="json")
                         .status_code, 409)
        r = self.a.post(f"/api/system/auftraege/{auftrag['kennung']}/abbrechen/")
        self.assertEqual(r.json()["status"], "abgebrochen")
        self.assertEqual(self.auftragsdateien(), [])
        self.assertEqual(self.a.post("/api/system/auftraege/", {"aktion": "rm -rf /"}, format="json").status_code, 400)
        texte = list(SystemEreignis.objects.filter(art="system").values_list("details__ereignis", flat=True))
        self.assertIn("angefordert", texte)
        self.assertIn("abgebrochen", texte)

    def test_ohne_auftragsverzeichnis(self):
        shutil.rmtree(self.ordner / "auftraege")
        r = self.a.post("/api/system/auftraege/", {"aktion": "updates_suchen"}, format="json")
        self.assertEqual(r.status_code, 503)
        self.assertIn("04-projekt.sh", r.json()["fehler"])
        self.assertFalse(Systemauftrag.objects.exists())

    def test_neustart_nur_mit_kennwort_und_code(self):
        url = "/api/system/auftraege/"
        r = self.a.post(url, {"aktion": "server_neustart", "minuten": 5}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("kennwort", r.json())
        r = self.a.post(url, {"aktion": "server_neustart", "minuten": 5, "kennwort": KENNWORT, "code": "falsch"},
                        format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("code", r.json())
        self.drosselung_aufheben()
        r = self.a.post(url, {"aktion": "server_neustart", "minuten": 7, "kennwort": KENNWORT,
                              "code": self.admin_codes[0]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("minuten", r.json())
        self.assertEqual(self.auftragsdateien(), [])
        r = self.a.post(url, {"aktion": "server_neustart", "minuten": 5, "kennwort": KENNWORT,
                              "code": self.admin_codes[1]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["parameter"], {"minuten": 5})
        self.assertEqual(len(self.auftragsdateien()), 1)
        # angemeldete Benutzer sehen die Warnung
        h = client_fuer(self.betrachter).get("/api/system/hinweis/").json()["hinweis"]
        self.assertEqual(h["art"], "warnung")
        self.assertIn("neu gestartet", h["text"])
        self.assertIn("Beginn:", h["text"])
        # Fehlversuche stehen im Audit-Log (ohne das Konto zu sperren)
        self.assertTrue(SystemEreignis.objects.filter(art="anmeldung_fehlgeschlagen", details__grund="bestaetigung")
                        .exists())
        self.assertTrue(SystemEreignis.objects.filter(art="2fa_fehlgeschlagen", details__schritt="bestaetigung")
                        .exists())
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.ist_gesperrt)
        # Notfall-Code gilt nur einmal
        r = self.a.post(url, {"aktion": "epm_neustart", "kennwort": KENNWORT, "code": self.admin_codes[1]},
                        format="json")
        self.assertEqual(r.status_code, 400)

    def test_sicherung_braucht_recht_sicherungen(self):
        Gruppenrecht.objects.create(rolle=Rolle.ADMIN, recht="backup_verwalten", erlaubt=False)
        d = self.a.get("/api/system/uebersicht/").json()
        self.assertFalse(next(x for x in d["aktionen"] if x["code"] == "sicherung")["erlaubt"])
        self.assertEqual(self.a.post("/api/system/auftraege/", {"aktion": "sicherung"}, format="json").status_code, 403)

    def test_ergebnis_vom_server_wird_uebernommen(self):
        r = self.a.post("/api/system/auftraege/", {"aktion": "updates_installieren", "minuten": 0, "kennwort": KENNWORT,
                                                   "code": self.admin_codes[0]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        kennung = r.json()["kennung"].replace("-", "")
        self.assertIsNotNone(Systemhinweis.aktiv())
        ergebnis = self.ordner / "status" / "auftraege" / f"{kennung}.json"
        ergebnis.write_text(json.dumps({"id": kennung, "status": "laeuft", "begonnen_am": timezone.now().isoformat(),
                                        "ausgabe": "Sicherung …"}))
        liste = self.a.get("/api/system/auftraege/").json()
        self.assertEqual(liste[0]["status"], "laeuft")
        ergebnis.write_text(json.dumps({"id": kennung, "status": "erledigt", "rueckgabe": 0,
                                        "begonnen_am": timezone.now().isoformat(),
                                        "beendet_am": timezone.now().isoformat(), "ergebnis": "Updates installiert.",
                                        "ausgabe": "…", "trocken": True}))
        liste = self.a.get("/api/system/auftraege/").json()
        self.assertEqual(liste[0]["status"], "erledigt")
        self.assertTrue(liste[0]["probelauf"])
        self.assertEqual(liste[0]["ergebnis"], "Updates installiert.")
        # Warnung endet mit dem Auftrag; Abschluss steht einmal im Audit-Log
        self.assertIsNone(Systemhinweis.aktiv())
        self.a.get("/api/system/auftraege/")
        self.assertEqual(SystemEreignis.objects.filter(art="system", details__ereignis="abgeschlossen").count(), 1)
        e = self.a.get("/api/protokoll/?gruppe=system").json()["results"]
        self.assertTrue(any(x["beschreibung"] == "Ubuntu-Updates installieren erledigt: Updates installiert."
                            for x in e))

    @unittest.skipUnless(AGENT.exists(), "rollout/epm-systemagent.py nur im Repo (nicht im Image)")
    def test_echter_agent_im_probelauf(self):
        """Backend legt ab → Agent (Probelauf) führt aus → Backend übernimmt das Ergebnis."""
        for aktion in ("status_aktualisieren", "docker_aufraeumen"):
            self.assertEqual(self.a.post("/api/system/auftraege/", {"aktion": aktion}, format="json").status_code, 201)
        self.assertEqual(len(self.auftragsdateien()), 2)
        basis = Path(tempfile.mkdtemp(prefix="epm-basis-"))
        try:
            os.symlink(self.ordner, basis / "system")
            p = subprocess.run([sys.executable, str(AGENT), "auftraege", "--basis", str(basis), "--trocken"],
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(p.returncode, 0, p.stderr)
        finally:
            shutil.rmtree(basis, ignore_errors=True)
        self.assertEqual(self.auftragsdateien(), [])
        liste = {x["aktion"]: x for x in self.a.get("/api/system/auftraege/").json()}
        self.assertEqual(liste["status_aktualisieren"]["status"], "erledigt", liste["status_aktualisieren"])
        self.assertTrue(liste["docker_aufraeumen"]["probelauf"])
        self.assertTrue((self.ordner / "status" / "system.json").exists())
        self.assertTrue(self.a.get("/api/system/uebersicht/").json()["agent"]["erreichbar"])


class EpmWartung(Systemverzeichnis):
    def aufgabe(self, code, **extra):
        r = self.a.post("/api/system/epm/", {"aufgabe": code, **extra}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_alle_aufgaben(self):
        for code in ("sitzungen_bereinigen", "datenbank_optimieren", "schutz_pruefen", "konfiguration_pruefen",
                     "dokumente_pruefen"):
            with self.subTest(aufgabe=code):
                a = self.aufgabe(code)
                self.assertEqual(a["ziel"], "epm")
                self.assertIn(a["status"], ("erledigt", "fehler"))
                self.assertTrue(a["ergebnis"])
        self.assertEqual(self.aufgabe("schutz_pruefen")["status"], "erledigt")
        self.assertEqual(self.a.post("/api/system/epm/", {"aufgabe": "x"}, format="json").status_code, 400)
        self.assertEqual(SystemEreignis.objects.filter(art="system", details__ereignis="epm_aufgabe").count(), 6)

    def test_dokumente_pruefen_findet_fehlende_und_veraenderte(self):
        from django.conf import settings

        ordner = settings.EPM_DOKUMENTE / str(self.patient.nummer)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "ok.pdf").write_bytes(b"%PDF-1.4 ok")
        (ordner / "geaendert.pdf").write_bytes(b"%PDF-1.4 vorher")
        import hashlib

        for name, inhalt in (("ok.pdf", b"%PDF-1.4 ok"), ("geaendert.pdf", b"%PDF-1.4 vorher"),
                             ("fehlt.pdf", b"x")):
            Dokument.objects.create(patient=self.patient, titel=name, datei=f"{self.patient.nummer}/{name}",
                                    originalname=name, mime="application/pdf", groesse=len(inhalt),
                                    sha256=hashlib.sha256(inhalt).hexdigest())
        (ordner / "geaendert.pdf").write_bytes(b"%PDF-1.4 nachh")  # gleiche Länge, anderer Inhalt
        (ordner / "unbekannt.txt").write_bytes(b"?")
        a = self.aufgabe("dokumente_pruefen")
        self.assertEqual(a["status"], "fehler")
        self.assertIn("1 von", a["ergebnis"])
        self.assertIn("fehlt.pdf", a["ausgabe"])
        self.assertIn("unbekannt.txt", a["ausgabe"])
        a = self.aufgabe("dokumente_pruefen", pruefsummen=True)
        self.assertIn("2 von", a["ergebnis"])
        self.assertIn("Prüfsumme weicht ab", a["ausgabe"])

    def test_schutz_wird_wieder_gesetzt(self):
        from django.db import connection

        with connection.cursor() as c:
            c.execute("DROP TRIGGER epm_schutz ON audit_systemereignis")
        self.assertIn("audit_systemereignis",
                      self.a.get("/api/system/uebersicht/").json()["epm"]["schutz"]["fehlend"])
        a = self.aufgabe("schutz_pruefen")
        self.assertEqual(a["status"], "erledigt")
        self.assertIn("wieder gesetzt", a["ergebnis"])
        self.assertEqual(self.a.get("/api/system/uebersicht/").json()["epm"]["schutz"]["fehlend"], [])

    def test_alle_anderen_abmelden(self):
        from epm.pruefhilfen import echte_anmeldung

        codes = mit_zweitem_faktor(self.mitarbeiter)
        m = echte_anmeldung(self.mitarbeiter, codes[0])
        self.assertEqual(m.get("/api/patienten/").status_code, 200)
        self.aufgabe("alle_abmelden")
        self.assertEqual(m.get("/api/patienten/").status_code, 403)


class Hinweise(Systemverzeichnis):
    def test_hinweis_an_alle(self):
        m = client_fuer(self.mitarbeiter)
        self.assertIsNone(m.get("/api/system/hinweis/").json()["hinweis"])
        self.assertEqual(m.post("/api/system/hinweis/", {"text": "x"}, format="json").status_code, 403)
        r = self.a.post("/api/system/hinweis/", {"text": "Heute ab 18 Uhr Wartung.", "art": "info", "minuten": 60},
                        format="json")
        self.assertEqual(r.status_code, 201, r.content)
        h = m.get("/api/system/hinweis/").json()["hinweis"]
        self.assertEqual(h["text"], "Heute ab 18 Uhr Wartung.")
        self.assertEqual(h["art"], "info")
        # abgelaufen
        Systemhinweis.objects.update(gueltig_bis=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(m.get("/api/system/hinweis/").json()["hinweis"])
        self.a.post("/api/system/hinweis/", {"text": "Neu"}, format="json")
        self.assertEqual(self.a.delete("/api/system/hinweis/").status_code, 200)
        self.assertIsNone(m.get("/api/system/hinweis/").json()["hinweis"])
        self.assertEqual(self.a.delete("/api/system/hinweis/").status_code, 404)
        arten = list(SystemEreignis.objects.filter(art="system").values_list("details__ereignis", flat=True))
        self.assertEqual(arten.count("hinweis"), 2)
        self.assertIn("hinweis_beendet", arten)
