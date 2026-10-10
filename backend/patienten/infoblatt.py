"""
Infoblatt an die Praxis (F177, baut auf der Patientenankündigung F173 auf).

Zu einem festen Zeitpunkt bekommt die Praxis Dr. Holtmeier ein Blatt mit allen Patienten, die in den nächsten Tagen
dort einen Sprechstundentermin haben. Grundlage sind die Praxistermine im Kalender:

- Ist ein Terminort gewählt, stehen nur die Praxistermine an diesem Ort auf dem Blatt; Telefon- und Videotermine auf
  Wunsch zusätzlich (mit Telefonnummer). Praxistermine ohne Ort fehlen auf dem Blatt und erscheinen in der Vorschau
  als Warnung, damit der Ort nachgetragen wird. Ohne gewählten Ort stehen alle Praxistermine darauf (wie bei F173).
- Jedes erzeugte Blatt (PDF oder E-Mail) wird mit einem Schnappschuss gemerkt (``Ankuendigung``: nur Nummer, Datum,
  Uhrzeit der Termine). Die Vorschau markiert danach, was seit dem letzten Blatt für denselben Tag neu ist oder sich
  verschoben hat, und nennt, was nicht mehr darauf steht.
- Die Startseite erinnert rechtzeitig vor dem nächsten Zeitraum (Einstellungen: wöchentlich/monatlich, Vorlauf).
"""
import calendar
from datetime import date, timedelta

from django.db.models import F
from django.utils import timezone

from epm.api_basis import benutzername, patienten_fuer
from stammdaten.models import Auswahlwert, Einstellungen
from vorlagen.felder import ankuendigung_hinweis, ist_telefonort

from .models import Ankuendigung, Termin, sichtbare_termine


def praxisort():
    """Der Terminort der Praxis Dr. Holtmeier (Vorschlag im Dialog und Grundlage der Erinnerung)."""
    return (Auswahlwert.objects.filter(liste=Auswahlwert.Liste.TERMINORT, wert__icontains="holtmeier")
            .order_by("-aktiv", "reihenfolge", "id").first())


def praxistermine(user, von: date, bis: date) -> list:
    """Alle Praxistermine im Zeitraum nach Tag und Uhrzeit – ohne Testpatienten und ohne ausgeblendete Termine."""
    return list(sichtbare_termine(Termin.objects.filter(
        patient__in=patienten_fuer(user).filter(ist_test=False), art=Termin.Art.PRAXISTERMIN,
        faellig_am__range=(von, bis))).select_related("patient", "ort")
        .order_by("faellig_am", F("uhrzeit").asc(nulls_last=True), "id"))


def aufteilen(termine: list, ort, telefon_mit: bool = False) -> tuple[list, list]:
    """→ (Termine auf dem Blatt, Praxistermine ohne Ort). Ohne gewählten Ort stehen alle auf dem Blatt."""
    if ort is None:
        return list(termine), []
    blatt, ohne = [], []
    for t in termine:
        if t.ort_id is None:
            ohne.append(t)
        elif t.ort_id == ort.pk or (telefon_mit and ist_telefonort(t.ort)):
            blatt.append(t)
    return blatt, ohne


def _uhr(t) -> str | None:
    return f"{t.uhrzeit:%H:%M}" if t.uhrzeit else None


def schnappschuss(termine: list) -> list[dict]:
    """Was auf dem Blatt stand – nur Nummer, Datum und Uhrzeit, keine Namen (Art.-17-Löschung bleibt einfach)."""
    return [{"termin": t.id, "datum": t.faellig_am.isoformat(), "uhrzeit": _uhr(t)} for t in termine]


def _gleicher_ort(qs, ort):
    return qs.filter(ort=ort) if ort is not None else qs.filter(ort__isnull=True)


def vergleich(von: date, bis: date, ort, blatt: list, user) -> dict:
    """Vergleich mit den bisherigen Blättern für denselben Ort.

    ``neu``: Termin-Nummern, die an ihrem Tag seit dem letzten Blatt für diesen Tag hinzugekommen sind oder deren Datum
    oder Uhrzeit sich geändert hat (gibt es für den Tag noch kein Blatt, ist nichts „neu“ – dann ist alles neu).
    ``vorher``: bisheriges Datum/Uhrzeit verschobener Termine. ``entfallen``: Termine, die auf dem letzten Blatt
    eines Tages standen und jetzt nicht mehr darauf stehen (abgesagt, verschoben, Ort geändert)."""
    bisher = list(_gleicher_ort(Ankuendigung.objects.filter(von__lte=bis, bis__gte=von), ort)
                  .order_by("-erstellt_am", "-id"))
    # je Tag das zuletzt erstellte Blatt, das diesen Tag umfasst
    je_tag: dict[str, set] = {}
    eintraege_je_tag: dict[str, list] = {}
    tag = von
    while tag <= bis:
        a = next((x for x in bisher if x.von <= tag <= x.bis), None)
        if a is not None:
            schluessel = tag.isoformat()
            eintraege = [e for e in a.termine if isinstance(e, dict) and e.get("datum") == schluessel]
            je_tag[schluessel] = {(e.get("termin"), e.get("uhrzeit")) for e in eintraege}
            eintraege_je_tag[schluessel] = eintraege
        tag += timedelta(days=1)
    zuletzt: dict[int, dict] = {}
    for a in reversed(bisher):   # ältestes zuerst, spätere überschreiben
        for e in a.termine:
            if isinstance(e, dict) and e.get("termin"):
                zuletzt[e["termin"]] = e
    neu, vorher = set(), {}
    for t in blatt:
        schluessel = t.faellig_am.isoformat()
        if schluessel in je_tag and (t.id, _uhr(t)) not in je_tag[schluessel]:
            neu.add(t.id)
            e = zuletzt.get(t.id)
            if e and (e.get("datum"), e.get("uhrzeit")) != (schluessel, _uhr(t)):
                vorher[t.id] = {"datum": e.get("datum"), "uhrzeit": e.get("uhrzeit")}
    auf_blatt = {t.id for t in blatt}
    weg = [e for eintraege in eintraege_je_tag.values() for e in eintraege if e.get("termin") not in auf_blatt]
    namen = {t.id: t for t in Termin.objects.filter(id__in=[e["termin"] for e in weg],
                                                     patient__in=patienten_fuer(user)).select_related("patient")}
    entfallen = []
    for e in sorted(weg, key=lambda e: (e.get("datum") or "", e.get("uhrzeit") or "99")):
        t = namen.get(e["termin"])
        entfallen.append({"termin": e["termin"], "datum": e.get("datum"), "uhrzeit": e.get("uhrzeit"),
                          "patient": t.patient_id if t else None,
                          "name": f"{t.patient.vorname} {t.patient.nachname}" if t else None})
    return {"neu": neu, "vorher": vorher, "entfallen": entfallen}


def letzte(von: date, bis: date, ort) -> dict | None:
    """Das zuletzt erstellte Blatt, das sich mit dem Zeitraum überschneidet (gleicher Ort)."""
    a = (_gleicher_ort(Ankuendigung.objects.filter(von__lte=bis, bis__gte=von), ort).select_related("benutzer")
         .order_by("-erstellt_am", "-id").first())
    if a is None:
        return None
    return {"erstellt_am": a.erstellt_am, "von_name": benutzername(a.benutzer), "von": a.von, "bis": a.bis,
            "anzahl": a.anzahl, "ausgabe": a.ausgabe}


def vorschau(user, von: date, bis: date, ort, telefon_mit: bool) -> dict:
    """Antwort für ``ausgabe: "liste"``: was auf das Blatt kommt, was fehlt, was zuletzt verschickt wurde."""
    blatt, ohne = aufteilen(praxistermine(user, von, bis), ort, telefon_mit)
    v = vergleich(von, bis, ort, blatt, user)

    def zeile(t, hinweis=True):
        z = {"termin": t.id, "patient": t.patient_id, "name": f"{t.patient.vorname} {t.patient.nachname}",
             "datum": t.faellig_am, "uhrzeit": _uhr(t)}
        if hinweis:
            z.update({"hinweis": ankuendigung_hinweis(t, ort) or "", "neu": t.id in v["neu"],
                      "vorher": v["vorher"].get(t.id)})
        return z

    return {"von": von, "bis": bis, "ort": {"id": ort.pk, "wert": ort.wert} if ort is not None else None,
            "telefon_mit": telefon_mit, "anzahl": len(blatt), "termine": [zeile(t) for t in blatt],
            "ohne_ort": [zeile(t, hinweis=False) for t in ohne], "entfallen": v["entfallen"],
            "letzte": letzte(von, bis, ort)}


def merken(user, von: date, bis: date, ort, telefon_mit: bool, ausgabe: str, blatt: list) -> Ankuendigung:
    return Ankuendigung.objects.create(benutzer=user, von=von, bis=bis, ort=ort, telefon_mit=telefon_mit,
                                       ausgabe=ausgabe, anzahl=len(blatt), termine=schnappschuss(blatt))


def naechster_zeitraum(heute: date, rhythmus: str) -> tuple[date, date] | None:
    """Nächste Kalenderwoche (Mo–So) bzw. nächster Kalendermonat; ``aus`` → None."""
    if rhythmus == "woche":
        beginn = heute + timedelta(days=7 - heute.weekday())
        return beginn, beginn + timedelta(days=6)
    if rhythmus == "monat":
        beginn = date(heute.year + (heute.month == 12), heute.month % 12 + 1, 1)
        return beginn, beginn.replace(day=calendar.monthrange(beginn.year, beginn.month)[1])
    return None


def erinnerung(user, heute: date | None = None) -> dict | None:
    """Hinweis auf der Startseite „Praxis … informieren“ (nur mit dem Recht „Einträge erfassen“).

    Erscheint ab (Beginn des nächsten Zeitraums − Vorlauf) bis zum Beginn, solange für den Zeitraum noch kein Blatt
    erstellt ist und dort Termine stehen (auch solche ohne Ort, damit sie nachgetragen werden)."""
    if not user.hat_recht("eintraege_erfassen"):
        return None
    heute = heute or timezone.localdate()
    e = Einstellungen.aktuell()
    zeitraum = naechster_zeitraum(heute, e.infoblatt_rhythmus)
    if zeitraum is None:
        return None
    von, bis = zeitraum
    if heute < von - timedelta(days=e.infoblatt_vorlauf_tage):
        return None
    ort = praxisort()
    blatt, ohne = aufteilen(praxistermine(user, von, bis), ort)
    if not blatt and not ohne:
        return None
    # erledigt, sobald ein Blatt (für diesen Ort oder für alle Orte) die Tage mit Terminen umfasst
    tage = [t.faellig_am for t in blatt] or [von]
    erstellt = Ankuendigung.objects.filter(von__lte=min(tage), bis__gte=max(tage))
    erstellt = erstellt.filter(ort__in=[ort]) | erstellt.filter(ort__isnull=True) if ort is not None else erstellt
    if erstellt.exists():
        return None
    return {"von": von, "bis": bis, "rhythmus": e.infoblatt_rhythmus, "anzahl": len(blatt), "ohne_ort": len(ohne),
            "ort": {"id": ort.pk, "wert": ort.wert} if ort is not None else None}
