# Korrespondenz der Akte (14.10.2026): Entwurf → freigegeben → versendet, mit Änderungsverlauf

import django.db.models.deletion
import simple_history.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("patienten", "0021_medikamente"),
        ("stammdaten", "0024_icd_katalog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HistoricalSchreiben",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("entwurf", "Entwurf"),
                            ("freigegeben", "freigegeben"),
                            ("versendet", "versendet"),
                        ],
                        default="entwurf",
                        max_length=15,
                    ),
                ),
                (
                    "vorlage",
                    models.CharField(max_length=60, verbose_name="Dokumentvorlage"),
                ),
                (
                    "vorlage_name",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="Name der Vorlage"
                    ),
                ),
                ("vorlage_version", models.PositiveIntegerField(blank=True, null=True)),
                ("titel", models.CharField(max_length=200, verbose_name="Betreff")),
                (
                    "empfaenger",
                    models.CharField(
                        blank=True, max_length=300, verbose_name="Empfänger"
                    ),
                ),
                ("text", models.TextField(blank=True, verbose_name="Freitext")),
                ("optionen", models.JSONField(blank=True, default=dict)),
                ("bloecke", models.JSONField(blank=True, default=list)),
                (
                    "kopie_von",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="kopiert aus Schreiben Nr."
                    ),
                ),
                ("erstellt_am", models.DateTimeField(blank=True, editable=False)),
                ("freigegeben_am", models.DateTimeField(blank=True, null=True)),
                ("pdf_sha256", models.CharField(blank=True, max_length=64)),
                ("versendet_am", models.DateField(blank=True, null=True)),
                (
                    "versandweg",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("post", "Post"),
                            ("email", "E-Mail"),
                            ("fax", "Fax"),
                            ("persoenlich", "persönlich übergeben"),
                            ("portal", "Portal"),
                            ("sonstiges", "anderer Weg"),
                        ],
                        max_length=20,
                    ),
                ),
                ("versand_notiz", models.CharField(blank=True, max_length=300)),
                ("versand_erfasst_am", models.DateTimeField(blank=True, null=True)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "dokument",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="patienten.dokument",
                        verbose_name="Freigegebene PDF",
                    ),
                ),
                (
                    "erstellt_von",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "firma",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="stammdaten.firma",
                        verbose_name="erfasst in Firma",
                    ),
                ),
                (
                    "freigegeben_von",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="patienten.patient",
                    ),
                ),
                (
                    "termin",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="patienten.termin",
                    ),
                ),
                (
                    "versendet_von",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Versand vermerkt von",
                    ),
                ),
            ],
            options={
                "verbose_name": "historical Schreiben",
                "verbose_name_plural": "historical Schreiben",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name="Schreiben",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("entwurf", "Entwurf"),
                            ("freigegeben", "freigegeben"),
                            ("versendet", "versendet"),
                        ],
                        default="entwurf",
                        max_length=15,
                    ),
                ),
                (
                    "vorlage",
                    models.CharField(max_length=60, verbose_name="Dokumentvorlage"),
                ),
                (
                    "vorlage_name",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="Name der Vorlage"
                    ),
                ),
                ("vorlage_version", models.PositiveIntegerField(blank=True, null=True)),
                ("titel", models.CharField(max_length=200, verbose_name="Betreff")),
                (
                    "empfaenger",
                    models.CharField(
                        blank=True, max_length=300, verbose_name="Empfänger"
                    ),
                ),
                ("text", models.TextField(blank=True, verbose_name="Freitext")),
                ("optionen", models.JSONField(blank=True, default=dict)),
                ("bloecke", models.JSONField(blank=True, default=list)),
                (
                    "kopie_von",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="kopiert aus Schreiben Nr."
                    ),
                ),
                ("erstellt_am", models.DateTimeField(auto_now_add=True)),
                ("geaendert_am", models.DateTimeField(auto_now=True)),
                ("freigegeben_am", models.DateTimeField(blank=True, null=True)),
                ("pdf_sha256", models.CharField(blank=True, max_length=64)),
                ("versendet_am", models.DateField(blank=True, null=True)),
                (
                    "versandweg",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("post", "Post"),
                            ("email", "E-Mail"),
                            ("fax", "Fax"),
                            ("persoenlich", "persönlich übergeben"),
                            ("portal", "Portal"),
                            ("sonstiges", "anderer Weg"),
                        ],
                        max_length=20,
                    ),
                ),
                ("versand_notiz", models.CharField(blank=True, max_length=300)),
                ("versand_erfasst_am", models.DateTimeField(blank=True, null=True)),
                (
                    "dokument",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="patienten.dokument",
                        verbose_name="Freigegebene PDF",
                    ),
                ),
                (
                    "erstellt_von",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "firma",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="stammdaten.firma",
                        verbose_name="erfasst in Firma",
                    ),
                ),
                (
                    "freigegeben_von",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="korrespondenz",
                        to="patienten.patient",
                    ),
                ),
                (
                    "termin",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="+",
                        to="patienten.termin",
                    ),
                ),
                (
                    "versendet_von",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Versand vermerkt von",
                    ),
                ),
            ],
            options={
                "verbose_name": "Schreiben",
                "verbose_name_plural": "Schreiben",
                "ordering": ["-erstellt_am", "-id"],
                "indexes": [
                    models.Index(
                        fields=["patient", "status"], name="schreiben_patient_status"
                    )
                ],
            },
        ),
    ]
