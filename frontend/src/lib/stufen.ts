/**
 * Stufen der Fensterbreite (S16, Festlegungen 01./02.10.2026): Seiten nutzen die volle Breite und teilen sich in Stufen
 * auf statt nur breiter zu werden. Grenzen wie in index.css (--breakpoint-…), als em abgefragt (px beim Grundwert 16 px;
 * mit größerer Browser-Schrift greifen die Stufen entsprechend früher):
 *   eng    unter 900 px      Startseite 1 Spalte
 *   schmal 900–1439 px      Startseite 2 Spalten, Seitenleiste als Symbole
 *   hd     1440–1919 px     Startseite 3 Spalten
 *   fhd    1920–2559 px     Startseite 4 Spalten
 *   qhd    ab 2560 px       Startseite 5 Spalten
 */
import { useSyncExternalStore } from "react";
import { em } from "./masse";

export type Stufe = "eng" | "schmal" | "hd" | "fhd" | "qhd";

const GRENZEN: [Stufe, number][] = [["qhd", 2560], ["fhd", 1920], ["hd", 1440], ["schmal", 900]];
const ABFRAGEN = typeof window !== "undefined" && window.matchMedia
  ? GRENZEN.map(([stufe, px]) => [stufe, window.matchMedia(`(min-width: ${em(px)})`)] as const)
  : [];

function aktuelleStufe(): Stufe {
  for (const [stufe, abfrage] of ABFRAGEN) if (abfrage.matches) return stufe;
  return "eng";
}

function abonnieren(melden: () => void) {
  for (const [, abfrage] of ABFRAGEN) abfrage.addEventListener("change", melden);
  return () => { for (const [, abfrage] of ABFRAGEN) abfrage.removeEventListener("change", melden); };
}

export function useStufe(): Stufe {
  return useSyncExternalStore(abonnieren, aktuelleStufe, () => "hd" as Stufe);
}

/** Spalten des Rasters der Startseite je Stufe (SU9: 2 Spalten unter 1440 px, 1 unter 900 px) */
export const RASTER_SPALTEN: Record<Stufe, number> = { eng: 1, schmal: 2, hd: 3, fhd: 4, qhd: 5 };

/** ab dieser Stufe (einschließlich) */
export function ab(stufe: Stufe, grenze: Stufe): boolean {
  const reihe: Stufe[] = ["eng", "schmal", "hd", "fhd", "qhd"];
  return reihe.indexOf(stufe) >= reihe.indexOf(grenze);
}

/**
 * Telefon (Festlegung 08.10.2026): unter 768 px Breite – Hauptarbeitsplatz bleibt der PC, am Telefon geht es um
 * schnelles Freigeben von Plänen, kurze Blicke in die Akte und Notizen. Dort: Leiste unten statt Seitenleiste,
 * Listen statt breiter Tabellen, Details vor den Listen.
 */
const MOBIL = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(max-width: 47.99em)") : null;

export function useMobil(): boolean {
  return useSyncExternalStore(
    (melden) => { MOBIL?.addEventListener("change", melden); return () => MOBIL?.removeEventListener("change", melden); },
    () => !!MOBIL?.matches,
    () => false,
  );
}

/** Ohne Seitenspalten (unter 1280 px stehen Liste und Detail untereinander): gewählten Eintrag in den Blick holen. */
export function detailZeigen(testid: string) {
  if (typeof window === "undefined" || window.matchMedia("(min-width: 80em)").matches) return;
  window.requestAnimationFrame(() => {
    document.querySelector(`[data-testid="${testid}"]`)?.scrollIntoView({ block: "start", behavior: "smooth" });
  });
}
