/**
 * Nachweis „Das Ergebnis bleibt nach einem Neustart erhalten“ – läuft als letzte Datei.
 *
 * Die übrigen Tests merken sich, was sie über die Oberfläche angelegt oder geändert haben (merken()). Hier werden
 * zusätzlich einige Einstellungen direkt vor dem Neustart in der Oberfläche geändert. Danach starten Backend und
 * Webserver neu, und alles wird erneut über die Oberfläche geprüft – gelesen aus PostgreSQL, nicht aus einem Speicher.
 */
import { expect, test } from "@playwright/test";
import type { Browser, Page } from "@playwright/test";
import { OHNE_ANMELDUNG, adminNavigation, apiAls, apiAnmelden, gemerkt, stackNeuStarten, totpBase32, virtuellerAuthenticator, zustand } from "./hilfen";
import type { Rolle } from "./hilfen";
import { laeuft } from "./teile";

test.describe.configure({ mode: "serial" });

/**
 * Geteilter CI-Lauf (e2e/teile.ts, 15.11.2026): Jeder Teil prüft nach seinem Neustart die Ergebnisse genau der Dateien,
 * die in ihm gelaufen sind – jede Prüfung steht damit in genau einem Teil. Ein Nachweis wird nur angelegt, wenn alle
 * seine Quellen in diesem Lauf sind; im Gesamtlauf (ohne EPM_E2E_TEIL) laufen alle wie bisher.
 */
type Ablauf = Parameters<typeof test>[2];
const nachweise: { quellen: string[]; titel: string; ablauf: Ablauf }[] = [];
function nachweis(quellen: string[], titel: string, ablauf: Ablauf) {
  nachweise.push({ quellen, titel, ablauf });
}

async function seiteAls(browser: Browser, wer: Rolle | { zustand: string }) {
  const ctx = await browser.newContext({ storageState: typeof wer === "string" ? zustand(wer) : wer.zustand, ignoreHTTPSErrors: true });
  return { ctx, page: await ctx.newPage() };
}

function gespeichert(page: Page, pfad: string) {
  return page.waitForResponse((a) => a.url().endsWith(`/api/${pfad}`) && a.request().method() !== "GET" && a.ok());
}

nachweis(["admin.spec.ts"], "Vor dem Neustart: Grenzwert und Rechte in der Oberfläche ändern", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "admin");
  await page.goto("/admin/vorlagen");
  await page.getByRole("button", { name: "Grenzwerte" }).click();
  await page.getByTestId("grenzwerte").getByLabel("Kontakt überfällig nach").fill("14");
  await page.getByTestId("grenzwerte").getByLabel("Kontakt bald fällig nach").fill("9");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Grenzwerte gespeichert.")).toBeVisible();

  await page.goto("/admin/benutzer");
  const rechte = page.getByTestId("rechte");
  await rechte.getByRole("button", { name: "Alle aufklappen" }).click();  // Bereiche seit 27.10.2026 zugeklappt
  await rechte.getByRole("checkbox", { name: "Betrachter: Versorger, Ansprechpartner und Ärzte pflegen" }).check();
  await rechte.getByRole("button", { name: "Speichern (1)" }).click();
  await expect(page.getByText("Rechte gespeichert. Sie gelten ab sofort.")).toBeVisible();
  await ctx.close();
});

nachweis(["konto.spec.ts"], "Vor dem Neustart: Darstellung und Startseite in der Oberfläche ändern", async ({ browser }) => {
  const d = await seiteAls(browser, gemerkt("darstellung"));
  await d.page.goto("/design");
  let antwort = gespeichert(d.page, "auth/ich/");
  await d.page.getByRole("radio", { name: "Darstellung Dunkel" }).click();
  await antwort;
  await d.page.goto("/");
  await d.page.getByRole("button", { name: "Startseite anpassen" }).click();
  antwort = gespeichert(d.page, "auth/ich/");
  await d.page.getByRole("button", { name: "Zuletzt eingetragen ausblenden" }).click();
  await antwort;
  antwort = gespeichert(d.page, "auth/ich/");
  await d.page.getByRole("group", { name: "Größe Auffällige Gewichte" }).getByRole("button", { name: "2×2" }).click();
  await antwort;
  await d.page.getByRole("button", { name: "Fertig" }).click();
  await expect(d.page.getByRole("heading", { name: "Zuletzt eingetragen" })).toHaveCount(0);
  // Karten der Akte im Raster (Fehlerliste 02.10.2026, 2; bei 1440 px 3 Spalten): Gewichtsverlauf über „⋯“ auf ganze Breite
  await d.page.goto("/patienten");
  await d.page.getByTestId("patientenliste").getByRole("link", { name: "Probe, Jonas" }).click();
  antwort = gespeichert(d.page, "auth/ich/");
  await d.page.getByTestId("groesse-gewicht").click();
  await d.page.getByRole("menuitem", { name: /^Breite: 3 Spalten/ }).click();
  await antwort;
  await expect(d.page.getByTestId("uebersicht-stufe").locator('[data-bereich="gewicht"]')).toHaveAttribute("data-breite", "3");
  await d.ctx.close();
});


nachweis(["akte.spec.ts"], "Nach dem Neustart: Akten mit Gewicht, Diagnose und Versionen, Kontakten, Termin, Abschluss und Verlauf", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "mitarbeiter");

  await page.goto(`/patienten/${gemerkt("gewicht").id}`);
  await expect(page.getByTestId("gewichtskarte").getByTestId("aktuelles-gewicht")).toHaveText("60,6 kg");

  await page.goto(`/patienten/${gemerkt("diagnose").id}/diagnosen`);
  const diagnose = page.getByTestId("karte-diagnose");
  await expect(diagnose.locator(".richtext strong")).toHaveText("Typ II");
  await expect(diagnose).toContainText("Fassung 2");
  await page.goto(`/patienten/${gemerkt("diagnose").id}/therapie`);
  await expect(page.getByTestId("karte-therapie")).toContainText("HPE 5×/Woche über Port");
  await expect(page.getByTestId("karte-therapie")).toContainText("geändert");

  const kontakte = gemerkt("kontakte").id;
  await page.goto(`/patienten/${kontakte}/kontakte`);
  const liste = page.getByTestId("kontaktliste");
  await expect(liste.getByRole("listitem").filter({ hasText: "Lieferung" })).toContainText("Grund: falscher Patient");
  await expect(liste.getByRole("listitem").filter({ hasText: "Appetit schlechter" })).toContainText("Rückruf");
  await page.goto(`/patienten/${kontakte}`);
  await expect(page.getByTestId("aktentermine")).toContainText("Rückruf Trinkmenge");

  const abschluss = gemerkt("abschluss").id;
  await page.goto(`/patienten/${abschluss}`);
  await expect(page.getByTestId("stammdaten")).toContainText("0251 98765");
  await expect(page.getByTestId("gewichtskarte").getByRole("button", { name: "Gewicht", exact: true })).toBeVisible(); // wieder geöffnet
  await page.goto(`/patienten/${abschluss}/verlauf`);
  const verlauf = page.getByTestId("verlauf");
  await expect(verlauf).toContainText("abgeschlossen");
  await expect(verlauf).toContainText("wieder geöffnet");
  await page.goto(`/patienten/${abschluss}`);
  await expect(page.getByTestId("kennzahlen")).toContainText("kein");  // Katheter und Versorger bewusst „kein“

  // Ärzte und Bezugspersonen
  const kd = gemerkt("kontaktdaten");
  await page.goto(`/patienten/${kd.patient}`);
  await expect(page.getByTestId("aerzte")).toContainText(kd.arzt);
  await expect(page.getByTestId("aerzte")).toContainText("0251 99999");
  await expect(page.getByTestId("bezugspersonen").getByTestId("bezugsperson")).toHaveCount(1);
  await expect(page.getByTestId("bezugspersonen")).toContainText("Bernd Betreuer");
  await expect(page.getByTestId("auskunft")).toContainText("niemand eingetragen");
  await ctx.close();
});

nachweis(["patienten.spec.ts"], "Nach dem Neustart: neuer Patient", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "mitarbeiter");
  const neu = gemerkt("neuer_patient");
  await page.goto(`/patienten?suche=${encodeURIComponent(neu.nachname)}`);
  await page.getByTestId("patientenliste").getByRole("link", { name: neu.name }).click();
  await expect(page.getByTestId("aktuelles-gewicht")).toHaveText("61,4 kg");
  await expect(page.getByTestId("kennzahlen")).toContainText("Port");
  await ctx.close();
});

nachweis(["plaene.spec.ts"], "Nach dem Neustart: Infusionsplan mit gespeicherter PDF", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "mitarbeiter");
  await page.goto(`/patienten/${gemerkt("plan").patient}/plaene`);
  await expect(page.getByTestId("planliste").getByRole("listitem")).toHaveCount(1);
  await expect(page.getByTestId("planliste")).toContainText("aktuell gültig");
  // Ansicht in der Akte = gespeicherte PDF der Freigabe, nach dem Neustart unverändert
  await expect(page.getByTestId("ansicht-herkunft")).toContainText("Gespeicherte PDF der Freigabe · Prüfsumme stimmt");
  const blatt = page.getByTestId("plan-ansicht").getByTestId("pdf-text").first();
  await expect(blatt).toContainText(/Aminosäuren\s+80\s+g\s+Glamin 13,4 %/);
  await expect(blatt).toContainText(/Volumen\s+2\.100\s+500\s+2\.600\s+ml/);
  await expect(blatt).toContainText(/Laufmenge je Stunde\s+216,7\s+ml\/h/);
  await expect(blatt).toContainText("Pantozol® Kurzinfusion 1 Amp. 40 mg in 50 ml Trägerlösung · 1-0-1");
  // gespeicherte PDF: nach dem Neustart unverändert (Prüfsumme)
  await page.getByTestId("plan-detail").getByRole("button", { name: "PDF öffnen" }).click();
  await expect(page.getByRole("dialog").getByTestId("pdf-pruefung")).toContainText("Prüfsumme stimmt");
  await expect(page.getByRole("dialog").getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await ctx.close();
});

nachweis(["dokumentvorlagen.spec.ts"], "Nach dem Neustart: veröffentlichte Dokumentvorlage", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "mitarbeiter");
  await page.goto("/admin/vorlagen/dokumente?art=infusionsplan");
  await expect(page.getByTestId("vorlage-stand")).toHaveText(`Fassung ${gemerkt("vorlage").version} ist in Gebrauch`);
  await page.getByTestId("aufbau").getByRole("button", { name: /Freigabevermerk/ }).click();
  await expect(page.getByTestId("block-eigenschaften").getByLabel("Text")).toHaveValue("Rückfragen an die Stiftung, Stand {{Heute}}");
  await ctx.close();
});

nachweis(["dokumente.spec.ts"], "Nach dem Neustart: Dokumente und Altdokument", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "mitarbeiter");
  const dok = gemerkt("dokumente").id;
  await page.goto(`/patienten/${dok}/dokumente`);
  const doks = page.getByTestId("dokumentliste");
  await expect(doks.getByRole("row").filter({ hasText: "Arztbrief Klinikum Nord" })).toContainText("15.09.2026");
  await expect(doks.getByRole("button", { name: "Port-Foto" })).toHaveCount(0);
  await page.getByLabel("Ausgeblendete anzeigen").check();
  await expect(doks.getByRole("button", { name: "Port-Foto" })).toBeVisible();
  const api = await apiAls("mitarbeiter");
  const brief = (await api.get(`dokumente/?patient=${dok}`)).results.find((d: { titel: string }) => d.titel === "Arztbrief Klinikum Nord");
  await api.ende();
  const datei = await page.request.get(`/api/dokumente/${brief.id}/datei/`);
  expect(await datei.text()).toBe("Arztbrief (E2E)\nAlles gut.\n");

  await page.goto(`/patienten/${gemerkt("altdokument").patient}/dokumente`);
  const alt = page.getByTestId("dokumentliste").getByRole("row").filter({ hasText: "Altdokument aus dem bisherigen System" });
  await expect(alt).toContainText("Labor");
  await expect(alt).not.toContainText("Typ prüfen");
  await ctx.close();
});

nachweis(["dokumente-falsch.spec.ts"], "Nach dem Neustart: endgültig gelöschtes Dokument bleibt weg, Audit-Log ohne Titel", async ({ browser }) => {
  // endgültig gelöschtes Dokument (Art. 17 DSGVO): bleibt nach dem Neustart weg, Verlauf nur mit dem Nachweis
  const { ctx, page } = await seiteAls(browser, "mitarbeiter");
  const weg = gemerkt("geloescht");
  await page.goto(`/patienten/${weg.patient}/dokumente`);
  await expect(page.getByText("Noch keine Dokumente.")).toBeVisible();
  await page.goto(`/patienten/${weg.patient}/verlauf`);
  await expect(page.getByTestId("verlauf")).toContainText("Datei und Inhalt entfernt");
  await expect(page.getByTestId("verlauf")).not.toContainText(weg.titel);
  await ctx.close();

  const a = await seiteAls(browser, "admin");
  await (await adminNavigation(a.page)).getByRole("link", { name: "Audit-Log" }).click();
  await a.page.getByRole("button", { name: "Dokument", exact: true }).click();
  await expect(a.page.getByTestId("auditlog")).toContainText("endgültig gelöscht – Datei, Titel und Inhalt entfernt (Art. 17 DSGVO)");
  await expect(a.page.getByTestId("auditlog")).not.toContainText(weg.titel);
  await a.ctx.close();
});

nachweis(["datenschutz.spec.ts"], "Nach dem Neustart: Datenschutz – Erklärungen, eingeschränkte und gelöschte Akte, Plan nach Freigabe", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "mediziner");
  await page.goto(`/patienten/${gemerkt("erklaerung").patient}/datenschutz`);
  await expect(page.getByTestId("erklaerung-einwilligung")).toContainText("widerrufen am");
  await expect(page.getByTestId("erklaerung-datenschutzinformation")).toContainText("liegt vor seit");
  await expect(page.getByTestId("erklaerungen-fehlen")).toHaveText("Einwilligung fehlt");

  // eingeschränkte Akte: weiter verschlossen, ohne Namen
  const zu = gemerkt("eingeschraenkt");
  await page.goto(`/patienten/${zu.patient}`);
  await expect(page.getByTestId("akte-eingeschraenkt")).toContainText("Verarbeitung eingeschränkt");
  await expect(page.getByTestId("akte-eingeschraenkt")).not.toContainText(zu.nachname);

  // endgültig gelöschte Akte: bleibt weg (beim Start prüft das Backend die Löschliste), das Löschprotokoll bleibt
  const weg = gemerkt("akte_geloescht");
  expect((await page.request.get(`/api/patienten/${weg.id}/`)).status()).toBe(404);
  await page.goto("/datenschutz");
  await expect(page.getByTestId("loeschprotokoll")).toContainText(`Nr. ${String(weg.nummer).padStart(4, "0")}`);
  await expect(page.getByTestId("eingeschraenkte")).toContainText(zu.nachname);
  await expect(page.getByRole("main")).not.toContainText(weg.nachname);
  await expect(page.getByTestId("datenschutz-einstellungen")).toContainText("Audit-Log 30 Jahre");

  // Plan, den ein Mitarbeiter nach der Freigabe per E-Mail abgeschlossen hat
  await page.goto(`/patienten/${gemerkt("plan_abgeschlossen").patient}/plaene`);
  await expect(page.getByTestId("plan-detail")).toContainText("(per E-Mail); im System abgeschlossen am");
  await expect(page.getByTestId("ansicht-herkunft")).toContainText("Prüfsumme stimmt");
  await ctx.close();
});

nachweis(["admin.spec.ts"], "Nach dem Neustart: Benutzer, Sperre, Audit-Log, Vorlagen, Grenzwert und Rechte", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "admin");

  const { name, anzeige } = gemerkt("benutzer");
  await page.goto("/admin/benutzer");
  const benutzer = page.getByTestId("benutzerliste");
  await expect(benutzer.getByRole("row").filter({ hasText: name })).toContainText("Mitarbeiter");
  await benutzer.getByRole("button", { name: anzeige, exact: true }).click();
  await expect(page.getByTestId("benutzer-detail").getByLabel("Funktion")).toHaveValue("Oberärztin");
  const { benutzername } = gemerkt("gesperrt");
  const entsperrt = benutzer.getByRole("row").filter({ hasText: benutzername });
  await expect(entsperrt).toContainText("2FA: nicht eingerichtet");
  await expect(entsperrt).not.toContainText("gesperrt");

  // Rechte: Änderung von vor dem Neustart gilt, auch für den Betrachter
  const rechte = page.getByTestId("rechte");
  await rechte.getByRole("button", { name: "Alle aufklappen" }).click();  // Bereiche seit 27.10.2026 zugeklappt
  await expect(rechte.getByRole("checkbox", { name: "Betrachter: Versorger, Ansprechpartner und Ärzte pflegen" })).toBeChecked();
  const b = await seiteAls(browser, "betrachter");
  await b.page.goto("/versorger");
  await expect(b.page.getByRole("button", { name: "Neuer Versorger" })).toBeVisible();
  await b.ctx.close();
  await rechte.getByRole("button", { name: "Standard" }).click();
  await rechte.getByRole("button", { name: /^Speichern \(\d+\)$/ }).click();
  await expect(page.getByText("Rechte gespeichert. Sie gelten ab sofort.")).toBeVisible();

  await (await adminNavigation(page)).getByRole("link", { name: "Audit-Log" }).click();
  await page.getByRole("button", { name: "Benutzer", exact: true }).click();
  await expect(page.getByTestId("auditlog")).toContainText(name);

  const { ort, vitamin } = gemerkt("vorlagen");
  await page.goto("/admin/vorlagen?bereich=briefkopf");
  await expect(page.getByTestId("logo")).toContainText("öffnen");
  await page.getByRole("button", { name: "Auswahllisten" }).click();
  const listen = page.getByRole("navigation", { name: "Listen" });
  const liste = page.getByTestId("liste");
  await listen.getByRole("button", { name: /^Terminorte/ }).click();
  await expect(liste.getByRole("row").filter({ hasText: ort })).toContainText("ausgeblendet");
  await listen.getByRole("button", { name: /^Vitamine/ }).click();
  await expect(liste.getByRole("row").filter({ hasText: vitamin })).toContainText("ausgeblendet");

  await page.getByRole("button", { name: "Grenzwerte" }).click();
  const grenzen = page.getByTestId("grenzwerte");
  await expect(grenzen.getByLabel("Kontakt überfällig nach")).toHaveValue("14");
  await expect(grenzen.getByLabel("Kontakt bald fällig nach")).toHaveValue("9");
  await grenzen.getByLabel("Kontakt bald fällig nach").fill("4");
  await grenzen.getByLabel("Kontakt überfällig nach").fill("6");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Grenzwerte gespeichert.")).toBeVisible();
  await ctx.close();
});

nachweis(["konto.spec.ts"], "Nach dem Neustart: Konto mit neuem Passwort und Gerät, Notfall-Codes, Darstellung, Startseite", async ({ browser }) => {
  const k = gemerkt("konto");
  const anmeldung = await apiAnmelden(k.benutzername, k.kennwort, totpBase32(k.geheim));
  expect(anmeldung.schritt).toBe("fertig");
  const ctx = await browser.newContext({ storageState: await anmeldung.ctx.storageState(), ignoreHTTPSErrors: true });
  await anmeldung.ctx.dispose();
  const page = await ctx.newPage();
  await page.goto("/konto");
  await expect(page.getByTestId("sicherheit")).toContainText("10 von 10 übrig");
  await ctx.close();

  const d = await seiteAls(browser, gemerkt("darstellung"));
  await d.page.goto("/");
  await expect(d.page.locator("html")).toHaveAttribute("data-schema", "dunkel");
  await expect(d.page.getByRole("heading", { name: "Auffällige Gewichte" })).toBeVisible();
  await expect(d.page.getByRole("heading", { name: "Zuletzt eingetragen" })).toHaveCount(0);
  await expect(d.page.locator('[data-kachel="gewicht"]')).toHaveAttribute("data-groesse", "2x2");
  await d.page.goto("/patienten");
  await d.page.getByTestId("patientenliste").getByRole("link", { name: "Probe, Jonas" }).click();
  await expect(d.page.getByTestId("uebersicht-stufe").locator('[data-bereich="gewicht"]')).toHaveAttribute("data-breite", "3");
  await d.ctx.close();
});

nachweis(["kalender.spec.ts"], "Nach dem Neustart: Termin im Kalender (erledigt)", async ({ browser }) => {
  const k = gemerkt("kalender");
  const m = await seiteAls(browser, "mitarbeiter");
  await m.page.goto(`/kalender?datum=${k.datum}`);
  await expect(m.page.getByTestId(`tag-${k.datum}`).getByRole("button", { name: new RegExp(`${k.titel} \\(erledigt\\)`) })).toBeVisible();
  await m.ctx.close();
});

nachweis(["system.spec.ts"], "Nach dem Neustart: Tätigkeiten der Systemverwaltung", async ({ browser }) => {
  const s = gemerkt("system");
  const a = await seiteAls(browser, "admin");
  await a.page.goto("/admin/system?reiter=verlauf");
  const zeilen = a.page.getByTestId("auftraege");
  await expect(zeilen.getByRole("row", { name: new RegExp(s.taetigkeit) }).first()).toContainText("erledigt");
  await expect(zeilen.getByRole("row", { name: /Server neu starten/ }).first()).toContainText("erledigt");
  await expect(zeilen.getByRole("row", { name: /Unveränderlichkeit prüfen/ }).first()).toContainText("erledigt");
  await a.ctx.close();
});

nachweis(["aa-import.spec.ts", "patienten.spec.ts"], "Nach dem Neustart: Import – Dump, Zuordnungen und Läufe der Altdaten-Übernahme", async ({ browser }) => {
  const { dump } = gemerkt("import");
  const a = await seiteAls(browser, "admin");
  await a.page.goto("/admin/import");
  await expect(a.page.getByTestId("import-status")).toHaveText("Dump geladen");
  await expect(a.page.getByTestId("dump-name")).toContainText(dump);
  await expect(a.page.getByTestId("dump-tabellen")).toContainText("patienten (7)");
  // inzwischen haben die anderen Tests echte Akten angelegt: Zuordnungen lassen sich weiter pflegen, übernommen wird nicht
  await expect(a.page.getByTestId("echte-akten")).toContainText("Übernommen wird nur in ein System ohne echte Akten");
  await a.page.goto("/admin/import?schritt=zuordnungen");
  await expect(a.page.getByTestId("offene-punkte")).toContainText("Alle Zuordnungen sind vollständig");
  const bereiche = a.page.getByRole("group", { name: "Bereich der Zuordnungen" });
  await bereiche.getByRole("button", { name: "Katheter und Werte" }).click();
  await expect(a.page.getByTestId("nickel-vielleicht").getByLabel("Nickelallergie im EPM für vielleicht")).toHaveValue("unbekannt");
  await bereiche.getByRole("button", { name: "Benutzer" }).click();
  await expect(a.page.getByTestId("benutzer-a.muster").getByLabel("Vorname für a.muster")).toHaveValue("Anton");
  await bereiche.getByRole("button", { name: "Gelöschte Patienten" }).click();
  await expect(a.page.getByTestId("geloescht-4").getByLabel("Anlass für Patient 4")).toHaveValue("therapie_beendet");
  await a.page.goto("/admin/import?schritt=import");
  await expect(a.page.getByTestId("hindernisse")).toContainText("echte Akten");
  await expect(a.page.getByRole("button", { name: "Altdaten übernehmen …" })).toBeDisabled();
  await a.page.goto("/admin/import?schritt=protokolle");
  const laeufe = a.page.getByTestId("laeufe");
  for (const art of ["Probelauf", "Dokumente übernommen", "Import zurückgenommen"]) {
    await expect(laeufe.getByTestId("lauf").filter({ hasText: art }).first()).toContainText("erfolgreich");
  }
  await a.ctx.close();
});

nachweis(["passkey.spec.ts"], "Nach dem Neustart: mit Passkey anmelden und mit Passkey bestätigen (Passkey entfernen)", async ({ browser }) => {
  const k = gemerkt("passkey");
  const ctx = await browser.newContext({ storageState: OHNE_ANMELDUNG, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const { cdp, authenticatorId } = await virtuellerAuthenticator(ctx, page);
  await cdp.send("WebAuthn.addCredential", { authenticatorId, credential: k.credential });
  await page.goto("/");
  await page.getByLabel("Benutzername").fill(k.benutzername);
  await page.getByLabel("Passwort").fill(k.kennwort);
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.getByTestId("passkey-anmelden").click();
  await expect(page.getByTestId("angemeldet-als")).toHaveText("P. Neustart");
  await page.goto("/konto");
  const eintrag = page.getByTestId("passkey-eintrag");
  await expect(eintrag).toContainText("Telefon");
  await eintrag.getByRole("button", { name: "Telefon entfernen" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Dein Passwort").fill(k.kennwort);
  await dialog.getByTestId("passkey-bestaetigen").click();
  await dialog.getByRole("button", { name: "Entfernen" }).click();
  await expect(page.getByText("Passkey „Telefon“ entfernt.")).toBeVisible();
  await expect(page.getByTestId("passkeys")).toContainText("keiner");
  await ctx.close();
});

// Reihenfolge: Änderungen vor dem Neustart, Neustart, Prüfungen danach – nur mit den Nachweisen dieses Laufs
const aktiv = nachweise.filter((n) => n.quellen.every(laeuft));
for (const n of aktiv.filter((n) => n.titel.startsWith("Vor dem Neustart"))) test(n.titel, n.ablauf);
if (aktiv.length) {
  test("Neustart von Backend und Webserver", () => {
    stackNeuStarten();
  });
}
for (const n of aktiv.filter((n) => !n.titel.startsWith("Vor dem Neustart"))) test(n.titel, n.ablauf);
