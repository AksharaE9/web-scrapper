import { useQuery } from "@tanstack/react-query";
import { qk } from "../lib/queryKeys";
import { QualityMetrics } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "";

export interface RawMetricSnapshot {
  metric_name: string;
  value: number;
  run_id?: string | null;
  computed_at: string;
  metadata?: Record<string, any>;
}

export interface RunSummaryItem {
  id: string;
  target: string;
  status: string;
  created_at: string | null;
  candidate_count: number;
  entity_count: number;
}

interface GlobalMetricsResponse {
  metrics: RawMetricSnapshot[];
  live_summary?: {
    total_entities: number;
    tier_distribution: {
      Verified: number;
      Likely: number;
      Unverified: number;
    };
    completeness: {
      phone_rate: number;
      email_rate: number;
      website_rate: number;
      address_rate: number;
    };
    average_confidence: number;
    multi_source_count: number;
    capture_recapture?: QualityMetrics["capture_recapture"];
    funnel?: {
      raw_ingested: number;
      relevance_passed: number;
      resolved_entities: number;
      verified_leads: number;
    };
  };
}

/** Aggregate a flat array of named snapshots or live_summary into the QualityMetrics shape. */
function aggregate(data: GlobalMetricsResponse): QualityMetrics {
  if (data.live_summary) {
    return {
      total_entities: data.live_summary.total_entities,
      tier_distribution: data.live_summary.tier_distribution,
      completeness: data.live_summary.completeness,
      average_confidence: data.live_summary.average_confidence,
      multi_source_count: data.live_summary.multi_source_count,
      capture_recapture: data.live_summary.capture_recapture,
      funnel: data.live_summary.funnel,
    };
  }

  const snaps = data.metrics || [];
  const get = (name: string): number | undefined => {
    const found = snaps
      .filter((s) => s.metric_name === name)
      .sort((a, b) => b.computed_at.localeCompare(a.computed_at))[0];
    return found?.value;
  };

  const v = get("tier_verified") ?? 0;
  const l = get("tier_likely") ?? 0;
  const u = get("tier_unverified") ?? 0;
  const total = get("total_entities") ?? (v + l + u);

  return {
    total_entities: total,
    tier_distribution: {
      Verified: v,
      Likely: l,
      Unverified: u,
    },
    completeness: {
      phone_rate: get("phone_completeness") ?? get("phone_rate") ?? 0,
      email_rate: get("email_completeness") ?? get("email_rate") ?? 0,
      website_rate: get("website_completeness") ?? get("website_rate") ?? 0,
      address_rate: get("address_completeness") ?? get("address_rate") ?? 1,
    },
    average_confidence: get("avg_confidence") ?? get("average_confidence") ?? 0,
    multi_source_count: Math.round(get("multi_source_count") ?? 0),
    capture_recapture: (() => {
      const cr = snaps.find((s) => s.metric_name === "capture_recapture");
      if (!cr?.metadata) return undefined;
      return cr.metadata as QualityMetrics["capture_recapture"];
    })(),
  };
}

export function useGlobalQualityMetrics() {
  return useQuery<QualityMetrics>({
    queryKey: qk.qualityMetrics(),
    queryFn: async () => {
      const res = await fetch(`${BASE_URL}/api/metrics/global`);
      if (!res.ok) throw new Error(`Global metrics fetch failed: ${res.statusText}`);
      const data: GlobalMetricsResponse = await res.json();
      return aggregate(data);
    },
    staleTime: 5_000,
    refetchInterval: 5_000, // 5s fast live sync
    retry: 1,
  });
}

export function useRunsMetricsList() {
  return useQuery<{ runs: RunSummaryItem[] }>({
    queryKey: ["runs_metrics_list"],
    queryFn: async () => {
      const res = await fetch(`${BASE_URL}/api/metrics/runs`);
      if (!res.ok) throw new Error(`Runs list fetch failed: ${res.statusText}`);
      return res.json();
    },
    staleTime: 5_000,
    refetchInterval: 5_000,
  });
}

export function useRunQualityMetrics(runId: string | null) {
  return useQuery<QualityMetrics>({
    queryKey: qk.runMetrics(runId ?? ""),
    queryFn: async () => {
      const res = await fetch(`${BASE_URL}/api/metrics/runs/${runId}`);
      if (!res.ok) throw new Error(`Run metrics fetch failed: ${res.statusText}`);
      const data = await res.json();
      return aggregate(data);
    },
    enabled: !!runId && runId !== "global",
    staleTime: 5_000,
    refetchInterval: 5_000,
    retry: 1,
  });
}
