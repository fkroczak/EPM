/** Menüpunkt „Infusionspläne“ (Wunsch 02.10.2026): alle Pläne aller Patienten, Gruppen, Suche, PDF, neuer Plan. */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

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
  // Status mit Frist beim Überfahren (Fehlerliste 02.10.2026, 1.2); „Erstellt“/„Freigegeben“ immer als Datum (1.1)
  await expect(alt.getByTestId("plan-frist")).toHaveAttribute("title", /^Frist abgelaufen am \d{2}\.\d{2}\.\d{4}: gültig seit \d{2}\.\d{2}\.\d{4}, älter als 12 Monate/);
  await expect(alt).not.toContainText(/heute|gestern|vor \d+/);
  await expect(alt.getByRole("cell").nth(6)).toContainText(/^\d{2}\.\d{2}\.\d{4}/);
  await alt.getByRole("button", { name: "PDF" }).click();
  await expect(page.getByTestId("pdf-pruefung")).toContainText("Prüfsumme stimmt");
  await page.keyboard.press("Escape");
  // Suche nach Name
  await page.getByRole("button", { name: /^Aktuell/ }).click();
  await expect(tabelle.getByTestId("plan-frist").first()).toHaveAttribute("title", /^Frist: \d{2}\.\d{2}\.\d{4} – ab dann gilt der Plan als alt/);
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

test("Kein Infusionsplan nötig: bestätigen unterdrückt den Hinweis, aufheben bringt ihn zurück", async ({ page }) => {
  const api = await apiAls("mediziner");
  const p = await api.post("patienten/", { nachname: eindeutig("Ohneplan"), vorname: "Olaf", geburtsdatum: "1966-06-16" });
  const hinweise = async () => {
    const zeile = (await api.get(`patienten/?suche=${encodeURIComponent(p.nachname)}`)).results[0];
    return (zeile.kennzahlen?.hinweise ?? []).map((h: { art: string }) => h.art);
  };
  expect(await hinweise()).toContain("ohne_plan");
  await page.goto(`/patienten/${p.id}`);
  await expect(page.getByTestId("aktueller-plan").getByTestId("ohne-plan")).toBeVisible();
  await page.goto(`/patienten/${p.id}/plaene`);
  await page.getByTestId("ohne-plan").getByRole("button", { name: "Kein Plan nötig" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Grund").fill("nur orale Ernährung");
  await dialog.getByRole("button", { name: "Bestätigen" }).click();
  await expect(page.getByText("Bestätigt: kein Infusionsplan nötig.")).toBeVisible();
  await expect(page.getByTestId("kein-plan")).toContainText("nur orale Ernährung");
  await expect(page.getByTestId("aktenkopf")).toContainText("nicht nötig");
  expect(await hinweise()).not.toContain("ohne_plan");
  // im Verlauf der Akte
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Verlauf/ }).click();
  await expect(page.getByTestId("verlauf")).toContainText("Kein Infusionsplan nötig");
  // aufheben
  await page.goto(`/patienten/${p.id}/plaene`);
  await page.getByTestId("kein-plan").getByRole("button", { name: "Aufheben" }).click();
  await expect(page.getByTestId("ohne-plan")).toBeVisible();
  expect(await hinweise()).toContain("ohne_plan");
  await api.ende();
});
