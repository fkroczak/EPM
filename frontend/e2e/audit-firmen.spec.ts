/**
 * Rundgang in beiden Firmen (Prüfung 11.10.2026): jede Seite der Navigation und jeder Reiter einer gemeinsamen Akte,
 * am Bildschirm und am Telefon – ohne Fehler in der Konsole, ohne fehlgeschlagene Anfrage, nichts ragt seitlich heraus.
 * Der Testzugang ist in DSKM und RGC Mediziner (vorbereiten.py); Max Mustermann gehört beiden Firmen.
 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, zustand } from "./hilfen";

test.use({ storageState: zustand("test") });
test.setTimeout(180_000);

async function firmaSetzen(kuerzel: string) {
  const api = await apiAls("test");
  await api.post("auth/firma/", { firma: kuerzel });
  await api.ende();
}

test.afterEach(async () => { await firmaSetzen("dskm"); });

async function seitenDerNavigation(page: Page, akte: number) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Hauptnavigation" });
  await expect(nav.getByRole("link").first()).toBeVisible();
  const ziele = await nav.getByRole("link").evaluateAll((els) => els.map((e) => e.getAttribute("href") ?? ""));
  await page.goto(`/patienten/${akte}`);
  const reiter = await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link")
    .evaluateAll((els) => els.map((e) => e.getAttribute("href") ?? ""));
  return [...new Set([...ziele, "/patienten/neu", ...reiter, "/hilfe", "/design", "/konto"])].filter((z) => z.startsWith("/"));
}

for (const [firma, kurz, leiste] of [["dskm", "DSKM", "rgb(255, 255, 255)"], ["rg", "RGC", "rgb(190, 201, 195)"]] as const) {
  test(`${kurz}: alle Seiten am Bildschirm und am Telefon ohne Fehler und ohne seitliches Herausragen`, async ({ page }) => {
    await firmaSetzen(firma);
    const api = await apiAls("test");
    const max = (await api.get("patienten/?test=nur&suche=Mustermann") as { results: { id: number; vorname: string }[] })
      .results.find((p) => p.vorname === "Max")!;
    await api.ende();
    const seiten = await seitenDerNavigation(page, max.id);
    expect(seiten.length).toBeGreaterThan(15);

    const fehler: string[] = [];
    let seite = "";
    page.on("console", (m) => { if (m.type() === "error") fehler.push(`${seite}: ${m.text()}`); });
    page.on("pageerror", (e) => fehler.push(`${seite}: ${e.message}`));
    page.on("response", (r) => { if (r.status() >= 400) fehler.push(`${seite}: ${r.status()} ${r.url()}`); });

    for (const [breite, hoehe] of [[1440, 900], [390, 844]] as const) {
      await page.setViewportSize({ width: breite, height: hoehe });
      for (const pfad of seiten) {
        seite = `${pfad} (${breite} px)`;
        await page.goto(pfad);
        await expect(page.locator("main h1").first()).toBeVisible();
        await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
        await expect(page.locator("html"), seite).toHaveAttribute("data-firma", firma);
        const ueber = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(ueber, `${seite} ragt seitlich heraus`).toBeLessThanOrEqual(0);
      }
    }
    // Erscheinung der Firma: Leiste und Logo
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(page.getByTestId("seitenleiste")).toHaveCSS("background-color", leiste);
    const logo = page.getByTestId("seitenleiste").getByRole("img", { name: firma === "rg" ? "Regeneration Clinic" : /Deutsche Stiftung|DSKM/ }).first();
    await expect(logo).toBeVisible();
    expect(await logo.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
    expect(fehler).toEqual([]);
  });
}
