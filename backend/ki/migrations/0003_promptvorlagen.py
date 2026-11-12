"""Mitgelieferte Promptvorlagen für den KI-Chat (12.11.2026). Änderbar unter Administration › Vorlagen › KI-Prompts."""
from decimal import Decimal

from django.db import migrations

VORLAGEN = [
    ("Medizinisch formulieren",
     "Stichpunkte oder Umgangssprache in sachliche medizinische Fachsprache bringen.",
     "Formuliere den Text des Nutzers in sachliche, präzise medizinische Fachsprache um, wie sie in Arztbriefen und "
     "der Verlaufsdokumentation üblich ist. Behalte jede inhaltliche Aussage, jeden Wert, jede Einheit, jedes Datum "
     "und jede Dosierung exakt bei. Füge keine Inhalte hinzu und lasse keine weg. Gängige Abkürzungen sind erlaubt, "
     "wenn sie eindeutig sind. Gib nur den umformulierten Text aus, ohne Vorbemerkung."),
    ("Rechtschreibung und Grammatik prüfen",
     "Fehler korrigieren, Inhalt und Stil bleiben.",
     "Korrigiere ausschließlich Rechtschreibung, Grammatik und Zeichensetzung des Textes. Ändere weder Inhalt noch "
     "Fachbegriffe, Werte, Einheiten oder Stil. Gib zuerst den korrigierten Text aus und danach unter der "
     "Überschrift „Änderungen:“ eine kurze Liste der Korrekturen (alt → neu). Gibt es keine Fehler, schreibe nur "
     "„Keine Fehler gefunden.“"),
    ("Arztbrief-Abschnitt aus Stichpunkten",
     "Aus Notizen einen zusammenhängenden Abschnitt für Arztbrief oder Bericht schreiben.",
     "Schreibe aus den Stichpunkten des Nutzers einen zusammenhängenden, sachlichen Abschnitt für einen Arztbrief "
     "bzw. Bericht in ganzen Sätzen (Perfekt bzw. Präsens, ohne Ich-Form). Verwende nur die Angaben aus den "
     "Stichpunkten. Fehlen für einen vollständigen Satz Angaben, setze [?] statt sie zu ergänzen."),
    ("Für Patienten verständlich",
     "Fachtext in einfache, freundliche Sprache für Patienten und Angehörige übertragen.",
     "Übertrage den Fachtext in einfache, verständliche Sprache für Patienten und Angehörige (kurze Sätze, "
     "Fachbegriffe erklären oder ersetzen, Sie-Form, freundlich und sachlich). Inhalt, Werte und Dosierungen bleiben "
     "exakt gleich; füge keine Ratschläge hinzu, die nicht im Text stehen."),
    ("Kürzen und zusammenfassen",
     "Langen Text auf das Wesentliche kürzen.",
     "Fasse den Text knapp und sachlich zusammen (höchstens ein Drittel der Länge). Übernimm Werte, Daten, "
     "Diagnosen und Dosierungen nur wörtlich aus dem Text, nichts hinzufügen. Gliedere bei Bedarf in kurze "
     "Stichpunkte."),
    ("Freier Chat",
     "Ohne feste Aufgabe – nur der Sicherheitsrahmen gilt.",
     "Beantworte die Anfrage des Nutzers sachlich und knapp."),
]


def anlegen(apps, schema_editor):
    V = apps.get_model("ki", "KiPromptvorlage")
    for i, (name, beschreibung, anweisung) in enumerate(VORLAGEN):
        V.objects.get_or_create(name=name, defaults={
            "beschreibung": beschreibung, "anweisung": anweisung, "reihenfolge": (i + 1) * 10, "mitgeliefert": True,
            "temperatur": Decimal("0.30") if name == "Freier Chat" else Decimal("0.10")})


class Migration(migrations.Migration):
    dependencies = [("ki", "0002_chat")]
    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
