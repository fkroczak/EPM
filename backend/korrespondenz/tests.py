"""Korrespondenz der Akte (14.10.2026): Status, Rechte, Unveränderlichkeit, Scoping, PDF mit Prüfsumme, Verlauf."""
import hashlib
from datetime import timedelta

from django.db import DatabaseError, transaction
from django.utils import timezone

from accounts.models import Mitgliedschaft, Rolle
from audit.models import SystemEreignis
from audit.schutz import wartungsmodus
from epm.pruefhilfen import Grundlage, benutzer, client_fuer, echte_anmeldung, mit_zweitem_faktor
from infusionen.models import Infusionsplan
from infusionen.tests import praeparat
from patienten.datenschutz import akten_entfernen
from patienten.models import Diagnose, Dokument, Gewichtsmessung, Medikament, Patient, PatientFirma, Termin
from stammdaten.models import Firma
from vorlagen.felder import FELDER, Kontext
from vorlagen.tests import kompakt, pdf_text

from .models import Schreiben


class KorrespondenzTest(Grundlage):
    def entwurf(self, client=None, patient=None, erwartet=201, **extra):
        c = client or client_fuer(self.mitarbeiter)
        daten = {"patient": (patient or self.patient).id, "vorlage": "patientenaufnahme", "titel": "Anforderung Befunde",
                 "empfaenger": "Hausarzt Dr. Hausmann", "text": "Bitte senden Sie uns die letzten Laborwerte.", **extra}
        r = c.post("/api/korrespondenz/", daten, format="json")
        self.assertEqual(r.status_code, erwartet, r.content)
        return r.json()

    def freigeben(self, d, client=None):
        r = (client or client_fuer(self.mediziner)).post(f"/api/korrespondenz/{d['id']}/freigeben/")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    # ---------------------------------------------------------------- Entwurf
    def test_entwurf_anlegen_aendern_loeschen(self):
        d = self.entwurf()
        self.assertEqual((d["status"], d["vorlage_name"]), ("entwurf", "Patientenaufnahme (benötigte Unterlagen)"))
        self.assertEqual(d["firma_kurz"], None)
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"/api/korrespondenz/{d['id']}/", {"titel": "  Anforderung   Laborwerte "}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["titel"], "Anforderung Laborwerte")
        self.assertEqual(c.get(f"/api/korrespondenz/?patient={self.patient.id}").json()[0]["id"], d["id"])
        self.assertEqual(self.patient.korrespondenz.count(), 1)
        r = c.delete(f"/api/korrespondenz/{d['id']}/")
        self.assertEqual(r.status_code, 204, r.content)
        self.assertFalse(Schreiben.objects.exists())
        self.assertTrue(SystemEreignis.objects.filter(art="korrespondenz", details__aktion="Entwurf gelöscht").exists())

    def test_pflichtangaben(self):
        r = client_fuer(self.mitarbeiter).post("/api/korrespondenz/", {"patient": self.patient.id, "vorlage": "gibt-es-nicht",
                                                                       "titel": "X"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("vorlage", r.json())
        r = client_fuer(self.mitarbeiter).post("/api/korrespondenz/", {"patient": self.patient.id,
                                                                       "vorlage": "patientenaufnahme", "titel": " "},
                                               format="json")
        self.assertIn("titel", r.json())
        # Terminbestätigung braucht einen Termin der eigenen Akte
        self.assertIn("termin", self.entwurf(vorlage="terminbestaetigung", erwartet=400))
        anderer = Patient.objects.create(nachname="Anders", vorname="Otto", geburtsdatum="1960-01-01")
        fremd = Termin.objects.create(patient=anderer, art=Termin.Art.PRAXISTERMIN, faellig_am=timezone.localdate())
        self.assertIn("termin", self.entwurf(vorlage="terminbestaetigung", termin=fremd.id, erwartet=400))
        eigen = Termin.objects.create(patient=self.patient, art=Termin.Art.PRAXISTERMIN,
                                      faellig_am=timezone.localdate() + timedelta(days=2))
        d = self.entwurf(vorlage="terminbestaetigung", termin=eigen.id)
        self.assertTrue(d["termin_text"].startswith(f"{eigen.faellig_am:%d.%m.%Y}"))
        self.assertIn("optionen", self.entwurf(vorlage="reisebescheinigung", optionen={"tage": 5000}, erwartet=400))

    def test_vorschau_ohne_speichern(self):
        r = client_fuer(self.mitarbeiter).post("/api/korrespondenz/vorschau/", {
            "patient": self.patient.id, "vorlage": "patientenaufnahme", "titel": "Anforderung",
            "text": "Freitext für die Vorschau"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("FreitextfürdieVorschau", kompakt(pdf_text(r.content)))
        self.assertIn("ENTWURF", kompakt(pdf_text(r.content, roh=True)))
        self.assertFalse(Schreiben.objects.exists())

    # ---------------------------------------------------------------- Freigabe
    def test_mitarbeiter_darf_nicht_freigeben(self):
        d = self.entwurf()
        r = client_fuer(self.mitarbeiter).post(f"/api/korrespondenz/{d['id']}/freigeben/")
        self.assertEqual(r.status_code, 403, r.content)
        self.assertIn("Schreiben freigeben", r.json()["detail"])
        self.assertEqual(Schreiben.objects.get(pk=d["id"]).status, "entwurf")

    def test_freigabe_erzeugt_pdf_mit_pruefsumme_und_sperrt(self):
        Diagnose.objects.create(patient=self.patient, bezeichnung="Kurzdarmsyndrom", icd_code="K91.2")
        d = self.entwurf()
        f = self.freigeben(d)
        self.assertEqual(f["status"], "freigegeben")
        self.assertIn(f"Freigegeben von {self.mediziner.anzeigename} am", f["freigabevermerk"])
        self.assertEqual(len(f["pdf_sha256"]), 64)
        self.assertEqual(f["vorlage_version"], 1)
        s = Schreiben.objects.get(pk=d["id"])
        self.assertIn("korrespondenz_text", [b["id"] for b in s.bloecke])  # Freitext vor dem Gruß eingefügt
        dok = Dokument.objects.get(pk=f["dokument"])
        self.assertEqual((dok.herkunft, dok.mime, dok.sha256), (Dokument.Herkunft.SYSTEM, "application/pdf", f["pdf_sha256"]))
        self.assertEqual(hashlib.sha256(dok.pfad.read_bytes()).hexdigest(), f["pdf_sha256"])
        # die gespeicherte PDF kommt unverändert zurück und enthält den Freitext
        c = client_fuer(self.mitarbeiter)
        r = c.get(f"/api/korrespondenz/{d['id']}/pdf/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(hashlib.sha256(r.content).hexdigest(), f["pdf_sha256"])
        self.assertIn("letztenLaborwerte", kompakt(pdf_text(r.content)))
        # unveränderlich: API und Datenbank
        self.assertEqual(c.patch(f"/api/korrespondenz/{d['id']}/", {"titel": "anders"}, format="json").status_code, 403)
        self.assertEqual(c.delete(f"/api/korrespondenz/{d['id']}/").status_code, 403)
        self.assertEqual(client_fuer(self.mediziner).post(f"/api/korrespondenz/{d['id']}/freigeben/").status_code, 400)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                Schreiben.objects.filter(pk=d["id"]).update(titel="am Modell vorbei")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                Schreiben.objects.filter(pk=d["id"]).delete()
        self.assertTrue(SystemEreignis.objects.filter(art="korrespondenz", details__aktion="freigegeben",
                                                      details__sha256=f["pdf_sha256"]).exists())
        # Prüfsumme wird beim Öffnen geprüft
        dok.pfad.write_bytes(b"%PDF-1.4 verfaelscht")
        self.assertEqual(c.get(f"/api/korrespondenz/{d['id']}/pdf/").status_code, 409)

    def test_entwurf_pdf_ist_vorschau(self):
        d = self.entwurf()
        r = client_fuer(self.betrachter).get(f"/api/korrespondenz/{d['id']}/pdf/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("ENTWURF", kompakt(pdf_text(r.content, roh=True)))

    # ---------------------------------------------------------------- Versand
    def test_versand_nur_nach_freigabe(self):
        d = self.entwurf()
        c = client_fuer(self.mitarbeiter)
        heute = timezone.localdate()
        r = c.post(f"/api/korrespondenz/{d['id']}/versendet/", {"versandweg": "post", "versendet_am": f"{heute}"},
                   format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.freigeben(d)
        r = c.post(f"/api/korrespondenz/{d['id']}/versendet/", {"versandweg": "brieftaube", "versendet_am": f"{heute}"},
                   format="json")
        self.assertIn("versandweg", r.json())
        r = c.post(f"/api/korrespondenz/{d['id']}/versendet/",
                   {"versandweg": "fax", "versendet_am": f"{heute + timedelta(days=1)}"}, format="json")
        self.assertIn("versendet_am", r.json())
        r = c.post(f"/api/korrespondenz/{d['id']}/versendet/",
                   {"versandweg": "fax", "versendet_am": f"{heute}", "versand_notiz": "an 0251 123"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        v = r.json()
        self.assertEqual((v["status"], v["versandweg_name"], v["versand_notiz"]), ("versendet", "Fax", "an 0251 123"))
        self.assertEqual(c.post(f"/api/korrespondenz/{d['id']}/versendet/", {"versandweg": "post",
                                                                            "versendet_am": f"{heute}"},
                                format="json").status_code, 400)
        # auch versendet unveränderlich
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                Schreiben.objects.filter(pk=d["id"]).update(versand_notiz="nachträglich")
        self.assertEqual(c.patch(f"/api/korrespondenz/{d['id']}/", {"titel": "x"}, format="json").status_code, 403)

    def test_kopieren_als_neuer_entwurf(self):
        d = self.entwurf()
        self.freigeben(d)
        r = client_fuer(self.mitarbeiter).post(f"/api/korrespondenz/{d['id']}/kopieren/")
        self.assertEqual(r.status_code, 201, r.content)
        k = r.json()
        self.assertEqual((k["status"], k["kopie_von"], k["titel"], k["text"]),
                         ("entwurf", d["id"], d["titel"], d["text"]))
        self.assertIsNone(k["dokument"])

    def test_verlauf_und_historie(self):
        d = self.entwurf()
        c = client_fuer(self.mitarbeiter)
        c.patch(f"/api/korrespondenz/{d['id']}/", {"empfaenger": "Klinikum Nord"}, format="json")
        self.freigeben(d)
        c.post(f"/api/korrespondenz/{d['id']}/versendet/", {"versandweg": "email",
                                                           "versendet_am": f"{timezone.localdate()}"}, format="json")
        v = c.get(f"/api/korrespondenz/{d['id']}/verlauf/").json()
        self.assertEqual([e["aktion"] for e in v], ["als versendet vermerkt", "freigegeben", "geändert", "angelegt"])
        self.assertEqual((v[0]["person"], v[1]["person"]), (self.mitarbeiter.anzeigename, self.mediziner.anzeigename))
        self.assertIn("empfaenger", [a["feld"] for a in v[2]["aenderungen"]])
        akte = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=korrespondenz").json()
        self.assertEqual(len(akte), 4)
        self.assertIn("versendet am", akte[0]["beschreibung"])
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]["zaehler"]["korrespondenz"], 1)

    # ---------------------------------------------------------------- Rechte und Bereich
    def test_rechte_und_testpatienten(self):
        self.assertEqual(client_fuer(self.betrachter).post("/api/korrespondenz/", {
            "patient": self.patient.id, "vorlage": "patientenaufnahme", "titel": "X"}, format="json").status_code, 403)
        # Admins schreiben nur bei Testpatienten – auch keine Freigabe echter Akten
        self.entwurf(client=client_fuer(self.admin), erwartet=403)
        test = Patient(nachname="Probe", vorname="Paula", geburtsdatum="1970-01-01", ist_test=True)
        test.save()
        d = self.entwurf(client=client_fuer(self.admin), patient=test)
        self.freigeben(d, client=client_fuer(self.admin))
        echt = self.entwurf()
        self.assertEqual(client_fuer(self.admin).post(f"/api/korrespondenz/{echt['id']}/freigeben/").status_code, 403)
        # Testbenutzer sehen nur Testpatienten
        tester = benutzer("tester", Rolle.MEDIZINER, ist_test=True)
        c = client_fuer(tester)
        self.assertEqual(c.get(f"/api/korrespondenz/{echt['id']}/").status_code, 404)
        self.assertEqual(c.get(f"/api/korrespondenz/?patient={self.patient.id}").json(), [])
        self.entwurf(client=c, erwartet=400)  # Patient gibt es für ihn nicht

    def test_eingeschraenkte_akte(self):
        d = self.entwurf()
        Patient.objects.filter(pk=self.patient.pk).update(eingeschraenkt_am=timezone.now())
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.get(f"/api/korrespondenz/{d['id']}/").status_code, 404)
        self.assertEqual(c.get(f"/api/korrespondenz/{d['id']}/pdf/").status_code, 404)

    def test_firmen(self):
        """Nur Schreiben aus Akten der aktiven Firma; neue Schreiben tragen die aktive Firma."""
        rg = Firma.objects.get(kuerzel="rg")
        nur_rg = benutzer("nurrg", Rolle.KEINE)
        Mitgliedschaft.objects.create(benutzer=nur_rg, firma=rg, rolle=Rolle.MEDIZINER)
        d = self.entwurf()  # Akte der DSKM
        c = echte_anmeldung(nur_rg, mit_zweitem_faktor(nur_rg, 1)[0])
        self.assertEqual(c.get(f"/api/korrespondenz/{d['id']}/").status_code, 404)
        PatientFirma.objects.create(patient=self.patient, firma=rg)
        self.assertEqual(c.get(f"/api/korrespondenz/{d['id']}/").status_code, 200)
        r = c.post("/api/korrespondenz/", {"patient": self.patient.id, "vorlage": "patientenaufnahme",
                                           "titel": "Brief der Klinik"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["firma_kurz"], "RGC")
        self.assertEqual(Schreiben.objects.get(pk=r.json()["id"]).firma, rg)

    def test_akte_loeschen_mit_freigegebenem_schreiben(self):
        test = Patient(nachname="Probe", vorname="Paula", geburtsdatum="1970-01-01", ist_test=True)
        test.save()
        d = self.entwurf(patient=test)
        self.freigeben(d)
        with wartungsmodus():
            akten_entfernen([test.id])
        self.assertFalse(Schreiben.objects.filter(pk=d["id"]).exists())
        self.assertFalse(Schreiben.history.filter(patient_id=test.id).exists())

    # ---------------------------------------------------------------- Datenfelder
    def test_datenfelder_diagnosen_gewicht_plan_medikation(self):
        for art in ("patientenaufnahme", "reisebescheinigung", "eigen-arztbrief"):
            for name in ("Patient.Diagnosen", "Gewicht.aktuell", "Plan.Kurz", "Plan.kcal", "Medikamente.Liste",
                         "Schreiben.Text", "Schreiben.Empfänger"):
                self.assertIn(name, FELDER[art], (art, name))
        p = Patient(nachname="Probe", vorname="Paula", geburtsdatum="1970-01-01", ist_test=True)
        p.save()
        Gewichtsmessung.objects.create(patient=p, gewicht_kg="60.0", gemessen_am=timezone.localdate())
        Medikament.objects.create(patient=p, wirkstoff="Pantoprazol", staerke="40 mg", morgens="1", einheit="Tbl.")
        Medikament.objects.create(patient=p, wirkstoff="Loperamid", bedarf=True, dosierung_frei="bis 4× täglich")
        c = client_fuer(self.mediziner)
        e = c.post("/api/infusionsplaene/entwurf/", {"patient": p.id}, format="json").json()
        r = c.patch(f"/api/infusionsplaene/{e['id']}/", {
            "basis_praeparat": praeparat("Sterofundin ISO").id, "basis_ml": 500,
            "glucose_praeparat": praeparat("Glucose", "70 %").id, "glucose_g": "160", "laufzeit_h": "12"},
            format="json")
        self.assertEqual(r.status_code, 200, r.content)
        k = Kontext(patient=p)
        felder = FELDER["eigen-arztbrief"]
        self.assertIsNone(felder["Plan.Kurz"].wert(k))  # nur ein Entwurf, noch kein aktueller Plan
        self.assertEqual(c.post(f"/api/infusionsplaene/{e['id']}/freigeben/").status_code, 200)
        k = Kontext(patient=Patient.objects.get(pk=p.pk))
        self.assertIn("60 kg am", felder["Gewicht.aktuell"].wert(k))
        self.assertEqual(felder["Gewicht.kg"].wert(k), "60 kg")
        self.assertIn("12 h", felder["Plan.Kurz"].wert(k))
        self.assertTrue(felder["Plan.kcal"].wert(k))
        self.assertEqual(felder["Plan.gültig_ab"].wert(k), f"{Infusionsplan.objects.get(pk=e['id']).gueltig_ab:%d.%m.%Y}")
        liste = felder["Medikamente.Liste"].wert(k)
        self.assertIn("Pantoprazol 40 mg", liste)
        self.assertIn("Bei Bedarf:\nLoperamid · bis 4× täglich", liste)
        self.assertIsNone(felder["Schreiben.Text"].wert(k))
