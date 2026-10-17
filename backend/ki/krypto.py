"""Arbeitsablage des KI-Dienstes: verschlüsselte Zwischendateien (Auftrag 8).

Was der KI-Dienst zwischen zwei Arbeitsschritten aufheben muss (Seitenbilder für die zweite Lesung, wenn das
Nachtfenster mitten in einem großen Dokument endet; Exporte für Evaluation und Training), liegt AES-256-GCM-
verschlüsselt unter ``EPM_KI``. Die Originale der Akte werden nie kopiert oder verändert.

Schlüssel: Docker-Secret ``EPM_KI_SCHLUESSEL_FILE`` (32 Bytes, roh, hex oder Base64). Ohne eigenes Secret wird er per
HKDF aus dem Django-Schlüssel abgeleitet – der liegt ebenfalls als Secret außerhalb der Ablage, nie neben den Dateien.
Zwischendateien werden nach Abschluss des Vorgangs bzw. spätestens nach ``aufbewahrung_tage`` gelöscht.
"""
import base64
import binascii
import os
import shutil
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

KENNUNG = b"EPMKI1"
# Der Container ki-worker bekommt statt des Django-Schlüssels nur diesen Platzhalter (rollout/projekt/compose.ki.yaml)
PLATZHALTER_SECRET_KEY = "ki-dienst-ohne-django-schluessel"
_schluessel_cache: dict[str, bytes] = {}


def _schluessel() -> bytes:
    pfad = settings.EPM_KI_SCHLUESSEL_FILE
    if pfad in _schluessel_cache:
        return _schluessel_cache[pfad]
    roh = b""
    if pfad:
        roh = Path(pfad).read_bytes().strip()
    if roh:
        if len(roh) == 32:
            s = roh
        else:
            try:
                s = binascii.unhexlify(roh) if len(roh) == 64 else base64.b64decode(roh, validate=True)
            except (binascii.Error, ValueError) as e:
                raise ValueError("EPM_KI_SCHLUESSEL_FILE: 32 Bytes roh, hex oder Base64 erwartet.") from e
        if len(s) != 32:
            raise ValueError("EPM_KI_SCHLUESSEL_FILE: der Schlüssel muss 32 Bytes lang sein.")
    else:
        if settings.SECRET_KEY == PLATZHALTER_SECRET_KEY:
            raise ValueError("EPM_KI_SCHLUESSEL_FILE fehlt oder ist leer (`epm-ki einrichten` legt es an).")
        s = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"epm-ki", info=b"arbeitsablage").derive(
            settings.SECRET_KEY.encode())
    _schluessel_cache[pfad] = s
    return s


def verschluesseln(daten: bytes, bezug: str = "") -> bytes:
    """``bezug`` (z. B. Vorgang und Seite) ist mitgeprüft: eine Datei lässt sich nicht unter falschem Namen lesen."""
    nonce = os.urandom(12)
    return KENNUNG + nonce + AESGCM(_schluessel()).encrypt(nonce, daten, bezug.encode())


def entschluesseln(blob: bytes, bezug: str = "") -> bytes:
    if not blob.startswith(KENNUNG):
        raise ValueError("Keine verschlüsselte Datei des KI-Dienstes.")
    nonce = blob[len(KENNUNG):len(KENNUNG) + 12]
    return AESGCM(_schluessel()).decrypt(nonce, blob[len(KENNUNG) + 12:], bezug.encode())


def ablage(*teile: str) -> Path:
    pfad = settings.EPM_KI.joinpath(*teile)
    pfad.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return pfad


def schreiben(pfad: Path, daten: bytes, bezug: str = ""):
    tmp = pfad.with_suffix(pfad.suffix + ".neu")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(verschluesseln(daten, bezug))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, pfad)


def lesen(pfad: Path, bezug: str = "") -> bytes:
    return entschluesseln(pfad.read_bytes(), bezug)


def vorgang_ordner(vorgang_id: int) -> Path:
    return settings.EPM_KI / "vorgaenge" / str(int(vorgang_id))


def vorgang_aufraeumen(vorgang_id: int):
    shutil.rmtree(vorgang_ordner(vorgang_id), ignore_errors=True)


def aufraeumen(tage: int, behalten: set[int] | None = None) -> int:
    """Zwischendateien älter als ``tage`` löschen (außer Vorgängen in ``behalten``); → Zahl gelöschter Ordner."""
    basis = settings.EPM_KI / "vorgaenge"
    if not basis.is_dir():
        return 0
    grenze = time.time() - tage * 86400
    geloescht = 0
    for ordner in basis.iterdir():
        if not ordner.name.isdigit() or (behalten and int(ordner.name) in behalten):
            continue
        try:
            if ordner.stat().st_mtime < grenze:
                shutil.rmtree(ordner, ignore_errors=True)
                geloescht += 1
        except OSError:
            continue
    return geloescht
