"""Vor dem Import nur Fassung 1 (14.10.2026): Wurden noch keine Altdaten übernommen, werden alle Dokumentvorlagen auf
Fassung 1 zurückgeführt – die Fassungen 2, 3 … aus den Updates (0002, 0009, 0013) und aus dem Freigeben in der
Testphase entfallen, die aktive Fassung wird Fassung 1 (``vorlagen.fassung1``)."""
from django.db import migrations


def zurueckfuehren(apps, schema_editor):
    from vorlagen.fassung1 import auf_fassung_1, import_durchgefuehrt

    if import_durchgefuehrt(apps):
        return
    # veröffentlichte Fassungen und Akteneinträge sind per Trigger geschützt (audit/schutz.py): wie 0012 nur für diese
    # eine Transaktion im Wartungsmodus
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET LOCAL epm.wartung = 'on'")
    auf_fassung_1(apps)


class Migration(migrations.Migration):

    dependencies = [
        ("vorlagen", "0013_fusszeile_vorstand_bank"),
        ("altimport", "0001_initial"),
        ("infusionen", "0008_historicalinfusionsplan_firma_infusionsplan_firma"),
        ("berichte", "0002_bericht_firma_historicalbericht_firma"),
        ("korrespondenz", "0001_korrespondenz"),
        ("patienten", "0021_medikamente"),
    ]

    operations = [migrations.RunPython(zurueckfuehren, migrations.RunPython.noop)]
