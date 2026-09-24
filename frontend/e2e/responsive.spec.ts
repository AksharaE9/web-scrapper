import { test, expect } from "@playwright/test";

test.describe("Responsive Viewports", () => {
  const viewports = [
    { width: 380, height: 800, name: "mobile" },
    { width: 768, height: 1024, name: "tablet" },
    { width: 1280, height: 800, name: "desktop" },
    { width: 1920, height: 1080, name: "wide" },
  ];

  for (const vp of viewports) {
    test(`renders cleanly without horizontal overflow at ${vp.width}x${vp.height} (${vp.name})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/scrape");

      // Verify page body does not have severe horizontal scroll overflow
      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2); // 2px margin of error for subpixel layout
    });
  }
});
