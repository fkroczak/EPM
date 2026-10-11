/**
 * Zwei Firmen in einem EPM (Anforderung 11.10.2026): DSKM und Regeneration Clinic. Umschalter unter dem Logo, Akten nur
 * der aktiven Firma, gemeinsame Akte mit Firma an jedem Eintrag, Auswahl der betreuenden Firmen mit Einwilligung.
 *
 * Musterdaten: Max Mustermann gehört beiden Firmen, Hanna Test nur der RG, alle anderen nur der DSKM.
 * Der Testzugang (e2e.test) ist in beiden Firmen Mediziner (vorbereiten.py). Am Ende steht er wieder in der DSKM.
 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, zustand } from "./hilfen";

test.use({ storageState: zustand("test") });

async function firmaSetzen(kuerzel: string) {
  const api = await apiAls("test");
  await api.post("auth/firma/", { firma: kuerzel });
  await api.ende();
}

async function namen(page: Page) {
  await page.goto("/patienten");
  await expect(page.getByRole("table").first()).toBeVisible();
  return page.getByRole("table").first().innerText();
}

test.afterEach(async () => { await firmaSetzen("dskm"); });

test("Umschalter unter dem Logo zeigt nur die Akten der aktiven Firma", async ({ page }) => {
  await firmaSetzen("dskm");
  let liste = await namen(page);
  expect(liste).toContain("Mustermann");
  expect(liste).toContain("Musterfrau");
  expect(liste).not.toContain("Hanna");
  const schalter = page.getByTestId("seitenleiste").getByRole("group", { name: "Firma" });
  await expect(schalter.getByRole("button", { name: "DSKM" })).toHaveAttribute("aria-pressed", "true");
  await schalter.getByRole("button", { name: "RG" }).click();
  await expect(page.getByText("Du arbeitest jetzt für Regeneration Clinic.")).toBeVisible();
  await expect(schalter.getByRole("button", { name: "RG" })).toHaveAttribute("aria-pressed", "true");
  liste = await namen(page);
  expect(liste).toContain("Mustermann");
  expect(liste).toContain("Hanna");
  expect(liste).not.toContain("Musterfrau");
});

test("gemeinsame Akte: Firmen im Kopf und an jedem Eintrag, Auswahl mit Einwilligung", async ({ page }) => {
  await firmaSetzen("dskm");
  const api = await apiAls("test");
  const treffer = (await api.get("patienten/?test=nur&suche=Musterfrau") as { results: { id: number; vorname: string }[] })
    .results.find((p) => p.vorname === "Erika")!;
  const geteilt = (await api.get("patienten/?test=nur&suche=Mustermann") as { results: { id: number; vorname: string }[] })
    .results.find((p) => p.vorname === "Max")!;
  await api.ende();

  await page.goto(`/patienten/${geteilt.id}/kontakte`);
  await expect(page.getByTestId("akte-firmen")).toHaveText("DSKM · RG");
  await expect(page.getByTestId("firma-marke").filter({ hasText: "RG" }).first()).toBeVisible();

  // Erika Musterfrau zusätzlich der RG zuordnen: ohne Datum der Einwilligung geht es nicht
  await page.goto(`/patienten/${treffer.id}`);
  await page.getByTestId("akte-firmen").click();
  const dialog = page.getByRole("dialog", { name: "Betreuende Firmen" });
  await dialog.getByTestId("firma-rg").check();
  await dialog.getByTestId("firmen-speichern").click();
  await expect(dialog.getByText("Bitte das Datum der Einwilligung angeben.")).toBeVisible();
  // Abbrechen: die Musterdaten bleiben unverändert
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  await expect(page.getByTestId("akte-firmen")).toHaveText("DSKM");
});

test("Telefon: Umschalter in der Schublade, Firma im Kopf, nichts ragt heraus", async ({ page }) => {
  await firmaSetzen("dskm");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/patienten");
  await expect(page.getByTestId("mobil-firma")).toHaveText("DSKM");
  await page.getByRole("button", { name: /Menü/ }).last().click();
  const schublade = page.getByTestId("schublade");
  await schublade.getByRole("group", { name: "Firma" }).getByRole("button", { name: "RG" }).click();
  await expect(page.getByTestId("mobil-firma")).toHaveText("RG");
  const breite = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(breite).toBeLessThanOrEqual(390);
});
