import { test, expect } from "@playwright/test";

test.describe("Full pipeline run", () => {
  test("create a run, watch it live, see the leads on screen", async ({ page }) => {
    // ── fail the test on ANY console error ────────────────────────────────
    const consoleErrors: string[] = [];
    page.on("console", (m) => {
      if (m.type() !== "error") return;
      const t = m.text();
      if (t.includes("chrome-extension://")) return; // writing-assistant ext, not ours
      consoleErrors.push(t);
    });
    page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message}`));

    // ── 1. configure ──────────────────────────────────────────────────────
    await page.goto("/scrape");
    await page.getByLabel(/locality/i).fill("HSR Layout");
    await page.getByLabel(/^city/i).fill("Bengaluru");
    await page.getByLabel(/state/i).fill("Karnataka");
    await page.getByLabel(/country/i).fill("India");

    // boundary resolves and is described in words
    await expect(page.getByTestId("boundary-summary")).toContainText(/HSR Layout/i, { timeout: 20_000 });
    await expect(page.getByTestId("boundary-kind")).toContainText(/polygon|circle/i);

    await page.getByPlaceholder(/add.*keyword/i).fill("pooja store");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("keyword-chip")).toHaveCount(1);

    await page.getByTestId("max-results").fill("30");

    // stub sources must be disabled, not merely unchecked
    for (const s of ["wikidata", "alltheplaces"]) {
      const el = page.getByTestId(`source-${s}`);
      if ((await el.count()) > 0) await expect(el).toBeDisabled();
    }

    // ── 2. launch ─────────────────────────────────────────────────────────
    await page.getByRole("button", { name: /launch|run/i }).click();
    await expect(page).toHaveURL(/\/runs\/[0-9a-f-]{36}\/live/, { timeout: 10_000 });
    const runId = page.url().match(/runs\/([0-9a-f-]{36})/)![1];

    // ── 3. live progress must be REAL, not a spinner ──────────────────────
    await expect(page.getByTestId("node-n1_geo")).toHaveAttribute("data-state", "done", { timeout: 60_000 });
    // a finished node never says Pending
    const n1 = page.getByTestId("node-n1_geo");
    await expect(n1).not.toContainText(/pending/i);

    await expect(page.getByTestId("node-n3a_overture")).toHaveAttribute("data-state", /running|done/, { timeout: 60_000 });
    await expect(page.getByTestId("source-ticker-overture")).toContainText(/cache|live/i);

    // leads stream in BEFORE completion
    await expect(page.getByTestId("live-lead-item").first()).toBeVisible({ timeout: 150_000 });
    const liveCount = await page.getByTestId("live-lead-item").count();
    expect(liveCount).toBeGreaterThan(0);

    // ── 4. terminal state ─────────────────────────────────────────────────
    await expect(page.getByTestId("run-status")).toHaveText(/completed|partial/i, { timeout: 180_000 });

    // ── 5. THE POINT OF THE WHOLE TEST: leads are visible ─────────────────
    await page.goto(`/runs/${runId}?tab=accepted`);
    const acceptedCount = Number((await page.getByTestId("tab-accepted-count").textContent())!.trim());
    expect(acceptedCount).toBeGreaterThan(0);

    const rows = page.getByTestId("lead-row");
    await expect(rows.first()).toBeVisible({ timeout: 15_000 });
    expect(await rows.count()).toBe(acceptedCount); // count == rows, exactly

    // every row shows a name and at least one contact
    for (let i = 0; i < Math.min(await rows.count(), 10); i++) {
      const r = rows.nth(i);
      await expect(r.getByTestId("lead-name")).not.toBeEmpty();
      const contact = await r.getByTestId("lead-contact").textContent();
      expect(contact?.trim().length).toBeGreaterThan(0);
    }

    // no object leaked into the DOM
    expect(await page.locator("body").textContent()).not.toContain("[object Object]");

    // ── 6. drawer shows provenance ────────────────────────────────────────
    await rows.first().click();
    await expect(page.getByTestId("lead-drawer")).toBeVisible();
    await expect(page.getByTestId("provenance-list")).not.toBeEmpty();
    await page.keyboard.press("Escape");

    // ── 7. exhaustion is shown ALONGSIDE leads, never instead ─────────────
    const reason = await page.getByTestId("completion-reason").textContent();
    if (/exhaust/i.test(reason ?? "")) {
      await expect(page.getByTestId("exhaustion-banner")).toBeVisible();
      expect(await rows.count()).toBeGreaterThan(0); // ← the bug you hit
    }

    // ── 8. export ─────────────────────────────────────────────────────────
    const dl = page.waitForEvent("download");
    await page.getByRole("button", { name: /csv/i }).click();
    const file = await dl;
    expect(file.suggestedFilename()).toMatch(/\.csv$/);

    // ── 9. clean console ──────────────────────────────────────────────────
    expect(consoleErrors, `Console errors:\n${consoleErrors.join("\n")}`).toHaveLength(0);
  });
});
