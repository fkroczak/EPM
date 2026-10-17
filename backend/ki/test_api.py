"""KI (Experimentell): API – Rechte, Firmen, Prüfen, Korrigieren, Konflikte, Übernahme in die Akte, Audit,
Berichtsentwürfe, Administration, Qualität, Evaluation, Datenbank-Rolle des Dienstes."""
import datetime as dt
from decimal import Decimal
from pathlib import Path

from django.db import DatabaseError, connection, transaction
from django.test import override_settings

from accounts.models import Mitgliedschaft, Rolle
from audit.models import SystemEreignis
from befunde.models import Laborbefund, Laborwert
from berichte.models import Bericht
from epm.pruefhilfen import Grundlage, benutzer, client_fuer, echte_anmeldung, mit_zweitem_faktor
from infusionen.models import Infusionsplan
from ki import berichte, evaluation
from ki.models import (KiBerichtsauftrag, KiEinstellung, KiEvaluationsfall, KiEvaluationslauf, KiFeld,
                       KiKorrektur, KiModellversion, KiUebernahme, KiVorgang)
from ki.testhilfen import KI_TMP, Attrappe, dokument
from patienten.models import Diagnose, Medikament, Patient, PatientFirma
from stammdaten.models import Firma, Laborparameter

A = SystemEreignis.Art


@override_settings(EPM_KI=Path(KI_TMP))
class KiApiGrundlage(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.kalium = Laborparameter.objects.get(name="Kalium")
        cls.natrium = Laborparameter.objects.get(name="Natrium")

    def vorgang(self, patient=None, **extra):
        patient = patient or self.patient
        d = dokument(patient, b"%PDF-1.4 " + str(extra.get("nr", 1)).encode(), name="a.pdf", mime="application/pdf")
        v = KiVorgang.objects.create(dokument=d, patient=patient, firma_id=d.firma_id, sha256=d.sha256,
                                     status=extra.pop("status", "zur_pruefung"),
                                     metadaten={"dokumentdatum": "2026-03-12", "absender": "Labor X"},
                                     dokumenttyp="labor", ist_test=patient.ist_test)
        return v

    def feld(self, v, gruppe="labor", konfidenz=0.9, **wert):
        standard = {"labor": {"parameter": self.kalium.pk, "parameter_name": "Kalium", "erkannt_als": "Kalium",
                              "freitext_name": "", "wert": "3.1", "wert_text": "", "einheit": "mmol/l",
                              "referenz_von": "3.5", "referenz_bis": "5.1", "datum": "2026-03-12",
                              "uhrzeit": "06:10", "markierung": "↓"}}
        schluessel = {"labor": "laborwert", "infusion": "position", "medikation": "medikament",
                      "diagnose": "diagnose", "text": "verlauf"}.get(gruppe, wert.pop("schluessel", "dokumentdatum"))
        return KiFeld.objects.create(vorgang=v, gruppe=gruppe, schluessel=schluessel,
                                     wert={**standard.get(gruppe, {}), **wert}, konfidenz=konfidenz, quelle="vision")


class RechteUndFirmenTest(KiApiGrundlage):
    def test_rechte_je_rolle(self):
        v = self.vorgang()
        self.assertEqual(client_fuer(self.betrachter).get("/api/ki/vorgaenge/").status_code, 403)
        r = client_fuer(self.mitarbeiter).get("/api/ki/vorgaenge/?status=zur_pruefung")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([x["id"] for x in r.json()["results"]], [v.pk])
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/ki/einstellungen/").status_code, 403)
        self.assertEqual(client_fuer(self.mediziner).get("/api/ki/einstellungen/").status_code, 403)
        self.assertEqual(client_fuer(self.admin).get("/api/ki/einstellungen/").status_code, 200)
        self.assertIn("ki_uebernehmen", self.mitarbeiter.rechte if hasattr(self.mitarbeiter, "rechte") else
                      __import__("accounts.rechte", fromlist=["rechte_fuer"]).rechte_fuer(self.mitarbeiter))

    def test_dskm_sieht_nur_dskm_rgc_nur_rgc(self):
        rg = Firma.objects.get(kuerzel="rg")
        rg_patient = Patient.objects.create(nachname="Klinik", vorname="Karla", geburtsdatum="1970-01-01")
        PatientFirma.objects.filter(patient=rg_patient).update(firma=rg)
        v_dskm = self.vorgang()
        v_rg = self.vorgang(rg_patient, nr=2)
        KiVorgang.objects.filter(pk=v_rg.pk).update(firma=rg)
        nur_rg = benutzer("nurrg", Rolle.KEINE)
        Mitgliedschaft.objects.create(benutzer=nur_rg, firma=rg, rolle=Rolle.MITARBEITER)
        c = echte_anmeldung(nur_rg, mit_zweitem_faktor(nur_rg, 1)[0])
        ids = [x["id"] for x in c.get("/api/ki/vorgaenge/").json()["results"]]
        self.assertEqual(ids, [v_rg.pk])
        self.assertEqual(c.get(f"/api/ki/vorgaenge/{v_dskm.pk}/").status_code, 404)
        m = echte_anmeldung(self.mitarbeiter, mit_zweitem_faktor(self.mitarbeiter, 1)[0])
        self.assertEqual([x["id"] for x in m.get("/api/ki/vorgaenge/").json()["results"]], [v_dskm.pk])
        # gemeinsame Akte, Dokument in der RGC erfasst: DSKM sieht den Vorgang trotzdem nicht
        PatientFirma.objects.create(patient=self.patient, firma=rg)
        v_geteilt = self.vorgang(nr=3)
        KiVorgang.objects.filter(pk=v_geteilt.pk).update(firma=rg)
        self.assertNotIn(v_geteilt.pk, [x["id"] for x in m.get("/api/ki/vorgaenge/").json()["results"]])

    def test_testpatienten_nur_mit_recht(self):
        test = Patient.objects.create(nachname="Test", vorname="T", geburtsdatum="1970-01-01", ist_test=True)
        v = self.vorgang(test)
        from accounts.models import Gruppenrecht

        Gruppenrecht.objects.create(rolle=Rolle.MITARBEITER, recht="testdaten_sehen", erlaubt=False)
        r = client_fuer(self.mitarbeiter).get("/api/ki/vorgaenge/")
        self.assertNotIn(v.pk, [x["id"] for x in r.json()["results"]])


class PruefenUndUebernehmenTest(KiApiGrundlage):
    def setUp(self):
        super().setUp()
        self.v = self.vorgang()
        self.kalium_feld = self.feld(self.v)
        self.c = client_fuer(self.mitarbeiter)

    def url(self, rest=""):
        return f"/api/ki/vorgaenge/{self.v.pk}/{rest}"

    def test_detail_mit_vorschau_neu(self):
        r = self.c.get(self.url())
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d["felder"][0]["endwert"]["wert"], "3.1")
        self.assertEqual(d["vorschau"][0]["aktion"], "neu")
        self.assertTrue(d["rechte"]["ki_uebernehmen"])

    def test_korrektur_versioniert_und_audit(self):
        r = self.c.patch(self.url(f"felder/{self.kalium_feld.pk}/"),
                         {"wert": {"wert": "3.4"}, "fehlerart": "lesefehler", "kommentar": "8 statt 4"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["endwert"]["wert"], "3.4")
        self.assertEqual(r.json()["wert"]["wert"], "3.1")  # Vorschlag der KI bleibt erhalten
        self.c.patch(self.url(f"felder/{self.kalium_feld.pk}/"), {"wert": {"einheit": "mmol/L"}}, format="json")
        k = list(KiKorrektur.objects.filter(feld=self.kalium_feld).order_by("version"))
        self.assertEqual([x.version for x in k], [1, 2])
        self.assertEqual((k[0].alt["wert"], k[0].neu["wert"], k[0].fehlerart), ("3.1", "3.4", "lesefehler"))
        self.assertEqual(SystemEreignis.objects.filter(art=A.KI, details__aktion="korrigiert").count(), 2)
        r = self.c.patch(self.url(f"felder/{self.kalium_feld.pk}/"), {"wert": {"boese": 1}}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(client_fuer(self.betrachter).patch(self.url(f"felder/{self.kalium_feld.pk}/"),
                                                            {"wert": {"wert": "1"}}, format="json").status_code, 403)

    def test_anderer_parameter_wird_dem_katalog_zugeordnet(self):
        r = self.c.patch(self.url(f"felder/{self.kalium_feld.pk}/"), {"wert": {"parameter_name": "Natrium", "wert": "138"},
                                                                      "fehlerart": "zuordnung"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["endwert"]["parameter"], r.json()["endwert"]["parameter_name"]),
                         (self.natrium.pk, "Natrium"))
        r = self.c.patch(self.url(f"felder/{self.kalium_feld.pk}/"), {"wert": {"parameter_name": "Spezialmarker"}},
                         format="json")
        self.assertEqual((r.json()["endwert"]["parameter"], r.json()["endwert"]["freitext_name"]),
                         (None, "Spezialmarker"))
        # Audit-Log lesbar
        r = client_fuer(self.admin).get("/api/protokoll/?gruppe=ki")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("Feld korrigiert", r.json()["results"][0]["beschreibung"])

    def test_alle_freigeben_laesst_unsichere_offen(self):
        unsicher = self.feld(self.v, konfidenz=0.4, parameter=self.natrium.pk, parameter_name="Natrium", wert="138")
        r = self.c.post(self.url("freigeben/"), {"alle": True}, format="json")
        self.assertEqual(r.json()["geaendert"], 1)
        unsicher.refresh_from_db()
        self.kalium_feld.refresh_from_db()
        self.assertEqual((self.kalium_feld.status, unsicher.status), ("freigegeben", "offen"))

    def test_uebernahme_neu_nur_freigegebene_mit_bestaetigung(self):
        r = self.c.post(self.url("uebernehmen/"), {"felder": [self.kalium_feld.pk], "bestaetigt": True}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("freigegeben", str(r.json()))
        self.c.post(self.url("freigeben/"), {"felder": [self.kalium_feld.pk]}, format="json")
        r = self.c.post(self.url("uebernehmen/"), {"felder": [self.kalium_feld.pk]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("bestätigen", r.json()["bestaetigt"])
        r = self.c.post(self.url("uebernehmen/"), {"felder": [self.kalium_feld.pk], "bestaetigt": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        b = Laborbefund.objects.get(patient=self.patient)
        self.assertEqual((b.abgenommen_am, b.abgenommen_um, b.dokument_id, b.labor),
                         (dt.date(2026, 3, 12), dt.time(6, 10), self.v.dokument_id, "Labor X"))
        self.assertEqual(b.werte.get().wert, Decimal("3.1"))
        self.kalium_feld.refresh_from_db()
        self.v.refresh_from_db()
        self.assertEqual((self.kalium_feld.status, self.v.status), ("uebernommen", "uebernommen"))
        self.assertEqual(self.kalium_feld.ziel, {"modell": "laborbefund", "id": b.pk})
        u = KiUebernahme.objects.get()
        self.assertEqual((u.benutzer, u.felder), (self.mitarbeiter, [self.kalium_feld.pk]))
        e = SystemEreignis.objects.get(art=A.KI, details__aktion="uebernommen")
        self.assertEqual(e.benutzer, self.mitarbeiter)

    def test_konflikt_ohne_entscheidung_schreibt_nichts_dann_ersetzen(self):
        alt = Laborbefund.objects.create(patient=self.patient, abgenommen_am=dt.date(2026, 3, 12))
        Laborwert.objects.create(befund=alt, parameter=self.kalium, wert=Decimal("3.9"), einheit="mmol/l")
        Laborwert.objects.create(befund=alt, parameter=self.natrium, wert=Decimal("140"), einheit="mmol/l")
        vorschau = self.c.get(self.url("vorschau/")).json()[0]
        self.assertEqual(vorschau["aktion"], "ueberschreiben")
        self.assertEqual(vorschau["bestehend"]["wert"], "3.9000")
        self.assertEqual(vorschau["optionen"], ["ersetzen", "neu", "verwerfen"])
        self.c.post(self.url("freigeben/"), {"felder": [self.kalium_feld.pk]}, format="json")
        r = self.c.post(self.url("uebernehmen/"), {"felder": [self.kalium_feld.pk], "bestaetigt": True}, format="json")
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.json()["konflikte"][0]["feld"], self.kalium_feld.pk)
        self.assertEqual(Laborwert.objects.get(befund=alt, parameter=self.kalium).wert, Decimal("3.9"))
        r = self.c.post(self.url("uebernehmen/"), {"felder": [self.kalium_feld.pk], "bestaetigt": True,
                                                   "entscheidungen": {str(self.kalium_feld.pk): "ersetzen"}},
                        format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Laborbefund.objects.count(), 1)
        self.assertEqual(Laborwert.objects.get(befund=alt, parameter=self.kalium).wert, Decimal("3.1"))
        self.assertEqual(Laborwert.objects.get(befund=alt, parameter=self.natrium).wert, Decimal("140"))
        # alter Stand im Verlauf
        self.assertTrue(alt.history.exists())

    def test_ergaenzen_in_vorhandenen_befund_und_verwerfen(self):
        alt = Laborbefund.objects.create(patient=self.patient, abgenommen_am=dt.date(2026, 3, 12))
        Laborwert.objects.create(befund=alt, parameter=self.natrium, wert=Decimal("140"), einheit="mmol/l")
        zweites = self.feld(self.v, parameter=None, parameter_name=None, erkannt_als="Tumormarker",
                            freitext_name="Tumormarker", wert=None, wert_text="negativ")
        self.c.post(self.url("freigeben/"), {"felder": [self.kalium_feld.pk, zweites.pk]}, format="json")
        r = self.c.post(self.url("uebernehmen/"), {"felder": [self.kalium_feld.pk, zweites.pk], "bestaetigt": True,
                                                   "entscheidungen": {str(self.kalium_feld.pk): "ergaenzen",
                                                                      str(zweites.pk): "verwerfen"}}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(sorted(alt.werte.values_list("parameter__name", flat=True)), ["Kalium", "Natrium"])
        zweites.refresh_from_db()
        self.assertEqual(zweites.status, "verworfen")

    def test_admin_nur_testpatienten(self):
        self.c.post(self.url("freigeben/"), {"felder": [self.kalium_feld.pk]}, format="json")
        r = client_fuer(self.admin).post(self.url("uebernehmen/"), {"felder": [self.kalium_feld.pk],
                                                                    "bestaetigt": True}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Laborbefund.objects.exists())

    def test_infusionsplan_als_altsystem_plan_nur_mit_recht(self):
        f = self.feld(self.v, "infusion", substanz="Kaliumchlorid", planfeld="kalium_mmol", menge="40",
                      einheit="mmol", von="2026-03-12", uhrzeit="08:00", applikation="i.v.", haeufigkeit="",
                      kontext="")
        g = self.feld(self.v, "infusion", substanz="Vitamin K", planfeld=None, menge="10", einheit="mg",
                      von="2026-03-12", applikation="i.v.", haeufigkeit="1x/Woche", kontext="")
        self.c.post(self.url("freigeben/"), {"felder": [f.pk, g.pk]}, format="json")
        r = self.c.post(self.url("uebernehmen/"), {"felder": [f.pk, g.pk], "bestaetigt": True}, format="json")
        self.assertEqual(r.status_code, 403)  # Mitarbeiter: „Infusionspläne anlegen“ fehlt
        r = client_fuer(self.mediziner).post(self.url("uebernehmen/"), {"felder": [f.pk, g.pk], "bestaetigt": True},
                                             format="json")
        self.assertEqual(r.status_code, 201, r.content)
        plan = Infusionsplan.objects.get(patient=self.patient)
        self.assertEqual((plan.status, plan.herkunft, plan.gueltig_ab, plan.kalium_mmol),
                         ("abgeloest", "altsystem", dt.date(2026, 3, 12), Decimal("40")))
        self.assertIn("Vitamin K", plan.bemerkung)
        self.assertIn("KI, geprüft", plan.bemerkung)
        # zweiter Plan mit gleichem Beginn: Konflikt, Ersetzen geht bei freigegebenen Plänen nicht
        v2 = self.vorgang(nr=2)
        f2 = self.feld(v2, "infusion", substanz="KCl", planfeld="kalium_mmol", menge="20", einheit="mmol",
                       von="2026-03-12")
        vorschau = client_fuer(self.mediziner).get(f"/api/ki/vorgaenge/{v2.pk}/vorschau/").json()[0]
        self.assertEqual((vorschau["aktion"], vorschau["optionen"]), ("konflikt", ["neu", "verwerfen"]))
        self.assertTrue(f2.pk)

    def test_infusion_einheit_und_planfeld_geprueft(self):
        """„Glucose 40 % 500 ml“ darf nicht als 500 g in den Plan; Planfelder nur aus der Liste (nie Patient/Status)."""
        c = client_fuer(self.mediziner)
        f = self.feld(self.v, "infusion", substanz="Glucose 40 %", planfeld="glucose_g", menge="500", einheit="ml",
                      von="2026-03-12")
        c.post(self.url("freigeben/"), {"felder": [f.pk]}, format="json")
        r = c.post(self.url("uebernehmen/"), {"felder": [f.pk], "bestaetigt": True}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("Einheit", r.json()["felder"][str(f.pk)])
        self.assertFalse(Infusionsplan.objects.exists())
        for boese in ["patient_id", "status", "herkunft", ["glucose_g"]]:
            r = c.patch(self.url(f"felder/{f.pk}/"), {"wert": {"planfeld": boese}}, format="json")
            self.assertEqual(r.status_code, 400, (boese, r.content))
        r = c.patch(self.url(f"felder/{f.pk}/"), {"wert": {"menge": "200", "einheit": "g"}, "status": "freigegeben"},
                    format="json")
        self.assertEqual(r.status_code, 200, r.content)
        r = c.post(self.url("uebernehmen/"), {"felder": [f.pk], "bestaetigt": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Infusionsplan.objects.get(patient=self.patient).glucose_g, Decimal("200"))

    def test_zweite_uebernahme_mit_veralteter_kopie_schreibt_nichts(self):
        """Wie bei zwei gleichzeitigen Bestätigungen: Die zweite liest nach der Sperre und findet alles übernommen."""
        from types import SimpleNamespace

        from ki import uebernahme

        self.c.post(self.url("freigeben/"), {"felder": [self.kalium_feld.pk]}, format="json")
        veraltet = KiVorgang.objects.get(pk=self.v.pk)
        r = self.c.post(self.url("uebernehmen/"), {"felder": [self.kalium_feld.pk], "bestaetigt": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        with self.assertRaises(uebernahme.Ungueltig):
            uebernahme.uebernehmen(veraltet, [self.kalium_feld.pk], {}, SimpleNamespace(user=self.mitarbeiter))
        self.assertEqual(Laborwert.objects.count(), 1)
        self.assertEqual(KiUebernahme.objects.count(), 1)

    def test_medikation_diagnose_text_und_dokumentdatum(self):
        m = self.feld(self.v, "medikation", wirkstoff="Pantoprazol", staerke="40 mg", dosierung="1-0-0",
                      handelsname="", grund="", seit=None)
        d = self.feld(self.v, "diagnose", bezeichnung="Kurzdarmsyndrom", icd_code="K91.2")
        t = self.feld(self.v, "text", text="Verlauf stabil.", aktenabschnitt="therapie")
        datum = self.feld(self.v, "meta", schluessel="dokumentdatum", **{"wert": "2026-03-12"})
        ids = [m.pk, d.pk, t.pk, datum.pk]
        c = client_fuer(self.mediziner)
        c.post(self.url("freigeben/"), {"felder": ids}, format="json")
        r = c.post(self.url("uebernehmen/"), {"felder": ids, "bestaetigt": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        med = Medikament.objects.get(patient=self.patient)
        self.assertFalse(med.aktiv)  # aus altem Dokument: nicht aktiv, Stand des Dokuments
        self.assertEqual(med.abgesetzt_am, dt.date(2026, 3, 12))
        self.assertIn("historischem Dokument", med.absetzgrund)
        self.assertEqual(Diagnose.objects.get(patient=self.patient).icd_code, "K91.2")
        self.patient.refresh_from_db()
        self.assertIn("Verlauf stabil.", self.patient.therapie)
        self.v.dokument.refresh_from_db()
        self.assertEqual(self.v.dokument.datum, dt.date(2026, 3, 12))

    def test_ablehnen_und_erneut(self):
        r = self.c.post(self.url("ablehnen/"), {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.c.patch(self.url(f"felder/{self.kalium_feld.pk}/"), {"wert": {"wert": "3.3"}}, format="json")
        r = self.c.post(self.url("ablehnen/"), {"grund": "falsches Dokument"}, format="json")
        self.assertEqual(r.json()["status"], "abgelehnt")
        self.kalium_feld.refresh_from_db()
        self.assertEqual(self.kalium_feld.status, "verworfen")
        r = self.c.post(self.url("erneut/"), {}, format="json")
        self.assertEqual(r.json()["status"], "neu")
        # korrigiertes Feld bleibt für die Qualitätsauswertung (verworfen), Seiten sind weg
        self.assertTrue(KiFeld.objects.filter(pk=self.kalium_feld.pk).exists())

    def test_anfordern(self):
        d = dokument(self.patient, b"%PDF-1.4 neu", name="n.pdf", mime="application/pdf")
        r = self.c.post("/api/ki/vorgaenge/anfordern/", {"dokument": d.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["prioritaet"], 10)
        self.assertEqual(client_fuer(self.betrachter).post("/api/ki/vorgaenge/anfordern/", {"dokument": d.pk},
                                                           format="json").status_code, 403)


class BerichteTest(KiApiGrundlage):
    def setUp(self):
        super().setUp()
        b = Laborbefund.objects.create(patient=self.patient, abgenommen_am=dt.date(2026, 3, 12))
        Laborwert.objects.create(befund=b, parameter=self.kalium, wert=Decimal("3.1"), einheit="mmol/l",
                                 referenz_von=Decimal("3.5"), referenz_bis=Decimal("5.1"))
        # ein KI-Vorschlag zählt nicht – nur freigegebene Inhalte der Akte
        v = self.vorgang()
        self.feld(v, wert="9.9")

    def test_nur_auf_anforderung_aus_akteninhalten_mit_quellen(self):
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/ki/berichte/", {"patient": self.patient.pk, "art": "labor", "von": "2026-01-01",
                                         "bis": "2026-12-31"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        auftrag = KiBerichtsauftrag.objects.get()
        self.assertEqual(auftrag.status, "wartet")
        berichte.erstellen(auftrag, Attrappe(bericht="Kalium 3,1 mmol/l am 12.03.2026 [1]. Wir empfehlen 9,9 [7]."))
        auftrag.refresh_from_db()
        self.assertEqual(len(auftrag.fakten), 1)
        self.assertIn("Kalium 3,1 mmol/l", auftrag.fakten[0]["text"])
        self.assertNotIn("9,9", auftrag.fakten[0]["text"])
        p = auftrag.pruefung
        self.assertFalse(p["ok"])
        self.assertEqual(p["unbelegte_werte"], ["9,9"])
        self.assertEqual(p["unbekannte_belege"], [7])
        self.assertTrue(p["empfehlung_oder_bewertung"])
        r = c.post(f"/api/ki/berichte/{auftrag.pk}/speichern/", {"text": "Kalium 3,1 mmol/l [1]."}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        bericht = Bericht.objects.get(pk=r.json()["bericht"])
        self.assertEqual(bericht.status, "entwurf")
        self.assertIn("KI-Entwurf (Experimentell)", bericht.inhalt)
        self.assertIn("Quellen", bericht.inhalt)
        self.assertEqual(c.post(f"/api/ki/berichte/{auftrag.pk}/speichern/", {}, format="json").status_code, 409)
        self.assertEqual(Bericht.objects.filter(patient=self.patient).count(), 1)

    def test_ohne_modell_und_ohne_recht(self):
        a = KiBerichtsauftrag.objects.create(patient=self.patient, art="labor", angefordert_von=self.mediziner)
        berichte.erstellen(a, None)
        self.assertIn("[1]", a.entwurf)
        self.assertTrue(a.pruefung["ok"], a.pruefung)
        self.assertEqual(client_fuer(self.betrachter).post("/api/ki/berichte/", {"patient": self.patient.pk,
                                                                                 "art": "labor"},
                                                           format="json").status_code, 403)


class AdministrationTest(KiApiGrundlage):
    def test_einstellungen_grenzen_und_training_nur_mit_rechtsgrundlage(self):
        c = client_fuer(self.admin)
        r = c.put("/api/ki/einstellungen/", {"nacht_beginn": "22:00", "worker_nacht": 2}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(KiEinstellung.laden().nacht_beginn, dt.time(22, 0))
        self.assertEqual(c.put("/api/ki/einstellungen/", {"worker_nacht": 99}, format="json").status_code, 400)
        self.assertEqual(c.put("/api/ki/einstellungen/", {"zeitzone": "Mond/Krater"}, format="json").status_code,
                         400)
        r = c.put("/api/ki/einstellungen/", {"training_erlaubt": True}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(SystemEreignis.objects.filter(art=A.KI, details__aktion="einstellungen").exists())

    def test_modell_registrieren_aktivieren_mit_2fa_und_zurueckschalten(self):
        mit_zweitem_faktor(self.admin, 3)
        c = echte_anmeldung(self.admin, "code0000x")
        r = c.post("/api/ki/modelle/", {"name": "Qwen3.5-4B Q4_K_M", "datei": "qwen3.5-4b-q4_k_m.gguf",
                                        "projektor": "mmproj-qwen3.5-4b-f16.gguf", "sha256": "a" * 64,
                                        "quantisierung": "Q4_K_M"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        erstes = r.json()["id"]
        self.assertEqual(c.post("/api/ki/modelle/", {"name": "x", "datei": "../boese.gguf", "sha256": "a" * 64},
                                format="json").status_code, 400)
        r = c.post(f"/api/ki/modelle/{erstes}/aktivieren/", {"kennwort": "ein-sicheres-Passwort-123",
                                                             "code": "code0001x"}, format="json")
        self.assertEqual(r.status_code, 400)  # erst evaluieren
        r = c.post(f"/api/ki/modelle/{erstes}/aktivieren/", {"kennwort": "falsch", "code": "code0001x",
                                                             "ohne_evaluation": True}, format="json")
        self.assertEqual(r.status_code, 400)
        with self.captureOnCommitCallbacks(execute=True):
            r = c.post(f"/api/ki/modelle/{erstes}/aktivieren/", {"kennwort": "ein-sicheres-Passwort-123",
                                                                 "code": "code0001x", "ohne_evaluation": True},
                       format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("DATEI=qwen3.5-4b-q4_k_m.gguf\nPROJEKTOR=mmproj-qwen3.5-4b-f16.gguf\nSHA256=" + "a" * 64,
                      (Path(KI_TMP) / "modell" / "aktiv.env").read_text())
        import json

        aktiv = json.loads((Path(KI_TMP) / "modell" / "aktiv.json").read_text())
        self.assertEqual(aktiv["datei"], "qwen3.5-4b-q4_k_m.gguf")
        zweites = KiModellversion.objects.create(name="Qwen3.5-4B Q8_0", datei="q8.gguf", sha256="b" * 64,
                                                 status="evaluation")
        r = c.post(f"/api/ki/modelle/{zweites.pk}/aktivieren/", {"kennwort": "ein-sicheres-Passwort-123",
                                                                 "code": "code0002x"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(KiModellversion.objects.get(pk=erstes).status, "vorherig")
        self.assertEqual(KiModellversion.aktiv().pk, zweites.pk)
        self.assertEqual(SystemEreignis.objects.filter(art=A.KI, details__aktion="modell_aktiviert").count(), 2)

    def test_stand_und_qualitaet(self):
        v = self.vorgang(status="uebernommen")
        f = self.feld(v)
        KiKorrektur.objects.create(feld=f, version=1, alt=f.wert, neu={**f.wert, "wert": "3.4"},
                                   fehlerart="lesefehler", benutzer=self.mitarbeiter)
        KiFeld.objects.filter(pk=f.pk).update(status="uebernommen")
        richtig = self.feld(v, parameter=self.natrium.pk, parameter_name="Natrium", wert="138")
        KiFeld.objects.filter(pk=richtig.pk).update(status="uebernommen")
        r = client_fuer(self.mitarbeiter).get("/api/ki/qualitaet/")
        self.assertEqual(r.status_code, 200, r.content)
        labor = next(g for g in r.json()["gruppen"] if g["gruppe"] == "labor")
        self.assertEqual((labor["entschieden"], labor["richtig"], labor["korrigiert"], labor["genauigkeit"]),
                         (2, 1, 1, 0.5))
        self.assertEqual(r.json()["ocr_fehlerrate"], 0.5)
        self.assertEqual(r.json()["fehlerarten"][0]["fehlerart"], "lesefehler")
        r = client_fuer(self.admin).get("/api/ki/stand/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("queue", r.json())

    def test_evaluation_und_trainingsfreigabe(self):
        v = self.vorgang(status="uebernommen")
        KiVorgang.objects.filter(pk=v.pk).update(ocr_text="Patient Echt, Anna\nKalium 3,1 mmol/l")
        f = self.feld(v)
        KiFeld.objects.filter(pk=f.pk).update(status="uebernommen")
        self.assertEqual(evaluation.faelle_erzeugen(), 1)
        fall = KiEvaluationsfall.objects.get()
        self.assertNotIn("Echt", fall.eingabe_text)
        self.assertEqual(fall.erwartet["laborwerte"], [["kalium", "3.1"]])
        mv = KiModellversion.objects.create(name="Probe", datei="p.gguf", sha256="c" * 64)
        lauf = KiEvaluationslauf.objects.create(modellversion=mv)
        modell = Attrappe(extraktion={"dokumenttyp": "labor", "laborwerte": [{"parameter": "K", "wert": "3,1"}],
                                      "infusionen": []})
        evaluation.lauf_ausfuehren(lauf, modell)
        mv.refresh_from_db()
        self.assertEqual(mv.evaluation["laborwerte"]["f1"], 1.0)
        self.assertEqual(mv.evaluation["dokumenttyp_genauigkeit"], 1.0)
        c = client_fuer(self.admin)
        r = c.post("/api/ki/evaluation/", {"aktion": "training_freigeben", "faelle": [fall.pk]}, format="json")
        self.assertEqual(r.status_code, 400)  # Rechtsgrundlage fehlt
        self.assertFalse(KiEvaluationsfall.objects.get().training_freigegeben)


class DbRolleTest(KiApiGrundlage):
    def test_ki_dienst_kann_nicht_in_die_akte_schreiben(self):
        from ki.dbrolle import einrichten

        e = einrichten(rolle="epm_ki_test")
        self.assertIn("ki_kivorgang", e["schreiben"])
        self.assertNotIn("befunde_laborbefund", e["schreiben"])
        d = dokument(self.patient, b"%PDF-1.4 r", name="r.pdf", mime="application/pdf")
        with connection.cursor() as c:
            c.execute("SET ROLE epm_ki_test")
            try:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as c2:
                        c2.execute("INSERT INTO befunde_laborbefund (patient_id, abgenommen_am, labor, beurteilung, "
                                   "erfasst_am) VALUES (%s, '2026-01-01', '', '', now())", [self.patient.pk])
                with self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as c2:
                        c2.execute("UPDATE patienten_dokument SET titel = 'x' WHERE id = %s", [d.pk])
                with transaction.atomic(), connection.cursor() as c2:
                    c2.execute("SELECT count(*) FROM patienten_dokument")
                    self.assertEqual(c2.fetchone()[0], 1)
                    c2.execute("INSERT INTO ki_kivorgang (dokument_id, patient_id, sha256, ist_test, status, "
                               "prioritaet, schritt, fortschritt, versuche, fehler, dokumenttyp, metadaten, seiten, "
                               "ocr_text, zusammenfassung, verfahren, prompt_version, erstellt_am, ablehnungsgrund) "
                               "VALUES (%s, %s, 'x', false, 'neu', 0, '', 0, 0, '', '', '{}', 0, '', '', '[]', '', "
                               "now(), '')", [d.pk, self.patient.pk])
            finally:
                c.execute("RESET ROLE")

    def test_ki_dienst_ohne_anmeldedaten_und_nachweise_nur_anfuegen(self):
        from ki.dbrolle import einrichten
        from ki.pipeline import alte_felder_entfernen

        einrichten(rolle="epm_ki_test")
        v = self.vorgang()
        offen, korrigiert = self.feld(v), self.feld(v)
        KiKorrektur.objects.create(feld=korrigiert, version=1, alt={}, neu={}, benutzer=self.mitarbeiter)
        mv = KiModellversion.objects.create(name="m", datei="m.gguf", sha256="x")
        with connection.cursor() as c:
            c.execute("SET ROLE epm_ki_test")
            try:
                for anweisung in ["SELECT count(*) FROM django_session", "SELECT count(*) FROM accounts_sitzung",
                                  "SELECT count(*) FROM otp_totp_totpdevice", "SELECT count(*) FROM otp_static_statictoken",
                                  "UPDATE ki_kikorrektur SET kommentar = 'x'", "DELETE FROM ki_kikorrektur",
                                  "DELETE FROM ki_kiuebernahme", "UPDATE ki_kimodellversion SET status = 'aktiv'"]:
                    with self.subTest(anweisung), self.assertRaises(DatabaseError), transaction.atomic():
                        with connection.cursor() as c2:
                            c2.execute(anweisung)
                # was der Dienst wirklich tut, geht weiter
                with transaction.atomic():
                    alte_felder_entfernen(v)
                    mv.evaluation = {"faelle": 1}
                    mv.save(update_fields=["evaluation"])
            finally:
                c.execute("RESET ROLE")
        self.assertFalse(KiFeld.objects.filter(pk=offen.pk).exists())
        self.assertEqual(KiFeld.objects.get(pk=korrigiert.pk).status, KiFeld.Status.VERWORFEN)
        self.assertEqual(KiKorrektur.objects.count(), 1)
