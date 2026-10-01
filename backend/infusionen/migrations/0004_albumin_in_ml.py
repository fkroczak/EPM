# Humanalbumin wird wie im Altsystem in ml erfasst (Festlegung 01.10.2026); Umbenennung ohne Datenverlust.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('infusionen', '0003_historicalinfusionsplan_gesamtvolumen_ml_and_more'),
    ]

    operations = [
        migrations.RenameField(model_name='infusionsplan', old_name='albumin_g', new_name='albumin_ml'),
        migrations.RenameField(model_name='historicalinfusionsplan', old_name='albumin_g', new_name='albumin_ml'),
        migrations.AlterField(
            model_name='infusionsplan',
            name='albumin_ml',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=6, null=True, verbose_name='Humanalbumin (ml)'),
        ),
        migrations.AlterField(
            model_name='historicalinfusionsplan',
            name='albumin_ml',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=6, null=True, verbose_name='Humanalbumin (ml)'),
        ),
    ]
