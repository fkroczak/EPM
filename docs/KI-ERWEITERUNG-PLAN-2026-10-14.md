# KI (Experimentell) – Verständnis, Annahmen, offene Fragen, Architektur, Plan

Stand 14.10.2026 · Code-Stand `3e69983` · **Nur Planung, noch kein Code.** Die Umsetzung beginnt erst nach Freigabe.

Grundregel für alles Folgende: **Die KI schreibt nie selbst in die Akte.** Sie schlägt vor, ein berechtigter Mitarbeiter
prüft, korrigiert und übernimmt. Ausschließlich lokale Modelle, kein Netz nach außen, keine Telemetrie.

---

## 1. Verständnis des Auftrags

Eine lokale KI-Erweiterung, die nachts (Standard 21:00–07:00, Europe/Berlin) Unterlagen aus einer Eingangsqueue
liest, Text erkennt (auch alte, schlechte, handschriftliche und tabellarische Vorlagen), den Dokumenttyp bestimmt,
Metadaten, Laborwerte, Infusionspläne und Freitext-Inhalte strukturiert und alles in eine **Prüf-Queue** im neuen
Bereich **„KI (Experimentell)“** legt. Darauf bauen auf:

- eine **regelbasierte** Verknüpfung Labor ↔ Infusionsplan mit Hinweisen („Kalium niedrig, anschließend
  Kaliumsubstitution dokumentiert“) – ausdrücklich ohne Bewertung, Diagnose oder Empfehlung,
- Berichtsentwürfe **nur auf Anforderung**, nur aus freigegebenen Akteninhalten, mit Quellenangaben,
- ein Qualitätskreislauf aus Mitarbeiterkorrekturen (Dashboard, Evaluationsdaten, kontrollierter Modellwechsel mit
  Rollback; Fine-Tuning nur getrennt, pseudonymisiert und mit dokumentierter Rechtsgrundlage),
- Ressourcenschutz: Das EPM selbst, die Datenbank und die Sicherung haben immer Vorrang.

## 2. Was das bestehende EPM schon mitbringt (Analyse)

| Bereich | Bestand | Folge für die KI-Erweiterung |
|---|---|---|
| Stack | Django 5.2 + DRF, PostgreSQL 18, React/Vite, Docker Compose, Netz `intern` ohne Weg nach außen | Neue Dienste kommen ins Netz `intern`; nichts davon hängt an `extern` |
| Texterkennung | Dienst `ocr` (`manage.py epm_ocr`): Tesseract (deu, tessdata_best) + PP-OCRv5 per onnxruntime, Bildaufbereitung (Entzerren, UVDoc, Binarisierung), Wort-Abgleich beider Lesarten, Sparmodus, Absturzschutz mit Lebenszeichen | Bleibt die **erste Stufe**. Das Vision-LLM liest zusätzlich dort, wo die klassische Erkennung unsicher ist (Handschrift, Tabellen, schlechte Kopien) und für die strukturierte Extraktion |
| Auswertung | `scans/ocr/auswertung.py`: regelbasiert (Laborkatalog, Synonyme, Einheiten-Umrechnung `einheiten.py`, ICD-Diagnosen, Dokumentdatum, Patientenhinweise); Klassifikation nur labor / bia / arztbrief | Wird als Prüfinstanz weiterverwendet: LLM-Werte werden gegen Katalog, Einheiten und Plausibilität geprüft; Abweichung LLM ↔ Regeln = „unsicher“ |
| Prüfen und Zuordnen | Scans-Workflow (`scans/api.py:zuordnen`), Patientenvorschlag ohne automatische Zuordnung, „Gelernt“/„Verbessern“ (nur Bezeichnungen, keine Patientendaten) | Übernahme in die Akte nutzt **dieselben Serializer** (`LaborbefundSerializer` usw.) – gleiche Validierung, gleiche Historie |
| Labor | `befunde.Laborbefund` (`abgenommen_am` ist **nur ein Datum**), `Laborwert` (Wert, Einheit, Referenz), Katalog `stammdaten.Laborparameter` | Uhrzeit fehlt → Verknüpfung „06:10 vs. 08:00“ heute nicht abbildbar (siehe Frage F4) |
| Infusionspläne | `infusionen.Infusionsplan` mit Versionen (`vorgaenger`, `gueltig_ab`, Status entwurf/aktuell/abgeloest), Elektrolyte als Felder (`kalium_mmol`, `natrium_mmol`, …), Positionen, Freigabe mit `plaene_freigeben`, `herkunft` EPM/Altsystem | Dosisänderungen lassen sich direkt aus der Versionskette ableiten – gute Grundlage für die Verknüpfung |
| Medikation, Berichte | `patienten.Medikament` (BMP-artig), `berichte.Bericht` mit Status und Freigabe (`berichte_freigeben`) | KI-Berichtsentwürfe werden als Entwurf angelegt, Freigabe über den vorhandenen Weg |
| Rechte | `accounts/rechte.py` (`RECHTE`, `STANDARD`, `Gruppenrecht`), `hat_recht()`, DRF-Klassen `recht()`/`nur_recht()`, 2FA/Passkeys, Firmen (DSKM, Regeneration Clinic) | Neue Rechte `ki_*` im selben System, je Firma |
| Audit | `audit.protokolliere()`, `SystemEreignis` nur anfügbar (DB-Trigger), django-simple-history | Neue Ereignisarten `KI_*`; Korrekturen zusätzlich versioniert |
| Last und Betrieb | Systemagent schreibt CPU/RAM/Last minütlich nach `system/status/system.json`; Aufträge an den Host als Dateien; Selbstheilung; Sicherung täglich 02:00 (gpg) | Ressourcensteuerung liest diese Messwerte; KI pausiert während der Sicherung |
| Verschlüsselung | Dokumente und Scans liegen **unverschlüsselt** (nur Rechte 0640), nur Sicherungen sind verschlüsselt | KI-Zwischendateien werden neu verschlüsselt abgelegt (siehe 5.6) |
| Hintergrundjobs | kein Celery; Polling-Schleife im Container | Gleiches Muster für den KI-Worker – keine neue Infrastruktur (kein Redis) nötig |
| Tests | Django-Testrunner gegen PostgreSQL, `epm/pruefhilfen.py`, Playwright gegen den echten Stack, CI `.github/workflows/backend.yml` | Neue Tests im selben Stil |

## 3. Technische Annahmen

1. **Ziel-Hardware ohne GPU.** Laut Doku: Test-VM 4 GB RAM / 2 Kerne, VPS „1000 G12“ 8 GB / 4 Kerne, Notfallplan
   mind. 4 Kerne / 8 GB. Diese Arbeitsumgebung (4 vCPU, 15 GB, keine GPU) ist **nicht** die Ziel-VM; Messungen müssen
   auf der Ziel-VM laufen (Phase 0 liefert dafür ein Skript).
2. **Modelle werden offline eingespielt** – wie heute die OCR-Modelle: auf einem PC mit Internet vorbereiten, als
   Datei mit SHA-256 auf den Server, in EPM „KI-Modelle einspielen“. Zur Laufzeit lädt nichts nach.
3. **Laufzeitumgebung `llama.cpp` (`llama-server`)** mit GGUF-Gewichten + Vision-Projektor (`mmproj`): läuft auf CPU
   (AVX2/AVX-512), optional CUDA/Vulkan, keine Telemetrie, Version fest im Image. vLLM nur bei GPU sinnvoll; Ollama
   ginge, bringt aber nichts zusätzlich.
4. **Qwen 3.5 als ein multimodales Modell für Vision und Text.** Die kleinen Qwen-3.5-Varianten sind von Haus aus
   multimodal; ein Modell kann OCR/Extraktion und Text/Berichte übernehmen → auf kleinen VMs nur **ein** Modell im
   Speicher. Ein getrennter Text-Dienst ist vorgesehen, wird aber nur bei ausreichender Hardware zusätzlich gestartet.
   Exakte Bezeichnung, Lizenz und GGUF-Verfügbarkeit („Qwen 3.5-OCR“) prüfe ich vor Phase 1 (Frage F2).
5. **Grobe Erwartung auf CPU (vor Messung, nur Größenordnung):** 2B-Modell Q4 ≈ 1,5–2 GB RAM, mehrere Minuten je
   Seite bei 4 Kernen; 4B Q4 ≈ 3–3,5 GB, etwa doppelt so langsam; 9B auf 8 GB ohne GPU nicht sinnvoll. Auf dem 8-GB-VPS
   bleibt neben Datenbank, Backend und OCR-Dienst Platz für **ein 2B-Modell, knapp für 4B**. Auf der 4-GB-Test-VM ist
   ein Vision-LLM **nicht** betreibbar.
6. **Folgerung:** Das LLM liest nicht jede Seite vollständig, sondern gezielt: Seiten/Bereiche mit niedriger
   OCR-Konfidenz, Tabellen, Handschrift sowie die strukturierte Extraktion auf Basis von Bild + OCR-Text. Damit bleibt
   der Nachtdurchsatz auch auf CPU brauchbar.
7. Verknüpfung Labor/Infusion und Hinweise sind **deterministische Regeln**, kein LLM – nachvollziehbar und testbar.
8. Volltextsuche zunächst mit PostgreSQL (deutsche Textsuche); semantischer Vektorindex (pgvector + lokales
   Embedding-Modell) erst in Phase 3 – braucht ein Postgres-Image mit pgvector statt `postgres:18-alpine`.
9. Fine-Tuning ist auf den CPU-VMs nicht machbar. Der Verbesserungskreislauf beginnt mit Evaluationsdaten,
   Prompt-/Regelversionen und dem vorhandenen „Gelernt“; LoRA-Training nur in einer getrennten Umgebung mit GPU.

## 4. Offene Fragen

| Nr | Frage | Warum wichtig | Mein Vorschlag |
|---|---|---|---|
| F1 | **Auf welcher VM soll die KI laufen** (Test-VM, VPS, eigene KI-VM)? Gibt es eine GPU oder kann aufgerüstet werden (z. B. 16–32 GB RAM, 8 Kerne, oder GPU mit ≥ 12 GB VRAM)? | Entscheidet Modellgröße und Durchsatz; 4 GB reichen nicht | Eigene KI-VM im selben internen Netz (8 Kerne, 32 GB) oder GPU; Minimum VPS 8 GB mit 2B-Modell |
| F2 | Welches Modell genau ist mit „Qwen 3.5-OCR“ gemeint? Ist der einmalige Download der Gewichte auf einem PC mit Internet erlaubt (Offline-Einspielen wie bei PP-OCR)? | Lizenz, Verfügbarkeit, Einspielweg | Qwen-3.5-Varianten 2B/4B (ggf. 9B mit GPU), GGUF Q4_K_M und Q8_0 vergleichen |
| F3 | Wie viele Seiten liegen als Altbestand an, wie viele kommen je Nacht neu? | Durchsatzplanung, Dauer des Altbestands | – |
| F4 | Darf `Laborbefund` eine **Uhrzeit der Entnahme** bekommen (Migration, optional)? | Sonst nur Verknüpfung auf Tagesebene, Zeitfenster 0–48 h nur grob | Ja, optionales Feld `abgenommen_um` |
| F5 | Welche Quellen gehören in die Nacht-Queue: (a) neuer Ablageordner, (b) vorhandene Dokumente der Akte ohne strukturierte Daten (z. B. Altsystem), (c) Import-Ordner `PatData`, (d) Scans? | Umfang, Rechte, Doppelerfassung | (a)+(b), (c) auf Wunsch; Scans bleiben im bestehenden Ablauf |
| F6 | Soll „KI (Experimentell)“ ein **eigener Menüpunkt** (Queue aller Patienten) **und** ein Reiter in der Akte sein? | Oberfläche | Beides: Menüpunkt für die Queue, Reiter in der Akte für Dokumente/Hinweise dieses Patienten |
| F7 | Wer darf prüfen, wer übernehmen? (Rollen mitarbeiter_plus / mediziner?) Gilt das für beide Firmen? | Rechtekonzept | Prüfen: mitarbeiter_plus + mediziner; Übernehmen Labor: mitarbeiter_plus + mediziner; Infusionspläne/Berichte: nur mediziner |
| F8 | Historische Infusionspläne: als `Infusionsplan` mit `herkunft=Altsystem`, Status „abgelöst“ in die Akte übernehmen, oder nur als Datengrundlage für Hinweise im KI-Bereich halten? | Akte bleibt sauber | Übernahme nur nach Freigabe als abgeschlossener Altsystem-Plan |
| F9 | Ist Fine-Tuning in diesem Projekt überhaupt gewollt? Wer ist Datenschutzbeauftragte(r), welche Rechtsgrundlage (z. B. Art. 9 Abs. 2 lit. h / § 22 BDSG, Qualitätssicherung)? Gibt es eine getrennte Trainingsumgebung? | Rechtsgrundlage, DSFA | Phase 1–2 ohne Training, nur Evaluation; Training erst nach DSFA |
| F10 | Welche Berichtarten zuerst (Verlaufsbericht, Laborzusammenfassung, Medikations-/Infusionsübersicht)? Entwurf im Reiter „Berichte“ ablegen? | Umfang Phase 2 | Laborzusammenfassung und Infusionsübersicht zuerst; Ablage als `Bericht` im Status Entwurf, Kennzeichnung KI |
| F11 | Die Sicherung läuft um 02:00 mitten im Nachtfenster. Darf die KI währenddessen pausieren? | Ressourcen, Konsistenz | Ja, automatisch |
| F12 | Pflegeberichte: gibt es dafür einen eigenen Dokumenttyp/Aktenbereich, oder Ablage als Dokument mit Typ „Pflegebericht“? | Zuordnung | Dokumenttyp in der Auswahlliste ergänzen |
| F13 | Verschlüsselung at rest der vorhandenen Dokumente ist heute nicht vorhanden – Teil dieses Auftrags oder separat (z. B. LUKS auf `/srv`)? | Aufwand, Betrieb | KI-Zwischendaten verschlüsselt (hier), Dokumente generell separat per LUKS |

## 5. Geplante Architektur

### 5.1 Komponenten

```
                         intern (Docker-Netz, internal: true – kein Weg nach außen)
┌──────────┐   HTTPS   ┌─────────┐      ┌──────────────────────────────────────────────┐
│ Browser  │──────────▶│ web     │─────▶│ backend (Django)                              │
│ (EPM-UI) │           │ (Nginx) │      │  + App ki: API, Prüf-Queue, Übernahme, Audit  │
└──────────┘           └─────────┘      └──────────────┬───────────────────────────────┘
                                                       │ PostgreSQL (Schema ki_*, Rolle epm)
                                ┌──────────────────────┼──────────────────────────┐
                                ▼                      ▼                          ▼
                        ┌──────────────┐      ┌────────────────┐        ┌──────────────────┐
                        │ db (Postgres)│◀─────│ ki-worker       │──────▶│ ki-modell         │
                        │ ki_* Tabellen│      │ Scheduler, Queue│ HTTP  │ llama-server      │
                        │ (DB-Rolle    │      │ Ressourcensteu- │ :8080 │ Qwen 3.5 (Vision  │
                        │  epm_ki)     │      │ erung, Pipeline │       │ + Text), nur      │
                        └──────────────┘      └───────┬────────┘        │ 127.0.0.1/intern  │
                                                      │                 └──────────────────┘
                              nutzt Bibliothek scans/ocr (Tesseract, PP-OCR) im selben Image
                                                      │
                     data/ki-eingang (Ablage, nur lesen) · data/ki-arbeit (verschlüsselt) · tmpfs
                     system/status/system.json (Lastwerte des Systemagenten, nur lesen)
```

- **ki-modell** (neuer Container, eigenes kleines Image mit `llama-server`, fest gepinnt): OCR-/Vision- und
  Text-Dienst. Lauscht nur im Netz `intern`, kein Port nach außen, `read_only`, `cap_drop: ALL`, `mem_limit`,
  Modelldateien schreibgeschützt eingebunden. Optional ein zweiter Container `ki-text` mit einem reinen Textmodell,
  wenn die Hardware es hergibt (Compose-Profil).
- **ki-worker** (gleiches Image wie Backend, Befehl `ki`): Scheduler (Zeitfenster), Queue, Pipeline, Ressourcen-
  steuerung. Schreibt **nur** in `ki_*`-Tabellen.
- **backend / App `ki`**: REST-API, Prüf- und Freigabeoberfläche, Übernahme in die Akte (nur hier, nur durch
  Benutzer), Berichtsentwürfe auf Anforderung, Dashboard, Admin-Konfiguration.
- **Index**: Phase 1 PostgreSQL-Volltext in `ki_*`; Phase 3 pgvector + lokales Embedding-Modell im `ki-modell`.
- Alles als **Compose-Profil `ki`**: ohne Freischaltung läuft EPM unverändert.

### 5.2 Datenfluss (Nacht)

1. **Eingang**: neue Datei in `data/ki-eingang/` oder Dokument der Akte wird vorgemerkt → `KiVorgang(status=neu)`
   mit SHA-256 (Duplikaterkennung). Original wird **nie verändert**; Arbeitskopie verschlüsselt in `data/ki-arbeit/`.
2. **OCR Stufe 1**: vorhandene Pipeline (`scans/ocr`): Aufbereitung, Tesseract + PP-OCR, Konfidenz je Wort/Zeile.
3. **OCR Stufe 2 (Vision-LLM)**: Seiten/Bereiche mit niedriger Konfidenz, Tabellen, Handschrift → Qwen liest Bild
   (in Kacheln bei großen Seiten), Ergebnis als JSON mit Bounding Boxes. Abgleich mit Stufe 1; Abweichungen markiert.
4. **Klassifikation + Metadaten**: Dokumenttyp (Laborbefund, Arztbericht/Entlassbericht, Verlauf, Infusionsplan,
   Medikationsplan, Pflegebericht, sonstiges), Dokument-/Erstellungsdatum, Fall-/Aufenthaltsbezug, Quelle, Sprache,
   Seitenzahl, Vertraulichkeit, Konfidenz. Patient nur als **Vorschlag** (vorhandene `patient_vorschlaege`).
5. **Extraktion je Typ** mit festem JSON-Schema (Grammatik-gebundene Ausgabe in llama.cpp, damit nur gültiges JSON
   entsteht): Laborwerte (Parameter → Katalog, Wert, Einheit, Referenz, Entnahmezeit, Auffälligkeit; Trend gegen
   Akte und KI-Bestand berechnet **Code**, nicht das LLM), Infusionspläne (Substanz, Dosis, Zeitraum, Applikation,
   Kontext), Freitext (Zusammenfassung, Diagnosen, Medikation, Verlauf, offene Punkte, Aktenabschnitt).
6. **Prüfung durch Regeln**: Katalog, Einheiten (`einheiten.py`), Plausibilitätsgrenzen, Datum im gültigen Bereich,
   Zahl im OCR-Text belegbar. Jedes Feld bekommt Konfidenz + Begründung („im Bild belegt“, „nur LLM“, „Widerspruch“).
7. **Verknüpfung + Hinweise** (Phase 2): Regelwerk, siehe 5.4.
8. **Prüf-Queue**: Status „Zur Prüfung vorgelegt“. Ende der Nachtarbeit um 07:00: laufende Seite wird sauber
   beendet und zurückgestellt.

### 5.3 Datenmodell (App `ki`, neue Tabellen – bestehende Tabellen bleiben unverändert, außer F4)

Getrennte Ebenen wie gefordert: **Original** (Datei/Dokument, unverändert) · **KI-Rohdaten** · **Korrektur** ·
**übernommene Akteninhalte** (bestehende Tabellen, mit Rückverweis).

| Modell | Inhalt |
|---|---|
| `KiVorgang` | ein Dokument in der Pipeline: Quelle (Ablage/Dokument), SHA-256, Firma, Patientvorschlag, Status (10 Werte aus dem Auftrag), Fehler, Versuche, Lebenszeichen, Modellversion, Dauer |
| `KiSeite` | Seite: OCR-Text Stufe 1/2, Konfidenz, Boxen, Sparstufe |
| `KiRohergebnis` | unveränderliches JSON der Modellantwort + Prompt-Version + Modellversion + Parameter (nur anfügen) |
| `KiFeld` | ein extrahiertes Feld (Metadatum, Laborwert, Infusionsposition, Freitextabschnitt): Wert, Einheit, Box, Konfidenz, Begründung, Status (offen/korrigiert/freigegeben/verworfen), Konflikt-Entscheidung (neu / ergänzen / ersetzen / verwerfen) |
| `KiKorrektur` | jede Änderung an einem Feld versioniert: alt, neu, Fehlerart, Benutzer, Zeitpunkt (nur anfügen) |
| `KiUebernahme` | Übernahme-Vorgang: welche Felder, wohin (Modell + ID des Akteneintrags), Konfliktentscheidungen, Benutzer, Zeit |
| `KiHinweis` | Verknüpfungshinweis: Art, Text, Stufe (gesichert/wahrscheinlich), Belege (Laborwert-IDs, Plan-IDs), Status (neu/gesehen/ausgeblendet) |
| `KiBerichtEntwurf` | Auftrag + Entwurf + Quellenliste + Modellversion; Freigabe über bestehenden `Bericht` |
| `KiModellversion` | Registry: Name, Datei, SHA-256, Quantisierung, Rolle (vision/text/embedding), Status (eingespielt/in Evaluation/aktiv/vorherig/gesperrt), Evaluationsergebnis, Freigabe durch Admin |
| `KiEvaluationsfall` / `KiEvaluationslauf` | Evaluationsdatensatz (pseudonymisiert) und Läufe je Modellversion |
| `KiTrainingsfreigabe` | Freigabe eines Beispiels für Training: Pseudonymisierungsstand, Rechtsgrundlage, Freigebender |
| `KiEinstellung` (Singleton) | Zeitfenster, Zeitzone, Worker-Zahl Tag/Nacht, Lastgrenzen, Zeitfenster Verknüpfung (0–48 h), Konfidenzschwellen, Aufbewahrung Zwischendaten |

### 5.4 Labor ↔ Infusionsplan (Regelwerk, kein LLM)

- Zuordnungstabelle Laborparameter ↔ Planfeld/Präparat (Kalium ↔ `kalium_mmol`, KCl; Natrium ↔ `natrium_mmol`;
  Phosphat, Calcium, Magnesium, Albumin, Glucose …), in der Admin-Konfiguration pflegbar.
- Für jeden auffälligen Wert (außerhalb Referenz) im Zeitfenster [t, t + 48 h] (konfigurierbar) die nächste
  Planversion/Position mit passender Substanz suchen; Dosisänderung = Vergleich mit `vorgaenger`.
- Folgewert (Wiederholungsmessung) nach der Maßnahme suchen → „normalisiert“ / „weiterhin auffällig“ / „kein
  Folgewert“.
- **Gesichert**: beide Seiten sind freigegebene Akteninhalte desselben Patienten, Zeitpunkte bekannt, Dosis
  nachweislich erhöht bzw. neu. **Wahrscheinlich**: mindestens eine Seite nur KI-Vorschlag, nur Tagesdatum, oder
  Substanz vorhanden aber Dosis unverändert.
- Textbausteine nur beschreibend: „Kalium niedrig (3,1 mmol/l, 12.03.), anschließend Kaliumsubstitution
  dokumentiert (Plan ab 12.03.).“ · „Kalium nach Substitution im Referenzbereich.“ · „Kalium weiterhin niedrig, keine
  nachfolgende Substitution im erfassten Zeitraum erkannt.“ Jede Meldung trägt den festen Zusatz „Entscheidungshilfe,
  keine medizinische Bewertung“ und Links zu den Belegen.

### 5.5 Rechte

Neue Rechte in `accounts/rechte.py` (Standard je Rolle, je Firma, über `Gruppenrecht` änderbar):

| Recht | Bedeutung | Standard |
|---|---|---|
| `ki_ansehen` | Bereich und Hinweise sehen | mitarbeiter, mitarbeiter_plus, mediziner |
| `ki_pruefen` | Felder korrigieren, ablehnen, Nachverarbeitung anstoßen | mitarbeiter_plus, mediziner |
| `ki_uebernehmen` | freigegebene Daten in die Akte übernehmen (zusätzlich gilt das jeweilige Akten-Recht, z. B. `eintraege_erfassen`; Infusionspläne zusätzlich `plaene_anlegen`) | mitarbeiter_plus, mediziner |
| `ki_berichte` | Berichtsentwurf anfordern | mediziner |
| `ki_verwalten` | Zeitfenster, Limits, Modelle einspielen/evaluieren | admin (Modellaktivierung mit Passwort + 2. Faktor) |
| `ki_training_freigeben` | Beispiele für Training freigeben | eigene Zuweisung (Datenschutz), nie automatisch |

Übungszugänge (`ist_test`) lernen nie mit, wie heute bei „Gelernt“.

### 5.6 Sicherheit und Datenschutz

- **Kein Netz**: Container nur im Netz `intern`; `llama-server` ohne Download-Funktion aufgerufen (nur lokale
  Datei), Offline-Schalter wie in `paddle.offline_erzwingen()`; Test, der während der Pipeline `socket.connect`
  verbietet (wie `OfflineTest`). Nginx leitet nichts an `ki-modell` weiter.
- **Technische Schreibsperre**: Der ki-worker verbindet sich mit einer eigenen DB-Rolle `epm_ki`, die nur auf
  `ki_*` schreiben und Stammdaten/Akte lesen darf. Selbst ein Fehler im Worker kann nichts in die Akte schreiben.
  Die Übernahme läuft ausschließlich im Backend, im Namen eines angemeldeten Benutzers mit Recht.
- **Zwischendateien verschlüsselt**: Arbeitskopien und Seitenbilder in `data/ki-arbeit/` mit AES-256-GCM
  (Bibliothek `cryptography`), Schlüssel als Docker-Secret; Entschlüsselung nur im Speicher/tmpfs. Automatische
  Löschung nach Übernahme bzw. nach konfigurierbarer Frist (Standard 14 Tage), Löschung im Audit-Log.
- **Keine Löschung/Überschreibung** von Originalen; Konflikte immer mit expliziter Entscheidung; „Ersetzen“ nutzt die
  Historie (simple-history), der alte Stand bleibt nachvollziehbar.
- **Audit**: neue Arten `KI_VORGANG`, `KI_GEPRUEFT`, `KI_KORREKTUR`, `KI_UEBERNAHME`, `KI_ABGELEHNT`, `KI_BERICHT`,
  `KI_MODELL` (Einspielen, Evaluation, Aktivierung, Rollback), `KI_EINSTELLUNG`; jede KI-Verarbeitung mit
  Modellname, Version, SHA-256, Prompt-Version.
- **Kennzeichnung**: alles aus der KI trägt sichtbar „KI (Experimentell)“; übernommene Einträge behalten einen
  Herkunftsverweis (`KiUebernahme`).
- **Datenschutz-Doku**: Ergänzung von `docs/DATENSCHUTZ.md` (Verarbeitungsverzeichnis, DSFA-Vorlage,
  Rechtsgrundlagen-Prüfung für Training, Löschfristen).

### 5.7 Ressourcensteuerung

| Modus | Wann | Verhalten |
|---|---|---|
| **Nacht** | im Zeitfenster (Standard 21–07) | bis `KI_WORKER_NACHT` (Standard 1 auf 4 Kerne, 2 ab 8 Kerne) parallele Seiten, volle Threads |
| **Tag** | außerhalb | nur auf Anforderung (Knopf „jetzt verarbeiten“, Berichtsentwurf), 1 Auftrag, wenige Threads, niedrigste Priorität; Modell optional entladen, um RAM freizugeben |
| **Pause** | Sicherung läuft, Update läuft, Wartung, Last zu hoch | keine neuen Seiten; laufende Seite wird beendet bzw. zurückgestellt |

- **Lastquellen**: `system/status/system.json` (Systemagent, Host-CPU/RAM/Last), cgroup-Werte des eigenen
  Containers, Antwortzeit der Datenbank, Länge der OCR-Queue (Scans der Mitarbeiter haben Vorrang).
- **Grenzen** (Umgebungsvariablen als Vorgabe, Admin-Oberfläche überschreibt): `KI_MAX_CPU_PROZENT` (Standard 75),
  `KI_MIN_RAM_FREI_MB` (Standard 1024), `KI_MAX_LAST_JE_KERN`, `KI_SPEICHER` (`mem_limit` von ki-modell),
  `KI_THREADS`. Hysterese, damit nicht ständig umgeschaltet wird.
- **Abstufung**: zu hohe Last → Batch/Kachelgröße verkleinern → Worker reduzieren → Pause; anhaltend knapp → auf
  „nur klassische OCR“ zurückfallen (wie heute der Sparmodus) und Vorgang markieren „Zur Nachverarbeitung“.
- **Schutz durch Container**: `mem_limit` ohne Swap (wie OCR-Dienst), `cpu_shares` niedrig, `nice`; Postgres und
  Backend bekommen Vorrang. Modell lädt beim Nachtstart (Systemagent-Auftrag „ki-modell starten“), entlädt morgens.

### 5.8 Oberfläche „KI (Experimentell)“

- **Menüpunkt** (Queue über alle berechtigten Patienten): Liste mit Filtern (Patient, Datum, Typ, Status,
  OCR-Konfidenz, Fehler), Zähler je Status.
- **Prüfansicht** zweigeteilt: links Original (vorhandene `PdfAnsicht`/Seitenansicht mit Hervorhebung der Box),
  rechts OCR-Text und strukturierte Felder. Farben/Marker: **neu**, **würde ändern**, **würde überschreiben**,
  **unsicher**, **niedrige Konfidenz**. Feldweise bearbeiten, freigeben, verwerfen; Gesamtfreigabe; Ablehnen mit
  Grund. Vor der Übernahme eine **Zusammenfassung mit Bestätigung** (aktive Bestätigung, kein Automatismus); bei
  Konflikt Pflichtwahl neu / ergänzen / ersetzen / verwerfen.
- **Reiter in der Akte** „KI (Experimentell)“: Vorgänge und Hinweise dieses Patienten, Berichtsentwurf anfordern.
- **Administration › KI**: Zeitfenster, Limits, Modelle (einspielen, evaluieren, aktivieren, zurückschalten),
  Status der Dienste, Qualitäts-Dashboard.

### 5.9 Modellwechsel, Evaluation, Rollback

Modell einspielen (Datei + SHA-256) → Status „eingespielt“ → Evaluationslauf gegen den Evaluationsdatensatz
(OCR-Zeichenfehlerrate, Typgenauigkeit, Laborwert-F1, Infusionsfelder, Dauer, RAM) → Vergleich mit aktiver Version
→ Admin aktiviert mit Passwort + 2. Faktor → vorherige Version bleibt als „vorherig“ liegen → Rollback per Knopf
(nur Umschalten, kein Löschen). Produktivmodelle werden nie überschrieben; Training ausschließlich außerhalb.

## 6. Implementierungsplan (schrittweise, jede Phase einzeln freizugeben)

### Phase 0 – Vorbereitung und Messung (vor jeder Funktion)
- Hardware-Prüfskript `werkzeuge/ki-pruefen.sh`: CPU (Kerne, AVX2/AVX-512), RAM, GPU/VRAM/CUDA/ROCm, Platte (Typ,
  frei), OS, Docker, Netz (bestätigt: kein Weg nach außen), aktuelle Last, Snapshot-Möglichkeit → JSON + Empfehlung.
- Benchmark-Skript `werkzeuge/ki-benchmark.py`: Modellgrößen × Quantisierung (Q4_K_M, Q8_0) auf einem Satz
  synthetischer und (lokal, nicht im Repo) echter Seiten: Zeichenfehlerrate, Tabellen-/Laborwert-Treffer,
  Handschrift, Sekunden/Seite, RAM-Höchststand, CPU-Last, große PDF.
- Ergebnis: Ressourcenprofil + Modellwahl als Doku, **Freigabe durch euch**.

### Phase 1 – MVP
1. App `ki`: Modelle, Migrationen, Rechte, Audit-Arten, Einstellungen (Admin).
2. Container `ki-modell` (llama-server-Image, Modelle offline einspielen wie `epm-ocr-modelle`), Compose-Profil `ki`,
   DB-Rolle `epm_ki`, verschlüsselte Arbeitsablage.
3. `ki-worker`: Zeitfenster-Scheduler, Queue mit Lebenszeichen/Absturzschutz, Ressourcensteuerung, Pause bei
   Sicherung/Update.
4. Pipeline: OCR Stufe 1 (bestehend) + Stufe 2 (Qwen), Klassifikation, Metadaten, Laborwert- und
   Infusionsplan-Extraktion, Regelprüfung.
5. Oberfläche: Menüpunkt-Queue, Prüfansicht, Übernahme Laborwerte (über `LaborbefundSerializer`) und Dokument;
   Akte-Reiter.
6. Tests (siehe 7) und Doku (`docs/BACKEND-FUNKTIONEN.md`, Betriebsanleitung).

### Phase 2 – Verknüpfung, Hinweise, Berichte
- Regelwerk Labor ↔ Infusion, `KiHinweis`, Anzeige im Akte-Reiter und in der Prüfansicht.
- Übernahme historischer Infusionspläne (nach F8) und Freitextabschnitte.
- Berichtsentwurf auf Anforderung: Fakten aus freigegebenen Daten sammeln → Qwen formuliert mit Quellenmarken →
  Prüfer im Code: jede Zahl/jedes Datum im Text muss in den Quellen vorkommen, sonst Markierung; Verbot von
  Empfehlungen/Diagnosen per Prompt **und** Wortfilter; Ablage als `Bericht` im Entwurf mit KI-Kennzeichnung.

### Phase 3 – Qualität und Verbesserung
- Qualitäts-Dashboard (OCR-Fehlerrate, Fehlerarten, Typgenauigkeit, Laborwert-/Infusions-Genauigkeit, Zahl der
  Korrekturen, Verlauf über Zeit) aus `KiKorrektur`/`KiFeld`.
- Evaluationsdatensatz aus Korrekturen (pseudonymisiert), Modell-Registry, Evaluation, Aktivierung, Rollback.
- Trainingsfreigabe mit Pseudonymisierung und Rechtsgrundlagen-Nachweis; Export nur verschlüsselt für die getrennte
  Trainingsumgebung (keine Trainings-Software auf dem Produktivserver).
- Optional: semantischer Index (pgvector + lokales Embedding-Modell).

### Phase 4 – Betrieb
- Deployment (Compose-Profil, `04-projekt.sh`/`epm-update` erweitert, Notfallpaket enthält KI-Modelle), Sicherung
  von Modell-Registry, Index, Konfiguration und `ki_*`-Tabellen (Datenbank ist schon in der Sicherung; Modelldateien
  ins Notfallpaket statt in die tägliche Sicherung).
- Betriebsdoku: Start/Stopp, Zeitfenster, Modellwechsel, Fehleranalyse (Protokolle, Statusseite), Rollback,
  Datenschutz- und Sicherheitsdoku.

## 7. Testkonzept

| Bereich | Tests |
|---|---|
| OCR | synthetische Seiten (`scans/testbilder.py`) inkl. Tabellen, verrauscht; Stufe-2-Abgleich mit **Modell-Attrappe** (fester JSON-Antwortserver), echte Modellläufe nur im Benchmark/auf der VM |
| Extraktion | JSON-Schema-Validierung, Katalog-Abbildung, Einheiten, Plausibilität, Widerspruch LLM ↔ Regeln → „unsicher“ |
| Verknüpfung | Tabellen-Tests: niedrig → Substitution → normalisiert; weiterhin niedrig ohne Maßnahme; Dosisänderung über `vorgaenger`; Zeitfenstergrenzen; gesichert vs. wahrscheinlich; nur Tagesdatum |
| Rechte | jede Rolle × jeder Endpunkt; Firmen-Trennung; Übungszugänge; Übernahme ohne Akten-Recht abgewiesen |
| Schreibsperre | Worker mit DB-Rolle `epm_ki` kann nicht in `befunde_*`/`infusionen_*` schreiben; keine Übernahme ohne Benutzer |
| Konflikte | Übernahme bei vorhandenem Eintrag ohne Entscheidung → abgewiesen; ersetzen behält Historie |
| Audit | jede Aktion erzeugt genau einen Eintrag mit Modellversion |
| Ressourcen | Scheduler (Zeitfenster über Mitternacht, Sommer-/Winterzeit), Pause bei Last/Sicherung, Hysterese, Rückfall auf klassische OCR, Absturz mitten in Seite |
| Offline | `socket.connect` verboten während Pipeline und Berichtserstellung |
| Berichte | erfundene Zahl im Entwurf wird markiert; Empfehlungsformulierungen werden markiert; Quellenliste vollständig |
| Browser | Playwright: Queue filtern, Feld korrigieren, Konfliktwahl, Übernahme, Ablehnung, Akte-Reiter |

## 8. Risiken

- **Durchsatz auf CPU** ist der größte Unsicherheitsfaktor → Phase 0 misst, bevor gebaut wird; gezielter Einsatz des
  LLM nur dort, wo die klassische OCR unsicher ist.
- **Halluzinationen**: kein Feld ohne Beleg im Bild/OCR-Text gilt als sicher; Zahlen werden gegen den OCR-Text
  gegengeprüft; nichts ohne Freigabe in der Akte.
- **RAM-Konkurrenz** auf 8 GB: harte Grenzen, Tagesmodus entlädt das Modell, Pause bei knappem Speicher.
