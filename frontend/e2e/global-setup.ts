import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { E2E_DATABASE_URL, E2E_SESSION_SECRET, E2E_COOKIES_PATH } from "../playwright.config";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

// Builds a fresh throwaway sqlite DB + fixture rows, and mints signed session
// cookies for each fixture identity (see scripts/e2e_setup.py) - so the
// suite's specs can skip real Google OAuth. Runs once before either
// webServer starts.
export default function globalSetup() {
  const repoRoot = path.resolve(__dirname, "../..");
  const tmpDir = path.dirname(E2E_COOKIES_PATH);
  if (!existsSync(tmpDir)) mkdirSync(tmpDir, { recursive: true });

  const output = execFileSync("python", ["scripts/e2e_setup.py"], {
    cwd: repoRoot,
    env: {
      ...process.env,
      NEWSAGENT_DATABASE_URL: E2E_DATABASE_URL,
      NEWSAGENT_SESSION_SECRET: E2E_SESSION_SECRET,
    },
    encoding: "utf-8",
  });

  writeFileSync(E2E_COOKIES_PATH, output);
}
