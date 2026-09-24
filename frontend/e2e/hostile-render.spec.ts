import { test, expect } from "@playwright/test";

test.describe("Hostile Payload Resilience", () => {
  test("degraded row renders without crashing page when hostile objects are returned", async ({ page }) => {
    // Intercept leads request to inject hostile row
    await page.route("**/api/runs/*/leads*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      const hostileLead = {
        business_id: "hostile-0000-4000-8000-000000000001",
        canonical_name: "Hostile Crash Test Store",
        primary_category: "religious_goods_store",
        locality: "HSR Layout",
        phones_e164: ["+918026001234"],
        emails: null,
        website_domain: null,
        tier: "Likely",
        confidence: 0.69,
        independent_source_count: 1,
        decision: "accepted",
        relevance_p: 0.77,
        relevance_reasons: [
          { type: "positive", label: "category match", icon: { type: "check", label: "ok", icon: "x" } },
          { unexpected: "shape", without: "label" },
          null,
        ],
      };

      const modifiedItems = [hostileLead, ...(json.items || [])];
      await route.fulfill({
        response,
        json: { ...json, items: modifiedItems, total: (json.total || 0) + 1 },
      });
    });

    const runsRes = await page.request.get("/api/runs");
    const runs = await runsRes.json();
    const runId = runs?.[0]?.id || "11111111-1111-4111-8111-111111111111";

    await page.goto(`/runs/${runId}?tab=accepted`);

    // Ensure page did not crash and hostile lead name is visible
    await expect(page.getByText("Hostile Crash Test Store")).toBeVisible({ timeout: 15_000 });
    expect(await page.locator("body").textContent()).not.toContain("[object Object]");
  });
});
