import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useRuns } from "../../hooks/useRuns";
import { RunCard } from "./RunCard";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { EmptyState, ErrorState, Skeleton } from "../../components/ui/EmptyState";
import { Search, Plus, Database, Filter, AlertTriangle, Copy, Check, RotateCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { qk } from "../../lib/queryKeys";

export const RunsPage: React.FC = () => {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [copiedCmd, setCopiedCmd] = useState(false);

  const { data: runs, isLoading, isError, error, refetch } = useRuns();
  const { data: health, refetch: refetchHealth } = useQuery({
    queryKey: qk.health,
    queryFn: () => api.getHealth(),
    refetchInterval: 10000,
  });

  const isQueueStalled =
    health?.queue?.worker?.state === "fatal" ||
    (Boolean(health?.queue?.depth?.queued && health.queue.depth.queued > 0) &&
      Boolean(health?.queue?.depth?.oldest_queued_age_s && health.queue.depth.oldest_queued_age_s > 120) &&
      health?.queue?.worker?.state !== "healthy");

  const handleCopyCommand = () => {
    navigator.clipboard.writeText("uv run alembic upgrade head");
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  const filteredRuns = (runs || []).filter((run) => {
    const matchSearch =
      !search ||
      run.locality?.toLowerCase().includes(search.toLowerCase()) ||
      run.city?.toLowerCase().includes(search.toLowerCase()) ||
      run.keywords.some((k) => k.toLowerCase().includes(search.toLowerCase()));

    const matchStatus = statusFilter === "all" || run.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Stalled Queue Banner */}
      {isQueueStalled && (
        <div className="p-4 rounded-xl border border-rose-500/40 bg-rose-500/10 text-rose-300 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-md">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-rose-200 text-sm">Runs are not being processed</p>
              <p className="text-rose-300/90 mt-0.5">
                {health?.queue?.worker?.last_error
                  ? `Worker error: ${health.queue.worker.last_error}. `
                  : "The background queue worker is unavailable or stalled. "}
                Run <code className="bg-surface-2 px-1.5 py-0.5 rounded text-text-primary font-mono">uv run alembic upgrade head</code> and restart the backend.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
            <button
              onClick={handleCopyCommand}
              className="px-2.5 py-1 rounded bg-surface-2 hover:bg-surface-3 text-text-primary border border-border-subtle flex items-center gap-1.5 text-xs font-mono cursor-pointer transition-colors"
            >
              {copiedCmd ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedCmd ? "Copied" : "Copy command"}
            </button>
            <button
              onClick={() => { refetch(); refetchHealth(); }}
              className="px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white flex items-center gap-1 text-xs font-semibold cursor-pointer transition-colors"
            >
              <RotateCw className="w-3.5 h-3.5" /> Retry
            </button>
          </div>
        </div>
      )}

      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary">
            Execution Runs & Datasets
          </h1>
          <p className="text-xs text-text-muted mt-0.5">
            Review historical discovery runs, inspect lead triage, and export verified leads.
          </p>
        </div>

        <Link to="/scrape">
          <Button variant="primary" size="sm" className="gap-1.5 shadow-sm">
            <Plus className="w-4 h-4" /> New Discovery Search
          </Button>
        </Link>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="w-full sm:w-80">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search runs by keyword, locality..."
            icon={<Search className="w-4 h-4" />}
          />
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto text-xs">
          <span className="text-text-muted flex items-center gap-1 font-medium">
            <Filter className="w-3.5 h-3.5" /> Status:
          </span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-surface-1 border border-border-strong text-text-primary rounded-md px-2.5 py-1 text-xs"
          >
            <option value="all">All Statuses</option>
            <option value="completed">Completed</option>
            <option value="running">Running</option>
            <option value="failed">Failed</option>
          </select>

          <button
            onClick={async () => {
              try {
                await api.clearFailedRuns();
                refetch();
              } catch (e) {
                console.error("Failed to clear corrupt runs:", e);
              }
            }}
            className="px-2.5 py-1 rounded bg-surface-2 hover:bg-surface-3 text-text-muted hover:text-text-primary border border-border-subtle text-xs transition-colors cursor-pointer"
            title="Remove corrupt/unretryable failed runs"
          >
            Clear failed
          </button>
        </div>
      </div>

      {/* Grid or States */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-44 rounded-lg" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState error={error as Error} onRetry={() => refetch()} />
      ) : filteredRuns.length === 0 ? (
        <EmptyState
          title="No discovery runs found"
          description={
            search || statusFilter !== "all"
              ? "No runs matched your current filter criteria."
              : "Launch your first discovery pipeline run to start generating leads."
          }
          actionLabel="Launch Search"
          onAction={() => (window.location.href = "/scrape")}
          icon={<Database className="w-6 h-6" />}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredRuns.map((run) => (
            <RunCard key={run.id} run={run} />
          ))}
        </div>
      )}
    </div>
  );
};
