/** Hilfen für die Browsertests: Anmeldung, TOTP-Codes, API-Zugriff mit Sitzung und CSRF. */
import { createHmac } from "node:crypto";
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { expect, request } from "@playwright/test";
import type { APIRequestContext, BrowserContext, CDPSession, Page } from "@playwright/test";

export const BASIS = process.env.EPM_URL ?? "https://localhost";
export const KENNWORT = "E2E-Kennwort-sicher-2026";
export const SCHLUESSEL_HEX = "3132333435363738393031323334353637383930";
export type Rolle = "mediziner" | "mitarbeiter" | "betrachter" | "admin" | "test";

export const zustand = (rolle: Rolle) => `e2e/.auth/${rolle}.json`;

/** Ohne Anmeldung. Wichtig: Innerhalb eines Tests übernimmt Playwright den storageState aus `test.use` auch für
 *  `request.newContext()` und `browser.newContext()`. Ohne diese Angabe würde eine „frische“ Anmeldung in der Sitzung
 *  der Rolle des Tests stattfinden – Django beendet dann deren Sitzung (Benutzerwechsel in derselben Sitzung). */
export const OHNE_ANMELDUNG = { cookies: [], origins: [] };

const ZAEHLER = "e2e/.auth/notfallcodes.json";

/** Jeder Notfall-Code gilt einmal; vergeben der Reihe nach je Konto (vorbereiten.py legt 40 je Konto an). */
export function naechsterNotfallcode(benutzer: string) {
  const stand: Record<string, number> = existsSync(ZAEHLER) ? JSON.parse(readFileSync(ZAEHLER, "utf8")) : {};
  const n = stand[benutzer] ?? 0;
  stand[benutzer] = n + 1;
  mkdirSync("e2e/.auth", { recursive: true });
  writeFileSync(ZAEHLER, JSON.stringify(stand));
  if (n >= 40) throw new Error(`Keine Notfall-Codes mehr für ${benutzer}`);
  return `e2e${String(n).padStart(4, "0")}code`;
}

function hotp(schluessel: Buffer, zaehler: number) {
  const puffer = Buffer.alloc(8);
  puffer.writeBigUInt64BE(BigInt(zaehler));
  const h = createHmac("sha1", schluessel).update(puffer).digest();
  const o = h[h.length - 1] & 0xf;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

export function totpHex(hex: string, zeit = Date.now()) {
  return hotp(Buffer.from(hex, "hex"), Math.floor(zeit / 30_000));
}

export function base32(text: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const z of text.replace(/=+$/, "").toUpperCase()) {
    const i = alphabet.indexOf(z);
    if (i < 0) continue;
    bits += i.toString(2).padStart(5, "0");
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

export function totpBase32(geheim: string, zeit = Date.now()) {
  return hotp(base32(geheim), Math.floor(zeit / 30_000));
}

/** Anmeldung über die Oberfläche (Benutzername, Passwort, Code) */
export async function anmeldenUI(page: Page, benutzer: string, code: string, kennwort = KENNWORT) {
  await page.goto("/");
  await page.getByLabel("Benutzername").fill(benutzer);
  await page.getByLabel("Passwort").fill(kennwort);
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect(page.getByRole("heading", { name: "Bestätigungscode" })).toBeVisible();
  await page.getByLabel("Code").fill(code);
  await page.getByRole("button", { name: "Anmelden" }).click();
  // erst zurück, wenn die Anmeldung fertig ist – sonst trifft ein sofortiges page.goto() noch die Anmeldeseite
  await expect(page.getByRole("navigation", { name: "Hauptnavigation" })).toBeVisible();
}

async function csrfVon(ctx: APIRequestContext): Promise<string> {
  const zustand = await ctx.storageState();
  return zustand.cookies.find((c) => c.name === "epm_csrf")?.value ?? "";
}

/** API-Zugriff mit gespeicherter Sitzung einer Rolle (für Testdaten und Prüfungen im Hintergrund) */
export async function apiAls(rolle: Rolle) {
  const ctx = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true, storageState: zustand(rolle) });
  const kopf = async () => ({ "X-CSRFToken": await csrfVon(ctx), Referer: `${BASIS}/`, Origin: BASIS });
  const pruefe = async (antwort: Awaited<ReturnType<APIRequestContext["get"]>>) => {
    if (!antwort.ok()) throw new Error(`${antwort.url()} → ${antwort.status()}: ${await antwort.text()}`);
    return antwort.status() === 204 ? null : antwort.json();
  };
  return {
    ctx,
    get: async (pfad: string) => pruefe(await ctx.get(`/api/${pfad}`)),
    post: async (pfad: string, daten?: unknown) => pruefe(await ctx.post(`/api/${pfad}`, { data: daten, headers: await kopf() })),
    patch: async (pfad: string, daten: unknown) => pruefe(await ctx.patch(`/api/${pfad}`, { data: daten, headers: await kopf() })),
    put: async (pfad: string, daten: unknown) => pruefe(await ctx.put(`/api/${pfad}`, { data: daten, headers: await kopf() })),
    roh: ctx,
    kopf,
    ende: () => ctx.dispose(),
  };
}

/** Backend und Webserver neu starten (Nachweis: Daten liegen in der Datenbank, nicht im Speicher) */
export function stackNeuStarten() {
  execSync("sudo docker compose -p epm-ci restart backend web", { cwd: process.env.EPM_CI_BASIS ?? "/tmp/epm-ci", stdio: "inherit" });
  for (let i = 0; i < 60; i++) {
    try {
      execSync(`curl -ksf ${BASIS}/api/auth/status/ -o /dev/null`, { stdio: "ignore" });
      return;
    } catch {
      execSync("sleep 2");
    }
  }
  throw new Error("Stack nach Neustart nicht erreichbar");
}

const NACHWEIS = "e2e/.auth/nachweis.json";

/** Ergebnis eines Tests merken; `zz-neustart.spec.ts` prüft es nach einem Neustart erneut in der Oberfläche. */
export function merken(schluessel: string, wert: unknown) {
  const stand: Record<string, unknown> = existsSync(NACHWEIS) ? JSON.parse(readFileSync(NACHWEIS, "utf8")) : {};
  stand[schluessel] = wert;
  mkdirSync("e2e/.auth", { recursive: true });
  writeFileSync(NACHWEIS, JSON.stringify(stand, null, 1));
}

/** Gemerktes Ergebnis; fehlt es, ist der Test davor nicht bis zum Ende gelaufen. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function gemerkt(schluessel: string): any {
  const stand = existsSync(NACHWEIS) ? JSON.parse(readFileSync(NACHWEIS, "utf8")) : {};
  if (!(schluessel in stand)) throw new Error(`Kein Ergebnis „${schluessel}“ gemerkt – der zugehörige Test ist vorher fehlgeschlagen.`);
  return stand[schluessel];
}

/** Sitzung in der Datenbank ablaufen lassen – genau das, was nach 30 Minuten ohne Anfrage passiert. */
export function sitzungAblaufenLassen(schluessel: string) {
  if (!/^[a-z0-9]+$/.test(schluessel)) throw new Error(`Unerwarteter Sitzungsschlüssel: ${schluessel}`);
  const befehl = "from datetime import timedelta; from django.utils import timezone; " +
    "from django.contrib.sessions.models import Session; " +
    `print(Session.objects.filter(session_key='${schluessel}').update(expire_date=timezone.now() - timedelta(seconds=1)))`;
  const ausgabe = execSync(`sudo docker compose -p epm-ci exec -T backend python manage.py shell -v 0 -c "${befehl}"`,
    { cwd: process.env.EPM_CI_BASIS ?? "/tmp/epm-ci" }).toString().trim();
  const anzahl = ausgabe.split("\n").pop()?.trim();
  if (anzahl !== "1") throw new Error(`Sitzung nicht gefunden (${anzahl})`);
}

/** Gilt die Sitzung der Seite noch? Bei einem Fehlschlag steht im Bericht, nach welchem Schritt sie endete. */
export async function sitzungGilt(page: Page, nachSchritt: string) {
  const s = await (await page.request.get("/api/auth/status/")).json();
  expect(s.schritt, `Sitzung nach „${nachSchritt}“`).toBe("fertig");
}

export function eindeutig(prefix: string) {
  return `${prefix}${Date.now().toString(36).slice(-5)}`;
}

/** Neues Konto über die Administration anlegen und die erste Anmeldung (Passwort, Authenticator) per API abschließen.
 *  Für Tests, die das eigene Konto verändern (Passwort, Gerät, Sitzungen), ohne die gemeinsamen Testkonten zu berühren. */
export async function neuesKonto(rolle = "mitarbeiter", vorname = "Konrad", nachname = "Konto") {
  const admin = await apiAls("admin");
  const benutzername = eindeutig("e2e.konto");
  const neu = await admin.post("benutzer/", { username: benutzername, first_name: vorname, last_name: nachname, rolle });
  await admin.ende();
  const ctx = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true, storageState: OHNE_ANMELDUNG });
  await ctx.get("/api/auth/status/");
  const kopf = async () => ({
    "X-CSRFToken": (await ctx.storageState()).cookies.find((c) => c.name === "epm_csrf")?.value ?? "",
    Referer: `${BASIS}/`,
    Origin: BASIS,
  });
  const schritt = async (pfad: string, daten?: unknown) => {
    const r = await ctx.post(`/api/${pfad}`, { data: daten, headers: await kopf() });
    if (!r.ok()) throw new Error(`${pfad}: ${r.status()} ${await r.text()}`);
    return r.json();
  };
  await schritt("auth/anmelden/", { benutzername, kennwort: neu.einmal_kennwort });
  const kennwort = `${KENNWORT}-${Math.random().toString(36).slice(2, 8)}`;
  await schritt("auth/kennwort/", { neu: kennwort });
  const qr = await schritt("auth/2fa/einrichten/");
  const geheim = new URL(qr.otpauth_url).searchParams.get("secret") ?? "";
  const fertig = await schritt("auth/2fa/bestaetigen/", { code: totpBase32(geheim) });
  const pfad = `e2e/.auth/${benutzername}.json`;
  await ctx.storageState({ path: pfad });
  await ctx.dispose();
  return { id: neu.id as number, benutzername, kennwort, geheim, notfallcodes: fertig.notfallcodes as string[], zustand: pfad };
}

/** Anmeldung per API mit Kennwort und Code (z. B. Notfall-Code für eine zweite Sitzung desselben Kontos) */
export async function apiAnmelden(benutzername: string, kennwort: string, code: string) {
  const ctx = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true, storageState: OHNE_ANMELDUNG });
  await ctx.get("/api/auth/status/");
  const kopf = async () => ({
    "X-CSRFToken": (await ctx.storageState()).cookies.find((c) => c.name === "epm_csrf")?.value ?? "",
    Referer: `${BASIS}/`,
    Origin: BASIS,
  });
  const a = await ctx.post("/api/auth/anmelden/", { data: { benutzername, kennwort }, headers: await kopf() });
  const s1 = await a.json();
  if (s1.schritt !== "2fa") return { ctx, schritt: s1.schritt as string, status: a.status() };
  const b = await ctx.post("/api/auth/2fa/", { data: { code }, headers: await kopf() });
  return { ctx, schritt: (await b.json()).schritt as string, status: b.status() };
}

/** Kleine, gültige PDF mit einer Textzeile je Seite (für die PDF-Anzeige in EPM). */
export function einfachePdf(seiten: string[]): Buffer {
  const objekte: string[] = [];
  const kids = seiten.map((_, i) => `${3 + i * 2} 0 R`).join(" ");
  const schrift = 3 + seiten.length * 2;
  objekte.push("<< /Type /Catalog /Pages 2 0 R >>");
  objekte.push(`<< /Type /Pages /Kids [${kids}] /Count ${seiten.length} >>`);
  for (let i = 0; i < seiten.length; i++) {
    const inhalt = `BT /F1 24 Tf 72 760 Td (${seiten[i].replace(/[()\\]/g, "")}) Tj ET`;
    objekte.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents ${4 + i * 2} 0 R /Resources << /Font << /F1 ${schrift} 0 R >> >> >>`);
    objekte.push(`<< /Length ${inhalt.length} >>\nstream\n${inhalt}\nendstream`);
  }
  objekte.push("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");
  let pdf = "%PDF-1.4\n";
  const versatz: number[] = [];
  objekte.forEach((o, i) => {
    versatz.push(pdf.length);
    pdf += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objekte.length + 1}\n0000000000 65535 f \n`;
  for (const v of versatz) pdf += `${String(v).padStart(10, "0")} 00000 n \n`;
  pdf += `trailer\n<< /Size ${objekte.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf, "latin1");
}

/** Kontrast zwischen Schrift und Hintergrund eines Knopfs (Regression „blaue Schrift auf blauem Knopf“). */
export async function kontrast(el: import("@playwright/test").Locator): Promise<number> {
  return el.evaluate((e) => {
    const s = getComputedStyle(e);
    const lum = (farbe: string) => {
      const [r, g, b] = (farbe.match(/\d+(\.\d+)?/g) ?? ["0", "0", "0"]).slice(0, 3).map((x) => Number(x) / 255)
        .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const [a, b] = [lum(s.color), lum(s.backgroundColor)].sort((x, y) => y - x);
    return (a + 0.05) / (b + 0.05);
  });
}

/** Virtueller Authenticator des Browsers (Passkey mit Fingerabdruck/PIN „bestätigt“), Chrome DevTools-Protokoll */
export async function virtuellerAuthenticator(ctx: BrowserContext, page: Page) {
  const cdp: CDPSession = await ctx.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  const { authenticatorId } = await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true,
      isUserVerified: true, automaticPresenceSimulation: true },
  });
  return { cdp, authenticatorId };
}

/** Navigation „Administration“: Wer mehr als zwei Verwaltungsseiten hat, sieht sie als Gruppe zum Aufklappen (F181).
 *  Klappt sie bei Bedarf auf und gibt die Navigation zurück. */
export async function adminNavigation(page: Page) {
  const nav = page.getByRole("navigation", { name: "Administration" });
  const knopf = nav.getByTestId("nav-administration");
  await nav.waitFor(); // sonst zählt count() vor dem ersten Zeichnen 0 und der Bereich bleibt zu
  if (await knopf.count() && (await knopf.getAttribute("aria-expanded")) !== "true") await knopf.click();
  return nav;
}
