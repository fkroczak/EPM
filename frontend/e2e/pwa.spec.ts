/** EPM als App (PWA, Festlegung 08.10.2026, F135): Manifest, Symbole, Service Worker ohne Patientendaten im
 *  Zwischenspeicher, „Keine Verbindung“ ohne Netz, Karte „EPM als App“ unter Mein Konto. */
import { expect, test } from "@playwright/test";
import { zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

test("Manifest und Symbole: installierbar mit Name, Startadresse, Farben und Kurzbefehlen", async ({ page }) => {
  await page.goto("/");
  const href = await page.locator('link[rel="manifest"]').getAttribute("href");
  expect(href).toBe("/manifest.webmanifest");
  const antwort = await page.request.get(href!);
  expect(antwort.ok()).toBe(true);
  const m = await antwort.json();
  expect(m.short_name).toBe("EPM");
  expect(m.start_url).toBe("/");
  expect(m.display).toBe("standalone");
  expect(m.theme_color).toBe("#251F53");
  expect(m.shortcuts.map((s: { url: string }) => s.url)).toContain("/infusionsplaene?gruppe=entwuerfe");
  for (const icon of m.icons as { src: string; purpose: string }[]) {
    const bild = await page.request.get(icon.src);
    expect(bild.ok(), icon.src).toBe(true);
    expect(bild.headers()["content-type"]).toMatch(/image\//);
  }
  expect(m.icons.some((i: { purpose: string; sizes: string }) => i.purpose === "maskable" && i.sizes === "512x512")).toBe(true);
  const apple = await page.locator('link[rel="apple-touch-icon"]').getAttribute("href");
  expect((await page.request.get(apple!)).ok()).toBe(true);
  // der Service Worker wird nie zwischengespeichert (sonst kämen Updates nicht an)
  const sw = await page.request.get("/sw.js");
  expect(sw.ok()).toBe(true);
  expect(sw.headers()["content-type"]).toMatch(/javascript/);
  expect(sw.headers()["cache-control"]).toMatch(/no-cache/);
});

test("Service Worker: nur Programmdateien im Zwischenspeicher, ohne Netz „Keine Verbindung“", async ({ page, context }) => {
  await page.goto("/patienten");
  await expect(page.getByTestId("patientenliste")).toBeVisible();
  const aktiv = await page.evaluate(async () => {
    if (!("serviceWorker" in navigator)) return "fehlt";
    const r = await Promise.race([navigator.serviceWorker.ready.then(() => "bereit"),
      new Promise<string>((ok) => setTimeout(() => ok("zeit"), 15_000))]);
    return r;
  });
  expect(aktiv).toBe("bereit");
  // einmal neu laden, damit der Service Worker die Seite kontrolliert und Dateien zwischenspeichert
  await page.reload();
  await expect(page.getByTestId("patientenliste")).toBeVisible();
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  await page.getByTestId("patientenliste").getByRole("link").first().click();
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
  const gespeichert = await page.evaluate(async () => {
    const adressen: string[] = [];
    for (const name of await caches.keys()) {
      for (const a of await (await caches.open(name)).keys()) adressen.push(new URL(a.url).pathname);
    }
    return adressen;
  });
  expect(gespeichert).toContain("/offline.html");
  expect(gespeichert.some((p) => p.startsWith("/assets/"))).toBe(true);
  // keine Patientendaten, keine Seiten, keine Dokumente
  expect(gespeichert.filter((p) => p.startsWith("/api/") || p.startsWith("/_geschuetzt/") || p === "/" || p.endsWith(".html") && p !== "/offline.html"))
    .toEqual([]);

  await context.setOffline(true);
  await page.goto("/patienten").catch(() => undefined);
  await expect(page.getByRole("heading", { name: "Keine Verbindung zu EPM" })).toBeVisible();
  await expect(page.getByText("VPN")).toBeVisible();
  await context.setOffline(false);
  await page.getByRole("link", { name: "Erneut versuchen" }).click();
  await expect(page.getByTestId("angemeldet-als")).toBeVisible();
});

test("Mein Konto: Karte „EPM als App“ mit Hinweis zur Installation", async ({ page }) => {
  await page.goto("/konto");
  const karte = page.getByTestId("app-karte");
  await expect(karte).toContainText("EPM als App");
  await expect(karte).toContainText("keine Patientendaten");
});
