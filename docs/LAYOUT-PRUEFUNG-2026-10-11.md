# Layout-Prüfung Tablet und Telefon (11.10.2026)

Anlass: Fehlermeldung der Praxis – am Tablet ließ sich auf einigen Flächen das Bild nicht bewegen („wie eingefroren“),
am Telefon ragten bei der Terminbuchung Elemente rechts heraus.

## Vorgehen

- Alle Seiten (Startseite, Patienten, alle Reiter der Akte, Kalender, Pläne, Versorger, Ärzte, Datenschutz, Scans,
  Konto, Hilfe, Administration) auf sechs Geräten mit Touch-Emulation: Telefon 320 und 390 px, Tablet hochkant 768 px,
  Tablet quer 1024, 1280 × 800 und 1366 × 1024.
- Je Seite: Breite der Seite, Elemente außerhalb des Bildschirms, abgeschnittene Inhalte; Wischen mit echten
  Touch-Ereignissen an 16 Punkten und in jedem inneren Scrollbereich, der am Ende steht.
- Lighthouse 12 (mobil und Desktop) auf dem gebauten Frontend; Barrierefreiheit mit axe-core 4 (WCAG 2.2 AA und
  Best Practices – dieselben Prüfungen wie WAVE, das lokale Seiten nicht erreicht), Desktop 1440 px und Telefon 390 px.

## Ursachen und Behebung

| Befund | Ursache | Behebung |
|---|---|---|
| Tablet „eingefroren“ (Startseite, Akte, Listen) | Innere Scrollbereiche mit `overscroll-behavior: contain` (Kacheln, Karten fester Höhe, Listen, Spalten): war der Bereich am Ende, lief die Seite beim Wischen nicht weiter | Mit Finger (`pointer: coarse`) reichen diese Bereiche das Wischen an die Seite weiter; mit Maus bleibt das Mausrad im Bereich |
| Tablet ab 1280 px: Akte über Kopf und Reiter nicht wischbar | Akte füllt ab 1280 × 600 px das Fenster (Seite `overflow: hidden`) | Gilt nur noch mit Maus/Touchpad (`pointer: fine`); auf Tablets scrollt die Seite |
| Diagramm Auslastung (System) blockierte das Wischen | `touch-action: none` über die ganze Fläche | `touch-action: pan-y` – senkrecht wischen scrollt, waagerecht zeigt Werte |
| Terminbuchung am Telefon: „ändern“ ragt rechts heraus | Gewählter Patient (Nummer, langer Name, Geburtsdatum) ohne Umbruch | Name bricht um, „ändern“ bleibt rechts; Trefferliste ebenso |
| Datum/Uhrzeit (iPhone, iPad) breiter als der Dialog | Safari gibt diesen Feldern eine feste Mindestbreite | `min-width: 0` und `appearance: none` für Datums- und Zeitfelder; Felder nie breiter als ihre Spalte |
| Vorlagen, Dokumentvorlagen, System am Tablet hochkant 990–1008 px breit | Umschalter/Reiter ohne Umbruch, Vorlagenkarten ohne `min-width: 0` | Umschalter brechen um; Karten und Titel brechen um |
| Systemverwaltung am Telefon 320 px: Knopf „EPM aktualisieren“ ragt heraus | Knopfgruppe `shrink-0` neben dem Text | Knöpfe am Telefon in eigener Zeile |

## Messwerte vorher → nachher

Lighthouse (gebautes Frontend, lokal):

| Seite | Performance mobil | Performance Desktop | Barrierefreiheit |
|---|---|---|---|
| Start | 39 → 68 | 93 → 96 | 100 |
| Patienten | – → 84 | 79 → 100 (Layout-Verschiebung 0,48 → 0,01) | 100 |
| Kalender | – → 82 | – → 100 | 100 |

Erstes Paket 853 kB → 683 kB (gzip 265 → 218 kB): die Kacheln der Administration auf der Startseite werden erst geladen,
wenn sie angezeigt werden. Bewusst unverändert: SEO „nicht indexierbar“ (`noindex` für ein Patientensystem gewollt),
keine Source-Maps im Betrieb, der 404 auf `/api/briefkopf/logo/` ohne eigenes Logo (Vertrag des Backends).

axe-core: 11 Regeln mit Verstößen → 1. Behoben: Name der Knöpfe passt zum sichtbaren Text (Benutzermenü, „Neu anlegen“,
„Zur Liste“), Erklärungen der Fachbegriffe außerhalb der Landmarken, Seitenleiste als eindeutige Landmarke, Kontrast
(Kartei, Kalender), Listen ohne Einträge, Rolle `listitem` am Knopf (Pläne), Scrollbereiche per Tastatur erreichbar,
leere Tabellenköpfe, Links im Fließtext unterstrichen, Zielgröße der „×“-Knöpfe (24 px), Überschrift des Kalenders am
Telefon. Offen (gering): Kalendereinträge und Plankarten am Telefon haben einen ausführlicheren Namen als der sichtbare
Text (WCAG 2.5.3) – die Browsertests sprechen sie über diesen Namen an.

Layout-Audit nachher: auf allen sechs Geräten keine Seite breiter als der Bildschirm, kein Element außerhalb, keine
Fläche, auf der Wischen hängen bleibt.

## Komponenten von shadcn/ui

Geprüft, aber nicht übernommen: Datumsauswahl (Date Picker) und Auswahl-Pills. Die eingebauten Datums- und Zeitfelder
öffnen auf Tablet und Telefon die Auswahl des Geräts (große Ziele, Sprache und Format des Geräts, offline), die
Ursache des Überstands war die Mindestbreite in Safari, nicht das Feld selbst. Eine eigene Kalenderauswahl brächte
zusätzliche Bibliotheken (react-day-picker, date-fns) ohne Gewinn am Touchgerät.

## Regressionstests

`frontend/e2e/touch.spec.ts`: Tablet 1280 × 800 mit Finger (Akte wischbar über den Kopf, Kachel am Ende hält das Wischen
nicht fest), Telefon 320 px (Terminbuchung mit langem Namen ragt nicht heraus).
