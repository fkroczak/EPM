/**
 * Administration › System › „Testphase und Go-live“ (Festlegung 03.10.2026, U27/U32) gegen den echten Stack:
 * Menüpunkt „Import“ aus- und einblenden, Musterdaten-Schalter, „Datenbank leeren“ mit Kontenauswahl, abgetipptem
 * Bestätigungscode, Passwort, 2FA und der Rückfrage „Wollen Sie wirklich …“. Der Systemagent sichert vorher (echt) und
 * leert dann über das Backend.
 *
 * Läuft als allerletzte Datei (nach zzz-sicherung.spec.ts): Danach gibt es keine Akten, Versorger und Testkonten mehr,
 * und alle anderen Anmeldungen sind beendet.
 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { KENNWORT, OHNE_ANMELDUNG, anmeldenUI, naechsterNotfallcode } from "./hilfen";

test.describe.configure({ mode: "serial" });
// beim manuellen Start des Workflows folgen Bildschirmfotos mit Musterdaten (.github/workflows/backend.yml)
test.skip(!!process.env.EPM_OHNE_LEEREN, "Bildschirmfotos brauchen die Musterdaten");
// nach dem Wiederherstellen in zzz-sicherung gelten die gespeicherten Sitzungen nicht mehr – neu anmelden
test.use({ storageState: OHNE_ANMELDUNG });

type Auftrag = { kennung: string; status: string; ergebnis: string; ausgabe: string; aktion: string };

async function anmelden(page: Page) {
  await anmeldenUI(page, "e2e.admin", naechsterNotfallcode("e2e.admin"));
  await expect(page.getByRole("navigation", { name: "Hauptnavigation" })).toBeVisible();
}

test("Testphase: Menüpunkt „Import“ ausblenden und wieder einblenden; Musterdaten-Schalter", async ({ page }) => {
  await anmelden(page);
  await page.goto("/admin/system");
  const karte = page.getByTestId("golive-karte");
  const nav = page.getByRole("navigation", { name: "Administration" });
  await expect(nav.getByRole("link", { name: "Import" })).toBeVisible();
  const import_aus = karte.getByRole("checkbox", { name: /Menüpunkt „Import“ ausblenden/ });
  await expect(import_aus).not.toBeChecked();
  // Schalter folgen der Antwort des Servers – klicken, dann auf den neuen Zustand warten
  await import_aus.click();
  await expect(import_aus).toBeChecked();
  await expect(page.getByText("Menüpunkt „Import“ ausgeblendet.")).toBeVisible();
  await expect(nav.getByRole("link", { name: "Import" })).toHaveCount(0);
  // die Seite bleibt erreichbar und sagt, wo man wieder einblendet
  await karte.getByRole("link", { name: "Import öffnen" }).click();
  await expect(page.getByTestId("import-ausgeblendet")).toBeVisible();
  await page.getByTestId("import-ausgeblendet").getByRole("link", { name: "Administration › System" }).click();
  await karte.getByRole("checkbox", { name: /Menüpunkt „Import“ ausblenden/ }).click();
  await expect(karte.getByRole("checkbox", { name: /Menüpunkt „Import“ ausblenden/ })).not.toBeChecked();
  await expect(nav.getByRole("link", { name: "Import" })).toBeVisible();

  const muster = karte.getByRole("checkbox", { name: /Musterdaten automatisch anlegen/ });
  await expect(muster).toBeChecked();
  await muster.click();
  await expect(muster).not.toBeChecked();
  await expect(page.getByText("Musterdaten werden nicht mehr automatisch angelegt.")).toBeVisible();
  await muster.click();
  await expect(muster).toBeChecked();
  await expect(page.getByText("Musterdaten werden beim Start wieder angelegt.")).toBeVisible();
});

test("Datenbank leeren: Kontenauswahl, Code abtippen, Passwort + 2FA, Rückfrage; vorher Sicherung; danach leer", async ({ page }) => {
  test.setTimeout(300_000);
  await anmelden(page);
  const vorher = await (await page.request.get("/api/benutzer/")).json();
  const liste = (Array.isArray(vorher) ? vorher : vorher.results) as { id: number; username: string }[];
  const betrachter = liste.find((b) => b.username === "e2e.betrachter")!;
  const mediziner = liste.find((b) => b.username === "e2e.mediziner")!;
  expect(betrachter && mediziner).toBeTruthy();

  await page.goto("/admin/system");
  await page.getByTestId("golive-karte").getByRole("button", { name: "Datenbank leeren …" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByTestId("leeren-umfang")).toContainText("Testpatienten");
  const konten = dialog.getByTestId("leeren-konten");
  // eigenes Konto fest, Testkonten vorgeschlagen zum Entfernen, echte Konten zum Behalten
  await expect(konten.getByRole("checkbox", { name: "A. Admin behalten", exact: true })).toBeDisabled();
  await expect(konten.getByRole("checkbox", { name: /Testzugang behalten/ })).not.toBeChecked();
  await expect(konten.getByRole("checkbox", { name: /Betrachtung behalten/ })).toBeChecked();
  await konten.getByRole("checkbox", { name: /Betrachtung behalten/ }).uncheck();

  const weiter = dialog.getByRole("button", { name: "Weiter …" });
  await expect(weiter).toBeDisabled();
  const code = (await dialog.getByTestId("leeren-code").textContent())!.trim();
  expect(code).toMatch(/^[A-Z2-9]{6}$/);
  await dialog.getByLabel("Bestätigungscode eingeben").fill("FALSCH");
  await dialog.getByLabel("Ihr Passwort").fill(KENNWORT);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(naechsterNotfallcode("e2e.admin"));
  await expect(weiter).toBeDisabled();
  await dialog.getByLabel("Bestätigungscode eingeben").fill(code.toLowerCase());
  await dialog.getByLabel("Beginn").selectOption("0");
  await weiter.click();

  // Rückfrage: „Nein“ führt zurück, die Eingaben bleiben
  await expect(dialog).toContainText("Wollen Sie wirklich die Datenbank löschen?");
  await expect(dialog.getByTestId("leeren-frage")).toContainText("Das Audit-Log beginnt neu");
  await dialog.getByRole("button", { name: "Nein, zurück" }).click();
  await expect(dialog.getByLabel("Bestätigungscode eingeben")).toHaveValue(code.toLowerCase());
  await weiter.click();
  const antwort = page.waitForResponse((r) => r.url().endsWith("/api/system/leeren/") && r.request().method() === "POST");
  await dialog.getByRole("button", { name: "Ja, Datenbank leeren" }).click();
  const r = await antwort;
  expect(r.status(), await r.text()).toBe(201);
  const auftrag = (await r.json()) as Auftrag;

  let a: Auftrag | undefined;
  await expect.poll(async () => {
    const liste = (await (await page.request.get("/api/system/auftraege/")).json()) as Auftrag[];
    a = liste.find((x) => x.kennung === auftrag.kennung);
    return a?.status;
  }, { timeout: 240_000, intervals: [2000] }).toMatch(/^(erledigt|fehler)$/);
  expect(a?.status, `${a?.ergebnis}\n${a?.ausgabe}`).toBe("erledigt");
  expect(a!.ergebnis).toContain("Datenbank geleert (Sicherung vorher:");

  // leer: keine Akten, keine Versorger; Testkonto und abgewählter Betrachter weg, Mediziner bleibt
  const epm = (await (await page.request.get("/api/system/uebersicht/")).json()).epm;
  expect(epm.patienten).toEqual({ in_betreuung: 0, abgeschlossen: 0, testpatienten: 0 });
  expect(epm.dokumente.anzahl).toBe(0);
  const versorger = await (await page.request.get("/api/versorger/")).json();
  expect(Array.isArray(versorger) ? versorger.length : versorger.count).toBe(0);
  expect((await page.request.get(`/api/benutzer/${betrachter.id}/`)).status()).toBe(404);
  expect((await page.request.get(`/api/benutzer/${mediziner.id}/`)).status()).toBe(200);

  // Sicherung vorher, Musterdaten aus, Audit-Log neu begonnen
  const backup = await (await page.request.get("/api/backup/")).json();
  expect(backup.sicherungen[0].art).toBe("vor_leeren");
  await page.goto("/admin/system");
  await expect(page.getByTestId("golive-karte").getByRole("checkbox", { name: /Musterdaten automatisch anlegen/ })).not.toBeChecked();
  await page.goto("/admin/audit-log");
  await page.getByRole("button", { name: "System", exact: true }).click();
  await expect(page.getByText(/Datenbank geleert: \d+ Akten, \d+ Testpatienten/).first()).toBeVisible();
});
