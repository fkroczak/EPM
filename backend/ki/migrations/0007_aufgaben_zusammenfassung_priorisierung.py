"""Priorisierung, Nachtaufgaben (``KiAufgabe``), „Akte auf einen Blick“ (``KiZusammenfassung``) – 14.11.2026.

Datenteil: die zwei mitgelieferten Nachtaufgaben anlegen und – falls es die Einstellungszeile schon gibt – Diktat-
Nachtfenster und Chat-Aufbewahrung aus den bisherigen Umgebungsvariablen übernehmen (``EPM_DIKTAT_NACHT``,
``EPM_KI_CHAT_TAGE``), damit sich nach dem Update nichts ändert. Migrationen importieren keinen App-Code: die
Auswertung der Variablen steht hier noch einmal (wie ``ki.models.diktat_nacht_env``).
"""
import datetime
import os

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import ki.models

AUFGABEN = [
    {"name": "Akte auf einen Blick für die Termine von morgen", "art": "zusammenfassung_termine", "aktiv": True,
     "wochentage": [0, 1, 2, 3, 4, 5, 6], "uhrzeit": datetime.time(3, 0), "parameter": {"tage_voraus": 1}},
    {"name": "Dokumente mit aktivem Modell neu lesen", "art": "neu_lesen", "aktiv": False, "wochentage": [6],
     "uhrzeit": datetime.time(1, 0),
     "parameter": {"seit_tagen": 30, "dokumenttypen": [], "nur_anderes_modell": True, "hoechstens": 200}},
]


def anlegen(apps, schema_editor):
    A = apps.get_model("ki", "KiAufgabe")
    for a in AUFGABEN:
        A.objects.get_or_create(art=a["art"], name=a["name"], defaults=a)
    E = apps.get_model("ki", "KiEinstellung")
    e = E.objects.filter(pk=1).first()
    if e is None:
        return  # KiEinstellung.laden() liest die Variablen beim ersten Mal selbst
    try:
        ab, bis = (int(x) for x in os.environ.get("EPM_DIKTAT_NACHT", "21-7").split("-"))
        if not (0 <= ab <= 23 and 0 <= bis <= 23):
            raise ValueError
    except ValueError:
        ab, bis = 21, 7
    try:
        tage = min(365, max(1, int(os.environ.get("EPM_KI_CHAT_TAGE", "30"))))
    except ValueError:
        tage = 30
    E.objects.filter(pk=1).update(diktat_nacht_beginn=ab, diktat_nacht_ende=bis, chat_tage=tage)


class Migration(migrations.Migration):

    dependencies = [
        ("ki", "0006_korrekturbeispiele_diktat"),
        ("patienten", "0022_befunde"),
        ("stammdaten", "0026_berichtart_konsultationsbericht"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="kieinstellung",
            name="chat_tage",
            field=models.PositiveSmallIntegerField(
                default=30, help_text="KI-Chats ohne Änderung danach löschen"
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="chat_vorrang",
            field=models.BooleanField(
                default=True,
                help_text="tagsüber hält ein wartender Chat alle anderen Aufträge an",
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="diktat_nacht_beginn",
            field=models.PositiveSmallIntegerField(
                default=21, help_text="Diktate „heute Nacht“ ab (Stunde)"
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="diktat_nacht_ende",
            field=models.PositiveSmallIntegerField(
                default=7, help_text="… bis (Stunde)"
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="neu_tage",
            field=models.PositiveSmallIntegerField(
                default=7, help_text="so lange gilt ein Dokument als neu"
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="prio_altbestand",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="prio_angefordert",
            field=models.PositiveSmallIntegerField(
                default=10, help_text="„jetzt verarbeiten“, „Erneut verarbeiten“"
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="prio_neu",
            field=models.PositiveSmallIntegerField(
                default=5, help_text="neu hochgeladene Dokumente"
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="prio_neu_lesen",
            field=models.PositiveSmallIntegerField(
                default=3, help_text="„Neu lesen“ (Nachtaufgabe, Administration)"
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="prio_termin",
            field=models.PositiveSmallIntegerField(
                default=8, help_text="Akte mit Praxistermin in den nächsten Tagen"
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="termin_tage",
            field=models.PositiveSmallIntegerField(
                default=3, help_text="Vorlauf für den Termin-Vorrang; 0 = aus"
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="zusammenfassung_ohne_termin_tage",
            field=models.PositiveSmallIntegerField(
                default=90,
                help_text="Zeitraum der Zusammenfassung ohne früheren Termin und ohne Kontakt",
            ),
        ),
        migrations.AddField(
            model_name="kieinstellung",
            name="zusammenfassung_tagsueber",
            field=models.BooleanField(
                default=True,
                help_text="„Akte auf einen Blick“ auf Anforderung auch tagsüber erstellen",
            ),
        ),
        migrations.CreateModel(
            name="KiAufgabe",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "art",
                    models.CharField(
                        choices=[
                            (
                                "zusammenfassung_termine",
                                "Akte auf einen Blick für die nächsten Termine",
                            ),
                            ("neu_lesen", "Dokumente mit dem aktiven Modell neu lesen"),
                            ("dokumente_vormerken", "Dokumente in die Queue legen"),
                        ],
                        max_length=30,
                    ),
                ),
                ("aktiv", models.BooleanField(default=True)),
                (
                    "wochentage",
                    models.JSONField(
                        default=ki.models._alle_wochentage,
                        help_text="0 = Montag … 6 = Sonntag",
                    ),
                ),
                (
                    "uhrzeit",
                    models.TimeField(
                        default=datetime.time(3, 0),
                        help_text="Ortszeit (Zeitzone der KI-Einstellungen)",
                    ),
                ),
                ("parameter", models.JSONField(blank=True, default=dict)),
                ("letzter_lauf", models.DateTimeField(blank=True, null=True)),
                ("letztes_ergebnis", models.CharField(blank=True, max_length=500)),
                (
                    "jetzt_angefordert",
                    models.BooleanField(
                        default=False,
                        help_text="läuft beim nächsten Durchlauf des KI-Dienstes",
                    ),
                ),
                ("geaendert_am", models.DateTimeField(auto_now=True)),
                (
                    "geaendert_von",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "KI-Nachtaufgabe",
                "verbose_name_plural": "KI-Nachtaufgaben",
                "ordering": ["uhrzeit", "id"],
            },
        ),
        migrations.CreateModel(
            name="KiZusammenfassung",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "grund",
                    models.CharField(
                        choices=[
                            ("termin", "nachts für einen Termin vorbereitet"),
                            ("angefordert", "auf Anforderung"),
                        ],
                        max_length=12,
                    ),
                ),
                ("von", models.DateField(blank=True, null=True)),
                ("bis", models.DateField(blank=True, null=True)),
                (
                    "von_grund",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("termin", "seit dem letzten Termin"),
                            ("kontakt", "seit dem letzten Kontakt"),
                            ("standard", "fester Zeitraum (ohne Termin und Kontakt)"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("wartet", "wartet"),
                            ("laeuft", "wird erstellt"),
                            ("fertig", "fertig"),
                            ("fehler", "Fehler"),
                        ],
                        db_index=True,
                        default="wartet",
                        max_length=8,
                    ),
                ),
                (
                    "fakten",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="[{nr, text, quelle, datum, link}]",
                    ),
                ),
                ("entwurf", models.TextField(blank=True)),
                (
                    "pruefung",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Markierungen der Gegenprüfung",
                    ),
                ),
                ("fehler", models.TextField(blank=True)),
                ("prompt_version", models.CharField(blank=True, max_length=20)),
                ("erstellt_am", models.DateTimeField(auto_now_add=True)),
                ("fertig_am", models.DateTimeField(blank=True, null=True)),
                ("lebenszeichen", models.DateTimeField(blank=True, null=True)),
                ("dauer_s", models.FloatField(blank=True, null=True)),
                (
                    "angefordert_von",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "firma",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="stammdaten.firma",
                    ),
                ),
                (
                    "modellversion",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="ki.kimodellversion",
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ki_zusammenfassungen",
                        to="patienten.patient",
                    ),
                ),
                (
                    "termin",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="patienten.termin",
                    ),
                ),
            ],
            options={
                "verbose_name": "KI-Zusammenfassung (Akte auf einen Blick)",
                "verbose_name_plural": "KI-Zusammenfassungen (Akte auf einen Blick)",
                "ordering": ["-erstellt_am", "-id"],
                "indexes": [
                    models.Index(
                        fields=["patient", "status"], name="ki_zusammenfassung_patient"
                    )
                ],
            },
        ),
        migrations.RunPython(anlegen, migrations.RunPython.noop),
    ]
