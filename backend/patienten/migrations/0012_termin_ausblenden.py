"""Termine im Kalender mit „×“ ausblenden (Wunsch 08.10.2026, F142): wie die Hinweise der Akte für 3, 6 oder 12 Monate
oder „nicht mehr nötig“, mit Grund, Person und Zeitpunkt."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def felder(historisch):
    von = (models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING,
                             related_name="+", to=settings.AUTH_USER_MODEL) if historisch else
           models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+",
                             to=settings.AUTH_USER_MODEL))
    return [
        ("ausgeblendet_bis", models.DateField(blank=True, null=True, verbose_name="ausgeblendet bis")),
        ("ausgeblendet_dauerhaft", models.BooleanField(default=False, verbose_name="ausgeblendet (nicht mehr nötig)")),
        ("ausblende_grund", models.CharField(blank=True, max_length=300, verbose_name="Grund des Ausblendens")),
        ("ausgeblendet_am", models.DateTimeField(blank=True, null=True)),
        ("ausgeblendet_von", von),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ("patienten", "0011_hinweisruhe"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name=modell, name=name, field=feld)
        for modell in ("termin", "historicaltermin")
        for name, feld in felder(modell == "historicaltermin")
    ]
