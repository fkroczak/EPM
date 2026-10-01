# Testkonten für die Browsertests (nur im CI-Stack, nie auf einem echten Server ausführen).
# Aufruf: docker compose exec -T backend python manage.py shell < frontend/e2e/vorbereiten.py
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.models import Rolle, User

KENNWORT = "E2E-Kennwort-sicher-2026"
# RFC-6238-Testschlüssel „12345678901234567890“ als Hex – die Tests berechnen daraus die Codes
SCHLUESSEL = "3132333435363738393031323334353637383930"

KONTEN = [
    ("e2e.mediziner", "Dr. med.", "Mara", "Medizin", "MM", "Ärztin", Rolle.MEDIZINER, False),
    ("e2e.mitarbeiter", "", "Sven", "Mitarbeit", "SM", "Ernährungsberater", Rolle.MITARBEITER, False),
    ("e2e.betrachter", "", "Bea", "Betrachtung", "BB", "Verwaltung", Rolle.BETRACHTER, False),
    ("e2e.admin", "", "Ada", "Admin", "AA", "Systemverwaltung", Rolle.ADMIN, False),
    ("e2e.test", "", "Tina", "Testzugang", "TT", "Schulung", Rolle.MEDIZINER, True),
]

for name, titel, vor, nach, kuerzel, funktion, rolle, test in KONTEN:
    user = User.objects.filter(username=name).first() or User(username=name)
    user.titel, user.first_name, user.last_name, user.kuerzel, user.funktion = titel, vor, nach, kuerzel, funktion
    user.rolle, user.ist_test, user.muss_kennwort_aendern = rolle, test, False
    user.set_password(KENNWORT)
    user.save()
    TOTPDevice.objects.filter(user=user).delete()
    StaticDevice.objects.filter(user=user).delete()
    TOTPDevice.objects.create(user=user, name="Authenticator-App", key=SCHLUESSEL, confirmed=True)
    geraet = StaticDevice.objects.create(user=user, name="Notfall-Codes", confirmed=True)
    for i in range(40):
        StaticToken.objects.create(device=geraet, token=f"e2e{i:04d}code")

print("Testkonten angelegt:", ", ".join(k[0] for k in KONTEN))
