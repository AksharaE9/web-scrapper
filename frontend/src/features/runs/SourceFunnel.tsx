import React, { useState } from "react";
import { Layers, Database, AlertCircle, CheckCircle, RefreshCw, ChevronDown, ChevronRight, Zap } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { api } from "../../api/client";

interface SourceStatsProps {
  sourceStats?: Record<string, any>;
  keywords?: string[];
  locality?: string;
  onRefreshRun?: () => void;
}

export const SourceFunnel: React.FC<SourceStatsProps> = ({
  sourceStats = {},
  keywords = [],
  locality = "this area",
  onRefreshRun,
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const [purging, setPurging] = useState(false);
  const [purgeSuccess, setPurgeSuccess] = useState<string | null>(null);

  const overture = sourceStats?.overture;
  const osm = sourceStats?.osm;

  if (!overture && !osm && Object.keys(sourceStats).length === 0) {
    return null;
  }

  const handlePurgeCache = async () => {
    try {
      setPurging(true);
      setPurgeSuccess(null);
      const res = await api.post("/cache/overture/purge", {});
      setPurgeSuccess(res.data?.message || "Overture cache purged successfully");
      if (onRefreshRun) {
        onRefreshRun();
      }
    } catch (err: any) {
      setPurgeSuccess("Failed to purge cache");
    } finally {
      setPurging(false);
    }
  };

  const overtureRaw = overture?.raw_count ?? overture?.count ?? 0;
  const overtureMatched = overture?.matched ?? 0;
  const overtureParseFails = overture?.parse_failures ?? 0;
  const overtureCategories = overture?.plan_categories ?? [];

  const osmRaw = osm?.raw_elements ?? osm?.count ?? 0;
  const osmMatched = osm?.matched ?? osm?.count ?? 0;

  const keywordPlanFailed = (overtureRaw > 0 && overtureMatched === 0) || (osmRaw > 0 && osmMatched === 0);

  return (
    <div
      data-testid="source-funnel-panel"
      className="rounded-xl border border-border bg-card/60 backdrop-blur-xs overflow-hidden shadow-xs"
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2.5">
          <Layers className="w-4 h-4 text-primary" />
          <span className="text-xs font-semibold uppercase tracking-wider text-text-primary">
            Source Funnel &amp; Telemetry
          </span>
          {overture && (
            <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-background/80 border border-border text-text-secondary">
              Overture: {overtureMatched} / {overtureRaw}
            </span>
          )}
          {osm && (
            <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-background/80 border border-border text-text-secondary">
              OSM: {osmMatched} / {osmRaw}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-text-muted">
          {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </div>
      </button>

      {isOpen && (
        <div className="p-4 space-y-4 text-xs font-mono">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Overture Section */}
            {overture && (
              <div className="p-3 rounded-lg bg-background/60 border border-border/80 space-y-2">
                <div className="flex items-center justify-between pb-1.5 border-b border-border/50">
                  <div className="flex items-center gap-1.5 font-semibold text-text-primary">
                    <Database className="w-3.5 h-3.5 text-blue-400" />
                    <span>Overture Maps</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px]">
                    <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">
                      {overture.release || "2026-08-19.0"}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded ${
                        overture.cache_hit
                          ? "bg-emerald-500/10 text-emerald-400"
                          : "bg-amber-500/10 text-amber-400"
                      }`}
                    >
                      {overture.cache_hit ? "CACHE HIT" : "CACHE MISS"}
                    </span>
                  </div>
                </div>

                <div className="space-y-1 text-text-secondary text-[11px]">
                  <div className="flex justify-between">
                    <span>Rows inside boundary polygon:</span>
                    <span className="font-semibold text-text-primary">{overtureRaw.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Rows parsed OK:</span>
                    <span>{(overtureRaw - overtureParseFails).toLocaleString()}</span>
                  </div>
                  {overtureParseFails > 0 && (
                    <div className="flex justify-between text-amber-400">
                      <span>Parse failures:</span>
                      <span>{overtureParseFails}</span>
                    </div>
                  )}
                  <div className="flex justify-between pt-1 border-t border-border/40 font-medium">
                    <span>Matched keyword plan:</span>
                    <span
                      className={
                        overtureMatched > 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"
                      }
                    >
                      {overtureMatched}
                    </span>
                  </div>
                </div>

                {overtureCategories.length > 0 && (
                  <div className="pt-1.5 text-[10px] text-text-muted">
                    <span className="text-text-secondary">Plan Categories:</span>{" "}
                    {JSON.stringify(overtureCategories)}
                  </div>
                )}
              </div>
            )}

            {/* OSM Overpass Section */}
            {osm && (
              <div className="p-3 rounded-lg bg-background/60 border border-border/80 space-y-2">
                <div className="flex items-center justify-between pb-1.5 border-b border-border/50">
                  <div className="flex items-center gap-1.5 font-semibold text-text-primary">
                    <Zap className="w-3.5 h-3.5 text-emerald-400" />
                    <span>OSM Overpass</span>
                  </div>
                  <div className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                    LIVE API
                  </div>
                </div>

                <div className="space-y-1 text-text-secondary text-[11px]">
                  <div className="flex justify-between">
                    <span>Elements returned:</span>
                    <span className="font-semibold text-text-primary">{osmRaw.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between pt-1 border-t border-border/40 font-medium">
                    <span>Matched keyword plan:</span>
                    <span
                      className={
                        osmMatched > 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"
                      }
                    >
                      {osmMatched}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Diagnostic Alert & Remediation */}
          {keywordPlanFailed && (
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Keyword Plan Shortfall:</span> Sources returned raw places,
                  but 0 matched the search criteria for &ldquo;{keywords.join(", ") || "keyword"}&rdquo;.
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePurgeCache}
                  disabled={purging}
                  className="text-[11px] h-7 px-2.5 border-amber-500/40 text-amber-900 dark:text-amber-200"
                >
                  <RefreshCw className={`w-3 h-3 mr-1 ${purging ? "animate-spin" : ""}`} />
                  Purge &amp; Rebuild Cache
                </Button>
              </div>
            </div>
          )}

          {purgeSuccess && (
            <div className="text-[11px] text-emerald-400 flex items-center gap-1.5">
              <CheckCircle className="w-3.5 h-3.5" />
              <span>{purgeSuccess}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
