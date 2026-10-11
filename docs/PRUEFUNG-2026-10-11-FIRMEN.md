# Browserprüfung beider Firmen (11.10.2026)

Anlass: EPM arbeitet seit dem 11.10.2026 für zwei Firmen – DSKM (Standardfarben) und Regeneration Clinic („RGC“,
Salbeigrün/Anthrazit). Geprüft wurde jede Seite, jeder Menüpunkt, jeder nicht zerstörende Knopf und jedes Formular in
beiden Firmen, am Bildschirm, am Tablet und am Telefon.

## Vorgehen

- Umgebung: Entwicklungsstand (Django 127.0.0.1:8000, Vite 127.0.0.1:5173), Chromium 1194 über Playwright; für
  Lighthouse das gebaute Frontend (`vite build`, `vite preview` auf 127.0.0.1:4173, `/api` über den Proxy).
- Konto: `e2e.admin` (sieht alle Seiten der Administration), für die Prüfung zusätzlich Admin in der RGC
  (`Mitgliedschaft`; bleibt in der lokalen Datenbank). Formulare am Telefon und die Schublade mit `e2e.test`
  (Mediziner in beiden Firmen). Akte: Max Mustermann (Testpatient, beiden Firmen zugeordnet), Plan-Editor mit einem
  vorhandenen Plan.
- Größen: Desktop 1440 × 900, Tablet 1024 × 768, Telefon 390 × 844; Firmen-Umschalter zusätzlich bei 1100 px
  (schmale Leiste) und die Schublade bei 360 × 640.
- Je Seite: Fehler und Warnungen der Konsole, fehlgeschlagene Anfragen (≥ 400), Seite breiter als das Fenster,
  Elemente außerhalb des Fensters, aktive Firma (`data-firma`).
- Knöpfe: auf jeder Seite jeder sichtbare Knopf, Reiter und Aufklapper (je Seite bis 45, ohne Wiederholungen),
  außer zerstörenden oder auslösenden (Löschen, Abschließen, Sperren, Zurücksetzen, Abmelden, Ausblenden,
  Wiederherstellen, Import, Update, Backup, Speichern, Senden, Darstellung …). Geöffnete Dialoge und Menüs:
  Lage im Fenster, Name des Dialogs, axe-Prüfung des Dialogs, Felder nicht breiter als der Dialog; danach Escape bzw.
  „Abbrechen“.
- Formulare: Neuer Patient, Konto, Versorger, Arzt, Benutzer, Termin (Kalender und Akte), Diagnose, Medikament,
  Kontakt, Gewicht, Suche. Jedes Feld: zugänglicher Name; Textfelder mit Umlauten und 300 Zeichen ohne Umbruch
  („Größe Ärztin Öztürk-Müßig – Überweisung …“) – Wert erhalten bzw. sauber auf `maxlength` gekürzt, Feld bleibt im
  Formular; leeres Speichern zeigt eine Meldung.
- Echt gespeichert (nur Testpatienten): je Firma ein neuer Patient über „Neuer Patient“ (Admin legt immer
  Testpatienten an, Nr. ≥ 9001: „Prüfüng-Äöß…, Jürgen“), darin Gewicht 72,5 kg, ein Kontakt, eine Diagnose
  („Mangelernährung – Prüfung Ä“, E43) und ein Medikament („Ölsäure-Präparat“) – alles erscheint in der Akte.
- Barrierefreiheit: axe-core 4 mit `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`, `best-practice` auf jeder
  Seite (Desktop und Telefon, beide Firmen) und in jedem geöffneten Dialog. Das sind die Prüfungen, die WAVE
  ausführt; WAVE selbst erreicht lokale Seiten nicht und wurde daher nicht benutzt.
- Lighthouse 12 (mobil und Desktop) für Anmeldung, Start, Patienten, Akte und Kalender in beiden Firmen, angemeldet
  über ein eigenes Chromium-Profil mit der Sitzung (die Kopfzeile `Cookie` allein genügt nicht: Chrome ersetzt sie,
  sobald der Server das CSRF-Cookie setzt – die ersten Messungen liefen deshalb unangemeldet und wurden verworfen).

## Abdeckung

36 Adressen (Start, Patienten, Neuer Patient, Akte mit allen 16 Reitern/Ansichten einschließlich Karteikarte,
Plan-Editor neu und bearbeiten, Kalender, Infusionspläne, Versorger, Ärzte, Datenschutz, Scans, Hilfe, Design, Konto,
Systemverwaltung, Backup, Benutzer, Vorlagen, Dokumentvorlagen, Audit-Log, System, Import) plus Anmeldung.

| Bereich | DSKM Desktop | DSKM Tablet | DSKM Telefon | RGC Desktop | RGC Tablet | RGC Telefon |
|---|---|---|---|---|---|---|
| Anmeldung | ✓ | ✓ | ✓ | (gleiche Seite) | | |
| Start, Patienten, Neuer Patient | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Akte: 16 Reiter + Plan-Editor | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Kalender, Infusionspläne, Versorger, Ärzte | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Datenschutz, Scans, Hilfe, Design, Konto | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Administration (7 Seiten) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Import | ✓ | ✓ | ✓ | leitet zur Startseite (gewollt) | ← | ← |
| Knöpfe/Dialoge | ✓ | – | ✓ | ✓ | – | ✓ |
| Formulare (Felder, leeres Speichern) | ✓ | – | ✓ | ✓ | – | ✓ |
| Speichern auf Testpatient | ✓ | – | – | ✓ | – | – |
| axe Seiten | ✓ | – | ✓ | ✓ | – | ✓ |

Seitenaufrufe je Lauf 216 (36 × 3 Größen × 2 Firmen) plus 144 im Schema „Dunkel“ (Desktop und Telefon). Knöpfe im
Abschlusslauf: 2083 Klicks, davon 801 mit Dialog oder Menü, 137 verschiedene Dialoge mit axe geprüft; kein Dialog
ragt aus dem Fenster (auch nicht bei 390 px), keiner ohne Namen.

## Firmen

| Prüfung | Ergebnis |
|---|---|
| RGC: Leiste `rgb(190, 201, 195)`, Logo der Klinik geladen, „Import“ fehlt in der Navigation, Kopf der Akte „DSKM · RGC“, Marken an Einträgen | ✓ |
| DSKM: Leiste weiß, Stiftungslogo bzw. hochgeladenes Logo, „Import“ vorhanden | ✓ |
| Umschalter 1440 px (Segmente unter dem Logo), 1100 px (Kürzel-Knopf der schmalen Leiste), 390 px (Schublade, Chip im Kopf) | ✓ – nach Behebung des Sitzungsfehlers (unten, Nr. 1) dreimal in Folge stabil |
| Schublade von rechts (390 × 844, 360 × 640): Breite 320 px, „Menü schließen“ 32 × 32 px oben rechts, überdeckt das Logo nicht, `safe-area`-Abstände oben/unten gesetzt, schließt per Knopf; bei 360 × 640 scrollt die Leiste innen | ✓ |

## Lighthouse (gebautes Frontend, lokal, nach den Korrekturen)

Werte Performance / Barrierefreiheit / Best Practices / SEO.

| Seite | Firma | mobil | Desktop | Barrierefreiheit vor der 2. Korrekturrunde (mobil/Desktop) |
|---|---|---|---|---|
| Anmeldung | – | 93 / 100 / 100 / 63 | 100 / 100 / 100 / 63 | 100 / 100 |
| Start | DSKM | 85 / 100 / 100 / 63 | 100 / 100 / 100 / 63 | 100 / 100 |
| Patienten | DSKM | 82 / 100 / 100 / 63 | 100 / 100 / 100 / 63 | 96 / 100 |
| Akte | DSKM | 86 / 100 / 96 / 63 | 99 / 100 / 96 / 63 | 100 / 100 |
| Kalender | DSKM | 98 / 100 / 100 / 63 | 100 / 100 / 100 / 63 | 100 / 96 |
| Start | RGC | 83 / 100 / 100 / 63 | 100 / 100 / 100 / 63 | 100 / 100 |
| Patienten | RGC | 99 / 100 / 100 / 63 | 100 / 100 / 100 / 63 | 96 / 100 |
| Akte | RGC | 80 / 100 / 96 / 63 | 99 / 100 / 96 / 63 | 100 / 100 |
| Kalender | RGC | 96 / 100 / 100 / 63 | 100 / 100 / 100 / 63 | 100 / 100 |

- SEO 63: allein „nicht indexierbar“ – `noindex, nofollow` ist für ein Patientensystem gewollt.
- Best Practices 96 (Akte): 403 auf `POST /api/meine-akten/geoeffnet/` – nur in dieser Messung, weil die Vorschau auf
  Port 4173 kein vertrauenswürdiger Ursprung für CSRF ist; im Betrieb (gleicher Ursprung) und auf 5173 tritt er nicht auf.
- Performance mobil 80–86 bei Start und Akte (simuliertes langsames 4G, LCP 2,5–3,8 s, TBT bis 660 ms); die Maschine
  war während der Messung zusätzlich durch den Django-Entwicklungsserver belastet. Desktop 99–100.

## axe-core vorher → nachher

Seiten (36 × Desktop/Telefon × 2 Firmen = 144 Prüfungen):

| Regel | vorher (Seiten / Knoten) | nachher |
|---|---|---|
| `aria-required-attr` (Messbalken CPU ohne `aria-valuenow`) | 6 / 6 | 0 |
| `color-contrast` (Zähler in Umschaltern; RGC-Kürzel im Benutzer-Chip) | 6 / 88 | 0 |
| `target-size` (Kalender „+N weitere“; Hinweis-Sprünge am Telefon) | 2 / 84 | 0 |
| `scrollable-region-focusable` (Kachel „Datensicherung“ am Telefon) | 3 / 3 | 0 |
| `link-in-text-block` (Datenschutz am Telefon) | 1 / 1 | 0 |
| `region` (Ladebalken außerhalb der Landmarken, nur während eine Anfrage lief) | im Abschlusslauf 4 / 4 | 0 (Lauf „Dunkel“ nach Nr. 12) |

Dialoge (jeder geöffnete Dialog einmal je Firma und Größe): vorher `aria-dialog-name` (Hinweisliste der Akte),
`link-in-text-block` („Herunterladen“ im Dokument-Dialog, 2×), `color-contrast` im Schema „Dunkel“ (Firmenwahl) und
16 Klicks, die einen Dialog ohne Namen öffneten → nachher 0 Verstöße in 137 Dialogen.

Schema „Dunkel“ (zusätzlicher Lauf, 36 Seiten × Desktop/Telefon × 2 Firmen): vorher `color-contrast` auf 10 Seiten
(16 Knoten, nur DSKM: gedämpfte Schrift `#b8bac0` auf der getönten Auswahl `#4c4a5c` = 4,43:1 – gewählte Zeile in
Benutzer, Versorger, Ärzte, Karten in Plänen, Labor, BIA) → nachher 0 (eine Seite ohne Überschrift, weil die Akte
wegen eines 500ers der Datenbank – siehe unten – nicht lud).

Anmeldung (Desktop, Tablet, Telefon): 0 Verstöße, keine Konsolenfehler.

## Befunde und Behebung

| Nr. | Befund | Behebung |
|---|---|---|
| 1 | **Firmenwechsel sprang zurück** (schmale Leiste 1100 px und Schublade): eine gleichzeitig laufende Anfrage speicherte die Sitzung mit der alten Firma, weil Django jede Sitzung bei jeder Anfrage vollständig zurückschrieb (`SESSION_SAVE_EVERY_REQUEST`) | Behoben von der Sicherheitsprüfung: `SESSION_SAVE_EVERY_REQUEST = False`, `accounts/sitzungen.py` verlängert nur noch das Ablaufdatum. Nachgeprüft: 1440/1100/390 px dreimal stabil |
| 2 | Jede RGC-Seite: 404 `/api/briefkopf/logo/?firma=rg` in der Konsole (kein eigenes Logo hochgeladen) | Oberfläche fragt mit `?leer=1`, der Server antwortet ohne Upload 204 statt 404; das mitgelieferte Logo erscheint ohne Konsolenfehler (`components/layout/logo.tsx`, `backend/stammdaten/api.py`, Test in `stammdaten/tests.py`). Ohne `leer` bleibt es bei 404 |
| 3 | Warnung „No `HydrateFallback` element“ beim ersten Laden jeder Seite | `hydrateFallbackElement` mit „EPM wird geladen …“ (`src/App.tsx`) |
| 4 | Messbalken CPU/Speicher der Startseite ohne Wert (`role="meter"` ohne `aria-valuenow`) | Wert 0 mit `aria-valuetext="keine Messung"` (`seiten/start/admin.tsx`) |
| 5 | Kontrast 4,0:1 der Zähler in Umschaltern (Patienten, Infusionspläne) | Deckkraft 70 → 80 % (`seiten/Patienten.tsx`, `seiten/Infusionsplaene.tsx`) |
| 6 | RGC, Benutzer: Firmenkürzel im gewählten Chip 3,8:1 | ohne zusätzliche Transparenz (`seiten/admin/Benutzer.tsx`) |
| 7 | Zielgröße unter 24 px: „+N weitere“ im Kalender, Einträge im Monatsraster, Sprünge in Hinweis-Chips, Fachbegriffe in Chips (Telefon) | „+N weitere“ 24 px hoch, 4 px Abstand zwischen Einträgen (`seiten/Kalender.tsx`); `.hinweis-sprung` und `.chip .begriff` mit 5 px Innenabstand oben/unten (`index.css`; der alte Kommentar „24 px“ stimmte mit 1 px nicht) |
| 8 | Kachel „Datensicherung“ am Telefon scrollt, ist aber nicht per Tastatur erreichbar | `KachelInhalt` wird fokussierbar, sobald der Inhalt überläuft (`seiten/start/kacheln.tsx`) |
| 9 | Links im Fließtext ohne Unterstreichung (Tailwind setzt `text-decoration: inherit`): Datenschutz-Listen, „Herunterladen“ im Dokument-Dialog | unterstrichen (`seiten/Datenschutz.tsx`, `seiten/akte/Dokumente.tsx`) |
| 10 | Hinweisliste der Akte („N Hinweise“) als Dialog ohne Namen | `aria-label="Hinweise zu dieser Akte"` (`components/HinweisChips.tsx`) |
| 11 | Schema „Dunkel“ (DSKM): gedämpfte Schrift auf getönter Auswahl 4,4:1 (Firmenwahl, gewählte Zeilen, Karten) | `--gedaempft` im Schema „Dunkel“ `#b8bac0` → `#bcbec4` (4,6:1) (`index.css`) |
| 12 | Ladebalken als `progressbar` außerhalb jeder Landmarke (axe `region`) | nur noch sichtbar (`aria-hidden`); Seiten melden das Laden selbst (`components/ui/Ladebalken.tsx`) |
| 13 | Versorger und Ärzte: 300 Zeichen ließen sich eintippen, erst das Speichern scheiterte („nicht mehr als 150 Zeichen“) | `maxLength` wie in der Datenbank (`seiten/Versorger.tsx`, `seiten/Aerzte.tsx`) |
| 14 | Nebenwirkung der Knopfprüfung: die Darstellung von `e2e.admin` wurde auf „Dunkel“/„Karteikarte“ umgeschaltet | zurückgesetzt (`darstellung = {}`); die Knopfprüfung lässt Darstellungs-Knöpfe seither aus |
| 15 | Ein einzelner 500er oder Netzfehler beim Abruf von `/api/auth/status/` zeigte die **Anmeldeseite**, obwohl die Sitzung galt (beobachtet während der Datenbank-Engpässe, siehe unten) | Bei Serverfehler (≥ 500) oder fehlender Verbindung bis zu drei Versuche (1,5 s, 3 s), erst dann die Anmeldung (`lib/auth.tsx`) |

Neuer Regressionstest: `e2e/audit-firmen.spec.ts` – in beiden Firmen jede Seite der Navigation, „Neuer Patient“, jeder
Reiter der gemeinsamen Akte, Hilfe, Design und Konto bei 1440 und 390 px: keine Konsolenfehler, keine Anfrage ≥ 400,
nichts ragt seitlich heraus, `data-firma` stimmt; dazu Farbe der Leiste und geladenes Logo.

## Offen bzw. bewusst so gelassen

- **500er im Entwicklungsbetrieb** (verstreut, u. a. `scans/stand`, `protokoll`, `auswahlwerte`): alle 94 waren
  „too many clients“ von PostgreSQL. Der Entwicklungsserver startet je Anfrage einen Thread, jeder hält mit
  `CONN_MAX_AGE = 60` eine eigene Verbindung (bis zu 85 gleichzeitig bei max. 100), parallel liefen die Tests der
  Sicherheitsprüfung. Kein Fehler der Seiten; im Betrieb (feste Worker) nicht zu erwarten. Vorschlag für die
  Entwicklung: `CONN_MAX_AGE = 0` unter `runserver`. Einzelne 500er/`ECONNREFUSED` stammen zudem von Neustarts des
  Entwicklungsservers während der Änderungen der Sicherheitsprüfung; jede betroffene Aktion (Merkliste, Versorgung,
  Bezugsperson, Termin) wurde danach einzeln wiederholt – ohne Fehler.
- **Gemeinsames Datenverzeichnis**: Die Backend-Tests schrieben offenbar in dasselbe `EPM_DOKUMENTE` wie der
  Entwicklungsstand. Um 19:23 wurden die PDFs der Musterakte 9002 ersetzt; Dokument und Infusionsplan zeigten danach auf
  eine gelöschte Datei (`/api/dokumente/…/datei/` → 500 `FileNotFoundError` im Entwicklungspfad ohne X-Accel, Plan-PDF
  → 404). Behoben durch Zurücksetzen der Testdaten (`testdaten_zuruecksetzen`, nur Testpatienten; neue IDs). Im Betrieb
  liefert Nginx die Datei aus (dort 404).
- Patienten am Telefon, nur für Konten, die Testpatienten sehen (Admin, Testzugang): Layout-Verschiebung 0,16, weil
  „· zusätzlich N Testpatienten …“ nach dem Laden in eine zweite Zeile umbricht. Für die Praxis ohne Wirkung.
- Schublade in einem schmalen Desktop-Fenster (< 768 px, Scrollleiste mit fester Breite): 15 px Abstand rechts, weil
  `scrollbar-gutter: stable` den Platz der Scrollleiste freihält. Auf Telefonen (überlagernde Scrollleisten) liegt sie
  bündig am Rand (gemessen mit iPhone-13-Emulation).
- Formular „Medikament“: Speichern bleibt gesperrt, bis ein Wirkstoff eingetragen ist (keine Meldung nötig);
  „Diagnose“ verlangt den ICD-Code (Pflichtfeld).
- Nicht geprüft: zerstörende und auslösende Aktionen (siehe Vorgehen), Datei-Upload und Kamera, Passkey-Anmeldung,
  echte Geräte (nur Emulation), Safari/Firefox, WAVE (lokal nicht erreichbar). Schema „Dunkel“ wurde für Seiten und Dialoge geprüft, „Hoher Kontrast“ und „Individuell“ nicht.

## Tests

ERGEBNIS_TESTS
