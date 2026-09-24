import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useRunEvents } from "../../hooks/useRunEvents";
import { useRun } from "../../hooks/useRun";
import { useScrapeDraft } from "../../stores/useScrapeDraft";
import { NodeGraph } from "./NodeGraph";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import {
  ArrowRight,
  RefreshCw,
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  Database,
  Globe,
  MapPin,
  Copy,
  SlidersHorizontal,
} from "lucide-react";
import { api } from "../../api/client";
import { formatDuration } from "../../lib/format";
import { toast } from "sonner";
import { ReasonChip } from "../../components/ui/ReasonChip";
import { renderSafe } from "../../lib/renderSafe";
import { ChipDescriptor } from "../../types";

interface LiveRunPanelProps {
  runId: string;
  onNewRun?: () => void;
}

export const LiveRunPanel: React.FC<LiveRunPanelProps> = ({ runId, onNewRun }) => {
  const navigate = useNavigate();
  const { data: run } = useRun(runId);
  const {
    nodes,
    status,
    streamedLeads,
    counts,
    terminalState,
    errorDetails,
    sourceCounts,
    expansionExhausted,
    conceptMissing,
  } = useRunEvents(runId);

  const { setDraftFromRun } = useScrapeDraft();
  const [elapsedSec, setElapsedSec] = useState(0);
  const [cancelling, setCancelling] = useState(false);

  // Live timer tick
  useEffect(() => {
    const isFinished = terminalState !== null || run?.status === "completed" || run?.status === "failed";
    if (isFinished) return;

    const timer = setInterval(() => {
      setElapsedSec((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [terminalState, run?.status]);

  const handleCancelRun = async () => {
    setCancelling(true);
    try {
      await api.cancelRun(runId);
      toast.success("Pipeline cancellation requested");
    } catch (err: any) {
      toast.error(err.message || "Failed to cancel run");
    } finally {
      setCancelling(false);
    }
  };

  const handleEditAndRerun = () => {
    if (run) {
      // Clone run configuration into draft store
      setDraftFromRun({
        location: {
          locality: run.locality || "",
          city: run.city || "",
          state: run.state || "",
          country: run.country || "India",
        },
        keywords: run.keywords || [],
        maxResults: (run.stats as any)?.max_results || 100,
      });
      toast.info("Loaded run configuration into discovery draft");
      navigate("/scrape");
    } else {
      onNewRun ? onNewRun() : navigate("/scrape");
    }
  };

  const handleCopyTraceback = () => {
    const errorText = JSON.stringify(errorDetails || run?.error || "Unknown error", null, 2);
    navigator.clipboard.writeText(errorText);
    toast.success("Technical failure details copied to clipboard");
  };

  const isReconnecting = status === "reconnecting";
  const isStalled = status === "stalled";
  const activeTerminalState = terminalState || (run?.status === "completed" ? "completed" : run?.status === "failed" ? "failed" : null);

  // Extract source stats: prefer live SSE counts, fall back to node event counts
  const overtureCount = sourceCounts["n3a_overture"] ?? nodes["n3a_overture"]?.count ?? 0;
  const osmCount = sourceCounts["n3b_overpass"] ?? nodes["n3b_overpass"]?.count ?? 0;
  const enrichCount = nodes["n6_enrich"]?.count ?? 0;

  return (
    <div className="space-y-5 animate-in fade-in slide-in-from-bottom-3 duration-300">
      {/* ── Compact Sticky Run Header ───────────────────────────────────────── */}
      <div className="p-4 rounded-xl border border-border-subtle bg-surface-1 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-base font-bold text-text-primary tracking-tight">
              {run?.keywords?.length ? run.keywords.join(", ") : "Lead Discovery Run"}
            </h1>
            <Badge
              variant={
                activeTerminalState === "completed"
                  ? "good"
                  : activeTerminalState === "failed" || isStalled
                  ? "critical"
                  : isReconnecting
                  ? "warning"
                  : "default"
              }
              size="sm"
            >
              <Activity className="w-3 h-3" />
              {activeTerminalState ? activeTerminalState.toUpperCase() : status.toUpperCase()}
            </Badge>
          </div>

          <p className="text-xs text-text-secondary flex items-center gap-2 font-mono flex-wrap">
            <span className="flex items-center gap-1 text-text-muted">
              <MapPin className="w-3.5 h-3.5" />
              {run?.locality || "Target Area"}, {run?.city || "City"}
            </span>
            <span>·</span>
            <span className="text-text-muted">ID: {runId.slice(0, 8)}</span>
            <span>·</span>
            <span className="flex items-center gap-1 text-text-muted">
              <Clock className="w-3.5 h-3.5" />
              {formatDuration(elapsedSec * 1000)}
            </span>
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={handleEditAndRerun}
            className="gap-1.5 text-xs"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            Edit & Re-Run
          </Button>

          {!activeTerminalState && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleCancelRun}
              disabled={cancelling}
              className="text-xs text-rose-500 hover:text-rose-600 hover:border-rose-500/40"
            >
              Cancel Run
            </Button>
          )}

          <Link to={`/runs/${runId}`}>
            <Button variant="primary" size="sm" className="gap-1.5 text-xs shadow-sm">
              Open Run Workspace <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </Link>
        </div>
      </div>

      {/* ── Status Alerts (Reconnecting, Stalled, Degraded) ────────────────── */}
      {isReconnecting && (
        <div className="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-600 dark:text-amber-400 flex items-center gap-2.5 shadow-xs">
          <RefreshCw className="w-4 h-4 animate-spin shrink-0" />
          <div>
            <span className="font-semibold">Reconnecting to pipeline stream:</span> Retrying SSE connection with exponential backoff.
          </div>
        </div>
      )}

      {isStalled && !activeTerminalState && (
        <div className="p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-600 dark:text-rose-400 flex items-center gap-2.5 shadow-xs">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <div>
            <span className="font-semibold">Pipeline Heartbeat Stalled (&gt;60s):</span> The backend worker may still be computing long-running LLM or crawl tasks.
          </div>
        </div>
      )}

      {/* ── Concept Missing Warning ────────────────────────────────────────── */}
      {conceptMissing && (
        <div className="p-3.5 bg-amber-400/10 border border-amber-400/30 rounded-xl text-xs text-amber-700 dark:text-amber-300 flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Concept Card Missing:</span>{" "}
            {conceptMissing}
          </div>
        </div>
      )}

      {/* ── Region 1: Hero DAG Pipeline Graph ───────────────────────────────── */}
      <NodeGraph nodes={nodes} />

      {/* ── Terminal State Screens ─────────────────────────────────────────── */}
      {activeTerminalState === "completed" && (
        <div className="p-6 rounded-xl border border-emerald-500/30 bg-emerald-500/5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-full bg-emerald-500/20 text-emerald-500 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-text-primary">Pipeline Execution Completed</h3>
                <p className="text-xs text-text-secondary mt-0.5">
                  Extracted, deduplicated, and scored golden lead records.
                </p>
              </div>
            </div>
            <Link to={`/runs/${runId}`}>
              <Button variant="primary" size="sm" className="gap-1.5 shadow-md">
                View All Leads <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </Link>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-2">
            <div className="p-3 rounded-lg bg-surface-1 border border-border-subtle text-center">
              <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
                {counts.accepted || (run?.stats as any)?.leads_accepted || 0}
              </div>
              <div className="text-[11px] text-text-muted mt-0.5 font-medium">Accepted Leads</div>
            </div>
            <div className="p-3 rounded-lg bg-surface-1 border border-border-subtle text-center">
              <div className="text-xl font-bold text-amber-500">
                {counts.review || (run?.stats as any)?.leads_review || 0}
              </div>
              <div className="text-[11px] text-text-muted mt-0.5 font-medium">Review Queue</div>
            </div>
            <div className="p-3 rounded-lg bg-surface-1 border border-border-subtle text-center">
              <div className="text-xl font-bold text-text-muted">
                {counts.rejected || (run?.stats as any)?.leads_rejected || 0}
              </div>
              <div className="text-[11px] text-text-muted mt-0.5 font-medium">Vetoed / Rejected</div>
            </div>
          </div>
        </div>
      )}

      {activeTerminalState === "zero_results" && (
        <div className="p-6 rounded-xl border border-amber-500/30 bg-amber-500/5 shadow-sm space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-full bg-amber-500/20 text-amber-500 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-text-primary">No Matching Leads Ingested (0 Results)</h3>
              <p className="text-xs text-text-secondary mt-0.5">
                Upstream sources returned raw candidates, but none passed strict relevance gates.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={handleEditAndRerun}>
              Widen Area & Edit Concept
            </Button>
            <Link to={`/runs/${runId}`}>
              <Button variant="ghost" size="sm">
                View Rejected Diagnoses
              </Button>
            </Link>
          </div>
        </div>
      )}

      {activeTerminalState === "failed" && (
        <div className="p-6 rounded-xl border border-rose-500/30 bg-rose-500/5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-full bg-rose-500/20 text-rose-500 flex items-center justify-center">
                <XCircle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-text-primary">Pipeline Execution Failed</h3>
                <p className="text-xs text-rose-600 dark:text-rose-400 mt-0.5 font-mono">
                  {errorDetails?.message || run?.error || "Unknown graph execution failure"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleCopyTraceback} className="gap-1 text-xs">
                <Copy className="w-3.5 h-3.5" /> Copy Details
              </Button>
              <Button variant="primary" size="sm" onClick={handleEditAndRerun} className="text-xs">
                Retry Run
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Region 2: Source Ticker ─────────────────────────────────────────── */}
      <div className="p-4 rounded-xl border border-border-subtle bg-surface-1 shadow-sm space-y-3">
        <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-accent" />
            Active Source Connectors &amp; Freshness
          </span>
          <span className="text-[11px] font-mono text-text-muted">
            {Object.values(sourceCounts).reduce((a, b) => a + b, 0)} raw candidates ingested
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Overture Places */}
          <div data-testid="source-ticker-overture" className="p-3 rounded-lg border border-border-subtle bg-surface-2/40 text-xs space-y-1">
            <div className="flex items-center justify-between font-semibold">
              <span className="flex items-center gap-1.5 text-text-primary">
                <Database className="w-3.5 h-3.5 text-blue-500" /> Overture Places
              </span>
              <span className={`text-[11px] font-mono ${overtureCount > 0 ? "text-emerald-500" : "text-text-muted"}`}>
                {overtureCount > 0 ? `${overtureCount} found (cache/live)` : "Ingesting (cache/live)…"}
              </span>
            </div>
            <p className="text-[11px] text-text-secondary">
              Category-first · Parquet spatial extraction · CDLA-2.0 · cache / live
            </p>
          </div>

          {/* OpenStreetMap */}
          <div className="p-3 rounded-lg border border-border-subtle bg-surface-2/40 text-xs space-y-1">
            <div className="flex items-center justify-between font-semibold">
              <span className="flex items-center gap-1.5 text-text-primary">
                <Globe className="w-3.5 h-3.5 text-emerald-500" /> OpenStreetMap Overpass
              </span>
              <span className={`text-[11px] font-mono ${osmCount > 0 ? "text-emerald-500" : "text-text-muted"}`}>
                {osmCount > 0 ? `${osmCount} found` : "Live Query"}
              </span>
            </div>
            <p className="text-[11px] text-text-secondary">
              Live polygon boundary query · ODbL 1.0
            </p>
          </div>

          {/* Website Enrichment */}
          <div className="p-3 rounded-lg border border-border-subtle bg-surface-2/40 text-xs space-y-1">
            <div className="flex items-center justify-between font-semibold">
              <span className="flex items-center gap-1.5 text-text-primary">
                <Globe className="w-3.5 h-3.5 text-purple-500" /> Web Grounding
              </span>
              <span className="text-[11px] font-mono text-text-muted">
                {enrichCount > 0 ? `${enrichCount} enriched` : "Robots compliant"}
              </span>
            </div>
            <p className="text-[11px] text-text-secondary">
              Deterministic JSON-LD &amp; contact crawler
            </p>
          </div>
        </div>
      </div>

      {/* ── Region 3: Real-Time Lead Stream Influx ──────────────────────────── */}
      <div className="p-4 rounded-xl border border-border-subtle bg-surface-1 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-accent" />
            Live Lead Stream Influx
          </div>
          {/* Rolling accept/review/reject counter */}
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              {counts.accepted} accepted
            </span>
            <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400">
              {counts.review} review
            </span>
            <span className="px-2 py-0.5 rounded-full bg-surface-2 text-text-muted">
              {counts.rejected} rejected
            </span>
          </div>
        </div>

        {/* ── Expansion Exhausted Banner ───────────────────────────────── */}
        {expansionExhausted && (
          <div className="p-3 rounded-lg border border-amber-400/30 bg-amber-400/5 text-xs space-y-2">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-text-primary">
                  {expansionExhausted.found}/{expansionExhausted.target} leads found — search exhausted
                </p>
                <p className="text-text-secondary mt-0.5">{expansionExhausted.message}</p>
              </div>
            </div>
            {expansionExhausted.suggestions.length > 0 && (
              <ul className="ml-6 space-y-0.5 text-text-secondary">
                {expansionExhausted.suggestions.map((s, i) => (
                  <li key={i} className="flex items-center gap-1">
                    <span className="text-accent">›</span> {s}
                  </li>
                ))}
              </ul>
            )}
            {expansionExhausted.review_available > 0 && (
              <Link to={`/runs/${runId}`} className="block">
                <Button variant="outline" size="sm" className="gap-1 text-[11px]">
                  Review {expansionExhausted.review_available} borderline matches
                </Button>
              </Link>
            )}
          </div>
        )}

        {streamedLeads.length === 0 ? (
          <div className="py-10 text-center rounded-lg border border-dashed border-border-strong bg-surface-2/30 text-text-muted text-xs flex flex-col items-center justify-center gap-1.5">
            <Sparkles className="w-5 h-5 text-accent animate-spin" />
            <span>Awaiting initial accepted leads from classification cascade...</span>
          </div>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {streamedLeads.map((lead) => (
              <div
                key={lead.id}
                data-testid="live-lead-item"
                className="p-3 rounded-lg border border-border-subtle bg-surface-2/50 hover:bg-surface-2 flex items-center justify-between gap-3 text-xs transition-colors animate-in fade-in slide-in-from-top-2 duration-150"
              >
                <div className="space-y-0.5 truncate">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-text-primary truncate">
                      {lead.name || lead.canonical_name || "Lead"}
                    </span>
                    <Badge variant={lead.tier === "Verified" ? "good" : "warning"} size="sm">
                      {lead.tier || "Unverified"}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-text-muted truncate">
                    {lead.basic_category || lead.primary_category || "Commercial"}{" "}
                    {(lead.phone_primary || (lead as any).phones_e164?.[0]) ? `· ${lead.phone_primary || (lead as any).phones_e164?.[0]}` : ""}
                  </p>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {((lead.decision_reasons || []) as Array<string | ChipDescriptor>).slice(0, 2).map((reason, rIdx) => {
                    if (typeof reason === "object" && reason !== null) {
                      return (
                        <ReasonChip
                          key={rIdx}
                          type={reason.type || "positive"}
                          label={reason.label || reason.detail || reason.feature || "signal"}
                          icon={reason.icon}
                          weight={reason.weight}
                          className="max-w-[150px] truncate text-[10px]"
                        />
                      );
                    }
                    return (
                      <ReasonChip
                        key={rIdx}
                        type="positive"
                        label={renderSafe(reason, "LiveRunPanel.reason")}
                        className="max-w-[150px] truncate text-[10px]"
                      />
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};


