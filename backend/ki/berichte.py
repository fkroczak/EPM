"""Berichtsentwurf auf ausdrückliche Anforderung (Auftrag 6).

1. **Fakten sammeln** – ausschließlich aus freigegebenen Inhalten der Akte (Laborbefunde, nicht-Entwurfs-
   Infusionspläne, Medikamente, Diagnosen, Verlauf der Therapie, Kontakte) im gewählten Zeitraum. Jede Tatsache
   bekommt eine Nummer und ihre Quelle. KI-Vorschläge, die noch niemand übernommen hat, zählen nicht.
2. **Formulieren** – das lokale Modell schreibt aus den nummerierten Fakten einen Text und belegt jede Aussage mit
   [Nummer]. Ohne Modell entsteht ein gegliederter Entwurf direkt aus den Fakten.
3. **Gegenprüfen** – jede Zahl und jedes Datum im Text muss in den Fakten stehen, jede Belegnummer muss es geben;
   Formulierungen, die nach Empfehlung oder Diagnose klingen, werden markiert. Die Markierungen stehen über dem
   Entwurf.

Der Entwurf ist immer als KI-generiert gekennzeichnet, nennt seine Quellen und geht nie von selbst in die Akte:
Speichern legt einen ``berichte.Bericht`` im Status „Entwurf“ an; freigeben kann ihn nur, wer das Recht hat.
"""
import datetime as dt
import html
import logging
import re

from django.utils import timezone
from django.utils.html import strip_tags

from audit.models import SystemEreignis, protokolliere

from . import prompts
from .modell import Client, ModellFehler
from .models import KiBerichtsauftrag, KiModellversion

log = logging.getLogger("epm.ki")
KENNZEICHNUNG = "KI-Entwurf (Experimentell) – automatisch erstellt, nicht geprüft, nicht freigegeben."
VERDAECHTIG = [r"\bempfehl", r"\bsollte[n]?\b", r"\braten\b", r"\bindiziert\b", r"\bratsam\b", r"\bnotwendig\b",
               r"\bverdacht auf\b", r"\bdiagnostiziert\b", r"\bwir schlagen\b", r"\bzu erwägen\b", r"\bprognose\b",
               r"\bmüsste\b", r"\bmuss\b"]
QUELLEN_JE_ART = {
    KiBerichtsauftrag.Art.LABOR: ["labor"],
    KiBerichtsauftrag.Art.INFUSION: ["infusion", "medikation"],
    KiBerichtsauftrag.Art.VERLAUF: ["diagnosen", "verlauf", "labor", "infusion", "medikation"],
}
ALLE_QUELLEN = ["labor", "infusion", "medikation", "diagnosen", "verlauf"]


def _z(d) -> str:
    if d is None:
        return ""
    if isinstance(d, int):
        return str(d)
    return format(d.normalize(), "f").replace(".", ",")


def _d(d: dt.date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else ""


def fakten_sammeln(auftrag: KiBerichtsauftrag) -> list[dict]:
    from befunde.models import Laborbefund
    from infusionen.models import Infusionsplan
    from patienten.models import Diagnose, Kontakt, Medikament, Therapieschritt

    p = auftrag.patient
    von = auftrag.von or dt.date(1900, 1, 1)
    bis = auftrag.bis or timezone.localdate()
    quellen = [q for q in (auftrag.dokumenttypen or QUELLEN_JE_ART[auftrag.art]) if q in ALLE_QUELLEN]
    fakten: list[dict] = []

    def neu(text, modell, kennung, datum=None):
        fakten.append({"nr": len(fakten) + 1, "text": text, "quelle": {"modell": modell, "id": kennung},
                       "datum": datum.isoformat() if datum else None})

    if "diagnosen" in quellen:
        for dg in Diagnose.objects.filter(patient=p, aktiv=True).order_by("reihenfolge", "id"):
            neu(f"Diagnose: {dg.bezeichnung} ({dg.icd_code})" + (f", seit {_d(dg.seit)}" if dg.seit else ""),
                "diagnose", dg.pk, dg.seit)
    if "labor" in quellen:
        for b in (Laborbefund.objects.filter(patient=p, abgenommen_am__range=(von, bis))
                  .prefetch_related("werte__parameter").order_by("abgenommen_am", "id")):
            zeit = _d(b.abgenommen_am) + (f" {b.abgenommen_um:%H:%M}" if b.abgenommen_um else "")
            for w in b.werte.all():
                name = w.parameter.name if w.parameter_id else w.freitext_name
                wert = _z(w.wert) if w.wert is not None else w.wert_text
                ref = ""
                if w.referenz_von is not None or w.referenz_bis is not None:
                    ref = f" (Referenz {_z(w.referenz_von)}–{_z(w.referenz_bis)})"
                neu(f"Labor {zeit}: {name} {wert} {w.einheit}{ref}".replace("  ", " "), "laborwert", w.pk,
                    b.abgenommen_am)
    if "infusion" in quellen:
        felder = [("basis_ml", "Basislösung", "ml"), ("glucose_g", "Glucose", "g"),
                  ("aminosaeuren_g", "Aminosäuren", "g"), ("lipide_g", "Lipide", "g"),
                  ("albumin_ml", "Humanalbumin", "ml"), ("natrium_mmol", "Natrium", "mmol"),
                  ("kalium_mmol", "Kalium", "mmol"), ("phosphat_mmol", "Phosphat", "mmol"),
                  ("calcium_mmol", "Calcium", "mmol"), ("magnesium_mmol", "Magnesium", "mmol"),
                  ("laufzeit_h", "Laufzeit", "h")]
        for plan in (Infusionsplan.objects.filter(patient=p, gueltig_ab__range=(von, bis))
                     .exclude(status=Infusionsplan.Status.ENTWURF).order_by("gueltig_ab", "id")):
            teile = [f"{name} {_z(getattr(plan, f))} {e}" for f, name, e in felder if getattr(plan, f) is not None]
            neu(f"Infusionsplan gültig ab {_d(plan.gueltig_ab)} ({plan.get_status_display()}): " + ", ".join(teile),
                "infusionsplan", plan.pk, plan.gueltig_ab)
    if "medikation" in quellen:
        for m in Medikament.objects.filter(patient=p).order_by("-aktiv", "reihenfolge", "id"):
            if m.seit and m.seit > bis:
                continue
            dosis = m.dosierung_frei or "-".join(x or "0" for x in (m.morgens, m.mittags, m.abends, m.nachts))
            status = "aktiv" if m.aktiv else f"abgesetzt {_d(m.abgesetzt_am)}".strip()
            neu(f"Medikament: {m.wirkstoff} {m.staerke} {dosis} ({status})".replace("  ", " "), "medikament", m.pk,
                m.seit)
    if "verlauf" in quellen:
        for t in Therapieschritt.objects.filter(patient=p, aktiv=True, datum__range=(von, bis)).order_by("datum"):
            neu(f"Therapie {_d(t.datum)}: {t.text}", "therapieschritt", t.pk, t.datum)
        for k in (Kontakt.objects.filter(patient=p, storniert_am__isnull=True,
                                         zeitpunkt__date__range=(von, bis)).order_by("zeitpunkt")[:200]):
            text = re.sub(r"\s+", " ", strip_tags(k.text)).strip()[:400]
            neu(f"Kontakt {k.zeitpunkt.astimezone(timezone.get_current_timezone()):%d.%m.%Y}: {text}", "kontakt",
                k.pk, k.zeitpunkt.date())
    return fakten


def _token(text: str) -> set[str]:
    """Zahlen und Daten eines Textes, vereinheitlicht (Komma/Punkt, führende Nullen bei Daten)."""
    aus = set()
    for m in re.finditer(r"\d{1,2}\.\d{1,2}\.\d{2,4}", text):
        tag, monat, jahr = m.group(0).split(".")
        aus.add(f"{int(tag)}.{int(monat)}.{jahr}")
    ohne_daten = re.sub(r"\d{1,2}\.\d{1,2}\.\d{2,4}", " ", text)
    ohne_belege = re.sub(r"\[\d+(?:\s*,\s*\d+)*\]", " ", ohne_daten)
    for m in re.finditer(r"\d+(?:[.,]\d+)?", ohne_belege):
        aus.add(m.group(0).replace(".", ","))
    return aus


def gegenpruefen(entwurf: str, fakten: list[dict]) -> dict:
    erlaubt = set()
    for f in fakten:
        erlaubt |= _token(f["text"])
    nummern = {f["nr"] for f in fakten}
    unbelegt = sorted(t for t in _token(entwurf) if t not in erlaubt and not re.fullmatch(r"\d", t))
    belege = {int(n) for grp in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", entwurf) for n in re.split(r"\s*,\s*", grp)}
    falsche = sorted(belege - nummern)
    saetze = [s.strip() for s in re.split(r"(?<=[.!?])\s+", entwurf) if s.strip()]
    ohne_beleg = [s[:160] for s in saetze if len(s) > 40 and not re.search(r"\[\d", s)]
    auffaellig = [s[:160] for s in saetze if any(re.search(v, s, re.I) for v in VERDAECHTIG)]
    return {"unbelegte_werte": unbelegt, "unbekannte_belege": falsche, "saetze_ohne_beleg": ohne_beleg[:20],
            "empfehlung_oder_bewertung": auffaellig[:20],
            "ok": not (unbelegt or falsche or auffaellig)}


def _ohne_modell(auftrag: KiBerichtsauftrag, fakten: list[dict]) -> str:
    if not fakten:
        return "Im gewählten Zeitraum sind keine freigegebenen Inhalte dokumentiert."
    zeilen = [f"{auftrag.get_art_display()} – Zusammenstellung der dokumentierten Angaben:"]
    zeilen += [f"- {f['text']} [{f['nr']}]" for f in fakten]
    return "\n".join(zeilen)


def erstellen(auftrag: KiBerichtsauftrag, client: Client | None) -> KiBerichtsauftrag:
    fakten = fakten_sammeln(auftrag)
    auftrag.fakten = fakten
    mv = KiModellversion.aktiv("vision") if client else None
    text = ""
    if client is not None and fakten:
        try:
            a = client.chat(prompts.BERICHT, prompts.bericht_text(auftrag.get_art_display(), fakten[:400]),
                            max_tokens=2000, temperatur=0.1)
            text = a.text
        except ModellFehler as e:
            auftrag.fehler = f"KI-Modell nicht verfügbar ({e}) – Entwurf direkt aus den Fakten."
    if not text:
        text = _ohne_modell(auftrag, fakten)
    auftrag.entwurf = text
    auftrag.pruefung = gegenpruefen(text, fakten)
    auftrag.modellversion = mv
    auftrag.status = KiBerichtsauftrag.Status.FERTIG
    auftrag.fertig_am = timezone.now()
    auftrag.save()
    log.info("Berichtsentwurf %s fertig: %s Fakten, Gegenprüfung %s", auftrag.pk, len(fakten),
             "ok" if auftrag.pruefung.get("ok") else "mit Markierungen")
    protokolliere(SystemEreignis.Art.KI, benutzername="ki-dienst", objekt=f"Berichtsentwurf {auftrag.pk}",
                  aktion="bericht_erstellt", patient_id=auftrag.patient_id, berichtsart=auftrag.art, fakten=len(fakten),
                  modell=mv.name if mv else "", prompt_version=prompts.PROMPT_VERSION if mv else "",
                  pruefung_ok=auftrag.pruefung.get("ok"))
    return auftrag


def als_html(auftrag: KiBerichtsauftrag, text: str | None = None) -> str:
    """Entwurf + Kennzeichnung + Quellen als Inhalt eines ``berichte.Bericht`` (bereinigtes HTML)."""
    text = auftrag.entwurf if text is None else text
    teile = [f"<p><strong>{html.escape(KENNZEICHNUNG)}</strong></p>"]
    for absatz in re.split(r"\n\s*\n", text.strip()):
        teile.append("<p>" + "<br>".join(html.escape(z) for z in absatz.splitlines()) + "</p>")
    if auftrag.fakten:
        teile.append("<p><strong>Quellen</strong></p><ol>")
        teile += [f"<li>{html.escape(f['text'])}</li>" for f in auftrag.fakten]
        teile.append("</ol>")
    return "".join(teile)
