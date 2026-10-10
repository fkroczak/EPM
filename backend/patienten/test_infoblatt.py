"""Infoblatt an die Praxis (F177): Ortsfilter, Telefontermine, Vorschau ohne PDF, Schnappschuss mit „neu“,
Erinnerung auf der Startseite, Einstellungen und Löschung – gegen die echte PostgreSQL-Datenbank."""
import json
import shutil
import tempfile
from datetime import date, time, timedelta
from pathlib import Path
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from audit.schutz import wartungsmodus
from epm.pruefhilfen import Grundlage, client_fuer
from stammdaten.models import Auswahlwert, Einstellungen

from .datenschutz import akten_entfernen
from .infoblatt import erinnerung, naechster_zeitraum
from .models import Ankuendigung, Patient, Termin

DOKUMENTE = tempfile.mkdtemp(prefix="epm-infoblatt-")
URL = "/api/kalender/ankuendigung/"


@override_settings(EPM_DOKUMENTE=Path(DOKUMENTE))
class InfoblattTest(Grundlage):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(DOKUMENTE, ignore_errors=True)

    def setUp(self):
        self.praxis = Auswahlwert.objects.get(liste=Auswahlwert.Liste.TERMINORT, wert="Praxis Dr. Holtmeier")
        self.telefon, _ = Auswahlwert.objects.get_or_create(liste=Auswahlwert.Liste.TERMINORT, wert="Telefon/Video")
        self.klinik, _ = Auswahlwert.objects.get_or_create(liste=Auswahlwert.Liste.TERMINORT, wert="Klinik")
        # nächste Woche (Mo–So) ab heute – Termine liegen immer in der Zukunft
        self.von, self.bis = naechster_zeitraum(timezone.localdate(), "woche")
        self.mo, self.di = self.von, self.von + timedelta(days=1)
        self.kaufmann = Patient.objects.create(nachname="Kaufmann", vorname="Marija", geburtsdatum="1980-01-01")
        self.flegel = Patient.objects.create(nachname="Flegel", vorname="Angelika", geburtsdatum="1970-01-01",
                                             telefon="+49 1767 038 1718")
        self.ohne = Patient.objects.create(nachname="Ohneort", vorname="Olga", geburtsdatum="1960-01-01")
        self.anders = Patient.objects.create(nachname="Anders", vorname="Arne", geburtsdatum="1960-01-01")
        self.t_praxis = self.termin(self.kaufmann, self.mo, time(14, 30), self.praxis)
        self.t_telefon = self.termin(self.flegel, self.mo, time(15), self.telefon)
        self.t_ohne = self.termin(self.ohne, self.di, time(9), None)
        self.t_klinik = self.termin(self.anders, self.di, time(10), self.klinik)
        Termin.objects.create(patient=self.kaufmann, art=Termin.Art.WIEDERVORLAGE, faellig_am=self.mo, titel="nicht dabei")
        self.c = client_fuer(self.mitarbeiter)

    def termin(self, patient, tag, uhr, ort, **extra):
        return Termin.objects.create(patient=patient, art=Termin.Art.PRAXISTERMIN, faellig_am=tag, uhrzeit=uhr, ort=ort,
                                     titel="Sprechstunde", **extra)

    def liste(self, **extra):
        r = self.c.post(URL, {"von": str(self.von), "bis": str(self.bis), "ort": self.praxis.id, "ausgabe": "liste",
                              **extra}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_ortsfilter_und_telefontermine(self):
        d = self.liste()
        self.assertEqual([t["termin"] for t in d["termine"]], [self.t_praxis.id])
        self.assertEqual(d["anzahl"], 1)
        self.assertEqual(d["ort"], {"id": self.praxis.id, "wert": "Praxis Dr. Holtmeier"})
        # ohne Ort: nicht auf dem Blatt, aber als Warnung mit Akte und Termin
        self.assertEqual(d["ohne_ort"], [{"termin": self.t_ohne.id, "patient": self.ohne.id, "name": "Olga Ohneort",
                                          "datum": str(self.di), "uhrzeit": "09:00"}])
        t = d["termine"][0]
        self.assertEqual((t["name"], t["uhrzeit"], t["hinweis"], t["neu"], t["patient"]),
                         ("Marija Kaufmann", "14:30", "", False, self.kaufmann.id))
        # Telefon- und Videotermine auf Wunsch zusätzlich, mit Telefonnummer
        d = self.liste(telefon_mit=True)
        self.assertEqual([t["termin"] for t in d["termine"]], [self.t_praxis.id, self.t_telefon.id])
        self.assertEqual(d["termine"][1]["hinweis"], "Telefon/Video +49 1767 038 1718")
        # ohne Ort („– alle –“): alle Praxistermine wie bisher, keine Warnung
        d = self.liste(ort=None)
        self.assertEqual([t["termin"] for t in d["termine"]],
                         [self.t_praxis.id, self.t_telefon.id, self.t_ohne.id, self.t_klinik.id])
        self.assertEqual(d["ohne_ort"], [])
        # die E-Mail enthält nur, was auf dem Blatt steht
        mail = self.c.post(URL, {"von": str(self.von), "bis": str(self.bis), "ort": self.praxis.id, "ausgabe": "email"},
                           format="json").json()
        self.assertIn("Marija Kaufmann", mail["text"])
        for nicht in ("Angelika", "Olga", "Arne", "nicht dabei"):
            self.assertNotIn(nicht, mail["text"])
        mail = self.c.post(URL, {"von": str(self.von), "bis": str(self.bis), "ort": self.praxis.id, "ausgabe": "email",
                                 "telefon_mit": True}, format="json").json()
        self.assertIn("Angelika Flegel → Telefon/Video +49 1767 038 1718", mail["text"])

    def test_pruefungen_und_rechte(self):
        basis = {"von": str(self.von), "bis": str(self.bis), "ausgabe": "liste"}
        for falsch, feld in (({"telefon_mit": "ja"}, "telefon_mit"), ({"ort": 999999}, "ort"),
                             ({"ort": "Praxis"}, "ort"), ({"bis": str(self.von - timedelta(days=1))}, "bis"),
                             ({"bis": str(self.von + timedelta(days=70))}, "bis"), ({"von": "morgen"}, "von")):
            r = self.c.post(URL, {**basis, **falsch}, format="json")
            self.assertEqual(r.status_code, 400, falsch)
            self.assertIn(feld, r.json())
        self.assertEqual(self.c.post(URL, {**basis, "ausgabe": "fax"}, format="json").status_code, 400)
        self.assertEqual(client_fuer(self.betrachter).post(URL, basis, format="json").status_code, 403)
        self.assertEqual(Ankuendigung.objects.count(), 0)

    def test_schnappschuss_und_neu(self):
        self.assertIsNone(self.liste()["letzte"])
        self.assertEqual(Ankuendigung.objects.count(), 0)   # Vorschau und E-Mail-Text merken nichts
        r = self.c.post(URL, {"von": str(self.von), "bis": str(self.bis), "ort": self.praxis.id, "vorschau": True},
                        format="json")   # „PDF ansehen“
        self.assertEqual((r.status_code, Ankuendigung.objects.count()), (200, 0))
        r = self.c.post(URL, {"von": str(self.von), "bis": str(self.bis), "ort": self.praxis.id, "telefon_mit": True},
                        format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r["Content-Type"], "application/pdf")
        a = Ankuendigung.objects.get()
        self.assertEqual((a.benutzer, a.von, a.bis, a.ort, a.telefon_mit, a.ausgabe, a.anzahl),
                         (self.mitarbeiter, self.von, self.bis, self.praxis, True, "pdf", 2))
        self.assertEqual(a.termine, [{"termin": self.t_praxis.id, "datum": str(self.mo), "uhrzeit": "14:30"},
                                     {"termin": self.t_telefon.id, "datum": str(self.mo), "uhrzeit": "15:00"}])
        self.assertNotIn("Kaufmann", json.dumps(a.termine))   # keine Namen im Schnappschuss
        d = self.liste(telefon_mit=True)
        self.assertEqual(d["letzte"]["anzahl"], 2)
        self.assertEqual((d["letzte"]["von"], d["letzte"]["bis"], d["letzte"]["ausgabe"]), (str(self.von), str(self.bis), "pdf"))
        self.assertTrue(d["letzte"]["von_name"])
        self.assertEqual([t["neu"] for t in d["termine"]], [False, False])
        # danach: ein neuer Termin am selben Tag, ein verschobener, ein abgesagter
        neu = self.termin(self.anders, self.mo, time(16), self.praxis)
        Termin.objects.filter(pk=self.t_praxis.pk).update(uhrzeit=time(11))
        Termin.objects.filter(pk=self.t_telefon.pk).update(ausgeblendet_dauerhaft=True)
        d = self.liste(telefon_mit=True)
        zeilen = {t["termin"]: t for t in d["termine"]}
        self.assertTrue(zeilen[neu.id]["neu"])
        self.assertIsNone(zeilen[neu.id]["vorher"])
        self.assertTrue(zeilen[self.t_praxis.id]["neu"])
        self.assertEqual(zeilen[self.t_praxis.id]["vorher"], {"datum": str(self.mo), "uhrzeit": "14:30"})
        self.assertEqual([(e["termin"], e["name"]) for e in d["entfallen"]], [(self.t_telefon.id, "Angelika Flegel")])
        # ein Tag, für den noch kein Blatt bestand (hier: Blatt nur bis Montag), ist nicht „neu“
        Ankuendigung.objects.update(bis=self.mo)
        spaeter = self.termin(self.kaufmann, self.di, time(8), self.praxis)
        d = self.liste()
        self.assertFalse({t["termin"]: t for t in d["termine"]}[spaeter.id]["neu"])
        # E-Mail (.eml) wird ebenfalls gemerkt; ein anderer Ort hat eigene Blätter
        r = self.c.post(URL, {"von": str(self.von), "bis": str(self.bis), "ausgabe": "eml"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        b = Ankuendigung.objects.first()
        self.assertEqual((b.ausgabe, b.ort, b.anzahl), ("eml", None, 5))
        self.assertEqual(self.liste()["letzte"]["ausgabe"], "pdf")

    def test_loeschung_entfernt_termine_aus_dem_schnappschuss(self):
        self.c.post(URL, {"von": str(self.von), "bis": str(self.bis), "ort": self.praxis.id, "telefon_mit": True},
                    format="json")
        self.assertEqual(len(Ankuendigung.objects.get().termine), 2)
        with wartungsmodus():
            akten_entfernen([self.kaufmann.id])
        a = Ankuendigung.objects.get()
        self.assertEqual([e["termin"] for e in a.termine], [self.t_telefon.id])
        self.assertEqual(a.anzahl, 2)   # nur die Zahl bleibt

    def test_erinnerung(self):
        e = Einstellungen.aktuell()
        self.assertEqual((e.infoblatt_rhythmus, e.infoblatt_vorlauf_tage), ("woche", 3))
        freitag = self.von - timedelta(days=3)
        # vor dem Vorlauf nichts, ab Freitag (Montag − 3 Tage) bis Sonntag der Hinweis
        self.assertIsNone(erinnerung(self.mitarbeiter, self.von - timedelta(days=4)))
        h = erinnerung(self.mitarbeiter, freitag)
        self.assertEqual((h["von"], h["bis"], h["anzahl"], h["ohne_ort"], h["rhythmus"]),
                         (self.von, self.bis, 1, 1, "woche"))
        self.assertEqual(h["ort"]["wert"], "Praxis Dr. Holtmeier")
        self.assertIsNotNone(erinnerung(self.mitarbeiter, self.von - timedelta(days=1)))
        # nur mit dem Recht „Einträge erfassen“
        self.assertIsNone(erinnerung(self.betrachter, freitag))
        # über die Startseite (Datum auf Freitag gestellt)
        with mock.patch("patienten.infoblatt.timezone") as uhr:
            uhr.localdate.return_value = freitag
            d = client_fuer(self.mitarbeiter).get("/api/startseite/").json()
            self.assertEqual((d["infoblatt"]["von"], d["infoblatt"]["anzahl"]), (str(self.von), 1))
            self.assertIsNone(client_fuer(self.betrachter).get("/api/startseite/").json()["infoblatt"])
            # erstellt (PDF für den Zeitraum) → kein Hinweis mehr
            self.c.post(URL, {"von": str(self.von), "bis": str(self.bis), "ort": self.praxis.id}, format="json")
            self.assertIsNone(client_fuer(self.mitarbeiter).get("/api/startseite/").json()["infoblatt"])
        # „keine Erinnerung“ und monatlich
        Einstellungen.objects.filter(pk=1).update(infoblatt_rhythmus="aus")
        Ankuendigung.objects.all().delete()
        self.assertIsNone(erinnerung(self.mitarbeiter, freitag))
        self.assertEqual(naechster_zeitraum(date(2026, 12, 20), "monat"), (date(2027, 1, 1), date(2027, 1, 31)))
        self.assertEqual(naechster_zeitraum(date(2028, 1, 31), "monat"), (date(2028, 2, 1), date(2028, 2, 29)))
        self.assertEqual(naechster_zeitraum(date(2026, 10, 10), "woche"), (date(2026, 10, 12), date(2026, 10, 18)))
        self.assertEqual(naechster_zeitraum(date(2026, 10, 12), "woche"), (date(2026, 10, 19), date(2026, 10, 25)))
        # ohne Termine im Zeitraum kein Hinweis
        Einstellungen.objects.filter(pk=1).update(infoblatt_rhythmus="woche")
        Termin.objects.filter(art=Termin.Art.PRAXISTERMIN).update(art=Termin.Art.SONSTIGES)
        self.assertIsNone(erinnerung(self.mitarbeiter, freitag))

    def test_einstellungen(self):
        c = client_fuer(self.mitarbeiter)   # Vorlagen pflegen
        d = c.get("/api/einstellungen/").json()
        self.assertEqual((d["infoblatt_rhythmus"], d["infoblatt_vorlauf_tage"]), ("woche", 3))
        for falsch in ({"infoblatt_vorlauf_tage": 7}, {"infoblatt_vorlauf_tage": 0}, {"infoblatt_rhythmus": "jahr"},
                       {"infoblatt_rhythmus": "monat", "infoblatt_vorlauf_tage": 28}):
            r = c.patch("/api/einstellungen/", falsch, format="json")
            self.assertEqual(r.status_code, 400, falsch)
        r = c.patch("/api/einstellungen/", {"infoblatt_rhythmus": "monat", "infoblatt_vorlauf_tage": 10}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        # zurück auf wöchentlich: 10 Tage Vorlauf passen nicht mehr
        r = c.patch("/api/einstellungen/", {"infoblatt_rhythmus": "woche"}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("infoblatt_vorlauf_tage", r.json())
        # der Kalender kennt den Rhythmus (Vorschlag für den Zeitraum im Dialog)
        k = c.get(f"/api/kalender/?von={self.von}&bis={self.bis}").json()
        self.assertEqual(k["infoblatt_rhythmus"], "monat")
