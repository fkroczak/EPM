/**
 * Korrespondenz der Akte (Kundenwunsch 14.10.2026): Reiter „Korrespondenz“ nach „Berichte“. Mitarbeiter legen einen
 * Entwurf an (Vorlage, Betreff, Empfänger, Freitext, Vorschau als PDF), Mediziner geben frei (endgültige PDF in den
 * Dokumenten), danach „Als versendet markieren“ mit Weg und Datum, Verlauf und „Als neuen Entwurf kopieren“.
 * Neu-Dialoge beginnen leer. Am Telefon ragt nichts seitlich heraus.
 *
 * Eigene Akte je Test: Die Musterdaten bleiben für die anderen Tests unverändert.
 */
import { devices, expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

async function neueAkte(schreiben: Record<string, unknown>[] = []) {
  const api = await apiAls("mitarbeiter");
  const p = await api.post("patienten/", { nachname: eindeutig("Brief"), vorname: "Bea", geburtsdatum: "1971-07-07" }) as
    { id: number; nachname: string };
  for (const s of schreiben) await api.post("korrespondenz/", { patient: p.id, vorlage: "patientenaufnahme", ...s });
  await api.ende();
  return p;
}

async function oeffnen(page: Page, id: number) {
  await page.goto(`/patienten/${id}/korrespondenz`);
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
  await expect(page.getByTestId("korrespondenz")).toBeVisible();
}

async function keinSeitlichesHerausragen(page: Page) {
  const { breite, inhalt } = await page.evaluate(() => ({ breite: window.innerWidth, inhalt: document.documentElement.scrollWidth }));
  expect(inhalt, `Seite ${inhalt}px breit bei ${breite}px`).toBeLessThanOrEqual(breite + 1);
}

test("Entwurf anlegen, freigeben, versenden, kopieren", async ({ page, browser }) => {
  const p = await neueAkte();
  await page.goto(`/patienten/${p.id}`);
  // Reiter gleich nach „Berichte“
  const reiter = page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link");
  await expect(reiter.filter({ hasText: /^Korrespondenz/ })).toBeVisible();
  const namen = await reiter.allTextContents();
  const berichte = namen.findIndex((n) => n.startsWith("Berichte"));
  expect(namen[berichte + 1]).toMatch(/^Korrespondenz/);
  await reiter.nth(berichte + 1).click();
  await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}/korrespondenz$`));
  const seite = page.getByTestId("korrespondenz");
  await expect(seite).toContainText("Noch kein Schreiben in dieser Akte.");

  // Neues Schreiben mit Vorschau
  await seite.getByRole("button", { name: "Neues Schreiben" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Neues Schreiben" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Entwurf speichern" })).toBeDisabled();
  await dialog.getByLabel("Vorlage").selectOption("patientenaufnahme");
  await expect(dialog.getByLabel("Betreff")).toHaveValue("Patientenaufnahme");
  await dialog.getByLabel("Betreff").fill("Anforderung Laborwerte");
  await dialog.getByLabel("Empfänger").fill("Hausarzt Dr. Hausmann");
  await dialog.getByLabel("Freitext").fill("Bitte senden Sie uns die letzten Laborwerte.");
  await dialog.getByRole("button", { name: "Vorschau" }).click();
  await expect(page.getByTestId("pdf-dialog")).toBeVisible();
  await expect(page.getByRole("button", { name: "Herunterladen" })).toBeEnabled({ timeout: 20_000 });
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("pdf-dialog")).toHaveCount(0);
  await page.getByRole("dialog").getByRole("button", { name: "Entwurf speichern" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  const detail = page.getByTestId("schreiben-detail");
  await expect(detail).toContainText("Anforderung Laborwerte");
  await expect(detail.getByTestId("schreiben-status")).toHaveText("Entwurf");
  await expect(detail).toContainText("Hausarzt Dr. Hausmann");
  await expect(detail).toContainText("Bitte senden Sie uns die letzten Laborwerte.");
  // Mitarbeiter dürfen nicht freigeben
  await expect(detail.getByRole("button", { name: "Freigeben" })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Korrespondenz/ })).toContainText("1");

  // ein neuer Dialog beginnt leer – nichts vom letzten Schreiben
  await seite.getByRole("button", { name: "Neues Schreiben" }).click();
  await expect(page.getByRole("dialog").getByLabel("Betreff")).toHaveValue("");
  await expect(page.getByRole("dialog").getByLabel("Freitext")).toHaveValue("");
  await expect(page.getByRole("dialog").getByLabel("Vorlage")).toHaveValue("");
  await page.getByRole("dialog").getByRole("button", { name: "Abbrechen" }).click();

  // Mediziner gibt frei
  const ctx = await browser.newContext({ storageState: zustand("mediziner"), ignoreHTTPSErrors: true });
  const med = await ctx.newPage();
  await oeffnen(med, p.id);
  const medDetail = med.getByTestId("schreiben-detail");
  await medDetail.getByRole("button", { name: "Freigeben" }).click();
  await expect(med.getByRole("dialog")).toContainText("endgültige PDF");
  await med.getByTestId("freigabe-bestaetigen").click();
  await expect(med.getByRole("dialog")).toHaveCount(0);
  await expect(medDetail.getByTestId("schreiben-status")).toHaveText("freigegeben");
  await expect(medDetail).toContainText("Freigegeben von");
  await expect(medDetail).toContainText("SHA-256");
  await expect(medDetail.getByRole("button", { name: "Bearbeiten" })).toHaveCount(0);
  await ctx.close();

  // Mitarbeiter: PDF öffnen, als versendet markieren
  await page.reload();
  await expect(detail.getByTestId("schreiben-status")).toHaveText("freigegeben");
  await expect(detail.getByRole("button", { name: "Löschen" })).toHaveCount(0);
  await detail.getByRole("button", { name: "PDF öffnen" }).click();
  await expect(page.getByRole("button", { name: "Herunterladen" })).toBeEnabled({ timeout: 20_000 });
  await page.keyboard.press("Escape");
  await detail.getByRole("button", { name: "Als versendet markieren" }).click();
  const versand = page.getByRole("dialog");
  await expect(versand.getByRole("button", { name: "Speichern" })).toBeDisabled();
  await versand.getByLabel("Weg").selectOption("fax");
  await versand.getByLabel("Notiz").fill("an 0251 123456");
  await versand.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(detail.getByTestId("schreiben-status")).toHaveText("versendet");
  await expect(detail.getByTestId("versand-angabe")).toContainText("Fax · an 0251 123456");
  await expect(detail.getByRole("button", { name: "Als versendet markieren" })).toHaveCount(0);

  // Verlauf
  await detail.getByRole("button", { name: "Verlauf" }).click();
  const verlauf = page.getByTestId("schreiben-verlauf");
  await expect(verlauf.getByRole("listitem").filter({ hasText: "als versendet vermerkt" })).toHaveCount(1);
  await expect(verlauf).toContainText("freigegeben");
  await expect(verlauf).toContainText("angelegt");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // Filter nach Status und Korrektur als neuer Entwurf
  const filter = page.getByTestId("status-filter");
  await filter.getByRole("button", { name: /^Entwurf/ }).click();
  await expect(seite).toContainText("Kein Schreiben mit diesem Status.");
  await filter.getByRole("button", { name: /^versendet/ }).click();
  await expect(seite.getByRole("listitem")).toHaveCount(1);
  await detail.getByRole("button", { name: "Als neuen Entwurf kopieren" }).click();
  await expect(detail.getByTestId("schreiben-status")).toHaveText("Entwurf");
  await expect(detail).toContainText("Kopie von Nr.");
  await expect(filter.getByRole("button", { name: "Alle" })).toHaveAttribute("aria-pressed", "true");
  await expect(seite.getByRole("list", { name: "Schreiben" }).getByRole("listitem")).toHaveCount(2);

  // Entwurf löschen (mit Rückfrage)
  await detail.getByRole("button", { name: "Löschen" }).click();
  await page.getByTestId("bestaetigen").click();
  await expect(seite.getByRole("list", { name: "Schreiben" }).getByRole("listitem")).toHaveCount(1);
});

test("aus „Schreiben und E-Mail“ in der Akte ablegen", async ({ page }) => {
  const p = await neueAkte();
  await page.goto(`/patienten/${p.id}`);
  await page.getByTestId("aktenaktionen").getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: "Schreiben und E-Mail …" }).click();
  const dialog = page.getByTestId("schreiben-dialog");
  await dialog.getByLabel("Schreiben", { exact: true }).selectOption("patientenaufnahme");
  await dialog.getByTestId("als-entwurf-ablegen").click();
  await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}/korrespondenz\\?schreiben=\\d+`));
  await expect(page.getByTestId("schreiben-detail").getByTestId("schreiben-status")).toHaveText("Entwurf");
});

test.describe("am Telefon", () => {
  const { defaultBrowserType: _browser, ...telefon } = devices["Pixel 7"];
  test.use({ ...telefon, viewport: { width: 375, height: 760 } });

  test("Liste, Detail und Dialog passen in die Breite", async ({ page }) => {
    const p = await neueAkte([{ titel: "Anforderung der Laborbefunde und der Arztbriefe aus dem Krankenhausaufenthalt",
      empfaenger: "Universitätsklinikum Münster, Klinik für Allgemein-, Viszeral- und Transplantationschirurgie",
      text: "Sehr geehrte Damen und Herren,\nbitte senden Sie uns die Befunde.".repeat(3) }]);
    // freigegeben: die meisten Aktionen (versendet, PDF, kopieren, Verlauf) – sie umbrechen in der Karte
    const med = await apiAls("mediziner");
    const [s] = await med.get(`korrespondenz/?patient=${p.id}`) as { id: number }[];
    await med.post(`korrespondenz/${s.id}/freigeben/`, {});
    await med.ende();
    await oeffnen(page, p.id);
    await expect(page.getByTestId("schreiben-detail")).toContainText("Universitätsklinikum Münster");
    await expect(page.getByTestId("schreiben-detail").getByRole("button", { name: "Als neuen Entwurf kopieren" })).toBeVisible();
    await keinSeitlichesHerausragen(page);
    const karte = await page.getByTestId("schreiben-detail").boundingBox();
    for (const knopf of await page.getByTestId("detail-aktionen").getByRole("button").all()) {
      const k = await knopf.boundingBox();
      expect(k!.x + k!.width, "Aktion ragt aus der Karte").toBeLessThanOrEqual(karte!.x + karte!.width + 1);
    }
    await page.getByTestId("korrespondenz").getByRole("button", { name: "Neues Schreiben" }).click();
    await expect(page.getByTestId("schreiben-formular")).toBeVisible();
    await keinSeitlichesHerausragen(page);
  });
});

test.describe("auf dem Tablet", () => {
  test.use({ viewport: { width: 820, height: 1180 } });

  test("Reiter erreichbar, nichts ragt heraus", async ({ page }) => {
    const p = await neueAkte([{ titel: "Bescheinigung", empfaenger: "Krankenkasse" }]);
    await oeffnen(page, p.id);
    await expect(page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Korrespondenz/ })).toBeVisible();
    await expect(page.getByTestId("schreiben-detail")).toContainText("Krankenkasse");
    await keinSeitlichesHerausragen(page);
  });
});
