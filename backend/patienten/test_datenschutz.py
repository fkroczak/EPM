"""Datenschutz (DSGVO) gegen die echte Datenbank: Erklärungen, Anfragen mit Frist, Einschränkung und Einsicht,
Aufbewahrung, Kopie der Akte, endgültiges Löschen mit Löschprotokoll, Freigabe eines Plans auf Anordnung."""
import io
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Rolle, User
from audit.bereinigung import OHNE_GRUND, bereinigen
from audit.models import SystemEreignis, protokolliere
from audit.schutz import wartungsmodus
from audit.texte import beschreibung
from epm.pruefhilfen import KENNWORT, TMP, Grundlage, benutzer, client_fuer, mit_zweitem_faktor
from infusionen.models import Infusionsplan
from infusionen.tests import praeparat
from stammdaten.models import Einstellungen
from vorlagen.tests import PDFTOTEXT, kompakt, pdf_text, wasserzeichen

from .datenschutz import akte_loeschen, akten_entfernen, akten_nachholen, lies_akten
from .models import (Akteneinsicht, Bezugsperson, Datenschutzanfrage, Dokument, DokumentVorgang, Erklaerung,
                     Gewichtsmessung, Kontakt, Loeschprotokoll, Patient, Termin, plus_jahre, plus_monate)
from .testdaten import testdaten_zuruecksetzen

A = SystemEreignis.Art
LISTE = Path(TMP) / "loeschliste-akten" / "loeschliste.jsonl"


def eintraege(antwort):
    daten = antwort.json()
    return daten["results"] if isinstance(daten, dict) else daten


class DatenschutzGrundlage(Grundlage):
    def abschliessen(self, patient=None, datum=None):
        """Akte über die API abschließen (wie in der Oberfläche; so steht der Abschluss auch im Verlauf)."""
        p = patient or self.patient
        r = client_fuer(self.mitarbeiter).post(
            f"/api/patienten/{p.id}/abschliessen/",
            {"anlass": "therapie_beendet", **({"datum": str(datum)} if datum else {})}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        p.refresh_from_db()
        return p

    def pruefen(self, client=None):
        return (client or client_fuer(self.mitarbeiter)).get("/api/startseite/").json()["pruefen"]

    def plan_entwurf(self, patient=None):
        m = client_fuer(self.mediziner)
        r = m.post("/api/infusionsplaene/entwurf/", {"patient": (patient or self.patient).id}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        r = m.patch(f"/api/infusionsplaene/{r.json()['id']}/", {
            "glucose_praeparat": praeparat("Glucose", "70 %").id, "glucose_g": "200",
            "aminosaeuren_praeparat": praeparat("Glamin").id, "aminosaeuren_g": "70",
            "lipide_praeparat": praeparat("Clinoleic").id, "lipide_g": "40", "laufzeit_h": "12"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["id"]


class Fristen(DatenschutzGrundlage):
    def test_aufbewahrung_und_frist_der_anfragen(self):
        self.assertEqual(plus_jahre(date(2024, 2, 29), 10), date(2034, 2, 28))
        self.assertEqual(plus_monate(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(plus_monate(date(2026, 11, 15), 3), date(2027, 2, 15))
        heute = timezone.localdate()
        p = self.patient
        # ohne Abschluss läuft keine Frist
        self.assertEqual((p.aufbewahrung()["bis"], p.aufbewahrung()["abgelaufen"]), (None, False))
        p = self.abschliessen(datum=heute - timedelta(days=30))
        a = p.aufbewahrung()
        self.assertEqual((a["jahre"], a["bis"], a["abgelaufen"]), (10, plus_jahre(p.abgeschlossen_am, 10), False))
        # im Einzelfall länger (nur wenn später als die reguläre Frist)
        p.aufbewahrung_bis = plus_jahre(heute, 15)
        self.assertEqual(p.aufbewahrung()["bis"], plus_jahre(heute, 15))
        p.aufbewahrung_bis = heute
        self.assertEqual(p.aufbewahrung()["bis"], a["regulaer_bis"])
        # abgelaufen: Abschluss vor mehr als zehn Jahren; die eingestellte Dauer gilt sofort
        p.aufbewahrung_bis = None
        p.abgeschlossen_am = plus_jahre(heute, -10) - timedelta(days=2)
        self.assertTrue(p.aufbewahrung()["abgelaufen"])
        e = Einstellungen.aktuell()
        e.aufbewahrung_jahre = 30
        e.save()
        self.assertFalse(p.aufbewahrung()["abgelaufen"])
        # Anfragen: ein Monat, verlängert drei Monate (Art. 12 Abs. 3 DSGVO)
        anfrage = Datenschutzanfrage(patient=p, art="auskunft", eingegangen_am=date(2026, 1, 31))
        self.assertEqual(anfrage.frist_bis, date(2026, 2, 28))
        anfrage.frist_verlaengert = True
        self.assertEqual(anfrage.frist_bis, date(2026, 4, 30))
        anfrage.eingegangen_am = heute - timedelta(days=100)
        self.assertTrue(anfrage.ueberfaellig)
        anfrage.erledigt_am = timezone.now()
        self.assertFalse(anfrage.ueberfaellig)

    def test_einstellungen(self):
        m = client_fuer(self.mediziner)
        e = m.get("/api/einstellungen/").json()
        self.assertEqual((e["aufbewahrung_jahre"], e["abschluss_pruefen_monate"], e["protokoll_aufbewahrung_jahre"]),
                         (10, 24, 0))
        self.assertEqual(e["pflicht_erklaerungen"], ["datenschutzinformation", "einwilligung", "schweigepflichtentbindung"])
        self.assertEqual(m.patch("/api/einstellungen/", {"aufbewahrung_jahre": 0}, format="json").status_code, 400)
        self.assertEqual(m.patch("/api/einstellungen/", {"abschluss_pruefen_monate": 0}, format="json").status_code, 400)
        self.assertEqual(m.patch("/api/einstellungen/", {"pflicht_erklaerungen": ["vollmacht"]}, format="json").status_code, 400)
        r = m.patch("/api/einstellungen/", {"aufbewahrung_jahre": 30, "pflicht_erklaerungen": ["einwilligung", "datenschutzinformation"]},
                    format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["pflicht_erklaerungen"], ["datenschutzinformation", "einwilligung"])
        text = beschreibung(SystemEreignis.objects.filter(art=A.STAMMDATEN).first())
        self.assertIn("von 10 auf 30 Jahre geändert", text)

    def test_abschluss_pruefen(self):
        """Akten ohne Kontakt seit der eingestellten Zeit: abschließen? Sonst beginnt die Aufbewahrungsfrist nie."""
        ruhend = Patient.objects.create(nachname="Ruhend", vorname="Rita", geburtsdatum="1970-01-01")
        Patient.objects.filter(pk=ruhend.pk).update(angelegt_am=timezone.now() - timedelta(days=30 * 30))
        c = client_fuer(self.mitarbeiter)
        self.assertEqual((self.pruefen()["abschluss_pruefen"], self.pruefen()["abschluss_monate"]), (1, 24))
        self.assertEqual([p["id"] for p in eintraege(c.get("/api/patienten/?pruefen=abschluss_pruefen"))], [ruhend.id])
        self.neuer_kontakt(patient=ruhend)
        self.assertEqual(self.pruefen()["abschluss_pruefen"], 0)


class Erklaerungen(DatenschutzGrundlage):
    def test_erfassen_nachhalten_widerrufen(self):
        c = client_fuer(self.mitarbeiter)
        pid, heute = self.patient.id, timezone.localdate()
        akte = f"/api/patienten/{pid}/"
        kopf = c.get(akte).json()["kopf"]["erklaerungen"]
        self.assertEqual(kopf["fehlt"], ["datenschutzinformation", "einwilligung", "schweigepflichtentbindung"])
        self.assertEqual(kopf["stand"]["einwilligung"]["status"], "nicht_erfasst")
        self.assertEqual(self.pruefen()["erklaerungen_fehlen"], 1)

        r = c.post("/api/erklaerungen/", {"patient": pid, "art": "datenschutzinformation", "erteilt_am": str(heute)},
                   format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["status"], r.json()["vorlage_version"], r.json()["art_name"]),
                         ("liegt_vor", 1, "Datenschutzinformation"))
        # mit dem unterschriebenen Blatt als Scan: liegt danach als Dokument in der Akte
        scan = SimpleUploadedFile("einwilligung.pdf", b"%PDF-1.4 unterschrieben", content_type="application/pdf")
        r = c.post("/api/erklaerungen/", {"patient": pid, "art": "einwilligung", "erteilt_am": str(heute), "datei": scan},
                   format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        einwilligung = r.json()
        dok = Dokument.objects.get(pk=einwilligung["dokument"])
        self.assertEqual((dok.typ.wert, dok.patient_id, dok.pfad.is_file()), ("Einwilligung/Datenschutz", pid, True))
        self.assertIn("Einwilligung", dok.titel)
        # Plausibilität und Dateityp
        r = c.post("/api/erklaerungen/", {"patient": pid, "art": "einwilligung", "erteilt_am": str(heute + timedelta(days=1))},
                   format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["erteilt_am"]))
        r = c.post("/api/erklaerungen/", {"patient": pid, "art": "einwilligung", "erteilt_am": str(heute),
                                          "datei": SimpleUploadedFile("x.exe", b"MZ\x00\x01\x02")}, format="multipart")
        self.assertEqual((r.status_code, list(r.json())), (400, ["datei"]))
        # Rechte: Betrachter liest nur; Admin schreibt nur bei Testpatienten
        daten = {"patient": pid, "art": "einwilligung", "erteilt_am": str(heute)}
        self.assertEqual(client_fuer(self.betrachter).post("/api/erklaerungen/", daten, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.admin).post("/api/erklaerungen/", daten, format="json").status_code, 403)
        self.assertEqual(len(client_fuer(self.betrachter).get(f"/api/erklaerungen/?patient={pid}").json()), 2)
        # nicht löschen, Art nicht ändern
        url = f"/api/erklaerungen/{einwilligung['id']}/"
        self.assertEqual(c.delete(url).status_code, 405)
        self.assertEqual(c.patch(url, {"art": "schweigepflichtentbindung"}, format="json").status_code, 400)
        self.assertEqual(c.patch(url, {"notiz": "Original im Ordner"}, format="json").status_code, 200)
        self.assertEqual(c.get(akte).json()["kopf"]["erklaerungen"]["fehlt"], ["schweigepflichtentbindung"])

        # Schweigepflichtentbindung widerrufen: Hinweis auf „Auskunft erlaubt“ bei den Bezugspersonen
        Bezugsperson.objects.create(patient=self.patient, name="Maria Echt", auskunft_erlaubt=True)
        entbindung = c.post("/api/erklaerungen/", {"patient": pid, "art": "schweigepflichtentbindung",
                                                   "erteilt_am": str(heute)}, format="json").json()
        self.assertEqual(self.pruefen()["erklaerungen_fehlen"], 0)
        r = c.post(f"/api/erklaerungen/{entbindung['id']}/widerrufen/", {"notiz": "telefonisch"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["status"], r.json()["widerrufen_am"]), ("widerrufen", str(heute)))
        self.assertIn("Auskunft erlaubt", r.json()["hinweis"])
        self.assertEqual(c.post(f"/api/erklaerungen/{entbindung['id']}/widerrufen/", {}, format="json").status_code, 400)
        kopf = c.get(akte).json()["kopf"]["erklaerungen"]
        self.assertEqual((kopf["stand"]["schweigepflichtentbindung"]["status"], kopf["fehlt"]),
                         ("widerrufen", ["schweigepflichtentbindung"]))
        self.assertEqual(self.pruefen()["erklaerungen_fehlen"], 1)
        self.assertEqual([p["id"] for p in eintraege(c.get("/api/patienten/?pruefen=erklaerungen"))], [pid])
        self.assertTrue(SystemEreignis.objects.filter(art=A.DATENSCHUTZ, details__patient_id=pid).exists())
        # welche Erklärungen vorliegen sollen, ist einstellbar
        r = client_fuer(self.mediziner).patch("/api/einstellungen/", {"pflicht_erklaerungen": ["einwilligung"]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.pruefen()["erklaerungen_fehlen"], 0)
        # alles steht im Verlauf der Akte
        verlauf = c.get(akte + "verlauf/?bereich=erklaerungen").json()
        self.assertEqual([v["aktion"] for v in verlauf], ["widerrufen", "angelegt", "geändert", "angelegt", "angelegt"])
        self.assertIn("widerrufen am", verlauf[0]["beschreibung"])

    def test_auch_bei_abgeschlossener_akte(self):
        """Ein Widerruf kann nach dem Abschluss eingehen; ein neues Dokument kommt aber nicht in die Akte."""
        c = client_fuer(self.mitarbeiter)
        heute = timezone.localdate()
        self.abschliessen()
        r = c.post("/api/erklaerungen/", {"patient": self.patient.id, "art": "einwilligung", "erteilt_am": str(heute)},
                   format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(c.post(f"/api/erklaerungen/{r.json()['id']}/widerrufen/", {}, format="json").status_code, 200)
        scan = SimpleUploadedFile("e.pdf", b"%PDF-1.4 x", content_type="application/pdf")
        r = c.post("/api/erklaerungen/", {"patient": self.patient.id, "art": "einwilligung", "erteilt_am": str(heute),
                                          "datei": scan}, format="multipart")
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(Dokument.objects.filter(patient=self.patient).count(), 0)

    def test_pdf_aus_der_dokumentvorlage(self):
        c = client_fuer(self.mitarbeiter)
        url = f"/api/patienten/{self.patient.id}/erklaerung-pdf/"
        self.assertEqual(c.get(url).status_code, 400)
        self.assertEqual(c.get(url + "?art=vollmacht").status_code, 400)
        r = c.get(url + "?art=einwilligung")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r["Content-Type"], r["X-EPM-Vorlage-Entwurf"], r["X-EPM-Vorlage-Version"]), ("application/pdf", "1", "1"))
        self.assertTrue(r.content.startswith(b"%PDF"))
        if PDFTOTEXT:
            # die mitgelieferte Startvorlage ist ungeprüft: Wasserzeichen ENTWURF, Lücken in eckigen Klammern
            self.assertIn("ENTWURF", wasserzeichen(r.content))
            text = kompakt(pdf_text(r.content))
            for erwartet in ["Echt, Anna", "Einwilligung in die Verarbeitung meiner Daten", "[Zwecke eintragen]",
                             "Art. 7 Abs. 3 DSGVO", "Ort, Datum, Unterschrift"]:
                self.assertIn(kompakt(erwartet), text)
        for art in ("datenschutzinformation", "schweigepflichtentbindung"):
            self.assertTrue(c.get(f"{url}?art={art}").content.startswith(b"%PDF"), art)
        self.assertEqual(SystemEreignis.objects.filter(art=A.EXPORT, details__patient_id=self.patient.id).count(), 3)
        # ein Mensch bearbeitet und veröffentlicht die Vorlage → ohne Wasserzeichen
        entwurf = c.get("/api/vorlagen/einwilligung/entwurf/").json()
        bloecke = [b for b in entwurf["bloecke"] if b["id"] != "hinweis"]
        self.assertEqual(c.put("/api/vorlagen/einwilligung/entwurf/", {"bloecke": bloecke}, format="json").status_code, 200)
        self.assertEqual(c.post("/api/vorlagen/einwilligung/veroeffentlichen/").status_code, 200)
        r = c.get(url + "?art=einwilligung")
        self.assertEqual((r["X-EPM-Vorlage-Entwurf"], r["X-EPM-Vorlage-Version"]), ("0", "2"))
        if PDFTOTEXT:
            self.assertNotIn("ENTWURF", wasserzeichen(r.content))
        stand = c.get(f"/api/patienten/{self.patient.id}/datenschutz/").json()["vorlagen"]
        self.assertEqual(stand["einwilligung"], {"version": 2, "entwurf": False})
        self.assertTrue(stand["datenschutzinformation"]["entwurf"])
        # eine neu erfasste Erklärung hält den Stand der Vorlage fest
        r = c.post("/api/erklaerungen/", {"patient": self.patient.id, "art": "einwilligung",
                                          "erteilt_am": str(timezone.localdate())}, format="json")
        self.assertEqual(r.json()["vorlage_version"], 2)


class Anfragen(DatenschutzGrundlage):
    def test_ablauf_mit_frist(self):
        c, m = client_fuer(self.mitarbeiter), client_fuer(self.mediziner)
        pid, heute = self.patient.id, timezone.localdate()
        r = c.post("/api/datenschutzanfragen/", {"patient": pid, "art": "auskunft", "gestellt_von": "Patientin selbst",
                                                 "inhalt": "Bittet um eine Kopie der Akte"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        a = r.json()
        self.assertEqual((a["frist_bis"], a["ist_offen"], a["ueberfaellig"]), (str(plus_monate(heute, 1)), True, False))
        self.assertEqual(self.pruefen()["datenschutz_anfragen"], 1)
        self.assertEqual(c.get(f"/api/patienten/{pid}/").json()["kopf"]["datenschutz_anfragen"], 1)
        url = f"/api/datenschutzanfragen/{a['id']}/"
        # Frist verlängern nur mit Grund (er ist der Person mitzuteilen)
        r = c.patch(url, {"frist_verlaengert": True}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["verlaengerung_grund"]))
        r = c.patch(url, {"frist_verlaengert": True, "verlaengerung_grund": "Sehr umfangreiche Akte"}, format="json")
        self.assertEqual((r.status_code, r.json()["frist_bis"]), (200, str(plus_monate(heute, 3))))
        self.assertEqual(client_fuer(self.betrachter).post("/api/datenschutzanfragen/", {"patient": pid, "art": "auskunft"},
                                                           format="json").status_code, 403)
        self.assertEqual(client_fuer(self.admin).post("/api/datenschutzanfragen/", {"patient": pid, "art": "auskunft"},
                                                      format="json").status_code, 403)
        # erledigen nur mit „Anfragen entscheiden“; Ablehnung nur mit Begründung
        self.assertEqual(c.post(url + "erledigen/", {"ergebnis": "erfuellt"}, format="json").status_code, 403)
        r = m.post(url + "erledigen/", {"ergebnis": "abgelehnt"}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["begruendung"]))
        r = m.post(url + "erledigen/", {"ergebnis": "erfuellt", "mitgeteilt_am": str(heute)}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["ist_offen"], r.json()["ergebnis_name"], r.json()["mitgeteilt_am"]),
                         (False, "erfüllt", str(heute)))
        self.assertEqual(m.post(url + "erledigen/", {"ergebnis": "erfuellt"}, format="json").status_code, 400)
        self.assertEqual(c.patch(url, {"inhalt": "nachträglich"}, format="json").status_code, 400)
        self.assertEqual(c.delete(url).status_code, 405)
        self.assertEqual(self.pruefen()["datenschutz_anfragen"], 0)
        verlauf = c.get(f"/api/patienten/{pid}/verlauf/?bereich=datenschutz").json()
        self.assertEqual([v["aktion"] for v in verlauf], ["erledigt", "Frist verlängert", "angelegt"])

    def test_loeschung_wird_eingeschraenkt_statt_geloescht(self):
        """Steht eine Aufbewahrungspflicht entgegen, wird die Verarbeitung eingeschränkt (§ 35 Abs. 3 BDSG)."""
        c, m = client_fuer(self.mitarbeiter), client_fuer(self.mediziner)
        pid = self.patient.id
        a = c.post("/api/datenschutzanfragen/", {"patient": pid, "art": "loeschung"}, format="json").json()
        url = f"/api/datenschutzanfragen/{a['id']}/erledigen/"
        r = m.post(url, {"ergebnis": "erfuellt"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Akte endgültig löschen", r.json()["ergebnis"])
        daten = {"ergebnis": "eingeschraenkt", "begruendung": "Die Akte ist noch bis 2036 aufzubewahren."}
        # in laufender Betreuung nicht möglich
        r = m.post(url, daten, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("abgeschlossene Akten", str(r.json()))
        self.assertTrue(Datenschutzanfrage.objects.get(pk=a["id"]).ist_offen)
        self.abschliessen()
        r = m.post(url, daten, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.ist_eingeschraenkt)
        self.assertEqual(self.patient.einschraenkung_grund, daten["begruendung"])
        # Übersicht: für Datenschutz-Berechtigte, nicht für Betrachter
        u = m.get("/api/datenschutz/").json()
        self.assertEqual([x["nummer"] for x in u["eingeschraenkt"]], [self.patient.nummer])
        self.assertEqual((u["anfragen_offen"], u["darf_entscheiden"]), ([], True))
        self.assertEqual(c.get("/api/datenschutz/").json()["darf_entscheiden"], False)
        self.assertEqual(client_fuer(self.betrachter).get("/api/datenschutz/").status_code, 403)
        # Anfragen zu eingeschränkten Akten sehen nur Datenschutz-Berechtigte
        self.assertEqual(len(c.get(f"/api/datenschutzanfragen/?patient={pid}").json()), 1)
        self.assertEqual(client_fuer(self.betrachter).get(f"/api/datenschutzanfragen/?patient={pid}").json(), [])
        # eine weitere Anfrage (z. B. Auskunft) lässt sich auch jetzt erfassen
        r = c.post("/api/datenschutzanfragen/", {"patient": pid, "art": "auskunft"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(m.get("/api/datenschutz/").json()["anfragen_offen"]), 1)


class Einschraenkung(DatenschutzGrundlage):
    GRUND = "Antrag der Patientin; die Akte ist noch aufzubewahren"

    def test_eingeschraenkte_akte_verschwindet_und_einsicht(self):
        self.neuer_kontakt()
        c, m = client_fuer(self.mitarbeiter), client_fuer(self.mediziner)
        offen = Patient.objects.create(nachname="Offen", vorname="Otto", geburtsdatum="1970-01-01")
        r = m.post(f"/api/patienten/{offen.id}/einschraenken/", {"grund": self.GRUND}, format="json")
        self.assertEqual(r.status_code, 400, r.content)  # laufende Betreuung
        p = self.abschliessen()
        url = f"/api/patienten/{p.id}/"
        self.assertEqual(c.post(url + "einschraenken/", {"grund": self.GRUND}, format="json").status_code, 403)
        self.assertEqual(m.post(url + "einschraenken/", {"grund": "kurz"}, format="json").status_code, 400)
        r = m.post(url + "einschraenken/", {"grund": self.GRUND}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(m.post(url + "einschraenken/", {"grund": self.GRUND}, format="json").status_code, 400)
        # verschwunden: Liste, Suche, Einträge – auch für die Person, die eingeschränkt hat
        for client in (c, m, client_fuer(self.betrachter)):
            self.assertNotIn(p.id, [x["id"] for x in eintraege(client.get("/api/patienten/?status=abgeschlossen"))])
            self.assertEqual(eintraege(client.get("/api/patienten/?suche=Echt")), [])
            self.assertEqual(eintraege(client.get(f"/api/kontakte/?patient={p.id}")), [])
            r = client.get(url)
            self.assertEqual((r.status_code, r.json()["eingeschraenkt"], r.json()["nummer"]), (403, True, p.nummer))
            self.assertNotIn("nachname", r.json())
            self.assertEqual(client.get(url + "verlauf/").status_code, 404)
            self.assertEqual(client.get(url + "pdf/").status_code, 404)
        self.assertEqual((m.get(url).json()["darf_einsicht"], c.get(url).json()["darf_einsicht"]), (True, False))
        self.assertEqual(c.get("/api/patienten/zaehler/").json()["abgeschlossen"], 0)
        # der Stand zum Datenschutz bleibt für Berechtigte lesbar (z. B. um eine Anfrage zu bearbeiten)
        self.assertEqual(c.get(url + "datenschutz/").json()["einschraenkung"]["grund"], self.GRUND)
        self.assertEqual(client_fuer(self.betrachter).get(url + "datenschutz/").status_code, 403)

        # Einsicht: nur mit „entscheiden“, mit Grund, nur für diese Person, steht im Audit-Log
        einsicht = {"grund": "Rückfrage des Hausarztes zur früheren Therapie"}
        self.assertEqual(c.post(url + "einsicht/", einsicht, format="json").status_code, 403)
        self.assertEqual(m.post(url + "einsicht/", {"grund": "x"}, format="json").status_code, 400)
        # Admins schreiben nur bei Testpatienten – und sehen eingeschränkte echte Akten auch nicht ein
        self.assertEqual(client_fuer(self.admin).post(url + "einsicht/", einsicht, format="json").status_code, 403)
        r = m.post(url + "einsicht/", einsicht, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((m.get(url).status_code, m.get(url).json()["ist_eingeschraenkt"]), (200, True))
        self.assertEqual(len(eintraege(m.get(f"/api/kontakte/?patient={p.id}"))), 1)
        self.assertEqual(c.get(url).status_code, 403)
        self.assertEqual(client_fuer(benutzer("zweiter", Rolle.MEDIZINER)).get(url).status_code, 403)
        e = SystemEreignis.objects.get(art=A.AKTE_EINSICHT)
        self.assertEqual((e.benutzer, e.details["grund"], e.details["patient_id"]), (self.mediziner, einsicht["grund"], p.id))
        # die Einsicht läuft ab
        Akteneinsicht.objects.update(bis=timezone.now() - timedelta(seconds=1))
        self.assertEqual(m.get(url).status_code, 403)

        # Aufheben: vorher wird die betroffene Person unterrichtet (Art. 18 Abs. 3 DSGVO)
        aufheben = {"grund": "Patientin wünscht die weitere Betreuung"}
        self.assertEqual(c.post(url + "einschraenkung-aufheben/", aufheben, format="json").status_code, 403)
        r = m.post(url + "einschraenkung-aufheben/", aufheben, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["unterrichtet_am"]))
        r = m.post(url + "einschraenkung-aufheben/", {**aufheben, "unterrichtet_am": str(timezone.localdate())}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((c.get(url).status_code, c.get(url).json()["ist_eingeschraenkt"]), (200, False))
        self.assertEqual(m.get("/api/datenschutz/").json()["eingeschraenkt"], [])
        aktionen = [v["aktion"] for v in c.get(url + "verlauf/?bereich=stammdaten").json()]
        self.assertEqual(aktionen[:3], ["Einschränkung aufgehoben", "Verarbeitung eingeschränkt", "abgeschlossen"])
        self.assertEqual(list(SystemEreignis.objects.filter(art__in=[A.AKTE_EINGESCHRAENKT, A.AKTE_EINSCHRAENKUNG_AUFGEHOBEN])
                              .order_by("id").values_list("art", flat=True)),
                         [A.AKTE_EINGESCHRAENKT, A.AKTE_EINSCHRAENKUNG_AUFGEHOBEN])
        # ohne Unterrichtung nur mit Begründung, warum sie entfällt
        m.post(url + "einschraenken/", {"grund": self.GRUND}, format="json")
        r = m.post(url + "einschraenkung-aufheben/", {**aufheben, "unterrichtung_entfaellt": "Patientin ist verstorben"},
                   format="json")
        self.assertEqual(r.status_code, 200, r.content)

    def test_aufbewahrung_im_einzelfall_verlaengern(self):
        c, m = client_fuer(self.mitarbeiter), client_fuer(self.mediziner)
        heute = timezone.localdate()
        p = self.abschliessen(datum=heute - timedelta(days=100))
        url = f"/api/patienten/{p.id}/"
        regulaer = plus_jahre(p.abgeschlossen_am, 10)
        self.assertEqual(c.get(url).json()["aufbewahrung"]["bis"], str(regulaer))
        grund = "Laufendes Verfahren vor dem Sozialgericht"
        r = m.post(url + "aufbewahrung/", {"bis": str(heute + timedelta(days=5)), "grund": grund}, format="json")
        self.assertEqual(r.status_code, 400)  # die reguläre Frist läuft ohnehin länger
        bis = plus_jahre(heute, 12)
        self.assertEqual(c.post(url + "aufbewahrung/", {"bis": str(bis), "grund": grund}, format="json").status_code, 403)
        self.assertEqual(m.post(url + "aufbewahrung/", {"bis": str(bis)}, format="json").status_code, 400)
        r = m.post(url + "aufbewahrung/", {"bis": str(bis), "grund": grund}, format="json")
        self.assertEqual((r.status_code, r.json()["aufbewahrung"]["bis"]), (200, str(bis)))
        a = c.get(url).json()["aufbewahrung"]
        self.assertEqual((a["verlaengert_bis"], a["grund"], a["regulaer_bis"]), (str(bis), grund, str(regulaer)))
        self.assertEqual(c.get(url + "verlauf/?bereich=stammdaten").json()[0]["aktion"], "Aufbewahrung verlängert")
        r = m.post(url + "aufbewahrung/", {"bis": None}, format="json")
        self.assertEqual((r.status_code, r.json()["aufbewahrung"]["bis"]), (200, str(regulaer)))


class Aktenkopie(DatenschutzGrundlage):
    def test_kopie_als_zip(self):
        c = client_fuer(self.mitarbeiter)
        pid, nummer = self.patient.id, self.patient.nummer
        self.neuer_kontakt()
        self.assertEqual(c.post("/api/gewichte/", {"patient": pid, "gewicht_kg": "61.5"}, format="json").status_code, 201)
        brief = SimpleUploadedFile("brief.pdf", b"%PDF-1.4 Brief", content_type="application/pdf")
        r = c.post("/api/dokumente/", {"patient": pid, "titel": "Arztbrief vom Hausarzt", "datei": brief}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        c.post("/api/erklaerungen/", {"patient": pid, "art": "einwilligung", "erteilt_am": str(timezone.localdate())},
               format="json")
        url = f"/api/patienten/{pid}/kopie/"
        self.assertEqual(client_fuer(self.betrachter).get(url).status_code, 403)
        r = c.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/zip")
        self.assertIn(f"Aktenkopie-{nummer}-", r["Content-Disposition"])
        z = zipfile.ZipFile(io.BytesIO(b"".join(r.streaming_content)))
        namen = z.namelist()
        for erwartet in (f"Akte-{nummer}.pdf", f"Verlauf-{nummer}.pdf", "LIESMICH.txt"):
            self.assertIn(erwartet, namen)
        dokumente = [n for n in namen if n.startswith("Dokumente/")]
        self.assertEqual(len(dokumente), 1)
        self.assertTrue(dokumente[0].endswith("brief.pdf"))
        self.assertEqual(z.read(dokumente[0]), b"%PDF-1.4 Brief")  # das Original, unverändert
        self.assertIn("1 Dokumente im Original", z.read("LIESMICH.txt").decode())
        akte = z.read(f"Akte-{nummer}.pdf")
        self.assertTrue(akte.startswith(b"%PDF"))
        if PDFTOTEXT:
            text = kompakt(pdf_text(akte))
            for erwartet in ["Kopie der Akte", "Echt, Anna", "61,5 kg", "Hallo", "Arztbrief vom Hausarzt",
                             "Einwilligung in die Datenverarbeitung", "liegt vor"]:
                self.assertIn(kompakt(erwartet), text)
        e = SystemEreignis.objects.get(art=A.EXPORT, details__was="Kopie der Akte")
        self.assertEqual((e.details["patient_id"], e.details["dokumente"]), (pid, 1))
        self.assertIn("Kopie der Akte als ZIP", beschreibung(e))
        d = c.get(f"/api/patienten/{pid}/datenschutz/").json()
        self.assertEqual(len(d["kopien"]), 1)
        self.assertFalse(d["loeschen"]["moeglich"])


@override_settings(EPM_LOESCHLISTE=LISTE)
class AkteLoeschen(DatenschutzGrundlage):
    def setUp(self):
        LISTE.unlink(missing_ok=True)

    def gefuellte_akte(self):
        """Akte mit Einträgen aller Art, zwei Plänen (einer auf Anordnung mit Nachweis) und Dokumenten, die zwischen
        dieser und einer anderen Akte gewechselt haben."""
        c, m = client_fuer(self.mitarbeiter), client_fuer(self.mediziner)
        p = Patient.objects.create(nachname="Loeschbar", vorname="Lena", geburtsdatum="1950-05-05")
        heute = timezone.localdate()
        self.neuer_kontakt(patient=p)
        self.assertEqual(c.post("/api/gewichte/", {"patient": p.id, "gewicht_kg": "58.0"}, format="json").status_code, 201)
        self.assertEqual(c.post("/api/termine/", {"patient": p.id, "art": "wiedervorlage", "titel": "Rückruf",
                                                  "faellig_am": str(heute + timedelta(days=3))}, format="json").status_code, 201)
        Bezugsperson.objects.create(patient=p, name="Ludwig Loeschbar")
        scan = SimpleUploadedFile("e.pdf", b"%PDF-1.4 Einwilligung", content_type="application/pdf")
        self.assertEqual(c.post("/api/erklaerungen/", {"patient": p.id, "art": "einwilligung", "erteilt_am": str(heute),
                                                       "datei": scan}, format="multipart").status_code, 201)
        # erster Plan: der Mediziner gibt selbst frei; zweiter: Freigabe per E-Mail, abgeschlossen vom Mitarbeiter
        self.assertEqual(m.post(f"/api/infusionsplaene/{self.plan_entwurf(p)}/freigeben/").status_code, 200)
        mail = SimpleUploadedFile("freigabe.txt", b"Plan ist freigegeben. Masin", content_type="text/plain")
        r = c.post(f"/api/infusionsplaene/{self.plan_entwurf(p)}/abschliessen/",
                   {"freigegeben_von": self.mediziner.id, "freigegeben_am": str(heute), "weg": "email", "nachweis": mail},
                   format="multipart")
        self.assertEqual(r.status_code, 200, r.content)

        def hochladen(patient, titel):
            datei = SimpleUploadedFile("brief.pdf", b"%PDF-1.4 " + titel.encode(), content_type="application/pdf")
            r = c.post("/api/dokumente/", {"patient": patient.id, "titel": titel, "datei": datei}, format="multipart")
            self.assertEqual(r.status_code, 201, r.content)
            return Dokument.objects.get(pk=r.json()["id"])

        weg, her = hochladen(p, "Arztbrief Anna Echt"), hochladen(self.patient, "Befund für Lena")
        for dok, ziel in ((weg, self.patient), (her, p)):
            r = m.post(f"/api/dokumente/{dok.id}/umhaengen/", {"patient": ziel.id, "grund": "Verwechslung mit Lena Loeschbar"},
                       format="json")
            self.assertEqual(r.status_code, 200, r.content)
        return p, weg, her

    def test_endgueltig_loeschen_auf_antrag(self):
        from django_otp.oath import totp
        from django_otp.plugins.otp_totp.models import TOTPDevice

        mit_zweitem_faktor(self.mediziner)
        geraet = TOTPDevice.objects.get(user=self.mediziner)

        def code():
            return f"{totp(geraet.bin_key, geraet.step, geraet.t0, geraet.digits):06d}"

        c, m = client_fuer(self.mitarbeiter), client_fuer(self.mediziner)
        p, weg, her = self.gefuellte_akte()
        pid, nummer = p.id, p.nummer
        url = f"/api/patienten/{pid}/"
        # nicht abgeschlossen → nicht löschbar
        r = m.post(url + "loeschen-vorbereiten/")
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn("abgeschlossene Akten", r.json()["fehler"])
        self.abschliessen(p)
        # Frist läuft, kein Antrag → nicht löschbar
        r = m.post(url + "loeschen-vorbereiten/")
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn("Aufbewahrungsfrist läuft bis", r.json()["fehler"])
        r = c.post("/api/datenschutzanfragen/", {"patient": pid, "art": "loeschung", "gestellt_von": "Patientin"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        # nur Mediziner
        self.assertEqual(client_fuer(self.admin).post(url + "loeschen-vorbereiten/").status_code, 403)
        self.assertEqual(c.post(url + "loeschen-vorbereiten/").status_code, 403)
        r = m.post(url + "loeschen-vorbereiten/")
        self.assertEqual(r.status_code, 200, r.content)
        v = r.json()
        self.assertEqual(v["loeschen"]["rechtsgrund"], "antrag")
        self.assertIn("Art. 17 Abs. 3 DSGVO", v["loeschen"]["hinweis"])
        self.assertEqual((v["umfang"]["kontakte"], v["umfang"]["infusionsplaene"], v["umfang"]["dokumente"]), (1, 2, 5))
        grund = "Antrag der Patientin; es besteht keine Aufbewahrungspflicht"
        r = m.post(url + "loeschen/", {"grund": grund, "kennwort": "falsch", "code": code(), "bestaetigung": v["code"]},
                   format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["kennwort"]))
        self.assertEqual(SystemEreignis.objects.filter(art=A.AKTE_LOESCHEN_ABGELEHNT).count(), 1)
        ordner = settings.EPM_DOKUMENTE / str(nummer)
        self.assertTrue(ordner.is_dir())
        with self.captureOnCommitCallbacks(execute=True):
            r = m.post(url + "loeschen/", {"grund": grund, "kennwort": KENNWORT, "code": code(),
                                           "bestaetigung": v["code"].lower()}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["geloescht"], r.json()["nummer"]), (True, nummer))

        # alles weg: Akte, Einträge, Historie, Dateien
        self.assertFalse(Patient.objects.filter(pk=pid).exists())
        self.assertFalse(Patient.history.filter(id=pid).exists())
        for modell in (Kontakt, Gewichtsmessung, Termin, Infusionsplan, Bezugsperson, Erklaerung, Datenschutzanfrage):
            self.assertFalse(modell.objects.filter(patient_id=pid).exists(), modell.__name__)
            self.assertFalse(modell.history.filter(patient_id=pid).exists(), modell.__name__)
        self.assertFalse(ordner.exists())
        self.assertEqual(m.get(url).status_code, 404)
        liste = LISTE.read_text(encoding="utf-8")
        self.assertIn(f'"akte": {pid}', liste)
        self.assertNotIn("Loeschbar", liste)
        # das Dokument, das vorher der anderen Akte zugeordnet wurde, bleibt dort – mit seinen früheren Fassungen;
        # das Dokument, das aus der anderen Akte kam, ist mit gelöscht
        self.assertTrue(Dokument.objects.filter(pk=weg.id, patient=self.patient).exists())
        self.assertGreaterEqual(Dokument.history.filter(id=weg.id).count(), 2)
        self.assertFalse(Dokument.objects.filter(pk=her.id).exists())
        self.assertFalse(Dokument.history.filter(patient_id=pid).exclude(id=weg.id).exists())
        v1, v2 = DokumentVorgang.objects.get(dokument_id=weg.id), DokumentVorgang.objects.get(dokument_id=her.id)
        self.assertEqual((v1.von_patient_id, v1.nach_patient_id, v1.grund), (None, self.patient.id, OHNE_GRUND))
        self.assertEqual((v2.von_patient_id, v2.nach_patient_id, v2.grund), (self.patient.id, None, OHNE_GRUND))
        r = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=dokumente")
        self.assertEqual(r.status_code, 200)
        self.assertIn("von einer anderen Akte übernommen", [x["aktion"] for x in r.json()])
        self.assertNotIn("Loeschbar", json.dumps(r.json(), ensure_ascii=False))

        # Löschprotokoll: Nummer, Rechtsgrund, Umfang – kein Name; unveränderlich
        eintrag = Loeschprotokoll.objects.get()
        self.assertEqual((eintrag.nummer, eintrag.akte_id, eintrag.rechtsgrund, eintrag.geloescht_von, eintrag.grund),
                         (nummer, pid, "antrag", self.mediziner, grund))
        self.assertEqual(eintrag.umfang["kontakte"], 1)
        self.assertIn("antrag_eingegangen_am", eintrag.umfang)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Loeschprotokoll.objects.update(grund="geändert")
        with self.assertRaises(DatabaseError), transaction.atomic():
            Loeschprotokoll.objects.all().delete()
        # Audit-Log: die Einträge bleiben, Namen und Inhalte sind entfernt
        alles = json.dumps(list(SystemEreignis.objects.values("objekt", "details")), ensure_ascii=False, default=str)
        self.assertNotIn("Loeschbar", alles)
        e = SystemEreignis.objects.get(art=A.AKTE_ABGESCHLOSSEN)
        self.assertEqual((e.objekt, e.details.get("entfernt"), e.details.get("anlass")),
                         (f"Akte Nr. {nummer} (gelöscht)", True, "therapie_beendet"))
        self.assertIn("Angaben mit der Akte gelöscht", beschreibung(e))
        g = SystemEreignis.objects.get(art=A.AKTE_GELOESCHT)
        self.assertEqual((g.objekt, g.details["rechtsgrund"], g.benutzer), (f"Akte Nr. {nummer}", "antrag", self.mediziner))
        u = SystemEreignis.objects.get(art=A.DOKUMENT_UMGEHAENGT, objekt=f"Dokument {weg.id}")
        self.assertEqual((u.details["von"], u.details["grund"], u.details["titel"]),
                         (f"gelöschte Akte Nr. {nummer}", OHNE_GRUND, "Arztbrief Anna Echt"))
        # die Nummer wird nicht neu vergeben
        neu = Patient.objects.create(nachname="Neu", vorname="Nina", geburtsdatum="1990-01-01")
        self.assertGreater(neu.nummer, nummer)
        # Übersicht zeigt das Löschprotokoll
        protokoll = m.get("/api/datenschutz/").json()["loeschprotokoll"]
        self.assertEqual([(x["nummer"], x["rechtsgrund"]) for x in protokoll], [(nummer, "antrag")])

    def test_loeschen_nach_ablauf_der_frist(self):
        m = client_fuer(self.mediziner)
        heute = timezone.localdate()
        p = self.abschliessen(datum=plus_jahre(heute, -11))
        url = f"/api/patienten/{p.id}/"
        d = m.get(url + "datenschutz/").json()
        self.assertEqual((d["loeschen"]["moeglich"], d["loeschen"]["rechtsgrund"]), (True, "frist"))
        self.assertTrue(d["aufbewahrung"]["abgelaufen"])
        self.assertEqual([x["nummer"] for x in m.get("/api/datenschutz/").json()["aufbewahrung_abgelaufen"]], [p.nummer])
        # im Einzelfall verlängert → nicht mehr löschbar
        bis = plus_jahre(heute, 2)
        self.assertEqual(m.post(url + "aufbewahrung/", {"bis": str(bis), "grund": "Laufendes Verfahren, Akte wird gebraucht"},
                                format="json").status_code, 200)
        self.assertFalse(m.get(url + "datenschutz/").json()["loeschen"]["moeglich"])
        self.assertEqual(m.post(url + "loeschen-vorbereiten/").status_code, 409)
        self.assertEqual(m.post(url + "aufbewahrung/", {"bis": None}, format="json").status_code, 200)
        # auch eine eingeschränkte Akte wird nach Ablauf der Frist gelöscht (ohne Einsicht)
        self.assertEqual(m.post(url + "einschraenken/", {"grund": "Antrag der Patientin vom letzten Jahr"},
                                format="json").status_code, 200)
        r = m.post(url + "loeschen-vorbereiten/")
        self.assertEqual((r.status_code, r.json()["loeschen"]["rechtsgrund"]), (200, "frist"))
        p.refresh_from_db()
        eintrag = akte_loeschen(p, self.mediziner, "frist", "Aufbewahrungsfrist abgelaufen")
        self.assertEqual((eintrag.rechtsgrund, eintrag.aufbewahrung_bis), ("frist", plus_jahre(p.abgeschlossen_am, 10)))
        self.assertFalse(Patient.objects.filter(pk=p.pk).exists())
        self.assertFalse(Akteneinsicht.objects.exists())

    def test_loeschungen_nach_wiederherstellung_nachholen(self):
        """Eine Sicherung enthält gelöschte Akten noch. Die Löschliste (eigener Ordner, ohne Namen) übersteht die
        Wiederherstellung; beim Start des Backends werden die Löschungen erneut vollzogen."""
        heute = timezone.localdate()
        p = Patient.objects.create(nachname="Wieder", vorname="Da", geburtsdatum="1950-01-01")
        pid, nummer, angelegt = p.id, p.nummer, p.angelegt_am
        self.abschliessen(p, datum=plus_jahre(heute, -11))
        with self.captureOnCommitCallbacks(execute=True):
            akte_loeschen(p, self.mediziner, "frist", "Aufbewahrungsfrist abgelaufen")
        self.assertEqual([(z["akte"], z["nummer"], z["rechtsgrund"]) for z in lies_akten()], [(pid, nummer, "frist")])
        self.assertNotIn("Wieder", LISTE.read_text(encoding="utf-8"))
        nichts = {"akten": 0, "protokoll_ergaenzt": 0, "akten_liste_ergaenzt": 0}
        self.assertEqual(akten_nachholen(), nichts)

        def wiederherstellen(**werte):
            """Stand einer älteren Sicherung: Die Akte ist wieder da, der Protokolleintrag fehlt."""
            with wartungsmodus():
                Loeschprotokoll.objects.all().delete()
            Patient(id=pid, nummer=nummer, nachname="Wieder", vorname="Da", geburtsdatum="1950-01-01",
                    abgeschlossen_am=plus_jahre(heute, -11), abschluss_anlass="therapie_beendet").save()
            if werte:
                Patient.objects.filter(pk=pid).update(**werte)

        # gleiche Kennung und Nummer, aber eine andere Akte (anderer Anlagezeitpunkt): bleibt; das Protokoll wird ergänzt
        wiederherstellen()
        self.assertEqual(akten_nachholen(), {**nichts, "protokoll_ergaenzt": 1})
        self.assertTrue(Patient.objects.filter(pk=pid).exists())
        with wartungsmodus():
            akten_entfernen([pid])
        # dieselbe Akte: wird beim Start erneut gelöscht
        wiederherstellen(angelegt_am=angelegt)
        ausgabe = io.StringIO()
        call_command("epm_loeschungen_nachholen", stdout=ausgabe)
        self.assertIn("akten 1", ausgabe.getvalue())
        self.assertFalse(Patient.objects.filter(pk=pid).exists())
        self.assertFalse(Patient.history.filter(id=pid).exists())
        self.assertEqual(Loeschprotokoll.objects.count(), 1)
        self.assertTrue(SystemEreignis.objects.filter(art=A.AKTE_GELOESCHT, details__nachgezogen=True).exists())
        self.assertEqual(len(lies_akten()), 1)  # das Nachholen trägt nichts doppelt ein
        # geht die Löschliste verloren, wird sie aus dem Löschprotokoll der Datenbank ergänzt
        LISTE.unlink()
        self.assertEqual(akten_nachholen(), {**nichts, "akten_liste_ergaenzt": 1})
        self.assertEqual([z["nummer"] for z in lies_akten()], [nummer])


class FreigabeAufAnordnung(DatenschutzGrundlage):
    """Der Mediziner gibt außerhalb von EPM frei (z. B. per E-Mail), ein Mitarbeiter schließt den Plan ab."""

    def test_abschliessen_nach_freigabe(self):
        c, m = client_fuer(self.mitarbeiter), client_fuer(self.mediziner)
        pid, heute = self.patient.id, timezone.localdate()
        plan_id = self.plan_entwurf()
        url = f"/api/infusionsplaene/{plan_id}/abschliessen/"
        # Auswahl: Mediziner mit dem Recht „freigeben“
        self.assertEqual([x["id"] for x in c.get(f"/api/infusionsplaene/freigebende/?patient={pid}").json()], [self.mediziner.id])
        self.assertEqual(client_fuer(self.betrachter).get("/api/infusionsplaene/freigebende/").status_code, 403)
        basis = {"freigegeben_von": self.mediziner.id, "freigegeben_am": str(heute), "weg": "email"}
        self.assertEqual(client_fuer(self.betrachter).post(url, basis, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.admin).post(url, basis, format="json").status_code, 403)  # echte Akte
        # per E-Mail: ohne Nachweis nicht; freigegeben haben kann nur ein Mediziner; Datum und Weg plausibel
        faelle = [(basis, "nachweis"), ({**basis, "freigegeben_von": self.mitarbeiter.id, "weg": "telefon"}, "freigegeben_von"),
                  ({**basis, "weg": "telefon", "freigegeben_am": str(heute + timedelta(days=1))}, "freigegeben_am"),
                  ({**basis, "weg": "telefon", "freigegeben_am": ""}, "freigegeben_am"), ({**basis, "weg": "system"}, "weg")]
        for daten, feld in faelle:
            with self.subTest(feld=feld):
                r = c.post(url, daten, format="json")
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn(feld, r.json())
        self.assertEqual(Infusionsplan.objects.get(pk=plan_id).status, "entwurf")
        self.assertEqual(Dokument.objects.filter(patient_id=pid).count(), 0)

        mail = SimpleUploadedFile("freigabe.txt", "Von: Masin\nDer Plan ist so freigegeben.".encode(), content_type="text/plain")
        r = c.post(url, {**basis, "nachweis": mail}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        antwort = r.json()
        plan = Infusionsplan.objects.get(pk=plan_id)
        self.assertEqual((plan.status, plan.freigegeben_von, plan.abgeschlossen_von, plan.freigabe_weg, plan.freigabe_datum),
                         ("aktuell", self.mediziner, self.mitarbeiter, "email", heute))
        self.assertEqual((antwort["freigabe_weg_name"], antwort["freigabe_datum"]), ("per E-Mail", str(heute)))
        for teil in ("Geprüft und freigegeben von", "(per E-Mail)", "im System abgeschlossen von"):
            self.assertIn(teil, antwort["freigabevermerk"])
        nachweis = Dokument.objects.get(pk=antwort["freigabe_nachweis"])
        self.assertEqual((nachweis.typ.wert, nachweis.herkunft, nachweis.pfad.is_file()), ("Freigabe", "upload", True))
        if PDFTOTEXT:
            text = kompakt(pdf_text((settings.EPM_DOKUMENTE / plan.pdf_datei).read_bytes()))
            for teil in ("Geprüft und freigegeben von", "(per E-Mail)", "im System abgeschlossen von"):
                self.assertIn(kompakt(teil), text)
        e = SystemEreignis.objects.get(art=A.PLAN_FREIGEGEBEN)
        self.assertEqual((e.benutzer, e.details["auf_anordnung"], e.details["patient_id"]), (self.mitarbeiter, True, pid))
        self.assertIn("per E-Mail", beschreibung(e))
        # Verlauf der Akte: nicht „freigegeben“ durch den Mitarbeiter, sondern abgeschlossen nach Freigabe des Mediziners
        verlauf = [x for x in c.get(f"/api/patienten/{pid}/verlauf/?bereich=infusionsplaene").json()
                   if x["aktion"] == "nach Freigabe abgeschlossen"]
        self.assertEqual(len(verlauf), 1, verlauf)
        self.assertIn(f"freigegeben von {self.mediziner.anzeigename} am {heute:%d.%m.%Y} (per E-Mail)", verlauf[0]["beschreibung"])
        self.assertEqual(verlauf[0]["person_id"], self.mitarbeiter.id)
        self.assertNotIn("freigegeben", [x["aktion"] for x in c.get(f"/api/patienten/{pid}/verlauf/?bereich=infusionsplaene").json()])
        # der Nachweis bleibt bei seinem Plan
        anderer = Patient.objects.create(nachname="Zwei", vorname="Zoe", geburtsdatum="1980-01-01")
        r = m.post(f"/api/dokumente/{nachweis.id}/umhaengen/", {"patient": anderer.id, "grund": "falscher Patient"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Nachweis der Freigabe", r.json()["fehler"])
        # danach unveränderlich
        self.assertEqual(c.post(url, {**basis, "weg": "telefon"}, format="json").status_code, 400)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Infusionsplan.objects.filter(pk=plan_id).update(freigabe_weg="telefon")

        # der Mediziner selbst gibt weiter direkt frei: Vermerk ohne Zusatz
        zweiter = self.plan_entwurf()
        r = m.post(f"/api/infusionsplaene/{zweiter}/freigeben/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["freigabe_weg"], r.json()["abgeschlossen_von_name"]), ("system", None))
        self.assertTrue(r.json()["freigabevermerk"].startswith("Maschinell erstellt, geprüft und freigegeben von"))
        # telefonisch oder persönlich: ohne Nachweis möglich
        dritter = self.plan_entwurf()
        r = c.post(f"/api/infusionsplaene/{dritter}/abschliessen/", {**basis, "weg": "telefon"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("(telefonisch)", r.json()["freigabevermerk"])


class AuditBereinigung(DatenschutzGrundlage):
    def test_aufbewahrung_des_audit_logs(self):
        alt = protokolliere(A.EXPORT, objekt="alter Eintrag")
        with wartungsmodus():
            SystemEreignis.objects.filter(pk=alt.pk).update(zeitpunkt=timezone.now() - timedelta(days=800))
        # der Wartungsmodus endet mit seinem Block: danach ist das Protokoll wieder unveränderlich
        with self.assertRaises(DatabaseError), transaction.atomic():
            SystemEreignis.objects.filter(pk=alt.pk).update(objekt="geändert")
        self.assertEqual(bereinigen()["protokoll"], 0)  # 0 = unbegrenzt aufbewahren
        e = Einstellungen.aktuell()
        e.protokoll_aufbewahrung_jahre = 2
        e.save()
        neu = protokolliere(A.EXPORT, objekt="neuer Eintrag")
        self.assertEqual(bereinigen()["protokoll"], 1)
        self.assertFalse(SystemEreignis.objects.filter(pk=alt.pk).exists())
        self.assertTrue(SystemEreignis.objects.filter(pk=neu.pk).exists())
        b = SystemEreignis.objects.get(art=A.PROTOKOLL_BEREINIGT)
        self.assertEqual((b.details["anzahl"], b.details["jahre"]), (1, 2))
        self.assertIn("1 Einträge älter als 2 Jahre", beschreibung(b))
        with self.assertRaises(DatabaseError), transaction.atomic():
            SystemEreignis.objects.all().delete()


@override_settings(EPM_DOKUMENTE=Path(TMP))
class Testdaten(TestCase):
    def test_zuruecksetzen_mit_umgehaengtem_dokument_und_erklaerungen(self):
        call_command("epm_musterdaten", stdout=io.StringIO())
        tester = User.objects.get(username="test")
        tester.muss_kennwort_aendern = False  # Einmal-Kennwort gilt hier als bereits ersetzt
        self.assertEqual(Erklaerung.objects.filter(patient__ist_test=True).count(), 6)
        self.assertEqual(client_fuer(tester).get("/api/startseite/").json()["pruefen"]["erklaerungen_fehlen"], 4)
        dok = Dokument.objects.filter(patient__ist_test=True, herkunft="upload").first()
        ziel = Patient.objects.filter(ist_test=True).exclude(pk=dok.patient_id).first()
        DokumentVorgang.objects.create(art="umgehaengt", dokument_id=dok.id, von_patient=dok.patient, nach_patient=ziel,
                                       grund="Test", person=tester)
        self.assertEqual(testdaten_zuruecksetzen(), {"geloescht": 6, "angelegt": 6})
        self.assertEqual(DokumentVorgang.objects.count(), 0)
        self.assertEqual(Erklaerung.objects.count(), 6)
        self.assertEqual(Erklaerung.history.count(), 6)
