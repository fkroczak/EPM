"""Word-Vorlagen der Regeneration Clinic (Vorlagen 01–12, Revision 3, Oktober 2026) → Blöcke einer Dokumentvorlage.

Aufruf (ohne Django):  python rgc_import.py <docx …> [--ziel statisch/rgc]

Die Texte werden wörtlich übernommen; nur der Aufbau wird auf die Bausteine von EPM abgebildet:
- Überschriften (Absatz mit Linie darunter) → Textblock mit Überschrift (Karte), Zwischenüberschriften als Zeile
- Kästen (Tabelle mit einer Zelle) → Textblock mit der ersten Zeile als Überschrift, eingebettete Tabellen → Datenfelder
- Formulartabellen (Bezeichnung | Wert) → Datenfelder; Angaben, die EPM kennt, als Platzhalter ({{Patient.Name}} …)
- Ankreuztabellen (☐) → Textzeilen; Tabellen mit Spaltenköpfen → Datenfelder oder Textzeilen
- Unterschriftstabellen (Linie mit Beschriftung) → Unterschriftsblöcke nebeneinander
Die Ausgabe sind JSON-Dateien ``statisch/rgc/<art>.json`` mit ``{"art", "quelle", "titel", "bloecke"}``.
"""
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Dateiname (Anfang) → Art in EPM
ARTEN = {
    "01_": "rgc_erklaerung_at", "02_": "rgc_erklaerung_gkv", "03_": "rgc_erklaerung_bguv", "04_": "rgc_erklaerung_pkv",
    "05_": "rgc_erklaerung_zusatz", "06_": "rgc_schweigepflicht", "07_": "rgc_aufklaerung_op",
    "08_": "rgc_aufklaerung_anaesthesie", "09_": "rgc_vereinbarung_oegk", "10_": "rgc_abtretung_oegk",
    "11_": "rgc_anlage_k", "12_": "rgc_anwaltsvollmacht",
}
LEER = " "  # leeres Formularfeld (von Hand auszufüllen)
MAX_LABEL, MAX_WERT = 100, 500


# ------------------------------------------------------------------------------------------------ Word lesen
def _text(p) -> str:
    teile = []
    for n in p.iter():
        if n.tag == W + "t":
            teile.append(n.text or "")
        elif n.tag == W + "tab":
            teile.append("  ")
        elif n.tag == W + "br":
            teile.append("\n")
    t = "".join(teile).replace(" ", " ")
    return re.sub(r"[ \t]+\n", "\n", t).strip()


def _fett(p) -> bool:
    runs = [r for r in p.findall(W + "r") if _text(r)]
    if not runs:
        return False
    for r in runs:
        b = r.find(W + "rPr/" + W + "b")
        if b is None or b.get(W + "val") in ("0", "false"):
            return False
    return True


def _ueberschrift(p) -> bool:
    return p.find(W + "pPr/" + W + "pBdr/" + W + "bottom") is not None


class Absatz:
    def __init__(self, p):
        self.text = _text(p)
        self.fett = _fett(p)
        self.ueberschrift = _ueberschrift(p)

    @property
    def art(self) -> str:
        t = self.text
        if re.match(r"^[–•☐]", t):
            return "aufzaehlung"
        if re.fullmatch(r"_{5,}", t):
            return "linie"
        if self.fett and len(t) <= 160:
            return "zwischen"
        return "absatz"


def _zelle(tc) -> list:
    """Inhalt einer Zelle: Absätze und eingebettete Tabellen in Reihenfolge."""
    inhalt = []
    for el in tc:
        if el.tag == W + "p":
            a = Absatz(el)
            if a.text:
                inhalt.append(("p", a))
        elif el.tag == W + "tbl":
            inhalt.append(("tbl", _tabelle(el)))
    return inhalt


def _tabelle(tbl) -> list[list[list]]:
    return [[_zelle(tc) for tc in tr.findall(W + "tc")] for tr in tbl.findall(W + "tr")]


def lies(pfad: Path) -> list:
    z = zipfile.ZipFile(pfad)
    body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    elemente = []
    for el in body:
        if el.tag == W + "p":
            a = Absatz(el)
            if a.text:
                elemente.append(("p", a))
        elif el.tag == W + "tbl":
            elemente.append(("tbl", _tabelle(el)))
    return elemente


# ------------------------------------------------------------------------------------------------ Blöcke bauen
def _zellentext(zelle) -> str:
    return "\n".join(a.text for art, a in zelle if art == "p")


def _zeilen(absaetze: list[Absatz]) -> str:
    """Absätze zu einem Text: Aufzählungen und Formularlinien einzeilig, sonst Leerzeile dazwischen."""
    teile = []
    for i, a in enumerate(absaetze):
        if i:
            vorher = absaetze[i - 1]
            eng = a.art in ("aufzaehlung", "linie") or vorher.art in ("zwischen", "linie") \
                or vorher.text.endswith(":")
            teile.append("\n" if eng else "\n\n")
        teile.append(a.text)
    return "".join(teile)


def _platzhalter(label: str) -> str | None:
    """Angaben, die EPM aus der Akte kennt – sonst von Hand auszufüllen."""
    l = label.lower()
    if "versicherungs-nr" in l and ("träger" in l or "versicherer" in l):
        return "{{Patient.Versicherung}} · {{Patient.Versichertennummer}}"
    if "name" in l and "geburtsdatum" in l:
        return "{{Patient.Name}} · geb. {{Patient.Geburtsdatum}}"
    if l.startswith(("name, vorname", "patient/in", "patient/-in", "vollmachtgeber")) and "name" in l or l.startswith("patient/-in"):
        return "{{Patient.Name}}"
    if l.startswith("geburtsdatum"):
        return "{{Patient.Geburtsdatum}}"
    if l.startswith("anschrift"):
        return "{{Patient.Anschrift}}"
    if l.startswith(("versicherungsnummer", "versicherungs-nr", "versichertennummer", "versicherten-nr")):
        return "{{Patient.Versichertennummer}}"
    if l.startswith(("krankenkasse", "krankenversicherung", "versicherung(en)", "versicherungsträger", "versicherer",
                     "unfallversicherungsträger", "zusatzversicherer")):
        return "{{Patient.Versicherung}}"
    if l.startswith("diagnose"):
        return "{{Patient.Diagnosen}}"
    return None


class Bauer:
    def __init__(self, art: str):
        self.art = art
        self.bloecke: list[dict] = []
        self.nr = 0
        self.heading: str | None = None
        self.heading_benutzt = False
        self.offen: list[Absatz] = []

    def kennung(self, typ: str) -> str:
        self.nr += 1
        return f"{typ}-{self.nr}"

    # --- Textblöcke
    def flush(self):
        if not self.offen:
            return
        absaetze, self.offen = self.offen, []
        text = _zeilen(absaetze)
        if self.heading and not self.heading_benutzt:
            self.heading_benutzt = True
            self.bloecke.append({"id": self.kennung("abschnitt"), "typ": "text", "bezeichnung": self.heading,
                                 "text": text, "optionen": {"ueberschrift": True}})
        elif self.heading:
            self.bloecke.append({"id": self.kennung("abschnitt"), "typ": "text",
                                 "bezeichnung": f"{self.heading} (Fortsetzung)", "text": text})
        else:
            bezeichnung = absaetze[0].text if absaetze[0].art == "zwischen" else "Einleitung" \
                if not any(b["typ"] == "datenfelder" for b in self.bloecke) else "Text"
            self.bloecke.append({"id": self.kennung("text"), "typ": "text", "bezeichnung": bezeichnung[:160],
                                 "text": text})

    def neue_ueberschrift(self, a: Absatz):
        self.flush()
        self.heading, self.heading_benutzt = a.text, False

    def absatz(self, a: Absatz):
        self.offen.append(a)

    def _tabellentitel(self) -> tuple[str, bool]:
        """Bezeichnung einer Tabelle: eine kurze fette Zeile unmittelbar davor, sonst die Überschrift des Abschnitts."""
        if self.offen and self.offen[-1].art == "zwischen":
            titel = self.offen.pop().text
            self.flush()
            return titel, True
        self.flush()
        if self.heading and not self.heading_benutzt:
            self.heading_benutzt = True
            return self.heading, True
        if self.heading is None and not any(b["typ"] == "datenfelder" for b in self.bloecke):
            return "Patientendaten", True
        return (f"{self.heading} – Tabelle" if self.heading else "Tabelle"), False

    # --- Tabellen
    def tabelle(self, zeilen):
        spalten = max(len(z) for z in zeilen)
        if spalten == 1 and len(zeilen) == 1:
            return self.kasten(zeilen[0][0])
        if any(_zellentext(z[0]).startswith("_____") for z in zeilen if z) \
                and all(re.match(r"^_{5,}", _zellentext(c)) for z in zeilen for c in z if _zellentext(c)):
            return self.unterschriften(zeilen)
        titel, ueber = self._tabellentitel()
        if all(_zellentext(c).startswith("☐") for z in zeilen for c in z if _zellentext(c)):
            return self.textblock(titel, "\n".join(_zellentext(c) for z in zeilen for c in z if _zellentext(c)), ueber)
        if spalten == 2 and all(_zellentext(z[0]) == "☐" for z in zeilen):
            text = "\n".join("☐  " + _zellentext(z[1]).replace("\n", "\n     ") for z in zeilen)
            return self.textblock(titel, text, ueber)
        kopf = [_zellentext(c) for c in zeilen[0]]
        koerper = zeilen[1:]
        mit_kopf = spalten >= 3 and all(a.fett for c in zeilen[0] for art, a in c if art == "p") and koerper
        if mit_kopf and all(_zellentext(c) in ("☐", "") for z in koerper for c in z[1:]):
            # Fragebogen: Frage | ☐ Ja | ☐ Nein
            text = "\n".join(_zellentext(z[0]).replace("\n", " · ") + ":  "
                             + "   ".join(f"☐ {k}" for k in kopf[1:]) for z in koerper)
            return self.textblock(titel, text, ueber)
        felder = []
        for z in (koerper if mit_kopf else zeilen):
            label = _zellentext(z[0]).replace("\n", " · ")
            if spalten == 2:
                wert = _zellentext(z[1]) if len(z) > 1 else ""
                wert = wert or _platzhalter(label) or LEER
            else:
                teile = []
                for i, c in enumerate(z[1:], 1):
                    t = _zellentext(c) or LEER
                    k = kopf[i] if mit_kopf and i < len(kopf) and kopf[i] else ""
                    teile.append(f"{k}: {t}" if k and t != LEER else t if not k else f"{k}: {t}")
                wert = "\n".join(teile)
                if mit_kopf and not kopf[0] and len(label) <= 3 and len(z) >= 3:
                    wert = "\n".join([_zellentext(z[1]), *teile[1:]])
            felder.append({"label": label, "wert": wert})
        if felder and all(len(f["label"]) <= MAX_LABEL and len(f["wert"]) <= MAX_WERT for f in felder) \
                and not any(f["label"].startswith(("•", "–")) for f in felder):
            self.bloecke.append({"id": self.kennung("felder"), "typ": "datenfelder", "bezeichnung": titel[:160],
                                 "spalten": 1, "felder": felder, **({"optionen": {"ueberschrift": True}} if ueber else {})})
            return
        # sonst Textzeilen: Zellen mit „ · “ getrennt, zweisprachige Aufzählungen untereinander
        zeilen_text = []
        for z in zeilen:
            zellen = [_zellentext(c) for c in z]
            trenner = "\n" if any(t.startswith(("•", "–")) for t in zellen) else " · "
            zeilen_text.append(trenner.join(t for t in zellen if t))
        self.textblock(titel, "\n".join(zeilen_text), ueber)

    def textblock(self, titel: str, text: str, ueber: bool):
        self.bloecke.append({"id": self.kennung("text"), "typ": "text", "bezeichnung": titel[:160], "text": text,
                             **({"optionen": {"ueberschrift": True}} if ueber else {})})

    def kasten(self, zelle):
        """Hervorgehobener Kasten: erste fette Zeile als Überschrift; eingebettete Tabellen als Datenfelder."""
        self.flush()
        absaetze = [a for art, a in zelle if art == "p"]
        hat_titel = bool(zelle) and zelle[0][0] == "p" and zelle[0][1].fett and len(zelle[0][1].text) <= 160
        rest = list(zelle[1:] if hat_titel else zelle)
        ueber = True
        if hat_titel:
            titel = zelle[0][1].text
        elif self.heading and not self.heading_benutzt:
            titel, self.heading_benutzt = self.heading, True
        else:
            titel, ueber = "Hinweis", False
        erster = True
        offen: list[Absatz] = []

        def schreibe():
            nonlocal erster
            if not offen:
                return
            self.bloecke.append({"id": self.kennung("kasten"), "typ": "text",
                                 "bezeichnung": titel if erster else f"{titel} (Fortsetzung)", "text": _zeilen(offen),
                                 "optionen": {"ueberschrift": True} if erster and ueber else {"kursiv": True}})
            erster = False
            offen.clear()

        for art, inhalt in rest:
            if art == "p":
                offen.append(inhalt)
                continue
            schreibe()
            felder = [{"label": _zellentext(z[0]).replace("\n", " · "), "wert": _zellentext(z[1]) if len(z) > 1 else LEER}
                      for z in inhalt]
            if all(len(f["label"]) <= MAX_LABEL and len(f["wert"]) <= MAX_WERT for f in felder):
                self.bloecke.append({"id": self.kennung("felder"), "typ": "datenfelder", "bezeichnung": titel,
                                     "spalten": 1, "felder": felder,
                                     **({"optionen": {"ueberschrift": True}} if erster and ueber else {})})
            else:
                self.bloecke.append({"id": self.kennung("kasten"), "typ": "text", "bezeichnung": titel,
                                     "text": "\n\n".join(f"{f['label']}: {f['wert']}" for f in felder),
                                     **({"optionen": {"ueberschrift": True}} if erster and ueber else {})})
            erster = False
        schreibe()
        if erster:  # nur ein Titel ohne Inhalt
            self.bloecke.append({"id": self.kennung("kasten"), "typ": "text", "bezeichnung": titel, "text": titel})

    def unterschriften(self, zeilen):
        self.flush()
        for z in zeilen:
            zellen = [c for c in z if _zellentext(c)]
            for i, c in enumerate(zellen):
                beschriftung = " · ".join(a.text for art, a in c if art == "p" and not re.fullmatch(r"_{5,}", a.text))
                block = {"id": self.kennung("unterschrift"), "typ": "unterschrift",
                         "bezeichnung": (beschriftung or "Unterschrift")[:160], "linie": (beschriftung or "Unterschrift")[:160],
                         "optionen": {"nicht_teilen": True}}
                if i:
                    block["optionen"]["neben_vorherigem"] = "haelfte"
                self.bloecke.append(block)


def baue(art: str, elemente: list) -> dict:
    b = Bauer(art)
    # Titelzeilen bis zur ersten Tabelle bzw. Überschrift
    titelzeilen = []
    rest = []
    for i, (typ, inhalt) in enumerate(elemente):
        if typ == "p" and not inhalt.ueberschrift and len(inhalt.text) <= 260 and not rest:
            titelzeilen.append(inhalt.text)
        else:
            rest = elemente[i:]
            break
    vorlage = next((t for t in titelzeilen if t.startswith("Vorlage ")), "")
    m = re.match(r"^(Vorlage \d+ · Version \d+ · Stand [\d/]+)\s*·?\s*(.*)$", vorlage)
    zusatz, nachsatz = (m.group(1), m.group(2)) if m else (vorlage, "")
    untertitel = [t for t in titelzeilen[1:] if t != vorlage] + ([nachsatz] if nachsatz else [])
    b.bloecke.append({"id": "briefkopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", "absender": True,
                      "linienfarbe": "#B9C6C3", "falzmarken": False})
    b.bloecke.append({"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": titelzeilen[0][:200],
                      "zusatz_label": "", "zusatz": zusatz[:200]})
    if untertitel:
        b.bloecke.append({"id": "untertitel", "typ": "text", "bezeichnung": "Untertitel", "text": "\n".join(untertitel),
                          "optionen": {"fett": True, "schrift": "klein"}})
    nr = vorlage.split(" · ")[0] if vorlage else "Vorlage"
    b.bloecke.append({
        "id": "hinweis", "typ": "text", "bezeichnung": "Hinweis zur Vorlage – entfällt nach dem Freigeben",
        "text": f"Diese Vorlage ist aus der Word-Vorlage {zusatz or nr} der Regeneration Clinic SIA übernommen. Angaben "
                "aus der Akte (Name, Geburtsdatum, Anschrift, Versicherung) setzt EPM ein; alle übrigen Felder und "
                "Ankreuzkästchen werden von Hand ausgefüllt. Bis die Vorlage hier einmal geprüft und freigegeben ist, "
                "tragen die PDFs das Wasserzeichen „ENTWURF“.",
        "optionen": {"ueberschrift": True, "kursiv": True, "schrift": "klein"},
    })
    fuss = None
    if rest and rest[-1][0] == "p" and rest[-1][1].text.startswith("Regeneration Clinic SIA · Vorlage"):
        fuss = rest[-1][1].text
        rest = rest[:-1]
    for typ, inhalt in rest:
        if typ == "tbl":
            b.tabelle(inhalt)
        elif inhalt.ueberschrift:
            b.neue_ueberschrift(inhalt)
        else:
            b.absatz(inhalt)
    b.flush()
    b.bloecke.append({"id": "fusszeile", "typ": "fusszeile", "bezeichnung": "Fußzeile",
                      "text": "{{Absender.Name}} · {{Absender.Straße}} · {{Absender.PLZ_Ort}} · {{Absender.E-Mail}}"
                              + (f"\n{fuss}" if fuss else ""),
                      "rechts": "{Seite}/{Seiten}"})
    return {"art": art, "titel": titelzeilen[0], "vorlage": zusatz, "bloecke": b.bloecke}


def main(argv):
    ziel = Path(__file__).resolve().parent / "statisch" / "rgc"
    dateien = []
    i = 0
    while i < len(argv):
        if argv[i] == "--ziel":
            ziel = Path(argv[i + 1])
            i += 2
            continue
        dateien.append(Path(argv[i]))
        i += 1
    ziel.mkdir(parents=True, exist_ok=True)
    for pfad in sorted(dateien):
        nr = re.search(r"(\d\d)_", pfad.name)
        art = ARTEN.get(f"{nr.group(1)}_" if nr else "")
        if art is None:
            print("übersprungen:", pfad.name)
            continue
        daten = baue(art, lies(pfad))
        daten["quelle"] = re.sub(r"^[0-9a-f]{8}-", "", pfad.name)
        (ziel / f"{art}.json").write_text(json.dumps(daten, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{art}: {len(daten['bloecke'])} Blöcke aus {pfad.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
