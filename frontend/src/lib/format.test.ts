import { describe, it, expect } from "vitest";
import { formatDate, formatDuration, formatPercent, computeWilsonScoreInterval } from "./format";

describe("format utilities", () => {
  it("formats date correctly", () => {
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate("2026-09-23T05:00:00Z")).toContain("Sep");
  });

  it("formats duration correctly", () => {
    expect(formatDuration(undefined)).toBe("—");
    expect(formatDuration(500)).toBe("500ms");
    expect(formatDuration(45000)).toBe("45.0s");
    expect(formatDuration(125000)).toBe("2m 5s");
  });

  it("formats percent correctly", () => {
    expect(formatPercent(undefined)).toBe("—");
    expect(formatPercent(0.854)).toBe("85.4%");
    expect(formatPercent(1)).toBe("100.0%");
  });

  it("computes Wilson score confidence interval", () => {
    const ci0 = computeWilsonScoreInterval(0, 0);
    expect(ci0.point).toBe(0);

    const ci = computeWilsonScoreInterval(19, 20);
    expect(ci.point).toBe(0.95);
    expect(ci.lower).toBeGreaterThan(0.7);
    expect(ci.upper).toBeLessThanOrEqual(1.0);
  });
});
