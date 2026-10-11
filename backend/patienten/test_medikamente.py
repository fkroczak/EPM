"""Medikamentenplan als eigener Reiter der Akte (Wunsch 11.10.2026): Medikamente mit Dosierung wie im
bundeseinheitlichen Medikationsplan, Absetzen statt Löschen, Medikationsplan als PDF."""
from datetime import timedelta

from django.utils import timezone

from audit.models import SystemEreignis
from audit.schutz import wartungsmodus
from epm.pruefhilfen import Grundlage, benutzer, client_fuer, echte_anmeldung, mit_zweitem_faktor
from accounts.models import Mitgliedschaft, Rolle
from stammdaten.models import Firma

from .datenschutz import akten_entfernen
from .models import Medikament, Patient, PatientFirma

URL = "/api/medikamente/"


class MedikamenteTest(Grundlage):
    def anlegen(self, client=None, **extra):
        c = client or client_fuer(self.mitarbeiter)
        daten = {"patient": self.patient.id, "wirkstoff": "Pantoprazol", "handelsname": "Pantozol",
                 "staerke": "40 mg", "darreichungsform": "Tablette", "morgens": "1", "mittags": "0", "abends": "0",
                 "nachts": "0", "einheit": "Stück", "grund": "Magenschutz", **extra}
        return c.post(URL, daten, format="json")

    def test_anlegen_und_liste(self):
        r = self.anlegen(wirkstoff="  Pantoprazol ")
        self.assertEqual(r.status_code, 201, r.content)
        m = r.json()
        self.assertEqual((m["wirkstoff"], m["schema"], m["aktiv"]), ("Pantoprazol", "1 – 0 – 0 – 0", True))
        self.assertTrue(m["angelegt_von_name"])
        self.assertIn("firma_kurz", m)
        r = self.anlegen(wirkstoff="Loperamid", staerke="2 mg", darreichungsform="Kapsel", morgens="", mittags="",
                         abends="", nachts="", bedarf=True, hinweise="max. 8 Kapseln am Tag", grund="Durchfall")
        self.assertEqual(r.status_code, 201, r.content)
        liste = client_fuer(self.betrachter).get(f"{URL}?patient={self.patient.id}").json()
        # Dauermedikation vor Bedarfsmedikation
        self.assertEqual([x["wirkstoff"] for x in liste], ["Pantoprazol", "Loperamid"])
        self.assertEqual(client_fuer(self.mitarbeiter).get(f"{URL}?patient={self.patient.id}&bedarf=true").json()[0]
                         ["wirkstoff"], "Loperamid")
        kopf = client_fuer(self.mitarbeiter).get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual(kopf["zaehler"]["medikamente"], 2)

    def test_pruefungen(self):
        r = self.anlegen(wirkstoff="  ")
        self.assertEqual(r.status_code, 400)
        self.assertIn("wirkstoff", r.json())
        # ohne Dosierung nur bei Bedarf
        leer = {"morgens": "", "mittags": "", "abends": "", "nachts": ""}
        r = self.anlegen(**leer)
        self.assertEqual(r.status_code, 400)
        self.assertIn("dosierung_frei", r.json())
        self.assertEqual(self.anlegen(**leer, bedarf=True).status_code, 201)
        r = self.anlegen(**leer, wirkstoff="Colecalciferol", staerke="20 000 IE", dosierung_frei="1× wöchentlich montags")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["schema"], r.json()["dosierung"]), ("", "1× wöchentlich montags"))
        morgen = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertIn("Zukunft", str(self.anlegen(seit=morgen).json()))

    def test_absetzen_und_wieder_ansetzen(self):
        m = self.anlegen().json()
        c = client_fuer(self.mitarbeiter)
        r = c.post(f"{URL}{m['id']}/absetzen/", {"absetzgrund": "keine Beschwerden mehr"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["aktiv"], r.json()["abgesetzt_am"], r.json()["absetzgrund"]),
                         (False, timezone.localdate().isoformat(), "keine Beschwerden mehr"))
        self.assertEqual(c.post(f"{URL}{m['id']}/absetzen/", {}, format="json").status_code, 400)
        kopf = c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual(kopf["zaehler"]["medikamente"], 0)
        # Datum in der Zukunft geht nicht
        m2 = self.anlegen(wirkstoff="Metamizol").json()
        morgen = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertEqual(c.post(f"{URL}{m2['id']}/absetzen/", {"abgesetzt_am": morgen}, format="json").status_code, 400)
        self.assertTrue(Medikament.objects.get(pk=m2["id"]).aktiv)
        # wieder ansetzen leert Datum und Grund
        r = c.post(f"{URL}{m['id']}/ansetzen/", format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["aktiv"], r.json()["abgesetzt_am"], r.json()["absetzgrund"]), (True, None, ""))
        # auch per PATCH wie bei den Diagnosen: Datum heute
        r = c.patch(f"{URL}{m['id']}/", {"aktiv": False}, format="json")
        self.assertEqual((r.status_code, r.json()["abgesetzt_am"]), (200, timezone.localdate().isoformat()))
        # alles steht im Verlauf
        verlauf = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=medikamente").json()
        self.assertEqual([e["aktion"] for e in verlauf if e["objekt_id"] == m["id"]],
                         ["abgesetzt", "wieder angesetzt", "abgesetzt", "angelegt"])
        self.assertIn("Pantoprazol 40 mg (Pantozol) · 1 – 0 – 0 – 0", verlauf[-1]["beschreibung"])

    def test_kein_loeschen(self):
        m = self.anlegen().json()
        self.assertEqual(client_fuer(self.mitarbeiter).delete(f"{URL}{m['id']}/").status_code, 405)
        with self.assertRaises(PermissionError):
            Medikament.objects.get(pk=m["id"]).delete()

    def test_rechte(self):
        m = self.anlegen().json()
        b = client_fuer(self.betrachter)
        self.assertEqual(b.get(f"{URL}?patient={self.patient.id}").status_code, 200)
        self.assertEqual(self.anlegen(b).status_code, 403)
        self.assertEqual(b.patch(f"{URL}{m['id']}/", {"wirkstoff": "X"}, format="json").status_code, 403)
        self.assertEqual(b.post(f"{URL}{m['id']}/absetzen/", {}, format="json").status_code, 403)
        # abgeschlossene Akte nimmt nichts mehr an
        Patient.objects.filter(pk=self.patient.pk).update(abgeschlossen_am=timezone.localdate(),
                                                          abschluss_anlass=Patient.Abschlussanlass.VERSTORBEN)
        self.assertNotIn(self.anlegen().status_code, (200, 201))

    def test_nur_eigene_akten(self):
        test = Patient.objects.create(nachname="Test", vorname="Tina", geburtsdatum="1970-01-01", ist_test=True)
        Medikament.objects.create(patient=test, wirkstoff="Testwirkstoff", morgens="1")
        testnutzer = benutzer("testnutzer", Rolle.MITARBEITER, ist_test=True)
        self.anlegen()
        c = client_fuer(testnutzer)
        self.assertEqual([m["wirkstoff"] for m in c.get(URL).json()], ["Testwirkstoff"])
        self.assertEqual(self.anlegen(c).status_code, 400)  # echte Akte gibt es für Testbenutzer nicht

    def test_medikationsplan_pdf(self):
        self.anlegen()
        self.anlegen(wirkstoff="Loperamid", staerke="2 mg", morgens="", mittags="", abends="", nachts="", bedarf=True)
        c = client_fuer(self.betrachter)
        r = c.get(f"/api/patienten/{self.patient.id}/medikationsplan-pdf/")
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.EXPORT).latest("id")
        self.assertEqual(e.details.get("was"), "Medikationsplan")
        # ohne Medikamente gibt es den Plan trotzdem (leere Dauermedikation)
        leer = Patient.objects.create(nachname="Leer", vorname="Lea", geburtsdatum="1980-01-01")
        self.assertEqual(c.get(f"/api/patienten/{leer.id}/medikationsplan-pdf/").status_code, 200)

    def test_tabellen_der_vorlage(self):
        from vorlagen.felder import Kontext, tabellenzeilen

        self.anlegen()
        self.anlegen(wirkstoff="Colecalciferol", staerke="20 000 IE", morgens="", mittags="", abends="", nachts="",
                     dosierung_frei="1× wöchentlich montags", einheit="Kapsel")
        self.anlegen(wirkstoff="Loperamid", staerke="2 mg", morgens="1", mittags="", abends="", nachts="", bedarf=True,
                     hinweise="nach jedem ungeformten Stuhl")
        abgesetzt = self.anlegen(wirkstoff="Ibuprofen").json()
        client_fuer(self.mitarbeiter).post(f"{URL}{abgesetzt['id']}/absetzen/", {}, format="json")
        k = Kontext(patient=self.patient)
        dauer = tabellenzeilen("medikationsplan", "medikamente", k)
        self.assertEqual([z[0] for z in dauer], ["Colecalciferol", "Pantoprazol"])
        self.assertEqual(dauer[1][4:9], ["1", "0", "0", "0", "Stück"])
        self.assertEqual(dauer[0][4:8], ["", "", "", ""])
        self.assertEqual(dauer[0][9], "1× wöchentlich montags")
        bedarf = tabellenzeilen("medikationsplan", "bedarfsmedikation", k)
        self.assertEqual([(z[0], z[4:8]) for z in bedarf], [("Loperamid", ["1", "0", "0", "0"])])

    def test_dsgvo_loeschen_entfernt_historie(self):
        m = self.anlegen().json()
        client_fuer(self.mitarbeiter).post(f"{URL}{m['id']}/absetzen/", {}, format="json")
        self.assertEqual(Medikament.history.filter(patient_id=self.patient.id).count(), 2)
        with wartungsmodus():
            akten_entfernen([self.patient.id])
        self.assertFalse(Medikament.objects.filter(pk=m["id"]).exists())
        self.assertEqual(Medikament.history.filter(patient_id=self.patient.id).count(), 0)

    def test_firma_wird_vermerkt(self):
        rg = Firma.objects.get(kuerzel="rg")
        nur_rg = benutzer("nurrg", Rolle.KEINE)
        Mitgliedschaft.objects.create(benutzer=nur_rg, firma=rg, rolle=Rolle.MITARBEITER)
        PatientFirma.objects.create(patient=self.patient, firma=rg)
        c = echte_anmeldung(nur_rg, mit_zweitem_faktor(nur_rg, 1)[0])
        r = self.anlegen(c)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["firma_kurz"], rg.kurzname)
        self.assertEqual(Medikament.objects.get(pk=r.json()["id"]).firma, rg)
