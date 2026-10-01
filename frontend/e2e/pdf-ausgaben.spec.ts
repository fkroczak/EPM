/** PDF-Ausgaben mit festem Aufbau: Verlauf der Akte (F24) und Audit-Log für einen Zeitraum (F59). */
import { expect, test } from "@playwright/test";
import { apiAls, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

test("Verlauf der Akte als PDF, mit Bereichsfilter", async ({ page }) => {
  await page.goto("/patienten");
  await page.getByTestId("patientenliste").getByRole("link", { name: "Musterfrau, Erika" }).click();
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Verlauf" }).click();
  await page.getByRole("group", { name: "Bereich" }).getByRole("button", { name: "Gewicht", exact: true }).click();
  const antwort = page.waitForResponse((a) => /\/verlauf\/pdf\/\?bereich=gewichte$/.test(a.url()) && a.ok());
  await page.getByRole("button", { name: "Verlauf als PDF" }).click();
  expect((await antwort).headers()["content-type"]).toBe("application/pdf");
  await expect(page.getByTestId("pdf-dialog").getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
});

test("Audit-Log für den gewählten Zeitraum als PDF; der Export steht danach im Audit-Log", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("admin"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/admin/audit-log");
  const antwort = page.waitForResponse((a) => a.url().includes("/api/protokoll/pdf/") && a.ok());
  await page.getByRole("button", { name: "Zeitraum als PDF" }).click();
  expect((await antwort).headers()["content-type"]).toBe("application/pdf");
  await expect(page.getByTestId("pdf-dialog").getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  const api = await apiAls("admin");
  const exporte = (await api.get("protokoll/?gruppe=export&seitengroesse=50")).results;
  const arten = exporte.map((e: { details: { was: string } }) => e.details.was);
  expect(arten).toContain("Audit-Log");
  expect(arten).toContain("Verlauf");
  await api.ende();
  await ctx.close();
});
