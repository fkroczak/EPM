"""Schalter „Technische Verwaltung“ (11.10.2026): Django-Admin und API-Browseroberfläche nur für begrenzte Zeit."""
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from accounts.models import Rolle
from audit.models import SystemEreignis
from epm import technik
from epm.pruefhilfen import Grundlage, benutzer, echte_anmeldung, mit_zweitem_faktor
from stammdaten.models import Einstellungen


@override_settings(EPM_DJANGO_ADMIN=None, EPM_API_BROWSABLE=None)
class TechnikSchalter(Grundlage):
    def setUp(self):
        technik.vergessen()
        self.admin = benutzer("techadmin", Rolle.ADMIN)
        self.c = echte_anmeldung(self.admin, mit_zweitem_faktor(self.admin, 1)[0])

    def tearDown(self):
        technik.vergessen()

    def html(self, pfad):
        return self.c.get(pfad, HTTP_ACCEPT="text/html")

    def test_standard_aus(self):
        self.assertEqual(self.html("/verwaltung/").status_code, 404)
        r = self.html("/api/auth/status/")
        self.assertIn("application/json", r["Content-Type"])
        self.assertFalse(self.c.get("/api/system/technik/").json()["an"])

    def test_einschalten_mit_ablauf_und_audit(self):
        r = self.c.put("/api/system/technik/", {"stunden": 1}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["an"] and r.json()["django_admin"] and r.json()["api_ansicht"])
        self.assertNotEqual(self.html("/verwaltung/").status_code, 404)
        self.assertIn("text/html", self.html("/api/auth/status/")["Content-Type"])
        self.assertTrue(SystemEreignis.objects.filter(objekt__startswith="Technische Verwaltung").exists())
        # abgelaufen: wieder aus, ohne dass jemand etwas tut
        Einstellungen.objects.filter(pk=1).update(technik_bis=timezone.now() - timedelta(seconds=1))
        technik.vergessen()
        self.assertEqual(self.html("/verwaltung/").status_code, 404)
        # sofort aus
        self.c.put("/api/system/technik/", {"stunden": 8}, format="json")
        self.assertFalse(self.c.put("/api/system/technik/", {"stunden": 0}, format="json").json()["an"])
        self.assertEqual(self.c.put("/api/system/technik/", {"stunden": 24}, format="json").status_code, 400)

    def test_nur_mit_systemrecht(self):
        m = benutzer("techmed", Rolle.MEDIZINER)
        c = echte_anmeldung(m, mit_zweitem_faktor(m, 1)[0])
        self.assertEqual(c.put("/api/system/technik/", {"stunden": 1}, format="json").status_code, 403)

    @override_settings(EPM_DJANGO_ADMIN=False)
    def test_server_konfiguration_ueberstimmt(self):
        self.c.put("/api/system/technik/", {"stunden": 1}, format="json")
        d = self.c.get("/api/system/technik/").json()
        self.assertEqual((d["an"], d["django_admin"], d["fest"]["django_admin"]), (True, False, False))
        self.assertEqual(self.html("/verwaltung/").status_code, 404)
