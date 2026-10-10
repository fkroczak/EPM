/**
 * Menüpunkt „Scans“ (F160–F167) über die Oberfläche gegen den echten Stack – mit dem OCR-Dienst im Container „ocr“:
 * Foto eines Laborbefunds hochladen → Blatt wird gefunden, entzerrt, erkannt → Text kopieren → einem Testpatienten
 * zuordnen und die Laborwerte übernehmen → Dokument mit Text in der Akte, Befund mit Werten.
 *
 * Dazu F182 (Texterkennung lernt mit: gelernte Zuordnungen verwalten, Kennzahl), F183 (Scan erkennt den Patienten:
 * Vorschlag oben, Übernahme nur per Klick) und F189 (falsch erkannt anmerken, Bereich markieren mit Maus und Touch,
 * Steuerung des Lernens).
 */
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

const FOTO = "e2e/dateien/laborbefund-foto.jpg";

test("Foto eines Laborbefunds: erkennen, Text kopieren, zuordnen mit Laborwerten", async ({ page, context }) => {
  test.setTimeout(240_000);
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const api = await apiAls("mitarbeiter");
  const nachname = eindeutig("Scanprobe");
  const p = await api.post("patienten/", { nachname, vorname: "Erika", geburtsdatum: "1961-03-14", geschlecht: "w", ist_test: true });

  await page.goto("/scans");
  await expect(page.getByRole("heading", { name: "Scans" })).toBeVisible();
  await page.getByTestId("scan-datei").setInputFiles(FOTO);
  const detail = page.getByTestId("scan-detail");
  await expect(detail.getByTestId("scan-titel")).toHaveText("laborbefund-foto");
  // der OCR-Dienst arbeitet im eigenen Container; die Seite fragt nach dem Stand
  await expect(detail.getByTestId("scan-status")).toHaveText("erkannt", { timeout: 180_000 });
  await expect(detail.getByTestId("scan-text")).toContainText("Kalium");
  await expect(detail.getByTestId("scan-text")).toContainText("Albumin");
  await expect(detail.getByTestId("scan-seite").locator("img")).toBeVisible();
  // in der Navigation steht die Zahl der offenen Scans
  await expect(page.getByTestId("nav-scans").first()).toHaveAttribute("title", /Scans \(\d+\)/);

  // Text kopieren
  await detail.getByTestId("scan-kopieren").click();
  await expect(page.getByText("Text kopiert.")).toBeVisible();
  const kopiert = await page.evaluate(() => navigator.clipboard.readText());
  expect(kopiert).toContain("Natrium");

  // F183: Geburtsdatum und Vorname stehen im Dokument – Vorschlag oben, aber nie automatisch gewählt
  await expect(detail.getByTestId("patient-vorschlag")).toBeVisible();

  // Zuordnen mit Prüfansicht
  await detail.getByTestId("scan-zuordnen").click();
  const zuordnen = page.getByTestId("zuordnen");
  await zuordnen.getByPlaceholder(/Name, Nr\. oder Geburtsdatum/).fill(nachname);
  await zuordnen.getByRole("option", { name: new RegExp(nachname) }).click();
  await expect(zuordnen.getByTestId("zuordnen-patient")).toContainText(nachname);
  const tabelle = zuordnen.getByTestId("labor-pruefen");
  await expect(tabelle).toBeVisible();
  await expect(tabelle.getByTestId("laborzeile").first()).toBeVisible();
  // eine Zeile anklicken zeigt die Stelle im Bild
  await tabelle.getByTestId("laborzeile").first().click();
  await expect(detail.getByTestId("markierte-stelle")).toBeVisible();
  await zuordnen.getByTestId("zuordnen-speichern").click();
  await expect(page.getByTestId("zuletzt-zugeordnet")).toBeVisible();

  // in der Akte: Dokument mit erkanntem Text, Laborbefund mit Werten (Albumin von g/dl in g/l umgerechnet)
  const dokumente = await api.get(`dokumente/?patient=${p.id}`);
  const dok = dokumente.results[0];
  expect(dok.herkunft).toBe("scan");
  expect(dok.hat_text).toBeTruthy();
  const befunde = await api.get(`laborbefunde/?patient=${p.id}`);
  expect(befunde).toHaveLength(1);
  const werte = Object.fromEntries((befunde[0].werte as { bezeichnung: string; wert: string; einheit: string }[])
    .map((w) => [w.bezeichnung, w]));
  expect(Number(werte["Natrium"].wert)).toBe(138);
  expect(Number(werte["Albumin"].wert)).toBe(34);
  expect(werte["Albumin"].einheit).toBe("g/l");
  expect(befunde[0].abgenommen_am).toBe("2026-09-01");
  await api.ende();

  // im Reiter Dokumente: im erkannten Text suchen und den Text anzeigen
  await page.goto(`/patienten/${p.id}/dokumente`);
  await page.getByTestId("dokumente-suche").fill("Hypokali");
  await expect(page.getByTestId("dokumentliste")).toContainText("laborbefund-foto");
  await page.getByTestId("dokument-text-zeigen").click();
  await expect(page.getByTestId("dokument-text")).toContainText("Kalium");
});

test("Werte von Hand übertragen: BIA nicht erkannt – Feld wählen, Wert im Bild anklicken; Laborwert ergänzen", async ({ page }) => {
  test.setTimeout(240_000);
  const api = await apiAls("mitarbeiter");
  const nachname = eindeutig("Handwert");
  // anderes Geburtsdatum als im Dokument: kein automatischer Vorschlag, der Patient wird gesucht
  const p = await api.post("patienten/", { nachname, vorname: "Hanna", geburtsdatum: "1970-05-20", geschlecht: "w", ist_test: true });

  await page.goto("/scans");
  await page.getByTestId("scan-datei").setInputFiles(FOTO);
  const detail = page.getByTestId("scan-detail");
  await expect(detail.getByTestId("scan-status")).toHaveText("erkannt", { timeout: 180_000 });
  await detail.getByTestId("scan-zuordnen").click();
  const zuordnen = page.getByTestId("zuordnen");
  if (await zuordnen.getByTestId("zuordnen-patient").isVisible()) await zuordnen.getByRole("button", { name: "ändern" }).click();
  await zuordnen.getByPlaceholder(/Name, Nr\. oder Geburtsdatum/).fill(nachname);
  await zuordnen.getByRole("option", { name: new RegExp(nachname) }).click();
  await expect(zuordnen.getByTestId("zuordnen-patient")).toContainText(nachname);

  // BIA wurde nicht erkannt: einschalten, Feld wählen, Zahl im Bild anklicken
  const bia = zuordnen.getByTestId("zuordnen-bia");
  await bia.getByRole("checkbox").first().check();
  const gewicht = bia.getByRole("textbox", { name: "Gewicht (kg)" });
  await gewicht.click();
  await expect(page.getByTestId("wort-waehlen")).toContainText("Gewicht");
  await page.locator('[data-testid="waehlbares-wort"][data-wort="62"]').first().click();
  await expect(gewicht).toHaveValue("62");

  // Laborwert ergänzen: + Wert, Parameter wählen, Wert im Bild anklicken
  await zuordnen.getByTestId("labor-wert-neu").click();
  const neu = zuordnen.getByTestId("laborzeile").last();
  await neu.getByLabel("Parameter").selectOption({ label: "Phosphat" });
  await neu.getByLabel("Wert", { exact: true }).click();
  await page.locator('[data-testid="waehlbares-wort"][data-wort="1,12"]').first().click();
  await expect(neu.getByLabel("Wert", { exact: true })).toHaveValue("1,12");
  await expect(zuordnen.getByTestId("zuordnen-speichern")).toContainText("+ BIA");
  await zuordnen.getByTestId("zuordnen-speichern").click();
  await expect(page.getByTestId("zuletzt-zugeordnet")).toBeVisible();

  // F182: Kennzahl unten in der Liste, große Ansicht per Klick
  await page.getByTestId("kennzahl-korrekturen").click();
  await expect(page.getByTestId("kennzahl-gross")).toBeVisible();
  await page.getByRole("button", { name: "Schließen" }).click();

  // F182: gelernt wurde „Zink → Gewicht“ und „Kreatinin → Phosphat“ (absichtlich falsch angeklickt) – sperren und löschen
  await page.getByTestId("scans-gelernt").click();
  const gelernt = page.getByTestId("gelernt");
  await expect(gelernt.getByRole("heading", { name: "Gelernte Zuordnungen" })).toBeVisible();
  await gelernt.getByRole("searchbox").fill("Phosphat");
  const zeile = gelernt.getByTestId("gelernt-zeile").filter({ hasText: "Kreatinin" }).first();
  await expect(zeile).toContainText("Phosphat");
  await zeile.getByTestId("gelernt-sperren").click();
  await expect(zeile).toContainText("gesperrt");
  for (const [suche, wort] of [["Phosphat", "Kreatinin"], ["Gewicht", "Zink"]]) {
    await gelernt.getByRole("searchbox").fill(suche);
    const zeilen = gelernt.getByTestId("gelernt-zeile").filter({ hasText: wort });
    while (await zeilen.count()) {
      await zeilen.first().getByTestId("gelernt-loeschen").click();
      await page.getByTestId("bestaetigen").click();
      await expect(page.getByText("Gelernte Zuordnung gelöscht.").first()).toBeVisible();
    }
  }
  await gelernt.getByTestId("gelernt-zurueck").click();
  await expect(page.getByTestId("scanliste")).toBeVisible();

  const messungen = await api.get(`bia-messungen/?patient=${p.id}`);
  expect(Number((messungen.results ?? messungen)[0].gewicht_kg)).toBe(62);
  const befunde = await api.get(`laborbefunde/?patient=${p.id}`);
  const phosphat = (befunde[0].werte as { bezeichnung: string; wert: string }[]).find((w) => w.bezeichnung === "Phosphat");
  expect(Number(phosphat?.wert)).toBe(1.12);
  await api.ende();
});

test("Scan verlängern, Seite anpassen und löschen; Einstellungen unter Vorlagen", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/scans");
  await page.getByTestId("scan-datei").setInputFiles(FOTO);
  const detail = page.getByTestId("scan-detail");
  await expect(detail.getByTestId("scan-status")).toHaveText("erkannt", { timeout: 180_000 });
  // verlängern
  await expect(detail.getByTestId("scan-ablauf")).toContainText("gelöscht");
  await detail.getByTestId("scan-verlaengern").click();
  await expect(detail.getByTestId("scan-ablauf")).toBeVisible();
  // Seite anpassen: Schwarz-Weiß → neu aufbereitet und erkannt
  await detail.getByTestId("seite-bearbeiten").click();
  const dialog = page.getByRole("dialog");
  // Vorschau zeigt die aufbereitete Seite; die Ecken liegen auf der zweiten Ansicht
  await expect(dialog.getByTestId("seite-vorschau").getByRole("img")).toBeVisible();
  await dialog.getByRole("button", { name: "Ecken setzen" }).click();
  await expect(dialog.getByTestId("ecke-0")).toBeVisible();
  await dialog.getByRole("button", { name: "Schwarz-Weiß" }).click();
  await expect(dialog.getByTestId("seite-vorschau").getByRole("img")).toBeVisible();
  await dialog.getByTestId("seite-uebernehmen").click();
  await expect(detail.getByTestId("scan-status")).toHaveText(/wartet|wird erkannt|erkannt/);
  await expect(detail.getByTestId("scan-status")).toHaveText("erkannt", { timeout: 180_000 });
  await expect(detail.getByTestId("scan-text")).toContainText("Kalium");
  // löschen
  await detail.getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: "Löschen …" }).click();
  await page.getByTestId("bestaetigen").click();
  await expect(page.getByText("Scan gelöscht.")).toBeVisible();

  // Fristen und Fachwörter unter Vorlagen › Grenzwerte
  await page.goto("/admin/vorlagen");
  await page.getByRole("button", { name: "Grenzwerte" }).click();
  const karte = page.getByTestId("grenzwerte-scans");
  await expect(karte).toBeVisible();
  await expect(karte.getByLabel("Nicht zugeordnete Scans löschen nach")).toHaveValue("7");
});

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
  await gelernt.getByTestId("lernen-pausieren").check();
  await expect(page.getByText(/Lernen pausiert/).first()).toBeVisible();
  await gelernt.getByTestId("lernen-pausieren").uncheck();
  await gelernt.getByTestId("lernen-schwelle").selectOption("3");
  await expect(page.getByText(/sicher ab 3 Bestätigungen/).first()).toBeVisible();
  await gelernt.getByTestId("lernen-schwelle").selectOption("2");
  await expect(page.getByText(/sicher ab 2 Bestätigungen/).first()).toBeVisible();
});

test("Betrachter sehen „Scans“ nicht", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const seite = await ctx.newPage();
  await seite.goto("/");
  await expect(seite.getByTestId("seitenleiste")).toBeVisible();
  await expect(seite.getByTestId("nav-scans")).toHaveCount(0);
  await seite.goto("/scans");
  await expect(seite).toHaveURL(/\/$/);
  await ctx.close();
});

test("Akte: „Text erkennen“ (OCRmyPDF) und „Werte übernehmen“ an einem Dokument", async ({ page }) => {
  test.setTimeout(300_000);
  const api = await apiAls("mitarbeiter");
  const nachname = eindeutig("Aktetext");
  const p = await api.post("patienten/", { nachname, vorname: "Erika", geburtsdatum: "1961-03-14", geschlecht: "w", ist_test: true });
  const hoch = await api.roh.post("/api/dokumente/", {
    headers: await api.kopf(),
    multipart: { patient: String(p.id), titel: "Laborbefund (Foto)",
      datei: { name: "befund-foto.jpg", mimeType: "image/jpeg", buffer: readFileSync(FOTO) } },
  });
  expect(hoch.status()).toBe(201);
  const dok = await hoch.json();

  await page.goto(`/patienten/${p.id}/dokumente`);
  await page.getByTestId("dokumentliste").getByText("Laborbefund (Foto)").click();
  const details = page.getByTestId("dokument-details");
  // Text erkennen: Datei wird durch dieselbe PDF/A mit Textebene ersetzt
  await details.getByTestId("dokument-text-erkennen").click();
  await page.getByRole("dialog").getByRole("button", { name: "Erkennen und ersetzen" }).click();
  await expect(page.getByText("Text erkannt – das Dokument ist jetzt durchsuchbar.")).toBeVisible({ timeout: 240_000 });
  const neu = await api.get(`dokumente/${dok.id}/`);
  expect(neu.mime).toBe("application/pdf");
  expect(neu.sha256).not.toBe(dok.sha256);
  expect(neu.hat_text).toBeTruthy();
  await page.getByTestId("dokumente-suche").fill("Kalium");
  await expect(page.getByTestId("dokumentliste")).toContainText("Laborbefund (Foto)");

  // Werte übernehmen: Prüfansicht in „Scans“, kein neues Dokument
  await page.getByTestId("dokumentliste").getByText("Laborbefund (Foto)").click();
  await details.getByTestId("dokument-werte-uebernehmen").click();
  await expect(page).toHaveURL(/\/scans\?id=\d+/);
  const detail = page.getByTestId("scan-detail");
  await expect(detail.getByTestId("scan-status")).toHaveText("erkannt", { timeout: 180_000 });
  await expect(detail.getByTestId("scan-quelle")).toContainText(nachname);
  await detail.getByTestId("scan-zuordnen").click();
  const zuordnen = page.getByTestId("zuordnen");
  await expect(zuordnen.getByTestId("zuordnen-quelle")).toBeVisible();
  await expect(zuordnen.getByTestId("zuordnen-speichern")).toContainText("Übernehmen");
  await zuordnen.getByTestId("zuordnen-speichern").click();
  await expect(page.getByText(/verknüpft mit „Laborbefund \(Foto\)“/)).toBeVisible();
  const befunde = await api.get(`laborbefunde/?patient=${p.id}`);
  expect(befunde[0].dokument).toBe(dok.id);
  const dokumente = await api.get(`dokumente/?patient=${p.id}`);
  expect(dokumente.results).toHaveLength(1);
  await api.ende();
});
