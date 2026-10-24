"""Mit dem Datensatz verschwindet die Aufnahme (Entwurf verworfen, Akte gelöscht) – erst nach dem Commit."""
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Diktat


@receiver(post_delete, sender=Diktat)
def aufnahme_loeschen(sender, instance: Diktat, **kwargs):
    pfad = instance.pfad
    if pfad is not None:
        transaction.on_commit(lambda: pfad.unlink(missing_ok=True))
