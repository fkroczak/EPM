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
        TERMINORT = "terminort", "Terminort"
        BEZIEHUNG = "beziehung", "Beziehung (Bezugsperson)"

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
    zustaendigkeit = models.CharField("Zuständigkeit", max_length=150, blank=True,
                                      help_text="z. B. „Disposition · Patienten A–K“")
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


class Arzt(models.Model):
    """Arzt bzw. Praxis (gemeinsame Liste, Festlegung 01.10.2026). Wird einmal gepflegt und beim Patienten
    mit Rolle zugeordnet (Hausarzt, Facharzt …); eine geänderte Telefonnummer gilt so für alle Patienten.
    Wird nie gelöscht, nur deaktiviert."""

    name = models.CharField("Name", max_length=150, help_text="z. B. „Dr. med. Anna Hausmann“")
    praxis = models.CharField("Praxis / Klinik", max_length=150, blank=True)
    fachrichtung = models.CharField(max_length=100, blank=True, help_text="z. B. Allgemeinmedizin, Gastroenterologie")
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
        verbose_name = "Arzt"
        verbose_name_plural = "Ärzte"
        ordering = ["name", "ort"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Ärzte werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return f"{self.name} ({self.ort})" if self.ort else self.name


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
    reihenfolge = models.PositiveSmallIntegerField(default=100)
    aktiv = models.BooleanField(default=True, help_text="Ausgeblendete Präparate erscheinen nicht bei neuen Plänen")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Präparat"
        verbose_name_plural = "Präparate"
        ordering = ["kategorie", "reihenfolge", "name", "konzentration"]
        constraints = [
            models.UniqueConstraint(fields=["kategorie", "name", "konzentration"], name="praeparat_eindeutig")
        ]

    def delete(self, *args, **kwargs):
        raise PermissionError("Präparate werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return f"{self.name} {self.konzentration}".strip()


# Erklärungen, die bei jeder Akte in Betreuung vorliegen sollen (Schlüssel wie ``patienten.Erklaerung.Art``).
# Fehlt eine davon, steht die Akte unter „Nach und nach prüfen“ (Festlegung 02.10.2026).
ERKLAERUNGSARTEN = ["datenschutzinformation", "einwilligung", "schweigepflichtentbindung"]


def pflicht_erklaerungen_standard():
    return list(ERKLAERUNGSARTEN)


def kontaktstufen_fehler(bald, ueberfaellig) -> dict | None:
    """Kontakt fällig in zwei Stufen (S04): beide mindestens 1 Monat, „bald fällig“ vor „überfällig“."""
    if bald is None or bald < 1:
        return {"kontakt_bald_monate": "Bitte mindestens 1 Monat angeben."}
    if ueberfaellig is None or ueberfaellig <= bald:
        return {"kontakt_ueberfaellig_monate": "„Überfällig“ muss später liegen als „bald fällig“."}
    return None


class Einstellungen(models.Model):
    """Genau ein Datensatz (pk=1): Absender, Warnschwellen, Plausibilitätsgrenzen, Fristen des Datenschutzes."""

    class Absender(models.TextChoices):
        STIFTUNG = "stiftung", "Stiftung"
        GUG = "gug", "gUG"

    absender = models.CharField("Absender", max_length=10, choices=Absender.choices, default=Absender.STIFTUNG)

    # Warnungen
    gewicht_warnung_prozent = models.DecimalField("Warnung Gewichtsverlust", max_digits=4, decimal_places=1,
                                                  default=Decimal("5.0"))
    gewicht_warnung_monate = models.PositiveSmallIntegerField("Zeitraum Gewichtsverlust", default=3)
    plan_alter_warnung_monate = models.PositiveSmallIntegerField("Infusionsplan gilt als alt nach", default=12)
    # Wiedereinbestellung in zwei Stufen (Festlegung 01.10.2026, S04): „bald fällig“ ab 4 Monaten (quartalsweise
    # Kontakte + 1 Monat), „überfällig“ ab 6 Monaten – beide einstellbar, „bald“ muss früher liegen als „überfällig“
    kontakt_bald_monate = models.PositiveSmallIntegerField("Kontakt bald fällig", default=4)
    kontakt_ueberfaellig_monate = models.PositiveSmallIntegerField("Kontakt überfällig", default=6)

    # Plausibilitätsgrenzen (Eingaben außerhalb werden abgelehnt)
    gewicht_min_kg = models.DecimalField("Gewicht minimal", max_digits=5, decimal_places=1, default=Decimal("20.0"))
    gewicht_max_kg = models.DecimalField("Gewicht maximal", max_digits=5, decimal_places=1, default=Decimal("250.0"))
    groesse_min_cm = models.DecimalField("Größe minimal", max_digits=5, decimal_places=1, default=Decimal("100.0"))
    groesse_max_cm = models.DecimalField("Größe maximal", max_digits=5, decimal_places=1, default=Decimal("230.0"))
    kcal_max_tag = models.PositiveIntegerField("Energie maximal", default=5000)
    # Grenzen je Planwert (Entwurf 18 · Vorlagen › Grenzwerte). Die Standardwerte sind bewusst weit
    # gefasst und werden von der Administration festgelegt.
    kcal_min_tag = models.PositiveIntegerField("Energie minimal", default=0)
    glucose_min_g = models.DecimalField("Glucose minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    glucose_max_g = models.DecimalField("Glucose maximal", max_digits=6, decimal_places=1, default=Decimal("1000"))
    aminosaeuren_min_g = models.DecimalField("Aminosäuren minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    aminosaeuren_max_g = models.DecimalField("Aminosäuren maximal", max_digits=6, decimal_places=1, default=Decimal("300"))
    lipide_min_g = models.DecimalField("Lipide minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    lipide_max_g = models.DecimalField("Lipide maximal", max_digits=6, decimal_places=1, default=Decimal("200"))
    natrium_min_mmol = models.DecimalField("Natrium minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    natrium_max_mmol = models.DecimalField("Natrium maximal", max_digits=6, decimal_places=1, default=Decimal("500"))
    kalium_min_mmol = models.DecimalField("Kalium minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    kalium_max_mmol = models.DecimalField("Kalium maximal", max_digits=6, decimal_places=1, default=Decimal("300"))
    # Gesamtvolumen = Gewicht × 35 ml (Festlegung 01.10.2026); Standard deckt 20–250 kg ab
    volumen_min_ml = models.DecimalField("Gesamtvolumen minimal", max_digits=7, decimal_places=0, default=Decimal("0"))
    volumen_max_ml = models.DecimalField("Gesamtvolumen maximal", max_digits=7, decimal_places=0, default=Decimal("9000"))

    # Datenschutz (Festlegung 02.10.2026)
    aufbewahrung_jahre = models.PositiveSmallIntegerField("Aufbewahrung nach Abschluss der Akte", default=10)
    abschluss_pruefen_monate = models.PositiveSmallIntegerField("Abschluss prüfen, wenn kein Kontakt seit", default=24)
    protokoll_aufbewahrung_jahre = models.PositiveSmallIntegerField(
        "Audit-Log aufbewahren", default=0, help_text="0 = unbegrenzt; sonst werden ältere Einträge täglich entfernt")
    pflicht_erklaerungen = models.JSONField("Erklärungen, die vorliegen sollen", default=pflicht_erklaerungen_standard,
                                            blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Einstellungen"
        verbose_name_plural = "Einstellungen"

    GRENZPAARE = [
        ("gewicht_min_kg", "gewicht_max_kg"), ("groesse_min_cm", "groesse_max_cm"), ("kcal_min_tag", "kcal_max_tag"),
        ("glucose_min_g", "glucose_max_g"), ("aminosaeuren_min_g", "aminosaeuren_max_g"),
        ("lipide_min_g", "lipide_max_g"), ("natrium_min_mmol", "natrium_max_mmol"),
        ("kalium_min_mmol", "kalium_max_mmol"), ("volumen_min_ml", "volumen_max_ml"),
    ]

    def save(self, *args, **kwargs):
        self.pk = 1
        for unten, oben in self.GRENZPAARE:
            if getattr(self, unten) >= getattr(self, oben):
                raise ValidationError({unten: "Untere Grenze muss kleiner als obere Grenze sein."})
        if not 1 <= self.aufbewahrung_jahre <= 100:
            raise ValidationError({"aufbewahrung_jahre": "Bitte 1 bis 100 Jahre angeben."})
        if self.abschluss_pruefen_monate < 1:
            raise ValidationError({"abschluss_pruefen_monate": "Bitte mindestens 1 Monat angeben."})
        fehler = kontaktstufen_fehler(self.kontakt_bald_monate, self.kontakt_ueberfaellig_monate)
        if fehler:
            raise ValidationError(fehler)
        if (not isinstance(self.pflicht_erklaerungen, list)
                or any(a not in ERKLAERUNGSARTEN for a in self.pflicht_erklaerungen)
                or len(set(self.pflicht_erklaerungen)) != len(self.pflicht_erklaerungen)):
            raise ValidationError({"pflicht_erklaerungen": "Unbekannte Erklärung."})
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Einstellungen können nicht gelöscht werden.")

    @classmethod
    def aktuell(cls) -> "Einstellungen":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Einstellungen"


class Absenderangaben(models.Model):
    """Briefkopf je Absender (Entwurf 18 · Briefkopf und Logo). Welcher gilt, steht in Einstellungen.absender."""

    art = models.CharField(max_length=10, choices=Einstellungen.Absender.choices, unique=True)
    name = models.CharField("Name", max_length=200, blank=True)
    strasse = models.CharField("Straße", max_length=150, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField("Ort", max_length=100, blank=True)
    telefon = models.CharField("Telefon", max_length=50, blank=True)
    fax = models.CharField("Fax", max_length=50, blank=True)
    email = models.CharField("E-Mail", max_length=150, blank=True)
    internet = models.CharField("Internet", max_length=150, blank=True)
    fusszeile = models.CharField("Fußzeile", max_length=300, blank=True)

    history = HistoricalRecords()

    # Vorbelegung wie im Entwurf; die Administration pflegt die Angaben danach selbst
    VORBELEGUNG = {
        Einstellungen.Absender.STIFTUNG: {
            "name": "Deutsche Stiftung Krankheitsbedingte Mangelernährung", "strasse": "Waltrup 16",
            "plz": "48341", "ort": "Altenberge", "telefon": "0251 98 11 400", "fax": "0251 98 11 4019",
            "email": "kontakt@dsgme.org", "internet": "www.dsgme.org",
            "fusszeile": "rechtsfähige gemeinnützige und mildtätige Stiftung",
        },
        Einstellungen.Absender.GUG: {},
    }

    class Meta:
        verbose_name = "Absenderangaben"
        verbose_name_plural = "Absenderangaben"
        ordering = ["art"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Absenderangaben werden nicht gelöscht.")

    def __str__(self):
        return f"{self.get_art_display()}: {self.name}"

    @classmethod
    def alle(cls) -> dict:
        ergebnis = {}
        for art in Einstellungen.Absender.values:
            obj, _ = cls.objects.get_or_create(art=art, defaults=cls.VORBELEGUNG.get(art, {}))
            ergebnis[art] = obj
        return ergebnis


class Logo(models.Model):
    """Hochgeladenes Logo für Briefkopf und Seitenleiste. Das neueste gilt; ältere bleiben erhalten."""

    datei = models.CharField(max_length=255, unique=True, editable=False)
    mime = models.CharField(max_length=40, editable=False)
    sha256 = models.CharField(max_length=64, editable=False)
    breite = models.PositiveIntegerField(null=True, blank=True, editable=False)
    hoehe = models.PositiveIntegerField(null=True, blank=True, editable=False)
    hochgeladen_am = models.DateTimeField(auto_now_add=True)
    hochgeladen_von = models.ForeignKey("accounts.User", on_delete=models.PROTECT, null=True, related_name="+")

    class Meta:
        verbose_name = "Logo"
        verbose_name_plural = "Logos"
        ordering = ["-hochgeladen_am", "-id"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Logos werden nicht gelöscht.")

    @classmethod
    def aktuell(cls):
        return cls.objects.first()
