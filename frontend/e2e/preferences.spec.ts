import { test, expect, signInAs } from "./fixtures";
import { DIGEST_NOUN_WEEKLY } from "@/branding";

test.describe("preferences - weekly email subscription", () => {
  test("a profiled user pauses and resumes their weekly digest, and it persists", async ({
    page,
    context,
  }) => {
    await signInAs(context, "profiled_user");
    await page.goto("/preferences");

    // A user who already completed the wizard sees the read-only summary,
    // not the wizard, straight away.
    await expect(page.getByRole("heading", { name: "העדפות הנושאים שלי" })).toBeVisible();
    await expect(page.getByText("פעיל", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "השהיה" }).click();
    await expect(page.getByText(`מושהה - ${DIGEST_NOUN_WEEKLY} לא יישלח.`)).toBeVisible();

    // Persisted server-side, not just local component state.
    await page.reload();
    await expect(page.getByText(`מושהה - ${DIGEST_NOUN_WEEKLY} לא יישלח.`)).toBeVisible();

    await page.getByRole("button", { name: "המשך" }).click();
    await expect(page.getByText("פעיל", { exact: true })).toBeVisible();

    await page.reload();
    await expect(page.getByText("פעיל", { exact: true })).toBeVisible();
  });
});
