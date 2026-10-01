/** Entwurf 2 · Start: Termine anlegen und abhaken, Karten ein- und ausblenden (gespeichert je Person). */
import { expect, test } from "@playwright/test";
import { apiAls, stackNeuStarten, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

test("Startseite zeigt Termine, Gewichte, Pläne, Prüfliste und Zuletzt eingetragen", async ({ page }) => {
  await page.goto("/");
  for (const titel of ["Termine und Wiedervorlagen", "Auffällige Gewichte", "Infusionspläne", "Nach und nach prüfen",
    "Zuletzt eingetragen"]) {
    await expect(page.getByRole("heading", { name: titel })).toBeVisible();
  }
  await expect(page.getByTestId("start-zahlen")).toContainText("offene Termine heute");
  // Musterdaten: Gewichtsverlust bei Max Mustermann, ein offener Planentwurf
  await expect(page.getByRole("link", { name: "Mustermann, Max" }).first()).toBeVisible();
  await expect(page.getByText("Entwurf", { exact: true }).first()).toBeVisible();
});

test("Termin von der Startseite anlegen und als erledigt abhaken", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Termin", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Patient").fill("Musterfrau");
  await dialog.getByRole("option", { name: /Musterfrau, Erika/ }).click();
  await dialog.getByLabel("Art").selectOption("rueckruf");
  await dialog.getByLabel("Uhrzeit").fill("23:30");
  await dialog.getByLabel("Titel").fill("E2E Rückruf Laborwerte");
  await dialog.getByRole("button", { name: "Termin speichern" }).click();
  await expect(dialog).toHaveCount(0);
  const zeile = page.getByTestId("terminliste").getByText("E2E Rückruf Laborwerte");
  await expect(zeile).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("terminliste").getByText("E2E Rückruf Laborwerte")).toBeVisible();
  await page.getByRole("checkbox", { name: /Erledigt: Musterfrau, Erika, E2E Rückruf Laborwerte/ }).check();
  await expect(page.getByText(/erledigt \d\d:\d\d von S\. Mitarbeit/)).toBeVisible();
  // im Backend gespeichert: nach Neustart von Backend und Webserver nicht mehr offen
  stackNeuStarten();
  await page.reload();
  await expect(page.getByTestId("terminliste").getByText("E2E Rückruf Laborwerte")).toHaveCount(0);
  const api = await apiAls("mitarbeiter");
  const termine = await api.get("termine/?offen=false&seitengroesse=200");
  const t = termine.results.find((x: { titel: string }) => x.titel === "E2E Rückruf Laborwerte");
  expect(t.erledigt_von_name).toBe("S. Mitarbeit");
  await api.ende();
});

test("Startseite anpassen: Karte ausblenden bleibt gespeichert", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Startseite anpassen" }).click();
  await page.getByRole("checkbox", { name: "Zuletzt eingetragen" }).uncheck();
  await page.getByRole("button", { name: "Fertig" }).click();
  await expect(page.getByRole("heading", { name: "Zuletzt eingetragen" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Auffällige Gewichte" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Zuletzt eingetragen" })).toHaveCount(0);
  // Reihenfolge per Tastatur am Griff
  await page.getByRole("button", { name: "Startseite anpassen" }).click();
  await page.getByRole("button", { name: "Infusionspläne verschieben (Pfeiltasten)" }).press("ArrowLeft");
  await page.getByRole("checkbox", { name: "Zuletzt eingetragen" }).check();
  await page.getByRole("button", { name: "Fertig" }).click();
  const api = await apiAls("mitarbeiter");
  await expect.poll(async () => {
    const ich = await api.get("auth/ich/");
    return ich.startseite.karten.map((k: { id: string; sichtbar: boolean }) => `${k.id}:${k.sichtbar}`);
  }).toEqual(["termine:true", "plaene:true", "gewicht:true", "pruefen:true", "aktiv:true"]);
  await api.patch("auth/ich/", { startseite: { karten: [] } });
  await api.ende();
});
