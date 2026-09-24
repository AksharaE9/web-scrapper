import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useScrapeDraft } from "../../stores/useScrapeDraft";
import { useRunTracker } from "../../stores/useRunTracker";
import { api } from "../../api/client";
import { GeoResolution } from "../../types";
import { LocationBuilder } from "./LocationBuilder";
import { KeywordBuilder } from "./KeywordBuilder";
import { RunOptions } from "./RunOptions";
import { Button } from "../../components/ui/Button";
import { Play, RefreshCw, AlertCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "../../lib/cn";

export const ScrapePage: React.FC = () => {
  const navigate = useNavigate();
  const {
    location,
    naturalQuery,
    isNaturalMode,
    keywords,
    excludeKeywords,
    maxResults,
    minConfidence,
    enrichWebsites,
    sources,
    cachePolicy,
    maxCacheAgeDays,
    resetDraft,
  } = useScrapeDraft();

  const trackRun = useRunTracker((s) => s.trackRun);

  const [resolvedGeo, setResolvedGeo] = useState<GeoResolution | null>(null);
  const [starting, setStarting] = useState(false);

  const blockers = useMemo(() => {
    const b: { code: string; message: string; focus?: string }[] = [];
    const hasLocation = isNaturalMode
      ? naturalQuery.trim().length > 0
      : Boolean(location.locality?.trim() || location.city?.trim());

    if (!hasLocation) {
      b.push({
        code: "no_geo",
        message: "Resolve a locality first",
        focus: isNaturalMode ? "#natural-query" : "#locality",
      });
    }
    if (keywords.length === 0) {
      b.push({
        code: "no_keywords",
        message: "Add at least one keyword",
        focus: "#keyword-input",
      });
    }
    if (starting) {
      b.push({
        code: "running",
        message: "A run is already launching",
      });
    }
    return b;
  }, [isNaturalMode, naturalQuery, location.locality, location.city, keywords.length, starting]);

  const canLaunch = blockers.length === 0;

  const handleStartRun = async () => {
    if (!canLaunch) {
      toast.error("Please resolve all blockers before launching.");
      return;
    }

    setStarting(true);
    try {
      const payload = {
        location: isNaturalMode
          ? { raw_text: naturalQuery }
          : {
              locality: location.locality,
              city: location.city,
              state: location.state,
              country: location.country,
            },
        keywords,
        exclude_keywords: excludeKeywords,
        max_results: maxResults,
        min_confidence: minConfidence,
        enrich_websites: enrichWebsites,
        sources,
        cache_policy: cachePolicy,
        max_cache_age_days: maxCacheAgeDays,
      };

      const res = await api.startRun(payload);
      trackRun(
        res.run_id,
        keywords.join(", "),
        isNaturalMode ? naturalQuery : location.locality || location.city || "Custom Search"
      );
      toast.success("Pipeline run launched!");
      navigate(`/runs/${res.run_id}/live`);
    } catch (err: any) {
      toast.error(err.message || "Failed to start run");
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-28">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary">
            Target Lead Discovery
          </h1>
          <p className="text-xs text-text-muted mt-0.5">
            Configure geographic bounds, ontology keywords, and source ingestion rules.
          </p>
        </div>
        <button
          type="button"
          onClick={resetDraft}
          className="text-xs text-text-muted hover:text-text-primary flex items-center gap-1 transition-colors cursor-pointer"
        >
          <RefreshCw className="w-3 h-3" /> Reset Form
        </button>
      </div>

      {/* 3 Step Form */}
      <LocationBuilder
        onGeoResolved={setResolvedGeo}
        resolvedGeo={resolvedGeo}
      />

      <KeywordBuilder />

      <RunOptions />

      {/* Sticky Bottom Summary Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-30 bg-surface-1/95 backdrop-blur-md border-t border-border-subtle p-3 sm:px-8 shadow-2xl">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1 text-xs truncate">
            <div className="flex items-center gap-1.5 truncate">
              <span className="font-semibold text-text-primary">
                {keywords.length > 0 ? keywords.slice(0, 2).join(", ") : "No keywords"}
                {keywords.length > 2 && ` +${keywords.length - 2} more`}
              </span>
              <span className="text-text-muted"> in </span>
              <span className="font-semibold text-text-primary">
                {isNaturalMode ? naturalQuery || "Location" : location.locality || location.city || "Locality"}
              </span>
              <span className="text-text-muted"> · {sources.join(" + ").toUpperCase()} (max {maxResults})</span>
            </div>

            {/* Launch Blockers List */}
            {!canLaunch && (
              <ul id="launch-blockers" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-amber-400 text-[11px]" aria-live="polite">
                {blockers.map((b) => (
                  <li key={b.code} className="inline-flex items-center gap-1">
                    <AlertCircle className="w-3 h-3 shrink-0" />
                    <span>{b.message}</span>
                    {b.focus && (
                      <button
                        type="button"
                        onClick={() => {
                          const el = document.querySelector<HTMLElement>(b.focus!);
                          el?.focus();
                          el?.scrollIntoView({ behavior: "smooth", block: "center" });
                        }}
                        className="underline hover:text-amber-300 font-medium ml-0.5 cursor-pointer"
                      >
                        Fix
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <button
            type="button"
            disabled={!canLaunch}
            aria-disabled={!canLaunch}
            aria-describedby={canLaunch ? undefined : "launch-blockers"}
            onClick={handleStartRun}
            className={cn(
              "py-2.5 px-6 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all shrink-0",
              canLaunch
                ? "bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 text-white shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:opacity-95 active:scale-[0.99] cursor-pointer"
                : "bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed shadow-none opacity-60 pointer-events-none"
            )}
          >
            {starting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Launching…</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>Launch Discovery ({maxResults} target)</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
