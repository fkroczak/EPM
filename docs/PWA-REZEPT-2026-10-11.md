# Rezept: EPM als Web-App so intuitiv wie eine Apple-Oberfläche (11.10.2026)

Frage der Praxis: „Gibt es ein Kochrezept, wie eine Website/PWA ähnlich intuitiv sein kann wie die Apple-Oberfläche?“

Kurz: Ja. Apple-Oberflächen wirken nicht wegen ihres Aussehens intuitiv, sondern weil sie ein paar Regeln sehr konsequent
einhalten. Diese Regeln lassen sich im Browser fast vollständig umsetzen. Grundlage sind die *Human Interface Guidelines*
von Apple (developer.apple.com/design/human-interface-guidelines) und die PWA-Checkliste von web.dev. Unten stehen die
Zutaten, was EPM davon schon hat (✓) und was noch fehlt (○).

## 1. Zutaten (die Regeln)

| Regel | Woran man es merkt | EPM |
|---|---|---|
| **Direkte Rückmeldung** – jede Berührung antwortet sofort (< 100 ms), ohne Nachfragen, wenn nichts verloren geht | Haken setzt sich sofort, Fehler werden zurückgenommen | ✓ (Termine abhaken, Rückmeldungen oben) |
| **Große Ziele** – mindestens 44 × 44 pt zum Antippen, Abstand zwischen Zielen | Kein Daneben-Tippen | ✓ am Telefon, ○ Tablet quer (Chips 30 px) |
| **Ein Weg pro Aufgabe, an der Stelle der Aufgabe** – was zu tun ist, führt per Tipp dorthin | Offener Punkt antippen → Dialog | ✓ seit 11.10.2026 (`lib/sprungziele.ts`) |
| **Wischen wie gewohnt** – nichts hält das Scrollen fest, Ränder federn | Kein „eingefroren“ | ✓ seit 11.10.2026 |
| **Nichts ragt heraus, nichts wird abgeschnitten** | Seite wackelt nicht seitlich | ✓ (Layout-Audit auf 6 Geräten) |
| **Gerätefelder nutzen** – Datum, Uhrzeit, Telefon, E-Mail mit den Eingaben des Geräts (`type="date"`, `inputmode`, `autocomplete`) | Passende Tastatur, Rad für Datum | ✓ Datum/Uhrzeit, ○ `inputmode="tel"`/`autocomplete` vollständig prüfen |
| **Schrift folgt der Einstellung** – Größen in rem, „Sehr groß“ vergrößert alles | Ältere Augen | ✓ (Mein Konto › Darstellung) |
| **Dunkel und Bewegung reduzieren** – `prefers-color-scheme`, `prefers-reduced-motion` | Ruhig, augenschonend | ✓ |
| **Sichere Ränder** – Notch und Home-Leiste frei (`env(safe-area-inset-*)`) | Leiste unten nicht verdeckt | ✓ |
| **Telefon: Hauptwege unten, Daumenreichweite** | Leiste unten, Menü als Schublade | ✓ |
| **Blätter statt Seitenwechsel** – kurze Aufgaben im Dialog/Blatt, Hintergrund bleibt sichtbar | Orientierung bleibt | ✓ (Dialoge), ○ am Telefon als Blatt von unten |
| **Platzhalter statt Springen** – Inhalte reservieren ihren Platz beim Laden | Nichts verrutscht beim Antippen | ✓ teils (Lighthouse CLS 0,01–0,2) |
| **Sprache des Alltags** – Verben auf Knöpfen („Kontakt speichern“), keine Fachbegriffe ohne Erklärung | Kein Rätseln | ✓ (Begriffe mit Erklärung) |

## 2. Als App auf den Home-Bildschirm (PWA) – noch offen

Damit EPM auf iPad/iPhone und Android wie eine App startet (eigenes Symbol, ohne Adressleiste):

1. `manifest.webmanifest` mit Name, Symbolen (192/512 px, „maskable“), `display: "standalone"`, `start_url: "/"`,
   `theme_color`/`background_color` aus den Stiftungsfarben.
2. Für iOS zusätzlich `apple-touch-icon` (180 px) und `apple-mobile-web-app-status-bar-style` im `index.html`.
3. **Kein Offline-Zwischenspeicher für Patientendaten.** Ein Service Worker darf höchstens die Programmdateien
   (JS/CSS/Schriften) vorhalten, nie Antworten von `/api/` – Patientendaten bleiben nur auf dem Server
   (Datenschutz). Ohne Service Worker geht es auch; das Symbol auf dem Home-Bildschirm funktioniert trotzdem.
4. Anmeldung: Passkeys funktionieren in der installierten Web-App wie im Browser (Zertifikat der eigenen CA nötig, siehe
   README „Zertifikat und Passkeys“).

Grenzen auf iOS: Push-Nachrichten nur für installierte Web-Apps (ab iOS 16.4) und nur mit Erlaubnis; keine
Hintergrund-Synchronisierung; Speicher kann vom System geleert werden – für EPM unkritisch, weil nichts lokal liegt.

## 3. Vorgehen (das eigentliche „Kochen“)

1. **Wege zählen:** die 5 häufigsten Aufgaben je Rolle aufschreiben (Pflege: Patient finden, Kontakt, Gewicht, Termin,
   Plan freigeben). Ziel: jede in ≤ 3 Tipps vom Start aus.
2. **Auf echten Geräten testen**, nicht nur im Browser-Emulator: ein iPhone, ein iPad, ein Android-Telefon; Safari
   verhält sich bei Datumsfeldern, Scrollen und Tastatur anders als Chrome.
3. **Automatisch prüfen** bei jeder Änderung: Layout-Audit (Überbreite, abgeschnitten, Wischen) auf 6 Größen,
   Lighthouse und axe (Barrierefreiheit) – Ergebnisse siehe `docs/LAYOUT-PRUEFUNG-2026-10-11.md`.
4. **Fünf-Personen-Test:** fünf Pflegekräfte je eine Aufgabe ohne Hilfe lösen lassen und zuschauen, wo sie zögern –
   findet etwa 80 % der Bedienprobleme.
