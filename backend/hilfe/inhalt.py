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
    ("listen", "Versorger und Ärzte"),
    ("administration", "Administration"),
]

ABSCHNITTE = [
    # ------------------------------------------------------------------ Erste Schritte
    {
        "id": "anmelden", "gruppe": "erste_schritte", "titel": "Anmelden mit Kennwort und Authenticator", "rechte": [],
        "seiten": [],
        "html": """
<p>Angemeldet wird mit Benutzername und <strong>Kennwort</strong>. Die <strong>Zwei-Faktor-Anmeldung</strong> (Code aus
einer Authenticator-App auf dem Telefon) ist freiwillig – die Administration kann sie für Admins oder für alle zur
Pflicht machen. Wer sie eingerichtet hat, wird bei jeder Anmeldung nach dem Code gefragt.</p>
<ol>
<li>Benutzername und Kennwort eingeben, <strong>Anmelden</strong> wählen.</li>
<li>Mit Zwei-Faktor-Anmeldung: den sechsstelligen Code aus der Authenticator-App eingeben. Er wechselt alle 30 Sekunden.</li>
<li>Bei der ersten Anmeldung mit dem Einmal-Kennwort vom Zugangsblatt wird zuerst ein eigenes Kennwort festgelegt. Ist
die Zwei-Faktor-Anmeldung Pflicht, wird danach die Authenticator-App eingerichtet (QR-Code scannen); sonst geht das
jederzeit unter <strong>Mein Konto › Anmeldung und Sicherheit › Einrichten</strong>. Danach zeigt EPM einmalig die
Notfall-Codes.</li>
</ol>
<p>Solange sie freiwillig ist, lässt sich die Zwei-Faktor-Anmeldung unter Mein Konto mit Kennwort und Code auch wieder
ausschalten. Bestätigungen (endgültig löschen, Wiederherstellen, Updates, Sicherung, Import) verlangen immer Kennwort
<strong>und</strong> Code – wer sie ausführen soll (z. B. Mediziner, Administration), muss die Zwei-Faktor-Anmeldung
eingerichtet haben.</p>
<p>Nach mehreren falschen Kennwörtern wird das Konto gesperrt; entsperren kann die Administration. Nach längerer
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
        "id": "konto", "gruppe": "erste_schritte", "titel": "Mein Konto: Darstellung, Kennwort, Anmeldungen", "rechte": [],
        "seiten": ["/konto"],
        "html": """
<p>Unter <strong>Mein Konto</strong> stellt jede Person für sich ein, wie EPM aussieht: Farbschema (auch hoher Kontrast
und dunkel), Akzentfarbe, Hintergrund, Dichte, Schriftgröße und Schriftstärke. Die Einstellungen gelten an jedem PC,
an dem man sich anmeldet.</p>
<ul>
<li><strong>Kennwort ändern</strong>: altes Kennwort, dann zweimal das neue.</li>
<li><strong>Zwei-Faktor-Anmeldung</strong>: einrichten, neues Gerät, Notfall-Codes; solange freiwillig auch ausschalten.</li>
<li><strong>Anmeldungen</strong>: zeigt, wo man gerade angemeldet ist; fremde Anmeldungen lassen sich einzeln beenden.</li>
<li><strong>Startseite anpassen</strong> führt zur Startseite im Bearbeitungsmodus.</li>
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
<p>Die Liste zeigt Patienten <strong>in Betreuung</strong> oder <strong>abgeschlossene</strong> Akten. Die Suche oben in
der Kopfzeile (Strg K) findet Patienten nach Name, Nummer oder Geburtsdatum von jeder Seite aus.</p>
<ul>
<li>Filter nach Versorger, Ansprechpartner und Katheter; Schnellfilter „Nur mit Hinweisen“, „Gewichtsverlust“,
„Termin diese Woche“.</li>
<li>Klick auf eine Spaltenüberschrift sortiert; Klick auf den Namen öffnet die Akte.</li>
<li>Je breiter das Fenster, desto mehr Spalten: ab 1440 px Versorger, Katheter und Plan, ab 1920 px Gewicht und
Erklärungen. Ab 2560 px steht rechts eine <strong>Vorschau</strong> der gewählten Akte (Zeile anklicken).</li>
</ul>
<p>Testpatienten (Nummern ab 9001) stehen in der Liste, zählen aber in keiner Statistik.</p>""",
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
„Kein Versorger“ bzw. „kein Katheter“ heißt bewusst keiner; leer heißt noch nicht erfasst.</p>""",
    },
    {
        "id": "aktenkopf", "gruppe": "patienten", "titel": "Aktenkopf und Merkliste", "rechte": ["akten_lesen"],
        "seiten": ["/patienten/:id"],
        "html": """
<p>Der Kopf der Akte zeigt die Kerndaten: Gewicht mit Trend, BMI, Katheter, Versorger, Ansprechpartner, aktuellen Plan,
nächsten Termin, Hausarzt, <strong>Auskunft an</strong> (Personen mit Schweigepflichtentbindung) und Nickelallergie.
Fehlt eine Erklärung zum Datenschutz, steht ein Hinweis neben dem Namen.</p>
<p>Der <strong>Stern</strong> neben dem Namen setzt die Akte auf deine Merkliste; sie erscheint dann auf der Startseite
unter „Meine Akten“. Dort stehen auch die zuletzt geöffneten Akten. Merkliste und Verlauf sieht nur die Person selbst.</p>
<p>Jeder Bereich hat seinen eigenen Reiter: Übersicht, Diagnosen, Therapie, Kontakte, Infusionspläne, Labor, BIA,
Berichte, Dokumente, Datenschutz und Verlauf.</p>
<p>Hinweise am Namen (Gewichtsverlust, Plan oder Befund zu alt, Kontakt fällig …) lassen sich mit dem <strong>×</strong>
ausblenden. Dabei wird gewählt, wie lange Ruhe sein soll – 3, 6 oder 12 Monate, danach erscheint der Hinweis von allein
wieder – oder <strong>nicht mehr nötig</strong>. Was gerade ausgeblendet ist, steht in der Übersicht der Akte unter
„Ausgeblendete Hinweise“ und lässt sich dort wieder einschalten.</p>""",
    },
    {
        "id": "spalten", "gruppe": "patienten", "titel": "Karten vergrößern und Spalten verbreitern", "rechte": [], "seiten": [],
        "html": """
<p>Auf breiten Bildschirmen nutzen alle Seiten die volle Breite und teilen sich in Stufen auf (ab 1440, 1920 und
2560 px).</p>
<p>In der Akte (Übersicht, Diagnosen, Therapie, Kontakte) und unter Administration › System stehen die Karten in einem
Raster wie auf der Startseite. Das Menü <strong>⋯</strong> oben rechts an jeder Karte stellt ihre
<strong>Breite</strong> (1 Spalte bis ganze Breite) und <strong>Höhe</strong> (automatisch oder 1–4 Zeilen; der Inhalt
scrollt dann in der Karte) ein; <strong>Standardgröße</strong> setzt zurück. Gespeichert wird je Person.</p>
<p>In der Patientenliste mit Vorschau und im Plan-Editor lässt sich der <strong>Teiler</strong> zwischen den Spalten
ziehen wie bei einem Fenster.</p>
<ul>
<li>Er rastet bei <strong>⅓</strong>, <strong>½</strong> und <strong>⅔</strong> ein.</li>
<li><strong>Doppelklick</strong> auf den Teiler setzt auf den Standard zurück.</li>
<li>Per Tastatur: Teiler mit Tab wählen, ← und → springen zum nächsten Einrastpunkt.</li>
</ul>
<p>Die Aufteilung wird je Seite, Fensterstufe und Person gespeichert.</p>""",
    },
    {
        "id": "stammdaten", "gruppe": "patienten", "titel": "Stammdaten, Diagnose und Therapie ändern",
        "rechte": ["akten_bearbeiten"], "seiten": ["/patienten/:id/therapie", "/patienten/:id/diagnosen"],
        "html": """
<p>Stammdaten (Name, Anschrift, Telefon und Telefon 2, Versicherungsart, Versicherung und Versichertennummer, Versorger,
Katheter, Nickelallergie …) ändert man über <strong>Weitere Aktionen › Stammdaten bearbeiten</strong> im Aktenkopf.
Die Diagnoseliste mit ICD-Code und der Freitext „Diagnose“ stehen im Reiter <strong>Diagnosen</strong>, Therapie,
Empfehlung und Bemerkung im Reiter <strong>Therapie</strong>; jede gespeicherte Fassung bekommt eine Versionsnummer,
frühere Fassungen bleiben lesbar.</p>
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
    # ------------------------------------------------------------------ Kontakte und Termine
    {
        "id": "kontakt_erfassen", "gruppe": "kontakte", "titel": "Kontakt erfassen", "rechte": ["eintraege_erfassen"],
        "seiten": ["/patienten/:id/kontakte"],
        "html": """
<p>Jedes Telefonat, jede Absprache mit dem Versorger und jeder Besuch wird als <strong>Kontakt</strong> in der Akte
festgehalten. Ein gespeicherter Kontakt wird nicht mehr geändert.</p>
<ol>
<li>Akte öffnen und <strong>Kontakt</strong> wählen – oder auf der Startseite <strong>Kontakt erfassen</strong>.</li>
<li>Text eintragen und die <strong>Kontaktart</strong> wählen (Liste unter Vorlagen › Auswahllisten). Für einen Rückruf, eine Wiedervorlage oder einen Praxistermin den Haken
<strong>Wiedervorlage</strong> setzen, Art und Datum wählen; sie erscheint auf der Startseite und im Kalender.</li>
<li><strong>Kontakt speichern</strong>. Zeitpunkt und Person trägt EPM selbst ein.</li>
</ol>
<p>Vor einer Auskunft am Telefon im Aktenkopf unter <strong>Auskunft an</strong> nachsehen, wem Auskunft gegeben werden
darf.</p>""",
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
<p>Anlegen über <strong>Termin</strong> in der Akte, auf der Startseite, im Kalender oder beim Kontakt. Offene Termine
lassen sich ändern (Titel anklicken) und als erledigt abhaken.</p>""",
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
<p>Die Knöpfe oben filtern nach Art. Rechts stehen überfällige Termine und Fälligkeiten; ab 1920 px Fensterbreite dazu
die Liste des gewählten Tages.</p>""",
    },
    # ------------------------------------------------------------------ Gewicht
    {
        "id": "gewicht", "gruppe": "gewicht", "titel": "Gewicht eintragen und korrigieren", "rechte": ["eintraege_erfassen"],
        "seiten": [],
        "html": """
<p>In der Übersicht der Akte unter <strong>Gewichtsverlauf</strong> das neue Gewicht, das Messdatum und die Quelle
(telefonisch, Ambulanz, Versorger, Arztbrief) eintragen und speichern – oder auf der Startseite über
<strong>Gewicht</strong> bzw. beim Kontakt mit „Gewicht mit erfassen“.</p>
<p>Unplausible Werte (außerhalb der Grenzwerte) und Daten in der Zukunft werden abgewiesen. Eine falsche Messung wird
unter <strong>Messwerte anzeigen › Korrigieren</strong> berichtigt; die bisherige Fassung bleibt im Verlauf sichtbar.</p>""",
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
<p>Die Ansicht wie PDF erscheint klein als Vorschau; ein Klick darauf (oder „Groß ansehen“) öffnet sie groß.</p>
<p>Der Menüpunkt <strong>Infusionspläne</strong> zeigt die Pläne aller Patienten: zur Freigabe, aktuell und älter als
eingestellt. Beim Überfahren des Status steht die Frist, ab der ein Plan als alt gilt.</p>
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
schlägt EPM Werte je kg Körpergewicht vor. <strong>Leer beginnen</strong> startet ohne Werte.</p>
<p>Volumen im Mischbeutel und Rate rechnet EPM aus dem letzten Gewicht; Werte außerhalb der Grenzwerte werden
angemahnt. <strong>Als Entwurf speichern</strong> macht den Plan für das Team sichtbar, noch nicht für den Versorger.</p>
<p>Ab 1920 px Fensterbreite zeigt eine dritte Spalte die <strong>PDF-Vorschau</strong> des zuletzt gespeicherten
Entwurfs (mit Wasserzeichen „ENTWURF“); nach jedem Speichern wird sie neu erzeugt.</p>""",
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
<p>Im Reiter <strong>Dokumente</strong> liegen Arztbriefe, Befunde, Erklärungen und erzeugte PDFs. Hochladen mit
<strong>Datei auswählen</strong> (PDF oder Bild), dazu Typ, Titel und Dokumentdatum. EPM schlägt das Datum aus den
Metadaten der Datei vor.</p>
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
<p>Gehört es in keine Akte, kann es <strong>endgültig gelöscht</strong> werden (nur Mediziner und Admin): mit Kennwort,
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
werden – mit Kennwort, Code aus der Authenticator-App und Bestätigungscode. Es bleibt nur ein Eintrag im Löschprotokoll
(Nummer, Daten der Frist, Grund, Umfang) ohne Namen und Inhalte. Wird später eine ältere Sicherung zurückgespielt,
löscht EPM die Akte beim Start erneut.</p>""",
    },
    # ------------------------------------------------------------------ Versorger und Ärzte
    {
        "id": "versorger", "gruppe": "listen", "titel": "Versorger und Ansprechpartner", "rechte": [],
        "seiten": ["/versorger"],
        "html": """
<p>Die Liste <strong>Versorger</strong> gilt für alle Akten: Versorger mit Telefon und Anschrift, darunter die
Ansprechpartner. Mit dem Recht „Versorger, Ansprechpartner und Ärzte pflegen“ lassen sich Einträge anlegen, ändern und
deaktivieren (nicht löschen); deaktivierte bleiben in bestehenden Akten sichtbar.</p>""",
    },
    {
        "id": "aerzte", "gruppe": "listen", "titel": "Ärzte", "rechte": [], "seiten": ["/aerzte"],
        "html": """
<p>Die Liste <strong>Ärzte</strong> enthält Hausärzte und andere Ärzte mit Praxis und Kontaktdaten. In der Akte werden
sie unter „Ärzte“ mit ihrer Rolle zugeordnet; der Hausarzt erscheint im Aktenkopf.</p>""",
    },
    # ------------------------------------------------------------------ Administration
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
<li><strong>Konten</strong>: gesperrt, Einmal-Kennwort offen, ohne zweiten Faktor, Notfall-Codes knapp.</li>
<li><strong>Angemeldet</strong>, <strong>Hinweis an alle</strong>, <strong>Zugriffe · 7 Tage</strong> aus dem Audit-Log
und <strong>Testumgebung</strong>.</li>
</ul>""",
    },
    {
        "id": "vorlagen", "gruppe": "administration", "titel": "Vorlagen: Auswahllisten, Präparate, Briefkopf",
        "rechte": ["vorlagen_pflegen"], "seiten": ["/admin/vorlagen"],
        "html": """
<p>Unter <strong>Vorlagen</strong> pflegt man die Auswahllisten (z. B. Katheter, Dokumenttypen, Terminorte), die
Präparate für Infusionspläne, Briefkopf und Logo sowie die Grenzwerte. Einträge werden deaktiviert statt gelöscht;
jede Änderung steht im Audit-Log.</p>""",
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
        "id": "dokumentvorlagen", "gruppe": "administration", "titel": "Dokumentvorlagen", "rechte": ["vorlagen_pflegen"],
        "seiten": ["/admin/vorlagen/dokumente"],
        "html": """
<p>Dokumentvorlagen bestimmen das Aussehen der PDFs (Infusionsplan, Patientendatenblatt, Vordrucke). Änderungen
entstehen als <strong>Entwurf</strong>, lassen sich mit einem Testpatienten in der <strong>Vorschau</strong> prüfen und
gelten erst nach <strong>Veröffentlichen</strong>. Frühere Versionen bleiben erhalten; jede PDF vermerkt, mit welcher
Version sie erzeugt wurde.</p>
<p>Die Vordrucke zum Datenschutz (Datenschutzinformation, Einwilligung, Schweigepflichtentbindung) kommen als ungeprüfte
Entwürfe mit Lücken in [eckigen Klammern]; ihre PDFs tragen das Wasserzeichen „ENTWURF“, bis eine eigene Version
veröffentlicht ist. Mit <strong>Entwurfsmodus ausschalten</strong> lässt sich das Wasserzeichen (und der Hinweisblock für
die Bearbeiter) auch ohne Bearbeiten abschalten – die Lücken bleiben dann stehen; jederzeit wieder einschaltbar.</p>""",
    },
    {
        "id": "benutzer", "gruppe": "administration", "titel": "Benutzer und Rechte", "rechte": ["benutzer_verwalten"],
        "seiten": ["/admin/benutzer"],
        "html": """
<p><strong>Benutzer anlegen</strong> erzeugt ein Einmal-Kennwort; das <strong>Zugangsblatt</strong> lässt sich nur
drucken, solange das Kennwort angezeigt wird. Benutzer werden nie gelöscht, nur gesperrt. Weitere Aktionen: entsperren,
neues Einmal-Kennwort (Kennwort vergessen), zweiten Faktor zurücksetzen (Telefon verloren).</p>
<p><strong>Ohne Login</strong>: Konten, die nur als Name für Einträge dienen (z. B. frühere Mitarbeiter oder aus dem
Altsystem übernommen), können sich nicht anmelden und haben die Rolle <strong>Keine Berechtigung</strong> – also keine
Rechte. Ein Konto lässt sich auf „ohne Login“ setzen (Kennwort und zweiter Faktor werden gelöscht, Einträge bleiben
zugeordnet) und mit <strong>Login geben</strong> wieder einbinden, z. B. als Mitarbeiter; dabei entsteht ein neues
Einmal-Kennwort.</p>
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
(längere Zeiträume als Mittelwerte mit gestrichelten Spitzen). Die Karten lassen sich über <strong>⋯</strong> in Breite und
Höhe einstellen. Von hier aus lassen sich <strong>Updates installieren</strong>,
der <strong>Server neu starten</strong> und EPM neu starten – mit Passwort und Code aus der Authenticator-App
(Zwei-Faktor-Anmeldung nötig), vorher läuft automatisch eine
Sicherung (schlägt sie fehl, wird nichts verändert), angemeldete Benutzer werden gewarnt. Beginn sofort oder in 5 bis 60
Minuten; ein wartender Auftrag lässt sich zurückziehen.</p>
<p><strong>EPM aktualisieren</strong> bringt EPM ohne Terminal auf einen neuen Stand: Der Server holt den Code, baut die
Programmteile neu, sichert und stellt um. Das dauert je nach Server 10 bis 30 Minuten; beim Umstellen ist EPM kurz nicht
erreichbar, deshalb vorher Eingaben speichern. Der Auftrag läuft auf dem Server weiter, auch wenn die Seite in der
Zwischenzeit nicht antwortet – das Ergebnis erscheint danach unter <strong>Aufträge</strong> samt Ausgabe. Geht etwas
schief, bleibt die bisherige Version in Betrieb; über <strong>Ausgabe</strong> ist zu sehen, woran es lag.</p>
<p>Außerdem: <strong>Hinweis an alle Benutzer</strong> setzen und angemeldete Benutzer abmelden. Bei den Konten führen die
Namen (gesperrt, ohne zweiten Faktor, offenes Einmal-Kennwort) direkt zur Person in der Benutzerverwaltung.</p>
<p><strong>Testphase und Go-live</strong>: <strong>Musterdaten automatisch anlegen</strong> abschalten, damit beim Start
keine Testpatienten und Testkonten mehr entstehen. <strong>Menüpunkt „Import“ ausblenden</strong>, wenn die Altdaten
übernommen sind – die Seite bleibt über die Karte erreichbar, der Menüpunkt lässt sich wieder einblenden.
<strong>Datenbank leeren</strong> (nur Rolle Admin) entfernt alles aus der Testphase: alle Akten (auch echte),
Dokumente, Versorger, Ärzte, die nicht ausgewählten Benutzer und das Audit-Log; Präparate, Auswahllisten, Vorlagen und
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
