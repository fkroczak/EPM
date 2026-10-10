/** Antwort von GET /api/startseite/ (docs/BACKEND-FUNKTIONEN.md, F09 und S01–S10). */
import type { Kontaktstufe, Termin } from "@/lib/typen";

export type PlanEintrag = { id: number; patient: number; name: string; gueltig_ab: string; status: string; erstellt_am: string;
  erstellt_von: string | null; freigegeben_am: string | null };

export type Wiedereintrag = { patient: number; name: string; nummer: number; ist_test: boolean; letzter_kontakt: string | null;
  stufe: Kontaktstufe };

export type Zuletzt = { bereich: string; bezeichnung: string; objekt_id: number; patient: number; name: string | null;
  zeitpunkt: string; person: string | null; person_id: number | null };

export type Startdaten = {
  termine: { ueberfaellig: Termin[]; heute: Termin[]; naechste_7_tage: Termin[] };
  /** S03: heute und die 6 folgenden Tage */
  woche: { datum: string; anzahl: number; praxistermine: number; feiertag: string | null }[];
  gewichtswarnungen: { patient: number; name: string; nummer: number; gewicht: { kg: number; am: string } | null; prozent: number;
    /** S06: Messungen der letzten 6 Monate */
    verlauf: { am: string; kg: number }[] }[];
  gewicht_schwelle: { prozent: number; monate: number };
  infusionsplaene: { entwuerfe: PlanEintrag[]; aelter_als_grenze: PlanEintrag[]; anzahl_entwuerfe: number; anzahl_aelter: number;
    grenze_monate: number };
  pruefen: { altdokumente: number; altdokumente_gesamt: number; nickelallergie_unbekannt: number; kein_versorger: number;
    kein_kontakt: number; kontakt_bald: number; kontakt_ueberfaellig: number; kontakt_monate: number; kontakt_bald_monate: number;
    kontakt_ueberfaellig_monate: number; erklaerungen_fehlen: number; abschluss_pruefen: number; abschluss_monate: number;
    datenschutz_anfragen: number; datenschutz_ueberfaellig: number; ohne_plan?: number;
    /** Befunde zu alt oder nie erfasst (F120); Grenzen unter Vorlagen › Grenzwerte */
    labor_faellig?: number; bia_faellig?: number; labor_monate?: number; bia_monate?: number };
  /** S04: Kontakt fällig ohne geplanten Termin, in zwei Stufen */
  wiedereinbestellung: { ueberfaellig: Wiedereintrag[]; bald: Wiedereintrag[]; anzahl_ueberfaellig: number; anzahl_bald: number;
    bald_monate: number; ueberfaellig_monate: number };
  zuletzt_eingetragen: Zuletzt[];
  /** S10: nur eigene Einträge */
  zuletzt_von_mir: Zuletzt[];
  /** S01 */
  zahlen: { in_betreuung: number; mit_offenem_termin: number; termine_7_tage: number; praxistermine_7_tage: number;
    termine_ueberfaellig: number; kontakt_ueberfaellig: number; kontakt_bald: number };
  /** F177: „Praxis … informieren“ vor dem nächsten Zeitraum (nur mit „Einträge erfassen“, bis ein Infoblatt erstellt ist) */
  infoblatt?: { von: string; bis: string; rhythmus: "woche" | "monat"; anzahl: number; ohne_ort: number;
    ort: { id: number; wert: string } | null } | null;
  /** F184: „Heute zu tun“ – ohne Testpatienten und abgeschlossene Akten; Bestätigungen und Termine ohne Ort nur mit
   *  „Einträge erfassen“ */
  tagesliste?: Tagesliste;
  /** S08 */
  notfallcodes: { uebrig: number; gesamt: number; eingerichtet: boolean; warnen_ab: number };
  /** O-07: Zustand der Sicherungen (vom Systemagenten), für alle sichtbar */
  sicherung: { zustand: "ok" | "warnung" | "fehler" | "unbekannt"; letzte_am: string | null; verschluesselt: boolean | null;
    titel: string; hinweise: string[] };
};

/** GET /api/meine-akten/ (S05) */
export type MeineAkte = { patient: number; name: string; nummer: number; ist_test: boolean; ist_abgeschlossen: boolean; am: string;
  gewicht: { kg: number; am: string } | null; trend: { richtung: "down" | "up" | "flat" | null; prozent: number; warnung: boolean } | null;
  naechster_termin: { id: number; art: string; faellig_am: string; uhrzeit: string | null; titel: string } | null; plan_entwurf: boolean };
export type MeineAkten = { merkliste: MeineAkte[]; zuletzt: MeineAkte[] };

/** F186: fehlende Angaben, gezählt je Regel (Akten) */
export type LueckenArt = "hausarzt" | "telefon" | "gewicht_fehlt" | "diagnose" | "termin_ort";

export type Tagesliste = {
  termine_heute: Termin[];
  /** Rückrufe und Wiedervorlagen, heute fällig oder überfällig */
  rueckrufe: Termin[]; rueckrufe_anzahl: number; rueckrufe_ueberfaellig: number;
  kontakt_ueberfaellig: number; kontakt_monate: number;
  plaene_pruefen: number;
  fehlende_angaben: Record<LueckenArt, number>; gewicht_fehlt_monate: number;
  /** F185: Praxistermine der nächsten zwei Wochen ohne Terminbestätigung */
  bestaetigung_fehlt: Termin[];
  /** Praxistermine ohne Ort (fehlen auf dem Infoblatt an die Praxis) */
  ohne_ort: Termin[];
};
