# Performance-Prüfung 14.11.2026

Ziel: EPM messbar schneller machen (Vorgabe 50 %), ohne Funktionen zu verlieren oder zu verändern; Skelett-Platzhalter
für eine schneller wirkende Oberfläche.

**Ergebnis in einem Satz:** Die Datenbanklast sinkt um 23–40 %, die langsamsten Seiten werden 30–86 % schneller
(Ärzte, Startseite, Administration), die Oberfläche steht dank Skeletten sofort in ihrer Form da – über alle 29
gemessenen Seiten zusammen sind es aber −16 % (Navigation in der Anwendung) bzw. −9 % (Seite neu laden), nicht −50 %.
Was übrig bleibt, ist vor allem Netzlaufzeit und die PDF-Ansicht der Infusionspläne (siehe „Offen“).

## Messung

- 246 Akten mit Kontakten, Gewichten, Plänen, Labor, BIA (Musterdaten, 41-fach angelegt), PostgreSQL 16.
- Alter Stand (Commit `7d92491`) und neuer Stand laufen **gleichzeitig** gegen dieselbe Datenbank; Prüfserver wie
  Nginx im Betrieb (HTTP/2, TLS, `/assets/` ein Jahr im Cache, gzip), gunicorn wie im Image.
- Chromium mit gedrosseltem Netz wie im VPN (40 ms Latenz, 20 Mbit/s). „Fertig“ = keine offene Anfrage und kein
  Ladehinweis mehr. Median aus 3 Runden, 29 Seiten (22 als Mediziner, 7 als Admin).
- Zwei Arten: **Navigation** (angemeldet, Klick in der Anwendung, 1 s Bedienzeit dazwischen) und **Neuladen**
  (ganze Seite neu laden, Dateien im Browser-Cache).
- Werkzeuge: `werkzeuge/performance/`. Antworten aller 318 geprüften API-Adressen (5 Konten, mehrere Akten, Ärzte) sind
  vorher und nachher **byte-gleich**.

### Gesamt

| | vorher | nachher | Änderung |
|---|---|---|---|
| Navigation, Summe 29 Seiten | 5,52 s | 4,64 s | **−16 %** |
| Neuladen, Summe 29 Seiten | 10,26 s | 9,34 s | **−9 %** |
| SQL-Abfragen, Navigation | 3.290 | 1.983 | **−40 %** |
| SQL-Abfragen, Neuladen | 8.743 | 6.733 | **−23 %** |

### Einzelne Seiten (Navigation / Neuladen, ms)

| Seite | vorher | nachher | |
|---|---|---|---|
| Ärzte | 810 / 999 | 134 / 279 | **−83 % / −72 %** (SQL 1.145 → 40) |
| Startseite (Mediziner) | – / 691 | – / 457 | **−34 %** (SQL 555 → 263) |
| Startseite (Admin) | – / 703 | – / 532 | **−24 %** (SQL 660 → 366) |
| Patientenliste | 184 / 246 | 130 / 254 | −29 % / ±0 |
| Vorlagen (Admin) | 229 / 280 | 177 / 249 | −23 % / −11 % |
| Hilfe | 115 / 215 | 114 / 178 | SQL 102 → 37 |
| Akte Übersicht | 383 / 447 | 394 / 440 | ±0 |
| Infusionspläne der Akte | 1.147 / 711 | 1.169 / 612 | ±0 / −14 % |

API-Endpunkte allein (Testclient, warm): `/api/startseite/` 392 → 98 Abfragen (405 → 230 ms), für den Testzugang
986 → 99 (781 → 253 ms); `/api/aerzte/1/patienten/` 1.120 → 15 (685 → 41 ms); `/api/patienten/zaehler/` 311 → 24;
`/api/hilfe/` 77 → 12; `/api/vorlagen/` 146 → 81. Die Listen zählen jetzt unabhängig von der Zahl der Zeilen – mit
mehr Ärzten, Versorgern und Plänen im Echtbetrieb wächst der Abstand.

## Änderungen

### Skelett-Platzhalter (Optik)
- `Laden` ohne eigenen Text zeigt Platzhalterzeilen in Form von Text statt des Ladekreises (rund 100 Stellen auf einmal,
  `components/ui/basis.tsx`). Mit eigenem Text („PDF wird erzeugt …“) bleibt der Ladekreis – dort sagt der Text,
  worauf gewartet wird. Für Screenreader bleibt „Wird geladen …“ (`role="status"`).
- Gerüst der Anwendung (Seitenleiste, Kopfzeile, Karten) schon in `index.html`, bevor das Skript geladen ist, und
  gleich in React (`AppSkelett`) – kein Springen beim Übergang. Mit sichtbarem Text „EPM wird geladen …“, weil reine
  Platzhalterflächen für den Browser nicht als erster Inhalt (FCP) zählen.
- Akte: Kopf, Reiter und sechs Karten als Platzhalter (`AkteSkelett` in `seiten/akte/Akte.tsx`); Patientenliste mit
  acht Zeilen.
- Glanz-Animation entfällt bei „Bewegung reduzieren“ (`prefers-reduced-motion`).

### Frontend
- **Seiten vorladen** (`lib/vorladen.ts`): Nach dem Start lädt der Browser im Leerlauf die Dateien von Patienten,
  Akte, Übersicht, Kontakten, Plänen, Dokumenten, Kalender und Infusionsplänen – ein Klick wartet dann nicht auf das
  Netz.
- **Akte beim Überfahren**: Bleibt die Maus 100 ms auf einem Link zu einer Akte, holt EPM deren Kopfdaten vorab
  (dieselbe Abfrage wie die Akte, nur Lesen, nicht protokolliert). Ohne Ladebalken (`still`) und als
  Hintergrundabfrage – verlängert die Sitzung nicht (F12 unverändert).
- **Anmeldestatus per Preload** in `index.html`: wird parallel zum Skript angefragt statt erst nach dem Start von React.
- **Bibliotheken als eigene Datei** (`vite.config.ts`, `bibliotheken-*.js`, 160 KB gz): nach einem EPM-Update lädt
  der Browser nur den eigenen Code neu (66 KB statt 226 KB komprimiert).

### Backend
- `patienten/kennzahlen.py`: `.only()` ließ `nickelallergie` und `kein_katheter` aus – Django lud sie je Akte einzeln
  nach (Hauptursache der Startseite). Kennzahlen der Prüfliste einmal statt zweimal (Labor, BIA) bzw. von der Startseite
  übernommen.
- `patienten/api.py`: Startseite übernimmt Kennzahlen und Einstellungen; Aktenkopf lädt den Verlauf einmal statt je
  Textfeld.
- `stammdaten/api.py`: Patienten je Arzt bzw. Ansprechpartner mit vorgeladenen Verknüpfungen; Patientenzahlen in den
  Listen der Versorger, Ansprechpartner und Ärzte als Unterabfrage statt je Zeile.
- `infusionen/`: Vorgänger mit Vitaminen und Positionen vorgeladen (`geaenderte_felder` über `.all()`, gleiche
  Reihenfolge laut `Meta.ordering`).
- `hilfe/api.py`: Rechte einmal je Anfrage; `vorlagen/api.py`: gemeinsame Werte einmal je Antwort;
  `epm/firma.py`, `accounts/api.py`: Firmen und Admin-Firmen einmal je Benutzerliste.
- `entrypoint.sh`: gunicorn mit `--threads 4` je Prozess (`GUNICORN_THREADS`). Eine Akte stellt 17–27 Anfragen
  gleichzeitig; mit 3 Prozessen ohne Threads stand der Rest in der Schlange, solange z. B. eine PDF-Ansicht rechnet.
  Der Zustand je Anfrage (aktive Firma) liegt in einer `ContextVar`, also getrennt je Thread; höchstens 12
  Datenbankverbindungen. In der Messung brachte das kaum etwas (auf dem Prüfrechner teilen sich Datenbank, Server und
  Browser die Kerne) – auf dem Server mit eigener Datenbank-CPU sollte es mehr bringen.
- Neue Tests: Abfragezahl bleibt gleich, wenn Zeilen hinzukommen (`stammdaten/tests.py` `ListenOhneAbfragenJeZeile`,
  `patienten/test_startseite.py`, `infusionen/tests.py`); sie schlagen auf dem alten Stand fehl.

### Prüfung
- 398 Tests (patienten, stammdaten, hilfe, vorlagen, accounts, infusionen, epm) grün; audit, system, faelle, befunde,
  berichte, korrespondenz, diktate, altimport: 265 grün, 1 übersprungen. Typprüfung und Bau des Frontends grün.
- Browsertests (`frontend/e2e`) brauchen den kompletten Stack mit Docker und liefen hier nicht – bitte über
  „Run workflow“ auf dem Branch starten. Keiner von ihnen prüft den Text „Wird geladen“.

## Offen (bewusst nicht geändert)

- **PDF-Ansicht der Infusionspläne** (`/api/infusionsplaene/<id>/ansicht/`): 250 ms reine Rechenzeit in WeasyPrint
  (warm), unter Last bis 0,8 s – größter Einzelposten der Navigation (1,15 s von 4,6 s). Zwischenspeichern wäre nur
  sicher, wenn alle Eingaben im Schlüssel stecken (Akte, Einstellungen, Briefkopf, Logo, Vorlagenversion,
  Wasserzeichen) – eigene Aufgabe.
- **Wellen beim Laden der Akte**: Die Karten fragen erst nach dem Aktenkopf an (Kontext `patient`). Parallel wäre
  schneller, ist aber ein Umbau der Akte.
- **Grundlast je Anfrage** (~10 ms, 9–11 Abfragen: Sitzung, zweiter Faktor, Firma, Rechte): bewusst ohne
  Zwischenspeicher, damit Rechte- und Firmenwechsel sofort wirken.
- Die Messumgebung hatte `libharfbuzz-subset0` zunächst nicht (das Image hat es); nachinstalliert, beide Stände danach
  gleich gemessen.
- Ein früher Lauf von `epm.test_sicherheit.FirmenTrennung.test_admin_der_anderen_firma` schlug einmal fehl (Name einer
  Akte der anderen Firma im Audit-Eintrag), danach dreimal grün; betrifft nicht geänderten Code, wirkt
  reihenfolgeabhängig.
