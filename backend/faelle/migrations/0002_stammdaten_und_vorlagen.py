"""Dokumentenautomation der RGC (26.10.2026): Kostenträgertypen mit Standardpaket, Kooperationspartner,
Unterschriftsberechtigte, Dokumenttyp „Rechnung“ und die mitgelieferten Vorlagen (Fall-Dokumente je Sprache,
Zusatzbögen zu Vorlage 07). Legt nur Fehlendes an; danach wird alles in der Oberfläche gepflegt."""
from django.db import migrations

PARTNER = ["Eibach", "ARS", "WC4", "AIWA"]
UNTERZEICHNER = [("Dr. Markus Gottwald", "Chefarzt"), ("Prof. Dr. Markus Masin", "Director")]


def anlegen(apps, schema_editor):
    from faelle.pakete import STANDARD
    from faelle.startvorlagen import anlegen as vorlagen_anlegen

    vorlagen_anlegen(apps, schema_editor)
    Kostentraegertyp = apps.get_model("faelle", "Kostentraegertyp")
    for i, (kuerzel, name, land, paket) in enumerate(STANDARD):
        Kostentraegertyp.objects.get_or_create(kuerzel=kuerzel, defaults={
            "name": name, "land": land, "paket": paket, "reihenfolge": (i + 1) * 10})
    Kooperationspartner = apps.get_model("faelle", "Kooperationspartner")
    for name in PARTNER:
        Kooperationspartner.objects.get_or_create(name=name)
    Unterzeichner = apps.get_model("faelle", "Unterzeichner")
    for i, (name, funktion) in enumerate(UNTERZEICHNER):
        Unterzeichner.objects.get_or_create(name=name, defaults={"funktion": funktion, "reihenfolge": (i + 1) * 10})
    Auswahlwert = apps.get_model("stammdaten", "Auswahlwert")
    Auswahlwert.objects.get_or_create(liste="dokumenttyp", wert="Rechnung", defaults={"reihenfolge": 240})


class Migration(migrations.Migration):
    dependencies = [
        ("faelle", "0001_initial"),
        ("vorlagen", "0014_vor_dem_import_fassung_1"),
        ("stammdaten", "0026_berichtart_konsultationsbericht"),
    ]

    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
