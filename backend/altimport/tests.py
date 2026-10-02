"""Übernahme der Altdaten (F65) gegen die echte Datenbank: Rechte, Dump, Zuordnungen, Probelauf, Import, Dokumente,
Zurücknehmen, Abschließen. Alle Daten sind erfunden (``testdaten/beispiel-dump.sql``)."""
import hashlib
import shutil
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Gruppenrecht, Rolle, User
from audit.models import SystemEreignis
from epm.pruefhilfen import KENNWORT, benutzer, client_fuer, mit_zweitem_faktor
from infusionen.models import Infusionsplan, InfusionsplanPosition
from patienten.models import Dokument, Gewichtsmessung, Kontakt, Loeschprotokoll, Patient
from patienten.testdaten import stammdaten_anlegen, testpatienten_anlegen
from stammdaten.models import Ansprechpartner, Auswahlwert, Praeparat, Versorger

from . import dienst
from .models import Alttabelle, Importlauf, Importobjekt, Importstand
from .pruefdaten import BEISPIEL

TMP = Path(tempfile.mkdtemp(prefix="epm-altimport-"))


def ortszeit(*teile):
    return timezone.make_aware(datetime(*teile))


@override_settings(EPM_DOKUMENTE=TMP / "dokumente", EPM_IMPORT=TMP / "import", EPM_X_ACCEL=True)
class Basis(TestCase):
    """System ohne echte Akten (wie vor dem Go-live): Stammdaten, Benutzer – und „e.beispiel“ gibt es schon."""

    @classmethod
    def setUpTestData(cls):
        stammdaten_anlegen()
        cls.admin = benutzer("admin", Rolle.ADMIN)
        cls.mediziner = benutzer("mediziner", Rolle.MEDIZINER)
        cls.mitarbeiter = benutzer("mitarbeiter", Rolle.MITARBEITER)
        cls.eva = User(username="e.beispiel", first_name="Eva", last_name="Beispiel", rolle=Rolle.MEDIZINER,
                       muss_kennwort_aendern=False)
        cls.eva.set_password(KENNWORT)
        cls.eva.save()

    def setUp(self):
        for ordner in ("dokumente", "import"):
            shutil.rmtree(TMP / ordner, ignore_errors=True)
            (TMP / ordner).mkdir(parents=True)
        self.codes = mit_zweitem_faktor(self.admin, anzahl_codes=12)
        self.a = client_fuer(self.admin)

    # ---- Schritte, die mehrere Tests brauchen
    def lade(self, daten=None, name="beispiel-dump.sql"):
        return self.a.post("/api/altimport/dump/", {"datei": SimpleUploadedFile(name, daten or BEISPIEL.read_bytes())},
                           format="multipart")

    def speichere(self, bereich, aenderungen):
        r = self.a.patch("/api/altimport/zuordnung/", {"bereich": bereich, "aenderungen": aenderungen}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def praeparat(self, kategorie, name):
        return Praeparat.objects.get(kategorie=kategorie, name=name)

    def entscheide(self):
        """Alle offenen Punkte des Beispiel-Dumps entscheiden."""
        self.speichere("werte", {"nickel": {"vielleicht": "unbekannt"}})
        self.speichere("praeparate", {
            "lipide": {"clinoleik 20%": {"art": "praeparat", "id": self.praeparat("lipide", "Clinoleic").id}},
            "medikamente": {"heparin 100 i.e. nach bedarf": {"art": "neu", "name": "Heparin", "konzentration": "",
                                                             "kategorie": "medikament"}}})
        self.speichere("geloeschte", {"4": {"art": "abgeschlossen", "anlass": "therapie_beendet"}})
        return self.speichere("korrekturen", {"patienten:3:geburtsdatum": {"art": "wert", "wert": "21.07.1988"}})

    def importiere(self):
        self.assertEqual(self.lade().status_code, 201)
        self.assertEqual(self.entscheide()["stand"]["offen"], [])
        r = self.a.post("/api/altimport/import/", {"kennwort": KENNWORT, "code": self.codes.pop()}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def akte(self, nummer):
        return Patient.objects.get(nummer=nummer)


class Rechte(Basis):
    def test_nur_admin(self):
        self.assertIn("altdaten_importieren", self.admin.rechte)
        for user in (self.mediziner, self.mitarbeiter):
            with self.subTest(rolle=user.rolle):
                self.assertNotIn("altdaten_importieren", user.rechte)
                c = client_fuer(user)
                self.assertEqual(c.get("/api/altimport/").status_code, 403)
                self.assertEqual(c.get("/api/altimport/zuordnung/").status_code, 403)
                self.assertEqual(c.post("/api/altimport/probelauf/").status_code, 403)
                self.assertEqual(c.post("/api/altimport/dump/", {"datei": SimpleUploadedFile("x.sql", b"x")},
                                        format="multipart").status_code, 403)
        test_admin = benutzer("testadmin", Rolle.ADMIN, ist_test=True)
        self.assertEqual(client_fuer(test_admin).get("/api/altimport/").status_code, 403)

    def test_anderen_rollen_nicht_erteilbar(self):
        r = self.a.put("/api/rechte/", {"matrix": {"mediziner": {"altdaten_importieren": True}}}, format="json")
        self.assertEqual(r.status_code, 400)
        Gruppenrecht.objects.create(rolle=Rolle.MEDIZINER, recht="altdaten_importieren", erlaubt=True)
        self.assertNotIn("altdaten_importieren", self.mediziner.rechte)


class DumpLaden(Basis):
    def test_laden_ersetzen_entfernen(self):
        d = self.a.get("/api/altimport/").json()
        self.assertEqual((d["status"], d["dump"], d["echte_akten"]["anzahl"]), ("leer", None, 0))
        r = self.lade()
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertEqual(d["status"], "geladen")
        self.assertEqual(d["dump"]["name"], "beispiel-dump.sql")
        self.assertEqual(d["dump"]["sha256"], hashlib.sha256(BEISPIEL.read_bytes()).hexdigest())
        self.assertEqual({t["name"]: t["zeilen"] for t in d["tabellen"]},
                         {"benutzerdaten": 4, "versorger": 4, "patienten": 7, "gewichte": 10, "kontakte": 6, "infusionen": 6})
        # Regel 1: Kennwörter stehen nirgends in der Datenbank
        self.assertIn("benutzerdaten.Kennwort", d["dump"]["hinweise"][0])
        alt = Alttabelle.objects.get(name="benutzerdaten")
        self.assertEqual([z[2] for z in alt.zeilen], [None] * 4)
        self.assertNotIn("8402c9af51cd47de57ace27a06061488", str(list(Alttabelle.objects.values_list("zeilen", flat=True))))
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.SYSTEM).first()
        self.assertIn("Dump „beispiel-dump.sql“ geladen (6 Tabellen, 37 Zeilen)", e.details["name"])
        # Zuordnungen bleiben, wenn ein neuer Dump geladen oder der Dump entfernt wird
        self.speichere("werte", {"nickel": {"vielleicht": "unbekannt"}})
        self.assertEqual(self.lade(name="frisch.sql").json()["dump"]["name"], "frisch.sql")
        self.assertEqual(Alttabelle.objects.count(), 6)
        r = self.a.delete("/api/altimport/dump/")
        self.assertEqual((r.status_code, r.json()["status"]), (200, "leer"))
        self.assertEqual(Alttabelle.objects.count(), 0)
        self.assertEqual(Importstand.aktuell().zuordnung, {"werte": {"nickel": {"vielleicht": "unbekannt"}}})
        self.assertEqual(self.a.delete("/api/altimport/dump/").status_code, 409)

    def test_timestamp_spalten_werden_in_ortszeit_umgerechnet(self):
        """mysqldump schreibt TIMESTAMP-Spalten in UTC (SET TIME_ZONE='+00:00'); DATETIME-Spalten bleiben, wie sie sind."""
        daten = BEISPIEL.read_bytes().replace(
            b"CREATE TABLE `kontakte` (", b"CREATE TABLE `kontakte_x` (").replace(b"INSERT INTO `kontakte`", b"INSERT INTO `kontakte_x`")
        daten += ("CREATE TABLE `kontakte` (`ID` int, `PatID` int, `kontakt` text, `lastchange` timestamp NOT NULL, `edit` varchar(50));\n"
                  "INSERT INTO `kontakte` VALUES (1,1,'Anruf kurz nach Mitternacht (erfunden)','2023-06-30 22:30:00','e.beispiel');\n").encode()
        d = self.lade(daten).json()
        self.assertIn("kontakte.lastchange", d["dump"]["hinweise"][-1])
        self.assertIn("1 Zeitpunkte wurden in Ortszeit (Europe/Berlin) umgerechnet", d["dump"]["hinweise"][-1])
        self.assertEqual(Alttabelle.objects.get(name="kontakte").zeilen[0][3], "2023-07-01 00:30:00")
        self.assertEqual(Alttabelle.objects.get(name="gewichte").zeilen[0][3], "2023-01-10 09:00:00")   # DATETIME bleibt
        self.speichere("tabellen_ignoriert", ["kontakte_x"])
        self.assertEqual(self.entscheide()["stand"]["offen"], [])
        r = self.a.post("/api/altimport/import/", {"kennwort": KENNWORT, "code": self.codes.pop()}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Kontakt.objects.get().zeitpunkt, ortszeit(2023, 7, 1, 0, 30))

    def test_unlesbare_dateien(self):
        for daten, erwartet in ((b"kein dump", "keine Tabellen"), (b"\x1f\x8bkaputt", "beschädigt"),
                                (b"CREATE TABLE `t` (`a` int);\nINSERT INTO `t` VALUES ('abc", "nicht geschlossen")):
            r = self.lade(daten)
            self.assertEqual(r.status_code, 400)
            self.assertIn(erwartet, r.json()["datei"])
        self.assertEqual(self.a.post("/api/altimport/dump/", {}, format="multipart").status_code, 400)
        with override_settings(EPM_UPLOAD_MAX_MB=0):
            self.assertIn("größer als 0 MB", self.lade().json()["datei"])
        self.assertEqual(Importstand.aktuell().status, "leer")


class Zuordnungen(Basis):
    def test_vorschlaege_offene_punkte_und_entscheidungen(self):
        self.assertIsNone(self.a.get("/api/altimport/zuordnung/").json()["stand"])
        self.lade()
        d = self.a.get("/api/altimport/zuordnung/").json()
        stand = d["stand"]
        self.assertEqual({o["text"] for o in stand["offen"]}, {
            "Nickelallergie „vielleicht“: Bitte zuordnen.", "Lipide „Clinoleik 20%“: Bitte zuordnen.",
            "Katheterblock / Medikamente „Heparin 100 I.E. nach Bedarf“: Bitte zuordnen.",
            "Es gibt Auffälligkeiten, über die noch entschieden werden muss."})
        self.assertEqual(d["hindernisse"], ["In den Zuordnungen sind noch 4 Punkte offen."])
        # der vorhandene Benutzer wird erkannt, doppelt kodierte Umlaute sind repariert (ftfy)
        benutzer_ = {b["schluessel"]: b["wirksam"] for b in stand["benutzer"]}
        self.assertEqual(benutzer_["e.beispiel"], {"art": "benutzer", "id": self.eva.id})
        self.assertEqual(benutzer_["hans.alt"]["art"], "historisch")
        self.assertEqual({p["bereich"]: p["anzahl"] for p in stand["protokoll"] if p["regel"] == 3},
                         {"kontakte": 1, "patienten": 2})
        # Präparate der Musterdaten werden erkannt
        amino = {z["text"]: z["wirksam"] for z in stand["praeparate"]["amino"]["zeilen"]}
        self.assertEqual(amino["Glamin 13,4%"], {"art": "praeparat", "id": self.praeparat("aminosaeuren", "Glamin").id})
        self.assertIn("Port", [k["wert"] for k in d["bestand"]["katheter"]])
        self.assertEqual(d["auswahl"]["rollen"], ["betrachter", "mitarbeiter", "mediziner", "admin"])
        # Entscheidungen speichern; die Korrektur merkt sich den Wert des Dumps (setzt der Server)
        d = self.entscheide()
        self.assertEqual((d["stand"]["offen"], d["hindernisse"]), ([], []))
        z = Importstand.aktuell().zuordnung
        self.assertEqual(z["korrekturen"], {"patienten:3:geburtsdatum": {"art": "wert", "alt": "0000-00-00", "wert": "21.07.1988"}})
        # Entscheidung zurücknehmen → wieder offen
        d = self.speichere("korrekturen", {"patienten:3:geburtsdatum": None})
        self.assertTrue(any(a["blockiert"] for a in d["stand"]["auffaelligkeiten"]))
        d = self.speichere("werte", {"nickel": {"vielleicht": None}})
        self.assertIn("Nickelallergie „vielleicht“: Bitte zuordnen.", [o["text"] for o in d["stand"]["offen"]])
        # Spalten und Tabellen
        d = self.speichere("spalten", {"patienten": {"hausarzt": ""}})
        self.assertIn("Spalte „barzt“", " ".join(o["text"] for o in d["stand"]["offen"]))
        d = self.speichere("spalten_ignoriert", {"patienten": ["barzt"]})
        self.assertNotIn("barzt", " ".join(o["text"] for o in d["stand"]["offen"]))
        # unbrauchbare Eingaben
        for koerper in ({"bereich": "unsinn", "aenderungen": {}}, {"bereich": "benutzer", "aenderungen": []},
                        {"bereich": "korrekturen", "aenderungen": {"patienten:1:name": {"art": "wert", "wert": "x"}}},
                        {"bereich": "korrekturen", "aenderungen": {"patienten:3:geburtsdatum": {"art": "loeschen"}}},
                        {"bereich": "tabellen_ignoriert", "aenderungen": {"a": 1}}):
            self.assertEqual(self.a.patch("/api/altimport/zuordnung/", koerper, format="json").status_code, 409, koerper)


class Probelauf(Basis):
    def test_probelauf_schreibt_nichts(self):
        self.lade()
        r = self.a.post("/api/altimport/probelauf/").json()
        self.assertFalse(r["erfolgreich"])
        self.assertIn("noch 4 Punkte offen", r["fehler"])
        self.entscheide()
        vorher = (User.objects.count(), Versorger.objects.count(), Praeparat.objects.count(), Auswahlwert.objects.count(),
                  SystemEreignis.objects.count())
        r = self.a.post("/api/altimport/probelauf/").json()
        self.assertTrue(r["erfolgreich"], r["fehler"])
        self.assertEqual(r["zahlen"]["geschrieben"], {
            "benutzer": 4, "versorger": 2, "ansprechpartner": 2, "auswahlwerte": 4, "praeparate": 1, "patienten": 6,
            "abgeschlossen": 1, "gewichte": 6, "kontakte": 4, "plaene": 5, "vitamine": 4, "positionen": 1})
        self.assertEqual(r["zahlen"]["patienten"], {"alt": 7, "neu": 6, "abgeschlossen": 1, "nicht": {"geloescht": 1}})
        self.assertTrue(any(p["regel"] == 5 and p["anzahl"] == 2 for p in r["protokoll"]))
        # nichts geschrieben
        self.assertEqual(Patient.objects.count(), 0)
        self.assertEqual(Patient.history.count(), 0)
        self.assertEqual((User.objects.count(), Versorger.objects.count(), Praeparat.objects.count(), Auswahlwert.objects.count(),
                          SystemEreignis.objects.count()), vorher)
        self.assertEqual(Importobjekt.objects.count(), 0)
        self.assertEqual(Importstand.aktuell().status, "geladen")
        self.assertEqual([x.art for x in Importlauf.objects.all()], ["probelauf", "probelauf"])
        # der Lauf ist als Text abrufbar – ohne Namen
        text = self.a.get(f"/api/altimport/laeufe/{r['id']}/text/")
        inhalt = text.content.decode()
        self.assertIn("attachment", text["Content-Disposition"])
        self.assertIn("Patienten: 7 im Altsystem, 6 übernommen (nicht übernommen: 1 im Altsystem gelöscht)", inhalt)
        self.assertIn("Regel 5: 2 × Unplausibles Gewicht", inhalt)
        for name in ("Musterfrau", "Müller", "Erika"):
            self.assertNotIn(name, inhalt)
        self.assertEqual(self.a.get(f"/api/altimport/laeufe/{r['id']}/").json()["protokoll"], r["protokoll"])
        self.assertEqual(self.a.get("/api/altimport/laeufe/999999/").status_code, 404)

    def test_echte_akte_verhindert_die_uebernahme(self):
        Patient.objects.create(nachname="Echt", vorname="Anna", geburtsdatum=date(1970, 1, 1))
        testpatienten_anlegen()   # Testpatienten stören nicht
        self.lade()
        self.entscheide()
        d = self.a.get("/api/altimport/zuordnung/").json()
        self.assertEqual(len(d["hindernisse"]), 1)
        self.assertIn("1 echte Akten (Nr. 1)", d["hindernisse"][0])
        self.assertFalse(self.a.post("/api/altimport/probelauf/").json()["erfolgreich"])
        r = self.a.post("/api/altimport/import/", {"kennwort": KENNWORT, "code": self.codes.pop()}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ohne echte Akten", r.json()["fehler"])

    def test_nummer_aus_dem_loeschprotokoll(self):
        Loeschprotokoll.objects.create(akte_id=77, nummer=5, angelegt_am=timezone.now(), rechtsgrund="frist", grund="Test")
        self.lade()
        self.entscheide()
        self.assertIn("Löschprotokoll", self.a.get("/api/altimport/zuordnung/").json()["hindernisse"][0])


class Import(Basis):
    def test_bestaetigung_mit_kennwort_und_code(self):
        self.lade()
        self.entscheide()
        r = self.a.post("/api/altimport/import/", {"kennwort": "falsch", "code": self.codes[0]}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["kennwort"]))
        r = self.a.post("/api/altimport/import/", {"kennwort": KENNWORT, "code": "000000"}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["code"]))
        self.assertEqual(Patient.objects.count(), 0)
        self.assertEqual(Importstand.aktuell().status, "geladen")

    def test_import(self):
        lauf = self.importiere()
        self.assertTrue(lauf["erfolgreich"])
        stand = self.a.get("/api/altimport/").json()
        self.assertEqual((stand["status"], stand["importiert_von"]), ("importiert", self.admin.anzeigename))
        self.assertEqual(stand["uebernommen"], {"patienten": 6, "gewichte": 6, "kontakte": 4, "plaene": 5, "dokumente": 0})
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.SYSTEM).first()
        self.assertEqual(e.details["name"], "Altdaten übernommen: 6 Akten (1 abgeschlossen), 6 Gewichte, 4 Kontakte, 5 Infusionspläne")
        self.assertEqual(e.benutzer, self.admin)

        # ---- Akten (Regeln 3, 4, 6, 9, 10, 11, 15)
        self.assertEqual(sorted(Patient.objects.values_list("nummer", flat=True)), [1, 2, 3, 4, 5, 7])
        erika, max_, paula, jonas, hanna = (self.akte(n) for n in (1, 2, 3, 4, 5))
        self.assertFalse(erika.ist_test)
        self.assertEqual((max_.nachname, max_.strasse, max_.plz), ("Müller", "Beispielstraße 5", "4109"))
        self.assertEqual((max_.groesse_cm, paula.groesse_cm), (Decimal("181.0"), None))
        self.assertIsNone(max_.versorger)
        self.assertEqual((erika.versorger.name, erika.ansprechpartner.name, erika.ansprechpartner.telefon),
                         ("Homecare Nord (erfunden)", "Frau Probe", "0000 111111"))
        self.assertEqual((erika.katheter.wert, hanna.katheter, hanna.kein_katheter, paula.katheter.wert),
                         ("Portkatheter", None, True, "ZVK"))
        self.assertEqual(sorted(Auswahlwert.objects.filter(liste="katheter").order_by("-reihenfolge").values_list("wert", flat=True)[:4]),
                         ["Broviac 2-lumig", "Portkatheter", "Power PICC", "ZVK"])   # neu, ans Ende der Auswahlliste
        self.assertEqual([p.nickelallergie for p in (erika, max_, paula, hanna)], ["nein", "unbekannt", "unbekannt", "ja"])
        self.assertEqual(paula.geburtsdatum, date(1988, 7, 21))
        self.assertEqual(erika.diagnose, "<p>Kurzdarmsyndrom nach Resektion (erfunden).</p><p>Restdarm ca. 80 cm.<br>Colon in Kontinuität.</p>")
        self.assertIn("<p>Verlauf:</p><ul><li>02.01.2021 Beginn</li></ul>", erika.therapie)
        self.assertNotIn("script", erika.therapie)
        self.assertNotIn("alert", erika.therapie)
        self.assertEqual(hanna.email, "")
        self.assertIn("hanna(at)example", hanna.bemerkung)
        self.assertEqual(len(max_.ueberweisung_durch), 200)
        self.assertIn("Station 4", max_.bemerkung)
        self.assertEqual((erika.hausarzt, erika.ueberweisung_durch), ("Dr. Hausmann (erfunden)", "Hausarzt"))
        # gelöschter Patient als abgeschlossene Akte – mit seinen Einträgen
        self.assertEqual((jonas.abgeschlossen_am, jonas.abschluss_anlass), (date(2020, 1, 15), "therapie_beendet"))
        self.assertEqual(jonas.abschluss_notiz, "Im Altsystem als gelöscht markiert am 15.01.2020.")
        self.assertEqual((jonas.kontakte.count(), jonas.gewichte.count(), jonas.infusionsplaene.count()), (1, 1, 1))
        self.assertFalse(Patient.objects.filter(nummer=6).exists())
        # Historie: eine Fassung je Akte mit Bearbeiter und Zeitpunkt des Altsystems
        h = erika.history.get()
        self.assertEqual((h.history_type, h.history_user, h.history_date), ("+", self.eva, ortszeit(2023, 5, 2, 10, 11, 12)))
        self.assertEqual(h.history_change_reason, "Aus dem Altsystem übernommen (Stand der letzten Änderung dort)")
        self.assertEqual(max_.history.get().history_user.username, "hans.alt")
        self.assertEqual(Patient.history.count(), 6)

        # ---- Benutzer (Regeln 1, 8)
        konto, historisch = User.objects.get(username="a.muster"), User.objects.get(username="hans.alt")
        self.assertEqual((konto.rolle, konto.is_active, konto.has_usable_password(), konto.nur_historisch),
                         ("mitarbeiter", True, False, False))
        self.assertEqual((historisch.nur_historisch, historisch.is_active, historisch.anzeigename), (True, False, "H. Alt"))
        self.assertEqual(User.objects.get(username="verwaltung").rolle, "admin")
        angelegt = SystemEreignis.objects.filter(art=SystemEreignis.Art.BENUTZER_ANGELEGT, objekt="a.muster").get()
        self.assertEqual(angelegt.details["quelle"], "altdaten")
        protokoll = self.a.get("/api/protokoll/?gruppe=benutzer").json()["results"]
        self.assertIn("Benutzer a.muster bei der Übernahme der Altdaten angelegt (Mitarbeiter), noch ohne Kennwort",
                      [x["beschreibung"] for x in protokoll])
        self.assertFalse(SystemEreignis.objects.filter(art=SystemEreignis.Art.BENUTZER_ANGELEGT, objekt="hans.alt").exists())

        # ---- Stammdaten: nur was gebraucht wird; Versorger mit Historie
        self.assertEqual(sorted(Versorger.objects.values_list("name", flat=True)),
                         ["Apotheke Süd (erfunden)", "Homecare Nord (erfunden)"])
        apotheke = Versorger.objects.get(name="Apotheke Süd (erfunden)")
        self.assertEqual((apotheke.telefon, apotheke.email, apotheke.notiz), ("0000 333333", "", "E-Mail laut Altsystem: keine-adresse."))
        self.assertEqual(apotheke.history.get().history_user, self.admin)
        self.assertEqual(Ansprechpartner.objects.count(), 2)
        self.assertTrue(Auswahlwert.objects.filter(liste="katheter", wert="Power PICC").exists())
        self.assertTrue(Praeparat.objects.filter(kategorie="medikament", name="Heparin").exists())

        # ---- Gewichte (Regeln 2, 4, 5)
        gewichte = list(erika.gewichte.order_by("gemessen_am"))
        self.assertEqual([(g.gewicht_kg, g.gemessen_am) for g in gewichte],
                         [(Decimal("64.5"), date(2023, 1, 10)), (Decimal("640.0"), date(2023, 4, 10)), (Decimal("63.8"), date(2023, 5, 10))])
        g = gewichte[0]
        self.assertEqual((g.datum_ungenau, g.quelle, g.erfasst_von, g.erfasst_am),
                         (True, "altsystem", self.eva, ortszeit(2023, 1, 10, 9, 0)))
        gh = g.history.get()
        self.assertEqual((gh.history_user, gh.history_date, gh.erfasst_am, gh.history_change_reason),
                         (self.eva, g.erfasst_am, g.erfasst_am, "Aus dem Altsystem übernommen"))
        self.assertIsNone(gewichte[2].erfasst_von)
        self.assertEqual(max_.gewichte.get().gewicht_kg, Decimal("78.3"))
        self.assertEqual(Gewichtsmessung.objects.count(), 6)

        # ---- Kontakte: Zeitpunkt und Bearbeiter des Altsystems; danach unveränderlich wie jeder Kontakt
        k = erika.kontakte.order_by("zeitpunkt").first()
        self.assertEqual((k.zeitpunkt, k.erfasst_am, k.erfasst_von, k.art), (ortszeit(2023, 1, 10, 9, 5),) * 2 + (self.eva, None))
        self.assertEqual(k.text, "<p>Telefonat: Befinden stabil, Infusion läuft ohne Probleme.<br>Rückruf in 4 Wochen.</p>")
        self.assertEqual(max_.kontakte.get().text, "<p>Rückfrage zur Laufzeit, Mutter sagt: 'alles gut' \\ Ende</p>")
        self.assertEqual(k.history.get().history_date, k.zeitpunkt)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Kontakt.objects.filter(pk=k.pk).update(text="geändert")

        # ---- Infusionspläne (Regeln 7, 13, 14, 16)
        alt, aktuell = erika.infusionsplaene.order_by("gueltig_ab")
        self.assertEqual((alt.status, aktuell.status, aktuell.vorgaenger, alt.vorgaenger), ("abgeloest", "aktuell", alt, None))
        self.assertEqual((alt.herkunft, alt.gueltig_ab, alt.erstellt_am, alt.erstellt_von),
                         ("altsystem", date(2021, 1, 2), ortszeit(2021, 1, 2, 10, 0), self.eva))
        self.assertEqual((alt.basis_praeparat.name, alt.basis_ml, alt.glucose_g, alt.glucose_praeparat), ("Sterofundin", 500, Decimal("150.0"), None))
        self.assertEqual((alt.aminosaeuren_praeparat.name, alt.lipide_praeparat.name, alt.spurenelemente.name, alt.katheterschutz.name),
                         ("Glamin", "Clinoleic", "Addel N", "Taurolin"))
        self.assertEqual(sorted(alt.vitamine.values_list("name", flat=True)), ["Soluvit N", "Vitalipid adult"])
        self.assertEqual((alt.kcal_manuell, alt.kcal, alt.pantozol_stufe, alt.pantozol_tage, alt.laufzeit_h), (None, 1115, 1, 5, Decimal("12.0")))
        self.assertEqual((alt.gesamtvolumen_ml, alt.volumen_gewicht_kg, alt.albumin_ml), (Decimal("2257.50"), None, None))
        self.assertEqual((alt.freigegeben_am, alt.freigegeben_von, alt.pdf_datei), (None, None, ""))
        self.assertEqual(alt.freigabevermerk, "Aus dem Altsystem übernommen; dort angelegt am 02.01.2021 von E. Beispiel.")
        self.assertEqual(aktuell.lipide_praeparat.name, "Clinoleic")                        # Schreibvariante zugeordnet
        self.assertEqual([(p.praeparat.name, p.bemerkung) for p in aktuell.positionen.all()], [("Heparin", "Heparin 100 I.E. nach Bedarf")])
        self.assertIn("Energie (laut Altsystem):</strong> 433.564 kcal", aktuell.bemerkung)
        self.assertIn("Laufrate (laut Altsystem):</strong> 180.0 ml/h", aktuell.bemerkung)
        self.assertEqual((aktuell.kcal_manuell, aktuell.albumin_ml, aktuell.albumin_praeparat.name), (None, Decimal("20.0"), "Humanalbumin"))
        plan_max = max_.infusionsplaene.get()
        self.assertEqual((plan_max.kcal_manuell, plan_max.pantozol_stufe, plan_max.glucose_g), (1500, 0, Decimal("9000.0")))
        self.assertIn("Protonenpumpenhemmer (laut Altsystem):</strong> 7", plan_max.bemerkung)
        self.assertEqual(Infusionsplan.objects.filter(status="aktuell").count(), 4)
        # Historie der Pläne mit ihren Vitaminen
        ph = alt.history.get()
        self.assertEqual((ph.history_user, ph.history_date, ph.history_type), (self.eva, ortszeit(2021, 1, 2, 10, 30), "+"))
        self.assertEqual(sorted(v.praeparat.name for v in ph.vitamine.all()), ["Soluvit N", "Vitalipid adult"])
        self.assertEqual(InfusionsplanPosition.history.count(), 1)
        # übernommene Pläne bleiben unveränderlich
        with self.assertRaises(PermissionError):
            aktuell.bemerkung = "x"
            aktuell.save()

        # ---- danach gesperrt: Zuordnungen, neuer Dump, zweiter Import
        self.assertEqual(self.a.patch("/api/altimport/zuordnung/", {"bereich": "werte", "aenderungen": {}}, format="json").status_code, 409)
        self.assertEqual(self.lade().status_code, 409)
        r = self.a.post("/api/altimport/import/", {"kennwort": KENNWORT, "code": self.codes.pop()}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertIsNone(self.a.get("/api/altimport/zuordnung/").json()["stand"])
        self.assertEqual(self.a.post("/api/altimport/probelauf/").json()["fehler"],
                         "Die Altdaten sind bereits übernommen. Für einen neuen Lauf den Import zuerst zurücknehmen.")

    def test_uebernommene_akten_im_alltag(self):
        """Die Akten verhalten sich wie jede andere: lesen, Verlauf, neuer Plan auf Grundlage des übernommenen."""
        self.importiere()
        erika = self.akte(1)
        m = client_fuer(self.mediziner)
        d = m.get(f"/api/patienten/{erika.id}/").json()
        self.assertEqual((d["nummer"], d["kopf"]["katheter"], d["kopf"]["versorger"]), (1, "Portkatheter", "Homecare Nord (erfunden)"))
        self.assertEqual(d["kopf"]["aktueller_plan"]["gueltig_ab"], "2022-06-01")
        verlauf = m.get(f"/api/patienten/{erika.id}/verlauf/").json()
        akte = next(v for v in verlauf if v["bereich"] == "stammdaten")
        self.assertEqual((akte["person"], akte["grund"]), (self.eva.anzeigename, "Aus dem Altsystem übernommen (Stand der letzten Änderung dort)"))
        plaene = m.get(f"/api/infusionsplaene/?patient={erika.id}").json()["results"]
        self.assertEqual({p["herkunft"] for p in plaene}, {"altsystem"})
        self.assertTrue(all(p["freigabevermerk"].startswith("Aus dem Altsystem übernommen") for p in plaene))
        self.assertEqual(m.get(f"/api/infusionsplaene/{plaene[0]['id']}/pdf/").status_code, 404)
        self.assertEqual(m.get(f"/api/infusionsplaene/{plaene[0]['id']}/ansicht/").status_code, 200)
        uebersicht = m.get("/api/infusionsplaene/uebersicht/?gruppe=aktuell").json()
        self.assertEqual({z["herkunft"] for z in uebersicht["ergebnisse"]}, {"altsystem"})
        # neuer Plan: mit dem übernommenen vorbelegt, bei Freigabe wird der übernommene abgelöst – ohne Scheinänderungen
        alt = erika.infusionsplaene.get(status="aktuell")
        entwurf = Infusionsplan.neuer_entwurf(erika, self.mediziner)
        self.assertEqual((entwurf.vorgaenger, entwurf.lipide_g, entwurf.herkunft), (alt, alt.lipide_g, "epm"))
        self.assertEqual(sorted(entwurf.vitamine.values_list("name", flat=True)), ["Cernevit"])
        self.assertEqual(entwurf.positionen.get().praeparat.name, "Heparin")
        entwurf.glucose_praeparat = self.praeparat("glucose", "Glucose")
        entwurf._history_user = self.mediziner
        entwurf.save()
        entwurf.freigeben(self.mediziner)
        alt.refresh_from_db()
        self.assertEqual(alt.status, "abgeloest")
        from patienten.api import verlauf_eintraege

        abgeloest = next(v for v in verlauf_eintraege(erika, bereich="infusionsplaene")
                         if v["objekt_id"] == alt.id and v["art"] == "geändert")
        self.assertEqual([a["feld"] for a in abgeloest["aenderungen"]], ["status"])
        # abgeschlossene übernommene Akte: gesperrt wie jede abgeschlossene Akte
        jonas = self.akte(4)
        r = client_fuer(self.mitarbeiter).post("/api/kontakte/", {"patient": jonas.id, "text": "<p>x</p>"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(jonas.aufbewahrung()["beginn"], date(2020, 1, 15))


class Dokumente(Basis):
    def lege(self, pfad, inhalt):
        ziel = TMP / "import" / "PatData" / pfad
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(inhalt)
        return ziel

    def dateien(self):
        import os

        from PIL import Image

        self.lege("1/arztbrief 2020.pdf", b"%PDF-1.4\n1 0 obj\n<< /Title (x) /CreationDate (D:20200304120000+01'00') >>\nendobj\n%%EOF\n")
        alt = self.lege("1/notiz.txt", "Notiz aus dem Altsystem (erfunden)\n".encode())
        os.utime(alt, (1546340400, 1546340400))   # 01.01.2019 12:00 Ortszeit
        self.lege("1/befunde/labor.pdf", b"%PDF-1.4\nohne Datum\n%%EOF\n")
        exif = Image.Exif()
        exif[306] = "2019:08:07 10:00:00"
        bild = TMP / "import" / "PatData" / "2" / "foto.jpg"
        bild.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (4, 4), "white").save(bild, exif=exif)
        self.lege("1/skript.php", b"<?php echo 1; ?>")
        self.lege("1/leer.txt", b"")
        self.lege("1/tabelle.xlsx", b"PK\x03\x04\x00\x00binaer\x00")
        self.lege("6/nicht-uebernommen.txt", b"Patient 6 wurde nicht uebernommen")
        self.lege("99/fremd.txt", b"kein Patient")
        self.lege("lose.txt", b"liegt nicht in einem Ordner")

    def test_dokumente_in_etappen(self):
        self.assertEqual(self.a.get("/api/altimport/dokumente/").json()["vorhanden"], False)
        self.dateien()
        self.assertEqual(self.a.post("/api/altimport/dokumente/").status_code, 409)   # erst nach dem Import
        self.importiere()
        d = self.a.get("/api/altimport/dokumente/").json()
        self.assertEqual((d["vorhanden"], d["ordner"], d["offen"], d["erledigt"]), (True, 4, 4, 0))
        self.assertEqual(sorted((x["ordner"], x["dateien"]) for x in d["ohne_patient"]), [("6", 1), ("99", 1)])
        self.assertEqual(sorted((x["pfad"], x["grund"]) for x in d["nicht_uebernommen"]), [
            ("1/leer.txt", "leere Datei"), ("1/skript.php", "Dateityp war schon im Altsystem nicht zugelassen"),
            ("1/tabelle.xlsx", "Dateityp wird vom EPM nicht angenommen (PDF, Bilder und Text)"),
            ("lose.txt", "liegt nicht in einem Patientenordner")])
        # erste Etappe: zwei Dateien, zweite: der Rest; jede Datei genau einmal
        r = dienst.dokumente_uebernehmen(self.admin, max_dateien=2)
        self.assertEqual((r["uebernommen"], r["offen"], r["fertig"]), (2, 2, False))
        r = self.a.post("/api/altimport/dokumente/").json()
        self.assertEqual((r["uebernommen"], r["offen"], r["erledigt"], r["fertig"]), (2, 0, 4, True))
        self.assertEqual(self.a.post("/api/altimport/dokumente/").json()["uebernommen"], 0)
        erika = self.akte(1)
        dokumente = {d.originalname: d for d in erika.dokumente.all()}
        self.assertEqual(sorted(dokumente), ["arztbrief 2020.pdf", "labor.pdf", "notiz.txt"])
        brief, notiz, labor = dokumente["arztbrief 2020.pdf"], dokumente["notiz.txt"], dokumente["labor.pdf"]
        self.assertEqual((brief.titel, brief.mime, brief.datum, brief.datum_quelle), ("arztbrief 2020", "application/pdf", date(2020, 3, 4), "pdf"))
        self.assertEqual((notiz.datum, notiz.datum_quelle, notiz.mime), (date(2019, 1, 1), "dateidatum", "text/plain; charset=utf-8"))
        self.assertEqual((labor.titel, labor.datum_quelle), ("befunde/labor", "dateidatum"))
        self.assertEqual((brief.herkunft, brief.typ.wert, brief.typ_geprueft, brief.hochgeladen_von), ("altsystem", "Sonstiges", False, None))
        self.assertEqual(brief.sha256, hashlib.sha256(brief.pfad.read_bytes()).hexdigest())
        self.assertTrue(brief.datei.startswith("1/") and brief.datei.endswith(".pdf"))
        self.assertEqual(brief.history.get().history_change_reason, "Aus dem Altsystem übernommen")
        foto = self.akte(2).dokumente.get()
        self.assertEqual((foto.mime, foto.datum, foto.datum_quelle), ("image/jpeg", date(2019, 8, 7), "exif"))
        # die Quelle bleibt unberührt; die Akte liefert die Datei aus
        self.assertTrue((TMP / "import" / "PatData" / "1" / "notiz.txt").exists())
        r = client_fuer(self.mediziner).get(f"/api/dokumente/{notiz.id}/datei/")
        self.assertEqual(r["X-Accel-Redirect"], "/_geschuetzt/dokumente/" + notiz.datei)
        # „Nach und nach prüfen“ zeigt die Altdokumente
        lauf = Importlauf.objects.filter(art="dokumente").get()
        self.assertEqual((lauf.erfolgreich, lauf.zahlen["dateien"], lauf.zahlen["nicht_uebernommen"]), (True, 4, 4))
        self.assertEqual(self.a.get("/api/altimport/").json()["uebernommen"]["dokumente"], 4)
        # ein endgültig gelöschtes Dokument kommt mit der nächsten Etappe nicht wieder
        self.assertEqual(Importobjekt.objects.filter(art="datei").count(), 4)
        self.lege("1/neu.txt", b"spaeter dazugelegt")
        self.assertEqual(self.a.post("/api/altimport/dokumente/").json()["uebernommen"], 1)


    def test_ordner_traegt_die_nummer_des_altsystems(self):
        """Eine bei der Übernahme korrigierte Patientennummer ändert nichts am Dokumentenordner: Er heißt wie im Altsystem."""
        self.assertEqual(self.lade(BEISPIEL.read_bytes().replace(b"(1,'Musterfrau'", b"(9500,'Musterfrau'")).status_code, 201)
        self.entscheide()
        # die Nummer eines anderen Patienten des Altsystems (auch eines gelöschten) ist nicht wählbar
        stand = self.speichere("korrekturen", {"patienten:9500:nummer": {"art": "wert", "wert": "6"}})["stand"]
        self.assertTrue(any(o["bereich"] == "auffaelligkeiten" for o in stand["offen"]))
        r = self.a.post("/api/altimport/import/", {"kennwort": KENNWORT, "code": self.codes.pop()}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.speichere("korrekturen", {"patienten:9500:nummer": {"art": "wert", "wert": "8"}})["stand"]["offen"], [])
        r = self.a.post("/api/altimport/import/", {"kennwort": KENNWORT, "code": self.codes.pop()}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.akte(8).nachname, "Musterfrau")
        self.lege("9500/brief.txt", b"gehoert zu Musterfrau")
        self.lege("8/fremd.txt", b"im Altsystem gab es keinen Patienten 8")
        self.lege("0002/alt.txt", b"Ordner mit fuehrenden Nullen")
        d = self.a.get("/api/altimport/dokumente/").json()
        self.assertEqual((d["offen"], [x["ordner"] for x in d["ohne_patient"]]), (2, ["8"]))
        self.assertEqual(self.a.post("/api/altimport/dokumente/").json()["uebernommen"], 2)
        brief = self.akte(8).dokumente.get()
        self.assertEqual(brief.originalname, "brief.txt")
        self.assertTrue(brief.datei.startswith("8/") and brief.pfad.exists())
        self.assertEqual(self.akte(2).dokumente.get().originalname, "alt.txt")

    def test_unlesbares_verknuepfungen_und_dateinamen(self):
        import os

        self.importiere()
        wurzel = TMP / "import" / "PatData"
        self.lege("1/MÃ¼ller Brief.txt", b"doppelt kodierter Dateiname")
        with open(os.path.join(os.fsencode(wurzel / "1"), b"Gr\xf6\xdfe.txt"), "wb") as f:   # Name in Latin-1, kein UTF-8
            f.write(b"alte Kodierung")
        self.lege("2/geheim/befund.txt", b"nicht lesbar")
        self.lege("2/lesbar.txt", b"lesbar")
        os.symlink(wurzel / "1", wurzel / "2" / "verweis")
        os.symlink(wurzel / "1", wurzel / "77")
        (wurzel / "²").mkdir()                                  # „Ziffer“, aber keine Zahl
        root = os.geteuid() == 0                                 # root liest alles – dann entfällt die Rechteprüfung
        os.chmod(wurzel / "2" / "geheim", 0)
        try:
            d = self.a.get("/api/altimport/dokumente/").json()
            nicht = {(x["pfad"], x["grund"]) for x in d["nicht_uebernommen"]}
            self.assertIn(("2/verweis", "Verknüpfung auf einen Ordner – wird nicht verfolgt"), nicht)
            self.assertIn(("77", "Verknüpfung – wird nicht verfolgt"), nicht)
            self.assertIn("²", [x["ordner"] for x in d["ohne_patient"]])
            if not root:
                self.assertIn(("2/geheim", "Ordner nicht lesbar (Zugriffsrechte)"), nicht)
                self.assertEqual((d["unlesbar"], d["offen"]), (1, 3))
            r = self.a.post("/api/altimport/dokumente/").json()
            self.assertEqual((r["uebernommen"], r["fertig"], r["probleme"]), (3 if not root else 4, True, []))
            namen = {x.originalname: x.titel for x in self.akte(1).dokumente.all()}
            self.assertEqual(namen, {"MÃ¼ller Brief.txt": "Müller Brief", "Größe.txt": "Größe"})
            if not root:
                # unlesbare Ordner zählen wie offene Dokumente: Abschließen nur ausdrücklich ohne sie
                koerper = {"kennwort": KENNWORT, "code": self.codes.pop(), "bestaetigung": "ABSCHLIESSEN"}
                r = self.a.post("/api/altimport/abschliessen/", koerper, format="json")
                self.assertEqual(r.status_code, 409)
                self.assertIn("1 Ordner oder Dateien nicht lesbar", r.json()["fehler"])
        finally:
            os.chmod(wurzel / "2" / "geheim", 0o750)


class ZuruecknehmenUndAbschliessen(Basis):
    def bestaetigung(self, wort):
        return {"kennwort": KENNWORT, "code": self.codes.pop(), "bestaetigung": wort}

    def test_zuruecknehmen_und_erneut_uebernehmen(self):
        self.importiere()
        (TMP / "import" / "PatData" / "1").mkdir(parents=True)
        (TMP / "import" / "PatData" / "1" / "notiz.txt").write_bytes(b"Notiz")
        dienst.dokumente_uebernehmen(self.admin)
        erika = self.akte(1)
        ids = list(Patient.objects.values_list("id", flat=True))
        ordner = TMP / "dokumente" / "1"
        self.assertTrue(any(ordner.iterdir()))
        # seit dem Import ist in einer übernommenen Akte gearbeitet worden; ein Versorger wird woanders gebraucht
        r = client_fuer(self.mitarbeiter).post("/api/kontakte/", {"patient": erika.id, "text": "<p>neu</p>"}, format="json")
        self.assertEqual(r.status_code, 201)
        client_fuer(self.mediziner).post(f"/api/patienten/{self.akte(5).id}/abschliessen/",
                                         {"anlass": "verstorben", "abgeschlossen_am": "2026-01-01"}, format="json")
        testpatienten_anlegen()
        test = Patient.objects.filter(ist_test=True).first()
        apotheke = Versorger.objects.get(name="Apotheke Süd (erfunden)")
        Patient.objects.filter(pk=test.pk).update(versorger=apotheke, ansprechpartner=None)
        self.assertEqual(self.a.get("/api/altimport/").json()["uebernommen"]["kontakte"], 5)

        r = self.a.post("/api/altimport/zuruecknehmen/", self.bestaetigung("falsch"), format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["bestaetigung"]))
        r = self.a.post("/api/altimport/zuruecknehmen/", {"kennwort": "falsch", "code": "1", "bestaetigung": "zurücknehmen"}, format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["kennwort"]))
        self.assertEqual(Patient.objects.filter(ist_test=False).count(), 6)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.a.post("/api/altimport/zuruecknehmen/", self.bestaetigung(" zurücknehmen "), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["zahlen"]["entfernt"], {"patienten": 6, "gewichte": 6, "kontakte": 5, "plaene": 5, "dokumente": 1})
        self.assertEqual(r.json()["zahlen"]["behalten"], {"versorger": 1})
        # alles Übernommene ist weg – mit Historie und Dateien; Testpatienten bleiben
        self.assertEqual(Patient.objects.filter(ist_test=False).count(), 0)
        self.assertGreater(Patient.objects.filter(ist_test=True).count(), 0)
        self.assertEqual(Patient.history.filter(id__in=ids).count(), 0)
        for modell in (Gewichtsmessung, Kontakt, Infusionsplan, Dokument):
            self.assertEqual(modell.objects.filter(patient_id__in=ids).count(), 0, modell)
            self.assertEqual(modell.history.filter(patient_id__in=ids).count(), 0, modell)
        self.assertFalse(ordner.exists())
        self.assertEqual(Importobjekt.objects.count(), 0)
        # vom Import angelegte Stammdaten: entfernt, soweit nichts anderes sie braucht
        self.assertFalse(User.objects.filter(username__in=["a.muster", "hans.alt", "verwaltung", "b.betrachter"]).exists())
        self.assertTrue(User.objects.filter(username="e.beispiel").exists())
        self.assertEqual(list(Versorger.objects.filter(name__contains="(erfunden)").values_list("name", flat=True)), ["Apotheke Süd (erfunden)"])
        self.assertFalse(Ansprechpartner.objects.filter(versorger__name__contains="(erfunden)").exists())
        self.assertFalse(Auswahlwert.objects.filter(wert__in=["Portkatheter", "Power PICC", "Broviac 2-lumig", "ZVK"]).exists())
        self.assertFalse(Praeparat.objects.filter(name="Heparin").exists())
        self.assertFalse(Versorger.history.filter(name="Homecare Nord (erfunden)").exists())
        # Audit-Log: der Vorgang steht drin, die Namen der entfernten Akten nicht mehr
        e = SystemEreignis.objects.filter(art=SystemEreignis.Art.SYSTEM).first()
        self.assertIn("zurückgenommen: 6 Akten mit 6 Gewichten, 5 Kontakten, 5 Infusionsplänen und 1 Dokumenten entfernt", e.details["name"])
        # im Audit-Log erscheint genau dieser Text (der Schlüssel „entfernt“ stünde dort für „Akte gelöscht“)
        from audit.texte import beschreibung
        self.assertIn("zurückgenommen: 6 Akten", beschreibung(e))
        abschluss = SystemEreignis.objects.filter(art=SystemEreignis.Art.AKTE_ABGESCHLOSSEN).get()
        self.assertEqual((abschluss.objekt, abschluss.details.get("entfernt")), ("Akte Nr. 5 (gelöscht)", True))
        # Dump und Zuordnungen sind noch da: gleich wieder übernehmen (dieselben Nummern)
        stand = self.a.get("/api/altimport/").json()
        self.assertEqual((stand["status"], stand["uebernommen"]), ("geladen", None))
        self.assertEqual(self.a.get("/api/altimport/zuordnung/").json()["stand"]["offen"], [])
        r = self.a.post("/api/altimport/import/", {"kennwort": KENNWORT, "code": self.codes.pop()}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(sorted(Patient.objects.filter(ist_test=False).values_list("nummer", flat=True)), [1, 2, 3, 4, 5, 7])
        self.assertEqual(self.akte(7).versorger, apotheke)   # der behaltene Versorger wird wiederverwendet
        self.assertEqual([x.art for x in Importlauf.objects.order_by("id")], ["import", "dokumente", "zurueckgenommen", "import"])

    def test_begonnene_dokumentenuebernahme_endet_mit_dem_zuruecknehmen(self):
        (TMP / "import" / "PatData" / "1").mkdir(parents=True, exist_ok=True)
        for name in ("a.txt", "b.txt"):
            (TMP / "import" / "PatData" / "1" / name).write_bytes(name.encode())
        self.importiere()
        self.assertFalse(dienst.dokumente_uebernehmen(self.admin, max_dateien=1)["fertig"])
        self.assertIsNone(Importlauf.objects.get(art="dokumente").beendet_am)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.a.post("/api/altimport/zuruecknehmen/", self.bestaetigung("ZURÜCKNEHMEN"), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        alt = Importlauf.objects.get(art="dokumente")
        self.assertEqual((alt.erfolgreich, alt.fehler), (False, "Nicht abgeschlossen: Der Import wurde zurückgenommen."))
        self.assertIsNotNone(alt.beendet_am)
        # der nächste Import zählt seine Dokumente in einem eigenen Lauf
        r = self.a.post("/api/altimport/import/", {"kennwort": KENNWORT, "code": self.codes.pop()}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(dienst.dokumente_uebernehmen(self.admin)["fertig"])
        neu = Importlauf.objects.filter(art="dokumente").order_by("-id").first()
        self.assertEqual((neu.erfolgreich, neu.zahlen["dateien"]), (True, 2))
        self.assertNotEqual(neu.id, alt.id)

    def test_fehlertext_ohne_inhalte_der_zeile(self):
        from django.db import IntegrityError

        f = IntegrityError('null value in column "nachname" violates not-null constraint\n'
                           'DETAIL:  Failing row contains (17, Musterfrau, Erika, 1961-03-14).')
        text = dienst._fehlertext(f)
        self.assertEqual(text, 'IntegrityError: null value in column "nachname" violates not-null constraint '
                               '(Einzelheiten im Protokoll des Servers)')
        self.assertEqual(dienst._fehlertext(RuntimeError("Zählung stimmt nicht")), "RuntimeError: Zählung stimmt nicht")

    def test_abschliessen(self):
        r = self.a.post("/api/altimport/abschliessen/", self.bestaetigung("ABSCHLIESSEN"), format="json")
        self.assertEqual(r.status_code, 409)   # nichts übernommen
        self.importiere()
        (TMP / "import" / "PatData" / "1").mkdir(parents=True)
        (TMP / "import" / "PatData" / "1" / "notiz.txt").write_bytes(b"Notiz")
        r = self.a.post("/api/altimport/abschliessen/", self.bestaetigung("abschliessen"), format="json")
        self.assertEqual(r.status_code, 409)
        self.assertIn("noch 1 Dokumente nicht übernommen", r.json()["fehler"])
        r = self.a.post("/api/altimport/abschliessen/", self.bestaetigung("zurücknehmen"), format="json")
        self.assertEqual((r.status_code, list(r.json())), (400, ["bestaetigung"]))
        dienst.dokumente_uebernehmen(self.admin)
        self.assertTrue(any(p["beispiele"] for p in Importlauf.objects.get(art="import").protokoll))
        gescheitert = Importlauf.objects.create(art="probelauf", fehler="Gelöschter Patient 4: Bitte den Anlass des Abschlusses wählen.",
                                                beendet_am=timezone.now())
        r = self.a.post("/api/altimport/abschliessen/", self.bestaetigung("abschliessen"), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        stand = Importstand.aktuell()
        self.assertEqual((stand.status, stand.zuordnung, stand.abgeschlossen_von), ("abgeschlossen", {}, self.admin))
        self.assertEqual((Alttabelle.objects.count(), Importobjekt.objects.count()), (0, 0))
        # die Protokolle behalten die Zählung, verlieren die Nummern – auch in den Fehlertexten früherer Läufe
        self.assertEqual(Importlauf.objects.get(id=gescheitert.id).fehler, "Nicht erfolgreich (Einzelheiten mit dem Abschließen entfernt).")
        protokoll = Importlauf.objects.get(art="import").protokoll
        self.assertTrue(protokoll and all(p["beispiele"] == [] and p["anzahl"] > 0 for p in protokoll))
        self.assertEqual(Patient.objects.filter(ist_test=False).count(), 6)
        d = self.a.get("/api/altimport/").json()
        self.assertEqual((d["status"], d["dump"], d["tabellen"]), ("abgeschlossen", None, []))
        # danach ist alles gesperrt
        for pfad, koerper in (("zuruecknehmen", self.bestaetigung("ZURÜCKNEHMEN")), ("abschliessen", self.bestaetigung("ABSCHLIESSEN")),
                              ("import", {"kennwort": KENNWORT, "code": self.codes.pop()}), ("dokumente", {})):
            self.assertEqual(self.a.post(f"/api/altimport/{pfad}/", koerper, format="json").status_code, 409, pfad)
        self.assertEqual(self.lade().status_code, 409)
        self.assertEqual(self.a.patch("/api/altimport/zuordnung/", {"bereich": "werte", "aenderungen": {}}, format="json").status_code, 409)
        self.assertIn("abgeschlossen", SystemEreignis.objects.filter(art=SystemEreignis.Art.SYSTEM).first().details["name"])
