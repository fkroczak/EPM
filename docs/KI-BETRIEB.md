# KI (Experimentell) – Betrieb, Modellwechsel, Fehleranalyse, Rollback

Stand 14.10.2026 · gehört zu [`KI-ERWEITERUNG-PLAN-2026-10-14.md`](KI-ERWEITERUNG-PLAN-2026-10-14.md) (Architektur,
Entscheidungen) und [`KI-API.md`](KI-API.md) (Schnittstellen). Datenschutz: [`DATENSCHUTZ.md`](DATENSCHUTZ.md),
Abschnitt „KI (Experimentell)“.

**Grundsatz:** Die KI läuft vollständig lokal und ohne Internet. Sie liest die Dokumente der Akten nur und schreibt nie
selbst in die Akte. Übernommen wird nur, was ein Mitarbeiter prüft und ausdrücklich bestätigt.

---

## 1. Was läuft wo

| Container | Image | Aufgabe | Netz | Schreibt |
|---|---|---|---|---|
| `ki-modell` | `epm-ki-modell:<Tag>` (llama.cpp `llama-server`, nur CPU) | Qwen3.5 (Bilder + Text); Startskript wählt Modell, prüft SHA-256, schläft tagsüber | `intern` | nichts (read-only, `/tmp` im RAM) |
| `ki-worker` | `epm-backend` (Befehl `ki`) | Nachtverarbeitung, Berichtsentwürfe, Steuerung nach Zeitfenster und Auslastung | `intern` | nur KI-Tabellen (DB-Rolle `epm_ki`) und `data/ki` |
| `ki-init` | `epm-backend` | einmalig je Start: DB-Rolle `epm_ki` anlegen/nachziehen | `intern` | Rechte der Rolle |
| `backend` | wie bisher | API, Prüfansicht, **Übernahme in die Akte** (im Namen des Mitarbeiters) | `intern` | wie bisher |

Dateien auf dem Server (`/srv/epm`):

| Pfad | Inhalt | Sicherung |
|---|---|---|
| `compose.ki.yaml` | Dienste der KI (kommt mit jedem Update) | Code |
| `ki-aktiv` | Marke: KI eingerichtet → `epm-update` lässt die KI-Container laufen | – |
| `ki-modelle/` | GGUF-Modelle, Vision-Projektor, `MODELLE.txt`, `SHA256SUMS.*` (offline eingespielt) | **nicht** in der täglichen Sicherung (groß, reproduzierbar) – das Modell-Paket `epm-ki-modelle-<Datum>.tar` zweimal getrennt aufbewahren |
| `data/ki/modell/` | `aktiv.env/.json` (freigegebenes Modell), `probe.env` (Evaluation), `schlafen` | entsteht neu |
| `data/ki/vorgaenge/` | verschlüsselte Zwischendateien (Seitenbilder bis zur zweiten Lesung) | nein – werden nach Abschluss bzw. nach `aufbewahrung_tage` gelöscht |
| `data/ki/.dienst/stand.json` | Stand des KI-Dienstes für die Oberfläche | – |
| `data/ki/benchmark-*.md/.json` | Ergebnisse des Benchmarks | optional |
| `secrets/ki_db_password`, `secrets/ki_schluessel` | Passwort der DB-Rolle, Schlüssel der Arbeitsablage | wie die übrigen Secrets (Notfallpaket) |
| Datenbank, Tabellen `ki_*` | Vorgänge, Vorschläge, Korrekturen, Übernahmen, Hinweise, Modelle, Einstellungen | **ja**, mit der täglichen Sicherung (pg_dump) |

## 2. Einrichten (neue VM mit 16–32 GB RAM, 4–8 Kernen)

1. **Hardware prüfen:** `sudo epm-ki pruefen` (bzw. `werkzeuge/ki-pruefen.sh`). AVX2 muss „ja“ zeigen – sonst im
   Hypervisor den CPU-Typ auf „host“ stellen. Vorher einen **Snapshot** der VM anlegen.
2. **Modelle vorbereiten** (PC mit Internet, einmalig erlaubt):
   `werkzeuge/ki.sh vorbereiten Q4_K_M Q8_0 --mit-image` → `epm-ki-modelle-<Datum>.tar` (Modelle + Vision-Projektor +
   Prüfsummen + Image `epm-ki-modell`). Standard-Quelle: `bartowski/Qwen_Qwen3.5-4B-GGUF` (andere mit `--repo`, z. B.
   ein 9B-Repository zum Vergleich). **Lizenz** in `README-Modell.md` bzw. auf der Modellkarte des Basismodells prüfen.
3. **Einspielen:** Datei per `scp` auf den Server, dann `sudo epm-ki einspielen ~/epm-ki-modelle-<Datum>.tar`
   (prüft SHA-256, lädt das Image).
4. **Einrichten:** `sudo epm-ki einrichten` – erzeugt Secrets und Ordner, setzt Grenzen nach Hardware in `.env`
   (`KI_SPEICHER`, `KI_THREADS`, `KI_WORKER_SPEICHER`; eigene Werte bleiben), nimmt `compose.ki.yaml` dazu, startet
   die Container und registriert die Modelle (die erste Variante wird aktiv).
5. **Messen:** nachts `sudo epm-ki benchmark` (mit eigenen Seiten: `--eigene`, Dateien nach
   `/srv/epm/data/ki/benchmark/` legen, z. B. `hand_rezept.jpg` + `hand_rezept.txt`). Ergebnis in
   `data/ki/benchmark-<Datum>.md`; danach Modell wählen (Abschnitt 4).
6. **Freigeben:** Administration › KI › Zeitfenster und Grenzen prüfen. Rechte unter Benutzer › Rechte
   (Standard: jeder Mitarbeiter ansehen/prüfen/übernehmen; KI verwalten und Trainingsfreigabe nur Admin).

Auf Servern unter 12 GB RAM / 4 Kernen bleibt der KI-Dienst von selbst aus (Administration › KI zeigt den Grund);
EPM läuft unverändert. `KI_HARDWARE_PRUEFEN=0` in `.env` schaltet die Prüfung ab (nur für Tests).

## 3. Täglicher Betrieb

- **Nachtfenster** (Standard 21:00–07:00, Europe/Berlin): Der Dienst merkt alle 10 Minuten neue Dokumente vor (neue
  zuerst, dann der Altbestand, jüngste zuerst) und verarbeitet sie. Um 07:00 werden laufende Dokumente nach der
  aktuellen Seite zurückgestellt und in der nächsten Nacht dort fortgesetzt.
- **Tagsüber** nur ausdrücklich Angefordertes (Akte › KI › „Dokument jetzt verarbeiten lassen“, „Erneut verarbeiten“,
  Berichtsentwürfe) – einer nach dem anderen. Nach 30 Minuten ohne Arbeit beendet der Modell-Container llama-server
  und gibt den Speicher frei (`KI_MODELL_TAGSUEBER_ENTLADEN=0` schaltet das ab); bei neuer Arbeit lädt er wieder
  (ein bis zwei Minuten).
- **Pausen:** während der Sicherung (Marke `system/status/backup-laeuft`), bei zu wenig freiem RAM, zu hoher CPU oder
  Systemlast (Grenzen in Administration › KI), tagsüber solange Scans warten. Hysterese: weiter erst deutlich unter
  den Grenzen. Knapp darunter arbeitet er „sparsam“ (ein Auftrag, kleinere Bilder, keine zweite Lesung).
- **Prüfen:** Menü „KI (Experimentell)“ → Dokument öffnen → Felder vergleichen, korrigieren, freigeben → „In die
  Akte übernehmen“ (Zusammenfassung, Konfliktentscheidungen, Bestätigung). Abgelehnte Dokumente bleiben unverändert in
  der Akte.
- **Hinweise Labor ↔ Infusionsplan:** Akte › KI. Sie werden nach jeder Verarbeitung und jeder Übernahme neu berechnet.
- **Qualität:** Menü „KI (Experimentell)“ › Qualität.

## 4. Modell wählen und wechseln

Vergleichswerte aus dem Benchmark: Sekunden je Seite (Scan, Foto, großes PDF), Zeichenfehlerrate (CER), Labor-F1,
höchster RAM. Faustregel auf CPU:

| RAM / Kerne | Empfehlung | `KI_SPEICHER` | Worker nachts |
|---|---|---|---|
| 16 GB / 4–6 | Qwen3.5-4B **Q4_K_M** | 6–7g | 1 |
| 32 GB / 8 | Qwen3.5-4B **Q8_0** (genauer), 9B Q4_K_M nur, wenn der Benchmark deutlich bessere Werte zeigt und die Nacht reicht | 10g | 2 |

Wechsel (Administration › KI › Modelle):
1. Neue Variante einspielen (`epm-ki einspielen`) und registrieren (`epm-ki einrichten` registriert alle Varianten
   aus `MODELLE.txt`; oder „Registrieren“ in der Oberfläche).
2. **Evaluationsfälle erzeugen** (Reiter „Evaluation und Training“) – aus geprüften Dokumenten, pseudonymisiert.
3. **Evaluieren** – der Lauf geschieht in der nächsten Nacht: Der KI-Dienst lädt den Kandidaten vorübergehend
   (`probe.env`), strukturiert alle Fälle, schaltet zurück. Ergebnis (Dokumenttyp, Labor-F1, Infusion-F1, s/Fall)
   steht neben dem aktiven Modell.
4. **Aktivieren** mit Passwort und zweitem Faktor. Das bisherige Modell wird „vorherige Version“. Der Modell-Container
   lädt das neue Modell (prüft die SHA-256) innerhalb von ein bis zwei Minuten.

## 5. Rollback

| Was | Wie |
|---|---|
| **Modell** | Administration › KI › Modelle › „Zurückschalten“ bei der vorherigen Version (Passwort + 2FA). Notfalls auf der Konsole: `docker compose exec backend python manage.py epm_ki_modell --liste`, dann `--registrieren <datei> --aktivieren` |
| **KI ganz abschalten** | Administration › KI › „KI-Dienst aktiv“ aus (nimmt nichts Neues an) – oder `sudo epm-ki aus` (Container gestoppt, aus `COMPOSE_FILE` genommen; Daten bleiben). Wieder an: `sudo epm-ki einrichten` |
| **EPM-Version** | wie bisher `sudo epm-update --zurueck TAG`. Die Migrationen `ki/0001`, `befunde/0003` (optionales Feld „Uhrzeit der Entnahme“) und `audit/0014` sind rein additiv; eine ältere Version läuft mit ihnen weiter (die KI-Tabellen bleiben unbenutzt) |
| **Falsch übernommene Werte** | wie jeder Eintrag der Akte: in Labor/Infusionspläne/… korrigieren; der Verlauf zeigt den alten Stand. Die Übernahme steht mit Person, Zeit und Ziel in `KiUebernahme` und im Audit-Log |

## 6. Fehleranalyse

| Anzeichen | Ursache und Abhilfe |
|---|---|
| „Der KI-Dienst meldet sich nicht“ | `docker compose ps ki-worker` · `docker compose logs --tail 100 ki-worker`. Häufig: `ki-init` fehlgeschlagen (Secret fehlt → `sudo epm-ki einrichten`) |
| „KI-Modell nicht bereit“ | `docker compose logs --tail 50 ki-modell`: Prüfsumme falsch (Datei beschädigt → neu einspielen), Datei fehlt, Speichergrenze zu klein (`KI_SPEICHER` erhöhen, `docker compose up -d ki-modell`). Tagsüber normal, wenn das Modell schläft |
| Modus „aus“ mit „Server zu klein“ | unter 12 GB RAM bzw. 4 Kernen (`KI_MIN_RAM_GB`, `KI_MIN_KERNE`) |
| ständig „Pause“ | Grund steht dabei (CPU, RAM, Last, Sicherung, Scans). Grenzen in Administration › KI anpassen oder `KI_THREADS` senken (zwei Kerne frei lassen) |
| Vorgang „Fehler“ | Text am Vorgang; nach drei Versuchen endgültig. „Erneut verarbeiten“. „Dokument wurde geändert“: neue Fassung (z. B. nach „Text erkennen“) → erneut verarbeiten |
| sehr langsam | Benchmark ansehen; `bild_max_px` senken (1280), Q4_K_M statt Q8_0, `KI_THREADS` = Kerne − 2 |
| Stand von der Konsole | `docker compose exec ki-worker python manage.py epm_ki --stand` |
| Einmal von Hand durchlaufen lassen | `docker compose exec ki-worker python manage.py epm_ki --einmal` (ohne Zeitfenster, nacheinander) |
| Audit | Administration › Audit-Log, Filter „KI“: Verarbeitung (Modell, SHA-256, Prompt-Fassung), Korrekturen, Übernahmen, Ablehnungen, Modellwechsel |

## 7. Backup und Wiederherstellung

- Die **Datenbank** (alle KI-Tabellen) ist in der täglichen Sicherung. Eine Wiederherstellung bringt Vorgänge,
  Korrekturen und Hinweise mit; Zwischendateien fehlen danach – betroffene Vorgänge „Erneut verarbeiten“.
- **Modelle** nicht in der täglichen Sicherung: Modell-Paket `epm-ki-modelle-<Datum>.tar` (mit `SHA256SUMS`) zweimal
  getrennt aufbewahren; nach einem Neuaufbau `epm-ki einspielen` + `epm-ki einrichten`.
- **Konfiguration:** `.env` (KI-Grenzen), `secrets/ki_*` und `compose.ki.yaml` liegen auf dem Server. Nach einem
  Neuaufbau erzeugt `epm-ki einrichten` neue Secrets; alte verschlüsselte Zwischendateien sind dann nicht mehr lesbar
  (gewollt – sie sind nur vorübergehend). Die Einstellungen aus Administration › KI stehen in der Datenbank.
- Während der Sicherung pausiert die KI (kein Wettlauf um Platte und CPU).

## 8. Training (optional)

Entscheidung 14.10.2026: optional, nachts ohne GPU, möglichst am Wochenende, wenn niemand angemeldet ist. Umsetzung:

1. Rechtsgrundlage dokumentieren (Administration › KI › Evaluation und Training, Passwort + 2FA) – vorher bleibt
   alles gesperrt.
2. Evaluationsfälle erzeugen, Text sichten, einzelne Fälle für das Training freigeben.
3. Das Training selbst läuft **nicht** im Produktiv-Dienst und überschreibt nie ein Modell. Auf der CPU ist nur ein
   kleines LoRA auf den Textteil realistisch (Stunden bis ein Wochenende für einige hundert Beispiele). Ergebnis ist
   eine neue GGUF-Datei → einspielen, registrieren, evaluieren, aktivieren wie in Abschnitt 4.
   Der Trainingslauf selbst ist noch nicht gebaut (Phase 3, nach den ersten Wochen mit echten Korrekturen –
   ob Training überhaupt nötig ist, zeigt das Qualitäts-Dashboard).
