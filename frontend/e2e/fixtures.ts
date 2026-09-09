import { test as base, expect, type BrowserContext, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { E2E_COOKIES_PATH, FRONTEND_URL } from "../playwright.config";

type Identity = "admin" | "new_user" | "profiled_user";

let cookies: Record<Identity, string> | undefined;

function loadCookies(): Record<Identity, string> {
  if (!cookies) {
    cookies = JSON.parse(readFileSync(E2E_COOKIES_PATH, "utf-8"));
  }
  return cookies;
}

/** Signs in as `identity` by planting the same signed session cookie the real
 * Google OAuth callback would set - see scripts/e2e_setup.py. Skips the real
 * OAuth flow entirely (can't be automated / no real Google account here). */
export async function signInAs(context: BrowserContext, identity: Identity): Promise<void> {
  const value = loadCookies()[identity];
  await context.addCookies([
    {
      name: "session",
      value,
      url: FRONTEND_URL,
    },
  ]);
}

/** A button matched by exact visible text, ignoring any same-text buttons
 * hidden in other wizard steps (ProfilePickerShell keeps every step mounted
 * via v-show, so more than one "המשך" button can exist in the DOM at once). */
export function visibleButton(page: Page, exactText: string) {
  // `:visible` is what disambiguates here: the wizard keeps all three step
  // panels mounted behind v-show, so "המשך" exists three times in the DOM
  // and only one of them is on screen.
  //
  // The whitespace tolerance matters because a RegExp `hasText` is tested
  // against raw textContent, with no normalization. Step 1's Continue button
  // carries a `v-if` spinner beside its label, and the whitespace between
  // that node and the label survives as a leading space - so a bare
  // `^המשך$` stopped matching the moment the spinner was added, while the
  // button's accessible name never changed.
  return page.locator("button:visible", { hasText: new RegExp(`^\\s*${exactText}\\s*$`) });
}

export const test = base;
export { expect };
