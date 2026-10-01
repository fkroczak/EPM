"""Anmeldung, Sperre, Einmal-Kennwort, Sitzungen und Einstellungen in „Mein Konto“ (echte Datenbank)."""
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from accounts.models import Gruppenrecht, Rolle, Sitzung, User
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
        status = self.c.get("/api/auth/status/").json()
        self.assertEqual(status["schritt"], "anmelden")
        self.assertEqual(status["organisation"]["anschrift"], "Waltrup 16 · 48341 Altenberge")
        self.assertNotIn("benutzer", status)
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
        # falscher Code, danach kurze Sperre mit eigener Meldung (nicht „Code ungültig“)
        falsch = "000000" if code != "000000" else "111111"
        self.assertIn("Code ungültig", self.c.post("/api/auth/2fa/bestaetigen/", {"code": falsch}, format="json").json()["fehler"])
        r = self.c.post("/api/auth/2fa/bestaetigen/", {"code": code}, format="json")
        self.assertEqual(r.status_code, 429)
        self.assertIn("warten", r.json()["fehler"])
        TOTPDevice.objects.filter(pk=geraet.pk).update(throttling_failure_timestamp=None, throttling_failure_count=0)
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
        # Audit-Log wie im Entwurf 20
        log = a.get("/api/protokoll/?gruppe=fehlversuch").json()["results"]
        texte = [e["beschreibung"] for e in log]
        self.assertIn("Falsches Passwort (3. Versuch)", texte)
        gesperrt = [e for e in log if e["art"] == "anmeldung_gesperrt" and "Konto gesperrt" in e["beschreibung"]]
        self.assertEqual(len(gesperrt), 1)
        self.assertRegex(gesperrt[0]["beschreibung"], r"^5 falsche Passwörter in \d+ Minuten, Konto gesperrt$")
        self.assertEqual({e["gruppe_name"] for e in log}, {"Fehlversuch"})
        self.assertTrue(all("geraet" in e for e in log))
        entsperrt = a.get("/api/protokoll/?gruppe=benutzer").json()["results"][0]
        self.assertEqual(entsperrt["beschreibung"], "Benutzer neu entsperrt")
        self.assertEqual(a.get("/api/protokoll/?gruppe=unbekannt").status_code, 400)

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

    def test_sitzung_laeuft_nach_30_minuten_ab(self):
        """F12: 30 Minuten ohne Anfrage → Sitzung ungültig; jede Anfrage verlängert sie."""
        from datetime import timedelta

        from django.conf import settings
        from django.contrib.sessions.models import Session
        from django.utils import timezone

        self.assertEqual((settings.SESSION_COOKIE_AGE, settings.SESSION_SAVE_EVERY_REQUEST), (30 * 60, True))
        c = echte_anmeldung(self.user, self.codes[0])
        self.assertEqual(c.get("/api/patienten/").status_code, 200)
        schluessel = c.session.session_key
        ablauf = Session.objects.get(session_key=schluessel).expire_date
        self.assertGreater(ablauf, timezone.now() + timedelta(minutes=29))
        Session.objects.filter(session_key=schluessel).update(expire_date=timezone.now() - timedelta(seconds=1))
        r = c.get("/api/patienten/")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(c.get("/api/auth/status/").json()["schritt"], "anmelden")

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

    def test_admin_sitzung_bleibt_bei_benutzerverwaltung(self):
        """Ablauf wie in der Oberfläche: anlegen, erste Anmeldung der neuen Person, sperren, entsperren,
        Einmal-Kennwort, 2FA zurücksetzen – die Sitzung des Admins bleibt gültig, die der Person endet."""
        chef = benutzer("chef", Rolle.ADMIN)
        a = echte_anmeldung(chef, mit_zweitem_faktor(chef)[0])
        r = a.post("/api/benutzer/", {"username": "neu.heilmann", "titel": "Dr. med.", "first_name": "Henrike",
                                      "last_name": "Heilmann", "kuerzel": "HH", "funktion": "Ärztin",
                                      "rolle": "mediziner"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        neu_id, einmal = r.json()["id"], r.json()["einmal_kennwort"]
        p = APIClient(HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) Chrome/140.0")
        r = p.post("/api/auth/anmelden/", {"benutzername": "neu.heilmann", "kennwort": einmal}, format="json")
        self.assertEqual(r.json()["schritt"], "kennwort_aendern", r.content)
        self.assertEqual(a.get("/api/auth/status/").json()["schritt"], "fertig")
        for schritt in ("sperren", "entsperren", "einmal-kennwort", "2fa-zuruecksetzen"):
            with self.subTest(schritt=schritt):
                r = a.post(f"/api/benutzer/{neu_id}/{schritt}/")
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(a.get("/api/auth/status/").json()["schritt"], "fertig")
                self.assertEqual(a.get("/api/rechte/").status_code, 200)
        self.assertEqual(p.get("/api/auth/status/").json()["schritt"], "anmelden")
        self.assertEqual(Sitzung.objects.filter(benutzer=chef).count(), 1)

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


class RechteJeGruppe(TestCase):
    """Rechte je Gruppe: Standard, Änderung durch die Administration, feste Rechte, Testbenutzer."""

    @classmethod
    def setUpTestData(cls):
        from patienten.models import Patient

        cls.admin = benutzer("admin", Rolle.ADMIN)
        cls.mediziner = benutzer("mediziner", Rolle.MEDIZINER)
        cls.mitarbeiter = benutzer("mitarbeiter", Rolle.MITARBEITER)
        cls.betrachter = benutzer("betrachter", Rolle.BETRACHTER)
        cls.patient = Patient.objects.create(nachname="Recht", vorname="R", geburtsdatum="1970-01-01")

    def test_standard(self):
        r = client_fuer(self.admin).get("/api/rechte/").json()
        m = r["matrix"]
        self.assertTrue(m["mediziner"]["vorlagen_pflegen"])
        self.assertTrue(m["mediziner"]["audit_lesen"])
        for code in ("benutzer_verwalten", "akten_wieder_oeffnen", "backup_verwalten", "testdaten_zuruecksetzen"):
            self.assertFalse(m["mediziner"][code], code)
            self.assertTrue(m["admin"][code], code)
        # Festlegung 01.10.2026: Admin alles (Patientendaten nur bei Testpatienten), Mitarbeiter schließen Akten ab
        # und pflegen Vorlagen
        # Festlegung 02.10.2026: endgültig löschen nur Mediziner – sonst hat der Admin alles
        self.assertEqual([c for c, v in m["admin"].items() if not v], ["dokumente_loeschen"])
        self.assertTrue(m["mediziner"]["dokumente_loeschen"])
        self.assertTrue(m["mediziner"]["dokumente_umhaengen"])
        self.assertTrue(m["admin"]["dokumente_umhaengen"])
        self.assertFalse(m["mitarbeiter"]["dokumente_loeschen"])
        # Festlegung 02.10.2026: Systemverwaltung (Server und EPM) nur Admin
        self.assertEqual(r["nur_rollen"], {"dokumente_loeschen": ["mediziner"], "system_verwalten": ["admin"]})
        abgelehnt = client_fuer(self.admin).put("/api/rechte/", {"matrix": {"mitarbeiter": {"dokumente_loeschen": True}}},
                                               format="json")
        self.assertEqual(abgelehnt.status_code, 400)
        self.assertIn("Mediziner vorbehalten", abgelehnt.json()["mitarbeiter.dokumente_loeschen"])
        self.assertEqual(r["nur_testpatienten"]["rollen"], ["admin"])
        self.assertIn("akten_abschliessen", r["nur_testpatienten"]["rechte"])
        for code in ("akten_abschliessen", "vorlagen_pflegen", "eintraege_erfassen", "akten_bearbeiten"):
            self.assertTrue(m["mitarbeiter"][code], code)
        for code in ("plaene_anlegen", "plaene_freigeben", "audit_lesen", "akten_wieder_oeffnen"):
            self.assertFalse(m["mitarbeiter"][code], code)
        self.assertEqual(m["betrachter"], {c["code"]: c["code"] == "akten_lesen" for c in r["rechte"]})
        self.assertIn(["admin", "benutzer_verwalten"], r["fest"])
        ich = client_fuer(self.mediziner).get("/api/auth/ich/").json()
        self.assertIn("vorlagen_pflegen", ich["rechte"])
        self.assertNotIn("benutzer_verwalten", ich["rechte"])
        self.assertEqual(client_fuer(self.mediziner).get("/api/rechte/").status_code, 403)
        self.assertEqual(client_fuer(self.mediziner).get("/api/protokoll/").status_code, 200)
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/protokoll/").status_code, 403)

    def test_admin_aendert_rechte(self):
        a = client_fuer(self.admin)
        b = client_fuer(self.betrachter)
        kontakt = {"patient": self.patient.id, "text": "<p>Anruf</p>"}
        self.assertEqual(b.post("/api/kontakte/", kontakt, format="json").status_code, 403)
        r = a.put("/api/rechte/", {"matrix": {"betrachter": {"eintraege_erfassen": True}}}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["matrix"]["betrachter"]["eintraege_erfassen"])
        self.assertEqual(b.post("/api/kontakte/", kontakt, format="json").status_code, 201)
        # Lesen entziehen: Liste und Akte gesperrt
        a.put("/api/rechte/", {"matrix": {"betrachter": {"akten_lesen": False}}}, format="json")
        self.assertEqual(b.get("/api/patienten/").status_code, 403)
        self.assertEqual(b.get("/api/startseite/").status_code, 403)
        eintrag = a.get("/api/protokoll/?gruppe=benutzer").json()["results"][0]
        self.assertEqual(eintrag["beschreibung"], "Rechte geändert: Betrachter darf nicht mehr „Akten lesen“")
        self.assertEqual(Gruppenrecht.history.count(), 2)
        # zurück auf den Standard
        a.put("/api/rechte/", {"matrix": {"betrachter": {"akten_lesen": True, "eintraege_erfassen": False}}},
              format="json")
        self.assertEqual(b.get("/api/patienten/").status_code, 200)

    def test_feste_rechte_und_eingaben(self):
        a = client_fuer(self.admin)
        for matrix in ({"admin": {"benutzer_verwalten": False}}, {"chef": {"akten_lesen": True}},
                       {"mediziner": {"fliegen": True}}, {"mediziner": {"akten_lesen": "ja"}}):
            with self.subTest(matrix=matrix):
                self.assertEqual(a.put("/api/rechte/", {"matrix": matrix}, format="json").status_code, 400)
        self.assertEqual(a.put("/api/rechte/", {}, format="json").status_code, 400)
        # eigene Rolle nicht so ändern, dass die Benutzerverwaltung verloren geht
        r = a.patch(f"/api/benutzer/{self.admin.id}/", {"rolle": "mediziner"}, format="json")
        self.assertEqual(r.status_code, 400)
        # Mediziner darf mit dem Recht Benutzer verwalten
        a.put("/api/rechte/", {"matrix": {"mediziner": {"benutzer_verwalten": True}}}, format="json")
        self.assertEqual(client_fuer(self.mediziner).get("/api/benutzer/").status_code, 200)

    def test_testbenutzer_ohne_globale_rechte(self):
        tester = benutzer("tester", Rolle.MEDIZINER, ist_test=True)
        t = client_fuer(tester)
        ich = t.get("/api/auth/ich/").json()
        for code in ("vorlagen_pflegen", "versorger_pflegen", "audit_lesen"):
            self.assertNotIn(code, ich["rechte"])
        self.assertIn("plaene_freigeben", ich["rechte"])
        self.assertEqual(t.patch("/api/einstellungen/", {"kcal_max_tag": 4000}, format="json").status_code, 403)
        self.assertEqual(t.post("/api/versorger/", {"name": "Test-Versorger"}, format="json").status_code, 403)
        self.assertEqual(t.get("/api/protokoll/").status_code, 403)

    def test_freigabe_eigenes_recht(self):
        from infusionen.models import Infusionsplan

        a = client_fuer(self.admin)
        a.put("/api/rechte/", {"matrix": {"mediziner": {"plaene_freigeben": False}}}, format="json")
        m = client_fuer(self.mediziner)
        e = m.post("/api/infusionsplaene/entwurf/", {"patient": self.patient.id}, format="json").json()
        self.assertEqual(m.post(f"/api/infusionsplaene/{e['id']}/freigeben/").status_code, 403)
        self.assertEqual(Infusionsplan.objects.get(pk=e["id"]).status, "entwurf")

    def test_rechte_stand_im_antwortkopf(self):
        """Ändert die Administration die Rechte, merkt die Oberfläche es an der nächsten Antwort (ohne neue Anmeldung)."""
        codes = mit_zweitem_faktor(self.mitarbeiter)
        c = echte_anmeldung(self.mitarbeiter, codes[0])
        vorher = c.get("/api/auth/ich/")["X-EPM-Rechte"]
        self.assertEqual(len(vorher), 12)
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/")["X-EPM-Rechte"], vorher)
        Gruppenrecht.objects.create(rolle=Rolle.MITARBEITER, recht="akten_abschliessen", erlaubt=False)
        r = c.post(f"/api/patienten/{self.patient.id}/abschliessen/", {"anlass": "verstorben"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertNotEqual(r["X-EPM-Rechte"], vorher)
        self.assertNotIn("akten_abschliessen", c.get("/api/auth/ich/").json()["rechte"])
        # ohne Anmeldung kein Kopf
        self.assertNotIn("X-EPM-Rechte", APIClient().get("/api/auth/status/"))
