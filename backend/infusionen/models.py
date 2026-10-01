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
    "lipide_praeparat", "lipide_g", "albumin_praeparat", "albumin_g",
    "natrium_mmol", "kalium_mmol", "phosphat_mmol", "calcium_mmol", "magnesium_mmol",
    "spurenelemente", "katheterschutz", "kcal_manuell",
    "laufzeit_h", "tage_pro_woche", "pantozol_stufe", "pantozol_tage", "bemerkung",
]

# Bezeichnungen und Einheiten für Vergleich und PDF (Reihenfolge wie im Entwurf 8)
VERGLEICHSZEILEN = [
    ("basis", "Basislösung"), ("glucose", "Glucose"), ("aminosaeuren", "Aminosäuren"), ("lipide", "Lipide"),
    ("albumin", "Humanalbumin"), ("natrium_mmol", "Natrium"), ("kalium_mmol", "Kalium"),
    ("phosphat_mmol", "Phosphat"), ("calcium_mmol", "Calcium"), ("magnesium_mmol", "Magnesium"),
    ("spurenelemente", "Spurenelemente"), ("vitamine", "Vitamine"), ("katheterschutz", "Katheterblock"),
    ("laufzeit_h", "Laufzeit"), ("tage_pro_woche", "Tage pro Woche"), ("kcal", "Energie"),
    ("pantozol", "Pantozol"), ("bemerkung", "Bemerkung"),
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
    spurenelemente = _p(Praeparat.Kategorie.SPURENELEMENTE, "Spurenelemente")
    del _p

    # Elektrolyte in mmol (Entwurf 7)
    natrium_mmol = models.DecimalField("Natrium (mmol)", max_digits=6, decimal_places=1, null=True, blank=True)
    kalium_mmol = models.DecimalField("Kalium (mmol)", max_digits=6, decimal_places=1, null=True, blank=True)
    phosphat_mmol = models.DecimalField("Phosphat (mmol)", max_digits=6, decimal_places=1, null=True, blank=True)
    calcium_mmol = models.DecimalField("Calcium (mmol)", max_digits=6, decimal_places=1, null=True, blank=True)
    magnesium_mmol = models.DecimalField("Magnesium (mmol)", max_digits=6, decimal_places=1, null=True, blank=True)
    vitamine = models.ManyToManyField(
        Praeparat, blank=True, related_name="+", limit_choices_to={"kategorie": Praeparat.Kategorie.VITAMINE},
        verbose_name="Vitamine",
    )

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

    history = HistoricalRecords(m2m_fields=[vitamine])

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
        if not (e.kcal_min_tag <= self.kcal <= e.kcal_max_tag):
            fehler["kcal_manuell"] = (f"{self.kcal} kcal liegen außerhalb der Plausibilitätsgrenzen "
                                      f"({e.kcal_min_tag}–{e.kcal_max_tag} kcal).")
        for feld, unten, oben, einheit in [
            ("glucose_g", e.glucose_min_g, e.glucose_max_g, "g"),
            ("aminosaeuren_g", e.aminosaeuren_min_g, e.aminosaeuren_max_g, "g"),
            ("lipide_g", e.lipide_min_g, e.lipide_max_g, "g"),
            ("natrium_mmol", e.natrium_min_mmol, e.natrium_max_mmol, "mmol"),
            ("kalium_mmol", e.kalium_min_mmol, e.kalium_max_mmol, "mmol"),
        ]:
            wert = getattr(self, feld)
            if wert is not None and not (unten <= wert <= oben):
                fehler[feld] = f"Wert außerhalb der Plausibilitätsgrenzen ({unten}–{oben} {einheit})."
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
        if self.pk and set(self.vitamine.values_list("pk", flat=True)) != set(v.vitamine.values_list("pk", flat=True)):
            felder.append("vitamine")
        if _positionen_signatur(self) != _positionen_signatur(v):
            felder.append("positionen")
        return felder

    # --- Abläufe ---
    @classmethod
    @transaction.atomic
    def neuer_entwurf(cls, patient: Patient, benutzer, leer: bool = False, vorlage: "Infusionsplan | None" = None):
        """Legt einen Entwurf an.

        Standard: vorbelegt mit dem aktuellen Plan. ``leer``: ohne Vorbelegung („Leer beginnen“).
        ``vorlage``: vorbelegt mit einem früheren Plan desselben Patienten („Als Vorlage für neuen Plan“).
        Vorgänger ist immer der aktuelle Plan, damit der Vergleich die tatsächliche Änderung zeigt.
        """
        patient.pruefe_bearbeitbar()
        if cls.objects.filter(patient=patient, status=cls.Status.ENTWURF).exists():
            raise ValidationError("Für diesen Patienten gibt es bereits einen Entwurf.")
        if vorlage is not None and vorlage.patient_id != patient.id:
            raise ValidationError({"vorlage": "Die Vorlage gehört zu einem anderen Patienten."})
        aktuell = cls.objects.filter(patient=patient, status=cls.Status.AKTUELL).first()
        quelle = None if leer else (vorlage or aktuell)
        entwurf = cls(patient=patient, erstellt_von=benutzer, vorgaenger=aktuell)
        if quelle:
            for f in PLANFELDER:
                setattr(entwurf, _attr(f), getattr(quelle, _attr(f)))
        entwurf._history_user = benutzer
        entwurf.save()
        if quelle:
            entwurf.vitamine.set(quelle.vitamine.all())
            bulk_create_with_history(
                [InfusionsplanPosition(
                    plan=entwurf, praeparat_id=p.praeparat_id, menge=p.menge, einheit=p.einheit,
                    haeufigkeit=p.haeufigkeit, bemerkung=p.bemerkung, reihenfolge=p.reihenfolge,
                ) for p in quelle.positionen.all()],
                InfusionsplanPosition,
                default_user=benutzer,
            )
        return entwurf

    def vergleich(self) -> dict:
        """Alle Werte neben denen des Vorgängers (Entwurf 8 · „Vergleich mit Vorgänger“)."""
        v = self.vorgaenger
        zeilen = []
        for schluessel, bezeichnung in VERGLEICHSZEILEN:
            jetzt = _anzeige(self, schluessel)
            vorher = _anzeige(v, schluessel) if v else None
            zeilen.append({"schluessel": schluessel, "wert": bezeichnung, "vorher": vorher, "jetzt": jetzt,
                           "geaendert": v is not None and vorher != jetzt})
        return {
            "vorgaenger": {"id": v.id, "gueltig_ab": v.gueltig_ab, "status": v.status} if v else None,
            "zeilen": zeilen,
            "anzahl_geaendert": sum(z["geaendert"] for z in zeilen),
        }

    @transaction.atomic
    def freigeben(self, benutzer):
        if self.status != self.Status.ENTWURF:
            raise ValidationError("Nur Entwürfe können freigegeben werden.")
        if not getattr(benutzer, "darf_plaene_freigeben", False):
            raise PermissionError("Infusionspläne freigeben darf nur, wer das Recht dazu hat.")
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
          "albumin_praeparat", "katheterschutz", "spurenelemente"}
    return f"{feld}_id" if feld in fk else feld


def _positionen_signatur(plan):
    return [
        (p.praeparat_id, p.menge, p.einheit, p.haeufigkeit, p.bemerkung)
        for p in plan.positionen.order_by("reihenfolge", "id")
    ]


def _zahl(wert, einheit=""):
    """Deutsche Schreibweise wie auf dem Plan: 1.480 kcal, 13,5 g, 500 ml."""
    if wert is None:
        return None
    if isinstance(wert, Decimal):
        text = f"{wert:,f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
    else:
        text = f"{wert:,}"
    text = text.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{text} {einheit}".strip()


def _anzeige(plan, schluessel):
    """Anzeigetext eines Planwerts, so wie er auf dem Plan steht."""
    if plan is None:
        return None
    if schluessel == "basis":
        teile = [str(plan.basis_praeparat) if plan.basis_praeparat_id else None, _zahl(plan.basis_ml, "ml")]
        return " · ".join(t for t in teile if t) or None
    if schluessel in ("glucose", "aminosaeuren", "lipide", "albumin"):
        praep = getattr(plan, f"{schluessel}_praeparat")
        teile = [str(praep) if praep else None, _zahl(getattr(plan, f"{schluessel}_g"), "g")]
        return " · ".join(t for t in teile if t) or None
    if schluessel.endswith("_mmol"):
        return _zahl(getattr(plan, schluessel), "mmol")
    if schluessel in ("spurenelemente", "katheterschutz"):
        praep = getattr(plan, schluessel)
        return str(praep) if praep else None
    if schluessel == "vitamine":
        namen = [str(p) for p in plan.vitamine.all()] if plan.pk else []
        return " | ".join(namen) or None
    if schluessel == "laufzeit_h":
        return _zahl(plan.laufzeit_h, "h")
    if schluessel == "tage_pro_woche":
        return _zahl(plan.tage_pro_woche, "× pro Woche")
    if schluessel == "kcal":
        return _zahl(plan.kcal, "kcal") + (" (manuell)" if plan.kcal_manuell is not None else "")
    if schluessel == "pantozol":
        return f"{plan.pantozol_stufe} · {plan.pantozol_tage}" if plan.pantozol_stufe else None
    if schluessel == "bemerkung":
        return plan.bemerkung or None
    return None


def _vitamine_schutz(sender, instance, action, **kwargs):
    """Vitamine eines freigegebenen Plans dürfen nicht mehr geändert werden."""
    if action in ("pre_add", "pre_remove", "pre_clear") and isinstance(instance, Infusionsplan):
        if instance.status != Infusionsplan.Status.ENTWURF:
            raise PermissionError("Freigegebene Pläne sind unveränderlich. Bitte einen neuen Plan anlegen.")


models.signals.m2m_changed.connect(_vitamine_schutz, sender=Infusionsplan.vitamine.through,
                                   dispatch_uid="epm_vitamine_schutz")
