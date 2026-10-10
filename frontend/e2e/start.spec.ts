/** Entwurf 2 · Startseite (S01–S11): Kennzahlen, Kacheln im Raster, Termine abhaken, Startseite anpassen (je Person
 *  gespeichert: Reihenfolge, Größe, Sichtbarkeit), Wiedereinbestellung, Meine Akten. */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, stackNeuStarten, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

function gespeichert(page: Page) {
  return page.waitForResponse((a) => a.url().endsWith("/api/auth/ich/") && a.request().method() === "PATCH" && a.ok());
}

test("Startseite zeigt Kennzahlen und alle Kacheln im Raster", async ({ page }) => {
  await page.goto("/");
  for (const titel of ["Termine und Wiedervorlagen", "Wiedereinbestellung fällig", "Meine Akten", "Auffällige Gewichte", "Infusionspläne",
    "Nach und nach prüfen", "Zuletzt eingetragen"]) {
    await expect(page.getByRole("heading", { name: titel, exact: true })).toBeVisible();
  }
  await expect(page.getByTestId("start-zahlen")).toContainText("offene Termine heute");
  // Kennzahlenleiste (S01, SU8: „Termine überfällig“ statt Datensicherung – die steht als Chip in der Kopfzeile)
  const leiste = page.getByTestId("kennzahlenleiste");
  for (const titel of ["In Betreuung", "Mit offenem Termin", "Termine in 7 Tagen", "Kontakt fällig", "Termine überfällig"]) {
    await expect(leiste.getByText(titel, { exact: true })).toBeVisible();
  }
  await expect(leiste).not.toContainText("Datensicherung");
  const api = await apiAls("mitarbeiter");
  const d = await api.get("startseite/");
  await api.ende();
  await expect(page.getByTestId("kz-in-betreuung")).toContainText(String(d.zahlen.in_betreuung));
  await expect(page.getByTestId("kz-ueberfaellig")).toContainText(String(d.zahlen.termine_ueberfaellig));
  // Raster bei 1440 px: 3 Spalten, Termine 2×2 (Standard)
  await expect(page.getByTestId("raster")).toHaveAttribute("data-spalten", "3");
  await expect(page.locator('[data-kachel="termine"]')).toHaveAttribute("data-groesse", "2x2");
  // Wochenstreifen (S03): 7 Tage ab heute, ein Tag filtert die Liste
  const streifen = page.getByTestId("wochenstreifen");
  await expect(streifen.getByRole("button")).toHaveCount(7);
  await expect(streifen.getByRole("button").first()).toContainText("heute");
  await streifen.getByRole("button").nth(1).click();
  await expect(streifen.getByRole("button").nth(1)).toHaveAttribute("aria-pressed", "true");
  await streifen.getByRole("button").nth(1).click();
  // Musterdaten: Gewichtsverlust bei Max Mustermann (mit Verlauf), ein offener Planentwurf zur Freigabe
  await expect(page.getByTestId("gewichtswarnungen").getByRole("link", { name: "Mustermann, Max" })).toBeVisible();
  await expect(page.getByTestId("gewichtswarnungen").getByRole("img", { name: /Verlauf 6 Monate/ }).first()).toBeVisible();
  await expect(page.getByTestId("plaene-kachel")).toContainText("Zur Freigabe");
  await expect(page.getByTestId("plaene-kachel").getByRole("link", { name: /Entwurf prüfen/ }).first()).toBeVisible();
  // Prüfliste: Kontakt in zwei Stufen (S04)
  await expect(page.getByTestId("pruefen-kontakt_ueberfaellig")).toBeVisible();
  await expect(page.getByTestId("pruefen-kontakt_bald")).toBeVisible();
  // Zuletzt eingetragen: Filter „Von mir“ (S10)
  await page.getByRole("group", { name: "Wer" }).getByRole("button", { name: "Von mir" }).click();
  await expect(page.getByRole("group", { name: "Wer" }).getByRole("button", { name: "Von mir" })).toHaveAttribute("aria-pressed", "true");
});

test("Termin von der Startseite anlegen und als erledigt abhaken", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Termin", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Patient").fill("Musterfrau");
  await dialog.getByRole("option", { name: /Musterfrau, Erika/ }).click();
  await dialog.getByLabel("Art", { exact: true }).selectOption("rueckruf");
  await dialog.getByLabel("Uhrzeit").fill("23:30");
  await dialog.getByLabel("Titel").fill("E2E Rückruf Laborwerte");
  await dialog.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const zeile = page.getByTestId("terminliste").getByText("E2E Rückruf Laborwerte");
  await expect(zeile).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("terminliste").getByText("E2E Rückruf Laborwerte")).toBeVisible();
  await page.getByRole("checkbox", { name: /Erledigt: Musterfrau, Erika, E2E Rückruf Laborwerte/ }).check();
  await expect(page.getByText(/erledigt \d\d:\d\d von S\. Mitarbeit/)).toBeVisible();
  // im Backend gespeichert: nach Neustart von Backend und Webserver nicht mehr offen
  stackNeuStarten();
  await page.reload();
  await expect(page.getByTestId("terminliste").getByText("E2E Rückruf Laborwerte")).toHaveCount(0);
  const api = await apiAls("mitarbeiter");
  const termine = await api.get("termine/?offen=false&seitengroesse=200");
  const t = termine.results.find((x: { titel: string }) => x.titel === "E2E Rückruf Laborwerte");
  expect(t.erledigt_von_name).toBe("S. Mitarbeit");
  await api.ende();
});

test("Startseite anpassen: ausblenden, verschieben und Größe per Tastatur, Maus und Knopf – je Person gespeichert", async ({ page }) => {
  // 1440 px breit (3 Spalten), aber hoch genug, dass alle Kacheln ohne Scrollen sichtbar sind – die Maus zieht
  // nur an sichtbaren Stellen (unter 960 px Höhe lag „Nach und nach prüfen“ in der vierten Rasterzeile außerhalb)
  await page.setViewportSize({ width: 1440, height: 1700 });
  await page.goto("/");
  await page.getByRole("button", { name: "Startseite anpassen" }).click();
  await expect(page.getByTestId("anpassen")).toContainText("3 Spalten");
  // ausblenden
  let antwort = gespeichert(page);
  await page.getByRole("button", { name: "Zuletzt eingetragen ausblenden" }).click();
  await antwort;
  await page.getByRole("button", { name: "Fertig" }).click();
  await expect(page.getByRole("heading", { name: "Zuletzt eingetragen" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Auffällige Gewichte" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Zuletzt eingetragen" })).toHaveCount(0);

  await page.getByRole("button", { name: "Startseite anpassen" }).click();
  // Tastatur am Griff: Pfeil = verschieben, Umschalt + Pfeil = Größe
  const griff = page.getByRole("button", { name: /^Infusionspläne verschieben/ });
  antwort = gespeichert(page);
  await griff.press("ArrowLeft");
  await antwort;
  await expect(griff).toBeFocused();
  antwort = gespeichert(page);
  await griff.press("Shift+ArrowRight");
  await antwort;
  await expect(page.locator('[data-kachel="plaene"]')).toHaveAttribute("data-groesse", "2x1");
  // Größenknopf
  antwort = gespeichert(page);
  await page.getByRole("group", { name: "Größe Auffällige Gewichte" }).getByRole("button", { name: "1×2" }).click();
  await antwort;
  await expect(page.locator('[data-kachel="gewicht"]')).toHaveAttribute("data-groesse", "1x2");
  // Maus: Ecke unten rechts ziehen – rastet in ganzen Rasterzellen ein
  const pruefen = page.locator('[data-kachel="pruefen"]');
  await pruefen.scrollIntoViewIfNeeded();
  const kasten = (await pruefen.boundingBox())!;
  const ecke = (await page.getByTestId("ecke-pruefen").boundingBox())!;
  antwort = gespeichert(page);
  await page.mouse.move(ecke.x + ecke.width / 2, ecke.y + ecke.height / 2);
  await page.mouse.down();
  await page.mouse.move(ecke.x + kasten.width * 0.8, ecke.y + 10, { steps: 8 });
  await expect(page.getByText(/2 × 1 · loslassen zum Einrasten/)).toBeVisible();
  await page.mouse.up();
  await antwort;
  await expect(pruefen).toHaveAttribute("data-groesse", "2x1");
  // Maus: Kachel am Griff auf eine andere ziehen
  const meine = page.getByRole("button", { name: /^Meine Akten verschieben/ });
  const ziel = (await page.locator('[data-kachel="termine"]').boundingBox())!;
  const g = (await meine.boundingBox())!;
  antwort = gespeichert(page);
  await page.mouse.move(g.x + g.width / 2, g.y + g.height / 2);
  await page.mouse.down();
  await page.mouse.move(ziel.x + 60, ziel.y + ziel.height / 2, { steps: 10 });
  await page.mouse.up();
  await antwort;
  // wieder einblenden
  antwort = gespeichert(page);
  await page.getByRole("button", { name: "Zuletzt eingetragen einblenden" }).click();
  await antwort;
  await page.getByRole("button", { name: "Fertig" }).click();

  const api = await apiAls("mitarbeiter");
  const ich = await api.get("auth/ich/");
  const karten = Object.fromEntries(ich.startseite.karten.map((k: { id: string; sichtbar: boolean; breite: number; hoehe: number }) =>
    [k.id, `${k.sichtbar}:${k.breite}x${k.hoehe}`]));
  expect([karten.plaene, karten.gewicht, karten.pruefen, karten.aktiv]).toEqual(["true:2x1", "true:1x2", "true:2x1", "true:2x1"]);
  const reihe = ich.startseite.karten.map((k: { id: string }) => k.id);
  expect(reihe.indexOf("plaene")).toBeLessThan(reihe.indexOf("gewicht"));
  expect(reihe.indexOf("meine")).toBeLessThan(reihe.indexOf("termine"));
  // Standard wiederherstellen
  await page.getByRole("button", { name: "Startseite anpassen" }).click();
  antwort = gespeichert(page);
  await page.getByRole("button", { name: "Standard" }).click();
  await antwort;
  await expect(page.locator('[data-kachel="pruefen"]')).toHaveAttribute("data-groesse", "1x1");
  const zurueck = await api.get("auth/ich/");
  expect(zurueck.startseite.karten.slice(0, 3).map((k: { id: string }) => k.id)).toEqual(["termine", "wieder", "meine"]);
  await api.ende();
});

test("Wiedereinbestellung (S04): Stufen und Kontakt direkt aus der Kachel", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  const d = await api.get("startseite/");
  await api.ende();
  await page.goto("/");
  const kachel = page.getByTestId("wiedereinbestellung");
  const w = d.wiedereinbestellung;
  if (w.anzahl_ueberfaellig) await expect(kachel.getByTestId("wieder-ueberfaellig")).toHaveText(String(w.anzahl_ueberfaellig));
  if (w.anzahl_bald) await expect(kachel.getByTestId("wieder-bald")).toHaveText(String(w.anzahl_bald));
  const erster = w.ueberfaellig[0] ?? w.bald[0];
  test.skip(!erster, "Musterdaten ohne fällige Wiedereinbestellung");
  await kachel.getByRole("button", { name: `Kontakt erfassen: ${erster.name}` }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Kontakt erfassen" })).toBeVisible();
  await expect(dialog).toContainText(erster.name);
  await expect(dialog.getByTestId("kontextkasten")).toBeVisible();
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
});

test("Heute zu tun: ganz oben, Rückruf abhaken, fehlende Angaben führen zur gefilterten Liste (F184, F186)", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  // echte Akte ohne Telefon, Hausarzt, Gewicht und Diagnose; ein heute fälliger Rückruf
  const nachname = `Morgenrunde${Date.now().toString(36).slice(-5)}`;
  const p = await api.post("patienten/", { nachname, vorname: "Toni", geburtsdatum: "1966-06-06" });
  // lange überfällig, damit er oben in der Gruppe steht (sie zeigt die ältesten zuerst)
  const vorher = new Date(Date.now() - 400 * 86_400_000).toLocaleDateString("sv-SE", { timeZone: "Europe/Berlin" });
  await api.post("termine/", { patient: p.id, art: "rueckruf", faellig_am: vorher, titel: "E2E Rückruf Morgenrunde" });
  await api.ende();

  await page.goto("/");
  const liste = page.getByTestId("heute-zu-tun");
  await expect(liste.getByRole("heading", { name: /Heute zu tun/ })).toBeVisible();
  // ganz oben: vor der Kennzahlenleiste und den Kacheln
  await expect(page.getByTestId("kennzahlenleiste")).toBeVisible();
  expect((await liste.boundingBox())!.y).toBeLessThan((await page.getByTestId("kennzahlenleiste").boundingBox())!.y);
  // Rückruf abhaken: verschwindet aus der Liste
  const rueckrufe = liste.getByTestId("tl-rueckrufe");
  await expect(rueckrufe).toContainText("E2E Rückruf Morgenrunde");
  await rueckrufe.getByRole("checkbox", { name: new RegExp(`Erledigt: ${nachname}`) }).click();  // Zeile verschwindet sofort
  await expect(page.getByText(`Erledigt: ${nachname}, Toni`)).toBeVisible();
  await expect(liste).not.toContainText("E2E Rückruf Morgenrunde");
  // fehlende Angaben: „n Akten ohne Telefonnummer“ → Patientenliste mit Filter
  await liste.getByTestId("tl-luecke-telefon").getByRole("link").click();
  await expect(page).toHaveURL(/pruefen=ohne_telefon/);
  await expect(page.getByTestId("pruefen")).toHaveValue("ohne_telefon");
  await expect(page.getByRole("link", { name: new RegExp(nachname) }).first()).toBeVisible();
});

test("Heute zu tun: Betrachter sieht die Liste ohne Knöpfe zum Vorbereiten", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/");
  const liste = page.getByTestId("heute-zu-tun");
  await expect(liste).toBeVisible();
  await expect(liste.getByTestId("tl-bestaetigung")).toHaveCount(0);
  await expect(liste.getByTestId("tl-ohne-ort")).toHaveCount(0);
  await ctx.close();
});
