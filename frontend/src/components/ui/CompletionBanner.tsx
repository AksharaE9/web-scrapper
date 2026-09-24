import React, { useState } from "react";
import { Info, AlertTriangle, Database, Clock, RefreshCw, X, ArrowRight, Eye, SlidersHorizontal, CheckCircle2 } from "lucide-react";
import { Button } from "./Button";

export interface CompletionBannerProps {
  reason?: string | null;
  acceptedCount: number;
  targetCount: number;
  details?: Record<string, any>;
  locality?: string;
  keyword?: string;
  reviewCount?: number;
  onWidenArea?: () => void;
  onReviewBorderline?: () => void;
  onViewExisting?: () => void;
  onRetrySource?: (sourceName?: string) => void;
  onEditConcept?: () => void;
  onExport?: () => void;
}

export const CompletionBanner: React.FC<CompletionBannerProps> = ({
  reason,
  acceptedCount,
  targetCount,
  details = {},
  locality = "this region",
  keyword = "business",
  reviewCount = 0,
  onWidenArea,
  onReviewBorderline,
  onViewExisting,
  onRetrySource,
  onEditConcept,
  onExport,
}) => {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed || !reason) return null;

  // Don't show shortfall banner if target was met
  if (reason === "target_met" && acceptedCount >= targetCount) {
    return (
      <div
        data-testid="completion-banner"
        className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200"
      >
        <div className="flex items-center gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
          <span className="font-semibold">
            {acceptedCount} of {targetCount} leads found.
          </span>
        </div>
        <div className="flex items-center gap-2">
          {onExport && (
            <Button variant="outline" size="sm" onClick={onExport} className="text-[11px] h-7 px-2.5">
              Export Leads
            </Button>
          )}
          <button
            type="button"
            onClick={() => setDismissed(true)}
            className="p-1 rounded hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
            title="Dismiss notification"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  // Reason-specific configurations
  switch (reason) {
    case "keyword_plan_matched_nothing": {
      const rawCount = details.raw_count || details.candidates_seen || 0;
      return (
        <div
          data-testid="completion-banner-keyword-plan-matched-nothing"
          className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-900 dark:text-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200"
        >
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold text-amber-950 dark:text-amber-100">
                Found {rawCount.toLocaleString()} places in {locality}, but none matched '{keyword}'.
              </p>
              <p className="text-[11px] text-amber-800 dark:text-amber-300 opacity-90">
                The search plan for this keyword did not match any categories or name patterns in the retrieved places.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {onEditConcept && (
              <Button variant="primary" size="sm" onClick={onEditConcept} className="text-[11px] h-7 px-2.5 bg-amber-600 hover:bg-amber-700 text-white">
                Review Keyword Plan
              </Button>
            )}
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="p-1 rounded hover:bg-amber-500/20 text-amber-600 dark:text-amber-400"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      );
    }

    case "no_candidates_found": {
      return (
        <div
          data-testid="completion-banner-no-candidates-found"
          className="p-3.5 rounded-xl bg-neutral-500/10 border border-neutral-500/30 text-xs text-neutral-900 dark:text-neutral-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200"
        >
          <div className="flex items-start gap-2.5">
            <Info className="w-4 h-4 text-neutral-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold text-neutral-950 dark:text-neutral-100">
                No places at all were returned for {locality}.
              </p>
              <p className="text-[11px] text-neutral-800 dark:text-neutral-300 opacity-90">
                This usually means the boundary or polygon has no mapped businesses in the source datasets.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {onWidenArea && (
              <Button variant="primary" size="sm" onClick={onWidenArea} className="text-[11px] h-7 px-2.5 bg-neutral-700 hover:bg-neutral-800 text-white">
                Widen Area
              </Button>
            )}
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="p-1 rounded hover:bg-neutral-500/20 text-neutral-600 dark:text-neutral-400"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      );
    }

    case "no_new_leads": {
      const alreadyKnown = details.already_known || details.candidates || (targetCount - acceptedCount);
      return (
        <div
          data-testid="completion-banner-no-new-leads"
          className="p-3.5 rounded-xl bg-blue-500/10 border border-blue-500/30 text-xs text-blue-900 dark:text-blue-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200"
        >
          <div className="flex items-start gap-2.5">
            <Database className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold text-blue-950 dark:text-blue-100">
                {acceptedCount} of {targetCount} found — {alreadyKnown} matches were already in your database from earlier runs.
              </p>
              <p className="text-[11px] text-blue-800 dark:text-blue-300 opacity-90">
                All candidates in {locality} are already indexed and stored with their corroboration history.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {onViewExisting && (
              <Button variant="primary" size="sm" onClick={onViewExisting} className="text-[11px] h-7 px-2.5 bg-blue-600 hover:bg-blue-700 text-white">
                <Eye className="w-3 h-3 mr-1" /> View Existing ({alreadyKnown})
              </Button>
            )}
            {onWidenArea && (
              <Button variant="outline" size="sm" onClick={onWidenArea} className="text-[11px] h-7 px-2.5">
                New Area
              </Button>
            )}
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="p-1 rounded hover:bg-blue-500/20 text-blue-600 dark:text-blue-400"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      );
    }

    case "region_exhausted": {
      const rungs = details.rungs_tried || [];
      const categories = details.categories_queried || "multiple";
      return (
        <div
          data-testid="exhaustion-banner"
          className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-900 dark:text-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200"
        >
          <div className="flex items-start gap-2.5">
            <Info className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold text-amber-950 dark:text-amber-100">
                {acceptedCount} of {targetCount} found — this area is genuinely exhausted.
              </p>
              <p className="text-[11px] text-amber-800 dark:text-amber-300 opacity-90">
                Searched {locality}, expanded across {categories} category definitions and {rungs.length || 2} strategy rungs. No further matches exist in source data.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {reviewCount > 0 && onReviewBorderline && (
              <Button variant="outline" size="sm" onClick={onReviewBorderline} className="text-[11px] h-7 px-2.5 border-amber-500/40 text-amber-900 dark:text-amber-200">
                Review {reviewCount} Borderline
              </Button>
            )}
            {onWidenArea && (
              <Button variant="primary" size="sm" onClick={onWidenArea} className="text-[11px] h-7 px-2.5 bg-amber-600 hover:bg-amber-700 text-white">
                Widen Area
              </Button>
            )}
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="p-1 rounded hover:bg-amber-500/20 text-amber-600 dark:text-amber-400"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      );
    }

    case "budget_exhausted": {
      const limit = details.limit || "time limit";
      return (
        <div
          data-testid="completion-banner-budget-exhausted"
          className="p-3.5 rounded-xl bg-purple-500/10 border border-purple-500/30 text-xs text-purple-900 dark:text-purple-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200"
        >
          <div className="flex items-start gap-2.5">
            <Clock className="w-4 h-4 text-purple-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold text-purple-950 dark:text-purple-100">
                {acceptedCount} of {targetCount} found — the run hit its {limit} before finishing.
              </p>
              <p className="text-[11px] text-purple-800 dark:text-purple-300 opacity-90">
                Resource safety limits halted further candidate evaluation.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {onWidenArea && (
              <Button variant="primary" size="sm" onClick={onWidenArea} className="text-[11px] h-7 px-2.5 bg-purple-600 hover:bg-purple-700 text-white">
                Raise Limit &amp; Continue
              </Button>
            )}
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="p-1 rounded hover:bg-purple-500/20 text-purple-600 dark:text-purple-400"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      );
    }

    case "partial_sources": {
      const failed = (details.failed || ["Upstream connector"]).join(", ");
      return (
        <div
          data-testid="completion-banner-partial-sources"
          className="p-3.5 rounded-xl bg-orange-500/10 border border-orange-500/30 text-xs text-orange-900 dark:text-orange-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200"
        >
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-orange-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold text-orange-950 dark:text-orange-100">
                {acceptedCount} of {targetCount} found — {failed} was unavailable, so results are incomplete.
              </p>
              <p className="text-[11px] text-orange-800 dark:text-orange-300 opacity-90">
                Other sources contributed successfully, but data completeness was impacted.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {onRetrySource && (
              <Button variant="primary" size="sm" onClick={() => onRetrySource(failed)} className="text-[11px] h-7 px-2.5 bg-orange-600 hover:bg-orange-700 text-white">
                <RefreshCw className="w-3 h-3 mr-1" /> Retry Missing Source
              </Button>
            )}
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="p-1 rounded hover:bg-orange-500/20 text-orange-600 dark:text-orange-400"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      );
    }

    case "low_relevance":
    default: {
      const candidates = details.candidates || (acceptedCount + 50);
      const rejected = candidates - acceptedCount;
      return (
        <div
          data-testid="completion-banner-low-relevance"
          className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-900 dark:text-rose-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200"
        >
          <div className="flex items-start gap-2.5">
            <SlidersHorizontal className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold text-rose-950 dark:text-rose-100">
                {acceptedCount} of {targetCount} found — {candidates} candidates were checked and {rejected > 0 ? rejected : "most"} didn't match '{keyword}'.
              </p>
              <p className="text-[11px] text-rose-800 dark:text-rose-300 opacity-90">
                A precision filter shortfall occurred. Refine synonyms or review rejected diagnoses.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {onEditConcept && (
              <Button variant="primary" size="sm" onClick={onEditConcept} className="text-[11px] h-7 px-2.5 bg-rose-600 hover:bg-rose-700 text-white">
                Edit Concept Card
              </Button>
            )}
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="p-1 rounded hover:bg-rose-500/20 text-rose-600 dark:text-rose-400"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      );
    }
  }
};
