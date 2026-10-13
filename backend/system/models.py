"""Administration › System: Aufträge an den Server bzw. Wartung des EPM und Hinweise an alle Benutzer."""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Systemauftrag(models.Model):
    """Eine Tätigkeit der Systemverwaltung. Aufträge an den Server führt der Systemagent auf dem Server aus
    (rollout/epm-systemagent.py); Wartungsaufgaben des EPM laufen direkt im Backend."""

    class Ziel(models.TextChoices):
        SERVER = "server", "Server"
        EPM = "epm", "EPM"

    class Status(models.TextChoices):
        WARTET = "wartet", "wartet auf den Server"
        LAEUFT = "laeuft", "läuft"
        ERLEDIGT = "erledigt", "erledigt"
        FEHLER = "fehler", "fehlgeschlagen"
        ABGEBROCHEN = "abgebrochen", "zurückgezogen"

    kennung = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ziel = models.CharField(max_length=10, choices=Ziel.choices)
    aktion = models.CharField(max_length=40)
    parameter = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WARTET)
    angefordert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    angefordert_am = models.DateTimeField(auto_now_add=True)
    begonnen_am = models.DateTimeField(null=True, blank=True)
    beendet_am = models.DateTimeField(null=True, blank=True)
    ergebnis = models.CharField(max_length=500, blank=True)
    ausgabe = models.TextField(blank=True)
    rueckgabe = models.IntegerField(null=True, blank=True)
    probelauf = models.BooleanField(default=False, help_text="Der Server hat die Aktion nur simuliert.")

    class Meta:
        verbose_name = "Systemauftrag"
        verbose_name_plural = "Systemaufträge"
        ordering = ["-angefordert_am", "-id"]

    def __str__(self):
        return f"{self.aktion} ({self.get_status_display()})"

    @property
    def offen(self) -> bool:
        return self.status in (self.Status.WARTET, self.Status.LAEUFT)


class Systemhinweis(models.Model):
    """Hinweis an alle angemeldeten Benutzer, z. B. vor Updates oder einem Neustart des Servers. Ohne ``angelegt_von``
    stammt er vom Server selbst (Selbstheilung: Rückfall auf die gute Version, knappe Platte)."""

    class Art(models.TextChoices):
        INFO = "info", "Information"
        WARNUNG = "warnung", "Warnung"

    text = models.CharField(max_length=500)
    art = models.CharField(max_length=10, choices=Art.choices, default=Art.WARNUNG)
    gueltig_bis = models.DateTimeField(null=True, blank=True)
    auftrag = models.ForeignKey(Systemauftrag, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True,
                                     blank=True)
    angelegt_am = models.DateTimeField(auto_now_add=True)
    beendet_am = models.DateTimeField(null=True, blank=True)
    beendet_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="+")

    class Meta:
        verbose_name = "Hinweis an alle Benutzer"
        verbose_name_plural = "Hinweise an alle Benutzer"
        ordering = ["-angelegt_am", "-id"]

    def __str__(self):
        return self.text[:60]

    @classmethod
    def aktiv(cls):
        jetzt = timezone.now()
        return (cls.objects.filter(beendet_am__isnull=True)
                .filter(Q(gueltig_bis__isnull=True) | Q(gueltig_bis__gt=jetzt))
                .select_related("angelegt_von").first())
