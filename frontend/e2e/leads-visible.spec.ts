import { test, expect } from "@playwright/test";

test.describe("Leads Visibility & Counts", () => {
  test("run detail matches API count with rendered rows exactly", async ({ page, request }) => {
    // 1. Fetch runs list from API
    const runsRes = await request.get("/api/runs");
    const runs = await runsRes.json();
    if (!runs || runs.length === 0) {
      test.skip();
      return;
    }

    const runId = runs[0].id;
    const leadsRes = await request.get(`/api/runs/${runId}/leads?decision=accepted`);
    const leadsData = await leadsRes.json();
    const apiTotal = leadsData.total ?? (Array.isArray(leadsData) ? leadsData.length : leadsData.items?.length ?? 0);

    // 2. Open UI
    await page.goto(`/runs/${runId}?tab=accepted`);
    await page.waitForSelector("[data-testid='run-status']");

    if (apiTotal > 0) {
      const renderedCount = await page.getByTestId("lead-row").count();
      expect(renderedCount).toBe(apiTotal);
    }
  });
});
