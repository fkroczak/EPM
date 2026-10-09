/** Datenformen der API (siehe docs/BACKEND-FUNKTIONEN.md). */
import type { Darstellung } from "./darstellung";

export type Recht =
  | "akten_lesen" | "eintraege_erfassen" | "akten_bearbeiten" | "dokumente_umhaengen" | "dokumente_loeschen"
  | "plaene_anlegen" | "plaene_freigeben" | "plaene_abschliessen"
  | "datenschutz_bearbeiten" | "datenschutz_entscheiden" | "akten_loeschen"
  | "akten_abschliessen" | "akten_wieder_oeffnen" | "versorger_pflegen" | "vorlagen_pflegen" | "audit_lesen"
  | "benutzer_verwalten" | "backup_verwalten" | "testdaten_zuruecksetzen" | "testdaten_sehen" | "system_verwalten"
  | "altdaten_importieren" | "berichte_freigeben" | "scans_bearbeiten";

/** Kacheln der Startseite (S11): klinische und – mit dem jeweiligen Recht – die der Administration (S12–S14) */
export type KartenId =
  | "termine" | "wieder" | "meine" | "gewicht" | "plaene" | "pruefen" | "aktiv"
  | "sicherung" | "server" | "updates" | "konten" | "angemeldet" | "hinweis" | "zugriffe" | "testumgebung";
/** Größe im Raster: Spalten × Zeilen, je 1 oder 2 */
export type Karte = { id: KartenId; sichtbar: boolean; breite: 1 | 2; hoehe: 1 | 2 };

export type Ich = {
  id: number;
  benutzername: string;
  anzeigename: string;
  titel: string;
  vorname: string;
  nachname: string;
  kuerzel: string | null;
  funktion: string;
  rolle: "betrachter" | "mitarbeiter" | "mitarbeiter_plus" | "mediziner" | "admin" | "keine";
  ist_test: boolean;
  darstellung: Partial<Darstellung>;
  /** karten: vollständig, in Anzeigereihenfolge (fehlende ergänzt der Server mit dem Standard der Rolle);
   *  notfallhinweis_bei: Hinweis zu den Notfall-Codes bei dieser Anzahl ausgeblendet (S08) */
  startseite: { karten: Karte[]; notfallhinweis_bei?: number | null; zweifaktorhinweis_aus?: boolean };
  /** Spaltenteiler je Seite und Fensterstufe (S17): {"akte_uebersicht@fhd": [0.6667]} */
  aufteilung: Record<string, number[]>;
  /** Größe der Karten je Seite (Akte, System): {"akte_uebersicht": {"gewicht": {breite: 2, hoehe: 0}}} */
  bereiche: Record<string, Record<string, Bereichsgroesse>>;
  /** Authenticator-App eingerichtet / für dieses Konto Pflicht (sonst freiwillig, Festlegung 02.10.2026) */
  zweiter_faktor: boolean;
  zweiter_faktor_pflicht: boolean;
  /** womit bestätigt werden kann (Festlegung 08.10.2026): Code aus der App und/oder Passkey */
  authenticator?: boolean;
  passkey?: boolean;
  /** Testbenutzer ausgeblendet (gesperrt, aus allen Listen) – Festlegung 03.10.2026 */
  ausgeblendet_am?: string | null;
  rechte: Recht[];
  /** Admins: Patientendaten nur bei Testpatienten schreiben (echte Akten nur lesen) */
  schreibt_nur_testpatienten: boolean;
  /** Menüpunkt „Import“ nach der Übernahme ausgeblendet (Administration › System, Festlegung 03.10.2026, U32) */
  import_ausgeblendet?: boolean;
};

/** Breite in Spalten des Rasters (1–5), Höhe in Rasterzeilen (0 = automatisch nach Inhalt, sonst 1–4) */
export type Bereichsgroesse = { breite: number; hoehe: number };

export type Schritt = "anmelden" | "kennwort_aendern" | "2fa_einrichten" | "2fa" | "fertig";

export type Status = {
  schritt: Schritt;
  benutzer?: Ich;
  organisation?: { name: string; anschrift: string };
  notfallcodes?: string[];
  /** Passkeys auf diesem Server möglich? (nur über den Namen mit Zertifikat der eigenen CA) */
  passkey?: { verfuegbar: boolean; rp_id: string; grund: string };
  /** im Schritt „2fa“: womit sich die Person anmelden kann */
  faktoren?: { authenticator: boolean; passkey: boolean };
  /** gerade eingerichteter Passkey */
  passkey_neu?: PasskeyEintrag;
};

export type PasskeyEintrag = { id: number; name: string; angelegt_am: string; zuletzt_am: string | null; synchronisiert: boolean };

export const ROLLEN: Record<string, string> = {
  betrachter: "Betrachter",
  mitarbeiter: "Mitarbeiter",
  mitarbeiter_plus: "Mitarbeiter (erweitert)",
  mediziner: "Mediziner",
  admin: "Admin",
  keine: "Keine Berechtigung",
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

/** Kontakt fällig in zwei Stufen (S04) */
export type Kontaktstufe = "bald" | "ueberfaellig";

export type Kennzahlen = {
  gewicht: { kg: number; am: string } | null;
  trend: Trend | null;
  letzter_kontakt: string | null;
  kontakt_stufe: Kontaktstufe | null;
  termin_woche: boolean;
  hinweise: { art: HinweisArt; text: string; stufe?: Kontaktstufe }[];
  /** weggeklickte Hinweise dieser Akte (F119) – sie erscheinen nicht in „hinweise“ */
  hinweise_stumm?: HinweisArt[];
  /** letzter Laborbefund bzw. letzte BIA-Messung mit Fälligkeit (F120) */
  labor?: { am: string | null; alt: boolean };
  bia?: { am: string | null; alt: boolean };
  /** nur in der Patientenliste (breite Spalten, S16) */
  naechster_termin?: { id: number; art: string; faellig_am: string; uhrzeit: string | null; titel: string } | null;
  plan?: { gueltig_ab: string | null; alt: boolean; entwurf: boolean } | null;
  kein_plan?: boolean;
  erklaerungen_fehlen?: ErklaerungsArt[];
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
/** beginn: Abschlussdatum – oder der Tag des letzten Kontakts, wenn der später liegt */
export type Aufbewahrung = { jahre: number; beginn: string | null; regulaer_bis: string | null; verlaengert_bis: string | null;
  grund: string; bis: string | null; abgelaufen: boolean };

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

/** name: null bei einer eingeschränkten Akte, wenn die angemeldete Person keine Einsicht nehmen dürfte */
type AktenZeile = { id: number; nummer: number; name: string | null; ist_test: boolean };
export type DatenschutzUebersicht = {
  anfragen_offen: Datenschutzanfrage[];
  anfragen_ueberfaellig: number;
  /** offene Anfragen zu eingeschränkten Akten, die diese Person nicht sieht */
  anfragen_verborgen: number;
  aufbewahrung_abgelaufen: (AktenZeile & { abgeschlossen_am: string; aufbewahrung_bis: string; verlaengert: boolean; eingeschraenkt: boolean })[];
  aufbewahrung_laeuft_ab: (AktenZeile & { abgeschlossen_am: string; aufbewahrung_bis: string; verlaengert: boolean; eingeschraenkt: boolean })[];
  eingeschraenkt: (AktenZeile & { am: string; von: string | null; grund: string | null })[];
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
  /** Versichertendaten (F118): Art, Name der Versicherung („krankenkasse“) und Versichertennummer */
  versicherungsart: "" | "gkv" | "pkv" | "selbstzahler" | "sonstige";
  krankenkasse: string;
  versichertennummer: string;
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
    /** offener Entwurf eines Infusionsplans (Aktenkopf „Entwurf fortsetzen“, 08.10.2026) */
    plan_entwurf?: { id: number; erstellt_am: string } | null;
    /** „Kein Infusionsplan nötig“ bestätigt (Ergänzung zur Fehlerliste 02.10.2026) */
    kein_plan?: { grund: string; am: string | null; von: string | null } | null;
    naechster_termin: {
      id: number; art: string; titel: string; faellig_am: string; uhrzeit: string | null; ort: string | null; bei: string;
    } | null;
    versionen: Record<"diagnose" | "therapie" | "empfehlung" | "bemerkung", Versionskopf>;
    /** Schnellerfassung (S02): Zeitpunkt des letzten gültigen Kontakts */
    letzter_kontakt: string | null;
    /** Merkliste der angemeldeten Person (S05) */
    gemerkt: boolean;
    zaehler: { kontakte: number; gewichte: number; dokumente: number; termine_offen: number; infusionsplaene: number;
      bezugspersonen: number; aerzte: number; erklaerungen: number;
      /** eigene Reiter seit 07.10.2026 (F121) */
      diagnosen: number; laborbefunde: number; bia_messungen: number; berichte: number };
  } | null;
};

/** PDF zum Anhängen an die E-Mails der Schreiben (F174) */
export type Anlage = {
  id: number;
  name: string;
  beschreibung: string;
  dateiname: string;
  groesse: number;
  aktiv: boolean;
  reihenfolge: number;
  mitgeliefert: boolean;
  hochgeladen_am: string;
  hochgeladen_von: string | null;
};

/** Text der E-Mail eines Schreibens (F172), im Dialog anpassbar */
export type Mailtext = { an: string; betreff: string; text: string; dateiname: string };

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
  /** Ausblenden mit „×“ im Kalender (F142): heute ausgeblendet, Frist oder „nicht mehr nötig“, Grund, wer und wann */
  ausgeblendet?: boolean;
  ausgeblendet_bis?: string | null;
  ausgeblendet_dauerhaft?: boolean;
  ausblende_grund?: string;
  ausgeblendet_am?: string | null;
  ausgeblendet_von_name?: string | null;
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
  /** kurzer Hinweis, z. B. „reines Taurolidin 2 %“ (F111) */
  hinweis: string;
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
  herkunft: "upload" | "altsystem" | "system" | "scan";
  hochgeladen_am: string;
  hochgeladen_von_name: string | null;
  /** erkannter Text vorhanden (aus „Scans“, F163) – lesen über dokumente/{id}/text/ */
  hat_text?: boolean;
  /** „Text erkennen“ (F170): letzter Auftrag */
  erkennung?: { id: number; status: "wartet" | "laeuft" | "fertig" | "fehler"; schritt: string; fehler: string;
    angefordert_am: string; beendet_am: string | null; seiten: number | null } | null;
  text_erkennbar?: { moeglich: boolean; grund: string };
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
  /** Infusionstage je Beutelart (F110): PE (Mischbeutel), Zusatzvolumen, infusionsfreie Tage */
  tage_pro_woche: number | null;
  zusatz_tage_pro_woche: number | null;
  freie_tage_pro_woche: number | null;
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
  /** aus dem Altsystem übernommene Pläne: ohne Freigabe im Sinne des EPM und ohne gespeicherte PDF */
  herkunft: "epm" | "altsystem";
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
  zweiter_faktor_pflicht: boolean;
  /** womit bestätigt werden kann (Festlegung 08.10.2026): Code aus der App und/oder Passkey */
  authenticator?: boolean;
  passkey?: boolean;
  /** Testbenutzer ausgeblendet (gesperrt, aus allen Listen) – Festlegung 03.10.2026 */
  ausgeblendet_am?: string | null;
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


// ================================================================= Wünsche aus der Praxis (06.10.2026)
export const VERSICHERUNGSARTEN: Record<string, string> = {
  "": "nicht erfasst",
  gkv: "GKV (gesetzlich)",
  pkv: "PKV (privat)",
  selbstzahler: "Selbstzahler",
  sonstige: "Sonstige",
};

/** Zusatzkennzeichen der Diagnose: G gesichert, V Verdacht, Z Zustand nach, A Ausschluss (F117) */
export const DIAGNOSE_KENNZEICHEN: Record<string, string> = {
  G: "G – gesichert",
  V: "V – Verdacht auf",
  Z: "Z – Zustand nach",
  A: "A – Ausschluss von",
};

export type Diagnose = {
  id: number;
  patient: number;
  bezeichnung: string;
  icd_code: string;
  kennzeichen: "G" | "V" | "Z" | "A";
  kennzeichen_name: string;
  anzeige: string;
  seit: string | null;
  notiz: string;
  reihenfolge: number;
  aktiv: boolean;
  beendet_am: string | null;
  angelegt_am: string;
  angelegt_von_name: string | null;
};

export type Diagnosevorlage = { id: number; icd_code: string; bezeichnung: string; aktiv: boolean; anzeige: string };

export const LABORGRUPPEN: Record<string, string> = {
  transaminasen: "Transaminasen",
  niere: "Nierenwerte",
  eisen: "Eisenhaushalt",
  eiweiss_fett: "Eiweiß- und Fettstoffwechsel",
  elektrolyte: "Elektrolyte",
  spurenelemente: "Spurenelemente",
  haematologie: "Hämatologie",
  vitamine: "Vitamine",
  knochen: "Knochenstoffwechsel",
  pankreas: "Pankreasenzyme",
  diabetes: "Blutzucker / Diabetes",
  schilddruese: "Schilddrüse",
  tumormarker: "Tumormarker",
  genetik: "Genetische Parameter",
  sonstiges: "Weitere Parameter",
};

export type Laborparameter = {
  id: number;
  gruppe: string;
  gruppe_name: string;
  name: string;
  kurzname: string;
  einheit: string;
  referenz_von: number | null;
  referenz_bis: number | null;
  reihenfolge: number;
  aktiv: boolean;
  in_befunden: number;
  /** weitere Schreibweisen für die Werterkennung in „Scans“ (F166), durch Komma getrennt */
  suchbegriffe?: string;
};

export type Laborwert = {
  id?: number;
  parameter: number | null;
  freitext_name: string;
  bezeichnung?: string;
  wert: number | string | null;
  wert_text: string;
  anzeige_wert?: string;
  einheit: string;
  referenz_von: number | null;
  referenz_bis: number | null;
  ausserhalb?: "hoch" | "niedrig" | null;
  bemerkung: string;
  reihenfolge?: number;
  gruppe?: string | null;
  gruppe_name?: string | null;
};

export type Laborbefund = {
  id: number;
  patient: number;
  patient_name?: string;
  abgenommen_am: string;
  labor: string;
  beurteilung: string;
  dokument: number | null;
  werte: Laborwert[];
  anzahl_werte: number;
  erfasst_am: string;
  erfasst_von_name: string | null;
};

export type BiaMessung = {
  id: number;
  patient: number;
  gemessen_am: string;
  gewicht_kg: number | null;
  bcm_kg: number | null;
  fettmasse_kg: number | null;
  ecw_prozent: number | null;
  koerperwasser_l: number | null;
  bmi: number | null;
  bmi_berechnet: number | null;
  magermasse_kg: number | null;
  beurteilung: string;
  dokument: number | null;
  gewichtsmessung: number | null;
  erfasst_am: string;
  erfasst_von_name: string | null;
};

export type Bericht = {
  id: number;
  patient: number;
  patient_name?: string;
  status: "entwurf" | "freigegeben";
  status_name: string;
  art: number | null;
  art_name: string | null;
  titel: string;
  datum: string;
  empfaenger: string;
  inhalt: string;
  erstellt_am: string;
  erstellt_von_name: string | null;
  freigegeben_am: string | null;
  freigegeben_von_name: string | null;
  freigabevermerk: string | null;
  dokument: number | null;
  pdf_sha256: string;
  vorlage_version: number | null;
};


// ================================================================= Hinweise stummschalten (07.10.2026, F119)
export type HinweisArt = "gewicht" | "plan" | "ohne_plan" | "versorger" | "kontakt" | "labor" | "bia";

/** Fristen, die beim Wegklicken zur Wahl stehen; „nicht mehr nötig“ ist die vierte Möglichkeit */
export const RUHE_FRISTEN = [3, 6, 12] as const;

export type Hinweisruhe = {
  id: number;
  art: HinweisArt;
  art_name: string;
  /** leer = nicht mehr nötig, bis jemand es zurücknimmt */
  bis: string | null;
  grund: string;
  laeuft: boolean;
  gesetzt_am: string;
  gesetzt_von_name: string | null;
  aufgehoben_am: string | null;
  aufgehoben_von_name: string | null;
};

// ================================================================= Scans (F160 ff.)
/** Wort der Erkennung: Text, x, y, Breite, Höhe (Pixel der aufbereiteten Seite), Sicherheit 0–1, andere Lesart */
export type ScanWort = [string, number, number, number, number, number, string?];
export type ScanStueck = { q: "p" | "t" | "m" | "d"; w: ScanWort[] };
export type ScanErgebnis = {
  breite: number; hoehe: number; verfahren?: string[]; reihen: ScanStueck[][];
  zeit?: Record<string, number | null> | number; bereiche?: number[][];
};
export type SeitenEinstellungen = {
  ecken: "auto" | "aus" | number[][];
  glaetten: "auto" | "ein" | "aus";
  drehung: 0 | 90 | 180 | 270 | null;
  schraeglage: "auto" | "aus" | number;
  schatten: boolean;
  modus: "graustufen" | "farbe" | "sw";
  kontrast: number;
  helligkeit: number;
  textebene?: boolean;
};
export type ScanSeite = {
  id: number; nr: number; status: "wartet" | "fertig" | "fehler"; fehler: string;
  roh_breite: number; roh_hoehe: number; herkunft: "pdf" | "bild"; kamera: boolean;
  einstellungen: Partial<SeitenEinstellungen>;
  info: { ecken?: number[][]; ecken_quelle?: "auto" | "hand"; foto?: boolean; drehung?: number; drehung_quelle?: string;
    schraeglage?: number; geglaettet?: boolean; textebene?: boolean; skala?: number; entrauscht?: number;
    texthoehe?: number | null;
    /** nach Abbrüchen des Dienstes sparsamer erkannt: 1 = ohne Glätten, kleinere Zeilensuche; 2 = nur Tesseract */
    sparstufe?: number };
  auftrag: { art: "seite" | "bereich"; box?: number[]; staerke?: number } | null;
  breite: number; hoehe: number; ergebnis: ScanErgebnis | Record<string, never>; text: string;
  sicherheit: number | null; unsicher: number; erkannt_am: string | null; textebene_vorhanden: boolean;
};
export type ScanLaborwert = {
  parameter: number | null; parameter_name: string | null; erkannt_als: string; zuordnung: "genau" | "aehnlich" | "frei";
  freitext_name: string; wert: string | null; wert_text: string; einheit: string; einheit_gelesen: string;
  referenz_von: string | null; referenz_bis: string | null; markierung: string; seite: number; box: number[] | null;
  zeile: string; sicherheit: number; hinweise: string[]; vorschlag: boolean;
  umrechnung?: { von: string; faktor: string; wert_gelesen: string };
};
export type ScanBiaWert = { wert: string; einheit: string; erkannt_als: string; seite: number; box: number[] | null;
  sicherheit: number; vorschlag: boolean; hinweise?: string[] };
export type ScanDiagnose = { bezeichnung: string; icd_code: string; kennzeichen: "G" | "V" | "Z" | "A"; zeile: string;
  seite: number; box: number[] | null; sicherheit: number; vorschlag: boolean };
export type ScanAuswertung = {
  arten?: ("labor" | "bia" | "arztbrief")[];
  datum?: string | null; datum_quelle?: string;
  labor?: { name: string; werte: ScanLaborwert[] };
  bia?: { werte: Partial<Record<"gewicht_kg" | "bcm_kg" | "fettmasse_kg" | "ecw_prozent" | "koerperwasser_l" | "bmi", ScanBiaWert>>;
    weitere: { name: string; wert: string; einheit: string; seite: number; box: number[] | null }[] };
  diagnosen?: ScanDiagnose[];
  abschnitte?: Partial<Record<"diagnosen" | "anamnese" | "befund" | "therapie" | "verlauf" | "procedere", string>>;
  originale?: { name: string; mime: string }[];
};
export type ScanVorschlag = { id: number; nummer: number; name: string; geburtsdatum: string | null; ist_test: boolean;
  abgeschlossen: boolean; punkte: number; grund: string };
export type ScanZeile = {
  id: number; titel: string; originalname: string; mime: string; groesse: number;
  status: "wartet" | "laeuft" | "fertig" | "fehler"; fortschritt: number; schritt: string; fehler: string;
  hochgeladen_am: string; hochgeladen_von_name: string | null; eigener: boolean; ist_test: boolean;
  laeuft_ab_am: string; hoechst_bis: string; verlaengerbar: boolean; verlaengert_anzahl: number; seiten_anzahl: number;
  vorschau: string | null; sicherheit: number | null; unsicher: number; arten: string[]; dokumentdatum: string | null;
  verfahren: string[]; belegt: number; erkannt_am: string | null; dauer_s: number | null;
  /** Arbeitskopie eines Dokuments der Akte („Werte übernehmen“, F171) */
  quelle?: { dokument: number; titel: string; patient: { id: number; nummer: number; nachname: string; vorname: string;
    geburtsdatum: string | null; ist_test: boolean } } | null;
};
export type Scan = ScanZeile & { text: string; seiten: ScanSeite[]; auswertung: ScanAuswertung; vorschlaege?: ScanVorschlag[] };
export type ScansStand = {
  offen: number; laufend: number; in_arbeit: number; wartend: number; abbrueche: number; fehler: number; gesamt: number; laeuft_bald_ab: number; belegt: number; grenze: number;
  prozent: number; anzahl_grenze: number; anzahl_alle: number; frist_tage: number; hoechst_tage: number;
  verlaengerung_tage: number; max_mb: number; max_seiten: number; upload_max_mb: number;
  verfahren?: { tesseract: { bereit: boolean; text: string }; ocrmypdf?: { bereit: boolean; text: string }; paddle: { bereit: boolean; glaetten: boolean; text: string; sparsam?: boolean; speicher_mb?: number | null } };
  dienst?: { gestartet: string; lebenszeichen: string; laeuft: boolean; bearbeitet: number; threads: string;
    /** Speicher des Containers „ocr“ in Bytes (cgroup v2), Höchststand seit dem Start */
    speicher?: { belegt: number; hoechst: number | null; grenze: number | null } | null } | null;
};
