"""Dokumentvorlagen und PDF-Erzeugung (F50, F51, F35, F37) gegen die echte Datenbank."""
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import timedelta

from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer
from infusionen.models import Infusionsplan
from infusionen.tests import praeparat
from patienten.models import Dokument, Patient

from .bloecke import STARTVORLAGEN, pruefe_bloecke
from .felder import Kontext
from .models import Dokumentvorlage
from .pdf import erzeuge_aus_vorlage

PDFTOTEXT = shutil.which("pdftotext")


def pdf_text(pdf: bytes, roh=False) -> str:
    """Text der PDF; ``roh`` = Reihenfolge wie im Inhaltsstrom (für das schräge Wasserzeichen)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf)
        f.flush()
        return subprocess.run([PDFTOTEXT, "-raw" if roh else "-layout", f.name, "-"], capture_output=True, text=True,
                              check=True).stdout


def wasserzeichen(pdf: bytes) -> str:
    return re.sub(r"\s+", "", pdf_text(pdf, roh=True))


def kompakt(text: str) -> str:
    """Ohne Leerraum – das schräge Wasserzeichen kommt beim Auslesen oft Zeichen für Zeichen."""
    return re.sub(r"\s+", "", text)


class Vorlagen(Grundlage):
    def testpatient_mit_plan(self, freigeben=False):
        p = Patient(nachname="Probe", vorname="Paula", geburtsdatum=timezone.localdate() - timedelta(days=19000))
        p.ist_test = True
        p.save()
        m = client_fuer(self.mitarbeiter)
        m.post("/api/gewichte/", {"patient": p.id, "gewicht_kg": "60.0"}, format="json")
        c = client_fuer(self.mediziner)
        e = c.post("/api/infusionsplaene/entwurf/", {"patient": p.id}, format="json").json()
        r = c.patch(f"/api/infusionsplaene/{e['id']}/", {
            "basis_praeparat": praeparat("Sterofundin").id, "basis_ml": 500,
            "glucose_praeparat": praeparat("Glucose", "70 %").id, "glucose_g": "160",
            "aminosaeuren_praeparat": praeparat("Glamin").id, "aminosaeuren_g": "80",
            "lipide_praeparat": praeparat("Clinoleic").id, "lipide_g": "60",
            "natrium_mmol": "78", "kalium_mmol": "40", "calcium_mmol": "9", "magnesium_mmol": "6",
            "laufzeit_h": "12", "pantozol_stufe": 1, "pantozol_tage": 5,
            "bemerkung": "<p>Start der <strong>heimparenteralen</strong> Ernährung</p>"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        if freigeben:
            self.assertEqual(c.post(f"/api/infusionsplaene/{e['id']}/freigeben/").status_code, 200)
        return p, Infusionsplan.objects.get(pk=e["id"])

    def test_startvorlagen_sind_gueltig_und_rechte(self):
        for art, bloecke in STARTVORLAGEN.items():
            with self.subTest(art=art):
                self.assertEqual(pruefe_bloecke(art, bloecke), [])
        r = client_fuer(self.admin).get("/api/vorlagen/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([(v["art"], v["aktiv"]["version"], v["entwurf"]) for v in r.json()],
                         [("infusionsplan", 1, None), ("patientendatenblatt", 1, None)])
        self.assertEqual(client_fuer(self.betrachter).get("/api/vorlagen/").status_code, 403)
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/vorlagen/infusionsplan/").status_code, 200)
        d = client_fuer(self.mediziner).get("/api/vorlagen/infusionsplan/").json()
        self.assertIn("Plan.Rate", [f["name"] for f in d["felder"]])
        self.assertIn("Patient.Diagnose", [f["name"] for f in client_fuer(self.admin)
                                           .get("/api/vorlagen/patientendatenblatt/").json()["felder"]])
        self.assertEqual(client_fuer(self.admin).get("/api/vorlagen/unbekannt/").status_code, 404)

    def test_entwurf_pruefen_veroeffentlichen_unveraenderlich(self):
        c = client_fuer(self.mitarbeiter)
        url = "/api/vorlagen/infusionsplan/entwurf/"
        start = c.get(url).json()
        self.assertEqual([start["ist_entwurf"], start["grundlage"]], [False, 1])
        bloecke = start["bloecke"]
        # Platzhalter nur aus der festen Liste, Bausteine und Optionen geprüft
        faelle = [
            ([*bloecke, {"id": "x", "typ": "text", "text": "Hallo {{Patient.Kontostand}}"}], "unbekanntes Datenfeld „Patient.Kontostand“"),
            ([*bloecke, {"id": "y", "typ": "fusszeile", "text": "doppelt"}], "Fußzeile darf höchstens einmal vorkommen."),
            ([*bloecke, {"id": "z", "typ": "skript"}], "unbekannter Bausteintyp"),
            ([*bloecke, {"id": "w", "typ": "text", "text": "x", "optionen": {"schrift": "riesig"}}], "Option „schrift“ ungültig"),
            ([*bloecke, {"id": "v", "typ": "tabelle", "quelle": "termine"}], "unbekannte Tabelle"),
            ([], "mindestens einen Block"),
        ]
        for daten, meldung in faelle:
            with self.subTest(meldung=meldung):
                r = c.put(url, {"bloecke": daten}, format="json")
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn(meldung, " ".join(r.json()["bloecke"]))
        neu = [*bloecke[:-1], {"id": "gruss", "typ": "text", "bezeichnung": "Gruß", "text": "Ihr Team · {{Heute}}",
                               "optionen": {"ausrichtung": "rechts", "kursiv": True}}, bloecke[-1]]
        r = c.put(url, {"bloecke": neu}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(c.get(url).json()["ist_entwurf"], True)
        self.assertEqual(client_fuer(self.betrachter).put(url, {"bloecke": neu}, format="json").status_code, 403)
        # Veröffentlichen: neue Version 2, v1 abgelöst und erhalten
        r = c.post("/api/vorlagen/infusionsplan/veroeffentlichen/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([r.json()["aktiv"]["version"], r.json()["entwurf"]],
                         [2, None])
        self.assertEqual([(v["version"], v["status"]) for v in r.json()["versionen"]], [(2, "aktiv"), (1, "abgeloest")])
        self.assertEqual(c.get("/api/vorlagen/infusionsplan/versionen/1/").json()["bloecke"], bloecke)
        self.assertEqual(c.post("/api/vorlagen/infusionsplan/veroeffentlichen/").status_code, 400)
        # veröffentlichte Versionen sind unveränderlich – im Modell und in der Datenbank
        v2 = Dokumentvorlage.objects.get(art="infusionsplan", version=2)
        v2.bloecke = []
        with self.assertRaises(PermissionError):
            v2.save()
        with self.assertRaises(PermissionError):
            v2.delete()
        for sql in ["UPDATE vorlagen_dokumentvorlage SET bloecke = '[]' WHERE id = %s",
                    "DELETE FROM vorlagen_dokumentvorlage WHERE id = %s"]:
            with self.subTest(sql=sql.split()[0]), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(sql, [v2.id])
        # Entwurf verwerfen
        c.put(url, {"bloecke": bloecke}, format="json")
        self.assertEqual(c.delete(url).status_code, 204)
        self.assertIsNone(Dokumentvorlage.entwurf_von("infusionsplan"))

    def test_vorschau_nur_mit_testpatient(self):
        c = client_fuer(self.admin)
        url = "/api/vorlagen/infusionsplan/vorschau/"
        self.assertEqual(c.post(url, {"patient": self.patient.id}, format="json").status_code, 400)  # echte Akte
        p, _ = self.testpatient_mit_plan()
        r = c.post(url, {"patient": p.id}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF-"))
        r = c.post("/api/vorlagen/patientendatenblatt/vorschau/", {"patient": p.id}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        if PDFTOTEXT:
            text = pdf_text(r.content)
            for erwartet in ["Patientendatenblatt", "Probe, Paula", "60 kg am", "1/1", "Spendenkonto"]:
                self.assertIn(kompakt(erwartet), kompakt(text))
            self.assertIn("ENTWURF", wasserzeichen(r.content))

    @unittest.skipUnless(PDFTOTEXT, "pdftotext fehlt")
    def test_inhalt_des_plan_pdfs(self):
        p, plan = self.testpatient_mit_plan()
        pdf, version = erzeuge_aus_vorlage("infusionsplan", Kontext(patient=p, plan=plan), wasserzeichen="TESTDATEN")
        self.assertEqual(version, 1)
        text = pdf_text(pdf)
        for erwartet in ["Empfehlung eines Infusionsplans", "Probe, Paula", "Sterofundin", "Glamin 13,4 %", "80 g",
                         "1.509 kcal", "2.100 ml", "500 ml", "2.600 ml", "216,7 ml/h", "78 mmol", "heimparenteralen",
                         "Pantozol® Kurzinfusion 1 Amp. 40 mg in 50 ml Trägerlösung · 1-0-1",
                         "Patienten-Nr.: 9", "Infusionsplan-Nr.:", "Volumen im Mischbeutel", "Laufmenge je Stunde",
                         "Deutsche Stiftung Krankheitsbedingte Mangelernährung", "Telefon 0251 98 11 400",
                         "Spendenkonto", "1/1", "Maschinell erstellt, geprüft und freigegeben von"]:
            self.assertIn(kompakt(erwartet), kompakt(text))
        self.assertIn("TESTDATEN", wasserzeichen(pdf))
        self.assertNotIn("{{", text)

    def test_freigabe_speichert_pdf_mit_pruefsumme(self):
        p, plan = self.testpatient_mit_plan(freigeben=True)
        plan.refresh_from_db()
        self.assertEqual(len(plan.pdf_sha256), 64)
        self.assertEqual(plan.vorlage_version, 1)
        dok = Dokument.objects.get(datei=plan.pdf_datei)
        self.assertEqual([dok.herkunft, dok.typ.wert, dok.mime, dok.sha256, dok.patient_id],
                         ["system", "Infusionsplan", "application/pdf", plan.pdf_sha256, p.id])
        self.assertTrue(dok.pfad.read_bytes().startswith(b"%PDF-"))
        c = client_fuer(self.mitarbeiter)
        r = c.get(f"/api/infusionsplaene/{plan.id}/pdf/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([r["X-EPM-Pruefung"], r["X-EPM-Vorlage-Version"]], ["ok", "1"])
        self.assertEqual(r["X-Accel-Redirect"], "/_geschuetzt/dokumente/" + plan.pdf_datei)
        if PDFTOTEXT:
            text = pdf_text(dok.pfad.read_bytes())
            self.assertIn("TESTDATEN", wasserzeichen(dok.pfad.read_bytes()))
            self.assertIn(timezone.localdate().strftime("%d.%m.%Y"), text)  # Freigabedatum
            self.assertNotIn("ENTWURF", wasserzeichen(dok.pfad.read_bytes()))
        # eine neue Vorlagenversion ändert gespeicherte PDFs nicht
        a = client_fuer(self.admin)
        bloecke = a.get("/api/vorlagen/infusionsplan/entwurf/").json()["bloecke"]
        a.put("/api/vorlagen/infusionsplan/entwurf/", {"bloecke": bloecke[:-1]}, format="json")
        a.post("/api/vorlagen/infusionsplan/veroeffentlichen/")
        self.assertEqual(c.get(f"/api/infusionsplaene/{plan.id}/pdf/")["X-EPM-Pruefung"], "ok")
        # verändert jemand die Datei, meldet die Prüfung „abweichend“
        with open(dok.pfad, "ab") as f:
            f.write(b"\n% veraendert")
        self.assertEqual(c.get(f"/api/infusionsplaene/{plan.id}/pdf/")["X-EPM-Pruefung"], "abweichend")
        # Entwurf ohne PDF
        e = client_fuer(self.mediziner).post("/api/infusionsplaene/entwurf/", {"patient": p.id}, format="json").json()
        self.assertEqual(c.get(f"/api/infusionsplaene/{e['id']}/pdf/").status_code, 404)
        # die Pdf-Felder freigegebener Pläne sind wie alle Werte gesperrt
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("UPDATE infusionen_infusionsplan SET pdf_sha256 = 'x' WHERE id = %s", [plan.id])


class WeiterePdfs(Grundlage):
    testpatient_mit_plan = Vorlagen.testpatient_mit_plan
    def test_akte_und_verlauf_als_pdf(self):
        from audit.models import SystemEreignis

        p, _ = self.testpatient_mit_plan(freigeben=True)
        c = client_fuer(self.betrachter)  # lesen genügt
        r = c.get(f"/api/patienten/{p.id}/pdf/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.content.startswith(b"%PDF-"))
        self.assertTrue(SystemEreignis.objects.filter(art="export", details__was="Akte").exists())
        r = c.get(f"/api/patienten/{p.id}/verlauf/pdf/?bereich=gewichte")
        self.assertEqual(r.status_code, 200, r.content)
        if PDFTOTEXT:
            text = pdf_text(r.content)
            for erwartet in ["Verlauf der Akte", "Probe, Paula", "Bereich Gewicht", "Gewicht", "angelegt"]:
                self.assertIn(kompakt(erwartet), kompakt(text))
            self.assertIn("TESTDATEN", wasserzeichen(r.content))
            self.assertIn("1.509kcal·2.600ml·12h", kompakt(pdf_text(c.get(f"/api/patienten/{p.id}/pdf/").content)))  # aktueller Plan im Datenblatt
        # auch abgeschlossene Akten lassen sich ausgeben
        Patient.objects.filter(pk=p.pk).update(abgeschlossen_am=timezone.localdate(), abschluss_anlass="therapie_beendet")
        self.assertEqual(c.get(f"/api/patienten/{p.id}/pdf/").status_code, 200)
        self.assertTrue(SystemEreignis.objects.filter(art="export", details__was="Verlauf").exists())

    def test_audit_log_als_pdf(self):
        a = client_fuer(self.admin)
        a.post("/api/benutzer/", {"username": "neu.pdf", "first_name": "Neu", "last_name": "Pdf", "rolle": "mitarbeiter"},
               format="json")
        r = a.get("/api/protokoll/pdf/?gruppe=benutzer")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.content.startswith(b"%PDF-"))
        if PDFTOTEXT:
            text = pdf_text(r.content)
            self.assertIn("Audit-Log", text)
            self.assertIn("neu.pdf", text)
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/protokoll/pdf/").status_code, 403)
        self.assertEqual(a.get("/api/protokoll/pdf/?gruppe=unbekannt").status_code, 400)

    def test_zugangsblatt(self):
        a = client_fuer(self.admin)
        r = a.post("/api/benutzer/", {"username": "zugang.test", "first_name": "Zora", "last_name": "Zugang",
                                      "rolle": "mitarbeiter"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        uid, kennwort = r.json()["id"], r.json()["einmal_kennwort"]
        url = f"/api/benutzer/{uid}/zugangsblatt/"
        self.assertEqual(a.post(url, {"kennwort": "falsch"}, format="json").status_code, 400)
        self.assertEqual(client_fuer(self.mitarbeiter).post(url, {"kennwort": kennwort}, format="json").status_code, 403)
        r = a.post(url, {"kennwort": kennwort}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        if PDFTOTEXT:
            text = pdf_text(r.content)
            for erwartet in ["Zugang zu EPM", "zugang.test", kennwort, "Authenticator", "Notfall-Codes"]:
                self.assertIn(kompakt(erwartet), kompakt(text))
        from accounts.models import User

        User.objects.filter(pk=uid).update(muss_kennwort_aendern=False)
        self.assertEqual(a.post(url, {"kennwort": kennwort}, format="json").status_code, 400)
