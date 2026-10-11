import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone
from django_otp.models import Device
from simple_history.models import HistoricalRecords


class Rolle(models.TextChoices):
    BETRACHTER = "betrachter", "Betrachter"
    MITARBEITER = "mitarbeiter", "Mitarbeiter"
    # Festlegung 03.10.2026 (U22): zwischen Mitarbeiter und Mediziner, um Rechte feiner zu verteilen
    MITARBEITER_PLUS = "mitarbeiter_plus", "Mitarbeiter (erweitert)"
    MEDIZINER = "mediziner", "Mediziner"
    ADMIN = "admin", "Admin"
    # Festlegung 02.10.2026: Konten ohne Login haben keinerlei Rechte; auch für Konten mit Login wählbar
    KEINE = "keine", "Keine Berechtigung"


# Zeichen für Einmal-Kennwörter: ohne leicht verwechselbare (0/O, 1/l/I)
_KENNWORT_ZEICHEN = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def erzeuge_einmal_kennwort(laenge: int = 14) -> str:
    roh = "".join(secrets.choice(_KENNWORT_ZEICHEN) for _ in range(laenge))
    return "-".join(roh[i:i + 7] for i in range(0, laenge, 7))


class EpmUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra):
        extra.setdefault("rolle", Rolle.ADMIN)
        extra.setdefault("muss_kennwort_aendern", False)  # Kennwort wurde gerade selbst gewählt
        return super().create_superuser(username, email, password, **extra)


class User(AbstractUser):
    """Mitarbeiter-Konto. Wird nie gelöscht, nur gesperrt (is_active=False)."""

    titel = models.CharField("Titel", max_length=40, blank=True)
    kuerzel = models.CharField("Kürzel", max_length=10, unique=True, null=True, blank=True)
    funktion = models.CharField("Funktion", max_length=80, blank=True)
    rolle = models.CharField("Rolle", max_length=20, choices=Rolle.choices, default=Rolle.BETRACHTER)
    ist_test = models.BooleanField(
        "Testbenutzer", default=False,
        help_text="Sieht und bearbeitet ausschließlich Testpatienten.",
    )
    nur_historisch = models.BooleanField(
        "Nur historisch", default=False,
        help_text="Ohne Login: Name, dem Einträge zugeordnet bleiben (aus dem Altsystem übernommen oder von der "
                  "Administration so gesetzt). Kann sich nicht anmelden und hat keine Rechte.",
    )
    muss_kennwort_aendern = models.BooleanField("Muss Passwort ändern", default=True)
    einmal_kennwort_gueltig_bis = models.DateTimeField("Einmal-Passwort gültig bis", null=True, blank=True)
    kennwort_geaendert_am = models.DateTimeField("Passwort geändert am", null=True, blank=True)
    fehlversuche = models.PositiveSmallIntegerField("Fehlversuche seit letzter Anmeldung", default=0)
    gesperrt_am = models.DateTimeField("Gesperrt am", null=True, blank=True)
    # Testbenutzer ausblenden (Festlegung 03.10.2026): gesperrt und aus allen Listen genommen, nicht gelöscht
    ausgeblendet_am = models.DateTimeField("Ausgeblendet am", null=True, blank=True)
    sperrgrund = models.CharField("Sperrgrund", max_length=200, blank=True)
    darstellung = models.JSONField("Darstellung", default=dict, blank=True)
    startseite = models.JSONField("Startseite (Karten)", default=dict, blank=True)
    # Spaltenteiler je Seite und Fensterstufe (S17): {"akte_uebersicht@fhd": [0.6667], …}
    aufteilung = models.JSONField("Aufteilung der Seiten", default=dict, blank=True)
    # Größe der Karten je Seite (Akte, System): {"akte_uebersicht": {"gewicht": {"breite": 2, "hoehe": 0}}, …}
    bereiche = models.JSONField("Größe der Karten", default=dict, blank=True)

    objects = EpmUserManager()

    class Meta:
        verbose_name = "Benutzer"
        verbose_name_plural = "Benutzer"
        ordering = ["last_name", "first_name"]

    def save(self, *args, **kwargs):
        # Django-Admin (/verwaltung/) nur für die Rolle Admin
        self.is_staff = self.rolle == Rolle.ADMIN
        if self.rolle != Rolle.ADMIN:
            self.is_superuser = False
        if self.nur_historisch:
            # ohne Login: keine Anmeldung, keine Rechte, kein Testzugang
            self.is_active = False
            self.set_unusable_password()
            self.rolle = Rolle.KEINE
            self.ist_test = False
            self.is_staff = False
            self.is_superuser = False
            felder = kwargs.get("update_fields")
            if felder is not None:
                kwargs["update_fields"] = list({*felder, "is_active", "password", "rolle", "ist_test", "is_staff",
                                                "is_superuser"})
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Benutzer werden nie gelöscht, nur gesperrt.")

    @property
    def anzeigename(self) -> str:
        """z. B. „Dr. med. M. Berger“"""
        vorname = f"{self.first_name[:1]}." if self.first_name else ""
        teile = [self.titel, vorname, self.last_name]
        name = " ".join(t for t in teile if t).strip()
        return name or self.username

    def __str__(self):
        return self.anzeigename

    # Rechte je Gruppe (accounts/rechte.py, in der Oberfläche unter Benutzer › Rechte)
    def hat_recht(self, code: str) -> bool:
        from .rechte import hat_recht

        return hat_recht(self, code)

    @property
    def rechte(self) -> list[str]:
        from .rechte import CODES, rechte_fuer

        vorhanden = rechte_fuer(self)
        return [c for c in CODES if c in vorhanden]

    @property
    def ist_admin(self):
        from epm.firma import wirksame_rolle

        return wirksame_rolle(self) == Rolle.ADMIN

    @property
    def darf_patienten_bearbeiten(self):
        return self.hat_recht("akten_bearbeiten")

    @property
    def darf_plaene_bearbeiten(self):
        return self.hat_recht("plaene_anlegen")

    @property
    def darf_plaene_freigeben(self):
        return self.hat_recht("plaene_freigeben")

    EINMAL_FELDER = ["password", "muss_kennwort_aendern", "einmal_kennwort_gueltig_bis"]

    def neues_einmal_kennwort(self) -> str:
        """Setzt ein Einmal-Kennwort mit Ablaufzeit; beim nächsten Login muss ein eigenes gewählt werden."""
        kennwort = erzeuge_einmal_kennwort()
        self.set_password(kennwort)
        self.muss_kennwort_aendern = True
        self.einmal_kennwort_gueltig_bis = timezone.now() + timedelta(hours=settings.EPM_EINMAL_KENNWORT_STUNDEN)
        return kennwort

    @property
    def einmal_kennwort_abgelaufen(self) -> bool:
        return bool(
            self.muss_kennwort_aendern
            and self.einmal_kennwort_gueltig_bis
            and self.einmal_kennwort_gueltig_bis < timezone.now()
        )

    @property
    def ist_gesperrt(self) -> bool:
        return self.gesperrt_am is not None

    SPERR_FELDER = ["is_active", "gesperrt_am", "sperrgrund", "fehlversuche"]

    def sperren(self, grund: str):
        self.is_active = False
        self.gesperrt_am = timezone.now()
        self.sperrgrund = grund[:200]

    def entsperren(self):
        self.is_active = True
        self.gesperrt_am = None
        self.sperrgrund = ""
        self.fehlversuche = 0


class Sitzung(models.Model):
    """Angemeldete Sitzung (für „Mein Konto“: Geräte anzeigen und abmelden)."""

    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sitzungen")
    sitzungsschluessel = models.CharField(max_length=40, unique=True)
    browser = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    angemeldet_am = models.DateTimeField(auto_now_add=True)
    zuletzt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Sitzung"
        verbose_name_plural = "Sitzungen"
        ordering = ["-zuletzt_am"]

    def __str__(self):
        return f"{self.benutzer} · {self.browser[:40]}"


class Mitgliedschaft(models.Model):
    """Rolle einer Person in einer weiteren Firma (Anforderung 11.10.2026). Die Rolle bei der DSKM (Hauptfirma) ist
    ``User.rolle`` wie bisher; hier stehen nur die übrigen Firmen (Regeneration Clinic) – fehlt der Eintrag, hat die
    Person dort keinen Zugang. Der Umschalter oben links zeigt nur Firmen mit Zugang."""

    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mitgliedschaften")
    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, related_name="mitgliedschaften")
    rolle = models.CharField("Rolle", max_length=20, choices=Rolle.choices, default=Rolle.KEINE)
    geaendert_am = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Mitgliedschaft"
        verbose_name_plural = "Mitgliedschaften"
        constraints = [models.UniqueConstraint(fields=["benutzer", "firma"], name="mitgliedschaft_einmal_je_firma")]

    def __str__(self):
        return f"{self.benutzer} · {self.firma}: {self.get_rolle_display()}"


class Gruppenrecht(models.Model):
    """Abweichung vom Standard der Rechte-Matrix (accounts/rechte.py) für eine Rolle."""

    rolle = models.CharField(max_length=20, choices=Rolle.choices)
    recht = models.CharField(max_length=40)
    erlaubt = models.BooleanField()
    geaendert_am = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Gruppenrecht"
        verbose_name_plural = "Gruppenrechte"
        constraints = [models.UniqueConstraint(fields=["rolle", "recht"], name="ein_eintrag_je_rolle_und_recht")]

    def __str__(self):
        return f"{self.get_rolle_display()}: {self.recht} = {'ja' if self.erlaubt else 'nein'}"


class Anmelderegeln(models.Model):
    """Genau ein Datensatz (pk=1): ob der zweite Faktor (Authenticator-App) Pflicht ist.

    Festlegung 02.10.2026: Der zweite Faktor ist freiwillig – zu viele Umstellungen auf einmal; EPM ist ohnehin nur
    über das VPN mit eigenem zweitem Faktor erreichbar. Wer ihn eingerichtet hat, meldet sich weiter damit an. Die
    Administration kann ihn hier wieder zur Pflicht machen (für Admins oder für alle)."""

    class ZweiterFaktor(models.TextChoices):
        FREIWILLIG = "freiwillig", "freiwillig"
        ADMINS = "admins", "Pflicht für Admins"
        ALLE = "alle", "Pflicht für alle"

    zweiter_faktor = models.CharField("Zweiter Faktor", max_length=12, choices=ZweiterFaktor.choices,
                                      default=ZweiterFaktor.FREIWILLIG)
    geaendert_am = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Anmelderegeln"
        verbose_name_plural = "Anmelderegeln"

    def __str__(self):
        return f"Zweiter Faktor: {self.get_zweiter_faktor_display()}"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def aktuell(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Passkey(Device):
    """Passkey (WebAuthn) als zweiter Faktor – gleichwertig zur Authenticator-App (Festlegung 08.10.2026).

    Ein django-otp-Gerät: Nach der Prüfung meldet ``django_otp.login`` die Sitzung damit an, ``is_verified()`` gilt
    wie beim Authenticator. Codes gibt es keine (``verify_token`` bleibt False). Gespeichert wird nur der öffentliche
    Schlüssel; der private bleibt im Gerät (Telefon, Windows Hello, Sicherheitsschlüssel) bzw. im Passwortmanager."""

    credential_id = models.CharField("Kennung", max_length=1400, unique=True)  # Base64URL
    public_key = models.BinaryField("Öffentlicher Schlüssel")
    sign_count = models.PositiveBigIntegerField("Zähler", default=0)
    transports = models.JSONField("Verbindungen", default=list, blank=True)
    aaguid = models.CharField("Gerätetyp (AAGUID)", max_length=36, blank=True)
    synchronisiert = models.BooleanField("Synchronisiert", default=False,
                                         help_text="Passkey liegt in einem Passwortmanager und kann auf mehreren Geräten sein.")
    angelegt_am = models.DateTimeField("Angelegt am", auto_now_add=True)
    zuletzt_am = models.DateTimeField("Zuletzt verwendet", null=True, blank=True)

    class Meta:
        verbose_name = "Passkey"
        verbose_name_plural = "Passkeys"
        ordering = ["angelegt_am"]

    def verify_token(self, token):
        return False
