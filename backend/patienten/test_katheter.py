"""Katheter-Historie (F192, 15.10.2026): Katheter je Akte mit Komplikationen, Zeitachse und Kennzahlen.

Geprüft werden Anlegen/Ändern/Zurücknehmen, Rechte (Betrachter, Admin nur Testpatienten, abgeschlossene Akte,
fremde Akten), die Prüfungen (Entfernt am ≥ Anlage, keine Zukunft, Komplikation in der Liegezeit), die Übernahme in die
Kerndaten (Festlegung 16.10.2026), die Kennzahl Infektionen je 1000 Kathetertage, Verlauf, Aktenkopie und Löschen nach
DSGVO."""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from accounts.models import Rolle
from audit.schutz import wartungsmodus
from epm.pruefhilfen import Grundlage, benutzer, client_fuer
from stammdaten.models import Auswahlwert

from .datenschutz import akten_entfernen, umfang
from .models import Katheter, KatheterKomplikation, Patient, katheter_kennzahlen

URL = "/api/katheter/"
KOMPL = "/api/katheter-komplikationen/"


def vor(tage: int) -> str:
    return (timezone.localdate() - timedelta(days=tage)).isoformat()


def wert(liste, text) -> Auswahlwert:
    return Auswahlwert.objects.get(liste=liste, wert=text)


class KatheterGrundlage(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        L = Auswahlwert.Liste
        cls.port = wert(L.KATHETER, "Port")
        cls.hickman = wert(L.KATHETER, "Hickman")
        cls.wechsel = wert(L.KATHETER_ENTFERNUNG, "Wechsel")
        cls.infektion = wert(L.KATHETER_KOMPLIKATION, "Katheterinfektion")
        cls.okklusion = wert(L.KATHETER_KOMPLIKATION, "Okklusion")

    def anlegen(self, client=None, patient=None, **extra):
        c = client or client_fuer(self.mitarbeiter)
        daten = {"patient": (patient or self.patient).id, "typ": self.port.id, "lage": "V. subclavia rechts",
                 "anlage_am": vor(100), **extra}
        return c.post(URL, daten, format="json")

    def komplikation(self, katheter_id, client=None, **extra):
        c = client or client_fuer(self.mitarbeiter)
        return c.post(KOMPL, {"katheter": katheter_id, "datum": vor(50), "art": self.infektion.id, **extra},
                      format="json")


class Auswahllisten(KatheterGrundlage):
    def test_grundwerte_vorhanden(self):
        """Die Grundwerte stehen in den Musterdaten (und legt die Migration stammdaten/0026 an)."""
        L = Auswahlwert.Liste
        self.assertEqual(list(Auswahlwert.objects.filter(liste=L.KATHETER_ENTFERNUNG).values_list("wert", flat=True)),
                         ["Wechsel", "Infektion", "Okklusion", "Dislokation", "Therapie beendet", "Sonstiges"])
        self.assertEqual(list(Auswahlwert.objects.filter(liste=L.KATHETER_KOMPLIKATION).values_list("wert", flat=True)),
                         ["Katheterinfektion", "Okklusion", "Thrombose", "Dislokation", "Leckage", "Sonstiges"])

    def test_pflege_unter_auswahllisten(self):
        """Neue Werte wie bei den übrigen Listen über /api/auswahlwerte/ (Administration › Auswahllisten)."""
        c = client_fuer(self.mitarbeiter)  # „Vorlagen pflegen“
        r = c.post("/api/auswahlwerte/", {"liste": "katheter_komplikation", "wert": "Tunnelinfektion"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        liste = c.get("/api/auswahlwerte/?liste=katheter_entfernung").json()
        self.assertEqual(len(liste), 6)


class Anlegen(KatheterGrundlage):
    def test_anlegen_liste_und_felder(self):
        r = self.anlegen(lage="  V. subclavia rechts ", notiz=" erster Port ")
        self.assertEqual(r.status_code, 201, r.content)
        k = r.json()
        self.assertEqual((k["typ_name"], k["lage"], k["notiz"], k["liegt"], k["liegedauer_tage"], k["aktiv"]),
                         ("Port", "V. subclavia rechts", "erster Port", True, 100, True))
        self.assertTrue(k["angelegt_von_name"])
        self.assertIn("firma_kurz", k)
        self.assertEqual(k["komplikationen"], [])
        liste = client_fuer(self.betrachter).get(f"{URL}?patient={self.patient.id}").json()
        self.assertEqual([x["id"] for x in liste], [k["id"]])
        kopf = client_fuer(self.mitarbeiter).get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual(kopf["zaehler"]["katheter"], 1)

    def test_bearbeiten_und_entfernen(self):
        k = self.anlegen().json()
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"{URL}{k['id']}/", {"entfernt_am": vor(10), "entfernungsgrund": self.wechsel.id}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["liegt"], r.json()["liegedauer_tage"], r.json()["entfernungsgrund_name"]),
                         (False, 90, "Wechsel"))
        # „Entfernt am“ leeren leert auch den Grund
        r = c.patch(f"{URL}{k['id']}/", {"entfernt_am": None}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["entfernt_am"], r.json()["entfernungsgrund"]), (None, None))

    def test_kein_loeschen_nur_zuruecknehmen(self):
        k = self.anlegen().json()
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.delete(f"{URL}{k['id']}/").status_code, 405)
        with self.assertRaises(PermissionError):
            Katheter.objects.get(pk=k["id"]).delete()
        x = self.komplikation(k["id"]).json()
        self.assertEqual(c.delete(f"{KOMPL}{x['id']}/").status_code, 405)
        r = c.patch(f"{URL}{k['id']}/", {"aktiv": False}, format="json")
        self.assertEqual((r.status_code, r.json()["aktiv"]), (200, False))
        self.assertTrue(Katheter.objects.filter(pk=k["id"]).exists())
        # zurückgenommene zählen nicht
        self.assertEqual(katheter_kennzahlen(self.patient)["anzahl"], 0)
        kopf = c.get(f"/api/patienten/{self.patient.id}/").json()["kopf"]
        self.assertEqual(kopf["zaehler"]["katheter"], 0)

    def test_komplikation_anlegen_und_aendern(self):
        k = self.anlegen().json()
        r = self.komplikation(k["id"], notiz=" Fieber ")
        self.assertEqual(r.status_code, 201, r.content)
        x = r.json()
        self.assertEqual((x["patient"], x["art_name"], x["ist_infektion"], x["notiz"]),
                         (self.patient.id, "Katheterinfektion", True, "Fieber"))
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"{KOMPL}{x['id']}/", {"art": self.okklusion.id}, format="json")
        self.assertEqual((r.status_code, r.json()["ist_infektion"]), (200, False))
        # im Katheter mitgeliefert
        k = c.get(f"{URL}{k['id']}/").json()
        self.assertEqual([y["art_name"] for y in k["komplikationen"]], ["Okklusion"])
        self.assertEqual(c.get(f"{KOMPL}?katheter={k['id']}").json()[0]["id"], x["id"])
        # Katheter nicht tauschbar
        k2 = self.anlegen(anlage_am=vor(30)).json()
        r = c.patch(f"{KOMPL}{x['id']}/", {"katheter": k2["id"]}, format="json")
        self.assertEqual(r.status_code, 400)


class Pruefungen(KatheterGrundlage):
    def test_entfernt_vor_anlage(self):
        r = self.anlegen(entfernt_am=vor(101))
        self.assertEqual(r.status_code, 400)
        self.assertIn("vor dem Anlagedatum", str(r.json()["entfernt_am"]))
        self.assertEqual(self.anlegen(entfernt_am=vor(100)).status_code, 201)  # gleicher Tag geht

    def test_keine_zukunft(self):
        morgen = (timezone.localdate() + timedelta(days=1)).isoformat()
        r = self.anlegen(anlage_am=morgen)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Zukunft", str(r.json()["anlage_am"]))
        r = self.anlegen(entfernt_am=morgen)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Zukunft", str(r.json()["entfernt_am"]))
        k = self.anlegen().json()
        r = self.komplikation(k["id"], datum=morgen)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Zukunft", str(r.json()["datum"]))

    def test_pflichtfelder_und_listen(self):
        r = client_fuer(self.mitarbeiter).post(URL, {"patient": self.patient.id}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertTrue({"typ", "anlage_am"} <= set(r.json()), r.json())
        # Wert aus der falschen Liste (DRF beschränkt die Auswahl schon über ``limit_choices_to``)
        r = self.anlegen(typ=self.wechsel.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("typ", r.json())
        r = self.anlegen(entfernt_am=vor(5), entfernungsgrund=self.infektion.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("entfernungsgrund", r.json())
        # Grund ohne Datum
        r = self.anlegen(entfernungsgrund=self.wechsel.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Entfernt am", str(r.json()["entfernungsgrund"]))
        k = self.anlegen().json()
        r = self.komplikation(k["id"], art=self.port.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("art", r.json())
        # ausgeblendete Werte sind nicht mehr wählbar
        Auswahlwert.objects.filter(pk=self.okklusion.pk).update(aktiv=False)
        self.assertEqual(self.komplikation(k["id"], art=self.okklusion.id).status_code, 400)

    def test_komplikation_in_der_liegezeit(self):
        k = self.anlegen(entfernt_am=vor(20)).json()
        r = self.komplikation(k["id"], datum=vor(101))
        self.assertEqual(r.status_code, 400)
        self.assertIn("vor der Anlage", str(r.json()["datum"]))
        r = self.komplikation(k["id"], datum=vor(19))
        self.assertEqual(r.status_code, 400)
        self.assertIn("nach der Entfernung", str(r.json()["datum"]))
        self.assertEqual(self.komplikation(k["id"], datum=vor(100)).status_code, 201)
        self.assertEqual(self.komplikation(k["id"], datum=vor(20)).status_code, 201)

    def test_liegezeit_nicht_an_komplikationen_vorbei_kuerzen(self):
        k = self.anlegen().json()
        self.komplikation(k["id"], datum=vor(50))
        c = client_fuer(self.mitarbeiter)
        r = c.patch(f"{URL}{k['id']}/", {"entfernt_am": vor(60)}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("außerhalb der Liegezeit", str(r.json()["entfernt_am"]))
        r = c.patch(f"{URL}{k['id']}/", {"anlage_am": vor(40)}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("außerhalb der Liegezeit", str(r.json()["anlage_am"]))
        self.assertEqual(Katheter.objects.get(pk=k["id"]).anlage_am.isoformat(), vor(100))

    def test_patient_fest(self):
        k = self.anlegen().json()
        anderer = Patient.objects.create(nachname="Anders", vorname="Ada", geburtsdatum="1970-01-01")
        r = client_fuer(self.mitarbeiter).patch(f"{URL}{k['id']}/", {"patient": anderer.id}, format="json")
        self.assertEqual(r.status_code, 400)


class Kerndaten(KatheterGrundlage):
    """Festlegung vom 16.10.2026: Ein neuer bzw. gewechselter Katheter aktualisiert ``Patient.katheter``."""

    def test_neuer_liegender_katheter_setzt_kerndaten(self):
        Patient.objects.filter(pk=self.patient.pk).update(kein_katheter=True, katheter=None)
        r = self.anlegen()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["kerndaten_aktualisiert"], r.json()["hinweise"]), (True, []))
        p = Patient.objects.get(pk=self.patient.pk)
        self.assertEqual((p.katheter_id, p.kein_katheter), (self.port.id, False))
        # im Verlauf mit Person
        h = p.history.latest("history_date")
        self.assertEqual(h.history_user_id, self.mitarbeiter.id)

    def test_wechsel_mit_hinweis_vorheriger_bleibt_offen(self):
        alt = self.anlegen().json()
        r = self.anlegen(typ=self.hickman.id, anlage_am=vor(5))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()["kerndaten_aktualisiert"])
        self.assertEqual(r.json()["hinweise"], ["Vorheriger Katheter noch nicht als entfernt eingetragen"])
        self.assertEqual(Patient.objects.get(pk=self.patient.pk).katheter_id, self.hickman.id)
        # der vorherige wird NICHT automatisch beendet
        self.assertIsNone(Katheter.objects.get(pk=alt["id"]).entfernt_am)
        z = client_fuer(self.betrachter).get(f"{URL}kennzahlen/?patient={self.patient.id}").json()
        self.assertEqual((z["offen"], z["aktuell"]["typ"], z["hinweise"]),
                         (2, "Hickman", ["Vorheriger Katheter noch nicht als entfernt eingetragen"]))
        # nach dem Eintragen der Entfernung verschwindet der Hinweis
        client_fuer(self.mitarbeiter).patch(f"{URL}{alt['id']}/", {"entfernt_am": vor(5), "entfernungsgrund": self.wechsel.id},
                                            format="json")
        z = client_fuer(self.betrachter).get(f"{URL}kennzahlen/?patient={self.patient.id}").json()
        self.assertEqual((z["offen"], z["hinweise"]), (1, []))

    def test_entfernter_katheter_aendert_kerndaten_nicht(self):
        Patient.objects.filter(pk=self.patient.pk).update(katheter=self.hickman)
        r = self.anlegen(entfernt_am=vor(50))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertFalse(r.json()["kerndaten_aktualisiert"])
        self.assertEqual(Patient.objects.get(pk=self.patient.pk).katheter_id, self.hickman.id)

    def test_gleicher_typ_keine_aenderung(self):
        Patient.objects.filter(pk=self.patient.pk).update(katheter=self.port)
        vorher = Patient.history.filter(id=self.patient.pk).count()
        r = self.anlegen()
        self.assertFalse(r.json()["kerndaten_aktualisiert"])
        self.assertEqual(Patient.history.filter(id=self.patient.pk).count(), vorher)

    def test_anlagedatum_fehlt(self):
        """Kerndaten mit Katheter, aber keine Historie (z. B. aus dem Altsystem): Hinweis statt erfundener Daten."""
        Patient.objects.filter(pk=self.patient.pk).update(katheter=self.port)
        z = client_fuer(self.betrachter).get(f"{URL}kennzahlen/?patient={self.patient.id}").json()
        self.assertEqual((z["anlagedatum_fehlt"], z["kerndaten_typ"], z["aktuell"]), (True, "Port", None))
        self.anlegen()
        z = client_fuer(self.betrachter).get(f"{URL}kennzahlen/?patient={self.patient.id}").json()
        self.assertFalse(z["anlagedatum_fehlt"])


class Kennzahl(KatheterGrundlage):
    def test_infektionen_je_1000_kathetertage(self):
        heute = timezone.localdate()
        # 1. Katheter: 400 Tage, eine Infektion, eine Okklusion
        k1 = self.anlegen(anlage_am=vor(600), entfernt_am=vor(200)).json()
        self.komplikation(k1["id"], datum=vor(500))
        self.komplikation(k1["id"], datum=vor(300), art=self.okklusion.id)
        # 2. Katheter: liegt seit 100 Tagen, eine Infektion
        k2 = self.anlegen(typ=self.hickman.id, anlage_am=vor(100)).json()
        self.komplikation(k2["id"], datum=vor(10))
        z = katheter_kennzahlen(Patient.objects.get(pk=self.patient.pk), heute)
        self.assertEqual((z["kathetertage"], z["infektionen"]), (500, 2))
        self.assertEqual(z["infektionen_je_1000"], Decimal("4.00"))   # 2 / 500 × 1000
        self.assertEqual((z["aktuell"]["typ"], z["aktuell"]["liegedauer_tage"]), ("Hickman", 100))
        # über die API (als Zahl, wie alle Dezimalzahlen der API)
        r = client_fuer(self.betrachter).get(f"{URL}kennzahlen/?patient={self.patient.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(str(r.json()["infektionen_je_1000"])), Decimal("4.00"))
        # zurückgenommene Komplikationen zählen nicht
        x = KatheterKomplikation.objects.filter(katheter_id=k2["id"]).first()
        client_fuer(self.mitarbeiter).patch(f"{KOMPL}{x.id}/", {"aktiv": False}, format="json")
        z = katheter_kennzahlen(Patient.objects.get(pk=self.patient.pk), heute)
        self.assertEqual((z["infektionen"], z["infektionen_je_1000"]), (1, Decimal("2.00")))

    def test_ohne_kathetertage(self):
        self.anlegen(anlage_am=vor(0))
        z = katheter_kennzahlen(Patient.objects.get(pk=self.patient.pk))
        self.assertEqual((z["kathetertage"], z["infektionen_je_1000"]), (0, None))
        z = katheter_kennzahlen(Patient.objects.create(nachname="Leer", vorname="Lea", geburtsdatum="1980-01-01"))
        self.assertEqual((z["anzahl"], z["aktuell"], z["infektionen_je_1000"]), (0, None, None))

    def test_infektion_nach_namen(self):
        neu = Auswahlwert.objects.create(liste=Auswahlwert.Liste.KATHETER_KOMPLIKATION, wert="Tunnelinfektion")
        k = self.anlegen().json()
        self.assertTrue(self.komplikation(k["id"], art=neu.id).json()["ist_infektion"])
        self.assertFalse(self.komplikation(k["id"], art=self.okklusion.id).json()["ist_infektion"])

    def test_kennzahlen_nur_eigene_akten(self):
        test = Patient.objects.create(nachname="Test", vorname="Tina", geburtsdatum="1970-01-01", ist_test=True)
        testnutzer = benutzer("testnutzer", Rolle.MITARBEITER, ist_test=True)
        c = client_fuer(testnutzer)
        self.assertEqual(c.get(f"{URL}kennzahlen/?patient={self.patient.id}").status_code, 404)
        self.assertEqual(c.get(f"{URL}kennzahlen/?patient={test.id}").status_code, 200)
        self.assertEqual(c.get(f"{URL}kennzahlen/").status_code, 404)


class Rechte(KatheterGrundlage):
    def test_betrachter_liest_nur(self):
        k = self.anlegen().json()
        b = client_fuer(self.betrachter)
        self.assertEqual(b.get(f"{URL}?patient={self.patient.id}").status_code, 200)
        self.assertEqual(b.get(f"{KOMPL}?patient={self.patient.id}").status_code, 200)
        self.assertEqual(self.anlegen(b).status_code, 403)
        self.assertEqual(b.patch(f"{URL}{k['id']}/", {"lage": "X"}, format="json").status_code, 403)
        self.assertEqual(self.komplikation(k["id"], b).status_code, 403)

    def test_admin_nur_testpatienten(self):
        r = self.anlegen(client_fuer(self.admin))
        self.assertEqual(r.status_code, 403)
        self.assertIn("Testpatienten", r.json()["fehler"])
        test = Patient.objects.create(nachname="Test", vorname="Tina", geburtsdatum="1970-01-01", ist_test=True)
        r = self.anlegen(client_fuer(self.admin), patient=test)
        self.assertEqual(r.status_code, 201, r.content)
        # Komplikation an einem echten Katheter: auch nicht
        echt = self.anlegen().json()
        self.assertEqual(self.komplikation(echt["id"], client_fuer(self.admin)).status_code, 403)

    def test_abgeschlossene_akte_nicht_bearbeitbar(self):
        k = self.anlegen().json()
        Patient.objects.filter(pk=self.patient.pk).update(abgeschlossen_am=timezone.localdate(),
                                                          abschluss_anlass=Patient.Abschlussanlass.VERSTORBEN)
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(self.anlegen().status_code, 409)
        self.assertEqual(c.patch(f"{URL}{k['id']}/", {"lage": "neu"}, format="json").status_code, 409)
        self.assertEqual(self.komplikation(k["id"]).status_code, 409)
        # lesen geht weiter
        self.assertEqual(c.get(f"{URL}?patient={self.patient.id}").status_code, 200)

    def test_eingeschraenkte_akte_unsichtbar(self):
        k = self.anlegen().json()
        Patient.objects.filter(pk=self.patient.pk).update(
            abgeschlossen_am=timezone.localdate(), abschluss_anlass=Patient.Abschlussanlass.VERSTORBEN,
            eingeschraenkt_am=timezone.now(), einschraenkung_grund="Antrag nach Art. 18 DSGVO")
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.get(f"{URL}?patient={self.patient.id}").json(), [])
        self.assertEqual(c.get(f"{URL}{k['id']}/").status_code, 404)
        self.assertEqual(c.get(f"{URL}kennzahlen/?patient={self.patient.id}").status_code, 404)

    def test_nur_eigene_akten(self):
        test = Patient.objects.create(nachname="Test", vorname="Tina", geburtsdatum="1970-01-01", ist_test=True)
        Katheter.objects.create(patient=test, typ=self.port, anlage_am=timezone.localdate())
        echt = self.anlegen().json()
        testnutzer = benutzer("testnutzer", Rolle.MITARBEITER, ist_test=True)
        c = client_fuer(testnutzer)
        self.assertEqual([k["patient"] for k in c.get(URL).json()], [test.id])
        self.assertEqual(self.anlegen(c).status_code, 400)  # echte Akte gibt es für Testbenutzer nicht
        # an einen Katheter einer fremden Akte keine Komplikation (der Katheter „existiert“ für ihn nicht)
        r = self.komplikation(echt["id"], c)
        self.assertEqual(r.status_code, 400)
        self.assertIn("katheter", r.json())


class Verlauf(KatheterGrundlage):
    def test_verlauf_mit_person_und_aktionen(self):
        k = self.anlegen(notiz="erster Port").json()
        x = self.komplikation(k["id"], notiz="Fieber").json()
        c = client_fuer(self.mitarbeiter)
        c.patch(f"{URL}{k['id']}/", {"entfernt_am": vor(10), "entfernungsgrund": self.wechsel.id}, format="json")
        c.patch(f"{KOMPL}{x['id']}/", {"aktiv": False}, format="json")
        verlauf = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=katheter").json()
        self.assertEqual([e["aktion"] for e in verlauf], ["als entfernt eingetragen", "angelegt"])
        self.assertTrue(all(e["person"] == self.mitarbeiter.anzeigename for e in verlauf))
        self.assertIn("Port · V. subclavia rechts · angelegt am", verlauf[-1]["beschreibung"])
        self.assertIn("entfernt am", verlauf[0]["beschreibung"])
        self.assertIn("(Wechsel)", verlauf[0]["beschreibung"])
        kompl = c.get(f"/api/patienten/{self.patient.id}/verlauf/?bereich=katheter_komplikationen").json()
        self.assertEqual([e["aktion"] for e in kompl], ["als falsch erfasst zurückgenommen", "angelegt"])
        self.assertIn("Katheterinfektion am", kompl[-1]["beschreibung"])
        self.assertIn("Katheter Port vom", kompl[-1]["beschreibung"])
        # „Alle“ enthält beide Bereiche und die Änderung der Kerndaten
        alle = {e["bereich"] for e in c.get(f"/api/patienten/{self.patient.id}/verlauf/").json()}
        self.assertTrue({"katheter", "katheter_komplikationen", "stammdaten"} <= alle)
        # Verlauf als PDF
        r = c.get(f"/api/patienten/{self.patient.id}/verlauf/pdf/?bereich=katheter")
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_aktenkopie_enthaelt_katheter(self):
        from io import BytesIO

        from pypdf import PdfReader
        from vorlagen.listen import aktenkopie_pdf

        k = self.anlegen(notiz="erster Port").json()
        self.komplikation(k["id"], notiz="Fieber")
        pdf = aktenkopie_pdf(Patient.objects.get(pk=self.patient.pk))
        text = " ".join("".join(s.extract_text() or "" for s in PdfReader(BytesIO(pdf)).pages).split())
        self.assertIn("Katheter-Historie", text)
        self.assertIn("V. subclavia rechts", text)
        self.assertIn("Katheterinfektion", text)
        self.assertIn("Infektionen je 1000 Kathetertage", text)


class Datenschutz(KatheterGrundlage):
    def test_dsgvo_loeschen_entfernt_historie(self):
        k = self.anlegen().json()
        self.komplikation(k["id"])
        client_fuer(self.mitarbeiter).patch(f"{URL}{k['id']}/", {"lage": "links"}, format="json")
        self.assertEqual(umfang(self.patient)["katheter"], 1)
        self.assertEqual(umfang(self.patient)["katheter_komplikationen"], 1)
        self.assertEqual(Katheter.history.filter(patient_id=self.patient.id).count(), 2)
        with wartungsmodus():
            akten_entfernen([self.patient.id])
        self.assertFalse(Katheter.objects.filter(pk=k["id"]).exists())
        self.assertEqual(Katheter.history.filter(patient_id=self.patient.id).count(), 0)
        self.assertEqual(KatheterKomplikation.history.filter(patient_id=self.patient.id).count(), 0)


class Testdaten(Grundlage):
    """Musterdaten: Testpatienten mit Katheter-Historie; Hanna Test bewusst ohne (Hinweis „Anlagedatum nicht erfasst“)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from .testdaten import testpatienten_anlegen

        testpatienten_anlegen()

    def test_historie_der_testpatienten(self):
        from .testdaten import TEST_KATHETER, TESTPATIENTEN

        for i, eintrag in enumerate(TESTPATIENTEN):
            p = Patient.objects.get(ist_test=True, nachname=eintrag[0])
            self.assertEqual(p.katheter_eintraege.count(), len(TEST_KATHETER.get(i, [])), eintrag[0])
            z = katheter_kennzahlen(p)
            if z["aktuell"]:
                # der liegende Katheter passt zu den Kerndaten
                self.assertEqual(z["aktuell"]["typ"], eintrag[7], eintrag[0])
        hanna = Patient.objects.get(ist_test=True, nachname="Test")
        self.assertTrue(katheter_kennzahlen(hanna)["anlagedatum_fehlt"])
        max_ = Patient.objects.get(ist_test=True, nachname="Mustermann")
        z = katheter_kennzahlen(max_)
        self.assertEqual((z["anzahl"], z["infektionen"]), (2, 1))
        self.assertIsNotNone(z["infektionen_je_1000"])
