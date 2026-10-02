"""
Übernahme der Altdaten – Datenbank und Dateien.

- ``dump_laden``            Dump lesen und speichern (Kennwort-Spalten werden vorher geleert)
- ``stand_berechnen``       Zuordnungen, offene Punkte, Protokoll und neue Datensätze (``umsetzung``)
- ``probelauf``             alles schreiben und wieder zurückrollen – zeigt, ob der Import durchläuft
- ``importiere``            schreiben; nur in ein System ohne echte Akten
- ``dokumente_*``           Dateien aus dem Dokumentenordner des Altsystems in Etappen übernehmen
- ``zuruecknehmen``         alles Übernommene wieder entfernen
- ``abschliessen``          Zurücknehmen sperren, Dump und Zuordnungen löschen

Geschrieben wird im Wartungsmodus der Datenbank: Übernommene Kontakte und Pläne tragen die Zeitpunkte und
Bearbeiter des Altsystems (die Trigger ließen das sonst nicht zu). Jeder Vorgang steht im Audit-Log.
"""
import hashlib
import logging
import os
import re
import shutil
import time
import uuid
from datetime import date
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import ProtectedError, RestrictedError
from django.utils import timezone

from accounts.models import User
from audit.bereinigung import akte_entfernen as protokoll_entfernen
from audit.models import SystemEreignis, protokolliere
from audit.schutz import wartungsmodus
from epm.sanitize import bereinige_html
from infusionen.models import Infusionsplan, InfusionsplanPosition
from patienten.models import TESTNUMMER_AB, Dokument, Gewichtsmessung, Kontakt, Loeschprotokoll, Patient
from stammdaten.models import Ansprechpartner, Auswahlwert, Einstellungen, Praeparat, Versorger

from . import dump, umsetzung
from . import werte as W
from .models import Alttabelle, Importlauf, Importobjekt, Importstand

log = logging.getLogger(__name__)
S = Importstand.Status
O = Importobjekt.Art
GRUND = umsetzung.GRUND
MB = 1024 * 1024
GRENZFELDER = ["gewicht_min_kg", "gewicht_max_kg", "groesse_min_cm", "groesse_max_cm", "kcal_min_tag", "kcal_max_tag",
               "glucose_min_g", "glucose_max_g", "aminosaeuren_min_g", "aminosaeuren_max_g", "lipide_min_g",
               "lipide_max_g", "natrium_min_mmol", "natrium_max_mmol", "kalium_min_mmol", "kalium_max_mmol",
               "volumen_min_ml", "volumen_max_ml"]


class Hindernis(Exception):
    """Der Vorgang ist so nicht möglich; die Meldung sagt, warum."""


class _Zurueck(Exception):
    """Probelauf: Alles Geschriebene wird wieder zurückgerollt."""


def melde(request, benutzer, text, **details):
    """Eintrag im Audit-Log (Gruppe „System“)."""
    protokolliere(SystemEreignis.Art.SYSTEM, request, benutzer=benutzer, objekt="Altdaten-Übernahme", ereignis="altdaten",
                  name=text, **details)


# ================================================================= Lesen
def bestand() -> dict:
    """Was es im EPM schon gibt – Grundlage für Vorschläge und für die Prüfung der Zuordnungen."""
    e = Einstellungen.aktuell()
    return {
        "benutzer": [{"id": u.id, "username": u.username, "vorname": u.first_name, "nachname": u.last_name,
                      "anzeigename": u.anzeigename, "rolle": u.rolle, "aktiv": u.is_active,
                      "nur_historisch": u.nur_historisch, "ist_test": u.ist_test}
                     for u in User.objects.order_by("last_name", "first_name", "username")],
        "versorger": list(Versorger.objects.order_by("name").values("id", "name", "aktiv")),
        "ansprechpartner": [{"id": a.id, "versorger": a.versorger_id, "name": a.name}
                            for a in Ansprechpartner.objects.order_by("name")],
        "katheter": list(Auswahlwert.objects.filter(liste=Auswahlwert.Liste.KATHETER).order_by("reihenfolge", "wert")
                         .values("id", "wert", "aktiv")),
        "praeparate": list(Praeparat.objects.order_by("kategorie", "reihenfolge", "name", "konzentration")
                           .values("id", "kategorie", "name", "konzentration", "aktiv")),
        "grenzen": {f: str(getattr(e, f)) for f in GRENZFELDER},
        "testnummer_ab": TESTNUMMER_AB,
    }


def tabellen() -> dict:
    return {t.name: {"spalten": t.spalten, "typen": t.typen, "entfernt": t.entfernt, "zeilen": t.zeilen}
            for t in Alttabelle.objects.all()}


def stand_berechnen(stand: Importstand | None = None, vorhandenes: dict | None = None) -> umsetzung.Ergebnis:
    stand = stand or Importstand.aktuell()
    return umsetzung.berechne(tabellen(), stand.zuordnung, vorhandenes or bestand(), W.ftfy_reparatur(),
                              timezone.localdate())


def echte_akten() -> dict:
    qs = Patient.objects.filter(ist_test=False)
    return {"anzahl": qs.count(), "nummern": list(qs.order_by("nummer").values_list("nummer", flat=True)[:20])}


def vorbedingungen(stand: Importstand, e: umsetzung.Ergebnis) -> list[str]:
    """Was den Import (und den Probelauf) verhindert. Leere Liste = es kann losgehen."""
    hindernisse = []
    if stand.status == S.LEER:
        return ["Es ist kein Dump geladen."]
    if stand.status == S.IMPORTIERT:
        return ["Die Altdaten sind bereits übernommen. Für einen neuen Lauf den Import zuerst zurücknehmen."]
    if stand.status == S.ABGESCHLOSSEN:
        return ["Die Übernahme ist abgeschlossen."]
    if e.offen:
        hindernisse.append(f"In den Zuordnungen sind noch {len(e.offen)} Punkte offen.")
    echte = echte_akten()
    if echte["anzahl"]:
        nummern = ", ".join(str(n) for n in echte["nummern"]) + (" …" if echte["anzahl"] > len(echte["nummern"]) else "")
        hindernisse.append(f"Im EPM gibt es {echte['anzahl']} echte Akten (Nr. {nummern}). Übernommen wird nur in ein "
                           f"System ohne echte Akten – die Patientennummern des Altsystems müssen frei sein.")
    nummern = {p["nummer"] for p in e.saetze.get("patienten", [])}
    if not nummern and not e.offen:
        hindernisse.append("Der Dump enthält keine Patienten, die übernommen werden.")
    vergeben = sorted(set(Loeschprotokoll.objects.filter(ist_test=False, nummer__in=nummern).values_list("nummer", flat=True)))
    if vergeben:
        hindernisse.append("Diese Patientennummern stehen im Löschprotokoll (endgültig gelöschte Akten) und werden nicht "
                           f"neu vergeben: {', '.join(str(n) for n in vergeben[:20])}.")
    return hindernisse


# ================================================================= Dump laden
@transaction.atomic
def dump_laden(daten: bytes, name: str, benutzer, request=None) -> Importstand:
    stand = Importstand.aktuell(sperren=True)
    if stand.status not in (S.LEER, S.GELADEN):
        raise Hindernis("Ein neuer Dump kann erst geladen werden, wenn der Import zurückgenommen ist."
                        if stand.status == S.IMPORTIERT else "Die Übernahme ist abgeschlossen.")
    ergebnis = dump.lies(daten)
    entfernt = dump.ohne_kennwoerter(ergebnis["tabellen"])
    zeit_hinweise = dump.zeitstempel_in_ortszeit(ergebnis["tabellen"], ergebnis.get("zeitzone"), settings.TIME_ZONE)
    Alttabelle.objects.all().delete()
    Alttabelle.objects.bulk_create([
        Alttabelle(name=n[:100], spalten=t["spalten"], typen=t.get("typen", {}), entfernt=t.get("entfernt", []),
                   zeilen=t["zeilen"]) for n, t in ergebnis["tabellen"].items()])
    hinweise = list(ergebnis["hinweise"])
    if entfernt:
        hinweise.append("Kennwörter werden nicht übernommen (Regel 1) – geleert und nicht gespeichert: "
                        + ", ".join(f"{t}.{s}" for t, s in entfernt) + ".")
    hinweise.extend(zeit_hinweise)
    stand.status = S.GELADEN
    stand.dump_name = (name or "dump.sql")[:255]
    stand.dump_sha256 = hashlib.sha256(daten).hexdigest()
    stand.dump_groesse = len(daten)
    stand.dump_geladen_am = timezone.now()
    stand.dump_geladen_von = benutzer
    stand.dump_hinweise = hinweise
    stand.save()
    zeilen = sum(len(t["zeilen"]) for t in ergebnis["tabellen"].values())
    melde(request, benutzer, f"Altdaten: Dump „{stand.dump_name}“ geladen ({len(ergebnis['tabellen'])} Tabellen, {zeilen} Zeilen)",
          sha256=stand.dump_sha256)
    return stand


@transaction.atomic
def dump_entfernen(benutzer, request=None) -> Importstand:
    stand = Importstand.aktuell(sperren=True)
    if stand.status != S.GELADEN:
        raise Hindernis("Es ist kein Dump geladen, der entfernt werden könnte." if stand.status == S.LEER
                        else "Der Dump wird erst nach dem Zurücknehmen oder mit dem Abschließen entfernt.")
    Alttabelle.objects.all().delete()
    melde(request, benutzer, f"Altdaten: Dump „{stand.dump_name}“ entfernt (Zuordnungen bleiben erhalten)")
    stand.status, stand.dump_name, stand.dump_sha256, stand.dump_groesse = S.LEER, "", "", 0
    stand.dump_geladen_am, stand.dump_geladen_von, stand.dump_hinweise = None, None, []
    stand.save()
    return stand


# ================================================================= Zuordnungen speichern
ZWEISTUFIG = {"spalten", "werte", "praeparate"}
BEREICHE = {"tabellen", "tabellen_ignoriert", "spalten", "spalten_ignoriert", "benutzer", "versorger", "werte",
            "praeparate", "geloeschte", "korrekturen"}


@transaction.atomic
def zuordnung_speichern(bereich: str, aenderungen, benutzer, request=None) -> Importstand:
    """Entscheidungen eines Bereichs übernehmen: ``{schlüssel: wert}``; ``None`` nimmt eine Entscheidung zurück
    (dann gilt wieder der Vorschlag). Bei „spalten“, „werte“ und „praeparate“ eine Ebene tiefer:
    ``{tabelle bzw. feld: {schlüssel: wert}}``. „tabellen_ignoriert“ und „spalten_ignoriert“ sind Listen."""
    stand = Importstand.aktuell(sperren=True)
    if stand.status in (S.IMPORTIERT, S.ABGESCHLOSSEN):
        raise Hindernis("Die Zuordnungen sind gesperrt, solange die Altdaten übernommen sind.")
    if bereich not in BEREICHE:
        raise Hindernis("Unbekannter Bereich.")
    z = dict(stand.zuordnung or {})
    if bereich == "tabellen_ignoriert":
        if not isinstance(aenderungen, list) or not all(isinstance(x, str) for x in aenderungen):
            raise Hindernis("Erwartet wird eine Liste von Tabellennamen.")
        z[bereich] = sorted(set(aenderungen))
    elif not isinstance(aenderungen, dict):
        raise Hindernis("Erwartet werden Zuordnungen als Objekt.")
    elif bereich == "spalten_ignoriert":
        ziel = dict(z.get(bereich) or {})
        for tabelle, liste in aenderungen.items():
            if not isinstance(liste, list) or not all(isinstance(x, str) for x in liste):
                raise Hindernis("Erwartet wird je Tabelle eine Liste von Spaltennamen.")
            ziel[str(tabelle)] = sorted(set(liste))
        z[bereich] = ziel
    else:
        if bereich == "korrekturen" and aenderungen:
            # Eine Korrektur gilt für genau den Wert, der jetzt im Dump steht (ein frischer Dump mit anderem Wert
            # macht sie unwirksam). Den Wert setzt der Server, nicht die Oberfläche.
            roh = {a["schluessel"]: a["roh"] for a in stand_berechnen(stand).auffaelligkeiten}
            for schluessel, wert in aenderungen.items():
                if wert is None:
                    continue
                if not isinstance(wert, dict) or wert.get("art") not in ("wert", "leer", "unveraendert", "auslassen"):
                    raise Hindernis("Unbekannte Entscheidung.")
                if schluessel not in roh:
                    raise Hindernis(f"Zu „{schluessel}“ gibt es keine Auffälligkeit (mehr). Bitte die Ansicht neu laden.")
                aenderungen[schluessel] = {"art": wert["art"], "alt": roh[schluessel],
                                           **({"wert": str(wert.get("wert", "")).strip()[:300]} if wert["art"] == "wert" else {})}
        ziel = dict(z.get(bereich) or {})
        for schluessel, wert in aenderungen.items():
            if bereich in ZWEISTUFIG:
                if not isinstance(wert, dict):
                    raise Hindernis("Erwartet werden Zuordnungen je Tabelle bzw. Feld.")
                innen = dict(ziel.get(schluessel) or {})
                for k, v in wert.items():
                    if v is None:
                        innen.pop(str(k), None)
                    else:
                        innen[str(k)] = v
                ziel[str(schluessel)] = innen
            elif wert is None:
                ziel.pop(str(schluessel), None)
            else:
                ziel[str(schluessel)] = wert
        z[bereich] = ziel
    stand.zuordnung = z
    stand.save()
    return stand


# ================================================================= Schreiben
def _zeit(wert):
    """Zeitpunkt des Altsystems (ohne Zeitzone, Ortszeit) als Zeitpunkt mit Zeitzone."""
    if wert is None:
        return None
    return timezone.make_aware(wert) if timezone.is_naive(wert) else wert


def _html(text: str) -> str:
    return bereinige_html(text) if text else ""


class _Schreiber:
    def __init__(self, e: umsetzung.Ergebnis, benutzer):
        self.s = e.saetze
        self.benutzer = benutzer
        self.jetzt = timezone.now()
        self.neu = {"benutzer": {}, "versorger": {}, "ansprechpartner": {}, "auswahlwerte": {}, "praeparate": {}}
        self.objekte = []
        self.personen = {}

    def kennung(self, ref, art):
        if not ref:
            return None
        return ref["id"] if "id" in ref else self.neu[art][ref["neu"]].id

    def person(self, ref):
        pk = self.kennung(ref, "benutzer")
        return self.personen.get(pk) if pk else None

    def merke(self, art, obj, schluessel):
        self.objekte.append(Importobjekt(art=art, objekt_id=obj.id, schluessel=str(schluessel)[:600]))

    def stamm(self, obj):
        obj._history_user = self.benutzer
        obj._change_reason = GRUND
        obj.save()
        return obj

    def alles(self) -> dict:
        self.stammdaten()
        self.patienten()
        self.gewichte()
        self.kontakte()
        self.plaene()
        Importobjekt.objects.bulk_create(self.objekte, batch_size=1000)
        return self.zahlen

    # ------------------------------------------------ Benutzer, Versorger, Auswahlwerte, Präparate
    def stammdaten(self):
        for b in self.s.get("benutzer", []):
            u = User(username=b["benutzername"], first_name=b["vorname"], last_name=b["nachname"], titel=b["titel"],
                     rolle=b["rolle"], nur_historisch=b["historisch"])
            u.set_unusable_password()
            u.save()
            self.neu["benutzer"][b["schluessel"]] = u
            self.merke(O.BENUTZER, u, b["schluessel"])
            if not b["historisch"]:
                protokolliere(SystemEreignis.Art.BENUTZER_ANGELEGT, benutzer=self.benutzer, objekt=u.username,
                              rolle=u.rolle, quelle="altdaten")
        for v in self.s.get("versorger", []):
            obj = self.stamm(Versorger(name=v["name"], telefon=v["telefon"], email=v["email"], notiz=v["notiz"]))
            self.neu["versorger"][v["schluessel"]] = obj
            self.merke(O.VERSORGER, obj, v["schluessel"])
        for a in self.s.get("ansprechpartner", []):
            obj = self.stamm(Ansprechpartner(versorger_id=self.kennung(a["versorger"], "versorger"), name=a["name"],
                                             telefon=a["telefon"], email=a["email"], notiz=a["notiz"]))
            self.neu["ansprechpartner"][a["schluessel"]] = obj
            self.merke(O.ANSPRECHPARTNER, obj, a["schluessel"])
        letzte = (Auswahlwert.objects.filter(liste=Auswahlwert.Liste.KATHETER).order_by("-reihenfolge")
                  .values_list("reihenfolge", flat=True).first() or 0)
        for i, w in enumerate(self.s.get("auswahlwerte", []), 1):
            obj = self.stamm(Auswahlwert(liste=w["liste"], wert=w["wert"], reihenfolge=min(letzte + 10 * i, 32000)))
            self.neu["auswahlwerte"][w["schluessel"]] = obj
            self.merke(O.AUSWAHLWERT, obj, f"{w['liste']}:{w['schluessel']}")
        for p in self.s.get("praeparate", []):
            obj = self.stamm(Praeparat(kategorie=p["kategorie"], name=p["name"], konzentration=p["konzentration"]))
            self.neu["praeparate"][p["schluessel"]] = obj
            self.merke(O.PRAEPARAT, obj, p["schluessel"])
        # alle Personen, die als Bearbeiter vorkommen (für die Historie braucht es die Objekte)
        ids = {u.id for u in self.neu["benutzer"].values()}
        for art in ("patienten", "gewichte", "kontakte", "plaene"):
            for s in self.s.get(art, []):
                for feld in ("bearbeiter", "ersteller"):
                    ref = s.get(feld)
                    if ref and "id" in ref:
                        ids.add(ref["id"])
        self.personen = User.objects.in_bulk(ids)
        self.zahlen = {"benutzer": len(self.neu["benutzer"]), "versorger": len(self.neu["versorger"]),
                       "ansprechpartner": len(self.neu["ansprechpartner"]),
                       "auswahlwerte": len(self.neu["auswahlwerte"]), "praeparate": len(self.neu["praeparate"])}

    # ------------------------------------------------ Akten
    def patienten(self):
        objs = []
        for s in self.s.get("patienten", []):
            p = Patient(
                nummer=s["nummer"], nachname=s["nachname"], vorname=s["vorname"], geburtsdatum=s["geburtsdatum"],
                geschlecht=s["geschlecht"], strasse=s["strasse"], plz=s["plz"], ort=s["ort"], telefon=s["telefon"],
                email=s["email"], hausarzt=s["hausarzt"], ueberweisung_durch=s["ueberweisung_durch"],
                groesse_cm=s["groesse_cm"], katheter_id=self.kennung(s["katheter"], "auswahlwerte"),
                versorger_id=self.kennung(s["versorger"], "versorger"),
                ansprechpartner_id=self.kennung(s["ansprechpartner"], "ansprechpartner"),
                nickelallergie=s["nickelallergie"], kein_katheter=s["kein_katheter"], kein_versorger=s["kein_versorger"],
                diagnose=_html(s["diagnose"]), therapie=_html(s["therapie"]), empfehlung=_html(s["empfehlung"]),
                bemerkung=_html("".join(s["bemerkung"])), ist_test=False)
            if s["abschluss"]:
                p.abgeschlossen_am = s["abschluss"]["am"]
                p.abschluss_anlass = s["abschluss"]["anlass"]
                p.abschluss_notiz = s["abschluss"]["notiz"]
            p._history_user = self.person(s["bearbeiter"])
            p._history_date = _zeit(s["geaendert"]) or self.jetzt
            p._change_reason = f"{GRUND} (Stand der letzten Änderung dort)"
            objs.append(p)
        Patient.objects.bulk_create(objs, batch_size=200)
        Patient.history.bulk_history_create(objs, batch_size=200)
        self.akte = {p.nummer: p.id for p in objs}
        for p, s in zip(objs, self.s.get("patienten", [])):
            self.merke(O.PATIENT, p, s["alt"])
        self.zahlen["patienten"] = len(objs)
        self.zahlen["abgeschlossen"] = sum(1 for p in objs if p.abgeschlossen_am)

    def gewichte(self):
        saetze = self.s.get("gewichte", [])
        objs = [Gewichtsmessung(patient_id=self.akte[s["patient"]], gewicht_kg=s["gewicht_kg"], gemessen_am=s["gemessen_am"],
                                datum_ungenau=True, quelle=Gewichtsmessung.Quelle.ALTSYSTEM,
                                erfasst_von_id=self.kennung(s["bearbeiter"], "benutzer")) for s in saetze]
        Gewichtsmessung.objects.bulk_create(objs, batch_size=1000)
        for o, s in zip(objs, saetze):
            o.erfasst_am = _zeit(s["zeit"])
            o._history_user, o._history_date, o._change_reason = self.person(s["bearbeiter"]), o.erfasst_am, GRUND
        Gewichtsmessung.objects.bulk_update(objs, ["erfasst_am"], batch_size=1000)
        Gewichtsmessung.history.bulk_history_create(objs, batch_size=1000)
        self.zahlen["gewichte"] = len(objs)

    def kontakte(self):
        saetze = self.s.get("kontakte", [])
        objs = [Kontakt(patient_id=self.akte[s["patient"]], zeitpunkt=_zeit(s["zeit"]), text=_html(s["text"]),
                        erfasst_von_id=self.kennung(s["bearbeiter"], "benutzer")) for s in saetze]
        Kontakt.objects.bulk_create(objs, batch_size=500)
        for o, s in zip(objs, saetze):
            o.erfasst_am = o.zeitpunkt
            o._history_user, o._history_date, o._change_reason = self.person(s["bearbeiter"]), o.zeitpunkt, GRUND
        Kontakt.objects.bulk_update(objs, ["erfasst_am"], batch_size=500)
        Kontakt.history.bulk_history_create(objs, batch_size=500)
        self.zahlen["kontakte"] = len(objs)

    PLANFELDER = ["basis_ml", "glucose_g", "aminosaeuren_g", "lipide_g", "albumin_ml", "natrium_mmol", "kalium_mmol",
                  "phosphat_mmol", "calcium_mmol", "magnesium_mmol", "kcal_manuell", "laufzeit_h", "pantozol_stufe",
                  "pantozol_tage", "gesamtvolumen_ml"]
    PLANPRAEPARATE = ["basis_praeparat", "glucose_praeparat", "aminosaeuren_praeparat", "lipide_praeparat",
                      "albumin_praeparat", "spurenelemente", "katheterschutz"]

    def plaene(self):
        saetze = self.s.get("plaene", [])
        objs = []
        for s in saetze:
            plan = Infusionsplan(
                patient_id=self.akte[s["patient"]], status=s["status"], gueltig_ab=s["gueltig_ab"],
                herkunft=Infusionsplan.Herkunft.ALTSYSTEM, erstellt_von_id=self.kennung(s["ersteller"], "benutzer"),
                bemerkung=_html(s["bemerkung"] + "".join(s["bemerkung_extras"])),
                **{f: s[f] for f in self.PLANFELDER},
                **{f"{f}_id": self.kennung(s[f], "praeparate") for f in self.PLANPRAEPARATE})
            objs.append(plan)
        Infusionsplan.objects.bulk_create(objs, batch_size=200)
        je_alt = {s["alt"]: plan for plan, s in zip(objs, saetze)}
        for plan, s in zip(objs, saetze):
            plan.erstellt_am = _zeit(s["erstellt"])
            plan.vorgaenger_id = je_alt[s["vorgaenger"]].id if s["vorgaenger"] else None
            plan._history_user, plan._history_date = self.person(s["bearbeiter"]), _zeit(s["geaendert"])
            plan._change_reason = GRUND
        Infusionsplan.objects.bulk_update(objs, ["erstellt_am", "vorgaenger"], batch_size=200)
        # Vitamine (Zuordnungstabelle) und weitere Bestandteile
        durch = Infusionsplan.vitamine.through
        zeilen = [durch(infusionsplan_id=plan.id, praeparat_id=self.kennung(ref, "praeparate"))
                  for plan, s in zip(objs, saetze) for ref in s["vitamine"]]
        durch.objects.bulk_create(zeilen, batch_size=1000)
        positionen = []
        for plan, s in zip(objs, saetze):
            for i, pos in enumerate(s["positionen"]):
                x = InfusionsplanPosition(plan_id=plan.id, praeparat_id=self.kennung(pos["praeparat"], "praeparate"),
                                          bemerkung=pos["bemerkung"], reihenfolge=i)
                x._history_user, x._history_date, x._change_reason = plan._history_user, plan._history_date, GRUND
                positionen.append(x)
        InfusionsplanPosition.objects.bulk_create(positionen, batch_size=1000)
        # Historie: je Plan eine Fassung mit ihren Vitaminen (sonst erschienen sie beim Ablösen als „geändert“)
        fassungen = Infusionsplan.history.bulk_history_create(objs, batch_size=200)
        je_plan = {h.id: h for h in fassungen}
        hist_vitamine = apps.get_model("infusionen", "HistoricalInfusionsplan_vitamine")
        hist_vitamine.objects.bulk_create(
            [hist_vitamine(history=je_plan[z.infusionsplan_id], id=z.id, infusionsplan_id=z.infusionsplan_id,
                           praeparat_id=z.praeparat_id) for z in zeilen], batch_size=1000)
        InfusionsplanPosition.history.bulk_history_create(positionen, batch_size=1000)
        self.zahlen.update(plaene=len(objs), vitamine=len(zeilen), positionen=len(positionen))


def _pruefe_geschrieben(e: umsetzung.Ergebnis, geschrieben: dict):
    """Zählung nach dem Schreiben: In der Datenbank muss stehen, was die Umsetzung vorgesehen hat."""
    ids = list(Importobjekt.objects.filter(art=O.PATIENT).values_list("objekt_id", flat=True))
    ist = {
        "patienten": Patient.objects.filter(id__in=ids, ist_test=False).count(),
        "gewichte": Gewichtsmessung.objects.filter(patient_id__in=ids).count(),
        "kontakte": Kontakt.objects.filter(patient_id__in=ids).count(),
        "plaene": Infusionsplan.objects.filter(patient_id__in=ids).count(),
    }
    soll = {k: len(e.saetze.get(k, [])) for k in ist}
    if ist != soll or any(geschrieben.get(k) != v for k, v in soll.items()):
        raise RuntimeError(f"Zählung stimmt nicht: vorgesehen {soll}, in der Datenbank {ist}.")
    historie = Patient.history.filter(id__in=ids).count()
    if historie != soll["patienten"]:
        raise RuntimeError(f"Historie unvollständig: {historie} Fassungen für {soll['patienten']} Akten.")


def _fehlertext(f: Exception) -> str:
    """Fehler für das Protokoll des Laufs. Bei Datenbankfehlern nur die erste Zeile: PostgreSQL nennt darunter die
    ganze betroffene Zeile („Failing row contains …“) – Patientendaten gehören nicht ins Protokoll."""
    text = str(f).strip()
    if isinstance(f, DatabaseError):
        erste = text.splitlines()[0] if text else ""
        return f"{type(f).__name__}: {erste[:500]} (Einzelheiten im Protokoll des Servers)"
    return f"{type(f).__name__}: {text[:2000]}"


def _lauf(art, benutzer, stand) -> Importlauf:
    return Importlauf(art=art, benutzer=benutzer, dump_name=stand.dump_name, dump_sha256=stand.dump_sha256)


def probelauf(benutzer) -> Importlauf:
    """Alles schreiben wie beim Import – und wieder zurückrollen. Zeigt Zählung, Protokoll und jeden Fehler."""
    stand = Importstand.aktuell()
    e = stand_berechnen(stand) if stand.status == S.GELADEN else umsetzung.Ergebnis()
    lauf = _lauf(Importlauf.Art.PROBELAUF, benutzer, stand)
    lauf.zahlen, lauf.protokoll = dict(e.zahlen), e.protokoll
    hindernisse = vorbedingungen(stand, e)
    if hindernisse:
        lauf.fehler = "\n".join(hindernisse + [o["text"] for o in e.offen])
    else:
        try:
            with transaction.atomic():
                with wartungsmodus():
                    geschrieben = _Schreiber(e, benutzer).alles()
                    _pruefe_geschrieben(e, geschrieben)
                lauf.zahlen["geschrieben"] = geschrieben
                raise _Zurueck
        except _Zurueck:
            lauf.erfolgreich = True
        except Exception as f:  # noqa: BLE001 – der Probelauf soll jeden Fehler zeigen, nicht abbrechen
            log.exception("Probelauf der Altdaten-Übernahme fehlgeschlagen")
            lauf.fehler = _fehlertext(f)
    lauf.beendet_am = timezone.now()
    lauf.save()
    return lauf


@transaction.atomic
def importiere(benutzer, request=None) -> Importlauf:
    """Die Altdaten übernehmen. Schlägt etwas fehl, bleibt die Datenbank unverändert; der Lauf hält den Fehler fest."""
    stand = Importstand.aktuell(sperren=True)
    e = stand_berechnen(stand)
    hindernisse = vorbedingungen(stand, e)
    if hindernisse:
        raise Hindernis(" ".join(hindernisse))
    lauf = _lauf(Importlauf.Art.IMPORT, benutzer, stand)
    lauf.zahlen, lauf.protokoll = dict(e.zahlen), e.protokoll
    try:
        with transaction.atomic():
            with wartungsmodus():
                geschrieben = _Schreiber(e, benutzer).alles()
                _pruefe_geschrieben(e, geschrieben)
            lauf.zahlen["geschrieben"] = geschrieben
            stand.status, stand.importiert_am, stand.importiert_von = S.IMPORTIERT, timezone.now(), benutzer
            stand.save()
            melde(request, benutzer,
                  f"Altdaten übernommen: {geschrieben['patienten']} Akten ({geschrieben['abgeschlossen']} abgeschlossen), "
                  f"{geschrieben['gewichte']} Gewichte, {geschrieben['kontakte']} Kontakte, {geschrieben['plaene']} Infusionspläne",
                  sha256=stand.dump_sha256, geschrieben=geschrieben)
        lauf.erfolgreich = True
    except Exception as f:  # noqa: BLE001 – Fehler festhalten statt einer Seite „Serverfehler“
        log.exception("Import der Altdaten fehlgeschlagen")
        lauf.fehler = _fehlertext(f)
    lauf.beendet_am = timezone.now()
    lauf.save()
    return lauf


# ================================================================= Zurücknehmen und Abschließen
def uebernommene_akten():
    return Patient.objects.filter(id__in=Importobjekt.objects.filter(art=O.PATIENT).values("objekt_id"))


def bestand_der_uebernahme() -> dict:
    """Was in den übernommenen Akten jetzt steht – zeigt vor dem Zurücknehmen, was verloren ginge."""
    ids = list(uebernommene_akten().values_list("id", flat=True))
    return {
        "patienten": len(ids),
        "gewichte": Gewichtsmessung.objects.filter(patient_id__in=ids).count(),
        "kontakte": Kontakt.objects.filter(patient_id__in=ids).count(),
        "plaene": Infusionsplan.objects.filter(patient_id__in=ids).count(),
        "dokumente": Dokument.objects.filter(patient_id__in=ids).count(),
    }


def _entferne_wenn_unbenutzt(modell, pk) -> bool:
    """Vom Import angelegte Stammdaten wieder entfernen – nur wenn nichts mehr darauf verweist."""
    if modell is Praeparat and Infusionsplan.vitamine.through.objects.filter(praeparat_id=pk).exists():
        return False
    if modell is User:
        u = User.objects.filter(pk=pk).first()
        if u is None or u.last_login is not None:
            return False
    try:
        with transaction.atomic():
            modell.objects.filter(pk=pk).delete()
            if hasattr(modell, "history"):
                modell.history.filter(id=pk).delete()
    except (ProtectedError, RestrictedError):
        return False
    return True


@transaction.atomic
def zuruecknehmen(benutzer, request=None) -> Importlauf:
    """Alles Übernommene wieder entfernen: Akten mit allen Einträgen, Historie und Dateien – auch das, was seit dem
    Import in diesen Akten erfasst wurde. Vom Import angelegte Benutzer, Versorger, Auswahlwerte und Präparate
    verschwinden, soweit nichts anderes sie verwendet. Der Dump und die Zuordnungen bleiben."""
    from patienten.datenschutz import akten_entfernen, dateien_entfernen, eigene_dokumente

    stand = Importstand.aktuell(sperren=True)
    if stand.status != S.IMPORTIERT:
        raise Hindernis("Die Übernahme ist abgeschlossen und kann nicht mehr zurückgenommen werden."
                        if stand.status == S.ABGESCHLOSSEN else "Es ist nichts übernommen, das zurückgenommen werden könnte.")
    lauf = _lauf(Importlauf.Art.ZURUECKGENOMMEN, benutzer, stand)
    vorher = bestand_der_uebernahme()
    akten = list(uebernommene_akten().values_list("id", "nummer", "nachname", "vorname"))
    ids = [a[0] for a in akten]
    behalten = {}
    with wartungsmodus():
        dokumente = {pid: sorted(eigene_dokumente([pid])) for pid in ids}
        akten_entfernen(ids)
        # Audit-Log: Einträge zu diesen Akten bleiben (wer, wann, was), verlieren aber Namen und Inhalte
        bereinigt = sum(protokoll_entfernen(pid, nummer, dokumente[pid], namen=(nach, vor))
                        for pid, nummer, nach, vor in akten)
        for art, modell in ((O.ANSPRECHPARTNER, Ansprechpartner), (O.VERSORGER, Versorger), (O.AUSWAHLWERT, Auswahlwert),
                            (O.PRAEPARAT, Praeparat), (O.BENUTZER, User)):
            for pk in Importobjekt.objects.filter(art=art).values_list("objekt_id", flat=True):
                if not _entferne_wenn_unbenutzt(modell, pk):
                    behalten[art] = behalten.get(art, 0) + 1
        Importobjekt.objects.all().delete()
    # eine begonnene Dokumentenübernahme gehört zu diesem Import – sie wird nicht mit dem nächsten fortgesetzt
    Importlauf.objects.filter(art=Importlauf.Art.DOKUMENTE, beendet_am__isnull=True).update(
        beendet_am=timezone.now(), fehler="Nicht abgeschlossen: Der Import wurde zurückgenommen.")
    for _, nummer, _, _ in akten:
        transaction.on_commit(lambda n=nummer: dateien_entfernen(n), robust=True)
    stand.status = S.GELADEN if Alttabelle.objects.exists() else S.LEER
    stand.importiert_am, stand.importiert_von = None, None
    stand.save()
    lauf.zahlen = {"entfernt": vorher, "behalten": behalten, "protokolleintraege": bereinigt}
    lauf.erfolgreich, lauf.beendet_am = True, timezone.now()
    lauf.save()
    melde(request, benutzer,
          f"Übernahme der Altdaten zurückgenommen: {vorher['patienten']} Akten mit {vorher['gewichte']} Gewichten, "
          f"{vorher['kontakte']} Kontakten, {vorher['plaene']} Infusionsplänen und {vorher['dokumente']} Dokumenten entfernt",
          entfernt=vorher, behalten=behalten)
    return lauf


@transaction.atomic
def abschliessen(benutzer, request=None, ohne_dokumente: bool = False) -> Importlauf:
    """Go-live: Die Übernahme gilt. Zurücknehmen ist danach nicht mehr möglich; der Dump, die Zuordnungen und die
    Einzelheiten der Protokolle (Nummern) werden gelöscht – es bleiben die Zählungen."""
    stand = Importstand.aktuell(sperren=True)
    if stand.status != S.IMPORTIERT:
        raise Hindernis("Abschließen ist erst möglich, wenn die Altdaten übernommen sind."
                        if stand.status != S.ABGESCHLOSSEN else "Die Übernahme ist bereits abgeschlossen.")
    offen = dokumente_stand(stand)
    if offen["vorhanden"] and (offen["offen"] or offen["unlesbar"]) and not ohne_dokumente:
        raise Hindernis(f"Es sind noch {offen['offen']} Dokumente nicht übernommen und {offen['unlesbar']} Ordner oder "
                        f"Dateien nicht lesbar. Bitte zuerst die Dokumente übernehmen – oder ausdrücklich ohne sie abschließen.")
    lauf = _lauf(Importlauf.Art.ABGESCHLOSSEN, benutzer, stand)
    lauf.zahlen = {"bestand": bestand_der_uebernahme(), "dokumente_offen": offen["offen"] if offen["vorhanden"] else 0,
                   "dokumente_unlesbar": offen["unlesbar"] if offen["vorhanden"] else 0}
    Alttabelle.objects.all().delete()
    Importobjekt.objects.all().delete()
    # Protokolle: Zählungen bleiben; einzelne Nummern (Beispiele) und Fehlertexte mit Nummern verschwinden
    for alt in Importlauf.objects.all():
        alt.protokoll = [{**p, "beispiele": []} for p in (alt.protokoll or []) if isinstance(p, dict)]
        if alt.fehler:
            alt.fehler = "Nicht erfolgreich (Einzelheiten mit dem Abschließen entfernt)."
        alt.save(update_fields=["protokoll", "fehler"])
    Importlauf.objects.filter(art=Importlauf.Art.DOKUMENTE, beendet_am__isnull=True).update(
        beendet_am=timezone.now(), fehler="Nicht abgeschlossen: Die Übernahme wurde ohne die offenen Dokumente abgeschlossen.")
    stand.status, stand.zuordnung, stand.dump_hinweise = S.ABGESCHLOSSEN, {}, []
    stand.abgeschlossen_am, stand.abgeschlossen_von = timezone.now(), benutzer
    stand.save()
    lauf.erfolgreich, lauf.beendet_am = True, timezone.now()
    lauf.save()
    melde(request, benutzer, "Übernahme der Altdaten abgeschlossen: Zurücknehmen gesperrt, Dump und Zuordnungen gelöscht",
          bestand=lauf.zahlen["bestand"])
    return lauf


# ================================================================= Dokumente
NICHT_ERLAUBT = {".php", ".php3", ".php4", ".php5", ".phtml", ".htm", ".html", ".js", ".svg"}
_PDF_DATUM = [re.compile(rb"/CreationDate\s*\(\s*D:(\d{4})(\d{2})(\d{2})"),
              re.compile(rb"<xmp:CreateDate>\s*(\d{4})-(\d{2})-(\d{2})"),
              re.compile(rb"/ModDate\s*\(\s*D:(\d{4})(\d{2})(\d{2})")]


def dokumentenordner() -> Path:
    return Path(settings.EPM_IMPORT) / "PatData"


def dateityp(pfad: Path) -> str | None:
    """Dateityp am Inhalt: PDF, Bilder, Text – wie beim Hochladen in der Akte, dazu GIF, BMP, TIFF und WebP."""
    from patienten.api import erkenne_dateityp

    with open(pfad, "rb") as f:
        kopf = f.read(16)
        if kopf.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if kopf.startswith((b"II*\x00", b"MM\x00*")):
            return "image/tiff"
        if kopf.startswith(b"RIFF") and kopf[8:12] == b"WEBP":
            return "image/webp"
        if kopf.startswith(b"BM") and pfad.suffix.lower() == ".bmp":
            return "image/bmp"
        return erkenne_dateityp(f)


def _gueltig(jahr, monat, tag) -> date | None:
    try:
        d = date(int(jahr), int(monat), int(tag))
    except ValueError:
        return None
    return d if date(1980, 1, 1) <= d <= timezone.localdate() else None


def dokumentdatum(pfad: Path, mime: str) -> tuple[date, str]:
    """Datum des Dokuments aus den Metadaten (PDF-Info, EXIF), sonst das Dateidatum – mit der Quelle."""
    Q = Dokument.DatumQuelle
    try:
        if mime == "application/pdf":
            groesse = pfad.stat().st_size
            with open(pfad, "rb") as f:
                teile = [f.read(MB)]
                if groesse > MB:
                    f.seek(max(MB, groesse - MB))
                    teile.append(f.read(MB))
            for muster in _PDF_DATUM:
                for teil in teile:
                    m = muster.search(teil)
                    d = _gueltig(*m.groups()) if m else None
                    if d:
                        return d, Q.PDF
        elif mime in ("image/jpeg", "image/tiff", "image/png", "image/webp"):
            from PIL import Image

            with Image.open(pfad) as bild:
                exif = bild.getexif()
                roh = exif.get_ifd(0x8769).get(36867) or exif.get(306)
            m = re.match(r"(\d{4}):(\d{2}):(\d{2})", str(roh or ""))
            d = _gueltig(*m.groups()) if m else None
            if d:
                return d, Q.EXIF
    except Exception:  # noqa: BLE001 – unlesbare Metadaten sind kein Hindernis: dann gilt das Dateidatum
        pass
    return date.fromtimestamp(pfad.stat().st_mtime), Q.DATEIDATUM


def _lesbar(name: str) -> str:
    """Datei- oder Ordnername für Anzeige, Titel und Schlüssel. Namen, die auf dem Server nicht als UTF-8 vorliegen
    (alte Kodierung des Altsystems), werden als Windows-1252 gelesen – sonst ließen sie sich nicht speichern."""
    def teil(t):
        try:
            t.encode("utf-8")
            return t
        except UnicodeEncodeError:
            return os.fsencode(t).decode("cp1252", "replace")

    return "/".join(teil(t) for t in name.split("/"))


def _ordnerschluessel(name: str) -> str:
    """Ordnername → Patientennummer des Altsystems („007“ = „7“); anderes bleibt, wie es ist."""
    if name.isdecimal():
        try:
            return str(int(name))
        except ValueError:
            pass
    return _lesbar(name)


def dokumente_stand(stand: Importstand | None = None, mit_dateien: bool = False) -> dict:
    """Überblick über den Dokumentenordner: was da ist, was schon übernommen ist, was nicht übernommen wird.
    Die Ordner tragen die Patientennummer des ALTsystems – zugeordnet wird über das, was der Import zu jedem
    übernommenen Patienten festgehalten hat (auch wenn die Nummer bei der Übernahme korrigiert wurde)."""
    stand = stand or Importstand.aktuell()
    wurzel = dokumentenordner()
    aus = {"vorhanden": wurzel.is_dir(), "pfad": str(wurzel), "ordner": 0, "dateien": 0, "bytes": 0, "erledigt": 0,
           "offen": 0, "offen_bytes": 0, "ohne_patient": [], "nicht_uebernommen": [], "nicht_uebernommen_anzahl": 0,
           "ohne_patient_anzahl": 0, "unlesbar": 0, "frei_bytes": None}
    if not aus["vorhanden"]:
        return aus
    try:
        eintraege = sorted(os.scandir(wurzel), key=lambda x: x.name)
    except OSError:
        aus["vorhanden"] = False   # vorhanden, aber für das Backend nicht lesbar: wie „fehlt“ (Hinweis in der Oberfläche)
        return aus
    try:
        aus["frei_bytes"] = shutil.disk_usage(settings.EPM_DOKUMENTE).free
    except OSError:
        pass
    akten = None
    if stand.status == S.IMPORTIERT:
        nummern = dict(uebernommene_akten().values_list("id", "nummer"))
        akten = {schluessel: (pk, nummern[pk]) for schluessel, pk in
                 Importobjekt.objects.filter(art=O.PATIENT).values_list("schluessel", "objekt_id") if pk in nummern}
    erledigt = set(Importobjekt.objects.filter(art=O.DATEI).values_list("schluessel", flat=True))
    offen = []

    def nicht(pfad, grund, unlesbar=False):
        aus["nicht_uebernommen_anzahl"] += 1
        aus["unlesbar"] += 1 if unlesbar else 0
        if len(aus["nicht_uebernommen"]) < 100:
            aus["nicht_uebernommen"].append({"pfad": _lesbar(pfad), "grund": grund})

    def relativ(pfad) -> str:
        return Path(pfad).relative_to(wurzel).as_posix()

    for eintrag in eintraege:
        if eintrag.is_symlink():
            nicht(eintrag.name, "Verknüpfung – wird nicht verfolgt")
            continue
        if not eintrag.is_dir(follow_symlinks=False):
            nicht(eintrag.name, "liegt nicht in einem Patientenordner")
            continue
        aus["ordner"] += 1
        schluessel = _ordnerschluessel(eintrag.name)
        dateien, fehler = [], []
        for ordner, unterordner, namen in os.walk(eintrag.path, followlinks=False, onerror=fehler.append):
            unterordner.sort()
            for name in unterordner:
                if os.path.islink(os.path.join(ordner, name)):
                    nicht(relativ(os.path.join(ordner, name)), "Verknüpfung auf einen Ordner – wird nicht verfolgt")
            for name in sorted(namen):
                voll = Path(ordner) / name
                dateien.append((voll, _lesbar(relativ(voll))))
        for f in fehler:
            nicht(relativ(f.filename) if f.filename else eintrag.name, "Ordner nicht lesbar (Zugriffsrechte)", unlesbar=True)
        aus["dateien"] += len(dateien)
        if akten is not None and schluessel not in akten:
            aus["ohne_patient_anzahl"] += 1
            if len(aus["ohne_patient"]) < 100:
                aus["ohne_patient"].append({"ordner": _lesbar(eintrag.name), "dateien": len(dateien)})
            continue
        for voll, rel in dateien:
            try:
                if voll.is_symlink() or not voll.is_file():
                    nicht(rel, "Verknüpfung, keine Datei")
                    continue
                groesse = voll.stat().st_size
                aus["bytes"] += groesse
                if rel in erledigt:
                    aus["erledigt"] += 1
                elif groesse == 0:
                    nicht(rel, "leere Datei")
                elif voll.suffix.lower() in NICHT_ERLAUBT:
                    nicht(rel, "Dateityp war schon im Altsystem nicht zugelassen")
                elif dateityp(voll) is None:
                    nicht(rel, "Dateityp wird vom EPM nicht angenommen (PDF, Bilder und Text)")
                else:
                    aus["offen"] += 1
                    aus["offen_bytes"] += groesse
                    if mit_dateien:
                        offen.append((voll, rel, schluessel, groesse))
            except OSError:
                nicht(rel, "Datei nicht lesbar (Zugriffsrechte)", unlesbar=True)
    if mit_dateien:
        aus["_offen"] = offen
        aus["_akten"] = akten or {}
    return aus


def _kopiere(quelle: Path, ziel: Path) -> str:
    """Datei ins Dokumentenverzeichnis kopieren (erst vollständig, dann umbenennen) → SHA-256."""
    ziel.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    h = hashlib.sha256()
    tmp = ziel.with_name(f".import-{ziel.name}")
    try:
        with open(quelle, "rb") as ein, open(tmp, "wb") as aus:
            for teil in iter(lambda: ein.read(1 << 20), b""):
                h.update(teil)
                aus.write(teil)
            aus.flush()
            os.fsync(aus.fileno())
        os.chmod(tmp, 0o640)
        os.replace(tmp, ziel)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return h.hexdigest()


@transaction.atomic
def dokumente_uebernehmen(benutzer, request=None, max_dateien=200, max_bytes=256 * MB, max_sekunden=20) -> dict:
    """Die nächste Etappe der Dokumente übernehmen (fortsetzbar: jede Datei wird nur einmal übernommen).
    Titel = Dateiname, Typ „Sonstiges“, Datum aus den Metadaten bzw. Dateidatum; „Typ geprüft“ bleibt offen, damit
    die Dokumente unter „Nach und nach prüfen“ erscheinen."""
    stand = Importstand.aktuell(sperren=True)
    if stand.status != S.IMPORTIERT:
        raise Hindernis("Dokumente werden übernommen, nachdem die Altdaten importiert sind."
                        if stand.status != S.ABGESCHLOSSEN else "Die Übernahme ist abgeschlossen.")
    uebersicht = dokumente_stand(stand, mit_dateien=True)
    if not uebersicht["vorhanden"]:
        raise Hindernis(f"Der Dokumentenordner {uebersicht['pfad']} ist auf dem Server nicht vorhanden.")
    offen, akten = uebersicht.pop("_offen"), uebersicht.pop("_akten")
    typ, _ = Auswahlwert.objects.get_or_create(liste=Auswahlwert.Liste.DOKUMENTTYP, wert="Sonstiges",
                                               defaults={"reihenfolge": 990})
    beginn = time.monotonic()
    neu, kopiert, summe, schluessel, probleme = [], [], 0, [], []
    frei = uebersicht["frei_bytes"]
    reparatur = W.ftfy_reparatur()
    try:
        for voll, relativ, alt, groesse in offen:
            if len(neu) >= max_dateien or (neu and summe + groesse > max_bytes) or time.monotonic() - beginn > max_sekunden:
                break
            if frei is not None and frei - summe - groesse < 200 * MB:
                raise Hindernis("Der Speicherplatz für Dokumente reicht nicht mehr (weniger als 200 MB frei).")
            patient_id, nummer = akten[alt]
            endung = "".join(c for c in voll.suffix[1:] if c.isascii() and c.isalnum())[:10].lower()
            datei = f"{nummer}/{uuid.uuid4().hex}{'.' + endung if endung else ''}"
            ziel = settings.EPM_DOKUMENTE / datei
            try:
                mime = dateityp(voll)
                if mime is None:
                    raise OSError("Dateityp nicht mehr erkennbar")
                datum, quelle = dokumentdatum(voll, mime)
                sha = _kopiere(voll, ziel)
            except OSError as f:
                # eine einzelne Datei hält die Übernahme nicht auf; sie bleibt offen und wird genannt
                log.warning("Altdaten: Datei nicht übernommen (%s): %s", type(f).__name__, relativ)
                probleme.append({"pfad": relativ, "grund": "beim Kopieren nicht lesbar"})
                continue
            kopiert.append(ziel)
            name = Path(relativ).name
            unterpfad = Path(relativ).relative_to(Path(relativ).parts[0])
            titel = unterpfad.with_suffix("").as_posix() or name
            if reparatur is not None and W.VERDACHT.search(titel):
                titel = reparatur(titel)   # Regel 3 gilt auch für Dateinamen (der Originalname bleibt, wie er war)
            d = Dokument(patient_id=patient_id, typ=typ, titel=titel[:200],
                         datum=datum, datei=datei, originalname=name[:255], mime=mime, groesse=groesse, sha256=sha,
                         herkunft=Dokument.Herkunft.ALTSYSTEM, datum_quelle=quelle, typ_geprueft=False)
            d._history_user, d._change_reason = None, GRUND
            neu.append(d)
            schluessel.append(relativ)
            summe += groesse
        Dokument.objects.bulk_create(neu, batch_size=200)
        Dokument.history.bulk_history_create(neu, batch_size=200)
        Importobjekt.objects.bulk_create([Importobjekt(art=O.DATEI, objekt_id=d.id, schluessel=s[:600])
                                          for d, s in zip(neu, schluessel)], batch_size=500)
    except BaseException:
        for ziel in kopiert:
            ziel.unlink(missing_ok=True)
        raise
    rest = uebersicht["offen"] - len(neu)
    ergebnis = {"uebernommen": len(neu), "bytes": summe, "offen": max(rest, 0),
                "offen_bytes": uebersicht["offen_bytes"] - summe, "erledigt": uebersicht["erledigt"] + len(neu),
                "fertig": rest <= 0, "probleme": probleme[:50]}
    lauf = Importlauf.objects.filter(art=Importlauf.Art.DOKUMENTE, beendet_am__isnull=True).order_by("-id").first()
    if lauf is None:
        if not neu:
            return ergebnis   # nichts zu tun und kein offener Lauf
        lauf = _lauf(Importlauf.Art.DOKUMENTE, benutzer, stand)
    zahlen = dict(lauf.zahlen or {})
    zahlen["dateien"] = zahlen.get("dateien", 0) + len(neu)
    zahlen["bytes"] = zahlen.get("bytes", 0) + summe
    zahlen["nicht_uebernommen"] = uebersicht["nicht_uebernommen_anzahl"]
    zahlen["ordner_ohne_patient"] = uebersicht["ohne_patient_anzahl"]
    lauf.zahlen = zahlen
    if rest <= 0:
        lauf.erfolgreich, lauf.beendet_am = True, timezone.now()
        melde(request, benutzer, f"Altdaten: {zahlen['dateien']} Dokumente übernommen "
                                 f"({zahlen['nicht_uebernommen']} Dateien nicht übernommen)", dateien=zahlen["dateien"])
    lauf.save()
    return ergebnis
