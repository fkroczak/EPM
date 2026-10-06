"""Grenzwerte für Befunde (Festlegung 07.10.2026, F120): Ein Laborbefund und eine BIA-Messung gelten nach
zwölf Monaten als alt; beides unter Vorlagen › Grenzwerte einstellbar."""
from django.db import migrations, models


def _monate(bezeichnung):
    return models.PositiveSmallIntegerField(default=12, verbose_name=bezeichnung)


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0013_praeparate_und_kataloge")]

    operations = [
        migrations.AddField(model_name="einstellungen", name="labor_alter_warnung_monate",
                            field=_monate("Laborbefund gilt als alt nach")),
        migrations.AddField(model_name="historicaleinstellungen", name="labor_alter_warnung_monate",
                            field=_monate("Laborbefund gilt als alt nach")),
        migrations.AddField(model_name="einstellungen", name="bia_alter_warnung_monate",
                            field=_monate("BIA-Messung gilt als alt nach")),
        migrations.AddField(model_name="historicaleinstellungen", name="bia_alter_warnung_monate",
                            field=_monate("BIA-Messung gilt als alt nach")),
    ]
