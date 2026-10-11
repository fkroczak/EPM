from django.apps import AppConfig


class VorlagenConfig(AppConfig):
    name = "vorlagen"
    verbose_name = "Dokumentvorlagen und PDF"

    def ready(self):
        from epm.sanitize import pillow_ohne_ghostscript

        pillow_ohne_ghostscript()
