#!/bin/sh
# Start: Datenbank-Migrationen, statische Dateien, dann Gunicorn.
# Andere Befehle werden direkt ausgeführt, z. B.:  python manage.py test
set -e
if [ "${1:-server}" = "server" ]; then
  python manage.py migrate --noinput
  python manage.py createcachetable  # Drosselung der Anmeldung (CACHES in settings.py)
  # nach einer Wiederherstellung (F63): Eintrag im Audit-Log, alle Anmeldungen beenden
  python manage.py epm_wiederherstellungen_nachtragen || echo "WARNUNG: Wiederherstellungen nicht geprüft"
  # Art. 17 DSGVO: Löschungen nachholen, die eine Wiederherstellung zurückgebracht hat (sonst nichts)
  python manage.py epm_loeschungen_nachholen || echo "WARNUNG: Löschliste nicht geprüft"
  python manage.py collectstatic --noinput --verbosity 0
  # Je Prozess 4 Threads (Performance-Prüfung 14.11.2026): Eine Akte fragt 17–27 Dinge gleichzeitig an, eine PDF-Ansicht
  # rechnet 0,25–0,8 s. Mit 3 Prozessen ohne Threads warteten alle anderen Anfragen in der Schlange. Zustand je Anfrage
  # (aktive Firma) liegt in einer ContextVar, also getrennt je Thread; höchstens 12 Datenbankverbindungen.
  exec gunicorn epm.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout 120 \
    --worker-tmp-dir /tmp \
    --forwarded-allow-ips "*" \
    --access-logfile - \
    --access-logformat '%(h)s "%(r)s" %(s)s %(b)s %(M)sms'
fi
if [ "$1" = "ki" ]; then
  # KI (Experimentell): Nachtverarbeitung und Berichtsentwürfe (eigener Container ki-worker, Datenbank-Rolle epm_ki)
  exec python manage.py epm_ki
fi
if [ "$1" = "ocr" ]; then
  # Texterkennung für „Scans“ (eigener Container, gleiches Image): arbeitet die Warteschlange ab, räumt stündlich auf
  exec python manage.py epm_ocr
fi
exec "$@"
