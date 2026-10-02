/** Datenformen der API (siehe docs/BACKEND-FUNKTIONEN.md). */
import type { Darstellung } from "./darstellung";

export type Recht =
  | "akten_lesen" | "eintraege_erfassen" | "akten_bearbeiten" | "dokumente_umhaengen" | "dokumente_loeschen"
  | "plaene_anlegen" | "plaene_freigeben" | "plaene_abschliessen"
  | "datenschutz_bearbeiten" | "datenschutz_entscheiden" | "akten_loeschen"
  | "akten_abschliessen" | "akten_wieder_oeffnen" | "versorger_pflegen" | "vorlagen_pflegen" | "audit_lesen"
  | "benutzer_verwalten" | "backup_verwalten" | "testdaten_zuruecksetzen" | "system_verwalten";

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

/** Protonenpumpenhemmer als Kurzinfusion; Codes wie im Altsystem (Feld pantozol) */
export const PROTONENPUMPENHEMMER: [number, string][] = [[0, "kein"], [1, "Pantozol® 40 mg"], [3, "Pantozol® 20 mg"], [2, "Nexium®"]];
/** Gabezeiten als Bitmaske wie im Altsystem (Feld panzeit): morgens 4, mittags 2, abends 1 */
export const PPI_ZEITEN: [number, string][] = [[4, "morgens"], [2, "mittags"], [1, "abends"]];

export function ppiName(code: number | string): string {
  return PROTONENPUMPENHEMMER.find(([c]) => String(c) === String(code))?.[1] ?? String(code);
}

export function ppiZeiten(maske: number | string | null | undefined): string {
  const m = Number(maske);
  return m ? PPI_ZEITEN.filter(([bit]) => m & bit).map(([, n]) => n).join(", ") : "";
}

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
  kein_katheter: boolean;
  kein_versorger: boolean;
  ist_abgeschlossen: boolean;
  abgeschlossen_am: string | null;
  abschluss_anlass: string;
  ist_test: boolean;
  /** Verarbeitung eingeschränkt (Art. 18 DSGVO): nur sichtbar, solange die eigene Einsicht läuft */
  ist_eingeschraenkt: boolean;
  kennzahlen: Kennzahlen | null;
};

/** Aufbewahrungsfrist einer abgeschlossenen Akte */
export type Aufbewahrung = { jahre: number; regulaer_bis: string | null; verlaengert_bis: string | null; grund: string;
  bis: string | null; abgelaufen: boolean };

export type ErklaerungsArt = "datenschutzinformation" | "einwilligung" | "schweigepflichtentbindung";
export const ERKLAERUNGEN: Record<ErklaerungsArt, string> = {
  datenschutzinformation: "Datenschutzinformation",
  einwilligung: "Einwilligung in die Datenverarbeitung",
  schweigepflichtentbindung: "Schweigepflichtentbindung",
};
export const ERKLAERUNGEN_KURZ: Record<ErklaerungsArt, string> = {
  datenschutzinformation: "Datenschutzinformation", einwilligung: "Einwilligung", schweigepflichtentbindung: "Schweigepflichtentbindung",
};
export type ErklaerungsStand = { status: "nicht_erfasst" | "liegt_vor" | "widerrufen"; am: string | null; id: number | null };

export type Erklaerung = {
  id: number; patient: number; art: ErklaerungsArt; art_name: string; status: "liegt_vor" | "widerrufen"; erteilt_am: string;
  dokument: number | null; dokument_titel: string | null; vorlage_version: number | null; notiz: string;
  widerrufen_am: string | null; widerruf_notiz: string; erfasst_am: string; erfasst_von_name: string | null; hinweis?: string;
};

export const ANFRAGEARTEN: Record<string, string> = {
  auskunft: "Auskunft / Kopie der Akte", berichtigung: "Berichtigung", loeschung: "Löschung",
  einschraenkung: "Einschränkung der Verarbeitung", widerruf: "Widerruf einer Einwilligung", sonstiges: "Sonstiges",
};
export const ANFRAGE_ERGEBNISSE: Record<string, string> = {
  erfuellt: "erfüllt", eingeschraenkt: "Verarbeitung eingeschränkt statt gelöscht", abgelehnt: "abgelehnt",
  zurueckgezogen: "zurückgezogen",
};

export type Datenschutzanfrage = {
  id: number; patient: number; patient_name: string; patient_nummer: number; patient_ist_test: boolean;
  patient_eingeschraenkt: boolean; art: string; art_name: string; eingegangen_am: string; gestellt_von: string; inhalt: string;
  frist_verlaengert: boolean; verlaengerung_grund: string; frist_bis: string; ueberfaellig: boolean; ist_offen: boolean;
  ergebnis: string; ergebnis_name: string; begruendung: string; mitgeteilt_am: string | null; erledigt_am: string | null;
  erledigt_von_name: string | null; erfasst_am: string; erfasst_von_name: string | null;
};

export type Loeschpruefung = { moeglich: boolean; rechtsgrund: "frist" | "antrag" | null; hinweis: string;
  frist_laeuft_bis: string | null; antrag: number | null; antrag_vom: string | null };

/** Reiter „Datenschutz“ einer Akte */
export type AktenDatenschutz = {
  aufbewahrung: Aufbewahrung;
  einschraenkung: { am: string; von: string | null; grund: string } | null;
  einsicht_bis: string | null;
  erklaerungen: Erklaerung[];
  stand: Record<ErklaerungsArt, ErklaerungsStand>;
  pflicht: ErklaerungsArt[];
  vorlagen: Record<ErklaerungsArt, { version: number; entwurf: boolean }>;
  anfragen: Datenschutzanfrage[];
  kopien: { zeitpunkt: string; person: string | null }[];
  loeschen: Loeschpruefung;
};

type AktenZeile = { id: number; nummer: number; name: string; ist_test: boolean };
export type DatenschutzUebersicht = {
  anfragen_offen: Datenschutzanfrage[];
  anfragen_ueberfaellig: number;
  aufbewahrung_abgelaufen: (AktenZeile & { abgeschlossen_am: string; aufbewahrung_bis: string; verlaengert: boolean; eingeschraenkt: boolean })[];
  aufbewahrung_laeuft_ab: (AktenZeile & { abgeschlossen_am: string; aufbewahrung_bis: string; verlaengert: boolean; eingeschraenkt: boolean })[];
  eingeschraenkt: (AktenZeile & { am: string; von: string | null; grund: string })[];
  erklaerungen_fehlen: number;
  abschluss_pruefen: number;
  loeschprotokoll: { id: number; nummer: number; ist_test: boolean; geloescht_am: string; geloescht_von: string | null;
    rechtsgrund: string; rechtsgrund_name: string; grund: string; abgeschlossen_am: string | null;
    aufbewahrung_bis: string | null; umfang: Record<string, number | string> }[];
  einstellungen: { aufbewahrung_jahre: number; abschluss_pruefen_monate: number; protokoll_aufbewahrung_jahre: number;
    pflicht_erklaerungen: ErklaerungsArt[] };
  darf_entscheiden: boolean;
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
  /** bewusst kein Katheter / kein Versorger (leer = noch nicht erfasst) */
  kein_katheter: boolean;
  kein_versorger: boolean;
  diagnose: string;
  therapie: string;
  empfehlung: string;
  bemerkung: string;
  abgeschlossen_am: string | null;
  abschluss_anlass: string;
  abschluss_notiz: string;
  ist_abgeschlossen: boolean;
  ist_test: boolean;
  ist_eingeschraenkt: boolean;
  eingeschraenkt_am: string | null;
  /** nur bei abgeschlossenen Akten */
  aufbewahrung: Aufbewahrung | null;
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
    /** Erklärungen zum Datenschutz, nachgehalten wie die Nickelallergie */
    erklaerungen: { stand: Record<ErklaerungsArt, ErklaerungsStand>; pflicht: ErklaerungsArt[]; fehlt: ErklaerungsArt[] };
    datenschutz_anfragen: number;
    kein_katheter: boolean;
    kein_versorger: boolean;
    /** Bezugspersonen mit Schweigepflichtentbindung */
    auskunft: { id: number; name: string; beziehung: string | null; telefon: string }[];
    hausarzt: { id: number; name: string; praxis: string; telefon: string } | null;
    aktueller_plan: { id: number; gueltig_ab: string; kcal: number; laufzeit_h: number | null } | null;
    naechster_termin: {
      id: number; art: string; titel: string; faellig_am: string; uhrzeit: string | null; ort: string | null; bei: string;
    } | null;
    versionen: Record<"diagnose" | "therapie" | "empfehlung", Versionskopf>;
    zaehler: { kontakte: number; gewichte: number; dokumente: number; termine_offen: number; infusionsplaene: number;
      bezugspersonen: number; aerzte: number; erklaerungen: number };
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

/** Gemeinsame Ärzteliste (Festlegung 01.10.2026) */
export type Arzt = {
  id: number;
  name: string;
  praxis: string;
  fachrichtung: string;
  strasse: string;
  plz: string;
  ort: string;
  telefon: string;
  fax: string;
  email: string;
  notiz: string;
  aktiv: boolean;
  patienten_anzahl: number;
};

export const ARZTROLLEN: Record<string, string> = {
  hausarzt: "Hausarzt", facharzt: "Facharzt", ueberweisend: "Überweisend", klinik: "Klinik", sonstige: "Sonstige",
};

/** Arzt eines Patienten (Zuordnung mit Rolle) */
export type PatientArzt = {
  id: number;
  patient: number;
  arzt: number;
  arzt_daten: Omit<Arzt, "notiz" | "patienten_anzahl">;
  rolle: keyof typeof ARZTROLLEN;
  rolle_name: string;
  notiz: string;
  aktiv: boolean;
  angelegt_am: string;
  angelegt_von_name: string | null;
};

/** Bezugsperson (Mutter, Vater, Betreuer/in …) */
export type Bezugsperson = {
  id: number;
  patient: number;
  beziehung: number | null;
  beziehung_name: string | null;
  name: string;
  telefon: string;
  mobil: string;
  email: string;
  strasse: string;
  plz: string;
  ort: string;
  notiz: string;
  auskunft_erlaubt: boolean;
  aktiv: boolean;
  angelegt_am: string;
  angelegt_von_name: string | null;
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
  albumin_ml: number | null;
  ca_mg_mmol: number | null;
  ca_mg_grenze_mmol: number | null;
  /** wie im Altsystem: Ca + Mg ≤ Gesamtvolumen ÷ 100 */
  ca_mg_stabil: boolean | null;
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
  /** berechnet wie im Altsystem: Körpergewicht × 35 ml, bei Freigabe eingefroren */
  gesamtvolumen_ml: number | null;
  volumen_gewicht_kg: number | null;
  /** Gesamtvolumen wie auf der alten PDF: Mischbeutel + Zusatzvolumen (Basislösung) */
  volumen_summe_ml: number | null;
  laufzeit_h: number | null;
  /** Gesamtvolumen ÷ Laufzeit */
  rate_ml_h: number | null;
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
  /** Freigabe außerhalb von EPM (z. B. per E-Mail): Weg, Datum, wer den Plan im System abgeschlossen hat, Nachweis */
  freigabe_weg: "" | "system" | "email" | "telefon" | "persoenlich" | "schriftlich";
  freigabe_weg_name: string;
  freigabe_datum: string | null;
  abgeschlossen_von_name: string | null;
  freigabe_nachweis: number | null;
  freigabevermerk: string | null;
  pdf_datei: string;
  pdf_sha256: string;
  vorlage_version: number | null;
};

/** Weg der Freigabe eines Plans (im System durch den Mediziner selbst oder außerhalb von EPM) */
export const FREIGABEWEGE: Record<string, string> = {
  system: "im System", email: "per E-Mail", telefon: "telefonisch", persoenlich: "persönlich", schriftlich: "schriftlich",
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

/** Zahlen und Texte; ``pflicht_erklaerungen`` ist die einzige Liste (siehe Vorlagen › Grenzwerte) */
export type Einstellungen = Record<string, number | string>;
