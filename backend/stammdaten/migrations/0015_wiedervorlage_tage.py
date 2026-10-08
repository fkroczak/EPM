"""Wiedervorlage beim Erfassen eines Kontakts (Wunsch 08.10.2026): standardmäßig in 14 Tagen, unter
Vorlagen › Grenzwerte einstellbar."""
from django.db import migrations, models


def _tage():
    return models.PositiveSmallIntegerField(default=14, verbose_name="Wiedervorlage nach")


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0014_befunde_grenzwerte")]

    operations = [
        migrations.AddField(model_name="einstellungen", name="wiedervorlage_tage", field=_tage()),
        migrations.AddField(model_name="historicaleinstellungen", name="wiedervorlage_tage", field=_tage()),
    ]
