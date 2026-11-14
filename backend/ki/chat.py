"""KI-Chat (12.11.2026): Texte medizinisch formulieren, prüfen, kürzen … im Menü „KI (Experimentell)“ › Chat.

- **Nur für die eigene Person**: Jede Unterhaltung gehört der Person, die sie begonnen hat; niemand sonst sieht sie
  (auch Admins nicht, ``api.KiChatViewSet``). Inhalte gehen nicht ins Audit-Log, nur dass gechattet wurde.
- **Wie alles bei der KI** spricht das Backend nicht selbst mit dem Modell: es legt die Antwort als Nachricht im
  Status „wartet“ an, der KI-Dienst schreibt sie (``epm_ki`` – Vorrang vor Dokumenten und Berichten, auch tagsüber).
- **Zuverlässigkeit**: fester Sicherheitsrahmen (``RAHMEN``) + Anweisung der gewählten Promptvorlage
  (Administration › Vorlagen › KI-Prompts) + niedrige Temperatur. Danach eine Gegenprüfung: Zahlen und Daten in der
  Antwort, die in keiner Eingabe der Person stehen, werden markiert; ebenso offene Stellen [?].
- **Dokumente** (12.11.2026): hochladen oder aus einer Akte wählen, ohne Seitengrenze. Der KI-Dienst erkennt den
  Text (wie bei den Scans; aus der Akte wird schon erkannter Text übernommen). Passt alles in den Kontext des Modells
  (``KI_KONTEXT``), liest es die Unterlagen ganz; sonst Teil für Teil: je Teil die für die Anfrage wichtigen Stellen
  wörtlich herausschreiben, dann aus diesen Auszügen antworten.
- Unterhaltungen werden nach ``KiEinstellung.chat_tage`` (Administration › KI; Startwert ``EPM_KI_CHAT_TAGE``,
  Standard 30) Tagen ohne Änderung gelöscht – mit ihren Anhängen.
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
from .models import KiChat, KiChatAnhang, KiChatNachricht, KiEinstellung, KiVorgang

log = logging.getLogger("epm.ki")
N = KiChatNachricht
RAHMEN = (
    "Du bist ein Schreibassistent im medizinischen Dokumentationssystem einer Praxis. Antworte immer auf Deutsch. "
    "Arbeite nur mit dem, was der Nutzer dir gibt: Erfinde keine Befunde, Werte, Daten, Diagnosen, Medikamente oder "
    "Dosierungen und ergänze keine Fakten. Übernimm Zahlen, Einheiten und Daten exakt. Ist etwas unklar oder fehlt "
    "eine Angabe, schreibe [?] an die Stelle oder frage nach, statt zu raten. Stelle keine eigenen Diagnosen und gib "
    "keine eigenen Therapieempfehlungen. Ein Mensch prüft jede Antwort, bevor sie verwendet wird."
)
MAX_ZEICHEN = 100000        # je Nachricht (längere Texte liest das Modell Teil für Teil)
VERLAUF_ZEICHEN = 200000    # Vorauswahl; was wirklich mitgeht, bestimmt der Kontext des Modells
MAX_TOKENS = 1500
ANTEIL_EINGABE = 0.8        # vom Kontext für die Eingabe; der Rest bleibt für die Antwort und einen parallelen Auftrag
AUSZUG_TOKENS = 700         # je gelesenem Teil eines langen Dokuments
AUSZUG_RAHMEN = (
    "Du hilfst, ein langes Dokument Stück für Stück zu lesen. Antworte auf Deutsch. Schreibe aus dem folgenden Teil "
    "alles heraus, was für die Aufgabe des Nutzers wichtig ist – Befunde, Werte mit Einheit und Datum, Diagnosen, "
    "Medikamente, Dosierungen, Daten, Namen von Untersuchungen – exakt wie im Text, knapp in Stichpunkten, mit "
    "Seitenangabe, wenn sie dasteht. Erfinde nichts und bewerte nichts. Steht nichts Wichtiges darin, antworte nur: "
    "nichts Relevantes"
)
ZWISCHENSTAND_S = 1.5       # so oft geht der bisher geschriebene Text in die Datenbank (Anzeige beim Schreiben)
MAX_VERSUCHE = 3            # Modell gerade nicht erreichbar (schläft, startet neu): zurück in die Queue
WARTEN_HOECHSTENS = dt.timedelta(minutes=15)

# Diktat → gegliederter Bericht (14.11.2026): mitgelieferte Vorlage (Migration 0006); fehlt sie oder ist sie
# ausgeblendet, gilt dieser Text. Wortgleich in ki/migrations/0006_korrekturbeispiele_diktat.py.
DIKTAT_VORLAGE = "Diktat als Brief gliedern"
DIKTAT_ANWEISUNG = (
    "Der Nutzer gibt dir die automatische Abschrift eines ärztlichen Diktats (Spracherkennung – sie kann Hör- und "
    "Schreibfehler enthalten) und die Berichtsart. Mache daraus einen gegliederten Entwurf dieses Berichts.\n"
    "- Übernimm jede inhaltliche Aussage, jeden Wert, jede Einheit, jedes Datum, jede Diagnose und jede Dosierung "
    "genau. Lasse nichts weg und füge nichts hinzu.\n"
    "- Setze Diktieranweisungen um, statt sie abzuschreiben („Punkt“, „Komma“, „neuer Absatz“, „Doppelpunkt“), "
    "entferne Füllwörter („äh“, „also“) und Versprecher; sagt der Arzt „streichen“ oder „nein, …“, gilt die "
    "korrigierte Fassung.\n"
    "- Gliedere mit Zwischenüberschriften, die zum Inhalt passen, z. B. Diagnosen, Anamnese, Befund, Therapie und "
    "Verlauf, Medikation, Procedere – nur Abschnitte, zu denen das Diktat etwas sagt. Jede Überschrift steht allein "
    "in einer Zeile mit „## “ davor; Aufzählungen beginnen mit „- “.\n"
    "- Ist ein Fachbegriff offensichtlich falsch gehört und die richtige Schreibweise eindeutig, schreibe sie "
    "richtig; sonst behalte das Wort und setze [?] dahinter.\n"
    "- Keine Anrede, keine Grußformel, keine Vorbemerkung – nur der Berichtstext."
)


def html_zu_text(html_text: str) -> str:
    """HTML aus dem Editor (Abschrift eines Diktats) → Klartext mit Absätzen für das Modell."""
    import html

    t = re.sub(r"(?i)<br\s*/?>", "\n", html_text or "")
    t = re.sub(r"(?i)</(p|h[1-6]|li|div)>", "\n\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def aufbewahrung_tage() -> int:
    """Einstellung ``chat_tage``; solange es keine Einstellungszeile gibt, ``EPM_KI_CHAT_TAGE`` (Startwert)."""
    tage = KiEinstellung.objects.filter(pk=1).values_list("chat_tage", flat=True).first()
    if tage:
        return tage
    try:
        return max(1, int(os.environ.get("EPM_KI_CHAT_TAGE", "30")))
    except ValueError:
        return 30


def systemanweisung(nachricht: KiChatNachricht) -> str:
    if not nachricht.anweisung.strip():
        return RAHMEN
    return f"{RAHMEN}\n\nAufgabe (Vorlage „{nachricht.vorlage_name}“):\n{nachricht.anweisung.strip()}"


def verlauf(nachricht: KiChatNachricht) -> list[dict]:
    """Bisherige fertige Nachrichten dieser Unterhaltung, neueste zuerst gekürzt auf ``VERLAUF_ZEICHEN``; bei
    Nachrichten mit Anhang steht dessen Name dabei (der Inhalt geht gesondert als Unterlage mit)."""
    alle = list(KiChatNachricht.objects.filter(chat_id=nachricht.chat_id, id__lt=nachricht.id, status=N.Status.FERTIG)
                .order_by("-id").values("id", "rolle", "text"))
    namen: dict[int, list[str]] = {}
    for nid, name in KiChatAnhang.objects.filter(nachricht__chat_id=nachricht.chat_id).values_list("nachricht_id",
                                                                                                    "name"):
        namen.setdefault(nid, []).append(name)
    aus, summe = [], 0
    for m in alle:
        text = m["text"].strip()
        if m["id"] in namen:
            text = (text + "\n\n" if text else "") + "[Angehängt: " + ", ".join(namen[m["id"]]) + "]"
        if not text:
            continue
        summe += len(text)
        if summe > VERLAUF_ZEICHEN and aus:
            break
        aus.append({"role": "user" if m["rolle"] == N.Rolle.NUTZER else "assistant", "content": text})
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


# ---------------------------------------------------------------------------------------------- Anhänge
def _vorhandener_text(dok) -> tuple[str, int]:
    """Schon erkannter Text eines Akten-Dokuments (Scans bzw. Nachtverarbeitung der KI) – spart die Texterkennung."""
    from patienten.models import DokumentText

    dt_ = DokumentText.objects.filter(dokument=dok).first()
    if dt_ is not None and dt_.text.strip():
        return dt_.text, 0
    v = (KiVorgang.objects.filter(dokument=dok, sha256=dok.sha256).exclude(ocr_text="")
         .order_by("-id").values_list("ocr_text", "seiten").first())
    return (v[0], v[1] or 0) if v else ("", 0)


def _pdf_seitenzahl(daten: bytes) -> int:
    if not daten.startswith(b"%PDF"):
        return 0
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(daten)
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception:  # noqa: BLE001 – nur für die Fortschrittsanzeige
        return 0


def anhang_erkennen(a: KiChatAnhang, paddle=None, melden=None) -> KiChatAnhang:
    """Text eines Anhangs erkennen, Seite für Seite (nach einem Abbruch geht es an der nächsten Seite weiter)."""
    from scans.ocr import fusion
    from scans.ocr.erkennung import seite_erkennen
    from scans.ocr.laden import Unlesbar, seiten_einzeln

    melden = melden or (lambda _t: None)

    def fehler(text: str):
        a.status, a.fehler, a.datei = KiChatAnhang.Status.FEHLER, text[:2000], None
        a.save(update_fields=["status", "fehler", "datei"])
        return a

    if a.status != KiChatAnhang.Status.WARTET:
        return a
    if a.herkunft == KiChatAnhang.Herkunft.AKTE:
        dok = a.dokument
        if dok is None:
            return fehler("Das Dokument ist nicht mehr in der Akte.")
        text, seiten = _vorhandener_text(dok)
        if text:
            a.text, a.seiten, a.seiten_fertig, a.status = text, seiten, seiten, KiChatAnhang.Status.FERTIG
            a.save(update_fields=["text", "seiten", "seiten_fertig", "status"])
            return a
        try:
            daten = dok.pfad.read_bytes()
        except OSError:
            return fehler("Die Datei des Dokuments ist nicht lesbar.")
    else:
        daten = bytes(a.datei or b"")
    gesamt = _pdf_seitenzahl(daten)
    teile = [a.text] if a.text and a.seiten_fertig else []
    try:
        _mime, seiten = seiten_einzeln(daten, max_seiten=10**6)
        for i, roh in enumerate(seiten, 1):
            if i <= a.seiten_fertig:
                continue
            melden(f"„{a.name}“: Seite {i}{f' von {gesamt}' if gesamt else ''} wird gelesen")
            _auf, ergebnis = seite_erkennen(roh, None, paddle=paddle)
            teile.append(f"[Seite {i}]\n{fusion.text_aus_json(ergebnis).strip()}")
            a.text, a.seiten_fertig = "\n\n".join(teile), i
            a.save(update_fields=["text", "seiten_fertig"])
    except Unlesbar as e:
        return fehler(str(e))
    a.seiten, a.status, a.datei = a.seiten_fertig, KiChatAnhang.Status.FERTIG, None
    a.save(update_fields=["seiten", "status", "datei"])
    return a


def _schneiden(text: str, max_zeichen: int) -> list[str]:
    """In Stücke von höchstens ``max_zeichen`` – an Absätzen (Seitenwechseln), notfalls mitten im Absatz."""
    stuecke, aktuell = [], ""
    for absatz in text.split("\n\n"):
        while len(absatz) > max_zeichen:
            if aktuell:
                stuecke.append(aktuell)
                aktuell = ""
            stuecke.append(absatz[:max_zeichen])
            absatz = absatz[max_zeichen:]
        if aktuell and len(aktuell) + 2 + len(absatz) > max_zeichen:
            stuecke.append(aktuell)
            aktuell = ""
        aktuell = f"{aktuell}\n\n{absatz}" if aktuell else absatz
    if aktuell.strip():
        stuecke.append(aktuell)
    return stuecke


def auszuege(client: Client, unterlagen: list[tuple[str, str]], aufgabe: str, budget: int, melden) -> str:
    """Lange Unterlagen Teil für Teil lesen: je Teil die wichtigen Stellen herausschreiben lassen. Sind auch die
    Auszüge noch zu lang, werden sie auf dieselbe Weise verdichtet."""
    teil_tokens = max(1024, int(budget * 0.6))
    stuecke = []
    for name, text in unterlagen:
        je_token = len(text) / max(1, client.tokens(text))
        stuecke += [(name, s) for s in _schneiden(text, max(2000, int(teil_tokens * je_token * 0.9)))]
    notizen = []
    for i, (name, stueck) in enumerate(stuecke, 1):
        melden(f"Unterlagen werden in Teilen gelesen: Teil {i} von {len(stuecke)}")
        a = client.chat(AUSZUG_RAHMEN, f"Aufgabe des Nutzers:\n{aufgabe}\n\nTeil {i} von {len(stuecke)} aus "
                                       f"„{name}“:\n{stueck}", max_tokens=AUSZUG_TOKENS, temperatur=0.0)
        if a.text and not a.text.lower().lstrip("„\"' ").startswith("nichts relevantes"):
            notizen.append(f"[{name}, Teil {i} von {len(stuecke)}]\n{a.text}")
    ergebnis = "\n\n".join(notizen) or "(In den Unterlagen steht nichts zu dieser Anfrage.)"
    if len(stuecke) > 1 and client.tokens(ergebnis) > budget * 0.75:
        return auszuege(client, [("Auszüge", ergebnis)], aufgabe, budget, melden)
    return ergebnis


def _unterlagen(nachricht: KiChatNachricht) -> list[tuple[str, str]]:
    return [(a.name, a.text) for a in KiChatAnhang.objects.filter(
        nachricht__chat_id=nachricht.chat_id, nachricht_id__lt=nachricht.id, status=KiChatAnhang.Status.FERTIG)
        .exclude(text="")]


def _block(unterlagen: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"<dokument name=\"{name}\">\n{text}\n</dokument>" for name, text in unterlagen)


def eingabe_bauen(nachricht: KiChatNachricht, client: Client, system: str, nachrichten: list[dict],
                  melden) -> tuple[list[dict], list[str]]:
    """Nachrichten für das Modell, so dass sie in den Kontext passen → (Nachrichten, Texte für die Gegenprüfung).

    Unterlagen gehen vor die letzte Anfrage. Passen sie nicht, liest das Modell sie Teil für Teil (``auszuege``);
    ein sehr langer eingegebener Text wird genauso behandelt. Vom übrigen Verlauf fällt das Älteste weg."""
    unterlagen = _unterlagen(nachricht)
    eingaben = [m["content"] for m in nachrichten if m["role"] == "user"] + [t for _n, t in unterlagen]
    if not nachrichten or nachrichten[-1]["role"] != "user":
        return nachrichten, eingaben
    vorher, frage = nachrichten[:-1], nachrichten[-1]["content"]
    budget = int(client.kontext() * ANTEIL_EINGABE) - MAX_TOKENS - client.tokens(system)
    if budget < 1500:
        raise ValueError("Der Kontext des KI-Modells ist zu klein (Administration › KI › Einrichtung › Kontext).")
    if client.tokens(frage) > budget * 0.6:
        # sehr langer eingegebener Text: wie eine Unterlage lesen; die Aufgabe steht in der Vorlage
        unterlagen = [*unterlagen, ("Ihr Text", frage)]
        frage = nachricht.anweisung.strip() or "Bearbeite den Text wie gewünscht."
    block = _block(unterlagen)
    if block and client.tokens(block) + client.tokens(frage) > budget * 0.75:
        aufgabe = f"{nachricht.anweisung.strip()}\n{frage}".strip()
        block = ("Auszüge aus den Unterlagen (das Modell hat sie Teil für Teil gelesen, nur die wichtigen Stellen "
                 "stehen hier):\n" + auszuege(client, unterlagen, aufgabe, budget, melden))
    letzte = f"Unterlagen:\n{block}\n\nAnfrage:\n{frage}" if block else frage
    rest = budget - client.tokens(letzte)
    while vorher and sum(len(m["content"]) for m in vorher) // 3 > rest:
        vorher.pop(0)
        while vorher and vorher[0]["role"] != "user":
            vorher.pop(0)
    return [*vorher, {"role": "user", "content": letzte}], eingaben


def beantworten(nachricht: KiChatNachricht, client: Client | None, paddle=None) -> KiChatNachricht:
    if client is None:
        nachricht.status, nachricht.fehler = N.Status.FEHLER, "Kein KI-Modell eingerichtet oder es ist nicht bereit."
        nachricht.fertig_am = timezone.now()
        nachricht.save(update_fields=["status", "fehler", "fertig_am"])
        return nachricht

    t0 = time.monotonic()

    def melden(text: str):
        KiChatNachricht.objects.filter(pk=nachricht.pk).update(schritt=text[:160], lebenszeichen=timezone.now())

    for a in KiChatAnhang.objects.filter(nachricht__chat_id=nachricht.chat_id, nachricht_id__lt=nachricht.id,
                                         status=KiChatAnhang.Status.WARTET):
        anhang_erkennen(a, paddle=paddle, melden=melden)
    frage = (KiChatNachricht.objects.filter(chat_id=nachricht.chat_id, id__lt=nachricht.id, rolle=N.Rolle.NUTZER)
             .order_by("-id").values_list("id", flat=True).first())
    kaputt = KiChatAnhang.objects.filter(nachricht_id=frage, status=KiChatAnhang.Status.FEHLER).first()
    if kaputt is not None:
        nachricht.status, nachricht.fertig_am = N.Status.FEHLER, timezone.now()
        nachricht.fehler, nachricht.schritt = f"„{kaputt.name}“ ist nicht lesbar: {kaputt.fehler}"[:2000], ""
        nachricht.save(update_fields=["status", "fertig_am", "fehler", "schritt"])
        return nachricht
    system = systemanweisung(nachricht)
    zuletzt = [0.0]

    def zwischenstand(text: str):
        # höchstens alle 1,5 s in die Datenbank – die Oberfläche fragt ohnehin nur so oft nach
        if time.monotonic() - zuletzt[0] >= ZWISCHENSTAND_S:
            zuletzt[0] = time.monotonic()
            KiChatNachricht.objects.filter(pk=nachricht.pk, status=N.Status.LAEUFT).update(
                text=text, lebenszeichen=timezone.now())

    try:
        nachrichten, eingaben = eingabe_bauen(nachricht, client, system, verlauf(nachricht), melden)
        melden("schreibt die Antwort")
        a = client.gespraech(system, nachrichten, max_tokens=MAX_TOKENS,
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
    nachricht.text, nachricht.schritt = a.text, ""
    nachricht.pruefung = gegenpruefen(a.text, eingaben)
    # umgekehrt: Zahlen und Daten der Anfrage, die in der Antwort fehlen (z. B. Diktat → Brief; beim Kürzen erwartet)
    anfrage = KiChatNachricht.objects.filter(pk=frage).values_list("text", flat=True).first() or ""
    in_antwort = _token(a.text)
    nachricht.pruefung["fehlende_werte"] = sorted(t for t in _token(anfrage)
                                                  if t not in in_antwort and not re.fullmatch(r"\d", t))[:30]
    nachricht.modell, nachricht.dauer_s = a.modell[:200], round(time.monotonic() - t0, 2)
    nachricht.status, nachricht.fehler, nachricht.fertig_am = N.Status.FERTIG, "", timezone.now()
    nachricht.save(update_fields=["text", "schritt", "pruefung", "modell", "dauer_s", "status", "fehler", "fertig_am"])
    KiChat.objects.filter(pk=nachricht.chat_id).update(aktualisiert_am=timezone.now())
    log.info("KI-Chat-Antwort %s fertig nach %d s: %s Tokens geschrieben%s", nachricht.pk, nachricht.dauer_s,
             (a.tokens or {}).get("completion_tokens", "?"),
             "" if nachricht.pruefung.get("ok") else " – Zahlen/Daten markiert")
    protokolliere(SystemEreignis.Art.KI, benutzername="ki-dienst", objekt=f"KI-Chat {nachricht.chat_id}",
                  aktion="chat_beantwortet", vorlage=nachricht.vorlage_name, dauer_s=nachricht.dauer_s,
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
