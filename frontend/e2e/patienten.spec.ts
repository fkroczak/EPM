/** Entwurf 3 · Patientenliste und Entwurf 12 · Neuer Patient – gegen echtes Backend und PostgreSQL. */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

test("Patientenliste: Filter, Schnellfilter, Sortierung, abgeschlossene Akten", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Patienten" }).click();
  await expect(page.getByRole("heading", { name: "Patienten", level: 1 })).toBeVisible();
  const liste = page.getByTestId("patientenliste");
  const zeile = (name: string) => liste.getByRole("row").filter({ has: page.getByRole("link", { name }) });

  // Musterdaten: fünf Testpatienten in Betreuung, Max Mustermann mit Gewichtsverlust, Paula Beispiel mit Nickelallergie
  await expect(zeile("Mustermann, Max")).toBeVisible();
  await expect(zeile("Mustermann, Max").getByText("Testpatient")).toBeVisible();
  await expect(zeile("Mustermann, Max").getByText(/Gewicht −\d+,\d % in \d+ Mon\./)).toBeVisible();
  await expect(zeile("Mustermann, Max").getByLabel(/Trend fallend/)).toBeVisible();
  await expect(zeile("Beispiel, Paula").getByText("Nickelallergie")).toBeVisible();
  await expect(liste.getByRole("link", { name: "Demo, Karl" })).toHaveCount(0);

  // Freitext
  await page.getByLabel("Liste filtern").fill("Muster");
  await expect(liste.getByRole("link", { name: "Musterfrau, Erika" })).toBeVisible();
  await expect(liste.getByRole("link", { name: "Probe, Jonas" })).toHaveCount(0);
  await expect(page).toHaveURL(/suche=Muster/);
  await page.getByRole("button", { name: "Filter zurücksetzen" }).click();
  await expect(liste.getByRole("link", { name: "Probe, Jonas" })).toBeVisible();

  // Versorger und Ansprechpartner
  await page.getByLabel("Versorger").selectOption({ label: "Testversorger Süd (fiktiv)" });
  await expect(page).toHaveURL(/versorger=\d+/);
  await expect(liste.getByRole("link", { name: "Probe, Jonas" })).toBeVisible();
  await expect(liste.getByRole("link", { name: "Musterfrau, Erika" })).toHaveCount(0);
  await page.getByLabel("Versorger").selectOption({ label: "Alle Versorger" });
  await expect(page).not.toHaveURL(/versorger=/);
  await page.getByLabel("Ansprechpartner").selectOption({ label: "Herr Muster (Testversorger Nord (fiktiv))" });
  await expect(page).toHaveURL(/ansprechpartner=\d+/);
  // gleiche Abfrage direkt an die API: nur Patienten dieses Ansprechpartners
  const apId = new URL(page.url()).searchParams.get("ansprechpartner");
  const api = await apiAls("mitarbeiter");
  const direkt = await api.get(`patienten/?status=in_betreuung&ansprechpartner=${apId}`);
  expect(direkt.results.map((p: { nachname: string; ansprechpartner_name: string }) => `${p.nachname}/${p.ansprechpartner_name}`)).toEqual(["Mustermann/Herr Muster"]);
  await api.ende();
  await expect(liste.getByRole("link", { name: "Mustermann, Max" })).toBeVisible();
  await expect(liste.getByRole("link", { name: "Musterfrau, Erika" })).toHaveCount(0);
  await page.getByRole("button", { name: "Filter zurücksetzen" }).click();

  // Schnellfilter
  await page.getByRole("button", { name: /^Gewichtsverlust/ }).click();
  await expect(liste.getByRole("link", { name: "Mustermann, Max" })).toBeVisible();
  await expect(liste.getByRole("link", { name: "Musterfrau, Erika" })).toHaveCount(0);
  await page.getByRole("button", { name: /^Gewichtsverlust/ }).click();

  // Sortierung nach Name
  await page.getByRole("button", { name: /^Name/ }).click();
  await expect(page.getByRole("columnheader", { name: /Name/ })).toHaveAttribute("aria-sort", "ascending");
  const namen = await liste.locator("tbody tr td:nth-child(2) a").allTextContents();
  expect(namen).toEqual([...namen].sort((a, b) => a.localeCompare(b, "de")));

  // Abgeschlossene Akten
  await page.getByRole("button", { name: /^Abgeschlossen/ }).click();
  await expect(page.getByRole("heading", { name: "Abgeschlossene Akten" })).toBeVisible();
  await expect(zeile("Demo, Karl")).toContainText("Therapie beendet");
});

test("Neuer Patient: Prüfung, Doppelung, Anlegen mit Gewicht bei Aufnahme", async ({ page }) => {
  await page.goto("/patienten");
  await page.getByRole("link", { name: "Neuer Patient" }).click();
  await expect(page.getByRole("heading", { name: "Neuer Patient" })).toBeVisible();
  await expect(page.getByTestId("naechste-nummer")).toHaveText(/^\d{4}$/);

  // Pflichtfelder (Prüfung in der Oberfläche)
  await page.getByRole("button", { name: "Anlegen und Akte öffnen" }).click();
  await expect(page.getByText("Bitte Nachnamen eingeben.")).toBeVisible();
  await expect(page.getByText("Bitte Geburtsdatum eingeben.")).toBeVisible();

  // Doppelung: gleiches Geburtsdatum und ähnlicher Name wie Erika Musterfrau
  await page.getByLabel("Nachname").fill("Musterfrau");
  await page.getByLabel("Vorname").fill("Erika");
  await page.getByLabel("Geburtsdatum").fill("14.03.1961");
  const doppelung = page.getByTestId("doppelung");
  await expect(doppelung).toContainText("Musterfrau, Erika");
  await doppelung.getByRole("button", { name: "Nein, andere Person" }).click();
  await expect(doppelung).toHaveCount(0);

  // Prüfung im Backend: Größe außerhalb der Grenzwerte
  const nachname = eindeutig("Neumann");
  await page.getByLabel("Nachname").fill(nachname);
  await page.getByLabel("Vorname").fill("Nele");
  await page.getByLabel("Geburtsdatum").fill("02.05.1972");
  await page.getByLabel("Größe").fill("500");
  await page.getByLabel("Gewicht bei Aufnahme").fill("61,4");
  await page.getByLabel("Versorger", { exact: true }).selectOption({ label: "Testversorger Nord (fiktiv)" });
  await page.getByLabel("Ansprechpartner beim Versorger").selectOption({ label: "Frau Beispiel" });
  await page.getByLabel("Katheter").selectOption({ label: "Port" });
  await page.getByRole("radio", { name: "ja" }).check();
  await page.getByLabel("Diagnose").fill("Kurzdarmsyndrom (E2E)");
  await page.getByRole("button", { name: "Anlegen und Akte öffnen" }).click();
  await expect(page.getByText(/Größe muss zwischen/)).toBeVisible();
  await page.getByLabel("Größe").fill("168");
  await page.getByRole("button", { name: "Anlegen und Akte öffnen" }).click();
  await expect(page).toHaveURL(/\/patienten\/\d+$/);
  const id = Number(page.url().split("/").pop());

  // gespeichert in der Datenbank: Stammdaten, erste Gewichtsmessung, Diagnose
  const api = await apiAls("mitarbeiter");
  const p = await api.get(`patienten/${id}/`);
  expect([p.nachname, p.vorname, p.geburtsdatum, p.nickelallergie, p.groesse_cm]).toEqual([nachname, "Nele", "1972-05-02", "ja", 168]);
  expect(p.kopf.versorger).toBe("Testversorger Nord (fiktiv)");
  expect(p.kopf.ansprechpartner).toBe("Frau Beispiel");
  expect(p.kopf.katheter).toBe("Port");
  expect(p.diagnose).toContain("Kurzdarmsyndrom (E2E)");
  const gewichte = await api.get(`gewichte/?patient=${id}`);
  expect(gewichte.results.map((g: { gewicht_kg: number }) => g.gewicht_kg)).toEqual([61.4]);
  await api.ende();

  // erscheint in der Liste
  await page.goto(`/patienten?suche=${nachname}`);
  await expect(page.getByTestId("patientenliste").getByRole("link", { name: `${nachname}, Nele` })).toBeVisible();
});

test("Betrachter sieht die Liste, aber keinen Knopf „Neuer Patient“", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/patienten");
  await expect(page.getByTestId("patientenliste").getByRole("link", { name: "Mustermann, Max" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Neuer Patient" })).toHaveCount(0);
  await page.goto("/patienten/neu");
  await expect(page.getByText("Patienten anlegen darf nur, wer das Recht „Akten bearbeiten“ hat.")).toBeVisible();
  await ctx.close();
});
