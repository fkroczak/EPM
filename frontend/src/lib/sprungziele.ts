/**
 * Ein Klick auf einen offenen Punkt oder einen Termin führt direkt an die Stelle, an der er erledigt wird
 * (Wunsch 11.10.2026): fehlende Angaben öffnen die Stammdaten, „Kein Laborbefund“ den Reiter Labor, ein Termin
 * seinen Dialog usw. Die Akte wertet ``state.oeffnen`` bzw. ``state.termin`` aus (seiten/akte/Akte.tsx).
 */
import type { HinweisArt } from "./typen";

/** Was die Akte nach dem Sprung tut: Dialog öffnen oder an eine Karte der Übersicht scrollen */
export type AktenAktion = "stammdaten" | "gewicht" | "termine" | "gewichtsverlauf";

export type Sprungziel = { pfad: string; state: { oeffnen?: AktenAktion; termin?: number; zeit: number } };

type Ziel = { reiter: string; oeffnen?: AktenAktion; titel: string };

const ZIELE: Record<HinweisArt | "nickelallergie", Ziel> = {
  gewicht: { reiter: "", oeffnen: "gewichtsverlauf", titel: "Gewichtsverlauf ansehen" },
  gewicht_fehlt: { reiter: "", oeffnen: "gewicht", titel: "Gewicht erfassen" },
  plan: { reiter: "plaene", titel: "Zu den Infusionsplänen" },
  ohne_plan: { reiter: "plaene", titel: "Zu den Infusionsplänen" },
  versorger: { reiter: "", oeffnen: "stammdaten", titel: "Versorger in den Stammdaten erfassen" },
  hausarzt: { reiter: "", oeffnen: "stammdaten", titel: "Hausarzt in den Stammdaten erfassen" },
  telefon: { reiter: "", oeffnen: "stammdaten", titel: "Telefon in den Stammdaten erfassen" },
  nickelallergie: { reiter: "", oeffnen: "stammdaten", titel: "Nickelallergie in den Stammdaten erfassen" },
  kontakt: { reiter: "kontakte", titel: "Zu den Kontakten" },
  labor: { reiter: "labor", titel: "Zum Labor" },
  bia: { reiter: "bia", titel: "Zur BIA" },
  diagnose: { reiter: "diagnosen", titel: "Zu den Diagnosen" },
  termin_ort: { reiter: "", oeffnen: "termine", titel: "Zu den Terminen" },
};

export function hinweisZiel(patientId: number, art: HinweisArt | "nickelallergie"): Sprungziel & { titel: string } {
  const z = ZIELE[art] ?? { reiter: "", titel: "Akte öffnen" };
  return {
    pfad: `/patienten/${patientId}${z.reiter ? `/${z.reiter}` : ""}`,
    // ``zeit`` macht jeden Klick neu – auch ein zweiter Klick auf denselben Punkt öffnet den Dialog wieder
    state: { oeffnen: z.oeffnen, zeit: Date.now() },
    titel: z.titel,
  };
}

export function terminZiel(patientId: number, terminId: number): Sprungziel {
  return { pfad: `/patienten/${patientId}`, state: { termin: terminId, zeit: Date.now() } };
}
