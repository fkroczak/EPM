"""
Prüft die fachlichen Regeln der Patientenakte gegen die echte PostgreSQL-Datenbank.

Aufruf im Container:
    sudo docker compose run --rm backend python manage.py test
"""
import io
import json
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

    def test_kontaktart(self):
        """Kontaktart wird erfasst und angezeigt (Klärung U6 vom 03.10.2026); nur Werte der Liste „Kontaktart“."""
        from stammdaten.models import Auswahlwert

        art, _ = Auswahlwert.objects.get_or_create(liste=Auswahlwert.Liste.KONTAKTART, wert="Telefon (angerufen)")
        k = self.neuer_kontakt(art=art.id)
        self.assertEqual((k["art"], k["art_name"]), (art.id, "Telefon (angerufen)"))
        self.assertIsNone(self.neuer_kontakt()["art_name"])
        fremd, _ = Auswahlwert.objects.get_or_create(liste=Auswahlwert.Liste.KATHETER, wert="Port")
        r = client_fuer(self.mitarbeiter).post("/api/kontakte/", {"patient": self.patient.id, "text": "x", "art": fremd.id},
                                               format="json")
        self.assertEqual(r.status_code, 400)

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

    def test_gleichzeitige_textaenderung_ueberschreibt_nicht(self):
        url = f"/api/patienten/{self.patient.id}/"
        a, b = client_fuer(self.mitarbeiter), client_fuer(self.mediziner)
        self.assertEqual(a.patch(url, {"therapie": "<p>A</p>", "basis_version": 0}, format="json").status_code, 200)
        # B hat noch Fassung 0 geöffnet
        r = b.patch(url, {"therapie": "<p>B</p>", "basis_version": 0}, format="json")
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn("inzwischen", r.json()["fehler"])
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.therapie, "<p>A</p>")
        self.assertEqual(b.patch(url, {"therapie": "<p>B</p>", "basis_version": 1}, format="json").status_code, 200)

    def test_aktennummer_unter_sperre(self):
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as abfragen:
            Patient.objects.create(nachname="Neu", vorname="Nina", geburtsdatum="1990-01-01")
        self.assertTrue(any("pg_advisory_xact_lock" in q["sql"] for q in abfragen.captured_queries))

    def test_befunde_mit_fassungen(self):
        """Reiter „Befunde“ (27.10.2026): Text mit Fassungen wie die Empfehlung, gleichzeitiges Speichern abgelehnt."""
        c = client_fuer(self.mitarbeiter)
        url = f"/api/patienten/{self.patient.id}/"
        self.assertEqual(c.patch(url, {"befunde": "<p>Sono: Leber unauffällig</p>", "basis_version": 0},
                                 format="json").status_code, 200)
        self.assertEqual(c.patch(url, {"befunde": "<p>Sono: Leber unauffällig</p><p>Gastro: o. B.</p>",
                                       "basis_version": 1}, format="json").status_code, 200)
        self.assertEqual(c.patch(url, {"befunde": "<p>veraltet</p>", "basis_version": 1}, format="json").status_code, 409)
        r = c.get(f"{url}versionen/?feld=befunde").json()
        self.assertEqual([f["version"] for f in r["fassungen"]], [2, 1])
        akte = c.get(url).json()
        self.assertIn("Gastro", akte["befunde"])
        self.assertEqual(akte["kopf"]["versionen"]["befunde"]["version"], 2)
        bereiche = {e.get("bereich") for e in c.get(f"{url}verlauf/?bereich=befunde").json()}
        self.assertEqual(bereiche, {"befunde"})

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
        # Bemerkung mit Versionen (Klärung U5 vom 03.10.2026); Krankenkasse und Telefon 2 in den Stammdaten
        self.assertEqual(c.patch(f"/api/patienten/{self.patient.id}/", {"bemerkung": "<p>aus dem Altsystem</p>",
                                                                        "krankenkasse": "AOK", "telefon2": "0251 1"},
                                 format="json").status_code, 200)
        r = c.get(f"/api/patienten/{self.patient.id}/versionen/?feld=bemerkung").json()
        self.assertEqual((r["version"], r["fassungen"][0]["text"]), (1, "<p>aus dem Altsystem</p>"))
        d = c.get(f"/api/patienten/{self.patient.id}/").json()
        self.assertEqual(d["kopf"]["versionen"]["bemerkung"]["version"], 1)
        self.assertEqual((d["krankenkasse"], d["telefon2"]), ("AOK", "0251 1"))
        verlauf = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=bemerkung").json()
        self.assertTrue(verlauf, verlauf)


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
        """Akten abschließen: Mitarbeiter, Mediziner, Admin (seit 02.10.2026 auch bei echten Akten); Betrachter nicht."""
        r = client_fuer(self.betrachter).post(f"/api/patienten/{self.patient.id}/abschliessen/",
                                              {"anlass": "therapie_beendet"}, format="json")
        self.assertEqual(r.status_code, 403)
        # Admin: echte Akte abschließen (Fehlerliste 02.10.2026, 6.3) – steht mit Person im Audit-Log
        echt = Patient.objects.create(nachname="Admin", vorname="Abschluss", geburtsdatum="1960-06-06")
        r = client_fuer(self.admin).post(f"/api/patienten/{echt.id}/abschliessen/", {"anlass": "betreuung_gewechselt"},
                                         format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["ist_abgeschlossen"])
        log = client_fuer(self.admin).get("/api/protokoll/?gruppe=abschluss").json()["results"]
        self.assertEqual(log[0]["person"], self.admin.anzeigename)
        # … mehr als abschließen darf die Administration an der echten Akte weiterhin nicht
        offen = Patient.objects.create(nachname="Admin", vorname="Offen", geburtsdatum="1960-06-06")
        self.assertEqual(client_fuer(self.admin).patch(f"/api/patienten/{offen.id}/", {"ort": "Münster"},
                                                       format="json").status_code, 403)
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
        self.assertEqual((r["testpatient"], r["testpatient_fest"]), (False, False))

    def test_testpatient_anlegen(self):
        """Fehlerliste 02.10.2026 (6.4): Mitarbeiter und Mediziner können beim Anlegen einen Testpatienten wählen –
        z. B. um Infusionspläne auszuprobieren. Er bekommt eine Nummer ab 9001 und zählt in keiner Statistik."""
        c = client_fuer(self.mitarbeiter)
        r = c.get("/api/patienten/naechste-nummer/?testpatient=1").json()
        self.assertEqual((r["nummer"], r["testpatient"], r["testpatient_fest"]), (9001, True, False))
        daten = {"nachname": "Plantest", "vorname": "Paula", "geburtsdatum": "1975-05-05"}
        r = c.post("/api/patienten/", {**daten, "testpatient": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["ist_test"], r.json()["nummer"]), (True, 9001))
        vorher = c.get("/api/patienten/zaehler/").json()["in_betreuung"]
        r2 = c.post("/api/patienten/", {**daten, "nachname": "Echt"}, format="json")
        self.assertEqual((r2.json()["ist_test"], r2.json()["nummer"] < 9001), (False, True))
        self.assertEqual(c.get("/api/patienten/zaehler/").json()["in_betreuung"], vorher + 1)
        # der Mediziner probiert an der Testakte einen Plan aus und gibt ihn frei
        m = client_fuer(self.mediziner)
        e = m.post("/api/infusionsplaene/entwurf/", {"patient": r.json()["id"]}, format="json")
        self.assertEqual(e.status_code, 201, e.content)
        # eine echte Akte wird nicht nachträglich zur Testakte (und umgekehrt)
        r3 = c.patch(f"/api/patienten/{r2.json()['id']}/", {"ist_test": True, "testpatient": True}, format="json")
        self.assertEqual(r3.status_code, 200)
        self.assertFalse(Patient.objects.get(pk=r2.json()["id"]).ist_test)

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

    def test_dokumentliste_ohne_abfragen_je_zeile(self):
        from django.test.utils import CaptureQueriesContext

        c = client_fuer(self.mitarbeiter)

        def abfragen():
            c.post("/api/dokumente/", {"patient": self.patient.id, "titel": "Brief",
                                       "datei": SimpleUploadedFile("brief.pdf", b"%PDF-1.4 x")}, format="multipart")
            with CaptureQueriesContext(connection) as q:
                self.assertEqual(c.get(f"/api/dokumente/?patient={self.patient.id}").status_code, 200)
            return len(q)

        eins = abfragen()
        abfragen()
        self.assertEqual(abfragen(), eins)

    def test_dokument_upload_fehler_hinterlaesst_keine_datei(self):
        from unittest import mock

        from django.conf import settings

        vorher = set(Path(settings.EPM_DOKUMENTE).rglob("*"))
        datei = SimpleUploadedFile("brief.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        with mock.patch.object(Dokument, "save", side_effect=DatabaseError("weg")), self.assertRaises(DatabaseError):
            client_fuer(self.mitarbeiter).post("/api/dokumente/", {"patient": self.patient.id, "titel": "Brief",
                                                                   "datei": datei}, format="multipart")
        self.assertEqual({p for p in Path(settings.EPM_DOKUMENTE).rglob("*") if p.is_file()},
                         {p for p in vorher if p.is_file()})

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
        # braucht keinen Infusionsplan (bestätigt) – sonst Hinweis „Kein Infusionsplan“
        Patient.objects.filter(pk=cls.stabil.pk).update(kein_plan=True)
        # Testpatient: in der Liste mit Filter „test=ohne“ ausblendbar, zählt in keiner Statistik
        cls.testpat = Patient.objects.create(nachname="Test", vorname="T", geburtsdatum="1970-01-01", ist_test=True)
        # länger bestehende Akten: „kein Gewicht“ zählt erst X Monate nach dem Anlegen (11.10.2026)
        Patient.objects.update(angelegt_am=timezone.now() - timedelta(days=365))

    def test_liste_mit_kennzahlen(self):
        r = client_fuer(self.mitarbeiter).get("/api/patienten/?status=in_betreuung&test=ohne").json()
        zeilen = {p["id"]: p for p in r["results"]}
        self.assertEqual(set(zeilen), {self.patient.id, self.verlust.id, self.stabil.id})
        v = zeilen[self.verlust.id]["kennzahlen"]
        self.assertEqual(Decimal(str(v["gewicht"]["kg"])), Decimal("64.0"))
        self.assertEqual((v["trend"]["richtung"], v["trend"]["warnung"]), ("down", True))
        # seit F120 hat jede Akte in Betreuung ohne Befunde zusätzlich „labor“ und „bia“, seit F186 die fehlenden
        # Angaben (hier ohne Hausarzt, Telefon und Diagnose; das Gewicht ist aktuell)
        self.assertEqual([h["art"] for h in v["hinweise"]],
                         ["gewicht", "ohne_plan", "nickelallergie", "labor", "bia", "hausarzt", "telefon", "diagnose"])
        s = zeilen[self.stabil.id]["kennzahlen"]
        self.assertEqual(s["trend"]["richtung"], "flat")
        self.assertTrue(s["termin_woche"])
        self.assertEqual([h["art"] for h in s["hinweise"]], ["nickelallergie", "labor", "bia", "hausarzt", "telefon", "diagnose"])
        ohne = zeilen[self.patient.id]["kennzahlen"]
        self.assertEqual({h["art"] for h in ohne["hinweise"]},
                         {"versorger", "nickelallergie", "kontakt", "ohne_plan", "labor", "bia", "hausarzt", "telefon", "gewicht_fehlt",
                          "diagnose"})
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
        # seit F120 hat jede Akte in Betreuung ohne Laborbefund und ohne BIA-Messung einen Hinweis – also alle drei
        self.assertEqual(ids("hinweise"), {self.verlust.id, self.patient.id, self.stabil.id})
        z = c.get("/api/patienten/zaehler/").json()
        # Testpatienten zählen nicht mit
        self.assertEqual(z, {"in_betreuung": 3, "abgeschlossen": 0, "mit_hinweisen": 3, "gewichtsverlust": 1,
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

    def test_migration_stellt_bestehenden_wert_12_auf_4(self):
        """Auf einer bestehenden Datenbank (Wert noch 12) stellt die Datenmigration um und schreibt den Grund in die
        Historie. Fehler auf dem Testsystem 01.10.2026: der Grund war länger als 100 Zeichen → Migration brach ab."""
        import importlib

        from django.apps import apps as django_apps

        from stammdaten.models import Einstellungen

        migration = importlib.import_module("stammdaten.migrations.0007_kontakt_ueberfaellig_4_monate")
        self.assertLessEqual(len(migration.GRUND), 100)
        # „bald fällig“ (seit 0009) unter 4, damit der damalige Zielwert 4 auch nach heutiger Prüfung gültig ist
        Einstellungen.objects.filter(pk=Einstellungen.aktuell().pk).update(kontakt_ueberfaellig_monate=12,
                                                                            kontakt_bald_monate=2)
        migration.umstellen(django_apps, None)
        e = Einstellungen.objects.get(pk=1)
        self.assertEqual(e.kontakt_ueberfaellig_monate, 4)
        self.assertEqual(e.history.order_by("-history_id").first().history_change_reason, migration.GRUND)
        # ein selbst eingetragener Wert bleibt
        Einstellungen.objects.filter(pk=1).update(kontakt_ueberfaellig_monate=6)
        migration.umstellen(django_apps, None)
        self.assertEqual(Einstellungen.objects.get(pk=1).kontakt_ueberfaellig_monate, 6)

    def test_kontakt_faellig_in_zwei_stufen(self):
        """S04 (Festlegung 01.10.2026): „bald fällig“ nach 4, „überfällig“ nach 6 Monaten ohne Kontakt – in
        Patientenliste (Hinweis und Prüffilter) und „Nach und nach prüfen“."""
        from stammdaten.models import Einstellungen

        e = Einstellungen.aktuell()
        self.assertEqual((e.kontakt_bald_monate, e.kontakt_ueberfaellig_monate), (4, 6))
        jetzt = timezone.now()
        drei = Patient.objects.create(nachname="Quartal", vorname="Q", geburtsdatum="1970-02-02")
        Kontakt.objects.create(patient=drei, text="<p>vor 3 Monaten</p>", zeitpunkt=jetzt - timedelta(days=90))
        fuenf = Patient.objects.create(nachname="Lange", vorname="L", geburtsdatum="1970-03-03")
        Kontakt.objects.create(patient=fuenf, text="<p>vor 5 Monaten</p>", zeitpunkt=jetzt - timedelta(days=150))
        sieben = Patient.objects.create(nachname="Sieben", vorname="S", geburtsdatum="1970-04-04")
        Kontakt.objects.create(patient=sieben, text="<p>vor 7 Monaten</p>", zeitpunkt=jetzt - timedelta(days=210))
        c = client_fuer(self.mitarbeiter)

        def ids(pruefen):
            return {p["id"] for p in c.get(f"/api/patienten/?pruefen={pruefen}&test=ohne").json()["results"]}

        self.assertTrue({fuenf.id, sieben.id, self.patient.id} <= ids("kein_kontakt"))
        self.assertNotIn(drei.id, ids("kein_kontakt"))
        self.assertEqual(ids("kontakt_bald"), {fuenf.id})
        self.assertEqual(ids("kontakt_ueberfaellig"), {sieben.id, self.patient.id})  # self.patient: noch kein Kontakt
        zeilen = {p["id"]: p for p in c.get("/api/patienten/?test=ohne&seitengroesse=200").json()["results"]}

        def hinweis(pid):
            return next(h for h in zeilen[pid]["kennzahlen"]["hinweise"] if h["art"] == "kontakt")

        self.assertEqual((hinweis(fuenf.id)["stufe"], hinweis(fuenf.id)["text"]), ("bald", "Kontakt bald fällig (über 4 Mon.)"))
        self.assertEqual((hinweis(sieben.id)["stufe"], hinweis(sieben.id)["text"]),
                         ("ueberfaellig", "Kontakt überfällig (über 6 Mon.)"))
        self.assertEqual(hinweis(self.patient.id)["text"], "Noch kein Kontakt erfasst")
        self.assertNotIn("kontakt", {h["art"] for h in zeilen[drei.id]["kennzahlen"]["hinweise"]})
        self.assertEqual(zeilen[fuenf.id]["kennzahlen"]["kontakt_stufe"], "bald")
        pruefen = c.get("/api/startseite/").json()["pruefen"]
        self.assertEqual((pruefen["kontakt_monate"], pruefen["kontakt_bald_monate"], pruefen["kontakt_ueberfaellig_monate"]),
                         (4, 4, 6))
        self.assertEqual((pruefen["kontakt_bald"], pruefen["kontakt_ueberfaellig"], pruefen["kein_kontakt"]), (1, 2, 3))
        # Grenzwerte verschieben: mit 6/8 Monaten ist „Sieben“ nur noch bald fällig
        Einstellungen.objects.filter(pk=1).update(kontakt_bald_monate=6, kontakt_ueberfaellig_monate=8)
        self.assertEqual(ids("kontakt_bald"), {sieben.id})

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
        self.assertEqual({z["bereich"] for z in zuletzt}, {"kontakt", "gewicht", "termin"})  # Termine seit S10
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
        # zweiter Faktor freiwillig (Festlegung 02.10.2026): ohne eingerichteten Authenticator genügt das Kennwort
        self.assertEqual(c.get("/api/patienten/").status_code, 200)
        # wer einen eingerichtet hat, kommt ohne Code nicht hinein
        from epm.pruefhilfen import mit_zweitem_faktor

        mit_zweitem_faktor(self.mitarbeiter)
        r = c.get("/api/patienten/")
        self.assertEqual(r.status_code, 403)
        # Meldung „Anmeldung …“ statt „Recht fehlt“: daran erkennt die Oberfläche, dass neu angemeldet werden muss
        self.assertIn("Anmeldung mit zweitem Faktor", r.json()["detail"])
        # … ebenso alle, sobald die Administration den zweiten Faktor zur Pflicht macht
        from accounts.models import Anmelderegeln

        Anmelderegeln.objects.update_or_create(pk=1, defaults={"zweiter_faktor": "alle"})
        d = APIClient()
        d.force_authenticate(self.betrachter)
        self.assertEqual(d.get("/api/patienten/").status_code, 403)

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


LOESCHLISTE = Path(TMP) / "loeschliste" / "loeschliste.jsonl"


@override_settings(EPM_LOESCHLISTE=LOESCHLISTE)
class FalschZugeordneteDokumente(Grundlage):
    """Dokument beim falschen Patienten (Festlegung 02.10.2026): richtig zuordnen oder endgültig löschen."""

    def setUp(self):
        LOESCHLISTE.unlink(missing_ok=True)
        self.sabine = Patient.objects.create(nachname="Falsch", vorname="Sabine", geburtsdatum="1970-01-01")
        self.bernd = Patient.objects.create(nachname="Richtig", vorname="Bernd", geburtsdatum="1960-06-06")

    def hochladen(self, patient, titel="Arztbrief Bernd Richtig"):
        datei = SimpleUploadedFile("brief.pdf", b"%PDF-1.4 Bernd", content_type="application/pdf")
        r = client_fuer(self.mitarbeiter).post("/api/dokumente/", {"patient": patient.id, "titel": titel, "datei": datei},
                                               format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        return Dokument.objects.get(pk=r.json()["id"])

    def test_umhaengen(self):
        dok = self.hochladen(self.sabine)
        alter_pfad, sha = dok.pfad, dok.sha256
        url = f"/api/dokumente/{dok.id}/umhaengen/"
        # Recht: Standard Mediziner und Admin (seit 02.10.2026 auch bei echten Akten), nicht Mitarbeiter
        self.assertEqual(client_fuer(self.mitarbeiter).post(url, {"patient": self.bernd.id, "grund": "falscher Patient"},
                                                            format="json").status_code, 403)
        r = client_fuer(self.admin).post(url, {"patient": self.bernd.id, "grund": ""}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["grund"]))  # erlaubt, nur der Grund fehlt
        c = client_fuer(self.mediziner)
        self.assertIn("grund", c.post(url, {"patient": self.bernd.id, "grund": ""}, format="json").json())
        self.assertIn("patient", c.post(url, {"patient": self.sabine.id, "grund": "falscher Patient"}, format="json").json())
        with self.captureOnCommitCallbacks() as nach_commit:
            r = c.post(url, {"patient": self.bernd.id, "grund": "beim falschen Patienten hochgeladen"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        dok.refresh_from_db()
        self.assertEqual((dok.patient_id, dok.sha256), (self.bernd.id, sha))
        self.assertTrue(dok.pfad.is_file())
        # die alte Datei verschwindet erst mit dem Commit
        self.assertTrue(alter_pfad.exists())
        for f in nach_commit:
            f()
        self.assertFalse(alter_pfad.exists())
        self.assertTrue(dok.datei.startswith(f"{self.bernd.nummer}/"))
        # Verlauf: Sabine sieht weder Titel noch Bernd, Bernd sieht die Übernahme mit Grund
        bei_sabine = c.get(f"/api/patienten/{self.sabine.id}/verlauf/?bereich=dokumente").json()
        self.assertEqual([e["aktion"] for e in bei_sabine], ["einer anderen Akte zugeordnet", "hochgeladen"])
        self.assertNotIn("Bernd", str(bei_sabine))
        self.assertNotIn("Arztbrief", str(bei_sabine))
        bei_bernd = c.get(f"/api/patienten/{self.bernd.id}/verlauf/?bereich=dokumente").json()
        self.assertEqual([(e["aktion"], e["grund"]) for e in bei_bernd],
                         [("von einer anderen Akte übernommen", "beim falschen Patienten hochgeladen")])
        self.assertIn("Arztbrief Bernd Richtig", bei_bernd[0]["beschreibung"])
        self.assertNotIn("Sabine", str(bei_bernd))
        # Audit-Log vollständig
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.DOKUMENT_UMGEHAENGT).get()
        self.assertEqual((e.details["von"][:13], e.details["nach"][:13]), ("Falsch, Sabin", "Richtig, Bern"))
        # Liste: nur noch bei Bernd
        self.assertEqual(c.get(f"/api/dokumente/?patient={self.sabine.id}").json()["count"], 0)
        self.assertEqual(c.get(f"/api/dokumente/?patient={self.bernd.id}").json()["count"], 1)
        # der Vorgang ist unveränderlich
        from .models import DokumentVorgang

        with self.assertRaises(DatabaseError), transaction.atomic():
            DokumentVorgang.objects.update(grund="geändert")

    def totp_code(self):
        from django_otp.oath import totp
        from django_otp.plugins.otp_totp.models import TOTPDevice

        from epm.pruefhilfen import mit_zweitem_faktor

        if not TOTPDevice.objects.filter(user=self.mediziner).exists():
            mit_zweitem_faktor(self.mediziner)
        geraet = TOTPDevice.objects.get(user=self.mediziner)
        return geraet, lambda: f"{totp(geraet.bin_key, geraet.step, geraet.t0, geraet.digits):06d}"

    def endgueltig_loeschen(self, dok, grund="Dokument eines fremden Patienten, nicht aus der Stiftung"):
        from epm.pruefhilfen import KENNWORT

        _, code = self.totp_code()
        c = client_fuer(self.mediziner)
        bestaetigung = c.post(f"/api/dokumente/{dok.id}/loeschen-vorbereiten/").json()["code"]
        with self.captureOnCommitCallbacks(execute=True):
            r = c.post(f"/api/dokumente/{dok.id}/loeschen/", {"grund": grund, "kennwort": KENNWORT, "code": code(),
                                                              "bestaetigung": bestaetigung}, format="json")
        self.assertEqual(r.status_code, 204, r.content)

    def test_admin_loescht_auch_bei_echter_akte(self):
        """Festlegung 02.10.2026: endgültig löschen auch Admins – auch bei echten Akten (Ausnahme von „nur
        Testpatienten“); mit denselben Bestätigungen wie beim Mediziner. Andere Patientendaten weiter nur lesen."""
        from django_otp.oath import totp
        from django_otp.plugins.otp_totp.models import TOTPDevice

        from epm.pruefhilfen import KENNWORT, mit_zweitem_faktor

        mit_zweitem_faktor(self.admin)
        geraet = TOTPDevice.objects.get(user=self.admin)
        dok = self.hochladen(self.sabine)
        self.assertFalse(dok.patient.ist_test)
        pfad = dok.pfad
        a = client_fuer(self.admin)
        bestaetigung = a.post(f"/api/dokumente/{dok.id}/loeschen-vorbereiten/").json()["code"]
        with self.captureOnCommitCallbacks(execute=True):
            r = a.post(f"/api/dokumente/{dok.id}/loeschen/", {
                "grund": "Falsch zugeordnet, gehört nicht zur Stiftung", "kennwort": KENNWORT,
                "code": f"{totp(geraet.bin_key, geraet.step, geraet.t0, geraet.digits):06d}", "bestaetigung": bestaetigung},
                format="json")
        self.assertEqual(r.status_code, 204, r.content)
        self.assertFalse(Dokument.objects.filter(pk=dok.id).exists())
        self.assertFalse(pfad.exists())
        # sonst schreibt der Admin bei echten Akten weiterhin nichts
        r = a.patch(f"/api/patienten/{self.sabine.id}/", {"diagnose": "<p>x</p>"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_admin_ordnet_dokument_bei_echten_akten_zu(self):
        """Fehlerliste 02.10.2026 (6.3): Admins dürfen ein Dokument auch bei echten Akten dem richtigen Patienten
        zuordnen; vollständig im Audit-Log."""
        dok = self.hochladen(self.sabine)
        self.assertFalse(self.sabine.ist_test or self.bernd.ist_test)
        r = client_fuer(self.admin).post(f"/api/dokumente/{dok.id}/umhaengen/",
                                         {"patient": self.bernd.id, "grund": "beim falschen Patienten hochgeladen"},
                                         format="json")
        self.assertEqual(r.status_code, 200, r.content)
        dok.refresh_from_db()
        self.assertEqual(dok.patient_id, self.bernd.id)
        self.assertTrue(dok.pfad.is_file())
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.DOKUMENT_UMGEHAENGT).get()
        self.assertEqual(e.benutzer, self.admin)
        # hochladen oder ändern darf die Administration an echten Akten weiterhin nicht
        r = client_fuer(self.admin).patch(f"/api/dokumente/{dok.id}/", {"notiz": "x"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_endgueltig_loeschen_ohne_zweiten_faktor(self):
        """Festlegung 03.10.2026: Endgültig löschen nur mit eingerichtetem zweitem Faktor; ohne ihn wird abgewiesen
        (mit Hinweis, ihn unter Mein Konto einzurichten), das Dokument bleibt."""
        from django_otp.plugins.otp_totp.models import TOTPDevice

        from accounts.zweifaktor import OHNE_ZWEITEN_FAKTOR
        from epm.pruefhilfen import KENNWORT

        self.assertFalse(TOTPDevice.objects.filter(user=self.mediziner).exists())
        dok = self.hochladen(self.sabine)
        c = client_fuer(self.mediziner)
        bestaetigung = c.post(f"/api/dokumente/{dok.id}/loeschen-vorbereiten/").json()["code"]
        r = c.post(f"/api/dokumente/{dok.id}/loeschen/", {"grund": "Dokument eines fremden Patienten", "kennwort": KENNWORT,
                                                          "bestaetigung": bestaetigung}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json(), {"code": OHNE_ZWEITEN_FAKTOR})
        self.assertTrue(Dokument.objects.filter(pk=dok.id).exists())

    def test_endgueltig_loeschen(self):
        from epm.pruefhilfen import KENNWORT

        geraet, code = self.totp_code()
        TOTPDevice = type(geraet)

        dok = self.hochladen(self.sabine)
        # Notiz und Datum mit Angaben zur fremden Person: auch sie müssen nach dem Löschen überall verschwinden
        r = client_fuer(self.mitarbeiter).patch(f"/api/dokumente/{dok.id}/", {"notiz": "Bernd Richtig, Kurzdarm",
                                                                             "datum": "2026-09-01"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        dok.refresh_from_db()
        pfad = dok.pfad
        basis = f"/api/dokumente/{dok.id}/"
        # Mediziner und Admin (auch bei echten Akten, Festlegung 02.10.2026), Mitarbeiter nicht
        self.assertFalse(dok.patient.ist_test)
        self.assertEqual(client_fuer(self.admin).post(basis + "loeschen-vorbereiten/").status_code, 200)
        self.assertEqual(client_fuer(self.mitarbeiter).post(basis + "loeschen-vorbereiten/").status_code, 403)
        c = client_fuer(self.mediziner)
        grund = "Dokument eines fremden Patienten, nicht aus der Stiftung"
        # ohne vorbereiteten Bestätigungscode
        r = c.post(basis + "loeschen/", {"grund": grund, "kennwort": KENNWORT, "code": code(), "bestaetigung": "X"}, format="json")
        self.assertIn("abgelaufen", r.json()["bestaetigung"])
        bestaetigung = c.post(basis + "loeschen-vorbereiten/").json()["code"]
        self.assertEqual(len(bestaetigung), 6)
        # falscher Bestätigungscode, falsches Kennwort, falscher 2FA-Code → abgelehnt und protokolliert
        self.assertIn("bestaetigung", c.post(basis + "loeschen/", {"grund": grund, "kennwort": KENNWORT, "code": code(),
                                                                   "bestaetigung": "AAAAAA" if bestaetigung != "AAAAAA" else "BBBBBB"},
                                             format="json").json())
        self.assertIn("kennwort", c.post(basis + "loeschen/", {"grund": grund, "kennwort": "falsch", "code": code(),
                                                               "bestaetigung": bestaetigung}, format="json").json())
        self.assertIn("code", c.post(basis + "loeschen/", {"grund": grund, "kennwort": KENNWORT, "code": "000000"
                                                           if code() != "000000" else "111111",
                                                           "bestaetigung": bestaetigung}, format="json").json())
        self.assertEqual(SystemEreignis.objects.filter(art=SystemEreignis.Art.DOKUMENT_LOESCHEN_ABGELEHNT).count(), 4)
        self.assertTrue(pfad.is_file())
        TOTPDevice.objects.filter(pk=geraet.pk).update(throttling_failure_timestamp=None, throttling_failure_count=0)
        with self.captureOnCommitCallbacks(execute=True):
            r = c.post(basis + "loeschen/", {"grund": grund, "kennwort": KENNWORT, "code": code(),
                                             "bestaetigung": bestaetigung.lower()}, format="json")
        self.assertEqual(r.status_code, 204, r.content)
        self.assertFalse(Dokument.objects.filter(pk=dok.id).exists())
        self.assertFalse(pfad.exists())
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.DOKUMENT_GELOESCHT).get()
        self.assertEqual((e.details["grund"], e.details["sha256"], e.details["groesse"]), (grund, dok.sha256, dok.groesse))
        self.assertNotIn("titel", e.details)
        verlauf = c.get(f"/api/patienten/{self.sabine.id}/verlauf/?bereich=dokumente").json()
        self.assertEqual([(e["aktion"], e["grund"]) for e in verlauf],
                         [("endgültig gelöscht", grund), ("geändert", None), ("hochgeladen", None)])
        self.assertNotIn("Arztbrief", str(verlauf))
        # Art. 17 DSGVO (U15): Titel, Dateiname, Notiz und Datum stehen nirgends mehr – auch nicht in der Historie
        # und im Audit-Log. Es bleibt der Nachweis ohne Inhalt: Nummer, Prüfsumme, Größe, Zeitpunkte, Person, Grund.
        historie = Dokument.history.filter(id=dok.id)
        self.assertEqual(historie.count(), 3)
        self.assertEqual(set(historie.values_list("titel", "originalname", "notiz", "datum")),
                         {("[entfernt]", "[entfernt]", "", None)})
        self.assertEqual(set(historie.values_list("sha256", "groesse")), {(dok.sha256, dok.groesse)})
        protokoll = c.get("/api/protokoll/?gruppe=dokument,fehlversuch").json()["results"]
        texte = "\n".join(p["beschreibung"] for p in protokoll)
        for verboten in ("Arztbrief", "Bernd", "brief.pdf", "Kurzdarm"):
            self.assertNotIn(verboten, texte)
            for ereignis in SystemEreignis.objects.filter(objekt=f"Dokument {dok.id}"):
                self.assertNotIn(verboten, json.dumps(ereignis.details, ensure_ascii=False))
        self.assertIn(f"Dokument Nr. {dok.id} (SHA-256 {dok.sha256[:8]}…) aus Falsch, Sabine", texte)
        self.assertIn("abgelehnt: Passwort falsch.", texte)
        # Löschliste: eine Zeile, ohne Titel und Dateinamen
        zeilen = LOESCHLISTE.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(zeilen), 1)
        eintrag = json.loads(zeilen[0])
        self.assertEqual((eintrag["dokument"], eintrag["sha256"], eintrag["patient"]), (dok.id, dok.sha256, self.sabine.id))
        self.assertNotIn("Arztbrief", zeilen[0])
        self.assertNotIn("brief.pdf", zeilen[0])
        # Die Trigger lassen nur genau diese Schwärzung zu: keine andere Spalte, kein anderes Dokument
        anderes = self.hochladen(self.bernd, "Bleibt bei Bernd")
        for sql, nummer in [("UPDATE patienten_historicaldokument SET titel = 'anders' WHERE id = %s", dok.id),
                            ("UPDATE patienten_historicaldokument SET groesse = 1 WHERE id = %s", dok.id),
                            ("UPDATE patienten_historicaldokument SET titel = '[entfernt]', originalname = '[entfernt]', "
                             "notiz = '', datum = NULL WHERE id = %s", anderes.id),
                            ("DELETE FROM patienten_historicaldokument WHERE id = %s", dok.id),
                            ("UPDATE audit_systemereignis SET details = details || '{\"grund\": \"x\"}' "
                             "WHERE objekt = 'Dokument ' || %s", dok.id)]:
            with self.subTest(sql=sql), self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
                cur.execute("SELECT set_config('epm.schwaerzen', %s, true)", [f"dokument:{dok.id}:{dok.sha256}"])
                cur.execute(sql, [nummer])
        self.assertEqual(Dokument.history.filter(id=anderes.id).get().titel, "Bleibt bei Bernd")
        # der Bestätigungscode gilt nur einmal
        self.assertEqual(c.post(basis + "loeschen/", {"grund": grund}, format="json").status_code, 404)

    def test_loeschung_nach_wiederherstellung_nachholen(self):
        """Eine Sicherung von vor der Löschung wird zurückgespielt: Beim Start löscht und schwärzt das Backend erneut
        (Art. 17 DSGVO). Ein neues Dokument, das dieselbe Nummer bekommen hat, bleibt unberührt."""
        from audit.schutz import wartungsmodus

        from .management.commands.epm_loeschungen_nachholen import nachholen
        from .models import DokumentVorgang

        dok = self.hochladen(self.sabine)
        werte = {f.attname: getattr(dok, f.attname) for f in Dokument._meta.concrete_fields}
        inhalt = dok.pfad.read_bytes()
        self.endgueltig_loeschen(dok)
        # Ohne Befund passiert nichts
        self.assertEqual(nachholen(), {"dokumente": 0, "dateien": 0, "geschwaerzt": 0, "liste_ergaenzt": 0})

        # „Wiederherstellung“: Datensatz, Datei und Historie sind zurück, Vorgang und Protokoll der Löschung nicht
        with wartungsmodus():
            DokumentVorgang.objects.filter(dokument_id=dok.id).delete()
            SystemEreignis.objects.filter(objekt=f"Dokument {dok.id}").delete()
        Dokument.objects.create(**werte)
        Path(dok.pfad).parent.mkdir(parents=True, exist_ok=True)
        dok.pfad.write_bytes(inhalt)
        self.assertEqual(Dokument.history.filter(id=dok.id, titel="Arztbrief Bernd Richtig").count(), 1)

        call_command("epm_loeschungen_nachholen", stdout=io.StringIO())
        self.assertFalse(Dokument.objects.filter(pk=dok.id).exists())
        self.assertFalse(dok.pfad.exists())
        self.assertFalse(Dokument.history.filter(id=dok.id).exclude(titel="[entfernt]").exists())
        vorgang = DokumentVorgang.objects.get(dokument_id=dok.id)
        self.assertIn("nach einer Wiederherstellung erneut ausgeführt", vorgang.grund)
        self.assertEqual((vorgang.sha256, vorgang.person_id), (dok.sha256, self.mediziner.id))
        e = SystemEreignis.objects.get(art=SystemEreignis.Art.DOKUMENT_LOESCHUNG_NACHGEHOLT)
        self.assertEqual(e.objekt, f"Dokument {dok.id}")
        protokoll = client_fuer(self.mediziner).get("/api/protokoll/?gruppe=dokument").json()["results"]
        self.assertIn("war durch eine Wiederherstellung zurückgekommen", protokoll[0]["beschreibung"])
        verlauf = client_fuer(self.mediziner).get(f"/api/patienten/{self.sabine.id}/verlauf/?bereich=dokumente").json()
        self.assertEqual(verlauf[0]["aktion"], "endgültig gelöscht")
        self.assertNotIn("Arztbrief", str(verlauf))

        # Nur die Datei kommt zurück (ältere Dokumentsicherung, neuere Datenbank): sie wird entfernt
        dok.pfad.write_bytes(inhalt)
        self.assertEqual(nachholen()["dateien"], 1)
        self.assertFalse(dok.pfad.exists())

        # Neues Dokument mit derselben Nummer, anderer Inhalt: bleibt
        neu = {**werte, "titel": "Neuer Befund", "sha256": "0" * 64, "datei": f"{self.sabine.nummer}/neu.pdf"}
        Dokument.objects.create(**neu)
        self.assertEqual(nachholen()["dokumente"], 0)
        self.assertEqual(Dokument.objects.get(pk=dok.id).titel, "Neuer Befund")
        self.assertEqual(Dokument.history.filter(id=dok.id, titel="Neuer Befund").count(), 1)

        # Löschliste verloren: wird aus der Datenbank ergänzt
        LOESCHLISTE.unlink()
        self.assertEqual(nachholen()["liste_ergaenzt"], 1)
        self.assertIn(dok.sha256, LOESCHLISTE.read_text(encoding="utf-8"))

    def test_migration_schwaerzt_bestehende_loeschungen(self):
        """Vor U15 gelöschte Dokumente (Titel noch in Historie und Audit-Log) werden beim Update nachträglich
        geschwärzt; der Vorgang bekommt Prüfsumme und Pfad, der Start ergänzt die Löschliste."""
        import importlib
        import types

        from django.apps import apps as django_apps

        from .management.commands.epm_loeschungen_nachholen import nachholen
        from .models import DokumentVorgang

        migration = importlib.import_module("patienten.migrations.0006_geloeschte_dokumente_schwaerzen")
        dok = self.hochladen(self.sabine)
        nummer, sha, datei = dok.id, dok.sha256, dok.datei  # nach delete() ist dok.id leer
        # so hat die Version vor U15 gelöscht: Vorgang ohne Prüfsumme, Titel im Audit-Log
        DokumentVorgang.objects.create(art=DokumentVorgang.Art.GELOESCHT, dokument_id=dok.id, von_patient=self.sabine,
                                       grund="fremdes Dokument", person=self.mediziner)
        protokolliere(SystemEreignis.Art.DOKUMENT_LOESCHEN_ABGELEHNT, objekt=f"Dokument {nummer}", titel=dok.titel,
                      fehler="Passwort falsch.")
        protokolliere(SystemEreignis.Art.DOKUMENT_GELOESCHT, objekt=f"Dokument {nummer}", titel=dok.titel,
                      akte="Falsch, Sabine", grund="fremdes Dokument", sha256=sha, groesse=dok.groesse)
        dok.delete()
        self.assertTrue(Dokument.history.filter(id=nummer, titel="Arztbrief Bernd Richtig").exists())
        migration.vorwaerts(django_apps, types.SimpleNamespace(connection=connection))
        self.assertEqual(Dokument.history.filter(id=nummer).count(), 2)
        self.assertFalse(Dokument.history.filter(id=nummer).exclude(titel="[entfernt]").exists())
        self.assertEqual(set(Dokument.history.filter(id=nummer).values_list("originalname", flat=True)), {"[entfernt]"})
        ereignisse = SystemEreignis.objects.filter(objekt=f"Dokument {nummer}")
        self.assertEqual(ereignisse.count(), 2)
        for e in ereignisse:
            self.assertEqual((e.details["titel"], e.details["sha256"]), ("[entfernt]", sha))
        v = DokumentVorgang.objects.get(dokument_id=nummer)
        self.assertEqual((v.sha256, v.datei), (sha, datei))
        self.assertEqual(nachholen()["liste_ergaenzt"], 1)
        # danach greift wieder der volle Schutz
        with self.assertRaises(DatabaseError), transaction.atomic():
            DokumentVorgang.objects.update(grund="geändert")

    def test_systemdokumente_bleiben(self):
        dok = self.hochladen(self.sabine)
        Dokument.objects.filter(pk=dok.pk).update(herkunft=Dokument.Herkunft.SYSTEM)
        r = client_fuer(self.mediziner).post(f"/api/dokumente/{dok.id}/umhaengen/",
                                             {"patient": self.bernd.id, "grund": "falscher Patient"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("gehören zu ihrem Plan", r.json()["fehler"])


class HinweiseStummschalten(Grundlage):
    """Hinweise mit „×“ wegklicken (Wunsch 07.10.2026, F119) und Grenzen für Befunde (F120)."""

    def setUp(self):
        self.c = client_fuer(self.mitarbeiter)
        self.p = Patient.objects.create(nachname="Ruhe", vorname="Rita",
                                        geburtsdatum=timezone.localdate() - timedelta(days=15000))

    def hinweise(self, patient=None):
        from .kennzahlen import kennzahlen
        akte = patient or self.p
        return kennzahlen([akte])[akte.id]

    def arten(self, patient=None):
        return {h["art"] for h in self.hinweise(patient)["hinweise"]}

    def test_akte_ohne_befunde_zeigt_labor_und_bia(self):
        self.assertIn("labor", self.arten())
        self.assertIn("bia", self.arten())

    def test_abgeschlossene_akte_ohne_hinweise(self):
        self.assertTrue({"versorger", "kontakt"} <= self.arten())
        Patient.objects.filter(pk=self.p.pk).update(abgeschlossen_am=timezone.localdate(),
                                                    abschluss_anlass=Patient.Abschlussanlass.THERAPIE_BEENDET)
        self.p.refresh_from_db()
        self.assertEqual(self.arten(), set())

    def test_wegklicken_fuer_sechs_monate(self):
        r = self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/",
                        {"art": "labor", "monate": 6, "grund": "beim Hausarzt angefordert"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        from .models import plus_monate
        self.assertEqual(r.json()["bis"], str(plus_monate(timezone.localdate(), 6)))
        werte = self.hinweise()
        self.assertNotIn("labor", {h["art"] for h in werte["hinweise"]})
        self.assertIn("labor", werte["hinweise_stumm"])
        self.assertIn("bia", {h["art"] for h in werte["hinweise"]})  # andere Hinweise bleiben

    def test_nicht_mehr_noetig_bleibt_ohne_frist(self):
        r = self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/",
                        {"art": "bia", "dauerhaft": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.json()["bis"])
        self.assertNotIn("bia", self.arten())

    def test_abgelaufene_ruhe_zeigt_den_hinweis_wieder(self):
        from .models import Hinweisruhe
        ruhe = Hinweisruhe.objects.create(patient=self.p, art="labor", bis=timezone.localdate() + timedelta(days=5),
                                         gesetzt_von=self.mitarbeiter)
        self.assertNotIn("labor", self.arten())
        Hinweisruhe.objects.filter(pk=ruhe.pk).update(bis=timezone.localdate() - timedelta(days=1))
        self.assertIn("labor", self.arten())

    def test_wieder_einschalten(self):
        self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/", {"art": "labor", "monate": 3}, format="json")
        r = self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/", {"art": "labor", "aufheben": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("labor", self.arten())
        # und danach wieder stummschaltbar (die eindeutige Regel gilt nur für laufende Einträge)
        r = self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/", {"art": "labor", "monate": 3}, format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_liste_zeigt_person_grund_und_frist(self):
        self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/",
                    {"art": "kontakt", "monate": 12, "grund": "Patient ist im Ausland"}, format="json")
        r = self.c.get(f"/api/patienten/{self.p.id}/hinweis-ruhe/")
        self.assertEqual(r.status_code, 200, r.content)
        eintrag = r.json()[0]
        self.assertEqual(eintrag["art_name"], "Kontakt fällig")
        self.assertEqual(eintrag["grund"], "Patient ist im Ausland")
        self.assertEqual(eintrag["gesetzt_von_name"], self.mitarbeiter.anzeigename)
        self.assertTrue(eintrag["laeuft"])

    def test_frist_muss_erlaubt_sein(self):
        r = self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/", {"art": "labor", "monate": 7}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

    def test_unbekannte_art_abgelehnt(self):
        r = self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/", {"art": "erfunden", "monate": 3}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

    def test_ohne_recht_nicht_erlaubt(self):
        c = client_fuer(self.betrachter)
        r = c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/", {"art": "labor", "monate": 3}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_nicht_loeschbar(self):
        from .models import Hinweisruhe
        ruhe = Hinweisruhe.objects.create(patient=self.p, art="labor", gesetzt_von=self.mitarbeiter)
        with self.assertRaises(PermissionError):
            ruhe.delete()

    def test_neue_frist_ersetzt_die_alte(self):
        """Nochmal wegklicken verlängert: die alte Stummschaltung endet, die neue tritt an ihre Stelle."""
        self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/", {"art": "labor", "monate": 3}, format="json")
        r = self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/", {"art": "labor", "monate": 12}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        liste = self.c.get(f"/api/patienten/{self.p.id}/hinweis-ruhe/").json()
        self.assertEqual([e["laeuft"] for e in liste], [True, False])
        self.assertNotIn("labor", self.arten())

    def test_datenbank_laesst_nur_eine_laufende_je_art_zu(self):
        from django.db import IntegrityError

        from .models import Hinweisruhe
        Hinweisruhe.objects.create(patient=self.p, art="labor", gesetzt_von=self.mitarbeiter)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Hinweisruhe.objects.create(patient=self.p, art="labor", gesetzt_von=self.mitarbeiter)

    def test_steht_im_verlauf_der_akte(self):
        self.c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/",
                    {"art": "labor", "monate": 3, "grund": "Termin steht"}, format="json")
        r = self.c.get(f"/api/patienten/{self.p.id}/verlauf/?bereich=hinweisruhe")
        self.assertEqual(r.status_code, 200, r.content)
        eintraege = r.json()
        self.assertTrue(eintraege, r.content)
        self.assertIn("Termin steht", eintraege[0]["beschreibung"])


class BefundGrenzwerte(Grundlage):
    """Ab wann ein Befund als zu alt gilt – einstellbar unter Vorlagen › Grenzwerte (Festlegung 07.10.2026, F120)."""

    def setUp(self):
        from befunde.models import BiaMessung, Laborbefund
        self.Laborbefund, self.BiaMessung = Laborbefund, BiaMessung
        self.p = Patient.objects.create(nachname="Alt", vorname="Albert",
                                        geburtsdatum=timezone.localdate() - timedelta(days=16000))

    def arten(self):
        from .kennzahlen import kennzahlen
        return {h["art"] for h in kennzahlen([self.p])[self.p.id]["hinweise"]}

    def test_standard_sind_zwoelf_monate(self):
        from stammdaten.models import Einstellungen
        e = Einstellungen.aktuell()
        self.assertEqual((e.labor_alter_warnung_monate, e.bia_alter_warnung_monate), (12, 12))

    def test_junger_befund_ohne_hinweis(self):
        self.Laborbefund.objects.create(patient=self.p, abgenommen_am=timezone.localdate() - timedelta(days=30))
        self.BiaMessung.objects.create(patient=self.p, gemessen_am=timezone.localdate() - timedelta(days=30))
        self.assertEqual(self.arten() & {"labor", "bia"}, set())

    def test_alter_befund_mit_hinweis(self):
        self.Laborbefund.objects.create(patient=self.p, abgenommen_am=timezone.localdate() - timedelta(days=500))
        self.BiaMessung.objects.create(patient=self.p, gemessen_am=timezone.localdate() - timedelta(days=500))
        self.assertEqual(self.arten() & {"labor", "bia"}, {"labor", "bia"})

    def test_grenze_wirkt(self):
        from stammdaten.models import Einstellungen
        self.Laborbefund.objects.create(patient=self.p, abgenommen_am=timezone.localdate() - timedelta(days=200))
        self.assertNotIn("labor", self.arten())
        e = Einstellungen.aktuell()
        e.labor_alter_warnung_monate = 6
        e.save()
        self.assertIn("labor", self.arten())

    def test_grenze_mindestens_ein_monat(self):
        c = client_fuer(self.admin)
        r = c.patch("/api/einstellungen/", {"labor_alter_warnung_monate": 0}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

    def test_abgeschlossene_akte_ohne_hinweis(self):
        # Akten abschließen dürfen Admins auch bei echten Akten (Festlegung 02.10.2026)
        c = client_fuer(self.admin)
        r = c.post(f"/api/patienten/{self.p.id}/abschliessen/", {"anlass": "therapie_beendet"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.arten() & {"labor", "bia"}, set())

    def test_prueflisten_filter_und_zahlen(self):
        c = client_fuer(self.mitarbeiter)
        r = c.get("/api/patienten/?pruefen=labor_faellig")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn(self.p.id, [x["id"] for x in r.json()["results"]])
        # weggeklickt verschwindet die Akte auch aus der Liste
        c.post(f"/api/patienten/{self.p.id}/hinweis-ruhe/", {"art": "labor", "dauerhaft": True}, format="json")
        r = c.get("/api/patienten/?pruefen=labor_faellig")
        self.assertNotIn(self.p.id, [x["id"] for x in r.json()["results"]])

    def test_startseite_zaehlt_mit(self):
        c = client_fuer(self.mitarbeiter)
        r = c.get("/api/startseite/")
        self.assertEqual(r.status_code, 200, r.content)
        pruefen = r.json()["pruefen"]
        self.assertGreaterEqual(pruefen["labor_faellig"], 1)
        self.assertEqual(pruefen["labor_monate"], 12)
        self.assertEqual(pruefen["bia_monate"], 12)
