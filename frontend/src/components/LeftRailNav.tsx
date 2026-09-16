import React from "react";
import { Radar, PlaySquare, ShieldCheck, Database } from "lucide-react";

export type TabType = "scrape" | "runs" | "quality";

interface LeftRailNavProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  runningCount: number;
}

export const LeftRailNav: React.FC<LeftRailNavProps> = ({
  activeTab,
  setActiveTab,
  runningCount,
}) => {
  const tabs = [
    {
      id: "scrape" as TabType,
      label: "1. Scrape",
      sub: "Discovery & Planning",
      icon: Radar,
    },
    {
      id: "runs" as TabType,
      label: "2. Runs",
      sub: "Live Feed & Leads",
      icon: PlaySquare,
      badge: runningCount > 0 ? runningCount : undefined,
    },
    {
      id: "quality" as TabType,
      label: "3. Quality",
      sub: "Calibration & Labels",
      icon: ShieldCheck,
    },
  ];

  return (
    <aside className="w-64 border-r border-slate-800/80 bg-slate-950/40 p-4 flex flex-col justify-between shrink-0">
      <nav className="space-y-2">
        <div className="px-3 py-2 text-[10px] font-mono tracking-wider text-slate-500 uppercase font-semibold">
          Workflows
        </div>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3.5 px-3.5 py-3 rounded-xl text-left transition-all duration-200 group ${
                isActive
                  ? "bg-gradient-to-r from-indigo-600/20 to-cyan-500/10 border border-indigo-500/30 text-white shadow-lg shadow-indigo-950/40"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent"
              }`}
            >
              <div
                className={`p-2 rounded-lg transition-colors ${
                  isActive
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-900 text-slate-400 group-hover:text-slate-200"
                }`}
              >
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-heading font-semibold text-sm">{tab.label}</span>
                  {tab.badge !== undefined && (
                    <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-indigo-500 text-white rounded-full animate-pulse">
                      {tab.badge}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 truncate">{tab.sub}</p>
              </div>
            </button>
          );
        })}
      </nav>

      {/* System stats badge at bottom */}
      <div className="bg-slate-900/40 border border-slate-800/60 rounded-xl p-3 text-xs text-slate-400 space-y-1.5">
        <div className="flex items-center justify-between text-slate-300 font-medium">
          <span className="flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-indigo-400" />
            Zero Keyless Infra
          </span>
          <span className="text-[10px] text-emerald-400 font-mono">ACTIVE</span>
        </div>
        <p className="text-[11px] leading-relaxed text-slate-500">
          Overture S3 + Overpass OSM + Nominatim + Local RAG. No billing accounts required.
        </p>
      </div>
    </aside>
  );
};
