import secrets

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Rolle(models.TextChoices):
    BETRACHTER = "betrachter", "Betrachter"
    MITARBEITER = "mitarbeiter", "Mitarbeiter"
    MEDIZINER = "mediziner", "Mediziner"
    ADMIN = "admin", "Admin"


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
        help_text="Aus dem Altsystem übernommener Name ohne Login (Bearbeiter alter Einträge).",
    )
    muss_kennwort_aendern = models.BooleanField("Muss Kennwort ändern", default=True)
    darstellung = models.JSONField("Darstellung", default=dict, blank=True)
    startseite = models.JSONField("Startseite (Karten)", default=dict, blank=True)

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
            self.is_active = False
            self.set_unusable_password()
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

    # Rollen-Abkürzungen
    @property
    def ist_admin(self):
        return self.rolle == Rolle.ADMIN

    @property
    def darf_patienten_bearbeiten(self):
        return self.rolle in (Rolle.MITARBEITER, Rolle.MEDIZINER)

    @property
    def darf_plaene_bearbeiten(self):
        return self.rolle == Rolle.MEDIZINER

    def neues_einmal_kennwort(self) -> str:
        """Setzt ein Einmal-Kennwort; beim nächsten Login muss ein eigenes gewählt werden."""
        kennwort = erzeuge_einmal_kennwort()
        self.set_password(kennwort)
        self.muss_kennwort_aendern = True
        return kennwort
