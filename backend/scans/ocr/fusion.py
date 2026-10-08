"""Zusammenführung der Erkennungen: je Zeilenstück das sicherere Ergebnis, je Wort eine Sicherheit.

Grundlage sind die Zeilen, die PP-OCR findet (robust auch auf Fotos). Für jede Zeile gibt es bis zu drei Lesarten:
PP-OCR selbst und Tesseract auf zwei Fassungen der Seite (Graustufen, Schwarz-Weiß). Die Lesarten werden Wort für
Wort verglichen:

- stimmen sie überein, gilt das Wort als sicher (beide Verfahren lesen dasselbe);
- weichen sie ab, gewinnt die Lesart mit der höheren Sicherheit – das Wort bleibt aber als „unsicher“ markiert und
  die andere Lesart wird mitgegeben (Anzeige beim Überfahren).

Was PP-OCR nicht als Zeile gefunden hat, Tesseract aber gelesen hat, kommt hinzu. Ohne PP-OCR werden die beiden
Tesseract-Fassungen auf dieselbe Weise verglichen.

Ergebnis je Seite: Reihen (gleiche Höhe) aus Stücken (Zellen einer Tabelle oder Zeilen eines Textes), Text mit
Tabulator zwischen den Stücken einer Reihe.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

import numpy as np

UNSICHER = 0.80     # darunter wird ein Wort markiert
EINIG_BONUS = 0.5   # stimmen zwei Verfahren überein, rückt die Sicherheit um die Hälfte des Abstands zu 1 nach oben

_ERLAUBT = re.compile(r"[A-Za-zÄÖÜäöüß0-9 .,:;/()\[\]%<>=+\-–—'\"µ°²³#&*!?§_@€$|~^]")


@dataclass
class Wort:
    t: str
    x: float
    y: float
    w: float
    h: float
    c: float
    alt: str | None = None

    def als_liste(self):
        aus = [self.t, round(self.x, 1), round(self.y, 1), round(self.w, 1), round(self.h, 1), round(self.c, 3)]
        if self.alt is not None:
            aus.append(self.alt)
        return aus


@dataclass
class Stueck:
    woerter: list[Wort]
    q: str                       # Quelle: "p" PP-OCR, "t" Tesseract, "d" Textebene der PDF, "m" gemischt
    alt: str | None = None       # abweichende Lesart des ganzen Stücks
    box: tuple = field(default=(0, 0, 0, 0))

    @property
    def text(self) -> str:
        return " ".join(w.t for w in self.woerter)

    @property
    def c(self) -> float:
        if not self.woerter:
            return 0.0
        g = np.array([max(1, len(w.t)) for w in self.woerter], dtype=np.float32)
        return float((np.array([w.c for w in self.woerter]) * g).sum() / g.sum())

    def rahmen(self):
        xs = [w.x for w in self.woerter] + [w.x + w.w for w in self.woerter]
        ys = [w.y for w in self.woerter] + [w.y + w.h for w in self.woerter]
        self.box = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        return self


def plausibel(text: str) -> float:
    """Anteil gewöhnlicher Zeichen (Buchstaben, Ziffern, Satzzeichen) – Zeichensalat wird abgewertet."""
    if not text:
        return 0.0
    return sum(1 for ch in text if _ERLAUBT.match(ch)) / len(text)


# ---------------------------------------------------------------- Tesseract → Stücke
def tesseract_stuecke(woerter, q: str = "t") -> list[Stueck]:
    """Wörter je Tesseract-Zeile; große Lücken (Tabellenspalten) trennen eine Zeile in mehrere Stücke."""
    zeilen: dict = {}
    for w in woerter:
        zeilen.setdefault(w.zeile, []).append(w)
    stuecke = []
    for liste in zeilen.values():
        liste.sort(key=lambda w: w.x)
        hoehe = float(np.median([w.h for w in liste])) if liste else 10.0
        aktuell = [liste[0]]
        for vorher, w in zip(liste, liste[1:]):
            if w.x - (vorher.x + vorher.w) > max(2.2 * hoehe, 25):
                stuecke.append(aktuell)
                aktuell = []
            aktuell.append(w)
        stuecke.append(aktuell)
    return [Stueck([Wort(w.text, w.x, w.y, w.w, w.h, w.c) for w in s], q).rahmen() for s in stuecke if s]


# ---------------------------------------------------------------- PP-OCR → Stücke
def paddle_stueck(z) -> Stueck:
    """Eine PP-OCR-Zeile mit Wörtern: Lage der Wörter aus der Lage ihrer Zeichen in der Zeile."""
    tl, tr, br, bl = z.ecken

    def punkt(anteil: float, oben: bool):
        a, b = (tl, tr) if oben else (bl, br)
        return a + (b - a) * anteil

    woerter, aktuell = [], []

    def abschliessen():
        if not aktuell:
            return
        anf, ende = aktuell[0][1], aktuell[-1][2]
        p = np.array([punkt(anf, True), punkt(ende, True), punkt(ende, False), punkt(anf, False)])
        x0, y0 = p[:, 0].min(), p[:, 1].min()
        text = "".join(ch for ch, *_ in aktuell)
        c = float(np.mean([s for *_, s in aktuell]))
        woerter.append(Wort(text, float(x0), float(y0), float(p[:, 0].max() - x0), float(p[:, 1].max() - y0), c))
        aktuell.clear()

    for ch, anf, ende, s in z.zeichen:
        if ch == " ":
            abschliessen()
        else:
            aktuell.append((ch, anf, ende, s))
    abschliessen()
    st = Stueck(woerter, "p")
    if not woerter:
        x0, y0 = z.ecken[:, 0].min(), z.ecken[:, 1].min()
        st.box = (float(x0), float(y0), float(z.ecken[:, 0].max() - x0), float(z.ecken[:, 1].max() - y0))
        return st
    return st.rahmen()


# ---------------------------------------------------------------- Vergleich zweier Lesarten
def _norm(t: str) -> str:
    return t.replace("–", "-").replace("—", "-").strip()


def vergleiche(a: list[Wort], b: list[Wort]) -> list[Wort]:
    """Wortweise Abgleich zweier Lesarten derselben Stelle. ``a`` gibt Lage und Reihenfolge vor."""
    if not b:
        return [Wort(w.t, w.x, w.y, w.w, w.h, min(w.c, 0.97)) for w in a]  # nur ein Verfahren: nie ganz sicher
    if not a:
        return [Wort(w.t, w.x, w.y, w.w, w.h, min(w.c, 0.97)) for w in b]
    sa, sb = [_norm(w.t) for w in a], [_norm(w.t) for w in b]
    aus: list[Wort] = []
    for art, i1, i2, j1, j2 in difflib.SequenceMatcher(a=sa, b=sb, autojunk=False).get_opcodes():
        if art == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                hoch = max(a[i].c, b[j].c)
                aus.append(Wort(a[i].t, a[i].x, a[i].y, a[i].w, a[i].h, hoch + (1 - hoch) * EINIG_BONUS))
        elif art == "replace" and (i2 - i1) == (j2 - j1):
            for i, j in zip(range(i1, i2), range(j1, j2)):
                wa, wb = a[i], b[j]
                pa, pb = wa.c * plausibel(wa.t), wb.c * plausibel(wb.t)
                gew, andere = (wa, wb) if pa >= pb else (wb, wa)
                aus.append(Wort(gew.t, wa.x, wa.y, wa.w, wa.h, min(max(pa, pb), UNSICHER - 0.05), alt=andere.t))
        else:
            teil_a, teil_b = a[i1:i2], b[j1:j2]
            ca = np.mean([w.c * plausibel(w.t) for w in teil_a]) if teil_a else -1
            cb = np.mean([w.c * plausibel(w.t) for w in teil_b]) if teil_b else -1
            gew, andere = (teil_a, teil_b) if ca >= cb else (teil_b, teil_a)
            alt = " ".join(w.t for w in andere) or None
            for k, w in enumerate(gew):
                aus.append(Wort(w.t, w.x, w.y, w.w, w.h, min(w.c, UNSICHER - 0.05),
                                alt=alt if k == 0 else None))
    aus.sort(key=lambda w: w.x)
    return aus


def _innen(w: Wort, box, rand: float) -> bool:
    x, y, bw, bh = box
    cx, cy = w.x + w.w / 2, w.y + w.h / 2
    return x - rand <= cx <= x + bw + rand and y - rand * 0.6 <= cy <= y + bh + rand * 0.6


def zusammenfuehren(paddle: list[Stueck] | None, tess_grau: list[Stueck], tess_sw: list[Stueck]) -> list[Stueck]:
    """Alle Lesarten → Stücke mit abgeglichenen Wörtern."""
    t_woerter = {"g": [(w, s) for s in tess_grau for w in s.woerter], "s": [(w, s) for s in tess_sw for w in s.woerter]}
    benutzt = {"g": set(), "s": set()}

    def tess_in(box, art):
        rand = max(4.0, box[3] * 0.25)
        treffer = []
        for nr, (w, _) in enumerate(t_woerter[art]):
            if nr not in benutzt[art] and _innen(w, box, rand):
                treffer.append((nr, w))
        for nr, _ in treffer:
            benutzt[art].add(nr)
        return sorted((w for _, w in treffer), key=lambda w: w.x)

    ergebnis: list[Stueck] = []
    if paddle:
        for st in paddle:
            if not st.woerter:
                continue
            tg, ts = tess_in(st.box, "g"), tess_in(st.box, "s")
            # die bessere Tesseract-Fassung für diese Zeile
            def guete(ws):
                return np.mean([w.c * plausibel(w.t) for w in ws]) if ws else 0.0
            tess = tg if guete(tg) >= guete(ts) else ts
            woerter = vergleiche(st.woerter, tess)
            ergebnis.append(Stueck(woerter, "m" if tess else "p").rahmen())
    else:
        for st in tess_grau:
            ts = tess_in(st.box, "s")
            for nr, (w, _) in enumerate(t_woerter["g"]):
                if any(w is x for x in st.woerter):
                    benutzt["g"].add(nr)
            ergebnis.append(Stueck(vergleiche(st.woerter, ts), "t").rahmen())
    # Reste: von Tesseract gelesen, aber keiner Zeile zugeordnet
    for art in ("g", "s"):
        rest = [(nr, w) for nr, (w, _) in enumerate(t_woerter[art]) if nr not in benutzt[art]]
        if not rest:
            continue
        nach_stueck: dict = {}
        for nr, w in rest:
            stueck = t_woerter[art][nr][1]
            nach_stueck.setdefault(id(stueck), []).append(w)
        for ws in nach_stueck.values():
            ws.sort(key=lambda w: w.x)
            neu = Stueck([Wort(w.t, w.x, w.y, w.w, w.h, min(w.c, 0.97)) for w in ws], "t").rahmen()
            # nicht doppelt: liegt das Stück über einem vorhandenen, entfällt es
            if any(_ueberdeckt(neu.box, s.box) for s in ergebnis):
                continue
            if neu.c * plausibel(neu.text) < 0.35:
                continue  # Flecken, Linien, Stempel – keine Schrift
            ergebnis.append(neu)
    return [s for s in ergebnis if s.woerter]


def _ueberdeckt(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy > 0.4 * max(aw * ah, 1)


# ---------------------------------------------------------------- Reihen und Text
def reihen(stuecke: list[Stueck]) -> list[list[Stueck]]:
    """Stücke gleicher Höhe zu Reihen (Tabellenzeilen), von oben nach unten, in der Reihe von links nach rechts."""
    rest = sorted(stuecke, key=lambda s: s.box[1] + s.box[3] / 2)
    aus: list[list[Stueck]] = []
    for s in rest:
        mitte = s.box[1] + s.box[3] / 2
        ziel = None
        for r in aus[-3:]:
            oben = min(x.box[1] for x in r)
            unten = max(x.box[1] + x.box[3] for x in r)
            hoehe = float(np.median([x.box[3] for x in r]))
            if oben - 0.15 * hoehe <= mitte <= unten + 0.15 * hoehe and abs(mitte - (oben + unten) / 2) < 0.6 * max(hoehe, s.box[3]):
                if not any(_ueberdeckt(s.box, x.box) for x in r):
                    ziel = r
        if ziel is None:
            aus.append([s])
        else:
            ziel.append(s)
    for r in aus:
        r.sort(key=lambda s: s.box[0])
    return aus


def seite_json(stuecke: list[Stueck], breite: int, hoehe: int, verfahren: list[str]) -> dict:
    rs = reihen(stuecke)
    return {
        "breite": int(breite), "hoehe": int(hoehe), "verfahren": verfahren,
        "reihen": [[{"q": s.q, "w": [w.als_liste() for w in s.woerter]} for s in r] for r in rs],
    }


def text_aus_json(daten: dict) -> str:
    zeilen = []
    for r in daten.get("reihen", []):
        zeilen.append("\t".join(" ".join(w[0] for w in s["w"]) for s in r))
    return "\n".join(zeilen)


def kennzahlen(daten: dict) -> dict:
    """Sicherheit der Seite (nach Zeichen gewichtet) und Zahl unsicherer Wörter."""
    woerter = [w for r in daten.get("reihen", []) for s in r for w in s["w"]]
    if not woerter:
        return {"sicherheit": None, "unsicher": 0, "woerter": 0}
    g = np.array([max(1, len(w[0])) for w in woerter], dtype=np.float32)
    c = np.array([w[5] for w in woerter], dtype=np.float32)
    return {"sicherheit": round(float((c * g).sum() / g.sum()), 3), "unsicher": int((c < UNSICHER).sum()),
            "woerter": len(woerter)}
