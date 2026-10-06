"""Wünsche aus der Praxis vom 06.10.2026: Hinweis am Präparat (F111), Katalog der Laborparameter (F112),
Liste der Diagnosen mit ICD-Code (F117) und die Auswahlliste „Berichtsarten“ (F115)."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import simple_history.models

LISTEN = [
    ("katheter", "Katheter"),
    ("dokumenttyp", "Dokumenttyp"),
    ("kontaktart", "Kontaktart"),
    ("terminort", "Terminort"),
    ("beziehung", "Beziehung (Bezugsperson)"),
    ("berichtart", "Berichtsart"),
]

GRUPPEN = [
    ("transaminasen", "Transaminasen"),
    ("niere", "Nierenwerte"),
    ("eisen", "Eisenhaushalt"),
    ("eiweiss_fett", "Eiweiß- und Fettstoffwechsel"),
    ("elektrolyte", "Elektrolyte"),
    ("spurenelemente", "Spurenelemente"),
    ("haematologie", "Hämatologie"),
    ("vitamine", "Vitamine"),
    ("knochen", "Knochenstoffwechsel"),
    ("pankreas", "Pankreasenzyme"),
    ("diabetes", "Blutzucker / Diabetes"),
    ("schilddruese", "Schilddrüse"),
    ("tumormarker", "Tumormarker"),
    ("genetik", "Genetische Parameter"),
    ("sonstiges", "Weitere Parameter"),
]

HINWEIS = models.CharField(blank=True, help_text="z. B. „reines Taurolidin 2 %“", max_length=200)


class Migration(migrations.Migration):
    dependencies = [
        ("stammdaten", "0011_musterdaten_import"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

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
        migrations.AddField(model_name="praeparat", name="hinweis", field=HINWEIS),
        migrations.AddField(model_name="historicalpraeparat", name="hinweis", field=HINWEIS),
        migrations.CreateModel(
            name="Laborparameter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gruppe", models.CharField(choices=GRUPPEN, max_length=30)),
                ("name", models.CharField(max_length=150)),
                ("kurzname", models.CharField(blank=True, help_text="für enge Spalten, z. B. „GPT“", max_length=60)),
                ("einheit", models.CharField(blank=True, help_text="z. B. mg/dl, µg/l, U/l", max_length=30)),
                ("referenz_von", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True,
                                                     verbose_name="Referenz von")),
                ("referenz_bis", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True,
                                                     verbose_name="Referenz bis")),
                ("reihenfolge", models.PositiveSmallIntegerField(default=100)),
                ("aktiv", models.BooleanField(default=True,
                                              help_text="Ausgeblendete Parameter erscheinen nicht in neuen Befunden")),
            ],
            options={
                "verbose_name": "Laborparameter",
                "verbose_name_plural": "Laborparameter",
                "ordering": ["gruppe", "reihenfolge", "name"],
            },
        ),
        migrations.CreateModel(
            name="HistoricalLaborparameter",
            fields=[
                ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID")),
                ("gruppe", models.CharField(choices=GRUPPEN, max_length=30)),
                ("name", models.CharField(max_length=150)),
                ("kurzname", models.CharField(blank=True, help_text="für enge Spalten, z. B. „GPT“", max_length=60)),
                ("einheit", models.CharField(blank=True, help_text="z. B. mg/dl, µg/l, U/l", max_length=30)),
                ("referenz_von", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True,
                                                     verbose_name="Referenz von")),
                ("referenz_bis", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True,
                                                     verbose_name="Referenz bis")),
                ("reihenfolge", models.PositiveSmallIntegerField(default=100)),
                ("aktiv", models.BooleanField(default=True,
                                              help_text="Ausgeblendete Parameter erscheinen nicht in neuen Befunden")),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                                                  max_length=1)),
                ("history_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                   related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "historical Laborparameter",
                "verbose_name_plural": "historical Laborparameter",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name="Diagnosevorlage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("icd_code", models.CharField(db_index=True, help_text="z. B. K91.2", max_length=10,
                                              verbose_name="ICD-Code")),
                ("bezeichnung", models.CharField(max_length=200)),
                ("aktiv", models.BooleanField(default=True)),
                ("angelegt_am", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Diagnose (Liste)",
                "verbose_name_plural": "Diagnosen (Liste)",
                "ordering": ["bezeichnung", "icd_code"],
            },
        ),
        migrations.CreateModel(
            name="HistoricalDiagnosevorlage",
            fields=[
                ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID")),
                ("icd_code", models.CharField(db_index=True, help_text="z. B. K91.2", max_length=10,
                                              verbose_name="ICD-Code")),
                ("bezeichnung", models.CharField(max_length=200)),
                ("aktiv", models.BooleanField(default=True)),
                ("angelegt_am", models.DateTimeField(blank=True, editable=False)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                                                  max_length=1)),
                ("history_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                   related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "historical Diagnose (Liste)",
                "verbose_name_plural": "historical Diagnosen (Liste)",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.AddConstraint(
            model_name="laborparameter",
            constraint=models.UniqueConstraint(fields=("gruppe", "name"), name="laborparameter_eindeutig"),
        ),
        migrations.AddConstraint(
            model_name="laborparameter",
            constraint=models.CheckConstraint(
                condition=models.Q(("referenz_von__isnull", True), ("referenz_bis__isnull", True),
                                   ("referenz_von__lte", models.F("referenz_bis")), _connector="OR"),
                name="laborparameter_referenz_reihenfolge",
            ),
        ),
        migrations.AddConstraint(
            model_name="diagnosevorlage",
            constraint=models.UniqueConstraint(fields=("icd_code", "bezeichnung"), name="diagnosevorlage_eindeutig"),
        ),
    ]
