from django.apps import AppConfig


class EpmConfig(AppConfig):
    name = "epm"
    verbose_name = "EPM"

    def ready(self):
        from .fehlertexte import anwenden

        anwenden()
