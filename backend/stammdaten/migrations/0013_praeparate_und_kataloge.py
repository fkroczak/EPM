"""Bestandsdaten zu den Wünschen vom 06.10.2026 (F111, F112, F115, F117).

* Zusatzvolumen: „Sterofundin“ → „Sterofundin ISO“, „Ringer-Infusionslösung“ → „Ringer-Lösung“,
  „Junosteril“ → „Jonosteril“ (Tippfehler); „Ringer-Lactat“ kommt dazu (U43).
* Vitamine: „Natrovit“ mit Hinweis „baugleich zu Cernevit, günstiger (Regressgefahr)“.
* Katheterschutz: „NutriLock“ (reines Taurolidin 2 %) und „TauroLock“ (Taurolidin mit Citrat).
* Dipeptamin und Omegaven werden ausgeblendet – bestehende Pläne behalten sie (U42).
* Auswahllisten: Berichtsarten, Dokumenttypen „Bericht“, „Sprechstunde“ und „BIA“.
* Katalog der Laborparameter nach Alices Liste.

Alles wiederholbar und schonend: Es wird nur angelegt oder umbenannt, was fehlt bzw. noch den alten Namen
trägt. Gelöscht wird nichts.
"""
from django.db import migrations

UMBENENNEN = [
    ("basisloesung", "Sterofundin", "", "Sterofundin ISO"),
    ("basisloesung", "Ringer-Infusionslösung", "", "Ringer-Lösung"),
    ("basisloesung", "Junosteril", "", "Jonosteril"),
]

NEU = [
    ("basisloesung", "Sterofundin ISO", "", "ml", ""),
    ("basisloesung", "Ringer-Lösung", "", "ml", ""),
    ("basisloesung", "Ringer-Lactat", "", "ml", ""),
    ("basisloesung", "Jonosteril", "", "ml", ""),
    ("basisloesung", "NaCl", "0,9 %", "ml", ""),
    ("vitamine", "Natrovit", "", "ml", "baugleich zu Cernevit, günstiger (Regressgefahr)"),
    ("katheterschutz", "NutriLock", "2 %", "ml", "reines Taurolidin 2 %"),
    ("katheterschutz", "TauroLock", "", "ml", "Taurolidin mit Citrat"),
]

AUSBLENDEN = ["dipeptamin", "omegaven"]

DOKUMENTTYPEN = ["BIA", "Bericht", "Sprechstunde"]
BERICHTARTEN = ["Arztbrief", "Verlaufsbericht", "Stellungnahme", "Sonstiges"]


def _laborparameter():
    from patienten.testdaten import LABORPARAMETER

    return LABORPARAMETER


def vorwaerts(apps, schema_editor):
    Praeparat = apps.get_model("stammdaten", "Praeparat")
    Auswahlwert = apps.get_model("stammdaten", "Auswahlwert")
    Laborparameter = apps.get_model("stammdaten", "Laborparameter")

    for kategorie, alt, konz, neu in UMBENENNEN:
        if Praeparat.objects.filter(kategorie=kategorie, name=neu, konzentration=konz).exists():
            continue  # der neue Name ist schon da – der alte bleibt, damit nichts doppelt entsteht
        Praeparat.objects.filter(kategorie=kategorie, name=alt, konzentration=konz).update(name=neu)

    for kategorie, name, konz, einheit, hinweis in NEU:
        vorhanden = Praeparat.objects.filter(kategorie=kategorie, name=name, konzentration=konz).first()
        if vorhanden is None:
            hoechste = (Praeparat.objects.filter(kategorie=kategorie)
                        .order_by("-reihenfolge").values_list("reihenfolge", flat=True).first() or 0)
            Praeparat.objects.create(kategorie=kategorie, name=name, konzentration=konz, einheit=einheit,
                                     hinweis=hinweis, reihenfolge=hoechste + 10)
        elif hinweis and not vorhanden.hinweis:
            vorhanden.hinweis = hinweis
            vorhanden.save(update_fields=["hinweis"])

    for name in AUSBLENDEN:
        Praeparat.objects.filter(name__iexact=name, aktiv=True).update(aktiv=False)

    for i, wert in enumerate(DOKUMENTTYPEN):
        Auswahlwert.objects.get_or_create(liste="dokumenttyp", wert=wert, defaults={"reihenfolge": 200 + i * 10})
    for i, wert in enumerate(BERICHTARTEN):
        Auswahlwert.objects.get_or_create(liste="berichtart", wert=wert, defaults={"reihenfolge": (i + 1) * 10})

    for i, (gruppe, name, einheit, kurz) in enumerate(_laborparameter()):
        Laborparameter.objects.get_or_create(
            gruppe=gruppe, name=name,
            defaults={"einheit": einheit, "kurzname": kurz, "reihenfolge": (i + 1) * 10},
        )


def rueckwaerts(apps, schema_editor):
    """Nur die Umbenennung zurückdrehen; angelegte Katalogeinträge bleiben (gelöscht wird in EPM nichts)."""
    Praeparat = apps.get_model("stammdaten", "Praeparat")
    for kategorie, alt, konz, neu in UMBENENNEN:
        if Praeparat.objects.filter(kategorie=kategorie, name=alt, konzentration=konz).exists():
            continue
        Praeparat.objects.filter(kategorie=kategorie, name=neu, konzentration=konz).update(name=alt)


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0012_labor_diagnosen_hinweis")]

    operations = [migrations.RunPython(vorwaerts, rueckwaerts)]
