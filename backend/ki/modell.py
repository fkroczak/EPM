"""Verbindung zum lokalen Modell-Dienst (Container ``ki-modell``: llama.cpp ``llama-server`` mit Qwen3.5).

Offline-Grundsatz (Auftrag 2 und 8): Es gibt nur **eine** Gegenstelle, und die steht im Netz ``intern``. Die Adresse
kommt aus ``EPM_KI_MODELL_URL``; ihr Rechnername muss in ``EPM_KI_ERLAUBTE_HOSTS`` stehen (Standard ``ki-modell``,
``localhost``, ``127.0.0.1``), sonst wird sie abgewiesen. Proxy-Einstellungen der Umgebung (``HTTPS_PROXY`` …) werden
ausdrücklich nicht benutzt – eine Anfrage kann den Server so nicht verlassen.

Der Dienst spricht die OpenAI-kompatible Schnittstelle von llama-server (``/v1/chat/completions``); Bilder gehen als
``data:``-Adresse mit. Strukturierte Antworten erzwingt ein JSON-Schema (llama.cpp übersetzt es in eine Grammatik),
damit nur gültiges JSON entsteht.
"""
import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from django.conf import settings

log = logging.getLogger("epm.ki")


class ModellFehler(RuntimeError):
    """Der Modell-Dienst hat nicht oder unbrauchbar geantwortet."""


class NichtErlaubt(ValueError):
    """Adresse des Modell-Dienstes zeigt nicht auf einen erlaubten Rechner im internen Netz."""


def pruefe_adresse(url: str) -> str:
    """Nur ``http://<erlaubter Rechner>[:Port]`` – kein https nach außen, keine Zugangsdaten, kein Pfadtrick."""
    teile = urlsplit(url or "")
    if teile.scheme != "http" or not teile.hostname:
        raise NichtErlaubt("Die Adresse des KI-Modells muss mit http:// beginnen und einen Rechnernamen enthalten.")
    if teile.username or teile.password or teile.query or teile.fragment:
        raise NichtErlaubt("Die Adresse des KI-Modells darf keine Zugangsdaten oder Parameter enthalten.")
    erlaubt = {h.lower() for h in settings.EPM_KI_ERLAUBTE_HOSTS}
    if teile.hostname.lower() not in erlaubt:
        raise NichtErlaubt(f"Rechner „{teile.hostname}“ ist für das KI-Modell nicht erlaubt "
                           f"(EPM_KI_ERLAUBTE_HOSTS: {', '.join(sorted(erlaubt))}).")
    return f"http://{teile.netloc}{teile.path.rstrip('/')}"


# Ohne Proxy: auch wenn die Umgebung einen setzt, geht nichts über ihn
_OEFFNER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass
class Antwort:
    text: str
    dauer_s: float
    modell: str = ""
    tokens: dict = field(default_factory=dict)

    def json(self) -> dict:
        try:
            daten = json.loads(self.text)
        except json.JSONDecodeError as e:
            # bei Grammatik-gebundener Ausgabe selten (z. B. abgeschnitten, weil max_tokens erreicht)
            raise ModellFehler(f"Antwort ist kein gültiges JSON ({e.msg}).") from e
        if not isinstance(daten, dict):
            raise ModellFehler("Antwort ist kein JSON-Objekt.")
        return daten


class Client:
    def __init__(self, url: str, zeitlimit_s: float = 900):
        self.url = pruefe_adresse(url)
        self.zeitlimit_s = zeitlimit_s

    @classmethod
    def aus_einstellungen(cls) -> "Client | None":
        """``None``, wenn kein Modell-Dienst eingerichtet ist (dann arbeitet die KI nur mit Regeln)."""
        url = settings.EPM_KI_MODELL_URL
        if not url:
            return None
        return cls(url)

    def _anfrage(self, pfad: str, daten: dict | None = None, zeitlimit: float | None = None) -> dict:
        body = json.dumps(daten).encode() if daten is not None else None
        req = urllib.request.Request(self.url + pfad, data=body, method="POST" if body else "GET",
                                     headers={"Content-Type": "application/json"})
        try:
            with _OEFFNER.open(req, timeout=zeitlimit or self.zeitlimit_s) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")[:300]
            raise ModellFehler(f"Modell-Dienst antwortet mit {e.code}: {text}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ModellFehler(f"Modell-Dienst nicht erreichbar ({e}).") from e
        except json.JSONDecodeError as e:
            raise ModellFehler("Modell-Dienst liefert kein JSON.") from e

    def bereit(self) -> dict:
        """{"bereit": bool, "modell": str, "text": str} – für Systemseite und Worker."""
        try:
            self._anfrage("/health", zeitlimit=5)
            modelle = self._anfrage("/v1/models", zeitlimit=5)
        except ModellFehler as e:
            return {"bereit": False, "modell": "", "text": str(e)}
        namen = [m.get("id", "") for m in modelle.get("data", []) if isinstance(m, dict)]
        return {"bereit": True, "modell": namen[0] if namen else "", "text": "bereit"}

    def kontext(self) -> int:
        """Kontext des Modells in Tokens (llama-server ``/props``); sonst ``KI_KONTEXT`` bzw. 16384."""
        try:
            props = self._anfrage("/props", zeitlimit=10)
            n = int((props.get("default_generation_settings") or {}).get("n_ctx") or props.get("n_ctx") or 0)
            if n > 0:
                return n
        except (ModellFehler, TypeError, ValueError, AttributeError):
            pass
        try:
            return max(2048, int(os.environ.get("KI_KONTEXT", "16384")))
        except ValueError:
            return 16384

    def tokens(self, text: str) -> int:
        """Tokens eines Textes (llama-server ``/tokenize``); ohne Antwort vorsichtig geschätzt (3 Zeichen je Token)."""
        try:
            r = self._anfrage("/tokenize", {"content": text}, zeitlimit=60)
            if isinstance(r.get("tokens"), list):
                return len(r["tokens"])
        except (ModellFehler, AttributeError):
            pass
        return len(text) // 3 + 1

    def chat(self, system: str, text: str, bilder: list[bytes] | None = None, schema: dict | None = None,
             max_tokens: int = 1500, temperatur: float = 0.0) -> Antwort:
        inhalt: list[dict] = []
        for b in bilder or []:
            inhalt.append({"type": "image_url",
                           "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b).decode()}})
        inhalt.append({"type": "text", "text": text})
        daten = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": inhalt}],
            "temperature": temperatur,
            "max_tokens": max_tokens,
            "stream": False,
            # Qwen3.5 denkt sonst zuerst ausführlich nach – das kostet auf der CPU Minuten und bringt beim Abschreiben
            # nichts
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if schema is not None:
            daten["response_format"] = {"type": "json_schema", "json_schema": {"name": "antwort", "schema": schema}}
        t0 = time.monotonic()
        r = self._anfrage("/v1/chat/completions", daten)
        dauer = time.monotonic() - t0
        try:
            wahl = r["choices"][0]
            text_aus = wahl["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ModellFehler("Antwort des Modell-Dienstes ist unvollständig.") from e
        if wahl.get("finish_reason") == "length" and schema is not None:
            log.warning("Antwort des Modells abgeschnitten (max_tokens=%s)", max_tokens)
        return Antwort(text=text_aus.strip(), dauer_s=round(dauer, 2), modell=str(r.get("model", "")),
                       tokens=r.get("usage") or {})

    def gespraech(self, system: str, nachrichten: list[dict], max_tokens: int = 1500,
                  temperatur: float = 0.1, bei_teil=None) -> Antwort:
        """Chat mit Verlauf: ``nachrichten`` = [{"role": "user"|"assistant", "content": str}, …] (KI-Chat).

        Gestreamt (Server-Sent Events): ``bei_teil(bisheriger_text)`` wird während des Schreibens aufgerufen, damit
        die Oberfläche die Antwort Stück für Stück zeigen kann."""
        daten = {"messages": [{"role": "system", "content": system}, *nachrichten], "temperature": temperatur,
                 "max_tokens": max_tokens, "stream": True, "chat_template_kwargs": {"enable_thinking": False}}
        req = urllib.request.Request(self.url + "/v1/chat/completions", data=json.dumps(daten).encode(),
                                     method="POST", headers={"Content-Type": "application/json"})
        t0 = time.monotonic()
        teile, modell, tokens = [], "", {}
        try:
            with _OEFFNER.open(req, timeout=self.zeitlimit_s) as r:
                for roh in r:
                    zeile = roh.decode("utf-8", "replace").strip()
                    if not zeile.startswith("data:"):
                        continue
                    inhalt = zeile[5:].strip()
                    if inhalt == "[DONE]":
                        break
                    try:
                        stueck = json.loads(inhalt)
                    except json.JSONDecodeError:
                        continue
                    modell = str(stueck.get("model", modell))
                    tokens = stueck.get("usage") or tokens
                    for wahl in stueck.get("choices") or []:
                        neu = (wahl.get("delta") or {}).get("content") or ""
                        if neu:
                            teile.append(neu)
                            if bei_teil is not None:
                                bei_teil("".join(teile))
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")[:300]
            raise ModellFehler(f"Modell-Dienst antwortet mit {e.code}: {text}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ModellFehler(f"Modell-Dienst nicht erreichbar ({e}).") from e
        return Antwort(text="".join(teile).strip(), dauer_s=round(time.monotonic() - t0, 2), modell=modell,
                       tokens=tokens)
