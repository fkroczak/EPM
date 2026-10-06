"""Laborbefunde und BIA-Messungen (Wünsche aus der Praxis vom 06.10.2026, F112–F114)."""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import simple_history.models

BEURTEILUNG = ("beurteilung", models.TextField(blank=True, verbose_name="Zusammenfassung / Beurteilung"))

LABORBEFUND_FELDER = [
    ("abgenommen_am", models.DateField(default=django.utils.timezone.localdate, verbose_name="Abnahme am")),
    ("labor", models.CharField(blank=True, help_text="z. B. „Labor Dr. Wagner“ oder die Klinik", max_length=150)),
    BEURTEILUNG,
]

LABORWERT_FELDER = [
    ("freitext_name", models.CharField(blank=True, max_length=150, verbose_name="Parameter (Freitext)")),
    ("wert", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
    ("wert_text", models.CharField(blank=True,
                                   help_text="für Angaben, die keine Zahl sind, z. B. „< 0,1“ oder „negativ“",
                                   max_length=50, verbose_name="Wert (Text)")),
    ("einheit", models.CharField(blank=True, max_length=30)),
    ("referenz_von", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True,
                                         verbose_name="Referenz von")),
    ("referenz_bis", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True,
                                         verbose_name="Referenz bis")),
    ("bemerkung", models.CharField(blank=True, max_length=200)),
    ("reihenfolge", models.PositiveSmallIntegerField(default=0)),
]

BIA_FELDER = [
    ("gemessen_am", models.DateField(default=django.utils.timezone.localdate, verbose_name="Gemessen am")),
    ("gewicht_kg", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True,
                                       verbose_name="Gewicht (kg)")),
    ("bcm_kg", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name="BCM (kg)")),
    ("fettmasse_kg", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True,
                                         verbose_name="Fettmasse (kg)")),
    ("ecw_prozent", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True,
                                        verbose_name="ECW – extrazelluläres Wasser (%)")),
    ("koerperwasser_l", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True,
                                            verbose_name="Körperwasser (l)")),
    ("bmi", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True, verbose_name="BMI")),
    BEURTEILUNG,
]

HISTORIE = [
    ("history_id", models.AutoField(primary_key=True, serialize=False)),
    ("history_date", models.DateTimeField(db_index=True)),
    ("history_change_reason", models.CharField(max_length=100, null=True)),
    ("history_type", models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")], max_length=1)),
]
HISTORIE_OPTIONEN = {"ordering": ("-history_date", "-history_id"), "get_latest_by": ("history_date", "history_id")}
ID_ECHT = ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"))
ID_HIST = ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID"))


def _hist_fk(ziel, **kwargs):
    return models.ForeignKey(blank=True, db_constraint=False, null=True,
                             on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to=ziel, **kwargs)


def _history_user():
    return models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                             to=settings.AUTH_USER_MODEL)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("patienten", "0010_versichertendaten_diagnosen"),
        ("stammdaten", "0012_labor_diagnosen_hinweis"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Laborbefund",
            fields=[ID_ECHT, *LABORBEFUND_FELDER, ("erfasst_am", models.DateTimeField(auto_now_add=True))],
            options={"verbose_name": "Laborbefund", "verbose_name_plural": "Laborbefunde",
                     "ordering": ["-abgenommen_am", "-id"]},
        ),
        migrations.CreateModel(
            name="HistoricalLaborbefund",
            fields=[ID_HIST, *LABORBEFUND_FELDER, ("erfasst_am", models.DateTimeField(blank=True, editable=False)),
                    *HISTORIE],
            options={"verbose_name": "historical Laborbefund", "verbose_name_plural": "historical Laborbefunde",
                     **HISTORIE_OPTIONEN},
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name="Laborwert",
            fields=[ID_ECHT, *LABORWERT_FELDER],
            options={"verbose_name": "Laborwert", "verbose_name_plural": "Laborwerte",
                     "ordering": ["reihenfolge", "id"]},
        ),
        migrations.CreateModel(
            name="HistoricalLaborwert",
            fields=[ID_HIST, *LABORWERT_FELDER, *HISTORIE],
            options={"verbose_name": "historical Laborwert", "verbose_name_plural": "historical Laborwerte",
                     **HISTORIE_OPTIONEN},
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name="BiaMessung",
            fields=[ID_ECHT, *BIA_FELDER, ("erfasst_am", models.DateTimeField(auto_now_add=True))],
            options={"verbose_name": "BIA-Messung", "verbose_name_plural": "BIA-Messungen",
                     "ordering": ["-gemessen_am", "-id"]},
        ),
        migrations.CreateModel(
            name="HistoricalBiaMessung",
            fields=[ID_HIST, *BIA_FELDER, ("erfasst_am", models.DateTimeField(blank=True, editable=False)), *HISTORIE],
            options={"verbose_name": "historical BIA-Messung", "verbose_name_plural": "historical BIA-Messungen",
                     **HISTORIE_OPTIONEN},
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        # --- Fremdschlüssel der echten Tabellen ---
        migrations.AddField(
            model_name="laborbefund", name="patient",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="laborbefunde",
                                    to="patienten.patient"),
        ),
        migrations.AddField(
            model_name="laborbefund", name="dokument",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="+", to="patienten.dokument",
                                    verbose_name="Originalbefund (Dokument der Akte)"),
        ),
        migrations.AddField(
            model_name="laborbefund", name="erfasst_von",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="laborwert", name="befund",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="werte",
                                    to="befunde.laborbefund"),
        ),
        migrations.AddField(
            model_name="laborwert", name="parameter",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="werte", to="stammdaten.laborparameter"),
        ),
        migrations.AddField(
            model_name="biamessung", name="patient",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bia_messungen",
                                    to="patienten.patient"),
        ),
        migrations.AddField(
            model_name="biamessung", name="dokument",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="+", to="patienten.dokument",
                                    verbose_name="Geräteprotokoll (Dokument der Akte)"),
        ),
        migrations.AddField(
            model_name="biamessung", name="gewichtsmessung",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                       related_name="+", to="patienten.gewichtsmessung",
                                       verbose_name="Im Gewichtsverlauf eingetragen als"),
        ),
        migrations.AddField(
            model_name="biamessung", name="erfasst_von",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                    to=settings.AUTH_USER_MODEL),
        ),
        # --- Fremdschlüssel der Historientabellen ---
        migrations.AddField(model_name="historicallaborbefund", name="patient", field=_hist_fk("patienten.patient")),
        migrations.AddField(model_name="historicallaborbefund", name="dokument",
                            field=_hist_fk("patienten.dokument",
                                           verbose_name="Originalbefund (Dokument der Akte)")),
        migrations.AddField(model_name="historicallaborbefund", name="erfasst_von",
                            field=_hist_fk(settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="historicallaborbefund", name="history_user", field=_history_user()),
        migrations.AddField(model_name="historicallaborwert", name="befund", field=_hist_fk("befunde.laborbefund")),
        migrations.AddField(model_name="historicallaborwert", name="parameter",
                            field=_hist_fk("stammdaten.laborparameter")),
        migrations.AddField(model_name="historicallaborwert", name="history_user", field=_history_user()),
        migrations.AddField(model_name="historicalbiamessung", name="patient", field=_hist_fk("patienten.patient")),
        migrations.AddField(model_name="historicalbiamessung", name="dokument",
                            field=_hist_fk("patienten.dokument",
                                           verbose_name="Geräteprotokoll (Dokument der Akte)")),
        migrations.AddField(model_name="historicalbiamessung", name="gewichtsmessung",
                            field=_hist_fk("patienten.gewichtsmessung",
                                           verbose_name="Im Gewichtsverlauf eingetragen als")),
        migrations.AddField(model_name="historicalbiamessung", name="erfasst_von",
                            field=_hist_fk(settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="historicalbiamessung", name="history_user", field=_history_user()),
        # --- Indizes und Regeln ---
        migrations.AddIndex(
            model_name="laborbefund",
            index=models.Index(fields=["patient", "abgenommen_am"], name="laborbefund_patient_datum"),
        ),
        migrations.AddIndex(
            model_name="biamessung",
            index=models.Index(fields=["patient", "gemessen_am"], name="bia_patient_datum"),
        ),
        migrations.AddConstraint(
            model_name="laborwert",
            constraint=models.UniqueConstraint(condition=models.Q(("parameter__isnull", False)),
                                               fields=("befund", "parameter"),
                                               name="laborwert_parameter_je_befund_einmal"),
        ),
        migrations.AddConstraint(
            model_name="laborwert",
            constraint=models.CheckConstraint(
                condition=models.Q(("parameter__isnull", False), models.Q(("freitext_name", ""), _negated=True),
                                   _connector="OR"),
                name="laborwert_hat_bezeichnung"),
        ),
        migrations.AddConstraint(
            model_name="laborwert",
            constraint=models.CheckConstraint(
                condition=models.Q(("wert__isnull", False), models.Q(("wert_text", ""), _negated=True),
                                   _connector="OR"),
                name="laborwert_hat_wert"),
        ),
    ]
