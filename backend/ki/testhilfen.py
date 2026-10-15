"""Hilfen für die Tests von „KI (Experimentell)“: Dokumente der Akte, Attrappe des Modell-Dienstes."""
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from django.core.files.base import ContentFile

KI_TMP = tempfile.mkdtemp(prefix="epm-ki-test-")


def dokument(patient, daten: bytes, name="befund.png", mime="image/png", **extra):
    from patienten.api import speichere_datei
    from patienten.models import Dokument

    meta = speichere_datei(patient, ContentFile(daten, name=name), mime)
    return Dokument.objects.create(patient=patient, titel=extra.pop("titel", "Laborbefund"), **meta, **extra)


def labor_png(**namen) -> bytes:
    from scans import testbilder

    return testbilder.png(testbilder.seite(testbilder.LABOR, **namen))


EXTRAKTION_LABOR = {
    "dokumenttyp": "labor", "dokumentdatum": "2026-09-01", "absender": "Labor Dr. Beispiel",
    "patient": {"name": "Muster, Erika", "geburtsdatum": "1961-03-14"},
    "laborwerte": [
        {"parameter": "Natrium", "wert": "138", "einheit": "mmol/l", "referenz": "135 - 145"},
        {"parameter": "Kalium", "wert": "3,2", "einheit": "mmol/l", "referenz": "3,5 - 5,1", "markierung": "L",
         "datum": "2026-09-01", "uhrzeit": "06:10"},
        {"parameter": "Kreatinin", "wert": "1,12", "einheit": "mg/dl", "referenz": "0,50 - 0,90"},
    ],
    "infusionen": [], "medikamente": [], "diagnosen": [],
    "zusammenfassung": "Laborbefund mit Elektrolyten und Nierenwerten.", "offene_punkte": [],
}


class Attrappe:
    """Steht für ``ki.modell.Client``: liefert feste Antworten und merkt sich die Anfragen."""

    url = "http://ki-modell:8080"

    def __init__(self, extraktion=None, transkription="Kalium 3,2 mmol/l", bericht=None):
        from ki.modell import Antwort

        self._antwort = Antwort
        self.extraktion = extraktion or EXTRAKTION_LABOR
        self.transkription = transkription
        self.bericht = bericht
        self.anfragen = []

    def bereit(self):
        return {"bereit": True, "modell": "attrappe.gguf#000000000000", "text": "bereit"}

    def chat(self, system, text, bilder=None, schema=None, max_tokens=1500, temperatur=0.0):
        self.anfragen.append({"system": system[:40], "bilder": len(bilder or []), "schema": schema is not None})
        if schema is not None:
            return self._antwort(json.dumps(self.extraktion), 0.1, "attrappe")
        if "Berichtsentwurf" in system or "Fakten" in text:
            return self._antwort(self.bericht or "Kalium 3,2 mmol/l am 01.09.2026 [1].", 0.1, "attrappe")
        return self._antwort(self.transkription, 0.1, "attrappe")


class ModellServer:
    """Echter HTTP-Server auf 127.0.0.1, der wie llama-server antwortet (für den Client-Test)."""

    def __init__(self, inhalt: str = '{"dokumenttyp": "labor"}', status: int = 200):
        antwort = {"choices": [{"message": {"content": inhalt}, "finish_reason": "stop"}], "model": "probe.gguf",
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        anfragen = self.anfragen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _senden(self, code, daten):
                body = json.dumps(daten).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/health":
                    self._senden(200, {"status": "ok"})
                elif self.path == "/v1/models":
                    self._senden(200, {"data": [{"id": "probe.gguf#abc"}]})
                else:
                    self._senden(404, {})

            def do_POST(self):
                laenge = int(self.headers.get("Content-Length", 0))
                anfragen.append(json.loads(self.rfile.read(laenge)))
                self._senden(status, antwort if status == 200 else {"error": "kaputt"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.faden = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.faden.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"


def ki_ordner() -> Path:
    p = Path(KI_TMP)
    p.mkdir(parents=True, exist_ok=True)
    return p
