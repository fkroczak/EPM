"""Technische Verwaltung an/aus (Wunsch 11.10.2026): Django-Admin (/verwaltung/) und die API-Browseroberfläche sind
standardmäßig aus. Ein Admin schaltet sie unter Administration › System für 1 oder 8 Stunden ein; danach sind sie von
selbst wieder aus. ``EPM_DJANGO_ADMIN`` bzw. ``EPM_API_BROWSABLE`` in der Server-Konfiguration legen sie fest."""
import time

from django.conf import settings
from django.http import Http404
from django.utils import timezone
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import BrowsableAPIRenderer

_ZWISCHENSPEICHER = {"bis": None, "geholt": 0.0}
GUELTIG_S = 10


def technik_bis():
    """Zeitpunkt, bis zu dem der Schalter an ist (oder None); höchstens alle 10 Sekunden aus der Datenbank."""
    if time.monotonic() - _ZWISCHENSPEICHER["geholt"] > GUELTIG_S:
        from stammdaten.models import Einstellungen

        _ZWISCHENSPEICHER.update(bis=Einstellungen.aktuell().technik_bis, geholt=time.monotonic())
    return _ZWISCHENSPEICHER["bis"]


def vergessen():
    _ZWISCHENSPEICHER["geholt"] = 0.0


def geschaltet() -> bool:
    bis = technik_bis()
    return bis is not None and bis > timezone.now()


def django_admin_an() -> bool:
    fest = getattr(settings, "EPM_DJANGO_ADMIN", None)
    return fest if fest is not None else geschaltet()


def api_ansicht_an() -> bool:
    fest = getattr(settings, "EPM_API_BROWSABLE", None)
    return fest if fest is not None else geschaltet()


class TechnikMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/verwaltung/") and not django_admin_an():
            raise Http404("Die technische Verwaltung ist ausgeschaltet.")
        return self.get_response(request)


class Verhandlung(DefaultContentNegotiation):
    """Wie üblich – nur ohne Browseroberfläche, solange sie aus ist."""

    def select_renderer(self, request, renderers, format_suffix=None):
        if not api_ansicht_an():
            renderers = [r for r in renderers if not isinstance(r, BrowsableAPIRenderer)] or renderers
        return super().select_renderer(request, renderers, format_suffix)
