/**
 * Scans, zweiter Teil (aufgeteilt 15.11.2026, damit die CI-Teile unter 5 Minuten bleiben – jeder Test wartet auf eine
 * echte Erkennung im OCR-Dienst): F183 (Scan erkennt den Patienten: Vorschlag oben, Übernahme nur per Klick) und F189
 * (falsch erkannt anmerken, Bereich markieren mit Maus und Touch, Steuerung des Lernens). Erster Teil: scans.spec.ts.
 */
import { expect, test } from "@playwright/test";
import { apiAls, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

const FOTO = "e2e/dateien/laborbefund-foto.jpg";

test("Patient wird vorgeschlagen und erst per Klick übernommen (F183)", async ({ page }) => {
  test.setTimeout(240_000);
  const api = await apiAls("mitarbeiter");
  // Das Foto nennt „Muster, Erika“, geb. 14.03.1961
  const p = await api.post("patienten/", { nachname: "Muster", vorname: "Erika", geburtsdatum: "1961-03-14", geschlecht: "w", ist_test: true });
  await page.goto("/scans");
  await page.getByTestId("scan-datei").setInputFiles(FOTO);
  const detail = page.getByTestId("scan-detail");
  await expect(detail.getByTestId("scan-status")).toHaveText("erkannt", { timeout: 180_000 });
  const vorschlag = detail.getByTestId("patient-vorschlag");
  await expect(vorschlag).toContainText("Muster");
  await expect(vorschlag).toContainText("14.03.1961");
  // nichts ist zugeordnet, bevor jemand klickt
  expect((await api.get(`dokumente/?patient=${p.id}`)).results).toHaveLength(0);
  const einer = vorschlag.getByTestId("patient-vorschlag-uebernehmen");
  if (await einer.isVisible()) await einer.click();
  else await vorschlag.getByRole("button", { name: /Muster/ }).first().click();
  const zuordnen = page.getByTestId("zuordnen");
  await expect(zuordnen.getByTestId("zuordnen-patient")).toContainText("Muster");
  await zuordnen.getByRole("button", { name: "Abbrechen" }).first().click();
  await detail.getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: /Löschen/ }).click();
  await page.getByTestId("bestaetigen").click();
  await api.ende();
});

/** Rahmen auf der Seitenansicht aufziehen – mit der Maus oder als Touch-Geste (Pointer-Ereignisse vom Typ „touch“) */
async function rahmenZiehen(page: import("@playwright/test").Page, von: [number, number], bis: [number, number], touch = false) {
  const flaeche = page.getByTestId("bereich-flaeche");
  await expect(flaeche).toBeVisible();
  const b = (await flaeche.boundingBox())!;
  const x0 = b.x + b.width * von[0], y0 = b.y + b.height * von[1], x1 = b.x + b.width * bis[0], y1 = b.y + b.height * bis[1];
  if (!touch) {
    await page.mouse.move(x0, y0);
    await page.mouse.down();
    await page.mouse.move((x0 + x1) / 2, (y0 + y1) / 2, { steps: 4 });
    await page.mouse.move(x1, y1, { steps: 4 });
    await page.mouse.up();
    return;
  }
  const art = { pointerType: "touch", pointerId: 7, isPrimary: true, bubbles: true };
  await flaeche.dispatchEvent("pointerdown", { ...art, clientX: x0, clientY: y0 });
  await flaeche.dispatchEvent("pointermove", { ...art, clientX: (x0 + x1) / 2, clientY: (y0 + y1) / 2 });
  await flaeche.dispatchEvent("pointermove", { ...art, clientX: x1, clientY: y1 });
  await flaeche.dispatchEvent("pointerup", { ...art, clientX: x1, clientY: y1 });
}

for (const touch of [false, true]) {
  test(`Erkennung verbessern (F189): falsch erkannt anmerken, richtigen Bereich markieren${touch ? " – mit Touch" : ""}`, async ({ page }) => {
    test.setTimeout(240_000);
    await page.goto("/scans");
    await page.getByTestId("scan-datei").setInputFiles(FOTO);
    const detail = page.getByTestId("scan-detail");
    await expect(detail.getByTestId("scan-status")).toHaveText("erkannt", { timeout: 180_000 });
    await detail.getByTestId("scan-zuordnen").click();
    const zuordnen = page.getByTestId("zuordnen");
    // Hinweis „So helfen Sie EPM, besser zu lesen“: wegklicken, über „?“ wieder aufrufen
    const hinweis = zuordnen.getByTestId("verbessern-hinweis");
    if (await hinweis.isVisible()) await zuordnen.getByTestId("verbessern-hinweis-zu").click();
    await zuordnen.getByTestId("verbessern-hilfe").click();
    await expect(hinweis).toContainText("So helfen Sie EPM, besser zu lesen");
    await zuordnen.getByTestId("verbessern-hinweis-zu").click();

    // falsch erkannt: Zeile verschwindet sofort („falscher Wert“ lernt nichts – andere Tests bleiben unberührt)
    const zeilen = zuordnen.getByTestId("laborzeile");
    const vorher = await zeilen.count();
    expect(vorher).toBeGreaterThan(1);
    await zeilen.first().getByTestId("falsch-erkannt").click();
    await page.getByRole("menuitem", { name: /Falscher Wert/ }).click();
    await expect(page.getByText(/Verworfen \(falscher Wert\)/).first()).toBeVisible();
    await expect(zeilen).toHaveCount(vorher - 1);

    // richtigen Bereich markieren: Rahmen um die Tabelle, nur dieser Teil wird neu gelesen
    await zuordnen.getByTestId("bereich-markieren").click();
    await expect(page.getByTestId("bereich-anleitung")).toContainText("Rahmen");
    await rahmenZiehen(page, [0.06, 0.17], [0.9, 0.3], touch);
    await expect(page.getByText(/aus dem markierten Bereich gelesen/).first()).toBeVisible({ timeout: 60_000 });
    await expect.poll(() => zeilen.count()).toBeGreaterThan(vorher - 1);
    await expect(zuordnen.getByText("Bereich", { exact: true }).first()).toBeVisible();

    // aufräumen: Scan löschen (nichts zugeordnet)
    await zuordnen.getByRole("button", { name: "Abbrechen" }).first().click();
    await detail.getByRole("button", { name: "Weitere Aktionen" }).click();
    await page.getByRole("menuitem", { name: /Löschen/ }).click();
    await page.getByTestId("bestaetigen").click();
  });
}

test("Gelernte Zuordnungen: Steuerung des Lernens (F189)", async ({ page }) => {
  await page.goto("/scans?bereich=gelernt");
  const gelernt = page.getByTestId("gelernt");
  await expect(gelernt.getByTestId("gelernt-korrigieren")).toContainText("Falsch erkannt");
  const steuerung = gelernt.getByTestId("gelernt-steuerung");
  await expect(steuerung).toBeVisible();
  // Mitarbeiter pflegen Vorlagen: dürfen pausieren und die Schwelle ändern – danach wieder zurück
  // Schalter folgt dem Stand des Servers (umgeschaltet nach der Antwort) – daher klicken und auf den Stand warten
  const pausieren = gelernt.getByTestId("lernen-pausieren");
  await pausieren.click();
  await expect(pausieren).toBeChecked();
  await expect(page.getByText(/Lernen pausiert/).first()).toBeVisible();
  await expect(steuerung).toContainText("Pausiert: Neues wird nicht gelernt");
  await pausieren.click();
  await expect(pausieren).not.toBeChecked();
  await expect(steuerung).not.toContainText("Pausiert:");
  await gelernt.getByTestId("lernen-schwelle").selectOption("3");
  await expect(page.getByText(/sicher ab 3 Bestätigungen/).first()).toBeVisible();
  await gelernt.getByTestId("lernen-schwelle").selectOption("2");
  await expect(page.getByText(/sicher ab 2 Bestätigungen/).first()).toBeVisible();
});
