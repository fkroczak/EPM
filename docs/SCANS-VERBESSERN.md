# Scans: So verbessern Sie die Erkennung

*Zum Ausdrucken für die Praxis. Stand 10.10.2026 (EPM F189).*

EPM liest den Text aus dem Bild eines Scans – auf dem eigenen Server, ohne Internet. Dabei kann es sich verlesen.
Sie prüfen jeden Wert, bevor er in die Akte kommt. Wenn Sie dabei Fehler anmerken, liest EPM den nächsten Befund
desselben Labors besser.

## In vier Schritten

1. **Vergleichen.** Beim Zuordnen auf eine Zeile tippen. Links im Bild leuchtet die Stelle auf, an der EPM gelesen hat.

2. **Falsches anmerken.** Stimmt eine Zeile nicht: auf **Falsch erkannt** tippen und den Grund wählen.

   | Grund | Wann? | Beispiel | Was EPM sich merkt |
   |---|---|---|---|
   | Gehört nicht dazu | Die Zeile ist gar kein Wert | „Referenzbereich“, eine Überschrift, ein Datum | Diese Zeile bei diesem Labor künftig weglassen |
   | Falsche Zeile | Die Bezeichnung gehört zu einem anderen Wert | „Eisen“ wurde dem Ferritin zugeordnet | Bei diesem Labor nicht mehr so zuordnen |
   | Falscher Wert | Die Zahl ist falsch gelesen | 3,8 statt 3,0 | nichts – den Wert mit „+ Wert“ richtig eintragen |

3. **Fehlendes markieren.** Fehlt ein Wert: auf **Bereich markieren** tippen und mit Maus oder Finger einen Rahmen um
   die richtigen Zeilen im Bild ziehen. EPM liest nur diesen Teil noch einmal genauer und zeigt jede Zeile als neuen
   Wert. Einen einzelnen Wert können Sie auch anklicken: Feld wählen, dann die Zahl im Bild antippen.

4. **Prüfen und übernehmen.** Wenn nötig den richtigen Laborwert aus der Liste wählen und „In die Akte legen“.
   Erst dann merkt sich EPM Ihre Auswahl.

## Gut zu wissen

- **Nichts geht ohne Sie in die Akte.** Was EPM gelernt hat, schlägt es nur vor. Neues Gelerntes steht zuerst mit
  „gelernt?“ da und ist nicht angehakt; erst nach mehrmaliger Bestätigung (Standard: 2-mal) ist es vorgewählt.
- **Keine Patientendaten.** Gespeichert werden nur Bezeichnungen (z. B. „Harnstoff-N gehört zu Harnstoff“) und die Lage
  auf der Seite – keine Werte, keine Namen, kein Geburtsdatum.
- **Falsch gelernt?** Unter **Scans › Gelernte Zuordnungen** lässt sich jeder Eintrag **löschen** (darf neu gelernt
  werden) oder **sperren** (nie wieder so).
- **Wie gut liest EPM?** Unten in der Scan-Liste steht, wie viel Prozent der Werte diesen Monat noch korrigiert werden
  mussten. Der Pfeil ▼ heißt: besser als im Vormonat.
- **Wer steuert das Lernen?** Wer Vorlagen pflegt, kann unter „Gelernte Zuordnungen“ das Lernen pausieren und einstellen,
  ab wie vielen Bestätigungen (1, 2 oder 3) etwas als sicher gilt. Übungszugänge lernen nie mit.
