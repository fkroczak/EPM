"""Einheiten der Laborwerte: Lesefehler reparieren, umrechnen, Plausibilität.

Labore schreiben dieselben Werte in verschiedenen Einheiten (Albumin in g/dl oder g/l, Kreatinin in mg/dl oder
µmol/l). Übernommen wird in der Einheit des Katalogs (Vorlagen › Labor); was sich nicht sicher umrechnen lässt,
bleibt in der gelesenen Einheit und wird markiert.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------- bekannte Einheiten (Schreibweise im EPM)
KANONISCH = [
    "mmol/l", "µmol/l", "nmol/l", "pmol/l", "mol/l",
    "g/l", "g/dl", "mg/l", "mg/dl", "µg/l", "µg/dl", "ng/ml", "ng/dl", "ng/l", "pg/ml", "µg/ml", "mg/ml",
    "U/l", "U/ml", "mU/l", "mU/ml", "µU/ml", "IU/l", "kU/l", "IE/l", "mIE/l",
    "%", "fl", "pg", "/nl", "/pl", "/µl", "G/l", "T/l", "Mio/µl", "Tsd/µl", "ml/min", "ml/min/1,73 m²",
    "mg/24h", "mmol/24h", "s", "sek", "ratio", "INR",
    "kg", "l", "l/l", "kg/m²", "°", "Ω", "cm",
]
_EXAKT = {k.replace(" ", ""): k for k in KANONISCH}
# „G/l“, „T/l“ mit „l“ als „A“ oder ganz verloren gelesen (schmale Schrift)
_EXAKT.update({"GA": "G/l", "G/A": "G/l", "G/": "G/l", "TA": "T/l", "T/A": "T/l", "T/": "T/l"})
# ohne Beachtung der Groß-/Kleinschreibung – außer G/l und T/l (Giga, Tera), die sonst mit g/l verwechselt würden
_INDEX = {k.lower().replace(" ", ""): k for k in KANONISCH if k not in ("G/l", "T/l")}
_INDEX.update({"u/l": "U/l", "iu/l": "U/l", "ie/l": "U/l", "mu/l": "mU/l", "miu/l": "mU/l", "mie/l": "mU/l",
               "µiu/ml": "mU/l", "µu/ml": "mU/l", "uu/ml": "mU/l", "ml/min/1.73m²": "ml/min/1,73 m²",
               "ml/min/1,73m2": "ml/min/1,73 m²", "ml/min/1.73m2": "ml/min/1,73 m²", "ml/min/1,73qm": "ml/min/1,73 m²", "ml/min/1.73qm": "ml/min/1,73 m²",
               "giga/l": "G/l", "tera/l": "T/l", "gpt/l": "G/l", "tpt/l": "T/l", "x10^9/l": "G/l", "x10^12/l": "T/l", "10^9/l": "G/l",
               "10^12/l": "T/l", "1/nl": "/nl", "1/pl": "/pl", "1/µl": "/µl", "tsd./µl": "Tsd/µl",
               "mio./µl": "Mio/µl", "kg/m2": "kg/m²", "sec": "s", "grad": "°", "fl.": "fl", "ohm": "Ω"})


def _ascii_mu(t: str) -> str:
    return t.replace("μ", "µ").replace("µ", "µ")


def einheit(token: str | None) -> str | None:
    """Gelesene Einheit → Schreibweise im EPM, None wenn es keine bekannte Einheit ist.

    Typische Lesefehler: „dI“, „di“, „d1“ statt „dl“; „Mg/dl“, „Hg/dl“, „ug/dl“ statt „µg/dl“; „mmol/1“."""
    if not token:
        return None
    t = _ascii_mu(unicodedata.normalize("NFKC", token.strip().strip(".,;:()[]")))
    if not t:
        return None
    t = t.replace(" ", "")
    # Zusätze hinter der Einheit: „pg/Ery“ (MCH), „ml/min/1,73m²KOF“ (eGFR, Körperoberfläche)
    t = re.sub(r"(?i)/(?:ery|erys|erythrozyt|zelle)$", "", t)
    t = re.sub(r"(?i)(?<=\d)(?:m²|m2|qm)?kof$", lambda m: m.group(0)[:-3], t)
    kandidaten = [t]
    r = t
    r = re.sub(r"(?<=/)d[iI1|]$", "dl", r)
    r = re.sub(r"(?<=/)[I1|]$", "l", r)
    r = re.sub(r"(?<=/m)[I1|]$", "l", r)
    r = re.sub(r"(?<=/m)l[iI1|]$", "l", r)
    r = re.sub(r"(?<=/m)[iI]$", "l", r)       # „ng/mi“
    r = re.sub(r"(?<=/n)[I1|]$", "l", r)
    r = re.sub(r"(?<=/p)[I1|]$", "l", r)
    r = re.sub(r"^[I1|l]/[I1|l]$", "l/l", r)                       # Hämatokrit „l/l“ als „I/l“, „1/1“
    # Schrägstrich nicht gelesen: „mmol1“, „mmoll“, „µmolI“, „mgdl“
    r = re.sub(r"^((?:m|µ|u|n|p)?mol)[I1|l]$", r"\1/l", r)
    r = re.sub(r"^((?:m|µ|u|n)?g)d[I1|li]$", r"\1/dl", r)
    kandidaten.append(r)
    # µ als u, M, H, p (nur vor g/ bzw. mol/ bzw. U/ – „Mg“ und „Hg“ gibt es als Einheit nicht)
    for v in list(kandidaten):
        m = re.match(r"^(?:u|M|H|mc|µ)(g/|mol/|U/)(.*)$", v)
        if m:
            kandidaten.append("µ" + m.group(1) + m.group(2))
    for v in kandidaten:
        if v in _EXAKT:
            return _EXAKT[v]
    for v in kandidaten:
        # Groß-/Kleinschreibung unsicher („Mmol/l“, „MG/DL“)
        if v.lower() in _INDEX:
            return _INDEX[v.lower()]
    return None


# ---------------------------------------------------------------- Umrechnung
_MASSE = {"g": Decimal(1), "mg": Decimal("1e-3"), "µg": Decimal("1e-6"), "ng": Decimal("1e-9"), "pg": Decimal("1e-12")}
_MOL = {"mol": Decimal(1), "mmol": Decimal("1e-3"), "µmol": Decimal("1e-6"), "nmol": Decimal("1e-9"),
        "pmol": Decimal("1e-12")}
_AKT = {"U": Decimal(1), "mU": Decimal("1e-3"), "µU": Decimal("1e-6"), "kU": Decimal(1000)}
_VOL = {"l": Decimal(1), "dl": Decimal("0.1"), "ml": Decimal("1e-3")}
_ANTEIL = {"%": Decimal("0.01"), "l/l": Decimal(1)}
_ZAHL = {"/nl": Decimal(1), "G/l": Decimal(1), "Tsd/µl": Decimal(1), "/µl": Decimal("1e-3"),
         "/pl": Decimal(1000), "T/l": Decimal(1000), "Mio/µl": Decimal(1000)}

# Molmassen (g/mol) für Umrechnungen zwischen Masse und Stoffmenge, je Laborwert (Schlüssel siehe ``schluessel``)
MOLMASSE = {
    "natrium": Decimal("22.99"), "kalium": Decimal("39.10"), "calcium": Decimal("40.08"),
    "magnesium": Decimal("24.305"), "phosphat": Decimal("30.97"), "chlorid": Decimal("35.45"),
    "kreatinin": Decimal("113.12"), "harnstoff": Decimal("60.06"), "harnsaeure": Decimal("168.11"),
    "glucose": Decimal("180.16"), "bilirubin": Decimal("584.66"), "triglyceride": Decimal("885.7"),
    "cholesterin": Decimal("386.65"), "eisen": Decimal("55.845"), "zink": Decimal("65.38"),
    "kupfer": Decimal("63.546"), "selen": Decimal("78.97"), "mangan": Decimal("54.938"),
    "vitamin_b12": Decimal("1355.37"), "folsaeure": Decimal("441.4"), "calcidiol": Decimal("400.64"),
    "calcitriol": Decimal("416.64"), "vitamin_a": Decimal("286.45"), "vitamin_e": Decimal("430.71"),
    "vitamin_b1": Decimal("265.35"), "vitamin_b6": Decimal("247.14"), "vitamin_k1": Decimal("450.7"),
    "ft4": Decimal("776.87"), "ft3": Decimal("650.98"), "haemoglobin": Decimal("16114.5"),
}


def _zerlege(e: str):
    """„mg/dl“ → ("masse", Faktor in g/l). None, wenn nicht zerlegbar."""
    if e in _ZAHL:
        return "zahl", _ZAHL[e]
    if e in _ANTEIL:
        return "anteil", _ANTEIL[e]
    if e == "IU/l":
        e = "U/l"
    m = re.match(r"^(g|mg|µg|ng|pg|mol|mmol|µmol|nmol|pmol|U|mU|µU|kU)/(l|dl|ml)$", e)
    if not m:
        return None
    zaehler, nenner = m.groups()
    vol = _VOL[nenner]
    if zaehler in _MASSE:
        return "masse", _MASSE[zaehler] / vol
    if zaehler in _MOL:
        return "mol", _MOL[zaehler] / vol
    return "akt", _AKT[zaehler] / vol


def faktor(von: str, nach: str, stoff: str | None = None) -> Decimal | None:
    """Faktor, mit dem ein Wert in ``von`` multipliziert wird, um ``nach`` zu erhalten. None = nicht umrechenbar."""
    if von == nach:
        return Decimal(1)
    a, b = _zerlege(von), _zerlege(nach)
    if a is None or b is None:
        return None
    if a[0] == b[0]:
        return a[1] / b[1]
    molmasse = MOLMASSE.get(stoff or "")
    if molmasse is None:
        return None
    if a[0] == "masse" and b[0] == "mol":
        return a[1] / molmasse / b[1]
    if a[0] == "mol" and b[0] == "masse":
        return a[1] * molmasse / b[1]
    return None


# ---------------------------------------------------------------- Plausibilität (Messbereich, in einer Bezugseinheit)
# Werte außerhalb sind fast sicher ein Lesefehler (fehlendes Komma, falsche Zeile) und werden nicht vorbelegt.
PLAUSIBEL = {
    "natrium": ("mmol/l", 90, 200), "kalium": ("mmol/l", 1, 10), "calcium": ("mmol/l", 0.8, 5),
    "magnesium": ("mmol/l", 0.1, 5), "phosphat": ("mmol/l", 0.1, 6), "chlorid": ("mmol/l", 60, 150),
    "kreatinin": ("mg/dl", 0.1, 25), "harnstoff": ("mg/dl", 2, 500), "harnsaeure": ("mg/dl", 0.2, 25),
    "glucose": ("mg/dl", 10, 1500), "albumin": ("g/l", 5, 70), "gesamteiweiss": ("g/l", 20, 140),
    "crp": ("mg/l", 0, 700), "haemoglobin": ("g/dl", 2, 25), "haematokrit": ("%", 5, 75),
    "ferritin": ("µg/l", 0.5, 50000), "eisen": ("µg/dl", 5, 1000), "transferrin": ("mg/dl", 20, 800),
    "transferrinsaettigung": ("%", 0.5, 120), "zink": ("µg/l", 50, 4000), "kupfer": ("µg/l", 100, 5000),
    "selen": ("µg/l", 5, 500), "mangan": ("µg/l", 0.1, 100), "vitamin_b12": ("ng/l", 20, 20000),
    "folsaeure": ("µg/l", 0.2, 200), "calcidiol": ("ng/ml", 1, 300), "bilirubin": ("mg/dl", 0, 50),
    "triglyceride": ("mg/dl", 10, 10000), "leukozyten": ("/nl", 0.1, 500), "thrombozyten": ("/nl", 1, 3000),
    "erythrozyten": ("/pl", 0.5, 10), "mcv": ("fl", 40, 160), "mch": ("pg", 10, 60), "mchc": ("g/dl", 20, 45),
    "hba1c": ("%", 2, 20), "tsh": ("mU/l", 0, 200),
    "gpt": ("U/l", 0, 20000), "got": ("U/l", 0, 20000), "ggt": ("U/l", 0, 20000), "ap": ("U/l", 0, 10000),
    "lipase": ("U/l", 0, 20000), "amylase": ("U/l", 0, 20000), "parathormon": ("pg/ml", 0, 5000),
}


def plausibel(stoff: str | None, wert: Decimal, einheit_: str) -> bool | None:
    """True/False, None wenn für diesen Wert kein Bereich hinterlegt oder nicht vergleichbar ist."""
    if not stoff or stoff not in PLAUSIBEL:
        return None
    bez, unten, oben = PLAUSIBEL[stoff]
    f = faktor(einheit_, bez, stoff) if einheit_ else None
    if f is None:
        return None
    w = wert * f
    return Decimal(str(unten)) <= w <= Decimal(str(oben))


# Andere Einheiten, in denen Labore einen Wert häufig angeben – zum Erschließen, wenn keine Einheit gelesen wurde
ALTERNATIVEN = {
    "haematokrit": ["l/l"], "haemoglobin": ["mmol/l", "g/l"], "kreatinin": ["µmol/l"], "glucose": ["mmol/l"],
    "harnstoff": ["mmol/l"], "harnsaeure": ["µmol/l"], "bilirubin": ["µmol/l"], "triglyceride": ["mmol/l"],
    "calcium": ["mg/dl"], "magnesium": ["mg/dl"], "phosphat": ["mg/dl"], "albumin": ["g/dl"],
    "gesamteiweiss": ["g/dl"], "eisen": ["µmol/l"], "leukozyten": ["/µl"], "thrombozyten": ["/µl"],
}


def einheit_raten(stoff: str | None, wert: Decimal, ziel: str) -> str | None:
    """Ohne gelesene Einheit: passt der Wert nicht zur Einheit des Katalogs, aber zu genau einer üblichen anderen
    (Hämatokrit 0,37 → l/l), diese Einheit. Sonst None."""
    if plausibel(stoff, wert, ziel) is not False:
        return None
    passend = [e for e in ALTERNATIVEN.get(stoff or "", [])
               if e != ziel and faktor(e, ziel, stoff) is not None and plausibel(stoff, wert, e)]
    return passend[0] if len(passend) == 1 else None


# ---------------------------------------------------------------- Zahlen
def zahl(text: str) -> Decimal | None:
    """„3,2“ → 3.2; „1.234,5“ → 1234.5; „0.68“ → 0.68. None, wenn keine Zahl."""
    t = text.strip().replace(" ", "").replace("−", "-")
    if not re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})*,\d+|[-+]?\d+(?:[.,]\d+)?", t):
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation:
        return None
