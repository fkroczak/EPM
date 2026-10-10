/**
 * Administration › System (Wunsch 02.10.2026, Festlegungen S12–S14): nur Admin; Auslastung vom Systemagenten
 * (in CI im Probelauf), Tätigkeiten für Server und EPM, Bestätigung mit Passwort + 2FA, Hinweis an alle Benutzer.
 */
import { expect, test } from "@playwright/test";
import { KENNWORT, adminNavigation, merken, naechsterNotfallcode, zustand } from "./hilfen";

test.use({ storageState: zustand("admin") });

test("System: Standard nur Admin, Vertretung je Gruppe freischaltbar und wieder zurücknehmbar", async ({ page, browser }) => {
  await page.goto("/");
  await (await adminNavigation(page)).getByRole("link", { name: "System", exact: true }).click();
  await expect(page.getByRole("heading", { name: "System", level: 1 })).toBeVisible();
  // Standard: nur Admin; für eine Urlaubsvertretung je Gruppe freischaltbar (Festlegung 02.10.2026)
  await page.goto("/admin/benutzer");
  const rechte = page.getByTestId("rechte");
  await expect(rechte.getByRole("checkbox", { name: "Admin: Systemverwaltung (Server und EPM)" })).toBeChecked();
  const mediziner = rechte.getByRole("checkbox", { name: "Mediziner: Systemverwaltung (Server und EPM)" });
  await expect(mediziner).toBeEnabled();
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
  // Vertretung: Mediziner bekommen die Systemverwaltung, sehen Menü und Seite; danach zurück auf Standard
  await mediziner.check();
  await rechte.getByRole("button", { name: "Speichern (1)" }).click();
  await expect(page.getByText("Rechte gespeichert. Sie gelten ab sofort.")).toBeVisible();
  const ctx = await browser.newContext({ storageState: zustand("mediziner"), ignoreHTTPSErrors: true });
  const p = await ctx.newPage();
  await p.goto("/");
  await (await adminNavigation(p)).getByRole("link", { name: "System", exact: true }).click();
  await expect(p.getByRole("heading", { name: "System", level: 1 })).toBeVisible();
  await p.getByTestId("system-reiter").getByRole("tab", { name: "Wartung" }).click();
  await expect(p.getByTestId("taetigkeiten")).toBeVisible();
  await mediziner.uncheck();
  await rechte.getByRole("button", { name: "Speichern (1)" }).click();
  await expect(rechte.getByRole("button", { name: "Speichern", exact: true })).toBeDisabled();
  await p.goto("/");
  await expect(p.getByRole("link", { name: "System", exact: true })).toHaveCount(0);
  await ctx.close();
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
  // Auslastung kompakt (Wunsch 10.10.2026): Kennzahl mit kleinem Verlauf, das große Diagramm erst im Dialog
  await expect(page.getByTestId("auslastung").getByTestId("mini-cpu")).toContainText("%");
  await expect(page.getByTestId("auslastung").getByTestId("sparkline").first()).toBeVisible();
  await expect(page.getByTestId("auslastung").getByTestId("verlauf")).toHaveCount(0);
  await page.getByTestId("auslastung-gross").click();
  // Zeitraum wählbar (Fehlerliste 02.10.2026, 4.1), Standard 24 h; die Wahl bleibt gemerkt
  let auslastung = page.getByRole("dialog");
  await expect(auslastung.getByRole("group", { name: "Zeitraum" }).getByRole("button")).toHaveText(["1 h", "3 h", "24 h", "7 Tage", "14 Tage", "1 Monat", "6 Monate"]);
  await expect(auslastung.getByTestId("verlauf")).toHaveAttribute("data-zeitraum", "24h");
  for (const [knopf, code, titel] of [["1 h", "1h", "1 Stunde"], ["6 Monate", "6m", "6 Monate"], ["7 Tage", "7t", "7 Tage"]]) {
    const antwort = page.waitForResponse((r) => r.url().includes(`/api/system/verlauf/?zeitraum=${code}`) && r.ok());
    await auslastung.getByRole("button", { name: knopf, exact: true }).click();
    await antwort;
    await expect(auslastung.getByTestId("verlauf")).toHaveAttribute("data-zeitraum", code);
    await expect(auslastung.getByRole("heading", { name: `Auslastung · ${titel}` })).toBeVisible();
  }
  await page.reload();
  await page.getByTestId("auslastung-gross").click();
  auslastung = page.getByRole("dialog");
  await expect(auslastung.getByTestId("verlauf")).toHaveAttribute("data-zeitraum", "7t");
  await auslastung.getByRole("button", { name: "24 h", exact: true }).click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  // Größe der Karten über „⋯“ (wie auf der Startseite), je Person gespeichert
  const karten = page.getByTestId("system-karten");
  const verlaufKarte = karten.locator('[data-bereich="verlauf"]');
  await expect(verlaufKarte).toHaveAttribute("data-breite", "2"); // 1440 px: 2 Spalten, Standard ganze Breite
  let gespeichert = page.waitForResponse((r) => r.url().endsWith("/api/auth/ich/") && r.request().method() === "PATCH" && r.ok());
  await page.getByTestId("groesse-verlauf").click();
  await page.getByRole("menuitem", { name: "Breite: 1 Spalte" }).click();
  await gespeichert;
  await expect(verlaufKarte).toHaveAttribute("data-breite", "1");
  gespeichert = page.waitForResponse((r) => r.url().endsWith("/api/auth/ich/") && r.request().method() === "PATCH" && r.ok());
  await page.getByTestId("groesse-verlauf").click();
  await page.getByRole("menuitem", { name: "Höhe: 2 Zeilen" }).click();
  await gespeichert;
  await expect(verlaufKarte).toHaveAttribute("data-hoehe", "2");
  await page.reload();
  await expect(page.getByTestId("system-karten").locator('[data-bereich="verlauf"]')).toHaveAttribute("data-hoehe", "2");
  gespeichert = page.waitForResponse((r) => r.url().endsWith("/api/auth/ich/") && r.request().method() === "PATCH" && r.ok());
  await page.getByTestId("groesse-verlauf").click();
  await page.getByRole("menuitem", { name: "Standardgröße" }).click();
  await gespeichert;
  await expect(page.getByTestId("system-karten").locator('[data-bereich="verlauf"]')).toHaveAttribute("data-breite", "2");
  // Konten: Zwei-Faktor-Anmeldung freiwillig, direkter Weg zur Einstellung (4.2)
  await expect(page.getByTestId("epm-karte")).toContainText("Zwei-Faktor-Anmeldung");
  await expect(page.getByTestId("epm-karte").getByRole("link", { name: "ändern" })).toHaveAttribute("href", "/admin/benutzer#anmeldung");
  // Wartung des EPM: sofort mit Ergebnis (Reiter „Wartung“, Ergebnisse unter „Verlauf“)
  const reiter = page.getByTestId("system-reiter");
  await reiter.getByRole("tab", { name: "Wartung" }).click();
  await page.getByTestId("aufgabe-schutz_pruefen").getByRole("button", { name: "Unveränderlichkeit prüfen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Ausführen" }).click();
  await reiter.getByRole("tab", { name: /^Verlauf/ }).click();
  const zeile = page.getByTestId("auftraege").getByRole("row", { name: /Unveränderlichkeit prüfen/ }).first();
  await expect(zeile).toContainText("erledigt");
  await expect(zeile).toContainText("geschützten Tabellen in Ordnung");
  // Auftrag an den Server: der Agent führt ihn aus, das Ergebnis erscheint ohne Neuladen
  await reiter.getByRole("tab", { name: "Wartung" }).click();
  await page.getByTestId("aktion-status_aktualisieren").getByRole("button", { name: "Status neu einlesen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Ausführen" }).click();
  await reiter.getByRole("tab", { name: /^Verlauf/ }).click();
  const auftrag = page.getByTestId("auftraege").getByRole("row", { name: /Status neu einlesen/ }).first();
  await expect(auftrag).toContainText("erledigt (Probelauf)", { timeout: 30_000 });
  await auftrag.getByRole("button", { name: "Ausgabe" }).click();
  await expect(page.getByTestId("auftrag-ausgabe")).toContainText("Status wird gemessen");
  merken("system", { taetigkeit: "Status neu einlesen" });
});

test("System: EPM aus der Oberfläche aktualisieren", async ({ page }) => {
  // Wunsch 07.10.2026 (F123): spätere Stände ohne Terminal einspielen
  await page.goto("/admin/system?reiter=wartung");
  const karte = page.getByTestId("aktion-epm_update");
  await expect(karte).toContainText("sudo epm-update");
  await expect(karte).toContainText("Passwort + 2FA");
  await karte.getByRole("button", { name: "EPM aktualisieren" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("kurz nicht erreichbar");
  await dialog.getByLabel("Ihr Passwort").fill(KENNWORT);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(naechsterNotfallcode("e2e.admin"));
  await dialog.getByRole("button", { name: "Bestätigen und ausführen" }).click();
  await expect(dialog).toHaveCount(0);
  await page.getByTestId("system-reiter").getByRole("tab", { name: /^Verlauf/ }).click();
  const auftrag = page.getByTestId("auftraege").getByRole("row", { name: /EPM aktualisieren/ }).first();
  await expect(auftrag).toContainText("erledigt (Probelauf)", { timeout: 60_000 });
  await auftrag.getByRole("button", { name: "Ausgabe" }).click();
  await expect(page.getByTestId("auftrag-ausgabe")).toContainText("epm-update");
});

test("System: Neustart nur mit Passwort und 2FA, vorher Warnung an alle Benutzer", async ({ page, browser }) => {
  await page.goto("/admin/system?reiter=wartung");
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
  await page.getByTestId("system-reiter").getByRole("tab", { name: /^Verlauf/ }).click();
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
  await page.getByTestId("system-reiter").getByRole("tab", { name: /^Anmeldungen und Hinweis/ }).click();
  await page.getByTestId("hinweis-karte").getByRole("button", { name: "Beenden" }).click();
  await expect(page.getByTestId("aktiver-hinweis")).toHaveCount(0);
  await p.reload();
  await expect(p.getByRole("heading", { name: "Patienten", level: 1 })).toBeVisible();
  await expect(p.getByTestId("systemhinweis")).toHaveCount(0);
  await ctx.close();
});

test("System: eigener Hinweis an alle Benutzer und Eintrag im Audit-Log", async ({ page, browser }) => {
  await page.goto("/admin/system?reiter=anmeldungen");
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

test("Systemverwaltung: Ampel, häufige Aufgaben, Graph im Dialog; Wartung ohne SSH (Dienste, Software, Zertifikat, Protokolle)", async ({ page }) => {
  // Wunsch 10.10.2026 (F179): alles aus der Oberfläche, nichts mehr per SSH
  await page.goto("/");
  await (await adminNavigation(page)).getByRole("link", { name: "Systemverwaltung" }).click();
  await expect(page.getByRole("heading", { name: "Systemverwaltung", level: 1 })).toBeVisible();
  for (const id of ["agent", "dienste", "platte", "updates", "zertifikat", "sicherung", "uebertragung", "auftraege"]) {
    await expect(page.getByTestId(`ampel-${id}`)).toBeVisible();
  }
  await expect(page.getByTestId("ampel-agent")).toHaveAttribute("data-stand", "ok");
  await expect(page.getByTestId("ampel-dienste")).toContainText("laufen");
  await expect(page.getByTestId("aufgaben")).toContainText("Jetzt sichern");
  // Graph klein, groß erst im Dialog
  await page.getByTestId("auslastung-gross").click();
  await expect(page.getByRole("dialog").getByTestId("verlauf")).toBeVisible();
  await page.keyboard.press("Escape");
  // Ampel führt zum passenden Reiter
  await page.getByTestId("ampel-zertifikat").click();
  await expect(page).toHaveURL(/reiter=zertifikat/);
  await expect(page.getByTestId("zertifikat-karte")).toContainText("Gültig bis");
  await expect(page.getByTestId("zertifikat-ablauf")).not.toHaveText("—");
  // Dienste einzeln neu starten (Probelauf), mit Passwort und 2FA
  await page.getByTestId("system-reiter").getByRole("tab", { name: "Wartung" }).click();
  await page.getByTestId("dienst-ocr").getByRole("button", { name: "ocr neu starten" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Beginn").selectOption("0");
  await dialog.getByLabel("Ihr Passwort").fill(KENNWORT);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(naechsterNotfallcode("e2e.admin"));
  await dialog.getByRole("button", { name: "Bestätigen und neu starten" }).click();
  await expect(dialog).toHaveCount(0);
  await page.getByTestId("system-reiter").getByRole("tab", { name: /^Verlauf/ }).click();
  await expect(page.getByTestId("auftraege").getByRole("row", { name: /Dienst neu starten/ }).first()).toContainText("erledigt (Probelauf)", { timeout: 30_000 });
  // Software: Versionen vom Server, Paket-Upload
  await page.getByTestId("system-reiter").getByRole("tab", { name: "Software" }).click();
  await expect(page.getByTestId("versionen")).toContainText("läuft");
  await expect(page.getByTestId("paket-karte")).toContainText("Update-Paket einspielen");
  // Protokolle: nur lesend, abrufen, filtern, herunterladen
  await page.getByTestId("system-reiter").getByRole("tab", { name: "Protokolle" }).click();
  await page.getByTestId("protokolle").getByLabel("Protokoll").selectOption("web");
  await page.getByTestId("protokolle").getByLabel("Zeilen").selectOption("100");
  await page.getByTestId("protokolle").getByRole("button", { name: "Abrufen" }).click();
  await expect(page.getByTestId("protokoll-text")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("protokoll-herunterladen")).toHaveAttribute("href", /\/api\/system\/protokolle\/.+\?herunterladen=1/);
});
