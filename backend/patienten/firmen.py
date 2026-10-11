"""Akten zwei Firmen zuordnen (Anforderung 11.10.2026: DSKM und Regeneration Clinic teilen sich zum Teil Patienten).

Eine Akte gehört einer oder beiden Firmen (``PatientFirma``). Beide sehen dann die ganze Akte; jeder Eintrag zeigt,
in welcher Firma er erfasst wurde. Weil es zwei Verantwortliche nach DSGVO sind, kommt eine weitere Firma nur mit
erfasster Einwilligung dazu (``Erklaerung.Art.FIRMEN``, nicht widerrufen). Die Einwilligung kann beim Zuordnen gleich
mit erfasst werden (Datum der Unterschrift). Jede Änderung steht im Audit-Log und im Verlauf der Akte.
"""
from django.db import transaction

from stammdaten.models import Firma

from .models import Erklaerung, PatientFirma


class FirmenFehler(ValueError):
    def __init__(self, feld: str, text: str):
        super().__init__(text)
        self.feld, self.text = feld, text


def einwilligung_liegt_vor(patient) -> bool:
    """Gilt die Einwilligung für den Austausch zwischen den Firmen? (erfasst, nicht widerrufen)"""
    return Erklaerung.objects.filter(patient=patient, art=Erklaerung.Art.FIRMEN, widerrufen_am__isnull=True).exists()


def firmen_von(patient) -> list[str]:
    return list(PatientFirma.objects.filter(patient=patient).order_by("firma__reihenfolge", "firma_id")
                .values_list("firma__kuerzel", flat=True))


@transaction.atomic
def firmen_setzen(patient, kuerzel: list[str], benutzer, einwilligung_am=None) -> tuple[list[str], list[str]]:
    """Setzt die Firmen der Akte; liefert (hinzugekommen, entfernt). ``einwilligung_am``: Einwilligung bei der
    Gelegenheit erfassen. Fehler als ``FirmenFehler``."""
    gewuenscht = list(dict.fromkeys(k for k in kuerzel if k))
    firmen = {f.kuerzel: f for f in Firma.objects.filter(kuerzel__in=gewuenscht, aktiv=True)}
    if not gewuenscht:
        raise FirmenFehler("firmen", "Die Akte muss mindestens einer Firma gehören.")
    unbekannt = [k for k in gewuenscht if k not in firmen]
    if unbekannt:
        raise FirmenFehler("firmen", f"Unbekannte Firma: {', '.join(unbekannt)}.")
    bisher = set(firmen_von(patient))
    neu = [k for k in gewuenscht if k not in bisher]
    weg = [k for k in bisher if k not in gewuenscht]
    if len(gewuenscht) > 1 and neu and not einwilligung_liegt_vor(patient):
        if einwilligung_am is None:
            raise FirmenFehler("einwilligung_am", "Für die Zuordnung zu mehreren Firmen fehlt die Einwilligung des "
                                                  "Patienten zum Austausch zwischen den Firmen. Bitte das Datum der "
                                                  "Unterschrift angeben.")
        Erklaerung.objects.create(patient=patient, art=Erklaerung.Art.FIRMEN, erteilt_am=einwilligung_am,
                                  notiz="bei der Zuordnung zu den Firmen erfasst", erfasst_von=benutzer)
    for k in neu:
        _zuordnen(patient, firmen[k], benutzer)
    for z in PatientFirma.objects.filter(patient=patient, firma__kuerzel__in=weg):
        z._history_user = benutzer
        z.delete()
    return neu, weg


def _zuordnen(patient, firma, benutzer):
    z = PatientFirma(patient=patient, firma=firma, zugeordnet_von=benutzer)
    z._history_user = benutzer
    z.save()
