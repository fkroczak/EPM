#!/bin/bash
# startet Backend (gunicorn, 3 Worker wie im Betrieb) + vite preview (gebautes Frontend)
pkill -f "gunicorn epm.wsgi" ; pkill -f "vite preview"; sleep 1
cd /home/user/EPM/backend
export DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:4173,https://127.0.0.1:8443 DJANGO_DEBUG=1 DJANGO_SECRET_KEY=x DB_HOST=localhost DB_PASSWORD=epm EPM_DOKUMENTE=/var/tmp/epm-dok EPM_SCANS=/var/tmp/epm-scans
export DJANGO_SETTINGS_MODULE=settings_mess PYTHONPATH=/var/tmp/mess
nohup gunicorn epm.wsgi:application --bind 127.0.0.1:8000 --workers 3 --threads 4 --timeout 120 > /var/tmp/mess/gunicorn.log 2>&1 &
cd /home/user/EPM/frontend && nohup npx vite preview --port 4173 --strictPort > /var/tmp/mess/preview.log 2>&1 &
for i in $(seq 1 40); do curl -sf http://127.0.0.1:4173/api/auth/status/ >/dev/null && break; sleep 0.5; done
curl -s -D- -o /dev/null http://127.0.0.1:4173/api/auth/status/ | grep -i "x-mess\|HTTP"
