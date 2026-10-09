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
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from audit.models import SystemEreignis, protokolliere
from patienten.loeschung import (
    datei_pruefsumme, lies_liste, nachholen_stand, nachholen_stand_schreiben, schwaerze_dokument, trage_ein,
    unlesbare_zeilen,
)
from patienten.models import Dokument, DokumentVorgang

# Was im Ergebnis „etwas getan“ bedeutet – mit dem Wortlaut für Audit-Log und Ausgabe
GETAN = (("akten", "Akten erneut gelöscht"), ("dokumente", "Dokumente erneut gelöscht"),
         ("dateien", "Dateien entfernt"), ("ordner_entfernt", "Dokumentenordner entfernt"),
         ("geschwaerzt", "Einträge erneut geschwärzt"), ("liste_ergaenzt", "Dokument-Löschungen in der Löschliste ergänzt"),
         ("akten_liste_ergaenzt", "Akten-Löschungen in der Löschliste ergänzt"),
         ("protokoll_ergaenzt", "Einträge im Löschprotokoll ergänzt"))


class Command(BaseCommand):
    help = "Holt endgültige Löschungen von Dokumenten nach (z. B. nach einer Wiederherstellung) und schwärzt erneut."

    def add_arguments(self, parser):
        parser.add_argument("--streng", action="store_true",
                            help="Mit Fehler enden, wenn nicht alles nachgeholt werden konnte (so ruft der Systemagent "
                                 "den Befehl nach einer Wiederherstellung auf; beim Start des Backends ohne)")

    def handle(self, *args, **opts):
        # endgültig gelöschte Akten (Datenschutz) ebenfalls aus der Löschliste erneut löschen – unabhängig von den
        # Dokumenten: scheitert das eine, läuft das andere trotzdem
        from patienten.datenschutz import akten_nachholen

        ergebnis, probleme = {}, []
        for was, schritt in (("Dokumente", nachholen), ("Akten", akten_nachholen)):
            try:
                ergebnis.update(schritt())
            except Exception as fehler:  # noqa: BLE001 – der Start des Backends darf daran nicht scheitern
                self.stderr.write(f"WARNUNG: Löschungen ({was}) konnten nicht geprüft werden: {fehler}")
                probleme.append(f"{was} nicht geprüft ({type(fehler).__name__})")
        if ergebnis.get("akten_fehler"):
            probleme.append(f"{ergebnis['akten_fehler']} Akten nicht nachgeholt")
        try:
            unlesbar = unlesbare_zeilen()
        except OSError as fehler:
            unlesbar = 0
            probleme.append(f"Löschliste nicht lesbar ({type(fehler).__name__})")
        if unlesbar:
            probleme.append(f"{unlesbar} Zeilen der Löschliste nicht lesbar")
        getan = [f"{ergebnis[k]} {name}" for k, name in GETAN if ergebnis.get(k)]
        if getan:
            self.stdout.write("Löschungen nachgeholt: " + ", ".join(getan))
        self._festhalten(getan, probleme)
        if probleme:
            self.stderr.write("WARNUNG: Löschungen nach Art. 17 DSGVO nicht vollständig nachgeholt: " + "; ".join(probleme))
            if opts.get("streng"):
                raise CommandError("Löschungen nicht vollständig nachgeholt: " + "; ".join(probleme))

    def _festhalten(self, getan, probleme):
        """Ergebnis sichtbar machen (Gegenprüfung 02.10.2026, O-28): Stand neben der Löschliste für die Backup-Seite
        und die Startseite, Eintrag im Audit-Log (Gruppe „System“). Ohne Befund und ohne vorherigen Fehler entsteht
        kein Eintrag – der Befehl läuft bei jedem Start. Die Texte nennen Zahlen, keine Namen und keine Nummern."""
        vorher = nachholen_stand()
        if probleme:
            status = "fehler"
            text = ("Löschungen nach Art. 17 DSGVO konnten nicht vollständig nachgeholt werden: " + "; ".join(probleme)
                    + (" – nachgeholt: " + ", ".join(getan) if getan else ""))
        elif getan:
            status, text = "ok", "Löschungen nach Art. 17 DSGVO nachgeholt: " + ", ".join(getan)
        elif vorher and vorher["status"] == "fehler":
            status, text = "ok", "Löschungen nach Art. 17 DSGVO geprüft: jetzt vollständig, nichts nachzuholen"
        else:
            status, text = "ok", ""
        if vorher is None or vorher["status"] != status or (text and vorher.get("text") != text):
            try:
                nachholen_stand_schreiben(status, text or (vorher or {}).get("text", ""), timezone.now().isoformat(timespec="seconds"))
            except OSError as fehler:
                self.stderr.write(f"WARNUNG: Stand des Nachholens nicht gespeichert: {fehler}")
        if not text or (vorher and vorher["status"] == status == "fehler" and vorher.get("text") == text):
            return   # nichts zu melden bzw. derselbe Fehler wie beim letzten Start: nicht bei jedem Start erneut
        try:
            protokolliere(SystemEreignis.Art.SYSTEM, benutzername="System", objekt="Löschliste",
                          ereignis="loeschungen_nachholen", status=status, name=text)
        except Exception as fehler:  # noqa: BLE001 – auch ohne Eintrag soll das Backend starten
            self.stderr.write(f"WARNUNG: Eintrag im Audit-Log nicht möglich: {fehler}")


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
        # auch eine frühere Fassung (vor „Text erkennen“, F170) ist dasselbe gelöschte Dokument
        fruehere = [x for x in (e.get("fruehere_sha256") or []) if isinstance(x, str) and x]
        dok = Dokument.objects.filter(id=dok_id, sha256__in=[sha, *fruehere]).select_related("patient").first()
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
        for pruefsumme in (sha, *fruehere):
            geaendert = schwaerze_dokument(dok_id, pruefsumme)
            ergebnis["geschwaerzt"] += geaendert["historie"] + geaendert["protokoll"]
    return ergebnis


def _datum(wert) -> str:
    from audit.texte import _datum as datum

    return datum(wert or "")
