"""Firmen DSKM und Regeneration Clinic anlegen (Anforderung 11.10.2026). Bis hierhin war alles DSKM: alle Akten,
alle Einträge und alle Konten (mit ihrer bisherigen Rolle) gehören der DSKM; bei der Regeneration Clinic hat zunächst
niemand Zugang – die Administration vergibt die Rollen unter Benutzer (Rolle bei der DSKM bleibt ``User.rolle``)."""
from django.db import migrations

EINTRAEGE = [("patienten", m) for m in ("Gewichtsmessung", "Kontakt", "Termin", "Bezugsperson", "PatientArzt",
                                        "Diagnose", "Therapieschritt", "Dokument")] + [
    ("befunde", "Laborbefund"), ("befunde", "BiaMessung"), ("infusionen", "Infusionsplan"), ("berichte", "Bericht")]


def anlegen(apps, schema_editor):
    # Kontakte und freigegebene Pläne sind per Trigger unveränderlich (audit/schutz.py) – hier wird nur die Herkunft
    # „DSKM“ nachgetragen, daher im Wartungsmodus dieser einen Transaktion
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET LOCAL epm.wartung = 'on'")
    Firma = apps.get_model("stammdaten", "Firma")
    dskm, _ = Firma.objects.get_or_create(kuerzel="dskm", defaults={
        "name": "Deutsche Stiftung Krankheitsbedingte Mangelernährung", "kurzname": "DSKM", "absender": "",
        "altdaten": True, "reihenfolge": 1})
    Firma.objects.get_or_create(kuerzel="rg", defaults={
        "name": "Regeneration Clinic", "kurzname": "RG", "absender": "rg", "altdaten": False, "reihenfolge": 2})
    Absenderangaben = apps.get_model("stammdaten", "Absenderangaben")
    Absenderangaben.objects.get_or_create(art="rg", defaults={"name": "Regeneration Clinic"})

    Patient = apps.get_model("patienten", "Patient")
    PatientFirma = apps.get_model("patienten", "PatientFirma")
    PatientFirma.objects.bulk_create([PatientFirma(patient_id=pid, firma=dskm)
                                      for pid in Patient.objects.values_list("id", flat=True)], ignore_conflicts=True)
    for app, name in EINTRAEGE:
        apps.get_model(app, name).objects.filter(firma__isnull=True).update(firma=dskm)
    Logo = apps.get_model("stammdaten", "Logo")
    Logo.objects.filter(firma__isnull=True).update(firma=dskm)
    # Konten: die Rolle bei der DSKM ist weiter ``User.rolle`` (unverändert); Mitgliedschaften gibt es nur für
    # weitere Firmen – bei der Regeneration Clinic zunächst niemand


class Migration(migrations.Migration):
    dependencies = [
        ("patienten", "0019_bezugsperson_firma_diagnose_firma_dokument_firma_and_more"),
        ("stammdaten", "0021_firma_alter_absenderangaben_art_and_more"),
        ("befunde", "0002_biamessung_firma_historicalbiamessung_firma_and_more"),
        ("berichte", "0002_bericht_firma_historicalbericht_firma"),
        ("infusionen", "0008_historicalinfusionsplan_firma_infusionsplan_firma"),
        ("accounts", "0010_historicalmitgliedschaft_mitgliedschaft"),
    ]
    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
