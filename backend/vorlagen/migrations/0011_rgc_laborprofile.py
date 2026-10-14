"""Laborprofile Malabsorption der Regeneration Clinic (MAL-01 bis MAL-06 und Übersicht mit Regelwerk, 14.10.2026) als
eigene Schreiben der Firma RGC. ``rgc.anlegen`` legt nur an, was noch fehlt (Kennung ``mitgeliefert``)."""
from django.db import migrations


def anlegen(apps, schema_editor):
    from vorlagen.rgc import anlegen as rgc_anlegen

    rgc_anlegen(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("vorlagen", "0010_rgc_vorlagen_ergaenzt"),
    ]

    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
