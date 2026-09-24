import React from "react";
import { cn } from "../../lib/cn";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "verified" | "likely" | "unverified" | "accepted" | "review" | "rejected" | "outline" | "good" | "warning" | "critical";
  size?: "sm" | "md";
}

export function Badge({ className, variant = "default", size = "sm", children, ...props }: BadgeProps) {
  const base = "inline-flex items-center font-medium rounded-full border transition-colors";

  const variants = {
    default: "bg-surface-2 text-text-secondary border-border-subtle",
    verified: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    likely: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    unverified: "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20",
    accepted: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    review: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    rejected: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
    good: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    warning: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    critical: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
    outline: "border-border-strong text-text-primary bg-transparent",
  };

  const sizes = {
    sm: "px-2 py-0.5 text-xs gap-1",
    md: "px-2.5 py-1 text-xs gap-1.5",
  };

  return (
    <div className={cn(base, variants[variant], sizes[size], className)} {...props}>
      {children}
    </div>
  );
}
