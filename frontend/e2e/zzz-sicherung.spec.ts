/**
 * Entwurf 11 · Administration › Backup (F61–F64, O-07, O-23) gegen den echten Stack: Der Systemagent läuft in CI im
 * Probelauf, Sicherung, Übertragung und Wiederherstellen aber echt (werkzeuge/ci-stack.sh: epm-backup.sh aus dem Repo,
 * GnuPG, rclone gegen einen lokalen WebDAV-Server).
 *
 * Läuft als letzte Datei (nach zz-neustart.spec.ts): Das Wiederherstellen spielt die Datenbank zurück und beendet alle
 * Anmeldungen – auch die gespeicherten Sitzungen der übrigen Tests.
 */
import { execSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, request, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { BASIS, KENNWORT, anmeldenUI, apiAls, eindeutig, naechsterNotfallcode, zustand } from "./hilfen";

test.describe.configure({ mode: "serial" });
test.use({ storageState: zustand("admin") });

const B = process.env.EPM_CI_BASIS ?? "/tmp/epm-ci";
const WEBDAV = process.env.EPM_CI_WEBDAV ?? "/tmp/epm-ci-webdav";
const ORDNER = "EPM-Sicherungen";
let passwort = "";

type Auftrag = { kennung: string; status: string; ergebnis: string; ausgabe: string; aktion: string };
type Sicherung = { stempel: string; verschluesselt: boolean; passwort_nr: number | null; art: string; uebertragen: boolean;
  dateien: string[] };

async function stand(page: Page) {
  const r = await page.request.get("/api/backup/");
  expect(r.ok(), `GET /api/backup/ → ${r.status()}`).toBeTruthy();
  return (await r.json()) as { auftraege: Auftrag[]; sicherungen: Sicherung[]; ziel: { eingerichtet: boolean } };
}

/** Wartet, bis der Systemagent den Auftrag erledigt hat (Ergebnis kommt über die Seite bzw. die API). */
async function abwarten(page: Page, kennung: string, timeout = 90_000) {
  let a: Auftrag | undefined;
  await expect.poll(async () => {
    a = (await stand(page)).auftraege.find((x) => x.kennung === kennung);
    return a?.status;
  }, { timeout, intervals: [1000, 2000] }).toMatch(/^(erledigt|fehler)$/);
  expect(a?.status, `${a?.aktion}: ${a?.ergebnis}\n${a?.ausgabe}`).toBe("erledigt");
  return a!;
}

/** Klick, der einen Auftrag anlegt; liefert den Auftrag aus der Antwort. */
async function auftragDurch(page: Page, pfad: string, klick: () => Promise<void>) {
  const antwort = page.waitForResponse((r) => r.url().endsWith(`/api/backup/${pfad}`) && r.request().method() === "POST");
  await klick();
  const r = await antwort;
  expect(r.status(), await r.text()).toBe(201);
  return (await r.json()) as Auftrag;
}

async function jetztSichern(page: Page) {
  const a = await auftragDurch(page, "jetzt/", async () => {
    await page.getByRole("button", { name: "Jetzt sichern" }).first().click();
    await page.getByRole("dialog").getByRole("button", { name: "Jetzt sichern" }).click();
  });
  await abwarten(page, a.kennung);
  return (await stand(page)).sicherungen[0];
}

/** Datei aus dem Backup-Ordner (nur root) entschlüsseln – wie auf dem Passwortblatt beschrieben. */
function entschluesseln(datei: string, mitPasswort: string): Buffer {
  const ordner = mkdtempSync(join(tmpdir(), "epm-gpg-"));
  try {
    writeFileSync(join(ordner, "datei.gpg"), execSync(`sudo cat ${datei}`));
    return execSync(`gpg --homedir ${ordner} --batch --quiet --pinentry-mode loopback --passphrase-fd 0 -d ${join(ordner, "datei.gpg")}`,
      { input: mitPasswort, stdio: ["pipe", "pipe", "pipe"] });
  } finally {
    try { execSync(`gpgconf --homedir ${ordner} --kill all`, { stdio: "ignore" }); } catch { /* egal */ }
    rmSync(ordner, { recursive: true, force: true });
  }
}

test("Backup: nur mit Recht „Sicherungen verwalten“; Sicherungs-Passwort festlegen und Passwortblatt drucken", async ({ page, browser }) => {
  for (const rolle of ["mediziner", "mitarbeiter", "betrachter"] as const) {
    const ctx = await browser.newContext({ storageState: zustand(rolle), ignoreHTTPSErrors: true });
    const p = await ctx.newPage();
    await p.goto("/admin/backup");
    await expect(p).toHaveURL(/\/$/);
    await expect(p.getByRole("link", { name: "Backup", exact: true })).toHaveCount(0);
    expect((await p.request.get("/api/backup/")).status()).toBe(403);
    await ctx.close();
  }

  await page.goto("/");
  await page.getByRole("navigation", { name: "Administration" }).getByRole("link", { name: "Backup" }).click();
  await expect(page.getByRole("heading", { name: "Backup und Wiederherstellung", level: 1 })).toBeVisible();
  await expect(page.getByTestId("agent-fehlt")).toHaveCount(0);
  const karte = page.getByTestId("verschluesselung");
  await expect(karte).toContainText("Noch kein Sicherungs-Passwort");
  await karte.getByRole("button", { name: "Passwort festlegen" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Vorschlag erzeugen" }).click();
  passwort = await dialog.getByLabel("Neues Sicherungs-Passwort").inputValue();
  expect(passwort).toMatch(/^[a-km-zA-HJ-NP-Z2-9]{5}(-[a-km-zA-HJ-NP-Z2-9]{5}){3}$/);
  await expect(dialog.getByLabel("Sicherungs-Passwort wiederholen")).toHaveValue(passwort);
  await dialog.getByLabel("Ihr Passwort").fill(KENNWORT);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(naechsterNotfallcode("e2e.admin"));
  await dialog.getByRole("button", { name: "Bestätigen und festlegen" }).click();
  await expect(dialog.getByTestId("passwort-ergebnis")).toContainText("Sicherungs-Passwort Nr. 1 festgelegt", { timeout: 60_000 });

  // Passwortblatt: enthält das Passwort (vom Server gegen den Prüfwert geprüft)
  await dialog.getByRole("button", { name: "Passwortblatt drucken" }).click();
  const blatt = page.getByTestId("pdf-dialog").getByTestId("pdf-text").first();
  await expect(blatt).toContainText(passwort);
  await expect(blatt).toContainText("Sicherungs-Passwort");
  await expect(blatt).toContainText("Nr. 1");
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").getByRole("button", { name: "Fertig" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(karte).toContainText("Nr. 1");
  await expect(karte.getByRole("button", { name: "Neues Passwort festlegen" })).toBeVisible();

  // Das Passwort steht nur auf dem Server – nicht in der Datenbank, nicht im Status für den Container
  expect(execSync(`sudo cat ${B}/konf-sicherung/passwort-1`).toString()).toBe(passwort);
  expect(execSync(`sudo stat -c %a ${B}/konf-sicherung/passwort-1`).toString().trim()).toBe("600");
  const dump = execSync(`sudo docker compose -p epm-ci exec -T db pg_dump -U epm -d epm --data-only`, { cwd: B, maxBuffer: 1 << 28 });
  expect(dump.includes(Buffer.from(passwort))).toBe(false);
  for (const name of readdirSync(`${B}/system/status`).filter((n) => n.endsWith(".json"))) {
    expect(readFileSync(`${B}/system/status/${name}`, "utf8")).not.toContain(passwort);
  }
});

test("Backup: „Jetzt sichern“ verschlüsselt mit dem Passwort aus der Oberfläche; Passwort prüfen", async ({ page }) => {
  expect(passwort, "Passwort aus dem Test davor").not.toBe("");
  await page.goto("/admin/backup");
  const s = await jetztSichern(page);
  expect([s.verschluesselt, s.passwort_nr, s.art]).toEqual([true, 1, "von_hand"]);
  const zeile = page.getByTestId(`sicherung-${s.stempel}`);
  await expect(zeile).toContainText("verschlüsselt");
  await expect(zeile).toContainText("Von Hand · e2e.admin");
  await expect(page.getByTestId("letzte-sicherung")).toContainText("heute");

  // Auf dem Server: mit dem Passwort lesbar (pg_dump-Format), mit einem anderen nicht; Prüfsummen stimmen
  for (const datei of s.dateien) expect(datei).toMatch(/\.gpg$/);
  const db = s.dateien.find((d) => d.startsWith("epm-db_"))!;
  expect(entschluesseln(`${B}/backup/${db}`, passwort).subarray(0, 5).toString()).toBe("PGDMP");
  expect(() => entschluesseln(`${B}/backup/${db}`, "ein-anderes-Passwort-2026")).toThrow();
  execSync(`sudo sh -c 'cd ${B}/backup && sha256sum -c epm_${s.stempel}.sha256'`, { stdio: "pipe" });

  // Passwort prüfen (z. B. das Blatt aus dem Tresor)
  await page.getByTestId("verschluesselung").getByRole("button", { name: "Passwort prüfen" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Sicherungs-Passwort").fill(`${passwort}x`);
  await dialog.getByRole("button", { name: "Prüfen" }).click();
  await expect(dialog).toContainText("Passt zu keinem hinterlegten Sicherungs-Passwort");
  await dialog.getByLabel("Sicherungs-Passwort").fill(passwort);
  await dialog.getByRole("button", { name: "Prüfen" }).click();
  await expect(dialog).toContainText("Stimmt: Passwort Nr. 1 (aktuell)");
  await dialog.getByRole("button", { name: "Schließen" }).click();
});

test("Backup: Übertragungsziel festlegen, Verbindung testen, von Hand und im Zeitfenster übertragen; Startseite", async ({ page, browser }) => {
  test.setTimeout(360_000);
  await page.goto("/admin/backup");
  const karte = page.getByTestId("uebertragung");
  await expect(karte).toContainText("Noch kein Übertragungsziel");
  // Zeitfenster, das gerade nicht offen ist (in jeder Zeitzone): die Übertragung startet nicht von selbst
  const h = new Date().getUTCHours();
  const um = (x: number) => `${String((h + x) % 24).padStart(2, "0")}:00`;
  await karte.getByRole("button", { name: "Ziel festlegen" }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("WebDAV-Adresse").fill("http://127.0.0.1:8099");
  await dialog.getByLabel("Benutzer").fill("epm-ci");
  await dialog.getByLabel("Passwort für das Ziel").fill("WebDAV-Test-2026");
  await expect(dialog.getByLabel("Ordner im Ziel")).toHaveValue(ORDNER);
  await dialog.getByLabel("Zeitfenster von").fill(um(10));
  await dialog.getByLabel("bis", { exact: true }).fill(um(11));
  await dialog.getByLabel("Ihr Passwort").fill(KENNWORT);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(naechsterNotfallcode("e2e.admin"));
  let a = await auftragDurch(page, "ziel/", () => dialog.getByRole("button", { name: "Bestätigen und speichern" }).click());
  await abwarten(page, a.kennung);
  await expect(karte).toContainText("http://127.0.0.1:8099");
  await expect(karte).toContainText(`${um(10)}–${um(11)} Uhr`);
  // Zugang nur auf dem Server (rclone, verschleiert, 0600), nicht in der Datenbank
  expect(execSync(`sudo stat -c %a ${B}/konf-sicherung/rclone.conf`).toString().trim()).toBe("600");
  expect(execSync(`sudo cat ${B}/konf-sicherung/rclone.conf`).toString()).not.toContain("WebDAV-Test-2026");

  a = await auftragDurch(page, "ziel/testen/", () => karte.getByRole("button", { name: "Verbindung testen" }).click());
  expect((await abwarten(page, a.kennung)).ergebnis).toContain("Verbindung in Ordnung");
  const verschluesselt = (await stand(page)).sicherungen.find((x) => x.verschluesselt)!;
  await expect(page.getByTestId(`sicherung-${verschluesselt.stempel}`)).toContainText("wartet auf Zeitfenster");

  // von Hand: nur verschlüsselte Sicherungen, mit Prüfsummen und Angaben
  a = await auftragDurch(page, "uebertragen/", async () => {
    await karte.getByRole("button", { name: "Jetzt übertragen" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Jetzt übertragen" }).click();
  });
  expect((await abwarten(page, a.kennung)).ergebnis).toContain("übertragen und geprüft");
  await expect(page.getByTestId(`sicherung-${verschluesselt.stempel}`)).toContainText("übertragen");
  const imZiel = readdirSync(join(WEBDAV, ORDNER));
  for (const datei of verschluesselt.dateien) expect(imZiel).toContain(datei);
  expect(imZiel).toContain(`epm_${verschluesselt.stempel}.sha256`);
  for (const datei of imZiel) expect(datei).toMatch(/\.gpg$|^epm_.*\.(sha256|json)$/);
  const db = verschluesselt.dateien.find((d) => d.startsWith("epm-db_"))!;
  expect(readFileSync(join(WEBDAV, ORDNER, db)).subarray(0, 5).toString()).not.toBe("PGDMP");

  // im Zeitfenster von selbst: neue Sicherung, Zeitfenster ganztägig (Passwort für das Ziel bleibt)
  const neu = await jetztSichern(page);
  await expect(page.getByTestId(`sicherung-${neu.stempel}`)).toContainText("wartet auf Zeitfenster");
  await karte.getByRole("button", { name: "Ziel ändern" }).click();
  dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("WebDAV-Adresse")).toHaveValue("http://127.0.0.1:8099");
  await dialog.getByLabel("Zeitfenster von").fill("00:00");
  await dialog.getByLabel("bis", { exact: true }).fill("00:00");
  await dialog.getByLabel("Ihr Passwort").fill(KENNWORT);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(naechsterNotfallcode("e2e.admin"));
  a = await auftragDurch(page, "ziel/", () => dialog.getByRole("button", { name: "Bestätigen und speichern" }).click());
  await abwarten(page, a.kennung);
  await expect(karte).toContainText("ganztägig");
  await expect.poll(async () => (await stand(page)).sicherungen.find((x) => x.stempel === neu.stempel)?.uebertragen,
    { timeout: 240_000, intervals: [5000] }).toBe(true);
  expect(readdirSync(join(WEBDAV, ORDNER))).toContain(neu.dateien.find((d) => d.startsWith("epm-db_")));
  await page.reload();
  await expect(page.getByTestId(`sicherung-${neu.stempel}`)).toContainText("übertragen");

  // Startseite (O-07): alle sehen den Zustand, nur mit dem Recht führt er zur Seite Backup
  const ctx = await browser.newContext({ storageState: zustand("mitarbeiter"), ignoreHTTPSErrors: true });
  const p = await ctx.newPage();
  await p.goto("/");
  await expect(p.getByTestId("backup-status")).toContainText(/Backup heute \d{2}:\d{2} erfolgreich/);
  await expect(p.getByRole("link", { name: /Backup heute/ })).toHaveCount(0);
  await ctx.close();
  await page.goto("/");
  await page.getByRole("link", { name: /Backup heute \d{2}:\d{2} erfolgreich/ }).click();
  await expect(page.getByRole("heading", { name: "Backup und Wiederherstellung", level: 1 })).toBeVisible();
});

test("Backup: Wiederherstellen mit Passwort und 2FA – Stand der Sicherung zurück, alle neu anmelden, Audit-Log", async ({ page }) => {
  test.setTimeout(480_000);
  await page.goto("/admin/backup");
  const s = await jetztSichern(page);
  // nach der Sicherung: ein neuer Benutzer (darf nach dem Wiederherstellen nicht mehr da sein)
  const admin = await apiAls("admin");
  const nachher = await admin.post("benutzer/", { username: eindeutig("e2e.nachher"), first_name: "Nora", last_name: "Nachher",
    rolle: "betrachter" });
  await admin.ende();
  expect((await page.request.get(`/api/benutzer/${nachher.id}/`)).status()).toBe(200);

  await page.reload();
  await page.getByTestId(`sicherung-${s.stempel}`).getByRole("button", { name: /wiederherstellen$/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Datenbank und Dokumente werden durch diesen Stand ersetzt");
  await dialog.getByLabel("Beginn").selectOption("0");
  await dialog.getByLabel("Ihr Passwort").fill(KENNWORT);
  await dialog.getByLabel("Code aus der Authenticator-App").fill(naechsterNotfallcode("e2e.admin"));
  const a = await auftragDurch(page, `${s.stempel}/wiederherstellen/`,
    () => dialog.getByRole("button", { name: "Bestätigen und wiederherstellen" }).click());
  expect(a.status).toBe("wartet");
  await expect(page.getByTestId("wiederherstellen-laeuft")).toBeVisible();

  // Backend startet mit der zurückgespielten Datenbank: alle Anmeldungen sind beendet
  await expect.poll(async () => {
    try {
      const r = await page.request.get("/api/auth/status/", { timeout: 10_000 });
      return r.ok() ? (await r.json()).schritt : `HTTP ${r.status()}`;
    } catch {
      return "nicht erreichbar";
    }
  }, { timeout: 360_000, intervals: [3000] }).toBe("anmelden");
  const mitarbeiter = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true, storageState: zustand("mitarbeiter") });
  expect((await (await mitarbeiter.get("/api/auth/status/")).json()).schritt).toBe("anmelden");
  await mitarbeiter.dispose();

  // neu anmelden: Auftrag erledigt, Stand vorher als eigene Sicherung, Eintrag im Audit-Log, späterer Benutzer weg
  await anmeldenUI(page, "e2e.admin", naechsterNotfallcode("e2e.admin"));
  await expect(page.getByRole("navigation", { name: "Hauptnavigation" })).toBeVisible();
  await page.goto("/admin/backup");
  const fertig = await abwarten(page, a.kennung, 120_000);
  expect(fertig.ergebnis).toContain("Sicherung wiederhergestellt");
  const zeile = page.getByTestId("auftraege").getByRole("row", { name: /Sicherung wiederherstellen/ }).first();
  await expect(zeile).toContainText("erledigt");
  await expect(zeile).toContainText(s.stempel);
  const sicherungen = (await stand(page)).sicherungen;
  expect(sicherungen[0].art).toBe("vor_wiederherstellung");
  await expect(page.getByTestId(`sicherung-${sicherungen[0].stempel}`)).toContainText("Vor Wiederherstellung");
  expect((await page.request.get(`/api/benutzer/${nachher.id}/`)).status()).toBe(404);

  await page.goto("/admin/audit-log");
  await page.getByRole("button", { name: "Backup", exact: true }).click();
  await expect(page.getByText(/wiederhergestellt, alle Anmeldungen beendet – der Stand davor \(auch dieses Audit-Log\) ist in der Sicherung/).first())
    .toBeVisible();
  await expect(page.getByText("Sicherung wiederherstellen erledigt: Sicherung wiederhergestellt.", { exact: false }).first()).toBeVisible();
});
