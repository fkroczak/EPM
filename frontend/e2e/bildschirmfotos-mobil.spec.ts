/** Bildschirmfotos am Telefon (nur mit EPM_BILDER=1, beim manuellen Start des Workflows) – Festlegung 08.10.2026. */
import { mkdirSync } from "node:fs";
import { devices, expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { OHNE_ANMELDUNG, zustand } from "./hilfen";

test.skip(!process.env.EPM_BILDER, "nur beim manuellen Start (EPM_BILDER=1)");
const { defaultBrowserType: _browser, ...telefon } = devices["Pixel 7"];
test.use({ ...telefon, storageState: zustand("mediziner") });

const ORDNER = "e2e/bildschirmfotos";
const foto = async (page: Page, name: string, ganz = true) => {
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${ORDNER}/mobil-${name}.png`, fullPage: ganz });
};

test("Bildschirmfotos am Telefon: Start, Menü, Patienten, Akte, Pläne, Konto", async ({ page }) => {
  mkdirSync(ORDNER, { recursive: true });
  await page.goto("/");
  await expect(page.getByTestId("mobil-leiste")).toBeVisible();
  await foto(page, "start");
  await page.getByTestId("mobil-menue").click();
  await expect(page.getByTestId("schublade")).toBeVisible();
  await foto(page, "menue", false);
  await page.keyboard.press("Escape");
  await page.goto("/patienten");
  await expect(page.getByTestId("patientenliste")).toBeVisible();
  await foto(page, "patienten");
  await page.getByTestId("patientenliste").getByRole("link").first().click();
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
  await foto(page, "akte");
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /Infusionspläne/ }).click();
  await foto(page, "akte-plaene");
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /Kontakte/ }).click();
  await foto(page, "akte-kontakte");
  await page.getByTestId("mobil-notiz").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await foto(page, "notiz", false);
  await page.keyboard.press("Escape");
  await page.goto("/infusionsplaene?gruppe=alle");
  await expect(page.getByTestId("plan-uebersicht")).toBeVisible();
  await foto(page, "infusionsplaene");
  await page.goto("/kalender");
  await foto(page, "kalender");
  await page.goto("/konto");
  await foto(page, "konto");
});

test("Bildschirmfotos am Telefon: Anmeldung", async ({ browser }) => {
  mkdirSync(ORDNER, { recursive: true });
  const ctx = await browser.newContext({ ...telefon, storageState: OHNE_ANMELDUNG, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Anmelden" })).toBeVisible();
  await foto(page, "anmeldung", false);
  await ctx.close();
});
