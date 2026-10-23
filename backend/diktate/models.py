"""Diktate (Wunsch 23.10.2026): Der Arzt diktiert Berichte (Arztbrief, Konsultationsbericht …) und Kommentare zu
Infusionsplänen; der Server schreibt die Aufnahme offline ab (whisper.cpp im OCR-Dienst, nur CPU).

- Die Aufnahme liegt bis zur Freigabe des Berichts unter ``EPM_SCANS/diktate/`` (nicht in der Sicherung, wie Scans)
  und wird mit der Freigabe gelöscht; beim Kommentar eines Infusionsplans gleich nach der Übernahme.
- Abgeschrieben wird ``sofort`` (kurze Diktate, nach wenigen Minuten fertig) oder ``nachts`` (lange Diktate, im
  Nachtfenster – der Server bleibt tagsüber frei).
- ``uebergabe``: Der Arzt macht den Text selbst fertig oder gibt ihn ans Sekretariat (Liste „Diktate“).
- Ins Diktat kommt nur Text; in den Bericht kommt er erst mit „In den Text übernehmen“. Freigeben darf wie bisher,
  wer „Berichte freigeben“ hat.
"""
from pathlib import Path

from django.conf import settings
from django.db import models

from patienten.models import Patient


def diktat_ordner() -> Path:
    return settings.EPM_SCANS / "diktate"


class Diktat(models.Model):
    class Zweck(models.TextChoices):
        BERICHT = "bericht", "Bericht"
        PLAN = "plan", "Kommentar zum Infusionsplan"

    class Status(models.TextChoices):
        WARTET = "wartet", "wartet"
        LAEUFT = "laeuft", "wird abgeschrieben"
        FERTIG = "fertig", "abgeschrieben"
        FEHLER = "fehler", "Fehler"

    class Wann(models.TextChoices):
        SOFORT = "sofort", "sofort"
        NACHTS = "nachts", "heute Nacht"

    class Uebergabe(models.TextChoices):
        SELBST = "selbst", "selbst fertig machen"
        SEKRETARIAT = "sekretariat", "ans Sekretariat"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="diktate")
    bericht = models.ForeignKey("berichte.Bericht", on_delete=models.CASCADE, null=True, blank=True,
                                related_name="diktate")
    zweck = models.CharField(max_length=10, choices=Zweck.choices, default=Zweck.BERICHT)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WARTET, db_index=True)
    wann = models.CharField(max_length=10, choices=Wann.choices, default=Wann.SOFORT)
    uebergabe = models.CharField(max_length=15, choices=Uebergabe.choices, default=Uebergabe.SELBST)

    # Aufnahme (relativ zu diktat_ordner(); leer, sobald gelöscht)
    datei = models.CharField(max_length=80, blank=True)
    mime = models.CharField(max_length=60, blank=True)
    groesse = models.PositiveIntegerField(default=0)
    dauer_s = models.FloatField(default=0)
    audio_geloescht_am = models.DateTimeField(null=True, blank=True)

    # Abschrift: formatierter Text (HTML wie im Editor) und die Wörter mit Zeit und Sicherheit fürs Nachhören
    text = models.TextField(blank=True)
    woerter = models.JSONField(default=list, blank=True, help_text="[[Wort, von_ms, bis_ms, Sicherheit 0–1], …]")
    modell = models.CharField(max_length=80, blank=True)
    rechenzeit_s = models.FloatField(null=True, blank=True)
    schritt = models.CharField(max_length=120, blank=True)
    fehler = models.CharField(max_length=300, blank=True)
    versuche = models.PositiveSmallIntegerField(default=0)
    lebenszeichen = models.DateTimeField(null=True, blank=True)

    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    abgeschrieben_am = models.DateTimeField(null=True, blank=True)
    uebernommen_am = models.DateTimeField(null=True, blank=True)
    uebernommen_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name="+")

    class Meta:
        verbose_name = "Diktat"
        verbose_name_plural = "Diktate"
        ordering = ["-erstellt_am", "-id"]
        indexes = [models.Index(fields=["status", "wann", "erstellt_am"], name="diktat_warteschlange")]

    def __str__(self):
        return f"Diktat {self.pk} ({self.get_status_display()})"

    @property
    def pfad(self) -> Path | None:
        return diktat_ordner() / self.datei if self.datei else None


class Begriffsliste(models.Model):
    """Eigene Fachbegriffe je Person (Namen, Präparate, Abkürzungen): gehen als Vorlage an die Abschrift."""

    benutzer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="diktat_begriffe")
    begriffe = models.TextField(blank=True, help_text="ein Begriff je Zeile oder durch Komma getrennt")
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fachbegriffe für Diktate"
        verbose_name_plural = "Fachbegriffe für Diktate"
