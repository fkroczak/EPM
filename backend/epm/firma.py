"""Aktive Firma je Anfrage (Anforderung 11.10.2026: EPM für DSKM und Regeneration Clinic).

Jede Person hat je Firma eine Rolle: bei der DSKM (Hauptfirma) ``User.rolle`` wie bisher, bei weiteren Firmen eine
``accounts.Mitgliedschaft`` (fehlt sie, kein Zugang). Oben links in der Seitenleiste wählt sie, für welche Firma sie
gerade arbeitet; die Wahl steht in der Sitzung (``SITZUNG``). Die ``FirmaMiddleware`` legt für jede Anfrage fest:

- ``request.user.firma``: die aktive Firma;
- ``request.user.firmenrolle``: die Rolle in dieser Firma – nach ihr richten sich die Rechte (``wirksame_rolle``);
- die Firma als Kontext (``aktive_firma()``), damit neue Einträge einer Akte sie vermerken (``AktenEintrag.firma``),
  neue Akten ihr zugeordnet werden und Logo bzw. Briefkopf passen.

Ohne Anfrage (Verwaltungsbefehle, Hintergrundaufgaben) gibt es keine aktive Firma: dann gilt ``User.rolle`` und es wird
nicht nach Firma gefiltert.
"""
from contextvars import ContextVar

SITZUNG = "epm_firma"
HAUPTFIRMA = "dskm"

_aktiv: ContextVar = ContextVar("epm_aktive_firma", default=None)


def aktive_firma():
    """Firma der laufenden Anfrage (oder ``None``)."""
    return _aktiv.get()


def setze_aktive_firma(firma):
    """Für Tests und Hintergrundaufgaben; gibt das Token zum Zurücksetzen zurück."""
    return _aktiv.set(firma)


def zuruecksetzen(token):
    _aktiv.reset(token)


def _firmen():
    from stammdaten.models import Firma

    return list(Firma.objects.filter(aktiv=True).order_by("reihenfolge", "id"))


def rollen_je_firma(user, firmen=None) -> dict:
    """{Firma: Rolle} für alle aktiven Firmen – auch „Keine Berechtigung“."""
    from accounts.models import Mitgliedschaft, Rolle

    firmen = firmen if firmen is not None else _firmen()
    weitere = dict(Mitgliedschaft.objects.filter(benutzer=user).values_list("firma_id", "rolle")) \
        if getattr(user, "pk", None) else {}
    return {f: (user.rolle if f.kuerzel == HAUPTFIRMA else weitere.get(f.pk, Rolle.KEINE)) for f in firmen}


def mitgliedschaften(user, firmen=None) -> dict:
    """{Firma: Rolle} der Firmen, in denen die Person Zugang hat (Rolle nicht „Keine Berechtigung“)."""
    from accounts.models import Rolle

    if user is None or getattr(user, "nur_historisch", False):
        return {}
    return {f: r for f, r in rollen_je_firma(user, firmen).items() if r != Rolle.KEINE}


def admin_firmen(user, firmen=None) -> set[str]:
    """Kürzel der Firmen, in denen die Person Admin ist. Rollen in einer Firma vergibt nur ein Admin dieser Firma
    (Festlegung 11.10.2026)."""
    from accounts.models import Rolle

    return {f.kuerzel for f, r in mitgliedschaften(user, firmen).items() if r == Rolle.ADMIN}


def darf_konto_verwalten(admin, user, firmen=None, erlaubt=None) -> tuple[bool, list]:
    """Kontoweite Verwaltung (sperren, Einmal-Passwort, zweiten Faktor zurücksetzen, aus- und einblenden, Kontodaten
    wie Name oder Benutzername ändern) darf nur, wer in **jeder** Firma Admin ist, in der die Person eine Rolle hat
    (Festlegung 11.10.2026) – sonst könnte ein Admin der einen Firma Konten der anderen aussperren. Ohne Rolle in
    irgendeiner Firma (ohne Login oder überall „Keine Berechtigung“) darf jeder Admin.

    Liefert ``(erlaubt, fehlende Firmen)``; die fehlenden Firmen sind die, in denen die Person eine Rolle hat, die
    Admin-Person aber kein Admin ist (für den Hinweis in der Antwort).

    ``firmen`` (aktive Firmen) und ``erlaubt`` (``admin_firmen(admin)``) lassen sich für Listen vorab ermitteln."""
    if erlaubt is None:
        erlaubt = admin_firmen(admin, firmen)
    fehlend = [f for f in mitgliedschaften(user, firmen) if f.kuerzel not in erlaubt]
    return (not fehlend, fehlend)


def konto_verwalten_hinweis(fehlend) -> str:
    """Text der 403-Antwort, wenn ``darf_konto_verwalten`` verneint."""
    namen = ", ".join(f.name for f in fehlend)
    return (f"Dieses Konto hat auch eine Rolle bei {namen}. Das darf nur, wer dort ebenfalls Admin ist."
            if len(fehlend) == 1 else
            f"Dieses Konto hat auch Rollen bei {namen}. Das darf nur, wer dort ebenfalls Admin ist.")


def wirksame_rolle(user) -> str | None:
    """Rolle, nach der sich die Rechte gerade richten: die Rolle in der aktiven Firma, sonst ``User.rolle``."""
    if user is None:
        return None
    rolle = getattr(user, "firmenrolle", None)
    return rolle if rolle is not None else getattr(user, "rolle", None)


def waehle(user, gewuenscht: str | None = None):
    """Aktive Firma: die gewünschte, sonst die erste mit Zugang. Setzt ``user.firma`` und ``user.firmenrolle``.
    Ohne Zugang zu irgendeiner Firma: Hauptfirma mit ``User.rolle`` (meist „Keine Berechtigung“)."""
    zugang = mitgliedschaften(user)
    if zugang:
        firma = next((f for f in zugang if f.kuerzel == gewuenscht), None) or next(iter(zugang))
        user.firmenrolle = zugang[firma]
    else:
        firma = next((f for f in _firmen() if f.kuerzel == HAUPTFIRMA), None)
        user.firmenrolle = user.rolle
    user.firma = firma
    return firma


class FirmaMiddleware:
    """Nach der Anmeldung: aktive Firma aus der Sitzung bestimmen und als Kontext setzen."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        token = None
        if user is not None and user.is_authenticated:
            firma = waehle(user, request.session.get(SITZUNG))
            token = _aktiv.set(firma)
        try:
            return self.get_response(request)
        finally:
            if token is not None:
                _aktiv.reset(token)


def rolle_in(user, firma) -> str | None:
    """Rolle einer (anderen) Person in einer Firma."""
    from accounts.models import Mitgliedschaft, Rolle

    if firma is None or firma.kuerzel == HAUPTFIRMA:
        return user.rolle
    m = Mitgliedschaft.objects.filter(benutzer=user, firma=firma).values_list("rolle", flat=True).first()
    return m or Rolle.KEINE


def als_in_firma(user, firma):
    """Dieselbe Person mit den Rechten in ``firma`` (z. B. der Mediziner, der einen Plan freigegeben hat)."""
    user.firma = firma
    user.firmenrolle = rolle_in(user, firma) if firma is not None else None
    return user


def benutzer_mit_rolle(qs, rolle: str, firma=None):
    """Konten mit dieser Rolle in der Firma (ohne Angabe: der aktiven)."""
    firma = firma or aktive_firma()
    if firma is None or firma.kuerzel == HAUPTFIRMA:
        return qs.filter(rolle=rolle)
    return qs.filter(mitgliedschaften__firma=firma, mitgliedschaften__rolle=rolle).distinct()


def benutzer_der_firma(qs, firma=None):
    """Konten mit Zugang zur Firma (für Auswahllisten wie „Wer hat freigegeben?“)."""
    from accounts.models import Rolle

    firma = firma or aktive_firma()
    if firma is None or firma.kuerzel == HAUPTFIRMA:
        return qs.exclude(rolle=Rolle.KEINE)
    return qs.filter(mitgliedschaften__firma=firma).exclude(mitgliedschaften__rolle=Rolle.KEINE).distinct()
