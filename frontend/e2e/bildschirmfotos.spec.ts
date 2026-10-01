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
