from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"
    verbose_name = "Benutzer"

    def ready(self):
        from . import sitzungen  # noqa: F401  (Signale für Sitzungen)
