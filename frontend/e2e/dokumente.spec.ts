/** Entwurf 9 · Dokumente und Entwurf 10 · Verlauf – Upload über Nginx bis in den Dateispeicher und zurück. */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, einfachePdf, kontrast, merken, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

// 1×1-Pixel-PNG
const PNG = Buffer.from("89504e470d0a1a0a0000000d4948445200000001000000010806000000" +
  "1f15c4890000000d49444154789c6300010000050001" + "0d0a2db40000000049454e44ae426082", "hex");

test("Dokumente hochladen, Typ am Inhalt prüfen, Metadaten ändern, ausblenden, herunterladen; Verlauf", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  const p = await api.post("patienten/", { nachname: eindeutig("Dok"), vorname: "Doris", geburtsdatum: "1980-08-08" });
  await page.goto(`/patienten/${p.id}/dokumente`);
  await expect(page.getByText("Noch keine Dokumente.")).toBeVisible();

  const eingabe = page.getByLabel("Dateien hochladen");
  await eingabe.setInputFiles([
    { name: "Arztbrief Klinik.txt", mimeType: "text/plain", buffer: Buffer.from("Arztbrief (E2E)\nAlles gut.\n", "utf-8") },
    { name: "Port-Foto.png", mimeType: "image/png", buffer: PNG },
    { name: "programm.exe", mimeType: "application/octet-stream", buffer: Buffer.from([0x4d, 0x5a, 0x00, 0x00, 0x01]) },
  ]);
  const uploads = page.getByTestId("uploads");
  await expect(uploads.getByRole("listitem").filter({ hasText: "programm.exe" })).toContainText("Erlaubt sind PDF, JPG, PNG und TXT.");
  await expect(uploads.getByRole("listitem").filter({ hasText: "Port-Foto.png" })).toContainText("hochgeladen");
  const liste = page.getByTestId("dokumentliste");
  await expect(liste.getByRole("button", { name: "Arztbrief Klinik" })).toBeVisible();
  await expect(liste.getByRole("button", { name: "Port-Foto" })).toBeVisible();
  await expect(liste.getByRole("row")).toHaveCount(3);

  // Metadaten
  await liste.getByRole("button", { name: "Arztbrief Klinik" }).click();
  const details = page.getByTestId("dokument-details");
  await expect(details.getByTitle("Vorschau Arztbrief Klinik")).toBeVisible();
  await details.getByLabel("Typ").selectOption({ label: "Arztbrief" });
  await details.getByLabel("Datum").fill("15.09.2026");
  await details.getByLabel("Titel").fill("Arztbrief Klinikum Nord");
  await details.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Dokument gespeichert.")).toBeVisible();
  const zeile = liste.getByRole("row").filter({ hasText: "Arztbrief Klinikum Nord" });
  await expect(zeile).toContainText("15.09.2026");
  await expect(zeile).toContainText("Arztbrief");

  // Datei über Nginx (X-Accel-Redirect) herunterladen: Inhalt unverändert
  const doks = await api.get(`dokumente/?patient=${p.id}`);
  const brief = doks.results.find((d: { titel: string }) => d.titel === "Arztbrief Klinikum Nord");
  expect(brief.mime).toBe("text/plain; charset=utf-8");
  const antwort = await page.request.get(`/api/dokumente/${brief.id}/datei/`);
  expect(antwort.status()).toBe(200);
  expect(await antwort.text()).toBe("Arztbrief (E2E)\nAlles gut.\n");
  expect(antwort.headers()["content-disposition"]).toContain("attachment");
  const bild = doks.results.find((d: { titel: string }) => d.titel === "Port-Foto");
  expect(bild.mime).toBe("image/png");

  // ausblenden und wieder anzeigen
  await liste.getByRole("button", { name: "Port-Foto" }).click();
  await details.getByRole("button", { name: "Ausblenden" }).click();
  await expect(page.getByText("Dokument ausgeblendet.")).toBeVisible();
  await expect(liste.getByRole("button", { name: "Port-Foto" })).toHaveCount(0);
  await page.getByLabel("Ausgeblendete anzeigen").check();
  await expect(liste.getByRole("button", { name: "Port-Foto" })).toBeVisible();

  // Verlauf: Upload und Änderung mit Person, nicht änderbar
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Verlauf" }).click();
  await page.getByRole("button", { name: "Dokumente" }).click();
  const verlauf = page.getByTestId("verlauf");
  await expect(verlauf.getByRole("row").filter({ hasText: "hochgeladen" })).toHaveCount(2);
  const geaendert = verlauf.getByRole("row").filter({ hasText: "Arztbrief Klinikum Nord" }).filter({ hasText: "geändert" }).first();
  await expect(geaendert).toContainText("S. Mitarbeit");
  await expect(geaendert).toContainText("Typ:");
  await page.getByLabel("Person").selectOption({ label: "S. Mitarbeit" });
  await expect(verlauf.getByRole("row").filter({ hasText: "hochgeladen" })).toHaveCount(2);
  await api.ende();
  merken("dokumente", { id: p.id });
});

test("Altdokument prüfen: Typ und Datum bestätigen", async ({ page }) => {
  await page.goto("/patienten?pruefen=altdokumente");
  await page.getByTestId("patientenliste").getByRole("link", { name: "Musterfrau, Erika" }).click();
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Dokumente/ }).click();
  const liste = page.getByTestId("dokumentliste");
  const alt = liste.getByRole("row").filter({ hasText: "Altdokument aus dem bisherigen System" });
  await expect(alt).toContainText("Typ prüfen");
  await alt.getByRole("button").click();
  const details = page.getByTestId("dokument-details");
  await expect(details).toContainText("Aus dem Altsystem übernommen. Bitte Typ und Datum prüfen.");
  await expect(details).toContainText("Altsystem · Datum Dateidatum (keine Metadaten)");
  await details.getByLabel("Typ").selectOption({ label: "Labor" });
  await details.getByRole("button", { name: "Typ und Datum bestätigen" }).click();
  await expect(page.getByText("Typ und Datum bestätigt.")).toBeVisible();
  await expect(alt).not.toContainText("Typ prüfen");
  await expect(alt).toContainText("Labor");
  merken("altdokument", { patient: Number(new URL(page.url()).pathname.split("/")[2]) });
});

test("PDF-Vorschau und Ansicht in EPM (ohne PDF-Programm des Browsers), Schaltflächen lesbar", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  const p = await api.post("patienten/", { nachname: eindeutig("Pdf"), vorname: "Paula", geburtsdatum: "1979-09-09" });
  await api.ende();
  await page.goto(`/patienten/${p.id}/dokumente`);
  await page.getByLabel("Dateien hochladen").setInputFiles([
    { name: "Befund.pdf", mimeType: "application/pdf", buffer: einfachePdf(["Seite eins (E2E)", "Seite zwei (E2E)"]) },
  ]);
  const liste = page.getByTestId("dokumentliste");
  await liste.getByRole("button", { name: "Befund" }).click();
  const details = page.getByTestId("dokument-details");
  // Vorschau wird von EPM selbst gezeichnet (Canvas), kein eingebettetes PDF-Programm
  const vorschau = details.getByTestId("pdf-vorschau");
  await expect(vorschau.locator('canvas[data-fertig="1"]')).toHaveCount(1);
  await expect(details.locator("iframe")).toHaveCount(0);
  await expect(vorschau).toContainText("Seite 1 von 2");
  await vorschau.getByRole("button", { name: "Nächste Seite" }).click();
  await expect(vorschau).toContainText("Seite 2 von 2");
  // die gezeichnete Seite ist nicht leer (Text schwarz auf weiß)
  const pixel = await vorschau.locator("canvas").evaluate((c: HTMLCanvasElement) => {
    const d = c.getContext("2d")!.getImageData(0, 0, c.width, c.height).data;
    let dunkel = 0;
    for (let i = 0; i < d.length; i += 4) if (d[i] < 128 && d[i + 3] > 0) dunkel++;
    return dunkel;
  });
  expect(pixel).toBeGreaterThan(50);

  // „Öffnen“: Primärknopf mit lesbarer Schrift (nicht Akzent auf Akzent), große Ansicht mit allen Seiten
  const oeffnen = details.getByRole("button", { name: "Öffnen" });
  expect(await kontrast(oeffnen)).toBeGreaterThan(4.5);
  await oeffnen.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByTestId("pdf-leser").locator('canvas[data-fertig="1"]')).toHaveCount(2);
  await dialog.getByRole("button", { name: "Vergrößern" }).click();
  await expect(dialog).toContainText("125 %");
  await dialog.getByRole("button", { name: "Schließen" }).click();
  // Herunterladen bleibt als Link mit lesbarer Schrift
  await expect(details.getByRole("link", { name: "Herunterladen" })).toBeVisible();
});
