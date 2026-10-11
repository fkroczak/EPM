/**
 * Musterdaten mit Befunden (Wunsch 11.10.2026): Die Testpatienten bringen Diagnosen mit ICD-Code, Laborbefunde und
 * BIA-Messungen mit (backend/patienten/testdaten.py). Geprüft wird, dass die Reiter sie zeigen – Werte außerhalb der
 * Referenz hervorgehoben – und dass die Akte ohne Labor und BIA (Test, Hanna) die Hinweise trägt.
 *
 * Nur lesend: Die Musterdaten bleiben für die anderen Tests unverändert.
 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, zustand } from "./hilfen";

test.use({ storageState: zustand("mediziner") });

type Treffer = { id: number; nachname: string; vorname: string };

/** Testpatient der Musterdaten (echte Akten aus dem Import können gleich heißen – deshalb ``test=nur``) */
async function testpatient(nachname: string, vorname: string) {
  const api = await apiAls("mediziner");
  const antwort = await api.get(`patienten/?test=nur&seitengroesse=200&suche=${encodeURIComponent(nachname)}`) as { results: Treffer[] };
  const liste = antwort.results;
  await api.ende();
  const p = liste.find((x) => x.nachname === nachname && x.vorname === vorname);
  expect(p, `Testpatient ${nachname}, ${vorname} fehlt – Musterdaten angelegt?`).toBeTruthy();
  return p!;
}

async function oeffnen(page: Page, id: number, reiter = "") {
  await page.goto(`/patienten/${id}${reiter}`);
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
}

test("Musterdaten: Diagnosen mit ICD-Code, auch beendete", async ({ page }) => {
  const erika = await testpatient("Musterfrau", "Erika");
  await oeffnen(page, erika.id, "/diagnosen");
  const liste = page.getByTestId("diagnoseliste");
  const zeilen = liste.getByTestId("diagnose-zeile");
  await expect(zeilen).toHaveCount(4);
  await expect(zeilen.first()).toContainText("K91.2G");
  await expect(zeilen.first()).toContainText("Kurzdarmsyndrom");
  // Verdacht ist eigens gekennzeichnet
  const verdacht = zeilen.filter({ hasText: "Störung des Magnesiumstoffwechsels" });
  await expect(verdacht).toContainText("E83.4V");
  await expect(verdacht).toContainText("V – Verdacht auf");
  await expect(zeilen.filter({ hasText: "Mesenterialinfarkt" })).toContainText("K55.0Z");

  // Mustermann: drei zutreffende, eine beendete (Infektion durch Katheter) unter „beendete anzeigen“
  const max = await testpatient("Mustermann", "Max");
  await oeffnen(page, max.id, "/diagnosen");
  await expect(liste.getByTestId("diagnose-zeile")).toHaveCount(3);
  await expect(liste).not.toContainText("T82.7");
  await liste.getByRole("button", { name: "1 beendete anzeigen" }).click();
  const beendet = liste.getByTestId("diagnose-zeile").filter({ hasText: "Infektion durch Katheter" });
  await expect(beendet).toContainText("T82.7G");
  await expect(beendet).toContainText(/beendet \d{2}\.\d{2}\.\d{4}/);
});

test("Musterdaten: Laborbefunde mit Verlauf, Werte außerhalb der Referenz hervorgehoben", async ({ page }) => {
  const erika = await testpatient("Musterfrau", "Erika");
  await oeffnen(page, erika.id, "/labor");
  const befunde = page.getByRole("list", { name: "Laborbefunde" }).getByRole("listitem");
  await expect(befunde).toHaveCount(4);
  await expect(befunde.first()).toContainText("Testlabor Münster (fiktiv)");
  // der jüngste Befund ist vorgewählt: Magnesium und Ferritin unter der Referenz, hervorgehoben
  const detail = page.getByTestId("labor-detail");
  await expect(detail).toContainText(/Laborbefund vom \d{2}\.\d{2}\.\d{4}/);
  await expect(detail).toContainText("Elektrolyte");
  const magnesium = detail.getByTitle("Magnesium", { exact: true }).locator("..");
  await expect(magnesium).toContainText("0,58");
  await expect(magnesium).toContainText("mmol/l");
  await expect(magnesium).toContainText("unter Referenz 0,66 – 1,07");
  await expect(magnesium.locator(".text-warn")).toHaveText("0,58");
  const ferritin = detail.getByTitle("Ferritin", { exact: true }).locator("..");
  await expect(ferritin).toContainText("unter Referenz 30 – 300");
  // ein Wert in der Referenz ist nicht hervorgehoben
  const natrium = detail.getByTitle("Natrium", { exact: true }).locator("..");
  await expect(natrium.locator(".text-warn")).toHaveCount(0);
  await expect(natrium).not.toContainText("Referenz");
  await expect(detail).toContainText("Magnesium erniedrigt und fallend");
  await expect(page.getByTestId("alter-labor")).toContainText(/Letzte Erfassung \d{2}\.\d{2}\.\d{4}/);
  // ein älterer Befund: Magnesium 0,71 liegt noch in der Referenz
  await befunde.nth(1).getByRole("button").click();
  await expect(page).toHaveURL(/befund=\d+/);
  const frueher = page.getByTestId("labor-detail").getByTitle("Magnesium", { exact: true }).locator("..");
  await expect(frueher).toContainText("0,71");
  await expect(frueher.locator(".text-warn")).toHaveCount(0);

  // Plan-Editor: Magnesium unter der Referenz mit fallendem Verlauf (F187)
  const api = await apiAls("mediziner");
  const entwuerfe = await api.get(`infusionsplaene/?patient=${erika.id}&status=entwurf`) as { results: { id: number }[] };
  await api.ende();
  await page.goto(entwuerfe.results.length
    ? `/patienten/${erika.id}/plaene/${entwuerfe.results[0].id}/bearbeiten`
    : `/patienten/${erika.id}/plaene/neu`);
  const mg = page.getByTestId("plan-hinweise").locator('[data-art="labor"]').filter({ hasText: "Magnesium" });
  await expect(mg).toContainText(/Magnesium 0,58 mmol\/l am \d{2}\.\d{2}\.\d{4} – unter dem Referenzbereich \(0,66–1,07\)\. Bitte prüfen\./);
  await expect(mg).toContainText("Verlauf: 0,79");
  await expect(mg).toContainText("fallend");
  await expect(page.getByTestId("plan-hinweise")).not.toContainText("Noch kein Laborbefund");

  // Beispiel, Paula: nur alte Befunde – Hinweis über der Liste
  const paula = await testpatient("Beispiel", "Paula");
  await oeffnen(page, paula.id, "/labor");
  await expect(page.getByRole("list", { name: "Laborbefunde" }).getByRole("listitem")).toHaveCount(2);
  await expect(page.getByTestId("alter-labor")).toContainText(/Der letzte Laborbefund ist vom \d{2}\.\d{2}\.\d{4} und damit älter als 12 Monate\./);
  await expect(page.getByTestId("labor-detail").getByTitle("Triglyceride", { exact: true }).locator(".."))
    .toContainText("über Referenz 0 – 150");
});

test("Musterdaten: BIA-Messungen zu mehreren Zeitpunkten", async ({ page }) => {
  const max = await testpatient("Mustermann", "Max");
  await oeffnen(page, max.id, "/bia");
  const messungen = page.getByRole("list", { name: "BIA-Messungen" }).getByRole("listitem");
  await expect(messungen).toHaveCount(3);
  await expect(messungen.first()).toContainText(/BCM \d+,\d kg/);
  const detail = page.getByTestId("bia-detail");
  await expect(detail).toContainText(/BIA-Messung vom \d{2}\.\d{2}\.\d{4}/);
  await expect(detail).toContainText("ECW (extrazelluläres Wasser)");
  await expect(detail).toContainText("51,0 %");
  await expect(detail).toContainText("BCM vermindert, ECW erhöht");
  await expect(page.getByTestId("alter-bia")).toContainText(/Letzte Erfassung \d{2}\.\d{2}\.\d{4}/);
  // die älteste Messung: ECW noch 44,0 %
  await messungen.last().getByRole("button").click();
  await expect(page.getByTestId("bia-detail")).toContainText("44,0 %");

  // Probe, Jonas: eine alte Messung – Hinweis „älter als 12 Monate“
  const jonas = await testpatient("Probe", "Jonas");
  await oeffnen(page, jonas.id, "/bia");
  await expect(page.getByRole("list", { name: "BIA-Messungen" }).getByRole("listitem")).toHaveCount(1);
  await expect(page.getByTestId("alter-bia")).toContainText(/letzte BIA-Messung ist vom \d{2}\.\d{2}\.\d{4} und damit älter als 12 Monate\./);
});

test("Musterdaten: Testpatient ohne Labor und BIA zeigt die Hinweise", async ({ page }) => {
  const hanna = await testpatient("Test", "Hanna");
  await oeffnen(page, hanna.id);
  // im Aktenkopf: ab zwei Hinweisen ein Sammel-Chip, der die Liste aufklappt (F181)
  const kopf = page.getByTestId("aktenkopf");
  const sammel = kopf.getByTestId("hinweise-sammel");
  await expect(sammel).toContainText(/\d+ Hinweise/);
  await sammel.click();
  const liste = page.getByTestId("hinweise-liste");
  await expect(liste.getByTestId("hinweis-labor")).toHaveText("Kein Laborbefund");
  await expect(liste.getByTestId("hinweis-bia")).toHaveText("Keine BIA-Messung");
  // Klick auf den Hinweis führt zum Reiter Labor (Wunsch 11.10.2026)
  await liste.getByTestId("hinweis-labor").click();
  await expect(page).toHaveURL(new RegExp(`/patienten/${hanna.id}/labor`));
  await expect(page.getByRole("list", { name: "Laborbefunde" })).toContainText("Noch kein Laborbefund erfasst.");
  await expect(page.getByTestId("labor-detail")).toHaveCount(0);
  await oeffnen(page, hanna.id, "/bia");
  await expect(page.getByRole("list", { name: "BIA-Messungen" })).toContainText("Noch keine BIA-Messung erfasst.");
  await expect(page.getByTestId("bia-detail")).toHaveCount(0);
  // Diagnosen hat sie trotzdem
  await oeffnen(page, hanna.id, "/diagnosen");
  await expect(page.getByTestId("diagnoseliste").getByTestId("diagnose-zeile")).toHaveCount(2);

  // in der Patientenliste dieselben Hinweise
  await page.goto("/patienten?suche=Hanna");
  const zeile = page.getByTestId("patientenliste").getByRole("row").filter({ has: page.getByRole("link", { name: "Test, Hanna", exact: true }) });
  await expect(zeile).toContainText("Kein Laborbefund");
  await expect(zeile).toContainText("Keine BIA-Messung");
});
