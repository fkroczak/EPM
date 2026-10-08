"""Startseite und Oberfläche (S01–S17): Kennzahlen, Wochenstreifen, Wiedereinbestellung, Meine Akten, Kacheln im Raster,
Spaltenteiler, Admin-Kacheln – gegen die echte PostgreSQL-Datenbank."""
import importlib
from datetime import timedelta
from decimal import Decimal

from django.apps import apps as django_apps
from django.utils import timezone
from django_otp.plugins.otp_static.models import StaticToken

from accounts.models import Rolle
from audit.models import SystemEreignis, protokolliere
from epm.pruefhilfen import Grundlage, benutzer, client_fuer, mit_zweitem_faktor
from infusionen.models import Infusionsplan
from stammdaten.models import Einstellungen

from .models import Gewichtsmessung, Kontakt, Merkeintrag, Patient, Termin


class Kontaktstufen(Grundlage):
    def test_migration_alter_wert_wird_bald_faellig(self):
        """Datenmigration 0009: der bisherige eine Grenzwert wird „bald fällig“, „überfällig“ liegt 2 Monate später
        (mindestens 6); Grund in der Historie (höchstens 100 Zeichen)."""
        migration = importlib.import_module("stammdaten.migrations.0009_kontakt_zwei_stufen")
        self.assertLessEqual(len(migration.GRUND), 100)
        Einstellungen.aktuell()
        for bisher, erwartet in ((4, (4, 6)), (8, (8, 10)), (3, (3, 6))):
            Einstellungen.objects.filter(pk=1).update(kontakt_bald_monate=1, kontakt_ueberfaellig_monate=bisher)
            migration.umstellen(django_apps, None)
            e = Einstellungen.objects.get(pk=1)
            self.assertEqual((e.kontakt_bald_monate, e.kontakt_ueberfaellig_monate), erwartet)
            self.assertEqual(e.history.order_by("-history_id").first().history_change_reason, migration.GRUND)

    def test_bald_muss_vor_ueberfaellig_liegen(self):
        c = client_fuer(self.mitarbeiter)  # Vorlagen pflegen
        r = c.patch("/api/einstellungen/", {"kontakt_bald_monate": 6}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("kontakt_ueberfaellig_monate", r.json())
        r = c.patch("/api/einstellungen/", {"kontakt_bald_monate": 0}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        r = c.patch("/api/einstellungen/", {"kontakt_bald_monate": 5, "kontakt_ueberfaellig_monate": 9}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        e = Einstellungen.aktuell()
        self.assertEqual((e.kontakt_bald_monate, e.kontakt_ueberfaellig_monate), (5, 9))
        eintrag = SystemEreignis.objects.filter(art=SystemEreignis.Art.STAMMDATEN, objekt="Einstellungen").first()
        self.assertEqual(sorted(eintrag.details["felder"]), ["kontakt_bald_monate", "kontakt_ueberfaellig_monate"])


    def test_wiedervorlage_tage_standard_14_und_einstellbar(self):
        """Wunsch 08.10.2026: Wiedervorlage beim Kontakt standardmäßig in 14 Tagen, einstellbar (1–365)."""
        self.assertEqual(Einstellungen.aktuell().wiedervorlage_tage, 14)
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.get("/api/einstellungen/").json()["wiedervorlage_tage"], 14)
        for falsch in (0, 400):
            r = c.patch("/api/einstellungen/", {"wiedervorlage_tage": falsch}, format="json")
            self.assertEqual(r.status_code, 400, r.content)
            self.assertIn("wiedervorlage_tage", r.json())
        r = c.patch("/api/einstellungen/", {"wiedervorlage_tage": 21}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Einstellungen.aktuell().wiedervorlage_tage, 21)

class Startseite(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        heute = timezone.localdate()
        jetzt = timezone.now()
        cls.heute = heute
        # überfällig ohne Termin, bald fällig ohne Termin, bald fällig mit geplantem Termin, aktuell
        cls.alt = Patient.objects.create(nachname="Alt", vorname="Anton", geburtsdatum="1950-01-01")
        Kontakt.objects.create(patient=cls.alt, text="<p>alt</p>", zeitpunkt=jetzt - timedelta(days=240))
        cls.bald = Patient.objects.create(nachname="Bald", vorname="Berta", geburtsdatum="1951-01-01")
        Kontakt.objects.create(patient=cls.bald, text="<p>bald</p>", zeitpunkt=jetzt - timedelta(days=150))
        cls.geplant = Patient.objects.create(nachname="Geplant", vorname="Gerd", geburtsdatum="1952-01-01")
        Kontakt.objects.create(patient=cls.geplant, text="<p>geplant</p>", zeitpunkt=jetzt - timedelta(days=150))
        Termin.objects.create(patient=cls.geplant, art=Termin.Art.PRAXISTERMIN, faellig_am=heute + timedelta(days=2),
                              titel="Kontrolle")
        Kontakt.objects.create(patient=cls.patient, text="<p>heute</p>")
        Termin.objects.create(patient=cls.patient, art=Termin.Art.RUECKRUF, faellig_am=heute, titel="Rückruf")
        Termin.objects.create(patient=cls.patient, art=Termin.Art.WIEDERVORLAGE, faellig_am=heute - timedelta(days=3),
                              titel="vergessen")
        Termin.objects.create(patient=cls.patient, art=Termin.Art.SONSTIGES, faellig_am=heute + timedelta(days=7),
                              titel="am achten Tag")
        # Gewichtsverlust mit Verlauf (ein Wert älter als 6 Monate zählt nicht zum Mini-Verlauf)
        for tage, kg in ((400, "75.0"), (150, "72.0"), (92, "70.0"), (0, "64.0")):
            Gewichtsmessung.objects.create(patient=cls.bald, gewicht_kg=Decimal(kg),
                                           gemessen_am=heute - timedelta(days=tage))
        cls.test = Patient.objects.create(nachname="Probe", vorname="Tom", geburtsdatum="1970-01-01", ist_test=True)
        # Testpatient mit überfälligem und anstehendem Termin: in den Kacheln sichtbar, in den Kennzahlen nicht
        Termin.objects.create(patient=cls.test, art=Termin.Art.RUECKRUF, faellig_am=heute - timedelta(days=1), titel="Test alt")
        Termin.objects.create(patient=cls.test, art=Termin.Art.PRAXISTERMIN, faellig_am=heute + timedelta(days=1),
                              titel="Test neu")

    def test_kennzahlen_und_wochenstreifen(self):
        d = client_fuer(self.mitarbeiter).get("/api/startseite/").json()
        z = d["zahlen"]
        self.assertEqual(z["in_betreuung"], 4)  # ohne Testpatient
        self.assertEqual(z["mit_offenem_termin"], 2)
        # ohne Testpatient (F13), die Kacheln zeigen ihn
        self.assertEqual((z["termine_7_tage"], z["praxistermine_7_tage"], z["termine_ueberfaellig"]), (2, 1, 1))
        self.assertEqual(len(d["termine"]["ueberfaellig"]), 2)
        # heute und die 6 folgenden Tage – der Termin am achten Tag zählt nicht mit
        self.assertEqual({t["titel"] for t in d["termine"]["naechste_7_tage"]}, {"Rückruf", "Kontrolle", "Test neu"})
        woche = d["woche"]
        self.assertEqual([w["datum"] for w in woche], [(self.heute + timedelta(days=i)).isoformat() for i in range(7)])
        self.assertEqual((woche[0]["anzahl"], woche[1]["anzahl"], woche[2]["anzahl"], woche[2]["praxistermine"]), (1, 1, 1, 1))
        # Testzugang: nur Testpatienten, die zählen dort auch in den Kennzahlen
        z = client_fuer(benutzer("tester", Rolle.MITARBEITER, ist_test=True)).get("/api/startseite/").json()["zahlen"]
        self.assertEqual((z["in_betreuung"], z["termine_7_tage"], z["termine_ueberfaellig"], z["kontakt_ueberfaellig"]),
                         (1, 1, 1, 0))
        self.assertTrue(all("feiertag" in w for w in woche))

    def test_feiertage_im_wochenstreifen(self):
        from .api import _woche
        from datetime import date

        tage = _woche(Termin.objects.none(), date(2026, 10, 1))
        self.assertEqual(tage[2]["feiertag"], "Tag der Deutschen Einheit")
        self.assertIsNone(tage[0]["feiertag"])

    def test_wiedereinbestellung_ohne_geplanten_termin(self):
        d = client_fuer(self.mitarbeiter).get("/api/startseite/").json()
        w = d["wiedereinbestellung"]
        self.assertEqual([x["patient"] for x in w["ueberfaellig"]], [self.alt.id])  # Testpatient hat einen Termin
        self.assertEqual([x["patient"] for x in w["bald"]], [self.bald.id])  # „Geplant“ hat einen Termin
        self.assertEqual((w["bald_monate"], w["ueberfaellig_monate"]), (4, 6))
        self.assertEqual((d["zahlen"]["kontakt_bald"], d["zahlen"]["kontakt_ueberfaellig"]), (1, 1))
        # ohne Kontakt und ohne Termin: Testpatient steht in der Kachel zuerst, zählt aber nicht in den Kennzahlen
        Termin.objects.filter(patient=self.test).update(erledigt_am=timezone.now())
        d = client_fuer(self.mitarbeiter).get("/api/startseite/").json()
        w = d["wiedereinbestellung"]
        self.assertEqual([x["patient"] for x in w["ueberfaellig"]], [self.test.id, self.alt.id])  # noch nie Kontakt: zuerst
        self.assertEqual((w["anzahl_ueberfaellig"], d["zahlen"]["kontakt_ueberfaellig"]), (2, 1))
        ids = {p["id"] for p in client_fuer(self.mitarbeiter).get(
            "/api/patienten/?pruefen=wiedereinbestellung&test=ohne").json()["results"]}
        self.assertEqual(ids, {self.alt.id, self.bald.id})

    def test_gewicht_mit_verlauf_und_plaene_gezaehlt(self):
        Infusionsplan.neuer_entwurf(self.bald, self.mediziner)
        d = client_fuer(self.mitarbeiter).get("/api/startseite/").json()
        w = next(x for x in d["gewichtswarnungen"] if x["patient"] == self.bald.id)
        self.assertEqual([float(v["kg"]) for v in w["verlauf"]], [72.0, 70.0, 64.0])
        self.assertEqual((d["infusionsplaene"]["anzahl_entwuerfe"], d["infusionsplaene"]["anzahl_aelter"]), (1, 0))

    def test_zuletzt_eingetragen_von_mir(self):
        c = client_fuer(self.mitarbeiter)
        self.neuer_kontakt(client=c, patient=self.alt)
        self.neuer_kontakt(client=client_fuer(self.mediziner), patient=self.bald)
        d = c.get("/api/startseite/").json()
        self.assertEqual({z["person_id"] for z in d["zuletzt_von_mir"]}, {self.mitarbeiter.id})
        self.assertIn(self.mediziner.id, {z["person_id"] for z in d["zuletzt_eingetragen"]})
        # erledigte Termine erscheinen als eigener Eintrag
        t = Termin.objects.get(titel="Rückruf")
        self.assertEqual(c.post(f"/api/termine/{t.id}/erledigt/").status_code, 200)
        d = c.get("/api/startseite/").json()
        self.assertIn(("termin", "Termin erledigt"), {(z["bereich"], z["bezeichnung"]) for z in d["zuletzt_von_mir"]})

    def test_notfallcodes_hinweis(self):
        mit_zweitem_faktor(self.mitarbeiter, anzahl_codes=10)
        d = client_fuer(self.mitarbeiter).get("/api/startseite/").json()["notfallcodes"]
        self.assertEqual((d["uebrig"], d["gesamt"], d["eingerichtet"], d["warnen_ab"]), (10, 10, True, 3))
        StaticToken.objects.filter(device__user=self.mitarbeiter).exclude(
            id__in=StaticToken.objects.filter(device__user=self.mitarbeiter).values("id")[:2]).delete()
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/startseite/").json()["notfallcodes"]["uebrig"], 2)


class MeineAkten(Grundlage):
    def test_merken_und_zuletzt_geoeffnet(self):
        c = client_fuer(self.betrachter)  # Lesezeichen gehen mit „Akten lesen“
        r = c.post("/api/meine-akten/merken/", {"patient": self.patient.id}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual([x["patient"] for x in r.json()["merkliste"]], [self.patient.id])
        self.assertTrue(c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]["gemerkt"])
        # nur für die Person selbst
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/meine-akten/").json()["merkliste"], [])
        self.assertFalse(client_fuer(self.mitarbeiter).get(f"/api/patienten/{self.patient.id}/").json()["kopf"]["gemerkt"])
        self.assertEqual(c.delete(f"/api/meine-akten/merken/{self.patient.id}/").json()["merkliste"], [])
        # zuletzt geöffnet: neueste zuerst, höchstens 20
        weitere = [Patient.objects.create(nachname=f"Nr{i}", vorname="X", geburtsdatum="1960-01-01") for i in range(21)]
        for p in [self.patient, *weitere]:
            self.assertEqual(c.post("/api/meine-akten/geoeffnet/", {"patient": p.id}, format="json").status_code, 204)
        zuletzt = c.get("/api/meine-akten/").json()["zuletzt"]
        self.assertEqual(len(zuletzt), 20)
        self.assertEqual(zuletzt[0]["patient"], weitere[-1].id)
        self.assertEqual(Merkeintrag.objects.filter(benutzer=self.betrachter, art="geoeffnet").count(), 20)

    def test_nur_akten_im_eigenen_bereich(self):
        tester = benutzer("tester", Rolle.MITARBEITER, ist_test=True)
        r = client_fuer(tester).post("/api/meine-akten/merken/", {"patient": self.patient.id}, format="json")
        self.assertEqual(r.status_code, 400)
        r = client_fuer(tester).post("/api/meine-akten/geoeffnet/", {"patient": "x"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_faellt_mit_der_akte_weg(self):
        from .testdaten import testdaten_zuruecksetzen

        testdaten_zuruecksetzen()
        test = Patient.objects.filter(ist_test=True).first()
        Merkeintrag.objects.create(benutzer=self.mitarbeiter, patient=test, art="merkliste")
        testdaten_zuruecksetzen()
        self.assertFalse(Merkeintrag.objects.filter(patient_id=test.id).exists())


class KachelnUndTeiler(Grundlage):
    def test_standard_je_rolle(self):
        ich = client_fuer(self.mitarbeiter).get("/api/auth/ich/").json()
        karten = {k["id"]: k for k in ich["startseite"]["karten"]}
        self.assertEqual(list(karten)[:3], ["termine", "wieder", "meine"])
        self.assertEqual((karten["termine"]["breite"], karten["termine"]["hoehe"]), (2, 2))
        self.assertTrue(karten["wieder"]["sichtbar"])
        self.assertFalse(karten["sicherung"]["sichtbar"])
        admin = {k["id"]: k for k in client_fuer(self.admin).get("/api/auth/ich/").json()["startseite"]["karten"]}
        self.assertTrue(admin["sicherung"]["sichtbar"])
        self.assertFalse(admin["termine"]["sichtbar"])

    def test_groesse_und_reihenfolge_gespeichert(self):
        c = client_fuer(self.mitarbeiter)
        r = c.patch("/api/auth/ich/", {"startseite": {"karten": [
            {"id": "gewicht", "sichtbar": True, "breite": 2, "hoehe": 1},
            {"id": "termine", "sichtbar": False, "breite": 1, "hoehe": 2},
            {"id": "unbekannt", "sichtbar": True}]}}, format="json")
        self.assertEqual(r.status_code, 400)  # unbekannte Kachel
        r = c.patch("/api/auth/ich/", {"startseite": {"karten": [
            {"id": "gewicht", "sichtbar": True, "breite": 2, "hoehe": 1},
            {"id": "termine", "sichtbar": False, "breite": 1, "hoehe": 2}]}}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.mitarbeiter.refresh_from_db()
        karten = self.mitarbeiter.startseite["karten"]
        self.assertEqual(karten[:2], [{"id": "gewicht", "sichtbar": True, "breite": 2, "hoehe": 1},
                                      {"id": "termine", "sichtbar": False, "breite": 1, "hoehe": 2}])
        self.assertEqual(len(karten), 15)  # fehlende hinten mit Standard
        self.assertEqual(c.patch("/api/auth/ich/", {"startseite": {"karten": [{"id": "gewicht", "breite": 3}]}},
                                 format="json").status_code, 400)
        # Hinweis zu den Notfall-Codes ausgeblendet – Kacheln bleiben
        c.patch("/api/auth/ich/", {"startseite": {"notfallhinweis_bei": 2}}, format="json")
        self.mitarbeiter.refresh_from_db()
        self.assertEqual((self.mitarbeiter.startseite["notfallhinweis_bei"], self.mitarbeiter.startseite["karten"][0]["id"]),
                         (2, "gewicht"))
        # Standard
        c.patch("/api/auth/ich/", {"startseite": {"karten": []}}, format="json")
        self.mitarbeiter.refresh_from_db()
        self.assertEqual(self.mitarbeiter.startseite["karten"][0]["id"], "termine")

    def test_spaltenteiler(self):
        c = client_fuer(self.mitarbeiter)
        r = c.patch("/api/auth/ich/", {"aufteilung": {"akte_uebersicht@fhd": [0.6667], "plan_editor@qhd": [0.3333, 0.6667]}},
                    format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["aufteilung"], {"akte_uebersicht@fhd": [0.6667], "plan_editor@qhd": [0.3333, 0.6667]})
        for falsch in ({"akte@fhd": [0.5]}, {"akte_uebersicht@4k": [0.5]}, {"akte_uebersicht@hd": [0.95]},
                       {"plan_editor@qhd": [0.6, 0.5]}, {"akte_uebersicht@hd": ["x"]}, {"akte_uebersicht@hd": [0.5, 0.55]}):
            self.assertEqual(c.patch("/api/auth/ich/", {"aufteilung": falsch}, format="json").status_code, 400, falsch)
        r = c.patch("/api/auth/ich/", {"aufteilung": {"akte_uebersicht@fhd": None}}, format="json")
        self.assertEqual(r.json()["aufteilung"], {"plan_editor@qhd": [0.3333, 0.6667]})


class AdminKacheln(Grundlage):
    def test_konten_ohne_geheimnisse(self):
        gesperrt = benutzer("gesperrt", Rolle.MITARBEITER)
        gesperrt.sperren("5 Fehlversuche bei der Anmeldung")
        gesperrt.save()
        neu = benutzer("neu", Rolle.MITARBEITER)
        neu.neues_einmal_kennwort()
        neu.save()
        knapp = benutzer("knapp", Rolle.MEDIZINER)
        mit_zweitem_faktor(knapp, anzahl_codes=2)
        gut = benutzer("gut", Rolle.MEDIZINER)
        mit_zweitem_faktor(gut, anzahl_codes=10)
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/benutzer/konten/").status_code, 403)
        r = client_fuer(self.admin).get("/api/benutzer/konten/")
        self.assertEqual(r.status_code, 200)
        zeilen = {z["benutzername"]: z for z in r.json()}
        self.assertEqual(zeilen["gesperrt"]["probleme"], ["gesperrt"])
        self.assertEqual(zeilen["neu"]["probleme"], ["einmal_kennwort"])
        self.assertEqual((zeilen["knapp"]["probleme"], zeilen["knapp"]["notfallcodes_uebrig"]), (["notfallcodes"], 2))
        self.assertNotIn("gut", zeilen)
        # zweiter Faktor freiwillig (Festlegung 02.10.2026): ohne ihn ist ein Konto nur bei Pflicht auffällig
        self.assertNotIn("mediziner", zeilen)
        from accounts.models import Anmelderegeln

        Anmelderegeln.objects.update_or_create(pk=1, defaults={"zweiter_faktor": "alle"})
        zeilen = {z["benutzername"]: z for z in client_fuer(self.admin).get("/api/benutzer/konten/").json()}
        self.assertEqual(zeilen["mediziner"]["probleme"], ["ohne_2fa"])
        self.assertNotIn("password", r.content.decode())

    def test_zugriffe_sieben_tage(self):
        protokolliere(SystemEreignis.Art.ANMELDUNG, benutzer=self.admin)
        protokolliere(SystemEreignis.Art.ANMELDUNG_FEHLGESCHLAGEN, benutzername="wer")
        protokolliere(SystemEreignis.Art.EXPORT, benutzer=self.admin, was="Audit-Log")
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/protokoll/zusammenfassung/").status_code, 403)
        r = client_fuer(self.admin).get("/api/protokoll/zusammenfassung/?tage=7").json()
        zahlen = {z["schluessel"]: z["anzahl"] for z in r["zeilen"]}
        self.assertEqual((zahlen["fehlversuche"], zahlen["exporte"], zahlen["wiederherstellungen"]), (1, 1, 0))
        self.assertGreaterEqual(zahlen["anmeldungen"], 1)
        self.assertEqual(r["tage"], 7)

    def test_testumgebung(self):
        from .testdaten import testdaten_zuruecksetzen

        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/testdaten/").status_code, 403)
        leer = client_fuer(self.admin).get("/api/testdaten/").json()
        self.assertIsNone(leer["zuletzt_am"])
        ergebnis = testdaten_zuruecksetzen()
        protokolliere(SystemEreignis.Art.TESTDATEN, benutzer=self.admin, **ergebnis)
        d = client_fuer(self.admin).get("/api/testdaten/").json()
        self.assertEqual(d["in_betreuung"] + d["abgeschlossen"], Patient.objects.filter(ist_test=True).count())
        self.assertIsNotNone(d["zuletzt_am"])
        self.assertEqual(d["zuletzt_von"], self.admin.anzeigename)


class Hilfe(Grundlage):
    def test_abschnitte_nach_rechten(self):
        def ids(user):
            d = client_fuer(user).get("/api/hilfe/").json()
            return {a["id"] for g in d["gruppen"] for a in g["abschnitte"]}

        betrachter, admin = ids(self.betrachter), ids(self.admin)
        self.assertIn("kontakt_erfassen", ids(self.mitarbeiter))
        self.assertNotIn("kontakt_erfassen", betrachter)  # ohne „Einträge erfassen“
        self.assertIn("patientenliste", betrachter)
        self.assertNotIn("benutzer", betrachter)
        self.assertNotIn("benutzer", ids(self.mediziner))
        self.assertTrue({"benutzer", "system", "backup", "admin_start"} <= admin)
        # der Mediziner bekommt die Systemverwaltung als Vertretung → Abschnitt erscheint
        from accounts.models import Gruppenrecht

        Gruppenrecht.objects.create(rolle=Rolle.MEDIZINER, recht="system_verwalten", erlaubt=True)
        self.assertIn("system", ids(self.mediziner))
        self.assertEqual(client_fuer(self.betrachter).get("/api/hilfe/").json()["darf_ergaenzen"], False)

    def test_ergaenzung_mit_historie_und_audit(self):
        url = "/api/hilfe/kontakt_erfassen/ergaenzung/"
        self.assertEqual(client_fuer(self.betrachter).put(url, {"text": "<p>x</p>"}, format="json").status_code, 403)
        c = client_fuer(self.mitarbeiter)  # „Vorlagen pflegen“
        r = c.put(url, {"text": "<p>Durchwahl Medi-Home <script>alert(1)</script>0251 12345-0</p>"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn("script", r.json()["ergaenzung"]["text"])
        c.put(url, {"text": "<p>Erst Versorger anrufen.</p>"}, format="json")
        d = client_fuer(self.mediziner).get("/api/hilfe/").json()
        abschnitt = next(a for g in d["gruppen"] for a in g["abschnitte"] if a["id"] == "kontakt_erfassen")
        self.assertEqual(abschnitt["ergaenzung"]["text"], "<p>Erst Versorger anrufen.</p>")
        self.assertEqual(abschnitt["ergaenzung"]["versionen"], 2)
        self.assertEqual(abschnitt["ergaenzung"]["geaendert_von"], self.mitarbeiter.anzeigename)
        versionen = c.get(url + "versionen/").json()
        self.assertEqual([v["version"] for v in versionen], [2, 1])
        self.assertIn("Medi-Home", versionen[1]["text"])
        # leeren = entfernen; die Historie bleibt
        r = c.put(url, {"text": "<p></p>"}, format="json")
        self.assertEqual(r.json()["ergaenzung"]["text"], "")
        self.assertEqual(len(c.get(url + "versionen/").json()), 3)
        aktionen = list(SystemEreignis.objects.filter(art=SystemEreignis.Art.VORLAGE, objekt="Hilfe › Kontakt erfassen")
                        .order_by("id").values_list("details__aktion", flat=True))
        self.assertEqual(aktionen, ["Ergänzung angelegt", "Ergänzung geändert", "Ergänzung entfernt"])
        self.assertEqual(c.put("/api/hilfe/gibt_es_nicht/ergaenzung/", {"text": "x"}, format="json").status_code, 404)

    def test_jeder_abschnitt_vollstaendig(self):
        from hilfe.inhalt import ABSCHNITTE, GRUPPEN
        from accounts.rechte import CODES

        gruppen = {g for g, _ in GRUPPEN}
        ids = [a["id"] for a in ABSCHNITTE]
        self.assertEqual(len(ids), len(set(ids)))
        for a in ABSCHNITTE:
            self.assertIn(a["gruppe"], gruppen, a["id"])
            self.assertTrue(set(a["rechte"]) <= set(CODES), a["id"])
            self.assertTrue(a["html"].strip().startswith("<"), a["id"])
            self.assertLessEqual(len(a["id"]), 60)
