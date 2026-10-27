/** Entwurf 3 · Patientenliste und Entwurf 12 · Neuer Patient – gegen echtes Backend und PostgreSQL. */
import { expect, test } from "@playwright/test";
import { apiAls, eindeutig, kontrast, merken, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

test("Patientenliste: Filter, Schnellfilter, Sortierung, abgeschlossene Akten", async ({ page }) => {
  const adressen: string[] = [];
  page.on("framenavigated", (f) => { if (f === page.mainFrame()) adressen.push(f.url().replace(/^https:\/\/[^/]+/, "")); });
  await page.goto("/");
  await page.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Patienten" }).click();
  await expect(page.getByRole("heading", { name: "Patienten", level: 1 })).toBeVisible();
  // „Neuer Patient“ ist ein Link mit Knopf-Stil: Schrift muss sich vom Akzent abheben (vorher blau auf blau)
  expect(await kontrast(page.getByRole("link", { name: "Neuer Patient" }))).toBeGreaterThan(4.5);
  const liste = page.getByTestId("patientenliste");
  const zeile = (name: string) => liste.getByRole("row").filter({ has: page.getByRole("link", { name }) });

  // Musterdaten: fünf Testpatienten in Betreuung, Max Mustermann mit Gewichtsverlust, Paula Beispiel mit Nickelallergie
  await expect(zeile("Mustermann, Max")).toBeVisible();
  await expect(zeile("Mustermann, Max").getByText("Testpatient")).toBeVisible();
  await expect(zeile("Mustermann, Max").getByText(/Gewicht −\d+,\d % in \d+ Mon\./)).toBeVisible();
  await expect(zeile("Mustermann, Max").getByLabel(/Trend fallend/)).toBeVisible();
  await expect(zeile("Beispiel, Paula").getByText("Nickelallergie")).toBeVisible();
  // Testpatienten zählen in keiner Statistik: Kopfzahl = echte Patienten in Betreuung
  const zaehlung = await apiAls("mitarbeiter");
  const echte = (await zaehlung.get("patienten/?status=in_betreuung&test=ohne&seitengroesse=1")).count;
  await zaehlung.ende();
  await expect(page.getByTestId("zahl-in-betreuung")).toContainText(`${echte} Patienten in Betreuung`);
  // Die Zahl der Testpatienten sieht nur die Administration (Festlegung 01.10.2026)
  await expect(page.getByTestId("zahl-in-betreuung")).not.toContainText("Testpatienten");
  await expect(page.getByRole("group", { name: "Ansicht" }).getByRole("button", { name: /In Betreuung/ })).not.toContainText("Test");
  await expect(liste.getByRole("link", { name: "Demo, Karl" })).toHaveCount(0);

  // Freitext (Feld oben in der Kopfzeile)
  await page.getByLabel("Liste filtern").fill("Muster");
  await expect(liste.getByRole("link", { name: "Musterfrau, Erika" })).toBeVisible();
  await expect(liste.getByRole("link", { name: "Probe, Jonas" })).toHaveCount(0);
  await expect(page).toHaveURL(/suche=Muster/);
  // ein Suchfeld: das Feld oben in der Kopfzeile filtert hier die Liste (08.10.2026); der Begriff steht als Chip im Filter
  await expect(page.getByTestId("suchbegriff")).toContainText("Muster");
  await page.getByRole("button", { name: "Filter zurücksetzen" }).click();
  await expect(liste.getByRole("link", { name: "Probe, Jonas" })).toBeVisible();
  await expect(page.getByLabel("Liste filtern")).toHaveValue("");
  // Prüffilter direkt wählbar
  await page.getByLabel("Prüfen").selectOption({ label: "Nickelallergie nicht erfasst" });
  await expect(page).toHaveURL(/pruefen=nickelallergie/);
  await page.getByLabel("Prüfen").selectOption("");
  await expect(page).not.toHaveURL(/pruefen=/);

  // Versorger und Ansprechpartner
  // „exact“, weil das „×“ an den Hinweisen „Versorger nicht erfasst“ ebenfalls auf Versorger lautet (F119)
  await page.getByLabel("Versorger", { exact: true }).selectOption({ label: "Testversorger Süd (fiktiv)" });
  await expect(page).toHaveURL(/versorger=\d+/);
  await expect(liste.getByRole("link", { name: "Probe, Jonas" })).toBeVisible();
  await expect(liste.getByRole("link", { name: "Musterfrau, Erika" })).toHaveCount(0);
  await page.getByLabel("Versorger", { exact: true }).selectOption({ label: "Alle Versorger" });
  await expect(page).not.toHaveURL(/versorger=/);
  const gefiltert = page.waitForResponse((a) => /\/api\/patienten\/\?.*ansprechpartner=\d+/.test(a.url()));
  await page.getByLabel("Ansprechpartner").selectOption({ label: "Herr Muster (Testversorger Nord (fiktiv))" });
  await expect(page).toHaveURL(/ansprechpartner=\d+/);
  // Antwort, die die Oberfläche erhält (trennt Backend- von Anzeigefehlern)
  const antwort = await gefiltert;
  expect(antwort.status()).toBe(200);
  expect((await antwort.json()).results.map((p: { nachname: string }) => p.nachname), antwort.url()).toEqual(["Mustermann"]);
  // gleiche Abfrage direkt an die API: nur Patienten dieses Ansprechpartners
  const apId = new URL(page.url()).searchParams.get("ansprechpartner");
  const api = await apiAls("mitarbeiter");
  const direkt = await api.get(`patienten/?status=in_betreuung&ansprechpartner=${apId}`);
  expect(direkt.results.map((p: { nachname: string; ansprechpartner_name: string }) => `${p.nachname}/${p.ansprechpartner_name}`)).toEqual(["Mustermann/Herr Muster"]);
  await api.ende();
  await expect(liste.getByRole("link", { name: "Mustermann, Max" })).toBeVisible();
  await expect(page, `Adressen seit dem Laden: ${adressen.join(" → ")}`).toHaveURL(/ansprechpartner=\d+/);
  await expect(page.getByLabel("Ansprechpartner")).toHaveValue(apId ?? "");
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
  // die Liste wird nachgeladen (bis dahin bleibt die alte Reihenfolge stehen)
  await expect.poll(async () => {
    const namen = await liste.locator("tbody tr td:nth-child(2) a").allTextContents();
    return namen.length > 1 && namen.join("|") === [...namen].sort((a, b) => a.localeCompare(b, "de")).join("|");
  }).toBe(true);

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

  // Versorger und Arzt direkt aus dem Formular neu anlegen – im Dialog, die Seite bleibt (08.10.2026)
  const versorgerName = eindeutig("Versorger E2E");
  await page.getByRole("button", { name: "Neu anlegen: Versorger" }).click();
  const vd = page.getByRole("dialog");
  await expect(vd.getByRole("heading", { name: "Neuer Versorger" })).toBeVisible();
  await vd.getByRole("button", { name: "Anlegen" }).click();
  await expect(vd.getByText("Bitte einen Namen eingeben.")).toBeVisible();
  await vd.getByRole("textbox", { name: /^Name\s*\*?$/ }).fill(versorgerName);
  await vd.getByLabel("Ort").fill("Münster");
  await vd.getByRole("button", { name: "Anlegen" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByLabel("Versorger", { exact: true }).locator("option:checked")).toHaveText(versorgerName);
  await expect(page.getByRole("heading", { name: "Neuer Patient" })).toBeVisible();
  const arztName = eindeutig("Dr. E2E");
  await page.getByRole("button", { name: "Neu anlegen: Arzt" }).click();
  await page.getByRole("dialog").getByRole("textbox", { name: /^Name\s*\*?$/ }).fill(arztName);
  await page.getByRole("dialog").getByRole("button", { name: "Anlegen" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByLabel("Hausarzt").locator("option:checked")).toHaveText(arztName);
  await expect(page).toHaveURL(/\/patienten\/neu$/);

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
  await page.getByLabel("Hausarzt").selectOption({ label: "Dr. med. Anna Hausmann (fiktiv) (Altenberge)" });
  await page.getByLabel("Diagnose").fill("Kurzdarmsyndrom (E2E)");
  await page.getByLabel("Überweisung / Kontaktaufnahme durch").fill("Praxis Dr. Holtmeier");
  // Bezugsperson gleich beim Anlegen (27.10.2026) statt als „Telefon 2“
  const personen = page.getByTestId("neu-bezugspersonen");
  await personen.getByLabel("Beziehung").selectOption({ label: "Ehepartner/in" });
  await personen.getByLabel("Mobil Bezugsperson").fill("0000 777777");
  await page.getByRole("button", { name: "Anlegen und Akte öffnen" }).click();
  await expect(personen.getByText("Bitte einen Namen eingeben.")).toBeVisible();
  await personen.getByLabel("Name").fill("Sonja Beispiel");
  await personen.getByRole("checkbox", { name: /Auskunft erlaubt/ }).check();
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
  // Hausarzt aus der Ärzteliste als Zuordnung gespeichert, mit Kontaktdaten im Kopf
  expect(p.kopf.hausarzt.name).toBe("Dr. med. Anna Hausmann (fiktiv)");
  expect(p.kopf.hausarzt.telefon).toBe("0000 111111");
  expect(p.diagnose).toContain("Kurzdarmsyndrom (E2E)");
  expect(p.ueberweisung_durch).toBe("Praxis Dr. Holtmeier");
  const gewichte = await api.get(`gewichte/?patient=${id}`);
  expect(gewichte.results.map((g: { gewicht_kg: number }) => g.gewicht_kg)).toEqual([61.4]);
  const bp = await api.get(`bezugspersonen/?patient=${id}`);
  expect(bp.map((b: { beziehung_name: string; name: string; mobil: string; auskunft_erlaubt: boolean }) =>
    [b.beziehung_name, b.name, b.mobil, b.auskunft_erlaubt])).toEqual([["Ehepartner/in", "Sonja Beispiel", "0000 777777", true]]);
  await api.ende();

  // erscheint in der Liste
  await page.goto(`/patienten?suche=${nachname}`);
  await expect(page.getByTestId("patientenliste").getByRole("link", { name: `${nachname}, Nele` })).toBeVisible();
  merken("neuer_patient", { id, nachname, name: `${nachname}, Nele` });
});

test("Neuer Patient als Testpatient (z. B. für Plantests): eigene Nummer ab 9001", async ({ page }) => {
  await page.goto("/patienten/neu");
  const nr = page.getByTestId("naechste-nummer");
  await expect(nr).toHaveText(/^\d{4}$/);
  const echt = Number(await nr.textContent());
  await page.getByRole("checkbox", { name: "als Testpatient anlegen" }).check();
  await expect(page.getByText("wird Testpatient")).toBeVisible();
  await expect.poll(async () => Number(await nr.textContent())).toBeGreaterThanOrEqual(9001);
  expect(echt).toBeLessThan(9001);
  const nachname = eindeutig("Plantest");
  await page.getByLabel("Nachname").fill(nachname);
  await page.getByLabel("Vorname").fill("Paul");
  await page.getByLabel("Geburtsdatum").fill("04.04.1974");
  await page.getByRole("button", { name: "Anlegen und Akte öffnen" }).click();
  await expect(page).toHaveURL(/\/patienten\/\d+$/);
  await expect(page.getByTestId("aktenkopf").getByText("Testpatient")).toBeVisible();
  const api = await apiAls("mitarbeiter");
  const p = await api.get(`patienten/${page.url().split("/").pop()}/`);
  expect([p.ist_test, p.nummer >= 9001]).toEqual([true, true]);
  await api.ende();
});

test("Betrachter sieht die Liste, aber keinen Knopf „Neuer Patient“", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/patienten");
  await expect(page.getByTestId("patientenliste").getByRole("link", { name: "Mustermann, Max" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Neuer Patient" })).toHaveCount(0);
  // ohne Recht gibt es die Seite nicht: zurück zur Liste, ohne Hinweis auf Rechte
  await page.goto("/patienten/neu");
  await expect(page).toHaveURL(/\/patienten$/);
  await expect(page.getByText(/darf nur|fehlt das Recht/)).toHaveCount(0);
  await ctx.close();
});

test("Testzugang: Hinweis dauerhaft sichtbar, nur Testpatienten, neue Patienten werden Testpatienten", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: zustand("test"), ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto("/");
  await expect(page.getByTestId("testzugang")).toBeVisible();
  await page.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Patienten" }).click();
  await expect(page.getByTestId("testzugang")).toBeVisible();
  const liste = page.getByTestId("patientenliste");
  await expect(liste.getByRole("link", { name: "Mustermann, Max" })).toBeVisible();
  // jede Zeile ist ein Testpatient – echte Patienten sind für den Testzugang unsichtbar
  await expect(liste.locator("tbody tr").filter({ hasNotText: "Testpatient" })).toHaveCount(0);
  await page.goto("/patienten/neu");
  await expect(page.getByText("wird Testpatient")).toBeVisible();
  await expect(page.getByTestId("naechste-nummer")).toHaveText(/^9\d{3}$/);
  await ctx.close();
});

test("Suche in der Kopfzeile (Strg K) nach Name, Nummer und Geburtsdatum", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  const max = (await api.get("patienten/?suche=Mustermann")).results.find((p: { vorname: string }) => p.vorname === "Max");
  await api.ende();
  const [jahr, monat, tag] = max.geburtsdatum.split("-");
  await page.goto("/");
  await expect(page.getByTestId("angemeldet-als")).toBeVisible(); // Kopfzeile geladen, Tastenkürzel aktiv
  await page.keyboard.press("Control+k");
  const suche = page.getByRole("combobox", { name: "Suchen" });
  await expect(suche).toBeFocused();
  for (const begriff of ["Mustermann", String(max.nummer).padStart(4, "0"), `${tag}.${monat}.${jahr}`]) {
    await suche.fill(begriff);
    await expect(page.getByRole("option", { name: /Mustermann, Max/ }), begriff).toBeVisible();
  }
  await page.getByRole("option", { name: /Mustermann, Max/ }).click();
  await expect(page.getByTestId("aktenkopf").getByRole("heading", { name: "Mustermann, Max" })).toBeVisible();
});
