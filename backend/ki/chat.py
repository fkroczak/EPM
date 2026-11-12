"""KI-Chat (12.11.2026): Texte medizinisch formulieren, prüfen, kürzen … im Menü „KI (Experimentell)“ › Chat.

- **Nur für die eigene Person**: Jede Unterhaltung gehört der Person, die sie begonnen hat; niemand sonst sieht sie
  (auch Admins nicht, ``api.KiChatViewSet``). Inhalte gehen nicht ins Audit-Log, nur dass gechattet wurde.
- **Wie alles bei der KI** spricht das Backend nicht selbst mit dem Modell: es legt die Antwort als Nachricht im
  Status „wartet“ an, der KI-Dienst schreibt sie (``epm_ki`` – Vorrang vor Dokumenten und Berichten, auch tagsüber).
- **Zuverlässigkeit**: fester Sicherheitsrahmen (``RAHMEN``) + Anweisung der gewählten Promptvorlage
  (Administration › Vorlagen › KI-Prompts) + niedrige Temperatur. Danach eine Gegenprüfung: Zahlen und Daten in der
  Antwort, die in keiner Eingabe der Person stehen, werden markiert; ebenso offene Stellen [?].
- Unterhaltungen werden nach ``EPM_KI_CHAT_TAGE`` (Standard 30) Tagen ohne Änderung gelöscht.
"""
import datetime as dt
import logging
import os
import re
import time

from django.db import transaction
from django.utils import timezone

from audit.models import SystemEreignis, protokolliere

from .berichte import _token
from .modell import Client, ModellFehler
from .models import KiChat, KiChatNachricht

log = logging.getLogger("epm.ki")
N = KiChatNachricht
RAHMEN = (
    "Du bist ein Schreibassistent im medizinischen Dokumentationssystem einer Praxis. Antworte immer auf Deutsch. "
    "Arbeite nur mit dem, was der Nutzer dir gibt: Erfinde keine Befunde, Werte, Daten, Diagnosen, Medikamente oder "
    "Dosierungen und ergänze keine Fakten. Übernimm Zahlen, Einheiten und Daten exakt. Ist etwas unklar oder fehlt "
    "eine Angabe, schreibe [?] an die Stelle oder frage nach, statt zu raten. Stelle keine eigenen Diagnosen und gib "
    "keine eigenen Therapieempfehlungen. Ein Mensch prüft jede Antwort, bevor sie verwendet wird."
)
MAX_ZEICHEN = 8000          # je Nachricht
VERLAUF_ZEICHEN = 16000     # so viel Verlauf geht höchstens mit (Kontext des Modells)
MAX_TOKENS = 1500
ZWISCHENSTAND_S = 1.5       # so oft geht der bisher geschriebene Text in die Datenbank (Anzeige beim Schreiben)
MAX_VERSUCHE = 3            # Modell gerade nicht erreichbar (schläft, startet neu): zurück in die Queue
WARTEN_HOECHSTENS = dt.timedelta(minutes=15)


def aufbewahrung_tage() -> int:
    try:
        return max(1, int(os.environ.get("EPM_KI_CHAT_TAGE", "30")))
    except ValueError:
        return 30


def systemanweisung(nachricht: KiChatNachricht) -> str:
    if not nachricht.anweisung.strip():
        return RAHMEN
    return f"{RAHMEN}\n\nAufgabe (Vorlage „{nachricht.vorlage_name}“):\n{nachricht.anweisung.strip()}"


def verlauf(nachricht: KiChatNachricht) -> list[dict]:
    """Bisherige fertige Nachrichten dieser Unterhaltung, neueste zuerst gekürzt auf ``VERLAUF_ZEICHEN``."""
    alle = list(KiChatNachricht.objects.filter(chat_id=nachricht.chat_id, id__lt=nachricht.id, status=N.Status.FERTIG)
                .order_by("-id").values("rolle", "text"))
    aus, summe = [], 0
    for m in alle:
        if not m["text"].strip():
            continue
        summe += len(m["text"])
        if summe > VERLAUF_ZEICHEN and aus:
            break
        aus.append({"role": "user" if m["rolle"] == N.Rolle.NUTZER else "assistant", "content": m["text"]})
    aus.reverse()
    # mit einer Nutzernachricht beginnen (Chat-Vorlage des Modells)
    while aus and aus[0]["role"] != "user":
        aus.pop(0)
    return aus


def gegenpruefen(antwort: str, eingaben: list[str]) -> dict:
    erlaubt = set()
    for e in eingaben:
        erlaubt |= _token(e)
    neu = sorted(t for t in _token(antwort) if t not in erlaubt and not re.fullmatch(r"\d", t))
    offen = len(re.findall(r"\[\?\]", antwort))
    return {"neue_werte": neu[:30], "offene_stellen": offen, "ok": not neu}


def beantworten(nachricht: KiChatNachricht, client: Client | None) -> KiChatNachricht:
    if client is None:
        nachricht.status, nachricht.fehler = N.Status.FEHLER, "Kein KI-Modell eingerichtet oder es ist nicht bereit."
        nachricht.fertig_am = timezone.now()
        nachricht.save(update_fields=["status", "fehler", "fertig_am"])
        return nachricht
    nachrichten = verlauf(nachricht)
    zuletzt = [0.0]

    def zwischenstand(text: str):
        # höchstens alle 1,5 s in die Datenbank – die Oberfläche fragt ohnehin nur so oft nach
        if time.monotonic() - zuletzt[0] >= ZWISCHENSTAND_S:
            zuletzt[0] = time.monotonic()
            KiChatNachricht.objects.filter(pk=nachricht.pk, status=N.Status.LAEUFT).update(
                text=text, lebenszeichen=timezone.now())

    try:
        a = client.gespraech(systemanweisung(nachricht), nachrichten, max_tokens=MAX_TOKENS,
                             temperatur=float(nachricht.temperatur), bei_teil=zwischenstand)
    except ModellFehler as e:
        # meist vorübergehend (Modell schläft, lädt oder startet neu): zurück in die Queue, der Dienst prüft das
        # Modell neu und versucht es noch einmal – erst nach MAX_VERSUCHE als Fehler
        nachricht.versuche += 1
        nachricht.fehler = str(e)[:2000]
        nachricht.text = ""
        if nachricht.versuche < MAX_VERSUCHE:
            nachricht.status = N.Status.WARTET
            nachricht.save(update_fields=["versuche", "fehler", "status", "text"])
        else:
            nachricht.status, nachricht.fertig_am = N.Status.FEHLER, timezone.now()
            nachricht.fehler = f"Das KI-Modell hat {MAX_VERSUCHE}-mal nicht geantwortet ({e})."[:2000]
            nachricht.save(update_fields=["versuche", "fehler", "status", "fertig_am", "text"])
        raise
    eingaben = [m["content"] for m in nachrichten if m["role"] == "user"]
    nachricht.text = a.text
    nachricht.pruefung = gegenpruefen(a.text, eingaben)
    nachricht.modell, nachricht.dauer_s = a.modell[:200], a.dauer_s
    nachricht.status, nachricht.fehler, nachricht.fertig_am = N.Status.FERTIG, "", timezone.now()
    nachricht.save(update_fields=["text", "pruefung", "modell", "dauer_s", "status", "fehler", "fertig_am"])
    KiChat.objects.filter(pk=nachricht.chat_id).update(aktualisiert_am=timezone.now())
    protokolliere(SystemEreignis.Art.KI, benutzername="ki-dienst", objekt=f"KI-Chat {nachricht.chat_id}",
                  aktion="chat_beantwortet", vorlage=nachricht.vorlage_name, dauer_s=a.dauer_s,
                  pruefung_ok=nachricht.pruefung.get("ok"))
    return nachricht


def holen() -> KiChatNachricht | None:
    with transaction.atomic():
        n = (KiChatNachricht.objects.select_for_update(skip_locked=True)
             .filter(status=N.Status.WARTET).order_by("id").first())
        if n is None:
            return None
        n.status, n.lebenszeichen = N.Status.LAEUFT, timezone.now()
        n.save(update_fields=["status", "lebenszeichen"])
        return n


def wartet() -> bool:
    return KiChatNachricht.objects.filter(status=N.Status.WARTET).exists()


def zu_lange_wartend() -> int:
    """Kommt das Modell nicht hoch (fehlt, zu wenig Speicher …), wartet niemand ewig am Bildschirm."""
    return KiChatNachricht.objects.filter(status=N.Status.WARTET,
                                          erstellt_am__lt=timezone.now() - WARTEN_HOECHSTENS).update(
        status=N.Status.FEHLER, fertig_am=timezone.now(),
        fehler=f"Das KI-Modell war {int(WARTEN_HOECHSTENS.total_seconds() // 60)} Minuten lang nicht bereit "
               "(lädt, fehlt oder Pause, z. B. während der Sicherung). Bitte später erneut senden.")


def aufraeumen(haengt_nach: dt.timedelta) -> int:
    """Hängende Antworten zurück in die Queue, alte Unterhaltungen löschen."""
    KiChatNachricht.objects.filter(status=N.Status.LAEUFT, lebenszeichen__lt=timezone.now() - haengt_nach).update(
        status=N.Status.WARTET)
    alt = timezone.now() - dt.timedelta(days=aufbewahrung_tage())
    anzahl, _ = KiChat.objects.filter(aktualisiert_am__lt=alt).delete()
    return anzahl
