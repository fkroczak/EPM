# EPM – Elektronisches Patienten-Management

| Ordner | Inhalt |
|---|---|
| `backend/` | Django-Backend (siehe `backend/README.md`) |
| `frontend/` | Oberfläche: React, TypeScript, Vite, Tailwind, Base UI (Bausteine im Stil von shadcn/ui), TipTap; Browsertests in `frontend/e2e/` (Playwright) |
| `rollout/` | Server-Einrichtung: `01-basis.sh` … `05-backend.sh`, Compose, Nginx |
| `werkzeuge/` | `epm-update.sh` (Update in einem Schritt), `ci-stack.sh` (kompletter Stack für die Browsertests), `epm-git-einrichten.sh`, `bauen.sh`/`bauen.ps1`, `hilfe-bilder.mjs` (Bilder der Hilfe) |
| `docs/PERFORMANCE-PRUEFUNG-2026-11-14.md` | Ladezeiten vorher/nachher, Skelett-Platzhalter, Vorladen, weniger Datenbankabfragen; Messwerkzeuge in `werkzeuge/performance/` |
| `docs/BACKEND-FUNKTIONEN.md` | Nachweis aller Funktionen mit API-Verträgen, Tests und Status |
| `VERSION` | Grundstand der Versionsnummer (X.Y.Z). Die letzte Stelle zählt automatisch je Änderung auf main hoch (`werkzeuge/version.sh`: 2.0.0 + 3 Merges = 2.0.3); neue Funktionen bzw. Hauptversion: VERSION von Hand auf 2.1.0 bzw. 3.0.0 setzen, die Zählung beginnt neu. Die Images heißen `epm-backend:<Version>-<Commit>` und `epm-web:<Version>-<Commit>` |

## Images

- `epm-backend` – Django mit Gunicorn (`backend/Dockerfile`); dasselbe Image läuft als OCR-Dienst (Compose-Dienst `ocr`,
  Menüpunkt „Scans“). Die Texterkennung arbeitet nur auf dem Server: Tesseract mit dem deutschen Modell liegt im Repo,
  die PP-OCRv5-Modelle lädt der Bau von `huggingface.co` (Proxy-Freigabe; ohne Zugang entsteht das Image trotzdem und
  erkennt nur mit Tesseract – Administration › System zeigt es). **Offline nachreichen:** auf einem PC mit Internet
  `werkzeuge/ocr-modelle.sh vorbereiten` (Windows: `werkzeuge\ocr-modelle.ps1`) → Datei per `scp` auf die Test-VM →
  `sudo epm-ocr-modelle einspielen DATEI.tar` → `sudo epm-update` (baut das Image mit den Modellen neu;
  `sudo epm-ocr-modelle status` zeigt den Stand) – oder in EPM unter Administration › System › Software
  „OCR-Modelle einspielen“ (Datei hochladen statt scp) und danach „EPM aktualisieren“
  Auf Servern mit wenig RAM (unter 6 GB) arbeitet die Texterkennung automatisch im Sparmodus (kleines Zeilenmodell,
  ohne Glätten); Speichergrenze und Rechenkerne des OCR-Dienstes trägt `04-projekt.sh` einmalig nach dem Server in
  `/srv/epm/.env` ein (`EPM_OCR_SPEICHER`, `EPM_OCR_THREADS`, Modus erzwingen mit `EPM_OCR_MODUS=voll|sparsam`)
- `epm-web` – Nginx mit dem gebauten Frontend (`frontend/Dockerfile`). Zum Bauen braucht der Server Zugang zu
  `registry.npmjs.org` (Proxy-Freigabe); ohne Zugang die Images mit `werkzeuge/bauen.sh` auf einem anderen Rechner bauen
  und als `epm-<VERSION>.tar` mit `rollout/05-backend.sh` einspielen.

## KI (Experimentell) (14.10.2026)
Lokale, offline lauffähige KI für die Akten: liest die Dokumente der Akten nachts (Standard 21:00–07:00) nur lesend,
erkennt Text (Tesseract/PP-OCR + Vision-Modell Qwen3.5-4B über llama.cpp, nur CPU), strukturiert Metadaten, Laborwerte,
Infusionspläne, Medikation, Diagnosen und Texte und legt alles in die Prüf-Queue (Menü „KI (Experimentell)“). In die Akte
kommt nur, was ein Mitarbeiter prüft und bestätigt. Dazu: Hinweise Labor ↔ Infusionsplan (Akte › KI), Berichtsentwürfe
auf Anforderung, Qualitäts-Dashboard, Modellwechsel mit Evaluation und Rollback (Administration › KI).
**Chat** (12.11.2026): Reiter „Chat“ im Menü KI (Experimentell) – Texte medizinisch formulieren, prüfen, kürzen …
mit festen Promptvorlagen (Administration › Vorlagen › KI-Prompts); jede Person sieht nur ihre eigenen Chats. Tagsüber wartet die KI nur auf Eingaben: das Modell bleibt
geladen, der Chat hat Vorrang, Hintergrundarbeit nur im Nachtfenster. Im Chat lassen sich Dokumente hochladen oder aus
einer Akte wählen (ohne Seitengrenze; lange Unterlagen liest die KI Teil für Teil, Kontext `KI_KONTEXT`).
**Lernt aus Korrekturen** (14.11.2026): frühere Korrekturen der Prüfansicht gehen als Beispiele in den Prompt (kein
Training; Administration › KI › „Korrekturen als Beispiele“). **Diktat → Brief**: „Mit KI gliedern“ am abgeschriebenen
Diktat macht daraus einen gegliederten Entwurf mit Prüfmarken. **Akte auf einen Blick**: Zusammenfassung seit dem
letzten Termin mit Quellenmarken (nachts für die Termine von morgen vorbereitet). Unter Administration › KI sind
jetzt auch **Priorisierung** (u. a. Vorrang für Patienten mit Termin), **Nachtaufgaben** (Zeitplan) und **Neu lesen**
mit dem aktiven Modell einstellbar.
Einrichten, Modell wählen, laden bzw. hochladen, Grenzen, Benchmark und Ausschalten gehen nach „EPM aktualisieren“
auch ohne SSH unter Administration › KI › Einrichtung.

```bash
werkzeuge/ki.sh vorbereiten Q4_K_M Q8_0 --mit-image   # PC mit Internet → epm-ki-modelle-<Datum>.tar
sudo epm-ki einspielen ~/epm-ki-modelle-<Datum>.tar  # Server: Prüfsummen, Modelle, Image
sudo epm-ki pruefen                                  # Hardware und Empfehlung
sudo epm-ki einrichten                               # Secrets, Grenzen, compose.ki.yaml, Container, Modell
sudo epm-ki benchmark                                # Varianten messen (nachts)
sudo epm-ki status | aus
```
Unter 12 GB RAM / 4 Kernen bleibt der KI-Dienst von selbst aus. Plan: [`docs/KI-ERWEITERUNG-PLAN-2026-10-14.md`](docs/KI-ERWEITERUNG-PLAN-2026-10-14.md),
Betrieb: [`docs/KI-BETRIEB.md`](docs/KI-BETRIEB.md), API: [`docs/KI-API.md`](docs/KI-API.md), Datenschutz: [`docs/DATENSCHUTZ.md`](docs/DATENSCHUTZ.md) § 7.

## Dreisprachigkeit der Regeneration Clinic (18.11.2026)
In der Firma RGC lässt sich die Oberfläche mit den **Flaggen in der Kopfzeile** auf Deutsch, Englisch oder Lettisch
umstellen (gespeichert im Benutzerkonto, `ich.sprache`; die DSKM bleibt deutsch). Übersetzt sind bisher Menü, Seitentitel,
Reiter der Akte und alles rund ums Labor; weitere Bereiche folgen schrittweise (`frontend/src/lib/uebersetzungen.ts`,
deutscher Text = Schlüssel). **Laborparameter** haben neben dem deutschen Namen einen englischen und lettischen
(`name_en`, `name_lv`); Werte hängen am Parameter, nicht am Namen – „Fosfors“ und „Phosphat“ sind derselbe Wert.
Scans und KI erkennen lettische und englische Befunde über alle drei Namen und das Wörterbuch
`backend/stammdaten/laborbegriffe.py` (z. B. „Hemoglobīns“, „MCV Eritroc.vid.tilp.“ → vorhandener deutscher Parameter,
ohne neue Parameter). Unter Vorlagen › Laborparameter: **Exportieren/Importieren (CSV)** mit Vorschau und
**Aus RGC-Vorlagen übernehmen** (alle Ankreuzzeilen der Laboranforderungen und -profile; neue Parameter nur nach
Anhaken). Details: [`docs/DREISPRACHIGKEIT-RGC-2026-11.md`](docs/DREISPRACHIGKEIT-RGC-2026-11.md).

## Freigaben (16.11.2026)
Menüpunkt **Freigaben**: alles, was ein Mensch freigeben muss, an einer Stelle – Datenpflege aus dem Altbestand,
Infusionsplan-Entwürfe (Recht „Infusionspläne freigeben“) und der Weg zur KI-Prüfung. **Datenpflege**: Regeln lesen
Freitext der Akten (Telefon mit Namen dahinter, Hausarzt/Überweisung mit Adresse, „Hinweise aus der
Altdaten-Übernahme“) und bereiten Schritte vor – Bezugsperson mit Beziehung und Nummer anlegen, Arzt aus der Ärzteliste
zuordnen (vorhandener Treffer oder neu), Telefonfeld bereinigen, erledigten Hinweis entfernen. Unsichere Vorschläge
(z. B. „Ehefrau“ nur vermutet) liest nachts das lokale KI-Modell gegen; es ändert nur den Vorschlag, nie die Akte
(DB-Rolle `epm_ki`). Jeder Vorschlag zeigt vorher → Schritte → nachher, jeder Schritt ist abwählbar und bearbeitbar.
**Freigeben** setzt erst nach 60 Sekunden um („Rückgängig“ bis dahin); umgesetzt wird mit den Rechten der freigebenden
Person, im Audit-Log und im Verlauf der Akte. „Altbestand durchsuchen“ erstellt Vorschläge sofort, der OCR-Dienst
alle 6 Stunden. Code: `backend/freigaben/`, Seite `frontend/src/seiten/Freigaben.tsx`.
Erweiterungen (16.11.2026): **Sammelfreigabe** „Alle eindeutigen freigeben“ (nur Vorschläge ohne offene Frage, ein
gemeinsames Rückgängig); **doppelte Ärzte zusammenführen** (gleicher Name ohne Titel, Telefon oder E-Mail; Werte je
Feld wählbar, Zuordnungen werden umgehängt, der Rest deaktiviert); **weitere Import-Hinweise** (Größe, E-Mail,
Name/Adresse vollständig; was kein Feld hat, kommt als Eintrag in die Karteikarte); **„+“/„INAKTIV“ im Namen**: Name
bereinigen und Akte abschließen – Anlass und Datum aus den letzten 5 Kontakten (Regeln, nachts KI mit wörtlichem
Zitat), Unklares wird abgefragt, ein Abschluss kommt nie in die Sammelfreigabe; **Lernen aus Korrekturen**
(Beziehung, gewählter Arzt, abgewählte Schritte, Anlass – ab 3 gleichen Entscheidungen vorbelegt, ab 5 eindeutig).
Neue Rechte (Benutzer › Rechte › „Freigaben und Datenpflege“, Standard ab Mitarbeiter): „Datenpflege freigeben“ und
„Sammelfreigabe“; jeder Schritt verlangt zusätzlich sein eigenes Recht (z. B. Akten abschließen, Ärzte pflegen).

## Diktate (23.10.2026)
Im Bericht (Arztbrief, Konsultationsbericht …) und im Kommentar des Infusionsplans: **Diktat aufnehmen** → im Browser
sprechen (PC, Mac, Handy im VPN) → „sofort“ oder „heute Nacht“, „ich selbst“ oder „Sekretariat“ → der OCR-Dienst schreibt
offline ab (whisper.cpp, nur CPU, Modell ≈ 550 MB in `scans/modelle/modelle.json`, kommt wie die OCR-Modelle ins Image
bzw. offline mit `werkzeuge/ocr-modelle.sh`). Nachhören mit markierten unsicheren Wörtern, „In den Text übernehmen“,
freigeben wie bisher – die PDF hat das Layout der Stiftung, die Aufnahme wird dabei gelöscht. Abgegebene Diktate stehen
im Menü **Diktate**; dort lässt sich auch ohne Akte diktieren (Patient und Berichtsart wählen, 26.10.2026). Recht „Diktieren“ (Standard Mediziner). Details: `docs/BACKEND-FUNKTIONEN.md` F192,
`docs/DATENSCHUTZ.md` § 8. Nachtfenster unter Administration › KI › Zeitfenster (`EPM_DIKTAT_NACHT=21-7` nur noch Startwert), Rechenkerne `EPM_DIKTAT_THREADS` (sonst
`EPM_OCR_THREADS`). Der OCR-Dienst braucht dafür mindestens `EPM_OCR_SPEICHER=3g` (Server ab 6 GB RAM).

## Dokumentenautomation der Regeneration Clinic (26.10.2026)
In der Firma RGC gibt es in der Akte den Reiter **Fälle**: Ein Behandlungsfall ist die eine Datenquelle für alle
Dokumente (Patientenerklärungen und Formulare 01–12, Zusatzbögen zu 07, OP-Bericht, Entlassungsbrief, Konsil, Rechnung –
DE/LV/EN). Je Kostenträgertyp entsteht das Dokumentenpaket automatisch. Solange ein Dokument nicht unterschrieben bzw.
signiert ist, lassen sich Falldaten und Rechnungspositionen ändern und die PDF neu erzeugen; jede Erzeugung ist eine
eigene, unveränderliche Fassung. Finalisieren: elektronische Signatur (fortgeschritten, Zertifikat der Person), extern
signierte PDF, Scan der Papierunterschrift oder ausdrücklich; finale Rechnungen werden storniert und neu erzeugt.
Leistungskatalog, Kostenträgertypen mit Paketen, Kooperationspartner und Unterschriftsberechtigte unter
Administration › **Fälle und Abrechnung**. Recht „Fall-Dokumente finalisieren“ (Standard Mediziner).
Details: [`docs/DOKUMENTENAUTOMATION-RGC-2026-10.md`](docs/DOKUMENTENAUTOMATION-RGC-2026-10.md).

## Server ohne SSH warten (10.10.2026)
Unter **Administration › Systemverwaltung** stehen Zustand (Ampel) und die häufigen Aufgaben; alles Weitere unter
Administration › System (Reiter Wartung, Software, Zertifikat, Protokolle) und › Backup. Updates, Neustart, Dienste,
Zurückschalten, Update-Pakete, OCR-Modelle, Zertifikat, Protokolle und Sicherungen laufen über den Systemagenten –
gefährliche Aktionen mit Passwort und zweitem Faktor, alles im Audit-Log. SSH braucht es nur noch für die
Ersteinrichtung des Servers (`rollout/01…05`, `epm-git-einrichten.sh`, einmalig `epm-zertifikat einrichten`) und wenn
der Systemagent selbst nicht läuft.

### SSH und Firewall (11.10.2026)
SSH ist im Betrieb geschlossen. Unter **Administration › System › Zugang** öffnet ein Admin es für 1, 4 oder 8 Stunden
(Passwort und zweiter Faktor, wahlweise nur für die eigene Adresse); danach schließt der Server es selbst. **Notzugang**
ohne SSH: die Konsole der VM im Hypervisor (z. B. Proxmox/VirtualBox). Dort stehen auch die erlaubten Netze für EPM und
SSH (Liste in `/etc/epm/zugang.json`), der „Netzfilter für EPM“ (Docker umgeht ufw bei Port 443), die Firewall-Regeln und
die von Fail2ban gesperrten Adressen.

- **Ersteinrichtung:** `rollout/03-security.sh` lässt SSH dauerhaft offen. Sobald EPM läuft: Administration › System ›
  Zugang › **Jetzt schließen**. Ein erneuter Lauf von `03-security.sh` trägt die gespeicherten Netze wieder ein
  (`epm-systemagent zugang-anwenden`) und öffnet SSH wieder dauerhaft.
- **Bestehende Server:** nach dem Update bleibt SSH offen („dauerhaft offen (Ersteinrichtung)“) – niemand wird
  ausgesperrt. Bitte einmal schließen; den Netzfilter für EPM nach Prüfung der Netze einschalten.
- Gedacht ist EPM nur für das interne Netz hinter dem VPN („Nur im VPN erreichbar“). Für ein Testsystem mit Zugang aus
  dem Internet lässt sich für EPM „Alle Adressen (0.0.0.0/0)“ eintragen; für SSH nie.

Uhrzeit: Zeitzone, Zeitsynchronisation und eigener Zeitserver (ohne Internet z. B. die OPNsense; sonst
`EPM_NTP_SERVER` in `/etc/epm/epm.conf` bei der Ersteinrichtung) unter Administration › System › Wartung › Uhrzeit.

## Selbstheilung (13.10.2026)
Der Server hält EPM ohne Eingriff am Laufen; Stand und Eingriffe unter **Administration › System › Wartung ›
Selbstheilung** (Audit-Log: Benutzer „systemagent“).

- **Gute Version:** `epm-update` merkt sich in `/srv/epm/.env` neben `EPM_VERSION` die zuletzt bewährte Version
  `EPM_VERSION_GUT`. Eine neue Version wird erst zur guten, wenn das Backend gesund ist, die Musterdaten stimmen und
  – wenn sie laufen – die Tests bestanden sind; ihre Images bleiben beim Aufräumen immer erhalten. Von Hand:
  `sudo epm-update --gut [TAG]` oder in EPM „Als gute Version bestätigen“.
- **Rückfall beim Update:** Startet die neue Version nicht (Backend nach 3 Minuten nicht gesund), zeigt `epm-update` die
  Container-Meldungen, schaltet selbst auf die gute Version zurück und bricht mit einer klaren Meldung ab; gleiches
  gilt für `--paket`. Datenbank-Migrationen werden dabei nicht zurückgedreht – läuft die gute Version damit nicht sauber,
  die Sicherung von vor dem Update wiederherstellen. Die Markierung `system/rueckfall.json` wird in EPM zum Hinweis an
  alle Benutzer.
- **Wächter jede Minute** (im Status-Lauf des Systemagenten, Zustand in `system/heilung.json`): fehlender oder
  beendeter Container → `docker compose up -d`; dreimal in Folge „unhealthy“ → `docker compose restart` (höchstens
  einmal je Dienst in 5 Minuten); Backend nach 3 Neustarts in 30 Minuten weiter ungesund und eine andere gute Version
  vorhanden → `epm-update --zurueck` auf die gute Version mit Hinweis an alle; Platte unter 1 GB oder 5 % frei → Hinweis
  und nur `docker image prune` (hängende Images). Während `epm-update` läuft (`system/update-laeuft`), während eines
  Auftrags und in den ersten zwei Minuten nach dem Booten hält er still.
- **Ausschalten für Wartung von Hand:** Knopf in EPM oder `touch /srv/epm/system/heilung-aus`; danach wieder einschalten.
- **Boot:** `epm.service` versucht den Start bei Fehlschlag alle 20 s erneut (ab systemd 253); der Status-Timer läuft
  unabhängig davon.
- **Wartungsseite:** Antwortet das Backend nicht (502/503/504), zeigt Nginx `wartung.html` („EPM startet gerade neu“,
  lädt alle 30 s neu); `/api/`-Anfragen bekommen JSON `{"fehler": …}`, das die Oberfläche als Meldung zeigt.

## Test-VM aktualisieren
Oder in EPM unter Administration › System: „EPM aktualisieren“ (Wartung), Versionen und „Zurückschalten“, „Update-Paket
erstellen“ (Software).
```bash
sudo epm-update                # holen, bauen (Backend und Frontend), Backup, starten, Musterdaten, Tests
sudo epm-update --versionen    # vorhandene Versionen
sudo epm-update --zurueck TAG  # zurückschalten (beide Images)
sudo epm-update --gut [TAG]    # laufende (oder genannte) Version als gute Version bestätigen (Selbstheilung)
sudo epm-update --paket-erstellen  # Update-Paket der laufenden, getesteten Version für den VPS
```

## VPS ohne Internet (Festlegung 02.10.2026)
Der VPS bekommt keine Verbindung zu GitHub und baut nichts selbst: In `/etc/epm/epm.conf` steht
`EPM_UPDATE_QUELLE="paket"`. Auf der Test-VM erzeugt `sudo epm-update --paket-erstellen` aus der dort laufenden und
getesteten Version eine Datei `epm-paket-<TAG>.tar` (Images, Rollout-Dateien, Systemagent, `epm-update`, Prüfsummen).
```bash
scp /srv/epm/images/epm-paket-<TAG>.tar epmadmin@VPS:~/      # vom PC bzw. der Test-VM
sudo epm-update --paket ~/epm-paket-<TAG>.tar                 # auf dem VPS: prüfen, Backup, umstellen, Tests
```
Oder ohne scp und SSH: auf der Test-VM unter Administration › System › Software „Update-Paket erstellen“ und
herunterladen, auf dem VPS dort „Update-Paket einspielen“ (hochladen, SHA-256 vergleichen, mit Passwort und 2FA
bestätigen).

**Signatur der Update-Pakete (seit 17.10.2026).** Ein Paket bringt Skripte mit, die auf dem VPS als root laufen. Die
Test-VM signiert deshalb die Prüfsummen jedes Pakets mit `/etc/epm/paket-signatur` (legt `epm-update` beim ersten
Paket von selbst an) und legt den öffentlichen Schlüssel bei. Der VPS prüft die Signatur, bevor er etwas auspackt oder
ausführt. Einzurichten ist nichts: Das erste gültig signierte Paket legt den Schlüssel auf dem VPS fest
(`/etc/epm/paket-vertraut.pub`, „trust on first use“, Eintrag im Audit-Log); danach nimmt er nur noch Pakete mit
demselben Schlüssel an. Beide Fingerabdrücke stehen unter Administration › System › Software › „Paket-Schlüssel“.

Ist der Schlüssel der Test-VM verloren (neu aufgesetzt), dort „Zurücksetzen“ (Rolle Admin, Passwort und zweiter
Faktor). Der Systemagent löscht den gespeicherten Schlüssel erst 24 Stunden später; bis dahin sehen alle Benutzer einen
Hinweis, und „Zurücksetzen abbrechen“ behält ihn. Antrag, Abbruch und Ausführung stehen im Audit-Log. Danach legt das
nächste Paket den Schlüssel neu fest. Restrisiko (bewusst in Kauf genommen): Wer das Backend übernimmt, kann vor dem
ersten Paket oder nach einem nicht bemerkten Zurücksetzen ein eigenes Paket einschleusen – deshalb den Hinweis ernst
nehmen und die Fingerabdrücke vergleichen. Alte, unsignierte Pakete nimmt der VPS nur auf der Konsole und nur ohne
gespeicherten Schlüssel an (`sudo epm-update --paket DATEI --ohne-signatur`).

Die Konfiguration des Servers liegt in `/etc/epm/epm.conf` (nicht im Repo). Die Oberfläche ist danach unter
`https://<EPM_WEB_NAME>/` erreichbar, die Django-Verwaltung unter `/verwaltung/` (nur Rolle Admin) und die API-Ansicht im Browser sind standardmäßig aus.
Zur Fehlersuche schaltet ein Admin sie unter Administration › System › Wartung › „Technische Verwaltung“ für 1 oder
8 Stunden ein (danach von selbst aus, Eintrag im Audit-Log). `EPM_DJANGO_ADMIN=0/1` bzw. `EPM_API_BROWSABLE=0/1` in
`/srv/epm/backend.env` legen sie fest; `epm-update` entfernt die Werte einmalig, damit der Schalter gilt.

## Zertifikat und Passkeys
Passkeys (zweiter Faktor mit Fingerabdruck, Gesicht oder PIN) gehen nur über einen Namen mit einem Zertifikat, dem die
Geräte vertrauen – nicht über die IP-Adresse. Dafür gibt es eine eigene CA (nur für den EPM-Namen gültig):
```bash
sudo epm-zertifikat einrichten   # CA + Serverzertifikat für EPM_WEB_NAME, Nginx lädt neu
sudo epm-zertifikat status       # Name, Aussteller, Ablauf (Serverzertifikat 397 Tage: jährlich „erneuern“)
```
Das Stammzertifikat liegt unter `https://<EPM_WEB_NAME>/epm-ca.crt` (für iPhone/iPad als Profil
`/epm-ca.mobileconfig`, schreibt `epm-zertifikat` bei jedem Einrichten/Erneuern/Importieren; auf bestehenden Servern
einmal `sudo epm-zertifikat erneuern` bzw. `importieren`, sonst baut der Browser das Profil selbst) und wird einmal je
PC/Telefon installiert – zum Herunterladen für alle unter Mein Konto › Gerät einrichten und auf der Anmeldeseite
(Anleitung in EPM unter Hilfe › „Passkey statt Code“). Den Namen auf der OPNsense per Unbound-Überschreibung auf die
Server-IP zeigen lassen. Ein Zertifikat einer anderen CA (z. B. der OPNsense): `sudo epm-zertifikat importieren CRT KEY CA`.
Status, Erneuern und Importieren gehen auch in EPM unter Administration › System › Zertifikat; nur das erstmalige
Einrichten der eigenen CA (`epm-zertifikat einrichten`) bleibt Teil der Ersteinrichtung per SSH.

## Datensicherung
Täglich um 02:00 (`epm-backup.timer`; Uhrzeit und „täglich/werktags“ in EPM unter Administration › Backup › Zeitplan,
als Drop-in `epm-backup.timer.d/zeitplan.conf`), 30 Tage auf dem Server unter `/srv/epm/backup` (unter Administration › Backup
auf 7, 14 oder 30 Tage einstellbar). Gesteuert wird alles unter
Administration › Backup: Passwort für die Verschlüsselung festlegen und das Passwortblatt im Tresor verwahren,
Übertragungsziel (WebDAV, z. B. Nextcloud mit App-Passwort) mit Zeitfenster, „Jetzt sichern“, Wiederherstellen (eigenes
Passwort und Code aus der Authenticator-App – die Zwei-Faktor-Anmeldung ist dafür nötig), Sicherung als eine Datei herunterladen und
wieder hochladen (z. B. von der Migrationsmaschine; Austausch über `/srv/epm/system/download` und `…/upload`). Passwort und Zugang liegen nur auf dem Server in `/etc/epm/sicherung` (root, 0600). Die Adresse des
Ziels muss im Proxy der OPNsense freigegeben sein. Nicht mehr gebrauchte Sicherungen lassen sich in der Liste ankreuzen
und gesammelt löschen (die jüngste bleibt immer); Protokolle der nächtlichen Sicherung und der Übertragung stehen unter
Administration › System › Protokolle. Ohne EPM entschlüsseln: `gpg -d -o epm-db_….dump epm-db_….dump.gpg`.

## Notfallpaket und Wiederaufbau (10.10.2026)
Administration › System › Notfall › „Notfallpaket erstellen“ (Passwort und zweiter Faktor) packt alles für einen
Neuaufbau ohne Internet in `epm-notfall-<TAG>-<Datum>.tar`: Images, Rollout-Skripte, Debian-Pakete, OCR-Modelle,
wahlweise die jüngste Sicherung, Einstellungen ohne Geheimnisse, CA (Schlüssel mit dem Sicherungs-Passwort
verschlüsselt), `SHA256SUMS`, `INHALT.json` und den Plan. Nach jedem Update und spätestens alle 30 Tage neu erstellen,
zwei Kopien getrennt lagern. Aufbau auf frischem Ubuntu Server: auspacken, im Ordner `sudo ./epm-notfall-aufbau.sh`
(`--probelauf` zeigt nur, was geschähe); die Rollout-Skripte laufen dabei mit `EPM_OFFLINE=1`. Plan:
[`docs/NOTFALLPLAN.md`](docs/NOTFALLPLAN.md).

## Bilder der Hilfe (11.10.2026)
Die Hilfe zeigt Bildschirmfotos und kurze GIFs (Wunsch 11.10.2026). Sie liegen in `frontend/public/hilfe-bilder/`
(Auslieferung unter `/hilfe-bilder/…`, im Image mit dabei) und stehen in `backend/hilfe/inhalt.py`. Neu erzeugen, z. B.
nach Änderungen an der Oberfläche – EPM muss laufen (Entwicklung: Vite auf 127.0.0.1:5173 mit Django):

```bash
cd frontend && npm ci && cd ..                       # Playwright aus frontend/node_modules
EPM_KENNWORT=… [EPM_CODE=…] node werkzeuge/hilfe-bilder.mjs          # alle Bilder
node werkzeuge/hilfe-bilder.mjs kontakt telefon                      # nur Bilder mit diesen Namen
```

Angemeldet wird mit einem **Testbenutzer** (Vorgabe `hilfe.bilder`, Rolle Mediziner), der nur die Testpatienten sieht –
das Werkzeug bricht bei anderen Konten ab. Die Sitzung bleibt in `werkzeuge/.hilfe-bilder-sitzung.json` (nicht im Repo).
Weitere Einstellungen: `EPM_URL` (Vorgabe `http://127.0.0.1:5173`), `EPM_BENUTZER`, `EPM_CHROMIUM` (Vorgabe
`/opt/pw-browsers/chromium`, leer = Chromium von Playwright), `EPM_PYTHON` (Python mit Pillow für GIFs und Verkleinern,
`werkzeuge/hilfe-gif.py`). Gespeichert wird nichts: Fenster werden nur geöffnet und mit Escape verworfen. Am Ende steht
eine Liste mit Größe und Maßen; ändern sich Maße, `width`/`height` in `inhalt.py` anpassen – der Test
`patienten.test_startseite.Hilfe` prüft Dateien, Alternativtexte und Seitenverhältnisse.

## Tests
Bei jedem Push laufen in GitHub Actions (`.github/workflows/backend.yml`), alle Teile gleichzeitig auf eigenen Rechnern
(Ziel: der ganze Lauf in unter 5 Minuten):
1. Backend-Tests gegen PostgreSQL 18 (`backend/*/tests.py`) in 4 Teilen (`EPM_TESTTEIL=2/4`, aufgeteilt nach den
   gemessenen Laufzeiten je Testklasse in `backend/epm/testzeiten.json`); fehlende Migrationen werden erzeugt und
   eingecheckt. Laufzeiten neu erfassen: `python3 werkzeuge/testzeiten.py test-ausgabe-*.txt` (Ausgaben der Teile).
2. Browsertests `frontend/e2e/*.spec.ts` (nur auf main und beim manuellen Start) in 12 Teilen (`frontend/e2e/teile.ts`),
   jeder mit eigenem Stack aus `werkzeuge/ci-stack.sh start` (gleiche Compose-Datei, Nginx-Konfiguration und Images wie
   auf dem Server, mit Musterdaten und Testkonten). Eine neue Spec-Datei muss dort einem Teil zugeordnet werden.
   `zz-neustart` prüft in jedem Teil nach einem Neustart die Ergebnisse der Dateien dieses Teils.

Am Commit steht ein Kommentar mit dem Gesamtergebnis, bei Fehlern je Teil ein Kommentar mit den Einzelheiten.

Lokal mit Docker: `werkzeuge/ci-stack.sh start`, dann in `frontend/` `npm ci && npx playwright test` (alle Dateien
nacheinander) oder `EPM_E2E_TEIL=3 npx playwright test` (ein Teil, frischer Stack nötig), zum Schluss
`werkzeuge/ci-stack.sh stop`. Backend: `python manage.py test --parallel auto` (alles) bzw. mit `EPM_TESTTEIL=1/4`.
