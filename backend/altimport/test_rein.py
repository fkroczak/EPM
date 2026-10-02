"""Dump-Leser, Werte und Umsetzung – reines Python, ohne Datenbank (läuft auch ohne Django: ``pytest altimport/test_rein.py``).

Alle Daten sind erfunden (``testdaten/beispiel-dump.sql``).
"""
import gzip
import time
import unittest
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal

from altimport import dump, umsetzung
from altimport import werte as W
from altimport.pruefdaten import BEISPIEL, bestand, entscheidungen

HEUTE = date(2026, 10, 2)


def einfach(text: str) -> str:
    """Ersatz für ftfy in den Tests ohne ftfy: repariert doppelt kodiertes UTF-8, wenn der ganze Text passt."""
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def beispiel() -> dict:
    d = dump.lies(BEISPIEL.read_bytes())
    dump.ohne_kennwoerter(d["tabellen"])
    return d["tabellen"]


def lauf(tabellen=None, zuordnung=None, vorhandenes=None):
    return umsetzung.berechne(tabellen or beispiel(), zuordnung or {}, vorhandenes or bestand(), einfach, HEUTE)


class DumpLesen(unittest.TestCase):
    def test_beispiel_dump(self):
        d = dump.lies(BEISPIEL.read_bytes())
        t = d["tabellen"]
        self.assertEqual({n: len(x["zeilen"]) for n, x in t.items()},
                         {"benutzerdaten": 4, "versorger": 4, "patienten": 7, "gewichte": 10, "kontakte": 6, "infusionen": 6})
        self.assertEqual(t["gewichte"]["spalten"], ["ID", "PatID", "gewicht", "lastchange", "edit"])
        self.assertEqual(t["patienten"]["typen"]["groesse"], "decimal(6,2)")
        self.assertEqual(len(t["infusionen"]["spalten"]), 33)
        self.assertEqual(d["kodierung"], "utf-8")
        self.assertEqual(d["hinweise"], [])
        # NULL bleibt None, Zahlen bleiben Text, Zeilenumbrüche und Anführungszeichen sind aufgelöst
        erika = t["patienten"]["zeilen"][0]
        self.assertIsNone(erika[-1])
        self.assertEqual(erika[0], "1")
        self.assertIn("(erfunden).\n\nRestdarm", erika[12])
        self.assertEqual(t["kontakte"]["zeilen"][2][2], "RÃ¼ckfrage zur Laufzeit, Mutter sagt: 'alles gut' \\ Ende")

    def test_maskierung_und_sonderfaelle(self):
        sql = (
            "CREATE TABLE `t` (\n  `a` int NOT NULL,\n  `b` varchar(20) DEFAULT 'x,y' COMMENT 'a (b), c',\n"
            "  `c` decimal(6,1) DEFAULT NULL,\n  `d` enum('ja','nein') DEFAULT NULL,\n  PRIMARY KEY (`a`),\n"
            "  KEY `idx` (`b`,`c`)\n) ENGINE=InnoDB;\n"
            "INSERT INTO `t` VALUES (1,'it\\'s; -- kein Kommentar (auch keine Klammer)',-1.5,'ja'),"
            "(2,'zwei''fach \"doppelt\"',1e3,NULL),(3,'Zeile\\nUmbruch\\tTab \\\\ Schrägstrich 100\\%',.5,'nein'),\n"
            "(4,_binary 'binär',0x4142,'ja');\n"
            "# Kommentar mit ; und 'Anführungszeichen\n"
            "/* Block; 'Kommentar' */\n"
            "INSERT INTO `t` VALUES (5,'',NULL,NULL);"
        )
        t = dump.lies(sql.encode())["tabellen"]["t"]
        self.assertEqual(t["spalten"], ["a", "b", "c", "d"])
        self.assertEqual(t["typen"], {"a": "int", "b": "varchar(20)", "c": "decimal(6,1)", "d": "enum('ja','nein')"})
        self.assertEqual(t["zeilen"], [
            ["1", "it's; -- kein Kommentar (auch keine Klammer)", "-1.5", "ja"],
            ["2", "zwei'fach \"doppelt\"", "1e3", None],
            ["3", "Zeile\nUmbruch\tTab \\ Schrägstrich 100\\%", ".5", "nein"],
            ["4", "binär", "0x4142", "ja"],
            ["5", "", None, None],
        ])

    def test_phpmyadmin_mit_spaltenliste(self):
        sql = ("-- phpMyAdmin SQL Dump\nSET SQL_MODE = \"NO_AUTO_VALUE_ON_ZERO\";\nSTART TRANSACTION;\n"
               "CREATE TABLE IF NOT EXISTS `epm`.`gewichte` (\n  `ID` int(11) NOT NULL,\n  `PatID` int(11) NOT NULL,\n"
               "  `gewicht` decimal(6,2) NOT NULL\n) ENGINE=InnoDB DEFAULT CHARSET=utf8;\n\n"
               "INSERT INTO `gewichte` (`ID`, `gewicht`, `PatID`) VALUES\n(1, '64.50', 1),\n(2, '70.00', 2);\n"
               "INSERT INTO `gewichte` (`ID`, `PatID`, `gewicht`, `lastchange`) VALUES (3, 2, '71.00', '2024-01-01 10:00:00');\n"
               "ALTER TABLE `gewichte`\n  ADD PRIMARY KEY (`ID`);\nCOMMIT;\n")
        t = dump.lies(sql.encode())["tabellen"]
        self.assertEqual(list(t), ["gewichte"])
        self.assertEqual(t["gewichte"]["spalten"], ["ID", "PatID", "gewicht", "lastchange"])
        self.assertEqual(t["gewichte"]["zeilen"], [["1", "1", "64.50", None], ["2", "2", "70.00", None],
                                                  ["3", "2", "71.00", "2024-01-01 10:00:00"]])

    def test_ohne_create_table(self):
        d = dump.lies(b"INSERT INTO t VALUES (1,'a'),(2,'b');")
        self.assertEqual(d["tabellen"]["t"]["spalten"], ["spalte1", "spalte2"])
        self.assertIn("keine Spaltennamen", d["hinweise"][0])

    def test_gepackt_und_windows_1252(self):
        gepackt = gzip.compress(BEISPIEL.read_bytes())
        self.assertEqual(len(dump.lies(gepackt)["tabellen"]), 6)
        alt = "CREATE TABLE `t` (`a` varchar(9));\nINSERT INTO `t` VALUES ('Größe');".encode("cp1252")
        d = dump.lies(alt)
        self.assertEqual(d["kodierung"], "windows-1252")
        self.assertEqual(d["tabellen"]["t"]["zeilen"], [["Größe"]])
        self.assertIn("nicht UTF-8", d["hinweise"][0])

    def test_fehler_sind_verstaendlich(self):
        faelle = {
            b"": "keine Tabellen",
            b"SELECT 1;": "keine Tabellen",
            b"CREATE TABLE `t` (`a` int, `b` int);\nINSERT INTO `t` VALUES (1,2),(3);": "Zeile 2: 1 Werte bei 2 Spalten",
            b"CREATE TABLE `t` (`a` int);\nINSERT INTO `t` VALUES (1),(abc);": "Zeile 2: Wert nicht lesbar",
            b"CREATE TABLE `t` (`a` int);\nINSERT INTO `t` (`a`,`b`) VALUES (1);": "1 Werte bei 2 genannten Spalten",
            b"\x1f\x8bkaputt": "beschädigt",
        }
        for daten, erwartet in faelle.items():
            with self.subTest(daten=daten[:30]):
                with self.assertRaises(dump.DumpFehler) as f:
                    dump.lies(daten)
                self.assertIn(erwartet, str(f.exception))

    def test_nicht_geschlossene_zeichenkette_haengt_nicht(self):
        boese = b"CREATE TABLE `t` (`a` text);\nINSERT INTO `t` VALUES ('" + b"a\\'" * 20000
        beginn = time.monotonic()
        with self.assertRaises(dump.DumpFehler) as f:
            dump.lies(boese)
        self.assertIn("Zeile 2: Eine Zeichenkette oder ein Kommentar ist nicht geschlossen", str(f.exception))
        self.assertLess(time.monotonic() - beginn, 2)

    def test_kennwoerter_werden_nie_gespeichert(self):
        d = dump.lies(BEISPIEL.read_bytes())
        self.assertRegex(d["tabellen"]["benutzerdaten"]["zeilen"][0][2], "^[0-9a-f]{32}$")
        self.assertEqual(dump.ohne_kennwoerter(d["tabellen"]), [("benutzerdaten", "Kennwort")])
        self.assertEqual([z[2] for z in d["tabellen"]["benutzerdaten"]["zeilen"]], [None] * 4)
        self.assertEqual(d["tabellen"]["benutzerdaten"]["entfernt"], ["Kennwort"])
        # auch am Inhalt erkannt, wenn die Spalte anders heißt
        t = {"x": {"spalten": ["name", "geheim"], "zeilen": [["a", "0cc175b9c0f1b6a831c399e269772661"],
                                                           ["b", "92eb5ffee6ae2fec3ad71c777531578f"], ["c", None]]}}
        self.assertEqual(dump.ohne_kennwoerter(t), [("x", "geheim")])
        self.assertEqual([z[1] for z in t["x"]["zeilen"]], [None, None, None])


class Werte(unittest.TestCase):
    def test_zahl(self):
        for roh, erwartet in [("64.50", "64.50"), ("1.480,5", "1480.5"), ("70,5", "70.5"), (" 12 ", "12"), ("-3", "-3"),
                              ("1e3", "1E+3"), (".5", "0.5"), ("433.564", "433.564")]:
            self.assertEqual(W.zahl(roh), Decimal(erwartet), roh)
        for leer in (None, "", " ", "-", "–"):
            self.assertIsNone(W.zahl(leer))
        for unlesbar in ("abc", "12 kg", "1,2,3", "1,234.5", "1.2.3", "nan", "--5"):
            with self.assertRaises(W.Unlesbar, msg=unlesbar):
                W.zahl(unlesbar)
        self.assertEqual(W.ganzzahl("5.0"), 5)
        with self.assertRaises(W.Unlesbar):
            W.ganzzahl("5.5")

    def test_zeitpunkt(self):
        self.assertEqual(W.zeitpunkt("2023-05-02 10:11:12"), datetime(2023, 5, 2, 10, 11, 12))
        self.assertEqual(W.zeitpunkt("2023-05-02"), datetime(2023, 5, 2))
        self.assertEqual(W.zeitpunkt("02.05.2023 10:11"), datetime(2023, 5, 2, 10, 11))
        self.assertEqual(W.datum("2023-05-02T10:11:12.123"), date(2023, 5, 2))
        for leer in (None, "", "0000-00-00", "0000-00-00 00:00:00"):
            self.assertIsNone(W.zeitpunkt(leer))
        for unlesbar in ("2023-13-01", "gestern", "2023-02-30", "1.1.23"):
            with self.assertRaises(W.Unlesbar, msg=unlesbar):
                W.zeitpunkt(unlesbar)

    def test_formatierter_text(self):
        self.assertEqual(W.als_html("Eins & <zwei>\nnoch\n\n  Drei  "),
                         ("<p>Eins &amp; &lt;zwei&gt;<br>noch</p><p>Drei</p>", False))
        html, war_html = W.als_html("<div>A</div><H1>B</h1><p>C<br/>D</p><h6>E</h6>")
        self.assertTrue(war_html)
        self.assertEqual(html, "<p>A</p><h3>B</h3><p>C<br/>D</p><h4>E</h4>")
        self.assertEqual(W.als_html("  "), ("", False))
        self.assertFalse(W.ist_html("a < b und c > d"))

    def test_email_und_platzhalter(self):
        self.assertTrue(W.email_gueltig("a.b@example.org"))
        for falsch in ("a(at)b.de", "a@b", "a b@c.de", "@b.de", ""):
            self.assertFalse(W.email_gueltig(falsch), falsch)
        self.assertTrue(all(W.ist_leer(x) for x in ("", "-", " – ", "--")))
        self.assertFalse(W.ist_leer("0"))

    def test_praeparatnamen_vergleichen(self):
        gleich = [("Glamin 13,4%", "glamin 13,4 %"), ("NaCl 0.9 %", "NaCl 0,9 %"), ("Nephrotect 10,0 %", "nephrotect 10%"),
                  ("Pantozol® 40 mg", "pantozol 40 mg")]
        for a, b in gleich:
            self.assertEqual(umsetzung.norm_praeparat(a), umsetzung.norm_praeparat(b), (a, b))
        self.assertNotEqual(umsetzung.norm_praeparat("Lipovenös MCT 10 %"), umsetzung.norm_praeparat("Lipovenös MCT 20 %"))
        self.assertEqual(umsetzung.praeparat_vorschlag("Glamin 13.4%"), {"name": "Glamin", "konzentration": "13,4 %"})
        self.assertEqual(umsetzung.praeparat_vorschlag("Addel N"), {"name": "Addel N", "konzentration": ""})

    def test_namen_aus_kuerzel(self):
        self.assertEqual(umsetzung.name_aus_kuerzel("anna-lena.mueller-schmidt"), ("Anna-Lena", "Mueller-Schmidt"))
        self.assertEqual(umsetzung.name_aus_kuerzel("e.beispiel"), ("E", "Beispiel"))
        self.assertEqual(umsetzung.name_aus_kuerzel("verwaltung"), ("", "Verwaltung"))
        self.assertEqual(umsetzung.benutzername_aus("Hans Alt (extern)"), "Hans.Alt.extern")

    @unittest.skipUnless(__import__("importlib").util.find_spec("ftfy"), "ftfy ist hier nicht installiert")
    def test_reparatur_mit_ftfy(self):
        repariere = W.ftfy_reparatur()
        self.assertEqual(W.text("MÃ¼ller â€“ GrÃ¶ÃŸe", repariere), ("Müller – Größe", True))
        # Unauffälliges bleibt unverändert – auch Anführungszeichen und HTML-Zeichen
        for text in ("Müller, Größe 1,80 m", "„Zitat“ &amp; <b>fett</b>", "Pâté"):
            self.assertEqual(W.text(text, repariere), (text, False))


class Umsetzung(unittest.TestCase):
    def test_vorschlaege_und_offene_punkte(self):
        e = lauf()
        offen = {(o["bereich"], o["text"]) for o in e.offen}
        self.assertEqual(offen, {
            ("werte", "Nickelallergie „vielleicht“: Bitte zuordnen."),
            ("praeparate", "Lipide „Clinoleik 20%“: Bitte zuordnen."),
            ("praeparate", "Katheterblock / Medikamente „Heparin 100 I.E. nach Bedarf“: Bitte zuordnen."),
            ("auffaelligkeiten", "Es gibt Auffälligkeiten, über die noch entschieden werden muss."),
        })
        # Spalten: alles erkannt; nicht übernommen werden nur die bekannten Spalten
        quelle = {t["name"]: t for t in e.quelle["tabellen"]}
        self.assertEqual({t["name"]: t["tabelle"] for t in e.quelle["tabellen"]},
                         {n: n for n in ("benutzerdaten", "versorger", "patienten", "gewichte", "kontakte", "infusionen")})
        self.assertEqual({f["name"]: f["spalte"] for f in quelle["gewichte"]["felder"]},
                         {"id": "ID", "patient": "PatID", "gewicht": "gewicht", "zeit": "lastchange", "bearbeiter": "edit"})
        self.assertEqual([(r["spalte"], r["art"]) for r in quelle["patienten"]["rest"]],
                         [("dokumente", "bekannt"), ("gewicht", "bekannt")])
        self.assertEqual([(r["spalte"], r["art"]) for r in quelle["benutzerdaten"]["rest"]],
                         [("ID", "bekannt"), ("Kennwort", "kennwort")])
        self.assertEqual(quelle["infusionen"]["rest"], [])
        self.assertEqual(e.quelle["uebrig"], [])
        # Benutzer: vorhandener Benutzer erkannt (auch bei anderer Schreibweise), Konten laut Rechten, Rest historisch
        benutzer = {b["schluessel"]: b["wirksam"] for b in e.benutzer}
        self.assertEqual(benutzer["e.beispiel"], {"art": "benutzer", "id": 1})
        self.assertEqual(benutzer["a.muster"]["rolle"], "mitarbeiter")
        self.assertEqual(benutzer["verwaltung"], {"art": "konto", "benutzername": "verwaltung", "vorname": "",
                                                  "nachname": "Verwaltung", "titel": "", "rolle": "admin"})
        self.assertEqual(benutzer["hans.alt"], {"art": "historisch", "benutzername": "hans.alt", "vorname": "Hans",
                                                "nachname": "Alt", "titel": ""})
        self.assertNotIn("test", benutzer)
        # Versorger: gleiche Firma = ein Versorger mit zwei Ansprechpartnern; Platzhalterzeile bleibt leer
        self.assertEqual([v["wirksam"]["art"] for v in e.versorger], ["leer", "neu", "neu", "neu"])
        self.assertEqual([v["name"] for v in e.saetze["versorger"]], ["Homecare Nord (erfunden)", "Apotheke Süd (erfunden)"])
        self.assertEqual([(a["name"], a["telefon"], a["email"]) for a in e.saetze["ansprechpartner"]],
                         [("Frau Probe", "0000 111111", "probe@example.org"), ("Herr Muster", "0000 222222", "muster@example.org")])
        apotheke = e.saetze["versorger"][1]
        self.assertEqual((apotheke["telefon"], apotheke["email"], apotheke["notiz"]),
                         ("0000 333333", "", "E-Mail laut Altsystem: keine-adresse."))
        # Werte
        katheter = {z["text"]: z["wirksam"] for z in e.werte["katheter"]}
        self.assertEqual(katheter["Nein"], {"art": "kein"})
        self.assertEqual(katheter["ZVK"], {"art": "wert", "id": 11})
        self.assertEqual(katheter["Portkatheter"], {"art": "neu", "wert": "Portkatheter"})
        self.assertEqual(katheter[""], {"art": "leer"})
        self.assertEqual({z["text"]: z["wirksam"] for z in e.werte["nickel"]},
                         {"": "unbekannt", "Ja": "ja", "Nein": "nein", "unbekannt": "unbekannt", "vielleicht": None})
        # Präparate: nur eindeutige Treffer werden vorgeschlagen; Ähnliches nur als Hinweis
        lipide = {z["text"]: z for z in e.praeparate["lipide"]["zeilen"]}
        self.assertEqual(lipide["Clinoleic 20 %"]["wirksam"], {"art": "praeparat", "id": 4})
        self.assertIsNone(lipide["Clinoleik 20%"]["wirksam"])
        self.assertEqual(lipide["Clinoleik 20%"]["aehnlich"], [4])
        self.assertEqual(lipide["Clinoleik 20%"]["neu_vorschlag"], {"name": "Clinoleik", "konzentration": "20 %"})
        amino = {z["text"]: z["wirksam"] for z in e.praeparate["amino"]["zeilen"]}
        self.assertEqual(amino, {"Aminoplasmal 10 %": {"art": "praeparat", "id": 12}, "Glamin": {"art": "praeparat", "id": 3},
                                 "Glamin 13,4%": {"art": "praeparat", "id": 3}})
        self.assertEqual([z["text"] for z in e.praeparate["vitamine"]["zeilen"]], ["Cernevit", "Soluvit N", "Vitalipid adult"])
        # gelöschte Patienten: Standard „nicht übernehmen“, mit Zählung ihrer Einträge
        self.assertEqual([(g["schluessel"], g["name"], g["wirksam"]["art"], g["gewichte"], g["kontakte"], g["plaene"])
                          for g in e.geloeschte], [("4", "Probe, Jonas", "nicht", 1, 1, 1), ("6", "Demo, Karl", "nicht", 0, 0, 0)])

    def test_auffaelligkeiten(self):
        e = lauf()
        a = {x["schluessel"]: x for x in e.auffaelligkeiten}
        self.assertEqual(set(a), {
            "patienten:3:geburtsdatum", "patienten:2:plz", "patienten:5:groesse", "gewichte:7:gewicht", "gewichte:8:zeit",
            "infusionen:2:kcal", "infusionen:3:pantozol", "infusionen:3:glucose_g"})
        geburt = a["patienten:3:geburtsdatum"]
        self.assertTrue(geburt["blockiert"])
        self.assertEqual((geburt["moeglich"], geburt["eingabe"], geburt["roh"]), (["wert", "auslassen"], "datum", "0000-00-00"))
        self.assertEqual([x["schluessel"] for x in e.auffaelligkeiten][0], "patienten:3:geburtsdatum")  # Blockierendes zuerst
        self.assertEqual(a["gewichte:7:gewicht"]["standard"], "unveraendert")
        self.assertEqual(a["gewichte:8:zeit"]["standard"], "auslassen")
        self.assertEqual(a["infusionen:2:kcal"]["standard"], "leer")
        self.assertFalse(any(x["blockiert"] for k, x in a.items() if k != "patienten:3:geburtsdatum"))
        # gelöschte, nicht übernommene Patienten erzeugen keine Auffälligkeiten (Nickelallergie „vielleicht“ ist eine Zuordnung)
        self.assertFalse([k for k in a if k.startswith(("patienten:4:", "patienten:6:"))])

    def test_datensaetze_nach_den_regeln(self):
        e = lauf(zuordnung=entscheidungen())
        self.assertEqual(e.offen, [])
        s = e.saetze
        patienten = {p["nummer"]: p for p in s["patienten"]}
        self.assertEqual(sorted(patienten), [1, 2, 3, 4, 5, 7])
        erika, max_, paula, jonas, hanna = (patienten[n] for n in (1, 2, 3, 4, 5))
        # Regel 3: doppelt kodierte Umlaute repariert
        self.assertEqual((max_["nachname"], max_["strasse"]), ("Müller", "Beispielstraße 5"))
        # Regel 4: fehlender Versorger → leer; Regel 6: Meter → Zentimeter, 0 → leer
        self.assertIsNone(max_["versorger"])
        self.assertEqual(max_["groesse_cm"], Decimal("181.0"))
        self.assertIsNone(paula["groesse_cm"])
        # Regel 9/10: Katheter über die Auswahlliste, „Nein“ = kein Katheter, Nickelallergie mit NULL → unbekannt
        self.assertEqual(erika["katheter"], {"neu": "portkatheter"})
        self.assertEqual((hanna["katheter"], hanna["kein_katheter"]), (None, True))
        self.assertEqual(paula["katheter"], {"id": 11})
        self.assertEqual([p["nickelallergie"] for p in (erika, max_, paula, hanna)], ["nein", "unbekannt", "unbekannt", "ja"])
        # Regel 11: reiner Text wird zu Absätzen, HTML bleibt (unbekannte Blöcke werden Absätze)
        self.assertEqual(erika["diagnose"], "<p>Kurzdarmsyndrom nach Resektion (erfunden).</p><p>Restdarm ca. 80 cm.<br>Colon in Kontinuität.</p>")
        self.assertIn("<p>Verlauf:</p><ul><li>02.01.2021 Beginn</li></ul>", erika["therapie"])
        self.assertEqual(max_["diagnose"], "<p>Chronisches Darmversagen (erfunden) &amp; &lt;Verdacht&gt;</p>")
        # nichts geht verloren: zu langer Text und ungültige E-Mail stehen in der Bemerkung
        self.assertEqual(len(max_["ueberweisung_durch"]), 200)
        self.assertIn("Station 4", max_["bemerkung"][0])
        self.assertEqual((hanna["email"], hanna["bemerkung"]),
                         ("", ["<p><strong>E-Mail (laut Altsystem, keine gültige Adresse):</strong> hanna(at)example</p>"]))
        # Versorger mit Ansprechpartner; Versorger 0 (Platzhalter) → leer
        self.assertEqual((erika["versorger"], erika["ansprechpartner"]),
                         ({"neu": "homecare nord (erfunden)"}, {"neu": "neu:homecare nord (erfunden):frau probe"}))
        self.assertEqual((hanna["versorger"], hanna["kein_versorger"]), (None, False))
        # Bearbeiter und Zeitpunkt der letzten Änderung
        self.assertEqual((erika["bearbeiter"], erika["geaendert"]), ({"id": 1}, datetime(2023, 5, 2, 10, 11, 12)))
        self.assertEqual(hanna["bearbeiter"], {"id": 1})  # „E.Beispiel“ = e.beispiel
        self.assertEqual(max_["bearbeiter"], {"neu": "hans.alt"})
        # Korrektur: Geburtsdatum eingetragen; gelöschter Patient als abgeschlossene Akte
        self.assertEqual(paula["geburtsdatum"], date(1988, 7, 21))
        self.assertEqual(jonas["abschluss"], {"am": date(2020, 1, 15), "anlass": "therapie_beendet",
                                              "notiz": "Im Altsystem als gelöscht markiert am 15.01.2020."})
        self.assertIsNone(erika["abschluss"])

        # Gewichte (Regeln 2, 4, 5)
        gewichte = {g["alt"]: g for g in s["gewichte"]}
        self.assertEqual(sorted(gewichte, key=int), ["1", "4", "6", "7", "9", "10"])
        self.assertEqual((gewichte["4"]["gewicht_kg"], gewichte["4"]["gemessen_am"], gewichte["4"]["bearbeiter"]),
                         (Decimal("78.3"), date(2022, 10, 1), {"neu": "hans.alt"}))
        self.assertIsNone(gewichte["9"]["bearbeiter"])
        self.assertEqual(e.zahlen["gewichte"], {"alt": 10, "neu": 6, "nicht": {"ohne_patient": 1, "platzhalter": 2, "ausgelassen": 1}})
        # Kontakte
        kontakte = {k["alt"]: k for k in s["kontakte"]}
        self.assertEqual(sorted(kontakte), ["1", "2", "3", "6"])
        self.assertEqual(kontakte["1"]["text"], "<p>Telefonat: Befinden stabil, Infusion läuft ohne Probleme.<br>Rückruf in 4 Wochen.</p>")
        self.assertEqual(kontakte["3"]["text"], "<p>Rückfrage zur Laufzeit, Mutter sagt: 'alles gut' \\ Ende</p>")
        self.assertEqual(e.zahlen["kontakte"], {"alt": 6, "neu": 4, "nicht": {"ohne_patient": 1, "leer": 1}})

        # Infusionspläne (Regeln 7, 13, 14, 16)
        plaene = {p["alt"]: p for p in s["plaene"]}
        self.assertEqual(sorted(plaene), ["1", "2", "3", "4", "6"])
        p1, p2, p3 = plaene["1"], plaene["2"], plaene["3"]
        self.assertEqual((p1["status"], p1["vorgaenger"], p2["status"], p2["vorgaenger"]), ("abgeloest", None, "aktuell", "1"))
        self.assertEqual((p1["gueltig_ab"], p1["erstellt"], p1["geaendert"]),
                         (date(2021, 1, 2), datetime(2021, 1, 2, 10, 0), datetime(2021, 1, 2, 10, 30)))
        self.assertEqual((p1["basis_praeparat"], p1["basis_ml"]), ({"id": 1, "kategorie": "basisloesung"}, 500))
        self.assertEqual((p1["glucose_g"], p1["glucose_praeparat"]), (Decimal("150.0"), None))   # „-“ → leer (Regel 7)
        self.assertEqual(p1["aminosaeuren_praeparat"]["id"], 3)
        self.assertIsNone(p1["albumin_ml"])                                                     # 0 = nicht verwendet
        self.assertEqual([v["id"] for v in p1["vitamine"]], [6, 7])                             # „A | B“
        self.assertEqual((p1["spurenelemente"]["id"], p1["katheterschutz"]["id"]), (5, 9))
        self.assertEqual((p1["pantozol_stufe"], p1["pantozol_tage"], p1["laufzeit_h"]), (1, 5, Decimal("12.0")))
        self.assertIsNone(p1["kcal_manuell"])          # 1115 kcal = berechnet (150·4 + 60·4 + 30·9,15)
        self.assertEqual(p1["gesamtvolumen_ml"], Decimal("2257.50"))
        self.assertEqual(p1["bemerkung"], "<p>Testplan – keine echte Verordnung</p>")
        # Plan 2: Schreibvariante zugeordnet, Heparin als weiterer Bestandteil, Tippfehler bei kcal, Laufrate in der Bemerkung
        self.assertEqual(p2["lipide_praeparat"], {"id": 4, "kategorie": "lipide"})
        self.assertEqual(p2["katheterschutz"]["id"], 9)
        self.assertEqual(p2["positionen"], [{"praeparat": {"neu": "medikament|heparin|", "kategorie": "medikament"},
                                             "bemerkung": "Heparin 100 I.E. nach Bedarf"}])
        self.assertIsNone(p2["kcal_manuell"])
        self.assertEqual(p2["bemerkung_extras"], ["<p><strong>Energie (laut Altsystem):</strong> 433.564 kcal</p>",
                                                  "<p><strong>Laufrate (laut Altsystem):</strong> 180.0 ml/h</p>"])
        self.assertEqual((p2["albumin_ml"], p2["albumin_praeparat"]["id"]), (Decimal("20.0"), 10))
        self.assertEqual((p2["pantozol_stufe"], p2["pantozol_tage"]), (0, None))               # Zeiten ohne PPI entfallen
        self.assertEqual((p2["ersteller"], p2["bearbeiter"]), ({"id": 1}, {"neu": "a.muster"}))
        # Plan 3: kcal weicht von der Berechnung ab → manuell; unbekannter PPI-Wert in der Bemerkung; ohne lastchange
        self.assertEqual((p3["kcal_manuell"], p3["pantozol_stufe"], p3["geaendert"]), (1500, 0, datetime(2022, 9, 15, 12, 0)))
        self.assertEqual(p3["bemerkung"], "<p>Kommentar mit <i>HTML</i></p>")
        self.assertEqual(p3["bemerkung_extras"], ["<p><strong>Protonenpumpenhemmer (laut Altsystem):</strong> 7</p>"])
        self.assertEqual(p3["glucose_g"], Decimal("9000.0"))   # unplausibel, aber unverändert übernommen (Auffälligkeit)
        self.assertEqual(e.zahlen["infusionen"], {"alt": 6, "neu": 5, "aktuell": 4, "nicht": {"ohne_patient": 1}})
        self.assertEqual(e.zahlen["patienten"], {"alt": 7, "neu": 6, "abgeschlossen": 1, "nicht": {"geloescht": 1}})

        # neu angelegt wird nur, was gebraucht wird
        self.assertEqual([p["schluessel"] for p in s["praeparate"]], ["medikament|heparin|"])
        self.assertEqual(sorted(a["wert"] for a in s["auswahlwerte"]), ["Broviac 2-lumig", "Portkatheter", "Power PICC"])
        self.assertEqual({b["benutzername"]: (b["rolle"], b["historisch"]) for b in s["benutzer"]},
                         {"a.muster": ("mitarbeiter", False), "b.betrachter": ("betrachter", False),
                          "verwaltung": ("admin", False), "hans.alt": ("betrachter", True)})

    def test_nur_benoetigte_stammdaten(self):
        # ohne den gelöschten Patienten 4 braucht niemand „Power PICC“
        z = entscheidungen()
        del z["geloeschte"]
        e = lauf(zuordnung=z)
        self.assertEqual(sorted(a["wert"] for a in e.saetze["auswahlwerte"]), ["Broviac 2-lumig", "Portkatheter"])
        # ein historischer Benutzer entsteht nur, wenn ein übernommener Eintrag ihn nennt
        z["korrekturen"]["patienten:2:nummer"] = {"art": "auslassen", "alt": "2"}
        e = lauf(zuordnung=z)
        self.assertNotIn("hans.alt", [b["benutzername"] for b in e.saetze["benutzer"]])
        self.assertEqual(e.zahlen["patienten"]["nicht"], {"geloescht": 2, "ausgelassen": 1})
        self.assertEqual(e.zahlen["gewichte"]["nicht"]["patient_nicht_uebernommen"], 3)

    def test_protokoll_nach_regeln_ohne_namen(self):
        e = lauf(zuordnung=entscheidungen())
        je_regel = {}
        for p in e.protokoll:
            je_regel.setdefault(p["regel"], []).append(p)
        self.assertTrue({1, 2, 3, 4, 5, 6, 8, 10, 11, 13, 14, 16} <= set(je_regel))
        self.assertEqual([(p["bereich"], p["anzahl"], p["beispiele"]) for p in je_regel[5]], [("gewichte", 2, ["2", "3"])])
        self.assertEqual({p["bereich"]: p["anzahl"] for p in je_regel[3]}, {"kontakte": 1, "patienten": 2})
        self.assertEqual(sorted((p["bereich"], p["anzahl"]) for p in je_regel[4]),
                         [("gewichte", 1), ("infusionen", 1), ("kontakte", 1), ("patienten", 1)])
        # das Protokoll nennt Nummern, keine Namen und keine Inhalte
        alles = " ".join(f"{p['text']} {' '.join(p['beispiele'])}" for p in e.protokoll)
        for name in ("Musterfrau", "Müller", "Erika", "Probe", "Hanna", "Kurzdarm", "example"):
            self.assertNotIn(name, alles)
        self.assertEqual([p["stufe"] for p in e.protokoll], sorted((p["stufe"] for p in e.protokoll),
                                                                 key=["fehler", "warnung", "hinweis", "info"].index))

    def test_korrekturen(self):
        z = entscheidungen()
        # Korrektur gilt nur, solange der Wert im Dump derselbe ist (frischer Dump mit anderem Wert → wieder offen)
        z["korrekturen"]["patienten:3:geburtsdatum"]["alt"] = "1900-01-01"
        e = lauf(zuordnung=z)
        self.assertTrue(any(a["schluessel"] == "patienten:3:geburtsdatum" and a["blockiert"] for a in e.auffaelligkeiten))
        # Patient auslassen: mit allen Einträgen; die Entscheidung bleibt in der Liste sichtbar
        z["korrekturen"]["patienten:3:geburtsdatum"] = {"art": "auslassen", "alt": "0000-00-00"}
        e = lauf(zuordnung=z)
        self.assertEqual(e.offen, [])
        self.assertNotIn(3, [p["nummer"] for p in e.saetze["patienten"]])
        a = next(a for a in e.auffaelligkeiten if a["schluessel"] == "patienten:3:geburtsdatum")
        self.assertEqual((a["art"], a["entscheidung"]["art"], a["blockiert"]), ("ausgelassen", "auslassen", False))
        # Werte korrigieren, leeren, bestätigen, auslassen
        z = entscheidungen()
        z["korrekturen"].update({
            "gewichte:7:gewicht": {"art": "wert", "wert": "64,0", "alt": "640.0"},
            "gewichte:8:zeit": {"art": "wert", "wert": "03.10.2022", "alt": None},
            "infusionen:2:kcal": {"art": "wert", "wert": "1400", "alt": "433.564"},
            "infusionen:3:glucose_g": {"art": "leer", "alt": "9000.0"},
            "patienten:5:groesse": {"art": "unveraendert", "alt": "16.0"},
            "patienten:2:plz": {"art": "wert", "wert": "04109", "alt": "4109"},
        })
        e = lauf(zuordnung=z)
        gewichte = {g["alt"]: g for g in e.saetze["gewichte"]}
        self.assertEqual(gewichte["7"]["gewicht_kg"], Decimal("64.0"))
        self.assertEqual(gewichte["8"]["gemessen_am"], date(2022, 10, 3))
        plaene = {p["alt"]: p for p in e.saetze["plaene"]}
        self.assertEqual(plaene["2"]["kcal_manuell"], 1400)   # berechnet wären 175·4 + 70·4 + 40·9,15 = 1346
        patienten = {p["nummer"]: p for p in e.saetze["patienten"]}
        self.assertEqual(patienten[2]["plz"], "04109")
        self.assertIsNone(plaene["3"]["glucose_g"])
        self.assertEqual(patienten[5]["groesse_cm"], Decimal("16.0"))
        a = {x["schluessel"]: x for x in e.auffaelligkeiten}
        self.assertEqual(a["gewichte:7:gewicht"]["art"], "korrigiert")
        self.assertEqual(a["patienten:5:groesse"]["entscheidung"]["art"], "unveraendert")
        self.assertEqual(a["infusionen:3:glucose_g"]["text"], "Korrigiert: leer statt „9000.0“.")
        self.assertNotIn("Energie", " ".join(plaene["2"]["bemerkung_extras"]))

    def test_spalten_und_tabellen_zuordnen(self):
        t = beispiel()
        # Spalte heißt anders, eine unbekannte Spalte und eine unbekannte Tabelle kommen dazu
        g = t["gewichte"]
        g["spalten"][g["spalten"].index("lastchange")] = "zeitstempel"
        g["spalten"].append("waage")
        for z in g["zeilen"]:
            z.append("W1")
        t["protokoll_alt"] = {"spalten": ["id", "text"], "zeilen": [["1", "x"]]}
        t["patientendaten"] = t.pop("patienten")
        e = lauf(tabellen=deepcopy(t), zuordnung=entscheidungen())
        texte = [o["text"] for o in e.offen if o["bereich"] == "spalten"]
        self.assertEqual(len(texte), 6)
        self.assertTrue(any("„patientendaten“" in x for x in texte))
        self.assertTrue(any("„Erfasst am“ ist keine Spalte zugeordnet" in x and "frischen Dump" in x for x in texte))
        self.assertTrue(any("Spalte „waage“" in x for x in texte) and any("Spalte „zeitstempel“" in x for x in texte))
        self.assertTrue(any("Tabelle „Patienten“ fehlt im Dump" in x for x in texte))
        self.assertTrue(any("„protokoll_alt“" in x for x in texte))
        z = entscheidungen()
        z.update({"tabellen": {"patienten": "Patientendaten"}, "tabellen_ignoriert": ["protokoll_alt"],
                  "spalten": {"gewichte": {"zeit": "zeitstempel"}}, "spalten_ignoriert": {"gewichte": ["waage"]}})
        e = lauf(tabellen=deepcopy(t), zuordnung=z)
        self.assertEqual(e.offen, [])
        self.assertEqual(len(e.saetze["gewichte"]), 6)
        self.assertEqual(e.quelle["uebrig"], [{"tabelle": "protokoll_alt", "zeilen": 1, "art": "ignoriert"}])
        # Spalte bewusst leer lassen; Tabelle bewusst nicht vorhanden
        z["spalten"]["patienten"] = {"hausarzt": ""}
        z["tabellen"]["benutzerdaten"] = ""
        e = lauf(tabellen=deepcopy(t), zuordnung=z)
        self.assertEqual({o["text"] for o in e.offen},
                         {"Tabelle „Patienten“: Die Spalte „barzt“ ist keinem Feld zugeordnet – bitte zuordnen oder „nicht übernehmen“ wählen.",
                          "Die Tabelle „benutzerdaten“ des Dumps ist keiner Tabelle zugeordnet – bitte zuordnen oder „nicht übernehmen“ wählen."})
        self.assertEqual({b["benutzername"] for b in e.saetze["benutzer"]}, {"a.muster", "hans.alt"})
        self.assertTrue(all(b["historisch"] for b in e.saetze["benutzer"]))

    def test_alter_dump_ohne_zeitpunkte(self):
        # Regel 2: Der Dump vom 23.02.2024 hat für Gewichte und Kontakte keine Spalte „lastchange“
        t = beispiel()
        for name in ("gewichte", "kontakte"):
            i = t[name]["spalten"].index("lastchange")
            t[name]["spalten"].pop(i)
            for z in t[name]["zeilen"]:
                z.pop(i)
        e = lauf(tabellen=t, zuordnung=entscheidungen())
        texte = [o["text"] for o in e.offen]
        self.assertEqual(len(texte), 2)
        self.assertTrue(all("frischen Dump ziehen" in x for x in texte))

    def test_zuordnungen_aendern(self):
        z = entscheidungen()
        z["benutzer"] = {"hans.alt": {"art": "benutzer", "id": 2},
                         "a.muster": {"art": "historisch", "vorname": "Anton", "nachname": "Muster", "titel": "Dr."},
                         "verwaltung": {"art": "ohne"}, "b.betrachter": {"art": "konto", "rolle": "mitarbeiter"}}
        z["versorger"] = {"1": {"art": "neu", "versorger": "Homecare Nord GmbH (erfunden)", "ansprechpartner": ""},
                          "2": {"art": "kein"}, "3": {"art": "leer"}}
        z["werte"]["katheter"] = {"portkatheter": {"art": "wert", "id": 10}, "broviac 2-lumig": {"art": "neu", "wert": "Broviac"},
                                  "nein": {"art": "leer"}}
        z["werte"]["geschlecht"] = {"m": "d"}
        z["praeparate"]["vitamine"] = {"cernevit": {"art": "bemerkung"}, "soluvit n": {"art": "leer"}}
        z["praeparate"]["medikamente"]["taurolin 2%"] = {"art": "neu", "name": "Taurolock", "konzentration": "",
                                                         "kategorie": "katheterschutz"}
        e = lauf(zuordnung=z)
        self.assertEqual(e.offen, [])
        s = e.saetze
        self.assertEqual({b["benutzername"]: (b["vorname"], b["titel"], b["rolle"], b["historisch"]) for b in s["benutzer"]},
                         {"a.muster": ("Anton", "Dr.", "betrachter", True), "b.betrachter": ("B", "", "mitarbeiter", False)})
        patienten = {p["nummer"]: p for p in s["patienten"]}
        self.assertEqual(patienten[2]["bearbeiter"], {"id": 2})
        self.assertEqual((patienten[1]["versorger"], patienten[1]["ansprechpartner"]),
                         ({"neu": "homecare nord gmbh (erfunden)"}, None))
        self.assertEqual(s["versorger"], [{"schluessel": "homecare nord gmbh (erfunden)", "name": "Homecare Nord GmbH (erfunden)",
                                           "telefon": "0000 111111", "email": "probe@example.org", "notiz": ""}])
        self.assertEqual(s["ansprechpartner"], [])
        self.assertEqual((patienten[7]["versorger"], patienten[7]["kein_versorger"]), (None, False))
        self.assertEqual(patienten[1]["katheter"], {"id": 10})
        self.assertEqual(patienten[2]["katheter"], {"neu": "broviac"})
        self.assertEqual((patienten[5]["katheter"], patienten[5]["kein_katheter"]), (None, False))
        self.assertEqual(patienten[2]["geschlecht"], "d")
        plaene = {p["alt"]: p for p in s["plaene"]}
        self.assertEqual(plaene["1"]["vitamine"], [{"id": 7, "kategorie": "vitamine"}])
        self.assertEqual(plaene["2"]["vitamine"], [])
        self.assertIn("<p><strong>Vitamine (laut Altsystem):</strong> Cernevit</p>", plaene["2"]["bemerkung_extras"])
        self.assertEqual(plaene["1"]["katheterschutz"], {"neu": "katheterschutz|taurolock|", "kategorie": "katheterschutz"})

    def test_ungueltige_zuordnungen_blockieren(self):
        z = entscheidungen()
        z["benutzer"] = {"hans.alt": {"art": "benutzer", "id": 999},
                         "a.muster": {"art": "konto", "benutzername": "e.beispiel", "rolle": "mitarbeiter"},
                         "verwaltung": {"art": "konto", "benutzername": "ver waltung", "rolle": "admin"},
                         "b.betrachter": {"art": "konto", "rolle": "chef"}}
        z["versorger"] = {"1": {"art": "vorhanden", "id": 5}, "3": {"art": "neu", "versorger": ""}}
        z["werte"]["katheter"] = {"zvk": {"art": "wert", "id": 99}}
        z["praeparate"]["amino"] = {"glamin": {"art": "praeparat", "id": 4}}       # Lipid statt Aminosäuren
        z["praeparate"]["medikamente"]["taurolin 2%"] = {"art": "neu", "name": "Taurolock", "kategorie": "vitamine"}
        z["geloeschte"] = {"4": {"art": "abgeschlossen", "anlass": "umgezogen"}, "6": {"art": "abgeschlossen", "anlass": "verstorben", "am": "2099-01-01"}}
        e = lauf(zuordnung=z)
        texte = " | ".join(o["text"] for o in e.offen)
        for erwartet in ("Benutzer „hans.alt“: Der gewählte Benutzer ist im EPM nicht (mehr) vorhanden.",
                         "Den Benutzernamen „e.beispiel“ gibt es im EPM schon",
                         "Benutzer „verwaltung“: Benutzername fehlt oder enthält unzulässige Zeichen",
                         "Benutzer „b.betrachter“: Bitte die Rolle des neuen Kontos wählen.",
                         "Versorger 1: Der gewählte Versorger ist im EPM nicht (mehr) vorhanden.",
                         "Versorger 3: Bitte den Namen des Versorgers angeben",
                         "Katheter „ZVK“: Der gewählte Katheter ist in der Auswahlliste nicht (mehr) vorhanden.",
                         "Aminosäuren „Glamin“: Das gewählte Präparat gehört nicht zur Kategorie „Aminosäuren“.",
                         "Katheterblock / Medikamente „Taurolin 2%“: Bitte die Kategorie des neuen Präparats wählen.",
                         "Gelöschter Patient 4: Bitte den Anlass des Abschlusses wählen.",
                         "Gelöschter Patient 6: Das Abschlussdatum liegt in der Zukunft."):
            self.assertIn(erwartet, texte)

    def test_patientennummern(self):
        t = beispiel()
        p = t["patienten"]["zeilen"]
        p[0][0] = "9001"     # Bereich der Testpatienten
        p[1][0] = "7"        # doppelt (wie Patient 7)
        p[4][0] = "abc"
        e = lauf(tabellen=t, zuordnung=entscheidungen())
        a = {x["schluessel"]: x for x in e.auffaelligkeiten if x["feld"] == "nummer"}
        self.assertEqual(set(a), {"patienten:9001:nummer", "patienten:7:nummer", "patienten:abc:nummer"})
        self.assertTrue(all(x["blockiert"] for x in a.values()))
        self.assertIn("Bereich der Testpatienten", a["patienten:9001:nummer"]["text"])
        self.assertIn("mehrfach", a["patienten:7:nummer"]["text"])

    def test_vorhandener_versorger_und_ansprechpartner(self):
        b = bestand()
        b["versorger"] = [{"id": 40, "name": "Homecare Nord (ERFUNDEN)"}]
        b["ansprechpartner"] = [{"id": 50, "versorger": 40, "name": "frau probe"}]
        e = lauf(zuordnung=entscheidungen(), vorhandenes=b)
        self.assertEqual([v["wirksam"] for v in e.versorger][1:3],
                         [{"art": "vorhanden", "id": 40, "ansprechpartner": "Frau Probe"},
                          {"art": "vorhanden", "id": 40, "ansprechpartner": "Herr Muster"}])
        erika = next(p for p in e.saetze["patienten"] if p["nummer"] == 1)
        self.assertEqual((erika["versorger"], erika["ansprechpartner"]), ({"id": 40}, {"id": 50}))
        self.assertEqual([v["name"] for v in e.saetze["versorger"]], ["Apotheke Süd (erfunden)"])
        self.assertEqual([(a["name"], a["versorger"]) for a in e.saetze["ansprechpartner"]], [("Herr Muster", {"id": 40})])


if __name__ == "__main__":
    unittest.main()


class Pruefbefunde(unittest.TestCase):
    """Fälle aus der unabhängigen Prüfung (02.10.2026): Nichts darf still verloren gehen oder falsch zugeordnet werden."""

    def test_untaugliche_korrektur_bleibt_offen(self):
        t = beispiel()
        t["patienten"]["zeilen"][0][0] = "9500"          # Nummer im Bereich der Testpatienten
        z = entscheidungen()
        z["korrekturen"]["patienten:9500:nummer"] = {"art": "wert", "wert": "2", "alt": "9500"}   # 2 ist vergeben
        e = lauf(tabellen=t, zuordnung=z)
        a = next(x for x in e.auffaelligkeiten if x["schluessel"] == "patienten:9500:nummer")
        self.assertTrue(a["blockiert"])
        self.assertIn("Der eingetragene Wert „2“ behebt das nicht.", a["text"])
        self.assertEqual(a["entscheidung"]["wert"], "2")      # bleibt sichtbar und änderbar
        self.assertIn({"bereich": "auffaelligkeiten", "text": "Es gibt Auffälligkeiten, über die noch entschieden werden muss."}, e.offen)
        self.assertTrue(any(p["stufe"] == "fehler" and p["beispiele"] == ["9500"] for p in e.protokoll))
        # brauchbare Nummer: übernommen, Gewichte und Pläne hängen weiter an der Nummer des Altsystems
        z["korrekturen"]["patienten:9500:nummer"]["wert"] = "8"
        e = lauf(tabellen=t, zuordnung=z)
        self.assertEqual(e.offen, [])
        self.assertIn(8, [p["nummer"] for p in e.saetze["patienten"]])
        # unlesbares Geburtsdatum als Korrektur
        z = entscheidungen()
        z["korrekturen"]["patienten:3:geburtsdatum"] = {"art": "wert", "wert": "irgendwann", "alt": "0000-00-00"}
        e = lauf(zuordnung=z)
        self.assertTrue(next(x for x in e.auffaelligkeiten if x["schluessel"] == "patienten:3:geburtsdatum")["blockiert"])
        self.assertNotEqual(e.offen, [])

    def test_korrigierte_nummer_darf_keinem_anderen_alt_patienten_gehoeren(self):
        t = beispiel()
        t["patienten"]["zeilen"][0][0] = "9500"
        z = entscheidungen()
        del z["geloeschte"]["4"]                           # Patient 4 und 6 sind gelöscht und werden nicht übernommen
        z["korrekturen"]["patienten:9500:nummer"] = {"art": "wert", "wert": "6", "alt": "9500"}
        e = lauf(tabellen=t, zuordnung=z)
        a = next(x for x in e.auffaelligkeiten if x["schluessel"] == "patienten:9500:nummer")
        self.assertTrue(a["blockiert"])
        self.assertIn("gehört im Altsystem einem anderen Patienten", a["text"])

    def test_unlesbare_zahl_als_korrektur_bleibt_offen(self):
        t = beispiel()
        spalten = t["infusionen"]["spalten"]
        e0 = lauf(tabellen=t, zuordnung=entscheidungen())
        feld = next(f for f in next(q for q in e0.quelle["tabellen"] if q["name"] == "infusionen")["felder"] if f["name"] == "natrium")
        i = spalten.index(feld["spalte"])
        t["infusionen"]["zeilen"][0][i] = "ca. 78"
        z = entscheidungen()
        e = lauf(tabellen=t, zuordnung=z)
        a = next(x for x in e.auffaelligkeiten if x["schluessel"] == "infusionen:1:natrium")
        self.assertEqual((a["art"], a["blockiert"], a["standard"]), ("unlesbar", False, "leer"))
        plan = next(p for p in e.saetze["plaene"] if p["alt"] == "1")
        self.assertIn("ca. 78", " ".join(plan["bemerkung_extras"]))     # Standard „leer“: der Altwert steht in der Bemerkung
        z["korrekturen"]["infusionen:1:natrium"] = {"art": "wert", "wert": "78 mmol", "alt": "ca. 78"}
        e = lauf(tabellen=t, zuordnung=z)
        a = next(x for x in e.auffaelligkeiten if x["schluessel"] == "infusionen:1:natrium")
        self.assertTrue(a["blockiert"])
        self.assertNotEqual(e.offen, [])
        z["korrekturen"]["infusionen:1:natrium"]["wert"] = "78"
        e = lauf(tabellen=t, zuordnung=z)
        self.assertEqual(e.offen, [])
        self.assertEqual(next(p for p in e.saetze["plaene"] if p["alt"] == "1")["natrium_mmol"], Decimal("78.0"))
        # bewusst eingetragener, weiter unplausibler Wert gilt (Plausibilität ist ein Hinweis, kein Verbot)
        z["korrekturen"]["gewichte:7:gewicht"] = {"art": "wert", "wert": "300", "alt": "640.0"}
        e = lauf(tabellen=t, zuordnung=z)
        self.assertEqual(e.offen, [])
        self.assertEqual({g["alt"]: g for g in e.saetze["gewichte"]}["7"]["gewicht_kg"], Decimal("300.0"))

    def test_sehr_grosse_zahl_ist_unlesbar_statt_absturz(self):
        for wert in ("1e30", "9" * 40, "1e-40"):
            with self.subTest(wert=wert), self.assertRaises(W.Unlesbar):
                W.zahl(wert)
        t = beispiel()
        t["gewichte"]["zeilen"][0][2] = "1e30"
        e = lauf(tabellen=t, zuordnung=entscheidungen())
        self.assertTrue(any(a["schluessel"] == "gewichte:1:gewicht" and a["art"] == "unlesbar" for a in e.auffaelligkeiten))

    def test_insert_select_haengt_nicht(self):
        beginn = time.monotonic()
        with self.assertRaises(dump.DumpFehler) as f:
            dump.lies(b"CREATE TABLE t (a int, b int, c int, d int, e int);\n"
                      b"INSERT INTO t (a, b, c, d, e) SELECT 1, 2, 3, 4, 5;\n")
        self.assertLess(time.monotonic() - beginn, 2)
        self.assertIn("INSERT nicht lesbar", str(f.exception))
        d = dump.lies(b"CREATE TABLE t (a int, b int);\nINSERT INTO t ( `b` ,a ) VALUES (2,1);\n")
        self.assertEqual(d["tabellen"]["t"]["zeilen"], [["1", "2"]])

    def test_timestamp_spalten_stehen_im_dump_in_utc(self):
        sql = ("/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;\n/*!40103 SET TIME_ZONE='+00:00' */;\n"
               "CREATE TABLE `kontakte` (`ID` int, `text` varchar(50), `lastchange` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,"
               " `angelegt` datetime DEFAULT NULL);\n"
               "INSERT INTO `kontakte` VALUES (1,'Sommer','2023-06-30 22:30:00','2023-06-30 22:30:00'),"
               "(2,'Winter','2023-12-31 23:30:00.250',NULL),(3,'leer','0000-00-00 00:00:00',NULL),(4,'nichts',NULL,NULL);\n"
               "/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;\n").encode()
        d = dump.lies(sql)
        self.assertEqual(d["zeitzone"], "+00:00")
        hinweise = dump.zeitstempel_in_ortszeit(d["tabellen"], d["zeitzone"], "Europe/Berlin")
        z = d["tabellen"]["kontakte"]["zeilen"]
        self.assertEqual(z[0][2], "2023-07-01 00:30:00")           # Sommerzeit: +2 Stunden, anderer Tag
        self.assertEqual(z[0][3], "2023-06-30 22:30:00")           # DATETIME bleibt
        self.assertEqual(z[1][2], "2024-01-01 00:30:00.250")       # Winterzeit: +1 Stunde, anderes Jahr
        self.assertEqual((z[2][2], z[3][2]), ("0000-00-00 00:00:00", None))
        self.assertEqual(len(hinweise), 1)
        self.assertIn("kontakte.lastchange", hinweise[0])
        self.assertIn("2 Zeitpunkte wurden in Ortszeit", hinweise[0])
        # ohne SET TIME_ZONE: nichts umrechnen, aber darauf hinweisen
        d = dump.lies(sql.replace(b"/*!40103 SET TIME_ZONE='+00:00' */;\n", b""))
        self.assertIsNone(d["zeitzone"])
        hinweise = dump.zeitstempel_in_ortszeit(d["tabellen"], d["zeitzone"])
        self.assertEqual(d["tabellen"]["kontakte"]["zeilen"][0][2], "2023-06-30 22:30:00")
        self.assertIn("keine Zeitzone", hinweise[0])
        # phpMyAdmin schreibt die Anweisung ohne Kommentar; der Beispiel-Dump hat keine TIMESTAMP-Spalten
        self.assertEqual(dump.lies(b'SET time_zone = "+00:00";\nCREATE TABLE t (a int);\nINSERT INTO t VALUES (1);')["zeitzone"], "+00:00")
        b = dump.lies(BEISPIEL.read_bytes())
        self.assertEqual(dump.zeitstempel_in_ortszeit(b["tabellen"], b["zeitzone"]), [])

    def test_benutzername_eines_testbenutzers_ist_vergeben(self):
        z = entscheidungen()
        z["benutzer"] = {"a.muster": {"art": "konto", "benutzername": "test", "vorname": "A", "nachname": "Muster",
                                      "titel": "", "rolle": "mitarbeiter"}}
        e = lauf(zuordnung=z)
        zeile = next(b for b in e.benutzer if b["schluessel"] == "a.muster")
        self.assertIn("Testbenutzer", zeile["fehler"])
        self.assertTrue(any(o["bereich"] == "benutzer" for o in e.offen))

    def test_html_links_bilder_und_text_ohne_inhalt(self):
        html, war = W.als_html('<p>Siehe <a href="https://example.org/brief.pdf" target="_blank">Arztbrief</a> und '
                               '<a href="https://example.org">https://example.org</a></p><img src="bilder/port.jpg" alt="Port">')
        self.assertTrue(war)
        self.assertIn("Arztbrief (https://example.org/brief.pdf)", html)
        self.assertEqual(html.count("https://example.org<"), 1)                 # Ziel = Text: nicht doppelt
        self.assertIn("[Bild im Text des Altsystems – nicht übernommen: bilder/port.jpg]", html)
        self.assertNotIn("<img", html)
        self.assertIn("nicht übernommen]", W.als_html('<p><img src="data:image/png;base64,AAAA"></p>')[0])
        self.assertTrue(W.ohne_lesbaren_text("<p>&nbsp;</p><script>alert(1)</script><br>"))
        self.assertFalse(W.ohne_lesbaren_text("<p>Text</p>"))
        t = beispiel()
        t["kontakte"]["zeilen"][0][2] = "<div><script>alert(1)</script></div>"
        e = lauf(tabellen=t, zuordnung=entscheidungen())
        kontakt = next(k for k in e.saetze["kontakte"] if k["alt"] == "1")
        self.assertEqual(kontakt["text"], "<p>&lt;div&gt;&lt;script&gt;alert(1)&lt;/script&gt;&lt;/div&gt;</p>")
        self.assertTrue(any("nur HTML ohne lesbaren Text" in p["text"] and p["beispiele"] == ["1"] for p in e.protokoll))

    def test_zu_lange_namen_werden_nicht_still_gekuerzt(self):
        t = beispiel()
        t["versorger"]["zeilen"][1][1] = "V" * 151
        t["patienten"]["zeilen"][0][19] = "K" * 101
        e = lauf(tabellen=t, zuordnung=entscheidungen())
        self.assertEqual(t["patienten"]["spalten"][19], "katheter")
        texte = " ".join(o["text"] for o in e.offen)
        self.assertIn("höchstens 150 Zeichen", texte)
        self.assertIn("höchstens 100 Zeichen", texte)

    def test_protokoll_nennt_reparierte_zeilen(self):
        e = lauf(zuordnung=entscheidungen())
        p = next(p for p in e.protokoll if p["regel"] == 3 and p["bereich"] == "patienten")
        self.assertEqual(p["beispiele"], ["2"])
        self.assertGreaterEqual(p["anzahl"], 2)
