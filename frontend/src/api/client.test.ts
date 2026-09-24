import { describe, it, expect } from "vitest";
import { api } from "./client";

describe("API Client", () => {
  it("fetches health check", async () => {
    const health = await api.getHealth();
    expect(health.status).toBe("ok");
  });

  it("fetches list of runs", async () => {
    const runs = await api.listRuns();
    expect(runs).toHaveLength(1);
    expect(runs[0].locality).toBe("HSR Layout");
  });

  it("fetches single run", async () => {
    const run = await api.getRun("11111111-1111-4111-8111-111111111111");
    expect(run.id).toBe("11111111-1111-4111-8111-111111111111");
  });

  it("fetches leads for a run", async () => {
    const leads = await api.getRunLeads("11111111-1111-4111-8111-111111111111", { decision: "accepted" });
    expect(leads.items.length).toBeGreaterThan(0);
    expect(leads.total).toBe(19);
    expect(leads.counts.accepted).toBe(19);
  });

  it("creates, reruns, cancels a run and clears failed runs", async () => {
    const res = await api.startRun({
      locality: "HSR Layout",
      city: "Bengaluru",
      keywords: ["pooja store"],
    } as any);
    expect(res.run_id).toBe("11111111-1111-4111-8111-111111111111");

    const rerunRes = await api.rerun("11111111-1111-4111-8111-111111111111");
    expect(rerunRes.status).toBe("queued");

    const cancelRes = await api.cancelRun("11111111-1111-4111-8111-111111111111");
    expect(cancelRes.status).toBe("cancelled");

    const clearRes = await api.clearFailedRuns();
    expect(clearRes.deleted_count).toBe(0);
  });

  it("fetches configuration endpoints", async () => {
    const sources = await api.getConfigSources();
    expect(sources.length).toBeGreaterThan(0);

    const limits = await api.getConfigLimits();
    expect(limits.max_results_max).toBe(200);

    const thresholds = await api.getConfigThresholds();
    expect(thresholds.tau_hi).toBe(0.7);

    const graph = await api.getConfigGraph();
    expect(graph.length).toBeGreaterThan(0);

    const lexicon = await api.getConfigLexicon();
    expect(lexicon.version).toBe(1);
  });

  it("exports run csv url", () => {
    const url = api.getExportUrl("run-123", "csv");
    expect(url).toContain("/api/runs/run-123/export?format=csv");
  });
});
