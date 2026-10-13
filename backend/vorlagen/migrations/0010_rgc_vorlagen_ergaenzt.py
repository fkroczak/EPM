"""Weitere Word-Vorlagen der Regeneration Clinic (01–05 Patientenerklärungen, 11 Anlage K, 12 Anwaltsvollmacht) als
eigene Schreiben der Firma RGC. ``rgc.anlegen`` legt nur an, was noch fehlt (Kennung ``mitgeliefert``)."""
from django.db import migrations


def anlegen(apps, schema_editor):
    from vorlagen.rgc import anlegen as rgc_anlegen

    rgc_anlegen(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("vorlagen", "0009_medikationsplan_quer"),
    ]

    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
