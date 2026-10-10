"""Texterkennung lernt mit (F182): aus den Korrekturen beim Übernehmen.

Beim Zuordnen eines Scans vergleicht EPM, was erkannt wurde, mit dem, was die Pflegekraft übernommen hat:

- erkannte Bezeichnung → gewählter Laborparameter, BIA-Feld oder Diagnose (mit ICD-Code),
- korrigierte Lesefehler in Bezeichnungen („Kreatimin“ → Kreatinin, „Kurzdarmsyndorm“ → Kurzdarmsyndrom),
- je Absender (Labor) die Spaltenlage der Werte.

Gespeichert wird das je Absender und allgemein (``GelernteZuordnung``). Die nächste Auswertung nutzt es vor der
Ähnlichkeitssuche – ab ``auswertung.SCHWELLE`` Bestätigungen als sicher, darunter nur als Vorschlag mit dem Hinweis
„gelernt“. In die Akte kommt weiterhin nichts ohne Bestätigung der Pflegekraft.

Keine Patientendaten: Gelernt werden nur Bezeichnungen. Werte, Namen, Geburtsdaten, Nummern und alles, was nach einer
Angabe zur Person aussieht, bleiben draußen; Bezeichnungen mit dem Namen des Patienten werden verworfen. Testzugänge
lernen nicht mit (ihre Übungen sollen die Erkennung für alle nicht verändern).

Dazu die Kennzahl „Wie oft musste korrigiert werden“ (``KorrekturZaehler``): je Monat, wie viele erkannte Werte
übernommen wurden und wie viele davon geändert oder von Hand ergänzt werden mussten.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import GelernteZuordnung, KorrekturZaehler, LernEinstellung
from .ocr import auswertung

G = GelernteZuordnung.Art


def schwelle() -> int:
    """Ab so vielen Bestätigungen gilt eine gelernte Zuordnung als sicher (Steuerung, 1–3; Standard 2). Ab derselben
    Zahl kommen Bezeichnungen in die Wörterliste für Tesseract."""
    return max(1, min(3, LernEinstellung.aktuell().schwelle))


def pausiert() -> bool:
    """„Lernen pausieren“ (F189): nichts Neues lernen; Gelerntes wird weiter angewandt, die Kennzahl weiter gezählt."""
    return LernEinstellung.aktuell().pausiert

# Wörter, die auf Angaben zur Person hindeuten – solche Bezeichnungen werden nie gelernt
_PERSON = {"patient", "patientin", "name", "vorname", "nachname", "geb", "geboren", "geburtsdatum", "herr", "herrn",
           "frau", "strasse", "str", "telefon", "tel", "versicherter", "versicherte", "versichertennr", "kasse",
           "krankenkasse", "anschrift", "adresse", "plz", "wohnort", "email", "mail"}
_DATUM = re.compile(r"\d{1,2}\s?[.\-/]\s?\d{1,2}\s?[.\-/]\s?\d{2,4}")


# ---------------------------------------------------------------- Lesen für die Auswertung
def gelerntes() -> auswertung.Gelerntes:
    """Alle gelernten Zuordnungen für ``auswertung.auswerten`` (eine Abfrage)."""
    eintraege, gesperrt, spalten, ignorieren, bereiche = {}, set(), {}, set(), {}
    n = schwelle()
    for g in GelernteZuordnung.objects.only("art", "quelle", "erkannt", "ziel", "ziel_text", "bestaetigt", "gesperrt",
                                            "spalte_x", "spalte_zeichen", "bereich").iterator():
        if g.gesperrt:
            gesperrt.add((g.art, g.quelle, g.erkannt, g.ziel))
            continue
        if g.art == G.SPALTE:
            if g.quelle and g.spalte_x and g.spalte_zeichen and g.bestaetigt >= n:
                spalten[g.quelle] = (g.spalte_x, g.spalte_zeichen)
            continue
        if g.art == G.IGNORIEREN:
            # ausdrücklich angemerkt – gilt sofort (eine Anmerkung reicht)
            if g.bestaetigt >= 1:
                ignorieren.add((g.quelle, g.erkannt))
            continue
        if g.art == G.BEREICH:
            if g.quelle and isinstance(g.bereich, list) and len(g.bereich) == 4 and g.bestaetigt >= n:
                bereiche.setdefault(g.quelle, []).append(g.bereich)
            continue
        eintraege.setdefault((g.art, g.quelle, g.erkannt), []).append((g.ziel, g.ziel_text, g.bestaetigt))
    return auswertung.Gelerntes(eintraege, gesperrt, spalten, ignorieren, bereiche, n)


def woerter() -> set[str]:
    """Häufig bestätigte Bezeichnungen für die Wörterliste von Tesseract (``--user-words``) – ohne Lesefehler."""
    aus = set()
    qs = GelernteZuordnung.objects.filter(gesperrt=False, lesefehler=False, bestaetigt__gte=schwelle()).filter(
        art__in=[G.LABOR, G.BIA, G.DIAGNOSE])
    for anzeige, ziel_text, art in qs.values_list("erkannt_anzeige", "ziel_text", "art"):
        text = ziel_text if art == G.DIAGNOSE else anzeige
        for teil in re.split(r"[\s()\[\],;:/]+", text or ""):
            if len(teil) >= 3 and any(c.isalpha() for c in teil) and not any(c.isdigit() for c in teil):
                aus.add(teil)
    return aus


# ---------------------------------------------------------------- Prüfen, ob eine Bezeichnung gelernt werden darf
def _namensteile(patient) -> set[str]:
    teile = set()
    for feld in ("nachname", "vorname", "geburtsname"):
        teile.update(t for t in auswertung.norm(getattr(patient, feld, "") or "").split() if len(t) >= 3)
    return teile


def zulaessig(text: str, patient=None, namen: set | None = None) -> bool:
    """Darf diese Bezeichnung gelernt werden? Nein bei Datum, langen Zahlen, Wörtern zur Person, dem Namen des
    Patienten oder sehr langen Texten (dann ist es keine Bezeichnung)."""
    if not text or len(text) > 80 or _DATUM.search(text) or re.search(r"\d{5,}", text):
        return False
    n = auswertung.norm(text)
    if not n or not re.search(r"[a-z]{2}", n):
        return False
    teile = set(n.split())
    if teile & _PERSON:
        return False
    if patient is not None and teile & _namensteile(patient):
        return False
    if namen and teile & {t for t in namen if len(t) >= 3}:
        return False   # im Dokument als Name gelesen (F183-Hinweise)
    return True


# ---------------------------------------------------------------- Schreiben
def _merken(art: str, quelle: str, quelle_anzeige: str, erkannt: str, ziel: str, user, *, ziel_text: str = "",
            parameter=None, lesefehler: bool = False, nur_quelle: bool = False):
    """Eine Zuordnung je Absender und allgemein bestätigen (anlegen oder hochzählen). ``nur_quelle``: nur für diesen
    Absender (ohne Absender allgemein)."""
    n = auswertung.norm(erkannt)[:200]
    if not n or not ziel:
        return
    jetzt = timezone.now()
    if nur_quelle:
        ziele = {(quelle, quelle_anzeige)}
    else:
        ziele = {(quelle, quelle_anzeige), ("", "")} if quelle else {("", "")}
    for q, q_anzeige in ziele:
        g, neu = GelernteZuordnung.objects.get_or_create(
            art=art, quelle=q, erkannt=n, ziel=str(ziel)[:40],
            defaults={"quelle_anzeige": q_anzeige[:150], "erkannt_anzeige": erkannt[:200], "ziel_text": ziel_text[:200],
                      "parameter": parameter, "lesefehler": lesefehler, "bestaetigt": 1, "zuletzt_am": jetzt,
                      "zuletzt_von": user})
        if not neu:
            GelernteZuordnung.objects.filter(pk=g.pk).update(
                bestaetigt=F("bestaetigt") + 1, zuletzt_am=jetzt, zuletzt_von=user,
                ziel_text=ziel_text[:200] or g.ziel_text, lesefehler=g.lesefehler or lesefehler)


def _widersprechen(art: str, quelle: str, erkannt: str, ziel: str):
    """Die Pflegekraft hat eine gelernte Zuordnung nicht übernommen: eine Bestätigung weniger (bei 0 entfällt sie)."""
    n = auswertung.norm(erkannt)[:200]
    qs = GelernteZuordnung.objects.filter(art=art, quelle__in={quelle, ""}, erkannt=n, ziel=str(ziel), gesperrt=False)
    qs.filter(bestaetigt__gt=0).update(bestaetigt=F("bestaetigt") - 1)
    qs.filter(bestaetigt__lte=0).delete()


def _spalte_merken(quelle: str, quelle_anzeige: str, lagen: list[tuple[float, float]], user):
    """Spaltenlage der Werte für diesen Absender: Mittel der bestätigten Werte (gleitend über die Zuordnungen)."""
    if not quelle or len(lagen) < 3:
        return
    xs = sorted(x for x, _ in lagen)
    zs = sorted(z for _, z in lagen)
    x, z = xs[len(xs) // 2], zs[len(zs) // 2]
    # nur, wenn die Werte wirklich untereinander stehen (linksbündig)
    if sum(1 for v in xs if abs(v - x) <= 0.5 * z) < 0.7 * len(xs):
        return
    g, neu = GelernteZuordnung.objects.get_or_create(
        art=G.SPALTE, quelle=quelle, erkannt="wertspalte", ziel="",
        defaults={"quelle_anzeige": quelle_anzeige[:150], "erkannt_anzeige": "Spalte der Werte", "spalte_x": x,
                  "spalte_zeichen": z, "bestaetigt": 1, "zuletzt_von": user})
    if not neu and not g.gesperrt:
        n = g.bestaetigt
        g.spalte_x = ((g.spalte_x or x) * n + x) / (n + 1)
        g.spalte_zeichen = ((g.spalte_zeichen or z) * n + z) / (n + 1)
        g.bestaetigt = n + 1
        g.zuletzt_am, g.zuletzt_von = timezone.now(), user
        g.save(update_fields=["spalte_x", "spalte_zeichen", "bestaetigt", "zuletzt_am", "zuletzt_von"])


def _zahl(v) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _gleich_zahl(a, b) -> bool:
    za, zb = _zahl(a), _zahl(b)
    return za == zb if (za is not None or zb is not None) else True


def _index(liste, i):
    try:
        i = int(i)
    except (TypeError, ValueError):
        return None
    return liste[i] if 0 <= i < len(liste) else None


def _zaehlen(zahlen: dict[str, list[int]]):
    monat = timezone.localdate().replace(day=1)
    for art, (uebernommen, korrigiert) in zahlen.items():
        if not uebernommen:
            continue
        z, _ = KorrekturZaehler.objects.get_or_create(monat=monat, art=art)
        KorrekturZaehler.objects.filter(pk=z.pk).update(uebernommen=F("uebernommen") + uebernommen,
                                                        korrigiert=F("korrigiert") + korrigiert)


@transaction.atomic
def aus_zuordnung(scan, daten: dict, user, patient=None) -> dict:
    """Nach dem Übernehmen (in derselben Transaktion): lernen und zählen. ``daten`` ist der Auftrag des Zuordnens mit
    ``herkunft`` = {"labor": [{"index": i | null, "stelle": {seite, box} | null}, …] (parallel zu labor.werte),
    "bia": {feld: {seite, box} | null}, "diagnosen": [i | null, …] (parallel zu diagnosen)}.

    → {"gelernt": Anzahl, "zahlen": {art: [übernommen, korrigiert]}}"""
    a = scan.auswertung or {}
    herkunft = daten.get("herkunft") if isinstance(daten.get("herkunft"), dict) else {}
    zaehlt = not getattr(user, "ist_test", False)
    lernt = zaehlt and not pausiert()
    absender = str((a.get("labor") or {}).get("name") or "")
    quelle = auswertung.norm(absender)[:150]
    reihen = None

    def reihen_():
        nonlocal reihen
        if reihen is None:
            seiten = list(scan.seiten.order_by("nr", "id"))
            reihen = auswertung.reihen_aus([s.ergebnis if s.ergebnis else {"reihen": []} for s in seiten])
        return reihen

    gelernt = 0
    zahlen = {"labor": [0, 0], "bia": [0, 0], "diagnose": [0, 0]}

    # ------------------------------------------------ Labor
    labor = daten.get("labor") if isinstance(daten.get("labor"), dict) else None
    if labor:
        erkannte = (a.get("labor") or {}).get("werte") or []
        herk = herkunft.get("labor") if isinstance(herkunft.get("labor"), list) else []
        lagen, bereiche_bestaetigt = [], []
        from stammdaten.models import Laborparameter

        for i, w in enumerate(labor.get("werte") or []):
            if not isinstance(w, dict):
                continue
            h = herk[i] if i < len(herk) and isinstance(herk[i], dict) else {}
            q = _index(erkannte, h.get("index"))
            param = w.get("parameter")
            param = str(param) if param not in (None, "") else ""
            korrigiert = (q is None or str(q.get("parameter") or "") != param
                          or not _gleich_zahl(q.get("wert"), w.get("wert"))
                          or (q.get("wert_text") or "").strip() != (w.get("wert_text") or "").strip()
                          or (q.get("einheit") or "") != (w.get("einheit") or (q.get("einheit") or "")))
            zahlen["labor"][0] += 1
            zahlen["labor"][1] += int(korrigiert)
            if q is not None and not korrigiert and q.get("wert_x") and q.get("wert_zeichen"):
                lagen.append((float(q["wert_x"]), float(q["wert_zeichen"])))
            if q is not None and param and str(q.get("parameter") or "") == param and isinstance(q.get("bereich"), list):
                bereiche_bestaetigt.append(tuple(q["bereich"]))
            if not lernt or not param:
                continue
            p = Laborparameter.objects.filter(pk=param).first()
            if p is None:
                continue
            if q is not None:
                etikett, art = q.get("erkannt_als") or "", q.get("zuordnung") or ""
                vorher = str(q.get("parameter") or "")
                if vorher and vorher != param and art in ("gelernt", "gelernt_vorschlag"):
                    _widersprechen(G.LABOR, quelle, etikett, vorher)
                if art == "genau" and vorher == param:
                    continue  # schon bekannt (Katalog, Suchbegriffe) – nichts zu lernen
                lesefehler = art == "aehnlich" and vorher == param
            else:
                stelle = h.get("stelle") if isinstance(h.get("stelle"), dict) else None
                etikett = auswertung.etikett_an(reihen_(), int(stelle.get("seite") or 0),
                                                stelle.get("box")) if stelle else ""
                lesefehler = False
            if etikett and zulaessig(etikett, patient):
                _merken(G.LABOR, quelle, absender, etikett, param, user, ziel_text=p.name, parameter=p,
                        lesefehler=lesefehler)
                gelernt += 1
        if lernt:
            _spalte_merken(quelle, absender, lagen, user)
            # markierte Bereiche, aus denen Werte übernommen wurden: dort sucht der OCR-Dienst beim nächsten Befund
            for box in set(bereiche_bestaetigt):
                bereich_merken(quelle, absender, list(box), user)

    # ------------------------------------------------ BIA
    bia = daten.get("bia") if isinstance(daten.get("bia"), dict) else None
    if bia:
        erkannte = ((a.get("bia") or {}).get("werte") or {})
        stellen = herkunft.get("bia") if isinstance(herkunft.get("bia"), dict) else {}
        for feld in auswertung.BIA_FELDER:
            if bia.get(feld) in (None, ""):
                continue
            q = erkannte.get(feld)
            korrigiert = q is None or not _gleich_zahl(q.get("wert"), bia.get(feld))
            zahlen["bia"][0] += 1
            zahlen["bia"][1] += int(korrigiert)
            if not lernt:
                continue
            etikett = ""
            if q is not None and q.get("zuordnung") in ("gelernt", "gelernt_vorschlag"):
                etikett = q.get("erkannt_als") or ""   # gelernte Bezeichnung bestätigt
            elif q is None and isinstance(stellen.get(feld), dict):
                st = stellen[feld]
                etikett = auswertung.etikett_an(reihen_(), int(st.get("seite") or 0), st.get("box"))
            if etikett and zulaessig(etikett, patient):
                _merken(G.BIA, quelle, absender, etikett, feld, user, ziel_text=feld)
                gelernt += 1

    # ------------------------------------------------ Diagnosen
    diagnosen = daten.get("diagnosen") if isinstance(daten.get("diagnosen"), list) else []
    if diagnosen:
        erkannte = a.get("diagnosen") or []
        herk = herkunft.get("diagnosen") if isinstance(herkunft.get("diagnosen"), list) else []
        for i, d in enumerate(diagnosen):
            if not isinstance(d, dict):
                continue
            q = _index(erkannte, herk[i] if i < len(herk) else None)
            bez, code = str(d.get("bezeichnung") or "").strip(), str(d.get("icd_code") or "").strip()
            geaendert = q is None or q.get("bezeichnung") != bez or q.get("icd_code") != code
            korrigiert = geaendert or q.get("kennzeichen") != d.get("kennzeichen")
            zahlen["diagnose"][0] += 1
            zahlen["diagnose"][1] += int(korrigiert)
            if not lernt or q is None:
                continue
            erkannt = q.get("erkannt_als") or q.get("bezeichnung") or ""
            erkannt_code = q.get("erkannt_code") or q.get("icd_code") or ""
            art = q.get("zuordnung") or ""
            if art == "gelernt" and geaendert:
                _widersprechen(G.DIAGNOSE, quelle, erkannt, q.get("icd_code") or "")
            if art == "gelernt_vorschlag" and (q.get("gelernt") or {}).get("bezeichnung") != bez:
                _widersprechen(G.DIAGNOSE, quelle, erkannt, (q.get("gelernt") or {}).get("icd_code") or "")
            # gelernt wird nur eine echte Korrektur (Bezeichnung oder Code anders als gelesen)
            korrektur = auswertung.norm(erkannt) != auswertung.norm(bez) or erkannt_code != code
            if korrektur and bez and code and zulaessig(erkannt, patient) and zulaessig(bez, patient):
                _merken(G.DIAGNOSE, quelle, absender, erkannt, code, user, ziel_text=bez,
                        lesefehler=auswertung.norm(erkannt) != auswertung.norm(bez))
                gelernt += 1

    if zaehlt:
        _zaehlen(zahlen)
    return {"gelernt": gelernt, "zahlen": zahlen}


# ---------------------------------------------------------------- F189: Bereich und „falsch erkannt“
def _ueberdeckung(a, b) -> float:
    """Anteil der Überdeckung zweier Rahmen (Schnitt durch Vereinigung)."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    schnitt = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    verein = a[2] * a[3] + b[2] * b[3] - schnitt
    return schnitt / verein if verein > 0 else 0.0


def bereich_merken(quelle: str, quelle_anzeige: str, box: list, user):
    """Bereich der Werte für diesen Absender bestätigen: ähnlicher Bereich → hochzählen und mitteln, sonst neu.
    Ohne Absender wird nichts gelernt (ein Bereich gilt nur für ein Layout)."""
    if not quelle or len(box) != 4:
        return
    box = [round(float(v), 4) for v in box]
    for eintrag in GelernteZuordnung.objects.filter(art=G.BEREICH, quelle=quelle):
        if isinstance(eintrag.bereich, list) and _ueberdeckung(eintrag.bereich, box) >= 0.5:
            if eintrag.gesperrt:
                return
            n = eintrag.bestaetigt
            eintrag.bereich = [round((a * n + b) / (n + 1), 4) for a, b in zip(eintrag.bereich, box)]
            eintrag.bestaetigt = n + 1
            eintrag.zuletzt_am, eintrag.zuletzt_von = timezone.now(), user
            eintrag.save(update_fields=["bereich", "bestaetigt", "zuletzt_am", "zuletzt_von"])
            return
    nr = GelernteZuordnung.objects.filter(art=G.BEREICH, quelle=quelle).count() + 1
    GelernteZuordnung.objects.create(art=G.BEREICH, quelle=quelle, quelle_anzeige=quelle_anzeige[:150],
                                     erkannt=f"bereich {nr}", erkannt_anzeige=f"Bereich {nr} der Werte", ziel=f"b{nr}",
                                     bereich=box, bestaetigt=1, zuletzt_von=user)


GRUENDE = {"falsche_zeile": "falsche Zeile", "falscher_wert": "falscher Wert", "gehoert_nicht_dazu": "gehört nicht dazu"}


def _sperren(art: str, quelle: str, quelle_anzeige: str, erkannt: str, ziel: str, user):
    """Für diesen Absender (ohne Absender: allgemein) „nie wieder so zuordnen“."""
    n = auswertung.norm(erkannt)[:200]
    if not n or not ziel:
        return
    eintrag, neu = GelernteZuordnung.objects.get_or_create(
        art=art, quelle=quelle, erkannt=n, ziel=str(ziel)[:40],
        defaults={"quelle_anzeige": quelle_anzeige[:150], "erkannt_anzeige": erkannt[:200], "gesperrt": True,
                  "zuletzt_von": user})
    if not neu and not eintrag.gesperrt:
        GelernteZuordnung.objects.filter(pk=eintrag.pk).update(gesperrt=True, zuletzt_am=timezone.now(),
                                                               zuletzt_von=user)


@transaction.atomic
def falsch_erkannt(scan, art: str, index, grund: str, user) -> dict:
    """„Falsch erkannt“ (F189): Vorschlag verwerfen (bleibt im Scan als verworfen markiert) und daraus lernen.

    - gehört nicht dazu (Kopfzeile, Referenzbereich, Datum …): die Bezeichnung wird für diesen Absender nicht mehr
      ausgewertet (``IGNORIEREN``);
    - falsche Zeile (die Bezeichnung gehört nicht zu diesem Laborwert/Feld): eine gelernte Zuordnung verliert eine
      Bestätigung; eine nur ähnlich geratene wird für diesen Absender gesperrt;
    - falscher Wert (Zahl falsch gelesen): nichts zu lernen, nur gezählt.
    Keine Patientendaten: nur die Bezeichnung, und nur, wenn sie nichts zur Person enthält.
    → {"gelernt": "ignorieren" | "widersprochen" | "gesperrt" | "", "art": …}"""
    if grund not in GRUENDE:
        raise ValueError("Bitte einen Grund wählen.")
    a = dict(scan.auswertung or {})
    absender = str((a.get("labor") or {}).get("name") or "")
    quelle = auswertung.norm(absender)[:150]
    namen = set(((a.get("patient") or {}).get("namen")) or [])
    if art == "labor":
        liste = (a.get("labor") or {}).get("werte") or []
        try:
            q = liste[int(index)]
        except (TypeError, ValueError, IndexError):
            raise ValueError("Diese Zeile gibt es nicht (mehr).") from None
        etikett, ziel = q.get("erkannt_als") or "", str(q.get("parameter") or "")
        lernart = G.LABOR
    elif art == "bia":
        werte = (a.get("bia") or {}).get("werte") or {}
        q = werte.get(str(index))
        if q is None:
            raise ValueError("Diesen Wert gibt es nicht (mehr).")
        etikett, ziel = q.get("erkannt_als") or "", str(index)
        lernart = G.BIA
    elif art == "diagnose":
        liste = a.get("diagnosen") or []
        try:
            q = liste[int(index)]
        except (TypeError, ValueError, IndexError):
            raise ValueError("Diese Diagnose gibt es nicht (mehr).") from None
        etikett, ziel = q.get("erkannt_als") or q.get("bezeichnung") or "", q.get("icd_code") or ""
        lernart = G.DIAGNOSE
    else:
        raise ValueError("Unbekannte Art.")
    q["verworfen"] = grund
    from .models import Scan

    Scan.objects.filter(pk=scan.pk).update(auswertung=a)
    scan.auswertung = a
    ergebnis = ""
    zaehlt = not getattr(user, "ist_test", False)
    if zaehlt and not pausiert() and zulaessig(etikett, None, namen):
        zuordnung = q.get("zuordnung") or ""
        if grund == "gehoert_nicht_dazu":
            _merken(G.IGNORIEREN, quelle, absender, etikett, "ignorieren", user, ziel_text=GRUENDE[grund],
                    nur_quelle=True)
            ergebnis = "ignorieren"
        elif grund == "falsche_zeile" and ziel:
            if zuordnung in ("gelernt", "gelernt_vorschlag"):
                _widersprechen(lernart, quelle, etikett, ziel)
                ergebnis = "widersprochen"
            elif zuordnung == "aehnlich" or lernart == G.BIA:
                _sperren(lernart, quelle, absender, etikett, ziel, user)
                ergebnis = "gesperrt"
    if zaehlt:
        monat = timezone.localdate().replace(day=1)
        z, _ = KorrekturZaehler.objects.get_or_create(monat=monat, art=art)
        KorrekturZaehler.objects.filter(pk=z.pk).update(verworfen=F("verworfen") + 1)
    return {"gelernt": ergebnis, "art": art}


# ---------------------------------------------------------------- Kennzahl
def kennzahl(monate: int = 12, heute: date | None = None) -> dict:
    """Anteil der übernommenen Werte, die korrigiert werden mussten – je Monat (älteste zuerst) und je Art."""
    heute = heute or timezone.localdate()
    start = heute.replace(day=1)
    liste = []
    for _ in range(monate):
        liste.insert(0, start)
        start = (start.replace(day=1) - timedelta(days=1)).replace(day=1)
    zaehler = {(z.monat, z.art): z for z in KorrekturZaehler.objects.filter(monat__gte=liste[0])}
    aus = []
    for m in liste:
        arten = {}
        summe_u = summe_k = summe_v = 0
        for art in ("labor", "bia", "diagnose"):
            z = zaehler.get((m, art))
            u, k, v = (z.uebernommen, z.korrigiert, z.verworfen) if z else (0, 0, 0)
            summe_u, summe_k, summe_v = summe_u + u, summe_k + k, summe_v + v
            arten[art] = {"uebernommen": u, "korrigiert": k, "verworfen": v,
                          "anteil": round(100 * k / u, 1) if u else None}
        aus.append({"monat": m.isoformat(), "uebernommen": summe_u, "korrigiert": summe_k, "verworfen": summe_v,
                    "anteil": round(100 * summe_k / summe_u, 1) if summe_u else None, "arten": arten})
    aktuell, vorher = aus[-1], aus[-2] if len(aus) > 1 else None
    trend = None
    if aktuell["anteil"] is not None and vorher and vorher["anteil"] is not None:
        trend = round(aktuell["anteil"] - vorher["anteil"], 1)
    return {"monate": aus, "aktuell": aktuell, "vormonat": vorher, "trend": trend,
            "gelernt": GelernteZuordnung.objects.filter(gesperrt=False).exclude(art=G.SPALTE).count(),
            "schwelle": schwelle(), "pausiert": pausiert()}


# ---------------------------------------------------------------- Leeren
def leeren() -> int:
    """Alles Gelernte und die Kennzahl entfernen (für „Datenbank leeren“). → Zahl der gelernten Zuordnungen."""
    anzahl = GelernteZuordnung.objects.count()
    GelernteZuordnung.objects.all().delete()
    KorrekturZaehler.objects.all().delete()
    return anzahl
