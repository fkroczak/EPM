#!/usr/bin/env python3
"""Laborprofile Malabsorption der Regeneration Clinic (RGC) in EPM übernehmen (14.10.2026).

    python3 werkzeuge/rgc-laborprofile.py LABORPROFILE.docx [ZIELORDNER]

Liest die Word-Datei „Laborprofile Malabsorption – Strukturierte Anforderungsprofile zur Integration in die Klinik-IT“
(Profilübersicht, Parameterkatalog je Profil, Regelwerk R1–R11, Monitoring-Intervalle) und schreibt

- ``backend/vorlagen/statisch/laborprofile-malabsorption.json``: die Inhalte strukturiert, je Parameter mit den Feldern
  aus Abschnitt 6 des Dokuments (Profil-ID, Nr., Parameter, Material, LOINC, Status P/O/R, Regelbezug, Hinweis) –
  wörtlich wie geliefert, Grundlage für spätere Fassungen;
- je Profil eine Laboranforderung als Vorlage nach ``backend/vorlagen/statisch/rgc/RC_Labor_MAL-….json`` (MAL-01,
  MAL-02A, MAL-02B, MAL-02C, MAL-03 mit A–D, MAL-04, MAL-05, MAL-06) und eine Übersicht mit Regelwerk und Intervallen
  (``RC_Labor_MAL-00``). Die Datenmigration ``vorlagen/0011_rgc_laborprofile`` legt sie als eigene Schreiben der
  Firma RGC an (Briefkopf der Klinik).

Die Anforderungen sind nach Röhrchen bzw. Material geordnet, damit Abnahme und Labor dieselbe Zuordnung sehen:
Pflichtparameter sind angekreuzt (☒), optionale und Reflexparameter zum Ankreuzen (☐). Material und LOINC stehen
genau wie im Dokument; mit „prüfen“ markierte Codes bleiben als Hinweis auf den Abgleich mit dem Laborkatalog stehen.

Braucht ``python-docx``.
"""
import json
import re
import sys
from pathlib import Path

import docx

STATISCH = Path(__file__).resolve().parent.parent / "backend" / "vorlagen" / "statisch"
LINIE = "____________________"
JA, NEIN = "☒", "☐"
STATUS = {"P": "Pflicht", "O": "optional", "R": "Reflex"}
# Material ohne eigenes Röhrchen bzw. ohne Probe (Rechenwert, Funktionsdiagnostik, extern)
OHNE_PROBE = ("berechnet", "–", "Funktionsdiagnostik", "nuklearmedizinisch (extern)", "gemäß ESPEN-HPN",
              "wie Ursprungsparameter")
# Reflexregeln mit Parametern aus einem anderen Profil: auslösende Parameter-Nr. je Regel. Steht ein Auslöser auf dem
# Bogen, kommt der Reflexparameter mit seinem Röhrchen dazu (MAL-01: Parathormon 2A.4 nach R7 – EDTA-Plasma, gekühlt)
AUSLOESER = {"R1": ["1.02"], "R2": ["1.27"], "R3": ["1.34"], "R7": ["1.31", "1.09"]}
VERSION = "1.0"
QUELLE = "Laborprofile Malabsorption, Dokumentversion 1.0 (Regeneration Clinic SIA, 14.10.2026)"

# Anforderungsbögen: Kennung → (Name, Profile auf dem Bogen, Titel, Untertitel)
BOEGEN = [
    ("MAL-01", "Laborprofil MAL-01 – Basisprofil Malabsorption", ["MAL-01"]),
    ("MAL-02A", "Laborprofil MAL-02A – Fettmalabsorption", ["MAL-02A"]),
    ("MAL-02B", "Laborprofil MAL-02B – Ausgeprägte oder langdauernde Malabsorption", ["MAL-02B"]),
    ("MAL-02C", "Laborprofil MAL-02C – Kurzdarmsyndrom / Darmversagen", ["MAL-02C"]),
    ("MAL-03", "Laborprofil MAL-03 – Ursachenbezogene Zusatzdiagnostik", ["MAL-03A", "MAL-03B", "MAL-03C", "MAL-03D"]),
    ("MAL-04", "Laborprofil MAL-04 – Initialpanel (Vollpanel)", ["MAL-01", "MAL-02A", "MAL-02B"]),
    ("MAL-05", "Laborprofil MAL-05 – Monitoring chronische intestinale Insuffizienz", ["MAL-05"]),
    ("MAL-06", "Laborprofil MAL-06 – Refeeding-Monitoring", ["MAL-06"]),
]
# Parameter-Nr. → Profil (MAL-03A–D teilen sich eine Tabelle im Dokument)
PROFIL_VON_NR = [(r"^1\.", "MAL-01"), (r"^2A\.", "MAL-02A"), (r"^2B\.", "MAL-02B"), (r"^2C\.", "MAL-02C"),
                 (r"^3A\.", "MAL-03A"), (r"^3B\.", "MAL-03B"), (r"^3C\.", "MAL-03C"), (r"^3D\.", "MAL-03D"),
                 (r"^5\.", "MAL-05"), (r"^6\.", "MAL-06")]

# Pflichthinweise bei der Anforderung (Abschnitt 6 und Regel R11) – erscheinen auf dem Bogen, wenn er den Parameter
# bzw. das Material enthält
PFLICHTHINWEISE = [
    (lambda p: p["nr"] == "1.33",
     "tTG-IgA (1.33): Patient unter glutenhaltiger Kost?  ☐ ja  ☐ nein – bei Nein nur mit Begründung anfordern "
     "(Serologie unter glutenfreier Kost falsch negativ, Regel R11). Begründung: " + LINIE),
    (lambda p: p["nr"] == "3A.1",
     "Pankreas-Elastase-1 (3A.1): aus geformtem Stuhl – wässriger Stuhl ist verdünnungsbedingt falsch niedrig (R5)."),
    (lambda p: "Spurenelement" in p["material"],
     "Spurenelemente: eigenes Spurenelement-Röhrchen verwenden, Hämolyse vermeiden."),
    (lambda p: "lichtgeschützt" in p["material"],
     "Lichtempfindliche Vitamine: Röhrchen lichtgeschützt abnehmen und transportieren."),
    (lambda p: "gekühlt" in p["material"],
     "Gekühlte Proben (" + "{gekuehlt}" + "): sofort kühlen und gekühlt transportieren."),
    (lambda p: "nüchtern" in p["material"].lower() or "nüchtern" in p["parameter"].lower()
     or "Nüchternabnahme" in p["hinweis"],
     "Nüchternabnahme erforderlich für: {nuechtern}."),
]


def zellen(tabelle) -> list[list[str]]:
    zeilen = []
    for zeile in tabelle.rows:
        gesehen, werte = set(), []
        for z in zeile.cells:
            if id(z._tc) in gesehen:
                continue
            gesehen.add(id(z._tc))
            werte.append(re.sub(r"\s+", " ", z.text).strip())
        zeilen.append(werte)
    return zeilen


def einlesen(datei: Path) -> dict:
    d = docx.Document(str(datei))
    tabellen = [zellen(t) for t in d.tables]
    profile, parameter, regeln, intervalle = [], [], [], []
    for t in tabellen:
        kopf = t[0]
        if kopf[:2] == ["Profil-ID", "Bezeichnung"]:
            for pid, name, ausloeser, inhalt in t[1:]:
                stufe = re.search(r"\(Stufe (\d)\)", name)
                profile.append({"id": pid, "bezeichnung": name, "stufe": int(stufe.group(1)) if stufe else None,
                                "indikation": ausloeser, "inhalt": inhalt})
        elif kopf[:2] == ["Nr.", "Parameter"]:
            for nr, name, material, loinc, status, hinweis in t[1:]:
                profil = next(p for muster, p in PROFIL_VON_NR if re.match(muster, nr))
                parameter.append({"profil": profil, "nr": nr, "parameter": name, "material": material,
                                  "loinc": loinc, "status": status if status in STATUS else "",
                                  "regeln": sorted(set(re.findall(r"\bR\d+\b", hinweis)), key=lambda r: int(r[1:])),
                                  "hinweis": hinweis})
        elif kopf[:2] == ["Regel", "Auslöser (Bedingung)"]:
            for rid, ausloeser, aktion, begruendung in t[1:]:
                regeln.append({"id": rid, "ausloeser": ausloeser, "aktion": aktion, "begruendung": begruendung})
        elif kopf[:2] == ["Situation", "Intervall"]:
            for situation, intervall, umfang, profil in t[1:]:
                intervalle.append({"situation": situation, "intervall": intervall, "umfang": umfang, "profil": profil})
    if not (profile and parameter and regeln and intervalle):
        sys.exit("Profilübersicht, Parameterkatalog, Regelwerk oder Intervalle nicht gefunden.")
    # Regeln, die ein Profil betreffen: aus den Hinweisen seiner Parameter und aus den Regeln, die es nennen
    for p in profile:
        bezug = {r for x in parameter if x["profil"] == p["id"] for r in x["regeln"]}
        nummern = {x["nr"] for x in parameter if x["profil"] == p["id"]}
        for r in regeln:
            text = f"{r['ausloeser']} {r['aktion']}"
            if p["id"] in text or any(re.search(rf"\({re.escape(n)}\)", text) for n in nummern):
                bezug.add(r["id"])
        p["regeln"] = sorted(bezug, key=lambda r: int(r[1:]))
    return {"titel": "Laborprofile Malabsorption – Strukturierte Anforderungsprofile", "version": VERSION,
            "quelle": QUELLE, "datei": datei.name, "status_legende": STATUS,
            "hinweis": "LOINC-Codes sind Zuordnungsvorschläge; „prüfen“ sowie Einheiten und Referenzbereiche vor "
                       "Produktivsetzung gegen den Katalog des beauftragten Labors abgleichen.",
            "profile": profile, "parameter": parameter, "regeln": regeln, "intervalle": intervalle}


# ---------------------------------------------------------------------------------------------- Anforderungsbögen
def _loinc(loinc: str) -> str:
    if not loinc or loinc == "–":
        return ""
    if loinc.startswith("wie "):
        return f"LOINC {loinc}"
    return "LOINC " + loinc.replace("prüfen", "im Laborkatalog prüfen")


def _status(p) -> str:
    if p["status"] == "R":
        return f"Reflex ({', '.join(f'Regel {r}' for r in p['regeln'])})" if p["regeln"] else "Reflex"
    return STATUS.get(p["status"], "Hinweis")


def _zeile(p, ankreuzen=True) -> dict:
    kreuz = JA if p["status"] == "P" and ankreuzen else NEIN
    name, rest = p["parameter"], ""
    if len(f"{kreuz} {p['nr']} {name}") > 100 and ":" in name:  # lange Aufzählung: Rest in die Wertspalte
        name, rest = (t.strip() for t in name.split(":", 1))
    label = f"{kreuz} {p['nr']} {name}"
    wert = " · ".join(t for t in (rest, _status(p), _loinc(p["loinc"]), p["hinweis"]) if t)
    return {"label": label[:100], "wert": wert[:500]}


def _material_reihen(parameter) -> list[tuple[str, list]]:
    """Parameter je Röhrchen/Material in der Reihenfolge des ersten Auftretens; Material ohne Probe zuletzt."""
    gruppen: dict[str, list] = {}
    for p in parameter:
        gruppen.setdefault(p["material"], []).append(p)
    proben = [(m, ps) for m, ps in gruppen.items() if m not in OHNE_PROBE]
    ohne = [(m, ps) for m, ps in gruppen.items() if m in OHNE_PROBE]
    return proben + ohne


def _roehrchen_text(reihen, ankreuzen=True) -> str:
    zeilen = []
    for material, ps in reihen:
        if material in OHNE_PROBE:
            continue
        teile = []
        for st, name in (("P", "Pflicht"), ("O", "optional"), ("R", "Reflex")):
            nrn = [p["nr"] for p in ps if p["status"] == st]
            if nrn:
                teile.append(f"{name}: {', '.join(nrn)}")
        pflicht = ankreuzen and any(p["status"] == "P" for p in ps)
        zeilen.append(f"{JA if pflicht else NEIN} {material} – {'; '.join(teile)}")
    return "\n".join(zeilen)


def _ohne_probe_name(material: str) -> str:
    return {"berechnet": "Rechenwert (kein Röhrchen)", "Funktionsdiagnostik": "Funktionsdiagnostik (keine Probe)",
            "nuklearmedizinisch (extern)": "Nuklearmedizinisch, extern (Konsil)",
            "gemäß ESPEN-HPN": "Nach ESPEN-HPN-Empfehlungen", "–": "Hinweis (kein Laborparameter)",
            "wie Ursprungsparameter": "Material wie Ursprungsparameter"}.get(material, material)


def _pflichthinweise(parameter) -> list[str]:
    hinweise = []
    gekuehlt = sorted({p["material"] for p in parameter if "gekühlt" in p["material"]})
    nuechtern = [p["nr"] for p in parameter if "nüchtern" in p["material"].lower()
                 or "nüchtern" in p["parameter"].lower() or "Nüchternabnahme" in p["hinweis"]]
    for bedingung, text in PFLICHTHINWEISE:
        if any(bedingung(p) for p in parameter):
            hinweise.append(text.format(gekuehlt="; ".join(gekuehlt), nuechtern=", ".join(nuechtern)))
    return hinweise


def _fremde_reflexe(daten: dict, parameter: list) -> list:
    """Reflexparameter anderer Profile, deren Regel ein Parameter dieses Bogens auslöst (als Reflex markiert)."""
    vorhanden = {p["nr"] for p in parameter}
    alle = {p["nr"]: p for p in daten["parameter"]}
    dazu = []
    for r in daten["regeln"]:
        if not set(AUSLOESER.get(r["id"], [])) & vorhanden:
            continue
        for nr in re.findall(r"\(([0-9A-D]+\.[0-9]+)\)", r["aktion"]):
            if nr not in vorhanden and nr in alle:
                p = alle[nr]
                dazu.append({**p, "status": "R", "regeln": [r["id"]],
                             "hinweis": f"aus {p['profil']}; {p['hinweis']}".rstrip("; ")})
                vorhanden.add(nr)
    return dazu


def _regel_text(regeln, ids) -> str:
    zeilen = []
    for r in regeln:
        if r["id"] in ids:
            zeilen.append(f"{r['id']} – Wenn: {r['ausloeser']} → {r['aktion']}")
    return "\n".join(zeilen)


def _kopf(titel: str, zusatz: str) -> list[dict]:
    return [
        # Briefpapier der Klinik 1:1 wie im gelieferten Dokument (Bänder, Logo, Anschrift, Absender und Kontakt)
        {"id": "kopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", "absender": True, "falzmarken": False,
         "briefpapier": "rgc"},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": titel, "zusatz": zusatz},
    ]


def _patient(nuechtern_feld: bool = True) -> dict:
    felder = [
        {"label": "Name, Vorname", "wert": "{{Patient.Name}}"},
        {"label": "Geburtsdatum", "wert": "{{Patient.Geburtsdatum}}"},
        {"label": "Patienten-ID", "wert": "{{Patient.Nummer}}"},
        {"label": "Versicherung", "wert": "{{Patient.Versicherung}}"},
        {"label": "Datum", "wert": "{{Heute}}"},
        {"label": "Abnahme (Uhrzeit)", "wert": LINIE},
        {"label": "Anfordernder Arzt", "wert": LINIE},
        {"label": "Abnahme durch", "wert": LINIE},
    ]
    if nuechtern_feld:
        felder.append({"label": "Nüchtern", "wert": "☐ ja  ☐ nein"})
        felder.append({"label": "Dringlichkeit", "wert": "☐ Routine  ☐ eilig"})
    return {"id": "patient", "typ": "datenfelder", "bezeichnung": "Patient und Anforderung", "spalten": 2,
            "felder": felder}


def _fuss() -> list[dict]:
    return [
        {"id": "unterschrift", "typ": "unterschrift", "bezeichnung": "Unterschrift",
         "linie": "Datum, Unterschrift anfordernder Arzt", "optionen": {"nicht_teilen": True}},
        {"id": "fuss", "typ": "fusszeile", "bezeichnung": "Fußzeile",
         "text": "{{Absender.Name}} · {{Absender.Straße}} · {{Absender.PLZ_Ort}}\n{{Absender.Telefon}} · "
                 "{{Absender.E-Mail}}\n{{Absender.Fußzeile}}",
         "rechts": "{Seite}/{Seiten}"},
    ]


def _text(kennung: str, ueberschrift: str, text: str, **optionen) -> dict:
    return {"id": kennung, "typ": "text", "bezeichnung": ueberschrift, "text": text,
            "optionen": {"ueberschrift": True, **optionen}}


def _material_bloecke(praefix: str, parameter, ankreuzen=True) -> list[dict]:
    bloecke = []
    for i, (material, ps) in enumerate(_material_reihen(parameter), 1):
        name = _ohne_probe_name(material) if material in OHNE_PROBE else f"Röhrchen / Material: {material}"
        for teil in range(0, len(ps), 30):  # höchstens 30 Felder je Block
            stueck = ps[teil:teil + 30]
            bloecke.append({"id": f"{praefix}m{i}{'' if teil == 0 else f'-{teil // 30 + 1}'}", "typ": "datenfelder",
                            "bezeichnung": name if teil == 0 else f"{name} (Fortsetzung)", "spalten": 1,
                            "felder": [_zeile(p, ankreuzen) for p in stueck], "optionen": {"ueberschrift": True}})
    return bloecke


LEGENDE = (f"{JA} Pflichtparameter des Profils (angekreuzt) · {NEIN} optional – bei Bedarf ankreuzen · "
           f"{NEIN} Reflex – nur bei Erfüllung der genannten Regel, wird vom Labor nachgefordert. "
           "LOINC als Zuordnungsvorschlag; „im Laborkatalog prüfen“ = Code beim beauftragten Labor zuordnen.")


def bogen(daten: dict, kennung: str, name: str, profil_ids: list[str]) -> dict:
    profile = {p["id"]: p for p in daten["profile"]}
    parameter = [p for p in daten["parameter"] if p["profil"] in profil_ids]
    regeln = sorted({r for pid in profil_ids for r in profile[pid]["regeln"]}, key=lambda r: int(r[1:]))
    if kennung == "MAL-04":
        regeln = sorted(set(regeln) | {"R10"}, key=lambda r: int(r[1:]))
    haupt = profile.get(kennung)
    if haupt is not None:
        titel = f"{kennung} · {haupt['bezeichnung']}"
    else:  # MAL-03: Zusatzdiagnostik A–D
        titel = f"{kennung} · Ursachenbezogene Zusatzdiagnostik (Stufe 3)"
    bloecke = _kopf(titel, f"Laboranforderung · Laborprofile Malabsorption V{VERSION}")
    bloecke.append(_patient())
    if haupt is not None:
        indikation = f"Indikation: {haupt['indikation']}\nInhalt: {haupt['inhalt']}"
    else:
        indikation = "\n".join(f"☐ {pid} · {profile[pid]['bezeichnung']} – {profile[pid]['indikation']}"
                               for pid in profil_ids)
    if kennung == "MAL-04":
        indikation += ("\nUmfasst die Pflichtparameter von MAL-01, MAL-02A und MAL-02B in einer Anforderung; "
                       "Reflexparameter bleiben regelgesteuert. Bei Kurzdarmsyndrom oder Darmversagen zusätzlich "
                       "MAL-02C anfordern (Regel R10).\n☐ MAL-02C zusätzlich angefordert")
    bloecke.append(_text("indikation", "Indikation und Klinische Angaben", indikation + "\n\nFragestellung:\n\n"))
    if kennung == "MAL-05":
        bloecke.append(_text("dynamisch", "5.1 Pathologische Parameter aus MAL-04 (dynamisch)",
                             "Zuletzt pathologische Parameter eintragen (Material wie Ursprungsparameter, Intervall "
                             "nach Monitoring-Plan):\n" + "\n".join(f"☐ {LINIE}{LINIE}" for _ in range(6))))
        parameter = [p for p in parameter if p["nr"] != "5.1"]
        bloecke.append(_text("intervalle", "Monitoring-Intervalle",
                             "\n".join(f"{i['situation']}: {i['intervall']} – {i['umfang']} – Profil {i['profil']}"
                                       for i in daten["intervalle"]), schrift="klein"))
    if kennung == "MAL-06":
        bloecke.append(_text("thiamin", "Pflichthinweis Thiaminsubstitution",
                             next(p["hinweis"] for p in parameter if p["nr"] == "6.6")
                             + "\n☐ Thiamin vor der ersten Nährstoffzufuhr gegeben – Datum/Uhrzeit: " + LINIE,
                             fett=True))
        bloecke.append(_text("abnahmen", "Abnahmezeitpunkte",
                             "Vor Kostaufbau und täglich in den ersten drei Tagen, anschließend nach klinischem "
                             "Verlauf.\n☐ vor Beginn   ☐ Tag 1   ☐ Tag 2   ☐ Tag 3   ☐ weitere: " + LINIE))
        parameter = [p for p in parameter if p["nr"] != "6.6"]
    parameter = parameter + _fremde_reflexe(daten, parameter)
    ankreuzen = kennung != "MAL-03"  # MAL-03: erst das Teilprofil wählen, dann dessen Parameter
    roehrchen = _roehrchen_text(_material_reihen(parameter), ankreuzen)
    if roehrchen:
        bloecke.append(_text("roehrchen", "Röhrchen und Material (Übersicht)", roehrchen))
    if kennung == "MAL-03":
        for pid in profil_ids:
            bloecke += _material_bloecke(pid.lower().replace("-", ""),
                                         [p for p in parameter if p["profil"] == pid], ankreuzen=False)
            # Überschrift des ersten Blocks je Teilprofil mit Profil-ID
            erster = next(b for b in reversed(bloecke) if b["id"].startswith(pid.lower().replace("-", "")) and
                          b["id"].endswith("m1"))
            erster["bezeichnung"] = f"{pid} · {profile[pid]['bezeichnung']} – {erster['bezeichnung']}"
    else:
        bloecke += _material_bloecke("", parameter)
    legende = LEGENDE if ankreuzen else LEGENDE.replace(
        f"{JA} Pflichtparameter des Profils (angekreuzt)",
        f"Teilprofil oben wählen, dann dessen Parameter ankreuzen: Pflicht = Pflichtparameter des Teilprofils")
    bloecke.append({"id": "legende", "typ": "text", "bezeichnung": "Legende", "text": legende,
                    "optionen": {"schrift": "klein", "kursiv": True}})
    hinweise = _pflichthinweise(parameter)
    if hinweise:
        bloecke.append(_text("praeanalytik", "Pflichthinweise zur Präanalytik", "\n".join(hinweise)))
    if regeln:
        bloecke.append(_text("regeln", "Reflexregeln und Befundhinweise", _regel_text(daten["regeln"], regeln),
                             schrift="klein"))
    bloecke += _fuss()
    beschreibung = (haupt["indikation"] if haupt else "Pankreas, CED, Dünndarmfehlbesiedlung/Kohlenhydrate, "
                    "Infektion und Proteinverlust (MAL-03A–D)")
    return {"quelle": f"RC_Labor_{kennung}", "name": name, "gruppe": "anforderungen",
            "beschreibung": f"Laboranforderung Malabsorption – {beschreibung}"[:300], "datei": daten["datei"],
            "bloecke": bloecke}


def uebersicht(daten: dict) -> dict:
    bloecke = _kopf("Laborprofile Malabsorption", f"Übersicht, Regelwerk und Monitoring · Dokumentversion {VERSION}")
    bloecke.append(_text("zweck", "Stufenkonzept",
                         "Stufe 1: Basisprofil bei jedem Verdacht (MAL-01). Stufe 2: gezielte Erweiterung bei "
                         "Fettmalabsorption (MAL-02A), ausgeprägter oder langdauernder Malabsorption (MAL-02B) und "
                         "Kurzdarmsyndrom/Darmversagen (MAL-02C). Stufe 3: ursachenbezogene Zusatzdiagnostik "
                         "(MAL-03A–D). Bei gesicherter Diagnose: Initialpanel MAL-04, Verlauf MAL-05, "
                         "Refeeding-Monitoring MAL-06.\n" + daten["hinweis"]))
    bloecke.append({"id": "profile", "typ": "datenfelder", "bezeichnung": "Profilübersicht", "spalten": 1,
                    "felder": [{"label": f"{p['id']} · {p['bezeichnung']}"[:100],
                                "wert": f"Auslöser: {p['indikation']} · Inhalt: {p['inhalt']}"[:500]}
                               for p in daten["profile"]], "optionen": {"ueberschrift": True}})
    bloecke.append(_text("regeln", "Regelwerk: Reflexanforderungen und Interpretationshinweise",
                         "\n".join(f"{r['id']} – Wenn: {r['ausloeser']} → {r['aktion']} (Begründung: "
                                   f"{r['begruendung']})" for r in daten["regeln"]), schrift="klein"))
    bloecke.append({"id": "intervalle", "typ": "datenfelder", "bezeichnung": "Monitoring-Intervalle", "spalten": 1,
                    "felder": [{"label": i["situation"][:100], "wert": f"{i['intervall']} · {i['umfang']} · "
                                                                       f"{i['profil']}"} for i in daten["intervalle"]],
                    "optionen": {"ueberschrift": True}})
    bloecke.append({"id": "fuss", "typ": "fusszeile", "bezeichnung": "Fußzeile", "text": _fuss()[1]["text"],
                    "rechts": _fuss()[1]["rechts"]})
    return {"quelle": "RC_Labor_MAL-00", "name": "Laborprofile Malabsorption – Übersicht und Regelwerk",
            "gruppe": "anforderungen", "beschreibung": "Übersicht der Profile MAL-01 bis MAL-06, Reflexregeln R1–R11 "
            "und Monitoring-Intervalle (Nachschlagen, Aushang)", "datei": daten["datei"], "bloecke": bloecke}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    daten = einlesen(Path(sys.argv[1]))
    ziel = Path(sys.argv[2]) if len(sys.argv) > 2 else STATISCH
    (ziel / "rgc").mkdir(parents=True, exist_ok=True)
    aus = ziel / "laborprofile-malabsorption.json"
    aus.write_text(json.dumps(daten, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{aus.name}: {len(daten['profile'])} Profile, {len(daten['parameter'])} Parameter, "
          f"{len(daten['regeln'])} Regeln")
    for vorlage in [uebersicht(daten)] + [bogen(daten, k, n, ids) for k, n, ids in BOEGEN]:
        aus = ziel / "rgc" / f"{vorlage['quelle']}.json"
        aus.write_text(json.dumps(vorlage, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{aus.name}: {len(vorlage['bloecke'])} Blöcke")


if __name__ == "__main__":
    main()
