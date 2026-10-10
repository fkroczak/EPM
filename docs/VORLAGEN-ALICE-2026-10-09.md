# Vorlagen von Alice – was daraus geworden ist (09.10.2026)

Alice hat ihre Vorlagen geschickt; Filip wünscht sich PDFs mit Patientenname nach Bedarf und vorbereitete E-Mails mit
Anhang. Umsetzung: F172–F177 in `docs/BACKEND-FUNKTIONEN.md` (Infoblatt an die Praxis: F177, 10.10.2026).

| Vorlage von Alice | in EPM | wo |
|---|---|---|
| Patientenaufnahme (welche Unterlagen wir brauchen) | Dokumentvorlage „Patientenaufnahme“ + E-Mail-Text | Akte › ⋯ › Schreiben und E-Mail |
| – (neu gewünscht) Terminbestätigung Sprechstunde | Dokumentvorlage „Terminbestätigung“: Adresse Dr. Holtmeier, Gesundheitskarte mitbringen, keine Überweisung nötig | Akte › ⋯ › Schreiben und E-Mail (Termin wählen) |
| Reisebescheinigung (Briefkopf Dr. Holtmeier) + ADAC-Packliste | Dokumentvorlage „Reisebescheinigung“; das ADAC-Attest hängt als zweite Seite an, Name/Ort/Datum/Reisedauer eingetragen | Akte › ⋯ › Schreiben und E-Mail |
| Patientenankündigung (monatlich angepasst) | „Infoblatt an die Praxis“ (F177): ein Blatt mit allen Patienten, die in der Praxis Holtmeier einen Termin haben – Zeitraum per Knopf (nächste/übernächste Woche, nächster Monat, eigener), Vorschau mit „neu“, Warnung bei Terminen ohne Ort, Erinnerung auf der Startseite; Text in der Dokumentvorlage „Patientenankündigung“ | Kalender › Praxis informieren (oder Startseite › Infoblatt erstellen) |
| Fallzusammenfassungen von Markus | Berichtsart „Fallzusammenfassung“ mit Knopf „Gliederung einfügen“ (12 Abschnitte) | Akte › Berichte › Neuer Bericht |
| Zottentraining, Handlungsempfehlung TauroLock, Blutuntersuchung | Anlagen, beim Schreiben an die E-Mail anhängbar | Vorlagen › Anlagen für E-Mails |

**So funktioniert die E-Mail:** „E-Mail vorbereiten“ lädt eine `.eml`-Datei. Doppelklick öffnet sie in Outlook als
fertigen Entwurf mit Empfänger, Betreff, Text und PDF im Anhang – prüfen und „Senden“. Betreff und Text stehen im
Baustein „E-Mail“ der jeweiligen Dokumentvorlage (Vorlagen › Dokumentvorlagen) und lassen sich dort dauerhaft bzw. im
Dialog für die eine E-Mail ändern.

**Eigene Vorlagen:** Vorlagen › Dokumentvorlagen › „+ Neue Vorlage“ legt ein weiteres Schreiben an (Name,
Beschreibung, wahlweise mit Termin). Es startet als Brief mit Anrede und E-Mail-Text und erscheint nach dem Anlegen in
der Akte unter „Schreiben und E-Mail“ › „Eigene Vorlagen“.

**Texte und Adressen ändern:** Alle vier Schreiben sind normale Dokumentvorlagen (Entwurf → Vorschau mit Testpatient →
Veröffentlichen). Die Anschrift der Praxis Dr. Holtmeier steht als Text in den Vorlagen.

## Rückfragen an Alice

1. **Reisebescheinigung unterschreiben:** Die PDF hat Platz für beide Unterschriften (Dr. Holtmeier, Prof. Masin).
   Wird sie ausgedruckt, unterschrieben und dann eingescannt verschickt – oder genügt die E-Mail ohne Unterschrift?
   Der E-Mail-Text geht derzeit davon aus, dass die Patientin sie selbst ausdruckt.
2. **ADAC-Attest:** Sollen die Medikamente/Materialien schon eingetragen werden (z. B. aus dem aktuellen
   Infusionsplan: PE-Beutel, Infusionspumpe, Spül- und Blocklösungen), oder trägt die Praxis sie von Hand ein?
3. **Infoblatt an die Praxis (vorher „Patientenankündigung“):** Auf dem Blatt stehen jetzt nur die Praxistermine mit
   dem Ort „Praxis Dr. Holtmeier“ (beim Anlegen eines Praxistermins schon eingetragen). **Telefon- und Videotermine**
   (Ort mit „Telefon“ oder „Video“ im Namen) stehen standardmäßig **nicht** darauf; im Dialog lassen sie sich mit
   einem Häkchen dazunehmen (dann mit Telefonnummer). Soll das Häkchen standardmäßig gesetzt sein – braucht die Praxis
   die Telefontermine auch? Hinweise wie „1 h, Neuaufnahme“ oder „+ Labor“ ins Feld „bei/Ort“ des Termins. Und an
   welche E-Mail-Adresse bzw. Faxnummer geht das Infoblatt (kann in der Vorlage stehen)?
4. **Terminbestätigung:** Zusätzlich zu Gesundheitskarte und Überweisung steht drin „Neue Befunde … bitte
   mitbringen“ und der Hinweis auf telefonische Absage bei Frau Hessel (9–13 Uhr). Streichen oder so lassen?
5. **Blutuntersuchung:** Das Schreiben an die Hausärzte liegt als PDF-Anlage bei. Soll es zusätzlich eine eigene
   Dokumentvorlage mit Patientenname und Anschrift des Hausarztes werden?
6. **Wann geht das Infoblatt raus?** Eingestellt ist: **wöchentlich** für die nächste Woche (Montag bis Sonntag), die
   Startseite erinnert **3 Tage vorher** (ab Freitag) mit „Praxis Holtmeier informieren“, bis das Blatt erstellt ist.
   Passt das, oder lieber monatlich für den nächsten Monat (die Vorlage spricht von „monatlich angepasst“) bzw. mit
   mehr Vorlauf? Beides lässt sich unter Vorlagen › Grenzwerte › „Infoblatt an die Praxis“ selbst ändern.
