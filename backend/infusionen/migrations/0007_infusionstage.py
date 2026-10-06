"""Infusionstage je Beutelart im Plan (Wunsch 06.10.2026, F110).

Das bisherige Feld „Tage pro Woche“ meint ab jetzt die PE (den Mischbeutel); dazu kommen die Tage mit
Zusatzvolumen („Elektrolytbeutel“) und die infusionsfreien Tage. Bestehende Pläne bleiben unverändert: Die
neuen Felder sind leer, und ein leeres Feld heißt weiterhin „nicht erfasst“."""
from django.db import migrations, models


def _pe():
    return models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="PE (Mischbeutel) pro Woche")


def _zusatz():
    return models.PositiveSmallIntegerField(
        blank=True, null=True, help_text="Tage pro Woche mit Zusatzvolumen („Elektrolytbeutel“)",
        verbose_name="Zusatzvolumen pro Woche")


def _frei():
    return models.PositiveSmallIntegerField(
        blank=True, null=True, help_text="Tage ganz ohne Infusion; „keine“ = 0",
        verbose_name="Infusionsfreie Tage pro Woche")


class Migration(migrations.Migration):
    dependencies = [("infusionen", "0006_herkunft")]

    operations = [
        migrations.AlterField(model_name="infusionsplan", name="tage_pro_woche", field=_pe()),
        migrations.AlterField(model_name="historicalinfusionsplan", name="tage_pro_woche", field=_pe()),
        migrations.AddField(model_name="infusionsplan", name="zusatz_tage_pro_woche", field=_zusatz()),
        migrations.AddField(model_name="historicalinfusionsplan", name="zusatz_tage_pro_woche", field=_zusatz()),
        migrations.AddField(model_name="infusionsplan", name="freie_tage_pro_woche", field=_frei()),
        migrations.AddField(model_name="historicalinfusionsplan", name="freie_tage_pro_woche", field=_frei()),
        migrations.AddConstraint(
            model_name="infusionsplan",
            constraint=models.CheckConstraint(
                condition=models.Q(("zusatz_tage_pro_woche__isnull", True),
                                   ("zusatz_tage_pro_woche__range", (1, 7)), _connector="OR"),
                name="zusatz_tage_pro_woche_bereich",
            ),
        ),
        migrations.AddConstraint(
            model_name="infusionsplan",
            constraint=models.CheckConstraint(
                condition=models.Q(("freie_tage_pro_woche__isnull", True),
                                   ("freie_tage_pro_woche__range", (0, 6)), _connector="OR"),
                name="freie_tage_pro_woche_bereich",
            ),
        ),
    ]
