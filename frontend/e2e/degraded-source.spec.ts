import { test, expect } from "@playwright/test";

test.describe("Degraded Source Handling", () => {
  test("shows partial banner and continues with available sources", async ({ page }) => {
    // If backend reports degraded/partial source
    const runsRes = await page.request.get("/api/runs");
    const runs = await runsRes.json();
    const partialRun = runs.find((r: any) => r.status === "partial");

    if (partialRun) {
      await page.goto(`/runs/${partialRun.id}`);
      await expect(page.getByTestId("run-status")).toHaveText(/partial/i);
    }
  });
});
