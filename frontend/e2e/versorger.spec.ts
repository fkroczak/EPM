/** Entwurf 13 · Versorger: anlegen, bearbeiten, Ansprechpartner, deaktivieren mit Neuzuordnung. */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, stackNeuStarten, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

test("Versorger anlegen, Ansprechpartner pflegen, deaktivieren mit Neuzuordnung", async ({ page }) => {
  const firma = eindeutig("E2E Homecare ");
  await page.goto("/versorger");
  await expect(page.getByTestId("versorgerliste")).toContainText("Testversorger Nord (fiktiv)");

  // Neuer Versorger: Pflichtfeld wird vom Backend geprüft
  await page.getByRole("button", { name: "Neuer Versorger" }).click();
  const detail = page.getByTestId("versorger-detail");
  await expect(detail.getByRole("heading", { name: "Neuer Versorger" })).toBeVisible();
  await detail.getByRole("button", { name: "Speichern" }).click();
  await expect(detail.getByRole("alert").first()).toBeVisible();
  await detail.getByLabel("Firma").fill(firma);
  await detail.getByLabel("Ort").fill("Münster");
  await detail.getByLabel("Telefon Zentrale").fill("0251 123 456");
  await detail.getByRole("button", { name: "Speichern" }).click();
  await expect(detail.getByRole("heading", { name: firma })).toBeVisible();
  await expect(page.getByTestId("versorgerliste")).toContainText(firma);
  // danach zum Lesen: Anschrift und Erreichbarkeit als Text, kein Formular (Entwurf 08.10.2026)
  await expect(detail.getByRole("textbox")).toHaveCount(0);
  await expect(detail).toContainText("0251 123 456");

  // bearbeiten: „Bearbeiten“ öffnet das Formular an derselben Stelle
  await detail.getByRole("button", { name: "Bearbeiten" }).click();
  await detail.getByLabel("Notiz").fill("Lieferung Di und Fr.");
  await detail.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Versorger gespeichert.")).toBeVisible();
  await expect(detail).toContainText("Lieferung Di und Fr.");

  // zwei Ansprechpartner
  for (const [name, zust] of [["Anna Alpha", "Patienten A–K"], ["Bernd Beta", "Patienten L–Z"]]) {
    await detail.getByRole("button", { name: "Ansprechpartner", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Name").fill(name);
    await dialog.getByLabel("Zuständigkeit").fill(zust);
    await dialog.getByLabel("Telefon").fill("0251 123 457");
    await dialog.getByRole("button", { name: "Speichern" }).click();
    await expect(dialog).toHaveCount(0);
    await expect(detail.getByTestId("ansprechpartner")).toContainText(name);
  }

  // ein Patient bei Anna Alpha (über die API angelegt)
  const api = await apiAls("mitarbeiter");
  const versorger = (await api.get("versorger/")).find((v: { name: string }) => v.name === firma);
  const alpha = versorger.ansprechpartner.find((a: { name: string }) => a.name === "Anna Alpha");
  const beta = versorger.ansprechpartner.find((a: { name: string }) => a.name === "Bernd Beta");
  const patient = await api.post("patienten/", { nachname: eindeutig("Zuordnung"), vorname: "Zoe", geburtsdatum: "1980-01-01",
    versorger: versorger.id, ansprechpartner: alpha.id });
  await page.reload();
  await expect(detail.getByTestId("ansprechpartner").getByRole("link", { name: "1 Patienten" })).toBeVisible();

  // Anna Alpha deaktivieren: Patienten werden Bernd Beta zugeordnet
  await detail.getByRole("button", { name: "Anna Alpha" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Deaktivieren" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByTestId("neu-zuordnen-liste")).toContainText(`${patient.nachname}, Zoe`);
  await dialog.getByLabel("Neu zuordnen an").selectOption({ label: "Bernd Beta (Patienten L–Z)" });
  await dialog.getByRole("button", { name: "1 Patienten neu zuordnen und deaktivieren" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(detail.getByTestId("ansprechpartner")).toContainText("Patienten A–K · inaktiv");

  // nach Neustart von Backend und Webserver: alles aus der Datenbank
  stackNeuStarten();
  const p = await api.get(`patienten/${patient.id}/`);
  expect(p.ansprechpartner).toBe(beta.id);
  const nachher = (await api.get("versorger/")).find((v: { name: string }) => v.name === firma);
  expect(nachher.notiz).toBe("Lieferung Di und Fr.");
  expect(nachher.ansprechpartner.find((a: { name: string }) => a.name === "Anna Alpha").aktiv).toBe(false);

  // Versorger deaktivieren: erscheint unter „Inaktiv“, nicht mehr bei neuen Patienten
  await page.goto(`/versorger?id=${versorger.id}`);
  // Deaktivieren steckt im Menü „⋯“ und fragt nach (Eine Sprache, 08.10.2026)
  await detail.getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: "Deaktivieren …" }).click();
  await expect(page.getByRole("dialog")).toContainText(firma);
  await page.getByRole("dialog").getByTestId("bestaetigen").click();
  await expect(page.getByText("Versorger deaktiviert.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Inaktiv" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("versorgerliste")).toContainText(firma);
  await page.goto("/patienten/neu");
  await expect(page.getByLabel("Versorger", { exact: true }).locator("option", { hasText: firma })).toHaveCount(0);
  await api.ende();
});

test("Betrachter sieht Versorger nur lesend", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/versorger");
  // nur lesen: Werte als Text, keine (ausgegrauten) Eingabefelder
  const detail = page.getByTestId("versorger-detail");
  await expect(detail.getByRole("heading", { level: 2 })).toBeVisible();
  await expect(detail.getByText("Anschrift", { exact: true })).toBeVisible();
  await expect(detail.getByRole("textbox")).toHaveCount(0);
  await expect(detail.getByRole("button", { name: "Bearbeiten" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Neuer Versorger" })).toHaveCount(0);
  await expect(page.getByTestId("versorger-detail").getByRole("button", { name: "Speichern" })).toHaveCount(0);
  await ctx.close();
});

test("Versorger suchen: Firma, Ort und Ansprechpartner (Wunsch 08.10.2026)", async ({ page }) => {
  await page.goto("/versorger");
  const liste = page.getByTestId("versorgerliste");
  await expect(liste).toContainText("Testversorger Nord (fiktiv)");
  await page.getByLabel("Versorger filtern").fill("Nord");
  await expect(liste).toContainText("Testversorger Nord (fiktiv)");
  await page.getByLabel("Versorger filtern").fill("gibtesnichtxyz");
  await expect(page.getByText("Kein Versorger passt zur Suche.")).toBeVisible();
  await page.getByLabel("Versorger filtern").fill("");
  await expect(liste).toContainText("Testversorger Nord (fiktiv)");
});

test("Versorger am Telefon: erst die Liste, dann der Eintrag, „Liste“ führt zurück (Entwurf 08.10.2026)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/versorger");
  const liste = page.getByTestId("versorgerliste");
  await expect(liste).toBeVisible();
  await expect(page.getByTestId("versorger-detail")).toHaveCount(0);
  await liste.getByRole("button", { name: /Testversorger Nord \(fiktiv\)/ }).click();
  const detail = page.getByTestId("versorger-detail");
  await expect(detail.getByRole("heading", { name: "Testversorger Nord (fiktiv)" })).toBeVisible();
  await expect(liste).toBeHidden();
  await detail.getByRole("button", { name: "Liste" }).click();
  await expect(liste).toBeVisible();
  const breite = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(breite).toBeLessThanOrEqual(390);
});
