import React from "react";
import { cn } from "../../lib/cn";

export interface StatTileProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  className?: string;
}

export function StatTile({ label, value, subtext, icon, badge, className }: StatTileProps) {
  return (
    <div className={cn("p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm flex flex-col justify-between", className)}>
      <div className="flex items-center justify-between text-text-muted text-xs font-medium">
        <span className="flex items-center gap-1.5">
          {icon}
          {label}
        </span>
        {badge}
      </div>
      <div className="mt-2 text-2xl font-bold text-text-primary tracking-tight font-mono">
        {value}
      </div>
      {subtext && <div className="mt-1 text-xs text-text-muted">{subtext}</div>}
    </div>
  );
}
