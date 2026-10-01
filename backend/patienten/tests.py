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
from stammdaten.models import Ansprechpartner, Auswahlwert, Versorger

from .kennzahlen import woche
from .models import Dokument, Gewichtsmessung, Kontakt, Patient, Termin
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

    def test_abschliessen_nur_mediziner(self):
        for wer in (self.mitarbeiter, self.betrachter, self.admin):
            with self.subTest(rolle=wer.rolle):
                r = client_fuer(wer).post(f"/api/patienten/{self.patient.id}/abschliessen/",
                                          {"anlass": "therapie_beendet"}, format="json")
                self.assertEqual(r.status_code, 403)
        c = client_fuer(self.mediziner)
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
        self.assertEqual(log[0]["person"], self.mediziner.anzeigename)
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
        self.assertEqual(z, {"in_betreuung": 3, "abgeschlossen": 0, "mit_hinweisen": 2, "gewichtsverlust": 1,
                             "termin_woche": 1})

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

    def test_suche(self):
        c = client_fuer(self.mitarbeiter)

        def ids(text):
            return [p["id"] for p in c.get("/api/patienten/", {"suche": text}).json()["results"]]

        self.assertEqual(ids("01.01.1960"), [self.verlust.id])
        self.assertEqual(ids("1971-07-07"), [self.stabil.id])
        self.assertEqual(ids(str(self.stabil.nummer)), [self.stabil.id])
        self.assertEqual(ids("ver"), [self.verlust.id])
        self.assertEqual(ids("Stefan Stabil"), [self.stabil.id])

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
        self.assertEqual(client_fuer(self.admin).post("/api/patienten/", daten, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.mitarbeiter).post("/api/patienten/", daten, format="json").status_code, 201)
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
        self.assertEqual(c.get("/api/patienten/").status_code, 403)

    def test_testbenutzer_sieht_nur_testpatienten(self):
        tester = benutzer("tester", Rolle.MEDIZINER, ist_test=True)
        testpat = Patient.objects.create(nachname="T", vorname="T", geburtsdatum="1970-01-01", ist_test=True)
        r = client_fuer(tester).get("/api/patienten/").json()
        self.assertEqual([p["id"] for p in r["results"]], [testpat.id])
        self.assertEqual(client_fuer(tester).get(f"/api/patienten/{self.patient.id}/").status_code, 404)
        r = client_fuer(tester).post("/api/kontakte/", {"patient": self.patient.id, "text": "x"}, format="json")
        self.assertEqual(r.status_code, 400)


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
