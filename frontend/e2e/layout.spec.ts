/** Bildschirmgrößen: unter 1440 px Seitenleiste mit Symbolen und die Akte einspaltig (S16, Stufen je Seite). */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

test("15-Zoll-Laptop: Seitenleiste als Symbolleiste, Navigation bleibt bedienbar", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  const leiste = page.locator("aside").first();
  const breite = (await leiste.boundingBox())?.width ?? 0;
  expect(breite).toBeLessThan(100);
  await page.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Patienten" }).click();
  await expect(page.getByRole("heading", { name: "Patienten", level: 1 })).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 900 });
  expect((await leiste.boundingBox())?.width ?? 0).toBeGreaterThan(200);
});

test("Akte ohne Seiten-Scrollen (F181): 1366 × 768 und 1920 × 1080 – sechs Karten in zwei Reihen, Kopf und Reiter bleiben stehen", async ({ page }) => {
  for (const [breite, hoehe, spalten] of [[1366, 768, "3"], [1920, 1080, "4"]] as const) {
    await page.setViewportSize({ width: breite, height: hoehe });
    await page.goto("/patienten");
    await page.getByTestId("patientenliste").getByRole("link", { name: "Probe, Jonas" }).click();
    const uebersicht = page.getByTestId("akte-uebersicht");
    await expect(uebersicht).toHaveAttribute("data-fuellt", "1");
    await expect(page.getByTestId("uebersicht-stufe")).toHaveAttribute("data-spalten", spalten);
    await expect(page.getByTestId("uebersicht-stufe").locator("[data-bereich]")).toHaveCount(6);
    // Die Seite scrollt nicht; jede Karte endet im Fenster (ihr Inhalt darf in der Karte scrollen)
    await expect.poll(() => page.evaluate(() => document.scrollingElement!.scrollHeight - innerHeight)).toBeLessThanOrEqual(0);
    const unten = await page.getByTestId("uebersicht-stufe").locator("[data-bereich]").evaluateAll((els) => els.map((e) => e.getBoundingClientRect().bottom));
    for (const u of unten) expect(u).toBeLessThanOrEqual(hoehe + 1);
    // Gewicht oben links, Kontakte und Termine darunter
    const gewicht = (await page.getByTestId("gewichtskarte").boundingBox())!;
    const termine = (await page.getByTestId("aktentermine").boundingBox())!;
    expect(termine.y).toBeGreaterThan(gewicht.y + gewicht.height - 1);
    // in einem Reiter mit zwei Spalten bleiben Kopf und Reiter stehen, gescrollt wird in der Spalte
    await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Kontakte/ }).click();
    await expect(page.getByTestId("kontakte")).toBeVisible();
    expect(await page.evaluate(() => document.scrollingElement!.scrollHeight - innerHeight)).toBeLessThanOrEqual(0);
    await expect(page.getByTestId("aktenkopf")).toBeInViewport();
  }
  // Akte mit vielen Hinweisen (kein Plan, kein Versorger, kein Kontakt, kein Labor, keine BIA …): im Kopf nur ein Chip
  // „N Hinweise“, der die Liste aufklappt – der Kopf bleibt ruhig und die Akte passt weiter ins Fenster
  const api = await apiAls("mitarbeiter");
  const viele = await api.post("patienten/", { nachname: eindeutig("Vielhinweis"), vorname: "Vera", geburtsdatum: "1960-05-05" });
  await api.ende();
  for (const [breite, hoehe] of [[1366, 768], [1920, 1080]] as const) {
    await page.setViewportSize({ width: breite, height: hoehe });
    await page.goto(`/patienten/${viele.id}`);
    const sammel = page.getByTestId("aktenkopf").getByTestId("hinweise-sammel");
    await expect(sammel).toContainText(/\d+ Hinweise/);
    await expect(page.getByTestId("akte-uebersicht")).toHaveAttribute("data-fuellt", "1");
    await expect.poll(() => page.evaluate(() => document.scrollingElement!.scrollHeight - innerHeight)).toBeLessThanOrEqual(0);
  }
  // Tablet quer (Entscheidung der Praxis 10.10.2026, F190): zwei breite Spalten, die Seite darf scrollen,
  // nichts ragt waagerecht heraus
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto(`/patienten/${viele.id}`);
  await expect(page.getByTestId("aktenkopf").getByTestId("hinweise-sammel")).toContainText(/\d+ Hinweise/);
  await expect(page.getByTestId("uebersicht-stufe")).toHaveAttribute("data-spalten", "2");
  await expect(page.getByTestId("akte-uebersicht")).not.toHaveAttribute("data-fuellt", "1");
  expect(await page.evaluate(() => document.scrollingElement!.scrollWidth - document.scrollingElement!.clientWidth)).toBeLessThanOrEqual(0);
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.getByTestId("aktenkopf").getByTestId("hinweise-sammel").click();
  const liste = page.getByTestId("hinweise-liste");
  await expect(liste).toContainText("Kein Laborbefund");
  // „×“ in der Liste öffnet den Dialog zum Ausblenden (die Liste schließt dabei)
  await liste.getByRole("button", { name: /Hinweis „Kein Laborbefund“ ausblenden/ }).click();
  await expect(page.getByRole("dialog").getByRole("heading", { name: "Hinweis ausblenden" })).toBeVisible();
  await page.keyboard.press("Escape");

  // Tablet hochkant: die Seite scrollt wie bisher, die Karten stehen untereinander bzw. zu zweit
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.reload();
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Übersicht" }).click();
  await expect(page.getByTestId("akte-uebersicht")).not.toHaveAttribute("data-fuellt", "1");
});
