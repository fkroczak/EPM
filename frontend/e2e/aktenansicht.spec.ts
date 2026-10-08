/** Aufbau der Patientenakte je Person (Wunsch 08.10.2026): Kopfzeile in drei Höhen, Seitenleiste mit ziehbarer Breite
 *  und senkrechten Reitern, Karteikarte mit Kürzelzeile – gewählt unter Mein Konto, gespeichert für die Person. */
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import { apiAls, eindeutig, neuesKonto } from "./hilfen";

function vorTagen(tage: number) {
  const d = new Date();
  d.setDate(d.getDate() - tage);
  return d.toISOString().slice(0, 10);
}

/** Mit der Maus am Griff ziehen (dx, dy in px) */
async function ziehen(page: Page, griff: Locator, dx: number, dy: number) {
  const box = (await griff.boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + Math.min(box.height / 2, 130);
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx / 2, y + dy / 2, { steps: 4 });
  await page.mouse.move(x + dx, y + dy, { steps: 4 });
  await page.mouse.up();
}

/** In Mein Konto die Aktenansicht wählen und warten, bis sie gespeichert ist */
async function ansichtWaehlen(page: Page, titel: string) {
  await page.goto("/konto");
  const gespeichert = page.waitForResponse((r) => r.url().includes("/api/auth/ich/") && r.request().method() === "PATCH" && r.ok());
  await page.getByRole("radio", { name: `Aktenansicht ${titel}` }).click();
  await gespeichert;
  await expect(page.getByRole("radio", { name: `Aktenansicht ${titel}` })).toHaveAttribute("aria-checked", "true");
}

test("Aktenansicht: Kopfzeile in Stufen, Seitenleiste mit Breite, Karteikarte mit Kürzelzeile – je Person gespeichert", async ({ browser }) => {
  const api = await apiAls("mitarbeiter");
  const nachname = eindeutig("Ansicht");
  const p = await api.post("patienten/", { nachname, vorname: "Vera", geburtsdatum: "1970-02-03", geschlecht: "w", groesse_cm: "168" });
  await api.post("gewichte/", { patient: p.id, gewicht_kg: "58.4", gemessen_am: vorTagen(3), quelle: "telefonisch" });
  await api.post("kontakte/", { patient: p.id, text: "<p>Telefonat zur Ansicht</p>", art: null, wiedervorlage: null });
  await api.ende();
  const akte = `/patienten/${p.id}`;

  const konto = await neuesKonto("mitarbeiter", "Anja", "Ansicht");
  const ctx = await browser.newContext({ storageState: konto.zustand, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();

  // 1 · Kopfzeile (Standard): Angaben in Gruppen; Griff unter dem Kopf in drei Stufen
  await page.goto(akte);
  const kopf = page.getByTestId("aktenkopf");
  await expect(kopf).toHaveAttribute("data-stufe", "voll");
  const zahlen = page.getByTestId("kennzahlen");
  for (const gruppe of ["Ernährung", "Versorgung", "Termine und Kontakt", "Hinweise und Auskunft"]) {
    await expect(zahlen.getByRole("group", { name: gruppe })).toBeVisible();
  }
  await expect(zahlen.getByRole("group", { name: "Ernährung" })).toContainText("58,4 kg");
  await expect(page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /^Kontakte/ })).toBeVisible();
  const griff = page.getByTestId("kopfgriff");
  const hoeheVoll = (await kopf.boundingBox())!.height;
  await griff.focus();
  await page.keyboard.press("ArrowUp");
  await expect(kopf).toHaveAttribute("data-stufe", "kompakt");
  await expect(zahlen).toContainText("58,4 kg");
  await expect(zahlen.getByRole("group")).toHaveCount(0);
  await page.keyboard.press("ArrowUp");
  await expect(kopf).toHaveAttribute("data-stufe", "minimal");
  await expect(page.getByTestId("kennzahlen")).toHaveCount(0);
  expect((await kopf.boundingBox())!.height).toBeLessThan(hoeheVoll);
  // Ziehen nach unten: zwei Stufen größer
  await ziehen(page, griff, 0, 80);
  await expect(kopf).toHaveAttribute("data-stufe", "voll");
  // gespeichert für die Person: nach dem Neuladen wieder „Eine Zeile“
  await ziehen(page, griff, 0, -40);
  await expect(kopf).toHaveAttribute("data-stufe", "kompakt");
  await page.waitForTimeout(500);
  await page.reload();
  await expect(page.getByTestId("aktenkopf")).toHaveAttribute("data-stufe", "kompakt");

  // 2 · Seitenleiste: Knöpfe oben in der Leiste, senkrechte Reiter, Breite ziehen (rastet ein)
  await ansichtWaehlen(page, "Seitenleiste");
  await page.goto(akte);
  await expect(page.getByTestId("akte-ansicht")).toHaveAttribute("data-ansicht", "seitenleiste");
  const leiste = page.getByTestId("aktenkopf");
  await expect(leiste.getByRole("button", { name: "Kontakt" })).toBeVisible();
  await expect(leiste.getByRole("heading", { name: `${nachname}, Vera` })).toBeVisible();
  // Knöpfe stehen über dem Namen
  const knopfY = (await leiste.getByRole("button", { name: "Gewicht" }).boundingBox())!.y;
  expect(knopfY).toBeLessThan((await leiste.getByRole("heading", { name: `${nachname}, Vera` }).boundingBox())!.y);
  await expect(page.getByTestId("kennzahlen").getByRole("group", { name: "Versorgung" })).toBeVisible();
  const reiter = page.getByTestId("senkrechte-reiter");
  const kontakte = reiter.getByRole("link", { name: /^Kontakte/ });
  const verlauf = reiter.getByRole("link", { name: /^Verlauf/ });
  // senkrecht: „Verlauf“ steht unter „Kontakte“, nicht daneben
  expect((await verlauf.boundingBox())!.y).toBeGreaterThan((await kontakte.boundingBox())!.y + 10);
  const breiteGriff = page.getByTestId("leistengriff");
  await expect(breiteGriff).toHaveAttribute("data-breite", "300");
  expect(Math.round((await leiste.boundingBox())!.width)).toBe(300);
  await breiteGriff.focus();
  await page.keyboard.press("ArrowRight");
  await expect(breiteGriff).toHaveAttribute("data-breite", "360");
  await expect.poll(async () => Math.round((await leiste.boundingBox())!.width)).toBe(360);
  // 360 − 100 = 260 → rastet bei 240 ein
  await ziehen(page, breiteGriff, -100, 0);
  await expect(breiteGriff).toHaveAttribute("data-breite", "240");
  await page.waitForTimeout(500);
  await page.reload();
  await expect(page.getByTestId("leistengriff")).toHaveAttribute("data-breite", "240");
  await page.getByTestId("senkrechte-reiter").getByRole("link", { name: /^Kontakte/ }).click();
  await expect(page).toHaveURL(new RegExp(`${akte}/kontakte$`));
  await expect(page.getByTestId("kontaktliste")).toContainText("Telefonat zur Ansicht");
  // unter 1280 px stehen Leiste und Inhalt untereinander, der Griff verschwindet
  await page.setViewportSize({ width: 1100, height: 900 });
  await expect(page.getByTestId("leistengriff")).toBeHidden();
  await page.setViewportSize({ width: 1440, height: 960 });

  // 3 · Karteikarte: öffnet mit allen Einträgen chronologisch, Filter, Kürzelzeile
  await ansichtWaehlen(page, "Karteikarte");
  await page.goto(akte);
  await expect(page).toHaveURL(new RegExp(`${akte}/kartei$`));
  await expect(page.getByTestId("akte-ansicht")).toHaveAttribute("data-ansicht", "karteikarte");
  const kartei = page.getByTestId("karteikarte");
  await expect(kartei.locator('[data-testid="karteieintrag"][data-art="K"]')).toContainText("Telefonat zur Ansicht");
  await expect(kartei.locator('[data-testid="karteieintrag"][data-art="G"]')).toContainText("58,4 kg");
  await kartei.getByRole("button", { name: /^G Gewicht/ }).click();
  await expect(kartei.getByTestId("karteieintrag")).toHaveCount(1);
  await kartei.getByRole("button", { name: "Alle", exact: true }).click();
  await expect(kartei.locator('[data-testid="karteieintrag"][data-art="K"]')).toHaveCount(1);
  // rechte Spalte mit den Angaben, „Übersicht“ bleibt als Reiter erreichbar
  await expect(page.getByTestId("kennzahlen").getByRole("group", { name: "Ernährung" })).toContainText("58,4 kg");
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Übersicht" }).click();
  await expect(page).toHaveURL(new RegExp(`${akte}$`));
  await expect(page.getByTestId("gewichtskarte")).toBeVisible();
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Karteikarte" }).click();

  // Kürzelzeile: „K Text“ öffnet den neuen Kontakt mit dem Text, gespeichert wird erst im Formular
  await page.getByLabel("Kürzelzeile").fill("K Rückruf zur Kürzelzeile vereinbart");
  await page.getByLabel("Kürzelzeile").press("Enter");
  await expect(page).toHaveURL(new RegExp(`${akte}/kontakte$`));
  const neu = page.getByTestId("neuer-kontakt");
  await expect(neu.getByRole("textbox", { name: "Neuer Kontakt" })).toContainText("Rückruf zur Kürzelzeile vereinbart");
  await neu.getByRole("button", { name: "Kontakt speichern" }).click();
  await expect(page.getByTestId("kontaktliste")).toContainText("Rückruf zur Kürzelzeile vereinbart");
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Karteikarte" }).click();
  await expect(kartei.locator('[data-testid="karteieintrag"][data-art="K"]')).toHaveCount(2);
  // „G 61,2“ öffnet das Gewicht mit dem Wert; unbekannte Kürzel melden sich
  await page.getByLabel("Kürzelzeile").fill("G 61,2");
  await page.getByLabel("Kürzelzeile").press("Enter");
  await expect(page).toHaveURL(new RegExp(`${akte}$`));
  await expect(page.getByTestId("gewichtskarte").getByLabel("Neues Gewicht")).toHaveValue("61,2");
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Karteikarte" }).click();
  await page.getByLabel("Kürzelzeile").fill("X etwas");
  await page.getByLabel("Kürzelzeile").press("Enter");
  await expect(page.getByTestId("kuerzelzeile").getByRole("alert")).toContainText("Unbekanntes Kürzel „X“");

  // zurück auf Standard: wieder Kopfzeile
  await page.goto("/konto");
  await page.getByRole("button", { name: "Auf Standard zurücksetzen" }).click();
  await page.waitForTimeout(500);
  await page.goto(akte);
  await expect(page.getByTestId("aktenkopf")).toHaveAttribute("data-stufe", "voll");
  await expect(page.getByTestId("akte-ansicht")).toHaveCount(0);
  await ctx.close();
});
