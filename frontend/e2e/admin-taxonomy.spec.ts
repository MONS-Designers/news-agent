import { test, expect, signInAs } from "./fixtures";

test.describe("admin taxonomy curation queue", () => {
  test("an admin promotes one pending suggestion and dismisses another", async ({
    page,
    context,
  }) => {
    await signInAs(context, "admin");
    await page.goto("/admin/taxonomy");

    await expect(page.getByRole("heading", { name: "תור טקסונומיה" })).toBeVisible();

    const robotics = page.locator("li", { hasText: "Robotics" });
    await expect(robotics).toBeVisible();
    const devRel = page.locator("li", { hasText: "DevRel Engineer" });
    await expect(devRel).toBeVisible();

    await robotics.getByRole("button", { name: "קידום" }).click();
    await expect(robotics).not.toBeVisible();

    await devRel.getByRole("button", { name: "דחייה" }).click();
    await expect(devRel).not.toBeVisible();

    await expect(page.getByText("אין הצעות טקסונומיה ממתינות.")).toBeVisible();

    // Persisted server-side: a fresh load shows the same empty queue.
    await page.reload();
    await expect(page.getByText("אין הצעות טקסונומיה ממתינות.")).toBeVisible();
  });
});
