import React from "react";
import { NavLink } from "react-router-dom";
import { Sparkles, Database, BarChart3, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useUiPrefs } from "../../stores/useUiPrefs";
import { useRunTracker } from "../../stores/useRunTracker";
import { cn } from "../../lib/cn";

export const LeftRailNav: React.FC = () => {
  const { railCollapsed, toggleRail } = useUiPrefs();
  const getActiveCount = useRunTracker((s) => s.getActiveCount);
  const runningCount = getActiveCount();

  const navItems = [
    {
      to: "/scrape",
      label: "Scrape",
      icon: <Sparkles className="w-4 h-4" />,
      badge: null,
    },
    {
      to: "/runs",
      label: "Runs",
      icon: <Database className="w-4 h-4" />,
      badge: runningCount > 0 ? `${runningCount} active` : null,
    },
    {
      to: "/quality",
      label: "Quality",
      icon: <BarChart3 className="w-4 h-4" />,
      badge: null,
    },
  ];

  return (
    <aside
      className={cn(
        "border-r border-border-subtle bg-surface-1 transition-all duration-200 flex flex-col justify-between z-20",
        railCollapsed ? "w-16" : "w-56"
      )}
    >
      <div className="p-3 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer",
                isActive
                  ? "bg-accent/10 text-accent font-semibold"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-2",
                railCollapsed && "justify-center px-0"
              )
            }
            title={railCollapsed ? item.label : undefined}
          >
            {item.icon}
            {!railCollapsed && <span className="flex-1">{item.label}</span>}
            {!railCollapsed && item.badge && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20 animate-pulse">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </div>

      {/* Footer / Rail Collapse Toggle */}
      <div className="p-3 border-t border-border-subtle flex items-center justify-between">
        {!railCollapsed && (
          <span className="text-[11px] font-mono text-text-muted">LEADCORE 3.0</span>
        )}
        <button
          onClick={toggleRail}
          className="p-1.5 rounded-md hover:bg-surface-2 text-text-muted hover:text-text-primary transition-colors cursor-pointer mx-auto"
          title={railCollapsed ? "Expand Rail" : "Collapse Rail"}
        >
          {railCollapsed ? (
            <PanelLeftOpen className="w-4 h-4" />
          ) : (
            <PanelLeftClose className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
  );
};
