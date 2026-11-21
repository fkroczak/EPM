"""Dokumenttypen mit eigenem Reiter in der Akte der RGC (Wunsch 21.11.2026): OP-Bericht, Röntgen / Radiologie,
Überweisung, Stationäre Einweisung.

Gibt es den Typ unter Vorlagen › Auswahllisten schon (z. B. „Röntgen“ von Hand angelegt), bekommt dieser die Kennung –
es entsteht kein zweiter Eintrag. Sonst wird er neu angelegt. Der angezeigte Name bleibt danach frei änderbar."""
from django.db import migrations

# Kennung, Name beim Anlegen, bereits übliche Namen (Groß-/Kleinschreibung egal)
TYPEN = [
    ("op_bericht", "OP-Bericht", ["OP-Bericht", "OP Bericht", "OP-Berichte", "Operationsbericht"]),
    ("radiologie", "Röntgen / Radiologie", ["Röntgen", "Röntgenbefund", "Röntgenbericht", "Radiologie",
                                             "Radiologischer Befund", "Radiologischer Bericht", "Röntgen / Radiologie"]),
    ("ueberweisung", "Überweisung", ["Überweisung", "Überweisungen", "Überweisungsschein"]),
    ("einweisung", "Stationäre Einweisung", ["Stationäre Einweisung", "Einweisung", "Krankenhauseinweisung",
                                             "Einweisung stationär"]),
]


def anlegen(apps, schema_editor):
    Auswahlwert = apps.get_model("stammdaten", "Auswahlwert")
    for i, (kennung, name, namen) in enumerate(TYPEN):
        if Auswahlwert.objects.filter(liste="dokumenttyp", kennung=kennung).exists():
            continue
        klein = {n.lower() for n in namen}
        wert = next((w for w in Auswahlwert.objects.filter(liste="dokumenttyp", kennung="").order_by("id")
                     if w.wert.strip().lower() in klein), None)
        if wert is None:
            wert = Auswahlwert(liste="dokumenttyp", wert=name, reihenfolge=250 + i * 10)
        wert.kennung = kennung
        wert.aktiv = True
        wert.save()


def zurueck(apps, schema_editor):
    apps.get_model("stammdaten", "Auswahlwert").objects.filter(liste="dokumenttyp").update(kennung="")


class Migration(migrations.Migration):
    dependencies = [("stammdaten", "0028_rgc_reiter_eingriffe")]
    operations = [migrations.RunPython(anlegen, zurueck)]
