# Dokumentenautomation der Regeneration Clinic (Oktober 2026)

Umsetzung der „Anforderungsspezifikation Dokumentenautomation RGC“ (Stand 26.10.2026, inkl. Editierbarkeit nach
PDF-Erzeugung) im bestehenden EPM. Backend: App `backend/faelle`; Oberfläche: Akte › **Fälle** und Administration ›
**Fälle und Abrechnung** (nur in der Firma Regeneration Clinic). Funktionsnachweis: `docs/BACKEND-FUNKTIONEN.md` F193.

## Grundprinzip

- **Ein Behandlungsfall = eine Datenquelle.** Kostenträger, Kooperationspartner, Sprache, Aufnahme/Entlassung,
  Eingriff, Diagnose und die Texte für OP-Bericht, Entlassungsbrief und Konsil stehen einmal im Fall; alle Dokumente
  des Falls lesen daraus (Platzhalter `{{Fall.…}}`, `{{Rechnung.…}}`, `{{Dokument.…}}`, Tabellen „rechnung“ und
  „leistungen“). Die Platzhalter stehen in **allen** Vorlagen der RGC zur Verfügung, also auch in den Word-Vorlagen
  der Revision 3 (Vorlagen 01–12).
- **Dokumentenpaket je Kostenträgertyp.** Beim Anlegen eines Falls legt EPM die Dokumente des Pakets als Entwurf an
  (Paket je Typ unter Administration › Fälle und Abrechnung › Kostenträgertypen pflegbar). Ist die Aufklärung
  Operation (Vorlage 07) im Paket, kommt der Zusatzbogen des Fachbereichs dazu. Weitere Dokumente (z. B. Konsil) lassen
  sich jederzeit hinzufügen; „Paket ergänzen“ legt nur Fehlendes an.
- **Status je Dokument:** Entwurf (noch keine PDF) → erzeugt (mindestens eine Fassung) → unterschrieben/signiert
  („final“). Nur der letzte Status ist unveränderlich.

## PDF-Erzeugung und nachträgliche Änderungen

| Anforderung | Umsetzung |
|---|---|
| Erzeugte PDF schreibt den Inhalt nicht fest | Bis zur Finalisierung bleiben Falldaten, Dokumenttext und Rechnungspositionen änderbar; „PDF neu erzeugen“ jederzeit. |
| Änderungen über Falldaten bzw. Leistungspositionen | Fall bearbeiten bzw. Positionen ändern/ergänzen/entfernen → neu erzeugen. „veraltet“ zeigt, dass sich seit der letzten Fassung etwas geändert hat (Vergleich des gespeicherten Datenstands). |
| Optionale DOCX für Freitexte | „DOCX herunterladen“ liefert die Freitexte des Dokuments (z. B. Verlauf, Empfehlung; bei der Rechnung Positionstexte und Hinweis) in einer Tabelle; „DOCX übernehmen“ schreibt die geänderten Texte in Fall/Dokument zurück und erzeugt sofort eine neue PDF-Fassung. Die hochgeladene DOCX hängt an der Fassung. |
| Rechnung: Positionen, Mengen, Preise, Texte nach erster PDF änderbar | Ja, bis zur Finalisierung. Die Rechnungsnummer (`RGC-JJJJ-NNNN`, fortlaufend je Jahr) entsteht bei der ersten Erzeugung und bleibt bei jeder Neu-Erzeugung gleich. |
| Korrektur, Nachtrag, Storno + Neuerzeugung | Nicht final: einfach ändern und neu erzeugen. Final: **Stornieren** erzeugt eine Stornorechnung (eigene Nummer, negative Positionen, Bezug auf die Ausgangsrechnung) und auf Wunsch eine neue Rechnung als Entwurf mit denselben Positionen. |
| Jede Neu-Erzeugung versioniert und protokolliert; vorherige Version bleibt | Jede Erzeugung ist eine `DokumentVersion` (unveränderlich, Datenbank-Trigger „nur anfügen“) mit PDF als Dokument der Akte, SHA-256, Vorlagenversion, Datenstand, Person, Zeitpunkt und Grund. Alle Fassungen bleiben abrufbar („Fassungen“). Audit-Log-Art „Behandlungsfall und Dokumente“; Verlauf der Akte zeigt Fälle und Dokumente. |
| Erst Unterschrift/Signatur/Finalisierung macht unveränderlich | Status „final“ nur über **Finalisieren**; danach lehnen Modell und Datenbank-Trigger jede Änderung an Dokument und Positionen ab (Ausnahme: der einmalige Storno-Vermerk an einer finalen Rechnung). |

Nicht finale Fassungen liegen ausgeblendet bei den Dokumenten der Akte (erreichbar über „Fassungen“); die finale
Fassung erscheint sichtbar in den Dokumenten (Archivierung in der Akte, Prüfsumme wird beim Abruf geprüft).

## Signatur und Archivierung

Vier Wege zur unveränderlichen Fassung (Recht „Fall-Dokumente finalisieren“, Standard Mediziner):

1. **Elektronisch signieren (fortgeschritten, in EPM):** PAdES-Signatur mit dem persönlichen Zertifikat der
   unterschriftsberechtigten Person (PKCS#12, unter Administration › Fälle und Abrechnung › Unterschriftsberechtigte
   hinterlegt). Signieren darf nur das verknüpfte Benutzerkonto; das Kennwort der Zertifikatsdatei speichert EPM nicht,
   es wird bei jeder Signatur eingegeben (alleinige Kontrolle über den Schlüssel). Steht die Person noch nicht auf dem
   Dokument, wird es mit ihrem Namen neu gesetzt und dann signiert.
2. **Extern signiert hochladen (z. B. qualifiziert):** Eine qualifizierte elektronische Signatur braucht eine
   qualifizierte Signaturerstellungseinheit (z. B. eParaksts-Karte/-mobile in Lettland) und ist offline in EPM nicht
   möglich. Die erzeugte PDF wird extern signiert und hochgeladen; EPM prüft, dass eine unversehrte Signatur enthalten
   ist, und vermerkt Unterzeichner und Abdeckung an der Fassung.
3. **Papierunterschrift + Scan:** PDF drucken, unterschreiben, Scan (PDF, JPEG oder PNG) hochladen; die
   unterschreibende Person wird ausgewählt.
4. **Finalisieren ohne Unterschrift:** die zuletzt erzeugte Fassung wird ausdrücklich endgültig.

Signatur und Finalisierung ohne Unterschrift verlangen eine aktuelle Fassung (keine Änderungen seit der letzten
Erzeugung). Beim Scan wird festgehalten, auf welcher Fassung er beruht und ob die Daten seitdem geändert wurden.

## Stammdaten

- **Leistungskatalog** (separat pflegbar): Nummer, Bezeichnung DE/LV/EN, Gruppe, Einheit, Preis (EUR), USt.-Satz,
  aktiv. CSV-Import (Semikolon, UTF-8, Kopfzeile `code;bezeichnung;bezeichnung_lv;bezeichnung_en;gruppe;einheit;preis;
  ust_satz`; bekannte Nummern werden aktualisiert, fehlerhafte Datei → nichts übernommen). Positionen übernehmen Text
  (in der Sprache des Falls) und Preis beim Anlegen; Preisänderungen im Katalog ändern bestehende Rechnungen nicht.
  Grundlage für Rechnung und Anlage K (Tabelle „leistungen“ und Feld `{{Leistungen.Summe}}` = aktuelle Rechnung des
  Falls). Der Katalog ist leer ausgeliefert – Preise liefert die Klinik.
- **Kostenträgertypen** (mitgeliefert, änderbar): Österreich ÖGK/SVS/BVAEB/KFA · Österreich Selbstzahler mit
  Rückerstattung · Deutschland GKV · Deutschland BG/UV · Deutschland PKV · Deutschland stationäre Zusatzversicherung ·
  Selbstzahler · International / andere Länder – je mit Standardpaket aus den Vorlagen 01–12 und den Fall-Dokumenten.
- **Kooperationspartner:** Eibach, ARS, WC4, AIWA – frei erweiterbar.
- **Unterschriftsberechtigte:** Dr. Markus Gottwald, Prof. Dr. Markus Masin – erweiterbar, je mit Benutzerkonto und
  optionalem Zertifikat.
- **Sprachen:** DE / LV / EN je Fall; OP-Bericht, Entlassungsbrief, Konsiliarbericht und Rechnung gibt es je Sprache
  (Beträge und Spaltenköpfe passend). Die Formulare 01–12 und die Zusatzbögen bleiben wie geliefert (07/08 und die
  Zusatzbögen zweisprachig DE/LV).

## Vorlagen

Mitgeliefert als eigene Schreiben der RGC (pflegbar unter Vorlagen › Dokumentvorlagen):

- Gruppe „Dokumente der Behandlungsfälle“: OP-Bericht, Entlassungsbrief, Konsiliarbericht, Rechnung – je Deutsch,
  Lettisch, Englisch (`eigen-rgc-<art>-<sprache>`), auf dem Briefpapier der Klinik. Sie entstehen nur im Fall und
  erscheinen nicht unter „Schreiben und E-Mail“ bzw. in der Korrespondenz.
- Fachspezifische Zusatzbögen zu Vorlage 07 (Gruppe „Aufklärungen, Erklärungen und Abrechnung“):
  Orthopädie/Traumatologie (`eigen-rgc-z07-ortho`), HNO (`eigen-rgc-z07-hno`), Adipositas und
  Stoffwechselerkrankungen (`eigen-rgc-z07-adipositas`) – je geplanter Eingriff zum Ankreuzen, eingriffsspezifische
  Risiken, Verhalten danach, ergänzende Fragen, Erklärung und Unterschriften, zweisprachig DE/LV.

## Abnahmekriterium

> Nach Erzeugung einer PDF (insbesondere Rechnung) kann der Inhalt noch geändert und die PDF neu erzeugt werden. Erst
> nach Unterschrift/Signatur ist die Fassung unveränderlich. Alle Versionen sind nachvollziehbar.

Automatisch geprüft in `backend/faelle/tests.py` (`test_rechnung_aenderbar_bis_finalisierung`: Positionen nach der
ersten PDF ändern, ergänzen, entfernen; Neu-Erzeugung mit gleicher Rechnungsnummer; erste Fassung unverändert und mit
Prüfsumme abrufbar; nach der Finalisierung lehnen API, Modell und Datenbank jede Änderung ab), dazu Signatur, Scan,
Storno, DOCX-Rundweg, Sprachen, Pakete, CSV-Import und das endgültige Löschen einer Akte mit Fällen.

## Offen bzw. vor dem Einsatz zu prüfen

- **Preise:** Leistungskatalog mit den Preisen der Klinik füllen (CSV-Import).
- **Bankverbindung der RGC** unter Vorlagen › Briefkopf und Logo eintragen – die Rechnung zeigt sie im Abschnitt
  „Bankverbindung“ (ohne Eintrag entfällt der Abschnitt).
- **Umsatzsteuer:** Standard 0 % mit Hinweis „Steuerfreie Heilbehandlung“; abweichende Sätze je Leistung einstellbar.
  Steuerliche Prüfung (LV/DE/AT) durch die Klinik.
- **Zusatzbögen und lettische Texte:** standardisierter Vorschlag; fachärztliche Prüfung (Orthopädie, HNO,
  Adipositaschirurgie) und Gegenlesung der lettischen Texte stehen aus – wie bei 07/08.
- **Qualifizierte Signatur:** nur über den Weg „extern signiert hochladen“. Eine direkte Anbindung eines
  Signaturdienstes (z. B. eParaksts) wäre ein eigener Schritt und braucht Internetzugang des Servers.
- **Zertifikate für die fortgeschrittene Signatur:** von einer Zertifizierungsstelle bzw. der eigenen Klinik-PKI;
  EPM prüft die Vertrauenskette nicht (offline), es vermerkt Aussteller und Gültigkeit.
- Automatischer Browsertest (Playwright in `frontend/e2e`) für den Reiter „Fälle“ steht aus; von Hand im Browser geprüft: Fall anlegen mit Paket, Position aus dem Katalog, Rechnung erzeugen, Preis ändern („veraltet“), neu erzeugen (gleiche Nummer, Fassung 2), finalisieren.
