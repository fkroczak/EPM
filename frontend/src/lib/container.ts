/**
 * Zustand eines Containers bewerten (Systemverwaltung, Dienste, Ampel „Dienste“). Einmal-Container wie ki-init laufen
 * bei jedem Start kurz und beenden sich: mit Exit-Code 0 ist das „erledigt“ (gut), nur ein anderer Code ist ein Fehler.
 */
export type ContainerZeile = { dienst: string; zustand: string; gesundheit: string; status?: string; exitcode?: number | null };

// Einmal-Container (restart: "no"), deren Ende mit 0 der Normalfall ist
export const EINMAL_CONTAINER = new Set(["ki-init"]);

function exitCode(c: ContainerZeile): number | null {
  if (typeof c.exitcode === "number") return c.exitcode;
  const m = /^Exited \((\d+)\)/.exec(c.status ?? "");   // ältere Systemagenten liefern nur den Status-Text
  return m ? Number(m[1]) : null;
}

export function containerBewertung(c: ContainerZeile): { gut: boolean; text: string } {
  if (EINMAL_CONTAINER.has(c.dienst) && c.zustand === "exited") {
    const code = exitCode(c);
    return code === 0 ? { gut: true, text: "erledigt" } : { gut: false, text: `fehlgeschlagen${code != null ? ` (Code ${code})` : ""}` };
  }
  const gut = c.zustand === "running" && (!c.gesundheit || c.gesundheit === "healthy");
  const text = (c.zustand === "running" ? "läuft" : c.zustand) + (c.gesundheit ? ` · ${c.gesundheit === "healthy" ? "gesund" : c.gesundheit}` : "");
  return { gut, text };
}
