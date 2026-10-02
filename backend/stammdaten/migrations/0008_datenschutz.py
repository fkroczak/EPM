"""Datenschutz (Festlegung 02.10.2026): Aufbewahrung nach Abschluss, „Abschluss prüfen“, Aufbewahrung des Audit-Logs,
Erklärungen, die in jeder Akte vorliegen sollen – einstellbar unter Vorlagen › Grenzwerte."""
import stammdaten.models
from django.db import migrations, models

FELDER = [
    ("aufbewahrung_jahre", lambda: models.PositiveSmallIntegerField(
        default=10, verbose_name="Aufbewahrung nach Abschluss der Akte")),
    ("abschluss_pruefen_monate", lambda: models.PositiveSmallIntegerField(
        default=24, verbose_name="Abschluss prüfen, wenn kein Kontakt seit")),
    ("protokoll_aufbewahrung_jahre", lambda: models.PositiveSmallIntegerField(
        default=0, help_text="0 = unbegrenzt; sonst werden ältere Einträge täglich entfernt",
        verbose_name="Audit-Log aufbewahren")),
    ("pflicht_erklaerungen", lambda: models.JSONField(
        blank=True, default=stammdaten.models.pflicht_erklaerungen_standard,
        verbose_name="Erklärungen, die vorliegen sollen")),
]


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0007_kontakt_ueberfaellig_4_monate")]

    operations = [
        migrations.AddField(model_name=modell, name=name, field=feld())
        for name, feld in FELDER for modell in ("einstellungen", "historicaleinstellungen")
    ]
