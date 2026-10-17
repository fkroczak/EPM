"""Abläufe rund um Scans – vom Backend (Hochladen, Bearbeiten, Zuordnen) und vom OCR-Dienst (Erkennen, Aufräumen).

Erkannt wird ausschließlich im Container ``ocr`` (``manage.py epm_ocr``): Er hält die Modelle im Speicher, arbeitet
einen Scan nach dem anderen ab und räumt stündlich auf. Das Backend legt nur Aufträge an (Status „wartet“).
"""
from __future__ import annotations

import gc
import hashlib
import logging
import os
import secrets
import shutil
import tempfile
import threading
import time
from datetime import timedelta
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from audit.models import SystemEreignis, protokolliere
from stammdaten.models import Einstellungen

from .models import Scan, ScanSeite
from .ocr import auswertung, fusion, laden

log = logging.getLogger("epm.scans")
A = SystemEreignis.Art

# Während der Erkennung schreibt der Dienst alle HERZSCHLAG_S Sekunden ein Lebenszeichen (eigener Faden, auch mitten
# in einer langen Seite). Bleibt es länger als HAENGT_NACH aus, ist der Dienst beendet worden (Neustart, Speicher-
# grenze) – der Scan kommt sofort wieder in die Warteschlange, nicht erst bei der stündlichen Bereinigung.
HERZSCHLAG_S = 20
HAENGT_NACH = timedelta(seconds=90)
# Abbrüche ohne Fortschritt (keine Seite fertig geworden), danach Fehler. Eine einzelne Seite wird nach dem ersten
# Abbruch sparsamer, nach dem zweiten nur mit Tesseract erkannt und nach dem dritten als Fehler markiert.
MAX_VERSUCHE = 4
MAX_ABBRUECHE_SEITE = 3


class ScanFehler(ValueError):
    """Verständliche Meldung für die Oberfläche."""


# ---------------------------------------------------------------- Speicher
def speicher_belegt() -> int:
    return int(Scan.objects.aggregate(s=Sum("belegt"))["s"] or 0)


def _groesse_ordner(pfad: Path) -> int:
    gesamt = 0
    if pfad.is_dir():
        for f in pfad.iterdir():
            try:
                gesamt += f.stat().st_size
            except OSError:
                pass
    return gesamt


def belegung_aktualisieren(scan: Scan):
    scan.belegt = _groesse_ordner(scan.pfad)
    Scan.objects.filter(pk=scan.pk).update(belegt=scan.belegt)


def dienst_stand() -> dict | None:
    """Was der OCR-Dienst zuletzt über sich geschrieben hat (Lebenszeichen, Verfahren), None wenn nie gelaufen."""
    import json

    pfad = settings.EPM_SCANS / ".dienst" / "stand.json"
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        from datetime import datetime

        alter = (timezone.now() - datetime.fromisoformat(daten["lebenszeichen"])).total_seconds()
    except (KeyError, ValueError, TypeError):
        alter = None
    daten["laeuft"] = alter is not None and alter < 180
    return daten


def verfahren() -> dict:
    """Bereitstehende Verfahren, wie der OCR-Dienst sie meldet (er allein lädt die Modelle und kennt seine
    Speichergrenze); ohne frische Meldung aus dem Image geschätzt."""
    from .ocr.erkennung import verfahren_stand

    d = dienst_stand()
    if d and d.get("laeuft") and isinstance(d.get("verfahren"), dict):
        return d["verfahren"]
    return verfahren_stand(laden=False)


def stand(user=None) -> dict:
    """Zahlen für Navigation, Startseite und Systemseite."""
    e = Einstellungen.aktuell()
    qs = sichtbare_scans(user) if user is not None else Scan.objects.all()
    jetzt = timezone.now()
    belegt = speicher_belegt()
    grenze = e.scans_max_mb * 1024 * 1024
    return {
        "offen": qs.filter(status=Scan.Status.FERTIG).count(),
        "laufend": qs.filter(status__in=[Scan.Status.WARTET, Scan.Status.LAEUFT]).count(),
        "in_arbeit": qs.filter(status=Scan.Status.LAEUFT).count(),
        "wartend": qs.filter(status=Scan.Status.WARTET).count(),
        # Seiten, bei denen der Dienst schon einmal abgebrochen wurde (meist Speichergrenze, siehe Systemseite)
        "abbrueche": ScanSeite.objects.filter(Q(abbrueche__gt=0) | Q(info__sparstufe__gte=1), scan__in=qs).count(),
        "fehler": qs.filter(status=Scan.Status.FEHLER).count(),
        "gesamt": qs.count(),
        "laeuft_bald_ab": qs.filter(laeuft_ab_am__lte=jetzt + timedelta(hours=24)).count(),
        "belegt": belegt,
        "grenze": grenze,
        "prozent": round(100 * belegt / grenze, 1) if grenze else 0,
        "anzahl_grenze": e.scans_max_anzahl,
        "anzahl_alle": Scan.objects.count(),
    }


def sichtbare_scans(user):
    """Scans, die diese Person sieht: Scans von Testbenutzern nur mit „Testdaten sehen“; Testbenutzer sehen nur
    Scans von Testbenutzern (wie bei den Akten)."""
    from accounts.rechte import sieht_testdaten
    from epm.api_basis import patienten_fuer

    # Arbeitskopien von Akte-Dokumenten (F171) nur für Personen, die die Akte sehen (z. B. nicht bei Einschränkung)
    qs = Scan.objects.filter(Q(quelldokument__isnull=True) | Q(quelldokument__patient__in=patienten_fuer(user)))
    firma = getattr(user, "firma", None)
    if firma is not None:  # Eingang der aktiven Firma (11.10.2026); ältere Scans ohne Firma gehören der DSKM
        qs = qs.filter(Q(firma=firma) | Q(firma__isnull=True) if firma.kuerzel == "dskm" else Q(firma=firma))
    if getattr(user, "ist_test", False):
        return qs.filter(ist_test=True)
    if not sieht_testdaten(user):
        return qs.filter(ist_test=False)
    return qs


# ---------------------------------------------------------------- Hochladen
def _schreiben(ziel: Path, daten) -> tuple[int, str]:
    """Atomar schreiben (Datei-Teile oder Bytes), SHA-256 und Größe liefern."""
    h = hashlib.sha256()
    groesse = 0
    fd, tmp = tempfile.mkstemp(dir=ziel.parent, prefix=".neu-")
    try:
        with os.fdopen(fd, "wb") as f:
            teile = daten.chunks() if hasattr(daten, "chunks") else [daten]
            for teil in teile:
                h.update(teil)
                groesse += len(teil)
                f.write(teil)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o640)
        os.replace(tmp, ziel)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return groesse, h.hexdigest()


def neuer_scan(dateien: list, benutzer, titel: str = "") -> Scan:
    """Eine oder mehrere Dateien (mehrere Fotos = mehrere Seiten) als ein Scan. Die Erkennung übernimmt der OCR-Dienst."""
    if not dateien:
        raise ScanFehler("Bitte eine Datei auswählen.")
    e = Einstellungen.aktuell()
    if Scan.objects.count() >= e.scans_max_anzahl:
        raise ScanFehler(f"Es liegen bereits {e.scans_max_anzahl} Scans vor (Obergrenze). Bitte zuerst zuordnen "
                         "oder löschen.")
    gesamt = sum(d.size for d in dateien)
    if gesamt > settings.EPM_UPLOAD_MAX_MB * 1024 * 1024:
        raise ScanFehler(f"Zusammen größer als {settings.EPM_UPLOAD_MAX_MB} MB.")
    if speicher_belegt() + gesamt * 4 > e.scans_max_mb * 1024 * 1024:
        # Seitenbilder brauchen ein Mehrfaches der hochgeladenen Datei
        raise ScanFehler("Der Speicher für Scans ist voll (Obergrenze unter Vorlagen › Grenzwerte). Bitte zuerst "
                         "zuordnen oder löschen.")
    arten = []
    for d in dateien:
        d.seek(0)
        mime = laden.dateityp(d.read(64))
        d.seek(0)
        if mime is None:
            raise ScanFehler(f"„{d.name}“: Erlaubt sind PDF, JPG, PNG, TIFF, WEBP, BMP"
                             + (" und HEIC" if laden.HEIC else "") + ".")
        arten.append(mime)
    ordner = secrets.token_hex(16)
    pfad = settings.EPM_SCANS / ordner
    pfad.mkdir(mode=0o750, parents=True)
    try:
        summen = []
        for nr, d in enumerate(dateien, 1):
            _, sha = _schreiben(pfad / f"original-{nr}", d)
            summen.append(sha)
        namen = [d.name for d in dateien]
        name = namen[0] + (f" (+{len(namen) - 1} weitere)" if len(namen) > 1 else "")
        jetzt = timezone.now()
        scan = Scan.objects.create(
            titel=(titel or os.path.splitext(namen[0])[0] or "Scan")[:200], originalname=name[:255],
            mime=arten[0], groesse=gesamt, sha256=summen[0] if len(summen) == 1 else hashlib.sha256(
                "".join(summen).encode()).hexdigest(),
            ordner=ordner, hochgeladen_von=benutzer, ist_test=bool(getattr(benutzer, "ist_test", False)),
            firma=getattr(benutzer, "firma", None),
            laeuft_ab_am=jetzt + timedelta(days=e.scans_frist_tage),
            auswertung={"originale": [{"name": n[:200], "mime": m} for n, m in zip(namen, arten)]},
        )
    except BaseException:
        shutil.rmtree(pfad, ignore_errors=True)
        raise
    belegung_aktualisieren(scan)
    return scan


def originale(scan: Scan) -> list[Path]:
    return sorted(scan.pfad.glob("original-*"), key=lambda p: int(p.name.split("-")[1]))


# ---------------------------------------------------------------- Verlängern, löschen, aufräumen
def verlaengern(scan: Scan, benutzer, request=None):
    e = Einstellungen.aktuell()
    hoechst = scan.hochgeladen_am + timedelta(days=e.scans_hoechst_tage)
    neu = min(max(scan.laeuft_ab_am, timezone.now()) + timedelta(days=e.scans_verlaengerung_tage), hoechst)
    if neu <= scan.laeuft_ab_am + timedelta(minutes=1):
        raise ScanFehler(f"Die Höchstdauer von {e.scans_hoechst_tage} Tagen ab dem Hochladen ist erreicht – "
                         "bitte zuordnen oder den Text herauskopieren.")
    scan.laeuft_ab_am = neu
    scan.verlaengert_anzahl += 1
    Scan.objects.filter(pk=scan.pk).update(laeuft_ab_am=neu, verlaengert_anzahl=scan.verlaengert_anzahl)
    protokolliere(A.SCAN, request, benutzer=benutzer, objekt=str(scan), aktion="verlaengert",
                  bis=neu.isoformat(timespec="minutes"), scan=scan.pk)
    return neu


def entfernen(scan: Scan):
    """Datenbankeintrag und Dateien endgültig entfernen (nach dem Zuordnen, beim Löschen, nach Ablauf)."""
    pfad = scan.pfad
    scan.delete()
    transaction.on_commit(lambda: shutil.rmtree(pfad, ignore_errors=True), robust=True)


def entfernen_wenn_ruhend(pk) -> bool:
    """``entfernen``, aber nicht während der Erkennung: Die Zeile wird gesperrt und der Stand erneut geprüft (der
    OCR-Dienst könnte den Scan eben geholt haben). In einer Transaktion aufrufen. → entfernt?"""
    scan = Scan.objects.select_for_update().filter(pk=pk).exclude(status=Scan.Status.LAEUFT).first()
    if scan is None:
        return False
    entfernen(scan)
    return True


def originale_verwerfen(scan: Scan):
    """Nach dem Entfernen oder Abtrennen von Seiten enthielte das hochgeladene Original Seiten, die nicht mehr zum Scan
    gehören (evtl. anderer Patienten) – es wird nicht mehr angeboten und gelöscht. In einer Transaktion aufrufen."""
    a = dict(scan.auswertung or {})
    a["originale"] = []
    scan.auswertung = a
    Scan.objects.filter(pk=scan.pk).update(auswertung=a)
    dateien = originale(scan)
    transaction.on_commit(lambda: [d.unlink(missing_ok=True) for d in dateien], robust=True)


def bereinigen() -> dict:
    """Abgelaufene Scans löschen, verwaiste Verzeichnisse und Reste entfernen. Läuft stündlich im OCR-Dienst und
    höchstens einmal je Stunde beim Öffnen der Liste."""
    e = Einstellungen.aktuell()
    jetzt = timezone.now()
    ergebnis = {"abgelaufen": 0, "verwaist": 0, "reste": 0}
    abgelaufen = Scan.objects.filter(laeuft_ab_am__lte=jetzt).exclude(status=Scan.Status.LAEUFT)
    for pk in list(abgelaufen.values_list("pk", flat=True)):
        with transaction.atomic():
            ergebnis["abgelaufen"] += entfernen_wenn_ruhend(pk)
    if ergebnis["abgelaufen"]:
        protokolliere(A.SCAN, objekt="Scans", aktion="abgelaufen", anzahl=ergebnis["abgelaufen"],
                      tage=e.scans_frist_tage)
    basis = settings.EPM_SCANS
    if basis.is_dir():
        bekannt = set(Scan.objects.values_list("ordner", flat=True))
        grenze = time.time() - 24 * 3600
        for eintrag in basis.iterdir():
            if eintrag.name.startswith("."):
                continue  # .dienst (Stand des OCR-Dienstes)
            try:
                alt = eintrag.stat().st_mtime < grenze
            except OSError:
                continue
            if eintrag.is_dir() and eintrag.name not in bekannt and alt:
                shutil.rmtree(eintrag, ignore_errors=True)
                ergebnis["verwaist"] += 1
            elif eintrag.is_file() and alt:
                eintrag.unlink(missing_ok=True)
                ergebnis["reste"] += 1
        for ordner in bekannt:
            for rest in (basis / ordner).glob(".neu-*"):
                try:
                    if rest.stat().st_mtime < grenze:
                        rest.unlink(missing_ok=True)
                        ergebnis["reste"] += 1
                except OSError:
                    pass
        # Nach einer Wiederherstellung: Scans aus der Datenbank, deren Dateien nicht gesichert werden (Absicht)
        for scan in Scan.objects.exclude(status=Scan.Status.LAEUFT).filter(hochgeladen_am__lt=jetzt - timedelta(hours=1)):
            if not scan.pfad.is_dir():
                with transaction.atomic():
                    if entfernen_wenn_ruhend(scan.pk):
                        ergebnis["ohne_dateien"] = ergebnis.get("ohne_dateien", 0) + 1
    ergebnis["abgebrochen"] = haengende_zuruecksetzen()
    from . import dokumente

    ergebnis["auftraege"] = dokumente.bereinigen()
    return ergebnis


def haengende_zuruecksetzen() -> int:
    """Aufträge ohne Lebenszeichen (der OCR-Dienst wurde beendet) zurück in die Warteschlange – nach zu vielen
    Abbrüchen ohne Fortschritt als Fehler. Läuft bei jedem Durchlauf des Dienstes (eine Abfrage)."""
    anzahl = 0
    for scan in Scan.objects.filter(status=Scan.Status.LAEUFT, lebenszeichen__lt=timezone.now() - HAENGT_NACH):
        anzahl += 1
        if scan.versuche >= MAX_VERSUCHE:
            Scan.objects.filter(pk=scan.pk).update(
                status=Scan.Status.FEHLER, schritt="",
                fehler="Die Erkennung wurde mehrfach abgebrochen (der Erkennungsdienst wurde beendet, vermutlich an "
                       "seiner Speichergrenze). „Erneut erkennen“ versucht es noch einmal.")
        else:
            Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.WARTET,
                                                   schritt="nach einem Abbruch erneut in der Warteschlange")
    from . import dokumente

    return anzahl + dokumente.haengende_zuruecksetzen(HAENGT_NACH)


def geplant_beendet(scan: Scan):
    """Der Dienst wird regulär beendet (Update, Neustart): Scan zurück in die Warteschlange, ohne dass es als Abbruch
    zählt (die Seite wird beim nächsten Mal normal erkannt)."""
    from django.db.models import F
    from django.db.models.functions import Greatest

    ScanSeite.objects.filter(scan_id=scan.pk, begonnen_am__isnull=False).update(begonnen_am=None)
    Scan.objects.filter(pk=scan.pk, status=Scan.Status.LAEUFT).update(
        status=Scan.Status.WARTET, schritt="Erkennungsdienst neu gestartet – geht gleich weiter",
        versuche=Greatest(F("versuche") - 1, 0))


class herzschlag:
    """Solange der Block läuft, schreibt ein eigener Faden alle HERZSCHLAG_S Sekunden das Lebenszeichen des Scans
    (und ruft ``zusatz`` auf, z. B. um die Datei für den Healthcheck zu berühren)."""

    def __init__(self, scan, zusatz=None, takt: float = HERZSCHLAG_S):
        # Scan oder Auftrag „Text erkennen“ (beide mit status „laeuft“ und lebenszeichen)
        self.modell, self.scan_id, self.zusatz, self.takt = type(scan), scan.pk, zusatz, takt
        self._stopp = threading.Event()
        self._faden = threading.Thread(target=self._lauf, name="epm-ocr-herzschlag", daemon=True)

    def schlag(self):
        """Ein Lebenszeichen: Zeitpunkt am Scan, dazu ``zusatz`` (Healthcheck, Stand für die Systemseite)."""
        self.modell.objects.filter(pk=self.scan_id, status="laeuft").update(lebenszeichen=timezone.now())
        if self.zusatz:
            self.zusatz()

    def _lauf(self):
        from django.db import connection

        try:
            while not self._stopp.wait(self.takt):
                try:
                    self.schlag()
                except Exception:  # noqa: BLE001 – ein ausgefallener Herzschlag darf die Erkennung nicht stören
                    log.warning("Lebenszeichen nicht geschrieben", exc_info=True)
        finally:
            connection.close()

    def __enter__(self):
        self._faden.start()
        return self

    def __exit__(self, *_):
        self._stopp.set()
        self._faden.join(timeout=5)
        return False


_zuletzt_bereinigt = 0.0


def bereinigen_hoechstens_stuendlich():
    global _zuletzt_bereinigt
    if time.monotonic() - _zuletzt_bereinigt < 3600 and _zuletzt_bereinigt:
        return None
    _zuletzt_bereinigt = time.monotonic()
    try:
        return bereinigen()
    except Exception:  # noqa: BLE001 – Aufräumen darf nichts anderes verhindern
        log.exception("Bereinigung der Scans fehlgeschlagen")
        return None


# ---------------------------------------------------------------- Bilder speichern
def _bild_speichern(ziel: Path, bild: np.ndarray, art: str = "jpg", qualitaet: int = 88) -> tuple[int, int]:
    if art == "png":
        ok, kodiert = cv2.imencode(".png", bild, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    else:
        ok, kodiert = cv2.imencode(".jpg", bild, [cv2.IMWRITE_JPEG_QUALITY, qualitaet])
    if not ok:
        raise RuntimeError("Bild konnte nicht gespeichert werden")
    _schreiben(ziel, kodiert.tobytes())
    return bild.shape[1], bild.shape[0]


def _klein(bild: np.ndarray, lang: int = 360) -> np.ndarray:
    h, w = bild.shape[:2]
    f = min(1.0, lang / max(h, w))
    return cv2.resize(bild, (max(1, round(w * f)), max(1, round(h * f))), interpolation=cv2.INTER_AREA)


def lade_bild(pfad: Path, grau: bool = False) -> np.ndarray:
    a = cv2.imread(str(pfad), cv2.IMREAD_GRAYSCALE if grau else cv2.IMREAD_COLOR)
    if a is None:
        raise ScanFehler("Bilddatei der Seite fehlt oder ist beschädigt.")
    return a


def _ist_grau(bild: np.ndarray) -> bool:
    if bild.ndim == 2:
        return True
    klein = _klein(bild, 400).astype(np.int16)
    return float(np.abs(klein[..., 0] - klein[..., 1]).mean() + np.abs(klein[..., 1] - klein[..., 2]).mean()) < 4


# ---------------------------------------------------------------- Erkennung (nur im OCR-Dienst)
@transaction.atomic
def seiten_anlegen(scan: Scan) -> list[ScanSeite]:
    """Originale → Rohbilder der Seiten (einmalig je Scan). Alle oder keine: bricht eine Datei ab (beschädigt, Dienst
    beendet), entsteht keine Seite, und der nächste Versuch beginnt von vorn."""
    for rest in scan.pfad.glob("roh-*"):  # Bilder eines abgebrochenen Versuchs (ohne Seiten in der Datenbank)
        rest.unlink(missing_ok=True)
    seiten = []
    nr = 0
    for datei in originale(scan):
        try:
            _, rohseiten = laden.seiten_einzeln(datei.read_bytes(), max_seiten=settings.EPM_SCANS_MAX_SEITEN)
            for roh in rohseiten:  # eine Seite nach der anderen im Speicher
                nr += 1
                if nr > settings.EPM_SCANS_MAX_SEITEN:
                    raise ScanFehler(f"Mehr als {settings.EPM_SCANS_MAX_SEITEN} Seiten in einem Scan.")
                bild = roh.bild
                if roh.herkunft == "pdf":
                    if _ist_grau(bild):
                        bild = cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY)
                    name, art = f"roh-{secrets.token_hex(6)}.png", "png"
                else:
                    name, art = f"roh-{secrets.token_hex(6)}.jpg", "jpg"
                b, h = _bild_speichern(scan.pfad / name, bild, art, 93)
                seiten.append(ScanSeite.objects.create(
                    scan=scan, nr=nr, roh=name, roh_breite=b, roh_hoehe=h, herkunft=roh.herkunft,
                    kamera=bool(roh.exif), dpi=roh.dpi, textebene=roh.digital, auftrag={"art": "seite"}))
        except laden.Unlesbar as fehler:
            raise ScanFehler(str(fehler)) from fehler
    if not seiten:
        raise ScanFehler("Die Datei enthält keine Seite.")
    return seiten


def woerterliste_schreiben(ziel: Path):
    """Fachwörter (Vorlagen › Grenzwerte), Namen des Laborkatalogs und häufig bestätigte gelernte Bezeichnungen (F182)
    als Wörterliste für Tesseract."""
    from stammdaten.models import Laborparameter

    from . import lernen

    woerter = set()
    for w in (Einstellungen.aktuell().ocr_fachwoerter or "").splitlines():
        if w.strip():
            woerter.add(w.strip())
    for name, kurz in Laborparameter.objects.values_list("name", "kurzname"):
        for teil in f"{name} {kurz}".replace("(", " ").replace(")", " ").split():
            if len(teil) >= 3 and any(c.isalpha() for c in teil):
                woerter.add(teil)
    woerter |= lernen.woerter()
    ziel.write_text("\n".join(sorted(woerter)) + "\n", encoding="utf-8")


def _rohseite(seite: ScanSeite) -> laden.Rohseite:
    bild = lade_bild(seite.datei(seite.roh))
    return laden.Rohseite(bild=bild, herkunft=seite.herkunft, dpi=seite.dpi, digital=seite.textebene,
                          exif={"kamera": "ja"} if seite.kamera else {})


VORSCHAU_SEITE = 1400  # längere Seite des Rohbilds für die Vorschau (Pixel)


def vorschau(seite: ScanSeite, einstellungen: dict) -> tuple[bytes, str]:
    """Seite mit ``einstellungen`` aufbereiten wie vor der Erkennung – verkleinert, ohne Glätten (UVDoc läuft nur im
    OCR-Dienst) und mit der zuletzt erkannten Ausrichtung, wenn „automatisch“ (spart den Tesseract-Aufruf).
    → (Bild, MIME-Typ)."""
    from .ocr.aufbereitung import Einstellungen as SeitenEinstellungen, aufbereiten

    e = SeitenEinstellungen.aus_json(einstellungen)
    if e.drehung is None:
        e.drehung = int((seite.info or {}).get("drehung") or 0)
    bild = _klein(lade_bild(seite.datei(seite.roh)), VORSCHAU_SEITE)
    auf = aufbereiten(bild, e, herkunft=seite.herkunft, kamera=bool(seite.kamera), vorschau=True)
    sw = auf.bild.ndim == 2 and bool(np.isin(auf.bild[::7, ::7], (0, 255)).all())
    ok, daten = cv2.imencode(".png" if sw else ".jpg", auf.bild, [] if sw else [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        raise ScanFehler("Die Vorschau ließ sich nicht erstellen.")
    return daten.tobytes(), "image/png" if sw else "image/jpeg"


def seite_erkennen(seite: ScanSeite, paddle, woerterliste: str | None, *, stufe: int = 0, schritt=None):
    from .ocr import erkennung

    auftrag = seite.auftrag or {"art": "seite"}
    alt = [seite.bild, seite.grau, seite.klein]
    if auftrag.get("art") == "bereich" and seite.grau and seite.ergebnis:
        grau = lade_bild(seite.datei(seite.grau), grau=True)
        daten = erkennung.bereich_erkennen(grau, seite.ergebnis, auftrag.get("box") or [0, 0, 1, 1],
                                           staerke=int(auftrag.get("staerke") or 0), woerterliste=woerterliste,
                                           paddle=paddle)
        seite.ergebnis = daten
    else:
        textebene = (seite.einstellungen or {}).get("textebene", True) is not False
        auf, daten = erkennung.seite_erkennen(_rohseite(seite), seite.einstellungen, woerterliste=woerterliste,
                                              paddle=paddle, textebene=textebene, stufe=stufe, schritt=schritt)
        token = secrets.token_hex(6)
        sw = auf.bild.ndim == 2 and bool(np.isin(auf.bild[::7, ::7], (0, 255)).all())
        seite.bild = f"bild-{token}.{'png' if sw else 'jpg'}"
        seite.breite, seite.hoehe = _bild_speichern(seite.datei(seite.bild), auf.bild, "png" if sw else "jpg", 88)
        seite.grau = f"grau-{token}.jpg"
        _bild_speichern(seite.datei(seite.grau), auf.grau, "jpg", 92)
        seite.klein = f"klein-{token}.jpg"
        _bild_speichern(seite.datei(seite.klein), _klein(auf.bild), "jpg", 80)
        seite.info = auf.info
        seite.ergebnis = daten
        for name in alt:
            if name:
                seite.datei(name).unlink(missing_ok=True)
    k = fusion.kennzahlen(seite.ergebnis)
    seite.text = fusion.text_aus_json(seite.ergebnis)
    seite.sicherheit = k["sicherheit"]
    seite.unsicher = k["unsicher"]
    seite.status = ScanSeite.Status.FERTIG
    seite.fehler = ""
    seite.auftrag = None
    seite.erkannt_am = timezone.now()
    seite.begonnen_am = None
    seite.abbrueche = 0  # gelungen; die Stufe steht in info["sparstufe"], „Anpassen“ versucht es wieder normal
    seite.save()


def katalog() -> list[dict]:
    from stammdaten.models import Laborparameter

    return list(Laborparameter.objects.filter(aktiv=True).values("id", "name", "kurzname", "einheit", "gruppe",
                                                                 "suchbegriffe"))


def diagnoseliste() -> list[tuple[str, str]]:
    """Liste unter Vorlagen › Diagnosen: ICD-Code für Diagnosen, die im Brief ohne Code stehen."""
    from stammdaten.models import Diagnosevorlage

    return list(Diagnosevorlage.objects.filter(aktiv=True).values_list("icd_code", "bezeichnung"))


def auswerten(scan: Scan):
    """Gesamttext, Kennzahlen und Werte aus allen Seiten (auch nach jeder Änderung einer Seite)."""
    seiten = list(scan.seiten.order_by("nr", "id"))
    # je Seite ein Eintrag (auch für nicht erkannte), damit „seite“ in den Vorschlägen der Nummer der Seite entspricht
    ergebnisse = [s.ergebnis if s.status == ScanSeite.Status.FERTIG and s.ergebnis else {"reihen": []} for s in seiten]
    scan.text = "\n\n".join(s.text for s in seiten if s.text)
    gewicht = sum(max(1, len(s.text)) for s in seiten if s.sicherheit is not None)
    scan.sicherheit = (sum(s.sicherheit * max(1, len(s.text)) for s in seiten if s.sicherheit is not None) / gewicht
                       if gewicht else None)
    scan.unsicher = sum(s.unsicher for s in seiten)
    verfahren = []
    for e in ergebnisse:
        for v in e.get("verfahren", []):
            if v not in verfahren:
                verfahren.append(v)
    scan.verfahren = verfahren
    alt = scan.auswertung or {}
    originale_info = alt.get("originale", [])
    from . import lernen

    a = auswertung.auswerten(ergebnisse, katalog(), timezone.localdate(), lernen.gelerntes(), zusatz_reihen(seiten),
                             diagnoseliste())
    a["originale"] = originale_info
    _verworfen_uebernehmen(alt, a)
    scan.auswertung = a
    scan.dokumentdatum = a.get("datum") or None


def zusatz_reihen(seiten: list[ScanSeite]) -> list:
    """Aus markierten bzw. gelernten Bereichen nachgelesene Reihen (F189), je Seite in ``info["zusatz"]``."""
    aus = []
    for i, s in enumerate(seiten):
        if s.status != ScanSeite.Status.FERTIG:
            continue
        for z in (s.info or {}).get("zusatz") or []:
            if isinstance(z, dict) and z.get("reihen"):
                aus.append((i, z, z.get("box")))
    return aus


def _verworfen_uebernehmen(alt: dict, neu: dict):
    """„Falsch erkannt“ angemerkte Vorschläge bleiben verworfen, wenn der Scan neu ausgewertet wird."""
    labor = {(w.get("zeile"), w.get("erkannt_als")): w["verworfen"] for w in (alt.get("labor") or {}).get("werte") or []
             if w.get("verworfen")}
    for w in (neu.get("labor") or {}).get("werte") or []:
        if (w.get("zeile"), w.get("erkannt_als")) in labor:
            w["verworfen"] = labor[(w.get("zeile"), w.get("erkannt_als"))]
    bia = {k: v["verworfen"] for k, v in ((alt.get("bia") or {}).get("werte") or {}).items() if v.get("verworfen")}
    for k, v in ((neu.get("bia") or {}).get("werte") or {}).items():
        if k in bia:
            v["verworfen"] = bia[k]
    dg = {(d.get("icd_code"), d.get("erkannt_als")): d["verworfen"] for d in alt.get("diagnosen") or []
          if d.get("verworfen")}
    for d in neu.get("diagnosen") or []:
        if (d.get("icd_code"), d.get("erkannt_als")) in dg:
            d["verworfen"] = dg[(d.get("icd_code"), d.get("erkannt_als"))]


MAX_ZUSATZ_SEITE = 12


def _zusatz_merken(seite: ScanSeite, daten: dict, herkunft: str):
    info = dict(seite.info or {})
    liste = [z for z in info.get("zusatz") or [] if z.get("box") != daten["box"]]
    liste.append({**daten, "herkunft": herkunft})
    info["zusatz"] = liste[-MAX_ZUSATZ_SEITE:]
    seite.info = info
    ScanSeite.objects.filter(pk=seite.pk).update(info=info)


def bereich_lesen(scan: Scan, seite: ScanSeite, box) -> list[int]:
    """„Richtigen Bereich markieren“ (F189): nur diesen Bereich der Seite neu lesen (Tesseract, vergrößert) und die
    Zeilen darin als neue Laborwerte anbieten. Die bisherigen Vorschläge behalten ihre Nummern (die neuen kommen
    hinten dazu). → Nummern der neuen Vorschläge in ``auswertung.labor.werte``."""
    from . import lernen
    from .ocr import ausschnitt

    box = ausschnitt.pruefen(box)
    if seite.status != ScanSeite.Status.FERTIG or not seite.grau:
        raise ausschnitt.BereichFehler("Die Seite ist noch nicht erkannt.")
    grau = lade_bild(seite.datei(seite.grau), grau=True)
    with tempfile.TemporaryDirectory(prefix="epm-woerter-") as tmp:
        liste = Path(tmp) / "fachwoerter.txt"
        woerterliste_schreiben(liste)
        daten = ausschnitt.lesen(grau, box, str(liste))
    _zusatz_merken(seite, daten, "markiert")
    seiten = list(scan.seiten.order_by("nr", "id"))
    nr = next(i for i, s in enumerate(seiten) if s.pk == seite.pk)
    a = dict(scan.auswertung or {})
    labor = dict(a.get("labor") or {"name": "", "werte": []})
    werte = list(labor.get("werte") or [])
    quelle = auswertung.norm(labor.get("name") or "")[:150]
    reihen = auswertung.reihen_der_seite(daten, nr, box)
    neu = auswertung.laborwerte(reihen, katalog(), lernen.gelerntes(), quelle)
    if not neu:
        # keine Zeile sieht wie ein Laborwert aus: den gelesenen Text trotzdem anbieten (Freitext, nicht vorgewählt)
        for r in reihen:
            text = " ".join(t.text for t in r)
            neu.append({"parameter": None, "parameter_name": None, "erkannt_als": text[:150], "zuordnung": "frei",
                        "freitext_name": text[:150], "wert": None, "wert_text": "", "einheit": "", "einheit_gelesen": "",
                        "referenz_von": None, "referenz_bis": None, "markierung": "", "seite": nr,
                        "box": [round(min(t.box[0] for t in r), 4), round(min(t.box[1] for t in r), 4),
                                round(max(t.box[0] + t.box[2] for t in r) - min(t.box[0] for t in r), 4),
                                round(max(t.box[1] + t.box[3] for t in r) - min(t.box[1] for t in r), 4)],
                        "zeile": text[:200], "sicherheit": round(min(t.c for t in r), 3),
                        "hinweise": ["aus dem markierten Bereich gelesen – kein Wert erkannt"], "vorschlag": False,
                        "bereich": box})
    for w in neu:
        w["hinweise"] = ["aus dem markierten Bereich gelesen"] + list(w.get("hinweise") or [])
    start = len(werte)
    werte += neu
    labor["werte"] = werte
    a["labor"] = labor
    if neu and "labor" not in (a.get("arten") or []):
        a["arten"] = list(a.get("arten") or []) + ["labor"]
    scan.auswertung = a
    Scan.objects.filter(pk=scan.pk).update(auswertung=a)
    return list(range(start, len(werte)))


def bereiche_nachlesen(scan: Scan) -> int:
    """Im OCR-Dienst nach der Erkennung: gelernte Bereiche der Werte dieses Absenders (F189) gezielt nachlesen, damit
    die Auswertung dort sucht. → Zahl der gelesenen Bereiche. Fehler stören die Erkennung nicht."""
    from . import lernen
    from .ocr import ausschnitt, tesseract

    seiten = list(scan.seiten.order_by("nr", "id"))
    ergebnisse = [s.ergebnis if s.status == ScanSeite.Status.FERTIG and s.ergebnis else {"reihen": []} for s in seiten]
    quelle = auswertung.norm(auswertung.labor_name(auswertung.reihen_aus(ergebnisse)))[:150]
    bereiche = lernen.gelerntes().bereiche.get(quelle) if quelle else None
    if not bereiche or not tesseract.verfuegbar()[0]:
        return 0
    anzahl = 0
    with tempfile.TemporaryDirectory(prefix="epm-woerter-") as tmp:
        liste = Path(tmp) / "fachwoerter.txt"
        woerterliste_schreiben(liste)
        for s in seiten:
            if s.status != ScanSeite.Status.FERTIG or not s.grau:
                continue
            vorhanden = [z.get("box") for z in (s.info or {}).get("zusatz") or []]
            for box in bereiche:
                if box in vorhanden:
                    continue
                try:
                    daten = ausschnitt.lesen(lade_bild(s.datei(s.grau), grau=True), ausschnitt.pruefen(box), str(liste))
                except Exception:  # noqa: BLE001 – ein gelernter Bereich darf die Erkennung nicht stören
                    log.warning("Gelernten Bereich auf Seite %s von %s nicht gelesen", s.nr, scan, exc_info=True)
                    continue
                _zusatz_merken(s, daten, "gelernt")
                anzahl += 1
    return anzahl


def auftrag_holen() -> Scan | None:
    with transaction.atomic():
        scan = (Scan.objects.select_for_update(skip_locked=True)
                .filter(status=Scan.Status.WARTET).order_by("hochgeladen_am", "id").first())
        if scan is None:
            return None
        jetzt = timezone.now()
        scan.status = Scan.Status.LAEUFT
        scan.begonnen_am = jetzt
        scan.lebenszeichen = jetzt
        scan.versuche += 1
        scan.schritt = "wird vorbereitet"
        scan.fortschritt = 0
        scan.save(update_fields=["status", "begonnen_am", "lebenszeichen", "versuche", "schritt", "fortschritt"])
        return scan


def _fortschritt(scan: Scan, prozent: int, schritt: str):
    Scan.objects.filter(pk=scan.pk).update(fortschritt=max(0, min(100, prozent)), schritt=schritt[:120],
                                           lebenszeichen=timezone.now())


def bearbeiten(scan: Scan, paddle=None, abbrechen=lambda: False) -> Scan:
    """Einen Auftrag abarbeiten: Seiten anlegen (beim ersten Mal), wartende Seiten erkennen, auswerten."""
    t0 = time.monotonic()
    try:
        if not scan.seiten.exists():
            _fortschritt(scan, 2, "Seiten werden geladen")
            seiten_anlegen(scan)
        offen = list(scan.seiten.filter(Q(status=ScanSeite.Status.WARTET) | Q(auftrag__isnull=False))
                     .order_by("nr", "id"))
        with tempfile.TemporaryDirectory(prefix="epm-woerter-") as tmp:
            liste = Path(tmp) / "fachwoerter.txt"
            woerterliste_schreiben(liste)
            for i, seite in enumerate(offen):
                if abbrechen():
                    Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.WARTET, schritt="unterbrochen")
                    ScanSeite.objects.filter(pk=seite.pk).update(begonnen_am=None)
                    return scan
                prozent = 5 + int(90 * i / max(len(offen), 1))
                kopf = f"Seite {i + 1} von {len(offen)}"
                # Stand der Vorversuche: war die Seite schon begonnen, wurde der Dienst dabei beendet
                if seite.begonnen_am is not None:
                    seite.abbrueche += 1
                    log.warning("%s von %s: voriger Versuch abgebrochen (%s. Mal)", kopf, scan, seite.abbrueche)
                if seite.abbrueche >= MAX_ABBRUECHE_SEITE:
                    ScanSeite.objects.filter(pk=seite.pk).update(
                        status=ScanSeite.Status.FEHLER, auftrag=None, begonnen_am=None, abbrueche=seite.abbrueche,
                        fehler=f"Die Erkennung dieser Seite wurde {seite.abbrueche}-mal abgebrochen (vermutlich an der "
                               "Speichergrenze des Erkennungsdienstes). Bitte die Seite anpassen (z. B. Ecken enger "
                               "setzen) oder kleiner einscannen.")
                    Scan.objects.filter(pk=scan.pk).update(versuche=0)
                    continue
                ScanSeite.objects.filter(pk=seite.pk).update(begonnen_am=timezone.now(), abbrueche=seite.abbrueche)
                _fortschritt(scan, prozent, f"{kopf} wird erkannt")
                try:
                    seite_erkennen(seite, paddle, str(liste), stufe=seite.abbrueche,
                                   schritt=lambda t, p=prozent, k=kopf: _fortschritt(scan, p, f"{k}: {t}"))
                except ScanFehler:
                    ScanSeite.objects.filter(pk=seite.pk).update(begonnen_am=None)
                    raise
                except Exception as fehler:  # noqa: BLE001 – eine Seite darf die anderen nicht aufhalten
                    log.exception("Seite %s von %s nicht erkannt", seite.nr, scan)
                    ScanSeite.objects.filter(pk=seite.pk).update(status=ScanSeite.Status.FEHLER, auftrag=None,
                                                                 begonnen_am=None, fehler=str(fehler)[:500])
                # Fortschritt: Abbrüche davor zählen nicht mehr gegen den Scan
                Scan.objects.filter(pk=scan.pk).update(versuche=0)
                gc.collect()  # große Bilder der Seite sofort freigeben
        scan.refresh_from_db()
        bereiche_nachlesen(scan)
        auswerten(scan)
        # nur die Felder der Erkennung: Titel und Ablauf ändert die Oberfläche währenddessen; ein inzwischen
        # gelöschter Scan wird nicht wieder angelegt
        Scan.objects.filter(pk=scan.pk).update(
            text=scan.text, sicherheit=scan.sicherheit, unsicher=scan.unsicher, verfahren=scan.verfahren,
            auswertung=scan.auswertung, dokumentdatum=scan.dokumentdatum, status=Scan.Status.FERTIG, fortschritt=100,
            schritt="", fehler="", erkannt_am=timezone.now(), dauer_s=round(time.monotonic() - t0, 1), versuche=0)
    except Scan.DoesNotExist:
        log.info("%s wurde während der Erkennung gelöscht", scan)
        return scan
    except ScanFehler as fehler:
        Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.FEHLER, fehler=str(fehler)[:1000], schritt="")
    except Exception as fehler:  # noqa: BLE001
        log.exception("Erkennung von %s fehlgeschlagen", scan)
        Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.FEHLER, schritt="",
                                               fehler=f"Die Erkennung ist fehlgeschlagen: {str(fehler)[:500]}")
    belegung_aktualisieren(scan)
    try:
        scan.refresh_from_db()
    except Scan.DoesNotExist:
        log.info("%s wurde während der Erkennung gelöscht", scan)
    return scan


# ---------------------------------------------------------------- Patient finden und prüfen
def _aehnlicher_name(teil: str, kandidaten: set[str]) -> str | None:
    """Ein Wort aus ``kandidaten``, das ``teil`` mit wenigen Lesefehlern entspricht (1 Fehler ab 4, 2 ab 8 Zeichen)."""
    if len(teil) < 4:
        return None
    grenze = 1 if len(teil) < 8 else 2
    beste = None
    for k in kandidaten:
        if k == teil:
            return k
        a = auswertung.abstand(teil, k)
        if 0 < a <= grenze and (beste is None or a < beste[0]):
            beste = (a, k)
    return beste[1] if beste else None


def patient_vorschlaege(scan: Scan, user, anzahl: int = 3) -> list[dict]:
    """Patienten, auf die das Dokument hinweist (F183): Name (auch mit Lesefehlern), Geburtsdatum (exakt, starkes
    Merkmal), Nummer. Nur Akten, die diese Person sehen darf. Zugeordnet wird nie automatisch – bestätigen muss immer
    ein Mensch.

    Stufe je Vorschlag: „sicher“ (Name und Geburtsdatum), „wahrscheinlich“ (genug Merkmale), „unsicher“ (nur ein
    schwaches Merkmal – die Oberfläche zeigt dann nur einen Hinweis). Passt das Geburtsdatum im Dokument nicht zur Akte,
    sinkt die Stufe (zwei Personen gleichen Namens)."""
    from epm.api_basis import patienten_fuer

    h = (scan.auswertung or {}).get("patient") or {}
    nummern = set(h.get("nummern") or [])
    geburt = set(h.get("geburtsdaten") or [])
    woerter = set(h.get("woerter") or [])
    namen = set(h.get("namen") or [])
    if not (nummern or geburt or woerter or namen):
        return []
    qs = patienten_fuer(user)
    if scan.ist_test:
        qs = qs.filter(ist_test=True)
    kandidaten = []
    for p in qs.only("id", "nummer", "nachname", "vorname", "geburtsdatum", "ist_test", "abgeschlossen_am").iterator():
        punkte, gruende = 0.0, []
        name_ok = name_aehnlich = False
        nach = auswertung.norm(p.nachname).split()
        vor = auswertung.norm(p.vorname).split()[:1]
        if nach and all(t in woerter or t in namen for t in nach):
            punkte += 2
            name_ok = True
        elif nach and namen:
            gelesen = [_aehnlicher_name(t, namen) for t in nach]
            if all(gelesen):
                punkte += 1.5
                name_aehnlich = True
                gruende.append(f"Name ähnlich gelesen („{' '.join(gelesen)}“)")
        vorname = False
        if vor and (vor[0] in woerter or vor[0] in namen):
            punkte += 2 if (name_ok or name_aehnlich) else 1
            vorname = True
        elif vor and namen and _aehnlicher_name(vor[0], namen):
            punkte += 1
            vorname = True
        geb_ok = bool(p.geburtsdatum and p.geburtsdatum.isoformat() in geburt)
        geb_falsch = bool(geburt and p.geburtsdatum and not geb_ok)
        if geb_ok:
            punkte += 3
        elif geb_falsch:
            punkte -= 2
        nummer_ok = p.nummer in nummern
        if nummer_ok:
            punkte += 3
        if punkte < 2:
            continue
        if (name_ok or name_aehnlich) and geb_ok:
            stufe = "sicher"
            gruende.insert(0, "Name und Geburtsdatum erkannt" if name_ok else "Geburtsdatum erkannt")
        elif punkte >= 4 and not geb_falsch:
            stufe = "wahrscheinlich"
        else:
            stufe = "unsicher"
        if not gruende or gruende[0] not in ("Name und Geburtsdatum erkannt", "Geburtsdatum erkannt"):
            teile = []
            if name_ok:
                teile.append("Name" if vorname else "Nachname")
            elif vorname and not name_aehnlich:
                teile.append("Vorname")
            if geb_ok:
                teile.append("Geburtsdatum")
            if teile:
                gruende.insert(0, " und ".join(teile) + " erkannt")
        if nummer_ok:
            gruende.append(f"Nr. {p.nummer}")
        if geb_falsch:
            gruende.append("Geburtsdatum im Dokument passt nicht")
        kandidaten.append({"id": p.id, "nummer": p.nummer, "name": f"{p.nachname}, {p.vorname}",
                           "nachname": p.nachname, "vorname": p.vorname,
                           "geburtsdatum": p.geburtsdatum, "ist_test": p.ist_test,
                           "abgeschlossen": p.abgeschlossen_am is not None, "punkte": punkte, "stufe": stufe,
                           "grund": ", ".join(gruende)})
    rang = {"sicher": 0, "wahrscheinlich": 1, "unsicher": 2}
    kandidaten.sort(key=lambda k: (rang[k["stufe"]], -k["punkte"], k["name"]))
    return kandidaten[:anzahl]


def zuordnung_pruefen(scan: Scan, patient) -> list[str]:
    """Hinweise, wenn das Dokument nicht zum gewählten Patienten zu passen scheint (falsch abgelegt?)."""
    h = (scan.auswertung or {}).get("patient") or {}
    hinweise = []
    geburt = set(h.get("geburtsdaten") or [])
    if geburt and patient.geburtsdatum and patient.geburtsdatum.isoformat() not in geburt:
        daten = ", ".join(sorted(f"{d[8:10]}.{d[5:7]}.{d[0:4]}" for d in geburt))
        hinweise.append(f"Im Dokument steht als Geburtsdatum {daten} – {patient.nachname}, {patient.vorname} ist am "
                        f"{patient.geburtsdatum:%d.%m.%Y} geboren.")
    woerter = set(h.get("woerter") or [])
    nach = auswertung.norm(patient.nachname).split()
    if len(woerter) >= 25 and nach and not all(t in woerter for t in nach):
        hinweise.append(f"Der Name „{patient.nachname}“ kommt im erkannten Text nicht vor.")
    # Nummern im Dokument sind meist die des Labors oder der Klinik – kein Hinweis auf eine falsche Akte
    return hinweise
