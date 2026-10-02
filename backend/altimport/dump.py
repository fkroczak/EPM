"""
MySQL-Dump lesen – ``mysqldump`` und phpMyAdmin-Export, auch gzip-gepackt. Reines Python, ohne Django.

Gelesen werden nur ``CREATE TABLE`` (Spalten) und ``INSERT``/``REPLACE`` (Zeilen); alles andere wird überlesen.
Jeder Wert kommt als Text oder ``None`` (NULL) zurück – Zahlen und Daten deutet erst ``werte``.

Kennwörter werden nie gespeichert (Regel 1 der Datenanalyse): ``ohne_kennwoerter`` leert solche Spalten sofort
nach dem Lesen.
"""
import gzip
import io
import re

MAX_BYTES = 300 * 1024 * 1024  # entpackt; das Altsystem hat wenige MB


class DumpFehler(ValueError):
    """Der Dump ist nicht lesbar; die Meldung nennt die Stelle."""


# ---------------------------------------------------------------- Datei → Text
def entpacke(daten: bytes) -> bytes:
    if daten[:2] != b"\x1f\x8b":
        return daten
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(daten)) as f:
            aus = f.read(MAX_BYTES + 1)
    except (OSError, EOFError) as e:
        raise DumpFehler(f"Die gepackte Datei ist beschädigt: {e}") from e
    if len(aus) > MAX_BYTES:
        raise DumpFehler("Die entpackte Datei ist größer als 300 MB.")
    return aus


def dekodiere(daten: bytes) -> tuple[str, str]:
    """Text und verwendete Kodierung. mysqldump schreibt UTF-8; ältere Exporte auch Windows-1252."""
    if daten.startswith(b"\xef\xbb\xbf"):
        daten = daten[3:]
    try:
        return daten.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return daten.decode("cp1252", errors="replace"), "windows-1252"


# ---------------------------------------------------------------- Bausteine der SQL-Sprache
# Zeichenketten ohne Rückverfolgung (possessiv), damit auch eine nicht geschlossene Zeichenkette schnell scheitert
_STR1 = r"'(?:[^'\\]++|\\.|'')*+'"
_STR2 = r'"(?:[^"\\]++|\\.|"")*+"'
# „offen“: ein Anführungszeichen, zu dem keine vollständige Zeichenkette passt – der Dump ist dort abgeschnitten
_TEIL = re.compile(rf"{_STR1}|{_STR2}|`[^`]*+`|--[^\n]*+|\#[^\n]*+|/\*.*?\*/|;|(?P<offen>['\"`]|/\*)", re.S)
_WERT = re.compile(
    rf"""\s*(?:
        (?P<s1>{_STR1})
      | (?P<s2>{_STR2})
      | (?P<null>NULL)
      | (?P<hex>0x[0-9A-Fa-f]*+|X'[0-9A-Fa-f]*+')
      | (?P<bin>_binary\s*{_STR1})
      | (?P<zahl>[-+]?(?:\d++\.?\d*+|\.\d++)(?:[eE][-+]?\d++)?)
      | (?P<wahr>TRUE|FALSE)
    )\s*(?P<ende>[,)])""",
    re.X | re.I | re.S,
)
_NAME = r"(?:`(?:[^`]|``)+`|\"[^\"]+\"|[A-Za-z_][\w$]*)"
_KOPF_CREATE = re.compile(rf"\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?((?:{_NAME}\s*\.\s*)?{_NAME})\s*\(", re.I)
_KOPF_INSERT = re.compile(
    rf"\s*(?:INSERT|REPLACE)\s+(?:LOW_PRIORITY\s+|DELAYED\s+|HIGH_PRIORITY\s+)?(?:IGNORE\s+)?(?:INTO\s+)?"
    rf"((?:{_NAME}\s*\.\s*)?{_NAME})\s*(\(\s*{_NAME}(?:\s*,\s*{_NAME})*\s*\))?\s*VALUES?\s*",
    re.I,
)
_SPALTE = re.compile(rf"\s*({_NAME})\s+([A-Za-z]+(?:\s*\([^)]*\))?(?:\s+unsigned)?)", re.I)
_KEINE_SPALTE = {"PRIMARY", "KEY", "UNIQUE", "CONSTRAINT", "INDEX", "FULLTEXT", "SPATIAL", "FOREIGN", "CHECK"}
_MASKE = re.compile(r"\\(.)|''|\"\"", re.S)
_ERSATZ = {"0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a"}


def _name(roh: str) -> str:
    """`db`.`tabelle` → tabelle; Anführungszeichen entfernt."""
    teil = re.findall(_NAME, roh)[-1]
    if teil[0] == "`":
        return teil[1:-1].replace("``", "`")
    if teil[0] == '"':
        return teil[1:-1]
    return teil


def _zeichenkette(roh: str) -> str:
    """Inhalt einer SQL-Zeichenkette (ohne die äußeren Anführungszeichen) mit aufgelösten Maskierungen."""
    anf = roh[0]
    innen = roh[1:-1]
    if "\\" not in innen and anf * 2 not in innen:
        return innen

    def ersatz(m):
        z = m.group(1)
        if z is None:
            return m.group(0)[0] if m.group(0)[0] == anf else m.group(0)
        if z in "%_":  # bleibt in MySQL mit Schrägstrich stehen
            return "\\" + z
        return _ERSATZ.get(z, z)

    return _MASKE.sub(ersatz, innen)


def _anweisungen(text: str):
    """Liefert (anfang, ende) jeder Anweisung; Kommentare außerhalb von Anweisungen werden übersprungen."""
    pos, n = 0, len(text)
    anfang = None
    for m in _TEIL.finditer(text):
        t = m.group(0)
        if m.group("offen"):
            zeile = text.count("\n", 0, m.start()) + 1
            raise DumpFehler(f"Zeile {zeile}: Eine Zeichenkette oder ein Kommentar ist nicht geschlossen – "
                             f"die Datei ist vermutlich abgeschnitten.")
        if anfang is None:
            # Beginn der nächsten Anweisung: erstes Zeichen, das kein Leerraum und kein Kommentar ist
            vor = text[pos:m.start()]
            if vor.strip():
                anfang = pos + (len(vor) - len(vor.lstrip()))
            elif t == ";" or t.startswith(("--", "#", "/*")):
                pos = m.end()
                continue
            else:
                anfang = m.start()
        if t == ";":
            yield anfang, m.start()
            anfang = None
            pos = m.end()
    rest_von = anfang if anfang is not None else pos
    if text[rest_von:n].strip():
        yield rest_von + (len(text[rest_von:n]) - len(text[rest_von:n].lstrip())), n


def _teile(inhalt: str) -> list[str]:
    """Spaltendefinitionen an den Kommas der obersten Ebene trennen (Klammern und Zeichenketten beachten)."""
    teile, tiefe, start = [], 0, 0
    for m in re.finditer(rf"{_STR1}|{_STR2}|`[^`]*+`|[(),]", inhalt, re.S):
        t = m.group(0)
        if t == "(":
            tiefe += 1
        elif t == ")":
            tiefe -= 1
        elif t == "," and tiefe == 0:
            teile.append(inhalt[start:m.start()])
            start = m.end()
    teile.append(inhalt[start:])
    return teile


def _klammer_zu(text: str, auf: int) -> int:
    """Position der schließenden Klammer zur öffnenden an ``auf``."""
    tiefe = 0
    for m in re.compile(rf"{_STR1}|{_STR2}|`[^`]*+`|[()]", re.S).finditer(text, auf):
        t = m.group(0)
        if t == "(":
            tiefe += 1
        elif t == ")":
            tiefe -= 1
            if tiefe == 0:
                return m.start()
    raise DumpFehler("CREATE TABLE ohne schließende Klammer.")


def _zeile(text: str, pos: int, tabelle: str, nr: int) -> tuple[list, int]:
    """Ein Wertetupel ab der öffnenden Klammer lesen → (Werte, Position hinter der schließenden Klammer)."""
    werte = []
    pos += 1
    while True:
        m = _WERT.match(text, pos)
        if m is None:
            stelle = " ".join(text[pos:pos + 60].split())
            raise DumpFehler(f"Tabelle „{tabelle}“, Zeile {nr}: Wert nicht lesbar bei „{stelle}“.")
        if m.group("null"):
            werte.append(None)
        elif m.group("s1") is not None or m.group("s2") is not None:
            werte.append(_zeichenkette(m.group("s1") or m.group("s2")))
        elif m.group("bin"):
            roh = m.group("bin")
            werte.append(_zeichenkette(roh[roh.index("'"):]))
        elif m.group("wahr"):
            werte.append("1" if m.group("wahr").upper() == "TRUE" else "0")
        else:
            werte.append(m.group("hex") or m.group("zahl"))
        pos = m.end()
        if m.group("ende") == ")":
            return werte, pos


# ---------------------------------------------------------------- Dump lesen
def lies(daten: bytes) -> dict:
    """Dump → {"tabellen": {name: {"spalten": [...], "typen": {spalte: typ}, "zeilen": [[...]]}},
    "kodierung": "utf-8", "hinweise": [...]}. Löst ``DumpFehler`` aus, wenn nichts Verwertbares enthalten ist."""
    roh = entpacke(daten)
    if len(roh) > MAX_BYTES:
        raise DumpFehler("Die Datei ist größer als 300 MB.")
    text, kodierung = dekodiere(roh)
    tabellen: dict = {}
    hinweise = []
    if kodierung != "utf-8":
        hinweise.append("Die Datei ist nicht UTF-8-kodiert; gelesen als Windows-1252.")
    nul = 0

    def tabelle(name):
        return tabellen.setdefault(name, {"spalten": [], "typen": {}, "zeilen": []})

    for anfang, ende in _anweisungen(text):
        kopf = text[anfang:anfang + 12].lstrip().upper()
        if kopf.startswith("CREATE"):
            m = _KOPF_CREATE.match(text, anfang, ende)
            if m is None:
                continue  # CREATE DATABASE, CREATE VIEW …
            name = _name(m.group(1))
            auf = m.end() - 1
            zu = _klammer_zu(text[:ende], auf)
            t = tabelle(name)
            t["spalten"], t["typen"] = [], {}
            for teil in _teile(text[auf + 1:zu]):
                s = _SPALTE.match(teil)
                if s is None or s.group(1).upper() in _KEINE_SPALTE:
                    continue
                spalte = _name(s.group(1))
                t["spalten"].append(spalte)
                t["typen"][spalte] = " ".join(s.group(2).lower().split())
        elif kopf.startswith(("INSERT", "REPLACE")):
            m = _KOPF_INSERT.match(text, anfang, ende)
            if m is None:
                stelle = " ".join(text[anfang:anfang + 60].split())
                raise DumpFehler(f"INSERT nicht lesbar: „{stelle}“.")
            name = _name(m.group(1))
            t = tabelle(name)
            liste = [_name(x) for x in re.findall(_NAME, m.group(2))] if m.group(2) else None
            pos = m.end()
            while pos < ende:
                while pos < ende and text[pos] in " \t\r\n,":
                    pos += 1
                if pos >= ende:
                    break
                if text[pos] != "(":
                    stelle = " ".join(text[pos:pos + 60].split())
                    raise DumpFehler(f"Tabelle „{name}“: unerwarteter Inhalt nach den Werten: „{stelle}“.")
                nr = len(t["zeilen"]) + 1
                werte, pos = _zeile(text, pos, name, nr)
                if liste is None:
                    if not t["spalten"]:
                        t["spalten"] = [f"spalte{i + 1}" for i in range(len(werte))]
                        hinweise.append(f"Tabelle „{name}“: keine Spaltennamen im Dump (kein CREATE TABLE) – "
                                        f"die Spalten heißen hier spalte1 bis spalte{len(werte)}.")
                    if len(werte) != len(t["spalten"]):
                        raise DumpFehler(f"Tabelle „{name}“, Zeile {nr}: {len(werte)} Werte bei "
                                         f"{len(t['spalten'])} Spalten.")
                else:
                    if len(werte) != len(liste):
                        raise DumpFehler(f"Tabelle „{name}“, Zeile {nr}: {len(werte)} Werte bei "
                                         f"{len(liste)} genannten Spalten.")
                    for spalte in liste:
                        if spalte not in t["spalten"]:
                            t["spalten"].append(spalte)
                            for z in t["zeilen"]:
                                z.append(None)
                    nach = dict(zip(liste, werte))
                    werte = [nach.get(s) for s in t["spalten"]]
                for i, w in enumerate(werte):
                    if w is not None and "\0" in w:
                        werte[i] = w.replace("\0", "")
                        nul += 1
                t["zeilen"].append(werte)
    tabellen = {n: t for n, t in tabellen.items() if t["spalten"]}
    if not tabellen:
        raise DumpFehler("In der Datei wurden keine Tabellen gefunden (kein CREATE TABLE und kein INSERT). "
                         "Erwartet wird ein MySQL-Dump als .sql oder .sql.gz.")
    if nul:
        hinweise.append(f"{nul} Werte enthielten Nullzeichen; sie wurden entfernt.")
    z = _ZEITZONE.search(text, 0, 1 << 20)
    return {"tabellen": tabellen, "kodierung": kodierung, "hinweise": hinweise, "zeitzone": z.group(1) if z else None}


# ---------------------------------------------------------------- TIMESTAMP-Spalten: Zeitzone des Dumps (Regel 2)
# mysqldump (Vorgabe --tz-utc) und phpMyAdmin setzen die Sitzung auf UTC: Dann stehen TIMESTAMP-Spalten in UTC im
# Dump, DATETIME-Spalten unverändert in der Zeit, in der sie gespeichert wurden.
_ZEITZONE = re.compile(r"SET\s+(?:@@session\.)?TIME_ZONE\s*=\s*['\"]([+-]\d\d:\d\d)['\"]", re.I)
_ZEITWERT = re.compile(r"(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d):(\d\d)(\.\d+)?")


def zeitstempel_in_ortszeit(tabellen: dict, zeitzone: str | None, ortszeit: str = "Europe/Berlin") -> list[str]:
    """Werte der TIMESTAMP-Spalten aus der Zeitzone des Dumps in Ortszeit umrechnen (an Ort und Stelle).
    Liefert Hinweise für die Anzeige. DATETIME-, DATE- und Textspalten bleiben unberührt."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    spalten = [(name, s) for name, t in tabellen.items() for s in t["spalten"]
               if str(t.get("typen", {}).get(s, "")).startswith("timestamp")]
    if not spalten:
        return []
    genannt = ", ".join(f"{n}.{s}" for n, s in spalten)
    if zeitzone is None:
        return [f"TIMESTAMP-Spalten ({genannt}): Der Dump nennt keine Zeitzone (SET TIME_ZONE fehlt) – die Zeitpunkte "
                f"werden als Ortszeit gelesen."]
    vz = -1 if zeitzone[0] == "-" else 1
    quelle = timezone(vz * timedelta(hours=int(zeitzone[1:3]), minutes=int(zeitzone[4:6])))
    ziel = ZoneInfo(ortszeit)
    anzahl = 0
    for name, spalte in spalten:
        t = tabellen[name]
        i = t["spalten"].index(spalte)
        for z in t["zeilen"]:
            w = z[i]
            m = _ZEITWERT.fullmatch(w.strip()) if isinstance(w, str) else None
            if m is None or m.group(1) == "0000":
                continue
            try:
                alt = datetime(*(int(x) for x in m.groups()[:6]), tzinfo=quelle)
            except ValueError:
                continue
            z[i] = alt.astimezone(ziel).strftime("%Y-%m-%d %H:%M:%S") + (m.group(7) or "")
            anzahl += 1
    return [f"TIMESTAMP-Spalten ({genannt}) stehen im Dump in der Zeitzone {zeitzone} (SET TIME_ZONE): "
            f"{anzahl} Zeitpunkte wurden in Ortszeit ({ortszeit}) umgerechnet."]


# ---------------------------------------------------------------- Kennwörter nie speichern (Regel 1)
_KENNWORT_NAME = re.compile(r"kennwort|passwor[dt]|passwd|password|pwd|^pass$|hash|salt", re.I)
_KENNWORT_WERT = re.compile(r"^(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{40}|[0-9a-fA-F]{64}|\$2[aby]\$.{50,}|\$argon2.+|\{[A-Z0-9-]+\}.+)$")


def ohne_kennwoerter(tabellen: dict) -> list[tuple[str, str]]:
    """Leert Spalten, die Kennwörter oder deren Prüfsummen enthalten – am Namen oder am Inhalt erkannt.
    Liefert die betroffenen (Tabelle, Spalte) und vermerkt sie je Tabelle unter ``entfernt``."""
    betroffen = []
    for name, t in tabellen.items():
        t.setdefault("entfernt", [])
        for i, spalte in enumerate(t["spalten"]):
            werte = [z[i] for z in t["zeilen"] if z[i] not in (None, "")]
            wie_pruefsumme = bool(werte) and sum(1 for w in werte if _KENNWORT_WERT.match(w)) >= 0.8 * len(werte)
            if _KENNWORT_NAME.search(spalte) or wie_pruefsumme:
                for z in t["zeilen"]:
                    z[i] = None
                if spalte not in t["entfernt"]:
                    t["entfernt"].append(spalte)
                betroffen.append((name, spalte))
    return betroffen
