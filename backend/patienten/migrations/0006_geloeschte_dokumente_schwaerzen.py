"""Bestand: Dokumente, die vor dieser Version endgültig gelöscht wurden, nachträglich nach Art. 17 DSGVO behandeln
(U15, Festlegung 02.10.2026): Titel, Dateiname, Notiz und Datum in Historie und Audit-Log durch „[entfernt]“ ersetzen,
Prüfsumme und Pfad im Vorgang nachtragen. Danach ergänzt der Start des Backends die Löschliste."""
from django.db import migrations

PLATZHALTER = "[entfernt]"
ARTEN = ["dokument_umgehaengt", "dokument_geloescht", "dokument_loeschen_abgelehnt"]


def vorwaerts(apps, schema_editor):
    Vorgang = apps.get_model("patienten", "DokumentVorgang")
    Historie = apps.get_model("patienten", "HistoricalDokument")
    Ereignis = apps.get_model("audit", "SystemEreignis")
    vorgaenge = list(Vorgang.objects.filter(art="geloescht"))
    if not vorgaenge:
        return
    with schema_editor.connection.cursor() as c:
        c.execute("SET LOCAL epm.wartung = 'on'")  # Schutz-Trigger: nur in dieser Transaktion
    for v in vorgaenge:
        letzte = Historie.objects.filter(id=v.dokument_id, history_type="-").order_by("-history_date").first()
        if letzte is None:
            continue
        sha = letzte.sha256
        if not v.sha256:
            Vorgang.objects.filter(pk=v.pk).update(sha256=sha, datei=letzte.datei)
        Historie.objects.filter(id=v.dokument_id, sha256=sha).update(
            titel=PLATZHALTER, originalname=PLATZHALTER, notiz="", datum=None)
        for e in Ereignis.objects.filter(objekt=f"Dokument {v.dokument_id}", art__in=ARTEN):
            details = dict(e.details or {})
            if "titel" in details:
                details["titel"] = PLATZHALTER
            details.setdefault("sha256", sha)
            Ereignis.objects.filter(pk=e.pk).update(details=details)
    with schema_editor.connection.cursor() as c:
        c.execute("SET LOCAL epm.wartung = 'off'")


class Migration(migrations.Migration):

    dependencies = [
        ('patienten', '0005_dokumentvorgang_nachweis'),
        ('audit', '0005_dokument_loeschung_nachgeholt'),
    ]

    operations = [
        migrations.RunPython(vorwaerts, migrations.RunPython.noop),
    ]
