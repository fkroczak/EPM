/** Menüpunkt „Infusionspläne“ (Wunsch 02.10.2026): alle Pläne aller Patienten, Gruppen, Suche, PDF, neuer Plan. */
import { expect, test } from "@playwright/test";
import { zustand } from "./hilfen";

test.use({ storageState: zustand("mediziner") });

test("Infusionspläne: Gruppen, Suche, gespeicherte PDF, Öffnen in der Akte", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Infusionspläne" }).click();
  await expect(page.getByRole("heading", { name: "Infusionspläne", level: 1 })).toBeVisible();
  const tabelle = page.getByTestId("plan-uebersicht");
  await expect(tabelle).toBeVisible();
  // Zur Freigabe: offener Entwurf bei Musterfrau (Musterdaten)
  await page.getByRole("button", { name: /^Zur Freigabe/ }).click();
  await expect(page).toHaveURL(/gruppe=entwuerfe/);
  await expect(tabelle.getByRole("row", { name: /Musterfrau, Erika/ })).toContainText("Entwurf");
  // älter als 12 Monate: Probe, Jonas
  await page.getByRole("button", { name: /^Älter als 12 Mon\./ }).click();
  const alt = tabelle.getByRole("row", { name: /Probe, Jonas/ });
  await expect(alt).toContainText("aktuell, alt");
  await alt.getByRole("button", { name: "PDF" }).click();
  await expect(page.getByTestId("pdf-pruefung")).toContainText("Prüfsumme stimmt");
  await page.keyboard.press("Escape");
  // Suche nach Name
  await page.getByRole("button", { name: /^Alle/ }).click();
  await page.getByLabel("Patient suchen").fill("Mustermann");
  await expect(tabelle.getByRole("row", { name: /Musterfrau/ })).toHaveCount(0);
  await expect(tabelle.getByRole("row", { name: /Mustermann, Max/ }).first()).toBeVisible();
  await tabelle.getByRole("link", { name: /Plan von Mustermann, Max öffnen/ }).first().click();
  await expect(page).toHaveURL(/\/patienten\/\d+\/plaene\?plan=\d+$/);
  await expect(page.getByTestId("planliste")).toBeVisible();
});

test("Infusionspläne: neuer Plan – vorhandener Entwurf wird geöffnet statt doppelt angelegt", async ({ page }) => {
  await page.goto("/infusionsplaene");
  await page.getByRole("button", { name: "Neuer Plan" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Patient").fill("Musterfrau");
  await dialog.getByRole("option", { name: /Musterfrau, Erika/ }).click();
  await expect(dialog.getByText("gibt es schon einen Entwurf")).toBeVisible();
  await dialog.getByRole("button", { name: "Entwurf öffnen" }).click();
  await expect(page).toHaveURL(/\/patienten\/\d+\/plaene\/\d+\/bearbeiten$/);
});

test("Infusionspläne: Betrachter sieht die Übersicht ohne „Neuer Plan“", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/infusionsplaene");
  await expect(page.getByTestId("plan-uebersicht")).toBeVisible();
  await expect(page.getByRole("button", { name: "Neuer Plan" })).toHaveCount(0);
  await ctx.close();
});
