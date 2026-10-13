"""Aufbau einer Dokumentvorlage aus Blöcken: Prüfung und Startvorlagen (Entwurf 18 · Dokumentvorlagen).

Ein Block ist ein JSON-Objekt ``{"id", "typ", "bezeichnung", "optionen", …}``. Platzhalter stehen als
``{{Feldname}}`` im Text und müssen aus der festen Liste der Art stammen (``felder.FELDER``).
In der Fußzeile stehen zusätzlich ``{Seite}`` und ``{Seiten}``.
"""
import re

from .felder import FELDER, TABELLEN, JeArt, ist_eigen

PLATZHALTER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
ID_MUSTER = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
FARBE = re.compile(r"^#[0-9A-Fa-f]{6}$")

TYPEN = {
    "briefkopf": "Briefkopf",
    "titel": "Titel",
    "text": "Text",
    "zweispaltig": "Zwei Spalten",
    "datenfelder": "Datenfelder",
    "tabelle": "Tabelle",
    "trennlinie": "Trennlinie",
    "leerraum": "Leerraum",
    "unterschrift": "Unterschrift",
    "seitenumbruch": "Seitenumbruch",
    "fusszeile": "Fußzeile",
    "kopfkarte": "Kopfkarte",
    # Text der E-Mail zum Schreiben (F172): steht nicht auf der PDF
    "email": "E-Mail",
}
OPTIONEN = {
    "schrift": {"klein", "normal", "gross"},
    "ausrichtung": {"links", "mitte", "rechts"},
    "fett": bool, "kursiv": bool, "ausblenden_wenn_leer": bool, "nicht_teilen": bool,
    "ueberschrift": bool,  # Bezeichnung als Überschrift über dem Block drucken
    "linie_oben": bool,  # dünne Linie über dem Block (z. B. Freigabevermerk wie „validiert von“ im Laborbefund)
    # neben den vorherigen Block setzen; Wert = Breite dieses Blocks, der vorherige erhält den Rest
    "neben_vorherigem": {"drittel", "haelfte", "zwei_drittel"},
    # Text in 2 oder 3 Spalten setzen, z. B. Ankreuzlisten der Laboranforderungen (RGC-Vorlagen, 13.10.2026)
    "spalten": {2, 3},
}
NEBENEINANDER = {"text", "datenfelder", "tabelle", "unterschrift"}
DARSTELLUNGEN = {"paare", "befund"}
MAX_BLOECKE = 60
# Schreiben mit E-Mail-Text (F172, F173)
class _MitEmail(set):
    def __contains__(self, art):
        return super().__contains__(art) or ist_eigen(art)  # eigene Schreiben (F176) haben ebenfalls eine E-Mail


MIT_EMAIL = _MitEmail({"patientenaufnahme", "terminbestaetigung", "reisebescheinigung", "patientenankuendigung"})
MAX_FELDER = 30
MAX_TEXT = 4000


def platzhalter(text: str) -> list[str]:
    return PLATZHALTER.findall(text or "")


def _text(wert, name, fehler, pflicht=False, laenge=MAX_TEXT):
    if wert is None or wert == "":
        if pflicht:
            fehler.append(f"{name}: bitte ausfüllen.")
        return
    if not isinstance(wert, str):
        fehler.append(f"{name}: Text erwartet.")
    elif len(wert) > laenge:
        fehler.append(f"{name}: höchstens {laenge} Zeichen.")


def _felder_pruefen(art, text, name, fehler):
    erlaubt = FELDER[art]
    for f in platzhalter(text if isinstance(text, str) else ""):
        if f not in erlaubt:
            fehler.append(f"{name}: unbekanntes Datenfeld „{f}“.")


def _eintraege(art, liste, name, fehler):
    if not isinstance(liste, list) or not liste:
        fehler.append(f"{name}: mindestens ein Feld angeben.")
        return
    if len(liste) > MAX_FELDER:
        fehler.append(f"{name}: höchstens {MAX_FELDER} Felder.")
    for i, e in enumerate(liste, 1):
        if not isinstance(e, dict) or set(e) - {"label", "wert"}:
            fehler.append(f"{name}, Feld {i}: nur „label“ und „wert“.")
            continue
        _text(e.get("label"), f"{name}, Feld {i} (Bezeichnung)", fehler, laenge=100)
        _text(e.get("wert"), f"{name}, Feld {i} (Wert)", fehler, pflicht=True, laenge=500)
        _felder_pruefen(art, e.get("wert"), f"{name}, Feld {i}", fehler)


def pruefe_bloecke(art: str, bloecke) -> list[str]:
    """Liefert eine Liste verständlicher Fehlermeldungen (leer = in Ordnung)."""
    if art not in FELDER:
        return ["Unbekannte Vorlagenart."]
    if not isinstance(bloecke, list) or not bloecke:
        return ["Die Vorlage braucht mindestens einen Block."]
    if len(bloecke) > MAX_BLOECKE:
        return [f"Höchstens {MAX_BLOECKE} Blöcke."]
    fehler: list[str] = []
    ids = set()
    zaehler = {"briefkopf": 0, "fusszeile": 0, "email": 0}
    for nr, b in enumerate(bloecke, 1):
        if not isinstance(b, dict):
            fehler.append(f"Block {nr}: ungültig.")
            continue
        typ = b.get("typ")
        name = f"Block {nr} ({b.get('bezeichnung') or TYPEN.get(typ, typ)})"
        if typ not in TYPEN:
            fehler.append(f"{name}: unbekannter Bausteintyp.")
            continue
        if not isinstance(b.get("id"), str) or not ID_MUSTER.match(b["id"]) or b["id"] in ids:
            fehler.append(f"{name}: fehlende oder doppelte Kennung.")
        ids.add(b.get("id"))
        _text(b.get("bezeichnung"), f"{name} (Bezeichnung)", fehler, laenge=160)
        optionen = b.get("optionen", {})
        if not isinstance(optionen, dict):
            fehler.append(f"{name}: Optionen ungültig.")
            optionen = {}
        for k, v in optionen.items():
            regel = OPTIONEN.get(k)
            if regel is None or (regel is bool and not isinstance(v, bool)) or (isinstance(regel, set) and v not in regel):
                fehler.append(f"{name}: Option „{k}“ ungültig.")
        erlaubt = {"id", "typ", "bezeichnung", "optionen"}
        if typ in zaehler:
            zaehler[typ] += 1
        if typ == "briefkopf":
            erlaubt |= {"absender", "linienfarbe", "falzmarken", "mit_linie"}
            for k in ("absender", "falzmarken", "mit_linie"):
                if k in b and not isinstance(b[k], bool):
                    fehler.append(f"{name}: „{k}“ ja oder nein.")
            if "linienfarbe" in b and not (isinstance(b["linienfarbe"], str) and FARBE.match(b["linienfarbe"])):
                fehler.append(f"{name}: Linienfarbe als #RRGGBB angeben.")
        elif typ == "zweispaltig":
            erlaubt |= {"links", "rechts", "rechts_klein"}
            for k in ("links", "rechts"):
                _text(b.get(k), f"{name} ({k})", fehler)
                _felder_pruefen(art, b.get(k), name, fehler)
            if not (b.get("links") or b.get("rechts")):
                fehler.append(f"{name}: mindestens eine Spalte ausfüllen.")
            if "rechts_klein" in b and not isinstance(b["rechts_klein"], bool):
                fehler.append(f"{name}: „rechts_klein“ ja oder nein.")
        elif typ == "titel":
            erlaubt |= {"text", "zusatz_label", "zusatz", "neben_logo"}
            if "neben_logo" in b and not isinstance(b["neben_logo"], bool):
                fehler.append(f"{name}: „neben_logo“ ja oder nein.")
            _text(b.get("text"), f"{name} (Text)", fehler, pflicht=True, laenge=200)
            _text(b.get("zusatz_label"), f"{name} (Zusatz)", fehler, laenge=80)
            _text(b.get("zusatz"), f"{name} (Zusatz)", fehler, laenge=200)
            for feld in ("text", "zusatz"):
                _felder_pruefen(art, b.get(feld), name, fehler)
        elif typ in ("text", "fusszeile"):
            erlaubt |= {"text"} | ({"rechts"} if typ == "fusszeile" else set())
            _text(b.get("text"), f"{name} (Text)", fehler, pflicht=typ == "text")
            _felder_pruefen(art, b.get("text"), name, fehler)
            if typ == "fusszeile":
                _text(b.get("rechts"), f"{name} (rechts)", fehler, laenge=100)
                _felder_pruefen(art, b.get("rechts"), name, fehler)
                if (b.get("text") or "").count("\n") > 7:
                    fehler.append(f"{name}: höchstens 8 Zeilen.")
        elif typ == "kopfkarte":
            # wie der Kopf der Akte in EPM: Name groß, darunter eine Zeile, rechts ein kleiner Text, unten Kennzahlen
            erlaubt |= {"text", "untertitel", "rechts", "felder"}
            _text(b.get("text"), f"{name} (Text)", fehler, pflicht=True, laenge=200)
            _text(b.get("untertitel"), f"{name} (Zeile darunter)", fehler, laenge=300)
            _text(b.get("rechts"), f"{name} (rechts)", fehler, laenge=1000)
            for feld in ("text", "untertitel", "rechts"):
                _felder_pruefen(art, b.get(feld), name, fehler)
            if b.get("felder"):
                _eintraege(art, b.get("felder"), name, fehler)
                if len(b["felder"]) > 8:
                    fehler.append(f"{name}: höchstens 8 Kennzahlen.")
        elif typ == "datenfelder":
            erlaubt |= {"spalten", "felder", "darstellung", "spaltenkoepfe"}
            if b.get("spalten", 2) not in (1, 2, 3, 4, 5, 6):
                fehler.append(f"{name}: 1 bis 6 Spalten.")
            if b.get("darstellung", "paare") not in DARSTELLUNGEN:
                fehler.append(f"{name}: Darstellung „paare“ oder „befund“.")
            if "spaltenkoepfe" in b and not isinstance(b["spaltenkoepfe"], bool):
                fehler.append(f"{name}: „spaltenkoepfe“ ja oder nein.")
            _eintraege(art, b.get("felder"), name, fehler)
        elif typ == "unterschrift":
            erlaubt |= {"felder", "linie"}
            if b.get("felder"):
                _eintraege(art, b.get("felder"), name, fehler)
            _text(b.get("linie"), f"{name} (Linie)", fehler, laenge=200)
        elif typ == "tabelle":
            erlaubt |= {"quelle"}
            if b.get("quelle") not in TABELLEN[art]:
                fehler.append(f"{name}: unbekannte Tabelle. Möglich: {', '.join(TABELLEN[art])}.")
        elif typ == "email":
            erlaubt |= {"betreff", "text"}
            if art not in MIT_EMAIL:
                fehler.append(f"{name}: Eine E-Mail gibt es nur bei den Schreiben.")
            _text(b.get("betreff"), f"{name} (Betreff)", fehler, pflicht=True, laenge=200)
            _text(b.get("text"), f"{name} (Text)", fehler, pflicht=True)
            for feld in ("betreff", "text"):
                _felder_pruefen(art, b.get(feld), name, fehler)
        elif typ == "leerraum":
            erlaubt |= {"hoehe_mm"}
            h = b.get("hoehe_mm", 6)
            if not isinstance(h, int) or isinstance(h, bool) or not 1 <= h <= 100:
                fehler.append(f"{name}: Höhe 1 bis 100 mm.")
        if optionen.get("neben_vorherigem"):
            vorher = bloecke[nr - 2] if nr > 1 and isinstance(bloecke[nr - 2], dict) else None
            if typ not in NEBENEINANDER or vorher is None or vorher.get("typ") not in NEBENEINANDER:
                fehler.append(f"{name}: „neben dem vorherigen Block“ geht nur bei Text, Datenfeldern, Tabellen und "
                              f"Unterschrift, wenn davor ebenfalls ein solcher Block steht.")
        unbekannt = set(b) - erlaubt
        if unbekannt:
            fehler.append(f"{name}: unbekannte Angaben {', '.join(sorted(unbekannt))}.")
    for typ, anzahl in zaehler.items():
        if anzahl > 1:
            fehler.append(f"{TYPEN[typ]} darf höchstens einmal vorkommen.")
    return fehler


# Kopf und Fuß wie fpdf_layout.php des Altsystems: Logo mit orangefarbener Linie, Falzmarken; unten Stiftung,
# Anschrift, Kontakt, Vorstand, Spendenkonto, rechts die Seitenzahl
KOPF = {"absender": False, "linienfarbe": "#EE8D4D", "falzmarken": True}
FUSS = {
    "text": "{{Absender.Name}}\n{{Absender.Straße}} · {{Absender.PLZ_Ort}} · {{Absender.Internet}}\n"
            "Telefon {{Absender.Telefon}} · Fax {{Absender.Fax}} · {{Absender.E-Mail}}\n"
            "Vorstand: Prof. Dr. Markus Masin; Prof. Dr. Till Zech, LL.M.\n"
            "Spendenkonto: DKM Darlehnskasse Münster eG · DE71 4006 0265 0017 8247 00 · BIC GENODEM1DKM",
    "rechts": "{Seite}/{Seiten}",
}

# Bisheriger Text des Freigabevermerks in der Startvorlage (bis 02.10.2026); eine aktive Vorlage, die ihn noch
# unverändert enthält, stellt die Migration 0002 auf {{Plan.Freigabevermerk}} um.
FREIGABEVERMERK_ALT = ("Maschinell erstellt, geprüft und freigegeben von {{Plan.freigegeben_von}} am "
                       "{{Plan.freigegeben_datum}}.")
FREIGABEVERMERK_NEU = "{{Plan.Freigabevermerk}}"

# ------------------------------------------------------------------------------------------------ Datenschutz
# Die drei Startvorlagen folgen im Aufbau dem Gesetz (Datenschutzinformation: die Pflichtangaben nach Art. 13 DSGVO
# in dessen Reihenfolge; Einwilligung: Art. 7 und Art. 9 Abs. 2 Buchst. a DSGVO). Inhalte, die nur die Stiftung
# festlegen kann (Zwecke, Rechtsgrundlage, Empfänger, Aufsichtsbehörde …), stehen als Lücke in [eckigen Klammern].
# Nichts davon ist rechtlich geprüft: Bis ein Mensch die Vorlage bearbeitet und veröffentlicht hat, tragen die
# erzeugten PDFs das Wasserzeichen „ENTWURF“.
HINWEIS_VORLAGE = {
    "id": "hinweis", "typ": "text", "bezeichnung": "Hinweis zur Vorlage – vor dem Veröffentlichen entfernen",
    "text": "Diese Vorlage ist ein Entwurf. Alle Stellen in [eckigen Klammern] sind von der Stiftung auszufüllen; der "
            "gesamte Text ist vor der Verwendung rechtlich zu prüfen (z. B. durch die oder den "
            "Datenschutzbeauftragten). Solange die Vorlage nicht bearbeitet und veröffentlicht ist, tragen die PDFs "
            "das Wasserzeichen „ENTWURF“.",
    "optionen": {"ueberschrift": True, "kursiv": True, "schrift": "klein"},
}
PATIENT_BLOCK = {
    "id": "patient", "typ": "datenfelder", "bezeichnung": "Patientin / Patient", "spalten": 2,
    "optionen": {"ueberschrift": True}, "felder": [
        {"label": "Name", "wert": "{{Patient.Name}}"}, {"label": "Geboren", "wert": "{{Patient.Geburtsdatum}}"},
        {"label": "Anschrift", "wert": "{{Patient.Anschrift}}"}, {"label": "Patienten-Nr.", "wert": "{{Patient.Nummer}}"}],
}


def _abschnitt(kennung, ueberschrift, text):
    return {"id": kennung, "typ": "text", "bezeichnung": ueberschrift, "text": text, "optionen": {"ueberschrift": True}}


DATENSCHUTZINFORMATION = [
    {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
    {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Information zur Verarbeitung Ihrer Daten",
     "zusatz_label": "Stand", "zusatz": "{{Heute}}"},
    HINWEIS_VORLAGE,
    {"id": "einleitung", "typ": "text", "bezeichnung": "Einleitung",
     "text": "Mit diesem Blatt informieren wir Sie nach Art. 13 der Datenschutz-Grundverordnung (DSGVO) darüber, wie "
             "wir Ihre personenbezogenen Daten verarbeiten."},
    _abschnitt("verantwortlich", "1. Wer ist für die Verarbeitung verantwortlich?",
               "{{Absender.Name}}\n{{Absender.Straße}}, {{Absender.PLZ_Ort}}\n"
               "Telefon {{Absender.Telefon}} · {{Absender.E-Mail}}\n\n"
               "Datenschutzbeauftragte/r: [Name und Kontaktdaten eintragen – oder diesen Satz streichen, wenn keine "
               "Benennung erforderlich ist]"),
    _abschnitt("zwecke", "2. Wozu verarbeiten wir Ihre Daten, und auf welcher Rechtsgrundlage?",
               "Zwecke: [eintragen]\n\nRechtsgrundlage: [eintragen]"),
    _abschnitt("empfaenger", "3. Wer erhält Ihre Daten?",
               "[Empfänger oder Kategorien von Empfängern eintragen]"),
    _abschnitt("drittland", "4. Werden Daten in ein Land außerhalb der Europäischen Union übermittelt?",
               "[eintragen: entweder, dass keine Übermittlung stattfindet, oder die Angaben nach Art. 13 Abs. 1 "
               "Buchst. f DSGVO]"),
    _abschnitt("dauer", "5. Wie lange speichern wir Ihre Daten?",
               "Wir bewahren Ihre Akte {{Aufbewahrung.Jahre}} Jahre nach dem Abschluss der Betreuung auf. "
               "[Grundlage dieser Frist eintragen; eintragen, was nach Ablauf geschieht – EPM zeigt abgelaufene "
               "Akten in der Übersicht „Datenschutz“ an, gelöscht wird dort von Hand]"),
    _abschnitt("rechte", "6. Welche Rechte haben Sie?",
               "Sie haben das Recht auf Auskunft über Ihre Daten (Art. 15 DSGVO), auf Berichtigung (Art. 16 DSGVO), "
               "auf Löschung (Art. 17 DSGVO) und auf Einschränkung der Verarbeitung (Art. 18 DSGVO) sowie – soweit "
               "die gesetzlichen Voraussetzungen vorliegen – das Recht auf Datenübertragbarkeit (Art. 20 DSGVO) und "
               "ein Widerspruchsrecht (Art. 21 DSGVO).\n\n"
               "Beruht die Verarbeitung auf Ihrer Einwilligung, können Sie die Einwilligung jederzeit widerrufen. Die "
               "Rechtmäßigkeit der Verarbeitung bis zum Widerruf bleibt davon unberührt (Art. 7 Abs. 3 DSGVO).\n\n"
               "Sie haben das Recht, sich bei einer Datenschutz-Aufsichtsbehörde zu beschweren (Art. 77 DSGVO). "
               "[Zuständige Aufsichtsbehörde mit Anschrift eintragen]"),
    _abschnitt("bereitstellung", "7. Müssen Sie Ihre Daten bereitstellen?",
               "[eintragen: ob die Bereitstellung gesetzlich oder vertraglich vorgeschrieben oder für die Betreuung "
               "erforderlich ist und welche Folgen es hat, wenn Daten nicht bereitgestellt werden – Art. 13 Abs. 2 "
               "Buchst. e DSGVO]"),
    _abschnitt("automatisiert", "8. Automatisierte Entscheidungen",
               "[eintragen: ob eine automatisierte Entscheidungsfindung einschließlich Profiling stattfindet – "
               "Art. 13 Abs. 2 Buchst. f DSGVO]"),
    PATIENT_BLOCK,
    {"id": "erhalten", "typ": "unterschrift", "bezeichnung": "Empfangsbestätigung",
     "linie": "Ort, Datum, Unterschrift – ich habe diese Information erhalten", "optionen": {"nicht_teilen": True}},
    {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
]

EINWILLIGUNG = [
    {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
    {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Einwilligung in die Verarbeitung meiner Daten"},
    HINWEIS_VORLAGE,
    PATIENT_BLOCK,
    _abschnitt("einwilligung", "Einwilligung",
               "Ich willige ein, dass die {{Absender.Name}} meine personenbezogenen Daten einschließlich meiner "
               "Gesundheitsdaten zu folgenden Zwecken verarbeitet:\n[Zwecke eintragen]\n\n"
               "Die Einwilligung umfasst die Weitergabe der dafür erforderlichen Daten an:\n[Empfänger eintragen]"),
    _abschnitt("widerruf", "Freiwilligkeit und Widerruf",
               "Diese Einwilligung ist freiwillig. Ich kann sie jederzeit mit Wirkung für die Zukunft widerrufen. "
               "Die Rechtmäßigkeit der bis zum Widerruf erfolgten Verarbeitung bleibt davon unberührt "
               "(Art. 7 Abs. 3 DSGVO).\n[eintragen: an wen der Widerruf zu richten ist und was er für die Betreuung "
               "bedeutet]"),
    {"id": "information", "typ": "text", "bezeichnung": "Datenschutzinformation",
     "text": "Die „Information zur Verarbeitung Ihrer Daten“ habe ich erhalten."},
    {"id": "unterschrift", "typ": "unterschrift", "bezeichnung": "Unterschrift",
     "linie": "Ort, Datum, Unterschrift Patient/in oder gesetzliche Vertretung", "optionen": {"nicht_teilen": True}},
    {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
]

SCHWEIGEPFLICHTENTBINDUNG = [
    {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
    {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Entbindung von der Schweigepflicht"},
    HINWEIS_VORLAGE,
    PATIENT_BLOCK,
    _abschnitt("erklaerung", "Erklärung",
               "Ich entbinde [Personen bzw. Funktionen bei der {{Absender.Name}} eintragen] von der Schweigepflicht "
               "gegenüber den unten genannten Personen und Stellen, soweit es für [Zweck eintragen] erforderlich ist."),
    {"id": "stellen", "typ": "datenfelder", "bezeichnung": "Personen und Stellen", "spalten": 1,
     "optionen": {"ueberschrift": True}, "felder": [
        {"label": "Versorger", "wert": "{{Versorger.Firma}}"},
        {"label": "Hausarzt", "wert": "{{Patient.Hausarzt}}"},
        {"label": "Bezugspersonen", "wert": "{{Bezugspersonen.Auskunft}}"},
        {"label": "Weitere", "wert": "______________________________________________"}]},
    _abschnitt("widerruf", "Freiwilligkeit und Widerruf",
               "Diese Erklärung ist freiwillig. Ich kann sie jederzeit mit Wirkung für die Zukunft widerrufen.\n"
               "[eintragen: an wen der Widerruf zu richten ist]"),
    {"id": "unterschrift", "typ": "unterschrift", "bezeichnung": "Unterschrift",
     "linie": "Ort, Datum, Unterschrift Patient/in oder gesetzliche Vertretung", "optionen": {"nicht_teilen": True}},
    {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
]

# ------------------------------------------------------------------------------------------------ Schreiben
# Vorlagen von Alice Hessel (09.10.2026, F172/F173). Texte wie in ihren Word-Vorlagen; die Anschrift der Praxis
# Dr. Holtmeier (Ort der Sprechstunden) steht im Text und wird hier gepflegt, wenn sie sich ändert.
ABSENDERZEILE = {"id": "absenderzeile", "typ": "text", "bezeichnung": "Absenderzeile",
                 "text": "{{Absender.Name}} · {{Absender.Straße}} · {{Absender.PLZ_Ort}}", "optionen": {"schrift": "klein"}}
EMPFAENGER_PATIENT = {"id": "empfaenger", "typ": "zweispaltig", "bezeichnung": "Empfänger und Datum",
                      "links": "{{Patient.Anrede}}\n{{Patient.Vorname_Name}}\n{{Patient.Straße}}\n{{Patient.PLZ_Ort}}",
                      "rechts": "{{Heute}}"}
PRAXIS_HOLTMEIER = "Praxis Dr. med. Martin Holtmeier\nHamannplatz 23\n48157 Münster"
UNTERLAGEN = (
    "• Vorname, Name\n"
    "• Anschrift\n"
    "• Telefonnummer (Festnetz/Handy)\n"
    "• E-Mail-Adresse (sofern vorhanden)\n"
    "• Körpergröße und Gewicht (vor und nach Erkrankung)\n"
    "• Bekannte Allergien (z. B. Nickel, Medikamente, Nahrungsmittelunverträglichkeiten)\n"
    "• Name, Adresse, Telefonnummer des Hausarztes\n"
    "• Aktuellste Blutwerte (im Optimalfall nicht älter als 14 Tage):\n"
    "\u2003– Elektrolyte (Magnesium, Kalium, Calcium, Natrium, Phosphat)\n"
    "\u2003– Spurenelemente (Kupfer, Zink, Selen, Mangan, Eisen)\n"
    "\u2003– Transaminasen (GPT, GGT, ALKP, GOT), ggf. Bilirubin gesamt + direkt\n"
    "\u2003– Ferritin, Albumin, CRP, Triglyceride\n"
    "\u2003– Vitamin B1, B2, B6, B12 sowie A, D3, E, K\n"
    "\u2003– Kleines Blutbild inkl. Gerinnung\n"
    "\u2003– Kreatinin, GFR, Harnstoff, Harnsäure\n"
    "• Alle Unterlagen über gestellte Diagnosen und aktuelle Behandlungen oder vorangegangene Operationen "
    "(z. B. Arztbriefe, Krankenhausberichte)\n"
    "• Übersicht über aktuell verordnete Medikamente oder andere medizinische Versorgungen\n"
    "• Übersicht über aktuelle (par-)enterale Ernährung\n"
    "• Auflistung aktueller Symptome und/oder Problematiken (bspw. Auftreten von Krämpfen in den Extremitäten, "
    "Ödembildung, Haarausfall, trockene Haut etc.)"
)
AUFNAHME_EINLEITUNG = (
    "wir bedanken uns schon jetzt für Ihr Vertrauen in die Deutsche Stiftung Krankheitsbedingte Mangelernährung. "
    "Prof. Dr. Masin und sein Team stehen Ihnen im Rahmen Ihrer Behandlung gern beratend zur Seite.\n\n"
    "Damit wir uns einen Überblick über Ihren aktuellen Gesundheitsstatus machen können, benötigen wir vorab "
    "einige Daten und Unterlagen von Ihnen:"
)
AUFNAHME_SCHLUSS = (
    "Die Stiftung unterliegt der EU-Datenschutz-Grundverordnung (DSGVO) vom 25.05.2018. Alle Informationen zum "
    "Datenschutz entnehmen Sie unserer Homepage {{Absender.Internet}}.\n\n"
    "Nach Zusendung bzw. Übermittlung der o. g. Angaben kann Prof. Masin vorab eine ernährungsmedizinische "
    "Beurteilung Ihres persönlichen Falles erstellen. Dem schließt sich dann entweder eine persönliche Vorstellung "
    "in unserer ernährungsmedizinischen Sprechstunde in Münster an oder auch ein Telefonat mit Ihnen, sollte die "
    "Anreise nicht sofort möglich sein. In jedem Fall besprechen wir mit Ihnen gemeinsam das weitere mögliche "
    "Vorgehen.\n\n"
    "Im Rahmen von Fragen, Terminvereinbarungen und Rücksprachen steht Ihnen Frau Hessel montags bis freitags in "
    "der Zeit von 9.00 bis 13.00 Uhr telefonisch unter {{Absender.Telefon}} zur Verfügung. Gern sind wir bereit, "
    "mit Ihrem Hausarzt/Ihrer Hausärztin und anderen mitbehandelnden Ärzten auf Ihren Wunsch hin Kontakt "
    "aufzunehmen."
)
GRUSS_TEAM = "Mit freundlichen Grüßen\n\nIhr Team der Deutschen Stiftung Krankheitsbedingte Mangelernährung"

PATIENTENAUFNAHME = [
    {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
    ABSENDERZEILE, EMPFAENGER_PATIENT,
    {"id": "leerraum", "typ": "leerraum", "bezeichnung": "Abstand", "hoehe_mm": 6},
    {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Patientenaufnahme"},
    {"id": "einleitung", "typ": "text", "bezeichnung": "Einleitung",
     "text": "{{Patient.Briefanrede}},\n\n" + AUFNAHME_EINLEITUNG},
    {"id": "unterlagen", "typ": "text", "bezeichnung": "Benötigte Daten und Unterlagen", "text": UNTERLAGEN},
    {"id": "schluss", "typ": "text", "bezeichnung": "Datenschutz und weiteres Vorgehen", "text": AUFNAHME_SCHLUSS},
    {"id": "gruss", "typ": "text", "bezeichnung": "Gruß", "text": GRUSS_TEAM, "optionen": {"nicht_teilen": True}},
    {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
    {"id": "email", "typ": "email", "bezeichnung": "E-Mail", "betreff": "Ihre Anfrage – benötigte Unterlagen",
     "text": "{{Patient.Briefanrede}},\n\n" + AUFNAHME_EINLEITUNG + "\n\n" + UNTERLAGEN + "\n\n" + AUFNAHME_SCHLUSS
             + "\n\nDiese Übersicht finden Sie auch im Anhang zum Ausdrucken.\n\n" + GRUSS_TEAM},
]

TERMIN_TEXT = ("hiermit bestätigen wir Ihren Termin in der ernährungsmedizinischen Sprechstunde von "
               "Prof. Dr. Markus Masin.")
TERMIN_HINWEIS = (
    "Bitte bringen Sie Ihre Gesundheitskarte (Versichertenkarte Ihrer Krankenkasse) mit. "
    "Eine Überweisung ist nicht notwendig.\n\n"
    "Neue Befunde, Arztbriefe oder Laborwerte, die uns noch nicht vorliegen, bringen Sie bitte ebenfalls mit."
)
TERMIN_ABSAGE = ("Sollten Sie den Termin nicht wahrnehmen können, sagen Sie bitte rechtzeitig ab. Frau Hessel ist "
                 "montags bis freitags von 9.00 bis 13.00 Uhr unter {{Absender.Telefon}} für Sie erreichbar.")

TERMINBESTAETIGUNG = [
    {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
    ABSENDERZEILE, EMPFAENGER_PATIENT,
    {"id": "leerraum", "typ": "leerraum", "bezeichnung": "Abstand", "hoehe_mm": 6},
    {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Terminbestätigung"},
    {"id": "einleitung", "typ": "text", "bezeichnung": "Einleitung",
     "text": "{{Patient.Briefanrede}},\n\n" + TERMIN_TEXT},
    {"id": "termin", "typ": "datenfelder", "bezeichnung": "Ihr Termin", "spalten": 1,
     "optionen": {"ueberschrift": True, "nicht_teilen": True}, "felder": [
        {"label": "Tag", "wert": "{{Termin.Datum}}"}, {"label": "Uhrzeit", "wert": "{{Termin.Uhrzeit}}"},
        {"label": "Ort", "wert": PRAXIS_HOLTMEIER}]},
    {"id": "hinweis", "typ": "text", "bezeichnung": "Bitte mitbringen", "text": TERMIN_HINWEIS,
},
    {"id": "absage", "typ": "text", "bezeichnung": "Absage", "text": TERMIN_ABSAGE},
    {"id": "gruss", "typ": "text", "bezeichnung": "Gruß", "text": GRUSS_TEAM, "optionen": {"nicht_teilen": True}},
    {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
    {"id": "email", "typ": "email", "bezeichnung": "E-Mail",
     "betreff": "Terminbestätigung: ernährungsmedizinische Sprechstunde am {{Termin.Datum}}",
     "text": "{{Patient.Briefanrede}},\n\n" + TERMIN_TEXT + "\n\nTag: {{Termin.Datum}}\nUhrzeit: {{Termin.Uhrzeit}}\n"
             "Ort: " + PRAXIS_HOLTMEIER.replace("\n", ", ") + "\n\n" + TERMIN_HINWEIS + "\n\n" + TERMIN_ABSAGE
             + "\n\n" + GRUSS_TEAM},
]

# Reisebescheinigung im Briefkopf von Dr. Holtmeier (mit seiner Zustimmung, Abstimmung durch Alice Hessel).
# Gehört mit dem ärztlichen Attest des ADAC zusammen: EPM hängt es als zweite Seite an (pdf.reise_attest).
REISEBESCHEINIGUNG = [
    {"id": "kopf", "typ": "zweispaltig", "bezeichnung": "Briefkopf Dr. Holtmeier",
     "links": "Dr. med. Martin Holtmeier\nFacharzt für Allgemeinmedizin\nChirotherapie & Sportmedizin\n"
              "Akademische Lehrpraxis der Westfälischen Wilhelms-Universität Münster",
     "rechts": "Hamannplatz 23\n48157 Münster\nTel.: 0251 249999\nFax: 0251 246182", "rechts_klein": True},
    {"id": "linie", "typ": "trennlinie", "bezeichnung": "Linie"},
    {"id": "absenderzeile", "typ": "text", "bezeichnung": "Absenderzeile",
     "text": "Dr. med. Martin Holtmeier · Hamannplatz 23 · 48157 Münster", "optionen": {"schrift": "klein"}},
    {"id": "empfaenger", "typ": "zweispaltig", "bezeichnung": "Empfänger und Datum",
     "links": "{{Patient.Anrede}}\n{{Patient.Vorname_Name}}\n{{Patient.Straße}}\n{{Patient.PLZ_Ort}}",
     "rechts": "Münster, {{Heute}}"},
    {"id": "leerraum", "typ": "leerraum", "bezeichnung": "Abstand", "hoehe_mm": 4},
    {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Bescheinigung / Certificate"},
    {"id": "deutsch", "typ": "text", "bezeichnung": "Bescheinigung (deutsch)",
     "text": "{{Patient.Anrede}} {{Patient.Vorname_Name}}, geb. {{Patient.Geburtsdatum}}, wohnhaft "
             "{{Patient.Anschrift}}, erhält aufgrund komplexer Grunderkrankungen eine individuell hergestellte "
             "parenterale Ernährungstherapie, die medizinisch indiziert und für die Sicherstellung {{Patient.ihrer}} "
             "lebensnotwendigen Nährstoffversorgung unverzichtbar ist.\n\n"
             "Die Therapie dient der täglichen intravenösen Applikation von Makro- und Mikronährstoffen über einen "
             "zentralvenösen Langzeitkatheter und ist für das Überleben {{Patient.der_Patientin}} essenziell. Eine "
             "kontinuierliche Fortführung der parenteralen Ernährung ist auch während Reisen im In- und Ausland "
             "medizinisch zwingend erforderlich.\n\n"
             "Aus diesem Grund ist die Mitführung der patientenindividuell hergestellten parenteralen "
             "Infusionslösungen sowie der für die Durchführung der Therapie erforderlichen Medizinprodukte und "
             "Verbrauchsmaterialien notwendig.\n\n"
             "Die patientenspezifisch hergestellten Infusionsbeutel sind durchgehend unter Einhaltung der Kühlkette "
             "bei einer Lagertemperatur von 2–8 °C aufzubewahren. Zur sicheren Applikation der Infusionslösung ist "
             "die Verwendung einer speziellen ambulanten Infusionspumpe erforderlich. Darüber hinaus müssen Spül- und "
             "Blocklösungen sowie weiteres steriles Verbrauchsmaterial zur sachgerechten Katheterpflege und zur "
             "Aufrechterhaltung der Katheterfunktion jederzeit mitgeführt werden.",
     "optionen": {"schrift": "klein"}},
    {"id": "englisch", "typ": "text", "bezeichnung": "Certificate (English)",
     "text": "{{Patient.Mrs}} {{Patient.Vorname_Name}}, born {{Patient.Geburtsdatum}}, resident at "
             "{{Patient.Anschrift}}, receives an individually compounded parenteral nutrition therapy due to complex "
             "underlying medical conditions. This therapy is medically indicated and indispensable for maintaining "
             "{{Patient.her}} vital nutritional requirements.\n\n"
             "The treatment consists of the daily intravenous administration of macro- and micronutrients via a "
             "long-term central venous catheter and is essential for the patient's survival. Continuous "
             "administration of parenteral nutrition is medically mandatory, including during domestic and "
             "international travel.\n\n"
             "For this reason, the patient must carry {{Patient.her}} individually compounded parenteral nutrition "
             "bags together with all medical devices and consumable supplies required for the safe administration "
             "of the therapy.\n\n"
             "The patient-specific parenteral nutrition bags must be stored continuously under refrigerated "
             "conditions at a temperature of 2–8 °C (35.6–46.4 °F) to maintain product stability. Administration of "
             "the infusion requires the use of a dedicated ambulatory infusion pump. In addition, catheter flushing "
             "solutions, catheter lock solutions, and other sterile consumable supplies necessary for appropriate "
             "catheter care and maintenance of catheter function must be carried at all times.",
     "optionen": {"schrift": "klein", "kursiv": True}},
    {"id": "gruss", "typ": "text", "bezeichnung": "Gruß", "text": "Mit freundlichen Grüßen",
     "optionen": {"nicht_teilen": True}},
    {"id": "abstand_unterschrift", "typ": "leerraum", "bezeichnung": "Platz für die Unterschriften", "hoehe_mm": 12},
    {"id": "holtmeier", "typ": "text", "bezeichnung": "Unterschrift Dr. Holtmeier",
     "text": "Dr. Martin Holtmeier\nFacharzt für Allgemeinmedizin\nund Chirotherapie",
     "optionen": {"linie_oben": True, "nicht_teilen": True, "schrift": "klein"}},
    {"id": "masin", "typ": "text", "bezeichnung": "Unterschrift Prof. Masin",
     "text": "Prof. Dr. Markus Masin\nKonsiliarius, Vorstand Deutsche Stiftung\nKrankheitsbedingte Mangelernährung",
     "optionen": {"linie_oben": True, "nicht_teilen": True, "schrift": "klein", "neben_vorherigem": "haelfte"}},
    {"id": "email", "typ": "email", "bezeichnung": "E-Mail",
     "betreff": "Ihre Reisebescheinigung für die parenterale Ernährung",
     "text": "{{Patient.Briefanrede}},\n\n"
             "anbei erhalten Sie Ihre Reisebescheinigung (deutsch/englisch) zusammen mit dem ärztlichen Attest für "
             "Medikamente und medizinisches Material (ADAC-Formular). Beide Dokumente gehören zusammen: Bitte drucken "
             "Sie sie aus und führen Sie sie auf Ihrer Reise mit, insbesondere bei der Kontrolle am Flughafen.\n\n"
             "Wir wünschen Ihnen eine gute Reise!\n\n" + GRUSS_TEAM},
]

PATIENTENANKUENDIGUNG = [
    {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
    ABSENDERZEILE,
    {"id": "empfaenger", "typ": "zweispaltig", "bezeichnung": "Empfänger und Datum",
     "links": PRAXIS_HOLTMEIER, "rechts": "{{Heute}}"},
    {"id": "leerraum", "typ": "leerraum", "bezeichnung": "Abstand", "hoehe_mm": 6},
    {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Patientenankündigung Sprechstunde",
     "zusatz": "{{Zeitraum}}"},
    {"id": "einleitung", "typ": "text", "bezeichnung": "Einleitung",
     "text": "Sehr geehrter Dr. Holtmeier, liebes Praxisteam,\n\n"
             "für die kommenden Sprechstunden möchten wir folgende Patienten ankündigen:"},
    {"id": "termine", "typ": "tabelle", "bezeichnung": "Termine", "quelle": "ankuendigung"},
    {"id": "gruss", "typ": "text", "bezeichnung": "Gruß", "text": "Mit freundlichen Grüßen\n\n{{Benutzer.Name}}",
     "optionen": {"nicht_teilen": True}},
    {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
    {"id": "email", "typ": "email", "bezeichnung": "E-Mail", "betreff": "Patientenankündigung Sprechstunde {{Zeitraum}}",
     "text": "Sehr geehrter Dr. Holtmeier, liebes Praxisteam,\n\n"
             "für die kommenden Sprechstunden möchten wir folgende Patienten ankündigen:\n\n{{Termine.Liste}}\n\n"
             "Die Übersicht finden Sie auch im Anhang.\n\nMit freundlichen Grüßen\n\n{{Benutzer.Name}}\n"
             "{{Absender.Name}}\nTelefon {{Absender.Telefon}}"},
]

def eigene_startvorlage(titel: str = "Titel") -> list:
    """Startvorlage eines eigenen Schreibens (F176): Brief an den Patienten mit E-Mail – Text in [eckigen Klammern]."""
    return [
        {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
        ABSENDERZEILE, EMPFAENGER_PATIENT,
        {"id": "leerraum", "typ": "leerraum", "bezeichnung": "Abstand", "hoehe_mm": 6},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": titel[:200] or "Titel"},
        {"id": "inhalt", "typ": "text", "bezeichnung": "Text",
         "text": "{{Patient.Briefanrede}},\n\n[Text des Schreibens]"},
        {"id": "gruss", "typ": "text", "bezeichnung": "Gruß", "text": GRUSS_TEAM, "optionen": {"nicht_teilen": True}},
        {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
        {"id": "email", "typ": "email", "bezeichnung": "E-Mail", "betreff": titel[:200] or "Betreff",
         "text": "{{Patient.Briefanrede}},\n\nanbei erhalten Sie [...].\n\n" + GRUSS_TEAM},
    ]


def _eigene_startvorlage_zu(art):
    from .models import EigenesSchreiben

    e = EigenesSchreiben.objects.filter(schluessel=art).first()
    return eigene_startvorlage(e.name if e else "Titel")


FIRMEN = [
    {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
    {"id": "titel", "typ": "titel", "bezeichnung": "Titel",
     "text": "Einwilligung in den Austausch meiner Daten zwischen DSKM und Regeneration Clinic"},
    HINWEIS_VORLAGE,
    PATIENT_BLOCK,
    _abschnitt("einwilligung", "Einwilligung",
               "Ich werde sowohl von der Deutschen Stiftung Krankheitsbedingte Mangelernährung (DSKM) als auch von der "
               "Regeneration Clinic (RG) betreut. Ich willige ein, dass beide meine Akte gemeinsam führen: Stammdaten, "
               "Kontakte, Gewichte, Termine, Befunde, Infusionspläne, Berichte und Dokumente sind für die "
               "Mitarbeitenden beider Einrichtungen sichtbar, soweit sie für meine Betreuung zuständig sind.\n\n"
               "[Zweck des Austauschs und ggf. Einschränkungen eintragen]"),
    _abschnitt("widerruf", "Freiwilligkeit und Widerruf",
               "Diese Einwilligung ist freiwillig. Ich kann sie jederzeit mit Wirkung für die Zukunft widerrufen; danach "
               "führt nur noch eine der beiden Einrichtungen meine Akte. Die Rechtmäßigkeit der bis zum Widerruf "
               "erfolgten Verarbeitung bleibt davon unberührt (Art. 7 Abs. 3 DSGVO).\n"
               "[eintragen: an wen der Widerruf zu richten ist]"),
    {"id": "unterschrift", "typ": "unterschrift", "bezeichnung": "Unterschrift",
     "linie": "Ort, Datum, Unterschrift Patient/in oder gesetzliche Vertretung", "optionen": {"nicht_teilen": True}},
    {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
]

# Startvorlagen. Patientendatenblatt: Aufbau wie im Entwurf „EPM Oberfläche“ (Dokumentvorlagen).
STARTVORLAGEN = {
    "patientenaufnahme": PATIENTENAUFNAHME,
    "terminbestaetigung": TERMINBESTAETIGUNG,
    "reisebescheinigung": REISEBESCHEINIGUNG,
    "patientenankuendigung": PATIENTENANKUENDIGUNG,
    "datenschutzinformation": DATENSCHUTZINFORMATION,
    "einwilligung": EINWILLIGUNG,
    "schweigepflichtentbindung": SCHWEIGEPFLICHTENTBINDUNG,
    "firmen": FIRMEN,
    # Aufbau wie die bisherige PDF des Altsystems (EPM_infuPDF.php mit fpdf_layout.php), moderner gesetzt
    # (Festlegung 01.10.2026); Freigabevermerk statt eingescannter Unterschrift
    "infusionsplan": [
        # Überarbeitung 01.10.2026 im Stil eines Laborbefunds: Werte rechtsbündig mit eigener Einheitenspalte,
        # Bereiche mit Kopfbalken, Kopf wie die Patientenansicht in EPM (Name, Patienten-Nr., Anschrift, Plan-Nr.),
        # Freigabevermerk unten wie „validiert von“. Ohne Linie unter dem Logo (Wunsch, mehr Platz).
        {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF, "mit_linie": False},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Empfehlung eines Infusionsplans",
         "zusatz_label": "gültig ab", "zusatz": "{{Plan.gültig_ab}}", "neben_logo": True},
        {"id": "patient", "typ": "kopfkarte", "bezeichnung": "Patient",
         "text": "{{Patient.Name}}",
         "untertitel": "{{Patient.Geschlecht}} · geb. {{Patient.Geburtsdatum}} ({{Patient.Alter}})\n{{Patient.Anschrift}}",
         "rechts": "Prof. Dr. Markus Masin\nDeutsche Stiftung Krankheitsbedingte Mangelernährung · Vorstand\n"
                   "Medical Institut for Nutrition Science & Technology · Director",
         "felder": [{"label": "Patienten-Nr.", "wert": "{{Patient.Nummer}}"},
                    {"label": "Infusionsplan-Nr.", "wert": "{{Plan.Nummer}}"},
                    {"label": "Größe", "wert": "{{Patient.Größe}}"}, {"label": "Gewicht", "wert": "{{Patient.Gewicht}}"},
                    {"label": "erstellt am", "wert": "{{Plan.erstellt_am}}"},
                    {"label": "erstellt von", "wert": "{{Plan.erstellt_von}}"}]},
        {"id": "zusammensetzung", "typ": "tabelle", "bezeichnung": "Zusammensetzung der Infusionslösung",
         "quelle": "zusammensetzung", "optionen": {"ueberschrift": True}},
        {"id": "mineralstoffe", "typ": "datenfelder", "bezeichnung": "Mineralstoffe", "spalten": 1,
         "darstellung": "befund", "spaltenkoepfe": True,
         "optionen": {"ueberschrift": True, "neben_vorherigem": "drittel"}, "felder": [
            {"label": "Natrium", "wert": "{{Na}}"}, {"label": "Kalium", "wert": "{{K}}"},
            {"label": "Calcium", "wert": "{{Ca}}"}, {"label": "Magnesium", "wert": "{{Mg}}"},
            {"label": "Phosphat", "wert": "{{PO4}}"}]},
        {"id": "inhaltsstoffe", "typ": "datenfelder", "bezeichnung": "Weitere Inhaltsstoffe", "spalten": 1,
         "darstellung": "befund", "optionen": {"ueberschrift": True}, "felder": [
            {"label": "Spurenelemente", "wert": "{{Spurenelemente}}"}, {"label": "Vitamine", "wert": "{{Vitamine}}"},
            {"label": "Medikament zur Blockung", "wert": "{{Katheterblock}}"},
            {"label": "Protonenpumpenhemmer", "wert": "{{Plan.Protonenpumpenhemmer_Anordnung}}"}]},
        # Infusionstage je Beutelart (Wunsch 06.10.2026, F110)
        {"id": "infusionstage", "typ": "datenfelder", "bezeichnung": "Infusionstage", "spalten": 3,
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}, "felder": [
            {"label": "PE (Mischbeutel)", "wert": "{{Plan.Tage_pro_Woche}}"},
            {"label": "Zusatzvolumen", "wert": "{{Plan.Zusatz_pro_Woche}}"},
            {"label": "Infusionsfreie Tage", "wert": "{{Plan.Infusionsfreie_Tage}}"}]},
        {"id": "positionen", "typ": "tabelle", "bezeichnung": "Weitere Bestandteile", "quelle": "positionen",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        # Laufzeit und Laufmenge stehen bei vielen Altplänen auf 0: normale Zeilen, nicht hervorgehoben
        {"id": "laufzeit", "typ": "tabelle", "bezeichnung": "Laufzeit und Volumen", "quelle": "bilanz",
         "optionen": {"ueberschrift": True, "nicht_teilen": True}},
        {"id": "bemerkung", "typ": "text", "bezeichnung": "Weitere Anordnungen/Bemerkungen", "text": "{{Plan.Bemerkung}}",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "diagnose", "typ": "text", "bezeichnung": "Diagnose", "text": "{{Patient.Diagnose}}",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        # Der Vermerk nennt, wer freigegeben hat – und bei einer Freigabe außerhalb von EPM (z. B. per E-Mail) auch den
        # Weg und wer den Plan im System abgeschlossen hat. Beim Entwurf entfällt er.
        {"id": "freigabe", "typ": "text", "bezeichnung": "Freigabevermerk", "text": "{{Plan.Freigabevermerk}}",
         "optionen": {"nicht_teilen": True, "linie_oben": True, "ausblenden_wenn_leer": True}},
        {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
    ],
    "patientendatenblatt": [
        {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Patientendatenblatt",
         "zusatz_label": "Stand", "zusatz": "{{Heute}}"},
        {"id": "person", "typ": "datenfelder", "bezeichnung": "Person", "spalten": 1, "felder": [
            {"label": "Name", "wert": "{{Patient.Name}}"}, {"label": "Nr.", "wert": "{{Patient.Nummer}}"},
            {"label": "Geboren", "wert": "{{Patient.Geburtsdatum}}"}, {"label": "Anschrift", "wert": "{{Patient.Anschrift}}"},
            {"label": "Telefon", "wert": "{{Patient.Telefon}}"}]},
        {"id": "betreuung", "typ": "datenfelder", "bezeichnung": "Betreuung", "spalten": 1, "felder": [
            {"label": "Hausarzt", "wert": "{{Patient.Hausarzt}}"},
            {"label": "Versorger", "wert": "{{Versorger.Firma}} · {{Versorger.Telefon}}"},
            {"label": "Katheter", "wert": "{{Patient.Katheter}}"},
            {"label": "Nickelallergie", "wert": "{{Patient.Nickelallergie}}"}]},
        {"id": "gewicht", "typ": "datenfelder", "bezeichnung": "Gewicht", "spalten": 3, "felder": [
            {"label": "Aktuell", "wert": "{{Gewicht.aktuell}}"}, {"label": "BMI", "wert": "{{Gewicht.BMI}}"},
            {"label": "Trend", "wert": "{{Gewicht.Trend}}"}]},
        {"id": "diagnose", "typ": "datenfelder", "bezeichnung": "Diagnose", "spalten": 1, "felder": [
            {"label": "Diagnose", "wert": "{{Patient.Diagnose}}"}]},
        {"id": "therapie", "typ": "datenfelder", "bezeichnung": "Aktuelle Therapie", "spalten": 1, "felder": [
            {"label": "Aktuelle Therapie", "wert": "{{Patient.Therapie}}"},
            {"label": "Plan", "wert": "{{Plan.kcal}} · {{Plan.ml}} · {{Plan.Stunden}}"}]},
        {"id": "termine", "typ": "tabelle", "bezeichnung": "Nächste Termine", "quelle": "termine"},
        {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
    ],
    # Bericht aus der Akte (Wunsch 06.10.2026, F115): Brief an einen Empfänger, Freigabevermerk statt Unterschrift
    "bericht": [
        {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "{{Bericht.Titel}}",
         "zusatz_label": "vom", "zusatz": "{{Bericht.Datum}}", "neben_logo": True},
        {"id": "patient", "typ": "kopfkarte", "bezeichnung": "Patient", "text": "{{Patient.Name}}",
         "untertitel": "{{Patient.Geschlecht}} · geb. {{Patient.Geburtsdatum}} ({{Patient.Alter}})\n"
                       "{{Patient.Anschrift}}",
         "felder": [{"label": "Patienten-Nr.", "wert": "{{Patient.Nummer}}"},
                    {"label": "Berichtsart", "wert": "{{Bericht.Art}}"},
                    {"label": "Empfänger", "wert": "{{Bericht.Empfänger}}"},
                    {"label": "Versicherung", "wert": "{{Patient.Versicherung}}"}]},
        {"id": "diagnosen", "typ": "tabelle", "bezeichnung": "Diagnosen", "quelle": "diagnosen",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "inhalt", "typ": "text", "bezeichnung": "Bericht", "text": "{{Bericht.Inhalt}}",
         "optionen": {"ueberschrift": True}},
        {"id": "freigabe", "typ": "text", "bezeichnung": "Freigabevermerk", "text": "{{Bericht.Freigabevermerk}}",
         "optionen": {"nicht_teilen": True, "linie_oben": True, "ausblenden_wenn_leer": True}},
        {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
    ],
    # Unterlagen für die Sprechstunde (Wunsch 06.10.2026, F116): der aktuellste Stand aller Bereiche auf einem Blatt
    "sprechstunde": [
        {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF, "mit_linie": False},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Unterlagen für die Sprechstunde",
         "zusatz_label": "Stand", "zusatz": "{{Heute}}", "neben_logo": True},
        {"id": "patient", "typ": "kopfkarte", "bezeichnung": "Patient", "text": "{{Patient.Name}}",
         "untertitel": "{{Patient.Geschlecht}} · geb. {{Patient.Geburtsdatum}} ({{Patient.Alter}})\n"
                       "{{Patient.Anschrift}}",
         "felder": [{"label": "Patienten-Nr.", "wert": "{{Patient.Nummer}}"},
                    {"label": "Größe", "wert": "{{Patient.Größe}}"},
                    {"label": "Gewicht", "wert": "{{Gewicht.aktuell}}"},
                    {"label": "BMI", "wert": "{{Gewicht.BMI}}"},
                    {"label": "Trend", "wert": "{{Gewicht.Trend}}"},
                    {"label": "Versicherung", "wert": "{{Patient.Versicherung}}"}]},
        {"id": "diagnosen", "typ": "tabelle", "bezeichnung": "Diagnosen", "quelle": "diagnosen",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "diagnosetext", "typ": "text", "bezeichnung": "Diagnose (Freitext)", "text": "{{Patient.Diagnose}}",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "plankopf", "typ": "datenfelder", "bezeichnung": "Aktueller Infusionsplan", "spalten": 3,
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}, "felder": [
            {"label": "gültig ab", "wert": "{{Plan.gültig_ab}}"}, {"label": "Energie", "wert": "{{Plan.kcal}}"},
            {"label": "Volumen", "wert": "{{Plan.ml}}"}, {"label": "Laufzeit", "wert": "{{Plan.Stunden}}"},
            {"label": "Rate", "wert": "{{Plan.Rate}}"},
            {"label": "PE pro Woche", "wert": "{{Plan.Tage_pro_Woche}}"},
            {"label": "Zusatzvolumen pro Woche", "wert": "{{Plan.Zusatz_pro_Woche}}"},
            {"label": "Infusionsfreie Tage", "wert": "{{Plan.Infusionsfreie_Tage}}"},
            {"label": "Katheterblock", "wert": "{{Katheterblock}}"}]},
        {"id": "zusammensetzung", "typ": "tabelle", "bezeichnung": "Zusammensetzung", "quelle": "zusammensetzung",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "biastand", "typ": "datenfelder", "bezeichnung": "BIA-Messung", "spalten": 1,
         "optionen": {"ausblenden_wenn_leer": True}, "felder": [
            {"label": "gemessen am", "wert": "{{BIA.Datum}}"}]},
        {"id": "bia", "typ": "tabelle", "bezeichnung": "Letzte BIA-Messung", "quelle": "bia",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "biabeurteilung", "typ": "text", "bezeichnung": "Beurteilung der BIA", "text": "{{BIA.Beurteilung}}",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "laborstand", "typ": "datenfelder", "bezeichnung": "Laborbefund", "spalten": 2,
         "optionen": {"ausblenden_wenn_leer": True}, "felder": [
            {"label": "abgenommen am", "wert": "{{Labor.Datum}}"}, {"label": "Labor", "wert": "{{Labor.Labor}}"}]},
        {"id": "labor", "typ": "tabelle", "bezeichnung": "Letzter Laborbefund", "quelle": "labor",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "laborbeurteilung", "typ": "text", "bezeichnung": "Beurteilung des Labors",
         "text": "{{Labor.Beurteilung}}", "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "empfehlung", "typ": "text", "bezeichnung": "Letzte Empfehlung", "text": "{{Patient.Empfehlung}}",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
    ],
    # Medikamentenplan der Akte (Wunsch 11.10.2026): Aufbau wie der bundeseinheitliche Medikationsplan
    "medikationsplan": [
        {"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", **KOPF, "mit_linie": False},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "Medikationsplan",
         "zusatz_label": "Stand", "zusatz": "{{Heute}}", "neben_logo": True},
        {"id": "patient", "typ": "datenfelder", "bezeichnung": "Patient", "spalten": 3, "felder": [
            {"label": "Name", "wert": "{{Patient.Name}}"}, {"label": "geboren", "wert": "{{Patient.Geburtsdatum}}"},
            {"label": "Patienten-Nr.", "wert": "{{Patient.Nummer}}"}]},
        {"id": "medikamente", "typ": "tabelle", "bezeichnung": "Dauermedikation", "quelle": "medikamente",
         "optionen": {"ueberschrift": True}},
        {"id": "bedarf", "typ": "tabelle", "bezeichnung": "Bedarfsmedikation", "quelle": "bedarfsmedikation",
         "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}},
        {"id": "hinweis", "typ": "text", "bezeichnung": "Hinweis",
         "text": "Mo = morgens, Mi = mittags, Ab = abends, Zn = zur Nacht. Bitte nehmen Sie Ihre Medikamente wie "
                 "angegeben ein und bringen Sie diesen Plan zu jedem Arzt- und Kliniktermin mit. Änderungen nur nach "
                 "Rücksprache mit Ihrer Ärztin oder Ihrem Arzt.",
         "optionen": {"nicht_teilen": True, "linie_oben": True}},
        {"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile", **FUSS},
    ],
}


class _Startvorlagen(JeArt):
    def __missing__(self, art):
        if ist_eigen(art):
            return _eigene_startvorlage_zu(art)
        raise KeyError(art)


STARTVORLAGEN = _Startvorlagen(STARTVORLAGEN, None)
