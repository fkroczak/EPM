/** Falsch zugeordnete Dokumente (Festlegung 02.10.2026): dem richtigen Patienten zuordnen; endgültig löschen nur
 *  Mediziner mit Kennwort, Code aus der Authenticator-App und abgetipptem Bestätigungscode. */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, neuesKonto, totpBase32, zustand } from "./hilfen";

test.use({ storageState: zustand("mediziner") });

test("Dokument beim falschen Patienten dem richtigen zuordnen; Verlauf neutral bzw. mit Grund", async ({ page }) => {
  const api = await apiAls("mediziner");
  const sabine = await api.post("patienten/", { nachname: eindeutig("Falsch"), vorname: "Sabine", geburtsdatum: "1971-01-01" });
  const bernd = await api.post("patienten/", { nachname: eindeutig("Richtig"), vorname: "Bernd", geburtsdatum: "1961-06-06" });
  await page.goto(`/patienten/${sabine.id}/dokumente`);
  await page.getByLabel("Dateien hochladen").setInputFiles([
    { name: "Befund Bernd.txt", mimeType: "text/plain", buffer: Buffer.from("Befund für Bernd (E2E)\n", "utf-8") },
  ]);
  const liste = page.getByTestId("dokumentliste");
  await liste.getByRole("button", { name: "Befund Bernd" }).click();
  const details = page.getByTestId("dokument-details");
  await details.getByRole("button", { name: "Anderem Patienten zuordnen" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Richtiger Patient").fill(bernd.nachname);
  await dialog.getByRole("option", { name: new RegExp(bernd.nachname) }).click();
  await dialog.getByLabel("Grund").fill("beim falschen Patienten hochgeladen");
  await expect(dialog.getByRole("button", { name: "Zuordnen" })).toBeDisabled();
  await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "Zuordnen" }).click();
  await expect(page.getByText(`Dokument ${bernd.nachname}, Bernd zugeordnet.`)).toBeVisible();
  await expect(page.getByText("Noch keine Dokumente.")).toBeVisible();

  // Verlauf bei Sabine: neutral, ohne Titel und ohne Bernd
  await page.goto(`/patienten/${sabine.id}/verlauf`);
  await page.getByRole("button", { name: "Dokumente" }).click();
  const verlauf = page.getByTestId("verlauf");
  await expect(verlauf.getByRole("row").filter({ hasText: "Dokument wurde einer anderen Akte zugeordnet." })).toHaveCount(1);
  await expect(verlauf).not.toContainText("Befund Bernd");
  await expect(verlauf).not.toContainText(bernd.nachname);
  // bei Bernd: übernommen mit Grund, Datei unverändert
  await page.goto(`/patienten/${bernd.id}/verlauf`);
  await page.getByRole("button", { name: "Dokumente" }).click();
  const zeile = page.getByTestId("verlauf").getByRole("row").filter({ hasText: "von einer anderen Akte übernommen" });
  await expect(zeile).toContainText("Befund Bernd");
  await expect(zeile).toContainText("Grund: beim falschen Patienten hochgeladen");
  const doks = await api.get(`dokumente/?patient=${bernd.id}`);
  const antwort = await page.request.get(`/api/dokumente/${doks.results[0].id}/datei/`);
  expect(await antwort.text()).toBe("Befund für Bernd (E2E)\n");
  // Audit-Log hält den Vorgang vollständig fest
  const protokoll = await api.get("protokoll/?gruppe=dokument");
  expect(protokoll.results[0].beschreibung).toContain(`von ${sabine.nachname}, Sabine`);
  await api.ende();
});

test("Endgültig löschen: nur Mediziner, mit Kennwort, Authenticator-Code und Bestätigungscode", async ({ browser }) => {
  const konto = await neuesKonto("mediziner", "Martha", "Loesch");
  const ctx = await browser.newContext({ storageState: konto.zustand, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const api = await apiAls("mediziner");
  const p = await api.post("patienten/", { nachname: eindeutig("Fremd"), vorname: "Frida", geburtsdatum: "1975-05-05" });
  await page.goto(`/patienten/${p.id}/dokumente`);
  await page.getByLabel("Dateien hochladen").setInputFiles([
    { name: "Fremdes Dokument.txt", mimeType: "text/plain", buffer: Buffer.from("gehört nicht zur Stiftung\n", "utf-8") },
  ]);
  await page.getByTestId("dokumentliste").getByRole("button", { name: "Fremdes Dokument" }).click();
  await page.getByTestId("dokument-details").getByRole("button", { name: "Endgültig löschen" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByTestId("bestaetigungscode")).not.toHaveText("······");
  const code = (await dialog.getByTestId("bestaetigungscode").textContent())!.trim();
  expect(code).toMatch(/^[A-Z0-9]{6}$/);
  await dialog.getByLabel("Grund").fill("Dokument eines fremden Patienten, nicht aus der Stiftung");
  await dialog.getByLabel("Kennwort").fill("falsches-Kennwort");
  // Code des nächsten 30-s-Fensters: der Code der Einrichtung ist schon verbraucht
  await dialog.getByLabel("Code aus der Authenticator-App").fill(totpBase32(konto.geheim, Date.now() + 30_000));
  await dialog.getByLabel("Code abtippen").fill(code.toLowerCase());
  await dialog.getByRole("button", { name: "Endgültig löschen" }).click();
  await expect(dialog).toContainText("Kennwort falsch.");
  await dialog.getByLabel("Kennwort").fill(konto.kennwort);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(totpBase32(konto.geheim, Date.now() + 30_000));
  await dialog.getByRole("button", { name: "Endgültig löschen" }).click();
  await expect(page.getByText("Dokument endgültig gelöscht.")).toBeVisible();
  await expect(page.getByText("Noch keine Dokumente.")).toBeVisible();
  await page.goto(`/patienten/${p.id}/verlauf`);
  await page.getByRole("button", { name: "Dokumente" }).click();
  const zeile = page.getByTestId("verlauf").getByRole("row").filter({ hasText: "Datei und Inhalt entfernt" });
  await expect(zeile).toContainText("Grund: Dokument eines fremden Patienten");
  await expect(page.getByTestId("verlauf")).not.toContainText("Fremdes Dokument");
  const protokoll = await api.get("protokoll/?gruppe=dokument,fehlversuch");
  const texte = protokoll.results.map((e: { beschreibung: string }) => e.beschreibung).join("\n");
  expect(texte).toContain("„Fremdes Dokument“");
  expect(texte).toContain("endgültig gelöscht");
  expect(texte).toContain("abgelehnt: Kennwort falsch.");
  await api.ende();
  await ctx.close();
});
