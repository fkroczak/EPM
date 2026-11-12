"""Werte aus dem erkannten Text: Laborbefund, BIA-Messung, Diagnosen mit ICD-Code, Abschnitte, Datum, Hinweise
auf den Patienten.

Feste Regeln, kein Sprachmodell. Alles ist ein Vorschlag für die Prüfansicht: Nichts wird ohne Bestätigung in eine
Akte geschrieben. Jeder Vorschlag nennt die Stelle (Seite, Lage), an der er gelesen wurde, und wie sicher die
Erkennung dort war.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from . import einheiten as E
from .fusion import UNSICHER

# ---------------------------------------------------------------- Laborparameter: Namen, wie Labore sie schreiben
# Schlüssel = Name im Katalog (normalisiert, siehe ``norm``); Werte = weitere Schreibweisen. Ergänzbar je Parameter
# unter Vorlagen › Labor (Feld „Suchbegriffe“).
SYNONYME = {
    "gpt alt": ["gpt", "alt", "alat", "gpt alat", "alt gpt", "alanin aminotransferase", "alaninaminotransferase", "sgpt"],
    "got ast": ["got", "ast", "asat", "got asat", "ast got", "aspartat aminotransferase", "aspartataminotransferase",
                "sgot"],
    "gamma gt": ["gamma gt", "ggt", "g gt", "y gt", "gammagt", "gamma glutamyltransferase", "gamma gt ggt"],
    "alkp": ["alkp", "ap", "alkalische phosphatase", "alk phosphatase", "alp", "ap alkalische phosphatase"],
    "bilirubin gesamt": ["bilirubin gesamt", "bilirubin ges", "gesamtbilirubin", "bilirubin", "bili ges",
                         "bilirubin total"],
    "bilirubin indirekt": ["bilirubin indirekt", "bilirubin indir", "indirektes bilirubin"],
    "bilirubin direkt": ["bilirubin direkt", "bilirubin dir", "direktes bilirubin", "bilirubin konjugiert"],
    "kreatinin": ["kreatinin", "creatinin", "krea", "crea", "kreatinin serum", "creatinin enzym", "kreatinin enzym"],
    "gfr ckd epi": ["gfr ckd epi", "egfr ckd epi", "egfr", "gfr nach ckd epi", "egfr nach ckd epi", "ckd epi",
                    "gfr berechnet ckd epi", "egfrcrea", "egfr crea", "egfrcrea nach ckd epi",
                    "egfr crea nach ckd epi", "egfrcrea ckd epi", "egfr kreatinin nach ckd epi",
                    "gfr rechn nach ckd epi", "gfr berechn nach ckd epi", "gfr berechnet nach ckd epi",
                    "gfr rechnerisch nach ckd epi", "gfr nach ckd epi formel"],
    "gfr": ["gfr", "glomerulaere filtrationsrate"],
    "harnstoff": ["harnstoff", "urea", "harnstoff n"],
    "harnsaeure": ["harnsaeure", "urat"],
    "cystatin c": ["cystatin c", "cystatin"],
    "eisen": ["eisen", "fe", "eisen serum"],
    "ferritin": ["ferritin"],
    "transferrin": ["transferrin"],
    "transferrinsaettigung": ["transferrinsaettigung", "transferrin saettigung", "tfs", "tsat"],
    "triglyceride": ["triglyceride", "triglyzeride", "tg"],
    "albumin": ["albumin", "alb", "albumin serum"],
    "gesamteiweiss": ["gesamteiweiss", "gesamtprotein", "eiweiss gesamt", "protein gesamt", "ge", "gesamt eiweiss"],
    "crp": ["crp", "c reaktives protein", "crp hochsensitiv", "hs crp"],
    "natrium": ["natrium", "na"],
    "kalium": ["kalium", "k"],
    "calcium": ["calcium", "kalzium", "ca", "calcium gesamt"],
    "magnesium": ["magnesium", "mg"],
    "phosphat": ["phosphat", "phosphor", "anorg phosphat", "anorganisches phosphat", "po4"],
    "chlorid": ["chlorid", "cl"],
    "kupfer": ["kupfer", "cu"],
    "zink": ["zink", "zn"],
    "selen": ["selen", "se"],
    "mangan": ["mangan", "mn"],
    "leukozyten": ["leukozyten", "leukos", "leuko", "wbc"],
    "erythrozyten": ["erythrozyten", "erys", "ery", "rbc"],
    "haemoglobin": ["haemoglobin", "hb", "hgb"],
    "haematokrit": ["haematokrit", "hkt", "hct", "hk"],
    "mcv": ["mcv"],
    "mchc": ["mchc"],
    "mch": ["mch"],
    "thrombozyten": ["thrombozyten", "thrombos", "thrombo", "plt"],
    "lymphozyten": ["lymphozyten", "lympho", "lymphos", "lymphozyten rel"],
    "vitamin a": ["vitamin a", "retinol"],
    "vitamin b1": ["vitamin b1", "thiamin", "vit b1"],
    "vitamin b2": ["vitamin b2", "riboflavin", "vit b2"],
    "vitamin b6": ["vitamin b6", "pyridoxal 5 phosphat", "pyridoxin", "vit b6"],
    "vitamin b12": ["vitamin b12", "vit b12", "cobalamin", "cyanocobalamin", "vitamin b 12"],
    "folsaeure": ["folsaeure", "folat", "folsaeure serum"],
    "vitamin k1": ["vitamin k1", "phyllochinon", "vit k1"],
    "vitamin k2": ["vitamin k2", "vit k2"],
    "vitamin e": ["vitamin e", "tocopherol", "alpha tocopherol"],
    "vitamin d": ["vitamin d"],
    "vitamin d3": ["vitamin d3"],
    "calcidiol 25 hydroxy vitamin d": ["25 oh vitamin d", "25 oh d", "25 hydroxy vitamin d", "25 oh vitamin d3",
                                        "calcidiol", "25 oh d3", "vitamin d 25 oh", "25 hydroxyvitamin d"],
    "calcitriol 1 25 dihydroxy vitamin d": ["1 25 dihydroxy vitamin d", "1 25 oh 2 d", "1 25 oh2 d", "calcitriol",
                                             "1 25 oh 2 vitamin d", "1 25 oh2 vitamin d", "1 25 oh 2 vitamin d3",
                                             "1 25 dihydroxyvitamin d"],
    "parathormon": ["parathormon", "pth", "intaktes parathormon", "ipth", "pth intakt"],
    "amylase": ["amylase", "alpha amylase", "pankreas amylase"],
    "lipase": ["lipase"],
    "c peptid": ["c peptid"],
    "hba1c": ["hba1c", "hb a1c"],
    "glucose": ["glucose", "glukose", "blutzucker", "bz", "glu", "glucose nuechtern"],
    "insulin": ["insulin"],
    "tsh basal": ["tsh", "tsh basal"],
    "ft3": ["ft3", "freies t3"],
    "ft4": ["ft4", "freies t4"],
}

# Schlüssel für Umrechnung und Plausibilität (einheiten.MOLMASSE / PLAUSIBEL) je Katalogname
STOFF = {
    "gpt alt": "gpt", "got ast": "got", "gamma gt": "ggt", "alkp": "ap", "bilirubin gesamt": "bilirubin",
    "bilirubin indirekt": "bilirubin", "bilirubin direkt": "bilirubin", "kreatinin": "kreatinin",
    "harnstoff": "harnstoff", "harnsaeure": "harnsaeure", "eisen": "eisen", "ferritin": "ferritin",
    "transferrin": "transferrin", "transferrinsaettigung": "transferrinsaettigung", "triglyceride": "triglyceride",
    "albumin": "albumin", "gesamteiweiss": "gesamteiweiss", "crp": "crp", "natrium": "natrium", "kalium": "kalium",
    "calcium": "calcium", "magnesium": "magnesium", "phosphat": "phosphat", "chlorid": "chlorid", "kupfer": "kupfer",
    "zink": "zink", "selen": "selen", "mangan": "mangan", "leukozyten": "leukozyten", "erythrozyten": "erythrozyten",
    "haemoglobin": "haemoglobin", "haematokrit": "haematokrit", "mcv": "mcv", "mch": "mch", "mchc": "mchc",
    "thrombozyten": "thrombozyten",
    "vitamin a": "vitamin_a", "vitamin b1": "vitamin_b1", "vitamin b6": "vitamin_b6", "vitamin b12": "vitamin_b12",
    "folsaeure": "folsaeure", "vitamin k1": "vitamin_k1", "vitamin e": "vitamin_e",
    "calcidiol 25 hydroxy vitamin d": "calcidiol", "calcitriol 1 25 dihydroxy vitamin d": "calcitriol",
    "parathormon": "parathormon", "amylase": "amylase", "lipase": "lipase", "hba1c": "hba1c", "glucose": "glucose",
    "tsh basal": "tsh", "ft3": "ft3", "ft4": "ft4",
}

AUSSTEHEND = {"folgt", "s u", "siehe unten", "n b", "nb", "kommt", "in arbeit", "ausstehend"}
TEXTWERTE = {"negativ", "positiv", "neg", "pos", "n b", "nb", "nicht nachweisbar", "nachweisbar", "folgt", "s u",
             "siehe unten", "normal", "unauffaellig", "kein", "keine"}


# ---------------------------------------------------------------- Gelerntes (F182)
# Ab so vielen Bestätigungen gilt eine gelernte Zuordnung als sicher (vorgewählt); darunter nur als Vorschlag
SCHWELLE = 2


@dataclass
class Treffer:
    """Gelernte Zuordnung für eine erkannte Bezeichnung."""

    ziel: str
    ziel_text: str
    bestaetigt: int
    labor: bool          # gilt für diesen Absender (sonst allgemein)
    schwelle: int = SCHWELLE

    @property
    def sicher(self) -> bool:
        return self.bestaetigt >= self.schwelle


@dataclass
class Gelerntes:
    """Gelernte Zuordnungen, wie ``scans.lernen.gelerntes()`` sie aus der Datenbank liest.

    ``eintraege``: (Art, Quelle, Bezeichnung) → [(Ziel, Zieltext, Bestätigungen)], Quelle „“ = allgemein;
    ``gesperrt``: (Art, Quelle, Bezeichnung, Ziel) – „nie wieder so zuordnen“ (Quelle „“ = bei allen Absendern);
    ``spalten``: Quelle → (linke Kante der Wertespalte, Zeichenbreite), nur bestätigte Lagen;
    ``ignorieren``: (Quelle, Bezeichnung) – „falsch erkannt, gehört nicht dazu“ (F189), Quelle „“ = überall;
    ``bereiche``: Quelle → [[x, y, b, h], …] – markierte Bereiche der Werte (F189, liest der OCR-Dienst gezielt nach);
    ``schwelle``: ab so vielen Bestätigungen sicher (Gelernte Zuordnungen › Steuerung, 1–3)."""

    eintraege: dict
    gesperrt: set
    spalten: dict
    ignorieren: set = field(default_factory=set)
    bereiche: dict = field(default_factory=dict)
    schwelle: int = SCHWELLE

    @classmethod
    def leer(cls) -> "Gelerntes":
        return cls({}, set(), {})

    def ist_gesperrt(self, art: str, quelle: str, erkannt: str, ziel) -> bool:
        ziel = str(ziel)
        return (art, "", erkannt, ziel) in self.gesperrt or (bool(quelle) and (art, quelle, erkannt, ziel) in self.gesperrt)

    def _bester(self, art, quelle, erkannt) -> Treffer | None:
        liste = [e for e in self.eintraege.get((art, quelle, erkannt), [])
                 if not self.ist_gesperrt(art, quelle, erkannt, e[0])]
        if not liste:
            return None
        ziel, text, n = max(liste, key=lambda e: e[2])
        return Treffer(ziel, text, n, bool(quelle), self.schwelle)

    def ignoriert(self, quelle: str, erkannt: str) -> bool:
        return bool(erkannt) and ((("", erkannt) in self.ignorieren) or (bool(quelle) and (quelle, erkannt) in self.ignorieren))

    def finden(self, art: str, quelle: str, erkannt: str) -> Treffer | None:
        """Zuerst das für denselben Absender Gelernte, dann das allgemeine; sichere Treffer vor Vorschlägen."""
        if not erkannt:
            return None
        eigen = self._bester(art, quelle, erkannt) if quelle else None
        allgemein = self._bester(art, "", erkannt)
        for t in (eigen, allgemein):
            if t and t.sicher:
                return t
        return eigen or allgemein


def norm(text: str) -> str:
    """Für Vergleiche: klein, Umlaute als ae/oe/ue, ß als ss, γ als g, nur Buchstaben und Ziffern."""
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = (t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss").replace("γ", "g")
         .replace("µ", "u").replace("μ", "u"))
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def abstand(a: str, b: str) -> int:
    """Levenshtein-Abstand (kurze Wörter, einfache Tabelle)."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 3:
        return 99
    vorher = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        jetzt = [i]
        for j, cb in enumerate(b, 1):
            jetzt.append(min(vorher[j] + 1, jetzt[j - 1] + 1, vorher[j - 1] + (ca != cb)))
        vorher = jetzt
    return vorher[-1]


# ---------------------------------------------------------------- Reihen mit Wörtern
@dataclass
class T:
    """Ein Wort der Seite mit Lage (relativ 0–1) und Sicherheit."""

    text: str
    seite: int
    box: tuple
    c: float
    bereich: tuple | None = None   # aus einem markierten Bereich nachgelesen (F189)


def reihen_aus(seiten: list[dict]) -> list[list[T]]:
    """Ergebnis-JSON aller Seiten → Reihen von Wörtern (Seite für Seite, oben nach unten)."""
    aus = []
    for nr, d in enumerate(seiten):
        aus += reihen_der_seite(d, nr)
    return aus


def reihen_der_seite(d: dict, nr: int, bereich=None) -> list[list[T]]:
    b, h = max(d.get("breite") or 1, 1), max(d.get("hoehe") or 1, 1)
    aus = []
    for r in d.get("reihen", []):
        reihe = []
        for s in r:
            for w in s["w"]:
                reihe.append(T(str(w[0]), nr, (w[1] / b, w[2] / h, w[3] / b, w[4] / h), float(w[5]),
                               tuple(bereich) if bereich else None))
        if reihe:
            aus.append(reihe)
    return aus


def _rahmen(ts: list[T]):
    if not ts:
        return None
    x0 = min(t.box[0] for t in ts)
    y0 = min(t.box[1] for t in ts)
    x1 = max(t.box[0] + t.box[2] for t in ts)
    y1 = max(t.box[1] + t.box[3] for t in ts)
    return [round(x0, 4), round(y0, 4), round(x1 - x0, 4), round(y1 - y0, 4)]


def _text(ts: list[T]) -> str:
    return " ".join(t.text for t in ts)


# ---------------------------------------------------------------- Datum
_DATUM = re.compile(r"(?<!\d)(\d{1,2})\s?[.\-/]\s?(\d{1,2})\s?[.\-/]\s?(\d{4}|\d{2})(?!\d)")


def datum_aus(text: str) -> date | None:
    m = _DATUM.search(text)
    if not m:
        return None
    t, mo, j = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if j < 100:
        j += 2000 if j <= (date.today().year % 100) + 1 else 1900
    try:
        return date(j, mo, t)
    except ValueError:
        return None


def alle_daten(text: str) -> list[date]:
    aus = []
    for m in _DATUM.finditer(text):
        d = datum_aus(m.group(0))
        if d:
            aus.append(d)
    return aus


DATUM_SCHLUESSEL = [
    ("abnahme", ["abnahme", "abgenommen", "entnahme", "probenentnahme", "blutentnahme", "entnommen", "abnahmedatum",
                 "entnahmedatum"]),
    ("messung", ["datum der messung", "messdatum", "messung vom", "gemessen am", "untersuchungsdatum"]),
    ("befund", ["befund vom", "befunddatum", "befundet", "ausgang", "druckdatum", "validiert"]),
    ("eingang", ["eingang", "eingangsdatum", "auftragseingang"]),
    ("brief", [" den ", "datum"]),
]


def dokumentdatum(reihen: list[list[T]], heute: date | None = None) -> tuple[date | None, str]:
    """Datum der Abnahme/Messung, sonst des Befunds/Briefs, sonst das erste plausible Datum oben auf Seite 1."""
    heute = heute or date.today()
    gefunden: dict[str, date] = {}
    for r in reihen[:60]:
        zeile = " " + _text(r).lower() + " "
        for art, woerter in DATUM_SCHLUESSEL:
            for wort in woerter:
                pos = zeile.find(wort)
                if pos >= 0:
                    d = datum_aus(zeile[pos:pos + len(wort) + 30])
                    if d and d <= heute and d.year >= 1990 and art not in gefunden:
                        gefunden[art] = d
    for art in ("abnahme", "messung", "befund", "brief", "eingang"):
        if art in gefunden:
            return gefunden[art], art
    for r in reihen[:25]:
        for d in alle_daten(_text(r)):
            if d <= heute and d.year >= 2000:
                return d, "erstes Datum"
    return None, ""


# ---------------------------------------------------------------- Labor
_OP = re.compile(r"^([<>≤≥]=?|<=|>=)$")
_WERT = re.compile(r"^(?P<op>[<>≤≥]=?)?(?P<zahl>[-+]?\d+(?:[.,]\d+)*)(?P<flag>\+\+|--|[HhLl+*↑↓!])?$")
# Zahl mit angehängtem, unbekanntem Zeichen („3,2U“ statt „3,2 L“): Zahl übernehmen, als unsicher markieren
# Pfeil vor dem Wert („↑18.69“, „↓27.7“), von der Erkennung oft als „!“ oder „|“ gelesen – als „1“ siehe _pfeil_als_eins
_PFEIL = re.compile(r"^(?P<pfeil>[↑↓!|ı])(?P<zahl>\d+(?:[.,]\d+)?)$")
_PFEIL_GELESEN = {"1", "11", "17", "71", "t", "T", "f", "!", "|", "I", "l", "ı"}
_ERLAEUTERUNG = re.compile(r"\b(?:mangel|zielwert|praevention|hypervitaminose|insuffizienz|optimal|toxisch|"
                          r"wuenschenswert|grenzwertig|empfohlen|therapeutisch|intoxikation|defizit)\b")
_PFEIL_WORT = {"↑", "↓", "|", "!", "ı"}  # Pfeil als eigenes Wort zwischen Name und Wert
_DATUM_WORT = re.compile(r"^\(?\d{1,2}\.\d{1,2}\.\d{2,4}\)?$")
_WERT_REST = re.compile(r"^(?P<op>[<>≤≥]=?)?(?P<zahl>\d+(?:[.,]\d+)?)(?P<rest>[A-Za-z↑↓*!+|]{1,2})$")
_FLAG = re.compile(r"^(\+\+|--|[HhLl+*↑↓!]|hoch|tief|niedrig)$")
_SPANNE = re.compile(r"(?P<von>\d+(?:[.,]\d+)?)\s*[-–—]\s*(?P<bis>\d+(?:[.,]\d+)?)")
_KLEINER = re.compile(r"(?:^|\s)(?:<|≤|<=|bis|kleiner)\s*(?P<bis>\d+(?:[.,]\d+)?)")
_GROESSER = re.compile(r"(?:^|\s)(?:>|≥|>=|ab|groesser|größer)\s*(?P<von>\d+(?:[.,]\d+)?)")


@dataclass
class Katalogeintrag:
    id: int
    name: str
    einheit: str
    gruppe: str
    begriffe: list[str]
    stoff: str | None


def katalog_index(parameter: list[dict]) -> tuple[dict[str, list[Katalogeintrag]], list[Katalogeintrag]]:
    """Katalog (aktive Laborparameter) → Index normalisierter Begriffe."""
    eintraege, index = [], {}
    for p in parameter:
        n = norm(p["name"])
        begriffe = {n}
        if p.get("kurzname"):
            begriffe.add(norm(p["kurzname"]))
        begriffe.update(SYNONYME.get(n, []))
        for b in re.split(r"[;,\n]", p.get("suchbegriffe") or ""):
            if b.strip():
                begriffe.add(norm(b))
        begriffe.discard("")
        e = Katalogeintrag(p["id"], p["name"], p.get("einheit") or "", p.get("gruppe") or "", sorted(begriffe),
                           STOFF.get(n))
        eintraege.append(e)
        for b in begriffe:
            index.setdefault(b, []).append(e)
    return index, eintraege


def _ist_wert(t: str) -> bool:
    return bool(_WERT.match(t.replace(" ", ""))) or norm(t) in TEXTWERTE


def _suche_parameter(label: str, index, eintraege, gelernt: Gelerntes | None = None,
                     quelle: str = "") -> tuple[Katalogeintrag | None, str, Treffer | None]:
    """→ (Parameter, „gelernt“ | „genau“ | „gelernt_vorschlag“ | „aehnlich“ | „“, gelernte Zuordnung).

    Reihenfolge: sicher Gelerntes (erst für diesen Absender, dann allgemein) → Katalog und Suchbegriffe → gelernter
    Vorschlag → ähnliche Schreibweise. Gesperrte Zuordnungen („nie wieder so“) fallen auf jeder Stufe weg."""
    n = norm(label)
    if not n:
        return None, "", None
    t = gelernt.finden("labor", quelle, n) if gelernt else None
    nach_id = {str(e.id): e for e in eintraege}
    if t is not None and t.ziel not in nach_id:
        t = None  # Parameter inzwischen deaktiviert
    if t is not None and t.sicher:
        return nach_id[t.ziel], "gelernt", t
    p, art = _suche_katalog(label, n, index)
    if p is not None and gelernt and gelernt.ist_gesperrt("labor", quelle, n, p.id):
        p, art = None, ""
    if p is not None and art == "genau":
        return p, art, None
    if t is not None:
        return nach_id[t.ziel], "gelernt_vorschlag", t
    return p, art, None


def _suche_katalog(label: str, n: str, index) -> tuple[Katalogeintrag | None, str]:
    """→ (Parameter, „genau“ | „aehnlich“ | „“) allein aus Katalog, Synonymen und Suchbegriffen."""
    if n in index and len(index[n]) == 1:
        return index[n][0], "genau"
    # ohne Zusätze in Klammern oder am Ende („Kreatinin (enzym.)“, „Albumin i.S.“)
    teile = n.split()
    for k in range(len(teile) - 1, 0, -1):
        kurz = " ".join(teile[:k])
        if kurz in index and len(index[kurz]) == 1 and len(kurz) >= 2:
            # kurze Kürzel („k“, „na“) nur, wenn sie das ganze Etikett sind
            if len(kurz) <= 3 and k < len(teile):
                continue
            return index[kurz][0], "genau"
    bester = _aehnlich(n, index)
    if bester:
        return bester, "aehnlich"
    # Methode in Klammern („MCH (berechnet)“, „CRP (Turbidimetrie)“, „eGFR nach CKD-EPI (2009)“): ohne sie dürfen
    # auch kurze Kürzel treffen; danach ähnliche Schreibweise des Namens allein („Hamoglobin (Photometrie)“)
    ohne = re.sub(r"\([^)]*\)?|\[[^\]]*\]?", " ", label)
    if norm(ohne) and norm(ohne) != n:
        n2 = norm(ohne)
        if n2 in index and len(index[n2]) == 1:
            return index[n2][0], "genau"
        teile = n2.split()
        for k in range(len(teile), 0, -1):
            bester = _aehnlich(" ".join(teile[:k]), index)
            if bester:
                return bester, "aehnlich"
    return None, ""


def _aehnlich(n: str, index) -> Katalogeintrag | None:
    """Katalogbegriff mit höchstens 1–2 Lesefehlern Abstand (nur Begriffe ab 5 Zeichen, eindeutig)."""
    if len(n) < 5:
        return None
    bester, bester_abstand = None, 99
    for begriff, liste in index.items():
        if len(begriff) < 5 or len(liste) != 1:
            continue
        grenze = 1 if len(begriff) < 9 else 2
        a = abstand(n, begriff)
        if a <= grenze and a < bester_abstand:
            bester, bester_abstand = liste[0], a
    return bester


def _referenz(text: str) -> tuple[Decimal | None, Decimal | None]:
    m = _SPANNE.search(text)
    if m:
        return E.zahl(m.group("von")), E.zahl(m.group("bis"))
    m = _KLEINER.search(text)
    if m:
        return None, E.zahl(m.group("bis"))
    m = _GROESSER.search(text)
    if m:
        return E.zahl(m.group("von")), None
    return None, None


def _dez(d: Decimal | None, stellen: int = 4) -> str | None:
    if d is None:
        return None
    q = d.quantize(Decimal(1).scaleb(-stellen)).normalize()
    text = format(q, "f")
    return text


def _wertstelle(r: list[T]) -> int | None:
    """Stelle des Werts in der Reihe: Etikett = Wörter bis zum ersten Wert (Zahl, „< 2,0“, „negativ“)."""
    for i, t in enumerate(r):
        if i == 0:
            continue
        txt = t.text
        if _OP.match(txt) and i + 1 < len(r) and E.zahl(r[i + 1].text.rstrip("HhLl+*↑↓!")) is not None:
            return i
        roh = txt.replace(" ", "")
        if _ist_wert(txt) or _WERT_REST.match(roh) or _PFEIL.match(roh):
            return i
    return None


def _wertspalten(reihen: list[list[T]], gelernt: tuple[float, float] | None = None) -> dict[int, tuple[float, float]]:
    """Je Seite: linke Kante der Wertespalte und Zeichenbreite – nur wenn die Werte linksbündig untereinander stehen.

    Ein Pfeil vor dem Wert („↑18.69“) ragt dann um ein Zeichen nach links heraus; die Erkennung liest ihn oft als
    „1“ („118.69“). Ohne linksbündige Spalte lässt sich das nicht unterscheiden."""
    je_seite: dict[int, list[tuple[float, float]]] = {}
    for r in reihen:
        k = _wertstelle(r) if len(r) >= 2 else None
        if k is None or not re.search(r"[A-Za-zÄÖÜäöü]", _text(r[:k])):
            continue
        t = r[k]
        if not re.fullmatch(r"\d+(?:[.,]\d+)?", t.text) or t.text.startswith("1"):
            continue
        je_seite.setdefault(t.seite, []).append((t.box[0], t.box[2] / max(len(t.text), 1)))
    aus = {}
    for seite, xs in je_seite.items():
        if len(xs) < 4:
            continue
        links = sorted(x for x, _ in xs)[len(xs) // 2]
        zeichen = sorted(z for _, z in xs)[len(xs) // 2]
        if sum(1 for x, _ in xs if abs(x - links) <= 0.35 * zeichen) >= 0.7 * len(xs):
            aus[seite] = (links, zeichen)
    if gelernt:
        # zu wenige Werte auf der Seite: die bestätigte Spaltenlage dieses Absenders (F182)
        for r in reihen:
            if r and r[0].seite not in aus:
                aus[r[0].seite] = gelernt
    return aus


def _pfeil_als_eins(t: T, roh: str, spalten) -> bool:
    """„118.69“, dessen „1“ links aus der Wertespalte ragt: ein als „1“ gelesener Pfeil."""
    if t.seite not in spalten or not re.fullmatch(r"1\d+(?:[.,]\d+)?", roh):
        return False
    links, zeichen = spalten[t.seite]
    eigenes = t.box[2] / len(roh)
    return t.box[0] < links - 0.6 * zeichen and abs(t.box[0] + eigenes - links) <= 0.5 * zeichen


_REF_VORN = re.compile(r"(?:[<>≤≥]=?|<=|>=)\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*[-–—]\s*\d+(?:[.,]\d+)?")
_WERT_HINTEN = re.compile(r"^(?:\d+(?:[.,]\d+)?)(?:\+\+|--|[HhLl+*↑↓!.,-])?$")


def _referenz_vorn(rest: list[T]) -> list[T] | None:
    """Spaltenfolge „Referenzbereich – Einheit – Wert“ („Hämoglobin 7,40 - 10,70 mmol/L 6.50↓“): → die Wörter in der
    üblichen Folge „Wert – Einheit – Referenzbereich“, sonst None.

    Erkannt nur, wenn die Reihe mit einer Spanne oder Grenze beginnt, danach höchstens die Einheit und dann eine
    einfache Zahl folgt (ohne weitere Spanne dahinter). „Natrium 138 mmol/l 135 - 145“ beginnt mit einer Zahl allein
    und bleibt unverändert."""
    n = 0
    for k in (3, 2, 1):
        if k < len(rest) and _REF_VORN.fullmatch(_text(rest[:k]).strip()):
            n = k
            break
    if not n:
        return None
    j = n
    if j < len(rest) and E.einheit(rest[j].text) is not None:
        j += 1
    elif j + 1 < len(rest) and E.einheit(rest[j].text + rest[j + 1].text) is not None:
        j += 2
    if j >= len(rest) or not _WERT_HINTEN.match(rest[j].text.replace(" ", "")):
        return None
    if j + 1 < len(rest) and rest[j + 1].text in "-–—":
        return None  # „0 - 2 /GF 0 - 5“: zwei Spannen, keine Wertespalte hinten
    w = rest[j]
    roh = w.text.replace(" ", "")
    # „6.50.“/„0.33-“: ein als Punkt oder Strich gelesener Pfeil hinten – weglassen
    if roh[-1] in ".,-":
        w = T(roh[:-1], w.seite, w.box, min(w.c, UNSICHER - 0.05), w.bereich)
    return [w, *rest[n:j], *rest[:n], *rest[j + 1:]]


def laborwerte(reihen: list[list[T]], parameter: list[dict], gelernt: Gelerntes | None = None,
               quelle: str = "") -> list[dict]:
    """Zeilen eines Laborbefunds → vorgeschlagene Werte (Parameter aus dem Katalog oder Freitext).

    ``gelernt``/``quelle``: gelernte Zuordnungen (F182) und der normalisierte Absender des Befunds."""
    index, eintraege = katalog_index(parameter)
    spalten = _wertspalten(reihen, gelernt.spalten.get(quelle) if gelernt and quelle else None)
    vorschlaege = []
    for r in reihen:
        if len(r) < 2:
            continue
        k = _wertstelle(r)
        if k is None:
            continue
        etikett = _text(r[:k - 1] if r[k - 1].text in _PFEIL_WORT and k > 1 else r[:k])
        if _ERLAEUTERUNG.search(norm(etikett)):
            continue  # Beurteilungsstufen unter dem Wert, kein eigener Wert
        if gelernt and gelernt.ignoriert(quelle, norm(etikett)):
            continue  # „falsch erkannt – gehört nicht dazu“ (F189)
        if not re.search(r"[A-Za-zÄÖÜäöü]", etikett) or len(etikett) > 60:
            continue
        if alle_daten(etikett) or _DATUM_WORT.match(r[k + 1].text if _OP.match(r[k].text) and k + 1 < len(r)
                                                    else r[k].text):
            continue  # Kopfzeilen mit Datum („Eingang 19.11.2024“); ein Datum beim Vorwert hinten zählt nicht
        param, art, gelernt_treffer = _suche_parameter(etikett, index, eintraege, gelernt, quelle)
        umgestellt = _referenz_vorn(r[k:])
        rest = umgestellt or r[k:]
        # Wert
        op, wert, wert_text, flag = "", None, "", ""
        j = 0
        if _OP.match(rest[0].text) and len(rest) > 1:
            op = rest[0].text
            j = 1
        pfeil = ""
        # Pfeil als eigenes Wort vor dem Wert: „↑ 37,3“ (steht dann am Ende des Etiketts) oder als Zahl gelesen
        # („Ferritin 17 252 µg/l“: eine kurze Zahl, dahinter noch eine Zahl und erst dann die Einheit)
        pfeil_wort = k > 1 and r[k - 1].text in _PFEIL_WORT
        if pfeil_wort:
            pfeil = r[k - 1].text
        elif (not op and rest[j].text in _PFEIL_GELESEN and j + 1 < len(rest) and E.zahl(rest[j + 1].text) is not None
              and (j + 2 >= len(rest) or (E.zahl(rest[j + 2].text) is None and rest[j + 2].text not in "-–—"))):
            # „1 9,7 G/l 4,0 - 9,0“: nicht aber „1 3,5 - 5,1“ (Wert 1, danach der Referenzbereich)
            pfeil = "1"
            j += 1
        wert_wort = rest[j]
        roh = gelesen = rest[j].text.replace(" ", "")
        if pfeil == "1":
            gelesen = f"{rest[j - 1].text} {roh}"
        p = _PFEIL.match(roh)
        if pfeil:
            pass
        elif p:
            pfeil, roh = p.group("pfeil"), p.group("zahl")
        elif _pfeil_als_eins(rest[j], roh, spalten):
            pfeil, roh = "1", roh[1:]
        m = _WERT.match(roh)
        angehaengt = ""
        if not m and param is not None:
            m = _WERT_REST.match(roh)
            if m:
                angehaengt = m.group("rest")
        if m:
            op = op or (m.group("op") or "")
            wert = E.zahl(m.group("zahl"))
            flag = (m.groupdict().get("flag") or "") if not angehaengt else ""
        elif norm(roh) in TEXTWERTE:
            wert_text = rest[j].text
        else:
            continue
        j += 1
        if j < len(rest) and not flag and _FLAG.match(rest[j].text):
            flag = rest[j].text
            j += 1
        # Einheit: das nächste Wort, wenn es eine bekannte Einheit ist (Lesefehler werden repariert)
        einheit_gelesen, einheit_ = "", ""
        ref_vorn = ""
        if j < len(rest):
            e = E.einheit(rest[j].text)
            if e is None and re.search(r"[<>≤≥]$", rest[j].text):
                # „ml/min/1.73qm> 60“: das Zeichen des Referenzbereichs klebt an der Einheit
                e = E.einheit(rest[j].text.rstrip("<>≤≥"))
                if e:
                    ref_vorn = rest[j].text[-1] + " "
            if e is None and j + 1 < len(rest):
                e = E.einheit(rest[j].text + rest[j + 1].text)  # „mmol /l“
                if e:
                    j += 1
            if e is not None:
                einheit_gelesen, einheit_ = rest[j].text, e
                j += 1
        ref_text = ref_vorn + _text(rest[j:])
        ref_von, ref_bis = _referenz(ref_text)
        if param is None and not einheit_:
            continue  # ohne Katalogtreffer nur Zeilen, die eindeutig wie ein Laborwert aussehen
        woerter = r[: k] + rest[: j]
        # Sicherheit des Werts selbst (Einheiten werden ohnehin repariert und geprüft)
        wert_woerter = [t for t in rest[:j] if re.search(r"\d", t.text)] or rest[:1]
        sicher = min(t.c for t in wert_woerter)
        hinweise = []
        if angehaengt:
            sicher = min(sicher, UNSICHER - 0.15)
            hinweise.append(f"gelesen als „{roh}“ – Zahl übernommen, Zusatz „{angehaengt}“ (H/L?) bitte prüfen")
        if pfeil and wert is not None:
            if pfeil in "↑↓":
                flag = flag or pfeil
            elif pfeil_wort:  # eigenes Wort vor dem Wert: Richtung aus dem Referenzbereich, die Zahl selbst ist sicher
                if ref_bis is not None and wert > ref_bis:
                    flag = flag or "↑"
                elif ref_von is not None and wert < ref_von:
                    flag = flag or "↓"
            else:
                if ref_bis is not None and wert > ref_bis:
                    flag = flag or "↑"
                elif ref_von is not None and wert < ref_von:
                    flag = flag or "↓"
                sicher = min(sicher, UNSICHER - 0.05)
                hinweise.append(f"gelesen als „{gelesen}“ – erstes Zeichen als Pfeil (↑/↓) gewertet, bitte prüfen")
        if umgestellt and wert is not None and not flag:
            # Pfeil hinter dem Wert oft als „.“/„-“ gelesen oder verloren: Richtung aus dem Referenzbereich
            flag = "↑" if ref_bis is not None and wert > ref_bis else "↓" if ref_von is not None and wert < ref_von else ""
        if op and wert is not None:
            wert_text, wert = f"{op} {m.group('zahl') if m else _dez(wert)}", None
            hinweise.append("unter bzw. über der Messgrenze – als Text übernommen")
        eintrag = {
            "parameter": param.id if param else None,
            "parameter_name": param.name if param else None,
            "erkannt_als": etikett,
            "zuordnung": art if param else "frei",
            "freitext_name": "" if param else etikett[:150],
            "wert": _dez(wert),
            "wert_text": wert_text[:50],
            "einheit": einheit_ or (param.einheit if param else ""),
            "einheit_gelesen": einheit_gelesen,
            "referenz_von": _dez(ref_von),
            "referenz_bis": _dez(ref_bis),
            "markierung": flag,
            "seite": r[0].seite,
            "box": _rahmen(woerter),
            "zeile": _text(r)[:200],
            "sicherheit": round(sicher, 3),
            "hinweise": hinweise,
            "vorschlag": True,
            # Lage des Werts (für die Spaltenlage je Absender, F182)
            "wert_x": round(wert_wort.box[0], 4),
            # aus einem markierten Bereich nachgelesen (F189): dieser Bereich
            "bereich": list(r[0].bereich) if r[0].bereich else None,
            "wert_zeichen": round(wert_wort.box[2] / max(len(wert_wort.text), 1), 5),
        }
        if art == "gelernt":
            hinweise.append(f"gelernt: so schon {gelernt_treffer.bestaetigt}-mal übernommen"
                            + ("" if gelernt_treffer.labor else " (allgemein)"))
        elif art == "gelernt_vorschlag":
            eintrag["vorschlag"] = False
            hinweise.append(f"gelernt, erst {gelernt_treffer.bestaetigt}-mal bestätigt – bitte prüfen")
        if art == "aehnlich":
            hinweise.append(f"Name ähnlich gelesen: „{etikett}“")
        if sicher < UNSICHER:
            hinweise.append("Erkennung unsicher – bitte mit dem Original vergleichen")
        if param and wert is not None:
            ziel = param.einheit
            # „127.7“ für MCH: unmöglich, ohne die führende „1“ aber plausibel – ein als „1“ gelesener Pfeil
            if not pfeil and m and re.fullmatch(r"1\d+(?:[.,]\d+)?", m.group("zahl")):
                bez = einheit_ or ziel
                ohne = E.zahl(m.group("zahl")[1:])
                if (bez and E.plausibel(param.stoff, wert, bez) is False
                        and E.plausibel(param.stoff, ohne, bez)):
                    wert = ohne
                    eintrag["wert"] = _dez(wert)
                    if not flag:
                        flag = ("↑" if ref_bis is not None and wert > ref_bis
                                else "↓" if ref_von is not None and wert < ref_von else "")
                        eintrag["markierung"] = flag
                    sicher = min(sicher, UNSICHER - 0.05)
                    eintrag["sicherheit"] = round(sicher, 3)
                    hinweise.append(f"gelesen als „{gelesen}“ – unmöglich; erstes Zeichen als Pfeil (↑/↓) gewertet, "
                                    f"bitte prüfen")
            # keine Einheit gelesen und der Wert passt nicht zum Katalog, aber zu einer üblichen anderen Einheit
            geraten = E.einheit_raten(param.stoff, wert, ziel) if not einheit_ and ziel else None
            von = einheit_ or geraten
            if von and ziel and von != ziel:
                f = E.faktor(von, ziel, param.stoff)
                if f is not None:
                    eintrag["umrechnung"] = {"von": von, "faktor": _dez(f, 8), "wert_gelesen": _dez(wert)}
                    wert = wert * f
                    eintrag["wert"] = _dez(wert)
                    eintrag["einheit"] = ziel
                    eintrag["referenz_von"] = _dez(ref_von * f) if ref_von is not None else None
                    eintrag["referenz_bis"] = _dez(ref_bis * f) if ref_bis is not None else None
                    if geraten:
                        hinweise.append(f"keine Einheit gelesen – der Wert passt nur zu {geraten}: umgerechnet in "
                                        f"{ziel}, bitte prüfen")
                    else:
                        hinweise.append(f"umgerechnet von {einheit_} in {ziel}")
                else:
                    hinweise.append(f"Einheit {einheit_} statt {ziel} (Katalog) – nicht umrechenbar, so übernommen")
            elif not einheit_ and ziel:
                hinweise.append(f"keine Einheit gelesen – Einheit des Katalogs ({ziel})")
            p = E.plausibel(param.stoff, wert, eintrag["einheit"])
            if p is False:
                hinweise.append("Wert außerhalb des möglichen Bereichs – vermutlich falsch gelesen")
                eintrag["vorschlag"] = False
        if param is None:
            eintrag["vorschlag"] = False
            hinweise.append("nicht im Katalog – nur auf Wunsch als freier Parameter")
        if sicher < 0.5:
            eintrag["vorschlag"] = False
        if wert is None and norm(wert_text) in AUSSTEHEND:
            eintrag["vorschlag"] = False
            hinweise.append("Ergebnis steht noch aus – nicht vorgewählt")
        vorschlaege.append(eintrag)
    # Steht ein Parameter mehrfach im Befund (z. B. „Eisen (Photometrie)“ in µmol/l und „Eisen (Umrechnung)“ in
    # µg/dl), ist nur eine Zeile vorgewählt: eine brauchbare, möglichst schon in der Einheit des Katalogs.
    je_parameter: dict[int, list[dict]] = {}
    for v in vorschlaege:
        if v["parameter"] is not None:
            je_parameter.setdefault(v["parameter"], []).append(v)
    for liste in je_parameter.values():
        if len(liste) < 2:
            continue
        beste = min(liste, key=lambda v: (not v["vorschlag"], "umrechnung" in v or not v["einheit_gelesen"]))
        for v in liste:
            if v is not beste:
                v["vorschlag"] = False
                v["hinweise"].append("steht mehrfach im Befund – eine andere Zeile ist vorgewählt")
    return vorschlaege


def labor_name(reihen: list[list[T]]) -> str:
    """Absender eines Laborbefunds (erste Zeile oben, die nach Labor/MVZ/Klinik aussieht)."""
    for r in reihen[:8]:
        t = _text(r)
        if re.search(r"\b(labor|mvz|medizinisches versorgungszentrum|klinik|klinikum|krankenhaus|praxis|"
                     r"laboratorium|diagnostik)\b", t, re.I):
            return re.split(r"\s[-–]\s|\t", t)[0][:150].strip()
    return ""


# ---------------------------------------------------------------- BIA
BIA_FELDER = {
    # Bezeichnungen gängiger Geräte und Protokolle (seca mBCA, Data Input/Nutriguard, Akern/Bodygram, InBody, Tanita,
    # RJL, Bodystat, Maltron) – deutsch und englisch, nach norm() (Kleinschrift, Umlaute ausgeschrieben, ohne Zeichen)
    "gewicht_kg": (["koerpergewicht", "gewicht", "aktuelles gewicht", "body weight", "weight", "gewicht kg",
                    "kg gewicht"], ["kg"]),
    "bcm_kg": (["bcm", "koerperzellmasse", "body cell mass", "zellmasse", "koerperzellmasse bcm", "bcm koerperzellmasse",
                "bcm body cell mass", "body cell mass bcm", "zellmasse bcm"], ["kg"]),
    "fettmasse_kg": (["fettmasse", "fm", "koerperfett", "fett", "fat mass", "fettmasse fm", "fm fettmasse",
                      "body fat mass", "bfm", "koerperfettmasse", "fett masse"], ["kg"]),
    "ecw_prozent": (["ecw", "extrazellulaeres wasser", "extrazellulaerwasser", "ecw tbw", "ecw anteil",
                     "anteil ecw", "ecw ratio", "ecw tbw ratio", "extrazellulaeres wasser ecw", "ecw extrazellulaeres wasser"],
                    ["%"]),
    "koerperwasser_l": (["koerperwasser", "tbw", "gesamtkoerperwasser", "total body water", "wasser", "gesamtwasser",
                         "tbw total body water", "total body water tbw", "koerperwasser tbw", "tbw koerperwasser",
                         "gesamtkoerperwasser tbw"], ["l"]),
    "bmi": (["bmi", "body mass index", "koerpermassenindex", "body mass index bmi", "bmi body mass index"],
            ["kg/m²", ""]),
}
BIA_WEITERE = {
    "Phasenwinkel": ["phasenwinkel", "phase angle", "phi", "pa", "pha", "phasenwinkel 50 khz", "phase angle 50 khz",
                     "phasenwinkel phi", "phasenwinkel pa"],
    "Magermasse": ["magermasse", "ffm", "fettfreie masse", "lean body mass", "lbm", "fat free mass", "ffm fettfreie masse",
                   "fettfreie masse ffm", "lean mass"],
    "Skelettmuskelmasse": ["skelettmuskelmasse", "smm", "skeletal muscle mass", "muskelmasse", "muscle mass"],
    "ECM": ["ecm", "extrazellulaere masse", "ecm extrazellulaere masse"],
    "ECM/BCM-Index": ["ecm bcm", "ecm bcm index"],
    "ICW": ["icw", "intrazellulaeres wasser", "intracellular water"],
    "Zellanteil": ["zellanteil", "bcm anteil"],
    "Grundumsatz": ["grundumsatz", "bmr", "ruheumsatz", "basal metabolic rate"],
    "Viszerales Fett": ["viszerales fett", "visceral fat", "vfa", "viszerale fettflaeche"],
    "Resistanz": ["resistanz", "resistance", "r", "resistanz r", "r 50 khz"],
    "Reaktanz": ["reaktanz", "reactance", "xc", "reaktanz xc", "xc 50 khz"],
}


def _wert_mit_einheit(rest: list[T], erwartet: list[str] | None = None) -> tuple[Decimal | None, str, list[T], str]:
    """→ (Wert, Einheit, benutzte Wörter, Hinweis). Unbekannte Einheiten zählen als „keine“."""
    for i, t in enumerate(rest[:3]):
        m = _WERT.match(t.text.replace(" ", ""))
        if m and not m.group("op"):
            w = E.zahl(m.group("zahl"))
            e, hinweis = "", ""
            if i + 1 < len(rest):
                e = E.einheit(rest[i + 1].text) or ""
                if not e and re.match(r"^kg/m.?$", rest[i + 1].text):
                    e = "kg/m²"
            elif erwartet and "l" in erwartet and re.fullmatch(r"\d+[.,]\d+[1Il|]", t.text):
                # „29,8 l“ als „29,81“ gelesen: die Einheit klebt als „1“ an der Zahl
                w = E.zahl(t.text[:-1])
                e, hinweis = "l", f"„{t.text}“ als {t.text[:-1]} l gelesen – bitte prüfen"
            return w, e, rest[: i + 2], hinweis
    return None, "", [], ""


def bia_werte(reihen: list[list[T]], gelernt: Gelerntes | None = None, quelle: str = "") -> dict:
    felder, weitere = {}, []
    for r in reihen:
        if len(r) < 2:
            continue
        for k in range(min(4, len(r) - 1), 0, -1):
            if any(_ist_wert(t.text) for t in r[:k]):
                continue  # das Etikett endet vor dem ersten Wert
            etikett = norm(_text(r[:k]))
            if not etikett:
                continue
            if gelernt and gelernt.ignoriert(quelle, etikett):
                break
            treffer = None
            # gelernt (F182): Bezeichnungen anderer Geräte, die die Pflegekraft einem Feld zugeordnet hat
            gl = gelernt.finden("bia", quelle, etikett) if gelernt else None
            if gl is not None and gl.ziel in BIA_FELDER:
                treffer = ("feld", gl.ziel, BIA_FELDER[gl.ziel][1])
            else:
                gl = None
            for feld, (begriffe, einheiten_) in BIA_FELDER.items():
                if treffer is not None:
                    break
                if etikett in begriffe or any(etikett.startswith(b + " ") and len(b) > 3 for b in begriffe):
                    if gelernt and gelernt.ist_gesperrt("bia", quelle, etikett, feld):
                        continue
                    treffer = ("feld", feld, einheiten_)
                    break
            if treffer is None:
                for name, begriffe in BIA_WEITERE.items():
                    if etikett in begriffe or any(etikett.startswith(b + " ") and len(b) > 2 for b in begriffe):
                        treffer = ("weitere", name, None)
                        break
            if treffer is None:
                continue
            wert, e, woerter, hinweis = _wert_mit_einheit(r[k:], treffer[2])
            if wert is None:
                break
            sicher = woerter[0].c if woerter else 0.0
            if hinweis:
                sicher = min(sicher, UNSICHER - 0.05)
            if treffer[0] == "feld":
                feld, erlaubt = treffer[1], treffer[2]
                if e and erlaubt and e not in erlaubt:
                    # z. B. Fettmasse in % – das Feld erwartet kg
                    weitere.append({"name": _text(r[:k]), "wert": _dez(wert), "einheit": e, "seite": r[0].seite,
                                    "box": _rahmen(r[:k] + woerter)})
                    break
                if feld == "ecw_prozent" and not e and wert is not None and 0 < wert < 1:
                    # als Verhältnis gedruckt (ECW/TBW 0,380) – das Feld erwartet Prozent
                    hinweis = hinweis or f"als Verhältnis {_dez(wert)} gedruckt – in Prozent umgerechnet"
                    wert, e = wert * 100, "%"
                if feld not in felder:
                    hinweise = [hinweis] if hinweis else []
                    if gl is not None:
                        hinweise.append(f"gelernt: so schon {gl.bestaetigt}-mal übernommen" if gl.sicher
                                        else f"gelernt, erst {gl.bestaetigt}-mal bestätigt – bitte prüfen")
                    felder[feld] = {"wert": _dez(wert), "einheit": e, "erkannt_als": _text(r[:k]),
                                    "seite": r[0].seite, "box": _rahmen(r[:k] + woerter),
                                    "sicherheit": round(sicher, 3),
                                    "vorschlag": sicher >= 0.5 and (gl is None or gl.sicher),
                                    "hinweise": hinweise}
                    if gl is not None:
                        felder[feld]["zuordnung"] = "gelernt" if gl.sicher else "gelernt_vorschlag"
            else:
                weitere.append({"name": treffer[1], "wert": _dez(wert), "einheit": e, "seite": r[0].seite,
                                "box": _rahmen(r[:k] + woerter)})
            break
    return {"werte": felder, "weitere": weitere}


# ---------------------------------------------------------------- Arztbrief: Diagnosen und Abschnitte
_ICD = re.compile(r"\b([A-TV-Z]\d{2}(?:\.\d{1,2})?)([+*!])?(?:\s*([GVZA])\b)?")
ABSCHNITTE = {
    "diagnosen": ["diagnose", "diagnosen", "aktuelle diagnosen", "entlassungsdiagnosen", "entlassdiagnosen",
                  "hauptdiagnose", "nebendiagnosen", "vorerkrankungen", "dauerdiagnosen"],
    "anamnese": ["anamnese", "jetzige anamnese"],
    "befund": ["befund", "befunde", "untersuchungsbefund", "aufnahmebefund"],
    "therapie": ["therapie", "therapie und verlauf", "verlauf und therapie", "behandlung", "medikation",
                 "entlassmedikation", "aktuelle medikation"],
    "verlauf": ["verlauf", "epikrise", "beurteilung", "zusammenfassung"],
    "procedere": ["procedere", "prozedere", "empfehlung", "empfehlungen", "weiteres vorgehen", "weiteres procedere"],
}


def _kennzeichen(text: str) -> str:
    """„V. a.“, „Z. n.“, „Ausschluss“ am Anfang → V, Z, A; sonst gesichert."""
    n = norm(text)
    if n.startswith(("v a ", "va ", "verdacht")):
        return "V"
    if n.startswith(("z n ", "zn ", "zustand nach")):
        return "Z"
    if n.startswith(("ausschluss", "ausschl", "a v ")):
        return "A"
    return "G"


_PRAEFIX = re.compile(r"^(?:v\.?\s*a\.?|verdacht\s+auf|z\.?\s*n\.?|zustand\s+nach|ausschluss(?:\s+von)?|ausschl\.?|"
                      r"a\.\s*v\.)\s*:?\s+", re.I)
_AUFZAEHLUNG = re.compile(r"^(?:\s*(?:[\-–•*·]+|\d{1,2}[.)]|[a-z][.)]))+\s*")
_MESSWERT = re.compile(r"\d\s*(?:kg|g|mg|µg|ug|ng|mmol|µmol|umol|mol|l|ml|dl|cm|mm|m|%|kcal|u|iu|ie)(?:/|\b|²|$)",
                       re.I)
_FUELLWORT = {"bei", "mit", "und", "oder", "der", "die", "das", "des", "den", "dem", "von", "vom", "nach", "im", "in",
              "am", "an", "auf", "zu", "zur", "zum", "ohne", "bzw", "sowie", "nicht", "naeher", "bezeichnet"}


def _woerter(text: str) -> list[str]:
    return [w for w in norm(text).split() if w not in _FUELLWORT and (len(w) >= 3 or w.isdigit())]


def _gleich(a: str, b: str) -> bool:
    if a == b:
        return True
    if a.isdigit() or b.isdigit():
        return False
    return (min(len(a), len(b)) >= 5 and abstand(a, b) <= 1) or (min(len(a), len(b)) >= 8 and abstand(a, b) <= 2)


def diagnoseliste_vorbereiten(liste: list | None) -> list[tuple[str, str, list[list[str]]]]:
    """(ICD-Code, Bezeichnung) der Liste unter Vorlagen › Diagnosen → mit Wortlisten je Schreibweise: „Neurodermitis
    (atopisches Ekzem)“ zählt als „Neurodermitis“ und als „atopisches Ekzem“, „A / B“ als A und als B."""
    aus = []
    for code, bez in liste or []:
        if not code or not bez:
            continue
        teile = [bez, re.sub(r"\([^)]*\)", " ", bez)] + re.findall(r"\(([^)]*)\)", bez)
        teile += [t for t in re.split(r"\s+/\s+|\(|\)", bez) if t.strip()]
        varianten = []
        for t in teile:
            w = _woerter(t)
            if w and w not in varianten:
                varianten.append(w)
        if varianten:
            aus.append((code, bez, varianten))
    return aus


def aus_liste(text: str, liste: list) -> tuple[str, str, float] | None:
    """Bester Eintrag der Diagnoseliste zum Freitext: (Code, Bezeichnung, Übereinstimmung 0–1).

    Übereinstimmung = gleiche Wörter (kleine Lesefehler zählen mit) geteilt durch die Wortzahl der längeren Seite –
    „Kurzdarmsyndrom“ passt zu „Kurzdarmsyndrom“ mit 1, „Kurzdarmsyndrom nach Resektion“ mit 0,33."""
    tw = _woerter(text)
    if not tw:
        return None
    bester, rang = None, None
    for code, bez, varianten in liste:
        n = norm(bez)
        # bei Gleichstand die unspezifische Form („Diabetes mellitus Typ 2“ → „ohne Komplikationen, nicht entgleist“,
        # nicht „mit Koma“), sonst die kürzere Bezeichnung
        allgemein = sum(t in n for t in ("ohne komplikation", "nicht naeher bez", "nicht entgleist"))
        for vw in varianten:
            gleich = sum(1 for w in tw if any(_gleich(w, v) for v in vw))
            wert = round(gleich / max(len(tw), len(vw)), 2)
            r = (wert, allgemein, -len(bez))
            if wert > 0 and (rang is None or r > rang):
                bester, rang = (code, bez, wert), r
    return bester


LISTE_SICHER = 1.0
LISTE_AEHNLICH = 0.6


def diagnosen(reihen: list[list[T]], gelernt: Gelerntes | None = None, quelle: str = "",
              liste: list | None = None) -> list[dict]:
    """Diagnosen des Briefs: zuerst alle Zeilen mit ICD-Code, dahinter (Kundenwunsch 14.10.2026: „PDF-Dokumente
    enthalten keine ICD-Diagnosen, nur Freitext“) die Zeilen unter „Diagnosen:“ ohne Code. Für diese kommt der Code
    aus dem Gelernten oder aus der Liste unter Vorlagen › Diagnosen; ohne Treffer bleibt er leer und muss vor dem
    Übernehmen ergänzt werden – der ICD-Code bleibt Pflicht. ``liste`` wie ``diagnoseliste_vorbereiten`` sie
    liefert."""
    aus, gesehen, mit_code = [], set(), set()
    for r in reihen:
        zeile = _text(r)
        for m in _ICD.finditer(zeile):
            code = m.group(1)
            davor = zeile[max(0, m.start() - 6): m.start()]
            # „Vitamin B12“, „Raum C12“: ein Code ohne Punkt zählt nur in Klammern, nach „ICD“ oder mit Kennzeichen
            if "." not in code and not m.group(3) and not re.search(r"(\(|\[|icd[-\s:]*|code[\s:]*)$", davor, re.I):
                continue
            if re.search(r"vitamin\s*$", zeile[: m.start()], re.I):
                continue
            mit_code.add(id(r))
            if code in gesehen:
                continue
            vor = zeile[: m.start()]
            # Text vor dem Code auf derselben Zeile (ohne Aufzählungszeichen und Klammer)
            text = re.sub(r"^[\s\-–•*·\d.)]+", "", vor).strip().rstrip("([:,;-– ").strip()
            if len(text) < 3:
                # Code am Zeilenanfang: Bezeichnung dahinter
                text = re.sub(r"^[\s:)\]\-–]+", "", zeile[m.end():]).strip()
            if len(text) < 3 or not re.search(r"[A-Za-zÄÖÜäöü]{3}", text):
                continue
            kennzeichen = m.group(3) or _kennzeichen(text)
            if gelernt and gelernt.ignoriert(quelle, norm(text)):
                continue  # „falsch erkannt – gehört nicht dazu“ (F189)
            gesehen.add(code)
            woerter = [t for t in r]
            eintrag = {"bezeichnung": text[:200], "icd_code": code + (m.group(2) or ""), "kennzeichen": kennzeichen,
                       "erkannt_als": text[:200], "erkannt_code": code + (m.group(2) or ""), "zeile": zeile[:200], "seite": r[0].seite, "box": _rahmen(woerter),
                       "sicherheit": round(min(t.c for t in r), 3), "vorschlag": True, "hinweise": []}
            # gelernt (F182): Lesefehler in der Bezeichnung bzw. im Code, die die Pflegekraft korrigiert hat
            gl = gelernt.finden("diagnose", quelle, norm(text)) if gelernt else None
            if gl is not None and gl.ziel_text:
                if gl.sicher:
                    eintrag.update(bezeichnung=gl.ziel_text[:200], icd_code=gl.ziel or eintrag["icd_code"],
                                   zuordnung="gelernt")
                    eintrag["hinweise"].append(f"gelernt: gelesen „{text[:80]}“, so schon {gl.bestaetigt}-mal "
                                               f"korrigiert")
                else:
                    eintrag["zuordnung"] = "gelernt_vorschlag"
                    eintrag["gelernt"] = {"bezeichnung": gl.ziel_text[:200], "icd_code": gl.ziel or eintrag["icd_code"]}
                    eintrag["hinweise"].append(f"gelernt, erst {gl.bestaetigt}-mal korrigiert: „{gl.ziel_text[:80]}“"
                                               f" ({gl.ziel}) – bitte prüfen")
            aus.append(eintrag)
    aus += _freitext_diagnosen(reihen, mit_code, gesehen, gelernt, quelle, liste or [])
    return aus


def _freitext_zeilen(reihen: list[list[T]], mit_code: set) -> list[tuple[str, list[T]]]:
    """Zeilen unter „Diagnosen:“ ohne ICD-Code, umbrochene Zeilen wieder zusammengesetzt."""
    zeilen: list[tuple[str, list[T]]] = []
    vorige = -2
    for art, woerter, text, nr in _abschnitt_zeilen(reihen):
        roh = text.strip()
        if art != "diagnosen" or not roh or id(reihen[nr]) in mit_code:
            continue
        if zeilen and nr == vorige + 1:
            alt, alt_w = zeilen[-1]
            # „Kurzdarm-“ / „syndrom“ und klein Weitergeschriebenes bzw. „… bei“ / „Dünndarmresektion“
            if alt.endswith("-") and roh[:1].islower():
                zeilen[-1], vorige = (alt[:-1] + roh, alt_w + woerter), nr
                continue
            if roh[:1].islower() or re.search(r"(,|\bbei|\bmit|\bund|\bnach|\bdurch|\bdes|\bder)$", alt, re.I):
                zeilen[-1], vorige = (f"{alt} {roh}", alt_w + woerter), nr
                continue
        zeilen.append((roh, woerter))
        vorige = nr
    return zeilen


def _freitext_diagnosen(reihen, mit_code, gesehen, gelernt, quelle, liste) -> list[dict]:
    aus, texte = [], set()
    for roh, r in _freitext_zeilen(reihen, mit_code):
        text = _AUFZAEHLUNG.sub("", roh).strip().rstrip(".,;:").strip()
        if len(text) < 3 or not re.search(r"[A-Za-zÄÖÜäöü]{3}", text):
            continue
        # Fließtext („Die Patientin stellte sich …“) und Messwerte („Körpergewicht 58,4 kg“) sind keine Diagnosen
        if len(text.split()) > 14 or re.match(r"^(seite|page)\s+\d", text, re.I) or _MESSWERT.search(text):
            continue
        if gelernt and gelernt.ignoriert(quelle, norm(text)):
            continue  # „falsch erkannt – gehört nicht dazu“ (F189)
        if norm(text) in texte:
            continue
        texte.add(norm(text))
        kennzeichen = _kennzeichen(text)
        ohne = _PRAEFIX.sub("", text).strip() or text
        eintrag = {"bezeichnung": ohne[:200], "icd_code": "", "kennzeichen": kennzeichen, "erkannt_als": text[:200],
                   "erkannt_code": "", "zeile": roh[:200], "seite": r[0].seite if r else 0,
                   "box": _rahmen(list(r)), "sicherheit": round(min((t.c for t in r), default=0), 3),
                   "vorschlag": False, "freitext": True, "hinweise": []}
        gl = gelernt.finden("diagnose", quelle, norm(text)) if gelernt else None
        if gl is not None and gl.ziel_text and gl.ziel:
            if gl.sicher:
                eintrag.update(bezeichnung=gl.ziel_text[:200], icd_code=gl.ziel, zuordnung="gelernt", vorschlag=True)
                eintrag["hinweise"].append(f"ohne ICD-Code im Brief; gelernt, so schon {gl.bestaetigt}-mal zugeordnet")
            else:
                eintrag["zuordnung"] = "gelernt_vorschlag"
                eintrag["gelernt"] = {"bezeichnung": gl.ziel_text[:200], "icd_code": gl.ziel}
                eintrag["hinweise"].append(f"gelernt, erst {gl.bestaetigt}-mal zugeordnet: „{gl.ziel_text[:80]}“"
                                           f" ({gl.ziel}) – bitte prüfen")
        if not eintrag["icd_code"]:
            t = aus_liste(ohne, liste)
            if t and t[2] >= LISTE_SICHER:
                eintrag.update(bezeichnung=t[1][:200], icd_code=t[0], zuordnung="liste",
                               vorschlag="gelernt" not in eintrag)
                eintrag["hinweise"].append(f"ohne ICD-Code im Brief; Code aus der Diagnoseliste: {t[1][:80]} ({t[0]})"
                                           f" – bitte prüfen")
            elif t and t[2] >= LISTE_AEHNLICH:
                eintrag.update(icd_code=t[0], zuordnung="liste_vorschlag")
                eintrag["hinweise"].append(f"ohne ICD-Code im Brief; ähnlich in der Diagnoseliste: {t[1][:80]} ({t[0]})"
                                           f" – bitte prüfen")
            elif "gelernt" not in eintrag:
                eintrag["hinweise"].append("ohne ICD-Code im Brief und nicht in der Diagnoseliste – bitte ICD-Code "
                                           "ergänzen")
        if eintrag["icd_code"] and eintrag["icd_code"] in gesehen and eintrag.get("zuordnung") != "gelernt":
            continue  # steht schon mit Code im Brief
        if eintrag["icd_code"]:
            gesehen.add(eintrag["icd_code"])
        aus.append(eintrag)
    return aus


def _abschnitt_zeilen(reihen: list[list[T]]):
    """Je Zeile unter einer bekannten Überschrift (Abschnitt, Wörter, Text, Nummer der Reihe) – für ``abschnitte``
    und die Diagnosen ohne ICD-Code. „Diagnosen: Kurzdarmsyndrom“ liefert den Rest hinter der Überschrift."""
    aktuell = None
    for nr, r in enumerate(reihen):
        zeile = _text(r).strip()
        kopf = re.match(r"^([A-Za-zÄÖÜäöüß ./-]{3,40}?)\s*:\s*(.*)$", zeile)
        gefunden = None
        if kopf:
            n = norm(kopf.group(1))
            for art, begriffe in ABSCHNITTE.items():
                if n in begriffe:
                    gefunden = art
                    break
        elif norm(zeile) in {b for bs in ABSCHNITTE.values() for b in bs}:
            n = norm(zeile)
            gefunden = next(a for a, bs in ABSCHNITTE.items() if n in bs)
            kopf = None
        if gefunden:
            aktuell = gefunden
            if kopf and kopf.group(2).strip():
                k = next((i for i, t in enumerate(r) if ":" in t.text), len(r) - 1)
                yield aktuell, r[k + 1:] or r, kopf.group(2).strip(), nr
            else:
                yield aktuell, [], "", nr
            continue
        if aktuell is None:
            continue
        if re.match(r"^(mit freundlichen|mfg|hochachtungsvoll|mit kollegialen)", zeile, re.I):
            aktuell = None
            continue
        # neue, nicht bekannte Überschrift beendet den Abschnitt
        if re.match(r"^[A-ZÄÖÜ][A-Za-zÄÖÜäöüß ./-]{2,40}:\s*$", zeile):
            aktuell = None
            continue
        yield aktuell, r, zeile, nr


def abschnitte(reihen: list[list[T]]) -> dict:
    """Überschriften wie „Diagnosen:“, „Therapie:“, „Procedere:“ und der Text darunter bis zur nächsten."""
    aus: dict[str, list[str]] = {}
    for art, _, text, _ in _abschnitt_zeilen(reihen):
        aus.setdefault(art, [])
        if text:
            aus[art].append(text)
    return {k: "\n".join(v).strip() for k, v in aus.items() if "\n".join(v).strip()}


# ---------------------------------------------------------------- Patient
# „Patient: Muster, Erika“, „Name: Erika Muster“, „wir berichten über Frau Erika Muster, geb. …“ (F183)
_NAME_VOR = re.compile(r"(?i:\b(?:patient(?:in)?|pat\.|name|versicherte[rn]?|betrifft|betr\.|herrn?|frau|über|ueber|für|"
                       r"fuer)\b\.?\s*:?\s*)((?:[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'\-]+\.?,?\s*){1,4})")
_KEIN_NAME = {"geb", "geboren", "geburtsdatum", "nr", "pat", "patient", "patientin", "name", "frau", "herr", "herrn", "dr",
              "med", "prof", "dipl", "und", "mit", "der", "die", "das", "den", "im", "am", "vom", "datum", "befund",
              "labor", "station", "kollege", "kollegin", "sehr", "geehrte", "geehrter", "auftrag", "einsender"}


def _namen(zeile: str) -> set[str]:
    """Wörter, die nach einem Hinweis wie „Patient:“ oder „Frau“ als Name stehen (normalisiert)."""
    aus = set()
    for m in _NAME_VOR.finditer(zeile):
        for w in re.split(r"[\s,]+", m.group(1)):
            n = norm(w)
            if len(n) >= 2 and not n.isdigit() and n not in _KEIN_NAME:
                aus.update(n.split())
    return aus


def patient_hinweise(reihen: list[list[T]], heute: date | None = None) -> dict:
    """Was im Dokument auf den Patienten hinweist: Nummern, Geburtsdaten, Namen (nach „Patient:“, „Frau“ …) und alle
    Wörter – für den Abgleich mit der Datenbank. Bleibt im Server, wird weder gelernt noch protokolliert (F183)."""
    heute = heute or date.today()
    nummern, geburt, woerter, namen = [], [], set(), set()
    for r in reihen[:80]:
        zeile = _text(r)
        namen |= _namen(zeile)
        for m in re.finditer(r"(?:pat(?:ienten)?\.?\s*-?\s*(?:nr|nummer|id)\.?|epm\s*-?\s*nr\.?|fallnr\.?|"
                             r"nr\.)\s*[:#]?\s*(\d{1,7})\b", zeile, re.I):
            nummern.append(int(m.group(1)))
        for m in re.finditer(r"(?:geb(?:oren)?\.?(?:\s*am)?|geburtsdatum|geb\.-datum|\*)\s*:?\s*"
                             r"(\d{1,2}\s?[.\-/]\s?\d{1,2}\s?[.\-/]\s?\d{2,4})", zeile, re.I):
            d = datum_aus(m.group(1))
            if d and d < heute:
                geburt.append(d)
        for t in r:
            w = norm(t.text)
            if len(w) >= 3 and not w.isdigit():
                woerter.add(w)
    return {"nummern": sorted(set(nummern)), "geburtsdaten": sorted({d.isoformat() for d in geburt}),
            "woerter": sorted(woerter), "namen": sorted(namen)}


def etikett_an(reihen: list[list[T]], seite: int, box) -> str:
    """Bezeichnung links von einer angeklickten Stelle (Wert, den die Pflegekraft im Bild gewählt hat): die Wörter der
    Reihe vor diesem Wort, ohne Zahlen und Pfeile. „“, wenn dort nichts Brauchbares steht (F182)."""
    try:
        mx, my = float(box[0]) + float(box[2]) / 2, float(box[1]) + float(box[3]) / 2
    except (TypeError, ValueError, IndexError):
        return ""
    for r in reihen:
        if not r or r[0].seite != seite:
            continue
        for k, t in enumerate(r):
            x, y, b, h = t.box
            if x - 0.002 <= mx <= x + b + 0.002 and y - 0.002 <= my <= y + h + 0.002:
                vorn = r[:k]
                while vorn and (vorn[-1].text in _PFEIL_WORT or _ist_wert(vorn[-1].text) or _OP.match(vorn[-1].text)):
                    vorn = vorn[:-1]
                text = _text(vorn).strip(" :")
                if not re.search(r"[A-Za-zÄÖÜäöü]{2}", text) or len(text) > 60:
                    return ""
                return text
    return ""


# ---------------------------------------------------------------- Gesamtauswertung
def auswerten(seiten: list[dict], parameter: list[dict], heute: date | None = None,
              gelernt: Gelerntes | None = None, zusatz: list | None = None, diagnoseliste: list | None = None) -> dict:
    """``zusatz``: aus markierten Bereichen nachgelesene Reihen (F189) als [(Seitenindex, Ergebnis-JSON, Bereich)] –
    sie kommen hinter alle anderen Reihen, damit die Nummern der übrigen Vorschläge gleich bleiben.
    ``diagnoseliste``: [(ICD-Code, Bezeichnung)] aus Vorlagen › Diagnosen für Diagnosen ohne Code im Brief."""
    reihen = reihen_aus(seiten)
    for nr, d, bereich in zusatz or []:
        reihen += reihen_der_seite(d, nr, bereich)
    d, quelle = dokumentdatum(reihen, heute)
    absender = labor_name(reihen)
    q = norm(absender)[:150]
    werte = laborwerte(reihen, parameter, gelernt, q)
    bia = bia_werte(reihen, gelernt, q)
    dg = diagnosen(reihen, gelernt, q, diagnoseliste_vorbereiten(diagnoseliste))
    ab = abschnitte(reihen)
    arten = []
    if sum(1 for w in werte if w["parameter"]) >= 3:
        arten.append("labor")
    if len(bia["werte"]) >= 2 or (bia["werte"] and bia["weitere"]):
        arten.append("bia")
    gesamt = " ".join(_text(r) for r in reihen[:40]).lower()
    if dg or ab.get("diagnosen") or "sehr geehrte" in gesamt or "arztbrief" in gesamt or "entlass" in gesamt:
        arten.append("arztbrief")
    if "bia" in arten and "labor" in arten and not any(w["parameter"] for w in werte[3:]):
        arten.remove("labor")
    return {
        "arten": arten,
        "datum": d.isoformat() if d else None,
        "datum_quelle": quelle,
        "labor": {"name": absender, "werte": werte},
        "bia": bia,
        "diagnosen": dg,
        "abschnitte": ab,
        "patient": patient_hinweise(reihen, heute),
    }
