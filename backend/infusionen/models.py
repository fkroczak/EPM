"""Infusionspläne: Entwurf → aktuell → abgelöst. Nach Freigabe unveränderlich."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from simple_history.models import HistoricalRecords
from simple_history.utils import bulk_create_with_history

from patienten.models import AktenEintrag, Patient
from stammdaten.models import Einstellungen, Praeparat

# Energiegehalt je Gramm (wie im Altsystem)
KCAL_JE_G = {
    "glucose_g": Decimal(4),
    "aminosaeuren_g": Decimal(4),
    "albumin_g": Decimal(4),
    "lipide_g": Decimal(9),
}

# Felder, die beim neuen Entwurf vom aktuellen Plan übernommen und auf Änderung verglichen werden
PLANFELDER = [
    "basis_praeparat", "basis_ml", "glucose_praeparat", "glucose_g", "aminosaeuren_praeparat", "aminosaeuren_g",
    "lipide_praeparat", "lipide_g", "albumin_praeparat", "albumin_g", "kcal_manuell",
    "laufzeit_h", "tage_pro_woche", "katheterschutz", "pantozol_stufe", "pantozol_tage", "bemerkung",
]


class Infusionsplan(AktenEintrag):
    class Status(models.TextChoices):
        ENTWURF = "entwurf", "Entwurf"
        AKTUELL = "aktuell", "aktuell"
        ABGELOEST = "abgeloest", "abgelöst"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="infusionsplaene")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ENTWURF)
    vorgaenger = models.OneToOneField(
        "self", on_delete=models.RESTRICT, null=True, blank=True, related_name="nachfolger"
    )
    gueltig_ab = models.DateField(default=timezone.localdate)

    def _p(kat, name):
        return models.ForeignKey(
            Praeparat, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
            limit_choices_to={"kategorie": kat}, verbose_name=name,
        )

    basis_praeparat = _p(Praeparat.Kategorie.BASISLOESUNG, "Basislösung")
    basis_ml = models.PositiveIntegerField("Basislösung (ml)", null=True, blank=True)
    glucose_praeparat = _p(Praeparat.Kategorie.GLUCOSE, "Glucose-Präparat")
    glucose_g = models.DecimalField("Glucose (g)", max_digits=6, decimal_places=1, null=True, blank=True)
    aminosaeuren_praeparat = _p(Praeparat.Kategorie.AMINOSAEUREN, "Aminosäuren-Präparat")
    aminosaeuren_g = models.DecimalField("Aminosäuren (g)", max_digits=6, decimal_places=1, null=True, blank=True)
    lipide_praeparat = _p(Praeparat.Kategorie.LIPIDE, "Lipid-Präparat")
    lipide_g = models.DecimalField("Lipide (g)", max_digits=6, decimal_places=1, null=True, blank=True)
    albumin_praeparat = _p(Praeparat.Kategorie.ALBUMIN, "Albumin-Präparat")
    albumin_g = models.DecimalField("Albumin (g)", max_digits=6, decimal_places=1, null=True, blank=True)
    del _p

    kcal_manuell = models.PositiveIntegerField(
        "kcal (manuell)", null=True, blank=True, help_text="Überschreibt die berechneten kcal"
    )
    laufzeit_h = models.DecimalField("Laufzeit (h)", max_digits=4, decimal_places=1, null=True, blank=True)
    tage_pro_woche = models.PositiveSmallIntegerField("Tage pro Woche", null=True, blank=True)
    katheterschutz = models.ForeignKey(
        Praeparat, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        limit_choices_to={"kategorie": Praeparat.Kategorie.KATHETERSCHUTZ}, verbose_name="Katheterschutz (Lock)",
    )
    pantozol_stufe = models.PositiveSmallIntegerField(
        "Pantozol", default=0, help_text="0–3 wie im Altsystem (Bedeutung wird noch festgelegt)"
    )
    pantozol_tage = models.PositiveSmallIntegerField("Pantozol Tage", null=True, blank=True)
    bemerkung = models.TextField(blank=True)

    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    freigegeben_am = models.DateTimeField(null=True, blank=True)
    freigegeben_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # Bei Freigabe erzeugte PDF (kommt mit den Dokumentvorlagen); wird nie neu erzeugt
    pdf_datei = models.CharField(max_length=255, blank=True)
    pdf_sha256 = models.CharField(max_length=64, blank=True)
    vorlage_version = models.PositiveIntegerField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Infusionsplan"
        verbose_name_plural = "Infusionspläne"
        ordering = ["-gueltig_ab", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["patient"], condition=models.Q(status="entwurf"), name="ein_entwurf_je_patient"
            ),
            models.UniqueConstraint(
                fields=["patient"], condition=models.Q(status="aktuell"), name="ein_aktueller_plan_je_patient"
            ),
            models.CheckConstraint(
                name="pantozol_bereich",
                condition=models.Q(pantozol_stufe__lte=3)
                & (models.Q(pantozol_tage__isnull=True) | models.Q(pantozol_tage__range=(1, 7))),
            ),
            models.CheckConstraint(
                name="tage_pro_woche_bereich",
                condition=models.Q(tage_pro_woche__isnull=True) | models.Q(tage_pro_woche__range=(1, 7)),
            ),
        ]

    def __str__(self):
        return f"Infusionsplan {self.patient.nummer} ab {self.gueltig_ab:%d.%m.%Y} ({self.get_status_display()})"

    # --- Regeln ---
    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.pk and not (update_fields and set(update_fields) <= {"status"}):
            alt_status = Infusionsplan.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if alt_status != self.Status.ENTWURF:
                raise PermissionError("Freigegebene Pläne sind unveränderlich. Bitte einen neuen Plan anlegen.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.ENTWURF:
            raise PermissionError("Nur Entwürfe können verworfen werden.")
        return super().delete(*args, **kwargs)

    @property
    def kcal_berechnet(self) -> int:
        summe = sum((getattr(self, f) or Decimal(0)) * faktor for f, faktor in KCAL_JE_G.items())
        return int(summe.quantize(Decimal(1)))

    @property
    def kcal(self) -> int:
        return self.kcal_manuell if self.kcal_manuell is not None else self.kcal_berechnet

    def clean(self):
        fehler = {}
        e = Einstellungen.aktuell()
        if self.kcal > e.kcal_max_tag:
            fehler["kcal_manuell"] = f"{self.kcal} kcal liegen über der Plausibilitätsgrenze von {e.kcal_max_tag} kcal."
        if self.pantozol_stufe and not self.pantozol_tage:
            fehler["pantozol_tage"] = "Bitte Tage angeben, wenn Pantozol gesetzt ist."
        if not self.pantozol_stufe and self.pantozol_tage:
            fehler["pantozol_tage"] = "Tage nur angeben, wenn Pantozol gesetzt ist."
        for feld, praep in [("glucose_g", "glucose_praeparat"), ("aminosaeuren_g", "aminosaeuren_praeparat"),
                            ("lipide_g", "lipide_praeparat"), ("albumin_g", "albumin_praeparat")]:
            if getattr(self, feld) and not getattr(self, f"{praep}_id"):
                fehler[praep] = "Bitte das Präparat auswählen."
        if fehler:
            raise ValidationError(fehler)

    def geaenderte_felder(self) -> list[str]:
        """Felder, die sich gegenüber dem Vorgänger geändert haben (für die Markierung im Plan)."""
        if not self.vorgaenger_id:
            return []
        v = self.vorgaenger
        felder = [f for f in PLANFELDER if getattr(self, _attr(f)) != getattr(v, _attr(f))]
        if _positionen_signatur(self) != _positionen_signatur(v):
            felder.append("positionen")
        return felder

    # --- Abläufe ---
    @classmethod
    @transaction.atomic
    def neuer_entwurf(cls, patient: Patient, benutzer) -> "Infusionsplan":
        """Legt einen Entwurf an, vorbelegt mit dem aktuellen Plan (inkl. Positionen)."""
        patient.pruefe_bearbeitbar()
        if cls.objects.filter(patient=patient, status=cls.Status.ENTWURF).exists():
            raise ValidationError("Für diesen Patienten gibt es bereits einen Entwurf.")
        aktuell = cls.objects.filter(patient=patient, status=cls.Status.AKTUELL).first()
        entwurf = cls(patient=patient, erstellt_von=benutzer, vorgaenger=aktuell)
        if aktuell:
            for f in PLANFELDER:
                setattr(entwurf, _attr(f), getattr(aktuell, _attr(f)))
        entwurf.save()
        if aktuell:
            bulk_create_with_history(
                [InfusionsplanPosition(
                    plan=entwurf, praeparat_id=p.praeparat_id, menge=p.menge, einheit=p.einheit,
                    haeufigkeit=p.haeufigkeit, bemerkung=p.bemerkung, reihenfolge=p.reihenfolge,
                )
                 for p in aktuell.positionen.all()],
                InfusionsplanPosition,
                default_user=benutzer,
            )
        return entwurf

    @transaction.atomic
    def freigeben(self, benutzer):
        if self.status != self.Status.ENTWURF:
            raise ValidationError("Nur Entwürfe können freigegeben werden.")
        if not getattr(benutzer, "darf_plaene_bearbeiten", False):
            raise PermissionError("Nur Mediziner geben Infusionspläne frei.")
        self.patient.pruefe_bearbeitbar()
        self.full_clean()
        alt = Infusionsplan.objects.select_for_update().filter(
            patient=self.patient, status=self.Status.AKTUELL
        ).first()
        if alt:
            alt.status = self.Status.ABGELOEST
            alt.save(update_fields=["status"])
        self.status = self.Status.AKTUELL
        self.freigegeben_am = timezone.now()
        self.freigegeben_von = benutzer
        super().save()  # letzter Schreibvorgang am Entwurf, danach gesperrt


class InfusionsplanPosition(models.Model):
    """Weitere Bestandteile: Elektrolyte, Vitamine, Spurenelemente, Medikamente …"""

    plan = models.ForeignKey(Infusionsplan, on_delete=models.CASCADE, related_name="positionen")
    praeparat = models.ForeignKey(Praeparat, on_delete=models.PROTECT, related_name="+")
    menge = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    einheit = models.CharField(max_length=10, blank=True)
    haeufigkeit = models.CharField("Häufigkeit", max_length=60, blank=True, help_text="z. B. täglich, Mo/Mi/Fr")
    bemerkung = models.CharField(max_length=200, blank=True)
    reihenfolge = models.PositiveSmallIntegerField(default=0)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Position"
        verbose_name_plural = "Positionen"
        ordering = ["reihenfolge", "id"]

    def _pruefe(self):
        if self.plan.status != Infusionsplan.Status.ENTWURF:
            raise PermissionError("Positionen freigegebener Pläne sind unveränderlich.")
        self.plan.patient.pruefe_bearbeitbar()

    def save(self, *args, **kwargs):
        self._pruefe()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._pruefe()
        return super().delete(*args, **kwargs)


def _attr(feld: str) -> str:
    """Fremdschlüssel über die *_id-Spalte vergleichen/kopieren (keine Zusatzabfragen)."""
    fk = {"basis_praeparat", "glucose_praeparat", "aminosaeuren_praeparat", "lipide_praeparat",
          "albumin_praeparat", "katheterschutz"}
    return f"{feld}_id" if feld in fk else feld


def _positionen_signatur(plan):
    return [
        (p.praeparat_id, p.menge, p.einheit, p.haeufigkeit, p.bemerkung)
        for p in plan.positionen.order_by("reihenfolge", "id")
    ]
