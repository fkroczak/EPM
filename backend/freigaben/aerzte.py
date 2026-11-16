"""Doppelte Ärzte zusammenführen (Menü „Freigaben“, 16.11.2026).

Im Altbestand steht derselbe Arzt oft unterschiedlich („Dr. Heuwing“, „Dr. med. Klaus Heuwing“); nach der Datenpflege
landen beide in der Ärzteliste. ``suchen`` findet Gruppen mit gleichem Namen (ohne Titel, Wortreihenfolge egal),
gleicher Telefonnummer oder gleicher E-Mail und legt je Gruppe einen Vorschlag an. Nach der Freigabe zeigen alle
Zuordnungen der Patienten auf einen Eintrag (mit den gewählten Kontaktdaten); die übrigen werden deaktiviert, nicht
gelöscht. Verworfene Gruppen („keine Dublette“) werden nicht noch einmal vorgeschlagen.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone

from . import lernen
from .datenpflege import ARZT_LAENGE, Veraltet, _name_schluessel, _ziffern
from .models import Arztdublette

FELDER = list(ARZT_LAENGE)
NAMEN = {"name": "Name", "praxis": "Praxis / Klinik", "fachrichtung": "Fachrichtung", "strasse": "Straße", "plz": "PLZ",
         "ort": "Ort", "telefon": "Telefon", "fax": "Fax", "email": "E-Mail"}


def _gruppen(aerzte) -> list[tuple[list[int], list[str]]]:
    """Union-Find über gleiche Merkmale → [(IDs, Gründe)]."""
    eltern = {a.id: a.id for a in aerzte}

    def wurzel(x):
        while eltern[x] != x:
            eltern[x] = eltern[eltern[x]]
            x = eltern[x]
        return x

    gruende: dict[tuple[int, int], set[str]] = {}
    je_merkmal: dict[tuple[str, str], list[int]] = {}
    for a in aerzte:
        name = _name_schluessel(a.name)
        if len(name) >= 4:
            je_merkmal.setdefault(("gleicher Name", name), []).append(a.id)
        tel = _ziffern(a.telefon).lstrip("0")
        if len(tel) >= 6:
            je_merkmal.setdefault(("gleiche Telefonnummer", tel[-8:]), []).append(a.id)
        if a.email:
            je_merkmal.setdefault(("gleiche E-Mail", a.email.lower()), []).append(a.id)
    for (grund, _), ids in je_merkmal.items():
        for i in ids[1:]:
            eltern[wurzel(i)] = wurzel(ids[0])
            gruende.setdefault(tuple(sorted((ids[0], i))), set()).add(grund)
    gruppen: dict[int, list[int]] = {}
    for a in aerzte:
        gruppen.setdefault(wurzel(a.id), []).append(a.id)
    aus = []
    for ids in gruppen.values():
        if len(ids) < 2:
            continue
        g = sorted({gr for paar, gs in gruende.items() if paar[0] in ids for gr in gs})
        aus.append((sorted(ids), g))
    return aus


def suchen() -> int:
    """Neue Dubletten-Vorschläge anlegen; offene, deren Gruppe sich geändert hat, werden veraltet. → Zahl neuer."""
    from stammdaten.models import Arzt

    gruppen = _gruppen(list(Arzt.objects.filter(aktiv=True).only("id", "name", "telefon", "email")))
    schluessel = {",".join(map(str, ids)): (ids, g) for ids, g in gruppen}
    Arztdublette.objects.filter(status=Arztdublette.Status.OFFEN).exclude(schluessel__in=schluessel).update(
        status=Arztdublette.Status.VERALTET, erledigt_am=timezone.now())
    bekannt = set(Arztdublette.objects.filter(schluessel__in=schluessel, status__in=["offen", "verworfen"])
                  .values_list("schluessel", flat=True))
    neu = [Arztdublette(schluessel=k, aerzte=ids, gruende=g) for k, (ids, g) in schluessel.items() if k not in bekannt]
    Arztdublette.objects.bulk_create(neu)
    return len(neu)


def darstellung(d: Arztdublette) -> dict:
    from stammdaten.models import Arzt

    aerzte = list(Arzt.objects.filter(pk__in=d.aerzte).annotate(
        patienten=Count("zuordnungen", filter=Q(zuordnungen__aktiv=True))).order_by("id"))
    # Ziel: der Eintrag mit den meisten Patienten, bei Gleichstand der älteste
    ziel = max(aerzte, key=lambda a: (a.patienten, -a.id)) if aerzte else None
    werte = {}
    for f in FELDER:
        eigen = getattr(ziel, f) if ziel else ""
        # leere Felder des Ziels aus den anderen füllen (längster Wert, z. B. vollständige Adresse)
        werte[f] = eigen or max((getattr(a, f) or "" for a in aerzte), key=len, default="")
    return {"id": d.id, "art": "aerzte", "gruende": d.gruende, "erstellt_am": d.erstellt_am,
            "aerzte": [{"id": a.id, "patienten": a.patienten, "aktiv": a.aktiv,
                        **{f: getattr(a, f) or "" for f in FELDER}} for a in aerzte],
            "ziel": ziel.id if ziel else None, "werte": werte, "felder": NAMEN,
            "aktuell": len(aerzte) == len(d.aerzte) and all(a.aktiv for a in aerzte)}


def uebernehmen(d: Arztdublette, eingabe: dict) -> dict:
    """Ziel und Werte aus der Oberfläche prüfen → {ziel, werte}."""
    from django.core.validators import validate_email

    eingabe = eingabe if isinstance(eingabe, dict) else {}
    vorschlag = darstellung(d)
    ziel = eingabe.get("ziel", vorschlag["ziel"])
    if not isinstance(ziel, int) or ziel not in d.aerzte:
        raise ValidationError({"ziel": "Bitte den Eintrag wählen, der bleiben soll."})
    werte, fehler = dict(vorschlag["werte"]), {}
    for f, grenze in ARZT_LAENGE.items():
        if f in (eingabe.get("werte") or {}):
            werte[f] = str(eingabe["werte"][f] or "").strip()
            if len(werte[f]) > grenze:
                fehler[f"werte.{f}"] = f"Höchstens {grenze} Zeichen."
    if not werte["name"]:
        fehler["werte.name"] = "Bitte einen Namen eingeben."
    if werte["email"]:
        try:
            validate_email(werte["email"])
        except ValidationError:
            fehler["werte.email"] = "Keine gültige E-Mail-Adresse."
    if fehler:
        raise ValidationError(fehler)
    return {"ziel": ziel, "werte": werte}


def umsetzen(d: Arztdublette, daten: dict, user) -> dict:
    """Zuordnungen auf den Ziel-Arzt umhängen, Werte übernehmen, die anderen deaktivieren."""
    from accounts.rechte import NAMEN as RECHTE
    from patienten.models import PatientArzt
    from stammdaten.models import Arzt

    for recht in ("datenpflege_freigeben", "versorger_pflegen"):
        if not user.hat_recht(recht):
            raise PermissionError(f"Dafür fehlt das Recht „{RECHTE[recht]}“.")
    d.refresh_from_db(from_queryset=Arztdublette.objects.select_for_update())
    if d.status != Arztdublette.Status.OFFEN:
        raise ValidationError({"fehler": "Dieser Vorschlag ist nicht mehr offen."})
    aerzte = {a.id: a for a in Arzt.objects.select_for_update().filter(pk__in=d.aerzte)}
    if len(aerzte) != len(d.aerzte) or not all(a.aktiv for a in aerzte.values()):
        raise Veraltet("Die Ärzteliste wurde inzwischen geändert – bitte erneut suchen.")
    ziel = aerzte[daten["ziel"]]
    for f, wert in daten["werte"].items():
        setattr(ziel, f, wert)
    ziel._history_user = user
    ziel.save()
    umgehaengt, doppelt = 0, 0
    andere = [a for a in aerzte.values() if a.id != ziel.id]
    for z in PatientArzt.objects.filter(arzt__in=andere).select_related("patient", "arzt"):
        quelle = z.arzt
        schon = z.aktiv and PatientArzt.objects.filter(patient=z.patient, arzt=ziel, rolle=z.rolle, aktiv=True).exists()
        if z.patient.ist_abgeschlossen:
            # abgeschlossene Akten sind schreibgeschützt: nur der Verweis auf den Arzt wird umgestellt (ohne Verlauf)
            PatientArzt.objects.filter(pk=z.pk).update(arzt=ziel, aktiv=z.aktiv and not schon)
        else:
            z.arzt, z._history_user = ziel, user
            if schon:
                z.aktiv = False
                z.notiz = (z.notiz + " · doppelt nach Zusammenführung").strip(" ·")[:300]
            z.save()
        umgehaengt += 1
        doppelt += bool(schon)
        # Lernen: Freitexte mit dem Namen des alten Eintrags gehören künftig zum Ziel
        lernen.merken("arzt", _name_schluessel(quelle.name), str(quelle.id), str(ziel.id), user)
    for a in andere:
        a.aktiv = False
        a.notiz = (f"{a.notiz}\nZusammengeführt in „{ziel.name}“ (Nr. {ziel.id}) am "
                   f"{timezone.localdate():%d.%m.%Y}").strip()
        a._history_user = user
        a.save()
        lernen.merken("arzt", _name_schluessel(a.name), str(a.id), str(ziel.id), user)
    d.status, d.erledigt_am, d.erledigt_von = Arztdublette.Status.UMGESETZT, timezone.now(), user
    d.ergebnis = {"ziel": ziel.id, "deaktiviert": [a.id for a in andere], "zuordnungen": umgehaengt,
                  "doppelt": doppelt}
    d.save(update_fields=["status", "erledigt_am", "erledigt_von", "ergebnis"])
    return d.ergebnis
