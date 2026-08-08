import { defineConfig } from "@playwright/test";

/**
 * End-to-end tests against a running BlackBox stack (API :8000, web :3000).
 * Start it with `make demo` locally; CI boots both servers before running.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    viewport: { width: 1600, height: 900 },
  },
});
