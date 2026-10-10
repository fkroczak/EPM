/**
 * Wünsche aus der Praxis vom 06.10.2026 über die Oberfläche: Diagnosen mit ICD (F117), Versichertendaten (F118),
 * Laborbefund und BIA (F112–F114), Bericht mit Freigabe (F115), Sprechstundenblatt (F116).
 *
 * Dazu die Wünsche vom 07.10.2026: Hinweise mit „×“ wegklicken (F119), Grenzen „gilt als alt“ (F120) und ein eigener
 * Reiter je Bereich (F121).
 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

async function neuerPatient() {
  const api = await apiAls("mitarbeiter");
  const nachname = eindeutig("Praxis");
  const p = await api.post("patienten/", { nachname, vorname: "Pia", geburtsdatum: "1972-03-08", geschlecht: "w",
    groesse_cm: "168", ist_test: true });
  await api.post("gewichte/", { patient: p.id, gewicht_kg: "62.4", quelle: "telefonisch" });
  await api.ende();
  return { id: p.id as number, name: `${nachname}, Pia` };
}

async function oeffnen(page: Page, id: number, reiter = "") {
  await page.goto(`/patienten/${id}${reiter}`);
  await expect(page.getByTestId("aktenkopf")).toBeVisible();
}

test("Diagnose mit ICD-Code eintragen; die Liste im Hintergrund wächst mit", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id, "/diagnosen");
  await page.getByRole("button", { name: "Neue Diagnose" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Diagnose").fill("Kurzdarmsyndrom");
  await dialog.getByLabel("ICD-Code").fill("K91.2");
  await dialog.getByLabel("Zusatzkennzeichen").selectOption("G");
  await expect(dialog.getByText("Kurzdarmsyndrom [K91.2G]")).toBeVisible();
  await dialog.getByRole("button", { name: "Speichern" }).click();
  // alle Diagnosen zusammen als Liste wie im Arztbrief (Wunsch 10.10.2026)
  const liste2 = page.getByTestId("diagnoseliste");
  await expect(liste2).toContainText("Kurzdarmsyndrom");
  await expect(liste2.getByTestId("diagnose-zeile").first()).toContainText("K91.2G");
  // „Beenden“ fragt nach – „Abbrechen“ lässt sie aktuell, erst die Rückfrage beendet (Eine Sprache, 08.10.2026)
  await liste2.getByRole("button", { name: "Kurzdarmsyndrom beenden" }).click();
  await expect(page.getByRole("dialog").getByRole("heading", { name: "Diagnose beenden" })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Abbrechen" }).click();
  await expect(liste2.getByRole("button", { name: "Kurzdarmsyndrom beenden" })).toBeVisible();
  await liste2.getByRole("button", { name: "Kurzdarmsyndrom beenden" }).click();
  await page.getByRole("dialog").getByTestId("bestaetigen").click();
  await expect(page.getByText("Als nicht mehr zutreffend eingetragen.")).toBeVisible();
  await liste2.getByRole("button", { name: /beendete anzeigen/ }).click();
  await liste2.getByRole("button", { name: "Kurzdarmsyndrom wieder aktuell" }).click();
  await expect(page.getByText("Wieder als zutreffend eingetragen.")).toBeVisible();

  // der Katalog hat den Eintrag übernommen (Vorlagen › Labor und Diagnosen)
  const api = await apiAls("mitarbeiter");
  const liste = await api.get("diagnoseliste/?aktiv=true");
  await api.ende();
  expect((liste as { icd_code: string; bezeichnung: string }[]).some(
    (d) => d.icd_code === "K91.2" && d.bezeichnung === "Kurzdarmsyndrom")).toBeTruthy();
});

test("Versichertendaten in den Stammdaten", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id);
  await page.getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: "Stammdaten bearbeiten" }).click();
  await page.getByLabel("Versicherungsart").selectOption("gkv");
  await page.getByLabel("Versicherung", { exact: true }).fill("AOK NordWest");
  await page.getByLabel("Versichertennummer").fill("A123456789");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByTestId("krankenkasse")).toContainText("AOK NordWest");
  await expect(page.getByTestId("krankenkasse")).toContainText("GKV");
  await expect(page.getByTestId("versichertennummer")).toHaveText("A123456789");
});

test("Laborbefund über die Maske erfassen – nur Werte eintragen", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id, "/labor");
  await page.getByRole("button", { name: "Neuer Laborbefund" }).click();
  await page.getByRole("dialog").getByLabel("Labor").fill("Labor Dr. Wagner");
  const maske = page.getByTestId("labor-maske");
  await maske.getByLabel("Ferritin").fill("18");
  await maske.getByLabel("Natrium").fill("138");
  // Parameter, der nicht im Katalog steht (Tumormarker, genetische Parameter)
  const weitere = page.getByTestId("weitere-parameter");
  await weitere.getByRole("button", { name: "Parameter hinzufügen" }).click();
  await weitere.getByLabel("Parameter 1").fill("CA 19-9");
  await weitere.getByLabel("Wert 1").fill("12,4");
  await weitere.getByLabel("Einheit 1").fill("U/ml");
  await page.getByRole("button", { name: /^Speichern \(\d+ Werte?\)$/ }).click();

  const detail = page.getByTestId("labor-detail");
  await expect(detail).toContainText("3 Werte");
  await expect(page.getByText("Ferritin")).toBeVisible();
  await expect(page.getByText("µg/l")).toBeVisible();
  await expect(page.getByText("CA 19-9")).toBeVisible();
});

test("BIA-Messung mit Beurteilung; das Gewicht wandert in den Verlauf", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id, "/bia");
  await page.getByRole("button", { name: "Neue Messung" }).click();
  await page.getByLabel("Gewicht (kg)").fill("61,2");
  await page.getByLabel("BCM (kg)").fill("24,1");
  await page.getByLabel("Fettmasse (kg)").fill("18,6");
  await page.getByLabel("ECW – extrazelluläres Wasser (%)").fill("46,2");
  await page.getByLabel("Körperwasser (l)").fill("32,8");
  await expect(page.getByRole("dialog").getByText(/aus Gewicht und Größe/)).toBeVisible(); // nur im Dialog (der Kopf erklärt „BMI“ ähnlich)
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByTestId("bia-detail")).toContainText("24,1 kg");

  await oeffnen(page, p.id);
  await expect(page.getByTestId("kennzahlen")).toContainText("61,2");
});

test("Bericht: Entwurf, Freigabe durch den Mediziner, danach unveränderlich", async ({ page, browser }) => {
  const p = await neuerPatient();
  const api = await apiAls("mitarbeiter");
  await api.post("diagnosen/", { patient: p.id, bezeichnung: "Kurzdarmsyndrom", icd_code: "K91.2", kennzeichen: "G", seit: "2020-03-01" });
  await api.post("diagnosen/", { patient: p.id, bezeichnung: "Verdacht auf Eisenmangel", icd_code: "D50.9", kennzeichen: "V" });
  await api.ende();
  await oeffnen(page, p.id, "/berichte");
  await page.getByRole("button", { name: "Neuer Bericht" }).click();
  await page.getByLabel("Titel").fill("Verlaufsbericht 2026");
  await page.getByLabel("Berichtsart").selectOption({ label: "Verlaufsbericht" });
  await page.getByLabel("Empfänger").fill("Hausarzt Dr. Hausmann");
  await page.getByRole("textbox", { name: "Bericht" }).fill("Stabiler Verlauf unter heimparenteraler Ernährung.");
  // alle Diagnosen der Akte stehen im Dialog und lassen sich in den Text übernehmen (Wunsch 10.10.2026)
  const diagnosen = page.getByRole("dialog").getByTestId("bericht-diagnosen");
  await expect(diagnosen).toContainText("Kurzdarmsyndrom");
  await expect(diagnosen).toContainText("Verdacht auf Eisenmangel");
  await diagnosen.getByRole("button", { name: "In den Text übernehmen" }).click();
  await expect(page.getByRole("textbox", { name: "Bericht" })).toContainText("Kurzdarmsyndrom (ICD-10 K91.2 G, seit 01.03.2020)");
  await expect(page.getByRole("textbox", { name: "Bericht" })).toContainText("Stabiler Verlauf");
  await page.getByRole("button", { name: "Entwurf speichern" }).click();
  // der Status steht links am Eintrag und rechts im Detail – hier das Detail (F122)
  await expect(page.getByTestId("bericht-detail").getByTestId("bericht-status")).toContainText("Entwurf"); // mit Erklärung zum Begriff (F181)

  // Mitarbeiter dürfen nicht freigeben – der Knopf erscheint erst gar nicht
  await expect(page.getByRole("button", { name: "Freigeben" })).toHaveCount(0);

  const medizinerSeite = await (await browser.newContext({ storageState: zustand("mediziner") })).newPage();
  await medizinerSeite.goto(`/patienten/${p.id}/berichte`);
  await medizinerSeite.getByRole("button", { name: "Freigeben" }).click();
  await medizinerSeite.getByRole("button", { name: "Freigeben" }).last().click();
  await expect(medizinerSeite.getByTestId("bericht-detail").getByTestId("bericht-status")).toHaveText("freigegeben");
  await expect(medizinerSeite.getByText(/Maschinell erstellt, geprüft und freigegeben von/)).toBeVisible();
  // Bearbeiten ist weg, die PDF liegt in den Dokumenten
  await expect(medizinerSeite.getByRole("button", { name: "Bearbeiten", exact: true })).toHaveCount(0);
  await medizinerSeite.goto(`/patienten/${p.id}/dokumente`);
  // genau treffen: Die Vorschau der PDF trägt den Titel im unsichtbaren Textlayer ein zweites Mal
  await expect(medizinerSeite.getByTestId("dokument-details")
    .getByText("Verlaufsbericht 2026", { exact: true })).toBeVisible();
  await medizinerSeite.close();
});

test("Infusionstage je Beutelart im Plan-Editor", async ({ browser }) => {
  const p = await neuerPatient();
  const seite = await (await browser.newContext({ storageState: zustand("mediziner") })).newPage();
  await seite.goto(`/patienten/${p.id}/plaene/neu`);
  const tage = seite.getByTestId("infusionstage");
  await tage.getByLabel(/^PE.*\(Mischbeutel\)$/).fill("5");
  await tage.getByLabel("Zusatzvolumen").fill("2");
  await tage.getByLabel("Infusionsfrei").fill("4");
  await seite.getByRole("button", { name: "Entwurf speichern" }).click();
  await expect(seite.getByText(/höchstens 2 infusionsfreie Tage/)).toBeVisible();
  await tage.getByLabel("Infusionsfrei").fill("0");
  await seite.getByRole("button", { name: "Entwurf speichern" }).click();
  await expect(seite.getByTestId("infusionstage").getByLabel(/^PE.*\(Mischbeutel\)$/)).toHaveValue("5");
  await seite.close();
});

test("Unterlagen für die Sprechstunde als PDF", async ({ page }) => {
  const p = await neuerPatient();
  const api = await apiAls("mitarbeiter");
  await api.post("diagnosen/", { patient: p.id, bezeichnung: "Kurzdarmsyndrom", icd_code: "K91.2", kennzeichen: "G" });
  await api.ende();
  await oeffnen(page, p.id);
  await page.getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: "Unterlagen für die Sprechstunde" }).click();
  await expect(page.getByRole("dialog")).toContainText("Unterlagen für die Sprechstunde");
  await expect(page.getByTestId("pdf-dialog")).toBeVisible();
  await expect(page.getByTestId("pdf-text").first()).toContainText("Kurzdarmsyndrom");
});

test("Hinweise mit „×“ wegklicken und wieder einschalten", async ({ page }) => {
  const p = await neuerPatient();
  // Ohne Laborbefund und ohne BIA-Messung steht beides als Hinweis an der Akte (F120)
  await page.goto(`/patienten?suche=${encodeURIComponent(p.name.split(",")[0])}`);
  const zeile = page.getByTestId("patientenliste").getByRole("row").filter({ hasText: p.name });
  await expect(zeile).toContainText("Kein Laborbefund");

  await zeile.getByRole("button", { name: /Hinweis „Kein Laborbefund“ ausblenden/ }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("group", { name: "Ruhe" }).getByRole("button", { name: "6 Monate" }).click();
  await dialog.getByLabel("Grund").fill("Labor ist beim Hausarzt angefordert");
  await dialog.getByRole("button", { name: "Ausblenden" }).click();
  await expect(page.getByText("Hinweis für 6 Monate ausgeblendet.")).toBeVisible();
  await expect(zeile).not.toContainText("Kein Laborbefund");
  await expect(zeile).toContainText("Keine BIA-Messung"); // andere Hinweise bleiben

  // In der Akte steht, was ausgeblendet ist – und lässt sich zurückholen
  await oeffnen(page, p.id);
  const karte = page.getByTestId("stumme-hinweise");
  await expect(karte).toContainText("Laborbefund älter als");
  await expect(karte).toContainText("Labor ist beim Hausarzt angefordert");
  await karte.getByRole("button", { name: "Wieder einschalten" }).click();
  await expect(page.getByText("Hinweis wieder eingeschaltet.")).toBeVisible();
  await expect(page.getByTestId("stumme-hinweise")).toHaveCount(0);

  // und steht im Verlauf der Akte
  await oeffnen(page, p.id, "/verlauf");
  await page.getByTestId("verlauf-bereich").selectOption("hinweisruhe");
  await expect(page.getByTestId("verlauf")).toContainText("Labor ist beim Hausarzt angefordert");
});

test("Jeder Bereich ein eigener Reiter; die alte Adresse leitet weiter", async ({ page }) => {
  const p = await neuerPatient();
  const reiter = page.getByRole("navigation", { name: "Aktenbereiche" });
  await oeffnen(page, p.id);
  // Diagnosen und Therapie getrennt (F121)
  await reiter.getByRole("link", { name: /^Diagnosen/ }).click();
  await expect(page.getByTestId("diagnosen")).toBeVisible();
  await expect(page.getByTestId("karte-diagnose")).toBeVisible();   // „Notizen“ rechts
  await expect(page.getByTestId("karte-therapie")).toHaveCount(0);
  await reiter.getByRole("link", { name: /^Therapie/ }).click();
  await expect(page.getByTestId("karte-therapie")).toBeVisible();
  await reiter.getByRole("link", { name: /^Empfehlung/ }).click();
  await expect(page.getByTestId("karte-empfehlung")).toBeVisible();
  await expect(page.getByTestId("karte-therapie")).toHaveCount(0);
  // Labor und BIA getrennt
  await reiter.getByRole("link", { name: /^Labor/ }).click();
  await expect(page.getByRole("button", { name: "Neuer Laborbefund" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Neue Messung" })).toHaveCount(0);
  await reiter.getByRole("link", { name: /^BIA/ }).click();
  await expect(page.getByRole("button", { name: "Neue Messung" })).toBeVisible();
  // der alte Weg „Labor & BIA“ landet beim Labor
  await page.goto(`/patienten/${p.id}/befunde`);
  await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}/labor$`));
});

test("Grenze „gilt als alt“ unter Vorlagen › Grenzwerte", async ({ browser, page }) => {
  const api = await apiAls("admin");
  await api.patch("einstellungen/", { labor_alter_warnung_monate: 6, bia_alter_warnung_monate: 9 });
  await api.ende();
  const ctx = await browser.newContext({ storageState: zustand("admin"), ignoreHTTPSErrors: true });
  const adm = await ctx.newPage();
  await adm.goto("/admin/vorlagen");
  await adm.getByRole("group", { name: "Bereich" }).getByRole("button", { name: "Grenzwerte" }).click();
  await expect(adm.getByLabel("Laborbefund gilt als alt nach")).toHaveValue("6");
  await expect(adm.getByLabel("BIA-Messung gilt als alt nach")).toHaveValue("9");
  await ctx.close();
  // die Startseite nennt die eingestellte Grenze und zählt die Akten
  await page.goto("/");
  await expect(page.getByText(/Laborbefund fehlt oder ist älter als 6 Monate/)).toBeVisible();
  await expect(page.getByTestId("pruefen-labor_faellig")).toBeVisible();
  const zurueck = await apiAls("admin");
  await zurueck.patch("einstellungen/", { labor_alter_warnung_monate: 12, bia_alter_warnung_monate: 12 });
  await zurueck.ende();
});

test("Bericht verwerfen fragt nach (Eine Sprache, 08.10.2026)", async ({ page }) => {
  const p = await neuerPatient();
  await oeffnen(page, p.id, "/berichte");
  await page.getByRole("button", { name: "Neuer Bericht" }).click();
  await page.getByLabel("Titel").fill("Bericht zum Verwerfen");
  await page.getByLabel("Berichtsart").selectOption({ label: "Verlaufsbericht" });
  await page.getByRole("textbox", { name: "Bericht" }).fill("Wird verworfen.");
  await page.getByRole("button", { name: "Entwurf speichern" }).click();
  const detail = page.getByTestId("bericht-detail");
  await expect(detail.getByTestId("bericht-status")).toContainText("Entwurf"); // mit Erklärung zum Begriff (F181)
  await detail.getByRole("button", { name: "Verwerfen" }).click();
  const frage = page.getByRole("dialog");
  await expect(frage.getByRole("heading", { name: "Entwurf verwerfen" })).toBeVisible();
  await expect(frage).toContainText("Bericht zum Verwerfen");
  // der rote Knopf steht links von „Abbrechen“
  const rot = (await frage.getByTestId("bestaetigen").boundingBox())!;
  const abbrechen = (await frage.getByRole("button", { name: "Abbrechen" }).boundingBox())!;
  expect(rot.x).toBeLessThan(abbrechen.x);
  await frage.getByRole("button", { name: "Abbrechen" }).click();
  await expect(detail).toContainText("Bericht zum Verwerfen");
  await detail.getByRole("button", { name: "Verwerfen" }).click();
  await page.getByRole("dialog").getByTestId("bestaetigen").click();
  await expect(page.getByText("Entwurf verworfen.")).toBeVisible();
  await expect(page.getByTestId("bericht-detail")).toHaveCount(0);
});
