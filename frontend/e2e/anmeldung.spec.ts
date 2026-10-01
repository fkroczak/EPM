/** Entwurf 1 · Anmeldung mit 2FA, erste Anmeldung mit eigenem Passwort und Authenticator, Abmeldung. */
import { expect, test } from "@playwright/test";
import { KENNWORT, SCHLUESSEL_HEX, anmeldenUI, apiAls, eindeutig, totpBase32, totpHex } from "./hilfen";

test("Anmeldung mit Passwort und Code aus der Authenticator-App, Abmelden", async ({ page }) => {
  await anmeldenUI(page, "e2e.betrachter", totpHex(SCHLUESSEL_HEX));
  await expect(page.getByTestId("angemeldet-als")).toHaveText("B. Betrachtung");
  await expect(page.getByRole("navigation", { name: "Hauptnavigation" })).toBeVisible();
  // Betrachter sieht keine Administration
  await expect(page.getByRole("navigation", { name: "Administration" })).toHaveCount(0);
  await page.getByRole("button", { name: "Abmelden" }).click();
  await expect(page.getByRole("heading", { name: "Anmelden" })).toBeVisible();
  // nach dem Abmelden ist die API gesperrt
  const status = await page.request.get("/api/auth/status/");
  expect((await status.json()).schritt).toBe("anmelden");
});

test("Falsches Passwort wird abgewiesen", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Benutzername").fill("e2e.mediziner");
  await page.getByLabel("Passwort").fill("falsch-falsch-falsch");
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect(page.getByRole("alert")).toContainText("Benutzername oder Kennwort falsch");
  await expect(page.getByLabel("Passwort")).toHaveValue("");
});

test("Erste Anmeldung: eigenes Passwort, Authenticator einrichten, Notfall-Codes", async ({ page }) => {
  const admin = await apiAls("admin");
  const name = eindeutig("e2e.neu");
  const neu = await admin.post("benutzer/", { username: name, first_name: "Nora", last_name: "Neuling", rolle: "mitarbeiter" });
  await admin.ende();
  await page.goto("/");
  await page.getByLabel("Benutzername").fill(name);
  await page.getByLabel("Passwort").fill(neu.einmal_kennwort);
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect(page.getByRole("heading", { name: "Eigenes Passwort festlegen" })).toBeVisible();
  await page.getByLabel("Neues Passwort").fill("kurz");
  await page.getByLabel("Passwort wiederholen").fill("kurz");
  await page.getByRole("button", { name: "Passwort speichern" }).click();
  await expect(page.getByRole("alert")).toContainText("mindestens 12 Zeichen");
  await page.getByLabel("Neues Passwort").fill(KENNWORT + "-neu");
  await page.getByLabel("Passwort wiederholen").fill(KENNWORT + "-neu");
  await page.getByRole("button", { name: "Passwort speichern" }).click();
  await expect(page.getByRole("heading", { name: "Authenticator-App einrichten" })).toBeVisible();
  await expect(page.getByRole("img", { name: "QR-Code für die Authenticator-App" })).toBeVisible();
  const geheim = (await page.getByTestId("otp-schluessel").textContent()) ?? "";
  expect(geheim.length).toBeGreaterThan(15);
  await page.getByLabel("Code aus der App").fill("000000");
  await page.getByRole("button", { name: "Bestätigen" }).click();
  await expect(page.getByRole("alert")).toContainText("Code ungültig");
  // nach einem Fehlversuch sperrt django-otp das Gerät kurz (Schutz gegen Durchprobieren)
  await page.waitForTimeout(2100);
  await page.getByLabel("Code aus der App").fill(totpBase32(geheim));
  await page.getByRole("button", { name: "Bestätigen" }).click();
  await expect(page.getByRole("heading", { name: "Notfall-Codes" })).toBeVisible();
  await expect(page.getByTestId("notfallcodes").locator("li")).toHaveCount(10);
  await page.getByRole("button", { name: "Codes notiert – weiter" }).click();
  await expect(page.getByTestId("angemeldet-als")).toHaveText("N. Neuling");
  // Sitzung bleibt nach dem Neuladen bestehen
  await page.reload();
  await expect(page.getByTestId("angemeldet-als")).toHaveText("N. Neuling");
});
