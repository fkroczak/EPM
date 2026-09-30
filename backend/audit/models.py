from django.conf import settings
from django.db import models


class SystemEreignis(models.Model):
    """Systemweites, unveränderliches Protokoll (DB-Trigger verhindert UPDATE/DELETE)."""

    class Art(models.TextChoices):
        ANMELDUNG = "anmeldung", "Anmeldung"
        ANMELDUNG_FEHLGESCHLAGEN = "anmeldung_fehlgeschlagen", "Anmeldung fehlgeschlagen"
        ANMELDUNG_GESPERRT = "anmeldung_gesperrt", "Anmeldung gesperrt (zu viele Fehlversuche)"
        ZWEITER_FAKTOR_FEHLGESCHLAGEN = "2fa_fehlgeschlagen", "2FA-Code falsch"
        ABMELDUNG = "abmeldung", "Abmeldung"
        KENNWORT_GEAENDERT = "kennwort_geaendert", "Kennwort geändert"
        ZWEITER_FAKTOR_EINGERICHTET = "2fa_eingerichtet", "2FA eingerichtet"
        BENUTZER_ANGELEGT = "benutzer_angelegt", "Benutzer angelegt"
        BENUTZER_GEAENDERT = "benutzer_geaendert", "Benutzer geändert"
        BENUTZER_GESPERRT = "benutzer_gesperrt", "Benutzer gesperrt"
        EINMAL_KENNWORT = "einmal_kennwort", "Einmal-Kennwort erzeugt"
        ZWEITER_FAKTOR_ZURUECKGESETZT = "2fa_zurueckgesetzt", "2FA zurückgesetzt"
        AKTE_ABGESCHLOSSEN = "akte_abgeschlossen", "Akte abgeschlossen"
        AKTE_GEOEFFNET = "akte_geoeffnet", "Akte wieder geöffnet"
        PLAN_FREIGEGEBEN = "plan_freigegeben", "Infusionsplan freigegeben"
        STAMMDATEN = "stammdaten", "Stammdaten geändert"
        VORLAGE = "vorlage", "Vorlage geändert"
        BACKUP = "backup", "Backup"
        EXPORT = "export", "Export"
        TESTDATEN = "testdaten", "Testdaten zurückgesetzt"

    zeitpunkt = models.DateTimeField(auto_now_add=True, db_index=True)
    art = models.CharField(max_length=40, choices=Art.choices, db_index=True)
    benutzer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    benutzername = models.CharField(max_length=150, blank=True, help_text="Wie eingegeben (auch bei Fehlversuchen)")
    objekt = models.CharField(max_length=200, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Systemereignis"
        verbose_name_plural = "Systemereignisse"
        ordering = ["-zeitpunkt", "-id"]

    def __str__(self):
        return f"{self.zeitpunkt:%d.%m.%Y %H:%M} {self.get_art_display()} {self.benutzername}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Systemereignisse sind unveränderlich.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Systemereignisse sind unveränderlich.")


def client_ip(request):
    if request is None:
        return None
    # Nginx setzt X-Real-IP; nur dieser Wert wird vertraut
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")


def protokolliere(art, request=None, benutzer=None, benutzername="", objekt="", **details):
    if benutzer is None and request is not None and getattr(request, "user", None) and request.user.is_authenticated:
        benutzer = request.user
    return SystemEreignis.objects.create(
        art=art,
        benutzer=benutzer,
        benutzername=benutzername or (benutzer.get_username() if benutzer else ""),
        objekt=str(objekt)[:200],
        details=details,
        ip=client_ip(request),
    )
