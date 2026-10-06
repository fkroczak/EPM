"""Berichte aus der Akte (Wunsch 06.10.2026, F115): Entwurf → freigegeben, danach unveränderlich."""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import simple_history.models

FELDER = [
    ("status", models.CharField(choices=[("entwurf", "Entwurf"), ("freigegeben", "freigegeben")],
                                default="entwurf", max_length=15)),
    ("titel", models.CharField(max_length=200)),
    ("datum", models.DateField(default=django.utils.timezone.localdate, verbose_name="Datum des Berichts")),
    ("empfaenger", models.CharField(blank=True, help_text="z. B. „Hausarzt Dr. Hausmann“", max_length=200)),
    ("inhalt", models.TextField(blank=True)),
    ("freigegeben_am", models.DateTimeField(blank=True, null=True)),
    ("pdf_sha256", models.CharField(blank=True, max_length=64)),
    ("vorlage_version", models.PositiveIntegerField(blank=True, null=True)),
]


def _hist_fk(ziel, **kwargs):
    return models.ForeignKey(blank=True, db_constraint=False, null=True,
                             on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to=ziel, **kwargs)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("patienten", "0010_versichertendaten_diagnosen"),
        ("stammdaten", "0012_labor_diagnosen_hinweis"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Bericht",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                *FELDER,
                ("erstellt_am", models.DateTimeField(auto_now_add=True)),
                ("geaendert_am", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Bericht", "verbose_name_plural": "Berichte", "ordering": ["-datum", "-id"]},
        ),
        migrations.CreateModel(
            name="HistoricalBericht",
            fields=[
                ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID")),
                *FELDER,
                ("erstellt_am", models.DateTimeField(blank=True, editable=False)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                                                  max_length=1)),
            ],
            options={"verbose_name": "historical Bericht", "verbose_name_plural": "historical Berichte",
                     "ordering": ("-history_date", "-history_id"),
                     "get_latest_by": ("history_date", "history_id")},
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.AddField(
            model_name="bericht", name="patient",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="berichte",
                                    to="patienten.patient"),
        ),
        migrations.AddField(
            model_name="bericht", name="art",
            field=models.ForeignKey(blank=True, limit_choices_to={"liste": "berichtart"}, null=True,
                                    on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                    to="stammdaten.auswahlwert", verbose_name="Berichtsart"),
        ),
        migrations.AddField(
            model_name="bericht", name="erstellt_von",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="bericht", name="freigegeben_von",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="+", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="bericht", name="dokument",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="+", to="patienten.dokument", verbose_name="Freigegebene PDF"),
        ),
        migrations.AddField(model_name="historicalbericht", name="patient", field=_hist_fk("patienten.patient")),
        migrations.AddField(model_name="historicalbericht", name="art",
                            field=_hist_fk("stammdaten.auswahlwert", limit_choices_to={"liste": "berichtart"},
                                           verbose_name="Berichtsart")),
        migrations.AddField(model_name="historicalbericht", name="erstellt_von",
                            field=_hist_fk(settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="historicalbericht", name="freigegeben_von",
                            field=_hist_fk(settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="historicalbericht", name="dokument",
                            field=_hist_fk("patienten.dokument", verbose_name="Freigegebene PDF")),
        migrations.AddField(
            model_name="historicalbericht", name="history_user",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(
            model_name="bericht",
            index=models.Index(fields=["patient", "datum"], name="bericht_patient_datum"),
        ),
    ]
