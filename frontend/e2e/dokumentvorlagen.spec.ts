/** Entwurf 18 · Dokumentvorlagen: Block ändern, Datenfeld einfügen, Prüfung, Vorschau mit Testpatient, Freigeben;
 *  Vorlagen-Portal einfacher (F180): Übersicht mit Suche, Feldeinfüger, frühere Fassung, Kopie als eigene Vorlage. */
import { expect, test } from "@playwright/test";
import { apiAls, merken, zustand } from "./hilfen";

test.use({ storageState: zustand("mitarbeiter") });

// Fassungen zählen erst nach dem ersten Altdaten-Import weiter (6c0eac8, vorlagen/fassung1.py); davor ersetzt Freigeben
// die Fassung 1, und es gibt keine frühere Fassung zum Wiederherstellen. Diese Tests prüfen das Verhalten danach –
// sie laufen daher nach „aa-import“ (gleicher Teil in e2e/teile.ts).
test.beforeAll(async () => {
  const api = await apiAls("mitarbeiter");
  const uebersicht = await api.get("vorlagen/infusionsplan/");
  await api.ende();
  expect(uebersicht.nur_fassung_1, "Vorbedingung: Altdaten-Import (aa-import.spec.ts) ist gelaufen").toBe(false);
});

test("Dokumentvorlage Infusionsplan: Text mit Datenfeld, Prüfung, Vorschau, Veröffentlichen", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  const vorher = (await api.get("vorlagen/")).find((v: { art: string }) => v.art === "infusionsplan");

  await page.goto("/admin/vorlagen");
  // Dokumentvorlagen sind ein Bereich der Vorlagen wie Briefkopf, Auswahllisten und Grenzwerte
  await page.getByRole("group", { name: "Bereich" }).getByRole("button", { name: "Dokumentvorlagen" }).click();
  await expect(page).toHaveURL(/\/admin\/vorlagen\/dokumente$/);
  await expect(page.getByRole("group", { name: "Bereich" }).getByRole("button", { name: "Dokumentvorlagen" })).toHaveAttribute("aria-pressed", "true");
  // zuerst die Liste aller Vorlagen mit „Wofür?“ und Stand (F180)
  const karte = page.getByTestId("vorlagenliste").getByRole("button", { name: /^Infusionsplan/ });
  await expect(karte).toContainText(`in Gebrauch · Fassung ${vorher.aktiv.version}`);
  await expect(karte).toContainText("Wo benutzt:");
  await karte.click();
  await expect(page).toHaveURL(/\/admin\/vorlagen\/dokumente\?art=infusionsplan$/);
  const editor = page.getByTestId("dokumentvorlagen");
  // Stand und Knöpfe stehen oben rechts im Seitenkopf der Vorlagen (wie „Speichern“ in den anderen Bereichen)
  const aktionen = page.getByRole("main");
  await expect(aktionen.getByTestId("vorlage-stand")).toHaveText(`Fassung ${vorher.aktiv.version} ist in Gebrauch`);
  const aufbau = editor.getByTestId("aufbau");
  // Startvorlage: Aufbau wie die PDF des Altsystems
  await expect(aufbau).toContainText("Zusammensetzung der Infusionslösung");
  await expect(aufbau).toContainText("Laufzeit und Volumen");
  await expect(editor.getByTestId("vorlage-seite")).toContainText("Empfehlung eines Infusionsplans");
  // Platzhalter als lesbarer Chip ({{Plan.gültig_ab}} → „gültig ab“)
  await expect(editor.getByTestId("vorlage-seite").locator(".feldchip", { hasText: "gültig ab" })).toBeVisible();
  // Aufbau wie ein Laborbefund: Mineralstoffe neben der Zusammensetzung, Kopf wie in der Akte
  await expect(editor.getByTestId("nebeneinander")).toContainText("Natrium");
  await aufbau.getByRole("button", { name: /Mineralstoffe/ }).click();
  // ältere Vorlage „ein Drittel daneben“ erscheint im 6-Spalten-Raster: Spalte 5 bis 6, in derselben Zeile (14.10.2026)
  const lage = editor.getByTestId("block-eigenschaften").getByTestId("raster-wahl");
  await expect(lage.getByLabel("Von Spalte")).toHaveValue("5");
  await expect(lage.getByLabel("Bis Spalte")).toHaveValue("6");
  await expect(lage.getByLabel("In derselben Zeile wie der Block davor")).toBeChecked();
  await expect(editor.getByTestId("block-eigenschaften").getByLabel("Darstellung")).toHaveValue("befund");
  // Reihenfolge der Felder ändern, ohne zu löschen und neu anzulegen
  const eig = editor.getByTestId("block-eigenschaften");
  await eig.getByRole("button", { name: "Feld 1 nach unten" }).click();
  await expect(eig.getByLabel("Bezeichnung 1", { exact: true })).toHaveValue("Kalium");
  await expect(eig.getByLabel("Bezeichnung 2", { exact: true })).toHaveValue("Natrium");
  await expect(editor.getByTestId("nebeneinander")).toContainText(/Kalium[\s\S]*Natrium/);
  await eig.getByRole("button", { name: "Feld 2 nach oben" }).click();
  await expect(eig.getByLabel("Bezeichnung 1", { exact: true })).toHaveValue("Natrium");
  await aufbau.getByRole("button", { name: /Briefkopf/ }).click();
  await expect(editor.getByTestId("block-eigenschaften").getByLabel("Linie unter dem Logo")).not.toBeChecked();
  await aufbau.getByRole("button", { name: /Titel/ }).click();
  await expect(editor.getByTestId("block-eigenschaften").getByLabel("Rechts neben dem Logo")).toBeChecked();
  await aufbau.getByRole("button", { name: /Patient/ }).click();
  await expect(editor.getByTestId("block-eigenschaften").getByRole("group", { name: "Felder" })).toContainText("Kennzahlen");

  // Block „Freigabevermerk“ ändern, Datenfeld an der Schreibmarke einsetzen
  await aufbau.getByRole("button", { name: /Freigabevermerk/ }).click();
  const eigenschaften = editor.getByTestId("block-eigenschaften");
  const text = eigenschaften.getByLabel("Text");
  // der Vermerk kommt aus einem Datenfeld: er nennt, wer freigegeben hat – und bei Freigabe außerhalb von EPM auch den Weg
  await expect(text).toHaveValue("{{Plan.Freigabevermerk}}");
  await text.fill("Rückfragen an die Stiftung, Stand ");
  await text.press("End");
  await editor.getByTestId("datenfelder").getByRole("button", { name: "Heutiges Datum einfügen" }).click();
  await expect(text).toHaveValue("Rückfragen an die Stiftung, Stand {{Heute}}");
  await expect(eigenschaften.getByTestId("angaben-im-text")).toContainText("Heutiges Datum");
  await eigenschaften.getByRole("button", { name: "Fett" }).click();
  await expect(aktionen.getByTestId("vorlage-stand")).toHaveText("Ungespeicherte Änderungen");

  // ein unbekannter Platzhalter wird vom Server abgewiesen
  await text.fill("Kontostand {{Patient.Kontostand}}");
  await expect(eigenschaften.locator(".feldchip-unbekannt")).toContainText("Patient.Kontostand");
  await aktionen.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(editor.getByTestId("vorlage-fehler")).toContainText("unbekanntes Datenfeld „Patient.Kontostand“");
  await text.fill("Rückfragen an die Stiftung, Stand {{Heute}}");

  // neuer Baustein hinter dem markierten Block
  await editor.getByTestId("bausteine").getByRole("button", { name: "+ Trennlinie" }).click();
  await expect(eigenschaften).toContainText("Trennlinie");
  await aktionen.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.getByText(`Gespeichert. In der Praxis gilt weiter Fassung ${vorher.aktiv.version}`)).toBeVisible();
  await expect(aktionen.getByTestId("vorlage-stand")).toHaveText("Gespeichert, noch nicht freigegeben");
  const entwurf = await api.get("vorlagen/infusionsplan/entwurf/");
  expect(entwurf.ist_entwurf).toBe(true);
  const hinweis = entwurf.bloecke.find((b: { id: string }) => b.id === "freigabe");
  expect([hinweis.text, hinweis.optionen.fett]).toEqual(["Rückfragen an die Stiftung, Stand {{Heute}}", true]);
  const ihr = entwurf.bloecke.findIndex((b: { id: string }) => b.id === "freigabe");
  expect(entwurf.bloecke[ihr + 1].typ).toBe("trennlinie");

  // Schritt 2: Vorschau mit Testpatient neben den Eigenschaften (PDF mit pdf.js gezeichnet)
  await editor.getByRole("group", { name: "Ansicht" }).getByRole("button", { name: "Vorschau mit Testpatient" }).click();
  const vorschau = page.getByTestId("vorlage-vorschau");
  await expect(vorschau.getByLabel("Testpatient")).not.toHaveValue("");
  await expect(vorschau.getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await expect(vorschau.getByTestId("vorschau-stand")).toContainText("Zeigt den aktuellen Stand");

  // Schritt 3: Freigeben → neue Fassung in Gebrauch, die alte bleibt erhalten
  await aktionen.getByRole("button", { name: "Freigeben", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("In der Vorschau geprüft.");
  await page.getByRole("dialog").getByRole("button", { name: "Freigeben" }).click();
  expect(vorher.naechste_fassung).toBe(vorher.aktiv.version + 1);
  await expect(page.getByText(`Fassung ${vorher.naechste_fassung} freigegeben.`)).toBeVisible();
  await expect(aktionen.getByTestId("vorlage-stand")).toHaveText(`Fassung ${vorher.naechste_fassung} ist in Gebrauch`);
  await expect(editor.getByTestId("versionen")).toContainText(`Fassung ${vorher.aktiv.version}`);
  const nachher = (await api.get("vorlagen/")).find((v: { art: string }) => v.art === "infusionsplan");
  expect([nachher.aktiv.version, nachher.entwurf]).toEqual([vorher.aktiv.version + 1, null]);
  expect(nachher.versionen.map((v: { status: string }) => v.status)).toEqual(["aktiv", ...vorher.versionen.map(() => "abgeloest")]);
  // mitgelieferte Startvorlage als Grundlage laden (z. B. nach einem Update mit neuem Aufbau)
  await editor.getByRole("button", { name: "Mitgelieferte Startvorlage laden" }).click();
  await expect(page.getByText("Mitgelieferte Startvorlage als Grundlage geladen")).toBeVisible();
  await expect(aktionen.getByTestId("vorlage-stand")).toHaveText("Ungespeicherte Änderungen");
  // Wechsel in einen anderen Bereich fragt bei ungespeicherten Änderungen nach
  page.once("dialog", (d) => { expect(d.message()).toContain("Ungespeicherte Änderungen"); void d.accept(); });
  await page.getByRole("group", { name: "Bereich" }).getByRole("button", { name: "Grenzwerte" }).click();
  await expect(page).toHaveURL(/\/admin\/vorlagen\?bereich=grenzwerte$/);
  await expect(page.getByTestId("dokumentvorlagen")).toHaveCount(0);
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

test("Vordruck Schweigepflichtentbindung: Entwurfsmodus (Wasserzeichen „ENTWURF“) aus- und wieder einschalten", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  const art = "schweigepflichtentbindung";
  const stand = (await api.get(`vorlagen/${art}/`)).entwurfsmodus;
  test.skip(!stand?.moeglich, "Vorlage wurde bereits veröffentlicht – ohne Entwurfsmodus");
  await page.goto("/admin/vorlagen/dokumente");
  await page.getByTestId("vorlagenliste").getByRole("button", { name: /^Schweigepflichtentbindung/ }).click();
  const editor = page.getByTestId("dokumentvorlagen");
  await expect(editor.getByTestId("vorlage-ungeprueft")).toBeVisible();
  await editor.getByRole("button", { name: "Entwurfsmodus ausschalten" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Ausschalten" }).click();
  await expect(page.getByText("Entwurfsmodus ausgeschaltet: Die PDFs tragen kein Wasserzeichen „ENTWURF“ mehr.")).toBeVisible();
  await expect(editor.getByTestId("entwurfsmodus-aus")).toBeVisible();
  expect((await api.get(`vorlagen/${art}/`)).entwurfsmodus).toEqual({ moeglich: true, aktiv: false, aus: true });
  // wieder einschalten (andere Tests erwarten den Entwurfshinweis)
  await editor.getByTestId("entwurfsmodus-aus").getByRole("button", { name: "Entwurfsmodus wieder einschalten" }).click();
  await expect(editor.getByTestId("vorlage-ungeprueft")).toBeVisible();
  expect((await api.get(`vorlagen/${art}/`)).entwurfsmodus.aus).toBe(false);
  await api.ende();
});

test("Vorlagen-Portal: Suche, Angabe per Klick, geführter Ablauf, frühere Fassung, Kopie als eigene Vorlage (F180)", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  const art = "terminbestaetigung";
  const vorher = await api.get(`vorlagen/${art}/`);
  const n = vorher.aktiv.version;

  // Übersicht in Alltagssprache mit Suche über alle Vorlagen, Listen und Präparate
  await page.goto("/admin/vorlagen");
  const start = page.getByTestId("vorlagen-start");
  await expect(start.getByTestId("vorlagen-kachel")).toHaveCount(8);  // seit fbdd90a mit „KI-Prompts“
  await expect(start.getByRole("link", { name: /KI-Prompts/ })).toBeVisible();
  await expect(start.getByRole("link", { name: /Briefe, Formulare und E-Mail-Texte/ })).toContainText("Wo benutzt:");
  await start.getByLabel("Was möchten Sie ändern?").fill("Terminbest");
  await start.getByTestId("vorlagen-treffer").getByRole("link", { name: /Terminbestätigung Sprechstunde/ }).click();
  await expect(page).toHaveURL(new RegExp(`/admin/vorlagen/dokumente\\?art=${art}$`));
  const editor = page.getByTestId("dokumentvorlagen");
  await expect(editor.getByTestId("vorlage-name")).toContainText("Terminbestätigung Sprechstunde");
  await expect(editor).toContainText("Schreiben und E-Mail");
  await expect(editor.getByTestId("schritte").getByRole("button", { name: /1 · Bearbeiten/ })).toHaveAttribute("aria-current", "step");
  await expect(editor.getByTestId("schritte").getByRole("button", { name: /3 · Freigeben/ })).toBeDisabled();

  // Angabe aus der Akte per Klick – ohne vorher ins Textfeld zu klicken; im Text als lesbarer Chip
  await editor.getByTestId("aufbau").getByRole("button", { name: /^Absage/ }).click();
  const eig = editor.getByTestId("block-eigenschaften");
  const text = eig.getByLabel("Text", { exact: true });
  const alt = await text.inputValue();
  const felder = editor.getByTestId("datenfelder");
  await felder.getByLabel("Angabe suchen").fill("Uhrzeit");
  await expect(felder.getByRole("button", { name: "Briefanrede („Sehr geehrte Frau …“) einfügen" })).toHaveCount(0);
  await felder.getByRole("button", { name: "Uhrzeit des Termins einfügen" }).click();
  await expect(text).toHaveValue(`${alt}{{Termin.Uhrzeit}}`);
  await expect(eig.getByTestId("angaben-im-text")).toContainText("Uhrzeit des Termins");
  await expect(page.getByTestId("vorlage-stand")).toHaveText("Ungespeicherte Änderungen");

  // Schritt 2: Live-Vorschau mit Testpatient und E-Mail-Text
  await editor.getByTestId("schritte").getByRole("button", { name: /2 · Vorschau prüfen/ }).click();
  const vorschau = editor.getByTestId("vorlage-vorschau");
  await expect(vorschau.getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await expect(vorschau.getByTestId("vorschau-email")).toBeVisible();
  // Schritt 3: Freigeben (speichert dabei)
  await editor.getByTestId("schritte").getByRole("button", { name: /3 · Freigeben/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Freigeben" }).click();
  await expect(page.getByText(`Fassung ${n + 1} freigegeben.`)).toBeVisible();
  expect((await api.get(`vorlagen/${art}/`)).aktiv.version).toBe(n + 1);

  // frühere Fassung ansehen und wiederherstellen – als Entwurf, in Gebrauch bleibt die neue
  const fassungen = editor.getByTestId("versionen");
  await fassungen.getByRole("button", { name: `Fassung ${n} ansehen` }).click();
  await expect(page.getByRole("dialog").getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Diese Fassung wiederherstellen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Wiederherstellen", exact: true }).click();
  await expect(page.getByText(`Fassung ${n} wiederhergestellt und gespeichert.`)).toBeVisible();
  await expect(page.getByTestId("vorlage-stand")).toHaveText("Gespeichert, noch nicht freigegeben");
  const entwurf = await api.get(`vorlagen/${art}/entwurf/`);
  expect([entwurf.ist_entwurf, entwurf.notiz]).toEqual([true, `wiederhergestellt aus Fassung ${n}`]);
  expect((await api.get(`vorlagen/${art}/`)).aktiv.version).toBe(n + 1);
  await editor.getByRole("button", { name: "Nicht freigegebene Änderungen verwerfen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Verwerfen" }).click();
  await expect(page.getByText(`Fassung ${n + 1} bleibt in Gebrauch.`)).toBeVisible();

  // als eigene Vorlage kopieren: startet mit demselben Text, sofort in der Akte wählbar
  const name = `Terminbestätigung Kopie ${Date.now()}`;
  await editor.getByRole("button", { name: "Als eigene Vorlage kopieren" }).click();
  await expect(page.getByRole("dialog").getByLabel("Name")).toHaveValue("Terminbestätigung Sprechstunde (Kopie)");
  await page.getByRole("dialog").getByLabel("Name").fill(name);
  await page.getByRole("dialog").getByRole("button", { name: "Kopie anlegen" }).click();
  await expect(page).toHaveURL(/\?art=eigen-/);
  await expect(page.getByTestId("vorlage-name")).toContainText(name);
  const kopie = new URL(page.url()).searchParams.get("art")!;
  expect((await api.get(`vorlagen/${kopie}/entwurf/`)).bloecke).toEqual((await api.get(`vorlagen/${art}/entwurf/`)).bloecke);
  expect((await api.get("schreiben/")).map((s: { art: string }) => s.art)).toContain(kopie);
  await api.patch(`vorlagen/${kopie}/eigen/`, { aktiv: false });
  await api.ende();
});

test("Gestaltung am Raster: ziehen, einrasten, Breite ziehen, direkt schreiben, Kopfband und DIN 5008 (14.10.2026)", async ({ page }) => {
  const api = await apiAls("mitarbeiter");
  await page.goto("/admin/vorlagen/dokumente?art=terminbestaetigung");
  const editor = page.getByTestId("dokumentvorlagen");
  const seite = editor.getByTestId("vorlage-seite");
  const eig = editor.getByTestId("block-eigenschaften");
  await expect(seite.getByTestId("raster")).toBeVisible();

  // Anschriftfeld nach DIN 5008 per Schalter: steht an der festen Stelle (Form B: 45 mm vom oberen Rand)
  await editor.getByTestId("din-schalter").check();
  const feld = seite.getByTestId("anschriftfeld");
  await expect(feld.locator(".feldchip", { hasText: "Straße" }).first()).toBeVisible();
  await expect(eig.getByRole("group", { name: "Form nach DIN 5008" })).toBeVisible();
  const blatt = await seite.locator("> div").boundingBox();
  const lage = await feld.boundingBox();
  expect(Math.round((lage!.y - blatt!.y) / (560 / 210))).toBe(45);
  await expect(seite.getByTestId("informationsblock")).toContainText("Datum");

  // Kopf als farbiges, welliges Band mit Fußband
  await editor.getByTestId("aufbau").getByRole("button", { name: /^Briefkopf/ }).click();
  await eig.getByRole("group", { name: "Gestaltung des Kopfs" }).getByRole("button", { name: "Farbiges Band" }).click();
  await eig.getByRole("group", { name: "Form des Bands" }).getByRole("button", { name: "Bogen" }).click();
  await eig.getByRole("button", { name: "Farbe des Bands #251F53" }).click();
  await eig.getByRole("button", { name: "Schriftfarbe #FFFFFF" }).click();
  await expect(seite.getByTestId("kopfband").locator("path")).toHaveAttribute("fill", "#251F53");

  // Fußzeile eigens gestalten wie die Kopfzeile: Band in eigener Farbe, Zeile „Vorstand“ per Schalter
  await seite.getByTestId("fusszeile").click();
  await eig.getByRole("group", { name: "Gestaltung der Fußzeile" }).getByRole("button", { name: "Farbiges Band" }).click();
  await eig.getByRole("group", { name: "Form des Bands" }).getByRole("button", { name: "Wellig" }).click();
  await eig.getByRole("button", { name: "Farbe des Bands #EE8D4D" }).click();
  await expect(seite.getByTestId("fussband").locator("path")).toHaveAttribute("fill", "#EE8D4D");
  await eig.getByLabel("Zeile „Vorstand“").check();
  await expect(seite.getByTestId("fusszeile").locator(".feldchip", { hasText: "Vorstand" })).toBeVisible();

  // „Einleitung“ am rechten Rand auf die halbe Breite ziehen: rastet an Spalte 3 ein
  const einleitung = seite.getByRole("button", { name: "Block Einleitung" });
  await einleitung.click();
  const griff = einleitung.getByTestId("rand-rechts");
  const g = (await griff.boundingBox())!;
  const inhalt = (await seite.getByTestId("seiteninhalt").boundingBox())!;
  await page.mouse.move(g.x + g.width / 2, g.y + g.height / 2);
  await page.mouse.down();
  await page.mouse.move(inhalt.x + inhalt.width * 0.47, g.y + 5, { steps: 8 });
  await page.mouse.up();
  await expect(eig.getByTestId("raster-wahl").getByLabel("Bis Spalte")).toHaveValue("3");

  // „Bitte mitbringen“ mit der Maus rechts neben die Einleitung ziehen: das Ziel wird angezeigt, der Block rastet ein
  const hinweis = seite.getByRole("button", { name: "Block Bitte mitbringen" });
  const h = (await hinweis.boundingBox())!;
  const e = (await einleitung.boundingBox())!;
  await page.mouse.move(h.x + 40, h.y + h.height / 2);
  await page.mouse.down();
  await page.mouse.move(inhalt.x + inhalt.width * 0.8, e.y + e.height / 2, { steps: 10 });
  await expect(seite.getByTestId("ziel-anzeige")).toBeVisible();
  await page.mouse.up();
  await expect(seite.getByTestId("nebeneinander").filter({ hasText: "Bitte" })).toBeVisible();
  await expect(eig.getByTestId("raster-wahl").getByLabel("Von Spalte")).toHaveValue("4");
  await expect(eig.getByTestId("raster-wahl").getByLabel("In derselben Zeile wie der Block davor")).toBeChecked();

  // Doppelklick: Text direkt auf der Seite schreiben, Angabe aus der Akte an der Schreibmarke
  await seite.getByRole("button", { name: "Block Absage" }).dblclick();
  const text = seite.getByLabel("Text auf der Seite");
  await text.fill("Absagen bitte bis ");
  await editor.getByTestId("datenfelder").getByRole("button", { name: "Heutiges Datum einfügen" }).click();
  await expect(text).toHaveValue("Absagen bitte bis {{Heute}}");
  await text.press("Escape");
  await expect(seite.getByRole("button", { name: "Block Absage" }).locator(".feldchip")).toHaveText("Heutiges Datum");

  // Baustein aus der Leiste auf die Seite ziehen
  const knopf = editor.getByTestId("bausteine").getByRole("button", { name: "+ Trennlinie" });
  const k = (await knopf.boundingBox())!;
  const titel = (await seite.getByRole("button", { name: "Block Titel" }).boundingBox())!;
  await page.mouse.move(k.x + k.width / 2, k.y + k.height / 2);
  await page.mouse.down();
  await page.mouse.move(titel.x + 50, titel.y + 2, { steps: 10 });
  await page.mouse.up();
  await expect(eig).toContainText("Trennlinie");

  await page.getByRole("main").getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.getByText("Gespeichert. In der Praxis gilt weiter")).toBeVisible();
  const entwurf = await api.get("vorlagen/terminbestaetigung/entwurf/");
  const nach = Object.fromEntries(entwurf.bloecke.map((b: { id: string }) => [b.id, b]));
  expect(nach.briefkopf).toMatchObject({ kopfband: "bogen", bandfarbe: "#251F53", textfarbe: "#FFFFFF" });
  expect(nach.fusszeile).toMatchObject({ band: "welle", bandfarbe: "#EE8D4D" });
  expect(nach.fusszeile.text).toContain("Vorstand: {{Absender.Vorstand}}");
  expect(nach["anschriftfeld-1"]).toMatchObject({ typ: "anschriftfeld", form: "B" });
  expect(nach.einleitung.optionen).toMatchObject({ raster_von: 1, raster_bis: 3 });
  expect(nach.hinweis.optionen).toMatchObject({ raster_von: 4, raster_bis: 6, neben_vorherigem: "raster" });
  expect(nach.absage.text).toBe("Absagen bitte bis {{Heute}}");
  const ids = entwurf.bloecke.map((b: { id: string }) => b.id);
  expect(ids.indexOf("trennlinie-1")).toBe(ids.indexOf("titel") - 1);

  // die Vorschau mit Testpatient entsteht auf dem Server aus denselben Angaben
  await editor.getByRole("button", { name: "Vorschau mit Testpatient" }).click();
  await expect(editor.getByTestId("vorschau-stand")).toContainText("Zeigt den aktuellen Stand", { timeout: 30_000 });

  // aufräumen: Entwurf verwerfen
  const r = await api.roh.delete("/api/vorlagen/terminbestaetigung/entwurf/", { headers: await api.kopf() });
  expect(r.status()).toBe(204);
  await api.ende();
});

test("E-Mail-Vorlage im eigenen Fenster bearbeiten: Angaben als Chips, Vorschau mit Testpatient (14.10.2026)", async ({ page }) => {
  await page.goto("/admin/vorlagen/dokumente?art=terminbestaetigung");
  const editor = page.getByTestId("dokumentvorlagen");
  await editor.getByTestId("email-bearbeiten").click();
  const fenster = page.getByTestId("email-fenster");
  // Platzhalter erscheinen als lesbare Chips statt {{Patient.Briefanrede}}
  const text = fenster.getByRole("textbox", { name: "Text der E-Mail" });
  await expect(text.locator(".feldchip", { hasText: "Briefanrede" })).toBeVisible();
  await expect(text).not.toContainText("{{");
  // am Ende weiterschreiben und eine Angabe an der Schreibmarke einsetzen
  await text.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.press("Enter");
  await page.keyboard.type("Stand: ");
  await fenster.getByTestId("datenfelder").getByRole("button", { name: "Heutiges Datum einfügen" }).click();
  await expect(text.locator(".feldchip", { hasText: "Heutiges Datum" })).toBeVisible();
  // von Hand getippte Platzhalter werden ebenfalls zum Chip
  await page.keyboard.type("{{Patient.Name}}");
  await expect(text.locator(".feldchip", { hasText: "Name" }).last()).toBeVisible();
  // Betreff einzeilig
  const betreff = fenster.getByRole("textbox", { name: "Betreff" });
  await betreff.click();
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  await page.keyboard.type(" (neu)");
  await expect(betreff).toContainText("(neu)");
  // Vorschau mit Testpatient: Angaben eingesetzt
  await fenster.getByRole("group", { name: "Ansicht der E-Mail" }).getByRole("button", { name: "Vorschau mit Testpatient" }).click();
  const vorschau = fenster.getByTestId("email-vorschau");
  await expect(vorschau).toContainText("(neu)", { timeout: 20_000 });
  await expect(vorschau).not.toContainText("{{");
  await page.getByRole("button", { name: "Übernehmen" }).click();
  await expect(fenster).toHaveCount(0);
  // übernommen in den Abschnitt E-Mail (reiner Text mit Platzhaltern)
  const eig = editor.getByTestId("block-eigenschaften");
  await expect(eig.getByLabel("Text", { exact: true })).toHaveValue(/\nStand: \{\{Heute\}\} \{\{Patient\.Name\}\}$/);
  await expect(eig.getByLabel("Betreff")).toHaveValue(/ \(neu\)$/);
  await expect(page.getByRole("main").getByTestId("vorlage-stand")).toHaveText("Ungespeicherte Änderungen");
});
