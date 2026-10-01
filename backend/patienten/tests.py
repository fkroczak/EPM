"""
Prüft die fachlichen Regeln der Patientenakte gegen die echte PostgreSQL-Datenbank.

Aufruf im Container:
    sudo docker compose run --rm backend python manage.py test
"""
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Rolle, User
from audit.models import SystemEreignis, protokolliere
from epm.pruefhilfen import TMP, Grundlage, benutzer, client_fuer
from infusionen.models import Infusionsplan
from stammdaten.models import Ansprechpartner, Arzt, Auswahlwert, Versorger

from .kennzahlen import woche
from .models import Bezugsperson, Dokument, Gewichtsmessung, Kontakt, Patient, PatientArzt, Termin
from .testdaten import testdaten_zuruecksetzen, testpatienten_anlegen


def wert(liste, text):
    return Auswahlwert.objects.get(liste=liste, wert=text)


class KontaktRegeln(Grundlage):
    def test_text_wird_bereinigt(self):
        k = self.neuer_kontakt()
        self.assertNotIn("script", k["text"])

    def test_kontakt_nicht_aenderbar(self):
        k = self.neuer_kontakt()
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.patch(f"/api/kontakte/{k['id']}/", {"text": "neu"}, format="json").status_code, 405)
        self.assertEqual(c.delete(f"/api/kontakte/{k['id']}/").status_code, 405)
        obj = Kontakt.objects.get(pk=k["id"])
        obj.text = "geändert"
        with self.assertRaises(PermissionError):
            obj.save()

    def test_trigger_verhindert_aenderung_in_der_datenbank(self):
        k = self.neuer_kontakt()
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("UPDATE patienten_kontakt SET text = 'x' WHERE id = %s", [k["id"]])

    def test_storno_genau_einmal(self):
        k = self.neuer_kontakt()
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.post(f"/api/kontakte/{k['id']}/storno/", {"grund": ""}, format="json").status_code, 400)
        r = c.post(f"/api/kontakte/{k['id']}/storno/", {"grund": "falscher Patient"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["storno_grund"], "falscher Patient")
        self.assertEqual(c.post(f"/api/kontakte/{k['id']}/storno/", {"grund": "nochmal"}, format="json").status_code, 400)

    def test_kontakt_mit_wiedervorlage(self):
        ort = wert(Auswahlwert.Liste.TERMINORT, "Praxis Dr. Holtmeier")
        faellig = timezone.localdate() + timedelta(days=7)
        k = self.neuer_kontakt(wiedervorlage={"art": "praxistermin", "ort": ort.id, "faellig_am": str(faellig),
                                              "uhrzeit": "10:30"})
        self.assertEqual(len(k["termine"]), 1)
        self.assertEqual(k["termine"][0]["ort"], "Praxis Dr. Holtmeier")
        termin = Termin.objects.get(kontakt_id=k["id"])
        self.assertEqual((termin.faellig_am, termin.uhrzeit, termin.art), (faellig, time(10, 30), "praxistermin"))
        self.assertEqual(termin.angelegt_von, self.mitarbeiter)
        self.assertEqual(termin.titel, "Praxistermin")

    def test_wiedervorlage_wird_geprueft(self):
        c = client_fuer(self.mitarbeiter)
        falscher_ort = wert(Auswahlwert.Liste.KATHETER, "Port")
        faelle = [
            {"faellig_am": str(timezone.localdate() - timedelta(days=1))},
            {"faellig_am": str(timezone.localdate()), "ort": falscher_ort.id},
            {"art": "unbekannt", "faellig_am": str(timezone.localdate())},
        ]
        for wv in faelle:
            with self.subTest(wv=wv):
                r = c.post("/api/kontakte/", {"patient": self.patient.id, "text": "<p>x</p>", "wiedervorlage": wv},
                           format="json")
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn("wiedervorlage", r.json())
        self.assertFalse(Kontakt.objects.filter(patient=self.patient).exists())  # nichts halb gespeichert


class Revisionssicherheit(Grundlage):
    def test_historie_ist_unveraenderlich(self):
        protokolliere(SystemEreignis.Art.EXPORT, benutzername="test")  # damit das Protokoll nicht leer ist
        self.patient.diagnose = "<p>neu</p>"
        self.patient.save()
        for sql in ("UPDATE patienten_historicalpatient SET nachname = 'x'",
                    "DELETE FROM patienten_historicalpatient",
                    "DELETE FROM audit_systemereignis"):
            with self.subTest(sql=sql), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(sql)

    def test_verlauf_nach_bereichen(self):
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"/api/patienten/{self.patient.id}/", {"therapie": "<p>Neue Therapie</p>", "ort": "Münster"},
                    format="json")
        self.assertEqual(r.status_code, 200, r.content)
        v = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=therapie").json()
        self.assertEqual(v[0]["bereich"], "therapie")
        self.assertEqual(v[0]["aktion"], "geändert")
        self.assertEqual(v[0]["person"], self.mitarbeiter.anzeigename)
        self.assertEqual([a["feld"] for a in v[0]["aenderungen"]], ["therapie"])
        v = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=stammdaten").json()
        self.assertIn("ort", [a["feld"] for a in v[0]["aenderungen"]])
        self.assertNotIn("therapie", [a["feld"] for a in v[0]["aenderungen"]])
        # Filter nach Person
        k = self.neuer_kontakt(client=client_fuer(self.mediziner))
        c.post(f"/api/kontakte/{k['id']}/storno/", {"grund": "doppelt"}, format="json")
        v = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=kontakte").json()
        self.assertEqual([e["aktion"] for e in v], ["storniert", "angelegt"])
        self.assertIn("Grund: doppelt", v[0]["beschreibung"])
        self.assertEqual(v[1]["beschreibung"], "Hallo")
        c.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "54.6", "gemessen_am": "2026-09-29"}, format="json")
        v = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=gewichte").json()
        self.assertEqual(v[0]["beschreibung"], "54,6 kg, gemessen am 29.09.2026")
        v = c.get(f"/api/patienten/{self.patient.id}/verlauf/?person={self.mediziner.id}").json()
        self.assertEqual({e["person_id"] for e in v}, {self.mediziner.id})

    def test_versionen_der_textfelder(self):
        c = client_fuer(self.mitarbeiter)
        for text in ("<p>Kurzdarm</p>", "<p>Kurzdarm, Colon in Kontinuität</p>"):
            self.assertEqual(c.patch(f"/api/patienten/{self.patient.id}/", {"diagnose": text},
                                     format="json").status_code, 200)
        r = c.get(f"/api/patienten/{self.patient.id}/versionen/?feld=diagnose").json()
        self.assertEqual(r["version"], 2)
        self.assertEqual([f["version"] for f in r["fassungen"]], [2, 1])
        self.assertIn("Kontinuität", r["fassungen"][0]["text"])
        self.assertEqual(r["fassungen"][0]["person"], self.mitarbeiter.anzeigename)
        kopf = c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual(kopf["versionen"]["diagnose"]["version"], 2)
        self.assertIsNone(kopf["versionen"]["empfehlung"])
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/versionen/?feld=nachname").status_code, 400)


class Akte(Grundlage):
    def test_abgeschlossene_akte_ist_gesperrt(self):
        c = client_fuer(self.mediziner)
        r = c.post(f"/api/patienten/{self.patient.id}/abschliessen/", {"anlass": "verstorben"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        r = c.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": "60.0"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(c.patch(f"/api/patienten/{self.patient.id}/", {"ort": "x"}, format="json").status_code, 409)
        # Wieder öffnen nur Admin, mit Grund
        self.assertEqual(c.post(f"/api/patienten/{self.patient.id}/wieder-oeffnen/", {"grund": "x"}, format="json").status_code, 403)
        a = client_fuer(self.admin)
        self.assertEqual(a.post(f"/api/patienten/{self.patient.id}/wieder-oeffnen/", {}, format="json").status_code, 400)
        self.assertEqual(a.post(f"/api/patienten/{self.patient.id}/wieder-oeffnen/", {"grund": "Irrtum"}, format="json").status_code, 200)

    def test_abschliessen_mit_recht(self):
        """Akten abschließen: Mitarbeiter, Mediziner, Admin (Admin nur bei Testpatienten); Betrachter nicht."""
        for wer in (self.betrachter, self.admin):
            with self.subTest(rolle=wer.rolle):
                r = client_fuer(wer).post(f"/api/patienten/{self.patient.id}/abschliessen/",
                                          {"anlass": "therapie_beendet"}, format="json")
                self.assertEqual(r.status_code, 403)
        c = client_fuer(self.mitarbeiter)
        url = f"/api/patienten/{self.patient.id}/abschliessen/"
        self.assertEqual(c.post(url, {"anlass": "x"}, format="json").status_code, 400)
        morgen = str(timezone.localdate() + timedelta(days=1))
        for datum in ("kein-datum", morgen):
            with self.subTest(datum=datum):
                r = c.post(url, {"anlass": "verstorben", "datum": datum}, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn("datum", r.json())
        r = c.post(f"/api/patienten/{self.patient.id}/abschliessen/", {"anlass": "therapie_beendet",
                                                                     "notiz": "HPE beendet"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["ist_abgeschlossen"])
        log = client_fuer(self.admin).get("/api/protokoll/?gruppe=abschluss").json()["results"]
        self.assertEqual(log[0]["beschreibung"],
                         f"Akte Echt, Anna (Nr. {self.patient.nummer:04d}) abgeschlossen, Anlass: Therapie beendet")
        self.assertEqual(log[0]["person"], self.mitarbeiter.anzeigename)
        r = c.post(f"/api/patienten/{self.patient.id}/abschliessen/", {"anlass": "verstorben"}, format="json")
        self.assertEqual(r.status_code, 409)  # bereits abgeschlossen

    def test_plausibilitaet_gewicht(self):
        c = client_fuer(self.mitarbeiter)
        for kg in ("0", "9999"):
            r = c.post("/api/gewichte/", {"patient": self.patient.id, "gewicht_kg": kg}, format="json")
            self.assertEqual(r.status_code, 400, kg)

    def test_gewichtswarnung(self):
        heute = timezone.localdate()
        for tage, kg in [(120, "70.0"), (95, "70.0"), (0, "65.0")]:
            Gewichtsmessung.objects.create(patient=self.patient, gewicht_kg=Decimal(kg),
                                           gemessen_am=heute - timedelta(days=tage))
        trend = self.patient.gewichtstrend()
        self.assertTrue(trend["warnung"])
        self.assertEqual(trend["prozent"], Decimal("-7.1"))

    def test_doppelte(self):
        c = client_fuer(self.mitarbeiter)
        r = c.get(f"/api/patienten/doppelte/?geburtsdatum={self.patient.geburtsdatum}&nachname=Echtmann")
        self.assertEqual([p["id"] for p in r.json()], [self.patient.id])

    def test_nummern(self):
        p = Patient.objects.create(nachname="B", vorname="C", geburtsdatum="1970-01-01")
        t = Patient.objects.create(nachname="T", vorname="T", geburtsdatum="1970-01-01", ist_test=True)
        self.assertEqual(p.nummer, self.patient.nummer + 1)
        self.assertEqual(t.nummer, 9001)
        r = client_fuer(self.mitarbeiter).get("/api/patienten/naechste-nummer/").json()
        self.assertEqual(r["nummer"], p.nummer + 1)

    def test_anlegen_mit_aufnahmegewicht(self):
        c = client_fuer(self.mitarbeiter)
        daten = {"nachname": "Neu", "vorname": "Nora", "geburtsdatum": "1980-02-02",
                 "ueberweisung_durch": "Uniklinik Münster", "aufnahme_gewicht_kg": "0"}
        self.assertEqual(c.post("/api/patienten/", daten, format="json").status_code, 400)
        self.assertFalse(Patient.objects.filter(nachname="Neu").exists())
        daten.update(aufnahme_gewicht_kg="58.4", aufnahme_quelle="ambulanz")
        r = c.post("/api/patienten/", daten, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        p = Patient.objects.get(pk=r.json()["id"])
        self.assertEqual(p.ueberweisung_durch, "Uniklinik Münster")
        self.assertEqual(p.angelegt_von, self.mitarbeiter)
        m = p.gewichte.get()
        self.assertEqual((m.gewicht_kg, m.quelle, m.gemessen_am, m.erfasst_von),
                         (Decimal("58.4"), "ambulanz", timezone.localdate(), self.mitarbeiter))
        # nur beim Anlegen
        r = c.patch(f"/api/patienten/{p.id}/", {"aufnahme_gewicht_kg": "60"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_dokument_upload_und_download(self):
        c = client_fuer(self.mitarbeiter)
        datei = SimpleUploadedFile("brief.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = c.post("/api/dokumente/", {"patient": self.patient.id, "titel": "Brief", "datei": datei}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.json()["sha256"]), 64)
        self.assertEqual(r.json()["mime"], "application/pdf")
        d = c.get(f"/api/dokumente/{r.json()['id']}/datei/")
        self.assertTrue(d["X-Accel-Redirect"].startswith("/_geschuetzt/dokumente/"))

    def test_dokumenttyp_am_inhalt(self):
        c = client_fuer(self.mitarbeiter)
        faelle = [
            ("bild.pdf", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20, 201, "image/png"),     # Endung egal, Inhalt zählt
            ("foto.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 20, 201, "image/jpeg"),
            ("alt.txt", "Brief mit Umlauten: Größe".encode("cp1252"), 201, "text/plain; charset=windows-1252"),
            ("programm.pdf", b"MZ\x90\x00\x03\x00\x00\x00", 400, None),            # ausführbare Datei
            ("leer.docx", b"PK\x03\x04\x14\x00\x06\x00", 400, None),               # Office-Datei nicht erlaubt
        ]
        for name, inhalt, code, mime in faelle:
            with self.subTest(name=name):
                datei = SimpleUploadedFile(name, inhalt, content_type="application/pdf")
                r = c.post("/api/dokumente/", {"patient": self.patient.id, "titel": name, "datei": datei},
                           format="multipart")
                self.assertEqual(r.status_code, code, r.content)
                if mime:
                    self.assertEqual(r.json()["mime"], mime)

    def test_altdokument_pruefen(self):
        alt = Dokument.objects.create(
            patient=self.patient, titel="Scan 2019", datum=date(2019, 5, 1), datei="1/alt.pdf",
            originalname="alt.pdf", mime="application/pdf", groesse=1, sha256="0" * 64,
            herkunft=Dokument.Herkunft.ALTSYSTEM, datum_quelle=Dokument.DatumQuelle.DATEIDATUM, typ_geprueft=False,
        )
        c = client_fuer(self.mitarbeiter)
        liste = c.get("/api/patienten/?pruefen=altdokumente").json()["results"]
        self.assertEqual([p["id"] for p in liste], [self.patient.id])
        self.assertEqual(c.get("/api/startseite/").json()["pruefen"]["altdokumente"], 1)
        falscher_typ = wert(Auswahlwert.Liste.KATHETER, "Port")
        self.assertEqual(c.post(f"/api/dokumente/{alt.id}/geprueft/", {"typ": falscher_typ.id},
                                format="json").status_code, 400)
        arztbrief = wert(Auswahlwert.Liste.DOKUMENTTYP, "Arztbrief")
        r = c.post(f"/api/dokumente/{alt.id}/geprueft/", {"typ": arztbrief.id, "datum": "2019-04-12"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["typ_name"], r.json()["datum"], r.json()["datum_quelle"], r.json()["typ_geprueft"]),
                         ("Arztbrief", "2019-04-12", "eingabe", True))
        self.assertEqual(c.get("/api/patienten/?pruefen=altdokumente").json()["results"], [])
        # typ_geprueft lässt sich nicht direkt setzen
        alt2 = Dokument.objects.create(patient=self.patient, titel="x", datei="1/x.pdf", originalname="x.pdf",
                                       mime="application/pdf", groesse=1, sha256="0" * 64, typ_geprueft=False)
        c.patch(f"/api/dokumente/{alt2.id}/", {"typ_geprueft": True}, format="json")
        alt2.refresh_from_db()
        self.assertFalse(alt2.typ_geprueft)

    def test_termin_mit_ort(self):
        c = client_fuer(self.mitarbeiter)
        ort = wert(Auswahlwert.Liste.TERMINORT, "Praxis Dr. Holtmeier")
        daten = {"patient": self.patient.id, "art": "praxistermin", "faellig_am": str(timezone.localdate()),
                 "uhrzeit": "09:15", "titel": "Kontrolle", "ort": ort.id}
        r = c.post("/api/termine/", daten, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["ort_name"], "Praxis Dr. Holtmeier")
        kopf = c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual(kopf["naechster_termin"]["ort"], "Praxis Dr. Holtmeier")
        daten["ort"] = wert(Auswahlwert.Liste.DOKUMENTTYP, "Labor").id
        self.assertEqual(c.post("/api/termine/", daten, format="json").status_code, 400)
        # erledigt → nicht mehr änderbar
        tid = r.json()["id"]
        self.assertEqual(c.post(f"/api/termine/{tid}/erledigt/").status_code, 200)
        self.assertEqual(c.patch(f"/api/termine/{tid}/", {"titel": "neu"}, format="json").status_code, 400)


class Patientenliste(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        heute = timezone.localdate()
        cls.versorger = Versorger.objects.create(name="Versorger A")
        cls.ap1 = Ansprechpartner.objects.create(versorger=cls.versorger, name="Frau Eins")
        # Gewichtsverlust: 70 → 64 kg in 3 Monaten
        cls.verlust = Patient.objects.create(nachname="Verlust", vorname="Vera", geburtsdatum="1960-01-01",
                                             versorger=cls.versorger, ansprechpartner=cls.ap1)
        for tage, kg in [(92, "70.0"), (0, "64.0")]:
            Gewichtsmessung.objects.create(patient=cls.verlust, gewicht_kg=Decimal(kg),
                                           gemessen_am=heute - timedelta(days=tage))
        Kontakt.objects.create(patient=cls.verlust, text="<p>Anruf</p>")
        # stabil, mit Termin in dieser Woche
        cls.stabil = Patient.objects.create(nachname="Stabil", vorname="Stefan", geburtsdatum="1971-07-07",
                                            versorger=cls.versorger, ansprechpartner=cls.ap1)
        for tage, kg in [(90, "80.0"), (0, "80.4")]:
            Gewichtsmessung.objects.create(patient=cls.stabil, gewicht_kg=Decimal(kg),
                                           gemessen_am=heute - timedelta(days=tage))
        Kontakt.objects.create(patient=cls.stabil, text="<p>Besuch</p>")
        montag, sonntag = woche(heute)
        Termin.objects.create(patient=cls.stabil, art=Termin.Art.RUECKRUF, faellig_am=sonntag, titel="Rückruf")
        # Testpatient: in der Liste mit Filter „test=ohne“ ausblendbar, zählt in keiner Statistik
        cls.testpat = Patient.objects.create(nachname="Test", vorname="T", geburtsdatum="1970-01-01", ist_test=True)

    def test_liste_mit_kennzahlen(self):
        r = client_fuer(self.mitarbeiter).get("/api/patienten/?status=in_betreuung&test=ohne").json()
        zeilen = {p["id"]: p for p in r["results"]}
        self.assertEqual(set(zeilen), {self.patient.id, self.verlust.id, self.stabil.id})
        v = zeilen[self.verlust.id]["kennzahlen"]
        self.assertEqual(Decimal(str(v["gewicht"]["kg"])), Decimal("64.0"))
        self.assertEqual((v["trend"]["richtung"], v["trend"]["warnung"]), ("down", True))
        self.assertEqual([h["art"] for h in v["hinweise"]], ["gewicht"])
        s = zeilen[self.stabil.id]["kennzahlen"]
        self.assertEqual(s["trend"]["richtung"], "flat")
        self.assertTrue(s["termin_woche"])
        self.assertEqual(s["hinweise"], [])
        ohne = zeilen[self.patient.id]["kennzahlen"]
        self.assertEqual({h["art"] for h in ohne["hinweise"]}, {"versorger", "kontakt"})
        self.assertIsNone(ohne["gewicht"])
        # Standard-Reihenfolge: letzter Kontakt, neueste zuerst; ohne Kontakt ans Ende
        self.assertEqual(r["results"][-1]["id"], self.patient.id)
        self.assertIsNotNone(zeilen[self.verlust.id]["alter"])

    def test_schnellfilter_und_zaehler(self):
        c = client_fuer(self.mitarbeiter)

        def ids(filter_):
            return {p["id"] for p in c.get(f"/api/patienten/?schnellfilter={filter_}&test=ohne").json()["results"]}

        self.assertEqual(ids("gewichtsverlust"), {self.verlust.id})
        self.assertEqual(ids("termin_woche"), {self.stabil.id})
        alle = {p["id"] for p in c.get("/api/patienten/?schnellfilter=hinweise").json()["results"]}
        self.assertIn(self.testpat.id, alle)  # ohne Filter „test=ohne“ sichtbar, aber nicht gezählt
        self.assertEqual(ids("hinweise"), {self.verlust.id, self.patient.id})
        z = c.get("/api/patienten/zaehler/").json()
        # Testpatienten zählen nicht mit
        self.assertEqual(z, {"in_betreuung": 3, "abgeschlossen": 0, "mit_hinweisen": 2, "gewichtsverlust": 1,
                             "termin_woche": 1})
        # nur die Administration sieht ihre Anzahl getrennt daneben
        test_offen = Patient.objects.filter(ist_test=True, abgeschlossen_am__isnull=True).count()
        self.assertGreaterEqual(test_offen, 1)
        za = client_fuer(self.admin).get("/api/patienten/zaehler/").json()
        self.assertEqual(za["in_betreuung"], 3)
        self.assertEqual(za["testpatienten"], {"in_betreuung": test_offen, "abgeschlossen": 0})

    def test_sortierung_ohne_kontakt_immer_am_ende(self):
        c = client_fuer(self.mitarbeiter)
        for ordnung in ("-letzter_kontakt", "letzter_kontakt"):
            ids = [p["id"] for p in c.get(f"/api/patienten/?test=ohne&ordering={ordnung}").json()["results"]]
            self.assertEqual(ids[-1], self.patient.id, ordnung)
            self.assertEqual(set(ids), {self.patient.id, self.verlust.id, self.stabil.id})
        Patient.objects.filter(pk=self.verlust.pk).update(abgeschlossen_am=timezone.localdate(),
                                                           abschluss_anlass="verstorben")
        r = c.get("/api/patienten/?status=abgeschlossen&ordering=-abgeschlossen_am").json()
        self.assertEqual([p["id"] for p in r["results"]], [self.verlust.id])
        # Versorger zählt nur Patienten in Betreuung (ohne Testpatienten), wie der Ansprechpartner
        v = c.get(f"/api/versorger/{self.versorger.id}/").json()
        self.assertEqual((v["patienten_anzahl"], v["ansprechpartner"][0]["patienten_anzahl"]), (1, 1))

    def test_filter_versorger_und_ansprechpartner(self):
        c = client_fuer(self.mitarbeiter)
        ap2 = Ansprechpartner.objects.create(versorger=self.versorger, name="Herr Zwei")
        Patient.objects.filter(pk=self.stabil.pk).update(ansprechpartner=ap2)

        def ids(**filter_):
            return {p["id"] for p in c.get("/api/patienten/", {"test": "ohne", **filter_}).json()["results"]}

        self.assertEqual(ids(versorger=self.versorger.id), {self.verlust.id, self.stabil.id})
        self.assertEqual(ids(ansprechpartner=self.ap1.id), {self.verlust.id})
        self.assertEqual(ids(ansprechpartner=ap2.id, ordering="-letzter_kontakt"), {self.stabil.id})

    def test_suche(self):
        c = client_fuer(self.mitarbeiter)

        def ids(text):
            return [p["id"] for p in c.get("/api/patienten/", {"suche": text}).json()["results"]]

        self.assertEqual(ids("01.01.1960"), [self.verlust.id])
        self.assertEqual(ids("1971-07-07"), [self.stabil.id])
        self.assertEqual(ids(str(self.stabil.nummer)), [self.stabil.id])
        self.assertEqual(ids("ver"), [self.verlust.id])
        self.assertEqual(ids("Stefan Stabil"), [self.stabil.id])

    def test_kontakt_ueberfaellig_nach_4_monaten(self):
        """Festlegung 01.10.2026: Patienten kommen meist quartalsweise → Hinweis nach 4 Monaten ohne Kontakt."""
        from stammdaten.models import Einstellungen

        self.assertEqual(Einstellungen.aktuell().kontakt_ueberfaellig_monate, 4)
        jetzt = timezone.now()
        drei = Patient.objects.create(nachname="Quartal", vorname="Q", geburtsdatum="1970-02-02")
        Kontakt.objects.create(patient=drei, text="<p>vor 3 Monaten</p>", zeitpunkt=jetzt - timedelta(days=90))
        fuenf = Patient.objects.create(nachname="Lange", vorname="L", geburtsdatum="1970-03-03")
        Kontakt.objects.create(patient=fuenf, text="<p>vor 5 Monaten</p>", zeitpunkt=jetzt - timedelta(days=150))
        c = client_fuer(self.mitarbeiter)
        ids = {p["id"] for p in c.get("/api/patienten/?pruefen=kein_kontakt&test=ohne").json()["results"]}
        self.assertIn(fuenf.id, ids)
        self.assertNotIn(drei.id, ids)
        zeilen = {p["id"]: p for p in c.get("/api/patienten/?test=ohne&seitengroesse=200").json()["results"]}
        self.assertIn("Kein Kontakt seit über 4 Mon.", [h["text"] for h in zeilen[fuenf.id]["kennzahlen"]["hinweise"]])
        self.assertNotIn("kontakt", {h["art"] for h in zeilen[drei.id]["kennzahlen"]["hinweise"]})
        self.assertEqual(c.get("/api/startseite/").json()["pruefen"]["kontakt_monate"], 4)

    def test_pruefen_filter(self):
        c = client_fuer(self.mitarbeiter)
        r = c.get("/api/patienten/?pruefen=kein_versorger&test=ohne").json()["results"]
        self.assertEqual([p["id"] for p in r], [self.patient.id])
        r = c.get("/api/patienten/?pruefen=kein_kontakt&test=ohne").json()["results"]
        self.assertEqual([p["id"] for p in r], [self.patient.id])
        pruefen = c.get("/api/startseite/").json()["pruefen"]
        self.assertEqual((pruefen["kein_versorger"], pruefen["kein_kontakt"]), (1, 1))

    def test_startseite(self):
        start = client_fuer(self.mitarbeiter).get("/api/startseite/").json()
        self.assertEqual([w["patient"] for w in start["gewichtswarnungen"]], [self.verlust.id])
        self.assertEqual((float(start["gewicht_schwelle"]["prozent"]), start["gewicht_schwelle"]["monate"]), (5.0, 3))
        zuletzt = start["zuletzt_eingetragen"]
        self.assertTrue(zuletzt)
        self.assertEqual({z["bereich"] for z in zuletzt}, {"kontakt", "gewicht"})
        self.assertEqual(start["zahlen"]["in_betreuung"], 3)  # ohne Testpatient


class Rollen(Grundlage):
    def test_schreibrechte(self):
        daten = {"nachname": "Neu", "vorname": "Nora", "geburtsdatum": "1980-02-02"}
        self.assertEqual(client_fuer(self.betrachter).post("/api/patienten/", daten, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.mitarbeiter).post("/api/patienten/", daten, format="json").status_code, 201)
        # Admins legen nur Testpatienten an (Nummern ab 9001)
        a = client_fuer(self.admin)
        self.assertEqual(a.get("/api/patienten/naechste-nummer/").json()["testpatient"], True)
        r = a.post("/api/patienten/", {**daten, "nachname": "Admin"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["ist_test"], r.json()["nummer"] >= 9001), (True, True))
        self.assertEqual(client_fuer(self.betrachter).get("/api/patienten/").status_code, 200)

    def test_nur_admin_verwaltet_benutzer(self):
        self.assertEqual(client_fuer(self.mediziner).get("/api/benutzer/").status_code, 403)
        r = client_fuer(self.admin).post("/api/benutzer/", {"username": "neu", "rolle": "mitarbeiter",
                                                             "first_name": "N", "last_name": "N"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("einmal_kennwort", r.json())

    def test_ohne_zweiten_faktor_kein_zugriff(self):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(self.mitarbeiter)  # kein is_verified
        r = c.get("/api/patienten/")
        self.assertEqual(r.status_code, 403)
        # Meldung „Anmeldung …“ statt „Recht fehlt“: daran erkennt die Oberfläche, dass neu angemeldet werden muss
        self.assertIn("Anmeldung mit zweitem Faktor", r.json()["detail"])

    def test_admin_schreibt_nur_bei_testpatienten(self):
        """Festlegung 01.10.2026: Admins dürfen alles, Patientendaten schreiben aber nur bei Testpatienten."""
        a = client_fuer(self.admin)
        test = Patient.objects.create(nachname="Probe", vorname="P", geburtsdatum="1970-01-01", ist_test=True)
        echt = self.patient
        self.assertTrue(a.get("/api/auth/ich/").json()["schreibt_nur_testpatienten"])
        self.assertFalse(client_fuer(self.mediziner).get("/api/auth/ich/").json()["schreibt_nur_testpatienten"])
        # echte Akte: lesen ja, schreiben nein
        self.assertEqual(a.get(f"/api/patienten/{echt.id}/").status_code, 200)
        versuche = [
            ("post", "/api/kontakte/", {"patient": echt.id, "text": "<p>x</p>"}),
            ("post", "/api/gewichte/", {"patient": echt.id, "gewicht_kg": "60.0"}),
            ("post", "/api/termine/", {"patient": echt.id, "art": "rueckruf", "faellig_am": str(timezone.localdate()),
                                       "titel": "Rückruf"}),
            ("patch", f"/api/patienten/{echt.id}/", {"ort": "Münster"}),
            ("post", "/api/infusionsplaene/entwurf/", {"patient": echt.id}),
            ("post", f"/api/patienten/{echt.id}/abschliessen/", {"anlass": "verstorben"}),
        ]
        for methode, url, daten in versuche:
            with self.subTest(url=url):
                r = getattr(a, methode)(url, daten, format="json")
                self.assertEqual(r.status_code, 403, r.content)
                self.assertIn("nur bei Testpatienten", r.json()["fehler"])
        self.assertEqual(Kontakt.objects.filter(patient=echt).count(), 0)
        # Einträge anderer Personen in echten Akten: nicht stornieren, nicht erledigen
        kontakt = self.neuer_kontakt()
        self.assertEqual(a.post(f"/api/kontakte/{kontakt['id']}/storno/", {"grund": "x"}, format="json").status_code, 403)
        # Testpatient: alles erlaubt
        self.assertEqual(a.post("/api/kontakte/", {"patient": test.id, "text": "<p>x</p>"}, format="json").status_code, 201)
        e = a.post("/api/infusionsplaene/entwurf/", {"patient": test.id}, format="json")
        self.assertEqual(e.status_code, 201, e.content)
        self.assertEqual(a.patch(f"/api/patienten/{test.id}/", {"ort": "Münster"}, format="json").status_code, 200)
        self.assertEqual(a.post(f"/api/patienten/{test.id}/abschliessen/", {"anlass": "therapie_beendet"},
                                format="json").status_code, 200)
        # Spezialeingriff bleibt: echte abgeschlossene Akte wieder öffnen
        client_fuer(self.mediziner).post(f"/api/patienten/{echt.id}/abschliessen/", {"anlass": "verstorben"},
                                         format="json")
        self.assertEqual(a.post(f"/api/patienten/{echt.id}/wieder-oeffnen/", {"grund": "Irrtum"},
                                format="json").status_code, 200)

    def test_testbenutzer_sieht_nur_testpatienten(self):
        tester = benutzer("tester", Rolle.MEDIZINER, ist_test=True)
        testpat = Patient.objects.create(nachname="T", vorname="T", geburtsdatum="1970-01-01", ist_test=True)
        r = client_fuer(tester).get("/api/patienten/").json()
        self.assertEqual([p["id"] for p in r["results"]], [testpat.id])
        self.assertEqual(client_fuer(tester).get(f"/api/patienten/{self.patient.id}/").status_code, 404)
        r = client_fuer(tester).post("/api/kontakte/", {"patient": self.patient.id, "text": "x"}, format="json")
        self.assertEqual(r.status_code, 400)


class Kontaktdaten(Grundlage):
    """Festlegung 01.10.2026: Bezugspersonen (1:n) mit Beziehung aus pflegbarer Liste und „Auskunft erlaubt“,
    gemeinsame Ärzteliste mit Zuordnung je Rolle, „kein“ Katheter/Versorger getrennt von „nicht erfasst“."""

    def test_beziehungsliste_wie_festgelegt(self):
        werte = list(Auswahlwert.objects.filter(liste=Auswahlwert.Liste.BEZIEHUNG).order_by("reihenfolge")
                     .values_list("wert", flat=True))
        self.assertEqual(werte, ["Mutter", "Vater", "Ehepartner/in", "Kind", "Betreuer/in (gesetzlich)",
                                 "Pflegedienst", "Sonstige"])

    def test_bezugspersonen_anlegen_aendern_nicht_loeschen(self):
        c = client_fuer(self.mitarbeiter)
        mutter = wert(Auswahlwert.Liste.BEZIEHUNG, "Mutter")
        r = c.post("/api/bezugspersonen/", {"patient": self.patient.id, "beziehung": mutter.id, "name": "Maria Echt",
                                            "telefon": "0251 1", "auskunft_erlaubt": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        bp = r.json()
        self.assertEqual((bp["beziehung_name"], bp["angelegt_von_name"] is not None), ("Mutter", True))
        # zweite Person (1:n), Beziehung aus falscher Liste wird abgewiesen
        katheter = wert(Auswahlwert.Liste.KATHETER, "Port")
        r = c.post("/api/bezugspersonen/", {"patient": self.patient.id, "beziehung": katheter.id, "name": "X"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("beziehung", r.json())
        r = c.post("/api/bezugspersonen/", {"patient": self.patient.id, "name": "  "}, format="json")
        self.assertEqual(r.status_code, 400)
        vater = wert(Auswahlwert.Liste.BEZIEHUNG, "Vater")
        r = c.post("/api/bezugspersonen/", {"patient": self.patient.id, "beziehung": vater.id, "name": "Paul Echt"},
                   format="json")
        self.assertEqual(r.status_code, 201)
        liste = c.get(f"/api/bezugspersonen/?patient={self.patient.id}").json()
        self.assertEqual(len(liste), 2)
        # Kopf zeigt, wem Auskunft gegeben werden darf
        kopf = c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual([a["name"] for a in kopf["auskunft"]], ["Maria Echt"])
        self.assertEqual(kopf["zaehler"]["bezugspersonen"], 2)
        # nicht löschen, sondern „nicht mehr aktuell“; steht im Verlauf
        self.assertEqual(c.delete(f"/api/bezugspersonen/{bp['id']}/").status_code, 405)
        r = c.patch(f"/api/bezugspersonen/{bp['id']}/", {"aktiv": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]["auskunft"], [])
        verlauf = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=bezugspersonen").json()
        self.assertEqual([v["aktion"] for v in verlauf], ["nicht mehr aktuell", "angelegt", "angelegt"])
        self.assertIn("Mutter · Maria Echt", verlauf[0]["beschreibung"])
        # Patient nicht umhängbar
        anderer = Patient.objects.create(nachname="Zwei", vorname="Z", geburtsdatum="1980-01-01")
        r = c.patch(f"/api/bezugspersonen/{bp['id']}/", {"patient": anderer.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_bezugspersonen_rechte(self):
        daten = {"patient": self.patient.id, "name": "Jemand"}
        self.assertEqual(client_fuer(self.betrachter).post("/api/bezugspersonen/", daten, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.betrachter).get(f"/api/bezugspersonen/?patient={self.patient.id}").status_code, 200)
        # Admin schreibt nur bei Testpatienten
        self.assertEqual(client_fuer(self.admin).post("/api/bezugspersonen/", daten, format="json").status_code, 403)
        # abgeschlossene Akte → 409
        Patient.objects.filter(pk=self.patient.pk).update(abgeschlossen_am=timezone.localdate(), abschluss_anlass="verstorben")
        r = client_fuer(self.mitarbeiter).post("/api/bezugspersonen/", daten, format="json")
        self.assertEqual(r.status_code, 409)

    def test_aerzteliste_und_zuordnung(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/aerzte/", {"name": "Dr. med. Haus", "praxis": "Praxis Haus", "fachrichtung": "Allgemeinmedizin",
                                    "ort": "Altenberge", "telefon": "02505 1"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        arzt = r.json()
        self.assertEqual(client_fuer(self.betrachter).post("/api/aerzte/", {"name": "X"}, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.betrachter).get("/api/aerzte/").status_code, 200)
        self.assertEqual(c.delete(f"/api/aerzte/{arzt['id']}/").status_code, 405)
        # neuer Patient mit Hausarzt aus der Liste (eine Transaktion)
        r = c.post("/api/patienten/", {"nachname": "Neu", "vorname": "Nora", "geburtsdatum": "1990-05-05",
                                       "aufnahme_hausarzt": arzt["id"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.json()["id"]
        self.assertEqual(r.json()["kopf"]["hausarzt"]["name"], "Dr. med. Haus")
        zuordnungen = c.get(f"/api/patient-aerzte/?patient={pid}").json()
        self.assertEqual([(z["rolle"], z["arzt_daten"]["telefon"]) for z in zuordnungen], [("hausarzt", "02505 1")])
        # gleiche Rolle doppelt → 400, andere Rolle möglich
        r = c.post("/api/patient-aerzte/", {"patient": pid, "arzt": arzt["id"], "rolle": "hausarzt"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = c.post("/api/patient-aerzte/", {"patient": pid, "arzt": arzt["id"], "rolle": "ueberweisend"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(c.get(f"/api/aerzte/{arzt['id']}/").json()["patienten_anzahl"], 1)
        # Telefonnummer einmal ändern → gilt in jeder Akte
        c.patch(f"/api/aerzte/{arzt['id']}/", {"telefon": "02505 99"}, format="json")
        self.assertEqual(c.get(f"/api/patienten/{pid}/").json()["kopf"]["hausarzt"]["telefon"], "02505 99")
        # nicht mehr zuständig statt löschen; deaktivierter Arzt nicht neu zuordenbar
        z = zuordnungen[0]
        self.assertEqual(c.delete(f"/api/patient-aerzte/{z['id']}/").status_code, 405)
        self.assertEqual(c.patch(f"/api/patient-aerzte/{z['id']}/", {"aktiv": False}, format="json").status_code, 200)
        self.assertIsNone(c.get(f"/api/patienten/{pid}/").json()["kopf"]["hausarzt"])
        verlauf = c.get(f"/api/patienten/{pid}/verlauf/?bereich=aerzte").json()
        self.assertEqual(verlauf[0]["aktion"], "nicht mehr zuständig")
        c.patch(f"/api/aerzte/{arzt['id']}/", {"aktiv": False}, format="json")
        r = c.post("/api/patient-aerzte/", {"patient": pid, "arzt": arzt["id"], "rolle": "facharzt"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = c.post("/api/patienten/", {"nachname": "N", "vorname": "N", "geburtsdatum": "1990-05-05",
                                       "aufnahme_hausarzt": arzt["id"]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Patient.objects.filter(nachname="N").exists())

    def test_kein_katheter_und_kein_versorger(self):
        c = client_fuer(self.mitarbeiter)
        url = f"/api/patienten/{self.patient.id}/"
        # nicht erfasst → Hinweis und Prüfliste
        zeile = lambda: next(p for p in c.get("/api/patienten/?test=ohne").json()["results"] if p["id"] == self.patient.id)  # noqa: E731
        self.assertIn("versorger", {h["art"] for h in zeile()["kennzahlen"]["hinweise"]})
        # bewusst „kein“ → kein Hinweis, nicht in der Prüfliste
        r = c.patch(url, {"kein_versorger": True, "kein_katheter": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["kopf"]["versorger"], r.json()["kopf"]["katheter"]), ("kein", "kein"))
        self.assertNotIn("versorger", {h["art"] for h in zeile()["kennzahlen"]["hinweise"]})
        self.assertEqual(c.get("/api/patienten/?pruefen=kein_versorger&test=ohne").json()["count"], 0)
        # „kein“ zusammen mit einer Auswahl ist widersprüchlich
        port = wert(Auswahlwert.Liste.KATHETER, "Port")
        r = c.patch(url, {"katheter": port.id, "kein_katheter": True}, format="json")
        self.assertEqual(r.status_code, 400)
        # Auswahl ohne Angabe hebt „kein“ auf
        r = c.patch(url, {"katheter": port.id}, format="json")
        self.assertEqual((r.status_code, r.json()["kein_katheter"], r.json()["kopf"]["katheter"]), (200, False, "Port"))
        # und die Datenbank lässt den Widerspruch auch direkt nicht zu
        with self.assertRaises(DatabaseError), transaction.atomic():
            Patient.objects.filter(pk=self.patient.pk).update(kein_katheter=True)


@override_settings(EPM_DOKUMENTE=Path(TMP))
class Musterdaten(TestCase):
    def test_anlegen_und_zuruecksetzen(self):
        call_command("epm_musterdaten", stdout=open("/dev/null", "w"))
        self.assertEqual(Patient.objects.filter(ist_test=True).count(), 6)
        self.assertTrue(Infusionsplan.objects.filter(status="entwurf").exists())
        plan = Infusionsplan.objects.filter(status="aktuell").first()
        self.assertEqual(sorted(str(v) for v in plan.vitamine.all()), ["Soluvit N", "Vitalipid adult"])
        self.assertEqual((plan.natrium_mmol, plan.kalium_mmol), (Decimal("78"), Decimal("40")))
        self.assertEqual(str(plan.spurenelemente), "Addel N")
        self.assertTrue(Termin.objects.filter(ort__wert="Praxis Dr. Holtmeier").exists())
        self.assertTrue(Dokument.objects.filter(typ_geprueft=False, herkunft="altsystem").exists())
        self.assertEqual(testpatienten_anlegen(), 0)  # wiederholbar
        r = testdaten_zuruecksetzen()
        self.assertEqual(r, {"geloescht": 6, "angelegt": 6})
        tester = User.objects.get(username="test")
        tester.muss_kennwort_aendern = False  # Einmal-Kennwort gilt hier als bereits ersetzt
        start = client_fuer(tester).get("/api/startseite/").json()
        self.assertTrue(start["gewichtswarnungen"])
        self.assertTrue(start["termine"]["ueberfaellig"])
        self.assertTrue(start["infusionsplaene"]["aelter_als_grenze"])
        self.assertTrue(start["infusionsplaene"]["entwuerfe"])
        self.assertEqual(start["pruefen"]["altdokumente"], 1)
        # Bezugspersonen und Ärzte gehören zu den Musterdaten und werden mit zurückgesetzt
        self.assertTrue(Bezugsperson.objects.filter(patient__ist_test=True, auskunft_erlaubt=True).exists())
        self.assertTrue(PatientArzt.objects.filter(patient__ist_test=True, rolle="hausarzt").exists())
        self.assertTrue(Arzt.objects.filter(name__endswith="(fiktiv)").exists())
