"""ICD-10-GM-Liste der Praxis als Vorlagen unter Vorlagen › Diagnosen (Liste „Erkrankungen – maximal erweiterte
ICD-10-GM-Liste für IT“, 13.10.2026).

* Diabetes mellitus E10–E14 vollständig fünfstellig: 4. Stelle = Komplikation, 5. Stelle 0 = nicht entgleist,
  1 = entgleist; bei .7 gelten 2/3 (sonstige multiple) und 4/5 (diabetisches Fußsyndrom).
* Gesamtliste der Erkrankungen aus Doku und Arztbriefen. Codes der Liste mit offener Stelle („M85.8-“) stehen
  vierstellig im Katalog (Osteopenie zusätzlich als M85.89); die Lokalisation wird in der Akte ergänzt.
* Das Zusatzkennzeichen (G/V/Z/A) und die Seite gehören zur Diagnose in der Akte, nicht in den Katalog.

Wiederholbar und schonend: Es wird nur angelegt, was als Kombination aus Code und Bezeichnung fehlt. Bestehende
Einträge – auch ausgeblendete – bleiben, wie sie sind. Gelöscht wird nichts.
"""
from django.db import migrations

DIABETES_TYPEN = [
    ("E10", "Diabetes mellitus Typ 1"),
    ("E11", "Diabetes mellitus Typ 2"),
    ("E12", "Diabetes mellitus bei Fehl-/Mangelernährung"),
    ("E13", "Sonstiger näher bezeichneter Diabetes mellitus (z. B. pankreopriv)"),
    ("E14", "Nicht näher bezeichneter Diabetes mellitus"),
]

DIABETES_KOMPLIKATIONEN = [
    ("0", "mit Koma"),
    ("1", "mit Ketoazidose"),
    ("2", "mit Nierenkomplikationen"),
    ("3", "mit Augenkomplikationen"),
    ("4", "mit neurologischen Komplikationen"),
    ("5", "mit peripheren vaskulären Komplikationen"),
    ("6", "mit sonstigen näher bezeichneten Komplikationen"),
    ("8", "mit nicht näher bezeichneten Komplikationen"),
    ("9", "ohne Komplikationen"),
]

DIABETES_MULTIPEL = [
    ("72", "mit sonstigen multiplen Komplikationen, nicht entgleist"),
    ("73", "mit sonstigen multiplen Komplikationen, entgleist"),
    ("74", "mit multiplen Komplikationen, mit diabetischem Fußsyndrom, nicht entgleist"),
    ("75", "mit multiplen Komplikationen, mit diabetischem Fußsyndrom, entgleist"),
]

ERKRANKUNGEN = [
    ("J45.9", "Asthma bronchiale"),
    ("E06.3", "Hashimoto-Thyreoiditis"),
    ("E07.9", "Schilddrüsenfehlfunktion"),
    ("L20.9", "Neurodermitis (atopisches Ekzem)"),
    ("L40.3", "Psoriasis plantaris / palmoplantaris"),
    ("F33.9", "Rezidivierende depressive Störung"),
    ("F44.81", "Dissoziative Identitätsstörung (DIS)"),
    ("K91.1", "Dumpingsyndrom"),
    ("E88.9", "Metabolisches Syndrom"),
    ("M77.3", "Fersensporn"),
    ("M21.4", "Senk-Spreizfuß"),
    ("M25.5", "Arthralgie"),
    ("M54.5", "Chronische Rückenschmerzen / Kreuzschmerz"),
    ("M67.4", "Handganglion"),
    ("J34.2", "Nasenseptumdeviation"),
    ("J33.8", "Polypöse Sinusitis"),
    ("E87.6", "Hypokaliämie"),
    ("R43.0", "Hyposmie"),
    ("E16.1", "Chronische hyperinsulinäre Hypoglykämie"),
    ("E16.1", "Pseudo-Nesidioblastose"),
    ("K86.83", "Iatrogene / exokrine Pankreasinsuffizienz"),
    ("K91.2", "Kurzdarmsyndrom (postchirurgisch)"),
    ("K90.9", "Malabsorptionssyndrom"),
    ("N80.9", "Endometriose"),
    ("K31.1", "Magenpylorusstenose"),
    ("K31.88", "Gastroparese"),
    ("M15.9", "Polyarthrose"),
    ("I73.0", "Raynaud-Syndrom"),
    ("M85.8", "Osteopenie"),
    ("M85.89", "Osteopenie, multiple Lokalisationen"),
    ("I89.0", "Lymphödem Grad 2"),
    ("D64.9", "Anämie, nicht näher bezeichnet"),
    ("D50.9", "Eisenmangelanämie"),
    ("M46.1", "Sakroiliitis"),
    ("I35.1", "Aortenklappeninsuffizienz"),
    ("E61.4", "Zinkmangel"),
    ("E55.9", "Vitamin-D-Mangel / -Insuffizienz"),
    ("E53.8", "Vitamin-B12-Mangel"),
    ("E56.1", "Vitamin-K-Mangel"),
    ("E58", "Calciummangel"),
    ("E61.1", "Eisenmangel"),
    ("E44.0", "Krankheitsbedingte Mangelernährung mäßigen Grades"),
    ("E21.1", "Sekundärer Hyperparathyreoidismus, nicht renalen Ursprungs"),
    ("M80.8", "Manifeste sekundäre Osteoporose mit pathologischen Frakturen"),
    ("M84.4", "Pathologische Fraktur"),
    ("G62.9", "Polyneuropathie / sensomotorische Polyneuropathie"),
    ("E16.2", "Rezidivierende Hypoglykämien (Dumping)"),
    ("K59.1", "Chronische Diarrhoe"),
    ("M85.55", "Aneurysmatische Knochenzyste des Beckens"),
    ("N18.3", "Chronische Nierenkrankheit Stadium 3"),
    ("K86.18", "Chronische Pankreatitis"),
    ("K86.88", "Pankreasatrophie"),
    ("Z98.0", "Zustand nach multiplen Eingriffen oberer GIT / Gastrektomie"),
    ("T82.7", "Katheterassoziierte Infektion"),
    ("I89.01", "Lymphinsuffizienz / Lymphödem beidseits"),
]


def eintraege():
    """Alle Einträge der Liste als (ICD-Code, Bezeichnung)."""
    liste = []
    for typ, name in DIABETES_TYPEN:
        for stelle, komplikation in DIABETES_KOMPLIKATIONEN:
            liste.append((f"{typ}.{stelle}0", f"{name}, {komplikation}, nicht entgleist"))
            liste.append((f"{typ}.{stelle}1", f"{name}, {komplikation}, entgleist"))
        for stellen, komplikation in DIABETES_MULTIPEL:
            liste.append((f"{typ}.{stellen}", f"{name}, {komplikation}"))
    return sorted(liste) + ERKRANKUNGEN


def vorwaerts(apps, schema_editor):
    Diagnosevorlage = apps.get_model("stammdaten", "Diagnosevorlage")
    vorhanden = set(Diagnosevorlage.objects.values_list("icd_code", "bezeichnung"))
    Diagnosevorlage.objects.bulk_create(
        [Diagnosevorlage(icd_code=code, bezeichnung=name) for code, name in eintraege() if (code, name) not in vorhanden])


class Migration(migrations.Migration):

    dependencies = [
        ("stammdaten", "0023_technik_bis"),
    ]

    operations = [
        migrations.RunPython(vorwaerts, migrations.RunPython.noop),
    ]
