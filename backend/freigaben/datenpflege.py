"""Datenpflege nach der Altdaten-Übernahme (Menü „Freigaben“, 16.11.2026).

Liest die Freitexte einer Akte und schlägt Schritte vor – umgesetzt wird erst nach der Freigabe durch einen Mitarbeiter:

- **Telefon** „015788255675 (Hr. Pohlmann) 0157 8902 6736 (Fr. Pohlmann) 0524242667“: die eigenen Nummern bleiben in
  Telefon/Telefon 2, die Nummer der Frau wird zur Bezugsperson „Ehefrau“ mit ihrer Nummer.
- **Hausarzt** „Dr. Klaus Heuwing, Alleestr. 10, 46282 Dorsten / T. 02362-26960 / dorsten@praxis-heuwing.de“: Arzt
  der Ärzteliste (vorhandener Treffer oder neu angelegt) mit Rolle Hausarzt zuordnen; danach verweist die Übersicht auf
  den Reiter „Ärzte“ und der Freitext entfällt. Ebenso „Überweisung durch“, wenn dort ein Arzt mit Adresse steht.
- **Hinweise aus der Altdaten-Übernahme** (früheres Feld „Bemerkung“): Absätze wie „Telefon (vollständig, laut
  Altsystem): …“ werden mit dem Inhalt verarbeitet und danach entfernt.

Ein Schritt ist ein Wörterbuch mit ``id``, ``art`` (arzt | bezugsperson | feld | hinweis), ``an`` (ausgewählt),
``quelle`` (Feld der Akte), ``auszug`` (Textstelle), ``sicher`` und ``hinweis`` (Begründung) sowie je Art:
``arzt``: ``rolle``, ``werte`` {name, praxis, fachrichtung, strasse, plz, ort, telefon, fax, email}, ``arzt_wahl``
(„auto“ = vorhandenen Treffer nehmen, sonst neu | „neu“ | ID); ``bezugsperson``: ``werte`` {beziehung, name, telefon,
mobil, email}; ``feld``: ``feld``, ``label``, ``alt``, ``neu``; ``hinweis``: ``titel``, ``alt`` (Absatz als HTML),
``text``. ``abhaengig_von``: Schritte, ohne die dieser nicht umgesetzt wird (z. B. die Nummer der Frau verschwindet
aus dem Telefonfeld nur, wenn sie als Bezugsperson angelegt wird).
"""
from __future__ import annotations

import html as htmlmod
import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from .models import Datenpflegevorschlag

FELDER = {"telefon": "Telefon", "telefon2": "Telefon 2", "email": "E-Mail", "hausarzt": "Hausarzt",
          "ueberweisung_durch": "Überweisung / Kontaktaufnahme durch"}
QUELLFELDER = [*FELDER, "bemerkung"]
LAENGE = {"telefon": 50, "telefon2": 50, "hausarzt": 150, "ueberweisung_durch": 200, "email": 254}
ARZT_LAENGE = {"name": 150, "praxis": 150, "fachrichtung": 100, "strasse": 150, "plz": 10, "ort": 100, "telefon": 50,
               "fax": 50, "email": 254}
PERSON_LAENGE = {"beziehung": 100, "name": 150, "telefon": 50, "mobil": 50, "email": 254}
ROLLEN = {"hausarzt", "facharzt", "ueberweisend", "klinik", "sonstige"}

# ------------------------------------------------------------------------------------------- Hinweise (Bemerkung)
ABSATZ = re.compile(r"<p>\s*<strong>(?P<titel>[^<]*?):\s*</strong>\s*(?P<inhalt>.*?)</p>", re.S)
HINWEIS_FELD = {"telefon": "telefon", "telefon 2": "telefon2", "hausarzt": "hausarzt", "e-mail": "email",
                "überweisung / kontaktaufnahme durch": "ueberweisung_durch", "überweisung": "ueberweisung_durch"}


def _text(html_text: str) -> str:
    return htmlmod.unescape(re.sub(r"<[^>]+>", " ", html_text or "")).strip()


def hinweise(bemerkung: str) -> list[dict]:
    """Absätze „<strong>Titel:</strong> Inhalt“ der Hinweise aus der Übernahme → [{titel, feld, inhalt, html}]."""
    aus = []
    for m in ABSATZ.finditer(bemerkung or ""):
        titel = _text(m["titel"])
        grund = re.sub(r"\s*\(.*\)\s*$", "", titel).strip().lower()
        aus.append({"titel": titel, "feld": HINWEIS_FELD.get(grund), "inhalt": re.sub(r"\s+", " ", _text(m["inhalt"])),
                    "html": m.group(0)})
    return aus


# ------------------------------------------------------------------------------------------------------ Telefon
_NUMMER = re.compile(r"(?<![\d+])(?:(?:\+|00)\d{2}\s?(?:\(0\)\s?)?|0)\d{2,5}(?:[ \-/]?\d{2,}){0,6}(?!\d)")
_TITEL = re.compile(r"^\s*(hr\.?|herrn?|fr\.?|frau)\s+", re.I)
BEZIEHUNGEN = [  # längere zuerst (Schwiegertochter vor Tochter, Ehefrau vor Frau)
    ("schwiegertochter", "Schwiegertochter"), ("schwiegersohn", "Schwiegersohn"), ("schwiegermutter", "Schwiegermutter"),
    ("ehefrau", "Ehefrau"), ("ehemann", "Ehemann"), ("ehepartner", "Ehepartner/in"),
    ("lebensgefährtin", "Lebensgefährte/in"), ("lebensgefährte", "Lebensgefährte/in"),
    ("lebenspartner", "Lebensgefährte/in"), ("partnerin", "Partner/in"), ("partner", "Partner/in"),
    ("betreuerin", "Betreuer/in"), ("betreuer", "Betreuer/in"), ("betreuung", "Betreuer/in"),
    ("mutter", "Mutter"), ("mama", "Mutter"), ("vater", "Vater"), ("papa", "Vater"),
    ("tochter", "Tochter"), ("sohn", "Sohn"), ("schwester", "Schwester"), ("bruder", "Bruder"),
    ("enkelin", "Enkel/in"), ("enkel", "Enkel/in"), ("oma", "Großmutter"), ("großmutter", "Großmutter"),
    ("opa", "Großvater"), ("großvater", "Großvater"), ("nichte", "Nichte"), ("neffe", "Neffe"),
    ("nachbarin", "Nachbar/in"), ("nachbar", "Nachbar/in"), ("freundin", "Freund/in"), ("freund", "Freund/in"),
    ("pflegedienst", "Pflegedienst"), ("tante", "Tante"), ("onkel", "Onkel"),
]
KEINE_PERSON = {"mobil", "handy", "privat", "dienstlich", "arbeit", "büro", "geschäftlich", "festnetz", "ab",
                "abends", "tagsüber", "morgens", "mittags", "nachmittags", "home", "fax", "tel", "telefon", "neu", "alt",
                "zuhause", "zu hause", "whatsapp", "notfall", "nur", "sms", "mailbox", "selbst", "patient", "patientin",
                "pat", "pat.", "eigene", "eigen"}


def _ziffern(nummer: str) -> str:
    return re.sub(r"\D", "", nummer or "")


def ist_mobil(nummer: str) -> bool:
    z = _ziffern(nummer)
    return bool(re.match(r"^(?:0|49|0049)1[5-7]", z))


def _nummern(text: str) -> list[re.Match | tuple]:
    """Nummern im Text; zwei durch Leerzeichen getrennte Nummern („0524 242667 0171 1234567“) werden getrennt, sobald
    ein neuer Block mit 0 beginnt und die bisherige Nummer schon 6 Ziffern hat."""
    aus = []
    for m in _NUMMER.finditer(text):
        start, teile, pos = m.start(), [], m.start()
        for t in re.finditer(r"\S+", m.group(0)):
            if teile and t.group(0).startswith(("0", "+")) and len(_ziffern("".join(teile))) >= 6 \
                    and not teile[-1].endswith(("-", "/")):
                aus.append((start, pos))
                start, teile = m.start() + t.start(), []
            teile.append(t.group(0))
            pos = m.start() + t.end()
        aus.append((start, pos))
    return [(s, e) for s, e in aus if len(_ziffern(text[s:e])) >= 6]


def telefon_zerlegen(text: str) -> tuple[list[dict], str]:
    """„0157… (Hr. X) 0157… (Fr. X) 05242…“ → [{nummer, label}], Rest (Text, der keiner Nummer zuzuordnen war)."""
    text = re.sub(r"\s+", " ", (text or "").replace("…", "")).strip()
    eintraege, rest, ende = [], [], 0
    for start, stop in _nummern(text):
        davor = text[ende:start].strip(" ,;/:-–|")
        danach = re.match(r"\s*\(([^)]*)\)?", text[stop:])
        nummer = text[start:stop].strip(" -/")
        label = (danach.group(1).strip() if danach else "")
        von = start
        if davor:
            # Text vor der Nummer: Name davor („Frau Pohlmann: 0157…“), sonst ein Rest der vorigen Nummer
            if not label and not re.search(r"\)\s*$", text[:start]):
                label = davor
                von = text.index(davor, ende)
            else:
                rest.append(davor)
        bis = stop + (danach.end() if danach else 0)
        eintraege.append({"nummer": nummer, "label": label.strip(" :,-"), "stelle": text[von:bis].strip()})
        ende = stop + (danach.end() if danach else 0)
    schluss = text[ende:].strip(" ,;/:-–|")
    if schluss:
        if eintraege and not eintraege[-1]["label"]:
            eintraege[-1]["label"] = schluss
        else:
            rest.append(schluss)
    return eintraege, " ".join(rest)


def _ist_person(label: str) -> bool:
    l = label.lower().strip(" .:")
    if not l or l in KEINE_PERSON or all(w.strip(".,") in KEINE_PERSON for w in l.split()):
        return False
    if _TITEL.match(label + " ") or any(k in l for k, _ in BEZIEHUNGEN):
        return True
    return bool(re.match(r"^[A-ZÄÖÜ][a-zäöüß]+(?:[ -][A-ZÄÖÜ][a-zäöüß]+)*$", label.strip()))


def person_einordnen(label: str, patient) -> dict:
    """Label einer Nummer → {eigen: bool, beziehung, name, sicher, hinweis}."""
    l = label.lower()
    nachname, vorname = (patient.nachname or "").lower(), (patient.vorname or "").lower()
    titel = _TITEL.match(label + " ")
    rest = _TITEL.sub("", label + " ").strip(" .")
    weiblich = bool(titel) and titel.group(1).lower().startswith("f")
    beziehung = next((b for k, b in BEZIEHUNGEN if re.search(rf"\b{k}", l)), "")
    if not beziehung:
        if vorname and re.search(rf"\b{re.escape(vorname)}\b", l):
            return {"eigen": True}
        if titel and (not rest or rest.lower() == nachname):
            pat_weiblich = patient.geschlecht == "w"
            if patient.geschlecht in ("w", "m") and weiblich == pat_weiblich:
                return {"eigen": True}
            if patient.geschlecht in ("w", "m") and rest.lower() == nachname:
                return {"eigen": False, "beziehung": "Ehefrau" if weiblich else "Ehemann", "sicher": False,
                        "name": f"{'Frau' if weiblich else 'Herr'} {rest}",
                        "hinweis": f"Beziehung vermutet: {'Frau' if weiblich else 'Herr'} mit dem Nachnamen des "
                                   f"Patienten – bitte prüfen (z. B. Tochter statt Ehefrau)."}
    name = rest
    for k, _ in BEZIEHUNGEN:
        name = re.sub(rf"\b{k}\w*\b", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip(" ,:-/()")
    if titel and name:
        name = f"{'Frau' if weiblich else 'Herr'} {name}"
    hinweis = "" if beziehung else "Beziehung bitte ergänzen."
    if not name:
        name = (f"{'Frau' if weiblich else 'Herr'} (Name unvollständig)" if titel
                else f"{beziehung or 'Person'} von {patient.vorname} {patient.nachname}".strip())
        hinweis = (hinweis + " Name stand nicht im Text.").strip()
    return {"eigen": False, "beziehung": beziehung, "name": name[:150], "sicher": bool(beziehung) and bool(rest),
            "hinweis": hinweis}


# ------------------------------------------------------------------------------------------------------- Ärzte
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PLZ_ORT = re.compile(r"^(?:D-?\s?)?(\d{5})\s+(\D.*)$")
_STRASSE_PLZ = re.compile(r"^(?P<strasse>.*?\d+\s?[a-zA-Z]?(?:\s?[-/]\s?\d+[a-zA-Z]?)?)\s+(?:D-?\s?)?"
                          r"(?P<plz>\d{5})\s+(?P<ort>\D.*)$")
_STRASSE = re.compile(r"^[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß.\- ]*\s\d+\s?[a-zA-Z]?(?:\s?[-/]\s?\d+[a-zA-Z]?)?$")
_FAX = re.compile(r"^(?:fax|f)\.?\s*:?\s*(?P<n>[+\d][\d \-/()]+)$", re.I)
_TEL = re.compile(r"^(?:tel(?:efon)?|fon|t|ph)\.?\s*:?\s*(?P<n>[+\d][\d \-/()]+)$", re.I)
_PRAXIS = re.compile(r"\b(praxis|gemeinschaftspraxis|mvz|klinik|klinikum|zentrum|krankenhaus|hospital|ambulanz)\b",
                     re.I)
FACHRICHTUNGEN = [("allgemeinmedizin", "Allgemeinmedizin"), ("hausarzt", "Allgemeinmedizin"),
                  ("innere", "Innere Medizin"), ("internist", "Innere Medizin"),
                  ("gastroenterolog", "Gastroenterologie"), ("onkolog", "Onkologie"), ("chirurg", "Chirurgie"),
                  ("kinderarzt", "Kinder- und Jugendmedizin"), ("pädiat", "Kinder- und Jugendmedizin"),
                  ("neurolog", "Neurologie"), ("kardiolog", "Kardiologie"), ("nephrolog", "Nephrologie"),
                  ("ernährung", "Ernährungsmedizin"), ("gynäkolog", "Gynäkologie"), ("urolog", "Urologie")]


KEIN_ARZT = {"unbekannt", "keiner", "kein", "keine", "nicht bekannt", "eigeninitiative", "selbst", "n.b", "nb", "k.a",
             "ka", "fehlt", "offen", "?"}


def arzt_zerlegen(text: str) -> dict | None:
    """Freitext eines Arztes → Werte für die Ärzteliste (nur, was sicher erkennbar ist) oder ``None``."""
    text = re.sub(r"\s+", " ", (text or "").replace("…", "")).strip()
    if not text or not re.search(r"[A-Za-zÄÖÜäöü]{3}", text):
        return None
    werte = dict.fromkeys(ARZT_LAENGE, "")
    m = _EMAIL.search(text)
    if m:
        werte["email"] = m.group(0).rstrip(".")
        text = re.sub(r"(?:\s*[/,;|])+\s*$", "", (text[:m.start()] + text[m.end():]).strip())
    teile = [t.strip(" ./") if not re.search(r"\b(str|dr|med|prof)\.$", t.strip(), re.I) else t.strip()
             for t in re.split(r"\s+/\s+|\s*[,;|\n]\s*|\s+-\s+(?=\D)", text) if t.strip(" .")]
    notiz = []
    for t in teile:
        f, tel = _FAX.match(t), _TEL.match(t)
        if f and not werte["fax"]:
            werte["fax"] = f["n"].strip()
        elif tel and not werte["telefon"]:
            werte["telefon"] = tel["n"].strip()
        elif re.fullmatch(r"[+\d][\d \-/()]{5,}", t) and not werte["telefon"]:
            werte["telefon"] = t
        elif (m := _STRASSE_PLZ.match(t)) and not werte["plz"]:
            werte.update(strasse=m["strasse"].strip(), plz=m["plz"], ort=m["ort"].strip())
        elif (m := _PLZ_ORT.match(t)) and not werte["plz"]:
            werte.update(plz=m[1], ort=m[2].strip())
        elif _STRASSE.match(t) and not werte["strasse"] and werte["name"]:
            werte["strasse"] = t
        elif not werte["name"]:
            werte["name"] = t
        elif not werte["ort"] and re.fullmatch(r"[A-ZÄÖÜ][a-zäöüß]+(?:[- ][A-ZÄÖÜ][a-zäöüß]+)*", t) \
                and not _PRAXIS.search(t) and t.lower() not in ("herr", "frau"):
            werte["ort"] = t
        elif _PRAXIS.search(t) and not werte["praxis"]:
            werte["praxis"] = t
        else:
            notiz.append(t)
    if not werte["name"]:
        return None
    if _PRAXIS.search(werte["name"]) and not werte["praxis"] and not re.search(r"\bdr\b|\bdipl", werte["name"], re.I):
        werte["praxis"] = werte["name"]
    gesamt = text.lower()
    werte["fachrichtung"] = next((f for k, f in FACHRICHTUNGEN if k in gesamt), "")
    werte = {k: v[:ARZT_LAENGE[k]] for k, v in werte.items()}
    werte["notiz"] = ", ".join(notiz)
    return werte


def _name_schluessel(name: str) -> str:
    n = re.sub(r"\b(dr|med|prof|dipl|univ|priv|doz|pd|herr|frau|hr|fr|praxis)\b\.?", " ", (name or "").lower())
    return " ".join(sorted(re.sub(r"[^a-zäöüß ]", " ", n).split()))


def aerzte_treffer(werte: dict, limit: int = 5) -> list:
    """Vorhandene Ärzte, die zu den Werten passen: gleicher Name (ohne Titel) oder gleiche Telefonnummer/E-Mail."""
    from stammdaten.models import Arzt

    schluessel, tel, mail = _name_schluessel(werte.get("name", "")), _ziffern(werte.get("telefon", "")), \
        (werte.get("email") or "").lower()
    if not schluessel and len(tel) < 6 and not mail:
        return []
    treffer = []
    for a in Arzt.objects.filter(aktiv=True).order_by("name", "id"):
        gleich_name = schluessel and _name_schluessel(a.name) == schluessel
        gleich_tel = len(tel) >= 6 and _ziffern(a.telefon).lstrip("0").endswith(tel.lstrip("0")[-8:])
        gleich_mail = mail and (a.email or "").lower() == mail
        if gleich_name or gleich_tel or gleich_mail:
            treffer.append(a)
        if len(treffer) >= limit:
            break
    return treffer


# --------------------------------------------------------------------------------------------- Vorschlag bauen
def _quelle(patient) -> dict:
    return {f: getattr(patient, f) or "" for f in QUELLFELDER}


def schritte_bauen(patient) -> list[dict]:
    """Alle Schritte für eine Akte (leer, wenn nichts zu tun ist)."""
    q = _quelle(patient)
    hw = hinweise(q["bemerkung"])
    schritte: list[dict] = []

    def neu(**s):
        s.setdefault("an", True)
        s.setdefault("sicher", True)
        s.setdefault("hinweis", "")
        s.setdefault("abhaengig_von", [])
        s["id"] = f"s{len(schritte) + 1}"
        schritte.append(s)
        return s

    # Telefon: Feld und vollständiger Wortlaut aus den Hinweisen (das Feld ist dann gekürzt)
    tel_hinweise = [h for h in hw if h["feld"] in ("telefon", "telefon2")]
    quelltexte = {"telefon": q["telefon"], "telefon2": q["telefon2"]}
    for h in tel_hinweise:
        quelltexte[h["feld"]] = h["inhalt"]
    eigene, personen, unklar = [], [], []
    vorhandene = {_ziffern(n) for b in patient.bezugspersonen.filter(aktiv=True) for n in (b.telefon, b.mobil) if n}
    mehrfach = False
    for feld in ("telefon", "telefon2"):
        eintraege, rest = telefon_zerlegen(quelltexte[feld])
        if rest:
            unklar.append(rest)
        mehrfach = mehrfach or len(eintraege) > 1
        for e in eintraege:
            label = e["label"]
            if label and _ist_person(label):
                p = person_einordnen(label, patient)
                if not p["eigen"]:
                    personen.append({**p, "nummer": e["nummer"], "feld": feld,
                                     "auszug": e["stelle"]})
                    continue
                label = ""  # „Hr. Pohlmann“ beim Patienten selbst: Name entfällt
            eigene.append(f"{e['nummer']} ({label})" if label else e["nummer"])
    tel_zu_tun = (personen or tel_hinweise or mehrfach) and not unklar
    if tel_zu_tun:
        person_ids = []
        for p in personen:
            if _ziffern(p["nummer"]) in vorhandene:
                continue  # schon als Bezugsperson erfasst – die Nummer darf aus dem Telefonfeld trotzdem heraus
            mobil = ist_mobil(p["nummer"])
            s = neu(art="bezugsperson", quelle=p["feld"], auszug=p["auszug"], sicher=p["sicher"], hinweis=p["hinweis"],
                    werte={"beziehung": p["beziehung"], "name": p["name"], "telefon": "" if mobil else p["nummer"],
                           "mobil": p["nummer"] if mobil else "", "email": ""})
            person_ids.append(s["id"])
        neu_tel, neu_tel2 = (eigene[0] if eigene else ""), ", ".join(eigene[1:])
        tel_ids = []
        if len(neu_tel) <= 50 and len(neu_tel2) <= 50:
            for feld, wert in (("telefon", neu_tel), ("telefon2", neu_tel2)):
                if wert != q[feld]:
                    s = neu(art="feld", feld=feld, label=FELDER[feld], quelle=feld, alt=q[feld], neu=wert,
                            auszug=quelltexte[feld], abhaengig_von=person_ids,
                            hinweis="Nummern anderer Personen stehen danach bei den Bezugspersonen." if personen else "")
                    tel_ids.append(s["id"])
        for h in tel_hinweise:
            neu(art="hinweis", quelle="bemerkung", titel=h["titel"], alt=h["html"], text=h["inhalt"],
                auszug=h["inhalt"], abhaengig_von=person_ids + tel_ids,
                hinweis="Der vollständige Wortlaut ist danach in Telefon und Bezugspersonen aufgeteilt.")

    # Ärzte: Hausarzt und Überweisung (Freitext oder vollständiger Wortlaut aus den Hinweisen)
    for feld, rolle in (("hausarzt", "hausarzt"), ("ueberweisung_durch", "ueberweisend")):
        hinweis_feld = next((h for h in hw if h["feld"] == feld), None)
        text = hinweis_feld["inhalt"] if hinweis_feld else q[feld]
        werte = arzt_zerlegen(text)
        # Überweisung: nur, wenn erkennbar ein Arzt (Titel, Praxis, Adresse oder Telefon); sonst z. B. „Eigeninitiative“
        if werte is None or werte["name"].lower().strip(" .-") in KEIN_ARZT or (rolle == "ueberweisend" and not (
                re.search(r"\bdr\b|\bdipl|\bmed\b", werte["name"], re.I) or werte["plz"] or werte["telefon"]
                or werte["praxis"])):
            continue
        if any(z.rolle == rolle and _name_schluessel(z.arzt.name) == _name_schluessel(werte["name"])
               for z in patient.aerzte.filter(aktiv=True).select_related("arzt")):
            a_id = None  # schon zugeordnet: nur noch den Freitext aufräumen
        else:
            notiz = werte.pop("notiz")
            a_id = neu(art="arzt", rolle=rolle, quelle=feld, auszug=text, werte=werte, arzt_wahl="auto",
                       hinweis=f"Nicht zugeordnet: {notiz}" if notiz else "", sicher=not notiz)["id"]
        werte.pop("notiz", None)
        if q[feld]:
            neu(art="feld", feld=feld, label=FELDER[feld], quelle=feld, alt=q[feld], neu="", auszug=q[feld],
                abhaengig_von=[a_id] if a_id else [],
                hinweis="Die Übersicht zeigt danach den Arzt aus dem Reiter „Ärzte“ mit Link.")
        if hinweis_feld:
            neu(art="hinweis", quelle="bemerkung", titel=hinweis_feld["titel"], alt=hinweis_feld["html"],
                text=hinweis_feld["inhalt"], auszug=hinweis_feld["inhalt"], abhaengig_von=[a_id] if a_id else [])
    return schritte


def erstellen(patient) -> Datenpflegevorschlag | None:
    """Neuen Vorschlag anlegen (den offenen ersetzen, wenn sich die Akte geändert hat); ``None``, wenn nichts zu tun."""
    try:
        patient.pruefe_bearbeitbar()
    except Exception:  # noqa: BLE001 – abgeschlossene oder eingeschränkte Akte: nichts vorschlagen
        return None
    q = _quelle(patient)
    offen = patient.datenpflegevorschlaege.filter(status=Datenpflegevorschlag.Status.OFFEN).first()
    if offen is not None and offen.quelle == q:
        return offen
    schritte = schritte_bauen(patient)
    with transaction.atomic():
        if offen is not None:
            offen.status = Datenpflegevorschlag.Status.VERALTET
            offen.erledigt_am = timezone.now()
            offen.save(update_fields=["status", "erledigt_am"])
        if not schritte:
            return None
        return Datenpflegevorschlag.objects.create(
            patient=patient, quelle=q, schritte=schritte,
            ki_offen=any(not s["sicher"] for s in schritte))


def kandidaten(qs):
    """Akten mit etwas zum Aufräumen: Hinweise aus der Übernahme, Hausarzt/Überweisung als Freitext, Telefon mit Text."""
    from django.db.models import Q

    return qs.filter(Q(bemerkung__contains="<strong>") | ~Q(hausarzt="")
                     | Q(ueberweisung_durch__iregex=r"(dr\.|praxis|[0-9]{5})")
                     | Q(telefon__iregex=r"[a-zA-Z(]") | Q(telefon2__iregex=r"[a-zA-Z(]") | Q(telefon__contains="  ")
                     | Q(telefon__iregex=r"[0-9][ ,;/]+0[0-9]{3}.*[0-9]{4}"))


def alle_erstellen(qs, hoechstens: int = 500) -> int:
    """Für bis zu ``hoechstens`` Akten Vorschläge erstellen; → Zahl neuer bzw. erneuerter Vorschläge."""
    n = 0
    for p in kandidaten(qs).order_by("id")[:hoechstens * 4]:
        vorher = p.datenpflegevorschlaege.filter(status=Datenpflegevorschlag.Status.OFFEN).values_list("id", flat=True)
        vorher = set(vorher)
        v = erstellen(p)
        if v is not None and v.pk not in vorher:
            n += 1
            if n >= hoechstens:
                break
    return n


# --------------------------------------------------------------------------------------------- Darstellung
def darstellung(v: Datenpflegevorschlag) -> list[dict]:
    """Schritte mit Live-Daten: Treffer in der Ärzteliste (auch Ärzte, die eine frühere Freigabe gerade angelegt
    hat – so entsteht derselbe Hausarzt nicht zweimal)."""
    aus = []
    for s in v.schritte:
        s = dict(s)
        if s["art"] == "arzt":
            treffer = aerzte_treffer(s["werte"])
            s["treffer"] = [{"id": a.id, "name": a.name, "praxis": a.praxis, "ort": a.ort, "plz": a.plz,
                             "strasse": a.strasse, "telefon": a.telefon, "email": a.email} for a in treffer]
            if s.get("arzt_wahl") == "auto":
                s["arzt_wahl"] = treffer[0].id if len(treffer) == 1 else "neu"
        aus.append(s)
    return aus


# --------------------------------------------------------------------------------------------- Umsetzen
class Veraltet(ValidationError):
    pass


def schritte_uebernehmen(v: Datenpflegevorschlag, eingabe) -> list[dict]:
    """Bearbeitete Schritte aus der Oberfläche prüfen: nur ``an``, ``werte``, ``neu``, ``rolle`` und ``arzt_wahl``
    sind änderbar; ``alt``, ``quelle`` und Abhängigkeiten bleiben wie vorgeschlagen. Wirft ``ValidationError``."""
    eingabe = {str(e.get("id")): e for e in (eingabe or []) if isinstance(e, dict)}
    fehler, aus = {}, []
    for s in v.schritte:
        s = {**s, "werte": dict(s.get("werte") or {})} if "werte" in s else dict(s)
        e = eingabe.get(s["id"], {})
        if "an" in e:
            s["an"] = bool(e["an"])
        if s["art"] in ("arzt", "bezugsperson") and isinstance(e.get("werte"), dict):
            laengen = ARZT_LAENGE if s["art"] == "arzt" else PERSON_LAENGE
            for k, grenze in laengen.items():
                if k in e["werte"]:
                    wert = str(e["werte"][k] or "").strip()
                    if len(wert) > grenze:
                        fehler[f"{s['id']}.{k}"] = f"Höchstens {grenze} Zeichen."
                    s["werte"][k] = wert
        if s["art"] == "arzt":
            if "rolle" in e:
                if e["rolle"] not in ROLLEN:
                    fehler[f"{s['id']}.rolle"] = "Unbekannte Rolle."
                s["rolle"] = e["rolle"]
            if "arzt_wahl" in e:
                w = e["arzt_wahl"]
                if w not in ("auto", "neu") and not (isinstance(w, int) or str(w).isdigit()):
                    fehler[f"{s['id']}.arzt_wahl"] = "Bitte einen Arzt wählen oder „neu anlegen“."
                s["arzt_wahl"] = int(w) if str(w).isdigit() else w
        if s["art"] == "feld" and "neu" in e:
            s["neu"] = str(e["neu"] or "").strip()
            if len(s["neu"]) > LAENGE[s["feld"]]:
                fehler[f"{s['id']}.neu"] = f"Höchstens {LAENGE[s['feld']]} Zeichen."
        if s["an"]:
            if s["art"] in ("arzt", "bezugsperson") and not s["werte"].get("name"):
                fehler[f"{s['id']}.name"] = "Bitte einen Namen eingeben."
            for k in ("email",):
                if s.get("werte", {}).get(k):
                    try:
                        validate_email(s["werte"][k])
                    except ValidationError:
                        fehler[f"{s['id']}.{k}"] = "Keine gültige E-Mail-Adresse."
        aus.append(s)
    # Abhängigkeiten: ist ein Schritt ab, entfallen alle, die auf ihm aufbauen (sonst ginge z. B. die Nummer der Frau
    # aus dem Telefonfeld verloren, ohne dass sie als Bezugsperson angelegt wird)
    an = {s["id"]: s["an"] for s in aus}
    for _ in range(3):
        for s in aus:
            if s["an"] and any(not an.get(d, False) for d in s.get("abhaengig_von", [])):
                s["an"] = an[s["id"]] = False
    if fehler:
        raise ValidationError(fehler)
    if not any(s["an"] for s in aus):
        raise ValidationError({"fehler": "Bitte mindestens einen Schritt auswählen."})
    return aus


def umsetzen(v: Datenpflegevorschlag, schritte: list[dict], user) -> list[dict]:
    """Freigegebene Schritte in die Akte schreiben (eine Transaktion). Wirft ``Veraltet``, wenn sich ein betroffenes
    Feld seit dem Vorschlag geändert hat, ``PermissionError`` bei fehlenden Rechten."""
    from patienten.models import Bezugsperson, Patient, PatientArzt
    from stammdaten.models import Arzt, Auswahlwert

    from epm.api_basis import pruefe_schreibbereich

    v.refresh_from_db(from_queryset=Datenpflegevorschlag.objects.select_for_update())
    if v.status != Datenpflegevorschlag.Status.OFFEN:
        raise ValidationError({"fehler": "Dieser Vorschlag ist nicht mehr offen."})
    p = Patient.objects.select_for_update().get(pk=v.patient_id)
    if not user.hat_recht("akten_bearbeiten"):
        raise PermissionError("Dafür fehlt das Recht „Patienten anlegen, Diagnose, Therapie, Stammdaten ändern“.")
    pruefe_schreibbereich(user, p)
    p.pruefe_bearbeitbar()
    aktiv = [s for s in schritte if s["an"]]
    # Stand prüfen: nur umsetzen, was noch so in der Akte steht
    for s in aktiv:
        if s["art"] == "feld" and (getattr(p, s["feld"]) or "") != s["alt"]:
            raise Veraltet(f"„{s['label']}“ wurde inzwischen geändert – bitte den Vorschlag neu erstellen.")
        if s["art"] == "hinweis" and s["alt"] not in (p.bemerkung or ""):
            raise Veraltet("Die Hinweise aus der Übernahme wurden inzwischen geändert – bitte den Vorschlag neu "
                           "erstellen.")
    ergebnis, felder = [], set()
    for s in aktiv:
        if s["art"] == "arzt":
            wahl = s.get("arzt_wahl", "auto")
            if wahl == "auto":
                treffer = aerzte_treffer(s["werte"])
                wahl = treffer[0].id if len(treffer) == 1 else "neu"
            if wahl == "neu":
                if not user.hat_recht("versorger_pflegen"):
                    raise PermissionError("Einen neuen Arzt anlegen darf nur, wer „Versorger, Ansprechpartner und "
                                          "Ärzte pflegen“ darf – bitte einen vorhandenen Arzt wählen.")
                arzt = Arzt.objects.create(**{k: s["werte"].get(k, "") for k in ARZT_LAENGE})
                ergebnis.append({"modell": "arzt", "id": arzt.id, "aktion": "angelegt", "text": arzt.name})
            else:
                arzt = Arzt.objects.filter(pk=wahl).first()
                if arzt is None:
                    raise ValidationError({f"{s['id']}.arzt_wahl": "Der gewählte Arzt existiert nicht mehr."})
            z, angelegt = PatientArzt.objects.get_or_create(patient=p, arzt=arzt, rolle=s["rolle"], aktiv=True,
                                                            defaults={"angelegt_von": user})
            ergebnis.append({"modell": "patientarzt", "id": z.id, "aktion": "zugeordnet" if angelegt else "vorhanden",
                             "text": f"{z.get_rolle_display()}: {arzt.name}"})
        elif s["art"] == "bezugsperson":
            w = s["werte"]
            beziehung = None
            if w.get("beziehung"):
                beziehung = (Auswahlwert.objects.filter(liste=Auswahlwert.Liste.BEZIEHUNG,
                                                        wert__iexact=w["beziehung"]).first()
                             or Auswahlwert.objects.create(liste=Auswahlwert.Liste.BEZIEHUNG, wert=w["beziehung"]))
            b = Bezugsperson.objects.create(patient=p, beziehung=beziehung, name=w["name"], telefon=w.get("telefon", ""),
                                            mobil=w.get("mobil", ""), email=w.get("email", ""), angelegt_von=user,
                                            notiz="aus der Datenpflege (Altdaten), freigegeben")
            ergebnis.append({"modell": "bezugsperson", "id": b.id, "aktion": "angelegt",
                             "text": f"{w['name']}" + (f" ({w['beziehung']})" if w.get("beziehung") else "")})
        elif s["art"] == "feld":
            setattr(p, s["feld"], s["neu"])
            felder.add(s["feld"])
            ergebnis.append({"modell": "patient", "id": p.id, "aktion": "geändert", "text": s["label"]})
        elif s["art"] == "hinweis":
            p.bemerkung = p.bemerkung.replace(s["alt"], "", 1).strip()
            felder.add("bemerkung")
            ergebnis.append({"modell": "patient", "id": p.id, "aktion": "entfernt", "text": f"Hinweis „{s['titel']}“"})
    if felder:
        p.save()  # Längen und E-Mail sind geprüft; full_clean fiele über unbeteiligte Altdaten (z. B. Größe)
    v.status = Datenpflegevorschlag.Status.UMGESETZT
    v.schritte = schritte
    v.erledigt_am, v.erledigt_von, v.ergebnis = timezone.now(), user, ergebnis
    v.save(update_fields=["status", "schritte", "erledigt_am", "erledigt_von", "ergebnis"])
    return ergebnis


# --------------------------------------------------------------------------------------------- KI (nachts)
KI_SYSTEM = (
    "Du hilfst bei der Datenpflege einer Patientenakte. Du bekommst Freitext aus einem Altsystem (Telefonfeld) und den "
    "Patienten (Vorname, Nachname, Geschlecht). Ordne jede Telefonnummer zu: gehört sie dem Patienten selbst oder einer "
    "anderen Person? Für andere Personen gib die Beziehung zum Patienten an (z. B. Ehefrau, Ehemann, Tochter, Sohn, "
    "Mutter, Vater, Betreuer/in, Nachbar/in) – nur, wenn sie aus dem Text hervorgeht oder sehr naheliegt – und den "
    "Namen, wie er im Text steht. Erfinde nichts. Antworte nur mit JSON.")
KI_SCHEMA = {
    "type": "object",
    "properties": {"nummern": {"type": "array", "items": {
        "type": "object",
        "properties": {"nummer": {"type": "string"}, "eigen": {"type": "boolean"},
                       "beziehung": {"type": "string"}, "name": {"type": "string"},
                       "sicher": {"type": "boolean"}},
        "required": ["nummer", "eigen", "beziehung", "name", "sicher"]}}},
    "required": ["nummern"],
}
ERLAUBTE_BEZIEHUNGEN = {b for _, b in BEZIEHUNGEN} | {"Ehepartner/in", "Angehörige/r"}


def ki_pruefen(v: Datenpflegevorschlag, client) -> Datenpflegevorschlag:
    """Unsichere Bezugspersonen eines Vorschlags vom lokalen Modell gegenlesen lassen (nur Beziehung und Name; die
    Nummern stammen immer aus den Regeln). Ohne Modell oder bei Fehlern bleibt der Vorschlag, wie er ist."""
    from ki.modell import ModellFehler

    personen = [s for s in v.schritte if s["art"] == "bezugsperson" and not s["sicher"]]
    if client is None or not personen:
        Datenpflegevorschlag.objects.filter(pk=v.pk).update(ki_offen=False)
        return v
    p = v.patient
    text = "\n".join(
        [f"Patient: {p.vorname} {p.nachname}, Geschlecht: {p.get_geschlecht_display()}",
         f"Telefonfeld: {v.quelle.get('telefon', '')}", f"Telefon 2: {v.quelle.get('telefon2', '')}"]
        + [f"Hinweis: {h['inhalt']}" for h in hinweise(v.quelle.get("bemerkung", "")) if h["feld"] in ("telefon",
                                                                                                     "telefon2")])
    try:
        daten = client.chat(KI_SYSTEM, text, schema=KI_SCHEMA, max_tokens=600).json()
    except ModellFehler:
        return v
    je_nummer = {_ziffern(n.get("nummer", "")): n for n in daten.get("nummern", []) if isinstance(n, dict)}
    schritte, geaendert = [dict(s) for s in v.schritte], False
    for s in schritte:
        if s["art"] != "bezugsperson" or s["sicher"]:
            continue
        nummer = _ziffern(s["werte"].get("mobil") or s["werte"].get("telefon"))
        k = je_nummer.get(nummer)
        if not k or k.get("eigen"):
            continue
        werte = dict(s["werte"])
        beziehung = str(k.get("beziehung") or "").strip()
        if beziehung in ERLAUBTE_BEZIEHUNGEN and beziehung != werte["beziehung"]:
            s["hinweis"] = (f"KI: „{beziehung}“ statt „{werte['beziehung']}“ – bitte prüfen." if werte["beziehung"]
                            else f"KI schlägt „{beziehung}“ vor – bitte prüfen.")
            werte["beziehung"], geaendert = beziehung, True
        elif beziehung == werte["beziehung"] and beziehung:
            s["hinweis"] = (s["hinweis"] + " KI sieht es genauso.").strip()
            geaendert = True
        s["werte"] = werte
    Datenpflegevorschlag.objects.filter(pk=v.pk, status=Datenpflegevorschlag.Status.OFFEN).update(
        ki_offen=False, **({"schritte": schritte, "verfahren": "regeln+ki"} if geaendert else {}))
    v.refresh_from_db()
    return v


def ki_holen() -> Datenpflegevorschlag | None:
    return (Datenpflegevorschlag.objects.filter(status=Datenpflegevorschlag.Status.OFFEN, ki_offen=True)
            .select_related("patient").order_by("erstellt_am", "id").first())
