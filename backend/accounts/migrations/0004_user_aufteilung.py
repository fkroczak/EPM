"""Spaltenteiler je Seite und Fensterstufe, je Person gespeichert (S17)."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_gruppenrecht_historicalgruppenrecht")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="aufteilung",
            field=models.JSONField(blank=True, default=dict, verbose_name="Aufteilung der Seiten"),
        ),
    ]
