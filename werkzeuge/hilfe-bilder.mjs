#!/usr/bin/env node
/**
 * EPM – Bilder für die Hilfe aus der laufenden Anwendung erzeugen (Wunsch 11.10.2026: „Seiteninterne Hilfe mit
 * Screenshots und kurzen animierten GIFs“).
 *
 *   node werkzeuge/hilfe-bilder.mjs                  alle Bilder neu
 *   node werkzeuge/hilfe-bilder.mjs kontakt telefon  nur Bilder, deren Name einen dieser Begriffe enthält
 *
 * Ergebnis: frontend/public/hilfe-bilder/*.png bzw. *.gif (je GIF ein Standbild *-standbild.png für „Bewegung
 * reduzieren“). Eingebunden werden sie in backend/hilfe/inhalt.py; am Ende steht eine Liste mit Größe und Maßen.
 *
 * Voraussetzungen
 *  - EPM läuft (Entwicklung: Vite auf 127.0.0.1:5173 mit Django dahinter). Andere Adresse: EPM_URL=https://…
 *  - Ein Konto, das nur Testpatienten sieht (Testbenutzer, Rolle Mediziner) – die Bilder zeigen ausschließlich die
 *    Testpatienten (Beispiel Paula, Mustermann Max, Test Hanna, Probe Jonas …), nie echte Daten.
 *    Anmeldung: EPM_BENUTZER (Vorgabe hilfe.bilder), EPM_KENNWORT und – falls das Konto einen zweiten Faktor hat –
 *    EPM_CODE (Notfall-Code oder Code aus der App). Die Sitzung wird in werkzeuge/.hilfe-bilder-sitzung.json
 *    gespeichert (nicht im Repo) und beim nächsten Lauf wiederverwendet, solange sie gilt.
 *  - Playwright aus frontend/node_modules (npm ci in frontend/), Chromium: EPM_CHROMIUM (Vorgabe
 *    /opt/pw-browsers/chromium; leer = das von Playwright installierte).
 *  - Python mit Pillow für GIFs und Verkleinern: EPM_PYTHON (Vorgabe python3), siehe werkzeuge/hilfe-gif.py.
 *
 * Es wird nichts gespeichert: Dialoge werden nur geöffnet, ausgefüllt gezeigt und mit Escape verworfen.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const WURZEL = fileURLToPath(new URL("..", import.meta.url));
const require = createRequire(join(WURZEL, "frontend", "package.json"));
const { chromium, request } = require("playwright");

const BASIS = (process.env.EPM_URL ?? "http://127.0.0.1:5173").replace(/\/$/, "");
const ZIEL = join(WURZEL, "frontend", "public", "hilfe-bilder");
const SITZUNG = process.env.EPM_SITZUNG ?? join(WURZEL, "werkzeuge", ".hilfe-bilder-sitzung.json");
const PYTHON = process.env.EPM_PYTHON ?? "python3";
const CHROMIUM = process.env.EPM_CHROMIUM ?? "/opt/pw-browsers/chromium";
const GIF_WERKZEUG = join(WURZEL, "werkzeuge", "hilfe-gif.py");
const AUSWAHL = process.argv.slice(2);
const ARBEIT = mkdtempSync(join(tmpdir(), "hilfe-bilder-"));

const PC = { viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 };
const TELEFON = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true };

/* Markierung (roter Rahmen) und Aufräumen fürs Bild: Kennzeichen „Test“/„Testpatient“/„Testzugang“ gibt es bei echten
   Akten nicht – sie würden in der Hilfe nur verwirren. Blinkende Schreibmarke und Übergänge aus. */
const VORBEREITUNG = () => {
  const stil = document.createElement("style");
  stil.textContent = `
    .hilfe-markierung { outline: 3px solid #d9241b !important; outline-offset: 3px !important; border-radius: 0.5rem; }
    * { caret-color: transparent !important; transition: none !important; animation-duration: 0s !important; }
    /* Fenster und Trefferliste der Suche liegen über der Seite – auch bei einem Stand vom 11.10.2026, in dem eine
       Kartenregel (index.css) sie in den Textfluss holte */
    .card.fixed { position: fixed !important; } .card.absolute { position: absolute !important; }`;
  const ausblenden = () => {
    for (const el of document.querySelectorAll(".chip")) {
      if (["Test", "Testpatient", "Testzugang"].includes(el.textContent.trim())) el.style.display = "none";
    }
  };
  const start = () => {
    document.head.appendChild(stil);
    ausblenden();
    new MutationObserver(ausblenden).observe(document.body, { childList: true, subtree: true, characterData: true });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
};

// ------------------------------------------------------------------ Anmeldung

async function sitzungGilt() {
  if (!existsSync(SITZUNG)) return false;
  const ctx = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true, storageState: SITZUNG });
  const s = await (await ctx.get("/api/auth/status/")).json().catch(() => ({}));
  await ctx.dispose();
  if (s.schritt === "fertig" && !s.benutzer?.ist_test) {
    throw new Error(`Das Konto ${s.benutzer?.benutzername} ist kein Testbenutzer – die Bilder dürfen nur Testpatienten zeigen.`);
  }
  return s.schritt === "fertig";
}

async function anmelden() {
  if (await sitzungGilt()) return;
  const benutzer = process.env.EPM_BENUTZER ?? "hilfe.bilder";
  if (!process.env.EPM_KENNWORT) throw new Error("Keine gültige Sitzung: bitte EPM_KENNWORT (und ggf. EPM_CODE) angeben.");
  const ctx = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true });
  await ctx.get("/api/auth/status/");
  // Django erneuert das CSRF-Token bei der Anmeldung – daher vor jedem Schritt neu lesen
  const kopf = async () => ({
    "X-CSRFToken": (await ctx.storageState()).cookies.find((c) => c.name === "epm_csrf")?.value ?? "",
    Referer: `${BASIS}/`, Origin: BASIS,
  });
  const a = await ctx.post("/api/auth/anmelden/", { data: { benutzername: benutzer, kennwort: process.env.EPM_KENNWORT }, headers: await kopf() });
  if (!a.ok()) throw new Error(`Anmeldung ${benutzer}: ${a.status()} ${await a.text()}`);
  let s = await a.json();
  if (s.schritt !== "fertig") {
    if (!process.env.EPM_CODE) throw new Error(`Anmeldung ${benutzer}: Schritt „${s.schritt}“ – bitte EPM_CODE angeben.`);
    s = await (await ctx.post("/api/auth/2fa/", { data: { code: process.env.EPM_CODE }, headers: await kopf() })).json();
    if (s.schritt !== "fertig") throw new Error(`Zweiter Faktor ${benutzer}: ${JSON.stringify(s)}`);
  }
  await ctx.storageState({ path: SITZUNG });
  await ctx.dispose();
  await sitzungGilt();
}

async function patientId(nachname, vorname) {
  const ctx = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true, storageState: SITZUNG });
  const d = await (await ctx.get(`/api/patienten/?suche=${encodeURIComponent(nachname)}`)).json();
  await ctx.dispose();
  const p = (d.results ?? d).find((x) => x.nachname === nachname && x.vorname === vorname && x.ist_test);
  if (!p) throw new Error(`Testpatient ${nachname}, ${vorname} nicht gefunden.`);
  return p.id;
}

// ------------------------------------------------------------------ Hilfen fürs Bild

async function seite(browser, geraet) {
  const ctx = await browser.newContext({ ...geraet, storageState: SITZUNG, ignoreHTTPSErrors: true, locale: "de-DE",
    timezoneId: "Europe/Berlin", colorScheme: "light", reducedMotion: "reduce" });
  await ctx.addInitScript(VORBEREITUNG);
  const page = await ctx.newPage();
  page.setDefaultTimeout(15_000);
  page.dsf = geraet.deviceScaleFactor;
  return page;
}

async function oeffne(page, pfad) {
  await page.goto(BASIS + pfad);
  await ruhig(page);
}

/** warten, bis Daten geladen und Schriften da sind */
async function ruhig(page, ms = 400) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(ms);
}

/** Fenster (Dialoge) ganz zeigen: dafür den PC-Bildschirm vorübergehend höher machen (1366×1000) */
async function hoch(page, erzeugen) {
  const vorher = page.viewportSize();
  await page.setViewportSize({ width: vorher.width, height: 1000 });
  try {
    await erzeugen();
  } finally {
    await page.setViewportSize(vorher);
  }
}

async function markiere(...ziele) {
  for (const z of ziele) await z.evaluate((el) => el.classList.add("hilfe-markierung"));
}

async function entmarkiere(page) {
  await page.evaluate(() => document.querySelectorAll(".hilfe-markierung").forEach((el) => el.classList.remove("hilfe-markierung")));
}

/** Ausschnitt um ein oder mehrere Elemente (mit Rand), begrenzt auf den sichtbaren Bereich */
async function ausschnitt(page, ziele, { rand = 12, minHoehe = 0, maxHoehe = Infinity, links, rechts } = {}) {
  const boxen = [];
  for (const z of [ziele].flat()) boxen.push(await z.boundingBox());
  const vp = page.viewportSize();
  const x = Math.max(0, (links ?? Math.min(...boxen.map((b) => b.x))) - rand);
  const y = Math.max(0, Math.min(...boxen.map((b) => b.y)) - rand);
  const r = Math.min(vp.width, (rechts ?? Math.max(...boxen.map((b) => b.x + b.width))) + rand);
  let u = Math.min(vp.height, Math.max(...boxen.map((b) => b.y + b.height)) + rand);
  u = Math.min(vp.height, Math.max(u, y + minHoehe), y + maxHoehe);
  return { x: Math.round(x), y: Math.round(y), width: Math.round(r - x), height: Math.round(u - y) };
}

/** Ausschnitt (CSS-Pixel im sichtbaren Bereich) → Bildpunkte im Bildschirmfoto. Fotografiert wird immer der sichtbare
 *  Bereich und danach zugeschnitten – ein „clip“ von Playwright rechnet ab dem Seitenanfang und verrutscht, sobald die
 *  Seite gescrollt ist oder ein Fenster das Scrollen sperrt. */
function zuschnitt(page, clip) {
  const f = page.dsf;
  return [clip.x, clip.y, clip.width, clip.height].map((v) => Math.round(v * f)).join(",");
}

const gewaehlt = (name) => !AUSWAHL.length || AUSWAHL.some((a) => name.includes(a));
const ergebnisse = [];

async function foto(page, name, clip, breite = 0) {
  const roh = join(ARBEIT, `${name}.png`);
  await page.screenshot({ path: roh, animations: "disabled" });
  execFileSync(PYTHON, [GIF_WERKZEUG, "png", join(ZIEL, `${name}.png`), roh, String(breite), zuschnitt(page, clip)]);
  ergebnisse.push(`${name}.png`);
}

/** GIF aus Einzelbildern: jedes Bild mit demselben Ausschnitt; Nr. des Standbilds ab 1 */
class Film {
  constructor(page, name, clip, { breite = 0, standbild } = {}) {
    Object.assign(this, { page, name, clip, breite, standbild, bilder: [] });
  }
  async bild() {
    const pfad = join(ARBEIT, `${this.name}-${String(this.bilder.length + 1).padStart(2, "0")}.png`);
    await this.page.screenshot({ path: pfad, animations: "disabled" });
    this.bilder.push(pfad);
  }
  fertig() {
    execFileSync(PYTHON, [GIF_WERKZEUG, "gif", join(ZIEL, `${this.name}.gif`), join(ZIEL, `${this.name}-standbild.png`),
      String(this.standbild ?? this.bilder.length), String(this.breite), zuschnitt(this.page, this.clip), ...this.bilder]);
    ergebnisse.push(`${this.name}.gif`, `${this.name}-standbild.png`);
  }
}

/** Dialog schließen, ohne zu speichern (fragt EPM nach, ob verworfen werden soll: ja) */
async function verwerfen(page) {
  await page.keyboard.press("Escape");
  const nachfrage = page.getByRole("button", { name: /^Verwerfen|^Schließen ohne|^Nicht speichern/ });
  if (await nachfrage.first().isVisible({ timeout: 800 }).catch(() => false)) await nachfrage.first().click();
  await page.getByRole("dialog").first().waitFor({ state: "detached", timeout: 5000 }).catch(() => {});
}

// ------------------------------------------------------------------ Bilder

const BILDER = {
  /** Startseite: Kopf mit den Schnellknöpfen und „Heute zu tun“ */
  async startseite({ pc }) {
    await oeffne(pc, "/");
    const kopf = pc.locator("main h1").first();
    const heute = pc.getByTestId("heute-zu-tun");
    await markiere(pc.getByRole("button", { name: "Kontakt erfassen", exact: true }));
    await foto(pc, "startseite-heute-zu-tun", await ausschnitt(pc, [kopf, heute], { rand: 14 }));
    await entmarkiere(pc);
  },

  /** Patient suchen (PC): Suchfeld oben, Treffer, Akte öffnet sich */
  async "patient-suchen"({ pc }) {
    await oeffne(pc, "/");
    const feld = pc.getByRole("combobox", { name: "Suchen" });
    const film = new Film(pc, "patient-suchen", { x: 64, y: 0, width: 1302, height: 330 }, { breite: 960, standbild: 3 });
    await markiere(feld);
    await film.bild();
    await feld.click();
    await feld.pressSequentially("Beisp", { delay: 60 });
    await pc.getByRole("option", { name: /Beispiel, Paula/ }).waitFor();
    await ruhig(pc, 300);
    await film.bild();
    await entmarkiere(pc);
    await markiere(pc.getByRole("option", { name: /Beispiel, Paula/ }));
    await film.bild();
    await foto(pc, "patient-suchen", { x: 560, y: 0, width: 806, height: 200 });
    await pc.getByRole("option", { name: /Beispiel, Paula/ }).click();
    await pc.getByTestId("aktenkopf").waitFor();
    await ruhig(pc);
    await film.bild();
    film.fertig();
  },

  /** Aktenkopf mit Hinweisen und den Knöpfen für die tägliche Arbeit */
  async aktenkopf({ pc, paula }) {
    await oeffne(pc, `/patienten/${paula}`);
    const kopf = pc.getByTestId("aktenkopf");
    await markiere(kopf.getByRole("button", { name: /Hinweise/ }).first());
    await foto(pc, "akte-kopf", await ausschnitt(pc, kopf, { rand: 10 }));
    await entmarkiere(pc);
  },

  /** Kontakt erfassen: Knopf in der Akte → Fenster → Notiz → Speichern (hier nur gezeigt, nicht gespeichert) */
  async "kontakt-erfassen"({ pc, paula }) {
    await hoch(pc, async () => {
    await oeffne(pc, `/patienten/${paula}`);
    const knopf = pc.getByTestId("aktenkopf").getByRole("button", { name: "Kontakt", exact: true });
    const film = new Film(pc, "kontakt-erfassen", { x: 64, y: 0, width: 1302, height: 1000 }, { breite: 960, standbild: 4 });
    await markiere(knopf);
    await film.bild();
    await entmarkiere(pc);
    await knopf.click();
    const dialog = pc.getByRole("dialog", { name: "Kontakt erfassen" });
    await dialog.waitFor();
    await ruhig(pc);
    await film.bild();
    await foto(pc, "kontakt-erfassen-fenster", await ausschnitt(pc, dialog, { rand: 0 }));
    const notiz = dialog.locator("[contenteditable=true]").first();
    await notiz.click();
    await notiz.pressSequentially("Gewicht telefonisch durchgegeben, Pumpe läuft gut.", { delay: 15 });
    await markiere(notiz);
    await film.bild();
    await entmarkiere(pc);
    const speichern = dialog.getByRole("button", { name: "Speichern", exact: true });
    await speichern.scrollIntoViewIfNeeded();
    await markiere(speichern);
    await film.bild();
    await entmarkiere(pc);
    film.fertig();
    await verwerfen(pc);
    });
  },

  /** Gewicht erfassen (Dialog) */
  async "gewicht-erfassen"({ pc, paula }) {
    await hoch(pc, async () => {
    await oeffne(pc, `/patienten/${paula}`);
    await pc.getByTestId("aktenkopf").getByRole("button", { name: "Gewicht", exact: true }).click();
    const dialog = pc.getByRole("dialog").first();
    await dialog.waitFor();
    await ruhig(pc);
    const feld = dialog.getByLabel(/^Gewicht/).first();
    await feld.fill("57,4");
    await ruhig(pc, 600);
    await markiere(feld);
    await foto(pc, "gewicht-erfassen-fenster", await ausschnitt(pc, dialog, { rand: 0 }));
    await entmarkiere(pc);
    await verwerfen(pc);
    });
  },

  /** Termin anlegen (Dialog) */
  async "termin-anlegen"({ pc, paula }) {
    await hoch(pc, async () => {
    await oeffne(pc, `/patienten/${paula}`);
    await pc.getByTestId("aktenkopf").getByRole("button", { name: "Termin", exact: true }).click();
    const dialog = pc.getByRole("dialog", { name: "Neuer Termin" });
    await dialog.waitFor();
    await ruhig(pc);
    await foto(pc, "termin-anlegen-fenster", await ausschnitt(pc, dialog, { rand: 0 }));
    await verwerfen(pc);
    });
  },

  /** Infusionspläne: Liste in der Akte und der Entwurf mit „Freigeben“ */
  async infusionsplan({ pc, paula }) {
    await oeffne(pc, `/patienten/${paula}/plaene`);
    await pc.getByText(/^Aktuell gültig/).first().waitFor();
    await foto(pc, "infusionsplan-ansehen", { x: 64, y: 300, width: 1302, height: 430 });
    await oeffne(pc, "/infusionsplaene");
    await pc.getByRole("tab", { name: /Zur Freigabe/ }).or(pc.getByRole("button", { name: /Zur Freigabe/ })).first().click();
    await ruhig(pc);
    await pc.getByRole("button", { name: "Öffnen" }).or(pc.getByRole("link", { name: "Öffnen" })).first().click();
    const detail = pc.getByTestId("plan-detail");
    await detail.waitFor();
    await detail.locator("canvas").first().waitFor({ timeout: 10_000 }).catch(() => {});
    await ruhig(pc, 1000);
    const freigeben = detail.getByRole("button", { name: "Freigeben", exact: true });
    await markiere(freigeben);
    await foto(pc, "infusionsplan-freigeben", await ausschnitt(pc, detail, { rand: 10, maxHoehe: 400 }));
    await entmarkiere(pc);
  },

  /** Dokumente: Ablagefläche, Liste und Vorschau */
  async dokumente({ pc, paula }) {
    await oeffne(pc, `/patienten/${paula}/dokumente`);
    await ruhig(pc, 1200);
    await markiere(pc.getByRole("button", { name: "Neues Dokument" }));
    await foto(pc, "dokumente-hochladen", { x: 64, y: 340, width: 1302, height: 428 }, 0);
    await entmarkiere(pc);
  },

  /** Kalender mit Monatsansicht und Tagesliste */
  async kalender({ pc }) {
    await oeffne(pc, "/kalender");
    await pc.getByTestId("kalender-monat").waitFor();
    await ruhig(pc, 600);
    await foto(pc, "kalender", { x: 64, y: 60, width: 1302, height: 708 }, 1100);
  },

  /** Das „?“ oben rechts öffnet die Hilfe zur Seite */
  async "hilfe-knopf"({ pc }) {
    await oeffne(pc, "/patienten");
    const knopf = pc.getByTestId("hilfe-zur-seite");
    await markiere(knopf);
    await foto(pc, "hilfe-knopf", { x: 764, y: 0, width: 602, height: 130 });
    await entmarkiere(pc);
  },

  /** Telefon: Akte oben (Kopf mit Hinweisen und Knöpfen) */
  async "telefon-akte"({ tel, max }) {
    await oeffne(tel, `/patienten/${max}`);
    await foto(tel, "telefon-akte", { x: 0, y: 0, width: 390, height: 484 });
  },

  /** Telefon: offenen Punkt in der Patientenliste antippen → EPM öffnet die passende Stelle */
  async "telefon-offener-punkt"({ tel }) {
    await oeffne(tel, "/patienten?suche=Mustermann");
    const liste = tel.getByTestId("patientenliste");
    const karte = liste.getByRole("listitem").filter({ hasText: "Mustermann, Max" }).first();
    await karte.scrollIntoViewIfNeeded();
    const film = new Film(tel, "telefon-offener-punkt", { x: 0, y: 0, width: 390, height: 844 }, { breite: 540, standbild: 2 });
    await film.bild();
    const chip = karte.getByText("Nickelallergie nicht erfasst", { exact: true }).first();
    await markiere(chip);
    await film.bild();
    await entmarkiere(tel);
    await chip.click();
    const dialog = tel.getByRole("dialog").first();
    await dialog.waitFor();
    await ruhig(tel, 600);
    const feld = dialog.getByText("Nickelallergie", { exact: false }).first();
    await feld.scrollIntoViewIfNeeded();
    await markiere(feld.locator("xpath=ancestor::*[contains(@class,'feld')][1]").or(feld).first());
    await film.bild();
    await entmarkiere(tel);
    film.fertig();
    await verwerfen(tel);
  },
};

// ------------------------------------------------------------------ Ablauf

await anmelden();
mkdirSync(ZIEL, { recursive: true });
const [paula, max] = [await patientId("Beispiel", "Paula"), await patientId("Mustermann", "Max")];
// Deutsche Oberfläche auch in den Datumsfeldern des Browsers (TT.MM.JJJJ statt MM/TT/JJJJ)
const browser = await chromium.launch({ ...(CHROMIUM ? { executablePath: CHROMIUM } : {}), args: ["--lang=de-DE"],
  env: { ...process.env, LANG: "de_DE.UTF-8", LANGUAGE: "de" } });
const pc = await seite(browser, PC);
const tel = await seite(browser, TELEFON);
let fehler = 0;
try {
  for (const [name, erzeugen] of Object.entries(BILDER)) {
    if (!gewaehlt(name)) continue;
    process.stdout.write(`${name} … `);
    try {
      await erzeugen({ pc, tel, paula, max });
      console.log("ok");
    } catch (e) {
      fehler += 1;
      console.log(`FEHLER: ${process.env.EPM_AUSFUEHRLICH ? e.message : e.message.split("\n")[0]}`);
      await pc.keyboard.press("Escape").catch(() => {});
      await tel.keyboard.press("Escape").catch(() => {});
    }
  }
} finally {
  await browser.close();
  rmSync(ARBEIT, { recursive: true, force: true });
}

// Übersicht: Datei, Größe, Maße (für width/height in backend/hilfe/inhalt.py; Telefonbilder in halber Größe angeben)
const masse = (datei) => {
  const kopf = execFileSync(PYTHON, ["-c", "import sys;from PIL import Image;i=Image.open(sys.argv[1]);print(i.width,i.height)", datei]);
  return String(kopf).trim().replace(" ", "×");
};
let summe = 0;
for (const datei of readdirSync(ZIEL).sort()) {
  const groesse = statSync(join(ZIEL, datei)).size;
  summe += groesse;
  const neu = ergebnisse.includes(datei) ? "neu" : "   ";
  console.log(`${neu}  ${datei.padEnd(40)} ${(groesse / 1024).toFixed(0).padStart(5)} KB  ${masse(join(ZIEL, datei))}`);
}
console.log(`Zusammen ${(summe / 1024 / 1024).toFixed(2)} MB in ${ZIEL}`);
process.exit(fehler ? 1 : 0);
