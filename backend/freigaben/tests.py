"""Menü „Freigaben“: Datenpflege aus Altdaten-Freitext, Freigabe mit 60 s Rückgängig, Infusionspläne."""
from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer
from infusionen.models import Infusionsplan
from infusionen.tests import PlanHilfen
from patienten.models import Bezugsperson, Patient, PatientArzt
from stammdaten.models import Arzt

from . import datenpflege, dienst
from .models import Datenpflegevorschlag, Freigabe

TELEFON = "015788255675 (Hr. Pohlmann) 0157 8902 6736 (Fr. Pohlmann) 0524242667"
HAUSARZT = "Dr. Klaus Heuwing, Alleestr. 10, 46282 Dorsten / T. 02362-26960 / dorsten@praxis-heuwing.de"


class Erkennung(SimpleTestCase):
    pat = SimpleNamespace(vorname="Klaus", nachname="Pohlmann", geschlecht="m")

    def test_telefon_mit_namen(self):
        eintraege, rest = datenpflege.telefon_zerlegen(TELEFON)
        self.assertEqual(rest, "")
        self.assertEqual([e["nummer"] for e in eintraege], ["015788255675", "0157 8902 6736", "0524242667"])
        self.assertEqual(datenpflege.person_einordnen("Hr. Pohlmann", self.pat), {"eigen": True})
        frau = datenpflege.person_einordnen("Fr. Pohlmann", self.pat)
        self.assertEqual((frau["eigen"], frau["beziehung"], frau["name"], frau["sicher"]),
                         (False, "Ehefrau", "Frau Pohlmann", False))

    def test_beziehung_aus_dem_text(self):
        eintraege, _ = datenpflege.telefon_zerlegen("Tochter Anna 0171 1234567, 05242 4711 (abends)")
        self.assertEqual(eintraege[0]["label"], "Tochter Anna")
        p = datenpflege.person_einordnen("Tochter Anna", self.pat)
        self.assertEqual((p["beziehung"], p["name"], p["sicher"]), ("Tochter", "Anna", True))
        self.assertFalse(datenpflege._ist_person("abends"))
        self.assertTrue(datenpflege.ist_mobil("0171 1234567"))
        self.assertFalse(datenpflege.ist_mobil("05242 4711"))

    def test_zwei_nummern_nur_mit_leerzeichen(self):
        eintraege, _ = datenpflege.telefon_zerlegen("0524 242667 0171 1234567")
        self.assertEqual([e["nummer"] for e in eintraege], ["0524 242667", "0171 1234567"])

    def test_arzt_aus_freitext(self):
        w = datenpflege.arzt_zerlegen(HAUSARZT)
        self.assertEqual({k: w[k] for k in ("name", "strasse", "plz", "ort", "telefon", "email")},
                         {"name": "Dr. Klaus Heuwing", "strasse": "Alleestr. 10", "plz": "46282", "ort": "Dorsten",
                          "telefon": "02362-26960", "email": "dorsten@praxis-heuwing.de"})
        w = datenpflege.arzt_zerlegen("Praxis Dr. Meyer, Hauptstr. 5 33378 Rheda-Wiedenbrück, Tel. 05242 12345, "
                                      "Fax 05242 12346")
        self.assertEqual((w["plz"], w["telefon"], w["fax"]), ("33378", "05242 12345", "05242 12346"))

    def test_hinweise_der_uebernahme(self):
        html = ("<p>frei</p><p><strong>Telefon (vollständig, laut Altsystem):</strong> 0157 1 (Fr. X)</p>"
                "<p><strong>Größe (laut Altsystem):</strong> 2,5 m</p>")
        h = datenpflege.hinweise(html)
        self.assertEqual([(x["feld"], x["inhalt"]) for x in h], [("telefon", "0157 1 (Fr. X)"), ("groesse_cm", "2,5 m")])
        self.assertEqual(datenpflege.hinweis_rest(html), "<p>frei</p>")
        self.assertEqual(datenpflege.groesse_lesen("1,71 m"), "171")
        self.assertEqual(datenpflege.groesse_lesen("171 cm"), "171")
        self.assertIsNone(datenpflege.groesse_lesen("2,5 m"))
        self.assertEqual(datenpflege.email_reparieren("max.muster(at)web,de"), "max.muster@web.de")
        self.assertIsNone(datenpflege.email_reparieren("keine Mail"))

    def test_name_markierung(self):
        for name, marker, sauber in [("Müller +", "+", "Müller"), ("INAKTIV Schulz", "INAKTIV", "Schulz"),
                                     ("Meyer (inaktiv)", "INAKTIV", "Meyer"), ("† Lange", "+", "Lange"),
                                     ("Müller-Lüdenscheidt", "", "Müller-Lüdenscheidt")]:
            p = SimpleNamespace(nachname=name, vorname="Anna")
            self.assertEqual((datenpflege.name_marker(p), datenpflege.name_bereinigen(name)), (marker, sauber), name)


class Ablauf(PlanHilfen, Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.pohlmann = Patient.objects.create(
            nachname="Pohlmann", vorname="Klaus", geschlecht="m", geburtsdatum=timezone.localdate() - timedelta(days=25000),
            telefon="015788255675 (Hr. Pohlmann) 0157 8902 6736 (Fr. …", hausarzt=HAUSARZT[:150],
            bemerkung=f"<p><strong>Telefon (vollständig, laut Altsystem):</strong> {TELEFON}</p>")

    def liste(self, c):
        r = c.get("/api/freigaben/")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def vorschlag(self, c):
        self.assertEqual(c.post("/api/freigaben/suchen/", {}, format="json").status_code, 200)
        return next(v for v in self.liste(c)["datenpflege"] if v["patient"]["id"] == self.pohlmann.id)

    def nach_ablauf(self):
        return dienst.faellige_umsetzen(timezone.now() + timedelta(seconds=61))

    def test_freigabe_mit_rueckgaengig_und_umsetzung(self):
        c = client_fuer(self.mitarbeiter)
        v = self.vorschlag(c)
        arten = [(s["art"], s.get("feld") or s.get("rolle") or s.get("titel")) for s in v["schritte"]]
        self.assertEqual(arten, [("bezugsperson", None), ("feld", "telefon"), ("feld", "telefon2"),
                                 ("hinweis", "Telefon (vollständig, laut Altsystem)"), ("arzt", "hausarzt"),
                                 ("feld", "hausarzt")])
        person = v["schritte"][0]
        self.assertEqual(person["werte"], {"beziehung": "Ehefrau", "name": "Frau Pohlmann", "telefon": "",
                                           "mobil": "0157 8902 6736", "email": ""})
        self.assertEqual(v["schritte"][1]["neu"], "015788255675")
        self.assertEqual(v["schritte"][2]["neu"], "0524242667")
        self.assertEqual(v["schritte"][4]["arzt_wahl"], "neu")

        # freigeben → noch nichts in der Akte; zurücknehmen geht
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertGreater(r.json()["sekunden"], 50)
        self.assertEqual(Bezugsperson.objects.filter(patient=self.pohlmann).count(), 0)
        self.assertEqual(Arzt.objects.count(), 0)
        self.assertEqual(c.post(f"/api/freigaben/{r.json()['id']}/zuruecknehmen/").status_code, 200)
        self.assertEqual(self.nach_ablauf(), 0)
        self.assertEqual(Bezugsperson.objects.filter(patient=self.pohlmann).count(), 0)

        # erneut freigeben (Beziehung korrigiert), nach 60 s umgesetzt
        v = self.liste(c)["datenpflege"][0]
        v["schritte"][0]["werte"]["beziehung"] = "Ehefrau"
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.nach_ablauf(), 1)
        self.assertEqual(Freigabe.objects.get(pk=r.json()["id"]).status, "umgesetzt")
        p = Patient.objects.get(pk=self.pohlmann.pk)
        self.assertEqual((p.telefon, p.telefon2, p.hausarzt, p.bemerkung), ("015788255675", "0524242667", "", ""))
        b = Bezugsperson.objects.get(patient=p)
        self.assertEqual((b.name, b.beziehung.wert, b.mobil, b.angelegt_von), ("Frau Pohlmann", "Ehefrau",
                                                                               "0157 8902 6736", self.mitarbeiter))
        z = PatientArzt.objects.get(patient=p)
        self.assertEqual((z.rolle, z.arzt.name, z.arzt.plz, z.arzt.email),
                         ("hausarzt", "Dr. Klaus Heuwing", "46282", "dorsten@praxis-heuwing.de"))
        self.assertEqual(Datenpflegevorschlag.objects.get(pk=v["id"]).status, "umgesetzt")
        self.assertEqual(self.liste(c)["datenpflege"], [])

        # derselbe Hausarzt bei einer zweiten Akte: Treffer statt Doppel
        zweite = Patient.objects.create(nachname="Beispiel", vorname="Berta", geschlecht="w",
                                        geburtsdatum=timezone.localdate() - timedelta(days=20000),
                                        hausarzt="Dr. med. Klaus Heuwing, Dorsten")
        c.post("/api/freigaben/suchen/", {"patient": zweite.id}, format="json")
        v2 = self.liste(c)["datenpflege"][0]
        self.assertEqual(v2["schritte"][0]["arzt_wahl"], z.arzt_id)
        c.post(f"/api/freigaben/datenpflege/{v2['id']}/freigeben/", {"schritte": v2["schritte"]}, format="json")
        self.nach_ablauf()
        self.assertEqual(Arzt.objects.count(), 1)
        self.assertEqual(PatientArzt.objects.get(patient=zweite).arzt_id, z.arzt_id)

    def test_abhaengigkeit_ohne_bezugsperson_bleibt_telefon(self):
        """Wird die Bezugsperson abgewählt, darf ihre Nummer nicht aus dem Telefonfeld verschwinden."""
        c = client_fuer(self.mitarbeiter)
        v = self.vorschlag(c)
        v["schritte"][0]["an"] = False
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.nach_ablauf()
        self.assertEqual(Freigabe.objects.get(pk=r.json()["id"]).fehler, "")
        p = Patient.objects.get(pk=self.pohlmann.pk)
        self.assertEqual(p.telefon, self.pohlmann.telefon)
        self.assertIn("Telefon (vollständig", p.bemerkung)
        self.assertEqual(p.hausarzt, "")  # Arzt-Schritte unabhängig davon umgesetzt
        self.assertFalse(Bezugsperson.objects.filter(patient=p).exists())

    def test_akte_inzwischen_geaendert(self):
        c = client_fuer(self.mitarbeiter)
        v = self.vorschlag(c)
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        Patient.objects.filter(pk=self.pohlmann.pk).update(telefon="0800 1")
        self.nach_ablauf()
        f = Freigabe.objects.get(pk=r.json()["id"])
        self.assertEqual(f.status, "fehler")
        self.assertIn("inzwischen geändert", f.fehler)
        self.assertFalse(Bezugsperson.objects.filter(patient=self.pohlmann).exists())
        self.assertEqual(Datenpflegevorschlag.objects.get(pk=v["id"]).status, "veraltet")

    def test_rechte(self):
        self.assertEqual(client_fuer(self.betrachter).get("/api/freigaben/").status_code, 403)
        c = client_fuer(self.mitarbeiter)
        v = self.vorschlag(c)
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        # zurücknehmen nur, wer freigegeben hat
        self.assertEqual(client_fuer(self.mediziner).post(f"/api/freigaben/{r.json()['id']}/zuruecknehmen/")
                         .status_code, 403)
        # Admins schreiben nur bei Testpatienten: Freigabe wird gleich abgelehnt
        self.assertEqual(client_fuer(self.admin).post(f"/api/freigaben/datenpflege/{v['id']}/verwerfen/").status_code,
                         200 if self.admin.hat_recht("akten_bearbeiten") else 403)

    def test_infusionsplan_im_menue(self):
        c = client_fuer(self.mediziner)
        e = self.entwurf(c)
        c.patch(f"/api/infusionsplaene/{e['id']}/", self.plan_daten(), format="json")
        daten = self.liste(c)
        self.assertEqual([p["id"] for p in daten["plaene"]], [e["id"]])
        self.assertTrue(daten["plaene"][0]["zeilen"])
        self.assertEqual(client_fuer(self.mitarbeiter).post(f"/api/freigaben/plaene/{e['id']}/freigeben/")
                         .status_code, 403)
        r = c.post(f"/api/freigaben/plaene/{e['id']}/freigeben/")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Infusionsplan.objects.get(pk=e["id"]).status, "entwurf")
        self.assertEqual(self.liste(c)["plaene"], [])  # wartet: nicht doppelt anbieten
        self.nach_ablauf()
        self.assertEqual(Infusionsplan.objects.get(pk=e["id"]).status, "aktuell", Freigabe.objects.get().fehler)


class KiGegenlesen(Grundlage):
    def test_ki_ergaenzt_nur_die_beziehung(self):
        from ki.modell import Antwort

        p = Patient.objects.create(nachname="Kunz", vorname="Otto", geschlecht="m", telefon="05242 1 (Frau Lehmann 0171 5555555)",
                                   geburtsdatum=timezone.localdate() - timedelta(days=25000))
        p.telefon = "05242 123456, Frau Lehmann 0171 5555555"
        p.save()
        v = datenpflege.erstellen(p)
        person = next(s for s in v.schritte if s["art"] == "bezugsperson")
        self.assertEqual((person["werte"]["beziehung"], person["sicher"], v.ki_offen), ("", False, True))

        class Modell:
            def chat(self, *a, **k):
                return Antwort('{"nummern": [{"nummer": "0171 5555555", "eigen": false, "beziehung": "Tochter", '
                               '"name": "Frau Lehmann", "sicher": true}, {"nummer": "x", "eigen": false, '
                               '"beziehung": "Erfunden", "name": "", "sicher": true}]}', 0.1)

        v = datenpflege.ki_pruefen(v, Modell())
        person = next(s for s in v.schritte if s["art"] == "bezugsperson")
        self.assertEqual((person["werte"]["beziehung"], person["werte"]["mobil"], v.verfahren, v.ki_offen),
                         ("Tochter", "0171 5555555", "regeln+ki", False))
        self.assertIn("KI schlägt", person["hinweis"])


class Erweiterungen(Grundlage):
    """Sammelfreigabe, weitere Hinweise, „+“/„INAKTIV“ mit Abschluss, Ärzte zusammenführen, Lernen, Rechte."""

    def neu(self, **felder):
        return Patient.objects.create(geburtsdatum=timezone.localdate() - timedelta(days=25000), **felder)

    def suchen(self, c):
        r = c.post("/api/freigaben/suchen/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def liste(self, c, filter_="alle"):
        r = c.get(f"/api/freigaben/?filter={filter_}")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def von(self, daten, patient):
        return next(v for v in daten["datenpflege"] if v["patient"]["id"] == patient.id)

    def ablauf(self):
        return dienst.faellige_umsetzen(timezone.now() + timedelta(seconds=61))

    def test_sammelfreigabe_nur_eindeutige_mit_gemeinsamem_rueckgaengig(self):
        c = client_fuer(self.mitarbeiter)
        a = self.neu(nachname="Kranz", vorname="Erika", geschlecht="w", telefon="05242 1234567, Tochter Anna 0171 5555555")
        b = self.neu(nachname="Lehr", vorname="Bodo", geschlecht="m", telefon="05242 7654321 (Fr. Lehr)")  # vermutet
        self.suchen(c)
        d = self.liste(c)
        self.assertTrue(self.von(d, a)["eindeutig"])
        self.assertFalse(self.von(d, b)["eindeutig"])
        self.assertEqual(d["zahlen"]["eindeutig"], 1)
        r = c.post("/api/freigaben/datenpflege/sammel/", {}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["anzahl"], r.json()["mit_frage"]), (1, 1))
        # gemeinsam zurücknehmen
        self.assertEqual(c.post(f"/api/freigaben/gruppe/{r.json()['gruppe']}/zuruecknehmen/").status_code, 200)
        self.assertEqual(self.ablauf(), 0)
        r = c.post("/api/freigaben/datenpflege/sammel/", {}, format="json")
        self.ablauf()
        self.assertEqual(Patient.objects.get(pk=a.pk).telefon, "05242 1234567")
        self.assertEqual(Bezugsperson.objects.get(patient=a).beziehung.wert, "Tochter")
        self.assertFalse(Bezugsperson.objects.filter(patient=b).exists())
        # ohne Recht „sammelfreigabe“ nicht
        from accounts.models import Gruppenrecht, Rolle
        Gruppenrecht.objects.create(rolle=Rolle.MITARBEITER, recht="sammelfreigabe", erlaubt=False)
        self.assertEqual(client_fuer(self.mitarbeiter).post("/api/freigaben/datenpflege/sammel/", {}, format="json")
                         .status_code, 403)

    def test_weitere_hinweise_feld_oder_karteikarte(self):
        from patienten.models import Kontakt

        c = client_fuer(self.mitarbeiter)
        p = self.neu(nachname="Voss", vorname="Ute", geschlecht="w", bemerkung=(
            "<p>Alte Bemerkung: mag keine Bananen</p>"
            "<p><strong>Größe (laut Altsystem):</strong> 1,64 m</p>"
            "<p><strong>E-Mail (laut Altsystem, keine gültige Adresse):</strong> ute.voss(at)web,de</p>"
            "<p><strong>Protonenpumpenhemmer (laut Altsystem):</strong> Pantoprazol 40</p>"))
        self.suchen(c)
        v = self.von(self.liste(c), p)
        arten = [(s["art"], s.get("feld") or s.get("titel", "")[:12]) for s in v["schritte"]]
        self.assertIn(("feld", "groesse_cm"), arten)
        self.assertIn(("feld", "email"), arten)
        self.assertEqual(sum(1 for a, _ in arten if a == "kontakt"), 2)  # Protonenpumpenhemmer + Bemerkung
        self.assertFalse(v["eindeutig"])  # Karteikarte und korrigierte E-Mail: bitte prüfen
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.ablauf()
        p.refresh_from_db()
        self.assertEqual((str(p.groesse_cm), p.email, p.bemerkung), ("164.0", "ute.voss@web.de", ""))
        texte = list(Kontakt.objects.filter(patient=p).values_list("text", flat=True))
        self.assertTrue(any("Pantoprazol 40" in t for t in texte) and any("Bananen" in t for t in texte))

    def kontakt(self, p, text, tage):
        from patienten.models import Kontakt

        Kontakt.objects.create(patient=p, text=f"<p>{text}</p>", zeitpunkt=timezone.now() - timedelta(days=tage))

    def test_name_mit_plus_verstorben_aus_kontakt(self):
        c = client_fuer(self.mitarbeiter)
        p = self.neu(nachname="Kunz +", vorname="Otto", geschlecht="m")
        self.kontakt(p, "Ehefrau rief an: Herr Kunz ist am 03.02.2025 verstorben.", 10)
        self.kontakt(p, "Plan besprochen", 40)
        self.suchen(c)
        v = self.von(self.liste(c, "inaktiv"), p)
        name = next(s for s in v["schritte"] if s["art"] == "feld" and s["feld"] == "nachname")
        ab = next(s for s in v["schritte"] if s["art"] == "abschluss")
        self.assertEqual((name["neu"], ab["werte"]["anlass"], ab["werte"]["datum"]), ("Kunz", "verstorben", "2025-02-03"))
        self.assertIn("verstorben", ab["werte"]["notiz"])
        self.assertEqual(len(ab["belege"]), 2)
        self.assertFalse(v["eindeutig"])  # Abschluss wird immer bestätigt
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.ablauf()
        p.refresh_from_db()
        self.assertEqual((p.nachname, p.abschluss_anlass), ("Kunz", "verstorben"))
        self.assertIsNotNone(p.abgeschlossen_am)  # vor dem Anlegen → Datum der Akte, echtes Datum in der Notiz
        self.assertIn("03.02.2025", p.abschluss_notiz)

    def test_inaktiv_ohne_grund_wird_abgefragt(self):
        c = client_fuer(self.mitarbeiter)
        p = self.neu(nachname="INAKTIV Brand", vorname="Eva", geschlecht="w")
        self.kontakt(p, "Rückruf vereinbart", 3)
        self.suchen(c)
        v = self.von(self.liste(c), p)
        ab = next(s for s in v["schritte"] if s["art"] == "abschluss")
        self.assertEqual(ab["werte"]["anlass"], "")
        self.assertIn("kein", ab["frage"])
        r = c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Anlass", str(r.json()))
        # beantwortet → geht; ohne Recht „Akten abschließen“ nicht
        ab["werte"]["anlass"] = "therapie_beendet"
        from accounts.models import Gruppenrecht, Rolle
        Gruppenrecht.objects.create(rolle=Rolle.MITARBEITER, recht="akten_abschliessen", erlaubt=False)
        r = client_fuer(self.mitarbeiter).post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/",
                                               {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 403, r.content)
        Gruppenrecht.objects.all().delete()
        r = client_fuer(self.mitarbeiter).post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/",
                                               {"schritte": v["schritte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.ablauf()
        p.refresh_from_db()
        self.assertEqual((p.nachname, p.abschluss_anlass), ("Brand", "therapie_beendet"))

    def test_aerzte_zusammenfuehren(self):
        c = client_fuer(self.mitarbeiter)
        a1 = Arzt.objects.create(name="Dr. Klaus Heuwing", ort="Dorsten", telefon="02362-26960")
        a2 = Arzt.objects.create(name="Dr. med. Klaus Heuwing", strasse="Alleestr. 10", plz="46282")
        Arzt.objects.create(name="Dr. Anna Andere", telefon="0251 1")
        p1, p2 = self.neu(nachname="A", vorname="A"), self.neu(nachname="B", vorname="B")
        PatientArzt.objects.create(patient=p1, arzt=a1, rolle="hausarzt")
        PatientArzt.objects.create(patient=p2, arzt=a2, rolle="hausarzt")
        PatientArzt.objects.create(patient=p1, arzt=a2, rolle="hausarzt")  # doppelt nach dem Zusammenführen
        self.assertEqual(self.suchen(c)["dubletten"], 1)
        d = self.liste(c)["aerzte"][0]
        self.assertEqual(sorted(a["id"] for a in d["aerzte"]), [a1.id, a2.id])
        self.assertEqual(d["ziel"], a2.id)  # meiste Patienten
        self.assertEqual((d["werte"]["ort"], d["werte"]["telefon"]), ("Dorsten", "02362-26960"))  # Lücken gefüllt
        r = c.post(f"/api/freigaben/aerzte/{d['id']}/freigeben/", {"ziel": a2.id, "werte": d["werte"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.ablauf()
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertFalse(a1.aktiv)
        self.assertEqual((a2.ort, a2.telefon), ("Dorsten", "02362-26960"))
        self.assertEqual(PatientArzt.objects.filter(arzt=a1).count(), 0)
        self.assertEqual(PatientArzt.objects.filter(patient=p1, aktiv=True).count(), 1)
        # Lernen: der alte Name führt künftig zum Ziel
        self.assertEqual([a.id for a in datenpflege.aerzte_treffer({"name": "Dr. Klaus Heuwing"})], [a2.id])
        self.assertEqual(self.suchen(c)["dubletten"], 0)

    def test_lernen_aus_korrekturen(self):
        """Dreimal „Tochter“ statt der vermuteten „Ehefrau“ → beim nächsten Mal „Tochter“ vorgeschlagen."""
        from .models import Lernbeispiel

        c = client_fuer(self.mitarbeiter)
        for i in range(3):
            p = self.neu(nachname=f"Lern{i}", vorname="Hans", geschlecht="m", telefon=f"05242 11111{i} (Fr. Lern{i})")
            self.suchen(c)
            v = self.von(self.liste(c), p)
            person = next(s for s in v["schritte"] if s["art"] == "bezugsperson")
            self.assertEqual(person["werte"]["beziehung"], "Ehefrau")
            person["werte"]["beziehung"] = "Tochter"
            c.post(f"/api/freigaben/datenpflege/{v['id']}/freigeben/", {"schritte": v["schritte"]}, format="json")
            self.ablauf()
        self.assertEqual(Lernbeispiel.objects.filter(art="beziehung", gewaehlt="Tochter").count(), 3)
        p = self.neu(nachname="Lern9", vorname="Hans", geschlecht="m", telefon="05242 222222 (Fr. Lern9)")
        self.suchen(c)
        v = self.von(self.liste(c), p)
        person = next(s for s in v["schritte"] if s["art"] == "bezugsperson")
        self.assertEqual(person["werte"]["beziehung"], "Tochter")
        self.assertIn("gelernt aus 3", person["hinweis"].lower())
        self.assertFalse(person["sicher"])  # erst ab 5 gleichen Entscheidungen eindeutig
        self.assertGreaterEqual(self.liste(c)["lernstand"]["beispiele"], 3)

    def test_rechte_standard_ab_mitarbeiter(self):
        from accounts.rechte import STANDARD
        from accounts.models import Rolle

        for rolle in (Rolle.MITARBEITER, Rolle.MITARBEITER_PLUS, Rolle.MEDIZINER, Rolle.ADMIN):
            self.assertTrue({"datenpflege_freigeben", "sammelfreigabe"} <= STANDARD[rolle], rolle)
        self.assertFalse({"datenpflege_freigeben", "sammelfreigabe"} & STANDARD[Rolle.BETRACHTER])
