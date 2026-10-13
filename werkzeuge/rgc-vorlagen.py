#!/usr/bin/env python3
"""Word-Vorlagen der Regeneration Clinic (RGC) in Dokumentvorlagen von EPM umsetzen (13.10.2026).

    python3 werkzeuge/rgc-vorlagen.py ORDNER_MIT_DOCX [ZIEL]

Liest die .docx-Dateien (Laboranforderungen „RC_Vorlage_NN_…“ und Formulare „NN_…“) und schreibt je Vorlage eine
JSON-Datei nach ``backend/vorlagen/statisch/rgc/`` (Name, Beschreibung, Gruppe, Blöcke). Die Datenmigration
``vorlagen/0007_rgc_vorlagen`` legt daraus eigene Schreiben der Firma RGC an. Patientendaten (Name, Geburtsdatum,
Anschrift, Patienten-ID, Versicherung, Diagnosen) werden als Datenfelder eingesetzt; alles andere bleibt zum
Ausfüllen bzw. Ankreuzen von Hand. Fett/kursiv innerhalb eines Absatzes kennt der Textblock nicht – Überschriften werden
zu Block-Überschriften, Kästen zu Karten, Tabellen zu Ankreuzlisten, Datenfeldern oder Unterschriftszeilen.

Braucht ``python-docx``.
"""
import json
import re
import sys
from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

ZIEL = Path(__file__).resolve().parent.parent / "backend" / "vorlagen" / "statisch" / "rgc"
MAX_TEXT = 3800
LINIE = "____________________"
BOX = "☐"
EM = " "  # Abstand vor weiteren Kästchen in einer Zeile (normale Leerzeichen fasst HTML zusammen)

# Name und Gruppe je Datei (Kennung = Dateiname ohne Präfix und Endung)
VORLAGEN = {
    "RC_Vorlage_01_Basislabor": ("Laboranforderung Basislabor", "anforderungen"),
    "RC_Vorlage_02_Gerinnung_Thrombophilie": ("Laboranforderung Gerinnung und Thrombophilie", "anforderungen"),
    "RC_Vorlage_03_Mikronaehrstoffe": ("Laboranforderung Mikronährstoffe", "anforderungen"),
    "RC_Vorlage_04_Endokrinologie": ("Laboranforderung Endokrinologie", "anforderungen"),
    "RC_Vorlage_05_Diabetologie": ("Laboranforderung Diabetologie", "anforderungen"),
    "RC_Vorlage_06_Immunologie": ("Laboranforderung Immunologie", "anforderungen"),
    "RC_Vorlage_07_Allergologie": ("Laboranforderung Allergologie", "anforderungen"),
    "RC_Vorlage_08_Mastzellaktivierung_MCAS": ("Laboranforderung Mastzellaktivierung (MCAS)", "anforderungen"),
    "RC_Vorlage_09_Rheumatologie": ("Laboranforderung Rheumatologie", "anforderungen"),
    "RC_Vorlage_10_Onkologie_Tumormarker": ("Laboranforderung Onkologie und Tumormarker", "anforderungen"),
    "RC_Vorlage_11_MRT-Anforderung": ("MRT-Anforderung", "anforderungen"),
    "RC_Vorlage_12_Roentgen-Anforderung": ("Röntgen-Anforderung", "anforderungen"),
    "RC_Vorlage_13_Echokardiographie": ("Echokardiographie-Anforderung", "anforderungen"),
    "RC_Vorlage_14_EKG-Funktionsdiagnostik": ("EKG und Funktionsdiagnostik", "anforderungen"),
    "06_Schweigepflichtentbindung_allgemein": ("Schweigepflichtentbindung RGC (Versicherungen)", "formulare"),
    "07_Aufklaerung_Operation_Universal_DE-LV": ("Aufklärung Operation (DE/LV)", "formulare"),
    "08_Aufklaerung_Anaesthesie_Universal_DE-LV": ("Aufklärung Anästhesie (DE/LV)", "formulare"),
    "09_Rueckerstattung_Selbstzahler_OEGK": ("Rückerstattung Selbstzahler ÖGK", "formulare"),
    "10_Abtretung_formal_OEGK_mit_Vorauszahlung": ("Abtretung ÖGK mit Vorauszahlung", "formulare"),
}

# Bezeichnung im Formular → Datenfeld (erste passende Regel gilt)
FELDER = [
    (r"patienten-id|pacienta id", "{{Patient.Nummer}}"),
    (r"versicherungs-?nr|versicherungsnummer|versichertennummer", "{{Patient.Versichertennummer}}"),
    (r"versicherung\(en\)|leistungsträger", "{{Patient.Versicherung}}"),
    (r"geburtsdatum", "{{Patient.Geburtsdatum}}"),
    (r"anschrift|adresse", "{{Patient.Anschrift}}"),
    (r"diagnose", "{{Patient.Diagnosen}}"),
    (r"datum / uhrzeit|datums / laiks", "{{Heute}}"),
    (r"name, vorname|^patient", "{{Patient.Name}}"),
    (r"^e-mail", "{{Patient.E-Mail}}"),
    (r"^telefon", "{{Patient.Telefon}}"),
]


def kennung(datei: Path) -> str:
    stamm = re.sub(r"^[0-9a-f]{8}-", "", datei.stem)  # Präfix des Uploads
    stamm = re.sub(r"_V\d+$", "", stamm)
    return re.sub(r"_\d$", "", stamm)  # „…_MCAS_1“


def text_von(p: Paragraph) -> str:
    t = re.sub(r"[ \t ]+", " ", p.text).strip()
    return re.sub(r"(?<=\S) ?☐", f"{EM}{BOX}", t)  # ☐ mitten in der Zeile mit Abstand davor


def _laeufe(p: Paragraph) -> list:
    """Textstücke mit Buchstaben oder Ziffern (Trenner wie „ / “ oder „ · “ sind oft nicht ausgezeichnet)."""
    return [r for r in p.runs if re.search(r"\w", r.text)]


def ist_fett(p: Paragraph) -> bool:
    runs = _laeufe(p)
    return bool(runs) and all(r.bold for r in runs)


def ist_kursiv(p: Paragraph) -> bool:
    runs = _laeufe(p)
    return bool(runs) and all(r.italic for r in runs)


def absaetze(zelle) -> list[Paragraph]:
    return [p for p in zelle.paragraphs if p.text.strip()]


def zelltext(zelle, trenner="\n") -> str:
    return trenner.join(text_von(p) for p in absaetze(zelle))


def zellen(zeile) -> list:
    """Zellen einer Zeile ohne die Wiederholungen verbundener Zellen."""
    ergebnis, gesehen = [], set()
    for z in zeile.cells:
        if id(z._tc) in gesehen:
            continue
        gesehen.add(id(z._tc))
        ergebnis.append(z)
    return ergebnis


def feldwert(label: str, wert: str) -> str:
    if wert and not wert.startswith("_"):
        return wert
    tief = label.lower()
    for muster, feld in FELDER:
        if re.search(muster, tief):
            return feld
    return wert or LINIE


class Bloecke:
    def __init__(self):
        self.liste = []
        self.ueberschrift = None
        self.zeilen: list[str] = []

    def neu(self, typ, **angaben):
        b = {"id": f"b{len(self.liste) + 1}", "typ": typ, **angaben}
        self.liste.append(b)
        return b

    def text(self, text, bezeichnung=None, optionen=None):
        """Textblock; zu lange Texte auf mehrere Blöcke verteilt (je höchstens MAX_TEXT Zeichen)."""
        teile, aktuell = [], ""
        for zeile in text.split("\n"):
            if aktuell and len(aktuell) + len(zeile) + 1 > MAX_TEXT:
                teile.append(aktuell)
                aktuell = zeile
            else:
                aktuell = f"{aktuell}\n{zeile}" if aktuell else zeile
        teile.append(aktuell)
        for i, t in enumerate(teile):
            o = dict(optionen or {})
            angaben = {"text": t or "\n"}
            if bezeichnung and i == 0:
                angaben["bezeichnung"] = bezeichnung
                o["ueberschrift"] = True
            else:
                angaben["bezeichnung"] = (bezeichnung or "Text")[:150] + (" (Fortsetzung)" if i else "")
            if o:
                angaben["optionen"] = o
            self.neu("text", **angaben)

    def abschnitt(self, ueberschrift):
        self.abschluss()
        if len(ueberschrift) > 150:
            self.zeilen.append(ueberschrift)
        else:
            self.ueberschrift = ueberschrift

    def zeile(self, text):
        self.zeilen.append(text)

    def abschluss(self):
        """Offenen Abschnitt als Textblock ausgeben."""
        while self.zeilen and not self.zeilen[-1].strip():
            self.zeilen.pop()
        if self.zeilen:
            self.text(_absatztext(self.zeilen), self.ueberschrift)
        elif self.ueberschrift:
            self.neu("text", bezeichnung=self.ueberschrift[:150], text=self.ueberschrift, optionen={"fett": True})
        self.ueberschrift, self.zeilen = None, []

    def ueberschrift_nehmen(self):
        """Überschrift für einen Block aus einer Tabelle: die des Abschnitts, wenn er noch keinen Text hat."""
        if self.zeilen:
            self.abschluss()
        u, self.ueberschrift = self.ueberschrift, None
        return u


def _absatztext(zeilen: list[str]) -> str:
    """Absätze mit Leerzeile trennen; Aufzählungen, Ankreuz- und Schreiblinien ohne."""
    aus = []
    for z in zeilen:
        eng = re.match(r"^(–|-|•|☐|_{5,})", z) or (aus and re.match(r"^(–|-|•|☐|_{5,})", aus[-1] or ""))
        if aus and not eng:
            aus.append("")
        aus.append(z)
    return "\n".join(aus)


# ---------------------------------------------------------------------------------------------------- Tabellen
def tabelle(b: Bloecke, t: Table, anforderung: bool):
    zeilen = [zellen(z) for z in t.rows]
    texte = [[zelltext(z) for z in zeile] for zeile in zeilen]
    spalten = max(len(z) for z in zeilen)
    alle = [x for zeile in texte for x in zeile]

    # Kopf der Anforderungen: Name, Geburtsdatum, Adresse, Patienten-ID, Datum, Arzt, Station, Dringlichkeit
    if texte and texte[0] and "Uzvārds" in texte[0][0]:
        b.abschluss()
        felder = []
        for x in alle:
            label = re.sub(r"\s*\n\s*", " ", x)
            if "Steidzamība" in label:
                felder.append({"label": "Steidzamība / Dringlichkeit", "wert": f"{BOX} STAT{EM}{BOX} rutīna / Routine"})
            else:
                felder.append({"label": label, "wert": feldwert(label, "")})
        b.neu("datenfelder", bezeichnung="Patient un nosūtījums / Patient und Anforderung", spalten=2, felder=felder)
        return

    # 1×1: Kasten
    if spalten == 1:
        ps = absaetze(zeilen[0][0]) if zeilen[0] else []
        if not ps:  # leerer Kasten: Platz zum Schreiben unter der Überschrift
            u = b.ueberschrift_nehmen()
            b.neu("text", bezeichnung=u or "Notizen", text="\n\n\n", optionen={"ueberschrift": True})
            return
        kopf = text_von(ps[0]) if ist_fett(ps[0]) and len(text_von(ps[0])) <= 150 else None
        rest = [text_von(p) for p in (ps[1:] if kopf else ps)]
        if kopf and not rest:
            if anforderung:  # „Klinische Angaben / Fragestellung“: Platz zum Schreiben
                b.abschluss()
                b.neu("text", bezeichnung=kopf, text="\n\n\n", optionen={"ueberschrift": True})
            else:  # Überschrift im Kasten, Text folgt als Absätze
                b.abschnitt(kopf)
            return
        if kopf:
            b.abschluss()
            b.text(_absatztext(rest), kopf)
            return
        u = b.ueberschrift_nehmen()  # Kasten direkt unter einer Überschrift: als Karte mit dieser Überschrift
        b.text(_absatztext(rest), u, None if u else {"linie_oben": True})
        return

    # Unterschriften: Schreiblinie mit Text darunter
    if any(x.startswith("___") for x in alle) and all(not x or x.startswith("___") for x in alle):
        b.abschluss()
        for zeile in texte:
            erste = True
            for x in zeile:
                if not x:
                    continue
                linie = re.sub(r"^_+\s*", "", x).replace("\n", " ")
                angaben = {"bezeichnung": "Unterschrift", "linie": linie[:200] or "Unterschrift",
                           "optionen": {"nicht_teilen": True}}
                if not erste:
                    angaben["optionen"]["neben_vorherigem"] = "haelfte"
                b.neu("unterschrift", **angaben)
                erste = False
        return

    kopfzeile = all(ist_fett(p) for z in zeilen[0] for p in absaetze(z)) and any(absaetze(z) for z in zeilen[0])
    daten = texte[1:] if kopfzeile else texte
    kopf = texte[0] if kopfzeile else None

    # Spalten nur mit Kästchen (☐): Ankreuzliste
    kaestchen = [i for i in range(spalten) if all(len(z) > i and z[i] in ("☐", "") for z in daten)
                 and any(len(z) > i and z[i] == "☐" for z in daten)]
    if kaestchen:
        u = b.ueberschrift_nehmen()
        aus = []
        for z in daten:
            inhalt = [z[i] for i in range(len(z)) if i not in kaestchen and z[i]]
            if not inhalt:
                continue
            haupt = inhalt[0]
            zusatz = f" — {' — '.join(inhalt[1:])}" if len(inhalt) > 1 else ""
            if len(kaestchen) == 1:
                aus.append(f"{BOX} {haupt}{zusatz}".replace("\n", " / " if anforderung else "\n    "))
            else:
                wahl = EM.join(f"{BOX} {kopf[i] if kopf else ''}".rstrip() for i in kaestchen)
                aus.append(f"{haupt}{zusatz}\n{wahl}\n")
        b.text("\n".join(aus).rstrip(), u)
        return

    # Ankreuzraster (Laboranforderungen): jede Zelle ein Eintrag
    def eintrag(zelle):
        ps = [text_von(p) for p in absaetze(zelle)]
        if not ps:
            return None
        if not ps[0].lstrip(EM).startswith(BOX) and len(ps) > 1:
            return f"{ps[0]}: {' '.join(x.strip(EM) for x in ps[1:])}"
        return " / ".join(ps)

    eintraege = [eintrag(z) for zeile in zeilen for z in zeile]
    eintraege = [e for e in eintraege if e]
    if eintraege and all(BOX in e for e in eintraege) and not kopfzeile:
        u = b.ueberschrift_nehmen()
        optionen = {"spalten": min(spalten, 3)} if spalten > 1 and len(eintraege) > 1 else None
        if u:
            b.text("\n".join(eintraege), u, optionen)
        else:
            b.text("\n".join(eintraege), None, optionen)
        return

    # Bezeichnung – Wert (Patientendaten, Angaben zur Klinik, zur Behandlung)
    if spalten == 2 and all(z and absaetze(z[0]) and all(ist_fett(p) for p in absaetze(z[0])) for z in zeilen) \
            and all(len(t[0]) <= 100 for t in texte):
        u = b.ueberschrift_nehmen()
        felder = [{"label": t[0].replace("\n", " · "), "wert": feldwert(t[0], t[1] if len(t) > 1 else "")[:500]}
                  for t in texte]
        angaben = {"bezeichnung": u or "Angaben", "spalten": 1, "felder": felder}
        if u:
            angaben["optionen"] = {"ueberschrift": True}
        b.neu("datenfelder", **angaben)
        return

    # zweisprachige Listen (links deutsch, rechts lettisch): zwei Spalten nebeneinander
    if spalten == 2 and kopfzeile:
        b.abschluss()
        for i in range(2):
            liste = "\n".join(z[i] for z in daten if len(z) > i and z[i])
            angaben = {"bezeichnung": kopf[i][:150] or "Liste", "text": liste or "\n", "optionen": {"ueberschrift": True}}
            if i:
                angaben["optionen"]["neben_vorherigem"] = "haelfte"
            b.neu("text", **angaben)
        return

    # sonst: Zeile für Zeile
    u = b.ueberschrift_nehmen()
    aus = []
    if kopf:
        aus.append(" — ".join(kopf))
    for z in daten:
        aus.append(" — ".join(x.replace("\n", " ") for x in z if x))
    b.text("\n".join(aus), u)


# ---------------------------------------------------------------------------------------------------- Dokument
def umsetzen(datei: Path) -> dict:
    schluessel = kennung(datei)
    name, gruppe = VORLAGEN[schluessel]
    anforderung = schluessel.startswith("RC_Vorlage")
    d = docx.Document(datei)
    b = Bloecke()
    b.neu("briefkopf", bezeichnung="Briefkopf", absender=anforderung, falzmarken=False)
    elemente = list(d.element.body.iterchildren())

    # Kopf: Titel, Zusatz und Kleingedrucktes bis zur ersten Tabelle bzw. zum ersten normalen Absatz
    titel, zusatz, klein = None, [], []
    i = 0
    while i < len(elemente):
        el = elemente[i]
        if el.tag.endswith("}tbl"):
            break
        p = Paragraph(el, d)
        t = text_von(p)
        if t:
            if titel is None:
                titel = t
            elif ist_fett(p) or ist_kursiv(p):
                zusatz.append(t)
            else:
                klein.append(t)
        i += 1
    zusatz_text = " · ".join(zusatz)
    if len(zusatz_text) > 200:
        klein = zusatz + klein
        zusatz_text = ""
    titel_block = {"bezeichnung": "Titel", "text": titel[:200]}
    if zusatz_text:
        titel_block["zusatz"] = zusatz_text
    b.neu("titel", **titel_block)
    if klein:
        b.neu("text", bezeichnung="Stand der Vorlage", text="\n".join(klein), optionen={"schrift": "klein"})

    for el in elemente[i:]:
        if el.tag.endswith("}tbl"):
            tabelle(b, Table(el, d), anforderung)
            continue
        if not el.tag.endswith("}p"):
            continue
        p = Paragraph(el, d)
        t = text_von(p)
        if not t:
            continue
        if anforderung and ist_kursiv(p) and "ankreuzen" in t:
            b.abschluss()
            b.neu("text", bezeichnung="Hinweis", text=t, optionen={"schrift": "klein", "kursiv": True})
        elif ist_fett(p) and not t.startswith(BOX) and len(t) <= 150:
            b.abschnitt(t)
        else:
            b.zeile(t)
    b.abschluss()

    b.neu("fusszeile", bezeichnung="Fußzeile",
          text="{{Absender.Name}} · {{Absender.Straße}} · {{Absender.PLZ_Ort}}\n"
               "{{Absender.Telefon}} · {{Absender.E-Mail}}\n{{Absender.Fußzeile}}",
          rechts="{Seite}/{Seiten}")
    beschreibung = (zusatz[0] if zusatz else "")
    return {"quelle": schluessel, "name": name, "gruppe": gruppe, "beschreibung": beschreibung[:300],
            "datei": datei.name.split("-", 1)[-1] if re.match(r"^[0-9a-f]{8}-", datei.name) else datei.name,
            "bloecke": b.liste}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ziel = Path(sys.argv[2]) if len(sys.argv) > 2 else ZIEL
    ziel.mkdir(parents=True, exist_ok=True)
    for datei in sorted(Path(sys.argv[1]).glob("*.docx")):
        vorlage = umsetzen(datei)
        aus = ziel / f"{vorlage['quelle']}.json"
        aus.write_text(json.dumps(vorlage, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{aus.name}: {len(vorlage['bloecke'])} Blöcke")


if __name__ == "__main__":
    main()
