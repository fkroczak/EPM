"""Medikationsplan im Querformat (13.10.2026): Die mitgelieferte Startvorlage „Medikationsplan“ erhält, solange sie nie
von einem Menschen veröffentlicht wurde, eine neue Fassung im Querformat (Falzmarken aus); eine bearbeitete und
freigegebene Vorlage bleibt, wie sie ist – das Querformat lässt sich im Editor einschalten."""
from django.db import migrations, models

NOTIZ = "Querformat (Update)"


def medikationsplan_quer(apps, schema_editor):
    """Die nie von einem Menschen veröffentlichte Startvorlage „Medikationsplan“ bekommt eine Fassung im Querformat;
    veröffentlichte Fassungen sind unveränderlich (Schutz-Trigger), erlaubt ist allein „aktiv → abgelöst“."""
    from django.utils import timezone

    Vorlage = apps.get_model("vorlagen", "Dokumentvorlage")
    Historie = apps.get_model("vorlagen", "HistoricalDokumentvorlage")
    aktiv = Vorlage.objects.filter(art="medikationsplan", firma=None, status="aktiv",
                                   veroeffentlicht_von__isnull=True).first()
    if aktiv is None:
        return
    bloecke = [{**b, "falzmarken": False} if isinstance(b, dict) and b.get("typ") == "briefkopf" else b
               for b in aktiv.bloecke]
    hoechste = Vorlage.objects.filter(art="medikationsplan", firma=None).aggregate(m=models.Max("version"))["m"] or 0
    Vorlage.objects.filter(pk=aktiv.pk).update(status="abgeloest")
    jetzt = timezone.now()
    neu = Vorlage.objects.create(art="medikationsplan", version=hoechste + 1, status="aktiv", bloecke=bloecke,
                                 ausrichtung="quer", notiz=NOTIZ, veroeffentlicht_am=jetzt)
    werte = {f.attname: getattr(neu, f.attname) for f in Vorlage._meta.concrete_fields
             if f.attname in {h.attname for h in Historie._meta.concrete_fields}}
    Historie.objects.create(**werte, history_date=jetzt, history_type="+", history_change_reason=NOTIZ)


class Migration(migrations.Migration):

    dependencies = [
        ("vorlagen", "0008_firma_ausrichtung"),
    ]

    operations = [
        migrations.RunPython(medikationsplan_quer, migrations.RunPython.noop),
    ]
