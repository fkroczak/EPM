/** Entwürfe 4, 5, 6 · Patientenakte: Kopf, Übersicht mit Gewicht, Diagnose & Therapie, Kontakte, Abschluss. */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, eindeutig, merken, stackNeuStarten, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

function vorTagen(tage: number) {
  const d = new Date();
  d.setDate(d.getDate() - tage);
  return d.toISOString().slice(0, 10);
}

/** frischer Patient nur für diesen Test (Musterdaten bleiben für die anderen Tests unverändert) */
async function neuerPatient(gewichte: [number, string][] = []) {
  const api = await apiAls("mitarbeiter");
  const nachname = eindeutig("Akte");
  const p = await api.post("patienten/", { nachname, vorname: "Alma", geburtsdatum: "1966-04-12", geschlecht: "w", groesse_cm: "165" });
  for (const [tage, kg] of gewichte) await api.post("gewichte/", { patient: p.id, gewicht_kg: kg, gemessen_am: vorTagen(tage), quelle: "telefonisch" });
  await api.ende();
  return { id: p.id as number, name: `${nachname}, Alma` };
}

async function oeffnen(page: Page, id: number, reiter = "") {
  await page.goto(`/patienten/${id}${reiter}`);
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
}

test("Akte aus der Liste öffnen: Kopf mit Kerndaten und Gewichtswarnung", async ({ page }) => {
  await page.goto("/patienten");
  await page.getByTestId("patientenliste").getByRole("link", { name: "Mustermann, Max" }).click();
  const kopf = page.getByTestId("aktenkopf");
  await expect(kopf.getByRole("heading", { name: "Mustermann, Max" })).toBeVisible();
  await expect(kopf.getByText("Testpatient")).toBeVisible();
  const zahlen = page.getByTestId("kennzahlen");
  await expect(zahlen).toContainText("Hickman");
  await expect(zahlen).toContainText("Testversorger Nord (fiktiv)");
  await expect(zahlen).toContainText(/↓ \d+,\d %/);
  await expect(page.getByTestId("gewichtstrend")).toContainText("Hinweis ab mehr als 5 % in 3 Monaten");
  await expect(page.getByTestId("gewichtsdiagramm")).toBeVisible();
  for (const r of ["Übersicht", "Diagnose & Therapie", "Kontakte", "Infusionspläne", "Dokumente", "Verlauf"]) {
    await expect(page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: new RegExp(`^${r}`) })).toBeVisible();
  }
  await expect(page.getByTestId("aktueller-plan")).toContainText("kcal");
});

test("Gewicht erfassen, Plausibilität, korrigieren, Zeitraum", async ({ page }) => {
  const p = await neuerPatient([[400, "62.0"], [95, "61.5"], [10, "61.0"]]);
  await oeffnen(page, p.id);
  const karte = page.getByTestId("gewichtskarte");
  await expect(karte.getByTestId("aktuelles-gewicht")).toHaveText("61,0 kg");

  // Schnellaktion „Gewicht“ setzt den Fokus ins Eingabefeld
  await page.getByTestId("aktenkopf").getByRole("button", { name: "Gewicht" }).click();
  await expect(karte.getByLabel("Neues Gewicht")).toBeFocused();

  // Backend weist unplausible Werte ab
  await karte.getByLabel("Neues Gewicht").fill("400");
  await karte.getByRole("button", { name: "Speichern" }).click();
  await expect(karte.getByText(/Gewicht muss zwischen/)).toBeVisible();

  await karte.getByLabel("Neues Gewicht").fill("60,4");
  await karte.getByLabel("Quelle").selectOption({ label: "Versorger" });
  await karte.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Gewicht 60,4 kg gespeichert.")).toBeVisible();
  await expect(karte.getByTestId("aktuelles-gewicht")).toHaveText("60,4 kg");
  await expect(page.getByTestId("kennzahlen")).toContainText("60,4 kg");

  // Zeitraum: 12 Monate zeigt 3 Messungen, „Alle“ 4
  await expect(karte).toContainText("3 Messungen im Zeitraum");
  await karte.getByRole("button", { name: "Alle" }).click();
  await expect(karte).toContainText("4 Messungen im Zeitraum");

  // korrigieren
  await karte.getByRole("button", { name: /Messwerte anzeigen/ }).click();
  const zeile = karte.getByTestId("messwerte").getByRole("row").filter({ hasText: "60,4 kg" });
  await zeile.getByRole("button", { name: "Korrigieren" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Gewicht (kg)").fill("60,6");
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(karte.getByTestId("messwerte")).toContainText("60,6 kg");

  // gespeichert in der Datenbank
  const api = await apiAls("mitarbeiter");
  const werte = await api.get(`gewichte/?patient=${p.id}`);
  expect(werte.results.map((g: { gewicht_kg: number }) => g.gewicht_kg)).toEqual([60.6, 61, 61.5, 62]);
  expect(werte.results[0].quelle).toBe("versorger");
  await api.ende();
  merken("gewicht", { id: p.id });
});

test("Diagnose und Therapie bearbeiten, Versionen ansehen", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id, "/therapie");
  const diagnose = page.getByTestId("karte-diagnose");
  await diagnose.getByRole("button", { name: "Bearbeiten" }).click();
  const editor = diagnose.getByRole("textbox", { name: "Diagnose" });
  await editor.fill("Kurzdarmsyndrom nach Resektion");
  await diagnose.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Diagnose gespeichert.")).toBeVisible();
  await expect(diagnose.getByTestId("version-diagnose")).toContainText("Version 1");

  await diagnose.getByRole("button", { name: "Bearbeiten" }).click();
  await editor.click();
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  await diagnose.getByRole("button", { name: "Fett" }).click();
  await page.keyboard.type("Typ II");
  await diagnose.getByRole("button", { name: "Speichern" }).click();
  await expect(diagnose.locator(".richtext strong")).toHaveText("Typ II");
  await expect(diagnose.getByTestId("version-diagnose")).toContainText("Version 2");

  await diagnose.getByRole("button", { name: "Versionen" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: /Version 2 · aktuell/ })).toBeVisible();
  await dialog.getByRole("button", { name: /^Version 1/ }).click();
  await expect(dialog.getByTestId("fassung")).toHaveText("Kurzdarmsyndrom nach Resektion");
  await page.keyboard.press("Escape");

  // Therapie: Editor ist direkt offen, Formatierung über die Werkzeugleiste
  const therapie = page.getByTestId("karte-therapie");
  await therapie.getByRole("textbox", { name: "Therapie" }).click();
  await therapie.getByRole("button", { name: "Aufzählung" }).click();
  await page.keyboard.type("HPE 5×/Woche über Port");
  await therapie.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Therapie gespeichert.")).toBeVisible();

  // nach Neuladen aus der Datenbank, Übersicht zeigt beides
  await oeffnen(page, p.id);
  await expect(page.locator(".richtext li").filter({ hasText: "HPE 5×/Woche über Port" })).toBeVisible();
  const api = await apiAls("mitarbeiter");
  const akte = await api.get(`patienten/${p.id}/`);
  expect(akte.diagnose).toBe("<p>Kurzdarmsyndrom nach Resektion</p><p><strong>Typ II</strong></p>");
  expect(akte.therapie).toBe("<ul><li><p>HPE 5×/Woche über Port</p></li></ul>");
  await api.ende();
  merken("diagnose", { id: p.id });
});

test("Kontakt mit Wiedervorlage erfassen, suchen, stornieren", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id);
  await page.getByTestId("aktenkopf").getByRole("button", { name: "Kontakt" }).click();
  await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}/kontakte$`));
  const neu = page.getByTestId("neuer-kontakt");
  const editor = neu.getByRole("textbox", { name: "Neuer Kontakt" });
  await expect(editor).toBeFocused();
  await editor.fill("Telefonat: Appetit schlechter, Trinkmenge dokumentieren.");
  await neu.getByLabel("Wiedervorlage").check();
  await neu.getByLabel("Art").selectOption({ label: "Rückruf" });
  await neu.getByLabel("Uhrzeit").fill("10:00");
  await neu.getByRole("button", { name: "Kontakt speichern" }).click();
  await expect(page.getByText("Kontakt und Wiedervorlage gespeichert.")).toBeVisible();
  const liste = page.getByTestId("kontaktliste");
  const erster = liste.getByTestId("kontakt").first();
  await expect(erster).toContainText("Appetit schlechter");
  await expect(erster).toContainText("Rückruf");
  await expect(erster).toContainText("S. Mitarbeit");

  // zweiter Kontakt und Suche
  await editor.fill("Versorger: Lieferung bestätigt.");
  await neu.getByRole("button", { name: "Kontakt speichern" }).click();
  await expect(liste.getByTestId("kontakt")).toHaveCount(2);
  await page.getByLabel("In Kontakten suchen").fill("Appetit");
  await expect(liste.getByTestId("kontakt")).toHaveCount(1);
  await page.getByLabel("In Kontakten suchen").fill("");

  // stornieren mit Grund (Pflicht)
  await liste.getByTestId("kontakt").filter({ hasText: "Lieferung" }).getByRole("button", { name: /stornieren/ }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Stornieren" }).click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  await dialog.getByLabel("Grund").fill("falscher Patient");
  await dialog.getByRole("button", { name: "Stornieren" }).click();
  await expect(dialog).toHaveCount(0);
  const storniert = liste.getByTestId("kontakt").filter({ hasText: "Lieferung" });
  await expect(storniert).toContainText("Grund: falscher Patient");
  await expect(storniert.getByRole("button", { name: /stornieren/ })).toHaveCount(0);

  // Wiedervorlage steht in der Akte und im Backend; Kontakte nach Neustart unverändert
  stackNeuStarten();
  await oeffnen(page, p.id);
  await expect(page.getByTestId("aktentermine")).toContainText("Rückruf");
  const api = await apiAls("mitarbeiter");
  const kontakte = await api.get(`kontakte/?patient=${p.id}`);
  expect(kontakte.results.map((k: { storno_grund: string }) => k.storno_grund)).toEqual(["falscher Patient", ""]);
  const termine = await api.get(`termine/?patient=${p.id}&offen=true`);
  expect(termine.results[0].art).toBe("rueckruf");
  expect(termine.results[0].uhrzeit).toBe("10:00:00");

  // Termin ändern (F29): Titel und Uhrzeit
  await page.getByTestId("aktentermine").getByRole("button", { name: "Rückruf" }).click();
  const td = page.getByRole("dialog");
  await expect(td.getByRole("heading", { name: "Termin ändern" })).toBeVisible();
  await td.getByLabel("Titel").fill("Rückruf Trinkmenge");
  await td.getByLabel("Uhrzeit").fill("11:15");
  await td.getByRole("button", { name: "Termin speichern" }).click();
  await expect(page.getByText("Termin geändert.")).toBeVisible();
  await expect(page.getByTestId("aktentermine")).toContainText("Rückruf Trinkmenge");
  const geaendert = await api.get(`termine/${termine.results[0].id}/`);
  expect([geaendert.titel, geaendert.uhrzeit]).toEqual(["Rückruf Trinkmenge", "11:15:00"]);
  await api.ende();
  merken("kontakte", { id: p.id });
});

test("Stammdaten bearbeiten, Akte abschließen (Mediziner) und wieder öffnen (Admin)", async ({ browser, page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id);
  await page.getByTestId("kennzahlen").getByRole("button", { name: /nicht erfasst/ }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Telefon").fill("0251 98765");
  await dialog.getByRole("radio", { name: "nein" }).check();
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Stammdaten gespeichert.")).toBeVisible();
  await expect(page.getByTestId("stammdaten")).toContainText("0251 98765");
  await expect(page.getByTestId("kennzahlen")).not.toContainText("nicht erfasst");

  // Mitarbeiter darf nicht abschließen
  await page.getByRole("button", { name: "Weitere Aktionen" }).click();
  await expect(page.getByRole("menuitem", { name: "Akte abschließen" })).toHaveCount(0);
  await expect(page.getByRole("menuitem", { name: /Akte als PDF/ })).toHaveAttribute("aria-disabled", "true");
  await page.keyboard.press("Escape");

  const med = await browser.newContext({ storageState: zustand("mediziner"), ignoreHTTPSErrors: true });
  const mp = await med.newPage();
  await oeffnen(mp, p.id);
  await mp.getByRole("button", { name: "Weitere Aktionen" }).click();
  await mp.getByRole("menuitem", { name: "Akte abschließen" }).click();
  const ad = mp.getByRole("dialog");
  await ad.getByRole("radio", { name: "Therapie beendet" }).check();
  await ad.getByLabel("Notiz").fill("Darmfunktion ausreichend");
  await ad.getByRole("button", { name: "Akte abschließen" }).click();
  await expect(mp.getByText(/Akte abgeschlossen am .* Therapie beendet/)).toBeVisible();
  await expect(mp.getByTestId("aktenkopf").getByRole("button", { name: "Kontakt" })).toHaveCount(0);
  await med.close();

  // Mitarbeiter: Akte nur lesbar, in der Liste unter „Abgeschlossen“
  await page.reload();
  await expect(page.getByTestId("gewichtskarte").getByLabel("Neues Gewicht")).toHaveCount(0);
  await page.goto(`/patienten?status=abgeschlossen&suche=${p.name.split(",")[0]}`);
  await expect(page.getByTestId("patientenliste")).toContainText("Therapie beendet");

  const adm = await browser.newContext({ storageState: zustand("admin"), ignoreHTTPSErrors: true });
  const ap = await adm.newPage();
  await oeffnen(ap, p.id);
  await ap.getByRole("button", { name: "Weitere Aktionen" }).click();
  await ap.getByRole("menuitem", { name: "Akte wieder öffnen" }).click();
  await ap.getByRole("dialog").getByLabel("Grund").fill("versehentlich abgeschlossen");
  await ap.getByRole("dialog").getByRole("button", { name: "Wieder öffnen" }).click();
  await expect(ap.getByText("Akte wieder geöffnet.")).toBeVisible();
  await adm.close();

  const api = await apiAls("mitarbeiter");
  const akte = await api.get(`patienten/${p.id}/`);
  expect([akte.ist_abgeschlossen, akte.telefon, akte.nickelallergie]).toEqual([false, "0251 98765", "nein"]);
  await api.ende();
  merken("abschluss", { id: p.id });
});
