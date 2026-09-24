import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useDebounce } from "./useDebounce";
import { useKeyboardShortcut } from "./useKeyboardShortcut";

describe("Utility Hooks", () => {
  it("debounces value changes", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ value, delay }) => useDebounce(value, delay), {
      initialProps: { value: "first", delay: 300 },
    });

    expect(result.current).toBe("first");

    rerender({ value: "second", delay: 300 });
    expect(result.current).toBe("first");

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current).toBe("second");
    vi.useRealTimers();
  });

  it("handles keyboard shortcuts", () => {
    const callback = vi.fn();
    renderHook(() => useKeyboardShortcut("k", callback, { ctrlOrCmd: true }));

    const event = new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true });
    window.dispatchEvent(event);

    expect(callback).toHaveBeenCalled();
  });
});
