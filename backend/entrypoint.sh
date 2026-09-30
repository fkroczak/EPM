#!/bin/sh
# Start: Datenbank-Migrationen, statische Dateien, dann Gunicorn.
# Andere Befehle werden direkt ausgeführt, z. B.:  python manage.py test
set -e
if [ "${1:-server}" = "server" ]; then
  python manage.py migrate --noinput
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
