/** Bildschirmfotos ausgewählter Seiten (nur mit EPM_BILDER=1, beim manuellen Start des Workflows) – zum Ansehen ohne
 *  laufenden Server. Läuft nach den übrigen Tests, zeigt also Musterdaten und deren Ergebnisse. */
import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { zustand } from "./hilfen";

test.skip(!process.env.EPM_BILDER, "nur beim manuellen Start (EPM_BILDER=1)");
test.use({ storageState: zustand("admin"), viewport: { width: 1600, height: 1000 } });

const ORDNER = "e2e/bildschirmfotos";

test("Bildschirmfotos: System, Kalender, Infusionspläne", async ({ page }) => {
  mkdirSync(ORDNER, { recursive: true });
  await page.goto("/admin/system");
  await expect(page.getByTestId("kennzahl-cpu")).toBeVisible();
  await expect(page.getByTestId("verlauf").or(page.getByText("Noch kein Verlauf"))).toBeVisible();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${ORDNER}/system.png`, fullPage: true });
  await page.getByTestId("aktion-server_neustart").getByRole("button", { name: "Server neu starten" }).click();
  await page.getByRole("dialog").getByLabel("Beginn").selectOption("15");
  await page.screenshot({ path: `${ORDNER}/system-neustart-dialog.png` });
  await page.keyboard.press("Escape");
  await page.goto("/kalender");
  await expect(page.getByTestId("kalender-monat")).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${ORDNER}/kalender.png`, fullPage: true });
  await page.goto("/infusionsplaene?gruppe=alle");
  await expect(page.getByTestId("plan-uebersicht")).toBeVisible();
  await page.screenshot({ path: `${ORDNER}/infusionsplaene.png`, fullPage: true });
});

test("Bildschirmfotos: Import der Altdaten (Dump, Zuordnungen, Probelauf)", async ({ page }) => {
  mkdirSync(ORDNER, { recursive: true });
  await page.goto("/admin/import");
  await expect(page.getByTestId("dump-name")).toBeVisible();
  await page.screenshot({ path: `${ORDNER}/import-dump.png`, fullPage: true });
  await page.goto("/admin/import?schritt=zuordnungen");
  await expect(page.getByTestId("offene-punkte")).toBeVisible();
  await page.screenshot({ path: `${ORDNER}/import-zuordnungen-spalten.png`, fullPage: true });
  const bereiche = page.getByRole("group", { name: "Bereich der Zuordnungen" });
  for (const [name, datei, testid] of [["Benutzer", "benutzer", "zuordnung-benutzer"], ["Versorger", "versorger", "zuordnung-versorger"],
    ["Katheter und Werte", "werte", "zuordnung-katheter"], ["Präparate", "praeparate", "zuordnung-praeparate-lipide"],
    ["Gelöschte Patienten", "geloeschte", "zuordnung-geloeschte"], ["Auffälligkeiten", "auffaelligkeiten", "zuordnung-auffaelligkeiten"]]) {
    await bereiche.getByRole("button", { name }).click();
    await expect(page.getByTestId(testid)).toBeVisible();
    await page.screenshot({ path: `${ORDNER}/import-zuordnungen-${datei}.png`, fullPage: true });
  }
  await page.goto("/admin/import?schritt=import");
  await expect(page.getByTestId("zaehlung")).toBeVisible();
  await page.screenshot({ path: `${ORDNER}/import-probelauf.png`, fullPage: true });
  await page.goto("/admin/import?schritt=dokumente");
  await expect(page.getByTestId("dokumente-karte")).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${ORDNER}/import-dokumente.png`, fullPage: true });
  await page.goto("/admin/import?schritt=protokolle");
  await page.getByTestId("lauf").filter({ has: page.getByRole("cell", { name: "Import", exact: true }) }).getByRole("button", { name: "Ansehen" }).click();
  await expect(page.getByTestId("lauf-ergebnis")).toBeVisible();
  await page.screenshot({ path: `${ORDNER}/import-protokoll.png`, fullPage: true });
});
