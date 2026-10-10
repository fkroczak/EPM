"""Automatisierungen für die Pflege (10.10.2026): Tagesliste „Heute zu tun“ (F184), Terminbestätigung vorbereiten
(F185), fehlende Angaben melden (F186) – gegen die echte PostgreSQL-Datenbank."""
from datetime import timedelta

from django.utils import timezone

from epm.pruefhilfen import Grundlage, benutzer, client_fuer
from accounts.models import Rolle
from infusionen.models import Infusionsplan
from stammdaten.models import Arzt, Auswahlwert, Einstellungen

from .luecken import luecken, offene_luecken
from .models import Bezugsperson, Diagnose, Gewichtsmessung, Hinweisruhe, Patient, PatientArzt, Termin


def vollstaendig(**felder) -> Patient:
    """Eine Akte ohne Lücken: Telefon, Hausarzt, aktuelles Gewicht, Diagnose."""
    p = Patient.objects.create(nachname=felder.pop("nachname", "Voll"), vorname="Vera", geburtsdatum="1960-01-01",
                               telefon="0251 1234", **felder)
    arzt = Arzt.objects.create(name="Dr. Haus")
    PatientArzt.objects.create(patient=p, arzt=arzt, rolle=PatientArzt.Rolle.HAUSARZT)
    Gewichtsmessung.objects.create(patient=p, gewicht_kg=60, gemessen_am=timezone.localdate() - timedelta(days=10))
    Diagnose.objects.create(patient=p, bezeichnung="Kurzdarmsyndrom", icd_code="K91.2")
    return p


class FehlendeAngaben(Grundlage):
    """F186: je Regel ein Test; abgeschlossene Akten und Testpatienten bleiben außen vor."""

    def setUp(self):
        self.voll = vollstaendig()

    def arten(self, p):
        return luecken([p.id]).get(p.id, [])

    def test_vollstaendige_akte_hat_keine_luecken(self):
        self.assertEqual(self.arten(self.voll), [])

    def test_leere_akte_meldet_alles_ausser_termin(self):
        self.assertEqual(self.arten(self.patient), ["hausarzt", "telefon", "gewicht_fehlt", "diagnose"])

    def test_hausarzt(self):
        PatientArzt.objects.filter(patient=self.voll).update(aktiv=False)
        self.assertIn("hausarzt", self.arten(self.voll))
        # alter Freitext „Hausarzt“ zählt auch
        Patient.objects.filter(pk=self.voll.pk).update(hausarzt="Dr. Alt, Münster")
        self.assertNotIn("hausarzt", self.arten(self.voll))
        # jeder zugeordnete Arzt (auch Facharzt) genügt
        Patient.objects.filter(pk=self.voll.pk).update(hausarzt="")
        PatientArzt.objects.create(patient=self.voll, arzt=Arzt.objects.create(name="Dr. Fach"),
                                   rolle=PatientArzt.Rolle.FACHARZT)
        self.assertNotIn("hausarzt", self.arten(self.voll))

    def test_telefon(self):
        Patient.objects.filter(pk=self.voll.pk).update(telefon="")
        self.assertIn("telefon", self.arten(self.voll))
        Patient.objects.filter(pk=self.voll.pk).update(telefon2="0171 99")
        self.assertNotIn("telefon", self.arten(self.voll))
        # Kontaktperson mit Mobilnummer genügt ebenfalls
        Patient.objects.filter(pk=self.voll.pk).update(telefon2="")
        b = Bezugsperson.objects.create(patient=self.voll, name="Tochter", mobil="0172 1")
        self.assertNotIn("telefon", self.arten(self.voll))
        Bezugsperson.objects.filter(pk=b.pk).update(aktiv=False)
        self.assertIn("telefon", self.arten(self.voll))

    def test_gewicht_nach_einstellung(self):
        Gewichtsmessung.objects.filter(patient=self.voll).update(gemessen_am=timezone.localdate() - timedelta(days=120))
        self.assertIn("gewicht_fehlt", self.arten(self.voll))  # Standard: 3 Monate
        Einstellungen.objects.filter(pk=1).update(gewicht_fehlt_monate=6)
        self.assertNotIn("gewicht_fehlt", self.arten(self.voll))

    def test_diagnose(self):
        Diagnose.objects.filter(patient=self.voll).update(aktiv=False)
        self.assertIn("diagnose", self.arten(self.voll))
        Patient.objects.filter(pk=self.voll.pk).update(diagnose="<p></p>")  # leerer Rich-Text
        self.assertIn("diagnose", self.arten(self.voll))
        Patient.objects.filter(pk=self.voll.pk).update(diagnose="<p>Kurzdarm</p>")
        self.assertNotIn("diagnose", self.arten(self.voll))

    def test_praxistermin_ohne_ort(self):
        heute = timezone.localdate()
        t = Termin.objects.create(patient=self.voll, art=Termin.Art.PRAXISTERMIN, faellig_am=heute + timedelta(days=5),
                                  titel="Sprechstunde")
        self.assertEqual(self.arten(self.voll), ["termin_ort"])
        praxis = Auswahlwert.objects.get(liste=Auswahlwert.Liste.TERMINORT, wert="Praxis Dr. Holtmeier")
        Termin.objects.filter(pk=t.pk).update(ort=praxis)
        self.assertEqual(self.arten(self.voll), [])
        # vergangene, erledigte und Rückrufe zählen nicht
        Termin.objects.create(patient=self.voll, art=Termin.Art.PRAXISTERMIN, faellig_am=heute - timedelta(days=1), titel="x")
        Termin.objects.create(patient=self.voll, art=Termin.Art.RUECKRUF, faellig_am=heute + timedelta(days=1), titel="x")
        Termin.objects.create(patient=self.voll, art=Termin.Art.PRAXISTERMIN, faellig_am=heute + timedelta(days=2), titel="x",
                              erledigt_am=timezone.now())
        self.assertEqual(self.arten(self.voll), [])
        # ohne Terminort der Praxis gibt es kein Infoblatt mit Ort – dann auch keine Meldung (wie infoblatt.aufteilen)
        Termin.objects.filter(pk=t.pk).update(ort=None)
        Auswahlwert.objects.filter(pk=praxis.pk).update(wert="Praxis Dr. Anders")
        self.assertEqual(self.arten(self.voll), [])

    def test_abgeschlossen_und_testpatienten_ausgenommen(self):
        test = Patient.objects.create(nachname="Test", vorname="T", geburtsdatum="1970-01-01", ist_test=True)
        zu = Patient.objects.create(nachname="Zu", vorname="Z", geburtsdatum="1970-01-01",
                                    abgeschlossen_am=timezone.localdate(),
                                    abschluss_anlass=Patient.Abschlussanlass.THERAPIE_BEENDET)
        self.assertEqual(luecken([test.id, zu.id]), {})

    def test_als_hinweis_in_akte_und_liste_und_ausblendbar(self):
        c = client_fuer(self.mitarbeiter)
        kopf = c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        arten = [h["art"] for h in kopf["hinweise"]]
        for art in ("hausarzt", "telefon", "gewicht_fehlt", "diagnose"):
            self.assertIn(art, arten)
        self.assertIn({"art": "gewicht_fehlt", "text": "Kein Gewicht seit 3 Mon."}, kopf["hinweise"])
        r = c.get("/api/patienten/", {"pruefen": "ohne_telefon"})
        self.assertEqual(r.status_code, 200, r.content[:2000])
        liste = r.json()["results"]
        self.assertEqual([p["id"] for p in liste], [self.patient.id])
        self.assertIn("telefon", [h["art"] for h in liste[0]["kennzahlen"]["hinweise"]])
        # „ausblenden“ wie bei den anderen Hinweisen (F119)
        r = c.post(f"/api/patienten/{self.patient.id}/hinweis-ruhe/", {"art": "telefon", "monate": 3}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        kopf = c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertNotIn("telefon", [h["art"] for h in kopf["hinweise"]])
        self.assertIn("telefon", kopf["hinweise_stumm"])
        self.assertEqual(c.get("/api/patienten/", {"pruefen": "ohne_telefon"}).json()["results"], [])
        self.assertNotIn("telefon", offene_luecken([self.patient.id]).get(self.patient.id, []))
        self.assertEqual(Hinweisruhe.objects.get(patient=self.patient, art="telefon").get_art_display(), "Keine Telefonnummer")

    def test_filter_je_regel(self):
        c = client_fuer(self.mitarbeiter)
        for filter_ in ("ohne_hausarzt", "ohne_gewicht", "ohne_diagnose"):
            ids = [p["id"] for p in c.get("/api/patienten/", {"pruefen": filter_}).json()["results"]]
            self.assertIn(self.patient.id, ids, filter_)
            self.assertNotIn(self.voll.id, ids, filter_)


class Tagesliste(Grundlage):
    """F184: „Heute zu tun“ auf der Startseite."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        heute = timezone.localdate()
        cls.heute = heute
        cls.voll = vollstaendig(nachname="Termin", email="vera@example.org", geschlecht="w")
        cls.praxis = Auswahlwert.objects.get(liste=Auswahlwert.Liste.TERMINORT, wert="Praxis Dr. Holtmeier")
        cls.heute_termin = Termin.objects.create(patient=cls.voll, art=Termin.Art.PRAXISTERMIN, faellig_am=heute,
                                                 ort=cls.praxis, titel="Sprechstunde")
        cls.rueckruf = Termin.objects.create(patient=cls.voll, art=Termin.Art.RUECKRUF, faellig_am=heute - timedelta(days=2),
                                             titel="Rückruf Labor")
        cls.spaeter = Termin.objects.create(patient=cls.voll, art=Termin.Art.RUECKRUF, faellig_am=heute + timedelta(days=2),
                                            titel="später")
        cls.bald = Termin.objects.create(patient=cls.voll, art=Termin.Art.PRAXISTERMIN, faellig_am=heute + timedelta(days=3),
                                         ort=cls.praxis, titel="Kontrolle")
        cls.ohne_ort = Termin.objects.create(patient=cls.voll, art=Termin.Art.PRAXISTERMIN,
                                             faellig_am=heute + timedelta(days=9), titel="ohne Ort")
        # Testpatient und abgeschlossene Akte: tauchen nirgends auf
        cls.test = Patient.objects.create(nachname="Probe", vorname="P", geburtsdatum="1970-01-01", ist_test=True,
                                          email="t@example.org")
        Termin.objects.create(patient=cls.test, art=Termin.Art.PRAXISTERMIN, faellig_am=heute, titel="Test")
        Termin.objects.create(patient=cls.test, art=Termin.Art.RUECKRUF, faellig_am=heute, titel="Test")
        Termin.objects.create(patient=cls.test, art=Termin.Art.PRAXISTERMIN, faellig_am=heute + timedelta(days=4), titel="T")
        cls.zu = Patient.objects.create(nachname="Zu", vorname="Z", geburtsdatum="1970-01-01")
        Termin.objects.create(patient=cls.zu, art=Termin.Art.RUECKRUF, faellig_am=heute, titel="zu")
        Patient.objects.filter(pk=cls.zu.pk).update(abgeschlossen_am=heute,
                                                    abschluss_anlass=Patient.Abschlussanlass.THERAPIE_BEENDET)
        Infusionsplan.objects.create(patient=cls.voll, gueltig_ab=heute, status=Infusionsplan.Status.ENTWURF)
        Infusionsplan.objects.create(patient=cls.test, gueltig_ab=heute, status=Infusionsplan.Status.ENTWURF)

    def liste(self, user=None):
        r = client_fuer(user or self.mitarbeiter).get("/api/startseite/")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["tagesliste"]

    def test_inhalt_ohne_testpatienten_und_abgeschlossene(self):
        tl = self.liste()
        self.assertEqual([t["id"] for t in tl["termine_heute"]], [self.heute_termin.id])
        self.assertEqual([t["id"] for t in tl["rueckrufe"]], [self.rueckruf.id])
        self.assertEqual((tl["rueckrufe_anzahl"], tl["rueckrufe_ueberfaellig"]), (1, 1))
        self.assertEqual(tl["plaene_pruefen"], 1)
        # der Termin ohne Ort braucht auch eine Bestätigung (Patientin hat E-Mail)
        self.assertEqual([t["id"] for t in tl["bestaetigung_fehlt"]], [self.bald.id, self.ohne_ort.id])
        self.assertEqual([t["id"] for t in tl["ohne_ort"]], [self.ohne_ort.id])
        # „Echt“ aus der Grundlage: kein Telefon, kein Hausarzt, kein Gewicht, keine Diagnose
        self.assertEqual(tl["fehlende_angaben"], {"hausarzt": 1, "telefon": 1, "gewicht_fehlt": 1, "diagnose": 1,
                                                  "termin_ort": 1})
        self.assertEqual(tl["gewicht_fehlt_monate"], 3)
        self.assertGreaterEqual(tl["kontakt_ueberfaellig"], 1)

    def test_erledigtes_verschwindet(self):
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.post(f"/api/termine/{self.rueckruf.id}/erledigt/").status_code, 200)
        r = c.patch(f"/api/termine/{self.ohne_ort.id}/", {"ort": self.praxis.id}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        tl = self.liste()
        self.assertEqual(tl["rueckrufe"], [])
        self.assertEqual(tl["rueckrufe_anzahl"], 0)
        self.assertEqual(tl["ohne_ort"], [])
        self.assertEqual(tl["fehlende_angaben"]["termin_ort"], 0)

    def test_rechte(self):
        # nur lesen: keine Bestätigungen, keine Termine ohne Ort zum Bearbeiten, Rest wie gehabt
        tl = self.liste(self.betrachter)
        self.assertEqual(tl["bestaetigung_fehlt"], [])
        self.assertEqual(tl["ohne_ort"], [])
        self.assertEqual(len(tl["termine_heute"]), 1)
        # ohne Recht „Akten lesen“ gibt es die Startseitendaten gar nicht
        keine = benutzer("keine", Rolle.KEINE)
        self.assertEqual(client_fuer(keine).get("/api/startseite/").status_code, 403)

    def test_testzugang_sieht_nur_testpatienten(self):
        tester = benutzer("tester", Rolle.MITARBEITER, ist_test=True)
        tl = self.liste(tester)
        self.assertEqual([t["patient"] for t in tl["termine_heute"]], [self.test.id])
        self.assertEqual(tl["fehlende_angaben"]["telefon"], 0)  # Regeln gelten nicht für Testpatienten

    def test_bestaetigung_nur_mit_einstellung(self):
        Einstellungen.objects.filter(pk=1).update(terminbestaetigung_anbieten=False)
        self.assertEqual(self.liste()["bestaetigung_fehlt"], [])


class Terminbestaetigung(Grundlage):
    """F185: Angebot nach dem Speichern, Vermerk am Termin, verschoben = wieder offen."""

    def setUp(self):
        self.p = vollstaendig(nachname="Muster", email="m@example.org", geschlecht="w")
        self.c = client_fuer(self.mitarbeiter)
        self.praxis = Auswahlwert.objects.get(liste=Auswahlwert.Liste.TERMINORT, wert="Praxis Dr. Holtmeier")

    def neu(self, **extra):
        daten = {"patient": self.p.id, "art": "praxistermin", "faellig_am": str(timezone.localdate() + timedelta(days=7)),
                 "uhrzeit": "10:00", "ort": self.praxis.id, "titel": "Sprechstunde", **extra}
        r = self.c.post("/api/termine/", daten, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_angebot_nach_dem_speichern(self):
        t = self.neu()
        self.assertEqual(t["bestaetigung"], {"angebot": True, "email": True, "anrede": "Frau Muster"})
        self.assertIsNone(t["bestaetigung_am"])
        # Rückrufe haben keine Bestätigung
        self.assertIsNone(self.neu(art="rueckruf")["bestaetigung"])

    def test_kein_angebot_ohne_anschrift_und_email_oder_ausgeschaltet(self):
        Patient.objects.filter(pk=self.p.pk).update(email="")
        self.assertFalse(self.neu()["bestaetigung"]["angebot"])
        Patient.objects.filter(pk=self.p.pk).update(strasse="Weg 1", plz="48149", ort="Münster")
        t = self.neu()
        self.assertTrue(t["bestaetigung"]["angebot"])
        self.assertFalse(t["bestaetigung"]["email"])
        Einstellungen.objects.filter(pk=1).update(terminbestaetigung_anbieten=False)
        self.assertFalse(self.neu()["bestaetigung"]["angebot"])

    def schreiben(self, termin_id, **extra):
        return self.c.post(f"/api/patienten/{self.p.id}/schreiben/",
                           {"art": "terminbestaetigung", "termin": termin_id, **extra}, format="json")

    def test_vermerk_nach_pdf_oder_eml_nicht_nach_vorschau(self):
        t = self.neu()
        self.assertEqual(self.schreiben(t["id"], ausgabe="email").status_code, 200)  # nur Text für den Dialog
        self.assertEqual(self.schreiben(t["id"], ausgabe="pdf", vorschau=True).status_code, 200)  # „PDF ansehen“
        self.assertIsNone(Termin.objects.get(pk=t["id"]).bestaetigung_am)
        r = self.schreiben(t["id"], ausgabe="eml")
        self.assertEqual(r.status_code, 200)
        termin = Termin.objects.get(pk=t["id"])
        self.assertIsNotNone(termin.bestaetigung_am)
        self.assertEqual(termin.bestaetigung_von, self.mitarbeiter)
        d = self.c.get(f"/api/termine/{t['id']}/").json()
        self.assertIsNotNone(d["bestaetigung_am"])
        self.assertEqual(d["bestaetigung_von_name"], "M. Tester")
        # im Verlauf der Akte nachvollziehbar
        verlauf = self.c.get(f"/api/patienten/{self.p.id}/verlauf/", {"bereich": "termine"}).json()
        self.assertTrue(any(e.get("aktion") == "Terminbestätigung erstellt" for e in verlauf), verlauf[:3])

    def test_andere_schreiben_setzen_keinen_vermerk(self):
        t = self.neu()
        self.assertEqual(self.c.post(f"/api/patienten/{self.p.id}/schreiben/",
                                     {"art": "patientenaufnahme", "ausgabe": "pdf"}, format="json").status_code, 200)
        self.assertIsNone(Termin.objects.get(pk=t["id"]).bestaetigung_am)

    def test_verschieben_macht_bestaetigung_ungueltig(self):
        t = self.neu()
        self.assertEqual(self.schreiben(t["id"], ausgabe="pdf").status_code, 200)
        # Titel ändern: Bestätigung bleibt
        self.c.patch(f"/api/termine/{t['id']}/", {"titel": "Andere Bezeichnung"}, format="json")
        self.assertIsNotNone(Termin.objects.get(pk=t["id"]).bestaetigung_am)
        # Uhrzeit ändern: Bestätigung fehlt wieder
        r = self.c.patch(f"/api/termine/{t['id']}/", {"uhrzeit": "11:30"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()["bestaetigung_am"])
        self.assertTrue(r.json()["bestaetigung"]["angebot"])

    def test_admin_bei_echter_akte_ohne_vermerk(self):
        t = self.neu()
        r = client_fuer(self.admin).post(f"/api/patienten/{self.p.id}/schreiben/",
                                         {"art": "terminbestaetigung", "termin": t["id"], "ausgabe": "pdf"}, format="json")
        if r.status_code == 200:  # Admin darf das Schreiben erzeugen, schreibt aber nicht in echte Akten
            self.assertIsNone(Termin.objects.get(pk=t["id"]).bestaetigung_am)


class Einstellungsfelder(Grundlage):
    def test_standard_und_grenzen(self):
        c = client_fuer(self.mitarbeiter)
        d = c.get("/api/einstellungen/").json()
        self.assertEqual((d["gewicht_fehlt_monate"], d["terminbestaetigung_anbieten"]), (3, True))
        for falsch in (0, 200):
            r = c.patch("/api/einstellungen/", {"gewicht_fehlt_monate": falsch}, format="json")
            self.assertEqual(r.status_code, 400, r.content)
            self.assertIn("gewicht_fehlt_monate", r.json())
        r = c.patch("/api/einstellungen/", {"gewicht_fehlt_monate": 6, "terminbestaetigung_anbieten": False}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        e = Einstellungen.aktuell()
        self.assertEqual((e.gewicht_fehlt_monate, e.terminbestaetigung_anbieten), (6, False))
        # ohne „Vorlagen pflegen“ nicht änderbar
        r = client_fuer(self.betrachter).patch("/api/einstellungen/", {"gewicht_fehlt_monate": 2}, format="json")
        self.assertIn(r.status_code, (403,))
