import { describe, it, expect } from "vitest";
import React from "react";
import { renderSafe } from "./renderSafe";

describe("renderSafe", () => {
  it("renders strings and numbers directly", () => {
    expect(renderSafe("hello world", "test")).toBe("hello world");
    expect(renderSafe(42, "test")).toBe(42);
    expect(renderSafe(0, "test")).toBe(0);
  });

  it("returns null for null, undefined, and false", () => {
    expect(renderSafe(null, "test")).toBeNull();
    expect(renderSafe(undefined, "test")).toBeNull();
    expect(renderSafe(false, "test")).toBeNull();
  });

  it("handles React elements cleanly", () => {
    const elem = React.createElement("span", null, "test");
    expect(renderSafe(elem, "test")).toBe(elem);
  });

  it("degrades gracefully and does not throw when given a raw object with type, label, icon", () => {
    const rawObj = { type: "positive", label: "Matched Category", icon: "check" };
    
    // Must not throw error
    let result: React.ReactNode;
    expect(() => {
      result = renderSafe(rawObj, "test-context");
    }).not.toThrow();

    // In non-prod or prod, returns safely without throwing
    expect(result).toBeDefined();
  });

  it("recursively handles arrays safely", () => {
    const arr = ["item1", 123, null, { type: "info", label: "badge" }];
    expect(() => {
      renderSafe(arr, "array-test");
    }).not.toThrow();
  });
});
