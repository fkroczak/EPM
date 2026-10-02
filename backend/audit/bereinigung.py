"""
Datenschutz im Audit-Log: was beim endgültigen Löschen einer Akte und nach Ablauf der eingestellten
Aufbewahrung mit den Einträgen geschieht.

- Akte gelöscht: Die Einträge zu dieser Akte bleiben als Nachweis (wer, wann, welche Art von Vorgang), verlieren
  aber Namen, Titel und Freitexte. Übrig bleibt „Akte Nr. NNNN (gelöscht)“.
- Aufbewahrung des Audit-Logs (Vorlagen › Grenzwerte, 0 = unbegrenzt): ältere Einträge werden einmal täglich
  entfernt; die Bereinigung steht selbst im Audit-Log.

Beides läuft im Wartungsmodus der Datenbank (sonst verhindern die Trigger jede Änderung am Protokoll).
"""
import logging

from django.db.models import Q
from django.utils import timezone

from .models import SystemEreignis, protokolliere
from .schutz import wartungsmodus

log = logging.getLogger(__name__)
A = SystemEreignis.Art

# Angaben ohne Personenbezug, die nach dem Löschen der Akte am Eintrag bleiben
BLEIBT = {"patient_id", "nach_id", "was", "format", "anlass", "aktion", "weg", "rechtsgrund", "ergebnis", "bereich",
          "auf_anordnung", "art"}
OHNE_GRUND = "(mit der Akte gelöscht)"


def akte_text(patient) -> str:
    """Bezeichnung einer Akte im Audit-Log; an der Endung „(Nr. N)“ werden die Einträge beim Löschen gefunden."""
    return f"Akte {patient.nachname}, {patient.vorname} (Nr. {patient.nummer})"


def geloescht_text(nummer) -> str:
    return f"Akte Nr. {nummer} (gelöscht)"


def akte_entfernen(patient_id: int, nummer: int, dokument_ids=()) -> int:
    """Namen und Inhalte der Einträge zu einer endgültig gelöschten Akte entfernen. Nur im Wartungsmodus aufrufen.

    Gefunden werden die Einträge über ``details.patient_id`` (alle Einträge seit Einführung) und – für ältere
    Einträge – über die Patientennummer im Text. Liefert die Anzahl der geänderten Einträge."""
    marke = f"(Nr. {nummer})"
    bedingung = (
        Q(details__patient_id=patient_id) | Q(details__nach_id=patient_id)
        | Q(art__in=[A.AKTE_ABGESCHLOSSEN, A.AKTE_GEOEFFNET], objekt=str(nummer))
        | Q(objekt__endswith=marke) | Q(objekt__endswith=f"/ Patient {nummer}")
        | Q(details__von__endswith=marke) | Q(details__nach__endswith=marke) | Q(details__akte__endswith=marke)
    )
    if dokument_ids:
        bedingung |= Q(art__in=[A.DOKUMENT_UMGEHAENGT, A.DOKUMENT_GELOESCHT, A.DOKUMENT_LOESCHEN_ABGELEHNT],
                       objekt__in=[f"Dokument {i}" for i in dokument_ids])
    anzahl = 0
    for e in SystemEreignis.objects.filter(bedingung):
        d = dict(e.details or {})
        if d.get("entfernt"):
            continue
        ist_von = d.get("patient_id") == patient_id or str(d.get("von", "")).endswith(marke)
        ist_nach = d.get("nach_id") == patient_id or str(d.get("nach", "")).endswith(marke)
        if e.art == A.DOKUMENT_UMGEHAENGT and ist_von and not ist_nach:
            # Das Dokument liegt weiter in der anderen Akte: nur die gelöschte Seite und der Freitext entfallen
            d.update(von=f"gelöschte Akte Nr. {nummer}", grund=OHNE_GRUND)
            SystemEreignis.objects.filter(pk=e.pk).update(details=d)
        else:
            neu = {k: v for k, v in d.items() if k in BLEIBT}
            neu["entfernt"] = True
            SystemEreignis.objects.filter(pk=e.pk).update(objekt=geloescht_text(nummer), details=neu)
        anzahl += 1
    return anzahl


def bereinigen() -> dict:
    """Abgelaufenes entfernen: Audit-Einträge nach der eingestellten Aufbewahrung, abgelaufene Sitzungen."""
    from django.contrib.sessions.models import Session

    from accounts.models import Sitzung
    from patienten.models import plus_jahre
    from stammdaten.models import Einstellungen

    ergebnis = {"protokoll": 0, "sitzungen": 0}
    jahre = Einstellungen.aktuell().protokoll_aufbewahrung_jahre
    if jahre:
        grenze = plus_jahre(timezone.now(), -jahre)
        with wartungsmodus():
            ergebnis["protokoll"], _ = SystemEreignis.objects.filter(zeitpunkt__lt=grenze).delete()
        if ergebnis["protokoll"]:
            protokolliere(A.PROTOKOLL_BEREINIGT, objekt="Audit-Log", anzahl=ergebnis["protokoll"], jahre=jahre)
    ergebnis["sitzungen"], _ = Session.objects.filter(expire_date__lt=timezone.now()).delete()
    Sitzung.objects.exclude(sitzungsschluessel__in=Session.objects.values("session_key")).delete()
    return ergebnis


_zuletzt = None


def taeglich():
    """Höchstens einmal am Tag je Prozess (wird beim Öffnen der Startseite angestoßen; ein Fehler stört die Seite nicht)."""
    global _zuletzt
    heute = timezone.localdate()
    if _zuletzt == heute:
        return
    _zuletzt = heute
    try:
        bereinigen()
    except Exception:  # noqa: BLE001 – Aufräumen darf die Startseite nie verhindern
        log.exception("Tägliche Bereinigung fehlgeschlagen")
