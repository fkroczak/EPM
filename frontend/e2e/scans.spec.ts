/**
 * Menüpunkt „Scans“ (F160–F167) über die Oberfläche gegen den echten Stack – mit dem OCR-Dienst im Container „ocr“:
 * Foto eines Laborbefunds hochladen → Blatt wird gefunden, entzerrt, erkannt → Text kopieren → einem Testpatienten
 * zuordnen und die Laborwerte übernehmen → Dokument mit Text in der Akte, Befund mit Werten.
 */
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
  await expect(dialog.getByTestId("ecke-0")).toBeVisible();
  await dialog.getByRole("button", { name: "Schwarz-Weiß" }).click();
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
