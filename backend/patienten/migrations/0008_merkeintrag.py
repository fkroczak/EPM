"""„Meine Akten“ (S05): Merkliste und zuletzt geöffnete Akten je Person."""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("patienten", "0007_datenschutz"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Merkeintrag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("art", models.CharField(choices=[("merkliste", "Merkliste"), ("geoeffnet", "zuletzt geöffnet")],
                                         max_length=10)),
                ("zeitpunkt", models.DateTimeField(default=django.utils.timezone.now)),
                ("benutzer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                               to=settings.AUTH_USER_MODEL)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                              to="patienten.patient")),
            ],
            options={
                "verbose_name": "Eintrag in „Meine Akten“",
                "verbose_name_plural": "Einträge in „Meine Akten“",
                "ordering": ["-zeitpunkt", "-id"],
                "constraints": [models.UniqueConstraint(fields=("benutzer", "patient", "art"),
                                                        name="merkeintrag_eindeutig")],
            },
        ),
    ]
