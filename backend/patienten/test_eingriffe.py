"""Eigene Reiter der RGC (Wunsch 21.11.2026): Eingriffe (Therapie/Operation mit OPS- und ICD-Code, Übernahme der
Diagnose mit der Genehmigung) und Dokumente je Dokumenttyp (OP-Bericht, Röntgen, Überweisung, Einweisung)."""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from audit.schutz import wartungsmodus
from epm.pruefhilfen import Grundlage, client_fuer
from stammdaten.models import Auswahlwert, Opsvorlage, ops_codes_ordnen

from .datenschutz import akten_entfernen
from .models import Diagnose, Dokument, Eingriff, Patient

URL = "/api/eingriffe/"


class EingriffeTest(Grundlage):
    def anlegen(self, client=None, **extra):
        c = client or client_fuer(self.mitarbeiter)
        daten = {"patient": self.patient.id, "art": "operation", "bezeichnung": "Dünndarmresektion",
                 "ops_codes": "5-455.01; 5-469.20", "icd_code": "k91.2", "diagnose_bezeichnung": "Kurzdarmsyndrom",
                 "kennzeichen": "G", **extra}
        return c.post(URL, daten, format="json")

    def test_ops_codes(self):
        self.assertEqual(ops_codes_ordnen("5-455.01; 5-469.20 5-455.01"), ("5-455.01, 5-469.20", []))
        self.assertEqual(ops_codes_ordnen("5-46A.1, 8-831.0"), ("5-46a.1, 8-831.0", []))
        self.assertEqual(ops_codes_ordnen("K91.2, 5455")[1], ["k91.2", "5455"])

    def test_beantragt_ohne_diagnose(self):
        r = self.anlegen()
        self.assertEqual(r.status_code, 201, r.content)
        e = r.json()
        self.assertEqual((e["status"], e["ops_codes"], e["icd_code"], e["diagnose"], e["genehmigt_am"]),
                         ("beantragt", "5-455.01, 5-469.20", "K91.2", None, None))
        self.assertIn("firma_kurz", e)
        self.assertFalse(Diagnose.objects.filter(patient=self.patient).exists())
        kopf = client_fuer(self.mitarbeiter).get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual(kopf["zaehler"]["eingriffe"], 1)

    def test_genehmigt_uebernimmt_diagnose(self):
        e = self.anlegen().json()
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"{URL}{e['id']}/", {"status": "genehmigt", "genehmigung": "AOK, Az. 12/345"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        e = r.json()
        self.assertEqual(e["genehmigt_am"], timezone.localdate().isoformat())
        self.assertEqual(e["diagnose_anzeige"], "Kurzdarmsyndrom [K91.2G]")
        d = Diagnose.objects.get(patient=self.patient)
        self.assertEqual((d.icd_code, d.kennzeichen, d.aktiv, d.notiz),
                         ("K91.2", "G", True, "aus Eingriff: Dünndarmresektion"))
        # weitere Änderungen legen keine zweite Diagnose an
        r = c.patch(f"{URL}{e['id']}/", {"status": "durchgefuehrt"}, format="json")
        self.assertEqual((r.status_code, r.json()["datum"]), (200, timezone.localdate().isoformat()))
        self.assertEqual(Diagnose.objects.filter(patient=self.patient).count(), 1)
        # ein zweiter Eingriff mit demselben ICD-Code verknüpft die vorhandene Diagnose
        r = self.anlegen(bezeichnung="Darmverlängerung (STEP)", ops_codes="5-467.5", status="genehmigt")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["diagnose"], d.id)
        self.assertEqual(Diagnose.objects.filter(patient=self.patient).count(), 1)
        # Verlauf: angelegt, Diagnose übernommen, Status
        verlauf = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=eingriffe").json()
        aktionen = [x["aktion"] for x in verlauf if x["objekt_id"] == e["id"]]
        self.assertEqual(aktionen, ["durchgeführt", "Diagnose übernommen", "genehmigt", "angelegt"])
        self.assertIn("OPS 5-455.01, 5-469.20", verlauf[-1]["beschreibung"])
        # die Diagnose steht auch im Verlauf der Diagnosen
        self.assertTrue(c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=diagnosen").json())

    def test_durchgefuehrt_direkt_und_kennzeichen(self):
        gestern = (timezone.localdate() - timedelta(days=1)).isoformat()
        r = self.anlegen(status="durchgefuehrt", datum=gestern, icd_code="Z90.4", kennzeichen="Z",
                         diagnose_bezeichnung="Verlust von Teilen des Verdauungstraktes")
        self.assertEqual(r.status_code, 201, r.content)
        d = Diagnose.objects.get(pk=r.json()["diagnose"])
        self.assertEqual((d.kennzeichen, d.seit.isoformat()), ("Z", gestern))

    def test_abgelehnt_und_entfernt_ohne_diagnose(self):
        self.assertEqual(self.anlegen(status="abgelehnt").status_code, 201)
        e = self.anlegen().json()
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.patch(f"{URL}{e['id']}/", {"aktiv": False}, format="json").status_code, 200)
        self.assertEqual(c.patch(f"{URL}{e['id']}/", {"status": "genehmigt"}, format="json").status_code, 200)
        self.assertFalse(Diagnose.objects.exists())
        verlauf = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=eingriffe").json()
        self.assertIn("entfernt", [x["aktion"] for x in verlauf])

    def test_pruefungen(self):
        r = self.anlegen(diagnose_bezeichnung=" ", bezeichnung="")
        self.assertEqual((r.status_code, set(r.json())), (400, {"diagnose_bezeichnung", "bezeichnung"}))
        r = self.anlegen(ops_codes="5-455.01, Darm", icd_code="91.2")
        self.assertEqual((r.status_code, set(r.json())), (400, {"ops_codes", "icd_code"}))
        self.assertIn("darm", r.json()["ops_codes"][0])
        morgen = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertIn("datum", self.anlegen(status="durchgefuehrt", datum=morgen).json())
        self.assertIn("genehmigt_am", self.anlegen(genehmigt_am=morgen).json())
        # geplant in der Zukunft ist erlaubt
        self.assertEqual(self.anlegen(datum=morgen).status_code, 201)
        # ohne OPS-Code geht es (z. B. Therapie ohne Prozedur)
        self.assertEqual(self.anlegen(art="therapie", ops_codes="", bezeichnung="Teduglutid").status_code, 201)

    def test_ops_liste_waechst(self):
        self.anlegen(ops_codes="5-455.01")
        self.anlegen(bezeichnung="Mehrere", ops_codes="5-455.01, 5-469.20")  # mehrdeutig: nicht in die Liste
        self.assertEqual(list(Opsvorlage.objects.values_list("ops_code", "bezeichnung")),
                         [("5-455.01", "Dünndarmresektion")])
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(len(c.get("/api/opsliste/?aktiv=true").json()), 1)

    def test_dokument_der_akte(self):
        andere = Patient.objects.create(nachname="Anders", vorname="Ute", geburtsdatum="1970-01-01")
        fremd = Dokument.objects.create(patient=andere, titel="fremd", datei="x/fremd.pdf", originalname="f.pdf",
                                        mime="application/pdf", groesse=1, sha256="0" * 64)
        self.assertIn("dokument", self.anlegen(dokument=fremd.id).json())
        eigen = Dokument.objects.create(patient=self.patient, titel="OP-Bericht", datei="x/eigen.pdf",
                                        originalname="e.pdf", mime="application/pdf", groesse=1, sha256="1" * 64)
        r = self.anlegen(dokument=eigen.id)
        self.assertEqual((r.status_code, r.json()["dokument_titel"]), (201, "OP-Bericht"))

    def test_rechte_und_kein_loeschen(self):
        e = self.anlegen().json()
        b = client_fuer(self.betrachter)
        self.assertEqual(b.get(f"{URL}?patient={self.patient.id}").status_code, 200)
        self.assertEqual(self.anlegen(b).status_code, 403)
        self.assertEqual(b.patch(f"{URL}{e['id']}/", {"status": "genehmigt"}, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.mitarbeiter).delete(f"{URL}{e['id']}/").status_code, 405)
        with self.assertRaises(PermissionError):
            Eingriff.objects.get(pk=e["id"]).delete()

    def test_akte_entfernen(self):
        e = self.anlegen(status="genehmigt").json()
        self.assertTrue(Eingriff.history.filter(id=e["id"]).exists())
        with wartungsmodus():
            akten_entfernen([self.patient.id])
        self.assertFalse(Eingriff.history.filter(id=e["id"]).exists())
        self.assertFalse(Diagnose.history.filter(patient_id=self.patient.id).exists())

    def test_akte_kopie_pdf(self):
        from vorlagen.listen import aktenkopie_pdf

        self.anlegen()
        self.assertTrue(aktenkopie_pdf(self.patient).startswith(b"%PDF"))


class DokumentReiterTest(Grundlage):
    def test_typen_mit_kennung(self):
        kennungen = dict(Auswahlwert.objects.filter(liste="dokumenttyp").exclude(kennung="")
                         .values_list("kennung", "wert"))
        self.assertEqual(kennungen, {"op_bericht": "OP-Bericht", "radiologie": "Röntgen / Radiologie",
                                     "ueberweisung": "Überweisung", "einweisung": "Stationäre Einweisung"})
        c = client_fuer(self.mitarbeiter)
        werte = c.get("/api/auswahlwerte/?liste=dokumenttyp").json()
        self.assertIn("op_bericht", {w["kennung"] for w in werte})
        # Kennung ist nicht änderbar, der Name schon
        op = Auswahlwert.objects.get(kennung="op_bericht")
        c.patch(f"/api/auswahlwerte/{op.id}/", {"kennung": "x", "wert": "OP-Bericht (Klinik)"}, format="json")
        op.refresh_from_db()
        self.assertEqual((op.kennung, op.wert), ("op_bericht", "OP-Bericht (Klinik)"))

    def test_hochladen_und_zaehler(self):
        roentgen = Auswahlwert.objects.get(kennung="radiologie")
        c = client_fuer(self.mitarbeiter)
        datei = SimpleUploadedFile("thorax.txt", "Röntgen Thorax: unauffällig".encode(), content_type="text/plain")
        r = c.post("/api/dokumente/", {"patient": self.patient.id, "datei": datei, "typ": roentgen.id,
                                       "titel": "Thorax"}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        liste = c.get(f"/api/dokumente/?patient={self.patient.id}&typ={roentgen.id}").json()
        self.assertEqual([d["titel"] for d in liste.get("results", liste)], ["Thorax"])
        kopf = c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual(kopf["zaehler"]["dokumentarten"], {"radiologie": 1})

    def test_vorhandener_typ_wird_verwendet(self):
        """Die Datenmigration übernimmt einen von Hand angelegten Typ wie „Röntgen“, statt einen zweiten anzulegen."""
        from importlib import import_module

        from django.apps import apps

        mig = import_module("stammdaten.migrations.0029_dokumenttypen_rgc")
        Auswahlwert.objects.filter(liste="dokumenttyp").update(kennung="")
        Auswahlwert.objects.filter(liste="dokumenttyp", wert="Röntgen / Radiologie").update(wert="Röntgen alt-entfernt")
        haendisch = Auswahlwert.objects.create(liste="dokumenttyp", wert="Röntgen")
        mig.anlegen(apps, None)
        haendisch.refresh_from_db()
        self.assertEqual(haendisch.kennung, "radiologie")
        self.assertEqual(Auswahlwert.objects.filter(liste="dokumenttyp", kennung="radiologie").count(), 1)


