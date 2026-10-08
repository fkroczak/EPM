# Passkeys (WebAuthn) als zweiter Faktor (Festlegung 08.10.2026)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_mitarbeiter_erweitert"),
    ]

    operations = [
        migrations.CreateModel(
            name="Passkey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="The human-readable name of this device.", max_length=64)),
                ("confirmed", models.BooleanField(default=True, help_text="Is this device ready for use?")),
                ("credential_id", models.CharField(max_length=1400, unique=True, verbose_name="Kennung")),
                ("public_key", models.BinaryField(verbose_name="Öffentlicher Schlüssel")),
                ("sign_count", models.PositiveBigIntegerField(default=0, verbose_name="Zähler")),
                ("transports", models.JSONField(blank=True, default=list, verbose_name="Verbindungen")),
                ("aaguid", models.CharField(blank=True, max_length=36, verbose_name="Gerätetyp (AAGUID)")),
                ("synchronisiert", models.BooleanField(
                    default=False,
                    help_text="Passkey liegt in einem Passwortmanager und kann auf mehreren Geräten sein.",
                    verbose_name="Synchronisiert")),
                ("angelegt_am", models.DateTimeField(auto_now_add=True, verbose_name="Angelegt am")),
                ("zuletzt_am", models.DateTimeField(blank=True, null=True, verbose_name="Zuletzt verwendet")),
                ("user", models.ForeignKey(help_text="The user that this device belongs to.",
                                           on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Passkey",
                "verbose_name_plural": "Passkeys",
                "ordering": ["angelegt_am"],
            },
        ),
    ]
