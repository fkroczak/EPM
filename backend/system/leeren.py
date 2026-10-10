"""
Datenbank leeren (Festlegung 03.10.2026, U27): vor dem Go-live alles aus der Testphase entfernen, damit die Altdaten in
ein leeres System übernommen werden können.

Weg: alle Akten (echte und Testpatienten) mit Einträgen, Plänen, Dokumenten und Historie, die Dateien, das
Löschprotokoll und die Löschliste, Merklisten, alle Scans mit ihren Dateien (auch nicht zugeordnete – sie enthalten
Patientendaten), was die Texterkennung gelernt hat, die gemerkten Infoblätter an die Praxis, der Stand des Altdaten-Imports, Versorger mit Ansprechpartnern, Ärzte,
alle Benutzer außer den ausgewählten (das eigene Konto bleibt immer) und das Audit-Log.
Bleiben: Präparate, Auswahllisten, Grenzwerte und Einstellungen, Briefkopf und Logo, Dokumentvorlagen, Rechte der
Gruppen, Hilfe-Ergänzungen, Sicherungen. Musterdaten (Testpatienten) werden danach nicht mehr automatisch angelegt.

Ausgeführt vom Systemagenten nach einer Sicherung (``manage.py epm_datenbank_leeren``); die Oberfläche fordert vorher
Passwort, Code der Zwei-Faktor-Anmeldung, einen abgetippten Bestätigungscode und eine ausdrückliche Rückfrage.
"""
import shutil
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import models, transaction

from audit.schutz import wartungsmodus


def umfang() -> dict:
    """Was beim Leeren entfernt würde – für die Rückfrage in der Oberfläche."""
    from altimport.models import Importlauf
    from patienten.models import Dokument, Kontakt, Loeschprotokoll, Patient
    from scans.models import Scan
    from stammdaten.models import Arzt, Versorger

    return {
        "patienten": Patient.objects.filter(ist_test=False).count(),
        "testpatienten": Patient.objects.filter(ist_test=True).count(),
        "kontakte": Kontakt.objects.count(),
        "dokumente": Dokument.objects.count(),
        "loeschprotokoll": Loeschprotokoll.objects.count(),
        "versorger": Versorger.objects.count(),
        "aerzte": Arzt.objects.count(),
        "importlaeufe": Importlauf.objects.count(),
        "scans": Scan.objects.count(),
    }


def _benutzer_verweise_umhaengen(weg_ids: list[int], ersatz) -> None:
    """Verweise auf zu entfernende Konten in allen übrigen Tabellen (Vorlagen, Präparate, Einstellungen, Aufträge,
    Historie …) leeren bzw. – wo ein Verweis Pflicht ist – auf das ausführende Konto setzen."""
    user_modell = apps.get_model(settings.AUTH_USER_MODEL)
    for modell in apps.get_models():
        if modell is user_modell:
            continue
        for feld in modell._meta.get_fields():
            if not isinstance(feld, models.ForeignKey) or feld.related_model is not user_modell:
                continue
            if feld.remote_field.on_delete is models.CASCADE:
                continue  # gehört zum Konto (Authenticator, Anmeldungen …) und geht mit ihm
            qs = modell._base_manager.filter(**{f"{feld.name}_id__in": weg_ids})
            if feld.null:
                qs.update(**{feld.name: None})
            else:
                qs.update(**{feld.name: ersatz})


def datenbank_leeren(ausfuehrend, behalten: list[int]) -> dict:
    """Leeren wie oben beschrieben. ``ausfuehrend``: das Konto, das den Auftrag gegeben hat (bleibt immer).
    Rückgabe: Anzahlen für das Audit-Log."""
    from accounts.models import User
    from accounts.sitzungen import alle_sitzungen_beenden
    from altimport.models import Alttabelle, Importlauf, Importobjekt, Importstand
    from audit.models import SystemEreignis
    from patienten.datenschutz import akten_entfernen
    from patienten.models import Akteneinsicht, Ankuendigung, Loeschprotokoll, Merkeintrag, Patient
    from scans import lernen
    from scans.models import Scan
    from stammdaten.models import Ansprechpartner, Arzt, Einstellungen, Versorger

    zahlen = umfang()
    bleiben = set(behalten or []) | {ausfuehrend.pk}
    weg = list(User.objects.exclude(pk__in=bleiben))
    with transaction.atomic(), wartungsmodus():
        akten_entfernen(list(Patient.objects.values_list("id", flat=True)))
        for modell in (Merkeintrag, Akteneinsicht, Ankuendigung):
            modell.objects.all().delete()
        Loeschprotokoll.objects.all().delete()
        # Scans enthalten Patientendaten, auch solange sie keiner Akte zugeordnet sind; das Gelernte beginnt neu
        Scan.objects.all().delete()
        lernen.leeren()
        if hasattr(Loeschprotokoll, "history"):
            Loeschprotokoll.history.all().delete()
        # Altdaten-Import: Stand, Dump und Läufe – die Übernahme beginnt danach von vorn
        Importobjekt.objects.all().delete()
        Importlauf.objects.all().delete()
        Alttabelle.objects.all().delete()
        Importstand.objects.all().delete()
        # gemeinsame Listen der Testphase
        for modell in (Ansprechpartner, Versorger, Arzt):
            modell.objects.all().delete()
            if hasattr(modell, "history"):
                modell.history.all().delete()
        # Benutzer: alle Anmeldungen außer denen des ausführenden Kontos beenden (der Hinweis vorher kündigt das an),
        # Verweise umhängen, nicht ausgewählte Konten entfernen
        weg_ids = [u.pk for u in weg]
        for u in User.objects.exclude(pk=ausfuehrend.pk):
            alle_sitzungen_beenden(u)
        _benutzer_verweise_umhaengen(weg_ids, ausfuehrend)
        User.objects.filter(pk__in=weg_ids).delete()
        # Audit-Log beginnt neu (Festlegung 03.10.2026); der Eintrag „Datenbank geleert“ folgt
        SystemEreignis.objects.all().delete()
        e = Einstellungen.aktuell()
        e.musterdaten_automatisch = False
        e._history_user = ausfuehrend
        e.save()
    # Dateien: Dokumente aller Akten, Löschliste
    basis = Path(settings.EPM_DOKUMENTE)
    if basis.is_dir():
        for eintrag in basis.iterdir():
            if eintrag.is_dir() and not eintrag.is_symlink():
                shutil.rmtree(eintrag, ignore_errors=True)
            elif eintrag.is_file():
                eintrag.unlink(missing_ok=True)
    # Dateien der Scans (der Stand des OCR-Dienstes in „.dienst“ bleibt)
    scans = Path(settings.EPM_SCANS)
    if scans.is_dir():
        for eintrag in scans.iterdir():
            if eintrag.name.startswith("."):
                continue
            if eintrag.is_dir() and not eintrag.is_symlink():
                shutil.rmtree(eintrag, ignore_errors=True)
            elif eintrag.is_file() or eintrag.is_symlink():
                eintrag.unlink(missing_ok=True)
    liste = Path(settings.EPM_LOESCHLISTE)
    if liste.exists():
        liste.write_text("", encoding="utf-8")
    zahlen["konten"] = len(weg)
    zahlen["benutzer_behalten"] = sorted(bleiben)
    return zahlen
