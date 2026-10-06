"""Berichte aus der Akte (F115): Entwurf, Freigabe, Unveränderlichkeit, PDF als Dokument."""
from django.db import DatabaseError, transaction
from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer
from patienten.models import Dokument
from stammdaten.models import Auswahlwert

from .models import Bericht


class BerichtTest(Grundlage):
    def entwurf(self, client=None, **extra):
        c = client or client_fuer(self.mitarbeiter)
        art = Auswahlwert.objects.get(liste=Auswahlwert.Liste.BERICHTART, wert="Arztbrief")
        r = c.post("/api/berichte/", {"patient": self.patient.id, "art": art.id, "titel": "Verlauf 2026",
                                      "empfaenger": "Hausarzt Dr. Hausmann",
                                      "inhalt": "<p>Stabiler Verlauf <script>x</script></p>", **extra}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_entwurf_anlegen_und_aendern(self):
        d = self.entwurf()
        self.assertEqual(d["status"], "entwurf")
        self.assertNotIn("<script>", d["inhalt"])
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"/api/berichte/{d['id']}/", {"titel": "Verlauf 2026 (korrigiert)"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["titel"], "Verlauf 2026 (korrigiert)")

    def test_entwurf_verwerfen(self):
        d = self.entwurf()
        r = client_fuer(self.mitarbeiter).delete(f"/api/berichte/{d['id']}/")
        self.assertEqual(r.status_code, 204, r.content)
        self.assertEqual(Bericht.objects.count(), 0)

    def test_mitarbeiter_darf_nicht_freigeben(self):
        """Freigeben hat ein eigenes Recht; Standard ist der Mediziner (U54)."""
        d = self.entwurf()
        r = client_fuer(self.mitarbeiter).post(f"/api/berichte/{d['id']}/freigeben/")
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(Bericht.objects.get(pk=d["id"]).status, "entwurf")

    def test_freigabe_erzeugt_pdf_und_sperrt(self):
        d = self.entwurf()
        c = client_fuer(self.mediziner)
        r = c.post(f"/api/berichte/{d['id']}/freigeben/")
        self.assertEqual(r.status_code, 200, r.content)
        f = r.json()
        self.assertEqual(f["status"], "freigegeben")
        self.assertIn("Maschinell erstellt, geprüft und freigegeben von", f["freigabevermerk"])
        self.assertEqual(len(f["pdf_sha256"]), 64)
        dok = Dokument.objects.get(pk=f["dokument"])
        self.assertEqual(dok.herkunft, Dokument.Herkunft.SYSTEM)
        self.assertEqual(dok.mime, "application/pdf")
        self.assertTrue(dok.pfad.is_file())
        # danach unveränderlich – über die API und in der Datenbank
        r = c.patch(f"/api/berichte/{d['id']}/", {"titel": "anders"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)
        r = c.delete(f"/api/berichte/{d['id']}/")
        self.assertEqual(r.status_code, 403, r.content)

    def test_trigger_schuetzt_freigegebenen_bericht(self):
        d = self.entwurf()
        client_fuer(self.mediziner).post(f"/api/berichte/{d['id']}/freigeben/")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                Bericht.objects.filter(pk=d["id"]).update(titel="am Modell vorbei")

    def test_leerer_bericht_nicht_freigebbar(self):
        d = self.entwurf(inhalt="")
        r = client_fuer(self.mediziner).post(f"/api/berichte/{d['id']}/freigeben/")
        self.assertEqual(r.status_code, 400, r.content)

    def test_abgeschlossene_akte_gesperrt(self):
        self.patient.abgeschlossen_am = timezone.localdate()
        self.patient.abschluss_anlass = self.patient.Abschlussanlass.THERAPIE_BEENDET
        self.patient.save()
        art = Auswahlwert.objects.get(liste=Auswahlwert.Liste.BERICHTART, wert="Arztbrief")
        r = client_fuer(self.mitarbeiter).post("/api/berichte/", {"patient": self.patient.id, "art": art.id,
                                                                  "titel": "X", "inhalt": "<p>Y</p>"}, format="json")
        self.assertEqual(r.status_code, 409, r.content)
