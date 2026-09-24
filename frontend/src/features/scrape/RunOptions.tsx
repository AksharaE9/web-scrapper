import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useScrapeDraft } from "../../stores/useScrapeDraft";
import { Globe, Database, Sliders, AlertCircle } from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { api } from "../../api/client";
import { qk } from "../../lib/queryKeys";

export const RunOptions: React.FC = () => {
  const {
    maxResults,
    enrichWebsites,
    sources,
    setMaxResults,
    setEnrichWebsites,
    setSources,
  } = useScrapeDraft();

  const { data: configSources = [] } = useQuery({
    queryKey: qk.configSources,
    queryFn: () => api.getConfigSources(),
    staleTime: 600_000,
  });

  const { data: configLimits } = useQuery({
    queryKey: qk.configLimits,
    queryFn: () => api.getConfigLimits(),
    staleTime: 600_000,
  });

  const maxLimit = configLimits?.max_results_max ?? 5000;
  const minLimit = configLimits?.max_results_min ?? 1;

  const handleSourceToggle = (srcId: string) => {
    if (sources.includes(srcId)) {
      if (sources.length > 1) {
        setSources(sources.filter((s) => s !== srcId));
      }
    } else {
      setSources([...sources, srcId]);
    }
  };

  const presetChips = [25, 50, 100, 250, 500, 1000, 2500];

  return (
    <div className="p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm space-y-4">
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 rounded-full bg-accent/10 text-accent flex items-center justify-center font-bold text-xs">
          3
        </div>
        <h3 className="text-sm font-semibold text-text-primary">How — Ingestion & Enrichment Parameters</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        {/* Max Results */}
        <div className="space-y-2">
          <div className="flex items-center justify-between font-medium text-text-secondary">
            <span className="flex items-center gap-1.5"><Sliders className="w-3.5 h-3.5" /> Max Results</span>
            <div className="flex items-center gap-1">
              <input
                data-testid="max-results"
                type="number"
                min={minLimit}
                max={maxLimit}
                value={maxResults}
                onChange={(e) => setMaxResults(Math.max(minLimit, Math.min(maxLimit, Number(e.target.value) || minLimit)))}
                className="w-16 px-1.5 py-0.5 text-right font-mono font-bold text-accent bg-surface-2 border border-border-subtle rounded text-xs focus:outline-none focus:border-accent"
              />
              <span className="text-text-muted">leads</span>
            </div>
          </div>

          <div className="flex flex-wrap gap-1">
            {presetChips.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => setMaxResults(chip)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                  maxResults === chip
                    ? "bg-accent text-white font-bold"
                    : "bg-surface-2 text-text-muted hover:bg-surface-2/80 hover:text-text-primary"
                }`}
              >
                {chip}
              </button>
            ))}
          </div>

          {maxResults > (configLimits?.warn_above ?? 1000) && (
            <div className="flex items-center gap-1 text-[10px] text-amber-500">
              <AlertCircle className="w-3 h-3 shrink-0" />
              <span>Large queries may take longer to complete.</span>
            </div>
          )}
        </div>

        {/* Source Providers */}
        <div className="space-y-1.5">
          <span className="font-medium text-text-secondary block flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5" /> Discovery Sources
          </span>
          <div className="space-y-1">
            {(configSources.length > 0 ? configSources : [
              { id: "overture", label: "Overture Places", implemented: true, licence: "CDLA-Permissive-2.0" },
              { id: "osm", label: "OpenStreetMap", implemented: true, licence: "ODbL 1.0" },
              { id: "wikidata", label: "Wikidata SPARQL", implemented: false, licence: "CC0" },
              { id: "alltheplaces", label: "AllThePlaces", implemented: false, licence: "CC-0" },
            ]).map((src) => {
              const isImplemented = src.implemented;
              return (
                <div key={src.id} className="flex items-center justify-between">
                  <label
                    className={`flex items-center gap-2 text-text-primary ${
                      isImplemented ? "cursor-pointer" : "text-text-muted opacity-50 cursor-not-allowed"
                    }`}
                  >
                    <input
                      data-testid={`source-${src.id}`}
                      type="checkbox"
                      disabled={!isImplemented}
                      checked={isImplemented && sources.includes(src.id)}
                      onChange={() => isImplemented && handleSourceToggle(src.id)}
                      className="rounded text-accent focus:ring-focus-ring"
                    />
                    <span>{src.label}</span>
                  </label>
                  {!isImplemented && (
                    <Badge variant="outline" size="sm" className="text-[9px]">
                      STUB
                    </Badge>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Web Enrichment */}
        <div className="space-y-3">
          <div className="space-y-1.5">
            <span className="font-medium text-text-secondary block flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5" /> Web Scraping & Enrichment
            </span>
            <label className="flex items-start gap-2 text-text-primary cursor-pointer p-2 rounded-md bg-surface-2/40 border border-border-subtle">
              <input
                type="checkbox"
                checked={enrichWebsites}
                onChange={(e) => setEnrichWebsites(e.target.checked)}
                className="mt-0.5 rounded text-accent focus:ring-focus-ring"
              />
              <div>
                <div className="font-semibold">Crawl Business Websites</div>
                <div className="text-[11px] text-text-muted">
                  Extracts phone/email, parses JSON-LD, checks robots.txt with polite backoff.
                </div>
              </div>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
};
