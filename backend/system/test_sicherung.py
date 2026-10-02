"""Administration › Backup (F61–F64, O-07, O-23): Rechte, Übersicht, Passwort, Passwortblatt, Ziel, Wiederherstellen,
Nachtragen nach einer Wiederherstellung, Startseite – und der echte Systemagent mit dem echten Backup-Skript
(GnuPG, nachgestelltes ``docker``) in eigenen Verzeichnissen. Geheimnisse dürfen nie in der Datenbank landen."""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from datetime import timedelta
from pathlib import Path

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.utils import timezone

from accounts.models import Rolle, Sitzung
from audit.models import SystemEreignis
from epm.pruefhilfen import KENNWORT, benutzer, client_fuer, echte_anmeldung, mit_zweitem_faktor

from .models import Systemauftrag, Systemhinweis
from .tests import AGENT, Systemverzeichnis

SKRIPT = AGENT.parent / "epm-backup.sh"
PASSWORT = "Tresor-Passwort-2026-xyz"


def iso(delta_h=0.0):
    return (timezone.now() - timedelta(hours=delta_h)).isoformat()


def eine_sicherung(stempel="2026-10-01_020000", alter_h=2.0, verschluesselt=True, uebertragen=True, **extra):
    endung = ".gpg" if verschluesselt else ""
    return {"stempel": stempel, "zeitpunkt": iso(alter_h), "art": "nachts", "ausgeloest_von": "",
            "verschluesselt": verschluesselt, "verfahren": "gpg" if verschluesselt else "",
            "passwort_nr": 1 if verschluesselt else None, "groesse": 4096,
            "dateien": [f"epm-db_{stempel}.dump{endung}", f"epm-dokumente_{stempel}.tar.gz{endung}"],
            "dokumente": True, "loeschliste": False, "pruefsummen": True, "epm_version": "0.9.0",
            "uebertragen_am": iso(alter_h - 0.2) if uebertragen else None, **extra}


class Backupverzeichnis(Systemverzeichnis):
    def status_schreiben(self, sicherungen=None, ziel=True, **extra):
        daten = {
            "version": 1, "zeit": iso(), "nachts_fehlgeschlagen": False, "gpg": True,
            "verschluesselung": {"eingerichtet": True, "aktuell": 1, "verfahren": "GnuPG (OpenPGP), AES-256, symmetrisch",
                                 "versionen": [{"nr": 1, "gesetzt_am": iso(48), "gesetzt_von": "admin",
                                                "entfernt_am": None, "sicherungen": 1}]},
            "ziel": {"eingerichtet": True, "url": "https://cloud.example.org/remote.php/dav/files/epm", "benutzer": "epm",
                     "ordner": "EPM", "von": "02:00", "bis": "05:00", "hersteller": "nextcloud"} if ziel
            else {"eingerichtet": False},
            "uebertragung": {"letzter_versuch": iso(1), "letzter_erfolg": iso(1), "letzter_fehler": "", "laeuft": False,
                             "offen": 0, "im_zeitfenster": False, "naechstes_fenster": iso(-12), "rclone": True},
            "sicherungen": [eine_sicherung()] if sicherungen is None else sicherungen,
            "speicher": {"platz": {"gesamt": 40 * 2 ** 30, "frei": 32 * 2 ** 30}, "sicherungen": 4096},
            "aufbewahrung_tage": 30, "naechste_sicherung": "Fri 2026-10-02 02:00:00 CEST", "wiederherstellungen": [],
        }
        daten.update(extra)
        (self.ordner / "status" / "sicherung.json").write_text(json.dumps(daten))
        return daten

    def pruefwert_schreiben(self, passwort=PASSWORT, nr=1):
        salz = os.urandom(16)
        wert = hashlib.scrypt(passwort.encode(), salt=salz, n=2 ** 14, r=8, p=1, dklen=32)
        (self.ordner / "status" / "sicherung-pruefwerte.json").write_text(json.dumps({"pruefwerte": [
            {"nr": nr, "verfahren": "scrypt", "n": 2 ** 14, "r": 8, "p": 1, "salz": salz.hex(), "wert": wert.hex()}]}))

    def auftragsdatei(self):
        dateien = list((self.ordner / "auftraege").glob("*.json"))
        self.assertEqual(len(dateien), 1, dateien)
        self.assertEqual(stat.S_IMODE(dateien[0].stat().st_mode), 0o600)
        return json.loads(dateien[0].read_text())

    def nirgends_in_der_datenbank(self, geheimnis):
        """Kein Passwort in Aufträgen, Audit-Log oder Hinweisen."""
        for a in Systemauftrag.objects.all():
            self.assertNotIn(geheimnis, json.dumps(a.parameter) + a.ergebnis + a.ausgabe)
        for e in SystemEreignis.objects.all():
            self.assertNotIn(geheimnis, json.dumps(e.details) + e.objekt)
        for h in Systemhinweis.objects.all():
            self.assertNotIn(geheimnis, h.text)


class Rechte(Backupverzeichnis):
    def test_nur_mit_recht_sicherungen_verwalten(self):
        self.assertEqual(self.a.get("/api/backup/").status_code, 200)
        for user in (self.mediziner, self.mitarbeiter, self.betrachter, benutzer("testadmin", Rolle.ADMIN, ist_test=True)):
            with self.subTest(benutzer=user.username):
                c = client_fuer(user)
                self.assertEqual(c.get("/api/backup/").status_code, 403)
                self.assertEqual(c.post("/api/backup/jetzt/").status_code, 403)
                self.assertEqual(c.post("/api/backup/passwort/pruefen/", {"passwort": PASSWORT}, format="json")
                                 .status_code, 403)
        self.assertEqual(self.auftragsdateien(), [])


class Uebersicht(Backupverzeichnis):
    def test_ohne_status_vom_server(self):
        d = self.a.get("/api/backup/").json()
        self.assertFalse(d["status"]["vorhanden"])
        self.assertEqual(d["kurz"]["zustand"], "unbekannt")
        self.assertEqual(d["sicherungen"], [])
        self.assertFalse(d["verschluesselung"]["eingerichtet"])
        self.assertFalse(d["ziel"]["eingerichtet"])
        self.assertEqual(set(d["aktionen"]), {"sicherung", "sicherung_passwort", "sicherung_ziel",
                                              "sicherung_ziel_entfernen", "sicherung_ziel_testen",
                                              "sicherung_uebertragen", "wiederherstellen"})
        self.assertEqual(d["aktionen"]["wiederherstellen"]["bestaetigung"], "2fa")

    def test_status_vom_server(self):
        self.status_schreiben(sicherungen=[eine_sicherung(), eine_sicherung("2026-09-30_020000", alter_h=26),
                                           eine_sicherung("2026-09-29_020000", verschluesselt=False, uebertragen=False,
                                                          art="von_hand", ausgeloest_von="admin")])
        d = self.a.get("/api/backup/").json()
        self.assertTrue(d["status"]["aktuell"])
        self.assertEqual(d["kurz"]["zustand"], "ok", d["kurz"])
        self.assertEqual(d["letzte"]["stempel"], "2026-10-01_020000")
        self.assertEqual(d["letzte"]["art_name"], "Automatisch")
        self.assertTrue(d["letzte"]["uebertragen"])
        self.assertTrue(d["letzte"]["wiederherstellbar"])
        self.assertEqual(d["sicherungen"][2]["art_name"], "Von Hand")
        self.assertFalse(d["sicherungen"][2]["uebertragen"])
        self.assertEqual(d["speicher"], {"sicherungen": 4096, "gesamt": 40 * 2 ** 30, "frei": 32 * 2 ** 30,
                                         "belegt": 8 * 2 ** 30})
        self.assertEqual(d["ziel"]["url"], "https://cloud.example.org/remote.php/dav/files/epm")
        self.assertNotIn("kennwort", json.dumps(d["ziel"]))
        self.assertEqual(d["aufbewahrung_tage"], 30)

    def test_nicht_nachgeholte_loeschungen_sind_ein_fehler(self):
        """Konnten Löschungen nach Art. 17 DSGVO nicht vollständig nachgeholt werden, zeigen es Backup-Seite und
        Startseite – auch wenn die Sicherung selbst in Ordnung ist (O-28)."""
        from django.test import override_settings

        from patienten.loeschung import nachholen_stand_schreiben

        ordner = Path(tempfile.mkdtemp(prefix="epm-loeschliste-"))
        try:
            with override_settings(EPM_LOESCHLISTE=ordner / "loeschliste.jsonl"):
                self.status_schreiben()
                self.assertEqual(self.a.get("/api/backup/").json()["kurz"]["zustand"], "ok")
                nachholen_stand_schreiben("fehler", "Löschungen … nicht vollständig nachgeholt: 1 Zeilen der Löschliste "
                                          "nicht lesbar", timezone.now().isoformat())
                kurz = self.a.get("/api/backup/").json()["kurz"]
                self.assertEqual((kurz["zustand"], kurz["titel"]), ("fehler", "Löschungen nicht nachgeholt"))
                self.assertIn("Endgültige Löschungen (Art. 17 DSGVO) konnten nicht vollständig nachgeholt werden", kurz["hinweise"][0])
                start = client_fuer(self.mitarbeiter).get("/api/startseite/").json()["sicherung"]
                self.assertEqual(start["zustand"], "fehler")
                # auch ohne Status vom Server sichtbar
                (self.ordner / "status" / "sicherung.json").unlink()
                kurz = self.a.get("/api/backup/").json()["kurz"]
                self.assertEqual((kurz["zustand"], kurz["titel"]), ("fehler", "Löschungen nicht nachgeholt"))
                # behoben: der Hinweis verschwindet
                nachholen_stand_schreiben("ok", "", timezone.now().isoformat())
                self.status_schreiben()
                self.assertEqual(self.a.get("/api/backup/").json()["kurz"]["zustand"], "ok")
        finally:
            shutil.rmtree(ordner, ignore_errors=True)

    def test_zustand_fuer_die_startseite(self):
        start = lambda: client_fuer(self.mitarbeiter).get("/api/startseite/").json()["sicherung"]  # noqa: E731
        self.assertEqual(start()["zustand"], "unbekannt")
        self.status_schreiben()
        s = start()
        self.assertEqual((s["zustand"], s["hinweise"], s["verschluesselt"]), ("ok", [], True))
        # unverschlüsselt und ohne Ziel: Warnung
        self.status_schreiben(sicherungen=[eine_sicherung(verschluesselt=False, uebertragen=False)], ziel=False)
        s = start()
        self.assertEqual(s["zustand"], "warnung")
        self.assertIn("unverschlüsselt", s["hinweise"][0])
        self.assertTrue(any("nur auf dem Server" in h for h in s["hinweise"]))
        # verschlüsselt, aber seit über einem Tag nicht übertragen
        self.status_schreiben(sicherungen=[eine_sicherung(alter_h=30, uebertragen=False)])
        s = start()
        self.assertTrue(any("nicht übertragen" in h for h in s["hinweise"]), s)
        # zu alt bzw. nächtlicher Lauf gescheitert: Fehler
        self.status_schreiben(sicherungen=[eine_sicherung(alter_h=40)])
        self.assertEqual(start()["zustand"], "fehler")
        self.status_schreiben(nachts_fehlgeschlagen=True)
        s = start()
        self.assertEqual(s["zustand"], "fehler")
        self.assertIn("nächtliche Sicherung ist fehlgeschlagen", s["hinweise"][0])
        # Agent meldet sich nicht mehr
        self.status_schreiben(zeit=iso(1))
        self.assertEqual(start()["zustand"], "fehler")
        self.status_schreiben(sicherungen=[])
        self.assertIn("noch keine Sicherung", " ".join(start()["hinweise"]))


class Passwort(Backupverzeichnis):
    url = "/api/backup/passwort/"

    def test_pruefungen_vor_der_bestaetigung(self):
        faelle = [({"passwort": "kurz", "passwort2": "kurz"}, "passwort"),
                  ({"passwort": "x" * 201, "passwort2": "x" * 201}, "passwort"),
                  ({"passwort": "Zeile1\nZeile2-lang-genug", "passwort2": "Zeile1\nZeile2-lang-genug"}, "passwort"),
                  ({"passwort": " Leerzeichen-vorne-1234", "passwort2": " Leerzeichen-vorne-1234"}, "passwort"),
                  ({"passwort": PASSWORT, "passwort2": PASSWORT + "!"}, "passwort2"),
                  ({"passwort": KENNWORT, "passwort2": KENNWORT}, "passwort")]
        for daten, feld in faelle:
            with self.subTest(feld=feld, daten=daten):
                r = self.a.post(self.url, {**daten, "kennwort": KENNWORT, "code": self.admin_codes[0]}, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn(feld, r.json())
        self.assertIn("Anmelde-Passwort", self.a.post(self.url, {"passwort": KENNWORT, "passwort2": KENNWORT},
                                                      format="json").json()["passwort"])
        # ohne Passwort und Code kein Auftrag
        r = self.a.post(self.url, {"passwort": PASSWORT, "passwort2": PASSWORT}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("kennwort", r.json())
        self.assertEqual(self.auftragsdateien(), [])
        # schon hinterlegt
        self.pruefwert_schreiben()
        r = self.a.post(self.url, {"passwort": PASSWORT, "passwort2": PASSWORT, "kennwort": KENNWORT,
                                   "code": self.admin_codes[0]}, format="json")
        self.assertIn("schon hinterlegt", r.json()["passwort"])

    def test_passwort_nur_in_der_auftragsdatei(self):
        r = self.a.post(self.url, {"passwort": PASSWORT, "passwort2": PASSWORT, "kennwort": KENNWORT,
                                   "code": self.admin_codes[0]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotIn(PASSWORT, r.content.decode())
        datei = self.auftragsdatei()
        self.assertEqual((datei["aktion"], datei["geheim"]), ("sicherung_passwort", {"passwort": PASSWORT}))
        self.assertEqual(Systemauftrag.objects.get().parameter, {})
        self.nirgends_in_der_datenbank(PASSWORT)
        e = self.a.get("/api/protokoll/?gruppe=backup").json()["results"]
        self.assertTrue(any(x["beschreibung"] == "Sicherungs-Passwort festlegen angefordert, mit Passwort und 2FA bestätigt"
                            for x in e), e)

    def test_pruefen_und_passwortblatt(self):
        self.status_schreiben()
        self.pruefwert_schreiben()
        r = self.a.post("/api/backup/passwort/pruefen/", {"passwort": PASSWORT}, format="json").json()
        self.assertEqual(r, {"stimmt": True, "nr": 1, "aktuell": True})
        self.assertFalse(self.a.post("/api/backup/passwort/pruefen/", {"passwort": PASSWORT + "x"}, format="json")
                         .json()["stimmt"])
        r = self.a.post("/api/backup/passwortblatt/", {"passwort": "falsch-falsch-falsch"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.a.post("/api/backup/passwortblatt/", {"passwort": PASSWORT}, format="json")
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(r["Cache-Control"], "private, no-store")
        self.assertTrue(r.content.startswith(b"%PDF"))
        arten = list(SystemEreignis.objects.filter(art="backup").values_list("details__ereignis", flat=True))
        self.assertEqual(sorted(arten), ["passwort_falsch", "passwort_falsch", "passwort_geprueft", "passwortblatt"])
        self.nirgends_in_der_datenbank(PASSWORT)
        # Raten wird gebremst: nach 5 falschen Passwörtern in 15 Minuten 429 (auch für das richtige)
        for _ in range(3):
            self.a.post("/api/backup/passwort/pruefen/", {"passwort": "noch-ein-falsches-pw"}, format="json")
        r = self.a.post("/api/backup/passwort/pruefen/", {"passwort": PASSWORT}, format="json")
        self.assertEqual(r.status_code, 429)
        self.assertEqual(self.a.post("/api/backup/passwortblatt/", {"passwort": PASSWORT}, format="json").status_code,
                         429)
        # nach 15 Minuten wieder möglich
        with unittest.mock.patch("system.sicherung.timezone.now", return_value=timezone.now() + timedelta(minutes=16)):
            self.assertTrue(self.a.post("/api/backup/passwort/pruefen/", {"passwort": PASSWORT}, format="json")
                            .json()["stimmt"])


class Ziel(Backupverzeichnis):
    url = "/api/backup/ziel/"
    gueltig = {"url": "https://cloud.example.org/remote.php/dav/files/epm/", "benutzer": "epm-sicherung",
               "ordner": "/EPM/Sicherungen/", "von": "02:00", "bis": "05:00", "ziel_kennwort": "App-Passwort-1234"}

    def test_pruefungen(self):
        faelle = [({"url": "http://cloud.example.org/dav"}, "url"), ({"url": "ftp://x"}, "url"),
                  ({"url": "https://nutzer:pw@cloud.example.org/"}, "url"), ({"benutzer": ""}, "benutzer"),
                  ({"ordner": "../etc"}, "ordner"), ({"von": "25:00"}, "von"), ({"bis": "5"}, "bis"),
                  ({"ziel_kennwort": ""}, "ziel_kennwort")]
        for aenderung, feld in faelle:
            with self.subTest(feld=feld):
                r = self.a.post(self.url, {**self.gueltig, **aenderung, "kennwort": KENNWORT, "code": "x"}, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn(feld, r.json())
        self.assertEqual(self.auftragsdateien(), [])

    def test_ziel_festlegen_zugang_nur_in_der_auftragsdatei(self):
        r = self.a.post(self.url, {**self.gueltig, "kennwort": KENNWORT, "code": self.admin_codes[0]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        datei = self.auftragsdatei()
        self.assertEqual(datei["geheim"], {"kennwort": "App-Passwort-1234"})
        self.assertEqual(datei["parameter"], {"url": "https://cloud.example.org/remote.php/dav/files/epm",
                                              "benutzer": "epm-sicherung", "ordner": "EPM/Sicherungen",
                                              "von": "02:00", "bis": "05:00"})
        self.nirgends_in_der_datenbank("App-Passwort-1234")
        e = self.a.get("/api/protokoll/?gruppe=backup").json()["results"]
        self.assertIn("Übertragungsziel festgelegt: https://cloud.example.org/remote.php/dav/files/epm, Ordner "
                      "„EPM/Sicherungen“, Zeitfenster 02:00–05:00, neues Passwort für das Ziel", e[0]["beschreibung"])
        # lokaler WebDAV-Server (Test) mit http erlaubt; bei bestehendem Ziel darf das Passwort fehlen (bleibt)
        self.status_schreiben()
        Path(self.ordner / "auftraege").joinpath(f"{datei['id']}.json").unlink()
        Systemauftrag.objects.update(status=Systemauftrag.Status.ERLEDIGT)
        r = self.a.post(self.url, {**self.gueltig, "url": "http://127.0.0.1:8099", "ziel_kennwort": "",
                                   "kennwort": KENNWORT, "code": self.admin_codes[1]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotIn("geheim", self.auftragsdatei())

    def test_testen_uebertragen_entfernen(self):
        self.assertEqual(self.a.post("/api/backup/ziel/testen/").status_code, 201)
        self.assertEqual(self.a.post("/api/backup/uebertragen/").status_code, 201)
        self.assertEqual(self.a.post("/api/backup/ziel/entfernen/").status_code, 400)  # Passwort + 2FA
        r = self.a.post("/api/backup/ziel/entfernen/", {"kennwort": KENNWORT, "code": self.admin_codes[0]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(self.auftragsdateien()), 3)
        # wartende Aufträge der Backup-Seite lassen sich dort zurückziehen
        a = Systemauftrag.objects.get(aktion="sicherung_uebertragen")
        r = self.a.post(f"/api/backup/auftraege/{a.kennung}/abbrechen/")
        self.assertEqual(r.json()["status"], "abgebrochen")
        u = Systemauftrag.objects.create(ziel="server", aktion="updates_suchen", angefordert_von=self.admin)
        self.assertEqual(self.a.post(f"/api/backup/auftraege/{u.kennung}/abbrechen/").status_code, 404)
        d = self.a.get("/api/backup/").json()
        self.assertEqual({x["aktion"] for x in d["auftraege"]},
                         {"sicherung_ziel_testen", "sicherung_uebertragen", "sicherung_ziel_entfernen"})


class Wiederherstellen(Backupverzeichnis):
    def url(self, stempel="2026-10-01_020000"):
        return f"/api/backup/{stempel}/wiederherstellen/"

    def test_nur_bekannte_sicherung_mit_laufendem_agenten(self):
        daten = {"kennwort": KENNWORT, "code": self.admin_codes[0], "minuten": 0}
        self.assertEqual(self.a.post(self.url(), daten, format="json").status_code, 409)   # kein Status
        self.status_schreiben(zeit=iso(1))
        self.assertEqual(self.a.post(self.url(), daten, format="json").status_code, 409)   # Agent meldet sich nicht
        self.status_schreiben(sicherungen=[eine_sicherung(), eine_sicherung("2026-09-30_020000", dokumente=False)])
        self.assertEqual(self.a.post(self.url("2026-09-01_020000"), daten, format="json").status_code, 404)
        self.assertEqual(self.a.post(self.url("..%2F..%2Fetc"), daten, format="json").status_code, 404)
        self.assertEqual(self.a.post(self.url("2026-09-30_020000"), daten, format="json").status_code, 409)
        self.assertEqual(self.auftragsdateien(), [])

    def test_mit_passwort_und_2fa_warnt_alle(self):
        self.status_schreiben()
        r = self.a.post(self.url(), {"minuten": 5}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.a.post(self.url(), {"kennwort": KENNWORT, "code": self.admin_codes[0], "minuten": 5}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        datei = self.auftragsdatei()
        self.assertEqual(datei["aktion"], "wiederherstellen")
        self.assertEqual(datei["parameter"]["stempel"], "2026-10-01_020000")
        self.assertEqual(datei["parameter"]["minuten"], 5)
        h = client_fuer(self.betrachter).get("/api/system/hinweis/").json()["hinweis"]
        self.assertIn("auf eine Sicherung zurückgesetzt", h["text"])
        e = self.a.get("/api/protokoll/?gruppe=backup").json()["results"]
        self.assertTrue(e[0]["beschreibung"].startswith("Wiederherstellen der Sicherung vom "), e[0])
        self.assertIn("mit Passwort und 2FA bestätigt", e[0]["beschreibung"])

    def test_nachtragen_nach_dem_start(self):
        """Der Agent vermerkt die Wiederherstellung, bevor das Backend mit der zurückgespielten Datenbank startet."""
        codes = mit_zweitem_faktor(self.mitarbeiter)
        echte_anmeldung(self.mitarbeiter, codes[0])
        self.assertTrue(Session.objects.exists() and Sitzung.objects.exists())
        kennung = "a" * 32
        eintraege = [{"id": "b" * 32, "stempel": "2026-09-30_020000", "status": "fehler", "angefordert_von": "admin"},
                     {"id": kennung, "stempel": "2026-10-01_020000", "sicherung_zeitpunkt": "2026-10-01T02:00:03+02:00",
                      "angefordert_von": "admin", "begonnen_am": iso(0.1), "vorher_stempel": "2026-10-02_101500",
                      "status": "umgestellt", "ergebnis": ""}]
        (self.ordner / "status" / "wiederherstellungen.json").write_text(json.dumps(eintraege))
        call_command("epm_wiederherstellungen_nachtragen", stdout=open(os.devnull, "w"))
        self.assertFalse(Session.objects.exists() or Sitzung.objects.exists())
        a = Systemauftrag.objects.get(aktion="wiederherstellen")
        self.assertEqual((a.kennung.hex, a.status, a.angefordert_von), (kennung, "laeuft", self.admin))
        e = SystemEreignis.objects.get(art="backup", details__ereignis="wiederhergestellt")
        self.assertEqual((e.benutzer, e.details["vorher_stempel"]), (self.admin, "2026-10-02_101500"))
        # Ergebnis des Agenten wird übernommen; das Nachtragen geschieht nur einmal
        (self.ordner / "status" / "auftraege" / f"{kennung}.json").write_text(json.dumps(
            {"id": kennung, "status": "erledigt", "rueckgabe": 0, "beendet_am": iso(), "ergebnis": "Sicherung wiederhergestellt."}))
        d = self.a.get("/api/backup/").json()
        self.assertEqual(d["auftraege"][0]["status"], "erledigt")
        call_command("epm_wiederherstellungen_nachtragen", stdout=open(os.devnull, "w"))
        self.assertEqual(SystemEreignis.objects.filter(details__ereignis="wiederhergestellt").count(), 1)
        texte = [x["beschreibung"] for x in self.a.get("/api/protokoll/?gruppe=backup").json()["results"]]
        self.assertIn("Sicherung vom 01.10.2026 02:00 wiederhergestellt, alle Anmeldungen beendet – der Stand davor "
                      "(auch dieses Audit-Log) ist in der Sicherung 2026-10-02_101500", texte)
        self.assertIn("Sicherung wiederherstellen erledigt: Sicherung wiederhergestellt.", texte)


@unittest.skipUnless(AGENT.exists() and SKRIPT.exists() and shutil.which("gpg") and shutil.which("jq"),
                     "Systemagent und Backup-Skript nur im Repo, GnuPG und jq nötig")
class EchterAgent(Backupverzeichnis):
    """Backend legt ab → echter Agent → echtes epm-backup.sh mit GnuPG (nur ``docker`` ist nachgestellt) → Backend
    zeigt an, prüft das Passwort, druckt das Blatt. Verzeichnisse wie auf dem Server, nur in /tmp."""

    def setUp(self):
        super().setUp()
        self.basis = Path(tempfile.mkdtemp(prefix="epm-basis-"))
        os.symlink(self.ordner, self.basis / "system")
        (self.basis / "data" / "dokumente" / "100001").mkdir(parents=True)
        (self.basis / "data" / "dokumente" / "100001" / "brief.pdf").write_bytes(b"%PDF-1.4 Brief")
        (self.basis / "data" / "loeschliste").mkdir()
        (self.basis / "data" / "loeschliste" / "loeschliste.jsonl").write_text('{"nummer": 7}\n')
        (self.basis / ".env").write_text("EPM_VERSION=9.9.9\n")
        self.konf = self.basis / "konf"
        bin_ = self.basis / "bin"
        bin_.mkdir()
        # nachgestelltes docker: „compose exec … pg_dump“ liefert einen erkennbaren Dump, alles andere tut nichts
        (bin_ / "docker").write_text('#!/bin/sh\ncase "$*" in *pg_dump*) printf "PGDMP-TESTDUMP" ;; esac\nexit 0\n')
        (bin_ / "docker").chmod(0o755)
        self.umgebung = {**os.environ, "PATH": f"{bin_}:{os.environ.get('PATH', '')}"}

    def tearDown(self):
        shutil.rmtree(self.basis, ignore_errors=True)
        super().tearDown()

    def agent(self):
        p = subprocess.run([sys.executable, str(AGENT), "auftraege", "--basis", str(self.basis), "--konf", str(self.konf),
                            "--backup-skript", str(SKRIPT)], capture_output=True, text=True, timeout=600,
                           env=self.umgebung)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.auftragsdateien(), [])

    def test_gescheiterte_sicherung_hinterlaesst_nichts(self):
        """Scheitert das Packen der Dokumente, nachdem der Datenbank-Dump schon fertig ist, bleibt kein Dump als halbe
        Sicherung liegen (O-27) – er stünde sonst in der Liste und würde mit übertragen."""
        self.assertEqual(self.a.post("/api/backup/jetzt/").status_code, 201)
        self.agent()
        self.assertEqual(len(self.a.get("/api/backup/").json()["sicherungen"]), 1)
        vorher = sorted(p.name for p in (self.basis / "backup").iterdir() if p.name.startswith("epm"))
        shutil.rmtree(self.basis / "data" / "dokumente")
        import time
        time.sleep(1.1)   # eigener Zeitstempel für den zweiten Lauf
        self.assertEqual(self.a.post("/api/backup/jetzt/").status_code, 201)
        self.agent()
        d = self.a.get("/api/backup/").json()
        self.assertEqual(d["auftraege"][0]["status"], "fehler", d["auftraege"][0]["ausgabe"])
        self.assertIn("es bleibt keine unvollständige Sicherung liegen", d["auftraege"][0]["ausgabe"])
        self.assertEqual(len(d["sicherungen"]), 1)
        self.assertEqual(sorted(p.name for p in (self.basis / "backup").iterdir() if p.name.startswith("epm")), vorher)

    def test_passwort_sicherung_pruefen_und_blatt(self):
        # 1. unverschlüsselte Sicherung (noch kein Passwort)
        self.assertEqual(self.a.post("/api/backup/jetzt/").status_code, 201)
        self.agent()
        d = self.a.get("/api/backup/").json()
        self.assertEqual(d["auftraege"][0]["status"], "erledigt", d["auftraege"][0]["ausgabe"])
        self.assertEqual(len(d["sicherungen"]), 1)
        self.assertFalse(d["sicherungen"][0]["verschluesselt"])
        self.assertIn("unverschlüsselt", d["kurz"]["hinweise"][0])
        # 2. Passwort festlegen
        r = self.a.post("/api/backup/passwort/", {"passwort": PASSWORT, "passwort2": PASSWORT, "kennwort": KENNWORT,
                                                  "code": self.admin_codes[0]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.agent()
        d = self.a.get("/api/backup/").json()
        self.assertEqual(d["auftraege"][0]["status"], "erledigt", d["auftraege"][0]["ausgabe"])
        self.assertEqual(d["auftraege"][0]["ergebnis"], "Sicherungs-Passwort Nr. 1 festgelegt. Es gilt ab der nächsten "
                                                        "Sicherung.")
        self.assertTrue(d["verschluesselung"]["eingerichtet"])
        self.assertEqual(d["verschluesselung"]["aktuell"], 1)
        self.assertEqual(d["verschluesselung"]["versionen"][0]["gesetzt_von"], "admin")
        self.assertEqual(stat.S_IMODE((self.konf / "passwort-1").stat().st_mode), 0o600)
        # 3. verschlüsselte Sicherung
        self.assertEqual(self.a.post("/api/backup/jetzt/").status_code, 201)
        self.agent()
        d = self.a.get("/api/backup/").json()
        neu = d["sicherungen"][0]
        self.assertTrue(neu["verschluesselt"], d["auftraege"][0]["ausgabe"])
        self.assertEqual((neu["passwort_nr"], neu["art"], neu["ausgeloest_von"], neu["epm_version"]),
                         (1, "von_hand", "admin", "9.9.9"))
        self.assertTrue(neu["loeschliste"] and neu["dokumente"] and neu["pruefsummen"])
        self.assertEqual(len(d["sicherungen"]), 2)
        # mit dem Passwort lesbar, mit einem anderen nicht
        datei = self.basis / "backup" / next(n for n in neu["dateien"] if n.startswith("epm-db_"))
        self.assertTrue(datei.name.endswith(".dump.gpg"))
        self.assertNotIn(b"PGDMP-TESTDUMP", datei.read_bytes())
        heim = tempfile.mkdtemp(prefix="epm-gpg-")
        try:
            gpg = ["gpg", "--homedir", heim, "--batch", "--quiet", "--pinentry-mode", "loopback", "--decrypt",
                   "--passphrase-fd", "0", str(datei)]
            p = subprocess.run(gpg, input=PASSWORT.encode(), capture_output=True, timeout=120)
            self.assertEqual(p.stdout, b"PGDMP-TESTDUMP", p.stderr)
            p = subprocess.run(gpg, input=b"ein-anderes-Passwort-1", capture_output=True, timeout=120)
            self.assertNotEqual(p.returncode, 0)
        finally:
            subprocess.run(["gpgconf", "--homedir", heim, "--kill", "all"], capture_output=True)
            shutil.rmtree(heim, ignore_errors=True)
        # 4. Backend prüft das Passwort gegen den Prüfwert des Servers und druckt das Blatt
        self.assertEqual(self.a.post("/api/backup/passwort/pruefen/", {"passwort": PASSWORT}, format="json").json(),
                         {"stimmt": True, "nr": 1, "aktuell": True})
        r = self.a.post("/api/backup/passwortblatt/", {"passwort": PASSWORT}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))
        # 5. das Passwort steht nirgends außer in /etc/epm/sicherung (hier: konf/)
        self.nirgends_in_der_datenbank(PASSWORT)
        for pfad in (self.ordner / "status").rglob("*.json"):
            self.assertNotIn(PASSWORT, pfad.read_text(), pfad)
        self.assertEqual((self.konf / "passwort-1").read_text(), PASSWORT)
