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
            "basis_praeparat": praeparat("Sterofundin ISO").id, "basis_ml": 500,
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
        # ohne aktive Firma (Tests, Befehle) erscheinen auch die Vorlagen der Regeneration Clinic (Oktober 2026)
        self.assertEqual([(v["art"], v["aktiv"]["version"], v["entwurf"]) for v in r.json()
                          if not v["art"].startswith("rgc_")],
                         [("infusionsplan", 1, None), ("patientendatenblatt", 1, None),
                          # Wünsche aus der Praxis vom 06.10.2026 (F115, F116)
                          ("bericht", 1, None), ("sprechstunde", 1, None),
                          # Medikamentenplan (Wunsch 11.10.2026)
                          ("medikationsplan", 1, None),
                          # Schreiben mit E-Mail-Text (Vorlagen von Alice Hessel, 09.10.2026; F172, F173)
                          ("patientenaufnahme", 1, None), ("terminbestaetigung", 1, None),
                          ("reisebescheinigung", 1, None), ("patientenankuendigung", 1, None),
                          ("datenschutzinformation", 1, None), ("einwilligung", 1, None),
                          ("schweigepflichtentbindung", 1, None), ("firmen", 1, None)])
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

    def test_migration_stellt_bisherigen_freigabevermerk_um(self):
        """Bestand: Enthält die aktive Vorlage noch den bisherigen Text, entsteht eine neue Version mit dem Datenfeld."""
        import importlib

        from django.apps import apps

        m = importlib.import_module("vorlagen.migrations.0002_datenschutz_freigabevermerk")
        bloecke = [dict(b) for b in STARTVORLAGEN["infusionsplan"]]
        for b in bloecke:
            if b["id"] == "freigabe":
                b.update(text=m.ALT, optionen={"nicht_teilen": True, "linie_oben": True})
        Dokumentvorlage.objects.create(art="infusionsplan", version=1, status="aktiv", bloecke=bloecke,
                                       veroeffentlicht_am=timezone.now())
        entwurf = Dokumentvorlage.objects.create(art="infusionsplan", status="entwurf", bloecke=bloecke)
        m.freigabevermerk(apps, None)
        # ein Entwurf in Arbeit wird an Ort und Stelle umgestellt (sonst käme der alte Satz beim Veröffentlichen zurück)
        entwurf.refresh_from_db()
        self.assertEqual(next(b for b in entwurf.bloecke if b["id"] == "freigabe")["text"], "{{Plan.Freigabevermerk}}")
        entwurf.delete()
        aktiv = Dokumentvorlage.aktive("infusionsplan")
        vermerk = next(b for b in aktiv.bloecke if b["id"] == "freigabe")
        self.assertEqual((aktiv.version, vermerk["text"], vermerk["optionen"]["ausblenden_wenn_leer"]),
                         (2, "{{Plan.Freigabevermerk}}", True))
        self.assertEqual(pruefe_bloecke("infusionsplan", aktiv.bloecke), [])
        self.assertEqual(Dokumentvorlage.objects.get(art="infusionsplan", version=1).status, "abgeloest")
        # wiederholbar; eine selbst geänderte Vorlage bleibt, wie sie ist
        m.freigabevermerk(apps, None)
        self.assertEqual(Dokumentvorlage.objects.filter(art="infusionsplan").count(), 2)

    @unittest.skipUnless(PDFTOTEXT, "pdftotext fehlt")
    def test_inhalt_des_plan_pdfs(self):
        # freigegeben: Der Freigabevermerk steht nur auf freigegebenen Plänen (beim Entwurf entfällt er)
        p, plan = self.testpatient_mit_plan(freigeben=True)
        pdf, version = erzeuge_aus_vorlage("infusionsplan", Kontext(patient=p, plan=plan), wasserzeichen="TESTDATEN")
        self.assertEqual(version, 1)
        text = pdf_text(pdf)
        # Aufbau wie ein Laborbefund (Überarbeitung 01.10.2026): Menge und Einheit in eigenen Spalten
        for erwartet in ["Empfehlung eines Infusionsplans", "Probe, Paula", "Sterofundin ISO", "Glamin 13,4 %", "80 g",
                         "1.509 kcal", "2.100", "500 ml", "2.600 ml", "216,7 ml/h", "78 mmol", "heimparenteralen",
                         "Pantozol® Kurzinfusion 1 Amp. 40 mg in 50 ml Trägerlösung · 1-0-1",
                         "Patienten-Nr.", "Infusionsplan-Nr.", str(p.nummer), "Mischbeutel", "Zusatzlösung · Sterofundin ISO",
                         "Laufmenge je Stunde", "Laufzeit 12 h", "Phosphat —",
                         "Deutsche Stiftung Krankheitsbedingte Mangelernährung", "Telefon 0251 98 11 400",
                         "Spendenkonto", "1/1", "Maschinell erstellt, geprüft und freigegeben von"]:
            self.assertIn(kompakt(erwartet), kompakt(text))
        self.assertIn("TESTDATEN", wasserzeichen(pdf))
        self.assertNotIn("{{", text)

    @unittest.skipUnless(PDFTOTEXT, "pdftotext fehlt")
    def test_plan_ohne_laufzeit_zeigt_striche(self):
        """Viele Altpläne haben Laufzeit 0: dann „—“ statt „0 h“ bzw. „0 ml/h“."""
        p, plan = self.testpatient_mit_plan()
        Infusionsplan.objects.filter(pk=plan.pk).update(laufzeit_h=0)
        plan.refresh_from_db()
        text = kompakt(pdf_text(erzeuge_aus_vorlage("infusionsplan", Kontext(patient=p, plan=plan))[0]))
        self.assertIn(kompakt("Laufzeit —"), text)
        self.assertIn(kompakt("Laufmenge je Stunde —"), text)
        self.assertNotIn(kompakt("0 ml/h"), text)

    def test_neue_bausteine_und_startvorlage(self):
        c = client_fuer(self.admin)
        start = STARTVORLAGEN["infusionsplan"]
        r = c.get("/api/vorlagen/infusionsplan/startvorlage/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["bloecke"], start)
        self.assertEqual(client_fuer(self.betrachter).get("/api/vorlagen/infusionsplan/startvorlage/").status_code, 403)
        self.assertIn("kopfkarte", [b["typ"] for b in c.get("/api/vorlagen/infusionsplan/").json()["bausteine"]])
        # „neben dem vorherigen Block“ nur, wenn davor ein Text-, Daten- oder Tabellenblock steht
        bloecke = [dict(b) for b in start]
        bloecke[2] = {**bloecke[2], "optionen": {"neben_vorherigem": "drittel"}}  # Kopfkarte
        self.assertTrue(any("neben dem vorherigen" in f for f in pruefe_bloecke("infusionsplan", bloecke)))
        bloecke = [dict(b) for b in start]
        bloecke[4] = {**bloecke[4], "optionen": {"neben_vorherigem": "viertel"}}
        self.assertTrue(any("Option „neben_vorherigem“ ungültig" in f for f in pruefe_bloecke("infusionsplan", bloecke)))
        bloecke = [dict(b) for b in start]
        bloecke[4] = {**bloecke[4], "darstellung": "kacheln"}
        self.assertTrue(any("Darstellung" in f for f in pruefe_bloecke("infusionsplan", bloecke)))
        bloecke = [dict(b) for b in start]
        bloecke[2] = {**bloecke[2], "felder": [{"label": "X", "wert": "{{Gibtsnicht}}"}]}
        self.assertTrue(any("unbekanntes Datenfeld „Gibtsnicht“" in f for f in pruefe_bloecke("infusionsplan", bloecke)))
        # Entwurf aus der Startvorlage speichern und veröffentlichen (Ende-zu-Ende über die API)
        self.assertEqual(c.put("/api/vorlagen/infusionsplan/entwurf/", {"bloecke": start}, format="json").status_code, 200)
        self.assertEqual(c.post("/api/vorlagen/infusionsplan/veroeffentlichen/").status_code, 200)
        self.assertEqual(Dokumentvorlage.aktive("infusionsplan").bloecke, start)

    def test_befund_html_und_nebeneinander(self):
        from .pdf import bloecke_html

        p, plan = self.testpatient_mit_plan()
        inhalt, _, _ = bloecke_html("infusionsplan", STARTVORLAGEN["infusionsplan"], Kontext(patient=p, plan=plan))
        self.assertIn('<td class="b">Natrium</td><td class="zahl">78</td><td class="einheit">mmol</td>', inhalt)
        self.assertIn('class="paar"', inhalt)  # Mineralstoffe neben der Zusammensetzung
        self.assertIn('class="kopfkarte"', inhalt)
        self.assertIn('briefkopf ohne-linie', inhalt)
        # Titel rechts neben dem Logo statt in einer eigenen Zeile; Bereiche mit Überschrift als Karte
        self.assertIn('<div class="kopftitel"><h1>Empfehlung eines Infusionsplans</h1>', inhalt)
        self.assertNotIn('block titel"', inhalt)
        self.assertEqual(inhalt.count(" karte"), 5)  # ohne Diagnose und weitere Bestandteile (leer → ausgeblendet)
        self.assertIn('<td class="zahl fett">2.600</td>', inhalt)
        self.assertNotIn("·  ·", inhalt)
        # Titel in eigener Zeile mittig, Mineralstoffe in großer Schrift (Optionen wirken im PDF)
        bloecke = [dict(b) for b in STARTVORLAGEN["infusionsplan"]]
        bloecke[1] = {**bloecke[1], "neben_logo": False, "optionen": {"ausrichtung": "mitte"}}
        bloecke[4] = {**bloecke[4], "optionen": {**bloecke[4]["optionen"], "schrift": "gross"}}
        self.assertEqual(pruefe_bloecke("infusionsplan", bloecke), [])
        inhalt, _, _ = bloecke_html("infusionsplan", bloecke, Kontext(patient=p, plan=plan))
        self.assertIn('<div class="block a-mitte titel"><h1>Empfehlung eines Infusionsplans</h1>', inhalt)
        self.assertIn('<div class="block s-gross karte"><h2>Mineralstoffe</h2>', inhalt)

    @unittest.skipUnless(PDFTOTEXT, "pdftotext fehlt")
    def test_ansicht_in_der_akte_im_layout_der_vorlage(self):
        """Pläne-Reiter zeigt den Plan wie die PDF: Entwurf aus der aktiven Vorlage mit Wasserzeichen „ENTWURF“."""
        p, plan = self.testpatient_mit_plan()
        r = client_fuer(self.mitarbeiter).get(f"/api/infusionsplaene/{plan.id}/ansicht/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([r["Content-Type"], r["X-EPM-Vorlage-Version"]], ["application/pdf", "1"])
        text = kompakt(pdf_text(r.content))
        for erwartet in ["Empfehlung eines Infusionsplans", "Probe, Paula", "Glamin 13,4 %", "Mischbeutel", "216,7"]:
            self.assertIn(kompakt(erwartet), text)
        self.assertIn("ENTWURF", wasserzeichen(r.content))

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
            for erwartet in ["Zugang zu EPM", "zugang.test", kennwort, "Authenticator", "Notfall-Codes", "Einmal-Passwort",
                             "Ein eigenes Passwort wählen"]:
                self.assertIn(kompakt(erwartet), kompakt(text))
            # sichtbar heißt es „Passwort“ (Entscheidung vom 10.10.2026)
            self.assertNotIn("Kennwort", text)
        from accounts.models import User

        User.objects.filter(pk=uid).update(muss_kennwort_aendern=False)
        self.assertEqual(a.post(url, {"kennwort": kennwort}, format="json").status_code, 400)


class VorlagenJeFirma(Grundlage):
    """Dokumentvorlagen je Firma (Festlegung „Gemischt“, 11.10.2026) und die Vorlagen der Regeneration Clinic
    (Oktober 2026) – mit echter Anmeldung, damit die aktive Firma aus der Sitzung gilt."""

    @classmethod
    def setUpTestData(cls):
        from accounts.models import Mitgliedschaft, Rolle
        from patienten.models import PatientFirma
        from stammdaten.models import Firma

        super().setUpTestData()
        cls.dskm, cls.rg = Firma.objects.get(kuerzel="dskm"), Firma.objects.get(kuerzel="rg")
        Mitgliedschaft.objects.create(benutzer=cls.admin, firma=cls.rg, rolle=Rolle.ADMIN)
        cls.rg_patient = Patient.objects.create(nachname="Klinik", vorname="Karla", geburtsdatum="1970-01-01",
                                                krankenkasse="ÖGK Wien", versichertennummer="1234 010170")
        cls.rg_patient.ist_test = True
        cls.rg_patient.save()
        PatientFirma.objects.filter(patient=cls.rg_patient).update(firma=cls.rg)
        cls.patient.ist_test = True
        cls.patient.save()

    def anmelden(self, firma=None):
        from epm.pruefhilfen import echte_anmeldung, mit_zweitem_faktor

        c = echte_anmeldung(self.admin, mit_zweitem_faktor(self.admin, 1)[0])
        if firma:
            self.assertEqual(c.post("/api/auth/firma/", {"firma": firma}, format="json").status_code, 200)
        return c

    @staticmethod
    def seitenformat(pdf: bytes) -> str:
        from io import BytesIO

        from pypdf import PdfReader

        box = PdfReader(BytesIO(pdf)).pages[0].mediabox
        return "quer" if float(box.width) > float(box.height) else "hoch"

    def test_eigene_vorlage_der_firma_gilt_nur_dort(self):
        c = self.anmelden("dskm")
        d = c.get("/api/vorlagen/einwilligung/").json()
        self.assertEqual((d["firma"]["aktiv"], d["firma"]["eigene"], d["firma"]["mehrere"], d["firma"]["moeglich"]),
                         ("dskm", False, True, True))
        # eigene Vorlage der RGC als Kopie der gemeinsamen: sofort in Gebrauch, Fassung 1 der Firma
        c = self.anmelden("rg")
        r = c.post("/api/vorlagen/einwilligung/firma/", {"eigene": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["firma"]["eigene"], r.json()["aktiv"]["firma"], r.json()["aktiv"]["version"]),
                         (True, "rg", 1))
        self.assertIn("Kopie der gemeinsamen Vorlage", r.json()["aktiv"]["notiz"])
        self.assertTrue(r.json()["entwurfsmodus"]["aktiv"])  # Kopie der ungeprüften Startvorlage: Wasserzeichen bleibt
        # bearbeiten und freigeben in der RGC ändert nur die Vorlage der RGC
        bloecke = [b for b in c.get("/api/vorlagen/einwilligung/entwurf/").json()["bloecke"] if b["id"] != "hinweis"]
        self.assertEqual(c.put("/api/vorlagen/einwilligung/entwurf/", {"bloecke": bloecke}, format="json").status_code, 200)
        r = c.post("/api/vorlagen/einwilligung/veroeffentlichen/")
        self.assertEqual((r.json()["aktiv"]["version"], r.json()["aktiv"]["firma"], r.json()["entwurf"]), (2, "rg", None))
        self.assertEqual([v["version"] for v in r.json()["versionen"]], [2, 1])
        self.assertEqual(Dokumentvorlage.aktive("einwilligung", firma=self.rg).version, 2)
        self.assertEqual((Dokumentvorlage.aktive("einwilligung", firma=self.dskm).version,
                          Dokumentvorlage.aktive("einwilligung", firma=self.dskm).firma), (1, None))
        self.assertIsNone(Dokumentvorlage.entwurf_von("einwilligung", firma=self.dskm))
        # PDF der Erklärung: in der RGC die eigene Fassung ohne Wasserzeichen, bei der DSKM die gemeinsame
        r = c.get(f"/api/patienten/{self.rg_patient.id}/erklaerung-pdf/?art=einwilligung")
        self.assertEqual((r.status_code, r["X-EPM-Vorlage-Version"], r["X-EPM-Vorlage-Entwurf"]), (200, "2", "0"))
        if PDFTOTEXT:
            self.assertNotIn("ENTWURF", wasserzeichen(r.content))
        d = self.anmelden("dskm").get(f"/api/patienten/{self.patient.id}/erklaerung-pdf/?art=einwilligung")
        self.assertEqual((d["X-EPM-Vorlage-Version"], d["X-EPM-Vorlage-Entwurf"]), ("1", "1"))
        self.assertEqual(self.anmelden("dskm").get("/api/vorlagen/einwilligung/").json()["versionen"][0]["version"], 1)
        # eigene Vorlage ablegen: wieder die gemeinsame, die Fassungen der RGC bleiben abgelöst erhalten
        r = c.post("/api/vorlagen/einwilligung/firma/", {"eigene": False}, format="json")
        self.assertEqual((r.status_code, r.json()["firma"]["eigene"], r.json()["aktiv"]["firma"]), (200, False, None))
        self.assertEqual(Dokumentvorlage.objects.filter(art="einwilligung", firma=self.rg, status="abgeloest").count(), 2)
        self.assertEqual(Dokumentvorlage.aktive("einwilligung", firma=self.rg).version, 1)
        # Konstanten je Firma: eigene Schreiben bleiben gemeinsam, nur mit mehreren Firmen
        self.assertEqual(c.post("/api/vorlagen/rgc_anlage_k/firma/", {"eigene": True}, format="json").status_code, 400)

    def test_entwurfsmodus_je_firma(self):
        c = self.anmelden("rg")
        c.post("/api/vorlagen/einwilligung/firma/", {"eigene": True}, format="json")
        r = c.post("/api/vorlagen/einwilligung/entwurfsmodus/", {"aus": True}, format="json")
        self.assertEqual((r.status_code, r.json()["entwurfsmodus"]["aus"], r.json()["entwurfsmodus"]["aktiv"]),
                         (200, True, False))
        from stammdaten.models import Einstellungen

        self.assertEqual(Einstellungen.aktuell().vordrucke_ohne_entwurf, ["einwilligung@rg"])
        # die gemeinsame Vorlage (DSKM) trägt das Wasserzeichen weiter
        d = self.anmelden("dskm").get("/api/vorlagen/einwilligung/").json()
        self.assertEqual((d["entwurfsmodus"]["aus"], d["entwurfsmodus"]["aktiv"]), (False, True))
        # beim Ablegen der eigenen Vorlage entfällt der Eintrag
        c.post("/api/vorlagen/einwilligung/firma/", {"eigene": False}, format="json")
        self.assertEqual(Einstellungen.aktuell().vordrucke_ohne_entwurf, [])

    def test_rgc_vorlagen_nur_in_der_regeneration_clinic(self):
        from vorlagen.felder import RGC_ARTEN

        c = self.anmelden("dskm")
        arten = [v["art"] for v in c.get("/api/vorlagen/").json()]
        self.assertFalse([a for a in arten if a.startswith("rgc_")])
        self.assertEqual(c.get("/api/vorlagen/rgc_erklaerung_at/").status_code, 404)
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/erklaerung-pdf/?art=rgc_erklaerung_at").status_code, 400)
        self.assertEqual(c.get(f"/api/patienten/{self.patient.id}/datenschutz/").json()["vordrucke"], [])
        self.assertFalse(Dokumentvorlage.objects.filter(art__startswith="rgc_").exists())
        c = self.anmelden("rg")
        liste = {v["art"]: v for v in c.get("/api/vorlagen/").json()}
        self.assertEqual([a for a in liste if a.startswith("rgc_")], list(RGC_ARTEN))
        v = liste["rgc_erklaerung_at"]
        self.assertEqual((v["gruppe"], v["aktiv"]["firma"], v["firma"]["gebunden"], v["firma"]["moeglich"],
                          v["entwurfsmodus"]["aktiv"]), ("rgc", "rg", True, False, True))
        self.assertEqual(v["name"], "Patientenerklärung Österreich (Stundung)")
        self.assertTrue(Dokumentvorlage.objects.filter(art="rgc_erklaerung_at", firma=self.rg, status="aktiv").exists())
        vordrucke = c.get(f"/api/patienten/{self.rg_patient.id}/datenschutz/").json()["vordrucke"]
        self.assertEqual([v["art"] for v in vordrucke], list(RGC_ARTEN))
        self.assertTrue(all(v["entwurf"] and v["version"] == 1 for v in vordrucke))
        # PDF jeder Vorlage für einen Patienten der RGC, wörtlich aus der Word-Vorlage, mit Wasserzeichen
        for art in RGC_ARTEN:
            with self.subTest(art=art):
                r = c.get(f"/api/patienten/{self.rg_patient.id}/erklaerung-pdf/?art={art}")
                self.assertEqual((r.status_code, r["X-EPM-Vorlage-Entwurf"]), (200, "1"), r.content[:200])
                self.assertTrue(r.content.startswith(b"%PDF"))
        if PDFTOTEXT:
            r = c.get(f"/api/patienten/{self.rg_patient.id}/erklaerung-pdf/?art=rgc_erklaerung_at")
            self.assertIn("ENTWURF", wasserzeichen(r.content))
            text = kompakt(pdf_text(r.content))
            for erwartet in ["Patientenerklärung bei Aufnahme (Österreich)", "Vorlage 01 · Version 6 · Stand 10/2026",
                             "Klinik, Karla", "01.01.1970", "ÖGK Wien", "1234 010170", "Leistungserbringerin",
                             "Regeneration Clinic SIA · Jāņa Asara iela 3", "Was die Stundung für Sie bedeutet",
                             "Rechtsstellung der Klinik im Überblick", "12. Stundung des erwarteten Kassenanteils",
                             "Unterschrift Patient/in – Zedent/in (vollständig lesbar)"]:
                self.assertIn(kompakt(erwartet), text, erwartet)
        # Entwurfsmodus abschalten gilt für die Vorlage der RGC
        r = c.post("/api/vorlagen/rgc_erklaerung_at/entwurfsmodus/", {"aus": True}, format="json")
        self.assertEqual((r.status_code, r.json()["entwurfsmodus"]["aktiv"]), (200, False))
        r = c.get(f"/api/patienten/{self.rg_patient.id}/erklaerung-pdf/?art=rgc_erklaerung_at")
        self.assertEqual(r["X-EPM-Vorlage-Entwurf"], "0")
        if PDFTOTEXT:
            self.assertNotIn("Hinweis zur Vorlage", pdf_text(r.content))

    def test_medikationsplan_im_querformat(self):
        c = self.anmelden("dskm")
        d = c.get("/api/vorlagen/medikationsplan/").json()
        self.assertEqual((d["ausrichtung"], d["querformat_moeglich"], d["aktiv"]["ausrichtung"]), ("quer", True, "quer"))
        self.assertFalse(c.get("/api/vorlagen/infusionsplan/").json()["querformat_moeglich"])
        r = c.get(f"/api/patienten/{self.patient.id}/medikationsplan-pdf/")
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertEqual(self.seitenformat(r.content), "quer")
        # Vorschau und Entwurf im Hochformat; ungültige Angabe abgewiesen
        bloecke = c.get("/api/vorlagen/medikationsplan/entwurf/").json()["bloecke"]
        r = c.post("/api/vorlagen/medikationsplan/vorschau/", {"patient": self.patient.id, "bloecke": bloecke,
                                                              "ausrichtung": "hoch"}, format="json")
        self.assertEqual((r.status_code, self.seitenformat(r.content)), (200, "hoch"))
        self.assertEqual(c.put("/api/vorlagen/medikationsplan/entwurf/", {"bloecke": bloecke, "ausrichtung": "schraeg"},
                               format="json").status_code, 400)
        r = c.put("/api/vorlagen/medikationsplan/entwurf/", {"bloecke": bloecke, "ausrichtung": "hoch"}, format="json")
        self.assertEqual((r.status_code, r.json()["ausrichtung"]), (200, "hoch"))
        r = c.post("/api/vorlagen/medikationsplan/veroeffentlichen/")
        self.assertEqual((r.json()["aktiv"]["version"], r.json()["ausrichtung"]), (2, "hoch"))
        self.assertEqual(self.seitenformat(c.get(f"/api/patienten/{self.patient.id}/medikationsplan-pdf/").content), "hoch")
