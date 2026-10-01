"""Dokumente umhängen und endgültig löschen (Festlegung 02.10.2026)."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patienten', '0003_bezugsperson_historicalbezugsperson_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DokumentVorgang',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('art', models.CharField(choices=[('umgehaengt', 'einem anderen Patienten zugeordnet'), ('geloescht', 'endgültig gelöscht')], max_length=20)),
                ('dokument_id', models.PositiveIntegerField(db_index=True)),
                ('grund', models.TextField()),
                ('zeitpunkt', models.DateTimeField(auto_now_add=True)),
                ('nach_patient', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='patienten.patient')),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('von_patient', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='patienten.patient')),
            ],
            options={
                'verbose_name': 'Dokument-Vorgang',
                'verbose_name_plural': 'Dokument-Vorgänge',
                'ordering': ['-zeitpunkt'],
            },
        ),
    ]
