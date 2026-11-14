"""Korrekturen der Mitarbeiter als Beispiele im Prompt (Few-Shot, 14.11.2026).

Wer in der Prüfansicht ein Feld korrigiert, hinterlässt ein Paar „KI las … → richtig ist …“ (``KiFeld.wert`` →
``KiFeld.korrigiert``, versioniert in ``KiKorrektur``). Vor der Extraktion eines neuen Dokuments sucht
``korrekturhinweise()`` solche Paare aus früheren Dokumenten und gibt sie dem Modell als kurze Liste mit – bevorzugt
vom selben Absender (gleiches Labor, gleiches Formular), sonst die jüngsten. So wiederholt das Modell einen Fehler
nicht, den schon jemand korrigiert hat (falsch gelesene Einheit, Parametername, Komma …). Das ist **kein Training**:
das Modell bleibt unverändert, die Liste steht nur in der Anfrage.

Datenschutz und Grenzen:
- nur Vorgänge **derselben Firma** und derselben Art (Übung ↔ echt), nie der Vorgang selbst;
- nur Name, Wert und Einheit (Labor), Substanz und Menge (Infusion), Wirkstoff, Stärke und Dosierung, Diagnose
  und Dokumenttyp – keine Namen, Geburtsdaten, Daten, Fallnummern, Kommentare oder Freitexte; zur Sicherheit
  zusätzlich durch ``pseudonymisieren``;
- höchstens ``KiEinstellung.beispiele_max`` Zeilen (0 = aus) und ``ZEICHEN_HOECHSTENS`` Zeichen.
"""
import re

from django.db.models import Prefetch

from scans.ocr import auswertung

from .models import KiEinstellung, KiFeld, KiKorrektur, KiVorgang
from .pseudonym import pseudonymisieren

SUCHEN_HOECHSTENS = 400     # so viele korrigierte Felder werden höchstens angesehen (jüngste zuerst)
ZEICHEN_HOECHSTENS = 1800   # damit bleibt genug Kontext für Seite und Antwort
GRUPPEN = ["labor", "infusion", "medikation", "diagnose", "meta"]


def _komma(wert) -> str:
    """Zahlen wie auf deutschen Befunden (3.2 → 3,2) – so steht es auch im Dokument, das das Modell liest."""
    t = str(wert).strip()
    return t.replace(".", ",") if re.fullmatch(r"-?\d+\.\d+", t) else t


def _teile(w: dict, *schluessel) -> str:
    return " ".join(_komma(w.get(s)) for s in schluessel if w.get(s) not in (None, "")).strip()


def _labor(w: dict, name_korrigiert: bool) -> str:
    name = (w.get("parameter_name") or w.get("freitext_name") or w.get("erkannt_als")) if name_korrigiert \
        else w.get("erkannt_als")
    return " ".join(x for x in (str(name or "").strip(), _teile(w, "wert") or _teile(w, "wert_text"),
                                _teile(w, "einheit")) if x)


def zeile(feld: KiFeld) -> str | None:
    """Ein korrigiertes Feld → „KI las … → richtig: …“ oder None (nichts Lehrreiches, z. B. nur das Datum geändert)."""
    alt, neu = feld.wert or {}, feld.korrigiert or {}
    if feld.gruppe == "labor":
        a, n = _labor(alt, False), _labor(neu, True)
        art = "Laborwert"
    elif feld.gruppe == "infusion":
        a, n = _teile(alt, "substanz", "menge", "einheit"), _teile(neu, "substanz", "menge", "einheit")
        art = "Infusion"
    elif feld.gruppe == "medikation":
        a, n = (_teile(alt, "wirkstoff", "staerke", "dosierung"), _teile(neu, "wirkstoff", "staerke", "dosierung"))
        art = "Medikament"
    elif feld.gruppe == "diagnose":
        a, n = _teile(alt, "bezeichnung", "icd_code"), _teile(neu, "bezeichnung", "icd_code")
        art = "Diagnose"
    elif feld.gruppe == "meta" and feld.schluessel == "dokumenttyp":
        a, n = _teile(alt, "wert"), _teile(neu, "wert")
        art = "Dokumenttyp"
    else:
        return None
    if not n or a == n:
        return None
    a, n = pseudonymisieren(a)[:120], pseudonymisieren(n)[:120]
    korrekturen = list(feld.korrekturen.all()) if feld.pk else []
    letzte = korrekturen[-1] if korrekturen else None
    zusatz = f" ({letzte.get_fehlerart_display()})" if letzte and letzte.fehlerart != KiKorrektur.Fehlerart.SONSTIGES else ""
    return f"- {art}: gelesen „{a or '–'}“ → richtig „{n}“{zusatz}"


def _absender(v: KiVorgang) -> set[str]:
    """Absender eines früheren Vorgangs – wie ihn die Regeln und wie ihn das Modell gelesen haben."""
    m = v.metadaten or {}
    return {auswertung.norm(str(m.get(k) or ""))[:150] for k in ("absender_regeln", "absender")} - {""}


def korrekturhinweise(vorgang: KiVorgang, absender: str = "") -> tuple[str, int]:
    """→ (Textblock für den Prompt, Zahl der Beispiele). Leer, wenn ausgeschaltet oder nichts passt."""
    anzahl = KiEinstellung.laden().beispiele_max
    if not anzahl:
        return "", 0
    eigen = {auswertung.norm(absender or "")[:150]} - {""} or _absender(vorgang)
    felder = (KiFeld.objects.filter(korrigiert__isnull=False, gruppe__in=GRUPPEN, korrekturen__isnull=False,
                                    vorgang__firma_id=vorgang.firma_id, vorgang__ist_test=vorgang.ist_test)
              .exclude(vorgang_id=vorgang.pk).distinct().select_related("vorgang")
              .prefetch_related(Prefetch("korrekturen", KiKorrektur.objects.order_by("version")))
              .order_by("-geaendert_am", "-id")[:SUCHEN_HOECHSTENS])
    gleich, andere = [], []
    for f in felder:
        z = zeile(f)
        if z is None:
            continue
        (gleich if eigen & _absender(f.vorgang) else andere).append(z)
    zeilen, gesehen, laenge = [], set(), 0
    for z in gleich + andere:
        if z in gesehen:
            continue
        if len(zeilen) >= anzahl or laenge + len(z) > ZEICHEN_HOECHSTENS:
            break
        gesehen.add(z)
        zeilen.append(z)
        laenge += len(z) + 1
    if not zeilen:
        return "", 0
    kopf = ("Frühere Korrekturen durch Mitarbeiter bei ähnlichen Dokumenten"
            + (" desselben Absenders" if gleich else "") + " – vermeide diese Lesefehler. Übernimm daraus nichts, "
            "was nicht auch in diesem Dokument steht:")
    return kopf + "\n" + "\n".join(zeilen), len(zeilen)
