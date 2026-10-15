#!/usr/bin/env bash
# EPM – KI (Experimentell): Modellgrößen und Quantisierungen auf der Ziel-VM vergleichen (Plan Phase 0).
#
#   sudo epm-ki benchmark                         alle eingespielten Varianten (MODELLE.txt), synthetische Seiten
#   sudo epm-ki benchmark --eigene                zusätzlich eigene Seiten aus /srv/epm/data/ki/benchmark
#                                                 (hand_*.jpg, tabelle_*.png, alt_*.pdf; dazu NAME.txt / NAME.json)
#   sudo epm-ki benchmark --threads 6 --max-px 1280 --grosses-pdf 40
#
# Je Variante: eigener llama-server-Container „epm-ki-bench“ im Netz „intern“ (kein Weg nach außen), Messung von
# Speicher (Höchststand) und CPU von außen (docker stats), Qualität und Zeit im Container ki-worker
# (manage.py epm_ki_benchmark). Ergebnis: /srv/epm/data/ki/benchmark-<Datum>.md und .json.
# Am besten nachts oder am Wochenende laufen lassen – der Benchmark lastet die CPU voll aus.
set -euo pipefail
B="${EPM_BASIS:-/srv/epm}"
VORRAT="$B/ki-modelle"
EIGENE=""; THREADS=""; MAX_PX=1600; GROSS=20; SPEICHER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --modelle) VORRAT="$2"; shift ;;
    --eigene) EIGENE="/data/ki/benchmark" ;;
    --threads) THREADS="$2"; shift ;;
    --max-px) MAX_PX="$2"; shift ;;
    --grosses-pdf) GROSS="$2"; shift ;;
    --speicher) SPEICHER="$2"; shift ;;
    *) echo "Unbekannt: $1"; exit 2 ;;
  esac
  shift
done
[[ -f "$VORRAT/MODELLE.txt" ]] || { echo "Keine Modelle (sudo epm-ki einspielen DATEI)."; exit 1; }
cd "$B"
TAG="$(sed -n 's/^KI_MODELL_IMAGE_TAG=//p' .env)"
[[ -n "$TAG" ]] || { echo "Image ki-modell fehlt (sudo epm-ki einrichten)."; exit 1; }
THREADS="${THREADS:-$(sed -n 's/^KI_THREADS=//p' .env)}"; THREADS="${THREADS:-4}"
SPEICHER="${SPEICHER:-$(sed -n 's/^KI_SPEICHER=//p' .env)}"; SPEICHER="${SPEICHER:-8g}"
NETZ="$(docker network ls --format '{{.Name}}' | grep -E '(^|_)intern$' | head -n1)"
[[ -n "$NETZ" ]] || { echo "Netz „intern“ nicht gefunden – läuft EPM?"; exit 1; }
docker compose ps -q ki-worker | grep -q . || { echo "Container ki-worker läuft nicht (sudo epm-ki einrichten)."; exit 1; }
STEMPEL="$(date +%Y%m%d-%H%M)"
JSON="$B/data/ki/benchmark-$STEMPEL.json"
MD="$B/data/ki/benchmark-$STEMPEL.md"
echo "[" > "$JSON"
erstes=1
{
  echo "# KI-Benchmark $(date '+%d.%m.%Y %H:%M') – $(hostname)"
  echo
  echo "Threads $THREADS · Speichergrenze $SPEICHER · Bildgröße $MAX_PX px · großes PDF $GROSS Seiten"
  echo
  echo "| Variante | Laden (s) | RAM max | CPU Ø | s/Seite Scan | s/Seite Foto | s/Seite PDF | CER Scan | CER Foto | Labor-F1 Scan | Labor-F1 Foto |"
  echo "|---|---|---|---|---|---|---|---|---|---|---|"
} > "$MD"

name=""; datei=""; projektor=""
while IFS= read -r zeile; do
  case "$zeile" in
    NAME=*) name="${zeile#NAME=}" ;;
    DATEI=*) datei="${zeile#DATEI=}" ;;
    PROJEKTOR=*) projektor="${zeile#PROJEKTOR=}" ;;
    QUANT=*)
      echo "==> $name ($datei)"
      docker rm -f epm-ki-bench >/dev/null 2>&1 || true
      start=$(date +%s)
      docker run -d --name epm-ki-bench --network "$NETZ" --read-only --tmpfs /tmp --cap-drop ALL \
        --security-opt no-new-privileges:true --memory "$SPEICHER" --memory-swap "$SPEICHER" \
        -v "$VORRAT:/modelle:ro" -e KI_THREADS="$THREADS" -e KI_KONTEXT=16384 -e KI_SLOTS=1 \
        -e KI_MODELL_DATEI="$datei" -e KI_PROJEKTOR_DATEI="$projektor" \
        "epm-ki-modell:$TAG" >/dev/null
      bereit=0
      for _ in $(seq 1 180); do
        if docker compose exec -T ki-worker python -c "import urllib.request,sys; urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://epm-ki-bench:8080/health', timeout=3)" >/dev/null 2>&1; then bereit=1; break; fi
        sleep 5
      done
      laden=$(( $(date +%s) - start ))
      if [[ $bereit != 1 ]]; then
        echo "   lädt nicht (Speicher zu knapp?) – $(docker logs --tail 5 epm-ki-bench 2>&1 | tr '\n' ' ')"
        echo "| $name | – | – | – | lädt nicht | | | | | | |" >> "$MD"
        docker rm -f epm-ki-bench >/dev/null 2>&1 || true
        continue
      fi
      stats="$(mktemp)"
      ( while docker inspect epm-ki-bench >/dev/null 2>&1; do
          docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' epm-ki-bench >> "$stats" 2>/dev/null || true
          sleep 2
        done ) &
      messer=$!
      ergebnis="$(docker compose exec -T ki-worker python manage.py epm_ki_benchmark --url http://epm-ki-bench:8080 \
        --grosses-pdf "$GROSS" --max-px "$MAX_PX" ${EIGENE:+--eigene "$EIGENE"} 2>/dev/null | tail -n1)" || ergebnis="{}"
      docker rm -f epm-ki-bench >/dev/null 2>&1 || true
      wait "$messer" 2>/dev/null || true
      werte="$(python3 - "$stats" "$ergebnis" "$name" "$laden" <<'PY'
import json, re, sys
stats, ergebnis, name, laden = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
cpu, mem = [], []
einheit = {"KiB": 1 / 1024 / 1024, "MiB": 1 / 1024, "GiB": 1.0}
for z in open(stats):
    m = re.match(r"([\d.]+)%\s+([\d.]+)(KiB|MiB|GiB)", z)
    if m:
        cpu.append(float(m.group(1)))
        mem.append(float(m.group(2)) * einheit[m.group(3)])
try:
    e = json.loads(ergebnis)
except ValueError:
    e = {}
k = e.get("je_kategorie", {})
def w(kat, feld, fmt="{}"):
    v = (k.get(kat) or {}).get(feld)
    return fmt.format(v) if v is not None else "–"
pdf = next((x for x in k if x == "grosses_pdf"), None)
zeile = (f"| {name} | {laden} | {max(mem):.1f} GB | {sum(cpu)/len(cpu):.0f} % | " if mem else f"| {name} | {laden} | – | – | ") + \
    f"{w('tabelle', 'sekunden_je_seite')} | {w('foto', 'sekunden_je_seite')} | {w('grosses_pdf', 'sekunden_je_seite')} | " \
    f"{w('tabelle', 'cer')} | {w('foto', 'cer')} | {w('tabelle', 'laborwerte_f1')} | {w('foto', 'laborwerte_f1')} |"
print(zeile)
print(json.dumps({"variante": name, "laden_s": laden, "ram_max_gb": round(max(mem), 2) if mem else None,
                  "cpu_mittel": round(sum(cpu) / len(cpu), 1) if cpu else None, **e}, ensure_ascii=False))
PY
)"
      echo "$werte" | head -n1 >> "$MD"
      [[ $erstes == 1 ]] || echo "," >> "$JSON"
      echo "$werte" | tail -n1 >> "$JSON"
      erstes=0
      rm -f "$stats"
      echo "   $(echo "$werte" | head -n1)"
      ;;
  esac
done < "$VORRAT/MODELLE.txt"
echo "]" >> "$JSON"
{
  echo
  echo "CER = Zeichenfehlerrate beim Abschreiben (kleiner ist besser). Labor-F1 = Treffer der Laborwerte (1 = alle"
  echo "richtig, nichts erfunden). Eigene Seiten: je Kategorie in der JSON-Datei. Auswahl der Variante und Grenzen:"
  echo "docs/KI-BETRIEB.md, Abschnitt „Modell wählen“."
} >> "$MD"
chown 10001:101 "$JSON" "$MD" 2>/dev/null || true
echo "Fertig: $MD"
