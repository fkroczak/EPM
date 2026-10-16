"""
Statistik (F193): anonymisierte Auswertung der Akten für Berichte der Stiftung – Menüpunkt „Statistik“.

GET /api/statistik/        ?art=jahr&jahr=2026 | ?art=quartal&jahr=2026&quartal=3 | ?art=frei&von=2026-01-01&bis=2026-06-30
                           → {firma, zeitraum, vergleich, werte, vorher, regel, hinweise, erstellt_am}
GET /api/statistik/pdf/    gleiche Parameter → PDF mit Briefkopf (vorlagen/listen.py, ``statistik_pdf``), Audit-Log „Export“
GET /api/statistik/csv/    gleiche Parameter → CSV (Semikolon, UTF-8 mit BOM für Excel), Audit-Log „Export“

Recht „Statistik ansehen“ (``statistik_ansehen``; Festlegung 16.10.2026: Standard „Mitarbeiter (erweitert)“, Mediziner
und Admin – Betrachter und Mitarbeiter nicht; je Gruppe umstellbar; Testbenutzer nie).

Welche Akten zählen
- nur Akten der aktiven Firma (Firmenumschaltung oben links, wie Patientenliste und Startseite: ``patienten_fuer``);
- **Testpatienten nie** („Testpatienten zählen in keiner Statistik“) – auch nicht für Personen mit „Testdaten sehen“;
- Akten mit eingeschränkter Verarbeitung (Art. 18 DSGVO) zählen mit, erscheinen aber nie einzeln (es gibt hier keine
  Einzelangaben: keine Namen, Nummern, Geburtsdaten, keine Listen von Akten).

Begriffe (nur vorhandene Felder, kein neues Datenmodell)
- **Beginn der Betreuung** = ``Patient.angelegt_am`` (Tag der Anlage in EPM). Ein eigenes Aufnahmedatum gibt es nicht
  (OFFEN, siehe docs/BACKEND-FUNKTIONEN.md F193). Akten aus dem Altsystem (erste Fassung der Historie mit dem Grund
  „Aus dem Altsystem übernommen …“) tragen als ``angelegt_am`` den Tag des Imports; ihr Beginn ist unbekannt. Sie
  gelten deshalb als „schon vor jedem Zeitraum in Betreuung“ und zählen **nie** als Neuaufnahme.
- **Ende** = ``Patient.abgeschlossen_am`` mit ``abschluss_anlass``.
- **Aktiv zum Stichtag** (Stichtag = Ende des Zeitraums, höchstens heute): Beginn ≤ Stichtag und nicht vor oder am
  Stichtag abgeschlossen.
- **Im Zeitraum betreut**: Beginn ≤ Ende des Zeitraums und nicht vor dem Beginn des Zeitraums abgeschlossen.
- **Neuaufnahmen**: Beginn im Zeitraum (ohne Altsystem-Akten).
- **Abgeschlossen**: ``abgeschlossen_am`` im Zeitraum, aufgeteilt nach Abschlussanlass.
- **Versorger, Katheter**: heutiger Stand der Akte (nicht der Stand am Stichtag – dafür müsste die Historie
  ausgewertet werden; OFFEN), je Akte, die zum Stichtag aktiv ist. „kein …“ = bewusst keiner, „nicht erfasst“ = leer.
- **Altersgruppen**: Alter am Stichtag, Gruppen 0–17, 18–39, 40–59, 60–79, 80+.
- **Kontakte**: nicht stornierte Kontakte mit Zeitpunkt im Zeitraum (Anzahl Kontakte, nicht Personen).
- **Infusionspläne erstellt**: ``erstellt_am`` im Zeitraum (alle Status, auch Entwürfe und übernommene Pläne);
  **freigegeben**: Tag der Freigabe (``freigabe_datum``, sonst ``freigegeben_am``) im Zeitraum.

Schutz kleiner Fallzahlen (k = 5) – ``REGEL``
1. Primär: jede Zelle mit 1 bis 4 Fällen erscheint als „< 5“ (in Antwort, PDF und CSV; der genaue Wert verlässt den
   Server nicht). 0 bleibt 0.
2. Sekundär (Bestand): „aktiv zum Stichtag“, „im Zeitraum betreut“, „Neuaufnahmen“, „abgeschlossen“ und die
   Verteilungen nach Versorger, Alter, Katheter und Abschlussanlass hängen rechnerisch zusammen – innerhalb eines
   Zeitraums (Summen der Verteilungen, betreut ≈ aktiv + abgeschlossen) und über den Vergleich (aktiv jetzt = aktiv im
   Vorzeitraum + Neuaufnahmen − Abschlüsse). Enthält dieser Bestand **in einem der beiden Zeiträumen** eine Zelle
   „< 5“, werden in **beiden** Zeiträumen alle seine Werte ab 5 auf volle 5 gerundet („≈ 20“) – auch die Summen. So
   lässt sich eine „< 5“-Zelle weder aus Summe minus übrige Zellen noch aus der Differenz zum Vorzeitraum zurückrechnen
   (jeder gerundete Wert weicht um bis zu 2 ab, eine Rückrechnung ergibt nur eine Spanne).
3. Eigenständige Zählungen (Kontakte, Infusionspläne erstellt bzw. freigegeben) nur nach Regel 1.
4. Vergleich zum Vorzeitraum: Die Oberfläche bildet Differenzen nur aus den angezeigten Werten; bei „< 5“ entfällt
   die Differenz, bei gerundeten Werten ist sie als ungefähr gekennzeichnet.
Restrisiko (OFFEN, Datenschutz zu bestätigen): Wer viele frei gewählte, sich überlappende Zeiträume abfragt, kann über
Differenzen einzelne Tage eingrenzen (z. B. „eine Neuaufnahme am 31.03.“).
"""
import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import StatistikRecht
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import patienten_fuer

from .models import Kontakt, Patient

K = 5  # kleinste Fallzahl, die genau gezeigt wird
RUNDEN_AUF = 5
# Grund der ersten Fassung übernommener Akten (altimport.umsetzung.GRUND + Zusatz, siehe altimport/dienst.py)
ALTSYSTEM_GRUND = "Aus dem Altsystem übernommen"

ALTERSGRUPPEN = [("0-17", "0–17 Jahre", 0, 17), ("18-39", "18–39 Jahre", 18, 39), ("40-59", "40–59 Jahre", 40, 59),
                 ("60-79", "60–79 Jahre", 60, 79), ("80+", "80 Jahre und älter", 80, 999)]

REGEL = ("Kleine Fallzahlen sind geschützt (k = 5): Werte von 1 bis 4 erscheinen als „< 5“. Enthält der Bestand "
         "(aktiv, betreut, Neuaufnahmen, abgeschlossen und die Verteilungen nach Versorger, Alter, Katheter und "
         "Abschlussanlass) in einem der beiden Zeiträume eine solche Zelle, sind dort in beiden Zeiträumen alle Werte "
         "ab 5 auf volle 5 gerundet („≈“), auch die Summen. Testpatienten zählen nicht; eingeschränkte Akten "
         "(Art. 18 DSGVO) zählen mit, erscheinen aber nie einzeln.")
BESTAND = ("aktiv", "betreut", "neuaufnahmen", "abgeschlossen")

KENNZAHLEN = [("aktiv", "Aktive Patienten zum Stichtag"), ("betreut", "Im Zeitraum betreut"),
              ("neuaufnahmen", "Neuaufnahmen"), ("abgeschlossen", "Abgeschlossene Akten"),
              ("kontakte", "Kontakte"), ("plaene_erstellt", "Infusionspläne erstellt"),
              ("plaene_freigegeben", "Infusionspläne freigegeben")]
VERTEILUNGEN = [("abschlussanlass", "Abgeschlossen nach Anlass"), ("versorger", "Aktive nach Versorger"),
                ("altersgruppen", "Aktive nach Altersgruppe (am Stichtag)"), ("katheter", "Aktive nach Katheter")]


class Eingabefehler(ValueError):
    pass


# ----------------------------------------------------------------------------------------------- Zeitraum
@dataclass
class Zeitraum:
    art: str
    von: date
    bis: date          # Ende des Zeitraums (für Abfragen: höchstens heute)
    ende: date         # Ende laut Wahl (Jahr/Quartal), ggf. nach heute
    titel: str

    @property
    def stichtag(self) -> date:
        return self.bis

    @property
    def laufend(self) -> bool:
        return self.ende > self.bis

    def als_dict(self) -> dict:
        return {"art": self.art, "von": self.von.isoformat(), "bis": self.bis.isoformat(), "ende": self.ende.isoformat(),
                "stichtag": self.stichtag.isoformat(), "titel": self.titel, "laufend": self.laufend}


def _d(tag: date) -> str:
    return f"{tag:%d.%m.%Y}"


def _quartal(jahr: int, q: int) -> tuple[date, date]:
    von = date(jahr, 3 * q - 2, 1)
    naechster = date(jahr + 1, 1, 1) if q == 4 else date(jahr, 3 * q + 1, 1)
    return von, naechster - timedelta(days=1)


def _zahl(params, name, unten, oben, vorgabe=None) -> int:
    try:
        wert = int(str(params.get(name) or (vorgabe if vorgabe is not None else "")).strip())
    except ValueError:
        raise Eingabefehler(f"Bitte {'ein Jahr' if name == 'jahr' else 'ein Quartal (1–4)'} angeben.")
    if not unten <= wert <= oben:
        raise Eingabefehler(f"{'Jahr' if name == 'jahr' else 'Quartal'} {wert} ist nicht möglich ({unten}–{oben}).")
    return wert


def _datum(params, name) -> date:
    text = str(params.get(name, "")).strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise Eingabefehler(f"Bitte „{'von' if name == 'von' else 'bis'}“ als Datum angeben (JJJJ-MM-TT).")


def zeitraeume(params, heute: date | None = None) -> tuple[Zeitraum, Zeitraum]:
    """(gewählter Zeitraum, Vorzeitraum zum Vergleich).

    Vorzeitraum: beim Jahr das ganze Vorjahr, beim Quartal das ganze Vorquartal, bei frei gewählten Daten die gleich
    lange Spanne direkt davor. Liegt das Ende des Zeitraums nach heute (laufendes Jahr bzw. Quartal), endet er heute;
    der Vorzeitraum bleibt vollständig (ANNAHME, offen: alternativ dieselbe Spanne des Vorjahres)."""
    heute = heute or timezone.localdate()
    art = str(params.get("art") or "jahr")
    if art == "jahr":
        jahr = _zahl(params, "jahr", 2000, heute.year, heute.year)
        von, ende = date(jahr, 1, 1), date(jahr, 12, 31)
        titel = str(jahr)
        v_von, v_ende, v_titel = date(jahr - 1, 1, 1), date(jahr - 1, 12, 31), f"Vorjahr {jahr - 1}"
    elif art == "quartal":
        jahr = _zahl(params, "jahr", 2000, heute.year, heute.year)
        q = _zahl(params, "quartal", 1, 4, (heute.month - 1) // 3 + 1)
        von, ende = _quartal(jahr, q)
        titel = f"{q}. Quartal {jahr}"
        vq, vj = (q - 1, jahr) if q > 1 else (4, jahr - 1)
        v_von, v_ende = _quartal(vj, vq)
        v_titel = f"Vorquartal ({vq}. Quartal {vj})"
    elif art == "frei":
        von, ende = _datum(params, "von"), _datum(params, "bis")
        if ende < von:
            raise Eingabefehler("„bis“ liegt vor „von“.")
        if (ende - von).days > 3660:
            raise Eingabefehler("Bitte höchstens zehn Jahre auf einmal auswerten.")
        titel = f"{_d(von)} – {_d(ende)}"
        v_ende = von - timedelta(days=1)
        v_von = v_ende - (ende - von)
        v_titel = f"Vorzeitraum {_d(v_von)} – {_d(v_ende)}"
    else:
        raise Eingabefehler("Zeitraum: bitte Kalenderjahr, Quartal oder frei von–bis wählen.")
    if von > heute:
        raise Eingabefehler("Der Zeitraum liegt in der Zukunft.")
    bis = min(ende, heute)
    if bis < ende:
        titel += f" (bis {_d(bis)})"
    return Zeitraum(art, von, bis, ende, titel), Zeitraum(art, v_von, min(v_ende, heute), v_ende, v_titel)


# ----------------------------------------------------------------------------------------------- Schutz
def gerundet(wert: int) -> int:
    """Auf volle 5 (halbe aufwärts); Werte ab 5 bleiben ab 5."""
    return RUNDEN_AUF * ((wert + RUNDEN_AUF // 2) // RUNDEN_AUF)


def _zahltext(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def zelle(wert: int, runden: bool = False) -> dict:
    """Ein Wert, wie er die Antwort verlässt: ``wert`` ist None, wenn er unterdrückt ist (1–4)."""
    if wert <= 0:
        return {"wert": 0, "anzeige": "0", "status": "exakt"}
    if wert < K:
        return {"wert": None, "anzeige": f"< {K}", "status": "klein"}
    if runden:
        r = gerundet(wert)
        return {"wert": r, "anzeige": f"≈ {_zahltext(r)}", "status": "gerundet"}
    return {"wert": wert, "anzeige": _zahltext(wert), "status": "exakt"}


def muss_runden(*rohwerte: dict) -> bool:
    """Regel 2: Gibt es im Bestand irgendeines der Zeiträume eine Zelle mit 1–4 Fällen?"""
    for r in rohwerte:
        zahlen = [r["kennzahlen"][k] for k in BESTAND]
        for v in VERTEILUNGEN:
            zahlen += [z["anzahl"] for z in r["verteilungen"][v[0]]]
        if any(0 < n < K for n in zahlen):
            return True
    return False


def schuetze(rohwerte: dict, runden: bool) -> dict:
    """Rohzahlen (genau) → geschützte Auswertung nach ``REGEL``. Die Rohzahlen verlassen diese Funktion nicht.
    ``runden``: Ergebnis von ``muss_runden`` über alle gezeigten Zeiträume."""
    kennzahlen = {}
    for schluessel, _ in KENNZAHLEN:
        kennzahlen[schluessel] = zelle(rohwerte["kennzahlen"][schluessel], runden and schluessel in BESTAND)
    verteilungen = {}
    for name, _ in VERTEILUNGEN:
        zeilen = [{"schluessel": z["schluessel"], "text": z["text"], "zelle": zelle(z["anzahl"], runden)}
                  for z in rohwerte["verteilungen"][name]]
        if name == "versorger" or name == "katheter":
            # nach angezeigtem Wert (nicht nach dem genauen – sonst verriete die Reihenfolge der „< 5“-Zeilen mehr),
            # „kein …“ und „nicht erfasst“ zuletzt
            ende = {"kein": 1, "offen": 2}
            zeilen.sort(key=lambda z: (ende.get(z["schluessel"], 0), -(z["zelle"]["wert"] if z["zelle"]["wert"] is not None
                                                                         else 0.5), z["text"].lower()))
        verteilungen[name] = zeilen
    return {"kennzahlen": kennzahlen, "verteilungen": verteilungen, "gerundet": runden}


# ----------------------------------------------------------------------------------------------- Zählen
def _tag(zeitpunkt):
    return timezone.localtime(zeitpunkt).date() if isinstance(zeitpunkt, datetime) else zeitpunkt


def _alter(geburtsdatum: date, stichtag: date) -> int:
    return stichtag.year - geburtsdatum.year - ((stichtag.month, stichtag.day) < (geburtsdatum.month, geburtsdatum.day))


def basis(user):
    """Akten, die in die Statistik eingehen: aktive Firma, ohne Testpatienten, eingeschränkte mitgezählt."""
    bereich = patienten_fuer(user, eingeschraenkte=True).filter(ist_test=False)
    return Patient.objects.filter(id__in=bereich.values("id"), ist_test=False)


def altakten_ids(patienten_qs) -> set:
    """Akten, deren erste Fassung aus dem Altsystem stammt (Beginn der Betreuung unbekannt)."""
    return set(Patient.history.filter(id__in=patienten_qs.values("id"), history_type="+",
                                      history_change_reason__startswith=ALTSYSTEM_GRUND)
               .values_list("id", flat=True))


def _zeilen(patienten_qs) -> list[dict]:
    alt = altakten_ids(patienten_qs)
    zeilen = []
    for p in patienten_qs.values("id", "geburtsdatum", "angelegt_am", "abgeschlossen_am", "abschluss_anlass",
                                 "versorger_id", "versorger__name", "kein_versorger", "katheter_id", "katheter__wert",
                                 "kein_katheter"):
        p["altakte"] = p["id"] in alt
        p["beginn"] = None if p["altakte"] else _tag(p["angelegt_am"])
        zeilen.append(p)
    return zeilen


def _bestand(zeilen: list[dict], z: Zeitraum) -> dict:
    """Kennzahlen des Bestands und Verteilungen für einen Zeitraum (genaue Zahlen, nur intern)."""
    def begonnen(p, tag):
        return p["beginn"] is None or p["beginn"] <= tag

    aktiv = [p for p in zeilen if begonnen(p, z.stichtag) and (p["abgeschlossen_am"] is None
                                                                or p["abgeschlossen_am"] > z.stichtag)]
    betreut = [p for p in zeilen if begonnen(p, z.bis) and (p["abgeschlossen_am"] is None
                                                             or p["abgeschlossen_am"] >= z.von)]
    neu = [p for p in zeilen if p["beginn"] is not None and z.von <= p["beginn"] <= z.bis]
    abgeschlossen = [p for p in zeilen if p["abgeschlossen_am"] is not None and z.von <= p["abgeschlossen_am"] <= z.bis]

    anlass = [{"schluessel": wert, "text": text, "anzahl": sum(1 for p in abgeschlossen if p["abschluss_anlass"] == wert)}
              for wert, text in Patient.Abschlussanlass.choices]

    def zaehle(schluessel_text):
        stand = {}
        for p in aktiv:
            s, t = schluessel_text(p)
            stand.setdefault(s, {"schluessel": s, "text": t, "anzahl": 0})["anzahl"] += 1
        return list(stand.values())

    versorger = zaehle(lambda p: (f"v{p['versorger_id']}", p["versorger__name"]) if p["versorger_id"]
                       else ("kein", "kein Versorger") if p["kein_versorger"] else ("offen", "nicht erfasst"))
    katheter = zaehle(lambda p: (f"k{p['katheter_id']}", p["katheter__wert"]) if p["katheter_id"]
                      else ("kein", "kein Katheter") if p["kein_katheter"] else ("offen", "nicht erfasst"))
    alter = [{"schluessel": s, "text": t, "anzahl": 0} for s, t, _, _ in ALTERSGRUPPEN]
    for p in aktiv:
        jahre = _alter(p["geburtsdatum"], z.stichtag)
        for i, (_, _, unten, oben) in enumerate(ALTERSGRUPPEN):
            if unten <= jahre <= oben:
                alter[i]["anzahl"] += 1
                break
    return {
        "kennzahlen": {"aktiv": len(aktiv), "betreut": len(betreut), "neuaufnahmen": len(neu),
                       "abgeschlossen": len(abgeschlossen)},
        "verteilungen": {"abschlussanlass": anlass, "versorger": versorger, "altersgruppen": alter,
                         "katheter": katheter},
    }


def _ereignisse(patienten_qs, zeitraeume_: list[Zeitraum]) -> list[dict]:
    """Kontakte und Infusionspläne je Zeitraum – je Modell eine Abfrage für alle Zeiträume."""
    from infusionen.models import Infusionsplan

    ids = patienten_qs.values("id")
    kontakte = Kontakt.objects.filter(patient_id__in=ids, storniert_am__isnull=True).aggregate(**{
        f"k{i}": Count("id", filter=Q(zeitpunkt__date__gte=z.von, zeitpunkt__date__lte=z.bis))
        for i, z in enumerate(zeitraeume_)})
    plaene = Infusionsplan.objects.filter(patient_id__in=ids).aggregate(**{
        k: v for i, z in enumerate(zeitraeume_) for k, v in (
            (f"e{i}", Count("id", filter=Q(erstellt_am__date__gte=z.von, erstellt_am__date__lte=z.bis))),
            (f"f{i}", Count("id", filter=~Q(status=Infusionsplan.Status.ENTWURF) & (
                Q(freigabe_datum__gte=z.von, freigabe_datum__lte=z.bis)
                | Q(freigabe_datum__isnull=True, freigegeben_am__date__gte=z.von, freigegeben_am__date__lte=z.bis)))),
        )})
    return [{"kontakte": kontakte[f"k{i}"], "plaene_erstellt": plaene[f"e{i}"], "plaene_freigegeben": plaene[f"f{i}"]}
            for i in range(len(zeitraeume_))]


def rohzahlen(patienten_qs, zeitraeume_: list[Zeitraum]) -> list[dict]:
    """Genaue Zahlen je Zeitraum – nur für ``schuetze`` und Tests, nie in einer Antwort."""
    zeilen = _zeilen(patienten_qs)
    ereignisse = _ereignisse(patienten_qs, zeitraeume_)
    ergebnis = []
    for z, e in zip(zeitraeume_, ereignisse):
        b = _bestand(zeilen, z)
        b["kennzahlen"].update(e)
        ergebnis.append(b)
    return ergebnis


def auswertung(user, params) -> dict:
    """Vollständige, geschützte Auswertung für die Antwort, das PDF und die CSV."""
    zeitraum, vergleich = zeitraeume(params)
    qs = basis(user)
    jetzt, vorher = rohzahlen(qs, [zeitraum, vergleich])
    runden = muss_runden(jetzt, vorher)
    firma = getattr(user, "firma", None)
    hinweise = [
        "Beginn der Betreuung = Tag der Anlage in EPM; ein eigenes Aufnahmedatum gibt es nicht.",
        "Versorger und Katheter: heutiger Stand der Akte, nicht der Stand am Stichtag.",
        "Infusionspläne freigegeben: nur in EPM freigegebene Pläne; aus dem Altsystem übernommene Pläne haben keinen "
        "Freigabevermerk und zählen nur als erstellt.",
    ]
    if altakten_ids(qs):
        hinweise.append("Aus dem Altsystem übernommene Akten haben kein Aufnahmedatum: Sie gelten als schon vor dem "
                        "Zeitraum in Betreuung und zählen nicht als Neuaufnahme.")
    if zeitraum.laufend:
        hinweise.append(f"Der Zeitraum läuft noch; Stichtag ist heute ({_d(zeitraum.bis)}). Der Vergleich zeigt den "
                        f"vollständigen Vorzeitraum.")
    return {
        "firma": {"kuerzel": firma.kuerzel, "name": firma.name, "kurzname": firma.kurzname} if firma else None,
        "zeitraum": zeitraum.als_dict(),
        "vergleich": vergleich.als_dict(),
        "werte": schuetze(jetzt, runden),
        "vorher": schuetze(vorher, runden),
        "kennzahlen": [{"schluessel": s, "text": t} for s, t in KENNZAHLEN],
        "verteilungen": [{"schluessel": s, "text": t} for s, t in VERTEILUNGEN],
        "regel": REGEL,
        "hinweise": hinweise,
        "erstellt_am": timezone.now().isoformat(),
    }


# ----------------------------------------------------------------------------------------------- Ausgabe
def csv_inhalt(daten: dict) -> bytes:
    """CSV für Excel: Semikolon, UTF-8 mit BOM, Zeilenende CRLF; nur angezeigte (geschützte) Werte."""
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    z, v = daten["zeitraum"], daten["vergleich"]
    w.writerow(["EPM-Statistik", daten["firma"]["name"] if daten["firma"] else ""])
    w.writerow(["Zeitraum", z["titel"], f"{_d(date.fromisoformat(z['von']))} – {_d(date.fromisoformat(z['bis']))}"])
    w.writerow(["Vergleich", v["titel"], f"{_d(date.fromisoformat(v['von']))} – {_d(date.fromisoformat(v['bis']))}"])
    w.writerow(["Erstellt", timezone.localtime().strftime("%d.%m.%Y %H:%M")])
    w.writerow([])
    w.writerow(["Bereich", "Merkmal", z["titel"], v["titel"]])
    for s, t in KENNZAHLEN:
        w.writerow(["Kennzahl", t, daten["werte"]["kennzahlen"][s]["anzeige"], daten["vorher"]["kennzahlen"][s]["anzeige"]])
    for s, t in VERTEILUNGEN:
        vorher = {zeile["schluessel"]: zeile["zelle"]["anzeige"] for zeile in daten["vorher"]["verteilungen"][s]}
        gesehen = set()
        for zeile in daten["werte"]["verteilungen"][s]:
            gesehen.add(zeile["schluessel"])
            w.writerow([t, zeile["text"], zeile["zelle"]["anzeige"], vorher.get(zeile["schluessel"], "0")])
        for zeile in daten["vorher"]["verteilungen"][s]:
            if zeile["schluessel"] not in gesehen:
                w.writerow([t, zeile["text"], "0", zeile["zelle"]["anzeige"]])
    w.writerow([])
    w.writerow(["Hinweis", daten["regel"]])
    for h in daten["hinweise"]:
        w.writerow(["Hinweis", h])
    return ("﻿" + puffer.getvalue()).encode("utf-8")


def _dateiname(daten: dict, endung: str) -> str:
    firma = daten["firma"]["kurzname"] if daten["firma"] else "EPM"
    titel = re.sub(r"[^0-9A-Za-zÄÖÜäöüß]+", "-", daten["zeitraum"]["titel"]).strip("-")
    return f"Statistik-{re.sub(r'[^0-9A-Za-z]+', '', firma) or 'EPM'}-{titel}-{timezone.localdate():%Y-%m-%d}.{endung}"


def _export_protokollieren(request, daten: dict, format_: str):
    z = daten["zeitraum"]
    protokolliere(SystemEreignis.Art.EXPORT, request,
                  objekt=f"Statistik {z['titel']}" + (f" · {daten['firma']['kurzname']}" if daten["firma"] else ""),
                  was="Statistik", format=format_, von=z["von"], bis=z["bis"],
                  vergleich_von=daten["vergleich"]["von"], vergleich_bis=daten["vergleich"]["bis"],
                  firma=daten["firma"]["kuerzel"] if daten["firma"] else "")


class StatistikView(APIView):
    permission_classes = [StatistikRecht]

    def daten(self, request):
        try:
            return auswertung(request.user, request.query_params), None
        except Eingabefehler as e:
            return None, Response({"fehler": str(e)}, status=400)

    def get(self, request):
        daten, fehler = self.daten(request)
        return fehler or Response(daten)


class StatistikPdfView(StatistikView):
    def get(self, request):
        from vorlagen.api import pdf_antwort
        from vorlagen.listen import statistik_pdf

        daten, fehler = self.daten(request)
        if fehler:
            return fehler
        pdf = statistik_pdf(daten)
        _export_protokollieren(request, daten, "PDF")
        return pdf_antwort(pdf, _dateiname(daten, "pdf"))


class StatistikCsvView(StatistikView):
    def get(self, request):
        from urllib.parse import quote

        daten, fehler = self.daten(request)
        if fehler:
            return fehler
        antwort = HttpResponse(csv_inhalt(daten), content_type="text/csv; charset=utf-8")
        antwort["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(_dateiname(daten, 'csv'))}"
        antwort["Cache-Control"] = "private, no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        _export_protokollieren(request, daten, "CSV")
        return antwort
