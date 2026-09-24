export interface RunFilters {
  status?: string;
  search?: string;
  limit?: number;
}

export interface LeadFilters {
  decision?: "accepted" | "review" | "rejected";
  tier?: string;
  search?: string;
  min_confidence?: number;
}

export const qk = {
  health: ["health"] as const,
  presets: ["presets"] as const,
  geoPreview: (text?: string, locality?: string, city?: string, state?: string, country?: string) =>
    ["geoPreview", { text, locality, city, state, country }] as const,
  keywordPlan: (kw: string) => ["keywordPlan", kw] as const,
  runs: (f?: RunFilters) => ["runs", f ?? {}] as const,
  run: (id: string | null) => ["run", id] as const,
  leads: (id: string | null, f?: LeadFilters) => ["runLeads", id, f ?? {}] as const,
  lead: (id: string | null) => ["lead", id] as const,
  concept: (kw: string) => ["concept", kw] as const,
  metrics: (scope: string, id?: string | null) => ["metrics", scope, id ?? null] as const,
  qualityMetrics: () => ["metrics", "global"] as const,
  runMetrics: (runId: string) => ["metrics", "run", runId] as const,
  configGraph: ["config", "graph"] as const,
  configLexicon: ["config", "lexicon"] as const,
  configSources: ["config", "sources"] as const,
  configLimits: ["config", "limits"] as const,
  configThresholds: ["config", "thresholds"] as const,
};
