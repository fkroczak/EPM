"""Stand der Übernahme der Altdaten: geladener Dump, Zuordnungen, Läufe und was der Import angelegt hat."""
from django.conf import settings
from django.db import models


class Importstand(models.Model):
    """Genau ein Datensatz (pk=1): wo die Übernahme steht.

    Die Zuordnungen (Spalten, Benutzer, Versorger, Werte, Präparate, Entscheidungen zu einzelnen Zeilen) sind
    unabhängig vom Dump gespeichert – sie gelten für den frischen Dump zum Go-live weiter."""

    class Status(models.TextChoices):
        LEER = "leer", "kein Dump geladen"
        GELADEN = "geladen", "Dump geladen"
        IMPORTIERT = "importiert", "Altdaten übernommen"
        ABGESCHLOSSEN = "abgeschlossen", "Übernahme abgeschlossen"

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.LEER)
    dump_name = models.CharField(max_length=255, blank=True)
    dump_sha256 = models.CharField(max_length=64, blank=True)
    dump_groesse = models.PositiveBigIntegerField(default=0)
    dump_geladen_am = models.DateTimeField(null=True, blank=True)
    dump_geladen_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                         related_name="+")
    dump_hinweise = models.JSONField(default=list, blank=True)
    zuordnung = models.JSONField(default=dict, blank=True)
    importiert_am = models.DateTimeField(null=True, blank=True)
    importiert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name="+")
    abgeschlossen_am = models.DateTimeField(null=True, blank=True)
    abgeschlossen_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                          related_name="+")

    class Meta:
        verbose_name = "Stand der Altdaten-Übernahme"
        verbose_name_plural = "Stand der Altdaten-Übernahme"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Der Stand der Übernahme wird nicht gelöscht.")

    @classmethod
    def aktuell(cls, sperren: bool = False) -> "Importstand":
        cls.objects.get_or_create(pk=1)
        qs = cls.objects.select_for_update() if sperren else cls.objects
        return qs.get(pk=1)

    def __str__(self):
        return self.get_status_display()


class Alttabelle(models.Model):
    """Eine Tabelle des geladenen Dumps, so wie sie gelesen wurde (Werte als Text oder null; Kennwort-Spalten sind
    geleert). Wird beim Abschließen der Übernahme gelöscht."""

    name = models.CharField(max_length=100, unique=True)
    spalten = models.JSONField(default=list)
    typen = models.JSONField(default=dict, blank=True)
    entfernt = models.JSONField(default=list, blank=True)
    zeilen = models.JSONField(default=list)

    class Meta:
        verbose_name = "Tabelle des Altsystems"
        verbose_name_plural = "Tabellen des Altsystems"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Importlauf(models.Model):
    """Ein Lauf des Werkzeugs mit Zählung und Importprotokoll. Das Protokoll nennt Nummern, keine Namen."""

    class Art(models.TextChoices):
        PROBELAUF = "probelauf", "Probelauf"
        IMPORT = "import", "Import"
        DOKUMENTE = "dokumente", "Dokumente übernommen"
        ZURUECKGENOMMEN = "zurueckgenommen", "Import zurückgenommen"
        ABGESCHLOSSEN = "abgeschlossen", "Übernahme abgeschlossen"

    art = models.CharField(max_length=20, choices=Art.choices)
    begonnen_am = models.DateTimeField(auto_now_add=True)
    beendet_am = models.DateTimeField(null=True, blank=True)
    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    erfolgreich = models.BooleanField(default=False)
    dump_name = models.CharField(max_length=255, blank=True)
    dump_sha256 = models.CharField(max_length=64, blank=True)
    zahlen = models.JSONField(default=dict, blank=True)
    protokoll = models.JSONField(default=list, blank=True)
    fehler = models.TextField(blank=True)

    class Meta:
        verbose_name = "Lauf der Altdaten-Übernahme"
        verbose_name_plural = "Läufe der Altdaten-Übernahme"
        ordering = ["-begonnen_am", "-id"]

    def __str__(self):
        return f"{self.get_art_display()} vom {self.begonnen_am:%d.%m.%Y %H:%M}"


class Importobjekt(models.Model):
    """Was der Import angelegt hat – Grundlage für „Zurücknehmen“ und für das Fortsetzen bei den Dokumenten.
    ``schluessel``: Nummer bzw. Bezeichnung im Altsystem, bei Dateien der Pfad unter dem Dokumentenordner."""

    class Art(models.TextChoices):
        PATIENT = "patient", "Patient"
        BENUTZER = "benutzer", "Benutzer"
        VERSORGER = "versorger", "Versorger"
        ANSPRECHPARTNER = "ansprechpartner", "Ansprechpartner"
        AUSWAHLWERT = "auswahlwert", "Auswahlwert"
        PRAEPARAT = "praeparat", "Präparat"
        DATEI = "datei", "Datei"

    art = models.CharField(max_length=20, choices=Art.choices)
    objekt_id = models.PositiveBigIntegerField()
    schluessel = models.CharField(max_length=600)

    class Meta:
        verbose_name = "Vom Import angelegtes Objekt"
        verbose_name_plural = "Vom Import angelegte Objekte"
        constraints = [models.UniqueConstraint(fields=["art", "schluessel"], name="importobjekt_eindeutig")]
        indexes = [models.Index(fields=["art", "objekt_id"], name="importobjekt_art_objekt")]
