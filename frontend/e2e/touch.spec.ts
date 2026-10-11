/** Tablet und Telefon mit Finger (Fehlermeldung 11.10.2026): „auf einigen Flächen lässt sich das Bild nicht bewegen, wie
 *  eingefroren“ (Tablet) und „bei der Terminbuchung ragen Elemente rechts heraus“ (Telefon). Geprüft mit echten
 *  Touch-Ereignissen (CDP), nicht mit dem Mausrad. */
import { expect, test } from "@playwright/test";
import type { CDPSession, Page } from "@playwright/test";
import { apiAls, eindeutig, einfachePdf, zustand } from "./hilfen";

/** Mit dem Finger von (x, y) 200 px nach oben wischen (Inhalt scrollt nach unten) – zweimal, wie ein Mensch es täte:
 *  Chrome bindet eine Geste an den Bereich, in dem sie beginnt. */
async function wischen(page: Page, cdp: CDPSession, x: number, y: number) {
  for (let n = 0; n < 2; n++) {
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    for (let k = 1; k <= 8; k++) {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: Math.max(2, y - k * 25) }] });
      await page.waitForTimeout(16);
    }
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await page.waitForTimeout(250);
  }
}

test.describe("Tablet quer (1280 × 800, Finger)", () => {
  test.use({ viewport: { width: 1280, height: 800 }, isMobile: true, hasTouch: true, storageState: zustand("mediziner") });

  test("Akte füllt das Fenster nicht – die Seite lässt sich über Kopf und Reiter wischen", async ({ page, context }) => {
    await page.goto("/patienten");
    await page.getByTestId("patientenliste").getByRole("link", { name: "Probe, Jonas" }).click();
    await expect(page.getByTestId("akte-uebersicht")).toBeVisible();
    await expect(page.getByTestId("akte-uebersicht")).not.toHaveAttribute("data-fuellt", "1");
    const rest = await page.evaluate(() => document.scrollingElement!.scrollHeight - innerHeight);
    test.skip(rest < 50, "Akte passt ins Fenster – nichts zu scrollen");
    const kopf = (await page.getByTestId("aktenkopf").boundingBox())!;
    const cdp = await context.newCDPSession(page);
    await wischen(page, cdp, kopf.x + kopf.width / 2, Math.min(kopf.y + kopf.height / 2, 600));
    expect(await page.evaluate(() => scrollY)).toBeGreaterThan(0);
  });

  test("Startseite: Kachel am Ende hält das Wischen nicht fest", async ({ page, context }) => {
    await page.goto("/");
    await expect(page.locator(".kachel-inhalt").first()).toBeVisible();
    // eine Kachel mit eigenem Scrollbalken erzeugen: Inhalt künstlich verlängern
    const punkt = await page.evaluate(() => {
      const k = document.querySelector<HTMLElement>(".kachel-inhalt")!;
      const fuell = document.createElement("div");
      fuell.style.height = "2000px";
      k.appendChild(fuell);
      k.scrollIntoView({ block: "center" });
      k.scrollTop = k.scrollHeight;
      const r = k.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: Math.min(r.top + r.height / 2, innerHeight - 100), y0: scrollY,
        rest: document.scrollingElement!.scrollHeight - innerHeight - scrollY, ob: getComputedStyle(k).overscrollBehaviorY };
    });
    expect(punkt.ob).toBe("auto");
    test.skip(punkt.rest < 50, "Seite ist schon am Ende");
    const cdp = await context.newCDPSession(page);
    await wischen(page, cdp, punkt.x, punkt.y);
    expect(await page.evaluate(() => scrollY)).toBeGreaterThan(punkt.y0);
  });
});

test.describe("Telefon 320 px (Finger)", () => {
  test.use({ viewport: { width: 320, height: 640 }, isMobile: true, hasTouch: true, storageState: zustand("mediziner") });

  test("Terminbuchung mit langem Namen: nichts ragt aus dem Dialog", async ({ page }) => {
    const api = await apiAls("mediziner");
    const nachname = eindeutig("Müller-Lüdenscheidt-Hohenzollern");
    await api.post("patienten/", { nachname, vorname: "Anna-Katharina Maximiliane", geburtsdatum: "1948-03-14" });
    await api.ende();
    await page.goto("/kalender");
    await page.getByRole("button", { name: "Neuer Termin" }).click();
    const dialog = page.getByRole("dialog", { name: "Neuer Termin" });
    await dialog.getByRole("searchbox").fill(nachname);
    await dialog.getByRole("listbox", { name: "Treffer" }).getByRole("option", { name: new RegExp(nachname) }).click();
    await dialog.getByLabel("Art").selectOption("praxistermin");
    await expect(dialog.getByRole("button", { name: "ändern" })).toBeVisible();
    const raus = await dialog.evaluate((d) => {
      const rechts = d.getBoundingClientRect().right;
      return [...d.querySelectorAll<HTMLElement>("*")].filter((el) => el.getBoundingClientRect().right > rechts + 0.5)
        .map((el) => `${el.tagName} ${el.textContent?.slice(0, 30)}`);
    });
    expect(raus).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  });
});

test.describe("Telefon 390 px: Benutzer bearbeiten", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, storageState: zustand("admin") });

  test("Formular steht unter der Liste und kommt nach dem Antippen in den Blick (Fehlermeldung 11.10.2026)", async ({ page }) => {
    await page.goto("/admin/benutzer");
    const zeile = page.getByTestId("benutzerliste").getByRole("row").filter({ hasText: "e2e.mitarbeiter" });
    await zeile.getByRole("button").first().click();
    const detail = page.getByTestId("benutzer-detail");
    await expect(detail).toContainText("S. Mitarbeit");
    await expect(detail).toBeInViewport();
    // vor Anmeldung und Rechten, nicht mehr ganz unten
    const formular = (await detail.boundingBox())!;
    const rechte = (await page.getByTestId("rechte").boundingBox())!;
    expect(formular.y).toBeLessThan(rechte.y);
  });
});

test.describe("Telefon 390 px: Nickelallergie nicht erfasst", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, storageState: zustand("mediziner") });

  test("Hinweis wie die anderen offenen Aufgaben, in Liste und Aktenkopf; erfasst → weg (Wunsch 11.10.2026)", async ({ page }) => {
    const api = await apiAls("mediziner");
    const nachname = eindeutig("Nickeltest");
    const p = await api.post("patienten/", { nachname, vorname: "Nora", geburtsdatum: "1966-06-06" });
    await page.goto(`/patienten?suche=${nachname}`);
    const chip = page.getByTestId("patientenliste").getByTestId("nickel-fehlt");
    await expect(chip).toHaveText("Nickelallergie nicht erfasst");
    await expect(chip).toHaveClass(/warn/);
    await page.goto(`/patienten/${p.id}`);
    await expect(page.getByTestId("cave").getByTestId("nickel-fehlt")).toBeVisible();
    await api.patch(`patienten/${p.id}/`, { nickelallergie: "nein" });
    await api.ende();
    await page.reload();
    await expect(page.getByTestId("nickel-fehlt")).toHaveCount(0);
  });
});

test.describe("Telefon 390 px: offene Punkte und Termine führen zur Stelle", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, storageState: zustand("mediziner") });

  test("Klick auf Hinweis bzw. Termin in der Patientenliste (Wunsch 11.10.2026)", async ({ page }) => {
    const api = await apiAls("mediziner");
    const nachname = eindeutig("Sprungtest");
    const p = await api.post("patienten/", { nachname, vorname: "Sina", geburtsdatum: "1971-07-07" });
    const morgen = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
    await api.post("termine/", { patient: p.id, art: "rueckruf", faellig_am: morgen, uhrzeit: null, titel: "Sprung prüfen", notiz: "", ort: null });
    await api.ende();
    const liste = page.getByTestId("patientenliste");

    // „Kein Laborbefund“ → Reiter Labor
    await page.goto(`/patienten?suche=${nachname}`);
    await liste.getByTestId("hinweis-labor").click();
    await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}/labor`));

    // „Nickelallergie nicht erfasst“ → Stammdaten offen
    await page.goto(`/patienten?suche=${nachname}`);
    await liste.getByTestId("nickel-fehlt").getByRole("button").click();
    await expect(page).toHaveURL(new RegExp(`/patienten/${p.id}$`));
    await expect(page.getByRole("dialog")).toContainText("Nickelallergie");

    // nächster Termin → Termin offen zum Bearbeiten
    await page.goto(`/patienten?suche=${nachname}`);
    await liste.getByTestId("naechster-termin").click();
    const dialog = page.getByRole("dialog", { name: "Termin bearbeiten" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByLabel("Titel")).toHaveValue("Sprung prüfen");
  });
});

test.describe("Telefon 390 px: Termine und Vorschau in der Akte führen zum Dialog", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, storageState: zustand("mediziner") });

  test("Nächster Termin (Kontakte, Aktenkopf) öffnet den Termin, Vorschau öffnet das Dokument groß (Wunsch 11.10.2026)", async ({ page }) => {
    const api = await apiAls("mediziner");
    const p = await api.post("patienten/", { nachname: eindeutig("Verweistest"), vorname: "Vera", geburtsdatum: "1969-09-09" });
    const morgen = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
    await api.post("termine/", { patient: p.id, art: "praxistermin", faellig_am: morgen, uhrzeit: "10:30", titel: "Kontrolltermin", notiz: "", ort: null });
    const hoch = await api.roh.post("/api/dokumente/", { headers: await api.kopf(),
      multipart: { patient: String(p.id), titel: "Arztbrief Vorschau", datei: { name: "brief.pdf", mimeType: "application/pdf", buffer: einfachePdf(["Seite eins"]) } } });
    expect(hoch.status()).toBe(201);
    await api.ende();

    // Reiter Kontakte: Karte „Nächster Termin“
    await page.goto(`/patienten/${p.id}/kontakte`);
    await page.getByTestId("naechster-termin").click();
    const termin = page.getByRole("dialog", { name: "Termin bearbeiten" });
    await expect(termin.getByLabel("Titel")).toHaveValue("Kontrolltermin");
    await page.keyboard.press("Escape");
    await expect(termin).toHaveCount(0);

    // Dokumente: Antippen der Vorschau öffnet das Dokument groß
    await page.goto(`/patienten/${p.id}/dokumente`);
    await page.getByTestId("dokumentliste").getByText("Arztbrief Vorschau").click();
    await page.getByTestId("dokument-details").getByTestId("vorschau-oeffnen").click();
    await expect(page.getByRole("dialog", { name: "Arztbrief Vorschau" })).toBeVisible();
  });
});

test.describe("Telefon 390 px: Terminbestätigung schon erledigt", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, storageState: zustand("mediziner") });

  test("„Bestätigung fehlt“ lässt sich als telefonisch bestätigt wegklicken (Wunsch 11.10.2026)", async ({ page }) => {
    const api = await apiAls("mediziner");
    const p = await api.post("patienten/", { nachname: eindeutig("Bestaetigt"), vorname: "Berta", geburtsdatum: "1958-08-08",
      geschlecht: "w", email: "berta@example.org" });
    const inEinerWoche = new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10);
    await api.post("termine/", { patient: p.id, art: "praxistermin", faellig_am: inEinerWoche, uhrzeit: "17:15", titel: "Praxistermin", notiz: "", ort: null });
    await api.ende();
    await page.goto(`/patienten/${p.id}/kontakte`);
    await page.getByTestId("naechster-termin").click();
    const dialog = page.getByRole("dialog", { name: "Termin bearbeiten" });
    await expect(dialog.getByTestId("bestaetigung-fehlt")).toBeVisible();
    await dialog.getByRole("button", { name: "Schon bestätigt …" }).click();
    await page.getByRole("menuitem", { name: "Telefonisch bestätigt" }).click();
    await expect(dialog).toHaveCount(0);
    await page.getByTestId("naechster-termin").click();
    await expect(page.getByRole("dialog", { name: "Termin bearbeiten" }).getByTestId("bestaetigung-erstellt")).toContainText("Bestätigt telefonisch");
  });
});
