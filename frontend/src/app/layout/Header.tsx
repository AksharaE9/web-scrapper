import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { qk } from "../../lib/queryKeys";
import { useUiPrefs } from "../../stores/useUiPrefs";
import {
  Sun,
  Moon,
  Database,
  Activity,
  Maximize2,
  Minimize2,
  Server,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";

export const Header: React.FC = () => {
  const { theme, setTheme, density, setDensity } = useUiPrefs();
  const [showHealthPopover, setShowHealthPopover] = useState(false);

  const { data: health } = useQuery({
    queryKey: qk.health,
    queryFn: () => api.getHealth(),
    refetchInterval: 20000,
    staleTime: 15000,
  });

  const isHealthy = health?.status === "ok";
  const isDegraded = health?.status === "degraded";

  return (
    <header className="h-14 border-b border-border-subtle bg-surface-1 px-4 md:px-6 flex items-center justify-between z-30 sticky top-0">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold tracking-wider font-mono shadow-sm">
          L0
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-tight text-text-primary">
              LeadCore Zero
            </span>
            <Badge variant="outline" size="sm" className="text-[10px] uppercase font-mono tracking-wider">
              v3.0 Engine
            </Badge>
          </div>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2 md:gap-3">
        {/* Live Health Cluster Indicator */}
        <div className="relative">
          <button
            onClick={() => setShowHealthPopover((p) => !p)}
            className="flex items-center gap-2 px-2.5 py-1 rounded-full border border-border-subtle hover:bg-surface-2 transition-colors cursor-pointer text-xs"
            title="Backend Health Status"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isHealthy
                  ? "bg-emerald-500 animate-pulse"
                  : isDegraded
                  ? "bg-amber-500"
                  : "bg-rose-500"
              }`}
            />
            <span className="font-mono text-text-secondary hidden sm:inline">
              {health?.status ? health.status.toUpperCase() : "CHECKING"}
            </span>
          </button>

          {/* Health Popover Details */}
          {showHealthPopover && (
            <div className="absolute right-0 mt-2 w-72 p-3 bg-surface-1 rounded-lg border border-border-strong shadow-xl z-50 text-xs font-mono">
              <div className="font-bold text-text-primary mb-2 flex items-center justify-between border-b border-border-subtle pb-1">
                <span>SYSTEM HEALTH</span>
                <Badge variant={isHealthy ? "good" : "warning"}>
                  {health?.status || "unknown"}
                </Badge>
              </div>
              <div className="space-y-1.5 text-text-secondary">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5"><Database className="w-3.5 h-3.5" /> PostgreSQL (Neon)</span>
                  <span className={health?.neon?.status === "ok" ? "text-emerald-500" : "text-rose-500"}>
                    {health?.neon?.status || "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5"><Server className="w-3.5 h-3.5" /> Overture Places</span>
                  <span className={health?.overture?.status === "ok" ? "text-emerald-500" : "text-rose-500"}>
                    {health?.overture?.latest_release || health?.overture?.status || "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5"><Activity className="w-3.5 h-3.5" /> OpenStreetMap (OSM)</span>
                  <span className={health?.overpass?.status === "ok" ? "text-emerald-500" : "text-rose-500"}>
                    {health?.overpass?.status || "—"}
                  </span>
                </div>
                {health?.queue && (
                  <div className="pt-2 mt-2 border-t border-border-subtle space-y-1">
                    <div className="flex items-center justify-between text-[11px] font-semibold text-text-primary">
                      <span>Worker Queue</span>
                      <span className={
                        health.queue.worker.state === "healthy"
                          ? "text-emerald-500"
                          : health.queue.worker.state === "degraded"
                          ? "text-amber-500"
                          : "text-rose-500"
                      }>
                        {health.queue.worker.state.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-text-muted">
                      <span>Queued / Running</span>
                      <span>{health.queue.depth.queued} / {health.queue.depth.running}</span>
                    </div>
                    {health.queue.depth.oldest_queued_age_s > 60 && (
                      <div className="text-[10px] text-amber-500">
                        Oldest waiting: {Math.round(health.queue.depth.oldest_queued_age_s / 60)}m
                      </div>
                    )}
                    {health.queue.worker.last_error && (
                      <div className="text-[10px] text-rose-400 break-all pt-0.5">
                        {health.queue.worker.last_error.slice(0, 80)}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Density Toggle */}
        <button
          onClick={() => setDensity(density === "comfortable" ? "compact" : "comfortable")}
          className="p-1.5 rounded-md border border-border-subtle text-text-secondary hover:text-text-primary hover:bg-surface-2 transition-colors cursor-pointer"
          title={`Density: ${density} (Click to toggle)`}
        >
          {density === "comfortable" ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>

        {/* Theme Toggle */}
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="p-1.5 rounded-md border border-border-subtle text-text-secondary hover:text-text-primary hover:bg-surface-2 transition-colors cursor-pointer"
          title={`Theme: ${theme}`}
        >
          {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
