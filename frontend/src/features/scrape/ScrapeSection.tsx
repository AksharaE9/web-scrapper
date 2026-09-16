import React, { useState, useEffect } from "react";
import {
  MapPin,
  Tag,
  Ban,
  Layers,
  Sparkles,
  Play,
  Sliders,
  Gauge,
  Zap,
} from "lucide-react";
import { GeoResolution, KeywordPlan, KeywordPreset, NodeEvent, QueryInput } from "../../types";
import { api } from "../../api/client";
import { MapPreview } from "./MapPreview";
import { RunGraphView } from "./RunGraphView";

interface ScrapeSectionProps {
  onRunStarted: (runId: string) => void;
}

export const ScrapeSection: React.FC<ScrapeSectionProps> = ({ onRunStarted }) => {
  // Input form state
  const [useNaturalText, setUseNaturalText] = useState<boolean>(false);
  const [rawText, setRawText] = useState<string>("");
  const [locality, setLocality] = useState<string>("");
  const [city, setCity] = useState<string>("");
  const [stateName, setStateName] = useState<string>("");
  const [country, setCountry] = useState<string>("India");

  const [keywordInput, setKeywordInput] = useState<string>("");
  const [keywords, setKeywords] = useState<string[]>([]);
  const [excludeInput, setExcludeInput] = useState<string>("");
  const [excludeKeywords, setExcludeKeywords] = useState<string[]>([]);

  // Lead target volume and discovery sources
  const [maxResults, setMaxResults] = useState<number>(100);
  const [sources, setSources] = useState<string[]>(["overture", "osm"]);
  const [enrichWebsites] = useState<boolean>(true);

  // Previews
  const [geoPreview, setGeoPreview] = useState<GeoResolution | null>(null);
  const [keywordPlans, setKeywordPlans] = useState<Record<string, KeywordPlan>>({});
  const [presets, setPresets] = useState<KeywordPreset[]>([]);
  const [selectedPlanPreview, setSelectedPlanPreview] = useState<KeywordPlan | null>(null);

  // Execution state
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [nodeEvents, setNodeEvents] = useState<Record<string, NodeEvent>>({});

  useEffect(() => {
    // Load presets
    api.listPresets().then(setPresets).catch(console.error);
  }, []);

  const handleResolveGeo = async () => {
    if (!useNaturalText && !locality && !city && !stateName) {
      setGeoPreview(null);
      return;
    }
    if (useNaturalText && !rawText.trim()) {
      setGeoPreview(null);
      return;
    }
    try {
      const data = await api.previewGeo(
        useNaturalText
          ? { text: rawText }
          : { locality, city, state: stateName, country }
      );
      setGeoPreview(data);
    } catch (e) {
      console.error("Geo resolve error:", e);
    }
  };

  const addKeyword = async (kw: string) => {
    const trimmed = kw.trim();
    if (trimmed && !keywords.includes(trimmed)) {
      setKeywords([...keywords, trimmed]);
      try {
        const plan = await api.previewKeywordPlan(trimmed);
        setKeywordPlans((prev: Record<string, KeywordPlan>) => ({ ...prev, [trimmed]: plan }));
      } catch (e) {
        console.error("Keyword plan error:", e);
      }
    }
    setKeywordInput("");
  };

  const removeKeyword = (kw: string) => {
    setKeywords(keywords.filter((k: string) => k !== kw));
  };

  const addExclude = (kw: string) => {
    const trimmed = kw.trim();
    if (trimmed && !excludeKeywords.includes(trimmed)) {
      setExcludeKeywords([...excludeKeywords, trimmed]);
    }
    setExcludeInput("");
  };

  const removeExclude = (kw: string) => {
    setExcludeKeywords(excludeKeywords.filter((k: string) => k !== kw));
  };

  const applyPreset = (p: KeywordPreset) => {
    setKeywords(p.search_categories);
    setExcludeKeywords(p.exclude_keywords || []);
  };

  const handleStartRun = async () => {
    if (keywords.length === 0) return;
    setIsRunning(true);
    setNodeEvents({});

    const query: QueryInput = {
      location: useNaturalText
        ? { raw_text: rawText }
        : { locality, city, state: stateName, country },
      keywords,
      exclude_keywords: excludeKeywords,
      max_results: maxResults,
      enrich_websites: enrichWebsites,
      sources,
    };

    try {
      const res = await api.startRun(query);
      onRunStarted(res.run_id);

      // Subscribe to SSE
      api.subscribeRunEvents(
        res.run_id,
        (ev: any) => {
          if (ev.node) {
            setNodeEvents((prev: Record<string, NodeEvent>) => ({ ...prev, [ev.node]: ev }));
          }
          if (ev.type === "run_completed" || ev.status === "completed" || ev.status === "failed") {
            setIsRunning(false);
          }
        },
        () => setIsRunning(false)
      );
    } catch (e: any) {
      alert(`Error starting run: ${e.message}`);
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-16">
      {/* Top Welcome Card */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-950/40 via-slate-900/60 to-slate-950/80 border border-indigo-500/20 p-8 shadow-2xl">
        <div className="max-w-2xl space-y-3 relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-mono">
            <Sparkles className="w-3.5 h-3.5" /> Graph-Engineered Local Lead Scraper
          </div>
          <h2 className="text-3xl font-heading font-bold text-white tracking-tight">
            Target Area & Keyword Discovery
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed">
            Enter any Indian locality and target SMB category. LeadCore Zero queries Overture Maps S3 Parquet partitions, OpenStreetMap Overpass API, resolves duplicates probabilistically with Splink, and verifies company details — ₹0 API cost.
          </p>
        </div>
      </div>

      {/* Main Grid: Inputs + Map Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Form (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Location Configuration Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white font-heading font-semibold">
                <MapPin className="w-4 h-4 text-indigo-400" />
                <span>Geographic Target</span>
              </div>
              <button
                type="button"
                onClick={() => setUseNaturalText(!useNaturalText)}
                className="text-xs text-indigo-400 hover:text-indigo-300 transition font-medium"
              >
                {useNaturalText ? "Switch to 4-field structure" : "Type naturally"}
              </button>
            </div>

            {useNaturalText ? (
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Natural Location Prompt
                </label>
                <input
                  type="text"
                  value={rawText}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRawText(e.target.value)}
                  onBlur={handleResolveGeo}
                  placeholder="e.g. Salons in Banjara Hills, Hyderabad, Telangana"
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-indigo-500 transition"
                />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">
                    Locality / Area
                  </label>
                  <input
                    type="text"
                    value={locality}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLocality(e.target.value)}
                    onBlur={handleResolveGeo}
                    onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleResolveGeo();
                      }
                    }}
                    placeholder="e.g. Indiranagar, Irramanzil, Bandra"
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-indigo-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">
                    City
                  </label>
                  <input
                    type="text"
                    value={city}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCity(e.target.value)}
                    onBlur={handleResolveGeo}
                    onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleResolveGeo();
                      }
                    }}
                    placeholder="e.g. Bengaluru, Hyderabad, Mumbai"
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-indigo-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">
                    State
                  </label>
                  <input
                    type="text"
                    value={stateName}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setStateName(e.target.value)}
                    onBlur={handleResolveGeo}
                    onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleResolveGeo();
                      }
                    }}
                    placeholder="e.g. Karnataka, Telangana, Maharashtra"
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-indigo-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">
                    Country
                  </label>
                  <input
                    type="text"
                    value={country}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCountry(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-400 text-sm focus:outline-none focus:border-indigo-500 transition"
                    disabled
                  />
                </div>
              </div>
            )}
          </div>

          {/* Keywords & Taxonomy Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white font-heading font-semibold">
                <Tag className="w-4 h-4 text-indigo-400" />
                <span>Search Keywords & Categories</span>
              </div>
              <span className="text-[11px] text-slate-500">Press Enter to add</span>
            </div>

            {/* Keyword tags */}
            <div>
              <div className="flex flex-wrap gap-2 mb-2">
                {keywords.map((kw: string) => (
                  <span
                    key={kw}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-200 text-xs font-medium cursor-pointer hover:bg-indigo-500/25 transition"
                    onClick={() => setSelectedPlanPreview(keywordPlans[kw] || null)}
                  >
                    <span>{kw}</span>
                    <button
                      type="button"
                      onClick={(e: React.MouseEvent) => {
                        e.stopPropagation();
                        removeKeyword(kw);
                      }}
                      className="text-indigo-400 hover:text-rose-400 font-bold ml-1"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <input
                type="text"
                value={keywordInput}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setKeywordInput(e.target.value)}
                onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addKeyword(keywordInput);
                  }
                }}
                placeholder="Type keyword (e.g. gym, cafe, dental clinic) and hit Enter"
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-indigo-500 transition"
              />
            </div>

            {/* Exclude keywords */}
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-slate-400 mb-2">
                <Ban className="w-3.5 h-3.5 text-rose-400" />
                <span>Exclude Negative Keywords</span>
              </div>
              <div className="flex flex-wrap gap-2 mb-2">
                {excludeKeywords.map((kw: string) => (
                  <span
                    key={kw}
                    className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs"
                  >
                    <span>{kw}</span>
                    <button
                      type="button"
                      onClick={() => removeExclude(kw)}
                      className="hover:text-rose-100 font-bold ml-1"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <input
                type="text"
                value={excludeInput}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setExcludeInput(e.target.value)}
                onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addExclude(excludeInput);
                  }
                }}
                placeholder="e.g. equipment, manufacturer, wholesaler"
                className="w-full px-4 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 text-xs focus:outline-none focus:border-rose-500/40 transition"
              />
            </div>

            {/* Quick Presets */}
            {presets.length > 0 && (
              <div className="pt-2 border-t border-slate-800/80">
                <span className="text-[11px] font-mono text-slate-500 block mb-2 uppercase tracking-wider">
                  Quick Industry Presets
                </span>
                <div className="flex flex-wrap gap-2">
                  {presets.slice(0, 5).map((p: KeywordPreset) => (
                    <button
                      key={p.id || p.name}
                      type="button"
                      onClick={() => applyPreset(p)}
                      className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:border-indigo-500/40 text-slate-300 hover:text-white text-xs transition"
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Sources & Options */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-2 text-white font-heading font-semibold text-sm">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>Independent Discovery Sources</span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs text-slate-300">
              <label className="flex items-center gap-2 cursor-pointer bg-slate-950/60 p-2.5 rounded-xl border border-slate-850">
                <input
                  type="checkbox"
                  checked={sources.includes("overture")}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    if (e.target.checked) setSources([...sources, "overture"]);
                    else setSources(sources.filter((s: string) => s !== "overture"));
                  }}
                  className="rounded text-indigo-600 focus:ring-0"
                />
                <span>Overture Maps S3 (Parquet)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer bg-slate-950/60 p-2.5 rounded-xl border border-slate-850">
                <input
                  type="checkbox"
                  checked={sources.includes("osm")}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    if (e.target.checked) setSources([...sources, "osm"]);
                    else setSources(sources.filter((s: string) => s !== "osm"));
                  }}
                  className="rounded text-indigo-600 focus:ring-0"
                />
                <span>OpenStreetMap (Overpass)</span>
              </label>
            </div>
          </div>

          {/* Target Leads Quantity Selector Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white font-heading font-semibold text-sm">
                <Sliders className="w-4 h-4 text-indigo-400" />
                <span>Target Leads Quantity</span>
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 font-mono text-xs font-bold">
                <Gauge className="w-3.5 h-3.5 text-indigo-400" />
                <span>{maxResults} Leads Target</span>
              </div>
            </div>

            {/* Quick Preset Buttons */}
            <div className="grid grid-cols-6 gap-2">
              {[50, 100, 250, 500, 1000, 2500].map((count) => (
                <button
                  key={count}
                  type="button"
                  onClick={() => setMaxResults(count)}
                  className={`py-2 px-1 rounded-xl text-xs font-mono font-semibold transition text-center ${
                    maxResults === count
                      ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 border border-indigo-400/30"
                      : "bg-slate-950 border border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
                  }`}
                >
                  {count >= 1000 ? `${count / 1000}k` : count}
                </button>
              ))}
            </div>

            {/* Smooth Range Slider */}
            <div className="space-y-1.5 pt-1">
              <input
                type="range"
                min={25}
                max={2500}
                step={25}
                value={maxResults}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMaxResults(Number(e.target.value))}
                className="w-full h-2 bg-slate-950 rounded-lg appearance-none cursor-pointer accent-indigo-500 border border-slate-800"
              />
              <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
                <span>25 (Local Microhood)</span>
                <span className="text-indigo-400 font-medium">
                  {maxResults <= 100
                    ? "~2.5 km search buffer"
                    : maxResults <= 300
                    ? "~4.5 km search buffer"
                    : maxResults <= 1000
                    ? "~8.0 km city-wide buffer"
                    : "~14.0 km metro buffer"}
                </span>
                <span>2,500+ (Metro-Wide)</span>
              </div>
            </div>

            {/* Throughput & Radial Guarantee Notice */}
            <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-850 flex items-start gap-2.5 text-xs text-slate-400">
              <Zap className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="leading-relaxed text-[11px]">
                <strong className="text-slate-200 font-medium">Concentric Radial Sorting:</strong> Leads are automatically sorted by outward distance rings from your target locality center (<span className="text-emerald-400">&lt;1.5km</span> first, then <span className="text-cyan-400">1.5–3.5km</span>, then <span className="text-indigo-400">3.5–6km+</span>) with confidence ranking.
              </div>
            </div>
          </div>

          {/* Submit Action Button */}
          <button
            type="button"
            disabled={isRunning || keywords.length === 0}
            onClick={handleStartRun}
            className={`w-full py-4 rounded-2xl font-heading font-bold text-base flex items-center justify-center gap-2.5 shadow-xl transition-all duration-200 ${
              isRunning
                ? "bg-slate-800 text-slate-400 cursor-not-allowed"
                : "bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 text-white hover:opacity-95 shadow-indigo-500/25 hover:shadow-indigo-500/40 active:scale-[0.99]"
            }`}
          >
            {isRunning ? (
              <>
                <div className="w-5 h-5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                <span>Executing Pipeline Nodes ({maxResults} target)...</span>
              </>
            ) : (
              <>
                <Play className="w-5 h-5 fill-current" />
                <span>Launch Lead Discovery ({maxResults} Target)</span>
              </>
            )}
          </button>
        </div>

        {/* Right Column: Geo Visualizer & Keyword Plan Inspector (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
            <h3 className="text-sm font-heading font-semibold text-slate-200">
              Resolved Geographic Boundary
            </h3>
            <MapPreview geo={geoPreview} />
            {geoPreview && (
              <div className="text-xs text-slate-400 font-mono space-y-1">
                <div>Display: <span className="text-slate-200">{geoPreview.display_name}</span></div>
                <div>Kind: <span className="text-indigo-400">{geoPreview.boundary_kind}</span></div>
              </div>
            )}
          </div>

          {/* Keyword Plan Popover / Details */}
          {selectedPlanPreview && (
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3 animate-in fade-in">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-mono font-bold text-indigo-400 uppercase tracking-wider">
                  Keyword Plan: {selectedPlanPreview.keyword}
                </h4>
                <button
                  onClick={() => setSelectedPlanPreview(null)}
                  className="text-xs text-slate-500 hover:text-slate-300"
                >
                  ✕
                </button>
              </div>
              <div className="text-xs text-slate-300 space-y-2">
                <div>
                  <span className="text-slate-500">Synonyms: </span>
                  {selectedPlanPreview.synonyms.join(", ")}
                </div>
                <div>
                  <span className="text-slate-500">OSM Tags: </span>
                  <code className="text-emerald-400 bg-slate-950 px-1 py-0.5 rounded">
                    {selectedPlanPreview.osm_tag_filters.join(" | ")}
                  </code>
                </div>
                <div>
                  <span className="text-slate-500">Planner: </span>
                  <span className="text-cyan-400 font-mono">{selectedPlanPreview.planner}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Live Graph View during / after execution */}
      {(isRunning || Object.keys(nodeEvents).length > 0) && (
        <RunGraphView nodeEvents={nodeEvents} />
      )}
    </div>
  );
};
