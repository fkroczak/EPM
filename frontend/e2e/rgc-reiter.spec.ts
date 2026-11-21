/**
 * Eigene Reiter der Regeneration Clinic (Wunsch 21.11.2026): „Eingriffe“ (Therapie/Operation mit OPS- und ICD-Code,
 * Diagnose wandert mit der Genehmigung in die Diagnoseliste) und je ein Reiter für OP-Berichte, Röntgen,
 * Überweisungen und Einweisungen. In der DSKM gibt es diese Reiter nicht.
 *
 * Der Testzugang (e2e.test) ist in beiden Firmen Mediziner; eigene Akte je Test, am Ende wieder in der DSKM.
 */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("test") });

async function firmaSetzen(kuerzel: string) {
  const api = await apiAls("test");
  await api.post("auth/firma/", { firma: kuerzel });
  await api.ende();
}

async function neueAkte() {
  await firmaSetzen("rg");
  const api = await apiAls("test");
  const p = await api.post("patienten/", { nachname: eindeutig("Klinik"), vorname: "Karl", geburtsdatum: "1971-07-07" }) as
    { id: number };
  await api.ende();
  return p;
}

test.afterEach(async () => { await firmaSetzen("dskm"); });

test("RGC: Reiter je Dokumenttyp – Röntgen hochladen, nur dort sichtbar; in der DSKM keine eigenen Reiter", async ({ page }) => {
  const p = await neueAkte();
  await page.goto(`/patienten/${p.id}`);
  const reiter = page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link");
  for (const name of ["Eingriffe", "OP-Berichte", "Röntgen", "Überweisungen", "Einweisungen"]) {
    await expect(reiter.filter({ hasText: new RegExp(`^${name}`) })).toBeVisible();
  }
  await reiter.filter({ hasText: /^Röntgen/ }).click();
  await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}/roentgen$`));
  const bereich = page.getByTestId("dokumente-radiologie");
  await expect(bereich).toContainText("Noch keine Röntgen- und radiologische Befunde.");
  await bereich.getByLabel("Dateien hochladen").setInputFiles({
    name: "Thorax.txt", mimeType: "text/plain", buffer: Buffer.from("Röntgen Thorax p.a.: unauffällig"),
  });
  await expect(page.getByTestId("uploads")).toContainText("hochgeladen");
  const liste = page.getByTestId("dokumentliste");
  await expect(liste).toContainText("Thorax");
  await expect(liste).toContainText("Röntgen / Radiologie");
  await expect(reiter.filter({ hasText: /^Röntgen/ })).toContainText("1");
  // in den anderen Dokument-Reitern steht es nicht, unter „Dokumente“ schon
  await reiter.filter({ hasText: /^OP-Berichte/ }).click();
  await expect(page.getByTestId("dokumente-op_bericht")).toContainText("Noch keine OP-Berichte.");
  await reiter.filter({ hasText: /^Dokumente/ }).click();
  await expect(page.getByTestId("dokumentliste")).toContainText("Thorax");

  // DSKM: eine gemeinsame Akte (Max Mustermann, beide Firmen) zeigt die Reiter der Klinik nicht
  await firmaSetzen("dskm");
  const api = await apiAls("test");
  const max = (await api.get("patienten/?test=nur&suche=Mustermann") as { results: { id: number; vorname: string }[] })
    .results.find((x) => x.vorname === "Max")!;
  await api.ende();
  await page.goto(`/patienten/${max.id}`);
  await expect(reiter.filter({ hasText: /^Diagnosen/ })).toBeVisible();
  await expect(reiter.filter({ hasText: /^Eingriffe/ })).toHaveCount(0);
  await expect(reiter.filter({ hasText: /^Röntgen/ })).toHaveCount(0);
  await expect(reiter.filter({ hasText: /^OP-Berichte/ })).toHaveCount(0);
});

test("RGC: Eingriff eintragen, genehmigen – Diagnose steht in der Diagnoseliste", async ({ page }) => {
  const p = await neueAkte();
  await page.goto(`/patienten/${p.id}/eingriffe`);
  const seite = page.getByTestId("eingriffe");
  await expect(seite).toContainText("Noch kein Eingriff eingetragen.");
  await seite.getByRole("button", { name: "Neuer Eingriff" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Neuer Eingriff" })).toBeVisible();
  await dialog.getByRole("combobox", { name: "Operation", exact: true }).fill("Dünndarmresektion");
  await dialog.getByLabel("OPS-Codes").fill("5-455.01; 5-469.20");
  await dialog.getByRole("combobox", { name: "Diagnose", exact: true }).fill("Kurzdarmsyndrom");
  await dialog.getByLabel("ICD-Code").fill("k91.2");
  await expect(dialog).toContainText("Mit „genehmigt“ oder „durchgeführt“ kommt Kurzdarmsyndrom [K91.2G] in die Diagnoseliste.");
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toHaveCount(0);

  const detail = page.getByTestId("eingriff-detail");
  await expect(detail).toContainText("Dünndarmresektion");
  await expect(detail).toContainText("beantragt");
  await expect(detail).toContainText("5-455.01, 5-469.20");
  await expect(detail).toContainText("kommt mit der Genehmigung in die Diagnoseliste");

  await detail.getByRole("button", { name: "Genehmigt" }).click();
  const frage = page.getByRole("alertdialog").or(page.getByRole("dialog"));
  await expect(frage).toContainText("Kurzdarmsyndrom [K91.2G]");
  await frage.getByRole("button", { name: "Genehmigt" }).click();
  await expect(page.getByText("genehmigt – Diagnose in die Diagnoseliste übernommen.")).toBeVisible();
  await expect(detail).toContainText("in der Diagnoseliste");

  await detail.getByRole("link", { name: "Zur Diagnose" }).click();
  await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}/diagnosen`));
  await expect(page.getByTestId("diagnose-zeile")).toHaveCount(1);
  await expect(page.getByTestId("diagnose-zeile")).toContainText("Kurzdarmsyndrom");
  await expect(page.getByTestId("diagnose-zeile")).toContainText("K91.2");

  // nach dem Neuladen noch da (Datenbank), Verlauf zeigt die Schritte
  await page.goto(`/patienten/${p.id}/verlauf?bereich=eingriffe`);
  await expect(page.getByText("Diagnose übernommen").first()).toBeVisible();
  await page.goto(`/patienten/${p.id}/eingriffe`);
  await expect(page.getByTestId("eingriff-detail")).toContainText("genehmigt");
});
