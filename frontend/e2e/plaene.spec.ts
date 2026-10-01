/** Entwürfe 7 und 8 · Infusionsplan anlegen, Plausibilität, freigeben, Vorbelegung, Vergleich, Verwerfen. */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, merken, zustand } from "./hilfen";

test.use({ storageState: zustand("mediziner") });

test("Erster Plan, Freigabe, Folgeplan mit markierten Änderungen, Verwerfen", async ({ page }) => {
  const api = await apiAls("mediziner");
  const patient = await api.post("patienten/", { nachname: eindeutig("Plan"), vorname: "Paul", geburtsdatum: "1970-02-02" });
  await api.post("gewichte/", { patient: patient.id, gewicht_kg: "60.0", quelle: "telefonisch" });

  await page.goto(`/patienten/${patient.id}/plaene`);
  await expect(page.getByText("Noch kein Infusionsplan.")).toBeVisible();
  await page.getByTestId("aktenkopf").getByRole("button", { name: "Neuer Plan" }).click();
  const editor = page.getByTestId("plan-editor");
  await expect(editor).toContainText("Erster Plan dieses Patienten.");

  await editor.getByLabel("Präparat", { exact: true }).selectOption({ label: "Sterofundin" });
  await editor.getByLabel("Volumen").fill("500");
  await editor.getByLabel("Präparat Glucose").selectOption({ label: "Glucose 70 %" });
  await editor.getByLabel("Menge Glucose in g").fill("160");
  await editor.getByLabel("Präparat Aminosäuren").selectOption({ label: "Glamin 13,4 %" });
  await editor.getByLabel("Menge Aminosäuren in g").fill("80");
  await editor.getByLabel("Präparat Lipide").selectOption({ label: "Clinoleic 20 %" });
  await editor.getByLabel("Menge Lipide in g").fill("60");
  await editor.getByLabel("Natrium").fill("78");
  await editor.getByLabel("Kalium").fill("40");
  await editor.getByLabel("Phosphat").fill("12");
  await editor.getByLabel("Calcium").fill("9");
  await editor.getByLabel("Magnesium").fill("6");
  await editor.getByLabel("Spurenelemente").selectOption({ label: "Addel N" });
  await editor.getByLabel("Katheterblock / Medikament").selectOption({ label: "Taurolin 2 %" });
  await editor.getByLabel("Katheterblock / Medikament").selectOption({ label: "Taurolin 2 %" });
  await editor.getByRole("button", { name: "+ Soluvit N" }).click();
  await editor.getByRole("button", { name: "+ Vitalipid adult" }).click();
  await editor.getByLabel("Laufzeit").fill("12");
  await editor.getByLabel("Tage pro Woche").fill("5");
  await editor.getByRole("textbox", { name: "Kommentar" }).fill("Start der heimparenteralen Ernährung");
  const summe = editor.getByTestId("plan-summe");
  await expect(summe).toContainText("1.500 kcal");
  await expect(summe).toContainText("25,0 kcal/kg");
  await editor.getByRole("button", { name: "Als Entwurf speichern" }).click();

  await expect(page).toHaveURL(/\/plaene\?plan=\d+/);
  await expect(page.getByText("Entwurf gespeichert.")).toBeVisible();
  const detail = page.getByTestId("plan-detail");
  const blatt = detail.getByTestId("pdf-ansicht");
  await expect(blatt).toContainText("ENTWURF");
  await expect(blatt).toContainText("Glamin 13,4 % · 80 g");
  await expect(blatt).toContainText("1.500 kcal");
  await expect(blatt).toContainText("Soluvit N | Vitalipid adult");
  await expect(blatt).toContainText("Taurolin 2 %");
  await expect(detail.getByTestId("planvergleich")).toHaveCount(0);

  // Freigeben (Recht „Pläne freigeben“)
  await detail.getByRole("button", { name: "Freigeben" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Freigeben" }).click();
  await expect(page.getByText("Plan freigegeben.")).toBeVisible();
  await expect(page.getByTestId("planliste")).toContainText("aktuell gültig");
  await expect(detail).toContainText(/Freigegeben am .* von Dr\. med\. M\. Medizin/);
  await expect(detail.getByRole("button", { name: "Bearbeiten" })).toHaveCount(0);

  // Folgeplan: vorbelegt, Grenzwert wird im Backend geprüft, Änderungen markiert
  await page.getByTestId("aktenkopf").getByRole("button", { name: "Neuer Plan" }).click();
  await expect(editor).toContainText("Vorbelegt mit dem aktuellen Plan vom");
  await expect(editor.getByLabel("Menge Aminosäuren in g")).toHaveValue("80");
  await editor.getByLabel("Menge Glucose in g").fill("2000");
  await expect(summe).toContainText("Glucose 2.000 g außerhalb");
  await editor.getByRole("button", { name: "Als Entwurf speichern" }).click();
  await expect(editor.getByText(/Wert außerhalb der Plausibilitätsgrenzen/)).toBeVisible();
  await editor.getByLabel("Menge Glucose in g").fill("160");
  await editor.getByLabel("Menge Aminosäuren in g").fill("90");
  await expect(editor.getByLabel("Menge Aminosäuren in g")).toHaveClass(/border-warn/);
  await expect(summe).toContainText("+40");
  await expect(summe).toContainText(/Geänderte Werte\s*1/);
  await editor.getByRole("button", { name: "Als Entwurf speichern" }).click();
  await expect(page.getByText("Entwurf gespeichert.")).toBeVisible();

  await detail.getByRole("button", { name: "Vergleich mit Vorgänger" }).click();
  const vergleich = detail.getByTestId("planvergleich");
  await expect(vergleich).toContainText("2 Werte geändert gegenüber dem Plan vom");
  await expect(vergleich.getByRole("row").filter({ hasText: "Aminosäuren" })).toContainText("geändert");
  await expect(vergleich.getByRole("row").filter({ hasText: "Glucose" })).not.toContainText("geändert");

  // es gibt nur einen Entwurf je Patient: „Neuer Plan“ führt zum vorhandenen Entwurf
  await page.goto(`/patienten/${patient.id}/plaene/neu`);
  await expect(page.getByRole("heading", { name: "Entwurf bearbeiten" })).toBeVisible();
  await page.goto(`/patienten/${patient.id}/plaene`);

  await detail.getByRole("button", { name: "Verwerfen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Verwerfen" }).click();
  await expect(page.getByText("Entwurf verworfen.")).toBeVisible();
  await expect(page.getByTestId("planliste").getByRole("listitem")).toHaveCount(1);

  // „Als Vorlage für neuen Plan“: ein früherer Plan mit allen Werten als Grundlage
  await detail.getByRole("button", { name: "Als Vorlage für neuen Plan" }).click();
  await expect(editor).toContainText("Vorlage geladen");
  await expect(editor.getByLabel("Menge Aminosäuren in g")).toHaveValue("80");
  await expect(editor.getByLabel("Phosphat")).toHaveValue("12");
  await editor.getByRole("button", { name: "Als Entwurf speichern" }).click();
  await expect(page.getByText("Entwurf gespeichert.").last()).toBeVisible();
  const ausVorlage = (await api.get(`infusionsplaene/?patient=${patient.id}&status=entwurf`)).results[0];
  expect([ausVorlage.aminosaeuren_g, ausVorlage.phosphat_mmol, ausVorlage.magnesium_mmol]).toEqual([80, 12, 6]);
  await detail.getByRole("button", { name: "Verwerfen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Verwerfen" }).click();
  await expect(page.getByTestId("planliste").getByRole("listitem")).toHaveCount(1);

  // „Leer beginnen“: alle Felder leer, Vergleich weiter gegen den aktuellen Plan
  await page.getByTestId("aktenkopf").getByRole("button", { name: "Neuer Plan" }).click();
  await expect(editor.getByLabel("Menge Aminosäuren in g")).toHaveValue("80");
  await editor.getByRole("button", { name: "Leer beginnen" }).click();
  await expect(editor).toContainText("Leer begonnen.");
  await expect(editor.getByLabel("Menge Aminosäuren in g")).toHaveValue("");
  await expect(editor.getByLabel("Phosphat")).toHaveValue("");
  await editor.getByRole("button", { name: "Als Entwurf speichern" }).click();
  await expect(page.getByText("Entwurf gespeichert.").last()).toBeVisible();
  const leer = (await api.get(`infusionsplaene/?patient=${patient.id}&status=entwurf`)).results[0];
  expect([leer.aminosaeuren_g, leer.phosphat_mmol, leer.basis_praeparat]).toEqual([null, null, null]);
  await detail.getByRole("button", { name: "Verwerfen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Verwerfen" }).click();
  await expect(page.getByTestId("planliste").getByRole("listitem")).toHaveCount(1);

  const plaene = await api.get(`infusionsplaene/?patient=${patient.id}`);
  expect(plaene.results.map((p: { status: string; aminosaeuren_g: string; kcal: number }) => [p.status, p.aminosaeuren_g, p.kcal]))
    .toEqual([["aktuell", 80, 1500]]);
  expect([plaene.results[0].phosphat_mmol, plaene.results[0].calcium_mmol, plaene.results[0].magnesium_mmol]).toEqual([12, 9, 6]);
  expect(plaene.results[0].vitamine_namen).toEqual(["Soluvit N", "Vitalipid adult"]);
  await api.ende();
  merken("plan", { patient: patient.id });
});

test("Mitarbeiter sieht Pläne, legt aber keine an", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("mitarbeiter"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/patienten");
  await page.getByTestId("patientenliste").getByRole("link", { name: "Musterfrau, Erika" }).click();
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Infusionspläne/ }).click();
  await expect(page.getByTestId("planliste")).toContainText("Entwurf");
  await expect(page.getByRole("button", { name: "Neuer Plan" })).toHaveCount(0);
  await expect(page.getByTestId("plan-detail").getByRole("button", { name: "Freigeben" })).toHaveCount(0);
  await ctx.close();
});
