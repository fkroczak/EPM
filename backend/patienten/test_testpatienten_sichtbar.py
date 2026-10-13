"""Testpatienten im echten Betrieb (Kundenfrage 13.10.2026): Ohne das Recht „Testdaten sehen“ gibt es Testpatienten für
diese Person nirgends – Liste, Suche, Zähler, Kalender, Startseite, Merkliste, Infusionspläne, Termine, Kontakte,
Berichte, Befunde, Gewichte, Dokumente und das Infoblatt. Alles läuft über ``epm.api_basis.patienten_fuer``."""
from datetime import timedelta

from django.utils import timezone

from accounts.models import Gruppenrecht, Rolle
from epm.pruefhilfen import Grundlage, client_fuer
from infusionen.models import Infusionsplan
from patienten.models import Gewichtsmessung, Kontakt, Patient, Termin

NAME = "Testzzpatient"


class TestpatientenSichtbarTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.test = Patient.objects.create(nachname=NAME, vorname="Toni", geburtsdatum="1970-01-01", ist_test=True,
                                          versorger=cls.patient.versorger)
        heute = timezone.localdate()
        Termin.objects.create(patient=cls.test, faellig_am=heute + timedelta(days=1), titel="Rückruf " + NAME)
        Termin.objects.create(patient=cls.test, faellig_am=heute - timedelta(days=3), titel="Überfällig " + NAME)
        Kontakt.objects.create(patient=cls.test, zeitpunkt=timezone.now(), text=f"<p>Kontakt {NAME}</p>",
                               erfasst_von=cls.mitarbeiter)
        Gewichtsmessung.objects.create(patient=cls.test, gewicht_kg=60, gemessen_am=heute, erfasst_von=cls.mitarbeiter)
        Infusionsplan.objects.create(patient=cls.test, erstellt_von=cls.mitarbeiter)
        Gruppenrecht.objects.create(rolle=Rolle.MITARBEITER, recht="testdaten_sehen", erlaubt=False)

    def test_nirgends_sichtbar(self):
        c = client_fuer(self.mitarbeiter)
        heute = timezone.localdate()
        pfade = [
            "/api/patienten/", f"/api/patienten/?suche={NAME}", "/api/patienten/?test=nur", "/api/patienten/zaehler/",
            f"/api/patienten/doppelte/?geburtsdatum=1970-01-01&nachname={NAME}",
            f"/api/kalender/?von={heute - timedelta(days=7)}&bis={heute + timedelta(days=7)}",
            "/api/startseite/", "/api/meine-akten/", "/api/infusionsplaene/", "/api/termine/", "/api/kontakte/",
            f"/api/berichte/?patient={self.test.id}", f"/api/laborbefunde/?patient={self.test.id}",
            f"/api/gewichte/?patient={self.test.id}", f"/api/dokumente/?patient={self.test.id}",
            f"/api/versorger/{self.patient.versorger_id}/" if self.patient.versorger_id else "/api/versorger/",
        ]
        for pfad in pfade:
            r = c.get(pfad)
            self.assertIn(r.status_code, (200, 400), (pfad, r.content))
            self.assertNotIn(NAME, r.content.decode(), pfad)
            self.assertNotIn(f'"id":{self.test.id},"nummer"', r.content.decode().replace(" ", ""), pfad)
        self.assertEqual(c.get(f"/api/patienten/{self.test.id}/").status_code, 404)
        # auch nichts anlegen: der Patient wäre für diese Person unsichtbar
        r = c.post("/api/termine/", {"patient": self.test.id, "faellig_am": str(heute), "titel": "x"}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        # mit dem Recht sieht dieselbe Person den Testpatienten
        Gruppenrecht.objects.filter(recht="testdaten_sehen").update(erlaubt=True)
        self.assertIn(NAME, c.get("/api/patienten/").content.decode())
        self.assertIn(NAME, c.get("/api/startseite/").content.decode())
