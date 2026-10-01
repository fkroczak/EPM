/** Bildschirmgrößen: unter 1440 px Seitenleiste mit Symbolen, unter 1280 px rutschen rechte Spalten nach unten. */
import { expect, test } from "@playwright/test";
import { zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

test("15-Zoll-Laptop: Seitenleiste als Symbolleiste, Navigation bleibt bedienbar", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  const leiste = page.locator("aside").first();
  const breite = (await leiste.boundingBox())?.width ?? 0;
  expect(breite).toBeLessThan(100);
  await page.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Patienten" }).click();
  await expect(page.getByRole("heading", { name: "Patienten", level: 1 })).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 900 });
  expect((await leiste.boundingBox())?.width ?? 0).toBeGreaterThan(200);
});

test("Unter 1280 px stehen die Karten der Akte untereinander", async ({ page }) => {
  await page.setViewportSize({ width: 1200, height: 900 });
  await page.goto("/patienten");
  await page.getByTestId("patientenliste").getByRole("link", { name: "Probe, Jonas" }).click();
  const gewicht = await page.getByTestId("gewichtskarte").boundingBox();
  const termine = await page.getByTestId("aktentermine").boundingBox();
  expect(gewicht && termine).toBeTruthy();
  expect(termine!.y).toBeGreaterThan(gewicht!.y + gewicht!.height - 1);

  await page.setViewportSize({ width: 1440, height: 900 });
  const g2 = await page.getByTestId("gewichtskarte").boundingBox();
  const t2 = await page.getByTestId("aktentermine").boundingBox();
  expect(t2!.x).toBeGreaterThan(g2!.x + g2!.width - 1);
});
