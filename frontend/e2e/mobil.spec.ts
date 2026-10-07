/** Am Telefon (Festlegung 08.10.2026, F133): Hauptarbeitsplatz bleibt der PC; am Telefon Pläne schnell freigeben, kurz
 *  in die Akte schauen und Notizen erfassen. Geprüft mit der Bildschirmgröße eines Android-Telefons (Touch). */
import { devices, expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, eindeutig, merken, zustand } from "./hilfen";

const { defaultBrowserType: _browser, ...telefon } = devices["Pixel 7"];
test.use({ ...telefon, storageState: zustand("mediziner") });

/** Nichts darf seitlich über den Bildschirm hinausragen (sonst wackelt die Seite beim Wischen). Im Fehlerfall nennt
 *  die Meldung die Elemente, die zu breit sind. */
async function passtInDieBreite(page: Page, wo: string) {
  const { breite, inhalt, zuBreit } = await page.evaluate(() => {
    const b = window.innerWidth;
    const liste: string[] = [];
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("body *"))) {
      const r = el.getBoundingClientRect();
      if (r.width && r.right > b + 1 && liste.length < 8) {
        liste.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)} (${Math.round(r.left)}–${Math.round(r.right)})`);
      }
    }
    return { breite: b, inhalt: document.documentElement.scrollWidth, zuBreit: liste };
  });
  expect(inhalt, `${wo}: Seite ${inhalt}px breit bei ${breite}px Bildschirm – ${zuBreit.join("; ")}`).toBeLessThanOrEqual(breite + 1);
}

test("Telefon: Leiste unten, Menü, Suche, Seiten passen in die Breite", async ({ page }) => {
  await page.goto("/");
  const leiste = page.getByTestId("mobil-leiste");
  await expect(leiste).toBeVisible();
  await expect(page.getByTestId("seitenleiste")).toBeHidden();
  await passtInDieBreite(page, "Start");

  // Menü (Schublade) mit allen Bereichen
  await page.getByTestId("mobil-menue").click();
  const schublade = page.getByTestId("schublade");
  await expect(schublade).toBeVisible();
  await expect(schublade.getByRole("link", { name: "Versorger" })).toBeVisible();
  await schublade.getByRole("link", { name: "Kalender" }).click();
  await expect(schublade).toBeHidden();
  await expect(page).toHaveURL(/\/kalender/);
  await passtInDieBreite(page, "Kalender");

  // Patientensuche aus der Kopfzeile
  await page.getByTestId("mobil-suche").click();
  await page.getByRole("combobox", { name: "Suchen" }).fill("Probe");
  await page.getByRole("option").first().click();
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
  await passtInDieBreite(page, "Akte");
  // Zurück in der Kopfzeile führt zur Liste
  await page.getByRole("link", { name: "Zurück: Patienten" }).click();
  await expect(page.getByTestId("patientenliste")).toBeVisible();
  await expect(page.getByTestId("patientenliste").getByRole("listitem").first()).toBeVisible();
  await passtInDieBreite(page, "Patienten");

  for (const [pfad, wo] of [["/infusionsplaene", "Infusionspläne"], ["/konto", "Mein Konto"], ["/hilfe", "Hilfe"], ["/versorger", "Versorger"]]) {
    await page.goto(pfad);
    await expect(leiste).toBeVisible();
    await passtInDieBreite(page, wo);
  }
});

test("Telefon: Entwurf aus „Pläne“ öffnen und freigeben – ohne Scrollen zum Plan", async ({ page }) => {
  const med = await apiAls("mediziner");
  const p = await med.post("patienten/", { nachname: eindeutig("Mobil"), vorname: "Mia", geburtsdatum: "1975-05-05" });
  await med.post("gewichte/", { patient: p.id, gewicht_kg: "58.0", quelle: "telefonisch" });
  const entwurf = await med.post("infusionsplaene/entwurf/", { patient: p.id });
  const praeparate: { id: number; kategorie: string; name: string }[] = await med.get("praeparate/");
  const praeparat = (kategorie: string, name: string) => praeparate.find((x) => x.kategorie === kategorie && x.name === name)!.id;
  await med.patch(`infusionsplaene/${entwurf.id}/`, {
    glucose_praeparat: praeparat("glucose", "Glucose"), glucose_g: "150",
    aminosaeuren_praeparat: praeparat("aminosaeuren", "Glamin"), aminosaeuren_g: "70",
    lipide_praeparat: praeparat("lipide", "Clinoleic"), lipide_g: "50", laufzeit_h: "12",
  });
  await med.ende();

  await page.goto("/");
  await page.getByTestId("mobil-leiste").getByRole("link", { name: "Pläne" }).click();
  await expect(page).toHaveURL(/gruppe=entwuerfe/);
  const karte = page.getByTestId("plan-uebersicht").getByRole("link", { name: `Plan von ${p.nachname}, ${p.vorname} öffnen` });
  await karte.click();
  const detail = page.getByTestId("plan-detail");
  await expect(detail).toBeVisible();
  // der gewählte Plan steht oben, vor der Liste
  await expect(detail.getByRole("button", { name: "Freigeben" })).toBeInViewport();
  await passtInDieBreite(page, "Plan in der Akte");
  await detail.getByRole("button", { name: "Freigeben" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeInViewport();
  await dialog.getByRole("button", { name: "Freigeben" }).click();
  await expect(page.getByText("Plan freigegeben.")).toBeVisible();
  await expect(detail).toContainText(/Freigegeben am/);
  merken("mobil_plan", { patient: p.id, plan: entwurf.id });
});

test("Telefon: Notiz zur offenen Akte über „Notiz“ in der Leiste", async ({ page }) => {
  const med = await apiAls("mediziner");
  const p = await med.post("patienten/", { nachname: eindeutig("Notiz"), vorname: "Nina", geburtsdatum: "1980-08-08" });
  await med.ende();
  await page.goto(`/patienten/${p.id}`);
  await expect(page.getByTestId("aktenkopf")).toContainText(p.nachname);
  await expect(page.getByTestId("gewichtskarte")).toBeVisible();
  await passtInDieBreite(page, "Akte ohne Einträge");
  // Reiter wischen seitlich statt umzubrechen
  const reiter = page.getByRole("navigation", { name: "Aktenbereiche" });
  const hoehe = await reiter.evaluate((e) => e.getBoundingClientRect().height);
  expect(hoehe).toBeLessThan(60);
  await page.getByTestId("mobil-notiz").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Kontakt erfassen" })).toBeVisible();
  await expect(dialog).toContainText(`${p.nachname}, ${p.vorname}`);   // die offene Akte ist vorgewählt
  const text = `Telefonat vom Telefon ${eindeutig("n")}`;
  await dialog.getByRole("textbox", { name: "Notiz" }).fill(text);
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /Kontakte/ }).click();
  await expect(page.getByTestId("kontaktliste")).toContainText(text);
  merken("mobil_notiz", { patient: p.id, text });
});
