/** Einmal je Lauf: jede Rolle meldet sich an (Kennwort + Notfall-Code); die Sitzung nutzen die Tests weiter. */
import { mkdirSync, rmSync } from "node:fs";
import { request } from "@playwright/test";
import { BASIS, KENNWORT, naechsterNotfallcode, zustand } from "./hilfen";
import type { Rolle } from "./hilfen";

const KONTEN: [Rolle, string][] = [
  ["mediziner", "e2e.mediziner"],
  ["mitarbeiter", "e2e.mitarbeiter"],
  ["betrachter", "e2e.betrachter"],
  ["admin", "e2e.admin"],
  ["test", "e2e.test"],
];

export default async function globalSetup() {
  rmSync("e2e/.auth", { recursive: true, force: true });
  mkdirSync("e2e/.auth", { recursive: true });
  for (const [rolle, benutzer] of KONTEN) {
    const ctx = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true });
    await ctx.get("/api/auth/status/");
    // Django erneuert das CSRF-Token bei der Anmeldung – daher vor jedem Schritt neu lesen
    const kopf = async () => ({
      "X-CSRFToken": (await ctx.storageState()).cookies.find((c) => c.name === "epm_csrf")?.value ?? "",
      Referer: `${BASIS}/`,
      Origin: BASIS,
    });
    const a = await ctx.post("/api/auth/anmelden/", { data: { benutzername: benutzer, kennwort: KENNWORT }, headers: await kopf() });
    if (!a.ok()) throw new Error(`Anmeldung ${benutzer}: ${a.status()} ${await a.text()}`);
    const b = await ctx.post("/api/auth/2fa/", { data: { code: naechsterNotfallcode(benutzer) }, headers: await kopf() });
    const s = await b.json();
    if (s.schritt !== "fertig") throw new Error(`2FA ${benutzer}: ${JSON.stringify(s)}`);
    await ctx.storageState({ path: zustand(rolle) });
    await ctx.dispose();
  }
}
