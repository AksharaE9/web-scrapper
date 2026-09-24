import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("Accessibility (A11y)", () => {
  const routes = ["/scrape", "/runs", "/quality"];

  for (const route of routes) {
    test(`zero critical a11y violations on ${route}`, async ({ page }) => {
      await page.goto(route);
      await page.waitForLoadState("domcontentloaded");

      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();

      const criticalViolations = accessibilityScanResults.violations.filter(
        (v) => v.impact === "critical"
      );

      expect(criticalViolations, `Found critical a11y issues on ${route}: ${JSON.stringify(criticalViolations, null, 2)}`).toHaveLength(0);
    });
  }
});
