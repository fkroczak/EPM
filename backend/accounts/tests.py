"""Anmeldung, Sperre, Einmal-Passwort, Sitzungen und Einstellungen in „Mein Konto“ (echte Datenbank)."""
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from accounts.models import Anmelderegeln, Gruppenrecht, Rolle, Sitzung, User
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
        """Ablauf mit Pflicht zum zweiten Faktor (die Administration kann sie setzen; Standard ist freiwillig)."""
        Anmelderegeln.objects.update_or_create(pk=1, defaults={"zweiter_faktor": "alle"})
        status = self.c.get("/api/auth/status/").json()
        self.assertEqual(status["schritt"], "anmelden")
        self.assertEqual(status["organisation"]["anschrift"], "Waltrup 16 · 48341 Altenberge")
        self.assertNotIn("benutzer", status)
        r = self.anmelden(self.kennwort)
        self.assertEqual(r.json()["schritt"], "kennwort_aendern")
        self.assertEqual(self.c.get("/api/patienten/").status_code, 403)
        # 2FA darf erst nach eigenem Kennwort eingerichtet werden
        self.assertEqual(self.c.post("/api/auth/2fa/einrichten/").status_code, 403)
        r = self.c.post("/api/auth/kennwort/", {"neu": "Ein-langes-neues-Passwort-42"}, format="json")
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
        self.anmelden("Ein-langes-neues-Passwort-42")
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
        r = a.post("/api/auth/kennwort/", {"alt": KENNWORT, "neu": "Ganz-neues-Passwort-2026"}, format="json")
        self.assertEqual(r.json()["schritt"], "fertig", r.content)
        self.assertEqual(a.get("/api/patienten/").status_code, 200)
        self.assertEqual(b.get("/api/patienten/").status_code, 403)
        self.assertEqual(Sitzung.objects.filter(benutzer=self.user).count(), 1)

    def test_admin_sitzung_bleibt_bei_benutzerverwaltung(self):
        """Ablauf wie in der Oberfläche: anlegen, erste Anmeldung der neuen Person, sperren, entsperren,
        Einmal-Passwort, 2FA zurücksetzen – die Sitzung des Admins bleibt gültig, die der Person endet."""
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

    def test_aktenansicht(self):
        """Aufbau der Patientenakte je Person (Wunsch 08.10.2026): Stil, Höhe des Kopfs, Breite der Seitenleiste."""
        r = self.darstellung(aktenansicht="seitenleiste", aktenkopf="kompakt", aktenleiste_breite=360)
        self.assertEqual(r.status_code, 200, r.content)
        d = self.c.get("/api/auth/ich/").json()["darstellung"]
        self.assertEqual((d["aktenansicht"], d["aktenkopf"], d["aktenleiste_breite"]), ("seitenleiste", "kompakt", 360))
        # ohne Angabe gilt der Standard: Kopfzeile, voller Kopf, 300 px
        self.assertEqual(self.darstellung(dichte="kompakt").status_code, 200)
        d = self.c.get("/api/auth/ich/").json()["darstellung"]
        self.assertEqual((d["aktenansicht"], d["aktenkopf"], d["aktenleiste_breite"]), ("kopfzeile", "voll", 300))
        for werte, feld in [({"aktenansicht": "kacheln"}, "aktenansicht"), ({"aktenkopf": "riesig"}, "aktenkopf"),
                            ({"aktenleiste_breite": 100}, "aktenleiste_breite"),
                            ({"aktenleiste_breite": 900}, "aktenleiste_breite")]:
            with self.subTest(werte=werte):
                r = self.darstellung(**werte)
                self.assertEqual(r.status_code, 400)
                self.assertIn(feld, r.json())
        self.assertEqual(self.darstellung(aktenansicht="karteikarte").status_code, 200)

    def test_form_wird_ignoriert(self):
        """Die Form „rund/eckig“ gab es nur kurz (08.10.2026): mitgeschickt stört sie nicht, gespeichert wird sie nicht."""
        r = self.darstellung(form="eckig", dichte="kompakt")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn("form", self.c.get("/api/auth/ich/").json()["darstellung"])

    def test_startseite_karten(self):
        r = self.c.patch("/api/auth/ich/", {"startseite": {"karten": [{"id": "gewicht", "sichtbar": False},
                                                                      {"id": "termine"}]}}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        karten = r.json()["startseite"]["karten"]
        self.assertEqual([k["id"] for k in karten][:2], ["gewicht", "termine"])
        self.assertEqual(len(karten), 15)  # fehlende Kacheln werden mit ihrem Standard angehängt (S11)
        self.assertFalse(karten[0]["sichtbar"])
        self.assertEqual((karten[1]["breite"], karten[1]["hoehe"]), (2, 2))  # Standardgröße der Termine
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
        # Festlegung 02.10.2026: endgültig löschen (Dokumente, Akten) Mediziner und Admin – der Admin hat alles
        self.assertEqual([c for c, v in m["admin"].items() if not v], [])
        self.assertTrue(m["admin"]["dokumente_loeschen"])
        self.assertTrue(m["admin"]["akten_loeschen"])
        self.assertTrue(m["mediziner"]["dokumente_loeschen"])
        self.assertTrue(m["mediziner"]["dokumente_umhaengen"])
        self.assertTrue(m["admin"]["dokumente_umhaengen"])
        self.assertFalse(m["mitarbeiter"]["dokumente_loeschen"])
        # Festlegung 02.10.2026: Systemverwaltung Standard nur Admin, aber für eine Vertretung jeder Gruppe erteilbar
        self.assertEqual(r["nur_rollen"], {"dokumente_loeschen": ["admin", "mediziner"],
                                           "akten_loeschen": ["admin", "mediziner"],
                                           "altdaten_importieren": ["admin"]})
        self.assertFalse(m["mediziner"]["system_verwalten"])
        # Datenschutz: Mitarbeiter erfassen und schließen freigegebene Pläne ab, entscheiden und löschen nicht
        for code in ("datenschutz_bearbeiten", "plaene_abschliessen"):
            self.assertTrue(m["mitarbeiter"][code], code)
        for code in ("datenschutz_entscheiden", "akten_loeschen"):
            self.assertFalse(m["mitarbeiter"][code], code)
            self.assertTrue(m["mediziner"][code], code)
        self.assertIn("datenschutz_entscheiden", r["nur_testpatienten"]["rechte"])
        abgelehnt = client_fuer(self.admin).put("/api/rechte/", {"matrix": {"mitarbeiter": {"dokumente_loeschen": True}}},
                                               format="json")
        self.assertEqual(abgelehnt.status_code, 400)
        self.assertIn("Admin und Mediziner vorbehalten", abgelehnt.json()["mitarbeiter.dokumente_loeschen"])
        self.assertEqual(r["nur_testpatienten"]["rollen"], ["admin"])
        # Festlegung 02.10.2026 (Fehlerliste 6.3): Akten abschließen und Dokumente zuordnen auch bei echten Akten
        for code in ("akten_abschliessen", "dokumente_umhaengen", "dokumente_loeschen", "akten_loeschen"):
            self.assertNotIn(code, r["nur_testpatienten"]["rechte"])
        self.assertIn("eintraege_erfassen", r["nur_testpatienten"]["rechte"])
        # Rolle „Keine Berechtigung“ (6.2): kein Recht, nicht einstellbar
        self.assertEqual(r["ohne_rechte"], ["keine"])
        self.assertEqual(set(m["keine"].values()), {False})
        self.assertIn({"code": "keine", "name": "Keine Berechtigung"}, r["rollen"])
        nein = client_fuer(self.admin).put("/api/rechte/", {"matrix": {"keine": {"akten_lesen": True}}}, format="json")
        self.assertEqual(nein.status_code, 400)
        self.assertIn("keine Rechte", nein.json()["keine.akten_lesen"])
        for code in ("akten_abschliessen", "vorlagen_pflegen", "eintraege_erfassen", "akten_bearbeiten"):
            self.assertTrue(m["mitarbeiter"][code], code)
        for code in ("plaene_anlegen", "plaene_freigeben", "audit_lesen", "akten_wieder_oeffnen"):
            self.assertFalse(m["mitarbeiter"][code], code)
        self.assertEqual(m["betrachter"], {c["code"]: c["code"] in ("akten_lesen", "testdaten_sehen") for c in r["rechte"]})
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


class ZweiterFaktorFreiwillig(TestCase):
    """Fehlerliste 02.10.2026, 6.5: Der zweite Faktor ist freiwillig; die Administration kann ihn zur Pflicht machen."""

    def setUp(self):
        cache.clear()
        self.admin = benutzer("admin", Rolle.ADMIN)
        self.user = User(username="frei", first_name="Frieda", last_name="Frei", rolle=Rolle.MITARBEITER)
        self.einmal = self.user.neues_einmal_kennwort()
        self.user.save()
        self.c = APIClient()

    def anmelden(self, kennwort, client=None):
        return (client or self.c).post("/api/auth/anmelden/", {"benutzername": "frei", "kennwort": kennwort},
                                       format="json")

    def test_erstanmeldung_ohne_zweiten_faktor(self):
        self.assertEqual(Anmelderegeln.aktuell().zweiter_faktor, "freiwillig")  # Standard
        self.assertEqual(self.anmelden(self.einmal).json()["schritt"], "kennwort_aendern")
        r = self.c.post("/api/auth/kennwort/", {"neu": "Ein-langes-neues-Passwort-42"}, format="json")
        self.assertEqual(r.json()["schritt"], "fertig", r.content)
        ich = r.json()["benutzer"]
        self.assertEqual((ich["zweiter_faktor"], ich["zweiter_faktor_pflicht"]), (False, False))
        self.assertEqual(self.c.get("/api/patienten/").status_code, 200)
        # nächste Anmeldung: das Kennwort genügt; im Audit-Log steht, dass ohne zweiten Faktor angemeldet wurde
        self.c.post("/api/auth/abmelden/")
        self.assertEqual(self.anmelden("falsch").status_code, 401)
        r = self.anmelden("Ein-langes-neues-Passwort-42")
        self.assertEqual(r.json()["schritt"], "fertig")
        self.user.refresh_from_db()
        self.assertEqual(self.user.fehlversuche, 0)  # der Fehlversuch davor ist mit der Anmeldung erledigt
        eintrag = SystemEreignis.objects.filter(art="anmeldung", benutzer=self.user).order_by("-id").first()
        self.assertEqual(eintrag.details["schritt"], "ohne_2fa")
        log = client_fuer(self.admin).get("/api/protokoll/?gruppe=anmeldung").json()["results"]
        self.assertIn("Anmeldung mit Passwort (ohne zweiten Faktor)", [e["beschreibung"] for e in log])
        # „Mein Konto“ zeigt den Stand
        s = self.c.get("/api/auth/sicherheit/").json()
        self.assertEqual((s["authenticator_aktiv"], s["zweiter_faktor_pflicht"]), (False, False))

    def test_freiwillig_einrichten_und_wieder_ausschalten(self):
        self.anmelden(self.einmal)
        self.c.post("/api/auth/kennwort/", {"neu": "Ein-langes-neues-Passwort-42"}, format="json")
        # freiwillig einrichten (Mein Konto)
        self.assertEqual(self.c.post("/api/auth/2fa/einrichten/").status_code, 200)
        geraet = TOTPDevice.objects.get(user=self.user)
        code = f"{totp(geraet.bin_key, geraet.step, geraet.t0, geraet.digits):06d}"
        r = self.c.post("/api/auth/2fa/bestaetigen/", {"code": code}, format="json")
        self.assertEqual(r.json()["schritt"], "fertig", r.content)
        notfall = r.json()["notfallcodes"]
        self.assertTrue(self.c.get("/api/auth/ich/").json()["zweiter_faktor"])
        # wer ihn eingerichtet hat, braucht ihn bei jeder Anmeldung
        neu = APIClient()
        self.assertEqual(self.anmelden("Ein-langes-neues-Passwort-42", neu).json()["schritt"], "2fa")
        self.assertEqual(neu.get("/api/patienten/").status_code, 403)
        self.assertEqual(neu.post("/api/auth/2fa/", {"code": notfall[0]}, format="json").json()["schritt"], "fertig")
        # ausschalten: Kennwort und Code; falsche Eingaben werden abgewiesen
        r = neu.post("/api/auth/2fa/ausschalten/", {"kennwort": "falsch", "code": notfall[1]}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["kennwort"]))
        r = neu.post("/api/auth/2fa/ausschalten/", {"kennwort": "Ein-langes-neues-Passwort-42", "code": "000000x"},
                     format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["code"]))
        # django-otp bremst nach einem falschen Code kurz (1 s, 2 s, 4 s …) – hier nicht abwarten
        from django_otp.plugins.otp_static.models import StaticDevice
        for modell in (TOTPDevice, StaticDevice):
            modell.objects.filter(user=self.user).update(throttling_failure_timestamp=None, throttling_failure_count=0)
        r = neu.post("/api/auth/2fa/ausschalten/", {"kennwort": "Ein-langes-neues-Passwort-42", "code": notfall[1]},
                     format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()["zweiter_faktor"])
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertEqual(neu.get("/api/patienten/").status_code, 200)  # die Sitzung gilt weiter
        self.assertEqual(self.anmelden("Ein-langes-neues-Passwort-42", APIClient()).json()["schritt"], "fertig")
        texte = [e["beschreibung"] for e in client_fuer(self.admin).get("/api/protokoll/?gruppe=benutzer").json()["results"]]
        self.assertIn("Zweiten Faktor (Authenticator-App) selbst ausgeschaltet", texte)
        # ohne zweiten Faktor gibt es nichts auszuschalten
        self.assertEqual(neu.post("/api/auth/2fa/ausschalten/", {"kennwort": "x", "code": "1"}, format="json").status_code, 400)

    def test_pflicht_durch_die_administration(self):
        self.anmelden(self.einmal)
        self.c.post("/api/auth/kennwort/", {"neu": "Ein-langes-neues-Passwort-42"}, format="json")
        self.assertEqual(self.c.get("/api/patienten/").status_code, 200)
        a = client_fuer(self.admin)
        stand = a.get("/api/benutzer/anmeldung/").json()
        self.assertEqual(stand["zweiter_faktor"], "freiwillig")
        self.assertEqual([x["wert"] for x in stand["auswahl"]], ["freiwillig", "admins", "alle"])
        self.assertIn(self.user.id, [k["id"] for k in stand["ohne_zweiten_faktor"]])
        self.assertEqual(a.put("/api/benutzer/anmeldung/", {"zweiter_faktor": "immer"}, format="json").status_code, 400)
        # Pflicht nur für Admins: die Mitarbeiterin arbeitet weiter
        self.assertEqual(a.put("/api/benutzer/anmeldung/", {"zweiter_faktor": "admins"}, format="json").status_code, 200)
        self.assertEqual(self.c.get("/api/patienten/").status_code, 200)
        self.assertFalse(self.c.get("/api/auth/ich/").json()["zweiter_faktor_pflicht"])
        # Pflicht für alle: Mit der nächsten Anfrage muss sie den Authenticator einrichten
        r = a.put("/api/benutzer/anmeldung/", {"zweiter_faktor": "alle"}, format="json")
        self.assertEqual(r.json()["zweiter_faktor"], "alle")
        self.assertEqual(self.c.get("/api/patienten/").status_code, 403)
        self.assertEqual(self.c.get("/api/auth/status/").json()["schritt"], "2fa_einrichten")
        self.assertEqual(self.c.post("/api/auth/2fa/einrichten/").status_code, 200)
        geraet = TOTPDevice.objects.get(user=self.user)
        code = f"{totp(geraet.bin_key, geraet.step, geraet.t0, geraet.digits):06d}"
        r = self.c.post("/api/auth/2fa/bestaetigen/", {"code": code}, format="json")
        self.assertEqual(r.json()["schritt"], "fertig", r.content)
        self.assertEqual(self.c.get("/api/patienten/").status_code, 200)
        # bei Pflicht lässt er sich nicht ausschalten
        r = self.c.post("/api/auth/2fa/ausschalten/", {"kennwort": "Ein-langes-neues-Passwort-42",
                                                       "code": r.json()["notfallcodes"][0]}, format="json")
        self.assertEqual(r.status_code, 403)
        texte = [e["beschreibung"] for e in a.get("/api/protokoll/?gruppe=benutzer").json()["results"]]
        self.assertIn("Zweiter Faktor bei der Anmeldung: Pflicht für alle (vorher Pflicht für Admins)", texte)
        self.assertEqual(Anmelderegeln.history.count(), 3)  # angelegt, admins, alle
        # nur mit dem Recht „Benutzer verwalten“
        self.assertEqual(self.c.get("/api/benutzer/anmeldung/").status_code, 403)

    def test_konten_kachel_meldet_fehlenden_faktor_nur_bei_pflicht(self):
        self.anmelden(self.einmal)
        self.c.post("/api/auth/kennwort/", {"neu": "Ein-langes-neues-Passwort-42"}, format="json")
        a = client_fuer(self.admin)
        self.assertNotIn(self.user.id, [k["id"] for k in a.get("/api/benutzer/konten/").json()])
        Anmelderegeln.objects.update_or_create(pk=1, defaults={"zweiter_faktor": "alle"})
        zeile = next(k for k in a.get("/api/benutzer/konten/").json() if k["id"] == self.user.id)
        self.assertEqual(zeile["probleme"], ["ohne_2fa"])


class OhneLoginUndTestbenutzer(TestCase):
    """Fehlerliste 02.10.2026, 6.1, 6.2, 6.4: „ohne Login“ setzen und zurück, Rolle „Keine Berechtigung“,
    Testbenutzer an- und abschalten."""

    def setUp(self):
        cache.clear()
        self.admin = benutzer("admin", Rolle.ADMIN)
        self.a = client_fuer(self.admin)
        self.user = benutzer("ehemalig", Rolle.MITARBEITER)

    def test_ohne_login_setzen_und_wieder_einbinden(self):
        codes = mit_zweitem_faktor(self.user)
        c = echte_anmeldung(self.user, codes[0])
        self.assertEqual(c.get("/api/patienten/").status_code, 200)
        r = self.a.post(f"/api/benutzer/{self.user.id}/ohne-login/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["nur_historisch"], r.json()["rolle"], r.json()["is_active"], r.json()["zweiter_faktor"]),
                         (True, "keine", False, False))
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())
        # Anmeldung beendet, keine neue möglich
        self.assertEqual(c.get("/api/patienten/").status_code, 403)
        r = APIClient().post("/api/auth/anmelden/", {"benutzername": "ehemalig", "kennwort": KENNWORT}, format="json")
        self.assertEqual(r.status_code, 401)
        # ohne Login: keine Rolle außer „Keine Berechtigung“, kein Einmal-Kennwort, nicht doppelt, nicht das eigene Konto
        self.assertEqual(self.a.patch(f"/api/benutzer/{self.user.id}/", {"rolle": "mediziner"}, format="json").status_code, 400)
        self.assertEqual(self.a.patch(f"/api/benutzer/{self.user.id}/", {"funktion": "früher Pflege"}, format="json").status_code, 200)
        self.assertEqual(self.a.post(f"/api/benutzer/{self.user.id}/einmal-kennwort/").status_code, 400)
        self.assertEqual(self.a.post(f"/api/benutzer/{self.user.id}/ohne-login/").status_code, 400)
        self.assertEqual(self.a.post(f"/api/benutzer/{self.admin.id}/ohne-login/").status_code, 400)
        # wieder einbinden: Rolle und Einmal-Kennwort wie beim Anlegen
        self.assertEqual(self.a.post(f"/api/benutzer/{self.user.id}/login-geben/", {"rolle": "chef"}, format="json").status_code, 400)
        r = self.a.post(f"/api/benutzer/{self.user.id}/login-geben/", {"rolle": "mitarbeiter"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["nur_historisch"], r.json()["rolle"], r.json()["is_active"]), (False, "mitarbeiter", True))
        neu = APIClient()
        r2 = neu.post("/api/auth/anmelden/", {"benutzername": "ehemalig", "kennwort": r.json()["einmal_kennwort"]}, format="json")
        self.assertEqual(r2.json()["schritt"], "kennwort_aendern", r2.content)
        self.assertEqual(self.a.post(f"/api/benutzer/{self.user.id}/login-geben/", {"rolle": "mitarbeiter"}, format="json").status_code, 400)
        texte = [e["beschreibung"] for e in self.a.get("/api/protokoll/?gruppe=benutzer").json()["results"]]
        self.assertIn("Benutzer ehemalig auf „ohne Login“ gesetzt (keine Anmeldung, keine Rechte)", texte)
        self.assertIn("Benutzer ehemalig erhält wieder einen Login (Mitarbeiter), Einmal-Passwort erzeugt", texte)

    def test_ohne_login_anlegen(self):
        r = self.a.post("/api/benutzer/", {"username": "frueher", "first_name": "Frida", "last_name": "Früher",
                                           "rolle": "mediziner", "ohne_login": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotIn("einmal_kennwort", r.json())
        self.assertEqual((r.json()["nur_historisch"], r.json()["rolle"], r.json()["is_active"]), (True, "keine", False))

    def test_rolle_keine_berechtigung(self):
        """Auch ein Konto mit Login kann „Keine Berechtigung“ haben: anmelden ja, sonst nichts."""
        r = self.a.patch(f"/api/benutzer/{self.user.id}/", {"rolle": "keine"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        c = client_fuer(self.user)
        ich = c.get("/api/auth/ich/").json()
        self.assertEqual((ich["rolle"], ich["rechte"]), ("keine", []))
        for pfad in ("patienten/", "startseite/", "versorger/", "aerzte/", "auswahlwerte/", "einstellungen/",
                     "kalender/", "infusionsplaene/", "benutzer/", "protokoll/", "backup/", "system/uebersicht/"):
            with self.subTest(pfad=pfad):
                self.assertEqual(c.get(f"/api/{pfad}").status_code, 403)
        self.assertEqual(c.get("/api/hilfe/").status_code, 200)
        # Betrachter lesen die gemeinsamen Listen weiterhin
        self.assertEqual(client_fuer(benutzer("b", Rolle.BETRACHTER)).get("/api/versorger/").status_code, 200)

    def test_testbenutzer_schalter(self):
        from patienten.models import Patient

        echt = Patient.objects.create(nachname="Echt", vorname="E", geburtsdatum="1970-01-01")
        test = Patient.objects.create(nachname="Test", vorname="T", geburtsdatum="1970-01-01", ist_test=True)
        c = client_fuer(self.user)
        self.assertEqual({p["id"] for p in c.get("/api/patienten/").json()["results"]}, {echt.id, test.id})
        r = self.a.patch(f"/api/benutzer/{self.user.id}/", {"ist_test": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        c = client_fuer(self.user)
        self.assertEqual({p["id"] for p in c.get("/api/patienten/").json()["results"]}, {test.id})
        self.assertTrue(c.get("/api/auth/ich/").json()["ist_test"])
        eintrag = self.a.get("/api/protokoll/?gruppe=benutzer").json()["results"][0]
        self.assertEqual(eintrag["beschreibung"], "Benutzer ehemalig geändert: ist_test")
        # wieder ausschalten
        self.assertEqual(self.a.patch(f"/api/benutzer/{self.user.id}/", {"ist_test": False}, format="json").status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(len(client_fuer(self.user).get("/api/patienten/").json()["results"]), 2)
        # nicht für Admins (auch nicht das eigene Konto) und nicht zusammen mit der Rolle Admin
        zweiter = benutzer("zweiter", Rolle.ADMIN)
        self.assertEqual(self.a.patch(f"/api/benutzer/{zweiter.id}/", {"ist_test": True}, format="json").status_code, 400)
        self.assertEqual(self.a.patch(f"/api/benutzer/{self.admin.id}/", {"ist_test": True}, format="json").status_code, 400)
        self.a.patch(f"/api/benutzer/{self.user.id}/", {"ist_test": True}, format="json")
        r = self.a.patch(f"/api/benutzer/{self.user.id}/", {"rolle": "admin"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("ist_test", r.json())


class KartenGroessen(TestCase):
    """Fehlerliste 02.10.2026, Punkt 2 und 4.1: Größe der Karten je Seite und Person (PATCH /api/auth/ich/)."""

    def setUp(self):
        self.user = benutzer("karten", Rolle.MITARBEITER)
        self.c = client_fuer(self.user)

    def setze(self, bereiche):
        return self.c.patch("/api/auth/ich/", {"bereiche": bereiche}, format="json")

    def test_speichern_und_zuruecksetzen(self):
        self.assertEqual(self.c.get("/api/auth/ich/").json()["bereiche"], {})
        r = self.setze({"akte_uebersicht": {"gewicht": {"breite": 3, "hoehe": 2}, "termine": {"breite": 1, "hoehe": 0}}})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["bereiche"]["akte_uebersicht"]["gewicht"], {"breite": 3, "hoehe": 2})
        # eine weitere Seite und eine weitere Karte kommen dazu, Bestehendes bleibt
        r = self.setze({"system": {"verlauf": {"breite": 2, "hoehe": 1}}, "akte_uebersicht": {"plan": {"breite": 2, "hoehe": 0}}})
        stand = r.json()["bereiche"]
        self.assertEqual(sorted(stand), ["akte_uebersicht", "system"])
        self.assertEqual(sorted(stand["akte_uebersicht"]), ["gewicht", "plan", "termine"])
        # gilt je Person
        andere = benutzer("andere", Rolle.MITARBEITER)
        self.assertEqual(client_fuer(andere).get("/api/auth/ich/").json()["bereiche"], {})
        # null setzt eine Karte bzw. die ganze Seite auf den Standard zurück
        stand = self.setze({"akte_uebersicht": {"gewicht": None}}).json()["bereiche"]
        self.assertEqual(sorted(stand["akte_uebersicht"]), ["plan", "termine"])
        stand = self.setze({"akte_uebersicht": None}).json()["bereiche"]
        self.assertEqual(sorted(stand), ["system"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.bereiche, {"system": {"verlauf": {"breite": 2, "hoehe": 1}}})

    def test_wird_geprueft(self):
        for bereiche in ({"startseite": {"x": {"breite": 1, "hoehe": 1}}}, {"akte_uebersicht": {"unbekannt": {"breite": 1, "hoehe": 1}}},
                         {"akte_uebersicht": {"gewicht": {"breite": 6, "hoehe": 1}}}, {"akte_uebersicht": {"gewicht": {"breite": 1, "hoehe": 5}}},
                         {"akte_uebersicht": {"gewicht": {"breite": True, "hoehe": 1}}}, {"akte_uebersicht": {"gewicht": {"breite": 1}}},
                         {"akte_uebersicht": {"gewicht": "gross"}}, {"akte_uebersicht": []}, []):
            with self.subTest(bereiche=bereiche):
                r = self.setze(bereiche)
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn("bereiche", r.json())
        self.user.refresh_from_db()
        self.assertEqual(self.user.bereiche, {})


class TestdatenAusblenden(TestCase):
    """Festlegung 03.10.2026: „Testdaten sehen“ je Gruppe einstellbar – ohne das Recht gibt es Testpatienten und
    Testbenutzer nicht; Testbenutzer lassen sich ausblenden (gesperrt, aus allen Listen, nicht gelöscht)."""

    @classmethod
    def setUpTestData(cls):
        from patienten.models import Patient

        cls.admin = benutzer("admin", Rolle.ADMIN)
        cls.mitarbeiter = benutzer("mitarbeiter", Rolle.MITARBEITER)
        cls.tester = benutzer("tester", Rolle.MITARBEITER, ist_test=True)
        cls.echt = Patient.objects.create(nachname="Echt", vorname="E", geburtsdatum="1970-01-01")
        cls.test = Patient.objects.create(nachname="Probe", vorname="P", geburtsdatum="1970-01-01", ist_test=True)

    def ids(self, user, pfad="/api/patienten/"):
        return {x["id"] for x in client_fuer(user).get(pfad).json()["results"]}

    def test_recht_testdaten_sehen(self):
        self.assertEqual(self.ids(self.mitarbeiter), {self.echt.id, self.test.id})  # Standard wie bisher
        Gruppenrecht.objects.create(rolle=Rolle.MITARBEITER, recht="testdaten_sehen", erlaubt=False)
        self.assertEqual(self.ids(self.mitarbeiter), {self.echt.id})
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.get(f"/api/patienten/{self.test.id}/").status_code, 404)
        # kein Testpatient anlegbar (verschwände sofort)
        r = c.post("/api/patienten/", {"nachname": "Neu", "vorname": "N", "geburtsdatum": "1980-01-01",
                                       "testpatient": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertFalse(r.json()["ist_test"])
        # Testbenutzer sehen ihre Testpatienten immer
        self.assertEqual(self.ids(self.tester), {self.test.id})
        # Admin: fest (legt nur Testpatienten an)
        client_fuer(self.admin).put("/api/rechte/", {"matrix": {"admin": {"testdaten_sehen": False}}}, format="json")
        self.assertIn(self.test.id, self.ids(self.admin))
        # Testbenutzer erscheinen ohne das Recht auch nicht in Listen (z. B. Benutzerverwaltung mit Vertretungsrecht)
        Gruppenrecht.objects.create(rolle=Rolle.MITARBEITER, recht="benutzer_verwalten", erlaubt=True)
        namen = {b["username"] for b in client_fuer(self.mitarbeiter).get("/api/benutzer/").json()["results"]}
        self.assertNotIn("tester", namen)
        self.assertIn("admin", namen)

    def test_testbenutzer_ausblenden_und_einblenden(self):
        c = client_fuer(self.admin)
        self.assertEqual(c.post(f"/api/benutzer/{self.mitarbeiter.id}/ausblenden/").status_code, 400)
        r = c.post(f"/api/benutzer/{self.tester.id}/ausblenden/")
        self.assertEqual(r.status_code, 200, r.content)
        self.tester.refresh_from_db()
        self.assertFalse(self.tester.is_active)
        self.assertIsNotNone(self.tester.ausgeblendet_am)
        namen = {b["username"] for b in c.get("/api/benutzer/").json()["results"]}
        self.assertNotIn("tester", namen)
        namen = {b["username"] for b in c.get("/api/benutzer/?ausgeblendete=1").json()["results"]}
        self.assertIn("tester", namen)
        self.assertNotIn("tester", {k["benutzername"] for k in c.get("/api/benutzer/konten/").json()})
        self.assertEqual(c.post(f"/api/benutzer/{self.tester.id}/entsperren/").status_code, 400)
        self.assertTrue(SystemEreignis.objects.filter(art=SystemEreignis.Art.BENUTZER_GESPERRT).exists())
        r = c.post(f"/api/benutzer/{self.tester.id}/einblenden/")
        self.assertEqual(r.status_code, 200, r.content)
        self.tester.refresh_from_db()
        self.assertTrue(self.tester.is_active)
        self.assertIsNone(self.tester.ausgeblendet_am)
        # alle auf einmal
        benutzer("tester2", Rolle.BETRACHTER, ist_test=True)
        self.assertEqual(c.post("/api/benutzer/testbenutzer-ausblenden/").json(), {"ausgeblendet": 2})
        self.assertFalse(User.objects.filter(ist_test=True, ausgeblendet_am__isnull=True).exists())


class MitarbeiterErweitert(TestCase):
    """Festlegung 03.10.2026 (U22): Rolle „Mitarbeiter (erweitert)“ – Standard wie Mitarbeiter und zusätzlich
    Infusionspläne anlegen; eigene Spalte in der Rechtetabelle, je Recht umstellbar, auch als Testbenutzer."""

    def test_standard_und_umstellbar(self):
        from accounts.rechte import STANDARD, matrix

        admin = benutzer("admin", Rolle.ADMIN)
        plus = benutzer("plus", Rolle.MITARBEITER_PLUS)
        self.assertEqual(STANDARD[Rolle.MITARBEITER_PLUS] - STANDARD[Rolle.MITARBEITER], {"plaene_anlegen"})
        self.assertTrue(plus.hat_recht("plaene_anlegen"))
        self.assertFalse(plus.hat_recht("plaene_freigeben"))
        c = client_fuer(admin)
        d = c.get("/api/rechte/").json()
        self.assertIn({"code": "mitarbeiter_plus", "name": "Mitarbeiter (erweitert)"}, d["rollen"])
        r = c.put("/api/rechte/", {"matrix": {"mitarbeiter_plus": {"plaene_freigeben": True}}}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(matrix()["mitarbeiter_plus"]["plaene_freigeben"])
        self.assertFalse(matrix()["mitarbeiter"]["plaene_freigeben"])
        # als Testbenutzer möglich
        r = c.patch(f"/api/benutzer/{plus.id}/", {"ist_test": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
