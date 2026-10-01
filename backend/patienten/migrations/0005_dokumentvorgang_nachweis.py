"""Endgültig gelöschte Dokumente: Nachweis mit Prüfsumme und Pfad, Person darf bei nachgeholter Löschung fehlen
(Art. 17 DSGVO, U15, Festlegung 02.10.2026)."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patienten', '0004_dokumentvorgang'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='dokumentvorgang',
            name='datei',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='dokumentvorgang',
            name='sha256',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='dokumentvorgang',
            name='person',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
    ]
