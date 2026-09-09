import { defineConfig } from '@playwright/test';

// Matches VITE_BACKEND in .env.e2e, which is what the vite proxy forwards
// /backend to.
const BACKEND_PORT = 8100;
// Not vite's default, so a dev server already running on 5173 is left alone.
const FRONTEND_PORT = 5174;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // The HTML report is what the failure artifact in .github/workflows/e2e.yml
  // picks up; locally the list output is already in the terminal.
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: './e2e/backend.sh',
      env: { E2E_BACKEND_PORT: String(BACKEND_PORT) },
      // Served without a token. Every route worth polling sits behind the
      // login the test has not performed yet, so readiness cannot key on one.
      url: `http://127.0.0.1:${BACKEND_PORT}/openapi.json`,
      // Never adopt a running server: this one is defined by the database and
      // the admin account backend.sh seeds, and the dev server has neither.
      reuseExistingServer: false,
      stdout: 'pipe',
      stderr: 'pipe',
      timeout: 120_000,
    },
    {
      // dev, not preview. `server.proxy` is dev-only configuration, so
      // /backend/* would 404 against a preview server.
      command: `npm run dev -- --mode e2e --port ${FRONTEND_PORT} --strictPort`,
      url: `http://127.0.0.1:${FRONTEND_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
