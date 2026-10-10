"""
Aus den Tabellen des Altsystems, den gespeicherten Zuordnungen und dem Bestand des EPM entsteht hier alles, was die
Oberfläche zeigt und was der Import schreibt – ohne Datenbank, als reine Berechnung:

- ``quelle``            Tabellen und Spalten des Dumps mit ihrer Zuordnung
- ``benutzer`` …        Zuordnungstabellen (Benutzer, Versorger, Werte, Präparate, gelöschte Patienten)
- ``auffaelligkeiten``  einzelne Werte, über die jemand entscheiden kann oder muss
- ``offen``             was den Import noch verhindert
- ``protokoll``         Importprotokoll nach den Regeln der Datenanalyse (ohne Namen, nur Nummern)
- ``zahlen``            Zählung alt gegen neu
- ``saetze``            die neuen Datensätze (für ``dienst.schreibe``)

Grundsätze: Nichts wird stillschweigend verworfen oder geraten. Was kein eigenes Feld hat oder nicht passt, steht
danach lesbar in der Bemerkung; was nicht übernommen wird, steht im Protokoll.
"""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher

from . import werte as W
from .felder import ANLAESSE, JE_NAME, KATEGORIEN, LAENGEN, MEDI_KATEGORIEN, PRAEPARATFELDER, RECHTE, ROLLEN, TABELLEN

GRUND = "Aus dem Altsystem übernommen"
ARTEN = ("wert", "leer", "unveraendert", "auslassen")
GEWICHTE_TAGE_STANDARD = 2      # Gewichte je Patient innerhalb von 2 Tagen zusammenfassen (Festlegung 09.10.2026)
GEWICHTE_TAGE_MAX = 14
GRUPPEN_ANZEIGE = 300           # so viele zusammengefasste Gruppen zeigt die Oberfläche einzeln
BEISPIELE = 20
KCAL_JE_G = (("glucose_g", Decimal(4)), ("aminosaeuren_g", Decimal(4)), ("lipide_g", Decimal("9.15")))


@dataclass
class Ergebnis:
    quelle: dict = field(default_factory=lambda: {"tabellen": [], "uebrig": [], "im_dump": []})
    benutzer: list = field(default_factory=list)
    versorger: list = field(default_factory=list)
    werte: dict = field(default_factory=dict)
    praeparate: dict = field(default_factory=dict)
    geloeschte: list = field(default_factory=list)
    auffaelligkeiten: list = field(default_factory=list)
    zusammengefasst: dict = field(default_factory=lambda: {"tage": 0, "gruppen": [], "anzahl": 0, "patienten": 0})
    offen: list = field(default_factory=list)
    protokoll: list = field(default_factory=list)
    zahlen: dict = field(default_factory=dict)
    saetze: dict = field(default_factory=dict)

    def als_dict(self) -> dict:
        """Für die Oberfläche (ohne die Datensätze selbst)."""
        return {"quelle": self.quelle, "benutzer": self.benutzer, "versorger": self.versorger, "werte": self.werte,
                "praeparate": self.praeparate, "geloeschte": self.geloeschte,
                "auffaelligkeiten": self.auffaelligkeiten, "zusammengefasst": self.zusammengefasst, "offen": self.offen, "protokoll": self.protokoll,
                "zahlen": self.zahlen}


# ---------------------------------------------------------------- kleine Hilfen
def _falte(s: str) -> str:
    s = (s or "").casefold()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return "".join(s.split())


def _gross(s: str) -> str:
    return " ".join("-".join(t[:1].upper() + t[1:] for t in w.split("-")) for w in s.split())


def name_aus_kuerzel(schluessel: str) -> tuple[str, str]:
    """„vorname.nachname“ → („Vorname“, „Nachname“); ohne Punkt gilt alles als Nachname."""
    teile = [t for t in re.split(r"[._\s]+", schluessel.split("@")[0]) if t]
    if len(teile) >= 2:
        return _gross(" ".join(teile[:-1])), _gross(teile[-1])
    return "", _gross(teile[0]) if teile else ""


def benutzername_aus(schluessel: str) -> str:
    return re.sub(r"\.{2,}", ".", re.sub(r"[^\w.@+-]", ".", schluessel)).strip(".")[:LAENGEN["benutzername"]]


_ZAHL_IM_TEXT = re.compile(r"\d+(?:[.,]\d+)?")


def norm_praeparat(text: str) -> str:
    """Vergleichsform eines Präparatnamens: klein, ohne ®/™, Zahlen einheitlich („10,0 %“ = „10%“)."""
    t = W.schluessel(text).replace("®", "").replace("™", "")

    def zahl(m):
        z = m.group(0).replace(",", ".")
        if "." in z:
            z = z.rstrip("0").rstrip(".")
        return z

    t = _ZAHL_IM_TEXT.sub(zahl, t)
    return re.sub(r"\s*%", "%", " ".join(t.split()))


_KONZ = re.compile(r"^(.*?\S)\s*(\d+(?:[.,]\d+)?)\s*%$")


def praeparat_vorschlag(text: str) -> dict:
    """Name und Konzentration aus einem Freitext wie „Glamin 13,4%“ – als Vorschlag für „neu anlegen“."""
    m = _KONZ.match(text.strip())
    if m:
        return {"name": m.group(1)[:LAENGEN["praeparat_name"]], "konzentration": f"{m.group(2).replace('.', ',')} %"}
    return {"name": text.strip()[:LAENGEN["praeparat_name"]], "konzentration": ""}


def _aehnlich(text: str, kandidaten: list, anzeige) -> list:
    n = norm_praeparat(text)
    bewertet = sorted(((SequenceMatcher(None, n, norm_praeparat(anzeige(k))).ratio(), k) for k in kandidaten),
                      key=lambda x: -x[0])
    return [k["id"] for r, k in bewertet[:3] if r >= 0.6]


def wertschluessel(roh) -> str:
    """Vergleichsform eines Rohwerts für Regeln: Text ohne Rand-Leerraum; NULL wie leer."""
    return "" if roh is None else str(roh).strip()


def gruppe(tab: str, feld: str, roh) -> str:
    """Schlüssel einer Gruppe gleicher Auffälligkeiten und einer Regel: Tabelle:Feld:Wert."""
    return f"{tab}:{feld}:{wertschluessel(roh)}"


def _dez(wert, stellen: int) -> Decimal:
    return wert.quantize(Decimal(1).scaleb(-stellen), rounding=ROUND_HALF_UP)


def _tag(d) -> str:
    return f"{d:%d.%m.%Y}"


class _Lauf:
    def __init__(self, tabellen, zuordnung, bestand, reparatur, heute):
        self.tabellen = tabellen or {}
        self.z = zuordnung if isinstance(zuordnung, dict) else {}
        self.bestand = bestand
        self.reparatur = reparatur
        self.heute = heute
        self.e = Ergebnis()
        self.q = {}                       # logische Tabelle → {"zeilen", "idx", "spalten"}
        self._protokoll = {}
        self.repariert = {}
        self.angewandt = {}               # Schlüssel → (Tabelle, Kennung, Feld, Rohwert, Entscheidung)
        # was die übernommenen Datensätze tatsächlich brauchen (nur das wird neu angelegt)
        self.genutzt = {"benutzer": set(), "auswahlwerte": set(), "praeparate": set()}
        self.korrekturen = self.z.get("korrekturen") if isinstance(self.z.get("korrekturen"), dict) else {}
        # Regeln je Wert: „alle Auffälligkeiten mit diesem Wert in diesem Feld“ (Schlüssel Tabelle:Feld:Wert).
        # Sie gelten für jede Zeile mit genau diesem Wert – auch im frischen Dump zum Go-live. Eine Entscheidung zu
        # einer einzelnen Zeile hat Vorrang.
        regeln = self.z.get("regeln") if isinstance(self.z.get("regeln"), dict) else {}
        self.regeln = {k: v for k, v in regeln.items() if isinstance(v, dict) and v.get("art") in ARTEN}
        self.regel_auslassen = {}         # Tabelle → {Feld: {Wert, …}}
        for k, v in self.regeln.items():
            if v["art"] == "auslassen" and k.count(":") >= 2:
                tab, feld, wert = k.split(":", 2)
                self.regel_auslassen.setdefault(tab, {}).setdefault(feld, set()).add(wert)
        tage = self.z.get("einstellungen", {}).get("gewichte_tage") if isinstance(self.z.get("einstellungen"), dict) else None
        self.gewichte_tage = tage if isinstance(tage, int) and 0 <= tage <= GEWICHTE_TAGE_MAX else GEWICHTE_TAGE_STANDARD
        self.grenzen = {k: Decimal(str(v)) for k, v in (bestand.get("grenzen") or {}).items()}
        self.test_ab = int(bestand.get("testnummer_ab") or 9001)
        self.geloescht_epm = {int(n) for n in bestand.get("geloeschte_nummern") or []}

    # ------------------------------------------------ Protokoll, offene Punkte, Auffälligkeiten
    def p(self, regel, bereich, stufe, text, kennung=None, anzahl=1):
        s = (regel, bereich, stufe, text)
        eintrag = self._protokoll.setdefault(s, {"regel": regel, "bereich": bereich, "stufe": stufe, "text": text,
                                                 "anzahl": 0, "beispiele": []})
        eintrag["anzahl"] += anzahl
        if kennung is not None and len(eintrag["beispiele"]) < BEISPIELE:
            eintrag["beispiele"].append(str(kennung))

    def nutze(self, art, ref):
        if ref and "neu" in ref:
            self.genutzt[art].add(ref["neu"])
        return ref

    # Auffälligkeiten, bei denen ein eingetragener Wert auch dann gilt, wenn er wieder auffällt
    WERT_GILT = {"unplausibel", "plz"}

    def sperre(self, bereich, text):
        if not any(o["bereich"] == bereich and o["text"] == text for o in self.e.offen):
            self.e.offen.append({"bereich": bereich, "text": text})

    def auffaellig(self, tab, kennung, feld, art, text, roh, standard, moeglich, eingabe="text", blockiert=False,
                   patient=None):
        """Auffälligkeit melden; liefert die wirksame Entscheidung (``standard``, wenn niemand entschieden hat)."""
        schluessel = f"{tab}:{kennung}:{feld}"
        k = self._korrektur(tab, kennung, feld, roh)
        if k and k.get("regel") and k["art"] not in moeglich:
            k = None                      # die Regel passt nicht zu dieser Art von Auffälligkeit
        entschieden = k["art"] if k and k["art"] in moeglich else None
        titel = feld
        try:
            titel = JE_NAME[tab].feld(feld).titel
        except (KeyError, StopIteration):
            pass
        # Ein eingetragener Wert, der dieselbe Auffälligkeit wieder auslöst, ist keine Entscheidung: Der Punkt bleibt
        # offen, bis ein brauchbarer Wert oder eine andere Entscheidung eingetragen ist. Ausnahme: „unplausibel“ und
        # die vierstellige PLZ – dort ist ein bewusst eingetragener Wert die Entscheidung.
        untauglich = (entschieden == "wert" and schluessel in self.angewandt and art not in self.WERT_GILT)
        if untauglich:
            text = f"{text} Der eingetragene Wert „{k.get('wert', '')}“ behebt das nicht."
            entschieden = None
        offen = (blockiert and entschieden is None) or untauglich
        self.e.auffaelligkeiten.append({
            "schluessel": schluessel, "tabelle": tab, "tabelle_titel": JE_NAME[tab].titel, "id": str(kennung),
            "patient": patient, "feld": feld, "feld_titel": titel, "art": art, "text": text,
            "wert": None if roh is None else str(roh)[:200], "roh": None if roh is None else str(roh),
            "standard": standard, "moeglich": moeglich,
            "eingabe": eingabe, "blockiert": offen, "entscheidung": k if entschieden or untauglich else None,
            "gruppe": gruppe(tab, feld, roh), "regel": self.regeln.get(gruppe(tab, feld, roh)),
        })
        if offen:
            self.sperre("auffaelligkeiten", "Es gibt Auffälligkeiten, über die noch entschieden werden muss.")
        return entschieden or standard

    def _korrektur(self, tab, kennung, feld, roh):
        """Gespeicherte Entscheidung zu einem Wert – nur gültig, solange der Wert im Dump derselbe ist. Ohne
        Entscheidung zur einzelnen Zeile gilt eine Regel für diesen Wert (``regel`` nennt dann ihren Schlüssel)."""
        k = self.korrekturen.get(f"{tab}:{kennung}:{feld}")
        if isinstance(k, dict) and k.get("art") in ARTEN and k.get("alt") == (None if roh is None else str(roh)):
            return k
        g = gruppe(tab, feld, roh)
        r = self.regeln.get(g)
        if r is None:
            return None
        return {**{x: r[x] for x in ("art", "wert") if x in r}, "alt": None if roh is None else str(roh), "regel": g}

    def lies(self, tab, kennung, feld, zeile):
        """Rohwert eines Felds – mit eingetragener Korrektur („wert“ ersetzt, „leer“ leert).
        Liefert (wirksamer Wert, Rohwert des Dumps)."""
        roh = self.roh(tab, zeile, feld)
        k = self._korrektur(tab, kennung, feld, roh)
        if k and k["art"] in ("wert", "leer"):
            self.angewandt[f"{tab}:{kennung}:{feld}"] = (tab, kennung, feld, roh, k)
            return (str(k.get("wert", "")) if k["art"] == "wert" else None), roh
        return roh, roh

    def _auslassend(self, tab, kennung, zeile):
        """Felder dieser Zeile, für die „nicht übernehmen“ gilt – einzeln entschieden oder per Regel für den Wert.
        → [(Feld, Rohwert, Entscheidung)]"""
        felder = set()
        vor = f"{tab}:{kennung}:"
        for schluessel, k in self.korrekturen.items():
            if schluessel.startswith(vor) and isinstance(k, dict) and k.get("art") == "auslassen":
                felder.add(schluessel[len(vor):])
        for feld, werte in self.regel_auslassen.get(tab, {}).items():
            if feld in self.q[tab]["idx"] and wertschluessel(self.roh(tab, zeile, feld)) in werte:
                felder.add(feld)
        aus = []
        for feld in sorted(felder):
            roh = self.roh(tab, zeile, feld)
            k = self._korrektur(tab, kennung, feld, roh)
            if k and k.get("regel") and "auslassen" not in (self.regeln[k["regel"]].get("moeglich") or ()):
                continue                  # „nicht übernehmen“ ist für diese Auffälligkeit nicht vorgesehen
            if k and k["art"] == "auslassen":
                aus.append((feld, roh, k))
        return aus

    def ausgelassen(self, tab, kennung, zeile) -> bool:
        """Gilt für ein Feld dieser Zeile „nicht übernehmen“ (einzeln entschieden oder per Regel)?"""
        return bool(self._auslassend(tab, kennung, zeile))

    # ------------------------------------------------ Quelle: Tabellen und Spalten
    def roh(self, tab, zeile, feld):
        i = self.q[tab]["idx"].get(feld)
        return None if i is None else zeile[i]

    def text(self, tab, zeile, feld, wert=...):
        return W.text(self.roh(tab, zeile, feld) if wert is ... else wert)[0]

    def kennung(self, tab, zeile, nr) -> str:
        feld = "nummer" if tab == "patienten" else "benutzername" if tab == "benutzerdaten" else "id"
        w = self.roh(tab, zeile, feld)
        return str(w).strip() if w not in (None, "") else f"z{nr}"

    def quelle(self):
        zt = self.z.get("tabellen") if isinstance(self.z.get("tabellen"), dict) else {}
        zs = self.z.get("spalten") if isinstance(self.z.get("spalten"), dict) else {}
        zi = self.z.get("spalten_ignoriert") if isinstance(self.z.get("spalten_ignoriert"), dict) else {}
        ti = {str(x).casefold() for x in (self.z.get("tabellen_ignoriert") or []) if isinstance(x, str)}
        nach_klein = {n.casefold(): n for n in self.tabellen}
        belegt = set()
        for t in TABELLEN:
            wahl = zt.get(t.name)
            vorschlag = next((nach_klein[v] for v in t.vorschlag if v in nach_klein), None)
            if wahl == "":
                name, quelle_art = None, "ohne"
            elif isinstance(wahl, str) and wahl.casefold() in nach_klein:
                name, quelle_art = nach_klein[wahl.casefold()], "gewaehlt"
            else:
                name, quelle_art = vorschlag, "vorschlag"
            if name in belegt:
                name = None
            if name:
                belegt.add(name)
            dump = self.tabellen.get(name) if name else None
            spalten = list(dump["spalten"]) if dump else []
            klein = {s.casefold(): i for i, s in enumerate(spalten)}
            gewaehlt = zs.get(t.name) if isinstance(zs.get(t.name), dict) else {}
            idx, vergeben, felder = {}, set(), []
            # erst die ausdrücklichen Zuordnungen, dann die Vorschläge für den Rest
            for f in t.felder:
                w = gewaehlt.get(f.name)
                if isinstance(w, str) and w.casefold() in klein and klein[w.casefold()] not in vergeben:
                    idx[f.name] = klein[w.casefold()]
                    vergeben.add(idx[f.name])
            for f in t.felder:
                w = gewaehlt.get(f.name)
                if f.name in idx:
                    art = "gewaehlt"
                elif w == "":
                    idx[f.name], art = None, "ohne"
                else:
                    i = next((klein[v] for v in f.vorschlag if v in klein and klein[v] not in vergeben), None)
                    idx[f.name], art = i, "vorschlag" if i is not None else "fehlt"
                    if i is not None:
                        vergeben.add(i)
                felder.append({"name": f.name, "titel": f.titel, "pflicht": f.pflicht, "hinweis": f.hinweis,
                               "spalte": spalten[idx[f.name]] if idx[f.name] is not None else None, "art": art})
                if dump is not None and f.pflicht and idx[f.name] is None:
                    self.sperre("spalten", f"Tabelle „{t.titel}“: Für „{f.titel}“ ist keine Spalte zugeordnet."
                                           + (f" {f.hinweis[0].upper() + f.hinweis[1:]}." if f.name == "zeit" else ""))
            ignoriert = {str(x).casefold() for x in (zi.get(t.name) or []) if isinstance(x, str)}
            entfernt = {s.casefold() for s in (dump or {}).get("entfernt", [])}
            rest = []
            for i, s in enumerate(spalten):
                if i in vergeben:
                    continue
                if s.casefold() in entfernt:
                    rest.append({"spalte": s, "art": "kennwort", "grund": "Passwörter werden nicht übernommen (Regel 1)"})
                elif s.casefold() in t.ohne:
                    rest.append({"spalte": s, "art": "bekannt", "grund": t.ohne[s.casefold()]})
                elif s.casefold() in ignoriert:
                    rest.append({"spalte": s, "art": "ignoriert", "grund": "bewusst nicht übernommen"})
                else:
                    gefuellt = sum(1 for z in dump["zeilen"] if z[i] not in (None, ""))
                    rest.append({"spalte": s, "art": "offen", "grund": f"{gefuellt} gefüllte Werte"})
                    self.sperre("spalten", f"Tabelle „{t.titel}“: Die Spalte „{s}“ ist keinem Feld zugeordnet – "
                                           f"bitte zuordnen oder „nicht übernehmen“ wählen.")
            if dump is None and quelle_art != "ohne":
                self.sperre("spalten", f"Die Tabelle „{t.titel}“ fehlt im Dump – bitte zuordnen oder „nicht vorhanden“ wählen.")
            self.q[t.name] = {"zeilen": self._repariert(t.name, dump["zeilen"], idx) if dump else [], "idx": idx,
                              "spalten": spalten}
            self.e.quelle["tabellen"].append({"name": t.name, "titel": t.titel, "ziel": t.ziel, "tabelle": name, "art": quelle_art,
                                  "zeilen": len(dump["zeilen"]) if dump else 0, "felder": felder, "rest": rest,
                                  "spalten": spalten})
        uebrig = []
        for n, dump in self.tabellen.items():
            if n in belegt:
                continue
            offen = n.casefold() not in ti
            uebrig.append({"tabelle": n, "zeilen": len(dump["zeilen"]), "art": "offen" if offen else "ignoriert"})
            if offen:
                self.sperre("spalten", f"Die Tabelle „{n}“ des Dumps ist keiner Tabelle zugeordnet – bitte zuordnen "
                                       f"oder „nicht übernehmen“ wählen.")
        self.e.quelle["uebrig"] = uebrig
        self.e.quelle["im_dump"] = sorted(self.tabellen)

    def _repariert(self, tab, zeilen, idx):
        """Doppelt kodierte Texte (Regel 3) einmal reparieren – nur in den Spalten, die übernommen werden."""
        if self.reparatur is None:
            return zeilen
        spalten = sorted({i for i in idx.values() if i is not None})
        aus, anzahl, beispiele = [], 0, []
        ki = idx.get("nummer" if tab == "patienten" else "benutzername" if tab == "benutzerdaten" else "id")
        for z in zeilen:
            neu = None
            for i in spalten:
                w = z[i]
                if w is not None and W.VERDACHT.search(w):
                    r = self.reparatur(w)
                    if r != w:
                        if neu is None:
                            neu = list(z)
                        neu[i] = r
                        anzahl += 1
            if neu is not None and ki is not None and z[ki] not in (None, "") and len(beispiele) < BEISPIELE:
                beispiele.append(str(z[ki]).strip())
            aus.append(neu if neu is not None else z)
        if anzahl:
            self.repariert[tab] = (anzahl, beispiele)
        return aus

    # ------------------------------------------------ Benutzer
    def benutzer(self):
        namen = {}   # schlüssel → {"text", "rechte", "vorname", "nachname", "anzahl": {tabelle: n}}

        def merke(roh, tab, **zusatz):
            t, _ = W.text(roh)
            if W.ist_leer(t):
                return
            n = namen.setdefault(W.schluessel(t), {"text": t, "rechte": None, "vorname": "", "nachname": "",
                                                   "konto": False, "anzahl": {}})
            if tab:
                n["anzahl"][tab] = n["anzahl"].get(tab, 0) + 1
            n.update(zusatz)

        for z in self.q["benutzerdaten"]["zeilen"]:
            merke(self.roh("benutzerdaten", z, "benutzername"), None, konto=True,
                  rechte=(str(self.roh("benutzerdaten", z, "rechte")).strip()
                          if self.roh("benutzerdaten", z, "rechte") is not None else None),
                  vorname=self.text("benutzerdaten", z, "vorname"), nachname=self.text("benutzerdaten", z, "nachname"))
        for tab, feldnamen in (("patienten", ("bearbeiter",)), ("gewichte", ("bearbeiter",)),
                               ("kontakte", ("bearbeiter",)), ("infusionen", ("ersteller", "bearbeiter"))):
            for z in self.q[tab]["zeilen"]:
                for f in feldnamen:
                    merke(self.roh(tab, z, f), tab)

        vorhanden = [b for b in self.bestand.get("benutzer", []) if not b.get("ist_test")]
        je_id = {b["id"]: b for b in vorhanden}
        je_name = {b["username"].casefold(): b for b in vorhanden}
        vergeben = {b["username"].casefold() for b in self.bestand.get("benutzer", [])}
        entscheidungen = self.z.get("benutzer") if isinstance(self.z.get("benutzer"), dict) else {}
        self.benutzer_ref = {}
        neu = {}
        for schluessel in sorted(namen):
            n = namen[schluessel]
            passend = [b for b in vorhanden if b["username"].casefold() == schluessel
                       or (_falte(b.get("nachname")) and _falte(schluessel)
                           == f"{_falte(b.get('vorname'))}.{_falte(b.get('nachname'))}")]
            vor, nach = (n["vorname"], n["nachname"]) if n["nachname"] else name_aus_kuerzel(n["text"])
            if len(passend) == 1:
                vorschlag = {"art": "benutzer", "id": passend[0]["id"]}
            elif n["konto"]:
                vorschlag = {"art": "konto", "benutzername": benutzername_aus(n["text"]), "vorname": vor,
                             "nachname": nach, "titel": "", "rolle": RECHTE.get(n["rechte"] or "", "")}
            else:
                vorschlag = {"art": "historisch", "benutzername": benutzername_aus(n["text"]), "vorname": vor,
                             "nachname": nach, "titel": ""}
            wahl = entscheidungen.get(schluessel)
            wirksam, fehler = vorschlag, ""
            if isinstance(wahl, dict) and wahl.get("art") in ("benutzer", "konto", "historisch", "ohne"):
                wirksam = {**(vorschlag if vorschlag["art"] == wahl["art"] else {}), **wahl}
                if wahl["art"] in ("konto", "historisch"):
                    for k, v in (("benutzername", benutzername_aus(n["text"])), ("vorname", vor), ("nachname", nach),
                                 ("titel", ""), ("rolle", RECHTE.get(n["rechte"] or "", ""))):
                        wirksam.setdefault(k, v)
                    if wahl["art"] == "historisch":
                        wirksam.pop("rolle", None)
            if wirksam["art"] == "benutzer":
                if wirksam.get("id") not in je_id:
                    fehler = "Der gewählte Benutzer ist im EPM nicht (mehr) vorhanden."
                else:
                    self.benutzer_ref[schluessel] = {"id": wirksam["id"]}
            elif wirksam["art"] in ("konto", "historisch"):
                name = str(wirksam.get("benutzername") or "").strip()
                wirksam["benutzername"] = name
                if not name or name != benutzername_aus(name):
                    fehler = "Benutzername fehlt oder enthält unzulässige Zeichen (erlaubt: Buchstaben, Ziffern, . _ @ + -)."
                elif name.casefold() in je_name:
                    fehler = f"Den Benutzernamen „{name}“ gibt es im EPM schon – bitte „vorhandener Benutzer“ wählen."
                elif name.casefold() in vergeben:
                    fehler = f"Den Benutzernamen „{name}“ trägt im EPM ein Testbenutzer – bitte einen anderen Benutzernamen eintragen."
                elif wirksam["art"] == "konto" and wirksam.get("rolle") not in ROLLEN:
                    fehler = "Bitte die Rolle des neuen Kontos wählen."
                elif any(len(str(wirksam.get(k) or "")) > g for k, g in (("vorname", 150), ("nachname", 150), ("titel", 40))):
                    fehler = "Vorname, Nachname oder Titel ist zu lang."
                else:
                    andere = neu.get(name.casefold())
                    if andere and andere["historisch"] != (wirksam["art"] == "historisch"):
                        fehler = f"„{name}“ soll zugleich als Konto und als historischer Benutzer angelegt werden."
                    else:
                        neu.setdefault(name.casefold(), {
                            "schluessel": name.casefold(), "benutzername": name,
                            "vorname": str(wirksam.get("vorname") or "").strip(),
                            "nachname": str(wirksam.get("nachname") or "").strip(),
                            "titel": str(wirksam.get("titel") or "").strip(),
                            "rolle": wirksam.get("rolle") if wirksam["art"] == "konto" else "betrachter",
                            "historisch": wirksam["art"] == "historisch"})
                        self.benutzer_ref[schluessel] = {"neu": name.casefold()}
            else:
                self.benutzer_ref[schluessel] = None
            if fehler:
                self.sperre("benutzer", f"Benutzer „{n['text']}“: {fehler}")
            self.e.benutzer.append({
                "schluessel": schluessel, "name": n["text"], "im_altsystem_konto": n["konto"], "rechte": n["rechte"],
                "anzahl": n["anzahl"], "eintraege": sum(n["anzahl"].values()), "vorschlag": vorschlag,
                "entscheidung": wahl if isinstance(wahl, dict) else None, "wirksam": wirksam, "fehler": fehler,
                "aehnlich": [b["id"] for b in vorhanden if b not in passend and _falte(b.get("nachname"))
                             and _falte(b.get("nachname")) in _falte(schluessel)][:3],
            })
        self.e.saetze["benutzer"] = list(neu.values())

    def bearbeiter(self, tab, zeile, feld):
        t = self.text(tab, zeile, feld)
        return None if W.ist_leer(t) else self.nutze("benutzer", self.benutzer_ref.get(W.schluessel(t)))

    # ------------------------------------------------ Versorger
    def versorger(self):
        vorhanden = self.bestand.get("versorger", [])
        je_id = {v["id"]: v for v in vorhanden}
        je_name = {W.schluessel(v["name"]): v for v in vorhanden}
        ansprech = {}
        for a in self.bestand.get("ansprechpartner", []):
            ansprech[(a["versorger"], W.schluessel(a["name"]))] = a
        entscheidungen = self.z.get("versorger") if isinstance(self.z.get("versorger"), dict) else {}
        genutzt = {}
        for z in self.q["patienten"]["zeilen"]:
            w = self.roh("patienten", z, "versorger")
            if w not in (None, ""):
                genutzt[str(w).strip()] = genutzt.get(str(w).strip(), 0) + 1
        self.versorger_ref = {}   # Nummer im Altsystem → {"versorger": ref|None, "ansprechpartner": ref|None, "kein": bool}
        neu_v, neu_a = {}, {}
        for nr, z in enumerate(self.q["versorger"]["zeilen"], 1):
            kennung = self.kennung("versorger", z, nr)
            firma, name = self.text("versorger", z, "firma"), self.text("versorger", z, "name")
            email, tel = self.text("versorger", z, "email"), self.text("versorger", z, "tel")
            firma, name = ("" if W.ist_leer(firma) else firma), ("" if W.ist_leer(name) else name)
            if not firma and not name:
                vorschlag = {"art": "leer"}
            else:
                # nicht kürzen: Ein zu langer Name wird unten als offener Punkt gemeldet und von Hand gekürzt
                vname = firma or name
                aname = name if firma else ""
                treffer = je_name.get(W.schluessel(vname))
                vorschlag = ({"art": "vorhanden", "id": treffer["id"], "ansprechpartner": aname} if treffer
                             else {"art": "neu", "versorger": vname, "ansprechpartner": aname})
            wahl = entscheidungen.get(kennung)
            wirksam, fehler = vorschlag, ""
            if isinstance(wahl, dict) and wahl.get("art") in ("neu", "vorhanden", "kein", "leer"):
                wirksam = dict(wahl)
                if wahl["art"] in ("neu", "vorhanden"):
                    wirksam.setdefault("ansprechpartner", name if firma else "")
            ref = {"versorger": None, "ansprechpartner": None, "kein": False}
            notiz = ""
            if wirksam["art"] == "kein":
                ref["kein"] = True
            elif wirksam["art"] in ("neu", "vorhanden"):
                aname = str(wirksam.get("ansprechpartner") or "").strip()
                if len(aname) > LAENGEN["ansprechpartner_name"]:
                    fehler = "Der Name des Ansprechpartners ist zu lang (höchstens 150 Zeichen)."
                if wirksam["art"] == "vorhanden":
                    if wirksam.get("id") not in je_id:
                        fehler = "Der gewählte Versorger ist im EPM nicht (mehr) vorhanden."
                    else:
                        ref["versorger"] = {"id": wirksam["id"]}
                        vschluessel = ("id", wirksam["id"])
                else:
                    vname = str(wirksam.get("versorger") or "").strip()
                    wirksam["versorger"] = vname
                    if not vname or len(vname) > LAENGEN["versorger_name"]:
                        fehler = "Bitte den Namen des Versorgers angeben (höchstens 150 Zeichen)."
                    elif W.schluessel(vname) in je_name:
                        # gleicher Name wie ein Versorger im EPM: der ist gemeint (Namen sind eindeutig)
                        ref["versorger"] = {"id": je_name[W.schluessel(vname)]["id"]}
                        vschluessel = ("id", ref["versorger"]["id"])
                    else:
                        s = W.schluessel(vname)
                        satz = neu_v.setdefault(s, {"schluessel": s, "name": vname, "telefon": "", "email": "", "notiz": ""})
                        ref["versorger"] = {"neu": s}
                        vschluessel = ("neu", s)
                        if not aname:
                            # Telefon und E-Mail gehören dann zum Versorger selbst
                            satz_tel, satz_mail, notiz = self._kontaktdaten(tel, email)
                            if satz_tel and not satz["telefon"]:
                                satz["telefon"] = satz_tel
                            elif satz_tel and satz_tel != satz["telefon"]:
                                notiz = f"{notiz} Weitere Telefonnummer laut Altsystem: {satz_tel}.".strip()
                            if satz_mail and not satz["email"]:
                                satz["email"] = satz_mail
                            elif satz_mail and satz_mail != satz["email"]:
                                notiz = f"{notiz} Weitere E-Mail laut Altsystem: {satz_mail}.".strip()
                            if notiz:
                                satz["notiz"] = f"{satz['notiz']} {notiz}".strip()
                if not fehler and aname:
                    da = ansprech.get((vschluessel[1], W.schluessel(aname))) if vschluessel[0] == "id" else None
                    if da:
                        ref["ansprechpartner"] = {"id": da["id"]}
                    else:
                        s = f"{vschluessel[0]}:{vschluessel[1]}:{W.schluessel(aname)}"
                        if s not in neu_a:
                            a_tel, a_mail, a_notiz = self._kontaktdaten(tel, email)
                            neu_a[s] = {"schluessel": s, "versorger": ref["versorger"], "name": aname, "telefon": a_tel,
                                        "email": a_mail, "notiz": a_notiz}
                        ref["ansprechpartner"] = {"neu": s}
                elif not fehler and wirksam["art"] == "vorhanden" and (tel or email):
                    self.p(0, "versorger", "info", "Telefon/E-Mail aus dem Altsystem nicht übernommen, weil der Versorger "
                                                   "im EPM schon gepflegt ist.", kennung)
            if fehler:
                ref = {"versorger": None, "ansprechpartner": None, "kein": False}
                self.sperre("versorger", f"Versorger {kennung}: {fehler}")
            self.versorger_ref[kennung] = ref
            self.e.versorger.append({
                "schluessel": kennung, "firma": firma, "name": name, "email": email, "tel": tel,
                "patienten": genutzt.get(kennung, 0), "vorschlag": vorschlag,
                "entscheidung": wahl if isinstance(wahl, dict) else None, "wirksam": wirksam, "fehler": fehler,
            })
        self.e.saetze["versorger"] = list(neu_v.values())
        self.e.saetze["ansprechpartner"] = list(neu_a.values())
        self.e.zahlen["versorger"] = {"alt": len(self.q["versorger"]["zeilen"]), "neu": len(neu_v),
                                      "ansprechpartner_neu": len(neu_a)}

    def _kontaktdaten(self, tel, email):
        """Telefon und E-Mail passend zu den Zielfeldern; was nicht passt, steht in der Notiz."""
        notiz = []
        if len(tel) > LAENGEN["telefon"]:
            notiz.append(f"Telefon laut Altsystem: {tel}")
            tel = ""
        if email and not W.email_gueltig(email):
            notiz.append(f"E-Mail laut Altsystem: {email}")
            email = ""
        return ("" if W.ist_leer(tel) else tel), email, ". ".join(notiz) + ("." if notiz else "")

    # ------------------------------------------------ Wertelisten: Katheter, Nickelallergie, Geschlecht
    def wertelisten(self):
        entscheidungen = self.z.get("werte") if isinstance(self.z.get("werte"), dict) else {}

        def sammle(feld):
            gefunden = {}
            for z in self.q["patienten"]["zeilen"]:
                t = self.text("patienten", z, feld)
                s = W.schluessel(t)
                g = gefunden.setdefault(s, {"text": t, "anzahl": 0})
                g["anzahl"] += 1
            return gefunden

        # Katheter (Regel 9)
        liste = self.bestand.get("katheter", [])
        je_id = {k["id"]: k for k in liste}
        je_wert = {W.schluessel(k["wert"]): k for k in liste}
        wahl_k = entscheidungen.get("katheter") if isinstance(entscheidungen.get("katheter"), dict) else {}
        self.katheter_ref, neu, zeilen = {}, {}, []
        for s, g in sorted(sammle("katheter").items()):
            if not s or s == "unbekannt" or W.ist_leer(g["text"]):
                vorschlag = {"art": "leer"}
            elif s in ("nein", "kein", "keiner", "ohne"):
                vorschlag = {"art": "kein"}
            elif s in je_wert:
                vorschlag = {"art": "wert", "id": je_wert[s]["id"]}
            else:
                vorschlag = {"art": "neu", "wert": g["text"]}
            wahl = wahl_k.get(s)
            wirksam, fehler = vorschlag, ""
            if isinstance(wahl, dict) and wahl.get("art") in ("wert", "neu", "kein", "leer"):
                wirksam = dict(wahl)
            ref = {"katheter": None, "kein": wirksam["art"] == "kein"}
            if wirksam["art"] == "wert":
                if wirksam.get("id") not in je_id:
                    fehler = "Der gewählte Katheter ist in der Auswahlliste nicht (mehr) vorhanden."
                else:
                    ref["katheter"] = {"id": wirksam["id"]}
            elif wirksam["art"] == "neu":
                wert = str(wirksam.get("wert") or "").strip()
                wirksam["wert"] = wert
                if not wert or len(wert) > LAENGEN["auswahlwert"]:
                    fehler = "Bitte die Bezeichnung angeben (höchstens 100 Zeichen)."
                elif W.schluessel(wert) in je_wert:
                    ref["katheter"] = {"id": je_wert[W.schluessel(wert)]["id"]}
                else:
                    neu.setdefault(W.schluessel(wert), {"schluessel": W.schluessel(wert), "liste": "katheter", "wert": wert})
                    ref["katheter"] = {"neu": W.schluessel(wert)}
            if fehler:
                self.sperre("werte", f"Katheter „{g['text']}“: {fehler}")
            self.katheter_ref[s] = ref
            zeilen.append({"schluessel": s, "text": g["text"], "anzahl": g["anzahl"], "vorschlag": vorschlag,
                           "entscheidung": wahl if isinstance(wahl, dict) else None, "wirksam": wirksam, "fehler": fehler})
        self.e.werte["katheter"] = zeilen
        self.e.saetze["auswahlwerte"] = list(neu.values())

        # Nickelallergie (Regel 10) und Geschlecht: feste Zielwerte
        fest = {
            "nickel": ("Nickelallergie", {"ja": "ja", "j": "ja", "nein": "nein", "n": "nein", "unbekannt": "unbekannt",
                                          "": "unbekannt"}, ("ja", "nein", "unbekannt")),
            "geschlecht": ("Geschlecht", {"w": "w", "weiblich": "w", "f": "w", "m": "m", "männlich": "m",
                                          "maennlich": "m", "d": "d", "divers": "d", "": "", "unbekannt": ""},
                           ("w", "m", "d", "")),
        }
        self.wert_ref = {}
        for feld, (titel, standard, erlaubt) in fest.items():
            wahl_f = entscheidungen.get(feld) if isinstance(entscheidungen.get(feld), dict) else {}
            zeilen, self.wert_ref[feld] = [], {}
            for s, g in sorted(sammle(feld).items()):
                if W.ist_leer(g["text"]):
                    s_std = standard[""]
                else:
                    s_std = standard.get(s)
                wahl = wahl_f.get(s)
                wirksam = wahl if isinstance(wahl, str) and wahl in erlaubt else s_std
                if wirksam is None:
                    self.sperre("werte", f"{titel} „{g['text']}“: Bitte zuordnen.")
                self.wert_ref[feld][s] = wirksam
                zeilen.append({"schluessel": s, "text": g["text"], "anzahl": g["anzahl"], "vorschlag": s_std,
                               "entscheidung": wahl if isinstance(wahl, str) else None, "wirksam": wirksam,
                               "fehler": "" if wirksam is not None else "Bitte zuordnen."})
            self.e.werte[feld] = zeilen

    # ------------------------------------------------ Präparate (Regel 16)
    def praeparate(self):
        entscheidungen = self.z.get("praeparate") if isinstance(self.z.get("praeparate"), dict) else {}
        bestand = self.bestand.get("praeparate", [])
        je_id = {p["id"]: p for p in bestand}

        def anzeige(p):
            return f"{p['name']} {p['konzentration']}".strip()

        self.praep_ref = {}
        neu = {}
        for feld, (titel, kategorie, mehrere) in PRAEPARATFELDER.items():
            texte = {}
            for z in self.q["infusionen"]["zeilen"]:
                for teil in self.teile(self.text("infusionen", z, feld), mehrere):
                    g = texte.setdefault(W.schluessel(teil), {"text": teil, "anzahl": 0})
                    g["anzahl"] += 1
            kategorien = (kategorie,) if kategorie else MEDI_KATEGORIEN
            kandidaten = [p for p in bestand if p["kategorie"] in kategorien]
            je_norm = {}
            for p in kandidaten:
                je_norm.setdefault(norm_praeparat(anzeige(p)), []).append(p)
            je_name = {}
            for p in kandidaten:
                je_name.setdefault(norm_praeparat(p["name"]), []).append(p)
            wahl_f = entscheidungen.get(feld) if isinstance(entscheidungen.get(feld), dict) else {}
            zeilen, self.praep_ref[feld] = [], {}
            for s, g in sorted(texte.items()):
                n = norm_praeparat(g["text"])
                treffer = je_norm.get(n) or je_name.get(n) or []
                vorschlag = {"art": "praeparat", "id": treffer[0]["id"]} if len(treffer) == 1 else None
                wahl = wahl_f.get(s)
                wirksam, fehler, ref = vorschlag, "", None
                if isinstance(wahl, dict) and wahl.get("art") in ("praeparat", "neu", "bemerkung", "leer"):
                    wirksam = dict(wahl)
                if wirksam is None:
                    fehler = "Bitte zuordnen."
                elif wirksam["art"] == "praeparat":
                    p = je_id.get(wirksam.get("id"))
                    if p is None:
                        fehler = "Das gewählte Präparat ist im EPM nicht (mehr) vorhanden."
                    elif p["kategorie"] not in kategorien:
                        fehler = f"Das gewählte Präparat gehört nicht zur Kategorie „{KATEGORIEN.get(kategorie, kategorie)}“."
                    else:
                        ref = {"id": p["id"], "kategorie": p["kategorie"]}
                elif wirksam["art"] == "neu":
                    name = str(wirksam.get("name") or "").strip()
                    konz = str(wirksam.get("konzentration") or "").strip()
                    kat = kategorie or wirksam.get("kategorie")
                    wirksam.update(name=name, konzentration=konz)
                    if not name or len(name) > LAENGEN["praeparat_name"] or len(konz) > LAENGEN["praeparat_konzentration"]:
                        fehler = "Bitte den Namen angeben (höchstens 150 Zeichen; Konzentration höchstens 60)."
                    elif kat not in kategorien:
                        fehler = "Bitte die Kategorie des neuen Präparats wählen."
                    else:
                        da = next((p for p in bestand if p["kategorie"] == kat and W.schluessel(p["name"]) == W.schluessel(name)
                                   and W.schluessel(p["konzentration"]) == W.schluessel(konz)), None)
                        if da:
                            ref = {"id": da["id"], "kategorie": kat}
                        else:
                            ps = f"{kat}|{W.schluessel(name)}|{W.schluessel(konz)}"
                            neu.setdefault(ps, {"schluessel": ps, "kategorie": kat, "name": name, "konzentration": konz})
                            ref = {"neu": ps, "kategorie": kat}
                elif wirksam["art"] == "bemerkung":
                    ref = {"bemerkung": True}
                else:
                    ref = {"leer": True}
                if fehler:
                    self.sperre("praeparate", f"{titel} „{g['text']}“: {fehler}")
                self.praep_ref[feld][s] = ref
                zeilen.append({"schluessel": s, "text": g["text"], "anzahl": g["anzahl"], "vorschlag": vorschlag,
                               "neu_vorschlag": praeparat_vorschlag(g["text"]),
                               "aehnlich": [] if vorschlag else _aehnlich(g["text"], kandidaten, anzeige),
                               "entscheidung": wahl if isinstance(wahl, dict) else None, "wirksam": wirksam,
                               "fehler": fehler})
            self.e.praeparate[feld] = {"titel": titel, "kategorie": kategorie, "kategorien": list(kategorien),
                                       "zeilen": zeilen}
        self.e.saetze["praeparate"] = list(neu.values())

    @staticmethod
    def teile(text, mehrere):
        """Freitext eines Präparatfelds in einzelne Angaben („A | B“ bei Vitaminen); Platzhalter entfallen (Regel 7)."""
        teile = re.split(r"\s*\|\s*", text) if mehrere else [text]
        return [t.strip() for t in teile if not W.ist_leer(t)]

    # ------------------------------------------------ Formatierte Texte (Regel 11)
    def html(self, tab, kennung, text, was) -> str:
        """Text des Altsystems als formatierter Text – mit Protokoll, wenn er HTML enthält. Nichts geht still verloren:
        Linkziele und Bilder bleiben als Text stehen; HTML ohne lesbaren Inhalt wird als Quelltext übernommen."""
        inhalt, war_html = W.als_html(text)
        if not war_html:
            return inhalt
        if W.ohne_lesbaren_text(inhalt):
            self.p(11, tab, "hinweis", f"{was} enthält nur HTML ohne lesbaren Text → der Quelltext steht als Text im Feld.", kennung)
            return W.als_html(text, als_text=True)[0]
        self.p(11, tab, "info", f"{was} enthält HTML → als formatierter Text übernommen und bereinigt.", kennung)
        if W.BILD.search(text) or W.LINK.search(text):
            self.p(11, tab, "hinweis", f"{was} enthält Links oder Bilder: Linkziele stehen als Text hinter dem Linktext, "
                                       f"Bilder werden nicht übernommen (Vermerk im Text).", kennung)
        return inhalt

    # ------------------------------------------------ Texte mit begrenzter Länge
    def begrenzt(self, text, laenge, titel, extras, tab, kennung):
        """Passt der Text nicht ins Zielfeld, steht er vollständig in der Bemerkung; im Feld der gekürzte Anfang."""
        if len(text) <= laenge:
            return text
        extras.append(W.absatz(f"{titel} (vollständig, laut Altsystem)", text))
        self.p(0, tab, "hinweis", f"„{titel}“ länger als {laenge} Zeichen: gekürzt im Feld, vollständig in der Bemerkung.", kennung)
        return text[:laenge - 2].rstrip() + " …"

    # ------------------------------------------------ Zahlen mit Regeln
    def zahlfeld(self, tab, kennung, feld, zeile, extras, *, stellen, ziffern, einheit="", grenzen=None,
                 null_ist_leer=True, patient=None):
        """Zahl eines Plans bzw. Patienten: lesen, runden, auf das Zielfeld und die Plausibilitätsgrenzen prüfen.
        Was nicht übernommen werden kann, steht mit dem Wert des Altsystems in ``extras`` (Bemerkung)."""
        wert, roh = self.lies(tab, kennung, feld, zeile)
        titel = JE_NAME[tab].feld(feld).titel
        try:
            z = W.zahl(wert)
        except W.Unlesbar:
            wahl = self.auffaellig(tab, kennung, feld, "unlesbar", f"{titel}: „{wert}“ ist keine Zahl.", roh, "leer",
                                   ["wert", "leer"], "zahl", patient=patient)
            if wahl == "leer":
                extras.append(W.absatz(f"{titel} (laut Altsystem, nicht lesbar)", str(roh)))
            return None
        if z is None or (null_ist_leer and z == 0):
            return None
        if z < 0:
            self.auffaellig(tab, kennung, feld, "negativ", f"{titel}: {wert} ist negativ.", roh, "leer",
                            ["wert", "leer"], "zahl", patient=patient)
            extras.append(W.absatz(f"{titel} (laut Altsystem)", str(roh)))
            return None
        gerundet = _dez(z, stellen)
        if gerundet != z:
            self.p(0, tab, "hinweis", f"„{titel}“ auf {stellen} Nachkommastelle(n) gerundet (mehr speichert das Feld nicht).",
                   kennung)
        if gerundet >= Decimal(10) ** (ziffern - stellen):
            self.auffaellig(tab, kennung, feld, "zu_gross", f"{titel}: {wert} ist größer, als das Feld speichern kann.",
                            roh, "leer", ["wert", "leer"], "zahl", patient=patient)
            extras.append(W.absatz(f"{titel} (laut Altsystem)", f"{roh} {einheit}".strip()))
            return None
        if grenzen:
            unten, oben = self.grenzen.get(grenzen[0]), self.grenzen.get(grenzen[1])
            if unten is not None and oben is not None and not (unten <= gerundet <= oben):
                wahl = self.auffaellig(tab, kennung, feld, "unplausibel",
                                       f"{titel}: {wert} liegt außerhalb der Plausibilitätsgrenzen ({unten:f}–{oben:f} {einheit}).",
                                       roh, "unveraendert", ["wert", "leer", "unveraendert"], "zahl", patient=patient)
                if wahl == "leer":
                    extras.append(W.absatz(f"{titel} (laut Altsystem)", f"{roh} {einheit}".strip()))
                    return None
        return gerundet

    # ------------------------------------------------ Patienten
    def patienten(self):
        tab = "patienten"
        zeilen = self.q[tab]["zeilen"]
        anzahl = {"gewichte": {}, "kontakte": {}, "infusionen": {}}
        for t in anzahl:
            for z in self.q[t]["zeilen"]:
                w = self.roh(t, z, "patient")
                if w is not None:
                    anzahl[t][str(w).strip()] = anzahl[t].get(str(w).strip(), 0) + 1
        entscheidungen = self.z.get("geloeschte") if isinstance(self.z.get("geloeschte"), dict) else {}
        saetze, nummern = [], {}
        nicht = {"geloescht": 0, "ausgelassen": 0, "fehler": 0}
        self.patient_ref = {}     # Nummer im Altsystem (Text) → Patientennummer, soweit übernommen
        self.patient_bekannt = {self.kennung(tab, z, nr) for nr, z in enumerate(zeilen, 1)}
        for nr, z in enumerate(zeilen, 1):
            kennung = self.kennung(tab, z, nr)
            # --- im Altsystem gelöscht? Entscheidung je Patient: nicht übernehmen (Standard) oder als abgeschlossene Akte
            abschluss = None
            try:
                geloescht = W.zeitpunkt(self.roh(tab, z, "geloescht"))
            except W.Unlesbar:
                geloescht = None
                self.p(0, tab, "warnung", "„Gelöscht am“ nicht lesbar – als nicht gelöscht behandelt.", kennung)
            if geloescht is not None:
                wahl = entscheidungen.get(kennung)
                wirksam, fehler = {"art": "nicht"}, ""
                if isinstance(wahl, dict) and wahl.get("art") == "abgeschlossen":
                    am = None
                    try:
                        am = W.datum(wahl.get("am")) if wahl.get("am") else geloescht.date()
                    except W.Unlesbar:
                        fehler = "Das Abschlussdatum ist nicht lesbar."
                    if am is not None and am > self.heute:
                        fehler = "Das Abschlussdatum liegt in der Zukunft."
                    if wahl.get("anlass") not in ANLAESSE:
                        fehler = "Bitte den Anlass des Abschlusses wählen."
                    wirksam = {"art": "abgeschlossen", "anlass": wahl.get("anlass"), "am": am.isoformat() if am else None}
                    if not fehler:
                        abschluss = {"am": am, "anlass": wahl["anlass"],
                                     "notiz": f"Im Altsystem als gelöscht markiert am {_tag(geloescht)}."}
                    else:
                        self.sperre("geloeschte", f"Gelöschter Patient {kennung}: {fehler}")
                try:
                    geburt_text = W.datum(self.roh(tab, z, "geburtsdatum"))
                except W.Unlesbar:
                    geburt_text = None
                self.e.geloeschte.append({
                    "schluessel": kennung,
                    "name": f"{self.text(tab, z, 'nachname')}, {self.text(tab, z, 'vorname')}",
                    "geburtsdatum": geburt_text.isoformat() if geburt_text else None,
                    "geloescht_am": geloescht.isoformat(),
                    "gewichte": anzahl["gewichte"].get(kennung, 0), "kontakte": anzahl["kontakte"].get(kennung, 0),
                    "plaene": anzahl["infusionen"].get(kennung, 0),
                    "entscheidung": wahl if isinstance(wahl, dict) else None, "wirksam": wirksam, "fehler": fehler,
                })
                if abschluss is None:
                    # wird nicht übernommen: dann auch keine Auffälligkeiten zu dieser Zeile
                    if not fehler:
                        nicht["geloescht"] += 1
                    continue
            if self.ausgelassen(tab, kennung, z):
                nicht["ausgelassen"] += 1
                self.p(0, tab, "hinweis", "Auf Entscheidung der Administration nicht übernommen.", kennung)
                self._auffaelligkeiten_der_zeile(tab, kennung, z)
                continue
            extras = []
            # --- Patientennummer (Regel 15)
            wert, roh = self.lies(tab, kennung, "nummer", z)
            try:
                nummer = W.ganzzahl(wert)
            except W.Unlesbar:
                nummer = None
            # im EPM endgültig gelöscht (Löschprotokoll, Art. 17 DSGVO)? Die Nummer wird nicht neu vergeben, und eine
            # andere Nummer wäre ein Weg um die Löschung herum – der Patient lässt sich nur ausnehmen. Geprüft wird
            # die Nummer des Dumps ebenso wie eine eingetragene Korrektur.
            try:
                nummer_im_dump = W.ganzzahl(roh)
            except W.Unlesbar:
                nummer_im_dump = None
            if any(n is not None and n in self.geloescht_epm for n in (nummer, nummer_im_dump)):
                self.auffaellig(tab, kennung, "nummer", "geloescht_epm",
                                "Die Patientennummer gehört zu einer im EPM endgültig gelöschten Akte (Löschprotokoll, "
                                "Art. 17 DSGVO) und wird nicht neu vergeben – dieser Patient kann nur ausgenommen werden.",
                                roh, "offen", ["auslassen"], "zahl", blockiert=True)
                nicht["fehler"] += 1
                self.p(15, tab, "fehler", "Patientennummer steht im Löschprotokoll des EPM → Patient wird so nicht übernommen.", kennung)
                continue
            problem = None
            if nummer is None or nummer <= 0:
                problem = f"Patientennummer „{wert}“ ist keine positive ganze Zahl."
            elif nummer >= self.test_ab:
                problem = f"Patientennummer {nummer} liegt im Bereich der Testpatienten (ab {self.test_ab})."
            elif nummer in nummern:
                problem = f"Patientennummer {nummer} kommt mehrfach vor."
            elif str(nummer) != kennung and str(nummer) in self.patient_bekannt:
                # eine korrigierte Nummer darf nicht die eines anderen Patienten des Altsystems sein – auch nicht eines
                # gelöschten: Gewichte, Pläne und der Dokumentenordner dieser Nummer gehören zu jenem Patienten
                problem = f"Patientennummer {nummer} gehört im Altsystem einem anderen Patienten."
            if problem:
                self.auffaellig(tab, kennung, "nummer", "nummer", problem, roh, "offen", ["wert", "auslassen"], "zahl",
                                blockiert=True)
                nicht["fehler"] += 1
                self.p(15, tab, "fehler", "Patientennummer nicht verwendbar → Patient wird so nicht übernommen.", kennung)
                continue
            # --- Geburtsdatum (Pflicht im EPM)
            wert, roh = self.lies(tab, kennung, "geburtsdatum", z)
            try:
                geburt = W.datum(wert)
            except W.Unlesbar:
                geburt = None
            if geburt is None:
                self.auffaellig(tab, kennung, "geburtsdatum", "fehlt",
                                "Geburtsdatum fehlt oder ist nicht lesbar – im EPM ist es Pflicht.", roh, "offen",
                                ["wert", "auslassen"], "datum", blockiert=True, patient=nummer)
                nicht["fehler"] += 1
                self.p(0, tab, "fehler", "Geburtsdatum fehlt → Patient wird so nicht übernommen.", kennung)
                continue
            if geburt > self.heute or geburt.year < 1900:
                self.auffaellig(tab, kennung, "geburtsdatum", "unplausibel", f"Geburtsdatum {_tag(geburt)} ist unplausibel.",
                                roh, "unveraendert", ["wert", "unveraendert", "auslassen"], "datum", patient=nummer)
            # --- Name
            namen = {}
            for feld in ("nachname", "vorname"):
                wert, roh = self.lies(tab, kennung, feld, z)
                t = self.text(tab, z, feld, wert)
                if not t:
                    self.auffaellig(tab, kennung, feld, "fehlt", f"{JE_NAME[tab].feld(feld).titel} ist leer.", roh,
                                    "unveraendert", ["wert", "unveraendert", "auslassen"], patient=nummer)
                namen[feld] = self.begrenzt(t, LAENGEN[feld], JE_NAME[tab].feld(feld).titel, extras, tab, kennung)
            # --- Anschrift und Kontakt
            wert, roh = self.lies(tab, kennung, "plz", z)
            plz = self.text(tab, z, "plz", wert)
            if plz in ("0", "00000") or W.ist_leer(plz):
                plz = ""
            elif plz.isdigit() and len(plz) == 4:
                self.auffaellig(tab, kennung, "plz", "plz", f"PLZ „{plz}“ hat vier Stellen (führende Null verloren oder Ausland?).",
                                roh, "unveraendert", ["wert", "unveraendert"], patient=nummer)
            felder = {}
            for feld, ziel in (("strasse", "strasse"), ("ort", "ort"), ("telefon", "telefon"), ("hausarzt", "hausarzt"),
                               ("kontaktaufnahme", "ueberweisung_durch")):
                t = self.text(tab, z, feld)
                felder[ziel] = self.begrenzt("" if W.ist_leer(t) else t, LAENGEN[feld], JE_NAME[tab].feld(feld).titel,
                                             extras, tab, kennung)
            plz = self.begrenzt(plz, LAENGEN["plz"], "PLZ", extras, tab, kennung)
            email = self.text(tab, z, "email")
            if W.ist_leer(email):
                email = ""
            elif not W.email_gueltig(email):
                extras.append(W.absatz("E-Mail (laut Altsystem, keine gültige Adresse)", email))
                self.p(0, tab, "hinweis", "E-Mail ist keine gültige Adresse: steht in der Bemerkung, das Feld bleibt leer.", kennung)
                email = ""
            # --- Größe (Regel 6)
            wert, roh = self.lies(tab, kennung, "groesse", z)
            groesse = None
            try:
                g = W.zahl(wert)
            except W.Unlesbar:
                g = None
                self.auffaellig(tab, kennung, "groesse", "unlesbar", f"Größe „{wert}“ ist keine Zahl.", roh, "leer",
                                ["wert", "leer"], "zahl", patient=nummer)
                extras.append(W.absatz("Größe (laut Altsystem, nicht lesbar)", str(roh)))
            if g is not None:
                if g == 0:
                    self.p(6, tab, "info", "Größe 0 → leer.", kennung)
                elif g < 0:
                    self.auffaellig(tab, kennung, "groesse", "negativ", f"Größe {wert} ist negativ.", roh, "leer",
                                    ["wert", "leer"], "zahl", patient=nummer)
                    extras.append(W.absatz("Größe (laut Altsystem)", str(roh)))
                else:
                    if g < 3:
                        self.p(6, tab, "info", "Größe in Metern (unter 3) → in Zentimeter umgerechnet (× 100).", kennung)
                        g = g * 100
                    g = _dez(g, 1)
                    unten, oben = self.grenzen.get("groesse_min_cm"), self.grenzen.get("groesse_max_cm")
                    if g >= 10000:
                        self.auffaellig(tab, kennung, "groesse", "zu_gross", f"Größe {wert} ist größer, als das Feld speichern kann.",
                                        roh, "leer", ["wert", "leer"], "zahl", patient=nummer)
                        extras.append(W.absatz("Größe (laut Altsystem)", str(roh)))
                    elif unten is not None and oben is not None and not (unten <= g <= oben):
                        wahl = self.auffaellig(tab, kennung, "groesse", "unplausibel",
                                               f"Größe {g:f} cm liegt außerhalb der Plausibilitätsgrenzen ({unten:f}–{oben:f} cm).",
                                               roh, "unveraendert", ["wert", "leer", "unveraendert"], "zahl", patient=nummer)
                        if wahl == "leer":
                            extras.append(W.absatz("Größe (laut Altsystem)", str(roh)))
                        else:
                            groesse = g
                    else:
                        groesse = g
            # --- Versorger (Regel 4)
            v = self.roh(tab, z, "versorger")
            vref = {"versorger": None, "ansprechpartner": None, "kein": False}
            if v not in (None, ""):
                vk = str(v).strip()
                if vk in self.versorger_ref:
                    vref = self.versorger_ref[vk]
                elif vk != "0":
                    self.p(4, tab, "hinweis", "Verweis auf einen Versorger, den es im Altsystem nicht mehr gibt → Versorger leer.", kennung)
            # --- Katheter, Nickelallergie, Geschlecht
            kref = self.katheter_ref.get(W.schluessel(self.text(tab, z, "katheter")), {"katheter": None, "kein": False})
            self.nutze("auswahlwerte", kref["katheter"])
            nickel = self.wert_ref["nickel"].get(W.schluessel(self.text(tab, z, "nickel")))
            geschlecht = self.wert_ref["geschlecht"].get(W.schluessel(self.text(tab, z, "geschlecht")))
            # --- Texte (Regel 11)
            texte = {}
            for feld in ("diagnose", "therapie", "empfehlung"):
                roh_text = self.text(tab, z, feld)
                texte[feld] = self.html(tab, kennung, "" if W.ist_leer(roh_text) else roh_text, f"„{JE_NAME[tab].feld(feld).titel}“")
            try:
                geaendert = W.zeitpunkt(self.roh(tab, z, "geaendert"))
            except W.Unlesbar:
                geaendert = None
                self.p(0, tab, "hinweis", "„Zuletzt geändert am“ nicht lesbar → Zeitpunkt des Imports.", kennung)
            nummern[nummer] = kennung
            self.patient_ref[kennung] = nummer
            saetze.append({
                "alt": kennung, "nummer": nummer, "nachname": namen["nachname"], "vorname": namen["vorname"],
                "geburtsdatum": geburt, "geschlecht": geschlecht or "", "strasse": felder["strasse"], "plz": plz,
                "ort": felder["ort"], "telefon": felder["telefon"], "email": email, "hausarzt": felder["hausarzt"],
                "ueberweisung_durch": felder["ueberweisung_durch"], "groesse_cm": groesse,
                "versorger": vref["versorger"], "ansprechpartner": vref["ansprechpartner"], "kein_versorger": vref["kein"],
                "katheter": kref["katheter"], "kein_katheter": kref["kein"], "nickelallergie": nickel or "unbekannt",
                "diagnose": texte["diagnose"], "therapie": texte["therapie"], "empfehlung": texte["empfehlung"],
                "bemerkung": extras, "bearbeiter": self.bearbeiter(tab, z, "bearbeiter"), "geaendert": geaendert,
                "abschluss": abschluss,
            })
        self.e.saetze["patienten"] = saetze
        self.e.zahlen["patienten"] = {"alt": len(zeilen), "neu": len(saetze),
                                      "abgeschlossen": sum(1 for s in saetze if s["abschluss"]),
                                      "nicht": {k: v for k, v in nicht.items() if v}}
        if nicht["geloescht"]:
            self.p(0, tab, "info", "Im Altsystem als gelöscht markiert und nicht übernommen (mit allen Einträgen).",
                   anzahl=nicht["geloescht"])
        nickel_unbekannt = sum(1 for s in saetze if s["nickelallergie"] == "unbekannt")
        if nickel_unbekannt:
            self.p(10, tab, "info", "Nickelallergie unbekannt (auch ohne Angabe) – die Akte zeigt dazu einen Hinweis.",
                   anzahl=nickel_unbekannt)

    def _auffaelligkeiten_der_zeile(self, tab, kennung, zeile, patient=None):
        """Für eine ausgelassene Zeile die Entscheidung in der Liste sichtbar halten (damit sie änderbar bleibt).
        Bei einer Regel bleiben die Wahlmöglichkeiten der ursprünglichen Auffälligkeit erhalten."""
        for feld, roh, k in self._auslassend(tab, kennung, zeile):
            eingabe = "datum" if feld in self.DATUMSFELDER else "text" if feld in self.TEXTFELDER else "zahl"
            moeglich = ["wert", "auslassen"]
            text = "Wird nicht übernommen (Entscheidung der Administration)."
            if k.get("regel"):
                r = self.regeln[k["regel"]]
                moeglich = [m for m in r.get("moeglich") or moeglich if m in ARTEN] or moeglich
                text = (f"Wird nicht übernommen – Regel für alle mit dem Wert „{'' if roh is None else roh}“"
                        f"{(': ' + r['befund']) if r.get('befund') else ''}.")
            self.auffaellig(tab, kennung, feld, "ausgelassen", text, roh, "auslassen", moeglich, eingabe, patient=patient)

    def _patient(self, tab, zeile, kennung, zaehler):
        """Patientennummer zu einem Eintrag – oder ``None`` mit Vermerk, warum er nicht übernommen wird."""
        w = self.roh(tab, zeile, "patient")
        pk = "" if w is None else str(w).strip()
        if pk in self.patient_ref:
            return self.patient_ref[pk]
        if pk in self.patient_bekannt:
            zaehler["patient_nicht_uebernommen"] += 1
        else:
            zaehler["ohne_patient"] += 1
            self.p(4, tab, "hinweis", "Kein Patient mit dieser Nummer im Altsystem → verworfen.", kennung)
        return None

    # ------------------------------------------------ Gewichte (Regeln 2, 4, 5)
    def gewichte(self):
        tab = "gewichte"
        zaehler = {"patient_nicht_uebernommen": 0, "ohne_patient": 0, "platzhalter": 0, "ausgelassen": 0}
        saetze = []
        unten, oben = self.grenzen.get("gewicht_min_kg"), self.grenzen.get("gewicht_max_kg")
        for nr, z in enumerate(self.q[tab]["zeilen"], 1):
            kennung = self.kennung(tab, z, nr)
            patient = self._patient(tab, z, kennung, zaehler)
            if patient is None:
                continue
            if self.ausgelassen(tab, kennung, z):
                zaehler["ausgelassen"] += 1
                self._auffaelligkeiten_der_zeile(tab, kennung, z, patient)
                continue
            wert, roh = self.lies(tab, kennung, "gewicht", z)
            try:
                kg = W.zahl(wert)
            except W.Unlesbar:
                self.auffaellig(tab, kennung, "gewicht", "unlesbar", f"Gewicht „{wert}“ ist keine Zahl.", roh, "auslassen",
                                ["wert", "auslassen"], "zahl", patient=patient)
                zaehler["ausgelassen"] += 1
                continue
            if kg is None or kg <= 0 or kg >= 9999:
                zaehler["platzhalter"] += 1
                self.p(5, tab, "info", "Unplausibles Gewicht (leer, 0 oder 9999 als Platzhalter) → nicht übernommen.", kennung)
                continue
            if _dez(kg, 1) != kg:
                self.p(0, tab, "hinweis", "Gewicht auf eine Nachkommastelle gerundet (mehr speichert das Feld nicht).", kennung)
            kg = _dez(kg, 1)
            if unten is not None and oben is not None and not (unten <= kg <= oben):
                wahl = self.auffaellig(tab, kennung, "gewicht", "unplausibel",
                                       f"Gewicht {kg:f} kg liegt außerhalb der Plausibilitätsgrenzen ({unten:f}–{oben:f} kg).",
                                       roh, "unveraendert", ["wert", "unveraendert", "auslassen"], "zahl", patient=patient)
                if wahl == "auslassen":
                    zaehler["ausgelassen"] += 1
                    continue
            wert, roh = self.lies(tab, kennung, "zeit", z)
            try:
                zeit = W.zeitpunkt(wert)
            except W.Unlesbar:
                zeit = None
            if zeit is None:
                self.auffaellig(tab, kennung, "zeit", "fehlt", "Ohne Zeitpunkt lässt sich das Messdatum nicht bestimmen.",
                                roh, "auslassen", ["wert", "auslassen"], "datum", patient=patient)
                zaehler["ausgelassen"] += 1
                self.p(2, tab, "warnung", "Gewicht ohne Zeitpunkt → nicht übernommen (Datum unter „Auffälligkeiten“ eintragen).", kennung)
                continue
            saetze.append({"alt": kennung, "patient": patient, "gewicht_kg": kg, "gemessen_am": zeit.date(), "zeit": zeit,
                           "bearbeiter": self.bearbeiter(tab, z, "bearbeiter")})
        saetze = self._gewichte_zusammenfassen(saetze, zaehler)
        self.e.saetze["gewichte"] = saetze
        self.e.zahlen[tab] = {"alt": len(self.q[tab]["zeilen"]), "neu": len(saetze),
                              "nicht": {k: v for k, v in zaehler.items() if v}}
        if saetze:
            self.p(2, tab, "info", "Messdatum = Tag der Erfassung im Altsystem; als „Datum ungenau“ und Quelle „Altsystem“ markiert.",
                   anzahl=len(saetze))

    def _gewichte_zusammenfassen(self, saetze, zaehler):
        """Mehrere Gewichte eines Patienten kurz hintereinander sind im Altsystem meist Korrekturen derselben Messung.
        Je Patient bilden alle Einträge, die höchstens ``gewichte_tage`` × 24 Stunden nach dem ersten Eintrag der
        Gruppe erfasst wurden, eine Gruppe; übernommen wird der zuletzt erfasste (bei gleichem Zeitpunkt der spätere
        im Dump). 0 Tage = nicht zusammenfassen."""
        tage = self.gewichte_tage
        z = self.e.zusammengefasst
        z["tage"] = tage
        if not tage or not saetze:
            return saetze
        fenster = timedelta(days=tage)
        je_patient = {}
        for i, s in enumerate(saetze):
            je_patient.setdefault(s["patient"], []).append((s["zeit"], i, s))
        verworfen = set()
        patienten = set()
        for patient, liste in je_patient.items():
            liste.sort(key=lambda x: (x[0], x[1]))
            n = 0
            while n < len(liste):
                beginn = liste[n][0]
                m = n
                while m + 1 < len(liste) and liste[m + 1][0] - beginn <= fenster:
                    m += 1
                if m > n:
                    gruppe_ = liste[n:m + 1]
                    behalten = gruppe_[-1][2]
                    weg = [x[2] for x in gruppe_[:-1]]
                    verworfen.update(x[1] for x in gruppe_[:-1])
                    patienten.add(patient)
                    for s in weg:
                        self.p(2, "gewichte", "hinweis",
                               f"Mehrere Gewichte innerhalb von {tage} {'Tag' if tage == 1 else 'Tagen'} → nur der zuletzt "
                               f"erfasste übernommen.", s["alt"])
                    if len(z["gruppen"]) < GRUPPEN_ANZEIGE:
                        z["gruppen"].append({
                            "patient": patient,
                            "behalten": {"id": behalten["alt"], "kg": f"{behalten['gewicht_kg']:f}", "zeit": behalten["zeit"].isoformat()},
                            "verworfen": [{"id": s["alt"], "kg": f"{s['gewicht_kg']:f}", "zeit": s["zeit"].isoformat()} for s in weg],
                        })
                n = m + 1
        z["anzahl"] = len(verworfen)
        z["patienten"] = len(patienten)
        if verworfen:
            zaehler["zusammengefasst"] = len(verworfen)
        return [s for i, s in enumerate(saetze) if i not in verworfen]

    # ------------------------------------------------ Kontakte
    def kontakte(self):
        tab = "kontakte"
        zaehler = {"patient_nicht_uebernommen": 0, "ohne_patient": 0, "leer": 0, "ausgelassen": 0}
        saetze = []
        for nr, z in enumerate(self.q[tab]["zeilen"], 1):
            kennung = self.kennung(tab, z, nr)
            patient = self._patient(tab, z, kennung, zaehler)
            if patient is None:
                continue
            if self.ausgelassen(tab, kennung, z):
                zaehler["ausgelassen"] += 1
                self._auffaelligkeiten_der_zeile(tab, kennung, z, patient)
                continue
            roh_text = self.text(tab, z, "text")
            if W.ist_leer(roh_text):
                zaehler["leer"] += 1
                self.p(0, tab, "hinweis", "Kontakt ohne Text → nicht übernommen.", kennung)
                continue
            inhalt = self.html(tab, kennung, roh_text, "Kontakt")
            wert, roh = self.lies(tab, kennung, "zeit", z)
            try:
                zeit = W.zeitpunkt(wert)
            except W.Unlesbar:
                zeit = None
            if zeit is None:
                self.auffaellig(tab, kennung, "zeit", "fehlt", "Kontakt ohne Zeitpunkt.", roh, "auslassen",
                                ["wert", "auslassen"], "datum", patient=patient)
                zaehler["ausgelassen"] += 1
                self.p(2, tab, "warnung", "Kontakt ohne Zeitpunkt → nicht übernommen (Datum unter „Auffälligkeiten“ eintragen).", kennung)
                continue
            saetze.append({"alt": kennung, "patient": patient, "text": inhalt, "zeit": zeit,
                           "bearbeiter": self.bearbeiter(tab, z, "bearbeiter")})
        self.e.saetze["kontakte"] = saetze
        self.e.zahlen[tab] = {"alt": len(self.q[tab]["zeilen"]), "neu": len(saetze),
                              "nicht": {k: v for k, v in zaehler.items() if v}}

    # ------------------------------------------------ Infusionspläne (Regeln 7, 13, 14, 16)
    def plaene(self):
        tab = "infusionen"
        zaehler = {"patient_nicht_uebernommen": 0, "ohne_patient": 0, "ausgelassen": 0}
        saetze = []
        zahlfelder = (
            ("glucose_g", "glucose_g", ("glucose_min_g", "glucose_max_g"), "g"),
            ("amino_g", "aminosaeuren_g", ("aminosaeuren_min_g", "aminosaeuren_max_g"), "g"),
            ("lipide_g", "lipide_g", ("lipide_min_g", "lipide_max_g"), "g"),
            ("albumin_ml", "albumin_ml", None, "ml"),
            ("natrium", "natrium_mmol", ("natrium_min_mmol", "natrium_max_mmol"), "mmol"),
            ("kalium", "kalium_mmol", ("kalium_min_mmol", "kalium_max_mmol"), "mmol"),
            ("phosphat", "phosphat_mmol", None, "mmol"),
            ("calcium", "calcium_mmol", None, "mmol"),
            ("magnesium", "magnesium_mmol", None, "mmol"),
        )
        for nr, z in enumerate(self.q[tab]["zeilen"], 1):
            kennung = self.kennung(tab, z, nr)
            patient = self._patient(tab, z, kennung, zaehler)
            if patient is None:
                continue
            if self.ausgelassen(tab, kennung, z):
                zaehler["ausgelassen"] += 1
                self._auffaelligkeiten_der_zeile(tab, kennung, z, patient)
                continue
            extras = []
            zeiten = {}
            for feld in ("erstellt", "geaendert"):
                wert, roh = self.lies(tab, kennung, feld, z)
                try:
                    zeiten[feld] = W.zeitpunkt(wert)
                except W.Unlesbar:
                    zeiten[feld] = None
            beginn = zeiten["erstellt"] or zeiten["geaendert"]
            if beginn is None:
                self.auffaellig(tab, kennung, "erstellt", "fehlt", "Plan ohne Datum („angelegt am“ und „zuletzt geändert am“ fehlen).",
                                self.roh(tab, z, "erstellt"), "auslassen", ["wert", "auslassen"], "datum", patient=patient)
                zaehler["ausgelassen"] += 1
                self.p(0, tab, "warnung", "Plan ohne Datum → nicht übernommen (Datum unter „Auffälligkeiten“ eintragen).", kennung)
                continue
            satz = {"alt": kennung, "patient": patient, "gueltig_ab": beginn.date(), "erstellt": beginn,
                    "geaendert": zeiten["geaendert"] or beginn, "ersteller": self.bearbeiter(tab, z, "ersteller"),
                    "bearbeiter": self.bearbeiter(tab, z, "bearbeiter") or self.bearbeiter(tab, z, "ersteller"),
                    "vitamine": [], "positionen": [], "katheterschutz": None, "spurenelemente": None}
            for feld, ziel, grenzen, einheit in zahlfelder:
                satz[ziel] = self.zahlfeld(tab, kennung, feld, z, extras, stellen=1, ziffern=6, einheit=einheit,
                                           grenzen=grenzen, patient=patient)
            satz["gesamtvolumen_ml"] = self.zahlfeld(tab, kennung, "gesamt_ml", z, extras, stellen=2, ziffern=7, einheit="ml",
                                                     grenzen=("volumen_min_ml", "volumen_max_ml"), patient=patient)
            basis = self.zahlfeld(tab, kennung, "basis_ml", z, extras, stellen=0, ziffern=9, einheit="ml", patient=patient)
            satz["basis_ml"] = int(basis) if basis is not None else None
            satz["laufzeit_h"] = self.zahlfeld(tab, kennung, "laufzeit_h", z, extras, stellen=1, ziffern=4, einheit="h",
                                               patient=patient)
            # --- Energie: Wert des Altsystems nur dann als „manuell“, wenn er von der Berechnung abweicht
            wert, roh = self.lies(tab, kennung, "kcal", z)
            kcal = None
            try:
                k = W.zahl(wert)
            except W.Unlesbar:
                k = None
                wahl = self.auffaellig(tab, kennung, "kcal", "unlesbar", f"Energie „{wert}“ ist keine Zahl.", roh, "leer",
                                       ["wert", "leer"], "zahl", patient=patient)
                extras.append(W.absatz("Energie (laut Altsystem, nicht lesbar)", str(roh)))
            if k is not None and k != 0:
                if k < 0 or k != k.to_integral_value() or k > 2147483647:
                    self.auffaellig(tab, kennung, "kcal", "keine_ganze_zahl",
                                    f"Energie „{wert}“ ist keine positive ganze Zahl (Tippfehler?) – EPM berechnet sie aus den Mengen.",
                                    roh, "leer", ["wert", "leer"], "zahl", patient=patient)
                    extras.append(W.absatz("Energie (laut Altsystem)", f"{roh} kcal"))
                else:
                    kcal = int(k)
                    unten, oben = self.grenzen.get("kcal_min_tag"), self.grenzen.get("kcal_max_tag")
                    if unten is not None and oben is not None and not (unten <= kcal <= oben):
                        wahl = self.auffaellig(tab, kennung, "kcal", "unplausibel",
                                               f"Energie {kcal} kcal liegt außerhalb der Plausibilitätsgrenzen ({unten:f}–{oben:f} kcal).",
                                               roh, "unveraendert", ["wert", "leer", "unveraendert"], "zahl", patient=patient)
                        if wahl == "leer":
                            extras.append(W.absatz("Energie (laut Altsystem)", f"{roh} kcal"))
                            kcal = None
            berechnet = int(sum(((satz[f] or Decimal(0)) * faktor for f, faktor in KCAL_JE_G), Decimal(0))
                            .quantize(Decimal(1), rounding=ROUND_HALF_UP))
            satz["kcal_manuell"] = kcal if kcal is not None and kcal != berechnet else None
            # --- Protonenpumpenhemmer (Regel 14)
            wert, roh = self.lies(tab, kennung, "pantozol", z)
            stufe = 0
            try:
                s = W.ganzzahl(wert)
            except W.Unlesbar:
                s = -1
            if s is None:
                s = 0
            if s not in (0, 1, 2, 3):
                self.auffaellig(tab, kennung, "pantozol", "unbekannt", f"Protonenpumpenhemmer „{wert}“ ist kein bekannter Wert (0–3).",
                                roh, "leer", ["wert", "leer"], "zahl", patient=patient)
                extras.append(W.absatz("Protonenpumpenhemmer (laut Altsystem)", str(roh)))
            else:
                stufe = s
            satz["pantozol_stufe"] = stufe
            try:
                zeit = W.ganzzahl(self.roh(tab, z, "panzeit"))
            except W.Unlesbar:
                zeit = None
            if stufe and zeit in range(1, 8):
                satz["pantozol_tage"] = zeit
            else:
                satz["pantozol_tage"] = None
                if stufe:
                    self.p(14, tab, "hinweis", "Protonenpumpenhemmer ohne gültige Zeiten (Bitmaske 1–7) → Zeiten leer.", kennung)
                elif zeit:
                    self.p(14, tab, "hinweis", "Zeiten ohne Protonenpumpenhemmer → nicht übernommen.", kennung)
            # --- Präparate (Regel 16)
            for feld, ziel in (("basis", "basis_praeparat"), ("glucose", "glucose_praeparat"),
                               ("amino", "aminosaeuren_praeparat"), ("albumin", "albumin_praeparat"),
                               ("lipide", "lipide_praeparat")):
                satz[ziel] = None
                for teil in self.teile(self.text(tab, z, feld), False):
                    ref = self.praep_ref[feld].get(W.schluessel(teil))
                    if ref and ("id" in ref or "neu" in ref):
                        satz[ziel] = self.nutze("praeparate", ref)
                    elif ref and ref.get("bemerkung"):
                        extras.append(W.absatz(f"{PRAEPARATFELDER[feld][0]} (laut Altsystem)", teil))
            for feld in ("spurenelemente", "vitamine", "medikamente"):
                for teil in self.teile(self.text(tab, z, feld), True):
                    ref = self.praep_ref[feld].get(W.schluessel(teil))
                    if not ref or ref.get("leer"):
                        continue
                    if ref.get("bemerkung"):
                        extras.append(W.absatz(f"{PRAEPARATFELDER[feld][0]} (laut Altsystem)", teil))
                        continue
                    self.nutze("praeparate", ref)
                    if feld == "vitamine":
                        if ref not in satz["vitamine"]:
                            satz["vitamine"].append(ref)
                    elif feld == "spurenelemente" and satz["spurenelemente"] is None:
                        satz["spurenelemente"] = ref
                    elif feld == "medikamente" and ref["kategorie"] == "katheterschutz" and satz["katheterschutz"] is None:
                        satz["katheterschutz"] = ref
                    else:
                        # weiterer Bestandteil; der Wortlaut des Altsystems bleibt an der Position erhalten
                        satz["positionen"].append({"praeparat": ref, "bemerkung": teil[:LAENGEN["position_bemerkung"]]})
                        if len(teil) > LAENGEN["position_bemerkung"]:
                            extras.append(W.absatz(f"{PRAEPARATFELDER[feld][0]} (vollständig, laut Altsystem)", teil))
            # --- Angaben ohne eigenes Feld (Regel 13)
            for feld, titel, einheit in (("laufrate", "Laufrate", "ml/h"), ("dipeptamin", "Dipeptamin", ""),
                                         ("omegaven", "Omegaven", "")):
                t = self.text(tab, z, feld)
                if W.ist_leer(t):
                    continue
                try:
                    if W.zahl(t) == 0:
                        continue
                except W.Unlesbar:
                    pass
                extras.append(W.absatz(f"{titel} (laut Altsystem)", f"{t} {einheit}".strip()))
                self.p(13, tab, "hinweis", f"„{titel}“ ist gefüllt: Das EPM hat dafür kein eigenes Feld, der Wert steht in der Bemerkung.", kennung)
            kommentar = self.text(tab, z, "kommentar")
            satz["bemerkung"] = self.html(tab, kennung, "" if W.ist_leer(kommentar) else kommentar, "„Kommentar“")
            satz["bemerkung_extras"] = extras
            saetze.append(satz)
        # Status und Vorgänger: je Patient nach Datum; der jüngste Plan ist der aktuelle (Regel 16)
        je_patient = {}
        for i, s in enumerate(saetze):
            je_patient.setdefault(s["patient"], []).append((s["gueltig_ab"], s["erstellt"], i, s))
        for liste in je_patient.values():
            liste.sort(key=lambda x: x[:3])
            vorher = None
            for n, (_, _, _, s) in enumerate(liste):
                s["status"] = "aktuell" if n == len(liste) - 1 else "abgeloest"
                s["vorgaenger"] = vorher
                vorher = s["alt"]
        self.e.saetze["plaene"] = saetze
        self.e.zahlen[tab] = {"alt": len(self.q[tab]["zeilen"]), "neu": len(saetze),
                              "aktuell": len(je_patient), "nicht": {k: v for k, v in zaehler.items() if v}}
        if saetze:
            self.p(16, tab, "info", "Je Patient ist der jüngste Plan „aktuell“, die früheren „abgelöst“; Vorgänger nach Datum. "
                                    "Ohne Freigabevermerk und ohne gespeicherte PDF (beides gab es im Altsystem nicht).",
                   anzahl=len(saetze))

    # ------------------------------------------------ Abschluss
    DATUMSFELDER = {"geburtsdatum", "zeit", "erstellt", "geaendert"}
    TEXTFELDER = {"nachname", "vorname", "plz"}

    def fertig(self):
        # Korrekturen, nach denen nichts mehr auffällt, bleiben in der Liste sichtbar (und damit änderbar)
        gemeldet = {a["schluessel"] for a in self.e.auffaelligkeiten}
        for schluessel, (tab, kennung, feld, roh, k) in self.angewandt.items():
            if schluessel in gemeldet:
                continue
            eingabe = "datum" if feld in self.DATUMSFELDER else "text" if feld in self.TEXTFELDER else "zahl"
            neu = "leer" if k["art"] == "leer" else f"„{k.get('wert', '')}“"
            self.e.auffaelligkeiten.append({
                "schluessel": schluessel, "tabelle": tab, "tabelle_titel": JE_NAME[tab].titel, "id": str(kennung),
                "patient": None, "feld": feld, "feld_titel": JE_NAME[tab].feld(feld).titel, "art": "korrigiert",
                "text": f"Korrigiert: {neu} statt „{'' if roh is None else roh}“.",
                "wert": None if roh is None else str(roh)[:200], "roh": None if roh is None else str(roh),
                "standard": "unveraendert", "moeglich": ["wert", "leer"], "eingabe": eingabe, "blockiert": False,
                "entscheidung": k, "gruppe": gruppe(tab, feld, roh), "regel": self.regeln.get(gruppe(tab, feld, roh)),
            })
            self.p(0, tab, "hinweis", f"„{JE_NAME[tab].feld(feld).titel}“ von der Administration korrigiert.", kennung)
        for tab, (n, beispiele) in sorted(self.repariert.items()):
            self.p(3, tab, "info", "Doppelt kodierte Umlaute repariert (Felder).", anzahl=n)
            for kennung in beispiele:
                self.p(3, tab, "info", "Doppelt kodierte Umlaute repariert (Felder).", kennung, anzahl=0)
        for tab in ("gewichte", "kontakte", "infusionen"):
            n = self.e.zahlen.get(tab, {}).get("nicht", {}).get("patient_nicht_uebernommen")
            if n:
                self.p(0, tab, "info", "Gehört zu einem Patienten, der nicht übernommen wird → nicht übernommen.", anzahl=n)
        # neu angelegt wird nur, was die übernommenen Datensätze brauchen (Konten immer: sie stehen für sich)
        self.e.saetze["benutzer"] = [b for b in self.e.saetze.get("benutzer", [])
                                     if not b["historisch"] or b["schluessel"] in self.genutzt["benutzer"]]
        for art in ("auswahlwerte", "praeparate"):
            self.e.saetze[art] = [x for x in self.e.saetze.get(art, []) if x["schluessel"] in self.genutzt[art]]
        self.e.zahlen["benutzer"] = {"alt": len(self.e.benutzer), "neu": len(self.e.saetze.get("benutzer", [])),
                                     "konten": sum(1 for b in self.e.saetze.get("benutzer", []) if not b["historisch"])}
        konten = self.e.zahlen["benutzer"]["konten"]
        if konten:
            self.p(1, "benutzer", "info", "Konten werden ohne Passwort angelegt; die Administration erzeugt danach "
                                         "je Person ein Einmal-Passwort (Benutzer › Einmal-Passwort), dazu 2FA.", anzahl=konten)
        if self.e.zahlen["benutzer"]["neu"] - konten:
            self.p(8, "benutzer", "info", "Bearbeiter ohne Konto als historische Benutzer ohne Login angelegt.",
                   anzahl=self.e.zahlen["benutzer"]["neu"] - konten)
        self.e.zahlen["praeparate_neu"] = len(self.e.saetze.get("praeparate", []))
        self.e.zahlen["auswahlwerte_neu"] = len(self.e.saetze.get("auswahlwerte", []))
        stufen = {"fehler": 0, "warnung": 1, "hinweis": 2, "info": 3}
        self.e.protokoll = sorted(self._protokoll.values(), key=lambda x: (stufen.get(x["stufe"], 9), x["bereich"], x["regel"], x["text"]))
        self.e.auffaelligkeiten.sort(key=lambda a: (not a["blockiert"], a["tabelle"], a["art"], a["id"]))
        return self.e


def berechne(tabellen: dict, zuordnung: dict, bestand: dict, reparatur=None, heute: date | None = None) -> Ergebnis:
    """Stand, Protokoll und neue Datensätze aus Dump, Zuordnungen und Bestand. ``reparatur``: Funktion für doppelt
    kodierte Texte (im Betrieb ``werte.ftfy_reparatur()``)."""
    lauf = _Lauf(tabellen, zuordnung, bestand, reparatur, heute or date.today())
    lauf.quelle()
    lauf.benutzer()
    lauf.versorger()
    lauf.wertelisten()
    lauf.praeparate()
    lauf.patienten()
    lauf.gewichte()
    lauf.kontakte()
    lauf.plaene()
    return lauf.fertig()
