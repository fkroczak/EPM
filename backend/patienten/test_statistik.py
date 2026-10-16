"""Statistik (F193): Zählungen, Testpatienten, „< 5“-Regel mit Rundung, Recht, Firmen, CSV, PDF und Audit-Log."""
from datetime import date, datetime, timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from accounts.models import Gruppenrecht, Mitgliedschaft, Rolle
from audit.models import SystemEreignis
from epm.pruefhilfen import Grundlage, benutzer, client_fuer, echte_anmeldung, mit_zweitem_faktor
from stammdaten.models import Auswahlwert, Firma, Versorger

from .models import Kontakt, Patient, PatientFirma
from .statistik import K, gerundet, muss_runden, schuetze, zeitraeume, zelle

JAHR = 2025


def _zeit(tag: date):
    return timezone.make_aware(datetime(tag.year, tag.month, tag.day, 10, 0))


class Zeitraeume(SimpleTestCase):
    def test_jahr_quartal_frei_und_vorzeitraum(self):
        heute = date(2026, 10, 16)
        z, v = zeitraeume({"art": "jahr", "jahr": "2025"}, heute)
        self.assertEqual((z.von, z.bis, v.von, v.bis), (date(2025, 1, 1), date(2025, 12, 31), date(2024, 1, 1),
                                                         date(2024, 12, 31)))
        # laufendes Jahr: Stichtag heute, Vorjahr vollständig
        z, v = zeitraeume({"art": "jahr", "jahr": "2026"}, heute)
        self.assertEqual((z.bis, z.stichtag, z.laufend, v.bis), (heute, heute, True, date(2025, 12, 31)))
        z, v = zeitraeume({"art": "quartal", "jahr": "2026", "quartal": "1"}, heute)
        self.assertEqual((z.von, z.bis, v.von, v.bis), (date(2026, 1, 1), date(2026, 3, 31), date(2025, 10, 1),
                                                         date(2025, 12, 31)))
        z, v = zeitraeume({"art": "frei", "von": "2026-03-01", "bis": "2026-03-10"}, heute)
        self.assertEqual((v.von, v.bis), (date(2026, 2, 19), date(2026, 2, 28)))
        # ohne Jahr bzw. Quartal: das laufende
        z, _ = zeitraeume({"art": "quartal"}, heute)
        self.assertEqual((z.von, z.bis), (date(2026, 10, 1), heute))

    def test_ungueltige_eingaben(self):
        from .statistik import Eingabefehler

        heute = date(2026, 10, 16)
        for params in ({"art": "jahr", "jahr": "2027"}, {"art": "quartal", "jahr": "2026", "quartal": "5"},
                       {"art": "frei", "von": "2026-05-01", "bis": "2026-04-01"}, {"art": "frei", "von": "x"},
                       {"art": "woche"}, {"art": "frei", "von": "2026-11-01", "bis": "2026-12-01"}):
            with self.subTest(params=params), self.assertRaises(Eingabefehler):
                zeitraeume(params, heute)


class Schutzregel(SimpleTestCase):
    """k = 5: 1–4 → „< 5“, 0 bleibt 0; im Bestand dann alles auf volle 5 gerundet (auch Summen und Vorzeitraum)."""

    def roh(self, aktiv=10, versorger=(10,), abgeschlossen=0, kontakte=3):
        return {"kennzahlen": {"aktiv": aktiv, "betreut": aktiv + abgeschlossen, "neuaufnahmen": 0,
                               "abgeschlossen": abgeschlossen, "kontakte": kontakte, "plaene_erstellt": 0,
                               "plaene_freigegeben": 7},
                "verteilungen": {"abschlussanlass": [], "altersgruppen": [],
                                 "katheter": [{"schluessel": "offen", "text": "nicht erfasst", "anzahl": aktiv}],
                                 "versorger": [{"schluessel": f"v{i}", "text": f"V{i}", "anzahl": n}
                                               for i, n in enumerate(versorger)]}}

    def test_zelle(self):
        self.assertEqual(zelle(0)["anzeige"], "0")
        for n in range(1, K):
            self.assertEqual((zelle(n)["wert"], zelle(n)["anzeige"], zelle(n, True)["anzeige"]), (None, "< 5", "< 5"))
        self.assertEqual(zelle(5)["anzeige"], "5")
        self.assertEqual(zelle(1234)["anzeige"], "1.234")
        self.assertEqual([gerundet(n) for n in (5, 6, 7, 8, 12, 13)], [5, 5, 5, 10, 10, 15])
        self.assertEqual(zelle(13, True)["anzeige"], "≈ 15")

    def test_ohne_kleine_zellen_genau(self):
        r = self.roh()
        self.assertFalse(muss_runden(r))
        s = schuetze(r, muss_runden(r))
        self.assertEqual(s["kennzahlen"]["aktiv"]["anzeige"], "10")
        # Kontakte zählen eigenständig: nur „< 5“, keine Rundung des Bestands
        self.assertEqual(s["kennzahlen"]["kontakte"]["anzeige"], "< 5")

    def test_kleine_zelle_rundet_den_bestand(self):
        r = self.roh(aktiv=13, versorger=(10, 3))
        runden = muss_runden(r)
        s = schuetze(r, runden)
        self.assertTrue(runden)
        self.assertEqual(s["kennzahlen"]["aktiv"]["anzeige"], "≈ 15")
        anzeigen = [z["zelle"]["anzeige"] for z in s["verteilungen"]["versorger"]]
        self.assertEqual(anzeigen, ["≈ 10", "< 5"])
        # nicht zurückrechenbar: 15 − 10 ≠ 3 (genauer Wert nirgends)
        self.assertNotIn(13, [s["kennzahlen"]["aktiv"]["wert"]])
        # eigenständige Zählungen bleiben genau
        self.assertEqual(s["kennzahlen"]["plaene_freigegeben"]["anzeige"], "7")

    def test_kleine_zelle_im_vorzeitraum_rundet_beide(self):
        jetzt, vorher = self.roh(aktiv=12), self.roh(aktiv=11, versorger=(9, 2))
        runden = muss_runden(jetzt, vorher)
        self.assertTrue(runden)
        self.assertEqual(schuetze(jetzt, runden)["kennzahlen"]["aktiv"]["anzeige"], "≈ 10")


class Statistik(Grundlage):
    """Ablauf über die API: Akten im Jahr 2025 mit genau gesetzten Daten (``angelegt_am`` = Beginn der Betreuung)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.plus = benutzer("plus", Rolle.MITARBEITER_PLUS)
        cls.dskm, cls.rg = Firma.objects.get(kuerzel="dskm"), Firma.objects.get(kuerzel="rg")
        cls.akten = [cls.akte(f"Statistik{i}", date(1970, 5, 1), date(JAHR, 3, 1)) for i in range(10)]
        # fünf davon im Juni abgeschlossen (Therapie beendet)
        Patient.objects.filter(pk__in=[p.pk for p in cls.akten[:5]]).update(
            abgeschlossen_am=date(JAHR, 6, 1), abschluss_anlass=Patient.Abschlussanlass.THERAPIE_BEENDET)
        # Testpatienten zählen nie – auch nicht mit dem Recht „Testdaten sehen“
        cls.tests = [cls.akte(f"Probe{i}", date(1950, 1, 1), date(JAHR, 2, 1), ist_test=True) for i in range(6)]
        # Kontakte im Jahr: 6 gültige, 1 storniert; davor einer (Vorjahr)
        offen = cls.akten[5]
        for tag in range(6):
            Kontakt.objects.create(patient=offen, text="<p>x</p>", zeitpunkt=_zeit(date(JAHR, 7, 1 + tag)))
        storno = Kontakt.objects.create(patient=offen, text="<p>x</p>", zeitpunkt=_zeit(date(JAHR, 8, 1)))
        storno.stornieren(cls.mitarbeiter, "falsch")
        Kontakt.objects.create(patient=offen, text="<p>x</p>", zeitpunkt=_zeit(date(JAHR - 1, 12, 1)))
        Kontakt.objects.create(patient=cls.tests[0], text="<p>x</p>", zeitpunkt=_zeit(date(JAHR, 7, 1)))

    @classmethod
    def akte(cls, name, geboren, beginn, ist_test=False, **felder):
        p = Patient.objects.create(nachname=name, vorname="Sina", geburtsdatum=geboren, ist_test=ist_test, **felder)
        Patient.objects.filter(pk=p.pk).update(angelegt_am=_zeit(beginn))
        p.refresh_from_db()
        return p

    def statistik(self, client=None, **params):
        c = client or client_fuer(self.mediziner)
        r = c.get("/api/statistik/", {"art": "jahr", "jahr": JAHR, **params})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    @staticmethod
    def anzeige(d, schluessel, vorher=False):
        return d["vorher" if vorher else "werte"]["kennzahlen"][schluessel]["anzeige"]

    @staticmethod
    def verteilung(d, name):
        return {z["schluessel"]: z["zelle"]["anzeige"] for z in d["werte"]["verteilungen"][name]}

    def test_zaehlungen_genau_ohne_kleine_zellen(self):
        d = self.statistik()
        self.assertEqual(d["zeitraum"]["von"], f"{JAHR}-01-01")
        self.assertEqual(d["vergleich"]["titel"], f"Vorjahr {JAHR - 1}")
        self.assertFalse(d["werte"]["gerundet"])
        self.assertEqual([self.anzeige(d, k) for k in ("aktiv", "betreut", "neuaufnahmen", "abgeschlossen", "kontakte")],
                         ["5", "10", "10", "5", "6"])
        self.assertEqual(self.verteilung(d, "abschlussanlass"),
                         {"verstorben": "0", "therapie_beendet": "5", "betreuung_gewechselt": "0"})
        self.assertEqual(self.verteilung(d, "altersgruppen"), {"0-17": "0", "18-39": "0", "40-59": "5", "60-79": "0",
                                                               "80+": "0"})
        self.assertEqual(self.verteilung(d, "versorger"), {"offen": "5"})
        self.assertEqual(self.verteilung(d, "katheter"), {"offen": "5"})
        # Vorjahr: noch niemand in Betreuung; der eine Kontakt von 2024 ist „< 5“
        self.assertEqual(self.anzeige(d, "aktiv", vorher=True), "0")
        self.assertEqual(self.anzeige(d, "kontakte", vorher=True), "< 5")

    def test_testpatienten_zaehlen_nie(self):
        # Admin sieht Testdaten (festes Recht) – in der Statistik zählen sie trotzdem nicht
        d = self.statistik(client_fuer(self.admin))
        self.assertEqual(self.anzeige(d, "neuaufnahmen"), "10")
        self.assertEqual(self.verteilung(d, "altersgruppen")["60-79"], "0")
        self.assertEqual(self.anzeige(d, "kontakte"), "6")

    def test_kleine_zahlen_und_rundung(self):
        versorger = Versorger.objects.create(name="Statistik-Versorger")
        katheter = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.KATHETER).first()
        Patient.objects.filter(pk=self.akten[6].pk).update(versorger=versorger, katheter=katheter)
        Patient.objects.filter(pk=self.akten[7].pk).update(kein_katheter=True)
        d = self.statistik()
        self.assertTrue(d["werte"]["gerundet"])
        self.assertEqual(self.verteilung(d, "versorger"), {f"v{versorger.pk}": "< 5", "offen": "< 5"})
        self.assertEqual(self.verteilung(d, "katheter"), {f"k{katheter.pk}": "< 5", "kein": "< 5", "offen": "< 5"})
        # Bestand gerundet, damit nichts zurückrechenbar ist; eigenständige Zählung (Kontakte) bleibt genau
        self.assertEqual([self.anzeige(d, k) for k in ("aktiv", "betreut", "neuaufnahmen", "abgeschlossen", "kontakte")],
                         ["≈ 5", "≈ 10", "≈ 10", "≈ 5", "6"])
        # kein genauer Wert 1–4 in der Antwort
        for z in d["werte"]["verteilungen"]["katheter"]:
            self.assertIsNone(z["zelle"]["wert"])

    def test_eingeschraenkte_akten_zaehlen_ohne_einzelangaben(self):
        Patient.objects.filter(pk=self.akten[8].pk).update(eingeschraenkt_am=timezone.now(), einschraenkung_grund="Art. 18")
        d = self.statistik()
        self.assertEqual(self.anzeige(d, "aktiv"), "5")
        import json

        text = json.dumps(d, ensure_ascii=False)
        for p in self.akten:
            self.assertNotIn(p.nachname, text)
        for verboten in ('"nummer"', '"name": "Sina', "1970-05-01", '"geburtsdatum"', '"patient'):
            self.assertNotIn(verboten, text)

    def test_altsystem_akte_ist_keine_neuaufnahme(self):
        alt = Patient(nachname="Altfall", vorname="Otto", geburtsdatum=date(1990, 1, 1))
        alt._change_reason = "Aus dem Altsystem übernommen (Stand der letzten Änderung dort)"
        alt.save()
        Patient.objects.filter(pk=alt.pk).update(angelegt_am=_zeit(date(JAHR, 4, 1)))
        d = self.statistik()
        # zählt nicht als Neuaufnahme (10 bleiben 10 – wegen der kleinen Altersgruppe gerundet), aber als aktiv
        # (seit unbekannt in Betreuung) – auch im Vorjahr
        self.assertEqual(self.anzeige(d, "neuaufnahmen"), "≈ 10")
        self.assertEqual(self.verteilung(d, "altersgruppen")["18-39"], "< 5")
        self.assertEqual(self.anzeige(d, "aktiv", vorher=True), "< 5")
        self.assertTrue(any("Altsystem" in h for h in d["hinweise"]))

    def test_infusionsplaene_im_zeitraum(self):
        from infusionen.models import Infusionsplan

        heute = timezone.localdate()
        for p in self.akten[5:10]:
            Infusionsplan.objects.create(patient=p, status=Infusionsplan.Status.ENTWURF, erstellt_von=self.mitarbeiter)
        plaene = [Infusionsplan(patient=p, status=Infusionsplan.Status.ABGELOEST, freigabe_datum=heute,
                                freigegeben_von=self.mediziner, erstellt_von=self.mitarbeiter) for p in self.akten[:6]]
        Infusionsplan.objects.bulk_create(plaene)
        params = {"art": "frei", "von": (heute - timedelta(days=5)).isoformat(), "bis": heute.isoformat()}
        d = self.statistik(**params)
        self.assertEqual((self.anzeige(d, "plaene_erstellt"), self.anzeige(d, "plaene_freigegeben")), ("11", "6"))
        self.assertEqual(self.anzeige(d, "plaene_freigegeben", vorher=True), "0")

    def test_recht(self):
        # Festlegung 16.10.2026: Mitarbeiter (erweitert), Mediziner, Admin ja; Betrachter und Mitarbeiter nein
        for user, erwartet in ((self.betrachter, 403), (self.mitarbeiter, 403), (self.plus, 200), (self.mediziner, 200),
                               (self.admin, 200)):
            with self.subTest(rolle=user.rolle):
                c = client_fuer(user)
                for pfad in ("/api/statistik/", "/api/statistik/csv/", "/api/statistik/pdf/"):
                    if erwartet == 200 and pfad.endswith("pdf/"):
                        continue  # PDF eigener Test (WeasyPrint)
                    self.assertEqual(c.get(pfad, {"jahr": JAHR}).status_code, erwartet, pfad)
                self.assertEqual("statistik_ansehen" in user.rechte, erwartet == 200)
        # Testbenutzer nie (die Statistik zählt echte Akten)
        test_mediziner = benutzer("testmed", Rolle.MEDIZINER, ist_test=True)
        self.assertEqual(client_fuer(test_mediziner).get("/api/statistik/").status_code, 403)
        # je Gruppe umstellbar
        Gruppenrecht.objects.create(rolle=Rolle.MITARBEITER, recht="statistik_ansehen", erlaubt=True)
        self.assertEqual(client_fuer(self.mitarbeiter).get("/api/statistik/", {"jahr": JAHR}).status_code, 200)
        # ohne Recht: kein Audit-Eintrag
        self.assertFalse(SystemEreignis.objects.filter(art=SystemEreignis.Art.EXPORT, details__was="Statistik",
                                                       benutzer=self.betrachter).exists())

    def test_ungueltiger_zeitraum_400(self):
        r = client_fuer(self.mediziner).get("/api/statistik/", {"art": "frei", "von": "2025-05-01", "bis": "2025-04-01"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("vor", r.json()["fehler"])

    def test_firmenfilter(self):
        """Wie Patientenliste und Startseite: nur Akten der aktiven Firma; geteilte Akten in beiden."""
        nur_rg = [self.akte(f"Klinik{i}", date(2000, 1, 1), date(JAHR, 3, 1)) for i in range(6)]
        PatientFirma.objects.filter(patient__in=nur_rg).update(firma=self.rg)
        # fünf Akten betreuen beide Firmen
        for p in self.akten[5:10]:
            PatientFirma.objects.create(patient=p, firma=self.rg)
        beide = benutzer("beide2", Rolle.MEDIZINER)
        Mitgliedschaft.objects.create(benutzer=beide, firma=self.rg, rolle=Rolle.MEDIZINER)
        c = echte_anmeldung(beide, mit_zweitem_faktor(beide, 1)[0])
        d = self.statistik(c)
        self.assertEqual(d["firma"]["kuerzel"], "dskm")
        self.assertEqual(self.anzeige(d, "neuaufnahmen"), "10")
        self.assertEqual(c.post("/api/auth/firma/", {"firma": "rg"}, format="json").status_code, 200)
        d = self.statistik(c)
        self.assertEqual(d["firma"]["kuerzel"], "rg")
        # 6 eigene + 5 geteilte; die übrigen DSKM-Akten nicht
        self.assertEqual(self.anzeige(d, "neuaufnahmen"), "11")
        self.assertEqual(self.anzeige(d, "abgeschlossen"), "0")
        self.assertEqual(self.verteilung(d, "altersgruppen")["18-39"], "6")
        self.assertEqual(self.verteilung(d, "altersgruppen")["40-59"], "5")

    def test_csv_format_und_audit(self):
        c = client_fuer(self.mediziner)
        r = c.get("/api/statistik/csv/", {"art": "jahr", "jahr": JAHR})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn(".csv", r["Content-Disposition"])
        roh = r.content
        self.assertTrue(roh.startswith(b"\xef\xbb\xbf"), roh[:10])
        text = roh.decode("utf-8-sig")
        zeilen = text.split("\r\n")
        self.assertEqual(zeilen[0].split(";")[0], "EPM-Statistik")
        self.assertIn(f"Bereich;Merkmal;{JAHR};Vorjahr {JAHR - 1}", zeilen)
        self.assertIn("Kennzahl;Aktive Patienten zum Stichtag;5;0", zeilen)
        self.assertIn("Kennzahl;Kontakte;6;< 5", zeilen)
        for p in self.akten:
            self.assertNotIn(p.nachname, text)
        self.assertNotIn("1970", text)
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.EXPORT).latest("id")
        self.assertEqual((e.benutzer, e.details["was"], e.details["format"], e.details["von"]),
                         (self.mediziner, "Statistik", "CSV", f"{JAHR}-01-01"))
        self.assertIn(str(JAHR), e.objekt)
        # nur Lesen der Ansicht ist kein Export
        anzahl = SystemEreignis.objects.filter(art=SystemEreignis.Art.EXPORT).count()
        self.statistik()
        self.assertEqual(SystemEreignis.objects.filter(art=SystemEreignis.Art.EXPORT).count(), anzahl)

    def test_pdf_und_audit(self):
        r = client_fuer(self.plus).get("/api/statistik/pdf/", {"art": "quartal", "jahr": JAHR, "quartal": 2})
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.EXPORT).latest("id")
        self.assertEqual((e.benutzer, e.details["was"], e.details["format"]), (self.plus, "Statistik", "PDF"))
        from audit.texte import beschreibung

        self.assertTrue(beschreibung(e).startswith("Statistik als PDF"), beschreibung(e))
