import {
  ConceptCard,
  HealthStatus,
  KeywordPlan,
  KeywordPreset,
  Lead,
  LeadsResponse,
  QueryInput,
  RunSummary,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "";

export const api = {
  async getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${BASE_URL}/api/health`);
    if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
    return res.json();
  },

  async previewGeo(
    params: {
      text?: string;
      locality?: string;
      city?: string;
      state?: string;
      country?: string;
    },
    signal?: AbortSignal
  ) {
    const searchParams = new URLSearchParams();
    if (params.text) searchParams.set("text", params.text);
    if (params.locality) searchParams.set("locality", params.locality);
    if (params.city) searchParams.set("city", params.city);
    if (params.state) searchParams.set("state", params.state);
    if (params.country) searchParams.set("country", params.country);

    const res = await fetch(`${BASE_URL}/api/geo/preview?${searchParams.toString()}`, { signal });
    if (!res.ok) throw new Error(`Geo preview failed: ${res.statusText}`);
    return res.json();
  },

  async previewKeywordPlan(keyword: string): Promise<KeywordPlan> {
    const res = await fetch(
      `${BASE_URL}/api/keywords/preview?keyword=${encodeURIComponent(keyword)}`
    );
    if (!res.ok) throw new Error(`Keyword preview failed: ${res.statusText}`);
    return res.json();
  },

  async listPresets(): Promise<KeywordPreset[]> {
    const res = await fetch(`${BASE_URL}/api/presets`);
    if (!res.ok) throw new Error(`Fetch presets failed: ${res.statusText}`);
    return res.json();
  },

  async startRun(input: QueryInput): Promise<{ run_id: string; status: string }> {
    const res = await fetch(`${BASE_URL}/api/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Start run failed: ${res.statusText}`);
    }
    return res.json();
  },

  async listRuns(): Promise<RunSummary[]> {
    const res = await fetch(`${BASE_URL}/api/runs`);
    if (!res.ok) throw new Error(`List runs failed: ${res.statusText}`);
    return res.json();
  },

  async getRun(runId: string): Promise<RunSummary> {
    const res = await fetch(`${BASE_URL}/api/runs/${runId}`);
    if (!res.ok) throw new Error(`Get run failed: ${res.statusText}`);
    return res.json();
  },

  async rerun(runId: string): Promise<{ run_id: string; status: string }> {
    const res = await fetch(`${BASE_URL}/api/runs/${runId}/rerun`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(`Rerun failed: ${res.statusText}`);
    return res.json();
  },

  async cancelRun(runId: string): Promise<{ status: string }> {
    const res = await fetch(`${BASE_URL}/api/runs/${runId}/cancel`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(`Cancel run failed: ${res.statusText}`);
    return res.json();
  },

  async clearFailedRuns(): Promise<{ deleted_count: number; run_ids: string[] }> {
    const res = await fetch(`${BASE_URL}/api/runs/clear-failed`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(`Clear failed runs failed: ${res.statusText}`);
    return res.json();
  },

  async getConceptCard(keyword: string): Promise<ConceptCard> {
    const res = await fetch(`${BASE_URL}/api/concepts/${encodeURIComponent(keyword)}`);
    if (!res.ok) throw new Error(`Fetch concept card failed: ${res.statusText}`);
    return res.json();
  },

  async updateConceptCard(conceptId: string, card: Partial<ConceptCard>): Promise<ConceptCard> {
    const res = await fetch(`${BASE_URL}/api/concepts/${encodeURIComponent(conceptId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(card),
    });
    if (!res.ok) throw new Error(`Update concept card failed: ${res.statusText}`);
    return res.json();
  },

  async getRunLeads(
    runId: string,
    params?: {
      tier?: string;
      search?: string;
      min_confidence?: number;
      decision?: "accepted" | "review" | "rejected" | "all";
      limit?: number;
      cursor?: number;
      include_delivered?: boolean;
      include_suppressed?: boolean;
    }
  ): Promise<LeadsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.decision) searchParams.set("decision", params.decision);
    if (params?.tier) searchParams.set("tier", params.tier);
    if (params?.search) searchParams.set("q", params.search);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.cursor) searchParams.set("cursor", String(params.cursor));
    if (params?.include_delivered) searchParams.set("include_delivered", "true");
    if (params?.include_suppressed) searchParams.set("include_suppressed", "true");
    if (params?.min_confidence !== undefined)
      searchParams.set("min_confidence", String(params.min_confidence));

    const res = await fetch(
      `${BASE_URL}/api/runs/${runId}/leads?${searchParams.toString()}`
    );
    if (!res.ok) throw new Error(`Get run leads failed: ${res.statusText}`);
    const data = await res.json();
    if (data && Array.isArray(data.items)) {
      return data;
    }
    if (Array.isArray(data)) {
      return {
        items: data,
        total: data.length,
        counts: { accepted: data.length, review: 0, rejected: 0 },
        filters_applied: {},
      };
    }
    return {
      items: [],
      total: 0,
      counts: { accepted: 0, review: 0, rejected: 0 },
      filters_applied: {},
    };
  },

  async relabelLead(
    runId: string,
    businessId: string,
    verdict: "relevant" | "not_relevant" | "unsure",
    notes?: string
  ): Promise<any> {
    const res = await fetch(`${BASE_URL}/api/runs/${runId}/relevance/relabel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business_id: businessId, verdict, notes }),
    });
    if (!res.ok) throw new Error(`Relabel failed: ${res.statusText}`);
    return res.json();
  },

  async rescoreRun(runId: string): Promise<any> {
    const res = await fetch(`${BASE_URL}/api/runs/${runId}/rescore`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(`Rescore run failed: ${res.statusText}`);
    return res.json();
  },

  async getLead(leadId: string): Promise<Lead> {
    const res = await fetch(`${BASE_URL}/api/leads/${leadId}`);
    if (!res.ok) throw new Error(`Get lead detail failed: ${res.statusText}`);
    return res.json();
  },

  async submitLabel(leadId: string, label: "correct" | "incorrect" | "duplicate" | "out_of_area" | "wrong_category", notes?: string) {
    const res = await fetch(`${BASE_URL}/api/labels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business_id: leadId, label, notes }),
    });
    if (!res.ok) throw new Error(`Label submission failed: ${res.statusText}`);
    return res.json();
  },

  getExportUrl(
    runId: string,
    format: "csv" | "xlsx" = "csv",
    decision: string = "accepted",
    includeDelivered: boolean = false,
    includeSuppressed: boolean = false
  ): string {
    const params = new URLSearchParams({ format, decision });
    if (includeDelivered) params.set("include_delivered", "true");
    if (includeSuppressed) params.set("include_suppressed", "true");
    return `${BASE_URL}/api/runs/${runId}/export?${params.toString()}`;
  },

  async getConfigGraph(): Promise<Array<{ id: string; label: string; description: string; critical: boolean; order: number }>> {
    const res = await fetch(`${BASE_URL}/api/config/graph`);
    if (!res.ok) throw new Error(`Fetch config graph failed: ${res.statusText}`);
    return res.json();
  },

  async getConfigLexicon(): Promise<{ version: number; non_evidence_categories: Record<string, string[]>; non_evidence_terms: string[]; variants: Record<string, string[]> }> {
    const res = await fetch(`${BASE_URL}/api/config/lexicon`);
    if (!res.ok) throw new Error(`Fetch config lexicon failed: ${res.statusText}`);
    return res.json();
  },

  async getConfigSources(): Promise<Array<{ id: string; label: string; enabled: boolean; implemented: boolean; status: string; licence: string; note: string }>> {
    const res = await fetch(`${BASE_URL}/api/config/sources`);
    if (!res.ok) throw new Error(`Fetch config sources failed: ${res.statusText}`);
    return res.json();
  },

  async getConfigLimits(): Promise<{ max_results_min: number; max_results_max: number; default: number; warn_above: number; default_cache_age_days: number; max_cache_age_days: number }> {
    const res = await fetch(`${BASE_URL}/api/config/limits`);
    if (!res.ok) throw new Error(`Fetch config limits failed: ${res.statusText}`);
    return res.json();
  },

  async getConfigThresholds(): Promise<{ tau_hi: number; tau_lo: number; tiers: string[]; review_band: [number, number] }> {
    const res = await fetch(`${BASE_URL}/api/config/thresholds`);
    if (!res.ok) throw new Error(`Fetch config thresholds failed: ${res.statusText}`);
    return res.json();
  },

  subscribeRunEvents(
    runId: string,
    onEvent: (event: any) => void,
    onError?: (err: any) => void
  ): () => void {
    const eventSource = new EventSource(`${BASE_URL}/api/runs/${runId}/events`);

    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onEvent(data);
      } catch (err) {
        console.error("SSE parse error", err);
      }
    };

    eventSource.onerror = (e) => {
      if (onError) onError(e);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  },
};
