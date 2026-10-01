/** Entwurf 18 · Dokumentvorlagen: Block ändern, Datenfeld einfügen, Prüfung, Vorschau mit Testpatient, Veröffentlichen. */
import { expect, test } from "@playwright/test";
import { apiAls, merken, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

test("Dokumentvorlage Infusionsplan: Text mit Datenfeld, Prüfung, Vorschau, Veröffentlichen", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  const vorher = (await api.get("vorlagen/")).find((v: { art: string }) => v.art === "infusionsplan");

  await page.goto("/admin/vorlagen");
  await page.getByRole("link", { name: "Dokumentvorlagen" }).click();
  await expect(page).toHaveURL(/\/admin\/vorlagen\/dokumente$/);
  const editor = page.getByTestId("dokumentvorlagen");
  await expect(editor.getByTestId("vorlage-stand")).toHaveText(`Version ${vorher.aktiv.version} ist aktiv`);
  const aufbau = editor.getByTestId("aufbau");
  // Startvorlage: Aufbau wie die PDF des Altsystems
  await expect(aufbau).toContainText("Zusammensetzung der Infusionslösung");
  await expect(aufbau).toContainText("Laufzeit und Volumen");
  await expect(editor.getByTestId("vorlage-seite")).toContainText("Empfehlung eines Infusionsplans");
  await expect(editor.getByTestId("vorlage-seite")).toContainText("Plan.gültig_ab");
  // Aufbau wie ein Laborbefund: Mineralstoffe neben der Zusammensetzung, Kopf wie in der Akte
  await expect(editor.getByTestId("nebeneinander")).toContainText("Natrium");
  await aufbau.getByRole("button", { name: /Mineralstoffe/ }).click();
  await expect(editor.getByTestId("block-eigenschaften").getByLabel("Neben dem vorherigen Block")).toHaveValue("drittel");
  await expect(editor.getByTestId("block-eigenschaften").getByLabel("Darstellung")).toHaveValue("befund");
  await aufbau.getByRole("button", { name: /Briefkopf/ }).click();
  await expect(editor.getByTestId("block-eigenschaften").getByLabel("Linie unter dem Logo")).not.toBeChecked();
  await aufbau.getByRole("button", { name: /Patient/ }).click();
  await expect(editor.getByTestId("block-eigenschaften").getByRole("group", { name: "Felder" })).toContainText("Kennzahlen");

  // Block „Freigabevermerk“ ändern, Datenfeld an der Schreibmarke einsetzen
  await aufbau.getByRole("button", { name: /Freigabevermerk/ }).click();
  const eigenschaften = editor.getByTestId("block-eigenschaften");
  const text = eigenschaften.getByLabel("Text");
  await expect(text).toHaveValue("Maschinell erstellt, geprüft und freigegeben von {{Plan.freigegeben_von}} am {{Plan.freigegeben_datum}}.");
  await text.fill("Rückfragen an die Stiftung, Stand ");
  await text.press("End");
  await editor.getByTestId("datenfelder").getByRole("button", { name: "Heute", exact: true }).click();
  await expect(text).toHaveValue("Rückfragen an die Stiftung, Stand {{Heute}}");
  await eigenschaften.getByRole("button", { name: "Fett" }).click();
  await expect(editor.getByTestId("vorlage-stand")).toHaveText("Ungespeicherte Änderungen");

  // ein unbekannter Platzhalter wird vom Server abgewiesen
  await text.fill("Kontostand {{Patient.Kontostand}}");
  await editor.getByRole("button", { name: "Entwurf speichern" }).click();
  await expect(editor.getByTestId("vorlage-fehler")).toContainText("unbekanntes Datenfeld „Patient.Kontostand“");
  await text.fill("Rückfragen an die Stiftung, Stand {{Heute}}");

  // neuer Baustein hinter dem markierten Block
  await editor.getByTestId("bausteine").getByRole("button", { name: "+ Trennlinie" }).click();
  await expect(eigenschaften).toContainText("Trennlinie");
  await editor.getByRole("button", { name: "Entwurf speichern" }).click();
  await expect(page.getByText("Entwurf gespeichert.")).toBeVisible();
  await expect(editor.getByTestId("vorlage-stand")).toContainText("Entwurf · gespeichert");
  const entwurf = await api.get("vorlagen/infusionsplan/entwurf/");
  expect(entwurf.ist_entwurf).toBe(true);
  const hinweis = entwurf.bloecke.find((b: { id: string }) => b.id === "freigabe");
  expect([hinweis.text, hinweis.optionen.fett]).toEqual(["Rückfragen an die Stiftung, Stand {{Heute}}", true]);
  const ihr = entwurf.bloecke.findIndex((b: { id: string }) => b.id === "freigabe");
  expect(entwurf.bloecke[ihr + 1].typ).toBe("trennlinie");

  // Vorschau mit Testpatient (PDF mit pdf.js gezeichnet)
  await editor.getByRole("button", { name: "Vorschau mit Testpatient" }).click();
  const vorschau = page.getByTestId("vorlage-vorschau");
  await expect(vorschau.getByLabel("Testpatient")).not.toHaveValue("");
  await expect(vorschau.getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await page.keyboard.press("Escape");

  // Veröffentlichen → neue aktive Version, alte bleibt erhalten
  await editor.getByRole("button", { name: "Veröffentlichen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Veröffentlichen" }).click();
  await expect(page.getByText(`Version ${vorher.aktiv.version + 1} veröffentlicht.`)).toBeVisible();
  await expect(editor.getByTestId("vorlage-stand")).toHaveText(`Version ${vorher.aktiv.version + 1} ist aktiv`);
  await expect(editor.getByTestId("versionen")).toContainText(`v${vorher.aktiv.version}`);
  const nachher = (await api.get("vorlagen/")).find((v: { art: string }) => v.art === "infusionsplan");
  expect([nachher.aktiv.version, nachher.entwurf]).toEqual([vorher.aktiv.version + 1, null]);
  expect(nachher.versionen.map((v: { status: string }) => v.status)).toEqual(["aktiv", ...vorher.versionen.map(() => "abgeloest")]);
  // mitgelieferte Startvorlage als Grundlage laden (z. B. nach einem Update mit neuem Aufbau)
  await editor.getByRole("button", { name: "Mitgelieferte Startvorlage laden" }).click();
  await expect(page.getByText("Mitgelieferte Startvorlage als Grundlage geladen")).toBeVisible();
  await expect(editor.getByTestId("vorlage-stand")).toHaveText("Ungespeicherte Änderungen");
  await api.ende();
  merken("vorlage", { version: nachher.aktiv.version });
});

test("Betrachter hat keinen Zugang zu den Dokumentvorlagen", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/admin/vorlagen/dokumente");
  await expect(page.getByTestId("dokumentvorlagen")).toHaveCount(0);
  const api = await apiAls("betrachter");
  await expect(api.get("vorlagen/")).rejects.toThrow(/403/);
  await api.ende();
  await ctx.close();
});
