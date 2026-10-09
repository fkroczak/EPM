"""„Text erkennen“ an Dokumenten der Akte (F170) und „Werte übernehmen“ aus einem Dokument (F171).

Text erkennen: Der OCR-Dienst legt mit OCRmyPDF (Tesseract, deutsches Modell) eine unsichtbare Textebene über die
Seiten und ersetzt die Datei des Dokuments durch diese PDF/A. Das Aussehen der Seiten bleibt; Seiten, die schon Text
haben, bleiben unberührt (``--skip-text``). Der Text kommt in ``DokumentText`` (Suche in der Akte, Kopieren). Die
bisherige Datei wird gelöscht; Titel, Typ, Datum, Notiz bleiben. Verlauf und Audit-Log nennen beide Prüfsummen.

Werte übernehmen: Eine Arbeitskopie des Dokuments wird ein Scan mit ``quelldokument`` und läuft durch die Erkennung
und Prüfansicht von „Scans“. Beim Zuordnen entsteht kein neues Dokument – Laborbefund und BIA-Messung werden mit dem
vorhandenen verknüpft.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from audit.models import SystemEreignis, protokolliere

from .models import DokumentErkennung

log = logging.getLogger("epm.scans")

# Dateitypen, die OCRmyPDF annimmt (Bilder werden zur PDF)
ERLAUBT = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/tiff": ".tif"}
ZEITLIMIT_S = int(os.environ.get("EPM_OCRMYPDF_ZEITLIMIT", str(30 * 60)))
MAX_VERSUCHE = 3
VERFAHREN = "OCRmyPDF (Tesseract)"

# Rückgabewerte von OCRmyPDF (ocrmypdf.ExitCode)
_FEHLERTEXTE = {
    1: "Ungültige Angaben an OCRmyPDF (Programmfehler – bitte melden).",
    2: "Ungültige Angaben an OCRmyPDF (Programmfehler – bitte melden).",
    3: "Ein benötigtes Programm fehlt im Image (Ghostscript oder Tesseract).",
    4: "Die Datei ist keine lesbare PDF bzw. kein lesbares Bild.",
    5: "Die Datei konnte nicht geschrieben werden (Speicherplatz?).",
    6: "Die PDF enthält bereits Text, der nicht ersetzt werden darf.",
    7: "Ein Teilprogramm ist abgebrochen (Speicher?).",
    8: "Die PDF ist verschlüsselt bzw. geschützt – bitte ungeschützt hochladen.",
    9: "Die Einstellungen von OCRmyPDF sind ungültig (Programmfehler – bitte melden).",
    15: "Die Erkennung ist abgebrochen.",
    130: "Die Erkennung wurde unterbrochen.",
}
_PDFA_NICHT_MOEGLICH = 10   # Ergebnis ist eine gültige PDF, nur nicht PDF/A


class ErkennungFehler(Exception):
    pass


def verfuegbar() -> tuple[bool, str]:
    """OCRmyPDF und Ghostscript im Image?"""
    ocr, gs = shutil.which("ocrmypdf"), shutil.which("gs")
    if not ocr or not gs:
        fehlt = ", ".join(n for n, p in (("OCRmyPDF", ocr), ("Ghostscript", gs)) if not p)
        return False, f"fehlt im Image: {fehlt}"
    try:
        v = subprocess.run([ocr, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        g = subprocess.run([gs, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"nicht startbar: {e}"
    return True, f"OCRmyPDF {v} · Ghostscript {g}"


def erkennbar(dok) -> str | None:
    """None = „Text erkennen“ ist möglich, sonst der Grund dagegen."""
    from infusionen.models import Infusionsplan
    from patienten.models import Dokument

    if dok.herkunft == Dokument.Herkunft.SYSTEM:
        return "Von EPM erzeugte Dokumente haben ihren Text schon."
    if dok.mime not in ERLAUBT:
        return "Nur für PDF, JPG, PNG und TIFF."
    if Infusionsplan.objects.filter(freigabe_nachweis=dok).exists():
        return "Der Nachweis der Freigabe eines Infusionsplans bleibt unverändert."
    return None


# ---------------------------------------------------------------- Text erkennen: Auftrag
def anfordern(dok, benutzer) -> DokumentErkennung:
    """Auftrag anlegen (oder den offenen zurückgeben)."""
    grund = erkennbar(dok)
    if grund:
        raise ErkennungFehler(grund)
    if not dok.pfad.is_file():
        raise ErkennungFehler("Die Datei fehlt im Dokumentenverzeichnis. Bitte die Administration informieren.")
    with transaction.atomic():
        offen = (DokumentErkennung.objects.select_for_update()
                 .filter(dokument=dok, status__in=[DokumentErkennung.Status.WARTET, DokumentErkennung.Status.LAEUFT])
                 .first())
        if offen:
            return offen
        return DokumentErkennung.objects.create(dokument=dok, angefordert_von=benutzer, sha256_vorher=dok.sha256)


def stand(dok) -> dict | None:
    """Letzter Auftrag des Dokuments (für die Akte)."""
    a = DokumentErkennung.objects.filter(dokument=dok).order_by("-angefordert_am", "-id").first()
    if a is None:
        return None
    return {"id": a.id, "status": a.status, "schritt": a.schritt, "fehler": a.fehler,
            "angefordert_am": a.angefordert_am, "beendet_am": a.beendet_am, "seiten": a.seiten}


def auftrag_holen() -> DokumentErkennung | None:
    with transaction.atomic():
        a = (DokumentErkennung.objects.select_for_update(skip_locked=True)
             .filter(status=DokumentErkennung.Status.WARTET).order_by("angefordert_am", "id").first())
        if a is None:
            return None
        jetzt = timezone.now()
        a.status = DokumentErkennung.Status.LAEUFT
        a.begonnen_am = a.lebenszeichen = jetzt
        a.versuche += 1
        a.schritt = "wird vorbereitet"
        a.save(update_fields=["status", "begonnen_am", "lebenszeichen", "versuche", "schritt"])
        return a


def haengende_zuruecksetzen(grenze: timedelta) -> int:
    anzahl = 0
    for a in DokumentErkennung.objects.filter(status=DokumentErkennung.Status.LAEUFT,
                                              lebenszeichen__lt=timezone.now() - grenze):
        anzahl += 1
        if a.versuche >= MAX_VERSUCHE:
            DokumentErkennung.objects.filter(pk=a.pk).update(
                status=DokumentErkennung.Status.FEHLER, beendet_am=timezone.now(), schritt="",
                fehler="Die Erkennung wurde mehrfach abgebrochen (vermutlich Speichergrenze des Erkennungsdienstes).")
        else:
            DokumentErkennung.objects.filter(pk=a.pk).update(status=DokumentErkennung.Status.WARTET,
                                                             schritt="nach einem Abbruch erneut in der Warteschlange")
    return anzahl


def geplant_beendet(a: DokumentErkennung):
    from django.db.models import F
    from django.db.models.functions import Greatest

    DokumentErkennung.objects.filter(pk=a.pk, status=DokumentErkennung.Status.LAEUFT).update(
        status=DokumentErkennung.Status.WARTET, schritt="Erkennungsdienst neu gestartet – geht gleich weiter",
        versuche=Greatest(F("versuche") - 1, 0))


def bereinigen(tage: int = 30) -> int:
    """Erledigte Aufträge nach ``tage`` Tagen entfernen (sie enthalten nur Zeitpunkte und Prüfsummen)."""
    grenze = timezone.now() - timedelta(days=tage)
    n, _ = DokumentErkennung.objects.filter(status__in=[DokumentErkennung.Status.FERTIG,
                                                        DokumentErkennung.Status.FEHLER],
                                            beendet_am__lt=grenze).delete()
    return n


# ---------------------------------------------------------------- Text erkennen: Ausführung (OCR-Dienst)
def ocrmypdf_befehl(eingabe: Path, ausgabe: Path, *, bild: bool, threads: int) -> list[str]:
    befehl = [
        "ocrmypdf",
        "--language", "deu",
        "--rotate-pages",            # quer oder kopfüber gescannte Seiten aufrichten (Tesseract-OSD)
        "--skip-text",               # Seiten mit Text bleiben, wie sie sind
        "--output-type", "pdfa",     # Archivformat
        "--optimize", "1",           # verlustfrei
        "--jobs", str(max(1, threads)),
        "--tesseract-timeout", "600",
        "--quiet",
    ]
    if bild:
        befehl += ["--image-dpi", "300"]  # nur genutzt, wenn das Bild selbst keine Auflösung angibt
    return befehl + [str(eingabe), str(ausgabe)]


def _text_der_pdf(daten: bytes) -> tuple[str, int]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(daten)
    try:
        seiten = []
        for i in range(len(pdf)):
            seite = pdf[i]
            tp = seite.get_textpage()
            try:
                seiten.append(tp.get_text_range().replace("\r\n", "\n").strip())
            finally:
                tp.close()
                seite.close()
        return "\n\n".join(t for t in seiten if t), len(pdf)
    finally:
        pdf.close()


def ausfuehren(a: DokumentErkennung, schritt=None) -> DokumentErkennung:
    """Einen Auftrag abarbeiten. Fehler stehen am Auftrag; das Dokument bleibt dann unverändert."""
    from .ocr.aufbereitung import tessdata_umgebung

    melden = schritt or (lambda _t: None)
    t0 = time.monotonic()
    try:
        dok = a.dokument
        if dok.sha256 != a.sha256_vorher:
            raise ErkennungFehler("Die Datei wurde inzwischen geändert – bitte erneut anfordern.")
        grund = erkennbar(dok)
        if grund:
            raise ErkennungFehler(grund)
        if not dok.pfad.is_file():
            raise ErkennungFehler("Die Datei fehlt im Dokumentenverzeichnis.")
        threads = int(os.environ.get("EPM_OCR_THREADS", "2"))
        with tempfile.TemporaryDirectory(prefix="epm-ocrmypdf-") as tmp:
            eingabe = Path(tmp) / f"eingabe{ERLAUBT[dok.mime]}"
            ausgabe = Path(tmp) / "ausgabe.pdf"
            shutil.copyfile(dok.pfad, eingabe)
            umgebung = {**os.environ, **tessdata_umgebung(), "OMP_THREAD_LIMIT": "1", "TMPDIR": tmp, "HOME": tmp}
            melden("OCRmyPDF liest die Seiten")
            try:
                lauf = subprocess.run(ocrmypdf_befehl(eingabe, ausgabe, bild=dok.mime != "application/pdf",
                                                      threads=threads),
                                      capture_output=True, text=True, timeout=ZEITLIMIT_S, env=umgebung)
            except FileNotFoundError:
                raise ErkennungFehler("OCRmyPDF fehlt im Image.") from None
            except subprocess.TimeoutExpired:
                raise ErkennungFehler(f"Die Erkennung dauerte länger als {ZEITLIMIT_S // 60} Minuten.") from None
            hinweis = ""
            if lauf.returncode == _PDFA_NICHT_MOEGLICH:
                hinweis = "als PDF (PDF/A war nicht möglich)"
            elif lauf.returncode != 0:
                rest = (lauf.stderr or "").strip().splitlines()[-3:]
                log.warning("OCRmyPDF %s für Dokument %s: %s", lauf.returncode, dok.id, " | ".join(rest))
                raise ErkennungFehler(_FEHLERTEXTE.get(lauf.returncode, f"OCRmyPDF meldet Fehler {lauf.returncode}.")
                                      + (f" ({rest[-1][:200]})" if rest else ""))
            if not ausgabe.is_file() or ausgabe.stat().st_size == 0:
                raise ErkennungFehler("OCRmyPDF hat keine Datei erzeugt.")
            daten = ausgabe.read_bytes()
        melden("Text übernehmen")
        text, seiten = _text_der_pdf(daten)
        if not text.strip():
            raise ErkennungFehler("Auf den Seiten wurde kein Text erkannt – das Dokument bleibt unverändert.")
        ersetzen(a, daten, text, seiten, hinweis)
        a.refresh_from_db()
        DokumentErkennung.objects.filter(pk=a.pk).update(dauer_s=round(time.monotonic() - t0, 1))
    except ErkennungFehler as fehler:
        DokumentErkennung.objects.filter(pk=a.pk).update(status=DokumentErkennung.Status.FEHLER, schritt="",
                                                         fehler=str(fehler)[:1000], beendet_am=timezone.now())
    except Exception as fehler:  # noqa: BLE001
        log.exception("Texterkennung von Dokument %s fehlgeschlagen", a.dokument_id)
        DokumentErkennung.objects.filter(pk=a.pk).update(status=DokumentErkennung.Status.FEHLER, schritt="",
                                                         fehler=f"Die Erkennung ist fehlgeschlagen: {str(fehler)[:500]}",
                                                         beendet_am=timezone.now())
    a.refresh_from_db()
    return a


def ersetzen(a: DokumentErkennung, daten: bytes, text: str, seiten: int, hinweis: str = ""):
    """Datei des Dokuments in einem Schritt ersetzen: neue Datei schreiben, Datenbank ändern, alte Datei löschen.
    Schlägt die Datenbank fehl, wird die neue Datei wieder entfernt; das Dokument bleibt wie es war."""
    from patienten.api import speichere_datei
    from patienten.models import Dokument, DokumentText

    dok = Dokument.objects.select_related("patient").get(pk=a.dokument_id)  # aktuell (z. B. nach Umhängen)
    name = (dok.originalname.rsplit(".", 1)[0] if "." in dok.originalname else dok.originalname)[:250] + ".pdf"
    meta = speichere_datei(dok.patient, ContentFile(daten, name=name), "application/pdf")
    neu_pfad = settings.EPM_DOKUMENTE / meta["datei"]
    try:
        with transaction.atomic():
            dok = Dokument.objects.select_for_update().select_related("patient").get(pk=dok.pk)
            if dok.sha256 != a.sha256_vorher:
                raise ErkennungFehler("Die Datei wurde inzwischen geändert – bitte erneut anfordern.")
            if dok.patient.ist_abgeschlossen:
                raise ErkennungFehler("Die Akte ist abgeschlossen – das Dokument bleibt unverändert.")
            alt_pfad, alt_sha = dok.pfad, dok.sha256
            dok.datei, dok.originalname, dok.mime = meta["datei"], meta["originalname"], meta["mime"]
            dok.groesse, dok.sha256 = meta["groesse"], meta["sha256"]
            dok._history_user = a.angefordert_von
            dok._change_reason = "Text erkannt: Datei durch dieselbe PDF mit Textebene ersetzt"
            dok.save()
            DokumentText.objects.update_or_create(dokument=dok, defaults={
                "text": text, "sicherheit": None, "verfahren": VERFAHREN, "erkannt_am": timezone.now()})
            protokolliere(SystemEreignis.Art.DOKUMENT_TEXT_ERKANNT, benutzer=a.angefordert_von,
                          objekt=f"Dokument {dok.id}", titel=dok.titel, sha256=dok.sha256, sha256_vorher=alt_sha,
                          seiten=seiten, verfahren=VERFAHREN, patient_id=dok.patient_id,
                          **({"hinweis": hinweis} if hinweis else {}))
            DokumentErkennung.objects.filter(pk=a.pk).update(
                status=DokumentErkennung.Status.FERTIG, schritt=hinweis, fehler="", beendet_am=timezone.now(),
                sha256_nachher=dok.sha256, seiten=seiten)
            if alt_pfad != neu_pfad:
                transaction.on_commit(lambda: alt_pfad.unlink(missing_ok=True), robust=True)
    except BaseException:
        neu_pfad.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------- Werte übernehmen (F171)
def als_scan(dok, benutzer):
    """Arbeitskopie des Dokuments als Scan (Erkennung und Prüfansicht wie in „Scans“). Ein offener Scan zum selben
    Dokument und Benutzer wird wiederverwendet."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from . import dienst
    from .models import Scan

    if dok.mime not in ERLAUBT:
        raise ErkennungFehler("Werte lassen sich nur aus PDF, JPG, PNG und TIFF übernehmen.")
    if not dok.pfad.is_file():
        raise ErkennungFehler("Die Datei fehlt im Dokumentenverzeichnis. Bitte die Administration informieren.")
    vorhanden = Scan.objects.filter(quelldokument=dok, hochgeladen_von=benutzer).first()
    if vorhanden is not None:
        return vorhanden
    datei = SimpleUploadedFile(dok.originalname or f"dokument{ERLAUBT[dok.mime]}", dok.pfad.read_bytes(), dok.mime)
    try:
        scan = dienst.neuer_scan([datei], benutzer, titel=dok.titel)
    except dienst.ScanFehler as fehler:
        raise ErkennungFehler(str(fehler)) from None
    Scan.objects.filter(pk=scan.pk).update(quelldokument=dok, ist_test=dok.patient.ist_test)
    scan.refresh_from_db()
    return scan
