"""
Hochladen großer Dateien in Stücken (Fehlerliste 02.10.2026, 5.3 – zuerst für Sicherungen, seit 10.10.2026 auch für
Update-Pakete und OCR-Modelle, damit niemand mehr Dateien per scp auf den Server bringen muss).

Die Datei landet in ``EPM_SYSTEM/upload/<Kennung>.teil``, die Angaben (Art, Name, Größe, wer, wann) daneben in
``<Kennung>.json``. Erst ein Auftrag an den Systemagenten verarbeitet sie; er kopiert sie dafür in einen Ordner, den das
Backend nicht beschreiben kann, und entfernt beide Dateien. Liegen gebliebene Uploads räumt der Agent nach 24 Stunden
weg. Uploads ohne „art“ stammen aus der Zeit vor dem 10.10.2026 und sind Sicherungen.
"""
import json
import os
import re
import uuid

from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import BaseParser
from rest_framework.response import Response

from audit.models import SystemEreignis, protokolliere

from . import host

ID_MUSTER = re.compile(r"^[0-9a-f]{32}$")
TEIL = 4 * 1024 * 1024                     # Bytes je Anfrage (unter DATA_UPLOAD_MAX_MEMORY_SIZE)
STEUERZEICHEN = {chr(i) for i in range(32)} | {"\x7f"}
# Art -> Endung, größte Datei, Text für eine falsche Datei, Bezeichnung (Audit-Log)
ARTEN = {
    "sicherung": {"endung": ".tar", "max": 200 * 1024 ** 3, "name": "Sicherung",
                  "falsch": "Bitte die Datei wählen, die „Herunterladen“ geliefert hat (epm-sicherung_<Zeitpunkt>.tar)."},
    "paket": {"endung": ".tar", "max": 16 * 1024 ** 3, "name": "Update-Paket",
              "falsch": "Bitte das Update-Paket der Test-VM wählen (epm-paket-<Version>.tar)."},
    "ocr": {"endung": ".tar", "max": 4 * 1024 ** 3, "name": "OCR-Modelle",
            "falsch": "Bitte die vorbereitete Datei wählen (epm-ocr-modelle-<Revision>.tar)."},
}


class RohParser(BaseParser):
    """Ein Stück der hochgeladenen Datei, unverändert (höchstens ``TEIL`` Bytes je Anfrage)."""

    media_type = "application/octet-stream"

    def parse(self, stream, media_type=None, parser_context=None):
        return stream.read(TEIL + 1)


def art_von(meta: dict) -> str:
    return str(meta.get("art") or "sicherung")


def finde(kennung, arten):
    """(Pfad der Datei, Angaben) eines begonnenen Uploads einer der ``arten`` oder (None, None)."""
    if not ID_MUSTER.match(kennung or ""):
        return None, None
    ordner = host.ordner_upload()
    meta = host._lies(ordner / f"{kennung}.json")
    pfad = ordner / f"{kennung}.teil"
    if not isinstance(meta, dict) or art_von(meta) not in arten or not pfad.is_file() or pfad.is_symlink():
        return None, None
    return pfad, meta


def liste(arten) -> list:
    """Hochgeladene, noch nicht verarbeitete Dateien: [{upload, art, name, groesse, erhalten, vollstaendig, von, …}]"""
    ordner = host.ordner_upload()
    ergebnis = []
    try:
        namen = sorted(n for n in os.listdir(ordner) if n.endswith(".json"))
    except OSError:
        return ergebnis
    for n in namen:
        kennung = n[:-5]
        meta = host._lies(ordner / n)
        if not ID_MUSTER.match(kennung) or not isinstance(meta, dict) or art_von(meta) not in arten:
            continue
        try:
            erhalten = os.stat(ordner / f"{kennung}.teil").st_size
        except OSError:
            continue
        ergebnis.append({"upload": kennung, "art": art_von(meta), "name": str(meta.get("name") or ""),
                         "groesse": meta.get("groesse"), "erhalten": erhalten,
                         "vollstaendig": erhalten == meta.get("groesse"), "von": str(meta.get("von") or ""),
                         "begonnen_am": meta.get("begonnen_am")})
    return ergebnis


def beginnen(request, art: str, fehlt_text: str):
    """Upload anlegen: Name und Größe prüfen, Platz prüfen, leere Datei und Angaben schreiben, Audit-Log."""
    regel = ARTEN[art]
    ordner = host.ordner_upload()
    if not ordner.is_dir():
        return Response({"fehler": fehlt_text}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    name = os.path.basename(str(request.data.get("name") or "").replace("\\", "/"))[:200]
    groesse = request.data.get("groesse")
    if not name.lower().endswith(regel["endung"]) or any(z in STEUERZEICHEN for z in name):
        return Response({"name": regel["falsch"]}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(groesse, bool) or not isinstance(groesse, int) or not (0 < groesse <= regel["max"]):
        return Response({"groesse": "Die Datei ist leer oder zu groß."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        frei = os.statvfs(ordner)
        # Platz für die hochgeladene Datei und für die Kopie, die der Agent prüft bzw. auspackt
        if frei.f_bavail * frei.f_frsize < 2 * groesse + 64 * 1024 * 1024:
            return Response({"groesse": "Auf dem Server ist dafür zu wenig Speicher frei."},
                            status=status.HTTP_400_BAD_REQUEST)
    except OSError:
        pass
    kennung = uuid.uuid4().hex
    try:
        fd = os.open(ordner / f"{kennung}.teil", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        os.close(fd)
        with open(ordner / f"{kennung}.json", "w", encoding="utf-8") as f:
            json.dump({"art": art, "name": name, "groesse": groesse, "von": request.user.get_username(),
                       "begonnen_am": timezone.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)
    except OSError as e:
        return Response({"fehler": f"Die Datei konnte nicht angelegt werden ({e.strerror}). Rechte des Ordners für "
                                   "hochgeladene Dateien prüfen."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    protokolliere(SystemEreignis.Art.BACKUP if art == "sicherung" else SystemEreignis.Art.SYSTEM, request,
                  objekt=f"{regel['name']} hochladen", ereignis="upload_begonnen", datei=name, groesse=groesse,
                  upload=kennung, upload_art=art)
    return Response({"upload": kennung, "teil": TEIL, "erhalten": 0, "groesse": groesse},
                    status=status.HTTP_201_CREATED)


def teil_anhaengen(request, pfad, meta):
    """Nächstes Stück an der gemeldeten Stelle anhängen (``?versatz=`` muss dem bisher Empfangenen entsprechen)."""
    daten = request.data
    if not isinstance(daten, (bytes, bytearray)) or not daten:
        return Response({"fehler": "Erwartet wird ein Stück der Datei (application/octet-stream)."},
                        status=status.HTTP_400_BAD_REQUEST)
    if len(daten) > TEIL:
        return Response({"fehler": "Das Stück ist zu groß."}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    erhalten = pfad.stat().st_size
    try:
        versatz = int(request.query_params.get("versatz", ""))
    except ValueError:
        versatz = -1
    if versatz != erhalten:
        # z. B. nach einer unterbrochenen Verbindung: Die Oberfläche setzt an der gemeldeten Stelle fort
        return Response({"fehler": "Das Stück passt nicht an das bisher Empfangene.", "erhalten": erhalten},
                        status=status.HTTP_409_CONFLICT)
    if erhalten + len(daten) > meta.get("groesse", 0):
        return Response({"fehler": "Es kommt mehr an, als angekündigt wurde."}, status=status.HTTP_400_BAD_REQUEST)
    with open(pfad, "ab") as f:
        f.write(daten)
    return Response({"erhalten": erhalten + len(daten), "groesse": meta.get("groesse")})


def entfernen(pfad):
    for datei in (pfad, pfad.with_suffix(".json")):
        try:
            os.unlink(datei)
        except OSError:
            pass
