"""
Rechte für die API – je Gruppe einstellbar (accounts/rechte.py, Oberfläche: Benutzer › Rechte).

Lesen setzt „Akten lesen“ voraus, Schreiben das jeweilige Recht. Jeder Zugriff setzt eine
vollständige Anmeldung voraus: Kennwort, kein offenes Einmal-Kennwort und – wenn eingerichtet oder
Pflicht (accounts/zweifaktor.py) – der zweite Faktor.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission


def ist_verifiziert(user) -> bool:
    """Zweiter Faktor in dieser Sitzung bestätigt (django-otp)."""
    pruefung = getattr(user, "is_verified", None)
    if callable(pruefung):
        return bool(pruefung())
    return getattr(user, "otp_device", None) is not None


def zweiter_faktor_erfuellt(user) -> bool:
    """Zweiter Faktor bestätigt – oder für diese Person nicht nötig: Er ist freiwillig (Festlegung 02.10.2026,
    ``Anmelderegeln``) und sie hat keinen eingerichtet. Wer einen eingerichtet hat, braucht ihn bei jeder Anmeldung."""
    if ist_verifiziert(user):
        return True
    from .zweifaktor import hat_zweiten_faktor, pflicht

    return not hat_zweiten_faktor(user) and not pflicht(user)


def voll_angemeldet(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and not user.muss_kennwort_aendern
        and zweiter_faktor_erfuellt(user)
    )


class Angemeldet(BasePermission):
    # Der Wortlaut ist Teil des Vertrags mit der Oberfläche (lib/api.ts erkennt daran die abgelaufene Anmeldung)
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
            if self.lesen is None:
                # gemeinsame Listen (Versorger, Ärzte, Auswahllisten): jeder Angemeldete – außer „Keine Berechtigung“
                from .rechte import OHNE_RECHTE

                return request.user.rolle not in OHNE_RECHTE
            return request.user.hat_recht(self.lesen)
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
SystemRecht = nur_recht("system_verwalten")          # Administration › System (nur Admin)
ImportRecht = nur_recht("altdaten_importieren")      # Administration › Import (nur Admin)
PlanAbschlussRecht = recht("plaene_abschliessen")
DatenschutzRecht = recht("datenschutz_bearbeiten")
DatenschutzEntscheidenRecht = recht("datenschutz_entscheiden")
AkteLoeschenRecht = recht("akten_loeschen")
BerichtFreigabeRecht = recht("berichte_freigeben")   # Bericht abschließen (F115)


class DatenschutzLesen(Angemeldet):
    """Übersicht „Datenschutz“: wer Anfragen erfasst oder entscheidet."""

    message = "Dafür fehlt das Recht „Datenschutz“."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            self.message = Angemeldet.message
            return False
        return request.user.hat_recht("datenschutz_bearbeiten") or request.user.hat_recht("datenschutz_entscheiden")
