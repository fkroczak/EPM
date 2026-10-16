/**
 * Statistik (F193): Menüpunkt nur mit „Statistik ansehen“ (Festlegung 16.10.2026: ab „Mitarbeiter (erweitert)“ –
 * Mediziner und Admin ja, Mitarbeiter und Betrachter nein), Kacheln mit Vorjahr, Diagramme, Zeitraum, CSV mit BOM,
 * PDF, Audit-Log; auf 1920 × 1080 ohne Scrollen. Genaue Zahlen prüft das Backend (patienten.test_statistik) – hier
 * haben die Tests davor schon Akten angelegt, die Zahlen stehen also nicht fest.
 */
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mediziner") });

test("Statistik: Menüpunkt je Recht, Kacheln und Diagramme ohne Scrollen, Zeitraum, CSV und PDF im Audit-Log", async ({ page, browser }) => {
  // eine echte Akte dieses Jahres, damit „Neuaufnahmen“ nicht 0 ist (Testpatienten zählen nie)
  const api = await apiAls("mitarbeiter");
  await api.post("patienten/", { nachname: eindeutig("Statistik"), vorname: "Stella", geburtsdatum: "1958-04-03" });
  await api.ende();

  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Hauptnavigation" });
  // eingeordnet direkt nach „Infusionspläne“, die übrigen Punkte in ihrer Reihenfolge
  const texte = (await nav.getByRole("link").allInnerTexts()).map((t) => t.trim()).filter(Boolean);
  expect(texte.slice(0, 5)).toEqual(["Start", "Patienten", "Kalender", "Infusionspläne", "Statistik"]);
  await nav.getByRole("link", { name: "Statistik" }).click();
  await expect(page).toHaveURL(/\/statistik/);
  await expect(page.getByRole("heading", { name: "Statistik" })).toBeVisible();

  const jahr = new Date().getFullYear();
  const kacheln = page.getByTestId("statistik-kacheln");
  await expect(kacheln.getByTestId("kennzahl-aktiv")).toContainText("Aktive Patienten zum Stichtag");
  await expect(kacheln.getByTestId("kennzahl-aktiv")).toContainText(`Vorjahr ${jahr - 1}`);
  // Neuaufnahmen: mindestens die eben angelegte Akte – „< 5“ oder eine Zahl, nie 0
  await expect(kacheln.getByTestId("kennzahl-neuaufnahmen").locator(".num").first()).not.toHaveText("0");
  for (const name of ["abschlussanlass", "versorger", "altersgruppen", "katheter"]) {
    await expect(page.getByTestId(`statistik-${name}`)).toBeVisible();
  }
  await expect(page.getByTestId("statistik-altersgruppen")).toContainText("80 Jahre und älter");
  await expect(page.getByTestId("statistik-regel")).toContainText("< 5");
  // keine Namen in der Auswertung
  await expect(page.locator("main")).not.toContainText("Stella");
  // 1080p ohne Scrollen
  const zuHoch = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);
  expect(zuHoch).toBeLessThanOrEqual(1);

  // Quartal wählen: Vergleich ist das Vorquartal
  await page.getByRole("group", { name: "Zeitraum" }).getByRole("button", { name: "Quartal" }).click();
  await page.getByRole("group", { name: "Quartal" }).getByRole("button", { name: "1. Q." }).click();
  await expect(page).toHaveURL(/art=quartal.*quartal=1/);
  await expect(kacheln.getByTestId("kennzahl-aktiv")).toContainText(`Vorquartal (4. Quartal ${jahr - 1})`);
  await page.getByRole("group", { name: "Zeitraum" }).getByRole("button", { name: "Kalenderjahr" }).click();

  // CSV: Semikolon, UTF-8 mit BOM, im Audit-Log
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "CSV" }).click()]);
  expect(download.suggestedFilename()).toMatch(/^Statistik-.*\.csv$/);
  const roh = readFileSync((await download.path())!);
  expect([...roh.subarray(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
  const text = roh.toString("utf8").slice(1);
  expect(text).toContain(`Bereich;Merkmal;${jahr}`);
  expect(text).toContain("Kennzahl;Aktive Patienten zum Stichtag;");
  expect(text).not.toContain("Stella");

  // PDF im Fenster
  await page.getByRole("button", { name: "PDF" }).click();
  await expect(page.getByTestId("pdf-dialog").getByTestId("pdf-leser").locator("canvas").first()).toBeVisible({ timeout: 30_000 });
  await page.keyboard.press("Escape");

  const med = await apiAls("mediziner");
  const exporte = await med.get("protokoll/?gruppe=export&search=Statistik");
  const formate = exporte.results.slice(0, 5).map((e: { beschreibung: string }) => e.beschreibung);
  expect(formate.some((b: string) => b.startsWith("Statistik als CSV"))).toBeTruthy();
  expect(formate.some((b: string) => b.startsWith("Statistik als PDF"))).toBeTruthy();
  await med.ende();

  // Mitarbeiter und Betrachter: kein Menüpunkt, die Adresse führt zur Startseite, die API lehnt ab
  for (const rolle of ["mitarbeiter", "betrachter"] as const) {
    const ctx = await browser.newContext({ storageState: zustand(rolle), ignoreHTTPSErrors: true });
    const p = await ctx.newPage();
    await p.goto("/");
    await expect(p.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Statistik" })).toHaveCount(0);
    await p.goto("/statistik");
    await expect(p).toHaveURL(/\/$/);
    const r = await ctx.request.get("/api/statistik/");
    expect(r.status()).toBe(403);
    await ctx.close();
  }
});
