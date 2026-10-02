"""Audit-Log: Ereignisse des Datenschutzes (Einschränkung, Einsicht, Akte gelöscht, Bereinigung)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0006_systemereignis_art_system'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemereignis',
            name='art',
            field=models.CharField(choices=[('anmeldung', 'Anmeldung'), ('anmeldung_fehlgeschlagen', 'Anmeldung fehlgeschlagen'), ('anmeldung_gesperrt', 'Anmeldung gesperrt (zu viele Fehlversuche)'), ('2fa_fehlgeschlagen', '2FA-Code falsch'), ('abmeldung', 'Abmeldung'), ('kennwort_geaendert', 'Kennwort geändert'), ('2fa_eingerichtet', '2FA eingerichtet'), ('benutzer_angelegt', 'Benutzer angelegt'), ('benutzer_geaendert', 'Benutzer geändert'), ('benutzer_gesperrt', 'Benutzer gesperrt'), ('rechte_geaendert', 'Rechte geändert'), ('einmal_kennwort', 'Einmal-Kennwort erzeugt'), ('2fa_zurueckgesetzt', '2FA zurückgesetzt'), ('akte_abgeschlossen', 'Akte abgeschlossen'), ('akte_geoeffnet', 'Akte wieder geöffnet'), ('plan_freigegeben', 'Infusionsplan freigegeben'), ('stammdaten', 'Stammdaten geändert'), ('vorlage', 'Vorlage geändert'), ('backup', 'Backup'), ('export', 'Export'), ('testdaten', 'Testdaten zurückgesetzt'), ('dokument_umgehaengt', 'Dokument anderem Patienten zugeordnet'), ('dokument_geloescht', 'Dokument endgültig gelöscht'), ('dokument_loeschen_abgelehnt', 'Löschen eines Dokuments abgelehnt'), ('dokument_loeschung_nachgeholt', 'Löschung eines Dokuments nachgeholt'), ('system', 'Systemverwaltung'), ('datenschutz', 'Datenschutz'), ('akte_eingeschraenkt', 'Verarbeitung einer Akte eingeschränkt'), ('akte_einschraenkung_aufgehoben', 'Einschränkung einer Akte aufgehoben'), ('akte_einsicht', 'Einsicht in eine eingeschränkte Akte'), ('akte_geloescht', 'Akte endgültig gelöscht'), ('akte_loeschen_abgelehnt', 'Löschen einer Akte abgelehnt'), ('protokoll_bereinigt', 'Audit-Log bereinigt')], db_index=True, max_length=40),
        ),
    ]
