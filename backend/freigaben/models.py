"""Menü „Freigaben“ (16.11.2026): alles, was ein Mensch freigeben muss, an einer Stelle.

- ``Datenpflegevorschlag``: Nachpflege nach der Altdaten-Übernahme. Regeln (und nachts das lokale KI-Modell) lesen die
  Freitexte einer Akte (Telefon mit Namen dahinter, Hausarzt mit Adresse, Hinweise aus der Übernahme) und schlagen
  Schritte vor: Arzt aus der Ärzteliste zuordnen, Bezugsperson anlegen, Feld bereinigen, erledigten Hinweis entfernen.
  In die Akte kommt nichts, bevor ein Mitarbeiter freigibt.
- ``Freigabe``: eine erteilte Freigabe – sie wird erst nach ``RUECKGAENGIG_S`` Sekunden umgesetzt und lässt sich bis
  dahin mit einem Klick zurücknehmen (für Datenpflege und Infusionspläne gleich).
"""
from django.conf import settings
from django.db import models

RUECKGAENGIG_S = 60


class Datenpflegevorschlag(models.Model):
    class Status(models.TextChoices):
        OFFEN = "offen", "wartet auf Freigabe"
        UMGESETZT = "umgesetzt", "umgesetzt"
        VERWORFEN = "verworfen", "verworfen"
        VERALTET = "veraltet", "Akte inzwischen geändert"

    patient = models.ForeignKey("patienten.Patient", on_delete=models.CASCADE, related_name="datenpflegevorschlaege")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OFFEN, db_index=True)
    quelle = models.JSONField(default=dict, help_text="Stand der gelesenen Felder beim Erstellen {feld: wert}")
    schritte = models.JSONField(default=list, help_text="vorgeschlagene Schritte (freigaben/datenpflege.py)")
    verfahren = models.CharField(max_length=20, default="regeln", help_text="regeln | regeln+ki")
    ki_offen = models.BooleanField(default=False, help_text="das KI-Modell soll den Vorschlag nachts noch prüfen")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    erledigt_am = models.DateTimeField(null=True, blank=True)
    erledigt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")
    ergebnis = models.JSONField(default=list, blank=True, help_text="nach der Umsetzung: [{modell, id, aktion}]")

    class Meta:
        verbose_name = "Datenpflege-Vorschlag"
        verbose_name_plural = "Datenpflege-Vorschläge"
        ordering = ["-erstellt_am", "-id"]
        constraints = [models.UniqueConstraint(fields=["patient"], condition=models.Q(status="offen"),
                                               name="datenpflege_ein_offener_je_akte")]

    def __str__(self):
        return f"Datenpflege {self.pk}"


class Freigabe(models.Model):
    class Art(models.TextChoices):
        DATENPFLEGE = "datenpflege", "Datenpflege"
        INFUSIONSPLAN = "infusionsplan", "Infusionsplan"

    class Status(models.TextChoices):
        WARTET = "wartet", "wird gleich umgesetzt"
        UMGESETZT = "umgesetzt", "umgesetzt"
        ZURUECK = "zurueck", "zurückgenommen"
        FEHLER = "fehler", "nicht umgesetzt"

    art = models.CharField(max_length=20, choices=Art.choices)
    objekt_id = models.PositiveIntegerField()
    patient = models.ForeignKey("patienten.Patient", on_delete=models.CASCADE, related_name="+")
    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WARTET, db_index=True)
    daten = models.JSONField(default=dict, blank=True, help_text="bei Datenpflege: die freigegebenen Schritte")
    freigegeben_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    freigegeben_am = models.DateTimeField(auto_now_add=True)
    umsetzen_ab = models.DateTimeField(db_index=True)
    erledigt_am = models.DateTimeField(null=True, blank=True)
    fehler = models.TextField(blank=True)

    class Meta:
        verbose_name = "Freigabe"
        verbose_name_plural = "Freigaben"
        ordering = ["-freigegeben_am", "-id"]
        constraints = [models.UniqueConstraint(fields=["art", "objekt_id"], condition=models.Q(status="wartet"),
                                               name="freigabe_eine_wartende_je_objekt")]

    def __str__(self):
        return f"Freigabe {self.pk} ({self.art} {self.objekt_id})"
