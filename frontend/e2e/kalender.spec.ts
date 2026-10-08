/** Globaler Kalender (Wunsch 02.10.2026): Termine aller Patienten, Überfälliges, Fälligkeiten; Termin anlegen und abhaken. */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, merken, zustand } from "./hilfen";

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
  await dialog.getByLabel("Art", { exact: true }).selectOption("wiedervorlage");
  await dialog.getByLabel("Uhrzeit").fill("09:15");
  await dialog.getByLabel("Titel").fill("E2E Kalender Kontrolle");
  await dialog.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const eintrag = page.getByTestId(`tag-${ziel}`).getByRole("button", { name: /09:15 Wiedervorlage: Beispiel, Paula – E2E Kalender Kontrolle/ });
  await expect(eintrag).toBeVisible();
  // Klick auf einen offenen Termin öffnet gleich „Termin ändern“ mit „Erledigt“ und „Akte öffnen“ (08.10.2026)
  await eintrag.click();
  const td = page.getByRole("dialog");
  await expect(td.getByRole("heading", { name: "Termin bearbeiten" })).toBeVisible();
  await expect(td.getByLabel("Titel")).toHaveValue("E2E Kalender Kontrolle");
  await expect(td.getByRole("link", { name: "Akte öffnen" })).toBeVisible();
  await expect(td.getByTestId("termin-angelegt")).toContainText("Angelegt");
  await td.getByRole("button", { name: "Erledigt" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByTestId(`tag-${ziel}`).getByRole("button", { name: /E2E Kalender Kontrolle \(erledigt\)/ })).toBeVisible();
  // Erledigtes öffnet die Ansicht (nicht mehr änderbar)
  await page.getByTestId(`tag-${ziel}`).getByRole("button", { name: /E2E Kalender Kontrolle \(erledigt\)/ }).click();
  await expect(page.getByRole("dialog").getByTestId("eintrag-details")).toContainText("Erledigt");
  await page.keyboard.press("Escape");
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

test("Kalender: Termin mit „×“ ausblenden (3 Monate, Grund), in der Akte wieder einschalten", async ({ page }) => {
  // eigener Patient mit einem überfälligen Rückruf (Musterdaten bleiben unberührt)
  const api = await apiAls("mitarbeiter");
  const nachname = eindeutig("Kalenderx");
  const p = await api.post("patienten/", { nachname, vorname: "Ina", geburtsdatum: "1971-05-06" });
  await api.post("termine/", { patient: p.id, art: "rueckruf", faellig_am: tagIn(-5), titel: "Rückruf E2E ausblenden" });
  await api.ende();
  await page.goto("/kalender");
  const eintrag = page.getByTestId("ueberfaellig-termine").getByTestId("kalender-eintrag").filter({ hasText: `${nachname}, Ina` });
  await expect(eintrag).toBeVisible();
  await eintrag.locator("xpath=..").getByTestId("eintrag-ausblenden").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Termin ausblenden" })).toBeVisible();
  await expect(dialog).toContainText("Rückruf E2E ausblenden");
  await dialog.getByRole("button", { name: "3 Monate" }).click();
  await dialog.getByLabel("Grund").fill("Patientin meldet sich selbst");
  await dialog.getByRole("button", { name: "Ausblenden" }).click();
  await expect(page.getByText("Termin für 3 Monate ausgeblendet.")).toBeVisible();
  await expect(page.getByTestId("ueberfaellig-termine")).not.toContainText(`${nachname}, Ina`);
  // in der Akte unter „Ausgeblendete Hinweise“ mit Grund – und zurück
  await page.goto(`/patienten/${p.id}`);
  const versteckt = page.getByTestId("stumme-hinweise").getByTestId("ausgeblendeter-termin");
  await expect(versteckt).toContainText("Rückruf E2E ausblenden");
  await expect(versteckt).toContainText("Patientin meldet sich selbst");
  await versteckt.getByRole("button", { name: "Wieder einschalten" }).click();
  await expect(page.getByText("Termin wieder eingeschaltet.")).toBeVisible();
  await page.goto("/kalender");
  await expect(page.getByTestId("ueberfaellig-termine")).toContainText(`${nachname}, Ina`);
});
