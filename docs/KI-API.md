# KI (Experimentell) – API

Stand 14.10.2026 · alle Endpunkte unter `/api/ki/`, JSON, Anmeldung mit zweitem Faktor wie überall (Sitzung + CSRF).
Sichtbar ist nur, was zur **aktiven Firma** gehört: Akte in der Firma (`patienten_fuer`) und Dokument in dieser Firma
erfasst oder ohne Firma. Fehler: `{"fehler": "…"}` bzw. Feldfehler `{"feld": ["…"]}` wie im übrigen EPM.

Rechte: `ki_ansehen` (lesen), `ki_pruefen` (korrigieren, freigeben, ablehnen, erneut, anfordern), `ki_uebernehmen`
(+ Recht der Akte je Ziel), `ki_berichte`, `ki_verwalten`, `ki_training_freigeben`.

Das Backend spricht nie selbst mit dem Modell: Verarbeitung, Berichtsentwürfe und Evaluation erledigt der KI-Dienst.

## Vorgänge (Prüf-Queue)

| Methode und Pfad | Recht | Beschreibung |
|---|---|---|
| `GET vorgaenge/?status=zur_pruefung,teilweise&patient=&dokumenttyp=&konfidenz_unter=0.85&fehler=1&von=&bis=&suche=&ordnung=neu\|alt\|konfidenz&page=&seitengroesse=` | ansehen | Seitenweise Liste (`count`, `next`, `results`) mit `felder_offen`, `felder_unsicher` |
| `GET vorgaenge/zaehler/` | ansehen | `{"je_status": {…}, "zur_pruefung": n}` (Menüpunkt) |
| `GET vorgaenge/{id}/` | ansehen | Vorgang mit `felder`, `seiten_liste` (OCR- und KI-Text je Seite), `modell`, `prompt_version`, `uebernahmen`, `vorschau` (siehe unten), `rechte` |
| `POST vorgaenge/anfordern/` `{"dokument": id}` | prüfen | Dokument mit Vorrang verarbeiten lassen (auch tagsüber) → 201 |
| `PATCH vorgaenge/{id}/felder/{fid}/` `{"wert": {…}, "fehlerart": "lesefehler", "kommentar": "…", "entscheidung": "ersetzen", "status": "freigegeben"}` | prüfen | Korrigieren (jede Änderung versioniert als `KiKorrektur`; Vorschlag der KI bleibt in `wert`, Korrektur in `korrigiert`), Konfliktentscheidung, Status je Feld. Laborwert mit anderem `parameter_name` wird dem Katalog neu zugeordnet |
| `POST vorgaenge/{id}/freigeben/` `{"felder": [ids] \| "alle": true, "status": "freigegeben\|verworfen\|offen"}` | prüfen | Mehrere Felder; „alle“ gibt nur sicher erkannte (oder korrigierte) Felder frei |
| `GET vorgaenge/{id}/vorschau/` | ansehen | je Feld: `aktion` = `neu` · `ergaenzen` · `ueberschreiben` · `identisch` · `konflikt` · `nur_info`, `bestehend` (Eintrag der Akte), `optionen` (nötige Entscheidung), `fehler` (z. B. Datum fehlt), `unsicher` |
| `POST vorgaenge/{id}/uebernehmen/` `{"felder": [ids], "entscheidungen": {"<id>": "neu\|ergaenzen\|ersetzen\|verwerfen"}, "bestaetigt": true}` | übernehmen + Recht der Akte | Übernahme freigegebener Felder in einer Transaktion → 201 `{"ziele": [{modell, id, aktion}], "status"}`; **409** `{"konflikte": [vorschau…]}`, wenn eine Entscheidung fehlt (nichts wird geschrieben); 400 ohne `bestaetigt` oder bei nicht freigegebenen Feldern; 403 ohne Recht bzw. als Admin bei echten Akten |
| `POST vorgaenge/{id}/ablehnen/` `{"grund": "…"}` | prüfen | alle offenen Vorschläge verworfen, Status „Abgelehnt“ |
| `POST vorgaenge/{id}/erneut/` `{"nachverarbeitung": false}` | prüfen | erneut verarbeiten (bzw. „zur Nachverarbeitung“ – läuft, sobald das Modell bereit ist) |
| `POST vorgaenge/neu_lesen/` `{"vorgaenge": [ids]}` oder `{"seit_tagen": 30, "dokumenttypen": ["labor", …], "nur_anderes_modell": true, "hoechstens": 200}` | verwalten | „Jetzt neu lesen“ (14.11.2026): wie „Erneut verarbeiten“, aber mit `prio_neu_lesen` (läuft nachts) – gleiche Logik wie die Nachtaufgabe `neu_lesen` (`eingang.neu_lesen`). Nur Vorgänge der eigenen Firma; ausgenommen in Arbeit/wartend, übernommen, abgelehnt. `seit_tagen` 0–3650 (Dokument hochgeladen in den letzten n Tagen, 0 = alle), `dokumenttypen` = `KiVorgang.dokumenttyp`, `hoechstens` 1–5000. → `{"vorgemerkt": n}`; Feldfehler unter dem Feldnamen. Audit `neu_lesen` |

Ziele der Übernahme und nötige Rechte: Labor → `Laborbefund`/`Laborwert` (`eintraege_erfassen`), Infusion →
`Infusionsplan` aus dem Altsystem, Status „abgelöst“ (`plaene_anlegen`), Medikation → `Medikament` (`akten_bearbeiten`;
aus alten Dokumenten „nicht aktiv“ mit Stand des Dokuments), Diagnose (`akten_bearbeiten`), Texte → Abschnitt der Akte
angehängt (`akten_bearbeiten`), Dokumentdatum/-typ → `Dokument` (`eintraege_erfassen`).

## Hinweise Labor ↔ Infusionsplan

| `GET hinweise/?patient=ID&alle=1` | ansehen | `[{art, art_name, stufe: gesichert\|wahrscheinlich, parameter, text, zeitpunkt, belege: {labor, plan, folge, wiederholungen}, status}]` |
|---|---|---|
| `PATCH hinweise/{id}/` `{"status": "neu\|gesehen\|ausgeblendet"}` | ansehen | Status |

## Berichtsentwürfe

| Methode und Pfad | Recht | Beschreibung |
|---|---|---|
| `GET berichte/?patient=ID` · `GET berichte/{id}/` | ansehen | Aufträge mit `fakten` (Quellen), `entwurf`, `pruefung` (`unbelegte_werte`, `unbekannte_belege`, `saetze_ohne_beleg`, `empfehlung_oder_bewertung`, `ok`), `kennzeichnung` |
| `POST berichte/` `{"patient", "art": "labor\|infusion\|verlauf", "von", "bis", "dokumenttypen": ["labor", "infusion", "medikation", "diagnosen", "verlauf"]}` | berichte | Auftrag → der KI-Dienst erstellt den Entwurf |
| `POST berichte/{id}/speichern/` `{"text": "…", "titel": "…"}` | berichte + `eintraege_erfassen` | legt einen `Bericht` im Status Entwurf an (Kennzeichnung + Quellen im Inhalt) |
| `POST berichte/{id}/verwerfen/` | berichte | |

## Akte auf einen Blick (14.11.2026)

Was seit dem letzten Praxistermin in der Akte dokumentiert wurde – Fakten aus der Akte (Code), formuliert vom lokalen
Modell, gegengeprüft wie der Berichtsentwurf. Sichtbar wie die Vorgänge: Akte im Bereich der Person und die
Zusammenfassung in deren Firma angefordert bzw. ohne Firma (nachts für einen Termin vorbereitet; Firma des Termins).
Inhalte stehen nie im Audit-Log.

| Methode und Pfad | Recht | Beschreibung |
|---|---|---|
| `GET zusammenfassungen/?patient=ID` | ansehen | höchstens 5, neueste zuerst (400 ohne `patient`; fremde Akte → `[]`) |
| `POST zusammenfassungen/` `{"patient": ID}` | berichte | neue auf Anforderung (`grund=angefordert`) → 201; **409**, solange für die Akte eine `wartet`/`laeuft`; 400 für unbekannte oder eingeschränkte Akte. Audit `zusammenfassung_angefordert` |

Antwort je Zusammenfassung:

```json
{"id": 7, "patient": 12, "grund": "termin|angefordert", "termin_datum": "2026-11-15|null",
 "von": "2026-10-02|null", "bis": "2026-11-14|null", "von_grund": "termin|kontakt|standard|null",
 "status": "wartet|laeuft|fertig|fehler", "entwurf": "Labor: … [1]\n\nInfusionsplan: … [3]",
 "fakten": [{"nr": 1, "text": "Labor 10.11.2026: Kalium 3,1 mmol/l (Referenz 3,5–5,1), unterhalb des Referenzbereichs",
             "quelle": {"modell": "laborwert", "id": 55}, "datum": "2026-11-10", "link": "labor"}],
 "pruefung": {"unbelegte_werte": [], "unbekannte_belege": [], "saetze_ohne_beleg": [],
              "empfehlung_oder_bewertung": [], "ok": true},
 "fehler": "", "modell": "Qwen3.5-4B|null", "erstellt_am": "…", "fertig_am": "…|null",
 "angefordert_von_name": "…|null"}
```

`von`/`bis`/`von_grund` stehen fest, sobald der KI-Dienst sie erstellt (`pruefung` ist bis dahin `null`). `von` =
letzter Praxistermin vor heute (nicht ausgeblendet; `von_grund=termin`), sonst letzter Kontakt (`kontakt`), sonst heute
− `zusammenfassung_ohne_termin_tage` (`standard`); `bis` = heute. `link` = Reiter der Akte (`labor`, `plaene`,
`medikamente`, `diagnosen`, `kontakte`, `dokumente`, `berichte`, `korrespondenz`, `faelle`, `bia`, `kartei` (Gewicht),
`therapie`, `ki` (Hinweise)); `quelle.modell` z. B. `laborwert`, `infusionsplan`, `medikament`, `diagnose`,
`behandlungsfall`, `gewichtsmessung`, `bia`, `therapieschritt`, `kontakt`, `bericht`, `schreiben`, `dokument`,
`kihinweis`. Höchstens 150 Fakten, Wichtiges zuerst.

## KI-Chat (12.11.2026)

Jede Person sieht **nur ihre eigenen** Unterhaltungen (auch Admins keine fremden; fremde → 404). Die Antwort schreibt
der KI-Dienst (Vorrang vor Dokumenten und Berichten, auch tagsüber; nicht während einer Pause, z. B. Sicherung).
Systemanweisung = fester Rahmen (`ki/chat.py` `RAHMEN`) + Anweisung der Promptvorlage. Unterhaltungen ohne Änderung
werden nach `chat_tage` (Einstellungen; Startwert `EPM_KI_CHAT_TAGE`, Standard 30) gelöscht; im Audit-Log steht nur, dass gechattet wurde, nie der Text.

| Methode und Pfad | Recht | Beschreibung |
|---|---|---|
| `GET chats/` · `GET chats/{id}/` | ansehen | eigene Chats; Detail mit `nachrichten` (`rolle` nutzer/ki, `status` wartet/laeuft/fertig/fehler, `pruefung`: `neue_werte` = Zahlen/Daten, die in keiner Eingabe stehen, `fehlende_werte` = Zahlen/Daten der Anfrage, die in der Antwort fehlen, `offene_stellen` = Anzahl [?]) |
| `POST chats/` `{"vorlage": ID, "titel": "…"}` · `DELETE chats/{id}/` | berichte · ansehen | |
| `POST chats/diktat/` `{"diktat": ID}` | berichte | Diktat → gegliederter Bericht (14.11.2026): neue eigene Unterhaltung mit der Vorlage „Diktat als Brief gliedern“ (fehlt sie, gilt `chat.DIKTAT_ANWEISUNG`) und der Abschrift als Klartext. Nur abgeschriebene Diktate in Akten, die die Person sehen darf (sonst 400/404). Protokoll `diktat_gliedern` ohne Inhalt |
| `POST chats/{id}/nachricht/` `{"text": "…", "vorlage": ID, "dokumente": [ID]}` oder multipart mit `dateien` | berichte | höchstens 100 000 Zeichen; Text oder Anhang nötig. `dokumente`: Dokumente aus Akten, die die Person sehen darf (lesbar: PDF, Bilder; Protokoll `chat_dokument_aus_akte` mit Patient und Dokument). `dateien`: bis 20 Dateien je `EPM_UPLOAD_MAX_MB`, keine Seitengrenze. 409, solange die letzte Antwort noch aussteht |

Anhänge (`nachrichten[].anhaenge`: `name`, `herkunft` upload/akte, `seiten`, `seiten_fertig`, `status` wartet/fertig/fehler)
erkennt der KI-Dienst vor der Antwort (aus der Akte: schon erkannter Text wird übernommen); eine hochgeladene Datei
wird danach gelöscht, nur der Text bleibt mit dem Chat. `schritt` der KI-Nachricht zeigt, was gerade passiert
(„Seite 3 von 40 wird gelesen“, „Teil 2 von 5“). Passen die Unterlagen nicht in den Kontext (`KI_KONTEXT`), liest das
Modell sie Teil für Teil und antwortet aus den Auszügen.
| `GET vorlagen/[?alle=1]` | ansehen oder `vorlagen_pflegen` | Promptvorlagen (`name`, `beschreibung`, `anweisung`, `temperatur` 0–1, `aktiv`, `reihenfolge`, `mitgeliefert`) |
| `POST vorlagen/` · `PATCH vorlagen/{id}/` · `DELETE vorlagen/{id}/` | `vorlagen_pflegen` | Oberfläche: Administration › Vorlagen › KI-Prompts; mitgelieferte nur ausblenden, nicht löschen |

## Administration

| Methode und Pfad | Recht | Beschreibung |
|---|---|---|
| `GET stand/` | ansehen | `dienst` (Modus, Grund, Auslastung, Modell bereit, laufend), `nachtfenster`; mit `ki_verwalten` zusätzlich `queue` und aktives `modell` |
| `GET/PUT einstellungen/` | verwalten | Zeitfenster, Zeitzone, Worker Tag/Nacht (≤ `KI_WORKER_MAX`), CPU-/RAM-/Lastgrenzen, Pause bei Sicherung, Altbestand, Seiten, Bildgröße, Schwellen, Verknüpfungsfenster, Aufbewahrung, Training (nur mit dokumentierter Rechtsgrundlage); seit 14.11.2026 auch Priorisierung, Akte auf einen Blick, Diktat-Nachtfenster und Chat-Aufbewahrung (Tabelle unten) |
| `POST rechtsgrundlage/` `{"rechtsgrundlage", "kennwort", "code"}` | training_freigeben | Passwort + zweiter Faktor |
| `GET aufgaben/` · `POST aufgaben/` · `PATCH aufgaben/{id}/` · `DELETE aufgaben/{id}/` | verwalten | Nachtaufgaben (14.11.2026), siehe unten |
| `POST aufgaben/{id}/jetzt/` | verwalten | `jetzt_angefordert = true` – läuft beim nächsten Durchlauf des KI-Dienstes (auch inaktiv) → Aufgabe |
| `GET/POST modelle/` | verwalten | Registry; POST `{name, datei, projektor, sha256, quantisierung}` (nur Dateinamen `*.gguf`) |
| `POST modelle/{id}/evaluieren/` | verwalten | Evaluationslauf (nachts im KI-Dienst) |
| `POST modelle/{id}/aktivieren/` `{"kennwort", "code", "ohne_evaluation"}` | verwalten | Passwort + 2FA; bisher aktives → „vorherige Version“; schreibt `data/ki/modell/aktiv.env` |
| `POST modelle/{id}/sperren/` | verwalten | |
| `GET qualitaet/` | ansehen | Genauigkeit je Bereich, OCR-Fehlerrate, Fehlerarten, Verlauf je Monat, je Modell/Prompt, Sekunden je Seite |
| `GET einrichtung/` | verwalten | Stand auf dem Server (`server`: eingerichtet, Modelldateien, Varianten, Grenzen, `download_erlaubt`), `hardware`, `katalog` (mit `passt`, `empfohlen`, `eingespielt`), `auftraege` (`ki_*`), `uploads`, `upload_max` |
| `POST einrichtung/` `{"aktion": "einrichten" \| "aus" \| "laden" \| "loeschen" \| "grenzen" \| "benchmark", …}` | verwalten | Auftrag an den Systemagenten. `laden`: `variante` aus dem Katalog; `loeschen`: `datei` (nicht das aktive Modell); `grenzen`: `KI_SPEICHER`, `KI_WORKER_SPEICHER`, `KI_THREADS`, `KI_WORKER_MAX`; `benchmark`: `eigene`. Passwort + 2FA (`kennwort`, `code`) außer bei `grenzen` und `benchmark` |
| `POST hochladen/` `{"name": "*.tar", "groesse"}` · `PUT hochladen/{kennung}/?versatz=` · `DELETE hochladen/{kennung}/` | verwalten | Modell-Paket in Stücken (wie Update-Paket, max. 64 GB) |
| `POST hochladen/{kennung}/einspielen/` `{"kennwort", "code"}` | verwalten | vollständiges Paket an den Agenten (`epm-ki einspielen`) |
| `GET benchmarks/` | verwalten | letzte 10 Benchmarks (`data/ki/benchmark-*.json`) |
| `GET evaluation/` · `POST evaluation/` `{"aktion": "erzeugen"}` / `{"aktion": "training_freigeben", "faelle": [ids]}` | verwalten bzw. training_freigeben | Evaluationsfälle (pseudonymisiert), Läufe, Trainingsfreigabe |

### Neue Einstellungen (14.11.2026)

| Feld | Standard | Grenzen | Bedeutung |
|---|---|---|---|
| `prio_angefordert` | 10 | 0–100, **größer als alle anderen `prio_*`** | ausdrücklich angefordert („jetzt verarbeiten“, „Erneut verarbeiten“); Tagesbetrieb mit `worker_tag = 0` nimmt nur Vorgänge ab dieser Priorität. Ändert sie sich, werden wartende Vorgänge umgestellt (angeforderte bleiben angefordert, die übrigen darunter) |
| `prio_termin` / `termin_tage` | 8 / 3 | 0–100 / 0–30 (0 = aus) | Dokumente von Akten mit Praxistermin zwischen heute und heute + `termin_tage` |
| `prio_neu` / `neu_tage` | 5 / 7 | 0–100 / 1–90 | neu hochgeladene Dokumente |
| `prio_neu_lesen` | 3 | 0–100 | „Neu lesen“ (Nachtaufgabe, `vorgaenge/neu_lesen/`) |
| `prio_altbestand` | 0 | 0–100 | Altbestand |
| `chat_vorrang` | true | | tagsüber hält ein wartender Chat alle anderen Aufträge an |
| `zusammenfassung_tagsueber` | true | | „Akte auf einen Blick“ auf Anforderung auch tagsüber |
| `zusammenfassung_ohne_termin_tage` | 90 | 7–730 | Zeitraum ohne früheren Termin und ohne Kontakt |
| `diktat_nacht_beginn` / `diktat_nacht_ende` | 21 / 7 | 0–23 | Nachtfenster der Diktate „heute Nacht“ (Startwert `EPM_DIKTAT_NACHT`) |
| `chat_tage` | 30 | 1–365 | KI-Chats ohne Änderung danach löschen (Startwert `EPM_KI_CHAT_TAGE`) |

Fehlerfall wie bisher: ein fehlgeschlagener Versuch senkt die Priorität auf ≤ 0.

### Nachtaufgaben (`aufgaben/`, 14.11.2026)

```json
{"id": 1, "name": "Akte auf einen Blick für die Termine von morgen", "art": "zusammenfassung_termine",
 "art_name": "Akte auf einen Blick für die nächsten Termine", "aktiv": true, "wochentage": [0, 1, 2, 3, 4, 5, 6],
 "uhrzeit": "03:00", "parameter": {"tage_voraus": 1}, "naechster_lauf": "2026-11-15T03:00:00+01:00|null",
 "letzter_lauf": "…|null", "letztes_ergebnis": "12 Zusammenfassungen eingereiht", "jetzt_angefordert": false,
 "geaendert_am": "…", "geaendert_von_name": "…|null"}
```

POST/PATCH mit `name`, `art`, `aktiv`, `wochentage` (0 = Mo … 6 = So, nicht leer), `uhrzeit` (`HH:MM`, Zeitzone der
Einstellungen), `parameter` (fehlende mit Standard ergänzt, unbekannte entfallen). Fehler der Parameter unter
`parameter.<feld>` (bzw. `parameter`). Arten:

- `zusammenfassung_termine` `{"tage_voraus": 1}` (1–14): je Akte mit Praxistermin zwischen heute und heute + n eine
  Zusammenfassung (`grund=termin`), sofern für diesen Termin noch keine fertige/wartende existiert.
- `neu_lesen` `{"seit_tagen": 30, "dokumenttypen": [], "nur_anderes_modell": true, "hoechstens": 200}` – wie
  `vorgaenge/neu_lesen/` (ohne Firmenfilter).
- `dokumente_vormerken` `{"altbestand": true}` – Dokumente in die Queue (bis 5000 je Lauf).

`naechster_lauf` kann in der Vergangenheit liegen (fällig, läuft beim nächsten Durchlauf). Eine Aufgabe, die nach ihrer
Uhrzeit angelegt oder geändert wurde, läuft erst zum nächsten Termin. Audit: `aufgabe_angelegt`, `aufgabe_geaendert`,
`aufgabe_geloescht`, `aufgabe_jetzt`; der KI-Dienst `aufgabe` (mit `aufgabenart`, Ergebnis ohne Inhalte).

## Geändert außerhalb von `/api/ki/`

- `GET/POST/PATCH /api/laborbefunde/`: neues optionales Feld `abgenommen_um` (Uhrzeit der Entnahme, `HH:MM:SS`).
- `GET /api/protokoll/?gruppe=ki`: neue Gruppe „KI“ im Audit-Log.
- `GET /api/rechte/`: sechs neue Rechte `ki_*`.
- Systemagent: neue Aktionen `ki_modelle`, `ki_modell_laden`, `ki_modell_loeschen`, `ki_einrichten`, `ki_aus`,
  `ki_grenzen`, `ki_benchmark` (nur über `/api/ki/einrichtung/`, nicht in Administration › System); `system.json`
  enthält `ki`; Upload-Art `ki`.
