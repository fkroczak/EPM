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


GROESSTE_ZAHL = Decimal(10) ** 15


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
    if not z.is_finite() or abs(z) >= GROESSTE_ZAHL or (z != 0 and z.adjusted() < -12):
        # weit jenseits dessen, was ein Feld des EPM speichert (und was sich noch runden lässt)
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


# Was die Bereinigung des EPM ersatzlos entfernt: Linkziele und Bilder. Linkziele bleiben als Text hinter dem
# Linktext stehen; Bilder werden mit ihrer Quelle genannt (eingebettete Bilddaten nur als Vermerk).
LINK = re.compile(r"<a\b[^<>]*?\bhref\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s<>]+))[^<>]*>(.*?)</a\s*>", re.I | re.S)
BILD = re.compile(r"<img\b[^<>]*?>", re.I)
_BILD_QUELLE = re.compile(r"\bsrc\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s<>]+))", re.I)
_UNSICHTBAR = re.compile(r"<(script|style)\b.*?</\1\s*>|<!--.*?-->", re.I | re.S)
_TAG = re.compile(r"<[^<>]*>")


def _link(m) -> str:
    ziel = html.unescape(next((g for g in m.groups()[:3] if g is not None), "")).strip()
    text = m.group(4)
    sichtbar = html.unescape(_TAG.sub("", text)).strip()
    if not ziel or ziel.casefold() == sichtbar.casefold() or ziel.casefold().startswith("javascript:"):
        return text
    return f"{text} ({html.escape(ziel[:500], quote=False)})"


def _bild(m) -> str:
    q = _BILD_QUELLE.search(m.group(0))
    quelle = html.unescape(next((g for g in q.groups() if g is not None), "")).strip() if q else ""
    if not quelle or quelle.casefold().startswith("data:"):
        return "[Bild im Text des Altsystems – nicht übernommen]"
    return f"[Bild im Text des Altsystems – nicht übernommen: {html.escape(quelle[:300], quote=False)}]"


def ohne_lesbaren_text(t: str) -> bool:
    """Bleibt von einem HTML-Text nach dem Entfernen aller Tags nichts Lesbares übrig?"""
    rest = html.unescape(_TAG.sub("", _UNSICHTBAR.sub("", t or "")))
    return not rest.replace("\xa0", " ").strip()


def ist_html(t: str) -> bool:
    return bool(_HTML.search(t))


def als_html(t: str, als_text: bool = False) -> tuple[str, bool]:
    """Text des Altsystems als formatierter Text. Liefert (HTML vor dem Bereinigen, war schon HTML?).

    Reiner Text: Zeichen maskieren, Leerzeile = neuer Absatz, Zeilenumbruch = ``<br>``. Vorhandenes HTML bleibt,
    nur unbekannte Blöcke werden auf Absätze bzw. erlaubte Überschriften abgebildet; das eigentliche Bereinigen
    (erlaubte Tags, keine Skripte) übernimmt ``epm.sanitize`` beim Schreiben. Linkziele und Bilder, die das
    Bereinigen ersatzlos entfernen würde, bleiben als Text stehen. ``als_text``: den Quelltext selbst als Text
    übernehmen (für HTML ohne lesbaren Inhalt)."""
    t = (t or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        return "", False
    if ist_html(t) and not als_text:
        t = BILD.sub(_bild, LINK.sub(_link, t))
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
