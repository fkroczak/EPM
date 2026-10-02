#!/bin/sh
# Start: Datenbank-Migrationen, statische Dateien, dann Gunicorn.
# Andere Befehle werden direkt ausgeführt, z. B.:  python manage.py test
set -e
if [ "${1:-server}" = "server" ]; then
  python manage.py migrate --noinput
  # nach einer Wiederherstellung (F63): Eintrag im Audit-Log, alle Anmeldungen beenden
  python manage.py epm_wiederherstellungen_nachtragen || echo "WARNUNG: Wiederherstellungen nicht geprüft"
  # Art. 17 DSGVO: Löschungen nachholen, die eine Wiederherstellung zurückgebracht hat (sonst nichts)
  python manage.py epm_loeschungen_nachholen || echo "WARNUNG: Löschliste nicht geprüft"
  python manage.py collectstatic --noinput --verbosity 0
  exec gunicorn epm.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout 120 \
    --worker-tmp-dir /tmp \
    --forwarded-allow-ips "*" \
    --access-logfile - \
    --access-logformat '%(h)s "%(r)s" %(s)s %(b)s %(M)sms'
fi
exec "$@"
