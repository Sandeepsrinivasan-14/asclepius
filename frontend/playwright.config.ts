import { defineConfig, devices } from "@playwright/test";

const CI = !!process.env.CI;

/**
 * End-to-end tests run against the real stack: the FastAPI backend (in-memory synthetic data, fixed seed)
 * and the Next.js frontend. `npm run e2e` starts both. Use `E2E_REUSE=1` to reuse servers you already run.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: CI ? 1 : 0,
  reporter: CI ? [["line"], ["html", { open: "never" }]] : [["line"]],
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure", ...devices["Desktop Chrome"] },
  webServer: [
    {
      command: process.platform === "win32" ? "python -m uvicorn asclepius.main:create_app --factory --port 8000" : "python3 -m uvicorn asclepius.main:create_app --factory --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: !CI || !!process.env.E2E_REUSE,
      timeout: 120_000,
    },
    {
      command: CI ? "npm run build && npm run start" : "npm run dev",
      url: "http://localhost:3000/login",
      reuseExistingServer: !CI || !!process.env.E2E_REUSE,
      timeout: 300_000,
    },
  ],
});
