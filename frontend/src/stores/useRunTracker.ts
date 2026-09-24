import { create } from "zustand";

export interface ActiveRunInfo {
  runId: string;
  query: string;
  locality: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  currentNode?: string;
  leadsFound: number;
  startedAt: number;
}

interface RunTrackerState {
  activeRuns: Record<string, ActiveRunInfo>;
  trackRun: (runId: string, query: string, locality: string) => void;
  updateRunProgress: (runId: string, update: Partial<ActiveRunInfo>) => void;
  markRunFinished: (runId: string, finalStatus: "completed" | "failed" | "cancelled") => void;
  clearRun: (runId: string) => void;
  getActiveCount: () => number;
}

export const useRunTracker = create<RunTrackerState>()((set, get) => ({
  activeRuns: {},
  trackRun: (runId, query, locality) =>
    set((s) => ({
      activeRuns: {
        ...s.activeRuns,
        [runId]: {
          runId,
          query,
          locality,
          status: "running",
          leadsFound: 0,
          startedAt: Date.now(),
        },
      },
    })),
  updateRunProgress: (runId, update) =>
    set((s) => {
      const existing = s.activeRuns[runId];
      if (!existing) return s;
      return {
        activeRuns: {
          ...s.activeRuns,
          [runId]: { ...existing, ...update },
        },
      };
    }),
  markRunFinished: (runId, finalStatus) =>
    set((s) => {
      const existing = s.activeRuns[runId];
      if (!existing) return s;
      return {
        activeRuns: {
          ...s.activeRuns,
          [runId]: { ...existing, status: finalStatus },
        },
      };
    }),
  clearRun: (runId) =>
    set((s) => {
      const copy = { ...s.activeRuns };
      delete copy[runId];
      return { activeRuns: copy };
    }),
  getActiveCount: () => {
    const runs = Object.values(get().activeRuns);
    return runs.filter((r) => r.status === "running" || r.status === "queued").length;
  },
}));
