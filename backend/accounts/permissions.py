"""
Rollenrechte für die API.

| Rolle        | Lesen | Patientendaten | Infusionspläne | Stammdaten/Benutzer |
|--------------|-------|----------------|----------------|---------------------|
| Betrachter   | ja    | –              | –              | –                   |
| Mitarbeiter  | ja    | ja             | –              | –                   |
| Mediziner    | ja    | ja             | ja (Freigabe)  | –                   |
| Admin        | ja    | –              | –              | ja                  |

Akten abschließen dürfen nur Mediziner, wieder öffnen nur der Admin (Rollenmatrix Entwurf 17).
Versorger und Ansprechpartner pflegen Mitarbeiter, Mediziner und Admin (siehe Unklarheit U10).

Jeder Zugriff setzt eine vollständige Anmeldung voraus: Kennwort + zweiter Faktor
und kein offenes Einmal-Kennwort.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Rolle


def ist_verifiziert(user) -> bool:
    """Zweiter Faktor in dieser Sitzung bestätigt (django-otp)."""
    pruefung = getattr(user, "is_verified", None)
    if callable(pruefung):
        return bool(pruefung())
    return getattr(user, "otp_device", None) is not None


def voll_angemeldet(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and ist_verifiziert(user)
        and not user.muss_kennwort_aendern
    )


class Angemeldet(BasePermission):
    message = "Anmeldung mit zweitem Faktor erforderlich."

    def has_permission(self, request, view):
        return voll_angemeldet(request.user)


class _Schreibrecht(Angemeldet):
    rollen: tuple = ()

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.rolle in self.rollen


class PatientendatenRecht(_Schreibrecht):
    message = "Patientendaten dürfen nur Mitarbeiter und Mediziner ändern."
    rollen = (Rolle.MITARBEITER, Rolle.MEDIZINER)


class PlanRecht(_Schreibrecht):
    message = "Infusionspläne dürfen nur Mediziner bearbeiten."
    rollen = (Rolle.MEDIZINER,)


class StammdatenRecht(_Schreibrecht):
    message = "Stammdaten pflegt nur der Admin."
    rollen = (Rolle.ADMIN,)


class NurAdmin(Angemeldet):
    message = "Nur für Admins."

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.rolle == Rolle.ADMIN


class AbschlussRecht(Angemeldet):
    message = "Akten abschließen dürfen nur Mediziner."

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.rolle == Rolle.MEDIZINER


class VersorgerRecht(_Schreibrecht):
    message = "Versorger pflegen Mitarbeiter, Mediziner und Admin."
    rollen = (Rolle.MITARBEITER, Rolle.MEDIZINER, Rolle.ADMIN)
