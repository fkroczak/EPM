/** Globaler Kalender (Wunsch 02.10.2026): Termine aller Patienten, Überfälliges, Fälligkeiten; Termin anlegen und abhaken. */
import { expect, test } from "@playwright/test";
import { merken, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

function tagIn(tage: number) {
  return new Date(Date.now() + tage * 86_400_000).toLocaleDateString("sv-SE", { timeZone: "Europe/Berlin" });
}

test("Kalender: Menüpunkt, Überfälliges und berechnete Fälligkeiten", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Kalender" }).click();
  await expect(page.getByRole("heading", { name: "Kalender", level: 1 })).toBeVisible();
  await expect(page.getByTestId("kalender-monat")).toBeVisible();
  // Musterdaten: Rückruf bei Musterfrau vor 3 Tagen ist überfällig; der Plan von Probe, Jonas ist älter als 12 Monate
  await expect(page.getByTestId("ueberfaellig-termine")).toContainText("Musterfrau, Erika");
  await expect(page.getByTestId("ueberfaellig-plan")).toContainText("Probe, Jonas");
  await page.getByTestId("ueberfaellig-plan").getByRole("button", { name: /Plan prüfen: Probe, Jonas/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Infusionsplan prüfen" })).toBeVisible();
  await expect(dialog.getByTestId("eintrag-details")).toContainText("gültig seit");
  await dialog.getByRole("link", { name: "Pläne öffnen" }).click();
  await expect(page).toHaveURL(/\/patienten\/\d+\/plaene$/);
  // Woche und Liste
  await page.goto("/kalender?ansicht=woche");
  await expect(page.getByTestId("kalender-woche")).toBeVisible();
  await expect(page.getByTestId("kalender-titel")).toContainText("KW");
  await page.getByRole("button", { name: "Liste" }).click();
  await expect(page.getByTestId("kalender-liste").or(page.getByText("In diesem Zeitraum gibt es keine Einträge."))).toBeVisible();
  // Feiertage (NRW): Dezember mit beiden Weihnachtstagen
  await page.goto(`/kalender?datum=${new Date().getFullYear()}-12-01`);
  await expect(page.getByTestId(`tag-${new Date().getFullYear()}-12-25`)).toContainText("1. Weihnachtstag");
});

test("Kalender: Termin an einem Tag anlegen, öffnen, abhaken; Erledigte ausblenden", async ({ page }) => {
  const ziel = tagIn(10);
  await page.goto(`/kalender?datum=${ziel}`);
  await page.getByTestId(`tag-${ziel}`).click();
  await page.getByTestId("tagesliste").getByRole("button", { name: "Termin", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Datum")).toHaveValue(ziel);
  await dialog.getByLabel("Patient").fill("Beispiel");
  await dialog.getByRole("option", { name: /Beispiel, Paula/ }).click();
  await dialog.getByLabel("Art").selectOption("wiedervorlage");
  await dialog.getByLabel("Uhrzeit").fill("09:15");
  await dialog.getByLabel("Titel").fill("E2E Kalender Kontrolle");
  await dialog.getByRole("button", { name: "Termin speichern" }).click();
  await expect(dialog).toHaveCount(0);
  const eintrag = page.getByTestId(`tag-${ziel}`).getByRole("button", { name: /09:15 Wiedervorlage: Beispiel, Paula – E2E Kalender Kontrolle/ });
  await expect(eintrag).toBeVisible();
  await eintrag.click();
  await expect(page.getByRole("dialog").getByTestId("eintrag-details")).toContainText("Wiedervorlage");
  await page.getByRole("dialog").getByRole("button", { name: "Erledigt" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByTestId(`tag-${ziel}`).getByRole("button", { name: /E2E Kalender Kontrolle \(erledigt\)/ })).toBeVisible();
  await page.getByLabel("Erledigte zeigen").uncheck();
  await expect(page.getByTestId(`tag-${ziel}`).getByRole("button", { name: /E2E Kalender Kontrolle/ })).toHaveCount(0);
  merken("kalender", { datum: ziel, titel: "E2E Kalender Kontrolle" });
});

test("Kalender: Betrachter sieht alles, legt aber nichts an", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/kalender");
  await expect(page.getByTestId("kalender-monat")).toBeVisible();
  await expect(page.getByTestId("ueberfaellig-termine")).toContainText("Musterfrau, Erika");
  await expect(page.getByRole("button", { name: "Termin", exact: true })).toHaveCount(0);
  await page.getByTestId("ueberfaellig-termine").getByRole("button", { name: /Musterfrau, Erika/ }).first().click();
  await expect(page.getByRole("dialog").getByRole("link", { name: "Akte öffnen" })).toBeVisible();
  await expect(page.getByRole("dialog").getByRole("button", { name: "Erledigt" })).toHaveCount(0);
  await ctx.close();
});
