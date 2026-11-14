"""Korrekturen als Beispiele im Prompt (Einstellung ``beispiele_max``) und mitgelieferte Promptvorlage
„Diktat als Brief gliedern“ (14.11.2026). Der Text der Vorlage steht wortgleich in ``ki/chat.py``
(``DIKTAT_ANWEISUNG``) – Migrationen importieren keinen App-Code."""
from decimal import Decimal

from django.db import migrations, models

NAME = "Diktat als Brief gliedern"
BESCHREIBUNG = "Abschrift eines Diktats als gegliederten Bericht (Überschriften, ohne Diktieranweisungen)."
ANWEISUNG = (
    "Der Nutzer gibt dir die automatische Abschrift eines ärztlichen Diktats (Spracherkennung – sie kann Hör- und "
    "Schreibfehler enthalten) und die Berichtsart. Mache daraus einen gegliederten Entwurf dieses Berichts.\n"
    "- Übernimm jede inhaltliche Aussage, jeden Wert, jede Einheit, jedes Datum, jede Diagnose und jede Dosierung "
    "genau. Lasse nichts weg und füge nichts hinzu.\n"
    "- Setze Diktieranweisungen um, statt sie abzuschreiben („Punkt“, „Komma“, „neuer Absatz“, „Doppelpunkt“), "
    "entferne Füllwörter („äh“, „also“) und Versprecher; sagt der Arzt „streichen“ oder „nein, …“, gilt die "
    "korrigierte Fassung.\n"
    "- Gliedere mit Zwischenüberschriften, die zum Inhalt passen, z. B. Diagnosen, Anamnese, Befund, Therapie und "
    "Verlauf, Medikation, Procedere – nur Abschnitte, zu denen das Diktat etwas sagt. Jede Überschrift steht allein "
    "in einer Zeile mit „## “ davor; Aufzählungen beginnen mit „- “.\n"
    "- Ist ein Fachbegriff offensichtlich falsch gehört und die richtige Schreibweise eindeutig, schreibe sie "
    "richtig; sonst behalte das Wort und setze [?] dahinter.\n"
    "- Keine Anrede, keine Grußformel, keine Vorbemerkung – nur der Berichtstext."
)


def anlegen(apps, schema_editor):
    V = apps.get_model("ki", "KiPromptvorlage")
    V.objects.get_or_create(name=NAME, defaults={"beschreibung": BESCHREIBUNG, "anweisung": ANWEISUNG,
                                                 "reihenfolge": 35, "mitgeliefert": True,
                                                 "temperatur": Decimal("0.10")})


class Migration(migrations.Migration):

    dependencies = [
        ("ki", "0005_chat_anhaenge"),
    ]

    operations = [
        migrations.AddField(
            model_name="kieinstellung",
            name="beispiele_max",
            field=models.PositiveSmallIntegerField(
                default=12,
                help_text="frühere Korrekturen als Beispiele im Prompt (ki/beispiele.py); 0 = aus",
            ),
        ),
        migrations.RunPython(anlegen, migrations.RunPython.noop),
    ]
