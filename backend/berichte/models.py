"""Berichte aus der Akte heraus (Wunsch 06.10.2026, F115): Entwurf → freigegeben.

Ein Bericht wird direkt in der Patientenakte geschrieben. Solange er Entwurf ist, lässt er sich beliebig
ändern. Mit der Freigabe entsteht aus der Dokumentvorlage „Bericht“ eine PDF, die als Dokument der Akte
abgelegt wird; der Bericht selbst ist danach unveränderlich (Modell und Datenbank-Trigger) – genau wie der
Infusionsplan, damit die abgelegte PDF und der Datensatz nie auseinanderlaufen. Eine Korrektur ist ein neuer
Bericht.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from simple_history.models import HistoricalRecords

from patienten.models import AktenEintrag, Patient
from stammdaten.models import Auswahlwert


class Bericht(AktenEintrag):
    class Status(models.TextChoices):
        ENTWURF = "entwurf", "Entwurf"
        FREIGEGEBEN = "freigegeben", "freigegeben"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="berichte")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ENTWURF)
    art = models.ForeignKey(
        Auswahlwert, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        limit_choices_to={"liste": Auswahlwert.Liste.BERICHTART}, verbose_name="Berichtsart",
    )
    titel = models.CharField(max_length=200)
    datum = models.DateField("Datum des Berichts", default=timezone.localdate)
    empfaenger = models.CharField(max_length=200, blank=True, help_text="z. B. „Hausarzt Dr. Hausmann“")
    inhalt = models.TextField(blank=True)

    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    geaendert_am = models.DateTimeField(auto_now=True)
    freigegeben_am = models.DateTimeField(null=True, blank=True)
    freigegeben_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # Bei der Freigabe erzeugte PDF (Dokument der Akte), mit Prüfsumme und Vorlagenversion wie beim Plan
    dokument = models.ForeignKey(
        "patienten.Dokument", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        verbose_name="Freigegebene PDF",
    )
    pdf_sha256 = models.CharField(max_length=64, blank=True)
    vorlage_version = models.PositiveIntegerField(null=True, blank=True)

    history = HistoricalRecords(excluded_fields=["geaendert_am"])

    class Meta:
        verbose_name = "Bericht"
        verbose_name_plural = "Berichte"
        ordering = ["-datum", "-id"]
        indexes = [models.Index(fields=["patient", "datum"], name="bericht_patient_datum")]

    def __str__(self):
        return f"{self.titel} ({self.get_status_display()})"

    @property
    def ist_entwurf(self) -> bool:
        return self.status == self.Status.ENTWURF

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.pk:
            # unter Sperre lesen: Eine laufende Freigabe hält die Zeile; danach ist der Bericht gesperrt
            alt = Bericht.objects.select_for_update().filter(pk=self.pk).values_list("status", flat=True).first()
            if alt != self.Status.ENTWURF:
                raise PermissionError("Freigegebene Berichte sind unveränderlich. Bitte einen neuen Bericht anlegen.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.ENTWURF:
            raise PermissionError("Nur Entwürfe können verworfen werden.")
        return super().delete(*args, **kwargs)

    def clean(self):
        fehler = {}
        if not (self.titel or "").strip():
            fehler["titel"] = "Bitte einen Titel angeben."
        if self.datum and self.datum > timezone.localdate():
            fehler["datum"] = "Das Datum liegt in der Zukunft."
        if self.art_id and self.art.liste != Auswahlwert.Liste.BERICHTART:
            fehler["art"] = "Bitte eine Berichtsart wählen."
        if fehler:
            raise ValidationError(fehler)

    @transaction.atomic
    def freigeben(self, benutzer):
        """Macht aus dem Entwurf einen freigegebenen Bericht und legt die PDF als Dokument der Akte ab."""
        if not benutzer.hat_recht("berichte_freigeben"):
            raise PermissionError("Berichte freigeben darf nur, wer das Recht dazu hat.")
        # Zeile sperren und vom gespeicherten Stand ausgehen: Die PDF zeigt genau den gespeicherten Text,
        # gleichzeitiges Bearbeiten und eine zweite Freigabe warten bzw. scheitern.
        self.refresh_from_db(from_queryset=Bericht.objects.select_for_update())
        if self.status != self.Status.ENTWURF:
            raise ValidationError("Nur Entwürfe können freigegeben werden.")
        self.patient.pruefe_bearbeitbar()
        self.full_clean()
        if not (self.inhalt or "").strip():
            raise ValidationError({"inhalt": "Ein leerer Bericht kann nicht freigegeben werden."})
        from diktate.dienst import bei_freigabe

        bei_freigabe(self)  # läuft noch eine Abschrift → warten; sonst Aufnahmen löschen
        self.status = self.Status.FREIGEGEBEN
        self.freigegeben_am = timezone.now()
        self.freigegeben_von = benutzer
        dok = self._pdf_ablegen(benutzer)
        try:
            super().save()  # AktenEintrag.save: letzter Schreibvorgang, danach gesperrt
        except BaseException:
            dok.pfad.unlink(missing_ok=True)
            raise
        return self

    @property
    def freigabevermerk(self) -> str | None:
        from epm.api_basis import benutzername

        if not self.freigegeben_von_id or not self.freigegeben_am:
            return None
        wann = timezone.localtime(self.freigegeben_am)
        return (f"Maschinell erstellt, geprüft und freigegeben von {benutzername(self.freigegeben_von)} "
                f"am {wann:%d.%m.%Y}.")

    def _pdf_ablegen(self, benutzer):
        from vorlagen.felder import Kontext
        from vorlagen.pdf import als_dokument, erzeuge_aus_vorlage, wasserzeichen_fuer

        p = self.patient
        pdf, version = erzeuge_aus_vorlage("bericht", Kontext(patient=p, bericht=self),
                                           wasserzeichen=wasserzeichen_fuer(p),
                                           titel=f"{self.titel} – {p.nachname}, {p.vorname}")
        dok = als_dokument(p, pdf, self.titel, "Bericht", self.datum, benutzer,
                           f"Bericht-{p.nummer}-{self.datum:%Y-%m-%d}.pdf")
        self.dokument, self.pdf_sha256, self.vorlage_version = dok, dok.sha256, version
        return dok
