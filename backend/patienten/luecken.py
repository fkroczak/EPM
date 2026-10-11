"""
Fehlende Angaben melden (F186, Automatisierungen für die Pflege 10.10.2026).

Regeln, die Lücken in den Akten finden – nur Akten in Betreuung, ohne Testpatienten:

- ``hausarzt``: kein Arzt zugeordnet (Reiter „Ärzte“) und auch kein Hausarzt im alten Freitextfeld;
- ``telefon``: weder Telefon noch Telefon 2 in den Stammdaten und keine Kontaktperson mit Telefon oder Mobilnummer;
- ``gewicht_fehlt``: keine Gewichtsmessung in den letzten X Monaten (Vorlagen › Grenzwerte), auch nie gewogen – bei
  einer neuen Akte erst X Monate nach dem Anlegen (Wunsch 11.10.2026: „frisch angelegt, trotzdem ‚kein Gewicht seit
  3 Monaten‘“);
- ``diagnose``: keine aktive Diagnose im Reiter „Diagnosen“ und das Feld „Diagnose“ ist leer;
- ``termin_ort``: ein offener Praxistermin in den nächsten Wochen ohne Ort – er fehlte sonst auf dem Infoblatt an die
  Praxis (F177). Wie dort zählt das nur, wenn es den Terminort der Praxis gibt (``infoblatt.praxisort``).

Die Regeln erscheinen als Hinweise der Akte (``kennzahlen``, Patientenliste, Aktenkopf) und lassen sich dort wie die
anderen Hinweise für 3, 6 oder 12 Monate oder dauerhaft ausblenden (F119, ``Hinweisruhe``). Ausgeblendete zählen auch
in der Tagesliste der Startseite nicht mit.
"""
import re
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from stammdaten.models import Einstellungen

from .models import (Bezugsperson, Diagnose, Gewichtsmessung, Patient, PatientArzt, Termin, ruhende_hinweise,
                     sichtbare_termine)

# Praxistermine ohne Ort: so weit voraus wird geschaut (etwa zwei Infoblätter im Monatsrhythmus)
ORT_TAGE = 56

REGELN = ("hausarzt", "telefon", "gewicht_fehlt", "diagnose", "termin_ort")

# Filter der Patientenliste (``?pruefen=``) je Regel
FILTER = {"hausarzt": "ohne_hausarzt", "telefon": "ohne_telefon", "gewicht_fehlt": "ohne_gewicht",
          "diagnose": "ohne_diagnose", "termin_ort": "termin_ohne_ort"}


def hinweis_text(art: str, e) -> str:
    return {
        "hausarzt": "Kein Hausarzt erfasst",
        "telefon": "Keine Telefonnummer",
        "gewicht_fehlt": f"Kein Gewicht seit {e.gewicht_fehlt_monate} Mon.",
        "diagnose": "Keine Diagnose",
        "termin_ort": "Praxistermin ohne Ort",
    }[art]


def _leer(text: str) -> bool:
    """Rich-Text-Felder speichern HTML – „<p></p>“ ist auch leer."""
    return not re.sub(r"<[^>]+>|&nbsp;|\s", "", text or "")


def ort_termine(patient_ids=None):
    """Offene, sichtbare Praxistermine ab heute (nächste ``ORT_TAGE`` Tage) ohne Ort – leer, wenn es keinen
    Terminort der Praxis gibt (dann steht ohnehin jeder Praxistermin auf dem Infoblatt)."""
    from .infoblatt import praxisort

    if praxisort() is None:
        return Termin.objects.none()
    heute = timezone.localdate()
    qs = Termin.objects.filter(art=Termin.Art.PRAXISTERMIN, ort__isnull=True, erledigt_am__isnull=True,
                               faellig_am__range=(heute, heute + timedelta(days=ORT_TAGE)))
    if patient_ids is not None:
        qs = qs.filter(patient_id__in=list(patient_ids))
    return sichtbare_termine(qs)


def luecken(patient_ids, e=None) -> dict:
    """{patient_id: [art, …]} für Akten in Betreuung ohne Testpatienten – ohne Rücksicht auf ausgeblendete Hinweise
    (das erledigen ``kennzahlen`` bzw. ``zaehlen``)."""
    e = e or Einstellungen.aktuell()
    ids = list(Patient.objects.filter(id__in=list(patient_ids), abgeschlossen_am__isnull=True, ist_test=False)
               .values_list("id", flat=True))
    if not ids:
        return {}
    mit_arzt = set(PatientArzt.objects.filter(patient_id__in=ids, aktiv=True).values_list("patient_id", flat=True))
    mit_telefon_person = set(Bezugsperson.objects.filter(patient_id__in=ids, aktiv=True)
                             .filter(~Q(telefon="") | ~Q(mobil="")).values_list("patient_id", flat=True))
    grenze = timezone.localdate() - timedelta(days=30 * e.gewicht_fehlt_monate)
    mit_gewicht = set(Gewichtsmessung.objects.filter(patient_id__in=ids, gemessen_am__gte=grenze)
                      .values_list("patient_id", flat=True))
    mit_diagnose = set(Diagnose.objects.filter(patient_id__in=ids, aktiv=True).values_list("patient_id", flat=True))
    ohne_ort = set(ort_termine(ids).values_list("patient_id", flat=True))
    ergebnis = {}
    for pid, hausarzt, telefon, telefon2, diagnose, angelegt in (Patient.objects.filter(id__in=ids).values_list(
            "id", "hausarzt", "telefon", "telefon2", "diagnose", "angelegt_am")):
        arten = []
        if pid not in mit_arzt and not hausarzt.strip():
            arten.append("hausarzt")
        if not telefon.strip() and not telefon2.strip() and pid not in mit_telefon_person:
            arten.append("telefon")
        # neue Akte: die Frist läuft ab dem Anlegen
        if pid not in mit_gewicht and (angelegt is None or timezone.localdate(angelegt) < grenze):
            arten.append("gewicht_fehlt")
        if pid not in mit_diagnose and _leer(diagnose):
            arten.append("diagnose")
        if pid in ohne_ort:
            arten.append("termin_ort")
        if arten:
            ergebnis[pid] = arten
    return ergebnis


def offene_luecken(patient_ids, e=None) -> dict:
    """Wie ``luecken``, aber ohne die in der Akte ausgeblendeten Hinweise (F119)."""
    werte = luecken(patient_ids, e)
    stumm = ruhende_hinweise(werte.keys())
    ergebnis = {}
    for pid, arten in werte.items():
        rest = [a for a in arten if a not in stumm.get(pid, set())]
        if rest:
            ergebnis[pid] = rest
    return ergebnis


def filter_ids(patienten_qs, art: str) -> list:
    """Patientenliste ``?pruefen=ohne_telefon`` usw.: Akten mit dieser Lücke (ausgeblendete nicht)."""
    regel = next((r for r, f in FILTER.items() if f == art), None)
    if regel is None:
        return []
    werte = offene_luecken(patienten_qs.values_list("id", flat=True))
    return [pid for pid, arten in werte.items() if regel in arten]


def zaehlen(patienten_qs, e=None) -> dict:
    """{art: Anzahl Akten} für die Tagesliste der Startseite."""
    e = e or Einstellungen.aktuell()
    werte = offene_luecken(patienten_qs.values_list("id", flat=True), e)
    return {art: sum(1 for arten in werte.values() if art in arten) for art in REGELN}
