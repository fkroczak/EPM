# Bedienbarkeit für Pflegekräfte (10.10.2026)

**Auftrag:** EPM soll von Personen ohne nennenswerte IT-Erfahrung, aber mit mehreren Jahren Erfahrung als
Krankenschwester, intuitiv bedient werden können.

**Vorgehen:** Die Alltagswege einer Pflegekraft im Code und in der laufenden Anwendung durchgegangen (Testkonto mit der
Rolle Mitarbeiter, PC 1440 px und Telefon 390 px): Anmelden → Startseite → Patient suchen/öffnen → Neuer Patient → Akte
(Übersicht, Kontakte, Dokumente, Therapie) → Kontakt erfassen → Dokument ablegen → Hilfe. Abgeglichen mit
`docs/WUENSCHE-PRAXIS-2026-10-06.md`, `docs/RUECKFRAGEN-ALICE-2026-10-06.md` und der Historie (F139–F171: einheitliche
Knöpfe, Rückfragen, Rückmeldungen als Overlay, „Ein Dialog je Sache“, „Weniger Wege“ usw. sind schon umgesetzt und
wurden nicht angetastet).

**Abgrenzung:** Startseite, Kalender, Termin-/Ankündigungs-/Schreiben-Dialoge und Einstellungen baut ein anderer
Entwickler. Akte, Navigation und Infusionspläne werden seit heute parallel strukturell überarbeitet – dort habe ich
nur fertige Textkorrekturen gemacht; Ideen dazu stehen unten als Empfehlungen.

Gesamteindruck: Die Grundlage ist gut – einheitliche Knöpfe, Bestätigungsdialoge vor dem Löschen, grüne/rote
Rückmeldung nach dem Speichern, Hilfe zu jeder Seite. Die Lücken liegen vor allem dort, wo **etwas nicht klappt**:
Fehlermeldungen ohne Lösungsweg, leere Listen ohne nächsten Schritt, Knöpfe, die grau sind, ohne zu sagen warum, und
strenge Eingabeformate.

## Befunde

Schwere: **hoch** = hält die Arbeit auf oder führt zu Fehlern · **mittel** = verunsichert, kostet Zeit · **gering** = Schönheitsfehler.

| Stelle | Problem | Schwere | umgesetzt |
|---|---|---|---|
| Alle Datumsfelder | Nur „TT.MM.JJJJ“ wurde verstanden; „14,3,68“ (Komma vom Ziffernblock), „14031968“ oder „heute“ gaben einen Fehler | hoch | ja |
| Kontakt erfassen | „Speichern“ grau, ohne Hinweis warum (Patient fehlt / Notiz leer) | hoch | ja |
| Kontakt erfassen | Uhrzeit nur als „10:30“; Fehler erschien am Feld *Datum* | mittel | ja |
| Ganze Anwendung | Ohne Netz/VPN erschien die englische Browsermeldung „Failed to fetch“; Serverfehler nur als „Fehler 500/502“ | hoch | ja |
| Anmeldung | „Benutzername oder Kennwort falsch.“ ohne Hinweis auf Feststelltaste und Sperre nach fünf Versuchen; kein Hinweis bei eingeschalteter Feststelltaste | mittel | ja |
| Anmeldung, Code | „Code ungültig.“ ohne Hinweis, dass der Code alle 30 Sekunden wechselt | mittel | ja |
| Neuer Patient | Bei fehlenden Pflichtfeldern keine Zusammenfassung; das rote Feld konnte außerhalb des Bildschirms liegen; nach dem Anlegen keine Bestätigung | mittel | ja |
| Patientenliste | Ohne Treffer nur „Keine Patienten passen zu diesen Filtern.“ – kein Suchtipp, kein Weg zu abgeschlossenen Akten oder „Neuer Patient“ (am Telefon gar kein Knopf) | hoch | ja |
| Patientenauswahl in Dialogen | Bei einem Zeichen passiert nichts; „Kein Patient gefunden.“ ohne Tipp und ohne Hinweis, dass abgeschlossene Akten fehlen | mittel | ja |
| Akte › Dokumente | Leere Liste ohne Hinweis, wie man ablegt; „1 Dokumente“ | gering | ja |
| Akte › Dokumente, Text erkennen | Rückfrage spricht von „PDF/A mit unsichtbarer Textebene“; „Audit-Log“ im Text für die Pflege | mittel | ja |
| Scans | „gelesen mit PP-OCR + Tesseract“, „Nur mit Tesseract erkannt … (Speichergrenze)“ | gering | ja (Namen im Tooltip) |
| Menüs „⋯“ | Nur ein Symbol; Name nur für Screenreader | mittel | teilweise (Tooltip) |
| Hilfe | Kein Einstieg „Wie mache ich …“; Anmelden-Abschnitt sprach von „Kennwort“ und „Anmelden“, die Oberfläche von „Passwort“ und „Weiter“; Dokumente-Abschnitt nannte „Datei auswählen“ statt „Neues Dokument“ | mittel | ja |
| Hilfe | Zweizeilige Einträge im Inhaltsverzeichnis überlappten sich | mittel | ja |
| Formatierter Text (Notizen, Hilfe) | Aufzählungen ohne Punkte/Nummern, obwohl der Editor „• Liste“ anbietet | mittel | ja |
| Aktenkopf | „Dokument hochladen“ versteckt unter „⋯ Weitere Aktionen“, obwohl es Alltag ist | hoch | nein – Empfehlung (Akte wird umgebaut) |
| Telefon-Leiste | Knopf heißt „Notiz“, der Dialog „Kontakt erfassen“ – zwei Wörter für dieselbe Sache | mittel | nein – Empfehlung (Navigation wird umgebaut) |
| Kopfzeilen-Suche | Ohne Treffer kein Angebot „Neuer Patient“, kein Hinweis bei nur einem Zeichen | mittel | nein – Empfehlung (Navigation) |
| Akte › Diagnosen/Therapie | „Version 1, Version 2“ statt „Fassung“ (sonst überall „Fassung“) | gering | nein – Empfehlung |
| Akte › Kontakte | „Ansprechp.“ abgekürzt | gering | nein – Empfehlung |
| Akte nicht gefunden | Nur die Fehlermeldung, kein Weg zurück | gering | nein – Empfehlung |
| Dialoge mit viel Inhalt | „Speichern“ steht unten außerhalb des Bildschirms (z. B. „Kontakt erfassen“ auf einem 900-px-Bildschirm) | mittel | nein – Empfehlung |
| Ganze Anwendung | „Passwort“ und „Kennwort“ gemischt (Anmeldung/Konto: Passwort; Hilfe, Löschen, Benutzer: Kennwort) | gering | ja – Backend, Hilfe, Anmeldung; Administration und Akte folgen beim Abgleich |
| Fachbegriffe | „BIA“, „Entwurf“, „Wiedervorlage“ ohne Erklärung | mittel | ja – Erklärung beim Draufzeigen (Baustein `Begriff`); Einbau in Akte, Administration und Infusionspläne folgt beim Abgleich |

## Was umgesetzt wurde (F178)

1. **Nachsichtige Eingaben.** Datum überall auch als „14.3.68“, „14,3,68“, „14/3/1968“, „14-3-1968“, „14031968“,
   „140368“, „heute“, „gestern“. Uhrzeit im Kontaktdialog auch als „10.30“, „1030“, „930“, „10 Uhr“.
2. **Sagen, was fehlt.** Neben dem grauen „Speichern“ im Kontaktdialog steht, was noch fehlt. „Neuer Patient“ zeigt
   oben „Noch nicht angelegt: 3 Felder sind rot markiert …“, springt zum ersten roten Feld und bestätigt danach
   „Beispiel, Paula angelegt (Nr. 0001). Die Akte ist geöffnet.“
3. **Fehlermeldungen mit Lösungsweg.** „Keine Verbindung zu EPM. Bitte Netzwerk bzw. VPN prüfen … die Eingaben bleiben
   stehen.“, „EPM ist gerade nicht erreichbar – vermutlich wird es neu gestartet oder aktualisiert …“, Serverfehler mit
   der Bitte, der Administration Uhrzeit und Vorgang zu nennen; Datei zu groß mit Grenze. Anmeldung mit Hinweis auf
   Feststelltaste und Sperre, Feststelltaste wird beim Tippen angezeigt.
4. **Leere Listen mit nächstem Schritt.** Patientenliste: Suchbegriff, Tipp („nur einen Teil des Namens …“), Knöpfe
   „Alle Filter entfernen“, „In abgeschlossenen Akten suchen“, „Neuer Patient“ – am PC und am Telefon. Patientenauswahl
   und Dokumente entsprechend.
5. **Weniger Fachjargon** in den Texten für die Pflege (PDF/A, Audit-Log, Programmnamen der Texterkennung).
6. **Hilfe:** „Die wichtigsten Wege im Alltag“ (Patient suchen, Kontakt, Gewicht, Termin, Dokument, Neuer Patient,
   grün/rot) und „Wenn etwas nicht klappt“ (grauer Knopf, rotes Feld, Datumsformate, nicht gefunden, keine Verbindung,
   Konto gesperrt, versehentlich gespeichert) ganz oben; Texte an die Oberfläche angeglichen; Überlappung behoben.
7. **Aufzählungen** in Notizen und Hilfe zeigen wieder Punkte und Nummern.

Geprüft: `npm ci`, `npm run typecheck`, `npm run build` grün; Backend-Tests der App `accounts` (enthält `/api/hilfe/`)
grün; Bildschirmfotos vorher/nachher der Seiten oben am PC und am Telefon. Die Browsertests (Playwright gegen den
vollständigen Stack) sind hier nicht gelaufen – keine geänderte Beschriftung wird dort abgefragt, der Lauf steht aber aus.

## Empfehlungen und Rückfragen für später

**Für den Umbau von Akte und Navigation (bitte an den zuständigen Entwickler):**

- **„Dokument“ als eigener Knopf im Aktenkopf** neben Kontakt/Gewicht/Termin, statt unter „⋯ Weitere Aktionen“.
  Allgemein: „⋯“ nur für Seltenes (PDF, Abschließen); bei breitem Bildschirm den Namen „Weitere Aktionen“ sichtbar.
- **Ein Wort je Sache:** Telefon-Leiste „Notiz“ → „Kontakt“ (der Dialog heißt „Kontakt erfassen“); „Version“ →
  „Fassung“ in Diagnosen/Therapie; „Ansprechp.“ ausschreiben.
- **Kopfzeilen-Suche:** bei einem Zeichen „mindestens zwei Zeichen“, ohne Treffer „Neuer Patient“ und
  „In abgeschlossenen Akten suchen“ anbieten (wie jetzt in der Patientenliste).
- **„Akte nicht gefunden“** mit Link zur Patientenliste.
- **Weniger Reiter auf einmal:** 12 Reiter (Übersicht … Verlauf) sind für Gelegenheitsnutzer viel. Vorschlag: die
  fünf häufigsten (Übersicht, Kontakte, Dokumente, Infusionspläne, Labor) vorn, der Rest unter „Mehr“ – Rücksprache
  mit Alice, da F121 bewusst „jeder Bereich ein Reiter“ festgelegt hat.

**Gemeinsame Bausteine (größer, mit Rücksprache):**

- **Fuß der Dialoge festhalten:** Bei langen Dialogen (Kontakt mit Gewicht und Wiedervorlage) rutscht „Speichern“ aus
  dem Bild. Ein am unteren Rand stehender Fuß würde das lösen; berührt alle Dialoge, daher nicht nebenbei.
- **Datumsauswahl per Kalender** zusätzlich zum Textfeld (Klick aufs Feld) – heute nur Tippen. Ohne neue Bibliothek mit
  `<input type="date">` machbar, ändert aber das Aussehen aller Datumsfelder; erst ausprobieren lassen.
- **Schriftgröße/Kontrast:** Unter Design gibt es Dichte und Farben; eine Stufe „große Schrift“ (z. B. 115 %) wäre für
  ältere Augen und Tablets hilfreich.
- **Klickflächen am Tablet:** Chips der Schnellfilter (30 px) und kleine Knöpfe (32 px) liegen unter den empfohlenen
  44 px; am Telefon ist das schon vergrößert, am Tablet im Querformat nicht.

**Rückfragen an den Auftraggeber (beantwortet am 10.10.2026):**

1. **„Passwort“ oder „Kennwort“?** – **entschieden: ja, umgesetzt („Passwort“ überall).** Alle Meldungen und Texte
   des Backends (Anmeldung, Konto, Bestätigungen, Audit-Texte, Hilfe, Befehle für die Einrichtung), die Anmeldung und
   die Browsertests sagen „Passwort“. Feld- und Variablennamen, API-Felder, Modelle und Migrationen bleiben. Noch offen,
   weil dort gerade umgebaut wird: Administration (Benutzer, System, Backup, Import), Akte (Löschen-Dialoge),
   Startseite der Administration, Zugangsblatt (`backend/vorlagen/listen.py`) und die Bezeichnungen in
   `audit/models.py` und `accounts/models.py` (brauchen eine Migration).
2. **Fachbegriffe erklären?** – **entschieden: ja, umgesetzt.** Neuer Baustein `components/ui/Begriff.tsx`: gepunktet
   unterstrichen, Erklärung bei Maus-Hover, Tastaturfokus und Antippen, für Screenreader per `aria-describedby`.
   Die Texte stehen an einer Stelle in `lib/begriffe.ts`: BIA, Entwurf, BMI, PE (parenterale Ernährung), Wiedervorlage,
   Wiedereinbestellung, GLIM, Testpatient, storniert. Eingebaut in Patientenliste (Entwurf, Testpatient),
   „Kontakt erfassen“ (Wiedervorlage) und Scans (BIA); Akte, Infusionspläne, Startseite und Administration folgen beim
   Abgleich.
3. **Einweisung:** Eine einseitige Kurzanleitung zum Ausdrucken – **entschieden: nein.**
