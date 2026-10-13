"""Dokumentvorlagen je Firma (Festlegung „Gemischt“, 11.10.2026): ``firma`` leer = gemeinsame Vorlage, gesetzt = eigene
Vorlage dieser Firma; Entwurf, aktive Fassung und Versionsnummern gelten je (Art, Firma). Seitenformat ``ausrichtung``
(Medikationsplan im Querformat, 13.10.2026; Umstellung der Startvorlage in 0009). Die Vorlagen der Regeneration
Clinic sind eigene Schreiben der Firma RGC (``vorlagen.rgc``)."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stammdaten", "0023_technik_bis"),
        ("vorlagen", "0007_rgc_vorlagen"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="dokumentvorlage",
            name="ein_entwurf_je_art",
        ),
        migrations.RemoveConstraint(
            model_name="dokumentvorlage",
            name="eine_aktive_je_art",
        ),
        migrations.RemoveConstraint(
            model_name="dokumentvorlage",
            name="version_je_art_eindeutig",
        ),
        migrations.AddField(
            model_name="dokumentvorlage",
            name="ausrichtung",
            field=models.CharField(
                choices=[("hoch", "Hochformat"), ("quer", "Querformat")],
                default="hoch",
                max_length=4,
            ),
        ),
        migrations.AddField(
            model_name="dokumentvorlage",
            name="firma",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dokumentvorlagen",
                to="stammdaten.firma",
            ),
        ),
        migrations.AddField(
            model_name="historicaldokumentvorlage",
            name="ausrichtung",
            field=models.CharField(
                choices=[("hoch", "Hochformat"), ("quer", "Querformat")],
                default="hoch",
                max_length=4,
            ),
        ),
        migrations.AddField(
            model_name="historicaldokumentvorlage",
            name="firma",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="stammdaten.firma",
            ),
        ),
        migrations.AddConstraint(
            model_name="dokumentvorlage",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "entwurf")),
                fields=("art", "firma"),
                name="ein_entwurf_je_art",
                nulls_distinct=False,
            ),
        ),
        migrations.AddConstraint(
            model_name="dokumentvorlage",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "aktiv")),
                fields=("art", "firma"),
                name="eine_aktive_je_art",
                nulls_distinct=False,
            ),
        ),
        migrations.AddConstraint(
            model_name="dokumentvorlage",
            constraint=models.UniqueConstraint(
                fields=("art", "firma", "version"),
                name="version_je_art_eindeutig",
                nulls_distinct=False,
            ),
        ),
    ]
