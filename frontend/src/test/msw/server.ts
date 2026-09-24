import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
import { GOLDEN_RUN, GOLDEN_LEADS } from "../fixtures/goldenRun";

export const handlers = [
  http.get("*/api/health", () =>
    HttpResponse.json({
      status: "ok",
      db: { engine: "postgresql", ok: true },
      queue: {
        worker: { state: "healthy" },
        depth: { queued: 0, running: 0, oldest_queued_age_s: 0 },
      },
    })
  ),
  http.get("*/api/runs", () => HttpResponse.json([GOLDEN_RUN])),
  http.get("*/api/runs/:id", ({ params }) => {
    if (params.id === "00000000-0000-0000-0000-000000000000" || params.id === "not-found") {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(GOLDEN_RUN);
  }),
  http.get("*/api/runs/:id/leads", ({ request }) => {
    const tab = new URL(request.url).searchParams.get("decision") ?? "accepted";
    return HttpResponse.json(
      tab === "accepted"
        ? GOLDEN_LEADS
        : { items: [], total: 0, next_cursor: null }
    );
  }),
  http.get("*/api/leads/:id", () => {
    return HttpResponse.json(GOLDEN_LEADS.items[0]);
  }),
  http.get("*/api/metrics/global", () => {
    return HttpResponse.json({
      metrics: [],
      live_summary: {
        total_entities: 19,
        tier_distribution: { Verified: 10, Likely: 9, Unverified: 0 },
        completeness: { phone_rate: 0.9, email_rate: 0.5, website_rate: 0.6, address_rate: 1.0 },
        average_confidence: 0.85,
        multi_source_count: 5,
      },
    });
  }),
  http.get("*/api/metrics/runs", () => {
    return HttpResponse.json({
      runs: [{ id: GOLDEN_RUN.id, target: "pooja store", status: "completed", created_at: GOLDEN_RUN.created_at, candidate_count: 100, entity_count: 19 }],
    });
  }),
  http.get("*/api/metrics/runs/:id", () => {
    return HttpResponse.json({
      metrics: [],
      live_summary: {
        total_entities: 19,
        tier_distribution: { Verified: 10, Likely: 9, Unverified: 0 },
        completeness: { phone_rate: 0.9, email_rate: 0.5, website_rate: 0.6, address_rate: 1.0 },
        average_confidence: 0.85,
        multi_source_count: 5,
      },
    });
  }),
  http.get("*/api/config/sources", () => {
    return HttpResponse.json([
      { id: "overture", label: "Overture Places", enabled: true, implemented: true, status: "live", licence: "CDLA-Permissive", note: "Primary" },
      { id: "osm", label: "OpenStreetMap", enabled: true, implemented: true, status: "live", licence: "ODbL", note: "Secondary" },
      { id: "wikidata", label: "Wikidata", enabled: false, implemented: false, status: "stub", licence: "CC0", note: "Stub" },
      { id: "alltheplaces", label: "AllThePlaces", enabled: false, implemented: false, status: "stub", licence: "MIT", note: "Stub" },
    ]);
  }),
  http.get("*/api/config/limits", () => {
    return HttpResponse.json({
      max_results_min: 1,
      max_results_max: 200,
      default: 50,
      warn_above: 100,
      default_cache_age_days: 30,
      max_cache_age_days: 90,
    });
  }),
  http.get("*/api/config/thresholds", () => {
    return HttpResponse.json({
      tau_hi: 0.7,
      tau_lo: 0.4,
      tiers: ["Verified", "Likely", "Unverified"],
      review_band: [0.4, 0.7],
    });
  }),
  http.get("*/api/config/graph", () => {
    return HttpResponse.json([
      { id: "n1_geo", label: "Geo Boundary", description: "Resolve bounds", critical: true, order: 1 },
    ]);
  }),
  http.get("*/api/config/lexicon", () => {
    return HttpResponse.json({
      version: 1,
      non_evidence_categories: {},
      non_evidence_terms: [],
      variants: {},
    });
  }),
  http.post("*/api/runs", () =>
    HttpResponse.json(
      { run_id: GOLDEN_RUN.id, status: "queued" },
      { status: 202 }
    )
  ),
  http.post("*/api/runs/:id/rerun", () =>
    HttpResponse.json({ run_id: GOLDEN_RUN.id, status: "queued" }, { status: 202 })
  ),
  http.post("*/api/runs/:id/cancel", () =>
    HttpResponse.json({ status: "cancelled" })
  ),
  http.post("*/api/runs/clear-failed", () =>
    HttpResponse.json({ deleted_count: 0, run_ids: [] })
  ),
];

export const server = setupServer(...handlers);
