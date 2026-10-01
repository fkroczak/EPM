"""Patientenakte: Stammdaten, Gewichte, Kontakte, Termine, Dokumente."""
from datetime import timedelta
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max
from django.utils import timezone
from simple_history.models import HistoricalRecords

from stammdaten.models import Ansprechpartner, Auswahlwert, Einstellungen, Versorger

TESTNUMMER_AB = 9001


class AkteGesperrt(ValidationError):
    pass


class Patient(models.Model):
    class Geschlecht(models.TextChoices):
        WEIBLICH = "w", "weiblich"
        MAENNLICH = "m", "männlich"
        DIVERS = "d", "divers"
        UNBEKANNT = "", "unbekannt"

    class Nickelallergie(models.TextChoices):
        JA = "ja", "Ja"
        NEIN = "nein", "Nein"
        UNBEKANNT = "unbekannt", "unbekannt"

    class Abschlussanlass(models.TextChoices):
        VERSTORBEN = "verstorben", "Verstorben"
        THERAPIE_BEENDET = "therapie_beendet", "Therapie beendet"
        BETREUUNG_GEWECHSELT = "betreuung_gewechselt", "Betreuung gewechselt"

    nummer = models.PositiveIntegerField("Patientennummer", unique=True, editable=False)
    nachname = models.CharField(max_length=100)
    vorname = models.CharField(max_length=100)
    geburtsdatum = models.DateField()
    geschlecht = models.CharField(max_length=1, choices=Geschlecht.choices, blank=True, default="")

    strasse = models.CharField("Straße", max_length=150, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField(max_length=100, blank=True)
    telefon = models.CharField(max_length=50, blank=True)
    telefon2 = models.CharField("Telefon 2", max_length=50, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    krankenkasse = models.CharField(max_length=100, blank=True)
    hausarzt = models.CharField(max_length=150, blank=True)
    ueberweisung_durch = models.CharField("Überweisung / Kontaktaufnahme durch", max_length=200, blank=True)

    groesse_cm = models.DecimalField("Größe (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
    katheter = models.ForeignKey(
        Auswahlwert, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        limit_choices_to={"liste": Auswahlwert.Liste.KATHETER},
    )
    versorger = models.ForeignKey(Versorger, on_delete=models.PROTECT, null=True, blank=True, related_name="patienten")
    ansprechpartner = models.ForeignKey(
        Ansprechpartner, on_delete=models.PROTECT, null=True, blank=True, related_name="patienten"
    )
    nickelallergie = models.CharField(max_length=10, choices=Nickelallergie.choices, default=Nickelallergie.UNBEKANNT)

    # Lange formatierte Texte (bereinigtes HTML), versioniert über die Historie
    diagnose = models.TextField(blank=True)
    therapie = models.TextField(blank=True, help_text="Aktuelle Therapie und Therapieverlauf")
    empfehlung = models.TextField(blank=True)
    bemerkung = models.TextField(blank=True)

    abgeschlossen_am = models.DateField(null=True, blank=True)
    abschluss_anlass = models.CharField(max_length=30, choices=Abschlussanlass.choices, blank=True)
    abschluss_notiz = models.TextField(blank=True)

    ist_test = models.BooleanField("Testpatient", default=False, editable=False)

    angelegt_am = models.DateTimeField(auto_now_add=True)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    geaendert_am = models.DateTimeField(auto_now=True)

    history = HistoricalRecords(excluded_fields=["geaendert_am"])

    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patienten"
        ordering = ["nachname", "vorname"]
        indexes = [models.Index(fields=["nachname", "vorname"]), models.Index(fields=["geburtsdatum"])]
        constraints = [
            models.CheckConstraint(
                name="abschluss_vollstaendig",
                condition=(
                    models.Q(abgeschlossen_am__isnull=True, abschluss_anlass="")
                    | (models.Q(abgeschlossen_am__isnull=False) & ~models.Q(abschluss_anlass=""))
                ),
            ),
        ]

    def __str__(self):
        return f"{self.nachname}, {self.vorname} ({self.nummer})"

    def save(self, *args, **kwargs):
        if self.nummer is None:
            self.nummer = self.naechste_nummer(self.ist_test)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.ist_test:
            raise PermissionError("Patientenakten werden nicht gelöscht, sondern abgeschlossen.")
        return super().delete(*args, **kwargs)

    @staticmethod
    def naechste_nummer(ist_test: bool) -> int:
        if ist_test:
            hoechste = Patient.objects.filter(nummer__gte=TESTNUMMER_AB).aggregate(m=Max("nummer"))["m"]
            return max(hoechste or 0, TESTNUMMER_AB - 1) + 1
        hoechste = Patient.objects.filter(ist_test=False).aggregate(m=Max("nummer"))["m"] or 0
        nummer = hoechste + 1
        if nummer >= TESTNUMMER_AB and Patient.objects.filter(nummer=nummer).exists():
            nummer = Patient.objects.aggregate(m=Max("nummer"))["m"] + 1
        return nummer

    @property
    def ist_abgeschlossen(self) -> bool:
        return self.abgeschlossen_am is not None

    def pruefe_bearbeitbar(self):
        if self.ist_abgeschlossen:
            raise AkteGesperrt("Die Akte ist abgeschlossen und schreibgeschützt.")

    def clean(self):
        e = Einstellungen.aktuell()
        if self.groesse_cm is not None and not (e.groesse_min_cm <= self.groesse_cm <= e.groesse_max_cm):
            raise ValidationError({"groesse_cm": f"Größe muss zwischen {e.groesse_min_cm} und {e.groesse_max_cm} cm liegen."})
        if self.ansprechpartner_id and self.ansprechpartner.versorger_id != self.versorger_id:
            raise ValidationError({"ansprechpartner": "Ansprechpartner gehört nicht zum gewählten Versorger."})
        if self.geburtsdatum and self.geburtsdatum > timezone.localdate():
            raise ValidationError({"geburtsdatum": "Geburtsdatum liegt in der Zukunft."})

    # --- abgeleitete Werte für den Patientenkopf ---
    def letzte_messung(self):
        return self.gewichte.order_by("-gemessen_am", "-id").first()

    @property
    def bmi(self):
        m = self.letzte_messung()
        if not (m and self.groesse_cm):
            return None
        meter = self.groesse_cm / Decimal(100)
        return (m.gewicht_kg / (meter * meter)).quantize(Decimal("0.1"))

    def gewichtstrend(self):
        """Veränderung des Gewichts im eingestellten Zeitraum, siehe ``berechne_trend``."""
        messungen = list(self.gewichte.order_by("gemessen_am", "id").values_list("gemessen_am", "gewicht_kg"))
        return berechne_trend(messungen, Einstellungen.aktuell())


def berechne_trend(messungen, e):
    """Veränderung zur Messung, die etwa den eingestellten Zeitraum zurückliegt.

    ``messungen`` = [(datum, kg), …] aufsteigend sortiert. Liefert dict(prozent, von, bis, tage, warnung)
    oder None. Warnung bei Abnahme über der Schwelle; nur echte Messwerte, keine Glättung.
    """
    if not messungen:
        return None
    letzte_datum, letzte_kg = messungen[-1]
    zeitraum = 30 * e.gewicht_warnung_monate
    # Vergleich: jüngste Messung, die mindestens etwa den Zeitraum zurückliegt (±15 Tage Spielraum)
    stichtag = letzte_datum - timedelta(days=zeitraum - 15)
    frueher = [m for m in messungen if m[0] <= stichtag]
    if frueher:
        vergleich = frueher[-1]
    else:
        aeltere = [m for m in messungen if m[0] < letzte_datum]
        vergleich = aeltere[0] if aeltere else None
    if not vergleich or vergleich[1] == 0:
        return None
    prozent = ((letzte_kg - vergleich[1]) / vergleich[1] * 100).quantize(Decimal("0.1"))
    tage = (letzte_datum - vergleich[0]).days
    warnung = prozent <= -e.gewicht_warnung_prozent and tage <= zeitraum + 45
    return {"prozent": prozent, "von": vergleich[0], "bis": letzte_datum, "tage": tage, "warnung": warnung,
            "vergleich_kg": vergleich[1], "aktuell_kg": letzte_kg}


class AktenEintrag(models.Model):
    """Basis für alles, was zu einer Akte gehört: gesperrt, wenn die Akte abgeschlossen ist."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.patient.pruefe_bearbeitbar()
        super().save(*args, **kwargs)


class Gewichtsmessung(AktenEintrag):
    class Quelle(models.TextChoices):
        TELEFONISCH = "telefonisch", "telefonisch"
        AMBULANZ = "ambulanz", "Ambulanz/Praxis"
        VERSORGER = "versorger", "Versorger"
        ARZTBRIEF = "arztbrief", "Arztbrief"
        ALTSYSTEM = "altsystem", "Altsystem"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="gewichte")
    gewicht_kg = models.DecimalField("Gewicht (kg)", max_digits=5, decimal_places=1)
    gemessen_am = models.DateField(default=timezone.localdate)
    datum_ungenau = models.BooleanField(default=False)
    quelle = models.CharField(max_length=20, choices=Quelle.choices, default=Quelle.TELEFONISCH)
    notiz = models.CharField(max_length=300, blank=True)
    erfasst_am = models.DateTimeField(auto_now_add=True)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Gewichtsmessung"
        verbose_name_plural = "Gewichtsmessungen"
        ordering = ["-gemessen_am", "-id"]
        indexes = [models.Index(fields=["patient", "gemessen_am"])]

    def clean(self):
        e = Einstellungen.aktuell()
        if self.gewicht_kg is not None and not (e.gewicht_min_kg <= self.gewicht_kg <= e.gewicht_max_kg):
            raise ValidationError({"gewicht_kg": f"Gewicht muss zwischen {e.gewicht_min_kg} und {e.gewicht_max_kg} kg liegen."})
        if self.gemessen_am and self.gemessen_am > timezone.localdate():
            raise ValidationError({"gemessen_am": "Datum liegt in der Zukunft."})


class Kontakt(AktenEintrag):
    """Protokoll der Kommunikation. Nach dem Speichern unveränderlich; Korrektur nur per Storno."""

    STORNO_FELDER = {"storniert_am", "storniert_von", "storno_grund"}

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="kontakte")
    zeitpunkt = models.DateTimeField(default=timezone.now)
    art = models.ForeignKey(
        Auswahlwert, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        limit_choices_to={"liste": Auswahlwert.Liste.KONTAKTART},
    )
    text = models.TextField()
    erfasst_am = models.DateTimeField(auto_now_add=True)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    storniert_am = models.DateTimeField(null=True, blank=True)
    storniert_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    storno_grund = models.CharField(max_length=300, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Kontakt"
        verbose_name_plural = "Kontakte"
        ordering = ["-zeitpunkt", "-id"]
        indexes = [models.Index(fields=["patient", "zeitpunkt"])]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("update_fields"):
            raise PermissionError("Kontakte sind nach dem Speichern unveränderlich (nur Storno möglich).")
        if kwargs.get("update_fields") and not set(kwargs["update_fields"]) <= self.STORNO_FELDER:
            raise PermissionError("An einem Kontakt dürfen nur die Storno-Felder gesetzt werden.")
        super().save(*args, **kwargs)

    def stornieren(self, benutzer, grund: str):
        if self.storniert_am:
            raise ValidationError("Kontakt ist bereits storniert.")
        if not grund.strip():
            raise ValidationError({"storno_grund": "Bitte einen Grund angeben."})
        self.storniert_am = timezone.now()
        self.storniert_von = benutzer
        self.storno_grund = grund.strip()
        self.save(update_fields=["storniert_am", "storniert_von", "storno_grund"])


class Termin(AktenEintrag):
    class Art(models.TextChoices):
        PRAXISTERMIN = "praxistermin", "Praxistermin"
        RUECKRUF = "rueckruf", "Rückruf"
        WIEDERVORLAGE = "wiedervorlage", "Wiedervorlage"
        SONSTIGES = "sonstiges", "Sonstiges"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="termine")
    art = models.CharField(max_length=20, choices=Art.choices, default=Art.WIEDERVORLAGE)
    faellig_am = models.DateField()
    uhrzeit = models.TimeField(null=True, blank=True)
    ort = models.ForeignKey(
        Auswahlwert, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        limit_choices_to={"liste": Auswahlwert.Liste.TERMINORT}, verbose_name="Terminort",
    )
    bei = models.CharField("bei/Ort (Freitext)", max_length=150, blank=True,
                           help_text="Ergänzung zum Terminort, z. B. Raum oder Ansprechperson")
    titel = models.CharField(max_length=200)
    notiz = models.TextField(blank=True)
    kontakt = models.ForeignKey(Kontakt, on_delete=models.SET_NULL, null=True, blank=True, related_name="termine")
    erledigt_am = models.DateTimeField(null=True, blank=True)
    erledigt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    angelegt_am = models.DateTimeField(auto_now_add=True)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Termin"
        verbose_name_plural = "Termine"
        ordering = ["faellig_am", "uhrzeit", "id"]
        indexes = [models.Index(fields=["faellig_am", "erledigt_am"])]

    def erledigen(self, benutzer):
        self.erledigt_am = timezone.now()
        self.erledigt_von = benutzer
        self.save()


def dokument_pfad(patient: Patient, originalname: str) -> str:
    endung = "".join(c for c in (originalname.rsplit(".", 1)[-1] if "." in originalname else "") if c.isalnum())[:10]
    return f"{patient.nummer}/{uuid.uuid4().hex}{'.' + endung.lower() if endung else ''}"


class Dokument(AktenEintrag):
    """Datei im Dateisystem (EPM_DOKUMENTE/<nummer>/...), Metadaten und Prüfsumme in der DB."""

    class Herkunft(models.TextChoices):
        UPLOAD = "upload", "Hochgeladen"
        ALTSYSTEM = "altsystem", "Altsystem"
        SYSTEM = "system", "Von EPM erzeugt"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="dokumente")
    typ = models.ForeignKey(
        Auswahlwert, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        limit_choices_to={"liste": Auswahlwert.Liste.DOKUMENTTYP},
    )
    titel = models.CharField(max_length=200)
    datum = models.DateField("Dokumentdatum", null=True, blank=True)
    datei = models.CharField(max_length=255, unique=True, editable=False)
    originalname = models.CharField(max_length=255, editable=False)
    mime = models.CharField(max_length=100, editable=False)
    groesse = models.PositiveBigIntegerField(editable=False)
    sha256 = models.CharField(max_length=64, editable=False)
    herkunft = models.CharField(max_length=20, choices=Herkunft.choices, default=Herkunft.UPLOAD, editable=False)

    class DatumQuelle(models.TextChoices):
        EINGABE = "eingabe", "Eingabe"
        PDF = "pdf", "PDF-Metadaten"
        EXIF = "exif", "EXIF"
        DATEIDATUM = "dateidatum", "Dateidatum (keine Metadaten)"

    datum_quelle = models.CharField(max_length=20, choices=DatumQuelle.choices, default=DatumQuelle.EINGABE)
    typ_geprueft = models.BooleanField(default=True, help_text="Bei Altdokumenten erst nach Prüfung von Typ und Datum")
    notiz = models.TextField(blank=True)
    ausgeblendet = models.BooleanField(default=False, help_text="Ausgeblendet statt gelöscht")
    hochgeladen_am = models.DateTimeField(auto_now_add=True)
    hochgeladen_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Dokument"
        verbose_name_plural = "Dokumente"
        ordering = ["-datum", "-hochgeladen_am"]

    @property
    def pfad(self):
        return settings.EPM_DOKUMENTE / self.datei
