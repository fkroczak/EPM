// Ladezeiten-Messung EPM: echter Browser (Chromium), gebautes Frontend (vite preview) + gunicorn.
// Aufruf: node messen.mjs <ausgabe.json> [runden]
import { createRequire } from "node:module";
const { chromium } = createRequire("/opt/node-tools/")("playwright");
import { createHmac } from "node:crypto";
import { writeFileSync } from "node:fs";

const BASIS = process.env.BASIS ?? "http://127.0.0.1:4173";
const SPA = !!process.env.SPA;
const KENNWORT = "E2E-Kennwort-sicher-2026";
const SCHLUESSEL = Buffer.from("3132333435363738393031323334353637383930", "hex");
const RUNDEN = Number(process.argv[3] ?? 5);

function totp(versatz = 0) {
  const b = Buffer.alloc(8);
  b.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000) + versatz));
  const h = createHmac("sha1", SCHLUESSEL).update(b).digest();
  const o = h[h.length - 1] & 0xf;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, "0");
}

const P = 1;
const SEITEN_ALLE = {
  "e2e.mediziner": [
    "/", "/patienten", `/patienten/${P}`, `/patienten/${P}/kartei`, `/patienten/${P}/diagnosen`,
    `/patienten/${P}/medikamente`, `/patienten/${P}/therapie`, `/patienten/${P}/kontakte`, `/patienten/${P}/plaene`,
    `/patienten/${P}/labor`, `/patienten/${P}/bia`, `/patienten/${P}/berichte`, `/patienten/${P}/korrespondenz`,
    `/patienten/${P}/dokumente`, `/patienten/${P}/verlauf`, "/kalender", "/infusionsplaene", "/versorger", "/aerzte",
    "/diktate", "/konto", "/hilfe",
  ],
  "e2e.admin": ["/", "/admin", "/admin/benutzer", "/admin/vorlagen", "/admin/audit-log", "/admin/system", "/admin/backup"],
};

const SEITEN = process.env.KURZ ? { "e2e.mediziner": ["/", "/patienten/1"] } : SEITEN_ALLE;
import { existsSync, readFileSync } from "node:fs";
const ZAEHLER = "/var/tmp/mess/notfallcodes.json";
function naechsterCode(benutzer) {
  const stand = existsSync(ZAEHLER) ? JSON.parse(readFileSync(ZAEHLER, "utf8")) : {};
  const n = stand[benutzer] ?? 0;
  stand[benutzer] = n + 1;
  writeFileSync(ZAEHLER, JSON.stringify(stand));
  return `e2e${String(n).padStart(4, "0")}code`;
}
async function anmelden(browser, benutzer) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  if (process.env.DROSSEL) {
    // VPN-ähnliches Netz: 40 ms Latenz, 20 Mbit/s runter, 5 Mbit/s hoch
    const cdp = await ctx.newCDPSession(page);
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 40,
      downloadThroughput: 20e6 / 8, uploadThroughput: 5e6 / 8 });
  }
  await page.goto(BASIS + "/");
  await page.getByLabel("Benutzername").fill(benutzer);
  await page.getByLabel("Passwort").fill(KENNWORT);
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.getByLabel("Code").waitFor();
  // jeder TOTP-Code gilt nur einmal: für das zweite Konto den nächsten Zeitschritt nehmen
  // Notfall-Codes (je einmal gültig, vorbereiten.py legt 40 je Konto an): beliebig viele Anmeldungen hintereinander
  await page.getByLabel("Code").fill(naechsterCode(benutzer));
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.waitForSelector("nav, header", { timeout: 20000 });
  await page.waitForLoadState("networkidle");
  return { ctx, page };
}

/** Eine Seite laden (voller Seitenaufruf, Dateien im Browser-Cache wie im Alltag) und messen. */
async function messen(page, pfad) {
  const api = [];
  const offen = new Map();
  let start = Date.now();
  // im SPA-Modus zählen auch die Seiten-Dateien (der Router wartet auf sie)
  const zaehlt = (u) => u.includes("/api/") || (SPA && u.includes("/assets/"));
  const onReq = (r) => { if (zaehlt(r.url())) offen.set(r, Date.now()); };
  const onDone = async (r) => {
    if (!offen.has(r)) return;
    const t = Date.now();
    const beginn = offen.get(r) - start;
    offen.delete(r);
    if (!r.url().includes("/api/")) return;
    const a = await r.response().catch(() => null);
    const kopf = a ? await a.allHeaders().catch(() => ({})) : {};
    api.push({ url: r.url().replace(BASIS, ""), beginn, ende: t - start, q: Number(kopf["x-mess-q"] ?? -1),
      ms: Number(kopf["x-mess-ms"] ?? -1), status: a?.status() });
  };
  page.on("request", onReq);
  page.on("requestfinished", onDone);
  page.on("requestfailed", onDone);
  if (SPA) {
    // Navigation innerhalb der Anwendung. Gibt es auf der Seite einen sichtbaren Link zum Ziel, fährt die Maus ihn an
    // und klickt nach 200 ms (wie ein Mensch); sonst Sprung über die Adresse (React Router reagiert auf popstate).
    // Die Zeit zählt ab dem Klick.
    const link = page.locator(`a[href="${pfad}"]:visible`).first();
    if (pfad !== "/" && await link.count()) {
      await link.hover();
      await page.waitForTimeout(200);
      offen.clear(); api.length = 0;
      start = Date.now();
      await link.click();
    } else {
      await page.evaluate((p) => { history.pushState({}, "", p); dispatchEvent(new PopStateEvent("popstate")); }, pfad);
    }
  } else {
    await page.goto(BASIS + pfad, { waitUntil: "commit" });
  }
  // fertig = 500 ms keine offene API-Anfrage und kein Ladehinweis mehr sichtbar
  let ruhigSeit = Date.now();
  while (Date.now() - start < 30000) {
    await page.waitForTimeout(50);
    const laedt = await page.evaluate(() => {
      const t = document.body?.innerText ?? "";
      return /wird geladen|lädt …|Wird geladen/i.test(t) || !!document.querySelector("[data-laden]");
    }).catch(() => true);
    if (offen.size > 0 || laedt) ruhigSeit = Date.now();
    else if (Date.now() - ruhigSeit > 500) break;
  }
  const fertig = ruhigSeit - start;
  const perf = await page.evaluate(() => {
    const fcp = performance.getEntriesByName("first-contentful-paint")[0]?.startTime ?? null;
    return { fcp };
  });
  // erster sichtbarer Inhalt im Hauptbereich (Skelett oder Daten) – per MutationObserver nicht nachträglich messbar,
  // daher: Zeitpunkt der ersten API-Antwort als Näherung nicht nötig; FCP + fertig genügen
  page.off("request", onReq);
  page.off("requestfinished", onDone);
  page.off("requestfailed", onDone);
  const letzteApi = api.length ? Math.max(...api.map((a) => a.ende)) : 0;
  return { pfad, fertig, letzteApi, fcp: perf.fcp, api };
}

const browser = await chromium.launch();
const ergebnis = {};
for (const [benutzer, seiten] of Object.entries(SEITEN)) {
  if (SPA) {
    // je Runde neu anmelden: leerer Abfrage-Speicher, Seiten-Dateien noch nicht geladen – dann einmal durch alle Seiten
    for (let r = 0; r < RUNDEN; r++) {
      const { ctx, page } = await anmelden(browser, benutzer);
      for (const pfad of seiten) {
        await page.waitForTimeout(1000); // Bedienzeit zwischen zwei Klicks
        const m = await messen(page, pfad);
        (ergebnis[`${benutzer.replace("e2e.", "")} ${pfad}`] ??= []).push(m);
      }
      await ctx.close();
    }
    continue;
  }
  const { ctx, page } = await anmelden(browser, benutzer);
  for (const pfad of seiten) await messen(page, pfad); // Aufwärmen (Dateien im Cache, Python-Importe)
  for (let r = 0; r < RUNDEN; r++) {
    for (const pfad of seiten) {
      const m = await messen(page, pfad);
      const k = `${benutzer.replace("e2e.", "")} ${pfad}`;
      (ergebnis[k] ??= []).push(m);
    }
  }
  await ctx.close();
}
await browser.close();

const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
const zusammen = Object.fromEntries(Object.entries(ergebnis).map(([k, ms]) => [k, {
  fertig: median(ms.map((m) => m.fertig)),
  letzteApi: median(ms.map((m) => m.letzteApi)),
  fcp: median(ms.map((m) => m.fcp ?? 0)),
  anfragen: ms[0].api.length,
  queries: ms[0].api.reduce((s, a) => s + Math.max(0, a.q), 0),
  serverMs: median(ms.map((m) => m.api.reduce((s, a) => s + Math.max(0, a.ms), 0))),
  api: ms[ms.length - 1].api.map((a) => `${a.status} q=${a.q} ${a.ms}ms [${a.beginn}-${a.ende}] ${a.url}`),
}]));
writeFileSync(process.argv[2], JSON.stringify(zusammen, null, 1));
let summe = 0;
for (const [k, v] of Object.entries(zusammen)) {
  summe += v.fertig;
  console.log(`${String(v.fertig).padStart(6)} ms fertig | ${String(v.serverMs.toFixed(0)).padStart(5)} ms Server | ${String(v.queries).padStart(4)} SQL | ${String(v.anfragen).padStart(2)} Anfr. | ${k}`);
}
console.log(`SUMME fertig: ${summe} ms`);
