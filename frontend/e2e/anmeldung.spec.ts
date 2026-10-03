/** Entwurf 1 · Anmeldung mit 2FA, erste Anmeldung mit eigenem Passwort und Authenticator, Abmeldung. */
import { expect, test } from "@playwright/test";
import { KENNWORT, SCHLUESSEL_HEX, anmeldenUI, apiAls, apiAnmelden, eindeutig, naechsterNotfallcode, sitzungAblaufenLassen, totpBase32, totpHex } from "./hilfen";

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

test("Erste Anmeldung: eigenes Passwort; Zwei-Faktor-Anmeldung freiwillig einrichten und wieder ausschalten", async ({ page }) => {
  const admin = await apiAls("admin");
  const name = eindeutig("e2e.neu");
  const neu = await admin.post("benutzer/", { username: name, first_name: "Nora", last_name: "Neuling", rolle: "mitarbeiter" });
  // Festlegung 02.10.2026: Die Zwei-Faktor-Anmeldung ist freiwillig (Standard)
  expect((await admin.get("benutzer/anmeldung/")).zweiter_faktor).toBe("freiwillig");
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
  // ohne zweiten Faktor direkt angemeldet; die Startseite weist einmal auf die freiwillige Einrichtung hin
  await expect(page.getByTestId("angemeldet-als")).toHaveText("N. Neuling");
  const hinweis = page.getByTestId("zweifaktor-hinweis");
  await expect(hinweis).toContainText("freiwillig");
  await hinweis.getByRole("link", { name: "Jetzt einrichten" }).click();
  await expect(page).toHaveURL(/\/konto#zwei-faktor$/);
  const sicherheit = page.getByTestId("sicherheit");
  await expect(sicherheit).toContainText("nicht eingerichtet");
  await expect(sicherheit).not.toContainText("Notfall-Codes");
  await sicherheit.getByRole("button", { name: "Einrichten" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("img", { name: "QR-Code für die Authenticator-App" })).toBeVisible();
  const geheim = (await dialog.getByTestId("otp-schluessel").textContent()) ?? "";
  expect(geheim.length).toBeGreaterThan(15);
  await dialog.getByLabel("Code aus der App").fill("000000");
  await dialog.getByRole("button", { name: "Bestätigen" }).click();
  await expect(dialog.getByRole("alert")).toContainText("Code ungültig");
  // nach einem Fehlversuch sperrt django-otp das Gerät kurz (Schutz gegen Durchprobieren)
  await page.waitForTimeout(2100);
  await dialog.getByLabel("Code aus der App").fill(totpBase32(geheim));
  await dialog.getByRole("button", { name: "Bestätigen" }).click();
  await expect(dialog.getByTestId("notfallcodes").locator("li")).toHaveCount(10);
  await dialog.getByRole("button", { name: "Fertig" }).click();
  await expect(sicherheit).toContainText("aktiv");
  await expect(sicherheit).toContainText("Notfall-Codes");
  // Sitzung bleibt nach dem Neuladen bestehen; der Hinweis auf der Startseite ist weg
  await page.goto("/");
  await expect(page.getByTestId("angemeldet-als")).toHaveText("N. Neuling");
  await expect(page.getByTestId("zweifaktor-hinweis")).toHaveCount(0);
  // wer den zweiten Faktor eingerichtet hat, wird beim Anmelden danach gefragt
  const mit = await apiAnmelden(name, KENNWORT + "-neu", totpBase32(geheim, Date.now() + 30_000));
  expect(mit.schritt).toBe("fertig");
  await mit.ctx.dispose();
  // freiwillig heißt auch: wieder ausschalten – mit Passwort und Code
  await page.goto("/konto");
  await sicherheit.getByRole("button", { name: "Ausschalten" }).click();
  await dialog.getByLabel("Dein Passwort").fill(KENNWORT + "-neu");
  await dialog.getByLabel("Code aus der Authenticator-App").fill("000000");
  await dialog.getByRole("button", { name: "Ausschalten" }).click();
  await expect(dialog).toContainText("Der Code ist ungültig");
  await page.waitForTimeout(2100);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(totpBase32(geheim, Date.now() + 60_000));
  await dialog.getByRole("button", { name: "Ausschalten" }).click();
  await expect(page.getByText("Zwei-Faktor-Anmeldung ausgeschaltet.")).toBeVisible();
  await expect(sicherheit).toContainText("nicht eingerichtet");
});

test("Abgelaufene Sitzung führt zurück zur Anmeldung", async ({ browser }) => {
  // eigene Sitzung, damit die gemeinsame Sitzung des Betrachters für andere Tests gültig bleibt
  const anmeldung = await apiAnmelden("e2e.betrachter", KENNWORT, naechsterNotfallcode("e2e.betrachter"));
  expect(anmeldung.schritt).toBe("fertig");
  const ctx = await browser.newContext({ storageState: await anmeldung.ctx.storageState(), ignoreHTTPSErrors: true });
  await anmeldung.ctx.dispose();
  const page = await ctx.newPage();
  await page.goto("/");
  await expect(page.getByTestId("angemeldet-als")).toBeVisible();
  await page.waitForLoadState("networkidle");
  // 30 Minuten ohne Anfrage: die Sitzung ist in der Datenbank abgelaufen, der nächste Aufruf führt zur Anmeldung
  sitzungAblaufenLassen((await ctx.cookies()).find((c) => c.name === "epm_sitzung")?.value ?? "");
  const abgewiesen = page.waitForResponse((a) => a.url().includes("/api/patienten/"));
  await page.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Patienten" }).click();
  expect((await abgewiesen).status()).toBe(403);
  await expect(page.getByRole("heading", { name: "Anmelden" })).toBeVisible();
  await ctx.close();
});
