"""Laborbefunde und BIA-Messungen (Wünsche aus der Praxis vom 06.10.2026, F112–F114).

Beides war bisher reine Abschreibarbeit: Werte von Hand in ein Freitextfeld tippen und das Blatt zusätzlich
hochladen. Stattdessen gibt es hier Masken mit vorgegebenen Parametern – eingetragen wird nur noch der
gemessene Wert.

Beide Modelle sind Einträge der Akte (``AktenEintrag``): Sie sind gesperrt, sobald die Akte abgeschlossen
ist, und jede Fassung steht mit Bearbeiter und Zeitpunkt im Verlauf.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from patienten.models import AktenEintrag, Gewichtsmessung, Patient
from stammdaten.models import Laborparameter


class Laborbefund(AktenEintrag):
    """Ein Laborbefund = eine Blutabnahme mit beliebig vielen Werten.

    Das Original (PDF des Labors) kann als Dokument der Akte verknüpft werden (U48); Pflicht ist es nicht."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="laborbefunde")
    abgenommen_am = models.DateField("Abnahme am", default=timezone.localdate)
    # Uhrzeit der Entnahme (14.10.2026, KI-Verknüpfung mit Infusionsplänen): optional, oft nicht dokumentiert
    abgenommen_um = models.TimeField("Abnahme um", null=True, blank=True)
    labor = models.CharField(max_length=150, blank=True, help_text="z. B. „Labor Dr. Wagner“ oder die Klinik")
    beurteilung = models.TextField("Zusammenfassung / Beurteilung", blank=True)
    dokument = models.ForeignKey(
        "patienten.Dokument", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="Originalbefund (Dokument der Akte)",
    )
    erfasst_am = models.DateTimeField(auto_now_add=True)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Laborbefund"
        verbose_name_plural = "Laborbefunde"
        ordering = ["-abgenommen_am", "-id"]
        indexes = [models.Index(fields=["patient", "abgenommen_am"], name="laborbefund_patient_datum")]

    def __str__(self):
        return f"Laborbefund vom {self.abgenommen_am:%d.%m.%Y}"

    def clean(self):
        if self.abgenommen_am and self.abgenommen_am > timezone.localdate():
            raise ValidationError({"abgenommen_am": "Das Datum liegt in der Zukunft."})
        if self.dokument_id and self.dokument.patient_id != self.patient_id:
            raise ValidationError({"dokument": "Das Dokument gehört zu einer anderen Akte."})

    @property
    def anzahl_werte(self) -> int:
        return self.werte.count()


class Laborwert(models.Model):
    """Eine Zeile eines Befunds: Parameter aus dem Katalog **oder** ein Freitextname.

    Der Freitextname deckt ab, was nur bei einzelnen Patienten erhoben wird (Tumormarker, genetische
    Parameter) und deshalb nicht in den Katalog gehört.

    ``wert`` ist die Zahl, mit der gerechnet und ein Verlauf gezeichnet werden kann. ``wert_text`` nimmt auf,
    was keine Zahl ist („< 0,1“, „negativ“, „n. b.“) – dann gibt es für diese Zeile keinen Verlauf (U47).
    Mindestens eines von beiden muss gefüllt sein, sonst wäre die Zeile leer."""

    befund = models.ForeignKey(Laborbefund, on_delete=models.CASCADE, related_name="werte")
    parameter = models.ForeignKey(Laborparameter, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="werte")
    freitext_name = models.CharField("Parameter (Freitext)", max_length=150, blank=True)
    wert = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    wert_text = models.CharField("Wert (Text)", max_length=50, blank=True,
                                 help_text="für Angaben, die keine Zahl sind, z. B. „< 0,1“ oder „negativ“")
    einheit = models.CharField(max_length=30, blank=True)
    referenz_von = models.DecimalField("Referenz von", max_digits=12, decimal_places=4, null=True, blank=True)
    referenz_bis = models.DecimalField("Referenz bis", max_digits=12, decimal_places=4, null=True, blank=True)
    bemerkung = models.CharField(max_length=200, blank=True)
    reihenfolge = models.PositiveSmallIntegerField(default=0)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Laborwert"
        verbose_name_plural = "Laborwerte"
        ordering = ["reihenfolge", "id"]
        constraints = [
            models.UniqueConstraint(fields=["befund", "parameter"], condition=models.Q(parameter__isnull=False),
                                    name="laborwert_parameter_je_befund_einmal"),
            models.CheckConstraint(
                name="laborwert_hat_bezeichnung",
                condition=models.Q(parameter__isnull=False) | ~models.Q(freitext_name=""),
            ),
            models.CheckConstraint(
                name="laborwert_hat_wert",
                condition=models.Q(wert__isnull=False) | ~models.Q(wert_text=""),
            ),
        ]

    def _pruefe(self):
        self.befund.patient.pruefe_bearbeitbar()

    def save(self, *args, **kwargs):
        self._pruefe()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._pruefe()
        return super().delete(*args, **kwargs)

    @property
    def bezeichnung(self) -> str:
        return str(self.parameter.name) if self.parameter_id else self.freitext_name

    @property
    def anzeige_wert(self) -> str:
        if self.wert is not None:
            text = f"{self.wert:f}".rstrip("0").rstrip(".") or "0"
            return text.replace(".", ",")
        return self.wert_text

    @property
    def ausserhalb(self):
        """Liegt der Wert außerhalb des Referenzbereichs? ``None``, wenn kein Bereich hinterlegt ist (U44)."""
        if self.wert is None or (self.referenz_von is None and self.referenz_bis is None):
            return None
        if self.referenz_von is not None and self.wert < self.referenz_von:
            return "niedrig"
        if self.referenz_bis is not None and self.wert > self.referenz_bis:
            return "hoch"
        return None

    def clean(self):
        fehler = {}
        self.freitext_name = (self.freitext_name or "").strip()
        self.wert_text = (self.wert_text or "").strip()
        if not self.parameter_id and not self.freitext_name:
            fehler["freitext_name"] = "Bitte einen Parameter wählen oder benennen."
        if self.parameter_id and self.freitext_name:
            fehler["freitext_name"] = "Entweder einen Parameter aus der Liste oder einen eigenen Namen."
        if self.wert is None and not self.wert_text:
            fehler["wert"] = "Bitte einen Wert eintragen."
        if self.wert is not None and self.wert_text:
            fehler["wert_text"] = "Entweder eine Zahl oder einen Text, nicht beides."
        if (self.referenz_von is not None and self.referenz_bis is not None
                and self.referenz_von > self.referenz_bis):
            fehler["referenz_bis"] = "„Referenz bis“ muss größer oder gleich „Referenz von“ sein."
        if fehler:
            raise ValidationError(fehler)

    def __str__(self):
        return f"{self.bezeichnung}: {self.anzeige_wert} {self.einheit}".strip()


class BiaMessung(AktenEintrag):
    """Körperzusammensetzung aus der BIA-Messung (F114).

    Werte wie von Alice genannt: Gewicht, BCM, Fettmasse, extrazelluläres Wasser (ECW) in Prozent,
    Körperwasser in Litern, BMI, Phasenwinkel – dazu ein Feld für die Beurteilung.

    Der BMI kommt vom Gerät und wird deshalb eingetragen; ``bmi_berechnet`` zeigt daneben, was sich aus
    Gewicht und hinterlegter Größe ergibt (U49)."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="bia_messungen")
    gemessen_am = models.DateField("Gemessen am", default=timezone.localdate)
    gewicht_kg = models.DecimalField("Gewicht (kg)", max_digits=5, decimal_places=1, null=True, blank=True)
    bcm_kg = models.DecimalField("BCM (kg)", max_digits=5, decimal_places=1, null=True, blank=True)
    fettmasse_kg = models.DecimalField("Fettmasse (kg)", max_digits=5, decimal_places=1, null=True, blank=True)
    ecw_prozent = models.DecimalField("ECW – extrazelluläres Wasser (%)", max_digits=4, decimal_places=1,
                                      null=True, blank=True)
    koerperwasser_l = models.DecimalField("Körperwasser (l)", max_digits=5, decimal_places=1, null=True, blank=True)
    bmi = models.DecimalField("BMI", max_digits=4, decimal_places=1, null=True, blank=True)
    # Phasenwinkel (Wunsch DSKM 16.11.2026): wichtigster Verlaufswert neben BCM und Fettmasse
    phasenwinkel_grad = models.DecimalField("Phasenwinkel (°)", max_digits=4, decimal_places=1, null=True, blank=True)
    beurteilung = models.TextField("Zusammenfassung / Beurteilung", blank=True)
    dokument = models.ForeignKey(
        "patienten.Dokument", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="Geräteprotokoll (Dokument der Akte)",
    )
    # Ergebnis der Übernahme in den Gewichtsverlauf (U50): Das Gewicht einer BIA ist ein Gewicht – es soll nicht
    # zweimal getippt werden müssen. Die Messung bleibt verknüpft, damit nichts doppelt entsteht.
    gewichtsmessung = models.OneToOneField(
        Gewichtsmessung, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="Im Gewichtsverlauf eingetragen als",
    )
    erfasst_am = models.DateTimeField(auto_now_add=True)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "BIA-Messung"
        verbose_name_plural = "BIA-Messungen"
        ordering = ["-gemessen_am", "-id"]
        indexes = [models.Index(fields=["patient", "gemessen_am"], name="bia_patient_datum")]

    def __str__(self):
        return f"BIA-Messung vom {self.gemessen_am:%d.%m.%Y}"

    @property
    def bmi_berechnet(self):
        """BMI aus dem Gewicht dieser Messung und der hinterlegten Größe – als Vergleich zum Gerätewert."""
        if self.gewicht_kg is None or not self.patient.groesse_cm:
            return None
        meter = self.patient.groesse_cm / Decimal(100)
        return (self.gewicht_kg / (meter * meter)).quantize(Decimal("0.1"))

    @property
    def magermasse_kg(self):
        """Fettfreie Masse = Gewicht − Fettmasse (nur wenn beides erfasst ist)."""
        if self.gewicht_kg is None or self.fettmasse_kg is None:
            return None
        return self.gewicht_kg - self.fettmasse_kg

    def clean(self):
        from stammdaten.models import Einstellungen

        fehler = {}
        if self.gemessen_am and self.gemessen_am > timezone.localdate():
            fehler["gemessen_am"] = "Das Datum liegt in der Zukunft."
        e = Einstellungen.aktuell()
        if self.gewicht_kg is not None and not (e.gewicht_min_kg <= self.gewicht_kg <= e.gewicht_max_kg):
            fehler["gewicht_kg"] = (f"Gewicht muss zwischen {e.gewicht_min_kg} und {e.gewicht_max_kg} kg liegen.")
        if self.ecw_prozent is not None and not (Decimal(0) < self.ecw_prozent <= Decimal(100)):
            fehler["ecw_prozent"] = "ECW ist ein Anteil zwischen 0 und 100 %."
        if self.phasenwinkel_grad is not None and not (Decimal(0) < self.phasenwinkel_grad <= Decimal(20)):
            fehler["phasenwinkel_grad"] = "Der Phasenwinkel liegt zwischen 0 und 20°."
        if (self.gewicht_kg is not None and self.fettmasse_kg is not None
                and self.fettmasse_kg > self.gewicht_kg):
            fehler["fettmasse_kg"] = "Die Fettmasse kann nicht größer als das Gewicht sein."
        if (self.gewicht_kg is not None and self.bcm_kg is not None and self.bcm_kg > self.gewicht_kg):
            fehler["bcm_kg"] = "Die BCM kann nicht größer als das Gewicht sein."
        if (self.gewicht_kg is not None and self.koerperwasser_l is not None
                and self.koerperwasser_l > self.gewicht_kg):
            fehler["koerperwasser_l"] = "Das Körperwasser kann nicht mehr Liter haben als das Gewicht Kilogramm."
        if not any(getattr(self, f) is not None for f in
                   ("gewicht_kg", "bcm_kg", "fettmasse_kg", "ecw_prozent", "koerperwasser_l", "bmi",
                    "phasenwinkel_grad")):
            fehler["fehler"] = "Bitte mindestens einen Messwert eintragen."
        if self.dokument_id and self.dokument.patient_id != self.patient_id:
            fehler["dokument"] = "Das Dokument gehört zu einer anderen Akte."
        if fehler:
            raise ValidationError(fehler)

    def gewicht_uebernehmen(self, benutzer):
        """Trägt das Gewicht der Messung in den Gewichtsverlauf ein (U50) – einmalig je BIA-Messung. Ist es schon
        eingetragen, gehen korrigiertes Gewicht und Datum in diesen Eintrag mit (Verlauf, BMI, Warnungen)."""
        if self.gewicht_kg is None:
            # shortcut: ein gelöschtes BIA-Gewicht bleibt im Verlauf stehen, bis es dort entfernt wird
            return self.gewichtsmessung
        if self.gewichtsmessung_id:
            messung = self.gewichtsmessung
            if (messung.gewicht_kg, messung.gemessen_am) != (self.gewicht_kg, self.gemessen_am):
                messung.gewicht_kg, messung.gemessen_am = self.gewicht_kg, self.gemessen_am
                messung._history_user = benutzer
                messung.full_clean()
                messung.save()
            return messung
        messung = Gewichtsmessung(patient=self.patient, gewicht_kg=self.gewicht_kg, gemessen_am=self.gemessen_am,
                                  quelle=Gewichtsmessung.Quelle.AMBULANZ, notiz="aus der BIA-Messung",
                                  erfasst_von=benutzer)
        messung._history_user = benutzer
        messung.full_clean()
        messung.save()
        self.gewichtsmessung = messung
        super().save(update_fields=["gewichtsmessung"])
        return messung
