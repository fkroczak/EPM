/** Datenformen der API (siehe docs/BACKEND-FUNKTIONEN.md). */
import type { Darstellung } from "./darstellung";

export type Recht =
  | "akten_lesen" | "eintraege_erfassen" | "akten_bearbeiten" | "plaene_anlegen" | "plaene_freigeben"
  | "akten_abschliessen" | "akten_wieder_oeffnen" | "versorger_pflegen" | "vorlagen_pflegen" | "audit_lesen"
  | "benutzer_verwalten" | "backup_verwalten" | "testdaten_zuruecksetzen";

export type Karte = { id: "termine" | "gewicht" | "plaene" | "pruefen" | "aktiv"; sichtbar: boolean };

export type Ich = {
  id: number;
  benutzername: string;
  anzeigename: string;
  titel: string;
  vorname: string;
  nachname: string;
  kuerzel: string | null;
  funktion: string;
  rolle: "betrachter" | "mitarbeiter" | "mediziner" | "admin";
  ist_test: boolean;
  darstellung: Partial<Darstellung>;
  startseite: { karten?: Karte[] };
  rechte: Recht[];
  /** Admins: Patientendaten nur bei Testpatienten schreiben (echte Akten nur lesen) */
  schreibt_nur_testpatienten: boolean;
};

export type Schritt = "anmelden" | "kennwort_aendern" | "2fa_einrichten" | "2fa" | "fertig";

export type Status = {
  schritt: Schritt;
  benutzer?: Ich;
  organisation?: { name: string; anschrift: string };
  notfallcodes?: string[];
};

export const ROLLEN: Record<string, string> = {
  betrachter: "Betrachter",
  mitarbeiter: "Mitarbeiter",
  mediziner: "Mediziner",
  admin: "Admin",
};

export const ABSCHLUSSANLAESSE: Record<string, string> = {
  verstorben: "verstorben",
  therapie_beendet: "Therapie beendet",
  betreuung_gewechselt: "Betreuung gewechselt",
};

export const GESCHLECHTER: Record<string, string> = { w: "weiblich", m: "männlich", d: "divers", "": "—" };

export const NICKEL: Record<string, string> = { ja: "ja", nein: "nein", unbekannt: "unbekannt" };

export type Trend = { richtung: "down" | "up" | "flat" | null; prozent: number; warnung: boolean };

export type Kennzahlen = {
  gewicht: { kg: number; am: string } | null;
  trend: Trend | null;
  letzter_kontakt: string | null;
  termin_woche: boolean;
  hinweise: { art: "gewicht" | "plan" | "versorger" | "kontakt"; text: string }[];
};

export type PatientZeile = {
  id: number;
  nummer: number;
  nachname: string;
  vorname: string;
  geburtsdatum: string;
  alter: number;
  ort: string;
  katheter: number | null;
  katheter_name: string | null;
  versorger: number | null;
  versorger_name: string | null;
  ansprechpartner: number | null;
  ansprechpartner_name: string | null;
  nickelallergie: "ja" | "nein" | "unbekannt";
  ist_abgeschlossen: boolean;
  abgeschlossen_am: string | null;
  abschluss_anlass: string;
  ist_test: boolean;
  kennzahlen: Kennzahlen | null;
};

export type Versionskopf = { version: number; zeitpunkt: string; person: string } | null;

export type Patient = {
  id: number;
  nummer: number;
  nachname: string;
  vorname: string;
  geburtsdatum: string;
  geschlecht: "" | "w" | "m" | "d";
  strasse: string;
  plz: string;
  ort: string;
  telefon: string;
  telefon2: string;
  email: string;
  krankenkasse: string;
  hausarzt: string;
  ueberweisung_durch: string;
  groesse_cm: number | null;
  katheter: number | null;
  versorger: number | null;
  ansprechpartner: number | null;
  nickelallergie: "ja" | "nein" | "unbekannt";
  diagnose: string;
  therapie: string;
  empfehlung: string;
  bemerkung: string;
  abgeschlossen_am: string | null;
  abschluss_anlass: string;
  abschluss_notiz: string;
  ist_abgeschlossen: boolean;
  ist_test: boolean;
  angelegt_am: string;
  angelegt_von_name: string | null;
  geaendert_am: string;
  kopf: {
    gewicht: { kg: number; am: string } | null;
    gewichtstrend: {
      prozent: number; von: string; bis: string; tage: number; warnung: boolean; vergleich_kg: number; aktuell_kg: number;
    } | null;
    bmi: number | null;
    katheter: string | null;
    versorger: string | null;
    ansprechpartner: string | null;
    ansprechpartner_telefon: string | null;
    nickelallergie: string;
    aktueller_plan: { id: number; gueltig_ab: string; kcal: number; laufzeit_h: number | null } | null;
    naechster_termin: {
      id: number; art: string; titel: string; faellig_am: string; uhrzeit: string | null; ort: string | null; bei: string;
    } | null;
    versionen: Record<"diagnose" | "therapie" | "empfehlung", Versionskopf>;
    zaehler: { kontakte: number; gewichte: number; dokumente: number; termine_offen: number; infusionsplaene: number };
  } | null;
};

export type Termin = {
  id: number;
  patient: number;
  patient_name: string;
  patient_ist_test: boolean;
  art: "praxistermin" | "rueckruf" | "wiedervorlage" | "sonstiges";
  ort: number | null;
  ort_name: string | null;
  faellig_am: string;
  uhrzeit: string | null;
  bei: string;
  titel: string;
  notiz: string;
  kontakt: number | null;
  erledigt_am: string | null;
  erledigt_von_name: string | null;
  angelegt_am: string;
  angelegt_von_name: string | null;
};

export const TERMINARTEN: Record<string, string> = {
  praxistermin: "Praxistermin",
  rueckruf: "Rückruf",
  wiedervorlage: "Wiedervorlage",
  sonstiges: "Sonstiges",
};

export type Gewicht = {
  id: number;
  patient: number;
  gewicht_kg: number;
  gemessen_am: string;
  datum_ungenau: boolean;
  quelle: string;
  notiz: string;
  erfasst_am: string;
  erfasst_von_name: string | null;
};

export const GEWICHTSQUELLEN: Record<string, string> = {
  telefonisch: "Telefonisch (Patient)",
  ambulanz: "Ambulanz / Praxis",
  versorger: "Versorger",
  arztbrief: "Arztbrief",
  altsystem: "Altsystem",
};

export type Kontakt = {
  id: number;
  patient: number;
  zeitpunkt: string;
  art: number | null;
  art_name: string | null;
  text: string;
  erfasst_am: string;
  erfasst_von_name: string | null;
  storniert_am: string | null;
  storniert_von_name: string | null;
  storno_grund: string;
  termine: { id: number; art: string; faellig_am: string; uhrzeit: string | null; ort: string | null; erledigt: boolean }[];
};

export type Auswahlwert = { id: number; liste: string; wert: string; reihenfolge: number; aktiv: boolean };

export type Praeparat = {
  id: number;
  kategorie: string;
  name: string;
  konzentration: string;
  einheit: string;
  reihenfolge: number;
  aktiv: boolean;
  anzeige: string;
  in_plaenen: number;
};

export type Ansprechpartner = {
  id: number;
  versorger: number;
  name: string;
  zustaendigkeit: string;
  telefon: string;
  mobil: string;
  email: string;
  notiz: string;
  aktiv: boolean;
  patienten_anzahl: number;
};

export type Versorger = {
  id: number;
  name: string;
  strasse: string;
  plz: string;
  ort: string;
  telefon: string;
  fax: string;
  email: string;
  notiz: string;
  aktiv: boolean;
  ansprechpartner: Ansprechpartner[];
  patienten_anzahl: number;
};

export type Dokument = {
  id: number;
  patient: number;
  typ: number | null;
  typ_name: string | null;
  titel: string;
  datum: string | null;
  datum_quelle: "eingabe" | "pdf" | "exif" | "dateidatum";
  typ_geprueft: boolean;
  notiz: string;
  ausgeblendet: boolean;
  originalname: string;
  mime: string;
  groesse: number;
  sha256: string;
  herkunft: "upload" | "altsystem" | "system";
  hochgeladen_am: string;
  hochgeladen_von_name: string | null;
};

export type Plan = {
  id: number;
  patient: number;
  patient_name: string;
  status: "entwurf" | "aktuell" | "abgeloest";
  vorgaenger: number | null;
  gueltig_ab: string;
  basis_praeparat: number | null;
  basis_ml: number | null;
  glucose_praeparat: number | null;
  glucose_g: number | null;
  aminosaeuren_praeparat: number | null;
  aminosaeuren_g: number | null;
  lipide_praeparat: number | null;
  lipide_g: number | null;
  albumin_praeparat: number | null;
  albumin_g: number | null;
  natrium_mmol: number | null;
  kalium_mmol: number | null;
  phosphat_mmol: number | null;
  calcium_mmol: number | null;
  magnesium_mmol: number | null;
  spurenelemente: number | null;
  vitamine: number[];
  vitamine_namen: string[];
  kcal_manuell: number | null;
  kcal_berechnet: number;
  kcal: number;
  laufzeit_h: number | null;
  tage_pro_woche: number | null;
  katheterschutz: number | null;
  pantozol_stufe: number;
  pantozol_tage: number | null;
  bemerkung: string;
  positionen: {
    id?: number; praeparat: number; praeparat_name?: string; kategorie?: string; menge: number | null; einheit: string;
    haeufigkeit: string; bemerkung: string; reihenfolge?: number;
  }[];
  geaenderte_felder: string[];
  erstellt_am: string;
  erstellt_von_name: string | null;
  freigegeben_am: string | null;
  freigegeben_von_name: string | null;
  pdf_datei: string;
  pdf_sha256: string;
  vorlage_version: number | null;
};

export type Vergleich = {
  vorgaenger: { id: number; gueltig_ab: string; status: string } | null;
  zeilen: { schluessel: string; wert: string; vorher: string | null; jetzt: string | null; geaendert: boolean }[];
  anzahl_geaendert: number;
};

export type Verlaufseintrag = {
  objekt_id: number;
  art: string;
  zeitpunkt: string;
  person: string | null;
  person_id: number | null;
  grund: string | null;
  bereich: string;
  aktion: string;
  aenderungen: { feld: string; alt: string; neu: string }[];
};

export type Benutzer = {
  id: number;
  username: string;
  titel: string;
  first_name: string;
  last_name: string;
  kuerzel: string | null;
  funktion: string;
  email: string;
  rolle: string;
  ist_test: boolean;
  is_active: boolean;
  nur_historisch: boolean;
  anzeigename: string;
  zweiter_faktor: boolean;
  muss_kennwort_aendern: boolean;
  einmal_kennwort_gueltig_bis: string | null;
  gesperrt_am: string | null;
  sperrgrund: string;
  fehlversuche: number;
  last_login: string | null;
  date_joined: string;
};

export type Systemereignis = {
  id: number;
  zeitpunkt: string;
  art: string;
  art_name: string;
  gruppe: string;
  gruppe_name: string;
  beschreibung: string;
  benutzer: number | null;
  person: string;
  benutzername: string;
  objekt: string;
  details: Record<string, unknown>;
  ip: string | null;
  geraet: string;
};

export type Einstellungen = Record<string, number | string>;
