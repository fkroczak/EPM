"""Verlauf der Therapie als eigene Einträge mit Datum (Wunsch 10.10.2026)."""
from datetime import timedelta

from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer

from .models import Therapieschritt


class TherapieschritteTest(Grundlage):
    def anlegen(self, client=None, **extra):
        c = client or client_fuer(self.mitarbeiter)
        daten = {"patient": self.patient.id, "datum": "2024-11-08", "text": "Beginn HPE", **extra}
        return c.post("/api/therapieschritte/", daten, format="json")

    def test_anlegen_und_neueste_zuerst(self):
        self.assertEqual(self.anlegen().status_code, 201)
        r = self.anlegen(datum="2026-03-23", text="  Umstellung Lipide ")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["text"], "Umstellung Lipide")
        self.assertTrue(r.json()["angelegt_von_name"])
        liste = client_fuer(self.betrachter).get(f"/api/therapieschritte/?patient={self.patient.id}").json()
        self.assertEqual([s["text"] for s in liste], ["Umstellung Lipide", "Beginn HPE"])

    def test_pruefungen(self):
        self.assertEqual(self.anlegen(text="  ").status_code, 400)
        morgen = (timezone.localdate() + timedelta(days=1)).isoformat()
        r = self.anlegen(datum=morgen)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Zukunft", str(r.json()))

    def test_entfernen_statt_loeschen(self):
        s = self.anlegen().json()
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.delete(f"/api/therapieschritte/{s['id']}/").status_code, 405)
        r = c.patch(f"/api/therapieschritte/{s['id']}/", {"aktiv": False}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Therapieschritt.objects.filter(aktiv=True).count(), 0)
        self.assertEqual(Therapieschritt.objects.count(), 1)

    def test_rechte(self):
        self.assertEqual(self.anlegen(client_fuer(self.betrachter)).status_code, 403)

    def test_im_verlauf_der_akte(self):
        self.anlegen()
        c = client_fuer(self.mitarbeiter)
        eintraege = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=therapieschritte").json()
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["beschreibung"], "08.11.2024: Beginn HPE")
