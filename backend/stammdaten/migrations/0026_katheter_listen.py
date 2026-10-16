"""Katheter-Historie (F192, 15.10.2026): zwei neue Auswahllisten „Katheter: Entfernungsgrund“ und „Katheter:
Komplikation“ mit Grundwerten. Pflegbar unter Administration › Auswahllisten; gelöscht wird nichts.

Wiederholbar und schonend: Es wird nur angelegt, was fehlt (gleiche Werte wie ``patienten.testdaten.AUSWAHLWERTE``).
Von Hand geschrieben (Django war in der Entwicklungsumgebung nicht installierbar) – im Aufbau wie
``0012_labor_diagnosen_hinweis`` (Auswahl der Listen) und ``0017_schreiben_fallzusammenfassung`` (Grundwerte).
"""
from django.db import migrations, models

LISTEN = [
    ("katheter", "Katheter"),
    ("dokumenttyp", "Dokumenttyp"),
    ("kontaktart", "Kontaktart"),
    ("terminort", "Terminort"),
    ("beziehung", "Beziehung (Bezugsperson)"),
    ("berichtart", "Berichtsart"),
    ("katheter_entfernung", "Katheter: Entfernungsgrund"),
    ("katheter_komplikation", "Katheter: Komplikation"),
]

ENTFERNUNGSGRUENDE = ["Wechsel", "Infektion", "Okklusion", "Dislokation", "Therapie beendet", "Sonstiges"]
KOMPLIKATIONEN = ["Katheterinfektion", "Okklusion", "Thrombose", "Dislokation", "Leckage", "Sonstiges"]


def vorwaerts(apps, schema_editor):
    Auswahlwert = apps.get_model("stammdaten", "Auswahlwert")
    for liste, werte in (("katheter_entfernung", ENTFERNUNGSGRUENDE), ("katheter_komplikation", KOMPLIKATIONEN)):
        for i, wert in enumerate(werte):
            Auswahlwert.objects.get_or_create(liste=liste, wert=wert, defaults={"reihenfolge": (i + 1) * 10})


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0025_absender_vorstand_bank")]

    operations = [
        migrations.AlterField(
            model_name="auswahlwert",
            name="liste",
            field=models.CharField(choices=LISTEN, max_length=30),
        ),
        migrations.AlterField(
            model_name="historicalauswahlwert",
            name="liste",
            field=models.CharField(choices=LISTEN, max_length=30),
        ),
        # rückwärts bleiben die Werte stehen (in EPM wird nichts gelöscht)
        migrations.RunPython(vorwaerts, migrations.RunPython.noop),
    ]
