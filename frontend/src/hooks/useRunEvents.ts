import { useEffect, useState, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { NodeEvent, Lead } from "../types";
import { qk } from "../lib/queryKeys";
import { useRunTracker } from "../stores/useRunTracker";

export type ConnectionStatus = "idle" | "connecting" | "open" | "reconnecting" | "stalled" | "closed";
export type TerminalRunState = "completed" | "partial" | "zero_results" | "failed" | "cancelled" | null;

const TERMINAL_EVENTS = new Set(["run_completed", "run_failed", "run_cancelled", "completed", "failed", "cancelled"]);
const BASE_URL = import.meta.env.VITE_API_URL || "";

export interface SourceTickerStatus {
  source: string;
  label: string;
  status: "idle" | "reading_cache" | "live" | "completed" | "failed";
  details: string;
  candidatesCount: number;
}

export interface ExpansionExhausted {
  target: number;
  found: number;
  review_available: number;
  message: string;
  suggestions: string[];
  rungs_tried: Array<{ rung: number; strategy: string; accepted: number; review: number }>;
}

export function useRunEvents(runId: string | null) {
  const [nodes, setNodes] = useState<Record<string, NodeEvent>>({});
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [lastEventTime, setLastEventTime] = useState<number>(Date.now());
  const [streamedLeads, setStreamedLeads] = useState<Partial<Lead>[]>([]);
  const [counts, setCounts] = useState({ accepted: 0, review: 0, rejected: 0 });
  const [terminalState, setTerminalState] = useState<TerminalRunState>(null);
  const [errorDetails, setErrorDetails] = useState<{ message: string; node?: string } | null>(null);
  const [sourceCounts, setSourceCounts] = useState<Record<string, number>>({});
  const [expansionExhausted, setExpansionExhausted] = useState<ExpansionExhausted | null>(null);
  const [conceptMissing, setConceptMissing] = useState<string | null>(null);

  const qc = useQueryClient();
  const updateRunProgress = useRunTracker((s) => s.updateRunProgress);
  const markRunFinished = useRunTracker((s) => s.markRunFinished);

  const retryCountRef = useRef(0);
  const timerRef = useRef<number | undefined>(undefined);
  const stalledCheckRef = useRef<number | undefined>(undefined);

  // Refs to avoid stale closures in the stall-detection interval
  const statusRef = useRef<ConnectionStatus>("idle");
  const lastEventTimeRef = useRef<number>(Date.now());

  const setStatusSynced = useCallback((s: ConnectionStatus) => {
    statusRef.current = s;
    setStatus(s);
  }, []);

  const setLastEventTimeSynced = useCallback((t: number) => {
    lastEventTimeRef.current = t;
    setLastEventTime(t);
  }, []);

  useEffect(() => {
    if (!runId) {
      setStatusSynced("idle");
      setNodes({});
      setStreamedLeads([]);
      setCounts({ accepted: 0, review: 0, rejected: 0 });
      setTerminalState(null);
      setErrorDetails(null);
      setSourceCounts({});
      setExpansionExhausted(null);
      setConceptMissing(null);
      return;
    }

    let es: EventSource | null = null;
    let isCancelled = false;

    const EVENT_TYPES = [
      "message",
      "node_started",
      "node_finished",
      "node_progress",
      "node_failed",
      "lead_accepted",
      "candidates_found",
      "relevance_progress",
      "expansion_exhausted",
      "expansion_rung",
      "concept_missing",
      "run_completed",
      "run_failed",
      "run_cancelled",
      "completed",
      "failed",
      "cancelled",
      "heartbeat",
    ];

    const connect = () => {
      if (isCancelled) return;
      setStatusSynced(retryCountRef.current > 0 ? "reconnecting" : "connecting");

      es = new EventSource(`${BASE_URL}/api/runs/${runId}/events`);

      es.onopen = () => {
        if (isCancelled) return;
        retryCountRef.current = 0;
        setStatusSynced("open");
        setLastEventTimeSynced(Date.now());
      };

      const handleEventMessage = (e: MessageEvent) => {
        if (isCancelled) return;
        setLastEventTimeSynced(Date.now());
        setStatusSynced("open");

        if (!e.data || e.data === "{}" || e.type === "heartbeat") {
          return;
        }

        try {
          const ev = typeof e.data === "string" ? JSON.parse(e.data) : e.data;
          if (ev.run_id && ev.run_id !== runId) return;

          const eventName = ev.event || ev.type || e.type || "";

          // Node Progress & DAG Updates
          if (ev.node) {
            const nodeStatus = ev.status || (
              eventName === "node_started" ? "running" :
              eventName === "node_finished" ? "completed" :
              eventName === "node_failed" ? "failed" :
              eventName === "node_progress" ? "running" : "running"
            );
            const nodePayload: NodeEvent = {
              run_id: ev.run_id || runId,
              node: ev.node,
              status: nodeStatus as any,
              duration_ms: ev.elapsed_ms ?? ev.duration_ms,
              count: ev.count ?? ev.candidate_count ?? ev.leads_found,
              iteration: typeof ev.iteration === "number" ? ev.iteration : 0,
              seq: ev.seq,
              attempt: ev.attempt,
              progress: ev.done !== undefined && ev.total !== undefined ? {
                done: ev.done,
                total: ev.total,
                current_domain: ev.current_domain,
                ok: ev.ok,
                blocked: ev.blocked,
                failed: ev.failed,
                fields_enriched: ev.fields_enriched,
              } : undefined,
              error: typeof ev.error === "string" ? ev.error : ev.error?.message,
            };
            setNodes((prev) => ({ ...prev, [ev.node]: nodePayload }));
            updateRunProgress(runId, {
              currentNode: ev.node,
              leadsFound: nodePayload.count ?? 0,
            });
          }

          // Per-source candidate counts (candidates_found)
          if (eventName === "candidates_found") {
            setSourceCounts((prev) => ({
              ...prev,
              [ev.source]: (prev[ev.source] || 0) + (ev.count || 0),
            }));
          }

          // Rolling relevance progress (relevance_progress)
          if (eventName === "relevance_progress") {
            setCounts({
              accepted: ev.accepted ?? 0,
              review: ev.review ?? 0,
              rejected: ev.rejected ?? 0,
            });
          }

          // Missing concept card warning
          if (eventName === "concept_missing") {
            setConceptMissing(ev.warning || `No reviewed concept card for '${ev.keyword}'`);
          }

          // Expansion exhausted
          if (eventName === "expansion_exhausted") {
            setExpansionExhausted({
              target: ev.target,
              found: ev.found,
              review_available: ev.review_available ?? 0,
              message: ev.message,
              suggestions: ev.suggestions || [],
              rungs_tried: ev.rungs_tried || [],
            });
          }

          // Live Streaming Lead Arrivals
          if (eventName === "lead_accepted" || ev.lead) {
            const newLead: Partial<Lead> = ev.lead || {
              id: ev.lead_id || ev.business_id || `lead-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
              name: ev.name || "Identified Business Lead",
              basic_category: ev.category || "Commercial",
              phone_primary: ev.phone || null,
              tier: ev.tier || "Verified",
              confidence_score: ev.score ?? ev.confidence ?? 0.88,
              decision: "accepted",
              decision_reasons: ev.reasons || ["Passed keyword ontology filter", "Proximity match"],
            };
            setStreamedLeads((prev) => [newLead, ...prev.slice(0, 49)]);
            setCounts((prev) => ({ ...prev, accepted: prev.accepted + 1 }));
          }

          // Counts updates from summary events
          if (ev.counts) {
            setCounts({
              accepted: ev.counts.accepted ?? 0,
              review: ev.counts.review ?? 0,
              rejected: ev.counts.rejected ?? 0,
            });
          }

          // Error telemetry
          if (ev.error) {
            setErrorDetails({
              message: typeof ev.error === "string" ? ev.error : ev.error.message || "Pipeline execution error",
              node: ev.node || ev.failed_node,
            });
          }

          const evType = (eventName || ev.status || "").toLowerCase();
          if (TERMINAL_EVENTS.has(evType)) {
            setStatusSynced("closed");
            es?.close();

            let finalState: TerminalRunState = "completed";
            if (evType.includes("fail")) {
              finalState = "failed";
            } else if (evType.includes("cancel")) {
              finalState = "cancelled";
            } else if (ev.counts?.accepted === 0 || (ev.count === 0 && !evType.includes("fail"))) {
              finalState = "zero_results";
            } else if (ev.degraded && ev.degraded.length > 0) {
              finalState = "partial";
            }

            setTerminalState(finalState);
            markRunFinished(runId, finalState === "zero_results" ? "completed" : finalState === "partial" ? "completed" : finalState);

            // Client-side safety net (§3.4): Zero nodes must remain in 'running' state after a terminal event
            setNodes((prev) => {
              const updated = { ...prev };
              Object.keys(updated).forEach((nodeKey) => {
                if (updated[nodeKey].status === "running") {
                  updated[nodeKey] = {
                    ...updated[nodeKey],
                    status: (finalState === "failed" ? "failed" : "completed") as any,
                    duration_ms: updated[nodeKey].duration_ms || 10,
                  };
                }
              });
              // Ensure n12_report is marked completed if run succeeded
              if (finalState === "completed" || finalState === "partial" || finalState === "zero_results") {
                updated["n12_report"] = {
                  run_id: runId,
                  node: "n12_report",
                  status: "completed" as any,
                  duration_ms: updated["n12_report"]?.duration_ms || 10,
                };
              }
              return updated;
            });

            qc.invalidateQueries({ queryKey: qk.run(runId) });
            qc.invalidateQueries({ queryKey: qk.runs() });
            qc.invalidateQueries({ queryKey: qk.leads(runId) });
          }
        } catch (err) {
          console.error("Failed to parse SSE event payload", err);
        }
      };

      EVENT_TYPES.forEach((t) => {
        es?.addEventListener(t, handleEventMessage as EventListener);
      });
      es.onmessage = handleEventMessage;

      es.onerror = () => {
        es?.close();
        if (isCancelled) return;

        if (retryCountRef.current >= 6) {
          setStatusSynced("closed");
          return;
        }

        const delay =
          Math.min(1000 * Math.pow(2, retryCountRef.current), 30000) +
          Math.random() * 300;
        retryCountRef.current += 1;
        setStatusSynced("reconnecting");
        timerRef.current = window.setTimeout(connect, delay);
      };
    };

    connect();

    // Stall detection: fires every 15s; triggers 'stalled' if > 60s silence
    stalledCheckRef.current = window.setInterval(() => {
      if (
        statusRef.current === "open" &&
        Date.now() - lastEventTimeRef.current > 60_000
      ) {
        setStatusSynced("stalled");
      }
    }, 15_000);

    return () => {
      isCancelled = true;
      es?.close();
      if (timerRef.current) clearTimeout(timerRef.current);
      if (stalledCheckRef.current) clearInterval(stalledCheckRef.current);
    };
  }, [runId, qc, updateRunProgress, markRunFinished, setStatusSynced, setLastEventTimeSynced]);

  return {
    nodes,
    status,
    lastEventTime,
    streamedLeads,
    counts,
    terminalState,
    errorDetails,
    sourceCounts,
    expansionExhausted,
    conceptMissing,
  };
}

