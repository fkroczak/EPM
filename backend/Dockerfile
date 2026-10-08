# EPM Backend – wird auf dem PC gebaut und per docker save/load auf den Server gebracht.
#   docker build -t epm-backend:0.1.0 .
FROM python:3.13-slim AS bau
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install -r /tmp/requirements.txt \
 && /opt/venv/bin/pip freeze > /opt/venv/versionen.txt

# Modelle der zweiten Texterkennung (PP-OCRv5, UVDoc) – geprüft gegen scans/modelle/modelle.json. Braucht der Bau-Rechner
# keinen Zugang zu huggingface.co, entsteht das Image trotzdem; die Erkennung arbeitet dann nur mit Tesseract
# (Administration › System und „Scans“ zeigen das an).
FROM python:3.13-slim AS modelle
COPY scans/modelle/ /tmp/modelle/
RUN python /tmp/modelle/holen.py /opt/ocr-modelle || echo "WARNUNG: PP-OCR-Modelle fehlen im Image"

FROM python:3.13-slim
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=epm.settings \
    DJANGO_STATIC_ROOT=/app/staticfiles \
    EPM_TESSDATA=/usr/share/tesseract-ocr/5/tessdata \
    EPM_OCR_MODELLE=/opt/ocr-modelle
# Pango/HarfBuzz für WeasyPrint (PDF-Erzeugung). Die Schrift IBM Plex liegt im Repo (schriften/, OFL-Lizenz):
# Debian 13 (trixie) hat kein Paket fonts-ibm-plex mehr, so baut das Image auch offline und unabhängig davon.
# Tesseract mit Ausrichtungserkennung (osd) für „Scans“; das deutsche Modell ist das genaueste (tessdata_best) aus dem Repo
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
      fontconfig fonts-dejavu-core tesseract-ocr tesseract-ocr-osd \
 && rm -rf /var/lib/apt/lists/*
COPY scans/modelle/tesseract/deu.traineddata /usr/share/tesseract-ocr/5/tessdata/deu.traineddata
RUN tesseract --list-langs 2>&1 | grep -qx deu && tesseract --list-langs 2>&1 | grep -qx osd
COPY schriften/ /usr/local/share/fonts/ibm-plex/
RUN fc-cache -f /usr/local/share/fonts && fc-list | grep -q "IBM Plex Sans"
RUN groupadd --gid 10001 epm && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin epm
COPY --from=bau /opt/venv /opt/venv
COPY --from=modelle /opt/ocr-modelle /opt/ocr-modelle
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
