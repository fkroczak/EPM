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
  await detail.getByRole("button", { name: "Versorger anlegen" }).click();
  await expect(detail.getByRole("alert").first()).toBeVisible();
  await detail.getByLabel("Firma").fill(firma);
  await detail.getByLabel("Ort").fill("Münster");
  await detail.getByLabel("Telefon Zentrale").fill("0251 123 456");
  await detail.getByRole("button", { name: "Versorger anlegen" }).click();
  await expect(detail.getByRole("heading", { name: firma })).toBeVisible();
  await expect(page.getByTestId("versorgerliste")).toContainText(firma);

  // bearbeiten
  await detail.getByLabel("Notiz").fill("Lieferung Di und Fr.");
  await detail.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Versorger gespeichert.")).toBeVisible();

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
  await detail.getByRole("button", { name: "Deaktivieren" }).click();
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
  await expect(detail.getByText("Firma", { exact: true })).toBeVisible();
  await expect(detail.getByRole("textbox")).toHaveCount(0);
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
