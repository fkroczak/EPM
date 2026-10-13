"""Mitgelieferte Vorlagen der Regeneration Clinic als eigene Schreiben der Firma RGC anlegen (13.10.2026)."""
from django.db import migrations


def anlegen(apps, schema_editor):
    from vorlagen.rgc import anlegen as rgc_anlegen

    rgc_anlegen(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("vorlagen", "0006_eigene_schreiben_firma"),
        ("stammdaten", "0023_technik_bis"),
        ("patienten", "0020_firmen_dskm_rg"),  # legt die Firma RGC (Kürzel „rg“) an
    ]

    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
