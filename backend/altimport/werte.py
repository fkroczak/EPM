"""Einzelne Werte des Altsystems lesen und bereinigen: Text, Zahl, Datum, Zeitpunkt, formatierter Text.

Reines Python, ohne Django. Nichts wird geraten: Was sich nicht lesen lässt, löst ``Unlesbar`` aus und wird von
``umsetzung`` als Auffälligkeit gemeldet.
"""
import html
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class Unlesbar(ValueError):
    pass


def ftfy_reparatur():
    """Reparatur doppelt kodierter Texte (Regel 3: „Ã¼“ statt „ü“) mit ftfy – nur die Kodierung, sonst nichts
    (keine geänderten Anführungszeichen, keine aufgelösten HTML-Zeichen)."""
    from ftfy import fix_encoding

    return fix_encoding


# Typische Reste doppelt kodierter Umlaute – nur dann wird die Reparatur überhaupt versucht (spart Zeit, und ein
# unauffälliger Text bleibt garantiert unverändert)
VERDACHT = re.compile("[ÃÂâ€™œžŸ�]")


def text(wert, reparatur=None) -> tuple[str, bool]:
    """Text ohne Rand-Leerraum; ``None`` wird zu „“. Liefert (Text, repariert?)."""
    if wert is None:
        return "", False
    t = str(wert).replace("\0", "")
    repariert = False
    if reparatur is not None and VERDACHT.search(t):
        neu = reparatur(t)
        repariert = neu != t
        t = neu
    return t.strip(), repariert


PLATZHALTER = {"-", "–", "—", "--", "---", "/", ".", "?"}


def ist_leer(t: str) -> bool:
    """Leer oder nur ein Platzhalter (Regel 7: „-“ in Textfeldern der Infusionen)."""
    return not t or t.strip() in PLATZHALTER


def zahl(wert) -> Decimal | None:
    """Zahl in deutscher oder englischer Schreibweise; leer → ``None``; sonst ``Unlesbar``."""
    if wert is None:
        return None
    t = str(wert).strip().replace(" ", "").replace(" ", "")
    if ist_leer(t):
        return None
    if "," in t:
        # deutsche Schreibweise: Punkt als Tausendertrenner, Komma als Dezimaltrenner
        if t.count(",") > 1 or not re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})*,\d*|[-+]?\d*,\d*", t):
            raise Unlesbar(str(wert))
        t = t.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", t):
        raise Unlesbar(str(wert))
    try:
        z = Decimal(t)
    except InvalidOperation as e:
        raise Unlesbar(str(wert)) from e
    if not z.is_finite():
        raise Unlesbar(str(wert))
    return z


def ganzzahl(wert) -> int | None:
    z = zahl(wert)
    if z is None:
        return None
    if z != z.to_integral_value():
        raise Unlesbar(str(wert))
    return int(z)


_DATUM = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?")
_DATUM_DE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:[ ,]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?")


def zeitpunkt(wert) -> datetime | None:
    """Zeitpunkt ohne Zeitzone (so steht er im Altsystem). „0000-00-00 …“ und leer → ``None``."""
    if wert is None:
        return None
    t = str(wert).strip()
    if ist_leer(t) or t.startswith("0000-00-00"):
        return None
    m = _DATUM.fullmatch(t)
    if m:
        j, mo, tg = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = _DATUM_DE.fullmatch(t)
        if not m:
            raise Unlesbar(str(wert))
        tg, mo, j = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(j, mo, tg, int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0))
    except ValueError as e:
        raise Unlesbar(str(wert)) from e


def datum(wert) -> date | None:
    z = zeitpunkt(wert)
    return z.date() if z else None


# ---------------------------------------------------------------- formatierter Text (Regel 11)
_HTML = re.compile(r"</?(?:p|br|b|i|u|s|strong|em|div|span|ul|ol|li|table|tr|td|th|thead|tbody|h[1-6]|font|a|hr|"
                   r"blockquote|mark|sub|sup|center|pre)\b[^<>]*>", re.I)
# Blöcke, die der Editor nicht kennt, auf erlaubte abbilden – sonst gingen beim Bereinigen die Umbrüche verloren
_BLOCK = [(re.compile(r"<(/?)(?:div|center|pre)\b[^<>]*>", re.I), r"<\1p>"),
          (re.compile(r"<(/?)h[12]\b[^<>]*>", re.I), r"<\1h3>"),
          (re.compile(r"<(/?)h[56]\b[^<>]*>", re.I), r"<\1h4>")]


def ist_html(t: str) -> bool:
    return bool(_HTML.search(t))


def als_html(t: str) -> tuple[str, bool]:
    """Text des Altsystems als formatierter Text. Liefert (HTML vor dem Bereinigen, war schon HTML?).

    Reiner Text: Zeichen maskieren, Leerzeile = neuer Absatz, Zeilenumbruch = ``<br>``. Vorhandenes HTML bleibt,
    nur unbekannte Blöcke werden auf Absätze bzw. erlaubte Überschriften abgebildet; das eigentliche Bereinigen
    (erlaubte Tags, keine Skripte) übernimmt ``epm.sanitize`` beim Schreiben."""
    t = (t or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        return "", False
    if ist_html(t):
        for muster, ersatz in _BLOCK:
            t = muster.sub(ersatz, t)
        return t, True
    absaetze = [a for a in re.split(r"\n[ \t]*\n+", t) if a.strip()]
    return "".join(f"<p>{html.escape(a.strip(), quote=False).replace(chr(10), '<br>')}</p>" for a in absaetze), False


def absatz(titel: str, inhalt: str) -> str:
    """Ein Absatz „Titel: Inhalt“ für Angaben, die im neuen System kein eigenes Feld haben."""
    return f"<p><strong>{html.escape(titel, quote=False)}:</strong> {html.escape(inhalt, quote=False)}</p>"


_EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+")


def email_gueltig(t: str) -> bool:
    return bool(_EMAIL.fullmatch(t)) and len(t) <= 254


def schluessel(t: str) -> str:
    """Vergleichsform eines Freitexts (Zuordnungen gelten unabhängig von Groß-/Kleinschreibung und Leerraum)."""
    return " ".join((t or "").split()).casefold()
