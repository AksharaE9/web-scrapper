import { test, expect } from "@playwright/test";

test.describe("Retry Guard", () => {
  test("non-retryable run hides retry button and direct API retry is rejected", async ({ page, request }) => {
    const runsRes = await request.get("/api/runs");
    const runs = await runsRes.json();
    if (!runs || runs.length === 0) return;

    const nonRetryable = runs.find((r: any) => r.retryable === false);
    if (nonRetryable) {
      await page.goto(`/runs/${nonRetryable.id}`);
      await expect(page.getByRole("button", { name: /retry/i })).toHaveCount(0);

      const retryRes = await request.post(`/api/runs/${nonRetryable.id}/retry`);
      expect([400, 422]).toContain(retryRes.status());
    }
  });
});
