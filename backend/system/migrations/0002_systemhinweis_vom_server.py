# Selbstheilung (13.10.2026): Hinweise, die der Systemagent auslöst (Rückfall auf die gute Version, knappe Platte),
# haben keinen anlegenden Benutzer.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("system", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="systemhinweis",
            name="angelegt_von",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                    to=settings.AUTH_USER_MODEL),
        ),
    ]
