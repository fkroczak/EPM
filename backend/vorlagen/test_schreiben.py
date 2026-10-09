"""Schreiben mit E-Mail-Text und Anlagen (Vorlagen von Alice Hessel, 09.10.2026; F172–F174)."""
import email
import io
import shutil
import tempfile
from datetime import time, timedelta
from email.policy import default

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from audit.models import SystemEreignis
from epm.pruefhilfen import Grundlage, client_fuer
from patienten.models import Dokument, Patient, Termin
from stammdaten.models import Auswahlwert

from .bloecke import STARTVORLAGEN, pruefe_bloecke
from .models import Anlage
from .tests import kompakt, pdf_text

DOKUMENTE = tempfile.mkdtemp(prefix="epm-schreiben-")


@override_settings(EPM_DOKUMENTE=__import__("pathlib").Path(DOKUMENTE))
class SchreibenTest(Grundlage):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(DOKUMENTE, ignore_errors=True)

    def setUp(self):
        self.p = Patient.objects.create(nachname="Kaufmann", vorname="Marija", geschlecht="w", strasse="Industriestr. 31",
                                        plz="40227", ort="Düsseldorf", email="marija@example.org",
                                        geburtsdatum=timezone.localdate() - timedelta(days=16000))
        self.ort, _ = Auswahlwert.objects.get_or_create(liste=Auswahlwert.Liste.TERMINORT, wert="Praxis Dr. Holtmeier")
        self.telefon, _ = Auswahlwert.objects.get_or_create(liste=Auswahlwert.Liste.TERMINORT, wert="Telefon/Video")
        self.tag = timezone.localdate() + timedelta(days=3)
        self.termin = Termin.objects.create(patient=self.p, art=Termin.Art.PRAXISTERMIN, faellig_am=self.tag,
                                            uhrzeit=time(14, 30), ort=self.ort, titel="Sprechstunde")
        self.c = client_fuer(self.mitarbeiter)

    def schreiben(self, **daten):
        return self.c.post(f"/api/patienten/{self.p.id}/schreiben/", daten, format="json")

    def test_startvorlagen_und_email_nur_bei_schreiben(self):
        for art in ("patientenaufnahme", "terminbestaetigung", "reisebescheinigung", "patientenankuendigung"):
            self.assertEqual(pruefe_bloecke(art, STARTVORLAGEN[art]), [])
        mit_email = [*STARTVORLAGEN["sprechstunde"], {"id": "m", "typ": "email", "betreff": "x", "text": "y"}]
        self.assertTrue(any("nur bei den Schreiben" in f for f in pruefe_bloecke("sprechstunde", mit_email)))
        doppelt = [*STARTVORLAGEN["patientenaufnahme"], {"id": "m2", "typ": "email", "betreff": "x", "text": "y"}]
        self.assertTrue(any("höchstens einmal" in f for f in pruefe_bloecke("patientenaufnahme", doppelt)))
        d = client_fuer(self.admin).get("/api/vorlagen/terminbestaetigung/").json()
        self.assertIn("email", [b["typ"] for b in d["bausteine"]])
        self.assertIn("Termin.Datum", [f["name"] for f in d["felder"]])
        d = client_fuer(self.admin).get("/api/vorlagen/infusionsplan/").json()
        self.assertNotIn("email", [b["typ"] for b in d["bausteine"]])

    def test_terminbestaetigung_pdf_email_und_eml(self):
        self.assertEqual(self.schreiben(art="terminbestaetigung", ausgabe="pdf").status_code, 400)  # ohne Termin
        r = self.schreiben(art="terminbestaetigung", termin=self.termin.id)
        self.assertEqual(r.status_code, 200, r.content)
        text = pdf_text(r.content)
        self.assertIn("Sehr geehrte Frau Kaufmann", text)
        self.assertIn("Hamannplatz 23", text)
        self.assertIn("14:30 Uhr", text)
        self.assertIn("Gesundheitskarte", text)
        self.assertIn(kompakt("Eine Überweisung ist nicht notwendig"), kompakt(text))

        r = self.schreiben(art="terminbestaetigung", termin=self.termin.id, ausgabe="email")
        self.assertEqual(r.status_code, 200, r.content)
        mail = r.json()
        self.assertEqual(mail["an"], "marija@example.org")
        self.assertIn(f"{self.tag:%d.%m.%Y}", mail["betreff"])
        self.assertIn("Ort: Praxis Dr. med. Martin Holtmeier, Hamannplatz 23, 48157 Münster", mail["text"])

        anlage = Anlage.objects.filter(aktiv=True).first() or self._anlage()
        r = self.schreiben(art="terminbestaetigung", termin=self.termin.id, ausgabe="eml", anlagen=[anlage.id],
                           betreff="Ihr Termin", text="Hallo,\nbis bald.", ablegen=True)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r["Content-Type"], "message/rfc822")
        nachricht = email.message_from_bytes(r.content, policy=default)
        self.assertEqual(nachricht["X-Unsent"], "1")
        self.assertEqual(nachricht["To"], "marija@example.org")
        self.assertEqual(nachricht["Subject"], "Ihr Termin")
        self.assertIn("bis bald.", nachricht.get_body(("plain",)).get_content())
        anhaenge = [(a.get_filename(), a.get_content()) for a in nachricht.iter_attachments()]
        self.assertEqual(len(anhaenge), 2)
        self.assertTrue(anhaenge[0][0].startswith("Terminbestätigung-Sprechstunde-Kaufmann-"))
        self.assertTrue(anhaenge[0][1].startswith(b"%PDF-"))
        self.assertEqual(anhaenge[1][0], anlage.dateiname)
        dok = Dokument.objects.get(pk=r["X-EPM-Dokument"])
        self.assertEqual((dok.patient_id, dok.typ.wert), (self.p.id, "Schreiben"))
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.EXPORT).latest("id")
        self.assertEqual((e.details["was"], e.details["ausgabe"], e.details["abgelegt"]),
                         ("Terminbestätigung Sprechstunde", "eml", True))
        # fremder Termin
        anderer = Termin.objects.create(patient=self.patient, faellig_am=self.tag, titel="x")
        self.assertEqual(self.schreiben(art="terminbestaetigung", termin=anderer.id).status_code, 400)
        # Lesen allein reicht nicht
        r = client_fuer(self.betrachter).post(f"/api/patienten/{self.p.id}/schreiben/",
                                              {"art": "patientenaufnahme"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_patientenaufnahme_und_reisebescheinigung(self):
        mail = self.schreiben(art="patientenaufnahme", ausgabe="email").json()
        self.assertTrue(mail["text"].startswith("Sehr geehrte Frau Kaufmann,"))
        self.assertIn("Spurenelemente (Kupfer, Zink, Selen, Mangan, Eisen)", mail["text"])
        self.assertIn("www.dsgme.org", mail["text"])
        self.assertNotIn("{{", mail["text"])

        r = self.schreiben(art="reisebescheinigung", tage=21)
        self.assertEqual(r.status_code, 200, r.content)
        from pypdf import PdfReader

        leser = PdfReader(io.BytesIO(r.content))
        self.assertEqual(len(leser.pages), 2)  # Bescheinigung (eine Seite) + ADAC-Attest
        felder = leser.get_fields()
        self.assertTrue(felder["Name des PatientenPatients namenom du patientnombre del paciente"]["/V"]
                        .startswith("Marija Kaufmann, geb. "))
        self.assertEqual(felder["Tage"]["/V"], "21")
        text = kompakt(pdf_text(r.content))
        self.assertIn(kompakt("für das Überleben der Patientin essenziell"), text)
        self.assertIn(kompakt("Sicherstellung ihrer lebensnotwendigen"), text)
        self.assertIn(kompakt("Mrs. Marija Kaufmann"), text)
        self.assertIn(kompakt("maintaining her vital"), text)
        self.assertIn("Hamannplatz23", text)
        self.p.geschlecht = "m"
        self.p.save()
        text = kompakt(pdf_text(self.schreiben(art="reisebescheinigung", attest=False).content))
        self.assertIn(kompakt("Überleben des Patienten"), text)
        self.assertIn(kompakt("Mr. Marija Kaufmann"), text)
        self.assertEqual(self.schreiben(art="reisebescheinigung", tage=0).status_code, 400)
        self.assertEqual(self.schreiben(art="infusionsplan").status_code, 400)

    def test_patientenankuendigung(self):
        zweiter = Patient.objects.create(nachname="Flegel", vorname="Angelika", telefon="+49 1767 038 1718",
                                         geburtsdatum=self.tag - timedelta(days=12000))
        Termin.objects.create(patient=zweiter, art=Termin.Art.PRAXISTERMIN, faellig_am=self.tag, uhrzeit=time(15),
                              ort=self.telefon, bei="WhatsApp-Video", titel="Sprechstunde")
        Termin.objects.create(patient=zweiter, art=Termin.Art.WIEDERVORLAGE, faellig_am=self.tag, titel="nicht dabei")
        test = Patient(nachname="Probe", vorname="Paula", geburtsdatum=self.tag - timedelta(days=15000))
        test.ist_test = True
        test.save()
        Termin.objects.create(patient=test, art=Termin.Art.PRAXISTERMIN, faellig_am=self.tag, titel="Test")
        koerper = {"von": str(self.tag - timedelta(days=1)), "bis": str(self.tag + timedelta(days=2)), "ort": self.ort.id}
        mail = self.c.post("/api/kalender/ankuendigung/", {**koerper, "ausgabe": "email"}, format="json").json()
        self.assertIn("Sehr geehrter Dr. Holtmeier", mail["text"])
        self.assertIn(f"{self.tag:%d.%m.%Y}\n14:30  Marija Kaufmann\n15:00  Angelika Flegel → Telefon/Video "
                      "+49 1767 038 1718 · WhatsApp-Video", mail["text"])
        self.assertNotIn("Paula", mail["text"])
        self.assertNotIn("nicht dabei", mail["text"])
        r = self.c.post("/api/kalender/ankuendigung/", koerper, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        text = pdf_text(r.content)
        self.assertIn("Patientenankündigung Sprechstunde", text)
        self.assertIn("Angelika Flegel", text)
        r = self.c.post("/api/kalender/ankuendigung/", {**koerper, "ausgabe": "eml"}, format="json")
        nachricht = email.message_from_bytes(r.content, policy=default)
        self.assertIsNone(nachricht["To"])
        self.assertEqual(len(list(nachricht.iter_attachments())), 1)
        self.assertEqual(self.c.post("/api/kalender/ankuendigung/", {"von": "2026-10-10", "bis": "2026-10-01"},
                                     format="json").status_code, 400)

    def _anlage(self):
        r = client_fuer(self.mitarbeiter).post("/api/anlagen/", {
            "name": "Merkblatt", "datei": SimpleUploadedFile("merkblatt.pdf", b"%PDF-1.4\n%%EOF\n")}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        return Anlage.objects.get(pk=r.json()["id"])

    def test_anlagen(self):
        c = client_fuer(self.mitarbeiter)
        liste = c.get("/api/anlagen/").json()
        self.assertEqual([a["name"] for a in liste][:1], ["Leitfaden Kurzdarmsyndrom und Zottentraining"])
        self.assertEqual(len(client_fuer(self.mitarbeiter).get("/api/anlagen/").json()), len(liste))  # nur einmal
        a = self._anlage()
        self.assertEqual(c.get(f"/api/anlagen/{a.id}/datei/").content[:5], b"%PDF-")
        r = c.post("/api/anlagen/", {"name": "x", "datei": SimpleUploadedFile("x.txt", b"hallo")}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(client_fuer(self.betrachter).post("/api/anlagen/", {"name": "x"}).status_code, 403)
        self.assertEqual(c.patch(f"/api/anlagen/{a.id}/", {"aktiv": False}, format="json").status_code, 200)
        self.assertNotIn(a.id, [x["id"] for x in c.get("/api/anlagen/").json()])
        self.assertIn(a.id, [x["id"] for x in c.get("/api/anlagen/?alle=1").json()])
        r = self.schreiben(art="patientenaufnahme", ausgabe="eml", anlagen=[a.id])
        self.assertEqual(r.status_code, 400)  # deaktiviert

    def test_vorschau_im_editor(self):
        test = Patient(nachname="Probe", vorname="Paula", geschlecht="w",
                       geburtsdatum=timezone.localdate() - timedelta(days=15000))
        test.ist_test = True
        test.save()
        c = client_fuer(self.admin)
        for art in ("patientenaufnahme", "terminbestaetigung", "reisebescheinigung", "patientenankuendigung"):
            with self.subTest(art=art):
                r = c.post(f"/api/vorlagen/{art}/vorschau/", {"patient": test.id}, format="json")
                self.assertEqual(r.status_code, 200, r.content)
                mail = c.post(f"/api/vorlagen/{art}/vorschau/", {"patient": test.id, "ausgabe": "email"},
                              format="json").json()
                self.assertTrue(mail["betreff"])

    def test_eigenes_schreiben(self):
        """F176: unter Vorlagen ein eigenes Schreiben anlegen, bearbeiten, aus der Akte erzeugen, deaktivieren."""
        admin = client_fuer(self.mitarbeiter)
        self.assertEqual(client_fuer(self.betrachter).post("/api/vorlagen/", {"name": "x"}, format="json").status_code, 403)
        self.assertEqual(admin.post("/api/vorlagen/", {"name": ""}, format="json").status_code, 400)
        self.assertEqual(admin.post("/api/vorlagen/", {"name": "Reisebescheinigung"}, format="json").status_code, 400)
        r = admin.post("/api/vorlagen/", {"name": "Rezeptanforderung", "beschreibung": "an den Hausarzt",
                                          "mit_termin": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        art = r.json()["art"]
        self.assertTrue(art.startswith("eigen-"))
        self.assertEqual((r.json()["name"], r.json()["aktiv"]["version"]), ("Rezeptanforderung", 1))
        self.assertIn(art, [v["art"] for v in admin.get("/api/vorlagen/").json()])
        self.assertEqual(admin.post("/api/vorlagen/", {"name": "rezeptanforderung"}, format="json").status_code, 400)
        d = admin.get(f"/api/vorlagen/{art}/").json()
        self.assertIn("email", [b["typ"] for b in d["bausteine"]])
        self.assertIn("Termin.Datum", [f["name"] for f in d["felder"]])

        # Entwurf bearbeiten und veröffentlichen
        bloecke = admin.get(f"/api/vorlagen/{art}/entwurf/").json()["bloecke"]
        inhalt = next(b for b in bloecke if b["id"] == "inhalt")
        inhalt["text"] = "{{Patient.Briefanrede}},\n\nbitte stellen Sie ein Rezept aus (Termin {{Termin.Datum}})."
        self.assertEqual(admin.put(f"/api/vorlagen/{art}/entwurf/", {"bloecke": bloecke}, format="json").status_code, 200)
        self.assertEqual(admin.post(f"/api/vorlagen/{art}/veroeffentlichen/").status_code, 200)

        liste = self.c.get("/api/schreiben/").json()
        self.assertEqual([x["name"] for x in liste if x["eigen"]], ["Rezeptanforderung"])
        self.assertEqual(self.schreiben(art=art).status_code, 400)  # Termin fehlt
        r = self.schreiben(art=art, termin=self.termin.id, ablegen=True)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn(kompakt(f"bitte stellen Sie ein Rezept aus (Termin"), kompakt(pdf_text(r.content)))
        self.assertIn(f"{self.tag:%d.%m.%Y}", pdf_text(r.content))
        self.assertIn("Rezeptanforderung", Dokument.objects.get(pk=r["X-EPM-Dokument"]).titel)
        mail = self.schreiben(art=art, termin=self.termin.id, ausgabe="email").json()
        self.assertEqual(mail["betreff"], "Rezeptanforderung")

        # deaktivieren: nicht mehr wählbar
        self.assertEqual(admin.patch(f"/api/vorlagen/{art}/eigen/", {"aktiv": False}, format="json").status_code, 200)
        self.assertNotIn(art, [x["art"] for x in self.c.get("/api/schreiben/").json()])
        self.assertEqual(self.schreiben(art=art, termin=self.termin.id).status_code, 400)
        self.assertEqual(self.schreiben(art="eigen-gibtsnicht").status_code, 400)
