import React, { useState } from "react";
import { Link } from "react-router-dom";
import { RunSummary } from "../../types";
import { Badge } from "../../components/ui/Badge";
import { formatDate } from "../../lib/format";
import { ArrowRight, MapPin, Tag, Clock, Layers, AlertCircle, ChevronDown, ChevronUp, RotateCw, Copy, Check } from "lucide-react";
import { api } from "../../api/client";

function translateError(errorStr?: string, failedNode?: string, errorCode?: string): { message: string; action: string } {
  if (
    errorCode === "corrupt_run_row" ||
    errorCode === "not_retryable" ||
    (errorStr && (errorStr.includes("corrupt_run_row") || errorStr.includes("NoneType") || errorStr.includes("raw_input: None")))
  ) {
    return {
      message: "This run was created before input validation existed and cannot be re-run.",
      action: "Start new search",
    };
  }
  if (errorCode === "schema_error" || (errorStr && (errorStr.includes("undefinedcolumn") || errorStr.includes("schema")))) {
    return {
      message: "Database schema is out of date. Required columns or migrations are missing.",
      action: "Run 'uv run alembic upgrade head' and restart backend",
    };
  }
  if (errorCode === "queue_timeout" || (errorStr && errorStr.includes("queue_timeout"))) {
    return {
      message: "Run remained in the queue for too long without being claimed by a worker.",
      action: "Check worker health and retry",
    };
  }
  if (errorCode === "unclaimable") {
    return {
      message: "Run could not be claimed or executed due to repeated worker lease collisions.",
      action: "Retry run",
    };
  }
  if (!errorStr) {
    return {
      message: "The run was stopped unexpectedly.",
      action: "Retry run",
    };
  }
  const err = errorStr.toLowerCase();
  if (err.includes("no_sources") || err.includes("failed_no_sources")) {
    return {
      message: "Both Overture and OpenStreetMap sources were unreachable, so there was nothing to search.",
      action: "Check network / retry",
    };
  }
  if (err.includes("overture") || err.includes("s3") || err.includes("httpfs")) {
    return {
      message: "Couldn't reach the Overture dataset. S3 connection may have timed out.",
      action: "Retry with cached data",
    };
  }
  if (err.includes("overpass") || err.includes("429") || err.includes("504")) {
    return {
      message: "OpenStreetMap was rate-limited or busy at the time of query.",
      action: "Retry in a few moments",
    };
  }
  if (err.includes("timeout") || err.includes("timed out")) {
    return {
      message: `Node '${failedNode || "pipeline"}' took longer than allocated timeout.`,
      action: "Retry with fewer keywords",
    };
  }
  if (err.includes("geo") || err.includes("polygon") || err.includes("nominatim")) {
    return {
      message: "Could not resolve boundary geometry for target area.",
      action: "Select an explicit city/locality",
    };
  }
  if (errorStr.includes("Traceback") || errorStr.includes("File '") || errorStr.includes('File "')) {
    const lines = errorStr.trim().split("\n").filter(Boolean);
    const lastLine = lines[lines.length - 1] || "Unexpected pipeline failure";
    const cleaned = lastLine.replace(/^([A-Za-z_]+Error:\s*)/, "");
    return {
      message: cleaned || "An unexpected error occurred during pipeline execution.",
      action: "Retry run",
    };
  }
  return {
    message: errorStr.length > 120 ? `${errorStr.slice(0, 120)}...` : errorStr,
    action: "Copy technical details",
  };
}

export const RunCard: React.FC<{ run: RunSummary }> = ({ run }) => {
  const [showErrorDetails, setShowErrorDetails] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  const isCompleted = run.status === "completed";
  const isPartial = run.status === "partial";
  const isQueued = run.status === "queued";
  const isRunning = run.status === "running" || isQueued;
  const isFailed = run.status === "failed" || run.status === "failed_no_sources";
  const isRetryable = run.retryable !== false && run.error_code !== "corrupt_run_row";

  const queuedDurationSec = isQueued && run.created_at
    ? Math.max(0, Math.floor((Date.now() - new Date(run.created_at).getTime()) / 1000))
    : 0;

  const totalLeads = run.stats?.resolved_entity_count || run.stats?.candidate_count || 0;
  const resolvedTitle =
    run.geo_display_name ||
    run.locality ||
    run.city ||
    (run.keywords.length > 0 ? `${run.keywords.join(", ")} Search` : "Untitled Run");

  const errorInfo = isFailed ? translateError(run.error, run.failed_node, run.error_code) : null;

  const handleCopy = () => {
    navigator.clipboard.writeText(
      JSON.stringify({ run_id: run.id, error: run.error, error_code: run.error_code, failed_node: run.failed_node, status: run.status }, null, 2)
    );
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRetry = async () => {
    if (!isRetryable) return;
    try {
      setIsRetrying(true);
      await api.rerun(run.id);
      window.location.reload();
    } catch (e) {
      console.error("Retry failed:", e);
    } finally {
      setIsRetrying(false);
    }
  };

  const prefillParams = new URLSearchParams();
  if (run.locality) prefillParams.set("locality", run.locality);
  if (run.city) prefillParams.set("city", run.city);
  if (run.keywords && run.keywords.length > 0) prefillParams.set("keywords", run.keywords.join(","));

  return (
    <div className="p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm hover:border-border-strong transition-all flex flex-col justify-between group">
      <div>
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="space-y-0.5 min-w-0">
            <h3 className="font-bold text-sm text-text-primary group-hover:text-accent transition-colors flex items-center gap-1.5 truncate">
              <MapPin className="w-3.5 h-3.5 text-accent shrink-0" />
              <span className="truncate">
                {resolvedTitle}
                {run.city && !resolvedTitle.includes(run.city) ? `, ${run.city}` : ""}
              </span>
            </h3>
            <div className="flex items-center gap-1.5 text-xs text-text-muted">
              <Tag className="w-3 h-3 shrink-0" />
              <span className="truncate">{run.keywords.join(", ") || "All businesses"}</span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {run.completion_reason === "region_exhausted" && (
              <span
                data-testid="exhaustion-badge"
                className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20"
              >
                exhausted
              </span>
            )}
            <Badge
              variant={
                isCompleted
                  ? "good"
                  : isPartial
                  ? "good"
                  : isQueued && queuedDurationSec > 120
                  ? "critical"
                  : isRunning
                  ? "warning"
                  : isFailed
                  ? "critical"
                  : "default"
              }
              size="sm"
              className="font-mono text-[10px]"
            >
              {isQueued && queuedDurationSec >= 60
                ? `QUEUED (${Math.floor(queuedDurationSec / 60)}m)`
                : run.status.toUpperCase()}
            </Badge>
          </div>
        </div>

        {/* Long Queued Notice */}
        {isQueued && queuedDurationSec > 60 && (
          <div className="mt-1.5 p-2 rounded bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-300 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 shrink-0 text-amber-400" />
            <span>Queued for {Math.floor(queuedDurationSec / 60)}m — waiting for free worker slot</span>
          </div>
        )}

        {/* Failed Explanation Banner (§3.1) */}
        {isFailed && errorInfo && (
          <div className="mt-2.5 p-2.5 rounded-md bg-red-950/20 border border-red-800/40 text-xs text-red-300 space-y-1.5">
            <div className="flex items-start gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
              <p className="leading-snug">{errorInfo.message}</p>
            </div>
            <div className="flex items-center justify-between pt-1 border-t border-red-900/30">
              <button
                type="button"
                onClick={() => setShowErrorDetails(!showErrorDetails)}
                className="text-[11px] text-red-400 hover:text-red-200 flex items-center gap-0.5 font-medium"
              >
                Why did this fail? {showErrorDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>

              {isRetryable ? (
                <button
                  type="button"
                  data-testid="retry-button"
                  onClick={handleRetry}
                  disabled={isRetrying}
                  className="text-[11px] px-2 py-0.5 rounded bg-red-900/40 hover:bg-red-900/60 text-red-200 border border-red-700/50 flex items-center gap-1 font-semibold"
                >
                  <RotateCw className={`w-2.5 h-2.5 ${isRetrying ? "animate-spin" : ""}`} />
                  {run.attempt_count && run.attempt_count > 0 ? `Retry (attempt ${run.attempt_count + 1})` : "Retry"}
                </button>
              ) : (
                <span
                  data-testid="cannot-rerun-badge"
                  className="text-[11px] px-2 py-0.5 rounded bg-surface-2 text-text-muted border border-border-subtle font-mono"
                >
                  Can't re-run
                </span>
              )}
            </div>

            {showErrorDetails && (
              <div className="pt-2 text-[10px] font-mono text-text-muted bg-surface-2/60 p-2 rounded border border-border-subtle space-y-1">
                {run.failed_node && <div>Failed Node: <span className="text-text-primary">{run.failed_node}</span></div>}
                <div className="break-all">{run.error || "No explicit stack trace recorded."}</div>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="mt-1 text-accent flex items-center gap-1 hover:underline"
                >
                  {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />} {copied ? "Copied" : "Copy technical details"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Boundary and Date */}
        <div className="flex items-center justify-between text-[11px] text-text-muted font-mono my-3 pt-2 border-t border-border-subtle">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" /> {formatDate(run.created_at)}
          </span>
          <span className="flex items-center gap-1">
            <Layers className="w-3 h-3" /> {run.boundary_kind || "admin_polygon"}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-border-subtle">
        <div className="font-mono text-xs">
          <span className="font-bold text-text-primary text-sm">{totalLeads}</span>
          <span className="text-text-muted"> leads</span>
        </div>

        <Link
          to={`/runs/${run.id}`}
          className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline"
        >
          Workspace <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
};
