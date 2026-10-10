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
  // Musterdaten: Rückruf bei Musterfrau vor 3 Tagen ist überfällig; der Plan von Probe, Jonas ist älter als 12 Monate.
  // Rechts die Reiter Tag | Überfällig | Fällig (Entwurf 08.10.2026), zuerst der heutige Tag
  await expect(page.getByTestId("tagesliste")).toBeVisible();
  await page.getByTestId("kalender-seite").getByRole("tab", { name: /Überfällig/ }).click();
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
  await page.getByTestId("tagesliste").getByRole("button", { name: /^Termin am / }).click();
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
  // „Anzeigen ▾“: Arten und Erledigte in einem Menü mit Legende
  await page.getByTestId("anzeigen").click();
  await page.getByTestId("anzeigen-auswahl").getByLabel("Erledigte zeigen").uncheck();
  await expect(page.getByTestId("anzeigen")).toContainText("ohne Erledigte");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("anzeigen-auswahl")).toHaveCount(0);
  await expect(page.getByTestId(`tag-${ziel}`).getByRole("button", { name: /E2E Kalender Kontrolle/ })).toHaveCount(0);
  merken("kalender", { datum: ziel, titel: "E2E Kalender Kontrolle" });
});

test("Kalender: Betrachter sieht alles, legt aber nichts an", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/kalender");
  await expect(page.getByTestId("kalender-monat")).toBeVisible();
  await expect(page.getByRole("button", { name: "Termin", exact: true })).toHaveCount(0);
  await expect(page.getByTestId("tagesliste").getByRole("button", { name: /^Termin am / })).toHaveCount(0);
  await page.getByRole("tab", { name: /Überfällig/ }).click();
  await expect(page.getByTestId("ueberfaellig-termine")).toContainText("Musterfrau, Erika");
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
  await page.getByRole("tab", { name: /Überfällig/ }).click();
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
  await page.getByRole("tab", { name: /Überfällig/ }).click();
  await expect(page.getByTestId("ueberfaellig-termine")).toContainText(`${nachname}, Ina`);
});

test("Kalender: eine Werkzeugzeile, Monat ohne Scrollen auf 1080p; Telefon mit Wochenband (Entwurf 08.10.2026)", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/kalender");
  await expect(page.getByTestId("kalender-monat")).toBeVisible();
  // Titel, Blättern, Ansicht, Anzeigen und „+ Termin“ in einer Zeile
  const titel = (await page.getByTestId("kalender-titel").boundingBox())!;
  const anzeigen = (await page.getByTestId("anzeigen").boundingBox())!;
  expect(Math.abs(titel.y + titel.height / 2 - (anzeigen.y + anzeigen.height / 2))).toBeLessThan(12);
  // der Monat passt in die Fensterhöhe
  const monat = (await page.getByTestId("kalender-monat").boundingBox())!;
  expect(monat.y + monat.height).toBeLessThanOrEqual(1080);
  // Fällig-Reiter
  await page.getByRole("tab", { name: /^Fällig/ }).click();
  await expect(page.getByTestId("bald-kontakt")).toBeVisible();

  // Telefon: Wochenband, Tag | Überfällig | Woche, keine waagerechte Scrollleiste
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/kalender");
  const band = page.getByTestId("kalender-woche");
  await expect(band.getByRole("button")).toHaveCount(7);
  await expect(band.getByRole("button", { pressed: true })).toHaveCount(1);
  await expect(page.getByTestId("tagesliste")).toBeVisible();
  await page.getByRole("tab", { name: /Überfällig/ }).click();
  await expect(page.getByTestId("ueberfaellig-termine")).toBeVisible();
  await page.getByRole("tab", { name: "Woche" }).click();
  await expect(page.getByTestId("kalender-liste").or(page.getByText("In diesem Zeitraum gibt es keine Einträge."))).toBeVisible();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect(band.getByRole("button", { pressed: true })).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("Kalender: „Praxis informieren“ – Infoblatt mit Vorschau, fehlendem Ort und PDF (F177)", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  const orte: { id: number; wert: string }[] = await api.get("auswahlwerte/?liste=terminort");
  const praxis = orte.find((o) => /holtmeier/i.test(o.wert))!;
  // nächste Woche (Mo–So); Testpatienten stehen nie auf dem Blatt, darum zwei echte Akten
  const wochentag = (new Date(`${tagIn(0)}T12:00:00Z`).getUTCDay() + 6) % 7;
  const montag = tagIn(7 - wochentag);
  const dienstag = tagIn(8 - wochentag);
  const ina = await api.post("patienten/", { nachname: eindeutig("Infoblatt"), vorname: "Ina", geburtsdatum: "1965-05-05" });
  const olga = await api.post("patienten/", { nachname: eindeutig("Ohneort"), vorname: "Olga", geburtsdatum: "1964-04-04" });
  await api.post("termine/", { patient: ina.id, art: "praxistermin", faellig_am: montag, uhrzeit: "10:15", ort: praxis.id, titel: "Sprechstunde" });
  await api.post("termine/", { patient: olga.id, art: "praxistermin", faellig_am: dienstag, uhrzeit: "11:30", ort: null, titel: "Sprechstunde" });
  await api.ende();

  await page.goto("/kalender");
  const knopf = page.getByRole("button", { name: "Praxis informieren" });
  await expect(knopf).toHaveAttribute("title", /Infoblatt mit allen Terminen an die Praxis Holtmeier/);
  await knopf.click();
  const dialog = page.getByRole("dialog", { name: "Infoblatt an die Praxis" });
  await expect(dialog.getByRole("heading", { name: "Infoblatt an die Praxis" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Nächste Woche", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(dialog.getByLabel("Ort der Sprechstunde")).toHaveValue(String(praxis.id));
  const vorschau = dialog.getByTestId("infoblatt-vorschau");
  await expect(vorschau).toContainText(/Diese \d+ Patienten stehen auf dem Infoblatt|Dieser Patient steht auf dem Infoblatt/);
  await expect(dialog.getByTestId("infoblatt-liste")).toContainText(`Ina ${ina.nachname}`);
  await expect(dialog.getByTestId("infoblatt-liste")).not.toContainText(olga.nachname);
  // Termin ohne Ort: Warnung, „Ort eintragen“ schlägt die Praxis vor – danach steht er auf dem Blatt
  await expect(dialog.getByTestId("infoblatt-ohne-ort")).toHaveText("Bei diesen Terminen fehlt der Ort – bitte im Termin eintragen.");
  await vorschau.getByRole("listitem").filter({ hasText: olga.nachname }).getByRole("button", { name: "Ort eintragen" }).click();
  const termin = page.getByRole("dialog", { name: "Termin bearbeiten" });
  await expect(termin.getByLabel("Ort")).toHaveValue(String(praxis.id));
  await termin.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(termin).toHaveCount(0);
  await expect(dialog.getByTestId("infoblatt-liste")).toContainText(`Olga ${olga.nachname}`);
  // andere Zeiträume
  await dialog.getByRole("button", { name: "Eigener Zeitraum" }).click();
  await expect(dialog.getByLabel("von", { exact: true })).toHaveValue(montag);
  await dialog.getByRole("button", { name: "Nächster Monat" }).click();
  await expect(dialog.getByTestId("infoblatt-zeitraum-text")).toContainText(", 01.");   // vom Ersten des nächsten Monats
  await dialog.getByRole("button", { name: "Nächste Woche", exact: true }).click();
  await expect(dialog.getByTestId("infoblatt-liste")).toContainText(`Ina ${ina.nachname}`);
  // PDF herunterladen merkt das Blatt: „Zuletzt erstellt am … von …“
  const [download] = await Promise.all([page.waitForEvent("download"),
    dialog.getByRole("button", { name: "PDF herunterladen" }).click()]);
  expect(download.suggestedFilename()).toMatch(/^Patientenankuendigung-\d{4}-\d{2}-\d{2}\.pdf$/);
  await expect(dialog.getByTestId("infoblatt-letzte")).toContainText("Zuletzt erstellt am");
});
