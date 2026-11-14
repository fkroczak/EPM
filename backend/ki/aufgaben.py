"""Nachtaufgaben des KI-Dienstes (Zeitplan, 14.11.2026, Administration › KI › Nachtaufgaben).

Der KI-Dienst fragt in jedem Durchlauf (alle 5 s, eine kleine Abfrage) nach fälligen Aufgaben: aktiv, heute ein
gewählter Wochentag, die Uhrzeit (Zeitzone der KI-Einstellungen) erreicht und seit diesem Termin noch nicht gelaufen –
oder ausdrücklich „Jetzt ausführen“. Eine Aufgabe **reiht nur Arbeit ein**; abgearbeitet wird nach Modus, Grenzen und
Nachtfenster wie alles andere. So bleibt die Steuerung an einer Stelle (``ki/steuerung.py``).

Wird eine Aufgabe nach ihrer Uhrzeit angelegt oder geändert, läuft sie erst zum nächsten Termin (sonst liefe eine um
14 Uhr angelegte „03:00“-Aufgabe sofort); ist der Dienst zur Uhrzeit nicht gelaufen, holt er sie am selben Tag nach.
"""
import datetime as dt
import logging
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from audit.models import SystemEreignis, protokolliere

from .models import Dokumenttyp, KiAufgabe, KiEinstellung

log = logging.getLogger("epm.ki")
A = KiAufgabe.Art
VORMERKEN_ANZAHL = 5000

# je Art: Feld → (Standard, Prüfung); Prüfung gibt den bereinigten Wert zurück oder wirft ValueError(Meldung)


def _zahl(unten, oben):
    def pruefen(wert):
        if isinstance(wert, bool) or not isinstance(wert, (int, str)) or not str(wert).strip().isdigit():
            raise ValueError(f"Bitte eine ganze Zahl von {unten} bis {oben}.")
        wert = int(wert)
        if not unten <= wert <= oben:
            raise ValueError(f"Erlaubt: {unten}–{oben}.")
        return wert
    return pruefen


def _ja_nein(wert):
    if not isinstance(wert, bool):
        raise ValueError("Bitte ja oder nein (true/false).")
    return wert


def _dokumenttypen(wert):
    if not isinstance(wert, list) or any(not isinstance(t, str) or t not in Dokumenttyp.values for t in wert):
        raise ValueError(f"Erlaubt: Liste aus {', '.join(Dokumenttyp.values)}.")
    return sorted(set(wert))


NEU_LESEN_PARAMETER = {"seit_tagen": (30, _zahl(0, 3650)), "dokumenttypen": ([], _dokumenttypen),
                       "nur_anderes_modell": (True, _ja_nein), "hoechstens": (200, _zahl(1, 5000))}
PARAMETER = {
    A.ZUSAMMENFASSUNG_TERMINE: {"tage_voraus": (1, _zahl(1, 14))},
    A.NEU_LESEN: NEU_LESEN_PARAMETER,
    A.DOKUMENTE_VORMERKEN: {"altbestand": (True, _ja_nein)},
}


def parameter_pruefen(art: str, parameter, schema: dict | None = None) -> dict:
    """→ vollständige, bereinigte Parameter (fehlende mit Standard, unbekannte entfallen). Wirft
    ``ValueError({"parameter.<feld>": Meldung})``."""
    schema = schema if schema is not None else PARAMETER[art]
    if parameter is None:
        parameter = {}
    if not isinstance(parameter, dict):
        raise ValueError({"parameter": "Parameter bitte als Objekt angeben."})
    aus, fehler = {}, {}
    for feld, (standard, pruefen) in schema.items():
        try:
            aus[feld] = pruefen(parameter[feld]) if feld in parameter else standard
        except ValueError as e:
            fehler[f"parameter.{feld}"] = str(e)
    if fehler:
        raise ValueError(fehler)
    return aus


def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(KiEinstellung.laden().zeitzone)
    except (KeyError, ValueError):
        return ZoneInfo("Europe/Berlin")


def _termin(tag: dt.date, uhrzeit: dt.time, zone: ZoneInfo) -> dt.datetime:
    return dt.datetime.combine(tag, uhrzeit, tzinfo=zone)


def _grenze(a: KiAufgabe) -> dt.datetime | None:
    """Termine bis hierher zählen nicht mehr: gelaufen oder vor der letzten Änderung."""
    werte = [w for w in (a.letzter_lauf, a.geaendert_am) if w is not None]
    return max(werte) if werte else None


def faellig(a: KiAufgabe, jetzt: dt.datetime | None = None, zone: ZoneInfo | None = None) -> bool:
    if a.jetzt_angefordert:
        return True
    if not a.aktiv:
        return False
    jetzt, zone = jetzt or timezone.now(), zone or _zone()
    heute = jetzt.astimezone(zone).date()
    if heute.weekday() not in (a.wochentage or []):
        return False
    termin = _termin(heute, a.uhrzeit, zone)
    grenze = _grenze(a)
    return termin <= jetzt and (grenze is None or grenze < termin)


def naechster_lauf(a: KiAufgabe, jetzt: dt.datetime | None = None, zone: ZoneInfo | None = None) -> dt.datetime | None:
    """Nächster Lauf (kann in der Vergangenheit liegen: fällig, der Dienst holt ihn beim nächsten Durchlauf)."""
    jetzt, zone = jetzt or timezone.now(), zone or _zone()
    if a.jetzt_angefordert:
        return jetzt
    if not a.aktiv or not a.wochentage:
        return None
    heute, grenze = jetzt.astimezone(zone).date(), _grenze(a)
    for i in range(8):
        tag = heute + dt.timedelta(days=i)
        termin = _termin(tag, a.uhrzeit, zone)
        if tag.weekday() in a.wochentage and (grenze is None or grenze < termin):
            return termin
    return None


def ausfuehren(a: KiAufgabe) -> str:
    """Arbeit einreihen; → Ergebnis in Worten (ohne Inhalte)."""
    from . import eingang, zusammenfassung

    p = parameter_pruefen(a.art, a.parameter)
    if a.art == A.ZUSAMMENFASSUNG_TERMINE:
        n = zusammenfassung.termine_vorbereiten(p["tage_voraus"])
        ergebnis = f"{n} Zusammenfassung{'' if n == 1 else 'en'} eingereiht"
    elif a.art == A.NEU_LESEN:
        n = eingang.neu_lesen(**p)
        ergebnis = f"{n} Dokument{'' if n == 1 else 'e'} zum Neulesen vorgemerkt"
    elif a.art == A.DOKUMENTE_VORMERKEN:
        n = eingang.vormerken(VORMERKEN_ANZAHL, altbestand=p["altbestand"])
        ergebnis = f"{n} Dokument{'' if n == 1 else 'e'} vorgemerkt"
    else:
        raise ValueError(f"unbekannte Art {a.art}")
    eingang.prioritaeten_aktualisieren()
    return ergebnis


def faellige_ausfuehren(jetzt: dt.datetime | None = None) -> int:
    """Vom KI-Dienst in jedem Durchlauf: fällige Aufgaben ausführen; → Zahl ausgeführter."""
    jetzt, zone = jetzt or timezone.now(), _zone()
    kandidaten = [a for a in KiAufgabe.objects.filter(Q(aktiv=True) | Q(jetzt_angefordert=True))
                  if faellig(a, jetzt, zone)]
    anzahl = 0
    for kandidat in kandidaten:
        with transaction.atomic():
            a = KiAufgabe.objects.select_for_update(skip_locked=True).filter(pk=kandidat.pk).first()
            if a is None or not faellig(a, jetzt, zone):
                continue
            # vor der Arbeit festhalten: auch ein Fehler soll nicht alle 5 Sekunden wiederholt werden
            try:
                with transaction.atomic():
                    ergebnis, ok = ausfuehren(a), True
            except Exception as e:  # noqa: BLE001 – eine Aufgabe darf den Dienst nicht anhalten
                log.exception("KI-Aufgabe %s fehlgeschlagen", a.pk)
                ergebnis, ok = f"Fehler: {type(e).__name__}", False
            KiAufgabe.objects.filter(pk=a.pk).update(letzter_lauf=timezone.now(), letztes_ergebnis=ergebnis[:500],
                                                     jetzt_angefordert=False)
        log.info("KI-Aufgabe %s (%s): %s", a.pk, a.art, ergebnis)
        protokolliere(SystemEreignis.Art.KI, benutzername="ki-dienst", objekt=f"KI-Aufgabe {a.pk}", aktion="aufgabe",
                      art=a.art, ergebnis=ergebnis[:200], ok=ok, jetzt=kandidat.jetzt_angefordert)
        anzahl += 1
    return anzahl
