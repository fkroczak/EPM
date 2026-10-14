"""Mitgelieferte Vorlagen der Regeneration Clinic (13.10.2026): Laboranforderungen, Bildgebung, Funktionsdiagnostik,
Aufklärungen, Schweigepflichtentbindung und ÖGK-Formulare; dazu die Laborprofile Malabsorption MAL-01 bis MAL-06
(14.10.2026, ``werkzeuge/rgc-laborprofile.py``, Datenmigration ``0011_rgc_laborprofile``).

Die Word-Dateien der RGC hat ``werkzeuge/rgc-vorlagen.py`` in Blöcke umgesetzt (``statisch/rgc/*.json``). Die
Datenmigration ``0007_rgc_vorlagen`` legt sie einmal als eigene Schreiben der Firma RGC an (Fassung 1 in Gebrauch);
danach werden sie wie jede eigene Vorlage unter Vorlagen › Dokumentvorlagen gepflegt.
"""
import json
from pathlib import Path

from django.utils import timezone

ORDNER = Path(__file__).resolve().parent / "statisch" / "rgc"

# Briefkopf der RGC aus den Angaben der Vorlagen (nur leere Felder werden ergänzt)
ABSENDER_RGC = {
    "name": "Regeneration Clinic SIA", "strasse": "Jāņa Asara iela 3", "plz": "LV-1009", "ort": "Rīga",
    "telefon": "+371 28717452", "email": "info@regeneration-clinic.eu",
    "fusszeile": "Ārstniecības iestāde · Health Institution Code 001000289 · Reg.-Nr. 40203593175",
}


def vorlagen() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(ORDNER.glob("*.json"))]


def schluessel(quelle: str) -> str:
    """„RC_Vorlage_04_Endokrinologie“ → „eigen-rgc-a04“, „07_Aufklaerung_…“ → „eigen-rgc-f07“,
    „RC_Labor_MAL-02A“ (Laborprofile Malabsorption) → „eigen-rgc-mal02a“."""
    if quelle.startswith("RC_Labor_MAL-"):
        return f"eigen-rgc-mal{quelle.removeprefix('RC_Labor_MAL-').lower()}"
    if quelle.startswith("RC_Vorlage_"):
        return f"eigen-rgc-a{quelle.split('_')[2]}"
    return f"eigen-rgc-f{quelle.split('_')[0]}"


def anlegen(apps, schema_editor=None):
    Firma = apps.get_model("stammdaten", "Firma")
    EigenesSchreiben = apps.get_model("vorlagen", "EigenesSchreiben")
    Dokumentvorlage = apps.get_model("vorlagen", "Dokumentvorlage")
    Absenderangaben = apps.get_model("stammdaten", "Absenderangaben")
    firma = Firma.objects.filter(kuerzel="rg").first()
    if firma is None:
        return
    jetzt = timezone.now()
    for v in vorlagen():
        quelle = f"rgc-{v['quelle']}"[:40]
        if EigenesSchreiben.objects.filter(mitgeliefert=quelle).exists():
            continue
        name = v["name"]
        if EigenesSchreiben.objects.filter(name__iexact=name).exists():
            name = f"{name} (RGC)"[:100]
        e = EigenesSchreiben.objects.create(
            schluessel=schluessel(v["quelle"]), name=name, beschreibung=v.get("beschreibung", "")[:300],
            mit_termin=False, aktiv=True, firma=firma, gruppe=v["gruppe"], mitgeliefert=quelle)
        Dokumentvorlage.objects.create(art=e.schluessel, version=1, status="aktiv", bloecke=v["bloecke"],
                                       notiz=f"Word-Vorlage der RGC: {v.get('datei', '')}"[:200],
                                       veroeffentlicht_am=jetzt)
    rg = Absenderangaben.objects.filter(art="rg").first()
    if rg is not None:
        geaendert = rg.name == "Regeneration Clinic"  # Vorbelegung vom 11.10.2026
        if geaendert:
            rg.name = ABSENDER_RGC["name"]
        for feld, wert in ABSENDER_RGC.items():
            if not getattr(rg, feld):
                setattr(rg, feld, wert)
                geaendert = True
        if geaendert:
            rg.save()
