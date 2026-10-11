/** Entwürfe 17, 18, 20 · Administration: Benutzer, Rechte je Gruppe, Vorlagen, Audit-Log; Zugriff nur mit Recht. */
import { expect, test } from "@playwright/test";
import { BASIS, OHNE_ANMELDUNG, adminNavigation, apiAls, eindeutig, merken, neuesKonto, sitzungGilt, zustand } from "./hilfen";
import { request } from "@playwright/test";

test.use({ storageState: zustand("admin") });

const PNG_1x1 = Buffer.from("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6300010000050001" +
  "0d0a2db40000000049454e44ae426082", "hex");
const SVG_LOGO = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="200" viewBox="0 0 600 200">' +
  '<rect width="600" height="200" fill="#251F53"/><text x="24" y="120" font-size="64" fill="#E8BD76">E2E Logo</text></svg>');
const SVG_SKRIPT = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="200"><script>alert(1)</script></svg>');

test("Benutzer anlegen, Einmal-Passwort, sperren und entsperren", async ({ page }) => {
  const name = eindeutig("e2e.neu");
  await page.goto("/");
  await (await adminNavigation(page)).getByRole("link", { name: "Benutzer" }).click();
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
  await detail.getByRole("button", { name: "Anlegen und Einmal-Passwort erzeugen" }).click();
  const kennwortBox = detail.getByTestId("einmal-kennwort");
  await expect(kennwortBox).toBeVisible();
  const einmal = (await kennwortBox.locator(".num").first().textContent())?.trim() ?? "";
  expect(einmal.length).toBeGreaterThan(8);
  // Zugangsblatt (F55) mit dem angezeigten Einmal-Passwort
  await kennwortBox.getByRole("button", { name: "Zugangsblatt drucken" }).click();
  await expect(page.getByTestId("pdf-dialog").getByTestId("pdf-leser").locator("canvas").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("benutzerliste")).toContainText("Dr. med. H. Heilmann");
  await expect(detail).toContainText("Einrichtung offen");
  await sitzungGilt(page, "Benutzer anlegen");

  // mit dem Einmal-Passwort beginnt die erste Anmeldung
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

  // neues Einmal-Passwort
  await detail.getByRole("button", { name: "Einmal-Passwort erzeugen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Einmal-Passwort erzeugen" }).click();
  await expect(page.getByText("Neues Einmal-Passwort erzeugt.")).toBeVisible();
  const zweites = (await kennwortBox.locator(".num").first().textContent())?.trim() ?? "";
  expect(zweites).not.toBe(einmal);

  // Audit-Log: Benutzer angelegt und gesperrt
  await (await adminNavigation(page)).getByRole("link", { name: "Audit-Log" }).click();
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
    // der erste Hinweis kann noch sichtbar sein – auf den gespeicherten Stand warten statt auf den Hinweis
    await expect.poll(async () => (await mitarbeiter.get("auth/ich/")).rechte).not.toContain("plaene_anlegen");
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
  // Startseite der Vorlagen ist die Übersicht in Alltagssprache (F180)
  await expect(page.getByTestId("vorlagen-start")).toBeVisible();
  await page.getByRole("group", { name: "Bereich" }).getByRole("button", { name: "Briefkopf und Logo" }).click();
  await expect(page).toHaveURL(/\?bereich=briefkopf$/);

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
  // ▲ ▼ für Tablet und Telefon (F180) – zurück ans Ende
  await liste.getByRole("button", { name: `${ort} nach unten` }).click();
  await expect.poll(async () => (await admin.get("auswahlwerte/?liste=terminort")).map((o: { wert: string }) => o.wert).indexOf(ort))
    .toBe(orte.length - 1);
  await expect(page.getByTestId("liste-wo")).toContainText("Termin");
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
  // Kontakt fällig in zwei Stufen (S04): „bald fällig“ muss vor „überfällig“ liegen
  await grenzen.getByLabel("Kontakt bald fällig nach").fill("13");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(grenzen.getByText("„Überfällig“ muss später liegen als „bald fällig“.")).toBeVisible();
  await grenzen.getByLabel("Kontakt bald fällig nach").fill("5");
  // Grenze für das berechnete Volumen im Mischbeutel (Gewicht × 35 ml)
  await expect(grenzen.getByLabel("Volumen im Mischbeutel minimal")).toHaveValue("0");
  await expect(grenzen.getByLabel("Volumen im Mischbeutel maximal")).toHaveValue("9000");
  await grenzen.getByLabel("Volumen im Mischbeutel maximal").fill("8000");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Grenzwerte gespeichert.")).toBeVisible();
  const einstellungen = await admin.get("einstellungen/");
  expect([einstellungen.kontakt_bald_monate, einstellungen.kontakt_ueberfaellig_monate, einstellungen.volumen_max_ml]).toEqual([5, 13, 8000]);
  await admin.patch("einstellungen/", { kontakt_bald_monate: 4, kontakt_ueberfaellig_monate: 6, volumen_max_ml: 9000 });
  await admin.ende();
  merken("vorlagen", { ort, vitamin });
});

test("Administration je Recht: Betrachter sieht nichts, Mitarbeiter Vorlagen, Mediziner Vorlagen und Audit-Log", async ({ browser }) => {
  const b = await browser.newContext({ storageState: zustand("betrachter"), ignoreHTTPSErrors: true });
  const bp = await b.newPage();
  await bp.goto("/");
  await expect(bp.getByRole("navigation", { name: "Administration" })).toHaveCount(0);
  // ohne Recht gibt es die Seite nicht: weiter zur Startseite, kein Hinweis auf Rechte (Festlegung 01.10.2026)
  await bp.goto("/admin/benutzer");
  await expect(bp).toHaveURL(/\/$/);
  await expect(bp.getByText(/fehlt das Recht/)).toHaveCount(0);
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
  await expect(mp.getByTestId("vorlagen-start")).toBeVisible();
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

  // 2FA zurücksetzen (Telefon verloren): neues Einmal-Passwort, Authenticator weg
  await detail.getByRole("button", { name: "2FA zurücksetzen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "2FA zurücksetzen" }).click();
  await expect(page.getByText("2FA zurückgesetzt, neues Einmal-Passwort erzeugt.")).toBeVisible();
  await expect(detail.getByTestId("einmal-kennwort")).toBeVisible();
  await detail.getByRole("button", { name: "Entsperren" }).click();
  await expect(page.getByText("Benutzer entsperrt.")).toBeVisible();
  await expect(page.getByTestId("benutzerliste").getByRole("row").filter({ hasText: konto.benutzername })).toContainText("2FA: nicht eingerichtet");
  merken("gesperrt", { benutzername: konto.benutzername });
});

test("Admin: echte Akten nur lesen, Testpatienten anlegen und bearbeiten", async ({ page }) => {
  // nur die Administration sieht die Zahl der Testpatienten neben „in Betreuung“ (zählen in keiner Statistik)
  await page.goto("/patienten");
  await expect(page.getByTestId("zahl-in-betreuung")).toContainText(/zusätzlich \d+ Testpatienten/);
  await expect(page.getByRole("group", { name: "Ansicht" }).getByRole("button", { name: /In Betreuung/ })).toContainText(/\+\d+ Test/);
  const m = await apiAls("mitarbeiter");
  const echt = await m.post("patienten/", { nachname: eindeutig("Echt"), vorname: "Erna", geburtsdatum: "1960-06-06" });
  await m.ende();
  await page.goto(`/patienten/${echt.id}`);
  const kopf = page.getByTestId("aktenkopf");
  // keine Hinweise auf fehlende Rechte, nur keine Aktionen
  await expect(kopf.getByText("nur lesen")).toHaveCount(0);
  await expect(kopf.getByRole("button", { name: "Kontakt", exact: true })).toHaveCount(0);
  await expect(kopf.getByRole("button", { name: "Neuer Plan" })).toHaveCount(0);
  await expect(page.getByTestId("gewichtskarte").getByRole("button", { name: "Gewicht", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Weitere Aktionen" }).click();
  await expect(page.getByRole("menuitem", { name: "Stammdaten bearbeiten" })).toHaveCount(0);
  // Ausnahme (Fehlerliste 02.10.2026, 6.3): Akten abschließen dürfen Admins auch bei echten Patienten
  await expect(page.getByRole("menuitem", { name: "Akte abschließen" })).toBeVisible();
  await page.keyboard.press("Escape");
  // auch die API weist ab
  const admin = await apiAls("admin");
  const abgewiesen = await admin.roh.post("/api/kontakte/", { data: { patient: echt.id, text: "<p>x</p>" }, headers: await admin.kopf() });
  expect(abgewiesen.status()).toBe(403);
  expect((await abgewiesen.json()).fehler).toContain("nur bei Testpatienten");
  await page.getByRole("button", { name: "Weitere Aktionen" }).click();
  await page.getByRole("menuitem", { name: "Akte abschließen" }).click();
  const abschluss = page.getByRole("dialog");
  await abschluss.getByRole("radio").first().check();
  await abschluss.getByRole("button", { name: "Akte abschließen" }).click();
  await expect(page.getByText("Akte abgeschlossen.")).toBeVisible();
  expect((await admin.get(`patienten/${echt.id}/`)).ist_abgeschlossen).toBe(true);

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
  await kopf.getByRole("button", { name: "Kontakt", exact: true }).click();
  const neu = page.getByRole("dialog");
  await neu.getByRole("textbox", { name: "Notiz" }).fill("Testkontakt der Administration");
  await neu.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.getByText(/^Kontakt für .* gespeichert\.$/)).toBeVisible();
  const p = await admin.get(`patienten/${id}/`);
  expect([p.ist_test, p.nummer >= 9001]).toEqual([true, true]);
  expect((await admin.get(`kontakte/?patient=${id}`)).results).toHaveLength(1);
  await admin.ende();
});

test("Benutzer ohne Login: anlegen, setzen, wieder einbinden; Rolle „Keine Berechtigung“; Testbenutzer-Schalter", async ({ page }) => {
  await page.goto("/admin/benutzer");
  // Rolle „Keine Berechtigung“ hat nie Rechte – keine Spalte in der Rechtetabelle
  const rechte = page.getByTestId("rechte");
  await expect(rechte.getByRole("columnheader", { name: "Keine Berechtigung" })).toHaveCount(0);
  await expect(rechte.getByRole("columnheader", { name: "Mitarbeiter", exact: true })).toBeVisible();
  // Rolle „Mitarbeiter (erweitert)“ (Festlegung 03.10.2026): eigene Spalte, Standard mit „Infusionspläne anlegen“
  await expect(rechte.getByRole("columnheader", { name: "Mitarbeiter (erweitert)" })).toBeVisible();
  await expect(rechte.getByRole("checkbox", { name: "Mitarbeiter (erweitert): Infusionspläne anlegen" })).toBeChecked();
  await expect(rechte.getByRole("checkbox", { name: "Mitarbeiter: Infusionspläne anlegen", exact: true })).not.toBeChecked();
  // ohne Login anlegen: kein Passwort, keine Rechte
  const name = eindeutig("e2e.ohne");
  await page.getByRole("button", { name: "Benutzer anlegen" }).click();
  const detail = page.getByTestId("benutzer-detail");
  await detail.getByLabel("Vorname").fill("Olga");
  await detail.getByLabel("Nachname").fill("Ohnelogin");
  await detail.getByLabel("Benutzername").fill(name);
  await detail.getByRole("checkbox", { name: /Ohne Login anlegen/ }).check();
  await expect(detail.getByLabel("Rolle")).toHaveValue("keine");
  await expect(detail.getByLabel("Rolle")).toBeDisabled();
  await detail.getByRole("button", { name: "Ohne Login anlegen" }).click();
  await expect(page.getByText("Benutzer ohne Login angelegt.")).toBeVisible();
  await expect(detail.getByTestId("einmal-kennwort")).toHaveCount(0);
  await expect(detail.getByTestId("ohne-login-hinweis")).toBeVisible();
  const zeile = page.getByTestId("benutzerliste").getByRole("row").filter({ hasText: name });
  await expect(zeile).toContainText("ohne Login");
  await expect(zeile).toContainText("Keine Berechtigung");
  // Login geben: als Mitarbeiter wieder einbinden, mit Einmal-Passwort
  await detail.getByRole("button", { name: "Login geben" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Rolle").selectOption("mitarbeiter");
  await dialog.getByRole("button", { name: "Login geben" }).click();
  await expect(page.getByText("O. Ohnelogin hat wieder einen Login.")).toBeVisible();
  await expect(detail.getByTestId("einmal-kennwort")).toBeVisible();
  await expect(zeile).toContainText("Mitarbeiter");
  await expect(zeile).toContainText("Einrichtung offen");
  // Testbenutzer-Schalter (für Betrachter, Mitarbeiter, Mediziner)
  await detail.getByRole("checkbox", { name: /Testbenutzer/ }).check();
  await detail.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Benutzer gespeichert.")).toBeVisible();
  await expect(zeile).toContainText("Testbenutzer");
  const admin = await apiAls("admin");
  const konto = (await admin.get(`benutzer/?search=${name}`)).results[0];
  expect([konto.rolle, konto.ist_test, konto.nur_historisch]).toEqual(["mitarbeiter", true, false]);
  // Admins können keine Testbenutzer sein
  await detail.getByLabel("Rolle").selectOption("admin");
  await expect(detail.getByRole("checkbox", { name: /Testbenutzer/ })).not.toBeChecked();
  await expect(detail.getByRole("checkbox", { name: /Testbenutzer/ })).toBeDisabled();
  await detail.getByLabel("Rolle").selectOption("mitarbeiter");
  await detail.getByRole("checkbox", { name: /Testbenutzer/ }).uncheck();
  await detail.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByText("Benutzer gespeichert.").last()).toBeVisible();
  // wieder auf „ohne Login“: keine Rechte, Rolle „Keine Berechtigung“
  await detail.getByRole("button", { name: "Auf „ohne Login“ setzen" }).click();
  await dialog.getByRole("button", { name: "Auf „ohne Login“ setzen" }).click();
  await expect(page.getByText("Konto ist jetzt ohne Login und ohne Rechte.")).toBeVisible();
  await expect(zeile).toContainText("ohne Login");
  const danach = await admin.get(`benutzer/${konto.id}/`);
  expect([danach.rolle, danach.nur_historisch, danach.is_active, danach.ist_test]).toEqual(["keine", true, false, false]);
  // Anmeldung: Zwei-Faktor-Anmeldung freiwillig (Standard), umstellbar
  const anmeldung = page.getByTestId("anmeldung");
  await expect(anmeldung.getByRole("radio", { name: /^freiwillig/ })).toBeChecked();
  await anmeldung.getByRole("radio", { name: /^Pflicht für alle/ }).check();
  await expect(anmeldung.getByRole("button", { name: "Speichern" })).toBeEnabled();
  await anmeldung.getByRole("radio", { name: /^freiwillig/ }).check();
  await expect(anmeldung.getByRole("button", { name: "Speichern" })).toBeDisabled();
  await admin.ende();
});

test("Testbenutzer ausblenden und wieder einblenden; Recht „Testdaten sehen“ je Gruppe", async ({ page }) => {
  const admin = await apiAls("admin");
  const name = eindeutig("e2e.tester");
  const konto = await admin.post("benutzer/", { username: name, first_name: "Tilo", last_name: "Tester", rolle: "mitarbeiter", ist_test: true });
  await page.goto(`/admin/benutzer?id=${konto.id}`);
  const detail = page.getByTestId("benutzer-detail");
  await expect(detail).toContainText("Testbenutzer:");
  await expect(page.getByRole("button", { name: "Alle Testbenutzer ausblenden" })).toBeVisible();
  await detail.getByRole("button", { name: "Testbenutzer ausblenden" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Testbenutzer ausblenden" }).click();
  await expect(page.getByText("Testbenutzer ausgeblendet.")).toBeVisible();
  const liste = page.getByTestId("benutzerliste");
  await expect(liste.getByRole("row").filter({ hasText: name })).toHaveCount(0);
  const gesperrt = await admin.get(`benutzer/${konto.id}/`);
  expect([gesperrt.is_active, !!gesperrt.ausgeblendet_am]).toEqual([false, true]);
  // nur mit „Ausgeblendete zeigen“ – dort wieder einblenden
  await page.getByRole("checkbox", { name: "Ausgeblendete zeigen" }).check();
  const zeile = liste.getByRole("row").filter({ hasText: name });
  await expect(zeile).toContainText("ausgeblendet");
  await zeile.getByRole("button", { name: "T. Tester" }).click();
  await detail.getByTestId("ausgeblendet-hinweis").getByRole("button", { name: "Einblenden" }).click();
  await expect(page.getByText("Testbenutzer wieder eingeblendet.")).toBeVisible();
  expect((await admin.get(`benutzer/${konto.id}/`)).is_active).toBe(true);
  // Recht „Testdaten sehen“: je Gruppe einstellbar, für Admin fest
  const rechte = page.getByTestId("rechte");
  await expect(rechte.getByRole("checkbox", { name: "Admin: Testdaten sehen (Testpatienten und Testbenutzer)" })).toBeDisabled();
  await expect(rechte.getByRole("checkbox", { name: "Betrachter: Testdaten sehen (Testpatienten und Testbenutzer)" })).toBeChecked();
  // ohne das Recht sieht der Betrachter keine Testpatienten
  const betrachter = await apiAls("betrachter");
  expect((await betrachter.get("patienten/?test=nur")).count).toBeGreaterThan(0);
  await admin.put("rechte/", { matrix: { betrachter: { testdaten_sehen: false } } });
  expect((await betrachter.get("patienten/?test=nur")).count).toBe(0);
  await admin.put("rechte/", { matrix: { betrachter: { testdaten_sehen: true } } });
  expect((await betrachter.get("patienten/?test=nur")).count).toBeGreaterThan(0);
  await betrachter.ende();
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

test("Recht während der Sitzung entzogen: Aktion verschwindet ohne neue Anmeldung, Ablehnung nur neutral", async ({ page, browser }) => {
  const admin = await apiAls("admin");
  const m = await apiAls("mitarbeiter");
  const p = await m.post("patienten/", { nachname: eindeutig("Rechtweg"), vorname: "Rita", geburtsdatum: "1971-07-07" });
  await m.ende();
  const standardMatrix = async () => {
    const r = await admin.get("rechte/");
    return Object.fromEntries(r.rollen.map((ro: { code: string }) => [ro.code,
      Object.fromEntries(r.rechte.map((x: { code: string }) => [x.code, r.standard[ro.code].includes(x.code) || r.fest.some((f: string[]) => f[0] === ro.code && f[1] === x.code)]))]));
  };
  const ctx = await browser.newContext({ storageState: zustand("mitarbeiter"), ignoreHTTPSErrors: true });
  const mp = await ctx.newPage();
  try {
    await mp.goto(`/patienten/${p.id}`);
    await mp.getByRole("button", { name: "Weitere Aktionen" }).click();
    await mp.getByRole("menuitem", { name: "Akte abschließen" }).click();
    const dialog = mp.getByRole("dialog");
    await dialog.getByRole("radio", { name: "Therapie beendet" }).check();

    // Administration entzieht Mitarbeitern „Akten abschließen“, während der Dialog offen ist
    const matrix = await standardMatrix();
    matrix.mitarbeiter.akten_abschliessen = false;
    await admin.put("rechte/", { matrix });

    // Klick auf „Akte abschließen“: Server lehnt ab → Dialog verschwindet, neutraler Hinweis ohne Rechte-Namen
    await dialog.getByRole("button", { name: "Akte abschließen" }).click();
    await expect(mp.getByRole("dialog")).toHaveCount(0);
    await expect(mp.getByRole("alert").filter({ hasText: "Diese Aktion steht nicht mehr zur Verfügung. Die Ansicht wurde aktualisiert." })).toBeVisible();
    await expect(mp.getByText(/fehlt das Recht/)).toHaveCount(0);
    await mp.getByRole("button", { name: "Weitere Aktionen" }).click();
    // erst warten, bis das Menü offen ist – sonst ist „0 Einträge“ sofort wahr und Escape kommt vor dem Menü
    await expect(mp.getByRole("menuitem", { name: "Akte als PDF" })).toBeVisible();
    await expect(mp.getByRole("menuitem", { name: "Akte abschließen" })).toHaveCount(0);
    await mp.keyboard.press("Escape");
    await expect(mp.getByRole("menu")).toHaveCount(0);
    expect((await admin.get(`patienten/${p.id}/`)).ist_abgeschlossen).toBe(false);

    // Recht zurück: erscheint mit der nächsten Anfrage wieder (Kopf X-EPM-Rechte), ohne neue Anmeldung
    await admin.put("rechte/", { matrix: await standardMatrix() });
    await mp.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Verlauf" }).click();
    await expect(mp.getByTestId("verlauf")).toBeVisible();
    await expect(mp.getByRole("dialog")).toHaveCount(0); // der vorher ausgeblendete Dialog geht nicht von selbst wieder auf
    await mp.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Übersicht" }).click();
    await mp.getByRole("button", { name: "Weitere Aktionen" }).click();
    await expect(mp.getByRole("menuitem", { name: "Akte abschließen" })).toBeVisible();
    await mp.keyboard.press("Escape");
    await expect(mp.getByRole("menu")).toHaveCount(0);

    // und umgekehrt: Recht entzogen, ohne dass die Person etwas tut → beim nächsten Seitenwechsel ausgeblendet
    const ohne = await standardMatrix();
    ohne.mitarbeiter.eintraege_erfassen = false;
    await admin.put("rechte/", { matrix: ohne });
    await mp.getByRole("navigation", { name: "Aktenbereiche" }).getByRole("link", { name: "Verlauf" }).click();
    await expect(mp.getByTestId("aktenkopf").getByRole("button", { name: "Kontakt", exact: true })).toHaveCount(0);
    await expect(mp.getByTestId("aktenkopf").getByRole("button", { name: "Gewicht", exact: true })).toHaveCount(0);
  } finally {
    try {
      await admin.put("rechte/", { matrix: await standardMatrix() });
    } catch (fehler) {
      console.error("Rechte nicht auf Standard zurückgesetzt:", fehler);
    }
    await ctx.close();
    await admin.ende();
  }
});
