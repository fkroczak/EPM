"""Auswahl der Modelle für Administration › KI › Einrichtung (Wunsch 15.10.2026: Modell in der Oberfläche wählen).

Feste Liste – der Server lädt nie von einer frei eingegebenen Adresse. Dieselben Schlüssel, Repositories und
Quantisierungen stehen im Systemagenten (``rollout/epm-systemagent.py``, ``KI_KATALOG``); ein Test prüft das.

Die Angaben zu Größe, Speicher und Tempo sind **Schätzungen für CPU-Betrieb** (llama.cpp, Kontext 16k, mit
Vision-Projektor). Was auf dem Server tatsächlich passt und wie gut es liest, zeigt der Benchmark.
Andere Modelle: als Paket mit ``werkzeuge/ki.sh vorbereiten … --repo NAME`` vorbereiten und hochladen.
"""

KATALOG = [
    {"schluessel": "qwen3.5-2b-q4", "name": "Qwen3.5-2B Q4_K_M", "repo": "bartowski/Qwen_Qwen3.5-2B-GGUF",
     "quant": "Q4_K_M", "groesse_gb": 1.9, "ki_speicher": "4g", "server_ram_gb": 12, "tempo": "schnell",
     "beschreibung": "Kleinste Variante. Schnell, aber neigt eher zum Zusammenfassen statt Abschreiben – für "
                     "Tests oder sehr knappe Server."},
    {"schluessel": "qwen3.5-2b-q8", "name": "Qwen3.5-2B Q8_0", "repo": "bartowski/Qwen_Qwen3.5-2B-GGUF",
     "quant": "Q8_0", "groesse_gb": 2.8, "ki_speicher": "5g", "server_ram_gb": 12, "tempo": "schnell",
     "beschreibung": "Kleine Variante mit höherer Genauigkeit."},
    {"schluessel": "qwen3.5-4b-q4", "name": "Qwen3.5-4B Q4_K_M", "repo": "bartowski/Qwen_Qwen3.5-4B-GGUF",
     "quant": "Q4_K_M", "groesse_gb": 3.4, "ki_speicher": "6g", "server_ram_gb": 14, "tempo": "mittel",
     "beschreibung": "Empfehlung für 16 GB RAM: guter Kompromiss aus Lesequalität und Tempo."},
    {"schluessel": "qwen3.5-4b-q8", "name": "Qwen3.5-4B Q8_0", "repo": "bartowski/Qwen_Qwen3.5-4B-GGUF",
     "quant": "Q8_0", "groesse_gb": 5.2, "ki_speicher": "8g", "server_ram_gb": 16, "tempo": "mittel",
     "beschreibung": "Genauer als Q4_K_M bei Zahlen und Tabellen, etwas langsamer. Empfehlung ab 24–32 GB RAM."},
    {"schluessel": "qwen3.5-9b-q4", "name": "Qwen3.5-9B Q4_K_M", "repo": "bartowski/Qwen_Qwen3.5-9B-GGUF",
     "quant": "Q4_K_M", "groesse_gb": 6.6, "ki_speicher": "10g", "server_ram_gb": 24, "tempo": "langsam",
     "beschreibung": "Liest laut Praxisberichten am zuverlässigsten, auf der CPU aber etwa doppelt so langsam wie 4B. "
                     "Nur mit 32 GB und wenn der Benchmark den Unterschied zeigt."},
]
NACH_SCHLUESSEL = {k["schluessel"]: k for k in KATALOG}


def mit_hardware(ram_bytes: int | None, kerne: int | None, eingespielt: set[str]) -> list[dict]:
    """Katalog mit „passt“ (RAM reicht), „empfohlen“ (größtes passendes 4B-Modell) und „eingespielt“."""
    ram_gb = (ram_bytes or 0) / 1024 ** 3
    aus = []
    for k in KATALOG:
        passt = bool(ram_bytes) and ram_gb >= k["server_ram_gb"] * 0.95 and (kerne or 0) >= 4
        modell = k["name"].split()[0].lower()  # „qwen3.5-4b“ steht im Dateinamen, ebenso die Quantisierung
        aus.append({**k, "passt": passt, "eingespielt": any(modell in d.lower() and k["quant"].lower() in d.lower()
                                                            for d in eingespielt)})
    vier = [k for k in aus if k["passt"] and "4b" in k["schluessel"]]
    if vier:
        empfehlung = vier[-1]["schluessel"] if ram_gb >= 24 else vier[0]["schluessel"]
        for k in aus:
            k["empfohlen"] = k["schluessel"] == empfehlung
    return aus
