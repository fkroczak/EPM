# UX-Prüfung 11.10.2026: Hick, Nähe, Lesbarkeit

Geprüft wurde EPM mit drei Grundsätzen. Die Zielgruppe sind Pflegekräfte, Ärztinnen und Ärzte sowie die Verwaltung.
Sie arbeiten oft am Tablet oder Telefon, und viele sind keine Technik-Profis.

1. **Hick'sches Gesetz**: Je mehr Möglichkeiten zur Wahl stehen, desto länger dauert die Entscheidung. Seltenes wird
   deshalb eingeklappt (progressive Offenlegung), und lange Formulare werden in Abschnitte gegliedert.
2. **Gesetz der Nähe**: Eine Bezeichnung steht sichtbar dicht an ihrem Feld. Bis zum nächsten Feld ist der Abstand
   deutlich größer.
3. **Lesbarkeit nach Flesch** (deutsche Fassung nach Amstad) und **Überfliegbarkeit**: kurze Sätze, aktive Sprache, ein
   Gedanke je Satz, Listen für Schritte und die wichtigste Handlung fett.

Vorgehen: erst messen, dann ändern, dann noch einmal messen. Alle Messungen liefen gegen die laufende Anwendung
(Django + Vite, Playwright/Chromium) mit den Testkonten `e2e.*`. Die Konten und Testdaten wurden dabei nicht
zurückgesetzt. Die Messskripte liegen außerhalb des Repos im Scratchpad unter `ux/` (`nahe.mjs`, `messen.mjs`,
`hick.mjs`, `fre.py`, `neu-flow.mjs`).

---

## 1. Gesetz der Nähe

### Methode

Das Skript prüft jedes sichtbare Feld in Seite oder Dialog. Erfasst werden `.feld`, `label[for]` mit Steuerelement und
`fieldset`/`legend`. Gemessen wird bei 1440 px und bei 390 px (Telefon mit Touch):

- **Label-Abstand**: Unterkante der Bezeichnung bis Oberkante der Eingabe,
- **Hinweis-Abstand**: Unterkante der Eingabe bis zum Hinweis bzw. Fehlertext,
- **Feld-Abstand**: Unterkante des Felds (samt Hinweis) bis zur nächsten Bezeichnung in derselben Spalte.

Ziel: Label-Abstand ≤ 6 px und Feld-Abstand ≥ 16 px. Damit ist der Feld-Abstand mindestens das 2,5- bis 3-Fache des
Label-Abstands. Hinweise hängen direkt am Feld.

### Ausgangslage (vorher)

Der Label-Abstand war überall gut: 3 px aus `.feld { gap: 0.1875rem }`. Hinweise hingen mit 3 px am Feld. Der
**Feld-Abstand war meist zu klein**:

| Formular / Dialog | Felder | Feld-Abstand 1440 px (Median) | davon < 16 px | Feld-Abstand 390 px (Median) | davon < 16 px |
|---|---:|---:|---:|---:|---:|
| Neuer Patient | 24 | 14 | 13 | 14 | 18 |
| Stammdaten-Dialog | 19 | 12 | 17 | 12 | 18 |
| Kontakt | 4 | 16 | 0 | 12 | 2 |
| Gewicht | 3 | – | – | 12 | 2 |
| Termin | 6 | 16 | 0 | 16 | 0 |
| Diagnose | 5 | 16 | 0 | 16 | 2 |
| Medikament | 14 | 16 | 2 | 12 | 8 |
| Labor | 3 | – | – | 12 | 1 |
| BIA | 8 | 12 | 4 | 12 | 5 |
| Versorger (neu) | 8 | **8** | 7 | **8** | 7 |
| Arzt (neu) | 10 | **8** | 9 | **8** | 9 |
| Benutzer anlegen | 9 | 16 | 3 | 12 | 6 |
| Vorlagen › Briefkopf | 9 | 12 | 8 | 12 | 8 |
| Vorlagen › Grenzwerte | 30 | 12 | 21 | 12 | 21 |
| Anmeldung | 2 | 16 | 0 | 16 | 0 |

Weitere Befunde:

- **Neuer Patient › Nickelallergie**: Zwischen Frage (`legend`) und Optionen lagen 16 px, so viel wie zwischen zwei
  Feldern. Die Frage wirkte losgelöst.
- **Neuer Patient › Diagnose**: Zwischen Bezeichnung und Textfeld lagen 12 px.
- Die 27–29 px bei „Dosierung“ (Medikament) und „Berechtigungen je Firma“ (Benutzer) waren ein Messfehler: Das Skript
  hatte bis zum ersten Eingabefeld gemessen. Bis zu den Unterbezeichnungen sind es 4–6 px, das ist in Ordnung.
- Die Abschnittstitel („Person“, „Betreuung“ …) stehen in eigenen Karten. Die Karte trennt die Abschnitte, deshalb gibt
  es dort kein Nähe-Problem.

### Änderungen

Die Änderungen sind **zentral** in `frontend/src/index.css` umgesetzt:

- Neue Variable `--feld-abstand`: **16 px** bei normaler Dichte, 20 px bei „Großzügig“, 12 px bei „Kompakt“ und 10 px
  bei „Sehr kompakt“. Auch die kompakten Stufen liegen beim 3- bis 4-Fachen des Label-Abstands. Wer „Kompakt“ wählt,
  will bewusst mehr auf dem Schirm sehen.
- Neue Regel `:is(.grid, .flex-col):has(> .feld, > :is(div, fieldset) > .feld)`: Sie setzt `row-gap` auf
  `--feld-abstand`. Größere Abstände (`gap-4` und mehr) und `.formular` sind ausgenommen. Die Regel steht ohne
  `@layer`, deshalb übersteuert sie `gap-2`, `gap-3` und `gap-y-3.5`. Dafür musste kein einzelnes Formular angefasst
  werden.
- `.formular` (Versorger, Ärzte): Am PC steigt der Abstand von 8 auf **12 px** (4× Label-Abstand), am Telefon auf
  16 px. Am PC bleiben es 12 statt 16 px wegen des Wunschs vom 08.10.2026, dass alles ohne Scrollen auf 1080p passt.

Einzeln in `frontend/src/seiten/PatientNeu.tsx`:

- Nickelallergie: `legend` mit `mb-0.5`, Optionen mit `py-1` statt fester `h-9`. Bis zu den Optionen sind es jetzt
  6 px statt 16 px.
- Diagnose: In der Karte steht `gap-1.5` statt `gap-3`. Das Label sitzt jetzt 6 px über dem Textfeld statt 12 px.

### Ergebnis (nachher)

| Formular / Dialog | Label-Abstand | Feld-Abstand 1440 px | < 16 px | Feld-Abstand 390 px | < 16 px |
|---|---:|---:|---:|---:|---:|
| Neuer Patient | 3 (max. 6) | 16 | 0 | 16 | 0 |
| Stammdaten-Dialog | 3 | 16 | 0 | 16 | 0 |
| Kontakt, Termin, Diagnose, Gewicht, Labor | 3 | 16 | 0 | 16 | 0 |
| Medikament | 3 (Gruppe 6) | 16 | 0 | 16 | 0 |
| BIA | 3 | 16 | 0 | 16 | 0 |
| Versorger, Arzt | 3 | **12** (bewusst) | 7 / 9 | 16 | 0 |
| Benutzer anlegen | 3 (Gruppe 4) | 16 | 0 | 16 | 0 |
| Vorlagen › Briefkopf, › Grenzwerte | 3 | 16 | 0 | 16 | 0 |
| Anmeldung | 3 | 16 | 0 | 16 | 0 |

Das Verhältnis von Feld-Abstand zu Label-Abstand liegt jetzt bei **5,3** (vorher 2,7–4,7). Bei Versorger und Arzt am
PC ist es 4,0. Konto und Design enthalten fast nur Umschalter (`Segmente`) und keine `.feld`-Felder. Sie wurden auf
den Bildschirmfotos angesehen, und dort war nichts auffällig.

---

## 2. Hick'sches Gesetz

### Gezählte Wahlmöglichkeiten (vorher)

| Ort | Admin | Mediziner | Mitarbeiter | Bemerkung |
|---|---:|---:|---:|---|
| Hauptnavigation | 8 | 8 | 8 | Start, Patienten, Kalender, Infusionspläne, Versorger, Ärzte, Datenschutz, Scans |
| Administration (Seitenleiste) | 1 (klappt auf: 6) | 2 | 1 | ab 3 Seiten schon als Gruppe zum Aufklappen (F181) |
| Kacheln der Startseite | 8 (Verwaltung) | 7 (klinisch) | 7 (klinisch) | je Rolle sinnvoll getrennt, alles unter „Startseite anpassen“ ein- und ausblendbar |
| Reiter der Akte | 13 | 13 | 13 | in drei Gruppen: 7 Behandlung · 4 Befunde (kleiner) · 2 Weiteres (klein, am Ende) |
| Aktionen im Aktenkopf | 5 + „⋯“ | 5 + „⋯“ | 4 + „⋯“ | Kontakt, Gewicht, Termin, Dokument, Neuer Plan |
| Menü „⋯“ der Akte | 6 | 6 | 6 | Stammdaten, Firmen, PDF, Sprechstunde, Schreiben, Abschließen |
| Neuer Patient: sichtbare Felder | 24 | 24 | 24 | 4 Abschnitte + Diagnose |

Eine Betrachter-Rolle gibt es unter den freigegebenen Testkonten nicht. Laut Code sieht sie dieselbe
Hauptnavigation ohne Datenschutz und Scans.

### Entscheidungen

**Geändert: Neuer Patient** (`frontend/src/seiten/PatientNeu.tsx`)

- **Telefon 2, E-Mail, Versicherungsart, Versicherung und Versichertennummer** stehen jetzt unter „Weitere Angaben:
  Telefon 2, E-Mail, Versicherung (optional)“ (`<details>`, `data-testid="neu-weitere-angaben"`). Beim Anlegen sind
  diese Angaben selten zur Hand. Sie lassen sich jederzeit über den Stammdaten-Dialog ergänzen.
  - Die Zeile zeigt, wie viele Felder schon ausgefüllt sind, z. B. „(1 ausgefüllt)“. So bleibt nichts unbemerkt
    versteckt.
  - Der Bereich **öffnet sich von selbst**, wenn dort ein Fehler steht (z. B. ungültige E-Mail vom Server). Danach
    springt der Fokus wie bisher auf das erste rote Feld. Das wurde mit Playwright geprüft: Der Server antwortete 400
    (`email`), der Bereich ging auf, und das Feld war sichtbar.
  - Ergebnis: Beim Öffnen stehen **19 statt 24 Felder** im Blick. Pflichtfelder und Kerndaten (Person, Anschrift,
    Telefon, Betreuung) bleiben offen.
- **Telefon**: Am Ende des Formulars steht ein zweites Paar „Abbrechen“ / „Anlegen und Akte öffnen“. Es ist nur
  unter 768 px sichtbar (`md:hidden`, `data-testid="neu-unten"`). Vorher musste man nach ca. 20 Feldern ganz nach oben
  zurückscrollen. Am PC gibt es weiter nur den Knopf oben. Die e2e-Tests (Desktop) finden ihn eindeutig.
- **Keine Schritte (Wizard)**: Mit 3 Pflichtfeldern ist ein mehrstufiger Ablauf unnötig. Er würde die schnelle Anlage
  (Name, Vorname, Geburtsdatum → Anlegen) verlangsamen und Rückwege nötig machen. Die Gliederung in Abschnittskarten
  plus Einklappen genügt.
- `frontend/e2e/patienten.spec.ts` („Neuer Patient …“) braucht **keine Änderung**. Der Test füllt nur Felder aus,
  die offen bleiben.

**Bewusst nicht geändert**

- **Reiter der Akte (13)**: Hier gibt es keinen Menüpunkt „Mehr ▾“. Gründe:
  1. „Jeder Bereich ein eigener Reiter“ ist eine ausdrückliche Festlegung (F121, Wunsch vom 07.10.2026).
  2. Die Reiter sind schon nach Häufigkeit gegliedert: Behandlung groß vorn, Befunde und Unterlagen kleiner hinter
     einem Trenner, Verlauf und Datenschutz klein am Ende. Das ist die Gruppierung, die Hick empfiehlt (Chunking).
  3. Alt+1…0 und die Muskelerinnerung bleiben so erhalten.
  4. Rund 15 e2e-Tests klicken „Verlauf“ und „Datenschutz“ direkt als Link in „Aktenbereiche“ an.

  Am Telefon wischt die Leiste seitlich: gemessen `scrollWidth` 1280 bei `clientWidth` 359, `overflow-x: auto`, der
  aktive Reiter wird in die Mitte geholt. Das funktioniert. Bei 1440 px rutschen „Verlauf“ und „Datenschutz“ in eine
  zweite Zeile. Das ist eine Schönheitsfrage, siehe Empfehlungen.
- **Seitenleiste**: 8 Einträge liegen im Rahmen. Die Administration ist schon eingeklappt (F181).
- **Startseite**: 7 klinische bzw. 8 Verwaltungs-Kacheln, je Rolle getrennt (`accounts/api.py`, `KARTEN`). Jede Kachel
  lässt sich unter „Startseite anpassen“ ausblenden. Andere Standards hätten die Startseiten bestehender Konten
  verändert und `patienten.test_startseite` berührt. Ein Nutzen ist ohne Nutzungsdaten nicht belegt.
- **Aktenkopf**: 5 Hauptaktionen plus „⋯“ mit 6 Einträgen sind gut gewählt. Die häufigen Aktionen stehen außen,
  seltene im Menü.
- **Stammdaten-Dialog (19 Felder)**: Das ist ein Bearbeitungsdialog. Wer ihn öffnet, sucht gezielt ein Feld. Wäre
  etwas eingeklappt, müsste man suchen.

---

## 3. Lesbarkeit (Flesch nach Amstad) und Überfliegbarkeit

### Methode

FRE = 180 − ASL − 58,5 × ASW. ASL ist die Zahl der Wörter je Satz, ASW die Zahl der Silben je Wort. Silben werden als
Vokalgruppen gezählt (`[aeiouyäöü]+`), damit ie, ei, au, eu, äu und ai als eine Silbe gelten. Sätze enden an `. ! ? : ;`
und an Absatz- bzw. Listenenden. Abkürzungen wie „z. B.“ oder „bzw.“ sind geschützt. Gemessen wurden:

- **Hilfe**: alle 66 Abschnitte aus `backend/hilfe/inhalt.py`, HTML und Bilder entfernt,
- **Oberfläche**: `hinweis=`-Props sowie Text in `<Meldung>` und `<Leer>` aus `frontend/src` (169 Texte mit
  mindestens 6 Wörtern),
- **Server**: Texte von `ValidationError`, `PermissionDenied`, `detail` und `…Fehler` in den Backend-Modulen ohne
  Tests und Migrationen (90 Texte).

Zur Einordnung: Für kurze Meldungen (1–2 Sätze) ist die Formel wenig aussagekräftig. Ein einziges Fachwort wie
„Zwei-Faktor-Anmeldung“ oder „Dokumentvorlage“ drückt den Wert um 10–20 Punkte, obwohl die Nutzer das Wort kennen.
Bei diesen Texten zählte deshalb vor allem: Satzlänge ≤ 15 Wörter, aktive Sprache, eine Aussage je Satz und ein
klarer nächster Schritt.

### Verteilung vorher → nachher

| Bereich | Anzahl | Median FRE | < 30 | 30–50 | 50–60 | ≥ 60 | Sätze > 15 Wörter |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hilfe vorher | 66 | 58,0 | 0 | 10 | 30 | 26 | 166 von 826 (20 %) |
| Hilfe nachher | 66 | 58,8 (Mittel 59,9) | 0 | **2** | 35 | 29 | **136 von 943 (14 %)** |
| Oberfläche vorher | 169 | 64,7 | 6 | 62 | – | 101 | – |
| Oberfläche nachher | 169 | 64,7 | 4 | 63 | – | 102 | – |
| Server vorher | 90 | 67,5 | 4 | 25 | – | 61 | – |

### Die 15 schwächsten Hilfeabschnitte (vorher) und was geschah

| Abschnitt | FRE vorher | FRE nachher | Wörter/Satz | lange Sätze | Änderung |
|---|---:|---:|---|---|---|
| import | 34,9 | 48,6 | 8,0 → 4,4 | 0 → 0 | 4 Schritte als nummerierte Liste |
| passkey | 38,8 | 44,2 | 9,2 → 7,7 | 4 → 0 | Einrichten als Schritte, Voraussetzungen als Liste, „Gerät verloren?“ fett |
| admin_start | 41,3 | 57,1 | 6,6 → 5,9 | 1 → 0 | Kacheln je Punkt, Bedingungen als eigene Sätze |
| systemverwaltung | 43,0 | 54,2 | 15,0 → 7,2 | 2 → 1 | Ampel-Prüfungen und SSH-Regeln als Listen |
| erklaerungen | 46,0 | 54,4 | 12,2 → 6,2 | 1 → 0 | Ablauf Drucken → Unterschreiben → Erfassen als Liste |
| loeschen | 46,8 | 60,5 | 17,3 → 8,4 | 2 → 0 | ein Gedanke je Satz |
| schreiben | 47,3 | 52,1 | 10,9 → 6,8 | 4 → 0 | drei Schreiben als Liste, Abschnitt „Texte ändern“ |
| stammdaten | 48,3 | 56,2 | 10,6 → 7,6 | 1 → 1 | zwei Wege als Liste, Diagnosen und Therapie getrennt |
| anmelden | 48,8 | 51,6 | 9,9 → 7,5 | 3 → 0 | 2FA erklärt, Bestätigungen in eigenem Absatz |
| system | 48,8 | 56,8 | 13,0 → 7,2 | 13 → 5 | eine Textwand in Zwischenüberschriften je Reiter gegliedert, mit Listen |
| design | 50,6 | 58,2 | 12,4 → 6,6 | 2 → 0 | Einstellungen als Liste |
| notfall | 50,6 | 50,6 | – | – | nicht geändert (≥ 50) |
| audit | 50,9 | 50,9 | – | – | nicht geändert (≥ 50) |
| gewicht_verlauf | 52,2 | 74,6 | 21,0 → 6,9 | 2 → 0 | drei Orte der Warnung als Liste |
| gewicht | 52,8 | 64,5 | 15,3 → 6,9 | 2 → 0 | fünf Wege zum Dialog als Liste, Korrektur als Liste |

Ziel FRE ≥ 50: Das erreichen jetzt 64 von 66 Abschnitten (vorher 56). Unter 50 bleiben zwei:

- **passkey (44)**: Die Menüpfade von Windows, iOS und Android („Stammzertifizierungsstellen“,
  „Zertifikatsvertrauenseinstellungen“) sind wörtliche Bildschirmtexte und müssen so bleiben.
- **import (48,6)**: Der Abschnitt hat nur 35 Wörter mit Fachbegriffen (Übernahme, Altdokumente).

Die Bedeutung ist unverändert, und keine Information ist weggefallen. Titel, `id`, `seiten`, Bilder und Links sind
gleich geblieben. Die Tests prüfen Titel und IDs, nicht den Fließtext. Der HTML-Stil bleibt `<p>`, `<ul>/<ol><li>` und
`<strong>`.

### Oberfläche und Server: umgeschriebene Texte

| Text (Datei) | FRE vorher | FRE nachher | Wörter/Satz |
|---|---:|---:|---|
| Leer „Wiedereinbestellung“ (`seiten/start/kacheln.tsx`) | 41,4 | 52,1 | 11,0 → 6,0 |
| „Noch kein Sicherungs-Passwort …“ (`seiten/admin/Backup.tsx`) | 29,6 | 52,0 | 10,0 → 6,5 |
| Hinweis „Aufbewahrung im Ziel“ (`seiten/admin/Backup.tsx`) | 47,3 | 65,1 | 9,5 → 6,7 |
| „Ohne Zeitsynchronisation …“ (`seiten/admin/SystemWartung.tsx`) | 38,8 | 43,0 | 12,0 → 8,3 |
| „Auf Version … zurückschalten“ (`seiten/admin/SystemWartung.tsx`) | 43,2 | 49,8 | 13,0 → 6,5 |
| „Alle abmelden“ (`seiten/admin/System.tsx`) | 15,0 | 47,5 | 5,5 → 6,5 |
| Akte endgültig löschen (`seiten/akte/Datenschutz.tsx`) | 45,3 | 54,1 | 14,8 → 8,9 |
| Dokument endgültig löschen (`seiten/akte/Dokumente.tsx`) | 48,8 | 53,0 | 11,7 → 9,2 |
| Server: Freigabevermerk fehlt (`backend/infusionen/models.py`) | 36,3 | 41,1 | Aussage zuerst („In … fehlt …“) |
| Server: Einschränkung nur bei abgeschlossener Akte (`backend/patienten/datenschutz.py`) | 53,5 | 65,1 | 9,5 → 6,7 |
| Server: Ansprechpartner passt nicht (`backend/patienten/models.py`) | 37,5 | 41,5 | jetzt mit Handlung: „Bitte einen passenden wählen.“ |

Gegen die Tests geprüft: Alle Ausgangstexte wurden in `backend/**/test*.py` und `frontend/e2e` gesucht. Nur
„Noch kein Sicherungs-Passwort“ wird geprüft (`e2e/zzz-sicherung.spec.ts`). Dieser Satzanfang bleibt wörtlich
erhalten. `patienten/test_datenschutz.py` prüft nur, dass „Freigabevermerk“ vorkommt, und das tut es weiterhin.

Bewusst nicht geändert:

- **„Für diese Bestätigung ist die Zwei-Faktor-Anmeldung nötig …“**: Eine Umformulierung senkte den FRE (35,8 → 31,9).
  Sie wurde zurückgenommen.
- **„Die Datei fehlt im Dokumentenverzeichnis …“** (4 Stellen): Der Begriff ist einheitlich und für die
  Administration gemeint.
- **Kurze Meldungen mit niedrigem FRE**, aber nur einer Aussage und ≤ 10 Wörtern, z. B. „Erledigte Termine können
  nicht geändert werden.“ Ein kürzerer Satz geht kaum. Ein niedriger Wert liegt hier nur an Fachwörtern.
- **`backend/accounts/api.py`** (Meldung zu Testbenutzern): Die Datei wurde gleichzeitig an anderer Stelle bearbeitet
  (Firmenrollen). Sie wurde nicht angefasst, um Konflikte zu vermeiden. Siehe Empfehlungen.

---

## 4. Tests

- `npx tsc --noEmit -p .` (frontend): ohne Fehler.
- `manage.py test --noinput hilfe infusionen patienten` (DB `epm_ux`): siehe Ergebnis im Bericht an den Auftraggeber.
- Ablauf „Neuer Patient“ mit eigenem Playwright-Skript nachgestellt, ohne `e2e.sh` und ohne angelegten Patienten:
  1. Pflichtfehler erscheinen.
  2. Der Bereich „Weitere Angaben“ ist zu Beginn zu.
  3. Er zählt Ausgefülltes.
  4. Bei einem Serverfehler zur E-Mail (400) öffnet er sich von selbst.
  5. Am PC ist genau ein Knopf „Anlegen und Akte öffnen“ sichtbar, am Telefon zwei.

## 5. Bildschirmfotos

Sie liegen im Scratchpad unter `ux/` (nicht im Repo):

- `vorher-` und `nachher-neuer-patient-1440.png` / `-390.png` (ganze Seite)
- `nachher-neu-zu-1440.png` / `-390.png`: Weitere Angaben zugeklappt, Knopf unten am Telefon
- `nachher-neu-fehler-1440.png`: Bereich offen nach Serverfehler
- `vorher-` und `nachher-stammdaten-1440.png` / `-390.png`, `…-kontakt-…`, `…-termin-…` (Dialoge)
- `vorher-akte-1440.png`, `-1024.png`, `-390.png` und `vorher-akte-menue-*.png` (Reiter und Menü „⋯“, unverändert)

## 6. Empfehlungen (offen)

1. **Test mit fünf Personen** (je zwei Pflege, zwei Verwaltung, eine ärztliche Person), Aufgaben am Tablet:
   - Patient anlegen,
   - Versicherung nachtragen (Wird „Weitere Angaben“ gefunden?),
   - Kontakt mit Gewicht erfassen,
   - Verlauf einer Akte öffnen.

   Messen: Zeit, Fehlklicks, Rückfragen. Erst danach über weitere Einklappungen entscheiden.
2. **Reiter der Akte bei 1280–1500 px**: „Verlauf“ und „Datenschutz“ brechen in eine zweite Zeile um. Möglich wäre,
   die Gruppe „Weiteres“ erst unterhalb einer Breite in ein „⋯“ zu falten, oder die Innenabstände der Reiter
   zwischen 1280 und 1600 px zu verringern. Das muss mit F121 und den e2e-Tests abgestimmt werden.
3. **Nutzungsdaten der Startkacheln** (welche werden ausgeblendet?) abwarten, bevor Standards geändert werden.
4. **Fehlerzustand im Formular „Neuer Patient“**: Rote Pflichtfehler bleiben stehen, bis erneut „Anlegen“ gewählt
   wird, auch wenn das Feld schon ausgefüllt ist. Besser wäre, den Fehler beim Tippen zu löschen.
5. **Django-Standardmeldungen** in der Du-Form, z. B. „Gib eine gültige E-Mail Adresse an.“, passen nicht zum Sie bzw.
   zum unpersönlichen Stil von EPM. Empfehlung: eigene `error_messages` für E-Mail, Zahl und Datum („Bitte eine gültige
   E-Mail-Adresse eingeben.“).
6. **Weitere Hilfeabschnitte** mit vielen langen Sätzen, obwohl FRE ≥ 50: `benutzer` (7 von 27 Sätzen),
   `dokumentvorlagen` (8 von 20), `kalender` (5 von 12), `notfall` (4 von 18). Diese ebenfalls in Listen gliedern.
7. Meldung zu Testbenutzern in `backend/accounts/api.py` (FRE 28) kürzen, sobald die Firmenrollen-Arbeiten dort
   abgeschlossen sind.
