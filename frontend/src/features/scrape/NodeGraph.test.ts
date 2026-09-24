import { describe, it, expect } from "vitest";
import { deriveNodeState, getNodeStatusText } from "./NodeGraph";
import { NodeEvent } from "../../types";

describe("NodeGraph state machine (deriveNodeState)", () => {
  it("returns 'pending' when no event is present", () => {
    expect(deriveNodeState(undefined)).toBe("pending");
    expect(getNodeStatusText("pending")).toBe("Pending");
  });

  it("returns 'running' when event status is running", () => {
    const ev: NodeEvent = {
      run_id: "test-run",
      node: "n1_geo",
      status: "running",
    };
    expect(deriveNodeState(ev)).toBe("running");
  });

  it("asserts a node with duration_ms > 0 can never display 'Pending'", () => {
    // Crucial bug fix test: A node that reported duration_ms or elapsed_ms is finished, not Pending
    const ev: NodeEvent = {
      run_id: "test-run",
      node: "n2_keyword",
      status: "running",
      duration_ms: 625,
      count: 5,
    };
    const state = deriveNodeState(ev);
    expect(state).toBe("done");
    expect(state).not.toBe("pending");
    expect(getNodeStatusText(state, 5)).toBe("5 items");
  });

  it("returns 'done' when status is completed", () => {
    const ev: NodeEvent = {
      run_id: "test-run",
      node: "n1_geo",
      status: "completed",
    };
    expect(deriveNodeState(ev)).toBe("done");
    expect(getNodeStatusText("done")).toBe("Done");
  });

  it("returns 'failed' when status is failed", () => {
    const ev: NodeEvent = {
      run_id: "test-run",
      node: "n3a_overture",
      status: "failed",
      error: "Timeout connecting to parquet source",
    };
    expect(deriveNodeState(ev)).toBe("failed");
    expect(getNodeStatusText("failed")).toBe("Failed");
  });

  it("returns 'skipped' when status is skipped", () => {
    const ev: NodeEvent = {
      run_id: "test-run",
      node: "n3d_alltheplaces",
      status: "skipped",
    };
    expect(deriveNodeState(ev)).toBe("skipped");
    expect(getNodeStatusText("skipped")).toBe("Skipped");
  });

  it("asserts a node with elapsed_ms > 0 displays 'done' and never 'pending'", () => {
    const ev = {
      run_id: "test-run",
      node: "n1_geo",
      elapsed_ms: 450,
    } as any;
    const state = deriveNodeState(ev);
    expect(state).toBe("done");
    expect(getNodeStatusText(state)).not.toBe("Pending");
  });

  it("resets downstream nodes to pending when upstream node runs in a higher pass", () => {
    // n7_verify has event from pass 0 (iteration 0)
    const evN7: NodeEvent = {
      run_id: "test-run",
      node: "n7_verify",
      status: "completed",
      duration_ms: 4000,
      iteration: 0,
    };
    // n6_enrich is actively running in pass 2 (iteration 1)
    // activeCycleNodeIndex for n6_enrich is 0, thisCycleIndex for n7_verify is 1
    const state = deriveNodeState(evN7, false, 1, 0, 1);
    expect(state).toBe("pending");
  });

  it("formats crawl progress correctly in status text", () => {
    const ev: NodeEvent = {
      run_id: "test-run",
      node: "n6_enrich",
      status: "running",
      progress: {
        done: 12,
        total: 25,
        current_domain: "example.com",
      },
    };
    expect(getNodeStatusText("running", ev)).toBe("12 / 25 domains");
  });
});

