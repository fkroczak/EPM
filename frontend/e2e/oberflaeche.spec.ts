/**
 * Startseite und Oberfläche (S02, S05, S12–S17): Schnellerfassung, Meine Akten, Hilfe, Startseite der Administration,
 * volle Breite in Stufen bei 1280, 1920 und 2560 px, Spaltenteiler mit Einrastpunkten.
 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

async function neuerPatient(praefix: string) {
  const api = await apiAls("mitarbeiter");
  const nachname = eindeutig(praefix);
  const p = await api.post("patienten/", { nachname, vorname: "Selma", geburtsdatum: "1961-05-12", geschlecht: "w", groesse_cm: "168" });
  await api.post("gewichte/", { patient: p.id, gewicht_kg: "60.0", gemessen_am: new Date(Date.now() - 20 * 86_400_000).toISOString().slice(0, 10),
    quelle: "telefonisch" });
  await api.post("bezugspersonen/", { patient: p.id, name: "Hans Schnell", auskunft_erlaubt: true });
  await api.ende();
  return { id: p.id as number, nachname, name: `${nachname}, Selma` };
}

function gespeichert(page: Page, pfad = "auth/ich/") {
  return page.waitForResponse((a) => a.url().endsWith(`/api/${pfad}`) && a.request().method() !== "GET" && a.ok());
}

test("Schnellerfassung (S02): Kontakt mit Wiedervorlage; das Gewicht scheitert getrennt und wird nachgeholt", async ({ page }) => {
  const p = await neuerPatient("Schnell");
  await page.goto("/");
  await page.getByRole("button", { name: "Kontakt erfassen" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Patient").fill(p.nachname);
  await dialog.getByRole("option", { name: new RegExp(p.name) }).click();
  const kontext = dialog.getByTestId("kontextkasten");
  await expect(kontext).toContainText("60,0 kg");
  await expect(kontext.getByTestId("kontext-auskunft")).toContainText("Hans Schnell");
  await dialog.getByRole("textbox", { name: "Notiz" }).fill("Ehemann ruft an: Lieferung bestätigt.");
  await dialog.getByLabel("Gewicht mit erfassen").check();
  await dialog.getByLabel("Gewicht", { exact: true }).fill("590"); // unplausibel: das Backend weist es ab
  await expect(dialog.getByTestId("gewicht-veraenderung")).toContainText("gegenüber");
  await dialog.getByLabel("Wiedervorlage anlegen").check();
  await dialog.getByRole("group", { name: "Art" }).getByRole("button", { name: "Rückruf" }).click();
  await dialog.getByRole("button", { name: "in 1 Monat" }).click();
  await dialog.getByLabel("Titel").fill("E2E Schnell Rückruf");
  await dialog.getByRole("button", { name: "Speichern" }).click();
  // Kontakt (mit Wiedervorlage) ist gespeichert, das Gewicht nicht – das sagt der Dialog deutlich
  await expect(dialog.getByTestId("kontakt-gespeichert")).toContainText("Kontakt gespeichert");
  await expect(dialog.getByTestId("kontakt-gespeichert")).toContainText("Gewicht wurde nicht gespeichert");
  await expect(dialog.getByText(/Gewicht muss zwischen/)).toBeVisible();
  const api = await apiAls("mitarbeiter");
  const kontakte = await api.get(`kontakte/?patient=${p.id}`);
  expect(kontakte.count).toBe(1);
  expect(kontakte.results[0].termine.map((t: { art: string }) => t.art)).toEqual(["rueckruf"]);
  // nur das Gewicht korrigieren und nachholen – kein zweiter Kontakt
  await dialog.getByLabel("Gewicht", { exact: true }).fill("59,4");
  await dialog.getByRole("button", { name: "Gewicht speichern" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText(`Kontakt und Gewicht für ${p.name} gespeichert.`)).toBeVisible();
  expect((await api.get(`kontakte/?patient=${p.id}`)).count).toBe(1);
  const gewichte = await api.get(`gewichte/?patient=${p.id}`);
  expect(gewichte.results.map((g: { gewicht_kg: string }) => Number(g.gewicht_kg))).toContain(59.4);
  const termine = await api.get(`termine/?patient=${p.id}&offen=true`);
  expect(termine.results.map((t: { titel: string }) => t.titel)).toEqual(["E2E Schnell Rückruf"]);
  await api.ende();

  // Gewicht allein
  await page.getByRole("button", { name: "Gewicht", exact: true }).click();
  const g = page.getByRole("dialog");
  await g.getByLabel("Patient").fill(p.nachname);
  await g.getByRole("option", { name: new RegExp(p.name) }).click();
  await g.getByLabel("Gewicht", { exact: true }).fill("59,1");
  await g.getByRole("button", { name: "Gewicht speichern" }).click();
  await expect(g).toHaveCount(0);
  await expect(page.getByText(`Gewicht 59,1 kg für ${p.name} gespeichert.`)).toBeVisible();
});

test("Meine Akten (S05): Stern im Aktenkopf, Merkliste und zuletzt geöffnet auf der Startseite", async ({ page }) => {
  const p = await neuerPatient("Merk");
  await page.goto(`/patienten/${p.id}`);
  const stern = page.getByTestId("merken");
  await expect(stern).toHaveAttribute("aria-pressed", "false");
  const antwort = gespeichert(page, "meine-akten/merken/");
  await stern.click();
  await antwort;
  await expect(stern).toHaveAttribute("aria-pressed", "true");
  await page.goto("/");
  const kachel = page.getByTestId("meine-akten");
  await expect(kachel.getByRole("link", { name: new RegExp(p.nachname) })).toBeVisible();
  await page.getByRole("group", { name: "Auswahl" }).getByRole("button", { name: "Zuletzt geöffnet" }).click();
  await expect(kachel.getByRole("link", { name: new RegExp(p.nachname) })).toBeVisible();
  await page.getByRole("group", { name: "Auswahl" }).getByRole("button", { name: /Merkliste/ }).click();
  await kachel.getByRole("button", { name: `Von der Merkliste nehmen: ${p.name}` }).click();
  await expect(kachel.getByRole("link", { name: new RegExp(p.nachname) })).toHaveCount(0);
  // eine andere Person sieht die Merkliste nicht
  const andere = await apiAls("mediziner");
  expect((await andere.get("meine-akten/")).merkliste.map((a: { patient: number }) => a.patient)).not.toContain(p.id);
  await andere.ende();
});

test("Hilfe (S15): „?“ führt zum passenden Abschnitt, Suche, Ergänzung mit Historie", async ({ page }) => {
  await page.goto("/patienten");
  await page.getByTestId("hilfe-zur-seite").click();
  await expect(page).toHaveURL(/\/hilfe\?seite=%2Fpatienten/);
  await expect(page.getByTestId("hilfe-titel")).toHaveText("Patientenliste, Suche und Filter");
  await expect(page.getByTestId("hilfe-abschnitt")).toContainText("mitgeliefert");
  await page.getByLabel("In der Hilfe suchen").fill("Notfall-Codes");
  await page.getByTestId("hilfe-inhalt").getByRole("button", { name: /Notfall-Codes/ }).first().click();
  await expect(page.getByTestId("hilfe-titel")).toHaveText("Notfall-Codes");
  // Ergänzung der Stiftung (Recht „Vorlagen pflegen“), mit Historie
  await page.getByTestId("hilfe-inhalt").getByRole("button", { name: "Kontakt erfassen", exact: true }).click();
  const ergaenzung = page.getByTestId("hilfe-ergaenzung");
  const text = `Durchwahl Versorger ${eindeutig("E2E")}`;
  await ergaenzung.getByRole("button", { name: /Ergänzen|Bearbeiten/ }).click();
  await ergaenzung.getByRole("textbox", { name: "Ergänzung der Stiftung" }).fill(text);
  await ergaenzung.getByRole("button", { name: "Speichern" }).click();
  await expect(ergaenzung).toContainText(text);
  await ergaenzung.getByRole("button", { name: /Historie/ }).click();
  await expect(page.getByTestId("hilfe-historie")).toContainText(text);
  await page.getByRole("dialog").getByRole("button", { name: "Schließen" }).click();
  // Betrachter: keine Abschnitte zum Erfassen, keine Ergänzung schreiben, aber lesen
  const ctx = await page.context().browser()!.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const b = await ctx.newPage();
  await b.goto("/hilfe");
  await expect(b.getByTestId("hilfe-inhalt").getByRole("button", { name: "Patientenliste, Suche und Filter" })).toBeVisible();
  await expect(b.getByTestId("hilfe-inhalt").getByRole("button", { name: "Kontakt erfassen", exact: true })).toHaveCount(0);
  await expect(b.getByTestId("hilfe-inhalt").getByRole("button", { name: "Benutzer und Rechte" })).toHaveCount(0);
  await ctx.close();
});

test("Startseite der Administration (S12–S14): Kacheln nach Rechten, Update nur mit Passwort und 2FA", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("admin"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/");
  for (const titel of ["Datensicherung", "Server", "Ubuntu-Updates", "Konten", "Hinweis an alle", "Zugriffe · 7 Tage", "Testumgebung"]) {
    await expect(page.getByRole("heading", { name: titel, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: /^Angemeldet/ })).toBeVisible();
  // klinische Kacheln sind für die Rolle Admin standardmäßig ausgeblendet
  await expect(page.getByRole("heading", { name: "Wiedereinbestellung fällig" })).toHaveCount(0);
  await expect(page.getByText("Administration · echte Akten sind für dich nur lesbar")).toBeVisible();
  await expect(page.getByTestId("kachel-zugriffe").getByTestId("zugriffe-anmeldungen")).not.toHaveText("");
  await expect(page.getByTestId("kachel-angemeldet")).toContainText("Du");
  const updates = page.getByTestId("kachel-updates");
  const knopf = updates.getByRole("button", { name: /Updates installieren/ });
  if (await knopf.isEnabled()) {
    await knopf.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByLabel("Ihr Passwort")).toBeVisible();
    await expect(dialog.getByLabel("Code aus der Authenticator-App")).toBeVisible();
    await expect(dialog).toContainText("Vorher erstellt der Server automatisch eine Sicherung");
    await dialog.getByRole("button", { name: "Abbrechen" }).click();
  }
  // Zugriffe führen ins Audit-Log mit derselben Gruppe
  await page.getByTestId("kachel-zugriffe").getByRole("link", { name: /Fehlversuche/ }).click();
  await expect(page).toHaveURL(/\/admin\/audit-log\?gruppe=fehlversuch/);
  await expect(page.getByRole("button", { name: "Fehlversuch", exact: true })).toHaveAttribute("aria-pressed", "true");
  // eine klinische Kachel einblenden und wieder Standard
  await page.goto("/");
  await page.getByRole("button", { name: "Startseite anpassen" }).click();
  let antwort = gespeichert(page);
  await page.getByRole("button", { name: "Infusionspläne einblenden" }).click();
  await antwort;
  await expect(page.getByRole("heading", { name: "Infusionspläne", exact: true })).toBeVisible();
  antwort = gespeichert(page);
  await page.getByRole("button", { name: "Standard" }).click();
  await antwort;
  await expect(page.getByRole("heading", { name: "Infusionspläne", exact: true })).toHaveCount(0);
  await ctx.close();
});

test("Volle Breite in Stufen: 1280 px", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await expect(page.getByTestId("raster")).toHaveAttribute("data-spalten", "2"); // SU9: 2 Spalten unter 1440 px
  const main = (await page.locator("main").boundingBox())!;
  const leiste = (await page.locator("aside").first().boundingBox())!;
  expect(main.width).toBeGreaterThan(1280 - leiste.width - 2);
  await page.goto("/patienten");
  await expect(page.getByRole("columnheader", { name: /Nächster Termin/ })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: /Katheter/ })).toHaveCount(0);
  await page.getByTestId("patientenliste").getByRole("link", { name: "Probe, Jonas" }).click();
  await expect(page.getByTestId("uebersicht-stufe")).toBeVisible();
  await expect(page.locator(".teiler")).toHaveCount(0); // unter 1440 px untereinander, ohne Teiler
});

test("Volle Breite in Stufen: 1920 px – Karten der Akte im Raster, Größe je Karte über „⋯“, je Person gespeichert", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/");
  await expect(page.getByTestId("raster")).toHaveAttribute("data-spalten", "4");
  const main = (await page.locator("main").boundingBox())!;
  expect(main.width).toBeGreaterThan(1600); // keine Grenze bei 1440 px mehr
  await page.goto("/patienten");
  await expect(page.getByRole("columnheader", { name: /Erklärungen/ })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: /Plan/ })).toBeVisible();
  await page.getByTestId("patientenliste").getByRole("link", { name: "Probe, Jonas" }).click();
  // Übersicht: Raster wie auf der Startseite (4 Spalten bei 1920 px), kein senkrechter Teiler mehr
  const stufe = page.getByTestId("uebersicht-stufe");
  await expect(stufe).toHaveAttribute("data-spalten", "4");
  await expect(page.locator(".teiler")).toHaveCount(0);
  const gewicht = stufe.locator('[data-bereich="gewicht"]');
  await expect(gewicht).toHaveAttribute("data-breite", "2"); // Standard: Gewichtsverlauf doppelt breit
  await expect(stufe.locator("[data-bereich]")).toHaveCount(9); // seit F121 zusätzlich „Labor und BIA“
  const b0 = (await gewicht.boundingBox())!;
  // „⋯“: Breite 3 Spalten
  let antwort = gespeichert(page);
  await page.getByTestId("groesse-gewicht").click();
  await page.getByRole("menuitem", { name: /^Breite: 3 Spalten/ }).click();
  await antwort;
  await expect(gewicht).toHaveAttribute("data-breite", "3");
  await expect.poll(async () => (await gewicht.boundingBox())!.width).toBeGreaterThan(b0.width * 1.3);
  const api = await apiAls("mitarbeiter");
  expect((await api.get("auth/ich/")).bereiche.akte_uebersicht.gewicht).toEqual({ breite: 3, hoehe: 0 });
  // feste Höhe: 1 Zeile – der Inhalt scrollt in der Karte
  antwort = gespeichert(page);
  await page.getByTestId("groesse-gewicht").click();
  await page.getByRole("menuitem", { name: "Höhe: 1 Zeile" }).click();
  await antwort;
  await expect(gewicht).toHaveAttribute("data-hoehe", "1");
  // gespeichert je Person: nach dem Neuladen gleich
  await page.reload();
  await expect(page.getByTestId("uebersicht-stufe").locator('[data-bereich="gewicht"]')).toHaveAttribute("data-breite", "3");
  await expect(page.getByTestId("uebersicht-stufe").locator('[data-bereich="gewicht"]')).toHaveAttribute("data-hoehe", "1");
  // Karten überdecken sich nicht (nach dem Neuladen erst, wenn alle Karten ihre Daten haben und das Raster steht)
  await expect(async () => {
    const karten = await page.getByTestId("uebersicht-stufe").locator("[data-bereich]").evaluateAll((els) => els.map((e) => {
      const r = e.getBoundingClientRect();
      return { id: e.getAttribute("data-bereich"), l: r.left, r: r.right, o: r.top, u: r.bottom };
    }));
    for (const a of karten) for (const b of karten) {
      if (a.id! < b.id!) expect(a.r <= b.l + 1 || b.r <= a.l + 1 || a.u <= b.o + 1 || b.u <= a.o + 1, `${a.id} überdeckt ${b.id}`).toBe(true);
    }
  }).toPass({ timeout: 10_000 });
  // Standardgröße
  antwort = gespeichert(page);
  await page.getByTestId("groesse-gewicht").click();
  await page.getByRole("menuitem", { name: "Standardgröße" }).click();
  await antwort;
  await expect(page.getByTestId("uebersicht-stufe").locator('[data-bereich="gewicht"]')).toHaveAttribute("data-breite", "2");
  expect((await api.get("auth/ich/")).bereiche.akte_uebersicht?.gewicht).toBeUndefined();
  await api.ende();
  // Diagnosen, Therapie und Empfehlung haben seit F122 das feste Muster: links die Einträge, rechts der gewählte.
  // Das Raster mit „⋯“ gibt es dort nicht mehr – die Knöpfe stehen dafür auf jedem Reiter an derselben Stelle.
  const reiter = page.getByRole("navigation", { name: "Aktenbereiche" });
  await reiter.getByRole("link", { name: /^Diagnosen/ }).click();
  await expect(page.getByTestId("diagnosen")).toBeVisible();
  await expect(page.getByTestId("eintragsliste")).toBeVisible();
  await expect(page.getByTestId("karte-diagnose")).toBeVisible();
  await reiter.getByRole("link", { name: /^Therapie/ }).click();
  await expect(page.getByTestId("karte-therapie")).toBeVisible();
  // Kontakte: seit F122 dasselbe Muster wie überall – links die Kontakte, rechts der gewählte, ohne Teiler.
  // Der Verlauf der Akte steht nur im eigenen Reiter „Verlauf“ (Fehlerliste 02.10.2026, 3)
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Kontakte/ }).click();
  const kontakte = page.getByTestId("kontakte");
  await expect(kontakte.getByTestId("kontaktliste")).toBeVisible();
  await expect(kontakte.getByRole("heading", { name: /Verlauf/ })).toHaveCount(0);
  await expect(page.locator(".teiler")).toHaveCount(0);
  // Kalender: Monat ¾ | Tagesliste ¼, auch in der Woche
  await page.goto("/kalender?ansicht=woche");
  await expect(page.getByTestId("tagesliste")).toBeVisible();
});

test("Volle Breite in Stufen: 2560 px ohne Vorschau in der Patientenliste und drei Spalten im Plan-Editor", async ({ page: seite }) => {
  let page = seite;
  await page.setViewportSize({ width: 2560, height: 1440 });
  await page.goto("/");
  await expect(page.getByTestId("raster")).toHaveAttribute("data-spalten", "5");
  // Patientenliste ohne Vorschau der Akte (Wunsch 08.10.2026): Klick auf die Zeile öffnet die Akte
  await page.goto("/patienten");
  await expect(page.getByTestId("teiler-patientenliste-0")).toHaveCount(0);
  await expect(page.getByTestId("akten-vorschau")).toHaveCount(0);
  await page.getByTestId("patientenzeile").filter({ hasText: "Probe, Jonas" }).locator("td").first().click();
  await expect(page).toHaveURL(/\/patienten\/\d+/);
  await expect(page.getByTestId("aktenkopf")).toContainText("Probe, Jonas");
  // Plan-Editor (Recht „Infusionspläne anlegen“: Mediziner): Eingabe | Summen | PDF-Vorschau mit zwei Teilern
  const api = await apiAls("mediziner");
  const jonas = (await api.get("patienten/?suche=Probe")).results.find((x: { vorname: string }) => x.vorname === "Jonas");
  const entwuerfe = await api.get(`infusionsplaene/?patient=${jonas.id}&status=entwurf`);
  await api.ende();
  const ctx = await page.context().browser()!.newContext({ storageState: zustand("mediziner"), ignoreHTTPSErrors: true,
    viewport: { width: 2560, height: 1440 } });
  page = await ctx.newPage();
  if (entwuerfe.results.length) {
    await page.goto(`/patienten/${jonas.id}/plaene/${entwuerfe.results[0].id}/bearbeiten`);
    await expect(page.getByTestId("teiler-plan_editor-0")).toBeVisible();
    await expect(page.getByTestId("teiler-plan_editor-1")).toBeVisible();
    await expect(page.getByTestId("plan-pdf-vorschau")).toContainText("Stand der letzten Speicherung");
    await expect(page.getByTestId("plan-pdf-vorschau").getByTestId("pdf-leser")).toBeVisible();
  } else {
    await page.goto(`/patienten/${jonas.id}/plaene/neu`);
    await expect(page.getByTestId("teiler-plan_editor-1")).toBeVisible();
    await expect(page.getByTestId("plan-pdf-vorschau")).toContainText("sobald der Entwurf gespeichert ist");
  }
  await ctx.close();
});

test("Rückmeldung als Overlay: grün quittiert und blendet aus, rot bleibt länger und lässt sich schließen", async ({ page }) => {
  await page.goto("/patienten");
  await page.getByTestId("patientenliste").getByRole("link", { name: "Mustermann, Max" }).click();
  const stern = page.getByTestId("merken");
  const vorher = await stern.getAttribute("aria-pressed");
  await stern.click();
  const gruen = page.getByTestId("rueckmeldung").filter({ hasText: vorher === "true" ? "Von der Merkliste genommen." : "Auf die Merkliste gesetzt." });
  await expect(gruen).toBeVisible();
  await expect(gruen).toHaveAttribute("data-art", "ok");
  expect(await gruen.evaluate((e) => getComputedStyle(e).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)");
  // nach rund 3 Sekunden ausgeblendet
  await expect(gruen).toHaveCount(0, { timeout: 6000 });
  await stern.click(); // Merkliste wie vorher
  await expect(stern).toHaveAttribute("aria-pressed", vorher ?? "false");
  // Fehler: rot, nach 5 Sekunden noch da, „×“ schließt
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("epm:hinweis", { detail: "Testfehler aus dem Browsertest" })));
  const rot = page.getByTestId("rueckmeldung").filter({ hasText: "Testfehler aus dem Browsertest" });
  await expect(rot).toHaveAttribute("data-art", "fehler");
  await expect(rot).toHaveAttribute("role", "alert");
  await page.waitForTimeout(5000);
  await expect(rot).toBeVisible();
  await rot.getByRole("button", { name: "Meldung schließen" }).click();
  await expect(rot).toHaveCount(0);
});
