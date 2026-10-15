#!/usr/bin/env bash
# EPM – KI (Experimentell): Ziel-VM prüfen und Ressourcen planen (Plan Phase 0, Auftrag 2 „Hardware- und VM-Optimierung“).
#
#   sudo werkzeuge/ki-pruefen.sh            # Bericht auf dem Bildschirm
#   sudo werkzeuge/ki-pruefen.sh --json     # nur JSON (für die Doku bzw. zum Vergleichen)
#
# Liest nur (nichts wird geändert): CPU (Kerne, Threads, AVX2/AVX-512), RAM, Swap, GPU, Platten (SSD/HDD, frei),
# Betriebssystem, Virtualisierung, Docker, Netz (kommt der Server ins Internet?), Auslastung, laufende EPM-Container,
# Snapshot-Hinweise. Am Ende eine Empfehlung: Modellgröße, Quantisierung, Speichergrenzen, Threads, Worker.
set -uo pipefail
JSON=0; [[ "${1:-}" == "--json" ]] && JSON=1
B="${EPM_BASIS:-/srv/epm}"

kerne=$(nproc 2>/dev/null || echo 1)
threads=$(grep -c ^processor /proc/cpuinfo 2>/dev/null || echo "$kerne")
cpu_name=$(sed -n 's/^model name\s*:\s*//p' /proc/cpuinfo | head -n1 | tr -d '"\\')
flags=$(grep -m1 ^flags /proc/cpuinfo 2>/dev/null || true)
avx2=0; [[ "$flags" == *" avx2"* ]] && avx2=1
avx512=0; [[ "$flags" == *" avx512f"* ]] && avx512=1
ram_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
frei_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
swap_mb=$(awk '/SwapTotal/ {print int($2/1024)}' /proc/meminfo)
last=$(cut -d' ' -f1-3 /proc/loadavg)
os_name=$(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-unbekannt}")
kernel=$(uname -r)
virt=$(systemd-detect-virt 2>/dev/null || echo "unbekannt")
gpu="keine erkannt"
if command -v nvidia-smi >/dev/null 2>&1; then
  gpu=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -n1)
elif command -v lspci >/dev/null 2>&1 && lspci | grep -Eqi 'vga|3d|display'; then
  gpu=$(lspci | grep -Ei 'vga|3d|display' | head -n1 | cut -d: -f3- | sed 's/^ //' | tr -d '"\\')
fi
cuda=0; command -v nvidia-smi >/dev/null 2>&1 && cuda=1
rocm=0; [[ -e /dev/kfd ]] && rocm=1
ziel="$B"; [[ -d "$ziel" ]] || ziel=/
platte_frei_gb=$(df -BG --output=avail "$ziel" | tail -n1 | tr -dc 0-9)
geraet=$(df --output=source "$ziel" | tail -n1)
rota=$(lsblk -no ROTA "$geraet" 2>/dev/null | head -n1 | tr -d ' ')
plattentyp=$([[ "$rota" == "0" ]] && echo "SSD/NVMe" || ([[ "$rota" == "1" ]] && echo "HDD" || echo "unbekannt"))
docker_v=$(docker version --format '{{.Server.Version}}' 2>/dev/null | head -n1 | tr -cd '0-9A-Za-z.+-')
[[ -n "$docker_v" ]] || docker_v="nicht erreichbar"
compose_v=$(docker compose version --short 2>/dev/null | head -n1 | tr -cd '0-9A-Za-z.+-')
internet="nein"
if timeout 4 bash -c 'exec 3<>/dev/tcp/1.1.1.1/443' 2>/dev/null; then internet="ja (Port 443 nach außen offen)"; fi
container=$(docker ps --format '{{.Names}}' 2>/dev/null | tr '\n' ' ')
snapshot="unbekannt – im Hypervisor prüfen (Proxmox/VMware/Hyper-V: Snapshot vor dem Einrichten anlegen)"
command -v lvs >/dev/null 2>&1 && lvs --noheadings 2>/dev/null | grep -q . && snapshot="LVM vorhanden (lvcreate --snapshot möglich)"

# ---------------------------------------------------------------- Empfehlung
# Faustwerte für CPU-Betrieb mit llama.cpp (vor der Messung mit werkzeuge/ki-benchmark.sh):
#   Qwen3.5-4B  Q4_K_M ≈ 2,7 GB + Vision-Projektor ≈ 0,7 GB + Kontext 16k ≈ 1 GB  → Grenze 6 GB
#   Qwen3.5-4B  Q8_0   ≈ 4,5 GB + 0,7 + 1                                          → Grenze 8 GB
#   Qwen3.5-9B  Q4_K_M ≈ 5,7 GB + 0,9 + 1,5                                        → Grenze 10 GB
# Für EPM selbst (PostgreSQL, Backend, Nginx, OCR-Dienst) bleiben mindestens 5 GB.
modell="keins (Server zu klein)"; quant="-"; ki_speicher="0"; worker_nacht=0
if (( ram_mb >= 28000 && kerne >= 8 )); then
  modell="Qwen3.5-4B (Q8_0), zum Vergleich 9B Q4_K_M"; quant="Q8_0"; ki_speicher="10g"; worker_nacht=2
elif (( ram_mb >= 15000 && kerne >= 6 )); then
  modell="Qwen3.5-4B"; quant="Q4_K_M (Q8_0 im Benchmark vergleichen)"; ki_speicher="7g"; worker_nacht=1
elif (( ram_mb >= 11500 && kerne >= 4 )); then
  modell="Qwen3.5-4B"; quant="Q4_K_M"; ki_speicher="6g"; worker_nacht=1
fi
ki_threads=$(( kerne > 3 ? kerne - 2 : 1 ))   # zwei Kerne bleiben für EPM und Datenbank
worker_speicher=$(( ram_mb >= 15000 ? 3 : 2 ))

if (( JSON )); then
  cat <<EOF
{"cpu": {"name": "$cpu_name", "kerne": $kerne, "threads": $threads, "avx2": $avx2, "avx512": $avx512},
 "ram_mb": $ram_mb, "ram_frei_mb": $frei_mb, "swap_mb": $swap_mb, "last": "$last",
 "gpu": "$gpu", "cuda": $cuda, "rocm": $rocm,
 "platte": {"frei_gb": ${platte_frei_gb:-0}, "typ": "$plattentyp", "pfad": "$ziel"},
 "os": "$os_name", "kernel": "$kernel", "virtualisierung": "$virt",
 "docker": "$docker_v", "compose": "$compose_v", "internet": "$internet", "container": "$container",
 "empfehlung": {"modell": "$modell", "quantisierung": "$quant", "KI_SPEICHER": "$ki_speicher",
                "KI_THREADS": $ki_threads, "KI_WORKER_SPEICHER": "${worker_speicher}g", "worker_nacht": $worker_nacht}}
EOF
  exit 0
fi

cat <<EOF
EPM – Prüfung der Ziel-VM für „KI (Experimentell)“   $(date '+%d.%m.%Y %H:%M')
-------------------------------------------------------------------------------
CPU            $cpu_name
               $kerne Kerne / $threads Threads · AVX2: $([[ $avx2 == 1 ]] && echo ja || echo NEIN) · AVX-512: $([[ $avx512 == 1 ]] && echo ja || echo nein)
RAM            $ram_mb MB gesamt, $frei_mb MB frei · Swap $swap_mb MB
GPU            $gpu  (CUDA: $([[ $cuda == 1 ]] && echo ja || echo nein), ROCm: $([[ $rocm == 1 ]] && echo ja || echo nein))
Platte         ${platte_frei_gb:-?} GB frei unter $ziel ($plattentyp)
System         $os_name · Kernel $kernel · Virtualisierung: $virt
Docker         $docker_v (Compose $compose_v)
Netz           ins Internet: $internet
Auslastung     Last (1/5/15 min): $last
Container      ${container:-keine}
Snapshot       $snapshot

Empfehlung (vor der Messung – bitte mit werkzeuge/ki-benchmark.sh bestätigen)
-------------------------------------------------------------------------------
Modell         $modell
Quantisierung  $quant
.env           KI_SPEICHER=$ki_speicher  KI_THREADS=$ki_threads  KI_WORKER_SPEICHER=${worker_speicher}g
Administration › KI: parallele Aufträge nachts $worker_nacht, tagsüber 0 (nur auf Anforderung)
EOF
(( avx2 == 0 )) && echo "WARNUNG: ohne AVX2 ist llama.cpp auf der CPU sehr langsam – CPU-Typ der VM im Hypervisor auf „host“ stellen."
(( ram_mb < 11500 )) && echo "HINWEIS: unter 12 GB RAM bleibt der KI-Dienst aus (EPM läuft unverändert weiter)."
(( ${platte_frei_gb:-0} < 20 )) && echo "WARNUNG: unter 20 GB frei – Modelle (4–8 GB je Variante) und Sicherungen brauchen Platz."
[[ "$plattentyp" == "HDD" ]] && echo "HINWEIS: HDD – das Laden des Modells dauert länger (mmap); SSD empfohlen."
[[ "$internet" == ja* ]] && echo "HINWEIS: Der Server erreicht das Internet. Die KI-Container hängen trotzdem nur am Netz „intern“ ohne Weg nach außen."
exit 0
