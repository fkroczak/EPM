"""Laborparameter dreisprachig: Auszug aus den RGC-Vorlagen, Export und Import (18.11.2026).

Ablauf unter Vorlagen › Laborparameter:

* **Aus RGC-Vorlagen** – liest die Ankreuzzeilen aller Laboranforderungen und Laborprofile der Regeneration Clinic
  („☐ Fosfāts / Phosphat“, „☒ 1.02 CRP“), ordnet sie über das Wörterbuch (``laborbegriffe``) Deutsch, Englisch und
  Lettisch zu und zeigt sie in der Vorschau – oder lädt sie als CSV herunter.
* **Export** – der ganze Katalog als CSV (Semikolon, UTF-8 mit BOM für Excel) zum Bearbeiten.
* **Import** – CSV hochladen oder die Zeilen aus den Vorlagen übernehmen. Zuerst immer eine Vorschau: was einen
  vorhandenen Parameter ergänzt, was neu wäre, was unklar ist. Übernommen wird nur, was angehakt ist.

Werte hängen immer am Parameter (``Laborwert.parameter``), nie am Namen: „Fosfors“ und „Phosphat“ sind derselbe Wert.
"""
from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation

from .laborbegriffe import eintraege
from .models import Laborparameter

SPALTEN = ["id", "gruppe", "name_de", "name_en", "name_lv", "kurzname", "einheit", "referenz_von", "referenz_bis",
           "suchbegriffe", "aktiv"]
GRUPPEN = {g for g, _t in Laborparameter.Gruppe.choices}
KASTEN = re.compile(r"^\s*[☐☒]\s*")
NUMMER = re.compile(r"^\d+[A-Z]?\.\d+\s+")  # „1.02 “, „2A.4 “ in den Laborprofilen
UEBERSPRINGEN = ("izmeklējums (lv / de)", "pflicht:", "optional:", "reflex:", "____", "☐", "zusätzlich angefordert")


def _norm(text: str) -> str:
    from scans.ocr.auswertung import norm

    return norm(text or "")


# ---------------------------------------------------------------- Wörterbuch
def _woerterbuch_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for e in eintraege():
        for t in (e["name"], e["name_en"], e["name_lv"], *e["weitere"]):
            n = _norm(t)
            if n:
                index.setdefault(n, e)
    return index


def _varianten(text: str) -> list[str]:
    """Ganze Zeile, ihre Hälften („LV / DE“) und beides ohne Klammerzusatz."""
    teile = [text, *[t for t in re.split(r"\s+/\s+", text) if t.strip()]]
    ohne = [re.sub(r"\([^)]*\)", " ", t) for t in teile]
    return [t for t in dict.fromkeys(teile + ohne) if t.strip()]


def eintrag_zu(text: str, index: dict[str, dict] | None = None) -> dict | None:
    index = index if index is not None else _woerterbuch_index()
    for v in _varianten(text):
        e = index.get(_norm(v))
        if e is not None:
            return e
    return None


# ---------------------------------------------------------------- Auszug aus den RGC-Vorlagen
def _zeile_bereinigen(text: str) -> str:
    text = KASTEN.sub("", text.strip())
    text = NUMMER.sub("", text)
    text = re.split(r"\s+—\s+", text)[0]  # „— tukšā dūšā / nüchtern“: Hinweis zur Abnahme
    return text.strip(" ·")


def vorlagen_zeilen(firma_kuerzel: str = "rg") -> list[tuple[str, str]]:
    """(bereinigte Zeile, Vorlage) aller Ankreuzzeilen der Laboranforderungen und -profile einer Firma."""
    from vorlagen.models import Dokumentvorlage, EigenesSchreiben

    zeilen = []
    for schreiben in EigenesSchreiben.objects.filter(firma__kuerzel=firma_kuerzel, aktiv=True,
                                                     gruppe="anforderungen").order_by("name"):
        if not schreiben.name.lower().startswith("labor"):  # nur Laboranforderungen und -profile, kein MRT/EKG
            continue
        vorlage = (Dokumentvorlage.objects.filter(art=schreiben.schluessel, status=Dokumentvorlage.Status.AKTIV)
                   .order_by("-version").first()
                   or Dokumentvorlage.objects.filter(art=schreiben.schluessel).order_by("-erstellt_am").first())
        if vorlage is None:
            continue
        for block in vorlage.bloecke or []:
            kandidaten = list((block.get("text") or "").split("\n"))
            kandidaten += [f.get("label") or "" for f in block.get("felder") or [] if isinstance(f, dict)]
            for roh in kandidaten:
                if not KASTEN.match(roh or ""):
                    continue
                text = _zeile_bereinigen(roh)
                if (text and not any(s in text.lower() for s in UEBERSPRINGEN) and len(text) <= 150
                        and not text.startswith("MAL-")):
                    zeilen.append((text, schreiben.name))
    return zeilen


def aus_vorlagen(firma_kuerzel: str = "rg") -> list[dict]:
    """Zeilen für Vorschau bzw. CSV: je Parameter einmal, mit den Vorlagen, in denen er steht."""
    index = _woerterbuch_index()
    nach: dict[str, dict] = {}
    for text, vorlage in vorlagen_zeilen(firma_kuerzel):
        e = eintrag_zu(text, index)
        if e is not None:
            schluessel = "w:" + e["name"]
            zeile = {"name": e["name"], "name_en": e["name_en"], "name_lv": e["name_lv"], "gruppe": e["gruppe"],
                     "einheit": e["einheit"], "kurzname": e["kurzname"], "bekannt": True}
        else:
            schluessel = "t:" + _norm(text)
            teile = [t.strip() for t in re.split(r"\s+/\s+", text)]
            lv, de = (teile[0], teile[1]) if len(teile) == 2 else (text, text)
            zeile = {"name": de, "name_en": "", "name_lv": lv, "gruppe": "sonstiges", "einheit": "", "kurzname": "",
                     "bekannt": False}
        z = nach.setdefault(schluessel, {**zeile, "zeile": text, "quellen": []})
        if vorlage not in z["quellen"]:
            z["quellen"].append(vorlage)
    return list(nach.values())


# ---------------------------------------------------------------- CSV
def export_csv(parameter) -> str:
    puffer = io.StringIO()
    puffer.write("﻿")
    w = csv.writer(puffer, delimiter=";", lineterminator="\r\n")
    w.writerow(SPALTEN)
    for p in parameter:
        w.writerow([p.id, p.gruppe, p.name, p.name_en, p.name_lv, p.kurzname, p.einheit,
                    _zahl(p.referenz_von), _zahl(p.referenz_bis), p.suchbegriffe, "ja" if p.aktiv else "nein"])
    return puffer.getvalue()


def zeilen_csv(zeilen: list[dict]) -> str:
    """Zeilen aus den Vorlagen als CSV im Format des Exports (ohne id; dazu Spalte „vorlagen“)."""
    puffer = io.StringIO()
    puffer.write("﻿")
    w = csv.writer(puffer, delimiter=";", lineterminator="\r\n")
    w.writerow(SPALTEN + ["vorlagen"])
    for z in zeilen:
        w.writerow(["", z.get("gruppe", ""), z.get("name", ""), z.get("name_en", ""), z.get("name_lv", ""),
                    z.get("kurzname", ""), z.get("einheit", ""), "", "", "", "ja", ", ".join(z.get("quellen") or [])])
    return puffer.getvalue()


def _zahl(d) -> str:
    if d is None:
        return ""
    return format(d.normalize(), "f").replace(".", ",")


class ImportFehler(ValueError):
    pass


def lies_csv(inhalt: bytes) -> list[dict]:
    try:
        text = inhalt.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = inhalt.decode("cp1252")
    erste = text.split("\n", 1)[0]
    trenner = ";" if erste.count(";") >= erste.count(",") else ","
    leser = csv.DictReader(io.StringIO(text), delimiter=trenner)
    kopf = {(k or "").strip().lower() for k in leser.fieldnames or []}
    if not ({"name_de", "name"} & kopf):
        raise ImportFehler("Die Datei braucht mindestens die Spalte „name_de“ (Kopfzeile wie beim Export).")
    zeilen = []
    for roh in leser:
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in roh.items() if k}
        name = r.get("name_de") or r.get("name") or ""
        if not (name or r.get("name_lv") or r.get("name_en")):
            continue
        zeilen.append({"id": int(r["id"]) if r.get("id", "").isdigit() else None, "gruppe": r.get("gruppe", ""),
                       "name": name, "name_en": r.get("name_en", ""), "name_lv": r.get("name_lv", ""),
                       "kurzname": r.get("kurzname", ""), "einheit": r.get("einheit", ""),
                       "referenz_von": r.get("referenz_von", ""), "referenz_bis": r.get("referenz_bis", ""),
                       "suchbegriffe": r.get("suchbegriffe", ""), "aktiv": r.get("aktiv", ""),
                       "quellen": [q.strip() for q in r.get("vorlagen", "").split(",") if q.strip()]})
    if len(zeilen) > 2000:
        raise ImportFehler("Höchstens 2000 Zeilen je Import.")
    return zeilen


# ---------------------------------------------------------------- Vorschau und Übernahme
def _dezimal(text) -> Decimal | None:
    if text in (None, ""):
        return None
    try:
        return Decimal(str(text).replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise ImportFehler(f"„{text}“ ist keine Zahl.")


def _katalog_finden(zeile: dict, parameter: list[Laborparameter]):
    """Vorhandenen Parameter zur Zeile: über die ID, sonst über Namen, Übersetzungen, Synonyme und Wörterbuch."""
    from scans.ocr import auswertung

    nach_id = {p.id: p for p in parameter}
    if zeile.get("id"):
        return nach_id.get(zeile["id"])
    werte = [{"id": p.id, "name": p.name, "kurzname": p.kurzname, "einheit": p.einheit, "gruppe": p.gruppe,
              "suchbegriffe": p.suchbegriffe, "name_en": p.name_en, "name_lv": p.name_lv} for p in parameter]
    index, _e = auswertung.katalog_index(werte)
    for feld in ("name", "name_lv", "name_en"):
        n = _norm(zeile.get(feld) or "")
        if n and index.get(n) and len(index[n]) == 1:
            return nach_id[index[n][0].id]
    return None


FELDER_VORHANDEN = ("name_en", "name_lv")
FELDER_MIT_ID = ("gruppe", "name", "name_en", "name_lv", "kurzname", "einheit", "referenz_von", "referenz_bis",
                 "suchbegriffe", "aktiv")


def _gewuenscht(zeile: dict, feld: str):
    wert = zeile.get(feld)
    if feld in ("referenz_von", "referenz_bis"):
        return _dezimal(wert)
    if feld == "aktiv":
        return None if wert in (None, "") else str(wert).strip().lower() in ("ja", "1", "true", "x", "aktiv")
    return (wert or "").strip() if isinstance(wert, str) else wert


def vorschau(zeilen: list[dict]) -> list[dict]:
    """Jede Zeile mit Status: „ergaenzt“ (vorhandener Parameter bekommt Namen dazu), „vorhanden“ (nichts zu tun),
    „neu“ (nicht im Katalog) oder „unklar“ (weder Katalog noch Wörterbuch kennen den Begriff)."""
    parameter = list(Laborparameter.objects.all())
    ergebnis = []
    for i, z in enumerate(zeilen):
        p = _katalog_finden(z, parameter)
        aus = {"nr": i, **{k: z.get(k) for k in ("id", "gruppe", "name", "name_en", "name_lv", "kurzname", "einheit",
                                                  "referenz_von", "referenz_bis", "suchbegriffe", "aktiv",
                                                  "quellen", "zeile")}}
        if p is not None:
            felder = FELDER_MIT_ID if z.get("id") else FELDER_VORHANDEN
            aenderungen = {}
            for f in felder:
                neu = _gewuenscht(z, f)
                if neu in (None, "") and f not in ("aktiv",):
                    continue  # leere Zellen löschen nichts
                if neu is None:
                    continue
                alt = getattr(p, f)
                if f in ("referenz_von", "referenz_bis") and alt is not None and neu is not None and alt == neu:
                    continue
                if alt != neu:
                    aenderungen[f] = [_text(alt), _text(neu)]
            aus.update(status="ergaenzt" if aenderungen else "vorhanden", parameter=p.id, parameter_name=p.name,
                       aenderungen=aenderungen)
        else:
            bekannt = z.get("bekannt", eintrag_zu(z.get("name") or "") is not None or
                            eintrag_zu(z.get("name_lv") or "") is not None)
            aus.update(status="neu" if bekannt and (z.get("name") or "").strip() else "unklar", parameter=None,
                       parameter_name="", aenderungen={})
        ergebnis.append(aus)
    return ergebnis


def _text(wert) -> str:
    if isinstance(wert, Decimal):
        return _zahl(wert)
    if isinstance(wert, bool):
        return "ja" if wert else "nein"
    return "" if wert is None else str(wert)


def uebernehmen(zeilen: list[dict]) -> dict:
    """Gewählte Zeilen übernehmen. Vorhandene Parameter: ohne ID nur die Übersetzungen, mit ID (aus dem Export) alle
    gefüllten Spalten. Nicht vorhandene: neu anlegen (Name Deutsch Pflicht)."""
    ergaenzt, neu, unveraendert = [], [], 0
    parameter = list(Laborparameter.objects.all())
    for z in zeilen:
        p = _katalog_finden(z, parameter)
        if p is None and z.get("id"):
            raise ImportFehler(f"Parameter mit der ID {z['id']} gibt es nicht.")
        if p is not None:
            geaendert = []
            for f in FELDER_MIT_ID if z.get("id") else FELDER_VORHANDEN:
                wert = _gewuenscht(z, f)
                if wert is None or wert == "":
                    continue
                if f == "gruppe" and wert not in GRUPPEN:
                    raise ImportFehler(f"Unbekannte Gruppe „{wert}“.")
                if getattr(p, f) != wert:
                    setattr(p, f, _kuerzen(f, wert))
                    geaendert.append(f)
            if geaendert:
                p.full_clean()
                p.save(update_fields=geaendert)
                ergaenzt.append(p.name)
            else:
                unveraendert += 1
            continue
        name = (z.get("name") or "").strip()
        if not name:
            raise ImportFehler(f"Für „{z.get('name_lv') or z.get('name_en')}“ fehlt der deutsche Name.")
        gruppe = z.get("gruppe") if z.get("gruppe") in GRUPPEN else "sonstiges"
        if Laborparameter.objects.filter(gruppe=gruppe, name=name).exists():
            raise ImportFehler(f"„{name}“ gibt es in dieser Gruppe schon.")
        aktiv = _gewuenscht(z, "aktiv")
        p = Laborparameter(gruppe=gruppe, name=name[:150], name_en=(z.get("name_en") or "")[:150],
                           name_lv=(z.get("name_lv") or "")[:150], kurzname=(z.get("kurzname") or "")[:60],
                           einheit=(z.get("einheit") or "")[:30], suchbegriffe=(z.get("suchbegriffe") or "")[:300],
                           referenz_von=_dezimal(z.get("referenz_von")), referenz_bis=_dezimal(z.get("referenz_bis")),
                           aktiv=True if aktiv is None else aktiv)
        p.full_clean()
        p.save()
        parameter.append(p)
        neu.append(p.name)
    return {"ergaenzt": ergaenzt, "neu": neu, "unveraendert": unveraendert}


def _kuerzen(feld: str, wert):
    grenzen = {"name": 150, "name_en": 150, "name_lv": 150, "kurzname": 60, "einheit": 30, "suchbegriffe": 300}
    return wert[:grenzen[feld]] if feld in grenzen and isinstance(wert, str) else wert
