"""Dokumentvorlagen für den Datenschutz (Datenschutzinformation, Einwilligung, Schweigepflichtentbindung) und der
Freigabevermerk des Infusionsplans (Festlegung 02.10.2026).

Enthält die aktive Vorlage „Infusionsplan“ noch den bisherigen Text des Freigabevermerks unverändert, entsteht daraus
eine neue Version mit dem Datenfeld {{Plan.Freigabevermerk}} (nennt bei einer Freigabe außerhalb von EPM auch den Weg
und wer den Plan abgeschlossen hat); ein Entwurf wird an Ort und Stelle umgestellt. Eine Vorlage, in der der Satz
geändert wurde, bleibt, wie sie ist – ein Plan lässt sich dann erst „nach Freigabe abschließen“, wenn das Datenfeld
ergänzt ist (``Infusionsplan.abschliessen_auf_anordnung``)."""
from django.db import migrations, models
from django.utils import timezone

ARTEN = [('infusionsplan', 'Infusionsplan'), ('patientendatenblatt', 'Patientendatenblatt'),
         ('datenschutzinformation', 'Datenschutzinformation'),
         ('einwilligung', 'Einwilligung in die Datenverarbeitung'),
         ('schweigepflichtentbindung', 'Schweigepflichtentbindung')]
ALT = "Maschinell erstellt, geprüft und freigegeben von {{Plan.freigegeben_von}} am {{Plan.freigegeben_datum}}."
NEU = "{{Plan.Freigabevermerk}}"
NOTIZ = "Freigabevermerk nennt Weg und Abschluss (Update)"


def umgestellt(alt):
    """Bausteine mit dem bisherigen Satz → Datenfeld; (Bausteine, geändert?)"""
    bloecke, geaendert = [], False
    for b in alt:
        if isinstance(b, dict) and b.get("typ") == "text" and b.get("text") == ALT:
            b = {**b, "text": NEU, "optionen": {**(b.get("optionen") or {}), "ausblenden_wenn_leer": True}}
            geaendert = True
        bloecke.append(b)
    return bloecke, geaendert


def freigabevermerk(apps, schema_editor):
    Vorlage = apps.get_model("vorlagen", "Dokumentvorlage")
    Historie = apps.get_model("vorlagen", "HistoricalDokumentvorlage")
    # ein Entwurf in Arbeit ist änderbar: der Satz wird an Ort und Stelle ersetzt
    for entwurf in Vorlage.objects.filter(art="infusionsplan", status="entwurf"):
        bloecke, geaendert = umgestellt(entwurf.bloecke)
        if geaendert:
            Vorlage.objects.filter(pk=entwurf.pk).update(bloecke=bloecke)
    aktiv = Vorlage.objects.filter(art="infusionsplan", status="aktiv").first()
    if aktiv is None:
        return  # noch keine Vorlage: die Startvorlage enthält das neue Datenfeld bereits
    bloecke, geaendert = umgestellt(aktiv.bloecke)
    if not geaendert:
        return
    hoechste = Vorlage.objects.filter(art="infusionsplan").aggregate(m=models.Max("version"))["m"] or 0
    # veröffentlichte Versionen sind unveränderlich; erlaubt ist allein „aktiv → abgelöst“
    Vorlage.objects.filter(pk=aktiv.pk).update(status="abgeloest")
    jetzt = timezone.now()
    neu = Vorlage.objects.create(art="infusionsplan", version=hoechste + 1, status="aktiv", bloecke=bloecke,
                                 notiz=NOTIZ, veroeffentlicht_am=jetzt)
    werte = {f.attname: getattr(neu, f.attname) for f in Vorlage._meta.concrete_fields
             if f.attname in {h.attname for h in Historie._meta.concrete_fields}}
    Historie.objects.create(**werte, history_date=jetzt, history_type="+", history_change_reason=NOTIZ[:100])


class Migration(migrations.Migration):

    dependencies = [
        ('vorlagen', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dokumentvorlage',
            name='art',
            field=models.CharField(choices=ARTEN, max_length=30),
        ),
        migrations.AlterField(
            model_name='historicaldokumentvorlage',
            name='art',
            field=models.CharField(choices=ARTEN, max_length=30),
        ),
        migrations.RunPython(freigabevermerk, migrations.RunPython.noop),
    ]
