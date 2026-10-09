"""Werte aus dem erkannten Text: Laborbefund, BIA-Messung, Diagnosen mit ICD-Code, Abschnitte, Datum, Hinweise
auf den Patienten.

Feste Regeln, kein Sprachmodell. Alles ist ein Vorschlag für die Prüfansicht: Nichts wird ohne Bestätigung in eine
Akte geschrieben. Jeder Vorschlag nennt die Stelle (Seite, Lage), an der er gelesen wurde, und wie sicher die
Erkennung dort war.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
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

TEXTWERTE = {"negativ", "positiv", "neg", "pos", "n b", "nb", "nicht nachweisbar", "nachweisbar", "folgt", "s u",
             "siehe unten", "normal", "unauffaellig", "kein", "keine"}


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


def reihen_aus(seiten: list[dict]) -> list[list[T]]:
    """Ergebnis-JSON aller Seiten → Reihen von Wörtern (Seite für Seite, oben nach unten)."""
    aus = []
    for nr, d in enumerate(seiten):
        b, h = max(d.get("breite") or 1, 1), max(d.get("hoehe") or 1, 1)
        for r in d.get("reihen", []):
            reihe = []
            for s in r:
                for w in s["w"]:
                    reihe.append(T(str(w[0]), nr, (w[1] / b, w[2] / h, w[3] / b, w[4] / h), float(w[5])))
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


def _suche_parameter(label: str, index, eintraege) -> tuple[Katalogeintrag | None, str]:
    """→ (Parameter, „genau“ | „ähnlich“ | „“)."""
    n = norm(label)
    if not n:
        return None, ""
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


def _wertspalten(reihen: list[list[T]]) -> dict[int, tuple[float, float]]:
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
    return aus


def _pfeil_als_eins(t: T, roh: str, spalten) -> bool:
    """„118.69“, dessen „1“ links aus der Wertespalte ragt: ein als „1“ gelesener Pfeil."""
    if t.seite not in spalten or not re.fullmatch(r"1\d+(?:[.,]\d+)?", roh):
        return False
    links, zeichen = spalten[t.seite]
    eigenes = t.box[2] / len(roh)
    return t.box[0] < links - 0.6 * zeichen and abs(t.box[0] + eigenes - links) <= 0.5 * zeichen


def laborwerte(reihen: list[list[T]], parameter: list[dict]) -> list[dict]:
    """Zeilen eines Laborbefunds → vorgeschlagene Werte (Parameter aus dem Katalog oder Freitext)."""
    index, eintraege = katalog_index(parameter)
    spalten = _wertspalten(reihen)
    vorschlaege = []
    for r in reihen:
        if len(r) < 2:
            continue
        k = _wertstelle(r)
        if k is None:
            continue
        etikett = _text(r[:k - 1] if r[k - 1].text in _PFEIL_WORT and k > 1 else r[:k])
        if not re.search(r"[A-Za-zÄÖÜäöü]", etikett) or len(etikett) > 60:
            continue
        if alle_daten(etikett) or _DATUM_WORT.match(r[k + 1].text if _OP.match(r[k].text) and k + 1 < len(r)
                                                    else r[k].text):
            continue  # Kopfzeilen mit Datum („Eingang 19.11.2024“); ein Datum beim Vorwert hinten zählt nicht
        param, art = _suche_parameter(etikett, index, eintraege)
        rest = r[k:]
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
        if j < len(rest):
            e = E.einheit(rest[j].text)
            if e is None and j + 1 < len(rest):
                e = E.einheit(rest[j].text + rest[j + 1].text)  # „mmol /l“
                if e:
                    j += 1
            if e is not None:
                einheit_gelesen, einheit_ = rest[j].text, e
                j += 1
        ref_text = _text(rest[j:])
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
        }
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


def bia_werte(reihen: list[list[T]]) -> dict:
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
            treffer = None
            for feld, (begriffe, einheiten_) in BIA_FELDER.items():
                if etikett in begriffe or any(etikett.startswith(b + " ") and len(b) > 3 for b in begriffe):
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
                    felder[feld] = {"wert": _dez(wert), "einheit": e, "erkannt_als": _text(r[:k]),
                                    "seite": r[0].seite, "box": _rahmen(r[:k] + woerter),
                                    "sicherheit": round(sicher, 3), "vorschlag": sicher >= 0.5,
                                    "hinweise": [hinweis] if hinweis else []}
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


def diagnosen(reihen: list[list[T]]) -> list[dict]:
    aus, gesehen = [], set()
    for r in reihen:
        zeile = _text(r)
        for m in _ICD.finditer(zeile):
            code = m.group(1)
            if code in gesehen:
                continue
            davor = zeile[max(0, m.start() - 6): m.start()]
            # „Vitamin B12“, „Raum C12“: ein Code ohne Punkt zählt nur in Klammern, nach „ICD“ oder mit Kennzeichen
            if "." not in code and not m.group(3) and not re.search(r"(\(|\[|icd[-\s:]*|code[\s:]*)$", davor, re.I):
                continue
            if re.search(r"vitamin\s*$", zeile[: m.start()], re.I):
                continue
            vor = zeile[: m.start()]
            # Text vor dem Code auf derselben Zeile (ohne Aufzählungszeichen und Klammer)
            text = re.sub(r"^[\s\-–•*·\d.)]+", "", vor).strip().rstrip("([:,;-– ").strip()
            if len(text) < 3:
                # Code am Zeilenanfang: Bezeichnung dahinter
                text = re.sub(r"^[\s:)\]\-–]+", "", zeile[m.end():]).strip()
            if len(text) < 3 or not re.search(r"[A-Za-zÄÖÜäöü]{3}", text):
                continue
            kennzeichen = m.group(3)
            if not kennzeichen:
                n = norm(text)
                if n.startswith(("v a ", "va ", "verdacht")):
                    kennzeichen = "V"
                elif n.startswith(("z n ", "zn ", "zustand nach")):
                    kennzeichen = "Z"
                elif n.startswith(("ausschluss", "ausschl", "a v ")):
                    kennzeichen = "A"
                else:
                    kennzeichen = "G"
            gesehen.add(code)
            woerter = [t for t in r]
            aus.append({"bezeichnung": text[:200], "icd_code": code + (m.group(2) or ""), "kennzeichen": kennzeichen,
                        "zeile": zeile[:200], "seite": r[0].seite, "box": _rahmen(woerter),
                        "sicherheit": round(min(t.c for t in r), 3), "vorschlag": True})
    return aus


def abschnitte(reihen: list[list[T]]) -> dict:
    """Überschriften wie „Diagnosen:“, „Therapie:“, „Procedere:“ und der Text darunter bis zur nächsten."""
    aus: dict[str, list[str]] = {}
    aktuell = None
    for r in reihen:
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
            aus.setdefault(aktuell, [])
            if kopf and kopf.group(2).strip():
                aus[aktuell].append(kopf.group(2).strip())
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
        aus[aktuell].append(zeile)
    return {k: "\n".join(v).strip() for k, v in aus.items() if "\n".join(v).strip()}


# ---------------------------------------------------------------- Patient
def patient_hinweise(reihen: list[list[T]], heute: date | None = None) -> dict:
    """Was im Dokument auf den Patienten hinweist: Nummern, Geburtsdaten, Wörter (für den Abgleich mit der Datenbank)."""
    heute = heute or date.today()
    nummern, geburt, woerter = [], [], set()
    for r in reihen[:80]:
        zeile = _text(r)
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
            "woerter": sorted(woerter)}


# ---------------------------------------------------------------- Gesamtauswertung
def auswerten(seiten: list[dict], parameter: list[dict], heute: date | None = None) -> dict:
    reihen = reihen_aus(seiten)
    d, quelle = dokumentdatum(reihen, heute)
    werte = laborwerte(reihen, parameter)
    bia = bia_werte(reihen)
    dg = diagnosen(reihen)
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
        "labor": {"name": labor_name(reihen), "werte": werte},
        "bia": bia,
        "diagnosen": dg,
        "abschnitte": ab,
        "patient": patient_hinweise(reihen, heute),
    }
