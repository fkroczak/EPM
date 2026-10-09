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


def bereinigen() -> dict:
    """Abgelaufene Scans löschen, verwaiste Verzeichnisse und Reste entfernen. Läuft stündlich im OCR-Dienst und
    höchstens einmal je Stunde beim Öffnen der Liste."""
    e = Einstellungen.aktuell()
    jetzt = timezone.now()
    ergebnis = {"abgelaufen": 0, "verwaist": 0, "reste": 0}
    abgelaufen = list(Scan.objects.filter(laeuft_ab_am__lte=jetzt).exclude(status=Scan.Status.LAEUFT))
    for scan in abgelaufen:
        with transaction.atomic():
            entfernen(scan)
    ergebnis["abgelaufen"] = len(abgelaufen)
    if abgelaufen:
        protokolliere(A.SCAN, objekt="Scans", aktion="abgelaufen", anzahl=len(abgelaufen), tage=e.scans_frist_tage)
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
                    entfernen(scan)
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
def seiten_anlegen(scan: Scan) -> list[ScanSeite]:
    """Originale → Rohbilder der Seiten (einmalig je Scan)."""
    seiten = []
    nr = 0
    for datei in originale(scan):
        try:
            _, rohseiten = laden.seiten_laden(datei.read_bytes(), max_seiten=settings.EPM_SCANS_MAX_SEITEN)
        except laden.Unlesbar as fehler:
            raise ScanFehler(str(fehler)) from fehler
        for roh in rohseiten:
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
    if not seiten:
        raise ScanFehler("Die Datei enthält keine Seite.")
    return seiten


def woerterliste_schreiben(ziel: Path):
    """Fachwörter (Vorlagen › Grenzwerte) und Namen des Laborkatalogs als Wörterliste für Tesseract."""
    from stammdaten.models import Laborparameter

    woerter = set()
    for w in (Einstellungen.aktuell().ocr_fachwoerter or "").splitlines():
        if w.strip():
            woerter.add(w.strip())
    for name, kurz in Laborparameter.objects.values_list("name", "kurzname"):
        for teil in f"{name} {kurz}".replace("(", " ").replace(")", " ").split():
            if len(teil) >= 3 and any(c.isalpha() for c in teil):
                woerter.add(teil)
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
    originale_info = (scan.auswertung or {}).get("originale", [])
    a = auswertung.auswerten(ergebnisse, katalog(), timezone.localdate())
    a["originale"] = originale_info
    scan.auswertung = a
    scan.dokumentdatum = a.get("datum") or None


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
        auswerten(scan)
        scan.status = Scan.Status.FERTIG
        scan.fortschritt = 100
        scan.schritt = ""
        scan.fehler = ""
        scan.erkannt_am = timezone.now()
        scan.dauer_s = round(time.monotonic() - t0, 1)
        scan.versuche = 0
        scan.save()
    except ScanFehler as fehler:
        Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.FEHLER, fehler=str(fehler)[:1000], schritt="")
    except Exception as fehler:  # noqa: BLE001
        log.exception("Erkennung von %s fehlgeschlagen", scan)
        Scan.objects.filter(pk=scan.pk).update(status=Scan.Status.FEHLER, schritt="",
                                               fehler=f"Die Erkennung ist fehlgeschlagen: {str(fehler)[:500]}")
    belegung_aktualisieren(scan)
    scan.refresh_from_db()
    return scan


# ---------------------------------------------------------------- Patient finden und prüfen
def patient_vorschlaege(scan: Scan, user, anzahl: int = 3) -> list[dict]:
    """Patienten, auf die das Dokument hinweist (Nummer, Geburtsdatum, Name). Bestätigen muss immer ein Mensch."""
    from epm.api_basis import patienten_fuer

    h = (scan.auswertung or {}).get("patient") or {}
    nummern = set(h.get("nummern") or [])
    geburt = set(h.get("geburtsdaten") or [])
    woerter = set(h.get("woerter") or [])
    if not (nummern or geburt or woerter):
        return []
    qs = patienten_fuer(user)
    if scan.ist_test:
        qs = qs.filter(ist_test=True)
    kandidaten = []
    for p in qs.only("id", "nummer", "nachname", "vorname", "geburtsdatum", "ist_test", "abgeschlossen_am").iterator():
        punkte, gruende = 0, []
        if p.nummer in nummern:
            punkte += 3
            gruende.append(f"Nr. {p.nummer}")
        if p.geburtsdatum and p.geburtsdatum.isoformat() in geburt:
            punkte += 3
            gruende.append("Geburtsdatum")
        nach = auswertung.norm(p.nachname).split()
        if nach and all(t in woerter for t in nach):
            punkte += 2
            gruende.append("Nachname")
        vor = auswertung.norm(p.vorname).split()[:1]
        if vor and vor[0] in woerter:
            punkte += 2 if nach and all(t in woerter for t in nach) else 1
            gruende.append("Vorname")
        if punkte >= 4:
            kandidaten.append({"id": p.id, "nummer": p.nummer, "name": f"{p.nachname}, {p.vorname}",
                               "geburtsdatum": p.geburtsdatum, "ist_test": p.ist_test,
                               "abgeschlossen": p.abgeschlossen_am is not None, "punkte": punkte,
                               "grund": ", ".join(gruende)})
    kandidaten.sort(key=lambda k: (-k["punkte"], k["name"]))
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
