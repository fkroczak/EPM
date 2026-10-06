/**
 * Wünsche aus der Praxis vom 06.10.2026 über die Oberfläche: Diagnosen mit ICD (F117), Versichertendaten (F118),
 * Laborbefund und BIA (F112–F114), Bericht mit Freigabe (F115), Sprechstundenblatt (F116).
 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

async function neuerPatient() {
  const api = await apiAls("mitarbeiter");
  const nachname = eindeutig("Praxis");
  const p = await api.post("patienten/", { nachname, vorname: "Pia", geburtsdatum: "1972-03-08", geschlecht: "w",
    groesse_cm: "168", ist_test: true });
  await api.post("gewichte/", { patient: p.id, gewicht_kg: "62.4", quelle: "telefonisch" });
  await api.ende();
  return { id: p.id as number, name: `${nachname}, Pia` };
}

async function oeffnen(page: Page, id: number, reiter = "") {
  await page.goto(`/patienten/${id}${reiter}`);
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
}

test("Diagnose mit ICD-Code eintragen; die Liste im Hintergrund wächst mit", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id, "/therapie");
  const karte = page.getByTestId("karte-diagnosen");
  await karte.getByRole("button", { name: "Diagnose" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Diagnose").fill("Kurzdarmsyndrom");
  await dialog.getByLabel("ICD-Code").fill("K91.2");
  await dialog.getByLabel("Zusatzkennzeichen").selectOption("G");
  await expect(dialog.getByText("Kurzdarmsyndrom [K91.2G]")).toBeVisible();
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(karte.getByTestId("diagnoseliste")).toContainText("Kurzdarmsyndrom");
  await expect(karte.getByTestId("diagnoseliste")).toContainText("[K91.2G]");

  // der Katalog hat den Eintrag übernommen (Vorlagen › Labor und Diagnosen)
  const api = await apiAls("mitarbeiter");
  const liste = await api.get("diagnoseliste/?aktiv=true");
  await api.ende();
  expect((liste as { icd_code: string; bezeichnung: string }[]).some(
    (d) => d.icd_code === "K91.2" && d.bezeichnung === "Kurzdarmsyndrom")).toBeTruthy();
});

test("Versichertendaten in den Stammdaten", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id);
  await page.getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: "Stammdaten bearbeiten" }).click();
  await page.getByLabel("Versicherungsart").selectOption("gkv");
  await page.getByLabel("Versicherung", { exact: true }).fill("AOK NordWest");
  await page.getByLabel("Versichertennummer").fill("A123456789");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByTestId("krankenkasse")).toContainText("AOK NordWest");
  await expect(page.getByTestId("krankenkasse")).toContainText("GKV");
  await expect(page.getByTestId("versichertennummer")).toHaveText("A123456789");
});

test("Laborbefund über die Maske erfassen – nur Werte eintragen", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id, "/befunde");
  await page.getByRole("button", { name: "Neuer Laborbefund" }).click();
  await page.getByRole("dialog").getByLabel("Labor").fill("Labor Dr. Wagner");
  const maske = page.getByTestId("labor-maske");
  await maske.getByLabel("Ferritin").fill("18");
  await maske.getByLabel("Natrium").fill("138");
  // Parameter, der nicht im Katalog steht (Tumormarker, genetische Parameter)
  const weitere = page.getByTestId("weitere-parameter");
  await weitere.getByRole("button", { name: "Parameter hinzufügen" }).click();
  await weitere.getByLabel("Parameter 1").fill("CA 19-9");
  await weitere.getByLabel("Wert 1").fill("12,4");
  await weitere.getByLabel("Einheit 1").fill("U/ml");
  await page.getByRole("button", { name: /Werte speichern/ }).click();

  await expect(page.getByText("3 Werte")).toBeVisible();
  await page.getByRole("button", { name: "Werte zeigen" }).click();
  await expect(page.getByText("Ferritin")).toBeVisible();
  await expect(page.getByText("µg/l")).toBeVisible();
  await expect(page.getByText("CA 19-9")).toBeVisible();
});

test("BIA-Messung mit Beurteilung; das Gewicht wandert in den Verlauf", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id, "/befunde");
  await page.getByRole("button", { name: "Neue Messung" }).click();
  await page.getByLabel("Gewicht (kg)").fill("61,2");
  await page.getByLabel("BCM (kg)").fill("24,1");
  await page.getByLabel("Fettmasse (kg)").fill("18,6");
  await page.getByLabel("ECW – extrazelluläres Wasser (%)").fill("46,2");
  await page.getByLabel("Körperwasser (l)").fill("32,8");
  await expect(page.getByText(/aus Gewicht und Größe/)).toBeVisible();
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByTestId("bia-tabelle")).toContainText("24,1 kg");

  await oeffnen(page, p.id);
  await expect(page.getByTestId("kennzahlen")).toContainText("61,2");
});

test("Bericht: Entwurf, Freigabe durch den Mediziner, danach unveränderlich", async ({ page, browser }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id, "/berichte");
  await page.getByRole("button", { name: "Neuer Bericht" }).click();
  await page.getByLabel("Titel").fill("Verlaufsbericht 2026");
  await page.getByLabel("Berichtsart").selectOption({ label: "Verlaufsbericht" });
  await page.getByLabel("Empfänger").fill("Hausarzt Dr. Hausmann");
  await page.getByRole("textbox", { name: "Bericht" }).fill("Stabiler Verlauf unter heimparenteraler Ernährung.");
  await page.getByRole("button", { name: "Entwurf speichern" }).click();
  await expect(page.getByTestId("bericht-status")).toHaveText("Entwurf");

  // Mitarbeiter dürfen nicht freigeben – der Knopf erscheint erst gar nicht
  await expect(page.getByRole("button", { name: "Freigeben" })).toHaveCount(0);

  const medizinerSeite = await (await browser.newContext({ storageState: zustand("mediziner") })).newPage();
  await medizinerSeite.goto(`/patienten/${p.id}/berichte`);
  await medizinerSeite.getByRole("button", { name: "Freigeben" }).click();
  await medizinerSeite.getByRole("button", { name: "Freigeben" }).last().click();
  await expect(medizinerSeite.getByTestId("bericht-status")).toHaveText("freigegeben");
  await expect(medizinerSeite.getByText(/Maschinell erstellt, geprüft und freigegeben von/)).toBeVisible();
  // Bearbeiten ist weg, die PDF liegt in den Dokumenten
  await expect(medizinerSeite.getByRole("button", { name: "Bearbeiten" })).toHaveCount(0);
  await medizinerSeite.goto(`/patienten/${p.id}/dokumente`);
  await expect(medizinerSeite.getByText("Verlaufsbericht 2026")).toBeVisible();
  await medizinerSeite.close();
});

test("Infusionstage je Beutelart im Plan-Editor", async ({ browser }) => {
  const p = await neuerPatient();
  const seite = await (await browser.newContext({ storageState: zustand("mediziner") })).newPage();
  await seite.goto(`/patienten/${p.id}/plaene/neu`);
  const tage = seite.getByTestId("infusionstage");
  await tage.getByLabel("PE (Mischbeutel)").fill("5");
  await tage.getByLabel("Zusatzvolumen").fill("2");
  await tage.getByLabel("Infusionsfrei").fill("4");
  await seite.getByRole("button", { name: "Entwurf speichern" }).click();
  await expect(seite.getByText(/höchstens 2 infusionsfreie Tage/)).toBeVisible();
  await tage.getByLabel("Infusionsfrei").fill("0");
  await seite.getByRole("button", { name: "Entwurf speichern" }).click();
  await expect(seite.getByTestId("infusionstage").getByLabel("PE (Mischbeutel)")).toHaveValue("5");
  await seite.close();
});

test("Unterlagen für die Sprechstunde als PDF", async ({ page }) => {
  const p = await neuerPatient();
  const api = await apiAls("mitarbeiter");
  await api.post("diagnosen/", { patient: p.id, bezeichnung: "Kurzdarmsyndrom", icd_code: "K91.2", kennzeichen: "G" });
  await api.ende();
  await oeffnen(page, p.id);
  await page.getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: "Unterlagen für die Sprechstunde" }).click();
  await expect(page.getByRole("dialog")).toContainText("Unterlagen für die Sprechstunde");
  await expect(page.getByTestId("pdf-dialog")).toBeVisible();
  await expect(page.getByTestId("pdf-text").first()).toContainText("Kurzdarmsyndrom");
});
