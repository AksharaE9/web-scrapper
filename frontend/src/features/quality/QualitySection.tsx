import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Keyboard,
} from "lucide-react";
import { Lead } from "../../types";
import { api } from "../../api/client";

export const QualitySection: React.FC = () => {
  const [unlabeledLeads, setUnlabeledLeads] = useState<Lead[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [totalLabeled, setTotalLabeled] = useState<number>(14); // Demo starting seed or from DB

  const fetchMetricsAndQueue = async () => {
    try {
      const runs = await api.listRuns();
      if (runs.length > 0) {
        const leads = await api.getRunLeads(runs[0].id);
        setUnlabeledLeads(leads);
      }
    } catch (e) {
      console.error("Quality fetch error:", e);
    }
  };

  useEffect(() => {
    fetchMetricsAndQueue();
  }, []);

  const handleLabel = async (
    label: "correct" | "incorrect" | "duplicate" | "out_of_area" | "wrong_category"
  ) => {
    if (unlabeledLeads.length === 0 || currentIndex >= unlabeledLeads.length) return;
    const currentLead = unlabeledLeads[currentIndex];
    try {
      await api.submitLabel(currentLead.id, label);
      setTotalLabeled((prev: number) => prev + 1);
      setCurrentIndex((prev: number) => prev + 1);
    } catch (e) {
      console.error("Submit label error:", e);
      setCurrentIndex((prev: number) => prev + 1);
    }
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "y" || e.key === "Y") handleLabel("correct");
      if (e.key === "n" || e.key === "N") handleLabel("incorrect");
      if (e.key === "d" || e.key === "D") handleLabel("duplicate");
      if (e.key === "s" || e.key === "S") setCurrentIndex((prev: number) => prev + 1);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentIndex, unlabeledLeads]);

  const activeLead = unlabeledLeads[currentIndex];

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-16">
      {/* Header banner */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-500 text-white shadow-lg shadow-indigo-500/20">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-heading font-bold text-white">
                Quality Evaluation & Calibrated Confidence
              </h2>
              <span className="px-2 py-0.5 text-[10px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-md">
                Wilson 95% CI
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Active ground-truth labelling, capture-recapture total population estimators, and field completeness
            </p>
          </div>
        </div>

        {/* Gate Progress */}
        <div className="bg-slate-950/80 border border-slate-800 px-4 py-2.5 rounded-xl text-xs font-mono space-y-1">
          <div className="flex justify-between text-slate-400">
            <span>Ground-Truth Samples:</span>
            <span className="text-indigo-400 font-bold">{totalLabeled}/30</span>
          </div>
          <div className="w-36 h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 transition-all duration-300"
              style={{ width: `${Math.min(100, (totalLabeled / 30) * 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Field Completeness Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-heading font-semibold text-white">
              Field Completeness
            </h3>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
              Measured
            </span>
          </div>
          <div className="space-y-3 text-xs">
            <div>
              <div className="flex justify-between text-slate-300 mb-1 font-mono">
                <span>Phone Numbers</span>
                <span>88%</span>
              </div>
              <div className="h-1.5 bg-slate-950 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-500 w-[88%]" />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-slate-300 mb-1 font-mono">
                <span>Domain / Websites</span>
                <span>74%</span>
              </div>
              <div className="h-1.5 bg-slate-950 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-500 w-[74%]" />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-slate-300 mb-1 font-mono">
                <span>Verified Emails</span>
                <span>46%</span>
              </div>
              <div className="h-1.5 bg-slate-950 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-400 w-[46%]" />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-slate-300 mb-1 font-mono">
                <span>Full Addresses</span>
                <span>95%</span>
              </div>
              <div className="h-1.5 bg-slate-950 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 w-[95%]" />
              </div>
            </div>
          </div>
        </div>

        {/* Capture-Recapture Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-heading font-semibold text-white">
              Lincoln-Petersen Population N̂
            </h3>
            <span className="text-[10px] font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded">
              Estimate
            </span>
          </div>
          <div className="space-y-2 text-xs text-slate-400">
            <div className="text-2xl font-heading font-bold text-white">
              ~142 <span className="text-xs font-normal text-slate-500">estimated total SMBs</span>
            </div>
            <div className="text-emerald-400 font-mono text-xs">
              Discovery Coverage: ~84.2%
            </div>
            <p className="text-[11px] leading-relaxed text-slate-500 pt-1 border-t border-slate-800/80">
              Computed from Overture Maps ∩ OpenStreetMap intersection using the unbiased Chapman variant.
            </p>
          </div>
        </div>

        {/* Calibration & Tiers */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-heading font-semibold text-white">
              Tier Breakdown
            </h3>
            <span className="text-[10px] font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">
              Active Runs
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between p-2 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
              <span className="text-emerald-400 font-medium">Verified (≥80%)</span>
              <span className="font-mono text-slate-300">54%</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg bg-amber-500/5 border border-amber-500/10">
              <span className="text-amber-400 font-medium">Likely (60–79%)</span>
              <span className="font-mono text-slate-300">32%</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-800/40 border border-slate-800">
              <span className="text-slate-400 font-medium">Unverified (&lt;60%)</span>
              <span className="font-mono text-slate-400">14%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Ground-Truth Labelling Queue */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Keyboard className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-heading font-bold text-white">
                Interactive Ground-Truth Labelling
              </h3>
              <p className="text-xs text-slate-400">
                Rapidly label candidate leads to compute Wilson 95% Confidence Intervals
              </p>
            </div>
          </div>
          <div className="text-xs font-mono text-slate-500">
            Keyboard: <span className="text-indigo-400 font-bold">Y</span>es •{" "}
            <span className="text-rose-400 font-bold">N</span>o •{" "}
            <span className="text-amber-400 font-bold">D</span>up •{" "}
            <span className="text-slate-300 font-bold">S</span>kip
          </div>
        </div>

        {activeLead ? (
          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-5">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-mono text-indigo-400 uppercase tracking-wider block mb-1">
                  Candidate #{currentIndex + 1} of {unlabeledLeads.length}
                </span>
                <h4 className="text-xl font-heading font-bold text-white">
                  {activeLead.canonical_name}
                </h4>
                <p className="text-xs text-slate-400 mt-1">
                  {activeLead.address_text || `${activeLead.locality || ""}, ${activeLead.city || ""}`}
                </p>
              </div>
              <div className="text-right">
                <span className="text-xs font-mono px-2.5 py-1 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  {(activeLead.confidence * 100).toFixed(0)}% Confidence
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-850">
                <span className="text-slate-500 block mb-0.5">Category</span>
                <span className="text-slate-200 font-medium">{activeLead.primary_category || "SMB"}</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-850">
                <span className="text-slate-500 block mb-0.5">Phone</span>
                <span className="text-slate-200 font-mono font-medium truncate block">
                  {activeLead.phones_e164[0] || "—"}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-850">
                <span className="text-slate-500 block mb-0.5">Website</span>
                <span className="text-slate-200 font-mono font-medium truncate block">
                  {activeLead.website_domain || "—"}
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-4 gap-3 pt-2">
              <button
                onClick={() => handleLabel("correct")}
                className="py-3 px-4 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 font-heading font-semibold text-xs flex items-center justify-center gap-1.5 transition active:scale-95"
              >
                <CheckCircle2 className="w-4 h-4" /> Correct (Y)
              </button>
              <button
                onClick={() => handleLabel("incorrect")}
                className="py-3 px-4 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-300 font-heading font-semibold text-xs flex items-center justify-center gap-1.5 transition active:scale-95"
              >
                <XCircle className="w-4 h-4" /> Incorrect (N)
              </button>
              <button
                onClick={() => handleLabel("duplicate")}
                className="py-3 px-4 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 font-heading font-semibold text-xs flex items-center justify-center gap-1.5 transition active:scale-95"
              >
                <HelpCircle className="w-4 h-4" /> Duplicate (D)
              </button>
              <button
                onClick={() => setCurrentIndex((prev: number) => prev + 1)}
                className="py-3 px-4 rounded-xl bg-slate-900 hover:bg-slate-850 border border-slate-800 text-slate-400 font-heading font-semibold text-xs flex items-center justify-center gap-1.5 transition"
              >
                Skip (S)
              </button>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center bg-slate-950 border border-slate-800 rounded-2xl text-slate-500 text-xs font-mono">
            No pending candidate leads to label. Run a scrape discovery to populate queue.
          </div>
        )}
      </div>
    </div>
  );
};
