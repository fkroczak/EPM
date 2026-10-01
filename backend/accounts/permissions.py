"""
Rechte für die API – je Gruppe einstellbar (accounts/rechte.py, Oberfläche: Benutzer › Rechte).

Lesen setzt „Akten lesen“ voraus, Schreiben das jeweilige Recht. Jeder Zugriff setzt eine
vollständige Anmeldung voraus: Kennwort + zweiter Faktor und kein offenes Einmal-Kennwort.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission


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


class _Recht(Angemeldet):
    """Lesen mit `lesen` (None = jeder Angemeldete), Schreiben mit `schreiben`."""

    lesen: str | None = "akten_lesen"
    schreiben: str = ""
    message = "Dafür fehlt das Recht."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            self.message = Angemeldet.message  # abgelaufene Sitzung, nicht fehlendes Recht
            return False
        if request.method in SAFE_METHODS:
            return self.lesen is None or request.user.hat_recht(self.lesen)
        return request.user.hat_recht(self.schreiben)


def recht(schreiben: str, lesen: str | None = "akten_lesen", meldung: str = ""):
    """Permission-Klasse für ein bestimmtes Recht, z. B. ``recht("plaene_freigeben")``."""
    from .rechte import NAMEN

    return type(
        f"Recht_{schreiben}",
        (_Recht,),
        {"schreiben": schreiben, "lesen": lesen,
         "message": meldung or f"Dafür fehlt das Recht „{NAMEN.get(schreiben, schreiben)}“."},
    )


def nur_recht(code: str):
    """Jede Methode (auch Lesen) nur mit diesem Recht, z. B. Audit-Log oder Benutzerverwaltung."""
    return recht(code, lesen=code)


# Rechte der Endpunkte (früher feste Rollen)
AktenRecht = recht("akten_bearbeiten")          # Patienten anlegen, Stammdaten, Diagnose, Therapie
EintragRecht = recht("eintraege_erfassen")      # Kontakte, Gewichte, Termine, Dokumente
PlanRecht = recht("plaene_anlegen")
FreigabeRecht = recht("plaene_freigeben")
AbschlussRecht = recht("akten_abschliessen")
WiederOeffnenRecht = recht("akten_wieder_oeffnen")
StammdatenRecht = recht("vorlagen_pflegen", lesen=None)
VersorgerRecht = recht("versorger_pflegen", lesen=None)
BenutzerRecht = nur_recht("benutzer_verwalten")
AuditRecht = nur_recht("audit_lesen")
TestdatenRecht = nur_recht("testdaten_zuruecksetzen")
UmhaengenRecht = recht("dokumente_umhaengen")
LoeschenRecht = recht("dokumente_loeschen")
