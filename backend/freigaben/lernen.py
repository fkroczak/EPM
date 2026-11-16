"""Lernen aus Korrekturen (Menü „Freigaben“, 16.11.2026) – kein Training, sondern Statistik über Entscheidungen.

Bei jeder umgesetzten Datenpflege hält ``festhalten`` fest, was die Person anders entschieden hat als vorgeschlagen
(und was sie bestätigt hat). Die nächsten Vorschläge fragen hier nach:

- ``beziehung(schluessel)``: z. B. „Fr. + gleicher Nachname“ → meist „Ehefrau“ (oder doch „Tochter“)
- ``arzt(schluessel)``: Freitext „Dr. Heuwing Dorsten“ → Arzt Nr. 17 der Ärzteliste (auch nach Zusammenführung)
- ``schritt(schluessel)``: Schritte, die fast immer abgewählt werden, sind vorab abgewählt
- ``abschluss(schluessel)``: Anlass des Abschlusses bei „+“ bzw. „INAKTIV“ mit einem bestimmten Wort im Kontakt

Eine Regel gilt ab ``MIN_BEISPIELE`` gleichen Entscheidungen mit ``MIN_ANTEIL`` Übereinstimmung; ab ``SICHER_BEISPIELE``
gilt der Vorschlag als eindeutig (ohne „bitte prüfen“) – außer beim Abschluss einer Akte, der immer bestätigt wird.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .models import Lernbeispiel

MIN_BEISPIELE = 3
SICHER_BEISPIELE = 5
MIN_ANTEIL = 0.8
LETZTE = 50  # nur die letzten Entscheidungen zählen – Gewohnheiten ändern sich


@dataclass
class Gelernt:
    wert: str
    anzahl: int
    gesamt: int

    @property
    def anteil(self) -> float:
        return self.anzahl / self.gesamt if self.gesamt else 0.0

    @property
    def sicher(self) -> bool:
        return self.anzahl >= SICHER_BEISPIELE and self.anteil >= 0.9

    def text(self) -> str:
        return f"gelernt aus {self.gesamt} Freigabe{'' if self.gesamt == 1 else 'n'}: {self.anzahl}× „{self.wert}“"


def _abfrage(art: str, schluessel: str) -> Gelernt | None:
    werte = list(Lernbeispiel.objects.filter(art=art, schluessel=schluessel).order_by("-zeitpunkt", "-id")
                 .values_list("gewaehlt", flat=True)[:LETZTE])
    if len(werte) < MIN_BEISPIELE:
        return None
    wert, anzahl = Counter(werte).most_common(1)[0]
    g = Gelernt(wert, anzahl, len(werte))
    return g if g.anteil >= MIN_ANTEIL else None


def beziehung(schluessel: str) -> Gelernt | None:
    return _abfrage("beziehung", schluessel)


def arzt(schluessel: str) -> int | None:
    """ID des Arztes, den Mitarbeiter zu diesem Freitext (Name ohne Titel) gewählt haben – schon ab einer Wahl, wenn
    sie eindeutig ist (ein Name meint fast immer denselben Arzt)."""
    werte = list(Lernbeispiel.objects.filter(art="arzt", schluessel=schluessel).order_by("-zeitpunkt")
                 .values_list("gewaehlt", flat=True)[:LETZTE])
    if not werte:
        return None
    wert, anzahl = Counter(werte).most_common(1)[0]
    return int(wert) if wert.isdigit() and anzahl / len(werte) >= MIN_ANTEIL else None


def schritt_abgewaehlt(schluessel: str) -> Gelernt | None:
    g = _abfrage("schritt", schluessel)
    return g if g is not None and g.wert == "ab" else None


def abschluss(schluessel: str) -> Gelernt | None:
    return _abfrage("abschluss", schluessel)


def merken(art: str, schluessel: str, vorschlag: str, gewaehlt: str, user=None):
    if schluessel:
        Lernbeispiel.objects.create(art=art, schluessel=schluessel[:200], vorschlag=str(vorschlag)[:200],
                                    gewaehlt=str(gewaehlt)[:200], benutzer=user)


def festhalten(vorher: list[dict], nachher: list[dict], user) -> int:
    """Vorgeschlagene und freigegebene Schritte vergleichen; → Zahl der Korrekturen (Abweichungen)."""
    alt = {s["id"]: s for s in vorher}
    korrekturen = 0
    for s in nachher:
        v = alt.get(s["id"], s)
        lern = s.get("lernen") or {}
        if lern.get("schritt"):
            merken("schritt", lern["schritt"], "an" if v.get("an") else "ab", "an" if s["an"] else "ab", user)
        if not s["an"]:
            korrekturen += bool(v.get("an"))
            continue
        if s["art"] == "bezugsperson" and lern.get("beziehung"):
            gewaehlt = s["werte"].get("beziehung", "")
            merken("beziehung", lern["beziehung"], v["werte"].get("beziehung", ""), gewaehlt, user)
            korrekturen += gewaehlt != v["werte"].get("beziehung", "")
        elif s["art"] == "arzt" and lern.get("arzt") and str(s.get("arzt_wahl", "")).isdigit():
            merken("arzt", lern["arzt"], str(v.get("arzt_wahl", "")), str(s["arzt_wahl"]), user)
            korrekturen += str(s["arzt_wahl"]) != str(v.get("arzt_wahl", ""))
        elif s["art"] == "abschluss" and lern.get("abschluss"):
            merken("abschluss", lern["abschluss"], v["werte"].get("anlass", ""), s["werte"].get("anlass", ""), user)
            korrekturen += s["werte"].get("anlass") != v["werte"].get("anlass")
        elif s["art"] in ("feld", "bezugsperson", "arzt"):
            korrekturen += (s.get("neu") != v.get("neu")) or (s.get("werte") != v.get("werte"))
    return korrekturen


def beispiele_fuer_ki(limit: int = 6) -> list[dict]:
    """Letzte bestätigte Beziehungen als Beispiele für den Prompt des KI-Modells."""
    return [{"fall": s, "beziehung": g} for s, g in Lernbeispiel.objects.filter(art="beziehung").exclude(gewaehlt="")
            .order_by("-zeitpunkt").values_list("schluessel", "gewaehlt")[:limit]]


def stand() -> dict:
    return {"beispiele": Lernbeispiel.objects.count(),
            "regeln": sum(1 for art, s in Lernbeispiel.objects.values_list("art", "schluessel").distinct()
                          if (_abfrage(art, s) if art != "arzt" else arzt(s)) is not None)}
