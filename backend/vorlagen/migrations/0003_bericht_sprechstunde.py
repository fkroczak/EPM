"""Zwei neue Dokumentvorlagen (Wünsche aus der Praxis vom 06.10.2026): „Bericht“ (F115) und
„Unterlagen für die Sprechstunde“ (F116).

Angelegt werden sie nicht hier: Die Startvorlage entsteht beim ersten Erzeugen einer PDF
(``Dokumentvorlage.aktive``) und kann danach wie jede andere unter Vorlagen › Dokumentvorlagen bearbeitet
und veröffentlicht werden."""
from django.db import migrations, models

ARTEN = [
    ("infusionsplan", "Infusionsplan"),
    ("patientendatenblatt", "Patientendatenblatt"),
    ("bericht", "Bericht"),
    ("sprechstunde", "Unterlagen für die Sprechstunde"),
    ("datenschutzinformation", "Datenschutzinformation"),
    ("einwilligung", "Einwilligung in die Datenverarbeitung"),
    ("schweigepflichtentbindung", "Schweigepflichtentbindung"),
]


class Migration(migrations.Migration):
    dependencies = [("vorlagen", "0002_datenschutz_freigabevermerk")]

    operations = [
        migrations.AlterField(
            model_name="dokumentvorlage",
            name="art",
            field=models.CharField(choices=ARTEN, max_length=30),
        ),
        migrations.AlterField(
            model_name="historicaldokumentvorlage",
            name="art",
            field=models.CharField(choices=ARTEN, max_length=30),
        ),
    ]
