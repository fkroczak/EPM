"""Hinweise mit „×“ wegklicken (Wunsch 07.10.2026, F119).

Beim Wegklicken wird entschieden, wie lange Ruhe sein soll: eine Frist in Monaten – danach erscheint der
Hinweis von allein wieder – oder „nicht mehr nötig“ (``bis`` leer), bis jemand es zurücknimmt. Gelöscht wird
nichts; das Aufheben trägt ``aufgehoben_am`` ein."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import simple_history.models

ARTEN = [
    ("gewicht", "Gewichtsverlust"),
    ("plan", "Infusionsplan älter als …"),
    ("ohne_plan", "Kein Infusionsplan"),
    ("versorger", "Versorger nicht erfasst"),
    ("kontakt", "Kontakt fällig"),
    ("labor", "Laborbefund älter als …"),
    ("bia", "BIA-Messung älter als …"),
]

FELDER = [
    ("art", models.CharField(choices=ARTEN, max_length=20)),
    ("bis", models.DateField(blank=True, help_text="leer = nicht mehr nötig, bis aufgehoben", null=True,
                             verbose_name="Ruhe bis")),
    ("grund", models.CharField(blank=True, max_length=300)),
    ("aufgehoben_am", models.DateTimeField(blank=True, null=True)),
]


def _hist_fk(ziel):
    return models.ForeignKey(blank=True, db_constraint=False, null=True,
                             on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to=ziel)


class Migration(migrations.Migration):
    dependencies = [
        ("patienten", "0010_versichertendaten_diagnosen"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Hinweisruhe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                *FELDER,
                ("gesetzt_am", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Stummgeschalteter Hinweis",
                "verbose_name_plural": "Stummgeschaltete Hinweise",
                "ordering": ["-gesetzt_am", "-id"],
            },
        ),
        migrations.CreateModel(
            name="HistoricalHinweisruhe",
            fields=[
                ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID")),
                *FELDER,
                ("gesetzt_am", models.DateTimeField(blank=True, editable=False)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                                                  max_length=1)),
            ],
            options={
                "verbose_name": "historical Stummgeschalteter Hinweis",
                "verbose_name_plural": "historical Stummgeschaltete Hinweise",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.AddField(
            model_name="hinweisruhe", name="patient",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hinweisruhe",
                                    to="patienten.patient"),
        ),
        migrations.AddField(
            model_name="hinweisruhe", name="gesetzt_von",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="hinweisruhe", name="aufgehoben_von",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="+", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(model_name="historicalhinweisruhe", name="patient", field=_hist_fk("patienten.patient")),
        migrations.AddField(model_name="historicalhinweisruhe", name="gesetzt_von",
                            field=_hist_fk(settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="historicalhinweisruhe", name="aufgehoben_von",
                            field=_hist_fk(settings.AUTH_USER_MODEL)),
        migrations.AddField(
            model_name="historicalhinweisruhe", name="history_user",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(
            model_name="hinweisruhe",
            index=models.Index(fields=["patient", "art"], name="hinweisruhe_patient_art"),
        ),
        migrations.AddConstraint(
            model_name="hinweisruhe",
            constraint=models.UniqueConstraint(condition=models.Q(("aufgehoben_am__isnull", True)),
                                               fields=("patient", "art"), name="hinweisruhe_je_art_einmal"),
        ),
    ]
