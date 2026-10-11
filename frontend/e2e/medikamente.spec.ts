/**
 * Medikamentenplan (Kundenwunsch 11.10.2026: „Medikamentenplan als neuer Punkt beim Patienten“): eigener Reiter nach
 * „Diagnosen“, Medikament eintragen, im Plan sehen, absetzen (bleibt unter „Abgesetzt“), Medikationsplan als PDF.
 * Am Telefon stehen die Medikamente als Karten – nichts ragt seitlich heraus.
 *
 * Eigene Akte je Test: Die Musterdaten bleiben für die anderen Tests unverändert.
 */
import { devices, expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

async function neueAkte(medikamente: Record<string, unknown>[] = []) {
  const api = await apiAls("mitarbeiter");
  const p = await api.post("patienten/", { nachname: eindeutig("Medi"), vorname: "Mia", geburtsdatum: "1966-06-06" }) as
    { id: number; nachname: string };
  for (const m of medikamente) await api.post("medikamente/", { patient: p.id, ...m });
  await api.ende();
  return p;
}

async function oeffnen(page: Page, id: number) {
  await page.goto(`/patienten/${id}/medikamente`);
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
  await expect(page.getByTestId("medikamente")).toBeVisible();
}

test("Medikament eintragen, im Plan sehen und absetzen", async ({ page }) => {
  const p = await neueAkte();
  await page.goto(`/patienten/${p.id}`);
  // Reiter gleich nach „Diagnosen“
  const reiter = page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link");
  await expect(reiter.filter({ hasText: /^Medikamente/ })).toBeVisible();
  const namen = await reiter.allTextContents();
  const diagnosen = namen.findIndex((n) => n.startsWith("Diagnosen"));
  expect(namen[diagnosen + 1]).toMatch(/^Medikamente/);
  await reiter.nth(diagnosen + 1).click();
  await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}/medikamente$`));
  const plan = page.getByTestId("medikamente");
  await expect(plan).toContainText("Keine Dauermedikation eingetragen.");

  await plan.getByRole("button", { name: "Medikament", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Neues Medikament" })).toBeVisible();
  await dialog.getByLabel("Wirkstoff").fill("Pantoprazol");
  await dialog.getByLabel("Handelsname").fill("Pantozol");
  await dialog.getByLabel("Stärke").fill("40 mg");
  await dialog.getByLabel("Darreichungsform").fill("Tablette");
  await dialog.getByLabel("morgens", { exact: true }).fill("1");
  await dialog.getByLabel("abends", { exact: true }).fill("1");
  await expect(dialog).toContainText("1 – 0 – 1 – 0");
  await dialog.getByLabel("Einheit").fill("Stück");
  await dialog.getByLabel("Grund").fill("Magenschutz");
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toHaveCount(0);

  const zeile = page.getByTestId("dauermedikation").getByTestId("medikament-zeile");
  await expect(zeile).toHaveCount(1);
  await expect(zeile).toContainText("Pantoprazol");
  await expect(zeile).toContainText("Pantozol");
  await expect(zeile).toContainText("1 – 0 – 1 – 0");
  await expect(zeile).toContainText("Magenschutz");
  await expect(page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Medikamente/ })).toContainText("1");

  // Bedarfsmedikation ohne Schema
  await plan.getByRole("button", { name: "Medikament", exact: true }).click();
  await dialog.getByLabel("Wirkstoff").fill("Loperamid");
  await dialog.getByLabel("Stärke").fill("2 mg");
  await dialog.getByLabel(/^Bei Bedarf/).check();
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByTestId("bedarfsmedikation").getByTestId("medikament-zeile")).toContainText("bei Bedarf");

  // Absetzen mit Grund: verschwindet aus dem Plan, bleibt unter „Abgesetzt“
  await zeile.getByRole("button", { name: "Pantoprazol absetzen" }).click();
  const frage = page.getByRole("dialog");
  await frage.getByLabel("Grund (freiwillig)").fill("keine Beschwerden mehr");
  await frage.getByTestId("bestaetigen").click();
  await expect(frage).toHaveCount(0);
  await expect(page.getByTestId("dauermedikation")).toHaveCount(0);
  await expect(plan).toContainText("Keine Dauermedikation eingetragen.");
  await plan.getByTestId("abgesetzt-umschalten").click();
  const abgesetzt = page.getByTestId("abgesetzt").getByTestId("medikament-zeile");
  await expect(abgesetzt).toContainText("Pantoprazol");
  await expect(abgesetzt).toContainText("keine Beschwerden mehr");
  await expect(abgesetzt).toContainText(/\d{2}\.\d{2}\.\d{4}/);

  // Medikationsplan als PDF
  await plan.getByRole("button", { name: "Medikationsplan als PDF" }).click();
  await expect(page.getByTestId("pdf-dialog")).toBeVisible();
  await expect(page.getByRole("button", { name: "Herunterladen" })).toBeEnabled({ timeout: 20_000 });
});

test.describe("am Telefon", () => {
  const { defaultBrowserType: _browser, ...telefon } = devices["Pixel 7"];
  test.use({ ...telefon, viewport: { width: 375, height: 760 } });

  test("Medikamente als Karten, nichts ragt heraus", async ({ page }) => {
    const p = await neueAkte([
      { wirkstoff: "Colecalciferol", handelsname: "Dekristol", staerke: "20 000 IE", darreichungsform: "Kapsel",
        dosierung_frei: "1× wöchentlich montags", einheit: "Stück", grund: "Vitamin-D-Mangel",
        hinweise: "mit einer fetthaltigen Mahlzeit einnehmen, nicht zusammen mit Colestyramin" },
      { wirkstoff: "Pantoprazol", staerke: "40 mg", morgens: "1", mittags: "0", abends: "1", nachts: "0", einheit: "Stück" },
    ]);
    await oeffnen(page, p.id);
    const karten = page.getByTestId("dauermedikation").getByTestId("medikament-karte");
    await expect(karten).toHaveCount(2);
    await expect(karten.filter({ hasText: "Pantoprazol" })).toContainText("1 – 0 – 1 – 0");
    await expect(page.getByTestId("dauermedikation").getByTestId("medikament-zeile").first()).toBeHidden();
    const { breite, inhalt } = await page.evaluate(() => ({ breite: window.innerWidth, inhalt: document.documentElement.scrollWidth }));
    expect(inhalt, `Seite ${inhalt}px breit bei ${breite}px`).toBeLessThanOrEqual(breite + 1);
  });
});
