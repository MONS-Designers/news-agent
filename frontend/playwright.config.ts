import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

// Deliberately non-default ports (README documents 5173/8000 for normal
// local dev) - a real dev session may already be running there, and this
// suite must never touch it or its DB.
const FRONTEND_PORT = 5183;
const BACKEND_PORT = 8010;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

const repoRoot = path.resolve(__dirname, "..");
const tmpDir = path.resolve(__dirname, "e2e/.tmp");
const dbPath = path.join(tmpDir, "e2e-test.db").replace(/\\/g, "/");

// Throwaway, test-only value - never the real NEWSAGENT_SESSION_SECRET.
// Shared between the backend webServer below and global-setup.ts's cookie
// minting so a cookie minted there verifies against this server.
export const E2E_SESSION_SECRET = "e2e-test-only-session-secret";
export const E2E_DATABASE_URL = `sqlite:///${dbPath}`;
export const E2E_COOKIES_PATH = path.join(tmpDir, "cookies.json");
export { FRONTEND_URL, BACKEND_URL };

const backendEnv = {
  NEWSAGENT_DATABASE_URL: E2E_DATABASE_URL,
  NEWSAGENT_SESSION_SECRET: E2E_SESSION_SECRET,
  NEWSAGENT_FRONTEND_URL: FRONTEND_URL,
  NEWSAGENT_BACKEND_BASE_URL: BACKEND_URL,
  // Offline/deterministic adapters - no external API calls from the suite.
  NEWSAGENT_SUGGESTION_PROVIDER: "popularity",
  NEWSAGENT_LLM_PROVIDER: "mock",
  NEWSAGENT_EMAIL_SENDER: "console",
  NEWSAGENT_GOOGLE_CLIENT_ID: "",
  NEWSAGENT_GOOGLE_CLIENT_SECRET: "",
  NEWSAGENT_LOG_LEVEL: "WARNING",
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: FRONTEND_URL,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `python -m uvicorn newsagent.api.main:app --port ${BACKEND_PORT}`,
      cwd: repoRoot,
      url: `${BACKEND_URL}/health`,
      env: backendEnv,
      reuseExistingServer: false,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort --host 127.0.0.1`,
      cwd: __dirname,
      url: FRONTEND_URL,
      env: { E2E_BACKEND_URL: BACKEND_URL },
      reuseExistingServer: false,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
