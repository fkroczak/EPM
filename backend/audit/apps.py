from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AuditConfig(AppConfig):
    name = "audit"
    verbose_name = "Protokoll"

    def ready(self):
        from . import schutz, signale  # noqa: F401

        post_migrate.connect(schutz.installiere_trigger, sender=self, dispatch_uid="epm_trigger")
