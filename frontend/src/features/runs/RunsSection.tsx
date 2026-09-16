import React, { useState, useEffect } from "react";
import {
  PlaySquare,
  Search,
  FileSpreadsheet,
  FileText,
  Eye,
  RefreshCw,
  MapPin,
  Tag,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronRight,
  LayoutGrid,
  ListFilter,
} from "lucide-react";
import { Lead, RunSummary } from "../../types";
import { api } from "../../api/client";
import { LeadDrawer } from "./LeadDrawer";

interface RunsSectionProps {
  initialRunId?: string | null;
}

export const RunsSection: React.FC<RunsSectionProps> = ({ initialRunId }) => {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialRunId || null);
  const [selectedRun, setSelectedRun] = useState<RunSummary | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loadingLeads, setLoadingLeads] = useState<boolean>(false);
  const [loadingRuns, setLoadingRuns] = useState<boolean>(false);

  // Filters for leads table
  const [tierFilter, setTierFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeLead, setActiveLead] = useState<Lead | null>(null);

  // Filter for runs deck
  const [runSearchQuery, setRunSearchQuery] = useState<string>("");
  const [viewMode, setViewMode] = useState<"cards" | "compact">("compact");

  const fetchRuns = async () => {
    try {
      setLoadingRuns(true);
      const data = await api.listRuns();
      setRuns(data);
      if (data.length > 0 && !selectedRunId) {
        setSelectedRunId(data[0].id);
      }
    } catch (e) {
      console.error("List runs error:", e);
    } finally {
      setLoadingRuns(false);
    }
  };

  const fetchLeads = async (runId: string) => {
    try {
      setLoadingLeads(true);
      const data = await api.getRunLeads(runId, {
        tier: tierFilter === "all" ? undefined : tierFilter,
        search: searchQuery || undefined,
      });
      setLeads(data);
    } catch (e) {
      console.error("Get leads error:", e);
    } finally {
      setLoadingLeads(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  useEffect(() => {
    if (initialRunId) {
      setSelectedRunId(initialRunId);
    }
  }, [initialRunId]);

  useEffect(() => {
    if (selectedRunId) {
      const run = runs.find((r: RunSummary) => r.id === selectedRunId);
      if (run) setSelectedRun(run);
      fetchLeads(selectedRunId);
    }
  }, [selectedRunId, tierFilter, searchQuery, runs]);

  const handleLabel = async (
    leadId: string,
    label: "correct" | "incorrect" | "duplicate" | "out_of_area" | "wrong_category"
  ) => {
    try {
      await api.submitLabel(leadId, label);
      setLeads((prev: Lead[]) =>
        prev.map((l: Lead) => (l.id === leadId ? { ...l, user_label: label } : l))
      );
      if (activeLead && activeLead.id === leadId) {
        setActiveLead(null);
      }
    } catch (e) {
      console.error("Label submission error:", e);
    }
  };

  const filteredRuns = runs.filter((r: RunSummary) => {
    if (!runSearchQuery.trim()) return true;
    const query = runSearchQuery.toLowerCase();
    const loc = (r.locality || "").toLowerCase();
    const city = (r.city || "").toLowerCase();
    const kws = (r.keywords || []).join(" ").toLowerCase();
    const status = (r.status || "").toLowerCase();
    return loc.includes(query) || city.includes(query) || kws.includes(query) || status.includes(query);
  });

  const formatRunDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + ", " + d.toLocaleDateString([], { month: "short", day: "numeric" });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* ── Section Header & View Controls ────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/60 border border-slate-800 p-5 rounded-2xl">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400">
            <PlaySquare className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-heading font-bold text-white flex items-center gap-2">
              <span>Discovery Runs & Lead Database</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono">
                {runs.length} Runs
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Select any execution card to inspect golden records, field provenance, and export verified leads
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Run search bar */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={runSearchQuery}
              onChange={(e) => setRunSearchQuery(e.target.value)}
              placeholder="Filter runs..."
              className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 w-44"
            />
          </div>

          {/* View mode toggle */}
          <div className="flex items-center bg-slate-950 border border-slate-800 rounded-xl p-0.5">
            <button
              onClick={() => setViewMode("cards")}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-mono flex items-center gap-1.5 transition ${
                viewMode === "cards"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
              title="Cards Deck View"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Cards</span>
            </button>
            <button
              onClick={() => setViewMode("compact")}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-mono flex items-center gap-1.5 transition ${
                viewMode === "compact"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
              title="Compact Dropdown View"
            >
              <ListFilter className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Compact</span>
            </button>
          </div>

          <button
            onClick={fetchRuns}
            className="p-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition"
            title="Refresh Runs"
          >
            <RefreshCw className={`w-4 h-4 ${loadingRuns ? "animate-spin text-indigo-400" : ""}`} />
          </button>
        </div>
      </div>

      {/* ── Runs Cards Deck ──────────────────────────────────────────────────── */}
      {viewMode === "cards" ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {filteredRuns.length === 0 ? (
            <div className="col-span-full text-center py-10 bg-slate-900/30 border border-slate-800/80 rounded-2xl text-slate-500 text-xs font-mono">
              No discovery runs matched your filter.
            </div>
          ) : (
            filteredRuns.map((r: RunSummary) => {
              const isSelected = r.id === selectedRunId;
              const isCompleted = r.status === "completed";
              const isRunning = r.status === "running" || r.status === "queued";
              const isFailed = r.status === "failed" || r.status === "failed_no_sources";

              return (
                <div
                  key={r.id}
                  onClick={() => setSelectedRunId(r.id)}
                  className={`relative p-4 rounded-2xl border transition-all cursor-pointer text-left flex flex-col justify-between gap-3 group ${
                    isSelected
                      ? "bg-gradient-to-b from-indigo-950/40 to-slate-900/80 border-indigo-500 shadow-lg shadow-indigo-950/40 ring-1 ring-indigo-500/50"
                      : "bg-slate-900/50 hover:bg-slate-900/80 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  {/* Top: Locality and Status */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 text-xs font-heading font-bold text-white truncate">
                        <MapPin className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                        <span className="truncate">{r.locality || r.city || "Target Locality"}</span>
                        {r.city && r.locality && (
                          <span className="text-slate-400 font-normal font-sans">({r.city})</span>
                        )}
                      </div>

                      {/* Status Pill */}
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1 shrink-0 ${
                          isCompleted
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : isRunning
                            ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 animate-pulse"
                            : isFailed
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        }`}
                      >
                        {isRunning ? (
                          <Loader2 className="w-2.5 h-2.5 animate-spin" />
                        ) : isCompleted ? (
                          <CheckCircle2 className="w-2.5 h-2.5" />
                        ) : (
                          <AlertCircle className="w-2.5 h-2.5" />
                        )}
                        <span>{r.status}</span>
                      </span>
                    </div>

                    {/* Keywords pills */}
                    <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                      {(r.keywords || ["SMB"]).map((kw, i) => (
                        <span
                          key={i}
                          className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-slate-950 border border-slate-800 text-slate-300 flex items-center gap-1"
                        >
                          <Tag className="w-2.5 h-2.5 text-indigo-400" />
                          <span className="truncate max-w-[150px]">{kw}</span>
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Bottom info bar */}
                  <div className="flex items-center justify-between pt-2.5 border-t border-slate-800/60 text-[11px] font-mono text-slate-400">
                    <span className="flex items-center gap-1 text-slate-500">
                      <Clock className="w-3 h-3" />
                      {formatRunDate(r.created_at)}
                    </span>
                    <span className="flex items-center gap-1 text-indigo-400 font-semibold group-hover:text-indigo-300 transition">
                      <span>{isSelected ? "Active Run" : "Select Run"}</span>
                      <ChevronRight className="w-3 h-3" />
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      ) : (
        /* Compact dropdown selector */
        <div className="flex items-center gap-3 bg-slate-900/40 p-4 rounded-xl border border-slate-800">
          <label className="text-xs font-mono text-slate-400 shrink-0">Selected Run:</label>
          <select
            value={selectedRunId || ""}
            onChange={(e) => setSelectedRunId(e.target.value)}
            className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs font-mono focus:outline-none focus:border-indigo-500"
          >
            {runs.map((r: RunSummary) => (
              <option key={r.id} value={r.id}>
                {r.locality || r.city || "Run"} ({r.keywords?.join(", ")}) — {r.status} ({formatRunDate(r.created_at)})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* ── Selected Run KPIs ─────────────────────────────────────────────────── */}
      {selectedRun && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 animate-fadeIn">
          <div className="p-4 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-1">
            <span className="text-xs text-slate-500 font-mono">Discovered Leads</span>
            <div className="text-2xl font-heading font-bold text-white flex items-center gap-2">
              <span>{leads.length}</span>
              {loadingLeads && <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />}
            </div>
          </div>
          <div className="p-4 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-1">
            <span className="text-xs text-slate-500 font-mono">Verified Ratio</span>
            <div className="text-2xl font-heading font-bold text-emerald-400">
              {leads.length > 0
                ? `${Math.round(
                    (leads.filter((l: Lead) => l.tier === "Verified").length / leads.length) * 100
                  )}%`
                : "0%"}
            </div>
          </div>
          <div className="p-4 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-1">
            <span className="text-xs text-slate-500 font-mono">Multi-Source Agreement</span>
            <div className="text-2xl font-heading font-bold text-indigo-400">
              {leads.filter((l: Lead) => l.independent_source_count >= 2).length}
            </div>
          </div>
          <div className="p-4 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-1">
            <span className="text-xs text-slate-500 font-mono">Run Status</span>
            <div className="text-sm font-heading font-bold text-slate-200 mt-2 capitalize flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              {selectedRun.status}
            </div>
          </div>
        </div>
      )}

      {/* ── Leads Table & Filter Bar ─────────────────────────────────────────── */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
        {/* Filters and Exports */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-1 max-w-md">
            <div className="relative w-full">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                placeholder="Search business name, phone, domain..."
                className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <select
              value={tierFilter}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setTierFilter(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 font-mono focus:outline-none focus:border-indigo-500"
            >
              <option value="all">All Tiers</option>
              <option value="Verified">Verified</option>
              <option value="Likely">Likely</option>
              <option value="Unverified">Unverified</option>
            </select>
          </div>

          {/* Export Buttons with attribution sheet */}
          {selectedRunId && (
            <div className="flex items-center gap-2">
              <a
                href={api.getExportUrl(selectedRunId, "csv")}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 font-mono flex items-center gap-1.5 transition"
              >
                <FileText className="w-3.5 h-3.5 text-indigo-400" />
                <span>CSV</span>
              </a>
              <a
                href={api.getExportUrl(selectedRunId, "xlsx")}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 font-mono flex items-center gap-1.5 transition"
              >
                <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
                <span>XLSX (Attribution)</span>
              </a>
            </div>
          )}
        </div>

        {/* Data Table */}
        <div className="border border-slate-800 rounded-xl overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 font-mono text-[11px] border-b border-slate-800">
              <tr>
                <th className="p-3">Rank</th>
                <th className="p-3">Business Name</th>
                <th className="p-3">Category</th>
                <th className="p-3">Phone</th>
                <th className="p-3">Website</th>
                <th className="p-3">Confidence</th>
                <th className="p-3">Tier</th>
                <th className="p-3">Sources</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-10 text-slate-500">
                    {loadingLeads ? (
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                        <span>Loading leads from database...</span>
                      </div>
                    ) : (
                      "No leads found for this run/filter."
                    )}
                  </td>
                </tr>
              ) : (
                leads.map((lead: Lead, idx: number) => (
                  <tr
                    key={lead.id}
                    className="hover:bg-slate-900/70 transition cursor-pointer group"
                    onClick={() => setActiveLead(lead)}
                  >
                    <td className="p-3 font-mono text-slate-500">#{idx + 1}</td>
                    <td className="p-3 font-medium text-white">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="group-hover:text-indigo-300 transition">{lead.canonical_name}</span>
                        {lead.distance_km != null && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-mono flex items-center gap-0.5 whitespace-nowrap" title={`Distance from locality centroid: ${lead.distance_km} km`}>
                            <MapPin className="w-2.5 h-2.5 text-indigo-400" />
                            {lead.distance_km < 1 ? `${Math.round(lead.distance_km * 1000)}m` : `${lead.distance_km} km`}
                          </span>
                        )}
                        {lead.is_new_business && (
                          <span className="text-[9px] px-1 py-0.2 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-mono">
                            NEW
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="p-3 text-slate-400 truncate max-w-[130px]">
                      {lead.primary_category || "SMB"}
                    </td>
                    <td className="p-3 font-mono text-slate-300">
                      {lead.phones_e164 && lead.phones_e164[0] ? lead.phones_e164[0] : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="p-3 font-mono text-slate-400 truncate max-w-[140px]">
                      {lead.website_domain || (lead.website_url ? lead.website_url.replace(/^https?:\/\//, "") : <span className="text-slate-600">—</span>)}
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-indigo-500 to-emerald-400"
                            style={{ width: `${Math.min(100, (lead.confidence || 0) * 100)}%` }}
                          />
                        </div>
                        <span className="font-mono text-[10px] text-slate-400">
                          {((lead.confidence || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium ${
                          lead.tier === "Verified"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : lead.tier === "Likely"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {lead.tier}
                      </span>
                    </td>
                    <td className="p-3 font-mono text-slate-400">
                      {lead.independent_source_count || 1}
                    </td>
                    <td className="p-3 text-right">
                      <button
                        onClick={(e: React.MouseEvent) => {
                          e.stopPropagation();
                          setActiveLead(lead);
                        }}
                        className="p-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-400 hover:text-white hover:border-indigo-500 transition"
                        title="Inspect Provenance & Details"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Lead Inspection Drawer ────────────────────────────────────────────── */}
      <LeadDrawer
        lead={activeLead}
        onClose={() => setActiveLead(null)}
        onLabel={handleLabel}
      />
    </div>
  );
};
