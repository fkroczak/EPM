/**
 * Aufteilung der Browsertests auf mehrere CI-Rechner (15.11.2026, Laufzeit der CI unter 5 Minuten).
 *
 * Jeder Teil startet einen eigenen, frischen Stack (werkzeuge/ci-stack.sh) und führt seine Dateien in alphabetischer
 * Reihenfolge aus – wie zuvor der Gesamtlauf: „aa-import“ zuerst (Übernahme nur ohne echte Akten), danach
 * „zz-neustart“ (Nachweis nach Neustart), „zzz-sicherung“ (stellt eine Sicherung wieder her) und „zzzz-leeren“ (leert
 * die Datenbank) zuletzt. „zz-neustart“ läuft in jedem Teil und prüft dort die Ergebnisse der Dateien dieses Teils.
 *
 * Neue Spec-Datei: hier einem Teil zuordnen – sonst bricht jeder geteilte Lauf mit einer Meldung ab.
 * Sekunden: gemessene Laufzeit im CI (zum Ausgleichen der Teile).
 */
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const TEILE: Record<string, string[]> = {
  "1": ["system.spec.ts"],
  "2": ["zzz-sicherung.spec.ts"],
  "3": ["audit-firmen.spec.ts"],
  "4": ["scans.spec.ts"],
  "12": ["scans-verbessern.spec.ts"],
  "5": ["admin.spec.ts", "konto.spec.ts", "passkey.spec.ts"],
  "6": ["akte.spec.ts", "start.spec.ts"],
  "7": ["datenschutz.spec.ts", "oberflaeche.spec.ts"],
  // dokumentvorlagen nach aa-import: Fassungen zählen erst nach dem Import weiter
  "8": ["aa-import.spec.ts", "patienten.spec.ts", "dokumentvorlagen.spec.ts"],
  "9": ["plaene.spec.ts", "dokumente.spec.ts", "dokumente-falsch.spec.ts", "kalender.spec.ts"],
  "10": ["praxiswuensche.spec.ts", "mobil.spec.ts", "touch.spec.ts", "anmeldung.spec.ts"],
  "11": ["aktenansicht.spec.ts", "versorger.spec.ts", "testdaten-befunde.spec.ts", "korrespondenz.spec.ts",
         "layout.spec.ts", "infusionsplaene.spec.ts", "pdf-ausgaben.spec.ts", "firmen.spec.ts", "medikamente.spec.ts",
         "zzzz-leeren.spec.ts"],
};

/** Laufen in jedem Teil bzw. nur auf Wunsch (Bildschirmfotos beim manuellen Start). */
export const IMMER = ["zz-neustart.spec.ts"];
export const NUR_AUF_WUNSCH = ["bildschirmfotos.spec.ts", "bildschirmfotos-mobil.spec.ts"];

const ORDNER = dirname(fileURLToPath(import.meta.url));

/** Dateien des Teils (mit „zz-neustart“); wirft, wenn eine Spec-Datei keinem oder mehreren Teilen zugeordnet ist. */
export function dateienDesTeils(teil: string): string[] {
  const vorhanden = readdirSync(ORDNER).filter((d) => d.endsWith(".spec.ts"));
  const zugeordnet = Object.values(TEILE).flat();
  const doppelt = zugeordnet.filter((d, i) => zugeordnet.indexOf(d) !== i);
  const fehlt = vorhanden.filter((d) => !zugeordnet.includes(d) && !IMMER.includes(d) && !NUR_AUF_WUNSCH.includes(d));
  const unbekannt = zugeordnet.filter((d) => !vorhanden.includes(d));
  if (doppelt.length || fehlt.length || unbekannt.length) {
    throw new Error(`e2e/teile.ts passt nicht zu den Spec-Dateien – doppelt: ${doppelt.join(", ") || "-"}; `
      + `keinem Teil zugeordnet: ${fehlt.join(", ") || "-"}; nicht vorhanden: ${unbekannt.join(", ") || "-"}`);
  }
  if (!TEILE[teil]) throw new Error(`EPM_E2E_TEIL=${teil}: unbekannt (vorhanden: ${Object.keys(TEILE).join(", ")})`);
  return [...TEILE[teil], ...IMMER].map((d) => join(ORDNER, d));
}

/** Läuft die Spec-Datei in diesem Lauf? Ohne EPM_E2E_TEIL (Gesamtlauf, Entwickler-Rechner) laufen alle. */
export function laeuft(datei: string): boolean {
  const teil = process.env.EPM_E2E_TEIL;
  return !teil || (TEILE[teil] ?? []).includes(datei);
}
