"""Kurzname der Regeneration Clinic: „RGC“ statt „RG“ (Wunsch 11.10.2026). Das Kürzel ``rg`` bleibt."""
from django.db import migrations


def umbenennen(apps, schema_editor):
    apps.get_model("stammdaten", "Firma").objects.filter(kuerzel="rg", kurzname="RG").update(kurzname="RGC")


def zurueck(apps, schema_editor):
    apps.get_model("stammdaten", "Firma").objects.filter(kuerzel="rg", kurzname="RGC").update(kurzname="RG")


class Migration(migrations.Migration):
    dependencies = [
        ("stammdaten", "0021_firma_alter_absenderangaben_art_and_more"),
        ("patienten", "0020_firmen_dskm_rg"),
    ]

    operations = [migrations.RunPython(umbenennen, zurueck)]
