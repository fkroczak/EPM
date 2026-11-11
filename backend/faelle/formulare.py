"""Formulare 01–12 der RGC (Revision 3) mit Platzhaltern des Behandlungsfalls (Dokumentenautomation, 26.10.2026).

Die Word-Vorlagen ließen Aufnahmedatum, Kooperationspartner, Kostenträger, Eingriff, OP-Datum und Kostenvoranschlag zum
Ausfüllen frei; im Fall stehen diese Angaben jetzt fest. Zugleich behoben: Bei der Umsetzung der Word-Dateien
(``werkzeuge/rgc-vorlagen.py``) war bei „Krankenkasse“, „Private Krankenversicherung“, „UV-Träger“, „Zusatzversicherung“
und „Rechtsanwalt“ die Anschrift des Patienten eingesetzt, bei „Versicherte Person“ fehlte der Name.

Die Datenmigration ``faelle.0003`` stellt jede mitgelieferte Vorlage um, die noch unverändert ist (nur Fassung 1, kein
Entwurf): vor dem ersten Import der Altdaten an Ort und Stelle (dann gibt es nur Fassung 1, ``vorlagen.fassung1``),
danach als Fassung 2 – Fassung 1 bleibt für bereits erzeugte PDFs erhalten.
Bearbeitete Vorlagen bleiben unberührt (dort die Felder im Editor einsetzen).
"""
import copy

AUFNAHME = ("Aufnahmedatum", "{{Fall.Aufnahme}}")
PARTNER = ("Kooperations-/Infrastrukturpartner", "{{Fall.Kooperationspartner}}")

# Vorlage → [(Anfang der Feldbezeichnung, neuer Wert)] in den Datenfeldern
FELDER = {
    "eigen-rgc-f01": [AUFNAHME, PARTNER],
    # Patientenerklärung GKV ambulant/tagesstationär (ersetzt die Fassung „Stundung“ V5, 11.11.2026)
    "eigen-rgc-f02": [("Unterzeichnende/r", "{{Patient.Name}}"),
                      ("Krankenkasse / Versichertennummer", "{{Fall.Kostenträger}} / {{Fall.Versichertennummer}}"),
                      ("Behandlungsanlass", "{{Fall.Diagnose}}"), ("Behandelnder Facharzt", "{{Fall.Arzt}}"),
                      ("Hausarzt", "{{Patient.Hausarzt}}")],
    "eigen-rgc-f03": [("UV-Träger", "{{Fall.Kostenträger}}"), ("Aktenzeichen des UV-Trägers", "{{Fall.Aktenzeichen}}"),
                      AUFNAHME, PARTNER],
    "eigen-rgc-f04": [("Versicherte Person", "{{Patient.Name}}"), ("Private Krankenversicherung", "{{Fall.Kostenträger}}"),
                      ("Versicherungsschein-Nr.", "{{Fall.Versichertennummer}}"), AUFNAHME, PARTNER],
    "eigen-rgc-f05": [("Versicherte Person", "{{Patient.Name}}"),
                      ("Stationäre Zusatzversicherung", "{{Fall.Kostenträger}}"),
                      ("Versicherungsschein-Nr.", "{{Fall.Versichertennummer}}"), AUFNAHME, PARTNER],
    "eigen-rgc-f06": [("Behandlungsfall ab", "{{Fall.Aufnahme}}")],
    "eigen-rgc-f07": [("Geplanter Eingriff", "{{Fall.Eingriff}}"), ("Operateur", "{{Fall.Operateur}}")],
    "eigen-rgc-f08": [("Geplanter Eingriff", "{{Fall.Eingriff}}"), ("Datum des Eingriffs", "{{Fall.OP_Datum}}")],
    "eigen-rgc-f09": [("Geplante Behandlung", "{{Fall.Eingriff}}"), ("Geplanter Termin", "{{Fall.Aufnahme}}"),
                      ("Kostenvoranschlag vom / Honorar", "{{Fall.Nummer}} · {{Leistungen.Summe}} EUR")],
    "eigen-rgc-f10": [("Geplante Behandlung", "{{Fall.Eingriff}}"), ("Geplanter Termin", "{{Fall.Aufnahme}}"),
                      ("Kostenvoranschlag vom / Honorar", "{{Fall.Nummer}} · {{Leistungen.Summe}} EUR")],
    "eigen-rgc-f11": [("Patient/in (Name, Vorname, Geburtsdatum)", "{{Patient.Name}}, geb. {{Patient.Geburtsdatum}}"),
                      ("Versicherungsträger / Versicherer", "{{Fall.Kostenträger}}"),
                      ("Kostenvoranschlag Nr. / Datum", "{{Fall.Nummer}} vom {{Heute}}")],
    "eigen-rgc-f12": [("Vollmachtgeber/in (Name, Vorname, Geburtsdatum)",
                       "{{Patient.Name}}, geb. {{Patient.Geburtsdatum}}"),
                      ("Versicherungsträger / Versicherer, Versicherungs-Nr.",
                       "{{Fall.Kostenträger}} · {{Fall.Versichertennummer}}"),
                      ("Behandlungsfall ab", "{{Fall.Aufnahme}}"),
                      ("Bevollmächtigte/r Rechtsanwalt", "____________________")],
}

# Anlage K: Gesamthonorar aus der Rechnung des Falls und die Leistungen als Tabelle (Leistungskatalog)
ANLAGE_K = "eigen-rgc-f11"
ZEILE_A_ALT = "(einschließlich Kooperationsklinik, Anästhesie, Implantate, Unterbringung) — EUR ______________"
ZEILE_A_NEU = "(einschließlich Kooperationsklinik, Anästhesie, Implantate, Unterbringung) — EUR {{Leistungen.Summe}}"
LEISTUNGEN = {"id": "leistungen", "typ": "tabelle", "bezeichnung": "Leistungen laut Kostenvoranschlag",
              "quelle": "leistungen", "optionen": {"ueberschrift": True, "ausblenden_wenn_leer": True}}


def umgestellt(art: str, bloecke: list) -> list | None:
    """Neue Blöcke mit den Feldern des Falls – None, wenn sich nichts ändert."""
    if art not in FELDER:
        return None
    neu = copy.deepcopy(bloecke)
    for b in neu:
        if b.get("typ") != "datenfelder":
            continue
        for e in b.get("felder", []):
            for anfang, wert in FELDER[art]:
                if e.get("label", "").startswith(anfang):
                    e["wert"] = wert
                    break
    if art == ANLAGE_K:
        for i, b in enumerate(neu):
            if b.get("typ") == "text" and ZEILE_A_ALT in b.get("text", ""):
                b["text"] = b["text"].replace(ZEILE_A_ALT, ZEILE_A_NEU)
                if not any(x.get("id") == LEISTUNGEN["id"] for x in neu):
                    neu.insert(i + 1, dict(LEISTUNGEN))
                break
    return neu if neu != bloecke else None


def umstellen(apps, schema_editor=None):
    """Vor dem ersten Import der Altdaten gibt es nur Fassung 1 (``vorlagen.fassung1``): dann wird sie ersetzt, danach
    entsteht Fassung 2 und Fassung 1 bleibt für bereits erzeugte PDFs erhalten."""
    from django.utils import timezone

    from vorlagen.fassung1 import import_durchgefuehrt

    vor_dem_import = not import_durchgefuehrt(apps)
    Dokumentvorlage = apps.get_model("vorlagen", "Dokumentvorlage")
    for art in FELDER:
        fassungen = list(Dokumentvorlage.objects.filter(art=art))
        if len(fassungen) != 1 or fassungen[0].version != 1 or fassungen[0].status != "aktiv":
            continue  # schon bearbeitet (weitere Fassung oder Entwurf) – bleibt, wie es ist
        alt = fassungen[0]
        bloecke = umgestellt(art, alt.bloecke)
        if bloecke is None:
            continue
        if vor_dem_import:
            Dokumentvorlage.objects.filter(pk=alt.pk).update(bloecke=bloecke)
            continue
        Dokumentvorlage.objects.filter(pk=alt.pk).update(status="abgeloest")
        Dokumentvorlage.objects.create(art=art, firma=alt.firma, version=2, status="aktiv", bloecke=bloecke,
                                       ausrichtung=alt.ausrichtung, veroeffentlicht_am=timezone.now(),
                                       notiz="Felder des Behandlungsfalls (Dokumentenautomation 26.10.2026)")
