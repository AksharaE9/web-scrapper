import { test, expect } from "@playwright/test";

test.describe("Region Exhaustion", () => {
  test("exhaustion banner displays alongside lead rows", async ({ page, request }) => {
    const runsRes = await request.get("/api/runs");
    const runs = await runsRes.json();
    const exhaustedRun = runs.find((r: any) => r.completion_reason === "region_exhausted" || /exhaust/i.test(r.completion_reason ?? ""));

    if (exhaustedRun) {
      await page.goto(`/runs/${exhaustedRun.id}?tab=accepted`);
      await expect(page.getByTestId("exhaustion-banner")).toBeVisible();
      const count = await page.getByTestId("lead-row").count();
      expect(count).toBeGreaterThan(0);
    }
  });
});
