"""Katheter-Historie (F192, 15.10.2026): Katheter je Akte mit Komplikationen, beide mit Historie (simple_history).

Von Hand geschrieben (Django war in der Entwicklungsumgebung nicht installierbar); Aufbau wie die von Django erzeugten
Migrationen ``0014_therapieschritte`` und ``0021_medikamente``: Historien-Modelle mit ``db_constraint=False`` und
``DO_NOTHING``, ``history_user`` mit ``SET_NULL``. Die Auswahllisten „Katheter: Entfernungsgrund“ und „Katheter:
Komplikation“ legt ``stammdaten/0026_katheter_listen`` an (Abhängigkeit unten). Die Schutz-Trigger für die neuen
Historientabellen setzt ``epm_trigger`` nach ``migrate`` von selbst (alle Tabellen mit „_historical“).
"""
import django.db.models.deletion
import simple_history.models
from django.conf import settings
from django.db import migrations, models

HISTORY_TYPE = models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")], max_length=1)
HISTORY_OPTIONEN = {"ordering": ("-history_date", "-history_id"), "get_latest_by": ("history_date", "history_id")}


def _hist_fk(ziel, **kwargs):
    """Fremdschlüssel im Historien-Modell: ohne Datenbank-Constraint, nichts kaskadiert."""
    return models.ForeignKey(blank=True, db_constraint=False, null=True,
                             on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to=ziel, **kwargs)


def _history_felder():
    return [
        ("history_id", models.AutoField(primary_key=True, serialize=False)),
        ("history_date", models.DateTimeField(db_index=True)),
        ("history_change_reason", models.CharField(max_length=100, null=True)),
        ("history_type", HISTORY_TYPE),
        ("history_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                                           to=settings.AUTH_USER_MODEL)),
    ]


def _katheter_felder():
    return [
        ("lage", models.CharField(blank=True, help_text="z. B. „V. subclavia rechts“", max_length=200,
                                  verbose_name="Lage/Zugang")),
        ("anlage_am", models.DateField(verbose_name="Anlagedatum")),
        ("entfernt_am", models.DateField(blank=True, null=True, verbose_name="Entfernt am")),
        ("notiz", models.CharField(blank=True, max_length=500)),
        ("aktiv", models.BooleanField(default=True)),
    ]


def _komplikation_felder():
    return [
        ("datum", models.DateField()),
        ("notiz", models.CharField(blank=True, max_length=500)),
        ("aktiv", models.BooleanField(default=True)),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ("patienten", "0021_medikamente"),
        ("stammdaten", "0026_katheter_listen"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------ Katheter
        migrations.CreateModel(
            name="Katheter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                *_katheter_felder(),
                ("angelegt_am", models.DateTimeField(auto_now_add=True)),
                ("angelegt_von", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                                   related_name="+", to=settings.AUTH_USER_MODEL)),
                ("firma", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                            related_name="+", to="stammdaten.firma", verbose_name="erfasst in Firma")),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="katheter_eintraege", to="patienten.patient")),
                ("typ", models.ForeignKey(limit_choices_to={"liste": "katheter"},
                                          on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                          to="stammdaten.auswahlwert", verbose_name="Katheter-Typ")),
                ("entfernungsgrund", models.ForeignKey(blank=True, limit_choices_to={"liste": "katheter_entfernung"},
                                                       null=True, on_delete=django.db.models.deletion.PROTECT,
                                                       related_name="+", to="stammdaten.auswahlwert",
                                                       verbose_name="Entfernungsgrund")),
            ],
            options={
                "verbose_name": "Katheter",
                "verbose_name_plural": "Katheter-Historie",
                "ordering": ["-anlage_am", "-id"],
                "indexes": [models.Index(fields=["patient", "anlage_am"], name="katheter_patient_anlage")],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("entfernt_am__isnull", True),
                                           ("entfernt_am__gte", models.F("anlage_am")), _connector="OR"),
                        name="katheter_entfernt_nach_anlage",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="HistoricalKatheter",
            fields=[
                ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID")),
                *_katheter_felder(),
                ("angelegt_am", models.DateTimeField(blank=True, editable=False)),
                *_history_felder(),
                ("angelegt_von", _hist_fk(settings.AUTH_USER_MODEL)),
                ("firma", _hist_fk("stammdaten.firma", verbose_name="erfasst in Firma")),
                ("patient", _hist_fk("patienten.patient")),
                ("typ", _hist_fk("stammdaten.auswahlwert", limit_choices_to={"liste": "katheter"},
                                 verbose_name="Katheter-Typ")),
                ("entfernungsgrund", _hist_fk("stammdaten.auswahlwert", limit_choices_to={"liste": "katheter_entfernung"},
                                              verbose_name="Entfernungsgrund")),
            ],
            options={"verbose_name": "historical Katheter", "verbose_name_plural": "historical Katheter-Historie",
                     **HISTORY_OPTIONEN},
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        # ------------------------------------------------------------------ Komplikationen
        migrations.CreateModel(
            name="KatheterKomplikation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                *_komplikation_felder(),
                ("angelegt_am", models.DateTimeField(auto_now_add=True)),
                ("angelegt_von", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                                   related_name="+", to=settings.AUTH_USER_MODEL)),
                ("firma", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                            related_name="+", to="stammdaten.firma", verbose_name="erfasst in Firma")),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="katheter_komplikationen", to="patienten.patient")),
                ("katheter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                               related_name="komplikationen", to="patienten.katheter")),
                ("art", models.ForeignKey(limit_choices_to={"liste": "katheter_komplikation"},
                                          on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                          to="stammdaten.auswahlwert", verbose_name="Art der Komplikation")),
            ],
            options={
                "verbose_name": "Katheter-Komplikation",
                "verbose_name_plural": "Katheter-Komplikationen",
                "ordering": ["-datum", "-id"],
                "indexes": [models.Index(fields=["patient", "datum"], name="katheterkompl_patient_datum")],
            },
        ),
        migrations.CreateModel(
            name="HistoricalKatheterKomplikation",
            fields=[
                ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID")),
                *_komplikation_felder(),
                ("angelegt_am", models.DateTimeField(blank=True, editable=False)),
                *_history_felder(),
                ("angelegt_von", _hist_fk(settings.AUTH_USER_MODEL)),
                ("firma", _hist_fk("stammdaten.firma", verbose_name="erfasst in Firma")),
                ("patient", _hist_fk("patienten.patient")),
                ("katheter", _hist_fk("patienten.katheter")),
                ("art", _hist_fk("stammdaten.auswahlwert", limit_choices_to={"liste": "katheter_komplikation"},
                                 verbose_name="Art der Komplikation")),
            ],
            options={"verbose_name": "historical Katheter-Komplikation",
                     "verbose_name_plural": "historical Katheter-Komplikationen", **HISTORY_OPTIONEN},
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
    ]
