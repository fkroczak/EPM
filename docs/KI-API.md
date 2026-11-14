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

## KI-Chat (12.11.2026)

Jede Person sieht **nur ihre eigenen** Unterhaltungen (auch Admins keine fremden; fremde → 404). Die Antwort schreibt
der KI-Dienst (Vorrang vor Dokumenten und Berichten, auch tagsüber; nicht während einer Pause, z. B. Sicherung).
Systemanweisung = fester Rahmen (`ki/chat.py` `RAHMEN`) + Anweisung der Promptvorlage. Unterhaltungen ohne Änderung
werden nach `EPM_KI_CHAT_TAGE` (Standard 30) gelöscht; im Audit-Log steht nur, dass gechattet wurde, nie der Text.

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
| `GET/PUT einstellungen/` | verwalten | Zeitfenster, Zeitzone, Worker Tag/Nacht (≤ `KI_WORKER_MAX`), CPU-/RAM-/Lastgrenzen, Pause bei Sicherung, Altbestand, Seiten, Bildgröße, Schwellen, Verknüpfungsfenster, Aufbewahrung, Training (nur mit dokumentierter Rechtsgrundlage) |
| `POST rechtsgrundlage/` `{"rechtsgrundlage", "kennwort", "code"}` | training_freigeben | Passwort + zweiter Faktor |
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

## Geändert außerhalb von `/api/ki/`

- `GET/POST/PATCH /api/laborbefunde/`: neues optionales Feld `abgenommen_um` (Uhrzeit der Entnahme, `HH:MM:SS`).
- `GET /api/protokoll/?gruppe=ki`: neue Gruppe „KI“ im Audit-Log.
- `GET /api/rechte/`: sechs neue Rechte `ki_*`.
- Systemagent: neue Aktionen `ki_modelle`, `ki_modell_laden`, `ki_modell_loeschen`, `ki_einrichten`, `ki_aus`,
  `ki_grenzen`, `ki_benchmark` (nur über `/api/ki/einrichtung/`, nicht in Administration › System); `system.json`
  enthält `ki`; Upload-Art `ki`.
