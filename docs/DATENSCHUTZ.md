# EPM – Datenschutz (DSGVO)

Stand: 02.10.2026 · gehört zu `docs/BACKEND-FUNKTIONEN.md` (F74–F83)

Dieses Dokument hält fest, **welche Vorschriften** EPM berücksichtigt, **wie** sie umgesetzt sind und **was offen ist**.
Es ist keine Rechtsberatung. Wo eine Frage nicht aus dem Gesetz selbst beantwortet werden kann, steht sie unter
„Offene Punkte“ – dort ist nichts eigenmächtig entschieden, die Werte sind in der Oberfläche einstellbar.

## 1. Ausgangslage (Angaben der Stiftung, 02.10.2026)

| Punkt | Stand |
|---|---|
| Verantwortlicher | Deutsche Stiftung Krankheitsbedingte Mangelernährung, allein. Die Praxis führt eigene Akten; die Stiftung vermittelt. |
| Daten | Gesundheitsdaten (Art. 9 DSGVO) von Patienten mit Kurzdarmsyndrom: Diagnose, Therapie, Gewichte, Kontakte, Empfehlungen für Infusionspläne, Dokumente |
| Freigabe der Pläne | nur Prof. Dr. rer. medic. Markus Masin (kein Arzt). Freigabe per E-Mail; Mitarbeiter dokumentieren und schließen den Plan im System ab. |
| Betrieb | VPS bei Netcup, Nextcloud bei Hetzner – jeweils mit Auftragsverarbeitungsvertrag; NAS in der Stiftung |
| Sicherungen | werden 30 Tage vorgehalten |
| Aufbewahrung | 10 Jahre – „soweit bekannt“ (Rechtsgrundlage siehe Offene Punkte, O1) |
| Altsystem | seit 13.06.2018 online |

## 2. Vorschriften und Umsetzung

| Vorschrift | Inhalt (kurz) | Umsetzung in EPM | Funktion |
|---|---|---|---|
| Art. 5 Abs. 1 e DSGVO (Speicherbegrenzung) | Daten nur so lange speichern, wie es der Zweck erfordert | Aufbewahrungsfrist je Akte ab Abschluss – bzw. ab dem letzten Kontakt, wenn der später liegt (einstellbar, Standard 10 Jahre); Übersicht „Aufbewahrung abgelaufen“ und „läuft in 12 Monaten ab“; Hinweis „Abschluss prüfen“ für lange ruhende Akten, damit die Frist überhaupt beginnt | F74, F81 |
| Art. 5 Abs. 2 DSGVO (Rechenschaftspflicht) | Einhaltung nachweisen können | Audit-Log, Verlauf, Löschprotokoll (ohne Namen), Erklärungen mit Datum und Scan | F58, F75, F80 |
| Art. 7 Abs. 1 und 3 DSGVO | Einwilligung nachweisen; Widerruf jederzeit, wirkt für die Zukunft | Erklärungen je Akte mit Datum, Fassung der Vorlage und Scan; Widerruf mit Datum; Hinweis im Aktenkopf und in „Nach und nach prüfen“, wenn eine Erklärung fehlt | F75 |
| Art. 9 Abs. 2 a bzw. h, Abs. 3 DSGVO | Gesundheitsdaten nur mit ausdrücklicher Einwilligung oder auf einer der anderen Grundlagen | Vordruck „Einwilligung“ als Dokumentvorlage; welche Grundlage die Stiftung nutzt, ist offen (O1) | F76 |
| Art. 12 Abs. 3 DSGVO | Anträge innerhalb eines Monats beantworten; Verlängerung um zwei Monate möglich, die Person ist darüber mit Gründen zu unterrichten | Anfragen als Vorgang mit Frist (1 Monat ab Eingang, einmal um 2 Monate verlängerbar – nur mit Grund), „überfällig“ in Akte, Startseite und Übersicht | F77 |
| Art. 12 Abs. 4 DSGVO | Wird ein Antrag nicht erfüllt, sind der Person innerhalb eines Monats die Gründe mitzuteilen – mit dem Hinweis auf die Beschwerde bei einer Aufsichtsbehörde und den gerichtlichen Rechtsbehelf | „abgelehnt“ und „eingeschränkt statt gelöscht“ nur mit Begründung; Datum der Mitteilung. Das Schreiben selbst (mit den Hinweisen) verfasst die Stiftung; EPM hält Begründung und Datum fest | F77 |
| Art. 13 DSGVO | Information bei der Erhebung | Vordruck „Datenschutzinformation“ als Dokumentvorlage (Entwurf mit Lücken, siehe O2); Aushändigung wird in der Akte nachgehalten | F75, F76 |
| Art. 15 Abs. 3 DSGVO | Kopie der Daten | „Kopie der Akte“ als ZIP: Akte und Verlauf als PDF, alle Dokumente im Original; jede Kopie steht im Audit-Log | F78 |
| Art. 17 Abs. 1 DSGVO | Löschung auf Antrag bzw. wenn der Zweck entfallen ist | Akte endgültig löschen (Mediziner und Admin, Kennwort + Authenticator-Code + Bestätigungscode): Einträge, Historie, Dateien weg; Audit-Log ohne Namen und Inhalte; Löschprotokoll ohne Namen. Einzelne Dokumente: F73 | F80, F73 |
| Art. 17 Abs. 3 b und e DSGVO | keine Löschung, soweit eine rechtliche Pflicht zur Aufbewahrung besteht oder die Daten für Rechtsansprüche gebraucht werden | Vor Ablauf der Frist wird nur auf Antrag gelöscht; der Mediziner entscheidet, ob eine Aufbewahrungspflicht entgegensteht – dann Einschränkung statt Löschung | F79, F80 |
| § 35 Abs. 3 BDSG | Einschränkung statt Löschung, wenn satzungsgemäße oder vertragliche Aufbewahrungsfristen entgegenstehen | Ergebnis „Verarbeitung eingeschränkt statt gelöscht“ einer Anfrage schränkt die Akte ein | F77, F79 |
| Art. 18 DSGVO | Eingeschränkte Daten werden – von der Speicherung abgesehen – nur noch mit Einwilligung der Person, für Rechtsansprüche, zum Schutz der Rechte einer anderen Person oder aus wichtigem öffentlichem Interesse verarbeitet (Abs. 2); vor dem Aufheben ist die Person zu unterrichten (Abs. 3) | Eingeschränkte Akte erscheint in keiner Patientenliste, Suche oder Auswertung; lesbar nur mit begründeter Einsicht (60 Minuten, im Audit-Log; die Ansicht nennt die zulässigen Zwecke nach Abs. 2 – ob der eingetragene Grund darunter fällt, entscheidet die Person, nicht das Programm). Damit Fristen und Anfragen nicht untergehen, führt die Übersicht „Datenschutz“ sie weiter auf: mit Namen nur für Personen, die Einsicht nehmen dürften, sonst nur mit Nummer; ebenso das Audit-Log. Aufheben nur mit Datum der Unterrichtung oder Begründung, warum sie entfällt | F79, F81 |
| Art. 32 DSGVO | Sicherheit der Verarbeitung | bestehend: Rollen und Rechte, 2FA, Sperre, Sitzungsende, Audit-Log, Trigger. Sicherungen 30 Tage, verschlüsselt (GnuPG, AES-256) mit einem Passwort, das die Administration in der Oberfläche festlegt (O5 geklärt) – solange keines festgelegt ist, sind die Sicherungen auf dem Server unverschlüsselt und werden nicht übertragen; Übertragung nur verschlüsselt; Wiederherstellen nur mit Passwort und 2FA | F61–F64, F66 |
| § 630f BGB | Dokumentation: Änderungen müssen erkennbar bleiben; Aufbewahrung 10 Jahre nach Abschluss der Behandlung | Verlauf und Versionen unveränderlich (bestehend, F19, F22, F60). Ob § 630f für die Stiftung unmittelbar gilt, ist offen (O1) | F60, F74 |
| § 203 StGB | Berufsgeheimnis; mitwirkende Dienstleister sind zur Geheimhaltung zu verpflichten | organisatorisch (O6) – nichts im Programm | – |

Zur Freigabe der Infusionspläne (kein Datenschutzthema, aber Teil der Klärung): Der Vermerk auf der PDF muss stimmen.
Schließt ein Mitarbeiter den Plan nach einer Freigabe per E-Mail ab, nennt der Vermerk den Mediziner, das Datum und
den Weg der Freigabe sowie, wer den Plan im System abgeschlossen hat; die E-Mail liegt als Nachweis in der Akte (F82).

## 3. Was EPM jetzt tut

**In der Akte, Reiter „Datenschutz“**
- *Erklärungen:* Datenschutzinformation, Einwilligung, Schweigepflichtentbindung – je Art „liegt vor seit …“, „widerrufen
  am …“ oder „nicht erfasst“ (nachgehalten wie die Nickelallergie). Vordruck als PDF mit den Daten des Patienten,
  unterschriebenes Blatt als Scan erfassen, Widerruf eintragen.
- *Anfragen:* Auskunft, Berichtigung, Löschung, Einschränkung, Widerruf, Sonstiges – mit Eingangsdatum, Frist und Ergebnis.
- *Aufbewahrung:* Frist der Akte, Verlängerung im Einzelfall (mit Grund), Kopie der Akte, Akte endgültig löschen.

**Menüpunkt „Datenschutz“** (wer Erklärungen/Anfragen erfassen oder entscheiden darf): offene Anfragen nach Frist,
Akten mit abgelaufener bzw. bald ablaufender Aufbewahrung, eingeschränkte Akten, Löschprotokoll, eingestellte Fristen.

**Startseite „Nach und nach prüfen“:** Erklärungen fehlen · Abschluss prüfen · offene Datenschutz-Anfragen (auch zu
abgeschlossenen Akten, mit der Zahl der überfälligen).

**Vorlagen › Dokumentvorlagen:** drei neue Vorlagen (Datenschutzinformation, Einwilligung, Schweigepflichtentbindung).

**Vorlagen › Grenzwerte › Datenschutz:** Aufbewahrung nach Abschluss (Jahre), „Abschluss prüfen“ (Monate),
Aufbewahrung des Audit-Logs (Jahre, 0 = unbegrenzt), Erklärungen, die vorliegen sollen. Ändern kann diese Werte nur, wer
über Datenschutz-Anfragen entscheidet – „Vorlagen pflegen“ allein reicht nicht.

**Rechte** (Benutzer › Rechte, je Gruppe einstellbar):

| Recht | Betrachter | Mitarbeiter | Mediziner | Admin |
|---|---|---|---|---|
| Datenschutz: Erklärungen und Anfragen erfassen, Kopie der Akte | – | ✓ | ✓ | ✓ T |
| Datenschutz: Anfragen entscheiden, Verarbeitung einschränken, Einsicht, Aufbewahrung verlängern | – | – | ✓ | ✓ T |
| Akten endgültig löschen | – | – | ✓ | ✓ (auch echte Akten) |
| Infusionspläne nach Freigabe abschließen | – | ✓ | ✓ | ✓ T |

T = nur bei Testpatienten. Endgültig löschen dürfen Admins seit 02.10.2026 auch echte Akten und Dokumente (Festlegung;
sonst schreiben Admins Patientendaten nur bei Testpatienten) – eine eingeschränkte Akte aber nicht, weil sie sie nicht
sehen; die löscht wer Einsicht nehmen darf. Admins können eingeschränkte echte Akten nicht einsehen; sie sehen von ihnen – in der
Übersicht, im Audit-Log – nur die Nummer, im Django-Admin gar nichts. Mitarbeiter (ohne das Recht „entscheiden“) ebenso.
Wer das Recht „entscheiden“ hat, sieht in der Übersicht „Datenschutz“ und im Audit-Log auch Namen und Grund – sonst
ließe sich eine Anfrage zu einer eingeschränkten Akte nicht bearbeiten; die Akte selbst öffnet auch diese Person nur
mit begründeter Einsicht.

**Was beim Löschen einer Akte bleibt:** das Löschprotokoll (Patientennummer und interne Kennung, angelegt am,
abgeschlossen am, Aufbewahrung bis, Rechtsgrund, der eingetragene Grund, Anzahl der gelöschten Einträge, bei einem
Antrag sein Eingangsdatum, Zeitpunkt, Person – kein Name, nicht der Anlass des Abschlusses) und die Einträge im
Audit-Log als „Akte Nr. N (gelöscht)“ ohne Namen, Titel und Freitexte. Die Patientennummer wird nicht neu vergeben.
Ein Dokument, das einer anderen Akte zugeordnet wurde, gehört zu jener Akte und bleibt dort.

**Sicherungen:** Eine ältere Sicherung enthält gelöschte Akten und Dokumente noch bis zu ihrem Ablauf (30 Tage). Jede
Löschung steht in der Löschliste (`data/loeschliste/loeschliste.jsonl`: dieselben Angaben wie im Löschprotokoll, kein
Name); nach einer Wiederherstellung löscht das Backend beim Start alles erneut, was die Sicherung zurückgebracht hat
(`manage.py epm_loeschungen_nachholen`). Die Löschliste gehört zu genau einem System – nie die eines anderen Systems
(z. B. einer Testkopie) einspielen. Jede Sicherung enthält eine Kopie der Löschliste (`epm-loeschliste_….jsonl`,
verschlüsselt wie die übrigen Dateien). Das Wiederherstellen fasst die Löschliste auf dem Server nicht an und spielt
auch keine aus der Sicherung ein: Auf einem **neuen** Server muss die neueste Löschliste aus den Sicherungen von Hand
nach `data/loeschliste/loeschliste.jsonl` gelegt werden, bevor eine ältere Sicherung zurückgespielt wird – sonst kommen
Löschungen zurück, die nach dieser Sicherung lagen.

## 4. Grenzen der Umsetzung (bewusst so)

- **Eingeschränkt werden nur abgeschlossene Akten.** In einer laufenden Betreuung wird die Akte gebraucht; wer die
  Verarbeitung nicht mehr will, beendet die Betreuung (Akte abschließen), danach wird eingeschränkt oder gelöscht.
- **Gelöscht wird die ganze Akte**, nicht einzelne Einträge (Ausnahme: ein Dokument, das nicht zur Akte gehört – F73).
  Falsche Angaben werden berichtigt; die frühere Fassung bleibt im Verlauf (§ 630f BGB: Änderungen erkennbar).
- **Der Grund einer Löschung bleibt** im Löschprotokoll und in der Löschliste. Die Oberfläche bittet, keine Namen
  hineinzuschreiben; verhindern kann das Programm es nicht.
- **Das Nachholen der Löschungen nach einer Wiederherstellung kann scheitern – dann wird es gemeldet, nicht still
  übergangen.** Es läuft bei jedem Start des Backends und noch einmal am Ende jeder Wiederherstellung. Was es erneut
  löscht und was nicht ging (Fehler, nicht nachgeholte Akten, unlesbare Zeilen der Löschliste), steht im Audit-Log
  (Gruppe „System“); ein Fehler erscheint auf der Backup-Seite und in der Kopfzeile der Startseite, bis ein Lauf ohne
  Fehler durchgeht, und die Meldung des Wiederherstellens nennt ihn („ACHTUNG: Löschungen … konnten nicht vollständig
  nachgeholt werden“). Das Backend startet in diesem Fall trotzdem – bis zur Behebung sind die betroffenen Akten oder
  Dokumente wieder sichtbar.
- **Die Frist beginnt nicht vor dem letzten Kontakt.** Das Abschlussdatum lässt sich rückwirkend eintragen; liegt ein
  Kontakt danach, zählt dessen Tag. So macht ein Tippfehler im Jahr eine Akte nicht sofort löschbar.
- **Gelöscht wird von Hand**, nie automatisch: Die Übersicht zeigt Akten mit abgelaufener Frist, ein Mediziner löscht.
- **Geänderte Jahre gelten für alle Akten**, auch für bereits abgeschlossene.
- **Die drei Vordrucke sind Entwürfe.** Sie folgen dem Aufbau von Art. 13 DSGVO bzw. nennen Freiwilligkeit und Widerruf,
  enthalten aber Lücken in [eckigen Klammern] und einen Hinweis zur Prüfung. Bis die Stiftung sie bearbeitet und
  veröffentlicht hat, tragen die PDFs das Wasserzeichen „ENTWURF“.
- **Das Audit-Log wird standardmäßig nicht gekürzt** (0 = unbegrenzt), siehe O3.

## 5. Offene Punkte (Entscheidung der Stiftung)

| Nr. | Frage | Warum offen | Zwischenstand in EPM |
|---|---|---|---|
| O1 | Auf welcher Rechtsgrundlage verarbeitet die Stiftung (Einwilligung nach Art. 9 Abs. 2 a oder Art. 9 Abs. 2 h), und woraus folgen die 10 Jahre? | § 630f Abs. 3 BGB verpflichtet Behandelnde. Die Stiftung „vermittelt“, die Praxis führt eigene Akten; Prof. Masin ist kein Arzt. Ob die 10 Jahre für die Stiftung aus dem Gesetz, aus einem Vertrag bzw. der Satzung oder aus den unterschriebenen Unterlagen folgen, ist nicht belegt („soweit bekannt“). Anfrage an die Stiftung ist formuliert, Antwort steht aus. | 10 Jahre als einstellbarer Standard; vor Ablauf wird nur auf Antrag und nach Entscheidung des Mediziners gelöscht |
| O2 | Texte der drei Vordrucke | Rechtstexte dürfen nicht erfunden werden: Zwecke, Empfänger, Rechtsgrundlage, Speicherdauer, Datenschutzbeauftragte/r, Aufsichtsbehörde trägt die Stiftung ein | Entwürfe mit Lücken, Wasserzeichen „ENTWURF“ bis zur Veröffentlichung |
| O3 | Wie lange wird das Audit-Log aufbewahrt? | keine gesetzliche Zahl gefunden; Abwägung zwischen Nachweis (Art. 5 Abs. 2) und Speicherbegrenzung | 0 = unbegrenzt, einstellbar |
| O4 | Nach wie vielen Monaten ohne Kontakt soll „Abschluss prüfen“ erscheinen? Welche Erklärungen sollen vorliegen? | fachliche Festlegung | 24 Monate; alle drei Erklärungen – beides einstellbar |
| O5 | ~~Verschlüsselung der Sicherungen: Wer verwahrt den Schlüssel?~~ **Geklärt 02.10.2026:** symmetrisch mit einem Passwort aus der Oberfläche (Administration › Backup); es liegt nur auf dem Server (root, 0600), damit die nächtliche Sicherung ohne Eingabe läuft, und ausgedruckt im Tresor (Passwortblatt). Ein neues Passwort gilt ab der nächsten Sicherung; ältere bleiben, bis keine Sicherung sie mehr braucht | – | umgesetzt (F61) |
| O6 | Verpflichtung von Netcup und Hetzner zur Geheimhaltung (§ 203 StGB) zusätzlich zum Auftragsverarbeitungsvertrag | liegt nicht vor bzw. nicht bekannt | – (organisatorisch) |
| O7 | Aufbewahrung der Sicherungen auf der NAS und in der Nextcloud | 30 Tage gelten nur für den Server. EPM überträgt nur verschlüsselte Sicherungen und löscht im Ziel nie (Schutz gegen versehentliches oder böswilliges Löschen) – wie lange Kopien dort liegen, legt die Stiftung fest; so lange bleiben gelöschte Akten darin (verschlüsselt) erhalten | – (organisatorisch; Löschen im Ziel z. B. per Aufbewahrungsregel der Nextcloud/NAS) |
| O8 | Sollen Mitarbeiter Pläne auch anlegen dürfen? | Abschließen nach Freigabe dürfen sie jetzt; das Anlegen ist nach der Festlegung vom 01.10.2026 Medizinern vorbehalten und unter Benutzer › Rechte umstellbar | unverändert |
| O9 | Nachweis bei Freigabe per Telefon oder persönlich | bei E-Mail und schriftlich ist der Nachweis Pflicht; bei Telefon/persönlich gibt es kein Schriftstück. Der genannte Mediziner wird von EPM nicht benachrichtigt – er sieht den Plan mit Vermerk in der Akte, im Verlauf und im Audit-Log | ohne Nachweis möglich, Weg und Datum stehen im Vermerk |

## 6. Vor der Inbetriebnahme (organisatorisch, nicht im Programm)

1. Antwort der Stiftung zu O1 einholen; Aufbewahrung in Vorlagen › Grenzwerte danach bestätigen oder anpassen.
2. Die drei Vordrucke ausfüllen, rechtlich prüfen lassen und veröffentlichen (Vorlagen › Dokumentvorlagen).
3. Verzeichnis von Verarbeitungstätigkeiten (Art. 30 DSGVO) um EPM ergänzen: Zwecke, Kategorien, Empfänger (Versorger,
   Praxis), Auftragsverarbeiter (Netcup, Hetzner), Löschfristen.
4. Geheimhaltungsverpflichtung der Dienstleister (O6) klären.
5. Sicherungs-Passwort unter Administration › Backup festlegen, Passwortblatt drucken und im Tresor verwahren; Aufbewahrung auf NAS/Nextcloud festlegen (O7).
6. Nach dem Import der Altdaten (F65): Altsystem abschalten und seine Daten löschen – Datenbank, Dumps, Kopien auf
   Arbeitsrechnern und die Test-VM. Solange dort Daten liegen, gelten Löschungen in EPM dort nicht.
   Im EPM selbst liegt der Dump (mit den Daten aller Patienten des Altsystems, auch der nicht übernommenen und der dort
   gelöschten) bis zum „Abschließen“ in der Datenbank; mit dem Abschließen werden Dump, Zuordnungen und die Nummern in
   den Importprotokollen gelöscht. Getrennt zu löschen bleiben: der Dokumentenordner `data/import/PatData` auf dem
   Server und Sicherungen aus der Zeit vor dem Abschließen (auf dem Server laufen sie nach 30 Tagen ab; Kopien auf NAS
   und Nextcloud löscht EPM nicht, siehe O7). Wird später eine Sicherung aus der Zeit vor dem Abschließen
   zurückgespielt, sind Dump und Zuordnungen wieder da und die Übernahme gilt wieder als vorläufig – dann erneut
   „Abschließen“. Kennwörter des Altsystems werden nie gespeichert.
7. Freigabe-E-Mails für Infusionspläne: nur Patienten- und Plannummer nennen, keine Namen oder Diagnosen.
8. Bestehende Patienten: vorhandene Einwilligungen und Schweigepflichtentbindungen nach und nach in der Akte erfassen
   (Startseite „Erklärungen fehlen“).
