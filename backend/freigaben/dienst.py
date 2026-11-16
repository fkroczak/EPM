"""Freigeben, zurücknehmen, umsetzen (Menü „Freigaben“, 16.11.2026).

Eine Freigabe wird nicht sofort ausgeführt: Sie wartet ``RUECKGAENGIG_S`` Sekunden und lässt sich so lange mit einem
Klick zurücknehmen. Danach setzt sie um, wer zuerst kommt – die Seite „Freigaben“ (fragt alle paar Sekunden), die
Zahl im Menü oder der OCR-Dienst in seinem Leerlauf. Umgesetzt wird immer mit den Rechten und in der Firma der Person,
die freigegeben hat.
"""
from __future__ import annotations

import datetime as dt
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.models import SystemEreignis, protokolliere

from . import datenpflege
from .models import RUECKGAENGIG_S, Datenpflegevorschlag, Freigabe

log = logging.getLogger("epm.freigaben")
F = Freigabe.Art


def _wartende(art: str, objekt_id: int) -> bool:
    return Freigabe.objects.filter(art=art, objekt_id=objekt_id, status=Freigabe.Status.WARTET).exists()


def freigeben_datenpflege(v: Datenpflegevorschlag, eingabe, user, firma=None) -> Freigabe:
    """Schritte prüfen (Werte, Rechte, Stand) und die Freigabe vormerken. Wirft ``ValidationError``/``PermissionError``."""
    from epm.api_basis import pruefe_schreibbereich

    if v.status != Datenpflegevorschlag.Status.OFFEN:
        raise ValidationError({"fehler": "Dieser Vorschlag ist nicht mehr offen."})
    if _wartende(F.DATENPFLEGE, v.pk):
        raise ValidationError({"fehler": "Dieser Vorschlag ist schon freigegeben und wird gleich umgesetzt."})
    if not user.hat_recht("akten_bearbeiten"):
        raise PermissionError("Dafür fehlt das Recht „Patienten anlegen, Diagnose, Therapie, Stammdaten ändern“.")
    pruefe_schreibbereich(user, v.patient)
    v.patient.pruefe_bearbeitbar()
    schritte = datenpflege.schritte_uebernehmen(v, eingabe)
    # Probelauf in einer Transaktion, die zurückgerollt wird: Fehler (Rechte, veralteter Stand) zeigt die Freigabe
    # sofort – nicht erst nach 60 Sekunden, wenn die Person schon weitergeklickt hat
    try:
        with transaction.atomic():
            datenpflege.umsetzen(Datenpflegevorschlag.objects.get(pk=v.pk), schritte, user)
            raise _Probe()
    except _Probe:
        pass
    return Freigabe.objects.create(art=F.DATENPFLEGE, objekt_id=v.pk, patient=v.patient, firma=firma,
                                   daten={"schritte": schritte}, freigegeben_von=user,
                                   umsetzen_ab=timezone.now() + dt.timedelta(seconds=RUECKGAENGIG_S))


class _Probe(Exception):
    pass


def freigeben_plan(plan, user, firma=None) -> Freigabe:
    from epm.api_basis import pruefe_schreibbereich

    if not user.darf_plaene_freigeben:
        raise PermissionError("Infusionspläne freigeben darf nur, wer das Recht dazu hat.")
    if plan.status != plan.Status.ENTWURF:
        raise ValidationError({"fehler": "Nur Entwürfe können freigegeben werden."})
    if _wartende(F.INFUSIONSPLAN, plan.pk):
        raise ValidationError({"fehler": "Dieser Plan ist schon freigegeben und wird gleich umgesetzt."})
    pruefe_schreibbereich(user, plan.patient)
    plan.patient.pruefe_bearbeitbar()
    return Freigabe.objects.create(art=F.INFUSIONSPLAN, objekt_id=plan.pk, patient=plan.patient, firma=firma,
                                   freigegeben_von=user,
                                   umsetzen_ab=timezone.now() + dt.timedelta(seconds=RUECKGAENGIG_S))


def zuruecknehmen(f: Freigabe, user) -> Freigabe:
    """Nur die Person, die freigegeben hat, und nur solange die Freigabe noch nicht umgesetzt ist."""
    with transaction.atomic():
        f = Freigabe.objects.select_for_update().get(pk=f.pk)
        if f.freigegeben_von_id != user.id:
            raise PermissionError("Zurücknehmen kann nur, wer freigegeben hat.")
        if f.status != Freigabe.Status.WARTET:
            raise ValidationError({"fehler": "Die Freigabe ist schon umgesetzt – zurücknehmen geht nicht mehr."})
        f.status, f.erledigt_am = Freigabe.Status.ZURUECK, timezone.now()
        f.save(update_fields=["status", "erledigt_am"])
    return f


def _ausfuehren(f: Freigabe):
    user = f.freigegeben_von
    if f.art == F.DATENPFLEGE:
        v = Datenpflegevorschlag.objects.get(pk=f.objekt_id)
        ergebnis = datenpflege.umsetzen(v, f.daten["schritte"], user)
        protokolliere(SystemEreignis.Art.STAMMDATEN, benutzer=user, objekt=f"Datenpflege {v.pk} / Patient "
                      f"{v.patient.nummer}", aktion="datenpflege_umgesetzt", patient_id=v.patient_id,
                      schritte=len(ergebnis))
    elif f.art == F.INFUSIONSPLAN:
        from infusionen.models import Infusionsplan

        plan = Infusionsplan.objects.get(pk=f.objekt_id)
        plan.freigeben(user)
        protokolliere(SystemEreignis.Art.PLAN_FREIGEGEBEN, benutzer=user,
                      objekt=f"Plan {plan.id} / Patient {plan.patient.nummer}", patient_id=plan.patient_id,
                      weg="Menü Freigaben")
    else:
        raise ValueError(f"unbekannte Art {f.art}")


def faellige_umsetzen(jetzt: dt.datetime | None = None) -> int:
    """Alle Freigaben, deren Rückgängig-Zeit abgelaufen ist, umsetzen; → Zahl der bearbeiteten."""
    from epm.firma import setze_aktive_firma, zuruecksetzen

    jetzt = jetzt or timezone.now()
    ids = list(Freigabe.objects.filter(status=Freigabe.Status.WARTET, umsetzen_ab__lte=jetzt)
               .order_by("umsetzen_ab").values_list("id", flat=True)[:20])
    anzahl = 0
    for fid in ids:
        with transaction.atomic():
            f = (Freigabe.objects.select_for_update(skip_locked=True, of=("self",))
                 .filter(pk=fid, status=Freigabe.Status.WARTET).select_related("freigegeben_von", "firma").first())
            if f is None:
                continue
            token = setze_aktive_firma(f.firma)
            try:
                with transaction.atomic():
                    _ausfuehren(f)
                f.status, f.fehler = Freigabe.Status.UMGESETZT, ""
            except (ValidationError, PermissionError, Exception) as e:  # noqa: BLE001 – Fehler gehört an die Freigabe
                if not isinstance(e, (ValidationError, PermissionError)):
                    log.exception("Freigabe %s nicht umgesetzt", f.pk)
                f.status, f.fehler = Freigabe.Status.FEHLER, _meldung(e)
                if isinstance(e, datenpflege.Veraltet):
                    Datenpflegevorschlag.objects.filter(pk=f.objekt_id, status="offen").update(
                        status=Datenpflegevorschlag.Status.VERALTET, erledigt_am=timezone.now())
            finally:
                zuruecksetzen(token)
            f.erledigt_am = timezone.now()
            f.save(update_fields=["status", "fehler", "erledigt_am"])
            anzahl += 1
    return anzahl


def _meldung(e: Exception) -> str:
    if isinstance(e, ValidationError):
        if hasattr(e, "message_dict"):
            return " ".join(str(m) for ms in e.message_dict.values() for m in ms)[:1000]
        return " ".join(e.messages)[:1000]
    if isinstance(e, PermissionError):
        return str(e)[:1000]
    return f"Unerwarteter Fehler ({type(e).__name__}) – bitte erneut versuchen oder die Administration fragen."
