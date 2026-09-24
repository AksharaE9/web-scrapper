import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, X } from "lucide-react";
import { useRunTracker } from "../../stores/useRunTracker";

export const RunStatusBar: React.FC = () => {
  const activeRuns = useRunTracker((s) => s.activeRuns);
  const clearRun = useRunTracker((s) => s.clearRun);

  const runsList = Object.values(activeRuns).filter(
    (r) => r.status === "running" || r.status === "queued"
  );

  if (runsList.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-40 max-w-md w-full space-y-2">
      {runsList.map((run) => (
        <div
          key={run.runId}
          className="p-3 bg-surface-1 border border-accent/40 rounded-lg shadow-xl backdrop-blur-md flex items-center justify-between gap-3 text-xs"
        >
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-2 h-2 rounded-full bg-accent animate-ping shrink-0" />
            <div className="truncate">
              <div className="font-semibold text-text-primary truncate">
                {run.query} · {run.locality}
              </div>
              <div className="text-[11px] text-text-muted flex items-center gap-2 font-mono">
                <span>Node: {run.currentNode || "initializing"}</span>
                {run.leadsFound > 0 && <span>· {run.leadsFound} leads</span>}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <Link
              to={`/runs/${run.runId}`}
              className="px-2.5 py-1 bg-accent/10 hover:bg-accent/20 text-accent font-medium rounded flex items-center gap-1 transition-colors"
            >
              View <ArrowRight className="w-3 h-3" />
            </Link>
            <button
              onClick={() => clearRun(run.runId)}
              className="p-1 hover:bg-surface-2 text-text-muted hover:text-text-primary rounded cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};
