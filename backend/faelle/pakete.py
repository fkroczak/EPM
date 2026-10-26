"""Paketregeln: welche Dokumente ein Fall je Kostenträgertyp automatisch bekommt (Anforderung 26.10.2026, Punkt 1).

Ein Paket ist eine Liste von Einträgen: die festen Dokumentarten ``op_bericht``, ``entlassbrief``, ``konsil``,
``rechnung`` oder der Schlüssel einer Vorlage (eigenes Schreiben, z. B. ``eigen-rgc-f02``). Ist die Aufklärung
Operation (Vorlage 07, ``eigen-rgc-f07``) im Paket, kommt der Zusatzbogen des Fachbereichs dazu.
"""
from .startvorlagen import ZUSATZBOEGEN

FESTE_ARTEN = {"op_bericht": "OP-Bericht", "entlassbrief": "Entlassungsbrief", "konsil": "Konsiliarbericht",
               "rechnung": "Rechnung"}
AUFKLAERUNG_OP = "eigen-rgc-f07"
MAX_EINTRAEGE = 40

# Mitgelieferte Kostenträgertypen mit Standardpaket (Vorlagen der RGC, Revision 3: 01–12)
_KERN = ["eigen-rgc-f06", "eigen-rgc-f07", "eigen-rgc-f08", "op_bericht", "entlassbrief", "rechnung"]
STANDARD = [
    ("at-oegk", "Österreich – ÖGK / SVS / BVAEB / KFA", "Österreich",
     ["eigen-rgc-f01", "eigen-rgc-f10", "eigen-rgc-f11", *_KERN]),
    ("at-selbstzahler", "Österreich – Selbstzahler mit Rückerstattung (ÖGK)", "Österreich",
     ["eigen-rgc-f09", "eigen-rgc-f11", *_KERN]),
    ("de-gkv", "Deutschland – GKV", "Deutschland", ["eigen-rgc-f02", "eigen-rgc-f11", *_KERN]),
    ("de-bg", "Deutschland – BG / Unfallversicherung", "Deutschland", ["eigen-rgc-f03", *_KERN]),
    ("de-pkv", "Deutschland – PKV", "Deutschland", ["eigen-rgc-f04", "eigen-rgc-f11", *_KERN]),
    ("de-zusatz", "Deutschland – stationäre Zusatzversicherung", "Deutschland",
     ["eigen-rgc-f05", "eigen-rgc-f11", *_KERN]),
    ("selbstzahler", "Selbstzahler", "", ["eigen-rgc-f11", *_KERN]),
    ("international", "International / andere Länder", "international", ["eigen-rgc-f11", *_KERN]),
]


def pruefe_paket(paket) -> list[str]:
    from vorlagen.felder import ist_eigen
    from vorlagen.models import EigenesSchreiben

    if not isinstance(paket, list):
        return ["Das Paket ist eine Liste von Dokumenten."]
    if len(paket) > MAX_EINTRAEGE:
        return [f"Höchstens {MAX_EINTRAEGE} Dokumente."]
    fehler = []
    bekannt = set(EigenesSchreiben.objects.filter(schluessel__in=[e for e in paket if ist_eigen(e)])
                  .values_list("schluessel", flat=True))
    gesehen = set()
    for e in paket:
        if not isinstance(e, str) or not (e in FESTE_ARTEN or e in bekannt):
            fehler.append(f"Unbekanntes Dokument „{e}“.")
        elif e in gesehen:
            fehler.append(f"„{e}“ steht doppelt im Paket.")
        gesehen.add(e)
    return fehler


def eintraege(fall) -> list[tuple[str, str]]:
    """[(Art, Vorlage)] des Pakets für den Fall: Art ist eine feste Art oder „vorlage“ (dann mit Schlüssel)."""
    liste = []
    for e in fall.kostentraegertyp.paket or []:
        if e in FESTE_ARTEN:
            liste.append((e, ""))
        else:
            liste.append(("vorlage", e))
            if e == AUFKLAERUNG_OP and fall.fachbereich in ZUSATZBOEGEN:
                liste.append(("vorlage", ZUSATZBOEGEN[fall.fachbereich][0]))
    return liste


def titel_fuer(art: str, vorlage: str = "") -> str:
    from vorlagen.models import art_name

    if art == "vorlage":
        return art_name(vorlage)[:200]
    return FESTE_ARTEN.get(art, art)


def paket_anlegen(fall, benutzer) -> list:
    """Legt die fehlenden Dokumente des Pakets als Entwurf an (vorhandene bleiben unberührt). → neue Dokumente."""
    from vorlagen.models import EigenesSchreiben

    from .models import FallDokument

    fall.pruefe_offen()
    vorhanden = {(d.art, d.vorlage) for d in fall.dokumente.exclude(art=FallDokument.Art.STORNO)
                 .filter(storniert_am__isnull=True)}
    aktive = set(EigenesSchreiben.objects.filter(aktiv=True).values_list("schluessel", flat=True))
    neu = []
    for art, vorlage in eintraege(fall):
        if (art, vorlage) in vorhanden or (vorlage and vorlage not in aktive):
            continue
        d = FallDokument(patient=fall.patient, fall=fall, art=art, vorlage=vorlage, titel=titel_fuer(art, vorlage),
                         aus_paket=True, erstellt_von=benutzer)
        d._history_user = benutzer
        d.save()
        vorhanden.add((art, vorlage))
        neu.append(d)
    return neu
