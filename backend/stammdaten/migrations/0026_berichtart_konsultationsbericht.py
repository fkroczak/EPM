"""Diktate (23.10.2026): Berichtsart „Konsultationsbericht“ neben „Arztbrief“."""
from django.db import migrations


def vorwaerts(apps, schema_editor):
    Auswahlwert = apps.get_model("stammdaten", "Auswahlwert")
    Auswahlwert.objects.get_or_create(liste="berichtart", wert="Konsultationsbericht", defaults={"reihenfolge": 15})


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0025_absender_vorstand_bank")]

    operations = [migrations.RunPython(vorwaerts, migrations.RunPython.noop)]
