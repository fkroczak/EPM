"""KI: Priorisierung (Einstellungen, Termin-Vorrang), Nachtaufgaben (Zeitplan, Ausführung, API), „Neu lesen“ und
„Akte auf einen Blick“ (Zeitraum, Fakten, Erstellen mit und ohne Modell, Gegenprüfung, API, KI-Dienst) – 14.11.2026."""
import datetime as dt
import os
from decimal import Decimal
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.utils import timezone

from accounts.models import Mitgliedschaft, Rolle
from audit.models import SystemEreignis
from befunde.models import Laborbefund, Laborwert
from epm.pruefhilfen import Grundlage, benutzer, client_fuer, echte_anmeldung, mit_zweitem_faktor
from infusionen.models import Infusionsplan
from ki import aufgaben, chat, dienst, eingang, zusammenfassung
from ki.models import KiAufgabe, KiEinstellung, KiModellversion, KiVorgang, KiZusammenfassung
from ki.steuerung import Entscheidung
from ki.testhilfen import KI_TMP, Attrappe, dokument
from patienten.models import Kontakt, Medikament, Patient, PatientFirma, Termin
from stammdaten.models import Firma, Laborparameter

A = SystemEreignis.Art
Z = KiZusammenfassung
BERLIN = ZoneInfo("Europe/Berlin")


def heute():
    return timezone.localdate()


def termin(patient, tage, art=Termin.Art.PRAXISTERMIN, **extra):
    return Termin.objects.create(patient=patient, art=art, faellig_am=heute() + dt.timedelta(days=tage),
                                 titel="Termin", **extra)


def pdf(patient, nr):
    return dokument(patient, b"%PDF-1.4 " + str(nr).encode(), name=f"d{nr}.pdf", mime="application/pdf")


@override_settings(EPM_KI=Path(KI_TMP))
class EinstellungenTest(Grundlage):
    def test_grenzen_und_reihenfolge_der_stufen(self):
        c = client_fuer(self.admin)
        r = c.put("/api/ki/einstellungen/", {"prio_termin": 7, "termin_tage": 5, "neu_tage": 14, "chat_tage": 60,
                                             "chat_vorrang": False, "zusammenfassung_tagsueber": False,
                                             "zusammenfassung_ohne_termin_tage": 120, "diktat_nacht_beginn": 22,
                                             "diktat_nacht_ende": 6}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        e = KiEinstellung.laden()
        self.assertEqual((e.prio_termin, e.termin_tage, e.chat_tage, e.chat_vorrang, e.diktat_nacht_beginn),
                         (7, 5, 60, False, 22))
        for feld, wert in (("prio_termin", 101), ("termin_tage", 31), ("neu_tage", 0), ("chat_tage", 0),
                           ("chat_tage", 366), ("diktat_nacht_beginn", 24), ("zusammenfassung_ohne_termin_tage", 6),
                           ("prio_angefordert", 101)):
            r = c.put("/api/ki/einstellungen/", {feld: wert}, format="json")
            self.assertEqual(r.status_code, 400, (feld, wert))
            self.assertIn(feld, r.json())
        # „angefordert“ muss die höchste Stufe sein – sonst nähme der Tagesbetrieb Termin-Dokumente wie angeforderte
        r = c.put("/api/ki/einstellungen/", {"prio_termin": 10}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("prio_termin", r.json())
        self.assertEqual(c.put("/api/ki/einstellungen/", {"prio_angefordert": 5}, format="json").status_code, 400)
        self.assertEqual(client_fuer(self.mitarbeiter).put("/api/ki/einstellungen/", {"prio_neu": 1},
                                                           format="json").status_code, 403)

    def test_angefordert_bleibt_angefordert_wenn_die_stufe_wechselt(self):
        a, b = pdf(self.patient, 1), pdf(self.patient, 2)
        eingang.vormerken()
        eingang.anfordern(a, self.mitarbeiter)
        c = client_fuer(self.admin)
        self.assertEqual(c.put("/api/ki/einstellungen/", {"prio_angefordert": 50}, format="json").status_code, 200)
        self.assertEqual(KiVorgang.objects.get(dokument=a).prioritaet, 50)
        self.assertEqual(KiVorgang.objects.get(dokument=b).prioritaet, 5)
        # niedriger: neue Dokumente (5) würden sonst „angefordert“ – sie bleiben darunter
        r = c.put("/api/ki/einstellungen/", {"prio_angefordert": 4, "prio_termin": 3, "prio_neu": 2,
                                             "prio_neu_lesen": 1}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(KiVorgang.objects.get(dokument=a).prioritaet, 4)
        self.assertEqual(KiVorgang.objects.get(dokument=b).prioritaet, 3)
        self.assertEqual(dienst.auftrag_holen(nur_angefordert=True, nachverarbeitung=False).dokument_id, a.pk)
        self.assertIsNone(dienst.auftrag_holen(nur_angefordert=True, nachverarbeitung=False))

    @mock.patch.dict(os.environ, {"EPM_KI_CHAT_TAGE": "12", "EPM_DIKTAT_NACHT": "20-8"})
    def test_umgebungsvariablen_nur_startwert_und_rueckfall(self):
        from diktate import dienst as diktat_dienst

        KiEinstellung.objects.all().delete()
        nacht = timezone.localtime(timezone.now()).replace(hour=21)
        # ohne Einstellungszeile: Umgebung (und die Diktate legen keine Zeile an)
        self.assertEqual(chat.aufbewahrung_tage(), 12)
        self.assertTrue(diktat_dienst.nachtfenster(nacht))
        self.assertFalse(KiEinstellung.objects.exists())
        e = KiEinstellung.laden()  # Startwerte aus der Umgebung
        self.assertEqual((e.chat_tage, e.diktat_nacht_beginn, e.diktat_nacht_ende), (12, 20, 8))
        KiEinstellung.objects.filter(pk=1).update(chat_tage=5, diktat_nacht_beginn=22, diktat_nacht_ende=6)
        self.assertEqual(chat.aufbewahrung_tage(), 5)
        self.assertFalse(diktat_dienst.nachtfenster(nacht))
        self.assertTrue(diktat_dienst.nachtfenster(nacht.replace(hour=23)))
        self.assertTrue(diktat_dienst.nachtfenster(nacht.replace(hour=5)))


@override_settings(EPM_KI=Path(KI_TMP))
class TerminVorrangTest(Grundlage):
    def test_termin_hebt_wartende_an_aber_nie_bis_angefordert(self):
        mit = Patient.objects.create(nachname="Termin", vorname="Tim", geburtsdatum="1970-01-01")
        ausgeblendet = Patient.objects.create(nachname="Aus", vorname="Al", geburtsdatum="1970-01-01")
        spaet = Patient.objects.create(nachname="Spät", vorname="Sam", geburtsdatum="1970-01-01")
        termin(mit, 2)
        termin(self.patient, 1, art=Termin.Art.RUECKRUF)
        termin(ausgeblendet, 1, ausgeblendet_dauerhaft=True)
        termin(spaet, 5)
        d = {p.pk: pdf(p, i) for i, p in enumerate([mit, self.patient, ausgeblendet, spaet])}
        eingang.vormerken()
        hoch = pdf(mit, 9)
        eingang.anfordern(hoch, self.mitarbeiter)
        KiVorgang.objects.filter(dokument=d[mit.pk]).update(prioritaet=9)  # höhere bleibt
        self.assertEqual(eingang.prioritaeten_aktualisieren(), 0)
        KiVorgang.objects.filter(dokument=d[mit.pk]).update(prioritaet=5)
        self.assertEqual(eingang.prioritaeten_aktualisieren(), 1)
        prio = dict(KiVorgang.objects.values_list("dokument_id", "prioritaet"))
        self.assertEqual(prio[d[mit.pk].pk], 8)
        self.assertEqual(prio[d[self.patient.pk].pk], 5)  # Rückruf zählt nicht
        self.assertEqual(prio[d[ausgeblendet.pk].pk], 5)
        self.assertEqual(prio[d[spaet.pk].pk], 5)  # außerhalb von termin_tage (3)
        self.assertEqual(prio[hoch.pk], 10)
        # Tagesbetrieb mit worker_tag = 0: nur das angeforderte, nicht das mit Termin
        self.assertEqual(dienst.auftrag_holen(nur_angefordert=True, nachverarbeitung=False).dokument_id, hoch.pk)
        self.assertIsNone(dienst.auftrag_holen(nur_angefordert=True, nachverarbeitung=False))
        self.assertEqual(dienst.auftrag_holen(nur_angefordert=False, nachverarbeitung=False).dokument_id,
                         d[mit.pk].pk)
        # Termin-Vorrang aus
        KiEinstellung.objects.filter(pk=1).update(termin_tage=0)
        self.assertEqual(eingang.prioritaeten_aktualisieren(), 0)

    def test_altbestand_und_neu_aus_den_einstellungen(self):
        KiEinstellung.laden()
        KiEinstellung.objects.filter(pk=1).update(prio_neu=6, prio_altbestand=1, neu_tage=2)
        neu, alt = pdf(self.patient, 1), pdf(self.patient, 2)
        type(alt).objects.filter(pk=alt.pk).update(hochgeladen_am=timezone.now() - dt.timedelta(days=3))
        eingang.vormerken(altbestand=True)
        prio = dict(KiVorgang.objects.values_list("dokument_id", "prioritaet"))
        self.assertEqual((prio[neu.pk], prio[alt.pk]), (6, 1))


class ZeitplanTest(Grundlage):
    def aufgabe(self, **extra):
        werte = {"name": "x", "art": "dokumente_vormerken", "aktiv": True, "wochentage": [0], "uhrzeit": dt.time(3),
                 "geaendert_am": dt.datetime(2026, 11, 1, tzinfo=dt.UTC), "letzter_lauf": None}
        return KiAufgabe(**{**werte, **extra})

    def test_faellig_wochentag_uhrzeit_zeitzone(self):
        montag_0330 = dt.datetime(2026, 11, 16, 2, 30, tzinfo=dt.UTC)  # 03:30 in Berlin (Winterzeit)
        a = self.aufgabe()
        self.assertTrue(aufgaben.faellig(a, montag_0330, BERLIN))
        self.assertFalse(aufgaben.faellig(a, montag_0330 - dt.timedelta(hours=1), BERLIN))  # 02:30 Ortszeit
        self.assertFalse(aufgaben.faellig(a, montag_0330, ZoneInfo("UTC")))  # dort erst 02:30
        self.assertFalse(aufgaben.faellig(self.aufgabe(wochentage=[1, 2]), montag_0330, BERLIN))
        self.assertFalse(aufgaben.faellig(self.aufgabe(aktiv=False), montag_0330, BERLIN))
        # heute schon gelaufen (nach der Uhrzeit) – erst nächste Woche wieder
        gelaufen = self.aufgabe(letzter_lauf=montag_0330 - dt.timedelta(minutes=20))
        self.assertFalse(aufgaben.faellig(gelaufen, montag_0330, BERLIN))
        self.assertEqual(aufgaben.naechster_lauf(gelaufen, montag_0330, BERLIN),
                         dt.datetime(2026, 11, 23, 3, tzinfo=BERLIN))
        # „Jetzt“ um 01:00 lief vor der Uhrzeit: der Lauf um 03:00 kommt trotzdem
        frueh = self.aufgabe(letzter_lauf=dt.datetime(2026, 11, 16, 0, 0, tzinfo=dt.UTC))
        self.assertTrue(aufgaben.faellig(frueh, montag_0330, BERLIN))
        # nach der Uhrzeit angelegt oder geändert: erst beim nächsten Termin
        geaendert = self.aufgabe(geaendert_am=montag_0330 - dt.timedelta(minutes=5))
        self.assertFalse(aufgaben.faellig(geaendert, montag_0330, BERLIN))
        # nicht gelaufen (Dienst aus): am selben Tag nachgeholt
        self.assertTrue(aufgaben.faellig(a, montag_0330 + dt.timedelta(hours=8), BERLIN))
        self.assertEqual(aufgaben.naechster_lauf(a, montag_0330, BERLIN), dt.datetime(2026, 11, 16, 3, tzinfo=BERLIN))
        # „Jetzt ausführen“ auch für eine inaktive Aufgabe und an jedem Tag
        jetzt = self.aufgabe(aktiv=False, wochentage=[4], jetzt_angefordert=True)
        self.assertTrue(aufgaben.faellig(jetzt, montag_0330, BERLIN))
        self.assertIsNone(aufgaben.naechster_lauf(self.aufgabe(aktiv=False), montag_0330, BERLIN))

    def test_mitgelieferte_aufgaben(self):
        a = KiAufgabe.objects.get(art="zusammenfassung_termine")
        self.assertEqual((a.aktiv, a.uhrzeit, a.wochentage, a.parameter),
                         (True, dt.time(3), list(range(7)), {"tage_voraus": 1}))
        n = KiAufgabe.objects.get(art="neu_lesen")
        self.assertEqual((n.aktiv, n.uhrzeit, n.wochentage), (False, dt.time(1), [6]))

    @override_settings(EPM_KI=Path(KI_TMP))
    def test_faellige_reihen_arbeit_ein_einmal_mit_audit(self):
        KiAufgabe.objects.update(aktiv=False)
        a = KiAufgabe.objects.create(name="Altbestand", art="dokumente_vormerken", uhrzeit=dt.time(0),
                                     parameter={"altbestand": True})
        KiAufgabe.objects.filter(pk=a.pk).update(geaendert_am=timezone.now() - dt.timedelta(days=2))
        pdf(self.patient, 1)
        self.assertEqual(aufgaben.faellige_ausfuehren(), 1)
        a.refresh_from_db()
        self.assertEqual(a.letztes_ergebnis, "1 Dokument vorgemerkt")
        self.assertIsNotNone(a.letzter_lauf)
        self.assertEqual(KiVorgang.objects.count(), 1)
        ev = SystemEreignis.objects.get(art=A.KI, details__aktion="aufgabe")
        self.assertEqual(ev.details["aufgabenart"], "dokumente_vormerken")
        self.assertEqual(aufgaben.faellige_ausfuehren(), 0)  # heute schon gelaufen
        KiAufgabe.objects.filter(pk=a.pk).update(jetzt_angefordert=True)
        self.assertEqual(aufgaben.faellige_ausfuehren(), 1)
        a.refresh_from_db()
        self.assertFalse(a.jetzt_angefordert)
        self.assertEqual(a.letztes_ergebnis, "0 Dokumente vorgemerkt")


@override_settings(EPM_KI=Path(KI_TMP))
class AufgabenApiTest(Grundlage):
    def test_rechte_validierung_jetzt_loeschen(self):
        for u in (self.betrachter, self.mitarbeiter, self.mediziner):
            self.assertEqual(client_fuer(u).get("/api/ki/aufgaben/").status_code, 403)
        c = client_fuer(self.admin)
        r = c.get("/api/ki/aufgaben/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual({x["art"] for x in r.json()}, {"zusammenfassung_termine", "neu_lesen"})
        self.assertIn("naechster_lauf", r.json()[0])
        daten = {"name": "Termine übermorgen", "art": "zusammenfassung_termine", "aktiv": True,
                 "wochentage": [0, 2, 4], "uhrzeit": "02:30", "parameter": {"tage_voraus": 2}}
        r = c.post("/api/ki/aufgaben/", daten, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        neu = r.json()
        self.assertEqual((neu["uhrzeit"], neu["art_name"], neu["parameter"]),
                         ("02:30", "Akte auf einen Blick für die nächsten Termine", {"tage_voraus": 2}))
        for falsch in ({"wochentage": []}, {"wochentage": [7]}, {"art": "kaffee"},
                       {"parameter": {"tage_voraus": 15}}, {"parameter": {"tage_voraus": "x"}}):
            self.assertEqual(c.post("/api/ki/aufgaben/", {**daten, **falsch}, format="json").status_code, 400,
                             falsch)
        r = c.post("/api/ki/aufgaben/", {**daten, "parameter": {"tage_voraus": 15}}, format="json")
        self.assertIn("parameter.tage_voraus", r.json())
        # PATCH mit dem ganzen Objekt; anderer Art: Parameter dieser Art (Standard ergänzt)
        r = c.patch(f"/api/ki/aufgaben/{neu['id']}/", {**daten, "art": "neu_lesen",
                                                       "parameter": {"hoechstens": 50, "dokumenttypen": ["labor"]}},
                    format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["parameter"], {"seit_tagen": 30, "dokumenttypen": ["labor"],
                                                 "nur_anderes_modell": True, "hoechstens": 50})
        r = c.patch(f"/api/ki/aufgaben/{neu['id']}/", {"parameter": {"dokumenttypen": ["rezept"]}}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("parameter.dokumenttypen", r.json())
        self.assertEqual(client_fuer(self.mitarbeiter).post(f"/api/ki/aufgaben/{neu['id']}/jetzt/").status_code, 403)
        r = c.post(f"/api/ki/aufgaben/{neu['id']}/jetzt/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["jetzt_angefordert"])
        self.assertTrue(KiAufgabe.objects.get(pk=neu["id"]).jetzt_angefordert)
        self.assertEqual(c.delete(f"/api/ki/aufgaben/{neu['id']}/").status_code, 204)
        aktionen = set(SystemEreignis.objects.filter(art=A.KI).values_list("details__aktion", flat=True))
        self.assertTrue({"aufgabe_angelegt", "aufgabe_geaendert", "aufgabe_jetzt", "aufgabe_geloescht"} <= aktionen)


@override_settings(EPM_KI=Path(KI_TMP))
class NeuLesenTest(Grundlage):
    def vorgang(self, nr, status, patient=None, **extra):
        patient = patient or self.patient
        d = pdf(patient, nr)
        return KiVorgang.objects.create(dokument=d, patient=patient, firma_id=d.firma_id, sha256=d.sha256,
                                        status=status, ist_test=patient.ist_test, dokumenttyp="labor", **extra)

    def test_filter_und_ausnahmen(self):
        alt = KiModellversion.objects.create(name="alt", datei="alt.gguf", sha256="a" * 64, status="archiviert")
        aktiv = KiModellversion.objects.create(name="neu", datei="neu.gguf", sha256="b" * 64, status="aktiv")
        pruef = self.vorgang(1, "zur_pruefung", modellversion=alt)
        fehler = self.vorgang(2, "fehler", modellversion=alt)
        ausgenommen = [self.vorgang(3, "uebernommen", modellversion=alt), self.vorgang(4, "abgelehnt"),
                       self.vorgang(5, "in_verarbeitung"), self.vorgang(6, "neu")]
        schon_neu = self.vorgang(7, "zur_pruefung", modellversion=aktiv)
        arztbrief = self.vorgang(8, "zur_pruefung", modellversion=alt)
        KiVorgang.objects.filter(pk=arztbrief.pk).update(dokumenttyp="arztbrief")
        vorher = dict(KiVorgang.objects.values_list("pk", "status"))
        self.assertEqual(eingang.neu_lesen(seit_tagen=30, dokumenttypen=["labor"], nur_anderes_modell=True,
                                           hoechstens=1), 1)
        self.assertEqual(eingang.neu_lesen(seit_tagen=30, dokumenttypen=["labor"], nur_anderes_modell=True,
                                           hoechstens=200), 1)
        for v in (pruef, fehler):
            v.refresh_from_db()
            self.assertEqual((v.status, v.prioritaet, v.versuche), ("neu", 3, 0))
        for v in [*ausgenommen, schon_neu, arztbrief]:
            self.assertEqual(KiVorgang.objects.get(pk=v.pk).status, vorher[v.pk])
        self.assertEqual(eingang.neu_lesen(nur_anderes_modell=False, dokumenttypen=[]), 2)  # schon_neu, arztbrief
        # zu alt
        alt_dok = self.vorgang(9, "zur_pruefung")
        type(alt_dok.dokument).objects.filter(pk=alt_dok.dokument_id).update(
            hochgeladen_am=timezone.now() - dt.timedelta(days=40))
        self.assertEqual(eingang.neu_lesen(seit_tagen=30, nur_anderes_modell=False), 0)
        self.assertEqual(eingang.neu_lesen(seit_tagen=0, nur_anderes_modell=False), 1)
        # nicht über „angefordert“: läuft nachts
        self.assertIsNone(dienst.auftrag_holen(nur_angefordert=True, nachverarbeitung=False))

    def test_api_rechte_firma_und_einzelne(self):
        rg = Firma.objects.get(kuerzel="rg")
        rg_patient = Patient.objects.create(nachname="Klinik", vorname="Karla", geburtsdatum="1970-01-01")
        PatientFirma.objects.filter(patient=rg_patient).update(firma=rg)
        echt = self.vorgang(1, "zur_pruefung")
        v = self.vorgang(2, "zur_pruefung", patient=rg_patient)
        w = self.vorgang(3, "fehler", patient=rg_patient)
        for u in (self.betrachter, self.mitarbeiter):
            self.assertEqual(client_fuer(u).post("/api/ki/vorgaenge/neu_lesen/", {}, format="json").status_code, 403)
        rg_admin = benutzer("rgadmin", Rolle.KEINE)
        Mitgliedschaft.objects.create(benutzer=rg_admin, firma=rg, rolle=Rolle.ADMIN)
        c = echte_anmeldung(rg_admin, mit_zweitem_faktor(rg_admin, 1)[0])  # sieht nur Akten der RGC
        r = c.post("/api/ki/vorgaenge/neu_lesen/", {"vorgaenge": [echt.pk, v.pk]}, format="json")
        self.assertEqual(r.json(), {"vorgemerkt": 1})
        self.assertEqual(KiVorgang.objects.get(pk=echt.pk).status, "zur_pruefung")
        r = c.post("/api/ki/vorgaenge/neu_lesen/", {"seit_tagen": 30, "dokumenttypen": [],
                                                    "nur_anderes_modell": False, "hoechstens": 10}, format="json")
        self.assertEqual(r.json(), {"vorgemerkt": 1})
        self.assertEqual(KiVorgang.objects.get(pk=w.pk).status, "neu")
        self.assertEqual(KiVorgang.objects.get(pk=echt.pk).status, "zur_pruefung")
        r = c.post("/api/ki/vorgaenge/neu_lesen/", {"hoechstens": 0}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("hoechstens", r.json())
        self.assertEqual(c.post("/api/ki/vorgaenge/neu_lesen/", {"vorgaenge": "x"}, format="json").status_code, 400)
        self.assertEqual(SystemEreignis.objects.filter(art=A.KI, details__aktion="neu_lesen").count(), 2)
        r = client_fuer(self.admin).post("/api/ki/vorgaenge/neu_lesen/", {"nur_anderes_modell": False}, format="json")
        self.assertEqual(r.json(), {"vorgemerkt": 1})  # echt


@override_settings(EPM_KI=Path(KI_TMP))
class ZusammenfassungTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.kalium = Laborparameter.objects.get(name="Kalium")
        cls.natrium = Laborparameter.objects.get(name="Natrium")

    def tage(self, n):
        return heute() - dt.timedelta(days=n)

    def labor(self, tag, param, wert):
        b = Laborbefund.objects.create(patient=self.patient, abgenommen_am=tag)
        Laborwert.objects.create(befund=b, parameter=param, wert=Decimal(wert), einheit="mmol/l",
                                 referenz_von=Decimal("3.5") if param == self.kalium else Decimal("135"),
                                 referenz_bis=Decimal("5.1") if param == self.kalium else Decimal("145"))

    def kontakt(self, tage, text="<p>Telefonat: Port gespült</p>"):
        return Kontakt.objects.create(patient=self.patient, zeitpunkt=timezone.now() - dt.timedelta(days=tage),
                                      text=text)

    def test_zeitraum_termin_kontakt_standard(self):
        self.assertEqual(zusammenfassung.zeitraum(self.patient), (self.tage(90), "standard"))
        self.kontakt(20)
        self.kontakt(0)  # heute zählt nicht
        self.assertEqual(zusammenfassung.zeitraum(self.patient), (self.tage(20), "kontakt"))
        termin(self.patient, -30)
        termin(self.patient, -3, art=Termin.Art.RUECKRUF)
        termin(self.patient, -5, ausgeblendet_dauerhaft=True)
        termin(self.patient, 2)
        self.assertEqual(zusammenfassung.zeitraum(self.patient), (self.tage(30), "termin"))
        KiEinstellung.laden()
        KiEinstellung.objects.filter(pk=1).update(zusammenfassung_ohne_termin_tage=10)
        anderer = Patient.objects.create(nachname="Neu", vorname="N", geburtsdatum="1970-01-01")
        self.assertEqual(zusammenfassung.zeitraum(anderer), (self.tage(10), "standard"))

    def test_fakten_wichtiges_zuerst_mit_links(self):
        self.labor(self.tage(40), self.kalium, "2.9")  # vor dem Zeitraum
        self.labor(self.tage(5), self.natrium, "140")
        self.labor(self.tage(4), self.kalium, "3.1")
        vorher = Infusionsplan.objects.create(patient=self.patient, status=Infusionsplan.Status.ABGELOEST,
                                              gueltig_ab=self.tage(60), kalium_mmol=Decimal("20"),
                                              herkunft=Infusionsplan.Herkunft.ALTSYSTEM)
        Infusionsplan.objects.create(patient=self.patient, status=Infusionsplan.Status.AKTUELL,
                                     gueltig_ab=self.tage(3), kalium_mmol=Decimal("40"), glucose_g=Decimal("150"),
                                     vorgaenger=vorher, herkunft=Infusionsplan.Herkunft.ALTSYSTEM)
        Infusionsplan.objects.create(patient=self.patient, status=Infusionsplan.Status.ENTWURF,
                                     gueltig_ab=self.tage(1), kalium_mmol=Decimal("99"))
        Medikament.objects.create(patient=self.patient, wirkstoff="Pantoprazol", staerke="40 mg", morgens="1",
                                  seit=self.tage(6))
        self.kontakt(2)
        Kontakt.objects.filter(pk=self.kontakt(1, "storniert").pk).update(storniert_am=timezone.now())
        fakten = zusammenfassung.fakten_sammeln(self.patient, self.tage(30), heute())
        texte = [f["text"] for f in fakten]
        self.assertEqual([f["nr"] for f in fakten], list(range(1, len(fakten) + 1)))
        self.assertTrue(texte[0].startswith("Labor") and "Kalium 3,1" in texte[0] and "unterhalb" in texte[0],
                        texte)
        self.assertEqual(fakten[0]["link"], "labor")
        self.assertEqual(fakten[0]["quelle"]["modell"], "laborwert")
        self.assertTrue(any("Kalium 20 → 40 mmol" in t and "Glucose neu 150 g" in t for t in texte), texte)
        self.assertFalse(any("99" in t or "2,9" in t or "storniert" in t for t in texte), texte)
        links = {f["quelle"]["modell"]: f["link"] for f in fakten}
        self.assertEqual(links, {"laborwert": "labor", "infusionsplan": "plaene", "medikament": "medikamente",
                                 "kontakt": "kontakte"})
        natrium = texte.index(next(t for t in texte if "Natrium" in t))
        plan = texte.index(next(t for t in texte if "Infusionsplan" in t))
        self.assertLess(plan, natrium)  # unauffällige Laborwerte nach Plan und Medikation
        self.assertIn("Telefonat: Port gespült", texte[-1])

    def test_erstellen_mit_und_ohne_modell_und_gegenpruefung(self):
        termin(self.patient, -10)
        self.labor(self.tage(4), self.kalium, "3.1")
        z = Z.objects.create(patient=self.patient, grund="angefordert", angefordert_von=self.mitarbeiter)
        zusammenfassung.erstellen(z, None)
        z.refresh_from_db()
        self.assertEqual((z.status, z.von, z.bis, z.von_grund), ("fertig", self.tage(10), heute(), "termin"))
        self.assertTrue(z.entwurf.startswith("- Labor"))
        self.assertIn("[1]", z.entwurf)
        self.assertTrue(z.pruefung["ok"], z.pruefung)
        self.assertIsNone(z.modellversion)
        KiModellversion.objects.create(name="Qwen", datei="q.gguf", sha256="q" * 64, status="aktiv")
        modell = Attrappe(bericht="Labor: Kalium 3,1 mmol/l [1]. Wir empfehlen 9,9 mmol/l Kalium [7].")
        z2 = zusammenfassung.erstellen(Z.objects.create(patient=self.patient, grund="termin"), modell)
        self.assertEqual(modell.anfragen[0]["system"], zusammenfassung.prompts.ZUSAMMENFASSUNG_AKTE[:40])
        self.assertIn("[1] Labor", modell.anfragen[0]["text"])
        p = z2.pruefung
        self.assertFalse(p["ok"])
        self.assertEqual((p["unbelegte_werte"], p["unbekannte_belege"]), (["9,9"], [7]))
        self.assertTrue(p["empfehlung_oder_bewertung"])
        self.assertEqual(z2.modellversion.name, "Qwen")
        # nichts Neues: ein Satz mit dem Datum des Zeitraums – das gilt als belegt
        leer = Patient.objects.create(nachname="Leer", vorname="L", geburtsdatum="1970-01-01")
        z3 = zusammenfassung.erstellen(Z.objects.create(patient=leer, grund="angefordert"), modell)
        self.assertEqual(z3.entwurf, f"Seit dem {self.tage(90):%d.%m.%Y} keine neuen Einträge.")
        self.assertTrue(z3.pruefung["ok"], z3.pruefung)
        self.assertEqual(len(modell.anfragen), 1)  # ohne Fakten kein Modellaufruf
        ev = SystemEreignis.objects.filter(art=A.KI, details__aktion="zusammenfassung_erstellt").first()
        self.assertNotIn("Kalium", str(ev.details))

    def test_termine_vorbereiten_je_patient_einmal(self):
        zweiter = Patient.objects.create(nachname="Zwei", vorname="Z", geburtsdatum="1970-01-01")
        t = termin(self.patient, 1)
        termin(self.patient, 0)
        termin(zweiter, 3)  # zu weit
        termin(zweiter, 1, art=Termin.Art.WIEDERVORLAGE)
        self.assertEqual(zusammenfassung.termine_vorbereiten(1), 1)
        z = Z.objects.get()
        self.assertEqual((z.grund, z.status, z.patient_id), ("termin", "wartet", self.patient.pk))
        self.assertNotEqual(z.termin_id, t.pk)  # der frühere Termin (heute)
        self.assertEqual(zusammenfassung.termine_vorbereiten(1), 0)
        Z.objects.update(status="fertig")
        self.assertEqual(zusammenfassung.termine_vorbereiten(1), 0)  # für diesen Termin schon fertig
        self.assertEqual(zusammenfassung.termine_vorbereiten(3), 1)  # zweiter

    def test_api_rechte_firma_409(self):
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(client_fuer(self.betrachter).get(f"/api/ki/zusammenfassungen/?patient={self.patient.pk}")
                         .status_code, 403)
        self.assertEqual(client_fuer(self.betrachter).post("/api/ki/zusammenfassungen/",
                                                           {"patient": self.patient.pk}, format="json").status_code,
                         403)
        r = c.post("/api/ki/zusammenfassungen/", {"patient": self.patient.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(set(r.json()), {"id", "patient", "grund", "termin_datum", "von", "bis", "von_grund", "status",
                                         "entwurf", "fakten", "pruefung", "fehler", "modell", "erstellt_am",
                                         "fertig_am", "angefordert_von_name"})
        self.assertEqual((r.json()["grund"], r.json()["status"]), ("angefordert", "wartet"))
        self.assertEqual(c.post("/api/ki/zusammenfassungen/", {"patient": self.patient.pk},
                                format="json").status_code, 409)
        self.assertEqual(c.post("/api/ki/zusammenfassungen/", {"patient": 999999}, format="json").status_code, 400)
        ev = SystemEreignis.objects.get(art=A.KI, details__aktion="zusammenfassung_angefordert")
        self.assertEqual(ev.details["patient_id"], self.patient.pk)
        zusammenfassung.erstellen(Z.objects.get(), None)
        r = c.get(f"/api/ki/zusammenfassungen/?patient={self.patient.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()[0]["status"], "fertig")
        self.assertEqual(r.json()[0]["von_grund"], "standard")
        self.assertEqual(set(r.json()[0]["pruefung"]), {"unbelegte_werte", "unbekannte_belege", "saetze_ohne_beleg",
                                                        "empfehlung_oder_bewertung", "ok"})
        for _ in range(6):
            Z.objects.create(patient=self.patient, grund="termin", status="fertig")
        self.assertEqual(len(c.get(f"/api/ki/zusammenfassungen/?patient={self.patient.pk}").json()), 5)
        self.assertEqual(c.get("/api/ki/zusammenfassungen/").status_code, 400)

    def test_andere_firma_sieht_nichts(self):
        rg = Firma.objects.get(kuerzel="rg")
        rg_patient = Patient.objects.create(nachname="Klinik", vorname="Karla", geburtsdatum="1970-01-01")
        PatientFirma.objects.filter(patient=rg_patient).update(firma=rg)
        Z.objects.create(patient=rg_patient, grund="termin", firma=rg)
        eigene = Z.objects.create(patient=self.patient, grund="termin")
        nur_rg = benutzer("nurrg", Rolle.KEINE)
        Mitgliedschaft.objects.create(benutzer=nur_rg, firma=rg, rolle=Rolle.MITARBEITER)
        c = echte_anmeldung(nur_rg, mit_zweitem_faktor(nur_rg, 1)[0])
        self.assertEqual(c.get(f"/api/ki/zusammenfassungen/?patient={self.patient.pk}").json(), [])
        self.assertEqual(c.post("/api/ki/zusammenfassungen/", {"patient": self.patient.pk},
                                format="json").status_code, 400)
        self.assertEqual(len(c.get(f"/api/ki/zusammenfassungen/?patient={rg_patient.pk}").json()), 1)
        m = echte_anmeldung(self.mitarbeiter, mit_zweitem_faktor(self.mitarbeiter, 1)[0])
        self.assertEqual(m.get(f"/api/ki/zusammenfassungen/?patient={rg_patient.pk}").json(), [])
        # gemeinsame Akte: die in der RGC angeforderte sieht die DSKM nicht, die nächtliche (ohne Firma) schon
        PatientFirma.objects.create(patient=self.patient, firma=rg)
        Z.objects.create(patient=self.patient, grund="angefordert", firma=rg, status="fertig")
        self.assertEqual([x["id"] for x in m.get(f"/api/ki/zusammenfassungen/?patient={self.patient.pk}").json()],
                         [eigene.pk])
        # Löschen mit dem Patienten (endgültige Löschung, Art. 17 DSGVO)
        Patient.objects.filter(pk=rg_patient.pk).delete()
        self.assertFalse(Z.objects.filter(patient_id=rg_patient.pk).exists())


@override_settings(EPM_KI=Path(KI_TMP))
class DienstTagNachtTest(Grundlage):
    def test_tagsueber_nur_angeforderte_und_nur_wenn_erlaubt(self):
        from ki.management.commands.epm_ki import Dienst

        einst = KiEinstellung.laden()
        nachts = Z.objects.create(patient=self.patient, grund="termin")
        angefordert = Z.objects.create(patient=self.patient, grund="angefordert")
        d = Dienst()
        tag, nacht = Entscheidung("tag", 1, True), Entscheidung("nacht", 1, False)
        einst.zusammenfassung_tagsueber = False
        self.assertIsNone(d._zusammenfassung_holen(tag, einst))
        einst.zusammenfassung_tagsueber = True
        self.assertEqual(d._zusammenfassung_holen(tag, einst).pk, angefordert.pk)
        self.assertIsNone(d._zusammenfassung_holen(tag, einst))
        z = d._zusammenfassung_holen(nacht, einst)
        self.assertEqual((z.pk, z.status), (nachts.pk, "laeuft"))
        # hängende zurück
        Z.objects.filter(pk=z.pk).update(lebenszeichen=timezone.now() - dt.timedelta(minutes=10))
        dienst.haengende_zuruecksetzen()
        self.assertEqual(Z.objects.get(pk=z.pk).status, "wartet")

    def test_chat_vorrang_abschaltbar_und_angefordert_aus_den_einstellungen(self):
        from types import SimpleNamespace

        from ki.management.commands.epm_ki import Dienst

        d = Dienst()
        d.einst = KiEinstellung.laden()
        d.entscheidung, d.chat_aktiv = Entscheidung("tag", 1, True), True
        self.assertEqual(d._abbrechen(SimpleNamespace(prioritaet=10)), "Chat hat tagsüber Vorrang")
        d.einst.chat_vorrang = False
        self.assertIsNone(d._abbrechen(SimpleNamespace(prioritaet=10)))
        d.einst.prio_angefordert = 20
        self.assertEqual(d._abbrechen(SimpleNamespace(prioritaet=10)), "Nachtfenster zu Ende")
        self.assertIsNone(d._abbrechen(SimpleNamespace(prioritaet=20)))

    @mock.patch.dict(os.environ, {"KI_HARDWARE_PRUEFEN": "0"})
    def test_dienst_erstellt_zusammenfassung_und_fuehrt_aufgaben_aus(self):
        from ki.management.commands.epm_ki import Dienst

        KiEinstellung.laden()
        KiEinstellung.objects.filter(pk=1).update(max_cpu_prozent=100, min_ram_frei_mb=256, max_last_je_kern=10)
        KiAufgabe.objects.update(aktiv=False)
        a = KiAufgabe.objects.get(art="zusammenfassung_termine")
        KiAufgabe.objects.filter(pk=a.pk).update(jetzt_angefordert=True)
        termin(self.patient, 1)
        # Steuerung fest auf „nacht“: unter der Last der parallelen CI-Tests meldete die Messung sonst „Pause“;
        # PP-OCR braucht dieser Test nicht (spart Speicher und Zeit)
        nacht = Entscheidung("nacht", 1, False)
        with override_settings(EPM_KI_MODELL_URL=""), \
                mock.patch.object(Dienst, "_entscheiden", return_value=nacht), \
                mock.patch("scans.ocr.paddle.Paddle.laden", side_effect=RuntimeError("im Test nicht nötig")):
            Dienst(einmal=True).laufen()
        z = Z.objects.get()
        self.assertEqual((z.grund, z.status), ("termin", "fertig"))
        a.refresh_from_db()
        self.assertEqual(a.letztes_ergebnis, "1 Zusammenfassung eingereiht")
