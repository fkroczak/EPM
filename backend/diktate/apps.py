from django.apps import AppConfig


class DiktateConfig(AppConfig):
    name = "diktate"
    verbose_name = "Diktate"

    def ready(self):
        from . import signale  # noqa: F401 – Aufnahme mit dem Datensatz löschen
