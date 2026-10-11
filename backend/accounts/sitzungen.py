"""Angemeldete Sitzungen erfassen (Gerät/Browser, IP, zuletzt aktiv) – für „Mein Konto“."""
from datetime import timedelta

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.sessions.models import Session
from django.dispatch import receiver
from django.utils import timezone

from audit.models import browser_kurz, client_ip

from .models import Sitzung

AKTUALISIEREN_NACH = timedelta(minutes=1)


@receiver(user_logged_in, dispatch_uid="epm_sitzung_an")
def _sitzung_an(sender, request, user, **kwargs):
    if request is None or not getattr(request, "session", None):
        return
    if not request.session.session_key:
        request.session.save()
    Sitzung.objects.update_or_create(
        sitzungsschluessel=request.session.session_key,
        defaults={
            "benutzer": user,
            "browser": browser_kurz(request.META.get("HTTP_USER_AGENT", ""))[:300],
            "ip": client_ip(request),
            "zuletzt_am": timezone.now(),
        },
    )


@receiver(user_logged_out, dispatch_uid="epm_sitzung_ab")
def _sitzung_ab(sender, request, user, **kwargs):
    if request is not None and getattr(request, "session", None) and request.session.session_key:
        Sitzung.objects.filter(sitzungsschluessel=request.session.session_key).delete()


class SitzungMiddleware:
    """Hält „zuletzt aktiv“ aktuell (höchstens einmal pro Minute ein Datenbankzugriff) und verlängert die Sitzung um
    30 Minuten ab jeder Anfrage. Dabei wird nur der Ablauf geschrieben, nicht die Daten der Sitzung: Laufen zwei Anfragen
    gleichzeitig, überschreibt die spätere so nicht, was die frühere geändert hat (z. B. die gewählte Firma)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        antwort = self.get_response(request)
        user = getattr(request, "user", None)
        sitzung = getattr(request, "session", None)
        schluessel = getattr(sitzung, "session_key", None)
        if schluessel and not sitzung.modified and antwort.status_code < 500:
            from django.conf import settings

            Session.objects.filter(session_key=schluessel, expire_date__gt=timezone.now()).update(
                expire_date=timezone.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE))
        if user is not None and user.is_authenticated and schluessel:
            grenze = timezone.now() - AKTUALISIEREN_NACH
            Sitzung.objects.filter(sitzungsschluessel=schluessel, zuletzt_am__lt=grenze).update(zuletzt_am=timezone.now())
        return antwort


def aktive_sitzungen(user):
    """Sitzungen des Benutzers, deren Django-Sitzung noch gültig ist; abgelaufene werden aufgeräumt."""
    gueltig = set(
        Session.objects.filter(
            expire_date__gt=timezone.now(),
            session_key__in=Sitzung.objects.filter(benutzer=user).values("sitzungsschluessel"),
        ).values_list("session_key", flat=True)
    )
    Sitzung.objects.filter(benutzer=user).exclude(sitzungsschluessel__in=gueltig).delete()
    return Sitzung.objects.filter(benutzer=user)


def schluessel_erneuert(alt: str | None, neu: str | None):
    """Nach ``cycle_key`` (z. B. Passwortwechsel) gehört die erfasste Sitzung zum neuen Schlüssel."""
    if alt and neu and alt != neu:
        Sitzung.objects.filter(sitzungsschluessel=alt).update(sitzungsschluessel=neu)


def sitzung_beenden(sitzung: Sitzung):
    Session.objects.filter(session_key=sitzung.sitzungsschluessel).delete()
    sitzung.delete()


def alle_sitzungen_beenden(user, ausser: str | None = None):
    """z. B. nach Sperre oder neuem Einmal-Passwort: alle anderen Anmeldungen beenden."""
    for s in Sitzung.objects.filter(benutzer=user).exclude(sitzungsschluessel=ausser or ""):
        sitzung_beenden(s)


class RechteStandMiddleware:
    """Setzt bei angemeldeten API-Anfragen den Kopf ``X-EPM-Rechte`` (siehe ``rechte.rechte_stand``)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        antwort = self.get_response(request)
        user = getattr(request, "user", None)
        if request.path.startswith("/api/") and user is not None and user.is_authenticated:
            from .rechte import rechte_stand

            antwort["X-EPM-Rechte"] = rechte_stand(user)
        return antwort
