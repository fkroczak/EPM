"""Herkunft eines Infusionsplans: in EPM angelegt oder aus dem Altsystem übernommen (F65). Übernommene Pläne haben
keinen Freigabevermerk und keine gespeicherte PDF – beides gab es im Altsystem nicht."""
from django.db import migrations, models


def _herkunft():
    return models.CharField(choices=[('epm', 'In EPM angelegt'), ('altsystem', 'Aus dem Altsystem übernommen')],
                            default='epm', editable=False, max_length=20)


class Migration(migrations.Migration):

    dependencies = [
        ('infusionen', '0005_freigabe_auf_anordnung'),
    ]

    operations = [
        migrations.AddField(model_name='infusionsplan', name='herkunft', field=_herkunft()),
        migrations.AddField(model_name='historicalinfusionsplan', name='herkunft', field=_herkunft()),
    ]
