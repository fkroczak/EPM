"""Befehl epm_firmenadmin: erster Admin einer Firma (Rollen je Firma vergibt in der Oberfläche nur ein Admin der Firma)."""
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.models import Mitgliedschaft, Rolle
from audit.models import SystemEreignis
from epm.pruefhilfen import benutzer
from stammdaten.models import Firma


class FirmenAdmin(TestCase):
    def setUp(self):
        self.admin = benutzer("chef", Rolle.ADMIN)
        self.rg = Firma.objects.get(kuerzel="rg")

    def aufruf(self, *args):
        out = StringIO()
        call_command("epm_firmenadmin", *args, stdout=out)
        return out.getvalue()

    def test_admin_der_rg_mit_audit(self):
        self.assertIn("jetzt Admin", self.aufruf("chef", "rg"))
        self.assertEqual(Mitgliedschaft.objects.get(benutzer=self.admin, firma=self.rg).rolle, Rolle.ADMIN)
        self.assertEqual(self.admin.rolle, Rolle.ADMIN)  # DSKM unverändert
        e = SystemEreignis.objects.get(art=SystemEreignis.Art.BENUTZER_GEAENDERT, objekt="chef")
        self.assertEqual(e.details["aenderungen"], {"rolle_rg": [Rolle.KEINE, Rolle.ADMIN]})
        # zweiter Aufruf ändert nichts und protokolliert nichts
        self.assertIn("bereits Admin", self.aufruf("chef", self.rg.kurzname.lower()))
        self.assertEqual(SystemEreignis.objects.filter(art=SystemEreignis.Art.BENUTZER_GEAENDERT).count(), 1)

    def test_bestehende_rolle_wird_admin(self):
        Mitgliedschaft.objects.create(benutzer=self.admin, firma=self.rg, rolle=Rolle.MITARBEITER)
        self.aufruf("chef", "RG")
        self.assertEqual(Mitgliedschaft.objects.get(benutzer=self.admin, firma=self.rg).rolle, Rolle.ADMIN)

    def test_dskm(self):
        u = benutzer("ma", Rolle.MITARBEITER)
        self.aufruf("ma", "dskm")
        u.refresh_from_db()
        self.assertEqual(u.rolle, Rolle.ADMIN)

    def test_abgelehnt(self):
        benutzer("probe", Rolle.MITARBEITER, ist_test=True)
        for args in (("niemand", "rg"), ("chef", "xyz"), ("probe", "rg")):
            with self.assertRaises(CommandError):
                self.aufruf(*args)
        self.assertFalse(Mitgliedschaft.objects.filter(rolle=Rolle.ADMIN).exists())
