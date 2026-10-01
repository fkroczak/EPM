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
        kontakt = {f["patient"]: f for f in d["faelligkeiten"] if f["art"] == "kontakt"}
        self.assertTrue(kontakt[self.lange.id]["ueberfaellig"])
        self.assertEqual(kontakt[self.lange.id]["faellig_am"],
                         (timezone.localdate(timezone.now() - timedelta(days=150)) + timedelta(days=120)).isoformat())
        self.assertNotIn(self.patient.id, kontakt)  # Kontakt heute: erst in 4 Monaten fällig
        self.assertEqual(d["grenzen"]["kontakt_monate"], 4)
        self.assertTrue(d["feiertage"] is not None)
        self.assertEqual(self.monat(client_fuer(self.betrachter), faelligkeiten=0)["faelligkeiten"], [])

    def test_testzugang_nur_testpatienten(self):
        d = self.monat(client_fuer(benutzer("tester", Rolle.MEDIZINER, ist_test=True)))
        self.assertEqual({t["patient"] for t in d["termine"]}, {self.test.id})
        self.assertEqual(d["termine_ueberfaellig"], [])
        self.assertTrue(all(f["patient"] == self.test.id for f in d["faelligkeiten"]))

    def test_abgeschlossene_akten_ohne_faelligkeit(self):
        Patient.objects.filter(pk=self.lange.pk).update(abgeschlossen_am=timezone.now())
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
