import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { useGlobalQualityMetrics, useRunQualityMetrics } from "./useQualityMetrics";
import { useLeads } from "./useLeads";
import { createWrapper } from "../test/utils";

describe("Custom Data Hooks", () => {
  it("fetches global quality metrics", async () => {
    const { result } = renderHook(() => useGlobalQualityMetrics(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total_entities).toBeDefined();
  });

  it("fetches run quality metrics", async () => {
    const { result } = renderHook(() => useRunQualityMetrics("11111111-1111-4111-8111-111111111111"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total_entities).toBeDefined();
  });

  it("fetches run leads", async () => {
    const { result } = renderHook(() => useLeads("11111111-1111-4111-8111-111111111111", { decision: "accepted" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items.length).toBeGreaterThan(0);
    expect(result.current.data?.total).toBe(19);
    expect(result.current.data?.counts.accepted).toBe(19);
  });
});
