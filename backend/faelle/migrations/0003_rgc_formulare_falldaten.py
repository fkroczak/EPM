"""Formulare 01–12 der RGC mit den Feldern des Behandlungsfalls (26.10.2026, ``faelle.formulare``): unveränderte
mitgelieferte Vorlagen bekommen eine Fassung 2; Fassung 1 bleibt für bereits erzeugte PDFs erhalten."""
from django.db import migrations


def umstellen(apps, schema_editor):
    from faelle.formulare import umstellen as formulare_umstellen

    # wie vorlagen/0012: freigegebene Fassungen schützt ein Trigger – nur für diese Transaktion im Wartungsmodus
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET LOCAL epm.wartung = 'on'")
    formulare_umstellen(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [("faelle", "0002_stammdaten_und_vorlagen"), ("altimport", "0001_initial")]

    operations = [migrations.RunPython(umstellen, migrations.RunPython.noop)]
