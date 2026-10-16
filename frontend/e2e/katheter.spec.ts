/**
 * Katheter-Historie (F192, 15.10.2026): eigener Reiter „Katheter“ nach „Medikamente“, Katheter anlegen (Kerndaten werden
 * übernommen – Festlegung 16.10.2026), Zeitachse mit Balken sichtbar, Komplikation als Markierung, Wechsel mit Hinweis
 * „Vorheriger Katheter noch nicht als entfernt eingetragen“, Kennzahl Infektionen je 1000 Kathetertage. Ohne Historie,
 * aber mit Katheter in den Kerndaten: „Anlagedatum nicht erfasst – bitte nachtragen“. Am Telefon senkrechte Zeitachse.
 *
 * Eigene Akte je Test: Die Musterdaten bleiben für die anderen Tests unverändert.
 */
import { devices, expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

function vorTagen(tage: number) {
  const d = new Date();
  d.setDate(d.getDate() - tage);
  return d.toISOString().slice(0, 10);
}

function deutsch(iso: string) {
  const [j, m, t] = iso.split("-");
  return `${t}.${m}.${j}`;
}

type Wert = { id: number; wert: string };

async function neueAkte(mitKerndaten = false) {
  const api = await apiAls("mitarbeiter");
  const typen = await api.get("auswahlwerte/?liste=katheter") as Wert[];
  const port = typen.find((t) => t.wert === "Port")!;
  const p = await api.post("patienten/", {
    nachname: eindeutig("Kath"), vorname: "Karla", geburtsdatum: "1971-07-07", ...(mitKerndaten ? { katheter: port.id } : {}),
  }) as { id: number };
  await api.ende();
  return p;
}

async function oeffnen(page: Page, id: number) {
  await page.goto(`/patienten/${id}/katheter`);
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
  await expect(page.getByTestId("katheter")).toBeVisible();
}

test("Katheter anlegen, Zeitachse sichtbar, Komplikation und Wechsel", async ({ page }) => {
  const p = await neueAkte();
  await page.goto(`/patienten/${p.id}`);
  // Reiter gleich nach „Medikamente“
  const reiter = page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link");
  await expect(reiter.filter({ hasText: /^Katheter/ })).toBeVisible();
  const namen = await reiter.allTextContents();
  const medikamente = namen.findIndex((n) => n.startsWith("Medikamente"));
  expect(namen[medikamente + 1]).toMatch(/^Katheter/);
  await reiter.nth(medikamente + 1).click();
  await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}/katheter$`));

  const seite = page.getByTestId("katheter");
  await expect(seite).toContainText("Noch kein Katheter eingetragen.");

  // anlegen
  await seite.getByRole("button", { name: "Katheter", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Neuer Katheter" })).toBeVisible();
  await dialog.getByLabel("Katheter-Typ").selectOption({ label: "Port" });
  await dialog.getByLabel("Lage/Zugang").fill("V. subclavia rechts");
  await dialog.getByLabel("Anlagedatum").fill(deutsch(vorTagen(200)));
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toHaveCount(0);

  // Zeitachse mit einem Balken, Kennzahl „aktueller Katheter“ mit Liegedauer
  const achse = page.getByTestId("katheter-zeitachse");
  await expect(achse).toBeVisible();
  await expect(achse.getByTestId("katheter-balken").filter({ visible: true })).toHaveCount(1);
  await expect(page.getByTestId("katheter-aktuell")).toContainText("Port · 200 Tage");
  await expect(page.getByTestId("katheter-liste").getByTestId("katheter-zeile").first()).toContainText("V. subclavia rechts");
  // Kerndaten übernommen (Aktenkopf) und Zähler am Reiter
  await expect(page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Katheter/ })).toContainText("1");
  const api = await apiAls("mitarbeiter");
  expect((await api.get(`patienten/${p.id}/`)).kopf.katheter).toBe("Port");

  // Komplikation: Markierung auf der Zeitachse, Kennzahl
  await page.getByRole("button", { name: "Komplikation am Port erfassen" }).filter({ visible: true }).click();
  await expect(dialog.getByRole("heading", { name: "Neue Komplikation" })).toBeVisible();
  await dialog.getByLabel("Datum").fill(deutsch(vorTagen(100)));
  await dialog.getByLabel("Art").selectOption({ label: "Katheterinfektion" });
  await dialog.getByLabel("Notiz").fill("Fieber, Blutkultur positiv");
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(achse.getByTestId("katheter-marke").filter({ visible: true })).toHaveCount(1);
  await expect(page.getByTestId("katheter-rate")).toContainText("5,00");   // 1 / 200 × 1000
  // Komplikation außerhalb der Liegezeit: verständliche Meldung
  await page.getByRole("button", { name: "Komplikation am Port erfassen" }).filter({ visible: true }).click();
  await dialog.getByLabel("Datum").fill(deutsch(vorTagen(300)));
  await dialog.getByLabel("Art").selectOption({ label: "Okklusion" });
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toContainText("vor der Anlage des Katheters");
  await dialog.getByRole("button", { name: "Abbrechen" }).click();

  // Wechsel: neuer Katheter, der alte bleibt offen → Hinweis
  await seite.getByRole("button", { name: "Katheter", exact: true }).click();
  await dialog.getByLabel("Katheter-Typ").selectOption({ label: "Hickman" });
  await dialog.getByLabel("Anlagedatum").fill(deutsch(vorTagen(10)));
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("katheter-hinweise")).toContainText("Vorheriger Katheter noch nicht als entfernt eingetragen");
  await expect(achse.getByTestId("katheter-balken").filter({ visible: true })).toHaveCount(2);
  expect((await api.get(`patienten/${p.id}/`)).kopf.katheter).toBe("Hickman");

  // den alten als entfernt eintragen → Hinweis verschwindet
  await page.getByRole("button", { name: "Port entfernen" }).filter({ visible: true }).click();
  await expect(dialog.getByRole("heading", { name: "Katheter entfernen" })).toBeVisible();
  await dialog.getByLabel("Entfernt am").fill(deutsch(vorTagen(10)));
  await dialog.getByLabel("Entfernungsgrund").selectOption({ label: "Wechsel" });
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("katheter-hinweise")).toHaveCount(0);
  await expect(page.getByTestId("katheter-aktuell")).toContainText("Hickman · 10 Tage");

  // im Verlauf der Akte mit Bearbeiter
  const verlauf = await api.get(`patienten/${p.id}/verlauf/?bereich=katheter`) as { aktion: string; person: string }[];
  expect(verlauf.map((e) => e.aktion)).toContain("als entfernt eingetragen");
  expect(verlauf.every((e) => !!e.person)).toBe(true);
  await api.ende();

  // nach dem Neuladen noch da (Daten in der Datenbank)
  await page.reload();
  await expect(page.getByTestId("katheter-zeitachse").getByTestId("katheter-balken").filter({ visible: true })).toHaveCount(2);
});

test("Katheter in den Kerndaten ohne Historie: Anlagedatum nachtragen", async ({ page }) => {
  const p = await neueAkte(true);
  await oeffnen(page, p.id);
  const hinweise = page.getByTestId("katheter-hinweise");
  await expect(hinweise).toContainText("Anlagedatum nicht erfasst – bitte nachtragen");
  await expect(page.getByTestId("katheter")).toContainText("Die Zeitachse erscheint, sobald das Anlagedatum nachgetragen ist.");
  await hinweise.getByRole("button", { name: "Anlagedatum nachtragen" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Katheter-Typ").selectOption({ label: "Port" });
  await dialog.getByLabel("Anlagedatum").fill(deutsch(vorTagen(30)));
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("katheter-hinweise")).toHaveCount(0);
  await expect(page.getByTestId("katheter-zeitachse")).toBeVisible();
});

test.describe("am Telefon", () => {
  const { defaultBrowserType: _browser, ...telefon } = devices["Pixel 7"];
  test.use({ ...telefon, viewport: { width: 375, height: 760 } });

  test("senkrechte Zeitachse, nichts ragt seitlich heraus", async ({ page }) => {
    const p = await neueAkte();
    const api = await apiAls("mitarbeiter");
    const typen = await api.get("auswahlwerte/?liste=katheter") as Wert[];
    await api.post("katheter/", { patient: p.id, typ: typen.find((t) => t.wert === "Port")!.id, lage: "V. subclavia rechts",
      anlage_am: vorTagen(400), entfernt_am: vorTagen(100) });
    await api.post("katheter/", { patient: p.id, typ: typen.find((t) => t.wert === "PICC")!.id, anlage_am: vorTagen(100) });
    await api.ende();
    await oeffnen(page, p.id);
    const achse = page.getByTestId("katheter-zeitachse");
    await expect(achse.getByTestId("katheter-balken").filter({ visible: true })).toHaveCount(2);
    await expect(page.getByTestId("katheter-liste").getByTestId("katheter-karte")).toHaveCount(2);
    const breite = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(breite).toBeLessThanOrEqual(1);
  });
});
