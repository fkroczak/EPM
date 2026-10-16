"""Patientenakte: Stammdaten, Gewichte, Kontakte, Termine, Dokumente."""
from datetime import timedelta
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Max
from django.utils import timezone
from simple_history.models import HistoricalRecords

from stammdaten.models import Ansprechpartner, Arzt, Auswahlwert, Einstellungen, Versorger

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
    # Versichertendaten (Wunsch 06.10.2026, F118): Für die Auseinandersetzungen mit den Kassen reicht der Name
    # der Kasse nicht. „krankenkasse“ behält seinen Spaltennamen (keine Datenwanderung) und heißt in der
    # Oberfläche „Versicherung“; Art und Versichertennummer kommen dazu.
    class Versicherungsart(models.TextChoices):
        GKV = "gkv", "GKV (gesetzlich)"
        PKV = "pkv", "PKV (privat)"
        SELBSTZAHLER = "selbstzahler", "Selbstzahler"
        SONSTIGE = "sonstige", "Sonstige"
        UNBEKANNT = "", "nicht erfasst"

    versicherungsart = models.CharField("Versicherungsart", max_length=20, choices=Versicherungsart.choices,
                                        blank=True, default="")
    krankenkasse = models.CharField("Versicherung", max_length=100, blank=True)
    versichertennummer = models.CharField("Versichertennummer", max_length=50, blank=True)
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
    # „kein“ = bewusst keiner (Festlegung 01.10.2026), leer = noch nicht erfasst (mit Hinweis wie Nickelallergie „unbekannt“)
    kein_katheter = models.BooleanField("Kein Katheter", default=False)
    kein_versorger = models.BooleanField("Kein Versorger", default=False)
    # Kein Infusionsplan nötig (Ergänzung zur Fehlerliste 02.10.2026): Jede Akte in Betreuung braucht einen
    # freigegebenen Plan – sonst erscheint ein Hinweis. Wer bestätigt, dass dieser Patient keinen braucht, unterdrückt
    # den Hinweis und die Warnung „Plan älter als …“. Mit der nächsten Freigabe eines Plans gilt wieder „Plan nötig“.
    kein_plan = models.BooleanField("Kein Infusionsplan nötig", default=False)
    kein_plan_grund = models.CharField("Grund (kein Infusionsplan)", max_length=300, blank=True)
    kein_plan_am = models.DateTimeField(null=True, blank=True)
    kein_plan_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")

    # Lange formatierte Texte (bereinigtes HTML), versioniert über die Historie
    diagnose = models.TextField(blank=True)
    therapie = models.TextField(blank=True, help_text="Aktuelle Therapie und Therapieverlauf")
    empfehlung = models.TextField(blank=True)
    bemerkung = models.TextField(blank=True)

    abgeschlossen_am = models.DateField(null=True, blank=True)
    abschluss_anlass = models.CharField(max_length=30, choices=Abschlussanlass.choices, blank=True)
    abschluss_notiz = models.TextField(blank=True)

    ist_test = models.BooleanField("Testpatient", default=False, editable=False)

    # Datenschutz (Festlegung 02.10.2026): Aufbewahrung = Abschluss + eingestellte Jahre; im Einzelfall länger
    # (mit Grund). Verarbeitung einschränken (Art. 18 DSGVO): Akte nur noch mit begründeter Einsicht lesbar.
    aufbewahrung_bis = models.DateField("Aufbewahrung verlängert bis", null=True, blank=True)
    aufbewahrung_grund = models.CharField("Grund der längeren Aufbewahrung", max_length=300, blank=True)
    eingeschraenkt_am = models.DateTimeField("Verarbeitung eingeschränkt am", null=True, blank=True)
    eingeschraenkt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                           related_name="+")
    einschraenkung_grund = models.CharField("Grund der Einschränkung", max_length=300, blank=True)

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
            models.CheckConstraint(name="kein_katheter_ohne_katheter",
                                   condition=models.Q(kein_katheter=False) | models.Q(katheter__isnull=True)),
            models.CheckConstraint(name="kein_versorger_ohne_versorger",
                                   condition=models.Q(kein_versorger=False)
                                   | models.Q(versorger__isnull=True, ansprechpartner__isnull=True)),
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
        # die Nummer einer gelöschten Akte wird nicht neu vergeben (sie steht im Löschprotokoll)
        geloescht = Loeschprotokoll.objects.filter(ist_test=False).aggregate(m=Max("nummer"))["m"] or 0
        nummer = max(hoechste, geloescht) + 1
        if nummer >= TESTNUMMER_AB and Patient.objects.filter(nummer=nummer).exists():
            nummer = Patient.objects.aggregate(m=Max("nummer"))["m"] + 1
        return nummer

    @property
    def ist_abgeschlossen(self) -> bool:
        return self.abgeschlossen_am is not None

    @property
    def ist_eingeschraenkt(self) -> bool:
        return self.eingeschraenkt_am is not None

    def aufbewahrung(self, jahre: int | None = None, letzter_kontakt=False) -> dict:
        """Aufbewahrungsfrist der Akte: läuft ab dem Abschluss (ohne Abschluss keine Frist).

        ``beginn`` = Abschlussdatum – oder der Tag des letzten Kontakts, wenn der später liegt (ein versehentlich zu
        früh eingetragenes Abschlussdatum macht die Akte so nicht vorzeitig löschbar). ``regulaer_bis`` = Beginn +
        eingestellte Jahre, ``bis`` = spätestes Datum aus regulärer Frist und einer Verlängerung im Einzelfall,
        ``abgelaufen`` = die Akte darf gelöscht werden. ``letzter_kontakt``: Zeitpunkt, falls schon bekannt
        (Listen), sonst wird er gelesen."""
        if jahre is None:
            jahre = Einstellungen.aktuell().aufbewahrung_jahre
        beginn = self.abgeschlossen_am
        if beginn:
            if letzter_kontakt is False:
                letzter_kontakt = self.kontakte.filter(storniert_am__isnull=True).aggregate(m=Max("zeitpunkt"))["m"]
            if letzter_kontakt and timezone.localtime(letzter_kontakt).date() > beginn:
                beginn = timezone.localtime(letzter_kontakt).date()
        regulaer = plus_jahre(beginn, jahre) if beginn else None
        bis = regulaer
        if regulaer and self.aufbewahrung_bis and self.aufbewahrung_bis > regulaer:
            bis = self.aufbewahrung_bis
        return {
            "jahre": jahre, "beginn": beginn, "regulaer_bis": regulaer, "verlaengert_bis": self.aufbewahrung_bis,
            "grund": self.aufbewahrung_grund, "bis": bis,
            "abgelaufen": bool(bis and bis < timezone.localdate()),
        }

    def pruefe_bearbeitbar(self):
        if self.ist_abgeschlossen:
            raise AkteGesperrt("Die Akte ist abgeschlossen und schreibgeschützt.")

    def clean(self):
        e = Einstellungen.aktuell()
        if self.groesse_cm is not None and not (e.groesse_min_cm <= self.groesse_cm <= e.groesse_max_cm):
            raise ValidationError({"groesse_cm": f"Größe muss zwischen {e.groesse_min_cm} und {e.groesse_max_cm} cm liegen."})
        if self.ansprechpartner_id and self.ansprechpartner.versorger_id != self.versorger_id:
            raise ValidationError({"ansprechpartner": "Dieser Ansprechpartner gehört nicht zum gewählten Versorger. "
                                                      "Bitte einen passenden wählen."})
        if self.geburtsdatum and self.geburtsdatum > timezone.localdate():
            raise ValidationError({"geburtsdatum": "Geburtsdatum liegt in der Zukunft."})
        if self.kein_katheter and self.katheter_id:
            raise ValidationError({"katheter": "Entweder einen Katheter wählen oder „kein Katheter“."})
        if self.kein_versorger and (self.versorger_id or self.ansprechpartner_id):
            raise ValidationError({"versorger": "Entweder einen Versorger wählen oder „kein Versorger“."})

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


def plus_jahre(tag, jahre: int):
    """Datum + Jahre; der 29. Februar wird in Jahren ohne Schalttag zum 28. Februar."""
    try:
        return tag.replace(year=tag.year + jahre)
    except ValueError:
        return tag.replace(year=tag.year + jahre, day=28)


def plus_monate(tag, monate: int):
    """Datum + Monate; gibt es den Tag im Zielmonat nicht (31. → Februar), gilt der letzte Tag des Monats."""
    import calendar

    monat = tag.month - 1 + monate
    jahr = tag.year + monat // 12
    monat = monat % 12 + 1
    return tag.replace(year=jahr, month=monat, day=min(tag.day, calendar.monthrange(jahr, monat)[1]))


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


class PatientFirma(models.Model):
    """Eine Akte gehört einer oder beiden Firmen (Anforderung 11.10.2026). Sichtbar ist sie in jeder Firma, der sie
    zugeordnet ist – dort mit allen Einträgen. Die zweite Firma kommt nur mit einer erfassten Einwilligung
    (``Erklaerung.Art.FIRMEN``) dazu; wer wann zugeordnet hat, steht hier, im Verlauf und im Audit-Log."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="firmenzuordnung")
    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, related_name="+")
    zugeordnet_am = models.DateTimeField(auto_now_add=True)
    zugeordnet_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Zuordnung zu einer Firma"
        verbose_name_plural = "Zuordnungen zu Firmen"
        constraints = [models.UniqueConstraint(fields=["patient", "firma"], name="patient_einmal_je_firma")]

    def __str__(self):
        return f"{self.patient} · {self.firma}"


class AktenEintrag(models.Model):
    """Basis für alles, was zu einer Akte gehört: gesperrt, wenn die Akte abgeschlossen ist.

    Jeder Eintrag merkt sich, in welcher Firma er erfasst wurde (Anforderung 11.10.2026): Eine Akte, die DSKM und
    Regeneration Clinic gemeinsam betreuen, zeigt beiden alles – mit der Herkunft je Eintrag."""

    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                              verbose_name="erfasst in Firma")

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.patient.pruefe_bearbeitbar()
        if self._state.adding and self.firma_id is None:
            from epm.firma import aktive_firma

            firma = aktive_firma()
            if firma is not None:
                self.firma = firma
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
    # Ausblenden mit „×“ im Kalender (Wunsch 08.10.2026, F142) – wie die Hinweise der Akte (F119): für 3, 6 oder 12
    # Monate oder „nicht mehr nötig“, mit Grund, Person und Zeitpunkt; jede Fassung steht im Verlauf der Akte
    ausgeblendet_bis = models.DateField("ausgeblendet bis", null=True, blank=True)
    ausgeblendet_dauerhaft = models.BooleanField("ausgeblendet (nicht mehr nötig)", default=False)
    ausblende_grund = models.CharField("Grund des Ausblendens", max_length=300, blank=True)
    ausgeblendet_am = models.DateTimeField(null=True, blank=True)
    ausgeblendet_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # Terminbestätigung (F185): wann zuletzt eine Bestätigung als PDF oder E-Mail erstellt wurde. Wird der Termin
    # verschoben (Datum, Uhrzeit, Ort), gilt die alte Bestätigung nicht mehr und das Feld wird geleert.
    bestaetigung_am = models.DateTimeField("Terminbestätigung erstellt am", null=True, blank=True)
    bestaetigung_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Bestaetigungsweg(models.TextChoices):
        SCHREIBEN = "", "PDF oder E-Mail aus EPM"
        TELEFONISCH = "telefonisch", "telefonisch"
        PERSOENLICH = "persoenlich", "persönlich"
        ANDERWEITIG = "anderweitig", "anderweitig"

    # Wunsch 11.10.2026: „Bestätigung fehlt“ wegklicken, wenn der Termin schon auf anderem Weg bestätigt ist
    bestaetigung_weg = models.CharField("Terminbestätigung auf welchem Weg", max_length=12, blank=True, default="",
                                        choices=Bestaetigungsweg.choices)

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

    @property
    def ist_ausgeblendet(self) -> bool:
        """Heute ausgeblendet? (Frist noch nicht abgelaufen oder „nicht mehr nötig“)"""
        return self.ausgeblendet_dauerhaft or (self.ausgeblendet_bis is not None
                                               and self.ausgeblendet_bis >= timezone.localdate())


def sichtbare_termine(qs):
    """Termine ohne die heute ausgeblendeten (F142): für Kalender, Startseite und den nächsten Termin der Akte."""
    return qs.exclude(ausgeblendet_dauerhaft=True).exclude(ausgeblendet_bis__gte=timezone.localdate())


class Bezugsperson(AktenEintrag):
    """Weitere Ansprechperson des Patienten (Mutter, Vater, Betreuer/in …), 1:n.

    Nicht mehr aktuelle Personen werden auf „aktiv = False“ gesetzt statt gelöscht; jede Fassung steht im
    Verlauf der Akte. „Auskunft erlaubt“ = Schweigepflichtentbindung liegt vor (im Patientenkopf sichtbar)."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="bezugspersonen")
    beziehung = models.ForeignKey(
        Auswahlwert, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        limit_choices_to={"liste": Auswahlwert.Liste.BEZIEHUNG},
    )
    name = models.CharField(max_length=150)
    telefon = models.CharField(max_length=50, blank=True)
    mobil = models.CharField(max_length=50, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    strasse = models.CharField("Straße", max_length=150, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField(max_length=100, blank=True)
    notiz = models.TextField(blank=True)
    auskunft_erlaubt = models.BooleanField("Auskunft erlaubt (Schweigepflichtentbindung liegt vor)", default=False)
    aktiv = models.BooleanField(default=True)
    angelegt_am = models.DateTimeField(auto_now_add=True)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Bezugsperson"
        verbose_name_plural = "Bezugspersonen"
        ordering = ["-aktiv", "-auskunft_erlaubt", "name", "id"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Bezugspersonen werden nicht gelöscht, sondern als „nicht mehr aktuell“ markiert.")

    def __str__(self):
        return self.name


class PatientArzt(AktenEintrag):
    """Zuordnung eines Arztes aus der gemeinsamen Ärzteliste zum Patienten, mit Rolle (1:n).
    Endet eine Zuständigkeit, wird sie auf „aktiv = False“ gesetzt; der Verlauf behält alle Fassungen."""

    class Rolle(models.TextChoices):
        HAUSARZT = "hausarzt", "Hausarzt"
        FACHARZT = "facharzt", "Facharzt"
        UEBERWEISEND = "ueberweisend", "Überweisend"
        KLINIK = "klinik", "Klinik"
        SONSTIGE = "sonstige", "Sonstige"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="aerzte")
    arzt = models.ForeignKey(Arzt, on_delete=models.PROTECT, related_name="zuordnungen")
    rolle = models.CharField(max_length=20, choices=Rolle.choices, default=Rolle.HAUSARZT)
    notiz = models.CharField(max_length=300, blank=True)
    aktiv = models.BooleanField(default=True)
    angelegt_am = models.DateTimeField(auto_now_add=True)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Arzt des Patienten"
        verbose_name_plural = "Ärzte des Patienten"
        ordering = ["-aktiv", "rolle", "id"]
        constraints = [
            models.UniqueConstraint(fields=["patient", "arzt", "rolle"], condition=models.Q(aktiv=True),
                                    name="arzt_je_rolle_einmal"),
        ]

    def delete(self, *args, **kwargs):
        raise PermissionError("Zuordnungen werden nicht gelöscht, sondern als „nicht mehr zuständig“ markiert.")

    def __str__(self):
        return f"{self.get_rolle_display()}: {self.arzt}"


class Diagnose(AktenEintrag):
    """Einzelne Diagnose der Akte mit ICD-Code und Zusatzkennzeichen (Wunsch 06.10.2026, F117).

    Anzeige wie gewünscht: „Kurzdarmsyndrom [K91.2 G]“. Das Zusatzkennzeichen ist Pflicht – ohne es sagt ein
    ICD-Code nicht, ob die Diagnose gesichert ist oder nur ein Verdacht. Nicht mehr zutreffende Diagnosen
    werden auf „aktiv = False“ gesetzt statt gelöscht; jede Fassung steht im Verlauf der Akte.

    Das lange Freitextfeld ``Patient.diagnose`` bleibt daneben bestehen (U51)."""

    class Kennzeichen(models.TextChoices):
        GESICHERT = "G", "G – gesichert"
        VERDACHT = "V", "V – Verdacht auf"
        ZUSTAND = "Z", "Z – Zustand nach"
        AUSSCHLUSS = "A", "A – Ausschluss von"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="diagnosen")
    bezeichnung = models.CharField(max_length=200)
    icd_code = models.CharField("ICD-Code", max_length=10, help_text="z. B. K91.2")
    kennzeichen = models.CharField("Zusatzkennzeichen", max_length=1, choices=Kennzeichen.choices,
                                   default=Kennzeichen.GESICHERT)
    seit = models.DateField("besteht seit", null=True, blank=True)
    notiz = models.CharField(max_length=300, blank=True)
    reihenfolge = models.PositiveSmallIntegerField(default=100)
    aktiv = models.BooleanField(default=True)
    beendet_am = models.DateField(null=True, blank=True)
    angelegt_am = models.DateTimeField(auto_now_add=True)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Diagnose"
        verbose_name_plural = "Diagnosen"
        ordering = ["-aktiv", "reihenfolge", "bezeichnung", "id"]
        indexes = [models.Index(fields=["patient", "aktiv"], name="diagnose_patient_aktiv")]

    def delete(self, *args, **kwargs):
        raise PermissionError("Diagnosen werden nicht gelöscht, sondern als „nicht mehr zutreffend“ markiert.")

    @property
    def anzeige(self) -> str:
        return f"{self.bezeichnung} [{self.icd_code}{self.kennzeichen}]"


    def clean(self):
        import re

        from stammdaten.models import ICD_MUSTER

        self.icd_code = (self.icd_code or "").strip().upper()
        fehler = {}
        if not (self.bezeichnung or "").strip():
            fehler["bezeichnung"] = "Bitte die Bezeichnung angeben."
        if not re.match(ICD_MUSTER, self.icd_code):
            fehler["icd_code"] = ("ICD-Code wie „K91.2“ angeben (Buchstabe, zwei Ziffern, bei Bedarf Punkt und "
                                  "ein bis zwei Stellen).")
        if self.kennzeichen not in self.Kennzeichen.values:
            fehler["kennzeichen"] = "Bitte G (gesichert), V (Verdacht), Z (Zustand nach) oder A (Ausschluss) wählen."
        heute = timezone.localdate()
        if self.seit and self.seit > heute:
            fehler["seit"] = "Das Datum liegt in der Zukunft."
        if self.beendet_am and self.beendet_am > heute:
            fehler["beendet_am"] = "Das Datum liegt in der Zukunft."
        if self.beendet_am and self.seit and self.beendet_am < self.seit:
            fehler["beendet_am"] = "Das Ende liegt vor dem Beginn."
        if fehler:
            raise ValidationError(fehler)

    def save(self, *args, **kwargs):
        if not self.aktiv and self.beendet_am is None:
            self.beendet_am = timezone.localdate()
        if self.aktiv:
            self.beendet_am = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.anzeige


class Medikament(AktenEintrag):
    """Ein Medikament im Medikamentenplan der Akte (Wunsch 11.10.2026), aufgebaut wie der bundeseinheitliche
    Medikationsplan: Wirkstoff, Handelsname, Stärke, Form, Dosierung morgens – mittags – abends – zur Nacht, Einheit,
    Hinweise und Grund. Was nicht in das Schema passt („1× wöchentlich montags“), steht unter ``dosierung_frei``.

    Bedarfsmedikation (``bedarf``) steht im Plan in einem eigenen Abschnitt. Nicht mehr eingenommene Medikamente
    werden „abgesetzt“ (``aktiv = False`` mit Datum und Grund), nie gelöscht; jede Fassung steht im Verlauf der Akte."""

    # Vorschläge für die Darreichungsform (Freitext bleibt erlaubt)
    FORMEN = ("Tablette", "Filmtablette", "Kapsel", "Brausetablette", "Tropfen", "Saft", "Pulver", "Injektion",
              "Infusion", "Pflaster", "Spray", "Zäpfchen", "Salbe")
    # Vorschläge für die Einheit
    EINHEITEN = ("Stück", "ml", "Tropfen", "IE", "Hub", "Beutel", "mg", "g")

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="medikamente")
    wirkstoff = models.CharField(max_length=200)
    handelsname = models.CharField(max_length=200, blank=True)
    staerke = models.CharField("Stärke", max_length=60, blank=True, help_text="z. B. 40 mg")
    darreichungsform = models.CharField(max_length=60, blank=True, help_text="z. B. Tablette, Kapsel, Tropfen")
    morgens = models.CharField(max_length=10, blank=True, help_text="z. B. 1, ½, 0")
    mittags = models.CharField(max_length=10, blank=True)
    abends = models.CharField(max_length=10, blank=True)
    nachts = models.CharField("zur Nacht", max_length=10, blank=True)
    dosierung_frei = models.CharField("Dosierung (frei)", max_length=120, blank=True,
                                      help_text="wenn das Schema nicht passt, z. B. „1× wöchentlich montags“")
    einheit = models.CharField(max_length=30, blank=True, help_text="z. B. Stück, ml, Tropfen, IE, Hub")
    bedarf = models.BooleanField("bei Bedarf", default=False)
    hinweise = models.CharField(max_length=300, blank=True)
    grund = models.CharField("Behandlungsgrund", max_length=200, blank=True)
    seit = models.DateField(null=True, blank=True)
    aktiv = models.BooleanField(default=True)
    abgesetzt_am = models.DateField(null=True, blank=True)
    absetzgrund = models.CharField(max_length=200, blank=True)
    reihenfolge = models.PositiveSmallIntegerField(default=100)
    angelegt_am = models.DateTimeField(auto_now_add=True)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    DOSIERFELDER = ("morgens", "mittags", "abends", "nachts")

    class Meta:
        verbose_name = "Medikament"
        verbose_name_plural = "Medikamente"
        ordering = ["-aktiv", "bedarf", "reihenfolge", "wirkstoff", "id"]
        indexes = [models.Index(fields=["patient", "aktiv"], name="medikament_patient_aktiv")]

    def delete(self, *args, **kwargs):
        raise PermissionError("Medikamente werden nicht gelöscht, sondern abgesetzt.")

    @property
    def schema(self) -> str:
        """„1 – 0 – 1 – 0“ wie im Medikationsplan; leer, wenn nur frei dosiert ist."""
        werte = [getattr(self, f) for f in self.DOSIERFELDER]
        if not any(w.strip() for w in werte):
            return ""
        return " – ".join((w.strip() or "0") for w in werte)

    @property
    def dosierung(self) -> str:
        """Schema und/oder freie Dosierung in einer Zeile (Verlauf, Karteikarte)."""
        return " · ".join(t for t in (self.schema, self.dosierung_frei.strip()) if t)

    def clean(self):
        fehler = {}
        for feld in ("wirkstoff", "handelsname", "staerke", "darreichungsform", "dosierung_frei", "einheit",
                     "hinweise", "grund", "absetzgrund", *self.DOSIERFELDER):
            setattr(self, feld, (getattr(self, feld) or "").strip())
        if not self.wirkstoff:
            fehler["wirkstoff"] = "Bitte den Wirkstoff angeben."
        if not self.bedarf and not self.dosierung_frei and not any(getattr(self, f) for f in self.DOSIERFELDER):
            fehler["dosierung_frei"] = ("Bitte die Dosierung angeben (morgens, mittags, abends, zur Nacht oder frei) – "
                                        "oder „bei Bedarf“ wählen.")
        heute = timezone.localdate()
        if self.seit and self.seit > heute:
            fehler["seit"] = "Das Datum liegt in der Zukunft."
        if not self.aktiv and self.abgesetzt_am is None:
            self.abgesetzt_am = heute
        if self.abgesetzt_am and self.abgesetzt_am > heute:
            fehler["abgesetzt_am"] = "Das Datum liegt in der Zukunft."
        if self.abgesetzt_am and self.seit and self.abgesetzt_am < self.seit:
            fehler["abgesetzt_am"] = "Das Absetzen liegt vor dem Beginn."
        if fehler:
            raise ValidationError(fehler)

    def save(self, *args, **kwargs):
        # abgesetzt ohne Datum: heute; wieder angesetzt: Datum und Grund des Absetzens entfallen
        if not self.aktiv and self.abgesetzt_am is None:
            self.abgesetzt_am = timezone.localdate()
        if self.aktiv:
            self.abgesetzt_am = None
            self.absetzgrund = ""
        super().save(*args, **kwargs)

    def __str__(self):
        return " ".join(t for t in (self.wirkstoff, self.staerke) if t)


class Katheter(AktenEintrag):
    """Ein Katheter in der Katheter-Historie der Akte (F192, Wunsch 15.10.2026): Typ (Auswahlliste „Katheter“ wie
    ``Patient.katheter``), Lage/Zugang, Anlagedatum, Entfernt am mit Grund (Auswahlliste „Katheter:
    Entfernungsgrund“) und Notiz; je Katheter beliebig viele Komplikationen (``KatheterKomplikation``).

    Ein noch liegender Katheter hat kein ``entfernt_am``. Falsch Erfasstes wird nicht gelöscht, sondern mit
    ``aktiv = False`` zurückgenommen (zählt dann in keiner Kennzahl und steht nicht mehr in der Zeitachse); jede Fassung
    steht im Verlauf der Akte.

    Kerndaten (Festlegung vom 16.10.2026): Wird ein neuer Katheter ohne „Entfernt am“ angelegt, übernimmt die API
    (``KatheterViewSet.perform_create``) seinen Typ in ``Patient.katheter`` und setzt ``kein_katheter`` zurück. Ein
    noch offener vorheriger Katheter wird dabei NICHT automatisch beendet – es gibt nur den Hinweis „Vorheriger
    Katheter noch nicht als entfernt eingetragen“."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="katheter_eintraege")
    typ = models.ForeignKey(
        Auswahlwert, on_delete=models.PROTECT, related_name="+", verbose_name="Katheter-Typ",
        limit_choices_to={"liste": Auswahlwert.Liste.KATHETER},
    )
    lage = models.CharField("Lage/Zugang", max_length=200, blank=True, help_text="z. B. „V. subclavia rechts“")
    anlage_am = models.DateField("Anlagedatum")
    entfernt_am = models.DateField("Entfernt am", null=True, blank=True)
    entfernungsgrund = models.ForeignKey(
        Auswahlwert, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        verbose_name="Entfernungsgrund", limit_choices_to={"liste": Auswahlwert.Liste.KATHETER_ENTFERNUNG},
    )
    notiz = models.CharField(max_length=500, blank=True)
    aktiv = models.BooleanField(default=True)
    angelegt_am = models.DateTimeField(auto_now_add=True)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Katheter"
        verbose_name_plural = "Katheter-Historie"
        ordering = ["-anlage_am", "-id"]
        indexes = [models.Index(fields=["patient", "anlage_am"], name="katheter_patient_anlage")]
        constraints = [
            models.CheckConstraint(name="katheter_entfernt_nach_anlage",
                                   condition=models.Q(entfernt_am__isnull=True)
                                   | models.Q(entfernt_am__gte=models.F("anlage_am"))),
        ]

    def delete(self, *args, **kwargs):
        raise PermissionError("Katheter werden nicht gelöscht, sondern als falsch erfasst zurückgenommen (aktiv = False).")

    @property
    def liegt(self) -> bool:
        return self.entfernt_am is None

    def liegedauer_tage(self, heute=None) -> int | None:
        """Liegedauer in Tagen: Entfernt am (bzw. heute) minus Anlagedatum – der Anlagetag zählt nicht mit
        (Zählweise siehe ``katheter_kennzahlen``)."""
        if self.anlage_am is None:
            return None
        ende = self.entfernt_am or heute or timezone.localdate()
        return max(0, (ende - self.anlage_am).days)

    def clean(self):
        fehler = {}
        self.lage = (self.lage or "").strip()
        self.notiz = (self.notiz or "").strip()
        heute = timezone.localdate()
        if not self.typ_id:
            fehler["typ"] = "Bitte den Katheter-Typ wählen."
        elif self.typ.liste != Auswahlwert.Liste.KATHETER:
            fehler["typ"] = "Ungültiger Wert für die Liste „Katheter“."
        if self.anlage_am is None:
            fehler["anlage_am"] = "Bitte das Anlagedatum angeben."
        elif self.anlage_am > heute:
            fehler["anlage_am"] = "Das Anlagedatum liegt in der Zukunft."
        if self.entfernt_am is not None:
            if self.entfernt_am > heute:
                fehler["entfernt_am"] = "Das Datum „Entfernt am“ liegt in der Zukunft."
            elif self.anlage_am is not None and self.entfernt_am < self.anlage_am:
                fehler["entfernt_am"] = "„Entfernt am“ liegt vor dem Anlagedatum."
        if self.entfernungsgrund_id:
            if self.entfernungsgrund.liste != Auswahlwert.Liste.KATHETER_ENTFERNUNG:
                fehler["entfernungsgrund"] = "Ungültiger Wert für die Liste „Entfernungsgrund“."
            elif self.entfernt_am is None:
                fehler["entfernungsgrund"] = "Ein Entfernungsgrund gehört zu einem entfernten Katheter – bitte auch " \
                                             "„Entfernt am“ angeben."
        # Bereits erfasste Komplikationen müssen in der (geänderten) Liegezeit bleiben
        if self.pk and not fehler and self.anlage_am is not None:
            ausserhalb = self.komplikationen.filter(aktiv=True).filter(
                models.Q(datum__lt=self.anlage_am)
                | (models.Q(datum__gt=self.entfernt_am) if self.entfernt_am else models.Q(pk__in=[]))
            ).order_by("datum").first()
            if ausserhalb is not None:
                feld = "anlage_am" if ausserhalb.datum < self.anlage_am else "entfernt_am"
                fehler[feld] = (f"Die Komplikation vom {ausserhalb.datum:%d.%m.%Y} läge dann außerhalb der Liegezeit. "
                                "Bitte zuerst die Komplikation anpassen.")
        if fehler:
            raise ValidationError(fehler)

    def save(self, *args, **kwargs):
        # ohne Entfernung kein Entfernungsgrund
        if self.entfernt_am is None:
            self.entfernungsgrund = None
        super().save(*args, **kwargs)

    def __str__(self):
        typ = self.typ.wert if self.typ_id else "Katheter"
        return f"{typ} seit {self.anlage_am:%d.%m.%Y}" if self.anlage_am else typ


class KatheterKomplikation(AktenEintrag):
    """Komplikation an einem Katheter (F192): Datum, Art (Auswahlliste „Katheter: Komplikation“) und Notiz. Das Datum
    liegt in der Liegezeit des Katheters. ``patient`` steht zusätzlich am Eintrag (wie an allen Einträgen der Akte:
    Sperre abgeschlossener Akten, Verlauf, Löschen nach DSGVO). Kein Löschen – ``aktiv = False`` nimmt zurück."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="katheter_komplikationen")
    katheter = models.ForeignKey(Katheter, on_delete=models.CASCADE, related_name="komplikationen")
    datum = models.DateField()
    art = models.ForeignKey(
        Auswahlwert, on_delete=models.PROTECT, related_name="+", verbose_name="Art der Komplikation",
        limit_choices_to={"liste": Auswahlwert.Liste.KATHETER_KOMPLIKATION},
    )
    notiz = models.CharField(max_length=500, blank=True)
    aktiv = models.BooleanField(default=True)
    angelegt_am = models.DateTimeField(auto_now_add=True)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Katheter-Komplikation"
        verbose_name_plural = "Katheter-Komplikationen"
        ordering = ["-datum", "-id"]
        indexes = [models.Index(fields=["patient", "datum"], name="katheterkompl_patient_datum")]

    def delete(self, *args, **kwargs):
        raise PermissionError("Komplikationen werden nicht gelöscht, sondern als falsch erfasst zurückgenommen.")

    @property
    def ist_infektion(self) -> bool:
        return ist_infektion(self.art.wert if self.art_id else "")

    def clean(self):
        fehler = {}
        self.notiz = (self.notiz or "").strip()
        heute = timezone.localdate()
        if not self.art_id:
            fehler["art"] = "Bitte die Art der Komplikation wählen."
        elif self.art.liste != Auswahlwert.Liste.KATHETER_KOMPLIKATION:
            fehler["art"] = "Ungültiger Wert für die Liste „Komplikation“."
        if self.datum is None:
            fehler["datum"] = "Bitte das Datum angeben."
        elif self.datum > heute:
            fehler["datum"] = "Das Datum liegt in der Zukunft."
        if self.katheter_id:
            k = self.katheter
            if self.patient_id and k.patient_id != self.patient_id:
                fehler["katheter"] = "Dieser Katheter gehört zu einer anderen Akte."
            elif self.datum is not None and "datum" not in fehler:
                if self.datum < k.anlage_am:
                    fehler["datum"] = (f"Das Datum liegt vor der Anlage des Katheters ({k.anlage_am:%d.%m.%Y}). "
                                       "Eine Komplikation gehört in die Liegezeit.")
                elif k.entfernt_am and self.datum > k.entfernt_am:
                    fehler["datum"] = (f"Das Datum liegt nach der Entfernung des Katheters ({k.entfernt_am:%d.%m.%Y}). "
                                       "Eine Komplikation gehört in die Liegezeit.")
        elif not fehler:
            fehler["katheter"] = "Bitte den Katheter angeben."
        if fehler:
            raise ValidationError(fehler)

    def save(self, *args, **kwargs):
        if self.patient_id is None and self.katheter_id:
            self.patient_id = self.katheter.patient_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.art.wert if self.art_id else 'Komplikation'} am {self.datum:%d.%m.%Y}"


def ist_infektion(art_wert: str) -> bool:
    """Zählt eine Komplikation als Katheterinfektion (Kennzahl je 1000 Kathetertage)?

    OFFEN – vom Nutzer zu bestätigen: Die Liste „Katheter: Komplikation“ ist pflegbar und hat kein eigenes Merkmal
    „Infektion“. Gezählt wird darum jeder Wert, der „infektion“ enthält (Grundwert „Katheterinfektion“, aber auch z. B.
    ein später angelegter Wert „Tunnelinfektion“). Wird ein Wert umbenannt, ändert sich die Kennzahl mit."""
    return "infektion" in (art_wert or "").lower()


def katheter_kennzahlen(patient, heute=None) -> dict:
    """Kennzahlen der Katheter-Historie einer Akte (F192); nur aktive (nicht zurückgenommene) Einträge.

    * ``aktuell``: der zuletzt angelegte noch liegende Katheter mit Liegedauer in Tagen
    * ``offen``: Anzahl noch liegender Katheter (mehr als einer → Hinweis „Vorheriger Katheter noch nicht als entfernt
      eingetragen“)
    * ``kathetertage``: Summe der Liegedauern (Entfernt am bzw. heute minus Anlagedatum)
    * ``infektionen``: Komplikationen, die als Katheterinfektion zählen (``ist_infektion``)
    * ``infektionen_je_1000``: Infektionen / Kathetertage × 1000 (übliche Kennzahl der heimparenteralen Ernährung,
      „CRBSI-Rate“), auf zwei Stellen gerundet; ohne Kathetertage ``None``
    * ``anlagedatum_fehlt``: In den Kerndaten steht ein Katheter (``Patient.katheter``), die Historie ist aber leer –
      die Oberfläche bittet dann „Anlagedatum nicht erfasst – bitte nachtragen“ (Festlegung 16.10.2026; es werden
      keine Daten erfunden).

    OFFEN – vom Nutzer zu bestätigen: Zählweise der Kathetertage. Gezählt werden die Tage zwischen Anlage und Entfernung
    (der Anlagetag zählt nicht mit, ein am selben Tag entfernter Katheter hat 0 Tage); überlappende Katheter zählen
    beide. Manche Register zählen jeden Kalendertag mit liegendem Katheter (dann +1 je Katheter)."""
    from decimal import ROUND_HALF_UP

    heute = heute or timezone.localdate()
    katheter = list(patient.katheter_eintraege.filter(aktiv=True).select_related("typ").order_by("-anlage_am", "-id"))
    offen = [k for k in katheter if k.liegt]
    tage = sum(k.liegedauer_tage(heute) or 0 for k in katheter)
    komplikationen = KatheterKomplikation.objects.filter(patient=patient, aktiv=True, katheter__aktiv=True) \
        .select_related("art")
    infektionen = sum(1 for k in komplikationen if k.ist_infektion)
    rate = None
    if tage > 0:
        rate = (Decimal(infektionen) * 1000 / Decimal(tage)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    aktuell = offen[0] if offen else None
    return {
        "aktuell": {"id": aktuell.id, "typ": aktuell.typ.wert, "lage": aktuell.lage, "anlage_am": aktuell.anlage_am,
                    "liegedauer_tage": aktuell.liegedauer_tage(heute)} if aktuell else None,
        "offen": len(offen),
        "anzahl": len(katheter),
        "kathetertage": tage,
        "infektionen": infektionen,
        "infektionen_je_1000": rate,
        "anlagedatum_fehlt": bool(patient.katheter_id) and not katheter,
        "kerndaten_typ": patient.katheter.wert if patient.katheter_id else None,
        "kerndaten_typ_id": patient.katheter_id,
    }


def dokument_pfad(patient: Patient, originalname: str) -> str:
    endung = "".join(c for c in (originalname.rsplit(".", 1)[-1] if "." in originalname else "") if c.isalnum())[:10]
    return f"{patient.nummer}/{uuid.uuid4().hex}{'.' + endung.lower() if endung else ''}"



class Therapieschritt(AktenEintrag):
    """Ein Schritt im Verlauf der Therapie mit Datum, z. B. „Beginn HPE“, „Umstellung Lipide“ (Wunsch 10.10.2026).

    Der Text „Therapie“ der Akte beschreibt, was aktuell gilt; der Verlauf steht daneben als Liste. Nichts wird
    gelöscht: ein falscher Schritt wird mit ``aktiv = False`` entfernt und bleibt im Verlauf der Akte."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="therapieschritte")
    datum = models.DateField()
    text = models.CharField(max_length=300)
    aktiv = models.BooleanField(default=True)
    angelegt_am = models.DateTimeField(auto_now_add=True)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Schritt der Therapie"
        verbose_name_plural = "Verlauf der Therapie"
        ordering = ["-datum", "-id"]
        indexes = [models.Index(fields=["patient", "aktiv"], name="therapieschritt_patient_aktiv")]

    def delete(self, *args, **kwargs):
        raise PermissionError("Schritte der Therapie werden nicht gelöscht, sondern entfernt (aktiv = False).")

    def __str__(self):
        return f"{self.datum}: {self.text}"


class Dokument(AktenEintrag):
    """Datei im Dateisystem (EPM_DOKUMENTE/<nummer>/...), Metadaten und Prüfsumme in der DB."""

    class Herkunft(models.TextChoices):
        UPLOAD = "upload", "Hochgeladen"
        ALTSYSTEM = "altsystem", "Altsystem"
        SYSTEM = "system", "Von EPM erzeugt"
        SCAN = "scan", "Aus „Scans“ (Text erkannt)"

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


class DokumentText(models.Model):
    """Erkannter Text eines Dokuments (Menüpunkt „Scans“, F163): damit die Akte das Dokument über seinen Inhalt findet.

    Ohne eigenen Verlauf – der Text ergibt sich aus der Datei. Er hängt am Dokument und geht mit ihm: beim Zuordnen zu
    einem anderen Patienten mit, beim endgültigen Löschen (Art. 17 DSGVO) mit weg."""

    dokument = models.OneToOneField(Dokument, on_delete=models.CASCADE, primary_key=True, related_name="erkannter_text")
    text = models.TextField()
    sicherheit = models.FloatField(null=True, blank=True, help_text="0–1, nach Zeichen gewichtet")
    verfahren = models.CharField(max_length=100, blank=True)
    erkannt_am = models.DateTimeField()

    class Meta:
        verbose_name = "Erkannter Text"
        verbose_name_plural = "Erkannte Texte"

    def __str__(self):
        return f"Text von Dokument {self.dokument_id}"


class DokumentVorgang(models.Model):
    """Ein Dokument hat die Akte verlassen: einem anderen Patienten zugeordnet oder endgültig gelöscht
    (Festlegung 02.10.2026). Unveränderlich (Trigger). Der Verlauf der bisherigen Akte zeigt das Dokument danach
    nur noch neutral – ohne Titel und ohne den anderen Patienten."""

    class Art(models.TextChoices):
        UMGEHAENGT = "umgehaengt", "einem anderen Patienten zugeordnet"
        GELOESCHT = "geloescht", "endgültig gelöscht"

    art = models.CharField(max_length=20, choices=Art.choices)
    dokument_id = models.PositiveIntegerField(db_index=True)
    # leer, wenn die bisherige Akte inzwischen endgültig gelöscht ist (das Dokument liegt bei ``nach_patient``)
    von_patient = models.ForeignKey(Patient, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    nach_patient = models.ForeignKey(Patient, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    grund = models.TextField()
    zeitpunkt = models.DateTimeField(auto_now_add=True)
    # leer nur, wenn eine Löschung nach einer Wiederherstellung nachgeholt wurde und die Person dort fehlt
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                               related_name="+")
    # Nachweis ohne Inhalt (Art. 17 DSGVO): welche Datei es war
    sha256 = models.CharField(max_length=64, blank=True, default="")
    datei = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Dokument-Vorgang"
        verbose_name_plural = "Dokument-Vorgänge"
        ordering = ["-zeitpunkt"]



# ================================================================= Datenschutz (Festlegung 02.10.2026)
class Erklaerung(models.Model):
    """Erklärung des Patienten: Datenschutzinformation erhalten, Einwilligung, Schweigepflichtentbindung.

    Nachgehalten wie die Nickelallergie, aber mit Datum: je Art „nicht erfasst“, „liegt vor seit …“ oder
    „widerrufen am …“. Das unterschriebene Blatt liegt als Dokument (Scan) in der Akte und ist hier verknüpft.
    Gelöscht wird nichts: Ein Widerruf wird eingetragen, eine neue Erklärung ist ein neuer Eintrag.
    Auch bei abgeschlossenen Akten möglich (ein Widerruf kann nach dem Abschluss eingehen)."""

    class Art(models.TextChoices):
        DATENSCHUTZINFORMATION = "datenschutzinformation", "Datenschutzinformation"
        EINWILLIGUNG = "einwilligung", "Einwilligung in die Datenverarbeitung"
        SCHWEIGEPFLICHTENTBINDUNG = "schweigepflichtentbindung", "Schweigepflichtentbindung"
        # Anforderung 11.10.2026: Voraussetzung, um eine Akte beiden Firmen (DSKM und RG) zuzuordnen
        FIRMEN = "firmen", "Einwilligung Austausch zwischen DSKM und Regeneration Clinic"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="erklaerungen")
    art = models.CharField(max_length=30, choices=Art.choices)
    erteilt_am = models.DateField("erteilt bzw. ausgehändigt am")
    dokument = models.ForeignKey(Dokument, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                 verbose_name="Unterschriebenes Blatt (Scan)")
    vorlage_version = models.PositiveIntegerField("Stand der Dokumentvorlage bei der Erfassung", null=True, blank=True)
    notiz = models.CharField(max_length=300, blank=True)
    widerrufen_am = models.DateField(null=True, blank=True)
    widerruf_notiz = models.CharField(max_length=300, blank=True)
    erfasst_am = models.DateTimeField(auto_now_add=True)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Erklärung"
        verbose_name_plural = "Erklärungen"
        ordering = ["art", "-erteilt_am", "-id"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Erklärungen werden nicht gelöscht; ein Widerruf wird eingetragen.")

    def clean(self):
        heute = timezone.localdate()
        if self.erteilt_am and self.erteilt_am > heute:
            raise ValidationError({"erteilt_am": "Das Datum liegt in der Zukunft."})
        if self.widerrufen_am and self.widerrufen_am > heute:
            raise ValidationError({"widerrufen_am": "Das Datum liegt in der Zukunft."})
        if self.widerrufen_am and self.erteilt_am and self.widerrufen_am < self.erteilt_am:
            raise ValidationError({"widerrufen_am": "Der Widerruf liegt vor der Erklärung."})

    def __str__(self):
        return f"{self.get_art_display()} vom {self.erteilt_am:%d.%m.%Y}"


def erklaerungen_stand(patient_ids) -> dict:
    """{patient_id: {art: {"status": "liegt_vor" | "widerrufen", "am": Datum, "id": ID}}} – je Art zählt die
    jüngste Erklärung; fehlt die Art ganz, fehlt auch der Schlüssel („nicht erfasst“)."""
    stand: dict = {}
    for e in Erklaerung.objects.filter(patient_id__in=list(patient_ids)).order_by("erteilt_am", "id"):
        stand.setdefault(e.patient_id, {})[e.art] = {
            "status": "widerrufen" if e.widerrufen_am else "liegt_vor",
            "am": e.widerrufen_am or e.erteilt_am, "id": e.id,
        }
    return stand


class Datenschutzanfrage(models.Model):
    """Anfrage einer betroffenen Person (Auskunft, Berichtigung, Löschung, Einschränkung, Widerruf) als Vorgang
    mit Frist: zu beantworten unverzüglich, spätestens einen Monat nach Eingang; bei Bedarf um zwei Monate
    verlängerbar (Art. 12 Abs. 3 DSGVO). Erledigt wird mit Ergebnis und Begründung; nichts wird gelöscht."""

    class Art(models.TextChoices):
        AUSKUNFT = "auskunft", "Auskunft / Kopie der Akte"
        BERICHTIGUNG = "berichtigung", "Berichtigung"
        LOESCHUNG = "loeschung", "Löschung"
        EINSCHRAENKUNG = "einschraenkung", "Einschränkung der Verarbeitung"
        WIDERRUF = "widerruf", "Widerruf einer Einwilligung"
        SONSTIGES = "sonstiges", "Sonstiges"

    class Ergebnis(models.TextChoices):
        ERFUELLT = "erfuellt", "erfüllt"
        EINGESCHRAENKT = "eingeschraenkt", "Verarbeitung eingeschränkt statt gelöscht"
        ABGELEHNT = "abgelehnt", "abgelehnt"
        ZURUECKGEZOGEN = "zurueckgezogen", "zurückgezogen"

    FRIST_MONATE = 1
    VERLAENGERUNG_MONATE = 2

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="datenschutzanfragen")
    art = models.CharField(max_length=20, choices=Art.choices)
    eingegangen_am = models.DateField(default=timezone.localdate)
    gestellt_von = models.CharField("Gestellt von", max_length=150, blank=True,
                                    help_text="z. B. „Patient selbst“, Betreuerin, Erbe")
    inhalt = models.TextField("Inhalt der Anfrage", blank=True)
    frist_verlaengert = models.BooleanField(default=False)
    verlaengerung_grund = models.CharField(max_length=300, blank=True)
    ergebnis = models.CharField(max_length=20, choices=Ergebnis.choices, blank=True)
    begruendung = models.TextField("Begründung / Vermerk", blank=True)
    mitgeteilt_am = models.DateField("Der Person mitgeteilt am", null=True, blank=True)
    erledigt_am = models.DateTimeField(null=True, blank=True)
    erledigt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")
    erfasst_am = models.DateTimeField(auto_now_add=True)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Datenschutz-Anfrage"
        verbose_name_plural = "Datenschutz-Anfragen"
        ordering = ["-eingegangen_am", "-id"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Datenschutz-Anfragen werden nicht gelöscht, sondern mit Ergebnis erledigt.")

    @property
    def ist_offen(self) -> bool:
        return self.erledigt_am is None

    @property
    def frist_bis(self):
        monate = self.FRIST_MONATE + (self.VERLAENGERUNG_MONATE if self.frist_verlaengert else 0)
        return plus_monate(self.eingegangen_am, monate)

    @property
    def ueberfaellig(self) -> bool:
        return self.ist_offen and self.frist_bis < timezone.localdate()

    def clean(self):
        if self.eingegangen_am and self.eingegangen_am > timezone.localdate():
            raise ValidationError({"eingegangen_am": "Das Datum liegt in der Zukunft."})
        if self.frist_verlaengert and not self.verlaengerung_grund.strip():
            raise ValidationError({"verlaengerung_grund": "Bitte den Grund der Verlängerung angeben."})

    def __str__(self):
        return f"{self.get_art_display()} vom {self.eingegangen_am:%d.%m.%Y}"


class Akteneinsicht(models.Model):
    """Begründete Einsicht in eine Akte, deren Verarbeitung eingeschränkt ist: gilt für eine Person und eine
    begrenzte Zeit; jede Einsicht steht mit Grund im Audit-Log."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="einsichten")
    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    grund = models.TextField()
    von = models.DateTimeField(auto_now_add=True)
    bis = models.DateTimeField()

    class Meta:
        verbose_name = "Akteneinsicht"
        verbose_name_plural = "Akteneinsichten"
        ordering = ["-von"]
        indexes = [models.Index(fields=["benutzer", "bis"], name="akteneinsicht_benutzer_bis")]


class Loeschprotokoll(models.Model):
    """Nachweis einer endgültig gelöschten Akte – ohne Namen und ohne Inhalte: Patientennummer und interne Kennung,
    angelegt am, abgeschlossen am, Aufbewahrung bis, Rechtsgrund, Grund (Freitext der löschenden Person), Umfang
    (Anzahl der Datensätze und Dateien), wer wann gelöscht hat. Der Anlass des Abschlusses (z. B. „verstorben“) wird
    bewusst nicht übernommen. Unveränderlich (Trigger). Nach dem Wiederherstellen einer älteren Sicherung werden die
    hier vermerkten Akten erneut gelöscht (``manage.py epm_loeschungen_nachholen``, bei jedem Start)."""

    class Rechtsgrund(models.TextChoices):
        FRIST = "frist", "Aufbewahrungsfrist abgelaufen"
        ANTRAG = "antrag", "Antrag der betroffenen Person"

    akte_id = models.PositiveBigIntegerField("Interne Kennung der Akte", db_index=True)
    nummer = models.PositiveIntegerField("Patientennummer", db_index=True)
    ist_test = models.BooleanField(default=False)
    angelegt_am = models.DateTimeField("Akte angelegt am")
    abgeschlossen_am = models.DateField(null=True, blank=True)
    aufbewahrung_bis = models.DateField(null=True, blank=True)
    rechtsgrund = models.CharField(max_length=20, choices=Rechtsgrund.choices)
    grund = models.TextField()
    umfang = models.JSONField(default=dict, blank=True)
    geloescht_am = models.DateTimeField(default=timezone.now)
    geloescht_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")

    class Meta:
        verbose_name = "Löschprotokoll"
        verbose_name_plural = "Löschprotokoll"
        ordering = ["-geloescht_am", "-id"]

    def __str__(self):
        return f"Akte Nr. {self.nummer} gelöscht am {self.geloescht_am:%d.%m.%Y}"


class Hinweisruhe(models.Model):
    """Ein Hinweis einer Akte ist stummgeschaltet (Wunsch 07.10.2026, F119).

    Jeder Hinweis der Patientenliste und des Aktenkopfs lässt sich mit „×“ wegklicken. Dabei wird entschieden,
    wie lange Ruhe sein soll: eine Frist in Monaten – danach erscheint der Hinweis von allein wieder – oder
    „nicht mehr nötig“ (``bis`` leer), dann bleibt er weg, bis jemand das zurücknimmt.

    Gelöscht wird nichts: Das Aufheben trägt ``aufgehoben_am`` ein, jede Fassung steht im Verlauf der Akte.
    Die Bestätigung „Kein Infusionsplan nötig“ (F105) bleibt davon unberührt – sie wirkt weiter wie bisher."""

    class Art(models.TextChoices):
        GEWICHT = "gewicht", "Gewichtsverlust"
        PLAN = "plan", "Infusionsplan älter als …"
        OHNE_PLAN = "ohne_plan", "Kein Infusionsplan"
        VERSORGER = "versorger", "Versorger nicht erfasst"
        KONTAKT = "kontakt", "Kontakt fällig"
        LABOR = "labor", "Laborbefund älter als …"
        BIA = "bia", "BIA-Messung älter als …"
        # Fehlende Angaben (F186, 10.10.2026)
        HAUSARZT = "hausarzt", "Kein Hausarzt erfasst"
        TELEFON = "telefon", "Keine Telefonnummer"
        GEWICHT_FEHLT = "gewicht_fehlt", "Kein aktuelles Gewicht"
        DIAGNOSE = "diagnose", "Keine Diagnose"
        TERMIN_ORT = "termin_ort", "Praxistermin ohne Ort"
        # Wunsch 11.10.2026: wegklickbar wie die übrigen (nicht jeder Patient hat einen Katheter)
        NICKELALLERGIE = "nickelallergie", "Nickelallergie nicht erfasst"

    FRISTEN = (3, 6, 12)

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="hinweisruhe")
    art = models.CharField(max_length=20, choices=Art.choices)
    bis = models.DateField("Ruhe bis", null=True, blank=True, help_text="leer = nicht mehr nötig, bis aufgehoben")
    grund = models.CharField(max_length=300, blank=True)
    gesetzt_am = models.DateTimeField(auto_now_add=True)
    gesetzt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    aufgehoben_am = models.DateTimeField(null=True, blank=True)
    aufgehoben_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Stummgeschalteter Hinweis"
        verbose_name_plural = "Stummgeschaltete Hinweise"
        ordering = ["-gesetzt_am", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["patient", "art"], condition=models.Q(aufgehoben_am__isnull=True),
                                    name="hinweisruhe_je_art_einmal"),
        ]
        indexes = [models.Index(fields=["patient", "art"], name="hinweisruhe_patient_art")]

    def delete(self, *args, **kwargs):
        raise PermissionError("Stummgeschaltete Hinweise werden nicht gelöscht, sondern aufgehoben.")

    @property
    def laeuft(self) -> bool:
        """Wirkt die Stummschaltung heute noch?"""
        if self.aufgehoben_am is not None:
            return False
        return self.bis is None or self.bis >= timezone.localdate()

    def aufheben(self, benutzer):
        if self.aufgehoben_am is not None:
            raise ValidationError("Der Hinweis ist bereits wieder eingeschaltet.")
        self.aufgehoben_am = timezone.now()
        self.aufgehoben_von = benutzer
        self.save(update_fields=["aufgehoben_am", "aufgehoben_von"])

    def clean(self):
        if self.bis is not None and self.bis < timezone.localdate():
            raise ValidationError({"bis": "Das Datum liegt in der Vergangenheit."})

    def __str__(self):
        wann = f"bis {self.bis:%d.%m.%Y}" if self.bis else "bis auf Weiteres"
        return f"{self.get_art_display()} stumm {wann}"


def ruhende_hinweise(patient_ids) -> dict:
    """{patient_id: {art}} – welche Hinweise heute stummgeschaltet sind (F119)."""
    heute = timezone.localdate()
    ergebnis: dict = {}
    for pid, art in (Hinweisruhe.objects
                     .filter(patient_id__in=list(patient_ids), aufgehoben_am__isnull=True)
                     .filter(models.Q(bis__isnull=True) | models.Q(bis__gte=heute))
                     .values_list("patient_id", "art")):
        ergebnis.setdefault(pid, set()).add(art)
    return ergebnis


class Merkeintrag(models.Model):
    """„Meine Akten“ (S05) je Person: Merkliste (Stern im Aktenkopf) und zuletzt geöffnete Akten. Nur der Verweis auf
    die Akte, keine Inhalte; sichtbar nur für die Person selbst. Fällt mit der Akte weg (endgültiges Löschen,
    Zurücksetzen der Testdaten)."""

    class Art(models.TextChoices):
        MERKLISTE = "merkliste", "Merkliste"
        GEOEFFNET = "geoeffnet", "zuletzt geöffnet"

    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="+")
    art = models.CharField(max_length=10, choices=Art.choices)
    zeitpunkt = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Eintrag in „Meine Akten“"
        verbose_name_plural = "Einträge in „Meine Akten“"
        ordering = ["-zeitpunkt", "-id"]
        constraints = [models.UniqueConstraint(fields=["benutzer", "patient", "art"], name="merkeintrag_eindeutig")]


class Ankuendigung(models.Model):
    """Ein erstelltes „Infoblatt an die Praxis“ (F177): wann, von wem, für welchen Zeitraum und Ort, als PDF oder
    E-Mail – und welche Termine darauf standen.

    Der Schnappschuss enthält je Termin nur Nummer, Datum und Uhrzeit, keine Namen: Daraus ergibt sich beim nächsten
    Infoblatt, welche Termine neu hinzugekommen oder verschoben sind. Wird eine Akte endgültig gelöscht (Art. 17 DSGVO)
    oder werden die Testdaten zurückgesetzt, entfallen ihre Termine auch hier (``datenschutz.akten_entfernen``).
    Angelegt nur beim Erzeugen der PDF bzw. der E-Mail, nicht bei der Vorschau."""

    class Ausgabe(models.TextChoices):
        PDF = "pdf", "PDF"
        EML = "eml", "E-Mail"

    erstellt_am = models.DateTimeField(default=timezone.now)
    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    von = models.DateField()
    bis = models.DateField()
    ort = models.ForeignKey(Auswahlwert, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                            limit_choices_to={"liste": Auswahlwert.Liste.TERMINORT}, verbose_name="Terminort")
    telefon_mit = models.BooleanField("mit Telefon- und Videoterminen", default=False)
    ausgabe = models.CharField(max_length=5, choices=Ausgabe.choices)
    anzahl = models.PositiveIntegerField("Zahl der Termine", default=0)
    # [{"termin": Nummer, "datum": "JJJJ-MM-TT", "uhrzeit": "HH:MM" oder null}, …]
    termine = models.JSONField("Termine auf dem Blatt", default=list, blank=True)

    class Meta:
        verbose_name = "Infoblatt an die Praxis"
        verbose_name_plural = "Infoblätter an die Praxis"
        ordering = ["-erstellt_am", "-id"]
        indexes = [models.Index(fields=["von", "bis"], name="ankuendigung_zeitraum")]

    def __str__(self):
        return f"Infoblatt {self.von:%d.%m.%Y}–{self.bis:%d.%m.%Y} vom {self.erstellt_am:%d.%m.%Y}"


@receiver(post_save, sender=Patient, dispatch_uid="patient_firma_zuordnen")
def _neue_akte_der_firma_zuordnen(sender, instance, created, raw=False, **kwargs):
    """Neue Akten gehören der Firma, in der sie angelegt werden (Anforderung 11.10.2026); ohne aktive Firma
    (Altdaten-Import, Verwaltungsbefehle) der DSKM – der Import gilt nur für sie."""
    if not created or raw:
        return
    from epm.firma import HAUPTFIRMA, aktive_firma
    from stammdaten.models import Firma

    firma = aktive_firma() or Firma.objects.filter(kuerzel=HAUPTFIRMA).first()
    if firma is not None:
        PatientFirma.objects.get_or_create(patient=instance, firma=firma,
                                           defaults={"zugeordnet_von_id": instance.angelegt_von_id})
