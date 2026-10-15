"""Übernahme geprüfter KI-Vorschläge in die Patientenakte – nur durch einen Mitarbeiter (Auftrag 5).

Sicherheitsprinzip:
- Nur Felder im Status „freigegeben“ werden übernommen; der Mitarbeiter bestätigt die Übernahme aktiv.
- ``vorschau()`` zeigt je Feld, was passieren würde: **neu**, **ergänzt** (z. B. Wert in einen vorhandenen Befund),
  **ändert/überschreibt** einen vorhandenen Eintrag oder ist **identisch** vorhanden – dazu unsicher erkannte Felder.
- Bei Konflikten mit vorhandenen Akteninhalten wird nichts automatisch überschrieben: ohne ausdrückliche
  Entscheidung (neu anlegen / ergänzen / ersetzen / verwerfen) bricht die Übernahme mit der Liste der Konflikte ab.
- Geschrieben wird über dieselben Wege wie in der Oberfläche (Serializer bzw. Modelle mit Verlauf), mit den Rechten
  der Akte; alles in einer Transaktion. Ersetzen behält den alten Stand im Verlauf (simple-history).

Ziele: Laborwerte → ``Laborbefund``/``Laborwert``; Infusionen → ``Infusionsplan`` (Altsystem, abgelöst);
Medikamente → ``Medikament``; Diagnosen → ``Diagnose``; Texte → Abschnitt der Akte (angehängt); Dokumentdatum und
-typ → ``Dokument``.
"""
import datetime as dt
import html
from collections import defaultdict

from django.db import transaction

from audit.models import SystemEreignis, protokolliere
from epm.api_basis import pruefe_schreibbereich
from epm.sanitize import bereinige_html
from scans.ocr import auswertung

from .models import KiFeld, KiUebernahme, KiVorgang
from .pruefung import dezimal

E = KiFeld.Entscheidung
UEBERNEHMBAR_META = {"dokumentdatum", "dokumenttyp"}
RECHT = {"labor": "eintraege_erfassen", "infusion": "plaene_anlegen", "medikation": "akten_bearbeiten",
         "diagnose": "akten_bearbeiten", "text": "akten_bearbeiten", "meta": "eintraege_erfassen"}
TYP_KANDIDATEN = {
    "labor": ["Labor", "Laborbefund"], "arztbericht": ["Arztbrief", "Arztbericht", "Bericht"],
    "entlassbericht": ["Entlassbrief", "Entlassbericht", "Arztbrief"], "verlauf": ["Verlauf", "Verlaufsdokumentation"],
    "infusionsplan": ["Infusionsplan"], "medikationsplan": ["Medikationsplan", "Medikamentenplan"],
    "pflegebericht": ["Pflegebericht", "Pflege"], "sonstiges": ["Sonstiges"],
}
ABSCHNITTE = {"diagnose": "Diagnose", "therapie": "Therapie", "empfehlung": "Empfehlung"}


class Konflikt(Exception):
    def __init__(self, konflikte: list[dict]):
        super().__init__("Konflikte mit vorhandenen Einträgen der Akte – bitte je Feld entscheiden.")
        self.konflikte = konflikte


class Ungueltig(Exception):
    def __init__(self, fehler: dict):
        super().__init__("Übernahme nicht möglich.")
        self.fehler = fehler


def uebernehmbar(f: KiFeld) -> bool:
    return f.gruppe != KiFeld.Gruppe.META or f.schluessel in UEBERNEHMBAR_META


def _datum(text) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(text)[:10]) if text else None
    except ValueError:
        return None


def _uhr(text) -> dt.time | None:
    try:
        return dt.time.fromisoformat(text) if text else None
    except ValueError:
        return None


def _labordatum(f: KiFeld) -> dt.date | None:
    return _datum(f.endwert.get("datum")) or _datum((f.vorgang.metadaten or {}).get("dokumentdatum"))


def _name(w: dict) -> str:
    return auswertung.norm(w.get("freitext_name") or w.get("erkannt_als") or "")


# --------------------------------------------------------------------------------------------- Vorschau
def vorschau_feld(f: KiFeld, unsicher_unter: float) -> dict:
    """Was die Übernahme dieses Felds bewirken würde (ohne etwas zu schreiben)."""
    from befunde.models import Laborbefund, Laborwert
    from infusionen.models import Infusionsplan
    from patienten.models import Diagnose, Medikament

    w = f.endwert
    p = f.vorgang.patient
    erg = {"feld": f.pk, "gruppe": f.gruppe, "schluessel": f.schluessel, "aktion": "neu", "bestehend": None,
           "optionen": [], "fehler": "", "unsicher": f.konfidenz is not None and f.konfidenz < unsicher_unter,
           "konfidenz": f.konfidenz, "entscheidung": f.entscheidung}
    if not uebernehmbar(f):
        erg["aktion"] = "nur_info"
        return erg
    if f.gruppe == KiFeld.Gruppe.LABOR:
        d = _labordatum(f)
        if d is None:
            erg["fehler"] = "Datum der Entnahme fehlt – bitte im Feld ergänzen."
            return erg
        if w.get("wert") is None and not w.get("wert_text"):
            erg["fehler"] = "Kein Wert – bitte korrigieren oder verwerfen."
            return erg
        befunde = Laborbefund.objects.filter(patient=p, abgenommen_am=d)
        if w.get("parameter"):
            alt = Laborwert.objects.filter(befund__in=befunde, parameter_id=w["parameter"]).first()
        else:
            alt = next((x for x in Laborwert.objects.filter(befund__in=befunde, parameter__isnull=True)
                        if auswertung.norm(x.freitext_name) == _name(w)), None)
        if alt is not None:
            gleich = (alt.wert is not None and dezimal(w.get("wert")) == alt.wert) or \
                     (alt.wert is None and (alt.wert_text or "") == (w.get("wert_text") or ""))
            erg["bestehend"] = {"modell": "laborwert", "id": alt.pk, "befund": alt.befund_id,
                                "wert": str(alt.wert) if alt.wert is not None else alt.wert_text,
                                "einheit": alt.einheit, "datum": d.isoformat()}
            erg["aktion"] = "identisch" if gleich else "ueberschreiben"
            erg["optionen"] = [E.VERWERFEN, E.NEU] if gleich else [E.ERSETZEN, E.NEU, E.VERWERFEN]
        elif befunde.exists():
            b = befunde.order_by("id").first()
            erg["bestehend"] = {"modell": "laborbefund", "id": b.pk, "datum": d.isoformat(), "labor": b.labor}
            erg["aktion"] = "ergaenzen"
            erg["optionen"] = [E.ERGAENZEN, E.NEU, E.VERWERFEN]
        return erg
    if f.gruppe == KiFeld.Gruppe.INFUSION:
        d = _datum(w.get("von"))
        if d is None:
            erg["fehler"] = "Beginn (gültig ab) fehlt – bitte im Feld ergänzen."
            return erg
        alt = Infusionsplan.objects.filter(patient=p, gueltig_ab=d).exclude(status=Infusionsplan.Status.ENTWURF).first()
        if alt is not None:
            erg["bestehend"] = {"modell": "infusionsplan", "id": alt.pk, "gueltig_ab": d.isoformat(),
                                "status": alt.get_status_display(),
                                "wert": str(getattr(alt, w["planfeld"])) if w.get("planfeld") else None}
            # Freigegebene Pläne sind unveränderlich: ersetzen/ergänzen geht nicht, nur zusätzlich anlegen
            erg["aktion"] = "konflikt"
            erg["optionen"] = [E.NEU, E.VERWERFEN]
        return erg
    if f.gruppe == KiFeld.Gruppe.MEDIKATION:
        if not (w.get("wirkstoff") or "").strip():
            erg["fehler"] = "Wirkstoff fehlt."
            return erg
        if not (w.get("dosierung") or "").strip():
            erg["fehler"] = "Dosierung fehlt – bitte ergänzen (z. B. „1-0-1“ oder „bei Bedarf“)."
            return erg
        n = auswertung.norm(w["wirkstoff"])
        alt = next((m for m in Medikament.objects.filter(patient=p, aktiv=True)
                    if auswertung.norm(m.wirkstoff) == n), None)
        if alt is not None:
            erg["bestehend"] = {"modell": "medikament", "id": alt.pk, "wirkstoff": alt.wirkstoff,
                                "staerke": alt.staerke, "dosierung": alt.dosierung}
            erg["aktion"] = "ueberschreiben"
            erg["optionen"] = [E.ERSETZEN, E.NEU, E.VERWERFEN]
        return erg
    if f.gruppe == KiFeld.Gruppe.DIAGNOSE:
        if not w.get("icd_code"):
            erg["fehler"] = "ICD-Code fehlt – bitte ergänzen."
            return erg
        alt = Diagnose.objects.filter(patient=p, aktiv=True, icd_code__iexact=w["icd_code"]).first()
        if alt is not None:
            erg["bestehend"] = {"modell": "diagnose", "id": alt.pk, "bezeichnung": alt.bezeichnung,
                                "icd_code": alt.icd_code}
            erg["aktion"] = "identisch"
            erg["optionen"] = [E.VERWERFEN, E.NEU]
        return erg
    if f.gruppe == KiFeld.Gruppe.TEXT:
        abschnitt = w.get("aktenabschnitt")
        if abschnitt not in ABSCHNITTE:
            erg["fehler"] = "Bitte den Abschnitt der Akte wählen (Diagnose, Therapie oder Empfehlung)."
            return erg
        # wird nur angehängt (mit Herkunft), nie überschrieben – keine Entscheidung nötig
        erg["aktion"] = "ergaenzen"
        erg["bestehend"] = {"modell": "patient", "id": p.pk, "abschnitt": ABSCHNITTE[abschnitt]}
        return erg
    # Metadaten des Dokuments
    dok = f.vorgang.dokument
    if f.schluessel == "dokumentdatum":
        d = _datum(w.get("wert"))
        if d is None:
            erg["fehler"] = "Kein gültiges Datum."
        elif dok.datum is None:
            erg["aktion"] = "neu"
        elif dok.datum == d:
            erg["aktion"], erg["optionen"] = "identisch", [E.VERWERFEN]
        else:
            erg["aktion"], erg["optionen"] = "ueberschreiben", [E.ERSETZEN, E.VERWERFEN]
        erg["bestehend"] = {"modell": "dokument", "id": dok.pk, "datum": dok.datum.isoformat() if dok.datum else None}
    elif f.schluessel == "dokumenttyp":
        typ = _dokumenttyp(w)
        if typ is None:
            erg["fehler"] = "Dieser Dokumenttyp steht nicht in der Auswahlliste – bitte einen Typ wählen."
        elif dok.typ_id is None:
            erg["aktion"] = "neu"
        elif dok.typ_id == typ.pk:
            erg["aktion"], erg["optionen"] = "identisch", [E.VERWERFEN]
        else:
            erg["aktion"], erg["optionen"] = "ueberschreiben", [E.ERSETZEN, E.VERWERFEN]
        erg["bestehend"] = {"modell": "dokument", "id": dok.pk, "typ": dok.typ.wert if dok.typ_id else None,
                            "neu": typ.wert if typ else None}
    return erg


def _dokumenttyp(w: dict):
    from stammdaten.models import Auswahlwert

    liste = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.DOKUMENTTYP, aktiv=True)
    if w.get("typ_id"):
        return liste.filter(pk=w["typ_id"]).first()
    for kandidat in TYP_KANDIDATEN.get(w.get("wert") or "", []):
        t = liste.filter(wert__iexact=kandidat).first()
        if t is not None:
            return t
    return None


def vorschau(vorgang: KiVorgang, felder: list[KiFeld] | None = None) -> list[dict]:
    from .models import KiEinstellung

    grenze = KiEinstellung.laden().feld_unsicher
    felder = felder if felder is not None else list(vorgang.felder.exclude(status__in=["verworfen", "uebernommen"]))
    return [vorschau_feld(f, grenze) for f in felder]


# --------------------------------------------------------------------------------------------- Übernahme
def uebernehmen(vorgang: KiVorgang, feld_ids: list[int], entscheidungen: dict, request) -> dict:
    """Übernimmt die gewählten (freigegebenen) Felder. Wirft ``Konflikt``/``Ungueltig``/``PermissionError``."""
    user = request.user
    patient = vorgang.patient
    pruefe_schreibbereich(user, patient)
    patient.pruefe_bearbeitbar()
    felder = list(vorgang.felder.filter(pk__in=feld_ids).select_related("vorgang__dokument"))
    if not felder or len(felder) != len(set(feld_ids)):
        raise Ungueltig({"felder": "Bitte freigegebene Felder dieses Vorgangs wählen."})
    nicht_frei = [f.pk for f in felder if f.status != KiFeld.Status.FREIGEGEBEN]
    if nicht_frei:
        raise Ungueltig({"felder": f"Nur freigegebene Felder lassen sich übernehmen (nicht freigegeben: "
                                   f"{', '.join(map(str, nicht_frei))})."})
    for f in felder:
        recht = RECHT[f.gruppe]
        if not user.hat_recht(recht):
            from accounts.rechte import NAMEN

            raise PermissionError(f"Für „{f.get_gruppe_display()}“ fehlt das Recht „{NAMEN[recht]}“.")
    vorschauen = {v["feld"]: v for v in vorschau(vorgang, felder)}
    fehler = {str(k): v["fehler"] for k, v in vorschauen.items() if v["fehler"]}
    if fehler:
        raise Ungueltig({"felder": fehler})
    wahl = {}
    konflikte = []
    for f in felder:
        v = vorschauen[f.pk]
        e = str(entscheidungen.get(str(f.pk)) or entscheidungen.get(f.pk) or "")
        if v["optionen"]:
            if e not in v["optionen"]:
                konflikte.append(v)
                continue
        elif e and e not in (E.NEU, E.VERWERFEN, E.ERGAENZEN):
            konflikte.append(v)
            continue
        wahl[f.pk] = e or (E.ERGAENZEN if v["aktion"] == "ergaenzen" else E.NEU)
    if konflikte:
        raise Konflikt(konflikte)

    ziele = []
    with transaction.atomic():
        nach_gruppe = defaultdict(list)
        for f in felder:
            if wahl[f.pk] == E.VERWERFEN:
                f.status, f.entscheidung, f.geaendert_von = KiFeld.Status.VERWORFEN, E.VERWERFEN, user
                f.save(update_fields=["status", "entscheidung", "geaendert_von", "geaendert_am"])
                continue
            nach_gruppe[f.gruppe].append(f)
        ctx = {"request": request}
        ziele += _labor(nach_gruppe["labor"], wahl, vorschauen, vorgang, user, ctx)
        ziele += _infusion(nach_gruppe["infusion"], vorgang, user)
        ziele += _medikation(nach_gruppe["medikation"], wahl, vorschauen, vorgang, user, ctx)
        ziele += _diagnose(nach_gruppe["diagnose"], vorgang, user, ctx)
        ziele += _texte(nach_gruppe["text"], vorgang, user)
        ziele += _meta(nach_gruppe["meta"], wahl, vorgang, user)
        KiUebernahme.objects.create(vorgang=vorgang, benutzer=user, felder=[f.pk for f in felder], ziele=ziele,
                                    entscheidungen={str(k): v for k, v in wahl.items()})
        offen = [f for f in vorgang.felder.all() if uebernehmbar(f)
                 and f.status in (KiFeld.Status.OFFEN, KiFeld.Status.FREIGEGEBEN)]
        vorgang.status = KiVorgang.Status.TEILWEISE if offen else KiVorgang.Status.UEBERNOMMEN
        vorgang.geprueft_von, vorgang.geprueft_am = user, dt.datetime.now(dt.UTC)
        vorgang.save(update_fields=["status", "geprueft_von", "geprueft_am"])
        protokolliere(SystemEreignis.Art.KI, request, objekt=str(vorgang), aktion="uebernommen", vorgang=vorgang.pk,
                      dokument=vorgang.dokument_id, patient_id=patient.id, felder=[f.pk for f in felder],
                      entscheidungen={str(k): v for k, v in wahl.items()}, ziele=ziele,
                      modell=vorgang.modellversion.name if vorgang.modellversion else "",
                      prompt_version=vorgang.prompt_version)
    from .verknuepfung import fuer_patient

    fuer_patient(patient)
    return {"ziele": ziele, "status": vorgang.status}


def _fertig(f: KiFeld, entscheidung: str, user, ziel: dict):
    f.status, f.entscheidung, f.ziel, f.geaendert_von = KiFeld.Status.UEBERNOMMEN, entscheidung, ziel, user
    f.save(update_fields=["status", "entscheidung", "ziel", "geaendert_von", "geaendert_am"])


def _herkunft(vorgang: KiVorgang) -> str:
    dok = vorgang.dokument
    return f"Aus „{dok.titel}“" + (f" vom {dok.datum:%d.%m.%Y}" if dok.datum else "") + " (KI, geprüft)"


def _zeile(w: dict) -> dict:
    return {"parameter": w.get("parameter"), "freitext_name": "" if w.get("parameter") else
            (w.get("freitext_name") or w.get("erkannt_als") or "")[:150],
            "wert": w.get("wert"), "wert_text": (w.get("wert_text") or "")[:50], "einheit": (w.get("einheit") or "")[:30],
            "referenz_von": w.get("referenz_von"), "referenz_bis": w.get("referenz_bis")}


def _vorhandene_zeilen(befund) -> list[dict]:
    return [{"parameter": x.parameter_id, "freitext_name": x.freitext_name,
             "wert": str(x.wert) if x.wert is not None else None, "wert_text": x.wert_text, "einheit": x.einheit,
             "referenz_von": str(x.referenz_von) if x.referenz_von is not None else None,
             "referenz_bis": str(x.referenz_bis) if x.referenz_bis is not None else None,
             "bemerkung": x.bemerkung} for x in befund.werte.all()]


def _labor(felder, wahl, vorschauen, vorgang, user, ctx) -> list[dict]:
    from befunde.api import LaborbefundSerializer
    from befunde.models import Laborbefund

    if not felder:
        return []
    ziele = []
    neu_je_datum: dict[tuple, list[KiFeld]] = defaultdict(list)
    in_bestehende: dict[int, list[tuple[KiFeld, str]]] = defaultdict(list)
    for f in felder:
        e = wahl[f.pk]
        v = vorschauen[f.pk]
        if e in (E.ERGAENZEN, E.ERSETZEN) and v["bestehend"]:
            bid = v["bestehend"].get("befund") or v["bestehend"]["id"]
            in_bestehende[bid].append((f, e))
        else:
            neu_je_datum[(_labordatum(f), f.endwert.get("uhrzeit"))].append(f)
    for (d, uhr), gruppe in neu_je_datum.items():
        daten = {"patient": vorgang.patient_id, "dokument": vorgang.dokument_id, "abgenommen_am": d.isoformat(),
                 "abgenommen_um": uhr, "labor": str((vorgang.metadaten or {}).get("absender") or "")[:150],
                 "beurteilung": "", "werte": [_zeile(f.endwert) for f in gruppe]}
        s = LaborbefundSerializer(data=daten, context=ctx)
        if not s.is_valid():
            raise Ungueltig({"labor": s.errors})
        befund = s.save(erfasst_von=user)
        ziele.append({"modell": "laborbefund", "id": befund.pk, "aktion": "neu", "werte": len(gruppe)})
        for f in gruppe:
            _fertig(f, wahl[f.pk] or E.NEU, user, {"modell": "laborbefund", "id": befund.pk})
    for bid, eintraege in in_bestehende.items():
        befund = Laborbefund.objects.select_for_update().get(pk=bid, patient=vorgang.patient)
        zeilen = _vorhandene_zeilen(befund)
        for f, e in eintraege:
            w = f.endwert
            neu = _zeile(w)
            if e == E.ERSETZEN:
                for z in zeilen:
                    passt = (w.get("parameter") and z["parameter"] == w["parameter"]) or \
                            (not w.get("parameter") and auswertung.norm(z["freitext_name"]) == _name(w))
                    if passt:
                        z.update(neu)
                        break
            else:
                zeilen.append(neu)
        s = LaborbefundSerializer(befund, data={"werte": zeilen}, partial=True, context=ctx)
        if not s.is_valid():
            raise Ungueltig({"labor": s.errors})
        befund._history_user = user
        s.save()
        aktionen = sorted({e for _f, e in eintraege})
        ziele.append({"modell": "laborbefund", "id": befund.pk, "aktion": "+".join(aktionen),
                      "werte": len(eintraege)})
        for f, e in eintraege:
            _fertig(f, e, user, {"modell": "laborbefund", "id": befund.pk})
    return ziele


def _infusion(felder, vorgang, user) -> list[dict]:
    """Historischer Plan (Entscheidung 14.10.2026): je Beginn ein abgeschlossener Plan „aus dem Altsystem“."""
    from infusionen.models import Infusionsplan
    from stammdaten.models import Einstellungen

    if not felder:
        return []
    e = Einstellungen.aktuell()
    grenzen = {"kalium_mmol": (e.kalium_min_mmol, e.kalium_max_mmol),
               "natrium_mmol": (e.natrium_min_mmol, e.natrium_max_mmol),
               "glucose_g": (e.glucose_min_g, e.glucose_max_g),
               "aminosaeuren_g": (e.aminosaeuren_min_g, e.aminosaeuren_max_g),
               "lipide_g": (e.lipide_min_g, e.lipide_max_g)}
    ziele = []
    je_beginn: dict[dt.date, list[KiFeld]] = defaultdict(list)
    for f in felder:
        je_beginn[_datum(f.endwert.get("von"))].append(f)
    for beginn, gruppe in sorted(je_beginn.items()):
        plan = Infusionsplan(patient=vorgang.patient, status=Infusionsplan.Status.ABGELOEST, gueltig_ab=beginn,
                             herkunft=Infusionsplan.Herkunft.ALTSYSTEM, erstellt_von=user)
        weitere = []
        for f in gruppe:
            w = f.endwert
            menge = dezimal(w.get("menge"))
            feld = w.get("planfeld")
            if feld and menge is not None and hasattr(plan, feld):
                if feld in grenzen and not (grenzen[feld][0] <= menge <= grenzen[feld][1]):
                    raise Ungueltig({str(f.pk): f"{w.get('substanz')}: {menge} liegt außerhalb der "
                                                f"Plausibilitätsgrenzen ({grenzen[feld][0]}–{grenzen[feld][1]})."})
                if feld == "basis_ml":
                    menge = int(menge)
                setattr(plan, feld, menge)
            else:
                teile = [w.get("substanz"), f"{w.get('menge') or ''} {w.get('einheit') or ''}".strip(),
                         w.get("applikation"), w.get("haeufigkeit")]
                weitere.append(" ".join(t for t in teile if t))
        bemerkung = f"<p><em>{html.escape(_herkunft(vorgang))}</em></p>"
        if weitere:
            bemerkung += "<p>Weitere Angaben: " + html.escape("; ".join(weitere)) + "</p>"
        plan.bemerkung = bereinige_html(bemerkung)
        plan._history_user = user
        plan.save()
        ziele.append({"modell": "infusionsplan", "id": plan.pk, "aktion": "neu", "gueltig_ab": beginn.isoformat()})
        for f in gruppe:
            _fertig(f, E.NEU, user, {"modell": "infusionsplan", "id": plan.pk})
    return ziele


def _medikation(felder, wahl, vorschauen, vorgang, user, ctx) -> list[dict]:
    from patienten.api import MedikamentSerializer
    from patienten.models import Medikament

    ziele = []
    for f in felder:
        w = f.endwert
        daten = {"wirkstoff": w.get("wirkstoff", "")[:200], "handelsname": (w.get("handelsname") or "")[:200],
                 "staerke": (w.get("staerke") or "")[:60], "dosierung_frei": (w.get("dosierung") or "")[:120],
                 "grund": (w.get("grund") or "")[:200], "seit": w.get("seit"),
                 "hinweise": _herkunft(vorgang)[:300]}
        if wahl[f.pk] == E.ERSETZEN:
            alt = Medikament.objects.get(pk=vorschauen[f.pk]["bestehend"]["id"], patient=vorgang.patient)
            daten.pop("wirkstoff")
            s = MedikamentSerializer(alt, data={k: v for k, v in daten.items() if v not in (None, "")}, partial=True,
                                     context=ctx)
            aktion = "ersetzt"
        else:
            # aus einem alten Dokument: aktiv nur, wenn der Mitarbeiter es so korrigiert hat; sonst als „nicht aktiv“
            # mit dem Stand des Dokuments – das tatsächliche Absetzdatum ist nicht bekannt
            aktiv = bool(w.get("aktiv", False))
            stand = _datum((vorgang.metadaten or {}).get("dokumentdatum")) or vorgang.dokument.datum
            if stand and daten.get("seit") and stand < _datum(daten["seit"]):
                stand = None
            zusatz = {} if aktiv else {"abgesetzt_am": (stand.isoformat() if stand else None),
                                       "absetzgrund": "nur aus historischem Dokument bekannt (KI-Übernahme) – "
                                                      "Absetzdatum unbekannt, eingetragen ist der Stand des Dokuments"}
            s = MedikamentSerializer(data={**daten, "patient": vorgang.patient_id, "aktiv": aktiv, **zusatz},
                                     context=ctx)
            aktion = "neu"
        if not s.is_valid():
            raise Ungueltig({str(f.pk): s.errors})
        if s.instance is not None:
            s.instance._history_user = user
            m = s.save()
        else:
            m = s.save(angelegt_von=user)
        ziele.append({"modell": "medikament", "id": m.pk, "aktion": aktion})
        _fertig(f, wahl[f.pk] or E.NEU, user, {"modell": "medikament", "id": m.pk})
    return ziele


def _diagnose(felder, vorgang, user, ctx) -> list[dict]:
    from patienten.api import DiagnoseSerializer
    from stammdaten.models import Diagnosevorlage

    ziele = []
    for f in felder:
        w = f.endwert
        s = DiagnoseSerializer(data={"patient": vorgang.patient_id, "bezeichnung": w.get("bezeichnung", "")[:200],
                                     "icd_code": w.get("icd_code", ""), "notiz": _herkunft(vorgang)[:300]},
                               context=ctx)
        if not s.is_valid():
            raise Ungueltig({str(f.pk): s.errors})
        d = s.save(angelegt_von=user)
        Diagnosevorlage.objects.get_or_create(icd_code=d.icd_code, bezeichnung=d.bezeichnung)
        ziele.append({"modell": "diagnose", "id": d.pk, "aktion": "neu"})
        _fertig(f, E.NEU, user, {"modell": "diagnose", "id": d.pk})
    return ziele


def _texte(felder, vorgang, user) -> list[dict]:
    if not felder:
        return []
    patient = vorgang.patient
    for f in felder:
        w = f.endwert
        abschnitt = w["aktenabschnitt"]
        absaetze = "".join(f"<p>{html.escape(z)}</p>" for z in str(w.get("text") or "").splitlines() if z.strip())
        alt = getattr(patient, abschnitt) or ""
        setattr(patient, abschnitt, bereinige_html(f"{alt}<p><em>{html.escape(_herkunft(vorgang))}:</em></p>{absaetze}"))
    patient._history_user = user
    patient.save()
    for f in felder:
        _fertig(f, E.ERGAENZEN, user, {"modell": "patient", "id": patient.pk, "abschnitt": f.endwert["aktenabschnitt"]})
    return [{"modell": "patient", "id": patient.pk, "aktion": "ergaenzt", "abschnitte":
             sorted({f.endwert["aktenabschnitt"] for f in felder})}]


def _meta(felder, wahl, vorgang, user) -> list[dict]:
    if not felder:
        return []
    dok = vorgang.dokument
    for f in felder:
        if f.schluessel == "dokumentdatum":
            dok.datum = _datum(f.endwert.get("wert"))
        elif f.schluessel == "dokumenttyp":
            dok.typ = _dokumenttyp(f.endwert)
            dok.typ_geprueft = True
    dok._history_user = user
    dok.save()
    for f in felder:
        _fertig(f, wahl[f.pk] or E.NEU, user, {"modell": "dokument", "id": dok.pk})
    return [{"modell": "dokument", "id": dok.pk, "aktion": "ergaenzt", "felder": [f.schluessel for f in felder]}]

