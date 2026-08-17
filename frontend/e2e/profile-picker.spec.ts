import { test, expect, signInAs, visibleButton } from "./fixtures";

test.describe("profile picker onboarding", () => {
  test("a brand-new user completes all three steps and lands with a saved profile", async ({
    page,
    context,
  }) => {
    await signInAs(context, "new_user");
    await page.goto("/preferences");

    // Step 1: About You - pick a curated Field, wait for its Roles to load,
    // pick a curated Role, pick an experience bucket.
    await page.getByRole("group", { name: "תחום" }).getByRole("button", { name: "Tech", exact: true }).click();
    const roleGroup = page.getByRole("group", { name: "תפקיד" });
    await roleGroup.getByRole("button", { name: "Software Engineer", exact: true }).click();
    // The radio input itself is visually hidden (sr-only); its wrapping
    // <label> is the actual click target.
    await page.locator("label", { hasText: "3–5 שנים" }).click();
    await visibleButton(page, "המשך").click();

    // Step 2: Interests - free text is optional, just advance.
    await page
      .getByRole("textbox", { name: "תחומי העניין שלך, במילים שלך" })
      .fill("Distributed systems and developer tooling");
    await visibleButton(page, "המשך").click();

    // Step 3: Topics - seeded fixture topics rank via the offline popularity
    // fallback (no LLM call), so chips appear without waiting on any provider.
    const topicsGroup = page.getByRole("group", { name: "נושאים מוצעים" });
    await expect(topicsGroup.getByRole("button").first()).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: "אני רוצה לקבל את הדייג'סט" }).click();

    // Saving redirects to the home page.
    await expect(page).toHaveURL(`${new URL(page.url()).origin}/`);

    // The saved profile persists - a fresh visit to /preferences shows the
    // read-only summary, not the wizard, with the values just chosen.
    await page.goto("/preferences");
    await expect(page.getByRole("heading", { name: "העדפות הנושאים שלי" })).toBeVisible();
    await expect(page.getByText("Software Engineer", { exact: true })).toBeVisible();
    await expect(page.getByText("3–5 שנים", { exact: true })).toBeVisible();
  });
});
