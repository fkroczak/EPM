"""Datenbank leeren (Festlegung 03.10.2026, U27) und Schalter unter Administration › System."""
import unittest
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import override_settings

from accounts.models import Gruppenrecht, Rolle, User
from audit.models import SystemEreignis
from epm.pruefhilfen import KENNWORT, TMP, benutzer, client_fuer
from patienten.models import Dokument, Kontakt, Loeschprotokoll, Patient
from stammdaten.models import Arzt, Einstellungen, Praeparat, Versorger

from .models import Systemauftrag
from .tests import AGENT, Systemverzeichnis


@override_settings(EPM_DOKUMENTE=Path(TMP) / "leeren-dokumente", EPM_LOESCHLISTE=Path(TMP) / "leeren-loeschliste.jsonl")
class DatenbankLeeren(Systemverzeichnis):
    def setUp(self):
        super().setUp()
        self.test = Patient.objects.create(nachname="Probe", vorname="P", geburtsdatum="1970-01-01", ist_test=True)
        self.neuer_kontakt()
        Versorger.objects.create(name="Testversorger")
        Arzt.objects.create(name="Dr. Test")
        self.tester = benutzer("tester", Rolle.MITARBEITER, ist_test=True)
        ordner = Path(settings.EPM_DOKUMENTE) / str(self.patient.nummer)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "x.txt").write_text("x")
        Path(settings.EPM_LOESCHLISTE).write_text('{"nummer": 1}\n')

    def test_ablauf_und_pruefungen(self):
        c = self.a
        # nur Admin
        Gruppenrecht.objects.create(rolle=Rolle.MEDIZINER, recht="system_verwalten", erlaubt=True)
        self.assertEqual(client_fuer(self.mediziner).post("/api/system/leeren/vorbereiten/").status_code, 403)
        v = c.post("/api/system/leeren/vorbereiten/").json()
        self.assertEqual((v["umfang"]["patienten"], v["umfang"]["testpatienten"]), (1, 1))
        self.assertTrue(next(b for b in v["benutzer"] if b["id"] == self.admin.id)["eigene"])
        daten = {"bestaetigung": v["code"], "wirklich": True, "behalten": [self.mediziner.id], "minuten": 0,
                 "kennwort": KENNWORT, "code": self.admin_codes[0]}
        self.assertEqual(list(c.post("/api/system/leeren/", {**daten, "bestaetigung": "FALSCH"}, format="json").json()),
                         ["bestaetigung"])
        self.assertEqual(list(c.post("/api/system/leeren/", {**daten, "wirklich": False}, format="json").json()),
                         ["wirklich"])
        r = c.post("/api/system/leeren/", daten, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        auftrag = Systemauftrag.objects.get(aktion="datenbank_leeren")
        self.assertEqual(auftrag.parameter, {"behalten": sorted([self.admin.id, self.mediziner.id]), "minuten": 0})
        # Code gilt nur einmal
        self.assertEqual(c.post("/api/system/leeren/", daten, format="json").status_code, 400)

    def test_leeren(self):
        praeparate = Praeparat.objects.count()
        self.assertGreater(praeparate, 0)
        from accounts.models import Sitzung

        Sitzung.objects.create(benutzer=self.mediziner, sitzungsschluessel="med-sitzung")
        Sitzung.objects.create(benutzer=self.admin, sitzungsschluessel="admin-sitzung")
        aus = StringIO()
        call_command("epm_datenbank_leeren", "--von", "admin", "--behalten", str(self.mediziner.id),
                     "--sicherung", "2026-10-03_1200", "--ja", stdout=aus)
        self.assertEqual(Patient.objects.count(), 0)
        self.assertEqual(Kontakt.objects.count(), 0)
        self.assertEqual(Dokument.objects.count(), 0)
        self.assertEqual(Loeschprotokoll.objects.count(), 0)
        self.assertEqual(Versorger.objects.count() + Arzt.objects.count(), 0)
        self.assertEqual(Praeparat.objects.count(), praeparate)  # Präparate und Vorlagen bleiben
        self.assertEqual(set(User.objects.values_list("username", flat=True)), {"admin", "mediziner"})
        # auch die bleibenden Konten müssen sich neu anmelden (nur das ausführende nicht)
        self.assertEqual(list(Sitzung.objects.values_list("sitzungsschluessel", flat=True)), ["admin-sitzung"])
        self.assertFalse(Einstellungen.aktuell().musterdaten_automatisch)
        self.assertEqual(list(Path(settings.EPM_DOKUMENTE).iterdir()), [])
        self.assertEqual(Path(settings.EPM_LOESCHLISTE).read_text(), "")
        # Audit-Log beginnt neu mit „Datenbank geleert“
        e = SystemEreignis.objects.get()
        self.assertEqual((e.details["ereignis"], e.benutzer), ("datenbank_geleert", self.admin))
        log = self.a.get("/api/protokoll/").json()["results"]
        self.assertIn("Datenbank geleert: 1 Akten, 1 Testpatienten", log[0]["beschreibung"])
        # Musterdaten werden danach nicht mehr automatisch angelegt
        call_command("epm_musterdaten", stdout=StringIO())
        self.assertEqual(Patient.objects.count(), 0)
        self.assertNotIn("e2e", "".join(User.objects.values_list("username", flat=True)))
        # ohne --ja passiert nichts
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("epm_datenbank_leeren", "--von", "admin", stdout=StringIO())

    def test_schalter(self):
        c = self.a
        d = c.get("/api/system/uebersicht/").json()
        self.assertEqual(d["einstellungen"], {"musterdaten_automatisch": True, "import_ausgeblendet": False})
        self.assertTrue(d["leeren_erlaubt"])
        r = c.post("/api/system/einstellungen/", {"import_ausgeblendet": True, "musterdaten_automatisch": False},
                   format="json")
        self.assertEqual(r.json(), {"musterdaten_automatisch": False, "import_ausgeblendet": True})
        self.assertTrue(c.get("/api/auth/ich/").json()["import_ausgeblendet"])
        self.assertEqual(c.post("/api/system/einstellungen/", {"import_ausgeblendet": "ja"}, format="json").status_code,
                         400)
        self.assertEqual(client_fuer(self.mitarbeiter).post("/api/system/einstellungen/", {"import_ausgeblendet": False},
                                                             format="json").status_code, 403)
        call_command("epm_musterdaten", stdout=StringIO())
        self.assertFalse(Patient.objects.filter(ist_test=True, nummer__gte=9001).exclude(pk=self.test.pk).exists())

    @unittest.skipUnless(AGENT.exists(), "rollout/epm-systemagent.py nur im Repo (nicht im Image)")
    def test_agent(self):
        """Der Agent kennt die Aktion (gleiche Liste wie host.py), sichert vorher, prüft die Auswahl der Konten und
        leert nie ohne Sicherung."""
        import importlib.util
        from types import SimpleNamespace

        from .host import AKTIONEN as BACKEND

        spec = importlib.util.spec_from_file_location("epm_systemagent", AGENT)
        agent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent)
        self.assertEqual(agent.AKTIONEN["datenbank_leeren"], ("Datenbank leeren", True))
        self.assertTrue(BACKEND["datenbank_leeren"]["sichern"])
        self.assertIn("datenbank_leeren", agent.SICHERUNG_AKTIONEN)
        zeilen = []
        a = SimpleNamespace()
        leeren = agent.Agent.leeren
        self.assertEqual(leeren(a, "1,2", "admin", zeilen.append, vorher="x")[0], 2)
        self.assertEqual(leeren(a, [1, True], "admin", zeilen.append, vorher="x")[0], 2)
        self.assertEqual(leeren(a, [1], "", zeilen.append, vorher="x")[0], 2)
        self.assertEqual(leeren(a, [1], "admin", zeilen.append, vorher=None)[0], 1)
        rc, text = leeren(a, [1, 2], "admin", zeilen.append, vorher=None, simuliert=True)
        self.assertEqual((rc, text), (0, "Probelauf: nichts geleert."))
        self.assertIn("epm_datenbank_leeren --von admin --behalten 1,2", zeilen[-1])
