"""Wünsche aus der Praxis vom 06.10.2026: Versichertendaten in den Stammdaten (F118) und die Diagnoseliste
der Akte mit ICD-Code und Zusatzkennzeichen (F117).

Das bisherige Feld „krankenkasse“ behält seinen Spaltennamen und heißt nur noch „Versicherung“ – es geht
also nichts verloren und nichts muss umgezogen werden."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import simple_history.models

VERSICHERUNGSARTEN = [
    ("gkv", "GKV (gesetzlich)"),
    ("pkv", "PKV (privat)"),
    ("selbstzahler", "Selbstzahler"),
    ("sonstige", "Sonstige"),
    ("", "nicht erfasst"),
]
KENNZEICHEN = [
    ("G", "G – gesichert"),
    ("V", "V – Verdacht auf"),
    ("Z", "Z – Zustand nach"),
    ("A", "A – Ausschluss von"),
]


def _art():
    return models.CharField(blank=True, choices=VERSICHERUNGSARTEN, default="", max_length=20,
                            verbose_name="Versicherungsart")


def _nummer():
    return models.CharField(blank=True, max_length=50, verbose_name="Versichertennummer")


def _kasse():
    return models.CharField(blank=True, max_length=100, verbose_name="Versicherung")


class Migration(migrations.Migration):
    dependencies = [
        ("patienten", "0009_kein_plan"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name="patient", name="versicherungsart", field=_art()),
        migrations.AddField(model_name="historicalpatient", name="versicherungsart", field=_art()),
        migrations.AddField(model_name="patient", name="versichertennummer", field=_nummer()),
        migrations.AddField(model_name="historicalpatient", name="versichertennummer", field=_nummer()),
        migrations.AlterField(model_name="patient", name="krankenkasse", field=_kasse()),
        migrations.AlterField(model_name="historicalpatient", name="krankenkasse", field=_kasse()),
        migrations.CreateModel(
            name="Diagnose",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bezeichnung", models.CharField(max_length=200)),
                ("icd_code", models.CharField(help_text="z. B. K91.2", max_length=10, verbose_name="ICD-Code")),
                ("kennzeichen", models.CharField(choices=KENNZEICHEN, default="G", max_length=1,
                                                 verbose_name="Zusatzkennzeichen")),
                ("seit", models.DateField(blank=True, null=True, verbose_name="besteht seit")),
                ("notiz", models.CharField(blank=True, max_length=300)),
                ("reihenfolge", models.PositiveSmallIntegerField(default=100)),
                ("aktiv", models.BooleanField(default=True)),
                ("beendet_am", models.DateField(blank=True, null=True)),
                ("angelegt_am", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Diagnose",
                "verbose_name_plural": "Diagnosen",
                "ordering": ["-aktiv", "reihenfolge", "bezeichnung", "id"],
            },
        ),
        migrations.CreateModel(
            name="HistoricalDiagnose",
            fields=[
                ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID")),
                ("bezeichnung", models.CharField(max_length=200)),
                ("icd_code", models.CharField(help_text="z. B. K91.2", max_length=10, verbose_name="ICD-Code")),
                ("kennzeichen", models.CharField(choices=KENNZEICHEN, default="G", max_length=1,
                                                 verbose_name="Zusatzkennzeichen")),
                ("seit", models.DateField(blank=True, null=True, verbose_name="besteht seit")),
                ("notiz", models.CharField(blank=True, max_length=300)),
                ("reihenfolge", models.PositiveSmallIntegerField(default=100)),
                ("aktiv", models.BooleanField(default=True)),
                ("beendet_am", models.DateField(blank=True, null=True)),
                ("angelegt_am", models.DateTimeField(blank=True, editable=False)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                                                  max_length=1)),
                ("angelegt_von", models.ForeignKey(blank=True, db_constraint=False, null=True,
                                                   on_delete=django.db.models.deletion.DO_NOTHING,
                                                   related_name="+", to=settings.AUTH_USER_MODEL)),
                ("history_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                   related_name="+", to=settings.AUTH_USER_MODEL)),
                ("patient", models.ForeignKey(blank=True, db_constraint=False, null=True,
                                              on_delete=django.db.models.deletion.DO_NOTHING,
                                              related_name="+", to="patienten.patient")),
            ],
            options={
                "verbose_name": "historical Diagnose",
                "verbose_name_plural": "historical Diagnosen",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.AddField(
            model_name="diagnose",
            name="angelegt_von",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="diagnose",
            name="patient",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="diagnosen",
                                    to="patienten.patient"),
        ),
        migrations.AddIndex(
            model_name="diagnose",
            index=models.Index(fields=["patient", "aktiv"], name="diagnose_patient_aktiv"),
        ),
    ]
