"""Modelle des KI-Dienstes von der Konsole aus verwalten (Ersteinrichtung durch `epm-ki einrichten`).

    python manage.py epm_ki_modell --liste
    python manage.py epm_ki_modell --registrieren qwen3.5-4b-q4_k_m.gguf --projektor mmproj-qwen3.5-4b-f16.gguf \
        --name "Qwen3.5-4B Q4_K_M" --quantisierung Q4_K_M [--aktivieren]

Die Prüfsumme wird aus der Datei im Modellordner (``EPM_KI_MODELLE``) berechnet. Aktivieren von der Konsole ist der
Weg für die Ersteinrichtung (Zugriff auf den Server = Admin); später wechselt man in EPM unter Administration › KI
(mit Passwort und zweitem Faktor). Beides steht im Audit-Log.
"""
import hashlib
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from audit.models import SystemEreignis, protokolliere
from ki.modellwahl import aktivieren as modell_aktivieren
from ki.models import KiModellversion

NAME = re.compile(r"^[A-Za-z0-9._-]{1,200}\.gguf$")


def sha256(pfad) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for teil in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(teil)
    return h.hexdigest()


class Command(BaseCommand):
    help = "KI-Modelle registrieren, auflisten und (Ersteinrichtung) aktivieren."

    def add_arguments(self, parser):
        parser.add_argument("--liste", action="store_true")
        parser.add_argument("--registrieren", metavar="DATEI")
        parser.add_argument("--projektor", default="")
        parser.add_argument("--name", default="")
        parser.add_argument("--quantisierung", default="")
        parser.add_argument("--aktivieren", action="store_true")
        parser.add_argument("--entfernt", metavar="DATEI", help="Datei wurde gelöscht: Einträge sperren")

    def handle(self, *args, liste=False, registrieren=None, projektor="", name="", quantisierung="",
               aktivieren=False, entfernt=None, **opt):
        if entfernt:
            n = (KiModellversion.objects.filter(datei=entfernt).exclude(status=KiModellversion.Status.AKTIV)
                 .update(status=KiModellversion.Status.GESPERRT, notiz="Datei auf dem Server gelöscht"))
            if n:
                protokolliere(SystemEreignis.Art.KI, benutzername="epm-ki (Konsole)", objekt=entfernt,
                              aktion="modell_gesperrt", modell=entfernt, grund="Datei gelöscht")
            self.stdout.write(f"{n} Einträge gesperrt.")
            return
        if liste or not registrieren:
            for mv in KiModellversion.objects.all():
                self.stdout.write(f"{mv.pk:>3}  {mv.get_status_display():<18} {mv.name:<30} {mv.datei}  "
                                  f"{mv.sha256[:12]}")
            return
        ordner = settings.EPM_KI_MODELLE
        for datei in filter(None, (registrieren, projektor)):
            if not NAME.match(datei):
                raise CommandError(f"Nur Dateinamen von GGUF-Dateien im Modellordner: {datei}")
            if not (ordner / datei).is_file():
                raise CommandError(f"{ordner / datei} fehlt (zuerst `epm-ki einspielen`).")
        self.stdout.write(f"Prüfsumme von {registrieren} wird berechnet …")
        summe = sha256(ordner / registrieren)
        mv = KiModellversion.objects.filter(sha256=summe, datei=registrieren).first()
        if mv is None:
            mv = KiModellversion.objects.create(
                name=name or registrieren.removesuffix(".gguf"), datei=registrieren, projektor=projektor,
                sha256=summe, groesse=(ordner / registrieren).stat().st_size, quantisierung=quantisierung,
                notiz="von der Konsole registriert")
            protokolliere(SystemEreignis.Art.KI, benutzername="epm-ki (Konsole)", objekt=str(mv),
                          aktion="modell_eingespielt", modell=mv.name, sha256=summe, datei=registrieren)
            self.stdout.write(f"Registriert: {mv.name} ({summe[:12]})")
        else:
            self.stdout.write(f"Schon registriert: {mv.name} ({mv.get_status_display()})")
        if aktivieren and mv.status != KiModellversion.Status.AKTIV:
            bisher = modell_aktivieren(mv, None)
            protokolliere(SystemEreignis.Art.KI, benutzername="epm-ki (Konsole)", objekt=str(mv),
                          aktion="modell_aktiviert", modell=mv.name, sha256=mv.sha256,
                          bisher=bisher.name if bisher else "", ohne_evaluation=True)
            self.stdout.write(f"Aktiv: {mv.name}" + (f" (vorher: {bisher.name})" if bisher else ""))
