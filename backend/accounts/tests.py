"""Anmeldung, Sperre, Einmal-Kennwort, Sitzungen und Einstellungen in „Mein Konto“ (echte Datenbank)."""
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from accounts.models import Rolle, Sitzung, User
from audit.models import SystemEreignis
from epm.pruefhilfen import (
    KENNWORT,
    benutzer,
    client_fuer,
    echte_anmeldung,
    mit_zweitem_faktor,
)


class Anmeldung(TestCase):
    def setUp(self):
        cache.clear()  # Drosselung der Anmeldung zurücksetzen
        self.user = User(username="neu", first_name="Nina", last_name="Neu", rolle=Rolle.MITARBEITER)
        self.kennwort = self.user.neues_einmal_kennwort()
        self.user.save()
        self.c = APIClient(enforce_csrf_checks=False)

    def anmelden(self, kennwort, client=None):
        return (client or self.c).post("/api/auth/anmelden/", {"benutzername": "neu", "kennwort": kennwort},
                                       format="json")

    def test_erstanmeldung(self):
        r = self.anmelden(self.kennwort)
        self.assertEqual(r.json()["schritt"], "kennwort_aendern")
        self.assertEqual(self.c.get("/api/patienten/").status_code, 403)
        # 2FA darf erst nach eigenem Kennwort eingerichtet werden
        self.assertEqual(self.c.post("/api/auth/2fa/einrichten/").status_code, 403)
        r = self.c.post("/api/auth/kennwort/", {"neu": "Ein-langes-neues-Kennwort-42"}, format="json")
        self.assertEqual(r.json()["schritt"], "2fa_einrichten")
        self.user.refresh_from_db()
        self.assertIsNone(self.user.einmal_kennwort_gueltig_bis)
        self.assertIsNotNone(self.user.kennwort_geaendert_am)
        r = self.c.post("/api/auth/2fa/einrichten/")
        self.assertIn("<svg", r.json()["qr_svg"])
        geraet = TOTPDevice.objects.get(user=self.user)
        code = f"{totp(geraet.bin_key, geraet.step, geraet.t0, geraet.digits):06d}"
        r = self.c.post("/api/auth/2fa/bestaetigen/", {"code": code}, format="json")
        self.assertEqual(r.json()["schritt"], "fertig", r.content)
        self.assertEqual(len(r.json()["notfallcodes"]), 10)
        self.assertEqual(self.c.get("/api/patienten/").status_code, 200)
        # „Anmeldung und Sicherheit“ in Mein Konto
        s = self.c.get("/api/auth/sicherheit/").json()
        self.assertTrue(s["authenticator_aktiv"])
        self.assertIsNotNone(s["authenticator_eingerichtet_am"])
        self.assertEqual((s["notfallcodes_uebrig"], s["notfallcodes_gesamt"]), (10, 10))
        # nächste Anmeldung: Kennwort + Notfallcode
        self.c.post("/api/auth/abmelden/")
        self.anmelden("Ein-langes-neues-Kennwort-42")
        self.assertEqual(self.c.get("/api/auth/status/").json()["schritt"], "2fa")
        r = self.c.post("/api/auth/2fa/", {"code": r.json()["notfallcodes"][0]}, format="json")
        self.assertEqual(r.json()["schritt"], "fertig")
        self.assertEqual(self.c.get("/api/auth/sicherheit/").json()["notfallcodes_uebrig"], 9)

    def test_sperre_nach_fehlversuchen(self):
        for _ in range(4):
            self.assertEqual(self.anmelden("falsch").status_code, 401)
        r = self.anmelden("falsch")  # fünfter Fehlversuch sperrt das Konto
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json()["gesperrt"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertIsNotNone(self.user.gesperrt_am)
        self.assertEqual(SystemEreignis.objects.filter(art="anmeldung_fehlgeschlagen").count(), 5)
        self.assertTrue(SystemEreignis.objects.filter(art="anmeldung_gesperrt", benutzer=self.user).exists())
        # auch das richtige Kennwort hilft nicht mehr – die Sperre wird nur dann verraten
        r = self.anmelden(self.kennwort)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.anmelden("noch-falsch").status_code, 401)
        # Hinweis für den Admin; Entsperren macht die Anmeldung wieder möglich
        admin = benutzer("admin", Rolle.ADMIN)
        a = client_fuer(admin)
        self.assertIn(self.user.id, [h["id"] for h in a.get("/api/benutzer/hinweise/").json()])
        r = a.post(f"/api/benutzer/{self.user.id}/entsperren/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["fehlversuche"], 0)
        self.assertEqual(a.get("/api/benutzer/hinweise/").json(), [])
        self.assertEqual(self.anmelden(self.kennwort).json()["schritt"], "kennwort_aendern")

    def test_einmal_kennwort_laeuft_ab(self):
        self.user.einmal_kennwort_gueltig_bis = timezone.now() - timedelta(minutes=1)
        self.user.save(update_fields=["einmal_kennwort_gueltig_bis"])
        r = self.anmelden(self.kennwort)
        self.assertEqual(r.status_code, 401)
        self.assertTrue(r.json()["abgelaufen"])
        self.assertEqual(self.c.get("/api/auth/status/").json()["schritt"], "anmelden")
        # Admin erzeugt ein neues Einmal-Kennwort mit neuer Frist
        admin = benutzer("admin", Rolle.ADMIN)
        r = client_fuer(admin).post(f"/api/benutzer/{self.user.id}/einmal-kennwort/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()["gueltig_bis"])
        self.assertEqual(self.anmelden(r.json()["einmal_kennwort"]).json()["schritt"], "kennwort_aendern")

    def test_neuer_benutzer_hat_frist(self):
        admin = benutzer("admin", Rolle.ADMIN)
        r = client_fuer(admin).post("/api/benutzer/", {"username": "frist", "rolle": "betrachter",
                                                       "first_name": "F", "last_name": "F"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNotNone(r.json()["einmal_kennwort_gueltig_bis"])
        self.assertTrue(r.json()["muss_kennwort_aendern"])


class Sitzungen(TestCase):
    def setUp(self):
        cache.clear()
        self.user = benutzer("sitzung", Rolle.MITARBEITER)
        self.codes = mit_zweitem_faktor(self.user)

    def test_anzeigen_und_beenden(self):
        buero = echte_anmeldung(self.user, self.codes[0])
        laptop = echte_anmeldung(self.user, self.codes[1], browser="Mozilla/5.0 (Macintosh) Safari/605.1.15")
        liste = buero.get("/api/sitzungen/").json()
        self.assertEqual(len(liste), 2)
        eigene = [s for s in liste if s["diese"]]
        fremde = [s for s in liste if not s["diese"]]
        self.assertEqual(len(eigene), 1)
        self.assertTrue(all(s["browser"] for s in liste))
        # die eigene Sitzung wird über „Abmelden“ beendet, nicht hier
        self.assertEqual(buero.delete(f"/api/sitzungen/{eigene[0]['id']}/").status_code, 400)
        self.assertEqual(buero.delete(f"/api/sitzungen/{fremde[0]['id']}/").status_code, 204)
        self.assertEqual(laptop.get("/api/patienten/").status_code, 403)
        self.assertEqual(laptop.get("/api/auth/status/").json()["schritt"], "anmelden")
        self.assertEqual(len(buero.get("/api/sitzungen/").json()), 1)
        # fremde Sitzungen sind nicht sichtbar
        andere = benutzer("andere", Rolle.MITARBEITER)
        self.assertEqual(client_fuer(andere).get("/api/sitzungen/").json(), [])

    def test_abmelden_entfernt_sitzung(self):
        c = echte_anmeldung(self.user, self.codes[0])
        self.assertEqual(Sitzung.objects.filter(benutzer=self.user).count(), 1)
        c.post("/api/auth/abmelden/")
        self.assertEqual(Sitzung.objects.filter(benutzer=self.user).count(), 0)

    def test_sperre_beendet_alle_sitzungen(self):
        c = echte_anmeldung(self.user, self.codes[0])
        admin = benutzer("admin", Rolle.ADMIN)
        self.assertEqual(client_fuer(admin).post(f"/api/benutzer/{self.user.id}/sperren/").status_code, 200)
        self.assertEqual(c.get("/api/patienten/").status_code, 403)
        self.assertFalse(Sitzung.objects.filter(benutzer=self.user).exists())

    def test_kennwortwechsel_beendet_andere_sitzungen(self):
        a = echte_anmeldung(self.user, self.codes[0])
        b = echte_anmeldung(self.user, self.codes[1])
        r = a.post("/api/auth/kennwort/", {"alt": KENNWORT, "neu": "Ganz-neues-Kennwort-2026"}, format="json")
        self.assertEqual(r.json()["schritt"], "fertig", r.content)
        self.assertEqual(a.get("/api/patienten/").status_code, 200)
        self.assertEqual(b.get("/api/patienten/").status_code, 403)
        self.assertEqual(Sitzung.objects.filter(benutzer=self.user).count(), 1)

    def test_abgelaufene_sitzung_verschwindet(self):
        c = echte_anmeldung(self.user, self.codes[0])
        echte_anmeldung(self.user, self.codes[1])
        zweite = Sitzung.objects.filter(benutzer=self.user).order_by("-id").first()
        Session.objects.filter(session_key=zweite.sitzungsschluessel).update(
            expire_date=timezone.now() - timedelta(days=1))
        liste = c.get("/api/sitzungen/").json()
        self.assertEqual([s["diese"] for s in liste], [True])
        self.assertFalse(Sitzung.objects.filter(pk=zweite.pk).exists())  # aufgeräumt


class MeinKonto(TestCase):
    def setUp(self):
        self.user = benutzer("konto", Rolle.MITARBEITER)
        self.c = client_fuer(self.user)

    def darstellung(self, **werte):
        return self.c.patch("/api/auth/ich/", {"darstellung": werte}, format="json")

    def test_darstellung_wird_gespeichert(self):
        r = self.darstellung(schema="individuell", akzent="petrol", hintergrund="sand", dichte="kompakt",
                             schriftgroesse="gross", schriftstaerke="kraeftig", auto_dunkel=True)
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.darstellung["akzent"], "petrol")
        self.assertEqual(self.user.darstellung["dichte"], "kompakt")
        self.assertEqual(self.c.get("/api/auth/ich/").json()["darstellung"]["schriftgroesse"], "gross")

    def test_darstellung_wird_geprueft(self):
        faelle = [
            ({"akzent": "pink"}, "akzent"),
            ({"unbekannt": 1}, "unbekannt"),
            ({"akzent": "eigen"}, "akzent_eigen"),
            ({"akzent": "eigen", "akzent_eigen": "#777777"}, "akzent_eigen"),  # weder weiße noch dunkle Schrift lesbar
            ({"hintergrund": "eigen", "hintergrund_eigen": "#333333"}, "hintergrund_eigen"),  # zu dunkel
            ({"hintergrund": "eigen", "hintergrund_eigen": "weiss"}, "hintergrund_eigen"),
        ]
        for werte, feld in faelle:
            with self.subTest(werte=werte):
                r = self.darstellung(**werte)
                self.assertEqual(r.status_code, 400)
                self.assertIn(feld, r.json())
        self.assertEqual(self.darstellung(akzent="eigen", akzent_eigen="#1F3A5F").status_code, 200)
        self.assertEqual(self.darstellung(hintergrund="eigen", hintergrund_eigen="#F4EFE6").status_code, 200)

    def test_startseite_karten(self):
        r = self.c.patch("/api/auth/ich/", {"startseite": {"karten": [{"id": "gewicht", "sichtbar": False},
                                                                      {"id": "termine"}]}}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        karten = r.json()["startseite"]["karten"]
        self.assertEqual([k["id"] for k in karten][:2], ["gewicht", "termine"])
        self.assertEqual(len(karten), 5)  # fehlende Karten werden angehängt
        self.assertFalse(karten[0]["sichtbar"])
        doppelt = {"karten": [{"id": "termine"}, {"id": "termine"}]}
        self.assertEqual(self.c.patch("/api/auth/ich/", {"startseite": doppelt}, format="json").status_code, 400)
