"""
Mitgelieferte Hilfetexte (S15). Sie kommen mit jeder EPM-Version und passen immer zu ihr; eigene Ergänzungen der
Stiftung stehen in der Datenbank (``Hilfeergaenzung``) und werden unter dem jeweiligen Abschnitt angezeigt.

Jeder Abschnitt nennt die Rechte, von denen mindestens eines nötig ist (leer = für alle Angemeldeten). Die Hilfe zeigt
nur Abschnitte zu dem, was die Person tatsächlich darf (Rechte je Gruppe, F66; nicht Erlaubtes ist ausgeblendet, F71).
``seiten`` ordnet Adressen der Oberfläche einem Abschnitt zu: das „?“ in der Kopfzeile springt dorthin
(``:id`` steht für eine Nummer, die längste passende Adresse gewinnt).

Bilder (Wunsch 11.10.2026: „Hilfe mit Screenshots und kurzen animierten GIFs“): Bildschirmfotos und kurze GIFs liegen im
Frontend unter ``frontend/public/hilfe-bilder/`` und werden mit ``node werkzeuge/hilfe-bilder.mjs`` aus der laufenden
Anwendung neu erzeugt (nur Testpatienten). ``_bild`` bzw. ``_film`` setzen das HTML; Breite und Höhe sind die Maße der
Datei (Telefonbilder in halber Größe, sie sind doppelt aufgelöst) – ``patienten.test_startseite.Hilfe`` prüft, dass
jede Datei da ist und die Maße passen.
"""
from html import escape

BILDER = "/hilfe-bilder/"


def _figur(datei: str, bild: str, unterschrift: str, telefon: bool) -> str:
    """PC-Bilder führen per Klick zur Datei in voller Größe (am Telefon sind sie sonst zu klein zum Lesen)"""
    if telefon:
        return f'\n<figure class="hilfe-bild telefon">{bild}<figcaption>{unterschrift}</figcaption></figure>'
    return (f'\n<figure class="hilfe-bild"><a href="{BILDER}{datei}" target="_blank" rel="noopener" '
            f'title="Bild groß ansehen">{bild}</a><figcaption>{unterschrift}</figcaption></figure>')


def _bild(datei: str, alt: str, unterschrift: str, breite: int, hoehe: int, telefon: bool = False) -> str:
    """Bildschirmfoto mit Bildunterschrift"""
    bild = f'<img src="{BILDER}{datei}" alt="{escape(alt)}" loading="lazy" width="{breite}" height="{hoehe}">'
    return _figur(datei, bild, unterschrift, telefon)


def _film(name: str, alt: str, unterschrift: str, breite: int, hoehe: int, telefon: bool = False) -> str:
    """Kurzes GIF (läuft in Schleife); wer „Bewegung reduzieren“ eingestellt hat, sieht stattdessen das Standbild"""
    bild = (f'<picture><source media="(prefers-reduced-motion: reduce)" srcset="{BILDER}{name}-standbild.png">'
            f'<img src="{BILDER}{name}.gif" alt="{escape(alt)}" loading="lazy" width="{breite}" height="{hoehe}"></picture>')
    return _figur(f"{name}.gif", bild, unterschrift, telefon)


GRUPPEN = [
    ("erste_schritte", "Erste Schritte"),
    ("startseite", "Startseite"),
    ("patienten", "Patienten und Akte"),
    ("kontakte", "Kontakte und Termine"),
    ("gewicht", "Gewicht"),
    ("plaene", "Infusionspläne"),
    ("statistik", "Statistik"),
    ("dokumente", "Dokumente"),
    ("datenschutz", "Datenschutz"),
    ("scans", "Scans und Texterkennung"),
    ("ki", "KI (Experimentell)"),
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
Treffer anklicken (Bild unten). Schneller: <strong>Strg K</strong>. Am Telefon die Lupe oben.</li>
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
bleibt länger stehen und sagt, was fehlt; mit dem × lässt sie sich schließen.</p>""" + _film(
            "patient-suchen", "Ablauf: Ins Suchfeld oben „Beisp“ tippen, der Treffer „Beispiel, Paula“ erscheint darunter, "
            "ein Klick darauf öffnet ihre Akte.", "Patient suchen: Name tippen, Treffer anklicken – die Akte öffnet sich.",
            960, 243),
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
<p>Angemeldet wird mit Benutzername und <strong>Passwort</strong>. Die <strong>Zwei-Faktor-Anmeldung</strong> ist
freiwillig. Dabei kommt ein Code aus einer Authenticator-App auf dem Telefon dazu. Die Administration kann sie für Admins
oder für alle zur Pflicht machen. Wer sie eingerichtet hat, gibt bei jeder Anmeldung den Code ein.</p>
<ol>
<li>Benutzername und Passwort eingeben, <strong>Weiter</strong> wählen. Groß- und Kleinschreibung zählt. Ist die
Feststelltaste an, weist EPM darauf hin.</li>
<li>Mit Zwei-Faktor-Anmeldung: den sechsstelligen Code aus der Authenticator-App eingeben. Er wechselt alle 30 Sekunden.</li>
<li>Erste Anmeldung: Mit dem Einmal-Passwort vom Zugangsblatt anmelden und ein eigenes Passwort festlegen. Ist die
Zwei-Faktor-Anmeldung Pflicht, folgt die Authenticator-App (QR-Code scannen). Sonst geht das jederzeit unter
<strong>Mein Konto › Anmeldung und Sicherheit › Einrichten</strong>. Danach zeigt EPM einmalig die Notfall-Codes.</li>
</ol>
<p>Solange sie freiwillig ist, lässt sich die Zwei-Faktor-Anmeldung unter Mein Konto wieder ausschalten. Dafür braucht
es Passwort und Code.</p>
<p>Manche Bestätigungen verlangen immer Passwort <strong>und</strong> Code: endgültig löschen, Wiederherstellen,
Updates, Sicherung und Import. Wer sie ausführen soll (z. B. Mediziner, Administration), muss die
Zwei-Faktor-Anmeldung eingerichtet haben.</p>
<p>Nach mehreren falschen Passwörtern wird das Konto gesperrt. Entsperren kann die Administration. Nach längerer
Pause meldet EPM von selbst ab.</p>""",
    },
    {
        "id": "notfallcodes", "gruppe": "erste_schritte", "titel": "Notfall-Codes", "rechte": [], "seiten": [],
        "html": """
<p>Notfall-Codes ersetzen den Code aus der Authenticator-App. Sie helfen, wenn das Telefon nicht zur Hand ist. Jeder
Code gilt <strong>genau einmal</strong>.</p>
<ul>
<li><strong>Ausdrucken</strong> und sicher aufbewahren – nicht auf dem Telefon speichern.</li>
<li>Sind nur noch wenige Codes übrig, zeigt die Startseite einen Hinweis.</li>
<li><strong>Neue Codes</strong> gibt es unter <strong>Mein Konto › Anmeldung und Sicherheit</strong>. Die alten werden
dabei ungültig.</li>
</ul>
<p>Telefon verloren und keine Codes mehr? Dann setzt die Administration den zweiten Faktor zurück. Sie gibt ein neues
Zugangsblatt aus.</p>""",
    },
    {
        "id": "passkey", "gruppe": "erste_schritte", "titel": "Passkey statt Code (PC und Telefon)", "rechte": [],
        "seiten": [],
        "html": """
<p>Ein <strong>Passkey</strong> ersetzt den Code aus der Authenticator-App. Nach dem Passwort bestätigt man die
Anmeldung mit Fingerabdruck, Gesicht oder der PIN des Geräts. Das geht mit Windows Hello, iPhone, Android oder einem
Passwortmanager.</p>
<p>Der Passkey gilt auch für alle Bestätigungen mit zweitem Faktor (endgültig löschen, Wiederherstellen, Updates,
Import …). Der Code aus der App und die Notfall-Codes bleiben daneben gültig.</p>
<p><strong>Einrichten:</strong></p>
<ol>
<li>Mein Konto › Anmeldung und Sicherheit › <strong>Passkey hinzufügen</strong> wählen.</li>
<li>Einen Namen vergeben (z. B. „iPhone“) und bestätigen.</li>
</ol>
<p>Am besten legt man auf PC <em>und</em> Telefon je einen an. Wer noch keinen zweiten Faktor hatte, bekommt dabei
Notfall-Codes.</p>
<p><strong>Voraussetzung:</strong></p>
<ul>
<li>EPM über den Namen aufrufen (z. B. <code>https://epm.stiftung.lan/</code>), nicht über die IP-Adresse.</li>
<li>Das Stammzertifikat der Stiftung einmal auf dem Gerät installieren:
<a href="/epm-ca.crt">Stammzertifikat herunterladen</a>. Für iPhone und iPad gibt es ein Profil:
<a href="/epm-ca.mobileconfig">Profil laden</a>.</li>
</ul>
<p>Beides gibt es auch unter <em>Mein Konto › Gerät einrichten</em>, mit Anleitung für das jeweilige Gerät. Auf der
Anmeldeseite steht es unter „Dieses Gerät einrichten“.</p>
<ul>
<li><strong>Windows:</strong> Datei öffnen › Zertifikat installieren › Lokaler Computer › „Vertrauenswürdige
Stammzertifizierungsstellen“.</li>
<li><strong>iPhone/iPad:</strong> Datei laden › Einstellungen › Allgemein › VPN und Geräteverwaltung › Profil
installieren; danach Einstellungen › Allgemein › Info › Zertifikatsvertrauenseinstellungen › EPM-CA einschalten.</li>
<li><strong>Android:</strong> Einstellungen › Sicherheit › Weitere Einstellungen › Verschlüsselung und Anmeldedaten ›
Zertifikat installieren › CA-Zertifikat.</li>
</ul>
<p><strong>Gerät verloren?</strong> Den Passkey von einem anderen Gerät aus unter Mein Konto entfernen. Oder die
Administration setzt den zweiten Faktor zurück.</p>""",
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
<p><strong>Offene Punkte führen zur Stelle:</strong> Hinweise wie „Nickelallergie nicht erfasst“ oder der nächste Termin
in der Patientenliste lassen sich antippen – EPM öffnet gleich das passende Fenster.</p>""" + _bild(
            "telefon-akte.png", "Akte am Telefon: oben Name und Hinweise, darunter die Knöpfe Kontakt, Gewicht, Termin, "
            "Dokument und Neuer Plan, darunter Gewicht, Infusionsplan, nächster Termin und letzter Kontakt.",
            "Die Akte am Telefon: Hinweise, Knöpfe und die wichtigsten Zahlen oben.", 390, 484, telefon=True) + _film(
            "telefon-offener-punkt", "Ablauf am Telefon: In der Patientenliste den Hinweis „Nickelallergie nicht erfasst“ "
            "antippen, EPM öffnet die Stammdaten mit dem Feld Nickelallergie.",
            "Hinweis antippen – EPM öffnet die Stelle, an der die Angabe fehlt.", 390, 844, telefon=True) + """
<p>Anmelden am Telefon am einfachsten mit einem Passkey (siehe „Passkey statt Code“).</p>""",
    },
    {
        "id": "design", "gruppe": "erste_schritte", "titel": "Design: Farben, Dichte, Aufbau der Akte", "rechte": [],
        "seiten": ["/design"],
        "html": """
<p>Unter <strong>Design</strong> stellt jede Person für sich ein, wie EPM aussieht. Design steht im Menü unten links bei
deinem Namen. Einstellbar sind:</p>
<ul>
<li>Farbschema (auch hoher Kontrast und dunkel), Akzentfarbe und Hintergrund,</li>
<li>Dichte, Schriftgröße und Schriftstärke,</li>
<li>Aufbau der Patientenakte: Kopfzeile, Seitenleiste oder Karteikarte.</li>
</ul>
<p>Die Einstellungen gelten an jedem PC, an dem man sich anmeldet. <strong>Auf Standard zurücksetzen</strong> stellt
alles zurück. <strong>Startseite anpassen</strong> führt zur Startseite im Bearbeitungsmodus.</p>""",
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
springt zum passenden Abschnitt. Die Suche findet Wörter in Titeln, Texten und Ergänzungen.</p>""" + _bild(
            "hilfe-knopf.png", "Kopfzeile von EPM: rechts neben dem Suchfeld das Fragezeichen, rot umrandet.",
            "Das <strong>?</strong> oben rechts öffnet die Hilfe zur Seite, auf der man gerade ist.", 602, 130) + """
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
Anzahl. Ein Klick auf eine Zeile führt direkt hin.</p>""" + _bild(
            "startseite-heute-zu-tun.png", "Startseite: oben das Datum und die Knöpfe Kontakt erfassen (rot umrandet), "
            "Gewicht und Termin; darunter die Liste Heute zu tun mit fälligen Rückrufen, fehlender Terminbestätigung, "
            "Patienten ohne Kontakt und einem Infusionsplan zur Prüfung.",
            "Startseite mit „Heute zu tun“. Oben die Knöpfe für Kontakt, Gewicht und Termin.", 1283, 637) + """
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
</ol>""" + _bild(
            "kontakt-erfassen-fenster.png", "Fenster Kontakt erfassen: oben Patient und der Kasten Aus der Akte, darunter "
            "Datum, Uhrzeit, Kontaktart und das Feld für die Notiz, unten Gewicht mit erfassen, Wiedervorlage anlegen und "
            "Speichern.", "Das Fenster „Kontakt erfassen“ – von der Startseite und aus der Akte gleich.", 720, 800) + """
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
Patienten zum Öffnen vor.</p>""" + _bild(
            "patient-suchen.png", "Suchfeld oben rechts mit dem Begriff „Beisp“, darunter der Treffer 9003 Beispiel, Paula "
            "mit Geburtsdatum.", "Schon ein Teil des Namens reicht; ein Klick auf den Treffer öffnet die Akte.", 806, 200) + """
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
        "id": "firmen", "gruppe": "patienten", "titel": "Zwei Firmen: DSKM und Regeneration Clinic",
        "rechte": ["akten_lesen"], "seiten": [],
        "html": """
<p>EPM wird von der <strong>DSKM</strong> und der <strong>Regeneration Clinic (RGC)</strong> genutzt. Ein Teil der
Patienten wird von beiden betreut, die übrigen nur von einer der beiden.</p>
<p><strong>Umschalten:</strong> Direkt unter dem Logo oben links steht der Schalter <strong>DSKM | RGC</strong> (in der
schmalen Leiste das Kürzel, am Telefon im Menü; oben im Kopf steht, für welche Firma gerade gearbeitet wird). Danach
zeigt EPM nur die Akten dieser Firma; Logo, Briefkopf und die eigenen Rechte richten sich nach ihr. Der Schalter
erscheint nur, wenn man in beiden Firmen eine Rolle hat.</p>
<p><strong>Farben:</strong> In der Regeneration Clinic erscheinen Seitenleiste, Menüs und Kopfzeile in den Farben der
Klinik (Salbeigrün und Anthrazit), in der DSKM in den Stiftungsfarben – so ist immer auf einen Blick klar, für welche
Firma man gerade arbeitet. Unter <em>Design</em> lassen sich die Farben je Firma wie gewohnt anpassen; „Standard“ sind
jeweils die Farben der Firma. Dichte, Schriftgröße und Aufbau der Akte gelten in beiden Firmen.</p>
<p><strong>Gemeinsame Akten:</strong> Im Aktenkopf zeigt der Chip <strong>DSKM · RGC</strong>, wer die Akte betreut.
An jedem Eintrag (Kontakt, Gewicht, Termin, Plan, Befund, Dokument …) steht klein, in welcher Firma er erfasst wurde.</p>
<p><strong>Betreuende Firmen ändern:</strong> den Firmen-Chip im Aktenkopf antippen oder <em>Weitere Aktionen (⋯) ›
Betreuende Firmen</em>. Eine zweite Firma geht nur mit der unterschriebenen <strong>Einwilligung zum Austausch</strong>:
Datum eintragen, EPM legt die Erklärung unter <em>Datenschutz</em> an (Vordruck dort als PDF). Beim Anlegen eines neuen
Patienten ist die Firma vorgewählt, für die gerade gearbeitet wird.</p>
<p>Der <strong>Import aus dem Altsystem</strong> gilt nur für die DSKM; übernommene Akten gehören der DSKM.</p>""",
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
<strong>Versorgung und Hinweise</strong>. Fehlt eine Erklärung zum Datenschutz, steht ein Hinweis neben dem Namen.</p>""" + _bild(
            "akte-kopf.png", "Aktenkopf von Beispiel, Paula: neben dem Namen die Hinweise 3 Erklärungen fehlen, 2 Hinweise "
            "(rot umrandet) und Nickelallergie; darunter die Knöpfe Kontakt, Gewicht, Termin, Dokument, Neuer Plan und "
            "weitere Aktionen; darunter Gewicht, Infusionsplan, nächster Termin, letzter Kontakt sowie Versorger, Hausarzt "
            "und Auskunft an.", "Der Aktenkopf: Hinweise neben dem Namen, Knöpfe für die tägliche Arbeit, die wichtigsten "
            "Zahlen.", 1275, 247) + """
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
<p>In der Akte unter <strong>Weitere Aktionen › Schreiben und E-Mail …</strong> entstehen Schreiben aus den
Dokumentvorlagen:</p>
<ul>
<li><strong>Patientenaufnahme</strong>: welche Unterlagen wir brauchen.</li>
<li><strong>Terminbestätigung</strong>: Termin wählen. Inhalt: Praxis Dr. Holtmeier, Gesundheitskarte mitbringen,
keine Überweisung nötig.</li>
<li><strong>Reisebescheinigung</strong>: Briefkopf Dr. Holtmeier, deutsch und englisch. Die zweite Seite ist das
ärztliche Attest des ADAC.</li>
</ul>
<p>Danach:</p>
<ul>
<li><strong>PDF ansehen / herunterladen</strong> – zum Drucken, Faxen oder Ablegen.</li>
<li><strong>E-Mail vorbereiten</strong> lädt eine Datei <em>.eml</em>. Ein Doppelklick öffnet sie in Outlook als
fertigen Entwurf. Empfänger, Betreff, Text und die PDF im Anhang sind schon drin – prüfen und senden.</li>
<li>Empfänger, Betreff und Text lassen sich vorher im Dialog ändern. <strong>Weitere Anlagen</strong> (z. B. Leitfaden
Zottentraining) werden mit angehängt.</li>
<li>Auf Wunsch wird die PDF als Dokument „Schreiben“ in der Akte abgelegt.</li>
</ul>
<p>Das <strong>Infoblatt an die Praxis</strong> nennt alle Patienten der nächsten Sprechstunden. Es entsteht im
<strong>Kalender › Praxis informieren</strong> (siehe „Infoblatt an die Praxis“).</p>
<p><strong>Texte ändern und eigene Vorlagen:</strong></p>
<ul>
<li>Die Texte stehen unter Vorlagen › Dokumentvorlagen. Betreff und Text der E-Mail stehen dort im Baustein
<strong>E-Mail</strong>.</li>
<li>Eigene Schreiben (z. B. an Hausärzte) legt <strong>+ Neue Vorlage</strong> unter Vorlagen › Dokumentvorlagen an. Sie
erscheinen danach hier unter „Eigene Vorlagen“.</li>
<li>Anlagen hochladen: Vorlagen › Anlagen für E-Mails.</li>
<li><strong>Fallzusammenfassung</strong>: im Reiter Berichte die Berichtsart „Fallzusammenfassung“ wählen und
<strong>Gliederung einfügen</strong>.</li>
</ul>""",
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
<p><strong>Stammdaten</strong> sind Name, Anschrift, Telefon und Telefon 2, Versicherungsart, Versicherung und
Versichertennummer, Versorger, Katheter, Nickelallergie und mehr. Es gibt zwei Wege, sie zu ändern:</p>
<ul>
<li><strong>Bearbeiten</strong> auf der Karte „Anschrift und Kontakt“ der Übersicht,</li>
<li><strong>Weitere Aktionen › Stammdaten bearbeiten</strong> im Aktenkopf.</li>
</ul>
<p><strong>Diagnosen:</strong> Die Diagnoseliste mit ICD-Code und die Notizen stehen im Reiter
<strong>Diagnosen</strong>. Die Kennzeichen sind gesichert (G), Verdacht (V), Zustand nach (Z) und Ausschluss (A).
<strong>Beenden</strong> fragt nach. Beendete Diagnosen bleiben unter „beendete anzeigen“ erhalten. Man kann sie
wieder als aktuell eintragen.</p>
<p><strong>Therapie</strong> und <strong>Empfehlung</strong> haben je einen eigenen Reiter. Die Empfehlung stammt aus
der letzten Sprechstunde. Sie steht auch auf den Unterlagen für die Sprechstunde.</p>
<ul>
<li>Links stehen die Fassungen, rechts der Text.</li>
<li>Zuerst wird gelesen. <strong>Bearbeiten</strong> öffnet den Editor, <strong>Abbrechen</strong> verwirft die
Eingabe.</li>
<li>Jede gespeicherte Fassung bekommt eine Versionsnummer. Frühere Fassungen bleiben lesbar.</li>
</ul>
<p>Jede Änderung steht mit Person und Zeitpunkt im Verlauf der Akte.</p>""",
    },
    {
        "id": "medikamente", "gruppe": "patienten", "titel": "Medikamentenplan",
        "rechte": ["akten_lesen", "akten_bearbeiten"], "seiten": ["/patienten/:id/medikamente"],
        "html": """
<p>Der Reiter <strong>Medikamente</strong> (gleich nach „Diagnosen“) zeigt den Medikamentenplan wie den
bundeseinheitlichen Medikationsplan: <strong>Dauermedikation</strong> und darunter die
<strong>Bedarfsmedikation</strong>, je mit Wirkstoff, Handelsname, Stärke, Form und Dosierung
morgens – mittags – abends – zur Nacht (z. B. „1 – 0 – 1 – 0“).</p>
<ul>
<li><strong>Medikament</strong> trägt ein neues ein. Pflicht sind der Wirkstoff und eine Dosierung – oder „bei Bedarf“.
Passt das Schema nicht (z. B. „1× wöchentlich montags“), die Dosierung im Feld <strong>Dosierung (frei)</strong>
angeben.</li>
<li>Der <strong>Stift</strong> ändert ein Medikament, <strong>Absetzen</strong> nimmt es aus dem Plan (mit Datum und
auf Wunsch einem Grund). Abgesetzte Medikamente werden nicht gelöscht: Sie stehen unter „Abgesetzt“ und lassen sich
<strong>wieder ansetzen</strong>.</li>
<li><strong>Medikationsplan als PDF</strong> erstellt den Plan zum Mitgeben oder Faxen (Aussehen unter
Vorlagen › Dokumentvorlagen › „Medikationsplan“).</li>
</ul>
<p>Eintragen und Ändern braucht das Recht „Patienten anlegen, Diagnose, Therapie, Stammdaten ändern“; jede Änderung
steht mit Person und Zeitpunkt im Verlauf der Akte.</p>""",
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
        "id": "korrespondenz", "gruppe": "patienten", "titel": "Korrespondenz", "rechte": ["akten_lesen"],
        "seiten": ["/patienten/:id/korrespondenz"],
        "html": """
<p>Der Reiter <strong>Korrespondenz</strong> sammelt alle Schreiben an oder über den Patienten. Jedes Schreiben hat einen
Status: <strong>Entwurf</strong>, <strong>freigegeben</strong> oder <strong>versendet</strong>. Oben filtern Sie nach
Status.</p>
<ol>
<li><strong>Neues Schreiben</strong>: Vorlage wählen, Betreff, Empfänger und Freitext eintragen.</li>
<li><strong>Vorschau</strong> zeigt die PDF. <strong>Entwurf speichern</strong> legt das Schreiben ab.</li>
<li>Wer das Recht „Schreiben freigeben“ hat, <strong>gibt frei</strong>. Dabei entsteht die endgültige PDF.</li>
<li><strong>Als versendet markieren</strong> hält Weg und Datum fest, z. B. Post, E-Mail oder Fax.</li>
</ol>
<p>Entwürfe lassen sich bearbeiten und löschen. Freigegebene Schreiben bleiben unverändert. Für eine Korrektur gibt es
<strong>Als neuen Entwurf kopieren</strong>. Die PDF liegt zusätzlich bei den Dokumenten der Akte.</p>
<p>Vorlagen übernehmen Daten aus der Akte: Diagnosen, Gewicht, Medikation und den aktuellen Infusionsplan. Der Freitext
steht an der Stelle <code>{{Schreiben.Text}}</code>, sonst vor dem Gruß. <strong>Verlauf</strong> zeigt jede Änderung mit
Person und Zeitpunkt.</p>
<p>Im Dialog <strong>Schreiben und E-Mail</strong> legt <strong>In der Akte ablegen (Entwurf)</strong> ein Schreiben hier
an.</p>""",
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
</ol>""" + _film(
            "kontakt-erfassen", "Ablauf in der Akte: Knopf Kontakt im Aktenkopf, das Fenster Kontakt erfassen öffnet sich, "
            "Notiz eintragen, unten Speichern.", "Kontakt erfassen: Kontakt – Notiz schreiben – Speichern.", 960, 737) + """
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
<strong>Akte öffnen</strong>. Auf Startseite und Übersicht hakt das Kästchen einen Termin als erledigt ab.</p>""" + _bild(
            "termin-anlegen-fenster.png", "Fenster Neuer Termin für Beispiel, Paula: Art (Rückruf), Ort, Datum, Uhrzeit "
            "(leer bedeutet ganztägig), Titel und Notiz, unten Abbrechen und Speichern.",
            "Neuer Termin: Art und Datum wählen, ohne Uhrzeit ist er ganztägig.", 520, 532),
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
<strong>Liste</strong>. Dazu kommen Feiertage (bundesweit und NRW) und berechnete Fälligkeiten:</p>
<ul>
<li><strong>Kontakt bald fällig</strong> und <strong>Kontakt überfällig</strong> – je Akte, sobald die Stufe erreicht
ist. Die Grenzwerte stehen unter Vorlagen › Grenzwerte.</li>
<li><strong>Plan prüfen</strong>, wenn der aktuelle Infusionsplan älter wird als eingestellt.</li>
</ul>
""" + _bild(
            "kalender.png", "Kalender im Oktober als Monatsansicht mit farbigen Terminen; rechts die Reiter Tag, Überfällig "
            "und Fällig mit den Terminen des gewählten Tages und der nächsten 7 Tage.",
            "Kalender: links der Monat, rechts der gewählte Tag und die nächsten 7 Tage.", 1100, 598) + """
<p><strong>Termin öffnen:</strong> Ein Klick auf einen offenen Termin öffnet <strong>Termin bearbeiten</strong> – mit
„Erledigt“ und „Akte öffnen“. Fälligkeiten und Erledigtes öffnen eine Ansicht.</p>
<p><strong>Eintrag ausblenden:</strong> Das <strong>×</strong> an einem Eintrag blendet ihn aus – wie die Hinweise in
der Akte: für 3, 6 oder 12 Monate oder als „nicht mehr nötig“, jeweils mit Grund.</p>
<p><strong>Anzeigen ▾</strong> wählt die Arten: Praxistermine, Rückrufe, Wiedervorlagen, Sonstiges, Kontakt fällig und
Plan prüfen. Dort steht auch, ob Erledigte erscheinen, und die Legende der Farben.</p>
<p>Rechts (Tablet: darunter) stehen drei Reiter:</p>
<ul>
<li><strong>Tag</strong> – der gewählte Tag und die nächsten 7 Tage, mit „+ Termin am …“.</li>
<li><strong>Überfällig</strong> – offene Termine, Kontakt überfällig und Plan prüfen.</li>
<li><strong>Fällig</strong> – Kontakt bald fällig.</li>
</ul>
<p>Am Telefon zeigt ein Wochenband die Tage. Darunter stehen Tag, Überfällig und Woche.</p>""",
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
<p>Diese Wege öffnen denselben Dialog:</p>
<ul>
<li><strong>Gewicht</strong> im Aktenkopf,</li>
<li><strong>+ Gewicht</strong> auf der Karte „Gewichtsverlauf“,</li>
<li>„G 54,6“ in der Kürzelzeile oder die Taste <strong>G</strong>,</li>
<li><strong>Gewicht</strong> auf der Startseite.</li>
</ul>
<p>Im Dialog Gewicht, Quelle (telefonisch, Ambulanz, Versorger, Arztbrief) und Messdatum eintragen. Dann
<strong>Speichern</strong>. Beim Kontakt geht es in einem Schritt mit „Gewicht mit erfassen“. Bei der BIA-Messung
ebenso.</p>""" + _bild(
            "gewicht-erfassen-fenster.png", "Fenster Gewicht erfassen: Feld Gewicht mit 57,4 kg (rot umrandet), Quelle "
            "telefonisch, Messdatum; darunter die Veränderung zur letzten Messung, unten Speichern.",
            "Gewicht erfassen: Wert eintragen – EPM zeigt gleich die Veränderung zur letzten Messung.", 640, 507) + """
<p>Unplausible Werte (außerhalb der Grenzwerte) und Daten in der Zukunft weist EPM ab.</p>
<p>Eine falsche Messung berichtigt <strong>Bearbeiten</strong>:</p>
<ul>
<li>die letzte direkt per Klick auf den Wert oder mit „Bearbeiten“ auf der Karte,</li>
<li>ältere unter <strong>Messwerte anzeigen</strong>.</li>
</ul>
<p>Die bisherige Fassung bleibt im Verlauf sichtbar.</p>""",
    },
    {
        "id": "gewicht_verlauf", "gruppe": "gewicht", "titel": "Gewichtsverlauf und Warnung", "rechte": ["akten_lesen"],
        "seiten": [],
        "html": """
<p>Das Diagramm zeigt die Messwerte über 12 Monate, 3 Jahre, 5 Jahre oder alle. Auf Wunsch ist die Kurve geglättet.</p>
<p>Verliert ein Patient zu viel Gewicht, warnt EPM. Die Grenze ist der eingestellte Anteil in der eingestellten Zeit.
Standard: mehr als 5 % in 3 Monaten. Die Warnung erscheint an drei Stellen:</p>
<ul>
<li>in der Akte,</li>
<li>in der Patientenliste,</li>
<li>auf der Startseite unter „Auffällige Gewichte“. Dort steht auch ein kleiner Verlauf der letzten 6 Monate in echten
Zeitabständen.</li>
</ul>""",
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
Wasserzeichen „ENTWURF“.</p>""" + _bild(
            "infusionsplan-ansehen.png", "Reiter Infusionspläne der Akte: links die Liste der Pläne, neueste oben "
            "(aktuell gültig, abgelöst), rechts der aktuelle Plan mit PDF öffnen, Ansicht wie PDF und Vergleich mit "
            "Vorgänger.", "Infusionspläne in der Akte: links die Pläne, rechts der gewählte Plan als PDF.", 1302, 430) + """
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
Praxisvorgabe</strong> setzt diese Mengen jederzeit neu aus dem letzten Gewicht ein – Präparate und Zusätze bleiben. Die
Mengen je kg pflegt die Praxis unter <strong>Vorlagen › Grenzwerte</strong>; neben dem Knopf steht, von wann die Vorgabe
ist.
<strong>Leer beginnen</strong> startet ohne Werte; <strong>Als Vorlage für neuen Plan</strong> (an einem früheren Plan)
übernimmt dessen Werte.</p>
<p>Volumen im Mischbeutel (letztes Gewicht × 35 ml) und Rate rechnet EPM mit. Die Karte <strong>Prüfung vor der
Freigabe</strong> sagt in einfachen Worten, was noch fehlt oder nicht passt: Gewicht vorhanden und nicht älter als
6 Monate (unter Vorlagen › Grenzwerte einstellbar), Präparat zu jeder Menge, Calcium + Magnesium stabil, Infusionstage stimmig, Laufzeit eingetragen,
Protonenpumpenhemmer mit Zeiten. Werte außerhalb der Grenzwerte stehen darüber. <strong>Als Entwurf speichern</strong>
macht den Plan für das Team sichtbar, noch nicht für den Versorger.</p>
<p>Die Karte <strong>Hinweise aus Labor und Gewicht</strong> zeigt, was seit dem letzten Plan in der Akte steht:
Laborwerte außerhalb des Referenzbereichs – nur für Bestandteile, die im Plan vorkommen (z. B. Magnesium, Kalium,
Spurenelemente, Vitamine) – mit den letzten drei Werten, eine deutliche Gewichtsänderung, Bestandteile, die in den letzten
drei Plänen jeweils erhöht oder verringert wurden, und ob Laborwerte fehlen oder zu alt sind (<strong>Blutuntersuchung
anfordern</strong> öffnet „Schreiben und E-Mail“ mit der Anlage „Blutuntersuchung“). Das sind <strong>Hinweise zum
Prüfen</strong>: EPM schlägt keine Mengen vor – die Entscheidung trifft die Ärztin bzw. der Arzt. Bewertet werden Werte
mit Referenzbereich (vom Befund, sonst aus dem Laborkatalog); fehlt er im Katalog, sagt die Karte das. Nachtragen unter
Vorlagen › Labor und Diagnosen › „Ohne Referenzbereich“ – bitte die Bereiche des eigenen Labors übernehmen.</p>
<p><strong>PDF-Vorschau</strong> zeigt die PDF mit genau den Werten, die gerade im Formular stehen – auch ungespeicherte;
gespeichert wird dabei nichts (ein neuer Plan wird dafür einmal als Entwurf gespeichert). Ab 1920 px zeigt zusätzlich eine
dritte Spalte die Vorschau des zuletzt gespeicherten Entwurfs.</p>""",
    },
    {
        "id": "plan_freigeben", "gruppe": "plaene", "titel": "Plan freigeben", "rechte": ["plaene_freigeben"], "seiten": [],
        "html": """
<p><strong>Speichern und freigeben</strong> macht den Plan zum aktuellen Plan. Dabei wird die PDF mit der aktiven
Dokumentvorlage erzeugt und mit Prüfsumme gespeichert; der vorherige Plan bleibt im Verlauf erhalten.</p>
<p>Ein gespeicherter Entwurf steht im Reiter Infusionspläne der Akte (oder unter <strong>Infusionspläne › Zur
Freigabe</strong>): prüfen und oben rechts <strong>Freigeben</strong>.</p>""" + _bild(
            "infusionsplan-freigeben.png", "Entwurf eines Infusionsplans mit den Knöpfen Bearbeiten, Verwerfen und "
            "Freigeben (rot umrandet), darunter die Ansicht wie PDF.",
            "Entwurf prüfen und oben rechts freigeben.", 971, 400),
    },
    {
        "id": "plan_abschliessen", "gruppe": "plaene", "titel": "Plan nach Freigabe abschließen",
        "rechte": ["plaene_abschliessen"], "seiten": [],
        "html": """
<p>Hat der Mediziner einen Entwurf außerhalb von EPM freigegeben (z. B. per E-Mail), wird der Entwurf mit
<strong>Nach Freigabe abschließen</strong> zum aktuellen Plan. Anzugeben sind wer freigegeben hat, das Datum, der Weg
der Freigabe und der Nachweis (z. B. die E-Mail als PDF).</p>""",
    },
    # ------------------------------------------------------------------ Statistik (F193, Festlegung 16.10.2026)
    {
        "id": "statistik", "gruppe": "statistik", "titel": "Statistik für Berichte der Stiftung",
        "rechte": ["statistik_ansehen"], "seiten": ["/statistik"],
        "html": """
<p>Der Menüpunkt <strong>Statistik</strong> zählt die Akten der Firma, für die Sie gerade arbeiten (Umschalter oben links),
für einen Zeitraum: <strong>Kalenderjahr</strong> (Standard: das laufende Jahr im Vergleich zum Vorjahr),
<strong>Quartal</strong> oder <strong>frei von–bis</strong>. Jede Zahl steht neben dem Wert des Vorzeitraums (Vorjahr,
Vorquartal bzw. die gleich lange Spanne direkt davor).</p>
<ul>
<li><strong>Aktive Patienten zum Stichtag</strong> (Ende des Zeitraums, im laufenden Zeitraum heute),
<strong>im Zeitraum betreut</strong>, <strong>Neuaufnahmen</strong> und <strong>abgeschlossene Akten</strong> nach
Anlass (verstorben, Therapie beendet, Betreuung gewechselt).</li>
<li>Die aktiven Patienten nach <strong>Versorger</strong>, <strong>Altersgruppe</strong> am Stichtag (0–17, 18–39,
40–59, 60–79, 80 und älter) und <strong>Katheter</strong> (auch „kein Katheter“ und „nicht erfasst“).</li>
<li><strong>Kontakte</strong> (ohne stornierte) sowie <strong>erstellte und freigegebene Infusionspläne</strong> im
Zeitraum.</li>
</ul>
<p><strong>Datenschutz:</strong> Die Statistik zeigt keine Namen, Nummern oder Geburtsdaten. Testpatienten zählen nie.
Akten mit eingeschränkter Verarbeitung zählen mit, erscheinen aber nie einzeln. <strong>Kleine Zahlen</strong> von 1 bis
4 stehen als <strong>„&lt; 5“</strong> da – auf der Seite, in der PDF und in der CSV. Kommt so eine kleine Zahl bei den
Patienten (aktiv, betreut, Neuaufnahmen, Abschlüsse und ihre Aufteilungen) vor, sind dort alle übrigen Zahlen auf volle
5 gerundet und mit „≈“ markiert, damit sich die kleine Zahl nicht aus der Summe zurückrechnen lässt.</p>
<p><strong>Gut zu wissen:</strong> Als Beginn der Betreuung gilt der Tag, an dem die Akte in EPM angelegt wurde. Aus dem
Altsystem übernommene Akten zählen deshalb nicht als Neuaufnahme, sondern als schon länger betreut. Versorger und
Katheter zeigen den heutigen Stand der Akte.</p>
<p><strong>PDF</strong> (mit Briefkopf) und <strong>CSV</strong> (für Excel: Semikolon, Umlaute richtig) laden die
Auswertung herunter; jeder Export steht im Audit-Log. Sehen dürfen die Statistik standardmäßig die Rollen
<strong>Mitarbeiter (erweitert)</strong>, <strong>Mediziner</strong> und <strong>Admin</strong> (Recht „Statistik
ansehen“, unter Administration › Benutzer › Rechte je Gruppe umstellbar); Betrachter und Mitarbeiter nicht.</p>""",
    },
    # ------------------------------------------------------------------ Dokumente
    {
        "id": "dokumente", "gruppe": "dokumente", "titel": "Dokumente hochladen und ansehen", "rechte": ["akten_lesen"],
        "seiten": ["/patienten/:id/dokumente"],
        "html": """
<p>Im Reiter <strong>Dokumente</strong> liegen Arztbriefe, Befunde, Erklärungen und erzeugte PDFs. Ablegen mit
<strong>Neues Dokument</strong> (PDF, Bild oder Text, höchstens 50 MB) – oder die Datei einfach auf die geöffnete Akte
ziehen; im Aktenkopf geht es auch über <strong>Weitere Aktionen › Dokument hochladen</strong>. Danach rechts Typ, Titel
und Dokumentdatum ergänzen und <strong>Speichern</strong>. EPM schlägt das Datum aus der Datei vor.</p>""" + _bild(
            "dokumente-hochladen.png", "Reiter Dokumente: oben die Fläche zum Hineinziehen mit dem Knopf Neues Dokument "
            "(rot umrandet), darunter die Liste der Dokumente, rechts die Vorschau des gewählten Dokuments.",
            "Dokumente: Datei hineinziehen oder „Neues Dokument“; rechts die Vorschau.", 1302, 428) + """
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
<p>Im Reiter <strong>Datenschutz</strong> der Akte werden drei Erklärungen nachgehalten: Datenschutzinformation,
Einwilligung und Schweigepflichtentbindung.</p>
<ol>
<li><strong>Vordruck als PDF</strong> ausdrucken.</li>
<li>Unterschreiben lassen.</li>
<li>Mit Datum <strong>erfassen</strong>, auf Wunsch mit Scan.</li>
</ol>
<p>Einen Widerruf hält <strong>Widerruf eintragen</strong> fest.</p>
<p>Fehlt eine Erklärung, die vorliegen soll? Dann steht ein Hinweis im Aktenkopf und unter „Nach und nach prüfen“.</p>""",
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
<p>Eine abgeschlossene Akte lässt sich <strong>endgültig löschen</strong>. Das geht nach Ablauf der Aufbewahrungsfrist
oder auf Antrag.</p>
<p>Bestätigt wird mit Passwort, Code aus der Authenticator-App und Bestätigungscode.</p>
<p>Danach bleibt nur ein Eintrag im Löschprotokoll: Nummer, Daten der Frist, Grund und Umfang. Namen und Inhalte stehen
dort nicht.</p>
<p>Wird später eine ältere Sicherung zurückgespielt, löscht EPM die Akte beim Start erneut.</p>""",
    },
    # ------------------------------------------------------------------ Versorger und Ärzte
    # ------------------------------------------------------------------ KI (Experimentell, 14.10.2026, F191)
    {
        "id": "ki", "gruppe": "ki", "titel": "KI (Experimentell): Vorschläge prüfen und übernehmen", "rechte": ["ki_ansehen"],
        "seiten": ["/ki"],
        "html": """
<p>Nachts liest die KI – auf dem eigenen Server, ohne Internet – die Dokumente der Akten: Laborbefunde, Arztberichte,
Infusions- und Medikationspläne, alte Scans. Sie schlägt vor, was darin steht: Dokumenttyp und -datum, Laborwerte,
Infusionen, Medikamente, Diagnosen, eine kurze Zusammenfassung. <strong>Nichts davon steht in der Akte</strong>, bis Sie
es prüfen und bestätigen.</p>
<ol>
<li>Im Menü <strong>KI (Experimentell)</strong> ein Dokument öffnen. Links steht das Original, rechts die Vorschläge.</li>
<li>Jeden Wert mit dem Original vergleichen. Markiert sind: <strong>neu</strong>, <strong>ergänzt Vorhandenes</strong>,
<strong>würde überschreiben</strong>, <strong>schon vorhanden</strong>, <strong>unsicher erkannt</strong> und
<strong>niedrige OCR-Sicherheit</strong> (schlecht lesbare Seite).</li>
<li>Falsches mit dem Stift korrigieren und die Fehlerart wählen – so wird die Erkennung messbar besser. Was nicht
dazugehört: verwerfen (×).</li>
<li>Richtiges freigeben (Haken). „Alle sicheren freigeben“ lässt unsichere Felder offen.</li>
<li>Gibt es in der Akte schon einen Eintrag (z. B. derselbe Laborwert am selben Tag mit anderem Wert), bitte
<strong>entscheiden</strong>: neu anlegen, ergänzen, ersetzen oder verwerfen. Ohne Entscheidung wird nichts
übernommen – und nie etwas automatisch überschrieben.</li>
<li><strong>In die Akte übernehmen</strong>: Zusammenfassung prüfen, bestätigen. Die Übernahme steht mit Ihrem Namen im
Verlauf der Akte und im Audit-Log.</li>
</ol>
<p>Passt das Dokument gar nicht (falsche Akte, unbrauchbarer Scan): <strong>Ablehnen</strong> mit Grund. Das Dokument
in der Akte bleibt unverändert. Ein Dokument sofort verarbeiten lassen (auch tagsüber): in der Akte im Reiter
<strong>KI (Experimentell)</strong> das Dokument wählen und „Anfordern“.</p>""",
    },
    {
        "id": "ki_hinweise", "gruppe": "ki", "titel": "Hinweise Labor und Infusionsplan, Berichtsentwürfe", "rechte": ["ki_ansehen"],
        "seiten": [],
        "html": """
<p>Im Reiter <strong>KI (Experimentell)</strong> der Akte stehen Zusammenhänge zwischen Laborwerten und Infusionsplänen,
z. B. „Kalium niedrig (3,1 mmol/l, 12.03.2026 06:10), anschließend Kaliumsubstitution dokumentiert“ oder „keine
nachfolgende Kaliumsubstitution im erfassten Zeitraum erkannt“. <strong>Gesichert</strong> heißt: beide Angaben stehen
freigegeben in der Akte, Reihenfolge und Dosisänderung sind belegt. <strong>Wahrscheinlich</strong>: mindestens eine
Angabe ist nur ein KI-Vorschlag, die Uhrzeit fehlt oder die Dosis hat sich nicht nachweislich geändert.</p>
<p>Die Hinweise sind <strong>Entscheidungshilfen</strong> – keine medizinische Bewertung, keine Diagnose, keine
Empfehlung.</p>
<p><strong>Berichtsentwurf</strong>: Berichtsart, Zeitraum und Quellen wählen, „Entwurf anfordern“. Der Entwurf entsteht
nur aus freigegebenen Inhalten der Akte, jede Aussage mit Quellennummer. Die Gegenprüfung markiert Zahlen ohne Beleg
und Sätze, die nach Empfehlung oder Bewertung klingen. Bearbeiten, dann „Als Bericht-Entwurf speichern“ – er liegt im
Reiter <strong>Berichte</strong> und wird wie jeder Bericht geprüft und freigegeben.</p>""",
    },
    {
        "id": "ki_einrichtung", "gruppe": "ki", "titel": "KI einrichten und Modell wählen", "rechte": ["ki_verwalten"],
        "seiten": ["/admin/ki"],
        "html": """
<p>Unter <strong>Administration › KI › Einrichtung</strong> wird die KI ohne SSH eingerichtet. Die Aufträge führt der
Systemagent auf dem Server aus; Einrichten, Ausschalten, Laden, Einspielen und Löschen verlangen Passwort und zweiten
Faktor.</p>
<ol>
<li>Die <strong>Checkliste</strong> zeigt, ob der Server reicht (mindestens 12 GB RAM, 4 Kerne, AVX2) und was fehlt.</li>
<li>Ein <strong>Modell wählen</strong>: Die Tabelle nennt Größe, nötigen Arbeitsspeicher, Tempo und die Empfehlung für
diesen Server. Hat der Server Internet, lädt <strong>Auf den Server laden</strong> das Modell direkt. Sonst das
Modell-Paket auf einem PC vorbereiten und unter <strong>Modell-Paket hochladen</strong> hochladen, dann
<strong>Einspielen</strong>.</li>
<li><strong>Einrichten</strong> startet die KI mit dem ersten Modell. Weitere Modelle erscheinen unter
<strong>Modelle</strong>, werden dort evaluiert und mit <strong>Aktivieren</strong> gewechselt (Rückkehr zur vorherigen
Version jederzeit).</li>
<li><strong>Grenzen</strong> (Speicher, Rechenkerne, Worker) und <strong>Benchmark</strong> helfen, Modell und Server
abzustimmen. <strong>Ausschalten</strong> stoppt die KI; Daten und Modelle bleiben.</li>
</ol>""",
    },
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
<li><strong>Diagnosen</strong> aus Arztbriefen, mit ICD-Code (z. B. „K91.2 G“) oder als Freitext unter „Diagnosen:“;
„V.a.“ wird zu V, „Z.n.“ zu Z. Steht im Brief kein Code, schlägt EPM ihn aus dem Gelernten oder der Liste unter
<strong>Vorlagen › Labor und Diagnosen</strong> vor (Marke „Liste“, bei nur ähnlichem Eintrag „Liste?“ – bitte prüfen).
Ohne Treffer bleibt das Feld leer und die Diagnose ist nicht angehakt: Der ICD-Code ist Pflicht, also ergänzen oder
den Haken weglassen. Ergänzte Codes lernt EPM für den nächsten Brief.</li>
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
<p><strong>Administration › Systemverwaltung</strong> zeigt mit einer Ampel, ob alles in Ordnung ist. Geprüft
werden:</p>
<ul>
<li>Systemagent, Dienste (Container) und Speicherplatz,</li>
<li>Ubuntu-Updates, Zertifikat, Texterkennung und Uhrzeit,</li>
<li>letzte Sicherung, Übertragung und fehlgeschlagene Aufträge.</li>
</ul>
<p>Jede Kachel führt direkt zu dem Bereich, in dem man etwas tun kann. Daneben stehen die häufigen Aufgaben: sichern,
Updates, Neustart, Software, Zertifikat, Protokolle, Hinweis an alle, Benutzer und Audit-Log. Die Auslastung steht als
kleiner Verlauf daneben. <strong>Größer anzeigen</strong> öffnet das große Diagramm.</p>
<p>Was früher nur per SSH ging, läuft hier als Auftrag an den Systemagenten auf dem Server. Dabei gilt:</p>
<ul>
<li>Es gibt nur fest eingetragene Tätigkeiten.</li>
<li>Gefährliches braucht Passwort und Code aus der Authenticator-App.</li>
<li>Alles steht im Audit-Log.</li>
</ul>
<p>Per SSH bleibt nur die Ersteinrichtung des Servers.</p>""",
    },
    {
        "id": "admin_start", "gruppe": "administration", "titel": "Startseite der Administration",
        "rechte": ["system_verwalten", "backup_verwalten", "benutzer_verwalten", "audit_lesen", "testdaten_zuruecksetzen"],
        "seiten": [],
        "html": """
<p>Für die Administration zeigt die Startseite eigene Kacheln. Jede Kachel erscheint nur mit dem passenden Recht.</p>
<ul>
<li><strong>Datensicherung</strong>: letzte Sicherung, Übertragung und Speicher. Dazu der Knopf „Jetzt sichern“.</li>
<li><strong>Server</strong> und <strong>Ubuntu-Updates</strong>: Auslastung und offene Updates. Hier lassen sich Updates
installieren und der Server neu starten. Das braucht Passwort und 2FA. Vorher sichert EPM automatisch, und angemeldete
Benutzer werden gewarnt.</li>
<li><strong>Konten</strong>: wer gesperrt ist, ein offenes Einmal-Passwort hat, keinen zweiten Faktor hat oder kaum
noch Notfall-Codes.</li>
<li><strong>Angemeldet</strong>, <strong>Hinweis an alle</strong> und <strong>Testumgebung</strong>.</li>
<li><strong>Zugriffe · 7 Tage</strong>: Zahlen aus dem Audit-Log.</li>
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
die Bearbeiter) auch ohne Bearbeiten abschalten – die Lücken bleiben dann stehen; jederzeit wieder einschaltbar.</p>
<p><strong>Vorlagen je Firma:</strong> Alle Vorlagen sind zunächst <em>gemeinsam</em> – was Sie freigeben, gilt bei der
DSKM und bei der Regeneration Clinic (Logo und Briefkopf kommen ohnehin je Firma). Soll eine Firma einen anderen
Text bekommen, wechseln Sie oben links in diese Firma und wählen im Editor <strong>Eigene Vorlage für … anlegen</strong>:
Die Kopie der gemeinsamen Fassung ist sofort in Gebrauch, und Entwurf, Vorschau, Freigeben und Fassungen gelten ab
dann nur noch für diese Firma; die andere Firma nutzt weiter die gemeinsame Vorlage. Die Liste und der Kopf des
Editors zeigen, ob Sie gerade die gemeinsame oder die eigene Vorlage bearbeiten. <strong>Eigene Vorlage
entfernen</strong> legt sie wieder ab (die Fassungen bleiben als abgelöst erhalten). Eigene Schreiben gehören
entweder allen Firmen oder fest einer Firma.</p>
<p><strong>Querformat:</strong> Bei Vorlagen mit breiten Tabellen (z. B. Medikationsplan) wählen Sie über der Seite
<em>Hochformat</em> oder <em>Querformat</em>; das Seitenformat wird mit der Fassung gespeichert. Der Medikationsplan
kommt im Querformat, damit Hinweise und Grund Platz haben; Falzmarken gibt es nur im Hochformat.</p>
<p><strong>Vorlagen der Regeneration Clinic:</strong> In der Firma RGC stehen zusätzlich ihre Word-Vorlagen als eigene
Schreiben bereit – nur dort, die DSKM sieht sie nicht. Unter „Anforderungen“ stehen Labor, Bildgebung und
Funktionsdiagnostik, dazu die Laborprofile Malabsorption MAL-01 bis MAL-06 mit Übersicht und Regelwerk – nach
Röhrchen geordnet, Pflichtparameter schon angekreuzt. Unter „Aufklärungen, Erklärungen und Abrechnung“ stehen die
Patientenerklärungen, die Schweigepflichtentbindung, die Aufklärungen zu Operation und Anästhesie, die
ÖGK-Formulare, Anlage K und die Anwaltsvollmacht. EPM setzt Name, Geburtsdatum, Anschrift, Versicherung und Versichertennummer ein. Alles andere wird
auf dem Ausdruck von Hand ausgefüllt. Gedruckt werden sie in der Akte über Weitere Aktionen (⋯) › „Schreiben und
E-Mail …“.</p>""",
    },
    {
        "id": "benutzer", "gruppe": "administration", "titel": "Benutzer und Rechte", "rechte": ["benutzer_verwalten"],
        "seiten": ["/admin/benutzer"],
        "html": """
<p><strong>Benutzer anlegen</strong> erzeugt ein Einmal-Passwort. Das <strong>Zugangsblatt</strong> lässt sich nur
drucken, solange das Passwort angezeigt wird. Benutzer werden nie gelöscht, nur gesperrt. Weitere Aktionen:</p>
<ul>
<li><strong>Entsperren</strong>.</li>
<li><strong>Neues Einmal-Passwort</strong> – wenn das Passwort vergessen wurde.</li>
<li><strong>Zweiten Faktor zurücksetzen</strong> – wenn das Telefon verloren ist.</li>
</ul>
<p><strong>Ohne Login:</strong> Manche Konten dienen nur als Name für Einträge. Beispiele: frühere Mitarbeiter oder
Personen aus dem Altsystem. Sie können sich nicht anmelden und haben die Rolle <strong>Keine Berechtigung</strong> –
also keine Rechte. Ein Konto lässt sich auf „ohne Login“ setzen: Passwort und zweiter Faktor werden gelöscht, die
Einträge bleiben zugeordnet. <strong>Login geben</strong> bindet es wieder ein, z. B. als Mitarbeiter. Dabei entsteht
ein neues Einmal-Passwort.</p>
<p><strong>Testbenutzer</strong> sehen und bearbeiten ausschließlich Testpatienten. Der Schalter steht im Konto – für
Betrachter, Mitarbeiter, Mitarbeiter (erweitert) und Mediziner. Nicht mehr gebrauchte Testbenutzer lassen sich
<strong>ausblenden</strong>, einzeln oder mit „Alle Testbenutzer ausblenden“. Sie sind dann gesperrt und in keiner
Liste mehr, aber nicht gelöscht. „Ausgeblendete zeigen“ und „Einblenden“ holen sie zurück. Das Recht
<strong>Testdaten sehen</strong> legt je Gruppe fest, wer Testpatienten und Testbenutzer überhaupt sieht.</p>
<p><strong>Rolle je Firma:</strong> Jede Person hat zwei Rollen: eine bei der DSKM und eine bei der Regeneration Clinic
(„Rolle DSKM“, „Rolle RGC“). „Keine Berechtigung“ heißt: kein Zugang zu dieser Firma. Wer in beiden Firmen eine Rolle
hat, schaltet unter dem Logo um. Die Rechte richten sich nach der Rolle in der gerade gewählten Firma. Die Rolle in
einer Firma vergibt und ändert nur, wer dort selbst <strong>Admin</strong> ist. Die anderen Felder sind gesperrt.
Sperren, Einmal-Passwort, zweiten Faktor zurücksetzen, Aus- und Einblenden und die Kontodaten ändern darf nur, wer in
jeder Firma der Person Admin ist. Konten ohne Rolle darf jeder Admin verwalten.</p>
<p>Unter <strong>Anmeldung</strong> legt die Administration die Zwei-Faktor-Anmeldung fest: freiwillig, Pflicht für
Admins oder Pflicht für alle.</p>
<p>Unter <strong>Rechte</strong> legt man je Gruppe fest, was erlaubt ist: Betrachter, Mitarbeiter, Mediziner, Admin.
Änderungen gelten sofort. Nicht Erlaubtes wird in der Oberfläche ausgeblendet. Admins schreiben Patientendaten nur bei
Testpatienten. Ausgenommen sind: Akten abschließen, Dokumente einem anderen Patienten zuordnen und endgültig
löschen.</p>""",
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
<p><strong>Administration › System</strong> zeigt den Zustand des Servers. Die Seite hat diese Reiter:
<strong>Übersicht</strong>, <strong>Wartung</strong>, <strong>Software</strong>, <strong>Zertifikat</strong>,
<strong>Zugang</strong>, <strong>Notfall</strong>, <strong>Protokolle</strong>, <strong>Anmeldungen und Hinweis</strong>, <strong>Verlauf</strong> und
<strong>Testphase</strong>.</p>
<p><strong>Übersicht</strong></p>
<ul>
<li>Auslastung (CPU, Arbeitsspeicher, Platte, Laufzeit) und offene Ubuntu-Updates.</li>
<li>Kennzahlen, Server, EPM und Texterkennung. Die Karten lassen sich in Breite und Höhe einstellen.</li>
<li>Die Auslastung als kleiner Verlauf. <strong>Größer anzeigen</strong> öffnet das Diagramm. Wählbar sind 1, 3 und
24 Stunden, 7 und 14 Tage sowie 1 und 6 Monate. Längere Zeiträume zeigen Mittelwerte mit gestrichelten Spitzen.</li>
</ul>
<p><strong>Updates und Neustart</strong></p>
<ul>
<li>Von hier aus lassen sich <strong>Updates installieren</strong>, der <strong>Server neu starten</strong> und EPM neu
starten.</li>
<li>Dafür braucht es Passwort und Code aus der Authenticator-App (Zwei-Faktor-Anmeldung nötig).</li>
<li>Vorher läuft automatisch eine Sicherung. Schlägt sie fehl, wird nichts verändert.</li>
<li>Angemeldete Benutzer werden gewarnt. Beginn sofort oder in 5 bis 60 Minuten. Ein wartender Auftrag lässt sich
zurückziehen.</li>
</ul>
<p><strong>EPM aktualisieren</strong> bringt EPM ohne Terminal auf einen neuen Stand:</p>
<ul>
<li>Der Server holt den Code, baut die Programmteile neu, sichert und stellt um.</li>
<li>Das dauert je nach Server 10 bis 30 Minuten. Beim Umstellen ist EPM kurz nicht erreichbar. Deshalb vorher Eingaben
speichern.</li>
<li>Der Auftrag läuft auf dem Server weiter, auch wenn die Seite zwischendurch nicht antwortet. Das Ergebnis erscheint
danach unter <strong>Aufträge</strong> samt Ausgabe.</li>
<li>Geht etwas schief, bleibt die bisherige Version in Betrieb. Unter <strong>Ausgabe</strong> steht, woran es lag.</li>
</ul>
<p><strong>Wartung</strong></p>
<ul>
<li><strong>Dienste</strong>: einzelne Container (backend, web, ocr, db) neu starten, z. B. wenn die Texterkennung
hängt.</li>
<li><strong>Selbstheilung</strong>: Der Server startet ausgefallene Dienste von selbst wieder und startet dreimal in Folge
ungesunde neu (höchstens einmal in 5 Minuten). Startet eine neue Version nicht – beim Update oder nach drei vergeblichen
Neustarts des Backends – schaltet er auf die <strong>gute Version</strong> zurück und zeigt oben auf jeder Seite einen
Hinweis mit den nächsten Schritten. Wird die Platte knapp, meldet er es und entfernt nur hängende Docker-Images. Die Karte
zeigt die laufende und die gute Version und die letzten Eingriffe (vollständig im Audit-Log unter „systemagent“).
<strong>Als gute Version bestätigen</strong> trägt die laufende Version als Rückfall ein – sinnvoll nach einigen Tagen
ohne Probleme; ein Update tut das selbst, wenn Musterdaten und Tests bestanden sind. <strong>Selbstheilung
ausschalten</strong> nur für Wartung von Hand, danach wieder einschalten. Sehen Sie im Browser „EPM startet gerade neu“,
läuft gerade ein Neustart, Update oder Rückfall; die Seite lädt sich alle 30 Sekunden neu.</li>
<li><strong>Speicher aufräumen</strong>: Das Systemprotokoll (Journal) auf eine Größe oder ein Alter verkleinern; dafür
gibt es eine einfache Rückfrage. Gespeicherte alte Versionen ankreuzen und löschen: Image-Dateien, Update-Pakete,
Docker-Images. Das braucht Passwort und Code. Die laufende, die vorherige und die gute Version bleiben immer.</li>
<li><strong>Technische Verwaltung</strong>: Django-Admin und API-Ansicht im Browser für 1 oder 8 Stunden einschalten,
z. B. zur Fehlersuche. Danach sind sie von selbst wieder aus. „Jetzt ausschalten“ beendet sofort.</li>
<li><strong>Uhrzeit</strong>: Zeitzone und Zeitsynchronisation (NTP) mit eigenem Zeitserver einstellen, ohne Internet
z. B. die OPNsense. Ist die Synchronisation aus, lässt sich die Uhrzeit von Hand setzen. Angezeigt wird auch, wie weit
die Uhr des Servers von diesem Gerät abweicht. Codes der Authenticator-App, Passkeys und Zertifikate brauchen eine
richtige Uhrzeit.</li>
</ul>
<p><strong>Software</strong></p>
<ul>
<li>Die vorhandenen Versionen mit <strong>Zurückschalten</strong>. Vorher sichert EPM automatisch.
Datenbank-Migrationen werden nicht zurückgedreht.</li>
<li><strong>Update-Paket einspielen</strong>: die Datei der Test-VM hochladen statt per scp. Der Server prüft Inhalt und
Prüfsummen. Er zeigt die SHA-256 zum Vergleichen.</li>
<li><strong>Update-Paket erstellen</strong> (Test-VM): Es liegt danach 2 Stunden zum Herunterladen bereit.</li>
<li><strong>OCR-Modelle einspielen</strong>.</li>
</ul>
<p><strong>Zertifikat</strong></p>
<ul>
<li>Inhaber, Aussteller und Ablauf.</li>
<li><strong>Zertifikat erneuern</strong> (eigene CA).</li>
<li><strong>Zertifikat importieren</strong>: CRT, KEY und CA als PEM. Der Schlüssel geht nur an den Server.</li>
<li>Das Stammzertifikat für die Geräte.</li>
</ul>
<p><strong>Zugang</strong>: SSH, erlaubte Netze, Firewall und Fail2ban.</p>
<ul>
<li><strong>SSH</strong> ist im Betrieb geschlossen. Für Arbeiten am Server öffnen Sie es für 1, 4 oder 8 Stunden. Das
braucht Passwort und Code. Danach schließt der Server SSH von selbst. <strong>Jetzt schließen</strong> beendet es sofort;
bestehende Verbindungen laufen weiter, bis sie enden.</li>
<li>Auf Wunsch gilt eine Öffnung nur für die aktuelle Adresse Ihres Geräts. Dieser Eintrag fällt beim Schließen weg.</li>
<li>Steht dort <strong>dauerhaft offen (Ersteinrichtung)</strong>, ist SSH seit der Einrichtung offen. Schließen Sie es
und öffnen Sie es danach nur noch auf Zeit.</li>
<li>Notzugang ohne SSH: die Konsole der VM im Hypervisor.</li>
<li><strong>Erlaubte Netze</strong>: aus welchen Netzen EPM (HTTPS) und SSH erreichbar sind, je mit Bezeichnung, bis zu 20.
Für SSH gibt es <strong>Meine aktuelle Adresse</strong>. Das letzte Netz für EPM und das Netz Ihres Geräts lassen sich
nicht entfernen – so sperren Sie sich nicht aus.</li>
<li><strong>Netzfilter für EPM</strong>: Docker umgeht die Firewall des Servers. Erst mit dem Netzfilter ist EPM nur aus
den erlaubten Netzen erreichbar.</li>
<li><strong>Firewall-Regeln</strong> und <strong>Gesperrte Adressen (Fail2ban)</strong> zeigen den Stand des Servers. Eine
gesperrte Adresse lässt sich mit <strong>Entsperren</strong> freigeben.</li>
</ul>
<p><strong>Protokolle</strong>: die letzten 100, 500 oder 2000 Zeilen der Container, des Systemagenten, der nächtlichen
Sicherung, der Übertragung oder des letzten Updates. Sie lassen sich filtern und herunterladen. Ein Abruf liegt eine
Stunde bereit und steht im Audit-Log.</p>
<p><strong>Außerdem:</strong> einen <strong>Hinweis an alle Benutzer</strong> setzen und angemeldete Benutzer abmelden.
Bei den Konten führen die Namen direkt zur Person in der Benutzerverwaltung (gesperrt, ohne zweiten Faktor, offenes
Einmal-Passwort).</p>
<p><strong>Testphase und Go-live</strong></p>
<ul>
<li><strong>Musterdaten automatisch anlegen</strong> abschalten. Dann entstehen beim Start keine Testpatienten und
Testkonten mehr.</li>
<li><strong>Menüpunkt „Import“ ausblenden</strong>, wenn die Altdaten übernommen sind. Die Seite bleibt über den Reiter
„Testphase“ erreichbar. Der Menüpunkt lässt sich wieder einblenden.</li>
<li><strong>Datenbank leeren</strong> (nur Rolle Admin) entfernt alles aus der Testphase. Das sind alle Akten (auch
echte), Dokumente, alle Scans samt Dateien (auch nicht zugeordnete), was die Texterkennung gelernt hat, Versorger, Ärzte,
die nicht ausgewählten Benutzer und das Audit-Log. Präparate, Auswahllisten, Vorlagen und Einstellungen bleiben.</li>
<li>Welche Konten bleiben, wird im Dialog angehakt. Das eigene Konto bleibt immer.</li>
<li>Bestätigt wird mit dem angezeigten Code zum Abtippen, mit Passwort und mit dem Code aus der Authenticator-App. Dazu
kommt die Rückfrage „Wollen Sie wirklich die Datenbank löschen?“.</li>
<li>Vorher sichert der Server automatisch. Zurück geht es nur über diese Sicherung.</li>
</ul>""",
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
        "id": "notfall", "gruppe": "administration", "titel": "Notfallpaket und Wiederaufbau nach Totalausfall",
        "rechte": ["system_verwalten", "backup_verwalten"], "seiten": ["/admin/system"],
        "html": """
<p>Fällt der Server ganz aus (Festplatte defekt, Diebstahl, Brand), wird EPM auf neuer Hardware mit dem
<strong>Notfallpaket</strong> wieder aufgebaut – ohne Internet und ohne Entwickler. Es entsteht unter
<strong>System › Notfall</strong> mit „Notfallpaket erstellen“ (Passwort und Code aus der Authenticator-App) und liegt
danach 6 Stunden als <code>epm-notfall-….tar</code> zum Herunterladen bereit; jeder Abruf steht im Audit-Log.</p>
<p>Im Paket: die laufenden Programme (Images) genau dieser Version, die Rollout-Skripte, die Debian-Pakete (Docker,
gpg, Firewall), die OCR-Modelle, wahlweise die jüngste Sicherung, die Einstellungen <em>ohne</em> Passwörter, das
CA-Zertifikat (den Schlüssel nur verschlüsselt mit dem Sicherungs-Passwort), Prüfsummen und der Wiederaufbau-Plan als
PDF. <strong>Nicht</strong> im Paket: Sicherungs-Passwort (steht auf dem Passwortblatt im Tresor), Zugang zum
Übertragungsziel; Datenbank-Passwort und geheimer Schlüssel werden beim Aufbau neu erzeugt.</p>
<p>Nach jedem EPM-Update und mindestens alle 30 Tage neu erstellen; die Ampel der Systemverwaltung erinnert daran. Zwei
Kopien an getrennten Orten aufbewahren (USB-Stick im Tresor, NAS), zusammen mit dem ausgedruckten Plan.</p>
<p>Der Wiederaufbau dauert etwa 1,5 bis 3 Stunden: Ubuntu Server installieren, Paket auf den Server kopieren und
auspacken, <code>sudo ./epm-notfall-aufbau.sh</code> starten und das Sicherungs-Passwort eingeben. Danach müssen sich
alle neu anmelden; Authenticator-Apps und Passkeys gelten weiter.
<a href="/api/system/notfallplan/?art=pdf">Wiederaufbau-Plan als PDF</a> (mit Checkliste zum Ausdrucken); im
Reiter „Notfall“ lässt er sich auch direkt lesen. Eigene Kapitel gibt es für „nur EPM kaputt“ und „nur die Datenbank
kaputt“.</p>""",
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
<p>Der Import übernimmt Akten aus dem Altsystem. So geht es:</p>
<ol>
<li><strong>Dump laden</strong>.</li>
<li><strong>Zuordnungen</strong> pflegen.</li>
<li>Den <strong>Probelauf</strong> prüfen.</li>
<li><strong>Importieren</strong>.</li>
</ol>
<p>Bis die Übernahme abgeschlossen ist, lässt sich ein Import zurücknehmen. Übernommene Dokumente stehen danach unter
„Altdokumente prüfen“.</p>""",
    },
]
