/** Datenformen der Altdaten-Übernahme (backend/altimport/api.py, umsetzung.py). */

export type Status = "leer" | "geladen" | "importiert" | "abgeschlossen";

export type Lauf = {
  id: number; art: "probelauf" | "import" | "dokumente" | "zurueckgenommen" | "abgeschlossen"; art_name: string;
  begonnen_am: string; beendet_am: string | null; person: string | null; erfolgreich: boolean; dump_name: string;
  zahlen: Zahlen & Record<string, unknown>; fehler: string; protokoll?: Protokollzeile[];
};

export type Zaehlung = { alt: number; neu: number; nicht?: Record<string, number>; abgeschlossen?: number; aktuell?: number };
export type Zahlen = {
  patienten?: Zaehlung; gewichte?: Zaehlung; kontakte?: Zaehlung; infusionen?: Zaehlung;
  versorger?: { alt: number; neu: number; ansprechpartner_neu: number };
  benutzer?: { alt: number; neu: number; konten: number };
  praeparate_neu?: number; auswahlwerte_neu?: number;
  geschrieben?: Record<string, number>;
};

export type Protokollzeile = { regel: number; bereich: string; stufe: "fehler" | "warnung" | "hinweis" | "info"; text: string;
  anzahl: number; beispiele: string[] };

export type Bestandszahlen = { patienten: number; gewichte: number; kontakte: number; plaene: number; dokumente: number };

export type Stand = {
  status: Status; status_name: string;
  dump: { name: string; sha256: string; groesse: number; geladen_am: string; geladen_von: string | null; hinweise: string[] } | null;
  tabellen: { name: string; spalten: number; zeilen: number }[];
  echte_akten: { anzahl: number; nummern: number[] };
  importiert_am: string | null; importiert_von: string | null;
  abgeschlossen_am: string | null; abgeschlossen_von: string | null;
  uebernommen: Bestandszahlen | null;
  dokumentenordner: string; upload_max_mb: number;
  laeufe: Lauf[];
};

// ---------------------------------------------------------------- Zuordnungen
export type Feldzeile = { name: string; titel: string; pflicht: boolean; hinweis: string; spalte: string | null;
  art: "gewaehlt" | "vorschlag" | "ohne" | "fehlt" };
export type Restspalte = { spalte: string; art: "kennwort" | "bekannt" | "ignoriert" | "offen"; grund: string };
export type Quelltabelle = { name: string; titel: string; ziel: string; tabelle: string | null; art: "gewaehlt" | "vorschlag" | "ohne";
  zeilen: number; felder: Feldzeile[]; rest: Restspalte[]; spalten: string[] };

export type BenutzerWahl =
  | { art: "benutzer"; id: number }
  | { art: "konto"; benutzername: string; vorname: string; nachname: string; titel: string; rolle: string }
  | { art: "historisch"; benutzername: string; vorname: string; nachname: string; titel: string }
  | { art: "ohne" };
export type Benutzerzeile = { schluessel: string; name: string; im_altsystem_konto: boolean; rechte: string | null;
  anzahl: Record<string, number>; eintraege: number; vorschlag: BenutzerWahl; entscheidung: Partial<BenutzerWahl> | null;
  wirksam: BenutzerWahl; fehler: string; aehnlich: number[] };

export type VersorgerWahl =
  | { art: "neu"; versorger: string; ansprechpartner: string }
  | { art: "vorhanden"; id: number; ansprechpartner: string }
  | { art: "kein" } | { art: "leer" };
export type Versorgerzeile = { schluessel: string; firma: string; name: string; email: string; tel: string; patienten: number;
  vorschlag: VersorgerWahl; entscheidung: VersorgerWahl | null; wirksam: VersorgerWahl; fehler: string };

export type KatheterWahl = { art: "wert"; id: number } | { art: "neu"; wert: string } | { art: "kein" } | { art: "leer" };
export type Katheterzeile = { schluessel: string; text: string; anzahl: number; vorschlag: KatheterWahl;
  entscheidung: KatheterWahl | null; wirksam: KatheterWahl; fehler: string };
export type Wertzeile = { schluessel: string; text: string; anzahl: number; vorschlag: string | null; entscheidung: string | null;
  wirksam: string | null; fehler: string };

export type PraeparatWahl =
  | { art: "praeparat"; id: number }
  | { art: "neu"; name: string; konzentration: string; kategorie?: string }
  | { art: "bemerkung" } | { art: "leer" };
export type Praeparatzeile = { schluessel: string; text: string; anzahl: number; vorschlag: PraeparatWahl | null;
  neu_vorschlag: { name: string; konzentration: string }; aehnlich: number[]; entscheidung: PraeparatWahl | null;
  wirksam: PraeparatWahl | null; fehler: string };
export type Praeparatfeld = { titel: string; kategorie: string; kategorien: string[]; zeilen: Praeparatzeile[] };

export type GeloeschtWahl = { art: "nicht" } | { art: "abgeschlossen"; anlass: string | null; am: string | null };
export type Geloeschtzeile = { schluessel: string; name: string; geburtsdatum: string | null; geloescht_am: string;
  gewichte: number; kontakte: number; plaene: number; entscheidung: GeloeschtWahl | null; wirksam: GeloeschtWahl; fehler: string };

export type Entscheidungsart = "wert" | "leer" | "unveraendert" | "auslassen";
export type Auffaelligkeit = { schluessel: string; tabelle: string; tabelle_titel: string; id: string; patient: number | null;
  feld: string; feld_titel: string; art: string; text: string; wert: string | null; roh: string | null;
  standard: Entscheidungsart | "offen"; moeglich: Entscheidungsart[]; eingabe: "text" | "zahl" | "datum"; blockiert: boolean;
  entscheidung: { art: Entscheidungsart; wert?: string; alt: string | null } | null };

export type Offen = { bereich: "spalten" | "benutzer" | "versorger" | "werte" | "praeparate" | "geloeschte" | "auffaelligkeiten"; text: string };

export type Zuordnungsstand = {
  quelle: { tabellen: Quelltabelle[]; uebrig: { tabelle: string; zeilen: number; art: "offen" | "ignoriert" }[]; im_dump: string[] };
  benutzer: Benutzerzeile[]; versorger: Versorgerzeile[];
  werte: { katheter: Katheterzeile[]; nickel: Wertzeile[]; geschlecht: Wertzeile[] };
  praeparate: Record<string, Praeparatfeld>;
  geloeschte: Geloeschtzeile[]; auffaelligkeiten: Auffaelligkeit[]; offen: Offen[];
  protokoll: Protokollzeile[]; zahlen: Zahlen;
};

export type Bestand = {
  benutzer: { id: number; username: string; anzeigename: string; rolle: string; aktiv: boolean; nur_historisch: boolean; ist_test: boolean }[];
  versorger: { id: number; name: string; aktiv: boolean }[];
  ansprechpartner: { id: number; versorger: number; name: string }[];
  katheter: { id: number; wert: string; aktiv: boolean }[];
  praeparate: { id: number; kategorie: string; name: string; konzentration: string; aktiv: boolean }[];
};

export type Zuordnung = {
  status: Status; stand: Zuordnungsstand | null; hindernisse: string[]; bestand: Bestand | null;
  auswahl?: { rollen: string[]; anlaesse: Record<string, string>; kategorien: Record<string, string> };
};

export type Dokumentenstand = {
  vorhanden: boolean; pfad: string; ordner: number; dateien: number; bytes: number; erledigt: number; offen: number;
  offen_bytes: number; ohne_patient: { ordner: string; dateien: number }[]; ohne_patient_anzahl: number;
  nicht_uebernommen: { pfad: string; grund: string }[]; nicht_uebernommen_anzahl: number; unlesbar: number; frei_bytes: number | null;
};
export type Etappe = { uebernommen: number; bytes: number; offen: number; offen_bytes: number; erledigt: number; fertig: boolean;
  probleme: { pfad: string; grund: string }[] };

/** Änderung an den Zuordnungen: Bereich und Entscheidungen (null = Entscheidung zurücknehmen, es gilt der Vorschlag) */
export type Aenderung = { bereich: string; aenderungen: unknown };

export const BEREICHE: Record<string, string> = {
  benutzerdaten: "Benutzer", benutzer: "Benutzer", versorger: "Versorger", patienten: "Patienten", gewichte: "Gewichte",
  kontakte: "Kontakte", infusionen: "Infusionspläne",
};
export const NICHT: Record<string, string> = {
  geloescht: "im Altsystem gelöscht", ausgelassen: "ausgelassen (siehe Auffälligkeiten)", fehler: "offene Auffälligkeit",
  patient_nicht_uebernommen: "Patient wird nicht übernommen", ohne_patient: "ohne Patient",
  platzhalter: "Platzhalter (leer, 0, 9999)", leer: "ohne Text",
};
