# Sicherheitsprüfung EPM – 11.10.2026

Prüfung im Auftrag des Betreibers: Sind bekannte Schwachstellen geschlossen, und halten Anmeldung, Rechte und die
Trennung der beiden Firmen (DSKM, Regeneration Clinic) gegen gezielte Angriffe? EPM verarbeitet Gesundheitsdaten
(Art. 9 DSGVO); entsprechend streng sind die Maßstäbe.

Stand des Codes: Arbeitskopie vom 11.10.2026 (EPM 2.0.0, Django 5.2.18, DRF 3.18.3). Geprüft wurde lokal mit der
Testsuite und dem Django-Testclient gegen PostgreSQL 16. **Nicht** geprüft werden konnte der echte Server (TLS-Zertifikat,
Firewall, Docker-Images, Sicherungen) – siehe Abschnitt 6.

## 1. Umfang

- Backend (`backend/`): alle API-Endpunkte unter `/api/` (aus den URL-Mustern gelesen: 258 Routen mit zusammen 356 Methoden, ohne Format-Varianten),
  Einstellungen, PDF-Erzeugung, Uploads und Downloads.
- Frontend (`frontend/`): Abhängigkeiten, Stellen, an denen HTML ungeprüft in die Seite kommt.
- Betrieb (`rollout/`): Nginx-Konfiguration, Compose-Datei, Beispiel-Einstellungen, Dockerfiles.

## 2. Methode und Werkzeuge

| Werkzeug | Version | Zweck |
|---|---|---|
| pip-audit | 2.10.1 | bekannte Schwachstellen (PyPI/OSV) in `requirements.txt` und in der installierten Umgebung |
| npm audit | npm 10.9.4, Node 22.22.0 | bekannte Schwachstellen im Frontend (`--omit=dev` und vollständig) |
| bandit | 1.9.4 | statische Analyse des Backends (ohne Tests und Migrationen) |
| `manage.py check --deploy` | Django 5.2.18 | Einstellungen für den Betrieb (DEBUG aus, Geheimnisse aus Dateien) |
| Django-Testclient | – | gezielte Angriffe als Tests, dauerhaft in `backend/epm/test_sicherheit.py` |
| Chromium (Playwright) | 1.63 | Darstellung einer PDF mit dem aktualisierten pdf.js |

Kern der Prüfung ist `backend/epm/test_sicherheit.py`. Die Tests lesen alle Endpunkte aus den URL-Mustern – ein später
hinzugefügter Endpunkt ist damit automatisch mitgeprüft:

- **ohne Anmeldung**, mit **halber Anmeldung** (Passwort richtig, zweiter Faktor offen) und mit **offenem
  Einmal-Passwort**: jede Methode jedes Endpunkts außer der Anmeldung selbst muss 401/403/404/405 liefern;
- **Firmentrennung**: Eine Person, die in der Regeneration Clinic Mediziner ist (in der DSKM nur Betrachter), und ein
  Admin nur der Regeneration Clinic rufen jeden Endpunkt mit jeder ID der Akten auf, die nur der DSKM gehören
  (Einzelabruf, Änderung, jede Aktion, Datei-Download, PDF, `?patient=`, Suche, Zeitraum) und schicken fremde
  `patient`-IDs im Inhalt neuer Einträge. Geprüft wird: kein Serverfehler, der Name der fremden Akte steht in keiner
  Antwort (auch nicht im Text erzeugter PDFs), keine Datei wird ausgeliefert, kein Datensatz und keine Historie der
  fremden Akten ändert sich, kein Audit-Eintrag zur fremden Akte entsteht. Gegenprobe: in der DSKM erscheinen die
  Akten;
- **Rollen**: Betrachter schicken an jeden Endpunkt jede schreibende Methode – keine darf gelingen.

## 3. Ergebnisse je Bereich

### 3.1 Bekannte Schwachstellen (CVE)

| Paket | Version vorher | Kennung | Schwere | Status |
|---|---|---|---|---|
| pdfjs-dist (Frontend) | 5.7.284 | GHSA-hq66-cqwq-w95j (beliebiges JavaScript beim Öffnen einer präparierten PDF) | hoch | **behoben**: 6.4.299 |
| weasyprint (Backend) | 69.0 | CVE-2026-106443 / GHSA-r543-q48m-4c9j (Bild-Daten gehen ungefiltert an Pillow; EPS → Ghostscript) | hoch (laut Hinweis) | **entschärft**, Paket noch 69.0 (siehe unten) |
| weasyprint (Backend) | 69.0 | CVE-2026-55073 / PYSEC-2026-3940 / GHSA-jf6q-chmf-3h3v (`url_fetcher` wird bei `stylesheets=`/`xmp_metadata=` umgangen) | – | **nicht betroffen**: EPM übergibt keines der beiden Argumente |

Alle übrigen Python-Pakete (Django 5.2.18, DRF 3.18.3, django-otp 1.7.4, webauthn, Pillow 12.3.0, pypdf 6.20.0,
psycopg 3.3.6, gunicorn 26.2.0, …) und alle übrigen npm-Pakete: keine bekannte Schwachstelle.

**pdf.js:** EPM zeigt hochgeladene PDFs (Arztbriefe, Scans, Befunde von außen) mit pdf.js im Ursprung der Anwendung an.
Eine präparierte PDF hätte dort Skript mit der Sitzung der angemeldeten Person ausführen können. Der Sprung auf 6.x
ist eine neue Hauptversion; die einzige Änderung im Code: `PDFDocumentProxy.destroy()` entfällt, stattdessen
`loadingTask.destroy()` (`frontend/src/components/PdfAnsicht.tsx`). Typprüfung und Build laufen, eine PDF wird in
Chromium korrekt gezeichnet. Die Browsertests der Akte (Dokumente, Pläne) sollten einmal mitlaufen.

**WeasyPrint:** Der Weg über Bilder war in EPM erreichbar – nicht über Rich-Text (dort sind Bilder ohnehin entfernt),
aber über ein SVG-Logo mit eingebettetem `<image href="data:image/…">` (Recht „Vorlagen pflegen“, Standard schon für
Mitarbeiter) und über die HTML-Einschleusung in Fußzeilen (Befund M3). Ghostscript ist im Backend-Image installiert
(für OCRmyPDF). Maßnahmen:
- Pillow öffnet kein EPS/PostScript mehr (`epm/sanitize.py: pillow_ohne_ghostscript`, beim Start aus
  `VorlagenConfig.ready`) – wirkt für WeasyPrint, Scans und Import gleichermaßen;
- der URL-Fetcher erlaubt weiter nur `data:`-URLs, jetzt als `URLFetcher` mit `allowed_protocols={"data"}` und ohne
  Weiterleitungen (`vorlagen/pdf.py: nur_eingebettet`).

Das Update auf WeasyPrint 70 ist vorbereitet: Mit dem neuen Fetcher laufen die PDF-Tests (vorlagen, berichte,
infusionen und die neuen Sicherheitstests, 66 Tests) unter 69.0 **und** 70.0 fehlerfrei. Die Pin-Grenze `<70` habe ich
nicht angehoben (Hauptversion; Layout der PDFs vorher einmal ansehen). Untergrenze jetzt `>=68` (ab da gibt es
`URLFetcher`).

**Docker-Images:** `python:3.13-slim`, `postgres:18-alpine`, `node:22-alpine`, `nginxinc/nginx-unprivileged:stable-alpine`
– gleitende Tags, die bei jedem Neubau die aktuellen Sicherheitsupdates mitbringen, aber nicht reproduzierbar sind. Ein
Scan der Images (z. B. Trivy) war hier nicht möglich (kein Docker-Daemon); siehe Abschnitt 6.

### 3.2 Statische Analyse (bandit)

23 Hinweise, keiner ein echter Fehler:

| Hinweis | Stelle | Bewertung |
|---|---|---|
| B603/B404 subprocess | `scans/…` (tesseract, ocrmypdf, gs) | Argumentlisten ohne Shell, Pfade aus EPM selbst – in Ordnung |
| B314/B405 XML | `stammdaten/api.py` (`_svg_pruefen`) | DOCTYPE/ENTITY werden vorher abgewiesen; Python-expat lädt keine externen Entitäten – in Ordnung |
| B324 SHA-1 | `scans/modelle/holen.py` | Git-Blob-Prüfsumme der OCR-Modelle beim Bau (nur wo keine SHA-256 hinterlegt ist); kein Kennwort – vertretbar, besser überall SHA-256 hinterlegen |
| B310 urlopen | `scans/modelle/holen.py` | feste URL aus `modelle.json`, nur beim Bau des Images – in Ordnung |
| B108 /tmp | `settings.py`, `epm_ocr.py` | Container mit eigenem /tmp – in Ordnung |
| B110/B112/B101/B311 | diverse | try/except/pass, assert in Testhilfen, Zufall für Testdaten – in Ordnung |

Rohes SQL (`cursor.execute`) kommt nur mit festen Texten bzw. Parametern vor (`audit/schutz.py`,
`patienten/loeschung.py`, `system/epm_aufgaben.py`) – keine Einschleusung möglich.

### 3.3 Django-Einstellungen

`manage.py check --deploy` mit DEBUG aus: nur W004 (HSTS) und W008 (SSL-Weiterleitung). Beides erledigt Nginx
(HSTS-Kopf; der Server lauscht nur mit TLS auf 8443/443) – vertretbar.

In Ordnung: `SECRET_KEY` und DB-Passwort nur aus Dateien (ohne Datei startet EPM nicht), `ALLOWED_HOSTS` aus der
Umgebung, Sitzungs- und CSRF-Cookie `Secure` (außer DEBUG), `HttpOnly` (Sitzung), `SameSite=Strict`, 30 Minuten
Sitzungsdauer mit Verlängerung bei Aktivität und Ende beim Schließen des Browsers, `X-Frame-Options: DENY`,
`nosniff`, `Referrer-Policy: same-origin`, Passwortregeln (mindestens 12 Zeichen, keine häufigen, nicht nur Ziffern,
nicht ähnlich dem Namen), Upload-Grenzen (5 MB im Speicher, 50 MB je Datei, Nginx 55 MB), DRF nur mit
Sitzungsanmeldung und CSRF.

Geändert: In `rollout/projekt/backend.env.beispiel` sind Django-Admin (`/verwaltung/`) und die API-Ansicht im Browser
jetzt aus (`EPM_DJANGO_ADMIN=0`, `EPM_API_BROWSABLE=0`). Das Frontend braucht beides nicht. **Bestehende Server** behalten
ihre `/srv/epm/backend.env` – dort bitte von Hand auf 0 setzen.

### 3.4 Nginx

In Ordnung: nur TLS 1.2/1.3, `server_tokens off`, HSTS, CSP (`script-src 'self'`, `frame-ancestors 'none'`),
`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, keine Kompression für `/api/` (BREACH), Dokumente und
Sicherungen nur über `internal`-Orte nach Prüfung durch Django, `X-Forwarded-For` wird überschrieben (nicht
angehängt) – die IP in Drosselung und Audit-Log lässt sich nicht fälschen.

Behoben (niedrig): Nginx erbt `add_header` nicht in Orte, die eigene `add_header` haben. Dokumente und bereitgestellte
Sicherungen kamen deshalb ohne HSTS, `X-Frame-Options` und `Referrer-Policy`. Die Köpfe stehen jetzt dort
(`X-Frame-Options: SAMEORIGIN` für Dokumente, weil die Akte Textdokumente im Rahmen anzeigt). Die Datei ließ sich hier
nicht mit `nginx -t` prüfen – bitte beim nächsten Update kontrollieren.

### 3.5 Anmeldung und zweiter Faktor

- Alle Endpunkte außer Anmeldung und Logo verlangen die vollständige Anmeldung – **mit einer Ausnahme (Befund M2)**:
  `/api/scans/gelernt/…`, `/api/scans/kennzahl/` und `/api/scans/gelernt/steuerung/` prüften nur „angemeldet“, nicht
  den zweiten Faktor und nicht das offene Einmal-Passwort. Mit dem Passwort allein ließen sich die gelernten
  Zuordnungen lesen, sperren und löschen und das Lernen umstellen. **Behoben** (`scans/api.py: GelerntRecht` prüft jetzt
  `voll_angemeldet`).
- Sperre nach 5 Fehlversuchen: für Passwort und für falsche Codes im zweiten Schritt (Authenticator und Notfall-Codes
  werden gemeinsam geprüft) durch Tests bestätigt; ein gesperrtes Konto kommt auch mit richtigem Passwort und gültigem
  Notfall-Code nicht hinein. Fehlgeschlagene Passkeys zählen über dieselbe Funktion mit (der vorhandene Passkey-Test
  prüft das Zählen). Bestätigungen in der Sitzung (endgültig löschen, 2FA ausschalten …) zählen ebenfalls.
- Notfall-Codes gelten genau einmal.
- Passkeys: feste RP-ID, nur `https://`-Ursprünge, Challenge in der Sitzung, einmal gültig, 5 Minuten, Benutzer-
  verifizierung verlangt, Schlüssel an das Konto gebunden – in Ordnung.
- Befund N2 (behoben): Die Regel „zweiter Faktor Pflicht für Admins“ galt nur für die DSKM-Rolle. Ein Admin nur der
  Regeneration Clinic blieb ohne zweiten Faktor. Jetzt zählt die Admin-Rolle in jeder Firma
  (`accounts/zweifaktor.py: ist_admin_in_einer_firma`).
- Befund N3 (behoben): „Passwort ändern“ zählte ein falsches bisheriges Passwort nicht als Fehlversuch – mit einer
  übernommenen Sitzung ließ sich das Passwort dort ohne Sperre durchprobieren (nur durch die Drosselung begrenzt).
  Jetzt wie jede andere Bestätigung: Fehlversuch, nach dem fünften gesperrt.

### 3.6 Firmentrennung (IDOR) und Rechte

Die Prüfung über alle Endpunkte fand zwei Lücken, beide **behoben**:

- **M1 – Audit-Log über Firmengrenzen:** Wer das Audit-Log lesen darf (Standard: Mediziner und Admin), sah in der
  Regeneration Clinic die Einträge zu Akten, die nur der DSKM gehören – mit Namen und Nummer der Patienten (z. B.
  „Akte Mustermann, Max (Nr. 123)“), ebenso in der PDF des Audit-Logs, und konnte nach Namen suchen. Jetzt erscheinen
  diese Einträge wie bei eingeschränkten Akten ohne Namen und Inhalt („Akte Nr. 123 (andere Firma)“); die Suche nach dem
  Namen findet sie nicht (`audit/api.py`, `audit/bereinigung.py`). Wer, wann und welche Art bleibt sichtbar (Nachweis).
- **N1 – Ansprechpartner neu zuordnen:** `POST /api/ansprechpartner/<id>/neu-zuordnen/` änderte den Ansprechpartner
  aller Akten – auch der anderen Firma. Jetzt nur die Akten im eigenen Bereich (`stammdaten/api.py`).
- **N4 – Vorschau „Patientenankündigung“** (Dokumentvorlagen) listete die Termine der Testpatienten beider Firmen
  (nur fiktive Daten). Jetzt nur die der aktiven Firma (`vorlagen/api.py`).

Bestätigt (Tests grün): Einzelabruf, Änderung und jede Aktion an Akten der anderen Firma liefern 404/400/403;
`?patient=`-Filter, Suche, Startseite, Kalender, Listen, Datei-Download, PDF-Ausgaben und Aktenkopie geben nichts preis;
neue Einträge mit fremder `patient`-ID (Kontakte, Gewichte, Termine, Dokumente mit Datei, Diagnosen, Medikamente,
Befunde, Berichte, Erklärungen, Anfragen, Pläne, Merkliste) werden abgewiesen; der Firmenwechsel in eine Firma ohne
Mitgliedschaft schlägt fehl, auch mit manipulierter Sitzung; die Rolle gilt je Firma (Mediziner in der Regeneration
Clinic schreibt als Betrachter in der DSKM nichts). Betrachter schreiben an keinem Endpunkt; Mitarbeiter geben keine
Pläne frei; Benutzer, Rechte, System, Sicherung, Import und Testdaten nur mit dem jeweiligen Recht; die eigene Rolle
lässt sich weder über `/api/auth/ich/` noch über `/api/benutzer/` noch über `/api/rechte/` ändern; Testbenutzer sehen und
schreiben nur Testpatienten.

Massenzuweisung: `ist_test`, `nummer`, `angelegt_von`, `eingeschraenkt_am`, `abgeschlossen_am` (Akte),
`erfasst_von`, `erfasst_am`, `storniert_am`, `firma` (Einträge), `is_superuser`, `is_staff`, `password`, `rolle`
(eigenes Konto) lassen sich nicht setzen.

### 3.7 Einschleusung (HTML, SQL, Dateien)

- Rich-Text (Diagnose, Therapie, Kontakte, Berichte, Befunde, Hilfe-Ergänzungen) wird beim Speichern mit nh3 auf eine
  feste Liste von Tags ohne Attribute, Links und Bilder bereinigt – auch beim Altdaten-Import. Die Stellen mit
  `dangerouslySetInnerHTML` im Frontend zeigen nur so bereinigtes oder serverseitig maskiertes HTML (Notfallplan,
  Hilfe, QR-Code).
- **M3 – HTML-Einschleusung in PDF-Fußzeilen (behoben):** Werte in der Fußzeile einer Vorlage (z. B. der Name der
  Patientin) wurden in eine CSS-Zeichenkette im `<style>`-Block gesetzt. `"` und `\` waren maskiert, `<` nicht: Ein
  Name wie `…</style><h1>…` beendete den Stilblock, der Rest stand als HTML im Dokument. Folgen: gefälschter Inhalt in
  amtlich wirkenden PDFs (Arztbrief, Plan) und – zusammen mit der WeasyPrint-Schwachstelle – ein Weg, Ghostscript mit
  fremdem PostScript zu füttern. Jetzt wird `<` als CSS-Escape geschrieben (`vorlagen/pdf.py: _css_string`).
- PDF-Erzeugung lädt nichts von außen: `file://`, `http(s)://`, `ftp://` werden abgewiesen (Test vorhanden).
- SVG-Logo: Skripte, Ereignisse, `foreignObject`, externe Verweise, DOCTYPE/Entitäten werden abgewiesen; ausgeliefert
  mit eigener CSP.
- Dokumente: Typ wird am Inhalt erkannt (PDF, JPEG, PNG, Text) – HTML, SVG oder Programme werden höchstens als
  `text/plain` gespeichert; Speicherpfad aus Patientennummer und Zufallsname (kein `../`); Dateiname im
  `Content-Disposition` nach RFC 5987 kodiert (keine Kopfzeilen-Einschleusung); `nosniff` überall.
- Dateinamen in System- und Sicherungs-Endpunkten werden gegen feste Muster geprüft.
- Keine CSV/Excel-Exporte, keine Weiterleitungen auf übergebene Adressen.

### 3.8 Sitzung und CSRF

CSRF gilt für jede schreibende Anfrage einer Sitzung, auch für die Anmeldung selbst (gegen Login-CSRF); falsches oder
fehlendes Token → 403. Nach der Anmeldung gibt es eine neue Sitzungs-ID (keine Sitzungsfixierung); nach dem Abmelden
ist das alte Cookie wertlos. Sperre, neues Einmal-Passwort und Passwortwechsel beenden die anderen Sitzungen.

### 3.9 Informationsabfluss

- Unbekannter Benutzername und falsches Passwort ergeben dieselbe Antwort; die Sperre wird nur bei richtigem Passwort
  verraten.
- Keine Tracebacks in Antworten (DEBUG aus; DRF liefert JSON-Fehler); Nginx versteckt seine Version und den
  `Server`-Kopf von Gunicorn.
- `/api/auth/status/` ohne Anmeldung: Name und Anschrift des Absenders, Namen der Firmen, ob Passkeys möglich sind –
  keine Patientendaten.
- Behoben (niedrig, N6): `DELETE /api/meine-akten/merken/` ohne Akte und `POST …/merken/<id>/` endeten mit
  Serverfehler 500; jetzt 400 bzw. normale Verarbeitung.

## 4. Befunde nach Schwere

| Nr. | Schwere | Befund | Status | Stelle |
|---|---|---|---|---|
| H1 | hoch | pdf.js: Skript beim Öffnen einer präparierten PDF (GHSA-hq66-cqwq-w95j) | behoben | `frontend/package.json`, `PdfAnsicht.tsx` |
| M1 | mittel | Audit-Log zeigt Namen von Patienten der anderen Firma | behoben | `audit/api.py`, `audit/bereinigung.py` |
| M2 | mittel | Scans/Gelerntes ohne zweiten Faktor erreichbar (lesen und ändern) | behoben | `scans/api.py` |
| M3 | mittel | HTML-Einschleusung in PDF-Fußzeilen über `</style>` | behoben | `vorlagen/pdf.py` |
| M4 | mittel | WeasyPrint CVE-2026-106443 (EPS → Ghostscript) über SVG-Logo bzw. M3 erreichbar | entschärft (Pillow ohne EPS, nur `data:`); Update auf 70 offen | `epm/sanitize.py`, `vorlagen/apps.py`, `vorlagen/pdf.py` |
| N1 | niedrig | „Ansprechpartner neu zuordnen“ ändert Akten der anderen Firma | behoben | `stammdaten/api.py` |
| N2 | niedrig | „2FA Pflicht für Admins“ übersah Admins weiterer Firmen | behoben | `accounts/zweifaktor.py` |
| N3 | niedrig | „Passwort ändern“ ohne Sperre nach Fehlversuchen | behoben | `accounts/api.py` |
| N4 | niedrig | Vorlagen-Vorschau zeigt Testtermine der anderen Firma | behoben | `vorlagen/api.py` |
| N5 | niedrig | Nginx: Sicherheitsköpfe fehlten bei Dokumenten und Sicherungen | behoben (ungetestet) | `rollout/projekt/nginx/epm.conf` |
| N6 | niedrig | Serverfehler 500 an der Merkliste | behoben | `patienten/meine_akten.py` |
| N7 | niedrig | Django-Admin und API-Ansicht im Betrieb eingeschaltet | Beispiel geändert; Server von Hand | `rollout/projekt/backend.env.beispiel` |

## 5. Tests

Neu: `backend/epm/test_sicherheit.py` – 31 Tests in sechs Gruppen (ohne Anmeldung, Firmentrennung über alle Endpunkte,
Rechte und Massenzuweisung, nur lesen, Sitzungen und Sperren, PDF und Dateien).

Testläufe vom 11.10.2026 (lokal, PostgreSQL 16, nacheinander):

- `epm accounts patienten audit system scans vorlagen befunde infusionen berichte stammdaten altimport hilfe`:
  586 Tests, 5 übersprungen, 13 fehlgeschlagen – alle 13 in `scans` und alle mit derselben Ursache: Tesseract ist in
  der Prüfumgebung nicht installiert (`FileNotFoundError: 'tesseract'`); unabhängig von dieser Prüfung.
- danach (nach der letzten Erweiterung der Sicherheitstests) `epm stammdaten`: 41 Tests, alle grün.
- PDF-Tests mit WeasyPrint 70.0 (`epm.test_sicherheit.PdfUndDateien vorlagen berichte infusionen`): 66 Tests, alle grün.

## 6. Offene Punkte und Empfehlungen

**Entscheidungen der Praxis (bewusst so festgelegt, Risiko benannt):**

1. **Zweiter Faktor ist freiwillig** (Festlegung 02.10.2026). Für Gesundheitsdaten empfehle ich „Pflicht für alle“
   (Benutzer › Anmeldung). Mit nur einem Passwort hängt der Schutz jeder Akte an der Passwortwahl jeder Person.
2. **Admin ist firmenübergreifend.** Die Benutzerverwaltung ist gemeinsam: Ein Admin der Regeneration Clinic kann
   Konten anlegen, Rollen in der DSKM vergeben (auch sich selbst) und Sicherungen herunterladen, die die Daten beider
   Firmen enthalten; ebenso Systemverwaltung. Admin-Rollen deshalb nur an Personen geben, die für beide Firmen
   zuständig sind – oder die Vergabe von Rollen auf die eigene Firma beschränken (Änderung am Rechtemodell).
3. **Gemeinsame Stammdaten** (Dokumentvorlagen, Briefköpfe beider Firmen, Versorger, Ärzte, Auswahllisten) kann jede
   Firma mit dem passenden Recht ändern. Kein Abfluss von Patientendaten, aber eine Firma kann Texte und Briefkopf der
   anderen ändern. Die Zahl „Patienten in Betreuung“ bei Versorgern und Ärzten zählt beide Firmen.
4. **Sperre nach 5 Fehlversuchen** schützt vor Raten, erlaubt aber, ein Konto mit bekanntem Benutzernamen absichtlich
   zu sperren (Entsperren durch die Administration, Hinweis im Audit-Log).
5. Die Drosselung der Anmeldung (30/min) gilt je Gunicorn-Prozess (Zwischenspeicher im Prozess) – bei 3 Prozessen
   praktisch bis 90/min. Die Kontosperre bleibt davon unberührt.

**Technisch noch zu tun:**

6. WeasyPrint auf 70 heben (`weasyprint>=70,<71`), vorher die PDF-Ausgaben (Plan, Arztbrief, Aktenkopie) einmal ansehen.
7. Auf bestehenden Servern `EPM_DJANGO_ADMIN=0` und `EPM_API_BROWSABLE=0` in `/srv/epm/backend.env` setzen.
8. Nginx-Konfiguration nach dem Update mit `nginx -t` prüfen.
9. Docker-Images regelmäßig neu bauen und scannen (z. B. `trivy image epm-backend:<Version>`), Basis-Images
   möglichst mit Digest festhalten, damit ein Bau nachvollziehbar ist.

**Nur auf dem echten Server prüfbar (nicht Teil dieser Prüfung):**

10. TLS: Zertifikat der eigenen CA, Gültigkeit, Schlüssellänge; Test z. B. mit `testssl.sh` gegen die Verwaltungs-IP.
11. Erreichbarkeit: Port 443 nur an der Verwaltungs-IP (`EPM_BIND_IP`), Firewall/VPN, kein Zugriff aus dem Internet,
    PostgreSQL und Backend nicht nach außen veröffentlicht.
12. Sicherungen: verschlüsselt (Sicherungs-Passwort gesetzt, Passwortblatt sicher verwahrt), Übertragungsziel nur mit
    eigener Anmeldung, eine Wiederherstellung zur Probe.
13. Rechte der Dateien unter `/srv/epm/secrets/` und `/srv/epm/backend.env` (nur root), Betriebssystem-Updates,
    Aufbewahrung der Protokolle.
