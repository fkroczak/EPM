"""Gemeinsame API-Bausteine: Fehlerbehandlung, Bereich des Benutzers (Testdaten), Rich-Text."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler, set_rollback

from epm.sanitize import bereinige_html
from patienten.models import AkteGesperrt, Patient


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


def patienten_fuer(user):
    """Testbenutzer sehen ausschließlich Testpatienten."""
    qs = Patient.objects.all()
    if getattr(user, "ist_test", False):
        qs = qs.filter(ist_test=True)
    return qs


NUR_TESTPATIENTEN_TEXT = "Als Admin nur bei Testpatienten möglich. Echte Akten sind für die Administration nur lesbar."


def pruefe_schreibbereich(user, patient):
    """Admins schreiben Patientendaten nur bei Testpatienten (Festlegung 01.10.2026) → sonst 403."""
    from accounts.rechte import schreibt_nur_testpatienten

    if schreibt_nur_testpatienten(user) and not patient.ist_test:
        raise PermissionError(NUR_TESTPATIENTEN_TEXT)


def legt_testpatienten_an(user) -> bool:
    """Testbenutzer und Admins legen nur Testpatienten an."""
    from accounts.rechte import schreibt_nur_testpatienten

    return bool(getattr(user, "ist_test", False) or schreibt_nur_testpatienten(user))


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
