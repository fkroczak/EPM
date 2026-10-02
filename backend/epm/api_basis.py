"""Gemeinsame API-Bausteine: Fehlerbehandlung, Bereich des Benutzers (Testdaten), Rich-Text."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler, set_rollback

from epm.sanitize import bereinige_html
from patienten.models import AkteGesperrt, Akteneinsicht, Patient


def exception_handler(exc, context):
    """Regelverletzungen aus den Modellen als verständliche API-Fehler ausgeben."""
    if isinstance(exc, AkteGesperrt):
        set_rollback()
        return Response({"fehler": exc.messages[0]}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.message_dict if hasattr(exc, "error_dict") else {"fehler": exc.messages})
    if isinstance(exc, PermissionError):
        set_rollback()
        return Response({"fehler": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, DatabaseError) and "EPM:" in str(exc):
        # DB-Trigger hat eine unzulässige Änderung abgelehnt
        set_rollback()
        meldung = str(exc).split("EPM:", 1)[1].splitlines()[0].strip()
        return Response({"fehler": meldung}, status=status.HTTP_403_FORBIDDEN)
    return drf_handler(exc, context)


def patienten_fuer(user, eingeschraenkte: bool = False):
    """Akten im Bereich des Benutzers: Testbenutzer sehen ausschließlich Testpatienten.

    Akten, deren Verarbeitung eingeschränkt ist (Art. 18 DSGVO), erscheinen nirgends – nicht in Listen, nicht in
    der Suche, nicht mit ihren Einträgen –, außer für die Person, die gerade eine begründete Einsicht hat.
    ``eingeschraenkte=True`` liefert auch sie – nur für Stellen, die keine Inhalte zeigen (Hinweis „eingeschränkt“
    mit Nummer, Zählen). Für die Datenschutz-Vorgänge selbst: ``patienten_mit_eingeschraenkten``."""
    qs = Patient.objects.all()
    if getattr(user, "ist_test", False):
        qs = qs.filter(ist_test=True)
    if not eingeschraenkte:
        einsicht = Akteneinsicht.objects.filter(benutzer_id=getattr(user, "pk", None), bis__gt=timezone.now())
        qs = qs.filter(Q(eingeschraenkt_am__isnull=True) | Q(id__in=einsicht.values("patient_id")))
    return qs


def darf_einsicht(user, patient) -> bool:
    """Darf diese Person in die eingeschränkte Akte Einsicht nehmen? Recht „Datenschutz: Anfragen entscheiden …“;
    Admins nur bei Testpatienten."""
    from accounts.rechte import schreibt_nur_testpatienten

    if not user.hat_recht("datenschutz_entscheiden"):
        return False
    if getattr(user, "ist_test", False) and not patient.ist_test:
        return False
    return patient.ist_test or not schreibt_nur_testpatienten(user)


def patienten_mit_eingeschraenkten(user):
    """Wie ``patienten_fuer``, zusätzlich die eingeschränkten Akten, in die diese Person Einsicht nehmen dürfte.

    Für die Datenschutz-Vorgänge selbst (Übersicht, Anfragen, einschränken, aufheben, löschen): Wer über eine
    eingeschränkte Akte entscheidet, muss sie finden können. Alle anderen sehen von ihr höchstens die Nummer."""
    from accounts.rechte import schreibt_nur_testpatienten

    if not user.hat_recht("datenschutz_entscheiden"):
        return patienten_fuer(user)
    qs = patienten_fuer(user, eingeschraenkte=True)
    if schreibt_nur_testpatienten(user):
        einsicht = Akteneinsicht.objects.filter(benutzer_id=user.pk, bis__gt=timezone.now())
        qs = qs.filter(Q(eingeschraenkt_am__isnull=True) | Q(ist_test=True) | Q(id__in=einsicht.values("patient_id")))
    return qs


NUR_TESTPATIENTEN_TEXT = "Als Admin nur bei Testpatienten möglich. Echte Akten sind für die Administration nur lesbar."


def pruefe_schreibbereich(user, patient, loeschen: bool = False, recht: str | None = None):
    """Admins schreiben Patientendaten nur bei Testpatienten (Festlegung 01.10.2026) → sonst 403.
    Ausnahmen (Festlegungen 02.10.2026, ``accounts.rechte.AUCH_BEI_ECHTEN_AKTEN``): endgültig löschen (``loeschen``;
    Dokumente F73, Akten F80), Dokumente einem anderen Patienten zuordnen und Akten abschließen (``recht``) dürfen
    Admins auch bei echten Akten."""
    from accounts.rechte import AUCH_BEI_ECHTEN_AKTEN, schreibt_nur_testpatienten

    if loeschen or recht in AUCH_BEI_ECHTEN_AKTEN:
        return
    if schreibt_nur_testpatienten(user) and not patient.ist_test:
        raise PermissionError(NUR_TESTPATIENTEN_TEXT)


def legt_testpatienten_an(user, gewuenscht: bool = False) -> bool:
    """Testbenutzer und Admins legen nur Testpatienten an. Alle anderen können beim Anlegen einen Testpatienten
    wählen (``gewuenscht``, Fehlerliste 02.10.2026) – z. B. um Infusionspläne auszuprobieren."""
    from accounts.rechte import schreibt_nur_testpatienten

    return bool(gewuenscht or getattr(user, "ist_test", False) or schreibt_nur_testpatienten(user))


def wahr(wert) -> bool:
    """„1“, „true“, „ja“, True → True (Schalter in Anfragen)"""
    return wert is True or str(wert).strip().lower() in ("1", "true", "ja", "on")


class RichText(serializers.CharField):
    """Formatierter Text: wird beim Speichern auf erlaubte Tags bereinigt."""

    def __init__(self, **kwargs):
        kwargs.setdefault("allow_blank", True)
        kwargs.setdefault("required", False)
        kwargs.setdefault("trim_whitespace", False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        return bereinige_html(super().to_internal_value(data))


class ModelClean:
    """Ruft Model.clean() im Serializer auf, damit Plausibilitätsprüfungen als 400 zurückkommen."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instanz = self.instance or self.Meta.model()
        vorher = {}
        for k, v in attrs.items():
            if not isinstance(v, list):
                vorher[k] = getattr(instanz, k, None)
                setattr(instanz, k, v)
        try:
            instanz.clean()
        except DjangoValidationError as e:
            raise ValidationError(e.message_dict if hasattr(e, "error_dict") else {"fehler": e.messages})
        finally:
            if self.instance is not None:
                for k, v in vorher.items():
                    setattr(instanz, k, v)
        return attrs


def benutzername(user):
    return user.anzeigename if user else None
