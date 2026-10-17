"""Anmeldung an der Django-Verwaltung (/verwaltung/): Fehlversuche zählen wie in der App – auch ein richtiges Passwort
mit falschem Authenticator-Code – und die Sitzung wartet nach zu vielen Fehlversuchen."""
from django.core.exceptions import ValidationError
from django_otp.admin import OTPAdminAuthenticationForm


class VerwaltungAnmeldung(OTPAdminAuthenticationForm):
    def clean(self):
        from audit.models import SystemEreignis, protokolliere

        from .api import (GESPERRT_TEXT, fehlversuch, fehlversuche_zuruecksetzen, sitzung_fehlversuch,
                          sitzung_wartezeit, wartezeit_text)
        from .models import User

        if minuten := sitzung_wartezeit(self.request):
            raise ValidationError(wartezeit_text(minuten), code="wartezeit")
        try:
            daten = super().clean()
        except ValidationError:
            # Passwort falsch (user_cache leer) oder Passwort richtig und Code falsch (user_cache gesetzt)
            konto = self.user_cache or User.objects.filter(
                username=self.cleaned_data.get("username", ""), nur_historisch=False).first()
            if self.user_cache is not None:
                protokolliere(SystemEreignis.Art.ZWEITER_FAKTOR_FEHLGESCHLAGEN, self.request, benutzer=konto,
                              verwaltung=True)
            if konto is not None and konto.is_active and fehlversuch(konto, self.request, "verwaltung"):
                raise ValidationError(GESPERRT_TEXT, code="gesperrt")
            if minuten := sitzung_fehlversuch(self.request):
                raise ValidationError(wartezeit_text(minuten), code="wartezeit")
            raise
        fehlversuche_zuruecksetzen(self.request, self.get_user())
        return daten
