/**
 * Administration › System (Wunsch 02.10.2026, Festlegungen S12–S14): nur Admin; Auslastung vom Systemagenten
 * (in CI im Probelauf), Tätigkeiten für Server und EPM, Bestätigung mit Passwort + 2FA, Hinweis an alle Benutzer.
 */
import { expect, test } from "@playwright/test";
import { KENNWORT, merken, naechsterNotfallcode, zustand } from "./hilfen";

test.use({ storageState: zustand("admin") });

test("System: nur für Admin – Menü, Seite und Recht nur für die Rolle Admin", async ({ page, browser }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Administration" }).getByRole("link", { name: "System" }).click();
  await expect(page.getByRole("heading", { name: "System", level: 1 })).toBeVisible();
  // Recht „Systemverwaltung“ gibt es in der Matrix nur für Admin
  await page.goto("/admin/benutzer");
  const rechte = page.getByTestId("rechte");
  await expect(rechte.getByRole("checkbox", { name: "Admin: Systemverwaltung (Server und EPM)" })).toBeChecked();
  const mediziner = rechte.getByRole("checkbox", { name: "Mediziner: Systemverwaltung (Server und EPM)" });
  await expect(mediziner).toBeDisabled();
  await expect(mediziner).not.toBeChecked();
  for (const rolle of ["mediziner", "mitarbeiter", "betrachter"] as const) {
    const ctx = await browser.newContext({ storageState: zustand(rolle), ignoreHTTPSErrors: true });
    const p = await ctx.newPage();
    await p.goto("/");
    await expect(p.getByRole("navigation", { name: "Hauptnavigation" })).toBeVisible();
    await expect(p.getByRole("link", { name: "System", exact: true })).toHaveCount(0);
    await p.goto("/admin/system");
    await expect(p).toHaveURL(/\/$/);
    await ctx.close();
  }
});

test("System: Auslastung und Status vom Systemagenten, Wartung des EPM", async ({ page }) => {
  await page.goto("/admin/system");
  await expect(page.getByTestId("kennzahl-cpu")).toBeVisible();
  await expect(page.getByTestId("kennzahl-ram")).toContainText("%");
  await expect(page.getByTestId("kennzahl-platte")).toContainText("frei von");
  // CI: der Systemagent läuft im Probelauf (werkzeuge/ci-stack.sh)
  await expect(page.getByText("Probelauf: Der Systemagent simuliert")).toBeVisible();
  await expect(page.getByTestId("agent-fehlt")).toHaveCount(0);
  await expect(page.getByTestId("container")).toContainText("backend");
  await expect(page.getByTestId("kennzahl-updates")).toContainText("Paketlisten");
  await expect(page.getByTestId("epm-karte")).toContainText("vollständig");
  await expect(page.getByTestId("epm-karte")).toContainText("Tabellen geschützt");
  // Wartung des EPM: sofort mit Ergebnis
  await page.getByTestId("aufgabe-schutz_pruefen").getByRole("button", { name: "Unveränderlichkeit prüfen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Ausführen" }).click();
  const zeile = page.getByTestId("auftraege").getByRole("row", { name: /Unveränderlichkeit prüfen/ }).first();
  await expect(zeile).toContainText("erledigt");
  await expect(zeile).toContainText("geschützten Tabellen in Ordnung");
  // Auftrag an den Server: der Agent führt ihn aus, das Ergebnis erscheint ohne Neuladen
  await page.getByTestId("aktion-status_aktualisieren").getByRole("button", { name: "Status neu einlesen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Ausführen" }).click();
  const auftrag = page.getByTestId("auftraege").getByRole("row", { name: /Status neu einlesen/ }).first();
  await expect(auftrag).toContainText("erledigt (Probelauf)", { timeout: 30_000 });
  await auftrag.getByRole("button", { name: "Ausgabe" }).click();
  await expect(page.getByTestId("auftrag-ausgabe")).toContainText("Status wird gemessen");
  merken("system", { taetigkeit: "Status neu einlesen" });
});

test("System: Neustart nur mit Passwort und 2FA, vorher Warnung an alle Benutzer", async ({ page, browser }) => {
  await page.goto("/admin/system");
  await page.getByTestId("aktion-server_neustart").getByRole("button", { name: "Server neu starten" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Vorher erstellt der Server automatisch eine Sicherung")).toBeVisible();
  await dialog.getByLabel("Beginn").selectOption("15");
  await dialog.getByLabel("Ihr Passwort").fill(KENNWORT);
  await dialog.getByLabel("Code aus der Authenticator-App").fill("000000");
  await dialog.getByRole("button", { name: "Bestätigen und ausführen" }).click();
  await expect(dialog.getByText("Der Code ist ungültig")).toBeVisible();
  await dialog.getByLabel("Code aus der Authenticator-App").fill(naechsterNotfallcode("e2e.admin"));
  // django-otp lässt nach einem falschen Code kurz keinen weiteren Versuch zu
  await page.waitForTimeout(2500);
  await dialog.getByRole("button", { name: "Bestätigen und ausführen" }).click();
  await expect(dialog).toHaveCount(0);
  const auftrag = page.getByTestId("auftraege").getByRole("row", { name: /Server neu starten/ }).first();
  await expect(auftrag).toContainText("Beginn nach 15 Min.");
  await expect(auftrag).toContainText("erledigt (Probelauf)", { timeout: 30_000 });
  // Warnung bei allen Angemeldeten
  const ctx = await browser.newContext({ storageState: zustand("mitarbeiter"), ignoreHTTPSErrors: true });
  const p = await ctx.newPage();
  await p.goto("/patienten");
  await expect(p.getByTestId("systemhinweis")).toContainText("Der Server wird neu gestartet");
  await expect(p.getByTestId("systemhinweis")).toContainText("Beginn:");
  // Admin beendet die Warnung, sie verschwindet bei den anderen mit der nächsten Abfrage
  await page.getByTestId("hinweis-karte").getByRole("button", { name: "Beenden" }).click();
  await expect(page.getByTestId("aktiver-hinweis")).toHaveCount(0);
  await p.reload();
  await expect(p.getByRole("heading", { name: "Patienten", level: 1 })).toBeVisible();
  await expect(p.getByTestId("systemhinweis")).toHaveCount(0);
  await ctx.close();
});

test("System: eigener Hinweis an alle Benutzer und Eintrag im Audit-Log", async ({ page, browser }) => {
  await page.goto("/admin/system");
  const karte = page.getByTestId("hinweis-karte");
  await karte.getByLabel("Neuer Hinweis").fill("E2E: Heute ab 18 Uhr Wartung");
  await karte.getByLabel("Anzeigen").selectOption("60");
  await karte.getByRole("button", { name: "Hinweis setzen" }).click();
  await expect(karte.getByTestId("aktiver-hinweis")).toContainText("E2E: Heute ab 18 Uhr Wartung");
  const ctx = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const p = await ctx.newPage();
  await p.goto("/");
  await expect(p.getByTestId("systemhinweis")).toContainText("E2E: Heute ab 18 Uhr Wartung");
  await p.getByRole("button", { name: "Hinweis ausblenden" }).click();
  await expect(p.getByTestId("systemhinweis")).toHaveCount(0);
  await ctx.close();
  await karte.getByRole("button", { name: "Beenden" }).click();
  await expect(karte.getByTestId("aktiver-hinweis")).toHaveCount(0);
  await page.goto("/admin/audit-log");
  await page.getByRole("button", { name: "System", exact: true }).click();
  await expect(page.getByText("Hinweis an alle Benutzer: „E2E: Heute ab 18 Uhr Wartung“").first()).toBeVisible();
  await expect(page.getByText("Server neu starten angefordert, Beginn in 15 Min., mit Passwort und 2FA bestätigt").first()).toBeVisible();
});
