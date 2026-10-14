"""Laborprofile Malabsorption auf dem Briefpapier der Regeneration Clinic (14.10.2026): Die mitgelieferten Bögen
``eigen-rgc-mal…`` bekommen den Briefkopf 1:1 wie auf dem gelieferten Dokument (``"briefpapier": "rgc"``).

Geändert wird nur die mitgelieferte Fassung 1, solange es keine weitere Fassung und keinen Entwurf gibt – eine schon
bearbeitete Vorlage bleibt, wie sie ist (dort im Editor beim Baustein „Briefkopf“ einschalten)."""
from django.db import migrations


def umstellen(apps, schema_editor):
    from vorlagen.rgc import schluessel, vorlagen

    # Freigegebene Fassungen sind per Trigger unveränderlich (audit/schutz.py, epm_vorlage_schutz). Auf einer frischen
    # Datenbank fehlt der Trigger beim ersten migrate noch, auf dem Server nicht: ohne Wartungsmodus brach migrate dort
    # ab und das Backend startete nicht (Rückfall 2.0.26 → 2.0.24, 14.10.2026). Daher wie patienten/0020 nur für diese
    # eine Transaktion im Wartungsmodus.
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET LOCAL epm.wartung = 'on'")

    Dokumentvorlage = apps.get_model("vorlagen", "Dokumentvorlage")
    for v in vorlagen():
        if not v["quelle"].startswith("RC_Labor_MAL-"):
            continue
        art = schluessel(v["quelle"])
        fassungen = list(Dokumentvorlage.objects.filter(art=art))
        if len(fassungen) != 1 or fassungen[0].version != 1 or fassungen[0].status != "aktiv":
            continue
        fassungen[0].bloecke = v["bloecke"]
        fassungen[0].save(update_fields=["bloecke"])


class Migration(migrations.Migration):

    dependencies = [
        ("vorlagen", "0011_rgc_laborprofile"),
    ]

    operations = [migrations.RunPython(umstellen, migrations.RunPython.noop)]
