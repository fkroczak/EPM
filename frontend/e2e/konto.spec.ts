/** Entwurf 14 · Mein Konto: Darstellung (gespeichert je Person), Passwort, Notfall-Codes, neues Gerät, Sitzungen. */
import { expect, test } from "@playwright/test";
import { apiAnmelden, merken, neuesKonto, totpBase32 } from "./hilfen";

test("Darstellung wählen, eigene Farben prüfen, nach Neuladen erhalten, zurücksetzen", async ({ browser }) => {
  const konto = await neuesKonto("mitarbeiter", "Dora", "Darstellung");
  const ctx = await browser.newContext({ storageState: konto.zustand, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/konto");
  const html = page.locator("html");
  await expect(page.getByTestId("profil")).toContainText(konto.benutzername);

  await page.getByRole("radio", { name: "Darstellung Dunkel" }).click();
  await expect(html).toHaveAttribute("data-schema", "dunkel");
  await page.getByRole("button", { name: "Kompakt", exact: true }).click();
  await expect(html).toHaveAttribute("data-dichte", "kompakt");
  await page.getByRole("button", { name: "Groß", exact: true }).click();
  await expect(html).toHaveAttribute("data-schrift", "gross");
  await page.waitForTimeout(500);
  await page.reload();
  await expect(html).toHaveAttribute("data-schema", "dunkel");
  await expect(html).toHaveAttribute("data-dichte", "kompakt");

  // Individuell: Akzent aus der Liste, eigene Farbe ohne lesbare Schrift wird nicht gespeichert
  await page.getByRole("radio", { name: "Darstellung Individuell" }).click();
  await page.getByRole("button", { name: "Akzentfarbe Petrol" }).click();
  await expect(html).toHaveAttribute("data-schema", "individuell");
  await expect.poll(() => html.evaluate((e) => e.style.getPropertyValue("--akzent"))).toBe("#0A6A86");
  await page.getByLabel("Eigene Akzentfarbe").fill("#7f7f7f");
  await expect(page.getByText("Auf dieser Farbe ist weder weiße noch dunkle Schrift gut lesbar.")).toBeVisible();
  await page.getByRole("button", { name: "Hintergrund Sand" }).click();
  await page.getByRole("button", { name: "Akzentfarbe Tannengrün" }).click();
  await page.waitForTimeout(500);
  await page.reload();
  await expect(html).toHaveAttribute("data-schema", "individuell");
  await expect.poll(() => html.evaluate((e) => e.style.getPropertyValue("--akzent"))).toBe("#1F6B4F");
  await expect.poll(() => html.evaluate((e) => e.style.getPropertyValue("--grund"))).toBe("#F3F1EC");

  await page.getByRole("button", { name: "Auf Standard zurücksetzen" }).click();
  await expect(html).toHaveAttribute("data-schema", "standard");
  await page.waitForTimeout(500);
  await page.reload();
  await expect(html).toHaveAttribute("data-schema", "standard");
  await expect(html).toHaveAttribute("data-dichte", "normal");
  await ctx.close();
  merken("darstellung", { zustand: konto.zustand });
});

test("Passwort ändern, Notfall-Codes neu, neues Gerät, andere Sitzung beenden", async ({ browser }) => {
  const konto = await neuesKonto("betrachter", "Siegfried", "Sicher");
  const ctx = await browser.newContext({ storageState: konto.zustand, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/konto");
  const sicherheit = page.getByTestId("sicherheit");
  await expect(sicherheit).toContainText("10 von 10 übrig");

  // Passwort: altes falsch → Meldung; richtig → geändert
  await sicherheit.getByRole("button", { name: "Ändern" }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Bisheriges Passwort").fill("falsch-falsch-falsch");
  await dialog.getByLabel("Neues Passwort", { exact: true }).fill(`${konto.kennwort}-2`);
  await dialog.getByLabel("Neues Passwort wiederholen").fill(`${konto.kennwort}-2`);
  await dialog.getByRole("button", { name: "Passwort ändern" }).click();
  await expect(dialog.getByRole("alert")).toContainText("Bisheriges Kennwort ist falsch.");
  await dialog.getByLabel("Bisheriges Passwort").fill(konto.kennwort);
  await dialog.getByRole("button", { name: "Passwort ändern" }).click();
  await expect(page.getByText("Passwort geändert. Andere Anmeldungen wurden beendet.")).toBeVisible();
  await expect(sicherheit).toContainText("zuletzt geändert");

  // zweite Anmeldung (anderes Gerät) mit dem neuen Passwort und einem Notfall-Code
  const zweite = await apiAnmelden(konto.benutzername, `${konto.kennwort}-2`, konto.notfallcodes[0]);
  expect(zweite.schritt).toBe("fertig");
  await page.reload();
  const sitzungen = page.getByTestId("sitzungen");
  await expect(sitzungen).toContainText("Dieser PC");
  await expect(sitzungen).toContainText("Anderes Gerät");
  await sitzungen.getByRole("button", { name: "Abmelden" }).click();
  await expect(sitzungen).not.toContainText("Anderes Gerät");
  expect((await (await zweite.ctx.get("/api/auth/status/")).json()).schritt).toBe("anmelden");
  await zweite.ctx.dispose();

  // Notfall-Codes neu erzeugen
  await expect(sicherheit).toContainText("9 von 10 übrig");
  await sicherheit.getByRole("button", { name: "Neu erzeugen" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Neu erzeugen" }).click();
  await expect(dialog.getByTestId("notfallcodes").locator("li")).toHaveCount(10);
  await dialog.getByRole("button", { name: "Fertig" }).click();
  await expect(sicherheit).toContainText("10 von 10 übrig");

  // neues Gerät: neuer Schlüssel, danach neue Notfall-Codes
  await sicherheit.getByRole("button", { name: "Neues Gerät" }).click();
  dialog = page.getByRole("dialog");
  const geheim = (await dialog.getByTestId("otp-schluessel").textContent()) ?? "";
  expect(geheim).not.toBe(konto.geheim);
  await dialog.getByLabel("Code aus der App").fill(totpBase32(geheim));
  await dialog.getByRole("button", { name: "Bestätigen" }).click();
  await expect(dialog.getByTestId("notfallcodes").locator("li")).toHaveCount(10);
  await dialog.getByRole("button", { name: "Fertig" }).click();
  await expect(page.getByText("Neues Gerät eingerichtet.")).toBeVisible();
  await expect(sicherheit).toContainText("aktiv");
  await ctx.close();
  merken("konto", { benutzername: konto.benutzername, kennwort: `${konto.kennwort}-2`, geheim });
});
