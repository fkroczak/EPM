from django.conf import settings
from django.db import models


class SystemEreignis(models.Model):
    """Systemweites, unveränderliches Protokoll (DB-Trigger verhindert UPDATE/DELETE).

    Zwei Ausnahmen, beide nur im Wartungsmodus und selbst protokolliert (Datenschutz): Wird eine Akte endgültig
    gelöscht, verlieren ihre Einträge Namen und Inhalte (``audit.bereinigung.akte_entfernen``); ist eine
    Aufbewahrungsdauer für das Audit-Log eingestellt, werden ältere Einträge entfernt."""

    class Art(models.TextChoices):
        ANMELDUNG = "anmeldung", "Anmeldung"
        ANMELDUNG_FEHLGESCHLAGEN = "anmeldung_fehlgeschlagen", "Anmeldung fehlgeschlagen"
        ANMELDUNG_GESPERRT = "anmeldung_gesperrt", "Anmeldung gesperrt (zu viele Fehlversuche)"
        ZWEITER_FAKTOR_FEHLGESCHLAGEN = "2fa_fehlgeschlagen", "2FA-Code falsch"
        ABMELDUNG = "abmeldung", "Abmeldung"
        KENNWORT_GEAENDERT = "kennwort_geaendert", "Passwort geändert"
        ZWEITER_FAKTOR_EINGERICHTET = "2fa_eingerichtet", "2FA eingerichtet"
        BENUTZER_ANGELEGT = "benutzer_angelegt", "Benutzer angelegt"
        BENUTZER_GEAENDERT = "benutzer_geaendert", "Benutzer geändert"
        BENUTZER_GESPERRT = "benutzer_gesperrt", "Benutzer gesperrt"
        RECHTE_GEAENDERT = "rechte_geaendert", "Rechte geändert"
        EINMAL_KENNWORT = "einmal_kennwort", "Einmal-Passwort erzeugt"
        ZWEITER_FAKTOR_ZURUECKGESETZT = "2fa_zurueckgesetzt", "2FA zurückgesetzt"
        AKTE_ABGESCHLOSSEN = "akte_abgeschlossen", "Akte abgeschlossen"
        AKTE_GEOEFFNET = "akte_geoeffnet", "Akte wieder geöffnet"
        # Anforderung 11.10.2026: Akte einer weiteren Firma zugeordnet bzw. aus einer Firma genommen
        AKTE_FIRMEN = "akte_firmen", "Zuordnung einer Akte zu Firmen geändert"
        PLAN_FREIGEGEBEN = "plan_freigegeben", "Infusionsplan freigegeben"
        BERICHT_FREIGEGEBEN = "bericht_freigegeben", "Bericht freigegeben"
        # Korrespondenz der Akte (14.10.2026): Schreiben freigegeben, versendet, Entwurf gelöscht, PDF geöffnet
        KORRESPONDENZ = "korrespondenz", "Korrespondenz"
        SPRECHSTUNDE_ERZEUGT = "sprechstunde_erzeugt", "Unterlagen für die Sprechstunde erzeugt"
        STAMMDATEN = "stammdaten", "Stammdaten geändert"
        VORLAGE = "vorlage", "Vorlage geändert"
        BACKUP = "backup", "Backup"
        EXPORT = "export", "Export"
        TESTDATEN = "testdaten", "Testdaten zurückgesetzt"
        DOKUMENT_UMGEHAENGT = "dokument_umgehaengt", "Dokument anderem Patienten zugeordnet"
        DOKUMENT_GELOESCHT = "dokument_geloescht", "Dokument endgültig gelöscht"
        DOKUMENT_LOESCHEN_ABGELEHNT = "dokument_loeschen_abgelehnt", "Löschen eines Dokuments abgelehnt"
        DOKUMENT_LOESCHUNG_NACHGEHOLT = "dokument_loeschung_nachgeholt", "Löschung eines Dokuments nachgeholt"
        # „Text erkennen“ an einem Dokument der Akte (F170): Datei durch dieselbe PDF mit Textebene ersetzt
        DOKUMENT_TEXT_ERKANNT = "dokument_text_erkannt", "Text eines Dokuments erkannt (Datei ersetzt)"
        SYSTEM = "system", "Systemverwaltung"
        # Datenschutz (Festlegung 02.10.2026)
        DATENSCHUTZ = "datenschutz", "Datenschutz"
        AKTE_EINGESCHRAENKT = "akte_eingeschraenkt", "Verarbeitung einer Akte eingeschränkt"
        AKTE_EINSCHRAENKUNG_AUFGEHOBEN = "akte_einschraenkung_aufgehoben", "Einschränkung einer Akte aufgehoben"
        AKTE_EINSICHT = "akte_einsicht", "Einsicht in eine eingeschränkte Akte"
        AKTE_GELOESCHT = "akte_geloescht", "Akte endgültig gelöscht"
        AKTE_LOESCHEN_ABGELEHNT = "akte_loeschen_abgelehnt", "Löschen einer Akte abgelehnt"
        PROTOKOLL_BEREINIGT = "protokoll_bereinigt", "Audit-Log bereinigt"
        # Scans und Texterkennung (Festlegung 08.10.2026, F160 ff.)
        SCAN = "scan", "Scan"

    zeitpunkt = models.DateTimeField(auto_now_add=True, db_index=True)
    art = models.CharField(max_length=40, choices=Art.choices, db_index=True)
    benutzer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    benutzername = models.CharField(max_length=150, blank=True, help_text="Wie eingegeben (auch bei Fehlversuchen)")
    objekt = models.CharField(max_length=200, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    geraet = models.CharField("Gerät / Browser", max_length=300, blank=True)

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


def browser_kurz(user_agent: str) -> str:
    """„Firefox 131 · Windows“ statt der langen Browser-Kennung."""
    ua = user_agent or ""
    browser = next((name for kennung, name in [
        ("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"),
    ] if kennung in ua), "Browser" if ua else "")
    version = ""
    for kennung in ("Edg/", "OPR/", "Firefox/", "Chrome/", "Version/"):
        if kennung in ua:
            version = ua.split(kennung, 1)[1].split(" ", 1)[0].split(".", 1)[0]
            break
    system = next((name for kennung, name in [
        ("Windows", "Windows"), ("Mac OS X", "macOS"), ("Android", "Android"), ("iPhone", "iOS"), ("Linux", "Linux"),
    ] if kennung in ua), "")
    return " · ".join(t for t in (f"{browser} {version}".strip(), system) if t)


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
        geraet=browser_kurz(request.META.get("HTTP_USER_AGENT", ""))[:300] if request is not None else "",
    )
