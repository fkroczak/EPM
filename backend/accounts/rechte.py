"""
Rechte je Gruppe (Rolle). Die Administration legt sie in der Oberfläche fest (Benutzer › Rechte).

Festlegungen vom 01.10.2026:
- Mediziner sind dem Admin gleichgestellt, ausgenommen Benutzerverwaltung und sehr spezifische
  Eingriffe (abgeschlossene Akten wieder öffnen, Sicherungen, Testdaten).
- Akten abschließen: Mitarbeiter, Mediziner und Admin. Vorlagen pflegen: auch Mitarbeiter und Mediziner.
- Admins dürfen alles, Patientendaten schreiben sie aber nur bei Testpatienten; echte Akten sind für
  sie nur lesbar (Wieder öffnen, Benutzer, Sicherungen bleiben).
Für Betrachter gilt die Rollenmatrix aus dem Entwurf 17.

Was nicht ausdrücklich in der Datenbank steht, kommt aus STANDARD. Testbenutzer erhalten nie
Rechte, die über Testpatienten hinaus wirken (Vorlagen, Versorger, Audit-Log, Verwaltung).
"""
from .models import Rolle

# (Code, Bezeichnung, Erläuterung) – Reihenfolge wie in der Oberfläche
RECHTE = [
    ("akten_lesen", "Akten lesen", "Patientenliste, Akten, Verlauf und Infusionspläne ansehen"),
    ("eintraege_erfassen", "Kontakte, Gewichte, Termine, Dokumente erfassen",
     "Einträge in der Akte anlegen; Kontakte stornieren, Termine erledigen"),
    ("akten_bearbeiten", "Patienten anlegen, Diagnose, Therapie, Stammdaten ändern", ""),
    ("plaene_anlegen", "Infusionspläne anlegen", "Entwürfe anlegen, bearbeiten und verwerfen"),
    ("plaene_freigeben", "Infusionspläne freigeben", ""),
    ("akten_abschliessen", "Akten abschließen", ""),
    ("akten_wieder_oeffnen", "Abgeschlossene Akten wieder öffnen", ""),
    ("versorger_pflegen", "Versorger, Ansprechpartner und Ärzte pflegen",
     "gemeinsame Listen: Versorger mit Ansprechpartnern, Ärzte mit Kontaktdaten"),
    ("vorlagen_pflegen", "Vorlagen pflegen", "Briefkopf und Logo, Auswahllisten, Präparate, Grenzwerte"),
    ("audit_lesen", "Audit-Log lesen", ""),
    ("benutzer_verwalten", "Benutzer und Rechte verwalten",
     "Benutzer anlegen, sperren, Einmal-Kennwort, 2FA zurücksetzen, Rechte der Gruppen"),
    ("backup_verwalten", "Sicherungen verwalten", "Sicherung starten, wiederherstellen"),
    ("testdaten_zuruecksetzen", "Testdaten zurücksetzen", ""),
]
CODES = [code for code, _, _ in RECHTE]
NAMEN = {code: name for code, name, _ in RECHTE}

_ALLE = set(CODES)
_ADMIN_SPEZIAL = {"benutzer_verwalten", "akten_wieder_oeffnen", "backup_verwalten", "testdaten_zuruecksetzen"}

# Rechte, die Patientendaten verändern (Einträge, Stammdaten, Pläne, Abschluss)
PATIENTENDATEN_SCHREIBEN = {"eintraege_erfassen", "akten_bearbeiten", "plaene_anlegen", "plaene_freigeben",
                            "akten_abschliessen"}

STANDARD = {
    Rolle.BETRACHTER: {"akten_lesen"},
    Rolle.MITARBEITER: {"akten_lesen", "eintraege_erfassen", "akten_bearbeiten", "akten_abschliessen",
                        "versorger_pflegen", "vorlagen_pflegen"},
    Rolle.MEDIZINER: _ALLE - _ADMIN_SPEZIAL,
    Rolle.ADMIN: set(_ALLE),
}

# Diese Rollen schreiben Patientendaten nur bei Testpatienten (fest, unabhängig von der Matrix)
NUR_TESTPATIENTEN_SCHREIBEN = {Rolle.ADMIN}

# Diese Rechte kann niemand entziehen (sonst sperrt sich die Administration aus)
FEST = {(Rolle.ADMIN, "benutzer_verwalten"), (Rolle.ADMIN, "akten_lesen")}

# Testbenutzer arbeiten nur mit Testpatienten; alles, was darüber hinaus wirkt, bleibt verwehrt
NUR_ECHTE_BENUTZER = {"versorger_pflegen", "vorlagen_pflegen", "audit_lesen", "benutzer_verwalten",
                      "backup_verwalten", "testdaten_zuruecksetzen", "akten_wieder_oeffnen"}


def matrix() -> dict:
    """{rolle: {recht: bool}} aus Standard und gespeicherten Abweichungen."""
    from .models import Gruppenrecht

    ergebnis = {rolle: {code: code in STANDARD[rolle] for code in CODES} for rolle in Rolle.values}
    for rolle, recht, erlaubt in Gruppenrecht.objects.values_list("rolle", "recht", "erlaubt"):
        if rolle in ergebnis and recht in NAMEN:
            ergebnis[rolle][recht] = erlaubt
    for rolle, recht in FEST:
        ergebnis[rolle][recht] = True
    return ergebnis


def rechte_fuer(user) -> frozenset:
    """Rechte eines Benutzers (eine kleine Abfrage; bewusst ohne Zwischenspeicher, damit
    Änderungen der Administration sofort gelten)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()
    werte = matrix().get(user.rolle, {})
    rechte = {code for code, erlaubt in werte.items() if erlaubt}
    if getattr(user, "ist_test", False):
        rechte -= NUR_ECHTE_BENUTZER
    return frozenset(rechte)


def hat_recht(user, code: str) -> bool:
    return code in rechte_fuer(user)


def schreibt_nur_testpatienten(user) -> bool:
    """Admins: Patientendaten nur bei Testpatienten schreiben (echte Akten nur lesen)."""
    return getattr(user, "rolle", None) in NUR_TESTPATIENTEN_SCHREIBEN


def rechte_stand(user) -> str:
    """Kurzer Fingerabdruck der Rechte eines Benutzers. Steht in jeder API-Antwort (Kopf ``X-EPM-Rechte``);
    ändert er sich (Administration ändert Rechte oder Rolle), lädt die Oberfläche die Rechte neu und blendet
    nicht mehr erlaubte Aktionen aus – ohne neue Anmeldung."""
    import hashlib

    teile = sorted(rechte_fuer(user)) + [f"nur_test={schreibt_nur_testpatienten(user)}",
                                         f"ist_test={getattr(user, 'ist_test', False)}"]
    return hashlib.sha256("|".join(teile).encode()).hexdigest()[:12]
