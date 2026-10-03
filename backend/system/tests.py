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
        # Austausch von Sicherungen (legt rollout/04-projekt.sh an): bereitgestellte und hochgeladene
        (self.ordner / "download").mkdir()
        (self.ordner / "upload").mkdir()
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

    def test_vertretung_je_gruppe_freischaltbar(self):
        """Festlegung 02.10.2026: Standard nur Admin, für eine Urlaubsvertretung jeder Gruppe erteilbar."""
        daten = self.a.get("/api/rechte/").json()
        self.assertNotIn("system_verwalten", daten["nur_rollen"])
        self.assertFalse(daten["matrix"]["mediziner"]["system_verwalten"])
        m = client_fuer(self.mediziner)
        self.assertEqual(m.get("/api/system/uebersicht/").status_code, 403)
        r = self.a.put("/api/rechte/", {"matrix": {"mediziner": {"system_verwalten": True}}}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["matrix"]["mediziner"]["system_verwalten"])
        self.mediziner.refresh_from_db()
        self.assertIn("system_verwalten", self.mediziner.rechte)
        self.assertEqual(m.get("/api/system/uebersicht/").status_code, 200)
        # Vertretung führt Tätigkeiten mit dem eigenen Passwort und 2FA aus
        codes = mit_zweitem_faktor(self.mediziner, anzahl_codes=2)
        r = m.post("/api/system/auftraege/", {"aktion": "server_neustart", "minuten": 0, "kennwort": KENNWORT,
                                              "code": codes[0]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        # Testzugänge erhalten es auch dann nicht
        tester = benutzer("tester", Rolle.MEDIZINER, ist_test=True)
        self.assertNotIn("system_verwalten", tester.rechte)
        # Urlaub vorbei: zurücknehmen wirkt sofort
        self.a.put("/api/rechte/", {"matrix": {"mediziner": {"system_verwalten": False}}}, format="json")
        self.assertEqual(m.get("/api/system/uebersicht/").status_code, 403)
        self.assertTrue(SystemEreignis.objects.filter(art="rechte_geaendert").exists())
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
        jetzt = int(timezone.now().timestamp())
        (self.ordner / "status" / "verlauf.json").write_text(json.dumps({"punkte": [[jetzt - 60, 5, 40, 0.1, 30]]}))
        self.assertEqual(self.a.get("/api/system/verlauf/").json()["punkte"], [[jetzt - 60, 5, 40, 0.1, 30]])

    def test_verlauf_in_zeitraeumen(self):
        """Fehlerliste 02.10.2026 (4.1): Auslastung für 1 Stunde bis 6 Monate – kurze Zeiträume aus den Messungen je
        Minute, lange aus den gemittelten Stufen des Agenten (mit Spitzen)."""
        jetzt = int(timezone.now().timestamp())
        minuten = [[jetzt - 60 * i, 10 + i % 7, 40, 0.2, 30] for i in range(1439, -1, -1)]   # 24 Stunden
        felder = ["zeit", "cpu", "ram", "last", "platte", "cpu_max", "ram_max"]
        stufen = {
            "viertelstunde": {"sekunden": 900, "felder": felder,
                              "punkte": [[jetzt - 900 * i, 12, 41, 0.2, 30, 55, 44] for i in range(1343, -1, -1)]},
            "stunde": {"sekunden": 3600, "felder": felder,
                       "punkte": [[jetzt - 3600 * i, 13, 42, 0.2, 30, 60, 45] for i in range(743, -1, -1)]},
            "vierteltag": {"sekunden": 21600, "felder": felder,
                           "punkte": [[jetzt - 21600 * i, 14, 43, 0.2, 31, 70, 50] for i in range(99, -1, -1)]},
        }
        (self.ordner / "status" / "verlauf.json").write_text(json.dumps(
            {"felder": felder[:5], "punkte": minuten, "stufen": stufen}))
        erwartet = {"1h": (60, 60, 62), "3h": (60, 180, 182), "24h": (60, 1438, 1440), "7t": (900, 671, 673),
                    "14t": (900, 1343, 1344), "1m": (3600, 743, 744), "6m": (21600, 100, 100)}
        for zeitraum, (schritt, von, bis) in erwartet.items():
            with self.subTest(zeitraum=zeitraum):
                d = self.a.get(f"/api/system/verlauf/?zeitraum={zeitraum}").json()
                self.assertEqual((d["zeitraum"], d["schritt_s"]), (zeitraum, schritt))
                self.assertTrue(von <= len(d["punkte"]) <= bis, len(d["punkte"]))
                self.assertEqual(len(d["felder"]), 5 if schritt == 60 else 7)
                self.assertGreaterEqual(d["punkte"][0][0], d["von"])
        d = self.a.get("/api/system/verlauf/").json()
        self.assertEqual(d["zeitraum"], "24h")  # Standard wie bisher
        self.assertEqual([z["code"] for z in d["zeitraeume"]], ["1h", "3h", "24h", "7t", "14t", "1m", "6m"])
        self.assertEqual(d["zeitraeume"][3]["name"], "7 Tage")
        self.assertEqual(self.a.get("/api/system/verlauf/?zeitraum=1j").status_code, 400)
        # ohne die Stufen (Agent noch in der alten Fassung): lange Zeiträume leer statt Fehler
        (self.ordner / "status" / "verlauf.json").write_text(json.dumps({"punkte": minuten}))
        self.assertEqual(self.a.get("/api/system/verlauf/?zeitraum=7t").json()["punkte"], [])
        self.assertEqual(self.a.get("/api/system/verlauf/?zeitraum=6m").status_code, 200)
        self.assertEqual(client_fuer(self.mediziner).get("/api/system/verlauf/?zeitraum=1h").status_code, 403)

    @unittest.skipUnless(AGENT.exists(), "rollout/epm-systemagent.py nur im Repo (nicht im Image)")
    def test_agent_aufbewahrung_im_ziel(self):
        """Festlegung 03.10.2026: Im Übertragungsziel entfernt der Agent Sicherungen, die älter als die Aufbewahrung
        sind (Standard 30 Tage) – nur Dateien von EPM-Sicherungen, nach dem Zeitstempel im Namen; die jüngste bleibt
        immer, alles andere im Ordner wird nicht angefasst; 0 = nie löschen."""
        import importlib.util
        from datetime import datetime, timezone as tz

        spec = importlib.util.spec_from_file_location("epm_systemagent", AGENT)
        agent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent)
        jetzt = datetime(2026, 10, 3, 12, 0, tzinfo=tz.utc)
        namen = ["epm-db_2026-08-01_0200.dump.gpg", "epm-dokumente_2026-08-01_0200.tar.gz.gpg", "epm_2026-08-01_0200.sha256",
                 "epm_2026-08-01_0200.json", "epm-db_2026-09-20_0200.dump.gpg", "epm-db_2026-10-02_020000.dump.gpg",
                 "notizen.txt", "epm-db_kaputt.dump.gpg", "unterordner/epm-db_2020-01-01_0200.dump.gpg"]
        self.assertEqual(agent.im_ziel_veraltet(namen, 30, jetzt),
                         ["epm-db_2026-08-01_0200.dump.gpg", "epm-dokumente_2026-08-01_0200.tar.gz.gpg",
                          "epm_2026-08-01_0200.json", "epm_2026-08-01_0200.sha256"])
        self.assertEqual(agent.im_ziel_veraltet(namen, 0, jetzt), [])
        # die jüngste Sicherung bleibt, auch wenn sie älter als die Aufbewahrung ist
        self.assertEqual(agent.im_ziel_veraltet(["epm-db_2020-01-01_0200.dump.gpg"], 14, jetzt), [])
        self.assertEqual(agent.Agent.ziel_aufbewahrung({}), 30)
        self.assertEqual(agent.Agent.ziel_aufbewahrung({"aufbewahrung_tage": 0}), 0)
        self.assertEqual(agent.Agent.ziel_aufbewahrung({"aufbewahrung_tage": 31}), 30)
        fehler, z = agent.Agent.ziel_pruefen({"url": "https://cloud.example.org/dav", "benutzer": "b", "von": "02:00",
                                               "bis": "05:00", "aufbewahrung_tage": 31})
        self.assertIn("Aufbewahrung im Ziel", fehler)

    @unittest.skipUnless(AGENT.exists(), "rollout/epm-systemagent.py nur im Repo (nicht im Image)")
    def test_agent_mittelt_den_verlauf_in_stufen(self):
        """Der Agent schreibt zu den Messungen je Minute gröbere Stufen fort: Mittelwert je Abschnitt, Spitzen von CPU
        und Arbeitsspeicher; beim ersten Lauf aus allen vorhandenen Minutenwerten."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("epm_systemagent", AGENT)
        agent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent)
        basis = 1_800_000_000 - 1_800_000_000 % 21600          # Beginn eines 6-Stunden-Abschnitts
        punkte = [[basis + 60 * i, float(i % 10), 50.0, 0.5, 20.0] for i in range(45)]   # 45 Minuten
        punkte[3][1] = None                                    # fehlende Messung zählt nicht mit
        punkte[20][1] = 90.0                                   # Spitze in der zweiten Viertelstunde
        stufen = agent.Agent.verlauf_stufen(None, punkte)
        self.assertEqual(sorted(stufen), ["stunde", "viertelstunde", "vierteltag"])
        viertel = stufen["viertelstunde"]["punkte"]
        self.assertEqual([p[0] for p in viertel], [basis, basis + 900, basis + 1800])
        erste = [i % 10 for i in range(15) if i != 3]
        self.assertEqual(viertel[0][1], round(sum(erste) / len(erste), 2))
        self.assertEqual((viertel[0][5], viertel[1][5], viertel[1][6]), (9.0, 90.0, 50.0))
        self.assertEqual(len(stufen["stunde"]["punkte"]), 1)
        self.assertEqual(stufen["stunde"]["punkte"][0][5], 90.0)
        self.assertEqual(stufen["viertelstunde"]["felder"][-2:], ["cpu_max", "ram_max"])
        # nächste Minute: der laufende Abschnitt wird ersetzt, kein zweiter Punkt für dieselbe Viertelstunde
        punkte.append([basis + 60 * 45, 100.0, 80.0, 0.5, 20.0])
        weiter = agent.Agent.verlauf_stufen(stufen, punkte)
        self.assertEqual([p[0] for p in weiter["viertelstunde"]["punkte"]], [basis, basis + 900, basis + 1800, basis + 2700])
        self.assertEqual(weiter["viertelstunde"]["punkte"][0], viertel[0])       # abgeschlossene Abschnitte bleiben
        self.assertEqual(weiter["stunde"]["punkte"][0][5], 100.0)
        self.assertEqual(len(weiter["stunde"]["punkte"]), 1)
        # alte Abschnitte fallen hinten heraus (hier: 14 Tage bei Viertelstunden)
        viele = {"viertelstunde": {"punkte": [[basis - 900 * i, 1, 1, 1, 1, 1, 1] for i in range(1400, 0, -1)]}}
        self.assertEqual(len(agent.Agent.verlauf_stufen(viele, punkte)["viertelstunde"]["punkte"]), 1344)

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

    def test_ohne_zweiten_faktor_geht_es_nicht(self):
        """Festlegung 03.10.2026: Update, Neustart, Wiederherstellen nur mit eingerichtetem zweitem Faktor – auch wenn
        die Anmeldung ohne ihn erlaubt ist. Das Kennwort allein genügt nicht."""
        from accounts.zweifaktor import OHNE_ZWEITEN_FAKTOR

        ohne = benutzer("ohne2fa", Rolle.ADMIN)
        c = client_fuer(ohne)
        r = c.post("/api/system/auftraege/", {"aktion": "epm_neustart", "minuten": 0, "kennwort": KENNWORT}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json(), {"code": OHNE_ZWEITEN_FAKTOR})
        self.assertFalse(Systemauftrag.objects.filter(angefordert_von=ohne).exists())

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
        (ordner / "geaendert.pdf").write_bytes(b"%PDF-1.4 nacher")  # gleiche Länge, anderer Inhalt
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
