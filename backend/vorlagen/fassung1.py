"""Vor dem Import nur Fassung 1 (14.10.2026): Solange keine Altdaten übernommen wurden, hat jede Dokumentvorlage nur
die Fassung 1. Freigeben, „Als eigene Vorlage kopieren“ und Updates ersetzen sie dann, statt Fassung 2, 3 … anzulegen;
erst ab dem ersten erfolgreichen Import zählen die Fassungen weiter (jede gespeicherte PDF verweist auf ihre Fassung).

Bis dahin gibt es nur Testdaten; ihre PDFs verweisen danach auf Fassung 1. Nach „Datenbank leeren“ (``system.leeren``)
gilt wieder „vor dem Import“.

Die Funktionen nehmen ``apps`` aus einer Migration entgegen, damit Update-Migrationen sie ebenfalls verwenden können;
sie müssen im Wartungsmodus laufen (veröffentlichte Fassungen und Akteneinträge sind per Trigger geschützt)."""
from django.apps import apps as django_apps

# Einträge, die die Fassung ihrer Vorlage festhalten (``vorlage_version``)
VERWEISE = (("infusionen", "Infusionsplan"), ("berichte", "Bericht"), ("korrespondenz", "Schreiben"),
            ("patienten", "Erklaerung"))


def import_durchgefuehrt(apps=None) -> bool:
    """Wurden schon Altdaten übernommen (erfolgreicher Lauf „Import“, auch wenn er später zurückgenommen wurde)?"""
    Importlauf = (apps or django_apps).get_model("altimport", "Importlauf")
    return Importlauf.objects.filter(art="import", erfolgreich=True).exists()


def auf_fassung_1(apps=None) -> int:
    """Alle Vorlagen auf Fassung 1 zurückführen: abgelöste Fassungen entfernen, die aktive wird Fassung 1, Verweise in
    den Akten zeigen auf Fassung 1. Entwürfe bleiben. → Zahl der entfernten Fassungen"""
    apps = apps or django_apps
    Vorlage = apps.get_model("vorlagen", "Dokumentvorlage")
    entfernt = Vorlage.objects.filter(status="abgeloest").count()
    Vorlage.objects.filter(status="abgeloest").delete()
    Vorlage.objects.filter(status="aktiv").exclude(version=1).update(version=1)
    for app, modell in VERWEISE:
        apps.get_model(app, modell).objects.filter(vorlage_version__gt=1).update(vorlage_version=1)
    return entfernt
