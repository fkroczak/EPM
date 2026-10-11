"""
Rechte je Gruppe (Rolle). Die Administration legt sie in der Oberfläche fest (Benutzer › Rechte).

Festlegungen vom 01.10.2026:
- Mediziner sind dem Admin gleichgestellt, ausgenommen Benutzerverwaltung und sehr spezifische
  Eingriffe (abgeschlossene Akten wieder öffnen, Sicherungen, Testdaten).
- Akten abschließen: Mitarbeiter, Mediziner und Admin. Vorlagen pflegen: auch Mitarbeiter und Mediziner.
- Admins dürfen alles, Patientendaten schreiben sie aber nur bei Testpatienten; echte Akten sind für
  sie nur lesbar (Wieder öffnen, Benutzer, Sicherungen bleiben).
- Systemverwaltung (Server und EPM, Festlegung 02.10.2026): Standard nur Admin; für eine Vertretung je Gruppe
  freischaltbar. Endgültig löschen (Dokumente, Akten): Mediziner und Admin, Admins auch bei echten Akten.
- Altdaten übernehmen (Import, F65): nur Admin; anderen Rollen nicht erteilbar. Der Import ist eine bewusste
  Ausnahme von „Admins schreiben Patientendaten nur bei Testpatienten“ – er legt die übernommenen Akten an.
- Festlegungen 02.10.2026 (Fehlerliste): Admins dürfen auch bei echten Akten Dokumente einem anderen Patienten zuordnen
  und Akten abschließen (wie schon endgültig löschen). Neue Rolle „Keine Berechtigung“: keinerlei Rechte, nicht
  einstellbar; Konten ohne Login haben immer diese Rolle.
- Festlegung 03.10.2026 (U22): Rolle „Mitarbeiter (erweitert)“ zwischen Mitarbeiter und Mediziner – Standard wie
  Mitarbeiter und zusätzlich Infusionspläne anlegen; alles je Gruppe umstellbar.
- Festlegung 08.10.2026 (Scans, F160): Menüpunkt „Scans“ mit eigenem Recht – Standard Mitarbeiter, Mitarbeiter
  (erweitert), Mediziner und Admin; Betrachter nicht (nicht zugeordnete Scans enthalten Patientendaten). Zuordnen
  verlangt zusätzlich „Einträge erfassen“ für die Akte (Admins wie überall nur bei Testpatienten).
- Festlegung 03.10.2026: „Testdaten sehen“ (Testpatienten und Testbenutzer) je Gruppe einstellbar – ohne das Recht
  erscheinen sie nirgends. Standard: alle Rollen wie bisher; Admin fest (legt nur Testpatienten an und verlöre sonst
  alles, was er schreiben darf). Testbenutzer sehen ihre Testpatienten immer.
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
    ("dokumente_umhaengen", "Dokumente einem anderen Patienten zuordnen",
     "bei falsch zugeordneten Dokumenten; mit Grund, im Verlauf beider Akten und im Audit-Log"),
    ("dokumente_loeschen", "Dokumente endgültig löschen",
     "nur Mediziner und Admin; mit Passwort, Code aus der Authenticator-App und Bestätigungscode; im Audit-Log"),
    ("scans_bearbeiten", "Scans: hochladen, erkennen, zuordnen",
     "Menüpunkt „Scans“: Dokumente hochladen, aufbereiten, Text erkennen lassen und kopieren, Scans verlängern und "
     "löschen; einem Patienten zuordnen und Werte übernehmen nur zusätzlich mit „Kontakte, Gewichte, Termine, "
     "Dokumente erfassen“"),
    ("plaene_anlegen", "Infusionspläne anlegen", "Entwürfe anlegen, bearbeiten und verwerfen"),
    ("plaene_freigeben", "Infusionspläne freigeben", ""),
    ("plaene_abschliessen", "Infusionspläne nach Freigabe abschließen",
     "wenn der Mediziner außerhalb von EPM freigegeben hat (z. B. per E-Mail): mit Datum, Weg und Nachweis"),
    ("berichte_freigeben", "Berichte freigeben",
     "einen Bericht aus der Akte abschließen; dabei entsteht die PDF und der Bericht wird unveränderlich "
     "(Standard: Mediziner, je Gruppe umstellbar – U54)"),
    ("akten_abschliessen", "Akten abschließen", ""),
    ("akten_wieder_oeffnen", "Abgeschlossene Akten wieder öffnen", ""),
    ("datenschutz_bearbeiten", "Datenschutz: Erklärungen und Anfragen erfassen",
     "Datenschutzinformation, Einwilligung und Schweigepflichtentbindung nachhalten; Anfragen erfassen; "
     "Kopie der Akte erstellen"),
    ("datenschutz_entscheiden", "Datenschutz: Anfragen entscheiden, Verarbeitung einschränken",
     "Anfragen mit Ergebnis erledigen; Akten einschränken, Einsicht nehmen; Aufbewahrung verlängern"),
    ("akten_loeschen", "Akten endgültig löschen",
     "nur Mediziner und Admin; nach Ablauf der Aufbewahrungsfrist oder auf Antrag; mit Passwort, Code aus der "
     "Authenticator-App und Bestätigungscode; im Löschprotokoll und im Audit-Log"),
    ("versorger_pflegen", "Versorger, Ansprechpartner und Ärzte pflegen",
     "gemeinsame Listen: Versorger mit Ansprechpartnern, Ärzte mit Kontaktdaten"),
    ("vorlagen_pflegen", "Vorlagen pflegen", "Briefkopf und Logo, Auswahllisten, Präparate, Grenzwerte"),
    ("audit_lesen", "Audit-Log lesen", ""),
    ("benutzer_verwalten", "Benutzer und Rechte verwalten",
     "Benutzer anlegen, sperren, Einmal-Passwort, 2FA zurücksetzen, Rechte der Gruppen"),
    ("backup_verwalten", "Sicherungen verwalten", "Sicherung starten, wiederherstellen"),
    ("testdaten_sehen", "Testdaten sehen (Testpatienten und Testbenutzer)",
     "ohne dieses Recht erscheinen Testpatienten (Nr. ab 9001) und Testbenutzer nirgends – nicht in Listen, Suche, "
     "Kalender, Startseite oder Auswahlfeldern; Testbenutzer selbst sehen ihre Testpatienten immer"),
    ("testdaten_zuruecksetzen", "Testdaten zurücksetzen", ""),
    ("system_verwalten", "Systemverwaltung (Server und EPM)",
     "Auslastung, Ubuntu-Updates, Neustart, Wartung von Datenbank und Dateien, Hinweise an alle Benutzer; Standard nur "
     "Admin, für eine Vertretung (z. B. Urlaub) je Gruppe freischaltbar"),
    ("altdaten_importieren", "Altdaten übernehmen (Import)",
     "Dump des Altsystems laden, Zuordnungen pflegen, Probelauf, Import, zurücknehmen, abschließen – nur Admin"),
]
CODES = [code for code, _, _ in RECHTE]
NAMEN = {code: name for code, name, _ in RECHTE}

_ALLE = set(CODES)
_ADMIN_SPEZIAL = {"benutzer_verwalten", "akten_wieder_oeffnen", "backup_verwalten", "testdaten_zuruecksetzen",
                  "system_verwalten", "altdaten_importieren"}

# Rechte, die Patientendaten verändern (Einträge, Stammdaten, Pläne, Abschluss)
PATIENTENDATEN_SCHREIBEN = {"eintraege_erfassen", "akten_bearbeiten", "plaene_anlegen", "plaene_freigeben",
                            "plaene_abschliessen", "akten_abschliessen", "dokumente_umhaengen",
                            "datenschutz_bearbeiten", "datenschutz_entscheiden", "berichte_freigeben"}

# Endgültiges Löschen (F73, F80) dürfen Admins auch bei echten Akten (Festlegung 02.10.2026); die übrigen Prüfungen
# (Frist bzw. Antrag, Kennwort + 2FA + Bestätigungscode, Audit-Log, Löschprotokoll) gelten unverändert
LOESCHEN = {"dokumente_loeschen", "akten_loeschen"}
# Was Admins auch bei echten Akten dürfen (Ausnahmen von „Admins schreiben Patientendaten nur bei Testpatienten“):
# endgültig löschen, Dokumente einem anderen Patienten zuordnen, Akten abschließen (Festlegungen 02.10.2026)
AUCH_BEI_ECHTEN_AKTEN = LOESCHEN | {"dokumente_umhaengen", "akten_abschliessen"}

# Rechte, die nur bestimmte Rollen haben können; anderen Rollen nicht erteilbar (Festlegungen 02.10.2026:
# endgültig löschen nur Mediziner und Admin – Admins auch bei echten Akten, Ausnahme von „Admins schreiben
# Patientendaten nur bei Testpatienten“). Die Systemverwaltung ist Standard nur für Admin, für eine Urlaubsvertretung
# aber jeder Gruppe erteilbar (Benutzer › Rechte). Altdaten übernehmen (F65): nur Admin.
NUR_ROLLEN = {"dokumente_loeschen": {Rolle.MEDIZINER, Rolle.ADMIN}, "akten_loeschen": {Rolle.MEDIZINER, Rolle.ADMIN},
              "altdaten_importieren": {Rolle.ADMIN}}

# Rollen ohne jedes Recht – in der Matrix nicht einstellbar
OHNE_RECHTE = {Rolle.KEINE}

STANDARD = {
    Rolle.KEINE: set(),
    Rolle.BETRACHTER: {"akten_lesen", "testdaten_sehen"},
    # Datenschutz: Mitarbeiter erfassen Erklärungen und Anfragen und schließen freigegebene Pläne ab;
    # entscheiden, einschränken und löschen bleibt beim Mediziner
    Rolle.MITARBEITER: {"akten_lesen", "eintraege_erfassen", "akten_bearbeiten", "akten_abschliessen",
                        "versorger_pflegen", "vorlagen_pflegen", "datenschutz_bearbeiten", "plaene_abschliessen",
                        "testdaten_sehen", "scans_bearbeiten"},
    Rolle.MITARBEITER_PLUS: {"akten_lesen", "eintraege_erfassen", "akten_bearbeiten", "akten_abschliessen",
                                  "versorger_pflegen", "vorlagen_pflegen", "datenschutz_bearbeiten",
                                  "plaene_abschliessen", "plaene_anlegen", "testdaten_sehen", "scans_bearbeiten"},
    Rolle.MEDIZINER: _ALLE - _ADMIN_SPEZIAL,
    Rolle.ADMIN: _ALLE - {c for c, rollen in NUR_ROLLEN.items() if Rolle.ADMIN not in rollen},
}

# Diese Rollen schreiben Patientendaten nur bei Testpatienten (fest, unabhängig von der Matrix)
NUR_TESTPATIENTEN_SCHREIBEN = {Rolle.ADMIN}

# Diese Rechte kann niemand entziehen (sonst sperrt sich die Administration aus)
FEST = {(Rolle.ADMIN, "benutzer_verwalten"), (Rolle.ADMIN, "akten_lesen"), (Rolle.ADMIN, "testdaten_sehen")}

# Testbenutzer arbeiten nur mit Testpatienten; alles, was darüber hinaus wirkt, bleibt verwehrt
NUR_ECHTE_BENUTZER = {"versorger_pflegen", "vorlagen_pflegen", "audit_lesen", "benutzer_verwalten",
                      "backup_verwalten", "testdaten_zuruecksetzen", "akten_wieder_oeffnen", "system_verwalten",
                      "altdaten_importieren"}


def matrix() -> dict:
    """{rolle: {recht: bool}} aus Standard und gespeicherten Abweichungen."""
    from .models import Gruppenrecht

    ergebnis = {rolle: {code: code in STANDARD[rolle] for code in CODES} for rolle in Rolle.values}
    for rolle, recht, erlaubt in Gruppenrecht.objects.values_list("rolle", "recht", "erlaubt"):
        if rolle in ergebnis and recht in NAMEN:
            ergebnis[rolle][recht] = erlaubt
    for rolle, recht in FEST:
        ergebnis[rolle][recht] = True
    for rolle in OHNE_RECHTE:
        ergebnis[rolle] = {code: False for code in CODES}
    for recht, rollen in NUR_ROLLEN.items():
        for rolle in ergebnis:
            if rolle not in rollen:
                ergebnis[rolle][recht] = False
    return ergebnis


def rechte_fuer(user) -> frozenset:
    """Rechte eines Benutzers (eine kleine Abfrage; bewusst ohne Zwischenspeicher, damit
    Änderungen der Administration sofort gelten)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()
    from epm.firma import wirksame_rolle

    rolle = wirksame_rolle(user)  # Rolle in der aktiven Firma (11.10.2026)
    if rolle in OHNE_RECHTE or getattr(user, "nur_historisch", False):
        return frozenset()
    werte = matrix().get(rolle, {})
    rechte = {code for code, erlaubt in werte.items() if erlaubt}
    if getattr(user, "ist_test", False):
        rechte -= NUR_ECHTE_BENUTZER
    # Altdaten-Import nur in der Firma, der die Altdaten gehören (DSKM, Anforderung 11.10.2026)
    firma = getattr(user, "firma", None)
    if firma is not None and not firma.altdaten:
        rechte.discard("altdaten_importieren")
    return frozenset(rechte)


def hat_recht(user, code: str) -> bool:
    return code in rechte_fuer(user)


def sieht_testdaten(user) -> bool:
    """Testpatienten und Testbenutzer sichtbar? Recht „Testdaten sehen“; Testbenutzer sehen ihre Testpatienten immer."""
    return bool(getattr(user, "ist_test", False)) or hat_recht(user, "testdaten_sehen")


def schreibt_nur_testpatienten(user) -> bool:
    """Admins: Patientendaten nur bei Testpatienten schreiben (echte Akten nur lesen)."""
    from epm.firma import wirksame_rolle

    return wirksame_rolle(user) in NUR_TESTPATIENTEN_SCHREIBEN


def rechte_stand(user) -> str:
    """Kurzer Fingerabdruck der Rechte eines Benutzers. Steht in jeder API-Antwort (Kopf ``X-EPM-Rechte``);
    ändert er sich (Administration ändert Rechte oder Rolle), lädt die Oberfläche die Rechte neu und blendet
    nicht mehr erlaubte Aktionen aus – ohne neue Anmeldung."""
    import hashlib

    firma = getattr(user, "firma", None)
    teile = sorted(rechte_fuer(user)) + [f"nur_test={schreibt_nur_testpatienten(user)}",
                                         f"ist_test={getattr(user, 'ist_test', False)}",
                                         f"firma={firma.kuerzel if firma else ''}"]
    return hashlib.sha256("|".join(teile).encode()).hexdigest()[:12]
