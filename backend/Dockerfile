# EPM Backend – wird auf dem PC gebaut und per docker save/load auf den Server gebracht.
#   docker build -t epm-backend:0.1.0 .
FROM python:3.13-slim AS bau
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install -r /tmp/requirements.txt \
 && /opt/venv/bin/pip freeze > /opt/venv/versionen.txt

FROM python:3.13-slim
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=epm.settings \
    DJANGO_STATIC_ROOT=/app/staticfiles
# Pango/HarfBuzz für WeasyPrint (PDF-Erzeugung), Schrift IBM Plex wie in der Oberfläche
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
      fonts-ibm-plex fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 10001 epm && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin epm
COPY --from=bau /opt/venv /opt/venv
WORKDIR /app
COPY --chown=root:root . /app
RUN sed -i "s/\r$//" /app/entrypoint.sh \
 && python -m compileall -q /app /opt/venv \
 && mkdir -p /app/staticfiles && chown 10001:10001 /app/staticfiles \
 && chmod 0755 /app/entrypoint.sh
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/auth/status/', timeout=4).status == 200 else 1)"
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["server"]
