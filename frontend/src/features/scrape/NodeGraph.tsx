import React from "react";
import { NodeEvent } from "../../types";
import { CheckCircle2, Clock, AlertCircle, Loader2, Sparkles, RefreshCw } from "lucide-react";
import { formatDuration } from "../../lib/format";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { qk } from "../../lib/queryKeys";

interface NodeGraphProps {
  nodes: Record<string, NodeEvent>;
  onRetryNode?: (nodeId: string) => void;
}

export type NodeState = "pending" | "running" | "done" | "failed" | "skipped";

// Nodes that are part of the iterative refinement cycle N6 -> N7 -> N8 -> N9 -> N6
const CYCLE_NODES = new Set(["n6_enrich", "n7_verify", "n8_score", "n9_critic"]);
const CYCLE_ORDER = ["n6_enrich", "n7_verify", "n8_score", "n9_critic"];

export function deriveNodeState(
  ev?: NodeEvent,
  isActiveRunning?: boolean,
  highestActiveCycleIteration?: number,
  activeCycleNodeIndex?: number,
  thisCycleIndex?: number
): NodeState {
  if (!ev) return "pending";
  if (ev.status === "failed") return "failed";
  if (ev.status === "skipped") return "skipped";

  // If a node upstream in the cycle is running in a higher iteration pass,
  // downstream nodes from prior iteration should not show current "done"
  if (
    highestActiveCycleIteration !== undefined &&
    highestActiveCycleIteration > 0 &&
    thisCycleIndex !== undefined &&
    activeCycleNodeIndex !== undefined
  ) {
    const nodeIter = ev.iteration ?? 0;
    if (nodeIter < highestActiveCycleIteration) {
      if (thisCycleIndex > activeCycleNodeIndex) {
        return "pending";
      }
    }
  }

  if (
    ev.status === "completed" ||
    (ev.status as string) === "done" ||
    (ev.duration_ms !== undefined && ev.duration_ms > 0) ||
    ((ev as any).elapsed_ms !== undefined && (ev as any).elapsed_ms > 0)
  ) {
    return "done";
  }
  if (ev.status === "running" || isActiveRunning) {
    return "running";
  }
  return "pending";
}

export function getNodeStatusText(state: NodeState, evOrCount?: NodeEvent | number): string {
  const ev = typeof evOrCount === "object" ? evOrCount : undefined;
  const count = typeof evOrCount === "number" ? evOrCount : ev?.count;
  if (ev?.progress && ev.progress.total > 0) {
    return `${ev.progress.done} / ${ev.progress.total} domains`;
  }
  switch (state) {
    case "done":
      return count !== undefined ? `${count} items` : "Done";
    case "running":
      return count !== undefined ? `${count} items...` : "Processing...";
    case "failed":
      return "Failed";
    case "skipped":
      return "Skipped";
    case "pending":
    default:
      return "Pending";
  }
}

export const NodeGraph: React.FC<NodeGraphProps> = React.memo(({ nodes, onRetryNode }) => {
  const { data: pipelineNodes = [], isLoading } = useQuery({
    queryKey: qk.configGraph,
    queryFn: () => api.getConfigGraph(),
    staleTime: 600_000,
  });

  // Identify currently active running node (only one animated at a time)
  const activeRunningNode = pipelineNodes.find(
    (n) => nodes[n.id]?.status === "running"
  );
  const activeRunningNodeId = activeRunningNode?.id;

  // Track highest iteration in active cycle
  let highestActiveCycleIteration = 0;
  let activeCycleNodeIndex = -1;

  if (activeRunningNodeId && CYCLE_NODES.has(activeRunningNodeId)) {
    activeCycleNodeIndex = CYCLE_ORDER.indexOf(activeRunningNodeId);
    highestActiveCycleIteration = nodes[activeRunningNodeId]?.iteration ?? 0;
  }

  return (
    <div className="p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm space-y-3">
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-accent" />
          Pipeline Execution DAG
        </span>
        {isLoading && <span className="text-[10px] text-text-muted">Loading graph schema...</span>}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
        {pipelineNodes.map((nodeDef, idx) => {
          const ev = nodes[nodeDef.id];
          const isActive = nodeDef.id === activeRunningNodeId;
          const isCycleNode = CYCLE_NODES.has(nodeDef.id);
          const cycleIdx = isCycleNode ? CYCLE_ORDER.indexOf(nodeDef.id) : undefined;

          const state = deriveNodeState(
            ev,
            isActive,
            highestActiveCycleIteration,
            activeCycleNodeIndex,
            cycleIdx
          );

          const isDone = state === "done";
          const isRunning = state === "running";
          const isFailed = state === "failed";
          const isPending = state === "pending";
          const statusText = getNodeStatusText(state, ev);
          const iteration = ev?.iteration ?? 0;

          return (
            <div
              key={nodeDef.id}
              data-testid={`node-${nodeDef.id}`}
              data-state={state}
              className={`p-3 rounded-lg border text-xs flex flex-col justify-between transition-all duration-200 relative group ${
                isDone
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                  : isRunning
                  ? "bg-accent/10 border-accent text-accent font-semibold shadow-sm ring-2 ring-accent/20 animate-pulse"
                  : isFailed
                  ? "bg-rose-500/10 border-rose-500/40 text-rose-600 dark:text-rose-400"
                  : "bg-surface-2/40 border-border-subtle text-text-muted"
              }`}
            >
              {/* Header with Step # and Status Icon */}
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5 font-mono truncate">
                  <span className="text-[10px] opacity-60 font-normal">0{idx + 1}</span>
                  <span className="font-semibold truncate">{nodeDef.label.replace(/^N\d+[a-z]?\s*/, "")}</span>
                </div>

                {isDone && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
                {isRunning && <Loader2 className="w-4 h-4 text-accent animate-spin shrink-0" />}
                {isFailed && <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />}
                {isPending && <Clock className="w-3.5 h-3.5 opacity-30 shrink-0" />}
              </div>

              {/* Description */}
              <p className="text-[10px] text-text-secondary line-clamp-2 mb-2 leading-tight">
                {nodeDef.description}
              </p>

              {/* Iteration Pass Badge if in refinement loop */}
              {isCycleNode && iteration > 0 && (
                <div className="mb-1.5 flex items-center gap-1 text-[9px] font-mono text-accent bg-accent/10 px-1.5 py-0.5 rounded w-fit">
                  <RefreshCw className="w-2.5 h-2.5" />
                  <span>pass {iteration + 1}</span>
                </div>
              )}

              {/* Metric Footer */}
              <div className="pt-2 border-t border-current/10 flex items-center justify-between text-[10px] font-mono">
                <span className="truncate max-w-[110px]" title={statusText}>{statusText}</span>
                <span>{ev?.duration_ms ? formatDuration(ev.duration_ms) : ""}</span>
              </div>

              {/* Retry button if failed */}
              {isFailed && onRetryNode && (
                <button
                  type="button"
                  onClick={() => onRetryNode(nodeDef.id)}
                  className="mt-2 w-full py-1 rounded bg-rose-500 text-white font-medium text-[10px] hover:bg-rose-600 transition-colors"
                >
                  Retry Node
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
});
NodeGraph.displayName = "NodeGraph";
