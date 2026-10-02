"""Eigene Ergänzungen der Stiftung zur mitgelieferten Hilfe (S15) – je Abschnitt ein Text, mit Historie."""
from django.db import models
from simple_history.models import HistoricalRecords


class Hilfeergaenzung(models.Model):
    """Ergänzung zu einem mitgelieferten Abschnitt (``hilfe.inhalt``), z. B. interne Abläufe oder Telefonnummern.
    Formatierter Text, beim Speichern bereinigt wie alle anderen Texte. Entfernen leert den Text; frühere Fassungen
    bleiben in der Historie (unveränderlich, Trigger)."""

    abschnitt = models.CharField(max_length=60, unique=True)
    text = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Hilfe-Ergänzung"
        verbose_name_plural = "Hilfe-Ergänzungen"

    def __str__(self):
        return self.abschnitt

    def delete(self, *args, **kwargs):
        raise PermissionError("Ergänzungen werden nicht gelöscht, nur geleert (die Historie bleibt).")
