"""Freigabe auf Anordnung (Festlegung 02.10.2026): Der Mediziner gibt außerhalb von EPM frei (z. B. per E-Mail), ein
Mitarbeiter schließt den Plan ab. Festgehalten werden Weg, Datum, Nachweis und wer abgeschlossen hat."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

WEGE = [('system', 'im System'), ('email', 'per E-Mail'), ('telefon', 'telefonisch'), ('persoenlich', 'persönlich'),
        ('schriftlich', 'schriftlich')]


def _weg():
    return models.CharField(blank=True, choices=WEGE, max_length=20, verbose_name='Weg der Freigabe')


def _datum():
    return models.DateField(blank=True, null=True, verbose_name='Datum der Freigabe durch den Mediziner')


class Migration(migrations.Migration):

    dependencies = [
        ('infusionen', '0004_albumin_in_ml'),
        ('patienten', '0007_datenschutz'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name='infusionsplan', name='freigabe_weg', field=_weg()),
        migrations.AddField(model_name='historicalinfusionsplan', name='freigabe_weg', field=_weg()),
        migrations.AddField(model_name='infusionsplan', name='freigabe_datum', field=_datum()),
        migrations.AddField(model_name='historicalinfusionsplan', name='freigabe_datum', field=_datum()),
        migrations.AddField(
            model_name='infusionsplan',
            name='abgeschlossen_von',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Im System abgeschlossen von'),
        ),
        migrations.AddField(
            model_name='historicalinfusionsplan',
            name='abgeschlossen_von',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Im System abgeschlossen von'),
        ),
        migrations.AddField(
            model_name='infusionsplan',
            name='freigabe_nachweis',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='patienten.dokument', verbose_name='Nachweis der Freigabe (z. B. die E-Mail)'),
        ),
        migrations.AddField(
            model_name='historicalinfusionsplan',
            name='freigabe_nachweis',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='patienten.dokument', verbose_name='Nachweis der Freigabe (z. B. die E-Mail)'),
        ),
    ]
