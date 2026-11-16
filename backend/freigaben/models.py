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


class Arztdublette(models.Model):
    """Vorschlag: mehrere Einträge der Ärzteliste sind derselbe Arzt (gleicher Name ohne Titel, gleiche Telefonnummer
    oder E-Mail). Nach der Freigabe zeigen alle Zuordnungen auf einen Eintrag, die übrigen werden deaktiviert."""

    class Status(models.TextChoices):
        OFFEN = "offen", "wartet auf Freigabe"
        UMGESETZT = "umgesetzt", "zusammengeführt"
        VERWORFEN = "verworfen", "keine Dublette"
        VERALTET = "veraltet", "Ärzteliste inzwischen geändert"

    schluessel = models.CharField(max_length=200, help_text="sortierte IDs, z. B. „3,17,42“")
    aerzte = models.JSONField(default=list, help_text="IDs der Ärzte")
    gruende = models.JSONField(default=list, help_text="warum sie zusammengehören")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OFFEN, db_index=True)
    erstellt_am = models.DateTimeField(auto_now_add=True)
    erledigt_am = models.DateTimeField(null=True, blank=True)
    erledigt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")
    ergebnis = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Ärzte-Dublette"
        verbose_name_plural = "Ärzte-Dubletten"
        ordering = ["erstellt_am", "id"]
        constraints = [models.UniqueConstraint(fields=["schluessel"], condition=models.Q(status__in=["offen", "verworfen"]),
                                               name="arztdublette_einmal")]

    def __str__(self):
        return f"Ärzte-Dublette {self.pk}"


class Lernbeispiel(models.Model):
    """Was Mitarbeiter bei der Freigabe anders entschieden haben als vorgeschlagen (Lernen aus Korrekturen, kein
    Training): Beziehung bei „Fr. + gleicher Nachname“, gewählter Arzt zu einem Freitext, abgewählte Schritte,
    Anlass des Abschlusses. Die nächsten Vorschläge richten sich danach (``freigaben/lernen.py``)."""

    art = models.CharField(max_length=20, db_index=True)  # beziehung | arzt | schritt | abschluss
    schluessel = models.CharField(max_length=200, db_index=True)
    vorschlag = models.CharField(max_length=200, blank=True)
    gewaehlt = models.CharField(max_length=200, blank=True)
    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    zeitpunkt = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lernbeispiel (Datenpflege)"
        verbose_name_plural = "Lernbeispiele (Datenpflege)"
        ordering = ["-zeitpunkt", "-id"]

    def __str__(self):
        return f"{self.art}: {self.schluessel} → {self.gewaehlt}"


class Freigabe(models.Model):
    class Art(models.TextChoices):
        DATENPFLEGE = "datenpflege", "Datenpflege"
        INFUSIONSPLAN = "infusionsplan", "Infusionsplan"
        AERZTE = "aerzte", "Ärzte zusammenführen"

    class Status(models.TextChoices):
        WARTET = "wartet", "wird gleich umgesetzt"
        UMGESETZT = "umgesetzt", "umgesetzt"
        ZURUECK = "zurueck", "zurückgenommen"
        FEHLER = "fehler", "nicht umgesetzt"

    art = models.CharField(max_length=20, choices=Art.choices)
    objekt_id = models.PositiveIntegerField()
    patient = models.ForeignKey("patienten.Patient", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    gruppe = models.CharField(max_length=36, blank=True, db_index=True, help_text="Sammelfreigabe: gemeinsam zurücknehmen")
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
