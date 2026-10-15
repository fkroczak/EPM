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
| `GET evaluation/` · `POST evaluation/` `{"aktion": "erzeugen"}` / `{"aktion": "training_freigeben", "faelle": [ids]}` | verwalten bzw. training_freigeben | Evaluationsfälle (pseudonymisiert), Läufe, Trainingsfreigabe |

## Geändert außerhalb von `/api/ki/`

- `GET/POST/PATCH /api/laborbefunde/`: neues optionales Feld `abgenommen_um` (Uhrzeit der Entnahme, `HH:MM:SS`).
- `GET /api/protokoll/?gruppe=ki`: neue Gruppe „KI“ im Audit-Log.
- `GET /api/rechte/`: sechs neue Rechte `ki_*`.
