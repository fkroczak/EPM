"""„Akte auf einen Blick“ (14.11.2026): was seit dem letzten Praxistermin in der Akte dokumentiert wurde.

Gleiches Vorgehen wie der Berichtsentwurf (``ki/berichte.py``):

1. **Zeitraum** – seit dem letzten Praxistermin vor heute; gibt es keinen, seit dem letzten Kontakt; sonst die
   letzten ``zusammenfassung_ohne_termin_tage`` Tage. Bis heute.
2. **Fakten sammeln** – Code, nicht das Modell: nur freigegebene bzw. gültige Inhalte der Akte im Zeitraum, jede
   Tatsache mit Nummer, Quelle und dem Reiter der Akte (``link``), in dem sie steht. Wichtiges zuerst (auffällige
   Laborwerte, Infusionsplan, Medikation …), höchstens ``MAX_FAKTEN``.
3. **Formulieren** – das lokale Modell schreibt kurze Absätze mit Stichwort („Labor:“, „Infusionsplan:“ …) und belegt
   jede Aussage mit [n]. Ohne Modell: die Fakten als Liste.
4. **Gegenprüfen** – ``berichte.gegenpruefen``: Zahlen und Daten nur aus den Fakten, Belege vorhanden, keine
   Bewertung oder Empfehlung.

Die Zusammenfassung ist ein KI-Entwurf zur Orientierung, nie Teil der Akte. Inhalte stehen nie im Audit-Log.
Nachts bereitet die Nachtaufgabe ``zusammenfassung_termine`` die Akten der Patienten mit Termin vor
(``termine_vorbereiten``); tagsüber entsteht sie nur auf Anforderung (Einstellung ``zusammenfassung_tagsueber``).
"""
import datetime as dt
import logging
import time

from django.db.models import Q
from django.utils import timezone

from audit.models import SystemEreignis, protokolliere

from . import prompts
from .berichte import (_d, _z, gegenpruefen, kontakt_datum, kurz, labor_zeit, laborwert_text, medikament_text,
                       plan_teile, plan_text)
from .modell import Client, ModellFehler
from .models import KiEinstellung, KiHinweis, KiModellversion, KiZusammenfassung

log = logging.getLogger("epm.ki")
Z = KiZusammenfassung
MAX_FAKTEN = 150


def termine(heute: dt.date | None = None):
    """Praxistermine, die nicht ausgeblendet sind."""
    from patienten.models import Termin

    heute = heute or timezone.localdate()
    return (Termin.objects.filter(art=Termin.Art.PRAXISTERMIN, ausgeblendet_dauerhaft=False)
            .filter(Q(ausgeblendet_bis__isnull=True) | Q(ausgeblendet_bis__lt=heute)))


def zeitraum(patient, heute: dt.date | None = None, einst: KiEinstellung | None = None) -> tuple[dt.date, str]:
    """→ (von, Herkunft): letzter Praxistermin vor heute, sonst letzter Kontakt, sonst heute − n Tage."""
    from patienten.models import Kontakt

    heute = heute or timezone.localdate()
    t = termine(heute).filter(patient=patient, faellig_am__lt=heute).order_by("-faellig_am").first()
    if t is not None:
        return t.faellig_am, Z.VonGrund.TERMIN
    k = (Kontakt.objects.filter(patient=patient, storniert_am__isnull=True, zeitpunkt__date__lt=heute)
         .order_by("-zeitpunkt").first())
    if k is not None:
        return kontakt_datum(k), Z.VonGrund.KONTAKT
    einst = einst or KiEinstellung.laden()
    return heute - dt.timedelta(days=einst.zusammenfassung_ohne_termin_tage), Z.VonGrund.STANDARD


def _plan_aenderungen(plan) -> str:
    """Änderungen eines Infusionsplans gegenüber seinem Vorgänger (Mengen und Präparate) – nur Tatsachen."""
    alt = plan.vorgaenger
    if alt is None:
        return ""
    from .berichte import PLAN_FELDER

    teile = []
    for f, name, e in PLAN_FELDER:
        a, n = getattr(alt, f), getattr(plan, f)
        if a == n:
            continue
        if a is None:
            teile.append(f"{name} neu {_z(n)} {e}")
        elif n is None:
            teile.append(f"{name} entfällt (bisher {_z(a)} {e})")
        else:
            teile.append(f"{name} {_z(a)} → {_z(n)} {e}")
    vorher = {p.praeparat.name for p in alt.positionen.select_related("praeparat")}
    jetzt = {p.praeparat.name for p in plan.positionen.select_related("praeparat")}
    teile += [f"{n} neu" for n in sorted(jetzt - vorher)] + [f"{n} entfällt" for n in sorted(vorher - jetzt)]
    if not teile:
        return f"Infusionsplan gültig ab {_d(plan.gueltig_ab)}: Mengen wie im Plan ab {_d(alt.gueltig_ab)}"
    return f"Infusionsplan gültig ab {_d(plan.gueltig_ab)}, Änderungen gegenüber dem Plan ab {_d(alt.gueltig_ab)}: " + \
        "; ".join(teile)


def fakten_sammeln(patient, von: dt.date, bis: dt.date) -> list[dict]:
    """Nummerierte Fakten mit Quelle und Reiter der Akte; Wichtiges zuerst."""
    from befunde.models import BiaMessung, Laborwert
    from berichte.models import Bericht
    from faelle.models import Behandlungsfall
    from infusionen.models import Infusionsplan
    from korrespondenz.models import Schreiben
    from patienten.models import Diagnose, Dokument, Gewichtsmessung, Kontakt, Medikament, Therapieschritt

    p, r = patient, (von, bis)
    gruppen: list[list[tuple]] = []  # je Abschnitt: (text, modell, id, datum, link)

    werte = list(Laborwert.objects.filter(befund__patient=p, befund__abgenommen_am__range=r)
                 .select_related("befund", "parameter").order_by("befund__abgenommen_am", "befund_id", "reihenfolge",
                                                                 "id"))
    auffaellig = [w for w in werte if w.ausserhalb]
    normal = [w for w in werte if not w.ausserhalb]
    hoch_tief = {"hoch": "oberhalb", "niedrig": "unterhalb"}

    def labor(w, zusatz=""):
        return (f"Labor {labor_zeit(w.befund)}: {laborwert_text(w)}{zusatz}", "laborwert", w.pk,
                w.befund.abgenommen_am, "labor")

    gruppen.append([labor(w, f", {hoch_tief[w.ausserhalb]} des Referenzbereichs") for w in auffaellig[:40]])

    plaene = []
    for plan in (Infusionsplan.objects.filter(patient=p, gueltig_ab__range=r)
                 .exclude(status=Infusionsplan.Status.ENTWURF).select_related("vorgaenger").order_by("gueltig_ab",
                                                                                                     "id")[:10]):
        if plan_teile(plan):
            plaene.append((plan_text(plan), "infusionsplan", plan.pk, plan.gueltig_ab, "plaene"))
        aenderung = _plan_aenderungen(plan)
        if aenderung:
            plaene.append((aenderung, "infusionsplan", plan.pk, plan.gueltig_ab, "plaene"))
    gruppen.append(plaene)

    medikamente = []
    for m in Medikament.objects.filter(patient=p).filter(
            Q(seit__range=r) | Q(seit__isnull=True, angelegt_am__date__range=r) | Q(abgesetzt_am__range=r)
    ).order_by("seit", "id")[:20]:
        seit = m.seit or timezone.localtime(m.angelegt_am).date()
        if von <= seit <= bis:
            medikamente.append((f"Medikament angesetzt {_d(seit)}: {medikament_text(m)}", "medikament", m.pk, seit,
                                "medikamente"))
        if m.abgesetzt_am and von <= m.abgesetzt_am <= bis:
            grund = f" ({m.absetzgrund})" if m.absetzgrund else ""
            medikamente.append((f"Medikament abgesetzt {_d(m.abgesetzt_am)}: {medikament_text(m)}{grund}",
                                "medikament", m.pk, m.abgesetzt_am, "medikamente"))
    gruppen.append(medikamente)

    diagnosen = []
    for dg in Diagnose.objects.filter(patient=p).filter(
            Q(seit__range=r) | Q(angelegt_am__date__range=r) | Q(beendet_am__range=r)).order_by("angelegt_am",
                                                                                                "id")[:15]:
        neu_am = timezone.localtime(dg.angelegt_am).date()
        if von <= neu_am <= bis or (dg.seit and von <= dg.seit <= bis):
            seit = f", seit {_d(dg.seit)}" if dg.seit else ""
            diagnosen.append((f"Diagnose eingetragen {_d(neu_am)}: {dg.bezeichnung} ({dg.icd_code}){seit}",
                              "diagnose", dg.pk, dg.seit or neu_am, "diagnosen"))
        if dg.beendet_am and von <= dg.beendet_am <= bis:
            diagnosen.append((f"Diagnose beendet {_d(dg.beendet_am)}: {dg.bezeichnung} ({dg.icd_code})", "diagnose",
                              dg.pk, dg.beendet_am, "diagnosen"))
    gruppen.append(diagnosen)

    faelle = []
    for f in Behandlungsfall.objects.filter(patient=p).filter(
            Q(aufnahme__range=r) | Q(entlassung__range=r) | Q(op_datum__range=r)).order_by("aufnahme", "id")[:10]:
        titel = f"Behandlungsfall {f.nummer}" + (f" ({f.titel})" if f.titel else "")
        for feld, wort in (("aufnahme", "Aufnahme"), ("op_datum", "OP"), ("entlassung", "Entlassung")):
            d = getattr(f, feld)
            if d and von <= d <= bis:
                faelle.append((f"{titel}: {wort} am {_d(d)}", "behandlungsfall", f.pk, d, "faelle"))
    gruppen.append(faelle)

    gruppen.append([(f"Gewicht {_d(g.gemessen_am)}: {_z(g.gewicht_kg)} kg ({g.get_quelle_display()})",
                     "gewichtsmessung", g.pk, g.gemessen_am, "kartei")
                    for g in Gewichtsmessung.objects.filter(patient=p, gemessen_am__range=r)
                    .order_by("gemessen_am", "id")[:10]])
    bia = []
    for b in BiaMessung.objects.filter(patient=p, gemessen_am__range=r).order_by("gemessen_am", "id")[:5]:
        teile = [f"{name} {_z(getattr(b, feld))} {e}".strip() for feld, name, e in (
            ("gewicht_kg", "Gewicht", "kg"), ("bcm_kg", "BCM", "kg"), ("fettmasse_kg", "Fettmasse", "kg"),
            ("ecw_prozent", "ECW", "%"), ("koerperwasser_l", "Körperwasser", "l"), ("bmi", "BMI", ""),
            ("phasenwinkel_grad", "Phasenwinkel", "°"))
            if getattr(b, feld) is not None]
        bia.append((f"BIA-Messung {_d(b.gemessen_am)}: " + (", ".join(teile) or "ohne Messwerte"), "bia", b.pk,
                    b.gemessen_am, "bia"))
    gruppen.append(bia)

    gruppen.append([labor(w) for w in normal[:30]])
    gruppen.append([(f"Therapie {_d(t.datum)}: {t.text}", "therapieschritt", t.pk, t.datum, "therapie")
                    for t in Therapieschritt.objects.filter(patient=p, aktiv=True, datum__range=r)
                    .order_by("datum", "id")[:15]])
    kontakte = list(Kontakt.objects.filter(patient=p, storniert_am__isnull=True, zeitpunkt__date__range=r)
                    .select_related("art").order_by("-zeitpunkt", "-id")[:25])
    gruppen.append([(f"Kontakt {_d(kontakt_datum(k))}" + (f" ({k.art.wert})" if k.art_id else "") +
                     f": {kurz(k.text, 300)}", "kontakt", k.pk, kontakt_datum(k), "kontakte")
                    for k in reversed(kontakte)])
    gruppen.append([(f"Bericht freigegeben {_d(timezone.localtime(b.freigegeben_am).date())}: {b.titel}"
                     + (f" ({b.art.wert})" if b.art_id else ""), "bericht", b.pk,
                     timezone.localtime(b.freigegeben_am).date(), "berichte")
                    for b in Bericht.objects.filter(patient=p, status=Bericht.Status.FREIGEGEBEN,
                                                    freigegeben_am__date__range=r)
                    .select_related("art").order_by("freigegeben_am", "id")[:10]])
    gruppen.append([(f"Schreiben versendet {_d(s.versendet_am)}: {s.titel}"
                     + (f" an {s.empfaenger}" if s.empfaenger else "")
                     + (f" ({s.get_versandweg_display()})" if s.versandweg else ""), "schreiben", s.pk,
                     s.versendet_am, "korrespondenz")
                    for s in Schreiben.objects.filter(patient=p, status=Schreiben.Status.VERSENDET,
                                                      versendet_am__range=r).order_by("versendet_am", "id")[:10]])
    gruppen.append([(f"Dokument neu in der Akte {_d(timezone.localtime(d.hochgeladen_am).date())}: {d.titel}"
                     + (f" ({d.typ.wert})" if d.typ_id else ""), "dokument", d.pk,
                     timezone.localtime(d.hochgeladen_am).date(), "dokumente")
                    for d in Dokument.objects.filter(patient=p, ausgeblendet=False, hochgeladen_am__date__range=r)
                    .exclude(herkunft=Dokument.Herkunft.SYSTEM).select_related("typ")
                    .order_by("hochgeladen_am", "id")[:20]])
    gruppen.append([(f"KI-Hinweis {_d(timezone.localtime(h.zeitpunkt).date())}: {h.text}", "kihinweis", h.pk,
                     timezone.localtime(h.zeitpunkt).date(), "ki")
                    for h in KiHinweis.objects.filter(patient=p, zeitpunkt__date__range=r)
                    .exclude(status=KiHinweis.Status.AUSGEBLENDET).order_by("zeitpunkt", "id")[:10]])

    fakten = []
    for text, modell, kennung, datum, link in (x for g in gruppen for x in g):
        if len(fakten) >= MAX_FAKTEN:
            break
        fakten.append({"nr": len(fakten) + 1, "text": text, "quelle": {"modell": modell, "id": kennung},
                       "datum": datum.isoformat() if datum else None, "link": link})
    return fakten


def ohne_modell(von: dt.date, fakten: list[dict]) -> str:
    if not fakten:
        return f"Seit dem {_d(von)} keine neuen Einträge."
    return "\n".join(f"- {f['text']} [{f['nr']}]" for f in fakten)


def erstellen(z: KiZusammenfassung, client: Client | None) -> KiZusammenfassung:
    """Zeitraum bestimmen, Fakten sammeln, formulieren (lassen), gegenprüfen – vom KI-Dienst aufgerufen."""
    t0 = time.monotonic()
    heute = timezone.localdate()
    z.von, z.von_grund = zeitraum(z.patient, heute)
    z.bis = heute
    fakten = fakten_sammeln(z.patient, z.von, z.bis)
    text, mv, z.fehler = "", None, ""
    if client is not None and fakten:
        try:
            a = client.chat(prompts.ZUSAMMENFASSUNG_AKTE, prompts.zusammenfassung_text(_d(z.von), _d(z.bis), fakten),
                            max_tokens=1500, temperatur=0.1)
            text = a.text.strip()
            mv = KiModellversion.aktiv("vision")
        except ModellFehler as e:
            z.fehler = f"KI-Modell nicht verfügbar ({e}) – Zusammenstellung direkt aus den Fakten."
    if not text:
        text = ohne_modell(z.von, fakten)
    z.fakten, z.entwurf = fakten, text
    z.pruefung = gegenpruefen(text, fakten, auch_erlaubt=f"{_d(z.von)} {_d(z.bis)}")
    z.modellversion = mv
    z.prompt_version = prompts.PROMPT_VERSION if text and mv else ""
    z.status, z.fertig_am = Z.Status.FERTIG, timezone.now()
    z.dauer_s = round(time.monotonic() - t0, 1)
    z.save()
    log.info("Akte auf einen Blick %s fertig: %s Fakten, Gegenprüfung %s", z.pk, len(fakten),
             "ok" if z.pruefung.get("ok") else "mit Markierungen")
    protokolliere(SystemEreignis.Art.KI, benutzername="ki-dienst", objekt=f"Akte auf einen Blick {z.pk}",
                  aktion="zusammenfassung_erstellt", patient_id=z.patient_id, grund=z.grund, fakten=len(fakten),
                  modell=mv.name if mv else "", prompt_version=z.prompt_version,
                  pruefung_ok=z.pruefung.get("ok"))
    return z


def termine_vorbereiten(tage_voraus: int = 1, heute: dt.date | None = None) -> int:
    """Nachtaufgabe: je Patient mit Praxistermin zwischen heute und heute + ``tage_voraus`` eine Zusammenfassung
    einreihen – nicht, wenn es für diesen Termin schon eine (fertige oder wartende) gibt oder für die Akte gerade eine
    entsteht. → Zahl eingereihter."""
    heute = heute or timezone.localdate()
    qs = (termine(heute).filter(faellig_am__range=(heute, heute + dt.timedelta(days=tage_voraus)),
                                patient__eingeschraenkt_am__isnull=True, patient__abgeschlossen_am__isnull=True)
          .order_by("faellig_am", "uhrzeit", "id"))
    gesehen, anzahl = set(), 0
    for t in qs:
        if t.patient_id in gesehen:
            continue
        gesehen.add(t.patient_id)
        if Z.objects.filter(termin=t, status__in=[*Z.OFFEN, Z.Status.FERTIG]).exists() or \
                Z.objects.filter(patient_id=t.patient_id, status__in=Z.OFFEN).exists():
            continue
        Z.objects.create(patient_id=t.patient_id, firma_id=t.firma_id, grund=Z.Grund.TERMIN, termin=t)
        anzahl += 1
    return anzahl
