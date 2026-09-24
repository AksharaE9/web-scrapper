/**
 * ReviewQueue — REL-2.0 Part A: Identity-based cursor, frozen queue snapshot.
 *
 * Three bugs in the original implementation:
 *   A1 — positional cursor over a mutating array (22→11 skip)
 *   A2 — stale closure in keyboard shortcuts (labels the same row repeatedly)
 *   A3 — no in-flight guard (click + keypress fire two concurrent mutations)
 *
 * Every guard below has a comment explaining what bug it prevents.
 * Do NOT remove any guard.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Lead } from "../../types";
import { useRelabelLead } from "../../hooks/useLeads";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { ReasonChip } from "../../components/ui/ReasonChip";
import {
  CheckCircle2,
  XCircle,
  SkipForward,
  ArrowLeft,
  MapPin,
  Undo2,
  CheckCheck,
} from "lucide-react";
import { toast } from "sonner";

type Verdict = "relevant" | "not_relevant" | "skip";
type DecidedEntry = { verdict: Verdict; at: number };

interface ReviewQueueProps {
  leads: Lead[];
  runId: string;
  onExit: () => void;
}

const STORAGE_KEY = (runId: string) => `rq_state_${runId}`;

function loadPersistedState(runId: string, queue: string[]) {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY(runId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as {
      queue: string[];
      decided: Record<string, DecidedEntry>;
      cursorId: string | null;
    };
    // Only restore if the queue snapshot matches — guards against stale state
    if (JSON.stringify(parsed.queue) === JSON.stringify(queue)) {
      return { decided: parsed.decided, cursorId: parsed.cursorId };
    }
  } catch {
    // ignore
  }
  return null;
}

function saveState(
  runId: string,
  queue: string[],
  decided: Record<string, DecidedEntry>,
  cursorId: string | null
) {
  try {
    sessionStorage.setItem(
      STORAGE_KEY(runId),
      JSON.stringify({ queue, decided, cursorId })
    );
  } catch {
    // ignore storage errors — non-fatal
  }
}

export const ReviewQueue: React.FC<ReviewQueueProps> = ({ leads, runId, onExit }) => {
  const relabelMutation = useRelabelLead(runId);

  // ── 1. FREEZE THE QUEUE ON ENTRY ─────────────────────────────────────────
  // Guard A1: the queue is a snapshot taken once on mount.
  // It does NOT shrink as items are labelled. Refetches update lead CONTENT
  // but never queue MEMBERSHIP or ORDER.
  const queueRef = useRef<string[] | null>(null);
  if (queueRef.current === null) {
    queueRef.current = leads.map((l) => l.id);
  }
  const queue = queueRef.current;

  // ── 2. RESTORE PERSISTED STATE OR INITIALISE FRESH ───────────────────────
  const [decided, setDecided] = useState<Record<string, DecidedEntry>>(() => {
    const persisted = loadPersistedState(runId, queue);
    return persisted?.decided ?? {};
  });
  const [cursorId, setCursorId] = useState<string | null>(() => {
    const persisted = loadPersistedState(runId, queue);
    return persisted?.cursorId ?? (queue[0] ?? null);
  });
  // Use a ref for inFlight so the check is SYNCHRONOUS (no setState delay)
  // If we used useState, React would batch the update and a second event could
  // slip through before the render with inFlight=true.
  const inFlightRef = useRef(false);

  // Build id → lead map; updated when the lead list refetches (content may change)
  const byId = useMemo(() => new Map(leads.map((l) => [l.id, l])), [leads]);

  const currentLead = cursorId ? byId.get(cursorId) : undefined;

  // Position is DERIVED from identity — never the other way round.
  const position = cursorId ? queue.indexOf(cursorId) + 1 : queue.length;
  const decidedCount = Object.keys(decided).length;

  // ── 3. PERSIST STATE ON EVERY CHANGE ─────────────────────────────────────
  // Guard R9: closing the drawer mid-review resumes at the same item.
  useEffect(() => {
    saveState(runId, queue, decided, cursorId);
  }, [runId, queue, decided, cursorId]);

  // ── 4. ADVANCE = FIND NEXT UNDECIDED BY IDENTITY ─────────────────────────
  // Guard A1: walks the frozen queue by identity. Skipped items are re-visited
  // by the wrap-around loop.
  const nextUndecidedAfter = useCallback(
    (id: string, decidedNow: Record<string, DecidedEntry>): string | null => {
      const start = queue.indexOf(id);
      // Forward pass: from start+1 to end
      for (let i = start + 1; i < queue.length; i++) {
        if (!decidedNow[queue[i]]) return queue[i];
      }
      // Wrap: from beginning to start (catches earlier skips)
      for (let i = 0; i < start; i++) {
        if (!decidedNow[queue[i]]) return queue[i];
      }
      return null; // All decided
    },
    [queue]
  );

  // ── 5. UNDO ───────────────────────────────────────────────────────────────
  const [undoStack, setUndoStack] = useState<string[]>([]);

  const undo = useCallback(async () => {
    if (undoStack.length === 0) return;
    const prevId = undoStack[undoStack.length - 1];
    const prevEntry = decided[prevId];
    if (!prevEntry || prevEntry.verdict === "skip") {
      // Just remove from decided, no retraction needed
    } else {
      // Send retraction to backend (verdict=null retracts)
      try {
        await relabelMutation.mutateAsync({
          businessId: prevId,
          verdict: "unsure" as any, // backend treats unsure as "retract"
        });
      } catch {
        // retraction failure is non-fatal — still restore locally
      }
    }
    const newDecided = { ...decided };
    delete newDecided[prevId];
    setDecided(newDecided);
    setCursorId(prevId);
    setUndoStack((s) => s.slice(0, -1));
  }, [decided, undoStack, relabelMutation]);

  // ── 6. SINGLE GUARDED ACTION ─────────────────────────────────────────────
  const handleAction = useCallback(
    async (verdict: Verdict) => {
      const id = cursorId;
      if (!id) return;
      // Guard: never double-label the same business
      if (decided[id]) return;

      if (inFlightRef.current) return; // synchronous guard
      inFlightRef.current = true;
      try {
        if (verdict !== "skip") {
          await relabelMutation.mutateAsync({
            businessId: id,
            verdict: verdict as "relevant" | "not_relevant",
          });
        }
        const decidedNow: Record<string, DecidedEntry> = {
          ...decided,
          [id]: { verdict, at: Date.now() },
        };
        setDecided(decidedNow);
        setUndoStack((s) => [...s, id]);
        const next = nextUndecidedAfter(id, decidedNow);
        setCursorId(next); // null means all done
      } catch (err: any) {
        // Guard: NO-ADVANCE-ON-ERROR. The item stays undecided and on screen.
        toast.error(err?.message ?? "Failed to submit label — item stays in queue");
      } finally {
        inFlightRef.current = false;
      }
    },
    [cursorId, decided, nextUndecidedAfter, relabelMutation]
  );

  // ── 7. KEYBOARD — the handler is a REF, never stale ─────────────────────
  // Guard A2: actionRef is refreshed on every render. The effect registers
  // once (no dependency on handleAction), preventing stale closures AND
  // preventing listener accumulation.
  const actionRef = useRef(handleAction);
  actionRef.current = handleAction;
  const undoRef = useRef(undo);
  undoRef.current = undo;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Guard: ignore key-repeat (holding Y)
      if (e.repeat) return;
      // Guard: ignore when typing in a form field
      const t = e.target as HTMLElement | null;
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      if (t?.isContentEditable) return;
      // Guard: ignore modified keys (Ctrl+Y, etc.)
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const k = e.key.toLowerCase();
      if (k === "y") {
        e.preventDefault();
        void actionRef.current("relevant");
      } else if (k === "n") {
        e.preventDefault();
        void actionRef.current("not_relevant");
      } else if (k === "s") {
        e.preventDefault();
        void actionRef.current("skip");
      } else if (k === "u") {
        e.preventDefault();
        void undoRef.current();
      } else if (e.key === "Escape") {
        onExit();
      }
    };
    // Listen on window — document events (from jsdom) bubble up through window via bubbles:true
    window.addEventListener("keydown", onKey);
    // Guard A2: cleanup removes the listener so it does not accumulate
    return () => window.removeEventListener("keydown", onKey);
  }, [onExit]); // intentionally minimal deps — handlers accessed via refs

  // ── RENDER: EMPTY STATE ───────────────────────────────────────────────────
  if (queue.length === 0) {
    return (
      <div className="p-8 text-center border border-dashed border-border-strong rounded-lg bg-surface-1">
        <h3 className="text-base font-bold text-text-primary mb-2">Review Queue Empty</h3>
        <p className="text-xs text-text-muted mb-4">No remaining leads requiring manual triage.</p>
        <Button variant="primary" size="sm" onClick={onExit}>
          Return to Leads Table
        </Button>
      </div>
    );
  }

  // ── RENDER: FINISH SCREEN (all items decided) ─────────────────────────────
  if (cursorId === null) {
    const verdictCounts = Object.values(decided).reduce(
      (acc, d) => {
        acc[d.verdict] = (acc[d.verdict] ?? 0) + 1;
        return acc;
      },
      {} as Record<Verdict, number>
    );
    const hasSkipped = (verdictCounts.skip ?? 0) > 0;

    return (
      <div className="p-8 text-center border border-border-strong rounded-lg bg-surface-1 shadow-lg space-y-5 max-w-2xl mx-auto">
        <div className="flex justify-center">
          <CheckCheck className="w-10 h-10 text-emerald-400" />
        </div>
        <h3 className="text-lg font-bold text-text-primary">Review Complete</h3>
        <div className="grid grid-cols-3 gap-3 text-sm font-mono">
          <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <div className="text-2xl font-bold text-emerald-400">{verdictCounts.relevant ?? 0}</div>
            <div className="text-xs text-text-muted mt-1">Accepted</div>
          </div>
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
            <div className="text-2xl font-bold text-rose-400">{verdictCounts.not_relevant ?? 0}</div>
            <div className="text-xs text-text-muted mt-1">Rejected</div>
          </div>
          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <div className="text-2xl font-bold text-amber-400">{verdictCounts.skip ?? 0}</div>
            <div className="text-xs text-text-muted mt-1">Skipped</div>
          </div>
        </div>
        <p className="text-xs text-text-muted">
          {hasSkipped
            ? "Skipped items will be presented in the next review cycle."
            : "All items reviewed. Labels have been submitted for model training."}
        </p>
        <div className="flex gap-3 justify-center">
          {hasSkipped && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                // Reset cursor to first skipped item
                const firstSkipped = queue.find((id) => decided[id]?.verdict === "skip");
                if (firstSkipped) {
                  // Remove all skips from decided so they re-appear
                  const newDecided = Object.fromEntries(
                    Object.entries(decided).filter(([, v]) => v.verdict !== "skip")
                  );
                  setDecided(newDecided);
                  setCursorId(firstSkipped);
                }
              }}
            >
              Review Skipped Items ({verdictCounts.skip ?? 0})
            </Button>
          )}
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              sessionStorage.removeItem(STORAGE_KEY(runId));
              onExit();
            }}
          >
            Done
          </Button>
        </div>
      </div>
    );
  }

  // ── RENDER: REVIEW CARD ───────────────────────────────────────────────────
  const lead = currentLead;
  const progress = queue.length > 0 ? (decidedCount / queue.length) * 100 : 0;

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {/* Header & Progress */}
      <div className="flex items-center justify-between">
        <button
          onClick={onExit}
          className="text-xs text-text-muted hover:text-text-primary flex items-center gap-1 cursor-pointer font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Table
        </button>

        <div className="flex items-center gap-3">
          {undoStack.length > 0 && (
            <button
              onClick={undo}
              className="text-xs text-text-muted hover:text-amber-300 flex items-center gap-1 font-mono"
              title="Undo last label (U)"
            >
              <Undo2 className="w-3 h-3" /> Undo (U)
            </button>
          )}
          {/* Honest progress: decisions made, not cursor position */}
          <div className="text-xs font-mono text-text-secondary font-semibold">
            Reviewed {decidedCount} of {queue.length}
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div
          className="h-full bg-accent transition-all duration-200"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Main Review Card */}
      {lead ? (
        <div className="p-6 rounded-lg border border-border-strong bg-surface-1 shadow-lg space-y-5">
          <div className="flex items-start justify-between gap-3 border-b border-border-subtle pb-4">
            <div>
              <h2 className="text-lg font-bold text-text-primary">{lead.canonical_name}</h2>
              <div className="text-xs text-text-muted flex items-center gap-1 mt-1 font-mono">
                <MapPin className="w-3.5 h-3.5 text-accent" />
                <span>{lead.locality || (lead as any).address_text || "—"}</span>
              </div>
            </div>
            <Badge variant="likely">{lead.tier}</Badge>
          </div>

          {/* Contact Info */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 bg-surface-2/40 rounded-md text-xs font-mono">
            <div>
              <span className="text-text-muted block text-[10px]">PHONE</span>
              <span className="font-semibold text-text-primary">{lead.phones_e164?.[0] || "—"}</span>
            </div>
            <div>
              <span className="text-text-muted block text-[10px]">EMAIL</span>
              <span className="font-semibold text-text-primary">{lead.emails?.[0] || "—"}</span>
            </div>
            <div>
              <span className="text-text-muted block text-[10px]">WEBSITE</span>
              <span className="font-semibold text-text-primary truncate block">
                {lead.website_domain || "—"}
              </span>
            </div>
          </div>

          {/* Reasons */}
          <div>
            <div className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider font-mono mb-2">
              Relevance Features & Signals
            </div>
            <div className="flex flex-wrap gap-1.5">
              {lead.relevance_reasons && lead.relevance_reasons.length > 0 ? (
                lead.relevance_reasons.map((r, i) => (
                  <ReasonChip
                    key={i}
                    type={r.type || "positive"}
                    label={r.label || r.feature || r.detail || "signal"}
                    weight={r.weight}
                  />
                ))
              ) : (
                <span className="text-text-muted font-mono text-xs">Standard ontology match</span>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="pt-4 border-t border-border-subtle flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="md"
                onClick={() => handleAction("relevant")}
                className="bg-emerald-600 hover:bg-emerald-700 gap-1.5 shadow"
              >
                <CheckCircle2 className="w-4 h-4" /> Accept (Y)
              </Button>
              <Button
                variant="danger"
                size="md"
                onClick={() => handleAction("not_relevant")}
                className="gap-1.5 shadow"
              >
                <XCircle className="w-4 h-4" /> Reject (N)
              </Button>
            </div>

            <Button
              variant="outline"
              size="md"
              onClick={() => handleAction("skip")}
              className="gap-1.5"
            >
              <SkipForward className="w-4 h-4" /> Skip (S)
            </Button>
          </div>
        </div>
      ) : (
        // Lead content not yet in cache (id in queue but not in byId map)
        <div className="p-6 rounded-lg border border-border-subtle bg-surface-1 text-center text-text-muted text-sm">
          Loading lead {position} of {queue.length}…
        </div>
      )}
    </div>
  );
};
