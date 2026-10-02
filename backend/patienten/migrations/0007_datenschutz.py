"""Datenschutz (Festlegung 02.10.2026): Aufbewahrung und Einschränkung an der Akte, Erklärungen, Anfragen betroffener
Personen, begründete Einsicht, Löschprotokoll."""
import django.db.models.deletion
import django.utils.timezone
import simple_history.models
from django.conf import settings
from django.db import migrations, models

ERKLAERUNG_ARTEN = [('datenschutzinformation', 'Datenschutzinformation'),
                    ('einwilligung', 'Einwilligung in die Datenverarbeitung'),
                    ('schweigepflichtentbindung', 'Schweigepflichtentbindung')]
ANFRAGE_ARTEN = [('auskunft', 'Auskunft / Kopie der Akte'), ('berichtigung', 'Berichtigung'), ('loeschung', 'Löschung'),
                 ('einschraenkung', 'Einschränkung der Verarbeitung'), ('widerruf', 'Widerruf einer Einwilligung'),
                 ('sonstiges', 'Sonstiges')]
ERGEBNISSE = [('erfuellt', 'erfüllt'), ('eingeschraenkt', 'Verarbeitung eingeschränkt statt gelöscht'),
              ('abgelehnt', 'abgelehnt'), ('zurueckgezogen', 'zurückgezogen')]
HISTORIE_ARTEN = [('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')]


def _benutzer(**kwargs):
    return models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+',
                             to=settings.AUTH_USER_MODEL, **kwargs)


def _historisch(ziel, **kwargs):
    return models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING,
                             related_name='+', to=ziel, **kwargs)


def _historie_felder():
    return [
        ('history_id', models.AutoField(primary_key=True, serialize=False)),
        ('history_date', models.DateTimeField(db_index=True)),
        ('history_change_reason', models.CharField(max_length=100, null=True)),
        ('history_type', models.CharField(choices=HISTORIE_ARTEN, max_length=1)),
        ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
    ]


def _historie_optionen(name, mehrzahl):
    return {'verbose_name': f'historical {name}', 'verbose_name_plural': f'historical {mehrzahl}',
            'ordering': ('-history_date', '-history_id'), 'get_latest_by': ('history_date', 'history_id')}


def _akte_felder():
    """Neue Felder der Akte – gleich für Patient und seine Historie (bis auf den Verweis auf den Benutzer)."""
    return [
        ('aufbewahrung_bis', models.DateField(blank=True, null=True, verbose_name='Aufbewahrung verlängert bis')),
        ('aufbewahrung_grund', models.CharField(blank=True, max_length=300, verbose_name='Grund der längeren Aufbewahrung')),
        ('eingeschraenkt_am', models.DateTimeField(blank=True, null=True, verbose_name='Verarbeitung eingeschränkt am')),
        ('einschraenkung_grund', models.CharField(blank=True, max_length=300, verbose_name='Grund der Einschränkung')),
    ]


def _erklaerung_felder():
    return [
        ('art', models.CharField(choices=ERKLAERUNG_ARTEN, max_length=30)),
        ('erteilt_am', models.DateField(verbose_name='erteilt bzw. ausgehändigt am')),
        ('vorlage_version', models.PositiveIntegerField(blank=True, null=True, verbose_name='Stand der Dokumentvorlage bei der Erfassung')),
        ('notiz', models.CharField(blank=True, max_length=300)),
        ('widerrufen_am', models.DateField(blank=True, null=True)),
        ('widerruf_notiz', models.CharField(blank=True, max_length=300)),
    ]


def _anfrage_felder():
    return [
        ('art', models.CharField(choices=ANFRAGE_ARTEN, max_length=20)),
        ('eingegangen_am', models.DateField(default=django.utils.timezone.localdate)),
        ('gestellt_von', models.CharField(blank=True, help_text='z. B. „Patient selbst“, Betreuerin, Erbe', max_length=150, verbose_name='Gestellt von')),
        ('inhalt', models.TextField(blank=True, verbose_name='Inhalt der Anfrage')),
        ('frist_verlaengert', models.BooleanField(default=False)),
        ('verlaengerung_grund', models.CharField(blank=True, max_length=300)),
        ('ergebnis', models.CharField(blank=True, choices=ERGEBNISSE, max_length=20)),
        ('begruendung', models.TextField(blank=True, verbose_name='Begründung / Vermerk')),
        ('mitgeteilt_am', models.DateField(blank=True, null=True, verbose_name='Der Person mitgeteilt am')),
        ('erledigt_am', models.DateTimeField(blank=True, null=True)),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ('patienten', '0006_geloeschte_dokumente_schwaerzen'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------ Akte
        *[migrations.AddField(model_name=modell, name=name, field=feld)
          for modell in ('patient', 'historicalpatient') for name, feld in _akte_felder()],
        migrations.AddField(
            model_name='patient',
            name='eingeschraenkt_von',
            field=_benutzer(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalpatient',
            name='eingeschraenkt_von',
            field=_historisch(settings.AUTH_USER_MODEL),
        ),
        # die bisherige Akte eines umgehängten Dokuments kann später endgültig gelöscht werden
        migrations.AlterField(
            model_name='dokumentvorgang',
            name='von_patient',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='patienten.patient'),
        ),
        # ------------------------------------------------------------------ Erklärungen
        migrations.CreateModel(
            name='Erklaerung',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                *_erklaerung_felder(),
                ('erfasst_am', models.DateTimeField(auto_now_add=True)),
                ('dokument', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='patienten.dokument', verbose_name='Unterschriebenes Blatt (Scan)')),
                ('erfasst_von', _benutzer(null=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='erklaerungen', to='patienten.patient')),
            ],
            options={
                'verbose_name': 'Erklärung',
                'verbose_name_plural': 'Erklärungen',
                'ordering': ['art', '-erteilt_am', '-id'],
            },
        ),
        migrations.CreateModel(
            name='HistoricalErklaerung',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                *_erklaerung_felder(),
                ('erfasst_am', models.DateTimeField(blank=True, editable=False)),
                *_historie_felder(),
                ('dokument', _historisch('patienten.dokument', verbose_name='Unterschriebenes Blatt (Scan)')),
                ('erfasst_von', _historisch(settings.AUTH_USER_MODEL)),
                ('patient', _historisch('patienten.patient')),
            ],
            options=_historie_optionen('Erklärung', 'Erklärungen'),
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        # ------------------------------------------------------------------ Anfragen betroffener Personen
        migrations.CreateModel(
            name='Datenschutzanfrage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                *_anfrage_felder(),
                ('erfasst_am', models.DateTimeField(auto_now_add=True)),
                ('erfasst_von', _benutzer(null=True)),
                ('erledigt_von', _benutzer(blank=True, null=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='datenschutzanfragen', to='patienten.patient')),
            ],
            options={
                'verbose_name': 'Datenschutz-Anfrage',
                'verbose_name_plural': 'Datenschutz-Anfragen',
                'ordering': ['-eingegangen_am', '-id'],
            },
        ),
        migrations.CreateModel(
            name='HistoricalDatenschutzanfrage',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                *_anfrage_felder(),
                ('erfasst_am', models.DateTimeField(blank=True, editable=False)),
                *_historie_felder(),
                ('erfasst_von', _historisch(settings.AUTH_USER_MODEL)),
                ('erledigt_von', _historisch(settings.AUTH_USER_MODEL)),
                ('patient', _historisch('patienten.patient')),
            ],
            options=_historie_optionen('Datenschutz-Anfrage', 'Datenschutz-Anfragen'),
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        # ------------------------------------------------------------------ Einsicht in eingeschränkte Akten
        migrations.CreateModel(
            name='Akteneinsicht',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('grund', models.TextField()),
                ('von', models.DateTimeField(auto_now_add=True)),
                ('bis', models.DateTimeField()),
                ('benutzer', _benutzer()),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='einsichten', to='patienten.patient')),
            ],
            options={
                'verbose_name': 'Akteneinsicht',
                'verbose_name_plural': 'Akteneinsichten',
                'ordering': ['-von'],
                'indexes': [models.Index(fields=['benutzer', 'bis'], name='akteneinsicht_benutzer_bis')],
            },
        ),
        # ------------------------------------------------------------------ Löschprotokoll (ohne Namen)
        migrations.CreateModel(
            name='Loeschprotokoll',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('akte_id', models.PositiveBigIntegerField(db_index=True, verbose_name='Interne Kennung der Akte')),
                ('nummer', models.PositiveIntegerField(db_index=True, verbose_name='Patientennummer')),
                ('ist_test', models.BooleanField(default=False)),
                ('angelegt_am', models.DateTimeField(verbose_name='Akte angelegt am')),
                ('abgeschlossen_am', models.DateField(blank=True, null=True)),
                ('abschluss_anlass', models.CharField(blank=True, max_length=30)),
                ('aufbewahrung_bis', models.DateField(blank=True, null=True)),
                ('rechtsgrund', models.CharField(choices=[('frist', 'Aufbewahrungsfrist abgelaufen'), ('antrag', 'Antrag der betroffenen Person')], max_length=20)),
                ('grund', models.TextField()),
                ('umfang', models.JSONField(blank=True, default=dict)),
                ('geloescht_am', models.DateTimeField(default=django.utils.timezone.now)),
                ('geloescht_von', _benutzer(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Löschprotokoll',
                'verbose_name_plural': 'Löschprotokoll',
                'ordering': ['-geloescht_am', '-id'],
            },
        ),
    ]
