import React from "react";
import { CheckCircle2, Loader2, AlertCircle, Clock } from "lucide-react";
import { NodeEvent } from "../../types";

interface RunGraphViewProps {
  nodeEvents: Record<string, NodeEvent>;
  activeNode?: string;
}

interface NodeDefinition {
  id: string;
  name: string;
  label: string;
  category: "input" | "planning" | "sources" | "resolution" | "enrichment" | "persistence";
}

const GRAPH_NODES: NodeDefinition[] = [
  { id: "n0_input", name: "N0 Input", label: "Input Normalizer", category: "input" },
  { id: "n1_geo", name: "N1 Geo", label: "Geo Boundary Resolver", category: "planning" },
  { id: "n2_keyword", name: "N2 Keyword", label: "Taxonomy & Synonyms", category: "planning" },
  { id: "n3a_overture", name: "N3a Overture", label: "Overture Places S3", category: "sources" },
  { id: "n3b_overpass", name: "N3b Overpass", label: "OSM Overpass API", category: "sources" },
  { id: "n4_filter", name: "N4 Filter", label: "Spatial & Name Filter", category: "resolution" },
  { id: "n5_resolve", name: "N5 Resolver", label: "Probabilistic ER (Splink)", category: "resolution" },
  { id: "n6_enrich", name: "N6 Enrich", label: "Website Scraper & RAG", category: "enrichment" },
  { id: "n7_verify", name: "N7 Verify", label: "Multi-Source Verification", category: "enrichment" },
  { id: "n8_score", name: "N8 Scorer", label: "Calibrated Confidence", category: "enrichment" },
  { id: "n9_critic", name: "N9 Critic", label: "Quality Threshold Gate", category: "enrichment" },
  { id: "n10_persist", name: "N10 Persist", label: "Global Dedup & Staging", category: "persistence" },
  { id: "n11_eval", name: "N11 Eval", label: "Capture-Recapture N̂", category: "persistence" },
  { id: "n12_report", name: "N12 Report", label: "Run Finalization", category: "persistence" },
];

export const RunGraphView: React.FC<RunGraphViewProps> = ({ nodeEvents, activeNode }) => {
  const getNodeStatus = (id: string) => {
    const ev = nodeEvents[id];
    if (ev) return ev.status;
    if (activeNode === id) return "running";
    return "queued";
  };

  const getStatusBadge = (id: string) => {
    const status = getNodeStatus(id);
    const ev = nodeEvents[id];

    if (status === "running") {
      return (
        <span className="flex items-center gap-1 text-[11px] font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/30">
          <Loader2 className="w-3 h-3 animate-spin" /> Running
        </span>
      );
    }
    if (status === "completed") {
      return (
        <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/30">
          <CheckCircle2 className="w-3 h-3" /> {ev?.duration_ms ? `${ev.duration_ms}ms` : "Done"}
        </span>
      );
    }
    if (status === "failed") {
      return (
        <span className="flex items-center gap-1 text-[11px] font-mono text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/30">
          <AlertCircle className="w-3 h-3" /> Error
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-[11px] font-mono text-slate-500 bg-slate-800/40 px-2 py-0.5 rounded-full">
        <Clock className="w-3 h-3" /> Queued
      </span>
    );
  };

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-heading font-semibold text-slate-200">
            Multi-Agent Pipeline Graph
          </h3>
          <p className="text-xs text-slate-400">
            LangGraph StateGraph Execution Topology (Parallel Fan-Out & Checkpointed)
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {GRAPH_NODES.map((node) => {
          const status = getNodeStatus(node.id);
          const ev = nodeEvents[node.id];
          const isRunning = status === "running";
          const isDone = status === "completed";
          const isFailed = status === "failed";

          return (
            <div
              key={node.id}
              className={`p-3.5 rounded-xl border transition-all duration-200 relative overflow-hidden ${
                isRunning
                  ? "bg-indigo-950/40 border-indigo-500/50 shadow-lg shadow-indigo-500/10 ring-1 ring-indigo-500/40"
                  : isDone
                  ? "bg-slate-900/80 border-slate-800 hover:border-slate-700"
                  : isFailed
                  ? "bg-rose-950/20 border-rose-800/60"
                  : "bg-slate-950/40 border-slate-850 opacity-60"
              }`}
            >
              {isRunning && (
                <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-indigo-500 to-cyan-400 animate-shimmer" />
              )}
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-mono font-semibold text-slate-400">
                  {node.name}
                </span>
                {getStatusBadge(node.id)}
              </div>
              <div className="font-heading font-medium text-xs text-slate-200 truncate">
                {node.label}
              </div>
              {ev?.count !== undefined && (
                <div className="mt-2 text-[11px] text-slate-400 font-mono">
                  Items: <span className="text-indigo-300 font-semibold">{ev.count}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
