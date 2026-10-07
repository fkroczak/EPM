/** Datenschutz (DSGVO) in der Oberfläche: Erklärungen nachhalten, Anfragen mit Frist, Kopie der Akte, Verarbeitung
 *  einschränken und Einsicht, Akte endgültig löschen, Plan nach Freigabe außerhalb von EPM abschließen. */
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import type { Browser } from "@playwright/test";
import { apiAls, eindeutig, einfachePdf, merken, neuesKonto, stackNeuStarten, totpBase32, zustand } from "./hilfen";
import type { Rolle } from "./hilfen";

async function seiteAls(browser: Browser, wer: Rolle | { zustand: string }) {
  const ctx = await browser.newContext({ storageState: typeof wer === "string" ? zustand(wer) : wer.zustand, ignoreHTTPSErrors: true });
  return { ctx, page: await ctx.newPage() };
}

function heute() {
  return new Date().toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" });
}

test("Erklärungen nachhalten: Hinweis im Aktenkopf, Vordruck als PDF, erfassen mit Scan, Widerruf", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "mitarbeiter");
  const api = await apiAls("mitarbeiter");
  const p = await api.post("patienten/", { nachname: eindeutig("Erklaer"), vorname: "Edda", geburtsdatum: "1969-09-09" });
  await page.goto(`/patienten/${p.id}`);
  // wie bei der Nickelallergie: fehlt etwas, steht es im Kopf der Akte
  await expect(page.getByTestId("erklaerungen-fehlen")).toHaveText("3 Erklärungen fehlen");
  await page.getByTestId("erklaerungen-fehlen").click();
  await expect(page).toHaveURL(/\/datenschutz$/);
  const zeile = (art: string) => page.getByTestId(`erklaerung-${art}`);
  await expect(zeile("einwilligung")).toContainText("nicht erfasst");
  // die mitgelieferten Vordrucke sind Entwürfe
  await expect(page.getByTestId("vorlage-entwurf")).toContainText("Wasserzeichen „ENTWURF“");

  // Vordruck für diesen Patienten als PDF
  await zeile("einwilligung").getByRole("button", { name: "Vordruck als PDF" }).click();
  const pdf = page.getByRole("dialog");
  await expect(pdf.getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await expect(pdf.getByTestId("pdf-text").first()).toContainText("Einwilligung in die Verarbeitung meiner Daten");
  await expect(pdf.getByTestId("pdf-text").first()).toContainText(`${p.nachname}, Edda`);
  await page.keyboard.press("Escape");

  // erfassen: Einwilligung mit Scan, die beiden anderen ohne
  await zeile("einwilligung").getByRole("button", { name: "Erfassen" }).click();
  let dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Unterschrieben am")).toHaveValue(heute());
  await dialog.getByLabel("Unterschriebenes Blatt").setInputFiles({ name: "Einwilligung.pdf", mimeType: "application/pdf",
    buffer: einfachePdf(["Einwilligung unterschrieben (E2E)"]) });
  await dialog.getByLabel("Notiz").fill("Original im Ordner");
  await dialog.getByRole("button", { name: "Erfassen" }).click();
  await expect(zeile("einwilligung")).toContainText(`liegt vor seit ${heute()}`);
  await expect(zeile("einwilligung")).toContainText("Scan unter „Dokumente“");
  for (const art of ["datenschutzinformation", "schweigepflichtentbindung"]) {
    await zeile(art).getByRole("button", { name: "Erfassen" }).click();
    dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Erfassen" }).click();
    await expect(zeile(art)).toContainText("liegt vor seit");
  }
  await expect(page.getByTestId("erklaerungen-fehlen")).toHaveCount(0);

  // Widerruf: wirkt für die Zukunft, bleibt sichtbar; der Kopf zeigt wieder, dass etwas fehlt
  await zeile("einwilligung").getByRole("button", { name: "Widerruf eintragen" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Notiz").fill("telefonisch");
  await dialog.getByRole("button", { name: "Widerruf eintragen" }).click();
  await expect(zeile("einwilligung")).toContainText(`widerrufen am ${heute()}`);
  await expect(page.getByTestId("erklaerungen-fehlen")).toHaveText("Einwilligung fehlt");

  // der Scan liegt als Dokument in der Akte; der Verlauf hält alles fest
  await page.goto(`/patienten/${p.id}/dokumente`);
  await expect(page.getByTestId("dokumentliste").getByRole("listitem").filter({ hasText: "Einwilligung in die Datenverarbeitung (unterschrieben)" }))
    .toContainText("Einwilligung/Datenschutz");
  await page.goto(`/patienten/${p.id}/verlauf`);
  await page.getByRole("button", { name: "Erklärungen" }).click();
  await expect(page.getByTestId("verlauf").getByRole("row").filter({ hasText: "widerrufen am" })).toHaveCount(1);
  await expect(page.getByTestId("verlauf").getByRole("row").filter({ hasText: "angelegt" })).toHaveCount(3);

  // Mitarbeiter erfassen, löschen können sie nicht
  await page.goto(`/patienten/${p.id}/datenschutz`);
  await expect(page.getByTestId("aufbewahrung")).toBeVisible();
  await expect(page.getByTestId("loeschen-bereich")).toHaveCount(0);
  // Startseite: „Nach und nach prüfen“ führt zu den Akten, in denen etwas fehlt
  await page.goto("/");
  await expect(page.getByTestId("pruefen-erklaerungen")).not.toHaveText("0");
  await page.getByTestId("pruefen-erklaerungen").click();
  await expect(page.getByTestId("patientenliste")).toContainText(p.nachname);
  await api.ende();
  merken("erklaerung", { patient: p.id });
  await ctx.close();
});

test("Anfrage mit Frist, Kopie der Akte, Löschwunsch → eingeschränkt, Einsicht mit Grund, Aufheben", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "mediziner");
  const api = await apiAls("mediziner");
  const p = await api.post("patienten/", { nachname: eindeutig("Schutz"), vorname: "Sina", geburtsdatum: "1966-06-06" });
  await api.post("kontakte/", { patient: p.id, text: "<p>Bittet um eine Kopie ihrer Akte</p>" });
  await page.goto(`/patienten/${p.id}/datenschutz`);
  const anfragen = page.getByTestId("anfragen");
  await anfragen.getByRole("button", { name: "Anfrage erfassen" }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Gestellt von").fill("Patientin selbst");
  await dialog.getByLabel("Inhalt der Anfrage").fill("Bittet um eine Kopie ihrer Akte");
  await dialog.getByRole("button", { name: "Erfassen" }).click();
  await expect(anfragen.getByTestId("anfragen-liste")).toContainText("offen bis");
  await expect(page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /Datenschutz/ })).toContainText("1");

  // Kopie der Akte als ZIP: Akte und Verlauf als PDF, Hinweisdatei
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("kopie").click()]);
  expect(download.suggestedFilename()).toMatch(/^Aktenkopie-\d+-\d{4}-\d{2}-\d{2}\.zip$/);
  const zip = readFileSync((await download.path())!);
  expect(zip.subarray(0, 2).toString()).toBe("PK");
  for (const name of [`Akte-${p.nummer}.pdf`, `Verlauf-${p.nummer}.pdf`, "LIESMICH.txt"]) expect(zip.includes(name)).toBe(true);
  await page.reload();
  await expect(page.getByTestId("kopien")).toContainText("Bisher erstellt");

  await anfragen.getByRole("button", { name: "Erledigen" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Der Person mitgeteilt am").fill(heute());
  await dialog.getByRole("button", { name: "Erledigen" }).click();
  await expect(page.getByText("Anfrage erledigt.")).toBeVisible();
  await expect(anfragen.getByTestId("anfragen-liste")).toContainText(`erfüllt · mitgeteilt am ${heute()}`);

  // Akte abgeschlossen, die Patientin wünscht die Löschung – die Akte ist aber noch aufzubewahren: einschränken
  await api.post(`patienten/${p.id}/abschliessen/`, { anlass: "therapie_beendet" });
  await api.post("datenschutzanfragen/", { patient: p.id, art: "loeschung", gestellt_von: "Patientin selbst" });
  await page.reload();
  await expect(page.getByTestId("aufbewahrung-stand")).toContainText("Aufbewahrung 10 Jahre");
  await anfragen.getByRole("button", { name: "Erledigen" }).click();
  dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Ergebnis")).toHaveValue("eingeschraenkt");
  await dialog.getByLabel(/Begründung/).fill("Die Akte ist noch aufzubewahren (E2E)");
  await dialog.getByRole("button", { name: "Erledigen" }).click();
  // ab jetzt ist die Akte verschlossen – auch für die Person, die eingeschränkt hat
  const verschlossen = page.getByTestId("akte-eingeschraenkt");
  await expect(verschlossen).toContainText("Verarbeitung eingeschränkt");
  await expect(verschlossen).not.toContainText(p.nachname);
  await page.goto(`/patienten?status=abgeschlossen&suche=${encodeURIComponent(p.nachname)}`);
  await expect(page.getByTestId("patientenliste")).not.toContainText(p.nachname);

  // Wer keine Einsicht nehmen dürfte (Mitarbeiter), sieht in der Übersicht nur die Nummer – keinen Namen, keinen Grund
  {
    const zweit = await seiteAls(browser, "mitarbeiter");
    await zweit.page.goto("/datenschutz");
    const zeile = zweit.page.getByTestId("eingeschraenkte").getByRole("row").filter({ hasText: `Nr. ${String(p.nummer).padStart(4, "0")}` });
    await expect(zeile).toContainText("Akte");
    await expect(zweit.page.getByRole("main")).not.toContainText(p.nachname);
    await expect(zweit.page.getByRole("main")).not.toContainText("Die Akte ist noch aufzubewahren (E2E)");
    await zweit.ctx.close();
  }

  // Übersicht Datenschutz: dort steht die Akte; Einsicht nur mit Grund
  await page.getByRole("navigation", { name: "Hauptnavigation" }).getByRole("link", { name: "Datenschutz" }).click();
  await page.getByTestId("eingeschraenkte").getByRole("row").filter({ hasText: p.nachname }).getByRole("link").click();
  await expect(verschlossen.getByRole("button", { name: "Einsicht nehmen" })).toBeDisabled();
  await verschlossen.getByLabel("Grund der Einsicht").fill("Rückfrage des Hausarztes zur Therapie (E2E)");
  await verschlossen.getByRole("button", { name: "Einsicht nehmen" }).click();
  await expect(page.getByTestId("aktenkopf")).toContainText(p.nachname);
  await expect(page.getByTestId("aktenkopf")).toContainText("Verarbeitung eingeschränkt");

  // Aufheben: vorher wird die betroffene Person unterrichtet
  await page.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: /Datenschutz/ }).click();
  await page.getByTestId("aufbewahrung").getByRole("button", { name: "Einschränkung aufheben" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Grund").fill("Patientin wünscht die weitere Betreuung (E2E)");
  await dialog.getByRole("button", { name: "Aufheben" }).click();
  await expect(dialog).toContainText("Art. 18 Abs. 3 DSGVO");
  await dialog.getByLabel("Person unterrichtet am").fill(heute());
  await dialog.getByRole("button", { name: "Aufheben" }).click();
  await expect(page.getByText("Einschränkung aufgehoben.")).toBeVisible();
  await expect(page.getByTestId("aktenkopf")).not.toContainText("Verarbeitung eingeschränkt");

  // alles steht im Audit-Log
  await page.goto("/admin/audit-log");
  await page.getByRole("button", { name: "Datenschutz", exact: true }).click();
  const log = page.getByTestId("auditlog");
  await expect(log).toContainText(`Einsicht in eingeschränkte Akte: Akte ${p.nachname}, Sina`);
  await expect(log).toContainText("Grund: Rückfrage des Hausarztes zur Therapie (E2E)");
  await expect(log).toContainText("Einschränkung aufgehoben");

  // für den Nachweis nach dem Neustart bleibt die Akte eingeschränkt
  await api.post(`patienten/${p.id}/einschraenken/`, { grund: "Antrag der Patientin, Akte ist aufzubewahren (E2E)" });
  await api.ende();
  merken("eingeschraenkt", { patient: p.id, nachname: p.nachname, nummer: p.nummer });
  await ctx.close();
});

test("Akte endgültig löschen: nur Mediziner, mit Kennwort, Authenticator-Code und Bestätigungscode", async ({ browser }) => {
  const konto = await neuesKonto("mediziner", "Lars", "Loescher");
  const { ctx, page } = await seiteAls(browser, konto);
  const api = await apiAls("mediziner");
  const p = await api.post("patienten/", { nachname: eindeutig("Weg"), vorname: "Wanda", geburtsdatum: "1950-03-03" });
  await api.post("kontakte/", { patient: p.id, text: "<p>Letzter Kontakt (E2E)</p>" });
  await api.post(`patienten/${p.id}/abschliessen/`, { anlass: "betreuung_gewechselt" });
  await page.goto(`/patienten/${p.id}/datenschutz`);
  const bereich = page.getByTestId("loeschen-bereich");
  // die Aufbewahrungsfrist läuft: ohne Antrag der Patientin kein Löschen
  await expect(bereich).toContainText("Die Aufbewahrungsfrist läuft bis");
  await expect(bereich.getByRole("button")).toHaveCount(0);
  await api.post("datenschutzanfragen/", { patient: p.id, art: "loeschung", gestellt_von: "Patientin" });
  await page.reload();
  await expect(bereich).toContainText("Art. 17 Abs. 3 DSGVO");
  await bereich.getByRole("button", { name: /Akte endgültig löschen/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByTestId("bestaetigungscode")).not.toHaveText("······");
  const code = (await dialog.getByTestId("bestaetigungscode").textContent())!.trim();
  await expect(dialog.getByTestId("loesch-umfang")).toContainText("1 Kontakte");
  await dialog.getByLabel("Grund").fill("Antrag der Patientin, keine Aufbewahrungspflicht (E2E)");
  await dialog.getByLabel("Kennwort").fill("falsches-Kennwort");
  await dialog.getByLabel("Code aus der Authenticator-App").fill(totpBase32(konto.geheim, Date.now() + 30_000));
  await dialog.getByLabel("Code abtippen").fill(code.toLowerCase());
  await dialog.getByRole("button", { name: "Akte endgültig löschen" }).click();
  await expect(dialog).toContainText("Kennwort falsch.");
  await dialog.getByLabel("Kennwort").fill(konto.kennwort);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(totpBase32(konto.geheim, Date.now() + 30_000));
  await dialog.getByRole("button", { name: "Akte endgültig löschen" }).click();
  await expect(page.getByText(/Akte Nr\. \d+ endgültig gelöscht\./)).toBeVisible();
  await expect(page).toHaveURL(/\/patienten\?status=abgeschlossen/);
  expect((await page.request.get(`/api/patienten/${p.id}/`)).status()).toBe(404);

  // Löschprotokoll: Nummer und Rechtsgrund, kein Name
  await page.goto("/datenschutz");
  const protokoll = page.getByTestId("loeschprotokoll").getByRole("row").filter({ hasText: `Nr. ${String(p.nummer).padStart(4, "0")}` });
  await expect(protokoll).toContainText("Antrag der betroffenen Person");
  await expect(protokoll).toContainText("1 Kontakte");
  await expect(page.getByRole("main")).not.toContainText(p.nachname);
  // Audit-Log: die Einträge zur Akte bleiben, Namen und Inhalte sind entfernt
  await page.goto("/admin/audit-log");
  for (const gruppe of ["Datenschutz", "Abschluss", "Fehlversuch"]) await page.getByRole("button", { name: gruppe, exact: true }).click();
  const log = page.getByTestId("auditlog");
  await expect(log).toContainText(`Akte Nr. ${p.nummer} endgültig gelöscht (Antrag der betroffenen Person)`);
  await expect(log).toContainText(`Akte abgeschlossen: Akte Nr. ${p.nummer} (gelöscht) – Angaben mit der Akte gelöscht`);
  await expect(log).toContainText(`Löschen einer Akte abgelehnt: Akte Nr. ${p.nummer} (gelöscht)`);
  await expect(log).not.toContainText(p.nachname);
  await api.ende();
  merken("akte_geloescht", { id: p.id, nummer: p.nummer, nachname: p.nachname });
  await ctx.close();
});

test("Plan nach Freigabe per E-Mail abschließen: Mitarbeiter hält Mediziner, Datum, Weg und Nachweis fest", async ({ browser }) => {
  const med = await apiAls("mediziner");
  const p = await med.post("patienten/", { nachname: eindeutig("Freigabe"), vorname: "Frieda", geburtsdatum: "1972-02-02" });
  await med.post("gewichte/", { patient: p.id, gewicht_kg: "60.0", quelle: "telefonisch" });
  const entwurf = await med.post("infusionsplaene/entwurf/", { patient: p.id });
  const praeparate: { id: number; kategorie: string; name: string }[] = await med.get("praeparate/");
  const praeparat = (kategorie: string, name: string) => praeparate.find((x) => x.kategorie === kategorie && x.name === name)!.id;
  await med.patch(`infusionsplaene/${entwurf.id}/`, {
    glucose_praeparat: praeparat("glucose", "Glucose"), glucose_g: "160",
    aminosaeuren_praeparat: praeparat("aminosaeuren", "Glamin"), aminosaeuren_g: "80",
    lipide_praeparat: praeparat("lipide", "Clinoleic"), lipide_g: "60", laufzeit_h: "12",
  });

  const { ctx, page } = await seiteAls(browser, "mitarbeiter");
  await page.goto(`/patienten/${p.id}/plaene`);
  const detail = page.getByTestId("plan-detail");
  // Mitarbeiter geben nicht selbst frei – sie schließen ab, nachdem der Mediziner freigegeben hat
  await expect(detail.getByRole("button", { name: "Freigeben" })).toHaveCount(0);
  await detail.getByRole("button", { name: "Nach Freigabe abschließen" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Freigegeben von").selectOption({ label: "Dr. med. M. Medizin" });
  await expect(dialog.getByLabel("Weg der Freigabe")).toHaveValue("email");
  // per E-Mail: ohne Nachweis nicht
  await expect(dialog.getByRole("button", { name: "Abschließen" })).toBeDisabled();
  await dialog.getByLabel("Nachweis der Freigabe").setInputFiles({ name: "Freigabe.txt", mimeType: "text/plain",
    buffer: Buffer.from("Von: Masin\nDer Plan ist so freigegeben (E2E)\n", "utf-8") });
  await dialog.getByRole("button", { name: "Abschließen" }).click();
  await expect(page.getByText("Plan abgeschlossen.")).toBeVisible();
  await expect(page.getByTestId("planliste")).toContainText("aktuell gültig");
  await expect(detail).toContainText("von Dr. med. M. Medizin (per E-Mail); im System abgeschlossen am");
  await expect(detail).toContainText("von S. Mitarbeit.");
  // der Freigabevermerk auf der PDF nennt beide
  const plan = await med.get(`infusionsplaene/${entwurf.id}/`);
  expect(plan.freigabevermerk).toMatch(/^Maschinell erstellt\. Geprüft und freigegeben von Dr\. med\. M\. Medizin am \d{2}\.\d{2}\.\d{4} \(per E-Mail\); im System abgeschlossen von S\. Mitarbeit am \d{2}\.\d{2}\.\d{4}\.$/);
  await expect(page.getByTestId("ansicht-herkunft")).toContainText("Gespeicherte PDF der Freigabe · Prüfsumme stimmt");
  await expect(page.getByTestId("plan-ansicht").getByTestId("pdf-text").first()).toContainText("im System abgeschlossen von S. Mitarbeit");
  // der Nachweis liegt in der Akte
  await page.goto(`/patienten/${p.id}/dokumente`);
  await expect(page.getByTestId("dokumentliste").getByRole("listitem").filter({ hasText: "Freigabe Infusionsplan gültig ab" })).toContainText("Freigabe");
  await med.ende();
  merken("plan_abgeschlossen", { patient: p.id, plan: entwurf.id });
  await ctx.close();
});

test("Grenzwerte: Fristen des Datenschutzes einstellen", async ({ browser }) => {
  const { ctx, page } = await seiteAls(browser, "mediziner");
  await page.goto("/admin/vorlagen");
  await page.getByRole("button", { name: "Grenzwerte" }).click();
  const ds = page.getByTestId("grenzwerte-datenschutz");
  await expect(ds.getByLabel("Aufbewahrung nach Abschluss der Akte")).toHaveValue("10");
  await expect(ds.getByRole("checkbox", { name: "Einwilligung in die Datenverarbeitung" })).toBeChecked();
  await ds.getByLabel("Aufbewahrung nach Abschluss der Akte").fill("0");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(ds).toContainText("Bitte 1 bis 100 Jahre angeben.");
  await ds.getByLabel("Aufbewahrung nach Abschluss der Akte").fill("10");
  await ds.getByLabel("Audit-Log aufbewahren").fill("30");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Grenzwerte gespeichert.")).toBeVisible();
  await page.goto("/datenschutz");
  await expect(page.getByTestId("datenschutz-einstellungen")).toContainText("Aufbewahrung 10 Jahre nach Abschluss der Akte · Audit-Log 30 Jahre");
  await ctx.close();

  // Mitarbeiter pflegen Grenzwerte, die Fristen des Datenschutzes aber nicht (sie entscheiden über das Löschen)
  const zweit = await seiteAls(browser, "mitarbeiter");
  await zweit.page.goto("/admin/vorlagen");
  await zweit.page.getByRole("button", { name: "Grenzwerte" }).click();
  const nurLesen = zweit.page.getByTestId("grenzwerte-datenschutz");
  await expect(nurLesen.getByLabel("Aufbewahrung nach Abschluss der Akte")).toBeDisabled();
  await expect(nurLesen.getByLabel("Audit-Log aufbewahren")).toHaveValue("30");
  await expect(nurLesen.getByTestId("datenschutz-nur-lesen")).toBeVisible();
  await zweit.ctx.close();
});

test("Audit-Log aufbewahren: ältere Einträge entfernt die tägliche Bereinigung, sie steht selbst im Audit-Log (F83)", async ({ browser }) => {
  test.setTimeout(180_000);
  const { ctx, page } = await seiteAls(browser, "mediziner");
  const marke = eindeutig("E2E-Altbestand");
  // Ein alter Eintrag lässt sich über die Oberfläche nicht erzeugen: direkt im Backend anlegen und zurückdatieren
  // (nur im Wartungsmodus möglich – sonst verhindern die Trigger jede Änderung am Protokoll)
  const skript = [
    "from datetime import timedelta", "from django.utils import timezone",
    "from audit.models import SystemEreignis, protokolliere", "from audit.schutz import wartungsmodus",
    `e = protokolliere(SystemEreignis.Art.EXPORT, objekt="${marke}")`,
    "with wartungsmodus():",
    "    SystemEreignis.objects.filter(pk=e.pk).update(zeitpunkt=timezone.now() - timedelta(days=800))",
  ].join("\n");
  execSync("sudo docker compose -p epm-ci exec -T backend python manage.py shell",
    { cwd: process.env.EPM_CI_BASIS ?? "/tmp/epm-ci", input: skript, stdio: ["pipe", "inherit", "inherit"] });
  const api = await apiAls("mediziner");
  expect((await api.get(`protokoll/?search=${encodeURIComponent(marke)}`)).count).toBe(1);

  // Aufbewahrung über die Oberfläche auf 1 Jahr
  await page.goto("/admin/vorlagen");
  await page.getByRole("button", { name: "Grenzwerte" }).click();
  const ds = page.getByTestId("grenzwerte-datenschutz");
  const vorher = await ds.getByLabel("Audit-Log aufbewahren").inputValue();
  await ds.getByLabel("Audit-Log aufbewahren").fill("1");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Grenzwerte gespeichert.")).toBeVisible();

  // Die Bereinigung läuft einmal am Tag je Prozess des Backends, angestoßen von der Startseite – nach einem Neustart
  // also beim nächsten Öffnen
  stackNeuStarten();
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Hauptnavigation" })).toBeVisible();
  await expect.poll(async () => (await api.get(`protokoll/?search=${encodeURIComponent(marke)}`)).count, { timeout: 30_000 }).toBe(0);
  await page.goto("/admin/audit-log");
  await expect(page.getByText(/\d+ Einträge älter als 1 Jahre entfernt/).first()).toBeVisible();

  // zurück auf den vorherigen Wert
  await page.goto("/admin/vorlagen");
  await page.getByRole("button", { name: "Grenzwerte" }).click();
  await page.getByTestId("grenzwerte-datenschutz").getByLabel("Audit-Log aufbewahren").fill(vorher);
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Grenzwerte gespeichert.")).toBeVisible();
  await api.ende();
  await ctx.close();
});
