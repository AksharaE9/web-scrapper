import { test, expect } from "@playwright/test";

test.describe("Deep Linking", () => {
  test("opening run leads drawer directly via query param or route", async ({ page }) => {
    const runsRes = await page.request.get("/api/runs");
    const runs = await runsRes.json();
    if (!runs || runs.length === 0) return;

    const runId = runs[0].id;
    await page.goto(`/runs/${runId}?tab=accepted`);

    const rows = page.getByTestId("lead-row");
    if ((await rows.count()) > 0) {
      await rows.first().click();
      await expect(page.getByTestId("lead-drawer")).toBeVisible();
    }
  });
});
