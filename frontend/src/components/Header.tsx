import React, { useEffect, useState } from "react";
import {
  Moon,
  Sun,
  Sparkles,
} from "lucide-react";
import { HealthStatus } from "../types";
import { api } from "../api/client";

interface HeaderProps {
  darkMode: boolean;
  setDarkMode: (val: boolean) => void;
}

export const Header: React.FC<HeaderProps> = ({ darkMode, setDarkMode }) => {
  const [health, setHealth] = useState<HealthStatus | null>(null);

  const fetchHealth = async () => {
    try {
      const data = await api.getHealth();
      setHealth(data);
    } catch (e) {
      console.error("Health fetch error:", e);
    }
  };

  useEffect(() => {
    fetchHealth();
    const timer = setInterval(fetchHealth, 20000);
    return () => clearInterval(timer);
  }, []);

  const getStatusIcon = (status?: "ok" | "error" | "disabled" | "degraded") => {
    if (status === "ok") return <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />;
    if (status === "disabled") return <span className="w-2 h-2 rounded-full bg-slate-500" />;
    if (status === "degraded") return <span className="w-2 h-2 rounded-full bg-amber-400" />;
    return <span className="w-2 h-2 rounded-full bg-rose-500" />;
  };

  return (
    <header className="h-16 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Brand logo and version badge */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-heading font-bold text-lg text-white tracking-tight">
              LeadCore <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">Zero</span>
            </h1>
            <span className="px-1.5 py-0.5 text-[10px] font-mono font-medium rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              v2.0
            </span>
          </div>
          <p className="text-[11px] text-slate-400 font-medium">₹0-Cost Graph-Engineered Lead Intelligence</p>
        </div>
      </div>

      {/* Real-time Health Indicators */}
      <div className="flex items-center gap-4 bg-slate-900/60 border border-slate-800/80 px-3.5 py-1.5 rounded-full text-xs">
        <div className="flex items-center gap-1.5" title="Neon Serverless Postgres">
          {getStatusIcon(health?.neon?.status)}
          <span className="text-slate-300 font-medium">Neon</span>
        </div>
        <div className="w-px h-3 bg-slate-800" />
        <div className="flex items-center gap-1.5" title="Overture Maps S3">
          {getStatusIcon(health?.overture?.status)}
          <span className="text-slate-300 font-medium">Overture</span>
        </div>
        <div className="w-px h-3 bg-slate-800" />
        <div className="flex items-center gap-1.5" title="OpenStreetMap Overpass API">
          {getStatusIcon(health?.overpass?.status)}
          <span className="text-slate-300 font-medium">Overpass</span>
        </div>
        <div className="w-px h-3 bg-slate-800" />
        <div className="flex items-center gap-1.5" title="Nominatim / Photon Geocoding">
          {getStatusIcon(health?.nominatim?.status)}
          <span className="text-slate-300 font-medium">Nominatim</span>
        </div>
        <div className="w-px h-3 bg-slate-800" />
        <div className="flex items-center gap-1.5" title="Ollama Local LLM (Optional)">
          {getStatusIcon(health?.ollama?.status)}
          <span className="text-slate-400 text-[11px]">
            LLM {health?.ollama?.status === "disabled" ? "(Off)" : "(On)"}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700 transition"
          title="Toggle Theme"
        >
          {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
