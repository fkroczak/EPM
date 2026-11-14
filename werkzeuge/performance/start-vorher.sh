#!/bin/bash
# Originalstand (git HEAD vor den Änderungen): Backend :8001, Frontend :4174
pkill -f "bind 127.0.0.1:8001"; pkill -f "port 4174"; sleep 1
cd /var/tmp/epm-vorher/backend
export DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:4174,https://127.0.0.1:8444 DJANGO_DEBUG=1 DJANGO_SECRET_KEY=x DB_HOST=localhost DB_PASSWORD=epm EPM_DOKUMENTE=/var/tmp/epm-dok EPM_SCANS=/var/tmp/epm-scans
export DJANGO_SETTINGS_MODULE=settings_mess PYTHONPATH=/var/tmp/mess
nohup gunicorn epm.wsgi:application --bind 127.0.0.1:8001 --workers 3 --timeout 120 > /var/tmp/mess/gunicorn-vorher.log 2>&1 &
cd /var/tmp/epm-vorher/frontend && nohup npx vite preview --port 4174 --strictPort > /var/tmp/mess/preview-vorher.log 2>&1 &
for i in $(seq 1 40); do curl -sf http://127.0.0.1:4174/api/auth/status/ >/dev/null && break; sleep 0.5; done
curl -s -D- -o /dev/null http://127.0.0.1:4174/api/auth/status/ | grep -i "x-mess-q\|HTTP"
