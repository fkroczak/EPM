"""Globaler Kalender: Termine aller Patienten, überfällige Termine, Fälligkeiten, Feiertage (echte Datenbank)."""
from datetime import date, timedelta

from django.utils import timezone

from accounts.models import Rolle
from epm.pruefhilfen import Grundlage, benutzer, client_fuer

from .kalender import feiertage, ostersonntag
from .models import Kontakt, Patient, Termin


class Feiertage(Grundlage):
    def test_ostern_und_nrw(self):
        self.assertEqual(ostersonntag(2026), date(2026, 4, 5))
        self.assertEqual(ostersonntag(2027), date(2027, 3, 28))
        tage = dict(feiertage(2026))
        self.assertEqual(tage[date(2026, 4, 3)], "Karfreitag")
        self.assertEqual(tage[date(2026, 5, 14)], "Christi Himmelfahrt")
        self.assertEqual(tage[date(2026, 5, 25)], "Pfingstmontag")
        self.assertEqual(tage[date(2026, 6, 4)], "Fronleichnam")      # NRW
        self.assertEqual(tage[date(2026, 11, 1)], "Allerheiligen")    # NRW
        self.assertEqual(len(tage), 11)
        self.assertNotIn(date(2026, 10, 31), tage)                    # Reformationstag nicht in NRW


class Kalender(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        heute = timezone.localdate()
        cls.heute = heute
        jetzt = timezone.now()
        # Kontakt vor 5 Monaten → bei 4 Monaten Grenze seit etwa einem Monat fällig
        cls.lange = Patient.objects.create(nachname="Lange", vorname="Lea", geburtsdatum="1950-01-01")
        Kontakt.objects.create(patient=cls.lange, text="<p>alt</p>", zeitpunkt=jetzt - timedelta(days=150))
        # Kontakt vor 3 Monaten → in etwa einem Monat fällig
        cls.bald = Patient.objects.create(nachname="Bald", vorname="Ben", geburtsdatum="1960-01-01")
        Kontakt.objects.create(patient=cls.bald, text="<p>neu</p>", zeitpunkt=jetzt - timedelta(days=90))
        Kontakt.objects.create(patient=cls.patient, text="<p>heute</p>")
        cls.test = Patient.objects.create(nachname="Probe", vorname="Tom", geburtsdatum="1970-01-01", ist_test=True)
        Kontakt.objects.create(patient=cls.test, text="<p>heute</p>")
        cls.t_heute = Termin.objects.create(patient=cls.patient, art=Termin.Art.PRAXISTERMIN, faellig_am=heute,
                                            titel="Praxis")
        cls.t_alt = Termin.objects.create(patient=cls.lange, art=Termin.Art.RUECKRUF,
                                          faellig_am=heute - timedelta(days=40), titel="Rückruf vergessen")
        cls.t_erledigt = Termin.objects.create(patient=cls.bald, art=Termin.Art.WIEDERVORLAGE, faellig_am=heute,
                                               titel="erledigt", erledigt_am=jetzt)
        cls.t_test = Termin.objects.create(patient=cls.test, art=Termin.Art.SONSTIGES, faellig_am=heute, titel="Test")

    def monat(self, client, **extra):
        von = self.heute.replace(day=1)
        bis = von + timedelta(days=41)
        r = client.get("/api/kalender/", {"von": von.isoformat(), "bis": bis.isoformat(), **extra})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_termine_und_faelligkeiten(self):
        d = self.monat(client_fuer(self.betrachter))  # lesen dürfen alle mit „Akten lesen“
        ids = {t["id"] for t in d["termine"]}
        self.assertTrue({self.t_heute.id, self.t_erledigt.id, self.t_test.id} <= ids)
        self.assertIn(self.t_alt.id, {t["id"] for t in d["termine_ueberfaellig"]})
        self.assertNotIn(self.t_erledigt.id, {t["id"] for t in self.monat(client_fuer(self.betrachter),
                                                                          erledigte=0)["termine"]})
        # Kontakt fällig in zwei Stufen (S04): je Akte ein Eintrag „bald fällig“ (4 Monate) und „überfällig“ (6 Monate)
        r = client_fuer(self.betrachter).get("/api/kalender/", {"von": (self.heute - timedelta(days=200)).isoformat(),
                                                                "bis": (self.heute + timedelta(days=60)).isoformat()})
        weit = r.json()
        kontakt = {(f["patient"], f["stufe"]): f for f in weit["faelligkeiten"] if f["art"] == "kontakt"}
        seit = timezone.localdate(timezone.now() - timedelta(days=150))
        self.assertTrue(kontakt[(self.lange.id, "bald")]["ueberfaellig"])
        self.assertEqual(kontakt[(self.lange.id, "bald")]["faellig_am"], (seit + timedelta(days=120)).isoformat())
        self.assertIn("bald fällig", kontakt[(self.lange.id, "bald")]["text"])
        self.assertEqual(kontakt[(self.lange.id, "ueberfaellig")]["faellig_am"], (seit + timedelta(days=180)).isoformat())
        self.assertFalse(kontakt[(self.lange.id, "ueberfaellig")]["ueberfaellig"])  # erst in etwa einem Monat
        self.assertNotIn((self.patient.id, "bald"), kontakt)  # Kontakt heute: erst in 4 Monaten fällig
        self.assertEqual((weit["grenzen"]["kontakt_bald_monate"], weit["grenzen"]["kontakt_monate"]), (4, 6))
        self.assertTrue(d["feiertage"] is not None)
        self.assertEqual(self.monat(client_fuer(self.betrachter), faelligkeiten=0)["faelligkeiten"], [])

    def test_testzugang_nur_testpatienten(self):
        d = self.monat(client_fuer(benutzer("tester", Rolle.MEDIZINER, ist_test=True)))
        self.assertEqual({t["patient"] for t in d["termine"]}, {self.test.id})
        self.assertEqual(d["termine_ueberfaellig"], [])
        self.assertTrue(all(f["patient"] == self.test.id for f in d["faelligkeiten"]))

    def test_abgeschlossene_akten_ohne_faelligkeit(self):
        Patient.objects.filter(pk=self.lange.pk).update(abgeschlossen_am=timezone.now(),
                                                        abschluss_anlass=Patient.Abschlussanlass.THERAPIE_BEENDET)
        d = self.monat(client_fuer(self.mitarbeiter))
        self.assertNotIn(self.lange.id, {f["patient"] for f in d["faelligkeiten"]})
        self.assertNotIn(self.t_alt.id, {t["id"] for t in d["termine_ueberfaellig"]})

    def test_zeitraum_pruefen(self):
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.get("/api/kalender/").status_code, 400)
        self.assertEqual(c.get("/api/kalender/", {"von": "2026-10-10", "bis": "2026-10-01"}).status_code, 400)
        self.assertEqual(c.get("/api/kalender/", {"von": "2026-01-01", "bis": "2027-12-31"}).status_code, 400)
        d = c.get("/api/kalender/", {"von": "2026-12-01", "bis": "2026-12-31"}).json()
        self.assertEqual([f["name"] for f in d["feiertage"]], ["1. Weihnachtstag", "2. Weihnachtstag"])

    def test_termin_ausblenden(self):
        """F142 (Wunsch 08.10.2026): „×“ am Termin – 3/6/12 Monate oder „nicht mehr nötig“, zurückholbar."""
        c = client_fuer(self.mitarbeiter)
        pfad = f"/api/termine/{self.t_alt.id}/ausblenden/"
        # Betrachter darf nicht, ungültige Frist wird abgewiesen
        self.assertEqual(client_fuer(self.betrachter).post(pfad, {"monate": 3}, format="json").status_code, 403)
        r = c.post(pfad, {"monate": 4}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("monate", r.json())
        r = c.post(pfad, {"monate": 3, "grund": "Patientin meldet sich selbst"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        t = r.json()
        self.assertTrue(t["ausgeblendet"])
        self.assertFalse(t["ausgeblendet_dauerhaft"])
        self.assertEqual(t["ausblende_grund"], "Patientin meldet sich selbst")
        self.assertGreater(t["ausgeblendet_bis"], self.heute.isoformat())
        # weg aus Kalender (überfällig) und Startseite, in der Akte unter ``ausgeblendet=true``
        self.assertNotIn(self.t_alt.id, {x["id"] for x in self.monat(c)["termine_ueberfaellig"]})
        liste = c.get("/api/termine/", {"patient": self.lange.id, "ausgeblendet": "true"}).json()
        ids = {x["id"] for x in (liste["results"] if isinstance(liste, dict) else liste)}
        self.assertEqual(ids, {self.t_alt.id})
        liste = c.get("/api/termine/", {"patient": self.lange.id, "ausgeblendet": "false"}).json()
        self.assertEqual(liste["results"] if isinstance(liste, dict) else liste, [])
        # „nicht mehr nötig“, dann zurückholen
        self.assertTrue(c.post(pfad, {"dauerhaft": True}, format="json").json()["ausgeblendet_dauerhaft"])
        r = c.post(pfad, {"aufheben": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()["ausgeblendet"])
        self.assertIn(self.t_alt.id, {x["id"] for x in self.monat(c)["termine_ueberfaellig"]})
        self.assertEqual(c.post(pfad, {"aufheben": True}, format="json").status_code, 400)
        # jede Fassung steht in der Historie
        self.assertGreaterEqual(Termin.history.filter(id=self.t_alt.id).count(), 4)

    def test_faelligkeit_folgt_der_hinweisruhe(self):
        """F142: „×“ an „Kontakt fällig“ im Kalender schaltet den Hinweis der Akte stumm (F119) – die Fälligkeit verschwindet."""
        c = client_fuer(self.mitarbeiter)
        bereich = {"von": (self.heute - timedelta(days=200)).isoformat(), "bis": (self.heute + timedelta(days=60)).isoformat()}
        vorher = c.get("/api/kalender/", bereich).json()["faelligkeiten"]
        self.assertIn(self.lange.id, {f["patient"] for f in vorher if f["art"] == "kontakt"})
        r = c.post(f"/api/patienten/{self.lange.id}/hinweis-ruhe/", {"art": "kontakt", "monate": 3}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        nachher = c.get("/api/kalender/", bereich).json()["faelligkeiten"]
        self.assertNotIn(self.lange.id, {f["patient"] for f in nachher if f["art"] == "kontakt"})
