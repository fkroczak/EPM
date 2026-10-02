"""Infusionspläne: Entwurf → aktuell → abgelöst. Nach Freigabe unveränderlich."""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from simple_history.models import HistoricalRecords
from simple_history.utils import bulk_create_with_history

from patienten.models import AktenEintrag, Gewichtsmessung, Patient
from stammdaten.models import Einstellungen, Praeparat

# Energiegehalt je Gramm wie im Altsystem (EPM_infuplan.php: amino*4 + gluco*4 + fett*9.15; Festlegung 01.10.2026).
# Humanalbumin wird wie dort in ml erfasst und zählt nicht zur Energie.
KCAL_JE_G = {
    "glucose_g": Decimal(4),
    "aminosaeuren_g": Decimal(4),
    "lipide_g": Decimal("9.15"),
}

# Vorbelegung des ersten Plans je kg Körpergewicht wie im Altsystem (EPM_infuplan.php; Festlegung 01.10.2026)
VORBELEGUNG_JE_KG = {
    "glucose_g": Decimal("3.5"),
    "aminosaeuren_g": Decimal("1.2"),
    "lipide_g": Decimal("1"),
    "natrium_mmol": Decimal("1.3"),
    "kalium_mmol": Decimal("0.7"),
    "phosphat_mmol": Decimal("0.3"),
    "calcium_mmol": Decimal("0.15"),
    "magnesium_mmol": Decimal("0.2"),
}

# Stabilität wie im Altsystem: Calcium + Magnesium (mmol) dürfen Gesamtvolumen ÷ 100 nicht übersteigen
CA_MG_ML_JE_MMOL = Decimal(100)

# Gesamtvolumen = Körpergewicht × 35 ml (wie im Altsystem: $volum = round($gewicht * 35, 2); Festlegung 01.10.2026)
ML_JE_KG = Decimal(35)

# Protonenpumpenhemmer als Kurzinfusion – Codes wie im Altsystem (EPM_infuplan.php), damit der Import passt
class Protonenpumpenhemmer(models.IntegerChoices):
    KEIN = 0, "kein"
    PANTOZOL_40 = 1, "Pantozol® 40 mg"
    NEXIUM = 2, "Nexium®"
    PANTOZOL_20 = 3, "Pantozol® 20 mg"


# Zeiten als Bitmaske wie im Altsystem (panzeit = 4 morgens + 2 mittags + 1 abends; meist 5 = morgens und abends)
PPI_ZEITEN = [(4, "morgens"), (2, "mittags"), (1, "abends")]


def ppi_zeiten_text(maske) -> str:
    return ", ".join(name for bit, name in PPI_ZEITEN if maske and maske & bit)


# Felder, die beim neuen Entwurf vom aktuellen Plan übernommen und auf Änderung verglichen werden
PLANFELDER = [
    "basis_praeparat", "basis_ml", "glucose_praeparat", "glucose_g", "aminosaeuren_praeparat", "aminosaeuren_g",
    "lipide_praeparat", "lipide_g", "albumin_praeparat", "albumin_ml",
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
    ("mischbeutel", "Volumen im Mischbeutel"), ("gesamtvolumen", "Gesamtvolumen"), ("laufzeit_h", "Laufzeit"),
    ("rate", "Rate"),
    ("tage_pro_woche", "Tage pro Woche"), ("kcal", "Energie"),
    ("pantozol", "Protonenpumpenhemmer"), ("positionen", "Weitere Bestandteile"), ("bemerkung", "Bemerkung"),
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
    albumin_ml = models.DecimalField("Humanalbumin (ml)", max_digits=6, decimal_places=1, null=True, blank=True)
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
        "Protonenpumpenhemmer", default=0, choices=Protonenpumpenhemmer.choices,
        help_text="als Kurzinfusion; Codes wie im Altsystem (Feld pantozol)",
    )
    pantozol_tage = models.PositiveSmallIntegerField(
        "Zeiten", null=True, blank=True, help_text="Bitmaske wie im Altsystem (panzeit): 4 morgens, 2 mittags, 1 abends"
    )
    # berechnet aus dem letzten Gewicht (nicht eingebbar); bleibt mit dem Plan nach der Freigabe unverändert
    gesamtvolumen_ml = models.DecimalField("Gesamtvolumen (ml)", max_digits=7, decimal_places=2, null=True, blank=True,
                                           editable=False)
    volumen_gewicht_kg = models.DecimalField("Gewicht für das Gesamtvolumen (kg)", max_digits=5, decimal_places=1,
                                             null=True, blank=True, editable=False)
    bemerkung = models.TextField(blank=True)

    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    freigegeben_am = models.DateTimeField(null=True, blank=True)
    freigegeben_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    # Freigabe auf Anordnung (Festlegung 02.10.2026): Der Mediziner gibt z. B. per E-Mail frei, ein Mitarbeiter
    # schließt den Plan danach im System ab. ``freigegeben_von`` ist immer der Mediziner, ``abgeschlossen_von`` die
    # Person, die den Plan im System abgeschlossen hat (leer = der Mediziner selbst).
    class Freigabeweg(models.TextChoices):
        SYSTEM = "system", "im System"
        EMAIL = "email", "per E-Mail"
        TELEFON = "telefon", "telefonisch"
        PERSOENLICH = "persoenlich", "persönlich"
        SCHRIFTLICH = "schriftlich", "schriftlich"

    freigabe_weg = models.CharField("Weg der Freigabe", max_length=20, choices=Freigabeweg.choices, blank=True)
    freigabe_datum = models.DateField("Datum der Freigabe durch den Mediziner", null=True, blank=True)
    abgeschlossen_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        verbose_name="Im System abgeschlossen von",
    )
    freigabe_nachweis = models.ForeignKey(
        "patienten.Dokument", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        verbose_name="Nachweis der Freigabe (z. B. die E-Mail)",
    )
    # Aus dem Altsystem übernommene Pläne (F65) haben keinen Freigabevermerk und keine gespeicherte PDF – beides gab es
    # dort nicht. Der jüngste Plan je Patient wird als „aktuell“ übernommen, die früheren als „abgelöst“.
    class Herkunft(models.TextChoices):
        EPM = "epm", "In EPM angelegt"
        ALTSYSTEM = "altsystem", "Aus dem Altsystem übernommen"

    herkunft = models.CharField(max_length=20, choices=Herkunft.choices, default=Herkunft.EPM, editable=False)
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
        nur_status = bool(update_fields and set(update_fields) <= {"status"})
        if not nur_status:
            if self.pk:
                alt_status = Infusionsplan.objects.filter(pk=self.pk).values_list("status", flat=True).first()
                if alt_status != self.Status.ENTWURF:
                    raise PermissionError("Freigegebene Pläne sind unveränderlich. Bitte einen neuen Plan anlegen.")
            if self.patient_id:
                self.berechne_volumen()  # Entwurf: immer mit dem aktuellen Gewicht; mit der Freigabe eingefroren
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.ENTWURF:
            raise PermissionError("Nur Entwürfe können verworfen werden.")
        return super().delete(*args, **kwargs)

    @property
    def kcal_berechnet(self) -> int:
        summe = sum((getattr(self, f) or Decimal(0)) * faktor for f, faktor in KCAL_JE_G.items())
        return int(Decimal(summe).quantize(Decimal(1), rounding=ROUND_HALF_UP))

    @property
    def kcal(self) -> int:
        return self.kcal_manuell if self.kcal_manuell is not None else self.kcal_berechnet

    @property
    def ca_mg_mmol(self):
        if self.calcium_mmol is None and self.magnesium_mmol is None:
            return None
        return (self.calcium_mmol or Decimal(0)) + (self.magnesium_mmol or Decimal(0))

    @property
    def ca_mg_grenze_mmol(self):
        return None if self.gesamtvolumen_ml is None else (self.gesamtvolumen_ml / CA_MG_ML_JE_MMOL).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def ca_mg_stabil(self):
        """Wie im Altsystem: instabil, wenn Ca + Mg (mmol) > Gesamtvolumen ÷ 100. Nur Hinweis, kein Speicherverbot."""
        if self.ca_mg_mmol is None or self.ca_mg_grenze_mmol is None:
            return None
        return self.ca_mg_mmol <= self.ca_mg_grenze_mmol

    def berechne_volumen(self):
        """Gesamtvolumen aus dem letzten erfassten Gewicht (35 ml/kg); ohne Gewicht leer."""
        letztes = (Gewichtsmessung.objects.filter(patient_id=self.patient_id)
                   .order_by("-gemessen_am", "-id").values_list("gewicht_kg", flat=True).first())
        self.volumen_gewicht_kg = letztes
        self.gesamtvolumen_ml = (letztes * ML_JE_KG).quantize(Decimal("0.01")) if letztes is not None else None

    @property
    def volumen_summe_ml(self):
        """Gesamtvolumen wie auf der alten PDF: Volumen im Mischbeutel (Gewicht × 35 ml) + Zusatzvolumen (Basislösung)."""
        if self.gesamtvolumen_ml is None:
            return None
        return self.gesamtvolumen_ml + Decimal(self.basis_ml or 0)

    @property
    def rate_ml_h(self):
        """Rate = Gesamtvolumen (Mischbeutel + Zusatzvolumen) ÷ Laufzeit (ml/h); Festlegung 01.10.2026."""
        if self.volumen_summe_ml is None or not self.laufzeit_h:
            return None
        return (self.volumen_summe_ml / self.laufzeit_h).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    def clean(self):
        fehler = {}
        e = Einstellungen.aktuell()
        if self.status == self.Status.ENTWURF and self.patient_id:
            self.berechne_volumen()
        if self.gesamtvolumen_ml is not None and not (e.volumen_min_ml <= self.gesamtvolumen_ml <= e.volumen_max_ml):
            fehler["gesamtvolumen_ml"] = (f"Volumen im Mischbeutel {_zahl(self.gesamtvolumen_ml, 'ml')} liegt außerhalb der "
                                          f"Plausibilitätsgrenzen ({_zahl(e.volumen_min_ml)}–{_zahl(e.volumen_max_ml)} ml).")
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
        if self.pantozol_stufe not in Protonenpumpenhemmer.values:
            fehler["pantozol_stufe"] = "Unbekannter Protonenpumpenhemmer."
        if self.pantozol_tage is not None and not 0 < self.pantozol_tage <= 7:
            fehler["pantozol_tage"] = "Zeiten: morgens, mittags und/oder abends."
        if self.pantozol_stufe and not self.pantozol_tage:
            fehler["pantozol_tage"] = "Bitte die Zeiten angeben (morgens, mittags, abends)."
        if not self.pantozol_stufe and self.pantozol_tage:
            fehler["pantozol_tage"] = "Zeiten nur angeben, wenn ein Protonenpumpenhemmer gewählt ist."
        for feld, praep in [("glucose_g", "glucose_praeparat"), ("aminosaeuren_g", "aminosaeuren_praeparat"),
                            ("lipide_g", "lipide_praeparat"), ("albumin_ml", "albumin_praeparat")]:
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

    # Wege, bei denen es ein Schriftstück gibt: Der Nachweis (z. B. die E-Mail) gehört an den Plan
    NACHWEIS_PFLICHT = {Freigabeweg.EMAIL, Freigabeweg.SCHRIFTLICH}

    @transaction.atomic
    def freigeben(self, benutzer):
        """Freigabe durch den Mediziner selbst, direkt im System."""
        if not getattr(benutzer, "darf_plaene_freigeben", False):
            raise PermissionError("Infusionspläne freigeben darf nur, wer das Recht dazu hat.")
        self._freigabe(mediziner=benutzer, abschliessend=None, weg=self.Freigabeweg.SYSTEM,
                       datum=timezone.localdate(), nachweis=None)

    @transaction.atomic
    def abschliessen_auf_anordnung(self, benutzer, mediziner, datum, weg, nachweis=None):
        """Der Mediziner hat außerhalb des Systems freigegeben (z. B. per E-Mail); ``benutzer`` schließt den Plan ab.
        Festgehalten werden: wer freigegeben hat, wann, auf welchem Weg, der Nachweis und wer abgeschlossen hat."""
        from accounts.models import Rolle

        if not benutzer.hat_recht("plaene_abschliessen"):
            raise PermissionError("Dafür fehlt das Recht „Infusionspläne nach Freigabe abschließen“.")
        fehler = {}
        if (mediziner is None or mediziner.rolle != Rolle.MEDIZINER or not mediziner.is_active
                or not mediziner.hat_recht("plaene_freigeben")
                or (mediziner.ist_test and not self.patient.ist_test)):
            fehler["freigegeben_von"] = "Bitte den Mediziner wählen, der den Plan freigegeben hat."
        if weg not in self.Freigabeweg.values or weg == self.Freigabeweg.SYSTEM:
            fehler["weg"] = "Bitte angeben, auf welchem Weg freigegeben wurde."
        if datum is None:
            fehler["freigegeben_am"] = "Bitte das Datum der Freigabe angeben."
        elif datum > timezone.localdate():
            fehler["freigegeben_am"] = "Das Datum liegt in der Zukunft."
        elif self.erstellt_am and datum < timezone.localtime(self.erstellt_am).date():
            fehler["freigegeben_am"] = "Die Freigabe liegt vor dem Anlegen des Plans."
        if weg in self.NACHWEIS_PFLICHT and nachweis is None:
            fehler["nachweis"] = "Bitte den Nachweis der Freigabe anhängen (z. B. die E-Mail als PDF)."
        if nachweis is not None and nachweis.patient_id != self.patient_id:
            fehler["nachweis"] = "Der Nachweis gehört zu einer anderen Akte."
        if fehler:
            raise ValidationError(fehler)
        # Der Vermerk auf der PDF muss beide Personen nennen – das leistet nur das Datenfeld „Freigabevermerk“.
        import json
        import re

        from vorlagen.models import Dokumentvorlage

        vorlage = json.dumps(Dokumentvorlage.aktive("infusionsplan").bloecke, ensure_ascii=False)
        if not re.search(r"\{\{\s*Plan\.Freigabevermerk\s*\}\}", vorlage):
            raise ValidationError({"fehler": "Die Dokumentvorlage „Infusionsplan“ enthält das Datenfeld „Freigabevermerk“ "
                                             "nicht. Ohne es nennt die PDF nicht, wer den Plan abgeschlossen hat. Bitte "
                                             "unter Vorlagen › Dokumentvorlagen ergänzen und veröffentlichen."})
        self._freigabe(mediziner=mediziner, abschliessend=benutzer, weg=weg, datum=datum, nachweis=nachweis)

    def _freigabe(self, mediziner, abschliessend, weg, datum, nachweis):
        if self.status != self.Status.ENTWURF:
            raise ValidationError("Nur Entwürfe können freigegeben werden.")
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
        self.freigegeben_von = mediziner
        self.freigabe_weg = weg
        self.freigabe_datum = datum
        self.abgeschlossen_von = abschliessend
        self.freigabe_nachweis = nachweis
        # PDF mit der aktiven Vorlage erzeugen, als Dokument „Von EPM erzeugt“ ablegen, Prüfsumme und Vorlagenversion
        # am Plan festhalten (F35/F51). Scheitert die PDF, wird nicht freigegeben.
        dok = self._pdf_ablegen(abschliessend or mediziner)
        try:
            super().save()  # letzter Schreibvorgang am Entwurf, danach gesperrt
        except BaseException:
            dok.pfad.unlink(missing_ok=True)
            raise

    @property
    def freigabe_tag(self):
        """Tag der Freigabe durch den Mediziner (bei Freigabe auf Anordnung das angegebene Datum)."""
        if self.freigabe_datum:
            return self.freigabe_datum
        return timezone.localtime(self.freigegeben_am).date() if self.freigegeben_am else None

    @property
    def freigabevermerk(self) -> str | None:
        """Vermerk statt Unterschrift – nennt, wer freigegeben hat, und bei Freigabe auf Anordnung auch den Weg und
        wer den Plan im System abgeschlossen hat (der Vermerk muss stimmen). Aus dem Altsystem übernommene Pläne
        tragen statt einer Freigabe ihre Herkunft – eine Freigabe im Sinne des EPM gab es dort nicht."""
        from epm.api_basis import benutzername

        if self.herkunft == self.Herkunft.ALTSYSTEM:
            wer = f" von {benutzername(self.erstellt_von)}" if self.erstellt_von_id else ""
            wann = f"{timezone.localtime(self.erstellt_am):%d.%m.%Y}" if self.erstellt_am else f"{self.gueltig_ab:%d.%m.%Y}"
            return f"Aus dem Altsystem übernommen; dort angelegt am {wann}{wer}."
        if not self.freigegeben_von_id or not self.freigabe_tag:
            return None

        mediziner, tag = benutzername(self.freigegeben_von), f"{self.freigabe_tag:%d.%m.%Y}"
        if not self.abgeschlossen_von_id:
            return f"Maschinell erstellt, geprüft und freigegeben von {mediziner} am {tag}."
        weg = self.get_freigabe_weg_display() if self.freigabe_weg else ""
        abschluss = f"{timezone.localtime(self.freigegeben_am):%d.%m.%Y}" if self.freigegeben_am else tag
        return (f"Maschinell erstellt. Geprüft und freigegeben von {mediziner} am {tag}"
                f"{f' ({weg})' if weg else ''}; im System abgeschlossen von {benutzername(self.abgeschlossen_von)} "
                f"am {abschluss}.")

    def _pdf_ablegen(self, benutzer):
        from vorlagen.felder import Kontext
        from vorlagen.pdf import als_dokument, erzeuge_aus_vorlage, wasserzeichen_fuer

        p = self.patient
        titel = f"Infusionsplan gültig ab {self.gueltig_ab:%d.%m.%Y}"
        pdf, version = erzeuge_aus_vorlage("infusionsplan", Kontext(patient=p, plan=self),
                                           wasserzeichen=wasserzeichen_fuer(p, self),
                                           titel=f"{titel} – {p.nachname}, {p.vorname}")
        dok = als_dokument(p, pdf, titel, "Infusionsplan", self.gueltig_ab, benutzer,
                           f"Infusionsplan-{p.nummer}-{self.gueltig_ab:%Y-%m-%d}.pdf")
        self.pdf_datei, self.pdf_sha256, self.vorlage_version = dok.datei, dok.sha256, version
        return dok


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
        menge = _zahl(plan.albumin_ml, "ml") if schluessel == "albumin" else _zahl(getattr(plan, f"{schluessel}_g"), "g")
        teile = [str(praep) if praep else None, menge]
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
    if schluessel == "gesamtvolumen":
        return _zahl(plan.volumen_summe_ml, "ml")
    if schluessel == "mischbeutel":
        if plan.gesamtvolumen_ml is None:
            return None
        return f"{_zahl(plan.gesamtvolumen_ml, 'ml')} (35 ml/kg × {_zahl(plan.volumen_gewicht_kg, 'kg')})"
    if schluessel == "rate":
        return _zahl(plan.rate_ml_h, "ml/h")
    if schluessel == "tage_pro_woche":
        return _zahl(plan.tage_pro_woche, "× pro Woche")
    if schluessel == "kcal":
        return _zahl(plan.kcal, "kcal") + (" (manuell)" if plan.kcal_manuell is not None else "")
    if schluessel == "pantozol":
        if not plan.pantozol_stufe:
            return None
        zeiten = ppi_zeiten_text(plan.pantozol_tage)
        return f"{Protonenpumpenhemmer(plan.pantozol_stufe).label} · {zeiten}" if zeiten else Protonenpumpenhemmer(plan.pantozol_stufe).label
    if schluessel == "positionen":
        if not plan.pk:
            return None
        teile = []
        for x in plan.positionen.select_related("praeparat"):
            t = " ".join(filter(None, [str(x.praeparat), _zahl(x.menge, x.einheit) if x.menge is not None else x.einheit]))
            zusatz = ", ".join(filter(None, [x.haeufigkeit, x.bemerkung]))
            teiles = f"{t} ({zusatz})" if zusatz else t
            teile.append(teiles)
        return " | ".join(teile) or None
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


def vorbelegung(patient):
    """Werte für den ersten Plan aus dem letzten Gewicht (je kg wie im Altsystem), auf die Feldgenauigkeit 0,1 gerundet."""
    gewicht = (Gewichtsmessung.objects.filter(patient=patient)
               .order_by("-gemessen_am", "-id").values_list("gewicht_kg", flat=True).first())
    werte = None
    if gewicht is not None:
        werte = {f: (gewicht * je_kg).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) for f, je_kg in VORBELEGUNG_JE_KG.items()}
    return {"gewicht_kg": gewicht, "je_kg": VORBELEGUNG_JE_KG, "werte": werte}
