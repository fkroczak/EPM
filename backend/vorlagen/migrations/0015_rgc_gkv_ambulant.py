"""Neue Patientenerklärung GKV der Regeneration Clinic (11.11.2026): „Vorlage_Patientenerklaerung_GKV_ambulant_
tagesstationaer.docx“ ersetzt die bisherige Fassung „02_Patientenerklaerung_GKV_DE_Stundung_V5“ (``eigen-rgc-f02``).

Die alte Vorlage wird nicht mehr angeboten: Vor dem ersten Import der Altdaten wird Fassung 1 ersetzt und alle übrigen
Fassungen und Entwürfe entfallen (``vorlagen.fassung1``); danach wird die alte Fassung abgelöst – sie bleibt nur für
bereits erzeugte PDFs erhalten – und die neue ist die nächste Fassung. Schlüssel und Paket „Deutschland – GKV“ bleiben."""
import json

from django.db import migrations
from django.utils import timezone

ART = "eigen-rgc-f02"
QUELLE = "02_Patientenerklaerung_GKV_ambulant"


def ersetzen(apps, schema_editor):
    from faelle.formulare import umgestellt
    from vorlagen.fassung1 import import_durchgefuehrt
    from vorlagen.rgc import ORDNER

    EigenesSchreiben = apps.get_model("vorlagen", "EigenesSchreiben")
    Dokumentvorlage = apps.get_model("vorlagen", "Dokumentvorlage")
    e = EigenesSchreiben.objects.filter(schluessel=ART).first()
    if e is None or e.mitgeliefert == f"rgc-{QUELLE}":
        return  # Firma RGC fehlt oder schon die neue Vorlage (frische Datenbank)
    # freigegebene Fassungen schützt ein Trigger (audit/schutz.py) – wie 0012 nur für diese Transaktion im Wartungsmodus
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET LOCAL epm.wartung = 'on'")

    v = json.loads((ORDNER / f"{QUELLE}.json").read_text(encoding="utf-8"))
    bloecke = umgestellt(ART, v["bloecke"]) or v["bloecke"]
    notiz = f"Word-Vorlage der RGC: {v['datei']}"[:200]
    EigenesSchreiben.objects.filter(pk=e.pk).update(name=v["name"], beschreibung=v["beschreibung"][:300],
                                                   mitgeliefert=f"rgc-{QUELLE}")

    fassungen = Dokumentvorlage.objects.filter(art=ART)
    alt = fassungen.filter(status="aktiv").first() or fassungen.exclude(version=None).order_by("-version").first()
    jetzt = timezone.now()
    if not import_durchgefuehrt(apps):
        fassungen.exclude(version=1).delete()
        if fassungen.exists():
            fassungen.update(status="aktiv", bloecke=bloecke, notiz=notiz, veroeffentlicht_am=jetzt)
            return
        version = 1
    else:
        fassungen.filter(status="entwurf").delete()
        fassungen.filter(status="aktiv").update(status="abgeloest")
        version = max([f.version or 0 for f in fassungen] + [0]) + 1
    Dokumentvorlage.objects.create(art=ART, firma=alt.firma if alt else e.firma, version=version, status="aktiv",
                                   bloecke=bloecke, ausrichtung=alt.ausrichtung if alt else "hoch", notiz=notiz,
                                   veroeffentlicht_am=jetzt)


class Migration(migrations.Migration):

    dependencies = [
        ("vorlagen", "0014_vor_dem_import_fassung_1"),
        ("faelle", "0003_rgc_formulare_falldaten"),
    ]

    operations = [migrations.RunPython(ersetzen, migrations.RunPython.noop)]
