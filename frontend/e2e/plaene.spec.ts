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
  // erster Plan je kg Körpergewicht vorbelegt wie im Altsystem (60 kg)
  await expect(editor).toContainText("Vorbelegt je kg Körpergewicht (60,0 kg) wie im Altsystem.");
  for (const [feld, wert] of [["Menge Glucose in g", "210"], ["Menge Aminosäuren in g", "72"], ["Menge Lipide in g", "60"],
    ["Natrium", "78"], ["Kalium", "42"], ["Phosphat", "18"], ["Calcium", "9"], ["Magnesium", "12"]]) {
    await expect(editor.getByLabel(feld)).toHaveValue(wert);
  }
  // Humanalbumin in ml ohne Energie, Lipide 9,15 kcal/g
  await expect(editor.getByLabel("Menge Humanalbumin in ml")).toHaveValue("");

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
  // Stabilität wie im Altsystem: Ca + Mg ≤ Mischbeutel ÷ 100 (2.100 ml → 21 mmol)
  await editor.getByLabel("Magnesium").fill("13");
  await expect(editor.getByTestId("ca-mg-stabilitaet")).toContainText("Calcium + Magnesium 22 mmol, Grenze 21 mmol (Mischbeutel ÷ 100): instabil");
  await expect(editor.getByTestId("plan-summe")).toContainText("Instabil: Calcium + Magnesium 22 mmol über 21 mmol");
  await editor.getByLabel("Magnesium").fill("6");
  await expect(editor.getByTestId("ca-mg-stabilitaet")).toContainText("Calcium + Magnesium 15 mmol, Grenze 21 mmol (Mischbeutel ÷ 100): stabil");
  await editor.getByLabel("Spurenelemente").selectOption({ label: "Addel N" });
  await editor.getByLabel("Katheterblock / Medikament").selectOption({ label: "Taurolin 2 %" });
  // Erweiterung: weiterer Bestandteil aus den Auswahllisten
  const weitere = editor.getByTestId("weitere-bestandteile");
  await weitere.getByRole("button", { name: "Bestandteil hinzufügen" }).click();
  await weitere.getByLabel("Bestandteil 1", { exact: true }).selectOption({ label: "Dipeptamin 20 %" });
  await weitere.getByLabel("Menge 1").fill("100");
  await weitere.getByLabel("Einheit 1").fill("ml");
  await weitere.getByLabel("Häufigkeit 1").fill("täglich");
  await editor.getByRole("button", { name: "+ Soluvit N" }).click();
  await editor.getByRole("button", { name: "+ Vitalipid adult" }).click();
  await editor.getByLabel("Laufzeit").fill("12");
  await editor.getByLabel("Tage pro Woche").fill("5");
  // wie auf der alten PDF: Mischbeutel = letztes Gewicht × 35 ml, Zusatzvolumen = Basislösung, Gesamtvolumen = Summe;
  // Laufzeit manuell, Rate = Gesamtvolumen ÷ Laufzeit (2.600 ÷ 12)
  await expect(editor.getByTestId("plan-mischbeutel")).toHaveText("2.100 ml");
  await expect(editor.getByTestId("plan-zusatzvolumen")).toHaveText("500 ml");
  await expect(editor.getByTestId("plan-gesamtvolumen")).toHaveText("2.600 ml");
  await expect(editor.getByTestId("plan-rate")).toHaveText("216,7 ml/h");
  await expect(editor.getByTestId("plan-volumen-hinweis")).toContainText("35 ml/kg × 60,0 kg");
  // Protonenpumpenhemmer mit den Codes des Altsystems; Zeiten morgens/mittags/abends
  await expect(editor.getByRole("checkbox", { name: "Morgens" })).toBeDisabled();
  await editor.getByLabel("Präparat (Kurzinfusion)").selectOption({ label: "Pantozol® 40 mg" });
  await editor.getByRole("button", { name: "Als Entwurf speichern" }).click();
  await expect(editor.getByText("Bitte die Zeiten angeben (morgens, mittags, abends).")).toBeVisible();
  await editor.getByRole("checkbox", { name: "Morgens" }).check();
  await editor.getByRole("checkbox", { name: "Abends" }).check();
  await editor.getByRole("textbox", { name: "Kommentar" }).fill("Start der heimparenteralen Ernährung");
  const summe = editor.getByTestId("plan-summe");
  await expect(summe).toContainText("1.509 kcal"); // 160·4 + 80·4 + 60·9,15
  await expect(summe).toContainText(/25,[12] kcal\/kg/);
  await editor.getByRole("button", { name: "Als Entwurf speichern" }).click();

  await expect(page).toHaveURL(/\/plaene\?plan=\d+/);
  await expect(page.getByText("Entwurf gespeichert.")).toBeVisible();
  const detail = page.getByTestId("plan-detail");
  // Ansicht wie PDF: die echte PDF aus der aktiven Dokumentvorlage (Text für Bildschirmleser liegt unter der Seite)
  const ansicht = detail.getByTestId("plan-ansicht");
  await expect(ansicht.getByTestId("ansicht-herkunft")).toContainText("Vorschau mit der aktiven Dokumentvorlage");
  const blatt = ansicht.getByTestId("pdf-text").first();
  await expect(blatt).toContainText(/E\s*N\s*T\s*W\s*U\s*R\s*F/);
  await expect(blatt).toContainText(/Aminosäuren\s+80\s+g\s+Glamin 13,4 %/);
  await expect(blatt).toContainText(/Kalorien\s+1\.509/);
  await expect(blatt).toContainText("Soluvit N | Vitalipid adult");
  await expect(blatt).toContainText("Taurolin 2 %");
  await expect(blatt).toContainText(/Dipeptamin 20 %\s+100\s+ml\s+täglich/);
  await expect(blatt).toContainText(/Volumen\s+2\.100\s+500\s+2\.600\s+ml/);
  await expect(blatt).toContainText(/Laufmenge je Stunde\s+216,7\s+ml\/h/);
  await expect(blatt).toContainText("Pantozol® Kurzinfusion 1 Amp. 40 mg in 50 ml Trägerlösung · 1-0-1");
  await expect(detail.getByTestId("planvergleich")).toHaveCount(0);
  // klein als Vorschau wie unter „Dokumente“ (Fehlerliste 02.10.2026, 1.3); ein Klick öffnet die große Ansicht
  await expect(ansicht.getByTestId("pdf-vorschau")).toBeVisible();
  expect((await ansicht.boundingBox())!.width).toBeLessThanOrEqual(342);
  await expect(ansicht.getByTestId("pdf-seite").first()).toHaveAttribute("data-fertig", "1");
  await ansicht.getByTestId("pdf-seite").first().click();
  const gross = page.getByRole("dialog").getByTestId("plan-gross");
  await expect(gross.getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await expect(gross.getByTestId("pdf-text").first()).toContainText(/Kalorien\s+1\.509/);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await ansicht.getByRole("button", { name: "Groß ansehen" }).click();
  await expect(page.getByRole("dialog").getByTestId("pdf-leser")).toBeVisible();
  await page.keyboard.press("Escape");

  // Freigeben (Recht „Pläne freigeben“)
  await detail.getByRole("button", { name: "Freigeben" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Freigeben" }).click();
  await expect(page.getByText("Plan freigegeben.")).toBeVisible();
  await expect(page.getByTestId("planliste")).toContainText("aktuell gültig");
  await expect(detail).toContainText(/Freigegeben am .* von Dr\. med\. M\. Medizin/);
  await expect(detail.getByRole("button", { name: "Bearbeiten" })).toHaveCount(0);
  // nach der Freigabe zeigt die Akte das gespeicherte Original
  await expect(detail.getByTestId("ansicht-herkunft")).toContainText("Gespeicherte PDF der Freigabe · Prüfsumme stimmt");
  // gespeicherte PDF (F37): Prüfsumme wird vor der Anzeige geprüft, Seiten werden gezeichnet
  await detail.getByRole("button", { name: "PDF öffnen" }).click();
  const pdfDialog = page.getByRole("dialog");
  await expect(pdfDialog.getByTestId("pdf-pruefung")).toContainText("Prüfsumme stimmt: unverändert seit der Freigabe");
  await expect(pdfDialog.getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await expect(pdfDialog.getByTestId("pdf-leser")).toContainText("1 Seite");
  await page.keyboard.press("Escape");
  const freigegeben = (await api.get(`infusionsplaene/?patient=${patient.id}&status=aktuell`)).results[0];
  expect(freigegeben.pdf_sha256).toMatch(/^[0-9a-f]{64}$/);
  expect(freigegeben.vorlage_version).toBeGreaterThanOrEqual(1);
  const dokumente = (await api.get(`dokumente/?patient=${patient.id}`)).results;
  expect(dokumente.map((d: { herkunft: string; mime: string; sha256: string }) => [d.herkunft, d.mime, d.sha256]))
    .toEqual([["system", "application/pdf", freigegeben.pdf_sha256]]);

  // Folgeplan: vorbelegt, Grenzwert wird im Backend geprüft, Änderungen markiert
  await page.getByTestId("aktenkopf").getByRole("button", { name: "Neuer Plan" }).click();
  await expect(editor).toContainText("Vorbelegt mit dem aktuellen Plan vom");
  await expect(editor.getByLabel("Menge Aminosäuren in g")).toHaveValue("80");
  await expect(editor.getByLabel("Präparat (Kurzinfusion)")).toHaveValue("1");
  await expect(editor.getByRole("checkbox", { name: "Morgens" })).toBeChecked();
  await expect(editor.getByRole("checkbox", { name: "Mittags" })).not.toBeChecked();
  await expect(editor.getByTestId("plan-rate")).toHaveText("216,7 ml/h");
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
  // Energie manuell setzen: gilt statt der berechneten, auch für die Grenzen
  await editor.getByLabel("Energie manuell").fill("1600");
  await expect(summe).toContainText("1.600 kcal (manuell)");
  await expect(summe).toContainText("berechnet wären 1.509 kcal");
  await editor.getByRole("button", { name: "Als Entwurf speichern" }).click();
  await expect(page.getByText("Entwurf gespeichert.").last()).toBeVisible();
  // auf den gespeicherten Entwurf warten (ein früherer Hinweis „Entwurf gespeichert.“ kann noch sichtbar sein)
  const entwurfVon = async () => (await api.get(`infusionsplaene/?patient=${patient.id}&status=entwurf`)).results[0];
  await expect.poll(async () => (await entwurfVon())?.kcal_manuell).toBe(1600);
  const ausVorlage = await entwurfVon();
  expect([ausVorlage.aminosaeuren_g, ausVorlage.phosphat_mmol, ausVorlage.magnesium_mmol]).toEqual([80, 12, 6]);
  expect([ausVorlage.kcal_manuell, ausVorlage.kcal, ausVorlage.kcal_berechnet]).toEqual([1600, 1600, 1509]);
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
  await expect.poll(async () => (await entwurfVon())?.id ?? null).not.toBeNull();
  const leer = await entwurfVon();
  expect([leer.aminosaeuren_g, leer.phosphat_mmol, leer.basis_praeparat]).toEqual([null, null, null]);
  await detail.getByRole("button", { name: "Verwerfen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Verwerfen" }).click();
  await expect(page.getByTestId("planliste").getByRole("listitem")).toHaveCount(1);

  const plaene = await api.get(`infusionsplaene/?patient=${patient.id}`);
  expect(plaene.results.map((p: { status: string; aminosaeuren_g: string; kcal: number }) => [p.status, p.aminosaeuren_g, p.kcal]))
    .toEqual([["aktuell", 80, 1509]]);
  expect([plaene.results[0].phosphat_mmol, plaene.results[0].calcium_mmol, plaene.results[0].magnesium_mmol]).toEqual([12, 9, 6]);
  expect(plaene.results[0].vitamine_namen).toEqual(["Soluvit N", "Vitalipid adult"]);
  expect(plaene.results[0].positionen.map((x: { praeparat_name: string; menge: number; einheit: string; haeufigkeit: string }) =>
    [x.praeparat_name, x.menge, x.einheit, x.haeufigkeit])).toEqual([["Dipeptamin 20 %", 100, "ml", "täglich"]]);
  expect([plaene.results[0].gesamtvolumen_ml, plaene.results[0].volumen_gewicht_kg, plaene.results[0].volumen_summe_ml,
    plaene.results[0].laufzeit_h, plaene.results[0].rate_ml_h]).toEqual([2100, 60, 2600, 12, 216.7]);
  expect([plaene.results[0].pantozol_stufe, plaene.results[0].pantozol_tage]).toEqual([1, 5]);
  expect([plaene.results[0].ca_mg_mmol, plaene.results[0].ca_mg_grenze_mmol, plaene.results[0].ca_mg_stabil]).toEqual([15, 21, true]);
  // Übersicht der Akte zeigt Gesamtvolumen und Rate des aktuellen Plans
  await page.goto(`/patienten/${patient.id}`);
  await expect(page.getByTestId("plan-volumen")).toContainText("Gesamtvolumen 2.600 ml · Rate 216,7 ml/h");
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
