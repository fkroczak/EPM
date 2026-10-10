"""
Mitgelieferte Hilfetexte (S15). Sie kommen mit jeder EPM-Version und passen immer zu ihr; eigene Ergänzungen der
Stiftung stehen in der Datenbank (``Hilfeergaenzung``) und werden unter dem jeweiligen Abschnitt angezeigt.

Jeder Abschnitt nennt die Rechte, von denen mindestens eines nötig ist (leer = für alle Angemeldeten). Die Hilfe zeigt
nur Abschnitte zu dem, was die Person tatsächlich darf (Rechte je Gruppe, F66; nicht Erlaubtes ist ausgeblendet, F71).
``seiten`` ordnet Adressen der Oberfläche einem Abschnitt zu: das „?“ in der Kopfzeile springt dorthin
(``:id`` steht für eine Nummer, die längste passende Adresse gewinnt).
"""

GRUPPEN = [
    ("erste_schritte", "Erste Schritte"),
    ("startseite", "Startseite"),
    ("patienten", "Patienten und Akte"),
    ("kontakte", "Kontakte und Termine"),
    ("gewicht", "Gewicht"),
    ("plaene", "Infusionspläne"),
    ("dokumente", "Dokumente"),
    ("datenschutz", "Datenschutz"),
    ("scans", "Scans und Texterkennung"),
    ("listen", "Versorger und Ärzte"),
    ("administration", "Administration"),
]

ABSCHNITTE = [
    # ------------------------------------------------------------------ Erste Schritte
    {
        # Bedienung für Pflegekräfte (10.10.2026, F178): die Alltagswege auf einen Blick, ganz oben in der Hilfe
        "id": "alltag", "gruppe": "erste_schritte", "titel": "Die wichtigsten Wege im Alltag", "rechte": [],
        "seiten": [],
        "html": """
<p>Für die tägliche Arbeit reichen wenige Wege. Jede Seite hat oben rechts ein <strong>?</strong> – es öffnet die Hilfe
genau zu dieser Seite.</p>
<ul>
<li><strong>Patient suchen:</strong> ins Suchfeld oben tippen (Name, Teil des Namens, Nummer oder Geburtsdatum) und den
Treffer anklicken. Schneller: <strong>Strg K</strong>. Am Telefon die Lupe oben.</li>
<li><strong>Telefonat oder Gespräch festhalten:</strong> in der Akte <strong>Kontakt</strong>, auf der Startseite
<strong>Kontakt erfassen</strong>. Notiz schreiben, <strong>Speichern</strong>. Gewicht und Wiedervorlage lassen sich im
selben Fenster mit erfassen.</li>
<li><strong>Gewicht eintragen:</strong> in der Akte <strong>Gewicht</strong>.</li>
<li><strong>Termin oder Rückruf:</strong> in der Akte <strong>Termin</strong> (mehr unter „Termine, Rückrufe und
Wiedervorlagen“).</li>
<li><strong>Brief oder Befund ablegen:</strong> Datei auf die geöffnete Akte ziehen oder im Reiter
<strong>Dokumente</strong> <strong>Neues Dokument</strong> wählen.</li>
<li><strong>Neuer Patient:</strong> in der Patientenliste <strong>Neuer Patient</strong>. Pflicht sind nur Nachname,
Vorname und Geburtsdatum.</li>
</ul>
<p>Nach jedem Speichern erscheint oben kurz eine <strong>grüne</strong> Bestätigung. Eine <strong>rote</strong> Meldung
bleibt länger stehen und sagt, was fehlt; mit dem × lässt sie sich schließen.</p>""",
    },
    {
        "id": "wenn_es_hakt", "gruppe": "erste_schritte", "titel": "Wenn etwas nicht klappt", "rechte": [], "seiten": [],
        "html": """
<ul>
<li><strong>Ein Knopf ist grau:</strong> es fehlt noch eine Angabe. Daneben steht meist, welche – zum Beispiel
„Zuerst den Patienten wählen“ oder „Zum Speichern bitte eine Notiz schreiben“.</li>
<li><strong>Ein Feld ist rot umrandet:</strong> darunter steht, was nicht passt. Beim neuen Patienten springt EPM zum
ersten roten Feld.</li>
<li><strong>Datum:</strong> am einfachsten „14.03.2026“. EPM versteht auch „14.3.26“, „14,3,26“, „14032026“ sowie
„heute“ und „gestern“. Uhrzeiten gehen als „10:30“, „10.30“ oder „1030“.</li>
<li><strong>Patient nicht gefunden:</strong> nur einen Teil des Namens eingeben (z. B. „Mül“) oder nach Nummer bzw.
Geburtsdatum suchen. Abgeschlossene Akten stehen in der Patientenliste unter <strong>Abgeschlossen</strong>; ohne
Treffer bietet die Liste auch „In abgeschlossenen Akten suchen“ und „Neuer Patient“ an.</li>
<li><strong>„Keine Verbindung zu EPM“:</strong> Netzwerk bzw. VPN prüfen und es noch einmal versuchen – die Eingaben
bleiben stehen. Steht dort, dass EPM gerade nicht erreichbar ist, wird es meist neu gestartet oder aktualisiert:
ein paar Minuten warten.</li>
<li><strong>Konto gesperrt</strong> (nach fünf falschen Passwörtern): die Administration entsperrt es.</li>
<li><strong>Etwas versehentlich gespeichert:</strong> Kontakte werden storniert (mit Grund), Messungen bearbeitet; alle
früheren Fassungen bleiben im <strong>Verlauf</strong> der Akte sichtbar. Es geht nichts verloren.</li>
</ul>""",
    },
    {
        "id": "anmelden", "gruppe": "erste_schritte", "titel": "Anmelden mit Passwort und Authenticator", "rechte": [],
        "seiten": [],
        "html": """
<p>Angemeldet wird mit Benutzername und <strong>Passwort</strong>. Die <strong>Zwei-Faktor-Anmeldung</strong> (Code aus
einer Authenticator-App auf dem Telefon) ist freiwillig – die Administration kann sie für Admins oder für alle zur
Pflicht machen. Wer sie eingerichtet hat, wird bei jeder Anmeldung nach dem Code gefragt.</p>
<ol>
<li>Benutzername und Passwort eingeben, <strong>Weiter</strong> wählen. Groß- und Kleinschreibung zählt; ist die
Feststelltaste an, weist EPM darauf hin.</li>
<li>Mit Zwei-Faktor-Anmeldung: den sechsstelligen Code aus der Authenticator-App eingeben. Er wechselt alle 30 Sekunden.</li>
<li>Bei der ersten Anmeldung mit dem Einmal-Passwort vom Zugangsblatt wird zuerst ein eigenes Passwort festgelegt. Ist
die Zwei-Faktor-Anmeldung Pflicht, wird danach die Authenticator-App eingerichtet (QR-Code scannen); sonst geht das
jederzeit unter <strong>Mein Konto › Anmeldung und Sicherheit › Einrichten</strong>. Danach zeigt EPM einmalig die
Notfall-Codes.</li>
</ol>
<p>Solange sie freiwillig ist, lässt sich die Zwei-Faktor-Anmeldung unter Mein Konto mit Passwort und Code auch wieder
ausschalten. Bestätigungen (endgültig löschen, Wiederherstellen, Updates, Sicherung, Import) verlangen immer Passwort
<strong>und</strong> Code – wer sie ausführen soll (z. B. Mediziner, Administration), muss die Zwei-Faktor-Anmeldung
eingerichtet haben.</p>
<p>Nach mehreren falschen Passwörtern wird das Konto gesperrt; entsperren kann die Administration. Nach längerer
Pause meldet EPM von selbst ab.</p>""",
    },
    {
        "id": "notfallcodes", "gruppe": "erste_schritte", "titel": "Notfall-Codes", "rechte": [], "seiten": [],
        "html": """
<p>Notfall-Codes ersetzen den Code aus der Authenticator-App, wenn das Telefon nicht zur Hand ist. Jeder Code gilt
<strong>genau einmal</strong>. Bitte ausdrucken und sicher aufbewahren, nicht auf dem Telefon speichern.</p>
<p>Sind nur noch wenige Codes übrig, erscheint auf der Startseite ein Hinweis. Neue Codes gibt es unter
<strong>Mein Konto › Anmeldung und Sicherheit</strong>; die alten werden dabei ungültig.</p>
<p>Telefon verloren und keine Codes mehr? Dann setzt die Administration den zweiten Faktor zurück und gibt ein neues
Zugangsblatt aus.</p>""",
    },
    {
        "id": "passkey", "gruppe": "erste_schritte", "titel": "Passkey statt Code (PC und Telefon)", "rechte": [],
        "seiten": [],
        "html": """
<p>Ein <strong>Passkey</strong> ersetzt den Code aus der Authenticator-App: Nach dem Passwort bestätigt man die
Anmeldung mit Fingerabdruck, Gesicht oder der PIN des Geräts (Windows Hello, iPhone, Android, Passwortmanager). Er gilt
auch für alle Bestätigungen mit zweitem Faktor (endgültig löschen, Wiederherstellen, Updates, Import …). Der Code aus
der App und die Notfall-Codes bleiben daneben gültig.</p>
<p><strong>Einrichten:</strong> Mein Konto › Anmeldung und Sicherheit › <strong>Passkey hinzufügen</strong>, Namen
vergeben (z. B. „iPhone“), bestätigen. Am besten auf PC <em>und</em> Telefon je einen anlegen. Wer noch keinen
zweiten Faktor hatte, bekommt dabei Notfall-Codes.</p>
<p><strong>Voraussetzung:</strong> EPM über den Namen aufrufen (z. B. <code>https://epm.stiftung.lan/</code>), nicht über
die IP-Adresse, und das Stammzertifikat der Stiftung einmal auf dem Gerät installieren:
<a href="/epm-ca.crt">Stammzertifikat herunterladen</a>.</p>
<ul>
<li><strong>Windows:</strong> Datei öffnen › Zertifikat installieren › Lokaler Computer › „Vertrauenswürdige
Stammzertifizierungsstellen“.</li>
<li><strong>iPhone/iPad:</strong> Datei laden › Einstellungen › Allgemein › VPN und Geräteverwaltung › Profil
installieren; danach Einstellungen › Allgemein › Info › Zertifikatsvertrauenseinstellungen › EPM-CA einschalten.</li>
<li><strong>Android:</strong> Einstellungen › Sicherheit › Weitere Einstellungen › Verschlüsselung und Anmeldedaten ›
Zertifikat installieren › CA-Zertifikat.</li>
</ul>
<p>Gerät verloren? Den Passkey unter Mein Konto entfernen (von einem anderen Gerät aus) oder die Administration setzt
den zweiten Faktor zurück.</p>""",
    },
    {
        "id": "telefon", "gruppe": "erste_schritte", "titel": "EPM am Telefon", "rechte": [], "seiten": [],
        "html": """
<p>Der Arbeitsplatz für EPM ist der PC. Am Telefon (im VPN) geht das Wichtigste unterwegs:</p>
<ul>
<li><strong>Pläne freigeben:</strong> unten <strong>Pläne</strong> zeigt die Entwürfe zur Freigabe; Plan öffnen, prüfen
(Ansicht wie PDF, Vergleich mit dem Vorgänger) und <strong>Freigeben</strong>.</li>
<li><strong>Kurz nachsehen:</strong> Suche oben (Lupe) oder <strong>Patienten</strong>; der Aktenkopf zeigt Gewicht,
Plan, Versorger und den nächsten Termin, die Reiter lassen sich seitlich wischen.</li>
<li><strong>Notiz erfassen:</strong> <strong>＋ Notiz</strong> in der Leiste unten öffnet die Schnellerfassung – in einer
offenen Akte gleich für diesen Patienten.</li>
<li>Alles Übrige steht unter <strong>Menü</strong>.</li>
</ul>
<p>Anmelden am Telefon am einfachsten mit einem Passkey (siehe „Passkey statt Code“).</p>""",
    },
    {
        "id": "design", "gruppe": "erste_schritte", "titel": "Design: Farben, Dichte, Aufbau der Akte", "rechte": [],
        "seiten": ["/design"],
        "html": """
<p>Unter <strong>Design</strong> (Menü unten links bei deinem Namen) stellt jede Person für sich ein, wie EPM aussieht:
Farbschema (auch hoher Kontrast und dunkel), Akzentfarbe, Hintergrund, Dichte, Schriftgröße und Schriftstärke sowie den
Aufbau der Patientenakte (Kopfzeile, Seitenleiste oder Karteikarte). Die Einstellungen gelten an jedem PC, an dem man
sich anmeldet. <strong>Auf Standard zurücksetzen</strong> stellt alles zurück; <strong>Startseite anpassen</strong>
führt zur Startseite im Bearbeitungsmodus.</p>""",
    },
    {
        "id": "konto", "gruppe": "erste_schritte", "titel": "Mein Konto: Passwort, Zwei-Faktor, Anmeldungen", "rechte": [],
        "seiten": ["/konto"],
        "html": """
<p><strong>Mein Konto</strong> zeigt das eigene Profil (Name, Funktion, Kürzel, Rolle – geändert von der
Administration) und alles zur Anmeldung. Wie EPM aussieht, steht seit dem 09.10.2026 im eigenen Menüpunkt
<strong>Design</strong>.</p>
<ul>
<li><strong>Passwort ändern</strong>: altes Passwort, dann zweimal das neue.</li>
<li><strong>Zwei-Faktor-Anmeldung</strong>: Authenticator-App oder Passkey einrichten, neues Gerät, Notfall-Codes; solange freiwillig auch ausschalten.</li>
<li><strong>Anmeldungen</strong>: zeigt, wo man gerade angemeldet ist; fremde Anmeldungen lassen sich einzeln beenden.</li>
</ul>""",
    },
    {
        "id": "hilfe", "gruppe": "erste_schritte", "titel": "Die Hilfe benutzen und ergänzen", "rechte": [],
        "seiten": ["/hilfe"],
        "html": """
<p>Die Hilfe zeigt nur Abschnitte zu dem, was du in EPM tun darfst. Das <strong>?</strong> oben rechts auf jeder Seite
springt zum passenden Abschnitt. Die Suche findet Wörter in Titeln, Texten und Ergänzungen.</p>
<p>Die Texte mit dem Zeichen <strong>mitgeliefert</strong> kommen mit EPM und passen immer zur installierten Version.
Wer das Recht „Vorlagen pflegen“ hat, kann unter jedem Abschnitt eine <strong>Ergänzung der Stiftung</strong> schreiben,
z. B. interne Abläufe oder Telefonnummern. Jede Änderung steht mit Person und Zeitpunkt in der Historie und im
Audit-Log; frühere Fassungen bleiben lesbar.</p>""",
    },
    # ------------------------------------------------------------------ Startseite
    {
        "id": "startseite", "gruppe": "startseite", "titel": "Startseite: Kacheln und Kennzahlen", "rechte": ["akten_lesen"],
        "seiten": ["/"],
        "html": """
<p>Die Startseite zeigt, was heute zu tun ist. Oben stehen die <strong>Kennzahlen</strong>: Patienten in Betreuung
(ohne Testpatienten), mit offenem Termin, Termine in den nächsten 7 Tagen, Kontakt fällig und überfällige Termine. Ein
Klick auf eine Kennzahl öffnet die passende Liste.</p>
<p>Darunter liegen die <strong>Kacheln</strong> in einem festen Raster: Termine und Wiedervorlagen (mit Wochenstreifen),
Wiedereinbestellung fällig, Meine Akten, Auffällige Gewichte (mit Verlauf der letzten 6 Monate), Infusionspläne, Nach
und nach prüfen und Zuletzt eingetragen. Passt der Inhalt nicht in die Kachel, lässt er sich in der Kachel scrollen;
der Verweis unten führt zur vollständigen Liste.</p>
<p>Je nach Fensterbreite stehen 1 bis 5 Spalten nebeneinander; die Kacheln behalten ihre Größe.</p>""",
    },
    {
        "id": "heute_zu_tun", "gruppe": "startseite", "titel": "Heute zu tun: die Tagesliste am Morgen",
        "rechte": ["akten_lesen"], "seiten": ["/"],
        "html": """
<p>Ganz oben auf der Startseite steht <strong>Heute zu tun</strong>: eine kurze Liste, das Wichtigste zuerst, jeweils mit
Anzahl. Ein Klick auf eine Zeile führt direkt hin.</p>
<ul>
<li><strong>Termine heute</strong> mit Uhrzeit, Patient und Ort; das Kästchen „erledigt“ hakt ab.</li>
<li><strong>Rückrufe und Wiedervorlagen</strong>, die heute fällig oder schon überfällig sind – ebenfalls zum Abhaken.</li>
<li><strong>Praxis informieren</strong>: das Infoblatt an die Praxis ist fällig – „Infoblatt erstellen“.</li>
<li><strong>Terminbestätigung fehlt</strong> bei Praxisterminen der nächsten zwei Wochen – „Bestätigung vorbereiten“.</li>
<li><strong>Kein Kontakt</strong> seit der eingestellten Zeit und kein Termin geplant, <strong>Infusionspläne zur
Prüfung</strong>, <strong>Scans</strong>, die auf Zuordnung warten.</li>
<li><strong>Praxistermine ohne Ort</strong> („Ort eintragen“) und <strong>fehlende Angaben</strong> in den Akten, z. B.
„3 Akten ohne Telefonnummer“ – der Klick öffnet die Patientenliste mit genau diesen Akten.</li>
</ul>
<p>Was erledigt ist, verschwindet von allein. Ist nichts mehr offen, steht dort „Für heute ist alles erledigt.“
EPM verschickt dabei nichts und trägt nichts ein: Die Knöpfe öffnen nur den passenden Dialog, entscheiden tust du.
Testpatienten und abgeschlossene Akten stehen nicht in der Liste.</p>""",
    },
    {
        "id": "startseite_anpassen", "gruppe": "startseite", "titel": "Startseite anpassen", "rechte": [], "seiten": [],
        "html": """
<p><strong>Startseite anpassen</strong> schaltet den Bearbeitungsmodus ein. Die Einstellung gilt nur für dich.</p>
<ul>
<li><strong>Verschieben</strong>: Kachel am Griff ziehen – oder Griff wählen und mit den Pfeiltasten verschieben.</li>
<li><strong>Größe</strong>: an der Ecke unten rechts ziehen; die Kachel rastet in 1×1, 2×1, 1×2 oder 2×2 Rasterzellen
ein. Per Tastatur: Umschalt + Pfeiltasten am Griff, oder die Größenknöpfe über der Kachel.</li>
<li><strong>Ausblenden</strong> mit dem Auge; ausgeblendete Kacheln stehen oben unter „Ausgeblendet“ und kommen per
Klick zurück.</li>
<li><strong>Standard</strong> stellt die mitgelieferte Startseite wieder her.</li>
</ul>""",
    },
    {
        "id": "termine_startseite", "gruppe": "startseite", "titel": "Termine und Wiedervorlagen abhaken",
        "rechte": ["akten_lesen"], "seiten": [],
        "html": """
<p>Die Kachel zeigt offene Termine für <strong>heute</strong>, die <strong>nächsten 7 Tage</strong> und
<strong>überfällige</strong>. Der Wochenstreifen zeigt je Tag die Anzahl, Praxistermine als Punkte und Feiertage; ein
Klick auf einen Tag zeigt nur dessen Termine.</p>
<p>Mit dem Recht, Einträge zu erfassen, hakt das Kästchen einen Termin als <strong>erledigt</strong> ab – mit Person und
Uhrzeit. Ein erledigter Termin bleibt in der Akte sichtbar.</p>""",
    },
    {
        "id": "wiedereinbestellung", "gruppe": "startseite", "titel": "Wiedereinbestellung fällig", "rechte": ["akten_lesen"],
        "seiten": [],
        "html": """
<p>Die Kachel listet Patienten in Betreuung, mit denen es länger <strong>keinen Kontakt</strong> gab und für die
<strong>kein Termin geplant</strong> ist – in zwei Stufen:</p>
<ul>
<li><strong>Bald fällig</strong>: letzter Kontakt länger her als „Kontakt bald fällig“ (Standard 4 Monate).</li>
<li><strong>Überfällig</strong>: letzter Kontakt länger her als „Kontakt überfällig“ (Standard 6 Monate) oder noch gar
kein Kontakt erfasst.</li>
</ul>
<p>Beide Grenzen stellt ein, wer Vorlagen pflegt (Vorlagen › Grenzwerte). Die Knöpfe neben dem Namen erfassen direkt einen
Kontakt oder legen einen Termin an. Dieselben Stufen zeigen die Hinweise in der Patientenliste, „Nach und nach
prüfen“ und der Kalender.</p>""",
    },
    {
        "id": "schnellerfassung", "gruppe": "startseite", "titel": "Kontakt, Gewicht und Termin von der Startseite",
        "rechte": ["eintraege_erfassen"], "seiten": [],
        "html": """
<p>Mit <strong>Kontakt erfassen</strong>, <strong>Gewicht</strong> und <strong>Termin</strong> oben auf der Startseite
lässt sich ein Telefonat festhalten, ohne die Akte zu öffnen.</p>
<ol>
<li>Patient suchen (Name, Nummer oder Geburtsdatum) und auswählen. Der Kasten „Aus der Akte“ zeigt letzten Kontakt,
Gewicht, aktuellen Plan, nächsten Termin und <strong>wem Auskunft gegeben werden darf</strong>.</li>
<li>Notiz eintragen und, wenn bekannt, die <strong>Kontaktart</strong> wählen (Telefon, persönlich, E-Mail …). Auf Wunsch
<strong>Gewicht mit erfassen</strong> und eine <strong>Wiedervorlage</strong> anlegen.</li>
<li><strong>Speichern</strong>.</li>
</ol>
<p>Kontakt und Gewicht werden nacheinander gespeichert. Scheitert das Gewicht (z. B. unplausibler Wert), bleibt der
Kontakt gespeichert; EPM sagt das deutlich und lässt das Gewicht korrigieren und erneut speichern.</p>""",
    },
    # ------------------------------------------------------------------ Patienten und Akte
    {
        "id": "patientenliste", "gruppe": "patienten", "titel": "Patientenliste, Suche und Filter", "rechte": ["akten_lesen"],
        "seiten": ["/patienten"],
        "html": """
<p>Die Liste zeigt Patienten <strong>in Betreuung</strong> oder <strong>abgeschlossene</strong> Akten. Es gibt
<strong>ein</strong> Suchfeld: das oben in der Kopfzeile (Strg K). Auf der Patientenliste filtert es direkt die Liste
(Name, Nummer oder Geburtsdatum; der Begriff steht als Chip bei den Filtern), auf allen anderen Seiten schlägt es
Patienten zum Öffnen vor.</p>
<ul>
<li>Filter nach Versorger, Ansprechpartner und Katheter; Schnellfilter „Nur mit Hinweisen“, „Gewichtsverlust“,
„Termin diese Woche“.</li>
<li><strong>Prüfen …</strong> wählt eine der Prüfungen: Kontakt fällig (bald fällig, überfällig), Wiedereinbestellung,
Nickelallergie oder Versorger nicht erfasst, kein Infusionsplan, Labor oder BIA fehlt bzw. zu alt, Erklärungen zum
Datenschutz fehlen, Abschluss prüfen, Altdokumente. Dieselben Listen öffnen sich auch über die Zahlen der Startseite
und der Seite Datenschutz.</li>
<li>Klick auf eine Spaltenüberschrift sortiert; Klick auf die Zeile öffnet die Akte.</li>
<li>Je breiter das Fenster, desto mehr Spalten: ab 1440 px Geboren, Katheter, Versorger und Gewicht, ab 1920 px Plan
und Erklärungen.</li>
</ul>
<p>Testpatienten (Nummern ab 9001) stehen in der Liste, zählen aber in keiner Statistik.</p>
<p><strong>Abgeschlossene Akten</strong> sind Akten, deren Betreuung beendet ist. Sie bleiben vollständig lesbar und
lassen sich als PDF ausgeben, werden aber nicht mehr verändert. Wieder öffnen kann nur die Administration, zum Beispiel
nach einem Versehen.</p>""",
    },
    {
        "id": "neuer_patient", "gruppe": "patienten", "titel": "Neuer Patient", "rechte": ["akten_bearbeiten"],
        "seiten": ["/patienten/neu"],
        "html": """
<p><strong>Neuer Patient</strong> in der Patientenliste öffnet das Formular. Pflicht sind Nachname, Vorname und
Geburtsdatum; EPM vergibt die Patientennummer selbst und warnt, wenn es eine Akte mit gleichem Namen und Geburtsdatum
schon gibt.</p>
<p><strong>Als Testpatient anlegen</strong> (Häkchen oben) legt eine Übungsakte an, z. B. um Infusionspläne
auszuprobieren: Nummer ab 9001, zählt in keiner Statistik. Testzugänge und Admins legen immer Testpatienten an.</p>
<p>Gewicht bei Aufnahme, Hausarzt, Versorger, Katheter und Nickelallergie lassen sich gleich mit erfassen.
„Kein Versorger“ bzw. „kein Katheter“ heißt bewusst keiner; leer heißt noch nicht erfasst. Fehlt ein Versorger oder
Arzt in der Liste, legt <strong>Neu anlegen</strong> ihn in einem Dialog an – das Formular bleibt mit allen Eingaben
stehen, der neue Eintrag ist gleich ausgewählt.</p>
<p>Therapie, erster Infusionsplan, Dokumente und Termine werden danach in der Akte angelegt.</p>""",
    },
    {
        "id": "aktenkopf", "gruppe": "patienten", "titel": "Aktenkopf und Merkliste", "rechte": ["akten_lesen"],
        "seiten": ["/patienten/:id"],
        "html": """
<p>Der Kopf der Akte ist schmal: in der ersten Zeile Name, Nummer, Geburtsdatum und die Knöpfe, darunter vier Kennzahlen –
<strong>Gewicht</strong> (mit Trend und BMI), <strong>Infusionsplan</strong>, <strong>nächster Termin</strong>,
<strong>letzter Kontakt</strong> – und eine Zeile mit Versorger, Ansprechpartner, Hausarzt, Katheter, Nickelallergie und
<strong>Auskunft an</strong> (Personen mit Schweigepflichtentbindung). Auf dem Tablet und am Telefon steht diese Zeile hinter
<strong>Versorgung und Hinweise</strong>. Fehlt eine Erklärung zum Datenschutz, steht ein Hinweis neben dem Namen.</p>
<p>Die Knöpfe im Kopf: <strong>Kontakt</strong>, <strong>Gewicht</strong>, <strong>Termin</strong> und
<strong>Dokument</strong> öffnen jeweils denselben Dialog bzw. die Dateiauswahl (die Seite bleibt, wo sie ist);
<strong>Neuer Plan</strong> – oder <strong>Entwurf fortsetzen</strong>, wenn es schon einen Entwurf gibt. Unter
<strong>Weitere Aktionen</strong> (⋯): Stammdaten bearbeiten, Akte als PDF, Unterlagen für die Sprechstunde, Schreiben
und E-Mail, Akte abschließen. Dokumente lassen sich auch einfach auf die geöffnete Akte ziehen.</p>
<p>Der <strong>Stern</strong> neben dem Namen setzt die Akte auf deine Merkliste; sie erscheint dann auf der Startseite
unter „Meine Akten“. Dort stehen auch die zuletzt geöffneten Akten. Merkliste und Verlauf sieht nur die Person selbst.</p>
<p>Jeder Bereich hat seinen eigenen Reiter. Vorn stehen die Bereiche der Behandlung – <strong>Übersicht, Diagnosen,
Therapie, Empfehlung, Infusionspläne, Kontakte</strong> –, kleiner danach Labor, BIA, Berichte und Dokumente, ganz rechts
Verlauf und Datenschutz. Wie die Akte aufgebaut ist (Kopfzeile, Seitenleiste, Karteikarte), stellt jede Person unter
<strong>Design</strong> ein. Tastenkürzel siehe „Tastenkürzel in der Akte“.</p>
<p><strong>Ohne Scrollen:</strong> Am PC (ab 1024 × 600 Bildpunkten) passt die Akte ins Fenster. Kopf und Reiter bleiben
immer stehen; ist ein Bereich länger, scrollt nur er – in der Übersicht jede Karte für sich, in Reitern mit zwei Spalten
jede Spalte für sich. Die Übersicht zeigt sechs Karten in zwei Reihen: Gewicht, aktueller Infusionsplan (mit
<strong>PDF ansehen</strong>), Diagnosen/Therapie/Empfehlung, Kontakte und Termine, Labor und BIA, Personen und Anschrift
(Bezugspersonen, Ärzte, Anschrift). Am Telefon scrollt die Seite wie gewohnt.</p>
<p>Hinweise am Namen (Gewichtsverlust, Plan oder Befund zu alt, Kontakt fällig …) lassen sich mit dem <strong>×</strong>
ausblenden. Dabei wird gewählt, wie lange Ruhe sein soll – 3, 6 oder 12 Monate, danach erscheint der Hinweis von allein
wieder – oder <strong>nicht mehr nötig</strong>. Was gerade ausgeblendet ist, steht in der Übersicht der Akte unter
„Ausgeblendete Hinweise“ und lässt sich dort wieder einschalten.</p>
<p><strong>Fehlende Angaben</strong> meldet EPM ebenfalls als Hinweis: kein Hausarzt bzw. Arzt erfasst, keine
Telefonnummer (auch keine bei den Kontaktpersonen), kein Gewicht seit einigen Monaten (Grenze unter Vorlagen ›
Grenzwerte), keine Diagnose und ein Praxistermin ohne Ort. Ist etwas bewusst nicht zu haben, den Hinweis mit
<strong>×</strong> ausblenden. Abgeschlossene Akten und Testpatienten bekommen diese Hinweise nicht. Die Startseite
zählt sie unter „Heute zu tun“ zusammen.</p>""",
    },
    {
        "id": "schreiben", "gruppe": "patienten", "titel": "Schreiben und E-Mail: Aufnahme, Terminbestätigung, Reise",
        "rechte": ["eintraege_erfassen"], "seiten": [],
        "html": """
<p>In der Akte unter <strong>Weitere Aktionen › Schreiben und E-Mail …</strong> entstehen aus den Dokumentvorlagen
<strong>Patientenaufnahme</strong> (welche Unterlagen wir brauchen), <strong>Terminbestätigung</strong> (Termin wählen;
Praxis Dr. Holtmeier, Gesundheitskarte mitbringen, keine Überweisung nötig) und <strong>Reisebescheinigung</strong>
(Briefkopf Dr. Holtmeier, deutsch und englisch, mit dem ärztlichen Attest des ADAC als zweiter Seite).</p>
<ul>
<li><strong>PDF ansehen / herunterladen</strong> – zum Drucken, Faxen oder Ablegen.</li>
<li><strong>E-Mail vorbereiten</strong> lädt eine Datei <em>.eml</em>. Ein Doppelklick öffnet sie in Outlook als fertigen
Entwurf mit Empfänger, Betreff, Text und der PDF im Anhang – prüfen und senden. Empfänger, Betreff und Text lassen sich
vorher im Dialog ändern; <strong>Weitere Anlagen</strong> (z. B. Leitfaden Zottentraining) werden mit angehängt.</li>
<li>Auf Wunsch wird die PDF als Dokument „Schreiben“ in der Akte abgelegt.</li>
</ul>
<p>Das <strong>Infoblatt an die Praxis</strong> mit allen Patienten der nächsten Sprechstunden entsteht im
<strong>Kalender › Praxis informieren</strong> (siehe „Infoblatt an die Praxis“).</p>
<p>Texte ändern: Vorlagen › Dokumentvorlagen; Betreff und Text der E-Mail stehen dort im Baustein <strong>E-Mail</strong>.
Eigene Schreiben (z. B. an Hausärzte) legt <strong>+ Neue Vorlage</strong> unter Vorlagen › Dokumentvorlagen an; sie
erscheinen danach hier unter „Eigene Vorlagen“. Anlagen hochladen: Vorlagen › Anlagen für E-Mails. Für eine <strong>Fallzusammenfassung</strong> im Reiter Berichte die
Berichtsart „Fallzusammenfassung“ wählen und <strong>Gliederung einfügen</strong>.</p>""",
    },
    {
        "id": "spalten", "gruppe": "patienten", "titel": "Karten vergrößern und Spalten verbreitern", "rechte": [], "seiten": [],
        "html": """
<p>Auf breiten Bildschirmen nutzen alle Seiten die volle Breite und teilen sich in Stufen auf (ab 1440, 1920 und
2560 px).</p>
<p>In der Übersicht der Akte und unter Administration › System stehen die Karten in einem Raster wie auf der
Startseite. Das <strong>Größen-Symbol</strong> oben rechts an jeder Karte stellt ihre <strong>Breite</strong> (1 Spalte
bis ganze Breite) und <strong>Höhe</strong> (automatisch oder 1–4 Zeilen; der Inhalt scrollt dann in der Karte) ein;
<strong>Standardgröße</strong> setzt zurück. Gespeichert wird je Person.</p>
<p>Im Plan-Editor lässt sich der <strong>Teiler</strong> zwischen den Spalten ziehen wie bei einem Fenster, in der
Ansicht „Seitenleiste“ der Akte die Breite der Leiste.</p>
<ul>
<li>Er rastet an festen Punkten ein.</li>
<li><strong>Doppelklick</strong> auf den Teiler setzt auf den Standard zurück.</li>
<li>Per Tastatur: Teiler mit Tab wählen, ← und → springen zum nächsten Einrastpunkt.</li>
</ul>
<p>Die Aufteilung wird je Seite, Fensterstufe und Person gespeichert.</p>""",
    },
    {
        "id": "stammdaten", "gruppe": "patienten", "titel": "Stammdaten, Diagnose und Therapie ändern",
        "rechte": ["akten_bearbeiten"], "seiten": ["/patienten/:id/therapie", "/patienten/:id/empfehlung", "/patienten/:id/diagnosen"],
        "html": """
<p>Stammdaten (Name, Anschrift, Telefon und Telefon 2, Versicherungsart, Versicherung und Versichertennummer, Versorger,
Katheter, Nickelallergie …) ändert <strong>Bearbeiten</strong> auf der Karte „Anschrift und Kontakt“ der Übersicht –
oder <strong>Weitere Aktionen › Stammdaten bearbeiten</strong> im Aktenkopf.</p>
<p>Die Diagnoseliste mit ICD-Code und die Notizen stehen im Reiter <strong>Diagnosen</strong>. Kennzeichen: gesichert
(G), Verdacht (V), Zustand nach (Z), Ausschluss (A). <strong>Beenden</strong> fragt nach; beendete Diagnosen bleiben
unter „beendete anzeigen“ erhalten und lassen sich wieder als aktuell eintragen.</p>
<p><strong>Therapie</strong> und <strong>Empfehlung</strong> (aus der letzten Sprechstunde; sie steht auch auf den
Unterlagen für die Sprechstunde) haben je einen Reiter: links die Fassungen, rechts der Text. Erst wird gelesen,
<strong>Bearbeiten</strong> öffnet den Editor, <strong>Abbrechen</strong> verwirft die Eingabe. Jede gespeicherte
Fassung bekommt eine Versionsnummer, frühere Fassungen bleiben lesbar.</p>
<p>Jede Änderung steht mit Person und Zeitpunkt im Verlauf der Akte.</p>""",
    },
    {
        "id": "akte_abschliessen", "gruppe": "patienten", "titel": "Akte abschließen und wieder öffnen",
        "rechte": ["akten_abschliessen", "akten_wieder_oeffnen"], "seiten": [],
        "html": """
<p>Endet die Betreuung, wird die Akte über <strong>Weitere Aktionen › Akte abschließen</strong> mit Anlass (verstorben,
Therapie beendet, Betreuung gewechselt) und Datum abgeschlossen. Admins dürfen das auch bei echten Akten. Sie bleibt vollständig lesbar, wird aber nicht mehr
verändert; erst mit dem Abschluss beginnt die Aufbewahrungsfrist.</p>
<p>Nach einem Versehen kann die Administration die Akte mit Grund <strong>wieder öffnen</strong>; der Grund steht im
Verlauf und im Audit-Log.</p>""",
    },
    {
        "id": "verlauf", "gruppe": "patienten", "titel": "Verlauf der Akte", "rechte": ["akten_lesen"],
        "seiten": ["/patienten/:id/verlauf"],
        "html": """
<p>Der Reiter <strong>Verlauf</strong> zeigt jede Änderung an der Akte mit Person und Zeitpunkt: neue Einträge,
Korrekturen mit vorherigem Wert, Stornos, Pläne, Dokumente. Er lässt sich nach Bereich und Person filtern und als PDF
ausgeben.</p>""",
    },
    {
        "id": "befunde", "gruppe": "patienten", "titel": "Labor und BIA", "rechte": ["akten_lesen"],
        "seiten": ["/patienten/:id/labor", "/patienten/:id/bia"],
        "html": """
<p><strong>Labor:</strong> Eingetragen wird nur der gemessene Wert – die Einheit steht in der Maske schon da. Werte
außerhalb des Referenzbereichs sind hervorgehoben. Die Parameter pflegt die Administration unter Vorlagen › Labor und
Diagnosen.</p>
<p><strong>BIA:</strong> Körperzusammensetzung (BCM, Fettmasse, ECW, Körperwasser …) mit Beurteilung. Das Gewicht der
Messung wandert auf Wunsch in den Gewichtsverlauf der Akte.</p>
<p>Ein Befund gilt nach der unter Vorlagen › Grenzwerte eingestellten Zeit als alt; die Akte zeigt dann einen Hinweis.
<strong>Bearbeiten</strong> berichtigt einen Befund, die bisherige Fassung bleibt im Verlauf.</p>""",
    },
    {
        "id": "berichte", "gruppe": "patienten", "titel": "Berichte", "rechte": ["akten_lesen"],
        "seiten": ["/patienten/:id/berichte"],
        "html": """
<p><strong>Neuer Bericht</strong> legt einen Entwurf an (Titel, Berichtsart, Empfänger, Text). Entwürfe lassen sich
bearbeiten oder <strong>verwerfen</strong> (mit Rückfrage). Wer das Recht hat, <strong>gibt frei</strong>: Der Bericht
ist dann unveränderlich, seine PDF liegt bei den Dokumenten der Akte. Eine Korrektur ist ein neuer Bericht.</p>""",
    },
    {
        "id": "tastatur", "gruppe": "patienten", "titel": "Tastenkürzel in der Akte", "rechte": ["akten_lesen"],
        "seiten": [],
        "html": """
<p>In einer geöffneten Akte (nicht, während in einem Eingabefeld geschrieben wird):</p>
<ul>
<li><strong>K</strong> Kontakt erfassen · <strong>G</strong> Gewicht erfassen · <strong>T</strong> Neuer Termin</li>
<li><strong>P</strong> Neuer Plan bzw. Entwurf fortsetzen</li>
<li><strong>Alt+1 … Alt+9</strong> Reiter der Akte wechseln (in der Reihenfolge der Reiter)</li>
<li><strong>?</strong> Übersicht der Tastenkürzel</li>
</ul>
<p>In Dialogen speichert <strong>Strg Enter</strong>, <strong>Esc</strong> schließt. Überall: <strong>Strg K</strong>
Patientensuche. Die Knöpfe zeigen ihr Kürzel beim Überfahren mit der Maus. In der Ansicht „Karteikarte“ gibt es
zusätzlich die Kürzelzeile („K Text“, „G 61,2“, „T“, „P“).</p>""",
    },
    # ------------------------------------------------------------------ Kontakte und Termine
    {
        "id": "kontakt_erfassen", "gruppe": "kontakte", "titel": "Kontakt erfassen", "rechte": ["eintraege_erfassen"],
        "seiten": ["/patienten/:id/kontakte"],
        "html": """
<p>Kontakte sind das Protokoll der Kommunikation mit dem Patienten: jedes Telefonat, jede Absprache mit dem Versorger
und jeder Besuch. Ein gespeicherter Kontakt wird nicht mehr geändert.</p>
<ol>
<li><strong>Kontakt</strong> im Aktenkopf, <strong>Neuer Kontakt</strong> im Reiter Kontakte, <strong>+ Kontakt</strong>
in der Übersicht, „K Text“ in der Kürzelzeile der Karteikarte, die Taste <strong>K</strong> oder
<strong>Kontakt erfassen</strong> auf der Startseite – alle öffnen denselben Dialog.</li>
<li>Text eintragen und die <strong>Kontaktart</strong> wählen (Liste unter Vorlagen › Auswahllisten). Auf Wunsch
<strong>Gewicht mit erfassen</strong>.</li>
<li>Für einen Rückruf, eine Wiedervorlage, einen Praxistermin oder Sonstiges <strong>Wiedervorlage anlegen</strong>
wählen. Vorgeschlagen wird eine Wiedervorlage in 14 Tagen (einstellbar unter Vorlagen › Grenzwerte); Datum, Uhrzeit
und Art lassen sich ändern. Sie erscheint auf der Startseite und im Kalender.</li>
<li><strong>Speichern</strong> (oder Strg Enter). Erfasst-von trägt EPM selbst ein.</li>
</ol>
<p>Vor einer Auskunft am Telefon im Aktenkopf unter <strong>Auskunft an</strong> nachsehen, wem Auskunft gegeben werden
darf. Termine der Akte stehen in der Übersicht und im Kalender.</p>""",
    },
    {
        "id": "kontakt_stornieren", "gruppe": "kontakte", "titel": "Kontakt stornieren", "rechte": ["eintraege_erfassen"],
        "seiten": [],
        "html": """
<p>War ein Kontakt falsch (Tippfehler, falscher Patient), wird er mit <strong>Stornieren</strong> und einem Grund
storniert. Er bleibt durchgestrichen sichtbar, mit Person, Zeitpunkt und Grund. Den richtigen Inhalt als neuen Kontakt
erfassen. Ein Kontakt lässt sich genau einmal stornieren.</p>""",
    },
    {
        "id": "termine", "gruppe": "kontakte", "titel": "Termine, Rückrufe und Wiedervorlagen", "rechte": ["akten_lesen"],
        "seiten": [],
        "html": """
<p>Termine gibt es als <strong>Rückruf</strong>, <strong>Wiedervorlage</strong>, <strong>Praxistermin</strong> (mit
Terminort) und <strong>Sonstiges</strong>. Ohne Uhrzeit gilt ein Termin als ganztägig.</p>
<p><strong>Neuer Termin</strong> über <strong>Termin</strong> in der Akte (Taste <strong>T</strong>), auf der Startseite,
im Kalender oder beim Kontakt. Offene Termine öffnet ein Klick (Titel in der Übersicht, Eintrag im Kalender oder in der
Karteikarte) gleich in <strong>Termin bearbeiten</strong> – dort auch <strong>Erledigt</strong> und
<strong>Akte öffnen</strong>. Auf Startseite und Übersicht hakt das Kästchen einen Termin als erledigt ab.</p>""",
    },
    {
        "id": "terminbestaetigung", "gruppe": "kontakte", "titel": "Terminbestätigung nach dem Speichern",
        "rechte": ["eintraege_erfassen"], "seiten": ["/kalender"],
        "html": """
<p>Speicherst du einen <strong>neuen Praxistermin</strong> oder <strong>verschiebst</strong> einen (Datum, Uhrzeit oder
Ort) und der Patient hat eine Anschrift oder E-Mail-Adresse, fragt EPM direkt danach:
<strong>„Terminbestätigung an Frau … schicken?“</strong></p>
<ul>
<li><strong>Ja, Bestätigung vorbereiten</strong> öffnet „Schreiben und E-Mail“ mit genau diesem Termin. Dort ein Klick auf
<strong>E-Mail vorbereiten</strong> (Outlook öffnet den Entwurf, du schickst ihn ab) oder <strong>PDF
herunterladen</strong> zum Drucken.</li>
<li><strong>Nicht jetzt</strong> schließt die Frage. Die Bestätigung lässt sich später im Termin („Bestätigung erstellen“)
oder in der Tagesliste nachholen.</li>
</ul>
<p>Der Termin merkt sich, wann eine Bestätigung erstellt wurde: Im Termin steht <strong>„Bestätigung erstellt am …“</strong>
oder <strong>„Bestätigung fehlt“</strong>. Wird der Termin verschoben, fehlt sie wieder. „PDF ansehen“ zählt nicht als
erstellt. Ob die Frage erscheint, stellt ein, wer Vorlagen pflegt (Vorlagen › Grenzwerte › Terminbestätigung).</p>""",
    },
    {
        "id": "kalender", "gruppe": "kontakte", "titel": "Kalender", "rechte": ["akten_lesen"], "seiten": ["/kalender"],
        "html": """
<p>Der Kalender zeigt alle Termine aller Patienten als <strong>Monat</strong>, <strong>Woche</strong> oder
<strong>Liste</strong>, dazu Feiertage (bundesweit und NRW) und berechnete Fälligkeiten:</p>
<ul>
<li><strong>Kontakt bald fällig</strong> und <strong>Kontakt überfällig</strong> – je Akte am Tag, an dem die Stufe
erreicht wird (Grenzwerte unter Vorlagen › Grenzwerte).</li>
<li><strong>Plan prüfen</strong>, wenn der aktuelle Infusionsplan älter wird als eingestellt.</li>
</ul>
<p>Ein Klick auf einen offenen Termin öffnet <strong>Termin bearbeiten</strong> (mit Erledigt und Akte öffnen);
Fälligkeiten und Erledigtes öffnen eine Ansicht. Das <strong>×</strong> an einem Eintrag blendet ihn aus – wie die
Hinweise in der Akte für 3, 6 oder 12 Monate oder als „nicht mehr nötig“, mit Grund.</p>
<p><strong>Anzeigen ▾</strong> wählt die Arten (Praxistermine, Rückrufe, Wiedervorlagen, Sonstiges, Kontakt fällig,
Plan prüfen) und ob Erledigte erscheinen – mit der Legende der Farben. Rechts (Tablet: darunter) stehen drei Reiter:
<strong>Tag</strong> (gewählter Tag und die nächsten 7 Tage, „+ Termin am …“), <strong>Überfällig</strong> (offene
Termine, Kontakt überfällig, Plan prüfen) und <strong>Fällig</strong> (Kontakt bald fällig). Am Telefon zeigt ein
Wochenband die Tage; darunter Tag, Überfällig und Woche.</p>""",
    },
    {
        "id": "infoblatt", "gruppe": "kontakte", "titel": "Infoblatt an die Praxis (alle Termine bei Dr. Holtmeier)",
        "rechte": ["eintraege_erfassen"], "seiten": ["/kalender", "/"],
        "html": """
<p>Die Praxis Dr. Holtmeier bekommt rechtzeitig <strong>ein Blatt mit allen Patienten</strong>, die dort in den
nächsten Tagen einen Termin haben – nicht ein Blatt je Patient. So geht es:</p>
<ol>
<li>Im <strong>Kalender</strong> oben auf <strong>Praxis informieren</strong> klicken – oder auf der Startseite auf
<strong>Infoblatt erstellen</strong>, wenn dort „Praxis Holtmeier informieren“ steht.</li>
<li>Den Zeitraum wählen: <strong>Nächste Woche</strong>, <strong>Übernächste Woche</strong>, <strong>Nächster
Monat</strong> oder <strong>Eigener Zeitraum</strong>.</li>
<li>Die Liste prüfen: Dort steht, wer auf dem Blatt steht, nach Tagen geordnet. <strong>neu</strong> heißt: seit dem
letzten Infoblatt dazugekommen oder verschoben.</li>
<li><strong>PDF herunterladen</strong> (zum Faxen) oder <strong>E-Mail vorbereiten</strong> (Outlook öffnet einen
fertigen Entwurf mit dem Blatt im Anhang).</li>
</ol>
<p>Auf dem Blatt stehen die Termine mit der Art <strong>Praxistermin</strong> und dem Ort <strong>Praxis Dr.
Holtmeier</strong>. Beim Anlegen eines Praxistermins ist dieser Ort schon eingetragen. Fehlt bei einem Praxistermin der
Ort, steht er nicht auf dem Blatt – der Dialog zeigt ihn dann gelb mit <strong>Ort eintragen</strong>.
Telefon- und Videotermine kommen nur dazu, wenn das Häkchen <strong>Telefon- und Videotermine auch aufführen</strong>
gesetzt ist (dann mit Telefonnummer). Hinweise wie „1 h, Neuaufnahme“ oder „+ Labor“ im Termin unter „bei/Ort“
eintragen – sie stehen hinter dem Namen. Testpatienten erscheinen nie.</p>
<p>Die Startseite erinnert vor der nächsten Woche (oder dem nächsten Monat), bis das Infoblatt erstellt ist. Wann sie
erinnert, steht unter Vorlagen › Grenzwerte › „Infoblatt an die Praxis“. Den Text des Blatts ändert man unter
Vorlagen › Dokumentvorlagen › „Patientenankündigung“.</p>""",
    },
    # ------------------------------------------------------------------ Gewicht
    {
        "id": "gewicht", "gruppe": "gewicht", "titel": "Gewicht eintragen und korrigieren", "rechte": ["eintraege_erfassen"],
        "seiten": [],
        "html": """
<p><strong>Gewicht</strong> im Aktenkopf, <strong>+ Gewicht</strong> auf der Karte „Gewichtsverlauf“, „G 54,6“ in der
Kürzelzeile, die Taste <strong>G</strong> oder <strong>Gewicht</strong> auf der Startseite öffnen denselben Dialog:
Gewicht, Quelle (telefonisch, Ambulanz, Versorger, Arztbrief) und Messdatum eintragen, <strong>Speichern</strong>. Beim
Kontakt geht es mit „Gewicht mit erfassen“ in einem Schritt, bei der BIA-Messung ebenso.</p>
<p>Unplausible Werte (außerhalb der Grenzwerte) und Daten in der Zukunft werden abgewiesen. Eine falsche Messung wird
mit <strong>Bearbeiten</strong> berichtigt – die letzte direkt per Klick auf den Wert oder „Bearbeiten“ auf der Karte,
ältere unter <strong>Messwerte anzeigen</strong>; die bisherige Fassung bleibt im Verlauf sichtbar.</p>""",
    },
    {
        "id": "gewicht_verlauf", "gruppe": "gewicht", "titel": "Gewichtsverlauf und Warnung", "rechte": ["akten_lesen"],
        "seiten": [],
        "html": """
<p>Das Diagramm zeigt die Messwerte über 12 Monate, 3 Jahre, 5 Jahre oder alle, wahlweise geglättet. Verliert ein
Patient mehr als den eingestellten Anteil in der eingestellten Zeit (Standard: mehr als 5 % in 3 Monaten), erscheint
eine Warnung in der Akte, in der Patientenliste und auf der Startseite unter „Auffällige Gewichte“ – dort mit einem
kleinen Verlauf der letzten 6 Monate in echten Zeitabständen.</p>""",
    },
    # ------------------------------------------------------------------ Infusionspläne
    {
        "id": "plan_ansehen", "gruppe": "plaene", "titel": "Infusionspläne ansehen", "rechte": ["akten_lesen"],
        "seiten": ["/patienten/:id/plaene", "/infusionsplaene"],
        "html": """
<p>Der Reiter <strong>Infusionspläne</strong> der Akte zeigt den aktuellen Plan, Entwürfe und frühere Pläne mit den
Änderungen gegenüber dem Vorgänger. Ein freigegebener Plan hat eine gespeicherte PDF mit Prüfsumme; EPM prüft beim Öffnen,
ob sie unverändert ist.</p>
<p>Die <strong>PDF</strong> steht direkt neben der Liste der Pläne, so hoch wie das Fenster: eine ganze Seite auf einen
Blick (<strong>Ganze Seite</strong>; − und + vergrößern auf die Breite). <strong>Groß ansehen</strong> öffnet sie im
Fenster, <strong>Herunterladen</strong> speichert sie. Entwürfe zeigen die Ansicht mit der aktiven Dokumentvorlage und dem
Wasserzeichen „ENTWURF“.</p>
<p>Der Menüpunkt <strong>Infusionspläne</strong> zeigt die Pläne aller Patienten: zur Freigabe, aktuell und älter als
eingestellt. Beim Überfahren des Status steht die Frist, ab der ein Plan als alt gilt. <strong>PDF</strong> gibt es an
jedem Plan (auch an Entwürfen); ab 1920 Bildpunkten Breite erscheint sie rechts neben der Liste, sonst im Fenster.</p>
<p>Jede Akte in Betreuung braucht einen freigegebenen Plan, sonst erscheint der Hinweis <strong>Kein
Infusionsplan</strong>. Braucht ein Patient keinen, unter Infusionspläne <strong>Kein Plan nötig</strong> wählen (mit
Grund): Der Hinweis und die Warnung „Plan älter als …“ entfallen; mit der nächsten Freigabe eines Plans endet die
Bestätigung.</p>""",
    },
    {
        "id": "plan_anlegen", "gruppe": "plaene", "titel": "Neuen Plan anlegen", "rechte": ["plaene_anlegen"],
        "seiten": ["/patienten/:id/plaene/neu", "/patienten/:id/plaene/:id/bearbeiten"],
        "html": """
<p><strong>Neuer Plan</strong> übernimmt die Werte des aktuellen Plans; geänderte Werte sind markiert. Beim ersten Plan
schlägt EPM Werte je kg Körpergewicht vor (Vorgabe der Praxis wie im Altsystem: Glucose 3,5 g, Aminosäuren 1,2 g,
Lipide 1 g, Natrium 1,3, Kalium 0,7, Phosphat 0,3, Calcium 0,15, Magnesium 0,2 mmol je kg). <strong>Mengen nach
Praxisvorgabe</strong> setzt diese Mengen jederzeit neu aus dem letzten Gewicht ein – Präparate und Zusätze bleiben.
<strong>Leer beginnen</strong> startet ohne Werte; <strong>Als Vorlage für neuen Plan</strong> (an einem früheren Plan)
übernimmt dessen Werte.</p>
<p>Volumen im Mischbeutel (letztes Gewicht × 35 ml) und Rate rechnet EPM mit. Die Karte <strong>Prüfung vor der
Freigabe</strong> sagt in einfachen Worten, was noch fehlt oder nicht passt: Gewicht vorhanden und nicht älter als
3 Monate, Präparat zu jeder Menge, Calcium + Magnesium stabil, Infusionstage stimmig, Laufzeit eingetragen,
Protonenpumpenhemmer mit Zeiten. Werte außerhalb der Grenzwerte stehen darüber. <strong>Als Entwurf speichern</strong>
macht den Plan für das Team sichtbar, noch nicht für den Versorger.</p>
<p><strong>PDF-Vorschau</strong> zeigt die PDF mit genau den Werten, die gerade im Formular stehen – auch ungespeicherte;
gespeichert wird dabei nichts (ein neuer Plan wird dafür einmal als Entwurf gespeichert). Ab 1920 px zeigt zusätzlich eine
dritte Spalte die Vorschau des zuletzt gespeicherten Entwurfs.</p>""",
    },
    {
        "id": "plan_freigeben", "gruppe": "plaene", "titel": "Plan freigeben", "rechte": ["plaene_freigeben"], "seiten": [],
        "html": """
<p><strong>Speichern und freigeben</strong> macht den Plan zum aktuellen Plan. Dabei wird die PDF mit der aktiven
Dokumentvorlage erzeugt und mit Prüfsumme gespeichert; der vorherige Plan bleibt im Verlauf erhalten.</p>""",
    },
    {
        "id": "plan_abschliessen", "gruppe": "plaene", "titel": "Plan nach Freigabe abschließen",
        "rechte": ["plaene_abschliessen"], "seiten": [],
        "html": """
<p>Hat der Mediziner einen Entwurf außerhalb von EPM freigegeben (z. B. per E-Mail), wird der Entwurf mit
<strong>Nach Freigabe abschließen</strong> zum aktuellen Plan. Anzugeben sind wer freigegeben hat, das Datum, der Weg
der Freigabe und der Nachweis (z. B. die E-Mail als PDF).</p>""",
    },
    # ------------------------------------------------------------------ Dokumente
    {
        "id": "dokumente", "gruppe": "dokumente", "titel": "Dokumente hochladen und ansehen", "rechte": ["akten_lesen"],
        "seiten": ["/patienten/:id/dokumente"],
        "html": """
<p>Im Reiter <strong>Dokumente</strong> liegen Arztbriefe, Befunde, Erklärungen und erzeugte PDFs. Ablegen mit
<strong>Neues Dokument</strong> (PDF, Bild oder Text, höchstens 50 MB) – oder die Datei einfach auf die geöffnete Akte
ziehen; im Aktenkopf geht es auch über <strong>Weitere Aktionen › Dokument hochladen</strong>. Danach rechts Typ, Titel
und Dokumentdatum ergänzen und <strong>Speichern</strong>. EPM schlägt das Datum aus der Datei vor.</p>
<p>Die Suche über der Liste findet Wörter in Titel und Notiz und – nach <strong>Text erkennen</strong> – auch im
Inhalt eines gescannten Briefs.</p>
<p>Dokumente werden in EPM angezeigt, ohne das PDF-Programm des PCs. Ausgeblendete Dokumente sind nicht gelöscht.</p>""",
    },
    {
        "id": "altdokumente", "gruppe": "dokumente", "titel": "Altdokumente prüfen", "rechte": ["eintraege_erfassen"],
        "seiten": [],
        "html": """
<p>Aus dem Altsystem übernommene Dokumente haben einen geschätzten Typ und ein Datum aus den Metadaten. Sie stehen unter
„Nach und nach prüfen“ auf der Startseite – mit Fortschritt („312 von 1.140 geprüft“). Typ und Datum ansehen,
bei Bedarf korrigieren und <strong>Typ und Datum bestätigen</strong>.</p>""",
    },
    {
        "id": "dokument_falsch", "gruppe": "dokumente", "titel": "Falsch zugeordnetes Dokument",
        "rechte": ["dokumente_umhaengen", "dokumente_loeschen"], "seiten": [],
        "html": """
<p>Liegt ein Dokument in der falschen Akte, ordnet <strong>Anderem Patienten zuordnen</strong> es mit Grund um. Beide
Akten zeigen den Vorgang im Verlauf, ohne den jeweils anderen Patienten zu nennen.</p>
<p>Gehört es in keine Akte, kann es <strong>endgültig gelöscht</strong> werden (nur Mediziner und Admin): mit Passwort,
Code aus der Authenticator-App und einem Bestätigungscode. Datei, Titel und Inhalt werden entfernt; im Audit-Log bleibt
ein neutraler Nachweis.</p>""",
    },
    # ------------------------------------------------------------------ Datenschutz
    {
        "id": "erklaerungen", "gruppe": "datenschutz", "titel": "Erklärungen erfassen",
        "rechte": ["datenschutz_bearbeiten"], "seiten": ["/patienten/:id/datenschutz"],
        "html": """
<p>Datenschutzinformation, Einwilligung und Schweigepflichtentbindung werden im Reiter <strong>Datenschutz</strong> der
Akte nachgehalten. <strong>Vordruck als PDF</strong> ausdrucken, unterschreiben lassen, mit Datum
<strong>erfassen</strong> – auf Wunsch mit Scan. Ein Widerruf wird mit <strong>Widerruf eintragen</strong>
festgehalten.</p>
<p>Fehlt eine der Erklärungen, die vorliegen sollen, steht ein Hinweis im Aktenkopf und unter „Nach und nach prüfen“.</p>""",
    },
    {
        "id": "anfragen", "gruppe": "datenschutz", "titel": "Anfragen betroffener Personen",
        "rechte": ["datenschutz_bearbeiten", "datenschutz_entscheiden"], "seiten": ["/datenschutz"],
        "html": """
<p>Auskunft, Berichtigung, Löschung, Einschränkung oder Widerruf werden als <strong>Anfrage</strong> mit Eingangsdatum
erfasst. EPM rechnet die Frist (ein Monat, verlängerbar um zwei) und zeigt überfällige Anfragen an. Entschieden und
erledigt wird mit Ergebnis und Begründung; nichts davon wird gelöscht.</p>
<p>Für eine Auskunft erstellt EPM eine <strong>Kopie der Akte</strong>. Der Menüpunkt <strong>Datenschutz</strong>
zeigt alle offenen Anfragen.</p>""",
    },
    {
        "id": "einschraenken", "gruppe": "datenschutz", "titel": "Verarbeitung einschränken und Einsicht nehmen",
        "rechte": ["datenschutz_entscheiden"], "seiten": [],
        "html": """
<p>Eine Akte mit <strong>eingeschränkter Verarbeitung</strong> (Art. 18 DSGVO) bleibt gespeichert, erscheint aber in
keiner Liste. Lesen kann sie nur, wer über Anfragen entscheidet – mit einer <strong>begründeten Einsicht</strong>, die
60 Minuten gilt und mit Grund im Audit-Log steht.</p>""",
    },
    {
        "id": "loeschen", "gruppe": "datenschutz", "titel": "Akte endgültig löschen", "rechte": ["akten_loeschen"],
        "seiten": [],
        "html": """
<p>Nach Ablauf der Aufbewahrungsfrist oder auf Antrag kann eine abgeschlossene Akte <strong>endgültig gelöscht</strong>
werden – mit Passwort, Code aus der Authenticator-App und Bestätigungscode. Es bleibt nur ein Eintrag im Löschprotokoll
(Nummer, Daten der Frist, Grund, Umfang) ohne Namen und Inhalte. Wird später eine ältere Sicherung zurückgespielt,
löscht EPM die Akte beim Start erneut.</p>""",
    },
    # ------------------------------------------------------------------ Versorger und Ärzte
    # ------------------------------------------------------------------ Scans und Texterkennung (F160 ff.)
    {
        "id": "scans", "gruppe": "scans", "titel": "Scans: hochladen, erkennen, zuordnen", "rechte": ["scans_bearbeiten"],
        "seiten": ["/scans"],
        "html": """
<p>Unter <strong>Scans</strong> kommen gescannte oder fotografierte Unterlagen an, bevor sie zu einer Akte gehören –
Arztbriefe, Laborbefunde, BIA-Ausdrucke, auch was Patienten selbst einscannen oder fotografieren.</p>
<ol>
<li><strong>Hochladen</strong> wählen oder Dateien irgendwo auf die Seite ziehen (PDF, JPG, PNG, TIFF, WEBP, HEIC). Mehrere
Fotos werden auf Wunsch ein Dokument mit mehreren Seiten. Am Telefon gibt es den Knopf <strong>Foto</strong>.</li>
<li>Die Seiten werden automatisch aufbereitet: Das Blatt wird im Foto gefunden und gerade gezogen, gewellte Seiten
geglättet, Drehung und Schräglage ausgeglichen, Schatten und Rauschen entfernt. Danach wird der Text erkannt – im
EPM selbst, ohne Internet und ohne fremde Dienste. Das dauert je Seite einige Sekunden bis etwa eine halbe Minute.</li>
<li>Den erkannten Text mit <strong>Text kopieren</strong> übernehmen (Tabellen werden mit Tabulator kopiert und lassen
sich so in eine Tabelle einfügen) – oder den Scan mit <strong>Zuordnen</strong> in eine Akte legen.</li>
</ol>
<p>Nicht zugeordnete Scans werden nach der eingestellten Frist (Standard 7 Tage) automatisch gelöscht. Mit
<strong>verlängern</strong> bleibt ein Scan länger, höchstens bis zur Höchstdauer ab dem Hochladen (Standard 30 Tage).
Die Fristen stellt ein, wer Vorlagen pflegt (<strong>Vorlagen › Grenzwerte › Scans und Texterkennung</strong>).</p>
<p>Die Zahl neben „Scans“ in der Navigation nennt die Scans, die auf Zuordnung warten oder gerade erkannt werden.
Gesehen und bearbeitet werden Scans von allen mit dem Recht „Scans“; Betrachter sehen sie nicht.</p>""",
    },
    {
        "id": "scans_erkennung", "gruppe": "scans", "titel": "Unsichere Stellen, Seite anpassen, Bereich neu erkennen",
        "rechte": ["scans_bearbeiten"], "seiten": [],
        "html": """
<p>Jede Seite wird mit <strong>zwei Verfahren</strong> gelesen (Tesseract mit dem genauesten deutschen Modell und
PP-OCR). Lesen beide dasselbe, gilt das Wort als sicher. Weichen sie ab, gewinnt die sicherere Lesart, das Wort ist
aber <strong>gelb unterlegt</strong> – beim Überfahren steht die andere Lesart. Gelbe Stellen bitte mit dem Bild
vergleichen.</p>
<ul>
<li><strong>Anpassen</strong>: Ecken des Blatts von Hand verschieben, drehen, Glätten an/aus, Schräglage, Darstellung
(Graustufen, Farbe, Schwarz-Weiß), Kontrast und Helligkeit. Danach wird die Seite neu aufbereitet und erkannt.</li>
<li><strong>Bereich neu erkennen</strong>: einen schlecht lesbaren Bereich mit der Maus einrahmen; er wird vergrößert
und neu gelesen, der übrige Text bleibt.</li>
<li><strong>Original</strong> zeigt die Seite so, wie sie hochgeladen wurde.</li>
<li>Mehrere Seiten lassen sich umsortieren und entfernen. Ein Stapel mit Unterlagen mehrerer Patienten lässt sich
im Menü „⋯“ <strong>ab einer Seite abtrennen</strong>; umgekehrt lässt sich ein anderer Scan hinten anhängen.</li>
</ul>
<p>Handschrift wird nicht zuverlässig erkannt. Am besten lesbar sind Scans mit mindestens 300 dpi oder Fotos, auf
denen das Blatt flach und vollständig zu sehen ist.</p>
<p>Fachwörter, die oft falsch gelesen werden (Präparate, Wirkstoffe), lassen sich unter <strong>Vorlagen ›
Grenzwerte › Fachwörter für die Texterkennung</strong> eintragen.</p>""",
    },
    {
        "id": "scans_zuordnen", "gruppe": "scans", "titel": "Zuordnen und Werte übernehmen (Labor, BIA, Diagnosen)",
        "rechte": ["scans_bearbeiten"], "seiten": [],
        "html": """
<p><strong>Zuordnen</strong> legt den Scan als Dokument in die Akte: eine durchsuchbare PDF (das aufbereitete Bild mit
dem erkannten Text darüber). Auf Wunsch wird die hochgeladene Datei zusätzlich unverändert abgelegt. Danach ist der
Scan aus „Scans“ verschwunden. Im Reiter <strong>Dokumente</strong> der Akte lässt sich auch im erkannten Text suchen.</p>
<ul>
<li><strong>Patient</strong>: Stehen Name und Geburtsdatum im Dokument, steht oben „Wahrscheinlich: Erika Muster,
geb. 14.03.1968 – übernehmen?“ mit dem Grund (z. B. „Name und Geburtsdatum erkannt“, auch wenn der Name leicht falsch
gelesen wurde). Ein Klick auf <strong>Übernehmen</strong> wählt den Patienten; zugeordnet wird erst mit „In die Akte
legen“. Passen mehrere Akten, wählen Sie eine aus; ist der Treffer unsicher, steht dort nur ein Hinweis. Vorgeschlagen
werden nur Akten, die Sie sehen dürfen. Passt das Dokument nicht zum gewählten Patienten (anderes Geburtsdatum, Name
kommt nicht vor), erscheint ein Hinweis – bitte dann genau prüfen.</li>
<li><strong>Laborbefund</strong>: Die erkannten Werte stehen in einer Tabelle mit Parameter, Wert, Einheit und
Referenzbereich. Werte in anderen Einheiten werden in die Einheit des Laborkatalogs umgerechnet (z. B. g/dl → g/l).
Ein Klick auf eine Zeile zeigt die Stelle im Bild. Unsicher gelesene oder unplausible Werte sind
<strong>nicht vorgewählt</strong>. Abnahmedatum und Labor werden vorbelegt.</li>
<li><strong>BIA-Messung</strong>: Gewicht, BCM, Fettmasse, ECW, Körperwasser, BMI; weitere Werte des Protokolls
(z. B. Phasenwinkel) kommen in die Beurteilung. Das Gewicht kann zugleich in den Gewichtsverlauf.</li>
<li><strong>Diagnosen mit ICD-Code</strong> (z. B. „K91.2 G“) aus Arztbriefen; „V.a.“ wird zu V, „Z.n.“ zu Z.</li>
<li><strong>Texte</strong>: Abschnitte wie „Diagnosen:“, „Therapie:“, „Procedere:“ lassen sich an die Textfelder der Akte
anhängen – mit Quelle und Datum.</li>
</ul>
<p>Nichts wird ohne Bestätigung übernommen. Ist etwas ungültig, entsteht gar nichts und die Fehler stehen an der
jeweiligen Zeile. Laborparameter, die ein Labor anders schreibt, lassen sich unter <strong>Vorlagen › Labor und
Diagnosen</strong> mit <strong>Suchbegriffen</strong> ergänzen – oder EPM lernt sie (nächster Abschnitt).</p>""",
    },
    {
        "id": "scans_gelernt", "gruppe": "scans", "titel": "Die Texterkennung lernt mit (gelernte Zuordnungen)",
        "rechte": ["scans_bearbeiten"], "seiten": [],
        "html": """
<p>Die Texterkennung lernt aus Ihren Korrekturen. Ordnen Sie beim Zuordnen eine Zeile einem anderen Laborwert zu,
verbessern Sie einen falsch gelesenen Namen (auch bei Diagnosen) oder ergänzen Sie einen Wert, indem Sie ihn im Bild
anklicken, merkt sich EPM die <strong>Bezeichnung auf dem Befund</strong> und wohin sie gehört – für dieses Labor und
allgemein. Bei Laboren, die ihre Werte immer an derselben Stelle drucken, merkt sich EPM auch die Spalte.</p>
<ul>
<li>Beim nächsten Befund steht dann ein Vorschlag mit dem Zeichen <strong>„gelernt?“</strong> da – noch nicht
angehakt. Ab der zweiten Bestätigung gilt die Zuordnung als sicher (<strong>„gelernt“</strong>) und ist vorgewählt.</li>
<li>Prüfen und übernehmen müssen Sie wie immer selbst: Ohne Ihre Bestätigung kommt nichts in die Akte.</li>
<li>Gespeichert werden nur Bezeichnungen, z. B. „Harnstoff-N → Harnstoff“ – keine Werte und keine Angaben zu
Patienten. Alles bleibt auf dem Server; nichts geht ins Internet.</li>
</ul>
<p>Unter <strong>Scans › Gelernte Zuordnungen</strong> sehen Sie alles Gelernte mit Suche und Filter nach Labor und
Art. Stimmt eine Zuordnung nicht, wählen Sie <strong>Löschen</strong> (sie kann neu gelernt werden) oder
<strong>Sperren</strong> – dann ordnet EPM diese Bezeichnung nie wieder so zu.</p>
<p>Unten in der Liste der Scans steht, welcher Anteil der übernommenen Werte in diesem Monat noch korrigiert werden
musste, mit Pfeil im Vergleich zum Vormonat (▼ = besser). Ein Klick zeigt den Verlauf über zwölf Monate.</p>
<p><strong>Wer darf was?</strong> Lernen tut EPM bei jedem, der Scans zuordnet (Übungszugänge ausgenommen). Ansehen,
sperren und löschen dürfen alle mit dem Recht „Scans“ oder „Vorlagen pflegen“. Unter <strong>Gelernte
Zuordnungen</strong> kann, wer Vorlagen pflegt, das Lernen <strong>pausieren</strong> (Gelerntes wird weiter genutzt)
und einstellen, ab wie vielen Bestätigungen (1, 2 oder 3) etwas als sicher gilt. Jede Änderung steht im Protokoll.</p>""",
    },
    {
        "id": "scans_verbessern", "gruppe": "scans", "titel": "So verbessern Sie die Erkennung",
        "rechte": ["scans_bearbeiten"], "seiten": ["/scans"],
        "html": """
<p>EPM liest den Text aus dem Bild. Manchmal verliest es sich: Es nimmt eine Kopfzeile für einen Wert, liest
„Kreatimin“ statt „Kreatinin“ oder übersieht eine Zeile. Mit diesen Schritten machen Sie den nächsten Befund besser.</p>
<ol>
<li><strong>Vergleichen.</strong> Tippen Sie beim Zuordnen auf eine Zeile. Links im Bild leuchtet die Stelle auf,
an der EPM gelesen hat.</li>
<li><strong>Falsches anmerken.</strong> Stimmt eine Zeile nicht, tippen Sie auf <strong>Falsch erkannt</strong> und
wählen den Grund:
<ul>
<li><em>Gehört nicht dazu</em> – zum Beispiel die Zeile „Referenzbereich“, eine Überschrift oder ein Datum.
EPM lässt diese Zeile bei diesem Labor künftig weg.</li>
<li><em>Falsche Zeile</em> – die Bezeichnung gehört zu einem anderen Wert, zum Beispiel „Eisen“ wurde dem Ferritin
zugeordnet. EPM ordnet das bei diesem Labor nicht mehr so zu.</li>
<li><em>Falscher Wert</em> – die Zahl ist falsch gelesen, zum Beispiel 3,8 statt 3,0. Die Zeile verschwindet; tragen Sie
den Wert mit <strong>+ Wert</strong> richtig ein.</li>
</ul></li>
<li><strong>Fehlendes markieren.</strong> Fehlt ein Wert, tippen Sie auf <strong>Bereich markieren</strong> und ziehen
mit der Maus oder dem Finger einen Rahmen um die richtigen Zeilen im Bild. EPM liest nur diesen Teil noch einmal
genauer und zeigt jede Zeile als neuen Wert. Einen einzelnen Wert können Sie auch anklicken: Feld wählen, dann die
Zahl im Bild antippen.</li>
<li><strong>Prüfen und übernehmen.</strong> Wählen Sie bei Bedarf den richtigen Laborwert aus der Liste und legen Sie
alles in die Akte. Erst dann merkt sich EPM Ihre Auswahl – für dieses Labor und allgemein.</li>
</ol>
<p>Beim nächsten Befund desselben Labors macht EPM es dann selbst richtig oder schlägt es vor („gelernt?“). Gespeichert
werden nur Bezeichnungen und die Lage auf der Seite, keine Werte und keine Namen. Hat EPM etwas Falsches gelernt,
löschen oder sperren Sie es unter <strong>Scans › Gelernte Zuordnungen</strong>.</p>""",
    },
    {
        "id": "versorger", "gruppe": "listen", "titel": "Versorger und Ansprechpartner", "rechte": [],
        "seiten": ["/versorger"],
        "html": """
<p>Die Liste <strong>Versorger</strong> gilt für alle Akten. Links stehen die Versorger mit Ort, Zahl der
Ansprechpartner und rechts der Zahl der Patienten in Betreuung; das Suchfeld findet Firma, Ort, Telefon und
Ansprechpartner, „Aktiv | Inaktiv | Alle“ filtert. Rechts der gewählte Versorger zum Lesen: Anschrift, Erreichbarkeit,
Notiz, die <strong>Ansprechpartner</strong> (mit Zuständigkeit, Telefon und Patientenzahl – ein Klick auf die Zahl
öffnet die Patientenliste) und die <strong>Patienten in Betreuung</strong> (nach Name oder nach Ansprechpartner).</p>
<p>Mit dem Recht „Versorger, Ansprechpartner und Ärzte pflegen“: <strong>Bearbeiten</strong> öffnet das Formular an
derselben Stelle; <strong>+ Ansprechpartner</strong> legt einen an, ein Klick auf den Namen bearbeitet ihn.
<strong>Deaktivieren</strong> (Menü „⋯“, mit Rückfrage) nimmt einen Versorger aus der Auswahl; gelöscht wird nie,
deaktivierte bleiben in allen Akten und Plänen sichtbar. Wird ein Ansprechpartner deaktiviert, zeigt EPM seine
Patienten zum Neuzuordnen an. Jede Änderung steht mit Person und Zeitpunkt im Audit-Log.</p>
<p>Am Telefon erscheint erst die Liste; ein Eintrag öffnet sich ganz, „‹ Liste“ führt zurück.</p>""",
    },
    {
        "id": "aerzte", "gruppe": "listen", "titel": "Ärzte", "rechte": [], "seiten": ["/aerzte"],
        "html": """
<p>Die Liste <strong>Ärzte</strong> enthält Hausärzte und andere Ärzte mit Praxis und Kontaktdaten – aufgebaut wie die
Versorger: links die Liste mit Suche (Name, Praxis, Fachrichtung, Ort) und Patientenzahl, rechts der gewählte Arzt mit
Praxis, Erreichbarkeit, Notiz und den zugeordneten Patienten in Betreuung. <strong>Bearbeiten</strong> öffnet das
Formular, <strong>Deaktivieren</strong> steht im Menü „⋯“ (mit Rückfrage): ein deaktivierter Arzt ist bei neuen
Zuordnungen nicht mehr wählbar, bleibt aber in allen Akten sichtbar.</p>
<p>In der Akte werden Ärzte unter „Ärzte“ mit ihrer Rolle zugeordnet; der Hausarzt erscheint im Aktenkopf. Fehlt ein
Arzt, legt „Neuen Arzt anlegen“ ihn gleich im Dialog an.</p>""",
    },
    # ------------------------------------------------------------------ Administration
    {
        "id": "systemverwaltung", "gruppe": "administration", "titel": "Systemverwaltung: Zustand auf einen Blick, ohne SSH",
        "rechte": ["system_verwalten", "backup_verwalten"], "seiten": ["/admin"],
        "html": """
<p><strong>Administration › Systemverwaltung</strong> zeigt als Ampel, ob alles in Ordnung ist: Systemagent, Dienste
(Container), Speicherplatz, Ubuntu-Updates, Zertifikat, Texterkennung, Uhrzeit, letzte Sicherung, Übertragung und
fehlgeschlagene Aufträge. Jede Kachel führt direkt zu dem Bereich, in dem man etwas tun kann. Daneben stehen die häufigen
Aufgaben (sichern, Updates, Neustart, Software, Zertifikat, Protokolle, Hinweis an alle, Benutzer, Audit-Log) und die
Auslastung als kleiner Verlauf – <strong>Größer anzeigen</strong> öffnet das große Diagramm.</p>
<p>Alles, was früher nur per SSH ging, läuft hier als Auftrag an den Systemagenten auf dem Server: nur fest eingetragene
Tätigkeiten, Gefährliches mit Passwort und Code aus der Authenticator-App, alles im Audit-Log. Per SSH bleibt nur die
Ersteinrichtung des Servers.</p>""",
    },
    {
        "id": "admin_start", "gruppe": "administration", "titel": "Startseite der Administration",
        "rechte": ["system_verwalten", "backup_verwalten", "benutzer_verwalten", "audit_lesen", "testdaten_zuruecksetzen"],
        "seiten": [],
        "html": """
<p>Für die Administration zeigt die Startseite eigene Kacheln – jeweils nur mit dem passenden Recht:</p>
<ul>
<li><strong>Datensicherung</strong>: letzte Sicherung, Übertragung, Speicher; „Jetzt sichern“.</li>
<li><strong>Server</strong> und <strong>Ubuntu-Updates</strong>: Auslastung, offene Updates; Updates installieren und
Server neu starten – mit Passwort und 2FA, vorher automatische Sicherung, angemeldete Benutzer werden gewarnt.</li>
<li><strong>Konten</strong>: gesperrt, Einmal-Passwort offen, ohne zweiten Faktor, Notfall-Codes knapp.</li>
<li><strong>Angemeldet</strong>, <strong>Hinweis an alle</strong>, <strong>Zugriffe · 7 Tage</strong> aus dem Audit-Log
und <strong>Testumgebung</strong>.</li>
</ul>""",
    },
    {
        "id": "vorlagen", "gruppe": "administration", "titel": "Vorlagen: Auswahllisten, Präparate, Briefkopf",
        "rechte": ["vorlagen_pflegen"], "seiten": ["/admin/vorlagen"],
        "html": """
<p>Unter <strong>Vorlagen</strong> beginnt alles mit der <strong>Übersicht</strong>: je Bereich eine Kachel mit „Wofür?“
und „Wo benutzt?“ – Briefe, Formulare und E-Mail-Texte, Briefkopf und Logo, Medikamente und Präparate, Auswahllisten
(z. B. Katheter, Dokumenttypen, Terminorte), Labor und Diagnosen, Grenzwerte und Fristen, Anlagen für E-Mails. Das Feld
<strong>Was möchten Sie ändern?</strong> sucht in allen Vorlagen, Listen, Präparaten und Anlagen und führt direkt hin.</p>
<p>In den <strong>Auswahllisten</strong> steht über jeder Liste, wo sie in EPM zur Auswahl kommt. Die Reihenfolge ändern
▲ ▼ (auch am Tablet), Ziehen am Griff oder die Pfeiltasten. Nicht mehr benötigte Einträge werden
<strong>ausgeblendet statt gelöscht</strong>: Sie werden nicht mehr angeboten, bleiben aber dort stehen, wo sie schon
eingetragen sind. Jede Änderung steht im Audit-Log; das „?“ neben einer Überschrift erklärt den Bereich.</p>""",
    },
    {
        "id": "grenzwerte", "gruppe": "administration", "titel": "Grenzwerte", "rechte": ["vorlagen_pflegen"], "seiten": [],
        "html": """
<p><strong>Vorlagen › Grenzwerte</strong> legt fest, ab wann EPM warnt und was als unplausibel abgewiesen wird:
Gewichtsverlust (Prozent und Zeitraum), Plan gilt als alt nach, <strong>Kontakt bald fällig</strong> (Standard 4 Monate)
und <strong>Kontakt überfällig</strong> (Standard 6 Monate; muss später liegen als „bald fällig“), Grenzen für Gewicht,
Größe und die Werte der Infusionspläne. Die Fristen des Datenschutzes ändert nur, wer über Datenschutz-Anfragen
entscheidet.</p>""",
    },
    {
        "id": "dokumentvorlagen", "gruppe": "administration", "titel": "Dokumentvorlagen (Briefe und Formulare)",
        "rechte": ["vorlagen_pflegen"], "seiten": ["/admin/vorlagen/dokumente"],
        "html": """
<p>Dokumentvorlagen bestimmen Text und Aussehen der Briefe, E-Mails und PDFs (Schreiben an Patienten, Infusionsplan,
Patientendatenblatt, Berichte, Unterlagen für die Sprechstunde, Vordrucke zum Datenschutz). Die Liste zeigt je Vorlage,
wofür sie ist, wo sie in der Praxis benutzt wird und ihren Stand: <em>in Gebrauch</em>, <em>Änderungen noch nicht
freigegeben</em> oder <em>Mustertext, noch nicht geprüft</em>.</p>
<p>Geändert wird in drei Schritten: <strong>1 · Bearbeiten</strong> (Abschnitt im Aufbau oder auf der Seite anklicken,
rechts ändern, „Speichern“), <strong>2 · Vorschau prüfen</strong> (die echte PDF mit einem Testpatienten, neben den
Eigenschaften, folgt jeder Änderung) und <strong>3 · Freigeben</strong>. Erst dann gilt die neue <strong>Fassung</strong>
für alle neuen PDFs und E-Mails; gespeicherte, noch nicht freigegebene Änderungen (der <em>Entwurf</em>) sieht in der
Praxis niemand. Wer die Seite mit ungespeicherten Änderungen verlässt, wird gefragt.</p>
<p><strong>Angaben aus der Akte</strong> (Anrede, Name, Termin …) fügt man per Klick aus der Liste rechts ein; im Text
stehen sie als lesbare Kästchen wie <em>Briefanrede</em> und werden beim Erstellen durch die Daten des Patienten ersetzt.</p>
<p><strong>Frühere Fassungen</strong> bleiben erhalten: „ansehen“ zeigt sie mit Testpatient, „wiederherstellen“
übernimmt sie als Grundlage – in Gebrauch ist sie erst nach dem Freigeben. Jede PDF vermerkt ihre Fassung.
<strong>+ Neue Vorlage</strong> legt ein eigenes Schreiben an; <strong>Als eigene Vorlage kopieren</strong> nimmt ein
bestehendes Schreiben als Grundlage. Beide erscheinen in der Akte unter „Schreiben und E-Mail“ › „Eigene Vorlagen“.</p>
<p>Die Vordrucke zum Datenschutz (Datenschutzinformation, Einwilligung, Schweigepflichtentbindung) kommen als ungeprüfte
Entwürfe mit Lücken in [eckigen Klammern]; ihre PDFs tragen das Wasserzeichen „ENTWURF“, bis eine eigene Fassung
freigegeben ist. Mit <strong>Entwurfsmodus ausschalten</strong> lässt sich das Wasserzeichen (und der Hinweisblock für
die Bearbeiter) auch ohne Bearbeiten abschalten – die Lücken bleiben dann stehen; jederzeit wieder einschaltbar.</p>""",
    },
    {
        "id": "benutzer", "gruppe": "administration", "titel": "Benutzer und Rechte", "rechte": ["benutzer_verwalten"],
        "seiten": ["/admin/benutzer"],
        "html": """
<p><strong>Benutzer anlegen</strong> erzeugt ein Einmal-Passwort; das <strong>Zugangsblatt</strong> lässt sich nur
drucken, solange das Passwort angezeigt wird. Benutzer werden nie gelöscht, nur gesperrt. Weitere Aktionen: entsperren,
neues Einmal-Passwort (Passwort vergessen), zweiten Faktor zurücksetzen (Telefon verloren).</p>
<p><strong>Ohne Login</strong>: Konten, die nur als Name für Einträge dienen (z. B. frühere Mitarbeiter oder aus dem
Altsystem übernommen), können sich nicht anmelden und haben die Rolle <strong>Keine Berechtigung</strong> – also keine
Rechte. Ein Konto lässt sich auf „ohne Login“ setzen (Passwort und zweiter Faktor werden gelöscht, Einträge bleiben
zugeordnet) und mit <strong>Login geben</strong> wieder einbinden, z. B. als Mitarbeiter; dabei entsteht ein neues
Einmal-Passwort.</p>
<p><strong>Testbenutzer</strong> (Schalter im Konto, für Betrachter, Mitarbeiter, Mitarbeiter (erweitert) und Mediziner) sehen und bearbeiten
ausschließlich Testpatienten. Nicht mehr gebrauchte Testbenutzer lassen sich <strong>ausblenden</strong> (einzeln oder
„Alle Testbenutzer ausblenden“): gesperrt und in keiner Liste mehr, aber nicht gelöscht; „Ausgeblendete zeigen“ und
„Einblenden“ holen sie zurück. Mit dem Recht <strong>Testdaten sehen</strong> legt man je Gruppe fest, wer
Testpatienten und Testbenutzer überhaupt sieht.</p>
<p>Unter <strong>Anmeldung</strong> legt die Administration fest, ob die Zwei-Faktor-Anmeldung freiwillig, Pflicht für
Admins oder Pflicht für alle ist.</p>
<p>Unter <strong>Rechte</strong> legt man je Gruppe (Betrachter, Mitarbeiter, Mediziner, Admin) fest, was erlaubt ist.
Änderungen gelten sofort; nicht Erlaubtes wird in der Oberfläche ausgeblendet. Admins schreiben Patientendaten nur bei
Testpatienten – ausgenommen Akten abschließen, Dokumente einem anderen Patienten zuordnen und endgültig löschen.</p>""",
    },
    {
        "id": "audit", "gruppe": "administration", "titel": "Audit-Log", "rechte": ["audit_lesen"],
        "seiten": ["/admin/audit-log"],
        "html": """
<p>Das Audit-Log hält Anmeldungen, Fehlversuche, Änderungen an Benutzern und Vorlagen, Exporte, Sicherungen und
Eingriffe in den Datenschutz fest. Es ist unveränderlich. Filter nach Zeitraum, Person und Art; „Zeitraum als PDF“ gibt
die gefilterten Einträge aus.</p>""",
    },
    {
        "id": "system", "gruppe": "administration", "titel": "System: Server, Updates, Neustart",
        "rechte": ["system_verwalten"], "seiten": ["/admin/system"],
        "html": """
<p><strong>Administration › System</strong> zeigt Auslastung (CPU, Arbeitsspeicher, Platte, Laufzeit), offene
Ubuntu-Updates und den Verlauf der Auslastung – wählbar 1 Stunde, 3 Stunden, 24 Stunden, 7 und 14 Tage, 1 und 6 Monate
(längere Zeiträume als Mittelwerte mit gestrichelten Spitzen). Die Seite ist in Reiter gegliedert: <strong>Übersicht</strong> (Kennzahlen, Auslastung als kleiner Verlauf –
<strong>Größer anzeigen</strong> öffnet das Diagramm –, Server, EPM, Texterkennung; die Karten lassen sich in Breite und
Höhe einstellen), <strong>Wartung</strong>, <strong>Software</strong>, <strong>Zertifikat</strong>,
<strong>Protokolle</strong>, <strong>Anmeldungen und Hinweis</strong>, <strong>Verlauf</strong> und
<strong>Testphase</strong>. Von hier aus lassen sich <strong>Updates installieren</strong>,
der <strong>Server neu starten</strong> und EPM neu starten – mit Passwort und Code aus der Authenticator-App
(Zwei-Faktor-Anmeldung nötig), vorher läuft automatisch eine
Sicherung (schlägt sie fehl, wird nichts verändert), angemeldete Benutzer werden gewarnt. Beginn sofort oder in 5 bis 60
Minuten; ein wartender Auftrag lässt sich zurückziehen.</p>
<p><strong>EPM aktualisieren</strong> bringt EPM ohne Terminal auf einen neuen Stand: Der Server holt den Code, baut die
Programmteile neu, sichert und stellt um. Das dauert je nach Server 10 bis 30 Minuten; beim Umstellen ist EPM kurz nicht
erreichbar, deshalb vorher Eingaben speichern. Der Auftrag läuft auf dem Server weiter, auch wenn die Seite in der
Zwischenzeit nicht antwortet – das Ergebnis erscheint danach unter <strong>Aufträge</strong> samt Ausgabe. Geht etwas
schief, bleibt die bisherige Version in Betrieb; über <strong>Ausgabe</strong> ist zu sehen, woran es lag.</p>
<p><strong>Wartung › Dienste</strong>: einzelne Container (backend, web, ocr, db) neu starten, z. B. wenn die Texterkennung
hängt. <strong>Speicher aufräumen</strong>: das Systemprotokoll (Journal) auf eine Größe oder ein Alter verkleinern
(einfache Rückfrage) und gespeicherte alte Versionen – Image-Dateien, Update-Pakete, Docker-Images – ankreuzen und
löschen (Passwort und Code); die laufende und die vorherige Version bleiben immer. <strong>Uhrzeit</strong>: Zeitzone,
Zeitsynchronisation (NTP) mit eigenem Zeitserver – ohne Internet z. B. die OPNsense – oder bei ausgeschalteter
Synchronisation die Uhrzeit von Hand; angezeigt wird auch, wie weit die Uhr des Servers von diesem Gerät abweicht. Codes
der Authenticator-App, Passkeys und Zertifikate brauchen eine richtige Uhrzeit. <strong>Software</strong>: die vorhandenen Versionen mit <strong>Zurückschalten</strong> (vorher automatische
Sicherung; Datenbank-Migrationen werden nicht zurückgedreht), <strong>Update-Paket einspielen</strong> (Datei der Test-VM
hochladen statt per scp – der Server prüft Inhalt und Prüfsummen und zeigt die SHA-256 zum Vergleichen),
<strong>Update-Paket erstellen</strong> (Test-VM; liegt danach 2 Stunden zum Herunterladen bereit) und
<strong>OCR-Modelle einspielen</strong>. <strong>Zertifikat</strong>: Inhaber, Aussteller und Ablauf,
<strong>Zertifikat erneuern</strong> (eigene CA), <strong>Zertifikat importieren</strong> (CRT, KEY und CA als PEM – der
Schlüssel geht nur an den Server) und das Stammzertifikat für die Geräte. <strong>Protokolle</strong>: die letzten 100,
500 oder 2000 Zeilen der Container, des Systemagenten, der nächtlichen Sicherung, der Übertragung oder des letzten
Updates – filtern und herunterladen; ein Abruf liegt eine Stunde bereit und steht im Audit-Log.</p>
<p>Außerdem: <strong>Hinweis an alle Benutzer</strong> setzen und angemeldete Benutzer abmelden. Bei den Konten führen die
Namen (gesperrt, ohne zweiten Faktor, offenes Einmal-Passwort) direkt zur Person in der Benutzerverwaltung.</p>
<p><strong>Testphase und Go-live</strong>: <strong>Musterdaten automatisch anlegen</strong> abschalten, damit beim Start
keine Testpatienten und Testkonten mehr entstehen. <strong>Menüpunkt „Import“ ausblenden</strong>, wenn die Altdaten
übernommen sind – die Seite bleibt über den Reiter „Testphase“ erreichbar, der Menüpunkt lässt sich wieder einblenden.
<strong>Datenbank leeren</strong> (nur Rolle Admin) entfernt alles aus der Testphase: alle Akten (auch echte),
Dokumente, alle Scans samt Dateien (auch nicht zugeordnete), was die Texterkennung gelernt hat, Versorger, Ärzte, die nicht ausgewählten Benutzer und das Audit-Log; Präparate, Auswahllisten, Vorlagen und
Einstellungen bleiben. Welche Konten bleiben, wird im Dialog angehakt (das eigene bleibt immer). Bestätigt wird mit dem
angezeigten Code zum Abtippen, Passwort, Code aus der Authenticator-App und der Rückfrage „Wollen Sie wirklich die
Datenbank löschen?“. Vorher sichert der Server automatisch – zurück geht es nur über diese Sicherung.</p>""",
    },
    {
        "id": "backup", "gruppe": "administration", "titel": "Datensicherung", "rechte": ["backup_verwalten"],
        "seiten": ["/admin/backup"],
        "html": """
<p>EPM sichert jede Nacht Datenbank und Dokumente, verschlüsselt mit einem Passwort, das in der Oberfläche festgelegt
wird (das <strong>Passwortblatt</strong> gehört in den Tresor). Die Sicherungen werden im Zeitfenster in einen
WebDAV-Ordner (z. B. Nextcloud) übertragen.</p>
<p><strong>Jetzt sichern</strong> startet eine Sicherung sofort. <strong>Wiederherstellen</strong> braucht das eigene
Passwort und den Code aus der Authenticator-App (Zwei-Faktor-Anmeldung nötig); danach müssen sich alle neu anmelden.</p>
<p>Die Seite hat die Reiter <strong>Sicherungen</strong>, <strong>Verschlüsselung</strong>, <strong>Übertragung</strong> und
<strong>Tätigkeiten</strong>. <strong>Sicherungen löschen</strong>: in der Liste links ankreuzen (oder alle auf einmal),
dann „N Sicherungen löschen“ – der Dialog nennt Anzahl und Größe und warnt, wenn eine Sicherung nirgends sonst liegt;
bestätigt wird mit Passwort und Code. Die jüngste Sicherung lässt sich nie löschen. Das Löschen ist endgültig; Kopien
im Übertragungsziel bleiben, bis die dortige Aufbewahrung sie entfernt. Die Größe je Sicherung steht klein unter
„Speicher“, groß per Klick.</p>
<p><strong>Zeitplan</strong> (unter „Letzte Sicherung“, „Ändern“): Uhrzeit der automatischen Sicherung, täglich oder
werktags; Standard täglich um 02:00. Passt die Uhrzeit nicht zum Zeitfenster der Übertragung (die neue Sicherung läge
dann Stunden nur auf dem Server), weist der Dialog darauf hin.</p>
<p><strong>Aufbewahrung</strong>: 7, 14 oder 30 Tage auf dem Server; ältere entfernt die nächste Sicherung. Im
Übertragungsziel gilt eine eigene Aufbewahrung (unter „Ziel ändern“, Standard 30 Tage, auch „nie löschen“): Nach jeder
Übertragung entfernt der Server dort ältere EPM-Sicherungen; die jüngste bleibt immer, andere Dateien im Ordner werden
nie angefasst.</p>
<p><strong>Herunterladen</strong>: Der Server legt die Sicherung für 2 Stunden als eine Datei
(<code>epm-sicherung_….tar</code>) bereit; verschlüsselte bleiben verschlüsselt. <strong>Sicherung hochladen</strong>
bringt genau so eine Datei zurück – auch von einem anderen EPM-Server, z. B. nach dem Altdaten-Import auf einer
Migrationsmaschine. Der Server prüft sie (Inhalt, Prüfsummen, Passwort) und nimmt sie als „Hochgeladen“ in die Liste
auf; stammt sie von einem anderen Server, wird ihr Passwort einmal abgefragt. Zurückgespielt wird erst mit
<strong>Wiederherstellen</strong>.</p>""",
    },
    {
        "id": "testdaten", "gruppe": "administration", "titel": "Testumgebung und Testpatienten",
        "rechte": ["testdaten_zuruecksetzen"], "seiten": [],
        "html": """
<p>Testpatienten (Nummern ab 9001) dienen zum Üben; sie zählen in keiner Statistik. Testzugänge sehen nur sie.
<strong>Testdaten zurücksetzen</strong> löscht alle Testpatienten und legt die Musterdaten neu an – echte Akten bleiben
unverändert.</p>""",
    },
    {
        "id": "import", "gruppe": "administration", "titel": "Altdaten übernehmen", "rechte": ["altdaten_importieren"],
        "seiten": ["/admin/import"],
        "html": """
<p>Der Import übernimmt Akten aus dem Altsystem: Dump laden, Zuordnungen pflegen, <strong>Probelauf</strong> prüfen,
importieren. Ein Import lässt sich zurücknehmen, solange die Übernahme nicht abgeschlossen ist. Übernommene Dokumente
stehen danach unter „Altdokumente prüfen“.</p>""",
    },
]
