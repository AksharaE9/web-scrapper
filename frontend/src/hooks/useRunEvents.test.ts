import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useRunEvents } from "./useRunEvents";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

describe("useRunEvents", () => {
  let mockEventSourceInstances: any[] = [];

  beforeEach(() => {
    mockEventSourceInstances = [];
    global.EventSource = vi.fn().mockImplementation((url: string) => {
      const listeners: Record<string, Function[]> = {};
      const instance = {
        url,
        close: vi.fn(),
        addEventListener: vi.fn((event: string, handler: Function) => {
          if (!listeners[event]) listeners[event] = [];
          listeners[event].push(handler);
        }),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
        onerror: null as any,
        onmessage: null as any,
        onopen: null as any,
        _trigger: (event: string, data: any) => {
          if (listeners[event]) {
            listeners[event].forEach((h) => h({ type: event, data: JSON.stringify(data) }));
          }
        },
      };
      mockEventSourceInstances.push(instance);
      return instance;
    }) as any;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  function createWrapper() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children);
  }

  it("creates exactly one EventSource for the run", () => {
    const wrapper = createWrapper();
    renderHook(() => useRunEvents("test-run-123"), { wrapper });

    expect(mockEventSourceInstances).toHaveLength(1);
    expect(mockEventSourceInstances[0].url).toContain("test-run-123");
  });

  it("calls close() on unmount", () => {
    const wrapper = createWrapper();
    const { unmount } = renderHook(() => useRunEvents("test-run-123"), { wrapper });

    expect(mockEventSourceInstances[0].close).not.toHaveBeenCalled();
    unmount();
    expect(mockEventSourceInstances[0].close).toHaveBeenCalled();
  });

  it("ignores events with foreign run_id", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useRunEvents("my-run-id"), { wrapper });

    act(() => {
      mockEventSourceInstances[0]._trigger("lead_accepted", {
        run_id: "other-foreign-run-id",
        lead: { id: "foreign-lead", name: "Foreign Lead" },
      });
    });

    expect(result.current.streamedLeads).toHaveLength(0);
  });

  it("terminal event updates terminal state and sets status", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useRunEvents("my-run-id"), { wrapper });

    act(() => {
      mockEventSourceInstances[0]._trigger("run_completed", {
        run_id: "my-run-id",
        counts: { accepted: 10, review: 2, rejected: 1 },
      });
    });

    expect(result.current.terminalState).toBe("completed");
    expect(result.current.status).toBe("closed");
  });

  it("client-side safety net reconciles all nodes so zero nodes remain in running state after run_completed (§3.4)", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useRunEvents("my-run-id"), { wrapper });

    // Simulate n12_report or n10_persist stuck in running
    act(() => {
      mockEventSourceInstances[0]._trigger("node_started", {
        run_id: "my-run-id",
        node: "n12_report",
        status: "running",
      });
      mockEventSourceInstances[0]._trigger("node_started", {
        run_id: "my-run-id",
        node: "n10_persist",
        status: "running",
      });
    });

    expect(result.current.nodes["n12_report"]?.status).toBe("running");
    expect(result.current.nodes["n10_persist"]?.status).toBe("running");

    // Publish terminal event
    act(() => {
      mockEventSourceInstances[0]._trigger("run_completed", {
        run_id: "my-run-id",
        counts: { accepted: 10, review: 2, rejected: 1 },
      });
    });

    // Verify ZERO nodes remain in running state
    const runningNodes = Object.values(result.current.nodes).filter((n) => n.status === "running");
    expect(runningNodes).toHaveLength(0);
    expect(result.current.nodes["n12_report"]?.status).toBe("completed");
    expect(result.current.nodes["n10_persist"]?.status).toBe("completed");
  });
});

