/**
 * Administration › Import (F65): Übernahme der Altdaten mit dem erfundenen Beispiel-Dump – Dump laden, Zuordnungen in
 * der Oberfläche korrigieren, Probelauf, Import (Passwort + 2FA), übernommene Akte ansehen, Dokumente aus dem Ordner
 * auf dem Server, Zurücknehmen.
 *
 * Die Datei heißt „aa-…“, damit sie vor allen anderen läuft: Übernommen wird nur in ein System ohne echte Akten.
 * Am Ende wird der Import zurückgenommen – die übrigen Tests finden das System wie zuvor vor. Der Dump, die
 * Zuordnungen und die Läufe bleiben; `zz-neustart.spec.ts` prüft sie nach dem Neustart erneut.
 */
import { execSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { KENNWORT, apiAls, einfachePdf, merken, naechsterNotfallcode, zustand } from "./hilfen";

test.use({ storageState: zustand("admin") });

const DUMP = "../backend/altimport/testdaten/beispiel-dump.sql";
const schritt = (page: Page, name: string) => page.getByRole("group", { name: "Schritte der Übernahme" }).getByRole("button", { name });
const bereich = (page: Page, name: string | RegExp) => page.getByRole("group", { name: "Bereich der Zuordnungen" }).getByRole("button", { name });

/** Bestätigen mit Passwort und Notfall-Code (jeder Code gilt einmal) */
async function bestaetigen(page: Page, knopf: string, wort?: string) {
  const dialog = page.getByRole("dialog");
  if (wort) await dialog.getByLabel(`Zur Bestätigung „${wort}“ eintippen`).fill(wort);
  await dialog.getByLabel("Ihr Passwort").fill(KENNWORT);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(naechsterNotfallcode("e2e.admin"));
  await dialog.getByRole("button", { name: knopf }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

/** Ordner des Altsystems auf dem „Server“ (CI-Stack): data/import/PatData/<Patientennummer>/ */
function dokumentenordnerAnlegen() {
  const quelle = mkdtempSync(join(tmpdir(), "epm-altdok-"));
  for (const ordner of ["1", "6"]) mkdirSync(join(quelle, "PatData", ordner), { recursive: true });
  writeFileSync(join(quelle, "PatData", "1", "Arztbrief alt.pdf"), einfachePdf(["Arztbrief aus dem Altsystem (erfunden)"]));
  writeFileSync(join(quelle, "PatData", "1", "notiz.txt"), "Notiz aus dem Altsystem (erfunden)\n");
  writeFileSync(join(quelle, "PatData", "1", "skript.php"), "<?php echo 1; ?>\n");
  writeFileSync(join(quelle, "PatData", "6", "nicht-uebernommen.txt"), "Patient 6 wird nicht übernommen (erfunden)\n");
  execSync(`touch -d "2022-03-04 10:00:00" "${join(quelle, "PatData", "1", "Arztbrief alt.pdf")}"`);
  const ziel = `${process.env.EPM_CI_BASIS ?? "/tmp/epm-ci"}/data/import`;
  execSync(`sudo rm -rf "${ziel}/PatData" && sudo cp -a "${quelle}/PatData" "${ziel}/" && sudo chown -R 10001:101 "${ziel}/PatData" && sudo chmod -R u=rwX,g=rX,o= "${ziel}/PatData"`,
    { stdio: "inherit" });
}

// Sicherheitsnetz: Scheitert ein Test, während die Altdaten übernommen sind, fänden alle folgenden Tests fremde
// Akten vor. Dann hier über die API zurücknehmen (in der Oberfläche prüft es der dritte Test).
test.afterAll(async () => {
  const admin = await apiAls("admin");
  try {
    if ((await admin.get("altimport/")).status === "importiert") {
      await admin.post("altimport/zuruecknehmen/", { kennwort: KENNWORT, code: naechsterNotfallcode("e2e.admin"), bestaetigung: "ZURÜCKNEHMEN" });
    }
  } finally {
    await admin.ende();
  }
});

test("Import: nur für Admin – Menü, Seite und Recht nur für die Rolle Admin", async ({ page, browser }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Administration" }).getByRole("link", { name: "Import" }).click();
  await expect(page.getByRole("heading", { name: "Import", level: 1 })).toBeVisible();
  await expect(page.getByTestId("import-status")).toHaveText("kein Dump geladen");
  await expect(page.getByTestId("echte-akten")).toHaveCount(0);
  await page.goto("/admin/benutzer");
  const rechte = page.getByTestId("rechte");
  await expect(rechte.getByRole("checkbox", { name: /^Admin: Altdaten/ })).toBeChecked();
  await expect(rechte.getByRole("checkbox", { name: /^Mediziner: Altdaten/ })).toBeDisabled();
  for (const rolle of ["mediziner", "mitarbeiter", "betrachter"] as const) {
    const ctx = await browser.newContext({ storageState: zustand(rolle), ignoreHTTPSErrors: true });
    const p = await ctx.newPage();
    await p.goto("/");
    await expect(p.getByRole("navigation", { name: "Hauptnavigation" })).toBeVisible();
    await expect(p.getByRole("link", { name: "Import", exact: true })).toHaveCount(0);
    await p.goto("/admin/import");
    await expect(p).toHaveURL(/\/$/);
    await ctx.close();
  }
});

test("Import: Dump laden und Zuordnungen in der Oberfläche korrigieren", async ({ page }) => {
  await page.goto("/admin/import");
  // ohne Dump: Hinweis statt Zuordnungen
  await schritt(page, "2 · Zuordnungen").click();
  await expect(page.getByTestId("zuordnungen-gesperrt")).toContainText("Zuerst unter „1 · Dump“ einen Dump laden");
  await schritt(page, "1 · Dump").click();

  await page.getByLabel("Dump auswählen").setInputFiles(DUMP);
  await page.getByRole("button", { name: "Dump laden" }).click();
  await expect(page.getByTestId("dump-name")).toContainText("beispiel-dump.sql");
  await expect(page.getByTestId("dump-tabellen")).toContainText("patienten (7)");
  await expect(page.getByTestId("dump-tabellen")).toContainText("gewichte (10)");
  // Regel 1: Kennwörter werden beim Einlesen verworfen
  await expect(page.getByTestId("dump-karte")).toContainText("benutzerdaten.Kennwort");
  await expect(page.getByTestId("import-status")).toHaveText("Dump geladen");

  await schritt(page, "2 · Zuordnungen").click();
  const offen = page.getByTestId("offene-punkte");
  await expect(offen).toContainText("5 offene Punkte");
  await expect(offen).toContainText("Nickelallergie „vielleicht“: Bitte zuordnen.");

  // Tabellen und Spalten: erkannt; eine Spalte abwählen und den Vorschlag wiederherstellen
  const patienten = page.getByTestId("quelle-patienten");
  await expect(patienten).toContainText("7 Zeilen in der Tabelle „patienten“");
  const email = patienten.getByRole("row").filter({ has: page.getByLabel("Spalte für Patienten: E-Mail") });
  const spalte = await email.getByLabel("Spalte für Patienten: E-Mail").inputValue();
  expect(spalte).not.toBe("");
  await email.getByLabel("Spalte für Patienten: E-Mail").selectOption("");
  await expect(email).toContainText("bewusst leer");
  await email.getByRole("button", { name: "Vorschlag für Patienten: E-Mail" }).click();
  await expect(email).toContainText("erkannt");
  await expect(email.getByLabel("Spalte für Patienten: E-Mail")).toHaveValue(spalte);

  // Benutzer: Konto im Altsystem → neues Konto mit Rolle; nur als Bearbeiter genannt → historischer Benutzer
  await bereich(page, "Benutzer").click();
  const muster = page.getByTestId("benutzer-a.muster");
  await expect(muster.getByLabel("Zuordnung für a.muster")).toHaveValue("konto");
  await expect(muster.getByLabel("Rolle für a.muster")).toHaveValue("mitarbeiter");
  await expect(page.getByTestId("benutzer-hans.alt").getByLabel("Zuordnung für hans.alt")).toHaveValue("historisch");
  // Namen korrigieren: aus dem Kürzel „A“ wird der Vorname
  await muster.getByLabel("Vorname für a.muster").fill("Anton");
  await muster.getByLabel("Vorname für a.muster").press("Enter");
  await expect(muster).toContainText("zugeordnet");
  await expect(muster.getByLabel("Vorname für a.muster")).toHaveValue("Anton");

  // Versorger: gleiche Firma = ein Versorger mit zwei Ansprechpartnern
  await bereich(page, "Versorger").click();
  await expect(page.getByTestId("versorger-1").getByLabel("Name des Versorgers 1")).toHaveValue("Homecare Nord (erfunden)");
  await expect(page.getByTestId("versorger-2").getByLabel("Ansprechpartner für Versorger 2")).toHaveValue("Herr Muster");
  await expect(page.getByTestId("versorger-0").getByLabel("Zuordnung für Versorger 0")).toHaveValue("leer");

  // Werte: unbekannter Wert der Nickelallergie
  await bereich(page, /^Katheter und Werte/).click();
  const nickel = page.getByTestId("nickel-vielleicht");
  await expect(nickel).toContainText("offen");
  await nickel.getByLabel("Nickelallergie im EPM für vielleicht").selectOption("unbekannt");
  await expect(nickel).toContainText("zugeordnet");
  await expect(page.getByTestId("katheter-nein").getByLabel("Katheter im EPM für Nein")).toHaveValue("kein");
  await expect(offen).toContainText("4 offene Punkte");

  // Präparate: Schreibvariante dem vorhandenen Präparat zuordnen, unbekanntes Medikament neu anlegen
  await bereich(page, /^Präparate/).click();
  const lipid = page.getByTestId("praeparat-lipide-clinoleik 20%");
  const wahl = lipid.getByLabel("Zuordnung für Lipide: Clinoleik 20%");
  // vorgeschlagen wird nur bei genauer Übereinstimmung – das ähnlich geschriebene Präparat steht oben in der Auswahl
  await expect(wahl).toHaveValue("");
  const aehnlich = wahl.locator('optgroup[label="Ähnlich geschrieben"] option');
  await expect(aehnlich).toHaveText(["Clinoleic 20 %"]);
  await wahl.selectOption((await aehnlich.getAttribute("value")) ?? "");
  await expect(lipid).toContainText("zugeordnet");
  const heparin = page.getByTestId("praeparat-medikamente-heparin 100 i.e. nach bedarf");
  await heparin.getByLabel("Zuordnung für Katheterblock / Medikamente: Heparin 100 I.E. nach Bedarf").selectOption("neu");
  const name = heparin.getByLabel("Name des neuen Präparats für Heparin 100 I.E. nach Bedarf");
  await expect(name).toHaveValue("Heparin 100 I.E. nach Bedarf");
  await name.fill("Heparin");
  await name.press("Enter");
  await expect(heparin.getByLabel("Kategorie für Heparin 100 I.E. nach Bedarf")).toHaveValue("medikament");
  await expect(heparin).toContainText("zugeordnet");
  await expect(offen).toContainText("2 offene Punkte");
  // „Sterofundin“ des Altsystems heißt im EPM seit dem 06.10.2026 „Sterofundin ISO“ (F111): kein genauer Treffer,
  // deshalb steht es unter „Ähnlich geschrieben“ und wird einmal von Hand zugeordnet (U43)
  const basis = page.getByTestId("praeparat-basis-sterofundin");
  await basis.getByLabel("Zuordnung für Basislösung: Sterofundin").selectOption({ label: "Sterofundin ISO" });
  await expect(basis).toContainText("zugeordnet");
  await expect(offen).toContainText("1 offene Punkte");

  // Im Altsystem gelöschte Patienten: Standard „nicht übernehmen“; Patient 4 als abgeschlossene Akte
  await bereich(page, "Gelöschte Patienten").click();
  const geloescht = page.getByTestId("geloescht-4");
  await expect(geloescht).toContainText("Probe, Jonas");
  await expect(geloescht.getByLabel("Entscheidung für Patient 4")).toHaveValue("nicht");
  await geloescht.getByLabel("Entscheidung für Patient 4").selectOption("abgeschlossen");
  await geloescht.getByLabel("Anlass für Patient 4").selectOption("therapie_beendet");
  await expect(geloescht.getByLabel("Anlass für Patient 4")).toHaveValue("therapie_beendet");
  await expect(page.getByTestId("geloescht-6").getByLabel("Entscheidung für Patient 6")).toHaveValue("nicht");

  // Auffälligkeiten: fehlendes Geburtsdatum eintragen (Pflicht im EPM)
  await bereich(page, /^Auffälligkeiten/).click();
  const geburt = page.getByTestId("auffaellig-patienten:3:geburtsdatum");
  await expect(geburt).toContainText("offen");
  await geburt.getByLabel("Entscheidung für Patienten 3: Geburtsdatum").selectOption("wert");
  await geburt.getByLabel("Wert für Patienten 3: Geburtsdatum").fill("1988-07-21");
  await geburt.getByLabel("Wert für Patienten 3: Geburtsdatum").blur();
  await expect(geburt).toContainText("entschieden");
  await expect(offen).toContainText("Alle Zuordnungen sind vollständig");

  // gespeichert – nach dem Neuladen der Seite steht alles wieder da
  await page.reload();
  await expect(page.getByTestId("offene-punkte")).toContainText("Alle Zuordnungen sind vollständig");
  await bereich(page, "Katheter und Werte").click();
  await expect(page.getByTestId("nickel-vielleicht").getByLabel("Nickelallergie im EPM für vielleicht")).toHaveValue("unbekannt");
});

test("Import: Probelauf, Übernahme mit Passwort und 2FA, Akte, Dokumente, Zurücknehmen", async ({ page, browser }) => {
  test.setTimeout(180_000);
  dokumentenordnerAnlegen();
  const mediziner = await apiAls("mediziner");
  expect((await mediziner.get("patienten/?test=ohne&seitengroesse=1")).count).toBe(0);

  // Probelauf: schreibt alles und rollt es zurück
  await page.goto("/admin/import?schritt=import");
  await expect(page.getByTestId("hindernisse")).toContainText("Probelauf und Import sind möglich");
  await expect(page.getByTestId("zaehlung").getByRole("row", { name: /^Patienten/ })).toContainText("1 als abgeschlossene Akten");
  await page.getByRole("button", { name: "Probelauf starten" }).click();
  const ergebnis = page.getByTestId("lauf-ergebnis");
  await expect(ergebnis).toContainText("erfolgreich – es wurde nichts gespeichert", { timeout: 30_000 });
  await expect(ergebnis).toContainText("6 Akten (1 abgeschlossen) · 6 Gewichte · 4 Kontakte · 5 Infusionspläne");
  await expect(ergebnis.getByTestId("protokoll")).toContainText("Regel 5");
  expect((await mediziner.get("patienten/?test=ohne&seitengroesse=1")).count).toBe(0);
  await expect(page.getByTestId("import-status")).toHaveText("Dump geladen");

  // Import: Bestätigung mit Passwort und zweitem Faktor
  await page.getByRole("button", { name: "Altdaten übernehmen …" }).click();
  await bestaetigen(page, "Bestätigen und übernehmen");
  await expect(page.getByTestId("import-status")).toHaveText("Altdaten übernommen");
  const bestand = page.getByTestId("uebernommen-bestand");
  await expect(bestand).toContainText("6 Akten");
  await expect(bestand).toContainText("6 Gewichte · 4 Kontakte · 5 Infusionspläne · 0 Dokumente");
  await expect(page.getByTestId("lauf-ergebnis")).toContainText("Import vom");
  // Zuordnungen sind gesperrt, solange übernommen ist
  await schritt(page, "2 · Zuordnungen").click();
  await expect(page.getByTestId("zuordnungen-gesperrt")).toContainText("Die Zuordnungen sind gesperrt");

  // Die übernommene Akte, wie die Mediziner sie sehen: Patientennummer des Altsystems, Gewichte, Kontakte, Pläne
  const treffer = (await mediziner.get("patienten/?suche=Musterfrau")).results as { id: number; nummer: number; vorname: string }[];
  const erika = treffer.find((p) => p.nummer === 1);
  expect(erika?.vorname).toBe("Erika");
  // Regel 3: kaputte Umlaute sind repariert
  const mueller = (await mediziner.get(`patienten/?suche=${encodeURIComponent("Müller")}`)).results as { nummer: number }[];
  expect(mueller.map((p) => p.nummer)).toContain(2);
  const ctx = await browser.newContext({ storageState: zustand("mediziner"), ignoreHTTPSErrors: true });
  const akte = await ctx.newPage();
  await akte.goto(`/patienten/${erika!.id}`);
  await expect(akte.getByTestId("aktenkopf")).toContainText("Musterfrau");
  await akte.getByRole("button", { name: /Messwerte anzeigen/ }).click();
  await expect(akte.getByTestId("messwerte")).toContainText("64,5");
  await akte.goto(`/patienten/${erika!.id}/kontakte`);
  await expect(akte.getByTestId("kontaktliste")).toContainText("Befinden stabil");
  await akte.goto(`/patienten/${erika!.id}/plaene`);
  await expect(akte.getByTestId("planliste")).toContainText("aus dem Altsystem");

  // Dokumente: aus dem Ordner auf dem Server, nicht über den Browser
  await page.goto("/admin/import?schritt=dokumente");
  await expect(page.getByTestId("dokumente-stand")).toContainText("Noch offen");
  const nicht = page.getByTestId("dokumente-nicht");
  await expect(nicht).toContainText("skript.php");
  await expect(nicht).toContainText("1 Ordner ohne übernommenen Patienten: 6 (1)");
  await page.getByRole("button", { name: "Dokumente übernehmen" }).click();
  await expect(page.getByText("alle Dokumente übernommen", { exact: true })).toBeVisible({ timeout: 60_000 });
  await akte.goto(`/patienten/${erika!.id}/dokumente`);
  const liste = akte.getByTestId("dokumentliste");
  await expect(liste.getByRole("button", { name: "Arztbrief alt" })).toBeVisible();
  await expect(liste.getByRole("button", { name: "notiz" })).toBeVisible();
  await expect(liste.getByRole("listitem").filter({ hasText: "Arztbrief alt" })).toContainText("04.03.2022");
  await expect(liste).not.toContainText("skript");
  await ctx.close();

  // Abschließen wäre jetzt möglich – hier wird stattdessen zurückgenommen
  await page.goto("/admin/import?schritt=abschluss");
  await expect(page.getByTestId("abschluss-karte").getByRole("button", { name: "Übernahme abschließen …" })).toBeEnabled();

  await page.goto("/admin/import?schritt=import");
  await expect(page.getByTestId("uebernommen-bestand")).toContainText("2 Dokumente");
  await page.getByRole("button", { name: "Import zurücknehmen …" }).click();
  await expect(page.getByTestId("zurueck-warnung")).toContainText("6 Akten");
  await expect(page.getByTestId("zurueck-warnung")).toContainText("2 Dokumenten");
  await bestaetigen(page, "Bestätigen und zurücknehmen", "ZURÜCKNEHMEN");
  await expect(page.getByTestId("import-status")).toHaveText("Dump geladen");
  await expect(page.getByTestId("lauf-ergebnis")).toContainText("Import zurückgenommen vom");
  // alles Übernommene ist weg – auch die angelegten Stammdaten; Dump und Zuordnungen bleiben
  expect((await mediziner.get("patienten/?test=ohne&seitengroesse=1")).count).toBe(0);
  const versorger = JSON.stringify(await mediziner.get("versorger/"));
  expect(versorger).not.toContain("Homecare Nord (erfunden)");
  await mediziner.ende();
  await schritt(page, "2 · Zuordnungen").click();
  await expect(page.getByTestId("offene-punkte")).toContainText("Alle Zuordnungen sind vollständig");

  // Protokolle: jeder Schritt ist als Lauf festgehalten
  await schritt(page, "Protokolle").click();
  const laeufe = page.getByTestId("laeufe");
  for (const art of ["Probelauf", "Import", "Dokumente übernommen", "Import zurückgenommen"]) {
    await expect(laeufe.getByTestId("lauf").filter({ hasText: art }).first()).toContainText("erfolgreich");
  }
  const lauf = laeufe.getByTestId("lauf").filter({ has: page.getByRole("cell", { name: "Import", exact: true }) });
  await lauf.getByRole("button", { name: "Ansehen" }).click();
  await expect(laeufe.getByTestId("lauf-ergebnis")).toContainText("6 Akten (1 abgeschlossen)");
  await expect(laeufe.getByRole("link", { name: "Protokoll als Textdatei" })).toBeVisible();
  // Audit-Log: Import und Zurücknehmen stehen drin
  await page.goto("/admin/audit-log");
  await page.getByRole("button", { name: "System", exact: true }).click();
  await expect(page.getByTestId("auditlog")).toContainText("zurückgenommen: 6 Akten");
  await expect(page.getByTestId("auditlog")).toContainText("Dump „beispiel-dump.sql“ geladen");
  merken("import", { dump: "beispiel-dump.sql" });
});
