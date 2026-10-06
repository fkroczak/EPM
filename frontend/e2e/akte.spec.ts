/** Entwürfe 4, 5, 6 · Patientenakte: Kopf, Übersicht mit Gewicht, Diagnosen, Therapie, Kontakte, Abschluss. */
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
  // jeder Bereich ein eigener Reiter (F121)
  for (const r of ["Übersicht", "Diagnosen", "Therapie", "Kontakte", "Infusionspläne", "Labor", "BIA", "Berichte",
    "Dokumente", "Verlauf"]) {
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

  // Diagramm: echte Zeitabstände (vor 400, 95, 10 Tagen, heute) und Glättung umschaltbar
  const diagramm = page.getByTestId("gewichtsdiagramm");
  const xs = (await diagramm.locator("circle:not([r='6'])").evaluateAll((k) => k.map((c) => Number(c.getAttribute("cx")))))
    .sort((a, b) => a - b);
  expect(xs).toHaveLength(4);
  expect((xs[1] - xs[0]) / (xs[2] - xs[1])).toBeCloseTo(305 / 85, 1);
  expect(await diagramm.locator("path").first().getAttribute("d")).toContain("C");
  await karte.getByLabel("Geglättet").uncheck();
  expect(await diagramm.locator("path").first().getAttribute("d")).not.toContain("C");

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
  // eigene Reiter seit F121: der Freitext „Diagnose“ unter „Diagnosen“, die Therapie unter „Therapie“
  await oeffnen(page, p.id, "/diagnosen");
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
  await oeffnen(page, p.id, "/therapie");
  await expect(page.getByTestId("zuletzt-therapie")).toContainText("noch nicht bearbeitet");
  const therapie = page.getByTestId("karte-therapie");
  await therapie.getByRole("textbox", { name: "Therapie" }).click();
  await therapie.getByRole("button", { name: "Aufzählung" }).click();
  await page.keyboard.type("HPE 5×/Woche über Port");
  await therapie.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Therapie gespeichert.")).toBeVisible();

  // Bemerkung (Klärung U5 vom 03.10.2026): eigene Karte mit Versionen
  const bemerkung = page.getByTestId("karte-bemerkung");
  await expect(bemerkung).toContainText("Noch keine Bemerkung eingetragen.");
  await bemerkung.getByRole("button", { name: "Bearbeiten" }).click();
  await bemerkung.getByRole("textbox", { name: "Bemerkung" }).fill("Port seit 2019, Allergie auf Pflaster");
  await bemerkung.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Bemerkung gespeichert.")).toBeVisible();
  await expect(bemerkung.getByTestId("version-bemerkung")).toContainText("Version 1");
  await page.goto(`/patienten/${p.id}/verlauf`);
  await page.getByRole("group", { name: "Bereich" }).getByRole("button", { name: "Bemerkung", exact: true }).click();
  await expect(page.getByTestId("verlauf").getByRole("row").filter({ hasText: "Port seit 2019" })).toContainText("Bemerkung");

  // nach Neuladen aus der Datenbank, Übersicht zeigt beides
  await oeffnen(page, p.id);
  await expect(page.locator(".richtext li").filter({ hasText: "HPE 5×/Woche über Port" })).toBeVisible();
  const api = await apiAls("mitarbeiter");
  const akte = await api.get(`patienten/${p.id}/`);
  expect(akte.diagnose).toBe("<p>Kurzdarmsyndrom nach Resektion</p><p><strong>Typ II</strong></p>");
  expect(akte.therapie).toBe("<ul><li><p>HPE 5×/Woche über Port</p></li></ul>");
  expect(akte.bemerkung).toBe("<p>Port seit 2019, Allergie auf Pflaster</p>");
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
  // Kontaktart (Klärung U6 vom 03.10.2026)
  await neu.getByLabel("Kontaktart").selectOption({ label: "Telefon (angerufen)" });
  await neu.getByLabel("Wiedervorlage").check();
  await neu.getByLabel("Art", { exact: true }).selectOption({ label: "Rückruf" });
  await neu.getByLabel("Uhrzeit").fill("10:00");
  await neu.getByRole("button", { name: "Kontakt speichern" }).click();
  await expect(page.getByText("Kontakt und Wiedervorlage gespeichert.")).toBeVisible();
  const liste = page.getByTestId("kontaktliste");
  const erster = liste.getByTestId("kontakt").first();
  await expect(erster).toContainText("Appetit schlechter");
  await expect(erster).toContainText("Rückruf");
  await expect(erster).toContainText("S. Mitarbeit");
  await expect(erster.getByTestId("kontaktart")).toHaveText("Telefon (angerufen)");

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

  // Praxistermin mit Terminort aus der pflegbaren Liste
  await page.getByTestId("aktenkopf").getByRole("button", { name: "Termin" }).click();
  const pt = page.getByRole("dialog");
  await pt.getByLabel("Art", { exact: true }).selectOption("praxistermin");
  await pt.getByLabel("Ort").selectOption({ label: "Praxis Dr. Holtmeier" });
  await pt.getByLabel("Titel").fill("Kontrolle in der Praxis");
  await pt.getByRole("button", { name: "Termin speichern" }).click();
  await expect(page.getByText("Termin angelegt.")).toBeVisible();
  await expect(page.getByTestId("aktentermine")).toContainText("Kontrolle in der Praxis");
  const praxis = (await api.get(`termine/?patient=${p.id}&offen=true`)).results.find((t: { titel: string }) => t.titel === "Kontrolle in der Praxis");
  expect([praxis.art, praxis.ort_name]).toEqual(["praxistermin", "Praxis Dr. Holtmeier"]);
  await api.ende();
  merken("kontakte", { id: p.id });
});

test("Stammdaten bearbeiten, Akte abschließen (Mitarbeiter) und wieder öffnen (Admin)", async ({ browser, page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id);
  await page.getByTestId("kennzahlen").getByRole("button", { name: /nicht erfasst/ }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Telefon", { exact: true }).fill("0251 98765");
  // Telefon 2 und Versicherung sichtbar (Klärung U5; seit 06.10.2026 heißt „Krankenkasse“ „Versicherung“, F118)
  await dialog.getByLabel("Telefon 2").fill("0171 2223334");
  await dialog.getByLabel("Versicherung", { exact: true }).fill("AOK NordWest");
  // Nickelallergie als Auswahlliste; Katheter und Versorger bewusst „kein“ (Festlegung 01.10.2026)
  await dialog.getByLabel("Nickelallergie").selectOption("nein");
  await dialog.getByLabel("Katheter").selectOption({ label: "kein Katheter" });
  await dialog.getByLabel("Versorger", { exact: true }).selectOption({ label: "kein Versorger" });
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Stammdaten gespeichert.")).toBeVisible();
  await expect(page.getByTestId("stammdaten")).toContainText("0251 98765");
  await expect(page.getByTestId("stammdaten").getByTestId("telefon2")).toHaveText("0171 2223334");
  await expect(page.getByTestId("stammdaten").getByTestId("krankenkasse")).toHaveText("AOK NordWest");
  const kennzahlen = page.getByTestId("kennzahlen");
  await expect(kennzahlen).not.toContainText("nicht erfasst");
  await expect(kennzahlen.locator("div").filter({ hasText: /^Katheter/ })).toContainText("kein");
  await expect(kennzahlen.locator("div").filter({ hasText: /^Versorger/ })).toContainText("kein");

  // Betrachter darf nicht abschließen
  const bet = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const bp = await bet.newPage();
  await oeffnen(bp, p.id);
  await bp.getByRole("button", { name: "Weitere Aktionen" }).click();
  await expect(bp.getByRole("menuitem", { name: "Akte abschließen" })).toHaveCount(0);
  // Akte als PDF (F23): Lesen genügt
  await bp.getByRole("menuitem", { name: "Akte als PDF" }).click();
  await expect(bp.getByTestId("pdf-dialog").getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await bet.close();

  // Mitarbeiter schließt ab (Festlegung 01.10.2026: Mitarbeiter, Mediziner und Admin)
  await page.getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: "Akte abschließen" }).click();
  const ad = page.getByRole("dialog");
  await ad.getByRole("radio", { name: "Therapie beendet" }).check();
  await ad.getByLabel("Notiz").fill("Darmfunktion ausreichend");
  await ad.getByRole("button", { name: "Akte abschließen" }).click();
  await expect(page.getByText(/Akte abgeschlossen am .* Therapie beendet/)).toBeVisible();
  await expect(page.getByTestId("aktenkopf").getByRole("button", { name: "Kontakt" })).toHaveCount(0);

  // danach nur lesbar, in der Liste unter „Abgeschlossen“
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
  // echte Akte: für den Admin weiter nur lesbar
  await expect(ap.getByTestId("aktenkopf").getByRole("button", { name: "Kontakt" })).toHaveCount(0);
  await adm.close();

  const api = await apiAls("mitarbeiter");
  const akte = await api.get(`patienten/${p.id}/`);
  expect([akte.ist_abgeschlossen, akte.telefon, akte.nickelallergie]).toEqual([false, "0251 98765", "nein"]);
  expect([akte.kein_katheter, akte.kein_versorger, akte.katheter, akte.versorger]).toEqual([true, true, null, null]);
  await api.ende();
  merken("abschluss", { id: p.id });
});

test("Ärzte aus der gemeinsamen Liste zuordnen, Bezugspersonen mit Auskunft pflegen", async ({ page }) => {
  const p = await neuerPatient();
  // Arzt einmal in der Ärzteliste anlegen
  const arztName = eindeutig("Dr. med. Erik Eintrag");
  await page.goto("/aerzte");
  await page.getByRole("button", { name: "Neuer Arzt" }).click();
  const detail = page.getByTestId("arzt-detail");
  // erst wenn das leere Formular „Neuer Arzt“ steht: vorher zeigt die Seite noch den ersten Arzt der Liste, und eine
  // sofort getippte Eingabe ginge beim Umschalten verloren (sporadischer Fehlschlag in CI, Lauf 36945132489)
  await expect(detail.getByRole("heading", { name: "Neuer Arzt" })).toBeVisible();
  await expect(detail.getByLabel("Name")).toHaveValue("");
  await detail.getByLabel("Name").fill(arztName);
  await detail.getByLabel("Praxis / Klinik").fill("Praxis Eintrag");
  await detail.getByLabel("Fachrichtung").fill("Allgemeinmedizin");
  await detail.getByLabel("Ort").fill("Münster");
  await detail.getByLabel("Telefon").fill("0251 12345");
  await detail.getByRole("button", { name: "Arzt anlegen" }).click();
  await expect(page.getByText("Arzt angelegt.")).toBeVisible();

  // in der Akte als Hausarzt zuordnen → Kopf zeigt Name und Telefon
  await oeffnen(page, p.id);
  const aerzte = page.getByTestId("aerzte");
  await aerzte.getByRole("button", { name: "Arzt", exact: true }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Arzt").selectOption({ label: `${arztName} · Allgemeinmedizin (Münster)` });
  await dialog.getByLabel("Rolle").selectOption("hausarzt");
  await dialog.getByRole("button", { name: "Zuordnen" }).click();
  await expect(page.getByText("Arzt zugeordnet.")).toBeVisible();
  await expect(aerzte.getByTestId("arzt-zuordnung")).toContainText(arztName);
  await expect(aerzte.getByTestId("arzt-zuordnung")).toContainText("0251 12345");
  const kopf = page.getByTestId("kennzahlen");
  await expect(kopf.locator("div").filter({ hasText: /^Hausarzt/ })).toContainText(arztName);

  // Telefonnummer in der Ärzteliste ändern → gilt in der Akte
  await page.goto("/aerzte");
  await page.getByLabel("Ärzte filtern").fill(arztName);
  await page.getByTestId("aerzteliste").getByRole("button", { name: arztName }).click();
  await page.getByTestId("arzt-detail").getByLabel("Telefon").fill("0251 99999");
  await page.getByTestId("arzt-detail").getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Arzt gespeichert.")).toBeVisible();
  await expect(page.getByTestId("arzt-patienten")).toContainText(p.name);
  await oeffnen(page, p.id);
  await expect(page.getByTestId("aerzte")).toContainText("0251 99999");

  // Bezugspersonen: zwei Personen, eine mit Schweigepflichtentbindung → „Auskunft an“ im Kopf
  const personen = page.getByTestId("bezugspersonen");
  // Höhe des Kopfs ohne Bezugspersonen merken: mit Personen bleibt sie gleich (festes Raster)
  const kopfHoehe = (await page.getByTestId("kennzahlen").boundingBox())!.height;
  await personen.getByRole("button", { name: "Person", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Beziehung").selectOption({ label: "Mutter" });
  await dialog.getByLabel("Name").fill("Margit Akte");
  await dialog.getByLabel("Telefon").fill("0251 55555");
  await dialog.getByRole("checkbox", { name: /Auskunft erlaubt/ }).check();
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Bezugsperson angelegt.").last()).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await personen.getByRole("button", { name: "Person", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Beziehung").selectOption({ label: "Betreuer/in (gesetzlich)" });
  await dialog.getByLabel("Name").fill("Bernd Betreuer");
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Bezugsperson angelegt.").last()).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(personen.getByTestId("bezugsperson")).toHaveCount(2);
  await expect(page.getByTestId("auskunft")).toContainText("Margit Akte (Mutter)");
  await expect(page.getByTestId("auskunft")).not.toContainText("Bernd Betreuer");
  // „Auskunft an“ im Kopf führt zu den Kontaktdaten der Person; der Kopf behält seine Höhe
  await page.getByTestId("auskunft").getByRole("button", { name: "Margit Akte (Mutter)" }).click();
  await expect(personen.getByTestId("bezugsperson").filter({ hasText: "Margit Akte" })).toHaveAttribute("aria-current", "true");
  expect((await page.getByTestId("kennzahlen").boundingBox())!.height).toBeCloseTo(kopfHoehe, 0);

  // nicht löschen, sondern „nicht mehr aktuell“ – bleibt unter „Frühere anzeigen“ und im Verlauf
  await personen.getByRole("button", { name: "Margit Akte" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Nicht mehr aktuell" }).click();
  await expect(page.getByText("Als nicht mehr aktuell markiert.")).toBeVisible();
  await expect(page.getByTestId("auskunft")).toContainText("niemand eingetragen");
  await expect(personen.getByTestId("bezugsperson")).toHaveCount(1);
  await personen.getByRole("button", { name: /Frühere anzeigen/ }).click();
  await expect(personen.getByTestId("bezugsperson")).toHaveCount(2);
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Verlauf" }).click();
  const bereich = page.getByRole("group", { name: "Bereich" });
  const verlauf = page.getByTestId("verlauf");
  await bereich.getByRole("button", { name: "Ärzte", exact: true }).click();
  await expect(bereich.getByRole("button", { name: "Ärzte", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(verlauf.getByRole("row").filter({ hasText: arztName })).toContainText("angelegt");
  await expect(verlauf.getByRole("row").filter({ hasText: "Bezugsperson" })).toHaveCount(0);
  await bereich.getByRole("button", { name: "Bezugspersonen", exact: true }).click();
  await expect(verlauf.getByRole("row").filter({ hasText: "nicht mehr aktuell" })).toContainText("Margit Akte");

  // in der Datenbank
  const api = await apiAls("mitarbeiter");
  const bps = await api.get(`bezugspersonen/?patient=${p.id}`);
  expect(bps.map((b: { name: string; aktiv: boolean; auskunft_erlaubt: boolean }) => [b.name, b.aktiv, b.auskunft_erlaubt]).sort())
    .toEqual([["Bernd Betreuer", true, false], ["Margit Akte", false, true]]);
  await api.ende();
  merken("kontaktdaten", { patient: p.id, arzt: arztName });
});
