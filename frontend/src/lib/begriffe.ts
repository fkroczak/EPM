/**
 * Erklärungen der Fachbegriffe, die in der Oberfläche vorkommen (Rückfrage beantwortet am 10.10.2026: „Erklärung beim
 * Draufzeigen, mindestens BIA und Entwurf“). Eine Stelle für alle Texte – angezeigt über den Baustein ``<Begriff>``
 * (components/ui/Begriff.tsx). Kurz halten: ein bis zwei Sätze, in Alltagssprache.
 */
export const BEGRIFFE = {
  texterkennung: "EPM liest den Text aus dem Bild eines Scans – auf dem eigenen Server, ohne Internet. Dabei kann es sich "
    + "verlesen; darum prüfen Sie jeden Wert, bevor er in die Akte kommt.",
  gelernt: "EPM merkt sich Ihre Korrekturen: welche Bezeichnung auf dem Befund zu welchem Laborwert gehört und welche "
    + "Zeilen keine Werte sind. Gespeichert werden nur Bezeichnungen, keine Werte und keine Namen.",
  bia: "Bioelektrische Impedanzanalyse: Messung der Körperzusammensetzung (Muskel-, Fett- und Wasseranteil) mit "
    + "schwachem Strom über Elektroden an Hand und Fuß.",
  entwurf: "Noch nicht freigegeben: Änderungen sind gespeichert, gelten aber erst nach „Freigeben“ bzw. "
    + "„Veröffentlichen“ und sind bis dahin nur hier sichtbar.",
  // Vorlagen-Portal (F180): eine veröffentlichte Version einer Vorlage heißt in der Oberfläche „Fassung“
  fassung: "Freigegebener Stand einer Vorlage. Jedes Freigeben ergibt eine neue Fassung; frühere bleiben erhalten und "
    + "lassen sich ansehen und wiederherstellen. Jede PDF vermerkt, mit welcher Fassung sie erzeugt wurde.",
  bmi: "Body-Mass-Index: Gewicht in kg geteilt durch die Körpergröße in Metern zum Quadrat. EPM rechnet ihn aus Gewicht "
    + "und Größe der Stammdaten.",
  pe: "Parenterale Ernährung: Nährlösung über die Vene statt über den Darm – hier der Mischbeutel mit Eiweiß, Zucker "
    + "und Fett.",
  wiedervorlage: "Erinnerung an eine Akte zu einem festen Tag, z. B. „in 14 Tagen nachfragen“. Sie erscheint auf der "
    + "Startseite und im Kalender, bis sie abgehakt ist.",
  wiedereinbestellung: "Der Patient sollte wieder in die Sprechstunde kommen, es ist aber noch kein Termin geplant.",
  glim: "GLIM-Kriterien: international vereinbarte Einordnung einer Mangelernährung nach Gewichtsverlust, niedrigem BMI, "
    + "Muskelmasse, verminderter Nahrungsaufnahme und Krankheitslast.",
  testpatient: "Übungsakte (Nummer ab 9001): zum Ausprobieren, zählt in keiner Statistik.",
  storniert: "Als falsch gekennzeichnet: Der Eintrag bleibt durchgestrichen sichtbar, mit Grund, Person und Zeitpunkt. "
    + "Gelöscht wird nichts.",
  // Hinweise im Plan-Editor (F187)
  referenzbereich: "Bereich, in dem ein Laborwert bei gesunden Menschen üblicherweise liegt – er steht auf dem "
    + "Laborbefund. Ein Wert außerhalb ist ein Anlass zum Prüfen, keine Diagnose.",
  // Administration (Systemverwaltung ohne SSH, 10.10.2026)
  systemagent: "Kleines Programm auf dem Server, das nur eine feste Liste von Tätigkeiten ausführt (Updates, Neustart, "
    + "Sicherung …) und jede Minute den Zustand meldet. EPM selbst hat keinen Zugriff auf den Server.",
  container: "Ein abgeschlossener Teil von EPM, der für sich läuft: backend (Anwendung), web (liefert die Oberfläche "
    + "aus), ocr (Texterkennung), db (Datenbank). Einzeln neu startbar.",
  ca: "Zertifizierungsstelle: stellt das Zertifikat aus. Vertraut ein Gerät der CA (Stammzertifikat installiert), "
    + "zeigt der Browser keine Warnung, und Passkeys funktionieren.",
  update_paket: "Eine Datei mit einer fertigen, auf der Test-VM geprüften EPM-Version – für den Server ohne Internet.",
  uebertragungsziel: "Ordner außerhalb des Servers (WebDAV, z. B. Nextcloud), in den die verschlüsselten Sicherungen "
    + "kopiert werden – damit sie einen Ausfall des Servers überstehen.",
} as const;

export type BegriffSchluessel = keyof typeof BEGRIFFE;
