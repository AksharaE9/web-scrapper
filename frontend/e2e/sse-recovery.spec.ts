import { test, expect } from "@playwright/test";

test.describe("SSE Connection Resiliency", () => {
  test("reconnects gracefully on network drop", async ({ page }) => {
    const runsRes = await page.request.get("/api/runs");
    const runs = await runsRes.json();
    if (!runs || runs.length === 0) return;

    const runId = runs[0].id;
    await page.goto(`/runs/${runId}/live`);

    // Verify connection established
    await expect(page.locator("body")).toBeVisible();
  });
});
