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
import re
from datetime import timedelta

from django.db import transaction
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


def akte_bedingung(patient_id: int, nummer: int) -> Q:
    """Einträge des Audit-Logs, die diese Akte betreffen: über ``details.patient_id`` (alle Einträge seit
    Einführung) und – für ältere Einträge – über die Patientennummer im Text."""
    marke = f"(Nr. {nummer})"
    return (
        Q(details__patient_id=patient_id) | Q(details__nach_id=patient_id)
        | Q(art__in=[A.AKTE_ABGESCHLOSSEN, A.AKTE_GEOEFFNET], objekt=str(nummer))
        | Q(objekt__endswith=marke) | Q(objekt__endswith=f"/ Patient {nummer}")
        | Q(details__von__endswith=marke) | Q(details__nach__endswith=marke) | Q(details__akte__endswith=marke)
    )


SUCHE = re.compile(r"Suche „[^“]*“")


def akte_entfernen(patient_id: int, nummer: int, dokument_ids=(), namen=()) -> int:
    """Namen und Inhalte der Einträge zu einer endgültig gelöschten Akte entfernen. Nur im Wartungsmodus aufrufen.

    ``dokument_ids``: Dokumente, die mit der Akte enden (darin liegen oder darin endgültig gelöscht wurden) – ihre
    Einträge verlieren Titel und Freitext ganz. Ein Dokument, das in einer anderen Akte weiterlebt, behält seinen
    Eintrag; nur die gelöschte Seite und der Freitext entfallen. ``namen``: Nachname und Vorname – ein Suchbegriff,
    der in einem Eintrag „Audit-Log als PDF“ festgehalten ist und einen der Namen enthält, wird entfernt.
    Liefert die Anzahl der geänderten Einträge."""
    marke = f"(Nr. {nummer})"
    eigene = {f"Dokument {i}" for i in dokument_ids}
    bedingung = akte_bedingung(patient_id, nummer)
    if eigene:
        bedingung |= Q(art__in=[A.DOKUMENT_UMGEHAENGT, A.DOKUMENT_GELOESCHT, A.DOKUMENT_LOESCHEN_ABGELEHNT],
                       objekt__in=sorted(eigene))
    anzahl = 0
    for e in SystemEreignis.objects.filter(bedingung):
        d = dict(e.details or {})
        if d.get("entfernt"):
            continue
        ist_von = d.get("patient_id") == patient_id or str(d.get("von", "")).endswith(marke)
        ist_nach = d.get("nach_id") == patient_id or str(d.get("nach", "")).endswith(marke)
        if e.art == A.DOKUMENT_UMGEHAENGT and ist_von and not ist_nach and e.objekt not in eigene:
            # Das Dokument liegt weiter in der anderen Akte: nur die gelöschte Seite und der Freitext entfallen
            d.update(von=f"gelöschte Akte Nr. {nummer}", grund=OHNE_GRUND)
            SystemEreignis.objects.filter(pk=e.pk).update(details=d)
        else:
            neu = {k: v for k, v in d.items() if k in BLEIBT}
            neu["entfernt"] = True
            SystemEreignis.objects.filter(pk=e.pk).update(objekt=geloescht_text(nummer), details=neu)
        anzahl += 1
    # „Audit-Log als PDF“ hält den Suchbegriff fest – war es der Name, verschwindet er hier
    for name in {n.strip() for n in namen if n and len(n.strip()) >= 2}:
        for e in SystemEreignis.objects.filter(art=A.EXPORT, details__was="Audit-Log", objekt__icontains=name):
            neu = SUCHE.sub("Suche „[entfernt]“", e.objekt)
            if neu != e.objekt:
                SystemEreignis.objects.filter(pk=e.pk).update(objekt=neu)
                anzahl += 1
    return anzahl


# ---------------------------------------------------------------- Akten mit eingeschränkter Verarbeitung
NUMMER_IM_TEXT = re.compile(r"(?:\(Nr\. (\d+)\)|/ Patient (\d+))$")


def betrifft(e, ids: dict, nummern: set) -> int | None:
    """Betrifft der Eintrag eine dieser Akten ({interne Kennung: Nummer})? Liefert die Patientennummer."""
    d = e.details or {}
    for schluessel in ("patient_id", "nach_id"):
        wert = d.get(schluessel)
        if isinstance(wert, int) and wert in ids:
            return ids[wert]
    texte = [e.objekt or "", str(d.get("von", "")), str(d.get("nach", "")), str(d.get("akte", ""))]
    for text in texte:
        m = NUMMER_IM_TEXT.search(text)
        if m and int(m.group(1) or m.group(2)) in nummern:
            return int(m.group(1) or m.group(2))
    if e.art in (A.AKTE_ABGESCHLOSSEN, A.AKTE_GEOEFFNET) and (e.objekt or "").isdigit() and int(e.objekt) in nummern:
        return int(e.objekt)
    return None


def verbergen(eintraege, verborgen: dict):
    """Einträge zu Akten mit eingeschränkter Verarbeitung für Personen ohne Einsichtsrecht: Der Eintrag bleibt
    sichtbar (wer, wann, welche Art), Name, Titel und Freitext nicht. ``verborgen``: {interne Kennung: Nummer}.
    Ändert nur die übergebenen Objekte im Speicher, nichts in der Datenbank."""
    if not verborgen:
        return eintraege
    nummern = set(verborgen.values())
    for e in eintraege:
        nummer = betrifft(e, verborgen, nummern)
        if nummer is not None:
            e.objekt = f"Akte Nr. {nummer} (Verarbeitung eingeschränkt)"
            e.details = {**{k: v for k, v in (e.details or {}).items() if k in BLEIBT}, "verborgen": True}
    return eintraege


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
    # Erfasste Sitzungen (Gerät, IP) ohne gültige Anmeldung – nur ältere: Beim Wechsel des Sitzungsschlüssels (z. B.
    # Kennwortwechsel) gibt es für einen Augenblick einen Eintrag ohne Sitzung, der nicht verschwinden darf.
    gestern = timezone.now() - timedelta(days=1)
    Sitzung.objects.filter(zuletzt_am__lt=gestern).exclude(sitzungsschluessel__in=Session.objects.values("session_key")).delete()
    return ergebnis


_zuletzt = None


def taeglich():
    """Höchstens einmal am Tag je Prozess des Backends (angestoßen beim Öffnen der Startseite; mehrere Prozesse
    räumen nacheinander auf, das schadet nicht). Ein Fehler stört die Seite nicht."""
    global _zuletzt
    heute = timezone.localdate()
    if _zuletzt == heute:
        return
    _zuletzt = heute
    try:
        with transaction.atomic():  # eigener Sicherungspunkt: ein Fehler hier bricht die Anfrage nicht ab
            bereinigen()
    except Exception:  # noqa: BLE001 – Aufräumen darf die Startseite nie verhindern
        log.exception("Tägliche Bereinigung fehlgeschlagen")
