import { defineConfig, devices } from "@playwright/test";

/**
 * Browsertests gegen den echten Stack (Nginx + Django + PostgreSQL), gestartet mit werkzeuge/ci-stack.sh.
 * Die Tests laufen nacheinander, weil sie gemeinsame Daten (Musterdaten, Startseite) verändern.
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.EPM_URL ?? "https://localhost",
    ignoreHTTPSErrors: true,
    locale: "de-DE",
    timezoneId: "Europe/Berlin",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 960 } } }],
});
