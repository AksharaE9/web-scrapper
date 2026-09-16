import {
  HealthStatus,
  KeywordPlan,
  KeywordPreset,
  Lead,
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

  async previewGeo(params: {
    text?: string;
    locality?: string;
    city?: string;
    state?: string;
    country?: string;
  }) {
    const searchParams = new URLSearchParams();
    if (params.text) searchParams.set("text", params.text);
    if (params.locality) searchParams.set("locality", params.locality);
    if (params.city) searchParams.set("city", params.city);
    if (params.state) searchParams.set("state", params.state);
    if (params.country) searchParams.set("country", params.country);

    const res = await fetch(`${BASE_URL}/api/geo/preview?${searchParams.toString()}`);
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

  async getRunLeads(
    runId: string,
    params?: { tier?: string; search?: string; min_confidence?: number }
  ): Promise<Lead[]> {
    const searchParams = new URLSearchParams();
    if (params?.tier) searchParams.set("tier", params.tier);
    if (params?.search) searchParams.set("search", params.search);
    if (params?.min_confidence !== undefined)
      searchParams.set("min_confidence", String(params.min_confidence));

    const res = await fetch(
      `${BASE_URL}/api/runs/${runId}/leads?${searchParams.toString()}`
    );
    if (!res.ok) throw new Error(`Get run leads failed: ${res.statusText}`);
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

  getExportUrl(runId: string, format: "csv" | "xlsx" = "csv"): string {
    return `${BASE_URL}/api/runs/${runId}/export?format=${format}`;
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
