"""Kontakt fällig in zwei Stufen (Festlegung 01.10.2026, S04): „bald fällig“ ab 4 Monaten, „überfällig“ ab 6 Monaten.

Der bisherige eine Grenzwert „Kontakt überfällig“ (Standard 4) wird zu „bald fällig“; „überfällig“ kommt neu dazu, mit
6 Monaten. Hatte die Administration einen eigenen Wert eingetragen, bleibt er als „bald fällig“ erhalten und
„überfällig“ liegt 2 Monate später, mindestens bei 6 (derselbe Abstand wie 4 → 6). Die Umstellung steht mit Grund in
der Historie der Einstellungen.
"""
from django.db import migrations, models
from django.utils import timezone

# history_change_reason fasst höchstens 100 Zeichen
GRUND = "Kontakt fällig in 2 Stufen: bald fällig = bisheriger Wert, überfällig neu (Festlegung 01.10.2026)"


def umstellen(apps, schema_editor):
    Einstellungen = apps.get_model("stammdaten", "Einstellungen")
    Historie = apps.get_model("stammdaten", "HistoricalEinstellungen")
    e = Einstellungen.objects.filter(pk=1).first()
    if e is None:
        return  # neue Datenbank: es gelten die Standardwerte 4 und 6
    bisher = e.kontakt_ueberfaellig_monate
    e.kontakt_bald_monate = bisher
    e.kontakt_ueberfaellig_monate = max(6, bisher + 2)
    e.save(update_fields=["kontakt_bald_monate", "kontakt_ueberfaellig_monate"])
    werte = {f.attname: getattr(e, f.attname) for f in Einstellungen._meta.concrete_fields}
    Historie.objects.create(**werte, history_date=timezone.now(), history_type="~", history_change_reason=GRUND[:100])


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0008_datenschutz")]

    operations = [
        migrations.AddField(
            model_name="einstellungen",
            name="kontakt_bald_monate",
            field=models.PositiveSmallIntegerField(default=4, verbose_name="Kontakt bald fällig"),
        ),
        migrations.AddField(
            model_name="historicaleinstellungen",
            name="kontakt_bald_monate",
            field=models.PositiveSmallIntegerField(default=4, verbose_name="Kontakt bald fällig"),
        ),
        # erst umstellen (der bisherige Wert steht noch im alten Feld), dann den Standard des Feldes ändern
        migrations.RunPython(umstellen, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="einstellungen",
            name="kontakt_ueberfaellig_monate",
            field=models.PositiveSmallIntegerField(default=6, verbose_name="Kontakt überfällig"),
        ),
        migrations.AlterField(
            model_name="historicaleinstellungen",
            name="kontakt_ueberfaellig_monate",
            field=models.PositiveSmallIntegerField(default=6, verbose_name="Kontakt überfällig"),
        ),
    ]
