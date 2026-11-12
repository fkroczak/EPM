"""KI-Dienst (Container ``ki-worker``): Nachtverarbeitung, Berichtsentwürfe auf Anforderung, Ressourcenschutz.

    python manage.py epm_ki              # Dauerbetrieb
    python manage.py epm_ki --einmal     # alle wartenden Aufträge (ohne Zeitfenster), dann Ende – Tests, Fehlersuche
    python manage.py epm_ki --stand      # Modell-Dienst, Zeitfenster, Auslastung, Queue anzeigen
    python manage.py epm_ki --vormerken  # Dokumente der Akten in die Queue legen, dann Ende

Je Durchlauf (alle 5 s) entscheidet ``ki.steuerung`` anhand von Zeitfenster und Auslastung, ob und wie viele
Vorgänge parallel laufen. Laufende Vorgänge prüfen zwischen den Seiten, ob sie weitermachen dürfen; endet das
Nachtfenster oder wird es eng, werden sie zurückgestellt und setzen später an der gleichen Seite fort.
"""
import json
import logging
import os
import signal
import threading
import time
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection
from django.utils import timezone

from ki import berichte, chat, dienst, eingang, evaluation, krypto, modellwahl, pipeline
from ki.modell import Client, ModellFehler
from ki.models import KiEinstellung, KiEvaluationslauf, KiModellversion, KiVorgang
from ki.steuerung import Entscheidung, Messung, Steuerung

log = logging.getLogger("epm.ki")
TAKT_S = 5
CHAT_SCHLUESSEL = -2 * 10**9  # Schlüssel in self.laufend: Chat < Evaluation < Bericht < 0 < Vorgang
VORMERKEN_ALLE_S = 600
MODELL_PRUEFEN_ALLE_S = 60
AUFRAEUMEN_ALLE_S = 3600
# Tagsüber ohne Arbeit: llama-server beenden lassen und den Speicher freigeben (KI_MODELL_TAGSUEBER_ENTLADEN=0: nie)
SCHLAFEN_NACH_S = int(os.environ.get("KI_MODELL_SCHLAFEN_NACH_MIN", "30")) * 60


class Command(BaseCommand):
    help = "KI (Experimentell): Dokumente der Akten nachts erkennen und strukturieren, Berichtsentwürfe erstellen."

    def add_arguments(self, parser):
        parser.add_argument("--einmal", action="store_true", help="alle wartenden Aufträge, dann beenden")
        parser.add_argument("--stand", action="store_true", help="Stand ausgeben und beenden")
        parser.add_argument("--vormerken", action="store_true", help="Dokumente vormerken und beenden")

    def handle(self, *args, einmal=False, stand=False, vormerken=False, **opt):
        if stand:
            return self._stand()
        if vormerken:
            self.stdout.write(f"{eingang.vormerken(100000)} Dokumente vorgemerkt.")
            return
        try:  # niedrige Priorität: EPM und Datenbank bleiben flüssig
            os.nice(int(os.environ.get("KI_NICE", "15")))
        except OSError:
            pass
        Dienst(einmal=einmal, ausgabe=self.stdout).laufen()

    def _stand(self):
        client = Client.aus_einstellungen()
        self.stdout.write(f"Modell-Dienst: {client.bereit() if client else 'nicht eingerichtet (EPM_KI_MODELL_URL)'}")
        einst = KiEinstellung.laden()
        e = Steuerung().entscheiden(einst, Messung().messen(), timezone.now())
        self.stdout.write(f"Entscheidung: {json.dumps(e.als_dict(), ensure_ascii=False)}")
        self.stdout.write(f"Queue: {json.dumps(eingang.stand(), ensure_ascii=False)}")


class Dienst:
    def __init__(self, einmal: bool = False, ausgabe=None):
        self.einmal = einmal
        self.ausgabe = ausgabe
        self.ende = threading.Event()
        self.steuerung = Steuerung()
        self.messung = Messung()
        self.entscheidung = Entscheidung("pause", 0, True, grund="startet")
        self.laufend: dict[int, threading.Thread] = {}
        self.vorgaenge: dict[int, KiVorgang] = {}
        self.client = Client.aus_einstellungen()
        self.modell_bereit = False
        self.zuletzt = {"vormerken": 0.0, "modell": 0.0, "aufraeumen": 0.0}
        self.lebt = Path(os.environ.get("EPM_KI_LEBT", "/tmp/epm-ki-lebt"))
        self.start = timezone.now()
        self.bearbeitet = 0
        self.paddle = None
        self.letzte_arbeit = time.monotonic()

    # ------------------------------------------------------------------ Ablauf
    def laufen(self):
        self._signale()
        try:
            from scans.ocr.paddle import Paddle

            self.paddle = Paddle.laden()
        except Exception:  # noqa: BLE001 – ohne PP-OCR weiter mit Tesseract
            log.warning("PP-OCR nicht ladbar – Stufe 1 nur mit Tesseract")
        log.info("KI-Dienst bereit (Modell: %s)", self.client.url if self.client else "keins – nur Regeln")
        while not self.ende.is_set():
            try:
                if not self.einmal:  # --einmal (Tests): die Verbindung gehört dem Aufrufer
                    close_old_connections()
                self._durchlauf()
            except Exception:  # noqa: BLE001 – Datenbank startet noch, Migration läuft …
                if self.einmal:
                    raise
                log.exception("Durchlauf fehlgeschlagen – neuer Versuch in 10 Sekunden")
                self.ende.wait(10)
                continue
            if self.einmal and not self.laufend and not self._noch_etwas_zu_tun():
                break
            self.ende.wait(TAKT_S)
        for t in list(self.laufend.values()):
            t.join(timeout=60)
        if not self.einmal:
            close_old_connections()

    def _signale(self):
        def stopp(*_):
            self.ende.set()

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, stopp)
            signal.signal(signal.SIGINT, stopp)

    def _noch_etwas_zu_tun(self) -> bool:
        return KiVorgang.objects.filter(status=KiVorgang.Status.NEU).exists() or chat.wartet() or \
            berichte.KiBerichtsauftrag.objects.filter(status="wartet").exists()

    def _durchlauf(self):
        jetzt_s = time.monotonic()
        self._lebenszeichen()
        einst = KiEinstellung.laden()
        if jetzt_s - self.zuletzt["aufraeumen"] > AUFRAEUMEN_ALLE_S:
            self.zuletzt["aufraeumen"] = jetzt_s
            dienst.haengende_zuruecksetzen()
            chat.aufraeumen(dienst.HAENGT_NACH)
            offen = set(KiVorgang.objects.filter(status__in=[*KiVorgang.WARTEND, *KiVorgang.IN_ARBEIT])
                        .values_list("id", flat=True))
            krypto.aufraeumen(einst.aufbewahrung_tage, behalten=offen)
        if self.client and jetzt_s - self.zuletzt["modell"] > MODELL_PRUEFEN_ALLE_S:
            self.zuletzt["modell"] = jetzt_s
            self.modell_bereit = self.client.bereit()["bereit"]
        if jetzt_s - self.zuletzt["vormerken"] > VORMERKEN_ALLE_S:
            self.zuletzt["vormerken"] = jetzt_s
            if einst.aktiv:
                eingang.vormerken(500)

        chat.zu_lange_wartend()
        e = self._entscheiden(einst)
        self.entscheidung = e
        for vid in [v for v, t in self.laufend.items() if not t.is_alive()]:
            self.laufend.pop(vid)
            self.vorgaenge.pop(vid, None)
        self._modell_schlaf(e)
        # KI-Chat: jemand wartet am Bildschirm – immer eine Antwort zur Zeit, auch wenn Dokumente alle Plätze belegen,
        # und auch in einer Pause wegen Auslastung (die macht meist die KI selbst); nicht während der Sicherung, bei
        # ausgeschalteter KI oder ohne bereites Modell
        if self._chat_erlaubt(e) and not any(k <= CHAT_SCHLUESSEL for k in self.laufend):
            n = chat.holen()
            if n is not None:
                self._starten(CHAT_SCHLUESSEL - n.pk, self._chat, n)
        if e.parallel <= 0:
            return
        # Berichtsentwürfe sind ausdrücklich angefordert: Vorrang, auch tagsüber
        if len(self.laufend) < e.parallel:
            b = dienst.bericht_holen()
            if b is not None:
                self._starten(-b.pk, self._bericht, b)
        # Evaluationslauf (Modellvergleich) nur nachts – er lädt ggf. einen Kandidaten als Probe
        if e.modus == "nacht" and not self.laufend and self.client is not None:
            lauf = KiEvaluationslauf.objects.filter(fertig_am__isnull=True).order_by("id").first()
            if lauf is not None:
                self._starten(-10**9 - lauf.pk, self._evaluation, lauf)
                return
        while len(self.laufend) < e.parallel and not self.ende.is_set():
            v = dienst.auftrag_holen(nur_angefordert=e.nur_angefordert and not self.einmal,
                                     nachverarbeitung=self.client is not None and self.modell_bereit)
            if v is None:
                break
            self.vorgaenge[v.pk] = v
            self._starten(v.pk, self._vorgang, v)

    def _chat_erlaubt(self, e: Entscheidung) -> bool:
        if e.parallel > 0:
            return True
        if e.modus != "pause" or (e.last or {}).get("sicherung_laeuft"):
            return False
        return self.client is None or self.modell_bereit

    def _modell_schlaf(self, e: Entscheidung):
        """Tagsüber ohne Arbeit gibt der Modell-Container seinen Speicher frei; kommt Arbeit, wird er geweckt."""
        if self.client is None or os.environ.get("KI_MODELL_TAGSUEBER_ENTLADEN", "1") == "0":
            return
        arbeit = bool(self.laufend) or e.modus == "nacht" or chat.wartet() or KiVorgang.objects.filter(
            status=KiVorgang.Status.NEU, prioritaet__gte=dienst.ANGEFORDERT_AB).exists() or \
            berichte.KiBerichtsauftrag.objects.filter(status="wartet").exists()
        if arbeit:
            self.letzte_arbeit = time.monotonic()
            if modellwahl.schlaeft():
                modellwahl.schlafen(False)
                self.zuletzt["modell"] = 0.0  # gleich wieder nach dem Modell fragen
        elif not modellwahl.schlaeft() and time.monotonic() - self.letzte_arbeit > SCHLAFEN_NACH_S:
            modellwahl.schlafen(True)
            self.modell_bereit = False

    def _entscheiden(self, einst) -> Entscheidung:
        from scans.models import Scan

        scans = Scan.objects.filter(status__in=[Scan.Status.WARTET, Scan.Status.LAEUFT]).exists()
        e = self.steuerung.entscheiden(einst, self.messung.messen(), timezone.now(), scans_warten=scans)
        if self.einmal and e.modus in ("tag", "nacht"):
            e.parallel, e.nur_angefordert = max(1, e.parallel), False
        if self.client is not None and not self.modell_bereit and os.environ.get("KI_OHNE_MODELL", "0") != "1":
            # Modell eingerichtet, aber (noch) nicht bereit: lieber warten als mit halber Qualität arbeiten
            e.parallel, e.grund = 0, "KI-Modell nicht bereit (startet oder fehlt) – Queue wartet."
            e.modus = "pause" if e.modus in ("tag", "nacht") else e.modus
        return e

    def _starten(self, schluessel: int, ziel, obj):
        if self.einmal:
            # --einmal: nacheinander im Vordergrund (Fehlersuche, Tests) – ohne eigene Fäden und Verbindungen
            ziel(obj)
            return
        t = threading.Thread(target=ziel, args=(obj,), name=f"epm-ki-{schluessel}", daemon=True)
        self.laufend[schluessel] = t
        t.start()

    # ------------------------------------------------------------------ Arbeit
    def _abbrechen(self, vorgang: KiVorgang) -> str | None:
        if self.ende.is_set():
            return "KI-Dienst wird beendet"
        e = self.entscheidung
        # Last-Pause: keine neuen Aufträge, aber laufende nicht abbrechen – die Last macht meist das Modell selbst;
        # sonst würde der Vorgang nach jedem Modellaufruf verworfen und endlos neu begonnen
        if e.modus == "aus" or (e.modus == "pause" and not e.wegen_last):
            return e.grund or "Pause"
        if e.modus == "tag" and e.nur_angefordert and vorgang.prioritaet < dienst.ANGEFORDERT_AB and not self.einmal:
            return "Nachtfenster zu Ende"
        return None

    def _vorgang(self, v: KiVorgang):
        # Protokoll (docker compose logs ki-worker): was bearbeitet wird – nur Nummern, keine Namen oder Inhalte
        t0 = time.monotonic()
        log.info("%s gestartet: Dokument %s, Akte Nr. %s, %s, Versuch %s", v, v.dokument_id, v.patient.nummer,
                 "angefordert" if v.prioritaet >= dienst.ANGEFORDERT_AB else "Nachtverarbeitung", v.versuche)

        def melden(text, prozent=None):
            dienst.fortschritt(v, text, prozent)
            log.info("%s: %s%s", v, text, f" ({prozent} %)" if prozent is not None else "")

        try:
            rahmen = pipeline.Rahmen(
                client=self.client if self.modell_bereit else None, sparsam=self.entscheidung.sparsam,
                abbrechen=lambda: self._abbrechen(v), melden=melden)
            if self.einmal:  # Lebenszeichen kommen mit jedem Fortschritt (gleicher Faden)
                pipeline.verarbeiten(v, rahmen, paddle=self.paddle)
            else:
                with dienst.herzschlag(v, zusatz=self._lebenszeichen):
                    pipeline.verarbeiten(v, rahmen, paddle=self.paddle)
            self.bearbeitet += 1
            v.refresh_from_db()
            log.info("%s fertig nach %d s: %s – Typ %s, %s Seite(n), %s Vorschläge", v, time.monotonic() - t0,
                     v.get_status_display(), v.dokumenttyp or "?", v.seiten, v.felder.count())
        except pipeline.Abgebrochen as e:
            dienst.zurueckstellen(v, str(e))
            log.info("%s zurückgestellt: %s", v, e)
        except Exception as e:  # noqa: BLE001 – ein Dokument darf den Dienst nicht anhalten
            log.exception("%s fehlgeschlagen", v)
            dienst.fehlgeschlagen(v, f"{type(e).__name__}: {e}")
        finally:
            if not self.einmal:
                connection.close()

    def _evaluation(self, lauf):
        """Modell der Version laden (Probe, wenn nicht aktiv), alle Fälle strukturieren lassen, zurückschalten."""
        mv = lauf.modellversion
        probe = mv.status != KiModellversion.Status.AKTIV
        try:
            if probe:
                modellwahl.probe_setzen(mv)
                kennung = modellwahl.kennung(mv)
                frist = time.monotonic() + 900
                while time.monotonic() < frist and not self.ende.is_set():
                    stand = self.client.bereit()
                    if stand["bereit"] and kennung in stand["modell"]:
                        break
                    self.ende.wait(10)
                else:
                    KiEvaluationslauf.objects.filter(pk=lauf.pk).update(
                        fertig_am=timezone.now(),
                        fehler="Kandidat nicht geladen (Datei fehlt, Prüfsumme falsch oder zu wenig Speicher).")
                    return
            evaluation.lauf_ausfuehren(lauf, self.client,
                                       abbrechen=lambda: self.ende.is_set() or self.entscheidung.modus != "nacht")
        except Exception as e:  # noqa: BLE001
            log.exception("Evaluationslauf %s fehlgeschlagen", lauf.pk)
            KiEvaluationslauf.objects.filter(pk=lauf.pk).update(fertig_am=timezone.now(),
                                                                fehler=f"{type(e).__name__}: {e}"[:500])
        finally:
            if probe:
                modellwahl.probe_setzen(None)
                self.modell_bereit = False
                self.zuletzt["modell"] = 0.0
            if not self.einmal:
                connection.close()

    def _chat(self, n):
        log.info("KI-Chat-Antwort %s gestartet (Vorlage „%s“, Versuch %s)", n.pk, n.vorlage_name or "–", n.versuche + 1)
        try:
            if self.einmal:
                chat.beantworten(n, self.client if self.modell_bereit else None)
            else:
                with dienst.herzschlag(n):
                    chat.beantworten(n, self.client if self.modell_bereit else None)
        except ModellFehler as e:
            # Modell weg (schläft, startet neu, abgestürzt): erst wieder arbeiten, wenn es sich als bereit meldet
            log.warning("KI-Chat-Antwort %s: Modell nicht erreichbar (%s)", n.pk, e)
            self.modell_bereit = False
            self.zuletzt["modell"] = 0.0
        except Exception as e:  # noqa: BLE001
            log.exception("KI-Chat-Antwort %s fehlgeschlagen", n.pk)
            type(n).objects.filter(pk=n.pk).update(status="fehler", fehler=f"{type(e).__name__}: {e}"[:2000],
                                                   fertig_am=timezone.now())
        finally:
            if not self.einmal:
                connection.close()

    def _bericht(self, b):
        log.info("Berichtsentwurf %s gestartet: %s, Akte Nr. %s", b.pk, b.get_art_display(), b.patient.nummer)
        try:
            if self.einmal:
                berichte.erstellen(b, self.client if self.modell_bereit else None)
            else:
                with dienst.herzschlag(b):
                    berichte.erstellen(b, self.client if self.modell_bereit else None)
        except Exception as e:  # noqa: BLE001
            log.exception("Berichtsentwurf %s fehlgeschlagen", b.pk)
            type(b).objects.filter(pk=b.pk).update(status="fehler", fehler=f"{type(e).__name__}: {e}"[:2000])
        finally:
            if not self.einmal:
                connection.close()

    # ------------------------------------------------------------------ Stand
    def _lebenszeichen(self):
        try:
            self.lebt.touch()
        except OSError:
            pass
        daten = {"gestartet": self.start.isoformat(timespec="seconds"),
                 "lebenszeichen": timezone.now().isoformat(timespec="seconds"),
                 "entscheidung": self.entscheidung.als_dict(), "laufend": sorted(self.vorgaenge),
                 "bearbeitet": self.bearbeitet,
                 "modell": {"eingerichtet": self.client is not None, "bereit": self.modell_bereit,
                            "adresse": self.client.url if self.client else ""},
                 "pp_ocr": self.paddle is not None}
        dienst.stand_schreiben(daten)

