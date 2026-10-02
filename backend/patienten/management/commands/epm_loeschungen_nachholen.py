"""
Endgültige Löschungen nachholen (Art. 17 DSGVO, U15).

Läuft bei jedem Start des Backends (entrypoint.sh, nach den Migrationen) und kann jederzeit von Hand laufen:

    docker compose exec backend python manage.py epm_loeschungen_nachholen

Quelle sind die Löschliste (eigener Ordner, übersteht eine Wiederherstellung) und die Dokument-Vorgänge in der
Datenbank. Für jede Löschung gilt:
- Gibt es das Dokument wieder (gleiche Nummer UND gleiche Prüfsumme – etwa nach einer Wiederherstellung aus einer
  älteren Sicherung), wird es erneut gelöscht, mit Vorgang und Eintrag im Audit-Log.
- Liegt die Datei wieder im Dokumentordner (gleiche Prüfsumme), wird sie entfernt.
- Titel, Dateiname, Notiz und Datum werden in Historie und Audit-Log erneut geschwärzt.
- Fehlt eine Löschung aus der Datenbank in der Löschliste, wird sie dort ergänzt.
Ohne Befund passiert nichts. Fehler werden gemeldet, halten den Start aber nicht auf.

Ebenso endgültig gelöschte Akten (``patienten.datenschutz.akten_nachholen``): Bringt eine Wiederherstellung eine
gelöschte Akte zurück (gleiche Kennung, Nummer und Anlagezeitpunkt), wird sie erneut vollständig gelöscht; das
Löschprotokoll in der Datenbank und die Löschliste werden gegenseitig ergänzt.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from audit.models import SystemEreignis, protokolliere
from patienten.loeschung import datei_pruefsumme, lies_liste, schwaerze_dokument, trage_ein
from patienten.models import Dokument, DokumentVorgang


class Command(BaseCommand):
    help = "Holt endgültige Löschungen von Dokumenten nach (z. B. nach einer Wiederherstellung) und schwärzt erneut."

    def handle(self, *args, **opts):
        try:
            ergebnis = nachholen()
            # endgültig gelöschte Akten (Datenschutz): ebenfalls aus der Löschliste erneut löschen
            from patienten.datenschutz import akten_nachholen

            ergebnis.update(akten_nachholen())
        except Exception as fehler:  # noqa: BLE001 – der Start des Backends darf daran nicht scheitern
            self.stderr.write(f"WARNUNG: Löschungen konnten nicht geprüft werden: {fehler}")
            return
        if any(ergebnis.values()):
            self.stdout.write("Löschungen nachgeholt: " + ", ".join(f"{k} {v}" for k, v in ergebnis.items()))


def nachholen() -> dict:
    ergebnis = {"dokumente": 0, "dateien": 0, "geschwaerzt": 0, "liste_ergaenzt": 0}
    aus_liste = {(int(e["dokument"]), e["sha256"]): e for e in lies_liste()}
    aus_db = {}
    for v in DokumentVorgang.objects.filter(art=DokumentVorgang.Art.GELOESCHT).exclude(sha256=""):
        aus_db.setdefault((v.dokument_id, v.sha256), v)

    for schluessel, v in aus_db.items():
        if schluessel not in aus_liste:
            eintrag = {"dokument": v.dokument_id, "sha256": v.sha256, "datei": v.datei, "patient": v.von_patient_id,
                       "person": v.person_id, "geloescht_am": v.zeitpunkt.isoformat(timespec="seconds")}
            trage_ein(eintrag)
            aus_liste[schluessel] = eintrag
            ergebnis["liste_ergaenzt"] += 1

    for (dok_id, sha), e in aus_liste.items():
        dok = Dokument.objects.filter(id=dok_id, sha256=sha).select_related("patient").first()
        if dok is not None:
            pfad = dok.pfad
            with transaction.atomic():
                if (dok_id, sha) not in aus_db:
                    from accounts.models import User

                    person = User.objects.filter(id=e.get("person")).first() if e.get("person") else None
                    DokumentVorgang.objects.create(
                        art=DokumentVorgang.Art.GELOESCHT, dokument_id=dok_id, von_patient=dok.patient,
                        grund=f"Endgültige Löschung vom {_datum(e.get('geloescht_am'))} nach einer Wiederherstellung "
                              "erneut ausgeführt", person=person, sha256=sha, datei=dok.datei)
                protokolliere(SystemEreignis.Art.DOKUMENT_LOESCHUNG_NACHGEHOLT, objekt=f"Dokument {dok_id}",
                              benutzername="System", sha256=sha, geloescht_am=e.get("geloescht_am", ""),
                              akte=f"Nr. {dok.patient.nummer}")
                dok._change_reason = "Endgültig gelöscht (nach einer Wiederherstellung nachgeholt)"
                dok.delete()
            pfad.unlink(missing_ok=True)
            ergebnis["dokumente"] += 1
        datei = e.get("datei") or ""
        if datei:
            pfad = settings.EPM_DOKUMENTE / datei
            try:
                if pfad.is_file() and datei_pruefsumme(pfad) == sha:
                    pfad.unlink()
                    ergebnis["dateien"] += 1
            except OSError:
                pass
        geaendert = schwaerze_dokument(dok_id, sha)
        ergebnis["geschwaerzt"] += geaendert["historie"] + geaendert["protokoll"]
    return ergebnis


def _datum(wert) -> str:
    from audit.texte import _datum as datum

    return datum(wert or "")
