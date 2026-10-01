"""„Kein Kontakt seit …“ nach 4 statt 12 Monaten (Festlegung 01.10.2026: die meisten Patienten kommen quartalsweise).

Nur ein noch unveränderter Standardwert (12) wird umgestellt; hat die Administration selbst einen Wert eingetragen,
bleibt er. Die Umstellung steht mit Grund in der Historie der Einstellungen.
"""
from django.db import migrations, models
from django.utils import timezone

GRUND = "Standard „Kontakt überfällig“ von 12 auf 4 Monate (Festlegung 01.10.2026: Patienten kommen meist quartalsweise)"


def umstellen(apps, schema_editor):
    Einstellungen = apps.get_model("stammdaten", "Einstellungen")
    Historie = apps.get_model("stammdaten", "HistoricalEinstellungen")
    e = Einstellungen.objects.filter(pk=1, kontakt_ueberfaellig_monate=12).first()
    if e is None:
        return
    e.kontakt_ueberfaellig_monate = 4
    e.save(update_fields=["kontakt_ueberfaellig_monate"])
    werte = {f.attname: getattr(e, f.attname) for f in Einstellungen._meta.concrete_fields}
    Historie.objects.create(**werte, history_date=timezone.now(), history_type="~", history_change_reason=GRUND)


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0006_arzt_alter_auswahlwert_liste_and_more")]

    operations = [
        migrations.AlterField(
            model_name="einstellungen",
            name="kontakt_ueberfaellig_monate",
            field=models.PositiveSmallIntegerField(default=4, verbose_name="Kontakt überfällig"),
        ),
        migrations.AlterField(
            model_name="historicaleinstellungen",
            name="kontakt_ueberfaellig_monate",
            field=models.PositiveSmallIntegerField(default=4, verbose_name="Kontakt überfällig"),
        ),
        migrations.RunPython(umstellen, migrations.RunPython.noop),
    ]
