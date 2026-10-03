"""Dokumentvorlagen (Entwurf 18 · Dokumentvorlagen): Infusionsplan, Patientendatenblatt und die Erklärungen zum
Datenschutz (Datenschutzinformation, Einwilligung, Schweigepflichtentbindung) aus Blöcken.

Je Art gibt es höchstens einen Entwurf und genau eine aktive Version. Veröffentlichen macht aus dem Entwurf die
nächste Version; die bisherige wird „abgelöst“ und bleibt erhalten. Veröffentlichte Versionen sind unveränderlich
(Modell und Datenbank-Trigger), damit jede gespeicherte PDF auf ihre Vorlagenversion zurückgeführt werden kann.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from simple_history.models import HistoricalRecords


class Dokumentvorlage(models.Model):
    class Art(models.TextChoices):
        INFUSIONSPLAN = "infusionsplan", "Infusionsplan"
        PATIENTENDATENBLATT = "patientendatenblatt", "Patientendatenblatt"
        # Datenschutz (Festlegung 02.10.2026): zum Ausdrucken und Unterschreiben je Patient. Die mitgelieferten
        # Startvorlagen sind Entwürfe mit Lücken in [eckigen Klammern]; bis die Stiftung sie geprüft und
        # veröffentlicht hat, tragen die PDFs das Wasserzeichen „ENTWURF“.
        DATENSCHUTZINFORMATION = "datenschutzinformation", "Datenschutzinformation"
        EINWILLIGUNG = "einwilligung", "Einwilligung in die Datenverarbeitung"
        SCHWEIGEPFLICHTENTBINDUNG = "schweigepflichtentbindung", "Schweigepflichtentbindung"

    class Status(models.TextChoices):
        ENTWURF = "entwurf", "Entwurf"
        AKTIV = "aktiv", "aktiv"
        ABGELOEST = "abgeloest", "abgelöst"

    art = models.CharField(max_length=30, choices=Art.choices)
    version = models.PositiveIntegerField(null=True, blank=True, help_text="leer beim Entwurf")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ENTWURF)
    bloecke = models.JSONField(default=list)
    notiz = models.CharField(max_length=200, blank=True, help_text="z. B. „Startvorlage nach Entwurf“")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")
    geaendert_am = models.DateTimeField(auto_now=True)
    geaendert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")
    veroeffentlicht_am = models.DateTimeField(null=True, blank=True)
    veroeffentlicht_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                            blank=True, related_name="+")

    history = HistoricalRecords(excluded_fields=["geaendert_am"])

    class Meta:
        verbose_name = "Dokumentvorlage"
        verbose_name_plural = "Dokumentvorlagen"
        ordering = ["art", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["art"], condition=models.Q(status="entwurf"), name="ein_entwurf_je_art"),
            models.UniqueConstraint(fields=["art"], condition=models.Q(status="aktiv"), name="eine_aktive_je_art"),
            models.UniqueConstraint(fields=["art", "version"], name="version_je_art_eindeutig"),
            models.CheckConstraint(name="version_nur_veroeffentlicht",
                                   condition=models.Q(status="entwurf", version__isnull=True)
                                   | (~models.Q(status="entwurf") & models.Q(version__isnull=False))),
        ]

    def __str__(self):
        return f"{self.get_art_display()} {'Entwurf' if self.version is None else f'v{self.version}'}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.pk and not (update_fields and set(update_fields) <= {"status"}):
            alt = Dokumentvorlage.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if alt != self.Status.ENTWURF:
                raise PermissionError("Veröffentlichte Vorlagen sind unveränderlich. Bitte einen neuen Entwurf anlegen.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.ENTWURF:
            raise PermissionError("Veröffentlichte Vorlagen werden nicht gelöscht.")
        return super().delete(*args, **kwargs)

    def clean(self):
        from .bloecke import pruefe_bloecke

        fehler = pruefe_bloecke(self.art, self.bloecke)
        if fehler:
            raise ValidationError({"bloecke": fehler})

    # --- Abläufe ---
    @classmethod
    def aktive(cls, art: str) -> "Dokumentvorlage":
        """Die aktive Version; gibt es noch keine, wird die Startvorlage nach dem Entwurf als v1 angelegt."""
        v = cls.objects.filter(art=art, status=cls.Status.AKTIV).first()
        if v is None:
            from .bloecke import STARTVORLAGEN

            with transaction.atomic():
                v = cls.objects.select_for_update().filter(art=art, status=cls.Status.AKTIV).first()
                if v is None:
                    v = cls.objects.create(art=art, version=1, status=cls.Status.AKTIV,
                                           bloecke=STARTVORLAGEN[art], notiz="Startvorlage nach Entwurf",
                                           veroeffentlicht_am=timezone.now())
        return v

    # Vordrucke zum Datenschutz: mitgelieferte Startvorlagen sind ungeprüfte Entwürfe (U17)
    VORDRUCKE = ("datenschutzinformation", "einwilligung", "schweigepflichtentbindung")

    @property
    def im_entwurfsmodus(self) -> bool:
        """Trägt die PDF das Wasserzeichen „ENTWURF“? Bei den Vordrucken, solange die mitgelieferte Startvorlage aktiv
        ist (nie von einem Menschen veröffentlicht) – außer jemand hat den Entwurfsmodus für diese Art ausgeschaltet."""
        from stammdaten.models import Einstellungen

        if self.art not in self.VORDRUCKE or self.veroeffentlicht_von_id is not None:
            return False
        return self.art not in (Einstellungen.aktuell().vordrucke_ohne_entwurf or [])

    @classmethod
    def entwurf_von(cls, art: str):
        return cls.objects.filter(art=art, status=cls.Status.ENTWURF).first()

    @transaction.atomic
    def veroeffentlichen(self, benutzer) -> "Dokumentvorlage":
        if self.status != self.Status.ENTWURF:
            raise ValidationError("Nur ein Entwurf kann veröffentlicht werden.")
        self.full_clean()
        alt = Dokumentvorlage.objects.select_for_update().filter(art=self.art, status=self.Status.AKTIV).first()
        hoechste = Dokumentvorlage.objects.filter(art=self.art).aggregate(m=models.Max("version"))["m"] or 0
        if alt:
            alt.status = self.Status.ABGELOEST
            alt.save(update_fields=["status"])
        self.status = self.Status.AKTIV
        self.version = hoechste + 1
        self.veroeffentlicht_am = timezone.now()
        self.veroeffentlicht_von = benutzer
        super().save()  # letzter Schreibvorgang, danach unveränderlich
        return self
