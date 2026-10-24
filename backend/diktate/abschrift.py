"""Abschrift eines Diktats: Aufnahme laden, mit whisper.cpp abschreiben (nur CPU, offline), Text aufbereiten.

Läuft ausschließlich im OCR-Dienst (``manage.py epm_ocr``). Das Modell wird erst beim ersten Diktat geladen und nach
``LEERLAUF_S`` ohne Diktat wieder freigegeben – tagsüber ohne Diktat belegt es keinen Speicher.

Das Modell (``ggml-large-v3-turbo-q5_0.bin``, ≈ 550 MB, MIT-Lizenz) steht in ``scans/modelle/modelle.json`` und
kommt wie die OCR-Modelle beim Bau ins Image oder offline mit ``werkzeuge/ocr-modelle.sh``.
"""
from __future__ import annotations

import html
import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger("epm.diktate")

MODELL_DATEI = "diktat/ggml-large-v3-turbo-q5_0.bin"
MODELL_NAME = "whisper large-v3-turbo (q5_0)"
LEERLAUF_S = 300
ABTASTRATE = 16_000
# Unter dieser Sicherheit (0–1, Wahrscheinlichkeit des unsichersten Teilworts) wird ein Wort markiert
UNSICHER_UNTER = 0.5
# Länge der Vorlage (Fachbegriffe) in Zeichen – whisper nimmt höchstens etwa 220 Tokens
VORLAGE_MAX = 700


class AbschriftFehler(RuntimeError):
    """Verständliche Meldung für die Oberfläche."""


def modell_pfad() -> Path:
    eigen = os.environ.get("EPM_DIKTAT_MODELL")
    if eigen:
        return Path(eigen)
    return Path(os.environ.get("EPM_OCR_MODELLE") or "/opt/ocr-modelle") / MODELL_DATEI


# Speicher, den der OCR-Dienst mindestens haben muss (Texterkennung + Sprachmodell ≈ 1 GB): EPM_OCR_SPEICHER ≥ 3g
MIN_SPEICHER = int(2.5 * 1024 ** 3)


def speichergrenze() -> int | None:
    """Grenze des Containers (cgroup v2) in Bytes, None ohne Grenze."""
    try:
        wert = Path("/sys/fs/cgroup/memory.max").read_text().strip()
    except OSError:
        return None
    return int(wert) if wert.isdigit() else None


def bereitschaft() -> tuple[bool, str]:
    """(bereit, Grund) – für den Stand des OCR-Dienstes und die Oberfläche."""
    try:
        import _pywhispercpp  # noqa: F401
    except ImportError:
        return False, "whisper.cpp fehlt im Image."
    if not modell_pfad().is_file():
        return False, ("Das Sprachmodell fehlt (mit „EPM aktualisieren“ bzw. den offline vorbereiteten OCR-Modellen "
                       "einspielen).")
    grenze = speichergrenze()
    if grenze is not None and grenze < MIN_SPEICHER:
        return False, (f"Der Erkennungsdienst hat nur {grenze / 1024 ** 3:.1f} GB Speicher; für Diktate mindestens "
                       "3 GB (EPM_OCR_SPEICHER=3g in /srv/epm/.env, Server mit mindestens 6 GB RAM).")
    return True, ""


def modell_bereit() -> bool:
    return bereitschaft()[0]


def threads() -> int:
    return max(1, int(os.environ.get("EPM_DIKTAT_THREADS") or os.environ.get("EPM_OCR_THREADS") or "2"))


# ---------------------------------------------------------------- Aufnahme laden
def audio_laden(pfad: Path):
    """Aufnahme (WebM/Opus, MP4/AAC vom iPhone, WAV, …) → Mono, 16 kHz, float32 (numpy)."""
    import av
    import numpy as np

    try:
        with av.open(str(pfad)) as quelle:
            if not quelle.streams.audio:
                raise AbschriftFehler("Die Aufnahme enthält keinen Ton.")
            wandler = av.AudioResampler(format="s16", layout="mono", rate=ABTASTRATE)
            teile = []
            for frame in quelle.decode(audio=0):
                for neu in wandler.resample(frame):
                    teile.append(neu.to_ndarray().reshape(-1))
            for neu in wandler.resample(None):
                teile.append(neu.to_ndarray().reshape(-1))
    except AbschriftFehler:
        raise
    except Exception as e:  # noqa: BLE001 – kaputte oder unbekannte Datei
        raise AbschriftFehler("Die Aufnahme ließ sich nicht lesen (Format nicht erkannt oder Datei beschädigt).") from e
    if not teile:
        raise AbschriftFehler("Die Aufnahme ist leer.")
    return np.concatenate(teile).astype(np.float32) / 32768.0


# ---------------------------------------------------------------- Modell
class Abschreiber:
    """Hält das Modell, solange Diktate kommen; ``freigeben_wenn_ruhig`` gibt den Speicher nach Leerlauf frei."""

    def __init__(self):
        self._modell = None
        self._zuletzt = 0.0

    def _laden(self):
        if self._modell is None:
            pfad = modell_pfad()
            if not pfad.is_file():
                raise AbschriftFehler("Das Sprachmodell für Diktate fehlt auf dem Server (Administration › System › "
                                      "Software: OCR-Modelle einspielen).")
            from pywhispercpp.model import Model

            log.info("Sprachmodell wird geladen: %s", pfad)
            self._modell = Model(str(pfad), n_threads=threads(), redirect_whispercpp_logs_to=None,
                                 print_progress=False, print_realtime=False, print_timestamps=False)
        self._zuletzt = time.monotonic()
        return self._modell

    def freigeben_wenn_ruhig(self):
        if self._modell is not None and time.monotonic() - self._zuletzt > LEERLAUF_S:
            log.info("Sprachmodell freigegeben (keine Diktate)")
            self._modell = None
            import gc

            gc.collect()

    def abschreiben(self, audio, vorlage: str = "", abbrechen=lambda: False, fortschritt=None) -> list[list]:
        """→ Wörter ``[[Wort, von_ms, bis_ms, Sicherheit], …]`` (Wort mit führendem Leerzeichen wie im Modell).
        ``fortschritt(anteil)`` kommt nach jedem fertigen Abschnitt (etwa alle 30 s Aufnahme) – im selben Faden, also
        auch dann, wenn whisper.cpp Python während der Rechnung blockiert (Lebenszeichen für den Healthcheck)."""
        modell = self._laden()
        dauer_ms = max(1.0, len(audio) / ABTASTRATE * 1000)

        def abschnitt(seg):
            if fortschritt is not None:
                fortschritt(min(1.0, seg.t1 * 10 / dauer_ms))

        modell.transcribe(audio, language="de", initial_prompt=vorlage or None, token_timestamps=True,
                          n_threads=threads(), abort_callback=lambda: bool(abbrechen()), suppress_blank=True,
                          no_context=False, new_segment_callback=abschnitt)
        self._zuletzt = time.monotonic()
        return woerter_aus_kontext(modell._ctx)


def woerter_aus_kontext(ctx) -> list[list]:
    """Teilwörter (Tokens) des letzten Durchlaufs zu Wörtern zusammensetzen: Ein Token mit führendem Leerzeichen
    beginnt ein neues Wort. Sicherheit eines Worts = die des unsichersten Teilworts; Zeiten in Millisekunden."""
    import _pywhispercpp as pw

    eot = pw.whisper_token_eot(ctx)
    woerter: list[list] = []
    roh = b""
    von = bis = 0
    p_min = 1.0

    def abschliessen():
        nonlocal roh
        if roh.strip():
            woerter.append([roh.decode("utf-8", errors="replace"), von, bis, round(p_min, 3)])
        roh = b""

    for i in range(pw.whisper_full_n_segments(ctx)):
        for j in range(pw.whisper_full_n_tokens(ctx, i)):
            daten = pw.whisper_full_get_token_data(ctx, i, j)
            if daten.id >= eot:  # Sondertokens (Zeitmarken, Sprache, Ende)
                continue
            teil = pw.whisper_token_to_bytes(ctx, daten.id)
            if isinstance(teil, str):
                teil = teil.encode("utf-8")
            if teil.startswith(b" ") or not roh:
                abschliessen()
                von, p_min = max(0, int(daten.t0) * 10), 1.0
            roh += teil
            bis = max(von, int(daten.t1) * 10)
            p_min = min(p_min, float(daten.p))
        abschliessen()  # ein Abschnitt endet immer mit einem ganzen Wort
    return woerter


# ---------------------------------------------------------------- Text aufbereiten
# Ansagen beim Diktieren → Zeichen. Bewusst ohne „Punkt“ und „Komma“: whisper setzt Satzzeichen selbst, und „Punkt“
# ist auch ein gewöhnliches Wort („ein wichtiger Punkt“).
_ABSATZ = re.compile(r"[\s,.;:]*\b(?:neuer|nächster|neue[rn]?)\s+(?:Absatz|Abschnitt)\b[\s,.;:!]*", re.I)
_ZEILE = re.compile(r"[\s,.;:]*\b(?:neue|nächste)\s+Zeile\b[\s,.;:!]*", re.I)
# nur Leerzeichen innerhalb der Zeile: Absätze und Zeilen (schon als \n gesetzt) bleiben stehen
_ERSATZ = [
    (re.compile(r"[ \t]*\bDoppelpunkt\b[ \t,.]*", re.I), ": "),
    (re.compile(r"[ \t]*\bKlammer[ \t]+auf\b[ \t,.]*", re.I), " ("),
    (re.compile(r"[ \t,.]*\bKlammer[ \t]+zu\b", re.I), ")"),
    (re.compile(r"[ \t]*\bSchrägstrich\b[ \t]*", re.I), "/"),
    (re.compile(r"[ \t]*\bFragezeichen\b", re.I), "?"),
    (re.compile(r"[ \t]*\bAusrufezeichen\b", re.I), "!"),
]
_SATZANFANG = re.compile(r"(^|[.!?]\s+)([a-zäöü])")


def klartext(woerter: list[list]) -> str:
    return "".join(w[0] for w in woerter).strip()


def _satz(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?)])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    return _SATZANFANG.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def als_html(text: str) -> str:
    """Abschrift → HTML für den Editor: Absätze und Zeilen aus den Ansagen, Satzzeichen, Großschreibung am Satzanfang."""
    text = _ABSATZ.sub("\n\n", text)
    text = _ZEILE.sub("\n", text)
    for muster, zeichen in _ERSATZ:
        text = muster.sub(zeichen, text)
    absaetze = []
    for absatz in re.split(r"\n{2,}", text):
        zeilen = [_satz(z) for z in absatz.split("\n")]
        zeilen = [z for z in zeilen if z]
        if zeilen:
            absaetze.append("<p>" + "<br>".join(html.escape(z, quote=False) for z in zeilen) + "</p>")
    return "".join(absaetze)


def unsichere(woerter: list[list]) -> int:
    return sum(1 for w in woerter if len(w) > 3 and w[3] < UNSICHER_UNTER)


def vorlage(patient=None, eigene: str = "", zweck: str = "bericht") -> str:
    """Kurzer Text, den whisper als „schon gesagt“ bekommt: Er gibt Schreibweise und Fachsprache vor (eigene Begriffe,
    Name, Diagnosen und Präparate der Akte). Gekürzt auf ``VORLAGE_MAX`` Zeichen, eigene Begriffe zuerst."""
    from stammdaten.models import Praeparat

    teile: list[str] = []

    def dazu(text):
        text = (text or "").strip()
        if text and text.lower() not in {t.lower() for t in teile}:
            teile.append(text)

    for b in re.split(r"[\n,;]+", eigene or ""):
        dazu(b)
    if patient is not None:
        dazu(f"{patient.vorname} {patient.nachname}")
        for d in patient.diagnosen.filter(aktiv=True).order_by("-id")[:12]:
            dazu(d.bezeichnung)
    for n in Praeparat.objects.filter(aktiv=True).order_by("kategorie", "reihenfolge").values_list("name", flat=True)[:40]:
        dazu(n)
    anfang = "Ärztliches Diktat, Ernährungsmedizin. " if zweck == "bericht" else "Kommentar zum Infusionsplan. "
    text = anfang + ", ".join(teile)
    if len(text) > VORLAGE_MAX:
        text = text[:VORLAGE_MAX].rsplit(",", 1)[0]
    return text + "."
