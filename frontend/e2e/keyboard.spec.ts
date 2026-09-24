import { test, expect } from "@playwright/test";

test.describe("Keyboard Navigation", () => {
  test("allows full keyboard navigation on scrape form", async ({ page }) => {
    await page.goto("/scrape");

    const localityInput = page.getByLabel(/locality/i);
    await localityInput.focus();
    await page.keyboard.type("Indiranagar");

    const keywordInput = page.getByPlaceholder(/add.*keyword/i);
    await keywordInput.focus();
    await page.keyboard.type("coffee roasters");
    await page.keyboard.press("Enter");

    await expect(page.getByTestId("keyword-chip")).toHaveCount(1);
  });
});
