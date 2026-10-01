/** Entwürfe 17, 18, 20 · Administration: Benutzer, Rechte je Gruppe, Vorlagen, Audit-Log; Zugriff nur mit Recht. */
import { expect, test } from "@playwright/test";
import { BASIS, OHNE_ANMELDUNG, apiAls, eindeutig, merken, neuesKonto, sitzungGilt, zustand } from "./hilfen";
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
  await sitzungGilt(page, "Benutzer anlegen");

  // mit dem Einmal-Kennwort beginnt die erste Anmeldung
  const ctx = await request.newContext({ baseURL: BASIS, ignoreHTTPSErrors: true, storageState: OHNE_ANMELDUNG });
  await ctx.get("/api/auth/status/");
  const csrf = (await ctx.storageState()).cookies.find((c) => c.name === "epm_csrf")?.value ?? "";
  const r = await ctx.post("/api/auth/anmelden/", { data: { benutzername: name, kennwort: einmal }, headers: { "X-CSRFToken": csrf, Referer: `${BASIS}/` } });
  expect((await r.json()).schritt).toBe("kennwort_aendern");
  await ctx.dispose();
  await sitzungGilt(page, "erste Anmeldung der neuen Person");

  // sperren und entsperren
  await detail.getByRole("button", { name: "Sperren" }).click();
  const gesperrt = page.waitForResponse((a) => a.url().endsWith("/sperren/"));
  await page.getByRole("dialog").getByRole("button", { name: "Benutzer sperren" }).click();
  const antwort = await gesperrt;
  expect(antwort.status(), await antwort.text()).toBe(200);
  await expect(page.getByText("Benutzer gesperrt.")).toBeVisible();
  await sitzungGilt(page, "Sperren");
  await expect(detail).toContainText("gesperrt");
  await detail.getByRole("button", { name: "Entsperren" }).click();
  await expect(page.getByText("Benutzer entsperrt.")).toBeVisible();

  // ändern: Funktion und Rolle
  await detail.getByLabel("Funktion").fill("Oberärztin");
  await detail.getByLabel("Rolle").selectOption("mitarbeiter");
  await detail.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Benutzer gespeichert.")).toBeVisible();
  await expect(page.getByTestId("benutzerliste").getByRole("row").filter({ hasText: name })).toContainText("Mitarbeiter");

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
  merken("benutzer", { name, anzeige: "Dr. med. H. Heilmann" });
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
    await expect(page.getByText("Rechte gespeichert. Sie gelten ab sofort.").last()).toBeVisible();
    expect((await mitarbeiter.get("auth/ich/")).rechte).not.toContain("plaene_anlegen");
  } finally {
    // Ausgangsstand für die übrigen Tests, auch wenn oben etwas fehlschlägt (ohne den ursprünglichen Fehler zu verdecken)
    try {
      const r = await admin.get("rechte/");
      const standard = Object.fromEntries(r.rollen.map((ro: { code: string }) => [ro.code,
        Object.fromEntries(r.rechte.map((x: { code: string }) => [x.code, r.standard[ro.code].includes(x.code) || r.fest.some((f: string[]) => f[0] === ro.code && f[1] === x.code)]))]));
      await admin.put("rechte/", { matrix: standard });
    } catch (fehler) {
      console.error("Rechte nicht auf Standard zurückgesetzt:", fehler);
    }
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
  await expect(liste.getByRole("button", { name: ort, exact: true })).toBeVisible();
  await liste.getByRole("button", { name: `${ort} verschieben (Pfeiltasten)` }).press("ArrowUp");
  await expect(page.getByText("Reihenfolge gespeichert.")).toBeVisible();
  const orte = await admin.get("auswahlwerte/?liste=terminort");
  expect(orte.map((o: { wert: string }) => o.wert).indexOf(ort)).toBe(orte.length - 2);
  await liste.getByRole("checkbox", { name: `${ort} in der Auswahl` }).uncheck();
  await expect(liste.getByRole("row").filter({ hasText: ort })).toContainText("ausgeblendet");
  await expect.poll(async () => (await admin.get("auswahlwerte/?liste=terminort")).find((o: { wert: string }) => o.wert === ort).aktiv).toBe(false);

  // Präparate: neues Vitamin anlegen und ausblenden (bleibt in alten Plänen, nicht mehr wählbar)
  await page.getByRole("navigation", { name: "Listen" }).getByRole("button", { name: /^Vitamine/ }).click();
  const vitamin = eindeutig("E2E-Vitamin ");
  await liste.getByRole("button", { name: "Präparat" }).click();
  await page.getByRole("dialog").getByLabel("Name").fill(vitamin);
  await page.getByRole("dialog").getByRole("button", { name: "Speichern" }).click();
  await expect(liste.getByRole("button", { name: vitamin, exact: true })).toBeVisible();
  await liste.getByRole("checkbox", { name: `${vitamin} in der Auswahl` }).uncheck();
  await expect(liste.getByRole("row").filter({ hasText: vitamin })).toContainText("ausgeblendet");
  await expect.poll(async () => {
    const vit = (await admin.get("praeparate/?kategorie=vitamine")).find((x: { name: string }) => x.name === vitamin);
    return [vit.aktiv, vit.kategorie];
  }).toEqual([false, "vitamine"]);

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
  merken("vorlagen", { ort, vitamin });
});

test("Administration je Recht: Betrachter sieht nichts, Mitarbeiter Vorlagen, Mediziner Vorlagen und Audit-Log", async ({ browser }) => {
  const b = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const bp = await b.newPage();
  await bp.goto("/");
  await expect(bp.getByRole("navigation", { name: "Administration" })).toHaveCount(0);
  await bp.goto("/admin/benutzer");
  await expect(bp.getByText("Für „Benutzer“ fehlt das Recht.")).toBeVisible();
  await b.close();
  // Vorlagen pflegen auch Mitarbeiter (Festlegung 01.10.2026)
  const m = await browser.newContext({ storageState: zustand("mitarbeiter"), ignoreHTTPSErrors: true });
  const mp = await m.newPage();
  await mp.goto("/");
  const mnav = mp.getByRole("navigation", { name: "Administration" });
  await expect(mnav.getByRole("link", { name: "Vorlagen" })).toBeVisible();
  await expect(mnav.getByRole("link", { name: "Audit-Log" })).toHaveCount(0);
  await expect(mnav.getByRole("link", { name: "Benutzer" })).toHaveCount(0);
  await mnav.getByRole("link", { name: "Vorlagen" }).click();
  await expect(mp.getByTestId("logo")).toBeVisible();
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

test("Fünf falsche Passwörter sperren das Konto; Admin sieht den Hinweis, setzt 2FA zurück und entsperrt", async ({ page, browser }) => {
  const konto = await neuesKonto("mitarbeiter", "Lotte", "Gesperrt");
  const fremd = await browser.newContext({ ignoreHTTPSErrors: true, storageState: OHNE_ANMELDUNG });
  const fp = await fremd.newPage();
  await fp.goto("/");
  for (let i = 0; i < 5; i++) {
    await fp.getByLabel("Benutzername").fill(konto.benutzername);
    await fp.getByLabel("Passwort").fill(`falsch-${i}-falsch-falsch`);
    await fp.getByRole("button", { name: "Weiter" }).click();
    await expect(fp.getByRole("alert")).toBeVisible();
  }
  await expect(fp.getByRole("alert")).toContainText("Das Konto ist gesperrt.");
  await fremd.close();

  await page.goto("/admin/audit-log");
  await expect(page.getByTestId("sperrhinweis").filter({ hasText: konto.benutzername })).toBeVisible();
  await page.getByRole("button", { name: "Fehlversuch" }).click();
  await expect(page.getByTestId("auditlog")).toContainText("L. Gesperrt");
  await page.getByTestId("sperrhinweis").filter({ hasText: konto.benutzername }).getByRole("link", { name: "Zum Benutzer" }).click();
  const detail = page.getByTestId("benutzer-detail");
  await expect(detail).toContainText("L. Gesperrt");
  await expect(detail).toContainText("Fehlversuche bei der Anmeldung");

  // 2FA zurücksetzen (Telefon verloren): neues Einmal-Kennwort, Authenticator weg
  await detail.getByRole("button", { name: "2FA zurücksetzen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "2FA zurücksetzen" }).click();
  await expect(page.getByText("2FA zurückgesetzt, neues Einmal-Kennwort erzeugt.")).toBeVisible();
  await expect(detail.getByTestId("einmal-kennwort")).toBeVisible();
  await detail.getByRole("button", { name: "Entsperren" }).click();
  await expect(page.getByText("Benutzer entsperrt.")).toBeVisible();
  await expect(page.getByTestId("benutzerliste").getByRole("row").filter({ hasText: konto.benutzername })).toContainText("2FA: nicht eingerichtet");
  merken("gesperrt", { benutzername: konto.benutzername });
});

test("Admin: echte Akten nur lesen, Testpatienten anlegen und bearbeiten", async ({ page }) => {
  const m = await apiAls("mitarbeiter");
  const echt = await m.post("patienten/", { nachname: eindeutig("Echt"), vorname: "Erna", geburtsdatum: "1960-06-06" });
  await m.ende();
  await page.goto(`/patienten/${echt.id}`);
  const kopf = page.getByTestId("aktenkopf");
  await expect(kopf.getByText("nur lesen")).toBeVisible();
  await expect(kopf.getByRole("button", { name: "Kontakt" })).toHaveCount(0);
  await expect(kopf.getByRole("button", { name: "Neuer Plan" })).toHaveCount(0);
  await expect(page.getByTestId("gewichtskarte").getByLabel("Neues Gewicht")).toHaveCount(0);
  await page.getByRole("button", { name: "Weitere Aktionen" }).click();
  await expect(page.getByRole("menuitem", { name: "Akte abschließen" })).toHaveCount(0);
  await expect(page.getByRole("menuitem", { name: "Stammdaten bearbeiten" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  // auch die API weist ab
  const admin = await apiAls("admin");
  const abgewiesen = await admin.roh.post("/api/kontakte/", { data: { patient: echt.id, text: "<p>x</p>" }, headers: await admin.kopf() });
  expect(abgewiesen.status()).toBe(403);
  expect((await abgewiesen.json()).fehler).toContain("nur bei Testpatienten");

  // Neuer Patient wird Testpatient, dort darf der Admin alles
  await page.goto("/patienten/neu");
  await expect(page.getByText("wird Testpatient")).toBeVisible();
  const nachname = eindeutig("Admintest");
  await page.getByLabel("Nachname").fill(nachname);
  await page.getByLabel("Vorname").fill("Anton");
  await page.getByLabel("Geburtsdatum").fill("03.03.1973");
  await page.getByRole("button", { name: "Anlegen und Akte öffnen" }).click();
  await expect(page).toHaveURL(/\/patienten\/\d+$/);
  const id = Number(page.url().split("/").pop());
  await expect(kopf.getByText("Testpatient")).toBeVisible();
  await kopf.getByRole("button", { name: "Kontakt" }).click();
  const neu = page.getByTestId("neuer-kontakt");
  await neu.getByRole("textbox", { name: "Neuer Kontakt" }).fill("Testkontakt der Administration");
  await neu.getByRole("button", { name: "Kontakt speichern" }).click();
  await expect(page.getByText("Kontakt gespeichert.")).toBeVisible();
  const p = await admin.get(`patienten/${id}/`);
  expect([p.ist_test, p.nummer >= 9001]).toEqual([true, true]);
  expect((await admin.get(`kontakte/?patient=${id}`)).results).toHaveLength(1);
  await admin.ende();
});

test("Testdaten auf Ausgangsstand zurücksetzen (nur Testpatienten)", async ({ page }) => {
  const admin = await apiAls("admin");
  const echte = (await admin.get("patienten/?test=ohne&seitengroesse=1")).count;
  await page.goto("/admin/benutzer");
  await page.getByTestId("benutzerliste").getByRole("button", { name: "T. Test", exact: true }).click();
  const detail = page.getByTestId("benutzer-detail");
  await expect(detail).toContainText("Testbenutzer:");
  await detail.getByRole("button", { name: "Testdaten auf Ausgangsstand zurücksetzen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Testdaten zurücksetzen" }).click();
  await expect(page.getByText(/Testdaten zurückgesetzt \(\d+ gelöscht, 6 angelegt\)/)).toBeVisible();
  expect((await admin.get("patienten/?test=ohne&seitengroesse=1")).count).toBe(echte);
  expect((await admin.get("patienten/?test=nur&seitengroesse=50")).results.map((p: { nachname: string }) => p.nachname).sort())
    .toEqual(["Beispiel", "Demo", "Musterfrau", "Mustermann", "Probe", "Test"]);
  await admin.ende();
});
