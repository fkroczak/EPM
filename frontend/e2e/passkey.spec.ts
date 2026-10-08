/** Passkeys (WebAuthn) als zweiter Faktor (Festlegung 08.10.2026, F130–F132): in Mein Konto anlegen, damit anmelden,
 *  eine Bestätigung damit abschließen. Der Passkey kommt von einem virtuellen Authenticator des Browsers (Chrome
 *  DevTools-Protokoll) – mit Fingerabdruck/PIN „bestätigt“, wie ein Telefon oder Windows Hello. */
import { expect, test } from "@playwright/test";
import { merken, neuesKonto, virtuellerAuthenticator } from "./hilfen";

test("Passkey in Mein Konto anlegen, damit anmelden, Bestätigung mit Passkey", async ({ browser }) => {
  const konto = await neuesKonto("mitarbeiter", "Paula", "Passkey");
  const ctx = await browser.newContext({ storageState: konto.zustand, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const { cdp, authenticatorId } = await virtuellerAuthenticator(ctx, page);

  // anlegen: Mein Konto › Anmeldung und Sicherheit › Passkey hinzufügen
  await page.goto("/konto");
  const sicherheit = page.getByTestId("sicherheit");
  await expect(sicherheit.getByTestId("passkeys")).toContainText("keiner");
  await sicherheit.getByRole("button", { name: "Passkey hinzufügen" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name des Passkeys").fill("Büro-PC");
  await dialog.getByRole("button", { name: "Passkey anlegen" }).click();
  await expect(page.getByText("Passkey „Büro-PC“ eingerichtet.")).toBeVisible();
  await expect(sicherheit.getByTestId("passkey-eintrag")).toContainText("Büro-PC");
  await expect(sicherheit.getByTestId("passkey-eintrag")).toContainText("noch nicht verwendet");
  const { credentials } = await cdp.send("WebAuthn.getCredentials", { authenticatorId });
  expect(credentials).toHaveLength(1);

  // abmelden und mit Passkey statt Code wieder anmelden
  // unten links nur die Person; Abmelden steht im Menü dahinter (Wunsch 08.10.2026)
  await page.getByTestId("benutzermenue").click();
  await page.getByRole("menuitem", { name: "Abmelden" }).click();
  await page.getByLabel("Benutzername").fill(konto.benutzername);
  await page.getByLabel("Passwort").fill(konto.kennwort);
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect(page.getByRole("heading", { name: "Mit Passkey anmelden" })).toBeVisible();
  // Umschalter: Der Code aus der App geht weiterhin
  await expect(page.getByRole("group", { name: "Zweiter Faktor" }).getByRole("button", { name: "Code" })).toBeVisible();
  await page.getByTestId("passkey-anmelden").click();
  await expect(page.getByTestId("angemeldet-als")).toHaveText("P. Passkey");
  const status = await (await page.request.get("/api/auth/status/")).json();
  expect(status.schritt).toBe("fertig");
  expect(status.benutzer.passkey).toBe(true);

  // Bestätigung mit Passwort und Passkey: Passkey umbenennen geht ohne, Zwei-Faktor-Anmeldung ausschalten mit
  await page.goto("/konto");
  await expect(sicherheit.getByTestId("passkey-eintrag")).toContainText("zuletzt");
  await sicherheit.getByRole("button", { name: "Ausschalten" }).click();
  const aus = page.getByRole("dialog");
  await expect(aus.getByRole("group", { name: "Zweiter Faktor" })).toBeVisible();
  await aus.getByLabel("Dein Passwort").fill("falsch-falsch-falsch");
  await aus.getByTestId("passkey-bestaetigen").click();
  await expect(aus.getByTestId("passkey-bestaetigt")).toBeVisible();
  await aus.getByRole("button", { name: "Ausschalten" }).click();
  await expect(aus.getByText("Das Passwort stimmt nicht.")).toBeVisible();
  // beim falschen Passwort wurde der Passkey nicht verbraucht – mit dem richtigen geht es
  await aus.getByLabel("Dein Passwort").fill(konto.kennwort);
  await aus.getByRole("button", { name: "Ausschalten" }).click();
  await expect(page.getByText("Zwei-Faktor-Anmeldung ausgeschaltet.")).toBeVisible();
  await expect(sicherheit.getByTestId("passkeys")).toContainText("keiner");
  await ctx.close();
});

test("Passkey für den Nachweis nach dem Neustart: anlegen, Schlüssel des virtuellen Geräts merken", async ({ browser }) => {
  const konto = await neuesKonto("mitarbeiter", "Petra", "Neustart");
  const ctx = await browser.newContext({ storageState: konto.zustand, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const { cdp, authenticatorId } = await virtuellerAuthenticator(ctx, page);
  await page.goto("/konto");
  await page.getByTestId("sicherheit").getByRole("button", { name: "Passkey hinzufügen" }).click();
  await page.getByRole("dialog").getByLabel("Name des Passkeys").fill("Telefon");
  await page.getByRole("dialog").getByRole("button", { name: "Passkey anlegen" }).click();
  await expect(page.getByText("Passkey „Telefon“ eingerichtet.")).toBeVisible();
  const { credentials } = await cdp.send("WebAuthn.getCredentials", { authenticatorId });
  // zz-neustart.spec.ts setzt den Schlüssel in ein neues virtuelles Gerät ein und meldet sich damit an
  merken("passkey", { benutzername: konto.benutzername, kennwort: konto.kennwort, credential: credentials[0] });
  await ctx.close();
});
