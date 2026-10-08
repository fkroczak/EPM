"""Menüpunkt „Scans“ (Festlegung 08.10.2026, F158 ff.): Posteingang für gescannte und fotografierte Dokumente.

Ablauf: hochladen → Seiten aufbereiten (automatisch, je Seite von Hand korrigierbar) → Text erkennen (OCR-Dienst)
→ einem Patienten zuordnen (mit Übernahme von Laborwerten, BIA, Diagnosen) oder den Text herauskopieren.

Ein Scan gehört zu keiner Akte. Er liegt bis zur Zuordnung bzw. bis zum Ablauf der Aufbewahrung (Standard 7 Tage,
je Scan verlängerbar bis zur Höchstdauer, beides unter Vorlagen › Grenzwerte) und wird dann endgültig gelöscht –
Datenbankeinträge und Dateien. Beim Zuordnen wird er zu einem Dokument der Akte und verschwindet aus „Scans“.
"""
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


class Scan(models.Model):
    class Status(models.TextChoices):
        WARTET = "wartet", "wartet auf Erkennung"
        LAEUFT = "laeuft", "wird erkannt"
        FERTIG = "fertig", "erkannt"
        FEHLER = "fehler", "Fehler"

    titel = models.CharField(max_length=200)
    originalname = models.CharField(max_length=255)
    mime = models.CharField(max_length=100)
    groesse = models.PositiveBigIntegerField(help_text="Größe der hochgeladenen Datei in Bytes")
    sha256 = models.CharField(max_length=64)
    # Verzeichnis unter EPM_SCANS (zufälliger Name, kein Bezug zum Inhalt)
    ordner = models.CharField(max_length=40, unique=True, editable=False)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WARTET, db_index=True)
    fortschritt = models.PositiveSmallIntegerField(default=0, help_text="0–100")
    schritt = models.CharField(max_length=120, blank=True)
    fehler = models.TextField(blank=True)
    versuche = models.PositiveSmallIntegerField(default=0)
    begonnen_am = models.DateTimeField(null=True, blank=True)
    lebenszeichen = models.DateTimeField(null=True, blank=True)
    erkannt_am = models.DateTimeField(null=True, blank=True)
    dauer_s = models.FloatField(null=True, blank=True, help_text="Dauer der letzten Erkennung in Sekunden")

    hochgeladen_am = models.DateTimeField(auto_now_add=True, db_index=True)
    hochgeladen_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                        related_name="+")
    # von einem Testbenutzer hochgeladen: nur mit „Testdaten sehen“ sichtbar und nur Testpatienten zuzuordnen
    ist_test = models.BooleanField(default=False)
    laeuft_ab_am = models.DateTimeField(db_index=True)
    verlaengert_anzahl = models.PositiveSmallIntegerField(default=0)

    # Ergebnis (über alle Seiten)
    text = models.TextField(blank=True)
    sicherheit = models.FloatField(null=True, blank=True)
    unsicher = models.PositiveIntegerField(default=0, help_text="Zahl der unsicheren Wörter")
    verfahren = models.JSONField(default=list, blank=True)
    auswertung = models.JSONField(default=dict, blank=True)
    dokumentdatum = models.DateField(null=True, blank=True)
    # Für die Liste: wie viel Platz die Dateien des Scans belegen (Original, Seiten, Vorschauen)
    belegt = models.PositiveBigIntegerField(default=0)

    class Meta:
        verbose_name = "Scan"
        verbose_name_plural = "Scans"
        ordering = ["-hochgeladen_am", "-id"]

    def __str__(self):
        return f"Scan Nr. {self.pk}"

    @property
    def pfad(self) -> Path:
        return settings.EPM_SCANS / self.ordner

    @property
    def original(self) -> Path:
        return self.pfad / "original"

    @property
    def hoechst_bis(self):
        from stammdaten.models import Einstellungen

        return self.hochgeladen_am + timedelta(days=Einstellungen.aktuell().scans_hoechst_tage)

    @property
    def bearbeitbar(self) -> bool:
        return self.status != self.Status.LAEUFT

    def abgelaufen(self) -> bool:
        return self.laeuft_ab_am <= timezone.now()


class ScanSeite(models.Model):
    class Status(models.TextChoices):
        WARTET = "wartet", "wartet"
        FERTIG = "fertig", "erkannt"
        FEHLER = "fehler", "Fehler"

    scan = models.ForeignKey(Scan, on_delete=models.CASCADE, related_name="seiten")
    nr = models.PositiveSmallIntegerField(help_text="Reihenfolge im Scan, ab 1")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WARTET)
    fehler = models.TextField(blank=True)

    # Rohbild der Seite (gerastert bzw. geladen, EXIF-Drehung angewandt) – Grundlage jeder neuen Aufbereitung
    roh = models.CharField(max_length=80)
    roh_breite = models.PositiveIntegerField(default=0)
    roh_hoehe = models.PositiveIntegerField(default=0)
    herkunft = models.CharField(max_length=10, default="bild", help_text="pdf | bild")
    kamera = models.BooleanField(default=False, help_text="Foto mit Kameradaten (EXIF)")
    dpi = models.FloatField(null=True, blank=True)
    # Textebene einer PDF-Seite: Wörter [Text, x, y, b, h] in Pixeln des Rohbilds
    textebene = models.JSONField(null=True, blank=True)

    # Was der Mensch festgelegt hat (scans.ocr.aufbereitung.Einstellungen) und was dabei herauskam
    einstellungen = models.JSONField(default=dict, blank=True)
    info = models.JSONField(default=dict, blank=True)
    # Auftrag an den OCR-Dienst für diese Seite: {"art": "seite"} oder {"art": "bereich", "box": [...], "staerke": n}
    auftrag = models.JSONField(null=True, blank=True)

    bild = models.CharField(max_length=80, blank=True, help_text="aufbereitete Seite (Anzeige, PDF)")
    grau = models.CharField(max_length=80, blank=True, help_text="aufbereitete Seite für die Erkennung")
    klein = models.CharField(max_length=80, blank=True, help_text="Vorschaubild")
    breite = models.PositiveIntegerField(default=0)
    hoehe = models.PositiveIntegerField(default=0)

    ergebnis = models.JSONField(default=dict, blank=True, help_text="Reihen mit Wörtern, Sicherheit, Lage")
    text = models.TextField(blank=True)
    sicherheit = models.FloatField(null=True, blank=True)
    unsicher = models.PositiveIntegerField(default=0)
    erkannt_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Seite eines Scans"
        verbose_name_plural = "Seiten von Scans"
        ordering = ["scan", "nr", "id"]

    def __str__(self):
        return f"Seite {self.nr} von {self.scan}"

    def datei(self, name: str) -> Path:
        return self.scan.pfad / name
