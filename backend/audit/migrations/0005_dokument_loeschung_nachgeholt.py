"""Audit-Log: Löschung nach einer Wiederherstellung nachgeholt (Art. 17 DSGVO, U15, 02.10.2026)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0004_dokumente_umhaengen_loeschen'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemereignis',
            name='art',
            field=models.CharField(choices=[('anmeldung', 'Anmeldung'), ('anmeldung_fehlgeschlagen', 'Anmeldung fehlgeschlagen'), ('anmeldung_gesperrt', 'Anmeldung gesperrt (zu viele Fehlversuche)'), ('2fa_fehlgeschlagen', '2FA-Code falsch'), ('abmeldung', 'Abmeldung'), ('kennwort_geaendert', 'Kennwort geändert'), ('2fa_eingerichtet', '2FA eingerichtet'), ('benutzer_angelegt', 'Benutzer angelegt'), ('benutzer_geaendert', 'Benutzer geändert'), ('benutzer_gesperrt', 'Benutzer gesperrt'), ('rechte_geaendert', 'Rechte geändert'), ('einmal_kennwort', 'Einmal-Kennwort erzeugt'), ('2fa_zurueckgesetzt', '2FA zurückgesetzt'), ('akte_abgeschlossen', 'Akte abgeschlossen'), ('akte_geoeffnet', 'Akte wieder geöffnet'), ('plan_freigegeben', 'Infusionsplan freigegeben'), ('stammdaten', 'Stammdaten geändert'), ('vorlage', 'Vorlage geändert'), ('backup', 'Backup'), ('export', 'Export'), ('testdaten', 'Testdaten zurückgesetzt'), ('dokument_umgehaengt', 'Dokument anderem Patienten zugeordnet'), ('dokument_geloescht', 'Dokument endgültig gelöscht'), ('dokument_loeschen_abgelehnt', 'Löschen eines Dokuments abgelehnt'), ('dokument_loeschung_nachgeholt', 'Löschung eines Dokuments nachgeholt')], db_index=True, max_length=40),
        ),
    ]
