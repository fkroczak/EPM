"""
Gemeinsame Hilfen für die Tests aller Apps (läuft gegen die echte PostgreSQL-Datenbank).

Aufruf im Container:
    sudo docker compose run --rm backend python manage.py test
"""
import tempfile
from datetime import timedelta
from pathlib import Path

from django.test import TestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from accounts.models import Rolle, User
from patienten.models import Patient
from patienten.testdaten import stammdaten_anlegen

TMP = tempfile.mkdtemp(prefix="epm-test-")
KENNWORT = "ein-sicheres-Kennwort-123"


def benutzer(name, rolle, ist_test=False):
    u = User(username=name, first_name=name.title(), last_name="Tester", rolle=rolle, ist_test=ist_test,
             muss_kennwort_aendern=False)
    u.set_password(KENNWORT)
    u.save()
    return u


def client_fuer(user):
    """API-Client mit vollständiger Anmeldung (Kennwort + zweiter Faktor)."""
    c = APIClient()
    user.is_verified = lambda: True
    c.force_authenticate(user)
    return c


def mit_zweitem_faktor(user, anzahl_codes=5) -> list[str]:
    """Bestätigter Authenticator + Notfall-Codes, damit echte Anmeldungen (mit Sitzung) möglich sind."""
    TOTPDevice.objects.create(user=user, name="Authenticator-App", confirmed=True)
    geraet = StaticDevice.objects.create(user=user, name="Notfall-Codes", confirmed=True)
    codes = [f"code{i:04d}x" for i in range(anzahl_codes)]
    for code in codes:
        StaticToken.objects.create(device=geraet, token=code)
    return codes


def echte_anmeldung(user, code, kennwort=KENNWORT, browser="Mozilla/5.0 (Windows NT 10.0) Firefox/140.0"):
    """Anmeldung über die API wie im Browser (Kennwort, dann Notfall-Code) – mit echter Sitzung."""
    c = APIClient(HTTP_USER_AGENT=browser)
    r = c.post("/api/auth/anmelden/", {"benutzername": user.username, "kennwort": kennwort}, format="json")
    assert r.status_code == 200, r.content
    r = c.post("/api/auth/2fa/", {"code": code}, format="json")
    assert r.json()["schritt"] == "fertig", r.content
    return c


@override_settings(EPM_DOKUMENTE=Path(TMP), EPM_X_ACCEL=True)
class Grundlage(TestCase):
    @classmethod
    def setUpTestData(cls):
        stammdaten_anlegen()
        cls.mitarbeiter = benutzer("mitarbeiter", Rolle.MITARBEITER)
        cls.mediziner = benutzer("mediziner", Rolle.MEDIZINER)
        cls.betrachter = benutzer("betrachter", Rolle.BETRACHTER)
        cls.admin = benutzer("admin", Rolle.ADMIN)
        cls.patient = Patient.objects.create(nachname="Echt", vorname="Anna",
                                             geburtsdatum=timezone.localdate() - timedelta(days=20000))

    def neuer_kontakt(self, client=None, patient=None, **extra):
        c = client or client_fuer(self.mitarbeiter)
        r = c.post("/api/kontakte/", {"patient": (patient or self.patient).id,
                                      "text": "<p>Hallo <script>x</script></p>", **extra}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()
