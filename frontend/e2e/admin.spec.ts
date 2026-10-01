/** Entwürfe 17, 18, 20 · Administration: Benutzer, Rechte je Gruppe, Vorlagen, Audit-Log; Zugriff nur mit Recht. */
import { expect, test } from "@playwright/test";
import { BASIS, apiAls, eindeutig, zustand } from "./hilfen";
import { request } from "@playwright/test";

test.use({ storageState: zustand("admin") });

const PNG_1x1 = Buffer.from("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6300010000050001" +
  "0d0a2db40000000049454e44ae426082", "hex");
const SVG_LOGO = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="200" viewBox="0 0 600 200">' +
  '<rect width="600" height="200" fill="#251F53"/><text x="24" y="120" font-size="64" fill="#E8BD76">E2E Logo</text></svg>');
const SVG_SKRIPT = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="200"><script>alert(1)</script></svg>');

test("Benutzer anlegen, Einmal-Kennwort, sperren und entsperren", async ({ page }) => {
  const name = eindeutig("e2e.neu");
  await page.goto("/");
  await page.getByRole("navigation", { name: "Administration" }).getByRole("link", { name: "Benutzer" }).click();
  await page.getByRole("button", { name: "Benutzer anlegen" }).click();
  const detail = page.getByTestId("benutzer-detail");
  await detail.getByLabel("Titel").selectOption("Dr. med.");
  await detail.getByLabel("Vorname").fill("Henrike");
  await detail.getByLabel("Nachname").fill("Heilmann");
  await detail.getByLabel("Kürzel").fill("HH");
  await detail.getByLabel("Funktion").fill("Ärztin");
  await detail.getByLabel("Benutzername").fill(name);
  await detail.getByLabel("Rolle").selectOption("mediziner");
  await expect(detail).toContainText("Anzeige in der Akte: Dr. med. H. Heilmann");
  await detail.getByRole("button", { name: "Anlegen und Einmal-Kennwort erzeugen" }).click();
  const kennwortBox = detail.getByTestId("einmal-kennwort");
  await expect(kennwortBox).toBeVisible();
  const einmal = (await kennwortBox.locator(".num").first().textContent())?.trim() ?? "";
  expect(einmal.length).toBeGreaterThan(8);
  await expect(page.getByTestId("benutzerliste")).toContainText("Dr. med. H. Heilmann");
  await expect(detail).toContainText("Einrichtung offen");

  // mit dem Einmal-Kennwort beginnt die erste Anmeldung
  const ctx = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true });
  await ctx.get("/api/auth/status/");
  const csrf = (await ctx.storageState()).cookies.find((c) => c.name === "epm_csrf")?.value ?? "";
  const r = await ctx.post("/api/auth/anmelden/", { data: { benutzername: name, kennwort: einmal }, headers: { "X-CSRFToken": csrf, Referer: `${BASIS}/` } });
  expect((await r.json()).schritt).toBe("kennwort_aendern");
  await ctx.dispose();

  // sperren und entsperren
  await detail.getByRole("button", { name: "Sperren" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Benutzer sperren" }).click();
  await expect(page.getByText("Benutzer gesperrt.")).toBeVisible();
  await expect(detail).toContainText("gesperrt");
  await detail.getByRole("button", { name: "Entsperren" }).click();
  await expect(page.getByText("Benutzer entsperrt.")).toBeVisible();

  // neues Einmal-Kennwort
  await detail.getByRole("button", { name: "Einmal-Kennwort erzeugen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Einmal-Kennwort erzeugen" }).click();
  await expect(page.getByText("Neues Einmal-Kennwort erzeugt.")).toBeVisible();
  const zweites = (await kennwortBox.locator(".num").first().textContent())?.trim() ?? "";
  expect(zweites).not.toBe(einmal);

  // Audit-Log: Benutzer angelegt und gesperrt
  await page.getByRole("navigation", { name: "Administration" }).getByRole("link", { name: "Audit-Log" }).click();
  await page.getByRole("button", { name: "Benutzer", exact: true }).click();
  const log = page.getByTestId("auditlog");
  await expect(log).toContainText(name);
  await expect(log.getByRole("row").filter({ hasText: name }).first()).toContainText("Benutzer");
});

test("Rechte je Gruppe: Admin erlaubt Mitarbeitern Pläne, wirkt sofort, Standard wiederherstellen", async ({ page }) => {
  const mitarbeiter = await apiAls("mitarbeiter");
  const admin = await apiAls("admin");
  try {
    expect((await mitarbeiter.get("auth/ich/")).rechte).not.toContain("plaene_anlegen");
    await page.goto("/admin/benutzer");
    const rechte = page.getByTestId("rechte");
    // feste Rechte lassen sich nicht entziehen
    await expect(rechte.getByRole("checkbox", { name: "Admin: Benutzer und Rechte verwalten" })).toBeDisabled();
    await rechte.getByRole("checkbox", { name: "Mitarbeiter: Infusionspläne anlegen" }).check();
    await rechte.getByRole("button", { name: "Speichern (1)" }).click();
    await expect(page.getByText("Rechte gespeichert. Sie gelten ab sofort.")).toBeVisible();
    expect((await mitarbeiter.get("auth/ich/")).rechte).toContain("plaene_anlegen");

    // Mitarbeiter sieht jetzt „Neuer Plan“ in der Akte
    const ctx = await page.context().browser()!.newContext({ storageState: zustand("mitarbeiter"), ignoreHTTPSErrors: true });
    const mp = await ctx.newPage();
    await mp.goto("/patienten");
    await mp.getByTestId("patientenliste").getByRole("link", { name: "Probe, Jonas" }).click();
    await expect(mp.getByTestId("aktenkopf").getByRole("button", { name: "Neuer Plan" })).toBeVisible();
    await ctx.close();

    await rechte.getByRole("button", { name: "Standard" }).click();
    await rechte.getByRole("button", { name: /^Speichern \(\d+\)$/ }).click();
    await expect(page.getByText("Rechte gespeichert. Sie gelten ab sofort.")).toBeVisible();
    expect((await mitarbeiter.get("auth/ich/")).rechte).not.toContain("plaene_anlegen");
  } finally {
    // Ausgangsstand für die übrigen Tests, auch wenn oben etwas fehlschlägt
    const r = await admin.get("rechte/");
    const standard = Object.fromEntries(r.rollen.map((ro: { code: string }) => [ro.code,
      Object.fromEntries(r.rechte.map((x: { code: string }) => [x.code, r.standard[ro.code].includes(x.code) || r.fest.some((f: string[]) => f[0] === ro.code && f[1] === x.code)]))]));
    await admin.put("rechte/", { matrix: standard });
    await mitarbeiter.ende();
    await admin.ende();
  }
});

test("Vorlagen: Logo, Absender, Auswahllisten mit Reihenfolge, Grenzwerte", async ({ page }) => {
  const admin = await apiAls("admin");
  await page.goto("/admin/vorlagen");

  // Logo: zu klein und mit Skript abgewiesen, gültiges SVG angenommen
  const logo = page.getByTestId("logo");
  await logo.getByLabel("Logo-Datei").setInputFiles({ name: "klein.png", mimeType: "image/png", buffer: PNG_1x1 });
  await expect(logo.getByRole("alert")).toContainText("nötig sind mindestens 600 px");
  await logo.getByLabel("Logo-Datei").setInputFiles({ name: "boese.svg", mimeType: "image/svg+xml", buffer: SVG_SKRIPT });
  await expect(logo.getByRole("alert")).toContainText("SVG mit Skripten");
  await logo.getByLabel("Logo-Datei").setInputFiles({ name: "logo.svg", mimeType: "image/svg+xml", buffer: SVG_LOGO });
  await expect(page.getByText("Neues Logo gespeichert.")).toBeVisible();
  await expect(logo).toContainText("öffnen");
  const bild = await page.request.get("/api/briefkopf/logo/");
  expect(bild.headers()["content-type"]).toBe("image/svg+xml");

  // Absender: Telefon ändern, Vorschau, gespeichert
  const absender = page.getByTestId("absender");
  const vorher = (await admin.get("briefkopf/")).absender.stiftung.telefon;
  await absender.getByLabel("Telefon").fill("0251 98 11 499");
  await expect(page.getByTestId("briefkopf-vorschau")).toContainText("Tel. 0251 98 11 499");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Briefkopf gespeichert.")).toBeVisible();
  expect((await admin.get("briefkopf/")).absender.stiftung.telefon).toBe("0251 98 11 499");
  await admin.patch("briefkopf/", { absender: { stiftung: { telefon: vorher } } });

  // Auswahllisten: Terminort anlegen, ausblenden, Reihenfolge per Tastatur
  await page.getByRole("button", { name: "Auswahllisten" }).click();
  await page.getByRole("navigation", { name: "Listen" }).getByRole("button", { name: /^Terminorte/ }).click();
  const liste = page.getByTestId("liste");
  const ort = eindeutig("Praxis E2E ");
  await liste.getByRole("button", { name: "Wert" }).click();
  await page.getByRole("dialog").getByLabel("Wert").fill(ort);
  await page.getByRole("dialog").getByRole("button", { name: "Speichern" }).click();
  await expect(liste.getByRole("button", { name: ort })).toBeVisible();
  await liste.getByRole("button", { name: `${ort} verschieben (Pfeiltasten)` }).press("ArrowUp");
  await expect(page.getByText("Reihenfolge gespeichert.")).toBeVisible();
  const orte = await admin.get("auswahlwerte/?liste=terminort");
  expect(orte.map((o: { wert: string }) => o.wert).indexOf(ort)).toBe(orte.length - 2);
  await liste.getByRole("checkbox", { name: `${ort} in der Auswahl` }).uncheck();
  await expect(liste.getByRole("row").filter({ hasText: ort })).toContainText("ausgeblendet");
  expect((await admin.get("auswahlwerte/?liste=terminort")).find((o: { wert: string }) => o.wert === ort).aktiv).toBe(false);

  // Grenzwerte: untere Grenze größer als obere wird abgewiesen, gültiger Wert gespeichert
  await page.getByRole("button", { name: "Grenzwerte" }).click();
  const grenzen = page.getByTestId("grenzwerte");
  await grenzen.getByLabel("Gewicht minimal").fill("300");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(grenzen.getByText("Untere Grenze muss kleiner als obere Grenze sein.")).toBeVisible();
  await grenzen.getByLabel("Gewicht minimal").fill("20");
  await grenzen.getByLabel("Kontakt überfällig nach").fill("13");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Grenzwerte gespeichert.")).toBeVisible();
  expect((await admin.get("einstellungen/")).kontakt_ueberfaellig_monate).toBe(13);
  await admin.patch("einstellungen/", { kontakt_ueberfaellig_monate: 12 });
  await admin.ende();
});

test("Ohne Recht keine Administration: Mitarbeiter sieht nichts, Mediziner Vorlagen und Audit-Log", async ({ browser }) => {
  const m = await browser.newContext({ storageState: zustand("mitarbeiter"), ignoreHTTPSErrors: true });
  const mp = await m.newPage();
  await mp.goto("/");
  await expect(mp.getByRole("navigation", { name: "Administration" })).toHaveCount(0);
  await mp.goto("/admin/benutzer");
  await expect(mp.getByText("Für „Benutzer“ fehlt das Recht.")).toBeVisible();
  await m.close();
  const d = await browser.newContext({ storageState: zustand("mediziner"), ignoreHTTPSErrors: true });
  const dp = await d.newPage();
  await dp.goto("/");
  const nav = dp.getByRole("navigation", { name: "Administration" });
  await expect(nav.getByRole("link", { name: "Vorlagen" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Audit-Log" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Benutzer" })).toHaveCount(0);
  await d.close();
});
