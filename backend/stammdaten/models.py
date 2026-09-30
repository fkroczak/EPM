"""Stammdaten, die der Admin selbst pflegt: Auswahllisten, Versorger, Präparate, Einstellungen."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords


class Auswahlwert(models.Model):
    class Liste(models.TextChoices):
        KATHETER = "katheter", "Katheter"
        DOKUMENTTYP = "dokumenttyp", "Dokumenttyp"
        KONTAKTART = "kontaktart", "Kontaktart"

    liste = models.CharField(max_length=30, choices=Liste.choices)
    wert = models.CharField(max_length=100)
    reihenfolge = models.PositiveSmallIntegerField(default=100)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Auswahlwert"
        verbose_name_plural = "Auswahlwerte"
        ordering = ["liste", "reihenfolge", "wert"]
        constraints = [models.UniqueConstraint(fields=["liste", "wert"], name="auswahlwert_eindeutig")]

    def delete(self, *args, **kwargs):
        raise PermissionError("Auswahlwerte werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return self.wert


class Versorger(models.Model):
    """Homecare-Versorger. Wird nie gelöscht, nur deaktiviert."""

    name = models.CharField(max_length=150, unique=True)
    strasse = models.CharField("Straße", max_length=150, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField(max_length=100, blank=True)
    telefon = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    notiz = models.TextField(blank=True)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Versorger"
        verbose_name_plural = "Versorger"
        ordering = ["name"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Versorger werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return self.name


class Ansprechpartner(models.Model):
    """Person beim Versorger; betreut jeweils einen Teil der Patienten."""

    versorger = models.ForeignKey(Versorger, on_delete=models.PROTECT, related_name="ansprechpartner")
    name = models.CharField(max_length=150)
    telefon = models.CharField(max_length=50, blank=True)
    mobil = models.CharField(max_length=50, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    notiz = models.TextField(blank=True)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Ansprechpartner"
        verbose_name_plural = "Ansprechpartner"
        ordering = ["versorger__name", "name"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Ansprechpartner werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return f"{self.name} ({self.versorger})"


class Praeparat(models.Model):
    class Kategorie(models.TextChoices):
        BASISLOESUNG = "basisloesung", "Basislösung"
        GLUCOSE = "glucose", "Glucose"
        AMINOSAEUREN = "aminosaeuren", "Aminosäuren"
        LIPIDE = "lipide", "Lipide"
        ALBUMIN = "albumin", "Albumin"
        ELEKTROLYTE = "elektrolyte", "Elektrolyte"
        VITAMINE = "vitamine", "Vitamine"
        SPURENELEMENTE = "spurenelemente", "Spurenelemente"
        KATHETERSCHUTZ = "katheterschutz", "Katheterschutz"
        MEDIKAMENT = "medikament", "Medikament"
        SONSTIGES = "sonstiges", "Sonstiges"

    kategorie = models.CharField(max_length=30, choices=Kategorie.choices)
    name = models.CharField(max_length=150)
    konzentration = models.CharField(max_length=60, blank=True, help_text="z. B. 50 %, 10 %, 20 %")
    einheit = models.CharField(max_length=10, default="ml", help_text="Standard-Einheit der Menge")
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Präparat"
        verbose_name_plural = "Präparate"
        ordering = ["kategorie", "name", "konzentration"]
        constraints = [
            models.UniqueConstraint(fields=["kategorie", "name", "konzentration"], name="praeparat_eindeutig")
        ]

    def delete(self, *args, **kwargs):
        raise PermissionError("Präparate werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return f"{self.name} {self.konzentration}".strip()


class Einstellungen(models.Model):
    """Genau ein Datensatz (pk=1): Absender, Warnschwellen, Plausibilitätsgrenzen."""

    class Absender(models.TextChoices):
        STIFTUNG = "stiftung", "Stiftung"
        GUG = "gug", "gUG"

    absender = models.CharField(max_length=10, choices=Absender.choices, default=Absender.STIFTUNG)

    # Warnungen
    gewicht_warnung_prozent = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("5.0"))
    gewicht_warnung_monate = models.PositiveSmallIntegerField(default=3)
    plan_alter_warnung_monate = models.PositiveSmallIntegerField(default=12)

    # Plausibilitätsgrenzen (Eingaben außerhalb werden abgelehnt)
    gewicht_min_kg = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("20.0"))
    gewicht_max_kg = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("250.0"))
    groesse_min_cm = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("100.0"))
    groesse_max_cm = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("230.0"))
    kcal_max_tag = models.PositiveIntegerField(default=5000)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Einstellungen"
        verbose_name_plural = "Einstellungen"

    def save(self, *args, **kwargs):
        self.pk = 1
        if self.gewicht_min_kg >= self.gewicht_max_kg or self.groesse_min_cm >= self.groesse_max_cm:
            raise ValidationError("Untere Grenze muss kleiner als obere Grenze sein.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Einstellungen können nicht gelöscht werden.")

    @classmethod
    def aktuell(cls) -> "Einstellungen":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Einstellungen"
