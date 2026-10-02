"""Übernahme der Altdaten (F65): Stand, Tabellen des geladenen Dumps, Läufe mit Protokoll, vom Import angelegte Objekte."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _person():
    return models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+',
                             to=settings.AUTH_USER_MODEL)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Alttabelle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('spalten', models.JSONField(default=list)),
                ('typen', models.JSONField(blank=True, default=dict)),
                ('entfernt', models.JSONField(blank=True, default=list)),
                ('zeilen', models.JSONField(default=list)),
            ],
            options={
                'verbose_name': 'Tabelle des Altsystems',
                'verbose_name_plural': 'Tabellen des Altsystems',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Importobjekt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('art', models.CharField(choices=[('patient', 'Patient'), ('benutzer', 'Benutzer'), ('versorger', 'Versorger'), ('ansprechpartner', 'Ansprechpartner'), ('auswahlwert', 'Auswahlwert'), ('praeparat', 'Präparat'), ('datei', 'Datei')], max_length=20)),
                ('objekt_id', models.PositiveBigIntegerField()),
                ('schluessel', models.CharField(max_length=600)),
            ],
            options={
                'verbose_name': 'Vom Import angelegtes Objekt',
                'verbose_name_plural': 'Vom Import angelegte Objekte',
                'indexes': [models.Index(fields=['art', 'objekt_id'], name='importobjekt_art_objekt')],
                'constraints': [models.UniqueConstraint(fields=('art', 'schluessel'), name='importobjekt_eindeutig')],
            },
        ),
        migrations.CreateModel(
            name='Importlauf',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('art', models.CharField(choices=[('probelauf', 'Probelauf'), ('import', 'Import'), ('dokumente', 'Dokumente übernommen'), ('zurueckgenommen', 'Import zurückgenommen'), ('abgeschlossen', 'Übernahme abgeschlossen')], max_length=20)),
                ('begonnen_am', models.DateTimeField(auto_now_add=True)),
                ('beendet_am', models.DateTimeField(blank=True, null=True)),
                ('erfolgreich', models.BooleanField(default=False)),
                ('dump_name', models.CharField(blank=True, max_length=255)),
                ('dump_sha256', models.CharField(blank=True, max_length=64)),
                ('zahlen', models.JSONField(blank=True, default=dict)),
                ('protokoll', models.JSONField(blank=True, default=list)),
                ('fehler', models.TextField(blank=True)),
                ('benutzer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Lauf der Altdaten-Übernahme',
                'verbose_name_plural': 'Läufe der Altdaten-Übernahme',
                'ordering': ['-begonnen_am', '-id'],
            },
        ),
        migrations.CreateModel(
            name='Importstand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('leer', 'kein Dump geladen'), ('geladen', 'Dump geladen'), ('importiert', 'Altdaten übernommen'), ('abgeschlossen', 'Übernahme abgeschlossen')], default='leer', max_length=15)),
                ('dump_name', models.CharField(blank=True, max_length=255)),
                ('dump_sha256', models.CharField(blank=True, max_length=64)),
                ('dump_groesse', models.PositiveBigIntegerField(default=0)),
                ('dump_geladen_am', models.DateTimeField(blank=True, null=True)),
                ('dump_hinweise', models.JSONField(blank=True, default=list)),
                ('zuordnung', models.JSONField(blank=True, default=dict)),
                ('importiert_am', models.DateTimeField(blank=True, null=True)),
                ('abgeschlossen_am', models.DateTimeField(blank=True, null=True)),
                ('abgeschlossen_von', _person()),
                ('dump_geladen_von', _person()),
                ('importiert_von', _person()),
            ],
            options={
                'verbose_name': 'Stand der Altdaten-Übernahme',
                'verbose_name_plural': 'Stand der Altdaten-Übernahme',
            },
        ),
    ]
