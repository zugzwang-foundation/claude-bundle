import { defineConfig } from "@playwright/test";

const PORT = 4173;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  /* Each flow downloads the model once into a fresh browser context: two at a time is plenty. */
  workers: 2,
  retries: 0,
  /* The whole story, including the model download, is given five minutes. */
  timeout: 300_000,
  expect: { timeout: 15_000 },
  reporter: "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    screenshot: "only-on-failure",
    trace: "off",
  },
  webServer: {
    command: "npm run preview",
    url: `http://localhost:${PORT}`,
    reuseExistingServer: true,
    timeout: 60_000,
  },
  projects: [
    {
      name: "phone",
      use: {
        browserName: "chromium",
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
        deviceScaleFactor: 3,
      },
    },
    {
      name: "desktop",
      use: {
        browserName: "chromium",
        viewport: { width: 1440, height: 900 },
      },
    },
  ],
});
