/** Tablet und Telefon mit Finger (Fehlermeldung 11.10.2026): „auf einigen Flächen lässt sich das Bild nicht bewegen, wie
 *  eingefroren“ (Tablet) und „bei der Terminbuchung ragen Elemente rechts heraus“ (Telefon). Geprüft mit echten
 *  Touch-Ereignissen (CDP), nicht mit dem Mausrad. */
import { expect, test } from "@playwright/test";
import type { CDPSession, Page } from "@playwright/test";
import { apiAls, eindeutig, zustand } from "./hilfen";

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
