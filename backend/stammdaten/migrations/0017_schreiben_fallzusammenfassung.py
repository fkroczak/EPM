"""Vorlagen von Alice Hessel (09.10.2026): Dokumenttyp „Schreiben“ für abgelegte Schreiben aus der Akte (F172) und
Berichtsart „Fallzusammenfassung“ mit einheitlicher Gliederung (F175)."""
from django.db import migrations


def vorwaerts(apps, schema_editor):
    Auswahlwert = apps.get_model("stammdaten", "Auswahlwert")
    Auswahlwert.objects.get_or_create(liste="dokumenttyp", wert="Schreiben", defaults={"reihenfolge": 230})
    Auswahlwert.objects.get_or_create(liste="berichtart", wert="Fallzusammenfassung", defaults={"reihenfolge": 5})


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0016_scans_einstellungen")]

    operations = [migrations.RunPython(vorwaerts, migrations.RunPython.noop)]
