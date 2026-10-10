"""Menüpunkt „Scans“ (Festlegung 08.10.2026, F160 ff.): Posteingang für gescannte und fotografierte Dokumente.

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
    # „Werte übernehmen“ aus einem Dokument der Akte (F171): Der Scan ist eine Arbeitskopie dieses Dokuments; beim
    # Zuordnen entsteht kein neues Dokument, die Werte werden mit dem vorhandenen verknüpft
    quelldokument = models.ForeignKey("patienten.Dokument", on_delete=models.CASCADE, null=True, blank=True,
                                      related_name="+")

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
    # Absturzschutz: gesetzt, solange der Dienst an der Seite arbeitet. Findet er beim nächsten Start einen Wert vor,
    # brach der vorige Versuch ab (z. B. Speichergrenze des Containers) – die Seite wird dann sparsamer erkannt.
    begonnen_am = models.DateTimeField(null=True, blank=True)
    abbrueche = models.PositiveSmallIntegerField(default=0, help_text="abgebrochene Versuche an dieser Seite")

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


class DokumentErkennung(models.Model):
    """„Text erkennen“ an einem Dokument der Akte (F170): Der OCR-Dienst legt mit OCRmyPDF eine unsichtbare Textebene
    über die Seiten (das Aussehen bleibt, PDF/A) und ersetzt die Datei des Dokuments durch diese PDF. Der Text kommt
    in ``DokumentText`` (Suche, Kopieren). Ein Auftrag je Dokument zur gleichen Zeit."""

    class Status(models.TextChoices):
        WARTET = "wartet", "wartet"
        LAEUFT = "laeuft", "wird erkannt"
        FERTIG = "fertig", "erkannt"
        FEHLER = "fehler", "Fehler"

    dokument = models.ForeignKey("patienten.Dokument", on_delete=models.CASCADE, related_name="erkennungen")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WARTET, db_index=True)
    angefordert_am = models.DateTimeField(auto_now_add=True)
    angefordert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                        related_name="+")
    begonnen_am = models.DateTimeField(null=True, blank=True)
    lebenszeichen = models.DateTimeField(null=True, blank=True)
    beendet_am = models.DateTimeField(null=True, blank=True)
    versuche = models.PositiveSmallIntegerField(default=0)
    schritt = models.CharField(max_length=120, blank=True)
    fehler = models.TextField(blank=True)
    # Prüfsumme beim Anfordern: Wurde die Datei inzwischen anders ersetzt, wird nichts überschrieben
    sha256_vorher = models.CharField(max_length=64)
    sha256_nachher = models.CharField(max_length=64, blank=True)
    seiten = models.PositiveIntegerField(null=True, blank=True)
    dauer_s = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Texterkennung eines Dokuments"
        verbose_name_plural = "Texterkennungen von Dokumenten"
        ordering = ["angefordert_am", "id"]
        constraints = [
            models.UniqueConstraint(fields=["dokument"], condition=models.Q(status__in=["wartet", "laeuft"]),
                                    name="scans_dokumenterkennung_ein_offener_auftrag"),
        ]

    def __str__(self):
        return f"Texterkennung Dokument {self.dokument_id}"


class GelernteZuordnung(models.Model):
    """Texterkennung lernt mit (F182): Was die Pflegekraft beim Übernehmen anders zugeordnet oder korrigiert hat.

    Gespeichert werden nur Bezeichnungen, wie sie auf Befunden stehen („Kreatimin“, „Harnstoff-N“, „Körperzellmasse“),
    und wohin sie gehören (Laborparameter, BIA-Feld, Diagnose mit ICD-Code) – je Absender (Labor) und allgemein.
    Keine Patientendaten: kein Bezug zu Patient, Scan oder Dokument, keine Werte, keine Namen, kein Datum. Darum darf
    das Gelernte bleiben, wenn Scans, Akten oder Dokumente gelöscht werden; „Datenbank leeren“ leert es mit.
    """

    class Art(models.TextChoices):
        LABOR = "labor", "Laborparameter"
        BIA = "bia", "BIA-Feld"
        DIAGNOSE = "diagnose", "Diagnose"
        SPALTE = "spalte", "Spaltenlage der Werte"
        # F189: „Falsch erkannt – gehört nicht dazu“ (Kopfzeile, Referenzbereich, Datum …): nicht mehr als Wert anbieten
        IGNORIEREN = "ignorieren", "nicht auswerten"
        # F189: Bereich der Seite, in dem dieses Labor seine Werte druckt (die Pflegekraft hat ihn markiert)
        BEREICH = "bereich", "Bereich der Werte"

    art = models.CharField(max_length=10, choices=Art.choices, db_index=True)
    # normalisierter Name des Absenders (scans.ocr.auswertung.norm); leer = allgemein, für alle Absender
    quelle = models.CharField(max_length=150, blank=True, db_index=True)
    quelle_anzeige = models.CharField(max_length=150, blank=True)
    # erkannte Bezeichnung, normalisiert (Schlüssel) und wie gelesen (Anzeige); bei der Spaltenlage „wertspalte“
    erkannt = models.CharField(max_length=200)
    erkannt_anzeige = models.CharField(max_length=200, blank=True)
    # Ziel: ID des Laborparameters (als Text), Name des BIA-Felds oder ICD-Code
    ziel = models.CharField(max_length=40, blank=True)
    ziel_text = models.CharField(max_length=200, blank=True, help_text="korrigierte Bezeichnung (Diagnose)")
    parameter = models.ForeignKey("stammdaten.Laborparameter", on_delete=models.CASCADE, null=True, blank=True,
                                  related_name="+")
    # Spaltenlage: linke Kante der Wertespalte und Zeichenbreite (relativ zur Seitenbreite)
    spalte_x = models.FloatField(null=True, blank=True)
    spalte_zeichen = models.FloatField(null=True, blank=True)
    # Bereich der Werte (F189): [x, y, Breite, Höhe] relativ zur Seite – nur Lage, kein Inhalt
    bereich = models.JSONField(null=True, blank=True)
    # Die Bezeichnung war ein Lesefehler (ähnlich gelesen) – kommt nicht in die Wörterliste für Tesseract
    lesefehler = models.BooleanField(default=False)
    bestaetigt = models.PositiveIntegerField(default=0, help_text="wie oft beim Übernehmen bestätigt")
    gesperrt = models.BooleanField(default=False, help_text="„nie wieder so zuordnen“")
    erstmals_am = models.DateTimeField(auto_now_add=True)
    zuletzt_am = models.DateTimeField(default=timezone.now)
    zuletzt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+")

    class Meta:
        verbose_name = "gelernte Zuordnung"
        verbose_name_plural = "gelernte Zuordnungen"
        ordering = ["art", "quelle", "erkannt", "-bestaetigt", "id"]
        constraints = [
            models.UniqueConstraint(fields=["art", "quelle", "erkannt", "ziel"], name="scans_gelernt_eindeutig"),
        ]

    def __str__(self):
        return f"{self.get_art_display()}: {self.erkannt_anzeige or self.erkannt} → {self.ziel_text or self.ziel}"


class KorrekturZaehler(models.Model):
    """Kennzahl „Wie oft musste korrigiert werden“ (F182): je Monat und Art, wie viele erkannte Werte übernommen wurden
    und wie viele davon die Pflegekraft ändern oder von Hand ergänzen musste. Nur Zahlen, keine Inhalte."""

    monat = models.DateField(help_text="erster Tag des Monats")
    art = models.CharField(max_length=10, choices=GelernteZuordnung.Art.choices[:3])
    uebernommen = models.PositiveIntegerField(default=0)
    korrigiert = models.PositiveIntegerField(default=0)
    # „Falsch erkannt“ angemerkt (F189): verworfene Vorschläge
    verworfen = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Zähler der Korrekturen"
        verbose_name_plural = "Zähler der Korrekturen"
        ordering = ["monat", "art"]
        constraints = [models.UniqueConstraint(fields=["monat", "art"], name="scans_korrektur_monat_art")]

    def __str__(self):
        return f"{self.monat:%m/%Y} {self.art}: {self.korrigiert}/{self.uebernommen}"


class LernEinstellung(models.Model):
    """Steuerung des Lernens (F189), eine Zeile: pausieren und Schwelle (ab wie vielen Bestätigungen eine gelernte
    Zuordnung als sicher gilt). Ändern mit „Vorlagen pflegen“, im Audit-Log."""

    pausiert = models.BooleanField(default=False, help_text="nichts Neues lernen; Gelerntes wird weiter angewandt")
    schwelle = models.PositiveSmallIntegerField(default=2, help_text="1–3 Bestätigungen bis „sicher“")
    geaendert_am = models.DateTimeField(null=True, blank=True)
    geaendert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="+")

    class Meta:
        verbose_name = "Steuerung des Lernens"
        verbose_name_plural = "Steuerung des Lernens"

    def __str__(self):
        return f"Lernen {'pausiert' if self.pausiert else 'aktiv'}, Schwelle {self.schwelle}"

    @classmethod
    def aktuell(cls) -> "LernEinstellung":
        e = cls.objects.order_by("id").first()
        return e or cls.objects.create()
