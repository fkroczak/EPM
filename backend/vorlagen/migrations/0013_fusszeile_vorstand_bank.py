"""Vorstand und Spendenkonto in der Fußzeile aus den Absenderangaben (14.10.2026): Bisher standen sie als fester Text
in jeder Vorlage (aus der Startvorlage ``bloecke.FUSS``); jetzt als {{Absender.Vorstand}} und
{{Absender.Bankverbindung}}, gepflegt unter Vorlagen › Briefkopf und Logo.

Nur der unveränderte Text wird ersetzt. Ein Entwurf wird an Ort und Stelle umgestellt; aus einer freigegebenen Fassung
entsteht eine neue Fassung (die bisherige bleibt abgelöst erhalten – jede gespeicherte PDF verweist auf ihre Fassung),
wie in 0002. Eine Vorlage, in der der Text schon geändert wurde, bleibt, wie sie ist."""
from django.db import migrations, models
from django.utils import timezone

ERSETZEN = [
    ("Prof. Dr. Markus Masin; Prof. Dr. Till Zech, LL.M.", "{{Absender.Vorstand}}"),
    ("DKM Darlehnskasse Münster eG · DE71 4006 0265 0017 8247 00 · BIC GENODEM1DKM", "{{Absender.Bankverbindung}}"),
]
NOTIZ = "Vorstand und Spendenkonto aus „Briefkopf und Logo“ (Update)"


def umgestellt(alt):
    """→ (Bausteine, geändert?)"""
    bloecke, geaendert = [], False
    for b in alt or []:
        if isinstance(b, dict) and b.get("typ") == "fusszeile" and isinstance(b.get("text"), str):
            text = b["text"]
            for vorher, nachher in ERSETZEN:
                text = text.replace(vorher, nachher)
            if text != b["text"]:
                b = {**b, "text": text}
                geaendert = True
        bloecke.append(b)
    return bloecke, geaendert


def umstellen(apps, schema_editor):
    Vorlage = apps.get_model("vorlagen", "Dokumentvorlage")
    Historie = apps.get_model("vorlagen", "HistoricalDokumentvorlage")
    for entwurf in Vorlage.objects.filter(status="entwurf"):
        bloecke, geaendert = umgestellt(entwurf.bloecke)
        if geaendert:
            Vorlage.objects.filter(pk=entwurf.pk).update(bloecke=bloecke)
    for aktiv in list(Vorlage.objects.filter(status="aktiv")):
        bloecke, geaendert = umgestellt(aktiv.bloecke)
        if not geaendert:
            continue
        hoechste = Vorlage.objects.filter(art=aktiv.art, firma_id=aktiv.firma_id).aggregate(
            m=models.Max("version"))["m"] or 0
        # veröffentlichte Fassungen sind unveränderlich; erlaubt ist allein „aktiv → abgelöst“
        Vorlage.objects.filter(pk=aktiv.pk).update(status="abgeloest")
        jetzt = timezone.now()
        neu = Vorlage.objects.create(art=aktiv.art, firma_id=aktiv.firma_id, ausrichtung=aktiv.ausrichtung,
                                     version=hoechste + 1, status="aktiv", bloecke=bloecke, notiz=NOTIZ,
                                     veroeffentlicht_am=jetzt,
                                     # wer die bisherige Fassung freigegeben hat: sonst bekämen von Menschen
                                     # freigegebene Vordrucke wieder das Wasserzeichen „ENTWURF“ (models.py, api.py)
                                     veroeffentlicht_von_id=aktiv.veroeffentlicht_von_id)
        werte = {f.attname: getattr(neu, f.attname) for f in Vorlage._meta.concrete_fields
                 if f.attname in {h.attname for h in Historie._meta.concrete_fields}}
        Historie.objects.create(**werte, history_date=jetzt, history_type="+", history_change_reason=NOTIZ[:100])


class Migration(migrations.Migration):

    dependencies = [
        ("vorlagen", "0012_rgc_laborprofile_briefpapier"),
        ("stammdaten", "0025_absender_vorstand_bank"),
    ]

    operations = [migrations.RunPython(umstellen, migrations.RunPython.noop)]
